#ifndef BERYL_IR_C_EMIT_H
#define BERYL_IR_C_EMIT_H
#include "ir.h"
/* Private schema-4 test harness emitter. No production entry point or CLI route.
 * Callers must compile with binary32 semantics, contraction/fast-math disabled.
 * Output is empty on invalid IR, unsupported configuration or output budget. */
typedef struct { bool trace_tests; uint32_t max_output_bytes; } IrCOpts;
typedef struct { bool ok; Str source; Span error; const char *reason; } IrCResult;
IrCResult ir_emit_c(Arena *arena, const IrProgram *program, IrCOpts options);
#endif
