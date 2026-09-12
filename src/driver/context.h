#ifndef BERYL_CONTEXT_H
#define BERYL_CONTEXT_H

#include <stdbool.h>

/* JSON-only, read-only context commands, including capabilities/examples.
 * argv begins with the context topic.
 * No compiler, game, script, or reference program is executed by this API. */
int context_command(int argc, char **argv, const char *compiler_version);

/* Registered research families, not a statement that a transform is released. */
bool context_optimization_family_known(const char *name);

#endif
