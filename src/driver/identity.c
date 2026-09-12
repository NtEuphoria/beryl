#include "identity.h"
#include "../common/fs.h"
#include "../common/hash.h"
#include "../common/json.h"

Str identity_sources(Arena *a, const SourceMap *sm) {
    SB b; sb_init(&b, a); sb_char(&b, '[');
    for (uint32_t i = 0; i < srcmap_count(sm); i++) {
        SourceFile *f = srcmap_get(sm, i);
        if (i) sb_char(&b, ',');
        sb_cstr(&b, "{\"path\":"); json_string(&b, f->path);
        sb_cstr(&b, ",\"sha256\":"); json_string(&b, hash256_str(a, f->text)); sb_char(&b, '}');
    }
    sb_char(&b, ']'); return sb_finish(&b);
}
Str identity_compiler(Arena *a) {
    const char *path = fs_executable(a);
    Str bytes;
    return path && fs_read(a, path, &bytes) ? hash256_str(a, bytes) : STR_EMPTY;
}
