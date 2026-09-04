/* parser.h — recursive descent for items and statements, Pratt for expressions. */
#ifndef BERYL_PARSER_H
#define BERYL_PARSER_H

#include "../common/arena.h"
#include "../common/diag.h"
#include "../lex/lexer.h"
#include "ast.h"

/* Returns a Module even when errors were reported, so later passes can still
 * run over the well-formed parts. Check diag_errors() before trusting it. */
Module *parse_file(Arena *a, DiagBag *d, Interner *in, TokenVec toks, uint32_t file);

/* ---- shared parser state, used by parser.c and parser_expr.c ----------- */

typedef struct {
    Arena    *a;
    DiagBag  *d;
    Interner *in;
    TokenVec  toks;
    uint32_t  pos;
    uint32_t  file;
    /* Struct literals are ambiguous with blocks after `if`/`while`/`for`, so
     * they are disabled while parsing those conditions. */
    bool no_struct_lit;
    /* Guards against a recovery loop making no forward progress. */
    uint32_t last_error_pos;
} P;

Token   p_peek(P *p);
Token   p_peek2(P *p);
TokKind p_kind(P *p);
Token   p_next(P *p);
bool    p_check(P *p, TokKind k);
bool    p_accept(P *p, TokKind k);
bool    p_expect(P *p, TokKind k, const char *ctx);
bool    p_member_name(P *p, Str *out, const char *ctx);
void    p_skip_newlines(P *p);
Span    p_span_from(P *p, uint32_t start_pos);

Expr     *parse_expr(P *p);
Expr     *parse_block(P *p);
TypeExpr *parse_type(P *p);

#endif /* BERYL_PARSER_H */
