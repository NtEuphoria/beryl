/* print.h — AST rendering.
 *
 * ast_print produces a stable S-expression dump used as the golden-test
 * oracle. ast_format produces canonical Beryl source and is what `beryl fmt`
 * writes; formatting is idempotent and round-trips through the parser.
 */
#ifndef BERYL_PRINT_H
#define BERYL_PRINT_H

#include "../common/arena.h"
#include "../common/str.h"
#include "ast.h"

Str ast_print(Arena *a, const Module *m);
Str ast_format(Arena *a, const Module *m);

#endif /* BERYL_PRINT_H */
