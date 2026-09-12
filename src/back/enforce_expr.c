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

/* Only introduce sequencing locals where an expression can perform work.
 * Pure arithmetic keeps the readable source shape. */
static bool needs_sequence(Expr *x) {
    if (!x) return false;
    switch (x->kind) {
        case EX_CALL: case EX_TRY: case EX_CATCH: case EX_ORELSE:
        case EX_STRUCT_LIT: case EX_ARRAY_LIT: case EX_BLOCK: return true;
        case EX_BINARY: return needs_sequence(x->binary.lhs) || needs_sequence(x->binary.rhs);
        case EX_UNARY: return needs_sequence(x->unary.operand);
        case EX_FIELD: return needs_sequence(x->field.base);
        case EX_INDEX: return needs_sequence(x->index.base) || needs_sequence(x->index.index);
        case EX_CAST: return needs_sequence(x->cast.value);
        default: return false;
    }
}

static Str hold(E *e, Expr *x) {
    Str value = ef_expr(e, x);
    Str tmp = ef_tmp(e);
    EfOrigin previous_origin = e->origin;
    e->origin = ef_expression_origin(e, x);
    ef_line(e, "%.*s %.*s = %.*s;", S(ef_type(e, x->type)), S(tmp), S(value));
    e->origin = previous_origin;
    return tmp;
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
            sb_str(&sb, ef_fn_name(e, fn));
            return sb_finish(&sb);
        }
        Str receiver = needs_sequence(recv) ? hold(e, recv) : ef_expr(e, recv);
        sb_fmt(&sb, "%.*s.%.*s", S(receiver), S(ef_fn_name(e, fn)));
        return sb_finish(&sb);
    }

    /* A receiver declaration without self is a static member of that type. */
    if (fn->fn.recv_decl) {
        sb_fmt(&sb, "%.*s.%.*s", S(ef_type(e,fn->fn.recv_decl->rtype)), S(ef_fn_name(e,fn)));
        return sb_finish(&sb);
    }
    /* A free function lives on its module's holder class. */
    Module *mod = (Module *)fn->owner;
    sb_fmt(&sb, "%.*s.%.*s", S(ef_module_holder(e, mod)), S(ef_fn_name(e,fn)));
    return sb_finish(&sb);
}

/* Renders the argument list, honouring conventions. `out` arguments pass the
 * storage itself; borrowed arguments pass the reference with no copy. */
static Str call_args(E *e, Expr *x, Item *fn, Str extra_out) {
    SB sb;
    sb_init(&sb, e->a);
    bool has_self = fn->fn.params.len > 0 && fn->fn.params.data[0].is_self;
    bool first    = true;

    bool sequence = false;
    for (uint32_t i = 0; i < x->call.args.len; i++) {
        Expr *v = x->call.args.data[i].value;
        /* A freshly built aggregate already denotes a stable temporary. */
        if (needs_sequence(v))
            sequence = true;
    }

    for (uint32_t i = 0; i < x->call.args.len; i++) {
        if (!first) sb_cstr(&sb, ", ");
        first = false;
        Arg *ar = &x->call.args.data[i];
        Str value = sequence && ar->conv == CONV_LET && !ef_is_literal(ar->value) &&
                    ar->value->kind != EX_STRUCT_LIT && ar->value->kind != EX_ARRAY_LIT
                    ? hold(e, ar->value) : ef_expr(e, ar->value);
        sb_str(&sb, value);
    }

    /* Fill every omitted default here rather than leaning on the signature.
     *
     * Two things go wrong otherwise. A default needing statements — a struct
     * literal, say — emitted them into the class body, which Workbench
     * rejects outright ("Unexpected scope"). And an omitted default left the
     * synthetic `out result` of an error union sitting in the wrong argument
     * slot. Filling them at the call site is also what the native back end
     * already does, so the two targets agree. */
    uint32_t base = x->call.args.len + (has_self ? 1 : 0);
    for (uint32_t i = base; i < fn->fn.params.len; i++) {
        Param *pm = &fn->fn.params.data[i];
        if (!pm->deflt) continue;
        if (!first) sb_cstr(&sb, ", ");
        first = false;
        sb_str(&sb, ef_expr(e, pm->deflt));
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
    ArgVec args = x->call.args;
    bool sequence = needs_sequence(recv);
    for (uint32_t i = 0; i < args.len; i++) sequence = sequence || needs_sequence(args.data[i].value);
    Str r = sequence ? hold(e, recv) : ef_expr(e, recv);
    Str values[2];
    for (uint32_t i = 0; i < args.len; i++)
        values[i] = sequence ? hold(e, args.data[i].value) : ef_expr(e, args.data[i].value);

    SB sb;
    sb_init(&sb, e->a);
    switch ((Intrinsic)x->intrinsic) {
        case INTR_LIST_LEN: sb_fmt(&sb, "%.*s.Count()", S(r)); break;
        case INTR_LIST_GET:
            sb_fmt(&sb, "%.*s.Get(%.*s)", S(r), S(values[0]));
            break;
        case INTR_LIST_PUSH:
            ef_line(e, "%.*s.Insert(%.*s);", S(r), S(values[0]));
            sb_cstr(&sb, "0");
            break;
        case INTR_LIST_SET:
            ef_line(e, "%.*s.Set(%.*s, %.*s);", S(r), S(values[0]), S(values[1]));
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
    bool sequence = false;
    for (uint32_t i = 0; i < args.len; i++) sequence = sequence || needs_sequence(args.data[i].value);

    if (intrinsic_is_vec_new((Intrinsic)x->intrinsic)) {
        /* `vector` is three floats, so a Vec2 or Vec4 never reaches here —
         * the enfusion profile lint rejects them at BE0701. */
        sb_cstr(&sb, "Vector(");
        for (uint32_t i = 0; i < args.len; i++) {
            if (i) sb_cstr(&sb, ", ");
            Str value = sequence ? hold(e, args.data[i].value) : ef_expr(e, args.data[i].value);
            sb_fmt(&sb, "%.*s", S(value));
        }
        sb_char(&sb, ')');
        return sb_finish(&sb);
    }

    Expr *receiver = x->call.callee->field.base;
    sequence = sequence || needs_sequence(receiver);
    Str recv = sequence ? hold(e, receiver) : ef_expr(e, receiver);
    Str argument = STR_EMPTY;
    if (args.len) argument = sequence ? hold(e, args.data[0].value) : ef_expr(e, args.data[0].value);

    switch ((Intrinsic)x->intrinsic) {
        case INTR_VEC_LENGTH: sb_fmt(&sb, "%.*s.Length()", S(recv)); break;
        case INTR_VEC_LENGTH_SQ: sb_fmt(&sb, "%.*s.LengthSq()", S(recv)); break;
        case INTR_VEC_NORMALIZED: sb_fmt(&sb, "%.*s.Normalized()", S(recv)); break;
        case INTR_VEC_DOT:
            sb_fmt(&sb, "vector.Dot(%.*s, %.*s)", S(recv),
                   S(argument));
            break;
        case INTR_VEC_DISTANCE:
            sb_fmt(&sb, "vector.Distance(%.*s, %.*s)", S(recv),
                   S(argument));
            break;
        default: { /* INTR_VEC_CROSS */
            /* Spelled out rather than called, because no cross product could
             * be confirmed on the engine's `vector` and the formula needs
             * only indexing and arithmetic, both of which are confirmed.
             * The temporaries keep each operand evaluated exactly once. */
            Str a = ef_tmp(e), b = ef_tmp(e);
            ef_line(e, "vector %.*s = %.*s;", S(a), S(recv));
            ef_line(e, "vector %.*s = %.*s;", S(b), S(argument));
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
        case INTR_PRINTLN: {
            /* The engine's Print always ends the line, so both map to it. */
            for (uint32_t i = 0; i < args.len; i++)
                ef_line(e,"Print(%.*s);",S(ef_expr(e,args.data[i].value)));
            if (args.len == 0) ef_line(e, "Print(\"\");");
            sb_cstr(&sb, "0");
            return sb_finish(&sb);
        }

        case INTR_ASSERT:
            ef_line(e, "if (!(%.*s))", S(ef_expr(e, args.data[0].value)));
            ef_line(e, "\tPrint(\"beryl: assertion failed\");");
            sb_cstr(&sb, "0");
            return sb_finish(&sb);

        case INTR_MIN:
        case INTR_MAX:
        case INTR_CLAMP: {
            /* The float bindings round large integers before selecting them.
             * Keep pure f32 expressions unchanged, but explicitly sequence an
             * effectful argument list before entering either engine binding. */
            const char *name = (Intrinsic)x->intrinsic == INTR_MIN ? "Min" :
                               (Intrinsic)x->intrinsic == INTR_MAX ? "Max" : "Clamp";
            bool sequence = false;
            for (uint32_t i = 0; i < args.len; i++)
                sequence = sequence || needs_sequence(args.data[i].value);
            Str values[3];
            for (uint32_t i = 0; i < args.len; i++) {
                Expr *arg = args.data[i].value;
                values[i] = sequence && !ef_is_literal(arg) ? hold(e, arg) : ef_expr(e, arg);
            }
            sb_fmt(&sb, "Math.%s%s(%.*s, %.*s", name,
                   x->type && x->type->kind == TY_INT ? "Int" : "",
                   S(values[0]), S(values[1]));
            if (args.len == 3) sb_fmt(&sb, ", %.*s", S(values[2]));
            sb_char(&sb, ')');
            return sb_finish(&sb);
        }
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
            /* Test a representable threshold before evaluating a +/- b.
             * Positive b makes MAX-b and MIN+b safe; negative b makes
             * MIN-b and MAX+b safe, including b == INT_MIN. Capture both
             * operands once, in source order, before branching. */
            bool add = (Intrinsic)x->intrinsic == INTR_SATURATING_ADD;
            Str a = hold(e, args.data[0].value);
            Str b = hold(e, args.data[1].value);
            Str result = ef_tmp(e);
            const char *positive_limit = add ? "2147483647" : "-2147483648";
            const char *negative_limit = add ? "-2147483648" : "2147483647";
            const char *threshold_op = add ? "-" : "+";
            const char *op = add ? "+" : "-";
            ef_line(e, "int %.*s = %.*s;", S(result), S(a));
            ef_line(e, "if (%.*s > 0)", S(b));
            ef_line(e, "{"); e->indent++;
            ef_line(e, "if (%.*s %s %s %s %.*s)", S(a), add ? ">" : "<",
                    positive_limit, threshold_op, S(b));
            ef_line(e, "\t%.*s = %s;", S(result), positive_limit);
            ef_line(e, "else");
            ef_line(e, "\t%.*s = %.*s %s %.*s;", S(result), S(a), op, S(b));
            e->indent--; ef_line(e, "}");
            ef_line(e, "else if (%.*s < 0)", S(b));
            ef_line(e, "{"); e->indent++;
            ef_line(e, "if (%.*s %s %s %s %.*s)", S(a), add ? "<" : ">",
                    negative_limit, threshold_op, S(b));
            ef_line(e, "\t%.*s = %s;", S(result), negative_limit);
            ef_line(e, "else");
            ef_line(e, "\t%.*s = %.*s %s %.*s;", S(result), S(a), op, S(b));
            e->indent--; ef_line(e, "}");
            sb_str(&sb, result);
            return sb_finish(&sb);
        }
        default: sb_cstr(&sb, "0"); return sb_finish(&sb);
    }
}

static Str ef_expr_gen(E *e, Expr *x);

Str ef_ptr_key(Arena *a, const void *p, uint32_t epoch) {
    char *b = ARENA_ARRAY(a, char, sizeof p + sizeof epoch);
    for (size_t i = 0; i < sizeof p; i++) b[i] = (char)(((uintptr_t)p >> (i * 8)) & 0xff);
    for (size_t i = 0; i < sizeof epoch; i++)
        b[sizeof p + i] = (char)((epoch >> (i * 8)) & 0xff);
    return (Str){b, (uint32_t)(sizeof p + sizeof epoch)};
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
        Str  key = ef_ptr_key(e->a, x, e->epoch);
        Str *hit = (Str *)map_get(e->memo, key);
        if (hit) return *hit;
        EfOrigin previous_origin = e->origin;
        e->origin = ef_expression_origin(e, x);
        Str  r   = ef_expr_gen(e, x);
        e->origin = previous_origin;
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
        case EX_INT:
            if (x->type && x->type->kind==TY_FLOAT) sb_str(&sb,ef_f32_literal(e,(double)(float)x->int_lit.val,x->span));
            else sb_fmt(&sb, "%llu", (unsigned long long)x->int_lit.val);
            break;
        case EX_FLOAT: sb_str(&sb,ef_f32_literal(e,x->float_lit.val,x->span)); break;
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
                sb_str(&sb, ef_local(e, ((Local *)x->res)->name, ((Local *)x->res)->span));
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
                    case CV_UINT: sb_fmt(&sb, "%llu", (unsigned long long)v.u); break;
                    case CV_FLOAT: sb_str(&sb,ef_f32_literal(e,v.f,x->span)); break;
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
            if (x->field.base && x->field.base->kind == EX_SELF) sb_fmt(&sb,"this.%.*s",S(ef_field(e,x->field.name)));
            else sb_fmt(&sb, "%.*s.%.*s", S(ef_expr(e, x->field.base)), S(ef_field(e, x->field.name)));
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
            if (x->binary.op == TK_ANDAND || x->binary.op == TK_OROR) {
                Str l = hold(e, x->binary.lhs);
                ef_line(e, "if (%s%.*s)", x->binary.op == TK_OROR ? "!" : "", S(l));
                ef_line(e, "{");
                e->indent++;
                Str r = ef_expr(e, x->binary.rhs);
                ef_line(e, "%.*s = %.*s;", S(l), S(r));
                e->indent--;
                ef_line(e, "}");
                sb_str(&sb, l);
                break;
            }

            Str seq_l = STR_EMPTY, seq_r = STR_EMPTY;
            if (needs_sequence(x)) {
                seq_l = hold(e, x->binary.lhs);
                seq_r = hold(e, x->binary.rhs);
                /* Rendering later in this case must reuse these values, not
                 * the original call text. This is per occurrence after the
                 * shared default-expansion pass. */
                Str *l = ARENA_NEW(e->a, Str), *r = ARENA_NEW(e->a, Str);
                *l = seq_l; *r = seq_r;
                map_put(e->memo, ef_ptr_key(e->a, x->binary.lhs, e->epoch), l);
                map_put(e->memo, ef_ptr_key(e->a, x->binary.rhs, e->epoch), r);
            }

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
                Str target = call_target(e, x, fn);
                Str args = call_args(e, x, fn, STR_EMPTY);
                sb_fmt(&sb, "%.*s(%.*s)", S(target), S(args));
                break;
            }
            /* An error-returning call needs somewhere to put its value. */
            Str out = STR_EMPTY;
            if (fn->rtype->elem && fn->rtype->elem->kind != TY_VOID) {
                out = ef_tmp(e);
                ef_line(e, "%.*s %.*s;", S(ef_type(e, fn->rtype->elem)), S(out));
            }
            Str okv = ef_tmp(e);
            Str target = call_target(e, x, fn);
            Str args = call_args(e, x, fn, out);
            ef_line(e, "bool %.*s = %.*s(%.*s);", S(okv), S(target), S(args));
            sb_str(&sb, okv); /* the caller inspects the bool */
            break;
        }

        case EX_STRUCT_LIT: {
            Type *t    = x->type;
            Str   cls  = ef_type(e, t);
            Str   tmp  = ef_tmp(e);
            ef_line(e, "%.*s %.*s = new %.*s();", S(cls), S(tmp), S(cls));
            /* Preserve written order, followed by normalized missing defaults.
             * Each assignment captures its logical value before the next field
             * can call a function or mutate an earlier source. */
            for (uint32_t i = 0; i < x->struct_lit.fields.len; i++) {
                FieldInit *fl = &x->struct_lit.fields.data[i];
                Expr *val = fl->value;
                ef_line(e, "%.*s.%.*s = %.*s;", S(tmp), S(ef_field(e, fl->name)),
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
            Str target = call_target(e, inner, fn);
            Str args = call_args(e, inner, fn, out);
            ef_line(e, "if (!%.*s(%.*s))", S(target), S(args));
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
                Str target = call_target(e, val, fn);
                Str args = call_args(e, val, fn, res);
                ef_line(e, "if (!%.*s(%.*s))", S(target), S(args));
                ef_line(e, "{");
                e->indent++;
                ef_line(e, "%.*s = %.*s;", S(res), S(ef_expr(e, x->orelse_expr.fallback)));
                e->indent--;
                ef_line(e, "}");
            } else {
                ef_line(e, "%.*s = %.*s;", S(res), S(ef_expr(e, val)));
            }
            sb_str(&sb, res);
            break;
        }

        case EX_CATCH: {
            Expr *val = x->catch_expr.value;
            Item *fn  = (val->res_kind == RES_FN) ? (Item *)val->res : NULL;
            bool is_void = x->type && x->type->kind == TY_VOID;
            Str res = is_void ? STR_EMPTY : ef_tmp(e);
            if (!is_void) ef_line(e, "%.*s %.*s;", S(ef_type(e, x->type)), S(res));
            if (fn && fn->rtype && fn->rtype->kind == TY_ERRUNION) {
                Str target = call_target(e, val, fn);
                Str args = call_args(e, val, fn, res);
                ef_line(e, "if (!%.*s(%.*s))", S(target), S(args));
                ef_line(e, "{");
                e->indent++;
                if (!is_void) {
                    const char *zero = x->type->kind == TY_BOOL ? "false" :
                        x->type->kind == TY_STR ? "\"\"" : x->type->kind == TY_VEC3 ? "\"0 0 0\"" : "0";
                    ef_line(e, "%.*s = %s;", S(res), zero);
                }
                if (!str_empty(x->catch_expr.binding))
                    ef_line(e, "int %.*s = 1;", S(ef_local(e, x->catch_expr.binding, x->span)));
                if (x->catch_expr.handler && x->catch_expr.handler->kind == EX_BLOCK)
                    ef_block(e, x->catch_expr.handler);
                else ef_expr(e, x->catch_expr.handler);
                e->indent--;
                ef_line(e, "}");
            }
            sb_str(&sb, is_void ? str_from("0") : res);
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
    /* A new statement is a new evaluation site. The memo exists only to
     * neutralize `S()` rendering its argument twice inside one expression;
     * letting it live longer made a shared node — a parameter default, which
     * every call site points at — render once and be reused elsewhere, so the
     * second call site referenced a temporary declared in the first. */
    e->epoch++;
    if (!s) return;
    EfOrigin previous_origin = e->origin;
    e->origin.span = s->span;
    e->origin.expansion = SPAN_NONE;
    e->origin.kind = s->kind == ST_DEFER ? "immediate_defer" : "statement";

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
                ef_line(e, "%.*s %.*s = %.*s;", S(ef_type(e, t)), S(ef_local(e, s->let.name, s->span)), S(v));
            } else if (t && (t->kind == TY_LIST || t->kind == TY_MAP)) {
                /* A container starts empty; a null ref would not be usable. */
                ef_line(e, "%.*s %.*s = new %.*s();", S(ef_type(e, t)),
                        S(ef_local(e, s->let.name, s->span)), S(ef_type(e, t)));
            } else {
                ef_line(e, "%.*s %.*s;", S(ef_type(e, t)), S(ef_local(e, s->let.name, s->span)));
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
            Expr *target = s->assign.target;
            if (target->kind == EX_INDEX) {
                /* EnforceScript rejects array[index] += value. Freeze the
                 * receiver and index once before the RHS, then emit a store. */
                Str base = ty_is_vec(target->index.base->type)
                    ? ef_expr(e, target->index.base) : hold(e, target->index.base);
                Str index = hold(e, target->index.index);
                Str old = STR_EMPTY;
                if (s->assign.op != TK_ASSIGN) {
                    old = ef_tmp(e);
                    ef_line(e, "%.*s %.*s = %.*s[%.*s];", S(ef_type(e, target->type)), S(old), S(base), S(index));
                }
                Str value = copy_if_needed(e, s->assign.value, ef_expr(e, s->assign.value));
                if (s->assign.op == TK_ASSIGN)
                    ef_line(e, "%.*s[%.*s] = %.*s;", S(base), S(index), S(value));
                else {
                    const char *op = s->assign.op == TK_PLUSEQ ? "+" :
                        s->assign.op == TK_MINUSEQ ? "-" : s->assign.op == TK_STAREQ ? "*" :
                        s->assign.op == TK_SLASHEQ ? "/" : "%";
                    ef_line(e, "%.*s[%.*s] = %.*s %s %.*s;", S(base), S(index), S(old), op, S(value));
                }
                break;
            }
            Str lv = ef_expr(e, s->assign.target);
            Str old=STR_EMPTY;
            if(s->assign.op!=TK_ASSIGN && needs_sequence(s->assign.value))
                old=hold(e,s->assign.target);
            Str rv = copy_if_needed(e, s->assign.value, ef_expr(e, s->assign.value));
            if(old.len) {
                const char *op=s->assign.op==TK_PLUSEQ?"+":s->assign.op==TK_MINUSEQ?"-":
                    s->assign.op==TK_STAREQ?"*":s->assign.op==TK_SLASHEQ?"/":"%";
                ef_line(e,"%.*s = %.*s %s %.*s;",S(lv),S(old),op,S(rv));
            } else ef_line(e, "%.*s %s %.*s;", S(lv), assign_op_str(s->assign.op), S(rv));
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
                Str lo = hold(e, it->range.lo);
                Str hi = hold(e, it->range.hi);
                Str lv = ef_local(e, s->for_st.var, s->span);
                ef_line(e, "for (int %.*s = %.*s; %.*s < %.*s; %.*s++)", S(lv), S(lo),
                        S(lv), S(hi), S(lv));
            } else {
                Type *et = (it && it->type) ? it->type->elem : NULL;
                ef_line(e, "foreach (%.*s %.*s : %.*s)", S(ef_type(e, et)),
                        S(ef_local(e, s->for_st.var, s->span)), S(ef_expr(e, it)));
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
                else if (s->expr->kind == EX_CALL && s->expr->res_kind == RES_FN &&
                         ((Item *)s->expr->res)->rtype->kind == TY_VOID)
                    ef_line(e, "%.*s;", S(v));
                ef_line(e, "return true;");
            } else {
                ef_line(e, "return %.*s;", S(v));
            }
            break;
        }

        case ST_BREAK: ef_line(e, "break;"); break;
        case ST_CONTINUE: ef_line(e, "continue;"); break;
        case ST_DEFER: {
            /* Preserve the documented v0.1 immediate behavior, including a
             * direct call whose expression rendering emits no statement. */
            Str value = ef_expr(e, s->expr);
            if (s->expr && s->expr->kind == EX_CALL && s->expr->res_kind == RES_FN &&
                ((Item *)s->expr->res)->rtype->kind != TY_ERRUNION)
                ef_line(e, "%.*s;", S(value));
            break;
        }
        default: break;
    }
    e->origin = previous_origin;
}

void ef_block(E *e, Expr *b) {
    if (!b || b->kind != EX_BLOCK) return;
    for (uint32_t i = 0; i < b->block.stmts.len; i++) ef_stmt(e, b->block.stmts.data[i]);
}
