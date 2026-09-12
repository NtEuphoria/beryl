/* enforce_backend.c — profile lint, type mapping, and class emission. */
#include "enforce_int.h"
#include "../common/fs.h"
#include "../common/symbol.h"
#include "../common/hash.h"
#include "../common/json.h"
#include "../sema/storage.h"

#include <stdio.h>
#include <math.h>
#include <float.h>
#include <string.h>

/* ---- output helpers ---------------------------------------------------- */

void ef_line(E *e, const char *fmt, ...) {
    uint32_t start = e->out.len;
    sb_repeat(&e->out, '\t', e->indent);
    va_list ap;
    va_start(ap, fmt);
    sb_vfmt(&e->out, fmt, ap);
    va_end(ap);
    sb_char(&e->out, '\n');
    if (e->map_enabled) {
        EfMapping mapping = {start, e->out.len - start, e->origin};
        vec_push(e->a, e->mappings, mapping);
    }
}

EfOrigin ef_expression_origin(E *e, Expr *x) {
    EfOrigin origin = e->origin;
    if (x) {
        origin.span = x->span;
        origin.expansion = x->has_expansion_site ? x->expansion_site : SPAN_NONE;
        origin.kind = x->has_expansion_site ? "default_expansion" : "prepared_expression";
    }
    return origin;
}

static EfOrigin item_origin(Item *it, const char *kind) {
    return (EfOrigin){.span=it->span, .expansion=SPAN_NONE, .kind=kind, .declaration=it->qual_name};
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

/* Internal symbols preserve declaration identity. Stable engine-facing names
 * belong to explicit exports, not a lossy spelling conversion. */
Str ef_method_name(E *e, Str name) { return symbol_encode(e->a,"m",name); }
Str ef_fn_name(E *e, Item *function) {
    Str exported=enfusion_export_name(e->exports,function);
    return exported.len ? exported : ef_method_name(e,function->name);
}
Str ef_field(E *e, Str name) { return symbol_encode(e->a,"f",name); }
Str ef_f32_literal(E *e,double value,Span span) {
    if (!isfinite(value) || value>FLT_MAX || value<-FLT_MAX) {
        diag_error(e->d,701,span,"Enfusion floating literal is outside the admitted finite binary32 range");
        return STR_EMPTY;
    }
    /* Widen the rounded binary32 value exactly, then print enough digits to
     * recover that double. This also avoids an above-FLT_MAX decimal spelling. */
    float rounded=(float)value;
    char buffer[64]; snprintf(buffer,sizeof buffer,"%.17g",(double)rounded);
    SB out; sb_init(&out,e->a); sb_cstr(&out,buffer);
    if (!strchr(buffer,'.') && !strchr(buffer,'e') && !strchr(buffer,'E')) sb_cstr(&out,".0");
    return sb_finish(&out);
}

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
        /* Vec2 and Vec4 are rejected by lint_type before they reach here; the
         * mapping is kept so a program with that error still renders. */
        case TY_VEC2:
        case TY_VEC3:
        case TY_VEC4: return str_from("vector");
        case TY_STRUCT:
        case TY_ENUM: {
            Str exported=enfusion_export_name(e->exports,t->decl);
            /* A mapped engine constructor belongs to a derived facade. Beryl
             * values retain the plain base constructor for literals and copies. */
            if (enfusion_export_constructor(e->exports,t->decl)) exported=STR_EMPTY;
            return exported.len ? exported : ef_prefixed(e, symbol_encode(e->a,"i",t->name));
        }
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

bool ef_is_literal(const Expr *x) {
    if (!x) return false;
    switch (x->kind) {
        case EX_INT:
        case EX_FLOAT:
        case EX_STR:
        case EX_CHAR:
        case EX_BOOL: return true;
        /* `-1` is still a literal; `-f()` is not. */
        case EX_UNARY: return x->unary.op == TK_MINUS && ef_is_literal(x->unary.operand);
        default: return false;
    }
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
    Str name = ef_prefixed(e, symbol_encode(e->a, "o", ty_name(e->a,t)));

    if (map_has(e->helpers_done, name)) return name;
    map_put(e->helpers_done, name, (void *)1);

    SB save    = e->out;
    EfMappings saved_maps = e->mappings;
    EfOrigin saved_origin = e->origin;
    e->mappings = (EfMappings){0};
    e->origin.kind = "value_helper";
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

    for (uint32_t i = 0; i < e->mappings.len; i++) {
        EfMapping mapping = e->mappings.data[i];
        mapping.start += e->helper.len;
        vec_push(e->a, e->helper_mappings, mapping);
    }
    sb_str(&e->helper, sb_finish(&e->out));
    e->mappings = saved_maps;
    e->origin = saved_origin;
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
        /* EnforceScript's `vector` is exactly three floats. Mapping Vec2 and
         * Vec4 onto it — which v0.1 did — silently gives a Vec2 a third
         * component and drops a Vec4's fourth. */
        case TY_VEC2:
        case TY_VEC4: {
            Diag *dg = diag_error(l->d, 701, at,
                                  "`%.*s` is not supported on the enfusion target",
                                  (int)ty_name(l->a, t).len, ty_name(l->a, t).ptr);
            diag_note(dg, "EnforceScript has one vector type, `vector`, which is "
                          "exactly three floats");
            diag_help(dg, "use `Vec3` for %s, or two `f32` fields", what);
            break;
        }
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

/* The generated struct copy helper calls array.Copy. Workbench 1.8.0.13
 * rejects its array<ref T> specializations for class/nested-array elements.
 * They also need recursive logical-value copying, which the current helper
 * does not implement. Reject these fields before emitting an invalid helper;
 * scalar arrays keep their existing admission. This is not full ownership lint. */
static void lint_field_copy(L *l, Field *field) {
    Type *type = field->rtype;
    if (!type || (type->kind != TY_ARRAY && type->kind != TY_LIST) || !type->elem) return;
    Type *element = type->elem;
    if (element->kind != TY_STRUCT && element->kind != TY_ARRAY && element->kind != TY_LIST) return;
    Diag *d = diag_error(l->d, 701, field->span,
                        "Enfusion field `%.*s` requires unsupported reference-array value copying",
                        S(field->name));
    diag_note(d, "the generated BerylCopy helper cannot use array.Copy for this strong-reference element type");
    diag_help(d, "keep this field outside the admitted Enfusion value profile until recursive collection copying is implemented; scalar array fields remain supported");
}

static void lint_expr(L *l, Expr *x) {
    if (!x) return;
    lint_type(l, x->type, x->span, "this expression");
    if (x->kind==EX_FLOAT && (!isfinite(x->float_lit.val) || x->float_lit.val>FLT_MAX || x->float_lit.val<-FLT_MAX))
        diag_error(l->d,701,x->span,"Enfusion floating literal is outside the admitted finite binary32 range");
    Expr *handled = x->kind == EX_TRY ? x->try_expr.inner :
                    x->kind == EX_CATCH ? x->catch_expr.value :
                    x->kind == EX_ORELSE ? x->orelse_expr.value : NULL;
    if (handled && handled->type && handled->type->kind == TY_ERRUNION &&
        (handled->kind != EX_CALL || handled->res_kind != RES_FN))
        diag_error(l->d, 701, x->span,
                   "this enfusion profile handles error unions only from direct calls");
    if (x->kind == EX_CATCH && x->type &&
        !(x->type->kind == TY_VOID || x->type->kind == TY_INT || x->type->kind == TY_FLOAT ||
          x->type->kind == TY_BOOL || x->type->kind == TY_CHAR || x->type->kind == TY_STR ||
          x->type->kind == TY_VEC3 || x->type->kind == TY_ENUM))
        diag_error(l->d, 701, x->span,
                   "this enfusion profile cannot construct the zero payload for this catch; use orelse");
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
    L l = {d, p->a, diag_errors(d)};
    if (!storage_admit(d,p,STORAGE_ENFUSION)) return false;
    enfusion_validate_exports(d,p,o);
    for (uint32_t i = 0; i < o.prefix.len; i++) {
        char c = o.prefix.ptr[i];
        if (!((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || c == '_' ||
              (i && c >= '0' && c <= '9'))) {
            diag_error(d,804,SPAN_NONE,"Enfusion prefix must be an ASCII identifier or empty");
            return false;
        }
    }

    for (uint32_t m = 0; m < p->modules.len; m++) {
        Module *mod = p->modules.data[m];
        for (uint32_t i = 0; i < mod->items.len; i++) {
            Item *it = mod->items.data[i];

            for (uint32_t k = 0; k < it->nlocals; k++) {
                Local *local = ((Local **)it->locals)[k];
                if (!local->is_param) lint_type(&l, local->type, local->span, "this local binding");
            }

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
                        lint_field_copy(&l, fl);
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
                case IT_TEST: lint_expr(&l, it->test.body); break;
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
static void emit_named_signature(E *e, Item *it, bool is_static, Str name) {
    SB sb;
    sb_init(&sb, e->a);

    Type *ret     = it->rtype;
    bool  err     = ret && ret->kind == TY_ERRUNION;
    Str   ret_str = err ? str_from("bool") : ef_type(e, ret);

    sb_fmt(&sb, "%s%.*s %.*s(", is_static ? "static " : "", S(ret_str),
           S(name));

    bool first = true;
    for (uint32_t i = 0; i < it->fn.params.len; i++) {
        Param *pm = &it->fn.params.data[i];
        if (pm->is_self) continue; /* the receiver is `this` */
        if (!first) sb_cstr(&sb, ", ");
        first = false;
        if (pm->conv == CONV_INOUT || pm->conv == CONV_SET) sb_cstr(&sb, "out ");
        sb_str(&sb, ef_type(e, pm->rtype));
        sb_char(&sb, ' ');
        sb_str(&sb, ef_local(e, pm->name, pm->span));
        /* Only a literal default goes in the signature. Anything else may
         * need statements to build, and there is nowhere to put them here —
         * rendering one emitted `_t0.x = 7;` into the class body, which is
         * not valid EnforceScript. Call sites fill every omitted argument
         * (see call_args), so a missing signature default costs nothing;
         * keeping the literal ones just makes the script read naturally. */
        if (pm->deflt && ef_is_literal(pm->deflt)) {
            sb_cstr(&sb, " = ");
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

Str ef_local(E *e, Str name, Span declaration) {
    Str id = symbol_encode(e->a,"l",name);
    SB sb;
    sb_init(&sb, e->a);
    sb_fmt(&sb, "%.*s_%u", S(id), declaration.offset);
    return sb_finish(&sb);
}

static void emit_method(E *e, Item *it) {
    EfOrigin previous_origin = e->origin;
    e->origin = item_origin(it, "function");
    e->fn        = it;
    e->tmp       = 0;
    e->fn_is_err = it->rtype && it->rtype->kind == TY_ERRUNION;

    emit_doc(e, it->doc);
    bool has_self = it->fn.params.len && it->fn.params.data[0].is_self;
    emit_named_signature(e, it, !has_self, ef_fn_name(e,it));
    ef_line(e, "{");
    e->indent++;
    ef_block(e, it->fn.body);
    if (e->fn_is_err) ef_line(e, "return true;");
    e->indent--;
    ef_line(e, "}");
    e->fn = NULL;
    e->origin = previous_origin;
}

static void emit_struct(E *e, Item *it) {
    e->origin = item_origin(it, "type");
    Str cls = ef_type(e, it->rtype);

    emit_doc(e, it->doc);
    ef_line(e, "class %.*s", S(cls));
    ef_line(e, "{");
    e->indent++;

    for (uint32_t i = 0; i < it->strukt.fields.len; i++) {
        Field *f = &it->strukt.fields.data[i];
        e->origin = item_origin(it, "field"); e->origin.span = f->span;
        emit_doc(e, f->doc);
        ef_line(e, "%.*s %.*s;", S(ef_type_field(e, f->rtype)), S(ef_field(e, f->name)));
    }
    ef_blank(e);

    /* Constructor: applies every field default the Beryl declaration gave. */
    e->origin = item_origin(it, "constructor");
    ef_line(e, "void %.*s()", S(cls));
    ef_line(e, "{");
    e->indent++;
    for (uint32_t i = 0; i < it->strukt.fields.len; i++) {
        Field *f = &it->strukt.fields.data[i];
        e->origin = item_origin(it, "field_default"); e->origin.span = f->deflt ? f->deflt->span : f->span;
        if (f->deflt) ef_line(e, "%.*s = %.*s;", S(ef_field(e, f->name)), S(ef_expr(e, f->deflt)));
        else if (f->rtype && f->rtype->kind == TY_LIST)
            ef_line(e, "%.*s = new %.*s();", S(ef_field(e, f->name)), S(ef_type(e, f->rtype)));
        else if (f->rtype && f->rtype->kind == TY_MAP)
            ef_line(e, "%.*s = new %.*s();", S(ef_field(e, f->name)), S(ef_type(e, f->rtype)));
    }
    e->indent--;
    e->origin = item_origin(it, "constructor");
    ef_line(e, "}");

    /* Beryl structs are values; EnforceScript classes are references. Clone is
     * what preserves value semantics at the points the language requires a
     * copy, and the emitter inserts calls to it only there. */
    ef_blank(e);
    e->origin = item_origin(it, "value_helper");
    ef_line(e, "//! Value semantics: Beryl structs copy on assignment. Named");
    ef_line(e, "//! BerylCopy rather than Clone, which the engine base class already has.");
    ef_line(e, "%.*s BerylCopy()", S(cls));
    ef_line(e, "{");
    e->indent++;
    ef_line(e, "%.*s c = new %.*s();", S(cls), S(cls));
    for (uint32_t i = 0; i < it->strukt.fields.len; i++) {
        Field *f  = &it->strukt.fields.data[i];
        e->origin.span = f->span;
        Str    fn = ef_field(e, f->name);
        if (!f->rtype) {
            ef_line(e, "c.%.*s = %.*s;", S(fn), S(fn));
            continue;
        }
        switch (f->rtype->kind) {
            case TY_STRUCT:
                ef_line(e, "c.%.*s = %.*s.BerylCopy();", S(fn), S(fn));
                break;
            case TY_ARRAY:
            case TY_LIST:
            case TY_MAP:
                /* A container is a reference here, so copying the field would
                 * alias it and quietly break value semantics. */
                ef_line(e, "c.%.*s = new %.*s();", S(fn), S(ef_type(e, f->rtype)));
                ef_line(e, "c.%.*s.Copy(%.*s);", S(fn), S(fn));
                break;
            default: ef_line(e, "c.%.*s = %.*s;", S(fn), S(fn)); break;
        }
    }
    e->origin = item_origin(it, "value_helper");
    ef_line(e, "return c;");
    e->indent--;
    ef_line(e, "}");

    /* Methods declared on this type become members of the class. */
    for (uint32_t m = 0; m < e->p->modules.len; m++) {
        Module *mod = e->p->modules.data[m];
        for (uint32_t i = 0; i < mod->items.len; i++) {
            Item *fn = mod->items.data[i];
            if (fn->kind != IT_FN || fn->fn.recv_decl != it) continue;
            if (fn->fn.generics.len || !fn->fn.body) continue;
            ef_blank(e);
            emit_method(e, fn);
        }
    }

    e->indent--;
    ef_line(e, "}");

    Item *initializer=enfusion_export_constructor(e->exports,it);
    if (initializer) {
        e->origin = item_origin(initializer, "exported_constructor");
        Str exported=enfusion_export_name(e->exports,it);
        ef_blank(e);
        ef_line(e,"//! Engine interface; inherited state occupies this same object.");
        ef_line(e,"class %.*s : %.*s",S(exported),S(cls));
        ef_line(e,"{"); e->indent++;
        emit_named_signature(e,initializer,false,exported);
        ef_line(e,"{"); e->indent++;
        SB call; sb_init(&call,e->a); sb_str(&call,ef_fn_name(e,initializer)); sb_char(&call,'(');
        for (uint32_t q=1;q<initializer->fn.params.len;q++) {
            Param *pm=&initializer->fn.params.data[q];
            if (q>1) sb_cstr(&call,", ");
            sb_str(&call,ef_local(e,pm->name,pm->span));
        }
        sb_cstr(&call,");"); ef_line(e,"%.*s",S(sb_finish(&call)));
        e->indent--; ef_line(e,"}"); e->indent--; ef_line(e,"}");
    }
}

static void emit_enum(E *e, Item *it) {
    e->origin = item_origin(it, "enum");
    Str nm = ef_type(e, it->rtype);
    emit_doc(e, it->doc);
    ef_line(e, "enum %.*s", S(nm));
    ef_line(e, "{");
    e->indent++;
    for (uint32_t i = 0; i < it->enom.variants.len; i++) {
        EnumVariant v     = it->enom.variants.data[i];
        e->origin.span = v.span;
        bool        last  = (i + 1 == it->enom.variants.len);
        if (v.value)
            ef_line(e, "%.*s = %.*s%s", S(symbol_encode(e->a,"v",v.name)), S(ef_expr(e, v.value)), last ? "" : ",");
        else ef_line(e, "%.*s%s", S(symbol_encode(e->a,"v",v.name)), last ? "" : ",");
    }
    e->indent--;
    ef_line(e, "}");
}

/* Free functions have no home in a language without namespaces, so they become
 * static methods on a per-module holder class — the same shape as the base
 * game's own `SCR_Math`. */
Str ef_module_holder(E *e, Module *m) {
    return ef_prefixed(e,symbol_encode(e->a,"h",path_str(e->a,m->path)));
}

static E ef_new(Arena *a, SourceMap *sm, DiagBag *d, Program *p, EnfusionOpts o) {
    E e   = {0};
    e.a   = a;
    e.sm  = sm;
    e.d   = d;
    e.p   = p;
    e.prefix       = o.prefix;
    e.exports      = o.exports;
    e.map_enabled  = o.source_map.len != 0;
    e.origin = (EfOrigin){.span=SPAN_NONE,.expansion=SPAN_NONE,.kind="generated"};
    e.helpers_done = map_new(a);
    e.memo         = map_new(a);
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

static void mapped_span(E *e, SB *json, Span span) {
    SourceFile *source = span_is_none(span) ? NULL : srcmap_get(e->sm, span.file);
    if (!source || span.offset > source->text.len || span.len > source->text.len - span.offset) {
        sb_cstr(json, "null"); return;
    }
    LineCol loc = srcmap_linecol(e->sm, span);
    sb_cstr(json, "{\"path\":"); json_string(json, source->path);
    sb_fmt(json, ",\"file_id\":%u,\"byte_offset\":%u,\"byte_length\":%u,\"line\":%u,\"column\":%u}",
           span.file, span.offset, span.len, loc.line, loc.col);
}

static Str map_json(E *e, Str generated) {
    SB json; sb_init(&json, e->a);
    sb_cstr(&json, "{\"schema_version\":1,\"operation\":\"source_map\",\"target\":\"enfusion\",\"column_unit\":\"byte\"");
    sb_cstr(&json, ",\"mapping_precision\":\"generated line associated with original span; no token-column interpolation\"");
    sb_cstr(&json, ",\"generated\":{\"file\":");
    SB file; sb_init(&file, e->a); sb_str(&file, e->prefix.len ? e->prefix : STR_LIT("Beryl")); sb_cstr(&file, "_Generated.c");
    json_string(&json, sb_finish(&file));
    sb_fmt(&json, ",\"bytes\":%u,\"sha256\":", generated.len); json_string(&json, hash256_str(e->a, generated));
    sb_cstr(&json, "},\"sources\":[");
    for (uint32_t i = 0; i < srcmap_count(e->sm); i++) {
        SourceFile *source = srcmap_get(e->sm, i);
        if (i) sb_char(&json, ',');
        sb_cstr(&json, "{\"path\":"); json_string(&json, source->path);
        sb_cstr(&json, ",\"sha256\":"); json_string(&json, hash256_str(e->a, source->text)); sb_char(&json, '}');
    }
    sb_cstr(&json, "],\"mappings\":[");
    uint32_t cursor = 0, line = 1, count = 0;
    for (unsigned part = 0; part < 2; part++) {
        EfMappings *maps = part ? &e->mappings : &e->helper_mappings;
        uint32_t base = part ? e->helper.len : 0;
        for (uint32_t i = 0; i < maps->len; i++) {
            EfMapping *mapping = &maps->data[i];
            uint32_t start = base + mapping->start;
            while (cursor < start && cursor < generated.len) if (generated.ptr[cursor++] == '\n') line++;
            if (count++) sb_char(&json, ',');
            sb_fmt(&json, "{\"generated\":{\"byte_offset\":%u,\"byte_length\":%u,\"line\":%u,\"column\":1},\"kind\":",
                   start, mapping->length, line);
            json_string(&json, str_from(mapping->origin.kind ? mapping->origin.kind : "generated"));
            sb_cstr(&json, ",\"original\":"); mapped_span(e, &json, mapping->origin.span);
            sb_cstr(&json, ",\"expansion_site\":"); mapped_span(e, &json, mapping->origin.expansion);
            sb_cstr(&json, ",\"declaration\":");
            if (mapping->origin.declaration.len) json_string(&json, mapping->origin.declaration); else sb_cstr(&json, "null");
            sb_char(&json, '}');
        }
    }
    sb_cstr(&json, "],\"exports\":[");
    for (uint32_t i = 0; i < e->exports.len; i++) {
        EnfusionExport *ex = &e->exports.data[i];
        if (i) sb_char(&json, ',');
        sb_cstr(&json, "{\"source\":"); json_string(&json, ex->source);
        sb_cstr(&json, ",\"name\":"); json_string(&json, ex->name); sb_char(&json, '}');
    }
    sb_cstr(&json, "]}\n"); return sb_finish(&json);
}

static Str render_all_mapped(Arena *a, SourceMap *sm, DiagBag *d, Program *p, EnfusionOpts o, Str *mapping) {
    E e = ef_new(a, sm, d, p, o);

    for (uint32_t m = 0; m < p->modules.len; m++) {
        Module *mod = p->modules.data[m];
        e.origin = (EfOrigin){.span=SPAN_NONE,.expansion=SPAN_NONE,.kind="module_holder"};

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
        ModuleScope *scope = mod->scope;
        if (scope && scope->files.data[0] != mod) continue;
        ItemVec free_items = {0};
        for (uint32_t mi = 0; mi < p->modules.len; mi++) {
            Module *part = p->modules.data[mi];
            if (!prog_same_module(mod,part)) continue;
            for (uint32_t i = 0; i < part->items.len; i++) {
                Item *it = part->items.data[i];
                if (it->kind == IT_FN && str_empty(it->fn.recv) && !it->fn.generics.len &&
                    it->fn.body && !str_eq_c(it->name,"main")) vec_push(a,free_items,it);
            }
        }
        if (!free_items.len) continue;

        Str holder = ef_module_holder(&e, mod);
        e.origin = (EfOrigin){.span=SPAN_NONE,.expansion=SPAN_NONE,.kind="module_holder"};
        ef_line(&e, "//! Free functions from module `%.*s`.",
                S(path_str(a, mod->path)));
        ef_line(&e, "class %.*s", S(holder));
        ef_line(&e, "{");
        e.indent++;
        bool first = true;
        for (uint32_t i = 0; i < free_items.len; i++) {
            Item *it = free_items.data[i];
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
    Str generated = sb_finish(&final);
    if (mapping) *mapping = map_json(&e, generated);
    return generated;
}

Str enfusion_render_all(Arena *a, SourceMap *sm, DiagBag *d, Program *p, EnfusionOpts o) {
    return render_all_mapped(a, sm, d, p, o, NULL);
}

Str enfusion_file_name(Arena *a, Item *it, EnfusionOpts o) {
    SB sb;
    sb_init(&sb, a);
    Str exported=enfusion_export_name(o.exports,it);
    if (!exported.len && !str_empty(o.prefix)) {
        sb_str(&sb, o.prefix);
        sb_char(&sb, '_');
    }
    sb_str(&sb, exported.len ? exported : symbol_encode(a,"i",it->qual_name));
    sb_cstr(&sb, ".c");
    return sb_finish(&sb);
}

bool enfusion_emit(Arena *a, SourceMap *sm, DiagBag *d, Program *p, EnfusionOpts o) {
    if (!enfusion_lint(d, p, o)) return false;

    Str mapping = STR_EMPTY;
    Str all = render_all_mapped(a, sm, d, p, o, o.source_map.len ? &mapping : NULL);
    if (diag_errors(d)) return false;

    SB path;
    sb_init(&path, a);
    sb_str(&path, o.out_dir);
    sb_cstr(&path, "/");
    sb_str(&path, str_empty(o.prefix) ? str_from("Beryl") : o.prefix);
    sb_cstr(&path, "_Generated.c");

    const char *generated_path = str_cstr(a, sb_finish(&path));
    if (o.source_map.len) {
        const char *map_path = fs_absolute(a, str_cstr(a, o.source_map));
        const char *code_path = fs_absolute(a, generated_path);
#ifdef _WIN32
        bool same = map_path && code_path && _stricmp(map_path, code_path) == 0;
#else
        bool same = map_path && code_path && strcmp(map_path, code_path) == 0;
#endif
        for (uint32_t i = 0; !same && i < srcmap_count(sm); i++) {
            SourceFile *source = srcmap_get(sm, i);
            const char *source_path = fs_absolute(a, str_cstr(a, source->path));
#ifdef _WIN32
            same = map_path && source_path && _stricmp(map_path, source_path) == 0;
#else
            same = map_path && source_path && strcmp(map_path, source_path) == 0;
#endif
        }
        if (!map_path || !code_path || same) {
            diag_error(d,804,SPAN_NONE,"source map must use a separate output path that does not overwrite source or generated code");
            return false;
        }
    }

    /* Bytes are written directly: UTF-8 with no BOM, which Workbench requires
     * and which PowerShell's Out-File would quietly break. */
    if (!fs_write(generated_path, all)) {
        fprintf(stderr, "beryl: cannot write into %.*s\n", S(o.out_dir));
        return false;
    }
    if (o.source_map.len && !fs_write(str_cstr(a, o.source_map), mapping)) {
        fprintf(stderr, "beryl: cannot write source map %.*s\n", S(o.source_map));
        return false;
    }
    return true;
}
