#include "src/parse/parser.h"
#include "src/sema/check.h"
#include "src/sema/ownership.h"
#include "src/reference/reference.h"
#include "src/back/c_backend.h"
#include "src/ir/c_emit.h"
#include "src/common/fs.h"
#include "src/driver/process.h"
#include <string.h>
#include <stdlib.h>
static void die(const char *s){fprintf(stderr,"probe: %s\n",s);exit(2);}
static FILE *open_file(Arena *a,const char *dir,const char *name){FILE *f=fs_open(fs_join(a,dir,name),"wb");if(!f)die("open evidence");return f;}
static void close_file(FILE *f){if(fclose(f))die("close evidence");}
static void diagnostic(Arena *a,DiagBag *d){Str s=diag_render_str(a,d);fprintf(stderr,"%.*s",(int)s.len,s.ptr);die("frontend/emitter rejected source");}
int main(int argc,char **argv){
    if(argc<5)die("usage probe output clang runtime source...");
    process_install_signals();
    Arena *ast=arena_new(0),*a=arena_new(0);SourceMap *sm=srcmap_new(ast);DiagBag *d=diag_new(ast,sm);Program *p=prog_new(ast);Interner *in=intern_new(ast);
    for(int n=4;n<argc;n++){Str text;if(!fs_read(ast,argv[n],&text))die("read source");uint32_t id=srcmap_add(sm,str_from(argv[n]),text);TokenVec tokens=lex_file(ast,sm,d,in,id);prog_add_module(p,parse_file(ast,d,in,tokens,id));}
    if(diag_errors(d)||!resolve_program(d,p)||!check_program(d,p)||!ownership_check(d,p))diagnostic(ast,d);
    Str astc=cgen_program(ast,sm,d,p,CGEN_TRACE_TESTS);if(!astc.len||diag_errors(d))diagnostic(ast,d);
    if(!fs_write(fs_join(a,argv[1],"ast.c"),astc))die("write AST C");
    IrProgram *ir=ir_lower(a,d,sm,p);if(!ir)diagnostic(ast,d);
    FILE *refout=open_file(a,argv[1],"reference.stdout"),*refevents=open_file(a,argv[1],"reference.events");
    RefResult reference=reference_test(d,p,(RefOpts){.output=refout,.events=refevents});close_file(refout);close_file(refevents);
    arena_free(ast); /* emission/evaluation now have no AST/type/source storage */
    IrCResult c=ir_emit_c(a,ir,(IrCOpts){.trace_tests=true}),again=ir_emit_c(a,ir,(IrCOpts){.trace_tests=true});
    if(!c.ok||!again.ok||!str_eq(c.source,again.source))die(c.reason?c.reason:"nondeterministic emission");
    if(!fs_write(fs_join(a,argv[1],"ir.c"),c.source))die("write IR C");
    unsigned mutants=0;
    IrCResult tiny=ir_emit_c(a,ir,(IrCOpts){.trace_tests=true,.max_output_bytes=1});if(tiny.ok||tiny.source.len)die("output budget mutant admitted");mutants++;
    tiny=ir_emit_c(a,ir,(IrCOpts){.max_output_bytes=UINT32_MAX});if(tiny.ok||tiny.source.len)die("oversized configuration admitted");mutants++;
    uint32_t schema=ir->schema_version;ir->schema_version++;tiny=ir_emit_c(a,ir,(IrCOpts){0});ir->schema_version=schema;if(tiny.ok||tiny.source.len)die("schema mutant admitted");mutants++;
    IrInstruction saved=ir->instructions.data[0];ir->instructions.data[0].op=(IrOp)-1;tiny=ir_emit_c(a,ir,(IrCOpts){0});ir->instructions.data[0]=saved;if(tiny.ok||tiny.source.len)die("opcode mutant admitted");mutants++;
    ir->instructions.data[0].source.origin.offset=UINT32_MAX;tiny=ir_emit_c(a,ir,(IrCOpts){0});ir->instructions.data[0]=saved;if(tiny.ok||tiny.source.len)die("source mutant admitted");mutants++;
    Str identity=ir->functions.data[0].identity;ir->functions.data[0].identity=(Str){.len=1,.ptr=NULL};tiny=ir_emit_c(a,ir,(IrCOpts){0});ir->functions.data[0].identity=identity;if(tiny.ok||tiny.source.len)die("test identity mutant admitted");mutants++;
    FILE *irout=open_file(a,argv[1],"ir-eval.stdout"),*irevents=open_file(a,argv[1],"ir-eval.events");
    IrRunResult result=ir_test(ir,(IrRunOpts){.output=irout,.events=irevents});close_file(irout);close_file(irevents);
    FILE *summary=open_file(a,argv[1],"probe.json");
    fprintf(summary,"{\"reference_status\":%u,\"reference_trap\":%u,\"reference_complete\":%s,\"reference_steps\":%llu,\"ir_status\":%u,\"ir_trap\":%u,\"ir_complete\":%s,\"ir_steps\":%llu,\"tests\":%u,\"assertions\":%llu,\"mutants_rejected\":%u,\"processes\":[",reference.status,reference.trap_kind,reference.trap_trace_complete?"true":"false",(unsigned long long)reference.steps,result.status,result.trap,result.trace_complete?"true":"false",(unsigned long long)result.steps,result.tests,(unsigned long long)result.assertions,mutants);
    for(unsigned emitter=0;emitter<2;emitter++)for(unsigned opt=0;opt<2;opt++){
        char name[60];snprintf(name,sizeof name,"%s-O%u",emitter?"ir":"ast",opt?2:0);char exe[70];snprintf(exe,sizeof exe,"%s.exe",name);
        if(emitter||opt)fputc(',',summary);
        if(!emitter&&((result.status==IR_RUN_TRAP&&result.trap==IR_TRAP_NONE)||result.status==IR_RUN_BUDGET)){
            fprintf(summary,"{\"name\":\"%s\",\"skipped\":\"outside AST-C admitted execution domain\"}",name);continue;
        }
        const char *exepath=fs_join(a,argv[1],exe),*cpath=fs_join(a,argv[1],emitter?"ir.c":"ast.c");
        const char *compile[]={argv[2],"-std=c11",opt?"-O2":"-O0","-ffp-contract=off","-fno-fast-math","-fsanitize=undefined","-fno-sanitize-recover=all","-I",argv[3],cpath,fs_join(a,argv[3],"beryl_rt.c"),"-o",exepath,NULL};
        char logname[90];snprintf(logname,sizeof logname,"%s-compile",name);ProcessResult built=process_run(a,(ProcessOpts){.argv=compile,.log_dir=argv[1],.log_name=logname,.timeout_ms=120000});
        fprintf(summary,"{\"name\":\"%s\",\"compile_status\":%u,\"compile_exit\":%u",name,built.status,built.exit_code);
        if(built.status==PROCESS_EXITED&&built.exit_code==0){const char *run[]={exepath,NULL};ProcessResult executed=process_run(a,(ProcessOpts){.argv=run,.log_dir=argv[1],.log_name=name,.timeout_ms=20000});fprintf(summary,",\"run_status\":%u,\"run_exit\":%u",executed.status,executed.exit_code);}
        fputc('}',summary);fflush(summary);
    }
    fprintf(summary,"]}\n");close_file(summary);arena_free(a);return 0;
}
