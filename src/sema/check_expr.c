/* check_expr.c — expression type checking. */
#include "check.h"

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

static Type *chk_int_lit(C *c, Expr *e, Type *expected) {
    Type *t = suffix_type(c, e->int_lit.suffix);
    if (!t) {
        /* An integer literal is polymorphic until context fixes it. Adopting a
         * float type is not a conversion — there is no runtime value yet. */
        if (expected && ty_is_numeric(expected)) t = expected;
        else t = ty_int(c->tc, 32, true);
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

    Item *it = prog_short(c->p, name);
    if (it) {
        if (it->kind == IT_CONST) {
            e->res      = it;
            e->res_kind = RES_CONST;
            if (!it->rtype && it->konst.value) it->rtype = chk(c, it->konst.value, NULL);
            return it->rtype ? it->rtype : chk_err(c);
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

    Type *want = (is_arith(op) && expected && ty_is_numeric(expected)) ? expected : NULL;
    Type *lt   = chk(c, e->binary.lhs, want);
    Type *rt   = chk(c, e->binary.rhs, lt);

    if (ty_is_error(lt) || ty_is_error(rt)) return chk_err(c);

    if (!ty_eq(lt, rt)) {
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
        bool vecish = lt->kind == TY_VEC2 || lt->kind == TY_VEC3 || lt->kind == TY_VEC4;
        if (!ty_is_numeric(lt) && !vecish) {
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
    Type *t = chk(c, e->unary.operand, expected);
    if (ty_is_error(t)) return t;
    if (op == TK_MINUS && !ty_is_numeric(t) && t->kind != TY_VEC2 && t->kind != TY_VEC3 &&
        t->kind != TY_VEC4) {
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

/* Checks the arguments of a call against a function item. */
static Type *chk_call_item(C *c, Expr *e, Item *fn, bool has_self) {
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

static Type *chk_call(C *c, Expr *e) {
    Expr *callee = e->call.callee;

    if (callee->kind == EX_PATH) {
        Str   name = callee->path.segs.data[0];
        Local *l   = chk_lookup(c, name);
        if (!l) {
            Item *fn = prog_short(c->p, name);
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

        if (base->kind == EX_PATH && !chk_lookup(c, base->path.segs.data[0])) {
            SB sb;
            sb_init(&sb, c->a);
            sb_str(&sb, base->path.segs.data[0]);
            sb_char(&sb, '.');
            sb_str(&sb, callee->field.name);
            Item *fn = prog_item(c->p, sb_finish(&sb));
            if (!fn) fn = prog_short(c->p, callee->field.name);
            if (fn && fn->kind == IT_FN && str_empty(fn->fn.recv)) {
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

        Str   tname = (bt->kind == TY_STRUCT || bt->kind == TY_ENUM) ? bt->name
                                                                    : ty_name(c->a, bt);
        Item *m     = prog_method(c->p, tname, callee->field.name);
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
        e->res      = m;
        e->res_kind = RES_FN;
        return chk_call_item(c, e, m, true);
    }

    diag_error(c->d, 307, e->span, "this expression is not callable");
    return chk_err(c);
}

static Type *chk_struct_lit(C *c, Expr *e) {
    Type *t = resolve_type_expr(c->p, c->d, e->struct_lit.type);
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
    if (bt->kind == TY_ARRAY || bt->kind == TY_LIST || bt->kind == TY_POOL) {
        Type *it = chk(c, e->index.index, ty_int(c->tc, 32, true));
        if (!ty_is_integer(it) && !ty_is_error(it))
            diag_error(c->d, 303, e->index.index->span,
                       "an index must be an integer, found `%.*s`",
                       (int)ty_name(c->a, it).len, ty_name(c->a, it).ptr);
        return bt->elem;
    }
    diag_error(c->d, 313, e->span, "`%.*s` cannot be indexed",
               (int)ty_name(c->a, bt).len, ty_name(c->a, bt).ptr);
    chk(c, e->index.index, NULL);
    return chk_err(c);
}

static Type *chk_cast(C *c, Expr *e) {
    Type *from = chk(c, e->cast.value, NULL);
    Type *to   = resolve_type_expr(c->p, c->d, e->cast.type);
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
            Type *bt = chk(c, e->field.base, NULL);
            if (ty_is_error(bt)) {
                t = chk_err(c);
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
            Type *inner = (vt && vt->kind == TY_ERRUNION) ? vt->elem : vt;
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
