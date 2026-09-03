/* lexer.h — source text to tokens.
 *
 * Lexing runs in two passes. The first produces raw tokens and records which
 * ones were preceded by a line break. The second decides where those breaks
 * become statement terminators, which needs to look at both neighbours and is
 * far clearer as a separate walk than as lookahead inside the scanner.
 */
#ifndef BERYL_LEXER_H
#define BERYL_LEXER_H

#include "../common/arena.h"
#include "../common/diag.h"
#include "../common/source.h"
#include "../common/str.h"
#include "../common/vec.h"
#include "token.h"

typedef VEC(Token) TokenVec;

TokenVec lex_file(Arena *a, SourceMap *sm, DiagBag *d, Interner *in, uint32_t file);

/* Exposed for tests and for the parser's error messages. */
bool tok_can_end_expr(TokKind k);
bool tok_is_continuation(TokKind k);

#endif /* BERYL_LEXER_H */
