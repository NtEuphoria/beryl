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

    /* Working state for the analysis passes; meaningless outside them. */
    uint8_t state; /* ownership */
    uint8_t taint; /* taint  */
    Span    moved_at;
} Local;

typedef struct Program {
    Arena   *a;
    TypeCtx *types;
    VEC(Module *) modules;
    Map *items;   /* qualified name  -> Item* */
    Map *module_scopes; /* full module path -> ModuleScope* */
    Map *methods; /* qualified receiver declaration + method -> Item* */
} Program;

typedef struct {
    Str name;
    Map *items;
    Map *imports;
    VEC(Module *) files;
} ModuleScope;
typedef struct {
    Item *item;
    ModuleScope *module;
    Item *site;
} Import;

Program *prog_new(Arena *a);
void     prog_add_module(Program *p, Module *m);

/* Builds the item tables, creates named types, resolves every declared type,
 * and checks for duplicates and module cycles. Returns false if it reported
 * an error. */
bool resolve_program(DiagBag *d, Program *p);

/* Resolves one syntactic type. Reports BE0302 and returns the error type when
 * the name is unknown. */
Type *resolve_type_expr(Program *p, DiagBag *d, Module *module, Item *scope, TypeExpr *te);

Item *prog_item(Program *p, Str qualified);
/* Lookup may return a private declaration; the caller must check accessibility
 * before admitting it. No unrelated module participates in unqualified lookup. */
Item *prog_lookup(Program *p, Module *module, Str name);
Item *prog_method(Program *p, Item *receiver, Str method);
bool prog_accessible(DiagBag *d, Module *from, Item *item, Span use);
bool prog_same_module(Module *a, Module *b);
bool prog_expr_path(Arena *a, Expr *e, Str *path, Str *root);

#endif /* BERYL_RESOLVE_H */
