/* parser_expr.c — Pratt expression parser.
 *
 * Two deliberate design points:
 *
 *   `a.b` always parses as field access, never as a module path. The parser
 *   cannot know which it is; the resolver decides, and flattens the chains
 *   that turn out to name a module or type.
 *
 *   There is no turbofish. Explicit generic arguments do not exist at call
 *   sites, so `<` is unambiguously a comparison operator. Generic arguments
 *   are inferred from argument types during monomorphization.
 */
#include "parser.h"

/* Binding powers, loosest to tightest. */
static int bp_of(TokKind k) {
    switch (k) {
        case TK_DOTDOT: return 1;
        case TK_OROR: return 2;
        case TK_ANDAND: return 3;
        case TK_EQ:
        case TK_NE:
        case TK_LT:
        case TK_LE:
        case TK_GT:
        case TK_GE: return 4;
        case TK_PIPE: return 5;
        case TK_CARET: return 6;
        case TK_AMP: return 7;
        case TK_SHL:
        case TK_SHR: return 8;
        case TK_PLUS:
        case TK_MINUS: return 9;
        case TK_STAR:
        case TK_SLASH:
        case TK_PERCENT: return 10;
        default: return 0;
    }
}

static bool is_cmp(TokKind k) { return bp_of(k) == 4; }

static Expr *parse_unary(P *p);
static Expr *parse_postfix(P *p);
static Expr *parse_primary(P *p);
static Expr *parse_bin(P *p, int min_bp);

static Expr *parse_struct_lit(P *p, Expr *path_expr);

Expr *parse_expr(P *p) { return parse_bin(p, 1); }

static Expr *parse_bin(P *p, int min_bp) {
    Expr *lhs = parse_unary(p);
    if (!lhs) return NULL;

    for (;;) {
        TokKind k = p_kind(p);

        if (k == TK_ORELSE && min_bp <= 1) {
            p_next(p);
            Expr *fb = parse_bin(p, 2);
            if (!fb) return lhs;
            Expr *e                = ast_expr(p->a, EX_ORELSE, span_join(lhs->span, fb->span));
            e->orelse_expr.value    = lhs;
            e->orelse_expr.fallback = fb;
            lhs                     = e;
            continue;
        }

        if (k == TK_CATCH && min_bp <= 1) {
            Token ct = p_next(p);
            Str   binding = STR_EMPTY;
            if (p_accept(p, TK_PIPE)) {
                Token id = p_peek(p);
                if (p_expect(p, TK_IDENT, "in a catch binding")) binding = id.text;
                p_expect(p, TK_PIPE, "after a catch binding");
            }
            Expr *handler = p_check(p, TK_LBRACE) ? parse_block(p) : parse_bin(p, 2);
            if (!handler) handler = ast_expr(p->a, EX_BLOCK, ct.span);
            Expr *e               = ast_expr(p->a, EX_CATCH, span_join(lhs->span, handler->span));
            e->catch_expr.value   = lhs;
            e->catch_expr.binding = binding;
            e->catch_expr.handler = handler;
            lhs                   = e;
            continue;
        }

        int bp = bp_of(k);
        if (bp == 0 || bp < min_bp) break;

        Token op = p_next(p);
        Expr *rhs = parse_bin(p, bp + 1);
        if (!rhs) return lhs;

        if (k == TK_DOTDOT) {
            Expr *e     = ast_expr(p->a, EX_RANGE, span_join(lhs->span, rhs->span));
            e->range.lo = lhs;
            e->range.hi = rhs;
            lhs         = e;
            continue;
        }

        Expr *e         = ast_expr(p->a, EX_BINARY, span_join(lhs->span, rhs->span));
        e->binary.op    = k;
        e->binary.lhs   = lhs;
        e->binary.rhs   = rhs;
        lhs             = e;

        /* Comparisons are non-associative: `a < b < c` is almost always a bug
         * carried over from another language, and chaining has no useful
         * meaning when the result is a bool. */
        if (is_cmp(k) && is_cmp(p_kind(p))) {
            Diag *dg = diag_error(p->d, 208, p_peek(p).span,
                                  "comparison operators cannot be chained");
            diag_label(dg, op.span, "first comparison");
            diag_label(dg, p_peek(p).span, "second comparison here");
            diag_help(dg, "write `a %s b && b %s c`", tok_name(k), tok_name(p_kind(p)));
            p_next(p);
            Expr *drop = parse_bin(p, bp + 1);
            (void)drop;
        }
    }
    return lhs;
}

static Expr *parse_unary(P *p) {
    TokKind k = p_kind(p);
    if (k == TK_MINUS || k == TK_BANG || k == TK_TILDE) {
        Token t   = p_next(p);
        Expr *rhs = parse_unary(p);
        if (!rhs) return NULL;
        Expr *e         = ast_expr(p->a, EX_UNARY, span_join(t.span, rhs->span));
        e->unary.op     = k;
        e->unary.operand = rhs;
        return e;
    }
    if (k == TK_TRY) {
        Token t   = p_next(p);
        Expr *rhs = parse_unary(p);
        if (!rhs) return NULL;
        Expr *e          = ast_expr(p->a, EX_TRY, span_join(t.span, rhs->span));
        e->try_expr.inner = rhs;
        return e;
    }
    return parse_postfix(p);
}

static Expr *parse_postfix(P *p) {
    Expr *e = parse_primary(p);
    if (!e) return NULL;

    for (;;) {
        if (p_check(p, TK_DOT)) {
            p_next(p);
            Token id    = p_peek(p);
            Str   fname = STR_EMPTY;
            if (!p_member_name(p, &fname, "after `.`")) break;
            Expr *f       = ast_expr(p->a, EX_FIELD, span_join(e->span, id.span));
            f->field.base = e;
            f->field.name = fname;
            e              = f;
            continue;
        }
        if (p_check(p, TK_LPAREN)) {
            Token  lp = p_next(p);
            ArgVec args = {0};
            p_skip_newlines(p);
            if (!p_check(p, TK_RPAREN)) {
                for (;;) {
                    p_skip_newlines(p);
                    Arg  arg  = {0};
                    Token ct  = p_peek(p);
                    if (ct.kind == TK_INOUT) {
                        p_next(p);
                        arg.conv = CONV_INOUT;
                    } else if (ct.kind == TK_SINK) {
                        p_next(p);
                        arg.conv = CONV_SINK;
                    } else if (ct.kind == TK_SET) {
                        p_next(p);
                        arg.conv = CONV_SET;
                    }
                    arg.value = parse_expr(p);
                    if (!arg.value) break;
                    arg.span = span_join(ct.span, arg.value->span);
                    vec_push(p->a, args, arg);
                    p_skip_newlines(p);
                    if (!p_accept(p, TK_COMMA)) break;
                    p_skip_newlines(p);
                    if (p_check(p, TK_RPAREN)) break; /* trailing comma */
                }
            }
            p_skip_newlines(p);
            Token rp = p_peek(p);
            p_expect(p, TK_RPAREN, "to close a call");
            Expr *c        = ast_expr(p->a, EX_CALL, span_join(e->span, rp.span));
            c->call.callee = e;
            c->call.args   = args;
            e              = c;
            (void)lp;
            continue;
        }
        if (p_check(p, TK_LBRACKET)) {
            p_next(p);
            p_skip_newlines(p);
            Expr *idx = parse_expr(p);
            p_skip_newlines(p);
            Token rb = p_peek(p);
            p_expect(p, TK_RBRACKET, "to close an index");
            if (!idx) break;
            Expr *ix        = ast_expr(p->a, EX_INDEX, span_join(e->span, rb.span));
            ix->index.base  = e;
            ix->index.index = idx;
            e               = ix;
            continue;
        }
        if (p_check(p, TK_AS)) {
            p_next(p);
            TypeExpr *ty = parse_type(p);
            if (!ty) break;
            Expr *c        = ast_expr(p->a, EX_CAST, span_join(e->span, ty->span));
            c->cast.value  = e;
            c->cast.type   = ty;
            e              = c;
            continue;
        }
        break;
    }
    return e;
}

/* `Point{ x: 1, y: 2 }` — only reachable when struct literals are enabled. */
static Expr *parse_struct_lit(P *p, Expr *path_expr) {
    Token lb = p_next(p); /* { */
    (void)lb;

    TypeExpr *ty = ast_type(p->a, TE_PATH, path_expr->span);
    /* Rebuild the dotted path from the field-access chain the postfix parser
     * would otherwise have produced. */
    Expr *cur = path_expr;
    StrVec rev = {0};
    while (cur->kind == EX_FIELD) {
        vec_push(p->a, rev, cur->field.name);
        cur = cur->field.base;
    }
    if (cur->kind == EX_PATH && cur->path.segs.len > 0)
        vec_push(p->a, rev, cur->path.segs.data[0]);
    for (uint32_t i = rev.len; i > 0; i--) vec_push(p->a, ty->segs, rev.data[i - 1]);

    FieldInitVec fields = {0};
    p_skip_newlines(p);
    while (!p_check(p, TK_RBRACE) && !p_check(p, TK_EOF)) {
        FieldInit fi = {0};
        Token     id = p_peek(p);
        if (!p_member_name(p, &fi.name, "in a struct literal field")) break;
        if (!p_expect(p, TK_COLON, "after a struct literal field name")) break;
        fi.value = parse_expr(p);
        if (!fi.value) break;
        fi.span = span_join(id.span, fi.value->span);
        vec_push(p->a, fields, fi);
        p_skip_newlines(p);
        if (!p_accept(p, TK_COMMA)) break;
        p_skip_newlines(p);
    }
    p_skip_newlines(p);
    Token rb = p_peek(p);
    p_expect(p, TK_RBRACE, "to close a struct literal");

    Expr *e               = ast_expr(p->a, EX_STRUCT_LIT, span_join(path_expr->span, rb.span));
    e->struct_lit.type    = ty;
    e->struct_lit.fields  = fields;
    return e;
}

static Expr *parse_if(P *p) {
    Token kw = p_next(p); /* if */

    bool saved       = p->no_struct_lit;
    p->no_struct_lit = true;
    Expr *cond       = parse_expr(p);
    p->no_struct_lit = saved;

    Expr *then_blk = parse_block(p);
    Expr *else_blk = NULL;
    if (p_check(p, TK_ELSE)) {
        p_next(p);
        else_blk = p_check(p, TK_IF) ? parse_if(p) : parse_block(p);
    }

    Span  end = else_blk ? else_blk->span : (then_blk ? then_blk->span : kw.span);
    Expr *e   = ast_expr(p->a, EX_IF, span_join(kw.span, end));
    e->if_expr.cond     = cond;
    e->if_expr.then_blk = then_blk;
    e->if_expr.else_blk = else_blk;
    return e;
}

static Expr *parse_unsafe(P *p) {
    Token at = p_next(p); /* @ */
    Token id = p_peek(p);
    if (!p_expect(p, TK_IDENT, "after `@`")) return NULL;
    if (!str_eq_c(id.text, "unsafe")) {
        diag_error(p->d, 204, id.span,
                   "`@%.*s` is not valid here; only `@unsafe(...)` may appear in an expression",
                   (int)id.text.len, id.text.ptr);
    }
    Str cap = STR_EMPTY;
    if (p_accept(p, TK_LPAREN)) {
        Token c = p_peek(p);
        if (p_expect(p, TK_IDENT, "as an @unsafe capability")) cap = c.text;
        p_expect(p, TK_RPAREN, "to close @unsafe");
    } else {
        Diag *dg = diag_error(p->d, 204, id.span, "`@unsafe` requires a capability");
        diag_help(dg, "write one of @unsafe(raw_ptr), @unsafe(unchecked_index), "
                      "@unsafe(ffi) or @unsafe(transmute)");
    }
    Expr *body = parse_block(p);
    if (!body) return NULL;
    Expr *e                = ast_expr(p->a, EX_UNSAFE, span_join(at.span, body->span));
    e->unsafe_expr.capability = cap;
    e->unsafe_expr.body       = body;
    return e;
}

static Expr *parse_primary(P *p) {
    Token t = p_peek(p);

    switch (t.kind) {
        case TK_INT: {
            p_next(p);
            Expr *e            = ast_expr(p->a, EX_INT, t.span);
            e->int_lit.val     = t.ival;
            e->int_lit.suffix  = t.suffix;
            return e;
        }
        case TK_FLOAT: {
            p_next(p);
            Expr *e             = ast_expr(p->a, EX_FLOAT, t.span);
            e->float_lit.val    = t.fval;
            e->float_lit.suffix = t.suffix;
            return e;
        }
        case TK_STRING: {
            p_next(p);
            Expr *e     = ast_expr(p->a, EX_STR, t.span);
            e->str_lit  = t.text;
            return e;
        }
        case TK_CHAR: {
            p_next(p);
            Expr *e     = ast_expr(p->a, EX_CHAR, t.span);
            e->char_lit = (uint32_t)t.ival;
            return e;
        }
        case TK_TRUE:
        case TK_FALSE: {
            p_next(p);
            Expr *e     = ast_expr(p->a, EX_BOOL, t.span);
            e->bool_lit = (t.kind == TK_TRUE);
            return e;
        }
        case TK_SELF: {
            p_next(p);
            return ast_expr(p->a, EX_SELF, t.span);
        }
        case TK_ERROR: {
            p_next(p);
            p_expect(p, TK_DOT, "after `error`");
            Token id = p_peek(p);
            if (!p_expect(p, TK_IDENT, "as an error name")) return NULL;
            Expr *e      = ast_expr(p->a, EX_ERROR_LIT, span_join(t.span, id.span));
            e->error_lit = id.text;
            return e;
        }
        case TK_IDENT: {
            p_next(p);
            Expr *e = ast_expr(p->a, EX_PATH, t.span);
            vec_push(p->a, e->path.segs, t.text);
            if (p_check(p, TK_LBRACE) && !p->no_struct_lit) return parse_struct_lit(p, e);
            return e;
        }
        case TK_LPAREN: {
            p_next(p);
            p_skip_newlines(p);
            bool saved       = p->no_struct_lit;
            p->no_struct_lit = false; /* parentheses re-enable struct literals */
            Expr *inner      = parse_expr(p);
            p->no_struct_lit = saved;
            p_skip_newlines(p);
            p_expect(p, TK_RPAREN, "to close a parenthesised expression");
            return inner;
        }
        case TK_LBRACKET: {
            p_next(p);
            ExprVec elems = {0};
            p_skip_newlines(p);
            while (!p_check(p, TK_RBRACKET) && !p_check(p, TK_EOF)) {
                Expr *el = parse_expr(p);
                if (!el) break;
                vec_push(p->a, elems, el);
                p_skip_newlines(p);
                if (!p_accept(p, TK_COMMA)) break;
                p_skip_newlines(p);
            }
            Token rb = p_peek(p);
            p_expect(p, TK_RBRACKET, "to close an array literal");
            Expr *e            = ast_expr(p->a, EX_ARRAY_LIT, span_join(t.span, rb.span));
            e->array_lit.elems = elems;
            return e;
        }
        case TK_IF: return parse_if(p);
        case TK_LBRACE: return parse_block(p);
        case TK_AT: return parse_unsafe(p);
        default: {
            diag_error(p->d, 202, t.span, "expected an expression, found `%s`",
                       tok_name(t.kind));
            return NULL;
        }
    }
}
