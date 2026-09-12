#include "taint.h"

#include "intrinsic.h"
#include <limits.h>
#include <string.h>

/* Bounded, monotone whole-program propagation. Field paths preserve disjoint
 * record members; indexed elements deliberately share one conservative cell.
 * This pass is a source restriction, not a backend constant-time guarantee. */
#define TAINT_MAX_PATH 24u
#define TAINT_MAX_FUNCTIONS 4096u
#define TAINT_MAX_CELLS 65536u
#define TAINT_MAX_WORK 4000000u
#define TAINT_MAX_DEPTH 192u
typedef struct { Local *root; const void *part[TAINT_MAX_PATH]; uint32_t n; bool valid; } TPath;
typedef struct { TPath path; uint8_t bits; } TCell;
typedef struct { Item *item; Expr *body; uint8_t returns; } TFunction;
typedef struct { Local *local; Item *owner; Expr *expression; } TInit;
typedef struct { bool known; int64_t lo, hi; } TRange;

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
    bool     emit, changed, exhausted;
    uint32_t work, depth;
    VEC(TCell) cells;
    VEC(TFunction) functions;
    VEC(TInit) initializers;
} T;

static bool spend(T *t) {
    if (t->exhausted) return false;
    if (++t->work > TAINT_MAX_WORK) { t->exhausted = true; return false; }
    return true;
}

static TFunction *function_of(T *t, Item *item) {
    for (uint32_t i=0;i<t->functions.len&&spend(t);i++)
        if (t->functions.data[i].item==item) return &t->functions.data[i];
    return NULL;
}

static bool path_fill(Expr *e, TPath *p, uint32_t depth) {
    if (!e || depth>TAINT_MAX_PATH) return false;
    if ((e->kind==EX_PATH || e->kind==EX_SELF) && e->res_kind==RES_LOCAL) {
        p->root=e->res; return true;
    }
    Expr *base=e->kind==EX_FIELD?e->field.base:e->kind==EX_INDEX?e->index.base:NULL;
    if (!base || !path_fill(base,p,depth+1) || p->n==TAINT_MAX_PATH) return false;
    if (e->kind==EX_INDEX) p->part[p->n++]=NULL;
    else if (e->res_kind==RES_FIELD) p->part[p->n++]=e->res;
    else return false; /* Unknown projections use a root summary. */
    return true;
}

static TPath path_of(Expr *e) {
    TPath p={0}; p.valid=path_fill(e,&p,0);
    if (!p.valid && p.root) { p.n=0; p.valid=true; }
    return p;
}

static bool path_prefix(TPath a,TPath b) {
    if (!a.valid || !b.valid || a.root!=b.root || a.n>b.n) return false;
    for (uint32_t i=0;i<a.n;i++) if (a.part[i]!=b.part[i]) return false;
    return true;
}

static uint8_t read_path(T *t,TPath p) {
    if (!p.valid) return TAINT_UNTRUSTED|TAINT_SECRET;
    uint8_t bits=p.root->taint;
    for (uint32_t i=0;i<t->cells.len&&spend(t);i++) {
        TCell *c=&t->cells.data[i];
        if (path_prefix(c->path,p)||path_prefix(p,c->path)) bits|=c->bits;
    }
    return bits;
}

static void add_bits(T *t,uint8_t *slot,uint8_t bits) {
    if ((*slot|bits)!=*slot) { *slot|=bits; t->changed=true; }
}

static void write_path(T *t,TPath p,uint8_t bits) {
    if (!bits || !p.valid) return;
    if (!p.n) { add_bits(t,&p.root->taint,bits); return; }
    for (uint32_t i=0;i<t->cells.len&&spend(t);i++) {
        TCell *c=&t->cells.data[i];
        if(c->path.root==p.root&&c->path.n==p.n&&path_prefix(c->path,p)) {
            add_bits(t,&c->bits,bits); return;
        }
    }
    if(t->cells.len>=TAINT_MAX_CELLS) {t->exhausted=true;return;}
    TCell c={p,bits}; vec_push(t->a,t->cells,c); t->changed=true;
}

static Local *parameter_local(T *t,Item *fn,uint32_t index) {
    uint32_t n=0;
    for(uint32_t i=0;i<fn->nlocals&&spend(t);i++) {
        Local *l=((Local **)fn->locals)[i];
        if(l->is_param&&n++==index) return l;
    }
    return NULL;
}

static Expr *actual_argument(Expr *call,Item *fn,uint32_t index) {
    bool receiver=fn->fn.params.len&&fn->fn.params.data[0].is_self;
    if(receiver&&index==0) return call->call.callee&&call->call.callee->kind==EX_FIELD?
        call->call.callee->field.base:NULL;
    uint32_t arg=index-(receiver?1u:0u);
    return arg<call->call.args.len?call->call.args.data[arg].value:NULL;
}

static TRange range_of(T *t,Expr *e,Item *owner,uint32_t depth);
static bool return_ranges(T *t,Expr *e,Item *owner,uint32_t depth,TRange *out,bool *seen) {
    if(!e) return true;
    if(depth>64 || !spend(t)) return false;
#define RETURNS(child) do { if(!return_ranges(t,(child),owner,depth+1,out,seen)) return false; } while(0)
    if(e->kind==EX_BLOCK) {
        for(uint32_t i=0;i<e->block.stmts.len;i++) {
            Stmt *s=e->block.stmts.data[i];
            if(s->kind==ST_RETURN) {
                TRange r=range_of(t,s->expr,owner,depth+1);
                if(!r.known) return false;
                if(!*seen) {*out=r;*seen=true;}
                else {if(r.lo<out->lo)out->lo=r.lo;if(r.hi>out->hi)out->hi=r.hi;}
                RETURNS(s->expr);
            } else if(s->kind==ST_EXPR||s->kind==ST_DEFER) { RETURNS(s->expr); }
            else if(s->kind==ST_LET) { RETURNS(s->let.init); }
            else if(s->kind==ST_ASSIGN) { RETURNS(s->assign.target); RETURNS(s->assign.value); }
            else if(s->kind==ST_WHILE) { RETURNS(s->while_st.cond); RETURNS(s->while_st.body); }
            else if(s->kind==ST_FOR) { RETURNS(s->for_st.iter); RETURNS(s->for_st.body); }
        }
    } else if(e->kind==EX_IF) {
        RETURNS(e->if_expr.cond); RETURNS(e->if_expr.then_blk); RETURNS(e->if_expr.else_blk);
    } else if(e->kind==EX_UNSAFE) { RETURNS(e->unsafe_expr.body); }
    else if(e->kind==EX_UNARY) { RETURNS(e->unary.operand); }
    else if(e->kind==EX_BINARY) { RETURNS(e->binary.lhs); RETURNS(e->binary.rhs); }
    else if(e->kind==EX_CAST) { RETURNS(e->cast.value); }
    else if(e->kind==EX_FIELD) { RETURNS(e->field.base); }
    else if(e->kind==EX_INDEX) { RETURNS(e->index.base); RETURNS(e->index.index); }
    else if(e->kind==EX_CALL) {
        RETURNS(e->call.callee);
        for(uint32_t i=0;i<e->call.args.len;i++) { RETURNS(e->call.args.data[i].value); }
    } else if(e->kind==EX_ARRAY_LIT) {
        for(uint32_t i=0;i<e->array_lit.elems.len;i++) { RETURNS(e->array_lit.elems.data[i]); }
    } else if(e->kind==EX_STRUCT_LIT) {
        for(uint32_t i=0;i<e->struct_lit.fields.len;i++) { RETURNS(e->struct_lit.fields.data[i].value); }
    } else if(e->kind==EX_RANGE) { RETURNS(e->range.lo); RETURNS(e->range.hi); }
    else if(e->kind==EX_TRY) return false; /* Propagating returns need their own range contract. */
    else if(e->kind==EX_ORELSE) { RETURNS(e->orelse_expr.value); RETURNS(e->orelse_expr.fallback); }
    else if(e->kind==EX_CATCH) { RETURNS(e->catch_expr.value); RETURNS(e->catch_expr.handler); }
#undef RETURNS
    return true;
}

static TRange range_of(T *t,Expr *e,Item *owner,uint32_t depth) {
    TRange no={0};
    if(!e || depth>64 || !spend(t) || !e->type || e->type->kind!=TY_INT) return no;
    if(e->kind==EX_INT&&e->int_lit.val<=INT64_MAX)
        return (TRange){true,(int64_t)e->int_lit.val,(int64_t)e->int_lit.val};
    if(e->kind==EX_UNARY&&e->unary.op==TK_MINUS) {
        TRange r=range_of(t,e->unary.operand,owner,depth+1);
        if(r.known&&r.lo!=INT64_MIN&&r.hi!=INT64_MIN) return(TRange){true,-r.hi,-r.lo};
    }
    if(e->kind==EX_PATH&&e->res_kind==RES_CONST) {
        Item *it=e->res; return range_of(t,it->konst.value,owner,depth+1);
    }
    if((e->kind==EX_PATH||e->kind==EX_SELF)&&e->res_kind==RES_LOCAL) {
        Local *local=e->res;
        if(local->is_mut||local->is_param) return no;
        for(uint32_t i=0;i<t->initializers.len&&spend(t);i++)
            if(t->initializers.data[i].local==local)
                return range_of(t,t->initializers.data[i].expression,t->initializers.data[i].owner,depth+1);
    }
    if(e->kind!=EX_CALL) return no;
    if(e->res_kind==RES_FN) {
        Item *fn=e->res; TFunction *f=function_of(t,fn);
        if(!f || fn==owner) return no;
        TRange r={0};bool seen=false;
        return return_ranges(t,f->body,fn,depth+1,&r,&seen)&&seen?r:no;
    }
    if(e->res_kind!=RES_INTRINSIC) return no;
    if(e->intrinsic==INTR_CLAMP&&e->call.args.len==3) {
        TRange lo=range_of(t,e->call.args.data[1].value,owner,depth+1);
        TRange hi=range_of(t,e->call.args.data[2].value,owner,depth+1);
        if(lo.known&&hi.known&&lo.lo==lo.hi&&hi.lo==hi.hi&&lo.lo<=hi.lo)
            return (TRange){true,lo.lo,hi.lo};
    }
    if((e->intrinsic==INTR_MIN||e->intrinsic==INTR_MAX)&&e->call.args.len==2) {
        TRange a=range_of(t,e->call.args.data[0].value,owner,depth+1);
        TRange b=range_of(t,e->call.args.data[1].value,owner,depth+1);
        if(a.known&&b.known) {
            if(e->intrinsic==INTR_MIN) return(TRange){true,a.lo<b.lo?a.lo:b.lo,a.hi<b.hi?a.hi:b.hi};
            return(TRange){true,a.lo>b.lo?a.lo:b.lo,a.hi>b.hi?a.hi:b.hi};
        }
    }
    return no;
}

/* ---- taint of an expression -------------------------------------------- */

static uint8_t taint_of(T *t, Expr *e);

static uint8_t taint_of_call(T *t, Expr *e) {
    uint8_t acc = TAINT_NONE;
    for (uint32_t i = 0; i < e->call.args.len; i++)
        acc |= taint_of(t, e->call.args.data[i].value);

    if(e->call.callee&&e->call.callee->kind==EX_FIELD)
        acc|=taint_of(t,e->call.callee->field.base);
    if (e->res_kind == RES_INTRINSIC) return acc;

    Item *fn = (e->res_kind == RES_FN) ? (Item *)e->res : NULL;
    if (!fn) return acc;

    TFunction *summary=function_of(t,fn);
    if(summary) acc|=summary->returns;

    if (item_has_attr(fn, "untrusted")) acc |= TAINT_UNTRUSTED;
    if (item_has_attr(fn, "secret")) acc |= TAINT_SECRET;

    /* A constant-time function may only call other constant-time functions;
     * otherwise the guarantee stops at the first ordinary callee. */
    if (t->emit && t->in_constant_time && !item_has_attr(fn, "constant_time") &&
        e->res_kind != RES_INTRINSIC) {
        Diag *dg = diag_error(t->d, 607, e->span,
                              "`@constant_time` function calls `%.*s`, which is not "
                              "declared constant-time",
                              (int)fn->name.len, fn->name.ptr);
        diag_label(dg, e->span, "called here");
        diag_note(dg, "the source restriction has to hold through every callee; "
                      "this check does not establish machine-level constant-time execution");
    }

    /* Server-authoritative code must not be reachable from client context. */
    if (t->emit && item_has_attr(fn, "server_only") && !t->in_server_only) {
        Diag *dg = diag_error(t->d, 705, e->span,
                              "`%.*s` is `@server_only` but is called from client context",
                              (int)fn->name.len, fn->name.ptr);
        diag_label(dg, e->span, "called here, from a caller that is not `@server_only`");
        diag_help(dg, "route the operation through a verified server request boundary; "
                      "annotations alone do not establish runtime authority");
    }
    return acc;
}

static uint8_t taint_inner(T *t, Expr *e) {
    if (!e) return TAINT_NONE;
    switch (e->kind) {
        case EX_PATH:
        case EX_SELF:
            if(e->res_kind==RES_LOCAL) return read_path(t,path_of(e));
            if(e->res_kind==RES_CONST) return taint_of(t,((Item *)e->res)->konst.value);
            return 0;
        case EX_FIELD: {
            TPath p=path_of(e);return p.valid?read_path(t,p):taint_of(t,e->field.base);
        }
        case EX_INDEX: {
            TPath p=path_of(e);
            return (uint8_t)((p.valid?read_path(t,p):taint_of(t,e->index.base))|
                             taint_of(t,e->index.index));
        }
        case EX_UNARY: return taint_of(t, e->unary.operand);
        case EX_BINARY:
            return (uint8_t)(taint_of(t, e->binary.lhs) | taint_of(t, e->binary.rhs));
        case EX_CAST: return taint_of(t, e->cast.value);
        case EX_CALL: return taint_of_call(t, e);
        case EX_TRY: return taint_of(t, e->try_expr.inner);
        case EX_ORELSE:
            return (uint8_t)(taint_of(t, e->orelse_expr.value) |
                             taint_of(t, e->orelse_expr.fallback));
        case EX_CATCH: return (uint8_t)(taint_of(t,e->catch_expr.value)|taint_of(t,e->catch_expr.handler));
        case EX_UNSAFE: return taint_of(t,e->unsafe_expr.body);
        case EX_IF: return (uint8_t)(taint_of(t,e->if_expr.cond)|taint_of(t,e->if_expr.then_blk)|taint_of(t,e->if_expr.else_blk));
        case EX_BLOCK: {
            uint8_t acc=0;
            for(uint32_t i=0;i<e->block.stmts.len;i++) {
                Stmt *s=e->block.stmts.data[i];
                if(s->kind==ST_EXPR||s->kind==ST_RETURN) acc|=taint_of(t,s->expr);
            }
            return acc;
        }
        case EX_RANGE:return(uint8_t)(taint_of(t,e->range.lo)|taint_of(t,e->range.hi));
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

static uint8_t taint_of(T *t,Expr *e) {
    if(!e) return 0;
    if(!spend(t)||t->depth>=TAINT_MAX_DEPTH) {t->exhausted=true;return TAINT_UNTRUSTED|TAINT_SECRET;}
    t->depth++;uint8_t result=taint_inner(t,e);t->depth--;return result;
}

/* ---- sinks -------------------------------------------------------------- */

static void check_index_sink(T *t, Expr *e) {
    if(!t->emit) return;
    uint8_t idx = taint_of(t, e->index.index);
    TRange bounds=range_of(t,e->index.index,t->fn,0);
    Type *storage=e->index.base?e->index.base->type:NULL;
    bool bounded=storage&&storage->kind==TY_ARRAY&&bounds.known&&bounds.lo>=0&&
        (uint64_t)bounds.hi<storage->array_len;

    if ((idx & TAINT_UNTRUSTED)&&!bounded) {
        Diag *dg = diag_error(t->d, 601, e->index.index->span,
                              "an untrusted value is used as an index without being "
                              "bounded first");
        diag_label(dg, e->index.index->span, "this index is attacker-controlled");
        diag_note(dg, "a client controls this value; an out-of-range index is the "
                      "cheapest thing for it to send");
        diag_help(dg, "prove bounds for this storage: `clamp(i, 0, n - 1)` requires "
                      "a nonempty collection and a current length; a bare `@validator` "
                      "does not establish those facts");
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
    if (!t->emit || !cond) return;
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
static Local *local_at(T *t, Span sp, Str name);

static void walk_inner(T *t, Expr *e) {
    if (!e) return;
    switch (e->kind) {
        case EX_INDEX:
            check_index_sink(t, e);
            walk_expr(t, e->index.base);
            walk_expr(t, e->index.index);
            break;

        case EX_UNSAFE: {
            if (t->emit && t->forbid_unsafe) {
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

        case EX_CALL: {
            if (e->call.callee && e->call.callee->kind == EX_FIELD)
                walk_expr(t, e->call.callee->field.base);
            for (uint32_t i = 0; i < e->call.args.len; i++)
                walk_expr(t, e->call.args.data[i].value);
            (void)taint_of_call(t, e);
            Item *fn=e->res_kind==RES_FN?e->res:NULL;
            if(fn) {
                for(uint32_t i=0;i<fn->fn.params.len;i++) {
                    Expr *actual=actual_argument(e,fn,i);
                    Local *formal=parameter_local(t,fn,i);
                    if(!actual||!formal) continue;
                    add_bits(t,&formal->taint,taint_of(t,actual));
                    Conv mode=fn->fn.params.data[i].conv;
                    if(mode==CONV_INOUT||mode==CONV_SET) {
                        TPath p={0};p.root=formal;p.valid=true;
                        write_path(t,path_of(actual),read_path(t,p));
                    }
                }
            } else if(e->res_kind==RES_INTRINSIC&&intrinsic_is_list_method((Intrinsic)e->intrinsic)) {
                Expr *receiver=e->call.callee&&e->call.callee->kind==EX_FIELD?e->call.callee->field.base:NULL;
                if(e->intrinsic==INTR_LIST_SET||e->intrinsic==INTR_LIST_PUSH) {
                    uint8_t bits=0;
                    for(uint32_t i=0;i<e->call.args.len;i++) bits|=taint_of(t,e->call.args.data[i].value);
                    write_path(t,path_of(receiver),bits);
                }
                if((e->intrinsic==INTR_LIST_GET||e->intrinsic==INTR_LIST_SET)&&e->call.args.len) {
                    Expr sink={0};sink.kind=EX_INDEX;sink.index.base=receiver;
                    sink.index.index=e->call.args.data[0].value;check_index_sink(t,&sink);
                }
            }
            break;
        }

        case EX_IF:
            check_branch_sink(t, e->if_expr.cond, "if");
            walk_expr(t, e->if_expr.cond);
            walk_expr(t, e->if_expr.then_blk);
            walk_expr(t, e->if_expr.else_blk);
            break;

        case EX_BINARY:
            if(e->binary.op==TK_ANDAND||e->binary.op==TK_OROR)
                check_branch_sink(t,e->binary.lhs,"short-circuit");
            walk_expr(t, e->binary.lhs);
            walk_expr(t, e->binary.rhs);
            break;
        case EX_UNARY: walk_expr(t, e->unary.operand); break;
        case EX_CAST: walk_expr(t, e->cast.value); break;
        case EX_FIELD: walk_expr(t, e->field.base); break;
        case EX_BLOCK: walk_block(t, e); break;
        case EX_TRY: {
            check_branch_sink(t,e->try_expr.inner,"try");
            walk_expr(t, e->try_expr.inner);
            TFunction *fn=function_of(t,t->fn);
            if(fn) add_bits(t,&fn->returns,taint_of(t,e->try_expr.inner));
            break;
        }
        case EX_ORELSE:
            check_branch_sink(t,e->orelse_expr.value,"orelse");
            walk_expr(t, e->orelse_expr.value);
            walk_expr(t, e->orelse_expr.fallback);
            break;
        case EX_CATCH:
            check_branch_sink(t,e->catch_expr.value,"catch");
            walk_expr(t, e->catch_expr.value);
            if(!str_empty(e->catch_expr.binding)) {
                Local *binding=local_at(t,e->span,e->catch_expr.binding);
                if(binding) add_bits(t,&binding->taint,taint_of(t,e->catch_expr.value));
            }
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
        case EX_RANGE:
            check_branch_sink(t,e->range.lo,"for");check_branch_sink(t,e->range.hi,"for");
            walk_expr(t,e->range.lo);walk_expr(t,e->range.hi);break;
        default: break;
    }
}

static void walk_expr(T *t,Expr *e) {
    if(!e) return;
    if(!spend(t)||t->depth>=TAINT_MAX_DEPTH){t->exhausted=true;return;}
    t->depth++;walk_inner(t,e);t->depth--;
}

/* Finds the binding a `let`/`for` statement introduced. */
static Local *local_at(T *t, Span sp, Str name) {
    if (!t->fn) return NULL;
    for (uint32_t i = 0; i < t->fn->nlocals&&spend(t); i++) {
        Local *l = ((Local **)t->fn->locals)[i];
        if (l->span.file==sp.file && l->span.offset == sp.offset && str_eq(l->name, name)) return l;
    }
    return NULL;
}

static void assign_value(T *t,TPath path,Expr *value,uint32_t depth) {
    if(!value||!path.valid||!spend(t))return;
    if(depth<TAINT_MAX_PATH&&path.n<TAINT_MAX_PATH&&value->kind==EX_STRUCT_LIT&&
       value->type&&value->type->kind==TY_STRUCT&&value->type->decl) {
        Item *decl=value->type->decl;
        for(uint32_t i=0;i<value->struct_lit.fields.len;i++) {
            FieldInit *init=&value->struct_lit.fields.data[i];bool found=false;
            for(uint32_t j=0;j<decl->strukt.fields.len&&spend(t);j++) {
                Field *field=&decl->strukt.fields.data[j];
                if(str_eq(field->name,init->name)) {
                    TPath member=path;member.part[member.n++]=field;
                    assign_value(t,member,init->value,depth+1);found=true;break;
                }
            }
            if(!found)write_path(t,path,taint_of(t,init->value));
        }
    } else write_path(t,path,taint_of(t,value));
}

static void walk_stmt(T *t, Stmt *s) {
    if (!s || !spend(t)) return;
    switch (s->kind) {
        case ST_LET: {
            walk_expr(t, s->let.init);
            Local *l = local_at(t, s->span, s->let.name);
            if (l) {
                TPath p={0};p.root=l;p.valid=true;assign_value(t,p,s->let.init,0);
                bool found=false;
                for(uint32_t i=0;i<t->initializers.len&&spend(t);i++)if(t->initializers.data[i].local==l){found=true;break;}
                if(!found&&s->let.init&&!l->is_mut){TInit init={l,t->fn,s->let.init};vec_push(t->a,t->initializers,init);}
            }
            break;
        }
        case ST_ASSIGN: {
            walk_expr(t, s->assign.target);
            walk_expr(t, s->assign.value);
            assign_value(t,path_of(s->assign.target),s->assign.value,0);
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
            if (l) add_bits(t,&l->taint,taint_of(t,s->for_st.iter));
            check_branch_sink(t,s->for_st.iter,"for");
            walk_expr(t, s->for_st.body);
            break;
        }
        case ST_RETURN: {
            walk_expr(t,s->expr);TFunction *fn=function_of(t,t->fn);
            if(fn)add_bits(t,&fn->returns,taint_of(t,s->expr));break;
        }
        case ST_EXPR:
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

    /* `@unsafe` on the item itself, as opposed to on a block inside it. */
    if (t->emit && t->forbid_unsafe && item_has_attr(it, "unsafe")) {
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
            Expr *body=NULL;
            if (it->kind == IT_FN && !it->fn.generics.len) body=it->fn.body;
            else if (it->kind == IT_TEST) body=it->test.body;
            if(!body) continue;
            if(t.functions.len>=TAINT_MAX_FUNCTIONS){t.exhausted=true;break;}
            TFunction fn={it,body,0};vec_push(t.a,t.functions,fn);
            uint8_t src=0;
            if(item_has_attr(it,"untrusted"))src|=TAINT_UNTRUSTED;
            if(item_has_attr(it,"secret"))src|=TAINT_SECRET;
            for(uint32_t j=0;j<it->nlocals;j++){
                Local *l=((Local **)it->locals)[j];l->taint=l->is_param?src:0;
            }
        }
    }
    do {
        t.changed=false;
        for(uint32_t i=0;i<t.functions.len&&!t.exhausted;i++)
            check_fn(&t,t.functions.data[i].item,t.functions.data[i].body);
    } while(t.changed&&!t.exhausted);
    t.emit=true;
    for(uint32_t i=0;i<t.functions.len&&!t.exhausted;i++)
        check_fn(&t,t.functions.data[i].item,t.functions.data[i].body);
    if(t.exhausted) {
        Diag *dg=diag_error(d,608,SPAN_NONE,"security analysis exceeded its bounded resource limit");
        diag_help(dg,"reduce the analyzed source set or expression depth; this result is not a successful security check");
    }
    return diag_errors(d) == before;
}
