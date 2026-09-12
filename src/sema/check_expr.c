/* check_expr.c — expression type checking. */
#include "check.h"

#include "intrinsic.h"
#include <stdlib.h>

/* Built-ins are only reachable when no user function shadows the name, so a
 * project is always free to define its own `min` or `print`. */
static Type *chk_intrinsic(C *c, Expr *e, Intrinsic id) {
    ArgVec   args = e->call.args;
    uint32_t n    = args.len;
    e->res_kind   = RES_INTRINSIC;
    e->intrinsic  = (uint8_t)id;

    Type *vd = ty_prim(c->tc, TY_VOID);

    switch (id) {
        case INTR_PRINT:
        case INTR_PRINTLN: {
            if (id == INTR_PRINT && n != 1) {
                diag_error(c->d, 304, e->span, "`print` takes 1 argument, found %u", n);
                for (uint32_t i = 0; i < n; i++) chk(c, args.data[i].value, NULL);
                return vd;
            }
            if (n > 1) {
                diag_error(c->d, 304, e->span, "`println` takes 0 or 1 arguments, found %u",
                           n);
            }
            for (uint32_t i = 0; i < n; i++) {
                Type *at = chk(c, args.data[i].value, NULL);
                if (ty_is_error(at)) continue;
                bool printable = ty_is_numeric(at) || at->kind == TY_BOOL ||
                                 at->kind == TY_STR || at->kind == TY_CHAR;
                if (!printable) {
                    Diag *dg = diag_error(c->d, 303, args.data[i].value->span,
                                          "`%.*s` cannot be printed",
                                          (int)ty_name(c->a, at).len, ty_name(c->a, at).ptr);
                    diag_help(dg, "print its fields, or a number derived from it");
                }
            }
            return vd;
        }

        case INTR_ASSERT: {
            Type *bt = ty_prim(c->tc, TY_BOOL);
            if (n != 1) {
                diag_error(c->d, 304, e->span, "`assert` takes 1 argument, found %u", n);
                for (uint32_t i = 0; i < n; i++) chk(c, args.data[i].value, NULL);
                return vd;
            }
            Type *at = chk(c, args.data[0].value, bt);
            chk_expect_type(c, args.data[0].value->span, bt, at, "in an assertion");
            return vd;
        }

        case INTR_MIN:
        case INTR_MAX:
        case INTR_CLAMP: {
            uint32_t want = (id == INTR_CLAMP) ? 3 : 2;
            if (n != want) {
                diag_error(c->d, 304, e->span, "`%s` takes %u arguments, found %u",
                           intrinsic_name(id), want, n);
                for (uint32_t i = 0; i < n; i++) chk(c, args.data[i].value, NULL);
                return chk_err(c);
            }
            Type *first = chk(c, args.data[0].value, NULL);
            for (uint32_t i = 1; i < n; i++) {
                Type *at = chk(c, args.data[i].value, first);
                chk_expect_type(c, args.data[i].value->span, first, at,
                                "in this argument");
            }
            if (!ty_is_error(first) && !ty_is_numeric(first)) {
                diag_error(c->d, 303, e->span, "`%s` requires numbers, found `%.*s`",
                           intrinsic_name(id), (int)ty_name(c->a, first).len,
                           ty_name(c->a, first).ptr);
                return chk_err(c);
            }
            return first;
        }

        case INTR_WRAPPING_ADD:
        case INTR_WRAPPING_SUB:
        case INTR_WRAPPING_MUL:
        case INTR_SATURATING_ADD:
        case INTR_SATURATING_SUB: {
            if (n != 2) {
                diag_error(c->d, 304, e->span, "`%s` takes 2 arguments, found %u",
                           intrinsic_name(id), n);
                for (uint32_t i = 0; i < n; i++) chk(c, args.data[i].value, NULL);
                return chk_err(c);
            }
            Type *lt = chk(c, args.data[0].value, NULL);
            Type *rt = chk(c, args.data[1].value, lt);
            chk_expect_type(c, args.data[1].value->span, lt, rt, "in this argument");
            if (!ty_is_error(lt) && !ty_is_integer(lt)) {
                Diag *dg = diag_error(c->d, 303, e->span,
                                      "`%s` requires an integer, found `%.*s`",
                                      intrinsic_name(id), (int)ty_name(c->a, lt).len,
                                      ty_name(c->a, lt).ptr);
                diag_note(dg, "these exist to opt out of the overflow trap, which only "
                              "applies to integers");
                return chk_err(c);
            }
            return lt;
        }

        case INTR_ABS:
        case INTR_SQRT: {
            if (n != 1) {
                diag_error(c->d, 304, e->span, "`%s` takes 1 argument, found %u",
                           intrinsic_name(id), n);
                for (uint32_t i = 0; i < n; i++) chk(c, args.data[i].value, NULL);
                return chk_err(c);
            }
            Type *at = chk(c, args.data[0].value, NULL);
            if (ty_is_error(at)) return at;
            if (id == INTR_SQRT && !ty_is_float(at)) {
                Diag *dg = diag_error(c->d, 303, e->span,
                                      "`sqrt` requires a float, found `%.*s`",
                                      (int)ty_name(c->a, at).len, ty_name(c->a, at).ptr);
                diag_help(dg, "cast first: `sqrt(x as f64)`");
                return chk_err(c);
            }
            if (!ty_is_numeric(at)) {
                diag_error(c->d, 303, e->span, "`abs` requires a number, found `%.*s`",
                           (int)ty_name(c->a, at).len, ty_name(c->a, at).ptr);
                return chk_err(c);
            }
            return at;
        }

        default: return chk_err(c);
    }
}

Type *chk_err(C *c) { return ty_prim(c->tc, TY_ERROR); }

void chk_expect_type(C *c, Span at, Type *want, Type *found, const char *ctx) {
    if (ty_is_error(want) || ty_is_error(found) || ty_eq(want, found)) return;

    /* Two numeric types that differ is the single most common mistake in a
     * language with no implicit conversion, so it gets its own code and a
     * help line showing the cast. */
    if (ty_is_numeric(want) && ty_is_numeric(found)) {
        Diag *dg = diag_error(c->d, 312, at, "expected `%.*s`, found `%.*s` %s",
                              (int)ty_name(c->a, want).len, ty_name(c->a, want).ptr,
                              (int)ty_name(c->a, found).len, ty_name(c->a, found).ptr, ctx);
        diag_note(dg, "Beryl performs no implicit numeric conversion, not even widening");
        diag_help(dg, "write an explicit cast: `... as %.*s`", (int)ty_name(c->a, want).len,
                  ty_name(c->a, want).ptr);
        return;
    }

    diag_error(c->d, 303, at, "expected `%.*s`, found `%.*s` %s",
               (int)ty_name(c->a, want).len, ty_name(c->a, want).ptr,
               (int)ty_name(c->a, found).len, ty_name(c->a, found).ptr, ctx);
}

static Type *suffix_type(C *c, Str suffix) {
    uint8_t  b = 0;
    bool     s = false;
    TypeKind k = ty_prim_from_name(suffix, &b, &s);
    if (k == TY_FLOAT) return ty_float(c->tc, b);
    if (k == TY_INT) return ty_int(c->tc, b, s);
    return NULL;
}

/* The largest magnitude an integer type can hold, given whether the literal
 * is about to be negated. A signed type reaches one further downward, which
 * is the whole reason `neg_ctx` exists. */
static uint64_t int_limit(const Type *t, bool negated) {
    if (t->bits >= 64) return t->is_signed ? (negated ? 0x8000000000000000ULL
                                                      : 0x7fffffffffffffffULL)
                                           : 0xffffffffffffffffULL;
    uint64_t span = 1ULL << t->bits;
    if (!t->is_signed) return span - 1;
    return negated ? span / 2 : span / 2 - 1;
}

static Type *chk_int_lit(C *c, Expr *e, Type *expected) {
    Type *t = suffix_type(c, e->int_lit.suffix);
    if (!t) {
        /* An integer literal is polymorphic until context fixes it. Adopting a
         * float type is not a conversion — there is no runtime value yet. */
        if (expected && ty_is_numeric(expected)) t = expected;
        else t = ty_int(c->tc, 32, true);
    }

    /* A literal too large for the type it lands in was silently truncated by
     * the C back end: `let x: i8 = 300` emitted `int8_t x = 300LL` and the
     * program saw 44. Nothing about that is a conversion the language
     * permits, so it is an error rather than a narrowing. */
    if (ty_is_integer(t)) {
        uint64_t lim = int_limit(t, e->int_lit.neg_ctx);
        if (e->int_lit.val > lim) {
            Diag *dg = diag_error(c->d, 321, e->span,
                                  "`%s%llu` does not fit in `%.*s`",
                                  e->int_lit.neg_ctx ? "-" : "",
                                  (unsigned long long)e->int_lit.val,
                                  (int)ty_name(c->a, t).len, ty_name(c->a, t).ptr);
            diag_note(dg, "`%.*s` holds %s%llu at most",
                      (int)ty_name(c->a, t).len, ty_name(c->a, t).ptr,
                      e->int_lit.neg_ctx ? "-" : "", (unsigned long long)lim);
            diag_help(dg, "use a wider type, or write the value you meant");
        }
    }
    return t;
}

static Type *chk_float_lit(C *c, Expr *e, Type *expected) {
    Type *t = suffix_type(c, e->float_lit.suffix);
    if (!t) {
        if (expected && ty_is_float(expected)) t = expected;
        else if (expected && ty_is_integer(expected)) {
            diag_error(c->d, 303, e->span,
                       "a fractional literal cannot have the integer type `%.*s`",
                       (int)ty_name(c->a, expected).len, ty_name(c->a, expected).ptr);
            t = chk_err(c);
        } else {
            t = ty_float(c->tc, 64);
        }
    }
    if (t && t->kind==TY_FLOAT && t->bits==32 && e->float_lit.spelling.len)
        e->float_lit.val=(double)strtof(str_cstr(c->a,e->float_lit.spelling),NULL);
    return t;
}

static Type *chk_path(C *c, Expr *e) {
    if (e->path.segs.len == 0) return chk_err(c);
    Str name = e->path.segs.data[0];

    Local *l = chk_lookup(c, name);
    if (l) {
        e->res      = l;
        e->res_kind = RES_LOCAL;
        return l->type;
    }

    Item *it = prog_lookup(c->p, c->mod, path_str(c->a, e->path.segs));
    if (it) {
        if (!prog_accessible(c->d, c->mod, it, e->span)) return chk_err(c);
        if (it->kind == IT_CONST) {
            e->res      = it;
            e->res_kind = RES_CONST;
            return chk_const(c, it);
        }
        if (it->kind == IT_FN) {
            e->res      = it;
            e->res_kind = RES_FN;
            return ty_prim(c->tc, TY_VOID); /* only meaningful under a call */
        }
        if (it->kind == IT_STRUCT || it->kind == IT_ENUM) {
            e->res      = it;
            e->res_kind = RES_TYPE;
            return it->rtype ? it->rtype : chk_err(c);
        }
    }

    Diag *dg = diag_error(c->d, 301, e->span, "cannot find `%.*s` in this scope",
                          (int)name.len, name.ptr);
    diag_help(dg, "check the spelling, or declare it with `let` or `var`");
    return chk_err(c);
}

static bool is_arith(TokKind k) {
    return k == TK_PLUS || k == TK_MINUS || k == TK_STAR || k == TK_SLASH || k == TK_PERCENT;
}
static bool is_cmp_op(TokKind k) {
    return k == TK_EQ || k == TK_NE || k == TK_LT || k == TK_LE || k == TK_GT || k == TK_GE;
}
static bool is_bitwise(TokKind k) {
    return k == TK_AMP || k == TK_PIPE || k == TK_CARET || k == TK_SHL || k == TK_SHR;
}

static Type *chk_binary(C *c, Expr *e, Type *expected) {
    TokKind op = e->binary.op;

    if (op == TK_ANDAND || op == TK_OROR) {
        Type *bt = ty_prim(c->tc, TY_BOOL);
        Type *lt = chk(c, e->binary.lhs, bt);
        Type *rt = chk(c, e->binary.rhs, bt);
        chk_expect_type(c, e->binary.lhs->span, bt, lt, "in a logical operand");
        chk_expect_type(c, e->binary.rhs->span, bt, rt, "in a logical operand");
        return bt;
    }

    Type *want  = (is_arith(op) && expected && ty_is_numeric(expected)) ? expected : NULL;
    Type *lt    = chk(c, e->binary.lhs, want);
    bool  scale = (op == TK_STAR || op == TK_SLASH);

    /* A vector scales by an `f32`, so that is what the right-hand side is
     * offered. It is only a hint — `v * w` still checks as component-wise —
     * but without it a literal in `v * 2.0` defaults to f64 and the operand
     * types never line up. */
    Type *rwant = (scale && ty_is_vec(lt)) ? ty_float(c->tc, 32) : lt;
    Type *rt    = chk(c, e->binary.rhs, rwant);

    if (ty_is_error(lt) || ty_is_error(rt)) return chk_err(c);

    if (!ty_eq(lt, rt)) {
        /* Scaling a vector by a scalar. Accepted on either side for `*`, and
         * on the left only for `/`, because `2.0 / v` is not a scaling — it
         * is a component-wise reciprocal, and spelling that as a division
         * would hide what it does. */
        Type *f32 = ty_float(c->tc, 32);
        if (scale && ty_is_vec(lt) && ty_eq(rt, f32)) return lt;
        if (op == TK_STAR && ty_eq(lt, f32) && ty_is_vec(rt)) return rt;

        /* `2.0 * v`. The left operand was checked before the right was known,
         * so a bare literal defaulted to f64. A literal has no runtime value
         * yet, so re-fixing it as f32 is not a conversion — the same rule
         * that lets `let x: f32 = 1` work. A typed f64 *value* still fails,
         * which is D5 doing its job. */
        if (op == TK_STAR && ty_is_float(lt) && ty_is_vec(rt) &&
            (e->binary.lhs->kind == EX_FLOAT || e->binary.lhs->kind == EX_INT)) {
            chk(c, e->binary.lhs, f32);
            e->binary.lhs->type = f32;
            return rt;
        }

        chk_expect_type(c, e->binary.rhs->span, lt, rt, "on the right of this operator");
        return is_cmp_op(op) ? ty_prim(c->tc, TY_BOOL) : lt;
    }

    if (is_cmp_op(op)) {
        if (op != TK_EQ && op != TK_NE && !ty_is_numeric(lt) && lt->kind != TY_STR &&
            lt->kind != TY_CHAR) {
            diag_error(c->d, 303, e->span, "`%.*s` is not ordered, so `%s` does not apply",
                       (int)ty_name(c->a, lt).len, ty_name(c->a, lt).ptr, tok_name(op));
        }
        return ty_prim(c->tc, TY_BOOL);
    }

    if (is_bitwise(op) && !ty_is_integer(lt)) {
        diag_error(c->d, 303, e->span, "`%s` requires an integer, found `%.*s`",
                   tok_name(op), (int)ty_name(c->a, lt).len, ty_name(c->a, lt).ptr);
        return chk_err(c);
    }

    if (is_arith(op)) {
        if (!ty_is_numeric(lt) && !ty_is_vec(lt)) {
            diag_error(c->d, 303, e->span, "`%s` requires a number, found `%.*s`",
                       tok_name(op), (int)ty_name(c->a, lt).len, ty_name(c->a, lt).ptr);
            return chk_err(c);
        }
        if (op == TK_PERCENT && !ty_is_integer(lt)) {
            diag_error(c->d, 303, e->span, "`%%` requires an integer, found `%.*s`",
                       (int)ty_name(c->a, lt).len, ty_name(c->a, lt).ptr);
            return chk_err(c);
        }
    }
    return lt;
}

static Type *chk_unary(C *c, Expr *e, Type *expected) {
    TokKind op = e->unary.op;
    if (op == TK_BANG) {
        Type *bt = ty_prim(c->tc, TY_BOOL);
        Type *t  = chk(c, e->unary.operand, bt);
        chk_expect_type(c, e->unary.operand->span, bt, t, "after `!`");
        return bt;
    }
    /* `-2147483648` is one expression to a reader and two nodes to the
     * parser. Telling the literal it is about to be negated is what lets the
     * range check accept the signed minimum without also accepting its
     * positive twin. */
    if (op == TK_MINUS && e->unary.operand && e->unary.operand->kind == EX_INT)
        e->unary.operand->int_lit.neg_ctx = true;

    Type *t = chk(c, e->unary.operand, expected);
    if (ty_is_error(t)) return t;
    if (op == TK_MINUS && !ty_is_numeric(t) && !ty_is_vec(t)) {
        diag_error(c->d, 303, e->span, "cannot negate `%.*s`", (int)ty_name(c->a, t).len,
                   ty_name(c->a, t).ptr);
        return chk_err(c);
    }
    if (op == TK_TILDE && !ty_is_integer(t)) {
        diag_error(c->d, 303, e->span, "`~` requires an integer, found `%.*s`",
                   (int)ty_name(c->a, t).len, ty_name(c->a, t).ptr);
        return chk_err(c);
    }
    return t;
}

static Field *find_field(Type *t, Str name) {
    if (!t || t->kind != TY_STRUCT || !t->decl) return NULL;
    Item *it = t->decl;
    for (uint32_t i = 0; i < it->strukt.fields.len; i++)
        if (str_eq(it->strukt.fields.data[i].name, name)) return &it->strukt.fields.data[i];
    return NULL;
}

/* `v.x` / `.y` / `.z` / `.w` on Vec2/3/4.
 *
 * Components are named rather than only indexed because that is how vector
 * code is actually written, and because a name can be checked against the
 * arity: `.z` on a `Vec2` is a compile error, where `v[2]` could only trap at
 * run time. Both spellings are accepted; this is the one that catches more. */
static Type *chk_vec_component(C *c, Expr *e, Type *vt) {
    Str      name  = e->field.name;
    uint32_t arity = ty_vec_arity(vt);
    uint32_t idx   = 4;

    if (name.len == 1) {
        switch (name.ptr[0]) {
            case 'x': idx = 0; break;
            case 'y': idx = 1; break;
            case 'z': idx = 2; break;
            case 'w': idx = 3; break;
            default: break;
        }
    }

    if (idx == 4) {
        Diag *dg = diag_error(c->d, 305, e->span, "no component `%.*s` on `%.*s`",
                              (int)name.len, name.ptr, (int)ty_name(c->a, vt).len,
                              ty_name(c->a, vt).ptr);
        diag_help(dg, "components are %s", arity == 2   ? "`x` and `y`"
                                           : arity == 3 ? "`x`, `y` and `z`"
                                                        : "`x`, `y`, `z` and `w`");
        return chk_err(c);
    }

    if (idx >= arity) {
        Diag *dg = diag_error(c->d, 320, e->span, "`%.*s` has no `%.*s` component",
                              (int)ty_name(c->a, vt).len, ty_name(c->a, vt).ptr,
                              (int)name.len, name.ptr);
        diag_note(dg, "`%.*s` has %u components", (int)ty_name(c->a, vt).len,
                  ty_name(c->a, vt).ptr, arity);
        return chk_err(c);
    }

    e->res_kind  = RES_VEC_COMP;
    e->intrinsic = (uint8_t)idx;
    return ty_float(c->tc, 32);
}

/* Checks the arguments of a call against a function item. */
static bool call_storage(Expr *e) {
    if (!e) return false;
    if (e->kind == EX_FIELD) return call_storage(e->field.base);
    if (e->kind == EX_INDEX) return call_storage(e->index.base);
    return (e->kind == EX_PATH || e->kind == EX_SELF) && e->res_kind == RES_LOCAL;
}

static Type *chk_call_item(C *c, Expr *e, Item *fn, bool has_self) {
    if (fn->fn.generics.len > 0) {
        /* Monomorphization is v0.2. Saying so plainly beats letting the call
         * type-check against unsubstituted parameters and fail somewhere
         * downstream with no obvious cause. */
        Diag *dg = diag_error(c->d, 508, e->span,
                              "`%.*s` is generic, and v0.1 does not instantiate "
                              "user-defined generics",
                              (int)fn->name.len, fn->name.ptr);
        diag_label(dg, fn->span, "declared with type parameters here");
        diag_note(dg, "the built-in generic containers — List, Map, Box, Rc, Pool, "
                      "Handle — are intrinsic and fully supported");
        diag_help(dg, "write a concrete version for now, or use `min`/`max`/`clamp` "
                      "if that is what you needed");
        for (uint32_t i = 0; i < e->call.args.len; i++)
            chk(c, e->call.args.data[i].value, NULL);
        return chk_err(c);
    }
    ArgVec  args   = e->call.args;
    uint32_t formal = fn->fn.params.len;
    uint32_t first  = has_self ? 1 : 0;
    uint32_t given  = args.len + first;

    uint32_t required = 0;
    for (uint32_t i = 0; i < formal; i++)
        if (!fn->fn.params.data[i].deflt) required = i + 1;

    if (given > formal || given < required) {
        Diag *dg = diag_error(c->d, 304, e->span,
                              "`%.*s` takes %u argument%s, found %u",
                              (int)fn->name.len, fn->name.ptr, formal - first,
                              (formal - first) == 1 ? "" : "s", args.len);
        diag_label(dg, fn->span, "defined here");
        return fn->rtype ? fn->rtype : chk_err(c);
    }

    for (uint32_t i = 0; i < args.len; i++) {
        Param *pm = &fn->fn.params.data[i + first];
        Type  *at = chk(c, args.data[i].value, pm->rtype);
        if ((pm->conv == CONV_INOUT || pm->conv == CONV_SET) && !call_storage(args.data[i].value))
            diag_error(c->d, 303, args.data[i].span,
                       "an `%s` argument must name local storage", conv_name(pm->conv));
        chk_expect_type(c, args.data[i].value->span, pm->rtype, at, "in this argument");

        if (args.data[i].conv != pm->conv) {
            /* A convention mismatch is a real error: `inout` at the call site
             * is what makes exclusive borrowing visible to the reader. */
            Diag *dg = diag_error(c->d, 303, args.data[i].span,
                                  "argument is declared `%s` but passed as `%s`",
                                  conv_name(pm->conv), conv_name(args.data[i].conv));
            diag_label(dg, pm->span, "declared here");
            if (pm->conv == CONV_INOUT)
                diag_help(dg, "write `inout` at the call site: it is what marks the "
                              "exclusive borrow for the reader");
            else if (pm->conv == CONV_LET && args.data[i].conv != CONV_LET)
                diag_help(dg, "drop the `%s`: this parameter only borrows",
                          conv_name(args.data[i].conv));
        }
    }
    return fn->rtype ? fn->rtype : ty_prim(c->tc, TY_VOID);
}

/* Methods on `List<T>`. The receiver is the base of the field access, so it
 * is already checked by the time this runs. */
static Type *chk_list_method(C *c, Expr *e, Type *lt, Str name) {
    Intrinsic id = intrinsic_list_method(name);
    if (id == INTR_NONE) {
        Diag *dg = diag_error(c->d, 306, e->call.callee->span,
                              "no method `%.*s` on `%.*s`", (int)name.len, name.ptr,
                              (int)ty_name(c->a, lt).len, ty_name(c->a, lt).ptr);
        diag_help(dg, "`List<T>` has len, push, get, set and clear");
        for (uint32_t i = 0; i < e->call.args.len; i++)
            chk(c, e->call.args.data[i].value, NULL);
        return chk_err(c);
    }

    e->res_kind  = RES_INTRINSIC;
    e->intrinsic = (uint8_t)id;

    Type    *i32 = ty_int(c->tc, 32, true);
    Type    *vd  = ty_prim(c->tc, TY_VOID);
    uint32_t n   = e->call.args.len;

    uint32_t want = (id == INTR_LIST_SET)                              ? 2
                    : (id == INTR_LIST_PUSH || id == INTR_LIST_GET)    ? 1
                                                                       : 0;
    if (n != want) {
        diag_error(c->d, 304, e->span, "`%.*s` takes %u argument%s, found %u",
                   (int)name.len, name.ptr, want, want == 1 ? "" : "s", n);
        for (uint32_t i = 0; i < n; i++) chk(c, e->call.args.data[i].value, NULL);
        return (id == INTR_LIST_GET) ? lt->elem : (id == INTR_LIST_LEN ? i32 : vd);
    }

    switch (id) {
        case INTR_LIST_LEN: return i32;
        case INTR_LIST_CLEAR: return vd;
        case INTR_LIST_PUSH: {
            Type *at = chk(c, e->call.args.data[0].value, lt->elem);
            chk_expect_type(c, e->call.args.data[0].value->span, lt->elem, at,
                            "in this `push`");
            return vd;
        }
        case INTR_LIST_GET: {
            Type *it = chk(c, e->call.args.data[0].value, i32);
            chk_expect_type(c, e->call.args.data[0].value->span, i32, it,
                            "as a list index");
            return lt->elem;
        }
        default: { /* INTR_LIST_SET */
            Type *it = chk(c, e->call.args.data[0].value, i32);
            chk_expect_type(c, e->call.args.data[0].value->span, i32, it,
                            "as a list index");
            Type *at = chk(c, e->call.args.data[1].value, lt->elem);
            chk_expect_type(c, e->call.args.data[1].value->span, lt->elem, at,
                            "in this `set`");
            return vd;
        }
    }
}

/* `Vec3(x, y, z)`. Every component is `f32` on both targets, so a float
 * literal argument adopts f32 rather than defaulting to f64 — which is the
 * whole reason the expected type is threaded through here. */
static Type *chk_vec_new(C *c, Expr *e, Type *vt) {
    uint32_t arity = ty_vec_arity(vt);
    uint32_t n     = e->call.args.len;
    Type    *f32   = ty_float(c->tc, 32);

    e->res_kind  = RES_INTRINSIC;
    e->intrinsic = (uint8_t)(INTR_VEC2_NEW + (arity - 2));

    if (n != arity) {
        Diag *dg = diag_error(c->d, 304, e->span, "`%.*s` takes %u arguments, found %u",
                              (int)ty_name(c->a, vt).len, ty_name(c->a, vt).ptr, arity, n);
        diag_help(dg, "one `f32` per component");
        for (uint32_t i = 0; i < n; i++) chk(c, e->call.args.data[i].value, f32);
        return vt;
    }

    for (uint32_t i = 0; i < n; i++) {
        Type *at = chk(c, e->call.args.data[i].value, f32);
        chk_expect_type(c, e->call.args.data[i].value->span, f32, at,
                        "as a vector component");
    }
    return vt;
}

/* Methods on Vec2/3/4. Like the list methods these are intrinsic, because the
 * Enfusion target has them on its own `vector` and a Beryl reimplementation
 * would be both slower and subtly different. */
static Type *chk_vec_method(C *c, Expr *e, Type *vt, Str name) {
    Intrinsic id    = intrinsic_vec_method(name);
    uint32_t  arity = ty_vec_arity(vt);
    Type     *f32   = ty_float(c->tc, 32);

    if (id == INTR_NONE) {
        Diag *dg = diag_error(c->d, 306, e->call.callee->span, "no method `%.*s` on `%.*s`",
                              (int)name.len, name.ptr, (int)ty_name(c->a, vt).len,
                              ty_name(c->a, vt).ptr);
        diag_help(dg, "`%.*s` has length, length_sq, dot, distance and normalized%s",
                  (int)ty_name(c->a, vt).len, ty_name(c->a, vt).ptr,
                  arity == 3 ? ", plus cross" : "");
        for (uint32_t i = 0; i < e->call.args.len; i++)
            chk(c, e->call.args.data[i].value, NULL);
        return chk_err(c);
    }

    /* The cross product is only defined in three dimensions. Rejecting it by
     * arity rather than by omitting it from the table means the message can
     * name the type the caller actually has. */
    if (id == INTR_VEC_CROSS && arity != 3) {
        Diag *dg = diag_error(c->d, 319, e->call.callee->span,
                              "`cross` is only defined on `Vec3`, found `%.*s`",
                              (int)ty_name(c->a, vt).len, ty_name(c->a, vt).ptr);
        diag_note(dg, "the cross product exists only in three dimensions");
        for (uint32_t i = 0; i < e->call.args.len; i++)
            chk(c, e->call.args.data[i].value, NULL);
        return chk_err(c);
    }

    e->res_kind  = RES_INTRINSIC;
    e->intrinsic = (uint8_t)id;

    bool     binary = (id == INTR_VEC_DOT || id == INTR_VEC_DISTANCE ||
                   id == INTR_VEC_CROSS);
    uint32_t want   = binary ? 1 : 0;
    uint32_t n      = e->call.args.len;
    Type    *ret    = (id == INTR_VEC_NORMALIZED || id == INTR_VEC_CROSS) ? vt : f32;

    if (n != want) {
        diag_error(c->d, 304, e->span, "`%.*s` takes %u argument%s, found %u",
                   (int)name.len, name.ptr, want, want == 1 ? "" : "s", n);
        for (uint32_t i = 0; i < n; i++) chk(c, e->call.args.data[i].value, NULL);
        return ret;
    }

    if (binary) {
        Type *at = chk(c, e->call.args.data[0].value, vt);
        chk_expect_type(c, e->call.args.data[0].value->span, vt, at, "in this call");
    }
    return ret;
}

static Type *chk_call(C *c, Expr *e) {
    Expr *callee = e->call.callee;

    if (callee->kind == EX_PATH) {
        Str   name = callee->path.segs.data[0];
        Local *l   = chk_lookup(c, name);
        if (!l) {
            Item *fn = prog_lookup(c->p, c->mod, name);
            if (fn && !prog_accessible(c->d, c->mod, fn, callee->span)) return chk_err(c);
            if (fn && fn->kind == IT_FN) {
                callee->res      = fn;
                callee->res_kind = RES_FN;
                callee->type     = fn->rtype;
                e->res           = fn;
                e->res_kind      = RES_FN;
                return chk_call_item(c, e, fn, false);
            }
            if (fn && (fn->kind == IT_STRUCT || fn->kind == IT_ENUM)) {
                diag_error(c->d, 307, e->span,
                           "`%.*s` is a type, not a function", (int)name.len, name.ptr);
                return chk_err(c);
            }
            if (fn || (c->mod && c->mod->scope && map_has(((ModuleScope *)c->mod->scope)->imports, name))) {
                diag_error(c->d, 307, e->span, "`%.*s` is not a function", (int)name.len, name.ptr);
                return chk_err(c);
            }
            TypeKind vk = str_eq_c(name, "Vec2")   ? TY_VEC2
                          : str_eq_c(name, "Vec3") ? TY_VEC3
                          : str_eq_c(name, "Vec4") ? TY_VEC4
                                                   : TY_ERROR;
            if (vk != TY_ERROR) return chk_vec_new(c, e, ty_prim(c->tc, vk));

            Intrinsic id = intrinsic_from_name(name);
            if (id != INTR_NONE) return chk_intrinsic(c, e, id);

            Diag *dg = diag_error(c->d, 301, callee->span,
                                  "cannot find function `%.*s` in this scope",
                                  (int)name.len, name.ptr);
            diag_help(dg, "check the spelling, or add a `use` for its module");
            for (uint32_t i = 0; i < e->call.args.len; i++)
                chk(c, e->call.args.data[i].value, NULL);
            return chk_err(c);
        }
        diag_error(c->d, 307, e->span, "`%.*s` is a value, not a function", (int)name.len,
                   name.ptr);
        return chk_err(c);
    }

    if (callee->kind == EX_FIELD) {
        /* Either a module-qualified call, or a method call on a value. */
        Expr *base = callee->field.base;

        Str full, root;
        if (prog_expr_path(c->a, callee, &full, &root) && !chk_lookup(c, root)) {
            Item *fn = prog_lookup(c->p, c->mod, full);
            if (fn && fn->kind == IT_FN && str_empty(fn->fn.recv)) {
                if (!prog_accessible(c->d, c->mod, fn, callee->span)) return chk_err(c);
                callee->res = fn; callee->res_kind = RES_FN; callee->type = fn->rtype;
                e->res      = fn;
                e->res_kind = RES_FN;
                return chk_call_item(c, e, fn, false);
            }
        }

        Type *bt = chk(c, base, NULL);
        if (ty_is_error(bt)) {
            for (uint32_t i = 0; i < e->call.args.len; i++)
                chk(c, e->call.args.data[i].value, NULL);
            return chk_err(c);
        }

        if (bt->kind == TY_LIST) return chk_list_method(c, e, bt, callee->field.name);
        if (ty_is_vec(bt)) return chk_vec_method(c, e, bt, callee->field.name);

        Str   tname = (bt->kind == TY_STRUCT || bt->kind == TY_ENUM) ? bt->name
                                                                    : ty_name(c->a, bt);
        Item *m     = prog_method(c->p, bt->decl, callee->field.name);
        if (!m) {
            Diag *dg = diag_error(c->d, 306, callee->span,
                                  "no method `%.*s` on `%.*s`",
                                  (int)callee->field.name.len, callee->field.name.ptr,
                                  (int)tname.len, tname.ptr);
            diag_help(dg, "methods are declared as `fn %.*s.%.*s(...)`", (int)tname.len,
                      tname.ptr, (int)callee->field.name.len, callee->field.name.ptr);
            for (uint32_t i = 0; i < e->call.args.len; i++)
                chk(c, e->call.args.data[i].value, NULL);
            return chk_err(c);
        }
        if (!prog_accessible(c->d, c->mod, m, callee->span)) return chk_err(c);
        bool has_self = m->fn.params.len && m->fn.params.data[0].is_self;
        if ((base->res_kind == RES_TYPE) == has_self) {
            diag_error(c->d,307,callee->span,has_self ?
                "an instance method requires a receiver value" :
                "a static method must be called through its receiver type");
            return chk_err(c);
        }
        e->res      = m;
        e->res_kind = RES_FN;
        return chk_call_item(c, e, m, has_self);
    }

    diag_error(c->d, 307, e->span, "this expression is not callable");
    return chk_err(c);
}

static Type *chk_struct_lit(C *c, Expr *e) {
    Type *t = resolve_type_expr(c->p, c->d, c->mod, c->scope, e->struct_lit.type);
    if (ty_is_error(t)) return t;
    if (t->kind != TY_STRUCT) {
        diag_error(c->d, 303, e->span, "`%.*s` is not a struct",
                   (int)ty_name(c->a, t).len, ty_name(c->a, t).ptr);
        return chk_err(c);
    }

    Item *decl = t->decl;
    for (uint32_t i = 0; i < e->struct_lit.fields.len; i++) {
        FieldInit *fi = &e->struct_lit.fields.data[i];
        Field     *fl = find_field(t, fi->name);
        if (!fl) {
            Diag *dg = diag_error(c->d, 315, fi->span, "`%.*s` has no field `%.*s`",
                                  (int)t->name.len, t->name.ptr, (int)fi->name.len,
                                  fi->name.ptr);
            diag_label(dg, decl->span, "defined here");
            chk(c, fi->value, NULL);
            continue;
        }
        Type *vt = chk(c, fi->value, fl->rtype);
        chk_expect_type(c, fi->value->span, fl->rtype, vt, "in this field");
    }

    for (uint32_t f = 0; f < decl->strukt.fields.len; f++) {
        Field *fl = &decl->strukt.fields.data[f];
        if (fl->deflt) continue;
        /* A container field starts empty, so a literal need not name it. */
        if (fl->rtype && (fl->rtype->kind == TY_LIST || fl->rtype->kind == TY_MAP))
            continue;
        bool given = false;
        for (uint32_t i = 0; i < e->struct_lit.fields.len; i++)
            if (str_eq(e->struct_lit.fields.data[i].name, fl->name)) given = true;
        if (!given) {
            Diag *dg = diag_error(c->d, 314, e->span, "missing field `%.*s` in `%.*s`",
                                  (int)fl->name.len, fl->name.ptr, (int)t->name.len,
                                  t->name.ptr);
            diag_label(dg, fl->span, "this field has no default and must be given");
        }
    }
    return t;
}

static Type *chk_index(C *c, Expr *e) {
    Type *bt = chk(c, e->index.base, NULL);
    if (ty_is_error(bt)) {
        chk(c, e->index.index, NULL);
        return chk_err(c);
    }
    if (bt->kind == TY_MAP) {
        Type *kt = chk(c, e->index.index, bt->key);
        chk_expect_type(c, e->index.index->span, bt->key, kt, "as a map key");
        return bt->elem;
    }
    if (bt->kind == TY_ARRAY || bt->kind == TY_LIST || bt->kind == TY_POOL ||
        ty_is_vec(bt)) {
        Type *it = chk(c, e->index.index, ty_int(c->tc, 32, true));
        if (!ty_is_integer(it) && !ty_is_error(it))
            diag_error(c->d, 303, e->index.index->span,
                       "an index must be an integer, found `%.*s`",
                       (int)ty_name(c->a, it).len, ty_name(c->a, it).ptr);
        /* A vector's elements are f32 and it carries no `elem`, so the type
         * comes from the arity rather than from the type node. */
        return ty_is_vec(bt) ? ty_float(c->tc, 32) : bt->elem;
    }
    diag_error(c->d, 313, e->span, "`%.*s` cannot be indexed",
               (int)ty_name(c->a, bt).len, ty_name(c->a, bt).ptr);
    chk(c, e->index.index, NULL);
    return chk_err(c);
}

static Type *chk_cast(C *c, Expr *e) {
    Type *from = chk(c, e->cast.value, NULL);
    Type *to   = resolve_type_expr(c->p, c->d, c->mod, c->scope, e->cast.type);
    if (ty_is_error(from) || ty_is_error(to)) return to;

    bool from_ok = ty_is_numeric(from) || from->kind == TY_CHAR || from->kind == TY_ENUM ||
                   from->kind == TY_BOOL;
    bool to_ok = ty_is_numeric(to) || to->kind == TY_CHAR || to->kind == TY_ENUM;
    if (!from_ok || !to_ok) {
        Diag *dg = diag_error(c->d, 303, e->span, "cannot cast `%.*s` to `%.*s`",
                              (int)ty_name(c->a, from).len, ty_name(c->a, from).ptr,
                              (int)ty_name(c->a, to).len, ty_name(c->a, to).ptr);
        diag_note(dg, "`as` converts between numbers, characters and enums only");
    }
    return to;
}

Type *chk(C *c, Expr *e, Type *expected) {
    if (!e) return chk_err(c);
    Type *t = NULL;

    switch (e->kind) {
        case EX_INT: t = chk_int_lit(c, e, expected); break;
        case EX_FLOAT: t = chk_float_lit(c, e, expected); break;
        case EX_STR: t = ty_prim(c->tc, TY_STR); break;
        case EX_CHAR: t = ty_prim(c->tc, TY_CHAR); break;
        case EX_BOOL: t = ty_prim(c->tc, TY_BOOL); break;
        case EX_PATH: t = chk_path(c, e); break;

        case EX_SELF: {
            Local *l = chk_lookup(c, str_from("self"));
            if (!l) {
                diag_error(c->d, 301, e->span, "`self` is only valid inside a method");
                t = chk_err(c);
            } else {
                e->res      = l;
                e->res_kind = RES_LOCAL;
                t           = l->type;
            }
            break;
        }

        case EX_UNARY: t = chk_unary(c, e, expected); break;
        case EX_BINARY: t = chk_binary(c, e, expected); break;
        case EX_CALL: t = chk_call(c, e); break;

        case EX_FIELD: {
            Str full, root;
            if (prog_expr_path(c->a, e, &full, &root) && !chk_lookup(c, root)) {
                Item *item = prog_lookup(c->p, c->mod, full);
                if (item) {
                    /* Keep one resolved representation for both emitters and
                     * constant evaluation. An engine/module name is not a value. */
                    e->kind = EX_PATH;
                    e->path.segs = (StrVec){0};
                    vec_push(c->a, e->path.segs, full);
                    t = chk_path(c, e);
                    break;
                }
            }
            Type *bt = chk(c, e->field.base, NULL);
            if (ty_is_error(bt)) {
                t = chk_err(c);
                break;
            }
            if (ty_is_vec(bt)) {
                t = chk_vec_component(c, e, bt);
                break;
            }
            Field *fl = find_field(bt, e->field.name);
            if (!fl) {
                Diag *dg = diag_error(c->d, 305, e->span, "no field `%.*s` on `%.*s`",
                                      (int)e->field.name.len, e->field.name.ptr,
                                      (int)ty_name(c->a, bt).len, ty_name(c->a, bt).ptr);
                if (bt->decl) diag_label(dg, bt->decl->span, "defined here");
                t = chk_err(c);
                break;
            }
            e->res      = fl;
            e->res_kind = RES_FIELD;
            t           = fl->rtype;
            break;
        }

        case EX_INDEX: t = chk_index(c, e); break;
        case EX_CAST: t = chk_cast(c, e); break;
        case EX_STRUCT_LIT: t = chk_struct_lit(c, e); break;

        case EX_ARRAY_LIT: {
            Type *want = (expected && expected->kind == TY_ARRAY) ? expected->elem : NULL;
            Type *elem = want;
            for (uint32_t i = 0; i < e->array_lit.elems.len; i++) {
                Type *et = chk(c, e->array_lit.elems.data[i], elem);
                if (!elem) elem = et;
                else chk_expect_type(c, e->array_lit.elems.data[i]->span, elem, et,
                                     "in this array element");
            }
            if (!elem) elem = chk_err(c);
            t = ty_array(c->tc, elem, e->array_lit.elems.len);
            break;
        }

        case EX_IF: {
            Type *bt = ty_prim(c->tc, TY_BOOL);
            Type *ct = chk(c, e->if_expr.cond, bt);
            if (!ty_is_error(ct) && !ty_eq(ct, bt)) {
                Diag *dg = diag_error(c->d, 311, e->if_expr.cond->span,
                                      "an `if` condition must be `bool`, found `%.*s`",
                                      (int)ty_name(c->a, ct).len, ty_name(c->a, ct).ptr);
                if (ty_is_numeric(ct))
                    diag_help(dg, "compare explicitly, for example `x != 0`");
            }
            chk(c, e->if_expr.then_blk, NULL);
            if (e->if_expr.else_blk) chk(c, e->if_expr.else_blk, NULL);
            t = ty_prim(c->tc, TY_VOID);
            break;
        }

        case EX_BLOCK:
            chk_block(c, e);
            t = ty_prim(c->tc, TY_VOID);
            break;

        case EX_TRY: {
            Type *it = chk(c, e->try_expr.inner, NULL);
            if (ty_is_error(it)) {
                t = it;
                break;
            }
            if (it->kind != TY_ERRUNION) {
                Diag *dg = diag_error(c->d, 303, e->span,
                                      "`try` needs an error union, found `%.*s`",
                                      (int)ty_name(c->a, it).len, ty_name(c->a, it).ptr);
                diag_help(dg, "only a function returning `!T` produces something to `try`");
                t = chk_err(c);
                break;
            }
            if (!c->ret_ty || c->ret_ty->kind != TY_ERRUNION) {
                Diag *dg = diag_error(c->d, 317, e->span,
                                      "`try` requires the enclosing function to return `!T`");
                if (c->fn) diag_label(dg, c->fn->span, "this function does not");
                diag_help(dg, "change the return type to `!%.*s`, or handle the error with "
                              "`orelse` or `catch`",
                          (int)ty_name(c->a, it->elem).len, ty_name(c->a, it->elem).ptr);
            }
            t = it->elem;
            break;
        }

        case EX_ORELSE: {
            Type *vt = chk(c, e->orelse_expr.value, NULL);
            if (ty_is_error(vt)) {
                chk(c, e->orelse_expr.fallback, NULL);
                t = vt;
                break;
            }
            Type *inner = (vt->kind == TY_ERRUNION || vt->kind == TY_OPTION) ? vt->elem : NULL;
            if (!inner) {
                Diag *dg = diag_error(c->d, 303, e->span,
                                      "`orelse` needs `T?` or `!T`, found `%.*s`",
                                      (int)ty_name(c->a, vt).len, ty_name(c->a, vt).ptr);
                diag_help(dg, "`orelse` supplies a value when one is absent; this "
                              "expression always has one");
                chk(c, e->orelse_expr.fallback, NULL);
                t = chk_err(c);
                break;
            }
            Type *ft = chk(c, e->orelse_expr.fallback, inner);
            chk_expect_type(c, e->orelse_expr.fallback->span, inner, ft, "as the fallback");
            t = inner;
            break;
        }

        case EX_CATCH: {
            Type *vt = chk(c, e->catch_expr.value, NULL);
            Type *inner = chk_err(c);
            if (vt && vt->kind == TY_ERRUNION) inner = vt->elem;
            else if (!ty_is_error(vt))
                diag_error(c->d, 303, e->span,
                           "`catch` needs an error union, found `%.*s`",
                           (int)ty_name(c->a, vt).len, ty_name(c->a, vt).ptr);
            chk_push_scope(c);
            if (!str_empty(e->catch_expr.binding))
                chk_declare(c, e->catch_expr.binding, ty_int(c->tc, 32, true), false, false,
                            CONV_LET, e->span);
            chk(c, e->catch_expr.handler, NULL);
            chk_pop_scope(c);
            t = inner;
            break;
        }

        case EX_ERROR_LIT:
            t = (expected && expected->kind == TY_ERRUNION)
                    ? expected
                    : ty_errunion(c->tc, ty_prim(c->tc, TY_VOID));
            break;

        case EX_UNSAFE:
            chk(c, e->unsafe_expr.body, NULL);
            t = ty_prim(c->tc, TY_VOID);
            break;

        case EX_RANGE: {
            Type *lo = chk(c, e->range.lo, ty_int(c->tc, 32, true));
            Type *hi = chk(c, e->range.hi, lo);
            chk_expect_type(c, e->range.hi->span, lo, hi, "as the end of a range");
            t = lo;
            break;
        }

        default: t = chk_err(c); break;
    }

    if (t) e->type = t;
    return t ? t : ty_prim(c->tc, TY_VOID);
}
