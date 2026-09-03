/* check.c — scopes, statements, functions, and the checking entry point. */
#include "check.h"

void chk_push_scope(C *c) { vec_push(c->a, c->scopes, map_new(c->a)); }

void chk_pop_scope(C *c) {
    if (c->scopes.len) c->scopes.len--;
}

Local *chk_lookup(C *c, Str name) {
    for (int32_t i = (int32_t)c->scopes.len - 1; i >= 0; i--) {
        Local *l = (Local *)map_get(c->scopes.data[i], name);
        if (l) return l;
    }
    return NULL;
}

Local *chk_declare(C *c, Str name, Type *ty, bool is_mut, bool is_param, Conv conv,
                   Span sp) {
    Local *l    = ARENA_NEW(c->a, Local);
    l->name     = name;
    l->type     = ty;
    l->is_mut   = is_mut;
    l->is_param = is_param;
    l->conv     = conv;
    l->span     = sp;
    l->id       = c->next_local_id++;
    if (c->scopes.len) map_put(c->scopes.data[c->scopes.len - 1], name, l);
    vec_push(c->a, c->locals, l);
    return l;
}

/* ---- flow: does this always return? ------------------------------------ */

static bool node_returns(Expr *e);

static bool stmt_returns(Stmt *s) {
    if (!s) return false;
    switch (s->kind) {
        case ST_RETURN: return true;
        case ST_EXPR: return node_returns(s->expr);
        default: return false;
    }
}

static bool node_returns(Expr *e) {
    if (!e) return false;
    if (e->kind == EX_BLOCK) {
        for (uint32_t i = 0; i < e->block.stmts.len; i++)
            if (stmt_returns(e->block.stmts.data[i])) return true;
        return false;
    }
    if (e->kind == EX_IF) {
        return e->if_expr.else_blk && node_returns(e->if_expr.then_blk) &&
               node_returns(e->if_expr.else_blk);
    }
    return false;
}

/* ---- lvalues ----------------------------------------------------------- */

static bool is_lvalue(const Expr *e) {
    if (!e) return false;
    switch (e->kind) {
        case EX_PATH: return e->res_kind == RES_LOCAL;
        case EX_SELF:
        case EX_FIELD:
        case EX_INDEX: return true;
        default: return false;
    }
}

/* ---- statements -------------------------------------------------------- */

static void chk_stmt(C *c, Stmt *s) {
    if (!s) return;

    switch (s->kind) {
        case ST_LET: {
            Type *declared = s->let.type ? resolve_type_expr(c->p, c->d, s->let.type) : NULL;
            Type *init     = NULL;
            if (s->let.init) {
                init = chk(c, s->let.init, declared);
                if (declared)
                    chk_expect_type(c, s->let.init->span, declared, init,
                                    "in this initializer");
            }
            Type *ty = declared ? declared : init;
            if (!ty) {
                Diag *dg = diag_error(c->d, 303, s->span,
                                      "`%.*s` needs either a type or an initializer",
                                      (int)s->let.name.len, s->let.name.ptr);
                diag_help(dg, "write `let %.*s: T = ...`", (int)s->let.name.len,
                          s->let.name.ptr);
                ty = chk_err(c);
            }
            if (chk_lookup(c, s->let.name)) {
                /* Shadowing in an inner scope is fine; in the same scope it is
                 * almost always a mistake. */
                Local *prev = (Local *)map_get(c->scopes.data[c->scopes.len - 1],
                                               s->let.name);
                if (prev) {
                    Diag *dg = diag_error(c->d, 308, s->span,
                                          "`%.*s` is already declared in this scope",
                                          (int)s->let.name.len, s->let.name.ptr);
                    diag_label(dg, prev->span, "first declared here");
                    diag_label(dg, s->span, "declared again here");
                }
            }
            chk_declare(c, s->let.name, ty, s->let.is_var, false, CONV_LET, s->span);
            break;
        }

        case ST_EXPR: chk(c, s->expr, NULL); break;

        case ST_ASSIGN: {
            Type *tt = chk(c, s->assign.target, NULL);
            if (!is_lvalue(s->assign.target)) {
                Diag *dg = diag_error(c->d, 303, s->assign.target->span,
                                      "this expression cannot be assigned to");
                diag_help(dg, "only a variable, field or element can appear on the left");
            }
            Type *vt = chk(c, s->assign.value, tt);
            chk_expect_type(c, s->assign.value->span, tt, vt, "in this assignment");
            if (s->assign.op != TK_ASSIGN && !ty_is_error(tt)) {
                bool vecish = tt->kind == TY_VEC2 || tt->kind == TY_VEC3 ||
                              tt->kind == TY_VEC4;
                if (!ty_is_numeric(tt) && !vecish)
                    diag_error(c->d, 303, s->span,
                               "`%s` requires a number, found `%.*s`",
                               tok_name(s->assign.op), (int)ty_name(c->a, tt).len,
                               ty_name(c->a, tt).ptr);
                if (s->assign.op == TK_PERCENTEQ && !ty_is_integer(tt))
                    diag_error(c->d, 303, s->span, "`%%=` requires an integer");
            }
            break;
        }

        case ST_WHILE: {
            Type *bt = ty_prim(c->tc, TY_BOOL);
            Type *ct = chk(c, s->while_st.cond, bt);
            if (!ty_is_error(ct) && !ty_eq(ct, bt)) {
                Diag *dg = diag_error(c->d, 311, s->while_st.cond->span,
                                      "a `while` condition must be `bool`, found `%.*s`",
                                      (int)ty_name(c->a, ct).len, ty_name(c->a, ct).ptr);
                if (ty_is_numeric(ct)) diag_help(dg, "compare explicitly, e.g. `x != 0`");
            }
            c->loop_depth++;
            chk(c, s->while_st.body, NULL);
            c->loop_depth--;
            break;
        }

        case ST_FOR: {
            Type *it = chk(c, s->for_st.iter, NULL);
            Type *elem;
            if (s->for_st.iter && s->for_st.iter->kind == EX_RANGE) {
                elem = it;
            } else if (it && (it->kind == TY_ARRAY || it->kind == TY_LIST)) {
                elem = it->elem;
            } else if (ty_is_error(it)) {
                elem = chk_err(c);
            } else {
                Diag *dg = diag_error(c->d, 303, s->for_st.iter->span,
                                      "`%.*s` cannot be iterated",
                                      (int)ty_name(c->a, it).len, ty_name(c->a, it).ptr);
                diag_help(dg, "iterate a range like `0..n`, an array, or a `List<T>`");
                elem = chk_err(c);
            }
            chk_push_scope(c);
            chk_declare(c, s->for_st.var, elem, false, false, CONV_LET, s->span);
            c->loop_depth++;
            chk(c, s->for_st.body, NULL);
            c->loop_depth--;
            chk_pop_scope(c);
            break;
        }

        case ST_RETURN: {
            Type *want = c->ret_ty ? c->ret_ty : ty_prim(c->tc, TY_VOID);
            if (!s->expr) {
                if (want->kind != TY_VOID && want->kind != TY_ERRUNION)
                    diag_error(c->d, 303, s->span,
                               "this function returns `%.*s`, so `return` needs a value",
                               (int)ty_name(c->a, want).len, ty_name(c->a, want).ptr);
                break;
            }
            /* In a function returning `!T`, a plain value is the ok case. */
            Type *target = want;
            if (want->kind == TY_ERRUNION && s->expr->kind != EX_ERROR_LIT)
                target = want->elem;
            Type *got = chk(c, s->expr, target);
            if (s->expr->kind != EX_ERROR_LIT)
                chk_expect_type(c, s->expr->span, target, got, "in this return");
            break;
        }

        case ST_BREAK:
        case ST_CONTINUE:
            if (c->loop_depth == 0) {
                const char *w = s->kind == ST_BREAK ? "break" : "continue";
                diag_error(c->d, 316, s->span, "`%s` outside of a loop", w);
            }
            break;

        case ST_DEFER: chk(c, s->expr, NULL); break;
        default: break;
    }
}

void chk_block(C *c, Expr *b) {
    if (!b || b->kind != EX_BLOCK) return;
    chk_push_scope(c);
    bool warned_unreachable = false;
    bool seen_return        = false;

    for (uint32_t i = 0; i < b->block.stmts.len; i++) {
        Stmt *s = b->block.stmts.data[i];
        if (seen_return && !warned_unreachable) {
            diag_warn(c->d, 318, s->span, "unreachable code");
            warned_unreachable = true;
        }
        chk_stmt(c, s);
        if (stmt_returns(s)) seen_return = true;
    }
    chk_pop_scope(c);
}

/* ---- items ------------------------------------------------------------- */

static void check_fn(C *c, Item *it) {
    c->fn            = it;
    c->ret_ty        = it->rtype;
    c->loop_depth    = 0;
    c->next_local_id = 0;
    c->locals.len    = 0;
    c->scopes.len    = 0;

    chk_push_scope(c);
    for (uint32_t i = 0; i < it->fn.params.len; i++) {
        Param *pm = &it->fn.params.data[i];
        bool   mut = (pm->conv == CONV_INOUT || pm->conv == CONV_SINK || pm->conv == CONV_SET);
        chk_declare(c, pm->name, pm->rtype, mut, true, pm->conv, pm->span);
        if (pm->deflt) {
            Type *dt = chk(c, pm->deflt, pm->rtype);
            chk_expect_type(c, pm->deflt->span, pm->rtype, dt, "in this default value");
        }
    }

    chk_block(c, it->fn.body);

    Type *ret = it->rtype;
    if (ret && ret->kind != TY_VOID && it->fn.body && !node_returns(it->fn.body)) {
        Diag *dg = diag_error(c->d, 310, it->span,
                              "not every path returns a value from `%.*s`",
                              (int)it->name.len, it->name.ptr);
        diag_label(dg, it->fn.ret ? it->fn.ret->span : it->span,
                   "this function must return `%.*s`", (int)ty_name(c->a, ret).len,
                   ty_name(c->a, ret).ptr);
        diag_help(dg, "add a `return` at the end, or give the `if` an `else` branch");
    }

    /* Hand the function's bindings to the ownership pass. */
    it->nlocals = c->locals.len;
    if (c->locals.len) {
        Local **arr = ARENA_ARRAY(c->a, Local *, c->locals.len);
        for (uint32_t i = 0; i < c->locals.len; i++) arr[i] = c->locals.data[i];
        it->locals = arr;
    }

    chk_pop_scope(c);
    c->fn = NULL;
}

bool check_program(DiagBag *d, Program *p) {
    uint32_t before = diag_errors(d);

    C c   = {0};
    c.a   = p->a;
    c.d   = d;
    c.p   = p;
    c.tc  = p->types;

    for (uint32_t m = 0; m < p->modules.len; m++) {
        Module *mod = p->modules.data[m];
        c.mod       = mod;

        for (uint32_t i = 0; i < mod->items.len; i++) {
            Item *it = mod->items.data[i];
            switch (it->kind) {
                case IT_FN:
                    if (it->fn.generics.len == 0) check_fn(&c, it);
                    break;
                case IT_TEST: {
                    c.fn            = NULL;
                    c.ret_ty        = ty_prim(c.tc, TY_VOID);
                    c.loop_depth    = 0;
                    c.next_local_id = 0;
                    c.locals.len    = 0;
                    c.scopes.len    = 0;
                    chk_push_scope(&c);
                    chk_block(&c, it->test.body);
                    it->nlocals = c.locals.len;
                    if (c.locals.len) {
                        Local **arr = ARENA_ARRAY(c.a, Local *, c.locals.len);
                        for (uint32_t k = 0; k < c.locals.len; k++) arr[k] = c.locals.data[k];
                        it->locals = arr;
                    }
                    chk_pop_scope(&c);
                    break;
                }
                case IT_CONST: {
                    c.scopes.len = 0;
                    chk_push_scope(&c);
                    Type *vt = chk(&c, it->konst.value, it->rtype);
                    if (it->rtype)
                        chk_expect_type(&c, it->konst.value->span, it->rtype, vt,
                                        "in this constant");
                    else it->rtype = vt;
                    chk_pop_scope(&c);
                    break;
                }
                case IT_STRUCT: {
                    /* Field defaults are checked against their declared type. */
                    c.scopes.len = 0;
                    chk_push_scope(&c);
                    for (uint32_t f = 0; f < it->strukt.fields.len; f++) {
                        Field *fl = &it->strukt.fields.data[f];
                        if (!fl->deflt) continue;
                        Type *dt = chk(&c, fl->deflt, fl->rtype);
                        chk_expect_type(&c, fl->deflt->span, fl->rtype, dt,
                                        "in this field default");
                    }
                    chk_pop_scope(&c);
                    break;
                }
                default: break;
            }
        }
    }

    return diag_errors(d) == before;
}
