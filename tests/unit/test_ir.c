#include "test.h"
#include "../../src/parse/parser.h"
#include "../../src/sema/check.h"
#include "../../src/sema/ownership.h"
#include "../../src/reference/reference.h"
#include "../../src/ir/ir.h"
#include <string.h>

typedef struct { Arena *a; DiagBag *d; SourceMap *sm; Program *p; } Parsed;
static Parsed parse_frontend(const char *text, bool check_access) {
    Parsed s={.a=arena_new(0)}; SourceMap *sm=srcmap_new(s.a); s.sm=sm; s.d=diag_new(s.a,sm); s.p=prog_new(s.a);
    Interner *in=intern_new(s.a); uint32_t id=srcmap_add(sm,str_from("ir.be"),str_from(text));
    TokenVec tokens=lex_file(s.a,sm,s.d,in,id); prog_add_module(s.p,parse_file(s.a,s.d,in,tokens,id));
    bool ok=!diag_errors(s.d) && resolve_program(s.d,s.p) && check_program(s.d,s.p) && (!check_access || ownership_check(s.d,s.p));
    CHECK(ok);
    if (!ok) { Str why=diag_render_str(s.a,s.d); printf("%.*s\n",(int)why.len,why.ptr); }
    return s;
}
static Parsed parse(const char *text) { return parse_frontend(text,true); }
static void rejected_before_ir(const char *name,const char *text) {
    CASE(name);Parsed s=parse_frontend(text,false);
    CHECK(!ownership_check(s.d,s.p));
    CHECK_CONTAINS(diag_render_str(s.a,s.d),"BE0401");
    arena_free(s.a);
}
static Parsed parse_pid(void) {
    Parsed s={.a=arena_new(0)}; s.sm=srcmap_new(s.a); s.d=diag_new(s.a,s.sm); s.p=prog_new(s.a); Interner *in=intern_new(s.a);
    const char *paths[]={"packages/sparkos/pid/pid.be","packages/sparkos/pid/pid_test.be"};
    for (uint32_t n=0;n<2;n++) {
        FILE *file=fopen(paths[n],"rb"); CHECK(file!=NULL); if (!file) continue;
        CHECK(fseek(file,0,SEEK_END)==0); long size=ftell(file); CHECK(size>=0 && size<1048576);
        if (size<0 || size>=1048576) { fclose(file); continue; }
        CHECK(fseek(file,0,SEEK_SET)==0); char *text=ARENA_ARRAY(s.a,char,(size_t)size+1);
        CHECK(fread(text,1,(size_t)size,file)==(size_t)size); fclose(file);
        uint32_t id=srcmap_add(s.sm,str_from(paths[n]),str_new(text,(uint32_t)size));
        TokenVec tokens=lex_file(s.a,s.sm,s.d,in,id); prog_add_module(s.p,parse_file(s.a,s.d,in,tokens,id));
    }
    bool ok=s.p->modules.len==2 && !diag_errors(s.d) && resolve_program(s.d,s.p) && check_program(s.d,s.p) && ownership_check(s.d,s.p);
    CHECK(ok); if (!ok) { Str why=diag_render_str(s.a,s.d); printf("%.*s\n",(int)why.len,why.ptr); }
    return s;
}
static Str captured(Arena *a,FILE *file) {
    CHECK(fflush(file)==0); CHECK(fseek(file,0,SEEK_END)==0); long n=ftell(file); CHECK(n>=0);
    if (n<0) return STR_EMPTY;
    CHECK(fseek(file,0,SEEK_SET)==0); char *data=ARENA_ARRAY(a,char,(size_t)n+1);
    CHECK(fread(data,1,(size_t)n,file)==(size_t)n); return str_new(data,(uint32_t)n);
}
static void parity(const char *name,const char *source,IrRunStatus status,uint64_t assertions,const char *output) {
    CASE(name); Parsed s=parse(source); Arena *a=arena_new(0);
    IrProgram *ir=ir_lower(a,s.d,s.sm,s.p); CHECK(ir!=NULL);
    if (!ir) { Str why=diag_render_str(s.a,s.d); printf("%.*s\n",(int)why.len,why.ptr); arena_free(a); arena_free(s.a); return; }
    FILE *refout=tmpfile(), *refevents=tmpfile(), *irout=tmpfile(), *irevents=tmpfile();
    CHECK(refout && refevents && irout && irevents);
    if (refout && refevents && irout && irevents) {
        RefResult ref=reference_test(s.d,s.p,(RefOpts){.output=refout,.events=refevents});
        Str expected_out=captured(a,refout), expected_events=captured(a,refevents);
        arena_free(s.a); s.a=NULL; /* IR must not depend on retained AST nodes, types or strings. */
        IrRunResult result=ir_test(ir,(IrRunOpts){.output=irout,.events=irevents});
        CHECK_EQ_I(result.status,status); CHECK_EQ_I(result.assertions,assertions);
        CHECK_EQ_I(result.tests,ref.tests); CHECK_EQ_I(result.failed_tests,ref.failed_tests);
        CHECK(str_eq(captured(a,irout),expected_out)); CHECK(str_eq(captured(a,irevents),expected_events));
        if (output) CHECK(str_eq_c(expected_out,output));
        if (status==IR_RUN_TRAP) {
            CHECK_EQ_I(ref.status,REF_TRAP);
            if (ref.trap_kind==REF_SOURCE_TRAP_NONE) { CHECK_EQ_I(result.trap,IR_TRAP_NONE); CHECK(!result.trace_complete); }
            else {
                CHECK_EQ_I(result.source.file,ref.trap_span.file); CHECK_EQ_I(result.source.offset,ref.trap_span.offset);
                CHECK_EQ_I(result.trap==IR_TRAP_OVERFLOW,ref.trap_kind==REF_SOURCE_TRAP_OVERFLOW);
                CHECK_EQ_I(result.trap==IR_TRAP_BOUNDS,ref.trap_kind==REF_SOURCE_TRAP_BOUNDS); CHECK(result.trace_complete);
            }
        } else CHECK_EQ_I(ref.status,status==IR_RUN_SUCCESS?REF_SUCCESS:REF_FAILED);
    }
    if (refout) fclose(refout); if (refevents) fclose(refevents); if (irout) fclose(irout); if (irevents) fclose(irevents);
    if (s.a) arena_free(s.a); arena_free(a);
}
static void unsupported(const char *name,const char *source) {
    CASE(name); Parsed s=parse(source); Arena *a=arena_new(0);
    CHECK(ir_lower(a,s.d,s.sm,s.p)==NULL); CHECK_CONTAINS(diag_render_str(s.a,s.d),"BE1101");
    arena_free(a); arena_free(s.a);
}
static uint32_t find_op(IrProgram *p,IrOp op) {
    for (uint32_t i=0;i<p->instructions.len;i++) if (p->instructions.data[i].op==op) return i;
    return IR_NONE;
}
static bool cancelled(void) { return true; }
static uint64_t fake_clock_value;
static uint64_t fake_clock(void) { return fake_clock_value++; }

static void access_modes(void) {
    FILE *file=fopen("tests/reference/access-modes/plain.be","rb"); CHECK(file!=NULL);
    if (file) {
        CHECK(fseek(file,0,SEEK_END)==0); long n=ftell(file); CHECK(n>0 && n<65536);
        if (n>0 && n<65536) {
            Arena *a=arena_new(0); char *text=ARENA_ARRAY(a,char,(size_t)n+1);
            CHECK(fseek(file,0,SEEK_SET)==0); CHECK(fread(text,1,(size_t)n,file)==(size_t)n);
            text[n]=0;
            parity("IR: analytical plain SET/SINK records arrays receivers defaults and control",text,
                IR_RUN_SUCCESS,26,"7\n5\n90\nok  6 tests, 26 assertions\n");
            arena_free(a);
        }
        fclose(file);
    }
    parity("IR: SET first RHS failure preserves the successful event prefix",
        "module t\nfn fail(set n: i32) { println(10)\nlet z = 0\nn = 1 / z }\n"
        "test \"set trap\" { var n = 7\nfail(set n)\nprintln(99) }\n",IR_RUN_TRAP,0,"10\n");
    parity("IR: SET completed write survives until a subsequent source trap",
        "module t\nfn fail(set n: i32) { n = 8\nprintln(n)\nlet z = 0\nn = 1 / z }\n"
        "test \"set trap\" { var n = 7\nfail(set n)\nprintln(99) }\n",IR_RUN_TRAP,0,"8\n");
    unsupported("IR: outer initialization-changing loop requires a later admission rule",
        "module t\nfn condition(set n: i32) -> bool { n = 1\nreturn false }\n"
        "test \"loop\" { var n: i32\nwhile condition(set n) { }\nassert(n == 1) }\n");
    struct { const char *name, *text, *code; } failures[]={
        {"IR modes: moved whole root cannot be read",
         "module t\nfn get(sink n: i32) -> i32 { return n }\ntest \"bad\" { let x=1\nget(sink x)\nprintln(x) }\n","BE0403"},
        {"IR modes: later argument cannot read a moved earlier argument",
         "module t\nfn get(sink n: i32, m: i32) {}\ntest \"bad\" { var x=1\nget(sink x,x) }\n","BE0403"},
        {"IR modes: SET does not initialize before later argument evaluation",
         "module t\nfn put(set n: i32,m: i32) { n=m }\ntest \"bad\" { var x:i32\nput(set x,x) }\n","BE0405"},
        {"IR modes: SET must initialize every normal return",
         "module t\nfn put(set n: i32,b: bool) { if b { n=1 } }\ntest \"bad\" {}\n","BE0404"},
        {"IR modes: SET read before its first assignment",
         "module t\nfn put(set n: i32) { println(n)\nn=1 }\ntest \"bad\" {}\n","BE0405"},
        {"IR modes: borrowed root cannot be moved",
         "module t\nfn get(sink n:i32) {}\nfn f(let n:i32) { get(sink n) }\ntest \"bad\" {}\n","BE0406"},
        {"IR modes: partial moves remain rejected",
         "module t\nstruct R {x:i32}\nfn get(sink n:i32) {}\ntest \"bad\" { var r=R{x:1}\nget(sink r.x) }\n","BE0406"},
        {"IR modes: initialized immutable SET remains rejected",
         "module t\nfn put(set n:i32) {n=1}\ntest \"bad\" {let n=0\nput(set n)}\n","BE0407"},
    };
    for (uint32_t n=0;n<sizeof failures/sizeof failures[0];n++) {
        CASE(failures[n].name); Parsed s=parse_frontend(failures[n].text,false);
        CHECK(!ownership_check(s.d,s.p)); CHECK_CONTAINS(diag_render_str(s.a,s.d),failures[n].code);
        arena_free(s.a);
    }

    parity("IR: a returning moved branch does not poison the surviving branch",
        "module t\nfn take(sink n:i32)->i32 {return n}\n"
        "fn select(sink n:i32,on:bool)->i32 {if on {return take(sink n)}\nreturn n}\n"
        "test \"branches\" {assert(select(sink 4,true)==4)\nassert(select(sink 7,false)==7)}\n",
        IR_RUN_SUCCESS,2,"ok  1 test, 2 assertions\n");
    parity("IR: initialized SET destination remains readable during later scalar capture",
        "module t\nfn replace(set n:i32,old:i32) {n=old+1}\n"
        "test \"capture\" {var n=4\nreplace(set n,n)\nassert(n==5)}\n",
        IR_RUN_SUCCESS,1,"ok  1 test, 1 assertion\n");
    {
        CASE("IR modes: back-edge mutant cannot hide a moved outer root");
        Parsed source=parse("module t\nfn take(sink n:i32)->i32 {return n}\n"
            "test \"loop\" {var n=0\nvar spare=0\nwhile n<3 {let old=take(sink n)\nn=old+1}\nassert(n==3)}\n");
        Arena *memory=arena_new(0); IrProgram *ir=ir_lower(memory,source.d,source.sm,source.p); CHECK(ir!=NULL);
        if (ir) {
            uint32_t move=find_op(ir,IR_MOVE),write=IR_NONE,spare=IR_NONE;
            CHECK(move!=IR_NONE);
            if (move!=IR_NONE) {
                uint32_t root=ir->instructions.data[move].place;
                for (uint32_t n=0;n<ir->places.len;n++) if (n!=root && ir->places.data[n].function==ir->places.data[root].function &&
                    ir->places.data[n].parent==IR_NONE && ir->places.data[n].mutable && !ir->places.data[n].synthetic) {spare=n;break;}
                for (uint32_t n=move+1;n<ir->instructions.len;n++) if (ir->instructions.data[n].op==IR_STORE && ir->instructions.data[n].place==root) {write=n;break;}
                CHECK(spare!=IR_NONE && write!=IR_NONE);
                if (spare!=IR_NONE && write!=IR_NONE) {
                    ir->instructions.data[write].place=spare;
                    IrVerification result=ir_verify(ir); CHECK(!result.ok);
                    CHECK(strcmp(result.reason,"loop back edge changes an outer logical state")==0);
                    ir->instructions.data[write].place=root; CHECK(ir_verify(ir).ok);
                }
            }
        }
        arena_free(memory); arena_free(source.a);
    }

    CASE("IR modes: malformed declaration move capture and SET return states reject");
    Parsed s=parse("module t\nfn put(set n:i32) {n=8}\nfn get(sink n:i32)->i32 {return n}\n"
        "test \"a\" {var x:i32\nput(set x)\nlet y=get(sink x)\nput(set x)\nassert(x==8)\nassert(y==8)}\n");
    Arena *a=arena_new(0); IrProgram *p=ir_lower(a,s.d,s.sm,s.p); CHECK(p!=NULL);
    if (p) {
        CHECK_EQ_I(p->schema_version,IR_SCHEMA_VERSION); CHECK(ir_verify(p).ok);
        uint32_t decl=find_op(p,IR_DECLARE),move=find_op(p,IR_MOVE),store=find_op(p,IR_STORE);
        CHECK(decl!=IR_NONE && move!=IR_NONE && store!=IR_NONE);
        if (decl!=IR_NONE && move!=IR_NONE && store!=IR_NONE) {
            IrInstruction old=p->instructions.data[decl];
            p->instructions.data[decl].op=IR_CAPTURE; p->instructions.data[decl].immediate=IR_SET; p->instructions.data[decl].flag=true;
            CHECK(!ir_verify(p).ok); p->instructions.data[decl]=old;
            uint32_t second=IR_NONE; for (uint32_t n=decl+1;n<p->instructions.len;n++) if (p->instructions.data[n].op==IR_DECLARE) {second=n;break;}
            CHECK(second!=IR_NONE);
            if (second!=IR_NONE) { IrInstruction saved=p->instructions.data[second]; p->instructions.data[second].place=old.place; CHECK(!ir_verify(p).ok); p->instructions.data[second]=saved; }
            old=p->instructions.data[move]; p->instructions.data[move].op=IR_LOAD;
            CHECK(!ir_verify(p).ok); p->instructions.data[move]=old;
            old=p->instructions.data[store]; p->instructions.data[store].op=IR_CAPTURE;
            p->instructions.data[store].immediate=IR_SET; p->instructions.data[store].flag=true;
            CHECK(!ir_verify(p).ok); p->instructions.data[store]=old;
            old=p->instructions.data[store]; p->instructions.data[store].op=IR_DECLARE;
            CHECK(!ir_verify(p).ok); p->instructions.data[store]=old;
            uint32_t mode_root=p->functions.data[1].places_start; IrMode mode=p->places.data[mode_root].mode;
            p->places.data[mode_root].mode=IR_LET; CHECK(!ir_verify(p).ok); p->places.data[mode_root].mode=mode;
            CHECK(ir_verify(p).ok);
        }
    }
    arena_free(a); arena_free(s.a);
}

void run_ir_tests(void) {
    access_modes();
    parity("IR: structured control, range continue, short circuit, call order and immediate defer",
        "module t\nfn mark(let n: i32) -> i32 { println(n)\nreturn n }\n"
        "fn flag() -> bool { println(999)\nreturn true }\n"
        "fn choose(let on: bool) -> i32 { if on { return 3 }\nreturn 4 }\n"
        "fn pack(let x: i32, let y: i32) -> i32 { return x * 10 + y }\n"
        "test \"control\" { var n = 0\nfor i in mark(0)..mark(6) { if i == 2 { continue }\nif i == 5 { break }\nn += i }\n"
        "assert(n == 8)\nwhile n < 11 { n += 1\nif n == 10 { continue }\nprintln(n) }\nassert(n == 11)\n"
        "let a = false && flag()\nlet b = true || flag()\nassert(!a && b)\nassert(pack(mark(1), mark(2)) == 12)\n"
        "defer println(77)\nassert(choose(true) == 3) }\n",IR_RUN_SUCCESS,5,
        "0\n6\n9\n11\n1\n2\n77\nok  1 test, 5 assertions\n");
    parity("IR: independent i32 boundary values, bitwise and comparisons",
        "module t\nfn input(let n: i32) -> i32 { return n }\n"
        "test \"numbers\" { let low = input(-2147483648)\nlet high = input(2147483647)\n"
        "assert(low % -1 == 0)\nassert(-7 / 2 == -3)\nassert((high & -1) == high)\n"
        "assert((low | 1) == -2147483647)\nassert((high ^ -1) == low)\nassert(~0 == -1)\n"
        "assert((true == false) == false)\nassert(low < high)\nassert(low <= low)\nassert(high >= high) }\n",IR_RUN_SUCCESS,10,
        "ok  1 test, 10 assertions\n");
    parity("IR: recursive function and constant declaration identity",
        "module t\nconst N: i32 = 4\nfn factorial(let n: i32) -> i32 { if n <= 1 { return 1 }\nreturn n * factorial(n - 1) }\n"
        "test \"recursive\" { assert(factorial(N) == 24) }\n",IR_RUN_SUCCESS,1,"ok  1 test, 1 assertion\n");
    parity("IR: compound checked failure retains first source site and prefix",
        "module t\ntest \"overflow\" { println(1)\nvar x = 2147483647\nx += 1\nprintln(2) }\n",IR_RUN_TRAP,0,"1\n");
    parity("IR: first failing call argument stops later argument evaluation",
        "module t\nfn first() -> i32 { println(1)\nlet zero = 0\nreturn 1 / zero }\n"
        "fn second() -> i32 { println(2)\nreturn 3 }\nfn combine(let a: i32, let b: i32) -> i32 { return a + b }\n"
        "test \"first\" { println(combine(first(), second())) }\n",IR_RUN_TRAP,0,"1\n");
    parity("IR: failed assertion continues observation stream but fails verification",
        "module t\ntest \"assert\" { assert(false)\nprintln(7) }\n",IR_RUN_FAILED,1,"7\nFAILED  1 of 1 test\n");
    parity("IR: nested loops consume only their own break and continue",
        "module t\ntest \"nested\" { var sum = 0\nfor i in 0..3 { for j in 0..4 { if j == 1 { continue }\nif j == 3 { break }\nsum += i + j } }\n"
        "assert(sum == 12)\nfor k in 2147483646..2147483647 { assert(k == 2147483646) } }\n",IR_RUN_SUCCESS,2,"ok  1 test, 2 assertions\n");
    parity("IR: immutable locals and short-circuit temporaries reinitialize only at their loop lifetime",
        "module t\ntest \"loop locals\" { var sum = 0\nfor i in 0..4 { let n = i + 1\nlet on = (i < 2) || (i == 3)\n"
        "if on { sum += n } }\nassert(sum == 7) }\n",IR_RUN_SUCCESS,1,"ok  1 test, 1 assertion\n");
    parity("IR: finite binary32 grouping, signed zeros and exact printed bits",
        "module t\ntest \"f\" { let big: f32 = 16777216\nlet one: f32 = 1\n"
        "let left = (big + one) - big\nlet right = big + (one - big)\nassert(left == 0)\nassert(right == 1)\n"
        "println(left)\nprintln(right)\nprintln(-0f32)\nprintln(0.1f32) }\n",IR_RUN_SUCCESS,2,"0\n1\n-0\n0.1\nok  1 test, 2 assertions\n");
    parity("IR: numeric casts, finite min/max/clamp and configured reversed bounds",
        "module t\ntest \"f\" { let n = 16777217\nassert(n as f32 == 16777216f32)\n"
        "let fraction: f32 = -3.75\nassert(fraction as i32 == -3)\nassert((true as f32) == 1)\n"
        "assert(clamp(0f32, 1f32, -1f32) == 1)\nassert(abs(-2.5f32) == 2.5)\n"
        "println(min(-0f32, 0f32))\nprintln(max(0f32, -0f32)) }\n",IR_RUN_SUCCESS,5,"0\n-0\nok  1 test, 5 assertions\n");
    parity("IR: widened literal parsing retains admitted binary32 value",
        "module t\ntest \"rounding\" { let n: f32 = 9223373686122217471\nassert(n == 9223373136366403584f32)\n"
        "let halfway: f32 = 1.0000000596046447753906250000000001\nassert(halfway == 1.00000011920928955078125) }\n",
        IR_RUN_SUCCESS,2,"ok  1 test, 2 assertions\n");
    parity("IR: nonfinite result stays outside the admitted domain without a fabricated integer trap",
        "module t\nfn input(let n: f32) -> f32 { return n }\ntest \"finite\" { println(7)\nlet zero = input(0)\nprintln(input(1) / zero) }\n",
        IR_RUN_TRAP,0,"7\n");
    parity("IR: invalid float-to-integer cast has no fabricated overflow category",
        "module t\nfn input(let n: f32) -> f32 { return n }\ntest \"cast\" { println(input(2147483648f32) as i32) }\n",IR_RUN_TRAP,0,"");
    parity("IR: fixed-width wrapping, saturation and arithmetic right shift",
        "module t\ntest \"bits\" { assert(wrapping_add(2147483647, 1) == -2147483648)\n"
        "assert(wrapping_mul(2147483647, 2) == -2)\nassert(wrapping_sub(-2147483648, 1) == 2147483647)\n"
        "assert(saturating_add(2147483647, 1) == 2147483647)\nassert(saturating_sub(-2147483648, 1) == -2147483648)\n"
        "assert((-4 >> 1) == -2)\nassert((1 << 31) == -2147483648) }\n",IR_RUN_SUCCESS,7,"ok  1 test, 7 assertions\n");
    unsupported("IR: f64 remains unavailable", "module t\ntest \"f\" { let x: f64 = 1\nprintln(x) }\n");
    parity("IR: arrays copy nested values and preserve literal and index evaluation order",
        "module t\nstruct R { xs: [i32; 2] }\nfn mark(let n: i32) -> i32 { println(n)\nreturn n }\n"
        "test \"arrays\" { var a = [R { xs: [mark(1), mark(2)] }, R { xs: [3, 4] }]\nvar b = a\n"
        "b[0].xs[1] = 9\nassert(a[0].xs[1] == 2)\nassert(b[0].xs[1] == 9)\n"
        "assert(a[mark(1)].xs[mark(0)] == 3) }\n",IR_RUN_SUCCESS,3,"1\n2\n1\n0\nok  1 test, 3 assertions\n");
    parity("IR: array return, default let borrow and inout element copy semantics",
        "module t\nfn make() -> [i32; 2] { return [4, 5] }\n"
        "fn sum(let xs: [i32; 2], let n: i32 = 1) -> i32 { return xs[0] + xs[1] + n }\n"
        "fn change(inout n: i32) { n += 3 }\nfn replace(inout xs: [i32; 2]) { xs = [7, 8] }\n"
        "test \"calls\" { var xs = make()\nassert(sum(xs) == 10)\nassert(make()[1] == 5)\n"
        "change(inout xs[0])\nassert(xs[0] == 7)\nreplace(inout xs)\nassert(xs[1] == 8) }\n",
        IR_RUN_SUCCESS,4,"ok  1 test, 4 assertions\n");
    parity("IR: dynamic compound destination and old value captured once before RHS",
        "module t\nfn next(inout n: i32) -> i32 { let old = n\nn += 1\nprintln(old)\nreturn old }\n"
        "fn rhs() -> i32 { println(9)\nreturn 5 }\n"
        "test \"compound\" { var xs = [2, 3]\nvar n = 0\nxs[next(inout n)] += rhs()\n"
        "assert(n == 1)\nassert(xs[0] == 7)\nassert(xs[1] == 3) }\n",IR_RUN_SUCCESS,3,"0\n9\nok  1 test, 3 assertions\n");
    parity("IR: fixed-array foreach uses an independent snapshot with structured exits",
        "module t\ntest \"snapshot\" { var xs = [1, 2, 3, 4]\nvar sum = 0\n"
        "for x in xs { xs[0] = 99\nif x == 2 { continue }\nif x == 4 { break }\nsum += x }\n"
        "assert(sum == 4)\nassert(xs[0] == 99) }\n",IR_RUN_SUCCESS,2,"ok  1 test, 2 assertions\n");
    parity("IR: logical empty arrays copy and iterate without observing padding",
        "module t\nfn count(let xs: [i32; 0]) -> i32 { var n = 0\nfor x in xs { n += x }\nreturn n }\n"
        "test \"empty\" { let xs: [i32; 0] = []\nlet copy = xs\nassert(count(copy) == 0) }\n",
        IR_RUN_SUCCESS,1,"ok  1 test, 1 assertion\n");
    parity("IR: zero-array index zero traps before accessing physical padding",
        "module t\ntest \"empty bounds\" { let xs: [i32; 0] = []\nprintln(7)\nprintln(xs[0]) }\n",IR_RUN_TRAP,0,"7\n");
    parity("IR: nested empty arrays preserve outer length and inner zero bounds",
        "module t\ntest \"nested empty\" { let xs: [[i32; 0]; 2] = [[], []]\nvar n = 0\n"
        "for inner in xs { n += 1\nfor element in inner { n += element } }\nassert(n == 2)\nprintln(n)\nprintln(xs[1][0]) }\n",
        IR_RUN_TRAP,1,"2\n");
    parity("IR: bounds failure precedes destination RHS and later observations",
        "module t\nfn rhs() -> i32 { println(9)\nreturn 2 }\ntest \"bounds\" { var xs = [1, 2]\nprintln(7)\nxs[2] = rhs()\nprintln(8) }\n",
        IR_RUN_TRAP,0,"7\n");
    parity("IR: negative index has exact first source failure and observation prefix",
        "module t\ntest \"negative\" { let xs = [1, 2]\nprintln(6)\nlet index = -1\nprintln(xs[index]) }\n",IR_RUN_TRAP,0,"6\n");
    parity("IR: index arithmetic fails before the bounds operation",
        "module t\ntest \"order\" { let xs = [1, 2]\nlet high = 2147483647\nprintln(6)\nprintln(xs[high + 1]) }\n",IR_RUN_TRAP,0,"6\n");
    parity("IR: value index captures the array before evaluating its index",
        "module t\nfn make() -> [f32; 2] { println(1)\nreturn [0.1f32, 2.5f32] }\nfn index() -> i32 { println(2)\nreturn 1 }\n"
        "test \"value index\" { println(make()[index()]) }\n",IR_RUN_SUCCESS,0,"1\n2\n2.5\nok  1 test, 0 assertions\n");
    parity("IR: nested array subregions preserve disjoint captured access",
        "module t\nstruct Pair { a: [i32; 2], b: [i32; 2] }\n"
        "fn index(inout xs: [i32; 2]) -> i32 { xs = [0, 8]\nreturn 1 }\n"
        "fn inc(inout x: i32, let n: i32) { x += n }\n"
        "test \"disjoint\" { var p = Pair { a: [1, 2], b: [3, 4] }\n"
        "assert(p.a[index(inout p.b)] == 2)\ninc(inout p.a[0], 2)\ninc(inout p.b[0], 3)\n"
        "assert(p.a[0] == 3)\nassert(p.b[0] == 3) }\n",IR_RUN_SUCCESS,3,"ok  1 test, 3 assertions\n");
    unsupported("IR: index captures reject mutation of the selected array root",
        "module t\nfn replace(inout xs: [i32; 2]) -> i32 { xs = [7, 8]\nreturn 0 }\n"
        "test \"unstable\" { var xs = [1, 2]\nprintln(xs[replace(inout xs)]) }\n");
    rejected_before_ir("IR: common ownership rejects distinct literal mutable element arguments conservatively",
        "module t\nfn two(inout a: i32, inout b: i32) { a += 1\nb += 1 }\n"
        "test \"overlap\" { var xs = [1, 2]\ntwo(inout xs[0], inout xs[1]) }\n");
    unsupported("IR: oversized inline arrays are not silently admitted",
        "module t\nfn large(let xs: [i32; 257]) -> i32 { return xs[0] }\ntest \"unused\" { assert(true) }\n");
    parity("IR: set array output creates an independently readable value",
        "module t\nfn output(set xs: [i32; 2]) { xs = [1, 2] }\ntest \"array set\" { var xs: [i32;2]\noutput(set xs)\nassert(xs[0] == 1)\nassert(xs[1] == 2) }\n",
        IR_RUN_SUCCESS,2,"ok  1 test, 2 assertions\n");
    unsupported("IR: aggregate equality is an admission limitation, not malformed lowering",
        "module t\ntest \"equality\" { let a = [1, 2]\nlet b = [1, 2]\nassert(a == b) }\n");
    {
        CASE("IR: array metadata, checked projection, effect and initialization mutants reject");
        Parsed s=parse("module t\nfn touch(inout n: i32) { n += 1 }\nfn make() -> [i32; 2] { return [3, 4] }\n"
            "test \"array mutants\" { var xs = [1, 2]\nlet index = 0\nxs[index] += 2\ntouch(inout xs[1])\n"
            "assert(xs[index] == 3)\nassert(xs[1] == 3)\nassert(make()[index] == 3) }\n");
        Arena *a=arena_new(0),*b=arena_new(0); IrProgram *p=ir_lower(a,s.d,s.sm,s.p),*repeat=ir_lower(b,s.d,s.sm,s.p); CHECK(p && repeat);
        if (p && repeat) {
            CHECK_EQ_I(p->aggregates.len,repeat->aggregates.len); CHECK_EQ_I(p->places.len,repeat->places.len);
            CHECK_EQ_I(p->instructions.len,repeat->instructions.len); CHECK(str_eq(p->source_manifest_sha256,repeat->source_manifest_sha256));
            for (uint32_t n=0;n<p->instructions.len;n++) {
                const IrInstruction *x=&p->instructions.data[n],*y=&repeat->instructions.data[n];
                CHECK(x->op==y->op && x->a==y->a && x->b==y->b && x->place==y->place && x->result==y->result &&
                    x->region==y->region && x->next==y->next && x->args_start==y->args_start && x->args_count==y->args_count);
            }
            arena_free(s.a); s.a=NULL;
            uint32_t construct=find_op(p,IR_ARRAY), projection=find_op(p,IR_INDEX_PLACE), base=find_op(p,IR_INDEX_BASE), index_value=find_op(p,IR_INDEX_VALUE);
            CHECK(construct!=IR_NONE && projection!=IR_NONE && base!=IR_NONE && index_value!=IR_NONE);
            if (construct!=IR_NONE && projection!=IR_NONE && base!=IR_NONE && index_value!=IR_NONE) {
                uint32_t type=p->values.data[p->instructions.data[construct].result].type-IR_FIRST_AGGREGATE;
                IrAggregate array=p->aggregates.data[type];
                p->aggregates.data[type].kind=(IrAggregateKind)-1; CHECK(!ir_verify(p).ok); p->aggregates.data[type]=array;
                p->aggregates.data[type].length=UINT32_MAX; CHECK(!ir_verify(p).ok); p->aggregates.data[type]=array;
                p->aggregates.data[type].cells++; CHECK(!ir_verify(p).ok); p->aggregates.data[type]=array;
                p->aggregates.data[type].element=IR_VOID; CHECK(!ir_verify(p).ok); p->aggregates.data[type]=array;
                p->aggregates.data[type].element=type+IR_FIRST_AGGREGATE; CHECK(!ir_verify(p).ok); p->aggregates.data[type]=array;
                p->aggregates.data[type].declaration.offset=UINT32_MAX; CHECK(!ir_verify(p).ok); p->aggregates.data[type]=array;
                IrInstruction array_inst=p->instructions.data[construct];
                p->instructions.data[construct].op=IR_RECORD; CHECK(!ir_verify(p).ok); p->instructions.data[construct]=array_inst;
                p->instructions.data[construct].args_count--; CHECK(!ir_verify(p).ok); p->instructions.data[construct]=array_inst;
                IrArgument element=p->arguments.data[array_inst.args_start];
                p->arguments.data[array_inst.args_start].field=1; CHECK(!ir_verify(p).ok); p->arguments.data[array_inst.args_start]=element;
                p->arguments.data[array_inst.args_start].value=IR_NONE; CHECK(!ir_verify(p).ok); p->arguments.data[array_inst.args_start]=element;
                p->arguments.data[array_inst.args_start].mode=IR_INOUT; CHECK(!ir_verify(p).ok); p->arguments.data[array_inst.args_start]=element;
                IrInstruction projected=p->instructions.data[projection]; IrPlace place=p->places.data[projected.place];
                p->places.data[projected.place].definition=IR_NONE; CHECK(!ir_verify(p).ok); p->places.data[projected.place]=place;
                p->places.data[projected.place].parent=projected.place; CHECK(!ir_verify(p).ok); p->places.data[projected.place]=place;
                p->places.data[projected.place].field=0; CHECK(!ir_verify(p).ok); p->places.data[projected.place]=place;
                p->places.data[projected.place].type=IR_BOOL; CHECK(!ir_verify(p).ok); p->places.data[projected.place]=place;
                p->instructions.data[projection].b=IR_NONE; CHECK(!ir_verify(p).ok); p->instructions.data[projection]=projected;
                p->instructions.data[projection].b=projection; CHECK(!ir_verify(p).ok); p->instructions.data[projection]=projected;
                p->instructions.data[projection].a=IR_NONE; CHECK(!ir_verify(p).ok); p->instructions.data[projection]=projected;
                p->instructions.data[projection].effects=IR_READ; CHECK(!ir_verify(p).ok); p->instructions.data[projection]=projected;
                IrInstruction captured_base=p->instructions.data[base];
                p->instructions.data[base].place=projected.place; CHECK(!ir_verify(p).ok); p->instructions.data[base]=captured_base;
                p->instructions.data[base].effects=0; CHECK(!ir_verify(p).ok); p->instructions.data[base]=captured_base;
                IrInstruction indexed=p->instructions.data[index_value];
                p->instructions.data[index_value].effects=0; CHECK(!ir_verify(p).ok); p->instructions.data[index_value]=indexed;
                p->instructions.data[index_value].b=indexed.a; CHECK(!ir_verify(p).ok); p->instructions.data[index_value]=indexed;
                /* Moving the bounds instruction after its first dependent
                 * operation must reject even with a well-formed list. */
                uint32_t after=projected.next;
                if (after!=IR_NONE && p->instructions.data[after].next!=IR_NONE) {
                    uint32_t previous=IR_NONE;
                    for (uint32_t n=0;n<p->instructions.len;n++) if (p->instructions.data[n].next==projection) { previous=n; break; }
                    CHECK(previous!=IR_NONE);
                    if (previous!=IR_NONE) {
                        uint32_t next=p->instructions.data[after].next;
                        p->instructions.data[previous].next=after; p->instructions.data[after].next=projection; p->instructions.data[projection].next=next;
                        CHECK(!ir_verify(p).ok);
                        p->instructions.data[previous].next=projection; p->instructions.data[after].next=next; p->instructions.data[projection]=projected;
                    }
                }
                CHECK(ir_verify(p).ok);
                /* A type-correct arithmetic mutation is semantically wrong; the
                 * analytical assertion must detect it, beyond verification. */
                uint32_t arithmetic=find_op(p,IR_BINARY);
                CHECK(arithmetic!=IR_NONE);
                IrInstruction old=p->instructions.data[arithmetic]; p->instructions.data[arithmetic].numeric=IR_SUB; CHECK(ir_verify(p).ok);
                FILE *out=tmpfile(); CHECK(out!=NULL);
                if (out) { IrRunResult mutant=ir_test(p,(IrRunOpts){.output=out}); CHECK_EQ_I(mutant.status,IR_RUN_FAILED); fclose(out); }
                p->instructions.data[arithmetic]=old;
            }
        }
        if (s.a) arena_free(s.a); arena_free(a); arena_free(b);
    }
    parity("IR: scalar inout is captured and mutates the caller", "module t\nfn bump(inout n: i32) { n += 1 }\ntest \"a\" { var x = 0\nbump(inout x)\nassert(x == 1) }\n",IR_RUN_SUCCESS,1,"ok  1 test, 1 assertion\n");
    parity("IR: expanded default parameters preserve the call", "module t\nfn f(let n: i32 = 1) -> i32 { return n }\ntest \"a\" { assert(f() == 1) }\n",IR_RUN_SUCCESS,1,"ok  1 test, 1 assertion\n");
    parity("IR: shift failure has no fabricated overflow category", "module t\nfn n(let x: i32) -> i32 { return x }\ntest \"a\" { println(2 << n(32)) }\n",IR_RUN_TRAP,0,"");
    parity("IR: declared but unused uninitialized local", "module t\ntest \"a\" { var x: i32 }\n",IR_RUN_SUCCESS,0,"ok  1 test, 0 assertions\n");
    unsupported("IR: unreachable string expressions remain unavailable", "module t\nfn f() { return\nprintln(\"dead\") }\ntest \"a\" { f() }\n");
    unsupported("IR: unreachable unsupported intrinsic remains unavailable", "module t\nfn f() { return\nprintln(sqrt(4f32)) }\ntest \"a\" { f() }\n");
    parity("IR: nested record values, returns, inout methods and default fields remain independent",
        "module t\nstruct Pair { x: i32 = 1\ny: i32 = 2 }\nstruct Boxed { pair: Pair\nz: f32 = 0.5 }\n"
        "fn Pair.bump(inout self, amount: i32 = 3) { self.x += amount }\nfn Pair.read(let self) -> i32 { return self.x }\n"
        "fn Pair.make(x: i32 = 1) -> Pair { return Pair{x: x} }\nfn clone(let p: Boxed) -> Boxed { return p }\n"
        "fn disjoint(inout x: i32, inout y: i32) { x += 1\ny += 2 }\n"
        "test \"record\" { var a = Boxed{pair: Pair{}}\nlet old = a\na.pair.bump()\nassert(a.pair.read() == 4)\nassert(old.pair.x == 1)\n"
        "var b = clone(a)\nb.pair.x = 8\nassert(a.pair.x == 4)\nassert(b.pair.x == 8)\nb = b\nassert(b.pair.x == 8)\n"
        "disjoint(inout a.pair.x, inout a.pair.y)\nassert(a.pair.x == 5 && a.pair.y == 4)\nassert(Pair.make(9).x == 9)\nprintln(old.z) }\n",
        IR_RUN_SUCCESS,7,"0.5\nok  1 test, 7 assertions\n");
    parity("IR: record initializer order and scalar compound old-value precede mutating RHS",
        "module t\nstruct R { a: i32\nb: i32 }\nfn mark(x: i32) -> i32 { println(x)\nreturn x }\n"
        "fn replace(inout n: i32) -> i32 { n = 40\nreturn 2 }\n"
        "test \"order\" { var r = R{b: mark(2), a: mark(1)}\nvar n = r.a\nn += replace(inout n)\nassert(n == 3)\nassert(r.b == 2) }\n",
        IR_RUN_SUCCESS,2,"2\n1\nok  1 test, 2 assertions\n");
    rejected_before_ir("IR: shared semantics reject projected assignment before lowering",
        "module t\nstruct R { x: i32 }\nfn replace(inout r: R) -> i32 { r = R{x: 10}\nreturn 7 }\n"
        "test \"replace\" { var r = R{x: 1}\nr.x = replace(inout r)\nprintln(r.x) }\n");
    rejected_before_ir("IR: shared semantics reject projected compound assignment before lowering",
        "module t\nstruct R { x: i32 }\nfn replace(inout r: R) -> i32 { r.x = 10\nreturn 7 }\n"
        "test \"replace\" { var r = R{x: 1}\nr.x += replace(inout r)\nprintln(r.x) }\n");
    parity("IR: plain sink consumes a whole record", "module t\nstruct R { n: i32 }\nfn take(sink r: R) -> i32 { return r.n }\ntest \"sink\" { var r = R{n: 3}\nassert(take(sink r) == 3) }\n" ,IR_RUN_SUCCESS,1,"ok  1 test, 1 assertion\n");
    parity("IR: plain set initializes a whole scalar", "module t\nfn set_one(set x: i32) { x = 1 }\ntest \"set\" { var x: i32\nset_one(set x)\nassert(x == 1) }\n" ,IR_RUN_SUCCESS,1,"ok  1 test, 1 assertion\n");
    {
        CASE("IR: record layout, constructor, projection and mode mutants reject malformed storage");
        Parsed s=parse("module t\nstruct R { a: i32\nb: i32 }\nfn update(inout a: i32, inout b: i32) { a += 1\nb += 2 }\n"
            "test \"r\" { var r = R{a: 1, b: 2}\nr.a = r.a\nupdate(inout r.a, inout r.b)\nassert(r.a == 2 && r.b == 4) }\n");
        Arena *a=arena_new(0); IrProgram *p=ir_lower(a,s.d,s.sm,s.p); CHECK(p!=NULL);
        if (p) {
            arena_free(s.a); s.a=NULL; CHECK(ir_verify(p).ok);
            IrAggregate record=p->aggregates.data[0]; IrField field=p->fields.data[0];
            p->aggregates.data[0].cells++; CHECK(!ir_verify(p).ok); p->aggregates.data[0]=record;
            p->fields.data[0].offset=1; CHECK(!ir_verify(p).ok); p->fields.data[0]=field;
            p->fields.data[0].type=IR_FIRST_AGGREGATE; CHECK(!ir_verify(p).ok); p->fields.data[0]=field;
            p->fields.data[0].declaration.offset=UINT32_MAX; CHECK(!ir_verify(p).ok); p->fields.data[0]=field;
            uint32_t construct=find_op(p,IR_RECORD), capture=find_op(p,IR_CAPTURE), call_id=find_op(p,IR_CALL);
            CHECK(construct!=IR_NONE && capture!=IR_NONE && call_id!=IR_NONE);
            IrInstruction *call=&p->instructions.data[call_id]; uint32_t aa=call->args_start;
            IrArgument saved=p->arguments.data[aa];
            p->arguments.data[aa].mode=(IrMode)-1; CHECK(!ir_verify(p).ok); p->arguments.data[aa]=saved;
            p->arguments.data[aa].by_place=false; CHECK(!ir_verify(p).ok); p->arguments.data[aa]=saved;
            p->arguments.data[aa].capture=IR_NONE; CHECK(!ir_verify(p).ok); p->arguments.data[aa]=saved;
            IrInstruction cap=p->instructions.data[capture];
            p->instructions.data[capture].effects=0; CHECK(!ir_verify(p).ok); p->instructions.data[capture]=cap;
            p->instructions.data[capture].flag=false; CHECK(!ir_verify(p).ok); p->instructions.data[capture]=cap;
            uint32_t second=p->arguments.data[aa+1].capture; IrInstruction second_saved=p->instructions.data[second];
            p->instructions.data[second].place=cap.place; CHECK(!ir_verify(p).ok); p->instructions.data[second]=second_saved;
            p->arguments.data[aa+1].capture=capture; CHECK(!ir_verify(p).ok); p->arguments.data[aa+1].capture=second;
            IrPlace place=p->places.data[cap.place];
            p->places.data[cap.place].parent=cap.place; CHECK(!ir_verify(p).ok); p->places.data[cap.place]=place;
            p->places.data[cap.place].mutable=false; CHECK(!ir_verify(p).ok); p->places.data[cap.place]=place;
            p->places.data[cap.place].field=IR_NONE; CHECK(!ir_verify(p).ok); p->places.data[cap.place]=place;
            uint32_t fields=p->instructions.data[construct].args_start; IrArgument second_field=p->arguments.data[fields+1];
            p->arguments.data[fields+1].field=p->arguments.data[fields].field; CHECK(!ir_verify(p).ok); p->arguments.data[fields+1]=second_field;
            uint32_t destination=find_op(p,IR_DESTINATION), write=IR_NONE;
            CHECK(destination!=IR_NONE);
            for (uint32_t n=0;n<p->instructions.len;n++) if (p->instructions.data[n].op==IR_STORE && p->instructions.data[n].b==destination) { write=n; break; }
            CHECK(write!=IR_NONE);
            if (write!=IR_NONE) {
                IrInstruction saved_write=p->instructions.data[write];
                p->instructions.data[write].b=IR_NONE; CHECK(!ir_verify(p).ok); p->instructions.data[write]=saved_write;
                p->instructions.data[write].b=capture; CHECK(!ir_verify(p).ok); p->instructions.data[write]=saved_write;
                IrInstruction saved_destination=p->instructions.data[destination];
                p->instructions.data[destination].place=p->instructions.data[second].place; CHECK(!ir_verify(p).ok); p->instructions.data[destination]=saved_destination;
            }
            CHECK(ir_verify(p).ok);
        }
        if (s.a) arena_free(s.a); arena_free(a);
    }
    {
        CASE("IR: full existing PID implementation and analytical plus seeded operation corpus");
        Parsed s=parse_pid(); Arena *a=arena_new(0); IrProgram *p=ir_lower(a,s.d,s.sm,s.p); CHECK(p!=NULL);
        if (!p) { Str why=diag_render_str(s.a,s.d); printf("%.*s\n",(int)why.len,why.ptr); }
        FILE *refout=tmpfile(),*refevents=tmpfile(),*out=tmpfile(),*events=tmpfile(); CHECK(refout && refevents && out && events);
        if (p && refout && refevents && out && events) {
            RefResult ref=reference_test(s.d,s.p,(RefOpts){.output=refout,.events=refevents});
            CHECK_EQ_I(ref.status,REF_SUCCESS); CHECK_EQ_I(ref.tests,8); CHECK(ref.assertions>1000);
            Str expected=captured(a,refout),expected_events=captured(a,refevents);
            arena_free(s.a); s.a=NULL;
            IrRunResult run=ir_test(p,(IrRunOpts){.output=out,.events=events});
            CHECK_EQ_I(run.status,IR_RUN_SUCCESS); CHECK_EQ_I(run.tests,8); CHECK_EQ_I(run.assertions,ref.assertions);
            CHECK(str_eq(captured(a,out),expected)); CHECK(str_eq(captured(a,events),expected_events));
            printf("IR PID corpus: %u tests, %llu assertions, %llu IR steps, %u output bytes, %u exact event bytes\n",run.tests,(unsigned long long)run.assertions,(unsigned long long)run.steps,expected.len,expected_events.len);
            uint32_t mutation=IR_NONE;
            const char *needle="self.integral += err * dt";
            for (uint32_t n=0;n<p->instructions.len;n++) {
                IrInstruction *i=&p->instructions.data[n];
                if (i->op==IR_BINARY && i->numeric==IR_ADD && i->source.origin.file==0 &&
                    i->source.origin.len>=strlen(needle) && !memcmp(p->sources.data[0].text.ptr+i->source.origin.offset,needle,strlen(needle))) { mutation=n; break; }
            }
            CHECK(mutation!=IR_NONE);
            if (mutation!=IR_NONE) {
                p->instructions.data[mutation].numeric=IR_SUB; CHECK(ir_verify(p).ok);
                FILE *mutout=tmpfile(),*mutevents=tmpfile(); CHECK(mutout && mutevents);
                if (mutout && mutevents) {
                    IrRunResult mutant=ir_test(p,(IrRunOpts){.output=mutout,.events=mutevents});
                    CHECK_EQ_I(mutant.status,IR_RUN_FAILED);
                    CHECK(!str_eq(captured(a,mutout),expected)); CHECK(!str_eq(captured(a,mutevents),expected_events));
                }
                if (mutout) fclose(mutout); if (mutevents) fclose(mutevents);
                p->instructions.data[mutation].numeric=IR_ADD;
            }
        }
        if (refout) fclose(refout); if (refevents) fclose(refevents); if (out) fclose(out); if (events) fclose(events);
        if (s.a) arena_free(s.a); arena_free(a);
    }
    {
        CASE("IR: malformed indices, effects, cycles, calls, initialization and value order are rejected");
        Parsed s=parse("module t\nfn add(let n: i32) -> i32 { return n + 1 }\n"
            "fn choose(let b: bool) -> i32 { if b { return 3 }\nreturn 4 }\n"
            "test \"good\" { let n = 4\nlet spare = 9\nassert(add(n) == 5)\nassert(choose(true) == 3) }\n");
        Arena *a=arena_new(0); IrProgram *p=ir_lower(a,s.d,s.sm,s.p); CHECK(p!=NULL);
        if (p) {
            uint32_t add=find_op(p,IR_BINARY), init=find_op(p,IR_INIT), call_id=find_op(p,IR_CALL);
            CHECK(add!=IR_NONE && init!=IR_NONE && call_id!=IR_NONE);
            IrInstruction saved=p->instructions.data[add];
            p->instructions.data[add].a=IR_NONE; CHECK(!ir_verify(p).ok); p->instructions.data[add]=saved;
            p->instructions.data[add].a=saved.result; CHECK(!ir_verify(p).ok); p->instructions.data[add]=saved;
            p->instructions.data[add].effects=0; CHECK(!ir_verify(p).ok); p->instructions.data[add]=saved;
            p->instructions.data[add].next=add; CHECK(!ir_verify(p).ok); p->instructions.data[add]=saved;
            p->instructions.data[add].op=(IrOp)-1; CHECK(!ir_verify(p).ok); p->instructions.data[add]=saved;
            IrType result_saved=p->functions.data[0].result;
            p->functions.data[0].result=(IrType)-1; CHECK(!ir_verify(p).ok); p->functions.data[0].result=result_saved;
            IrInstruction init_saved=p->instructions.data[init];
            /* A first STORE is now legal; reading that still-uninitialized
             * root in place of its initialization must remain invalid. */
            p->instructions.data[init].op=IR_CAPTURE; p->instructions.data[init].immediate=IR_LET;
            p->instructions.data[init].flag=false; p->instructions.data[init].effects=IR_READ;
            CHECK(!ir_verify(p).ok); p->instructions.data[init]=init_saved;
            /* Retargeting a later INIT to this already initialized immutable
             * place must fail even though INIT does not carry STORE's mode. */
            uint32_t second_init=IR_NONE;
            for (uint32_t k=init+1;k<p->instructions.len;k++) if (p->instructions.data[k].op==IR_INIT) { second_init=k; break; }
            CHECK(second_init!=IR_NONE);
            if (second_init!=IR_NONE) {
                IrInstruction other=p->instructions.data[second_init];
                p->instructions.data[second_init].place=init_saved.place; CHECK(!ir_verify(p).ok); p->instructions.data[second_init]=other;
            }
            IrInstruction call_saved=p->instructions.data[call_id];
            p->instructions.data[call_id].function=IR_NONE; CHECK(!ir_verify(p).ok); p->instructions.data[call_id]=call_saved;
            p->instructions.data[call_id].args_count++; CHECK(!ir_verify(p).ok); p->instructions.data[call_id]=call_saved;
            uint32_t conditional=find_op(p,IR_IF); IrInstruction branch_saved=p->instructions.data[conditional];
            p->instructions.data[conditional].child[0]=branch_saved.region; CHECK(!ir_verify(p).ok); p->instructions.data[conditional]=branch_saved;
            uint32_t yes=p->regions.data[branch_saved.child[0]].first;
            uint32_t tail=p->regions.data[branch_saved.region].last;
            IrInstruction return_saved=p->instructions.data[tail];
            p->instructions.data[tail].a=p->instructions.data[yes].result; CHECK(!ir_verify(p).ok); p->instructions.data[tail]=return_saved;
            CHECK(ir_verify(p).ok);
            p->instructions.data[add].numeric=IR_SUB; CHECK(ir_verify(p).ok);
            FILE *out=tmpfile(); CHECK(out!=NULL);
            if (out) { IrRunResult mutant=ir_test(p,(IrRunOpts){.output=out}); CHECK_EQ_I(mutant.status,IR_RUN_FAILED); fclose(out); }
            p->instructions.data[add]=saved;
        }
        arena_free(a); arena_free(s.a);
    }
    {
        CASE("IR: finite-f32 semantic and nonfinite-constant mutants are distinguished");
        Parsed s=parse("module t\ntest \"float mutant\" { let one: f32 = 1\nprintln(one)\nassert((16777216f32 + one) - 16777216f32 == 0) }\n");
        Arena *a=arena_new(0); IrProgram *p=ir_lower(a,s.d,s.sm,s.p); CHECK(p!=NULL);
        if (p) {
            arena_free(s.a); s.a=NULL; uint32_t selected=IR_NONE;
            for (uint32_t n=0;n<p->instructions.len;n++) if (p->instructions.data[n].op==IR_CONST &&
                p->values.data[p->instructions.data[n].result].type==IR_F32 && p->instructions.data[n].float_bits==UINT32_C(0x3f800000)) { selected=n; break; }
            CHECK(selected!=IR_NONE); FILE *out=tmpfile(),*events=tmpfile(); CHECK(out && events);
            if (selected!=IR_NONE && out && events) {
                IrRunResult base=ir_test(p,(IrRunOpts){.output=out,.events=events}); CHECK_EQ_I(base.status,IR_RUN_SUCCESS);
                CHECK_CONTAINS(captured(a,events),"\"bits\":1065353216");
                p->instructions.data[selected].float_bits=UINT32_C(0x7f800000); CHECK(!ir_verify(p).ok);
                p->instructions.data[selected].float_bits=UINT32_C(0x7fc00000); CHECK(!ir_verify(p).ok);
                p->instructions.data[selected].float_bits=UINT32_C(0x40000000); CHECK(ir_verify(p).ok);
                IrRunResult mutant=ir_test(p,(IrRunOpts){.output=out}); CHECK_EQ_I(mutant.status,IR_RUN_FAILED);
            }
            if (out) fclose(out); if (events) fclose(events);
        }
        if (s.a) arena_free(s.a); arena_free(a);
    }
    {
        CASE("IR: independently retained source manifest and span bounds reject stale or malformed provenance");
        Parsed s=parse("module t\ntest \"source\" { assert(true) }\n");
        srcmap_add(s.sm,str_from("unused.be"),str_from("module unused\n"));
        Arena *a=arena_new(0); IrProgram *p=ir_lower(a,s.d,s.sm,s.p); CHECK(p!=NULL);
        if (p) {
            arena_free(s.a); s.a=NULL;
            CHECK(ir_verify(p).ok); CHECK_EQ_I(p->sources.len,2);
            IrSource original=p->instructions.data[0].source;
            p->instructions.data[0].source.origin.offset=UINT32_MAX; CHECK(!ir_verify(p).ok); p->instructions.data[0].source=original;
            p->instructions.data[0].source.origin.len=UINT32_MAX; CHECK(!ir_verify(p).ok); p->instructions.data[0].source=original;
            p->instructions.data[0].source.has_expansion=true;
            p->instructions.data[0].source.expansion=(Span){.file=2,.offset=0,.len=0}; CHECK(!ir_verify(p).ok); p->instructions.data[0].source=original;
            IrSourceFile first=p->sources.data[0]; p->sources.data[0]=p->sources.data[1]; p->sources.data[1]=first;
            CHECK(!ir_verify(p).ok); p->sources.data[1]=p->sources.data[0]; p->sources.data[0]=first;
            Str hash=p->sources.data[0].sha256; p->sources.data[0].sha256=str_from("0000000000000000000000000000000000000000000000000000000000000000");
            CHECK(!ir_verify(p).ok); p->sources.data[0].sha256=hash;
            Str text=p->sources.data[0].text; p->sources.data[0].text=str_from("changed"); CHECK(!ir_verify(p).ok); p->sources.data[0].text=text;
            CHECK(ir_verify(p).ok);
        }
        if (s.a) arena_free(s.a); arena_free(a);
    }
    {
        CASE("IR: execution budgets and cancellation do not become source traps");
        Parsed s=parse("module t\ntest \"loop\" { while true {} }\n"); Arena *a=arena_new(0);
        IrProgram *p=ir_lower(a,s.d,s.sm,s.p); CHECK(p!=NULL); FILE *out=tmpfile(); CHECK(out!=NULL);
        if (p && out) {
            IrRunResult steps=ir_test(p,(IrRunOpts){.output=out,.max_steps=30}); CHECK_EQ_I(steps.status,IR_RUN_BUDGET); CHECK_EQ_I(steps.trap,IR_TRAP_NONE);
            IrRunResult memory=ir_test(p,(IrRunOpts){.output=out,.max_bytes=1}); CHECK_EQ_I(memory.status,IR_RUN_BUDGET);
            IrRunResult cancel=ir_test(p,(IrRunOpts){.output=out,.cancelled=cancelled}); CHECK_EQ_I(cancel.status,IR_RUN_CANCELLED); CHECK(!cancel.trace_complete);
            IrRunResult no_clock=ir_test(p,(IrRunOpts){.output=out,.timeout_ms=1}); CHECK_EQ_I(no_clock.status,IR_RUN_UNAVAILABLE); CHECK_EQ_I(no_clock.steps,0);
            fake_clock_value=0;
            IrRunResult timed=ir_test(p,(IrRunOpts){.output=out,.timeout_ms=2,.clock_ms=fake_clock}); CHECK_EQ_I(timed.status,IR_RUN_TIMEOUT); CHECK_EQ_I(timed.trap,IR_TRAP_NONE);
            IrRunResult too_deep=ir_test(p,(IrRunOpts){.output=out,.max_call_depth=IR_MAX_DEPTH+1}); CHECK_EQ_I(too_deep.status,IR_RUN_UNAVAILABLE);
        }
        if (out) fclose(out); arena_free(a); arena_free(s.a);
    }
}
