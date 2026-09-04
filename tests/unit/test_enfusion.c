/* Tests for the EnforceScript backend: lowering, conventions, and the lint. */
#include <string.h>
#include "../../src/back/enforce_backend.h"
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

/* Runs the whole front end and renders EnforceScript. Frees the previous
 * arena, so the result is valid until the next call. */
static Str enf(const char *src, uint32_t *errors) {
    static Arena *keep = NULL;
    if (keep) arena_free(keep);

    Fx f = {0};
    f.a  = arena_new(0);
    keep = f.a;
    f.sm = srcmap_new(f.a);
    f.d  = diag_new(f.a, f.sm);
    f.in = intern_new(f.a);
    f.p  = prog_new(f.a);

    uint32_t file = srcmap_add(f.sm, str_from("t.be"), str_from(src));
    TokenVec toks = lex_file(f.a, f.sm, f.d, f.in, file);
    prog_add_module(f.p, parse_file(f.a, f.d, f.in, toks, file));

    resolve_program(f.d, f.p);
    check_program(f.d, f.p);
    ownership_check(f.d, f.p);

    EnfusionOpts o = {str_from("SPK"), str_from(".")};

    if (diag_errors(f.d) > 0) {
        if (errors) *errors = diag_errors(f.d);
        return diag_render_str(f.a, f.d);
    }
    enfusion_lint(f.d, f.p, o);
    if (diag_errors(f.d) > 0) {
        if (errors) *errors = diag_errors(f.d);
        return diag_render_str(f.a, f.d);
    }
    if (errors) *errors = 0;
    return enfusion_render_all(f.a, f.sm, f.d, f.p, o);
}

static void test_struct_and_method(void) {
    CASE("enfusion: a struct becomes a prefixed class with defaults and a copy helper");
    uint32_t errs = 0;
    Str      out  = enf("module flight.pid\n"
                        "pub struct Pid {\n"
                        "    kp: f32\n"
                        "    ki: f32 = 0\n"
                        "    integral: f32 = 0\n"
                        "}\n"
                        "pub fn Pid.step(inout self, sp: f32, dt: f32) -> f32 {\n"
                        "    self.integral += sp * dt\n"
                        "    return self.kp * sp + self.ki * self.integral\n"
                        "}\n",
                        &errs);
    if (errs) printf("%.*s\n", (int)out.len, out.ptr);
    CHECK_EQ_I(errs, 0);

    CHECK_CONTAINS(out, "class SPK_Pid");
    CHECK_CONTAINS(out, "\tfloat kp;");
    CHECK_CONTAINS(out, "\tvoid SPK_Pid()");
    CHECK_CONTAINS(out, "\t\tki = 0;");
    CHECK_CONTAINS(out, "\tSPK_Pid BerylCopy()");

    CASE("enfusion: the receiver is implicit, so self.field is a bare field");
    CHECK_CONTAINS(out, "\tfloat step(float sp, float dt)");
    CHECK_CONTAINS(out, "\t\tintegral += (sp * dt);");
    CHECK_CONTAINS(out, "return ((kp * sp) + (ki * integral));");

    CASE("enfusion: braces are Allman and indentation is tabs, matching Bohemia");
    bool has_space_indent = false;
    for (uint32_t i = 1; i < out.len; i++)
        if (out.ptr[i - 1] == '\n' && out.ptr[i] == ' ') has_space_indent = true;
    CHECK(!has_space_indent);

    CASE("enfusion: no byte-order mark, which Workbench rejects");
    CHECK(out.len >= 3);
    CHECK(!(out.len >= 3 && (unsigned char)out.ptr[0] == 0xEF &&
            (unsigned char)out.ptr[1] == 0xBB && (unsigned char)out.ptr[2] == 0xBF));
}

static void test_type_mapping(void) {
    CASE("enfusion: containers and vectors map to engine-native types");
    uint32_t errs = 0;
    Str      out  = enf("module t\n"
                        "struct Entity {\n"
                        "    id: i32\n"
                        "}\n"
                        "struct Store {\n"
                        "    items: List<i32>\n"
                        "    byName: Map<str, Entity>\n"
                        "    pos: Vec3\n"
                        "    flag: bool\n"
                        "    label: str\n"
                        "}\n",
                        &errs);
    if (errs) printf("%.*s\n", (int)out.len, out.ptr);
    CHECK_EQ_I(errs, 0);

    CHECK_CONTAINS(out, "ref array<int> items;");
    CHECK_CONTAINS(out, "ref map<string, ref SPK_Entity> byName;");
    CHECK_CONTAINS(out, "vector pos;");
    CHECK_CONTAINS(out, "bool flag;");
    CHECK_CONTAINS(out, "string label;");

    CASE("enfusion: containers are constructed, since a null ref is not usable");
    CHECK_CONTAINS(out, "items = new array<int>();");
    CHECK_CONTAINS(out, "byName = new map<string, ref SPK_Entity>();");
}

static void test_error_union(void) {
    CASE("enfusion: `!T` becomes a bool return plus an out parameter");
    uint32_t errs = 0;
    Str      out  = enf("module t\n"
                        "fn parse(let s: str) -> !i32 {\n"
                        "    if s == \"\" {\n"
                        "        return error.Empty\n"
                        "    }\n"
                        "    return 1\n"
                        "}\n",
                        &errs);
    if (errs) printf("%.*s\n", (int)out.len, out.ptr);
    CHECK_EQ_I(errs, 0);

    CHECK_CONTAINS(out, "static bool parse(string s, out int result)");
    CHECK_CONTAINS(out, "return false;");
    CHECK_CONTAINS(out, "result = 1;");
    CHECK_CONTAINS(out, "return true;");

    CASE("enfusion: free functions live on a per-module holder class");
    CHECK_CONTAINS(out, "class SPK_T");
}

static void test_option(void) {
    CASE("enfusion: `T?` generates a wrapper class, never a silent sentinel");
    uint32_t errs = 0;
    Str      out  = enf("module t\n"
                        "struct Slot {\n"
                        "    held: i32?\n"
                        "}\n",
                        &errs);
    if (errs) printf("%.*s\n", (int)out.len, out.ptr);
    CHECK_EQ_I(errs, 0);
    CHECK_CONTAINS(out, "class SPK_Opt_int");
    CHECK_CONTAINS(out, "bool has;");
    CHECK_CONTAINS(out, "int val;");
    CHECK_CONTAINS(out, "ref SPK_Opt_int held;");
}

static void test_enum_and_inout(void) {
    CASE("enfusion: enums map directly, and inout parameters become `out`");
    uint32_t errs = 0;
    Str      out  = enf("module t\n"
                        "enum Mode {\n"
                        "    Idle\n"
                        "    Armed = 3\n"
                        "}\n"
                        "fn bump(inout n: i32, let by: i32) {\n"
                        "    n += by\n"
                        "}\n",
                        &errs);
    if (errs) printf("%.*s\n", (int)out.len, out.ptr);
    CHECK_EQ_I(errs, 0);
    CHECK_CONTAINS(out, "enum SPK_Mode");
    CHECK_CONTAINS(out, "Armed = 3");
    CHECK_CONTAINS(out, "static void bump(out int n, int by)");
    CHECK_CONTAINS(out, "n += by;");
}

static void test_value_semantics(void) {
    CASE("enfusion: copying a struct binding inserts a copy, a literal does not");
    uint32_t errs = 0;
    Str      out  = enf("module t\n"
                        "struct P {\n"
                        "    x: i32\n"
                        "}\n"
                        "fn go(let src: P) -> i32 {\n"
                        "    let copy = src\n"
                        "    let fresh = P{ x: 1 }\n"
                        "    return copy.x + fresh.x\n"
                        "}\n",
                        &errs);
    if (errs) printf("%.*s\n", (int)out.len, out.ptr);
    CHECK_EQ_I(errs, 0);
    /* A place expression copies; a freshly built value does not. */
    CHECK_CONTAINS(out, "SPK_P copy = src.BerylCopy();");
    CHECK_CONTAINS(out, "SPK_P _t0 = new SPK_P();");
}

/* Both of these were found by compiling generated script in the real
 * Workbench, not by inspection. Neither would fail a golden test that only
 * checked the text looked reasonable. */
static void test_reserved_words(void) {
    CASE("enfusion: identifiers colliding with engine keywords are renamed");
    uint32_t errs = 0;
    Str      out  = enf("module t\n"
                        "struct Holder {\n"
                        "    ref: i32 = 0\n"
                        "    class: i32 = 0\n"
                        "}\n"
                        "fn scale(let v: i32, let by: i32) -> i32 {\n"
                        "    var out = v\n"
                        "    out = out * by\n"
                        "    return out\n"
                        "}\n",
                        &errs);
    if (errs) printf("%.*s\n", (int)out.len, out.ptr);
    CHECK_EQ_I(errs, 0);

    /* `out` is how EnforceScript spells an out-parameter, and a collision
     * surfaces only as "Broken expression" with no hint of the cause. */
    CHECK_CONTAINS(out, "int out_ = v;");
    CHECK_CONTAINS(out, "out_ = (out_ * by);");
    CHECK_CONTAINS(out, "return out_;");
    CHECK_CONTAINS(out, "int ref_;");
    CHECK_CONTAINS(out, "int class_;");

    CASE("enfusion: the copy helper avoids the engine base class's Clone");
    out = enf("module t\n"
              "struct P {\n"
              "    x: i32\n"
              "}\n",
              &errs);
    CHECK_EQ_I(errs, 0);
    /* `Class` already declares Clone, so redeclaring it is a hard error. */
    CHECK_CONTAINS(out, "SPK_P BerylCopy()");
    bool declares_clone = false;
    for (uint32_t i = 0; i + 8 <= out.len; i++)
        if (out.ptr[i] == ' ' && memcmp(out.ptr + i + 1, "Clone()", 7) == 0)
            declares_clone = true;
    CHECK(!declares_clone);
}

static void test_lint(void) {
    CASE("enfusion: unsupported integer widths are BE0701 with a substitute");
    uint32_t errs = 0;
    Str      out  = enf("module t\n"
                        "struct W {\n"
                        "    big: i64\n"
                        "}\n",
                        &errs);
    CHECK(errs >= 1);
    CHECK_CONTAINS(out, "error[BE0701]");
    CHECK_CONTAINS(out, "not supported on the enfusion target");
    CHECK_CONTAINS(out, "one integer type, a signed 32-bit `int`");
    CHECK_CONTAINS(out, "use `i32`");

    CASE("enfusion: f64 is refused too, naming f32");
    out = enf("module t\n"
              "fn f(let x: f64) -> f64 {\n"
              "    return x\n"
              "}\n",
              &errs);
    CHECK(errs >= 1);
    CHECK_CONTAINS(out, "error[BE0701]");
    CHECK_CONTAINS(out, "use `f32`");

    CASE("enfusion: @unsafe is forbidden by construction, BE0703");
    out = enf("module t\n"
              "fn f() {\n"
              "    @unsafe(raw_ptr) {\n"
              "        let a = 1\n"
              "    }\n"
              "}\n",
              &errs);
    CHECK(errs >= 1);
    CHECK_CONTAINS(out, "error[BE0703]");
    CHECK_CONTAINS(out, "forbidden on the enfusion target");
    CHECK_CONTAINS(out, "no raw pointers");
}

void run_enfusion_tests(void) {
    test_struct_and_method();
    test_type_mapping();
    test_error_union();
    test_option();
    test_enum_and_inout();
    test_value_semantics();
    test_reserved_words();
    test_lint();
}
