#include "types.h"

struct TypeCtx {
    Arena *a;
    Map   *interned; /* canonical name -> Type* */
};

TypeCtx *types_new(Arena *a) {
    TypeCtx *c  = ARENA_NEW(a, TypeCtx);
    c->a        = a;
    c->interned = map_new(a);
    return c;
}

/* Interning key is the canonical rendering, which is unique per type. */
static Type *intern_ty(TypeCtx *c, Type *t) {
    Str  key = ty_name(c->a, t);
    Type *ex = (Type *)map_get(c->interned, key);
    if (ex) return ex;
    Type *nt = ARENA_NEW(c->a, Type);
    *nt      = *t;
    map_put(c->interned, key, nt);
    return nt;
}

Type *ty_prim(TypeCtx *c, TypeKind k) {
    Type t = {0};
    t.kind = k;
    return intern_ty(c, &t);
}

Type *ty_int(TypeCtx *c, uint8_t bits, bool is_signed) {
    Type t     = {0};
    t.kind     = TY_INT;
    t.bits     = bits;
    t.is_signed = is_signed;
    return intern_ty(c, &t);
}

Type *ty_float(TypeCtx *c, uint8_t bits) {
    Type t = {0};
    t.kind = TY_FLOAT;
    t.bits = bits;
    return intern_ty(c, &t);
}

Type *ty_array(TypeCtx *c, Type *elem, uint64_t n) {
    Type t      = {0};
    t.kind      = TY_ARRAY;
    t.elem      = elem;
    t.array_len = n;
    return intern_ty(c, &t);
}

Type *ty_option(TypeCtx *c, Type *inner) {
    Type t = {0};
    t.kind = TY_OPTION;
    t.elem = inner;
    return intern_ty(c, &t);
}

Type *ty_errunion(TypeCtx *c, Type *ok) {
    Type t = {0};
    t.kind = TY_ERRUNION;
    t.elem = ok;
    return intern_ty(c, &t);
}

Type *ty_wrap(TypeCtx *c, TypeKind k, Type *elem) {
    Type t = {0};
    t.kind = k;
    t.elem = elem;
    return intern_ty(c, &t);
}

Type *ty_map(TypeCtx *c, Type *key, Type *val) {
    Type t = {0};
    t.kind = TY_MAP;
    t.key  = key;
    t.elem = val;
    return intern_ty(c, &t);
}

Type *ty_named(TypeCtx *c, TypeKind k, Str qualified, Item *decl) {
    Type t = {0};
    t.kind = k;
    t.name = qualified;
    t.decl = decl;
    return intern_ty(c, &t);
}

Type *ty_typeparam(TypeCtx *c, Str name) {
    Type t = {0};
    t.kind = TY_TYPEPARAM;
    t.name = name;
    return intern_ty(c, &t);
}

bool ty_eq(const Type *a, const Type *b) { return a == b; }

static void name_into(SB *sb, const Type *t) {
    if (!t) {
        sb_cstr(sb, "<null>");
        return;
    }
    switch (t->kind) {
        case TY_ERROR: sb_cstr(sb, "<error>"); break;
        case TY_VOID: sb_cstr(sb, "void"); break;
        case TY_BOOL: sb_cstr(sb, "bool"); break;
        case TY_CHAR: sb_cstr(sb, "char"); break;
        case TY_STR: sb_cstr(sb, "str"); break;
        case TY_INT: sb_fmt(sb, "%c%u", t->is_signed ? 'i' : 'u', t->bits); break;
        case TY_FLOAT: sb_fmt(sb, "f%u", t->bits); break;
        case TY_VEC2: sb_cstr(sb, "Vec2"); break;
        case TY_VEC3: sb_cstr(sb, "Vec3"); break;
        case TY_VEC4: sb_cstr(sb, "Vec4"); break;
        case TY_QUAT: sb_cstr(sb, "Quat"); break;
        case TY_MAT3: sb_cstr(sb, "Mat3"); break;
        case TY_MAT4: sb_cstr(sb, "Mat4"); break;
        case TY_STRUCT:
        case TY_ENUM:
        case TY_TYPEPARAM: sb_str(sb, t->name); break;
        case TY_ARRAY:
            sb_char(sb, '[');
            name_into(sb, t->elem);
            sb_fmt(sb, "; %llu]", (unsigned long long)t->array_len);
            break;
        case TY_OPTION:
            name_into(sb, t->elem);
            sb_char(sb, '?');
            break;
        case TY_ERRUNION:
            sb_char(sb, '!');
            name_into(sb, t->elem);
            break;
        case TY_LIST:
            sb_cstr(sb, "List<");
            name_into(sb, t->elem);
            sb_char(sb, '>');
            break;
        case TY_BOX:
            sb_cstr(sb, "Box<");
            name_into(sb, t->elem);
            sb_char(sb, '>');
            break;
        case TY_RC:
            sb_cstr(sb, "Rc<");
            name_into(sb, t->elem);
            sb_char(sb, '>');
            break;
        case TY_HANDLE:
            sb_cstr(sb, "Handle<");
            name_into(sb, t->elem);
            sb_char(sb, '>');
            break;
        case TY_POOL:
            sb_cstr(sb, "Pool<");
            name_into(sb, t->elem);
            sb_char(sb, '>');
            break;
        case TY_MAP:
            sb_cstr(sb, "Map<");
            name_into(sb, t->key);
            sb_cstr(sb, ", ");
            name_into(sb, t->elem);
            sb_char(sb, '>');
            break;
        default: sb_cstr(sb, "?"); break;
    }
}

Str ty_name(Arena *a, const Type *t) {
    SB sb;
    sb_init(&sb, a);
    name_into(&sb, t);
    return sb_finish(&sb);
}

bool ty_is_integer(const Type *t) { return t && t->kind == TY_INT; }
bool ty_is_float(const Type *t) { return t && t->kind == TY_FLOAT; }
bool ty_is_numeric(const Type *t) { return ty_is_integer(t) || ty_is_float(t); }
bool ty_is_error(const Type *t) { return !t || t->kind == TY_ERROR; }

bool ty_is_copy(const Type *t) {
    if (!t) return true;
    switch (t->kind) {
        case TY_BOOL:
        case TY_CHAR:
        case TY_INT:
        case TY_FLOAT:
        case TY_ENUM:
        case TY_VEC2:
        case TY_VEC3:
        case TY_VEC4:
        case TY_QUAT:
        case TY_HANDLE:
        case TY_VOID:
        case TY_ERROR: return true;
        case TY_OPTION: return ty_is_copy(t->elem);
        default: return false;
    }
}

TypeKind ty_prim_from_name(Str name, uint8_t *bits, bool *is_signed) {
    struct {
        const char *n;
        TypeKind    k;
        uint8_t     b;
        bool        s;
    } table[] = {
        {"void", TY_VOID, 0, false},  {"bool", TY_BOOL, 0, false},
        {"char", TY_CHAR, 0, false},  {"str", TY_STR, 0, false},
        {"i8", TY_INT, 8, true},      {"i16", TY_INT, 16, true},
        {"i32", TY_INT, 32, true},    {"i64", TY_INT, 64, true},
        {"u8", TY_INT, 8, false},     {"u16", TY_INT, 16, false},
        {"u32", TY_INT, 32, false},   {"u64", TY_INT, 64, false},
        {"f32", TY_FLOAT, 32, false}, {"f64", TY_FLOAT, 64, false},
        {"Vec2", TY_VEC2, 0, false},  {"Vec3", TY_VEC3, 0, false},
        {"Vec4", TY_VEC4, 0, false},  {"Quat", TY_QUAT, 0, false},
        {"Mat3", TY_MAT3, 0, false},  {"Mat4", TY_MAT4, 0, false},
    };
    for (size_t i = 0; i < sizeof table / sizeof table[0]; i++) {
        if (str_eq_c(name, table[i].n)) {
            *bits      = table[i].b;
            *is_signed = table[i].s;
            return table[i].k;
        }
    }
    return TY_ERROR;
}
