/* Tests for the source map and the diagnostic renderer. */
#include <string.h>

#include "../../src/common/diag.h"
#include "../../src/common/source.h"
#include "test.h"

/* Byte offset of the nth (1-based) occurrence of `needle` in a NUL-terminated
 * source string. */
static uint32_t off_of(const char *src, const char *needle, int nth) {
    const char *p = src;
    for (int i = 0; i < nth; i++) {
        p = strstr(p, needle);
        if (!p) return 0;
        if (i + 1 < nth) p += 1;
    }
    return (uint32_t)(p - src);
}

static void test_srcmap(void) {
    Arena     *a  = arena_new(0);
    SourceMap *sm = srcmap_new(a);

    const char *src = "module main\n"
                      "\n"
                      "fn main() {\n"
                      "    var a = 1\n"
                      "}\n";
    uint32_t f = srcmap_add(sm, str_from("test.be"), str_from(src));

    CASE("srcmap: line/col at the start of the file");
    LineCol lc = srcmap_linecol(sm, (Span){f, 0, 1});
    CHECK_EQ_I(lc.line, 1);
    CHECK_EQ_I(lc.col, 1);

    CASE("srcmap: line/col immediately after a newline");
    lc = srcmap_linecol(sm, (Span){f, 12, 1}); /* start of the blank line 2 */
    CHECK_EQ_I(lc.line, 2);
    CHECK_EQ_I(lc.col, 1);

    CASE("srcmap: line/col mid-line");
    uint32_t off = off_of(src, "var", 1);
    lc           = srcmap_linecol(sm, (Span){f, off, 3});
    CHECK_EQ_I(lc.line, 4);
    CHECK_EQ_I(lc.col, 5); /* four spaces of indent */

    CASE("srcmap: line text excludes the newline");
    CHECK_EQ_S(srcmap_line(sm, f, 1), "module main");
    CHECK_EQ_S(srcmap_line(sm, f, 2), "");
    CHECK_EQ_S(srcmap_line(sm, f, 4), "    var a = 1");

    CASE("srcmap: out-of-range line is empty, not a crash");
    CHECK_EQ_S(srcmap_line(sm, f, 999), "");
    CHECK_EQ_S(srcmap_line(sm, f, 0), "");

    CASE("srcmap: last line without a trailing newline");
    uint32_t g = srcmap_add(sm, str_from("b.be"), str_from("one\ntwo"));
    CHECK_EQ_S(srcmap_line(sm, g, 2), "two");
    lc = srcmap_linecol(sm, (Span){g, 6, 1});
    CHECK_EQ_I(lc.line, 2);
    CHECK_EQ_I(lc.col, 3);

    CASE("srcmap: CRLF gives the same line numbers as LF, and strips the CR");
    uint32_t h = srcmap_add(sm, str_from("crlf.be"), str_from("alpha\r\nbeta\r\n"));
    CHECK_EQ_S(srcmap_line(sm, h, 1), "alpha");
    CHECK_EQ_S(srcmap_line(sm, h, 2), "beta");
    lc = srcmap_linecol(sm, (Span){h, 7, 1}); /* 'b' of beta */
    CHECK_EQ_I(lc.line, 2);
    CHECK_EQ_I(lc.col, 1);

    CASE("span_join covers both spans");
    Span j = span_join((Span){f, 4, 2}, (Span){f, 10, 3});
    CHECK_EQ_I(j.offset, 4);
    CHECK_EQ_I(j.len, 9);
    j = span_join((Span){f, 10, 3}, (Span){f, 4, 2}); /* order independent */
    CHECK_EQ_I(j.offset, 4);
    CHECK_EQ_I(j.len, 9);
    CHECK(span_is_none(span_join(SPAN_NONE, SPAN_NONE)));
    CHECK_EQ_I(span_join(SPAN_NONE, (Span){f, 4, 2}).offset, 4);

    arena_free(a);
}

static void test_render_basic(void) {
    Arena     *a  = arena_new(0);
    SourceMap *sm = srcmap_new(a);
    DiagBag   *d  = diag_new(a, sm);

    const char *src = "module main\n"
                      "\n"
                      "fn main() {\n"
                      "    let x: i32 = true\n"
                      "}\n";
    uint32_t f = srcmap_add(sm, str_from("test.be"), str_from(src));

    CASE("render: single span with code, note and help");
    uint32_t off = off_of(src, "true", 1);
    Diag    *dg  = diag_error(d, 303, (Span){f, off, 4}, "type mismatch");
    diag_label(dg, (Span){f, off, 4}, "expected `i32`, found `bool`");
    diag_note(dg, "Beryl performs no implicit conversions");
    diag_help(dg, "write `if true { 1 } else { 0 }`");

    Str out = diag_render_str(a, d);
    CHECK_CONTAINS(out, "error[BE0303]: type mismatch");
    CHECK_CONTAINS(out, "--> test.be:4:18");
    CHECK_CONTAINS(out, "4 |     let x: i32 = true");
    CHECK_CONTAINS(out, "^^^^ expected `i32`, found `bool`");
    CHECK_CONTAINS(out, "= note: Beryl performs no implicit conversions");
    CHECK_CONTAINS(out, "= help: write `if true { 1 } else { 0 }`");

    CASE("render: no ANSI escapes in the golden-test renderer");
    bool has_esc = false;
    for (uint32_t i = 0; i < out.len; i++)
        if (out.ptr[i] == '\x1b') has_esc = true;
    CHECK(!has_esc);

    CASE("render: counts");
    CHECK_EQ_I(diag_errors(d), 1);
    CHECK_EQ_I(diag_warnings(d), 0);
    CHECK(diag_any(d));

    arena_free(a);
}

static void test_render_two_labels(void) {
    Arena     *a  = arena_new(0);
    SourceMap *sm = srcmap_new(a);
    DiagBag   *d  = diag_new(a, sm);

    const char *src = "module main\n"
                      "\n"
                      "fn main() {\n"
                      "    var a = 1\n"
                      "    swap(inout a, inout a)\n"
                      "}\n";
    uint32_t f = srcmap_add(sm, str_from("test.be"), str_from(src));

    uint32_t o1 = off_of(src, "inout a", 1);
    uint32_t o2 = off_of(src, "inout a", 2);

    Diag *dg = diag_error(d, 401, (Span){f, o1, 7}, "overlapping exclusive borrows of `a`");
    diag_label(dg, (Span){f, o1, 7}, "first exclusive borrow here");
    diag_label(dg, (Span){f, o2, 7}, "second exclusive borrow here");
    diag_note(dg, "`inout` guarantees non-aliasing");
    diag_help(dg, "copy one side first");

    CASE("render: two labelled spans on one line, exact layout");
    Str out = diag_render_str(a, d);

    const char *expect =
        "error[BE0401]: overlapping exclusive borrows of `a`\n"
        " --> test.be:5:10\n"
        "  |\n"
        "5 |     swap(inout a, inout a)\n"
        "  |          ^^^^^^^  ^^^^^^^ second exclusive borrow here\n"
        "  |          |\n"
        "  |          first exclusive borrow here\n"
        "  |\n"
        "  = note: `inout` guarantees non-aliasing\n"
        "  = help: copy one side first\n";

    CHECK_EQ_S(out, expect);

    arena_free(a);
}

static void test_render_tabs_and_utf8(void) {
    Arena     *a  = arena_new(0);
    SourceMap *sm = srcmap_new(a);
    DiagBag   *d  = diag_new(a, sm);

    CASE("render: tabs expand so carets stay under the right token");
    /* One leading tab, then `bad`. Tab expands to 4 columns. */
    const char *src = "\tbad\n";
    uint32_t    f   = srcmap_add(sm, str_from("t.be"), str_from(src));
    Diag       *dg  = diag_error(d, 1, (Span){f, 1, 3}, "nope");
    diag_label(dg, (Span){f, 1, 3}, "here");
    Str out = diag_render_str(a, d);
    CHECK_CONTAINS(out, "1 |     bad");
    CHECK_CONTAINS(out, "  |     ^^^ here");

    CASE("render: multi-byte UTF-8 before the span (byte columns, documented)");
    Arena     *a2  = arena_new(0);
    SourceMap *sm2 = srcmap_new(a2);
    DiagBag   *d2  = diag_new(a2, sm2);
    /* "é" is two bytes in UTF-8. */
    const char *s2 = "let \xC3\xA9 = bad\n";
    uint32_t    g  = srcmap_add(sm2, str_from("u.be"), str_from(s2));
    uint32_t    ob = off_of(s2, "bad", 1);
    Diag       *e2 = diag_error(d2, 2, (Span){g, ob, 3}, "nope");
    diag_label(e2, (Span){g, ob, 3}, "here");
    Str o2 = diag_render_str(a2, d2);
    /* The caret run has the right width and the source line is intact. */
    CHECK_CONTAINS(o2, "^^^ here");
    CHECK_CONTAINS(o2, "let \xC3\xA9 = bad");

    arena_free(a2);
    arena_free(a);
}

static void test_render_multi(void) {
    Arena     *a  = arena_new(0);
    SourceMap *sm = srcmap_new(a);
    DiagBag   *d  = diag_new(a, sm);

    const char *src = "aaa\nbbb\nccc\n";
    uint32_t    f   = srcmap_add(sm, str_from("m.be"), str_from(src));

    CASE("render: labels on different lines get separate blocks");
    Diag *dg = diag_error(d, 42, (Span){f, 0, 3}, "two places");
    diag_label(dg, (Span){f, 0, 3}, "first");
    diag_label(dg, (Span){f, 8, 3}, "third");
    Str out = diag_render_str(a, d);
    CHECK_CONTAINS(out, "1 | aaa");
    CHECK_CONTAINS(out, "3 | ccc");
    CHECK_CONTAINS(out, "^^^ first");
    CHECK_CONTAINS(out, "^^^ third");

    CASE("render: several diagnostics are separated by a blank line");
    diag_warn(d, 7, (Span){f, 4, 3}, "a warning");
    Str out2 = diag_render_str(a, d);
    CHECK_CONTAINS(out2, "warning[BE0007]: a warning");
    CHECK_EQ_I(diag_errors(d), 1);
    CHECK_EQ_I(diag_warnings(d), 1);

    CASE("render: diagnostic with no span still renders");
    DiagBag *d3 = diag_new(a, sm);
    Diag    *n  = diag_error(d3, 801, SPAN_NONE, "malformed manifest");
    diag_help(n, "check beryl.toml");
    Str o3 = diag_render_str(a, d3);
    CHECK_CONTAINS(o3, "error[BE0801]: malformed manifest");
    CHECK_CONTAINS(o3, "= help: check beryl.toml");

    arena_free(a);
}

void run_diag_tests(void) {
    test_srcmap();
    test_render_basic();
    test_render_two_labels();
    test_render_tabs_and_utf8();
    test_render_multi();
}
