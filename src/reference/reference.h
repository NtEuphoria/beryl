/* Bounded AST reference execution. Independent of code generation/runtime math. */
#ifndef BERYL_REFERENCE_H
#define BERYL_REFERENCE_H
#include "../sema/resolve.h"
#include <stdio.h>

typedef enum { REF_SUCCESS, REF_FAILED, REF_UNAVAILABLE, REF_TRAP, REF_BUDGET, REF_IO, REF_TIMEOUT, REF_CANCELLED } RefStatus;
/* Only source failures implemented by both admitted execution paths qualify.
 * Interpreter limits, unsupported numeric domains and internal errors do not. */
typedef enum { REF_SOURCE_TRAP_NONE, REF_SOURCE_TRAP_OVERFLOW,
    REF_SOURCE_TRAP_DIV_ZERO, REF_SOURCE_TRAP_BOUNDS } RefTrapKind;
typedef struct {
    bool enabled;
    RefTrapKind kind;
    uint32_t file, offset; /* loaded source identity and zero-based byte offset */
} RefExpectedTrap;
typedef struct { bool enabled; uint32_t file, offset; } RefWatchRoot;
typedef struct {
    uint64_t max_steps;       /* default 1,000,000 */
    uint64_t max_bytes;       /* cumulative evaluation allocations; default 64 MiB */
    uint32_t max_call_depth;  /* default 128 */
    FILE *output;
    FILE *events;            /* optional ordered test/observable event stream */
    bool (*cancelled)(void);
    uint64_t (*clock_ms)(void);
    uint32_t timeout_ms;
    RefExpectedTrap expected_trap; /* verification only; does not make a trap return */
    RefWatchRoot watch_root; /* one initialized top-level test-local i32 array */
} RefOpts;
typedef struct {
    RefStatus status;
    uint64_t steps, bytes, assertions;
    uint32_t tests, failed_tests;
    RefTrapKind trap_kind;
    Span trap_span;
    bool trap_trace_complete;
} RefResult;

bool reference_admit(DiagBag *d, Program *p);
RefResult reference_test(DiagBag *d, Program *p, RefOpts opts);
const char *reference_status_name(RefStatus status);
const char *reference_trap_kind_name(RefTrapKind kind);
#endif
