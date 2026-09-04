/* intrinsic.h — the small set of built-in functions available without import.
 *
 * `print` is deliberate ambient authority, matching EnforceScript's own
 * `Print`. Everything that touches the filesystem, the network or the clock
 * needs a capability value passed in from `main`.
 */
#ifndef BERYL_INTRINSIC_H
#define BERYL_INTRINSIC_H

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
} Intrinsic;

Intrinsic   intrinsic_from_name(Str name);
const char *intrinsic_name(Intrinsic i);

#endif /* BERYL_INTRINSIC_H */
