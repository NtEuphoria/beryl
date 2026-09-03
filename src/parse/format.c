/* format.c — canonical Beryl source, as written by `beryl fmt`.
 *
 * Formatting is idempotent and round-trips: reparsing the output yields an
 * identical AST. Parentheses are emitted only where precedence requires them,
 * which is what makes the round-trip test meaningful rather than trivial.
 */
#include "print.h"

#define IND "    "

typedef struct {
    SB  sb;
    int depth;
} F;

static void f_nl(F *f) {
    sb_char(&f->sb, '\n');
    for (int i = 0; i < f->depth; i++) sb_cstr(&f->sb, IND);
}

static int prec(TokKind k) {
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

static void f_expr(F *f, const Expr *e, int parent_prec);
static void f_block(F *f, const Expr *b);

static void f_type(F *f, const TypeExpr *t) {
    if (!t) return;
    switch (t->kind) {
        case TE_PATH:
            for (uint32_t i = 0; i < t->segs.len; i++) {
                if (i) sb_char(&f->sb, '.');
                sb_str(&f->sb, t->segs.data[i]);
            }
            if (t->args.len) {
                sb_char(&f->sb, '<');
                for (uint32_t i = 0; i < t->args.len; i++) {
                    if (i) sb_cstr(&f->sb, ", ");
                    f_type(f, t->args.data[i]);
                }
                sb_char(&f->sb, '>');
            }
            break;
        case TE_ARRAY:
            sb_char(&f->sb, '[');
            f_type(f, t->elem);
            sb_cstr(&f->sb, "; ");
            f_expr(f, t->len, 0);
            sb_char(&f->sb, ']');
            break;
        case TE_OPTION:
            f_type(f, t->elem);
            sb_char(&f->sb, '?');
            break;
        case TE_ERRUNION:
            sb_char(&f->sb, '!');
            f_type(f, t->elem);
            break;
        default: break;
    }
}

static void f_stmt(F *f, const Stmt *s);

static void f_expr(F *f, const Expr *e, int parent_prec) {
    if (!e) return;
    switch (e->kind) {
        case EX_INT:
            sb_fmt(&f->sb, "%llu", (unsigned long long)e->int_lit.val);
            if (!str_empty(e->int_lit.suffix)) sb_str(&f->sb, e->int_lit.suffix);
            break;
        case EX_FLOAT:
            sb_fmt(&f->sb, "%g", e->float_lit.val);
            if (!str_empty(e->float_lit.suffix)) sb_str(&f->sb, e->float_lit.suffix);
            break;
        case EX_STR: {
            sb_char(&f->sb, '"');
            for (uint32_t i = 0; i < e->str_lit.len; i++) {
                char c = e->str_lit.ptr[i];
                switch (c) {
                    case '\n': sb_cstr(&f->sb, "\\n"); break;
                    case '\t': sb_cstr(&f->sb, "\\t"); break;
                    case '\r': sb_cstr(&f->sb, "\\r"); break;
                    case '"': sb_cstr(&f->sb, "\\\""); break;
                    case '\\': sb_cstr(&f->sb, "\\\\"); break;
                    default: sb_char(&f->sb, c); break;
                }
            }
            sb_char(&f->sb, '"');
            break;
        }
        case EX_CHAR: sb_fmt(&f->sb, "'%c'", (char)e->char_lit); break;
        case EX_BOOL: sb_cstr(&f->sb, e->bool_lit ? "true" : "false"); break;
        case EX_SELF: sb_cstr(&f->sb, "self"); break;
        case EX_PATH:
            for (uint32_t i = 0; i < e->path.segs.len; i++) {
                if (i) sb_char(&f->sb, '.');
                sb_str(&f->sb, e->path.segs.data[i]);
            }
            break;
        case EX_UNARY:
            sb_cstr(&f->sb, tok_name(e->unary.op));
            f_expr(f, e->unary.operand, 11);
            break;
        case EX_BINARY: {
            int p     = prec(e->binary.op);
            bool wrap = p < parent_prec;
            if (wrap) sb_char(&f->sb, '(');
            f_expr(f, e->binary.lhs, p);
            sb_fmt(&f->sb, " %s ", tok_name(e->binary.op));
            f_expr(f, e->binary.rhs, p + 1);
            if (wrap) sb_char(&f->sb, ')');
            break;
        }
        case EX_CALL:
            f_expr(f, e->call.callee, 12);
            sb_char(&f->sb, '(');
            for (uint32_t i = 0; i < e->call.args.len; i++) {
                if (i) sb_cstr(&f->sb, ", ");
                Arg ar = e->call.args.data[i];
                if (ar.conv != CONV_LET) sb_fmt(&f->sb, "%s ", conv_name(ar.conv));
                f_expr(f, ar.value, 0);
            }
            sb_char(&f->sb, ')');
            break;
        case EX_FIELD:
            f_expr(f, e->field.base, 12);
            sb_char(&f->sb, '.');
            sb_str(&f->sb, e->field.name);
            break;
        case EX_INDEX:
            f_expr(f, e->index.base, 12);
            sb_char(&f->sb, '[');
            f_expr(f, e->index.index, 0);
            sb_char(&f->sb, ']');
            break;
        case EX_CAST:
            f_expr(f, e->cast.value, 12);
            sb_cstr(&f->sb, " as ");
            f_type(f, e->cast.type);
            break;
        case EX_STRUCT_LIT:
            f_type(f, e->struct_lit.type);
            sb_char(&f->sb, '{');
            for (uint32_t i = 0; i < e->struct_lit.fields.len; i++) {
                if (i) sb_char(&f->sb, ',');
                sb_char(&f->sb, ' ');
                FieldInit fi = e->struct_lit.fields.data[i];
                sb_str(&f->sb, fi.name);
                sb_cstr(&f->sb, ": ");
                f_expr(f, fi.value, 0);
            }
            sb_cstr(&f->sb, " }");
            break;
        case EX_ARRAY_LIT:
            sb_char(&f->sb, '[');
            for (uint32_t i = 0; i < e->array_lit.elems.len; i++) {
                if (i) sb_cstr(&f->sb, ", ");
                f_expr(f, e->array_lit.elems.data[i], 0);
            }
            sb_char(&f->sb, ']');
            break;
        case EX_IF:
            sb_cstr(&f->sb, "if ");
            f_expr(f, e->if_expr.cond, 0);
            sb_char(&f->sb, ' ');
            f_block(f, e->if_expr.then_blk);
            if (e->if_expr.else_blk) {
                sb_cstr(&f->sb, " else ");
                if (e->if_expr.else_blk->kind == EX_IF) f_expr(f, e->if_expr.else_blk, 0);
                else f_block(f, e->if_expr.else_blk);
            }
            break;
        case EX_BLOCK: f_block(f, e); break;
        case EX_TRY:
            sb_cstr(&f->sb, "try ");
            f_expr(f, e->try_expr.inner, 11);
            break;
        case EX_CATCH:
            f_expr(f, e->catch_expr.value, 2);
            sb_cstr(&f->sb, " catch ");
            if (!str_empty(e->catch_expr.binding)) {
                sb_char(&f->sb, '|');
                sb_str(&f->sb, e->catch_expr.binding);
                sb_cstr(&f->sb, "| ");
            }
            f_expr(f, e->catch_expr.handler, 2);
            break;
        case EX_ORELSE:
            f_expr(f, e->orelse_expr.value, 2);
            sb_cstr(&f->sb, " orelse ");
            f_expr(f, e->orelse_expr.fallback, 2);
            break;
        case EX_ERROR_LIT:
            sb_cstr(&f->sb, "error.");
            sb_str(&f->sb, e->error_lit);
            break;
        case EX_UNSAFE:
            sb_cstr(&f->sb, "@unsafe(");
            sb_str(&f->sb, e->unsafe_expr.capability);
            sb_cstr(&f->sb, ") ");
            f_block(f, e->unsafe_expr.body);
            break;
        case EX_RANGE:
            f_expr(f, e->range.lo, 2);
            sb_cstr(&f->sb, "..");
            f_expr(f, e->range.hi, 2);
            break;
        default: break;
    }
}

static void f_block(F *f, const Expr *b) {
    if (!b || b->kind != EX_BLOCK) {
        sb_cstr(&f->sb, "{ }");
        return;
    }
    if (b->block.stmts.len == 0) {
        sb_cstr(&f->sb, "{ }");
        return;
    }
    sb_char(&f->sb, '{');
    f->depth++;
    for (uint32_t i = 0; i < b->block.stmts.len; i++) {
        f_nl(f);
        f_stmt(f, b->block.stmts.data[i]);
    }
    f->depth--;
    f_nl(f);
    sb_char(&f->sb, '}');
}

static void f_stmt(F *f, const Stmt *s) {
    if (!s) return;
    switch (s->kind) {
        case ST_LET:
            sb_cstr(&f->sb, s->let.is_var ? "var " : "let ");
            sb_str(&f->sb, s->let.name);
            if (s->let.type) {
                sb_cstr(&f->sb, ": ");
                f_type(f, s->let.type);
            }
            if (s->let.init) {
                sb_cstr(&f->sb, " = ");
                f_expr(f, s->let.init, 0);
            }
            break;
        case ST_EXPR: f_expr(f, s->expr, 0); break;
        case ST_ASSIGN:
            f_expr(f, s->assign.target, 0);
            sb_fmt(&f->sb, " %s ", tok_name(s->assign.op));
            f_expr(f, s->assign.value, 0);
            break;
        case ST_WHILE:
            sb_cstr(&f->sb, "while ");
            f_expr(f, s->while_st.cond, 0);
            sb_char(&f->sb, ' ');
            f_block(f, s->while_st.body);
            break;
        case ST_FOR:
            sb_cstr(&f->sb, "for ");
            sb_str(&f->sb, s->for_st.var);
            sb_cstr(&f->sb, " in ");
            f_expr(f, s->for_st.iter, 0);
            sb_char(&f->sb, ' ');
            f_block(f, s->for_st.body);
            break;
        case ST_RETURN:
            sb_cstr(&f->sb, "return");
            if (s->expr) {
                sb_char(&f->sb, ' ');
                f_expr(f, s->expr, 0);
            }
            break;
        case ST_BREAK: sb_cstr(&f->sb, "break"); break;
        case ST_CONTINUE: sb_cstr(&f->sb, "continue"); break;
        case ST_DEFER:
            sb_cstr(&f->sb, "defer ");
            f_expr(f, s->expr, 0);
            break;
        default: break;
    }
}

static void f_doc(F *f, Str doc) {
    if (str_empty(doc)) return;
    uint32_t start = 0;
    for (uint32_t i = 0; i <= doc.len; i++) {
        if (i == doc.len || doc.ptr[i] == '\n') {
            sb_cstr(&f->sb, "//! ");
            sb_str(&f->sb, str_new(doc.ptr + start, i - start));
            f_nl(f);
            start = i + 1;
        }
    }
}

static void f_item(F *f, const Item *it) {
    f_doc(f, it->doc);
    for (uint32_t i = 0; i < it->attrs.len; i++) {
        Attr at = it->attrs.data[i];
        sb_char(&f->sb, '@');
        sb_str(&f->sb, at.name);
        if (!str_empty(at.arg)) {
            sb_char(&f->sb, '(');
            sb_str(&f->sb, at.arg);
            sb_char(&f->sb, ')');
        }
        f_nl(f);
    }
    if (it->is_pub) sb_cstr(&f->sb, "pub ");

    switch (it->kind) {
        case IT_FN: {
            sb_cstr(&f->sb, "fn ");
            if (!str_empty(it->fn.recv)) {
                sb_str(&f->sb, it->fn.recv);
                sb_char(&f->sb, '.');
            }
            sb_str(&f->sb, it->name);
            if (it->fn.generics.len) {
                sb_char(&f->sb, '<');
                for (uint32_t i = 0; i < it->fn.generics.len; i++) {
                    GenericParam g = it->fn.generics.data[i];
                    if (i) sb_cstr(&f->sb, ", ");
                    sb_str(&f->sb, g.name);
                    if (!str_empty(g.bound)) {
                        sb_cstr(&f->sb, ": ");
                        sb_str(&f->sb, g.bound);
                    }
                }
                sb_char(&f->sb, '>');
            }
            sb_char(&f->sb, '(');
            for (uint32_t i = 0; i < it->fn.params.len; i++) {
                Param pm = it->fn.params.data[i];
                if (i) sb_cstr(&f->sb, ", ");
                if (pm.conv != CONV_LET) sb_fmt(&f->sb, "%s ", conv_name(pm.conv));
                sb_str(&f->sb, pm.name);
                if (!pm.is_self && pm.type) {
                    sb_cstr(&f->sb, ": ");
                    f_type(f, pm.type);
                }
                if (pm.deflt) {
                    sb_cstr(&f->sb, " = ");
                    f_expr(f, pm.deflt, 0);
                }
            }
            sb_char(&f->sb, ')');
            if (it->fn.ret) {
                sb_cstr(&f->sb, " -> ");
                f_type(f, it->fn.ret);
            }
            sb_char(&f->sb, ' ');
            f_block(f, it->fn.body);
            break;
        }
        case IT_STRUCT: {
            sb_cstr(&f->sb, "struct ");
            sb_str(&f->sb, it->name);
            if (it->strukt.generics.len) {
                sb_char(&f->sb, '<');
                for (uint32_t i = 0; i < it->strukt.generics.len; i++) {
                    if (i) sb_cstr(&f->sb, ", ");
                    sb_str(&f->sb, it->strukt.generics.data[i].name);
                }
                sb_char(&f->sb, '>');
            }
            sb_cstr(&f->sb, " {");
            f->depth++;
            for (uint32_t i = 0; i < it->strukt.fields.len; i++) {
                Field fl = it->strukt.fields.data[i];
                f_nl(f);
                f_doc(f, fl.doc);
                sb_str(&f->sb, fl.name);
                sb_cstr(&f->sb, ": ");
                f_type(f, fl.type);
                if (fl.deflt) {
                    sb_cstr(&f->sb, " = ");
                    f_expr(f, fl.deflt, 0);
                }
            }
            f->depth--;
            f_nl(f);
            sb_char(&f->sb, '}');
            break;
        }
        case IT_ENUM: {
            sb_cstr(&f->sb, "enum ");
            sb_str(&f->sb, it->name);
            sb_cstr(&f->sb, " {");
            f->depth++;
            for (uint32_t i = 0; i < it->enom.variants.len; i++) {
                EnumVariant ev = it->enom.variants.data[i];
                f_nl(f);
                sb_str(&f->sb, ev.name);
                if (ev.value) {
                    sb_cstr(&f->sb, " = ");
                    f_expr(f, ev.value, 0);
                }
            }
            f->depth--;
            f_nl(f);
            sb_char(&f->sb, '}');
            break;
        }
        case IT_CONST:
            sb_cstr(&f->sb, "const ");
            sb_str(&f->sb, it->name);
            if (it->konst.type) {
                sb_cstr(&f->sb, ": ");
                f_type(f, it->konst.type);
            }
            sb_cstr(&f->sb, " = ");
            f_expr(f, it->konst.value, 0);
            break;
        case IT_TEST:
            sb_cstr(&f->sb, "test \"");
            sb_str(&f->sb, it->test.label);
            sb_cstr(&f->sb, "\" ");
            f_block(f, it->test.body);
            break;
        case IT_USE:
            sb_cstr(&f->sb, "use ");
            for (uint32_t i = 0; i < it->use_.path.len; i++) {
                if (i) sb_char(&f->sb, '.');
                sb_str(&f->sb, it->use_.path.data[i]);
            }
            break;
        case IT_TRAIT: {
            sb_cstr(&f->sb, "trait ");
            sb_str(&f->sb, it->name);
            sb_cstr(&f->sb, " {");
            f->depth++;
            for (uint32_t i = 0; i < it->trait.methods.len; i++) {
                f_nl(f);
                f_item(f, it->trait.methods.data[i]);
            }
            f->depth--;
            f_nl(f);
            sb_char(&f->sb, '}');
            break;
        }
        default: break;
    }
}

Str ast_format(Arena *a, const Module *m) {
    F f = {0};
    sb_init(&f.sb, a);

    f_doc(&f, m->doc);
    if (!str_empty(m->doc)) sb_char(&f.sb, '\n');
    sb_cstr(&f.sb, "module ");
    for (uint32_t i = 0; i < m->path.len; i++) {
        if (i) sb_char(&f.sb, '.');
        sb_str(&f.sb, m->path.data[i]);
    }
    sb_char(&f.sb, '\n');

    for (uint32_t i = 0; i < m->items.len; i++) {
        sb_char(&f.sb, '\n');
        f_item(&f, m->items.data[i]);
        sb_char(&f.sb, '\n');
    }
    return sb_finish(&f.sb);
}
