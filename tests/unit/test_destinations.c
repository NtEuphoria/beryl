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

static void call_case(const char *name,const char *body,bool accepted) {
    CASE(name);
    Arena *a=arena_new(0); SourceMap *sm=srcmap_new(a); DiagBag *d=diag_new(a,sm);
    Interner *in=intern_new(a); Program *p=prog_new(a);
    SB text; sb_init(&text,a);
    sb_fmt(&text,"module t\nstruct R { x: i32, y: i32 }\n"
        "struct P { child: R, other: R }\n"
        "fn replace(inout p: P) -> i32 { p = P{child: R{x: 9, y: 8}, other: R{x: 7, y: 6}}\nreturn 0 }\n"
        "fn replace_array(inout xs: [R; 2]) -> i32 { xs = [R{x: 9, y: 8}, R{x: 7, y: 6}]\nreturn 0 }\n"
        "fn bump(inout n: i32) -> i32 { n += 1\nreturn n }\n"
        "fn fill(set n: i32) -> i32 { n = 5\nreturn 0 }\n"
        "fn consume(sink p: P) -> i32 { return p.child.x }\n"
        "fn move_after(let r: R, sink p: P) -> i32 { return r.x + p.other.x }\n"
        "fn observe(let r: R, n: i32) -> i32 { return r.x + n }\n"
        "fn change(inout n: i32, tag: i32) { n += 1 }\n"
        "fn out(set n: i32, tag: i32) { n = tag }\n"
        "fn R.observe(let self, n: i32) -> i32 { return self.x + n }\n"
        "fn R.change(inout self, n: i32) { self.x = n }\n"
        "fn scalar(n: i32, tag: i32) -> i32 { return n + tag }\n"
        "fn wrap(n: i32) -> i32 { return n }\n"
        "fn defaulted(let r: R, n: i32 = wrap(0)) -> i32 { return r.x + n }\n"
        "fn mutate_bool(inout p: P) -> bool { replace(inout p)\nreturn true }\n"
        "fn bool_to_int(value: bool) -> i32 { if value { return 1 }\nreturn 0 }\n"
        "test \"call\" { var p = P{child: R{x: 1, y: 2}, other: R{x: 3, y: 4}}\n%s\n}\n",body);
    uint32_t file=srcmap_add(sm,STR_LIT("call_captures.be"),sb_finish(&text));
    TokenVec tokens=lex_file(a,sm,d,in,file); prog_add_module(p,parse_file(a,d,in,tokens,file));
    bool typed=!diag_errors(d) && resolve_program(d,p) && check_program(d,p);
    CHECK(typed);
    if (typed) {
        bool result=ownership_check(d,p); CHECK_EQ_I(result,accepted);
        if (!accepted) {
            Str errors=diag_render_str(a,d);
            CHECK_CONTAINS(errors,"BE0401"); CHECK_CONTAINS(errors,"captured call argument");
            CHECK_CONTAINS(errors,"separate binding");
        }
    }
    if (diag_errors(d) && (!typed || accepted)) { Str errors=diag_render_str(a,d); printf("%.*s\n",(int)errors.len,errors.ptr); }
    arena_free(a);
}
void run_call_capture_tests(void) {
    call_case("call capture: projected record then root replacement", "observe(p.child, replace(inout p))",false);
    call_case("call capture: whole record then field write", "observe(p.child, bump(inout p.child.x))",false);
    call_case("call capture: fixed array element then root replacement", "var xs = [p.child, p.other]\nobserve(xs[0], replace_array(inout xs))",false);
    call_case("call capture: projected inout then parent replacement", "change(inout p.child.x, replace(inout p))",false);
    call_case("call capture: projected set then parent replacement", "out(set p.child.x, replace(inout p))",false);
    call_case("call capture: implicit let receiver", "p.child.observe(replace(inout p))",false);
    call_case("call capture: implicit inout receiver", "p.child.change(replace(inout p))",false);
    call_case("call capture: nested user call", "observe(p.child, wrap(wrap(replace(inout p))))",false);
    call_case("call capture: later set effect", "observe(p.child, fill(set p.child.x))",false);
    call_case("call capture: later sink effect", "observe(p.child, consume(sink p))",false);
    call_case("call capture: direct later sink", "move_after(p.child, sink p)",false);
    call_case("call capture: selection index cannot replace parent", "var xs = [p.child, p.other]\nobserve(xs[replace_array(inout xs)], 0)",false);
    call_case("call capture: potentially skipped block", "if false { observe(p.child, replace(inout p)) }",false);
    call_case("call capture: dynamic indices remain conservative", "var xs = [p.child, p.other]\nlet i = 0\nlet j = 1\nobserve(xs[i], bump(inout xs[j].x))",false);
    call_case("call capture: conservative unreachable call", "return\nobserve(p.child, replace(inout p))",false);
    call_case("call capture: potentially skipped effect", "observe(p.child, bool_to_int(false && mutate_bool(inout p)))",false);
    call_case("call capture: scalar let captured by value", "scalar(p.child.x, replace(inout p))",true);
    call_case("call capture: unrelated index variable", "var xs = [p.child, p.other]\nvar i = -1\nobserve(xs[bump(inout i)], 0)",true);
    call_case("call capture: disjoint plain fields", "observe(p.child, bump(inout p.other.x))",true);
    call_case("call capture: disjoint constant indices", "var xs = [p.child, p.other]\nobserve(xs[0], bump(inout xs[1].x))",true);
    call_case("call capture: explicit snapshot before mutation", "let snapshot = p.child\nobserve(snapshot, replace(inout p))",true);
    call_case("call capture: mutation before selection", "let result = replace(inout p)\nobserve(p.child, result)",true);
    call_case("call capture: temporary aggregate already detached", "observe(R{x: p.child.x, y: p.child.y}, replace(inout p))",true);
    call_case("call capture: expanded pure default", "defaulted(p.child)",true);
    call_case("call capture: independent sink temporary", "move_after(p.child, sink P{child: R{x: 7, y: 8}, other: R{x: 5, y: 6}})",true);

    CASE("call capture: bounded direct API refuses exhausted budget");
    Type i32={.kind=TY_INT,.bits=32,.is_signed=true}; Local local={.type=&i32};
    Expr root={.kind=EX_PATH,.res_kind=RES_LOCAL,.res=&local,.type=&i32};
    Param params[2]={{.conv=CONV_INOUT},{.conv=CONV_LET}};
    Arg args[2]={{.conv=CONV_INOUT,.value=&root},{.conv=CONV_LET,.value=&root}};
    Item fn={.kind=IT_FN}; fn.fn.params.data=params; fn.fn.params.len=2;
    Expr call={.kind=EX_CALL,.res_kind=RES_FN,.res=&fn}; call.call.args.data=args; call.call.args.len=2;
    uint32_t visits=ACCESS_MAX_VISITS;
    AccessResult result=access_call_arguments(&call,&visits);
    CHECK_EQ_I(result.status,ACCESS_UNPROVEN); CHECK_EQ_I(visits,ACCESS_MAX_VISITS); CHECK(result.call_argument);
}
