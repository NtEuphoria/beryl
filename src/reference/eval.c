#include "internal.h"
#include <math.h>

static Local *declaration(Frame *f,Str name,Span span) {
    for (uint32_t i=0;f && i<f->item->nlocals;i++) {
        Local *l=((Local **)f->item->locals)[i];
        if (l->span.offset==span.offset && str_eq(l->name,name)) return l;
    }
    return NULL;
}
static bool is_place(Expr *e) {
    return e && ((e->kind==EX_PATH && e->res_kind==RES_LOCAL) || e->kind==EX_SELF ||
        (e->kind==EX_FIELD && is_place(e->field.base)) ||
        (e->kind==EX_INDEX && is_place(e->index.base)));
}
Value *ref_place(Ref *r,Frame *f,Expr *e) {
    if (!e || !ref_step(r,e->span)) return NULL;
    if ((e->kind==EX_PATH || e->kind==EX_SELF) && e->res_kind==RES_LOCAL) {
        Local *l=e->res;
        if (f && l && l->id<f->item->nlocals && f->locals[l->id]) return f->locals[l->id];
        ref_fail(r,REF_TRAP,e->span,"missing local storage"); return NULL;
    }
    if (e->kind==EX_FIELD) {
        Value *v=is_place(e->field.base)?ref_place(r,f,e->field.base):ref_eval(r,f,e->field.base);
        Field *field=e->res;
        if (!v || !field || e->res_kind!=RES_FIELD) return NULL;
        return v->as.members[field->index];
    }
    if (e->kind==EX_INDEX) {
        Value *v=is_place(e->index.base)?ref_place(r,f,e->index.base):ref_eval(r,f,e->index.base);
        if (!v) return NULL;
        Value *index=ref_eval(r,f,e->index.index); if (!index) return NULL;
        if (index->as.i<0 || (uint64_t)index->as.i>=v->type->array_len) {
            ref_source_trap(r,REF_SOURCE_TRAP_BOUNDS,e->span,"array index outside its fixed bounds"); return NULL;
        }
        return v->as.members[index->as.i];
    }
    ref_fail(r,REF_UNAVAILABLE,e->span,"this place expression"); return NULL;
}
Value *ref_call(Ref *r,Frame *caller,Expr *e) {
    Item *fn=e->res;
    if (r->call_depth>=r->opts.max_call_depth) { ref_fail(r,REF_BUDGET,e->span,"call-depth budget exhausted"); return NULL; }
    Frame f={.item=fn}; f.locals=ref_alloc(r,fn->nlocals,sizeof(Value *),e->span); if (!f.locals) return NULL;
    bool self=fn->fn.params.len && fn->fn.params.data[0].is_self;
    for (uint32_t i=0;i<fn->fn.params.len;i++) {
        Param *pm=&fn->fn.params.data[i];
        Expr *actual=self && i==0 ? e->call.callee->field.base : e->call.args.data[i-(self?1:0)].value;
        Value *v=NULL;
        if (pm->conv==CONV_INOUT || pm->conv==CONV_SET) v=ref_place(r,caller,actual);
        else if (pm->conv==CONV_LET && (pm->rtype->kind==TY_STRUCT || pm->rtype->kind==TY_ARRAY) && is_place(actual)) {
            v=ref_place(r,caller,actual); if (!ref_readable(r,v,actual->span)) return NULL;
        } else {
            if (pm->conv==CONV_SINK && is_place(actual)) {
                /* Admitted plain values have no observable destructor. */
                Value *old=ref_place(r,caller,actual);
                v=ref_copy(r,old,actual->span);
                Value *empty=ref_zero(r,pm->rtype,false,actual->span);
                if (!v || !old || !empty) return NULL;
                *old=*empty;
            } else v=ref_eval(r,caller,actual);
        }
        if (!v) return NULL;
        f.locals[i]=v;
    }
    r->call_depth++;
    ref_eval(r,&f,fn->fn.body);
    r->call_depth--;
    if (r->result.status!=REF_SUCCESS) return NULL;
    if (f.returned) return ref_copy(r,f.returned,e->span);
    if (fn->rtype && fn->rtype->kind!=TY_VOID) {
        ref_fail(r,REF_TRAP,e->span,"non-void function completed without returning"); return NULL;
    }
    return ref_zero(r,fn->rtype,true,e->span);
}
static Value *evaluate(Ref *r,Frame *f,Expr *e) {
    switch (e->kind) {
        case EX_INT:
            if (e->type->kind==TY_FLOAT) return ref_f32(r,(float)e->int_lit.val,e->span);
            return ref_i32(r,(int64_t)e->int_lit.val,e->span);
        case EX_FLOAT: return ref_f32(r,(float)e->float_lit.val,e->span);
        case EX_BOOL: return ref_bool(r,e->bool_lit,e->span);
        case EX_STR: {
            Value *v=ref_zero(r,e->type,true,e->span); if (v) v->as.s=e->str_lit; return v;
        }
        case EX_PATH:
            if (e->res_kind==RES_CONST) {
                if (r->constant_depth>=64) { ref_fail(r,REF_BUDGET,e->span,"constant nesting budget exhausted"); return NULL; }
                Item *it=e->res; r->constant_depth++;
                Value *value=ref_eval(r,NULL,it->konst.value);
                r->constant_depth--; return value;
            }
            /* fall through */
        case EX_SELF: case EX_FIELD: case EX_INDEX: return ref_copy(r,ref_place(r,f,e),e->span);
        case EX_UNARY: {
            Expr *operand=e->unary.operand;
            if (e->unary.op==TK_MINUS && operand->kind==EX_INT && e->type->kind==TY_INT &&
                operand->int_lit.val==UINT64_C(2147483648)) return ref_i32(r,INT32_MIN,e->span);
            Value *v=ref_eval(r,f,operand); if (!v) return NULL;
            if (e->unary.op==TK_BANG) return ref_bool(r,!v->as.b,e->span);
            if (e->unary.op==TK_PLUS) return v;
            if (e->unary.op==TK_MINUS) return v->type->kind==TY_FLOAT ? ref_f32(r,-v->as.f,e->span) : ref_i32(r,-v->as.i,e->span);
            if (e->unary.op==TK_TILDE) return ref_i32(r,-v->as.i-1,e->span);
            break;
        }
        case EX_BINARY: {
            Value *a=ref_eval(r,f,e->binary.lhs); if (!a) return NULL;
            TokKind op=e->binary.op;
            if (op==TK_ANDAND && !a->as.b) return ref_bool(r,false,e->span);
            if (op==TK_OROR && a->as.b) return ref_bool(r,true,e->span);
            Value *b=ref_eval(r,f,e->binary.rhs); if (!b) return NULL;
            if (op==TK_ANDAND || op==TK_OROR) return ref_bool(r,b->as.b,e->span);
            return ref_binary(r,op,a,b,e->type,e->span);
        }
        case EX_CALL: return e->res_kind==RES_FN ? ref_call(r,f,e) : ref_intrinsic(r,f,e);
        case EX_CAST: {
            Value *v=ref_eval(r,f,e->cast.value); if (!v) return NULL;
            double n=v->type->kind==TY_FLOAT ? (double)v->as.f : v->type->kind==TY_BOOL ? (v->as.b?1.0:0.0) : (double)v->as.i;
            if (e->type->kind==TY_FLOAT) return ref_f32(r,(float)n,e->span);
            if (!isfinite(n) || n<(double)INT32_MIN || n>=2147483648.0) {
                ref_fail(r,REF_TRAP,e->span,"numeric cast outside the i32 range"); return NULL;
            }
            return ref_i32(r,(int64_t)n,e->span);
        }
        case EX_STRUCT_LIT: {
            Value *v=ref_zero(r,e->type,true,e->span); if (!v) return NULL;
            Item *it=e->type->decl;
            for (uint32_t i=0;i<e->struct_lit.fields.len;i++) {
                FieldInit *field=&e->struct_lit.fields.data[i];
                Value *value=ref_eval(r,f,field->value); if (!value) return NULL;
                for (uint32_t j=0;j<it->strukt.fields.len;j++) if (str_eq(field->name,it->strukt.fields.data[j].name)) {
                    v->as.members[j]=value; break;
                }
            }
            return v;
        }
        case EX_ARRAY_LIT: {
            Value *v=ref_zero(r,e->type,true,e->span); if (!v) return NULL;
            for (uint32_t i=0;i<e->array_lit.elems.len;i++) {
                v->as.members[i]=ref_eval(r,f,e->array_lit.elems.data[i]); if (!v->as.members[i]) return NULL;
            }
            return v;
        }
        case EX_IF: {
            Value *condition=ref_eval(r,f,e->if_expr.cond); if (!condition) return NULL;
            Expr *branch=condition->as.b ? e->if_expr.then_blk : e->if_expr.else_blk;
            if (branch) ref_eval(r,f,branch);
            return ref_zero(r,e->type,true,e->span);
        }
        case EX_BLOCK:
            for (uint32_t i=0;i<e->block.stmts.len && f->flow==FLOW_NORMAL && r->result.status==REF_SUCCESS;i++)
                ref_stmt(r,f,e->block.stmts.data[i]);
            return ref_zero(r,e->type,true,e->span);
        default: break;
    }
    ref_fail(r,REF_UNAVAILABLE,e->span,"this expression form"); return NULL;
}
Value *ref_eval(Ref *r,Frame *f,Expr *e) {
    if (!e || !ref_step(r,e->span)) return NULL;
    if (r->eval_depth>=512) { ref_fail(r,REF_BUDGET,e->span,"evaluation nesting budget exhausted"); return NULL; }
    r->eval_depth++; Value *v=evaluate(r,f,e); r->eval_depth--; return v;
}
void ref_stmt(Ref *r,Frame *f,Stmt *s) {
    if (!s || !ref_step(r,s->span)) return;
    switch (s->kind) {
        case ST_LET: {
            Local *l=declaration(f,s->let.name,s->span);
            if (!l) { ref_fail(r,REF_TRAP,s->span,"missing declaration identity"); return; }
            f->locals[l->id]=s->let.init ? ref_eval(r,f,s->let.init) : ref_zero(r,l->type,false,s->span);
            if (r->opts.watch_root.enabled && s->span.file==r->opts.watch_root.file && s->span.offset==r->opts.watch_root.offset)
                r->watch_root=f->locals[l->id];
            break;
        }
        case ST_EXPR: case ST_DEFER: ref_eval(r,f,s->expr); break;
        case ST_RETURN:
            f->returned=s->expr ? ref_eval(r,f,s->expr) : ref_zero(r,NULL,true,s->span);
            f->flow=FLOW_RETURN; break;
        case ST_BREAK: f->flow=FLOW_BREAK; break;
        case ST_CONTINUE: f->flow=FLOW_CONTINUE; break;
        case ST_ASSIGN: {
            Value *target=ref_place(r,f,s->assign.target); if (!target) return;
            Value *old=s->assign.op==TK_ASSIGN ? NULL : ref_copy(r,target,s->span);
            Value *rhs=ref_eval(r,f,s->assign.value); if (!rhs) return;
            if (s->assign.op!=TK_ASSIGN) {
                TokKind op=s->assign.op==TK_PLUSEQ ? TK_PLUS : s->assign.op==TK_MINUSEQ ? TK_MINUS :
                    s->assign.op==TK_STAREQ ? TK_STAR : s->assign.op==TK_SLASHEQ ? TK_SLASH : TK_PERCENT;
                rhs=ref_binary(r,op,old,rhs,target->type,s->span); if (!rhs) return;
            }
            *target=*rhs; break;
        }
        case ST_WHILE:
            while (r->result.status==REF_SUCCESS) {
                Value *cond=ref_eval(r,f,s->while_st.cond); if (!cond || !cond->as.b) break;
                ref_eval(r,f,s->while_st.body);
                if (f->flow==FLOW_RETURN) break;
                bool stop=f->flow==FLOW_BREAK; f->flow=FLOW_NORMAL; if (stop) break;
            }
            break;
        case ST_FOR: {
            Local *local=declaration(f,s->for_st.var,s->span);
            if (!local) { ref_fail(r,REF_TRAP,s->span,"missing loop binding"); return; }
            Expr *iter=s->for_st.iter; Value *array=NULL;
            int64_t lo=0,hi=0;
            if (iter->kind==EX_RANGE) {
                Value *first=ref_eval(r,f,iter->range.lo); if (!first) return; lo=first->as.i;
                Value *last=ref_eval(r,f,iter->range.hi); if (!last) return; hi=last->as.i;
            } else { array=ref_eval(r,f,iter); if (!array) return; hi=(int64_t)array->type->array_len; }
            for (int64_t i=lo;i<hi && r->result.status==REF_SUCCESS;i++) {
                if (!ref_step(r,s->span)) break;
                f->locals[local->id]=array ? ref_copy(r,array->as.members[i],s->span) : ref_i32(r,i,s->span);
                ref_eval(r,f,s->for_st.body);
                if (f->flow==FLOW_RETURN) break;
                bool stop=f->flow==FLOW_BREAK; f->flow=FLOW_NORMAL; if (stop) break;
            }
            break;
        }
    }
}
