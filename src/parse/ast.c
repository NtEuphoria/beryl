#include "ast.h"

const char *conv_name(Conv c) {
    switch (c) {
        case CONV_LET: return "let";
        case CONV_INOUT: return "inout";
        case CONV_SINK: return "sink";
        case CONV_SET: return "set";
        default: return "?";
    }
}

Expr *ast_expr(Arena *a, ExprKind k, Span s) {
    Expr *e = ARENA_NEW(a, Expr);
    e->kind = k;
    e->span = s;
    return e;
}

Stmt *ast_stmt(Arena *a, StmtKind k, Span s) {
    Stmt *st = ARENA_NEW(a, Stmt);
    st->kind = k;
    st->span = s;
    return st;
}

Item *ast_item(Arena *a, ItemKind k, Span s) {
    Item *it = ARENA_NEW(a, Item);
    it->kind = k;
    it->span = s;
    return it;
}

TypeExpr *ast_type(Arena *a, TypeExprKind k, Span s) {
    TypeExpr *t = ARENA_NEW(a, TypeExpr);
    t->kind     = k;
    t->span     = s;
    return t;
}

Str path_str(Arena *a, StrVec segs) {
    SB sb;
    sb_init(&sb, a);
    for (uint32_t i = 0; i < segs.len; i++) {
        if (i) sb_char(&sb, '.');
        sb_str(&sb, segs.data[i]);
    }
    return sb_finish(&sb);
}
