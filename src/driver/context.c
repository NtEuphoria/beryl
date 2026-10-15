/* Compiler-owned context. Every response is bound to the bytes actually read.
 * Admission is deliberately separate from execution and engine verification. */
#include "context.h"
#include "features.h"
#include "binding_context.h"
#include "identity.h"
#include "manifest.h"
#include "../common/fs.h"
#include "../common/hash.h"
#include "../common/json.h"
#include "../lex/lexer.h"
#include "../parse/parser.h"
#include "../sema/check.h"
#include "../sema/ownership.h"
#include "../sema/taint.h"
#include "../back/c_backend.h"
#include "../back/enforce_backend.h"
#include "../reference/reference.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

bool context_optimization_family_known(const char *name) {
    return features_family_known(name);
}

typedef struct {
    Arena *a;
    SourceMap *sm;
    DiagBag *diag;
    Interner *in;
    Program *program;
    ItemVec declarations;
    Manifest manifest;
    bool loaded, checked;
} Context;

static void jstr(SB *b, const char *s) { json_string(b, str_from(s)); }
static void nullable(SB *b, Str s) {
    if (s.len) json_string(b, s); else sb_cstr(b, "null");
}
static const char *kind_name(ItemKind k) {
    switch (k) {
        case IT_FN: return "function";
        case IT_STRUCT: return "struct";
        case IT_ENUM: return "enum";
        case IT_CONST: return "constant";
        case IT_TRAIT: return "trait";
        case IT_TEST: return "test";
        case IT_USE: return "import";
    }
    return "unknown";
}
static bool valid_name(const char *s) {
    size_t len = strlen(s);
    if (!len || len > 512) return false;
    bool first = true;
    for (size_t i = 0; i < len; i++) {
        unsigned char ch = (unsigned char)s[i];
        if (ch == '.') { if (first) return false; first = true; continue; }
        bool letter = (ch >= 'a' && ch <= 'z') || (ch >= 'A' && ch <= 'Z') || ch == '_';
        if (!letter && (first || ch < '0' || ch > '9')) return false;
        first = false;
    }
    return !first;
}
static int item_order(const void *left, const void *right) {
    const Item *a = *(Item * const *)left, *b = *(Item * const *)right;
    uint32_t n = a->qual_name.len < b->qual_name.len ? a->qual_name.len : b->qual_name.len;
    int c = memcmp(a->qual_name.ptr, b->qual_name.ptr, n);
    if (c) return c;
    return (a->qual_name.len > b->qual_name.len) - (a->qual_name.len < b->qual_name.len);
}
static void source_span(Context *c, SB *b, Span span, bool text) {
    SourceFile *file = span_is_none(span) ? NULL : srcmap_get(c->sm, span.file);
    if (!file || span.offset > file->text.len || span.len > file->text.len - span.offset) {
        sb_cstr(b, "null"); return;
    }
    LineCol loc = srcmap_linecol(c->sm, span);
    sb_cstr(b, "{\"path\":"); json_string(b, file->path);
    sb_fmt(b, ",\"byte_offset\":%u,\"byte_length\":%u,\"line\":%u,\"column\":%u,\"column_unit\":\"byte\"",
           span.offset, span.len, loc.line, loc.col);
    if (text) { sb_cstr(b, ",\"text\":"); json_string(b, str_slice(file->text, span.offset, span.len)); }
    sb_char(b, '}');
}
static Str declaration_id(Context *c, Item *it) {
    SB key; sb_init(&key, c->a);
    sb_cstr(&key, "beryl.declaration.v1:"); sb_cstr(&key, kind_name(it->kind));
    sb_char(&key, ':'); sb_str(&key, it->qual_name);
    return hash256_str(c->a, sb_finish(&key));
}
static void type_json(Context *c, SB *b, Type *type) {
    if (!type) { sb_cstr(b, "null"); return; }
    sb_cstr(b, "{\"name\":"); json_string(b, ty_name(c->a, type));
    sb_cstr(b, ",\"declaration\":");
    if (type->decl) json_string(b, type->decl->qual_name); else sb_cstr(b, "null");
    sb_char(b, '}');
}
static void default_json(Context *c, SB *b, Expr *e) {
    if (!e) { sb_cstr(b, "null"); return; }
    source_span(c, b, e->span, true);
}
static void declaration(Context *c, SB *b, Item *it) {
    sb_cstr(b, "{\"declaration_id\":"); json_string(b, declaration_id(c, it));
    sb_cstr(b, ",\"qualified_name\":"); json_string(b, it->qual_name);
    sb_cstr(b, ",\"name\":"); json_string(b, it->name);
    sb_cstr(b, ",\"kind\":"); jstr(b, kind_name(it->kind));
    sb_cstr(b, ",\"visibility\":"); jstr(b, it->is_pub ? "public" : "module_private");
    sb_cstr(b, ",\"module\":"); json_string(b, path_str(c->a, ((Module *)it->owner)->path));
    sb_cstr(b, ",\"source\":"); source_span(c, b, it->span, true);
    sb_cstr(b, ",\"documentation\":"); json_string(b, it->doc);
    sb_cstr(b, ",\"attributes\":[");
    for (uint32_t i = 0; i < it->attrs.len; i++) {
        Attr at = it->attrs.data[i]; if (i) sb_char(b, ',');
        sb_cstr(b, "{\"name\":"); json_string(b, at.name);
        sb_cstr(b, ",\"argument\":"); json_string(b, at.arg);
        sb_cstr(b, ",\"source\":"); source_span(c, b, at.span, true); sb_char(b, '}');
    }
    sb_cstr(b, "],\"effects\":{\"status\":\"unavailable\",\"reason\":\"No complete interprocedural effect contract is exposed; attributes are source requirements, not inferred purity.\"}");
    if (it->kind == IT_FN) {
        sb_cstr(b, ",\"receiver\":");
        if (it->fn.recv_decl) json_string(b, it->fn.recv_decl->qual_name); else sb_cstr(b, "null");
        sb_cstr(b, ",\"return_type\":"); type_json(c, b, it->rtype);
        sb_cstr(b, ",\"parameters\":[");
        for (uint32_t i = 0; i < it->fn.params.len; i++) {
            Param p = it->fn.params.data[i]; if (i) sb_char(b, ',');
            sb_cstr(b, "{\"name\":"); json_string(b, p.name);
            sb_cstr(b, ",\"access_mode\":"); jstr(b, conv_name(p.conv));
            sb_fmt(b, ",\"is_self\":%s,\"type\":", p.is_self ? "true" : "false"); type_json(c, b, p.rtype);
            sb_cstr(b, ",\"default\":"); default_json(c, b, p.deflt);
            sb_cstr(b, ",\"source\":"); source_span(c, b, p.span, true); sb_char(b, '}');
        }
        sb_cstr(b, "],\"generic_parameters\":[");
        for (uint32_t i = 0; i < it->fn.generics.len; i++) {
            GenericParam g = it->fn.generics.data[i]; if (i) sb_char(b, ',');
            sb_cstr(b, "{\"name\":"); json_string(b, g.name);
            sb_cstr(b, ",\"bound\":"); nullable(b, g.bound); sb_char(b, '}');
        }
        sb_char(b, ']');
    } else if (it->kind == IT_STRUCT) {
        sb_cstr(b, ",\"generic_parameters\":[");
        for (uint32_t i = 0; i < it->strukt.generics.len; i++) {
            GenericParam g = it->strukt.generics.data[i]; if (i) sb_char(b, ',');
            sb_cstr(b, "{\"name\":"); json_string(b, g.name);
            sb_cstr(b, ",\"bound\":"); nullable(b, g.bound); sb_char(b, '}');
        }
        sb_cstr(b, "],\"fields\":[");
        for (uint32_t i = 0; i < it->strukt.fields.len; i++) {
            Field f = it->strukt.fields.data[i]; if (i) sb_char(b, ',');
            sb_cstr(b, "{\"name\":"); json_string(b, f.name);
            sb_cstr(b, ",\"type\":"); type_json(c, b, f.rtype);
            sb_cstr(b, ",\"documentation\":"); json_string(b, f.doc);
            sb_cstr(b, ",\"default\":"); default_json(c, b, f.deflt);
            sb_cstr(b, ",\"source\":"); source_span(c, b, f.span, true); sb_char(b, '}');
        }
        sb_char(b, ']');
    } else if (it->kind == IT_CONST) {
        sb_cstr(b, ",\"type\":"); type_json(c, b, it->rtype);
    }
    sb_char(b, '}');
}
static void load_inputs(Context *c, int nfiles, char **files) {
    c->manifest = manifest_load(c->a, c->diag, ".");
    if (c->manifest.found) srcmap_add(c->sm, STR_LIT("beryl.toml"), c->manifest.source_text);
    if (diag_errors(c->diag)) return;
    if (!nfiles && c->manifest.found) {
        PathVec paths = list_beryl_files(c->a, "src");
        nfiles = (int)paths.len;
        files = ARENA_ARRAY(c->a, char *, (size_t)(nfiles ? nfiles : 1));
        for (int i = 0; i < nfiles; i++) files[i] = str_cstr(c->a, paths.data[i]);
        if (!nfiles) diag_error(c->diag, 802, SPAN_NONE, "no .be files found under src/");
    }
    if (nfiles > 256) { diag_error(c->diag, 804, SPAN_NONE, "context accepts at most 256 source files"); return; }
    uint64_t bytes = 0;
    for (int i = 0; i < nfiles && !diag_errors(c->diag); i++) {
        Str txt;
        if (!fs_read(c->a, files[i], &txt)) { diag_error(c->diag, 803, SPAN_NONE, "cannot read source file `%s`", files[i]); break; }
        bytes += txt.len;
        if (bytes > 64 * 1024 * 1024ULL) { diag_error(c->diag, 804, SPAN_NONE, "context source input exceeds 64 MiB"); break; }
        uint32_t file = srcmap_add(c->sm, str_from(files[i]), txt);
        TokenVec tokens = lex_file(c->a, c->sm, c->diag, c->in, file);
        prog_add_module(c->program, parse_file(c->a, c->diag, c->in, tokens, file));
    }
    c->loaded = c->program->modules.len != 0;
    if (!c->loaded || diag_errors(c->diag)) return;
    if (!resolve_program(c->diag, c->program) || !check_program(c->diag, c->program) ||
        !ownership_check(c->diag, c->program) ||
        !taint_check(c->diag, c->program, (SecurityOpts){c->manifest.forbid_unsafe})) return;
    c->checked = true;
    for (uint32_t m = 0; m < c->program->modules.len; m++) {
        Module *module = c->program->modules.data[m];
        for (uint32_t i = 0; i < module->items.len; i++) {
            Item *it = module->items.data[i];
            if (it->kind != IT_USE && it->kind != IT_TEST) vec_push(c->a, c->declarations, it);
        }
    }
    if (c->declarations.len > 1) qsort(c->declarations.data, c->declarations.len, sizeof(Item *), item_order);
}
static void admission(Context *c, SB *b, const char *name) {
    sb_cstr(b, "{\"status\":");
    DiagBag *d = diag_new(c->a, c->sm);
    bool ok = false;
    if (c->checked) {
        if (!strcmp(name, "reference")) ok = reference_admit(d, c->program);
        else if (!strcmp(name, "native")) ok = native_lint(d, c->a, c->program);
        else ok = enfusion_lint(d, c->program, (EnfusionOpts){
            .prefix = str_empty(c->manifest.enfusion_prefix) ? STR_LIT("BE") : c->manifest.enfusion_prefix});
    }
    jstr(b, c->checked ? (ok ? "admitted" : "unavailable") : "not_checked");
    sb_cstr(b, ",\"scope\":\"all_loaded_declarations\",\"execution\":\"not_run\",\"engine_verification\":\"not_run\",\"diagnostics\":");
    sb_str(b, diag_render_json(c->a, d)); sb_char(b, '}');
}
static void capabilities(Context *c, SB *b) {
    sb_cstr(b, "{\"frontend\":{\"representation\":\"typed_AST\",\"status\":");
    jstr(b, c->checked ? "checked" : "not_checked");
    sb_cstr(b, "},\"reference\":"); admission(c, b, "reference");
    sb_cstr(b, ",\"native\":"); admission(c, b, "native");
    sb_cstr(b, ",\"enfusion\":"); admission(c, b, "enfusion");
    sb_cstr(b, ",\"structured_IR\":\"not_released\",\"effect_contracts\":\"unavailable\",\"engine_binding_registry\":\"bounded_snapshot\",\"optimization_plans\":\"none_released\"");
    sb_cstr(b, ",\"ir_differential_tests\":\"experimental_native_test_profile\"");
    sb_cstr(b, ",\"native_evidence\":{\"status\":\"implemented\",\"execution\":\"not_run\",\"required_capability\":\"clang.c11.ir.assembly\",\"tool_identity\":\"selected executable; dependent SDK and linker binaries not fingerprinted\",\"measurements\":\"not_measured\"}");
    sb_cstr(b, ",\"expected_trap_differential\":{\"status\":\"implemented_bounded\",\"execution\":\"not_run\",\"traps\":[\"overflow\",\"division_by_zero\",\"bounds\"],\"site_identity\":\"loaded source file ID and byte offset\",\"observations\":\"ordered test/assert/print events and stdout; optional one registered initialized top-level test-local i32 array\",\"maximum_watched_elements\":4096,\"failure_exclusions\":[\"timeout\",\"cancellation\",\"budget\",\"unavailable\",\"incomplete_trace\"]}");
    sb_cstr(b, ",\"enfusion_source_map\":{\"status\":\"implemented\",\"schema_version\":1,\"precision\":\"generated line to original byte span\",\"default_expansion\":\"template span and outermost request site; full nested expansion chain unavailable\",\"engine_column_interpolation\":\"unavailable\",\"engine_verification\":\"not_run\"}");
    sb_cstr(b, ",\"engine_scenarios\":{\"status\":\"tool_owned\",\"discovery\":\"installed local mod tooling\",\"engine_verification\":\"not_run\"}}");
}
static Item *lookup(Context *c, const char *query, SB *candidates) {
    Item *found = NULL; uint32_t count = 0; bool qualified = strchr(query, '.') != NULL;
    sb_char(candidates, '[');
    for (uint32_t i = 0; i < c->declarations.len; i++) {
        Item *it = c->declarations.data[i];
        if (!str_eq_c(qualified ? it->qual_name : it->name, query)) continue;
        if (count++) sb_char(candidates, ',');
        json_string(candidates, it->qual_name); found = it;
    }
    sb_char(candidates, ']');
    if (count == 1) return found;
    Diag *d = diag_error(c->diag, 811, SPAN_NONE, count ? "ambiguous context symbol `%s`" : "unknown context symbol `%s`", query);
    diag_help(d, "use a fully qualified declaration name and include its source files");
    return NULL;
}

int context_command(int argc, char **argv, const char *compiler_version) {
    Context c = {0}; c.a = arena_new(0); c.sm = srcmap_new(c.a);
    c.diag = diag_new(c.a, c.sm); c.in = intern_new(c.a); c.program = prog_new(c.a);
    const char *topic = argc ? argv[0] : "", *query = NULL;
    const char *engine_executable = NULL, *api_root = NULL;
    bool project = !strcmp(topic, "project"), symbol = !strcmp(topic, "symbol");
    bool binding = !strcmp(topic, "binding"), optimization = !strcmp(topic, "optimization"), list = false;
    bool inventory = !strcmp(topic, "capabilities"), examples = !strcmp(topic, "examples");
    bool target_seen = false; uint32_t target_mask = FEATURE_ALL;
    char **files = ARENA_ARRAY(c.a, char *, (size_t)(argc ? argc : 1)); int nfiles = 0;
    bool positional = false;
    if (!project && !symbol && !binding && !optimization && !inventory && !examples)
        diag_error(c.diag, 804, SPAN_NONE, "context topic must be project, symbol, binding, optimization, capabilities, or examples");
    for (int i = 1; i < argc; i++) {
        if (!positional && !strcmp(argv[i], "--")) { positional = true; continue; }
        if (!positional && !strcmp(argv[i], "--format")) {
            if (++i >= argc || strcmp(argv[i], "json")) diag_error(c.diag, 804, SPAN_NONE, "context supports --format json only");
        } else if (!positional && (inventory || examples) && !strcmp(argv[i], "--target")) {
            if (target_seen || ++i >= argc || !(target_mask = features_target(argv[i])))
                diag_error(c.diag, 804, SPAN_NONE, "catalogue target must be native, reference, enfusion, compiler, or tooling and cannot repeat");
            target_seen = true;
        } else if (!positional && binding && (!strcmp(argv[i], "--engine-executable") || !strcmp(argv[i], "--api-root"))) {
            const char **destination = !strcmp(argv[i], "--api-root") ? &api_root : &engine_executable;
            if (*destination || ++i >= argc || !argv[i][0]) diag_error(c.diag, 804, SPAN_NONE, "binding identity options require one nonempty path and cannot repeat");
            else *destination = argv[i];
        } else if (!positional && !strcmp(argv[i], "--list") && optimization) list = true;
        else if (!positional && argv[i][0] == '-') diag_error(c.diag, 804, SPAN_NONE, "unknown context option `%s`", argv[i]);
        else if (!project && !query && !list) query = argv[i];
        else files[nfiles++] = argv[i];
    }
    if (!project && !list && !inventory && !examples && !query) diag_error(c.diag, 804, SPAN_NONE, "this context topic requires a name");
    if (query && !valid_name(query)) diag_error(c.diag, 804, SPAN_NONE, "context names must be dot-separated identifiers (at most 512 bytes)");
    if ((binding || list || inventory || examples) && nfiles) diag_error(c.diag, 804, SPAN_NONE, "binding lookup, catalogue lookup, and optimization --list do not accept source files");
    if (list && query) diag_error(c.diag, 804, SPAN_NONE, "optimization --list cannot also select a symbol");
    if (!diag_errors(c.diag) && (project || symbol || (optimization && !list))) load_inputs(&c, nfiles, files);
    if (!diag_errors(c.diag) && (symbol || (optimization && !list)) && !c.loaded)
        diag_error(c.diag, 804, SPAN_NONE, "symbol context requires .be inputs or a beryl.toml package");
    SB matches; sb_init(&matches, c.a); Item *selected = NULL;
    if (!diag_errors(c.diag) && query && !binding && !inventory && !examples) selected = lookup(&c, query, &matches);
    FeatureIssue registry_issue = {0};
    if (!diag_errors(c.diag) && !features_validate(features_registry(), &registry_issue))
        diag_error(c.diag, 804, SPAN_NONE, "invalid compiler capability registry: %s (%s)", registry_issue.kind, registry_issue.id ? registry_issue.id : "registry");
    if (!diag_errors(c.diag) && query && (inventory || examples)) {
        const Feature *f = inventory ? features_find(features_registry(), query) : NULL;
        const FeatureExample *e = examples ? features_example_find(features_registry(), query) : NULL;
        if (!f && !e) diag_error(c.diag, 804, SPAN_NONE, "unknown %s `%s`", inventory ? "capability" : "example", query);
        else if (!((f ? f->targets : e->targets) & target_mask))
            diag_error(c.diag, 804, SPAN_NONE, "selected %s has no entry for the requested target", inventory ? "capability" : "example");
    }
    BindingContext binding_result = {0};
    if (binding && !diag_errors(c.diag)) binding_result = binding_context(c.a, query, engine_executable, api_root);
    const char *status = diag_errors(c.diag) ? "failure" : binding ? binding_result.status : "success";
    SB b; sb_init(&b, c.a);
    sb_cstr(&b, "{\"schema_version\":1,\"operation\":");
    SB op; sb_init(&op, c.a); sb_cstr(&op, "context."); sb_cstr(&op, topic); json_string(&b, sb_finish(&op));
    sb_cstr(&b, ",\"stage\":\"context\",\"status\":"); jstr(&b, status);
    sb_cstr(&b, ",\"compiler_version\":"); jstr(&b, compiler_version ? compiler_version : "unknown");
    sb_cstr(&b, ",\"working_directory\":");
    const char *directory = fs_absolute(c.a, ".");
    if (directory) jstr(&b, directory); else sb_cstr(&b, "null");
    sb_cstr(&b, ",\"compiler_fingerprint\":"); nullable(&b, identity_compiler(c.a));
    Str sources = identity_sources(c.a, c.sm);
    sb_cstr(&b, ",\"source_fingerprint\":"); json_string(&b, hash256_str(c.a, sources));
    sb_cstr(&b, ",\"binding_fingerprint\":"); nullable(&b, binding_result.fingerprint);
    sb_cstr(&b, ",\"artifact_fingerprint\":null,\"sources\":"); sb_str(&b, sources);
    sb_cstr(&b, ",\"execution\":\"not_run\",\"diagnostics\":"); sb_str(&b, diag_render_json(c.a, c.diag));
    sb_cstr(&b, ",\"data\":");
    if (diag_errors(c.diag)) {
        sb_cstr(&b, "null,\"candidates\":"); sb_str(&b, matches.len ? sb_finish(&matches) : STR_LIT("[]"));
    } else if (binding) {
        sb_str(&b, binding_result.data);
    } else if (inventory || examples) {
        sb_str(&b, inventory ? features_catalog_json(c.a, query, target_mask) : features_examples_json(c.a, query, target_mask));
    } else {
        sb_char(&b, '{');
        if (selected) { sb_cstr(&b, "\"symbol\":"); declaration(&c, &b, selected); sb_char(&b, ','); }
        if (project) {
            sb_cstr(&b, "\"project\":{\"manifest_found\":"); sb_cstr(&b, c.manifest.found ? "true" : "false");
            sb_cstr(&b, ",\"name\":"); nullable(&b, c.manifest.name);
            sb_cstr(&b, ",\"version\":"); nullable(&b, c.manifest.version); sb_cstr(&b, "},\"declarations\":[");
            for (uint32_t i = 0; i < c.declarations.len; i++) { if (i) sb_char(&b, ','); declaration(&c, &b, c.declarations.data[i]); }
            sb_cstr(&b, "],");
        }
        sb_cstr(&b, "\"capabilities\":"); capabilities(&c, &b);
        sb_cstr(&b, ",\"optimization_families\":"); sb_str(&b, features_families_json(c.a));
        sb_cstr(&b, ",\"catalogue\":{\"schema_version\":1,\"registry_fingerprint\":"); json_string(&b, features_fingerprint(c.a));
        sb_cstr(&b, ",\"discovery\":\"beryl context capabilities\",\"examples\":\"beryl context examples\"}");
        sb_cstr(&b, ",\"released_plans\":[],\"measurements\":null}");
    }
    sb_cstr(&b, "}\n"); Str response = sb_finish(&b);
    int rc = diag_errors(c.diag) ? 1 : strcmp(status, "success") ? 3 : 0;
    if (fwrite(response.ptr, 1, response.len, stdout) != response.len || fflush(stdout)) rc = 2;
    arena_free(c.a); return rc;
}
