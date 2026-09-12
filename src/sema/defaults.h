#ifndef BERYL_DEFAULTS_H
#define BERYL_DEFAULTS_H
#include "check.h"

/* Validate templates after checking, then insert fresh, resolved expression
 * occurrences before ownership, taint, target lint and either backend. */
bool expand_defaults(DiagBag *d, Program *p);
#endif
