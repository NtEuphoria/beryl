/* print.c — stable S-expression dump of the AST, used by golden tests. */
#include "print.h"


typedef struct {
    SB  sb;
    int depth;
} Pr;

static void nl(Pr *p) {
    sb_char(&p->sb, '\n');
    sb_repeat(&p->sb, ' ', p->depth * 2);
}

static void pr_expr(Pr *p, const Expr *e);
static void pr_stmt(Pr *p, const Stmt *s);

static void pr_type(Pr *p, const TypeExpr *t) {
    if (!t) {
        sb_cstr(&p->sb, "_");
        return;
    }
    switch (t->kind) {
        case TE_PATH: {
            for (uint32_t i = 0; i < t->segs.len; i++) {
                if (i) sb_char(&p->sb, '.');
                sb_str(&p->sb, t->segs.data[i]);
            }
            if (t->args.len) {
                sb_char(&p->sb, '<');
                for (uint32_t i = 0; i < t->args.len; i++) {
                    if (i) sb_char(&p->sb, ',');
                    pr_type(p, t->args.data[i]);
                }
                sb_char(&p->sb, '>');
            }
            break;
        }
        case TE_ARRAY:
            sb_char(&p->sb, '[');
            pr_type(p, t->elem);
            sb_cstr(&p->sb, ";");
            if (t->len) pr_expr(p, t->len);
            sb_char(&p->sb, ']');
            break;
        case TE_OPTION:
            pr_type(p, t->elem);
            sb_char(&p->sb, '?');
            break;
        case TE_ERRUNION:
            sb_char(&p->sb, '!');
            pr_type(p, t->elem);
            break;
        default: sb_cstr(&p->sb, "?"); break;
    }
}

static void pr_expr(Pr *p, const Expr *e) {
    if (!e) {
        sb_cstr(&p->sb, "(nil)");
        return;
    }
    switch (e->kind) {
        case EX_INT:
            sb_fmt(&p->sb, "(int %llu%.*s)", (unsigned long long)e->int_lit.val,
                   (int)e->int_lit.suffix.len, e->int_lit.suffix.ptr); break;
        case EX_FLOAT:
            sb_fmt(&p->sb, "(float %.17g%.*s)", e->float_lit.val,
                   (int)e->float_lit.suffix.len, e->float_lit.suffix.ptr); break;
        case EX_STR:
            sb_fmt(&p->sb, "(str \"%.*s\")", (int)e->str_lit.len, e->str_lit.ptr);
            break;
        case EX_CHAR: sb_fmt(&p->sb, "(char %u)", e->char_lit); break;
        case EX_BOOL: sb_fmt(&p->sb, "(bool %s)", e->bool_lit ? "true" : "false"); break;
        case EX_SELF: sb_cstr(&p->sb, "(self)"); break;
        case EX_PATH: {
            sb_cstr(&p->sb, "(path ");
            for (uint32_t i = 0; i < e->path.segs.len; i++) {
                if (i) sb_char(&p->sb, '.');
                sb_str(&p->sb, e->path.segs.data[i]);
            }
            sb_char(&p->sb, ')');
            break;
        }
        case EX_UNARY:
            sb_fmt(&p->sb, "(unary %s ", tok_name(e->unary.op));
            pr_expr(p, e->unary.operand);
            sb_char(&p->sb, ')');
            break;
        case EX_BINARY:
            sb_fmt(&p->sb, "(bin %s ", tok_name(e->binary.op));
            pr_expr(p, e->binary.lhs);
            sb_char(&p->sb, ' ');
            pr_expr(p, e->binary.rhs);
            sb_char(&p->sb, ')');
            break;
        case EX_CALL:
            sb_cstr(&p->sb, "(call ");
            pr_expr(p, e->call.callee);
            for (uint32_t i = 0; i < e->call.args.len; i++) {
                sb_char(&p->sb, ' ');
                Arg ar = e->call.args.data[i];
                if (ar.conv != CONV_LET) sb_fmt(&p->sb, "%s:", conv_name(ar.conv));
                pr_expr(p, ar.value);
            }
            sb_char(&p->sb, ')');
            break;
        case EX_FIELD:
            sb_cstr(&p->sb, "(field ");
            pr_expr(p, e->field.base);
            sb_fmt(&p->sb, " %.*s)", (int)e->field.name.len, e->field.name.ptr);
            break;
        case EX_INDEX:
            sb_cstr(&p->sb, "(index ");
            pr_expr(p, e->index.base);
            sb_char(&p->sb, ' ');
            pr_expr(p, e->index.index);
            sb_char(&p->sb, ')');
            break;
        case EX_CAST:
            sb_cstr(&p->sb, "(cast ");
            pr_expr(p, e->cast.value);
            sb_char(&p->sb, ' ');
            pr_type(p, e->cast.type);
            sb_char(&p->sb, ')');
            break;
        case EX_STRUCT_LIT:
            sb_cstr(&p->sb, "(structlit ");
            pr_type(p, e->struct_lit.type);
            for (uint32_t i = 0; i < e->struct_lit.fields.len; i++) {
                FieldInit fi = e->struct_lit.fields.data[i];
                sb_fmt(&p->sb, " (%.*s ", (int)fi.name.len, fi.name.ptr);
                pr_expr(p, fi.value);
                sb_char(&p->sb, ')');
            }
            sb_char(&p->sb, ')');
            break;
        case EX_ARRAY_LIT:
            sb_cstr(&p->sb, "(arraylit");
            for (uint32_t i = 0; i < e->array_lit.elems.len; i++) {
                sb_char(&p->sb, ' ');
                pr_expr(p, e->array_lit.elems.data[i]);
            }
            sb_char(&p->sb, ')');
            break;
        case EX_IF:
            sb_cstr(&p->sb, "(if ");
            pr_expr(p, e->if_expr.cond);
            sb_char(&p->sb, ' ');
            pr_expr(p, e->if_expr.then_blk);
            if (e->if_expr.else_blk) {
                sb_char(&p->sb, ' ');
                pr_expr(p, e->if_expr.else_blk);
            }
            sb_char(&p->sb, ')');
            break;
        case EX_BLOCK: {
            sb_cstr(&p->sb, "(block");
            p->depth++;
            for (uint32_t i = 0; i < e->block.stmts.len; i++) {
                nl(p);
                pr_stmt(p, e->block.stmts.data[i]);
            }
            p->depth--;
            sb_char(&p->sb, ')');
            break;
        }
        case EX_TRY:
            sb_cstr(&p->sb, "(try ");
            pr_expr(p, e->try_expr.inner);
            sb_char(&p->sb, ')');
            break;
        case EX_CATCH:
            sb_cstr(&p->sb, "(catch ");
            pr_expr(p, e->catch_expr.value);
            if (!str_empty(e->catch_expr.binding))
                sb_fmt(&p->sb, " |%.*s|", (int)e->catch_expr.binding.len,
                       e->catch_expr.binding.ptr);
            sb_char(&p->sb, ' ');
            pr_expr(p, e->catch_expr.handler);
            sb_char(&p->sb, ')');
            break;
        case EX_ORELSE:
            sb_cstr(&p->sb, "(orelse ");
            pr_expr(p, e->orelse_expr.value);
            sb_char(&p->sb, ' ');
            pr_expr(p, e->orelse_expr.fallback);
            sb_char(&p->sb, ')');
            break;
        case EX_ERROR_LIT:
            sb_fmt(&p->sb, "(error %.*s)", (int)e->error_lit.len, e->error_lit.ptr);
            break;
        case EX_UNSAFE:
            sb_fmt(&p->sb, "(unsafe %.*s ", (int)e->unsafe_expr.capability.len,
                   e->unsafe_expr.capability.ptr);
            pr_expr(p, e->unsafe_expr.body);
            sb_char(&p->sb, ')');
            break;
        case EX_RANGE:
            sb_cstr(&p->sb, "(range ");
            pr_expr(p, e->range.lo);
            sb_char(&p->sb, ' ');
            pr_expr(p, e->range.hi);
            sb_char(&p->sb, ')');
            break;
        default: sb_cstr(&p->sb, "(?)"); break;
    }
}

static void pr_stmt(Pr *p, const Stmt *s) {
    if (!s) {
        sb_cstr(&p->sb, "(nil)");
        return;
    }
    switch (s->kind) {
        case ST_LET:
            sb_fmt(&p->sb, "(%s %.*s ", s->let.is_var ? "var" : "let", (int)s->let.name.len,
                   s->let.name.ptr);
            if (s->let.type) {
                pr_type(p, s->let.type);
                sb_char(&p->sb, ' ');
            }
            pr_expr(p, s->let.init);
            sb_char(&p->sb, ')');
            break;
        case ST_EXPR: pr_expr(p, s->expr); break;
        case ST_ASSIGN:
            sb_fmt(&p->sb, "(assign %s ", tok_name(s->assign.op));
            pr_expr(p, s->assign.target);
            sb_char(&p->sb, ' ');
            pr_expr(p, s->assign.value);
            sb_char(&p->sb, ')');
            break;
        case ST_WHILE:
            sb_cstr(&p->sb, "(while ");
            pr_expr(p, s->while_st.cond);
            sb_char(&p->sb, ' ');
            pr_expr(p, s->while_st.body);
            sb_char(&p->sb, ')');
            break;
        case ST_FOR:
            sb_fmt(&p->sb, "(for %.*s ", (int)s->for_st.var.len, s->for_st.var.ptr);
            pr_expr(p, s->for_st.iter);
            sb_char(&p->sb, ' ');
            pr_expr(p, s->for_st.body);
            sb_char(&p->sb, ')');
            break;
        case ST_RETURN:
            sb_cstr(&p->sb, "(return");
            if (s->expr) {
                sb_char(&p->sb, ' ');
                pr_expr(p, s->expr);
            }
            sb_char(&p->sb, ')');
            break;
        case ST_BREAK: sb_cstr(&p->sb, "(break)"); break;
        case ST_CONTINUE: sb_cstr(&p->sb, "(continue)"); break;
        case ST_DEFER:
            sb_cstr(&p->sb, "(defer ");
            pr_expr(p, s->expr);
            sb_char(&p->sb, ')');
            break;
        default: sb_cstr(&p->sb, "(?)"); break;
    }
}

static void pr_item(Pr *p, const Item *it) {
    for (uint32_t i = 0; i < it->attrs.len; i++) {
        Attr at = it->attrs.data[i];
        sb_fmt(&p->sb, "(@%.*s", (int)at.name.len, at.name.ptr);
        if (!str_empty(at.arg)) sb_fmt(&p->sb, " %.*s", (int)at.arg.len, at.arg.ptr);
        sb_cstr(&p->sb, ") ");
    }

    switch (it->kind) {
        case IT_FN: {
            sb_fmt(&p->sb, "(fn%s ", it->is_pub ? " pub" : "");
            if (!str_empty(it->fn.recv))
                sb_fmt(&p->sb, "%.*s.", (int)it->fn.recv.len, it->fn.recv.ptr);
            sb_fmt(&p->sb, "%.*s", (int)it->name.len, it->name.ptr);
            if (it->fn.generics.len) {
                sb_char(&p->sb, '<');
                for (uint32_t i = 0; i < it->fn.generics.len; i++) {
                    GenericParam g = it->fn.generics.data[i];
                    if (i) sb_char(&p->sb, ',');
                    sb_str(&p->sb, g.name);
                    if (!str_empty(g.bound)) sb_fmt(&p->sb, ":%.*s", (int)g.bound.len, g.bound.ptr);
                }
                sb_char(&p->sb, '>');
            }
            sb_cstr(&p->sb, " (params");
            for (uint32_t i = 0; i < it->fn.params.len; i++) {
                Param pm = it->fn.params.data[i];
                sb_fmt(&p->sb, " (%s %.*s", conv_name(pm.conv), (int)pm.name.len, pm.name.ptr);
                if (pm.type) {
                    sb_char(&p->sb, ' ');
                    pr_type(p, pm.type);
                }
                if (pm.deflt) {
                    sb_cstr(&p->sb, " =");
                    pr_expr(p, pm.deflt);
                }
                sb_char(&p->sb, ')');
            }
            sb_char(&p->sb, ')');
            if (it->fn.ret) {
                sb_cstr(&p->sb, " (ret ");
                pr_type(p, it->fn.ret);
                sb_char(&p->sb, ')');
            }
            p->depth++;
            nl(p);
            pr_expr(p, it->fn.body);
            p->depth--;
            sb_char(&p->sb, ')');
            break;
        }
        case IT_STRUCT: {
            sb_fmt(&p->sb, "(struct%s %.*s", it->is_pub ? " pub" : "", (int)it->name.len,
                   it->name.ptr);
            if (it->strukt.generics.len) {
                sb_char(&p->sb, '<');
                for (uint32_t i = 0; i < it->strukt.generics.len; i++) {
                    if (i) sb_char(&p->sb, ',');
                    sb_str(&p->sb, it->strukt.generics.data[i].name);
                }
                sb_char(&p->sb, '>');
            }
            p->depth++;
            for (uint32_t i = 0; i < it->strukt.fields.len; i++) {
                Field f = it->strukt.fields.data[i];
                nl(p);
                sb_fmt(&p->sb, "(%.*s ", (int)f.name.len, f.name.ptr);
                pr_type(p, f.type);
                if (f.deflt) {
                    sb_cstr(&p->sb, " = ");
                    pr_expr(p, f.deflt);
                }
                sb_char(&p->sb, ')');
            }
            p->depth--;
            sb_char(&p->sb, ')');
            break;
        }
        case IT_ENUM: {
            sb_fmt(&p->sb, "(enum%s %.*s", it->is_pub ? " pub" : "", (int)it->name.len,
                   it->name.ptr);
            for (uint32_t i = 0; i < it->enom.variants.len; i++) {
                EnumVariant ev = it->enom.variants.data[i];
                sb_fmt(&p->sb, " (%.*s", (int)ev.name.len, ev.name.ptr);
                if (ev.value) {
                    sb_char(&p->sb, ' ');
                    pr_expr(p, ev.value);
                }
                sb_char(&p->sb, ')');
            }
            sb_char(&p->sb, ')');
            break;
        }
        case IT_CONST:
            sb_fmt(&p->sb, "(const%s %.*s ", it->is_pub ? " pub" : "", (int)it->name.len,
                   it->name.ptr);
            if (it->konst.type) {
                pr_type(p, it->konst.type);
                sb_char(&p->sb, ' ');
            }
            pr_expr(p, it->konst.value);
            sb_char(&p->sb, ')');
            break;
        case IT_TEST:
            sb_fmt(&p->sb, "(test \"%.*s\"", (int)it->test.label.len, it->test.label.ptr);
            p->depth++;
            nl(p);
            pr_expr(p, it->test.body);
            p->depth--;
            sb_char(&p->sb, ')');
            break;
        case IT_USE: {
            sb_cstr(&p->sb, "(use ");
            for (uint32_t i = 0; i < it->use_.path.len; i++) {
                if (i) sb_char(&p->sb, '.');
                sb_str(&p->sb, it->use_.path.data[i]);
            }
            sb_char(&p->sb, ')');
            break;
        }
        case IT_TRAIT: {
            sb_fmt(&p->sb, "(trait%s %.*s", it->is_pub ? " pub" : "", (int)it->name.len,
                   it->name.ptr);
            p->depth++;
            for (uint32_t i = 0; i < it->trait.methods.len; i++) {
                nl(p);
                pr_item(p, it->trait.methods.data[i]);
            }
            p->depth--;
            sb_char(&p->sb, ')');
            break;
        }
        default: sb_cstr(&p->sb, "(?)"); break;
    }
}

Str ast_print(Arena *a, const Module *m) {
    Pr p = {0};
    sb_init(&p.sb, a);

    sb_cstr(&p.sb, "(module ");
    for (uint32_t i = 0; i < m->path.len; i++) {
        if (i) sb_char(&p.sb, '.');
        sb_str(&p.sb, m->path.data[i]);
    }
    p.depth++;
    for (uint32_t i = 0; i < m->items.len; i++) {
        nl(&p);
        pr_item(&p, m->items.data[i]);
    }
    p.depth--;
    sb_cstr(&p.sb, ")\n");
    return sb_finish(&p.sb);
}
