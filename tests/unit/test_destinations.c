#include "test.h"
#include "../../src/parse/parser.h"
#include "../../src/sema/check.h"
#include "../../src/sema/access.h"

static void destination_case(const char *name,const char *body,bool accepted) {
    CASE(name);
    Arena *a=arena_new(0); SourceMap *sm=srcmap_new(a); DiagBag *d=diag_new(a,sm);
    Interner *in=intern_new(a); Program *p=prog_new(a);
    SB text; sb_init(&text,a);
    sb_fmt(&text,"module t\nstruct R { x: i32, y: i32 }\n"
        "fn bump(inout x: i32) -> i32 { x += 1\nreturn x }\n"
        "fn replace(inout r: R, value: i32 = 7) -> i32 { r = R{x: 10, y: 20}\nreturn value }\n"
        "fn R.replace(inout self) -> i32 { self = R{x: 10, y: 20}\nreturn 7 }\n"
        "fn wrap(x: i32) -> i32 { return x }\n"
        "test \"destination\" { var r = R{x: 1, y: 2}\n%s\n}\n",body);
    uint32_t file=srcmap_add(sm,STR_LIT("destinations.be"),sb_finish(&text));
    TokenVec tokens=lex_file(a,sm,d,in,file); prog_add_module(p,parse_file(a,d,in,tokens,file));
    bool typed=!diag_errors(d) && resolve_program(d,p) && check_program(d,p);
    CHECK(typed);
    if (typed) {
        bool result=ownership_check(d,p); CHECK_EQ_I(result,accepted);
        if (!accepted) { CHECK_CONTAINS(diag_render_str(a,d),"BE0401"); CHECK_CONTAINS(diag_render_str(a,d),"projected assignment"); }
    }
    if (diag_errors(d) && (!typed || accepted)) { Str errors=diag_render_str(a,d); printf("%.*s\n",(int)errors.len,errors.ptr); }
    arena_free(a);
}

void run_destination_tests(void) {
    destination_case("destination: root replacement with expanded default", "r.x = replace(inout r)",false);
    destination_case("destination: nested call effects", "r.x = wrap(wrap(replace(inout r)))",false);
    destination_case("destination: implicit mutable receiver", "r.x = r.replace()",false);
    destination_case("destination: compound overlapping scalar", "r.x += bump(inout r.x)",false);
    destination_case("destination: conservative skipped operand", "if false { r.x = replace(inout r) }",false);
    destination_case("destination: unreachable conflict still checked", "return\nr.x = replace(inout r)",false);
    destination_case("destination: dynamic indices fail closed", "var xs = [1, 2]\nlet i = 0\nlet j = 1\nxs[i] = bump(inout xs[j])",false);
    destination_case("destination: disjoint fields preserved", "r.x += bump(inout r.y)",true);
    destination_case("destination: disjoint constant indices preserved", "var xs = [1, 2]\nxs[0] = bump(inout xs[1])",true);
    destination_case("destination: unrelated index side effects preserved", "var xs = [1, 2]\nvar i = -1\nxs[bump(inout i)] += r.x",true);
    destination_case("destination: separate statements preserve storage", "let result = replace(inout r)\nr.x = result",true);
    destination_case("destination: ordinary scalar compound order preserved", "var x = 4\nx += bump(inout x)",true);

    CASE("destination: bounded checker refuses exhausted budget");
    Expr root={.kind=EX_PATH,.res_kind=RES_LOCAL},field={.kind=EX_FIELD};
    Local local={0}; root.res=&local; field.field.base=&root;
    Stmt assignment={.kind=ST_ASSIGN}; assignment.assign.target=&field;
    uint32_t visits=ACCESS_MAX_VISITS;
    AccessResult result=access_projected_assignment(&assignment,&visits);
    CHECK_EQ_I(result.status,ACCESS_UNPROVEN); CHECK_EQ_I(visits,ACCESS_MAX_VISITS);
}
