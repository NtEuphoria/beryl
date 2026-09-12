#ifndef BERYL_FEATURES_H
#define BERYL_FEATURES_H

#include "../common/str.h"
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

/* Compiler-owned inventory, not a record of local execution or a replacement
 * for the target admission passes. All serialized identities are text. */
enum {
    FEATURE_NATIVE = 1, FEATURE_REFERENCE = 2, FEATURE_ENFUSION = 4,
    FEATURE_COMPILER = 8, FEATURE_TOOLING = 16, FEATURE_ALL = 31
};
typedef enum {
    FEATURE_UNAVAILABLE, FEATURE_EXPERIMENTAL, FEATURE_PARTIAL, FEATURE_BOUNDED
} FeatureState;

#define FEATURE_MAX_LINKS 8
typedef struct {
    const char *id, *title;
    FeatureState state;
    uint32_t targets;
    const char *interface_name, *bounds, *admission, *source;
    const char *dependencies[FEATURE_MAX_LINKS];
    const char *test_groups[FEATURE_MAX_LINKS];
} Feature;
typedef struct {
    const char *id, *source, *positive, *negative;
} FeatureTestGroup;
typedef struct {
    const char *id, *title;
    uint32_t targets;
    const char *sources[FEATURE_MAX_LINKS];
    const char *features[FEATURE_MAX_LINKS];
    const char *test_groups[FEATURE_MAX_LINKS];
    const char *usage, *bounds;
} FeatureExample;
typedef struct {
    const char *name, *hypothesis, *requires;
} OptimizationFamily;
typedef struct {
    const Feature *features; size_t feature_count;
    const FeatureTestGroup *tests; size_t test_count;
    const FeatureExample *examples; size_t example_count;
    const OptimizationFamily *families; size_t family_count;
} FeatureRegistry;
typedef struct { const char *kind, *id; } FeatureIssue;

const FeatureRegistry *features_registry(void);
bool features_validate(const FeatureRegistry *r, FeatureIssue *issue);
const Feature *features_find(const FeatureRegistry *r, const char *id);
const FeatureExample *features_example_find(const FeatureRegistry *r, const char *id);
const char *features_state_name(FeatureState state);
uint32_t features_target(const char *name); /* zero for an unknown target */
bool features_family_known(const char *name);
Str features_fingerprint(Arena *a);
Str features_catalog_json(Arena *a, const char *id, uint32_t targets);
Str features_examples_json(Arena *a, const char *id, uint32_t targets);
Str features_families_json(Arena *a); /* preserves context v1 family shape */

#endif
