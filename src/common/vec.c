#include "vec.h"

#include <string.h>

void vec_reserve_(Arena *a, void **data, uint32_t *cap, uint32_t need, uint32_t live,
                  size_t elem) {
    if (need <= *cap) return;
    uint32_t ncap = *cap ? *cap * 2 : 8;
    while (ncap < need) ncap *= 2;
    void *nd = arena_alloc(a, (size_t)ncap * elem, 16);
    if (live && *data) memcpy(nd, *data, (size_t)live * elem);
    *data = nd;
    *cap  = ncap;
}
