/* vec.h — macro-based dynamic array over an arena.
 *
 * Growth copies the live elements into a fresh arena allocation; the old one
 * is simply abandoned. That is deliberate: arenas make abandonment free, and
 * it keeps the whole implementation to one function.
 *
 * Strict C11 — no `typeof`. Element alignment is a conservative 16, which
 * satisfies every scalar and aggregate the compiler stores in a vector.
 */
#ifndef BERYL_VEC_H
#define BERYL_VEC_H

#include <stddef.h>
#include <stdint.h>

#include "arena.h"

#define VEC(T)                                                                             \
    struct {                                                                               \
        T       *data;                                                                     \
        uint32_t len;                                                                      \
        uint32_t cap;                                                                      \
    }

/* Grows *data to hold at least `need` elements, copying `live` of them. */
void vec_reserve_(Arena *a, void **data, uint32_t *cap, uint32_t need, uint32_t live,
                  size_t elem);

#define vec_reserve(A, V, N)                                                               \
    vec_reserve_((A), (void **)&(V).data, &(V).cap, (N), (V).len, sizeof(*(V).data))

#define vec_push(A, V, X)                                                                  \
    do {                                                                                   \
        if ((V).len == (V).cap) vec_reserve((A), (V), (V).len + 1);                        \
        (V).data[(V).len++] = (X);                                                         \
    } while (0)

#define vec_at(V, I)      ((V).data[(I)])
#define vec_last(V)       ((V).data[(V).len - 1])
#define vec_pop(V)        ((V).data[--(V).len])
#define vec_clear(V)      ((V).len = 0)
#define vec_empty(V)      ((V).len == 0)
#define vec_foreach(I, V) for (uint32_t I = 0; I < (V).len; I++)

#endif /* BERYL_VEC_H */
