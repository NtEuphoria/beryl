/* check.h — bidirectional type checking and inference.
 *
 * Inference is function-local and signatures are always explicit. There is no
 * global inference and no unification across items: that is a deliberate
 * compile-speed decision, and it makes error messages point at the line that
 * is actually wrong.
 */
#ifndef BERYL_CHECK_H
#define BERYL_CHECK_H

#include "../common/diag.h"
#include "../common/map.h"
#include "resolve.h"
#include "types.h"

typedef struct {
    Arena   *a;
    DiagBag *d;
    Program *p;
    TypeCtx *tc;
    Module  *mod;
    Item    *fn;      /* function being checked */
    Type    *ret_ty;  /* its declared return type, possibly an error union */
    int      loop_depth;
    VEC(Map *) scopes;
    VEC(Local *) locals;
    uint32_t next_local_id;
} C;

bool check_program(DiagBag *d, Program *p);

/* Shared between check.c and check_expr.c. */
Type  *chk(C *c, Expr *e, Type *expected);
void   chk_block(C *c, Expr *block);
Local *chk_lookup(C *c, Str name);
Local *chk_declare(C *c, Str name, Type *ty, bool is_mut, bool is_param, Conv conv, Span sp);
void   chk_push_scope(C *c);
void   chk_pop_scope(C *c);
Type  *chk_err(C *c);

/* Reports the right diagnostic for `found` where `want` was required. */
void chk_expect_type(C *c, Span at, Type *want, Type *found, const char *ctx);

#endif /* BERYL_CHECK_H */
