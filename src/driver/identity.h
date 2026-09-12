#ifndef BERYL_IDENTITY_H
#define BERYL_IDENTITY_H
#include "../common/source.h"
/* Describes bytes actually loaded into the compiler, in compilation order. */
Str identity_sources(Arena *a, const SourceMap *sm);
Str identity_compiler(Arena *a); /* empty means unavailable */
#endif
