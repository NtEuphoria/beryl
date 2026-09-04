/* c_backend.h — emits C11 from the typed AST.
 *
 * Emitting C rather than machine code buys clang's optimizer for free and
 * keeps the compiler small. `inout` parameters become `T *restrict`, backed
 * by the exclusivity guarantee the ownership pass proved.
 */
#ifndef BERYL_C_BACKEND_H
#define BERYL_C_BACKEND_H

#include "../common/diag.h"
#include "../sema/resolve.h"

typedef enum {
    CGEN_PROGRAM, /* a `main` entry point */
    CGEN_TESTS,   /* a generated main that runs every test block */
} CgenMode;

Str cgen_program(Arena *a, SourceMap *sm, DiagBag *d, Program *p, CgenMode mode);

#endif /* BERYL_C_BACKEND_H */
