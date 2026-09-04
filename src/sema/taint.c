#include "taint.h"

#include "intrinsic.h"

bool item_has_attr(const Item *it, const char *name) {
    for (uint32_t i = 0; i < it->attrs.len; i++)
        if (str_eq_c(it->attrs.data[i].name, name)) return true;
    return false;
}

Str item_attr_arg(const Item *it, const char *name) {
    for (uint32_t i = 0; i < it->attrs.len; i++)
        if (str_eq_c(it->attrs.data[i].name, name)) return it->attrs.data[i].arg;
    return STR_EMPTY;
}

typedef struct {
    Arena   *a;
    DiagBag *d;
    Program *p;
    Item    *fn;
    bool     forbid_unsafe;
    bool     in_constant_time;
    bool     in_server_only;
} T;

/* ---- taint of an expression -------------------------------------------- */

static uint8_t taint_of(T *t, Expr *e);

/* `clamp`, `min` and `max` bound a value, which is exactly what makes an
 * untrusted index safe to use. They therefore launder untrusted taint — but
 * not secret taint, since bounding a secret still reveals it through timing. */
static bool intrinsic_bounds(Intrinsic id) {
    return id == INTR_CLAMP || id == INTR_MIN || id == INTR_MAX;
}

static uint8_t taint_of_call(T *t, Expr *e) {
    uint8_t acc = TAINT_NONE;
    for (uint32_t i = 0; i < e->call.args.len; i++)
        acc |= taint_of(t, e->call.args.data[i].value);

    if (e->res_kind == RES_INTRINSIC) {
        if (intrinsic_bounds((Intrinsic)e->intrinsic)) acc &= (uint8_t)~TAINT_UNTRUSTED;
        return acc;
    }

    Item *fn = (e->res_kind == RES_FN) ? (Item *)e->res : NULL;
    if (!fn) return acc;

    /* A validator's whole job is to make its result trustworthy. */
    if (item_has_attr(fn, "validator")) acc &= (uint8_t)~TAINT_UNTRUSTED;

    if (item_has_attr(fn, "untrusted")) acc |= TAINT_UNTRUSTED;
    if (item_has_attr(fn, "secret")) acc |= TAINT_SECRET;

    /* A constant-time function may only call other constant-time functions;
     * otherwise the guarantee stops at the first ordinary callee. */
    if (t->in_constant_time && !item_has_attr(fn, "constant_time") &&
        e->res_kind != RES_INTRINSIC) {
        Diag *dg = diag_error(t->d, 607, e->span,
                              "`@constant_time` function calls `%.*s`, which is not "
                              "declared constant-time",
                              (int)fn->name.len, fn->name.ptr);
        diag_label(dg, e->span, "called here");
        diag_note(dg, "the guarantee has to hold through every callee, or it does not "
                      "hold at all");
    }

    /* Server-authoritative code must not be reachable from client context. */
    if (item_has_attr(fn, "server_only") && !t->in_server_only) {
        Diag *dg = diag_error(t->d, 705, e->span,
                              "`%.*s` is `@server_only` but is called from client context",
                              (int)fn->name.len, fn->name.ptr);
        diag_label(dg, e->span, "called here, from a caller that is not `@server_only`");
        diag_help(dg, "mark the caller `@server_only` too, or route the call through an "
                      "authority check");
    }
    return acc;
}

static uint8_t taint_of(T *t, Expr *e) {
    if (!e) return TAINT_NONE;
    switch (e->kind) {
        case EX_PATH:
        case EX_SELF: return (e->res_kind == RES_LOCAL) ? ((Local *)e->res)->taint : 0;
        case EX_FIELD: return taint_of(t, e->field.base);
        case EX_INDEX: return (uint8_t)(taint_of(t, e->index.base) |
                                        taint_of(t, e->index.index));
        case EX_UNARY: return taint_of(t, e->unary.operand);
        case EX_BINARY:
            return (uint8_t)(taint_of(t, e->binary.lhs) | taint_of(t, e->binary.rhs));
        case EX_CAST: return taint_of(t, e->cast.value);
        case EX_CALL: return taint_of_call(t, e);
        case EX_TRY: return taint_of(t, e->try_expr.inner);
        case EX_ORELSE:
            return (uint8_t)(taint_of(t, e->orelse_expr.value) |
                             taint_of(t, e->orelse_expr.fallback));
        case EX_STRUCT_LIT: {
            uint8_t acc = 0;
            for (uint32_t i = 0; i < e->struct_lit.fields.len; i++)
                acc |= taint_of(t, e->struct_lit.fields.data[i].value);
            return acc;
        }
        case EX_ARRAY_LIT: {
            uint8_t acc = 0;
            for (uint32_t i = 0; i < e->array_lit.elems.len; i++)
                acc |= taint_of(t, e->array_lit.elems.data[i]);
            return acc;
        }
        default: return TAINT_NONE;
    }
}

/* ---- sinks -------------------------------------------------------------- */

static void check_index_sink(T *t, Expr *e) {
    uint8_t idx = taint_of(t, e->index.index);

    if (idx & TAINT_UNTRUSTED) {
        Diag *dg = diag_error(t->d, 601, e->index.index->span,
                              "an untrusted value is used as an index without being "
                              "bounded first");
        diag_label(dg, e->index.index->span, "this index is attacker-controlled");
        diag_note(dg, "a client controls this value; an out-of-range index is the "
                      "cheapest thing for it to send");
        diag_help(dg, "bound it with `clamp(i, 0, n - 1)`, or route it through a "
                      "`@validator` function");
    }
    if (idx & TAINT_SECRET) {
        Diag *dg = diag_error(t->d, 603, e->index.index->span,
                              "a secret value is used as a memory index");
        diag_note(dg, "the access pattern is observable through the cache, which leaks "
                      "the secret regardless of what the code does with it");
        diag_help(dg, "index by a public value, or read the whole table");
    }
}

static void check_branch_sink(T *t, Expr *cond, const char *what) {
    if (!cond) return;
    if (taint_of(t, cond) & TAINT_SECRET) {
        Diag *dg = diag_error(t->d, 602, cond->span,
                              "a secret value decides this `%s`", what);
        diag_note(dg, "branching on a secret makes its value observable through timing");
        diag_help(dg, "compute both sides and select without branching");
    }
}

/* ---- walk --------------------------------------------------------------- */

static void walk_expr(T *t, Expr *e);
static void walk_block(T *t, Expr *b);

static void walk_expr(T *t, Expr *e) {
    if (!e) return;
    switch (e->kind) {
        case EX_INDEX:
            check_index_sink(t, e);
            walk_expr(t, e->index.base);
            walk_expr(t, e->index.index);
            break;

        case EX_UNSAFE: {
            if (t->forbid_unsafe) {
                Diag *dg = diag_error(t->d, 605, e->span,
                                      "`@unsafe(%.*s)` is used in a package declaring "
                                      "`forbid_unsafe`",
                                      (int)e->unsafe_expr.capability.len,
                                      e->unsafe_expr.capability.ptr);
                diag_help(dg, "remove the block, or set `forbid_unsafe = false` in "
                              "beryl.toml and accept the audit surface");
            }
            walk_expr(t, e->unsafe_expr.body);
            break;
        }

        case EX_CALL:
            (void)taint_of_call(t, e); /* reports server_only and constant_time */
            for (uint32_t i = 0; i < e->call.args.len; i++)
                walk_expr(t, e->call.args.data[i].value);
            if (e->call.callee && e->call.callee->kind == EX_FIELD)
                walk_expr(t, e->call.callee->field.base);
            break;

        case EX_IF:
            check_branch_sink(t, e->if_expr.cond, "if");
            walk_expr(t, e->if_expr.cond);
            walk_expr(t, e->if_expr.then_blk);
            walk_expr(t, e->if_expr.else_blk);
            break;

        case EX_BINARY:
            walk_expr(t, e->binary.lhs);
            walk_expr(t, e->binary.rhs);
            break;
        case EX_UNARY: walk_expr(t, e->unary.operand); break;
        case EX_CAST: walk_expr(t, e->cast.value); break;
        case EX_FIELD: walk_expr(t, e->field.base); break;
        case EX_BLOCK: walk_block(t, e); break;
        case EX_TRY: walk_expr(t, e->try_expr.inner); break;
        case EX_ORELSE:
            walk_expr(t, e->orelse_expr.value);
            walk_expr(t, e->orelse_expr.fallback);
            break;
        case EX_CATCH:
            walk_expr(t, e->catch_expr.value);
            walk_expr(t, e->catch_expr.handler);
            break;
        case EX_STRUCT_LIT:
            for (uint32_t i = 0; i < e->struct_lit.fields.len; i++)
                walk_expr(t, e->struct_lit.fields.data[i].value);
            break;
        case EX_ARRAY_LIT:
            for (uint32_t i = 0; i < e->array_lit.elems.len; i++)
                walk_expr(t, e->array_lit.elems.data[i]);
            break;
        default: break;
    }
}

/* Finds the binding a `let`/`for` statement introduced. */
static Local *local_at(T *t, Span sp, Str name) {
    if (!t->fn) return NULL;
    for (uint32_t i = 0; i < t->fn->nlocals; i++) {
        Local *l = ((Local **)t->fn->locals)[i];
        if (l->span.offset == sp.offset && str_eq(l->name, name)) return l;
    }
    return NULL;
}

static void walk_stmt(T *t, Stmt *s) {
    if (!s) return;
    switch (s->kind) {
        case ST_LET: {
            walk_expr(t, s->let.init);
            Local *l = local_at(t, s->span, s->let.name);
            if (l) l->taint = s->let.init ? taint_of(t, s->let.init) : TAINT_NONE;
            break;
        }
        case ST_ASSIGN: {
            walk_expr(t, s->assign.value);
            walk_expr(t, s->assign.target);
            /* Taint accumulates: an assignment can add taint but a later merge
             * must not silently drop it. */
            if (s->assign.target && s->assign.target->kind == EX_PATH &&
                s->assign.target->res_kind == RES_LOCAL) {
                Local *l = (Local *)s->assign.target->res;
                l->taint |= taint_of(t, s->assign.value);
            }
            break;
        }
        case ST_WHILE:
            check_branch_sink(t, s->while_st.cond, "while");
            walk_expr(t, s->while_st.cond);
            walk_expr(t, s->while_st.body);
            break;
        case ST_FOR: {
            walk_expr(t, s->for_st.iter);
            Local *l = local_at(t, s->span, s->for_st.var);
            if (l) l->taint = taint_of(t, s->for_st.iter);
            walk_expr(t, s->for_st.body);
            break;
        }
        case ST_EXPR:
        case ST_RETURN:
        case ST_DEFER: walk_expr(t, s->expr); break;
        default: break;
    }
}

static void walk_block(T *t, Expr *b) {
    if (!b || b->kind != EX_BLOCK) return;
    for (uint32_t i = 0; i < b->block.stmts.len; i++) walk_stmt(t, b->block.stmts.data[i]);
}

static void check_fn(T *t, Item *it, Expr *body) {
    t->fn               = it;
    t->in_constant_time = item_has_attr(it, "constant_time");
    t->in_server_only   = item_has_attr(it, "server_only");

    uint8_t src = TAINT_NONE;
    if (item_has_attr(it, "untrusted")) src |= TAINT_UNTRUSTED;
    if (item_has_attr(it, "secret")) src |= TAINT_SECRET;

    for (uint32_t i = 0; i < it->nlocals; i++) {
        Local *l = ((Local **)it->locals)[i];
        l->taint = l->is_param ? src : TAINT_NONE;
    }

    /* `@unsafe` on the item itself, as opposed to on a block inside it. */
    if (t->forbid_unsafe && item_has_attr(it, "unsafe")) {
        Diag *dg = diag_error(t->d, 605, it->span,
                              "`@unsafe` is used in a package declaring `forbid_unsafe`");
        diag_help(dg, "remove it, or set `forbid_unsafe = false` in beryl.toml and "
                      "accept the audit surface");
    }

    walk_block(t, body);
    t->fn = NULL;
}

bool taint_check(DiagBag *d, Program *p, SecurityOpts o) {
    uint32_t before = diag_errors(d);

    T t = {0};
    t.a = p->a;
    t.d = d;
    t.p = p;
    t.forbid_unsafe = o.forbid_unsafe;

    for (uint32_t m = 0; m < p->modules.len; m++) {
        Module *mod = p->modules.data[m];
        for (uint32_t i = 0; i < mod->items.len; i++) {
            Item *it = mod->items.data[i];
            if (it->kind == IT_FN && !it->fn.generics.len && it->fn.body)
                check_fn(&t, it, it->fn.body);
            else if (it->kind == IT_TEST && it->test.body)
                check_fn(&t, it, it->test.body);
        }
    }
    return diag_errors(d) == before;
}
