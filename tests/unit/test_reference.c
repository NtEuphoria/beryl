#include "test.h"
#include "../../src/parse/parser.h"
#include "../../src/sema/check.h"
#include "../../src/sema/ownership.h"
#include "../../src/reference/reference.h"

static void run_case_impl(bool check_ownership,const char *name,const char *source,RefOpts opts,RefStatus expected,
                     uint64_t assertions,const char *diagnostic) {
    CASE(name);
    Arena *a=arena_new(0); SourceMap *sm=srcmap_new(a); DiagBag *d=diag_new(a,sm);
    Interner *in=intern_new(a); Program *p=prog_new(a);
    uint32_t id=srcmap_add(sm,str_from("reference.be"),str_from(source));
    TokenVec tokens=lex_file(a,sm,d,in,id); prog_add_module(p,parse_file(a,d,in,tokens,id));
    bool ok=!diag_errors(d) && resolve_program(d,p) && check_program(d,p) && (!check_ownership || ownership_check(d,p));
    CHECK(ok);
    if (!ok) { Str out=diag_render_str(a,d); printf("%.*s\n",(int)out.len,out.ptr); arena_free(a); return; }
    FILE *output=tmpfile(),*events=tmpfile(); CHECK(output && events);
    if (output && events) {
        opts.output=output; opts.events=events;
        RefResult result=reference_test(d,p,opts);
        CHECK_EQ_I(result.status,expected);
        if (expected==REF_SUCCESS) CHECK_EQ_I(result.assertions,assertions);
        if (diagnostic) CHECK_CONTAINS(diag_render_str(a,d),diagnostic);
        if (result.status!=expected) { Str out=diag_render_str(a,d); printf("%.*s\n",(int)out.len,out.ptr); }
        if (expected==REF_SUCCESS) {
            CHECK(result.tests>0); CHECK(result.steps>0); CHECK(result.bytes>0);
            CHECK(fseek(events,0,SEEK_END)==0); CHECK(ftell(events)>0);
        } else if (expected==REF_UNAVAILABLE) {
            CHECK_EQ_I(result.tests,0); CHECK_EQ_I(result.steps,0);
            CHECK(fseek(events,0,SEEK_END)==0); CHECK_EQ_I(ftell(events),0);
        }
    }
    if (output) fclose(output);
    if (events) fclose(events);
    arena_free(a);
}
static void run_case(const char *name,const char *source,RefOpts opts,RefStatus expected,
                     uint64_t assertions,const char *diagnostic) {
    run_case_impl(true,name,source,opts,expected,assertions,diagnostic);
}
void run_reference_tests(void) {
    run_case_impl(false,"reference API without ownership: rejects captured child across parent replacement",
        "module t\nstruct R { x: i32 }\nstruct P { child: R }\n"
        "fn replace(inout p: P) -> i32 { p = P{child: R{x: 9}}\nreturn 0 }\n"
        "fn observe(let r: R, n: i32) -> i32 { return r.x }\n"
        "test \"capture\" { var p = P{child: R{x: 1}}\nassert(observe(p.child, replace(inout p)) == 1) }\n",
        (RefOpts){0},REF_UNAVAILABLE,0,"captured call argument");
    run_case_impl(false,"reference API without ownership: rejects captured inout across parent replacement",
        "module t\nstruct R { x: i32 }\n"
        "fn replace(inout r: R) -> i32 { r = R{x: 9}\nreturn 0 }\n"
        "fn change(inout n: i32, tag: i32) { n += 1 }\n"
        "test \"capture\" { var r = R{x: 1}\nchange(inout r.x, replace(inout r)) }\n",
        (RefOpts){0},REF_UNAVAILABLE,0,"captured call argument");
    run_case("reference: range bounds capture in source order and once",
        "module t\nfn upper(inout start:i32)->i32{start=100\nreturn 3}\n"
        "test \"bounds\"{var start=0\nvar count=0\nfor i in start..upper(inout start){count+=1}\n"
        "assert(count==3)\nassert(start==100)\nvar stop=3\ncount=0\n"
        "for i in 0..stop{count+=1\nstop=0}\nassert(count==3)}\n",
        (RefOpts){0},REF_SUCCESS,3,NULL);
    run_case_impl(false,"reference API without ownership: projected destination rejects RHS ancestor replacement",
        "module t\nstruct R { x: i32 }\n"
        "fn replace(inout r: R) -> i32 { r = R{x: 10}\nreturn 7 }\n"
        "test \"replacement\" { var r = R{x: 1}\nr.x = replace(inout r)\nprintln(r.x) }\n",
        (RefOpts){0},REF_UNAVAILABLE,0,"projected assignment");
    run_case_impl(false,"reference API without ownership: projected compound destination rejects overlapping inout",
        "module t\nstruct R { x: i32 }\n"
        "fn bump(inout x: i32) -> i32 { x += 1\nreturn x }\n"
        "test \"compound\" { var r = R{x: 1}\nr.x += bump(inout r.x) }\n",
        (RefOpts){0},REF_UNAVAILABLE,0,"projected assignment");
    run_case_impl(false,"reference API without ownership: destination index evaluation rejects ancestor replacement",
        "module t\nstruct R { xs: [i32; 2] }\n"
        "fn replace(inout r: R) -> i32 { r = R{xs: [10, 20]}\nreturn 0 }\n"
        "test \"index\" { var r = R{xs: [1, 2]}\nr.xs[replace(inout r)] = 7 }\n",
        (RefOpts){0},REF_UNAVAILABLE,0,"destination evaluation or RHS");
    run_case("reference: disjoint fields, indices and unrelated index effects stay admitted",
        "module t\nstruct R { x: i32, y: i32 }\n"
        "fn bump(inout x: i32) -> i32 { x += 1\nreturn x }\n"
        "test \"disjoint\" { var r = R{x: 1, y: 2}\nr.x = bump(inout r.y)\n"
        "assert(r.x == 3)\nassert(r.y == 3)\nvar xs = [1, 2]\n"
        "xs[0] = bump(inout xs[1])\nassert(xs[0] == 3)\n"
        "var i = -1\nxs[bump(inout i)] += 4\nassert(i == 0)\nassert(xs[0] == 7) }\n",
        (RefOpts){0},REF_SUCCESS,5,NULL);
    run_case("reference: direct-width literal parsing avoids double rounding",
        "module t\nconst FOLDED: f32 = 9223373686122217471\n"
        "test \"rounding\" { let expected: f32 = 9223373136366403584\n"
        "let explicit = 9223373686122217471f32\nassert(explicit == expected)\nassert(FOLDED == expected)\n"
        "let decimal: f32 = 1.0000000596046447753906250000000001\n"
        "let next: f32 = 1.00000011920928955078125\nassert(decimal == next) }\n",
        (RefOpts){0},REF_SUCCESS,3,NULL);
    run_case("reference: independent numeric fixtures and f32 grouping",
        "module t\ntest \"numeric\" {\n"
        "let x: f32 = 16777216\nlet one: f32 = 1\nassert((x + one) - x == 0)\n"
        "assert(x + (one - x) == 1)\nassert(clamp(9, -2, 3) == 3)\n"
        "assert(wrapping_add(2147483647, 1) == -2147483648)\n"
        "assert(wrapping_mul(2147483647, 2) == -2)\n"
        "assert(saturating_sub(-2147483648, 1) == -2147483648)\n"
        "assert((-4 >> 1) == -2)\nassert((-7 / 2) == -3)\n"
        "let a: f32 = 2.25\nassert(sqrt(a) == 1.5)\n}\n",
        (RefOpts){0},REF_SUCCESS,9,NULL);
    run_case("reference: records, nested arrays, methods and independent copies",
        "module t\nstruct P { values: [i32; 2] }\nstruct Q { p: P }\n"
        "fn P.add(inout self, let x: i32) { self.values[0] += x }\n"
        "test \"copy\" { var a = Q{p: P{values: [1, 2]}}\nvar b = a\n"
        "b.p.add(8)\nassert(a.p.values[0] == 1)\nassert(b.p.values[0] == 9)\n"
        "b = b\nassert(b.p.values[1] == 2) }\n",
        (RefOpts){0},REF_SUCCESS,3,NULL);
    run_case("reference: arguments, compound assignment and short circuit ordering",
        "module t\nfn next(inout n: i32) -> i32 { n += 1\nreturn n }\n"
        "fn pack(let a: i32, let b: i32) -> i32 { return a * 10 + b }\n"
        "fn yes(inout n: i32) -> bool { n += 1\nreturn true }\n"
        "test \"order\" { var n = 0\nassert(pack(next(inout n), next(inout n)) == 12)\n"
        "var x = 4\nx += next(inout x)\nassert(x == 9)\n"
        "let a = false && yes(inout n)\nlet b = true || yes(inout n)\nassert(n == 2) }\n",
        (RefOpts){0},REF_SUCCESS,3,NULL);
    run_case("reference: set, sink, immediate defer, loops and early returns",
        "module t\nfn fill(set n: i32) { n = 7 }\n"
        "fn take(sink n: i32) -> i32 { return n + 1 }\n"
        "fn bump(inout n: i32) { n += 1 }\n"
        "fn early(let n: i32) -> i32 { if n > 0 { return 3 }\nreturn 4 }\n"
        "test \"control\" { var n: i32\nfill(set n)\nassert(n == 7)\n"
        "let moved = take(sink n)\nassert(moved == 8)\nvar x = 0\ndefer bump(inout x)\nassert(x == 1)\n"
        "for i in 0..10 { if i == 2 { continue }\nif i == 5 { break }\nx += i }\n"
        "assert(x == 9)\nwhile x < 12 { x += 1 }\nassert(x == 12)\nassert(early(1) == 3) }\n",
        (RefOpts){0},REF_SUCCESS,6,NULL);
    run_case("reference: failed assertions never become successful tests",
        "module t\ntest \"bad\" { assert(1 == 2) }\n",(RefOpts){0},REF_FAILED,0,"reference assertion failed");
    run_case("reference: unsupported containers rejected before execution",
        "module t\ntest \"list\" { var xs: List<i32>\nxs.push(1) }\n",
        (RefOpts){0},REF_UNAVAILABLE,0,"BE1001");
    run_case("reference: overflow trap", "module t\ntest \"overflow\" { var x = 2147483647\nx += 1 }\n",
        (RefOpts){0},REF_TRAP,0,"i32 arithmetic overflow");
    run_case("reference: fixed-array bounds trap", "module t\ntest \"bounds\" { let xs = [1, 2]\nlet n = 2\nprintln(xs[n]) }\n",
        (RefOpts){0},REF_TRAP,0,"fixed bounds");
    run_case("reference: step budget", "module t\ntest \"loop\" { while true {} }\n",
        (RefOpts){.max_steps=50},REF_BUDGET,0,"step budget");
    run_case("reference: call depth budget", "module t\nfn recurse() { recurse() }\ntest \"recurse\" { recurse() }\n",
        (RefOpts){.max_call_depth=4},REF_BUDGET,0,"call-depth budget");
    run_case("reference: allocation budget", "module t\ntest \"allocation\" { let xs = [1, 2, 3, 4]\nassert(xs[0] == 1) }\n",
        (RefOpts){.max_bytes=128},REF_BUDGET,0,"allocation budget");
    run_case("reference: empty selection rejected", "module t\nfn nothing() {}\n",
        (RefOpts){0},REF_UNAVAILABLE,0,"no test blocks");
}
