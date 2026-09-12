#ifndef BERYL_STORAGE_H
#define BERYL_STORAGE_H

#include "resolve.h"

typedef enum { STORAGE_NATIVE = 0, STORAGE_ENFUSION } StorageTarget;
enum {
    STORAGE_OWNED = 1u << 0,       /* dynamically allocated logical value */
    STORAGE_SHARED = 1u << 1,      /* reference/handle; not an ordinary value copy */
    STORAGE_TARGET_REFERENCE = 1u << 2,
    STORAGE_UNKNOWN = 1u << 3
};
typedef struct {
    uint32_t flags;
    bool logical_copy_supported; /* current emitter, not a cleanup guarantee */
} StorageClass;

/* Bounded, recursive classification of resolved declarations, not spellings.
 * Cycles, unresolved types and resource exhaustion are unknown, never plain. */
StorageClass storage_classify(const Type *type, StorageTarget target);

/* Call after type/ownership checking and before target emission. This is a
 * copy/borrow admission gate. Native List scope-exit cleanup remains incomplete. */
bool storage_admit(DiagBag *d, Program *p, StorageTarget target);

#endif
