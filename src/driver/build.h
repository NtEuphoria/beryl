/* Native compilation and execution use isolated jobs and explicit argv. */
#ifndef BERYL_BUILD_H
#define BERYL_BUILD_H
#include "../back/c_backend.h"
#include "../common/diag.h"
#include "../sema/resolve.h"
#include "process.h"
#include "../ir/ir.h"

typedef struct {
    const char *out_exe;   /* optional published output; never executed directly */
    const char *cache_dir; /* parent of isolated job directories */
    const char *clang;     /* native executable, no shell fragment */
    uint32_t timeout_ms;
    bool release;
    bool save_native_evidence;
    const char *requested_lowering; /* explicit ir is admitted for differential tests only */
    const IrProgram *ir_tests; /* pre-admitted immutable test IR; no production ABI */
    const char *optimization_policy; /* auto/off; no family is released yet */
    Str disabled_optimizations_json;
    CgenMode mode;
    CgenTraceWatch trace_watch; /* bounded test-only observed output root */
} BuildOpts;
typedef struct {
    const char *job_dir;
    const char *exe;
    const char *c_source;
    ProcessResult compile;
    ProcessResult run;
    ProcessResult compiler_identity;
    ProcessResult compiler_evidence;
    bool identity_attempted;
    bool evidence_attempted;
    bool executed;
    const char *native_evidence_path;
    const char *selected_lowering;
    Str sources_json, source_fingerprint, compiler_fingerprint, executable_fingerprint;
} BuildResult;

bool build_native(Arena *a, SourceMap *sm, DiagBag *d, Program *p,
                  BuildOpts opts, BuildResult *result);
bool build_and_run(Arena *a, SourceMap *sm, DiagBag *d, Program *p,
                   BuildOpts opts, BuildResult *result, int *exit_code);
#endif
