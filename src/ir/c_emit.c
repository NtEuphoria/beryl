#include "c_emit.h"
#include <string.h>
#include <stdio.h>
#include <stdlib.h>

#define S(s) (int)(s).len,(s).ptr
typedef struct { Span at; uint32_t line; } Line;
typedef struct { Arena *a; const IrProgram *p; IrCOpts opts; SB out; const char *error; Span at; Line *lines; uint32_t line_count; } Emit;
static void put(Emit *e,const char *fmt,...) BE_PRINTF(2,3);
static void put(Emit *e,const char *fmt,...) {
    if(e->error)return;
    va_list args;va_start(args,fmt);va_list copy;va_copy(copy,args);
    int n=vsnprintf(NULL,0,fmt,copy);va_end(copy);
    if(n<0 || (uint32_t)n>e->opts.max_output_bytes-e->out.len){e->error="C output budget exceeded";va_end(args);return;}
    sb_vfmt(&e->out,fmt,args);va_end(args);
}
static Str fmt(Emit *e,const char *format,...) BE_PRINTF(2,3);
static Str fmt(Emit *e,const char *format,...) {SB b;sb_init(&b,e->a);va_list args;va_start(args,format);sb_vfmt(&b,format,args);va_end(args);return sb_finish(&b);}
static Str type(Emit *e,IrType t){return t==IR_VOID?STR_LIT("void"):t==IR_BOOL?STR_LIT("bool"):t==IR_I32?STR_LIT("int32_t"):t==IR_F32?STR_LIT("float"):fmt(e,"be_ir_t_%u",t);}
static Str quote(Emit *e,Str s){
    SB b;sb_init(&b,e->a);sb_char(&b,'"');
    for(uint32_t i=0;i<s.len;i++){unsigned char c=(unsigned char)s.ptr[i];
        if(c=='"'||c=='\\'||c=='?'){sb_char(&b,'\\');sb_char(&b,(char)c);}
        else if(c<32||c>=127)sb_fmt(&b,"\\%03o",c);else sb_char(&b,(char)c);
    }sb_char(&b,'"');return sb_finish(&b);
}
static int line_compare(const void *a,const void *b){const Line *x=a,*y=b;if(x->at.file!=y->at.file)return x->at.file<y->at.file?-1:1;return x->at.offset==y->at.offset?0:x->at.offset<y->at.offset?-1:1;}
static void prepare_lines(Emit *e){
    e->line_count=e->p->instructions.len+e->p->functions.len;e->lines=ARENA_ARRAY(e->a,Line,e->line_count);uint32_t n=0;
    for(uint32_t i=0;i<e->p->instructions.len;i++)e->lines[n++].at=e->p->instructions.data[i].source.origin;
    for(uint32_t i=0;i<e->p->functions.len;i++)e->lines[n++].at=e->p->functions.data[i].declaration;
    qsort(e->lines,e->line_count,sizeof(Line),line_compare);uint32_t file=IR_NONE,offset=0,line_number=1;
    for(uint32_t i=0;i<e->line_count;i++){Line *q=&e->lines[i];if(file!=q->at.file){file=q->at.file;offset=0;line_number=1;}
        Str text=e->p->sources.data[file].text;while(offset<q->at.offset){if(text.ptr[offset]=='\n')line_number++;offset++;}q->line=line_number;
    }
}
static uint32_t line(Emit *e,Span s){Line key={.at=s};Line *found=bsearch(&key,e->lines,e->line_count,sizeof(Line),line_compare);return found?found->line:1;}
static Str site(Emit *e,Span s,bool traced){return traced?fmt(e,"be_ir_file_%u, %u, %u, %u",s.file,line(e,s),s.file,s.offset):fmt(e,"be_ir_file_%u, %u",s.file,line(e,s));}
static void event(Emit *e,const char *kind,Span s,Str flag){if(e->opts.trace_tests)put(e,"beryl_test_event(\"%s\", %u, %u, %.*s);\n",kind,s.file,s.offset,S(flag));}
/* Static field projections are formed at the instruction, because their parent
 * may be an indexed place whose definition has not run at function entry. */
static Str pointer(Emit *e,uint32_t id){const IrPlace *p=&e->p->places.data[id];if(p->parent==IR_NONE||p->definition!=IR_NONE)return fmt(e,"p_%u",id);Str parent=pointer(e,p->parent);return fmt(e,"&((%.*s)->f_%u)",S(parent),p->field);}
static void signature(Emit *e,uint32_t fn){const IrFunction *f=&e->p->functions.data[fn];put(e,"static %.*s be_ir_fn_%u(",S(type(e,f->result)),fn);if(!f->parameters)put(e,"void");for(uint32_t a=0;a<f->parameters;a++){const IrPlace *p=&e->p->places.data[f->places_start+a];bool ptr=p->mode==IR_INOUT||p->mode==IR_SET||p->type>=IR_FIRST_AGGREGATE;put(e,"%s%s%.*s%s arg_%u",a?", ":"",ptr&&(p->mode==IR_LET||p->mode==IR_SINK)?"const ":"",S(type(e,p->type)),ptr?" *":"",a);}put(e,")");}
static void numeric(Emit *e,const IrInstruction *i){
    IrType t=e->p->values.data[i->a].type;Str at=site(e,i->source.origin,e->opts.trace_tests);
    const char *ops[]={"-","!","~","+","-","*","/","%","&","|","^","==","!=","<","<=",">",">=","<<",">>"};
    if(i->op==IR_UNARY){
        if(i->numeric==IR_NEG&&t==IR_I32)put(e,"v_%u = be_neg_i32%s(v_%u, %.*s);\n",i->result,e->opts.trace_tests?"_at":"",i->a,S(at));
        else if(i->numeric==IR_BIT_NOT)put(e,"v_%u = be_ir_i32(~(uint32_t)v_%u);\n",i->result,i->a);
        else put(e,"v_%u = %sv_%u;\n",i->result,ops[i->numeric],i->a);
        return;
    }
    if(t==IR_F32&&i->numeric>=IR_ADD&&i->numeric<=IR_DIV){put(e,"v_%u = be_ir_finite(v_%u %s v_%u, %.*s);\n",i->result,i->a,ops[i->numeric],i->b,S(site(e,i->source.origin,false)));return;}
    if(t==IR_I32&&i->numeric>=IR_ADD&&i->numeric<=IR_REM){const char *names[]={"add","sub","mul","div","rem"};put(e,"v_%u = be_%s_i32%s(v_%u, v_%u, %.*s);\n",i->result,names[i->numeric-IR_ADD],e->opts.trace_tests?"_at":"",i->a,i->b,S(at));return;}
    if(i->numeric>=IR_BIT_AND&&i->numeric<=IR_BIT_XOR){put(e,"v_%u = be_ir_i32((uint32_t)v_%u %s (uint32_t)v_%u);\n",i->result,i->a,ops[i->numeric],i->b);return;}
    if(i->numeric==IR_SHL||i->numeric==IR_SHR){put(e,"v_%u = be_ir_shift(v_%u, v_%u, %s, %.*s);\n",i->result,i->a,i->b,i->numeric==IR_SHR?"true":"false",S(site(e,i->source.origin,false)));return;}
    put(e,"v_%u = v_%u %s v_%u;\n",i->result,i->a,ops[i->numeric],i->b);
}
static void intrinsic(Emit *e,const IrInstruction *i){
    const IrArgument *a=e->p->arguments.data+i->args_start;uint32_t x=a[0].value,y=i->args_count>1?a[1].value:0,z=i->args_count>2?a[2].value:0;
    switch(i->intrinsic){
        case IR_MIN:case IR_MAX:put(e,"v_%u = v_%u %s v_%u ? v_%u : v_%u;\n",i->result,x,i->intrinsic==IR_MIN?"<":">",y,x,y);break;
        case IR_CLAMP:put(e,"v_%u = v_%u < v_%u ? v_%u : v_%u > v_%u ? v_%u : v_%u;\n",i->result,x,y,y,x,z,z,x);break;
        case IR_ABS:if(e->p->values.data[x].type==IR_F32)put(e,"v_%u = fabsf(v_%u);\n",i->result,x);else put(e,"v_%u = v_%u < 0 ? be_neg_i32%s(v_%u, %.*s) : v_%u;\n",i->result,x,e->opts.trace_tests?"_at":"",x,S(site(e,i->source.origin,e->opts.trace_tests)),x);break;
        case IR_WRAP_ADD:case IR_WRAP_SUB:case IR_WRAP_MUL:put(e,"v_%u = be_ir_i32((uint32_t)((uint64_t)(uint32_t)v_%u %s (uint32_t)v_%u));\n",i->result,x,i->intrinsic==IR_WRAP_ADD?"+":i->intrinsic==IR_WRAP_SUB?"-":"*",y);break;
        case IR_SAT_ADD:case IR_SAT_SUB:put(e,"v_%u = be_%s_i32(v_%u, v_%u);\n",i->result,i->intrinsic==IR_SAT_ADD?"satadd":"satsub",x,y);break;
    }
}
static void region(Emit *e,uint32_t id,uint32_t loop){
    for(uint32_t n=e->p->regions.data[id].first;n!=IR_NONE&&!e->error;n=e->p->instructions.data[n].next){
        const IrInstruction *i=&e->p->instructions.data[n];e->at=i->source.origin;
        put(e,"/* ir:%u source:%u:%u */\nbe_ir_tick(%.*s);\n",n,i->source.origin.file,i->source.origin.offset,S(site(e,i->source.origin,false)));
        switch(i->op){
            case IR_CONST:if(e->p->values.data[i->result].type==IR_F32)put(e,"v_%u = be_ir_float(UINT32_C(%u));\n",i->result,i->float_bits);else put(e,"v_%u = (int32_t)INT64_C(%lld);\n",i->result,(long long)i->immediate);break;
            case IR_LOAD:case IR_MOVE:put(e,"v_%u = *(%.*s);\n",i->result,S(pointer(e,i->place)));break;
            case IR_INIT:put(e,"root_%u = v_%u;\n",i->place,i->a);break;
            case IR_STORE:put(e,"*(%.*s) = v_%u;\n",S(pointer(e,i->place)),i->a);break;
            case IR_UNARY:case IR_BINARY:numeric(e,i);break;
            case IR_CAST:
                if(e->p->values.data[i->result].type==IR_F32)put(e,"v_%u = be_ir_finite((float)v_%u, %.*s);\n",i->result,i->a,S(site(e,i->source.origin,false)));
                else if(e->p->values.data[i->a].type==IR_F32)put(e,"v_%u = be_ir_cast(v_%u, %.*s);\n",i->result,i->a,S(site(e,i->source.origin,false)));
                else put(e,"v_%u = v_%u;\n",i->result,i->a);break;
            case IR_INTRINSIC:intrinsic(e,i);break;
            case IR_CALL:{
                if(i->result!=IR_NONE)put(e,"v_%u = ",i->result);put(e,"be_ir_fn_%u(",i->function);
                for(uint32_t a=0;a<i->args_count;a++){const IrArgument *arg=&e->p->arguments.data[i->args_start+a];if(a)put(e,", ");
                    if(arg->by_place)put(e,"%.*s",S(pointer(e,e->p->instructions.data[arg->capture].place)));
                    else put(e,"%sv_%u",e->p->values.data[arg->value].type>=IR_FIRST_AGGREGATE?"&":"",arg->value);
                }put(e,");\n");break;
            }
            case IR_RECORD:case IR_ARRAY:{
                put(e,"v_%u = (%.*s){0};\n",i->result,S(type(e,e->p->values.data[i->result].type)));
                for(uint32_t a=0;a<i->args_count;a++){const IrArgument *arg=&e->p->arguments.data[i->args_start+a];if(i->op==IR_RECORD)put(e,"v_%u.f_%u = v_%u;\n",i->result,arg->field,arg->value);else put(e,"v_%u.items[%u] = v_%u;\n",i->result,a,arg->value);}break;
            }
            case IR_FIELD:put(e,"v_%u = v_%u.f_%u;\n",i->result,i->a,i->place);break;
            case IR_INDEX_VALUE:case IR_INDEX_PLACE:{
                bool place=i->op==IR_INDEX_PLACE;uint32_t parent=place?e->p->places.data[i->place].parent:IR_NONE;
                IrType t=place?e->p->places.data[parent].type:e->p->values.data[i->a].type;const IrAggregate *a=&e->p->aggregates.data[t-IR_FIRST_AGGREGATE];
                uint32_t index=place?i->a:i->b;
                put(e,"int64_t index_%u = be_idx%s(v_%u, %u, %.*s);\n",n,e->opts.trace_tests?"_at":"",index,a->length,S(site(e,i->source.origin,e->opts.trace_tests)));
                if(a->length){if(place)put(e,"p_%u = &((%.*s)->items[index_%u]);\n",i->place,S(pointer(e,parent)),n);else put(e,"v_%u = v_%u.items[index_%u];\n",i->result,i->a,n);}
                else put(e,"(void)index_%u; /* zero logical length: check cannot return */\n",n);
                break;
            }
            case IR_DECLARE:case IR_CAPTURE:case IR_DESTINATION:case IR_INDEX_BASE:put(e,"/* Verified stable place interval; no value evaluation. */\n");break;
            case IR_IF:put(e,"if(v_%u) {\n",i->a);region(e,i->child[0],loop);put(e,"} else {\n");region(e,i->child[1],loop);put(e,"}\n");break;
            case IR_LOOP:put(e,"while(true) {\n");region(e,i->child[0],n);region(e,i->child[1],n);put(e,"continue_%u:;\n",n);region(e,i->child[2],n);put(e,"}\nbreak_%u:;\n",n);break;
            case IR_YIELD:put(e,"if(!v_%u) goto break_%u;\n",i->a,loop);break;
            case IR_BREAK:put(e,"goto break_%u;\n",loop);break;
            case IR_CONTINUE:put(e,"goto continue_%u;\n",loop);break;
            case IR_RETURN:put(e,"be_ir_depth--;\nreturn");if(i->a!=IR_NONE)put(e," v_%u",i->a);put(e,";\n");break;
            case IR_PRINT:
                event(e,"print",i->source.origin,i->flag?STR_LIT("true"):STR_LIT("false"));
                for(uint32_t a=0;a<i->args_count;a++){const IrArgument *arg=&e->p->arguments.data[i->args_start+a];IrType t=e->p->values.data[arg->value].type;
                    if(t==IR_F32&&e->opts.trace_tests)put(e,"beryl_test_f32(%u, %u, v_%u);\n",arg->source.file,arg->source.offset,arg->value);
                    put(e,"beryl_print_%s(v_%u);\n",t==IR_F32?"f64":t==IR_BOOL?"bool":"i64",arg->value);
                }if(i->flag)put(e,"beryl_newline();\n");break;
            case IR_ASSERT:{uint32_t a=e->p->arguments.data[i->args_start].value;event(e,"assert",i->source.origin,fmt(e,"v_%u",a));put(e,"beryl_test_assert(v_%u, \"assertion\", %.*s);\n",a,S(site(e,i->source.origin,false)));break;}
        }
    }
}
IrCResult ir_emit_c(Arena *a,const IrProgram *p,IrCOpts opts){
    IrVerification v=ir_verify(p);if(!v.ok)return(IrCResult){.error=v.source,.reason=v.reason};
    if(!opts.max_output_bytes)opts.max_output_bytes=16u*1024u*1024u;
    if(opts.max_output_bytes>64u*1024u*1024u)return(IrCResult){.error=SPAN_NONE,.reason="C output maximum is 64 MiB"};
    uint32_t tests=0;for(uint32_t n=0;n<p->functions.len;n++)if(p->functions.data[n].test)tests++;
    if(!tests)return(IrCResult){.error=SPAN_NONE,.reason="experimental C emitter requires at least one test"};
    for(uint32_t n=0;n<p->functions.len;n++){
        const IrFunction *f=&p->functions.data[n];
        if(f->identity.len>32768||(f->identity.len&&!f->identity.ptr))return(IrCResult){.error=f->declaration,.reason="C test identity storage or size"};
        uint64_t frame=(uint64_t)f->places_count*8+(uint64_t)f->parameters*8;
        for(uint32_t j=0;j<f->places_count;j++){const IrPlace *q=&p->places.data[f->places_start+j];if(q->parent==IR_NONE)frame+=(uint64_t)ir_type_cells(p,q->type)*4;}
        for(uint32_t j=0;j<f->values_count;j++)frame+=(uint64_t)ir_type_cells(p,p->values.data[f->values_start+j].type)*4;
        for(uint32_t j=0;j<p->instructions.len;j++){const IrInstruction *i=&p->instructions.data[j];if(p->regions.data[i->region].function==n&&(i->op==IR_INDEX_PLACE||i->op==IR_INDEX_VALUE))frame+=8;}
        /* Bounded estimate for declared objects, not a compiler stack-layout proof. */
        if(frame>65536)return(IrCResult){.error=f->declaration,.reason="C test function exceeds 64 KiB declared-storage admission"};
    }
    Emit e={.a=a,.p=p,.opts=opts,.at=SPAN_NONE};sb_init(&e.out,a);
    prepare_lines(&e);
    put(&e,"/* Experimental schema5 IR test harness. No production ABI. */\n#include \"beryl_rt.h\"\n#include <math.h>\n#include <string.h>\n#include <float.h>\n#include <stdio.h>\n"
        "_Static_assert(sizeof(float)==4 && FLT_RADIX==2 && FLT_MANT_DIG==24 && FLT_MAX_EXP==128 && FLT_EVAL_METHOD==0, \"binary32 evaluation required\");\n"
        "#if defined(__FAST_MATH__) || (defined(__FINITE_MATH_ONLY__) && __FINITE_MATH_ONLY__)\n#error IR C requires finite checks and strict arithmetic\n#endif\n#pragma STDC FP_CONTRACT OFF\n"
        "static uint64_t be_ir_steps; static uint32_t be_ir_depth;\n"
        "static _Noreturn void be_ir_domain(const char *why,const char *f,int l){fflush(stdout);fflush(stderr);beryl_panic(why,f,l);}\n"
        "static void be_ir_tick(const char *f,int l){if(be_ir_steps++>=UINT64_C(1000000))be_ir_domain(\"IR step budget\",f,l);}\n"
        "static void be_ir_enter(const char *f,int l){if(be_ir_depth>=128)be_ir_domain(\"IR call depth\",f,l);be_ir_depth++;}\n"
        "static int32_t be_ir_i32(uint32_t u){return u<=INT32_MAX?(int32_t)u:(int32_t)((int64_t)u-INT64_C(4294967296));}\n"
        "static float be_ir_float(uint32_t bits){float x;memcpy(&x,&bits,4);return x;}\n"
        "static float be_ir_finite(float x,const char *f,int l){volatile float y=x;if(!isfinite(y))be_ir_domain(\"outside finite IR domain\",f,l);return y;}\n"
        "static int32_t be_ir_cast(float x,const char *f,int l){if(!isfinite(x)||(double)x<(double)INT32_MIN||(double)x>=2147483648.0)be_ir_domain(\"outside IR cast domain\",f,l);return (int32_t)x;}\n"
        "static int32_t be_ir_shift(int32_t x,int32_t n,bool right,const char *f,int l){if(n<0||n>=32)be_ir_domain(\"outside IR shift domain\",f,l);uint32_t u=(uint32_t)x;if(right){u>>=(unsigned)n;if(x<0&&n)u|=(uint32_t)(UINT64_C(0xffffffff)<<(32-(unsigned)n));}else u=(uint32_t)((uint64_t)u<<(unsigned)n);return be_ir_i32(u);}\n");
    for(uint32_t n=0;n<p->sources.len;n++)put(&e,"static const char be_ir_file_%u[] = %.*s;\n",n,S(quote(&e,p->sources.data[n].path)));
    for(uint32_t n=0;n<p->aggregates.len;n++){
        const IrAggregate *t=&p->aggregates.data[n];put(&e,"typedef struct {\n");
        if(t->kind==IR_TYPE_RECORD){if(!t->fields_count)put(&e,"unsigned char empty;\n");for(uint32_t j=0;j<t->fields_count;j++){uint32_t field=t->fields_start+j;put(&e,"%.*s f_%u;\n",S(type(&e,p->fields.data[field].type)),field);}}
        else if(t->length)put(&e,"%.*s items[%u];\n",S(type(&e,t->element)),t->length);else put(&e,"unsigned char empty;\n");
        put(&e,"} be_ir_t_%u;\n",n+IR_FIRST_AGGREGATE);
    }
    for(uint32_t n=0;n<p->functions.len;n++){signature(&e,n);put(&e,";\n");}
    for(uint32_t n=0;n<p->functions.len&&!e.error;n++){
        const IrFunction *f=&p->functions.data[n];signature(&e,n);put(&e," {\nbe_ir_enter(%.*s);\n",S(site(&e,f->declaration,false)));
        for(uint32_t q=0;q<f->places_count;q++){
            uint32_t id=f->places_start+q;const IrPlace *p1=&p->places.data[id];
            if(p1->parent!=IR_NONE){if(p1->definition!=IR_NONE)put(&e,"%s%.*s *p_%u = NULL;\n",p1->mutable?"":"const ",S(type(&e,p1->type)),id);continue;}
            bool borrowed=q<f->parameters&&(p1->mode==IR_INOUT||p1->mode==IR_SET||(p1->mode==IR_LET&&p1->type>=IR_FIRST_AGGREGATE));
            if(!borrowed){put(&e,"%.*s root_%u",S(type(&e,p1->type)),id);if(q<f->parameters)put(&e," = %sarg_%u",p1->type>=IR_FIRST_AGGREGATE?"*":"",q);put(&e,";\n");}
            put(&e,"%s%.*s *p_%u = ",p1->parameter&&p1->mode==IR_LET?"const ":"",S(type(&e,p1->type)),id);if(borrowed)put(&e,"arg_%u;\n",q);else put(&e,"&root_%u;\n",id);
        }
        for(uint32_t q=0;q<f->values_count;q++){uint32_t id=f->values_start+q;put(&e,"%.*s v_%u;\n",S(type(&e,p->values.data[id].type)),id);}
        region(&e,f->body,IR_NONE);put(&e,"}\n");
    }
    put(&e,"int main(void){\n");if(opts.trace_tests)put(&e,"beryl_test_trace_enable();\n");
    for(uint32_t n=0;n<p->functions.len;n++){const IrFunction *f=&p->functions.data[n];if(!f->test)continue;put(&e,"beryl_test_begin(%.*s);\n",S(quote(&e,f->identity)));event(&e,"test_begin",f->declaration,STR_LIT("true"));put(&e,"be_ir_fn_%u();\n",n);event(&e,"test_end",f->declaration,STR_LIT("beryl_test_current_ok()"));}
    put(&e,"return beryl_test_summary();\n}\n");
    if(e.error)return(IrCResult){.error=e.at,.reason=e.error};
    return(IrCResult){.ok=true,.source=sb_finish(&e.out),.error=SPAN_NONE};
}
