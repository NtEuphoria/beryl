#include "vec.h"
#include "checked_size.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static _Noreturn void vec_failure(void) {
    fputs("beryl: invalid or overflowing compiler vector capacity\n", stderr);
    abort();
}

uint32_t vec_push_need_(uint32_t len, uint32_t cap) {
    if (len > cap || len == UINT32_MAX) vec_failure();
    return len + 1;
}

void vec_reserve_(Arena *a, void **data, uint32_t *cap, size_t need, uint32_t live,
                  size_t elem) {
    if (!elem || live > *cap || (*cap && !*data)) vec_failure();
    size_t limit = SIZE_MAX / elem;
    if (limit > UINT32_MAX) limit = UINT32_MAX;
    size_t ncap, bytes, live_bytes;
    if (!checked_size_grow(*cap, need, limit, 8, &ncap) ||
        !checked_size_mul(ncap, elem, &bytes) ||
        !checked_size_mul(live, elem, &live_bytes)) vec_failure();
    if (need <= *cap) return;
    void *nd = arena_alloc(a, bytes, 16);
    if (live_bytes) memcpy(nd, *data, live_bytes);
    *data = nd;
    *cap  = (uint32_t)ncap;
}
