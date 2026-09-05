/* intrinsic.h — the small set of built-in functions available without import.
 *
 * `print` is deliberate ambient authority, matching EnforceScript's own
 * `Print`. Everything that touches the filesystem, the network or the clock
 * needs a capability value passed in from `main`.
 */
#ifndef BERYL_INTRINSIC_H
#define BERYL_INTRINSIC_H

#include <stdbool.h>

#include "../common/str.h"

typedef enum {
    INTR_NONE = 0,
    INTR_PRINT,
    INTR_PRINTLN,
    INTR_ASSERT,
    INTR_MIN,
    INTR_MAX,
    INTR_ABS,
    INTR_CLAMP,
    INTR_SQRT,

    /* Methods on the built-in containers. These are intrinsic rather than
     * library code because each backend already has a native answer: a
     * dynamic array natively, and the engine's own `array<T>` on Enfusion,
     * which no reimplementation could match for size or speed. */
    INTR_LIST_LEN = 64,
    INTR_LIST_PUSH,
    INTR_LIST_GET,
    INTR_LIST_SET,
    INTR_LIST_CLEAR,

    /* Explicit opt-outs from the overflow trap. Checked arithmetic costs
     * roughly 2x in a dependent multiply-add chain (docs/BENCHMARKS.md), and
     * these are how a hot loop opts out without reaching for @unsafe. */
    INTR_WRAPPING_ADD = 96,
    INTR_WRAPPING_SUB,
    INTR_WRAPPING_MUL,
    INTR_SATURATING_ADD,
    INTR_SATURATING_SUB,

    /* Methods on Vec2/3/4. Intrinsic for the same reason the container
     * methods are: the Enfusion target has these on its own `vector`, and a
     * reimplementation in Beryl would be slower and would not match. */
    INTR_VEC_LENGTH = 128,
    INTR_VEC_LENGTH_SQ,
    INTR_VEC_DOT,
    INTR_VEC_DISTANCE,
    INTR_VEC_NORMALIZED,
    INTR_VEC_CROSS,

    /* `Vec3(x, y, z)`. A call on a type name rather than a struct literal,
     * because a vector's components are positional everywhere else in
     * graphics and `Vec3{ x: 1, y: 2, z: 3 }` reads badly in arithmetic. */
    INTR_VEC2_NEW = 144,
    INTR_VEC3_NEW,
    INTR_VEC4_NEW,
} Intrinsic;

Intrinsic   intrinsic_from_name(Str name);
const char *intrinsic_name(Intrinsic i);

/* Resolves a method name on `List<T>`, or INTR_NONE. */
Intrinsic intrinsic_list_method(Str name);

/* Resolves a method name on `Vec2`/`Vec3`/`Vec4`, or INTR_NONE. Arity is not
 * consulted here; `cross` is rejected on Vec2/Vec4 by the checker, which can
 * say which type it found. */
Intrinsic intrinsic_vec_method(Str name);

static inline bool intrinsic_is_list_method(Intrinsic i) {
    return i >= INTR_LIST_LEN && i <= INTR_LIST_CLEAR;
}
static inline bool intrinsic_is_wrapping(Intrinsic i) {
    return i >= INTR_WRAPPING_ADD && i <= INTR_SATURATING_SUB;
}
static inline bool intrinsic_is_vec_method(Intrinsic i) {
    return i >= INTR_VEC_LENGTH && i <= INTR_VEC_CROSS;
}
static inline bool intrinsic_is_vec_new(Intrinsic i) {
    return i >= INTR_VEC2_NEW && i <= INTR_VEC4_NEW;
}

#endif /* BERYL_INTRINSIC_H */
