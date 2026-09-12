#include "test.h"
#include "../../src/common/fs.h"
#include "../../src/parse/parser.h"
#include "../../src/parse/print.h"

typedef struct { Arena *a; SourceMap *sm; DiagBag *d; Interner *in; } LimitsFx;
static LimitsFx limits_fx(void) {
    LimitsFx f={0}; f.a=arena_new(0); f.sm=srcmap_new(f.a);
    f.d=diag_new(f.a,f.sm); f.in=intern_new(f.a); return f;
}
static Module *limits_parse(LimitsFx *f, Str code) {
    uint32_t id=srcmap_add(f->sm,STR_LIT("limits.be"),code);
    return parse_file(f->a,f->d,f->in,lex_file(f->a,f->sm,f->d,f->in,id),id);
}
static void rejected(LimitsFx *f, Str code, const char *reason) {
    Module *m=limits_parse(f,code);
    CHECK(m && m->items.len==0);
    CHECK_EQ_I(diag_errors(f->d),1);
    Str text=diag_render_str(f->a,f->d);
    CHECK_CONTAINS(text,"BE0210"); CHECK_CONTAINS(text,reason);
    /* Resource rejection must not hand a dangerous tree to the AST printer. */
    CHECK(ast_print(f->a,m).len<256);
}
static void chain(const char *name,const char *prefix,const char *unit,
                  uint32_t count,const char *suffix,const char *reason) {
    CASE(name); LimitsFx f=limits_fx(); SB b; sb_init(&b,f.a);
    sb_cstr(&b,prefix); for (uint32_t i=0;i<count;i++) sb_cstr(&b,unit); sb_cstr(&b,suffix);
    rejected(&f,sb_finish(&b),reason); arena_free(f.a);
}
void run_parser_limits_tests(void) {
    chain("parser limits: unary recursion", "module p\nfn f(){let n=", "!", 2048,
          "true\n}\n", "recursive parse depth");
    CASE("parser limits: nested parentheses");
    LimitsFx f=limits_fx(); SB b; sb_init(&b,f.a);
    sb_cstr(&b,"module p\nfn f(){let n="); sb_repeat(&b,'(',2048); sb_cstr(&b,"1");
    sb_repeat(&b,')',2048); sb_cstr(&b,"\n}\n");
    rejected(&f,sb_finish(&b),"recursive parse depth"); arena_free(f.a);

    CASE("parser limits: generic type recursion including split shift tokens");
    f=limits_fx(); sb_init(&b,f.a); sb_cstr(&b,"module p\nfn f(x:");
    for (uint32_t i=0;i<1024;i++) sb_cstr(&b,"List<");
    sb_cstr(&b,"i32"); sb_repeat(&b,'>',1024); sb_cstr(&b,"){}\n");
    rejected(&f,sb_finish(&b),"recursive parse depth"); arena_free(f.a);

    CASE("parser limits: nested array type and length expressions");
    f=limits_fx(); sb_init(&b,f.a); sb_cstr(&b,"module p\nfn f(x:");
    sb_repeat(&b,'[',1024); sb_cstr(&b,"i32");
    for (uint32_t i=0;i<1024;i++) sb_cstr(&b,";1]");
    sb_cstr(&b,"){}\n"); rejected(&f,sb_finish(&b),"recursive parse depth"); arena_free(f.a);

    chain("parser limits: error-union type recursion", "module p\nfn f(x:", "!", 1024,
          "i32){}\n", "recursive parse depth");
    chain("parser limits: iterative optional type depth", "module p\nfn f(x:i32", "?", 2048,
          "){}\n", "syntax tree depth");
    chain("parser limits: direct else-if recursion", "module p\nfn f(){", "if true {} else ", 1024,
          "{}\n}\n", "recursive parse depth");

    CASE("parser limits: nested statement blocks");
    f=limits_fx(); sb_init(&b,f.a); sb_cstr(&b,"module p\nfn f(){");
    sb_repeat(&b,'{',1024); sb_repeat(&b,'}',1024); sb_cstr(&b,"}\n");
    rejected(&f,sb_finish(&b),"recursive parse depth"); arena_free(f.a);
    chain("parser limits: flat left-associative AST depth", "module p\nfn f(){return 1", "+1", 5000,
          "\n}\n", "syntax tree depth");
    chain("parser limits: flat field AST depth", "module p\nfn f(){return a", ".x", 5000,
          "\n}\n", "syntax tree depth");
    chain("parser limits: flat call AST depth", "module p\nfn f(){return a", "()", 5000,
          "\n}\n", "syntax tree depth");
    chain("parser limits: flat index AST depth", "module p\nfn f(){return a", "[0]", 5000,
          "\n}\n", "syntax tree depth");

    CASE("parser limits: duplicate-parameter scan has a work budget");
    f=limits_fx(); sb_init(&b,f.a); sb_cstr(&b,"module p\nfn f(");
    for (uint32_t i=0;i<2048;i++) sb_fmt(&b,"%sx%u:i32",i?",":"",i);
    sb_cstr(&b,"){}\n"); rejected(&f,sb_finish(&b),"parser work"); arena_free(f.a);

    CASE("parser limits: malformed token streams reject before lookup");
    for (uint32_t mode=0;mode<7;mode++) {
        f=limits_fx(); Token tokens[2]={{.kind=TK_IDENT},{.kind=TK_EOF}};
        TokenVec tv={.data=tokens,.len=2,.cap=2};
        if (mode==0) tv.len=0;
        if (mode==1) tv.data=NULL;
        if (mode==2) tv.cap=1;
        if (mode==3) tokens[1].kind=TK_IDENT;
        if (mode==4) tokens[0].kind=TK_EOF;
        if (mode==5) tokens[0].kind=(TokKind)-1;
        if (mode==6) tokens[0].kind=TK_COUNT;
        Module *m=parse_file(f.a,f.d,f.in,tv,0);
        CHECK(m && m->items.len==0); CHECK_EQ_I(diag_errors(f.d),1);
        CHECK_CONTAINS(diag_render_str(f.a,f.d),"invalid token stream"); arena_free(f.a);
    }
    CASE("parser limits: token-count rejection precedes oversized-vector access");
    f=limits_fx(); Token eof={.kind=TK_EOF};
    TokenVec too_many={.data=&eof,.len=PARSE_MAX_TOKENS+1,.cap=PARSE_MAX_TOKENS+1};
    Module *m=parse_file(f.a,f.d,f.in,too_many,0);
    CHECK(m && m->items.len==0); CHECK_EQ_I(diag_errors(f.d),1);
    CHECK_CONTAINS(diag_render_str(f.a,f.d),"tokens per file"); arena_free(f.a);

    CASE("parser limits: exact AST depth boundary and immediate next rejection");
    for (uint32_t extra=0;extra<2;extra++) {
        f=limits_fx(); sb_init(&b,f.a); sb_cstr(&b,"module p\nfn f(){return 1");
        for (uint32_t i=0;i<PARSE_MAX_AST_DEPTH-4+extra;i++) sb_cstr(&b,"+1");
        sb_cstr(&b,"\n}\n"); m=limits_parse(&f,sb_finish(&b));
        if (!extra) { CHECK_EQ_I(diag_errors(f.d),0); CHECK_EQ_I(m->items.len,1); CHECK(ast_print(f.a,m).len>100); }
        else { CHECK_EQ_I(diag_errors(f.d),1); CHECK_EQ_I(m->items.len,0); }
        arena_free(f.a);
    }
    CASE("parser limits: ordinary nesting and independent later file stay admitted");
    f=limits_fx(); sb_init(&b,f.a); sb_cstr(&b,"module p\nfn f(){return ");
    sb_repeat(&b,'(',32); sb_cstr(&b,"1+2*3"); sb_repeat(&b,')',32); sb_cstr(&b,"\n}\n");
    m=limits_parse(&f,sb_finish(&b)); CHECK_EQ_I(diag_errors(f.d),0); CHECK_EQ_I(m->items.len,1);
    m=limits_parse(&f,STR_LIT("module next\nfn next(){return 1}\n"));
    CHECK_EQ_I(diag_errors(f.d),0); CHECK_EQ_I(m->items.len,1); arena_free(f.a);

    CASE("parser limits: complete current PID implementation and corpus parse");
    const char *paths[]={"packages/sparkos/pid/pid.be","packages/sparkos/pid/pid_test.be"};
    for (uint32_t i=0;i<2;i++) {
        f=limits_fx(); Str content=STR_EMPTY; CHECK(fs_read(f.a,paths[i],&content));
        m=limits_parse(&f,content); CHECK_EQ_I(diag_errors(f.d),0); CHECK(m && m->items.len>0);
        arena_free(f.a);
    }
}
