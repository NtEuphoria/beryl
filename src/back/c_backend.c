/* c_backend.c — C11 emission. */
#include "c_backend.h"

#include "../common/map.h"
#include "../sema/intrinsic.h"
#include "../sema/constfold.h"
#include "../sema/types.h"

typedef struct {
    Arena     *a;
    SourceMap *sm;
    DiagBag   *d;
    Program   *p;
    SB         types; /* struct and helper typedefs, in dependency order */
    SB         protos;
    SB         out;   /* function bodies */
    SB        *cur;   /* where statements are currently written */
    Map       *emitted;
    Map       *memo;  /* (Expr*, epoch) -> rendered text; see gen_expr */
    uint32_t   epoch; /* bumped per statement so a memo never crosses one */
    int        indent;
    int        tmp;
    Item      *fn;      /* function being emitted */
    Str        ret_ctype; /* its C return type, for `try` early returns */
} G;

/* ---- names ------------------------------------------------------------- */

static bool is_c_keyword(Str s) {
    static const char *const kw[] = {
        "auto", "break", "case", "char", "const", "continue", "default", "do", "double",
        "else", "enum", "extern", "float", "for", "goto", "if", "inline", "int", "long",
        "register", "restrict", "return", "short", "signed", "sizeof", "static", "struct",
        "switch", "typedef", "union", "unsigned", "void", "volatile", "while", "bool",
        "true", "false", "main", "printf", "abort", "exit"};
    for (size_t i = 0; i < sizeof kw / sizeof kw[0]; i++)
        if (str_eq_c(s, kw[i])) return true;
    return false;
}

/* `flight.pid.Pid.step` -> `flight_pid_Pid_step`.
 *
 * Every character that is not valid in a C identifier is replaced, because a
 * test's name is prose ("a non-positive dt produces no output") and still has
 * to become a callable symbol. */
static Str mangle(G *g, Str qual) {
    SB sb;
    sb_init(&sb, g->a);
    for (uint32_t i = 0; i < qual.len; i++) {
        char c  = qual.ptr[i];
        bool ok = (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') ||
                  (c >= '0' && c <= '9') || c == '_';
        sb_char(&sb, ok ? c : '_');
    }
    return sb_finish(&sb);
}

/* Test labels are prose and can collide once sanitized, so a test's symbol
 * carries its source offset, which is unique within a build. */
static Str item_symbol(G *g, Item *it) {
    Str base = mangle(g, it->qual_name);
    if (it->kind != IT_TEST) return base;
    SB sb;
    sb_init(&sb, g->a);
    sb_fmt(&sb, "%.*s_%u", (int)base.len, base.ptr, it->span.offset);
    return sb_finish(&sb);
}

static Str local_name(G *g, Str n) {
    if (!is_c_keyword(n)) return n;
    SB sb;
    sb_init(&sb, g->a);
    sb_str(&sb, n);
    sb_char(&sb, '_');
    return sb_finish(&sb);
}

/* A C identifier derived from a type's canonical name. */
static Str type_id(G *g, const Type *t) {
    Str n = ty_name(g->a, t);
    SB  sb;
    sb_init(&sb, g->a);
    sb_cstr(&sb, "BeT_");
    for (uint32_t i = 0; i < n.len; i++) {
        char c = n.ptr[i];
        bool ok = (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9');
        sb_char(&sb, ok ? c : '_');
    }
    return sb_finish(&sb);
}

static Str tmp_name(G *g) {
    SB sb;
    sb_init(&sb, g->a);
    sb_fmt(&sb, "_t%d", g->tmp++);
    return sb_finish(&sb);
}

/* ---- output helpers ---------------------------------------------------- */

static void line(G *g, const char *fmt, ...) BE_PRINTF(2, 3);
static void line(G *g, const char *fmt, ...) {
    sb_repeat(g->cur, ' ', g->indent * 4);
    va_list ap;
    va_start(ap, fmt);
    sb_vfmt(g->cur, fmt, ap);
    va_end(ap);
    sb_char(g->cur, '\n');
}

/* CAUTION: `S` expands its argument TWICE. Passing a generator call directly
 * — `S(gen_expr(g, e))` — therefore runs it twice, and any statement that
 * generator emitted lands in the output twice. `gen_expr` is memoized so the
 * existing call sites of that shape stay correct; a new generator that emits
 * lines must be memoized the same way, or hoisted into a local first. */
#define S(x) (int)(x).len, (x).ptr

/* The bytes of a pointer, as a map key — exact identity, not a hash. */
static Str ptr_key(Arena *a, const void *p, uint32_t epoch) {
    char *b = ARENA_ARRAY(a, char, sizeof p + sizeof epoch);
    for (size_t i = 0; i < sizeof p; i++) b[i] = (char)(((uintptr_t)p >> (i * 8)) & 0xff);
    for (size_t i = 0; i < sizeof epoch; i++)
        b[sizeof p + i] = (char)((epoch >> (i * 8)) & 0xff);
    return (Str){b, (uint32_t)(sizeof p + sizeof epoch)};
}

static Str gen_expr_gen(G *g, Expr *e);

/* The type checker accepts more than this back end can lower. Where that is
 * true the gap must be a diagnostic, never silence and never a zero value: a
 * `for` over a list used to emit no loop at all, so the program compiled, ran
 * and returned the wrong answer. Failing here is the whole point. */
static void unsupported(G *g, Span at, const char *what) {
    Diag *dg = diag_error(g->d, 903, at, "%s is not yet supported by the native back end",
                          what);
    diag_note(dg, "it type-checks, so this is a gap in code generation rather than a "
                  "mistake in your program");
    diag_help(dg, "build for the enfusion target, or open an issue with this program");
}

static uint32_t line_of(G *g, Span sp) { return srcmap_linecol(g->sm, sp).line; }

static Str file_of(G *g, Span sp) {
    SourceFile *f = srcmap_get(g->sm, sp.file);
    if (!f) return str_from("<unknown>");
    SB sb;
    sb_init(&sb, g->a);
    for (uint32_t i = 0; i < f->path.len; i++) {
        char c = f->path.ptr[i];
        if (c == '\\') sb_cstr(&sb, "\\\\");
        else sb_char(&sb, c);
    }
    return sb_finish(&sb);
}

/* ---- types ------------------------------------------------------------- */

static void ensure_type(G *g, Type *t);

static Str ctype(G *g, Type *t) {
    if (!t) return str_from("void");
    switch (t->kind) {
        case TY_VOID: return str_from("void");
        case TY_BOOL: return str_from("bool");
        case TY_CHAR: return str_from("uint32_t");
        case TY_STR: return str_from("BeStr");
        case TY_ERROR: return str_from("int32_t");
        case TY_INT: {
            SB sb;
            sb_init(&sb, g->a);
            sb_fmt(&sb, "%sint%u_t", t->is_signed ? "" : "u", t->bits);
            return sb_finish(&sb);
        }
        case TY_FLOAT: return str_from(t->bits == 32 ? "float" : "double");
        /* Declared by the runtime header, so nothing is generated for them.
         * Components are f32 on both targets — see beryl_rt.h. */
        case TY_VEC2: return str_from("BeVec2");
        case TY_VEC3: return str_from("BeVec3");
        case TY_VEC4: return str_from("BeVec4");
        case TY_STRUCT:
        case TY_ENUM: {
            ensure_type(g, t);
            Item *decl = t->decl;
            return mangle(g, decl ? decl->qual_name : t->name);
        }
        default:
            ensure_type(g, t);
            return type_id(g, t);
    }
}

static void ensure_type(G *g, Type *t) {
    if (!t) return;
    Str key = ty_name(g->a, t);
    if (map_has(g->emitted, key)) return;
    map_put(g->emitted, key, (void *)1);

    SB  *save   = g->cur;
    int  saveid = g->indent;
    g->cur      = &g->types;
    g->indent   = 0;

    switch (t->kind) {
        case TY_STRUCT: {
            Item *decl = t->decl;
            for (uint32_t i = 0; decl && i < decl->strukt.fields.len; i++)
                ensure_type(g, decl->strukt.fields.data[i].rtype);
            Str nm = mangle(g, decl ? decl->qual_name : t->name);
            line(g, "typedef struct %.*s {", S(nm));
            for (uint32_t i = 0; decl && i < decl->strukt.fields.len; i++) {
                Field *f = &decl->strukt.fields.data[i];
                Str    ct = ctype(g, f->rtype);
                line(g, "    %.*s %.*s;", S(ct), S(f->name));
            }
            if (!decl || decl->strukt.fields.len == 0) line(g, "    char _empty;");
            line(g, "} %.*s;", S(nm));
            line(g, "");
            break;
        }
        case TY_ENUM: {
            Item *decl = t->decl;
            Str   nm   = mangle(g, decl ? decl->qual_name : t->name);
            line(g, "typedef int32_t %.*s;", S(nm));
            line(g, "");
            break;
        }
        case TY_ARRAY: {
            ensure_type(g, t->elem);
            Str id = type_id(g, t);
            Str el = ctype(g, t->elem);
            line(g, "typedef struct { %.*s v[%llu]; } %.*s;", S(el),
                 (unsigned long long)(t->array_len ? t->array_len : 1), S(id));
            line(g, "");
            break;
        }
        case TY_OPTION: {
            ensure_type(g, t->elem);
            Str id = type_id(g, t);
            Str el = ctype(g, t->elem);
            line(g, "typedef struct { bool has; %.*s val; } %.*s;", S(el), S(id));
            line(g, "");
            break;
        }
        case TY_LIST: {
            ensure_type(g, t->elem);
            Str id = type_id(g, t);
            Str el = ctype(g, t->elem);
            line(g, "typedef struct { %.*s *data; int32_t len; int32_t cap; } %.*s;",
                 S(el), S(id));
            line(g, "static void %.*s_push(%.*s *l, %.*s v) {", S(id), S(id), S(el));
            line(g, "    if (l->len == l->cap) {");
            line(g, "        l->cap = l->cap ? l->cap * 2 : 8;");
            line(g, "        l->data = (%.*s *)beryl_grow(l->data, sizeof(%.*s) * "
                    "(size_t)l->cap);",
                 S(el), S(el));
            line(g, "    }");
            line(g, "    l->data[l->len++] = v;");
            line(g, "}");
            line(g, "static %.*s %.*s_get(const %.*s *l, int64_t i, const char *f, int n) {",
                 S(el), S(id), S(id));
            line(g, "    be_idx(i, l->len, f, n);");
            line(g, "    return l->data[i];");
            line(g, "}");
            line(g, "static void %.*s_set(%.*s *l, int64_t i, %.*s v, const char *f, "
                    "int n) {",
                 S(id), S(id), S(el));
            line(g, "    be_idx(i, l->len, f, n);");
            line(g, "    l->data[i] = v;");
            line(g, "}");
            line(g, "");
            break;
        }
        case TY_ERRUNION: {
            ensure_type(g, t->elem);
            Str id = type_id(g, t);
            if (t->elem && t->elem->kind == TY_VOID) {
                line(g, "typedef struct { int32_t err; } %.*s;", S(id));
            } else {
                Str el = ctype(g, t->elem);
                line(g, "typedef struct { int32_t err; %.*s val; } %.*s;", S(el), S(id));
            }
            line(g, "");
            break;
        }
        default: break;
    }

    g->cur    = save;
    g->indent = saveid;
}

/* ---- expressions ------------------------------------------------------- */

static Str gen_expr(G *g, Expr *e);
static void gen_block(G *g, Expr *b);

/* `vec2` / `vec3` / `vec4` — the middle of every `be_vec3_add` style helper. */
static const char *vec_suffix(const Type *t) {
    switch (ty_vec_arity(t)) {
        case 2: return "vec2";
        case 4: return "vec4";
        default: return "vec3";
    }
}

static const char *int_suffix(const Type *t) {
    switch (t->bits) {
        case 8: return t->is_signed ? "i8" : "u8";
        case 16: return t->is_signed ? "i16" : "u16";
        case 32: return t->is_signed ? "i32" : "u32";
        default: return t->is_signed ? "i64" : "u64";
    }
}

static void emit_c_string(SB *sb, Str s) {
    sb_char(sb, '"');
    for (uint32_t i = 0; i < s.len; i++) {
        unsigned char c = (unsigned char)s.ptr[i];
        switch (c) {
            case '"': sb_cstr(sb, "\\\""); break;
            case '\\': sb_cstr(sb, "\\\\"); break;
            case '\n': sb_cstr(sb, "\\n"); break;
            case '\t': sb_cstr(sb, "\\t"); break;
            case '\r': sb_cstr(sb, "\\r"); break;
            default:
                if (c < 32 || c >= 127) sb_fmt(sb, "\\x%02X", c);
                else sb_char(sb, (char)c);
        }
    }
    sb_char(sb, '"');
}

/* Declares a temporary initialized to `init` and returns its name. */
static Str temp_of(G *g, Type *t, Str init) {
    Str nm = tmp_name(g);
    Str ct = ctype(g, t);
    line(g, "%.*s %.*s = %.*s;", S(ct), S(nm), S(init));
    return nm;
}

static Str zero_of(G *g, Type *t) {
    SB sb;
    sb_init(&sb, g->a);
    if (!t) {
        sb_cstr(&sb, "0");
        return sb_finish(&sb);
    }
    switch (t->kind) {
        case TY_BOOL: sb_cstr(&sb, "false"); break;
        case TY_STR: sb_cstr(&sb, "((BeStr){0,0})"); break;
        case TY_INT:
        case TY_CHAR:
        case TY_FLOAT:
        case TY_ENUM: sb_cstr(&sb, "0"); break;
        default: {
            Str ct = ctype(g, t);
            sb_fmt(&sb, "((%.*s){0})", S(ct));
            break;
        }
    }
    return sb_finish(&sb);
}

static Str gen_binary(G *g, Expr *e) {
    Type   *t  = e->binary.lhs->type;
    TokKind op = e->binary.op;
    Str     l  = gen_expr(g, e->binary.lhs);
    Str     r  = gen_expr(g, e->binary.rhs);

    SB sb;
    sb_init(&sb, g->a);

    /* Vectors first, because C has no operators on them and the fall-through
     * at the bottom of this function would otherwise emit `(a + b)` on a
     * struct — which is what v0.1 did. */
    Type *rtv = e->binary.rhs->type;
    if (ty_is_vec(t) || ty_is_vec(rtv)) {
        bool        lv = ty_is_vec(t);
        const char *s  = vec_suffix(lv ? t : rtv);
        switch (op) {
            case TK_EQ: sb_fmt(&sb, "be_%s_eq(%.*s, %.*s)", s, S(l), S(r)); break;
            case TK_NE: sb_fmt(&sb, "(!be_%s_eq(%.*s, %.*s))", s, S(l), S(r)); break;
            case TK_PLUS: sb_fmt(&sb, "be_%s_add(%.*s, %.*s)", s, S(l), S(r)); break;
            case TK_MINUS: sb_fmt(&sb, "be_%s_sub(%.*s, %.*s)", s, S(l), S(r)); break;
            case TK_SLASH:
                if (lv && ty_is_vec(rtv)) sb_fmt(&sb, "be_%s_div(%.*s, %.*s)", s, S(l), S(r));
                else sb_fmt(&sb, "be_%s_unscale(%.*s, %.*s)", s, S(l), S(r));
                break;
            default: /* TK_STAR */
                if (lv && ty_is_vec(rtv)) sb_fmt(&sb, "be_%s_mul(%.*s, %.*s)", s, S(l), S(r));
                else if (lv) sb_fmt(&sb, "be_%s_scale(%.*s, %.*s)", s, S(l), S(r));
                else sb_fmt(&sb, "be_%s_scale(%.*s, %.*s)", s, S(r), S(l));
                break;
        }
        return sb_finish(&sb);
    }

    /* Strings compare by content. `==` on the slice struct is not equality,
     * and C will not compile it at all. */
    if (t && t->kind == TY_STR && (op == TK_EQ || op == TK_NE)) {
        sb_fmt(&sb, "%sbe_str_eq(%.*s, %.*s)", op == TK_NE ? "!" : "", S(l), S(r));
        return sb_finish(&sb);
    }

    const char *cop = NULL;
    switch (op) {
        case TK_EQ: cop = "=="; break;
        case TK_NE: cop = "!="; break;
        case TK_LT: cop = "<"; break;
        case TK_LE: cop = "<="; break;
        case TK_GT: cop = ">"; break;
        case TK_GE: cop = ">="; break;
        case TK_ANDAND: cop = "&&"; break;
        case TK_OROR: cop = "||"; break;
        case TK_AMP: cop = "&"; break;
        case TK_PIPE: cop = "|"; break;
        case TK_CARET: cop = "^"; break;
        default: break;
    }
    if (cop) {
        sb_fmt(&sb, "(%.*s %s %.*s)", S(l), cop, S(r));
        return sb_finish(&sb);
    }

    /* Arithmetic on integers is checked; on floats it is not. */
    if (t && t->kind == TY_INT) {
        const char *fn = NULL;
        switch (op) {
            case TK_PLUS: fn = "be_add"; break;
            case TK_MINUS: fn = "be_sub"; break;
            case TK_STAR: fn = "be_mul"; break;
            case TK_SLASH: fn = "be_div"; break;
            case TK_PERCENT: fn = "be_rem"; break;
            case TK_SHL: fn = "be_shl"; break;
            case TK_SHR: fn = "be_shr"; break;
            default: break;
        }
        if (fn) {
            Str f = file_of(g, e->span);
            sb_fmt(&sb, "%s_%s(%.*s, %.*s, \"%.*s\", %u)", fn, int_suffix(t), S(l), S(r),
                   S(f), line_of(g, e->span));
            return sb_finish(&sb);
        }
    }

    const char *plain = NULL;
    switch (op) {
        case TK_PLUS: plain = "+"; break;
        case TK_MINUS: plain = "-"; break;
        case TK_STAR: plain = "*"; break;
        case TK_SLASH: plain = "/"; break;
        case TK_PERCENT: plain = "%"; break;
        case TK_SHL: plain = "<<"; break;
        case TK_SHR: plain = ">>"; break;
        default: plain = "+"; break;
    }
    sb_fmt(&sb, "(%.*s %s %.*s)", S(l), plain, S(r));
    return sb_finish(&sb);
}

/* Container methods are emitted against the helpers generated with the list's
 * type, so the receiver has to be rendered as storage rather than a value. */
/* Vector methods are plain calls on values — unlike the list methods, which
 * need the receiver as storage because they mutate it. */
static Str gen_vec_method(G *g, Expr *e) {
    Expr *recv = e->call.callee->field.base;
    Str   s    = str_from(vec_suffix(recv->type));
    Str   r    = gen_expr(g, recv);

    SB sb;
    sb_init(&sb, g->a);

    const char *fn = "length";
    switch ((Intrinsic)e->intrinsic) {
        case INTR_VEC_LENGTH_SQ: fn = "length_sq"; break;
        case INTR_VEC_DOT: fn = "dot"; break;
        case INTR_VEC_DISTANCE: fn = "distance"; break;
        case INTR_VEC_NORMALIZED: fn = "normalized"; break;
        case INTR_VEC_CROSS: fn = "cross"; break;
        default: break;
    }

    if (e->call.args.len == 1) {
        Str a = gen_expr(g, e->call.args.data[0].value);
        sb_fmt(&sb, "be_%.*s_%s(%.*s, %.*s)", S(s), fn, S(r), S(a));
    } else {
        sb_fmt(&sb, "be_%.*s_%s(%.*s)", S(s), fn, S(r));
    }
    return sb_finish(&sb);
}

static Str gen_vec_new(G *g, Expr *e) {
    SB sb;
    sb_init(&sb, g->a);
    sb_fmt(&sb, "be_%s(", vec_suffix(e->type));
    for (uint32_t i = 0; i < e->call.args.len; i++) {
        if (i) sb_cstr(&sb, ", ");
        Str a = gen_expr(g, e->call.args.data[i].value);
        sb_fmt(&sb, "%.*s", S(a));
    }
    sb_char(&sb, ')');
    return sb_finish(&sb);
}

static Str gen_list_method(G *g, Expr *e) {
    Expr  *recv = e->call.callee->field.base;
    Type  *lt   = recv->type;
    Str    id   = type_id(g, lt);
    Str    r    = gen_expr(g, recv);
    Str    f    = file_of(g, e->span);
    ArgVec args = e->call.args;

    SB sb;
    sb_init(&sb, g->a);
    switch ((Intrinsic)e->intrinsic) {
        case INTR_LIST_LEN: sb_fmt(&sb, "(%.*s).len", S(r)); break;
        case INTR_LIST_CLEAR:
            line(g, "(%.*s).len = 0;", S(r));
            sb_cstr(&sb, "((void)0)");
            break;
        case INTR_LIST_PUSH:
            line(g, "%.*s_push(&(%.*s), %.*s);", S(id), S(r),
                 S(gen_expr(g, args.data[0].value)));
            sb_cstr(&sb, "((void)0)");
            break;
        case INTR_LIST_GET:
            sb_fmt(&sb, "%.*s_get(&(%.*s), (int64_t)%.*s, \"%.*s\", %u)", S(id), S(r),
                   S(gen_expr(g, args.data[0].value)), S(f), line_of(g, e->span));
            break;
        default: /* INTR_LIST_SET */
            line(g, "%.*s_set(&(%.*s), (int64_t)%.*s, %.*s, \"%.*s\", %u);", S(id), S(r),
                 S(gen_expr(g, args.data[0].value)),
                 S(gen_expr(g, args.data[1].value)), S(f), line_of(g, e->span));
            sb_cstr(&sb, "((void)0)");
            break;
    }
    return sb_finish(&sb);
}

static Str gen_call_intrinsic(G *g, Expr *e) {
    if (intrinsic_is_list_method((Intrinsic)e->intrinsic)) return gen_list_method(g, e);
    if (intrinsic_is_vec_method((Intrinsic)e->intrinsic)) return gen_vec_method(g, e);
    if (intrinsic_is_vec_new((Intrinsic)e->intrinsic)) return gen_vec_new(g, e);

    SB sb;
    sb_init(&sb, g->a);
    ArgVec args = e->call.args;
    Str    f    = file_of(g, e->span);

    switch ((Intrinsic)e->intrinsic) {
        case INTR_PRINT:
        case INTR_PRINTLN: {
            for (uint32_t i = 0; i < args.len; i++) {
                Str   v = gen_expr(g, args.data[i].value);
                Type *t = args.data[i].value->type;
                if (!t) continue;
                if (t->kind == TY_STR) line(g, "beryl_print_str(%.*s);", S(v));
                else if (t->kind == TY_BOOL) line(g, "beryl_print_bool(%.*s);", S(v));
                else if (t->kind == TY_CHAR) line(g, "beryl_print_char(%.*s);", S(v));
                else if (t->kind == TY_FLOAT)
                    line(g, "beryl_print_f64((double)%.*s);", S(v));
                else if (t->kind == TY_INT && !t->is_signed)
                    line(g, "beryl_print_u64((uint64_t)%.*s);", S(v));
                else line(g, "beryl_print_i64((int64_t)%.*s);", S(v));
            }
            if ((Intrinsic)e->intrinsic == INTR_PRINTLN) line(g, "beryl_newline();");
            sb_cstr(&sb, "((void)0)");
            return sb_finish(&sb);
        }
        case INTR_ASSERT: {
            Str v = gen_expr(g, args.data[0].value);
            SB  txt;
            sb_init(&txt, g->a);
            emit_c_string(&txt, str_from("assertion"));
            line(g, "beryl_test_assert(%.*s, %.*s, \"%.*s\", %u);", S(v),
                 S(sb_finish(&txt)), S(f), line_of(g, e->span));
            sb_cstr(&sb, "((void)0)");
            return sb_finish(&sb);
        }
        case INTR_MIN:
        case INTR_MAX: {
            Type *t = e->type;
            Str   a = temp_of(g, t, gen_expr(g, args.data[0].value));
            Str   b = temp_of(g, t, gen_expr(g, args.data[1].value));
            sb_fmt(&sb, "(%.*s %s %.*s ? %.*s : %.*s)", S(a),
                   (Intrinsic)e->intrinsic == INTR_MIN ? "<" : ">", S(b), S(a), S(b));
            return sb_finish(&sb);
        }
        case INTR_CLAMP: {
            Type *t  = e->type;
            Str   x  = temp_of(g, t, gen_expr(g, args.data[0].value));
            Str   lo = temp_of(g, t, gen_expr(g, args.data[1].value));
            Str   hi = temp_of(g, t, gen_expr(g, args.data[2].value));
            sb_fmt(&sb, "(%.*s < %.*s ? %.*s : (%.*s > %.*s ? %.*s : %.*s))", S(x), S(lo),
                   S(lo), S(x), S(hi), S(hi), S(x));
            return sb_finish(&sb);
        }
        case INTR_ABS: {
            Type *t = e->type;
            Str   x = temp_of(g, t, gen_expr(g, args.data[0].value));
            if (t && t->kind == TY_FLOAT)
                sb_fmt(&sb, "be_abs_f%u(%.*s)", t->bits, S(x));
            else if (t && t->kind == TY_INT)
                sb_fmt(&sb, "(%.*s < 0 ? be_neg_%s(%.*s, \"%.*s\", %u) : %.*s)", S(x),
                       int_suffix(t), S(x), S(f), line_of(g, e->span), S(x));
            else sb_fmt(&sb, "%.*s", S(x));
            return sb_finish(&sb);
        }
        case INTR_SQRT: {
            Type *t = e->type;
            Str   x = gen_expr(g, args.data[0].value);
            sb_fmt(&sb, "be_sqrt_f%u(%.*s)", t ? t->bits : 64, S(x));
            return sb_finish(&sb);
        }
        case INTR_WRAPPING_ADD:
        case INTR_WRAPPING_SUB:
        case INTR_WRAPPING_MUL:
        case INTR_SATURATING_ADD:
        case INTR_SATURATING_SUB: {
            Type       *t  = e->type;
            const char *fn = (Intrinsic)e->intrinsic == INTR_WRAPPING_ADD   ? "be_wadd"
                             : (Intrinsic)e->intrinsic == INTR_WRAPPING_SUB ? "be_wsub"
                             : (Intrinsic)e->intrinsic == INTR_WRAPPING_MUL ? "be_wmul"
                             : (Intrinsic)e->intrinsic == INTR_SATURATING_ADD
                                 ? "be_satadd"
                                 : "be_satsub";
            sb_fmt(&sb, "%s_%s(%.*s, %.*s)", fn, int_suffix(t),
                   S(gen_expr(g, args.data[0].value)),
                   S(gen_expr(g, args.data[1].value)));
            return sb_finish(&sb);
        }
        default: sb_cstr(&sb, "0"); return sb_finish(&sb);
    }
}

static Str gen_call(G *g, Expr *e) {
    if (e->res_kind == RES_INTRINSIC) return gen_call_intrinsic(g, e);

    Item *fn = (e->res_kind == RES_FN) ? (Item *)e->res : NULL;
    if (!fn) return str_from("0");

    bool has_self = fn->fn.params.len > 0 && fn->fn.params.data[0].is_self;

    SB sb;
    sb_init(&sb, g->a);
    Str nm = mangle(g, fn->qual_name);
    sb_fmt(&sb, "%.*s(", S(nm));

    uint32_t written = 0;
    if (has_self && e->call.callee && e->call.callee->kind == EX_FIELD) {
        Str recv = gen_expr(g, e->call.callee->field.base);
        Conv cv  = fn->fn.params.data[0].conv;
        if (cv == CONV_INOUT || cv == CONV_SET) sb_fmt(&sb, "&(%.*s)", S(recv));
        else sb_fmt(&sb, "%.*s", S(recv));
        written++;
    }

    for (uint32_t i = 0; i < e->call.args.len; i++) {
        uint32_t slot = i + (has_self ? 1 : 0);
        Conv     cv   = (slot < fn->fn.params.len) ? fn->fn.params.data[slot].conv : CONV_LET;
        Str      v    = gen_expr(g, e->call.args.data[i].value);
        if (written) sb_cstr(&sb, ", ");
        if (cv == CONV_INOUT || cv == CONV_SET) sb_fmt(&sb, "&(%.*s)", S(v));
        else sb_fmt(&sb, "%.*s", S(v));
        written++;
    }

    /* Defaults for omitted trailing parameters. */
    for (uint32_t slot = e->call.args.len + (has_self ? 1 : 0); slot < fn->fn.params.len;
         slot++) {
        Param *pm = &fn->fn.params.data[slot];
        if (!pm->deflt) break;
        Str v = gen_expr(g, pm->deflt);
        if (written) sb_cstr(&sb, ", ");
        sb_fmt(&sb, "%.*s", S(v));
        written++;
    }

    sb_char(&sb, ')');
    return sb_finish(&sb);
}

/* Memoized for the same reason as `ef_expr`: `S` expands its argument twice,
 * so a generator passed straight into it runs twice and re-emits whatever
 * statements it needed. See the caution at the `S` definition above. */
static Str gen_expr(G *g, Expr *e) {
    if (e) {
        Str  key = ptr_key(g->a, e, g->epoch);
        Str *hit = (Str *)map_get(g->memo, key);
        if (hit) return *hit;
        Str  r   = gen_expr_gen(g, e);
        Str *box = ARENA_NEW(g->a, Str);
        *box     = r;
        map_put(g->memo, key, box);
        return r;
    }
    return gen_expr_gen(g, e);
}

static Str gen_expr_gen(G *g, Expr *e) {
    SB sb;
    sb_init(&sb, g->a);
    if (!e) {
        sb_cstr(&sb, "0");
        return sb_finish(&sb);
    }

    switch (e->kind) {
        case EX_INT:
            if (e->type && e->type->kind == TY_FLOAT)
                sb_fmt(&sb, "%llu.0%s", (unsigned long long)e->int_lit.val,
                       e->type->bits == 32 ? "f" : "");
            else sb_fmt(&sb, "%lluLL", (unsigned long long)e->int_lit.val);
            break;

        case EX_FLOAT: {
            /* `%g` drops a trailing `.0`, and `1f` is not a float literal in
             * C — it lexes as an integer with a stray suffix. Nothing caught
             * this before because no f32 literal had ever reached the C back
             * end; `Vec3(1.0, 2.0, 3.0)` is the first. */
            SB tmp;
            sb_init(&tmp, g->a);
            sb_fmt(&tmp, "%.17g", e->float_lit.val);
            Str  d     = sb_finish(&tmp);
            bool fract = false;
            for (uint32_t i = 0; i < d.len && !fract; i++)
                fract = d.ptr[i] == '.' || d.ptr[i] == 'e' || d.ptr[i] == 'E';
            sb_fmt(&sb, "%.*s%s%s", S(d), fract ? "" : ".0",
                   (e->type && e->type->bits == 32) ? "f" : "");
            break;
        }

        case EX_STR:
            sb_cstr(&sb, "BE_STR(");
            emit_c_string(&sb, e->str_lit);
            sb_char(&sb, ')');
            break;

        case EX_CHAR: sb_fmt(&sb, "%uu", e->char_lit); break;
        case EX_BOOL: sb_cstr(&sb, e->bool_lit ? "true" : "false"); break;

        case EX_PATH:
        case EX_SELF: {
            if (e->res_kind == RES_LOCAL) {
                Local *l = (Local *)e->res;
                Str    n = local_name(g, l->name);
                if (l->is_param && (l->conv == CONV_INOUT || l->conv == CONV_SET))
                    sb_fmt(&sb, "(*%.*s)", S(n));
                else sb_fmt(&sb, "%.*s", S(n));
            } else if (e->res_kind == RES_CONST) {
                Item *it = (Item *)e->res;
                Str   n  = mangle(g, it->qual_name);
                sb_fmt(&sb, "%.*s", S(n));
            } else {
                sb_cstr(&sb, "0");
            }
            break;
        }

        case EX_UNARY: {
            Str   v = gen_expr(g, e->unary.operand);
            Type *t = e->unary.operand->type;
            if (e->unary.op == TK_BANG) sb_fmt(&sb, "(!%.*s)", S(v));
            else if (e->unary.op == TK_TILDE) sb_fmt(&sb, "(~%.*s)", S(v));
            else if (t && t->kind == TY_INT) {
                Str f = file_of(g, e->span);
                sb_fmt(&sb, "be_neg_%s(%.*s, \"%.*s\", %u)", int_suffix(t), S(v), S(f),
                       line_of(g, e->span));
            } else if (ty_is_vec(t)) {
                sb_fmt(&sb, "be_%s_neg(%.*s)", vec_suffix(t), S(v));
            } else sb_fmt(&sb, "(-%.*s)", S(v));
            break;
        }

        case EX_BINARY: return gen_binary(g, e);
        case EX_CALL: return gen_call(g, e);

        case EX_FIELD: {
            Str b = gen_expr(g, e->field.base);
            sb_fmt(&sb, "%.*s.%.*s", S(b), S(e->field.name));
            break;
        }

        case EX_INDEX: {
            Str   b  = gen_expr(g, e->index.base);
            Str   ix = gen_expr(g, e->index.index);
            Type *bt = e->index.base->type;
            Str   f  = file_of(g, e->span);
            /* A list keeps its elements behind a pointer and its length in a
             * field, so it indexes differently from an array or a vector —
             * which both store inline as `.v[]`. Emitting the array form for
             * a list produced `xs.v[be_idx(i, 0, ...)]`: the wrong member,
             * and a bound of zero. */
            if (bt && bt->kind == TY_LIST) {
                Str bn = temp_of(g, bt, b);
                sb_fmt(&sb, "%.*s.data[be_idx((int64_t)%.*s, %.*s.len, \"%.*s\", %u)]",
                       S(bn), S(ix), S(bn), S(f), line_of(g, e->span));
                break;
            }
            /* A vector's length is its arity; `.v[]` is the union member that
             * makes `v[i]` and `v.x` the same storage. */
            uint64_t n = ty_is_vec(bt) ? ty_vec_arity(bt)
                         : (bt && bt->kind == TY_ARRAY) ? bt->array_len
                                                        : 0;
            sb_fmt(&sb, "%.*s.v[be_idx((int64_t)%.*s, %llu, \"%.*s\", %u)]", S(b), S(ix),
                   (unsigned long long)n, S(f), line_of(g, e->span));
            break;
        }

        case EX_CAST: {
            Str v  = gen_expr(g, e->cast.value);
            Str ct = ctype(g, e->type);
            sb_fmt(&sb, "((%.*s)%.*s)", S(ct), S(v));
            break;
        }

        case EX_STRUCT_LIT: {
            Type *t    = e->type;
            Item *decl = t ? t->decl : NULL;
            Str   ct   = ctype(g, t);
            sb_fmt(&sb, "((%.*s){", S(ct));
            bool first = true;
            for (uint32_t fi = 0; decl && fi < decl->strukt.fields.len; fi++) {
                Field *fl = &decl->strukt.fields.data[fi];
                Expr  *val = NULL;
                for (uint32_t k = 0; k < e->struct_lit.fields.len; k++)
                    if (str_eq(e->struct_lit.fields.data[k].name, fl->name))
                        val = e->struct_lit.fields.data[k].value;
                Str v = val ? gen_expr(g, val)
                            : (fl->deflt ? gen_expr(g, fl->deflt) : zero_of(g, fl->rtype));
                if (!first) sb_cstr(&sb, ", ");
                sb_fmt(&sb, ".%.*s = %.*s", S(fl->name), S(v));
                first = false;
            }
            if (first) sb_cstr(&sb, "0");
            sb_cstr(&sb, "})");
            break;
        }

        case EX_ARRAY_LIT: {
            Str ct = ctype(g, e->type);
            sb_fmt(&sb, "((%.*s){{", S(ct));
            for (uint32_t i = 0; i < e->array_lit.elems.len; i++) {
                if (i) sb_cstr(&sb, ", ");
                Str v = gen_expr(g, e->array_lit.elems.data[i]);
                sb_fmt(&sb, "%.*s", S(v));
            }
            if (e->array_lit.elems.len == 0) sb_cstr(&sb, "0");
            sb_cstr(&sb, "}})");
            break;
        }

        case EX_TRY: {
            Type *ut = e->try_expr.inner->type;
            Str   v  = gen_expr(g, e->try_expr.inner);
            Str   t  = temp_of(g, ut, v);
            line(g, "if (%.*s.err != 0) {", S(t));
            g->indent++;
            if (g->fn && g->fn->rtype && g->fn->rtype->kind == TY_ERRUNION) {
                line(g, "return (%.*s){ .err = %.*s.err };", S(g->ret_ctype), S(t));
            } else {
                line(g, "beryl_panic(\"unhandled error\", \"%.*s\", %u);",
                     S(file_of(g, e->span)), line_of(g, e->span));
            }
            g->indent--;
            line(g, "}");
            if (ut && ut->elem && ut->elem->kind != TY_VOID) sb_fmt(&sb, "%.*s.val", S(t));
            else sb_cstr(&sb, "((void)0)");
            break;
        }

        case EX_ORELSE: {
            Type *vt = e->orelse_expr.value->type;
            Str   v  = gen_expr(g, e->orelse_expr.value);
            Str   t  = temp_of(g, vt, v);
            Str   r  = tmp_name(g);
            Str   rt = ctype(g, e->type);
            line(g, "%.*s %.*s;", S(rt), S(r));
            bool is_opt = vt && vt->kind == TY_OPTION;
            line(g, "if (%.*s.%s) {", S(t), is_opt ? "has" : "err == 0");
            g->indent++;
            line(g, "%.*s = %.*s.val;", S(r), S(t));
            g->indent--;
            line(g, "} else {");
            g->indent++;
            Str fb = gen_expr(g, e->orelse_expr.fallback);
            line(g, "%.*s = %.*s;", S(r), S(fb));
            g->indent--;
            line(g, "}");
            sb_fmt(&sb, "%.*s", S(r));
            break;
        }

        case EX_CATCH: {
            Type *vt = e->catch_expr.value->type;
            Str   v  = gen_expr(g, e->catch_expr.value);
            Str   t  = temp_of(g, vt, v);
            Str   r  = tmp_name(g);
            Str   rt = ctype(g, e->type);
            line(g, "%.*s %.*s = %.*s;", S(rt), S(r), S(zero_of(g, e->type)));
            line(g, "if (%.*s.err == 0) {", S(t));
            g->indent++;
            if (vt && vt->elem && vt->elem->kind != TY_VOID)
                line(g, "%.*s = %.*s.val;", S(r), S(t));
            g->indent--;
            line(g, "} else {");
            g->indent++;
            if (!str_empty(e->catch_expr.binding))
                line(g, "int32_t %.*s = %.*s.err; (void)%.*s;", S(e->catch_expr.binding),
                     S(t), S(e->catch_expr.binding));
            if (e->catch_expr.handler && e->catch_expr.handler->kind == EX_BLOCK)
                gen_block(g, e->catch_expr.handler);
            else gen_expr(g, e->catch_expr.handler);
            g->indent--;
            line(g, "}");
            sb_fmt(&sb, "%.*s", S(r));
            break;
        }

        case EX_ERROR_LIT: {
            /* Error names are interned into a global set; the tag is its hash
             * truncated to a positive int, which keeps them stable per name. */
            uint64_t h = str_hash(e->error_lit) & 0x7fffffffu;
            if (h == 0) h = 1;
            sb_fmt(&sb, "%lluL", (unsigned long long)h);
            break;
        }

        case EX_IF: {
            /* `if` in expression position is only used as a statement in v0.1. */
            Str c = gen_expr(g, e->if_expr.cond);
            line(g, "if (%.*s) {", S(c));
            g->indent++;
            gen_block(g, e->if_expr.then_blk);
            g->indent--;
            if (e->if_expr.else_blk) {
                line(g, "} else {");
                g->indent++;
                if (e->if_expr.else_blk->kind == EX_IF) gen_expr(g, e->if_expr.else_blk);
                else gen_block(g, e->if_expr.else_blk);
                g->indent--;
            }
            line(g, "}");
            sb_cstr(&sb, "((void)0)");
            break;
        }

        case EX_BLOCK:
            line(g, "{");
            g->indent++;
            gen_block(g, e);
            g->indent--;
            line(g, "}");
            sb_cstr(&sb, "((void)0)");
            break;

        case EX_UNSAFE:
            gen_expr(g, e->unsafe_expr.body);
            sb_cstr(&sb, "((void)0)");
            break;

        default: sb_cstr(&sb, "0"); break;
    }
    return sb_finish(&sb);
}

/* Renders a folded constant as a literal. A constant must be folded rather
 * than emitted as an expression: C requires a compile-time constant in an
 * initializer, and `WIDTH * HEIGHT` would otherwise become a call to the
 * checked-multiply helper. */
static Str const_literal(G *g, Expr *e, Type *want) {
    ConstVal v = const_eval(g->a, g->d, g->p, e, true);
    SB       sb;
    sb_init(&sb, g->a);
    switch (v.kind) {
        case CV_INT:
            if (want && want->kind == TY_FLOAT)
                sb_fmt(&sb, "%lld.0%s", (long long)v.i, want->bits == 32 ? "f" : "");
            else sb_fmt(&sb, "%lldLL", (long long)v.i);
            break;
        case CV_FLOAT:
            sb_fmt(&sb, "%.17g%s", v.f, (want && want->bits == 32) ? "f" : "");
            break;
        case CV_BOOL: sb_cstr(&sb, v.b ? "true" : "false"); break;
        case CV_STR:
            sb_cstr(&sb, "BE_STR(");
            emit_c_string(&sb, v.s);
            sb_char(&sb, ')');
            break;
        default: sb_cstr(&sb, "0"); break;
    }
    return sb_finish(&sb);
}

/* ---- statements -------------------------------------------------------- */

static const char *assign_op(TokKind k) {
    switch (k) {
        case TK_PLUSEQ: return "+";
        case TK_MINUSEQ: return "-";
        case TK_STAREQ: return "*";
        case TK_SLASHEQ: return "/";
        case TK_PERCENTEQ: return "%";
        default: return NULL;
    }
}

static void gen_stmt(G *g, Stmt *s) {
    /* See ef_stmt: a shared node such as a parameter default is rendered at
     * more than one site, and a memo that outlived the statement let the
     * second site reference the first site's temporaries. */
    g->epoch++;
    if (!s) return;

    switch (s->kind) {
        case ST_LET: {
            Str nm = local_name(g, s->let.name);
            if (s->let.init) {
                Str v  = gen_expr(g, s->let.init);
                Str ct = ctype(g, s->let.init->type);
                line(g, "%.*s %.*s = %.*s;", S(ct), S(nm), S(v));
            } else {
                /* Declared without a value; ownership proved it is assigned
                 * before any read, so no initializer is emitted. */
                Type *dt = NULL;
                for (uint32_t i = 0; g->fn && i < g->fn->nlocals; i++) {
                    Local *cand = ((Local **)g->fn->locals)[i];
                    if (cand->span.offset == s->span.offset &&
                        str_eq(cand->name, s->let.name)) {
                        dt = cand->type;
                        break;
                    }
                }
                Str ct = ctype(g, dt);
                /* A container starts empty. Everything else was proved
                 * assigned-before-read by the ownership pass, so it needs no
                 * initializer here. */
                if (dt && (dt->kind == TY_LIST || dt->kind == TY_MAP))
                    line(g, "%.*s %.*s = {0};", S(ct), S(nm));
                else line(g, "%.*s %.*s;", S(ct), S(nm));
            }
            break;
        }

        case ST_EXPR: {
            Str v = gen_expr(g, s->expr);
            if (!str_eq_c(v, "((void)0)")) line(g, "(void)(%.*s);", S(v));
            break;
        }

        case ST_ASSIGN: {
            const char *op = assign_op(s->assign.op);
            Str         rv = gen_expr(g, s->assign.value);
            Str         lv = gen_expr(g, s->assign.target);
            Type       *t  = s->assign.target->type;
            if (!op) {
                line(g, "%.*s = %.*s;", S(lv), S(rv));
            } else if (t && t->kind == TY_INT) {
                const char *fn = NULL;
                switch (s->assign.op) {
                    case TK_PLUSEQ: fn = "be_add"; break;
                    case TK_MINUSEQ: fn = "be_sub"; break;
                    case TK_STAREQ: fn = "be_mul"; break;
                    case TK_SLASHEQ: fn = "be_div"; break;
                    default: fn = "be_rem"; break;
                }
                Str f = file_of(g, s->span);
                line(g, "%.*s = %s_%s(%.*s, %.*s, \"%.*s\", %u);", S(lv), fn,
                     int_suffix(t), S(lv), S(rv), S(f), line_of(g, s->span));
            } else {
                line(g, "%.*s %s= %.*s;", S(lv), op, S(rv));
            }
            break;
        }

        case ST_WHILE: {
            /* The condition may need temporaries, so it is recomputed at the
             * top of the loop body rather than in the `for` header. */
            line(g, "for (;;) {");
            g->indent++;
            Str c = gen_expr(g, s->while_st.cond);
            line(g, "if (!(%.*s)) break;", S(c));
            gen_block(g, s->while_st.body);
            g->indent--;
            line(g, "}");
            break;
        }

        case ST_FOR: {
            Expr *it = s->for_st.iter;
            Str   nm = local_name(g, s->for_st.var);
            if (it && it->kind == EX_RANGE) {
                Str lo = gen_expr(g, it->range.lo);
                Str hi = gen_expr(g, it->range.hi);
                Str ct = ctype(g, it->range.lo->type);
                Str hn = temp_of(g, it->range.hi->type, hi);
                line(g, "for (%.*s %.*s = %.*s; %.*s < %.*s; %.*s++) {", S(ct), S(nm),
                     S(lo), S(nm), S(hn), S(nm));
                g->indent++;
                gen_block(g, s->for_st.body);
                g->indent--;
                line(g, "}");
            } else if (it && it->type && it->type->kind == TY_ARRAY) {
                Str av = gen_expr(g, it);
                Str an = temp_of(g, it->type, av);
                Str ct = ctype(g, it->type->elem);
                Str ix = tmp_name(g);
                line(g, "for (int64_t %.*s = 0; %.*s < %llu; %.*s++) {", S(ix), S(ix),
                     (unsigned long long)it->type->array_len, S(ix));
                g->indent++;
                line(g, "%.*s %.*s = %.*s.v[%.*s];", S(ct), S(nm), S(an), S(ix));
                gen_block(g, s->for_st.body);
                g->indent--;
                line(g, "}");
            } else if (it && it->type && it->type->kind == TY_LIST) {
                /* A list's length is a runtime field, so the bound is read
                 * once into a temporary rather than re-evaluated per step —
                 * the loop iterates the list as it was on entry. */
                Str av = gen_expr(g, it);
                Str an = temp_of(g, it->type, av);
                Str ct = ctype(g, it->type->elem);
                Str ix = tmp_name(g);
                line(g, "for (int32_t %.*s = 0; %.*s < %.*s.len; %.*s++) {", S(ix), S(ix),
                     S(an), S(ix));
                g->indent++;
                line(g, "%.*s %.*s = %.*s.data[%.*s];", S(ct), S(nm), S(an), S(ix));
                gen_block(g, s->for_st.body);
                g->indent--;
                line(g, "}");
            } else {
                /* Never emit nothing. A `for` the checker accepted but this
                 * function cannot lower used to vanish silently, which is how
                 * `for v in xs` over a list compiled, ran, and returned zero. */
                unsupported(g, s->span, "this `for` iterable");
            }
            break;
        }

        case ST_RETURN: {
            Type *rt = g->fn ? g->fn->rtype : NULL;
            if (!s->expr) {
                if (rt && rt->kind == TY_ERRUNION)
                    line(g, "return (%.*s){ .err = 0 };", S(g->ret_ctype));
                else line(g, "return;");
                break;
            }
            Str v = gen_expr(g, s->expr);
            if (rt && rt->kind == TY_ERRUNION) {
                if (s->expr->kind == EX_ERROR_LIT)
                    line(g, "return (%.*s){ .err = %.*s };", S(g->ret_ctype), S(v));
                else if (rt->elem && rt->elem->kind != TY_VOID)
                    line(g, "return (%.*s){ .err = 0, .val = %.*s };", S(g->ret_ctype), S(v));
                else line(g, "return (%.*s){ .err = 0 };", S(g->ret_ctype));
            } else {
                line(g, "return %.*s;", S(v));
            }
            break;
        }

        case ST_BREAK: line(g, "break;"); break;
        case ST_CONTINUE: line(g, "continue;"); break;
        case ST_DEFER: {
            /* v0.1 runs a `defer` where it is written; scope-exit ordering
             * arrives with destructors. Documented in docs/SPEC.md. */
            Str v = gen_expr(g, s->expr);
            if (!str_eq_c(v, "((void)0)")) line(g, "(void)(%.*s);", S(v));
            break;
        }
        default: break;
    }
}

static void gen_block(G *g, Expr *b) {
    if (!b || b->kind != EX_BLOCK) return;
    for (uint32_t i = 0; i < b->block.stmts.len; i++) gen_stmt(g, b->block.stmts.data[i]);
}

/* ---- functions --------------------------------------------------------- */

static Str fn_signature(G *g, Item *it) {
    SB sb;
    sb_init(&sb, g->a);
    Str ret = ctype(g, it->rtype);
    Str nm  = mangle(g, it->qual_name);
    sb_fmt(&sb, "%.*s %.*s(", S(ret), S(nm));

    if (it->fn.params.len == 0) sb_cstr(&sb, "void");
    for (uint32_t i = 0; i < it->fn.params.len; i++) {
        Param *pm = &it->fn.params.data[i];
        if (i) sb_cstr(&sb, ", ");
        Str ct = ctype(g, pm->rtype);
        Str pn = local_name(g, pm->name);
        if (pm->conv == CONV_INOUT || pm->conv == CONV_SET)
            sb_fmt(&sb, "%.*s *restrict %.*s", S(ct), S(pn));
        else sb_fmt(&sb, "%.*s %.*s", S(ct), S(pn));
    }
    sb_char(&sb, ')');
    return sb_finish(&sb);
}

static void gen_fn(G *g, Item *it, Expr *body) {
    g->fn        = it;
    g->tmp       = 0;
    g->ret_ctype = ctype(g, it->rtype);

    g->cur = &g->out;
    Str sig = fn_signature(g, it);
    line(g, "%.*s {", S(sig));
    g->indent++;
    gen_block(g, body);
    /* A non-void function whose flow analysis passed still needs a terminator
     * for C, which cannot see what the checker proved. */
    if (it->rtype && it->rtype->kind != TY_VOID) {
        if (it->rtype->kind == TY_ERRUNION)
            line(g, "return (%.*s){ .err = 0 };", S(g->ret_ctype));
        else line(g, "return %.*s;", S(zero_of(g, it->rtype)));
    }
    g->indent--;
    line(g, "}");
    line(g, "");
    g->fn = NULL;
}

/* ---- program ----------------------------------------------------------- */

/* ---- native profile lint ----------------------------------------------- */

/* The type checker accepts these because they are real types with a real
 * lowering planned; the native backend simply cannot emit them yet. Saying so
 * beats emitting C that clang rejects with a message about a type the user
 * never wrote. */
static void lint_native_type(DiagBag *d, Arena *a, Type *t, Span at, const char *what) {
    if (!t) return;
    switch (t->kind) {
        case TY_MAP: {
            Diag *dg = diag_error(d, 901, at,
                                  "`Map<K, V>` has no native representation in v0.1");
            diag_note(dg, "it lowers to the engine's own `map` on the enfusion target, "
                          "where it works today");
            diag_help(dg, "use `List<T>` with a linear scan, or build for enfusion, for "
                          "%s", what);
            break;
        }
        case TY_BOX:
        case TY_RC:
        case TY_POOL:
        case TY_HANDLE: {
            Diag *dg = diag_error(d, 902, at,
                                  "`%.*s` is not implemented in v0.1",
                                  (int)ty_name(a, t).len, ty_name(a, t).ptr);
            diag_note(dg, "the ownership model is designed around these, but v0.1 ships "
                          "only value types, arrays and List");
            diag_help(dg, "use a value, an array index, or `List<T>` for %s", what);
            break;
        }
        case TY_ARRAY:
        case TY_LIST:
        case TY_OPTION:
        case TY_ERRUNION: lint_native_type(d, a, t->elem, at, what); break;
        default: break;
    }
}

static bool lint_native(DiagBag *d, Arena *a, Program *p) {
    uint32_t before = diag_errors(d);
    for (uint32_t m = 0; m < p->modules.len; m++) {
        Module *mod = p->modules.data[m];
        for (uint32_t i = 0; i < mod->items.len; i++) {
            Item *it = mod->items.data[i];
            if (it->kind == IT_STRUCT) {
                for (uint32_t f = 0; f < it->strukt.fields.len; f++)
                    lint_native_type(d, a, it->strukt.fields.data[f].rtype,
                                     it->strukt.fields.data[f].span, "this field");
            } else if (it->kind == IT_FN && !it->fn.generics.len) {
                for (uint32_t q = 0; q < it->fn.params.len; q++)
                    lint_native_type(d, a, it->fn.params.data[q].rtype,
                                     it->fn.params.data[q].span, "this parameter");
                lint_native_type(d, a, it->rtype, it->span, "this return type");
            }
        }
    }
    return diag_errors(d) == before;
}

Str cgen_program(Arena *a, SourceMap *sm, DiagBag *d, Program *p, CgenMode mode) {
    if (!lint_native(d, a, p)) return STR_EMPTY;

    G g = {0};
    g.a = a;
    g.sm = sm;
    g.d = d;
    g.p = p;
    g.emitted = map_new(a);
    g.memo    = map_new(a);
    sb_init(&g.types, a);
    sb_init(&g.protos, a);
    sb_init(&g.out, a);
    g.cur = &g.out;

    /* Emit named types first so signatures can refer to them. */
    for (uint32_t m = 0; m < p->modules.len; m++) {
        Module *mod = p->modules.data[m];
        for (uint32_t i = 0; i < mod->items.len; i++) {
            Item *it = mod->items.data[i];
            if ((it->kind == IT_STRUCT || it->kind == IT_ENUM) && it->rtype)
                ensure_type(&g, it->rtype);
        }
    }

    /* Constants. */
    g.cur = &g.protos;
    for (uint32_t m = 0; m < p->modules.len; m++) {
        Module *mod = p->modules.data[m];
        for (uint32_t i = 0; i < mod->items.len; i++) {
            Item *it = mod->items.data[i];
            if (it->kind != IT_CONST || !it->konst.value) continue;
            Str ct = ctype(&g, it->rtype);
            Str nm = mangle(&g, it->qual_name);
            /* folded below */
            line(&g, "static const %.*s %.*s = %.*s;", S(ct), S(nm),
                 S(const_literal(&g, it->konst.value, it->rtype)));
        }
    }

    /* Prototypes. */
    for (uint32_t m = 0; m < p->modules.len; m++) {
        Module *mod = p->modules.data[m];
        for (uint32_t i = 0; i < mod->items.len; i++) {
            Item *it = mod->items.data[i];
            if (it->kind != IT_FN || it->fn.generics.len || !it->fn.body) continue;
            Str sig = fn_signature(&g, it);
            line(&g, "%.*s;", S(sig));
        }
        for (uint32_t i = 0; i < mod->items.len; i++) {
            Item *it = mod->items.data[i];
            if (it->kind != IT_TEST || !it->test.body) continue;
            Str nm = item_symbol(&g, it);
            line(&g, "static void %.*s(void);", S(nm));
        }
    }
    line(&g, "");

    /* Bodies. */
    Item *user_main = NULL;
    VEC(Item *) tests = {0};

    for (uint32_t m = 0; m < p->modules.len; m++) {
        Module *mod = p->modules.data[m];
        for (uint32_t i = 0; i < mod->items.len; i++) {
            Item *it = mod->items.data[i];
            if (it->kind == IT_FN && !it->fn.generics.len && it->fn.body) {
                gen_fn(&g, it, it->fn.body);
                if (str_eq_c(it->name, "main") && str_empty(it->fn.recv)) user_main = it;
            } else if (it->kind == IT_TEST && it->test.body) {
                g.fn        = it;
                g.tmp       = 0;
                g.ret_ctype = str_from("void");
                g.cur       = &g.out;
                Str nm      = item_symbol(&g, it);
                line(&g, "static void %.*s(void) {", S(nm));
                g.indent++;
                gen_block(&g, it->test.body);
                g.indent--;
                line(&g, "}");
                line(&g, "");
                g.fn = NULL;
                vec_push(a, tests, it);
            }
        }
    }

    /* Entry point. */
    g.cur = &g.out;
    if (mode == CGEN_TESTS) {
        line(&g, "int main(void) {");
        g.indent++;
        for (uint32_t i = 0; i < tests.len; i++) {
            Item *it = tests.data[i];
            SB    nb;
            sb_init(&nb, a);
            emit_c_string(&nb, it->test.label);
            line(&g, "beryl_test_begin(%.*s);", S(sb_finish(&nb)));
            line(&g, "%.*s();", S(item_symbol(&g, it)));
        }
        line(&g, "return beryl_test_summary();");
        g.indent--;
        line(&g, "}");
    } else if (user_main) {
        line(&g, "int main(void) {");
        g.indent++;
        Str nm = mangle(&g, user_main->qual_name);
        if (user_main->rtype && user_main->rtype->kind == TY_INT)
            line(&g, "return (int)%.*s();", S(nm));
        else {
            line(&g, "%.*s();", S(nm));
            line(&g, "return 0;");
        }
        g.indent--;
        line(&g, "}");
    }

    /* Assemble. */
    SB final;
    sb_init(&final, a);
    sb_cstr(&final, "/* Generated by beryl. Do not edit. */\n");
    sb_cstr(&final, "#include \"beryl_rt.h\"\n\n");
    sb_str(&final, sb_finish(&g.types));
    sb_char(&final, '\n');
    sb_str(&final, sb_finish(&g.protos));
    sb_char(&final, '\n');
    sb_str(&final, sb_finish(&g.out));
    return sb_finish(&final);
}
