/* ownership.h — mutable value semantics, enforced.
 *
 * Beryl has no lifetime annotations because references are second-class: a
 * borrow cannot be stored in a struct, returned, or placed in a container, so
 * it can never outlive the call it was passed to. That leaves three things to
 * check, and all three are ordinary flow analysis over structured control
 * flow rather than a borrow checker over a CFG:
 *
 *   definite initialization — every read sees an initialized binding
 *   moves                   — a `sink` argument consumes its source
 *   exclusivity             — no two overlapping accesses when one is `inout`
 *                             and projected destinations survive selection/RHS
 *
 * `restrict` is emitted only for functions whose exclusive arguments are proven
 * local paths at every call. Native storage admission rejects shared list
 * buffers, which is what makes those paths name distinct allocations.
 */
#ifndef BERYL_OWNERSHIP_H
#define BERYL_OWNERSHIP_H

#include "../common/diag.h"
#include "resolve.h"

bool ownership_check(DiagBag *d, Program *p);

#endif /* BERYL_OWNERSHIP_H */
