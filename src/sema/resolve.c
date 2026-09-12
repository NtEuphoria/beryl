#include "resolve.h"
#include "constfold.h"

static Str join2(Arena *a, Str base, Str name) {
    SB b; sb_init(&b, a);
    if (base.len) { sb_str(&b, base); sb_char(&b, '.'); }
    sb_str(&b, name); return sb_finish(&b);
}
Program *prog_new(Arena *a) {
    Program *p = ARENA_NEW(a, Program);
    p->a = a; p->types = types_new(a); p->items = map_new(a);
    p->module_scopes = map_new(a); p->methods = map_new(a);
    return p;
}
void prog_add_module(Program *p, Module *m) { vec_push(p->a, p->modules, m); }
Item *prog_item(Program *p, Str qualified) { return map_get(p->items, qualified); }
bool prog_same_module(Module *a, Module *b) {
    return a && b && a->scope && a->scope == b->scope;
}
bool prog_accessible(DiagBag *d, Module *from, Item *it, Span use) {
    if (!it) return false;
    if (it->is_pub || prog_same_module(from, it->owner)) return true;
    Diag *dg = diag_error(d, 323, use, "`%.*s` is private to its module", (int)it->qual_name.len, it->qual_name.ptr);
    diag_label(dg, it->span, "private declaration here");
    diag_help(dg, "use its module's public API, or explicitly declare this item `pub`");
    return false;
}

Item *prog_lookup(Program *p, Module *module, Str path) {
    ModuleScope *s = module ? module->scope : NULL;
    uint32_t dot = 0;
    while (dot < path.len && path.ptr[dot] != '.') dot++;
    if (dot == path.len) {
        if (!s) return NULL;
        Item *it = map_get(s->items, path);
        if (it) return it;
        Import *im = map_get(s->imports, path);
        return im ? im->item : NULL;
    }
    Str root = str_new(path.ptr, dot), tail = str_new(path.ptr + dot + 1, path.len - dot - 1);
    if (s) {
        /* An explicit alias takes precedence over an absolute module root. */
        Import *im = map_get(s->imports, root);
        if (im) {
            Str base = im->module ? im->module->name : im->item->qual_name;
            return prog_item(p, join2(p->a, base, tail));
        }
        Item *local = map_get(s->items, root);
        if (local) return prog_item(p, join2(p->a, local->qual_name, tail));
        Item *relative = prog_item(p, join2(p->a, s->name, path));
        if (relative) return relative;
    }
    return prog_item(p, path);
}

Item *prog_method(Program *p, Item *receiver, Str method) {
    return receiver ? map_get(p->methods, join2(p->a, receiver->qual_name, method)) : NULL;
}

bool prog_expr_path(Arena *a, Expr *e, Str *path, Str *root) {
    if (!e) return false;
    if (e->kind == EX_PATH && e->path.segs.len) {
        *path = path_str(a, e->path.segs); *root = e->path.segs.data[0]; return true;
    }
    if (e->kind == EX_FIELD) {
        Str base;
        if (prog_expr_path(a, e->field.base, &base, root)) {
            *path = join2(a, base, e->field.name); return true;
        }
    }
    return false;
}

static void duplicate(DiagBag *d, Item *now, Item *prev, Str name) {
    Diag *dg = diag_error(d, 308, now->span, "`%.*s` is defined twice", (int)name.len, name.ptr);
    diag_label(dg, prev->span, "first declaration here");
    diag_label(dg, now->span, "conflicting declaration here");
}

static void collect(DiagBag *d, Program *p, Module *m) {
    ModuleScope *s = m->scope;
    for (uint32_t i = 0; i < m->items.len; i++) {
        Item *it = m->items.data[i]; it->owner = m;
        if (it->kind == IT_USE) continue;
        Str local = it->kind == IT_FN && it->fn.recv.len ? join2(p->a, it->fn.recv, it->name) : it->name;
        it->qual_name = join2(p->a, s->name, local);
        if (it->kind == IT_TEST || (it->kind == IT_FN && it->fn.recv.len)) continue;
        Item *prev = prog_item(p, it->qual_name);
        if (prev) { duplicate(d, it, prev, it->qual_name); continue; }
        map_put(p->items, it->qual_name, it);
        map_put(s->items, it->name, it);
        if (it->kind == IT_STRUCT) it->rtype = ty_named(p->types, TY_STRUCT, it->qual_name, it);
        if (it->kind == IT_ENUM) it->rtype = ty_named(p->types, TY_ENUM, it->qual_name, it);
    }
}

static void imports(DiagBag *d, Program *p, ModuleScope *s) {
    for (uint32_t f = 0; f < s->files.len; f++) {
        Module *m = s->files.data[f];
        for (uint32_t i = 0; i < m->items.len; i++) {
            Item *site = m->items.data[i];
            if (site->kind != IT_USE || !site->use_.path.len) continue;
            Str full = path_str(p->a, site->use_.path);
            Str alias = site->use_.path.data[site->use_.path.len - 1];
            Item *item = prog_item(p, full);
            ModuleScope *mod = map_get(p->module_scopes, full);
            if ((!item && !mod) || (item && mod)) {
                diag_error(d, 324, site->span, "import `%.*s` %s", (int)full.len, full.ptr,
                           item && mod ? "is ambiguous between an item and module" : "does not name an item or module");
                continue;
            }
            if (item && !prog_accessible(d, m, item, site->span)) continue;
            Item *own = map_get(s->items, alias);
            Import *old = map_get(s->imports, alias);
            if (own && own != item) { duplicate(d, site, own, alias); continue; }
            if (old && (old->item != item || old->module != mod)) {
                duplicate(d, site, old->site, alias); continue;
            }
            if (!old) {
                Import *im = ARENA_NEW(p->a, Import);
                im->item = item; im->module = mod; im->site = site;
                map_put(s->imports, alias, im);
            }
        }
    }
}

static void methods(DiagBag *d, Program *p, Module *m) {
    for (uint32_t i = 0; i < m->items.len; i++) {
        Item *it = m->items.data[i];
        if (it->kind != IT_FN || !it->fn.recv.len) continue;
        Item *recv = prog_lookup(p, m, it->fn.recv);
        if (!recv || (recv->kind != IT_STRUCT && recv->kind != IT_ENUM)) {
            diag_error(d, 302, it->span, "unknown receiver type `%.*s`", (int)it->fn.recv.len, it->fn.recv.ptr);
            continue;
        }
        if (!prog_same_module(m, recv->owner)) {
            diag_error(d, 323, it->span, "methods must be declared in their receiver's module"); continue;
        }
        it->fn.recv_decl = recv;
        Str key = join2(p->a, recv->qual_name, it->name);
        Item *prev = map_get(p->methods, key);
        if (prev) duplicate(d, it, prev, key);
        else map_put(p->methods, key, it);
    }
}

static TypeKind container_kind(Str name, uint32_t *arity) {
    if (str_eq_c(name,"List")) { *arity=1; return TY_LIST; }
    if (str_eq_c(name,"Box")) { *arity=1; return TY_BOX; }
    if (str_eq_c(name,"Rc")) { *arity=1; return TY_RC; }
    if (str_eq_c(name,"Handle")) { *arity=1; return TY_HANDLE; }
    if (str_eq_c(name,"Pool")) { *arity=1; return TY_POOL; }
    if (str_eq_c(name,"Map")) { *arity=2; return TY_MAP; }
    return TY_ERROR;
}

Type *resolve_type_expr(Program *p, DiagBag *d, Module *module, Item *scope, TypeExpr *te) {
    if (!te) return ty_prim(p->types, TY_VOID);
    switch (te->kind) {
    case TE_OPTION: return ty_option(p->types, resolve_type_expr(p,d,module,scope,te->elem));
    case TE_ERRUNION: return ty_errunion(p->types, resolve_type_expr(p,d,module,scope,te->elem));
    case TE_ARRAY: {
        Type *elem = resolve_type_expr(p,d,module,scope,te->elem);
        uint64_t n = 0;
        const_eval_len_in(p->a,d,p,module,scope,te->len,&n);
        return ty_array(p->types,elem,n);
    }
    case TE_PATH: break;
    default: return ty_prim(p->types,TY_ERROR);
    }
    if (!te->segs.len) return ty_prim(p->types,TY_ERROR);
    Str full = path_str(p->a,te->segs);
    Str last = te->segs.data[te->segs.len-1];
    if (scope && te->segs.len == 1) {
        GenericVec generics = scope->kind == IT_FN ? scope->fn.generics :
                              scope->kind == IT_STRUCT ? scope->strukt.generics : (GenericVec){0};
        for (uint32_t i = 0; i < generics.len; i++) {
            if (str_eq(generics.data[i].name,last)) {
                if (te->args.len) diag_error(d,302,te->span,"a type parameter takes no type arguments");
                SB key; sb_init(&key,p->a); sb_str(&key,scope->qual_name); sb_cstr(&key,".$"); sb_str(&key,last);
                return ty_typeparam(p->types,sb_finish(&key));
            }
        }
    }
    Item *it = prog_lookup(p,module,full);
    if (it) {
        if (!prog_accessible(d,module,it,te->span)) return ty_prim(p->types,TY_ERROR);
        if ((it->kind == IT_STRUCT || it->kind == IT_ENUM) && it->rtype) {
            if (te->args.len || (it->kind == IT_STRUCT && it->strukt.generics.len)) {
                diag_error(d,508,te->span,"user-defined generic types are not instantiated yet");
                return ty_prim(p->types,TY_ERROR);
            }
            return it->rtype;
        }
    } else if (te->segs.len == 1) {
        uint32_t arity = 0; TypeKind ck = container_kind(last,&arity);
        if (ck != TY_ERROR) {
            if (te->args.len != arity) {
                diag_error(d,302,te->span,"`%.*s` takes %u type arguments, found %u",(int)last.len,last.ptr,arity,te->args.len);
                return ty_prim(p->types,TY_ERROR);
            }
            Type *first = resolve_type_expr(p,d,module,scope,te->args.data[0]);
            if (ck == TY_MAP) return ty_map(p->types,first,resolve_type_expr(p,d,module,scope,te->args.data[1]));
            return ty_wrap(p->types,ck,first);
        }
        uint8_t bits=0; bool sign=false; TypeKind pk=ty_prim_from_name(last,&bits,&sign);
        if (pk != TY_ERROR) {
            if (te->args.len) diag_error(d,302,te->span,"primitive types take no type arguments");
            if (pk == TY_INT) return ty_int(p->types,bits,sign);
            if (pk == TY_FLOAT) return ty_float(p->types,bits);
            return ty_prim(p->types,pk);
        }
    }
    Diag *dg=diag_error(d,302,te->span,"unknown type `%.*s`",(int)full.len,full.ptr);
    diag_help(dg,"check the spelling and import its declaration; generic parameters must be declared");
    return ty_prim(p->types,TY_ERROR);
}

static void resolve_decls(DiagBag *d, Program *p, Module *m) {
    for (uint32_t i=0;i<m->items.len;i++) {
        Item *it=m->items.data[i];
        GenericVec generics = it->kind == IT_FN ? it->fn.generics :
            it->kind == IT_STRUCT ? it->strukt.generics : (GenericVec){0};
        for (uint32_t q=0;q<generics.len;q++) for (uint32_t prev=0;prev<q;prev++) {
            if (str_eq(generics.data[q].name,generics.data[prev].name)) {
                Diag *dg=diag_error(d,308,generics.data[q].span,"duplicate generic parameter");
                diag_label(dg,generics.data[prev].span,"first declared here"); break;
            }
        }
        switch (it->kind) {
        case IT_STRUCT:
            for (uint32_t f=0;f<it->strukt.fields.len;f++) {
                Field *fl=&it->strukt.fields.data[f];
                fl->rtype=resolve_type_expr(p,d,m,it,fl->type); fl->index=f;
                for (uint32_t g=0;g<f;g++) if (str_eq(it->strukt.fields.data[g].name,fl->name)) {
                    Diag *dg=diag_error(d,308,fl->span,"duplicate field `%.*s`",(int)fl->name.len,fl->name.ptr);
                    diag_label(dg,it->strukt.fields.data[g].span,"first declared here"); break;
                }
            }
            break;
        case IT_FN:
            for (uint32_t q=0;q<it->fn.params.len;q++) {
                Param *pm=&it->fn.params.data[q];
                pm->rtype=pm->is_self ? (it->fn.recv_decl ? it->fn.recv_decl->rtype : ty_prim(p->types,TY_ERROR)) :
                    resolve_type_expr(p,d,m,it,pm->type);
                if (pm->is_self && !it->fn.recv_decl && !it->fn.recv.len)
                    diag_error(d,302,pm->span,"self requires a method receiver");
            }
            it->rtype=resolve_type_expr(p,d,m,it,it->fn.ret);
            break;
        case IT_CONST:
            it->rtype=it->konst.type ? resolve_type_expr(p,d,m,it,it->konst.type) : NULL;
            break;
        default: break;
        }
    }
}

static bool visit(DiagBag *d, Program *p, Map *marks, ModuleScope *s) {
    intptr_t mark=(intptr_t)map_get(marks,s->name);
    if (mark==2) return true;
    if (mark==1) {
        diag_error(d,309,s->files.data[0]->span,"module `%.*s` is part of an import cycle",(int)s->name.len,s->name.ptr);
        return false;
    }
    map_put(marks,s->name,(void *)(intptr_t)1);
    bool ok=true;
    for (uint32_t f=0;f<s->files.len;f++) {
        Module *m=s->files.data[f];
        for (uint32_t i=0;i<m->items.len;i++) {
            Item *it=m->items.data[i];
            if (it->kind!=IT_USE || !it->use_.path.len) continue;
            Import *im=map_get(s->imports,it->use_.path.data[it->use_.path.len-1]);
            if (!im) continue;
            ModuleScope *dep=im->module ? im->module : ((Module *)im->item->owner)->scope;
            if (dep!=s) ok=visit(d,p,marks,dep) && ok;
        }
    }
    map_put(marks,s->name,(void *)(intptr_t)2); return ok;
}

bool resolve_program(DiagBag *d, Program *p) {
    uint32_t before=diag_errors(d);
    for (uint32_t i=0;i<p->modules.len;i++) {
        Module *m=p->modules.data[i]; Str name=path_str(p->a,m->path);
        ModuleScope *s=map_get(p->module_scopes,name);
        if (!s) {
            s=ARENA_NEW(p->a,ModuleScope); s->name=name;
            s->items=map_new(p->a); s->imports=map_new(p->a);
            map_put(p->module_scopes,name,s);
        }
        m->scope=s; vec_push(p->a,s->files,m);
    }
    for (uint32_t i=0;i<p->modules.len;i++) collect(d,p,p->modules.data[i]);
    for (uint32_t i=0;i<p->modules.len;i++) {
        Module *m=p->modules.data[i]; ModuleScope *s=m->scope;
        if (s->files.data[0]!=m) continue;
        Item *collision=prog_item(p,s->name);
        if (collision) {
            Diag *dg=diag_error(d,308,m->span,"module and item have the same qualified identity");
            diag_label(dg,collision->span,"item declaration here");
        }
        imports(d,p,s);
    }
    for (uint32_t i=0;i<p->modules.len;i++) methods(d,p,p->modules.data[i]);
    for (uint32_t i=0;i<p->modules.len;i++) resolve_decls(d,p,p->modules.data[i]);
    Map *marks=map_new(p->a);
    for (uint32_t i=0;i<p->modules.len;i++) visit(d,p,marks,p->modules.data[i]->scope);
    return diag_errors(d)==before;
}
