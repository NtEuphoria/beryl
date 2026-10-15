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

    CASE("ownership: BE0401 labels both overlapping borrows");
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
    CHECK_CONTAINS(out, "cannot be borrowed exclusively in the same call");

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

    bad_src("ownership: a let method receiver overlaps an inout argument",
            "module t\n"
            "struct P { x: i32 }\n"
            "fn P.read(let self, inout other: P) -> i32 {\n"
            "    return self.x + other.x\n"
            "}\n"
            "fn m() {\n"
            "    var p = P{ x: 1 }\n"
            "    p.read(inout p)\n"
            "}\n",
            "BE0401", NULL);

    bad_src("ownership: a let aggregate overlaps an inout of the same value",
            "module t\n"
            "struct P { x: i32 }\n"
            "fn f(inout a: P, let b: P) {\n"
            "    a.x = b.x\n"
            "}\n"
            "fn m() {\n"
            "    var p = P{ x: 1 }\n"
            "    f(inout p, p)\n"
            "}\n",
            "BE0401", NULL);

    ok_src("ownership: a call result is a copy, not an alias of its argument",
           "module t\n"
           "struct P { x: i32 }\n"
           "fn id(let p: P) -> P { return p }\n"
           "fn f(inout a: P, let b: P) { a.x = b.x }\n"
           "fn m() {\n"
           "    var p = P{ x: 1 }\n"
           "    f(inout p, id(p))\n"
           "}\n");

    ok_src("ownership: a default aggregate does not alias an inout argument",
           "module t\n"
           "struct P { x: i32 = 0 }\n"
           "fn f(inout a: P, let b: P = P{ }) { a.x = b.x }\n"
           "fn m() {\n"
           "    var p = P{ x: 1 }\n"
           "    f(inout p)\n"
           "}\n");

    bad_src("ownership: list set overlaps a get of the same list",
            "module t\n"
            "fn m() {\n"
            "    var xs: List<i32>\n"
            "    xs.push(1)\n"
            "    xs.set(0, xs.get(0))\n"
            "}\n",
            "BE0401", NULL);

    bad_src("ownership: an inout list overlaps its own len() in one call",
            "module t\n"
            "fn f(inout xs: List<i32>, n: i32) { xs.push(n) }\n"
            "fn m() {\n"
            "    var xs: List<i32>\n"
            "    f(inout xs, xs.len())\n"
            "}\n",
            "BE0401", NULL);

    ok_src("ownership: list len() in a separate statement does not overlap a later push",
           "module t\n"
           "fn m() {\n"
           "    var xs: List<i32>\n"
           "    let n = xs.len()\n"
           "    xs.push(n)\n"
           "}\n");
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

    /* Four holes that all let a read of uninitialized memory through. The
     * native back end emits a bare `int32_t x;` for these, so each one was a
     * genuine read of whatever was on the stack. */

    bad_src("ownership: a loop may run zero times, so its body cannot initialize",
            "module t\n"
            "fn m() -> i32 {\n"
            "    var x: i32\n"
            "    while false {\n"
            "        x = 1\n"
            "    }\n"
            "    return x\n"
            "}\n",
            "BE0405", "used before it is initialized");

    ok_src("ownership: a loop body still initializes for reads inside it",
           "module t\n"
           "fn m() -> i32 {\n"
           "    var x: i32\n"
           "    x = 0\n"
           "    for i in 0..3 {\n"
           "        x += i\n"
           "    }\n"
           "    return x\n"
           "}\n");

    bad_src("ownership: compound assignment reads before it writes",
            "module t\n"
            "fn m() -> i32 {\n"
            "    var y: i32\n"
            "    y += 1\n"
            "    return y\n"
            "}\n",
            "BE0405", "used before it is initialized");

    bad_src("ownership: `inout` lends a value, it does not promise to create one",
            "module t\n"
            "fn bump(inout n: i32) {\n"
            "    n += 1\n"
            "}\n"
            "fn m() -> i32 {\n"
            "    var z: i32\n"
            "    bump(inout z)\n"
            "    return z\n"
            "}\n",
            "BE0405", "passed `inout` before it is initialized");

    ok_src("ownership: `set` does promise it, so an uninitialized argument is fine",
           "module t\n"
           "fn fill(set n: i32) {\n"
           "    n = 7\n"
           "}\n"
           "fn m() -> i32 {\n"
           "    var a: i32\n"
           "    fill(set a)\n"
           "    return a\n"
           "}\n");

    bad_src("ownership: a catch handler runs only on the error path",
            "module t\n"
            "fn f() -> !i32 {\n"
            "    return 1\n"
            "}\n"
            "fn m() -> i32 {\n"
            "    var w: i32\n"
            "    let r = f() catch |e| { w = 1 }\n"
            "    return w\n"
            "}\n",
            "BE0405", "used before it is initialized");

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

static void test_receiver_modes(void) {
    bad_src("ownership: sink receiver marks the whole caller moved",
        "module t\nstruct R{x:i32}\nfn R.take(sink self)->i32{return self.x}\n"
        "fn f(){var r=R{x:1}\nr.take()\nprint(r.x)}\n", "BE0403", "after it was moved");
    bad_src("ownership: sink receiver cannot consume a let parameter",
        "module t\nstruct R{x:i32}\nfn R.take(sink self)->i32{return self.x}\n"
        "fn f(let r:R)->i32{return r.take()}\n", "BE0406", "borrowed parameter");
    bad_src("ownership: sink receiver cannot consume an inout parameter",
        "module t\nstruct R{x:i32}\nfn R.take(sink self)->i32{return self.x}\n"
        "fn f(inout r:R)->i32{return r.take()}\n", "BE0406", "borrowed parameter");
    bad_src("ownership: sink receiver cannot partially move a field",
        "module t\nstruct R{x:i32}\nstruct P{r:R}\nfn R.take(sink self)->i32{return self.x}\n"
        "fn f(){var p=P{r:R{x:1}}\np.r.take()}\n", "BE0406", "cannot move out of `p.r`");
    bad_src("ownership: sink receiver cannot partially move an array element",
        "module t\nstruct R{x:i32}\nfn R.take(sink self)->i32{return self.x}\n"
        "fn f(){var xs=[R{x:1}]\nxs[0].take()}\n", "BE0406", "cannot move out of");
    bad_src("ownership: sink receiver is consumed before later argument reads",
        "module t\nstruct R{x:i32}\nfn R.take(sink self,tag:i32)->i32{return self.x+tag}\n"
        "fn f(){var r=R{x:1}\nr.take(r.x)}\n", "BE0403", "after it was moved");
    ok_src("ownership: sink temporary receiver has no caller to consume",
        "module t\nstruct R{x:i32}\nfn R.take(sink self)->i32{return self.x}\n"
        "fn f()->i32{return R{x:1}.take()}\n");
    ok_src("ownership: set receiver initializes an uninitialized whole binding",
        "module t\nstruct R{x:i32}\nfn R.fill(set self){self=R{x:7}}\n"
        "fn f()->i32{var r:R\nr.fill()\nreturn r.x}\n");
    ok_src("ownership: set receiver can perform the first initialization of a let",
        "module t\nstruct R{x:i32}\nfn R.fill(set self){self=R{x:7}}\n"
        "fn f()->i32{let r:R\nr.fill()\nreturn r.x}\n");
    ok_src("ownership: set receiver discharges an outer set initialization contract",
        "module t\nstruct R{x:i32}\nfn R.fill(set self){self=R{x:7}}\n"
        "fn f(set r:R){r.fill()}\n");
    ok_src("ownership: set receiver reinitializes storage after a whole move",
        "module t\nstruct R{x:i32}\nfn R.take(sink self)->i32{return self.x}\n"
        "fn R.fill(set self){self=R{x:7}}\n"
        "fn f()->i32{var r=R{x:1}\nr.take()\nr.fill()\nreturn r.x}\n");
    bad_src("ownership: set receiver cannot replace an initialized immutable local",
        "module t\nstruct R{x:i32}\nfn R.fill(set self){self=R{x:7}}\n"
        "fn f(){let r=R{x:1}\nr.fill()}\n", "BE0407", "immutable");
    bad_src("ownership: set receiver cannot replace a read-only parameter",
        "module t\nstruct R{x:i32}\nfn R.fill(set self){self=R{x:7}}\n"
        "fn f(let r:R){r.fill()}\n", "BE0407", "let` parameter");
    bad_src("ownership: set receiver is not initialized before later arguments",
        "module t\nstruct R{x:i32}\nfn R.fill(set self,tag:i32){self=R{x:tag}}\n"
        "fn f(){var r:R\nr.fill(r.x)}\n", "BE0405", "before it is initialized");
    bad_src("ownership: set receiver does not initialize a partial uninitialized parent",
        "module t\nstruct R{x:i32}\nstruct P{r:R}\nfn R.fill(set self){self=R{x:7}}\n"
        "fn f(){var p:P\np.r.fill()}\n", "BE0405", "before it is initialized");
    bad_src("ownership: conditional set method still must initialize on every return",
        "module t\nstruct R{x:i32}\nfn R.fill(set self,flag:bool){if flag{self=R{x:7}}}\n",
        "BE0404", "not initialized");
    ok_src("ownership: let receiver index transfer is traversed only once",
        "module t\nstruct R{x:i32}\nfn R.read(let self)->i32{return self.x}\n"
        "fn index(sink n:i32)->i32{return n}\n"
        "fn f()->i32{var xs=[R{x:1}]\nvar n=0\nreturn xs[index(sink n)].read()}\n");
    bad_src("ownership: once-evaluated let receiver index still records its transfer",
        "module t\nstruct R{x:i32}\nfn R.read(let self)->i32{return self.x}\n"
        "fn index(sink n:i32)->i32{return n}\n"
        "fn f(){var xs=[R{x:1}]\nvar n=0\nxs[index(sink n)].read()\nprint(n)}\n",
        "BE0403", "after it was moved");
    ok_src("ownership: set receiver index transfer is traversed only once",
        "module t\nstruct R{x:i32}\nfn R.fill(set self){self=R{x:7}}\n"
        "fn index(sink n:i32)->i32{return n}\n"
        "fn f()->i32{var xs=[R{x:1}]\nvar n=0\nxs[index(sink n)].fill()\nreturn xs[0].x}\n");
    ok_src("ownership: set receiver precedes an expanded nonmutating default",
        "module t\nstruct R{x:i32}\nfn mark()->i32{println(7)\nreturn 7}\n"
        "fn R.fill(set self,tag:i32=mark()){self=R{x:tag}}\n"
        "fn f()->i32{var r:R\nr.fill()\nreturn r.x}\n");
}

void run_ownership_tests(void) {
    bad_src("ownership: destination index expressions cannot hide a read",
        "module t\nfn idx(let x: i32) -> i32 { return x }\n"
        "fn f() { var a = [1]\nlet x: i32\na[idx(x)] = 0 }\n",
        "BE0405", NULL);
    bad_src("ownership: try failure must initialize set output",
        "module t\nfn fail() -> !i32 { return error.Bad }\n"
        "fn fill(set x: i32) -> !i32 { let y = try fail()\nx = y\nreturn y }\n",
        "BE0404", NULL);
    ok_src("ownership: initialized set output permits try",
        "module t\nfn fail() -> !i32 { return error.Bad }\n"
        "fn fill(set x: i32) -> !i32 { x = 0\nreturn try fail() }\n");
    bad_src("ownership: later argument reads before set call executes",
        "module t\nfn fill(set x: i32, let y: i32) { x = y }\n"
        "fn f() { var x: i32\nfill(set x, x) }\n", "BE0405", NULL);
    bad_src("ownership: short circuit may skip initialization",
        "module t\nfn fill(set x: i32) -> bool { x = 1\nreturn true }\n"
        "fn f() { var x: i32\nlet b = false && fill(set x)\nprint(x) }\n",
        "BE0405", NULL);
    bad_src("ownership: returning loop body does not erase fallthrough",
        "module t\nfn f(set x: i32) { while false { x = 1\nreturn } }\n",
        "BE0404", NULL);
    bad_src("ownership: catch return leaves success path live",
        "module t\nfn v() -> !i32 { return 1 }\n"
        "fn f(set x: i32) { let a = v() catch |e| { x = 1\nreturn } }\n",
        "BE0404", NULL);
    bad_src("ownership: break bypasses later initialization",
        "module t\nfn f() { var x: i32\nwhile true { break\nx = 1 }\nprint(x) }\n",
        "BE0405", NULL);
    bad_src("ownership: immutable list cannot mutate through intrinsic",
        "module t\nfn f(let xs: List<i32>) { xs.push(1) }\n", "BE0407", NULL);
    test_exclusivity();
    test_moves();
    test_init();
    test_borrow_mutation();
    test_set_param();
    test_receiver_modes();
    test_loops_and_reality();
}
