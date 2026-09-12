/* parser.c — parser state, type syntax, statements and blocks.
 * Items and the file-level entry point live in parser_item.c;
 * expressions live in parser_expr.c.
 */
#include "parser.h"

static _Noreturn void resource_limit(P *p, Span at, const char *what, uint32_t limit) {
    Diag *dg = diag_error(p->d, 210, at, "parser resource limit exceeded: %s (limit %u)",
                          what, limit);
    diag_help(dg, "split this expression or declaration into smaller parts, or split the source file into modules");
    longjmp(p->resource_exit, 1);
}

void p_work(P *p) {
    if (p->work >= PARSE_MAX_WORK)
        resource_limit(p, p_peek(p).span, "parser work", PARSE_MAX_WORK);
    p->work++;
}

void p_enter(P *p) {
    p_work(p);
    if (p->recursion >= PARSE_MAX_RECURSION)
        resource_limit(p, p_peek(p).span, "recursive parse depth", PARSE_MAX_RECURSION);
    p->recursion++;
}

void p_leave(P *p) { p->recursion--; }

void p_validate_tokens(P *p) {
    if (p->toks.len > PARSE_MAX_TOKENS)
        resource_limit(p, SPAN_NONE, "tokens per file", PARSE_MAX_TOKENS);
    if (!p->toks.len || !p->toks.data || p->toks.len > p->toks.cap ||
        p->toks.data[p->toks.len - 1].kind != TK_EOF) {
        diag_error(p->d, 210, SPAN_NONE, "invalid token stream supplied to parser");
        longjmp(p->resource_exit, 1);
    }
    for (uint32_t i = 0; i < p->toks.len; i++) {
        if ((uint32_t)p->toks.data[i].kind >= TK_COUNT ||
            (p->toks.data[i].kind == TK_EOF && i + 1 != p->toks.len)) {
            diag_error(p->d, 210, p->toks.data[i].span, "invalid token stream supplied to parser");
            longjmp(p->resource_exit, 1);
        }
    }
}

/* ---- state helpers ----------------------------------------------------- */

Token p_peek(P *p) { return p->toks.data[p->pos]; }

Token p_peek2(P *p) {
    uint32_t i = (p->pos + 1 < p->toks.len) ? p->pos + 1 : p->toks.len - 1;
    return p->toks.data[i];
}

TokKind p_kind(P *p) { return p_peek(p).kind; }

Token p_next(P *p) {
    p_work(p);
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

/* Accepts a field or method name. A reserved word is fine here: `list.set(i, v)`
 * is unambiguous, because nothing but a name can follow a `.`. */
bool p_member_name(P *p, Str *out, const char *ctx) {
    Token t = p_peek(p);
    if (t.kind == TK_IDENT || tok_is_keyword(t.kind)) {
        p_next(p);
        *out = t.text;
        return true;
    }
    return p_expect(p, TK_IDENT, ctx);
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

static TypeExpr *parse_type_inner(P *p);
TypeExpr *parse_type(P *p) {
    p_enter(p);
    TypeExpr *result = parse_type_inner(p);
    p_leave(p);
    return result;
}

static TypeExpr *parse_type_inner(P *p) {
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

static Expr *parse_block_inner(P *p);
Expr *parse_block(P *p) {
    p_enter(p);
    Expr *result = parse_block_inner(p);
    p_leave(p);
    return result;
}

static Expr *parse_block_inner(P *p) {
    Token lb = p_peek(p);
    if (!p_expect(p, TK_LBRACE, "to open a block")) return NULL;

    StmtVec stmts = {0};
    p_skip_newlines(p);

    while (!p_check(p, TK_RBRACE) && !p_check(p, TK_EOF)) {
        uint32_t before = p->pos;

        Stmt *s = parse_stmt(p);
        if (s) vec_push(p->a, stmts, s);

        if (p_check(p, TK_RBRACE) || p_check(p, TK_EOF)) break;

        /* A line break terminates a statement even when the lexer suppressed
         * the virtual newline, which it does after any token that cannot end
         * an expression — `>` closing a generic type, for instance. */
        if (!p_accept(p, TK_NEWLINE) && !p_peek(p).nl_before) {
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

/* Iterative validation also catches deep trees built by flat parsing loops:
 * left-associative operators, postfix chains and repeated optional types.
 * No recursive compiler consumer sees an over-limit tree. */
typedef enum { SHAPE_ITEM, SHAPE_STMT, SHAPE_EXPR, SHAPE_TYPE } ShapeKind;
typedef struct { ShapeKind kind; const void *node; uint32_t depth; } Shape;
typedef VEC(Shape) ShapeVec;

static Span shape_span(Shape s) {
    switch (s.kind) {
        case SHAPE_ITEM: return ((const Item *)s.node)->span;
        case SHAPE_STMT: return ((const Stmt *)s.node)->span;
        case SHAPE_EXPR: return ((const Expr *)s.node)->span;
        case SHAPE_TYPE: return ((const TypeExpr *)s.node)->span;
    }
    return SPAN_NONE;
}

static void shape_push(P *p, ShapeVec *stack, uint32_t *nodes, ShapeKind kind,
                       const void *node, uint32_t depth) {
    if (!node) return;
    Shape s = {kind, node, depth};
    if (depth > PARSE_MAX_AST_DEPTH)
        resource_limit(p, shape_span(s), "syntax tree depth", PARSE_MAX_AST_DEPTH);
    if (*nodes >= PARSE_MAX_AST_NODES)
        resource_limit(p, shape_span(s), "syntax tree nodes", PARSE_MAX_AST_NODES);
    (*nodes)++;
    vec_push(p->a, *stack, s);
}

void p_validate_shape(P *p, Module *module) {
    ShapeVec stack = {0};
    uint32_t nodes = 0;
    for (uint32_t i = 0; i < module->items.len; i++)
        shape_push(p, &stack, &nodes, SHAPE_ITEM, module->items.data[i], 1);
    while (stack.len) {
        p_work(p);
        Shape s = vec_pop(stack);
        uint32_t depth = s.depth + 1;
#define CHILD(kind_, node_) shape_push(p, &stack, &nodes, (kind_), (node_), depth)
        switch (s.kind) {
            case SHAPE_ITEM: {
                const Item *it = s.node;
                switch (it->kind) {
                    case IT_FN:
                        CHILD(SHAPE_TYPE, it->fn.ret); CHILD(SHAPE_EXPR, it->fn.body);
                        for (uint32_t i=0;i<it->fn.params.len;i++) {
                            CHILD(SHAPE_TYPE,it->fn.params.data[i].type);
                            CHILD(SHAPE_EXPR,it->fn.params.data[i].deflt);
                        }
                        break;
                    case IT_STRUCT:
                        for (uint32_t i=0;i<it->strukt.fields.len;i++) {
                            CHILD(SHAPE_TYPE,it->strukt.fields.data[i].type);
                            CHILD(SHAPE_EXPR,it->strukt.fields.data[i].deflt);
                        }
                        break;
                    case IT_ENUM:
                        for (uint32_t i=0;i<it->enom.variants.len;i++) CHILD(SHAPE_EXPR,it->enom.variants.data[i].value);
                        break;
                    case IT_CONST: CHILD(SHAPE_TYPE,it->konst.type); CHILD(SHAPE_EXPR,it->konst.value); break;
                    case IT_TEST: CHILD(SHAPE_EXPR,it->test.body); break;
                    case IT_TRAIT:
                        for (uint32_t i=0;i<it->trait.methods.len;i++) CHILD(SHAPE_ITEM,it->trait.methods.data[i]);
                        break;
                    case IT_USE: break;
                }
                break;
            }
            case SHAPE_STMT: {
                const Stmt *st = s.node;
                switch (st->kind) {
                    case ST_LET: CHILD(SHAPE_TYPE,st->let.type); CHILD(SHAPE_EXPR,st->let.init); break;
                    case ST_EXPR: case ST_RETURN: case ST_DEFER: CHILD(SHAPE_EXPR,st->expr); break;
                    case ST_ASSIGN: CHILD(SHAPE_EXPR,st->assign.target); CHILD(SHAPE_EXPR,st->assign.value); break;
                    case ST_WHILE: CHILD(SHAPE_EXPR,st->while_st.cond); CHILD(SHAPE_EXPR,st->while_st.body); break;
                    case ST_FOR: CHILD(SHAPE_EXPR,st->for_st.iter); CHILD(SHAPE_EXPR,st->for_st.body); break;
                    case ST_BREAK: case ST_CONTINUE: break;
                }
                break;
            }
            case SHAPE_TYPE: {
                const TypeExpr *t = s.node;
                CHILD(SHAPE_TYPE,t->elem); CHILD(SHAPE_EXPR,t->len);
                for (uint32_t i=0;i<t->args.len;i++) CHILD(SHAPE_TYPE,t->args.data[i]);
                break;
            }
            case SHAPE_EXPR: {
                const Expr *e = s.node;
                switch (e->kind) {
                    case EX_PATH:
                        for (uint32_t i=0;i<e->path.targs.len;i++) CHILD(SHAPE_TYPE,e->path.targs.data[i]);
                        break;
                    case EX_UNARY: CHILD(SHAPE_EXPR,e->unary.operand); break;
                    case EX_BINARY: CHILD(SHAPE_EXPR,e->binary.lhs); CHILD(SHAPE_EXPR,e->binary.rhs); break;
                    case EX_CALL:
                        CHILD(SHAPE_EXPR,e->call.callee);
                        for (uint32_t i=0;i<e->call.args.len;i++) CHILD(SHAPE_EXPR,e->call.args.data[i].value);
                        break;
                    case EX_FIELD: CHILD(SHAPE_EXPR,e->field.base); break;
                    case EX_INDEX: CHILD(SHAPE_EXPR,e->index.base); CHILD(SHAPE_EXPR,e->index.index); break;
                    case EX_CAST: CHILD(SHAPE_EXPR,e->cast.value); CHILD(SHAPE_TYPE,e->cast.type); break;
                    case EX_STRUCT_LIT:
                        CHILD(SHAPE_TYPE,e->struct_lit.type);
                        for (uint32_t i=0;i<e->struct_lit.fields.len;i++) CHILD(SHAPE_EXPR,e->struct_lit.fields.data[i].value);
                        break;
                    case EX_ARRAY_LIT:
                        for (uint32_t i=0;i<e->array_lit.elems.len;i++) CHILD(SHAPE_EXPR,e->array_lit.elems.data[i]);
                        break;
                    case EX_IF: CHILD(SHAPE_EXPR,e->if_expr.cond); CHILD(SHAPE_EXPR,e->if_expr.then_blk); CHILD(SHAPE_EXPR,e->if_expr.else_blk); break;
                    case EX_BLOCK:
                        for (uint32_t i=0;i<e->block.stmts.len;i++) CHILD(SHAPE_STMT,e->block.stmts.data[i]);
                        break;
                    case EX_TRY: CHILD(SHAPE_EXPR,e->try_expr.inner); break;
                    case EX_CATCH: CHILD(SHAPE_EXPR,e->catch_expr.value); CHILD(SHAPE_EXPR,e->catch_expr.handler); break;
                    case EX_ORELSE: CHILD(SHAPE_EXPR,e->orelse_expr.value); CHILD(SHAPE_EXPR,e->orelse_expr.fallback); break;
                    case EX_UNSAFE: CHILD(SHAPE_EXPR,e->unsafe_expr.body); break;
                    case EX_RANGE: CHILD(SHAPE_EXPR,e->range.lo); CHILD(SHAPE_EXPR,e->range.hi); break;
                    case EX_INT: case EX_FLOAT: case EX_STR: case EX_CHAR: case EX_BOOL: case EX_SELF: case EX_ERROR_LIT: break;
                }
                break;
            }
        }
#undef CHILD
    }
}
