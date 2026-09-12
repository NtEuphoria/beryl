/* manifest.h — beryl.toml.
 *
 * A deliberately small reader for the subset the spec defines, not a general
 * TOML parser. There is no way for a manifest to run code, which is the whole
 * point of not having build scripts.
 */
#ifndef BERYL_MANIFEST_H
#define BERYL_MANIFEST_H

#include "../common/diag.h"
#include "../common/str.h"

typedef struct {
    bool found;
    Str source_text; /* exact bytes loaded, for operation fingerprints */

    Str name;
    Str version;

    /* [target.enfusion] */
    Str enfusion_prefix;
    Str enfusion_out;

    /* [security] */
    bool forbid_unsafe;
} Manifest;

/* Reads `beryl.toml` from `dir`. A missing file is not an error; `found` is
 * false and every field keeps its default. */
Manifest manifest_load(Arena *a, DiagBag *d, const char *dir);

/* Lists `*.be` under `dir`, sorted, so a package builds deterministically. */
typedef VEC(Str) PathVec;
PathVec list_beryl_files(Arena *a, const char *dir);

#endif /* BERYL_MANIFEST_H */
