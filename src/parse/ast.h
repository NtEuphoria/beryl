/* ast.h — the syntax tree.
 *
 * The tree is mutated in place by later passes: `check` fills in `Expr.type`,
 * `monomorph` clones and rewrites items, and `lower` desugars. Nothing here is
 * freed individually — it all lives in one arena.
 */
#ifndef BERYL_AST_H
#define BERYL_AST_H

#include <stdbool.h>
#include <stdint.h>

#include "../common/arena.h"
#include "../common/source.h"
#include "../common/str.h"
#include "../common/vec.h"
#include "../lex/token.h"

typedef struct Expr     Expr;
typedef struct Stmt     Stmt;
typedef struct Item     Item;
typedef struct TypeExpr TypeExpr;
typedef struct Type     Type; /* sema/types.h */

typedef VEC(Str) StrVec;
typedef VEC(Expr *) ExprVec;
typedef VEC(Stmt *) StmtVec;
typedef VEC(Item *) ItemVec;
typedef VEC(TypeExpr *) TypeExprVec;

/* ---- passing conventions ----------------------------------------------- */

typedef enum { CONV_LET = 0, CONV_INOUT, CONV_SINK, CONV_SET } Conv;

const char *conv_name(Conv c); /* "let" / "inout" / "sink" / "set" */

/* ---- syntactic types --------------------------------------------------- */

typedef enum {
    TE_PATH,     /* Foo, core.math.Vec3, List<i32> */
    TE_ARRAY,    /* [T; N] */
    TE_OPTION,   /* T? */
    TE_ERRUNION, /* !T */
} TypeExprKind;

struct TypeExpr {
    TypeExprKind kind;
    Span         span;
    StrVec       segs; /* TE_PATH: dotted path segments */
    TypeExprVec  args; /* TE_PATH: generic arguments */
    TypeExpr    *elem; /* TE_ARRAY element, TE_OPTION/TE_ERRUNION inner */
    Expr        *len;  /* TE_ARRAY length expression */
};

/* ---- attributes -------------------------------------------------------- */

typedef struct {
    Str  name; /* server_only, untrusted, constant_time, unsafe, layout */
    Str  arg;  /* @unsafe(ffi) -> "ffi"; empty when absent */
    Span span;
} Attr;

typedef VEC(Attr) AttrVec;

/* ---- expressions ------------------------------------------------------- */

typedef enum {
    EX_INT,
    EX_FLOAT,
    EX_STR,
    EX_CHAR,
    EX_BOOL,
    EX_PATH,
    EX_SELF,
    EX_UNARY,
    EX_BINARY,
    EX_CALL,
    EX_FIELD,
    EX_INDEX,
    EX_CAST,
    EX_STRUCT_LIT,
    EX_ARRAY_LIT,
    EX_IF,
    EX_BLOCK,
    EX_TRY,
    EX_CATCH,
    EX_ORELSE,
    EX_ERROR_LIT,
    EX_UNSAFE,
    EX_RANGE,
} ExprKind;

/* A call argument may carry an explicit convention: f(inout x, sink y). */
typedef struct {
    Conv  conv;
    Expr *value;
    Span  span;
} Arg;

typedef VEC(Arg) ArgVec;

typedef struct {
    Str   name;
    Expr *value;
    Span  span;
} FieldInit;

typedef VEC(FieldInit) FieldInitVec;

struct Expr {
    ExprKind kind;
    Span     span;
    Type    *type; /* filled by sema/check */
    union {
        struct {
            uint64_t val;
            Str      suffix;
        } int_lit;
        struct {
            double val;
            Str    suffix;
        } float_lit;
        Str      str_lit;
        uint32_t char_lit;
        bool     bool_lit;
        struct {
            StrVec      segs;
            TypeExprVec targs;
        } path;
        struct {
            TokKind op;
            Expr   *operand;
        } unary;
        struct {
            TokKind op;
            Expr   *lhs;
            Expr   *rhs;
        } binary;
        struct {
            Expr  *callee;
            ArgVec args;
        } call;
        struct {
            Expr *base;
            Str   name;
        } field;
        struct {
            Expr *base;
            Expr *index;
        } index;
        struct {
            Expr     *value;
            TypeExpr *type;
        } cast;
        struct {
            TypeExpr    *type;
            FieldInitVec fields;
        } struct_lit;
        struct {
            ExprVec elems;
        } array_lit;
        struct {
            Expr *cond;
            Expr *then_blk;
            Expr *else_blk; /* NULL, a block, or a nested EX_IF */
        } if_expr;
        struct {
            StmtVec stmts;
        } block;
        struct {
            Expr *inner;
        } try_expr;
        struct {
            Expr *value;
            Str   binding; /* catch |e| { } — empty if absent */
            Expr *handler;
        } catch_expr;
        struct {
            Expr *value;
            Expr *fallback;
        } orelse_expr;
        Str error_lit; /* error.OutOfRange -> "OutOfRange" */
        struct {
            Str   capability; /* raw_ptr / unchecked_index / ffi / transmute */
            Expr *body;
        } unsafe_expr;
        struct {
            Expr *lo;
            Expr *hi;
        } range;
    };
};

/* ---- statements -------------------------------------------------------- */

typedef enum {
    ST_LET, /* also ST_VAR via `is_var` */
    ST_EXPR,
    ST_ASSIGN,
    ST_WHILE,
    ST_FOR,
    ST_RETURN,
    ST_BREAK,
    ST_CONTINUE,
    ST_DEFER,
} StmtKind;

struct Stmt {
    StmtKind kind;
    Span     span;
    union {
        struct {
            Str       name;
            TypeExpr *type; /* NULL when inferred */
            Expr     *init;
            bool      is_var;
        } let;
        Expr *expr; /* ST_EXPR, ST_RETURN (may be NULL), ST_DEFER */
        struct {
            Expr   *target;
            TokKind op; /* TK_ASSIGN or a compound form */
            Expr   *value;
        } assign;
        struct {
            Expr *cond;
            Expr *body;
        } while_st;
        struct {
            Str   var;
            Expr *iter;
            Expr *body;
        } for_st;
    };
};

/* ---- items ------------------------------------------------------------- */

typedef struct {
    Str  name;
    Str  bound; /* trait bound, empty if none */
    Span span;
} GenericParam;

typedef VEC(GenericParam) GenericVec;

typedef struct {
    Str       name;
    TypeExpr *type;
    Expr     *deflt;
    Conv      conv;
    bool      is_self;
    Span      span;
} Param;

typedef VEC(Param) ParamVec;

typedef struct {
    Str       name;
    TypeExpr *type;
    Expr     *deflt;
    Str       doc;
    Span      span;
} Field;

typedef VEC(Field) FieldVec;

typedef struct {
    Str   name;
    Expr *value; /* explicit discriminant, or NULL */
    Span  span;
} EnumVariant;

typedef VEC(EnumVariant) EnumVariantVec;

typedef enum { IT_FN, IT_STRUCT, IT_ENUM, IT_CONST, IT_TEST, IT_USE, IT_TRAIT } ItemKind;

struct Item {
    ItemKind kind;
    Span     span;
    bool     is_pub;
    Str      doc;
    AttrVec  attrs;
    Str      name;
    Str      qual_name; /* module-qualified, filled by resolve */
    union {
        struct {
            Str        recv;     /* receiver type for a method, empty for free fn */
            GenericVec generics;
            ParamVec   params;
            TypeExpr  *ret; /* NULL means void */
            Expr      *body;
        } fn;
        struct {
            GenericVec generics;
            FieldVec   fields;
        } strukt;
        struct {
            EnumVariantVec variants;
        } enom;
        struct {
            TypeExpr *type;
            Expr     *value;
        } konst;
        struct {
            Str   label; /* test "name" { } */
            Expr *body;
        } test;
        struct {
            StrVec path;
        } use_;
        struct {
            GenericVec generics;
            ItemVec    methods;
        } trait;
    };
};

typedef struct {
    StrVec   path; /* module flight.pid -> ["flight", "pid"] */
    ItemVec  items;
    Span     span;
    Str      doc;
    uint32_t file;
} Module;

/* ---- construction ------------------------------------------------------ */

Expr     *ast_expr(Arena *a, ExprKind k, Span s);
Stmt     *ast_stmt(Arena *a, StmtKind k, Span s);
Item     *ast_item(Arena *a, ItemKind k, Span s);
TypeExpr *ast_type(Arena *a, TypeExprKind k, Span s);

/* Dotted path as text, for diagnostics: ["core","math"] -> "core.math" */
Str path_str(Arena *a, StrVec segs);

#endif /* BERYL_AST_H */
