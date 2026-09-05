/* enforce_expr.c — EnforceScript expressions and statements.
 *
 * The interesting part is value semantics. Beryl structs are values;
 * EnforceScript classes are references. A copy is therefore inserted exactly
 * where the language requires one — binding, assigning, or returning a place
 * expression of struct type — and nowhere else, because a call that merely
 * borrows needs no copy at all.
 */
#include "enforce_int.h"

static const char *bin_op(TokKind k) {
    switch (k) {
        case TK_PLUS: return "+";
        case TK_MINUS: return "-";
        case TK_STAR: return "*";
        case TK_SLASH: return "/";
        case TK_PERCENT: return "%";
        case TK_EQ: return "==";
        case TK_NE: return "!=";
        case TK_LT: return "<";
        case TK_LE: return "<=";
        case TK_GT: return ">";
        case TK_GE: return ">=";
        case TK_ANDAND: return "&&";
        case TK_OROR: return "||";
        case TK_AMP: return "&";
        case TK_PIPE: return "|";
        case TK_CARET: return "^";
        case TK_SHL: return "<<";
        case TK_SHR: return ">>";
        default: return "+";
    }
}

/* Wraps a place expression in `.Clone()` when value semantics demand a copy. */
static Str copy_if_needed(E *e, Expr *x, Str rendered) {
    if (!x || !ef_is_place(x)) return rendered;
    if (!x->type || x->type->kind != TY_STRUCT) return rendered;
    SB sb;
    sb_init(&sb, e->a);
    sb_fmt(&sb, "%.*s.BerylCopy()", S(rendered));
    return sb_finish(&sb);
}

static Str call_target(E *e, Expr *x, Item *fn) {
    SB sb;
    sb_init(&sb, e->a);
    Expr *callee = x->call.callee;
    bool  has_self = fn->fn.params.len > 0 && fn->fn.params.data[0].is_self;

    if (has_self && callee && callee->kind == EX_FIELD) {
        Expr *recv = callee->field.base;
        if (recv->kind == EX_SELF) {
            /* Calling another method on the same instance. */
            sb_str(&sb, ef_method_name(fn->name));
            return sb_finish(&sb);
        }
        sb_fmt(&sb, "%.*s.%.*s", S(ef_expr(e, recv)), S(ef_method_name(fn->name)));
        return sb_finish(&sb);
    }

    /* A free function lives on its module's holder class. */
    Module *mod = (Module *)fn->owner;
    SB      hb;
    sb_init(&hb, e->a);
    for (uint32_t i = 0; mod && i < mod->path.len; i++) {
        Str seg = mod->path.data[i];
        if (!seg.len) continue;
        char c0 = seg.ptr[0];
        sb_char(&hb, (c0 >= 'a' && c0 <= 'z') ? (char)(c0 - 'a' + 'A') : c0);
        sb_str(&hb, str_slice(seg, 1, seg.len - 1));
    }
    sb_fmt(&sb, "%.*s.%.*s", S(ef_prefixed(e, sb_finish(&hb))),
           S(ef_method_name(fn->name)));
    return sb_finish(&sb);
}

/* Renders the argument list, honouring conventions. `out` arguments pass the
 * storage itself; borrowed arguments pass the reference with no copy. */
static Str call_args(E *e, Expr *x, Item *fn, Str extra_out) {
    SB sb;
    sb_init(&sb, e->a);
    bool has_self = fn->fn.params.len > 0 && fn->fn.params.data[0].is_self;
    bool first    = true;

    for (uint32_t i = 0; i < x->call.args.len; i++) {
        uint32_t slot = i + (has_self ? 1 : 0);
        (void)slot;
        if (!first) sb_cstr(&sb, ", ");
        first = false;
        sb_str(&sb, ef_expr(e, x->call.args.data[i].value));
    }
    if (!str_empty(extra_out)) {
        if (!first) sb_cstr(&sb, ", ");
        sb_str(&sb, extra_out);
    }
    return sb_finish(&sb);
}

/* `List<T>` is the engine's own `array<T>` on this target, so its methods are
 * the engine's methods. Nothing is reimplemented. */
static Str gen_list_method(E *e, Expr *x) {
    Expr  *recv = x->call.callee->field.base;
    Str    r    = ef_expr(e, recv);
    ArgVec args = x->call.args;

    SB sb;
    sb_init(&sb, e->a);
    switch ((Intrinsic)x->intrinsic) {
        case INTR_LIST_LEN: sb_fmt(&sb, "%.*s.Count()", S(r)); break;
        case INTR_LIST_GET:
            sb_fmt(&sb, "%.*s.Get(%.*s)", S(r), S(ef_expr(e, args.data[0].value)));
            break;
        case INTR_LIST_PUSH:
            ef_line(e, "%.*s.Insert(%.*s);", S(r), S(ef_expr(e, args.data[0].value)));
            sb_cstr(&sb, "0");
            break;
        case INTR_LIST_SET:
            ef_line(e, "%.*s.Set(%.*s, %.*s);", S(r), S(ef_expr(e, args.data[0].value)),
                    S(ef_expr(e, args.data[1].value)));
            sb_cstr(&sb, "0");
            break;
        default: /* INTR_LIST_CLEAR */
            ef_line(e, "%.*s.Clear();", S(r));
            sb_cstr(&sb, "0");
            break;
    }
    return sb_finish(&sb);
}

/* Vector methods and construction.
 *
 * Every spelling here is taken from EnforceScript that already compiles in
 * Workbench, which is why `Dot` and `Distance` are static calls on `vector`
 * while `Length` and `Normalized` are instance methods — the engine is not
 * consistent about it and guessing would cost a Workbench round trip each.
 */
static Str gen_vec(E *e, Expr *x) {
    SB sb;
    sb_init(&sb, e->a);
    ArgVec args = x->call.args;

    if (intrinsic_is_vec_new((Intrinsic)x->intrinsic)) {
        /* `vector` is three floats, so a Vec2 or Vec4 never reaches here —
         * the enfusion profile lint rejects them at BE0701. */
        sb_cstr(&sb, "Vector(");
        for (uint32_t i = 0; i < args.len; i++) {
            if (i) sb_cstr(&sb, ", ");
            sb_fmt(&sb, "%.*s", S(ef_expr(e, args.data[i].value)));
        }
        sb_char(&sb, ')');
        return sb_finish(&sb);
    }

    Str recv = ef_expr(e, x->call.callee->field.base);

    switch ((Intrinsic)x->intrinsic) {
        case INTR_VEC_LENGTH: sb_fmt(&sb, "%.*s.Length()", S(recv)); break;
        case INTR_VEC_LENGTH_SQ: sb_fmt(&sb, "%.*s.LengthSq()", S(recv)); break;
        case INTR_VEC_NORMALIZED: sb_fmt(&sb, "%.*s.Normalized()", S(recv)); break;
        case INTR_VEC_DOT:
            sb_fmt(&sb, "vector.Dot(%.*s, %.*s)", S(recv),
                   S(ef_expr(e, args.data[0].value)));
            break;
        case INTR_VEC_DISTANCE:
            sb_fmt(&sb, "vector.Distance(%.*s, %.*s)", S(recv),
                   S(ef_expr(e, args.data[0].value)));
            break;
        default: { /* INTR_VEC_CROSS */
            /* Spelled out rather than called, because no cross product could
             * be confirmed on the engine's `vector` and the formula needs
             * only indexing and arithmetic, both of which are confirmed.
             * The temporaries keep each operand evaluated exactly once. */
            Str a = ef_tmp(e), b = ef_tmp(e);
            ef_line(e, "vector %.*s = %.*s;", S(a), S(recv));
            ef_line(e, "vector %.*s = %.*s;", S(b), S(ef_expr(e, args.data[0].value)));
            sb_fmt(&sb,
                   "Vector(%.*s[1] * %.*s[2] - %.*s[2] * %.*s[1], "
                   "%.*s[2] * %.*s[0] - %.*s[0] * %.*s[2], "
                   "%.*s[0] * %.*s[1] - %.*s[1] * %.*s[0])",
                   S(a), S(b), S(a), S(b), S(a), S(b), S(a), S(b), S(a), S(b), S(a), S(b));
            break;
        }
    }
    return sb_finish(&sb);
}

static Str gen_intrinsic(E *e, Expr *x) {
    if (intrinsic_is_list_method((Intrinsic)x->intrinsic)) return gen_list_method(e, x);
    if (intrinsic_is_vec_method((Intrinsic)x->intrinsic) ||
        intrinsic_is_vec_new((Intrinsic)x->intrinsic))
        return gen_vec(e, x);

    SB sb;
    sb_init(&sb, e->a);
    ArgVec args = x->call.args;

    switch ((Intrinsic)x->intrinsic) {
        case INTR_PRINT:
        case INTR_PRINTLN:
            /* The engine's Print always ends the line, so both map to it. */
            for (uint32_t i = 0; i < args.len; i++)
                ef_line(e, "Print(%.*s);", S(ef_expr(e, args.data[i].value)));
            if (args.len == 0) ef_line(e, "Print(\"\");");
            sb_cstr(&sb, "0");
            return sb_finish(&sb);

        case INTR_ASSERT:
            ef_line(e, "if (!(%.*s))", S(ef_expr(e, args.data[0].value)));
            ef_line(e, "\tPrint(\"beryl: assertion failed\");");
            sb_cstr(&sb, "0");
            return sb_finish(&sb);

        case INTR_MIN:
            sb_fmt(&sb, "Math.Min(%.*s, %.*s)", S(ef_expr(e, args.data[0].value)),
                   S(ef_expr(e, args.data[1].value)));
            return sb_finish(&sb);
        case INTR_MAX:
            sb_fmt(&sb, "Math.Max(%.*s, %.*s)", S(ef_expr(e, args.data[0].value)),
                   S(ef_expr(e, args.data[1].value)));
            return sb_finish(&sb);
        case INTR_CLAMP:
            sb_fmt(&sb, "Math.Clamp(%.*s, %.*s, %.*s)", S(ef_expr(e, args.data[0].value)),
                   S(ef_expr(e, args.data[1].value)), S(ef_expr(e, args.data[2].value)));
            return sb_finish(&sb);
        case INTR_ABS: {
            Type *t = x->type;
            sb_fmt(&sb, "Math.%s(%.*s)",
                   (t && t->kind == TY_FLOAT) ? "AbsFloat" : "AbsInt",
                   S(ef_expr(e, args.data[0].value)));
            return sb_finish(&sb);
        }
        case INTR_SQRT:
            sb_fmt(&sb, "Math.Sqrt(%.*s)", S(ef_expr(e, args.data[0].value)));
            return sb_finish(&sb);

        /* EnforceScript's `int` already wraps, so the opt-outs are plain
         * operators here. They still carry meaning in the source: they say the
         * author considered overflow and chose this. */
        case INTR_WRAPPING_ADD:
            sb_fmt(&sb, "(%.*s + %.*s)", S(ef_expr(e, args.data[0].value)),
                   S(ef_expr(e, args.data[1].value)));
            return sb_finish(&sb);
        case INTR_WRAPPING_SUB:
            sb_fmt(&sb, "(%.*s - %.*s)", S(ef_expr(e, args.data[0].value)),
                   S(ef_expr(e, args.data[1].value)));
            return sb_finish(&sb);
        case INTR_WRAPPING_MUL:
            sb_fmt(&sb, "(%.*s * %.*s)", S(ef_expr(e, args.data[0].value)),
                   S(ef_expr(e, args.data[1].value)));
            return sb_finish(&sb);
        case INTR_SATURATING_ADD:
        case INTR_SATURATING_SUB: {
            /* No engine equivalent, so it is spelled out with a clamp. */
            Str a  = ef_expr(e, args.data[0].value);
            Str b  = ef_expr(e, args.data[1].value);
            Str op = str_from((Intrinsic)x->intrinsic == INTR_SATURATING_ADD ? "+" : "-");
            sb_fmt(&sb, "Math.Clamp(%.*s %.*s %.*s, -2147483648, 2147483647)", S(a), S(op),
                   S(b));
            return sb_finish(&sb);
        }
        default: sb_cstr(&sb, "0"); return sb_finish(&sb);
    }
}

static Str ef_expr_gen(E *e, Expr *x);

Str ef_ptr_key(Arena *a, const void *p) {
    char *b = ARENA_ARRAY(a, char, sizeof p);
    for (size_t i = 0; i < sizeof p; i++) b[i] = (char)(((uintptr_t)p >> (i * 8)) & 0xff);
    return (Str){b, (uint32_t)sizeof p};
}

/* Renders one expression, emitting any statements it needs first.
 *
 * Memoized on the node, because `S` (enforce_int.h) expands its argument
 * twice and nearly every call site passes `ef_expr(...)` straight into it.
 * Without the memo a nested `try f()` emitted the call four times instead of
 * once, and a struct literal emitted `new` eight times — the values used were
 * right, so nothing failed loudly; the extra calls simply happened. */
Str ef_expr(E *e, Expr *x) {
    if (x) {
        Str  key = ef_ptr_key(e->a, x);
        Str *hit = (Str *)map_get(e->memo, key);
        if (hit) return *hit;
        Str  r   = ef_expr_gen(e, x);
        Str *box = ARENA_NEW(e->a, Str);
        *box     = r;
        map_put(e->memo, key, box);
        return r;
    }
    return ef_expr_gen(e, x);
}

static Str ef_expr_gen(E *e, Expr *x) {
    SB sb;
    sb_init(&sb, e->a);
    if (!x) {
        sb_cstr(&sb, "0");
        return sb_finish(&sb);
    }

    switch (x->kind) {
        case EX_INT: sb_fmt(&sb, "%llu", (unsigned long long)x->int_lit.val); break;
        case EX_FLOAT: sb_fmt(&sb, "%g", x->float_lit.val); break;
        case EX_BOOL: sb_cstr(&sb, x->bool_lit ? "true" : "false"); break;
        case EX_CHAR: sb_fmt(&sb, "%u", x->char_lit); break;

        case EX_STR: {
            sb_char(&sb, '"');
            for (uint32_t i = 0; i < x->str_lit.len; i++) {
                char c = x->str_lit.ptr[i];
                if (c == '"') sb_cstr(&sb, "\\\"");
                else if (c == '\\') sb_cstr(&sb, "\\\\");
                else if (c == '\n') sb_cstr(&sb, "\\n");
                else if (c == '\t') sb_cstr(&sb, "\\t");
                else sb_char(&sb, c);
            }
            sb_char(&sb, '"');
            break;
        }

        case EX_SELF: sb_cstr(&sb, "this"); break;

        case EX_PATH:
            if (x->res_kind == RES_LOCAL) {
                sb_str(&sb, ef_ident(e, ((Local *)x->res)->name));
            } else if (x->res_kind == RES_CONST) {
                /* Constants are folded to a literal. EnforceScript has no
                 * module-level constant to bind the name to, and folding is
                 * always correct where a constant is legal at all. */
                Item *it = (Item *)x->res;
                ConstVal v = it && it->konst.value
                                 ? const_eval(e->a, e->d, e->p, it->konst.value, false)
                                 : (ConstVal){0};
                switch (v.kind) {
                    case CV_INT: sb_fmt(&sb, "%lld", (long long)v.i); break;
                    case CV_FLOAT: sb_fmt(&sb, "%g", v.f); break;
                    case CV_BOOL: sb_cstr(&sb, v.b ? "true" : "false"); break;
                    case CV_STR: sb_fmt(&sb, "\"%.*s\"", S(v.s)); break;
                    default: sb_cstr(&sb, "0"); break;
                }
            } else if (x->path.segs.len) {
                sb_str(&sb, x->path.segs.data[0]);
            } else {
                sb_cstr(&sb, "0");
            }
            break;

        case EX_FIELD:
            /* `v.x` on a vector. EnforceScript's `vector` has no named
             * components, only indices — which is why Beryl checks the name
             * against the arity before it gets here. */
            if (x->res_kind == RES_VEC_COMP) {
                sb_fmt(&sb, "%.*s[%u]", S(ef_expr(e, x->field.base)), x->intrinsic);
                break;
            }
            /* Inside a method, `self.kp` is just `kp`, matching how the base
             * game's own classes are written. */
            if (x->field.base && x->field.base->kind == EX_SELF) sb_str(&sb, ef_ident(e, x->field.name));
            else sb_fmt(&sb, "%.*s.%.*s", S(ef_expr(e, x->field.base)), S(ef_ident(e, x->field.name)));
            break;

        case EX_INDEX:
            sb_fmt(&sb, "%.*s[%.*s]", S(ef_expr(e, x->index.base)),
                   S(ef_expr(e, x->index.index)));
            break;

        case EX_UNARY: {
            const char *op = x->unary.op == TK_BANG   ? "!"
                             : x->unary.op == TK_TILDE ? "~"
                                                       : "-";
            sb_fmt(&sb, "%s%.*s", op, S(ef_expr(e, x->unary.operand)));
            break;
        }

        case EX_BINARY: {
            Type *lt = x->binary.lhs->type;
            Type *rt = x->binary.rhs->type;

            /* `2.0 * v` is written `v * 2.0` on the way out. Scaling is
             * commutative, and only the vector-on-the-left form is confirmed
             * against the engine. */
            if (x->binary.op == TK_STAR && !ty_is_vec(lt) && ty_is_vec(rt)) {
                sb_fmt(&sb, "(%.*s * %.*s)", S(ef_expr(e, x->binary.rhs)),
                       S(ef_expr(e, x->binary.lhs)));
                break;
            }

            /* Component-wise vector division. The engine has no `/` taking
             * two vectors — Workbench rejects it with "Unknown operator '/'"
             * — but it does have `/` by a float, so only this form needs
             * spelling out. Doing that rather than profile-gating it keeps
             * the operator meaning the same on both targets. */
            if (x->binary.op == TK_SLASH && ty_is_vec(lt) && ty_is_vec(rt)) {
                Str a = ef_tmp(e), b = ef_tmp(e);
                ef_line(e, "vector %.*s = %.*s;", S(a), S(ef_expr(e, x->binary.lhs)));
                ef_line(e, "vector %.*s = %.*s;", S(b), S(ef_expr(e, x->binary.rhs)));
                sb_fmt(&sb, "Vector(%.*s[0] / %.*s[0], %.*s[1] / %.*s[1], %.*s[2] / %.*s[2])",
                       S(a), S(b), S(a), S(b), S(a), S(b));
                break;
            }

            /* Vector equality is spelled out component-wise. `==` on the
             * engine's `vector` could not be confirmed, and this is exactly
             * what the native back end computes, so the two agree by
             * construction rather than by assumption. */
            if ((x->binary.op == TK_EQ || x->binary.op == TK_NE) && ty_is_vec(lt)) {
                Str a = ef_tmp(e), b = ef_tmp(e);
                ef_line(e, "vector %.*s = %.*s;", S(a), S(ef_expr(e, x->binary.lhs)));
                ef_line(e, "vector %.*s = %.*s;", S(b), S(ef_expr(e, x->binary.rhs)));
                const char *cmp = x->binary.op == TK_EQ ? "==" : "!=";
                const char *join = x->binary.op == TK_EQ ? " && " : " || ";
                sb_char(&sb, '(');
                for (uint32_t i = 0; i < ty_vec_arity(lt); i++) {
                    if (i) sb_cstr(&sb, join);
                    sb_fmt(&sb, "%.*s[%u] %s %.*s[%u]", S(a), i, cmp, S(b), i);
                }
                sb_char(&sb, ')');
                break;
            }

            sb_fmt(&sb, "(%.*s %s %.*s)", S(ef_expr(e, x->binary.lhs)),
                   bin_op(x->binary.op), S(ef_expr(e, x->binary.rhs)));
            break;
        }

        case EX_CAST: {
            Type *t = x->type;
            if (t && t->kind == TY_INT) sb_fmt(&sb, "(int)%.*s", S(ef_expr(e, x->cast.value)));
            else if (t && t->kind == TY_FLOAT)
                sb_fmt(&sb, "(float)%.*s", S(ef_expr(e, x->cast.value)));
            else sb_str(&sb, ef_expr(e, x->cast.value));
            break;
        }

        case EX_CALL: {
            if (x->res_kind == RES_INTRINSIC) return gen_intrinsic(e, x);
            Item *fn = (x->res_kind == RES_FN) ? (Item *)x->res : NULL;
            if (!fn) {
                sb_cstr(&sb, "0");
                break;
            }
            bool err = fn->rtype && fn->rtype->kind == TY_ERRUNION;
            if (!err) {
                sb_fmt(&sb, "%.*s(%.*s)", S(call_target(e, x, fn)),
                       S(call_args(e, x, fn, STR_EMPTY)));
                break;
            }
            /* An error-returning call needs somewhere to put its value. */
            Str out = STR_EMPTY;
            if (fn->rtype->elem && fn->rtype->elem->kind != TY_VOID) {
                out = ef_tmp(e);
                ef_line(e, "%.*s %.*s;", S(ef_type(e, fn->rtype->elem)), S(out));
            }
            Str okv = ef_tmp(e);
            ef_line(e, "bool %.*s = %.*s(%.*s);", S(okv), S(call_target(e, x, fn)),
                    S(call_args(e, x, fn, out)));
            sb_str(&sb, okv); /* the caller inspects the bool */
            break;
        }

        case EX_STRUCT_LIT: {
            Type *t    = x->type;
            Item *decl = t ? t->decl : NULL;
            Str   cls  = ef_type(e, t);
            Str   tmp  = ef_tmp(e);
            ef_line(e, "%.*s %.*s = new %.*s();", S(cls), S(tmp), S(cls));
            for (uint32_t i = 0; decl && i < decl->strukt.fields.len; i++) {
                Field *fl  = &decl->strukt.fields.data[i];
                Expr  *val = NULL;
                for (uint32_t k = 0; k < x->struct_lit.fields.len; k++)
                    if (str_eq(x->struct_lit.fields.data[k].name, fl->name))
                        val = x->struct_lit.fields.data[k].value;
                if (!val) continue; /* the constructor already applied the default */
                ef_line(e, "%.*s.%.*s = %.*s;", S(tmp), S(ef_ident(e, fl->name)),
                        S(copy_if_needed(e, val, ef_expr(e, val))));
            }
            sb_str(&sb, tmp);
            break;
        }

        case EX_ARRAY_LIT: {
            Str cls = ef_type(e, x->type);
            Str tmp = ef_tmp(e);
            ef_line(e, "%.*s %.*s = new %.*s();", S(cls), S(tmp), S(cls));
            for (uint32_t i = 0; i < x->array_lit.elems.len; i++)
                ef_line(e, "%.*s.Insert(%.*s);", S(tmp),
                        S(ef_expr(e, x->array_lit.elems.data[i])));
            sb_str(&sb, tmp);
            break;
        }

        case EX_TRY: {
            Expr *inner = x->try_expr.inner;
            Item *fn    = (inner->res_kind == RES_FN) ? (Item *)inner->res : NULL;
            if (!fn) {
                sb_cstr(&sb, "0");
                break;
            }
            Str out = STR_EMPTY;
            if (fn->rtype && fn->rtype->elem && fn->rtype->elem->kind != TY_VOID) {
                out = ef_tmp(e);
                ef_line(e, "%.*s %.*s;", S(ef_type(e, fn->rtype->elem)), S(out));
            }
            ef_line(e, "if (!%.*s(%.*s))", S(call_target(e, inner, fn)),
                    S(call_args(e, inner, fn, out)));
            ef_line(e, "\treturn false;");
            if (str_empty(out)) sb_cstr(&sb, "0");
            else sb_str(&sb, out);
            break;
        }

        case EX_ORELSE: {
            Expr *val = x->orelse_expr.value;
            Item *fn  = (val->res_kind == RES_FN) ? (Item *)val->res : NULL;
            Str   res = ef_tmp(e);
            ef_line(e, "%.*s %.*s;", S(ef_type(e, x->type)), S(res));
            if (fn && fn->rtype && fn->rtype->kind == TY_ERRUNION) {
                ef_line(e, "if (!%.*s(%.*s))", S(call_target(e, val, fn)),
                        S(call_args(e, val, fn, res)));
                e->indent++;
                ef_line(e, "%.*s = %.*s;", S(res), S(ef_expr(e, x->orelse_expr.fallback)));
                e->indent--;
            } else {
                ef_line(e, "%.*s = %.*s;", S(res), S(ef_expr(e, val)));
            }
            sb_str(&sb, res);
            break;
        }

        case EX_CATCH: {
            Expr *val = x->catch_expr.value;
            Item *fn  = (val->res_kind == RES_FN) ? (Item *)val->res : NULL;
            Str   res = ef_tmp(e);
            ef_line(e, "%.*s %.*s;", S(ef_type(e, x->type)), S(res));
            if (fn && fn->rtype && fn->rtype->kind == TY_ERRUNION) {
                ef_line(e, "if (!%.*s(%.*s))", S(call_target(e, val, fn)),
                        S(call_args(e, val, fn, res)));
                ef_line(e, "{");
                e->indent++;
                if (x->catch_expr.handler && x->catch_expr.handler->kind == EX_BLOCK)
                    ef_block(e, x->catch_expr.handler);
                else ef_expr(e, x->catch_expr.handler);
                e->indent--;
                ef_line(e, "}");
            }
            sb_str(&sb, res);
            break;
        }

        case EX_ERROR_LIT: sb_cstr(&sb, "false"); break;

        case EX_IF:
            ef_line(e, "if (%.*s)", S(ef_expr(e, x->if_expr.cond)));
            ef_line(e, "{");
            e->indent++;
            ef_block(e, x->if_expr.then_blk);
            e->indent--;
            ef_line(e, "}");
            if (x->if_expr.else_blk) {
                ef_line(e, "else");
                if (x->if_expr.else_blk->kind == EX_IF) {
                    e->indent++;
                    ef_expr(e, x->if_expr.else_blk);
                    e->indent--;
                } else {
                    ef_line(e, "{");
                    e->indent++;
                    ef_block(e, x->if_expr.else_blk);
                    e->indent--;
                    ef_line(e, "}");
                }
            }
            sb_cstr(&sb, "0");
            break;

        case EX_BLOCK:
            ef_block(e, x);
            sb_cstr(&sb, "0");
            break;

        case EX_RANGE: sb_str(&sb, ef_expr(e, x->range.lo)); break;

        default: sb_cstr(&sb, "0"); break;
    }
    return sb_finish(&sb);
}

/* ---- statements -------------------------------------------------------- */

static const char *assign_op_str(TokKind k) {
    switch (k) {
        case TK_PLUSEQ: return "+=";
        case TK_MINUSEQ: return "-=";
        case TK_STAREQ: return "*=";
        case TK_SLASHEQ: return "/=";
        case TK_PERCENTEQ: return "%=";
        default: return "=";
    }
}

void ef_stmt(E *e, Stmt *s) {
    if (!s) return;

    switch (s->kind) {
        case ST_LET: {
            Type *t = s->let.init ? s->let.init->type : NULL;
            if (!t) {
                for (uint32_t i = 0; e->fn && i < e->fn->nlocals; i++) {
                    Local *l = ((Local **)e->fn->locals)[i];
                    if (l->span.offset == s->span.offset && str_eq(l->name, s->let.name)) {
                        t = l->type;
                        break;
                    }
                }
            }
            if (s->let.init) {
                Str v = copy_if_needed(e, s->let.init, ef_expr(e, s->let.init));
                ef_line(e, "%.*s %.*s = %.*s;", S(ef_type(e, t)), S(ef_ident(e, s->let.name)), S(v));
            } else if (t && (t->kind == TY_LIST || t->kind == TY_MAP)) {
                /* A container starts empty; a null ref would not be usable. */
                ef_line(e, "%.*s %.*s = new %.*s();", S(ef_type(e, t)),
                        S(ef_ident(e, s->let.name)), S(ef_type(e, t)));
            } else {
                ef_line(e, "%.*s %.*s;", S(ef_type(e, t)), S(ef_ident(e, s->let.name)));
            }
            break;
        }

        case ST_EXPR: {
            Str v = ef_expr(e, s->expr);
            /* A call emitted for its value leaves a bare temporary behind;
             * only a real call expression needs a statement of its own. */
            if (s->expr && s->expr->kind == EX_CALL && s->expr->res_kind == RES_FN) {
                Item *fn = (Item *)s->expr->res;
                if (!(fn->rtype && fn->rtype->kind == TY_ERRUNION))
                    ef_line(e, "%.*s;", S(v));
            }
            break;
        }

        case ST_ASSIGN: {
            Str rv = copy_if_needed(e, s->assign.value, ef_expr(e, s->assign.value));
            Str lv = ef_expr(e, s->assign.target);
            ef_line(e, "%.*s %s %.*s;", S(lv), assign_op_str(s->assign.op), S(rv));
            break;
        }

        case ST_WHILE: {
            /* The condition is re-evaluated at the top of the body so that a
             * condition needing temporaries still works. */
            ef_line(e, "while (true)");
            ef_line(e, "{");
            e->indent++;
            Str c = ef_expr(e, s->while_st.cond);
            ef_line(e, "if (!(%.*s))", S(c));
            ef_line(e, "\tbreak;");
            ef_block(e, s->while_st.body);
            e->indent--;
            ef_line(e, "}");
            break;
        }

        case ST_FOR: {
            Expr *it = s->for_st.iter;
            if (it && it->kind == EX_RANGE) {
                Str lo = ef_expr(e, it->range.lo);
                Str hi = ef_expr(e, it->range.hi);
                Str lv = ef_ident(e, s->for_st.var);
                ef_line(e, "for (int %.*s = %.*s; %.*s < %.*s; %.*s++)", S(lv), S(lo),
                        S(lv), S(hi), S(lv));
            } else {
                Type *et = (it && it->type) ? it->type->elem : NULL;
                ef_line(e, "foreach (%.*s %.*s : %.*s)", S(ef_type(e, et)),
                        S(ef_ident(e, s->for_st.var)), S(ef_expr(e, it)));
            }
            ef_line(e, "{");
            e->indent++;
            ef_block(e, s->for_st.body);
            e->indent--;
            ef_line(e, "}");
            break;
        }

        case ST_RETURN: {
            if (!s->expr) {
                ef_line(e, e->fn_is_err ? "return true;" : "return;");
                break;
            }
            if (s->expr->kind == EX_ERROR_LIT) {
                ef_line(e, "return false;");
                break;
            }
            Str v = copy_if_needed(e, s->expr, ef_expr(e, s->expr));
            if (e->fn_is_err) {
                Type *ok = e->fn->rtype ? e->fn->rtype->elem : NULL;
                if (ok && ok->kind != TY_VOID) ef_line(e, "result = %.*s;", S(v));
                ef_line(e, "return true;");
            } else {
                ef_line(e, "return %.*s;", S(v));
            }
            break;
        }

        case ST_BREAK: ef_line(e, "break;"); break;
        case ST_CONTINUE: ef_line(e, "continue;"); break;
        case ST_DEFER: ef_expr(e, s->expr); break;
        default: break;
    }
}

void ef_block(E *e, Expr *b) {
    if (!b || b->kind != EX_BLOCK) return;
    for (uint32_t i = 0; i < b->block.stmts.len; i++) ef_stmt(e, b->block.stmts.data[i]);
}
