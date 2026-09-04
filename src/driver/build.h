/* build.h — generate C, invoke clang, optionally run the result. */
#ifndef BERYL_BUILD_H
#define BERYL_BUILD_H

#include "../back/c_backend.h"
#include "../common/diag.h"
#include "../sema/resolve.h"

typedef struct {
    const char *out_exe;   /* where to write the executable */
    const char *cache_dir; /* scratch for generated C; created if absent */
    bool        release;   /* -O2 rather than -O0 -g */
    bool        keep_c;    /* leave the generated C in place for inspection */
    CgenMode    mode;
} BuildOpts;

/* Compiles the program to a native executable. Returns false on failure,
 * having reported why. */
bool build_native(Arena *a, SourceMap *sm, DiagBag *d, Program *p, BuildOpts o);

/* Runs an executable, returning its exit code.
 *
 * Smart App Control on this machine blocks freshly built unsigned binaries
 * non-deterministically, so a blocked launch is detected and the caller is
 * told to rebuild rather than being handed a bogus exit status. See
 * docs/BUILDING.md. */
typedef enum { RUN_OK, RUN_BLOCKED, RUN_FAILED } RunStatus;

RunStatus run_exe(Arena *a, const char *exe, int *exit_code);

/* Builds and runs, rebuilding with a fresh content hash when SAC blocks. */
bool build_and_run(Arena *a, SourceMap *sm, DiagBag *d, Program *p, BuildOpts o,
                   int *exit_code);

#endif /* BERYL_BUILD_H */
