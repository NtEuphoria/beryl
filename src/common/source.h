/* source.h — source file registry and byte-span bookkeeping.
 *
 * A Span is (file, byte offset, byte length). Line starts are precomputed once
 * per file so line/column lookup is a binary search rather than a rescan.
 */
#ifndef BERYL_SOURCE_H
#define BERYL_SOURCE_H

#include <stdbool.h>
#include <stdint.h>

#include "arena.h"
#include "str.h"
#include "vec.h"

typedef struct {
    uint32_t file;
    uint32_t offset;
    uint32_t len;
} Span;

#define SPAN_NONE ((Span){UINT32_MAX, 0, 0})

static inline bool span_is_none(Span s) { return s.file == UINT32_MAX; }

typedef VEC(uint32_t) U32Vec;

typedef struct {
    Str      path;
    Str      text;
    uint32_t id;
    U32Vec   line_starts; /* byte offset of the first char of each line */
} SourceFile;

typedef struct SourceMap SourceMap;

typedef struct {
    uint32_t line; /* 1-based */
    uint32_t col;  /* 1-based, counted in bytes */
} LineCol;

SourceMap  *srcmap_new(Arena *a);
uint32_t    srcmap_add(SourceMap *sm, Str path, Str text);
SourceFile *srcmap_get(const SourceMap *sm, uint32_t file);
uint32_t    srcmap_count(const SourceMap *sm);

LineCol srcmap_linecol(const SourceMap *sm, Span s);

/* The text of one line, excluding its newline and any trailing CR. */
Str srcmap_line(const SourceMap *sm, uint32_t file, uint32_t line);

/* Smallest span covering both. Spans in different files return `a`. */
Span span_join(Span a, Span b);

#endif /* BERYL_SOURCE_H */
