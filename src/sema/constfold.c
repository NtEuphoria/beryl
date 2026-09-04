#include "constfold.h"

#define CONST_STEP_LIMIT 100000u
#define CONST_DEPTH_LIMIT 64u

typedef struct {
    Arena   *a;
    DiagBag *d;
    Program *p;
    uint32_t steps;
    uint32_t depth;
    bool     report;
    bool     failed;
} CE;

static ConstVal none(void) {
    ConstVal v = {0};
    return v;
}
static ConstVal cint(int64_t i) {
    ConstVal v = {CV_INT, i, 0, false, STR_EMPTY};
    return v;
}
static ConstVal cflt(double f) {
    ConstVal v = {CV_FLOAT, 0, f, false, STR_EMPTY};
    return v;
}
static ConstVal cbool(bool b) {
    ConstVal v = {CV_BOOL, 0, 0, b, STR_EMPTY};
    return v;
}

static void fail(CE *c, uint32_t code, Span at, const char *msg, const char *help) {
    c->failed = true;
    if (!c->report) return;
    Diag *dg = diag_error(c->d, code, at, "%s", msg);
    if (help) diag_help(dg, "%s", help);
}

static double as_f(ConstVal v) { return v.kind == CV_FLOAT ? v.f : (double)v.i; }

static ConstVal ev(CE *c, Expr *e);

static ConstVal ev_binary(CE *c, Expr *e) {
    ConstVal l = ev(c, e->binary.lhs);
    ConstVal r = ev(c, e->binary.rhs);
    if (l.kind == CV_NONE || r.kind == CV_NONE) return none();

    TokKind op = e->binary.op;

    if (l.kind == CV_BOOL && r.kind == CV_BOOL) {
        switch (op) {
            case TK_ANDAND: return cbool(l.b && r.b);
            case TK_OROR: return cbool(l.b || r.b);
            case TK_EQ: return cbool(l.b == r.b);
            case TK_NE: return cbool(l.b != r.b);
            default: break;
        }
        fail(c, 501, e->span, "this operator is not constant on booleans", NULL);
        return none();
    }

    if (l.kind == CV_STR || r.kind == CV_STR) {
        if (l.kind == CV_STR && r.kind == CV_STR) {
            if (op == TK_EQ) return cbool(str_eq(l.s, r.s));
            if (op == TK_NE) return cbool(!str_eq(l.s, r.s));
        }
        fail(c, 501, e->span, "this operator is not constant on strings", NULL);
        return none();
    }

    bool fp = (l.kind == CV_FLOAT || r.kind == CV_FLOAT);

    switch (op) {
        case TK_EQ: return cbool(fp ? as_f(l) == as_f(r) : l.i == r.i);
        case TK_NE: return cbool(fp ? as_f(l) != as_f(r) : l.i != r.i);
        case TK_LT: return cbool(fp ? as_f(l) < as_f(r) : l.i < r.i);
        case TK_LE: return cbool(fp ? as_f(l) <= as_f(r) : l.i <= r.i);
        case TK_GT: return cbool(fp ? as_f(l) > as_f(r) : l.i > r.i);
        case TK_GE: return cbool(fp ? as_f(l) >= as_f(r) : l.i >= r.i);
        default: break;
    }

    if (fp) {
        double x = as_f(l), y = as_f(r);
        switch (op) {
            case TK_PLUS: return cflt(x + y);
            case TK_MINUS: return cflt(x - y);
            case TK_STAR: return cflt(x * y);
            case TK_SLASH:
                if (y == 0) {
                    fail(c, 502, e->span, "division by zero in a constant expression", NULL);
                    return none();
                }
                return cflt(x / y);
            default:
                fail(c, 501, e->span, "this operator is not constant on floats", NULL);
                return none();
        }
    }

    int64_t x = l.i, y = r.i, out = 0;
    switch (op) {
        case TK_PLUS:
            if (__builtin_add_overflow(x, y, &out)) {
                fail(c, 503, e->span, "constant arithmetic overflows a 64-bit value", NULL);
                return none();
            }
            return cint(out);
        case TK_MINUS:
            if (__builtin_sub_overflow(x, y, &out)) {
                fail(c, 503, e->span, "constant arithmetic overflows a 64-bit value", NULL);
                return none();
            }
            return cint(out);
        case TK_STAR:
            if (__builtin_mul_overflow(x, y, &out)) {
                fail(c, 503, e->span, "constant arithmetic overflows a 64-bit value", NULL);
                return none();
            }
            return cint(out);
        case TK_SLASH:
            if (y == 0) {
                fail(c, 502, e->span, "division by zero in a constant expression", NULL);
                return none();
            }
            return cint(x / y);
        case TK_PERCENT:
            if (y == 0) {
                fail(c, 502, e->span, "division by zero in a constant expression", NULL);
                return none();
            }
            return cint(x % y);
        case TK_AMP: return cint(x & y);
        case TK_PIPE: return cint(x | y);
        case TK_CARET: return cint(x ^ y);
        case TK_SHL:
            if (y < 0 || y >= 64) {
                fail(c, 503, e->span, "constant shift is out of range", NULL);
                return none();
            }
            return cint((int64_t)((uint64_t)x << y));
        case TK_SHR:
            if (y < 0 || y >= 64) {
                fail(c, 503, e->span, "constant shift is out of range", NULL);
                return none();
            }
            return cint(x >> y);
        default:
            fail(c, 501, e->span, "this operator is not constant", NULL);
            return none();
    }
}

static ConstVal ev(CE *c, Expr *e) {
    if (!e) return none();

    if (++c->steps > CONST_STEP_LIMIT) {
        fail(c, 504, e->span, "constant evaluation exceeded its step limit",
             "a constant must terminate; check for a self-referential definition");
        return none();
    }
    if (c->depth > CONST_DEPTH_LIMIT) {
        fail(c, 504, e->span, "constant evaluation nested too deeply",
             "a constant must terminate; check for a self-referential definition");
        return none();
    }

    switch (e->kind) {
        case EX_INT: return cint((int64_t)e->int_lit.val);
        case EX_FLOAT: return cflt(e->float_lit.val);
        case EX_BOOL: return cbool(e->bool_lit);
        case EX_STR: {
            ConstVal v = {CV_STR, 0, 0, false, e->str_lit};
            return v;
        }

        case EX_UNARY: {
            ConstVal v = ev(c, e->unary.operand);
            if (v.kind == CV_NONE) return none();
            switch (e->unary.op) {
                case TK_MINUS:
                    if (v.kind == CV_FLOAT) return cflt(-v.f);
                    if (v.kind == CV_INT) return cint(-v.i);
                    break;
                case TK_BANG:
                    if (v.kind == CV_BOOL) return cbool(!v.b);
                    break;
                case TK_TILDE:
                    if (v.kind == CV_INT) return cint(~v.i);
                    break;
                default: break;
            }
            fail(c, 501, e->span, "this operator is not constant here", NULL);
            return none();
        }

        case EX_BINARY: return ev_binary(c, e);

        case EX_CAST: {
            ConstVal v = ev(c, e->cast.value);
            if (v.kind == CV_NONE) return none();
            /* Only the shape matters here; the checker has already validated
             * that the conversion is one `as` permits. */
            if (e->cast.type && e->cast.type->segs.len) {
                Str  last = e->cast.type->segs.data[e->cast.type->segs.len - 1];
                if (str_starts_with(last, "f")) return cflt(as_f(v));
                if (str_starts_with(last, "i") || str_starts_with(last, "u"))
                    return cint(v.kind == CV_FLOAT ? (int64_t)v.f : v.i);
            }
            return v;
        }

        case EX_PATH: {
            if (e->path.segs.len != 1) break;
            Item *it = prog_short(c->p, e->path.segs.data[0]);
            if (!it || it->kind != IT_CONST || !it->konst.value) break;
            c->depth++;
            ConstVal v = ev(c, it->konst.value);
            c->depth--;
            return v;
        }

        default: break;
    }

    fail(c, 501, e->span, "this is not a constant expression",
         "constants are built from literals, other constants, and arithmetic on them");
    return none();
}

ConstVal const_eval(Arena *a, DiagBag *d, Program *p, Expr *e, bool report) {
    CE c  = {0};
    c.a   = a;
    c.d   = d;
    c.p   = p;
    c.report = report;
    return ev(&c, e);
}

bool const_eval_len(Arena *a, DiagBag *d, Program *p, Expr *e, uint64_t *out) {
    *out = 0;
    if (!e) return false;

    ConstVal v = const_eval(a, d, p, e, false);
    if (v.kind != CV_INT) {
        Diag *dg = diag_error(d, 505, e->span,
                              "an array length must be a constant integer");
        diag_help(dg, "use a literal, or a `const` declared with one");
        return false;
    }
    if (v.i < 0) {
        diag_error(d, 505, e->span, "an array length cannot be negative");
        return false;
    }
    *out = (uint64_t)v.i;
    return true;
}
