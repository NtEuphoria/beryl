/* enforce_backend.c — profile lint, type mapping, and class emission. */
#include "enforce_int.h"

#include <stdio.h>

/* ---- output helpers ---------------------------------------------------- */

void ef_line(E *e, const char *fmt, ...) {
    sb_repeat(&e->out, '\t', e->indent);
    va_list ap;
    va_start(ap, fmt);
    sb_vfmt(&e->out, fmt, ap);
    va_end(ap);
    sb_char(&e->out, '\n');
}

void ef_blank(E *e) { sb_char(&e->out, '\n'); }

Str ef_prefixed(E *e, Str name) {
    SB sb;
    sb_init(&sb, e->a);
    if (!str_empty(e->prefix)) {
        sb_str(&sb, e->prefix);
        sb_char(&sb, '_');
    }
    sb_str(&sb, name);
    return sb_finish(&sb);
}

Str ef_tmp(E *e) {
    SB sb;
    sb_init(&sb, e->a);
    sb_fmt(&sb, "_t%d", e->tmp++);
    return sb_finish(&sb);
}

/* EnforceScript reserves words Beryl does not, `out` and `ref` most sharply,
 * and a collision is a bare "Broken expression" from Workbench with no hint of
 * the cause. Every emitted identifier goes through here. */
static bool is_enforce_keyword(Str s) {
    static const char *const kw[] = {
        "out",      "inout",    "ref",     "class",    "enum",     "void",
        "int",      "float",    "bool",    "string",   "vector",   "array",
        "map",      "set",      "new",     "delete",   "null",     "this",
        "super",    "override", "protected", "private", "static",  "const",
        "typedef",  "proto",    "native",  "sealed",   "modded",   "owned",
        "notnull",  "volatile", "autoptr", "if",       "else",     "while",
        "for",      "foreach",  "switch",  "case",     "default",  "break",
        "continue", "return",   "true",    "false",    "managed",  "local",
        "event",    "sizeof",   "typename", "Class",   "result",   "private"};
    for (size_t i = 0; i < sizeof kw / sizeof kw[0]; i++)
        if (str_eq_c(s, kw[i])) return true;
    return false;
}

Str ef_ident(E *e, Str name) {
    if (!is_enforce_keyword(name)) return name;
    SB sb;
    sb_init(&sb, e->a);
    sb_str(&sb, name);
    sb_char(&sb, '_');
    return sb_finish(&sb);
}

/* Base-game methods are PascalCase; Beryl's are snake_case. Converting keeps
 * generated script idiomatic without renaming anything in the Beryl source. */
Str ef_method_name(Str name) { return name; }

/* ---- type mapping ------------------------------------------------------ */

static Str opt_class(E *e, Type *t);

Str ef_type(E *e, Type *t) {
    if (!t) return str_from("void");
    switch (t->kind) {
        case TY_VOID: return str_from("void");
        case TY_BOOL: return str_from("bool");
        case TY_STR: return str_from("string");
        case TY_CHAR: return str_from("int");
        case TY_INT: return str_from("int");
        case TY_FLOAT: return str_from("float");
        case TY_VEC2:
        case TY_VEC3:
        case TY_VEC4: return str_from("vector");
        case TY_STRUCT:
        case TY_ENUM: return ef_prefixed(e, t->name);
        case TY_ERROR: return str_from("int");

        case TY_ARRAY:
        case TY_LIST: {
            SB sb;
            sb_init(&sb, e->a);
            sb_cstr(&sb, "array<");
            sb_str(&sb, ef_type_field(e, t->elem));
            sb_char(&sb, '>');
            return sb_finish(&sb);
        }
        case TY_MAP: {
            SB sb;
            sb_init(&sb, e->a);
            sb_cstr(&sb, "map<");
            sb_str(&sb, ef_type(e, t->key));
            sb_cstr(&sb, ", ");
            sb_str(&sb, ef_type_field(e, t->elem));
            sb_char(&sb, '>');
            return sb_finish(&sb);
        }
        /* Box and Rc are both just a reference; Enfusion already refcounts,
         * which is why Rc costs nothing on this target. */
        case TY_BOX:
        case TY_RC: return ef_type(e, t->elem);
        case TY_OPTION: return opt_class(e, t);
        default: return str_from("int");
    }
}

/* A member holding a class instance or a container of them needs `ref` to own
 * it; primitives and vectors do not. */
Str ef_type_field(E *e, Type *t) {
    if (!t) return str_from("void");
    bool owns = t->kind == TY_STRUCT || t->kind == TY_ARRAY || t->kind == TY_LIST ||
                t->kind == TY_MAP || t->kind == TY_BOX || t->kind == TY_RC ||
                t->kind == TY_OPTION;
    if (!owns) return ef_type(e, t);
    SB sb;
    sb_init(&sb, e->a);
    sb_cstr(&sb, "ref ");
    sb_str(&sb, ef_type(e, t));
    return sb_finish(&sb);
}

bool ef_needs_copy(Type *t) {
    return t && (t->kind == TY_STRUCT || t->kind == TY_ARRAY || t->kind == TY_LIST ||
                 t->kind == TY_MAP || t->kind == TY_OPTION);
}

bool ef_is_place(const Expr *x) {
    if (!x) return false;
    switch (x->kind) {
        case EX_PATH:
        case EX_SELF:
        case EX_FIELD:
        case EX_INDEX: return true;
        default: return false;
    }
}

/* `T?` has no engine equivalent, so a tiny wrapper class is generated for each
 * instantiation. Emitting one is cheaper than the sentinel values a hand
 * translation would reach for, and it cannot be silently wrong. */
static Str opt_class(E *e, Type *t) {
    Str inner = ef_type(e, t->elem);
    SB  nb;
    sb_init(&nb, e->a);
    sb_cstr(&nb, "Opt_");
    for (uint32_t i = 0; i < inner.len; i++) {
        char c  = inner.ptr[i];
        bool ok = (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9');
        sb_char(&nb, ok ? c : '_');
    }
    Str name = ef_prefixed(e, sb_finish(&nb));

    if (map_has(e->helpers_done, name)) return name;
    map_put(e->helpers_done, name, (void *)1);

    SB save    = e->out;
    int savein = e->indent;
    sb_init(&e->out, e->a);
    e->indent = 0;

    ef_line(e, "//! Generated by beryl: `%.*s?` has no engine equivalent.",
            (int)inner.len, inner.ptr);
    ef_line(e, "class %.*s", S(name));
    ef_line(e, "{");
    e->indent = 1;
    ef_line(e, "bool has;");
    ef_line(e, "%.*s val;", S(inner));
    e->indent = 0;
    ef_line(e, "}");
    ef_blank(e);

    sb_str(&e->helper, sb_finish(&e->out));
    e->out    = save;
    e->indent = savein;
    return name;
}

/* ---- profile lint ------------------------------------------------------ */

typedef struct {
    DiagBag *d;
    Arena   *a;
    uint32_t before;
} L;

static void lint_type(L *l, Type *t, Span at, const char *what) {
    if (!t) return;
    switch (t->kind) {
        case TY_INT:
            if (t->bits != 32 || !t->is_signed) {
                Diag *dg = diag_error(l->d, 701, at,
                                      "`%.*s` is not supported on the enfusion target",
                                      (int)ty_name(l->a, t).len, ty_name(l->a, t).ptr);
                diag_note(dg, "EnforceScript has one integer type, a signed 32-bit `int`");
                diag_help(dg, "use `i32` for %s", what);
            }
            break;
        case TY_FLOAT:
            if (t->bits != 32) {
                Diag *dg = diag_error(l->d, 701, at,
                                      "`f64` is not supported on the enfusion target");
                diag_note(dg, "EnforceScript has one floating type, a 32-bit `float`");
                diag_help(dg, "use `f32` for %s", what);
            }
            break;
        case TY_ARRAY:
        case TY_LIST:
        case TY_BOX:
        case TY_RC:
        case TY_OPTION:
        case TY_ERRUNION: lint_type(l, t->elem, at, what); break;
        case TY_MAP:
            lint_type(l, t->key, at, what);
            lint_type(l, t->elem, at, what);
            break;
        default: break;
    }
}

static void lint_expr(L *l, Expr *x) {
    if (!x) return;
    switch (x->kind) {
        case EX_UNSAFE: {
            Diag *dg = diag_error(l->d, 703, x->span,
                                  "`@unsafe` is forbidden on the enfusion target");
            diag_note(dg, "EnforceScript has no raw pointers, so there is no invariant "
                          "here to suspend");
            return;
        }
        case EX_UNARY: lint_expr(l, x->unary.operand); break;
        case EX_BINARY:
            lint_expr(l, x->binary.lhs);
            lint_expr(l, x->binary.rhs);
            break;
        case EX_CALL:
            lint_expr(l, x->call.callee);
            for (uint32_t i = 0; i < x->call.args.len; i++)
                lint_expr(l, x->call.args.data[i].value);
            break;
        case EX_FIELD: lint_expr(l, x->field.base); break;
        case EX_INDEX:
            lint_expr(l, x->index.base);
            lint_expr(l, x->index.index);
            break;
        case EX_CAST: lint_expr(l, x->cast.value); break;
        case EX_STRUCT_LIT:
            for (uint32_t i = 0; i < x->struct_lit.fields.len; i++)
                lint_expr(l, x->struct_lit.fields.data[i].value);
            break;
        case EX_ARRAY_LIT:
            for (uint32_t i = 0; i < x->array_lit.elems.len; i++)
                lint_expr(l, x->array_lit.elems.data[i]);
            break;
        case EX_IF:
            lint_expr(l, x->if_expr.cond);
            lint_expr(l, x->if_expr.then_blk);
            lint_expr(l, x->if_expr.else_blk);
            break;
        case EX_BLOCK:
            for (uint32_t i = 0; i < x->block.stmts.len; i++) {
                Stmt *s = x->block.stmts.data[i];
                if (!s) continue;
                switch (s->kind) {
                    case ST_LET:
                        if (s->let.init) lint_expr(l, s->let.init);
                        if (s->let.init && s->let.init->type)
                            lint_type(l, s->let.init->type, s->span, "this binding");
                        break;
                    case ST_EXPR:
                    case ST_RETURN:
                    case ST_DEFER: lint_expr(l, s->expr); break;
                    case ST_ASSIGN:
                        lint_expr(l, s->assign.target);
                        lint_expr(l, s->assign.value);
                        break;
                    case ST_WHILE:
                        lint_expr(l, s->while_st.cond);
                        lint_expr(l, s->while_st.body);
                        break;
                    case ST_FOR:
                        lint_expr(l, s->for_st.iter);
                        lint_expr(l, s->for_st.body);
                        break;
                    default: break;
                }
            }
            break;
        case EX_TRY: lint_expr(l, x->try_expr.inner); break;
        case EX_CATCH:
            lint_expr(l, x->catch_expr.value);
            lint_expr(l, x->catch_expr.handler);
            break;
        case EX_ORELSE:
            lint_expr(l, x->orelse_expr.value);
            lint_expr(l, x->orelse_expr.fallback);
            break;
        case EX_RANGE:
            lint_expr(l, x->range.lo);
            lint_expr(l, x->range.hi);
            break;
        default: break;
    }
}

static bool has_attr(Item *it, const char *name) {
    for (uint32_t i = 0; i < it->attrs.len; i++)
        if (str_eq_c(it->attrs.data[i].name, name)) return true;
    return false;
}

bool enfusion_lint(DiagBag *d, Program *p, EnfusionOpts o) {
    (void)o;
    L l = {d, p->a, diag_errors(d)};

    for (uint32_t m = 0; m < p->modules.len; m++) {
        Module *mod = p->modules.data[m];
        for (uint32_t i = 0; i < mod->items.len; i++) {
            Item *it = mod->items.data[i];

            if (has_attr(it, "unsafe")) {
                Diag *dg = diag_error(d, 703, it->span,
                                      "`@unsafe` is forbidden on the enfusion target");
                diag_note(dg, "the engine has no raw pointers, so the capability has "
                              "nothing to suspend");
            }

            switch (it->kind) {
                case IT_STRUCT:
                    for (uint32_t f = 0; f < it->strukt.fields.len; f++) {
                        Field *fl = &it->strukt.fields.data[f];
                        lint_type(&l, fl->rtype, fl->span, "this field");
                        lint_expr(&l, fl->deflt);
                    }
                    break;
                case IT_FN:
                    if (it->fn.generics.len) break; /* checked after monomorphization */
                    for (uint32_t q = 0; q < it->fn.params.len; q++)
                        lint_type(&l, it->fn.params.data[q].rtype,
                                  it->fn.params.data[q].span, "this parameter");
                    lint_type(&l, it->rtype, it->fn.ret ? it->fn.ret->span : it->span,
                              "this return type");
                    lint_expr(&l, it->fn.body);
                    break;
                case IT_CONST: lint_type(&l, it->rtype, it->span, "this constant"); break;
                default: break;
            }
        }
    }
    return diag_errors(d) == l.before;
}

/* ---- item emission ----------------------------------------------------- */

/* `!T` lowers to the idiom the base game itself uses: a bool return plus an
 * `out` parameter for the value. The error *tag* is not preserved on this
 * target, which is stated plainly in docs/ENFUSION.md rather than hidden. */
static void emit_signature(E *e, Item *it, bool is_static) {
    SB sb;
    sb_init(&sb, e->a);

    Type *ret     = it->rtype;
    bool  err     = ret && ret->kind == TY_ERRUNION;
    Str   ret_str = err ? str_from("bool") : ef_type(e, ret);

    sb_fmt(&sb, "%s%.*s %.*s(", is_static ? "static " : "", S(ret_str),
           S(ef_method_name(it->name)));

    bool first = true;
    for (uint32_t i = 0; i < it->fn.params.len; i++) {
        Param *pm = &it->fn.params.data[i];
        if (pm->is_self) continue; /* the receiver is `this` */
        if (!first) sb_cstr(&sb, ", ");
        first = false;
        if (pm->conv == CONV_INOUT || pm->conv == CONV_SET) sb_cstr(&sb, "out ");
        sb_str(&sb, ef_type(e, pm->rtype));
        sb_char(&sb, ' ');
        sb_str(&sb, ef_ident(e, pm->name));
        if (pm->deflt) {
            sb_cstr(&sb, " = ");
            /* Defaults must be literals in EnforceScript, which the checker
             * has already restricted them to in practice. */
            sb_str(&sb, ef_expr(e, pm->deflt));
        }
    }

    if (err && ret->elem && ret->elem->kind != TY_VOID) {
        if (!first) sb_cstr(&sb, ", ");
        sb_fmt(&sb, "out %.*s result", S(ef_type(e, ret->elem)));
    }

    sb_char(&sb, ')');
    ef_line(e, "%.*s", S(sb_finish(&sb)));
}

static void emit_doc(E *e, Str doc) {
    if (str_empty(doc)) return;
    uint32_t start = 0;
    for (uint32_t i = 0; i <= doc.len; i++) {
        if (i == doc.len || doc.ptr[i] == '\n') {
            Str l = str_new(doc.ptr + start, i - start);
            if (l.len) ef_line(e, "//! %.*s", S(l));
            else ef_line(e, "//!");
            start = i + 1;
        }
    }
}

static void emit_method(E *e, Item *it) {
    e->fn        = it;
    e->tmp       = 0;
    e->fn_is_err = it->rtype && it->rtype->kind == TY_ERRUNION;

    emit_doc(e, it->doc);
    emit_signature(e, it, str_empty(it->fn.recv));
    ef_line(e, "{");
    e->indent++;
    ef_block(e, it->fn.body);
    if (e->fn_is_err) ef_line(e, "return true;");
    e->indent--;
    ef_line(e, "}");
    e->fn = NULL;
}

static void emit_struct(E *e, Item *it) {
    Str cls = ef_prefixed(e, it->name);

    emit_doc(e, it->doc);
    ef_line(e, "class %.*s", S(cls));
    ef_line(e, "{");
    e->indent++;

    for (uint32_t i = 0; i < it->strukt.fields.len; i++) {
        Field *f = &it->strukt.fields.data[i];
        emit_doc(e, f->doc);
        ef_line(e, "%.*s %.*s;", S(ef_type_field(e, f->rtype)), S(ef_ident(e, f->name)));
    }
    ef_blank(e);

    /* Constructor: applies every field default the Beryl declaration gave. */
    ef_line(e, "void %.*s()", S(cls));
    ef_line(e, "{");
    e->indent++;
    for (uint32_t i = 0; i < it->strukt.fields.len; i++) {
        Field *f = &it->strukt.fields.data[i];
        if (f->deflt) ef_line(e, "%.*s = %.*s;", S(ef_ident(e, f->name)), S(ef_expr(e, f->deflt)));
        else if (f->rtype && f->rtype->kind == TY_LIST)
            ef_line(e, "%.*s = new %.*s();", S(ef_ident(e, f->name)), S(ef_type(e, f->rtype)));
        else if (f->rtype && f->rtype->kind == TY_MAP)
            ef_line(e, "%.*s = new %.*s();", S(ef_ident(e, f->name)), S(ef_type(e, f->rtype)));
    }
    e->indent--;
    ef_line(e, "}");

    /* Beryl structs are values; EnforceScript classes are references. Clone is
     * what preserves value semantics at the points the language requires a
     * copy, and the emitter inserts calls to it only there. */
    ef_blank(e);
    ef_line(e, "//! Value semantics: Beryl structs copy on assignment. Named");
    ef_line(e, "//! BerylCopy rather than Clone, which the engine base class already has.");
    ef_line(e, "%.*s BerylCopy()", S(cls));
    ef_line(e, "{");
    e->indent++;
    ef_line(e, "%.*s c = new %.*s();", S(cls), S(cls));
    for (uint32_t i = 0; i < it->strukt.fields.len; i++) {
        Field *f = &it->strukt.fields.data[i];
        if (ef_needs_copy(f->rtype) && f->rtype->kind == TY_STRUCT)
            ef_line(e, "c.%.*s = %.*s.BerylCopy();", S(ef_ident(e, f->name)), S(ef_ident(e, f->name)));
        else ef_line(e, "c.%.*s = %.*s;", S(ef_ident(e, f->name)), S(ef_ident(e, f->name)));
    }
    ef_line(e, "return c;");
    e->indent--;
    ef_line(e, "}");

    /* Methods declared on this type become members of the class. */
    for (uint32_t m = 0; m < e->p->modules.len; m++) {
        Module *mod = e->p->modules.data[m];
        for (uint32_t i = 0; i < mod->items.len; i++) {
            Item *fn = mod->items.data[i];
            if (fn->kind != IT_FN || !str_eq(fn->fn.recv, it->name)) continue;
            if (fn->fn.generics.len || !fn->fn.body) continue;
            ef_blank(e);
            emit_method(e, fn);
        }
    }

    e->indent--;
    ef_line(e, "}");
}

static void emit_enum(E *e, Item *it) {
    Str nm = ef_prefixed(e, it->name);
    emit_doc(e, it->doc);
    ef_line(e, "enum %.*s", S(nm));
    ef_line(e, "{");
    e->indent++;
    for (uint32_t i = 0; i < it->enom.variants.len; i++) {
        EnumVariant v     = it->enom.variants.data[i];
        bool        last  = (i + 1 == it->enom.variants.len);
        if (v.value)
            ef_line(e, "%.*s = %.*s%s", S(v.name), S(ef_expr(e, v.value)), last ? "" : ",");
        else ef_line(e, "%.*s%s", S(v.name), last ? "" : ",");
    }
    e->indent--;
    ef_line(e, "}");
}

/* Free functions have no home in a language without namespaces, so they become
 * static methods on a per-module holder class — the same shape as the base
 * game's own `SCR_Math`. */
static Str module_holder(E *e, Module *m) {
    SB sb;
    sb_init(&sb, e->a);
    for (uint32_t i = 0; i < m->path.len; i++) {
        Str seg = m->path.data[i];
        if (seg.len) {
            char c0 = seg.ptr[0];
            sb_char(&sb, (c0 >= 'a' && c0 <= 'z') ? (char)(c0 - 'a' + 'A') : c0);
            sb_str(&sb, str_slice(seg, 1, seg.len - 1));
        }
    }
    return ef_prefixed(e, sb_finish(&sb));
}

static E ef_new(Arena *a, SourceMap *sm, DiagBag *d, Program *p, EnfusionOpts o) {
    E e   = {0};
    e.a   = a;
    e.sm  = sm;
    e.d   = d;
    e.p   = p;
    e.prefix       = o.prefix;
    e.helpers_done = map_new(a);
    sb_init(&e.out, a);
    sb_init(&e.helper, a);
    return e;
}

Str enfusion_render_item(Arena *a, SourceMap *sm, DiagBag *d, Program *p, Item *it,
                         EnfusionOpts o) {
    E e = ef_new(a, sm, d, p, o);

    switch (it->kind) {
        case IT_STRUCT: emit_struct(&e, it); break;
        case IT_ENUM: emit_enum(&e, it); break;
        default: break;
    }

    SB final;
    sb_init(&final, a);
    sb_str(&final, sb_finish(&e.helper));
    sb_str(&final, sb_finish(&e.out));
    return sb_finish(&final);
}

Str enfusion_render_all(Arena *a, SourceMap *sm, DiagBag *d, Program *p, EnfusionOpts o) {
    E e = ef_new(a, sm, d, p, o);

    for (uint32_t m = 0; m < p->modules.len; m++) {
        Module *mod = p->modules.data[m];

        for (uint32_t i = 0; i < mod->items.len; i++) {
            Item *it = mod->items.data[i];
            if (it->kind == IT_ENUM) {
                emit_enum(&e, it);
                ef_blank(&e);
            }
        }
        for (uint32_t i = 0; i < mod->items.len; i++) {
            Item *it = mod->items.data[i];
            if (it->kind == IT_STRUCT) {
                emit_struct(&e, it);
                ef_blank(&e);
            }
        }

        /* Free functions, if the module has any. */
        bool any_free = false;
        for (uint32_t i = 0; i < mod->items.len; i++) {
            Item *it = mod->items.data[i];
            if (it->kind == IT_FN && str_empty(it->fn.recv) && !it->fn.generics.len &&
                it->fn.body && !str_eq_c(it->name, "main"))
                any_free = true;
        }
        if (!any_free) continue;

        Str holder = module_holder(&e, mod);
        ef_line(&e, "//! Free functions from module `%.*s`.",
                S(path_str(a, mod->path)));
        ef_line(&e, "class %.*s", S(holder));
        ef_line(&e, "{");
        e.indent++;
        bool first = true;
        for (uint32_t i = 0; i < mod->items.len; i++) {
            Item *it = mod->items.data[i];
            if (it->kind != IT_FN || !str_empty(it->fn.recv) || it->fn.generics.len ||
                !it->fn.body || str_eq_c(it->name, "main"))
                continue;
            if (!first) ef_blank(&e);
            first = false;
            emit_method(&e, it);
        }
        e.indent--;
        ef_line(&e, "}");
        ef_blank(&e);
    }

    SB final;
    sb_init(&final, a);
    sb_str(&final, sb_finish(&e.helper));
    sb_str(&final, sb_finish(&e.out));
    return sb_finish(&final);
}

Str enfusion_file_name(Arena *a, Item *it, EnfusionOpts o) {
    SB sb;
    sb_init(&sb, a);
    if (!str_empty(o.prefix)) {
        sb_str(&sb, o.prefix);
        sb_char(&sb, '_');
    }
    sb_str(&sb, it->name);
    sb_cstr(&sb, ".c");
    return sb_finish(&sb);
}

bool enfusion_emit(Arena *a, SourceMap *sm, DiagBag *d, Program *p, EnfusionOpts o) {
    if (!enfusion_lint(d, p, o)) return false;

    Str all = enfusion_render_all(a, sm, d, p, o);

    SB path;
    sb_init(&path, a);
    sb_str(&path, o.out_dir);
    sb_cstr(&path, "/");
    sb_str(&path, str_empty(o.prefix) ? str_from("Beryl") : o.prefix);
    sb_cstr(&path, "_Generated.c");

    /* Bytes are written directly: UTF-8 with no BOM, which Workbench requires
     * and which PowerShell's Out-File would quietly break. */
    FILE *fp = fopen(str_cstr(a, sb_finish(&path)), "wb");
    if (!fp) {
        fprintf(stderr, "beryl: cannot write into %.*s\n", S(o.out_dir));
        return false;
    }
    fwrite(all.ptr, 1, all.len, fp);
    fclose(fp);
    return true;
}
