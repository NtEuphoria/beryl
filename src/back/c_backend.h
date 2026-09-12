/* c_backend.h — emits C11 from the typed AST.
 *
 * Emitting C rather than machine code buys clang's optimizer for free and
 * keeps the compiler small. `inout` parameters become `T *`. Restrict remains
 * disabled until ownership tracks storage identity through collection copies.
 */
#ifndef BERYL_C_BACKEND_H
#define BERYL_C_BACKEND_H

#include "../common/diag.h"
#include "../sema/resolve.h"

typedef enum {
    CGEN_PROGRAM, /* a `main` entry point */
    CGEN_TESTS,   /* a generated main that runs every test block */
    CGEN_TRACE_TESTS, /* test harness plus ordered events on stderr */
} CgenMode;
typedef struct { bool enabled; uint32_t file, offset; } CgenTraceWatch;

Str cgen_program(Arena *a, SourceMap *sm, DiagBag *d, Program *p, CgenMode mode);
Str cgen_program_watched(Arena *a, SourceMap *sm, DiagBag *d, Program *p,
                        CgenMode mode, CgenTraceWatch watch);
bool native_lint(DiagBag *d, Arena *a, Program *p);

#endif /* BERYL_C_BACKEND_H */
