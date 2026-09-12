#ifndef BERYL_BINDING_CONTEXT_H
#define BERYL_BINDING_CONTEXT_H
#include "../common/str.h"
typedef struct {
    const char *status;
    Str fingerprint;
    Str data;
} BindingContext;
/* Read-only lookup; optional paths verify the selected snapshot's exact bytes.
 * No engine or project code runs and no contract is inferred from a signature. */
BindingContext binding_context(Arena *a, const char *query,
                               const char *engine_executable, const char *api_root);
#endif
