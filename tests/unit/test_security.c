/* Tests for the taint engine and its policies. */
#include "../../src/parse/parser.h"
#include "../../src/sema/check.h"
#include "../../src/sema/ownership.h"
#include "../../src/sema/taint.h"
#include "test.h"

/* Runs the whole front end including taint. Frees the previous arena, so the
 * result is valid until the next call. */
static Str sec(const char *src, bool forbid_unsafe, uint32_t *errors) {
    static Arena *keep = NULL;
    if (keep) arena_free(keep);

    Arena     *a  = arena_new(0);
    keep          = a;
    SourceMap *sm = srcmap_new(a);
    DiagBag   *d  = diag_new(a, sm);
    Interner  *in = intern_new(a);
    Program   *p  = prog_new(a);

    uint32_t file = srcmap_add(sm, str_from("t.be"), str_from(src));
    TokenVec toks = lex_file(a, sm, d, in, file);
    prog_add_module(p, parse_file(a, d, in, toks, file));

    resolve_program(d, p);
    check_program(d, p);
    ownership_check(d, p);

    SecurityOpts o = {forbid_unsafe};
    taint_check(d, p, o);

    if (errors) *errors = diag_errors(d);
    return diag_render_str(a, d);
}

static void ok_src(const char *what, const char *src) {
    CASE(what);
    uint32_t errs = 0;
    Str      out  = sec(src, false, &errs);
    if (errs) printf("%.*s\n", (int)out.len, out.ptr);
    CHECK_EQ_I(errs, 0);
}

static void bad_src(const char *what, const char *src, const char *code,
                    const char *text) {
    CASE(what);
    uint32_t errs = 0;
    Str      out  = sec(src, false, &errs);
    CHECK(errs >= 1);
    CHECK_CONTAINS(out, code);
    if (text) CHECK_CONTAINS(out, text);
}

static void test_untrusted(void) {
    bad_src("security: an untrusted value reaching an index is BE0601",
            "module t\n"
            "struct S {\n"
            "    slots: [i32; 8]\n"
            "}\n"
            "@untrusted\n"
            "fn S.on_rpc(inout self, let i: i32) {\n"
            "    self.slots[i] = 1\n"
            "}\n",
            "BE0601", "used as an index without being bounded");

    CASE("security: BE0601 explains the threat and names the fix");
    uint32_t errs = 0;
    Str      out  = sec("module t\n"
                        "struct S {\n"
                        "    slots: [i32; 8]\n"
                        "}\n"
                        "@untrusted\n"
                        "fn S.on_rpc(inout self, let i: i32) {\n"
                        "    self.slots[i] = 1\n"
                        "}\n",
                        false, &errs);
    CHECK_CONTAINS(out, "a client controls this value");
    CHECK_CONTAINS(out, "clamp(i, 0, n - 1)");

    ok_src("security: clamp bounds the value, so the index is trustworthy",
           "module t\n"
           "struct S {\n"
           "    slots: [i32; 8]\n"
           "}\n"
           "@untrusted\n"
           "fn S.on_rpc(inout self, let i: i32) {\n"
           "    self.slots[clamp(i, 0, 7)] = 1\n"
           "}\n");

    ok_src("security: a @validator launders the taint too",
           "module t\n"
           "struct S {\n"
           "    slots: [i32; 8]\n"
           "}\n"
           "@validator\n"
           "fn bound(let raw: i32) -> i32 {\n"
           "    return clamp(raw, 0, 7)\n"
           "}\n"
           "@untrusted\n"
           "fn S.on_rpc(inout self, let i: i32) {\n"
           "    let safe = bound(i)\n"
           "    self.slots[safe] = 1\n"
           "}\n");

    bad_src("security: taint survives arithmetic, so `i + 1` is still untrusted",
            "module t\n"
            "struct S {\n"
            "    slots: [i32; 8]\n"
            "}\n"
            "@untrusted\n"
            "fn S.on_rpc(inout self, let i: i32) {\n"
            "    let j = i + 1\n"
            "    self.slots[j] = 1\n"
            "}\n",
            "BE0601", NULL);
}

static void test_secret(void) {
    bad_src("security: branching on a secret is BE0602",
            "module t\n"
            "@secret\n"
            "fn compare(let key: i32) -> i32 {\n"
            "    if key > 10 {\n"
            "        return 1\n"
            "    }\n"
            "    return 0\n"
            "}\n",
            "BE0602", "observable through timing");

    bad_src("security: indexing by a secret is BE0603",
            "module t\n"
            "struct Tbl {\n"
            "    sbox: [i32; 16]\n"
            "}\n"
            "@secret\n"
            "fn Tbl.lookup(let self, let k: i32) -> i32 {\n"
            "    return self.sbox[k]\n"
            "}\n",
            "BE0603", "observable through the cache");

    CASE("security: clamp does not launder a secret, only an untrusted value");
    uint32_t errs = 0;
    Str      out  = sec("module t\n"
                        "struct Tbl {\n"
                        "    sbox: [i32; 16]\n"
                        "}\n"
                        "@secret\n"
                        "fn Tbl.lookup(let self, let k: i32) -> i32 {\n"
                        "    return self.sbox[clamp(k, 0, 15)]\n"
                        "}\n",
                        false, &errs);
    CHECK(errs >= 1);
    CHECK_CONTAINS(out, "BE0603");
}

static void test_constant_time(void) {
    bad_src("security: a constant-time function calling an ordinary one is BE0607",
            "module t\n"
            "fn helper(let a: i32) -> i32 {\n"
            "    return a\n"
            "}\n"
            "@constant_time\n"
            "fn mix(let a: i32) -> i32 {\n"
            "    return helper(a)\n"
            "}\n",
            "BE0607", "has to hold through every callee");

    ok_src("security: calling another constant-time function is fine",
           "module t\n"
           "@constant_time\n"
           "fn helper(let a: i32) -> i32 {\n"
           "    return a\n"
           "}\n"
           "@constant_time\n"
           "fn mix(let a: i32) -> i32 {\n"
           "    return helper(a)\n"
           "}\n");
}

static void test_server_only(void) {
    bad_src("security: reaching a server-only function from client context is BE0705",
            "module t\n"
            "@server_only\n"
            "fn commit(let v: i32) {\n"
            "    let q = v\n"
            "}\n"
            "fn from_client() {\n"
            "    commit(1)\n"
            "}\n",
            "BE0705", "called from client context");

    ok_src("security: a server-only caller may reach it",
           "module t\n"
           "@server_only\n"
           "fn commit(let v: i32) {\n"
           "    let q = v\n"
           "}\n"
           "@server_only\n"
           "fn handler() {\n"
           "    commit(1)\n"
           "}\n");
}

static void test_forbid_unsafe(void) {
    CASE("security: @unsafe under forbid_unsafe is BE0605");
    uint32_t errs = 0;
    Str      out  = sec("module t\n"
                        "fn f() {\n"
                        "    @unsafe(raw_ptr) {\n"
                        "        let a = 1\n"
                        "    }\n"
                        "}\n",
                        true, &errs);
    CHECK(errs >= 1);
    CHECK_CONTAINS(out, "BE0605");
    CHECK_CONTAINS(out, "forbid_unsafe");

    CASE("security: the same code is permitted when forbid_unsafe is off");
    out = sec("module t\n"
              "fn f() {\n"
              "    @unsafe(raw_ptr) {\n"
              "        let a = 1\n"
              "    }\n"
              "}\n",
              false, &errs);
    if (errs) printf("%.*s\n", (int)out.len, out.ptr);
    CHECK_EQ_I(errs, 0);
}

void run_security_tests(void) {
    test_untrusted();
    test_secret();
    test_constant_time();
    test_server_only();
    test_forbid_unsafe();
}
