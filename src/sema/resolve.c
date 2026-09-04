#include "resolve.h"

#include "constfold.h"

Program *prog_new(Arena *a) {
    Program *p = ARENA_NEW(a, Program);
    p->a       = a;
    p->types   = types_new(a);
    p->items   = map_new(a);
    p->shorts  = map_new(a);
    p->methods = map_new(a);
    return p;
}

void prog_add_module(Program *p, Module *m) { vec_push(p->a, p->modules, m); }

Item *prog_item(Program *p, Str qualified) { return (Item *)map_get(p->items, qualified); }
Item *prog_short(Program *p, Str name) { return (Item *)map_get(p->shorts, name); }

Item *prog_method(Program *p, Str recv, Str method) {
    SB sb;
    sb_init(&sb, p->a);
    sb_str(&sb, recv);
    sb_char(&sb, '.');
    sb_str(&sb, method);
    return (Item *)map_get(p->methods, sb_finish(&sb));
}

static Str join2(Arena *a, Str base, Str name) {
    SB sb;
    sb_init(&sb, a);
    if (!str_empty(base)) {
        sb_str(&sb, base);
        sb_char(&sb, '.');
    }
    sb_str(&sb, name);
    return sb_finish(&sb);
}

/* ---- pass 1: collect items --------------------------------------------- */

static void collect(DiagBag *d, Program *p, Module *m) {
    Str modpath = path_str(p->a, m->path);

    for (uint32_t i = 0; i < m->items.len; i++) {
        Item *it  = m->items.data[i];
        it->owner = m;

        if (it->kind == IT_USE) continue;

        if (it->kind == IT_FN && !str_empty(it->fn.recv)) {
            /* Methods live in a separate namespace keyed by receiver type. */
            Str key = join2(p->a, it->fn.recv, it->name);
            if (map_has(p->methods, key)) {
                Item *prev = (Item *)map_get(p->methods, key);
                Diag *dg   = diag_error(d, 308, it->span, "method `%.*s` is defined twice",
                                        (int)key.len, key.ptr);
                diag_label(dg, prev->span, "first definition here");
                diag_label(dg, it->span, "defined again here");
            } else {
                map_put(p->methods, key, it);
            }
            it->qual_name = join2(p->a, modpath, key);
            continue;
        }

        if (it->kind == IT_TEST) {
            it->qual_name = join2(p->a, modpath, it->name);
            continue; /* tests are not referenceable by name */
        }

        it->qual_name = join2(p->a, modpath, it->name);

        if (map_has(p->items, it->qual_name)) {
            Item *prev = (Item *)map_get(p->items, it->qual_name);
            Diag *dg   = diag_error(d, 308, it->span, "`%.*s` is defined twice",
                                    (int)it->name.len, it->name.ptr);
            diag_label(dg, prev->span, "first definition here");
            diag_label(dg, it->span, "defined again here");
            continue;
        }
        map_put(p->items, it->qual_name, it);
        if (!map_has(p->shorts, it->name)) map_put(p->shorts, it->name, it);
    }
}

/* ---- pass 2: create named types ---------------------------------------- */

static void make_named_types(Program *p, Module *m) {
    for (uint32_t i = 0; i < m->items.len; i++) {
        Item *it = m->items.data[i];
        if (it->kind == IT_STRUCT)
            it->rtype = ty_named(p->types, TY_STRUCT, it->name, it);
        else if (it->kind == IT_ENUM)
            it->rtype = ty_named(p->types, TY_ENUM, it->name, it);
    }
}

/* ---- type expression resolution ---------------------------------------- */

/* Generic containers are intrinsic: on the Enfusion target they lower to the
 * engine's own `array` and `map`, which is both faster and smaller than any
 * reimplementation could be. */
static TypeKind container_kind(Str name, uint32_t *arity) {
    if (str_eq_c(name, "List")) { *arity = 1; return TY_LIST; }
    if (str_eq_c(name, "Box")) { *arity = 1; return TY_BOX; }
    if (str_eq_c(name, "Rc")) { *arity = 1; return TY_RC; }
    if (str_eq_c(name, "Handle")) { *arity = 1; return TY_HANDLE; }
    if (str_eq_c(name, "Pool")) { *arity = 1; return TY_POOL; }
    if (str_eq_c(name, "Map")) { *arity = 2; return TY_MAP; }
    return TY_ERROR;
}

Type *resolve_type_expr(Program *p, DiagBag *d, TypeExpr *te) {
    if (!te) return ty_prim(p->types, TY_VOID);

    switch (te->kind) {
        case TE_OPTION: return ty_option(p->types, resolve_type_expr(p, d, te->elem));
        case TE_ERRUNION: return ty_errunion(p->types, resolve_type_expr(p, d, te->elem));
        case TE_ARRAY: {
            Type    *elem = resolve_type_expr(p, d, te->elem);
            uint64_t n    = 0;
            const_eval_len(p->a, d, p, te->len, &n);
            return ty_array(p->types, elem, n);
        }
        case TE_PATH: break;
        default: return ty_prim(p->types, TY_ERROR);
    }

    if (te->segs.len == 0) return ty_prim(p->types, TY_ERROR);
    Str last = te->segs.data[te->segs.len - 1];

    uint32_t arity = 0;
    TypeKind ck    = container_kind(last, &arity);
    if (ck != TY_ERROR) {
        if (te->args.len != arity) {
            diag_error(d, 302, te->span, "`%.*s` takes %u type argument%s, found %u",
                       (int)last.len, last.ptr, arity, arity == 1 ? "" : "s", te->args.len);
            return ty_prim(p->types, TY_ERROR);
        }
        if (ck == TY_MAP)
            return ty_map(p->types, resolve_type_expr(p, d, te->args.data[0]),
                          resolve_type_expr(p, d, te->args.data[1]));
        return ty_wrap(p->types, ck, resolve_type_expr(p, d, te->args.data[0]));
    }

    uint8_t  bits = 0;
    bool     sign = false;
    TypeKind pk   = ty_prim_from_name(last, &bits, &sign);
    if (pk != TY_ERROR) {
        if (pk == TY_INT) return ty_int(p->types, bits, sign);
        if (pk == TY_FLOAT) return ty_float(p->types, bits);
        return ty_prim(p->types, pk);
    }

    Item *it = prog_item(p, path_str(p->a, te->segs));
    if (!it) it = prog_short(p, last);
    if (it && (it->kind == IT_STRUCT || it->kind == IT_ENUM) && it->rtype) return it->rtype;

    /* A bare single-uppercase-ish name inside a generic item is a type
     * parameter; monomorphization substitutes it later. */
    if (te->segs.len == 1 && last.len <= 2) return ty_typeparam(p->types, last);

    Diag *dg = diag_error(d, 302, te->span, "unknown type `%.*s`", (int)last.len, last.ptr);
    diag_help(dg, "check the spelling, or add a `use` for the module that defines it");
    return ty_prim(p->types, TY_ERROR);
}

/* ---- pass 3: resolve declared types ------------------------------------ */

static void resolve_decls(DiagBag *d, Program *p, Module *m) {
    for (uint32_t i = 0; i < m->items.len; i++) {
        Item *it = m->items.data[i];
        switch (it->kind) {
            case IT_STRUCT:
                for (uint32_t f = 0; f < it->strukt.fields.len; f++) {
                    Field *fl = &it->strukt.fields.data[f];
                    fl->rtype = resolve_type_expr(p, d, fl->type);
                    fl->index = f;
                    for (uint32_t g = 0; g < f; g++) {
                        if (str_eq(it->strukt.fields.data[g].name, fl->name)) {
                            Diag *dg = diag_error(d, 308, fl->span,
                                                  "duplicate field `%.*s`",
                                                  (int)fl->name.len, fl->name.ptr);
                            diag_label(dg, it->strukt.fields.data[g].span,
                                       "first declared here");
                            diag_label(dg, fl->span, "declared again here");
                            break;
                        }
                    }
                }
                break;
            case IT_FN:
                for (uint32_t q = 0; q < it->fn.params.len; q++) {
                    Param *pm = &it->fn.params.data[q];
                    if (pm->is_self) {
                        Item *recv = prog_short(p, it->fn.recv);
                        pm->rtype  = (recv && recv->rtype) ? recv->rtype
                                                           : ty_prim(p->types, TY_ERROR);
                        if (!recv)
                            diag_error(d, 302, pm->span, "unknown receiver type `%.*s`",
                                       (int)it->fn.recv.len, it->fn.recv.ptr);
                    } else {
                        pm->rtype = resolve_type_expr(p, d, pm->type);
                    }
                }
                it->rtype = it->fn.ret ? resolve_type_expr(p, d, it->fn.ret)
                                       : ty_prim(p->types, TY_VOID);
                break;
            case IT_CONST:
                it->rtype = it->konst.type ? resolve_type_expr(p, d, it->konst.type) : NULL;
                break;
            default: break;
        }
    }
}

/* ---- module cycles ----------------------------------------------------- */

typedef enum { WHITE = 0, GREY, BLACK } Mark;

static bool visit(DiagBag *d, Program *p, Map *index, Map *marks, Module *m) {
    Str key = path_str(p->a, m->path);
    intptr_t st = (intptr_t)map_get(marks, key);
    if (st == BLACK) return true;
    if (st == GREY) {
        Diag *dg = diag_error(d, 309, m->span, "module `%.*s` is part of an import cycle",
                              (int)key.len, key.ptr);
        diag_note(dg, "Beryl forbids circular module dependencies, which is what keeps "
                      "resolution a single ordered pass rather than a fixpoint");
        return false;
    }
    map_put(marks, key, (void *)(intptr_t)GREY);

    bool ok = true;
    for (uint32_t i = 0; i < m->items.len; i++) {
        Item *it = m->items.data[i];
        if (it->kind != IT_USE || it->use_.path.len < 2) continue;
        /* `use a.b.Name` imports module `a.b`. */
        StrVec modpath = {0};
        for (uint32_t s = 0; s + 1 < it->use_.path.len; s++)
            vec_push(p->a, modpath, it->use_.path.data[s]);
        Module *dep = (Module *)map_get(index, path_str(p->a, modpath));
        if (dep && dep != m) ok = visit(d, p, index, marks, dep) && ok;
    }

    map_put(marks, key, (void *)(intptr_t)BLACK);
    return ok;
}

bool resolve_program(DiagBag *d, Program *p) {
    uint32_t before = diag_errors(d);

    for (uint32_t i = 0; i < p->modules.len; i++) collect(d, p, p->modules.data[i]);
    for (uint32_t i = 0; i < p->modules.len; i++) make_named_types(p, p->modules.data[i]);
    for (uint32_t i = 0; i < p->modules.len; i++) resolve_decls(d, p, p->modules.data[i]);

    Map *index = map_new(p->a);
    Map *marks = map_new(p->a);
    for (uint32_t i = 0; i < p->modules.len; i++)
        map_put(index, path_str(p->a, p->modules.data[i]->path), p->modules.data[i]);
    for (uint32_t i = 0; i < p->modules.len; i++)
        visit(d, p, index, marks, p->modules.data[i]);

    return diag_errors(d) == before;
}
