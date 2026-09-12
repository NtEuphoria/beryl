#include "constfold.h"
#include <math.h>

#define CONST_STEP_LIMIT 100000u
#define CONST_DEPTH_LIMIT 64u
typedef struct {
    DiagBag *d; Program *p;
    Module *module; Item *scope;
    uint32_t steps, depth;
    bool report, failed;
} CE;

static ConstVal none(void) { return (ConstVal){0}; }
static ConstVal cint(int64_t i) { return (ConstVal){.kind = CV_INT, .i = i}; }
static ConstVal cuint(uint64_t u) { return (ConstVal){.kind = CV_UINT, .u = u}; }
static ConstVal cflt(double f) { return (ConstVal){.kind = CV_FLOAT, .f = f}; }
static ConstVal cbool(bool b) { return (ConstVal){.kind = CV_BOOL, .b = b}; }
static void fail(CE *c, uint32_t code, Span at, const char *msg) {
    if (!c->failed && c->report) diag_error(c->d, code, at, "%s", msg);
    c->failed = true;
}
static ConstVal overflow(CE *c, Expr *e) {
    fail(c, 503, e->span, "constant arithmetic overflows its integer type");
    return none();
}
static uint64_t mask(unsigned bits) {
    return bits == 64 ? UINT64_MAX : (UINT64_C(1) << bits) - 1;
}
/* Decode two's-complement bits without a host signed overflow or an
 * out-of-range unsigned-to-signed conversion. */
static int64_t signed_bits(uint64_t u, unsigned bits) {
    u &= mask(bits);
    uint64_t sign = UINT64_C(1) << (bits - 1);
    return (u & sign) ? -1 - (int64_t)(mask(bits) - u) : (int64_t)u;
}
static uint64_t as_u(ConstVal v) {
    return v.kind == CV_UINT ? v.u : v.kind == CV_BOOL ? (uint64_t)v.b : (uint64_t)v.i;
}
static double as_f(ConstVal v) {
    return v.kind == CV_FLOAT ? v.f : v.kind == CV_UINT ? (double)v.u
        : v.kind == CV_BOOL ? (double)v.b : (double)v.i;
}
static Item *constant_item(CE *c, Expr *e) {
    if (e->res_kind == RES_CONST) return e->res;
    if (e->res_kind != RES_NONE) return NULL;
    Str full, root;
    if (!prog_expr_path(c->p->a, e, &full, &root)) return NULL;
    Item *it = prog_lookup(c->p, c->module, full);
    if (!it || it->kind != IT_CONST) return NULL;
    if (!prog_accessible(c->d, c->module, it, e->span)) { c->failed = true; return NULL; }
    return it;
}
/* Extents can be evaluated before checking. Honor explicit suffixes there,
 * otherwise use the language's i32/f64 defaults. */
static Type *expr_type(CE *c, Expr *e) {
    if (e->type) return e->type;
    if (e->kind == EX_PATH || e->kind == EX_FIELD) {
        Item *it = constant_item(c, e);
        if (it && it->kind == IT_CONST && it->rtype) return it->rtype;
        if (it && it->konst.type) return resolve_type_expr(c->p, c->d, it->owner, it, it->konst.type);
    }
    if (e->kind == EX_UNARY) return expr_type(c, e->unary.operand);
    if (e->kind == EX_BINARY) return expr_type(c, e->binary.lhs);
    uint8_t bits = 0;
    bool sign = false;
    Str suffix = e->kind == EX_INT ? e->int_lit.suffix :
                 e->kind == EX_FLOAT ? e->float_lit.suffix : STR_EMPTY;
    TypeKind k = ty_prim_from_name(suffix, &bits, &sign);
    if (k == TY_INT) return ty_int(c->p->types, bits, sign);
    if (k == TY_FLOAT) return ty_float(c->p->types, bits);
    return e->kind == EX_FLOAT ? ty_float(c->p->types, 64) : ty_int(c->p->types, 32, true);
}
static ConstVal bit_value(uint64_t u, Type *t) {
    return t->is_signed ? cint(signed_bits(u, t->bits)) : cuint(u & mask(t->bits));
}
static ConstVal checked_signed(CE *c, Expr *e, Type *t, int64_t x) {
    int64_t hi = (int64_t)(mask(t->bits) >> 1);
    return x < -hi - 1 || x > hi ? overflow(c, e) : cint(x);
}
static ConstVal float_value(double f, Type *t) {
    return cflt(t && t->kind == TY_FLOAT && t->bits == 32 ? (double)(float)f : f);
}
static ConstVal ev(CE *c, Expr *e);
static ConstVal ev_binary(CE *c, Expr *e) {
    TokKind op = e->binary.op;
    ConstVal l = ev(c, e->binary.lhs);
    if (l.kind == CV_NONE) return none();
    /* Unexecuted operands contribute no value dependency or trap. */
    if (l.kind == CV_BOOL && op == TK_ANDAND && !l.b) return cbool(false);
    if (l.kind == CV_BOOL && op == TK_OROR && l.b) return cbool(true);
    ConstVal r = ev(c, e->binary.rhs);
    if (r.kind == CV_NONE) return none();
    if (l.kind == CV_BOOL && r.kind == CV_BOOL) {
        switch (op) {
            case TK_ANDAND: return cbool(l.b && r.b);
            case TK_OROR: return cbool(l.b || r.b);
            case TK_EQ: return cbool(l.b == r.b);
            case TK_NE: return cbool(l.b != r.b);
            default: break;
        }
    }
    if (l.kind == CV_STR || r.kind == CV_STR) {
        if (l.kind == CV_STR && r.kind == CV_STR) {
            if (op == TK_EQ) return cbool(str_eq(l.s, r.s));
            if (op == TK_NE) return cbool(!str_eq(l.s, r.s));
        }
        fail(c, 501, e->span, "this operator is not constant on strings");
        return none();
    }
    bool fp = l.kind == CV_FLOAT || r.kind == CV_FLOAT;
    bool uns = l.kind == CV_UINT;
#define CMP(OP) (fp ? as_f(l) OP as_f(r) : uns ? as_u(l) OP as_u(r) : l.i OP r.i)
    switch (op) {
        case TK_EQ: return cbool(CMP(==));
        case TK_NE: return cbool(CMP(!=));
        case TK_LT: return cbool(CMP(<));
        case TK_LE: return cbool(CMP(<=));
        case TK_GT: return cbool(CMP(>));
        case TK_GE: return cbool(CMP(>=));
        default: break;
    }
#undef CMP
    Type *t = expr_type(c, e->binary.lhs);
    if (fp) {
        double x = as_f(l), y = as_f(r);
        switch (op) {
            case TK_PLUS: return float_value(x + y, t);
            case TK_MINUS: return float_value(x - y, t);
            case TK_STAR: return float_value(x * y, t);
            case TK_SLASH:
                if (y != 0) return float_value(x / y, t);
                fail(c, 502, e->span, "division by zero in a constant expression");
                return none();
            default: break;
        }
    } else if (t->kind == TY_INT) {
        uint64_t ux = as_u(l), uy = as_u(r), uout = 0;
        int64_t x = l.i, y = r.i, out = 0;
        if (op == TK_AMP) return bit_value(ux & uy, t);
        if (op == TK_PIPE) return bit_value(ux | uy, t);
        if (op == TK_CARET) return bit_value(ux ^ uy, t);
        if (op == TK_SHL || op == TK_SHR) {
            if (uy >= t->bits) {
                fail(c, 503, e->span, "constant shift is out of range");
                return none();
            }
            if (op == TK_SHL) return bit_value(ux << uy, t);
            uint64_t shifted = (ux & mask(t->bits)) >> uy;
            if (t->is_signed && x < 0 && uy)
                shifted |= mask(t->bits) ^ (mask(t->bits) >> uy);
            return bit_value(shifted, t);
        }
        if ((op == TK_SLASH || op == TK_PERCENT) && uy == 0) {
            fail(c, 502, e->span, "division by zero in a constant expression");
            return none();
        }
        if (!t->is_signed) {
            bool bad = false;
            switch (op) {
                case TK_PLUS: bad = __builtin_add_overflow(ux, uy, &uout); break;
                case TK_MINUS: bad = __builtin_sub_overflow(ux, uy, &uout); break;
                case TK_STAR: bad = __builtin_mul_overflow(ux, uy, &uout); break;
                case TK_SLASH: uout = ux / uy; break;
                case TK_PERCENT: uout = ux % uy; break;
                default: fail(c, 501, e->span, "this operator is not constant"); return none();
            }
            return bad || uout > mask(t->bits) ? overflow(c, e) : cuint(uout);
        }
        int64_t min = -(int64_t)(mask(t->bits) >> 1) - 1;
        /* Match be_rem: the mathematical remainder is representable even
         * when the quotient is not. Do not execute host MIN % -1. */
        if (op == TK_PERCENT && x == min && y == -1) return cint(0);
        if ((op == TK_SLASH || op == TK_PERCENT) && x == min && y == -1)
            return overflow(c, e);
        bool bad = false;
        switch (op) {
            case TK_PLUS: bad = __builtin_add_overflow(x, y, &out); break;
            case TK_MINUS: bad = __builtin_sub_overflow(x, y, &out); break;
            case TK_STAR: bad = __builtin_mul_overflow(x, y, &out); break;
            case TK_SLASH: out = x / y; break;
            case TK_PERCENT: out = x % y; break;
            default: fail(c, 501, e->span, "this operator is not constant"); return none();
        }
        return bad ? overflow(c, e) : checked_signed(c, e, t, out);
    }
    fail(c, 501, e->span, "this operator is not constant");
    return none();
}
static ConstVal ev_inner(CE *c, Expr *e) {
    switch (e->kind) {
        case EX_INT: {
            Type *t = expr_type(c, e);
            if (t->kind == TY_FLOAT) return float_value(t->bits==32 ?
                (double)(float)e->int_lit.val : (double)e->int_lit.val, t);
            if (t->is_signed) {
                if (e->int_lit.val > (mask(t->bits) >> 1)) return overflow(c, e);
                return cint((int64_t)e->int_lit.val);
            }
            return e->int_lit.val > mask(t->bits) ? overflow(c, e) : cuint(e->int_lit.val);
        }
        case EX_FLOAT: return float_value(e->float_lit.val, expr_type(c, e));
        case EX_BOOL: return cbool(e->bool_lit);
        case EX_CHAR: return cuint(e->char_lit);
        case EX_STR: return (ConstVal){.kind = CV_STR, .s = e->str_lit};
        case EX_BINARY: return ev_binary(c, e);
        case EX_UNARY: {
            Type *t = expr_type(c, e);
            Expr *arg = e->unary.operand;
            if (e->unary.op == TK_MINUS && arg->kind == EX_INT &&
                t->kind == TY_INT && t->is_signed &&
                arg->int_lit.val == (UINT64_C(1) << (t->bits - 1)))
                return cint(-(int64_t)(arg->int_lit.val - 1) - 1);
            ConstVal v = ev(c, arg);
            if (v.kind == CV_NONE) return none();
            switch (e->unary.op) {
                case TK_MINUS:
                    if (v.kind == CV_FLOAT) return float_value(-v.f, t);
                    if (v.kind == CV_UINT) return v.u ? overflow(c, e) : v;
                    if (v.kind == CV_INT) {
                        if (v.i == INT64_MIN) return overflow(c, e);
                        return checked_signed(c, e, t, -v.i);
                    }
                    break;
                case TK_BANG: if (v.kind == CV_BOOL) return cbool(!v.b); break;
                case TK_TILDE: return bit_value(~as_u(v), t);
                default: break;
            }
            break;
        }
        case EX_CAST: {
            ConstVal v = ev(c, e->cast.value);
            if (v.kind == CV_NONE) return none();
            Type *t = e->type ? e->type : resolve_type_expr(c->p, c->d, c->module, c->scope, e->cast.type);
            if (t->kind == TY_FLOAT) {
                if (t->bits==32 && v.kind==CV_INT) return float_value((double)(float)v.i,t);
                if (t->bits==32 && v.kind==CV_UINT) return float_value((double)(float)v.u,t);
                return float_value(as_f(v), t);
            }
            if (t->kind == TY_CHAR) t = ty_int(c->p->types, 32, false);
            if (t->kind == TY_ENUM) t = ty_int(c->p->types, 32, true);
            if (t->kind == TY_INT) {
                if (v.kind != CV_FLOAT) return bit_value(as_u(v), t);
                /* Check the truncated value against exclusive powers of two
                 * before invoking a host floating-to-integer cast. */
                double f = trunc(v.f);
                double bound = ldexp(1.0, t->is_signed ? t->bits - 1 : t->bits);
                if (!isfinite(f) || f < (t->is_signed ? -bound : 0) || f >= bound)
                    return overflow(c, e);
                return t->is_signed ? cint((int64_t)f) : cuint((uint64_t)f);
            }
            break;
        }
        case EX_PATH:
        case EX_FIELD: {
            Item *it = constant_item(c, e);
            if (it && it->konst.value) {
                Module *saved_module = c->module; Item *saved_scope = c->scope;
                c->module = it->owner; c->scope = it;
                ConstVal result = ev(c, it->konst.value);
                c->module = saved_module; c->scope = saved_scope;
                return result;
            }
            break;
        }
        default: break;
    }
    fail(c, 501, e->span, "this is not a constant expression");
    return none();
}
static ConstVal ev(CE *c, Expr *e) {
    if (!e || c->failed) return none();
    if (++c->steps > CONST_STEP_LIMIT || c->depth >= CONST_DEPTH_LIMIT) {
        fail(c, 504, e->span, "constant evaluation exceeded its step or nesting limit");
        return none();
    }
    c->depth++;
    ConstVal v = ev_inner(c, e);
    c->depth--;
    return c->failed ? none() : v;
}
ConstVal const_eval(Arena *a, DiagBag *d, Program *p, Expr *e, bool report) {
    CE c = {.d = d, .p = p, .report = report};
    return ev(&c, e);
}
bool const_eval_len(Arena *a, DiagBag *d, Program *p, Expr *e, uint64_t *out) {
    return const_eval_len_in(a, d, p, NULL, NULL, e, out);
}
bool const_eval_len_in(Arena *a, DiagBag *d, Program *p, Module *module, Item *scope, Expr *e, uint64_t *out) {
    *out = 0;
    if (!e) return false;
    CE c = {.d = d, .p = p, .module = module, .scope = scope, .report = false};
    ConstVal v = ev(&c, e);
    if (v.kind != CV_INT && v.kind != CV_UINT) {
        diag_error(d, 505, e->span, "an array length must be a constant integer");
        return false;
    }
    if (v.kind == CV_INT && v.i < 0) {
        diag_error(d, 505, e->span, "an array length cannot be negative");
        return false;
    }
    *out = as_u(v);
    return true;
}
