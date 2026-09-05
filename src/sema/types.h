/* types.h — semantic types.
 *
 * Types are interned, so `ty_eq` is pointer equality and the checker never
 * walks a structure to compare two types.
 */
#ifndef BERYL_TYPES_H
#define BERYL_TYPES_H

#include <stdbool.h>
#include <stdint.h>

#include "../common/arena.h"
#include "../common/map.h"
#include "../common/str.h"
#include "../parse/ast.h"

typedef enum {
    TY_ERROR = 0, /* poison; suppresses cascades */
    TY_VOID,
    TY_BOOL,
    TY_CHAR,
    TY_INT,
    TY_FLOAT,
    TY_STR,
    TY_STRUCT,
    TY_ENUM,
    TY_ARRAY,
    TY_OPTION,
    TY_ERRUNION,
    TY_VEC2,
    TY_VEC3,
    TY_VEC4,
    TY_QUAT,
    TY_MAT3,
    TY_MAT4,
    TY_LIST,
    TY_MAP,
    TY_BOX,
    TY_RC,
    TY_HANDLE,
    TY_POOL,
    TY_TYPEPARAM,
} TypeKind;

struct Type {
    TypeKind kind;
    uint8_t  bits;      /* TY_INT: 8/16/32/64 · TY_FLOAT: 32/64 */
    bool     is_signed; /* TY_INT */
    Str      name;      /* struct/enum/type-parameter name */
    Item    *decl;      /* struct or enum declaration */
    Type    *elem;      /* array/option/errunion/list/box/rc/handle/pool element */
    Type    *key;       /* map key */
    uint64_t array_len;
};

typedef struct TypeCtx TypeCtx;

TypeCtx *types_new(Arena *a);

Type *ty_prim(TypeCtx *c, TypeKind k);
Type *ty_int(TypeCtx *c, uint8_t bits, bool is_signed);
Type *ty_float(TypeCtx *c, uint8_t bits);
Type *ty_array(TypeCtx *c, Type *elem, uint64_t n);
Type *ty_option(TypeCtx *c, Type *inner);
Type *ty_errunion(TypeCtx *c, Type *ok);
Type *ty_wrap(TypeCtx *c, TypeKind k, Type *elem);          /* List/Box/Rc/Handle/Pool */
Type *ty_map(TypeCtx *c, Type *key, Type *val);
Type *ty_named(TypeCtx *c, TypeKind k, Str qualified, Item *decl);
Type *ty_typeparam(TypeCtx *c, Str name);

bool ty_eq(const Type *a, const Type *b);
Str  ty_name(Arena *a, const Type *t);

bool ty_is_numeric(const Type *t);
bool ty_is_integer(const Type *t);
bool ty_is_float(const Type *t);

/* Vec2/3/4. Quat and Mat3/4 are deliberately excluded: they lower to a type
 * name but have no component or arithmetic semantics defined yet, and
 * pretending otherwise is how a back end ends up emitting a zero value for
 * an operation nobody implemented. */
bool     ty_is_vec(const Type *t);
uint32_t ty_vec_arity(const Type *t); /* 2, 3, 4 — or 0 if not a vector */
/* Scalars and small aggregates with no destructor: copied rather than moved. */
bool ty_is_copy(const Type *t);
bool ty_is_error(const Type *t);

/* Names a primitive type keyword, or TY_ERROR if it is not one. */
TypeKind ty_prim_from_name(Str name, uint8_t *bits, bool *is_signed);

#endif /* BERYL_TYPES_H */
