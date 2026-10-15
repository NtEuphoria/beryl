#include "reference.h"
#include "../sema/intrinsic.h"
#include "../sema/access.h"

typedef struct { DiagBag *d; uint32_t depth, work, before; } Admission;
static bool type_ok(Admission *a,Type *t,uint32_t depth) {
    if (a->work++>=100000) return false;
    if (!t) return true;
    if (depth>64) return false;
    switch (t->kind) {
        case TY_VOID: case TY_BOOL: case TY_STR: return true;
        case TY_INT: return t->bits==32 && t->is_signed;
        case TY_FLOAT: return t->bits==32;
        case TY_STRUCT:
            if (!t->decl || t->decl->strukt.generics.len) return false;
            for (uint32_t i=0;i<t->decl->strukt.fields.len;i++)
                if (!type_ok(a,t->decl->strukt.fields.data[i].rtype,depth+1)) return false;
            return true;
        case TY_ARRAY: return t->array_len<=1000000 && type_ok(a,t->elem,depth+1);
        default: return false;
    }
}
static void unavailable(Admission *a,Span span,const char *what) {
    if (diag_errors(a->d)!=a->before) return;
    if (a->work>=100000) what="admission work exceeding 100,000 visits";
    diag_error(a->d,1001,span,"reference execution does not support %s",what);
}
/* Direct API users still receive bounded reference admission even when they
 * did not call the shared ownership pass. Ordinary CLI paths report BE0401. */
static void assignment_boundary(Admission *a,Stmt *s) {
    AccessResult result=access_projected_assignment(s,&a->work);
    if (result.status!=ACCESS_SAFE)
        unavailable(a,s->span,"a projected assignment whose destination evaluation or RHS may mutate an overlapping place; use separate statements before selecting the destination");
}
static void expr(Admission *a,Expr *e);
static void stmt(Admission *a,Stmt *s) {
    if (!s || diag_errors(a->d)!=a->before) return;
    if (a->work++>=100000) { unavailable(a,s->span,"admission work exceeding 100,000 visits"); return; }
    switch (s->kind) {
        case ST_LET: expr(a,s->let.init); break;
        case ST_EXPR: case ST_RETURN: case ST_DEFER: expr(a,s->expr); break;
        case ST_ASSIGN: assignment_boundary(a,s); expr(a,s->assign.target); expr(a,s->assign.value); break;
        case ST_WHILE: expr(a,s->while_st.cond); expr(a,s->while_st.body); break;
        case ST_FOR: expr(a,s->for_st.iter); expr(a,s->for_st.body); break;
        case ST_BREAK: case ST_CONTINUE: break;
    }
}
static void expr(Admission *a,Expr *e) {
    if (!e || diag_errors(a->d)!=a->before) return;
    if (a->depth>=128) { unavailable(a,e->span,"AST nesting beyond 128 levels"); return; }
    if (!type_ok(a,e->type,0)) { unavailable(a,e->span,"this expression's type"); return; }
    a->depth++;
    switch (e->kind) {
        case EX_INT: case EX_FLOAT: case EX_BOOL: case EX_STR: case EX_SELF: break;
        case EX_PATH:
            if (e->res_kind!=RES_LOCAL && e->res_kind!=RES_CONST)
                unavailable(a,e->span,"a type or function as a first-class value");
            break;
        case EX_UNARY: expr(a,e->unary.operand); break;
        case EX_BINARY:
            if (e->binary.lhs->type->kind==TY_STR)
                unavailable(a,e->span,"string operators");
            expr(a,e->binary.lhs); expr(a,e->binary.rhs); break;
        case EX_CALL:
            if (access_call_arguments(e,&a->work).status!=ACCESS_SAFE)
                unavailable(a,e->span,"a captured call argument whose selection or later arguments may mutate an overlapping place; use separate statements or an independent value snapshot");
            if (e->res_kind==RES_FN) {
                Item *fn=e->res;
                if (!fn || !fn->fn.body || fn->fn.generics.len)
                    unavailable(a,e->span,"a function without a concrete body");
                else if (fn->fn.params.len && fn->fn.params.data[0].is_self)
                    expr(a,e->call.callee->field.base);
            } else if (e->res_kind==RES_INTRINSIC) {
                Intrinsic id=(Intrinsic)e->intrinsic;
                if (!((id>=INTR_PRINT && id<=INTR_SQRT) ||
                      (id>=INTR_WRAPPING_ADD && id<=INTR_SATURATING_SUB)))
                    unavailable(a,e->span,"this intrinsic");
            } else unavailable(a,e->span,"this call target");
            for (uint32_t i=0;i<e->call.args.len;i++) expr(a,e->call.args.data[i].value);
            if (e->res_kind==RES_INTRINSIC && (e->intrinsic==INTR_PRINT || e->intrinsic==INTR_PRINTLN)) {
                for (uint32_t i=0;i<e->call.args.len;i++) {
                    TypeKind k=e->call.args.data[i].value->type->kind;
                    if (k!=TY_INT && k!=TY_FLOAT && k!=TY_BOOL && k!=TY_STR)
                        unavailable(a,e->span,"printing non-scalar values");
                }
            }
            break;
        case EX_FIELD: expr(a,e->field.base); break;
        case EX_INDEX: expr(a,e->index.base); expr(a,e->index.index); break;
        case EX_CAST: expr(a,e->cast.value); break;
        case EX_STRUCT_LIT:
            for (uint32_t i=0;i<e->struct_lit.fields.len;i++) expr(a,e->struct_lit.fields.data[i].value);
            break;
        case EX_ARRAY_LIT:
            for (uint32_t i=0;i<e->array_lit.elems.len;i++) expr(a,e->array_lit.elems.data[i]);
            break;
        case EX_IF: expr(a,e->if_expr.cond); expr(a,e->if_expr.then_blk); expr(a,e->if_expr.else_blk); break;
        case EX_BLOCK:
            for (uint32_t i=0;i<e->block.stmts.len;i++) stmt(a,e->block.stmts.data[i]);
            break;
        case EX_RANGE:
            if (e->type->kind!=TY_INT) unavailable(a,e->span,"non-integer ranges");
            expr(a,e->range.lo); expr(a,e->range.hi); break;
        default: unavailable(a,e->span,"this expression form"); break;
    }
    a->depth--;
}
bool reference_admit(DiagBag *d,Program *p) {
    uint32_t before=diag_errors(d); Admission a={.d=d,.before=before};
    for (uint32_t m=0;m<p->modules.len && diag_errors(d)==before;m++) for (uint32_t i=0;i<p->modules.data[m]->items.len && diag_errors(d)==before;i++) {
        Item *it=p->modules.data[m]->items.data[i];
        if (it->kind==IT_USE) continue;
        if (!type_ok(&a,it->rtype,0)) unavailable(&a,it->span,"this declaration's type");
        for (uint32_t l=0;l<it->nlocals;l++) {
            Local *local=((Local **)it->locals)[l];
            if (!type_ok(&a,local->type,0)) unavailable(&a,local->span,"this local's type");
        }
        switch (it->kind) {
            case IT_FN:
                if (it->fn.generics.len || !it->fn.body) unavailable(&a,it->span,"generic or external functions");
                expr(&a,it->fn.body); break;
            case IT_TEST: expr(&a,it->test.body); break;
            case IT_CONST: expr(&a,it->konst.value); break;
            case IT_STRUCT:
                for (uint32_t f=0;f<it->strukt.fields.len;f++) expr(&a,it->strukt.fields.data[f].deflt);
                break;
            default: unavailable(&a,it->span,"this declaration kind"); break;
        }
    }
    return diag_errors(d)==before;
}
