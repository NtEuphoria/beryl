#ifndef BERYL_HASH_H
#define BERYL_HASH_H
#include "str.h"
/* SHA-256 identifies exact bytes; never used as a substitute for validation. */
typedef struct { uint32_t h[8]; uint64_t bytes; unsigned used; unsigned char block[64]; } Hash256;
void hash256_init(Hash256 *h);
void hash256_update(Hash256 *h, const void *data, size_t len);
Str hash256_finish(Arena *a, Hash256 *h);
Str hash256_str(Arena *a, Str data);
#endif
