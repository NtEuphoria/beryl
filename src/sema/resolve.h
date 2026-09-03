/* resolve.h — item tables, module graph, and TypeExpr to Type resolution. */
#ifndef BERYL_RESOLVE_H
#define BERYL_RESOLVE_H

#include "../common/diag.h"
#include "../parse/ast.h"
#include "types.h"

/* A binding introduced by a parameter or a let/var. */
typedef struct {
    Str      name;
    Type    *type;
    bool     is_mut;
    bool     is_param;
    Conv     conv;
    Span     span;
    uint32_t id; /* dense index within the enclosing function */
} Local;

typedef struct Program {
    Arena   *a;
    TypeCtx *types;
    VEC(Module *) modules;
    Map *items;   /* qualified name  -> Item* */
    Map *shorts;  /* short name      -> Item* (first declaration wins) */
    Map *methods; /* "Recv.method"   -> Item* */
} Program;

Program *prog_new(Arena *a);
void     prog_add_module(Program *p, Module *m);

/* Builds the item tables, creates named types, resolves every declared type,
 * and checks for duplicates and module cycles. Returns false if it reported
 * an error. */
bool resolve_program(DiagBag *d, Program *p);

/* Resolves one syntactic type. Reports BE0302 and returns the error type when
 * the name is unknown. */
Type *resolve_type_expr(Program *p, DiagBag *d, TypeExpr *te);

Item *prog_item(Program *p, Str qualified);
Item *prog_short(Program *p, Str name);
Item *prog_method(Program *p, Str recv, Str method);

#endif /* BERYL_RESOLVE_H */
