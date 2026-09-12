/* Checked allocation arithmetic. Failure leaves the output unchanged. */
#ifndef BERYL_CHECKED_SIZE_H
#define BERYL_CHECKED_SIZE_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

static inline bool checked_size_add(size_t a, size_t b, size_t *out) {
    if (b > SIZE_MAX - a) return false;
    *out = a + b;
    return true;
}

static inline bool checked_size_mul(size_t a, size_t b, size_t *out) {
    if (a && b > SIZE_MAX / a) return false;
    *out = a * b;
    return true;
}

static inline bool checked_size_align(size_t n, size_t alignment, size_t *out) {
    size_t sum;
    if (!alignment || (alignment & (alignment - 1)) ||
        !checked_size_add(n, alignment - 1, &sum)) return false;
    *out = sum & ~(alignment - 1);
    return true;
}

/* Geometric growth saturates at a checked element limit, never wraps.
 * A zero need preserves a zero capacity; initial must be nonzero. */
static inline bool checked_size_grow(size_t current, size_t need, size_t limit,
                                     size_t initial, size_t *out) {
    if (!initial || current > limit || need > limit) return false;
    size_t cap = current;
    if (cap < need && !cap) cap = initial < limit ? initial : limit;
    while (cap < need) cap = cap > limit / 2 ? limit : cap * 2;
    *out = cap;
    return true;
}

/* Hash tables use a power-of-two mask, so saturation to a non-power-of-two
 * limit is invalid. Reject the next growth if a full doubling cannot fit. */
static inline bool checked_size_grow_power2(size_t current, size_t initial,
                                            size_t limit, size_t *out) {
    size_t next;
    if (!initial || (initial & (initial - 1)) ||
        (current && (current & (current - 1)))) return false;
    if (current) {
        if (!checked_size_mul(current, 2, &next)) return false;
    } else next = initial;
    if (next > limit) return false;
    *out = next;
    return true;
}

#endif
