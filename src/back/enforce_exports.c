#include "enforce_backend.h"
#include "../common/symbol.h"

Str enfusion_export_name(EnfusionExports exports, Item *item) {
    if (!item) return STR_EMPTY;
    for (uint32_t i=0;i<exports.len;i++)
        if (exports.data[i].item == item && exports.data[i].kind != EF_EXPORT_CONSTRUCTOR)
            return exports.data[i].name;
    return STR_EMPTY;
}

Item *enfusion_export_constructor(EnfusionExports exports, Item *receiver) {
    for (uint32_t i=0;i<exports.len;i++) {
        EnfusionExport *ex=&exports.data[i];
        if (ex->kind==EF_EXPORT_CONSTRUCTOR && ex->item && ex->item->kind==IT_FN &&
            ex->item->fn.recv_decl==receiver) return ex->item;
    }
    return NULL;
}

static bool starts(Str value, Str prefix) {
    return value.len >= prefix.len && str_eq(str_new(value.ptr,prefix.len),prefix);
}
static bool identifier(Str name) {
    if (!name.len) return false;
    for (uint32_t i=0;i<name.len;i++) {
        char c=name.ptr[i];
        if (!((c>='a'&&c<='z') || (c>='A'&&c<='Z') || c=='_' || (i&&c>='0'&&c<='9')))
            return false;
    }
    static const char *const reserved[]={"out","inout","ref","class","enum","void","int",
        "float","bool","string","vector","array","map","set","new","delete","null",
        "this","super","override","protected","private","static","const","typedef",
        "proto","native","sealed","modded","owned","notnull","volatile","autoptr",
        "if","else","while","for","foreach","switch","case","default","break",
        "continue","return","true","false","managed","local","event","sizeof","typename"};
    for (size_t i=0;i<sizeof reserved/sizeof reserved[0];i++) if (str_eq_c(name,reserved[i])) return false;
    return true;
}
static Str folded(Arena *a,Str value) {
    SB b; sb_init(&b,a);
    for (uint32_t i=0;i<value.len;i++) {
        char c=value.ptr[i]; sb_char(&b,c>='A'&&c<='Z' ? (char)(c-'A'+'a') : c);
    }
    return sb_finish(&b);
}
static Item *method(Program *p,Str source) {
    uint32_t dot=source.len;
    while (dot && source.ptr[dot-1]!='.') dot--;
    if (!dot) return NULL;
    Item *receiver=prog_item(p,str_new(source.ptr,dot-1));
    return prog_method(p,receiver,str_new(source.ptr+dot,source.len-dot));
}
static bool scalar(Type *t,bool allow_void) {
    return t && ((allow_void&&t->kind==TY_VOID) || t->kind==TY_BOOL ||
        (t->kind==TY_INT&&t->bits==32&&t->is_signed) || (t->kind==TY_FLOAT&&t->bits==32));
}
static bool literal_default(Expr *x) {
    return !x || x->kind==EX_INT || x->kind==EX_FLOAT || x->kind==EX_BOOL ||
        (x->kind==EX_UNARY && x->unary.op==TK_MINUS && literal_default(x->unary.operand));
}
static Str internal_prefix(Arena *a,Str prefix) {
    SB b; sb_init(&b,a);
    if (prefix.len) { sb_str(&b,prefix); sb_char(&b,'_'); }
    sb_cstr(&b,"be_"); return sb_finish(&b);
}

bool enfusion_validate_exports(DiagBag *d,Program *p,EnfusionOpts o) {
    uint32_t before=diag_errors(d);
    Map *classes=map_new(p->a), *members=map_new(p->a), *sources=map_new(p->a);
    Str reserved=folded(p->a,internal_prefix(p->a,o.prefix));
    for (uint32_t i=0;i<o.exports.len;i++) {
        EnfusionExport *ex=&o.exports.data[i];
        ex->item=ex->kind==EF_EXPORT_CLASS ? prog_item(p,ex->source) : method(p,ex->source);
        Item *it=ex->item;
        if (!it || (ex->kind==EF_EXPORT_CLASS ? it->kind!=IT_STRUCT : it->kind!=IT_FN)) {
            diag_error(d,326,SPAN_NONE,"export source `%.*s` is not a supported declaration",
                (int)ex->source.len,ex->source.ptr); continue;
        }
        if (!it->is_pub || (it->kind==IT_FN && (!it->fn.body || it->fn.generics.len)) ||
            (it->kind==IT_STRUCT && it->strukt.generics.len))
            diag_error(d,326,it->span,"exports require public, concrete declarations with an implementation");
        if (!identifier(ex->name)) diag_error(d,326,it->span,"export name must be a non-reserved ASCII engine identifier");
        Str key=folded(p->a,ex->name);
        if (starts(key,ex->kind==EF_EXPORT_CLASS ? reserved : str_from("be_")))
            diag_error(d,326,it->span,"export name overlaps the compiler's internal namespace");
        if (map_has(sources,ex->source)) diag_error(d,326,it->span,"a declaration may have only one export mapping");
        map_put(sources,ex->source,it);
        if (ex->kind==EF_EXPORT_CLASS) {
            Item *old=map_get(classes,key);
            if (old) { Diag *dg=diag_error(d,326,it->span,"duplicate exported class identity");
                diag_label(dg,old->span,"other export here"); }
            map_put(classes,key,it);
        }
    }
    for (uint32_t i=0;i<o.exports.len;i++) {
        EnfusionExport *ex=&o.exports.data[i]; Item *it=ex->item;
        if (ex->kind==EF_EXPORT_CLASS || !it || it->kind!=IT_FN) continue;
        Item *recv=it->fn.recv_decl;
        Str cls=enfusion_export_name(o.exports,recv);
        if (!recv || !cls.len) {
            diag_error(d,326,it->span,"exported methods require an explicitly exported receiver class"); continue;
        }
        Str key=folded(p->a,ex->name);
        bool constructor=ex->kind==EF_EXPORT_CONSTRUCTOR;
        if (!constructor && (str_eq(key,folded(p->a,cls)) || str_eq_c(key,"berylcopy") || str_eq_c(key,"clone")))
            diag_error(d,326,it->span,"exported method conflicts with a constructor or engine/copy helper");
        if (constructor) {
            if (!str_eq(ex->name,cls))
                diag_error(d,326,it->span,"constructor name must exactly match its exported class");
            if (!it->rtype || it->rtype->kind!=TY_VOID || !it->fn.params.len ||
                !it->fn.params.data[0].is_self || it->fn.params.data[0].conv!=CONV_INOUT)
                diag_error(d,326,it->span,"constructor mapping requires an inout self initializer returning void");
            for (uint32_t q=0;q<recv->strukt.fields.len;q++)
                if (!scalar(recv->strukt.fields.data[q].rtype,false))
                    diag_error(d,326,recv->strukt.fields.data[q].span,"initial constructor exports require scalar object state");
        }
        SB b; sb_init(&b,p->a); sb_str(&b,recv->qual_name); sb_char(&b,'.'); sb_str(&b,key);
        Str full=sb_finish(&b); Item *old=map_get(members,full);
        if (old) { Diag *dg=diag_error(d,326,it->span,"duplicate exported method identity");
            diag_label(dg,old->span,"other export here"); }
        map_put(members,full,it);
        if (!scalar(it->rtype,true)) diag_error(d,326,it->span,"initial exported methods support scalar results only");
        for (uint32_t q=0;q<it->fn.params.len;q++) {
            Param *pm=&it->fn.params.data[q];
            if (!pm->is_self && (!scalar(pm->rtype,false) || pm->conv!=CONV_LET))
                diag_error(d,326,pm->span,"initial exported arguments must be read-only bool, i32 or f32 values");
            if (pm->is_self && pm->conv!=CONV_LET && pm->conv!=CONV_INOUT)
                diag_error(d,326,pm->span,"an exported receiver must use let or inout");
            if (!literal_default(pm->deflt))
                diag_error(d,326,pm->span,"exported defaults must be scalar literals in this version");
        }
    }
    return diag_errors(d)==before;
}
