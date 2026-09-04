/* enforce_int.h — state shared between the EnforceScript emitter's two files. */
#ifndef BERYL_ENFORCE_INT_H
#define BERYL_ENFORCE_INT_H

#include "../common/map.h"
#include "../sema/intrinsic.h"
#include "../sema/constfold.h"
#include "../sema/types.h"
#include "enforce_backend.h"

typedef struct {
    Arena     *a;
    SourceMap *sm;
    DiagBag   *d;
    Program   *p;
    Str        prefix;
    SB         out;    /* the class currently being written */
    SB         helper; /* generated helper classes, emitted before it */
    Map       *helpers_done;
    int        indent;
    int        tmp;
    Item      *fn;      /* function being emitted */
    bool       fn_is_err; /* its return type is an error union */
} E;

#define S(x) (int)(x).len, (x).ptr

/* Bohemia indents with tabs, so generated script does too. */
void ef_line(E *e, const char *fmt, ...) BE_PRINTF(2, 3);
void ef_blank(E *e);

Str ef_prefixed(E *e, Str name);
Str ef_type(E *e, Type *t);
Str ef_type_field(E *e, Type *t); /* adds `ref` where a member needs it */
Str ef_tmp(E *e);
Str ef_ident(E *e, Str name);
Str ef_method_name(Str name);

Str  ef_expr(E *e, Expr *x);
void ef_stmt(E *e, Stmt *s);
void ef_block(E *e, Expr *b);

/* True when the expression names storage rather than producing a fresh value,
 * which is what decides whether a copy is needed for value semantics. */
bool ef_is_place(const Expr *x);
bool ef_needs_copy(Type *t);

#endif /* BERYL_ENFORCE_INT_H */
