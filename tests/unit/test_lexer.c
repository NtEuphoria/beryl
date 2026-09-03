/* Tests for the lexer, including the newline-termination rule. */

#include "../../src/lex/lexer.h"
#include "test.h"

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

static TokenVec lex_str(Fx *f, const char *src) {
    uint32_t file = srcmap_add(f->sm, str_from("t.be"), str_from(src));
    return lex_file(f->a, f->sm, f->d, f->in, file);
}

/* Compact rendering of a token stream, for readable assertions. */
static Str dump(Fx *f, TokenVec v) {
    SB sb;
    sb_init(&sb, f->a);
    for (uint32_t i = 0; i < v.len; i++) {
        if (i) sb_char(&sb, ' ');
        Token t = v.data[i];
        switch (t.kind) {
            case TK_IDENT: sb_fmt(&sb, "id:%.*s", (int)t.text.len, t.text.ptr); break;
            case TK_INT: sb_fmt(&sb, "int:%llu", (unsigned long long)t.ival); break;
            case TK_FLOAT: sb_cstr(&sb, "flt"); break;
            case TK_STRING: sb_fmt(&sb, "str:%.*s", (int)t.text.len, t.text.ptr); break;
            case TK_CHAR: sb_fmt(&sb, "chr:%llu", (unsigned long long)t.ival); break;
            case TK_DOC: sb_cstr(&sb, "doc"); break;
            case TK_NEWLINE: sb_cstr(&sb, "NL"); break;
            case TK_EOF: sb_cstr(&sb, "EOF"); break;
            default: sb_cstr(&sb, tok_name(t.kind)); break;
        }
    }
    return sb_finish(&sb);
}

static void test_keywords(void) {
    Fx f = fx_new();

    CASE("lexer: every keyword maps to its own kind");
    TokenVec v = lex_str(&f, "module use pub fn struct enum trait let var if else while "
                             "for in return break continue test const comptime true false "
                             "inout sink set as try catch orelse error defer self match");
    /* No newlines inside, so kinds line up one-to-one before EOF. */
    TokKind expect[] = {TK_MODULE, TK_USE,   TK_PUB,    TK_FN,       TK_STRUCT, TK_ENUM,
                        TK_TRAIT,  TK_LET,   TK_VAR,    TK_IF,       TK_ELSE,   TK_WHILE,
                        TK_FOR,    TK_IN,    TK_RETURN, TK_BREAK,    TK_CONTINUE,
                        TK_TEST,   TK_CONST, TK_COMPTIME, TK_TRUE,   TK_FALSE,  TK_INOUT,
                        TK_SINK,   TK_SET,   TK_AS,     TK_TRY,      TK_CATCH,  TK_ORELSE,
                        TK_ERROR,  TK_DEFER, TK_SELF,   TK_MATCH};
    CHECK_EQ_I(v.len, sizeof expect / sizeof expect[0] + 1); /* + EOF */
    bool ok = true;
    for (uint32_t i = 0; i < sizeof expect / sizeof expect[0]; i++)
        if (v.data[i].kind != expect[i]) ok = false;
    CHECK(ok);

    CASE("lexer: identifiers with keyword prefixes are identifiers");
    CHECK_EQ_S(dump(&f, lex_str(&f, "letter iffy return_value inx selfish")),
               "id:letter id:iffy id:return_value id:inx id:selfish EOF");

    CHECK_EQ_I(diag_errors(f.d), 0);
    fx_free(&f);
}

static void test_operators(void) {
    Fx f = fx_new();

    CASE("lexer: maximal munch on multi-character operators");
    CHECK_EQ_S(dump(&f, lex_str(&f, "== != <= >= && || << >> += -= *= /= %= -> => .. ")),
               "== != <= >= && || << >> += -= *= /= %= -> => .. EOF");

    CASE("lexer: single-character operators are not over-munched");
    CHECK_EQ_S(dump(&f, lex_str(&f, "= ! < > & | + - * / % . @ ? : ~ ^")),
               "= ! < > & | + - * / % . @ ? : ~ ^ EOF");

    CASE("lexer: brackets");
    CHECK_EQ_S(dump(&f, lex_str(&f, "( ) { } [ ] ,")), "( ) { } [ ] , EOF");

    CHECK_EQ_I(diag_errors(f.d), 0);
    fx_free(&f);
}

static void test_numbers(void) {
    Fx f = fx_new();

    CASE("lexer: decimal, hex, binary, octal, with separators");
    TokenVec v = lex_str(&f, "0 42 1_000_000 0xFF 0xff 0b1010 0o777");
    CHECK_EQ_I(v.data[0].ival, 0);
    CHECK_EQ_I(v.data[1].ival, 42);
    CHECK_EQ_I(v.data[2].ival, 1000000);
    CHECK_EQ_I(v.data[3].ival, 255);
    CHECK_EQ_I(v.data[4].ival, 255);
    CHECK_EQ_I(v.data[5].ival, 10);
    CHECK_EQ_I(v.data[6].ival, 511);

    CASE("lexer: numeric suffixes are captured");
    v = lex_str(&f, "42i64 7u8 3.5f32");
    CHECK_EQ_I(v.data[0].kind, TK_INT);
    CHECK_EQ_S(v.data[0].suffix, "i64");
    CHECK_EQ_S(v.data[1].suffix, "u8");
    CHECK_EQ_I(v.data[2].kind, TK_FLOAT);
    CHECK_EQ_S(v.data[2].suffix, "f32");

    CASE("lexer: an integer literal with a float suffix becomes a float");
    v = lex_str(&f, "1f32");
    CHECK_EQ_I(v.data[0].kind, TK_FLOAT);
    CHECK(v.data[0].fval == 1.0);

    CASE("lexer: floats including exponents");
    v = lex_str(&f, "1.5 1e-9 2.5E+3 1.0");
    CHECK_EQ_I(v.data[0].kind, TK_FLOAT);
    CHECK(v.data[0].fval == 1.5);
    CHECK_EQ_I(v.data[1].kind, TK_FLOAT);
    CHECK(v.data[1].fval < 1e-8 && v.data[1].fval > 0);
    CHECK_EQ_I(v.data[2].kind, TK_FLOAT);
    CHECK(v.data[2].fval == 2500.0);

    CASE("lexer: `1..2` is INT DOTDOT INT, never a float");
    CHECK_EQ_S(dump(&f, lex_str(&f, "1..2")), "int:1 .. int:2 EOF");
    CHECK_EQ_S(dump(&f, lex_str(&f, "0..len")), "int:0 .. id:len EOF");

    CASE("lexer: `1.` without a following digit is INT then DOT");
    CHECK_EQ_S(dump(&f, lex_str(&f, "1.x")), "int:1 . id:x EOF");

    CHECK_EQ_I(diag_errors(f.d), 0);

    CASE("lexer: unknown numeric suffix is BE0104");
    Fx g = fx_new();
    lex_str(&g, "42zz");
    CHECK_EQ_I(diag_errors(g.d), 1);
    CHECK_CONTAINS(diag_render_str(g.a, g.d), "error[BE0104]");
    CHECK_CONTAINS(diag_render_str(g.a, g.d), "unknown numeric suffix `zz`");
    fx_free(&g);

    CASE("lexer: oversized integer literal is BE0106");
    Fx h = fx_new();
    lex_str(&h, "99999999999999999999999");
    CHECK_EQ_I(diag_errors(h.d), 1);
    CHECK_CONTAINS(diag_render_str(h.a, h.d), "error[BE0106]");
    fx_free(&h);

    fx_free(&f);
}

static void test_strings(void) {
    Fx f = fx_new();

    CASE("lexer: string escapes are cooked");
    TokenVec v = lex_str(&f, "\"a\\nb\" \"tab\\there\" \"q\\\"q\" \"\\x41\"");
    CHECK_EQ_S(v.data[0].text, "a\nb");
    CHECK_EQ_S(v.data[1].text, "tab\there");
    CHECK_EQ_S(v.data[2].text, "q\"q");
    CHECK_EQ_S(v.data[3].text, "A");

    CASE("lexer: raw strings keep backslashes");
    v = lex_str(&f, "r\"a\\nb\"");
    CHECK_EQ_I(v.data[0].kind, TK_STRING);
    CHECK_EQ_S(v.data[0].text, "a\\nb");

    CASE("lexer: char literals");
    v = lex_str(&f, "'a' '\\n' '\\x41'");
    CHECK_EQ_I(v.data[0].ival, 'a');
    CHECK_EQ_I(v.data[1].ival, '\n');
    CHECK_EQ_I(v.data[2].ival, 65);

    CHECK_EQ_I(diag_errors(f.d), 0);

    CASE("lexer: unterminated string is BE0101 at the opening quote");
    Fx g = fx_new();
    lex_str(&g, "let s = \"oops\n");
    CHECK_EQ_I(diag_errors(g.d), 1);
    Str out = diag_render_str(g.a, g.d);
    CHECK_CONTAINS(out, "error[BE0101]");
    CHECK_CONTAINS(out, "unterminated string literal");
    CHECK_CONTAINS(out, ":1:9");
    fx_free(&g);

    CASE("lexer: unknown escape is BE0103 with a help line");
    Fx h = fx_new();
    lex_str(&h, "\"a\\qb\"");
    CHECK_EQ_I(diag_errors(h.d), 1);
    CHECK_CONTAINS(diag_render_str(h.a, h.d), "error[BE0103]");
    CHECK_CONTAINS(diag_render_str(h.a, h.d), "= help:");
    fx_free(&h);

    fx_free(&f);
}

static void test_comments(void) {
    Fx f = fx_new();

    CASE("lexer: line comments are skipped");
    CHECK_EQ_S(dump(&f, lex_str(&f, "a // this is ignored\nb")), "id:a NL id:b EOF");

    CASE("lexer: doc comments become tokens");
    CHECK_EQ_S(dump(&f, lex_str(&f, "//! docs here\nfn")), "doc fn EOF");

    CHECK_EQ_I(diag_errors(f.d), 0);

    CASE("lexer: block comments are BE0107 with a help line");
    Fx g = fx_new();
    lex_str(&g, "a /* nope */ b");
    CHECK_EQ_I(diag_errors(g.d), 1);
    CHECK_CONTAINS(diag_render_str(g.a, g.d), "error[BE0107]");
    CHECK_CONTAINS(diag_render_str(g.a, g.d), "block comments are not supported");
    fx_free(&g);

    fx_free(&f);
}

static void test_newline_rule(void) {
    Fx f = fx_new();

    CASE("newline: two statements get exactly one terminator");
    CHECK_EQ_S(dump(&f, lex_str(&f, "let a = 1\nlet b = 2")),
               "let id:a = int:1 NL let id:b = int:2 EOF");

    CASE("newline: blank lines collapse");
    CHECK_EQ_S(dump(&f, lex_str(&f, "let a = 1\n\n\nlet b = 2")),
               "let id:a = int:1 NL let id:b = int:2 EOF");

    CASE("newline: a leading binary operator continues the previous line");
    CHECK_EQ_S(dump(&f, lex_str(&f, "return a\n+ b")), "return id:a + id:b EOF");
    CHECK_EQ_S(dump(&f, lex_str(&f, "x = a\n* b")), "id:x = id:a * id:b EOF");
    CHECK_EQ_S(dump(&f, lex_str(&f, "x = a\n&& b")), "id:x = id:a && id:b EOF");

    CASE("newline: a trailing operator continues onto the next line");
    CHECK_EQ_S(dump(&f, lex_str(&f, "x = a +\nb")), "id:x = id:a + id:b EOF");

    CASE("newline: suppressed inside parentheses and brackets");
    CHECK_EQ_S(dump(&f, lex_str(&f, "f(\n1,\n2\n)")),
               "id:f ( int:1 , int:2 ) EOF");
    CHECK_EQ_S(dump(&f, lex_str(&f, "a[\n1\n]")), "id:a [ int:1 ] EOF");

    CASE("newline: braces do not suppress, so statements in a block terminate");
    CHECK_EQ_S(dump(&f, lex_str(&f, "{\na\nb\n}")), "{ id:a NL id:b } EOF");

    CASE("newline: none emitted before a closing brace or before `else`");
    CHECK_EQ_S(dump(&f, lex_str(&f, "if c {\na\n}\nelse {\nb\n}")),
               "if id:c { id:a } else { id:b } EOF");

    CASE("newline: emitted after a closing brace when a statement follows");
    CHECK_EQ_S(dump(&f, lex_str(&f, "if c {\na\n}\nb = 1")),
               "if id:c { id:a } NL id:b = int:1 EOF");

    CASE("newline: struct fields separate on newlines");
    CHECK_EQ_S(dump(&f, lex_str(&f, "struct P {\nx: f32\ny: f32\n}")),
               "struct id:P { id:x : id:f32 NL id:y : id:f32 } EOF");

    CASE("newline: no terminator at the very start of a file");
    CHECK_EQ_S(dump(&f, lex_str(&f, "\n\nlet a = 1")), "let id:a = int:1 EOF");

    CASE("newline: `.` on the next line continues a method chain");
    CHECK_EQ_S(dump(&f, lex_str(&f, "a\n.b()")), "id:a . id:b ( ) EOF");

    CHECK_EQ_I(diag_errors(f.d), 0);
    fx_free(&f);
}

static void test_realistic(void) {
    Fx f = fx_new();

    CASE("lexer: a realistic function lexes cleanly with correct terminators");
    const char *src = "module flight.pid\n"
                      "\n"
                      "pub fn Pid.step(inout self, sp: f32, dt: f32) -> f32 {\n"
                      "    if dt <= 0 { return 0 }\n"
                      "    let err = sp - self.meas\n"
                      "    self.integral += err * dt\n"
                      "    return self.kp * err\n"
                      "         + self.ki * self.integral\n"
                      "}\n";
    TokenVec v = lex_str(&f, src);
    CHECK_EQ_I(diag_errors(f.d), 0);

    Str d = dump(&f, v);
    /* The continuation line must not have produced a terminator. */
    CHECK_CONTAINS(d, "return self . id:kp * id:err + self . id:ki");
    /* Statements inside the body must have. */
    CHECK_CONTAINS(d, "} NL let id:err");
    /* The module header terminates. */
    CHECK_CONTAINS(d, "module id:flight . id:pid NL pub fn");

    fx_free(&f);
}

void run_lexer_tests(void) {
    test_keywords();
    test_operators();
    test_numbers();
    test_strings();
    test_comments();
    test_newline_rule();
    test_realistic();
}
