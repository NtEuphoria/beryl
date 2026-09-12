#ifndef BERYL_REFERENCE_DRIVER_H
#define BERYL_REFERENCE_DRIVER_H
#include "build.h"
#include "../reference/reference.h"
/* Strict kind@file_id:byte_offset syntax for machine-readable source identity. */
bool driver_parse_expected_trap(const char *text,RefExpectedTrap *out);
bool driver_parse_watch_root(const char *text,RefWatchRoot *out);
int driver_reference_tests(Arena *a,SourceMap *sm,DiagBag *d,Program *p,
                        RefOpts reference,BuildOpts native,bool differential);
#endif
