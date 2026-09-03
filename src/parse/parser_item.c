/* parser_item.c — items, module header, and the file entry point. */
#include "parser.h"

static void skip_nl_only(P *p) {
    while (p_check(p, TK_NEWLINE)) p_next(p);
}

/* Consecutive `//!` lines form one doc block attached to the next item. */
static Str collect_doc(P *p) {
    if (!p_check(p, TK_DOC)) return STR_EMPTY;
    SB sb;
    sb_init(&sb, p->a);
    bool first = true;
    while (p_check(p, TK_DOC)) {
        Token t = p_next(p);
        if (!first) sb_char(&sb, '\n');
        Str line = t.text;
        if (line.len && line.ptr[0] == ' ') line = str_slice(line, 1, line.len - 1);
        sb_str(&sb, line);
        first = false;
        skip_nl_only(p);
    }
    return sb_finish(&sb);
}

static AttrVec collect_attrs(P *p) {
    AttrVec v = {0};
    while (p_check(p, TK_AT)) {
        Token at = p_next(p);
        Token id = p_peek(p);
        if (!p_expect(p, TK_IDENT, "after `@`")) break;
        Attr a = {0};
        a.name = id.text;
        a.span = span_join(at.span, id.span);
        if (p_accept(p, TK_LPAREN)) {
            Token arg = p_peek(p);
            if (p_check(p, TK_IDENT)) {
                p_next(p);
                a.arg = arg.text;
            }
            p_expect(p, TK_RPAREN, "to close an attribute argument");
        }
        vec_push(p->a, v, a);
        skip_nl_only(p);
    }
    return v;
}

static GenericVec parse_generics(P *p) {
    GenericVec v = {0};
    if (!p_accept(p, TK_LT)) return v;
    for (;;) {
        Token id = p_peek(p);
        if (!p_expect(p, TK_IDENT, "as a generic parameter")) break;
        GenericParam g = {0};
        g.name         = id.text;
        g.span         = id.span;
        if (p_accept(p, TK_COLON)) {
            Token b = p_peek(p);
            if (p_expect(p, TK_IDENT, "as a trait bound")) g.bound = b.text;
        }
        vec_push(p->a, v, g);
        if (!p_accept(p, TK_COMMA)) break;
    }
    p_expect(p, TK_GT, "to close generic parameters");
    return v;
}

static ParamVec parse_params(P *p) {
    ParamVec v = {0};
    if (!p_expect(p, TK_LPAREN, "to open a parameter list")) return v;

    p_skip_newlines(p);
    if (p_accept(p, TK_RPAREN)) return v;

    for (;;) {
        p_skip_newlines(p);
        Param pm  = {0};
        Token t   = p_peek(p);
        pm.span   = t.span;
        bool conv_given = true;
        switch (t.kind) {
            case TK_INOUT: p_next(p); pm.conv = CONV_INOUT; break;
            case TK_SINK: p_next(p); pm.conv = CONV_SINK; break;
            case TK_SET: p_next(p); pm.conv = CONV_SET; break;
            case TK_LET: p_next(p); pm.conv = CONV_LET; break;
            default: pm.conv = CONV_LET; conv_given = false; break;
        }
        (void)conv_given;

        if (p_check(p, TK_SELF)) {
            Token s    = p_next(p);
            pm.is_self = true;
            pm.name    = s.text;
            pm.span    = span_join(pm.span, s.span);
        } else {
            Token id = p_peek(p);
            if (!p_expect(p, TK_IDENT, "as a parameter name")) break;
            pm.name = id.text;
            p_expect(p, TK_COLON, "after a parameter name");
            pm.type = parse_type(p);
            if (p_accept(p, TK_ASSIGN)) pm.deflt = parse_expr(p);
            pm.span = span_join(pm.span, pm.deflt ? pm.deflt->span
                                                  : (pm.type ? pm.type->span : id.span));
        }

        vec_push(p->a, v, pm);
        p_skip_newlines(p);
        if (!p_accept(p, TK_COMMA)) break;
        p_skip_newlines(p);
        if (p_check(p, TK_RPAREN)) break; /* trailing comma */
    }

    p_skip_newlines(p);
    p_expect(p, TK_RPAREN, "to close a parameter list");
    return v;
}

static void check_params(P *p, ParamVec ps) {
    for (uint32_t i = 0; i < ps.len; i++) {
        Param pm = ps.data[i];

        if (pm.is_self && i != 0) {
            Diag *dg = diag_error(p->d, 206, pm.span,
                                  "`self` may only be the first parameter");
            diag_help(dg, "write `fn Type.name(inout self, ...)`");
        }
        if (pm.deflt && pm.conv != CONV_LET) {
            Diag *dg = diag_error(p->d, 207, pm.span,
                                  "a `%s` parameter cannot have a default value",
                                  conv_name(pm.conv));
            diag_note(dg, "defaults are copied at the call site, which has no meaning for "
                          "a borrow or a move");
        }
        for (uint32_t j = 0; j < i; j++) {
            if (str_eq(ps.data[j].name, pm.name) && !str_empty(pm.name)) {
                Diag *dg = diag_error(p->d, 205, pm.span, "duplicate parameter `%.*s`",
                                      (int)pm.name.len, pm.name.ptr);
                diag_label(dg, ps.data[j].span, "first declared here");
                diag_label(dg, pm.span, "declared again here");
                break;
            }
        }
    }
}

static Item *parse_fn(P *p, bool is_pub, Str doc, AttrVec attrs) {
    Token kw = p_next(p); /* fn */
    Token n1 = p_peek(p);
    if (!p_expect(p, TK_IDENT, "as a function name")) return NULL;

    Str recv = STR_EMPTY, name = n1.text;
    if (p_accept(p, TK_DOT)) {
        Token n2 = p_peek(p);
        if (!p_expect(p, TK_IDENT, "as a method name")) return NULL;
        recv = n1.text;
        name = n2.text;
    }

    Item *it   = ast_item(p->a, IT_FN, kw.span);
    it->is_pub = is_pub;
    it->doc    = doc;
    it->attrs  = attrs;
    it->name   = name;

    it->fn.recv     = recv;
    it->fn.generics = parse_generics(p);
    it->fn.params   = parse_params(p);
    check_params(p, it->fn.params);

    if (p_accept(p, TK_ARROW)) it->fn.ret = parse_type(p);

    it->fn.body = parse_block(p);
    it->span    = span_join(kw.span, it->fn.body ? it->fn.body->span : kw.span);
    return it;
}

static Item *parse_struct(P *p, bool is_pub, Str doc, AttrVec attrs) {
    Token kw = p_next(p);
    Token id = p_peek(p);
    if (!p_expect(p, TK_IDENT, "as a struct name")) return NULL;

    Item *it   = ast_item(p->a, IT_STRUCT, kw.span);
    it->is_pub = is_pub;
    it->doc    = doc;
    it->attrs  = attrs;
    it->name   = id.text;

    it->strukt.generics = parse_generics(p);
    if (!p_expect(p, TK_LBRACE, "to open a struct body")) return it;

    p_skip_newlines(p);
    while (!p_check(p, TK_RBRACE) && !p_check(p, TK_EOF)) {
        uint32_t before = p->pos;

        Str   fdoc = collect_doc(p);
        Token fid  = p_peek(p);
        if (!p_expect(p, TK_IDENT, "as a field name")) break;

        Field f = {0};
        f.name  = fid.text;
        f.doc   = fdoc;
        p_expect(p, TK_COLON, "after a field name");
        f.type = parse_type(p);
        if (p_accept(p, TK_ASSIGN)) f.deflt = parse_expr(p);
        f.span = span_join(fid.span, f.deflt ? f.deflt->span
                                             : (f.type ? f.type->span : fid.span));
        vec_push(p->a, it->strukt.fields, f);

        /* Fields separate on a comma, a line break, or both. */
        bool sep = false;
        if (p_accept(p, TK_COMMA)) sep = true;
        if (p_check(p, TK_NEWLINE)) {
            p_skip_newlines(p);
            sep = true;
        }
        if (!sep) break;
        if (p->pos == before) p_next(p);
    }

    Token rb = p_peek(p);
    p_expect(p, TK_RBRACE, "to close a struct body");
    it->span = span_join(kw.span, rb.span);
    return it;
}

static Item *parse_enum(P *p, bool is_pub, Str doc, AttrVec attrs) {
    Token kw = p_next(p);
    Token id = p_peek(p);
    if (!p_expect(p, TK_IDENT, "as an enum name")) return NULL;

    Item *it   = ast_item(p->a, IT_ENUM, kw.span);
    it->is_pub = is_pub;
    it->doc    = doc;
    it->attrs  = attrs;
    it->name   = id.text;

    if (!p_expect(p, TK_LBRACE, "to open an enum body")) return it;
    p_skip_newlines(p);

    while (!p_check(p, TK_RBRACE) && !p_check(p, TK_EOF)) {
        uint32_t before = p->pos;
        Token    vid    = p_peek(p);
        if (!p_expect(p, TK_IDENT, "as an enum variant")) break;

        EnumVariant ev = {0};
        ev.name        = vid.text;
        ev.span        = vid.span;
        if (p_accept(p, TK_ASSIGN)) ev.value = parse_expr(p);
        vec_push(p->a, it->enom.variants, ev);

        bool sep = false;
        if (p_accept(p, TK_COMMA)) sep = true;
        if (p_check(p, TK_NEWLINE)) {
            p_skip_newlines(p);
            sep = true;
        }
        if (!sep) break;
        if (p->pos == before) p_next(p);
    }

    Token rb = p_peek(p);
    p_expect(p, TK_RBRACE, "to close an enum body");
    it->span = span_join(kw.span, rb.span);
    return it;
}

static Item *parse_const(P *p, bool is_pub, Str doc, AttrVec attrs) {
    Token kw = p_next(p);
    Token id = p_peek(p);
    if (!p_expect(p, TK_IDENT, "as a constant name")) return NULL;

    Item *it   = ast_item(p->a, IT_CONST, kw.span);
    it->is_pub = is_pub;
    it->doc    = doc;
    it->attrs  = attrs;
    it->name   = id.text;

    if (p_accept(p, TK_COLON)) it->konst.type = parse_type(p);
    p_expect(p, TK_ASSIGN, "in a constant declaration");
    it->konst.value = parse_expr(p);
    it->span = span_join(kw.span, it->konst.value ? it->konst.value->span : kw.span);
    return it;
}

static Item *parse_test(P *p, Str doc, AttrVec attrs) {
    Token kw = p_next(p);
    Token lb = p_peek(p);

    Item *it  = ast_item(p->a, IT_TEST, kw.span);
    it->doc   = doc;
    it->attrs = attrs;

    if (p_check(p, TK_STRING)) {
        p_next(p);
        it->test.label = lb.text;
        it->name       = lb.text;
    } else {
        diag_error(p->d, 201, lb.span, "expected a test name string after `test`, found `%s`",
                   tok_name(lb.kind));
    }
    it->test.body = parse_block(p);
    it->span      = span_join(kw.span, it->test.body ? it->test.body->span : kw.span);
    return it;
}

static Item *parse_use(P *p, Str doc, AttrVec attrs) {
    Token kw = p_next(p);
    Item *it = ast_item(p->a, IT_USE, kw.span);
    it->doc  = doc;
    it->attrs = attrs;

    Token seg = p_peek(p);
    if (!p_expect(p, TK_IDENT, "after `use`")) return it;
    vec_push(p->a, it->use_.path, seg.text);
    while (p_accept(p, TK_DOT)) {
        Token s2 = p_peek(p);
        if (!p_expect(p, TK_IDENT, "in a use path")) break;
        vec_push(p->a, it->use_.path, s2.text);
    }
    if (it->use_.path.len) it->name = it->use_.path.data[it->use_.path.len - 1];
    it->span = p_span_from(p, 0);
    it->span = span_join(kw.span, seg.span);
    return it;
}

static Item *parse_trait(P *p, bool is_pub, Str doc, AttrVec attrs) {
    Token kw = p_next(p);
    Token id = p_peek(p);
    if (!p_expect(p, TK_IDENT, "as a trait name")) return NULL;

    Item *it   = ast_item(p->a, IT_TRAIT, kw.span);
    it->is_pub = is_pub;
    it->doc    = doc;
    it->attrs  = attrs;
    it->name   = id.text;

    it->trait.generics = parse_generics(p);
    if (!p_expect(p, TK_LBRACE, "to open a trait body")) return it;
    p_skip_newlines(p);

    while (!p_check(p, TK_RBRACE) && !p_check(p, TK_EOF)) {
        uint32_t before = p->pos;
        Str      mdoc   = collect_doc(p);
        if (p_check(p, TK_FN)) {
            /* A trait method is a signature; the body is optional. */
            Token   fkw = p_next(p);
            Token   fid = p_peek(p);
            if (!p_expect(p, TK_IDENT, "as a trait method name")) break;
            Item *m   = ast_item(p->a, IT_FN, fkw.span);
            m->name   = fid.text;
            m->doc    = mdoc;
            m->fn.params = parse_params(p);
            check_params(p, m->fn.params);
            if (p_accept(p, TK_ARROW)) m->fn.ret = parse_type(p);
            if (p_check(p, TK_LBRACE)) m->fn.body = parse_block(p);
            vec_push(p->a, it->trait.methods, m);
        } else {
            diag_error(p->d, 204, p_peek(p).span,
                       "expected `fn` in a trait body, found `%s`", tok_name(p_kind(p)));
            break;
        }
        p_skip_newlines(p);
        if (p->pos == before) p_next(p);
    }

    Token rb = p_peek(p);
    p_expect(p, TK_RBRACE, "to close a trait body");
    it->span = span_join(kw.span, rb.span);
    return it;
}

static void sync_item(P *p) {
    int depth = 0;
    while (!p_check(p, TK_EOF)) {
        TokKind k = p_kind(p);
        if (k == TK_LBRACE) depth++;
        else if (k == TK_RBRACE && depth > 0) depth--;
        else if (depth == 0) {
            switch (k) {
                case TK_FN:
                case TK_STRUCT:
                case TK_ENUM:
                case TK_CONST:
                case TK_TEST:
                case TK_USE:
                case TK_TRAIT:
                case TK_PUB:
                case TK_AT: return;
                default: break;
            }
        }
        p_next(p);
    }
}

Module *parse_file(Arena *a, DiagBag *d, Interner *in, TokenVec toks, uint32_t file) {
    P p = {0};
    p.a              = a;
    p.d              = d;
    p.in             = in;
    p.toks           = toks;
    p.file           = file;
    p.last_error_pos = UINT32_MAX;

    Module *m = ARENA_NEW(a, Module);
    m->file   = file;
    m->span   = toks.len ? toks.data[0].span : SPAN_NONE;

    skip_nl_only(&p);
    m->doc = collect_doc(&p);
    skip_nl_only(&p);

    if (p_check(&p, TK_MODULE)) {
        p_next(&p);
        Token seg = p_peek(&p);
        if (p_expect(&p, TK_IDENT, "as a module name")) {
            vec_push(a, m->path, seg.text);
            while (p_accept(&p, TK_DOT)) {
                Token s2 = p_peek(&p);
                if (!p_expect(&p, TK_IDENT, "in a module path")) break;
                vec_push(a, m->path, s2.text);
            }
        }
    } else if (!p_check(&p, TK_EOF)) {
        Diag *dg = diag_error(d, 209, p_peek(&p).span,
                              "a source file must begin with a `module` declaration");
        diag_help(dg, "add `module <name>` as the first line of the file");
    }

    for (;;) {
        skip_nl_only(&p);
        if (p_check(&p, TK_EOF)) break;

        Str doc = collect_doc(&p);
        skip_nl_only(&p);
        AttrVec attrs = collect_attrs(&p);
        skip_nl_only(&p);
        if (p_check(&p, TK_EOF)) break;

        bool     is_pub = p_accept(&p, TK_PUB);
        uint32_t before = p.pos;
        Item    *it     = NULL;

        switch (p_kind(&p)) {
            case TK_FN: it = parse_fn(&p, is_pub, doc, attrs); break;
            case TK_STRUCT: it = parse_struct(&p, is_pub, doc, attrs); break;
            case TK_ENUM: it = parse_enum(&p, is_pub, doc, attrs); break;
            case TK_CONST: it = parse_const(&p, is_pub, doc, attrs); break;
            case TK_TEST: it = parse_test(&p, doc, attrs); break;
            case TK_USE: it = parse_use(&p, doc, attrs); break;
            case TK_TRAIT: it = parse_trait(&p, is_pub, doc, attrs); break;
            default: {
                if (p.pos != p.last_error_pos) {
                    p.last_error_pos = p.pos;
                    diag_error(d, 204, p_peek(&p).span,
                               "expected an item (`fn`, `struct`, `enum`, `const`, `test`, "
                               "`use` or `trait`), found `%s`",
                               tok_name(p_kind(&p)));
                }
                sync_item(&p);
                break;
            }
        }

        if (it) vec_push(a, m->items, it);
        if (p.pos == before) p_next(&p);
    }

    return m;
}
