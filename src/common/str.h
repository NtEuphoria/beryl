/* str.h — non-owning string slice, string builder, and interner.
 *
 * `Str` never owns its bytes. Source text lives in an arena for the whole
 * compilation, so slices into it stay valid and no copying is needed.
 */
#ifndef BERYL_STR_H
#define BERYL_STR_H

#include <stdarg.h>
#include <stdbool.h>
#include <stdint.h>

#include "arena.h"

typedef struct {
    const char *ptr;
    uint32_t    len;
} Str;

#define STR_EMPTY ((Str){NULL, 0})
#define STR_LIT(s) ((Str){(s), (uint32_t)(sizeof(s) - 1)})

Str      str_from(const char *cstr);
Str      str_new(const char *p, uint32_t len);
bool     str_eq(Str a, Str b);
bool     str_eq_c(Str a, const char *b);
bool     str_empty(Str s);
uint64_t str_hash(Str s);
Str      str_dup(Arena *a, Str s);
char    *str_cstr(Arena *a, Str s); /* NUL-terminated copy */
bool     str_starts_with(Str s, const char *prefix);
Str      str_slice(Str s, uint32_t start, uint32_t len);

/* ---- string builder ---------------------------------------------------- */

typedef struct {
    Arena   *a;
    char    *buf;
    uint32_t len;
    uint32_t cap;
} SB;

void sb_init(SB *sb, Arena *a);
void sb_char(SB *sb, char c);
void sb_str(SB *sb, Str s);
void sb_cstr(SB *sb, const char *s);
void sb_fmt(SB *sb, const char *fmt, ...);
void sb_vfmt(SB *sb, const char *fmt, va_list ap);
void sb_repeat(SB *sb, char c, int n);
Str  sb_finish(SB *sb);
Str  sb_peek(const SB *sb);

/* ---- interner ---------------------------------------------------------- */
/* Interned Strs are canonical: equal contents share a pointer, so identifier
 * comparison in later passes is a pointer compare. */

typedef struct Interner Interner;

Interner *intern_new(Arena *a);
Str       intern(Interner *in, Str s);
Str       intern_c(Interner *in, const char *s);
uint32_t  intern_count(const Interner *in);

#endif /* BERYL_STR_H */
