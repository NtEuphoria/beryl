#include "defaults.h"
#include "constfold.h"

typedef struct {
    Program *p;
    DiagBag *d;
    uint32_t depth, steps;
    bool failed;
    Span site;
} D;

static bool allowed(Expr *e) {
    if (!e) return true;
    switch (e->kind) {
        case EX_INT: case EX_FLOAT: case EX_BOOL: case EX_CHAR: case EX_STR:
        case EX_ERROR_LIT: return true;
        case EX_PATH: return e->res_kind != RES_LOCAL;
        case EX_UNARY: return allowed(e->unary.operand);
        case EX_BINARY: return allowed(e->binary.lhs) && allowed(e->binary.rhs);
        case EX_FIELD: return allowed(e->field.base);
        case EX_INDEX: return allowed(e->index.base) && allowed(e->index.index);
        case EX_CAST: return allowed(e->cast.value);
        case EX_ORELSE: return allowed(e->orelse_expr.value) && allowed(e->orelse_expr.fallback);
        case EX_CALL:
            if (!allowed(e->call.callee)) return false;
            for (uint32_t i = 0; i < e->call.args.len; i++)
                if (e->call.args.data[i].conv != CONV_LET ||
                    !allowed(e->call.args.data[i].value)) return false;
            return true;
        case EX_STRUCT_LIT:
            for (uint32_t i = 0; i < e->struct_lit.fields.len; i++)
                if (!allowed(e->struct_lit.fields.data[i].value)) return false;
            return true;
        case EX_ARRAY_LIT:
            for (uint32_t i = 0; i < e->array_lit.elems.len; i++)
                if (!allowed(e->array_lit.elems.data[i])) return false;
            return true;
        default: return false; /* no formals, local bindings or nonlocal exits */
    }
}

static void visit(D *d, Expr *e);
static Expr *clone(D *d, Expr *e) {
    if (!e || d->failed) return NULL;
    if (++d->steps > 100000 || d->depth >= 64) {
        diag_error(d->d, 504, e->span, "default expansion exceeded its step or nesting limit");
        d->failed = true;
        return NULL;
    }
    d->depth++;
    Expr *x = ARENA_NEW(d->p->a, Expr);
    *x = *e; /* retain declaration bindings and checked types */
    x->has_expansion_site = true;
    x->expansion_site = d->site;
    switch (x->kind) {
        case EX_UNARY: x->unary.operand = clone(d, e->unary.operand); break;
        case EX_BINARY:
            x->binary.lhs = clone(d, e->binary.lhs);
            x->binary.rhs = clone(d, e->binary.rhs); break;
        case EX_FIELD: x->field.base = clone(d, e->field.base); break;
        case EX_INDEX:
            x->index.base = clone(d, e->index.base);
            x->index.index = clone(d, e->index.index); break;
        case EX_CAST: x->cast.value = clone(d, e->cast.value); break;
        case EX_ORELSE:
            x->orelse_expr.value = clone(d, e->orelse_expr.value);
            x->orelse_expr.fallback = clone(d, e->orelse_expr.fallback); break;
        case EX_CALL:
            x->call.callee = clone(d, e->call.callee);
            x->call.args = (ArgVec){0};
            for (uint32_t i = 0; i < e->call.args.len; i++) {
                Arg ar = e->call.args.data[i];
                ar.value = clone(d, ar.value);
                vec_push(d->p->a, x->call.args, ar);
            }
            break;
        case EX_STRUCT_LIT:
            x->struct_lit.fields = (FieldInitVec){0};
            for (uint32_t i = 0; i < e->struct_lit.fields.len; i++) {
                FieldInit f = e->struct_lit.fields.data[i];
                f.value = clone(d, f.value);
                vec_push(d->p->a, x->struct_lit.fields, f);
            }
            break;
        case EX_ARRAY_LIT:
            x->array_lit.elems = (ExprVec){0};
            for (uint32_t i = 0; i < e->array_lit.elems.len; i++)
                vec_push(d->p->a, x->array_lit.elems, clone(d, e->array_lit.elems.data[i]));
            break;
        default: break;
    }
    /* A template can itself omit another default, so expansion remains under
     * the same depth/work budget until the entire occurrence is complete. */
    visit(d, x);
    d->depth--;
    return x;
}

static void visit(D *d, Expr *e) {
    if (!e || d->failed) return;
    switch (e->kind) {
        case EX_CALL: {
            visit(d, e->call.callee);
            for (uint32_t i = 0; i < e->call.args.len; i++) visit(d, e->call.args.data[i].value);
            if (e->res_kind != RES_FN) break;
            Item *fn = (Item *)e->res;
            uint32_t first = fn->fn.params.len && fn->fn.params.data[0].is_self ? 1 : 0;
            for (uint32_t i = e->call.args.len + first; i < fn->fn.params.len; i++) {
                Param *pm = &fn->fn.params.data[i];
                if (!pm->deflt) continue; /* arity was checked already */
                Span previous = d->site;
                d->site = e->has_expansion_site ? e->expansion_site : e->span;
                Arg ar = {.value = clone(d, pm->deflt), .conv = pm->conv, .span = e->span};
                d->site = previous;
                vec_push(d->p->a, e->call.args, ar);
            }
            break;
        }
        case EX_STRUCT_LIT: {
            for (uint32_t i = 0; i < e->struct_lit.fields.len; i++)
                visit(d, e->struct_lit.fields.data[i].value);
            Item *it = e->type ? e->type->decl : NULL;
            if (!it) break;
            for (uint32_t i = 0; i < it->strukt.fields.len; i++) {
                Field *fl = &it->strukt.fields.data[i];
                bool given = false;
                for (uint32_t k = 0; k < e->struct_lit.fields.len; k++)
                    if (str_eq(fl->name, e->struct_lit.fields.data[k].name)) given = true;
                if (!given && fl->deflt) {
                    Span previous = d->site;
                    d->site = e->has_expansion_site ? e->expansion_site : e->span;
                    FieldInit f = {.name = fl->name, .value = clone(d, fl->deflt), .span = e->span};
                    d->site = previous;
                    vec_push(d->p->a, e->struct_lit.fields, f);
                }
            }
            break;
        }
        case EX_ARRAY_LIT:
            for (uint32_t i = 0; i < e->array_lit.elems.len; i++) visit(d, e->array_lit.elems.data[i]);
            break;
        case EX_UNARY: visit(d, e->unary.operand); break;
        case EX_BINARY: visit(d, e->binary.lhs); visit(d, e->binary.rhs); break;
        case EX_FIELD: visit(d, e->field.base); break;
        case EX_INDEX: visit(d, e->index.base); visit(d, e->index.index); break;
        case EX_CAST: visit(d, e->cast.value); break;
        case EX_IF:
            visit(d, e->if_expr.cond); visit(d, e->if_expr.then_blk); visit(d, e->if_expr.else_blk); break;
        case EX_BLOCK:
            for (uint32_t i = 0; i < e->block.stmts.len; i++) {
                Stmt *s = e->block.stmts.data[i];
                switch (s->kind) {
                    case ST_LET: visit(d, s->let.init); break;
                    case ST_EXPR: case ST_RETURN: case ST_DEFER: visit(d, s->expr); break;
                    case ST_ASSIGN: visit(d, s->assign.target); visit(d, s->assign.value); break;
                    case ST_WHILE: visit(d, s->while_st.cond); visit(d, s->while_st.body); break;
                    case ST_FOR: visit(d, s->for_st.iter); visit(d, s->for_st.body); break;
                    default: break;
                }
            }
            break;
        case EX_TRY: visit(d, e->try_expr.inner); break;
        case EX_CATCH: visit(d, e->catch_expr.value); visit(d, e->catch_expr.handler); break;
        case EX_ORELSE: visit(d, e->orelse_expr.value); visit(d, e->orelse_expr.fallback); break;
        case EX_UNSAFE: visit(d, e->unsafe_expr.body); break;
        case EX_RANGE: visit(d, e->range.lo); visit(d, e->range.hi); break;
        default: break;
    }
}

bool expand_defaults(DiagBag *diag, Program *p) {
    D d = {.p = p, .d = diag};
    uint32_t before = diag_errors(diag);
    for (uint32_t m = 0; m < p->modules.len; m++) {
        Module *mod = p->modules.data[m];
        for (uint32_t i = 0; i < mod->items.len; i++) {
            Item *it = mod->items.data[i];
            if (it->kind == IT_FN && !it->fn.generics.len) {
                for (uint32_t j = 0; j < it->fn.params.len; j++) {
                    Param *pm = &it->fn.params.data[j];
                    if (pm->deflt && (pm->conv != CONV_LET || !allowed(pm->deflt))) {
                        Diag *dg = diag_error(diag, 322, pm->span, "unsupported parameter default");
                        diag_help(dg, "use a let value built without parameter references, local bindings, or nonlocal exits; otherwise pass the argument explicitly");
                    }
                }
            } else if (it->kind == IT_STRUCT) {
                for (uint32_t j = 0; j < it->strukt.fields.len; j++) {
                    Field *fl = &it->strukt.fields.data[j];
                    if (fl->deflt) const_eval(p->a, diag, p, fl->deflt, true);
                }
            }
        }
    }
    if (diag_errors(diag) != before) return false;
    for (uint32_t m = 0; m < p->modules.len; m++) {
        Module *mod = p->modules.data[m];
        for (uint32_t i = 0; i < mod->items.len; i++) {
            Item *it = mod->items.data[i];
            if (it->kind == IT_FN && !it->fn.generics.len) {
                /* Check recursive templates even if no call uses them. */
                for (uint32_t j = 0; j < it->fn.params.len; j++)
                    if (it->fn.params.data[j].deflt) (void)clone(&d, it->fn.params.data[j].deflt);
                visit(&d, it->fn.body);
            } else if (it->kind == IT_TEST) visit(&d, it->test.body);
        }
    }
    return diag_errors(diag) == before;
}
