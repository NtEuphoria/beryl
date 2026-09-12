#ifndef BERYL_ANALYZE_H
#define BERYL_ANALYZE_H
#include "../common/diag.h"

#define ANALYZE_MAX_FILES 64u
#define ANALYZE_MAX_FILE_BYTES 1048576u
#define ANALYZE_MAX_TOTAL_BYTES 8388608u
#define ANALYZE_MAX_TOKENS 262144u
#define ANALYZE_MAX_VERSION UINT64_C(9007199254740991)

typedef enum { ANALYZE_NATIVE, ANALYZE_ENFUSION, ANALYZE_REFERENCE } AnalyzeTarget;
typedef struct {
    Str path, text, sha256;
    uint64_t document_version;
} AnalyzeSource;
typedef struct {
    Str request_id, request_fingerprint, expected_compiler_sha256;
    uint64_t snapshot_version;
    AnalyzeTarget target;
    bool forbid_unsafe;
    AnalyzeSource *sources;
    uint32_t source_count;
} AnalyzeSnapshot;
typedef struct {
    Str json;
    const char *status, *stage;
    int exit_code;
    Str identity_fragment; /* internal JSON member fragment for stale rejection */
} AnalyzeResult;

/* Exact bytes only: no discovery, imports from disk, build or execution. This
 * one-shot API retains all analysis data in `arena`; callers own that lifetime.
 * The same validation applies to direct C snapshots and the JSON front end. */
AnalyzeResult analyze_snapshot(Arena *arena, const AnalyzeSnapshot *snapshot,
                               const char *compiler_version);
/* Reader callbacks return adjacent immutable content files, never logical
 * source paths. No callback is called until the complete request schema passes.
 * A successful reader must supply bytes <= ANALYZE_MAX_FILE_BYTES. */
typedef bool (*AnalyzeRead)(void *user, Arena *arena, Str content_file, Str *bytes);
AnalyzeResult analyze_request(Arena *arena, Str request, AnalyzeRead reader,
                              void *user, const char *compiler_version);
int analyze_command(int argc, char **argv, const char *compiler_version);
#endif
