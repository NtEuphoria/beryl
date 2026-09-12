#include "access.h"
#include "intrinsic.h"

typedef struct { Local *root; const Expr *part[ACCESS_MAX_DEPTH]; uint32_t count; bool known; } Path;
typedef struct { uint32_t *visits; const Path *watched; AccessResult issue; } Scan;
static bool stop(Scan *s,AccessStatus status,Span at,const char *reason) {
    if (s->issue.status==ACCESS_SAFE) {
        s->issue.status=status; s->issue.conflict=at; s->issue.reason=reason;
    }
    return true;
}
static bool visit(Scan *s,Span at,uint32_t depth) {
    if (s->issue.status!=ACCESS_SAFE) return false;
    if (depth>=ACCESS_MAX_DEPTH || *s->visits>=ACCESS_MAX_VISITS) {
        stop(s,ACCESS_UNPROVEN,at,"access analysis exceeded its bounded depth or visit budget"); return false;
    }
    (*s->visits)++; return true;
}
static Path path_of(const Expr *e) {
    Path p={0};
    while (e && (e->kind==EX_FIELD || e->kind==EX_INDEX)) {
        if (p.count==ACCESS_MAX_DEPTH) return p;
        p.part[p.count++]=e; e=e->kind==EX_FIELD?e->field.base:e->index.base;
    }
    if (e && (e->kind==EX_PATH || e->kind==EX_SELF) && e->res_kind==RES_LOCAL && e->res) {
        p.root=e->res; p.known=true;
    }
    return p;
}
/* Distinct binding paths prove storage separation only for recursively plain
 * values. Container copies and reference wrappers still need separate storage
 * identity analysis; their spellings must not manufacture non-aliasing. */
static bool plain_type(Scan *s,const Type *t,uint32_t depth) {
    if (!t || !visit(s,SPAN_NONE,depth)) return false;
    switch (t->kind) {
        case TY_VOID: case TY_BOOL: case TY_CHAR: case TY_INT: case TY_FLOAT:
        case TY_ENUM: case TY_VEC2: case TY_VEC3: case TY_VEC4: return true;
        case TY_ARRAY: return plain_type(s,t->elem,depth+1);
        case TY_STRUCT:
            if (!t->decl || t->decl->strukt.generics.len) return false;
            for (uint32_t i=0;i<t->decl->strukt.fields.len;i++)
                if (!plain_type(s,t->decl->strukt.fields.data[i].rtype,depth+1)) return false;
            return true;
        default: return false;
    }
}
static bool mutation(Scan *s,const Expr *other) {
    if (!s->watched) return false;
    Path p=path_of(other); const Path *w=s->watched;
    Span at=other?other->span:SPAN_NONE;
    if (!w->known || !p.known) return stop(s,ACCESS_UNPROVEN,at,"a mutable access has no proven local storage path");
    bool plain=plain_type(s,w->root->type,0) && plain_type(s,p.root->type,0);
    if (s->issue.status!=ACCESS_SAFE) return true;
    if (p.root!=w->root) return !plain && stop(s,ACCESS_UNPROVEN,at,"distinct bindings may share owning or reference storage");
    uint32_t n=p.count<w->count?p.count:w->count;
    for (uint32_t i=0;i<n;i++) {
        const Expr *x=w->part[w->count-1-i], *y=p.part[p.count-1-i];
        bool different=false;
        if (x->kind!=y->kind) break;
        if (x->kind==EX_FIELD) {
            if (x->res_kind==RES_FIELD && y->res_kind==RES_FIELD && x->res && y->res) different=x->res!=y->res;
            else if (x->res_kind==RES_VEC_COMP && y->res_kind==RES_VEC_COMP) different=x->intrinsic!=y->intrinsic;
            else break;
        } else {
            const Expr *xi=x->index.index,*yi=y->index.index;
            if (!xi || !yi || xi->kind!=EX_INT || yi->kind!=EX_INT) break;
            different=xi->int_lit.val!=yi->int_lit.val;
        }
        if (different) return !plain && stop(s,ACCESS_UNPROVEN,at,"disjoint fields or indices may share owning or reference storage");
    }
    return stop(s,ACCESS_CONFLICT,at,"a write, move or mutable argument may overlap the selected destination");
}
static bool expression(Scan *s,const Expr *e,uint32_t depth);
static bool statement(Scan *s,const Stmt *st,uint32_t depth) {
    if (!st) return false;
    if (!visit(s,st->span,depth)) return true;
    switch (st->kind) {
        case ST_LET: return expression(s,st->let.init,depth+1);
        case ST_EXPR: case ST_RETURN: case ST_DEFER: return expression(s,st->expr,depth+1);
        case ST_ASSIGN:
            if (s->watched) {
                if (mutation(s,st->assign.target)) return true;
            } else {
                AccessResult result=access_projected_assignment(st,s->visits);
                if (result.status!=ACCESS_SAFE) { s->issue=result; return true; }
            }
            return expression(s,st->assign.target,depth+1) || expression(s,st->assign.value,depth+1);
        case ST_WHILE: return expression(s,st->while_st.cond,depth+1) || expression(s,st->while_st.body,depth+1);
        case ST_FOR: return expression(s,st->for_st.iter,depth+1) || expression(s,st->for_st.body,depth+1);
        case ST_BREAK: case ST_CONTINUE: return false;
    }
    return stop(s,ACCESS_UNPROVEN,st->span,"an unknown statement has no verified access summary");
}
static bool known_intrinsic(Intrinsic i) {
    return (i>=INTR_PRINT && i<=INTR_SQRT) || intrinsic_is_list_method(i) ||
        intrinsic_is_wrapping(i) || intrinsic_is_vec_method(i) || intrinsic_is_vec_new(i);
}
static bool expression(Scan *s,const Expr *e,uint32_t depth) {
    if (!e) return false;
    if (!visit(s,e->span,depth)) return true;
    depth++;
    switch (e->kind) {
        case EX_INT: case EX_FLOAT: case EX_BOOL: case EX_STR: case EX_CHAR:
        case EX_PATH: case EX_SELF: case EX_ERROR_LIT: return false;
        case EX_UNARY: return expression(s,e->unary.operand,depth);
        case EX_BINARY: return expression(s,e->binary.lhs,depth) || expression(s,e->binary.rhs,depth);
        case EX_CALL: {
            const Expr *receiver=NULL;
            if (e->res_kind==RES_FN && e->res) {
                const Item *fn=e->res;
                if (s->watched && (!fn->fn.body || fn->fn.generics.len))
                    return stop(s,ACCESS_UNPROVEN,e->span,"an external or generic call has no verified access summary");
                if (fn->fn.params.len && fn->fn.params.data[0].is_self) {
                    if (!e->call.callee || e->call.callee->kind!=EX_FIELD)
                        return stop(s,ACCESS_UNPROVEN,e->span,"a method receiver has no verified access path");
                    receiver=e->call.callee->field.base;
                    if (s->watched && fn->fn.params.data[0].conv!=CONV_LET && mutation(s,receiver)) return true;
                }
            } else if (e->res_kind==RES_INTRINSIC) {
                Intrinsic id=(Intrinsic)e->intrinsic;
                if (s->watched && !known_intrinsic(id)) return stop(s,ACCESS_UNPROVEN,e->span,"an intrinsic has no verified access summary");
                if (intrinsic_is_list_method(id) || intrinsic_is_vec_method(id)) {
                    if (!e->call.callee || e->call.callee->kind!=EX_FIELD)
                        return stop(s,ACCESS_UNPROVEN,e->span,"an intrinsic receiver has no verified access path");
                    receiver=e->call.callee->field.base;
                    if ((id==INTR_LIST_PUSH || id==INTR_LIST_SET || id==INTR_LIST_CLEAR) && mutation(s,receiver)) return true;
                }
            } else if (s->watched) return stop(s,ACCESS_UNPROVEN,e->span,"an indirect call has no verified access summary");
            if (expression(s,receiver?receiver:e->call.callee,depth)) return true;
            for (uint32_t i=0;i<e->call.args.len;i++) {
                const Arg *arg=&e->call.args.data[i];
                if ((arg->conv!=CONV_LET && mutation(s,arg->value)) || expression(s,arg->value,depth)) return true;
            }
            return false;
        }
        case EX_FIELD: return expression(s,e->field.base,depth);
        case EX_INDEX: return expression(s,e->index.base,depth) || expression(s,e->index.index,depth);
        case EX_CAST: return expression(s,e->cast.value,depth);
        case EX_STRUCT_LIT:
            for (uint32_t i=0;i<e->struct_lit.fields.len;i++) if (expression(s,e->struct_lit.fields.data[i].value,depth)) return true;
            return false;
        case EX_ARRAY_LIT:
            for (uint32_t i=0;i<e->array_lit.elems.len;i++) if (expression(s,e->array_lit.elems.data[i],depth)) return true;
            return false;
        case EX_IF: return expression(s,e->if_expr.cond,depth) || expression(s,e->if_expr.then_blk,depth) || expression(s,e->if_expr.else_blk,depth);
        case EX_BLOCK:
            for (uint32_t i=0;i<e->block.stmts.len;i++) if (statement(s,e->block.stmts.data[i],depth)) return true;
            return false;
        case EX_TRY: return expression(s,e->try_expr.inner,depth);
        case EX_CATCH: return expression(s,e->catch_expr.value,depth) || expression(s,e->catch_expr.handler,depth);
        case EX_ORELSE: return expression(s,e->orelse_expr.value,depth) || expression(s,e->orelse_expr.fallback,depth);
        case EX_UNSAFE: return expression(s,e->unsafe_expr.body,depth);
        case EX_RANGE: return expression(s,e->range.lo,depth) || expression(s,e->range.hi,depth);
    }
    return stop(s,ACCESS_UNPROVEN,e->span,"an unknown expression has no verified access summary");
}
AccessResult access_projected_assignment(const Stmt *st,uint32_t *visits) {
    AccessResult result={.status=ACCESS_SAFE,.destination=SPAN_NONE,.conflict=SPAN_NONE,.reason="safe"};
    if (!st || st->kind!=ST_ASSIGN) return result;
    const Expr *target=st->assign.target;
    if (!target || (target->kind!=EX_FIELD && target->kind!=EX_INDEX)) return result;
    uint32_t local_visits=0; Path watched=path_of(target);
    Scan s={.visits=visits?visits:&local_visits,.watched=&watched,.issue=result}; s.issue.destination=target->span;
    if (!watched.known) stop(&s,ACCESS_UNPROVEN,target->span,"a projected destination has no proven local storage path");
    else if (!expression(&s,target,0)) expression(&s,st->assign.value,0);
    return s.issue;
}
bool access_check_destinations(DiagBag *d,Program *p) {
    uint32_t visits=0; Scan s={.visits=&visits,.issue={.destination=SPAN_NONE,.conflict=SPAN_NONE,.reason="safe"}};
    for (uint32_t m=0;m<p->modules.len && s.issue.status==ACCESS_SAFE;m++)
        for (uint32_t i=0;i<p->modules.data[m]->items.len && s.issue.status==ACCESS_SAFE;i++) {
            const Item *it=p->modules.data[m]->items.data[i];
            if (it->kind==IT_FN && !it->fn.generics.len) expression(&s,it->fn.body,0);
            else if (it->kind==IT_TEST) expression(&s,it->test.body,0);
            else if (it->kind==IT_CONST) expression(&s,it->konst.value,0);
            else if (it->kind==IT_STRUCT && !it->strukt.generics.len)
                for (uint32_t f=0;f<it->strukt.fields.len && s.issue.status==ACCESS_SAFE;f++) expression(&s,it->strukt.fields.data[f].deflt,0);
        }
    if (s.issue.status==ACCESS_SAFE) return true;
    Span at=s.issue.destination.file==UINT32_MAX?s.issue.conflict:s.issue.destination;
    Diag *diagnostic=diag_error(d,401,at,"cannot preserve exclusive projected assignment: %s",s.issue.reason);
    diag_label(diagnostic,s.issue.conflict,"conflicting or unproven access occurs here");
    diag_help(diagnostic,"perform the mutation in a separate statement before selecting the destination");
    return false;
}
