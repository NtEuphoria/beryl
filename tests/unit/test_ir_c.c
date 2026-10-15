#include "test.h"
#include "../../src/parse/parser.h"
#include "../../src/sema/check.h"
#include "../../src/sema/ownership.h"
#include "../../src/ir/c_emit.h"
#include "../../src/driver/build.h"

void run_ir_c_tests(void) {
    Arena *ast=arena_new(0), *a=arena_new(0);
    SourceMap *sm=srcmap_new(ast); DiagBag *d=diag_new(ast,sm);
    Interner *in=intern_new(ast); Program *p=prog_new(ast);
    uint32_t file=srcmap_add(sm,STR_LIT("ir-c.be"),STR_LIT(
        "module testemit\nstruct R { a: i32 }\n"
        "fn initialize(set xs: [R; 2]) { xs = [R{a:3},R{a:4}] }\n"
        "fn consume(sink xs: [R; 2]) -> i32 { xs[0].a = 12\nreturn xs[0].a }\n"
        "test \"copy\" { let xs: [R; 2]\ninitialize(set xs)\n"
        "var ys = xs\nys[1].a += 5\nassert(xs[1].a == 4)\nassert(ys[1].a == 9)\n"
        "assert(consume(sink ys) == 12)\ninitialize(set ys)\nassert(ys[0].a == 3) }\n"));
    prog_add_module(p,parse_file(ast,d,in,lex_file(ast,sm,d,in,file),file));
    CASE("IR C: emission owns its source after AST release and is deterministic");
    bool valid=!diag_errors(d) && resolve_program(d,p) && check_program(d,p) && ownership_check(d,p);
    CHECK(valid);
    IrProgram *ir=valid?ir_lower(a,d,sm,p):NULL; CHECK(ir!=NULL);
    if (!ir) { arena_free(ast); arena_free(a); return; }
    IrCResult first=ir_emit_c(a,ir,(IrCOpts){.trace_tests=true}); CHECK(first.ok);
    arena_free(ast);
    IrCResult second=ir_emit_c(a,ir,(IrCOpts){.trace_tests=true});
    CHECK(second.ok); CHECK(str_eq(first.source,second.source));

    CASE("IR C: malformed input and output budget never produce usable partial code");
    IrCResult bad=ir_emit_c(a,ir,(IrCOpts){.max_output_bytes=1});
    CHECK(!bad.ok && !bad.source.len);
    uint32_t schema=ir->schema_version; ir->schema_version++;
    bad=ir_emit_c(a,ir,(IrCOpts){0}); CHECK(!bad.ok && !bad.source.len);
    ir->schema_version=schema;

    CASE("IR C: native build rejects incompatible calling conventions before a job");
    sm=srcmap_new(a); d=diag_new(a,sm); BuildResult built;
    BuildOpts options={.requested_lowering="ast",.ir_tests=ir};
    CHECK(!build_native(a,sm,d,NULL,options,&built)); CHECK(built.job_dir==NULL);
    CHECK_CONTAINS(diag_render_str(a,d),"BE1102");
    d=diag_new(a,sm); options.requested_lowering="ir";
    CHECK(!build_native(a,sm,d,NULL,options,&built)); CHECK(built.job_dir==NULL);
    CHECK_CONTAINS(diag_render_str(a,d),"BE1101");

    CASE("IR C: matching native source identity is mandatory before a job");
    d=diag_new(a,sm); options.mode=CGEN_TRACE_TESTS;
    CHECK(!build_native(a,sm,d,NULL,options,&built)); CHECK(built.job_dir==NULL);
    CHECK_CONTAINS(diag_render_str(a,d),"BE1102");
    CASE("IR C: malformed source table is verified before snapshot comparison");
    srcmap_add(sm,STR_LIT("other.be"),STR_LIT("module other\n"));
    d=diag_new(a,sm); IrSourceFile *saved=ir->sources.data; ir->sources.data=NULL;
    CHECK(!build_native(a,sm,d,NULL,options,&built)); CHECK(built.job_dir==NULL);
    CHECK_CONTAINS(diag_render_str(a,d),"BE1102");
    ir->sources.data=saved;
    arena_free(a);
}
