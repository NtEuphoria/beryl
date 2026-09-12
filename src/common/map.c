#include "map.h"
#include "checked_size.h"

#include <stdio.h>
#include <stdlib.h>

typedef struct {
    Str      key;
    void    *val;
    uint64_t hash;
} Slot;

struct Map {
    Arena   *a;
    Slot    *slots;
    uint32_t cap; /* power of two */
    uint32_t len;
};

static void map_grow(Map *m) {
    size_t limit = SIZE_MAX / sizeof(Slot), next;
    if (limit > UINT32_MAX) limit = UINT32_MAX;
    if (!checked_size_grow_power2(m->cap, 64, limit, &next)) {
        fputs("beryl: compiler map capacity limit exceeded\n", stderr);
        abort();
    }
    uint32_t ncap = (uint32_t)next;
    Slot    *nslots = ARENA_ARRAY(m->a, Slot, ncap);
    for (uint32_t i = 0; i < m->cap; i++) {
        Slot s = m->slots[i];
        if (!s.key.ptr) continue;
        uint32_t j = (uint32_t)(s.hash & (ncap - 1));
        while (nslots[j].key.ptr) j = (j + 1) & (ncap - 1);
        nslots[j] = s;
    }
    m->slots = nslots;
    m->cap   = ncap;
}

Map *map_new(Arena *a) {
    Map *m = ARENA_NEW(a, Map);
    m->a   = a;
    map_grow(m);
    return m;
}

/* Empty keys are stored with a non-NULL sentinel pointer so that a genuinely
 * empty Str can still be used as a key without colliding with "slot unused". */
static const char g_empty_key[1] = {0};

static Str norm_key(Str k) {
    if (k.ptr == NULL) return (Str){g_empty_key, 0};
    return k;
}

void map_put(Map *m, Str key, void *val) {
    key = norm_key(key);
    if ((uint64_t)m->len * 10 >= (uint64_t)m->cap * 7) map_grow(m);
    uint64_t h = str_hash(key);
    uint32_t i = (uint32_t)(h & (m->cap - 1));
    while (m->slots[i].key.ptr) {
        if (m->slots[i].hash == h && str_eq(m->slots[i].key, key)) {
            m->slots[i].val = val;
            return;
        }
        i = (i + 1) & (m->cap - 1);
    }
    m->slots[i].key  = key;
    m->slots[i].val  = val;
    m->slots[i].hash = h;
    m->len++;
}

void *map_get(const Map *m, Str key) {
    key        = norm_key(key);
    uint64_t h = str_hash(key);
    uint32_t i = (uint32_t)(h & (m->cap - 1));
    while (m->slots[i].key.ptr) {
        if (m->slots[i].hash == h && str_eq(m->slots[i].key, key)) return m->slots[i].val;
        i = (i + 1) & (m->cap - 1);
    }
    return NULL;
}

bool map_has(const Map *m, Str key) {
    key        = norm_key(key);
    uint64_t h = str_hash(key);
    uint32_t i = (uint32_t)(h & (m->cap - 1));
    while (m->slots[i].key.ptr) {
        if (m->slots[i].hash == h && str_eq(m->slots[i].key, key)) return true;
        i = (i + 1) & (m->cap - 1);
    }
    return false;
}

uint32_t map_len(const Map *m) { return m->len; }

bool map_next(const Map *m, uint32_t *cursor, MapEntry *out) {
    for (uint32_t i = *cursor; i < m->cap; i++) {
        if (m->slots[i].key.ptr) {
            out->key = m->slots[i].key;
            out->val = m->slots[i].val;
            *cursor  = i + 1;
            return true;
        }
    }
    *cursor = m->cap;
    return false;
}
