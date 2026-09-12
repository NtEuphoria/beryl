#ifndef BERYL_SYMBOL_H
#define BERYL_SYMBOL_H
#include "str.h"
/* Injective byte encoding with a trusted category prefix. Underscores escape
 * too, so source punctuation cannot collide with literal escape-like text. */
Str symbol_encode(Arena *a, const char *category, Str name);
#endif
