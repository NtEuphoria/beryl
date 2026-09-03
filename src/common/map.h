/* map.h — open-addressing hash map from Str to void*.
 *
 * No deletion, therefore no tombstones: the compiler never removes a binding
 * from a scope, it discards the whole scope.
 */
#ifndef BERYL_MAP_H
#define BERYL_MAP_H

#include <stdbool.h>
#include <stdint.h>

#include "arena.h"
#include "str.h"

typedef struct Map Map;

typedef struct {
    Str   key;
    void *val;
} MapEntry;

Map     *map_new(Arena *a);
void     map_put(Map *m, Str key, void *val);
void    *map_get(const Map *m, Str key);
bool     map_has(const Map *m, Str key);
uint32_t map_len(const Map *m);

/* Iteration. Start with cursor = 0; returns false when exhausted.
 *
 *   uint32_t c = 0; MapEntry e;
 *   while (map_next(m, &c, &e)) { ... }
 */
bool map_next(const Map *m, uint32_t *cursor, MapEntry *out);

#endif /* BERYL_MAP_H */
