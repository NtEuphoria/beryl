/* parser.c — parser state, type syntax, statements and blocks.
 * Items and the file-level entry point live in parser_item.c;
 * expressions live in parser_expr.c.
 */
#include "parser.h"

/* ---- state helpers ----------------------------------------------------- */

Token p_peek(P *p) { return p->toks.data[p->pos]; }

Token p_peek2(P *p) {
    uint32_t i = (p->pos + 1 < p->toks.len) ? p->pos + 1 : p->toks.len - 1;
    return p->toks.data[i];
}

TokKind p_kind(P *p) { return p_peek(p).kind; }

Token p_next(P *p) {
    Token t = p_peek(p);
    if (t.kind != TK_EOF) p->pos++;
    return t;
}

bool p_check(P *p, TokKind k) { return p_kind(p) == k; }

bool p_accept(P *p, TokKind k) {
    if (!p_check(p, k)) return false;
    p_next(p);
    return true;
}

bool p_expect(P *p, TokKind k, const char *ctx) {
    if (p_accept(p, k)) return true;
    /* One diagnostic per position: a cascade from a single confusion helps
     * nobody, and the recovery below will move us along regardless. */
    if (p->pos != p->last_error_pos) {
        p->last_error_pos = p->pos;
        Token t           = p_peek(p);
        diag_error(p->d, 201, t.span, "expected `%s` %s, found `%s`", tok_name(k), ctx,
                   tok_name(t.kind));
    }
    return false;
}

void p_skip_newlines(P *p) {
    while (p_check(p, TK_NEWLINE) || p_check(p, TK_DOC)) p_next(p);
}

Span p_span_from(P *p, uint32_t start_pos) {
    Span a = p->toks.data[start_pos].span;
    Span b = p->toks.data[p->pos > start_pos ? p->pos - 1 : start_pos].span;
    return span_join(a, b);
}

/* Skips to the next plausible statement boundary after an error. */
static void sync_stmt(P *p) {
    int depth = 0;
    while (!p_check(p, TK_EOF)) {
        TokKind k = p_kind(p);
        if (k == TK_LBRACE) depth++;
        if (k == TK_RBRACE) {
            if (depth == 0) return;
            depth--;
        }
        if (k == TK_NEWLINE && depth == 0) {
            p_next(p);
            return;
        }
        p_next(p);
    }
}

/* ---- types ------------------------------------------------------------- */

/* `List<List<i32>>` closes with a single `>>` token, so the inner close has to
 * split it rather than demand a `>`. */
static void expect_type_gt(P *p) {
    if (p_check(p, TK_SHR)) {
        Token *t = &p->toks.data[p->pos];
        t->kind        = TK_GT;
        t->span.offset = t->span.offset + 1;
        t->span.len    = 1;
        return;
    }
    p_expect(p, TK_GT, "to close generic arguments");
}

TypeExpr *parse_type(P *p) {
    Token t = p_peek(p);

    if (t.kind == TK_BANG) {
        p_next(p);
        TypeExpr *inner = parse_type(p);
        if (!inner) return NULL;
        TypeExpr *te = ast_type(p->a, TE_ERRUNION, span_join(t.span, inner->span));
        te->elem     = inner;
        return te;
    }

    TypeExpr *base = NULL;

    if (t.kind == TK_LBRACKET) {
        p_next(p);
        TypeExpr *elem = parse_type(p);
        if (!elem) return NULL;
        p_expect(p, TK_SEMI, "between the element type and length of an array type");
        Expr *len = parse_expr(p);
        Token rb  = p_peek(p);
        p_expect(p, TK_RBRACKET, "to close an array type");
        base       = ast_type(p->a, TE_ARRAY, span_join(t.span, rb.span));
        base->elem = elem;
        base->len  = len;
    } else if (t.kind == TK_IDENT) {
        base = ast_type(p->a, TE_PATH, t.span);
        p_next(p);
        vec_push(p->a, base->segs, t.text);
        while (p_check(p, TK_DOT) && p_peek2(p).kind == TK_IDENT) {
            p_next(p);
            Token seg = p_next(p);
            vec_push(p->a, base->segs, seg.text);
            base->span = span_join(base->span, seg.span);
        }
        if (p_accept(p, TK_LT)) {
            for (;;) {
                TypeExpr *arg = parse_type(p);
                if (!arg) break;
                vec_push(p->a, base->args, arg);
                if (!p_accept(p, TK_COMMA)) break;
            }
            expect_type_gt(p);
            base->span = span_join(base->span, p_peek(p).span);
        }
    } else {
        diag_error(p->d, 203, t.span, "expected a type, found `%s`", tok_name(t.kind));
        return NULL;
    }

    while (p_check(p, TK_QUESTION)) {
        Token q      = p_next(p);
        TypeExpr *op = ast_type(p->a, TE_OPTION, span_join(base->span, q.span));
        op->elem     = base;
        base         = op;
    }
    return base;
}

/* ---- statements -------------------------------------------------------- */

static bool is_assign_op(TokKind k) {
    switch (k) {
        case TK_ASSIGN:
        case TK_PLUSEQ:
        case TK_MINUSEQ:
        case TK_STAREQ:
        case TK_SLASHEQ:
        case TK_PERCENTEQ: return true;
        default: return false;
    }
}

static Stmt *parse_let(P *p, bool is_var) {
    Token kw = p_next(p);
    Token id = p_peek(p);
    if (!p_expect(p, TK_IDENT, is_var ? "after `var`" : "after `let`")) return NULL;

    TypeExpr *ty = NULL;
    if (p_accept(p, TK_COLON)) ty = parse_type(p);

    Expr *init = NULL;
    if (p_accept(p, TK_ASSIGN)) init = parse_expr(p);

    Span  end = init ? init->span : (ty ? ty->span : id.span);
    Stmt *st  = ast_stmt(p->a, ST_LET, span_join(kw.span, end));
    st->let.name   = id.text;
    st->let.type   = ty;
    st->let.init   = init;
    st->let.is_var = is_var;
    return st;
}

static Stmt *parse_while(P *p) {
    Token kw         = p_next(p);
    bool  saved      = p->no_struct_lit;
    p->no_struct_lit = true;
    Expr *cond       = parse_expr(p);
    p->no_struct_lit = saved;
    Expr *body       = parse_block(p);
    Stmt *st         = ast_stmt(p->a, ST_WHILE, span_join(kw.span, body ? body->span : kw.span));
    st->while_st.cond = cond;
    st->while_st.body = body;
    return st;
}

static Stmt *parse_for(P *p) {
    Token kw = p_next(p);
    Token id = p_peek(p);
    if (!p_expect(p, TK_IDENT, "as the loop variable")) return NULL;
    p_expect(p, TK_IN, "after the loop variable");

    bool saved       = p->no_struct_lit;
    p->no_struct_lit = true;
    Expr *iter       = parse_expr(p);
    p->no_struct_lit = saved;

    Expr *body      = parse_block(p);
    Stmt *st        = ast_stmt(p->a, ST_FOR, span_join(kw.span, body ? body->span : kw.span));
    st->for_st.var  = id.text;
    st->for_st.iter = iter;
    st->for_st.body = body;
    return st;
}

static Stmt *parse_stmt(P *p) {
    Token t = p_peek(p);

    switch (t.kind) {
        case TK_LET: return parse_let(p, false);
        case TK_VAR: return parse_let(p, true);
        case TK_WHILE: return parse_while(p);
        case TK_FOR: return parse_for(p);
        case TK_RETURN: {
            p_next(p);
            Expr *v = NULL;
            if (!p_check(p, TK_NEWLINE) && !p_check(p, TK_RBRACE) && !p_check(p, TK_EOF))
                v = parse_expr(p);
            Stmt *st = ast_stmt(p->a, ST_RETURN, span_join(t.span, v ? v->span : t.span));
            st->expr = v;
            return st;
        }
        case TK_BREAK: p_next(p); return ast_stmt(p->a, ST_BREAK, t.span);
        case TK_CONTINUE: p_next(p); return ast_stmt(p->a, ST_CONTINUE, t.span);
        case TK_DEFER: {
            p_next(p);
            Expr *v  = parse_expr(p);
            Stmt *st = ast_stmt(p->a, ST_DEFER, span_join(t.span, v ? v->span : t.span));
            st->expr = v;
            return st;
        }
        default: break;
    }

    Expr *e = parse_expr(p);
    if (!e) return NULL;

    if (is_assign_op(p_kind(p))) {
        Token op  = p_next(p);
        Expr *val = parse_expr(p);
        if (!val) return NULL;
        Stmt *st           = ast_stmt(p->a, ST_ASSIGN, span_join(e->span, val->span));
        st->assign.target  = e;
        st->assign.op      = op.kind;
        st->assign.value   = val;
        return st;
    }

    Stmt *st = ast_stmt(p->a, ST_EXPR, e->span);
    st->expr = e;
    return st;
}

Expr *parse_block(P *p) {
    Token lb = p_peek(p);
    if (!p_expect(p, TK_LBRACE, "to open a block")) return NULL;

    StmtVec stmts = {0};
    p_skip_newlines(p);

    while (!p_check(p, TK_RBRACE) && !p_check(p, TK_EOF)) {
        uint32_t before = p->pos;

        Stmt *s = parse_stmt(p);
        if (s) vec_push(p->a, stmts, s);

        if (p_check(p, TK_RBRACE) || p_check(p, TK_EOF)) break;

        if (!p_accept(p, TK_NEWLINE)) {
            if (p->pos != p->last_error_pos) {
                p->last_error_pos = p->pos;
                Diag *dg          = diag_error(p->d, 201, p_peek(p).span,
                                               "expected end of statement, found `%s`",
                                               tok_name(p_kind(p)));
                diag_help(dg, "statements end at a line break; put this on its own line");
            }
            sync_stmt(p);
        }

        p_skip_newlines(p);

        if (p->pos == before) p_next(p); /* guarantee forward progress */
    }

    Token rb = p_peek(p);
    p_expect(p, TK_RBRACE, "to close a block");

    Expr *e        = ast_expr(p->a, EX_BLOCK, span_join(lb.span, rb.span));
    e->block.stmts = stmts;
    return e;
}
