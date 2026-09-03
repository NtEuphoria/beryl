#include "ownership.h"

typedef enum { OS_UNINIT = 0, OS_INIT, OS_MOVED } OwnState;

typedef struct {
    Arena   *a;
    DiagBag *d;
    Program *p;
    Item    *fn;
    Local  **locals;
    uint32_t nlocals;
    bool     quiet;       /* true while iterating a loop to a fixpoint */
    bool     unreachable; /* set after a `return` on this path */
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
 * receiver of a method taking `inout self` counts as one of them. */
static void check_call_exclusivity(O *o, Expr *call) {
    Access   acc[17];
    bool     excl[17];
    uint32_t n = 0;

    Expr *callee = call->call.callee;
    Item *target = (call->res_kind == RES_FN) ? (Item *)call->res : NULL;
    bool  has_self = target && target->kind == IT_FN && target->fn.params.len > 0 &&
                    target->fn.params.data[0].is_self;

    if (has_self && callee && callee->kind == EX_FIELD) {
        acc[n]  = path_of(callee->field.base);
        excl[n] = target->fn.params.data[0].conv == CONV_INOUT ||
                  target->fn.params.data[0].conv == CONV_SET;
        n++;
    }

    for (uint32_t i = 0; i < call->call.args.len && n < 17; i++) {
        acc[n] = path_of(call->call.args.data[i].value);
        /* Label the whole argument, `inout a`, not just the operand. */
        acc[n].span = call->call.args.data[i].span;
        excl[n]     = (call->call.args.data[i].conv == CONV_INOUT ||
                   call->call.args.data[i].conv == CONV_SET);
        n++;
    }

    for (uint32_t i = 0; i < n; i++) {
        for (uint32_t j = i + 1; j < n; j++) {
            if (!excl[i] && !excl[j]) continue;
            if (!overlaps(&acc[i], &acc[j])) continue;

            Str   name = path_text(o, &acc[i]);
            Diag *dg = err(o, 401, acc[j].span, "overlapping exclusive borrows of `%.*s`",
                           (int)name.len, name.ptr);
            if (dg) {
                diag_label(dg, acc[i].span,
                           excl[i] ? "first exclusive borrow here" : "borrowed here");
                diag_label(dg, acc[j].span,
                           excl[j] ? "second exclusive borrow here" : "borrowed again here");
                diag_note(dg, "`inout` guarantees non-aliasing, which is what licenses "
                              "`restrict` in the generated code");
                diag_help(dg, "copy one side into a local first");
            }
        }
    }
}

static void check_inout_arg(O *o, Access ac, Span at) {
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
    /* Writing through an `inout` counts as initializing the whole binding. */
    if (ac.nfields == 0 && !ac.has_index && l->state == OS_UNINIT) l->state = OS_INIT;
}

static void walk_expr(O *o, Expr *e) {
    if (!e) return;

    switch (e->kind) {
        case EX_PATH:
        case EX_SELF:
        case EX_FIELD: check_read(o, e); break;

        case EX_INDEX:
            check_read(o, e);
            walk_expr(o, e->index.index);
            break;

        case EX_UNARY: walk_expr(o, e->unary.operand); break;

        case EX_BINARY:
            walk_expr(o, e->binary.lhs);
            walk_expr(o, e->binary.rhs);
            break;

        case EX_CALL: {
            Expr *callee = e->call.callee;
            Item *target = (e->res_kind == RES_FN) ? (Item *)e->res : NULL;
            bool  has_self = target && target->kind == IT_FN && target->fn.params.len > 0 &&
                            target->fn.params.data[0].is_self;

            if (callee && callee->kind == EX_FIELD) {
                if (has_self && target->fn.params.data[0].conv == CONV_INOUT)
                    check_inout_arg(o, path_of(callee->field.base), callee->field.base->span);
                else walk_expr(o, callee->field.base);
            }

            for (uint32_t i = 0; i < e->call.args.len; i++) {
                Arg ar = e->call.args.data[i];
                if (ar.conv == CONV_SINK) {
                    do_move(o, ar.value);
                } else if (ar.conv == CONV_INOUT || ar.conv == CONV_SET) {
                    Access ac = path_of(ar.value);
                    if (ac.valid) {
                        check_inout_arg(o, ac, ar.span);
                        if (ar.conv == CONV_INOUT && (ac.nfields || ac.has_index))
                            check_read(o, ar.value);
                    } else {
                        walk_expr(o, ar.value);
                    }
                } else {
                    walk_expr(o, ar.value);
                }
            }
            check_call_exclusivity(o, e);
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
        case EX_TRY: walk_expr(o, e->try_expr.inner); break;

        case EX_CATCH:
            walk_expr(o, e->catch_expr.value);
            if (!str_empty(e->catch_expr.binding))
                mark_init(o, e->span, e->catch_expr.binding);
            walk_expr(o, e->catch_expr.handler);
            break;

        case EX_ORELSE:
            walk_expr(o, e->orelse_expr.value);
            walk_expr(o, e->orelse_expr.fallback);
            break;

        case EX_UNSAFE: walk_expr(o, e->unsafe_expr.body); break;

        case EX_RANGE:
            walk_expr(o, e->range.lo);
            walk_expr(o, e->range.hi);
            break;

        default: break;
    }
}

static void walk_assign(O *o, Stmt *s) {
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

/* Runs a loop body to a fixpoint quietly, then once more with diagnostics. */
static void walk_loop_body(O *o, Expr *body) {
    bool saved = o->quiet;
    o->quiet   = true;
    for (int pass = 0; pass < 8; pass++) {
        uint8_t *before = snapshot(o);
        walk_expr(o, body);
        merge_into(o, before);
        if (states_equal(o, before)) break;
    }
    o->quiet = saved;
    walk_expr(o, body);
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
                    l->state = s->let.init ? OS_INIT : OS_UNINIT;
                    break;
                }
            }
            break;

        case ST_EXPR: walk_expr(o, s->expr); break;
        case ST_ASSIGN: walk_assign(o, s); break;

        case ST_WHILE:
            walk_expr(o, s->while_st.cond);
            walk_loop_body(o, s->while_st.body);
            break;

        case ST_FOR:
            walk_expr(o, s->for_st.iter);
            mark_init(o, s->span, s->for_st.var); /* the loop binds it */
            walk_loop_body(o, s->for_st.body);
            break;

        case ST_RETURN:
            if (s->expr) walk_expr(o, s->expr);
            for (uint32_t i = 0; i < o->nlocals; i++) {
                Local *l = o->locals[i];
                if (l->is_param && l->conv == CONV_SET && l->state != OS_INIT) {
                    Diag *dg = err(o, 404, s->span,
                                   "`set` parameter `%.*s` is not initialized on this path",
                                   (int)l->name.len, l->name.ptr);
                    if (dg) {
                        diag_label(dg, l->span,
                                   "declared `set` here, so the callee must assign it");
                        diag_label(dg, s->span, "returns without assigning it");
                    }
                }
            }
            o->unreachable = true;
            break;

        case ST_DEFER: walk_expr(o, s->expr); break;
        default: break;
    }
}

static void walk_block(O *o, Expr *b) {
    if (!b || b->kind != EX_BLOCK) return;
    for (uint32_t i = 0; i < b->block.stmts.len; i++) walk_stmt(o, b->block.stmts.data[i]);
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

    O o = {0};
    o.a = p->a;
    o.d = d;
    o.p = p;

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
