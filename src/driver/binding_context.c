#include "binding_context.h"
#include "../common/fs.h"
#include "../common/hash.h"
#include "../common/json.h"
#include <string.h>

typedef struct { const char *name, *owner, *document, *document_hash, *json; } BindingRow;
#include "binding_registry.inc"

static void quoted(SB *b, const char *s) { json_string(b, str_from(s)); }

/* Stream engine identity without allocating the executable in the arena.
 * Bounds apply before every update, including a file that grows while read. */
static Str file_hash(Arena *a, const char *path, uint64_t limit) {
    FILE *file = fs_open(path, "rb");
    if (!file) return STR_EMPTY;
    Hash256 hash; hash256_init(&hash);
    unsigned char bytes[16384]; size_t n; uint64_t total = 0;
    bool ok = true;
    while ((n = fread(bytes, 1, sizeof bytes, file)) != 0) {
        if (total > limit || n > limit - total) { ok = false; break; }
        hash256_update(&hash, bytes, n); total += n;
    }
    if (ferror(file) || !total) ok = false;
    if (fclose(file)) ok = false;
    return ok ? hash256_finish(a, &hash) : STR_EMPTY;
}

static const char *match_status(Str actual, const char *expected) {
    return !actual.len ? "unavailable" : str_eq_c(actual, expected) ? "match" : "mismatch";
}

BindingContext binding_context(Arena *a, const char *query,
                               const char *engine_executable, const char *api_root) {
    SB b; sb_init(&b, a); uint32_t count = 0;
    const BindingRow *first = NULL;
    for (size_t i = 0; i < sizeof registry_rows / sizeof registry_rows[0]; i++) {
        const BindingRow *row = &registry_rows[i];
        if (!strcmp(query, row->name) || !strcmp(query, row->owner)) { count++; first = row; }
    }
    Str engine_hash = STR_EMPTY, document_hash = STR_EMPTY;
    const char *engine_status = "not_checked", *document_status = "not_checked";
    if (engine_executable) {
        engine_hash = file_hash(a, engine_executable, 1024ULL * 1024 * 1024);
        engine_status = match_status(engine_hash, registry_engine_sha256);
    }
    if (api_root && first) {
        document_hash = file_hash(a, fs_join(a, api_root, first->document), 8ULL * 1024 * 1024);
        document_status = match_status(document_hash, first->document_hash);
    }
    bool stale = !strcmp(engine_status, "mismatch") || !strcmp(document_status, "mismatch");
    bool unavailable = !count || !strcmp(engine_status, "unavailable") || !strcmp(document_status, "unavailable");
    const char *status = stale ? "stale_input" : unavailable ? "unavailable" : "success";
    sb_cstr(&b, "{\"name\":"); quoted(&b, query);
    sb_cstr(&b, ",\"registry\":{\"status\":\"snapshot_available\",\"scope\":\"selected installed EnfusionScriptAPI declarations\",\"engine_version\":");
    quoted(&b, registry_engine_version);
    sb_cstr(&b, ",\"engine_sha256\":"); quoted(&b, registry_engine_sha256);
    sb_fmt(&b, ",\"declaration_count\":%zu}", sizeof registry_rows / sizeof registry_rows[0]);
    sb_cstr(&b, ",\"applicability\":{\"engine\":"); quoted(&b, engine_status);
    sb_cstr(&b, ",\"document\":"); quoted(&b, document_status);
    sb_cstr(&b, ",\"engine_sha256_read\":");
    if (engine_hash.len) json_string(&b, engine_hash); else sb_cstr(&b, "null");
    sb_cstr(&b, ",\"document_sha256_read\":");
    if (document_hash.len) json_string(&b, document_hash); else sb_cstr(&b, "null");
    sb_cstr(&b, ",\"loaded_session\":\"not_checked\",\"engine_dependencies\":\"not_checked\"},\"extracted_declaration\":{\"status\":");
    quoted(&b, count ? "snapshot_available" : "unavailable");
    sb_cstr(&b, ",\"declarations\":["); bool comma = false;
    for (size_t i = 0; i < sizeof registry_rows / sizeof registry_rows[0]; i++) {
        const BindingRow *row = &registry_rows[i];
        if (strcmp(query, row->name) && strcmp(query, row->owner)) continue;
        if (comma) sb_char(&b, ','); comma = true; sb_cstr(&b, row->json);
    }
    sb_cstr(&b, "]},\"verified_contract\":{\"status\":\"unavailable\",\"engine_version\":null,\"signature_execution\":\"not_run\",\"effects\":null,\"retention\":null,\"authority\":null,\"reason\":\"Extracted declarations do not establish tested signatures, allocation, retention, ordering, or authority contracts.\"},\"guidance\":\"Use --engine-executable and --api-root to check this snapshot against selected local files. Matching files do not verify a loaded engine session or its dependencies. Unknown declarations require extraction and review; do not infer an API.\"}");
    return (BindingContext){status, str_from(registry_sha256), sb_finish(&b)};
}
