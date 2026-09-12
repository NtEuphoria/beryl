/* diag.h — diagnostics with caret spans, stable codes, notes and helps.
 *
 * Every error carries a BE#### code documented in docs/DIAGNOSTICS.md. The
 * renderer is deliberately held to a rustc-grade bar: multiple labelled spans
 * on one line, tab-aware column alignment, and a note/help footer.
 */
#ifndef BERYL_DIAG_H
#define BERYL_DIAG_H

#include <stdarg.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>

#include "arena.h"
#include "source.h"
#include "str.h"

typedef enum { DIAG_ERROR, DIAG_WARNING } DiagLevel;

typedef struct DiagLabel {
    Span              span;
    Str               msg;
    struct DiagLabel *next;
} DiagLabel;

typedef struct Diag {
    DiagLevel    level;
    uint32_t     code; /* 0 means no code */
    Str          msg;
    Span         primary;
    DiagLabel   *labels;
    Str          note;
    Str          help;
    Arena       *a; /* for label/note formatting */
    struct Diag *next;
} Diag;

typedef struct DiagBag DiagBag;

DiagBag *diag_new(Arena *a, SourceMap *sm);

Diag *diag_error(DiagBag *d, uint32_t code, Span at, const char *fmt, ...) BE_PRINTF(4, 5);
Diag *diag_warn(DiagBag *d, uint32_t code, Span at, const char *fmt, ...) BE_PRINTF(4, 5);

/* Adds a caret span with a message. Labels render in insertion order, sorted
 * by position within a line. If a diagnostic has no labels, carets are drawn
 * on the primary span with no message. */
void diag_label(Diag *dg, Span at, const char *fmt, ...) BE_PRINTF(3, 4);
void diag_note(Diag *dg, const char *fmt, ...) BE_PRINTF(2, 3);
void diag_help(Diag *dg, const char *fmt, ...) BE_PRINTF(2, 3);

uint32_t diag_errors(const DiagBag *d);
uint32_t diag_warnings(const DiagBag *d);
bool     diag_any(const DiagBag *d);
Diag    *diag_first(const DiagBag *d);

void diag_render(const DiagBag *d, FILE *out, bool color);
Str  diag_render_str(Arena *a, const DiagBag *d); /* for golden tests; never coloured */
Str  diag_render_json(Arena *a, const DiagBag *d); /* JSON array, byte-based locations */

#endif /* BERYL_DIAG_H */
