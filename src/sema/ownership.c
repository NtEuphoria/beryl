#include "ownership.h"
#include "intrinsic.h"
#include "access.h"

typedef enum { OS_UNINIT = 0, OS_INIT, OS_MOVED } OwnState;

typedef struct LoopFlow {
    uint8_t *breaks, *continues;
    struct LoopFlow *parent;
} LoopFlow;

typedef struct {
    Arena   *a;
    DiagBag *d;
    Program *p;
    Item    *fn;
    Local  **locals;
    uint32_t nlocals;
    bool     quiet;       /* true while iterating a loop to a fixpoint */
    bool     unreachable; /* set after a `return` on this path */
    LoopFlow *loop;
} O;

/* Diagnostics are suppressed during the quiet fixpoint passes so a loop body
 * reports each problem once rather than once per iteration. */
static Diag *err(O *o, uint32_t code, Span at, const char *fmt, ...) {
    if (o->quiet) return NULL;
    va_list ap;
    va_start(ap, fmt);
    SB sb;
    sb_init(&sb, o->a);
    sb_vfmt(&sb, fmt, ap);
    va_end(ap);
    Str msg = sb_finish(&sb);
    return diag_error(o->d, code, at, "%.*s", (int)msg.len, msg.ptr);
}

/* ---- state snapshots for branch merging -------------------------------- */

static uint8_t *snapshot(O *o) {
    uint8_t *s = ARENA_ARRAY(o->a, uint8_t, o->nlocals ? o->nlocals : 1);
    for (uint32_t i = 0; i < o->nlocals; i++) s[i] = o->locals[i]->state;
    return s;
}

static void restore(O *o, const uint8_t *s) {
    for (uint32_t i = 0; i < o->nlocals; i++) o->locals[i]->state = s[i];
}

/* MOVED absorbs; UNINIT beats INIT so a maybe-uninitialized read is caught. */
static uint8_t merge_state(uint8_t x, uint8_t y) {
    if (x == OS_MOVED || y == OS_MOVED) return OS_MOVED;
    if (x == OS_UNINIT || y == OS_UNINIT) return OS_UNINIT;
    return OS_INIT;
}

static void merge_into(O *o, const uint8_t *other) {
    for (uint32_t i = 0; i < o->nlocals; i++)
        o->locals[i]->state = merge_state(o->locals[i]->state, other[i]);
}

static bool states_equal(O *o, const uint8_t *s) {
    for (uint32_t i = 0; i < o->nlocals; i++)
        if (o->locals[i]->state != s[i]) return false;
    return true;
}

static void record_exit(O *o, uint8_t **state) {
    if (!*state) *state = snapshot(o);
    else for (uint32_t i = 0; i < o->nlocals; i++)
        (*state)[i] = merge_state((*state)[i], o->locals[i]->state);
}

static void check_set_exit(O *o, Span at) {
    for (uint32_t i = 0; i < o->nlocals; i++) {
        Local *l = o->locals[i];
        if (!l->is_param || l->conv != CONV_SET || l->state == OS_INIT) continue;
        Diag *dg = err(o, 404, at,
                       "`set` parameter `%.*s` is not initialized on this path",
                       (int)l->name.len, l->name.ptr);
        if (dg) {
            diag_label(dg, l->span, "declared `set` here, so the callee must assign it");
            diag_label(dg, at, "can return without assigning it");
        }
    }
}

/* Marks the binding declared at `sp` with name `n` as initialized. Used for
 * loop variables and catch bindings, which are bound by the construct itself
 * rather than by an assignment. */
static void mark_init(O *o, Span sp, Str n) {
    for (uint32_t i = 0; i < o->nlocals; i++) {
        Local *l = o->locals[i];
        if (l->span.offset == sp.offset && str_eq(l->name, n)) {
            l->state = OS_INIT;
            return;
        }
    }
}

/* ---- access paths ------------------------------------------------------ */

#define ACC_MAX_FIELDS 6

typedef struct {
    Local  *root;
    Str     fields[ACC_MAX_FIELDS];
    uint8_t nfields;
    bool    has_index; /* an unknown element: conflicts with any sibling */
    bool    valid;
    Span    span;
} Access;

/* Builds the storage an expression denotes, if it denotes any. */
static Access path_of(const Expr *e) {
    Access ac = {0};
    ac.span   = e ? e->span : SPAN_NONE;

    Str         rev[ACC_MAX_FIELDS];
    int         n   = 0;
    const Expr *cur = e;

    while (cur) {
        if (cur->kind == EX_FIELD) {
            if (n < ACC_MAX_FIELDS) rev[n++] = cur->field.name;
            else ac.has_index = true; /* collapse to a conservative root overlap */
            cur = cur->field.base;
            continue;
        }
        if (cur->kind == EX_INDEX) {
            ac.has_index = true;
            cur          = cur->index.base;
            continue;
        }
        break;
    }

    if (cur && (cur->kind == EX_PATH || cur->kind == EX_SELF) &&
        cur->res_kind == RES_LOCAL && cur->res) {
        ac.root  = (Local *)cur->res;
        ac.valid = true;
        for (int i = n - 1, k = 0; i >= 0; i--, k++) ac.fields[k] = rev[i];
        ac.nfields = (uint8_t)n;
    }
    return ac;
}

/* True when two paths can name overlapping storage. */
static bool overlaps(const Access *x, const Access *y) {
    if (!x->valid || !y->valid) return false;
    if (x->root != y->root) return false;
    if (x->has_index || y->has_index) return true;

    uint8_t n = x->nfields < y->nfields ? x->nfields : y->nfields;
    for (uint8_t i = 0; i < n; i++)
        if (!str_eq(x->fields[i], y->fields[i])) return false;
    return true; /* one is a prefix of the other, or they are equal */
}

static Str path_text(O *o, const Access *ac) {
    SB sb;
    sb_init(&sb, o->a);
    sb_str(&sb, ac->root->name);
    for (uint8_t i = 0; i < ac->nfields; i++) {
        sb_char(&sb, '.');
        sb_str(&sb, ac->fields[i]);
    }
    if (ac->has_index) sb_cstr(&sb, "[..]");
    return sb_finish(&sb);
}

/* ---- reads, writes, moves ---------------------------------------------- */

static void check_read(O *o, const Expr *e) {
    Access ac = path_of(e);
    if (!ac.valid) return;
    Local *l = ac.root;

    if (l->state == OS_MOVED) {
        Diag *dg = err(o, 403, e->span, "use of `%.*s` after it was moved",
                       (int)l->name.len, l->name.ptr);
        if (dg) {
            diag_label(dg, l->moved_at, "moved here");
            diag_label(dg, e->span, "used here after the move");
            diag_help(dg, "pass a copy, or restructure so the move happens last");
        }
    } else if (l->state == OS_UNINIT) {
        Diag *dg = err(o, 405, e->span, "`%.*s` is used before it is initialized",
                       (int)l->name.len, l->name.ptr);
        if (dg) {
            diag_label(dg, l->span, "declared here without a value");
            diag_label(dg, e->span, "read here");
        }
    }
}

static void walk_expr(O *o, Expr *e);
static void walk_block(O *o, Expr *b);

/* Compute a destination without treating an uninitialized whole binding as
 * a read. Index expressions still execute and must receive all analyses. */
static void walk_place(O *o, Expr *e) {
    if (!e) return;
    if (e->kind == EX_FIELD) walk_place(o, e->field.base);
    else if (e->kind == EX_INDEX) {
        walk_expr(o, e->index.base);
        walk_expr(o, e->index.index);
    } else if (e->kind != EX_PATH && e->kind != EX_SELF) walk_expr(o, e);
}

static void do_move(O *o, Expr *e) {
    Access ac = path_of(e);
    if (!ac.valid) {
        walk_expr(o, e);
        return;
    }
    Local *l = ac.root;

    if (ac.nfields > 0 || ac.has_index) {
        Str   name = path_text(o, &ac);
        Diag *dg   = err(o, 406, e->span, "cannot move out of `%.*s`", (int)name.len,
                         name.ptr);
        if (dg) {
            diag_note(dg, "a partial move would leave `%.*s` in a state with no name",
                      (int)l->name.len, l->name.ptr);
            diag_help(dg, "copy the value out instead, or move the whole binding");
        }
        return;
    }
    if (l->is_param && (l->conv == CONV_LET || l->conv == CONV_INOUT)) {
        Diag *dg = err(o, 406, e->span, "cannot move out of the borrowed parameter `%.*s`",
                       (int)l->name.len, l->name.ptr);
        if (dg) {
            diag_label(dg, l->span, "declared `%s` here, so it is borrowed, not owned",
                       conv_name(l->conv));
            diag_help(dg, "declare the parameter `sink` if the function should consume it");
        }
        return;
    }

    check_read(o, e);
    l->state    = OS_MOVED;
    l->moved_at = e->span;
}

/* No two accesses in one call may overlap when either is exclusive. The
 * receiver of a method taking `inout self` counts as one of them, and so does
 * the receiver of a list mutator. `len` and `get` count as shared reads. */
typedef struct {
    Access ac;
    bool   excl;
} CallAccess;
typedef VEC(CallAccess) CallAccessVec;

static bool list_mutator(const Expr *e) {
    return e && e->kind == EX_CALL && e->res_kind == RES_INTRINSIC &&
           (e->intrinsic == INTR_LIST_PUSH || e->intrinsic == INTR_LIST_SET ||
            e->intrinsic == INTR_LIST_CLEAR);
}

static bool list_reader(const Expr *e) {
    return e && e->kind == EX_CALL && e->res_kind == RES_INTRINSIC &&
           (e->intrinsic == INTR_LIST_LEN || e->intrinsic == INTR_LIST_GET);
}

static void note_access(O *o, CallAccessVec *out, Access ac, bool excl) {
    CallAccess slot;
    slot.ac = ac;
    slot.excl = excl;
    vec_push(o->a, *out, slot);
}

static void deny_restrict(Item *target, Span at) {
    if (!target || target->kind != IT_FN || !target->restrict_admitted) return;
    target->restrict_admitted = false;
    target->restrict_blocker = at;
}

/* List receivers inside an argument are live for the whole call, same as a
 * direct argument. `xs.set(i, xs.get(0))` is therefore one exclusive read of
 * `xs` overlapping a shared one. */
static void collect_list_receivers(O *o, const Expr *e, CallAccessVec *out) {
    if (!e) return;
    if (list_mutator(e) || list_reader(e)) {
        const Expr *base = e->call.callee && e->call.callee->kind == EX_FIELD
                               ? e->call.callee->field.base : NULL;
        Access ac = path_of(base);
        if (base) ac.span = base->span;
        note_access(o, out, ac, list_mutator(e));
        for (uint32_t i = 0; i < e->call.args.len; i++)
            collect_list_receivers(o, e->call.args.data[i].value, out);
        return;
    }
    switch (e->kind) {
        case EX_FIELD: collect_list_receivers(o, e->field.base, out); break;
        case EX_INDEX:
            collect_list_receivers(o, e->index.base, out);
            collect_list_receivers(o, e->index.index, out);
            break;
        case EX_UNARY: collect_list_receivers(o, e->unary.operand, out); break;
        case EX_BINARY:
            collect_list_receivers(o, e->binary.lhs, out);
            collect_list_receivers(o, e->binary.rhs, out);
            break;
        case EX_CALL:
            if (e->call.callee) collect_list_receivers(o, e->call.callee, out);
            for (uint32_t i = 0; i < e->call.args.len; i++)
                collect_list_receivers(o, e->call.args.data[i].value, out);
            break;
        case EX_CAST: collect_list_receivers(o, e->cast.value, out); break;
        case EX_IF:
            collect_list_receivers(o, e->if_expr.cond, out);
            collect_list_receivers(o, e->if_expr.then_blk, out);
            collect_list_receivers(o, e->if_expr.else_blk, out);
            break;
        case EX_BLOCK:
            for (uint32_t i = 0; i < e->block.stmts.len; i++) {
                const Stmt *s = e->block.stmts.data[i];
                if (!s) continue;
                if (s->kind == ST_LET) collect_list_receivers(o, s->let.init, out);
                else if (s->kind == ST_EXPR || s->kind == ST_RETURN || s->kind == ST_DEFER)
                    collect_list_receivers(o, s->expr, out);
                else if (s->kind == ST_ASSIGN) {
                    collect_list_receivers(o, s->assign.target, out);
                    collect_list_receivers(o, s->assign.value, out);
                }
            }
            break;
        default: break;
    }
}

static void check_call_exclusivity(O *o, Expr *call) {
    CallAccessVec acc = {0};
    Expr *callee = call->call.callee;
    Item *target = (call->res_kind == RES_FN) ? (Item *)call->res : NULL;
    bool  has_self = target && target->kind == IT_FN && target->fn.params.len > 0 &&
                    target->fn.params.data[0].is_self;

    if ((list_mutator(call) || list_reader(call)) && callee && callee->kind == EX_FIELD) {
        Access ac = path_of(callee->field.base);
        ac.span = callee->field.base ? callee->field.base->span : call->span;
        note_access(o, &acc, ac, list_mutator(call));
    } else if (has_self && callee && callee->kind == EX_FIELD) {
        Access ac = path_of(callee->field.base);
        bool excl = target->fn.params.data[0].conv == CONV_INOUT ||
                    target->fn.params.data[0].conv == CONV_SET;
        note_access(o, &acc, ac, excl);
    }

    for (uint32_t i = 0; i < call->call.args.len; i++) {
        Access ac = path_of(call->call.args.data[i].value);
        /* Label the whole argument, `inout a`, not just the operand. */
        ac.span = call->call.args.data[i].span;
        bool excl = call->call.args.data[i].conv == CONV_INOUT ||
                    call->call.args.data[i].conv == CONV_SET;
        note_access(o, &acc, ac, excl);
        collect_list_receivers(o, call->call.args.data[i].value, &acc);
    }

    for (uint32_t i = 0; i < acc.len; i++) {
        if (acc.data[i].excl && !acc.data[i].ac.valid)
            deny_restrict(target, acc.data[i].ac.span);
        for (uint32_t j = i + 1; j < acc.len; j++) {
            if (!acc.data[i].excl && !acc.data[j].excl) continue;
            if (!overlaps(&acc.data[i].ac, &acc.data[j].ac)) continue;

            Str   name = path_text(o, &acc.data[i].ac);
            Diag *dg = err(o, 401, acc.data[j].ac.span, "overlapping exclusive borrows of `%.*s`",
                           (int)name.len, name.ptr);
            if (dg) {
                diag_label(dg, acc.data[i].ac.span,
                           acc.data[i].excl ? "first exclusive borrow here" : "borrowed here");
                diag_label(dg, acc.data[j].ac.span,
                           acc.data[j].excl ? "second exclusive borrow here" : "borrowed again here");
                diag_note(dg, "overlapping local access paths cannot be borrowed "
                              "exclusively in the same call");
                diag_help(dg, "copy one side into a local first");
            }
        }
    }
}

static void check_inout_arg(O *o, Access ac, Span at, Conv conv) {
    if (!ac.valid) return;
    Local *l = ac.root;

    if (l->is_param && l->conv == CONV_LET) {
        Diag *dg = err(o, 407, at,
                       "cannot borrow `%.*s` exclusively: it is a `let` parameter",
                       (int)l->name.len, l->name.ptr);
        if (dg) {
            diag_label(dg, l->span, "declared `let` here, which only permits reading");
            diag_help(dg, "declare the parameter `inout` to allow mutation");
        }
        return;
    }
    if (!l->is_param && !l->is_mut && l->state == OS_INIT) {
        Diag *dg = err(o, 407, at, "cannot borrow immutable `%.*s` as `inout`",
                       (int)l->name.len, l->name.ptr);
        if (dg) {
            diag_label(dg, l->span, "declared with `let` here");
            diag_help(dg, "declare it with `var` instead");
        }
        return;
    }
    if (ac.nfields != 0 || ac.has_index) return;

    /* The two conventions differ exactly here, and conflating them was a hole
     * you could read uninitialized memory through.
     *
     * `set` promises the callee assigns before returning — BE0404 enforces
     * that on the callee side — so passing an uninitialized binding is the
     * normal way to use it, and it comes back initialized.
     *
     * `inout` promises nothing of the sort: the callee may read first. So an
     * uninitialized argument is a read before initialization, and saying so
     * here is the only place it can be caught. */
    if (conv == CONV_SET) {
        /* Initialization happens after every argument has been evaluated. */
        return;
    }

    if (l->state == OS_UNINIT) {
        Diag *dg = err(o, 405, at, "`%.*s` is passed `inout` before it is initialized",
                       (int)l->name.len, l->name.ptr);
        if (dg) {
            diag_label(dg, l->span, "declared here without a value");
            diag_label(dg, at, "borrowed exclusively here, and the callee may read it");
            diag_note(dg, "`inout` lends an existing value; only `set` promises the "
                          "callee will assign one");
            diag_help(dg, "give it a value first, or declare the parameter `set`");
        }
        l->state = OS_INIT; /* reported once; do not cascade */
    } else if (l->state == OS_MOVED) {
        Diag *dg = err(o, 403, at, "use of `%.*s` after it was moved",
                       (int)l->name.len, l->name.ptr);
        if (dg) {
            diag_label(dg, l->moved_at, "moved here");
            diag_label(dg, at, "borrowed exclusively here after the move");
        }
        l->state = OS_INIT;
    }
}

/* Implicit receivers and written arguments have the same source-order access
 * contract. A place selection is walked once; set's initialization is delayed
 * until the call, after every later explicit or expanded default argument. */
static void walk_call_argument(O *o, Expr *value, Conv conv, Span at) {
    if (conv == CONV_SINK) {
        do_move(o, value);
    } else if (conv == CONV_INOUT || conv == CONV_SET) {
        Access ac = path_of(value);
        if (ac.valid) {
            walk_place(o, value);
            check_inout_arg(o, ac, at, conv);
            if (ac.nfields || ac.has_index) check_read(o, value);
        } else {
            walk_expr(o, value);
        }
    } else {
        walk_expr(o, value);
    }
}

static void finish_call_argument(Expr *value, Conv conv) {
    Access ac = path_of(value);
    if (conv == CONV_SET && ac.valid && !ac.nfields && !ac.has_index)
        ac.root->state = OS_INIT;
}

static void walk_expr(O *o, Expr *e) {
    if (!e) return;

    switch (e->kind) {
        case EX_PATH:
        case EX_SELF: check_read(o, e); break;

        case EX_FIELD: walk_expr(o, e->field.base); break;

        case EX_INDEX:
            walk_expr(o, e->index.base);
            walk_expr(o, e->index.index);
            break;

        case EX_UNARY: walk_expr(o, e->unary.operand); break;

        case EX_BINARY: {
            walk_expr(o, e->binary.lhs);
            uint8_t *before = NULL;
            if (e->binary.op == TK_ANDAND || e->binary.op == TK_OROR)
                before = snapshot(o);
            walk_expr(o, e->binary.rhs);
            if (before) {
                if (o->unreachable) restore(o, before);
                else merge_into(o, before);
                o->unreachable = false;
            }
            break;
        }

        case EX_CALL: {
            Expr *callee = e->call.callee;
            Item *target = (e->res_kind == RES_FN) ? (Item *)e->res : NULL;
            bool  has_self = target && target->kind == IT_FN && target->fn.params.len > 0 &&
                            target->fn.params.data[0].is_self;

            if (callee && callee->kind == EX_FIELD) {
                bool mutator = e->res_kind == RES_INTRINSIC &&
                    (e->intrinsic == INTR_LIST_PUSH || e->intrinsic == INTR_LIST_SET ||
                     e->intrinsic == INTR_LIST_CLEAR);
                Conv conv = has_self ? target->fn.params.data[0].conv :
                            mutator ? CONV_INOUT : CONV_LET;
                walk_call_argument(o, callee->field.base, conv, callee->field.base->span);
            }

            for (uint32_t i = 0; i < e->call.args.len; i++) {
                Arg ar = e->call.args.data[i];
                walk_call_argument(o, ar.value, ar.conv, ar.span);
            }
            check_call_exclusivity(o, e);
            if (has_self && callee && callee->kind == EX_FIELD)
                finish_call_argument(callee->field.base, target->fn.params.data[0].conv);
            for (uint32_t i = 0; i < e->call.args.len; i++) {
                Arg ar = e->call.args.data[i];
                finish_call_argument(ar.value, ar.conv);
            }
            break;
        }

        case EX_CAST: walk_expr(o, e->cast.value); break;

        case EX_STRUCT_LIT:
            for (uint32_t i = 0; i < e->struct_lit.fields.len; i++)
                walk_expr(o, e->struct_lit.fields.data[i].value);
            break;

        case EX_ARRAY_LIT:
            for (uint32_t i = 0; i < e->array_lit.elems.len; i++)
                walk_expr(o, e->array_lit.elems.data[i]);
            break;

        case EX_IF: {
            walk_expr(o, e->if_expr.cond);
            uint8_t *before      = snapshot(o);
            bool     save_unreach = o->unreachable;

            walk_expr(o, e->if_expr.then_blk);
            uint8_t *after_then = snapshot(o);
            bool     then_dead  = o->unreachable;

            restore(o, before);
            o->unreachable = save_unreach;
            if (e->if_expr.else_blk) walk_expr(o, e->if_expr.else_blk);
            bool else_dead = o->unreachable;

            /* A branch that returns contributes nothing to the merged state. */
            if (then_dead && !else_dead) {
                /* keep the else-branch state as-is */
            } else if (else_dead && !then_dead) {
                restore(o, after_then);
            } else {
                merge_into(o, after_then);
            }
            o->unreachable =
                save_unreach || (then_dead && else_dead && e->if_expr.else_blk != NULL);
            break;
        }

        case EX_BLOCK: walk_block(o, e); break;
        case EX_TRY:
            walk_expr(o, e->try_expr.inner);
            check_set_exit(o, e->span); /* failure propagates out of this function */
            break;

        /* A handler and a fallback run only when the value is an error or
         * empty, so anything they initialize is initialized on one path out
         * of two. Walking them as though they always ran credited
         * `f() catch |e| { x = 1 }` with initializing `x` on the success path
         * too. Merging with the state from before is what makes the "maybe"
         * visible; the walk still happens, so reads inside are still checked. */
        case EX_CATCH: {
            walk_expr(o, e->catch_expr.value);
            uint8_t *before = snapshot(o);
            if (!str_empty(e->catch_expr.binding))
                mark_init(o, e->span, e->catch_expr.binding);
            walk_expr(o, e->catch_expr.handler);
            if (o->unreachable) restore(o, before);
            else merge_into(o, before);
            o->unreachable = false; /* the success path continues */
            break;
        }

        case EX_ORELSE: {
            walk_expr(o, e->orelse_expr.value);
            uint8_t *before = snapshot(o);
            walk_expr(o, e->orelse_expr.fallback);
            if (o->unreachable) restore(o, before);
            else merge_into(o, before);
            o->unreachable = false;
            break;
        }

        case EX_UNSAFE: walk_expr(o, e->unsafe_expr.body); break;

        case EX_RANGE:
            walk_expr(o, e->range.lo);
            walk_expr(o, e->range.hi);
            break;

        default: break;
    }
}

static void walk_assign(O *o, Stmt *s) {
    walk_place(o, s->assign.target);

    /* `x += 1` reads `x` before it writes it, so it cannot be the thing that
     * initializes `x`. Checking the read first is what makes that true; the
     * write below then finds the binding already reported and moves on. */
    if (s->assign.op != TK_ASSIGN) check_read(o, s->assign.target);
    walk_expr(o, s->assign.value);

    Access ac = path_of(s->assign.target);
    if (!ac.valid) {
        walk_expr(o, s->assign.target);
        return;
    }
    Local *l = ac.root;

    /* Mutating through a read-only borrow is never allowed. */
    if (l->is_param && l->conv == CONV_LET) {
        Str   name = path_text(o, &ac);
        Diag *dg = err(o, 407, s->span, "cannot assign to `%.*s` through a `let` borrow",
                       (int)name.len, name.ptr);
        if (dg) {
            diag_label(dg, l->span, "`%.*s` is declared `let`, which only permits reading",
                       (int)l->name.len, l->name.ptr);
            diag_help(dg, "declare the parameter `inout` to allow mutation");
        }
        return;
    }

    bool whole = (ac.nfields == 0 && !ac.has_index);

    if (whole) {
        /* Assigning to an uninitialized binding initializes it, even a `let`. */
        if (l->state == OS_UNINIT || l->state == OS_MOVED) {
            l->state = OS_INIT;
            return;
        }
        if (!l->is_mut && !l->is_param) {
            Diag *dg = err(o, 402, s->span, "cannot assign twice to immutable `%.*s`",
                           (int)l->name.len, l->name.ptr);
            if (dg) {
                diag_label(dg, l->span, "first bound here with `let`");
                diag_label(dg, s->span, "assigned again here");
                diag_help(dg, "declare it with `var` if it needs to change");
            }
        }
        return;
    }

    if (!l->is_mut && !l->is_param) {
        Str   name = path_text(o, &ac);
        Diag *dg = err(o, 402, s->span, "cannot assign to `%.*s`: `%.*s` is immutable",
                       (int)name.len, name.ptr, (int)l->name.len, l->name.ptr);
        if (dg) {
            diag_label(dg, l->span, "declared with `let` here");
            diag_help(dg, "declare it with `var` if its fields need to change");
        }
        return;
    }
    check_read(o, s->assign.target);
}

/* A loop has separate fallthrough, continue and break edges. Each pass
 * rechecks the condition at the current head state; a body return never
 * makes the zero-iteration path unreachable. The finite state lattice
 * converges without a guessed iteration cutoff. */
static void walk_loop(O *o, Expr *cond, Expr *body) {
    uint8_t *entry = snapshot(o);
    bool saved_quiet = o->quiet;
    LoopFlow *parent = o->loop;
    o->quiet = true;
    for (;;) {
        uint8_t *head = snapshot(o);
        LoopFlow flow = {.parent = parent};
        o->loop = &flow;
        o->unreachable = false;
        if (cond) walk_expr(o, cond);
        walk_expr(o, body);
        if (!o->unreachable) record_exit(o, &flow.continues);
        restore(o, entry);
        if (flow.continues) merge_into(o, flow.continues);
        if (states_equal(o, head)) break;
    }
    o->quiet = saved_quiet;
    LoopFlow flow = {.parent = parent};
    o->loop = &flow;
    o->unreachable = false;
    if (cond) walk_expr(o, cond);
    uint8_t *condition_exit = snapshot(o);
    walk_expr(o, body);
    restore(o, condition_exit);
    if (flow.breaks) merge_into(o, flow.breaks);
    o->unreachable = false;
    o->loop = parent;
}

static void walk_stmt(O *o, Stmt *s) {
    if (!s) return;

    switch (s->kind) {
        case ST_LET:
            /* The initializer is evaluated before the binding exists, so
             * `let x = x` refers to an outer `x` rather than to itself. */
            if (s->let.init) walk_expr(o, s->let.init);
            for (uint32_t i = 0; i < o->nlocals; i++) {
                Local *l = o->locals[i];
                if (l->span.offset == s->span.offset && str_eq(l->name, s->let.name)) {
                    /* A container declared without a value starts empty rather
                     * than uninitialized; there is no other useful state for
                     * it, and it saves an initializer that says nothing. */
                    bool defaulted = l->type && (l->type->kind == TY_LIST ||
                                                 l->type->kind == TY_MAP);
                    l->state = (s->let.init || defaulted) ? OS_INIT : OS_UNINIT;
                    break;
                }
            }
            break;

        case ST_EXPR: walk_expr(o, s->expr); break;
        case ST_ASSIGN: walk_assign(o, s); break;

        case ST_WHILE:
            walk_loop(o, s->while_st.cond, s->while_st.body);
            break;

        case ST_FOR:
            walk_expr(o, s->for_st.iter);
            mark_init(o, s->span, s->for_st.var); /* the loop binds it */
            walk_loop(o, NULL, s->for_st.body);
            break;

        case ST_RETURN:
            if (s->expr) walk_expr(o, s->expr);
            check_set_exit(o, s->span);
            o->unreachable = true;
            break;

        case ST_BREAK:
        case ST_CONTINUE:
            if (o->loop) {
                record_exit(o, s->kind == ST_BREAK ? &o->loop->breaks : &o->loop->continues);
                o->unreachable = true;
            }
            break;
        case ST_DEFER: walk_expr(o, s->expr); break;
        default: break;
    }
}

static void walk_block(O *o, Expr *b) {
    if (!b || b->kind != EX_BLOCK) return;
    for (uint32_t i = 0; i < b->block.stmts.len && !o->unreachable; i++)
        walk_stmt(o, b->block.stmts.data[i]);
}

static void own_fn(O *o, Item *it, Expr *body) {
    o->fn          = it;
    o->locals      = (Local **)it->locals;
    o->nlocals     = it->nlocals;
    o->quiet       = false;
    o->unreachable = false;

    for (uint32_t i = 0; i < o->nlocals; i++) {
        Local *l    = o->locals[i];
        l->state    = OS_UNINIT;
        l->moved_at = SPAN_NONE;
        if (l->is_param) l->state = (l->conv == CONV_SET) ? OS_UNINIT : OS_INIT;
    }

    walk_block(o, body);

    /* Falling off the end is a return path too. */
    if (!o->unreachable) {
        for (uint32_t i = 0; i < o->nlocals; i++) {
            Local *l = o->locals[i];
            if (l->is_param && l->conv == CONV_SET && l->state != OS_INIT) {
                Diag *dg = err(o, 404, it->span,
                               "`set` parameter `%.*s` is not initialized on every path",
                               (int)l->name.len, l->name.ptr);
                if (dg)
                    diag_label(dg, l->span,
                               "declared `set` here, so the callee must assign it");
            }
        }
    }
}

bool ownership_check(DiagBag *d, Program *p) {
    uint32_t before = diag_errors(d);
    if (!access_check_destinations(d,p)) return false;

    O o = {0};
    o.a = p->a;
    o.d = d;
    o.p = p;

    for (uint32_t m = 0; m < p->modules.len; m++) {
        Module *mod = p->modules.data[m];
        for (uint32_t i = 0; i < mod->items.len; i++) {
            Item *it = mod->items.data[i];
            if (it->kind == IT_FN) it->restrict_admitted = true;
        }
    }

    for (uint32_t m = 0; m < p->modules.len; m++) {
        Module *mod = p->modules.data[m];
        for (uint32_t i = 0; i < mod->items.len; i++) {
            Item *it = mod->items.data[i];
            if (it->kind == IT_FN && it->fn.generics.len == 0 && it->fn.body)
                own_fn(&o, it, it->fn.body);
            else if (it->kind == IT_TEST && it->test.body)
                own_fn(&o, it, it->test.body);
        }
    }
    return diag_errors(d) == before;
}
