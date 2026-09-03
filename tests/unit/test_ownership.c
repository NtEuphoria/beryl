/* Tests for mutable value semantics: definite init, moves, exclusivity. */
#include "../../src/parse/parser.h"
#include "../../src/sema/check.h"
#include "../../src/sema/ownership.h"
#include "test.h"

typedef struct {
    Arena     *a;
    SourceMap *sm;
    DiagBag   *d;
    Interner  *in;
    Program   *p;
} Fx;

static Fx fx_new(void) {
    Fx f = {0};
    f.a  = arena_new(0);
    f.sm = srcmap_new(f.a);
    f.d  = diag_new(f.a, f.sm);
    f.in = intern_new(f.a);
    f.p  = prog_new(f.a);
    return f;
}

/* Runs the whole front end including ownership. Frees the previous arena, so
 * the returned Str is valid until the next call. */
static Str own(const char *src, uint32_t *errors) {
    static Arena *keep = NULL;
    if (keep) arena_free(keep);
    Fx f = fx_new();
    keep = f.a;

    uint32_t file = srcmap_add(f.sm, str_from("t.be"), str_from(src));
    TokenVec toks = lex_file(f.a, f.sm, f.d, f.in, file);
    prog_add_module(f.p, parse_file(f.a, f.d, f.in, toks, file));

    resolve_program(f.d, f.p);
    check_program(f.d, f.p);
    ownership_check(f.d, f.p);

    if (errors) *errors = diag_errors(f.d);
    return diag_render_str(f.a, f.d);
}

static void ok_src(const char *what, const char *src) {
    CASE(what);
    uint32_t errs = 0;
    Str      out  = own(src, &errs);
    if (errs) printf("%.*s\n", (int)out.len, out.ptr);
    CHECK_EQ_I(errs, 0);
}

static void bad_src(const char *what, const char *src, const char *code, const char *text) {
    CASE(what);
    uint32_t errs = 0;
    Str      out  = own(src, &errs);
    CHECK(errs >= 1);
    CHECK_CONTAINS(out, code);
    if (text) CHECK_CONTAINS(out, text);
}

static void test_exclusivity(void) {
    bad_src("ownership: two inout borrows of the same binding is BE0401",
            "module t\n"
            "fn swap2(inout a: i32, inout b: i32) {\n"
            "    a = b\n"
            "}\n"
            "fn m() {\n"
            "    var a = 1\n"
            "    swap2(inout a, inout a)\n"
            "}\n",
            "BE0401", "overlapping exclusive borrows of `a`");

    CASE("ownership: BE0401 labels both borrows and explains restrict");
    uint32_t errs = 0;
    Str      out  = own("module t\n"
                        "fn swap2(inout a: i32, inout b: i32) {\n"
                        "    a = b\n"
                        "}\n"
                        "fn m() {\n"
                        "    var a = 1\n"
                        "    swap2(inout a, inout a)\n"
                        "}\n",
                        &errs);
    CHECK_CONTAINS(out, "first exclusive borrow here");
    CHECK_CONTAINS(out, "second exclusive borrow here");
    CHECK_CONTAINS(out, "licenses `restrict`");

    bad_src("ownership: an inout that overlaps a shared borrow is BE0401",
            "module t\n"
            "struct P { x: i32, y: i32 }\n"
            "fn f(inout a: P, b: i32) {\n"
            "    a.x = b\n"
            "}\n"
            "fn m() {\n"
            "    var p = P{ x: 1, y: 2 }\n"
            "    f(inout p, p.x)\n"
            "}\n",
            "BE0401", NULL);

    ok_src("ownership: disjoint fields may be borrowed exclusively at once",
           "module t\n"
           "struct P { x: i32, y: i32 }\n"
           "fn f(inout a: i32, inout b: i32) {\n"
           "    a = b\n"
           "}\n"
           "fn m() {\n"
           "    var p = P{ x: 1, y: 2 }\n"
           "    f(inout p.x, inout p.y)\n"
           "}\n");

    bad_src("ownership: a field overlapping its whole struct is BE0401",
            "module t\n"
            "struct P { x: i32, y: i32 }\n"
            "fn f(inout a: P, inout b: i32) {\n"
            "    b = 1\n"
            "}\n"
            "fn m() {\n"
            "    var p = P{ x: 1, y: 2 }\n"
            "    f(inout p, inout p.x)\n"
            "}\n",
            "BE0401", NULL);

    bad_src("ownership: an inout method receiver participates in exclusivity",
            "module t\n"
            "struct P { x: i32 }\n"
            "fn P.bump(inout self, inout other: P) {\n"
            "    self.x = other.x\n"
            "}\n"
            "fn m() {\n"
            "    var p = P{ x: 1 }\n"
            "    p.bump(inout p)\n"
            "}\n",
            "BE0401", NULL);
}

static void test_moves(void) {
    bad_src("ownership: use after move is BE0403 with the move site labelled",
            "module t\n"
            "struct Big { a: i32, b: i32 }\n"
            "fn take(sink v: Big) {\n"
            "    let q = v.a\n"
            "}\n"
            "fn m() {\n"
            "    let x = Big{ a: 1, b: 2 }\n"
            "    take(sink x)\n"
            "    let y = x.a\n"
            "}\n",
            "BE0403", "use of `x` after it was moved");

    CASE("ownership: BE0403 labels where the move happened");
    uint32_t errs = 0;
    Str      out  = own("module t\n"
                        "struct Big { a: i32 }\n"
                        "fn take(sink v: Big) {\n"
                        "    let q = v.a\n"
                        "}\n"
                        "fn m() {\n"
                        "    let x = Big{ a: 1 }\n"
                        "    take(sink x)\n"
                        "    let y = x.a\n"
                        "}\n",
                        &errs);
    CHECK_CONTAINS(out, "moved here");
    CHECK_CONTAINS(out, "used here after the move");

    ok_src("ownership: moving in both branches then not using it is fine",
           "module t\n"
           "struct Big { a: i32 }\n"
           "fn take(sink v: Big) {\n"
           "    let q = v.a\n"
           "}\n"
           "fn m(let c: bool) {\n"
           "    let x = Big{ a: 1 }\n"
           "    if c {\n"
           "        take(sink x)\n"
           "    } else {\n"
           "        take(sink x)\n"
           "    }\n"
           "}\n");

    bad_src("ownership: a move on only one branch poisons the merge",
            "module t\n"
            "struct Big { a: i32 }\n"
            "fn take(sink v: Big) {\n"
            "    let q = v.a\n"
            "}\n"
            "fn m(let c: bool) {\n"
            "    let x = Big{ a: 1 }\n"
            "    if c {\n"
            "        take(sink x)\n"
            "    }\n"
            "    let y = x.a\n"
            "}\n",
            "BE0403", NULL);

    bad_src("ownership: cannot move out of a field is BE0406",
            "module t\n"
            "struct Inner { v: i32 }\n"
            "struct Outer { i: Inner }\n"
            "fn take(sink v: Inner) {\n"
            "    let q = v.v\n"
            "}\n"
            "fn m() {\n"
            "    let o = Outer{ i: Inner{ v: 1 } }\n"
            "    take(sink o.i)\n"
            "}\n",
            "BE0406", "cannot move out of `o.i`");

    bad_src("ownership: cannot move out of a borrowed parameter is BE0406",
            "module t\n"
            "struct Big { a: i32 }\n"
            "fn take(sink v: Big) {\n"
            "    let q = v.a\n"
            "}\n"
            "fn m(let b: Big) {\n"
            "    take(sink b)\n"
            "}\n",
            "BE0406", "borrowed parameter");
}

static void test_init(void) {
    bad_src("ownership: reading an uninitialized binding is BE0405",
            "module t\n"
            "fn m() -> i32 {\n"
            "    let x: i32\n"
            "    return x\n"
            "}\n",
            "BE0405", "used before it is initialized");

    ok_src("ownership: a deferred initialization is fine once assigned",
           "module t\n"
           "fn m(let c: bool) -> i32 {\n"
           "    var x: i32\n"
           "    if c {\n"
           "        x = 1\n"
           "    } else {\n"
           "        x = 2\n"
           "    }\n"
           "    return x\n"
           "}\n");

    bad_src("ownership: initialized on only one branch is still BE0405",
            "module t\n"
            "fn m(let c: bool) -> i32 {\n"
            "    var x: i32\n"
            "    if c {\n"
            "        x = 1\n"
            "    }\n"
            "    return x\n"
            "}\n",
            "BE0405", NULL);

    ok_src("ownership: a returning branch does not poison the merge",
           "module t\n"
           "fn m(let c: bool) -> i32 {\n"
           "    var x: i32\n"
           "    if c {\n"
           "        return 0\n"
           "    } else {\n"
           "        x = 2\n"
           "    }\n"
           "    return x\n"
           "}\n");

    bad_src("ownership: assigning twice to a `let` is BE0402",
            "module t\n"
            "fn m() {\n"
            "    let x = 1\n"
            "    x = 2\n"
            "}\n",
            "BE0402", "cannot assign twice to immutable `x`");

    bad_src("ownership: assigning to a field of a `let` is BE0402",
            "module t\n"
            "struct P { x: i32 }\n"
            "fn m() {\n"
            "    let p = P{ x: 1 }\n"
            "    p.x = 2\n"
            "}\n",
            "BE0402", "is immutable");
}

static void test_borrow_mutation(void) {
    bad_src("ownership: assigning through a `let` parameter is BE0407",
            "module t\n"
            "struct P { x: i32 }\n"
            "fn f(let p: P) {\n"
            "    p.x = 1\n"
            "}\n",
            "BE0407", "through a `let` borrow");

    bad_src("ownership: passing a `let` parameter as inout is BE0407",
            "module t\n"
            "fn g(inout a: i32) {\n"
            "    a = 1\n"
            "}\n"
            "fn f(let v: i32) {\n"
            "    g(inout v)\n"
            "}\n",
            "BE0407", "it is a `let` parameter");

    bad_src("ownership: borrowing an immutable local as inout is BE0407",
            "module t\n"
            "fn g(inout a: i32) {\n"
            "    a = 1\n"
            "}\n"
            "fn m() {\n"
            "    let v = 1\n"
            "    g(inout v)\n"
            "}\n",
            "BE0407", "cannot borrow immutable");

    ok_src("ownership: mutating through an inout parameter is fine",
           "module t\n"
           "struct P { x: i32 }\n"
           "fn f(inout p: P) {\n"
           "    p.x = 1\n"
           "}\n");
}

static void test_set_param(void) {
    bad_src("ownership: a `set` parameter left unassigned is BE0404",
            "module t\n"
            "fn f(set out: i32) {\n"
            "    let q = 1\n"
            "}\n",
            "BE0404", "not initialized on every path");

    bad_src("ownership: a `set` parameter unassigned on one path is BE0404",
            "module t\n"
            "fn f(set out: i32, let c: bool) {\n"
            "    if c {\n"
            "        return\n"
            "    }\n"
            "    out = 1\n"
            "}\n",
            "BE0404", "not initialized on this path");

    ok_src("ownership: a `set` parameter assigned on every path is fine",
           "module t\n"
           "fn f(set out: i32, let c: bool) {\n"
           "    if c {\n"
           "        out = 0\n"
           "        return\n"
           "    }\n"
           "    out = 1\n"
           "}\n");
}

static void test_loops_and_reality(void) {
    ok_src("ownership: a loop variable is initialized by the loop",
           "module t\n"
           "fn m() -> i32 {\n"
           "    var s = 0\n"
           "    for i in 0..10 {\n"
           "        s += i\n"
           "    }\n"
           "    return s\n"
           "}\n");

    bad_src("ownership: a move inside a loop is caught on the second iteration",
            "module t\n"
            "struct Big { a: i32 }\n"
            "fn take(sink v: Big) {\n"
            "    let q = v.a\n"
            "}\n"
            "fn m() {\n"
            "    let x = Big{ a: 1 }\n"
            "    for i in 0..3 {\n"
            "        take(sink x)\n"
            "    }\n"
            "}\n",
            "BE0403", NULL);

    CASE("ownership: a loop reports a problem once, not once per iteration");
    uint32_t errs = 0;
    own("module t\n"
        "struct Big { a: i32 }\n"
        "fn take(sink v: Big) {\n"
        "    let q = v.a\n"
        "}\n"
        "fn m() {\n"
        "    let x = Big{ a: 1 }\n"
        "    for i in 0..3 {\n"
        "        take(sink x)\n"
        "    }\n"
        "}\n",
        &errs);
    CHECK_EQ_I(errs, 1);

    ok_src("ownership: the PID controller passes unchanged",
           "module flight.pid\n"
           "pub struct Pid {\n"
           "    kp: f32\n"
           "    ki: f32 = 0\n"
           "    integral: f32 = 0\n"
           "    last_meas: f32 = 0\n"
           "    has_last: bool = false\n"
           "}\n"
           "pub fn Pid.step(inout self, sp: f32, meas: f32, dt: f32) -> f32 {\n"
           "    if dt <= 0 {\n"
           "        return 0\n"
           "    }\n"
           "    let err = sp - meas\n"
           "    self.integral += err * dt\n"
           "    var deriv: f32 = 0\n"
           "    if self.has_last {\n"
           "        deriv = -(meas - self.last_meas) / dt\n"
           "    }\n"
           "    self.last_meas = meas\n"
           "    self.has_last = true\n"
           "    return self.kp * err + self.ki * self.integral + deriv\n"
           "}\n");
}

void run_ownership_tests(void) {
    test_exclusivity();
    test_moves();
    test_init();
    test_borrow_mutation();
    test_set_param();
    test_loops_and_reality();
}
