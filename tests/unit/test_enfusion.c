/* Tests for the EnforceScript backend: lowering, conventions, and the lint. */
#include <string.h>
#include "../../src/back/enforce_backend.h"
#include "../../src/parse/parser.h"
#include "../../src/sema/check.h"
#include "../../src/sema/ownership.h"
#include "test.h"
#include "../../src/back/enforce_int.h"
#include <stdlib.h>
#include <string.h>

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

    EnfusionOpts o = {.prefix=str_from("SPK"), .out_dir=str_from(".")};

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
    Str rendered = enfusion_render_all(f.a, f.sm, f.d, f.p, o);
    /* Local source offsets identify bindings but are not the behavior under
     * test in these readable lowering assertions. Keep the encoded name and
     * remove only the final numeric location suffix. */
    SB normalized; sb_init(&normalized, f.a);
    for (uint32_t i = 0; i < rendered.len;) {
        if (i + 5 <= rendered.len && memcmp(rendered.ptr + i, "be_l_", 5) == 0) {
            uint32_t end = i + 5, last = end;
            while (end < rendered.len) {
                char ch = rendered.ptr[end];
                if (!((ch >= 'a' && ch <= 'z') || (ch >= 'A' && ch <= 'Z') ||
                      (ch >= '0' && ch <= '9') || ch == '_')) break;
                if (ch == '_') last = end;
                end++;
            }
            bool numeric = last + 1 < end;
            for (uint32_t k = last + 1; k < end; k++) numeric = numeric && rendered.ptr[k] >= '0' && rendered.ptr[k] <= '9';
            sb_str(&normalized, str_new(rendered.ptr + i, (numeric ? last : end) - i));
            i = end;
        } else sb_char(&normalized, rendered.ptr[i++]);
    }
    return sb_finish(&normalized);
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

    CHECK_CONTAINS(out, "class SPK_be_i_flight_2epid_2ePid");
    CHECK_CONTAINS(out, "\tfloat be_f_kp;");
    CHECK_CONTAINS(out, "\tvoid SPK_be_i_flight_2epid_2ePid()");
    CHECK_CONTAINS(out, "\t\tbe_f_ki = 0.0;");
    CHECK_CONTAINS(out, "\tSPK_be_i_flight_2epid_2ePid BerylCopy()");

    CASE("enfusion: receiver is implicit and fields cannot be shadowed by locals");
    CHECK_CONTAINS(out, "\tfloat be_m_step(float be_l_sp, float be_l_dt)");
    CHECK_CONTAINS(out, "\t\tthis.be_f_integral += (be_l_sp * be_l_dt);");
    CHECK_CONTAINS(out, "return ((this.be_f_kp * be_l_sp) + (this.be_f_ki * this.be_f_integral));");

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

static void test_receiver_mode_admission(void) {
    uint32_t errors = 0;
    CASE("enfusion: unused sink self declarations fail before rendering");
    Str out = enf("module t\nstruct R{x:i32}\n"
        "fn R.take(sink self)->i32{return self.x}\n", &errors);
    CHECK(errors > 0);
    CHECK_CONTAINS(out, "BE0701");
    CHECK_CONTAINS(out, "sink self");
    CHECK_MISSING(out, "class SPK_");

    CASE("enfusion: set self cannot initialize an implicit class receiver");
    out = enf("module t\nstruct R{x:i32}\n"
        "fn R.fill(set self){self=R{x:7}}\n"
        "fn f()->i32{var r:R\nr.fill()\nreturn r.x}\n", &errors);
    CHECK(errors > 0);
    CHECK_CONTAINS(out, "BE0701");
    CHECK_CONTAINS(out, "set self");
    CHECK_CONTAINS(out, "ordinary function");
    CHECK_MISSING(out, "class SPK_");

    CASE("enfusion: inout self cannot replace the whole implicit instance");
    out = enf("module t\nstruct R{x:i32}\n"
        "fn R.reset(inout self){self=R{x:7}}\n", &errors);
    CHECK_EQ_I(errors, 1);
    CHECK_CONTAINS(out, "BE0701");
    CHECK_CONTAINS(out, "whole `self` replacement");
    CHECK_MISSING(out, "class SPK_");

    CASE("enfusion: nested whole-self replacement is also rejected");
    out = enf("module t\nstruct R{x:i32}\n"
        "fn R.reset(inout self,flag:bool){if flag{self=R{x:7}}}\n", &errors);
    CHECK_EQ_I(errors, 1);
    CHECK_CONTAINS(out, "BE0701");
    CHECK_CONTAINS(out, "whole `self` replacement");

    CASE("enfusion: an explicit set helper cannot replace implicit whole self");
    out = enf("module t\nstruct R{x:i32}\n"
        "fn fill(set r:R){r=R{x:7}}\n"
        "fn R.reset(inout self){fill(set self)}\n", &errors);
    CHECK_EQ_I(errors, 1);
    CHECK_CONTAINS(out, "BE0701");
    CHECK_CONTAINS(out, "whole `self` cannot be passed `set`");
    CHECK_MISSING(out, "class SPK_");

    CASE("enfusion: an explicit inout helper cannot replace implicit whole self");
    out = enf("module t\nstruct R{x:i32}\n"
        "fn fill(inout r:R){r=R{x:7}}\n"
        "fn R.reset(inout self){fill(inout self)}\n", &errors);
    CHECK_EQ_I(errors, 1);
    CHECK_CONTAINS(out, "BE0701");
    CHECK_CONTAINS(out, "whole `self` cannot be passed `inout`");

    CASE("enfusion: explicit mutable helpers retain projected-field admission");
    out = enf("module t\nstruct R{x:i32}\n"
        "fn fill(set x:i32){x=7}\nfn bump(inout x:i32){x+=1}\n"
        "fn R.reset(inout self){fill(set self.x)\nbump(inout self.x)}\n", &errors);
    CHECK_EQ_I(errors, 0);
    CHECK_CONTAINS(out, "be_m_fill(this.be_f_x)");
    CHECK_CONTAINS(out, "be_m_bump(this.be_f_x)");

    CASE("enfusion: read-only and inout field methods retain their admission");
    out = enf("module t\nstruct R{x:i32}\n"
        "fn R.read(let self)->i32{return self.x}\n"
        "fn R.reset(inout self){self.x=7}\n", &errors);
    CHECK_EQ_I(errors, 0);
    CHECK_CONTAINS(out, "this.be_f_x = 7;");
    CHECK_CONTAINS(out, "return this.be_f_x;");
    CHECK_MISSING(out, "this =");

    CASE("enfusion: ordinary explicit set and sink functions retain admission");
    out = enf("module t\nstruct R{x:i32}\n"
        "fn fill(set r:R){r=R{x:7}}\n"
        "fn take(sink r:R)->i32{return r.x}\n"
        "fn f()->i32{var r:R\nfill(set r)\nreturn take(sink r)}\n", &errors);
    CHECK_EQ_I(errors, 0);
    CHECK_CONTAINS(out, "be_m_fill(out SPK_be_i_t_2eR be_l_r)");
    CHECK_CONTAINS(out, "be_m_take(SPK_be_i_t_2eR be_l_r)");
    CHECK_MISSING(out, "this =");
}

static void test_type_mapping(void) {
    CASE("enfusion: legacy map of logical records requires recursive copy support");
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
    CHECK_EQ_I(errs, 1);
    CHECK_CONTAINS(out, "BE0701");
    CHECK_CONTAINS(out, "storage admission");
    CHECK_MISSING(out, "class SPK_");

    CASE("enfusion: admitted scalar containers and vectors map to engine-native types");
    out=enf("module t\nstruct Store {items:List<i32>\npos:Vec3\nflag:bool\nlabel:str}\n",&errs);
    CHECK_EQ_I(errs, 0);

    CHECK_CONTAINS(out, "ref array<int> be_f_items;");
    CHECK_CONTAINS(out, "vector be_f_pos;");
    CHECK_CONTAINS(out, "bool be_f_flag;");
    CHECK_CONTAINS(out, "string be_f_label;");

    CASE("enfusion: containers are constructed, since a null ref is not usable");
    CHECK_CONTAINS(out, "be_f_items = new array<int>();");
}

static void test_range_bound_capture(void) {
    CASE("enfusion: compound assignment reads old value before a mutating RHS");
    uint32_t compound_errors=0;
    Str compound=enf("module t\nfn next(inout x:i32)->i32{x+=1\nreturn x}\n"
        "fn f()->i32{var x=4\nx+=next(inout x)\nreturn x}\n",&compound_errors);
    CHECK_EQ_I(compound_errors,0);
    CHECK_CONTAINS(compound,"int _t0 = be_l_x;");
    CHECK_CONTAINS(compound,"be_l_x = _t0 + SPK_be_h_t.be_m_next(be_l_x);");
    CHECK_MISSING(compound,"be_l_x += SPK_be_h_t.be_m_next(be_l_x);");
    CASE("enfusion: range bounds are captured before the loop");
    uint32_t errors=0;
    Str out=enf("module t\nfn upper(inout start:i32)->i32{start=100\nreturn 3}\n"
        "fn f(){var start=0\nfor i in start..upper(inout start){start=i}\n"
        "var xs:List<i32>\nxs.push(1)\nfor j in 0..xs.len(){xs.push(j)}}\n",&errors);
    CHECK_EQ_I(errors,0);
    CHECK_CONTAINS(out,"= be_l_start;");
    CHECK_MISSING(out,"= be_l_start; be_l_i <");
    unsigned loops=0;
    const char *at=out.ptr,*end=out.ptr+out.len;
    while(at<end) {
        const char *next=memchr(at,'\n',(size_t)(end-at));
        if(!next)next=end;
        Str line=str_new(at,(uint32_t)(next-at));
        if(line.len && memchr(at,';',line.len)) {
            bool is_for=false;
            for(uint32_t k=0;k+5<=line.len;k++) if(!memcmp(at+k,"for (",5)){is_for=true;break;}
            if(is_for) {
                loops++;
                CHECK_MISSING(line,"be_l_start");
                CHECK_MISSING(line,".Count()");
                CHECK_MISSING(line,"upper(");
            }
        }
        at=next<end?next+1:end;
    }
    CHECK_EQ_I(loops,2);
}

static void test_reference_array_copy_admission(void) {
    const char *fixtures[] = {
        "module t\nstruct Element { value: i32 }\nstruct Store { values: List<Element> }\n",
        "module t\nstruct Element { value: i32 }\nstruct Store { values: [Element; 2] }\n",
        "module t\nstruct Store { values: List<List<i32>> }\n",
        "module t\nstruct Store { values: [[i32; 2]; 2] }\n"
    };
    for (size_t i = 0; i < sizeof fixtures / sizeof fixtures[0]; i++) {
        CASE("enfusion: ref-array struct copy shape is rejected before invalid engine emission");
        uint32_t errors = 0; Str result = enf(fixtures[i], &errors);
        CHECK_EQ_I(errors, 1);
        CHECK_CONTAINS(result, "BE0701");
        CHECK_CONTAINS(result, "storage admission");
        CHECK_MISSING(result, "class SPK_");
    }
    CASE("enfusion: primitive array fields retain existing copy admission");
    uint32_t errors = 0;
    Str result = enf("module t\nstruct Store { fixed: [i32; 2]\ndynamic: List<f32> }\n", &errors);
    CHECK_EQ_I(errors, 0);
    CHECK_CONTAINS(result, "c.be_f_fixed.Copy(be_f_fixed);");
    CHECK_CONTAINS(result, "c.be_f_dynamic.Copy(be_f_dynamic);");
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

    CHECK_CONTAINS(out, "static bool be_m_parse(string be_l_s, out int result)");
    CHECK_CONTAINS(out, "return false;");
    CHECK_CONTAINS(out, "result = 1;");
    CHECK_CONTAINS(out, "return true;");

    CASE("enfusion: free functions live on a per-module holder class");
    CHECK_CONTAINS(out, "class SPK_be_h_t");
}

static void test_option(void) {
    CASE("enfusion: legacy optional record field rejects shallow wrapper copying");
    uint32_t errs = 0;
    Str      out  = enf("module t\n"
                        "struct Slot {\n"
                        "    held: i32?\n"
                        "}\n",
                        &errs);
    CHECK_EQ_I(errs, 1);
    CHECK_CONTAINS(out, "BE0701");
    CHECK_CONTAINS(out, "storage admission");
    CHECK_MISSING(out, "class SPK_");
    CASE("enfusion: local optional representation remains explicit and bounded");
    out=enf("module t\nfn f(){var held:i32?}\n",&errs);
    CHECK_EQ_I(errs, 0);
    CHECK_CONTAINS(out, "class SPK_be_o_i32_3f");
    CHECK_CONTAINS(out, "bool has;");
    CHECK_CONTAINS(out, "int val;");
    CHECK_CONTAINS(out, "SPK_be_o_i32_3f be_l_held;");
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
    CHECK_CONTAINS(out, "enum SPK_be_i_t_2eMode");
    CHECK_CONTAINS(out, "be_v_Armed = 3");
    CHECK_CONTAINS(out, "static void be_m_bump(out int be_l_n, int be_l_by)");
    CHECK_CONTAINS(out, "be_l_n += be_l_by;");
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
    CHECK_CONTAINS(out, "SPK_be_i_t_2eP be_l_copy = be_l_src.BerylCopy();");
    CHECK_CONTAINS(out, "SPK_be_i_t_2eP _t0 = new SPK_be_i_t_2eP();");
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
    CHECK_CONTAINS(out, "int be_l_out = be_l_v;");
    CHECK_CONTAINS(out, "be_l_out = (be_l_out * be_l_by);");
    CHECK_CONTAINS(out, "return be_l_out;");
    CHECK_CONTAINS(out, "int be_f_ref;");
    CHECK_CONTAINS(out, "int be_f_class;");

    CASE("enfusion: the copy helper avoids the engine base class's Clone");
    out = enf("module t\n"
              "struct P {\n"
              "    x: i32\n"
              "}\n",
              &errs);
    CHECK_EQ_I(errs, 0);
    /* `Class` already declares Clone, so redeclaring it is a hard error. */
    CHECK_CONTAINS(out, "SPK_be_i_t_2eP BerylCopy()");
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

    CASE("enfusion: Vec2 and Vec4 are refused, naming Vec3");
    out = enf("module t\n"
              "fn f(let v: Vec2) -> f32 {\n"
              "    return v.x\n"
              "}\n",
              &errs);
    CHECK(errs >= 1);
    CHECK_CONTAINS(out, "error[BE0701]");
    CHECK_CONTAINS(out, "exactly three floats");
    CHECK_CONTAINS(out, "use `Vec3`");

    CASE("enfusion: Vec3 is accepted, with the whole method surface");
    out = enf("module t\n"
              "fn f(let a: Vec3, let b: Vec3, let s: f32) -> Vec3 {\n"
              "    let m = a.length() + a.length_sq() + a.dot(b) + a.distance(b)\n"
              "    return a.normalized() + a.cross(b) + a / b + a * s + s * a "
              "+ Vec3(m, 0.0, 0.0)\n"
              "}\n",
              &errs);
    CHECK_EQ_I(errs, 0);
    /* Spellings confirmed against EnforceScript that compiles in Workbench. */
    CHECK_CONTAINS(out, "vector.Dot(");
    CHECK_CONTAINS(out, "vector.Distance(");
    CHECK_CONTAINS(out, ".Length()");
    CHECK_CONTAINS(out, ".LengthSq()");
    CHECK_CONTAINS(out, ".Normalized()");
    CHECK_CONTAINS(out, "Vector(");
    /* The engine has no `/` on two vectors, so it must be written out. */
    CHECK_MISSING(out, "(a / b)");

    CASE("enfusion: omitted defaults are filled at the call site, not the signature");
    out = enf("module t\n"
              "struct P {\n"
              "    x: i32\n"
              "}\n"
              "fn take(let p: P = P{ x: 7 }, let tag: i32 = 0) -> i32 {\n"
              "    return p.x + tag\n"
              "}\n"
              "fn a() -> i32 {\n"
              "    return take()\n"
              "}\n"
              "fn b() -> i32 {\n"
              "    return take()\n"
              "}\n",
              &errs);
    CHECK_EQ_I(errs, 0);
    /* A default needing statements must not put them in the class body: they
     * landed outside any method, and Workbench answered "Unexpected scope". */
    CHECK_MISSING(out, "static int be_m_take(SPK_be_i_t_2eP be_l_p = ");
    /* Each call site builds its own, so neither borrows the other's temporary. */
    CHECK_CONTAINS(out, "SPK_be_i_t_2eP _t0 = new SPK_be_i_t_2eP();");
    CHECK_CONTAINS(out, "be_m_take(_t0, 0)");
    /* A literal default still reads naturally in the signature. */
    CHECK_CONTAINS(out, "int be_l_tag = 0");

    CASE("enfusion: an omitted default does not displace the error-union out slot");
    out = enf("module t\n"
              "fn parse(let s: str, let radix: i32 = 10) -> !i32 {\n"
              "    return radix\n"
              "}\n"
              "fn m() -> !i32 {\n"
              "    return try parse(\"x\")\n"
              "}\n",
              &errs);
    CHECK_EQ_I(errs, 0);
    CHECK_CONTAINS(out, "be_m_parse(\"x\", 10, _t0)");

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
    CASE("enfusion: effectful field defaults are rejected by existing constant admission");
    uint32_t aggregate_errors = 0;
    Str aggregate_result = enf("module t\nfn mark()->i32{println(7)\nreturn 7}\n"
        "struct R {value:i32=mark()}\nfn exercise(){let r=R{value:1}\nlet copied=r}\n", &aggregate_errors);
    CHECK(aggregate_errors > 0);
    CHECK_CONTAINS(aggregate_result, "BE0501");
    CHECK_CONTAINS(aggregate_result, "not a constant expression");
    CHECK_MISSING(aggregate_result, "class SPK_");
    CASE("enfusion: literal, named constant and constant-expression defaults remain admitted");
    aggregate_result = enf("module t\nconst K:i32=7\n"
        "struct R {a:i32=K\nb:i32=K+1\nc:i32=-1}\n"
        "fn exercise(){let r=R{}\nlet copied=r}\n", &aggregate_errors);
    CHECK_EQ_I(aggregate_errors, 0);
    CHECK_CONTAINS(aggregate_result, "BerylCopy");
    CASE("enfusion: integer selection uses integer bindings without changing float selection");
    uint32_t numeric_errors = 0;
    Str numeric = enf("module t\n"
        "fn imin(a: i32, b: i32) -> i32 { return min(a,b) }\n"
        "fn imax(a: i32, b: i32) -> i32 { return max(a,b) }\n"
        "fn iclamp(a: i32, b: i32, c: i32) -> i32 { return clamp(a,b,c) }\n"
        "fn fmin(a: f32, b: f32) -> f32 { return min(a,b) }\n"
        "fn fmax(a: f32, b: f32) -> f32 { return max(a,b) }\n"
        "fn fclamp(a: f32, b: f32, c: f32) -> f32 { return clamp(a,b,c) }\n", &numeric_errors);
    CHECK_EQ_I(numeric_errors, 0);
    CHECK_CONTAINS(numeric, "Math.MinInt(be_l_a, be_l_b)");
    CHECK_CONTAINS(numeric, "Math.MaxInt(be_l_a, be_l_b)");
    CHECK_CONTAINS(numeric, "Math.ClampInt(be_l_a, be_l_b, be_l_c)");
    CHECK_CONTAINS(numeric, "Math.Min(be_l_a, be_l_b)");
    CHECK_CONTAINS(numeric, "Math.Max(be_l_a, be_l_b)");
    CHECK_CONTAINS(numeric, "Math.Clamp(be_l_a, be_l_b, be_l_c)");

    CASE("enfusion: saturation tests representable thresholds before arithmetic");
    numeric = enf("module t\n"
        "fn add(a: i32, b: i32) -> i32 { return saturating_add(a,b) }\n"
        "fn sub(a: i32, b: i32) -> i32 { return saturating_sub(a,b) }\n", &numeric_errors);
    CHECK_EQ_I(numeric_errors, 0);
    CHECK_MISSING(numeric, "Math.Clamp");
    CHECK_CONTAINS(numeric, "int _t0 = be_l_a;");
    CHECK_CONTAINS(numeric, "int _t1 = be_l_b;");
    CHECK_CONTAINS(numeric, "if (_t0 > 2147483647 - _t1)");
    CHECK_CONTAINS(numeric, "if (_t0 < -2147483648 - _t1)");
    CHECK_CONTAINS(numeric, "if (_t0 < -2147483648 + _t1)");
    CHECK_CONTAINS(numeric, "if (_t0 > 2147483647 + _t1)");

    CASE("enfusion: selection captures a read before a later mutating argument");
    numeric = enf("module t\nstruct C { value: i32 = 0 }\n"
        "fn C.next(inout self) -> i32 { self.value += 1\nreturn self.value }\n"
        "fn capture() -> i32 { var c = C{}\nreturn min(c.value,c.next()) }\n", &numeric_errors);
    CHECK_EQ_I(numeric_errors, 0);
    CHECK_CONTAINS(numeric, "int _t1 = be_l_c.be_f_value;");
    CHECK_CONTAINS(numeric, "int _t2 = be_l_c.be_m_next();");
    CHECK_CONTAINS(numeric, "return Math.MinInt(_t1, _t2);");

    CASE("enfusion: same-statement defaults have separate temporaries");
    uint32_t errs = 0;
    Str out = enf("module t\nstruct P { x: i32 }\n"
        "fn pick(let p: P = P{ x: 7 }) -> i32 { return p.x }\n"
        "fn exercise() -> i32 { return pick() + pick() }\n", &errs);
    CHECK_EQ_I(errs, 0);
    CHECK_CONTAINS(out, "SPK_be_i_t_2eP _t0 = new SPK_be_i_t_2eP();");
    CHECK_CONTAINS(out, "SPK_be_i_t_2eP _t2 = new SPK_be_i_t_2eP();");
    CHECK_CONTAINS(out, "be_m_pick(_t0)");
    CHECK_CONTAINS(out, "be_m_pick(_t2)");

    CASE("enfusion: collisions between locals and generated names are renamed");
    out = enf("module t\nfn exercise() { let int = 1\nlet int_ = 2\n"
        "let _t0 = 3\nprintln(int + int_ + _t0) }\n", &errs);
    CHECK_EQ_I(errs, 0);
    CHECK_CONTAINS(out, "be_l_int_5f");
    CHECK_MISSING(out, "int int_ =");
    CHECK_MISSING(out, "int _t0 =");

    CASE("enfusion: indexed compound assignment uses one index and an explicit store");
    out = enf("module t\nfn idx() -> i32 { return 0 }\n"
        "fn exercise() { var a = [1]\na[idx()] += 1 }\n", &errs);
    CHECK_EQ_I(errs, 0);
    CHECK_MISSING(out, "] +=");
    CHECK_CONTAINS(out, "= SPK_be_h_t.be_m_idx();");

    CASE("enfusion: catch void needs no payload storage");
    out = enf("module t\nfn fail() -> !void { return error.Bad }\n"
        "fn exercise() { fail() catch |e| { println(e) } }\n", &errs);
    CHECK_EQ_I(errs, 0);
    CHECK_CONTAINS(out, "int be_l_e = 1;");
    CHECK_MISSING(out, "void _t");

    CASE("enfusion: uninitialized locals still receive target lint");
    out = enf("module t\nfn exercise() { var unsupported: f64 }\n", &errs);
    CHECK(errs > 0);
    CHECK_CONTAINS(out, "BE0701");
    CASE("enfusion: finite binary32 literal spellings retain exact bits");
    Arena *fa=arena_new(0); SourceMap *sm=srcmap_new(fa); DiagBag *fd=diag_new(fa,sm);
    E emitter={.a=fa,.d=fd};
    uint32_t state=0x12345678;
    for (uint32_t i=0;i<512;i++) {
        state=state*1664525u+1013904223u;
        uint32_t bits=i==0?0:i==1?0x80000000u:i==2?1:i==3?0x7f7fffffu:state;
        if ((bits&0x7f800000u)==0x7f800000u) continue;
        float value; memcpy(&value,&bits,sizeof value);
        Str text=ef_f32_literal(&emitter,(double)value,SPAN_NONE);
        float parsed=strtof(str_cstr(fa,text),NULL); uint32_t actual;
        memcpy(&actual,&parsed,sizeof actual); CHECK_EQ_I(actual,bits);
    }
    CHECK_EQ_I(diag_errors(fd),0); arena_free(fa);
    test_struct_and_method();
    test_receiver_mode_admission();
    test_type_mapping();
    test_reference_array_copy_admission();
    test_range_bound_capture();
    test_error_union();
    test_option();
    test_enum_and_inout();
    test_value_semantics();
    test_reserved_words();
    test_lint();
}
