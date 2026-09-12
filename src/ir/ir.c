#include "ir.h"
#include "../sema/resolve.h"
#include "../sema/intrinsic.h"
#include "../common/hash.h"
#include <math.h>
#include <stdlib.h>
#include <string.h>

typedef struct {
    Arena *a; DiagBag *d; IrProgram *ir; Item **items; Item *item;
    uint32_t function, region, depth, work, type_depth; bool failed;
    Type *types[IR_MAX_TYPES];
} Lower;
static void unavailable(Lower *l,Span at,const char *why) {
    if (!l->failed) diag_error(l->d,1101,at,"experimental structured IR does not support %s",why);
    l->failed=true;
}
static bool bounded(Lower *l,uint32_t count,uint32_t limit,Span at) {
    if (count<limit) return true;
    unavailable(l,at,"a table or traversal exceeding its fixed experimental quota"); return false;
}
static bool scalar(Type *t,IrType *out) {
    if (!t || t->kind==TY_VOID) { *out=IR_VOID; return true; }
    if (t->kind==TY_BOOL) { *out=IR_BOOL; return true; }
    if (t->kind==TY_INT && t->bits==32 && t->is_signed) { *out=IR_I32; return true; }
    if (t->kind==TY_FLOAT && t->bits==32) { *out=IR_F32; return true; }
    return false;
}
static bool admitted_type(Lower *l,Type *t,IrType *out,Span at) {
    if (scalar(t,out)) return true;
    if (!t || (t->kind!=TY_ARRAY && (t->kind!=TY_STRUCT || !t->decl || t->decl->kind!=IT_STRUCT || t->decl->strukt.generics.len))) return false;
    for (uint32_t n=0;n<l->ir->aggregates.len;n++) if (l->types[n]==t) { *out=IR_FIRST_AGGREGATE+n; return true; }
    if (l->type_depth>=IR_MAX_DEPTH || l->ir->aggregates.len>=IR_MAX_TYPES) return false;
    if (t->kind==TY_ARRAY) {
        if (t->array_len>IR_MAX_CELLS) return false;
        IrType elem; l->type_depth++;
        bool ok=admitted_type(l,t->elem,&elem,at); l->type_depth--;
        if (!ok || elem==IR_VOID || l->ir->aggregates.len>=IR_MAX_TYPES) return false;
        uint32_t size=ir_type_cells(l->ir,elem), count=(uint32_t)t->array_len;
        if (!size || (count && size>IR_MAX_CELLS/count)) return false;
        for (uint32_t n=0;n<l->ir->aggregates.len;n++) {
            IrAggregate *existing=&l->ir->aggregates.data[n];
            if (existing->kind==IR_TYPE_ARRAY && existing->element==elem && existing->length==count) { *out=IR_FIRST_AGGREGATE+n; return true; }
        }
        uint32_t id=l->ir->aggregates.len;
        IrAggregate array={.kind=IR_TYPE_ARRAY,.declaration=at,.fields_start=l->ir->fields.len,
            .cells=count?count*size:1,.element=elem,.length=count};
        l->types[id]=t; vec_push(l->a,l->ir->aggregates,array); *out=IR_FIRST_AGGREGATE+id; return true;
    }
    Item *item=t->decl; uint32_t n=item->strukt.fields.len;
    if (!n || n>IR_MAX_CELLS || n>IR_MAX_FIELDS-l->ir->fields.len) return false;
    IrType types[IR_MAX_CELLS]; uint32_t cells=0; l->type_depth++;
    for (uint32_t f=0;f<n;f++) {
        if (!admitted_type(l,item->strukt.fields.data[f].rtype,&types[f],item->strukt.fields.data[f].span) || types[f]==IR_VOID) { l->type_depth--; return false; }
        uint32_t size=ir_type_cells(l->ir,types[f]);
        if (size>IR_MAX_CELLS-cells) { l->type_depth--; return false; } cells+=size;
    }
    l->type_depth--;
    if (l->ir->aggregates.len>=IR_MAX_TYPES || n>IR_MAX_FIELDS-l->ir->fields.len) return false;
    uint32_t id=l->ir->aggregates.len, offset=0;
    IrAggregate record={.identity=str_dup(l->a,item->qual_name),.declaration=item->span,.fields_start=l->ir->fields.len,.fields_count=n,.cells=cells};
    for (uint32_t f=0;f<n;f++) {
        Field *field=&item->strukt.fields.data[f];
        IrField copied={.type=types[f],.identity=str_dup(l->a,field->name),.declaration=field->span,.offset=offset};
        vec_push(l->a,l->ir->fields,copied); offset+=ir_type_cells(l->ir,types[f]);
    }
    l->types[id]=t; vec_push(l->a,l->ir->aggregates,record); *out=IR_FIRST_AGGREGATE+id; return true;
}
static bool is_place(Expr *e) {
    return e && (((e->kind==EX_PATH || e->kind==EX_SELF) && e->res_kind==RES_LOCAL) ||
        (e->kind==EX_FIELD && e->res_kind==RES_FIELD && is_place(e->field.base)) ||
        (e->kind==EX_INDEX && is_place(e->index.base)));
}
static IrSource origin(Span s) { return (IrSource){.origin=s}; }
static uint32_t region_new(Lower *l,IrRegionKind kind,uint32_t parent,Span at) {
    if (!bounded(l,l->ir->regions.len,IR_MAX_REGIONS,at)) return IR_NONE;
    uint32_t id=l->ir->regions.len;
    IrRegion r={.function=l->function,.parent_instruction=parent,.first=IR_NONE,.last=IR_NONE,.kind=kind,.source=at};
    vec_push(l->a,l->ir->regions,r); return id;
}
static uint32_t emit(Lower *l,IrOp op,IrType type,IrSource source) {
    if (l->failed || !bounded(l,l->ir->instructions.len,IR_MAX_INSTRUCTIONS,source.origin)) return IR_NONE;
    uint32_t id=l->ir->instructions.len;
    IrInstruction i={.op=op,.source=source,.region=l->region,.next=IR_NONE,.result=IR_NONE,
        .a=IR_NONE,.b=IR_NONE,.place=IR_NONE,.function=IR_NONE,.child={IR_NONE,IR_NONE,IR_NONE}};
    if (type!=IR_VOID) {
        if (!bounded(l,l->ir->values.len,IR_MAX_VALUES,source.origin)) return IR_NONE;
        i.result=l->ir->values.len;
        IrValue v={.type=type,.function=l->function,.definition=id}; vec_push(l->a,l->ir->values,v);
    }
    vec_push(l->a,l->ir->instructions,i);
    IrRegion *r=&l->ir->regions.data[l->region];
    if (r->last!=IR_NONE) l->ir->instructions.data[r->last].next=id; else r->first=id;
    r->last=id; return id;
}
static uint32_t value_of(Lower *l,uint32_t id) { return id==IR_NONE?IR_NONE:l->ir->instructions.data[id].result; }
static uint32_t constant(Lower *l,IrType t,int32_t n,IrSource s) {
    uint32_t id=emit(l,IR_CONST,t,s); if (id!=IR_NONE) l->ir->instructions.data[id].immediate=n;
    return value_of(l,id);
}
static uint32_t float_constant(Lower *l,float n,IrSource s) {
    if (!isfinite(n)) { unavailable(l,s.origin,"nonfinite floating constants"); return IR_NONE; }
    _Static_assert(sizeof(float)==sizeof(uint32_t),"IR requires binary32 storage");
    uint32_t id=emit(l,IR_CONST,IR_F32,s);
    if (id!=IR_NONE) memcpy(&l->ir->instructions.data[id].float_bits,&n,sizeof n);
    return value_of(l,id);
}
static uint32_t fresh_place(Lower *l,IrType t,Span at) {
    if (!bounded(l,l->ir->places.len,IR_MAX_PLACES,at)) return IR_NONE;
    uint32_t id=l->ir->places.len;
    IrPlace p={.type=t,.function=l->function,.source_local=IR_NONE,.declaration=at,.mutable=true,.synthetic=true,.parent=IR_NONE,.field=IR_NONE,.definition=IR_NONE};
    vec_push(l->a,l->ir->places,p); return id;
}
static uint32_t expression(Lower *l,Expr *e);
static uint32_t local_place(Lower *l,Expr *e) {
    if (e && (e->kind==EX_PATH || e->kind==EX_SELF) && e->res_kind==RES_LOCAL && e->res) {
        Local *v=e->res;
        if (v->id<l->item->nlocals && ((Local **)l->item->locals)[v->id]==v)
            return l->ir->functions.data[l->function].places_start+v->id;
    }
    if (e && e->kind==EX_FIELD && e->res_kind==RES_FIELD && e->res) {
        uint32_t parent=local_place(l,e->field.base); if (l->failed) return IR_NONE;
        IrType t=l->ir->places.data[parent].type;
        if (t<IR_FIRST_AGGREGATE || t-IR_FIRST_AGGREGATE>=l->ir->aggregates.len || l->ir->aggregates.data[t-IR_FIRST_AGGREGATE].kind!=IR_TYPE_RECORD) { unavailable(l,e->span,"a non-record field place"); return IR_NONE; }
        IrAggregate *record=&l->ir->aggregates.data[t-IR_FIRST_AGGREGATE]; Field *field=e->res;
        if (field->index>=record->fields_count) { unavailable(l,e->span,"unresolved field identity"); return IR_NONE; }
        uint32_t fi=record->fields_start+field->index;
        for (uint32_t p=l->ir->functions.data[l->function].places_start;p<l->ir->places.len;p++)
            if (l->ir->places.data[p].parent==parent && l->ir->places.data[p].field==fi) return p;
        if (!bounded(l,l->ir->places.len,IR_MAX_PLACES,e->span)) return IR_NONE;
        uint32_t id=l->ir->places.len;
        IrPlace place={.type=l->ir->fields.data[fi].type,.function=l->function,.source_local=IR_NONE,.declaration=e->span,
            .mutable=l->ir->places.data[parent].mutable,.synthetic=true,.parent=parent,.field=fi,.definition=IR_NONE};
        vec_push(l->a,l->ir->places,place); return id;
    }
    if (e && e->kind==EX_INDEX) {
        uint32_t parent=local_place(l,e->index.base); if (l->failed) return IR_NONE;
        IrType type=l->ir->places.data[parent].type;
        if (type<IR_FIRST_AGGREGATE || l->ir->aggregates.data[type-IR_FIRST_AGGREGATE].kind!=IR_TYPE_ARRAY) { unavailable(l,e->span,"a non-array index place"); return IR_NONE; }
        IrType element=l->ir->aggregates.data[type-IR_FIRST_AGGREGATE].element;
        IrSource source={.origin=e->span,.has_expansion=e->has_expansion_site,.expansion=e->expansion_site};
        uint32_t capture=emit(l,IR_INDEX_BASE,IR_VOID,source);
        if (capture!=IR_NONE) { l->ir->instructions.data[capture].place=parent; l->ir->instructions.data[capture].effects=IR_READ; }
        uint32_t index=expression(l,e->index.index);
        if (l->failed || !bounded(l,l->ir->places.len,IR_MAX_PLACES,e->span)) return IR_NONE;
        uint32_t result=l->ir->places.len;
        IrPlace place={.type=element,.function=l->function,.source_local=IR_NONE,.declaration=e->span,
            .mutable=l->ir->places.data[parent].mutable,.synthetic=true,.parent=parent,.field=IR_NONE,.definition=IR_NONE};
        vec_push(l->a,l->ir->places,place);
        uint32_t id=emit(l,IR_INDEX_PLACE,IR_VOID,source);
        if (id!=IR_NONE) {
            IrInstruction *inst=&l->ir->instructions.data[id]; inst->place=result; inst->a=index; inst->b=capture;
            inst->effects=IR_READ|IR_FAILURE; l->ir->places.data[result].definition=id;
        }
        return result;
    }
    unavailable(l,e?e->span:l->item->span,"a place other than a resolved local, record field or fixed-array element"); return IR_NONE;
}
static uint32_t declaration(Lower *l,Str name,Span s) {
    for (uint32_t i=0;i<l->item->nlocals;i++) {
        Local *v=((Local **)l->item->locals)[i];
        if (v->id==i && v->span.file==s.file && v->span.offset==s.offset && str_eq(v->name,name))
            return l->ir->functions.data[l->function].places_start+i;
    }
    unavailable(l,s,"a declaration without resolved local identity"); return IR_NONE;
}
static uint32_t load(Lower *l,uint32_t place,IrSource s) {
    if (l->failed || place>=l->ir->places.len) return IR_NONE;
    uint32_t id=emit(l,IR_LOAD,l->ir->places.data[place].type,s);
    if (id!=IR_NONE) { l->ir->instructions.data[id].place=place; l->ir->instructions.data[id].effects=IR_READ; }
    return value_of(l,id);
}
static uint32_t store(Lower *l,uint32_t place,uint32_t value,bool init,IrSource s) {
    uint32_t id=emit(l,init?IR_INIT:IR_STORE,IR_VOID,s);
    if (id!=IR_NONE) { IrInstruction *i=&l->ir->instructions.data[id]; i->place=place; i->a=value; i->effects=IR_WRITE; }
    return id;
}
static bool numeric(TokKind t,IrNumeric *op) {
    switch (t) {
        case TK_PLUS: *op=IR_ADD; break; case TK_MINUS: *op=IR_SUB; break;
        case TK_STAR: *op=IR_MUL; break; case TK_SLASH: *op=IR_DIV; break; case TK_PERCENT: *op=IR_REM; break;
        case TK_AMP: *op=IR_BIT_AND; break; case TK_PIPE: *op=IR_BIT_OR; break; case TK_CARET: *op=IR_BIT_XOR; break;
        case TK_EQ: *op=IR_EQ; break; case TK_NE: *op=IR_NE; break; case TK_LT: *op=IR_LT; break;
        case TK_LE: *op=IR_LE; break; case TK_GT: *op=IR_GT; break; case TK_GE: *op=IR_GE; break;
        case TK_SHL: *op=IR_SHL; break; case TK_SHR: *op=IR_SHR; break;
        default: return false;
    }
    return true;
}
static uint32_t binary(Lower *l,IrNumeric op,uint32_t a,uint32_t b,IrType t,IrSource s) {
    uint32_t id=emit(l,IR_BINARY,t,s);
    if (id!=IR_NONE) {
        IrInstruction *i=&l->ir->instructions.data[id]; i->numeric=op; i->a=a; i->b=b;
        i->effects=(op>=IR_ADD && op<=IR_REM) || op==IR_SHL || op==IR_SHR?IR_FAILURE:0;
    }
    return value_of(l,id);
}
static uint32_t expression(Lower *l,Expr *e);
static void statement(Lower *l,Stmt *s);
static bool intrinsic(Intrinsic id,IrIntrinsic *result) {
    switch (id) {
        case INTR_MIN: *result=IR_MIN; break; case INTR_MAX: *result=IR_MAX; break;
        case INTR_ABS: *result=IR_ABS; break; case INTR_CLAMP: *result=IR_CLAMP; break;
        case INTR_WRAPPING_ADD: *result=IR_WRAP_ADD; break; case INTR_WRAPPING_SUB: *result=IR_WRAP_SUB; break;
        case INTR_WRAPPING_MUL: *result=IR_WRAP_MUL; break; case INTR_SATURATING_ADD: *result=IR_SAT_ADD; break;
        case INTR_SATURATING_SUB: *result=IR_SAT_SUB; break; default: return false;
    }
    return true;
}
/* Admission visits dead expressions too. Unreachable pruning is a lowering
 * choice, never a way to advertise unsupported syntax as part of this subset. */
static void admit_expression(Lower *l,Expr *e);
static void admit_statement(Lower *l,Stmt *s) {
    if (!s || l->failed) return;
    switch (s->kind) {
        case ST_LET:
            if (!s->let.init) unavailable(l,s->span,"an uninitialized local");
            admit_expression(l,s->let.init); break;
        case ST_EXPR: case ST_RETURN: case ST_DEFER: admit_expression(l,s->expr); break;
        case ST_ASSIGN:
            if (!is_place(s->assign.target))
                unavailable(l,s->span,"an assignment place other than a local scalar");
            admit_expression(l,s->assign.target); admit_expression(l,s->assign.value); break;
        case ST_WHILE: admit_expression(l,s->while_st.cond); admit_expression(l,s->while_st.body); break;
        case ST_FOR:
            if (s->for_st.iter && s->for_st.iter->kind==EX_RANGE) {
                admit_expression(l,s->for_st.iter->range.lo); admit_expression(l,s->for_st.iter->range.hi);
            } else if (s->for_st.iter && s->for_st.iter->type && s->for_st.iter->type->kind==TY_ARRAY)
                admit_expression(l,s->for_st.iter);
            else unavailable(l,s->span,"iteration other than an exclusive i32 range or fixed array");
            admit_expression(l,s->for_st.body); break;
        case ST_BREAK: case ST_CONTINUE: break;
    }
}
static void admit_expression(Lower *l,Expr *e) {
    if (!e || l->failed) return;
    IrType type;
    if (l->depth>=IR_MAX_DEPTH || l->work++>=100000) { unavailable(l,e->span,"the nesting or admission-work quota"); return; }
    if (!admitted_type(l,e->type,&type,e->span)) { unavailable(l,e->span,"this expression type"); return; }
    l->depth++;
    switch (e->kind) {
        case EX_INT: case EX_FLOAT: case EX_BOOL: break;
        case EX_SELF: case EX_PATH:
            if (e->res_kind!=RES_LOCAL && e->res_kind!=RES_CONST) unavailable(l,e->span,"this path");
            break;
        case EX_UNARY:
            if (e->unary.op!=TK_PLUS && e->unary.op!=TK_MINUS && e->unary.op!=TK_BANG && e->unary.op!=TK_TILDE)
                unavailable(l,e->span,"this unary operation");
            admit_expression(l,e->unary.operand); break;
        case EX_BINARY: {
            IrNumeric op;
            IrType operand_type;
            if (!scalar(e->binary.lhs->type,&operand_type) || operand_type==IR_VOID)
                unavailable(l,e->span,"aggregate comparison or arithmetic");
            if (e->binary.op!=TK_ANDAND && e->binary.op!=TK_OROR && !numeric(e->binary.op,&op))
                unavailable(l,e->span,"this binary operation");
            admit_expression(l,e->binary.lhs); admit_expression(l,e->binary.rhs); break;
        }
        case EX_CALL: {
            IrIntrinsic in;
            if (e->res_kind!=RES_FN && !(e->res_kind==RES_INTRINSIC &&
                (e->intrinsic==INTR_PRINT || e->intrinsic==INTR_PRINTLN || e->intrinsic==INTR_ASSERT || intrinsic((Intrinsic)e->intrinsic,&in))))
                unavailable(l,e->span,"this intrinsic or indirect call");
            if (e->res_kind==RES_FN) {
                Item *callee=e->res;
                if (callee->fn.params.len && callee->fn.params.data[0].is_self) {
                    if (e->call.callee->kind!=EX_FIELD) unavailable(l,e->span,"an unresolved method receiver");
                    else admit_expression(l,e->call.callee->field.base);
                }
            }
            if (e->call.args.len>IR_MAX_CALL_ARGUMENTS) unavailable(l,e->span,"more than 256 call arguments");
            for (uint32_t a=0;a<e->call.args.len && !l->failed;a++) {
                IrType actual; Arg *arg=&e->call.args.data[a];
                if ((arg->conv!=CONV_LET && arg->conv!=CONV_INOUT) || !admitted_type(l,arg->value->type,&actual,arg->span) || actual==IR_VOID)
                    unavailable(l,arg->span,"this call argument type or mode");
                else if (e->res_kind==RES_INTRINSIC && actual>=IR_FIRST_AGGREGATE)
                    unavailable(l,arg->span,"aggregate observations or numeric intrinsic arguments");
                admit_expression(l,arg->value);
            }
            break;
        }
        case EX_FIELD:
            if (e->res_kind!=RES_FIELD) unavailable(l,e->span,"non-record field expressions");
            admit_expression(l,e->field.base); break;
        case EX_STRUCT_LIT:
            for (uint32_t f=0;f<e->struct_lit.fields.len;f++) admit_expression(l,e->struct_lit.fields.data[f].value);
            break;
        case EX_ARRAY_LIT:
            for (uint32_t a=0;a<e->array_lit.elems.len;a++) admit_expression(l,e->array_lit.elems.data[a]);
            break;
        case EX_INDEX:
            if (!e->index.base->type || e->index.base->type->kind!=TY_ARRAY)
                unavailable(l,e->span,"an index outside a fixed array");
            admit_expression(l,e->index.base); admit_expression(l,e->index.index); break;
        case EX_CAST: admit_expression(l,e->cast.value); break;
        case EX_BLOCK:
            for (uint32_t i=0;i<e->block.stmts.len && !l->failed;i++) admit_statement(l,e->block.stmts.data[i]);
            break;
        case EX_IF:
            admit_expression(l,e->if_expr.cond); admit_expression(l,e->if_expr.then_blk); admit_expression(l,e->if_expr.else_blk); break;
        default: unavailable(l,e->span,"this expression form"); break;
    }
    l->depth--;
}
static uint32_t region_effects(Lower *l,uint32_t region) {
    uint32_t effects=0;
    if (region!=IR_NONE) for (uint32_t i=l->ir->regions.data[region].first;i!=IR_NONE;i=l->ir->instructions.data[i].next)
        effects|=l->ir->instructions.data[i].effects;
    return effects;
}
static bool falls_through(Lower *l,uint32_t r) {
    if (r==IR_NONE || l->ir->regions.data[r].last==IR_NONE) return true;
    IrInstruction *i=&l->ir->instructions.data[l->ir->regions.data[r].last];
    if (i->op==IR_RETURN || i->op==IR_BREAK || i->op==IR_CONTINUE || i->op==IR_YIELD) return false;
    if (i->op==IR_IF) return falls_through(l,i->child[0]) || falls_through(l,i->child[1]);
    return true;
}
static uint32_t branch(Lower *l,uint32_t owner,Expr *e) {
    uint32_t saved=l->region, r=region_new(l,IR_REGION_BRANCH,owner,e?e->span:l->item->span);
    if (r!=IR_NONE) { l->region=r; if (e) expression(l,e); l->region=saved; }
    return r;
}
static IrArgument argument(Lower *l,Expr *e,Conv mode,Span at) {
    IrArgument arg={.value=IR_NONE,.source=at,.mode=mode==CONV_INOUT?IR_INOUT:IR_LET,.capture=IR_NONE};
    IrType type;
    if (!admitted_type(l,e->type,&type,at) || type==IR_VOID || (mode!=CONV_LET && mode!=CONV_INOUT)) { unavailable(l,at,"this argument type or mode"); return arg; }
    if (mode==CONV_INOUT || (type>=IR_FIRST_AGGREGATE && is_place(e))) {
        uint32_t place=local_place(l,e), id=emit(l,IR_CAPTURE,IR_VOID,origin(at));
        if (id!=IR_NONE) { l->ir->instructions.data[id].place=place; l->ir->instructions.data[id].effects=IR_READ; l->ir->instructions.data[id].flag=mode==CONV_INOUT; }
        arg.by_place=true; arg.capture=id;
    } else arg.value=expression(l,e);
    return arg;
}
static uint32_t call(Lower *l,Expr *e,IrType type,IrSource s) {
    uint32_t n=e->call.args.len, target=IR_NONE, self=0; Item *callee=NULL;
    IrOp op=IR_CALL; IrIntrinsic selected=IR_MIN;
    if (e->res_kind==RES_FN) {
        callee=e->res;
        for (uint32_t f=0;f<l->ir->functions.len;f++) if (l->items[f]==callee && !l->ir->functions.data[f].test) target=f;
        if (target==IR_NONE) { unavailable(l,e->span,"this call target"); return IR_NONE; }
        self=callee->fn.params.len && callee->fn.params.data[0].is_self;
    } else if (e->res_kind==RES_INTRINSIC && (e->intrinsic==INTR_PRINT || e->intrinsic==INTR_PRINTLN || e->intrinsic==INTR_ASSERT))
        op=e->intrinsic==INTR_ASSERT?IR_ASSERT:IR_PRINT;
    else if (e->res_kind==RES_INTRINSIC && intrinsic((Intrinsic)e->intrinsic,&selected)) op=IR_INTRINSIC;
    else { unavailable(l,e->span,"this intrinsic or indirect call"); return IR_NONE; }
    if (n+ self>IR_MAX_CALL_ARGUMENTS || (callee && n+self!=callee->fn.params.len)) { unavailable(l,e->span,"unexpanded defaults or call arity"); return IR_NONE; }
    IrArgument args[IR_MAX_CALL_ARGUMENTS];
    if (self) args[0]=argument(l,e->call.callee->field.base,callee->fn.params.data[0].conv,e->call.callee->field.base->span);
    for (uint32_t a=0;a<n && !l->failed;a++) args[a+self]=argument(l,e->call.args.data[a].value,e->call.args.data[a].conv,e->call.args.data[a].value->span);
    n+=self;
    if (l->failed || n>IR_MAX_ARGUMENTS-l->ir->arguments.len) { if (!l->failed) unavailable(l,e->span,"the argument-table quota"); return IR_NONE; }
    uint32_t start=l->ir->arguments.len;
    for (uint32_t a=0;a<n;a++) vec_push(l->a,l->ir->arguments,args[a]);
    uint32_t id=emit(l,op,type,s);
    if (id!=IR_NONE) {
        IrInstruction *i=&l->ir->instructions.data[id]; i->function=target; i->args_start=start; i->args_count=n;
        i->flag=e->intrinsic==INTR_PRINTLN; i->effects=op==IR_CALL?IR_ALL_EFFECTS:IR_OBSERVE|IR_FAILURE;
        if (op==IR_INTRINSIC) { i->intrinsic=selected; i->effects=IR_FAILURE; }
    }
    return value_of(l,id);
}
static uint32_t expression(Lower *l,Expr *e) {
    if (!e || l->failed) return IR_NONE;
    if (l->depth>=IR_MAX_DEPTH || l->work++>=100000) { unavailable(l,e->span,"the nesting or admission-work quota"); return IR_NONE; }
    IrType t;
    if (!admitted_type(l,e->type,&t,e->span)) { unavailable(l,e->span,"this expression type"); return IR_NONE; }
    IrSource s={.origin=e->span,.has_expansion=e->has_expansion_site,.expansion=e->expansion_site};
    uint32_t result=IR_NONE; l->depth++;
    switch (e->kind) {
        case EX_INT:
            if (t==IR_F32) result=float_constant(l,(float)e->int_lit.val,s);
            else if (e->int_lit.val>INT32_MAX) unavailable(l,e->span,"an out-of-range positive i32 literal");
            else result=constant(l,IR_I32,(int32_t)e->int_lit.val,s);
            break;
        case EX_FLOAT: result=float_constant(l,(float)e->float_lit.val,s); break;
        case EX_BOOL: result=constant(l,IR_BOOL,e->bool_lit,s); break;
        case EX_SELF: case EX_PATH:
            if (e->res_kind==RES_CONST) result=expression(l,((Item *)e->res)->konst.value);
            else result=load(l,local_place(l,e),s);
            break;
        case EX_UNARY: {
            if (t==IR_I32 && e->unary.op==TK_MINUS && e->unary.operand->kind==EX_INT && e->unary.operand->int_lit.val==UINT64_C(2147483648)) {
                result=constant(l,IR_I32,INT32_MIN,s); break;
            }
            uint32_t a=expression(l,e->unary.operand);
            if (e->unary.op==TK_PLUS) { result=a; break; }
            IrNumeric op=e->unary.op==TK_MINUS?IR_NEG:e->unary.op==TK_BANG?IR_NOT:IR_BIT_NOT;
            if (e->unary.op!=TK_MINUS && e->unary.op!=TK_BANG && e->unary.op!=TK_TILDE) { unavailable(l,e->span,"this unary operation"); break; }
            uint32_t id=emit(l,IR_UNARY,t,s);
            if (id!=IR_NONE) { IrInstruction *i=&l->ir->instructions.data[id]; i->a=a; i->numeric=op; i->effects=op==IR_NEG?IR_FAILURE:0; }
            result=value_of(l,id); break;
        }
        case EX_BINARY: {
            uint32_t a=expression(l,e->binary.lhs);
            if (e->binary.op==TK_ANDAND || e->binary.op==TK_OROR) {
                uint32_t place=fresh_place(l,IR_BOOL,e->span), id=emit(l,IR_IF,IR_VOID,s), saved=l->region;
                if (id==IR_NONE) break;
                uint32_t children[2];
                for (uint32_t c=0;c<2;c++) {
                    children[c]=region_new(l,IR_REGION_BRANCH,id,e->span); if (children[c]==IR_NONE) break;
                    l->region=children[c];
                    bool evaluate=e->binary.op==TK_ANDAND ? c==0 : c==1;
                    uint32_t v=evaluate?expression(l,e->binary.rhs):constant(l,IR_BOOL,c==0,s);
                    store(l,place,v,true,s);
                }
                l->region=saved;
                if (l->failed) break;
                IrInstruction *i=&l->ir->instructions.data[id]; i->a=a; i->child[0]=children[0]; i->child[1]=children[1];
                i->effects=region_effects(l,children[0])|region_effects(l,children[1]);
                result=load(l,place,s);
            } else {
                uint32_t b=expression(l,e->binary.rhs); IrNumeric op;
                if (!numeric(e->binary.op,&op)) unavailable(l,e->span,"this binary operation");
                else result=binary(l,op,a,b,t,s);
            }
            break;
        }
        case EX_FIELD:
            if (is_place(e)) result=load(l,local_place(l,e),s);
            else {
                uint32_t base=expression(l,e->field.base); IrType base_type;
                if (!admitted_type(l,e->field.base->type,&base_type,e->field.base->span) || base_type<IR_FIRST_AGGREGATE || e->res_kind!=RES_FIELD || l->ir->aggregates.data[base_type-IR_FIRST_AGGREGATE].kind!=IR_TYPE_RECORD) { unavailable(l,e->span,"this field projection"); break; }
                uint32_t field=l->ir->aggregates.data[base_type-IR_FIRST_AGGREGATE].fields_start+((Field *)e->res)->index;
                uint32_t id=emit(l,IR_FIELD,t,s);
                if (id!=IR_NONE) { l->ir->instructions.data[id].a=base; l->ir->instructions.data[id].place=field; }
                result=value_of(l,id);
            }
            break;
        case EX_INDEX:
            if (is_place(e)) result=load(l,local_place(l,e),s);
            else {
                uint32_t base=expression(l,e->index.base), index=expression(l,e->index.index);
                uint32_t id=emit(l,IR_INDEX_VALUE,t,s);
                if (id!=IR_NONE) { l->ir->instructions.data[id].a=base; l->ir->instructions.data[id].b=index; l->ir->instructions.data[id].effects=IR_FAILURE; }
                result=value_of(l,id);
            }
            break;
        case EX_ARRAY_LIT: {
            uint32_t n=e->array_lit.elems.len;
            if (n>IR_MAX_CALL_ARGUMENTS) { unavailable(l,e->span,"array construction beyond its bounded arity"); break; }
            IrArgument args[IR_MAX_CALL_ARGUMENTS];
            for (uint32_t a=0;a<n && !l->failed;a++)
                args[a]=(IrArgument){.value=expression(l,e->array_lit.elems.data[a]),.source=e->array_lit.elems.data[a]->span,.field=a};
            if (l->failed || n>IR_MAX_ARGUMENTS-l->ir->arguments.len) { if (!l->failed) unavailable(l,e->span,"the argument-table quota"); break; }
            uint32_t start=l->ir->arguments.len;
            for (uint32_t a=0;a<n;a++) vec_push(l->a,l->ir->arguments,args[a]);
            uint32_t id=emit(l,IR_ARRAY,t,s);
            if (id!=IR_NONE) { l->ir->instructions.data[id].args_start=start; l->ir->instructions.data[id].args_count=n; }
            result=value_of(l,id); break;
        }
        case EX_STRUCT_LIT: {
            IrAggregate *record=&l->ir->aggregates.data[t-IR_FIRST_AGGREGATE]; uint32_t n=e->struct_lit.fields.len;
            if (n!=record->fields_count || n>IR_MAX_CALL_ARGUMENTS) { unavailable(l,e->span,"an incomplete record literal"); break; }
            IrArgument args[IR_MAX_CALL_ARGUMENTS];
            for (uint32_t f=0;f<n;f++) {
                FieldInit *field=&e->struct_lit.fields.data[f]; uint32_t slot=IR_NONE;
                for (uint32_t k=0;k<n;k++) if (str_eq(field->name,l->ir->fields.data[record->fields_start+k].identity)) slot=record->fields_start+k;
                if (slot==IR_NONE) { unavailable(l,field->span,"a record field identity"); break; }
                args[f]=(IrArgument){.value=expression(l,field->value),.source=field->value->span,.field=slot};
            }
            if (l->failed || n>IR_MAX_ARGUMENTS-l->ir->arguments.len) { if (!l->failed) unavailable(l,e->span,"the argument-table quota"); break; }
            uint32_t start=l->ir->arguments.len;
            for (uint32_t f=0;f<n;f++) vec_push(l->a,l->ir->arguments,args[f]);
            uint32_t id=emit(l,IR_RECORD,t,s);
            if (id!=IR_NONE) { l->ir->instructions.data[id].args_start=start; l->ir->instructions.data[id].args_count=n; }
            result=value_of(l,id); break;
        }
        case EX_CALL: result=call(l,e,t,s); break;
        case EX_CAST: {
            uint32_t a=expression(l,e->cast.value), id=emit(l,IR_CAST,t,s);
            if (id!=IR_NONE) { l->ir->instructions.data[id].a=a; l->ir->instructions.data[id].effects=IR_FAILURE; }
            result=value_of(l,id); break;
        }
        case EX_BLOCK:
            for (uint32_t i=0;i<e->block.stmts.len && !l->failed && falls_through(l,l->region);i++) statement(l,e->block.stmts.data[i]);
            break;
        case EX_IF: {
            uint32_t a=expression(l,e->if_expr.cond), id=emit(l,IR_IF,IR_VOID,s);
            if (id==IR_NONE) break;
            uint32_t yes=branch(l,id,e->if_expr.then_blk), no=branch(l,id,e->if_expr.else_blk);
            if (!l->failed) {
                IrInstruction *i=&l->ir->instructions.data[id]; i->a=a; i->child[0]=yes; i->child[1]=no;
                i->effects=region_effects(l,yes)|region_effects(l,no);
            }
            break;
        }
        default: unavailable(l,e->span,"this expression form"); break;
    }
    l->depth--; return result;
}
static void loop(Lower *l,Stmt *s,bool for_loop) {
    IrSource src=origin(s->span); uint32_t lo=IR_NONE, hi=IR_NONE, counter=IR_NONE, binding=IR_NONE;
    uint32_t snapshot=IR_NONE; bool range=for_loop && s->for_st.iter->kind==EX_RANGE;
    if (for_loop) {
        Expr *iter=s->for_st.iter;
        if (range) { lo=expression(l,iter->range.lo); hi=expression(l,iter->range.hi); }
        else {
            snapshot=expression(l,iter);
            lo=constant(l,IR_I32,0,src); hi=constant(l,IR_I32,(int32_t)iter->type->array_len,src);
        }
        counter=fresh_place(l,IR_I32,s->span); binding=declaration(l,s->for_st.var,s->span); store(l,counter,lo,true,src);
    }
    uint32_t id=emit(l,IR_LOOP,IR_VOID,src), saved=l->region; if (id==IR_NONE) return;
    uint32_t children[3];
    children[0]=region_new(l,IR_REGION_CONDITION,id,s->span);
    children[1]=region_new(l,IR_REGION_BRANCH,id,s->span);
    children[2]=region_new(l,IR_REGION_STEP,id,s->span);
    if (l->failed) return;
    l->region=children[0];
    uint32_t condition;
    if (for_loop) { uint32_t current=load(l,counter,src); condition=binary(l,IR_LT,current,hi,IR_BOOL,src); }
    else condition=expression(l,s->while_st.cond);
    uint32_t yield=emit(l,IR_YIELD,IR_VOID,src);
    if (yield!=IR_NONE) { l->ir->instructions.data[yield].a=condition; l->ir->instructions.data[yield].effects=IR_EXIT; }
    l->region=children[1];
    if (for_loop) {
        uint32_t current=load(l,counter,src), value=current;
        if (!range && !l->failed) {
            IrSource synthetic=src; synthetic.synthetic=true;
            uint32_t get=emit(l,IR_INDEX_VALUE,l->ir->places.data[binding].type,synthetic);
            if (get!=IR_NONE) { l->ir->instructions.data[get].a=snapshot; l->ir->instructions.data[get].b=current; l->ir->instructions.data[get].effects=IR_FAILURE; }
            value=value_of(l,get);
        }
        store(l,binding,value,true,src);
    }
    expression(l,for_loop?s->for_st.body:s->while_st.body);
    l->region=children[2];
    if (for_loop) {
        IrSource synthetic=src; synthetic.synthetic=true;
        uint32_t old=load(l,counter,synthetic), one=constant(l,IR_I32,1,synthetic);
        uint32_t next=binary(l,IR_ADD,old,one,IR_I32,synthetic); store(l,counter,next,false,synthetic);
    }
    l->region=saved;
    if (!l->failed) {
        IrInstruction *i=&l->ir->instructions.data[id];
        for (uint32_t c=0;c<3;c++) { i->child[c]=children[c]; i->effects|=region_effects(l,children[c]); }
    }
}
static void statement(Lower *l,Stmt *s) {
    if (!s || l->failed) return;
    IrSource src=origin(s->span);
    switch (s->kind) {
        case ST_LET: {
            if (!s->let.init) { unavailable(l,s->span,"an uninitialized local"); break; }
            uint32_t p=declaration(l,s->let.name,s->span), v=expression(l,s->let.init); store(l,p,v,true,src); break;
        }
        case ST_EXPR: case ST_DEFER: expression(l,s->expr); break; /* current immediate semantics */
        case ST_ASSIGN: {
            uint32_t p=local_place(l,s->assign.target), old=IR_NONE, destination=IR_NONE;
            if (!l->failed && l->ir->places.data[p].parent!=IR_NONE) {
                destination=emit(l,IR_DESTINATION,IR_VOID,src);
                if (destination!=IR_NONE) { l->ir->instructions.data[destination].place=p; l->ir->instructions.data[destination].effects=IR_READ; }
            }
            if (s->assign.op!=TK_ASSIGN) old=load(l,p,src); /* before RHS evaluation */
            uint32_t rhs=expression(l,s->assign.value);
            if (s->assign.op!=TK_ASSIGN) {
                IrNumeric op=s->assign.op==TK_PLUSEQ?IR_ADD:s->assign.op==TK_MINUSEQ?IR_SUB:s->assign.op==TK_STAREQ?IR_MUL:s->assign.op==TK_SLASHEQ?IR_DIV:IR_REM;
                IrType type=IR_I32; admitted_type(l,s->assign.target->type,&type,s->assign.target->span);
                rhs=binary(l,op,old,rhs,type,src);
            }
            uint32_t write=store(l,p,rhs,false,src);
            if (write!=IR_NONE) l->ir->instructions.data[write].b=destination;
            break;
        }
        case ST_RETURN: {
            uint32_t v=s->expr?expression(l,s->expr):IR_NONE, id=emit(l,IR_RETURN,IR_VOID,src);
            if (id!=IR_NONE) { l->ir->instructions.data[id].a=v; l->ir->instructions.data[id].effects=IR_EXIT; }
            break;
        }
        case ST_BREAK: case ST_CONTINUE: {
            uint32_t id=emit(l,s->kind==ST_BREAK?IR_BREAK:IR_CONTINUE,IR_VOID,src);
            if (id!=IR_NONE) l->ir->instructions.data[id].effects=IR_EXIT;
            break;
        }
        case ST_WHILE: loop(l,s,false); break;
        case ST_FOR: loop(l,s,true); break;
    }
}
IrProgram *ir_lower(Arena *a,DiagBag *d,const SourceMap *sources,Program *program) {
    if (!a || !d || !sources || !program || diag_errors(d)) return NULL;
    IrProgram *ir=ARENA_NEW(a,IrProgram); ir->schema_version=4;
    Lower l={.a=a,.d=d,.ir=ir};
    uint32_t count=srcmap_count(sources); uint64_t source_bytes=0;
    if (!count || count>IR_MAX_SOURCE_FILES) { unavailable(&l,SPAN_NONE,"an absent or oversized source manifest"); return NULL; }
    for (uint32_t f=0;f<count;f++) {
        SourceFile *file=srcmap_get(sources,f);
        if (!file || file->id!=f || file->path.len>32768 || file->text.len>IR_MAX_SOURCE_BYTES-source_bytes) {
            unavailable(&l,SPAN_NONE,"source manifest identity or size limits"); return NULL;
        }
        source_bytes+=file->text.len;
        IrSourceFile copied={.path=str_dup(a,file->path),.text=str_dup(a,file->text),.sha256=hash256_str(a,file->text)};
        vec_push(a,ir->sources,copied);
    }
    ir->source_manifest_sha256=ir_source_manifest_hash(a,ir);
    Item *items[IR_MAX_FUNCTIONS]; l.items=items;
    for (uint32_t m=0;m<program->modules.len && !l.failed;m++) for (uint32_t n=0;n<program->modules.data[m]->items.len && !l.failed;n++) {
        Item *it=program->modules.data[m]->items.data[n]; IrType result;
        if (it->kind==IT_USE) continue;
        if (!admitted_type(&l,it->rtype,&result,it->span)) { unavailable(&l,it->span,"this declaration type"); break; }
        if (it->kind==IT_STRUCT) {
            for (uint32_t f=0;f<it->strukt.fields.len;f++) admit_expression(&l,it->strukt.fields.data[f].deflt);
            continue;
        }
        if (it->kind==IT_CONST) { admit_expression(&l,it->konst.value); continue; }
        if (it->kind!=IT_FN && it->kind!=IT_TEST) { unavailable(&l,it->span,"this declaration kind"); break; }
        if (it->kind==IT_FN && (it->fn.generics.len || !it->fn.body)) {
            unavailable(&l,it->span,"generic or external declarations"); break;
        }
        if (!bounded(&l,ir->functions.len,IR_MAX_FUNCTIONS,it->span)) break;
        if (it->kind==IT_FN) for (uint32_t p=0;p<it->fn.params.len;p++) {
            Param *pm=&it->fn.params.data[p]; IrType t;
            if ((pm->conv!=CONV_LET && pm->conv!=CONV_INOUT) || !admitted_type(&l,pm->rtype,&t,pm->span) || t==IR_VOID)
                unavailable(&l,pm->span,"parameters other than admitted let/inout types");
            admit_expression(&l,pm->deflt);
        }
        items[ir->functions.len]=it;
        IrFunction f={.identity=str_dup(a,it->qual_name),.declaration=it->span,.result=it->kind==IT_TEST?IR_VOID:result,
            .test=it->kind==IT_TEST,.body=IR_NONE,.parameters=it->kind==IT_TEST?0:it->fn.params.len};
        vec_push(a,ir->functions,f);
    }
    for (uint32_t f=0;f<ir->functions.len && !l.failed;f++)
        admit_expression(&l,items[f]->kind==IT_TEST?items[f]->test.body:items[f]->fn.body);
    for (uint32_t f=0;f<ir->functions.len && !l.failed;f++) {
        l.function=f; l.item=items[f]; IrFunction *fn=&ir->functions.data[f];
        fn->places_start=ir->places.len; fn->values_start=ir->values.len;
        for (uint32_t p=0;p<l.item->nlocals;p++) {
            Local *local=((Local **)l.item->locals)[p]; IrType t;
            if (!local || local->id!=p || !admitted_type(&l,local->type,&t,local->span) || t==IR_VOID || !bounded(&l,ir->places.len,IR_MAX_PLACES,l.item->span)) {
                if (!l.failed) unavailable(&l,l.item->span,"this local type or identity"); break;
            }
            IrPlace place={.type=t,.function=f,.source_local=p,.declaration=local->span,.parameter=local->is_param,.mutable=local->is_mut,.mode=local->is_param && l.item->fn.params.data[p].conv==CONV_INOUT?IR_INOUT:IR_LET,.parent=IR_NONE,.field=IR_NONE,.definition=IR_NONE};
            vec_push(a,ir->places,place);
        }
        if (l.failed) break;
        l.region=region_new(&l,IR_REGION_BODY,IR_NONE,l.item->span); fn->body=l.region;
        expression(&l,l.item->kind==IT_TEST?l.item->test.body:l.item->fn.body);
        if (!l.failed && fn->result==IR_VOID && falls_through(&l,l.region)) {
            uint32_t id=emit(&l,IR_RETURN,IR_VOID,origin(l.item->span)); if (id!=IR_NONE) ir->instructions.data[id].effects=IR_EXIT;
        }
        fn->places_count=ir->places.len-fn->places_start; fn->values_count=ir->values.len-fn->values_start;
    }
    if (l.failed) return NULL;
    IrVerification checked=ir_verify(ir);
    if (!checked.ok) {
        if (!strcmp(checked.reason,"write or control effect crosses projected destination") || !strcmp(checked.reason,"write or control effect crosses captured argument interval") ||
            !strcmp(checked.reason,"write or control effect crosses index base capture") || !strcmp(checked.reason,"write or control effect crosses dynamic place interval") ||
            !strcmp(checked.reason,"overlapping captured mutable arguments"))
            diag_error(d,1101,checked.source,"experimental IR rejects this alias/evaluation-order boundary: %s",checked.reason);
        else diag_error(d,1102,checked.source,"invalid experimental structured IR: %s",checked.reason);
        return NULL;
    }
    return ir;
}
