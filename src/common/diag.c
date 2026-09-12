#include "diag.h"
#include "json.h"


#include "vec.h"

#define TAB_WIDTH 4

struct DiagBag {
    Arena     *a;
    SourceMap *sm;
    Diag      *head;
    Diag      *tail;
    uint32_t   errors;
    uint32_t   warnings;
};

DiagBag *diag_new(Arena *a, SourceMap *sm) {
    DiagBag *d = ARENA_NEW(a, DiagBag);
    d->a       = a;
    d->sm      = sm;
    return d;
}

static Diag *diag_add(DiagBag *d, DiagLevel lv, uint32_t code, Span at, const char *fmt,
                      va_list ap) {
    Diag *dg    = ARENA_NEW(d->a, Diag);
    dg->level   = lv;
    dg->code    = code;
    dg->primary = at;
    dg->a       = d->a;

    SB sb;
    sb_init(&sb, d->a);
    sb_vfmt(&sb, fmt, ap);
    dg->msg = sb_finish(&sb);

    if (d->tail) d->tail->next = dg;
    else d->head = dg;
    d->tail = dg;

    if (lv == DIAG_ERROR) d->errors++;
    else d->warnings++;
    return dg;
}

Diag *diag_error(DiagBag *d, uint32_t code, Span at, const char *fmt, ...) {
    va_list ap;
    va_start(ap, fmt);
    Diag *dg = diag_add(d, DIAG_ERROR, code, at, fmt, ap);
    va_end(ap);
    return dg;
}

Diag *diag_warn(DiagBag *d, uint32_t code, Span at, const char *fmt, ...) {
    va_list ap;
    va_start(ap, fmt);
    Diag *dg = diag_add(d, DIAG_WARNING, code, at, fmt, ap);
    va_end(ap);
    return dg;
}

static Str vfmt_str(Arena *a, const char *fmt, va_list ap) {
    SB sb;
    sb_init(&sb, a);
    sb_vfmt(&sb, fmt, ap);
    return sb_finish(&sb);
}

void diag_label(Diag *dg, Span at, const char *fmt, ...) {
    DiagLabel *l = ARENA_NEW(dg->a, DiagLabel);
    l->span      = at;
    va_list ap;
    va_start(ap, fmt);
    l->msg = vfmt_str(dg->a, fmt, ap);
    va_end(ap);

    DiagLabel **slot = &dg->labels;
    while (*slot) slot = &(*slot)->next;
    *slot = l;
}

void diag_note(Diag *dg, const char *fmt, ...) {
    va_list ap;
    va_start(ap, fmt);
    dg->note = vfmt_str(dg->a, fmt, ap);
    va_end(ap);
}

void diag_help(Diag *dg, const char *fmt, ...) {
    va_list ap;
    va_start(ap, fmt);
    dg->help = vfmt_str(dg->a, fmt, ap);
    va_end(ap);
}

uint32_t diag_errors(const DiagBag *d) { return d->errors; }
uint32_t diag_warnings(const DiagBag *d) { return d->warnings; }
bool     diag_any(const DiagBag *d) { return d->head != NULL; }
Diag    *diag_first(const DiagBag *d) { return d->head; }

/* ---- rendering --------------------------------------------------------- */

/* Display column after `nbytes` bytes of `line`, expanding tabs. Multi-byte
 * UTF-8 counts as one column per byte in v0.1 (documented limitation). */
static uint32_t disp_width(Str line, uint32_t nbytes) {
    uint32_t c = 0;
    for (uint32_t i = 0; i < nbytes && i < line.len; i++) {
        if (line.ptr[i] == '\t') c += TAB_WIDTH - (c % TAB_WIDTH);
        else c++;
    }
    return c;
}

static void emit_expanded(SB *sb, Str line) {
    uint32_t c = 0;
    for (uint32_t i = 0; i < line.len; i++) {
        if (line.ptr[i] == '\t') {
            uint32_t n = TAB_WIDTH - (c % TAB_WIDTH);
            sb_repeat(sb, ' ', (int)n);
            c += n;
        } else {
            sb_char(sb, line.ptr[i]);
            c++;
        }
    }
}

typedef struct {
    Span     span;
    Str      msg;
    uint32_t line, col; /* 1-based */
} RLabel;

typedef VEC(RLabel) RLabelVec;

static uint32_t digits(uint32_t n) {
    uint32_t d = 1;
    while (n >= 10) {
        n /= 10;
        d++;
    }
    return d;
}

static void gutter_bar(SB *sb, uint32_t gw) {
    sb_repeat(sb, ' ', (int)gw + 1);
    sb_cstr(sb, "|");
}

/* Renders one group of labels that share a file and line. */
static void render_group(SB *sb, const SourceMap *sm, RLabel *labs, uint32_t n,
                         uint32_t gw) {
    uint32_t file = labs[0].span.file;
    uint32_t line = labs[0].line;
    Str      text = srcmap_line(sm, file, line);

    /* source line */
    sb_fmt(sb, "%*u | ", (int)gw, line);
    emit_expanded(sb, text);
    sb_char(sb, '\n');

    /* caret row */
    gutter_bar(sb, gw);
    sb_char(sb, ' ');
    uint32_t cur = 0;
    for (uint32_t i = 0; i < n; i++) {
        uint32_t sb_col = disp_width(text, labs[i].col - 1);
        uint32_t eb_col = disp_width(text, labs[i].col - 1 + labs[i].span.len);
        if (eb_col <= sb_col) eb_col = sb_col + 1;
        if (sb_col < cur) sb_col = cur;
        if (eb_col <= sb_col) eb_col = sb_col + 1;
        sb_repeat(sb, ' ', (int)(sb_col - cur));
        sb_repeat(sb, '^', (int)(eb_col - sb_col));
        cur = eb_col;
    }
    /* The rightmost label's message goes inline on the caret row. */
    bool inline_msg = n > 0 && !str_empty(labs[n - 1].msg);
    if (inline_msg) {
        sb_char(sb, ' ');
        sb_str(sb, labs[n - 1].msg);
    }
    sb_char(sb, '\n');

    /* Remaining labelled spans get connector rows beneath, right to left. */
    uint32_t rem = inline_msg ? n - 1 : n;
    uint32_t with_msg[64];
    uint32_t nm = 0;
    for (uint32_t i = 0; i < rem && nm < 64; i++) {
        if (!str_empty(labs[i].msg)) with_msg[nm++] = i;
    }
    if (nm == 0) return;

    gutter_bar(sb, gw);
    sb_char(sb, ' ');
    cur = 0;
    for (uint32_t k = 0; k < nm; k++) {
        uint32_t c = disp_width(text, labs[with_msg[k]].col - 1);
        if (c < cur) c = cur;
        sb_repeat(sb, ' ', (int)(c - cur));
        sb_char(sb, '|');
        cur = c + 1;
    }
    sb_char(sb, '\n');

    for (int32_t k = (int32_t)nm - 1; k >= 0; k--) {
        gutter_bar(sb, gw);
        sb_char(sb, ' ');
        cur = 0;
        for (int32_t j = 0; j < k; j++) {
            uint32_t c = disp_width(text, labs[with_msg[j]].col - 1);
            if (c < cur) c = cur;
            sb_repeat(sb, ' ', (int)(c - cur));
            sb_char(sb, '|');
            cur = c + 1;
        }
        uint32_t c = disp_width(text, labs[with_msg[k]].col - 1);
        if (c < cur) c = cur;
        sb_repeat(sb, ' ', (int)(c - cur));
        sb_str(sb, labs[with_msg[k]].msg);
        sb_char(sb, '\n');
    }
}

static void render_one(SB *sb, const SourceMap *sm, Arena *a, const Diag *dg) {
    const char *lvl = (dg->level == DIAG_ERROR) ? "error" : "warning";

    if (dg->code) sb_fmt(sb, "%s[BE%04u]: ", lvl, dg->code);
    else sb_fmt(sb, "%s: ", lvl);
    sb_str(sb, dg->msg);
    sb_char(sb, '\n');

    /* Collect labels; fall back to the primary span when none were added. */
    RLabelVec labs = {0};
    for (DiagLabel *l = dg->labels; l; l = l->next) {
        if (span_is_none(l->span)) continue;
        RLabel r = {l->span, l->msg, 0, 0};
        vec_push(a, labs, r);
    }
    if (labs.len == 0 && !span_is_none(dg->primary)) {
        RLabel r = {dg->primary, STR_EMPTY, 0, 0};
        vec_push(a, labs, r);
    }

    if (labs.len == 0) {
        if (!str_empty(dg->note)) {
            sb_cstr(sb, "  = note: ");
            sb_str(sb, dg->note);
            sb_char(sb, '\n');
        }
        if (!str_empty(dg->help)) {
            sb_cstr(sb, "  = help: ");
            sb_str(sb, dg->help);
            sb_char(sb, '\n');
        }
        return;
    }

    for (uint32_t i = 0; i < labs.len; i++) {
        LineCol lc          = srcmap_linecol(sm, labs.data[i].span);
        labs.data[i].line   = lc.line;
        labs.data[i].col    = lc.col;
    }

    /* Insertion sort by (file, line, col) — label counts are tiny. */
    for (uint32_t i = 1; i < labs.len; i++) {
        RLabel   key = labs.data[i];
        uint32_t j   = i;
        while (j > 0) {
            RLabel p = labs.data[j - 1];
            bool   gt = (p.span.file > key.span.file) ||
                      (p.span.file == key.span.file && p.line > key.line) ||
                      (p.span.file == key.span.file && p.line == key.line && p.col > key.col);
            if (!gt) break;
            labs.data[j] = p;
            j--;
        }
        labs.data[j] = key;
    }

    uint32_t maxline = 0;
    for (uint32_t i = 0; i < labs.len; i++)
        if (labs.data[i].line > maxline) maxline = labs.data[i].line;
    uint32_t gw = digits(maxline);

    /* Location line points at the primary span, or the first label. */
    Span        loc = span_is_none(dg->primary) ? labs.data[0].span : dg->primary;
    LineCol     lc  = srcmap_linecol(sm, loc);
    SourceFile *f   = srcmap_get(sm, loc.file);
    sb_repeat(sb, ' ', (int)gw);
    sb_fmt(sb, "--> %.*s:%u:%u\n", f ? (int)f->path.len : 0, f ? f->path.ptr : "", lc.line,
           lc.col);

    gutter_bar(sb, gw);
    sb_char(sb, '\n');

    uint32_t i = 0;
    while (i < labs.len) {
        uint32_t j = i + 1;
        while (j < labs.len && labs.data[j].span.file == labs.data[i].span.file &&
               labs.data[j].line == labs.data[i].line)
            j++;
        render_group(sb, sm, &labs.data[i], j - i, gw);
        i = j;
    }

    if (!str_empty(dg->note)) {
        gutter_bar(sb, gw);
        sb_char(sb, '\n');
        sb_repeat(sb, ' ', (int)gw + 1);
        sb_cstr(sb, "= note: ");
        sb_str(sb, dg->note);
        sb_char(sb, '\n');
    }
    if (!str_empty(dg->help)) {
        if (str_empty(dg->note)) {
            gutter_bar(sb, gw);
            sb_char(sb, '\n');
        }
        sb_repeat(sb, ' ', (int)gw + 1);
        sb_cstr(sb, "= help: ");
        sb_str(sb, dg->help);
        sb_char(sb, '\n');
    }
}

Str diag_render_str(Arena *a, const DiagBag *d) {
    SB sb;
    sb_init(&sb, a);
    for (Diag *dg = d->head; dg; dg = dg->next) {
        render_one(&sb, d->sm, a, dg);
        if (dg->next) sb_char(&sb, '\n');
    }
    return sb_finish(&sb);
}

static void json_span(SB *b, const SourceMap *sm, Span s) {
    SourceFile *file = span_is_none(s) ? NULL : srcmap_get(sm, s.file);
    if (!file) { sb_cstr(b, "null"); return; }
    LineCol lc = srcmap_linecol(sm, s);
    sb_cstr(b, "{\"file\":"); json_string(b, file->path);
    sb_fmt(b, ",\"offset\":%u,\"length\":%u,\"line\":%u,\"column\":%u}",
           s.offset, s.len, lc.line, lc.col);
}

Str diag_render_json(Arena *a, const DiagBag *d) {
    SB b; sb_init(&b, a); sb_char(&b, '[');
    for (Diag *dg = d->head; dg; dg = dg->next) {
        if (dg != d->head) sb_char(&b, ',');
        sb_fmt(&b, "{\"code\":\"BE%04u\",\"level\":\"%s\",\"message\":",
               dg->code, dg->level == DIAG_ERROR ? "error" : "warning");
        json_string(&b, dg->msg);
        sb_cstr(&b, ",\"primary\":"); json_span(&b, d->sm, dg->primary);
        sb_cstr(&b, ",\"related\":[");
        for (DiagLabel *l = dg->labels; l; l = l->next) {
            if (l != dg->labels) sb_char(&b, ',');
            sb_cstr(&b, "{\"span\":"); json_span(&b, d->sm, l->span);
            sb_cstr(&b, ",\"message\":"); json_string(&b, l->msg); sb_char(&b, '}');
        }
        sb_cstr(&b, "],\"note\":"); json_string(&b, dg->note);
        sb_cstr(&b, ",\"help\":"); json_string(&b, dg->help); sb_char(&b, '}');
    }
    sb_char(&b, ']'); return sb_finish(&b);
}

void diag_render(const DiagBag *d, FILE *out, bool color) {
    Str s = diag_render_str(d->a, d);
    if (!color) {
        fwrite(s.ptr, 1, s.len, out);
        return;
    }
    /* Minimal colouring: the header word only, so alignment is unaffected. */
    const char *p   = s.ptr;
    uint32_t    n   = s.len;
    uint32_t    pos = 0;
    while (pos < n) {
        uint32_t eol = pos;
        while (eol < n && p[eol] != '\n') eol++;
        Str  line     = str_new(p + pos, eol - pos);
        bool coloured = true;
        if (str_starts_with(line, "error")) fputs("\x1b[1;31m", out);
        else if (str_starts_with(line, "warning")) fputs("\x1b[1;33m", out);
        else coloured = false;
        fwrite(line.ptr, 1, line.len, out);
        if (coloured) fputs("\x1b[0m", out);
        fputc('\n', out);
        pos = eol + 1;
    }
}
