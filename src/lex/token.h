/* token.h — token kinds and the token record. */
#ifndef BERYL_TOKEN_H
#define BERYL_TOKEN_H

#include <stdbool.h>
#include <stdint.h>

#include "../common/source.h"
#include "../common/str.h"

typedef enum {
    TK_EOF = 0,
    TK_NEWLINE, /* virtual statement terminator */

    /* literals and names */
    TK_IDENT,
    TK_INT,
    TK_FLOAT,
    TK_STRING,
    TK_CHAR,
    TK_DOC, /* //! documentation comment */

    /* keywords */
    TK_MODULE,
    TK_USE,
    TK_PUB,
    TK_FN,
    TK_STRUCT,
    TK_ENUM,
    TK_TRAIT,
    TK_LET,
    TK_VAR,
    TK_IF,
    TK_ELSE,
    TK_WHILE,
    TK_FOR,
    TK_IN,
    TK_RETURN,
    TK_BREAK,
    TK_CONTINUE,
    TK_TEST,
    TK_CONST,
    TK_COMPTIME,
    TK_TRUE,
    TK_FALSE,
    TK_INOUT,
    TK_SINK,
    TK_SET,
    TK_AS,
    TK_TRY,
    TK_CATCH,
    TK_ORELSE,
    TK_ERROR,
    TK_DEFER,
    TK_SELF,
    TK_MATCH,

    /* punctuation */
    TK_LPAREN,
    TK_RPAREN,
    TK_LBRACE,
    TK_RBRACE,
    TK_LBRACKET,
    TK_RBRACKET,
    TK_COMMA,
    TK_DOT,
    TK_DOTDOT,
    TK_COLON,
    TK_SEMI,
    TK_ARROW,    /* -> */
    TK_FATARROW, /* => */
    TK_AT,
    TK_QUESTION,
    TK_BANG,
    TK_PIPE,
    TK_AMP,
    TK_CARET,
    TK_TILDE,
    TK_PLUS,
    TK_MINUS,
    TK_STAR,
    TK_SLASH,
    TK_PERCENT,
    TK_ASSIGN, /* =  */
    TK_EQ,     /* == */
    TK_NE,
    TK_LT,
    TK_LE,
    TK_GT,
    TK_GE,
    TK_ANDAND,
    TK_OROR,
    TK_SHL,
    TK_SHR,
    TK_PLUSEQ,
    TK_MINUSEQ,
    TK_STAREQ,
    TK_SLASHEQ,
    TK_PERCENTEQ,

    TK_COUNT
} TokKind;

const char *tok_name(TokKind k);

typedef struct {
    TokKind  kind;
    Span     span;
    Str      text;   /* identifier name, cooked string value, or raw literal text */
    Str      suffix;
    /* True when a line break preceded this token. The lexer's newline rule
     * suppresses most of these, but a `>` closing a generic type can never
     * end an expression, so the parser needs the raw fact as well. */
    bool nl_before; /* numeric type suffix, empty when absent */
    uint64_t ival;   /* TK_INT, TK_CHAR */
    double   fval;   /* TK_FLOAT */
} Token;

#endif /* BERYL_TOKEN_H */
