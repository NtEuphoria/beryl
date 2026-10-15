#include "ir.h"
#include <stdlib.h>
#include <string.h>
#include <float.h>
#include <math.h>
_Static_assert(sizeof(float)==sizeof(uint32_t) && FLT_RADIX==2 && FLT_MANT_DIG==24 && FLT_MAX_EXP==128,"IR requires binary32");

typedef enum { NEXT, RETURN, BREAK, CONTINUE, YIELD } FlowKind;
typedef struct { FlowKind kind; int64_t value; const int64_t *cells; } Flow;
typedef struct { const IrFunction *fn; int64_t **places, **values; } Frame;
typedef struct { int64_t *cells; bool borrow; } Actual;
typedef struct {
    const IrProgram *p; IrRunOpts opts; IrRunResult result;
    uint64_t sequence, output_bytes, started;
    uint32_t calls, regions; bool test_failed;
} Run;
static bool running(Run *r) { return r->result.status==IR_RUN_SUCCESS; }
static void failure(Run *r,IrRunStatus status,Span at) {
    if (running(r)) { r->result.status=status; r->result.source=at; }
}
static bool tick(Run *r,Span at) {
    if (!running(r)) return false;
    if (r->opts.cancelled && r->opts.cancelled()) { failure(r,IR_RUN_CANCELLED,at); return false; }
    if (r->opts.timeout_ms && r->opts.clock_ms && r->opts.clock_ms()-r->started>=r->opts.timeout_ms) {
        failure(r,IR_RUN_TIMEOUT,at); return false;
    }
    if (r->result.steps>=r->opts.max_steps) { failure(r,IR_RUN_BUDGET,at); return false; }
    r->result.steps++; return true;
}
static bool bytes(Run *r,FILE *file,const char *data,size_t n,Span at) {
    if (!running(r)) return false;
    if (n>UINT64_C(67108864)-r->output_bytes) { failure(r,IR_RUN_BUDGET,at); return false; }
    r->output_bytes+=n;
    if (!file || fwrite(data,1,n,file)!=n) { failure(r,IR_RUN_IO,at); return false; }
    return true;
}
static void event(Run *r,const char *kind,Span at,bool flag) {
    if (!r->opts.events || !running(r)) return;
    char text[200]; int n=snprintf(text,sizeof text,
        "{\"event\":\"%s\",\"seq\":%llu,\"file\":%u,\"offset\":%u,\"flag\":%s}\n",
        kind,(unsigned long long)r->sequence++,at.file,at.offset,flag?"true":"false");
    if (n<0 || (size_t)n>=sizeof text) failure(r,IR_RUN_IO,at);
    else bytes(r,r->opts.events,text,(size_t)n,at);
}
static void trap(Run *r,IrTrap kind,Span at) {
    if (!running(r)) return;
    r->result.trap=kind; r->result.source=at;
    if (r->opts.events) {
        if (fflush(r->opts.output)!=0 || fflush(r->opts.events)!=0) { failure(r,IR_RUN_IO,at); return; }
        char text[200]; int n=snprintf(text,sizeof text,
            "{\"event\":\"source_trap\",\"seq\":%llu,\"file\":%u,\"offset\":%u,\"kind\":\"%s\",\"complete\":true}\n",
            (unsigned long long)r->sequence++,at.file,at.offset,kind==IR_TRAP_OVERFLOW?"overflow":kind==IR_TRAP_BOUNDS?"bounds":"division_by_zero");
        if (n<0 || (size_t)n>=sizeof text || !bytes(r,r->opts.events,text,(size_t)n,at)) { failure(r,IR_RUN_IO,at); return; }
        if (fflush(r->opts.events)!=0) { failure(r,IR_RUN_IO,at); return; }
        r->result.trace_complete=true;
    }
    failure(r,IR_RUN_TRAP,at);
}
static int64_t checked(Run *r,int64_t value,Span at) {
    if (value<INT32_MIN || value>INT32_MAX) trap(r,IR_TRAP_OVERFLOW,at);
    return value;
}
static int64_t from_bits(uint32_t n) { return n<=INT32_MAX?(int64_t)n:(int64_t)n-INT64_C(4294967296); }
static float floating(int64_t bits) { uint32_t word=(uint32_t)bits; float x; memcpy(&x,&word,sizeof x); return x; }
static int64_t float_value(Run *r,float x,Span at) {
    if (!isfinite(x)) { failure(r,IR_RUN_TRAP,at); return 0; }
    uint32_t bits; memcpy(&bits,&x,sizeof bits); return bits;
}
static double number(IrType type,int64_t bits) { return type==IR_F32?(double)floating(bits):(double)bits; }
static int64_t arithmetic(Run *r,IrNumeric op,IrType type,int64_t a,int64_t b,Span at) {
    if (type==IR_F32) {
        volatile float x=floating(a), y=floating(b), z=0;
        switch (op) {
            case IR_ADD: z=x+y; break; case IR_SUB: z=x-y; break;
            case IR_MUL: z=x*y; break; case IR_DIV: z=x/y; break;
            case IR_EQ: return x==y; case IR_NE: return x!=y;
            case IR_LT: return x<y; case IR_LE: return x<=y; case IR_GT: return x>y; case IR_GE: return x>=y;
            default: failure(r,IR_RUN_INVALID,at); return 0;
        }
        return float_value(r,z,at);
    }
    switch (op) {
        case IR_ADD: return checked(r,a+b,at);
        case IR_SUB: return checked(r,a-b,at);
        case IR_MUL: return checked(r,a*b,at);
        case IR_DIV: case IR_REM:
            if (!b) { trap(r,IR_TRAP_DIVISION_ZERO,at); return 0; }
            if (a==INT32_MIN && b==-1) {
                if (op==IR_REM) return 0;
                trap(r,IR_TRAP_OVERFLOW,at); return 0;
            }
            return op==IR_DIV?a/b:a%b;
        case IR_BIT_AND: return from_bits((uint32_t)a&(uint32_t)b);
        case IR_BIT_OR: return from_bits((uint32_t)a|(uint32_t)b);
        case IR_BIT_XOR: return from_bits((uint32_t)a^(uint32_t)b);
        case IR_EQ: return a==b; case IR_NE: return a!=b;
        case IR_LT: return a<b; case IR_LE: return a<=b; case IR_GT: return a>b; case IR_GE: return a>=b;
        case IR_SHL: case IR_SHR: {
            if (b<0 || b>=32) { failure(r,IR_RUN_TRAP,at); return 0; }
            uint32_t bits=(uint32_t)a;
            if (op==IR_SHL) bits=(uint32_t)((uint64_t)bits<<(unsigned)b);
            else { bits>>=(unsigned)b; if (a<0 && b) bits|=(uint32_t)(UINT64_C(0xffffffff)<<(32-(unsigned)b)); }
            return from_bits(bits);
        }
        default: failure(r,IR_RUN_INVALID,at); return 0;
    }
}
static int64_t *place_cells(Run *r,Frame *f,uint32_t id,Span at) {
    uint32_t offset=0;
    for (uint32_t depth=0;depth<IR_MAX_DEPTH;depth++) {
        const IrPlace *place=&r->p->places.data[id];
        if (place->parent==IR_NONE || place->definition!=IR_NONE) {
            int64_t *base=f->places[id-f->fn->places_start];
            if (!base) { failure(r,IR_RUN_INVALID,at); return NULL; }
            return base+offset;
        }
        offset+=r->p->fields.data[place->field].offset; id=place->parent;
    }
    failure(r,IR_RUN_INVALID,at); return NULL;
}
static bool index_offset(Run *r,const IrAggregate *array,int64_t index,Span at,uint32_t *offset) {
    if (index<0 || (uint64_t)index>=array->length) { trap(r,IR_TRAP_BOUNDS,at); return false; }
    *offset=(uint32_t)index*ir_type_cells(r->p,array->element); return true;
}
static int64_t *value_cells(Frame *f,uint32_t id) { return id==IR_NONE?NULL:f->values[id-f->fn->values_start]; }
static int64_t value(Frame *f,uint32_t id) { return id==IR_NONE?0:*value_cells(f,id); }
static int64_t intrinsic(Run *r,Frame *f,const IrInstruction *i) {
    uint32_t first=r->p->arguments.data[i->args_start].value;
    IrType type=r->p->values.data[first].type; int64_t a=value(f,first);
    int64_t b=i->args_count>1?value(f,r->p->arguments.data[i->args_start+1].value):0;
    double x=number(type,a),y=number(type,b);
    switch (i->intrinsic) {
        case IR_MIN: return x<y?a:b; case IR_MAX: return x>y?a:b;
        case IR_CLAMP: {
            int64_t c=value(f,r->p->arguments.data[i->args_start+2].value);
            return x<y?b:x>number(type,c)?c:a;
        }
        case IR_ABS:
            if (type==IR_F32) return (uint32_t)a&UINT32_C(0x7fffffff);
            return checked(r,a<0?-a:a,i->source.origin);
        case IR_WRAP_ADD: return from_bits((uint32_t)((uint64_t)(uint32_t)a+(uint32_t)b));
        case IR_WRAP_SUB: return from_bits((uint32_t)((uint64_t)(uint32_t)a-(uint32_t)b));
        case IR_WRAP_MUL: return from_bits((uint32_t)((uint64_t)(uint32_t)a*(uint32_t)b));
        case IR_SAT_ADD: case IR_SAT_SUB: {
            int64_t z=i->intrinsic==IR_SAT_ADD?a+b:a-b;
            return z<INT32_MIN?INT32_MIN:z>INT32_MAX?INT32_MAX:z;
        }
    }
    failure(r,IR_RUN_INVALID,i->source.origin); return 0;
}
static void float_event(Run *r,Span source,int64_t bits) {
    if (!r->opts.events || !running(r)) return;
    char text[200]; int n=snprintf(text,sizeof text,
        "{\"event\":\"f32\",\"seq\":%llu,\"file\":%u,\"offset\":%u,\"bits\":%u}\n",
        (unsigned long long)r->sequence++,source.file,source.offset,(uint32_t)bits);
    if (n<0 || (size_t)n>=sizeof text) failure(r,IR_RUN_IO,source);
    else bytes(r,r->opts.events,text,(size_t)n,source);
}
static Flow region(Run *r,Frame *f,uint32_t id);
static void invoke(Run *r,uint32_t fn,const Actual *args,int64_t *out,Span at) {
    if (r->calls>=r->opts.max_call_depth) { failure(r,IR_RUN_BUDGET,at); return; }
    const IrFunction *function=&r->p->functions.data[fn];
    uint64_t slots=(uint64_t)function->places_count+function->values_count, cells=0;
    if (!slots) slots=1;
    for (uint32_t p=0;p<function->places_count;p++) {
        const IrPlace *place=&r->p->places.data[function->places_start+p];
        if (place->parent==IR_NONE) cells+=ir_type_cells(r->p,place->type);
    }
    for (uint32_t v=0;v<function->values_count;v++) cells+=ir_type_cells(r->p,r->p->values.data[function->values_start+v].type);
    if (!cells) cells=1;
    uint64_t size=slots*sizeof(int64_t *)+cells*sizeof(int64_t);
    if (size>r->opts.max_bytes-r->result.allocated_bytes) { failure(r,IR_RUN_BUDGET,at); return; }
    int64_t **pointers=calloc((size_t)slots,sizeof(int64_t *));
    int64_t *storage=calloc((size_t)cells,sizeof(int64_t));
    if (!pointers || !storage) { free(pointers); free(storage); failure(r,IR_RUN_BUDGET,at); return; }
    r->result.allocated_bytes+=size;
    Frame frame={.fn=function,.places=pointers,.values=pointers+function->places_count}; uint32_t offset=0;
    for (uint32_t p=0;p<function->places_count;p++) {
        const IrPlace *place=&r->p->places.data[function->places_start+p];
        if (place->parent==IR_NONE) {
            frame.places[p]=storage+offset; offset+=ir_type_cells(r->p,place->type);
            if (p<function->parameters) {
                if (args[p].borrow) frame.places[p]=args[p].cells;
                else memcpy(frame.places[p],args[p].cells,ir_type_cells(r->p,place->type)*sizeof(int64_t));
            }
        } /* Projected addresses are resolved after their checked definition. */
    }
    for (uint32_t v=0;v<function->values_count;v++) {
        frame.values[v]=storage+offset; offset+=ir_type_cells(r->p,r->p->values.data[function->values_start+v].type);
    }
    r->calls++; Flow returned=region(r,&frame,function->body); r->calls--;
    if (running(r)) {
        if (returned.kind!=RETURN) failure(r,IR_RUN_INVALID,at);
        else if (function->result!=IR_VOID) memcpy(out,returned.cells,ir_type_cells(r->p,function->result)*sizeof(int64_t));
    }
    free(storage); free(pointers);
}
static Flow region(Run *r,Frame *f,uint32_t id) {
    Flow flow={.kind=NEXT};
    if (!running(r)) return flow;
    if (r->regions>=IR_MAX_DEPTH) { failure(r,IR_RUN_BUDGET,r->p->regions.data[id].source); return flow; }
    r->regions++;
    for (uint32_t at=r->p->regions.data[id].first;at!=IR_NONE && flow.kind==NEXT;at=r->p->instructions.data[at].next) {
        const IrInstruction *i=&r->p->instructions.data[at]; Span source=i->source.origin;
        if (!tick(r,source)) break;
        int64_t result=0; bool aggregate_result=false;
        switch (i->op) {
            case IR_CONST: result=r->p->values.data[i->result].type==IR_F32?(int64_t)i->float_bits:i->immediate; break;
            case IR_LOAD: case IR_MOVE: {
                int64_t *source_cells=place_cells(r,f,i->place,source);
                if (source_cells) memcpy(value_cells(f,i->result),source_cells,ir_type_cells(r->p,r->p->places.data[i->place].type)*sizeof(int64_t));
                aggregate_result=true; break;
            }
            case IR_INIT: case IR_STORE: {
                int64_t *destination=place_cells(r,f,i->place,source);
                if (destination) memcpy(destination,value_cells(f,i->a),ir_type_cells(r->p,r->p->places.data[i->place].type)*sizeof(int64_t)); break;
            }
            case IR_UNARY:
                if (i->numeric==IR_NOT) result=!value(f,i->a);
                else if (i->numeric==IR_BIT_NOT) result=from_bits(~(uint32_t)value(f,i->a));
                else if (r->p->values.data[i->a].type==IR_F32) result=float_value(r,-floating(value(f,i->a)),source);
                else result=checked(r,-value(f,i->a),source);
                break;
            case IR_BINARY: result=arithmetic(r,i->numeric,r->p->values.data[i->a].type,value(f,i->a),value(f,i->b),source); break;
            case IR_CAST: {
                IrType from=r->p->values.data[i->a].type,to=r->p->values.data[i->result].type;
                double x=number(from,value(f,i->a));
                if (to==IR_F32) { volatile float rounded=(float)x; result=float_value(r,rounded,source); }
                else if (!isfinite(x) || x<(double)INT32_MIN || x>=2147483648.0) failure(r,IR_RUN_TRAP,source);
                else result=(int64_t)x;
                break;
            }
            case IR_INTRINSIC: result=intrinsic(r,f,i); break;
            case IR_CALL: {
                Actual args[IR_MAX_CALL_ARGUMENTS];
                for (uint32_t a=0;a<i->args_count;a++) {
                    const IrArgument *arg=&r->p->arguments.data[i->args_start+a];
                    args[a]=(Actual){.borrow=arg->by_place,.cells=arg->by_place?place_cells(r,f,r->p->instructions.data[arg->capture].place,source):value_cells(f,arg->value)};
                }
                if (running(r)) invoke(r,i->function,args,value_cells(f,i->result),source); aggregate_result=true; break;
            }
            case IR_DECLARE: case IR_DESTINATION: case IR_CAPTURE: case IR_INDEX_BASE: break; /* capture stability verified independently */
            case IR_RECORD:
                for (uint32_t a=0;a<i->args_count;a++) {
                    const IrArgument *arg=&r->p->arguments.data[i->args_start+a]; const IrField *field=&r->p->fields.data[arg->field];
                    memcpy(value_cells(f,i->result)+field->offset,value_cells(f,arg->value),ir_type_cells(r->p,field->type)*sizeof(int64_t));
                }
                aggregate_result=true; break;
            case IR_FIELD: {
                const IrField *field=&r->p->fields.data[i->place];
                memcpy(value_cells(f,i->result),value_cells(f,i->a)+field->offset,ir_type_cells(r->p,field->type)*sizeof(int64_t));
                aggregate_result=true; break;
            }
            case IR_ARRAY: {
                const IrAggregate *array=&r->p->aggregates.data[r->p->values.data[i->result].type-IR_FIRST_AGGREGATE];
                uint32_t cells=ir_type_cells(r->p,array->element);
                for (uint32_t a=0;a<i->args_count;a++) memcpy(value_cells(f,i->result)+a*cells,value_cells(f,r->p->arguments.data[i->args_start+a].value),cells*sizeof(int64_t));
                aggregate_result=true; break;
            }
            case IR_INDEX_VALUE: {
                const IrAggregate *array=&r->p->aggregates.data[r->p->values.data[i->a].type-IR_FIRST_AGGREGATE]; uint32_t offset;
                if (index_offset(r,array,value(f,i->b),source,&offset)) memcpy(value_cells(f,i->result),value_cells(f,i->a)+offset,ir_type_cells(r->p,array->element)*sizeof(int64_t));
                aggregate_result=true; break;
            }
            case IR_INDEX_PLACE: {
                uint32_t parent=r->p->places.data[i->place].parent;
                const IrAggregate *array=&r->p->aggregates.data[r->p->places.data[parent].type-IR_FIRST_AGGREGATE]; uint32_t offset;
                if (index_offset(r,array,value(f,i->a),source,&offset)) {
                    int64_t *base=place_cells(r,f,parent,source);
                    if (base) f->places[i->place-f->fn->places_start]=base+offset;
                }
                break;
            }
            case IR_IF: flow=region(r,f,i->child[value(f,i->a)?0:1]); break;
            case IR_LOOP:
                while (running(r)) {
                    Flow cond=region(r,f,i->child[0]);
                    if (!running(r)) break;
                    if (cond.kind!=YIELD) { failure(r,IR_RUN_INVALID,source); break; }
                    if (!cond.value) break;
                    Flow body=region(r,f,i->child[1]);
                    if (body.kind==RETURN) { flow=body; break; }
                    if (body.kind==BREAK || !running(r)) break;
                    Flow step=region(r,f,i->child[2]);
                    if (running(r) && step.kind!=NEXT) { failure(r,IR_RUN_INVALID,source); break; }
                }
                break;
            case IR_RETURN: flow=(Flow){.kind=RETURN,.value=value(f,i->a),.cells=value_cells(f,i->a)}; break;
            case IR_BREAK: flow.kind=BREAK; break;
            case IR_CONTINUE: flow.kind=CONTINUE; break;
            case IR_YIELD: flow=(Flow){.kind=YIELD,.value=value(f,i->a)}; break;
            case IR_PRINT:
                event(r,"print",source,i->flag);
                for (uint32_t a=0;a<i->args_count && running(r);a++) {
                    uint32_t v=r->p->arguments.data[i->args_start+a].value; char text[40]; int n;
                    if (r->p->values.data[v].type==IR_BOOL) n=snprintf(text,sizeof text,"%s",value(f,v)?"true":"false");
                    else if (r->p->values.data[v].type==IR_F32) {
                        float_event(r,r->p->arguments.data[i->args_start+a].source,value(f,v));
                        n=snprintf(text,sizeof text,"%g",(double)floating(value(f,v)));
                    }
                    else n=snprintf(text,sizeof text,"%lld",(long long)value(f,v));
                    if (n<0 || (size_t)n>=sizeof text) failure(r,IR_RUN_IO,source);
                    else bytes(r,r->opts.output,text,(size_t)n,source);
                }
                if (i->flag) bytes(r,r->opts.output,"\n",1,source);
                break;
            case IR_ASSERT: {
                bool pass=value(f,r->p->arguments.data[i->args_start].value)!=0;
                r->result.assertions++; event(r,"assert",source,pass); if (!pass) r->test_failed=true; break;
            }
        }
        if (!running(r)) break;
        if (i->result!=IR_NONE && !aggregate_result) *value_cells(f,i->result)=result;
    }
    r->regions--; return flow;
}
IrRunResult ir_test(const IrProgram *p,IrRunOpts opts) {
    IrVerification checked_ir=ir_verify(p);
    if (!checked_ir.ok) return (IrRunResult){.status=IR_RUN_INVALID,.source=checked_ir.source};
    if ((opts.timeout_ms && !opts.clock_ms) || opts.max_call_depth>IR_MAX_DEPTH)
        return (IrRunResult){.status=IR_RUN_UNAVAILABLE,.source=SPAN_NONE};
    Run r={.p=p,.opts=opts};
    if (!r.opts.output) r.opts.output=stdout;
    if (!r.opts.max_steps) r.opts.max_steps=1000000;
    if (!r.opts.max_bytes) r.opts.max_bytes=64*1024*1024;
    if (!r.opts.max_call_depth) r.opts.max_call_depth=IR_MAX_DEPTH;
    if (r.opts.clock_ms) r.started=r.opts.clock_ms();
    for (uint32_t f=0;f<p->functions.len && running(&r);f++) {
        const IrFunction *fn=&p->functions.data[f]; if (!fn->test) continue;
        r.test_failed=false; r.result.tests++; event(&r,"test_begin",fn->declaration,true);
        if (running(&r)) invoke(&r,f,NULL,NULL,fn->declaration);
        if (r.test_failed) r.result.failed_tests++;
        event(&r,"test_end",fn->declaration,!r.test_failed);
    }
    if (running(&r) && !r.result.tests) failure(&r,IR_RUN_UNAVAILABLE,SPAN_NONE);
    if (running(&r)) {
        char text[160]; int n;
        if (r.result.failed_tests) n=snprintf(text,sizeof text,"FAILED  %u of %u test%s\n",r.result.failed_tests,r.result.tests,r.result.tests==1?"":"s");
        else n=snprintf(text,sizeof text,"ok  %u test%s, %llu assertion%s\n",r.result.tests,r.result.tests==1?"":"s",
            (unsigned long long)r.result.assertions,r.result.assertions==1?"":"s");
        if (n<0 || (size_t)n>=sizeof text) failure(&r,IR_RUN_IO,SPAN_NONE);
        else bytes(&r,r.opts.output,text,(size_t)n,SPAN_NONE);
        if (running(&r) && r.result.failed_tests) r.result.status=IR_RUN_FAILED;
    }
    if (fflush(r.opts.output)!=0 || (r.opts.events && fflush(r.opts.events)!=0)) {
        r.result.status=IR_RUN_IO; r.result.trace_complete=false;
    }
    return r.result;
}
