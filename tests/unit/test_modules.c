#include "test.h"
#include "../../src/parse/parser.h"
#include "../../src/sema/check.h"
#include "../../src/sema/ownership.h"
#include "../../src/back/c_backend.h"
#include "../../src/back/enforce_backend.h"
#include "../../src/common/symbol.h"

typedef struct { Arena *a; SourceMap *sm; DiagBag *d; Interner *in; Program *p; } Fixture;
static Fixture fixture(void) {
    Fixture f={0}; f.a=arena_new(0); f.sm=srcmap_new(f.a); f.d=diag_new(f.a,f.sm);
    f.in=intern_new(f.a); f.p=prog_new(f.a); return f;
}
static void add(Fixture *f,const char *path,const char *code) {
    uint32_t id=srcmap_add(f->sm,str_from(path),str_from(code));
    TokenVec tokens=lex_file(f->a,f->sm,f->d,f->in,id);
    prog_add_module(f->p,parse_file(f->a,f->d,f->in,tokens,id));
}
static bool checked(Fixture *f) {
    return !diag_errors(f->d) && resolve_program(f->d,f->p) && check_program(f->d,f->p) &&
        ownership_check(f->d,f->p);
}
static void expect_failure(const char *name,const char *a,const char *b,const char *code) {
    CASE(name); Fixture f=fixture(); add(&f,"a.be",a); add(&f,"b.be",b);
    CHECK(!checked(&f)); CHECK_CONTAINS(diag_render_str(f.a,f.d),code); arena_free(f.a);
}
static unsigned occurrences(Str text,const char *needle) {
    unsigned count=0; Str n=str_from(needle);
    for (uint32_t i=0;i+n.len<=text.len;i++) if (str_eq(str_new(text.ptr+i,n.len),n)) count++;
    return count;
}

void run_module_tests(void) {
    expect_failure("modules: unrelated declarations are not visible",
        "module a\npub fn hidden() -> i32 { return 1 }\n",
        "module b\nfn f() -> i32 { return hidden() }\n","BE0301");
    expect_failure("modules: private import fails",
        "module a\nstruct Secret { x: i32 }\n",
        "module b\nuse a.Secret\nfn f() {}\n","BE0323");
    expect_failure("modules: private qualified call fails",
        "module a\nfn hidden() -> i32 { return 1 }\n",
        "module b\nuse a\nfn f() -> i32 { return a.hidden() }\n","BE0323");
    expect_failure("modules: import spelling cannot fall back to another function",
        "module a\npub fn f() -> i32 { return 1 }\n",
        "module b\nfn g() -> i32 { return absent.f() }\n","BE0301");
    expect_failure("modules: unknown import fails",
        "module a\npub struct P { x: i32 }\n",
        "module b\nuse a.Missing\n","BE0324");
    expect_failure("modules: imported name conflicts with declaration",
        "module a\npub struct P { x: i32 }\n",
        "module b\nuse a.P\nstruct P { x: i32 }\n","BE0308");
    expect_failure("modules: identically spelled records are different types",
        "module a\npub struct P { x: i32 }\npub fn take(let p: P) {}\n",
        "module b\nuse a\nstruct P { x: i32 }\nfn f() { a.take(P{x: 1}) }\n","BE0303");
    expect_failure("modules: private method remains private through public type",
        "module a\npub struct P { x: i32 }\nfn P.get(let self) -> i32 { return self.x }\n",
        "module b\nuse a.P\nfn f() -> i32 { let p = P{x: 1}\nreturn p.get() }\n","BE0323");
    expect_failure("modules: no inferred short type parameters",
        "module a\nfn f(let value: X) {}\n", "module b\n","BE0302");
    expect_failure("modules: qualified primitives do not discard module prefix",
        "module a\nfn f(let value: missing.i32) {}\n", "module b\n","BE0302");
    expect_failure("modules: external methods cannot attach by receiver spelling",
        "module a\npub struct P { x: i32 }\n",
        "module b\nuse a.P\npub fn P.get(let self) -> i32 { return self.x }\n","BE0323");
    expect_failure("modules: duplicate parameters have no declaration identity",
        "module a\nfn f(let x: i32, let x: i32) {}\n", "module b\n", "BE0205");
    expect_failure("modules: duplicate generic parameters are rejected",
        "module a\nfn f<Element, Element>() {}\n", "module b\n", "BE0308");
    expect_failure("modules: instance method cannot receive a type as its value",
        "module a\npub struct P { x: i32 }\npub fn P.get(let self) -> i32 { return self.x }\n",
        "module b\nuse a.P\nfn f() -> i32 { return P.get() }\n", "BE0307");
    expect_failure("modules: static method cannot silently discard a value receiver",
        "module a\npub struct P { x: i32 }\npub fn P.get() -> i32 { return 1 }\n",
        "module b\nuse a.P\nfn f() -> i32 { let p = P{x: 0}\nreturn p.get() }\n", "BE0307");

    CASE("modules: declared long generic parameter resolves in its declaration");
    Fixture f=fixture(); add(&f,"generic.be","module generic\nfn identity<Element>(let value: Element) -> Element { return value }\n");
    CHECK(checked(&f));
    Item *fn=prog_item(f.p,str_from("generic.identity"));
    CHECK(fn && fn->fn.params.data[0].rtype->kind==TY_TYPEPARAM);
    if (fn) CHECK(fn->rtype==fn->fn.params.data[0].rtype);
    arena_free(f.a);

    CASE("modules: native entry point ambiguity fails with both sites");
    f=fixture(); add(&f,"one.be","module one\nfn main() {}\n");
    add(&f,"two.be","module two\nfn main() {}\n");
    CHECK(checked(&f)); cgen_program(f.a,f.sm,f.d,f.p,CGEN_PROGRAM);
    CHECK_CONTAINS(diag_render_str(f.a,f.d),"BE0325");
    CHECK_CONTAINS(diag_render_str(f.a,f.d),"other entry point here"); arena_free(f.a);

    CASE("modules: invalid prefix cannot become an engine identifier or output path");
    f=fixture(); add(&f,"one.be","module one\nstruct P { x: i32 }\n"); CHECK(checked(&f));
    CHECK(!enfusion_lint(f.d,f.p,(EnfusionOpts){.prefix=str_from("../escape")}));
    CHECK_CONTAINS(diag_render_str(f.a,f.d),"BE0804"); arena_free(f.a);

    CASE("modules: conflicting imports identify both sites");
    f=fixture();
    add(&f,"a.be","module a\npub struct P { x: i32 }\n");
    add(&f,"b.be","module b\npub struct P { x: i32 }\n");
    add(&f,"c.be","module c\nuse a.P\nuse b.P\n");
    CHECK(!checked(&f)); Str diagnostics=diag_render_str(f.a,f.d);
    CHECK_CONTAINS(diagnostics,"BE0308"); CHECK_CONTAINS(diagnostics,"first declaration here");
    CHECK_CONTAINS(diagnostics,"conflicting declaration here"); arena_free(f.a);

    CASE("modules: imports, qualified constants, methods, and extents use declaration identity");
    f=fixture();
    add(&f,"a.be","module deep.a\nconst BASE: i32 = 2\npub const SIZE: i32 = BASE + 1\n"
        "pub struct P { x: i32 }\npub fn P.get(let self) -> i32 { return self.x + SIZE }\n"
        "pub fn size() -> i32 { return SIZE }\n");
    add(&f,"b.be","module deep.b\npub struct P { x: i32 }\npub fn P.get(let self) -> i32 { return self.x * 2 }\n");
    add(&f,"main.be","module main\nuse deep.a\nuse deep.b\nuse deep.a.SIZE\nuse deep.a.SIZE\n"
        "const BASE: i32 = 99\nstruct Storage { values: [i32; SIZE] }\n"
        "fn main() { let p = a.P{x: 4}\nlet q = b.P{x: 5}\n"
        "assert(p.get() == 7)\nassert(q.get() == 10)\nassert(deep.a.SIZE == 3)\nassert(a.size() == 3) }\n");
    bool ok=checked(&f); CHECK(ok);
    if (!ok) { Str d=diag_render_str(f.a,f.d); printf("%.*s\n",(int)d.len,d.ptr); }
    if (ok) {
        Item *a=prog_item(f.p,str_from("deep.a.P")), *b=prog_item(f.p,str_from("deep.b.P"));
        CHECK(a->rtype!=b->rtype);
        CHECK(prog_method(f.p,a,str_from("get"))->fn.recv_decl==a);
        CHECK(prog_method(f.p,b,str_from("get"))->fn.recv_decl==b);
        Item *storage=prog_item(f.p,str_from("main.Storage"));
        CHECK_EQ_I(storage->strukt.fields.data[0].rtype->array_len,3);
        Str native=cgen_program(f.a,f.sm,f.d,f.p,CGEN_PROGRAM);
        CHECK_CONTAINS(native,"be_i_deep_2ea_2eP"); CHECK_CONTAINS(native,"be_i_deep_2eb_2eP");
        EnfusionOpts opts={.prefix=str_from("UT")};
        Str engine=enfusion_render_all(f.a,f.sm,f.d,f.p,opts);
        CHECK_EQ_I(occurrences(engine,"class UT_be_i_deep_2ea_2eP\n"),1);
        CHECK_EQ_I(occurrences(engine,"class UT_be_i_deep_2eb_2eP\n"),1);
        CHECK_EQ_I(occurrences(engine,"be_m_get("),2); /* main omitted, one method per type */
        CHECK_EQ_I(diag_errors(f.d),0);
    }
    arena_free(f.a);

    CASE("modules: multiple files share private scope and one generated holder");
    f=fixture();
    add(&f,"one.be","module shared\nfn first() -> i32 { return second() }\ntest \"same\" { assert(first() == 2) }\n");
    add(&f,"two.be","module shared\nfn second() -> i32 { return 2 }\ntest \"same\" { assert(second() == 2) }\n");
    CHECK(checked(&f));
    Str engine=enfusion_render_all(f.a,f.sm,f.d,f.p,(EnfusionOpts){.prefix=str_from("UT")});
    CHECK_EQ_I(occurrences(engine,"class UT_be_h_shared\n"),1);
    CHECK_CONTAINS(engine,"be_m_first"); CHECK_CONTAINS(engine,"be_m_second");
    arena_free(f.a);

    CASE("symbols: encoding distinguishes punctuation, escapes, and categories");
    Arena *a=arena_new(0);
    CHECK(!str_eq(symbol_encode(a,"i",str_from("a.b")),symbol_encode(a,"i",str_from("a_b"))));
    CHECK(!str_eq(symbol_encode(a,"i",str_from("a.b")),symbol_encode(a,"i",str_from("a_2eb"))));
    CHECK(!str_eq(symbol_encode(a,"i",str_from("P")),symbol_encode(a,"t",str_from("P"))));
    arena_free(a);

    CASE("exports: exact public names replace internal names at declarations and calls");
    f=fixture();
    add(&f,"export.be","module controller\npub struct P { value: i32 }\n"
        "pub fn P.step(inout self, let x: i32 = 2) -> i32 { self.value += x\nreturn self.value }\n"
        "pub fn exercise() -> i32 { var p = P{value: 1}\nreturn p.step() }\n");
    CHECK(checked(&f));
    EnfusionExport mappings[]={
        {.kind=EF_EXPORT_CLASS,.source=str_from("controller.P"),.name=str_from("SPK_PID")},
        {.kind=EF_EXPORT_METHOD,.source=str_from("controller.P.step"),.name=str_from("Step")}
    };
    EnfusionOpts opts={.prefix=str_from("UT"),.exports={.data=mappings,.len=2,.cap=2}};
    CHECK(enfusion_lint(f.d,f.p,opts));
    Str exported=enfusion_render_all(f.a,f.sm,f.d,f.p,opts);
    CHECK_CONTAINS(exported,"class SPK_PID\n"); CHECK_CONTAINS(exported,"int Step(");
    CHECK_CONTAINS(exported,".Step(2)"); CHECK_CONTAINS(exported,"new SPK_PID()");
    CHECK(str_eq_c(enfusion_file_name(f.a,mappings[0].item,opts),"SPK_PID.c"));
    mappings[1].name=str_from("BerylCopy");
    CHECK(!enfusion_lint(f.d,f.p,opts)); CHECK_CONTAINS(diag_render_str(f.a,f.d),"BE0326");
    arena_free(f.a);

    CASE("exports: engine constructor preserves independent value construction");
    f=fixture();
    add(&f,"constructor.be","module controller\npub struct P { value: i32 = 7 }\n"
        "pub fn P.initialize(inout self, let x: i32 = 2) { self.value = x }\n"
        "pub fn P.step(inout self, let x: i32) -> i32 { self.value += x\nreturn self.value }\n"
        "pub fn exercise() -> i32 { let p = P{}\nlet copy = p\nreturn copy.value }\n");
    CHECK(checked(&f));
    EnfusionExport constructors[]={
        {.kind=EF_EXPORT_CLASS,.source=str_from("controller.P"),.name=str_from("SPK_PID")},
        {.kind=EF_EXPORT_CONSTRUCTOR,.source=str_from("controller.P.initialize"),.name=str_from("SPK_PID")},
        {.kind=EF_EXPORT_METHOD,.source=str_from("controller.P.step"),.name=str_from("Step")}
    };
    opts=(EnfusionOpts){.prefix=str_from("UT"),.exports={.data=constructors,.len=3,.cap=3}};
    CHECK(enfusion_lint(f.d,f.p,opts));
    exported=enfusion_render_all(f.a,f.sm,f.d,f.p,opts);
    CHECK_CONTAINS(exported,"class SPK_PID : UT_be_i_controller_2eP");
    CHECK_CONTAINS(exported,"void SPK_PID(int be_l_x_");
    CHECK_CONTAINS(exported,"void be_m_initialize(");
    CHECK_CONTAINS(exported,"be_m_initialize(be_l_x_");
    CHECK_CONTAINS(exported,"new UT_be_i_controller_2eP()");
    CHECK_MISSING(exported,"new SPK_PID()");
    CHECK_EQ_I(occurrences(exported,"class SPK_PID :"),1);
    constructors[1].source=str_from("controller.P.step");
    opts.exports.len=2;
    CHECK(!enfusion_lint(f.d,f.p,opts));
    CHECK_CONTAINS(diag_render_str(f.a,f.d),"returning void"); arena_free(f.a);

    CASE("exports: class collisions identify both declarations");
    f=fixture(); add(&f,"export.be","module t\npub struct A { x: i32 }\npub struct B { x: i32 }\n");
    CHECK(checked(&f));
    EnfusionExport duplicates[]={
        {.kind=EF_EXPORT_CLASS,.source=str_from("t.A"),.name=str_from("SPK_PID")},
        {.kind=EF_EXPORT_CLASS,.source=str_from("t.B"),.name=str_from("spk_pid")}
    };
    CHECK(!enfusion_lint(f.d,f.p,(EnfusionOpts){.exports={.data=duplicates,.len=2,.cap=2}}));
    CHECK_CONTAINS(diag_render_str(f.a,f.d),"duplicate exported class identity");
    CHECK_CONTAINS(diag_render_str(f.a,f.d),"other export here"); arena_free(f.a);

    CASE("exports: unknown declarations fail before rendering");
    f=fixture(); add(&f,"export.be","module t\npub struct A { x: i32 }\n"); CHECK(checked(&f));
    EnfusionExport missing={.kind=EF_EXPORT_CLASS,.source=str_from("t.Missing"),.name=str_from("SPK_PID")};
    CHECK(!enfusion_lint(f.d,f.p,(EnfusionOpts){.exports={.data=&missing,.len=1,.cap=1}}));
    CHECK_CONTAINS(diag_render_str(f.a,f.d),"BE0326"); arena_free(f.a);

    CASE("codegen: proven inout parameters are restrict");
    f=fixture();
    add(&f,"t.be","module t\nfn add(inout y: [i32; 4], inout x: [i32; 4]) {\n"
        "    y[0] = y[0] + x[0]\n}\n"
        "fn main() {\n    var y = [1, 2, 3, 4]\n    var x = [1, 1, 1, 1]\n"
        "    add(inout y, inout x)\n    println(y[0])\n}\n");
    CHECK(checked(&f));
    Str native=cgen_program(f.a,f.sm,f.d,f.p,CGEN_PROGRAM);
    CHECK_CONTAINS(native,"*restrict ");
    arena_free(f.a);

    CASE("codegen: an unproven exclusive argument revokes restrict");
    f=fixture();
    add(&f,"t.be","module t\nstruct P { x: i32 }\n"
        "fn make() -> P { return P{ x: 1 } }\n"
        "fn bump(inout p: P) { p.x = p.x + 1 }\n"
        "fn main() { bump(inout make().x)\n }\n");
    bool admitted=checked(&f);
    if (admitted) {
        Str text=cgen_program(f.a,f.sm,f.d,f.p,CGEN_PROGRAM);
        CHECK_MISSING(text,"*restrict ");
    }
    arena_free(f.a);
}
