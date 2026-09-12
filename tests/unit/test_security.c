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
    bad_src("security: server-only call in omitted default is checked in caller",
        "module t\n@server_only\nfn secret() -> i32 { return 7 }\n"
        "fn consume(let x: i32 = secret()) -> i32 { return x }\n"
        "fn client() -> i32 { return consume() }\n", "BE0705", NULL);
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

    ok_src("security: clamp proves this fixed-array bound while retaining provenance",
           "module t\n"
           "struct S {\n"
           "    slots: [i32; 8]\n"
           "}\n"
           "@untrusted\n"
           "fn S.on_rpc(inout self, let i: i32) {\n"
           "    self.slots[clamp(i, 0, 7)] = 1\n"
           "}\n");

    ok_src("security: validator body proves bounds independently of its annotation",
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

    CASE("security: clamp never launders secret provenance");
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

static void test_provenance_regressions(void) {
    bad_src("security: min is not a lower-bound validator",
        "module t\n@untrusted\nfn f(i:i32) -> i32 { let a=[1,2,3,4]\nreturn a[min(i,3)] }\n","BE0601",NULL);
    bad_src("security: max is not an upper-bound validator",
        "module t\n@untrusted\nfn f(i:i32) -> i32 { let a=[1,2,3,4]\nreturn a[max(i,0)] }\n","BE0601",NULL);
    bad_src("security: reversed clamp limits do not prove bounds",
        "module t\n@untrusted\nfn f(i:i32) -> i32 { let a=[1,2,3,4]\nreturn a[clamp(i,3,0)] }\n","BE0601",NULL);
    bad_src("security: clamp proof belongs to destination size",
        "module t\n@untrusted\nfn f(i:i32) -> i32 { let a=[1,2]\nreturn a[clamp(i,0,3)] }\n","BE0601",NULL);
    bad_src("security: bare validator cannot erase provenance",
        "module t\n@validator\nfn trust(i:i32)->i32 { return i }\n"
        "@untrusted\nfn f(i:i32)->i32 { let a=[1,2]\nreturn a[trust(i)] }\n","BE0601",NULL);
    ok_src("security: checked helper range does not require validator annotation",
        "module t\nfn bound(i:i32)->i32 { return clamp(i,0,1) }\n"
        "@untrusted\nfn f(i:i32)->i32 { let a=[1,2]\nlet j=bound(i)\nreturn a[j] }\n");
    bad_src("security: helper index receives caller provenance",
        "module t\nfn helper(i:i32)->i32 { let a=[1,2]\nreturn a[i] }\n"
        "@untrusted\nfn f(i:i32)->i32 { return helper(i) }\n","BE0601",NULL);
    bad_src("security: later declared helper gets same provenance",
        "module t\n@untrusted\nfn f(i:i32)->i32 { return helper(i) }\n"
        "fn helper(i:i32)->i32 { let a=[1,2]\nreturn a[i] }\n","BE0601",NULL);
    bad_src("security: field assignment cannot hide untrusted index",
        "module t\nstruct R { bad:i32, good:i32 }\n@untrusted\n"
        "fn f(i:i32)->i32 { var r=R{bad:0,good:0}\nr.bad=i\nlet a=[1,2]\nreturn a[r.bad] }\n","BE0601",NULL);
    ok_src("security: disjoint plain field keeps separate provenance",
        "module t\nstruct R { bad:i32, good:i32 }\n@untrusted\n"
        "fn f(i:i32)->i32 { var r=R{bad:0,good:0}\nr.bad=i\nlet a=[1,2]\nreturn a[r.good] }\n");
    bad_src("security: array element assignment updates element summary",
        "module t\n@untrusted\nfn f(i:i32)->i32 { var slots=[0,0]\nslots[0]=i\nlet a=[1,2]\nreturn a[slots[1]] }\n","BE0601",NULL);
    bad_src("security: inout helper propagates writes back to caller",
        "module t\nfn put(inout out:i32,i:i32){out=i}\n@untrusted\n"
        "fn f(i:i32)->i32 {var j=0\nput(inout j,i)\nlet a=[1,2]\nreturn a[j]}\n","BE0601",NULL);
    bad_src("security: set helper propagates writes back to caller",
        "module t\nfn put(set out:i32,i:i32){out=i}\n@untrusted\n"
        "fn f(i:i32)->i32 {var j:i32\nput(set j,i)\nlet a=[1,2]\nreturn a[j]}\n","BE0601",NULL);
    bad_src("security: loop backedge reaches earlier index",
        "module t\n@untrusted\nfn f(i:i32){var j=0\nlet a=[1,2]\n"
        "while true {let x=a[j]\nj=i}}\n","BE0601",NULL);
    bad_src("security: short circuit secret control is an observation",
        "module t\n@secret\nfn f(key:bool)->bool { return key && true }\n","BE0602",NULL);
    bad_src("security: recursive helper group propagates sources",
        "module t\nfn a(i:i32)->i32 {if i==0{return 0}\nreturn b(i)}\n"
        "fn b(i:i32)->i32{let values=[1,2]\nlet n=values[i]\nreturn a(n)}\n"
        "@untrusted\nfn f(i:i32)->i32{return a(i)}\n","BE0601",NULL);
    bad_src("security: mutation invalidates immutable-alias range assumption",
        "module t\n@untrusted\nfn f(i:i32)->i32 {var j=clamp(i,0,1)\nj=i\nlet a=[1,2]\nreturn a[j]}\n","BE0601",NULL);
    bad_src("security: source returned through zero-argument helper is propagated",
        "module t\n@untrusted\nfn source()->i32{return 12}\nfn middle()->i32{return source()}\n"
        "fn f()->i32{let a=[1,2]\nreturn a[middle()]}\n","BE0601",NULL);
    bad_src("security: helper range includes early return inside initializer",
        "module t\nfn bound(i:i32)->i32{let x=if i>2 {return i}\nreturn clamp(i,0,1)}\n"
        "@untrusted\nfn f(i:i32)->i32{let a=[1,2]\nreturn a[bound(i)]}\n","BE0601",NULL);
    bad_src("security: helper range includes immediate defer return",
        "module t\nfn bound(i:i32)->i32{defer {if i>2{return i}}\nreturn clamp(i,0,1)}\n"
        "@untrusted\nfn f(i:i32)->i32{let a=[1,2]\nreturn a[bound(i)]}\n","BE0601",NULL);
    bad_src("security: list element keeps provenance across helper calls",
        "module t\nfn add(inout xs:List<i32>,i:i32){xs.push(i)}\n"
        "@untrusted\nfn f(i:i32)->i32{var xs:List<i32>\nadd(inout xs,i)\nlet a=[1,2]\nreturn a[xs.get(0)]}\n","BE0601",NULL);
    bad_src("security: nested helper field write keeps provenance",
        "module t\nstruct R{value:i32}\nfn put(inout r:R,i:i32){r.value=i}\n"
        "@untrusted\nfn f(i:i32)->i32{var r=R{value:0}\nput(inout r,i)\nlet a=[1,2]\nreturn a[r.value]}\n","BE0601",NULL);
    bad_src("security: catch error binding retains union provenance",
        "module t\n@untrusted\nfn source()->!i32{return error.Bad}\n"
        "fn f(){let a=[1,2]\nlet v=source() catch |err| {let x=a[err]}}\n","BE0601",NULL);
    bad_src("security: try propagates error provenance into return summary",
        "module t\n@untrusted\nfn source()->!i32{return error.Bad}\n"
        "fn middle()->!i32{let x=try source()\nreturn 0}\n"
        "fn f(){let a=[1,2]\nlet v=middle() catch |err| {let x=a[err]}}\n","BE0601",NULL);
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
    test_provenance_regressions();
}
