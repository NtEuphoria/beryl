#include "source.h"

struct SourceMap {
    Arena *a;
    VEC(SourceFile) files;
};

SourceMap *srcmap_new(Arena *a) {
    SourceMap *sm = ARENA_NEW(a, SourceMap);
    sm->a         = a;
    return sm;
}

uint32_t srcmap_add(SourceMap *sm, Str path, Str text) {
    SourceFile f = {0};
    f.path       = path;
    f.text       = text;
    f.id         = sm->files.len;

    /* Line 1 starts at offset 0; each '\n' opens the next line. */
    vec_push(sm->a, f.line_starts, 0u);
    for (uint32_t i = 0; i < text.len; i++) {
        if (text.ptr[i] == '\n') vec_push(sm->a, f.line_starts, i + 1);
    }

    vec_push(sm->a, sm->files, f);
    return f.id;
}

SourceFile *srcmap_get(const SourceMap *sm, uint32_t file) {
    if (file >= sm->files.len) return NULL;
    return &sm->files.data[file];
}

uint32_t srcmap_count(const SourceMap *sm) { return sm->files.len; }

LineCol srcmap_linecol(const SourceMap *sm, Span s) {
    LineCol lc = {1, 1};
    if (span_is_none(s)) return lc;
    SourceFile *f = srcmap_get(sm, s.file);
    if (!f) return lc;

    uint32_t off = s.offset;
    if (off > f->text.len) off = f->text.len;

    /* Largest index with line_starts[i] <= off. */
    uint32_t lo = 0, hi = f->line_starts.len - 1;
    while (lo < hi) {
        uint32_t mid = lo + (hi - lo + 1) / 2;
        if (f->line_starts.data[mid] <= off) lo = mid;
        else hi = mid - 1;
    }
    lc.line = lo + 1;
    lc.col  = off - f->line_starts.data[lo] + 1;
    return lc;
}

Str srcmap_line(const SourceMap *sm, uint32_t file, uint32_t line) {
    SourceFile *f = srcmap_get(sm, file);
    if (!f || line == 0 || line > f->line_starts.len) return STR_EMPTY;

    uint32_t start = f->line_starts.data[line - 1];
    uint32_t end   = (line < f->line_starts.len) ? f->line_starts.data[line] : f->text.len;

    if (end > start && f->text.ptr[end - 1] == '\n') end--;
    if (end > start && f->text.ptr[end - 1] == '\r') end--;

    return str_new(f->text.ptr + start, end - start);
}

Span span_join(Span a, Span b) {
    if (span_is_none(a)) return b;
    if (span_is_none(b)) return a;
    if (a.file != b.file) return a;

    uint32_t start = a.offset < b.offset ? a.offset : b.offset;
    uint32_t ae = a.offset + a.len, be = b.offset + b.len;
    uint32_t end = ae > be ? ae : be;
    return (Span){a.file, start, end - start};
}
