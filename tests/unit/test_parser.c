/* Tests for the parser: precedence, ambiguity, items, recovery, round-trip. */
#include "../../src/parse/parser.h"
#include "../../src/parse/print.h"
#include "test.h"
#include <string.h>

typedef struct {
    Arena     *a;
    SourceMap *sm;
    DiagBag   *d;
    Interner  *in;
} Fx;

static Fx fx_new(void) {
    Fx f = {0};
    f.a  = arena_new(0);
    f.sm = srcmap_new(f.a);
    f.d  = diag_new(f.a, f.sm);
    f.in = intern_new(f.a);
    return f;
}
static void fx_free(Fx *f) { arena_free(f->a); }

static Module *parse_src(Fx *f, const char *src) {
    uint32_t file = srcmap_add(f->sm, str_from("t.be"), str_from(src));
    TokenVec toks = lex_file(f->a, f->sm, f->d, f->in, file);
    return parse_file(f->a, f->d, f->in, toks, file);
}

static Str dump_src(Fx *f, const char *src) {
    return ast_print(f->a, parse_src(f, src));
}

/* Wraps an expression in a minimal module so it can be parsed. */
static Str dump_expr(Fx *f, const char *expr) {
    SB sb;
    sb_init(&sb, f->a);
    sb_cstr(&sb, "module t\nfn m() {\n    let v = ");
    sb_cstr(&sb, expr);
    sb_cstr(&sb, "\n}\n");
    return dump_src(f, str_cstr(f->a, sb_finish(&sb)));
}

static void test_precedence(void) {
    Fx f = fx_new();

    CASE("parser: multiplication binds tighter than addition");
    CHECK_CONTAINS(dump_expr(&f, "a + b * c"),
                   "(bin + (path a) (bin * (path b) (path c)))");
    CHECK_CONTAINS(dump_expr(&f, "a * b + c"),
                   "(bin + (bin * (path a) (path b)) (path c))");

    CASE("parser: comparison binds looser than arithmetic");
    CHECK_CONTAINS(dump_expr(&f, "a + b < c * d"),
                   "(bin < (bin + (path a) (path b)) (bin * (path c) (path d)))");

    CASE("parser: && binds tighter than ||");
    CHECK_CONTAINS(dump_expr(&f, "a || b && c"),
                   "(bin || (path a) (bin && (path b) (path c)))");

    CASE("parser: unary binds tighter than binary");
    CHECK_CONTAINS(dump_expr(&f, "!a && b"), "(bin && (unary ! (path a)) (path b))");
    CHECK_CONTAINS(dump_expr(&f, "-a + b"), "(bin + (unary - (path a)) (path b))");

    CASE("parser: `as` binds tighter than arithmetic");
    CHECK_CONTAINS(dump_expr(&f, "a as i64 + 1"),
                   "(bin + (cast (path a) i64) (int 1))");

    CASE("parser: left associativity of same-precedence operators");
    CHECK_CONTAINS(dump_expr(&f, "a - b - c"),
                   "(bin - (bin - (path a) (path b)) (path c))");

    CASE("parser: parentheses override precedence");
    CHECK_CONTAINS(dump_expr(&f, "(a + b) * c"),
                   "(bin * (bin + (path a) (path b)) (path c))");

    CASE("parser: postfix chains");
    CHECK_CONTAINS(dump_expr(&f, "a.b.c"), "(field (field (path a) b) c)");
    CHECK_CONTAINS(dump_expr(&f, "a.b()"), "(call (field (path a) b))");
    CHECK_CONTAINS(dump_expr(&f, "a[i].b"), "(field (index (path a) (path i)) b)");

    CHECK_EQ_I(diag_errors(f.d), 0);
    fx_free(&f);
}

static void test_chained_comparison(void) {
    Fx f = fx_new();

    CASE("parser: chained comparison is BE0208 with both spans");
    parse_src(&f, "module t\nfn m() {\n    let v = a < b < c\n}\n");
    CHECK_EQ_I(diag_errors(f.d), 1);
    Str out = diag_render_str(f.a, f.d);
    CHECK_CONTAINS(out, "error[BE0208]");
    CHECK_CONTAINS(out, "comparison operators cannot be chained");
    CHECK_CONTAINS(out, "first comparison");
    CHECK_CONTAINS(out, "second comparison here");
    CHECK_CONTAINS(out, "= help:");

    fx_free(&f);
}

static void test_struct_literal_ambiguity(void) {
    Fx f = fx_new();

    CASE("parser: struct literal in a normal expression position");
    CHECK_CONTAINS(dump_expr(&f, "Point{ x: 1, y: 2 }"),
                   "(structlit Point (x (int 1)) (y (int 2)))");

    CASE("parser: after `if`, a brace opens a block, not a struct literal");
    Str s = dump_src(&f, "module t\nfn m() {\n    if p {\n        a()\n    }\n}\n");
    CHECK_CONTAINS(s, "(if (path p) (block");
    CHECK_EQ_I(diag_errors(f.d), 0);

    CASE("parser: after `while`, the same rule applies");
    s = dump_src(&f, "module t\nfn m() {\n    while p {\n        a()\n    }\n}\n");
    CHECK_CONTAINS(s, "(while (path p) (block");

    CASE("parser: parentheses re-enable struct literals inside a condition");
    s = dump_src(&f, "module t\nfn m() {\n    if (Point{ x: 1 }).x {\n        a()\n    }\n}\n");
    CHECK_CONTAINS(s, "(structlit Point");

    CHECK_EQ_I(diag_errors(f.d), 0);
    fx_free(&f);
}

static void test_items(void) {
    Fx f = fx_new();

    CASE("parser: method declaration with a self receiver and conventions");
    Str s = dump_src(&f,
                     "module flight.pid\n"
                     "pub fn Pid.step(inout self, sp: f32, dt: f32 = 0.1) -> f32 {\n"
                     "    return sp\n"
                     "}\n");
    CHECK_CONTAINS(s, "(module flight.pid");
    CHECK_CONTAINS(s, "(fn pub Pid.step (params (inout self) (let sp f32) (let dt f32 =(float 0.10000000000000001)))");
    CHECK_CONTAINS(s, "(ret f32)");
    CHECK_EQ_I(diag_errors(f.d), 0);

    CASE("parser: struct with defaults, fields separated by newlines");
    s = dump_src(&f,
                 "module t\n"
                 "pub struct Pid {\n"
                 "    kp: f32\n"
                 "    ki: f32 = 0\n"
                 "    tag: str = \"x\"\n"
                 "}\n");
    CHECK_CONTAINS(s, "(struct pub Pid");
    CHECK_CONTAINS(s, "(kp f32)");
    CHECK_CONTAINS(s, "(ki f32 = (int 0))");
    CHECK_EQ_I(diag_errors(f.d), 0);

    CASE("parser: struct fields separated by commas on one line");
    s = dump_src(&f, "module t\nstruct P { x: f32, y: f32, z: f32 }\n");
    CHECK_CONTAINS(s, "(x f32)");
    CHECK_CONTAINS(s, "(z f32)");
    CHECK_EQ_I(diag_errors(f.d), 0);

    CASE("parser: generics with a trait bound");
    s = dump_src(&f, "module t\nfn max<T: Ord>(let a: T, let b: T) -> T {\n    return a\n}\n");
    CHECK_CONTAINS(s, "(fn max<T:Ord>");
    CHECK_EQ_I(diag_errors(f.d), 0);

    CASE("parser: enum with explicit discriminants");
    s = dump_src(&f, "module t\nenum Mode { Idle, Armed = 3, Active }\n");
    CHECK_CONTAINS(s, "(enum Mode (Idle) (Armed (int 3)) (Active))");

    CASE("parser: const, use, test");
    s = dump_src(&f,
                 "module t\n"
                 "use core.math.clamp\n"
                 "const LIMIT: i32 = 10\n"
                 "test \"it works\" {\n"
                 "    let a = 1\n"
                 "}\n");
    CHECK_CONTAINS(s, "(use core.math.clamp)");
    CHECK_CONTAINS(s, "(const LIMIT i32 (int 10))");
    CHECK_CONTAINS(s, "(test \"it works\"");
    CHECK_EQ_I(diag_errors(f.d), 0);

    CASE("parser: attributes with and without arguments");
    s = dump_src(&f,
                 "module t\n"
                 "@server_only\n"
                 "@unsafe(ffi)\n"
                 "fn go() {\n"
                 "    let a = 1\n"
                 "}\n");
    CHECK_CONTAINS(s, "(@server_only) (@unsafe ffi) (fn go");
    CHECK_EQ_I(diag_errors(f.d), 0);

    CASE("parser: trait with a method signature");
    s = dump_src(&f, "module t\ntrait Ord {\n    fn cmp(let self, let other: T) -> i32\n}\n");
    CHECK_CONTAINS(s, "(trait Ord");
    CHECK_CONTAINS(s, "(fn cmp (params (let self) (let other T))");
    CHECK_EQ_I(diag_errors(f.d), 0);

    fx_free(&f);
}

static void test_types(void) {
    Fx f = fx_new();

    CASE("parser: option, error union, array and generic types");
    Str s = dump_src(&f,
                     "module t\n"
                     "fn a(let x: i32?) -> !i32 {\n"
                     "    return 0\n"
                     "}\n"
                     "fn b(let y: [i32; 8], let z: Map<str, Entity>) {\n"
                     "    let q = 1\n"
                     "}\n");
    CHECK_CONTAINS(s, "(let x i32?)");
    CHECK_CONTAINS(s, "(ret !i32)");
    CHECK_CONTAINS(s, "(let y [i32;(int 8)])");
    CHECK_CONTAINS(s, "(let z Map<str,Entity>)");
    CHECK_EQ_I(diag_errors(f.d), 0);

    CASE("parser: nested generics close correctly through a `>>` token");
    s = dump_src(&f, "module t\nfn a(let x: List<List<i32>>) {\n    let q = 1\n}\n");
    CHECK_CONTAINS(s, "(let x List<List<i32>>)");
    CHECK_EQ_I(diag_errors(f.d), 0);

    fx_free(&f);
}

static void test_error_handling_syntax(void) {
    Fx f = fx_new();

    CASE("parser: try, orelse, catch");
    Str s = dump_src(&f,
                     "module t\n"
                     "fn m() {\n"
                     "    let a = try parse(s)\n"
                     "    let b = parse(s) orelse 0\n"
                     "    let c = parse(s) catch |e| {\n"
                     "        log(e)\n"
                     "    }\n"
                     "    let d = error.OutOfRange\n"
                     "}\n");
    CHECK_CONTAINS(s, "(try (call (path parse) (path s)))");
    CHECK_CONTAINS(s, "(orelse (call (path parse) (path s)) (int 0))");
    CHECK_CONTAINS(s, "(catch (call (path parse) (path s)) |e| (block");
    CHECK_CONTAINS(s, "(error OutOfRange)");
    CHECK_EQ_I(diag_errors(f.d), 0);

    CASE("parser: call-site conventions");
    s = dump_src(&f, "module t\nfn m() {\n    swap(inout a, sink b)\n}\n");
    CHECK_CONTAINS(s, "(call (path swap) inout:(path a) sink:(path b))");
    CHECK_EQ_I(diag_errors(f.d), 0);

    CASE("parser: @unsafe block with a capability");
    s = dump_src(&f, "module t\nfn m() {\n    @unsafe(raw_ptr) {\n        go()\n    }\n}\n");
    CHECK_CONTAINS(s, "(unsafe raw_ptr (block");
    CHECK_EQ_I(diag_errors(f.d), 0);

    fx_free(&f);
}

static void test_statements(void) {
    Fx f = fx_new();

    CASE("parser: statements, loops, assignment forms");
    Str s = dump_src(&f,
                     "module t\n"
                     "fn m() {\n"
                     "    var i = 0\n"
                     "    while i < 10 {\n"
                     "        i += 1\n"
                     "        if i == 5 { continue }\n"
                     "        if i == 8 { break }\n"
                     "    }\n"
                     "    for k in 0..4 {\n"
                     "        sum = sum + k\n"
                     "    }\n"
                     "    defer cleanup()\n"
                     "    return\n"
                     "}\n");
    CHECK_CONTAINS(s, "(var i (int 0))");
    CHECK_CONTAINS(s, "(assign += (path i) (int 1))");
    CHECK_CONTAINS(s, "(continue)");
    CHECK_CONTAINS(s, "(break)");
    CHECK_CONTAINS(s, "(for k (range (int 0) (int 4))");
    CHECK_CONTAINS(s, "(defer (call (path cleanup)))");
    CHECK_CONTAINS(s, "(return)");
    CHECK_EQ_I(diag_errors(f.d), 0);

    CASE("parser: multi-line expression continuation");
    s = dump_src(&f,
                 "module t\n"
                 "fn m() -> f32 {\n"
                 "    return self.kp * err\n"
                 "         + self.ki * integral\n"
                 "}\n");
    CHECK_CONTAINS(s, "(bin + (bin * (field (self) kp) (path err))");
    CHECK_EQ_I(diag_errors(f.d), 0);

    fx_free(&f);
}

static void test_param_diagnostics(void) {
    CASE("parser: duplicate parameter is BE0205 with both spans");
    Fx f = fx_new();
    parse_src(&f, "module t\nfn m(let a: i32, let a: i32) {\n    let q = 1\n}\n");
    Str out = diag_render_str(f.a, f.d);
    CHECK_CONTAINS(out, "error[BE0205]");
    CHECK_CONTAINS(out, "duplicate parameter `a`");
    CHECK_CONTAINS(out, "first declared here");
    fx_free(&f);

    CASE("parser: `self` not first is BE0206");
    Fx g = fx_new();
    parse_src(&g, "module t\nfn T.m(let a: i32, inout self) {\n    let q = 1\n}\n");
    CHECK_CONTAINS(diag_render_str(g.a, g.d), "error[BE0206]");
    fx_free(&g);

    CASE("parser: default on an inout parameter is BE0207");
    Fx h = fx_new();
    parse_src(&h, "module t\nfn m(inout a: i32 = 1) {\n    let q = 1\n}\n");
    Str o = diag_render_str(h.a, h.d);
    CHECK_CONTAINS(o, "error[BE0207]");
    CHECK_CONTAINS(o, "= note:");
    fx_free(&h);

    CASE("parser: missing module declaration is BE0209");
    Fx i = fx_new();
    parse_src(&i, "fn m() {\n    let q = 1\n}\n");
    CHECK_CONTAINS(diag_render_str(i.a, i.d), "error[BE0209]");
    fx_free(&i);
}

static void test_recovery(void) {
    Fx f = fx_new();

    CASE("parser: two independent item errors are both reported");
    parse_src(&f,
              "module t\n"
              "fn a( {\n"
              "    let x = 1\n"
              "}\n"
              "fn b(let y: ) {\n"
              "    let z = 2\n"
              "}\n"
              "fn c() {\n"
              "    let w = 3\n"
              "}\n");
    CHECK(diag_errors(f.d) >= 2);

    CASE("parser: recovery still yields the well-formed items");
    Fx g = fx_new();
    Module *m = parse_src(&g, "module t\nfn a(( {\n}\nfn good() {\n    let x = 1\n}\n");
    bool found_good = false;
    for (uint32_t i = 0; i < m->items.len; i++)
        if (str_eq_c(m->items.data[i]->name, "good")) found_good = true;
    CHECK(found_good);
    fx_free(&g);

    fx_free(&f);
}

static void test_roundtrip(void) {
    Fx f = fx_new();

    CASE("formatter: format then reparse yields an identical AST");
    const char *src = "module flight.pid\n"
                      "\n"
                      "pub struct Pid {\n"
                      "    kp: f32\n"
                      "    ki: f32 = 0\n"
                      "}\n"
                      "\n"
                      "pub fn Pid.step(inout self, sp: f32, dt: f32) -> f32 {\n"
                      "    if dt <= 0 {\n"
                      "        return 0\n"
                      "    }\n"
                      "    let err = sp - self.meas\n"
                      "    self.integral += err * dt\n"
                      "    return self.kp * err + self.ki * self.integral\n"
                      "}\n";

    Module *m1 = parse_src(&f, src);
    CHECK_EQ_I(diag_errors(f.d), 0);
    Str dump1 = ast_print(f.a, m1);
    Str fmt1  = ast_format(f.a, m1);

    Module *m2 = parse_src(&f, str_cstr(f.a, fmt1));
    CHECK_EQ_I(diag_errors(f.d), 0);
    Str dump2 = ast_print(f.a, m2);
    CHECK_EQ_S(dump2, str_cstr(f.a, dump1));

    CASE("formatter: formatting is idempotent");
    Str fmt2 = ast_format(f.a, m2);
    CHECK_EQ_S(fmt2, str_cstr(f.a, fmt1));

    CASE("formatter: precedence-preserving parentheses survive the round trip");
    const char *src2 = "module t\n\nfn m() -> i32 {\n    return (a + b) * c\n}\n";
    Module *p1 = parse_src(&f, src2);
    Str     d1 = ast_print(f.a, p1);
    Module *p2 = parse_src(&f, str_cstr(f.a, ast_format(f.a, p1)));
    CHECK_EQ_S(ast_print(f.a, p2), str_cstr(f.a, d1));
    CHECK_EQ_I(diag_errors(f.d), 0);

    fx_free(&f);
}

void run_parser_tests(void) {
    CASE("formatter: literal kinds, exact payloads and suffixes survive");
    Fx f = fx_new();
    Module *before = parse_src(&f,
        "module t\nconst A = 1.0\nconst B = 1.2345678901234567f64\n"
        "const C = 16777217f32\nconst D = 255u8\nconst E = '\\n'\n"
        "const F = '\\0'\nconst G = '\\\''\nconst H = '\\\\'\nconst I = '\\xFF'\n");
    Str formatted = ast_format(f.a, before);
    Module *after = parse_src(&f, str_cstr(f.a, formatted));
    CHECK_EQ_I(diag_errors(f.d), 0);
    CHECK_EQ_I(before->items.len, after->items.len);
    for (uint32_t i = 0; i < before->items.len && i < after->items.len; i++) {
        Expr *a = before->items.data[i]->konst.value;
        Expr *b = after->items.data[i]->konst.value;
        CHECK_EQ_I(a->kind, b->kind);
        if (a->kind == EX_FLOAT && b->kind == EX_FLOAT) {
            CHECK(memcmp(&a->float_lit.val, &b->float_lit.val, sizeof(double)) == 0);
            CHECK(str_eq(a->float_lit.suffix, b->float_lit.suffix));
        } else if (a->kind == EX_INT && b->kind == EX_INT) {
            CHECK(a->int_lit.val == b->int_lit.val);
            CHECK(str_eq(a->int_lit.suffix, b->int_lit.suffix));
        } else if (a->kind == EX_CHAR && b->kind == EX_CHAR) CHECK_EQ_I(a->char_lit, b->char_lit);
    }
    CHECK(str_eq(formatted, ast_format(f.a, after)));
    fx_free(&f);
    test_precedence();
    test_chained_comparison();
    test_struct_literal_ambiguity();
    test_items();
    test_types();
    test_error_handling_syntax();
    test_statements();
    test_param_diagnostics();
    test_recovery();
    test_roundtrip();
}
