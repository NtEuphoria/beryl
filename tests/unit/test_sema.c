/* Tests for name resolution and type checking. */
#include "../../src/sema/check.h"
#include "../../src/parse/parser.h"
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
static void fx_free(Fx *f) { arena_free(f->a); }

static void add_src(Fx *f, const char *src) {
    uint32_t file = srcmap_add(f->sm, str_from("t.be"), str_from(src));
    TokenVec toks = lex_file(f->a, f->sm, f->d, f->in, file);
    prog_add_module(f->p, parse_file(f->a, f->d, f->in, toks, file));
}

/* Runs the whole front end and returns the rendered diagnostics. */
static Str sema(Fx *f, const char *src) {
    add_src(f, src);
    resolve_program(f->d, f->p);
    check_program(f->d, f->p);
    return diag_render_str(f->a, f->d);
}

/* One-shot: fresh fixture per source, returns diagnostics text. */
static Str sema1(const char *src, uint32_t *errors) {
    static Arena *keep = NULL;
    if (keep) arena_free(keep);
    Fx f  = fx_new();
    keep  = f.a;
    Str s = sema(&f, src);
    if (errors) *errors = diag_errors(f.d);
    return s; /* backed by `keep`, valid until the next call */
}

static void test_positive(void) {
    CASE("sema: a realistic method type-checks with no errors");
    uint32_t errs = 0;
    Str      out  = sema1("module flight.pid\n"
                          "pub struct Pid {\n"
                          "    kp: f32\n"
                          "    ki: f32 = 0\n"
                          "    integral: f32 = 0\n"
                          "    limit: f32 = 1\n"
                          "}\n"
                          "pub fn Pid.step(inout self, sp: f32, meas: f32, dt: f32) -> f32 {\n"
                          "    if dt <= 0 {\n"
                          "        return 0\n"
                          "    }\n"
                          "    let err = sp - meas\n"
                          "    self.integral += err * dt\n"
                          "    return self.kp * err + self.ki * self.integral\n"
                          "}\n",
                          &errs);
    if (errs) printf("%.*s\n", (int)out.len, out.ptr);
    CHECK_EQ_I(errs, 0);

    CASE("sema: integer literals adopt the expected numeric type");
    out = sema1("module t\n"
                "fn m() {\n"
                "    let a = 1\n"
                "    let b: f32 = 1\n"
                "    let c: i64 = 2\n"
                "    let d: f32 = 1.5\n"
                "    let e = 1u8\n"
                "}\n",
                &errs);
    if (errs) printf("%.*s\n", (int)out.len, out.ptr);
    CHECK_EQ_I(errs, 0);

    CASE("sema: recursion, calls, loops, casts");
    out = sema1("module t\n"
                "fn fact(let n: i32) -> i32 {\n"
                "    if n <= 1 {\n"
                "        return 1\n"
                "    }\n"
                "    return n * fact(n - 1)\n"
                "}\n"
                "fn m() -> i64 {\n"
                "    var s = 0\n"
                "    for i in 0..10 {\n"
                "        s += fact(i)\n"
                "    }\n"
                "    return s as i64\n"
                "}\n",
                &errs);
    if (errs) printf("%.*s\n", (int)out.len, out.ptr);
    CHECK_EQ_I(errs, 0);

    CASE("sema: struct literal, field access, arrays");
    out = sema1("module t\n"
                "struct P { x: f32, y: f32 = 0 }\n"
                "fn m() -> f32 {\n"
                "    let p = P{ x: 1.5 }\n"
                "    let arr = [1, 2, 3]\n"
                "    let q = arr[0]\n"
                "    return p.x\n"
                "}\n",
                &errs);
    if (errs) printf("%.*s\n", (int)out.len, out.ptr);
    CHECK_EQ_I(errs, 0);

    CASE("sema: error unions with try, orelse and catch");
    out = sema1("module t\n"
                "fn parse(let s: str) -> !i32 {\n"
                "    return 0\n"
                "}\n"
                "fn ok() -> !i32 {\n"
                "    let a = try parse(\"1\")\n"
                "    return a\n"
                "}\n"
                "fn fallback() -> i32 {\n"
                "    return parse(\"1\") orelse 7\n"
                "}\n",
                &errs);
    if (errs) printf("%.*s\n", (int)out.len, out.ptr);
    CHECK_EQ_I(errs, 0);

    CASE("sema: shadowing in a nested scope is allowed");
    out = sema1("module t\n"
                "fn m() {\n"
                "    let a = 1\n"
                "    if true {\n"
                "        let a = 2\n"
                "        let b = a\n"
                "    }\n"
                "}\n",
                &errs);
    if (errs) printf("%.*s\n", (int)out.len, out.ptr);
    CHECK_EQ_I(errs, 0);
}

/* Asserts that `src` produces a diagnostic containing `code` and `text`. */
static void expect_diag(const char *what, const char *src, const char *code,
                        const char *text) {
    CASE(what);
    uint32_t errs = 0;
    Str      out  = sema1(src, &errs);
    CHECK(errs >= 1);
    CHECK_CONTAINS(out, code);
    if (text) CHECK_CONTAINS(out, text);
}

static void test_diagnostics(void) {
    expect_diag("sema: unknown identifier is BE0301",
                "module t\nfn m() {\n    let a = nope\n}\n", "BE0301",
                "cannot find `nope` in this scope");

    expect_diag("sema: unknown type is BE0302",
                "module t\nfn m(let a: Nope) {\n    let q = 1\n}\n", "BE0302",
                "unknown type `Nope`");

    expect_diag("sema: type mismatch is BE0303",
                "module t\nfn m() {\n    let a: bool = \"x\"\n}\n", "BE0303", NULL);

    expect_diag("sema: wrong argument count is BE0304",
                "module t\nfn f(let a: i32) {\n    let q = 1\n}\n"
                "fn m() {\n    f(1, 2)\n}\n",
                "BE0304", "takes 1 argument");

    expect_diag("sema: unknown field is BE0305",
                "module t\nstruct P { x: i32 }\n"
                "fn m() {\n    let p = P{ x: 1 }\n    let q = p.nope\n}\n",
                "BE0305", "no field `nope`");

    expect_diag("sema: unknown method is BE0306",
                "module t\nstruct P { x: i32 }\n"
                "fn m() {\n    let p = P{ x: 1 }\n    p.nope()\n}\n",
                "BE0306", "no method `nope`");

    expect_diag("sema: calling a non-function is BE0307",
                "module t\nfn m() {\n    let a = 1\n    a()\n}\n", "BE0307",
                "is a value, not a function");

    expect_diag("sema: duplicate definition is BE0308",
                "module t\nfn f() {\n    let q = 1\n}\nfn f() {\n    let q = 2\n}\n",
                "BE0308", "defined twice");

    expect_diag("sema: missing return on a path is BE0310",
                "module t\nfn m(let c: bool) -> i32 {\n    if c {\n        return 1\n    }\n}\n",
                "BE0310", "not every path returns a value");

    expect_diag("sema: non-bool condition is BE0311",
                "module t\nfn m() {\n    if 1 {\n        let q = 1\n    }\n}\n", "BE0311",
                "must be `bool`");

    expect_diag("sema: implicit numeric conversion is BE0312 with a cast help",
                "module t\nfn m() {\n    let a: i32 = 1\n    let b: i64 = 2\n"
                "    let c = a + b\n}\n",
                "BE0312", "no implicit numeric conversion");

    expect_diag("sema: indexing a non-indexable type is BE0313",
                "module t\nfn m() {\n    let a = 1\n    let b = a[0]\n}\n", "BE0313",
                "cannot be indexed");

    expect_diag("sema: missing struct field is BE0314",
                "module t\nstruct P { x: i32, y: i32 }\n"
                "fn m() {\n    let p = P{ x: 1 }\n}\n",
                "BE0314", "missing field `y`");

    expect_diag("sema: unknown struct literal field is BE0315",
                "module t\nstruct P { x: i32 }\n"
                "fn m() {\n    let p = P{ x: 1, z: 2 }\n}\n",
                "BE0315", "has no field `z`");

    expect_diag("sema: break outside a loop is BE0316",
                "module t\nfn m() {\n    break\n}\n", "BE0316", "outside of a loop");

    expect_diag("sema: try without an error-union return is BE0317",
                "module t\nfn p() -> !i32 {\n    return 0\n}\n"
                "fn m() -> i32 {\n    let a = try p()\n    return a\n}\n",
                "BE0317", "requires the enclosing function to return");

    expect_diag("sema: convention mismatch at the call site",
                "module t\nfn f(inout a: i32) {\n    a = 1\n}\n"
                "fn m() {\n    var x = 0\n    f(x)\n}\n",
                "BE0303", "declared `inout` but passed as `let`");

    expect_diag("sema: assigning to a non-lvalue",
                "module t\nfn m() {\n    1 = 2\n}\n", "BE0303",
                "cannot be assigned to");

    expect_diag("sema: same-scope redeclaration is BE0308",
                "module t\nfn m() {\n    let a = 1\n    let a = 2\n}\n", "BE0308",
                "already declared in this scope");

    expect_diag("sema: a fractional literal cannot be an integer",
                "module t\nfn m() {\n    let a: i32 = 1.5\n}\n", "BE0303",
                "fractional literal");
}

static void test_containers(void) {
    CASE("containers: List methods type-check, and a container field defaults empty");
    uint32_t errs = 0;
    Str      out  = sema1("module t\n"
                          "struct S {\n"
                          "    ids: List<i32>\n"
                          "}\n"
                          "fn m() -> i32 {\n"
                          "    var s = S{ }\n"
                          "    s.ids.push(1)\n"
                          "    s.ids.set(0, 2)\n"
                          "    var free: List<i32>\n"
                          "    free.push(3)\n"
                          "    s.ids.clear()\n"
                          "    return s.ids.len() + free.get(0)\n"
                          "}\n",
                          &errs);
    if (errs) printf("%.*s\n", (int)out.len, out.ptr);
    CHECK_EQ_I(errs, 0);

    expect_diag("containers: an unknown List method names the ones that exist",
                "module t\nfn m() {\n    var xs: List<i32>\n    xs.frobnicate()\n}\n",
                "BE0306", "len, push, get, set and clear");

    expect_diag("containers: push checks its element type",
                "module t\nfn m() {\n    var xs: List<i32>\n    xs.push(1.5)\n}\n",
                "BE0303", NULL);

    CASE("parser: a reserved word is a valid member name");
    /* `set` is a passing convention, but `xs.set(i, v)` still has to parse. */
    out = sema1("module t\n"
                "struct Holder {\n"
                "    set: i32 = 0\n"
                "    for: i32 = 0\n"
                "}\n"
                "fn m() -> i32 {\n"
                "    let h = Holder{ set: 1, for: 2 }\n"
                "    return h.set + h.for\n"
                "}\n",
                &errs);
    if (errs) printf("%.*s\n", (int)out.len, out.ptr);
    CHECK_EQ_I(errs, 0);
}

static void test_const_eval(void) {
    CASE("const: literals, arithmetic and other constants fold");
    uint32_t errs = 0;
    Str      out  = sema1("module t\n"
                          "const W: i32 = 4\n"
                          "const H: i32 = 3\n"
                          "const CELLS: i32 = W * H\n"
                          "fn m() {\n"
                          "    let grid: [i32; CELLS] = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]\n"
                          "}\n",
                          &errs);
    if (errs) printf("%.*s\n", (int)out.len, out.ptr);
    CHECK_EQ_I(errs, 0);

    expect_diag("const: a non-constant array length is BE0505",
                "module t\nfn m(let n: i32) {\n    let a: [i32; n] = [0]\n}\n", "BE0505",
                "must be a constant integer");

    expect_diag("const: a negative array length is BE0505",
                "module t\nfn m() {\n    let a: [i32; 3 - 9] = [0]\n}\n", "BE0505",
                "cannot be negative");

    expect_diag("const: division by zero in a constant is BE0502",
                "module t\nconst BAD: i32 = 4 / 0\nfn m() {\n    let q = BAD\n}\n",
                "BE0502", "division by zero");

    expect_diag("const: constant overflow is BE0503",
                "module t\n"
                "const HUGE: i64 = 9223372036854775807\n"
                "const OVER: i64 = HUGE * 2\n"
                "fn m() {\n    let q = OVER\n}\n",
                "BE0503", "overflows a 64-bit value");

    CASE("const: the evaluator has no I/O to reach for, by construction");
    /* A call is simply not a constant expression; there is no sandbox to
     * escape because nothing beyond pure arithmetic is implemented. */
    out = sema1("module t\n"
                "fn side() -> i32 {\n    return 1\n}\n"
                "fn m() {\n    let a: [i32; side()] = [0]\n}\n",
                &errs);
    CHECK(errs >= 1);
    CHECK_CONTAINS(out, "BE0505");
}

static void test_warnings(void) {
    CASE("sema: unreachable code after return is a warning, not an error");
    Fx f = fx_new();
    Str out = sema(&f, "module t\nfn m() -> i32 {\n    return 1\n    let a = 2\n}\n");
    CHECK_EQ_I(diag_errors(f.d), 0);
    CHECK_EQ_I(diag_warnings(f.d), 1);
    CHECK_CONTAINS(out, "warning[BE0318]");
    CHECK_CONTAINS(out, "unreachable code");
    fx_free(&f);
}

static void test_module_cycle(void) {
    CASE("sema: circular module imports are BE0309");
    Fx f = fx_new();
    add_src(&f, "module a\nuse b.thing\nfn f() {\n    let q = 1\n}\n");
    uint32_t file = srcmap_add(f.sm, str_from("b.be"),
                               str_from("module b\nuse a.f\nfn thing() {\n    let q = 1\n}\n"));
    TokenVec toks = lex_file(f.a, f.sm, f.d, f.in, file);
    prog_add_module(f.p, parse_file(f.a, f.d, f.in, toks, file));

    resolve_program(f.d, f.p);
    Str out = diag_render_str(f.a, f.d);
    CHECK_CONTAINS(out, "error[BE0309]");
    CHECK_CONTAINS(out, "import cycle");
    fx_free(&f);
}

void run_sema_tests(void) {
    test_positive();
    test_diagnostics();
    test_const_eval();
    test_containers();
    test_warnings();
    test_module_cycle();
}
