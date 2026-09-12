#ifndef BERYL_JSON_READ_H
#define BERYL_JSON_READ_H
#include "str.h"

typedef enum { JR_NULL, JR_BOOL, JR_NUMBER, JR_STRING, JR_ARRAY, JR_OBJECT } JsonKind;
typedef struct JsonValue {
    JsonKind kind;
    uint32_t offset, length, count;
    Str name, text; /* decoded member name; decoded string or exact number token */
    bool boolean;
    struct JsonValue *child, *next;
} JsonValue;
typedef struct {
    uint32_t bytes, nodes, depth, string_bytes, work;
} JsonLimits;
typedef struct {
    const char *message; /* NULL on success; syntax or resource error */
    uint32_t offset;
    bool limit;
} JsonReadError;

/* Strict UTF-8 JSON. No BOM, duplicate decoded keys, or trailing input.
 * Unknown members are a schema responsibility. Results live in the arena.
 * Input and configured limits must outlive only this call. Depth counts the
 * root as one; work includes scanning and duplicate-key comparisons. */
JsonLimits json_read_limits(void);
JsonValue *json_read(Arena *a, Str input, JsonLimits limits, JsonReadError *error);
JsonValue *json_member(const JsonValue *object, const char *name);
bool json_u64(const JsonValue *value, uint64_t maximum, uint64_t *out);
bool json_utf8(Str input, uint32_t *bad_offset);
#endif
