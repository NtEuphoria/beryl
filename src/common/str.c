#include "str.h"
#include "checked_size.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static _Noreturn void str_capacity_failure(void) {
    fputs("beryl: compiler string or interner capacity limit exceeded\n", stderr);
    abort();
}

Str str_from(const char *cstr) {
    if (!cstr) return STR_EMPTY;
    size_t len = strlen(cstr);
    if (len > UINT32_MAX) str_capacity_failure();
    return (Str){cstr, (uint32_t)len};
}

Str str_new(const char *p, uint32_t len) { return (Str){p, len}; }

bool str_eq(Str a, Str b) {
    if (a.len != b.len) return false;
    if (a.ptr == b.ptr) return true;
    if (a.len == 0) return true;
    return memcmp(a.ptr, b.ptr, a.len) == 0;
}

bool str_eq_c(Str a, const char *b) { return str_eq(a, str_from(b)); }

bool str_empty(Str s) { return s.len == 0; }

uint64_t str_hash(Str s) {
    uint64_t h = 1469598103934665603ULL; /* FNV-1a 64 */
    for (uint32_t i = 0; i < s.len; i++) {
        h ^= (unsigned char)s.ptr[i];
        h *= 1099511628211ULL;
    }
    return h;
}

Str str_dup(Arena *a, Str s) {
    if (s.len == 0) return STR_EMPTY;
    char *p = (char *)arena_alloc(a, s.len, 1);
    memcpy(p, s.ptr, s.len);
    return (Str){p, s.len};
}

char *str_cstr(Arena *a, Str s) {
    size_t bytes;
    if (!checked_size_add(s.len, 1, &bytes)) str_capacity_failure();
    char *p = (char *)arena_alloc(a, bytes, 1);
    if (s.len) memcpy(p, s.ptr, s.len);
    p[s.len] = '\0';
    return p;
}

bool str_starts_with(Str s, const char *prefix) {
    size_t n = strlen(prefix);
    if (s.len < n) return false;
    return memcmp(s.ptr, prefix, n) == 0;
}

Str str_slice(Str s, uint32_t start, uint32_t len) {
    if (start > s.len) return STR_EMPTY;
    if (len > s.len - start) len = s.len - start;
    return (Str){s.ptr ? s.ptr + start : NULL, len};
}

/* ---- string builder ---------------------------------------------------- */

void sb_init(SB *sb, Arena *a) {
    sb->a   = a;
    sb->buf = NULL;
    sb->len = 0;
    sb->cap = 0;
}

static void sb_reserve(SB *sb, size_t need) {
    size_t total, cap;
    if (sb->len > sb->cap || (sb->cap && !sb->buf) ||
        !checked_size_add(sb->len, need, &total) ||
        !checked_size_grow(sb->cap, total, UINT32_MAX, 128, &cap))
        str_capacity_failure();
    if (total <= sb->cap) return;
    char *nb = (char *)arena_alloc(sb->a, cap, 1);
    if (sb->len) memcpy(nb, sb->buf, sb->len);
    sb->buf = nb;
    sb->cap = (uint32_t)cap;
}

void sb_char(SB *sb, char c) {
    sb_reserve(sb, 1);
    sb->buf[sb->len++] = c;
}

void sb_str(SB *sb, Str s) {
    if (!s.len) return;
    sb_reserve(sb, s.len);
    memcpy(sb->buf + sb->len, s.ptr, s.len);
    sb->len += s.len;
}

void sb_cstr(SB *sb, const char *s) { sb_str(sb, str_from(s)); }

void sb_vfmt(SB *sb, const char *fmt, va_list ap) {
    va_list ap2;
    va_copy(ap2, ap);
    int n = vsnprintf(NULL, 0, fmt, ap2);
    va_end(ap2);
    if (n <= 0) return;
    sb_reserve(sb, (size_t)n + 1);
    vsnprintf(sb->buf + sb->len, (size_t)n + 1, fmt, ap);
    sb->len += (uint32_t)n;
}

void sb_fmt(SB *sb, const char *fmt, ...) {
    va_list ap;
    va_start(ap, fmt);
    sb_vfmt(sb, fmt, ap);
    va_end(ap);
}

void sb_repeat(SB *sb, char c, int n) {
    for (int i = 0; i < n; i++) sb_char(sb, c);
}

Str sb_finish(SB *sb) { return (Str){sb->buf, sb->len}; }
Str sb_peek(const SB *sb) { return (Str){sb->buf, sb->len}; }

/* ---- interner ---------------------------------------------------------- */

typedef struct {
    Str      key;
    uint64_t hash;
} ISlot;

struct Interner {
    Arena   *a;
    ISlot   *slots;
    uint32_t cap; /* power of two */
    uint32_t len;
};

static void intern_grow(Interner *in) {
    size_t limit = SIZE_MAX / sizeof(ISlot), next;
    if (limit > UINT32_MAX) limit = UINT32_MAX;
    if (!checked_size_grow_power2(in->cap, 256, limit, &next)) str_capacity_failure();
    uint32_t ncap = (uint32_t)next;
    ISlot   *nslots = ARENA_ARRAY(in->a, ISlot, ncap);
    for (uint32_t i = 0; i < in->cap; i++) {
        ISlot s = in->slots[i];
        if (!s.key.ptr) continue;
        uint32_t j = (uint32_t)(s.hash & (ncap - 1));
        while (nslots[j].key.ptr) j = (j + 1) & (ncap - 1);
        nslots[j] = s;
    }
    in->slots = nslots;
    in->cap   = ncap;
}

Interner *intern_new(Arena *a) {
    Interner *in = ARENA_NEW(a, Interner);
    in->a        = a;
    intern_grow(in);
    return in;
}

/* A canonical, non-NULL empty string. The slot table uses key.ptr == NULL to
 * mean "empty slot", so an interned empty string must not have a NULL ptr. */
static const char g_empty_byte[1] = {0};

Str intern(Interner *in, Str s) {
    if (s.len == 0) return (Str){g_empty_byte, 0};
    if ((uint64_t)in->len * 10 >= (uint64_t)in->cap * 7) intern_grow(in);
    uint64_t h = str_hash(s);
    uint32_t i = (uint32_t)(h & (in->cap - 1));
    while (in->slots[i].key.ptr) {
        if (in->slots[i].hash == h && str_eq(in->slots[i].key, s)) return in->slots[i].key;
        i = (i + 1) & (in->cap - 1);
    }
    /* Copy into the arena so the canonical slice outlives any transient buffer. */
    Str canon        = str_dup(in->a, s);
    in->slots[i].key  = canon;
    in->slots[i].hash = h;
    in->len++;
    return canon;
}

Str intern_c(Interner *in, const char *s) { return intern(in, str_from(s)); }

uint32_t intern_count(const Interner *in) { return in->len; }
