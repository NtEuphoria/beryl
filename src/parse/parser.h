/* parser.h — recursive descent for items and statements, Pratt for expressions. */
#ifndef BERYL_PARSER_H
#define BERYL_PARSER_H

#include <setjmp.h>

#include "../common/arena.h"
#include "../common/diag.h"
#include "../lex/lexer.h"
#include "ast.h"

/* Returns a Module even when errors were reported, so later passes can still
 * run over the well-formed parts. Check diag_errors() before trusting it. */
Module *parse_file(Arena *a, DiagBag *d, Interner *in, TokenVec toks, uint32_t file);

/* Per-file structural limits. Token admission occurs after lexing; these are
 * not a lexer allocation limit or a whole-program compiler work budget. */
#define PARSE_MAX_TOKENS 262144u
#define PARSE_MAX_RECURSION 256u
#define PARSE_MAX_AST_DEPTH 128u
#define PARSE_MAX_AST_NODES 262144u
#define PARSE_MAX_WORK 1048576u

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
    uint32_t recursion, work;
    jmp_buf resource_exit; /* owned only by the active parse_file call */
} P;

void p_work(P *p);
void p_enter(P *p);
void p_leave(P *p);
void p_validate_tokens(P *p);
void p_validate_shape(P *p, Module *module);

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
