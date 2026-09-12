/* Shared bounded checks for access intervals, after resolution and typing. */
#ifndef BERYL_ACCESS_H
#define BERYL_ACCESS_H
#include "ownership.h"

#define ACCESS_MAX_VISITS 100000u
#define ACCESS_MAX_DEPTH 128u
typedef enum { ACCESS_SAFE, ACCESS_CONFLICT, ACCESS_UNPROVEN } AccessStatus;
typedef struct {
    AccessStatus status;
    Span destination, conflict;
    const char *reason;
} AccessResult;

/* Checks the destination-selection/RHS interval of one assignment. A shared
 * visit counter bounds repeated/nested checks; no ownership state is changed. */
AccessResult access_projected_assignment(const Stmt *statement,uint32_t *visits);
/* Visits all source bodies/default expansions, including unreachable code. */
bool access_check_destinations(DiagBag *diagnostics,Program *program);
#endif
