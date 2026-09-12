#include "storage.h"
#include "intrinsic.h"

#define STORAGE_DEPTH 128u
#define STORAGE_VISITS 100000u

typedef struct { const Type *stack[STORAGE_DEPTH]; uint32_t visits; StorageTarget target; } Types;
static bool scalar(const Type *t) {
    if (!t) return false;
    switch (t->kind) {
        case TY_VOID: case TY_BOOL: case TY_CHAR: case TY_INT: case TY_FLOAT:
        case TY_STR: case TY_ENUM: case TY_VEC2: case TY_VEC3: case TY_VEC4:
        case TY_QUAT: case TY_MAT3: case TY_MAT4: return true;
        default: return false;
    }
}
static StorageClass classify(Types *s,const Type *t,uint32_t depth) {
    StorageClass unknown={STORAGE_UNKNOWN,false};
    if (!t || depth>=STORAGE_DEPTH || s->visits>=STORAGE_VISITS) return unknown;
    s->visits++;
    if (scalar(t) || t->kind==TY_ERROR) return (StorageClass){0,true};
    for (uint32_t i=0;i<depth;i++) if (s->stack[i]==t) return unknown;
    s->stack[depth]=t;
    StorageClass r={0,true},inner={0,true};
    if (t->kind==TY_STRUCT) {
        if (!t->decl || t->decl->kind!=IT_STRUCT || t->decl->strukt.generics.len) return unknown;
        if (s->target==STORAGE_ENFUSION) r.flags|=STORAGE_TARGET_REFERENCE;
        for (uint32_t i=0;i<t->decl->strukt.fields.len;i++) {
            const Type *field=t->decl->strukt.fields.data[i].rtype;
            inner=classify(s,field,depth+1); r.flags|=inner.flags;
            bool field_copy=inner.logical_copy_supported;
            /* BerylCopy has a verified scalar array/List field Copy path. */
            if (s->target==STORAGE_ENFUSION && field &&
                (field->kind==TY_ARRAY || field->kind==TY_LIST)) field_copy=scalar(field->elem);
            r.logical_copy_supported=r.logical_copy_supported && field_copy;
        }
        return r;
    }
    if (t->elem) inner=classify(s,t->elem,depth+1);
    else return unknown;
    r.flags=inner.flags; r.logical_copy_supported=inner.logical_copy_supported;
    switch (t->kind) {
        case TY_ARRAY:
            if (s->target==STORAGE_ENFUSION) { r.flags|=STORAGE_TARGET_REFERENCE; r.logical_copy_supported=false; }
            return r;
        case TY_OPTION:
            if (s->target==STORAGE_ENFUSION) { r.flags|=STORAGE_TARGET_REFERENCE; r.logical_copy_supported=false; }
            return r;
        case TY_ERRUNION: return r;
        case TY_LIST: case TY_MAP: case TY_BOX: case TY_POOL:
            r.flags|=STORAGE_OWNED; r.logical_copy_supported=false;
            if (t->kind==TY_BOX || t->kind==TY_POOL) r.flags|=STORAGE_UNKNOWN;
            if (s->target==STORAGE_ENFUSION) r.flags|=STORAGE_TARGET_REFERENCE;
            if (t->kind==TY_MAP) { inner=classify(s,t->key,depth+1); r.flags|=inner.flags; }
            return r;
        case TY_RC: case TY_HANDLE:
            r.flags|=STORAGE_SHARED; r.logical_copy_supported=false;
            if (s->target==STORAGE_ENFUSION) r.flags|=STORAGE_TARGET_REFERENCE;
            return r;
        default: return unknown;
    }
}
StorageClass storage_classify(const Type *type,StorageTarget target) {
    if ((uint32_t)target>STORAGE_ENFUSION) return (StorageClass){STORAGE_UNKNOWN,false};
    Types s={.target=target}; return classify(&s,type,0);
}

typedef struct {
    DiagBag *d; Program *p; StorageTarget target; const Item *fn;
    uint32_t visits; bool failed;
} Scan;
static bool fail(Scan *s,Span at,const char *reason) {
    if (!s->failed) {
        Diag *d=diag_error(s->d,s->target==STORAGE_NATIVE?903:701,at,
            "%s storage admission: %s",s->target==STORAGE_NATIVE?"native":"Enfusion",reason);
        diag_help(d,"keep storage in one owner and use admitted let/inout borrows; use plain values or a reviewed external adapter for this unsupported operation");
        s->failed=true;
    }
    return false;
}
static bool visit(Scan *s,Span at,uint32_t depth) {
    if (s->failed) return false;
    if (depth>=STORAGE_DEPTH || s->visits>=STORAGE_VISITS) return fail(s,at,"analysis exceeded its bounded depth or visit budget");
    s->visits++; return true;
}
static StorageClass scan_type(Scan *s,const Type *t) {
    Types types={.visits=s->visits,.target=s->target};
    StorageClass result=classify(&types,t,0); s->visits=types.visits;
    return result;
}
static bool restricted(Scan *s,const Type *t) {
    StorageClass c=scan_type(s,t);
    return c.flags&(STORAGE_OWNED|STORAGE_SHARED|STORAGE_UNKNOWN);
}
static bool reference_value(Scan *s,const Type *t) {
    StorageClass c=scan_type(s,t);
    return c.flags&(STORAGE_OWNED|STORAGE_SHARED|STORAGE_UNKNOWN|STORAGE_TARGET_REFERENCE);
}
static bool place(const Expr *e) { return e && (e->kind==EX_PATH || e->kind==EX_SELF || e->kind==EX_FIELD || e->kind==EX_INDEX); }
static const Expr *call_receiver(const Expr *e) {
    if (!e->call.callee || e->call.callee->kind!=EX_FIELD) return NULL;
    if (e->res_kind==RES_FN && e->res) {
        const Item *fn=e->res;
        if (fn->fn.params.len && fn->fn.params.data[0].is_self) return e->call.callee->field.base;
    } else if (e->res_kind==RES_INTRINSIC &&
               (intrinsic_is_list_method((Intrinsic)e->intrinsic) || intrinsic_is_vec_method((Intrinsic)e->intrinsic)))
        return e->call.callee->field.base;
    return NULL;
}
static const Type *root_type(const Expr *e) {
    uint32_t depth=0;
    while (e && (e->kind==EX_FIELD || e->kind==EX_INDEX)) {
        if (depth++>=STORAGE_DEPTH) return NULL;
        e=e->kind==EX_FIELD?e->field.base:e->index.base;
    }
    if (e && e->res_kind==RES_LOCAL && e->res) return ((const Local *)e->res)->type;
    return e?e->type:NULL;
}
/* Every fresh owned value admitted here is checked recursively by the ordinary
 * walk. Calls returning owned values are rejected at declarations and calls. */
static bool fresh(const Expr *e) { return e && (e->kind==EX_STRUCT_LIT || e->kind==EX_ARRAY_LIT); }
static bool materialize(Scan *s,const Expr *e,bool assignment) {
    if (!e || !e->type) return true;
    StorageClass c=scan_type(s,e->type);
    if (c.flags&(STORAGE_SHARED|STORAGE_UNKNOWN)) return fail(s,e->span,"reference or unresolved storage has no reviewed logical-copy contract");
    if (s->target==STORAGE_NATIVE) {
        if ((c.flags&STORAGE_OWNED) && (assignment || !fresh(e)))
            return fail(s,e->span,assignment?"owning-value replacement has no destruction/transfer lowering":"this logical value copy would duplicate an owning descriptor");
    } else if (!c.logical_copy_supported && !fresh(e)) {
        return fail(s,e->span,"this logical value copy would retain shared collection/option storage");
    }
    return true;
}
static bool expression(Scan *s,const Expr *e,uint32_t depth);
static bool statement(Scan *s,const Stmt *st,uint32_t depth);

/* A temporary descriptor/reference captured for a borrow or foreach must not
 * outlive a mutation of its backing storage. Until storage identities exist,
 * conservatively reject any storage mutation in that evaluation interval.
 * Plain scalar accumulation remains admitted. This is not a purity analysis. */
static bool stable_expr(Scan *s,const Expr *e,uint32_t depth);
static bool stable_stmt(Scan *s,const Stmt *st,uint32_t depth) {
    if (!st) return true;
    if (!visit(s,st->span,depth)) return false;
    switch (st->kind) {
        case ST_LET: return stable_expr(s,st->let.init,depth+1);
        case ST_EXPR: case ST_RETURN: case ST_DEFER: return stable_expr(s,st->expr,depth+1);
        case ST_ASSIGN:
            if (reference_value(s,root_type(st->assign.target))) return fail(s,st->span,"a storage write can invalidate an active collection iteration or argument borrow");
            return stable_expr(s,st->assign.target,depth+1) && stable_expr(s,st->assign.value,depth+1);
        case ST_WHILE: return stable_expr(s,st->while_st.cond,depth+1) && stable_expr(s,st->while_st.body,depth+1);
        case ST_FOR: return stable_expr(s,st->for_st.iter,depth+1) && stable_expr(s,st->for_st.body,depth+1);
        case ST_BREAK: case ST_CONTINUE: return true;
    }
    return fail(s,st->span,"unknown statement in a storage lifetime interval");
}
static bool stable_expr(Scan *s,const Expr *e,uint32_t depth) {
    if (!e) return true;
    if (!visit(s,e->span,depth)) return false;
    depth++;
    switch (e->kind) {
        case EX_CALL: {
            const Expr *receiver=call_receiver(e);
            if (e->res_kind==RES_FN && e->res) {
                const Item *fn=e->res;
                if (!fn->fn.body || fn->fn.generics.len) return fail(s,e->span,"a call has no verified storage-effect summary");
                if (fn->fn.params.len && fn->fn.params.data[0].is_self && fn->fn.params.data[0].conv!=CONV_LET &&
                    reference_value(s,root_type(receiver))) return fail(s,e->span,"a mutable receiver can invalidate an active storage borrow");
            } else if (e->res_kind==RES_INTRINSIC) {
                Intrinsic id=(Intrinsic)e->intrinsic;
                if (id==INTR_LIST_PUSH || id==INTR_LIST_SET || id==INTR_LIST_CLEAR)
                    return fail(s,e->span,"a collection mutation can invalidate an active iteration or argument borrow");
                if (!((id>=INTR_PRINT && id<=INTR_SQRT) || intrinsic_is_list_method(id) ||
                      intrinsic_is_wrapping(id) || intrinsic_is_vec_method(id) || intrinsic_is_vec_new(id)))
                    return fail(s,e->span,"an intrinsic has no verified storage-effect summary");
            } else return fail(s,e->span,"an indirect call has no verified storage-effect summary");
            if (!stable_expr(s,receiver?receiver:e->call.callee,depth)) return false;
            for (uint32_t i=0;i<e->call.args.len;i++) {
                const Arg *a=&e->call.args.data[i];
                if (a->conv!=CONV_LET && reference_value(s,root_type(a->value))) return fail(s,a->span,"a mutable argument can invalidate an active storage borrow");
                if (!stable_expr(s,a->value,depth)) return false;
            }
            return true;
        }
        case EX_UNARY: return stable_expr(s,e->unary.operand,depth);
        case EX_BINARY: return stable_expr(s,e->binary.lhs,depth) && stable_expr(s,e->binary.rhs,depth);
        case EX_FIELD: return stable_expr(s,e->field.base,depth);
        case EX_INDEX: return stable_expr(s,e->index.base,depth) && stable_expr(s,e->index.index,depth);
        case EX_CAST: return stable_expr(s,e->cast.value,depth);
        case EX_STRUCT_LIT:
            for (uint32_t i=0;i<e->struct_lit.fields.len;i++) if (!stable_expr(s,e->struct_lit.fields.data[i].value,depth)) return false;
            return true;
        case EX_ARRAY_LIT:
            for (uint32_t i=0;i<e->array_lit.elems.len;i++) if (!stable_expr(s,e->array_lit.elems.data[i],depth)) return false;
            return true;
        case EX_IF: return stable_expr(s,e->if_expr.cond,depth) && stable_expr(s,e->if_expr.then_blk,depth) && stable_expr(s,e->if_expr.else_blk,depth);
        case EX_BLOCK:
            for (uint32_t i=0;i<e->block.stmts.len;i++) if (!stable_stmt(s,e->block.stmts.data[i],depth)) return false;
            return true;
        case EX_TRY: return stable_expr(s,e->try_expr.inner,depth);
        case EX_CATCH: return stable_expr(s,e->catch_expr.value,depth) && stable_expr(s,e->catch_expr.handler,depth);
        case EX_ORELSE: return stable_expr(s,e->orelse_expr.value,depth) && stable_expr(s,e->orelse_expr.fallback,depth);
        case EX_UNSAFE: return fail(s,e->span,"unsafe storage effects are not admitted during a borrow");
        case EX_RANGE: return stable_expr(s,e->range.lo,depth) && stable_expr(s,e->range.hi,depth);
        case EX_INT: case EX_FLOAT: case EX_STR: case EX_CHAR: case EX_BOOL:
        case EX_PATH: case EX_SELF: case EX_ERROR_LIT: return true;
    }
    return fail(s,e->span,"unknown expression in a storage lifetime interval");
}

static bool expression(Scan *s,const Expr *e,uint32_t depth) {
    if (!e) return true;
    if (!visit(s,e->span,depth)) return false;
    depth++;
    switch (e->kind) {
        case EX_CALL: {
            const Expr *receiver=call_receiver(e);
            if (restricted(s,e->type)) return fail(s,e->span,"owning/reference return values have no complete copy/transfer lowering");
            if (e->res_kind==RES_INTRINSIC && intrinsic_is_list_method((Intrinsic)e->intrinsic)) {
                const Type *element=receiver && receiver->type?receiver->type->elem:NULL;
                Intrinsic id=(Intrinsic)e->intrinsic;
                if (id==INTR_LIST_PUSH || id==INTR_LIST_SET || id==INTR_LIST_GET) {
                    StorageClass c=scan_type(s,element);
                    if (!c.logical_copy_supported || (s->target==STORAGE_ENFUSION && !scalar(element)))
                        return fail(s,e->span,"collection element operations lack recursive independent-value copying");
                }
            }
            bool captured=receiver && reference_value(s,root_type(receiver));
            if (!expression(s,receiver?receiver:e->call.callee,depth)) return false;
            for (uint32_t i=0;i<e->call.args.len;i++) {
                const Arg *a=&e->call.args.data[i];
                if (captured && !stable_expr(s,a->value,depth)) return false;
                if ((a->conv==CONV_SINK || a->conv==CONV_SET) && restricted(s,a->value?a->value->type:NULL))
                    return fail(s,a->span,"owning sink/set arguments have no complete transfer and cleanup lowering");
                if (!expression(s,a->value,depth)) return false;
                /* A scalar let value is captured by value, even when read from
                 * a reference-backed record/collection. Only mutable projected
                 * arguments retain a storage address; let aggregates retain
                 * storage only when their actual emitted value contains it. */
                if (place(a->value) && reference_value(s,
                    a->conv==CONV_INOUT || a->conv==CONV_SET
                        ? root_type(a->value) : a->value->type)) captured=true;
            }
            return true;
        }
        case EX_STRUCT_LIT:
            for (uint32_t i=0;i<e->struct_lit.fields.len;i++) {
                const Expr *v=e->struct_lit.fields.data[i].value;
                if (!materialize(s,v,false) || !expression(s,v,depth)) return false;
            }
            return true;
        case EX_ARRAY_LIT:
            for (uint32_t i=0;i<e->array_lit.elems.len;i++) {
                const Expr *v=e->array_lit.elems.data[i];
                if (s->target==STORAGE_ENFUSION && v && !scalar(v->type) && !fresh(v))
                    return fail(s,v->span,"array literal insertion does not copy reference-valued elements");
                if (!materialize(s,v,false) || !expression(s,v,depth)) return false;
            }
            return true;
        case EX_INDEX:
            if (reference_value(s,root_type(e->index.base)) && !stable_expr(s,e->index.index,depth)) return false;
            return expression(s,e->index.base,depth) && expression(s,e->index.index,depth);
        case EX_FIELD: return expression(s,e->field.base,depth);
        case EX_UNARY: return expression(s,e->unary.operand,depth);
        case EX_BINARY: return expression(s,e->binary.lhs,depth) && expression(s,e->binary.rhs,depth);
        case EX_CAST: return expression(s,e->cast.value,depth);
        case EX_IF: return expression(s,e->if_expr.cond,depth) && expression(s,e->if_expr.then_blk,depth) && expression(s,e->if_expr.else_blk,depth);
        case EX_BLOCK:
            for (uint32_t i=0;i<e->block.stmts.len;i++) if (!statement(s,e->block.stmts.data[i],depth)) return false;
            return true;
        case EX_TRY: return expression(s,e->try_expr.inner,depth);
        case EX_CATCH: return expression(s,e->catch_expr.value,depth) && expression(s,e->catch_expr.handler,depth);
        case EX_ORELSE: return expression(s,e->orelse_expr.value,depth) && expression(s,e->orelse_expr.fallback,depth);
        case EX_UNSAFE: return expression(s,e->unsafe_expr.body,depth);
        case EX_RANGE: return expression(s,e->range.lo,depth) && expression(s,e->range.hi,depth);
        case EX_INT: case EX_FLOAT: case EX_STR: case EX_CHAR: case EX_BOOL:
        case EX_PATH: case EX_SELF: case EX_ERROR_LIT: return true;
    }
    return fail(s,e->span,"unknown expression has no storage contract");
}
static bool statement(Scan *s,const Stmt *st,uint32_t depth) {
    if (!st) return true;
    if (!visit(s,st->span,depth)) return false;
    depth++;
    switch (st->kind) {
        case ST_LET: return materialize(s,st->let.init,false) && expression(s,st->let.init,depth);
        case ST_ASSIGN: return materialize(s,st->assign.value,true) && expression(s,st->assign.target,depth) && expression(s,st->assign.value,depth);
        case ST_RETURN:
            if (st->expr && restricted(s,st->expr->type)) return fail(s,st->span,"returning owning/reference storage is not admitted");
            return materialize(s,st->expr,false) && expression(s,st->expr,depth);
        case ST_EXPR: case ST_DEFER: return expression(s,st->expr,depth);
        case ST_WHILE: return expression(s,st->while_st.cond,depth) && expression(s,st->while_st.body,depth);
        case ST_FOR: {
            const Expr *it=st->for_st.iter; const Type *t=it?it->type:NULL;
            if (t && (t->kind==TY_LIST || t->kind==TY_ARRAY)) {
                StorageClass c=scan_type(s,t->elem);
                if (!c.logical_copy_supported || (s->target==STORAGE_ENFUSION && !scalar(t->elem)))
                    return fail(s,st->span,"iteration binding lacks independent element-value copying");
                if ((t->kind==TY_LIST || s->target==STORAGE_ENFUSION) && !stable_expr(s,st->for_st.body,depth)) return false;
            }
            return expression(s,it,depth) && expression(s,st->for_st.body,depth);
        }
        case ST_BREAK: case ST_CONTINUE: return true;
    }
    return fail(s,st->span,"unknown statement has no storage contract");
}
bool storage_admit(DiagBag *d,Program *p,StorageTarget target) {
    Scan s={.d=d,.p=p,.target=target};
    if ((uint32_t)target>STORAGE_ENFUSION) return fail(&s,SPAN_NONE,"unknown target profile");
    for (uint32_t m=0;m<p->modules.len && !s.failed;m++)
        for (uint32_t i=0;i<p->modules.data[m]->items.len && !s.failed;i++) {
            const Item *it=p->modules.data[m]->items.data[i]; s.fn=it;
            if (it->kind==IT_FN && it->fn.generics.len) continue;
            for (uint32_t k=0;k<it->nlocals && !s.failed;k++) {
                const Local *local=((Local **)it->locals)[k];
                StorageClass c=scan_type(&s,local->type);
                if (c.flags&(STORAGE_SHARED|STORAGE_UNKNOWN))
                    fail(&s,local->span,"this local or parameter has no reviewed storage representation/retention contract");
            }
            if (it->kind==IT_FN && !it->fn.generics.len) {
                if (restricted(&s,it->rtype)) { fail(&s,it->span,"owning/reference return signatures require unavailable copy/transfer lowering"); break; }
                for (uint32_t k=0;k<it->fn.params.len && !s.failed;k++) {
                    const Param *pm=&it->fn.params.data[k];
                    StorageClass c=scan_type(&s,pm->rtype);
                    if (c.flags&(STORAGE_SHARED|STORAGE_UNKNOWN))
                        fail(&s,pm->span,"this parameter has no reviewed storage representation/retention contract");
                    if ((pm->conv==CONV_SINK || pm->conv==CONV_SET) && restricted(&s,pm->rtype))
                        fail(&s,pm->span,"owning sink/set parameters require unavailable transfer and cleanup lowering");
                    if (!it->fn.body && reference_value(&s,pm->rtype)) fail(&s,pm->span,"external storage parameters have no reviewed borrowing/retention contract");
                    materialize(&s,pm->deflt,false); expression(&s,pm->deflt,0);
                }
                expression(&s,it->fn.body,0);
            } else if (it->kind==IT_TEST) expression(&s,it->test.body,0);
            else if (it->kind==IT_CONST) {
                if (restricted(&s,it->rtype)) fail(&s,it->span,"owning/reference constants have no storage lifecycle contract");
                materialize(&s,it->konst.value,false); expression(&s,it->konst.value,0);
            } else if (it->kind==IT_STRUCT && !it->strukt.generics.len) {
                if (target==STORAGE_ENFUSION && !scan_type(&s,it->rtype).logical_copy_supported) {
                    fail(&s,it->span,"generated record helper lacks recursive copying for this field storage shape"); break;
                }
                for (uint32_t f=0;f<it->strukt.fields.len && !s.failed;f++) {
                    const Expr *e=it->strukt.fields.data[f].deflt;
                    if (target==STORAGE_ENFUSION && e && !scalar(e->type) && !fresh(e))
                        fail(&s,e->span,"record field default emission does not copy a reference-valued source");
                    materialize(&s,e,false); expression(&s,e,0);
                }
            }
        }
    return !s.failed;
}
