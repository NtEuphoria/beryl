/* main.c — the beryl CLI.
 *
 * Subcommands grow as the compiler does; `build`, `run` and `test` arrive with
 * the backends. Everything here is deliberately thin: the driver reads files,
 * runs passes in order, and prints diagnostics.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#ifdef _WIN32
#include <io.h>
#include <fcntl.h>
#endif

#include "../common/arena.h"
#include "../common/diag.h"
#include "../common/fs.h"
#include "../common/json.h"
#include "../common/hash.h"
#include "../common/source.h"
#include "../lex/lexer.h"
#include "../parse/parser.h"
#include "../parse/print.h"
#include "../sema/check.h"
#include "../back/enforce_backend.h"
#include "../sema/taint.h"
#include "audit.h"
#include "build.h"
#include "manifest.h"
#include "identity.h"
#include "reference_driver.h"
#include "mod_driver.h"
#include "context.h"
#include "doctor.h"
#include "analyze.h"
#include "mcp_driver.h"
#include "../sema/ownership.h"
#include "../sema/resolve.h"

#define BERYL_VERSION "0.1.0-dev"

typedef struct {
    Arena     *a;
    SourceMap *sm;
    DiagBag   *d;
    Interner  *in;
    Program   *p;
} Ctx;

static Str read_file(Arena *a, const char *path, bool *ok) {
    Str out;
    *ok = fs_read(a, path, &out);
    return out;
}

static Ctx ctx_new(void) {
    Ctx c = {0};
    c.a   = arena_new(0);
    c.sm  = srcmap_new(c.a);
    c.d   = diag_new(c.a, c.sm);
    c.in  = intern_new(c.a);
    c.p   = prog_new(c.a);
    return c;
}

/* Parses one file into the program. Returns the module, or NULL on read
 * failure (already reported). */
static Module *load(Ctx *c, const char *path) {
    bool ok  = false;
    Str  txt = read_file(c->a, path, &ok);
    if (!ok) {
        diag_error(c->d, 803, SPAN_NONE, "cannot read source file `%s`", path);
        return NULL;
    }
    uint32_t file = srcmap_add(c->sm, str_from(path), txt);
    TokenVec toks = lex_file(c->a, c->sm, c->d, c->in, file);
    Module  *m    = parse_file(c->a, c->d, c->in, toks, file);
    prog_add_module(c->p, m);
    return m;
}

static int report(Ctx *c) {
    if (diag_any(c->d)) diag_render(c->d, stderr, true);
    uint32_t e = diag_errors(c->d);
    uint32_t w = diag_warnings(c->d);
    if (e) {
        fprintf(stderr, "\n%u error%s", e, e == 1 ? "" : "s");
        if (w) fprintf(stderr, ", %u warning%s", w, w == 1 ? "" : "s");
        fprintf(stderr, "\n");
        return 1;
    }
    if (w) fprintf(stderr, "\n%u warning%s\n", w, w == 1 ? "" : "s");
    return 0;
}

static int cmd_ast(int argc, char **argv) {
    if (argc < 1) {
        fprintf(stderr, "usage: beryl ast <file.be>\n");
        return 2;
    }
    Ctx     c = ctx_new();
    Module *m = load(&c, argv[0]);
    if (!m) { report(&c); arena_free(c.a); return 2; }
    Str s = ast_print(c.a, m);
    fwrite(s.ptr, 1, s.len, stdout);
    int rc = diag_errors(c.d) ? report(&c) : 0;
    arena_free(c.a);
    return rc;
}

static int cmd_fmt(int argc, char **argv) {
    bool check_only = false;
    int  i          = 0;
    if (argc > 0 && strcmp(argv[0], "--check") == 0) {
        check_only = true;
        i          = 1;
    }
    if (i >= argc) {
        fprintf(stderr, "usage: beryl fmt [--check] <file.be>...\n");
        return 2;
    }

    int rc = 0;
    for (; i < argc; i++) {
        Ctx     c = ctx_new();
        Module *m = load(&c, argv[i]);
        if (!m) {
            report(&c);
            arena_free(c.a);
            return 2;
        }
        if (diag_errors(c.d)) {
            report(&c);
            arena_free(c.a);
            return 1;
        }
        Str out = ast_format(c.a, m);

        bool ok  = false;
        Str  orig = read_file(c.a, argv[i], &ok);
        if (check_only) {
            if (!str_eq(orig, out)) {
                fprintf(stderr, "%s is not formatted\n", argv[i]);
                rc = 1;
            }
        } else if (!str_eq(orig, out)) {
            if (!fs_write(argv[i], out)) {
                fprintf(stderr, "beryl: cannot write %s\n", argv[i]);
                arena_free(c.a);
                return 2;
            }
            printf("formatted %s\n", argv[i]);
        }
        arena_free(c.a);
    }
    return rc;
}

/* Loads every file, then runs resolve, check and ownership in order. Each
 * stage only runs when the previous one was clean, so a syntax error never
 * produces a cascade of invented type errors. */
static bool frontend(Ctx *c, int nfiles, char **files, bool forbid_unsafe) {
    if (diag_errors(c->d)) return false;
    for (int i = 0; i < nfiles; i++)
        if (!load(c, files[i])) return false;
    if (diag_errors(c->d)) return false;

    if (!resolve_program(c->d, c->p)) return false;
    if (!check_program(c->d, c->p)) return false;
    if (!ownership_check(c->d, c->p)) return false;

    SecurityOpts so = {forbid_unsafe};
    if (!taint_check(c->d, c->p, so)) return false;
    return true;
}

typedef struct {
    const char *out;
    bool        release;
    bool        emit_c;
    bool        enfusion;
    bool        invalid;
    bool        tests;
    bool        json;
    const char *clang;
    uint32_t    timeout_ms;
    const char *prefix;
    const char *out_dir;
    EnfusionExports exports;
    const char *backend;
    const char *lowering;
    const char *optimization;
    bool save_native_evidence;
    const char *source_map;
    Str disabled_optimizations_json;
    RefOpts reference;
    int         nfiles;
    char      **files;
} Flags;

static Flags parse_flags(Ctx *c, int argc, char **argv) {
    Arena *a = c->a;
    Flags f  = {0};
    f.timeout_ms = 120000;
    f.files  = ARENA_ARRAY(a, char *, argc > 0 ? argc : 1);
    SB disabled; sb_init(&disabled, a); sb_char(&disabled, '[');
    unsigned disabled_count = 0;
    for (int i = 0; i < argc; i++) {
        if (strcmp(argv[i], "--release") == 0) f.release = true;
        else if (strcmp(argv[i], "--emit-c") == 0) f.emit_c = true;
        else if (strcmp(argv[i], "--tests") == 0) f.tests = true;
        else if ((!strcmp(argv[i], "--lowering") || !strcmp(argv[i], "--opt")) && i+1<argc) {
            bool lowering = !strcmp(argv[i], "--lowering");
            const char *option = argv[i], *value = argv[++i];
            const char **destination = lowering ? &f.lowering : &f.optimization;
            if (*destination || (lowering ? (strcmp(value,"auto") && strcmp(value,"ast") && strcmp(value,"ir")) :
                                          (strcmp(value,"auto") && strcmp(value,"off")))) {
                diag_error(c->d,804,SPAN_NONE,"invalid or duplicate %s; use %s",option,lowering?"auto, ast, or ir":"auto or off"); f.invalid=true;
            } else *destination = value;
        }
        else if (!strcmp(argv[i], "--disable-opt") && i+1<argc) {
            const char *family = argv[++i];
            if (!context_optimization_family_known(family)) {
                diag_error(c->d,804,SPAN_NONE,"unknown optimization family `%s`; use context optimization --list",family); f.invalid=true;
            } else {
                if (disabled_count++) sb_char(&disabled, ',');
                json_string(&disabled, str_from(family));
            }
        }
        else if (!strcmp(argv[i], "--save-native-evidence")) f.save_native_evidence = true;
        else if (!strcmp(argv[i], "--source-map") && i+1<argc) f.source_map = argv[++i];
        else if (!strcmp(argv[i], "--expect-source-trap") && i+1<argc) {
            const char *value = argv[++i];
            if (f.reference.expected_trap.enabled || !driver_parse_expected_trap(value, &f.reference.expected_trap)) {
                diag_error(c->d,804,SPAN_NONE,"expected trap must be a single kind@file_id:byte_offset; kinds: overflow, division_by_zero, bounds"); f.invalid=true;
            }
        }
        else if (strcmp(argv[i],"--backend")==0 && i+1<argc) {
            f.backend=argv[++i];
            if (strcmp(f.backend,"native") && strcmp(f.backend,"reference") && strcmp(f.backend,"differential")) {
                diag_error(c->d,804,SPAN_NONE,"test backend must be native, reference, or differential"); f.invalid=true;
            }
        }
        else if ((!strcmp(argv[i],"--max-steps") || !strcmp(argv[i],"--max-bytes") || !strcmp(argv[i],"--max-call-depth")) && i+1<argc) {
            const char *option=argv[i], *value=argv[++i];
            char *end; errno=0; unsigned long long n=strtoull(value,&end,10);
            unsigned long long limit=!strcmp(option,"--max-steps") ? 1000000000ULL :
                !strcmp(option,"--max-bytes") ? 536870912ULL : 128ULL;
            if (!*value || value[0]=='-' || value[0]=='+' || *end || errno || !n || n>limit) {
                diag_error(c->d,804,SPAN_NONE,"%s must be an integer from 1 through %llu",option,limit); f.invalid=true;
            } else if (!strcmp(option,"--max-steps")) f.reference.max_steps=n;
            else if (!strcmp(option,"--max-bytes")) f.reference.max_bytes=n;
            else f.reference.max_call_depth=(uint32_t)n;
        }
        else if (!strcmp(argv[i], "--observe-root") && i+1<argc) {
            const char *value = argv[++i];
            if (f.reference.watch_root.enabled || !driver_parse_watch_root(value, &f.reference.watch_root)) {
                diag_error(c->d,804,SPAN_NONE,"observed root must be a single file_id:declaration_byte_offset"); f.invalid=true;
            }
        }
        else if (strcmp(argv[i], "--clang") == 0 && i + 1 < argc) f.clang = argv[++i];
        else if (strcmp(argv[i], "--format") == 0 && i + 1 < argc) {
            const char *format = argv[++i];
            if (strcmp(format, "json") == 0) f.json = true;
            else if (strcmp(format, "human") != 0) {
                diag_error(c->d, 804, SPAN_NONE, "unknown diagnostic format `%s`", format);
                f.invalid = true;
            }
        } else if (strcmp(argv[i], "--timeout-ms") == 0 && i + 1 < argc) {
            const char *value = argv[++i];
            char *end; errno = 0;
            unsigned long n = strtoul(value, &end, 10);
            if (!*value || value[0] == '-' || value[0] == '+' || *end || errno || n == 0 || n > UINT32_MAX) {
                diag_error(c->d, 804, SPAN_NONE, "timeout must be a positive integer in milliseconds"); f.invalid = true;
            } else f.timeout_ms = (uint32_t)n;
        }
        else if (strcmp(argv[i], "-o") == 0 && i + 1 < argc) f.out = argv[++i];
        else if ((strcmp(argv[i], "-t") == 0 || strcmp(argv[i], "--target") == 0) &&
                 i + 1 < argc) {
            const char *t = argv[++i];
            if (strcmp(t, "enfusion") == 0) f.enfusion = true;
            else if (strcmp(t, "native") != 0) {
                diag_error(c->d, 804, SPAN_NONE, "unknown target `%s`; use native or enfusion", t);
                f.invalid = true;
            }
        } else if ((strcmp(argv[i], "--export-class") == 0 || strcmp(argv[i], "--export-method") == 0 ||
                    strcmp(argv[i], "--export-constructor") == 0) && i + 1 < argc) {
            EnfusionExport ex={0};
            ex.kind = strcmp(argv[i], "--export-class") == 0 ? EF_EXPORT_CLASS :
                strcmp(argv[i], "--export-method") == 0 ? EF_EXPORT_METHOD : EF_EXPORT_CONSTRUCTOR;
            const char *value=argv[++i], *eq=strchr(value,'=');
            if (!eq || eq==value || !eq[1] || strchr(eq+1,'=')) {
                diag_error(c->d,804,SPAN_NONE,"export mapping must be qualified.declaration=EngineName"); f.invalid=true;
            } else {
                ex.source=str_new(value,(uint32_t)(eq-value)); ex.name=str_from(eq+1);
                vec_push(a,f.exports,ex);
            }
        } else if (strcmp(argv[i], "--prefix") == 0 && i + 1 < argc) f.prefix = argv[++i];
        else if (strcmp(argv[i], "--out-dir") == 0 && i + 1 < argc) f.out_dir = argv[++i];
        else if (argv[i][0] == '-') {
            diag_error(c->d, 804, SPAN_NONE, "unknown option or missing option value: %s", argv[i]);
            f.invalid = true;
        } else f.files[f.nfiles++] = argv[i];
    }
    if (f.exports.len && !f.enfusion) {
        diag_error(c->d,804,SPAN_NONE,"export mappings require --target enfusion"); f.invalid=true;
    }
    sb_char(&disabled, ']');
    f.disabled_optimizations_json = sb_finish(&disabled);
    if (f.reference.expected_trap.enabled && (!f.backend || strcmp(f.backend,"differential"))) {
        diag_error(c->d,804,SPAN_NONE,"expected source traps require test --backend differential"); f.invalid=true;
    }
    if (f.source_map && (!f.enfusion || !f.out_dir)) {
        diag_error(c->d,804,SPAN_NONE,"--source-map requires --target enfusion and explicit --out-dir"); f.invalid=true;
    }
    if (f.reference.watch_root.enabled && !f.reference.expected_trap.enabled) {
        diag_error(c->d,804,SPAN_NONE,"--observe-root requires --expect-source-trap and differential execution"); f.invalid=true;
    }
    if ((f.reference.max_steps || f.reference.max_bytes || f.reference.max_call_depth) &&
        (!f.backend || !strcmp(f.backend,"native"))) {
        diag_error(c->d,804,SPAN_NONE,"reference budgets require --backend reference or differential"); f.invalid=true;
    }
    return f;
}

static void reject_build_options(Ctx *c, Flags *f) {
    if (f->lowering || f->optimization || f->save_native_evidence || f->source_map || f->disabled_optimizations_json.len > 2) {
        diag_error(c->d,804,SPAN_NONE,"lowering, optimization and native-evidence options require build, run, or test"); f->invalid=true;
    }
}

/* When no files are named, a package builds itself: beryl.toml is read and
 * every .be under src/ is compiled, in sorted order so a build is
 * reproducible. */
static Manifest resolve_inputs(Ctx *c, Flags *f) {
    Manifest m = manifest_load(c->a, c->d, ".");
    if (m.found) srcmap_add(c->sm, str_from("beryl.toml"), m.source_text);
    if (!f->prefix) f->prefix = str_empty(m.enfusion_prefix) ? "BE" : str_cstr(c->a, m.enfusion_prefix);
    if (!f->out_dir && !str_empty(m.enfusion_out)) f->out_dir = str_cstr(c->a, m.enfusion_out);
    if (f->nfiles > 0) return m;
    if (!m.found) return m;

    PathVec files = list_beryl_files(c->a, "src");
    if (files.len == 0) {
        Diag *dg = diag_error(c->d, 802, SPAN_NONE, "no .be files found under src/");
        diag_help(dg, "put your sources in src/, or name them on the command line");
        return m;
    }
    f->files = ARENA_ARRAY(c->a, char *, files.len);
    for (uint32_t i = 0; i < files.len; i++)
        f->files[f->nfiles++] = str_cstr(c->a, files.data[i]);

    return m;
}

static bool write_text_file(const char *path, const char *content) {
    return fs_write(path, str_from(content));
}

static int cmd_new(int argc, char **argv) {
    if (argc < 1) {
        fprintf(stderr, "usage: beryl new <name>\n");
        return 2;
    }
    const char *name = argv[0];
    /* This argument is a package name, not an arbitrary path or TOML fragment. */
    if (!*name || strlen(name) > 100) { fprintf(stderr, "beryl: invalid package name\n"); return 2; }
    for (const char *p = name; *p; p++) {
        if (!((*p >= 'a' && *p <= 'z') || (*p >= 'A' && *p <= 'Z') ||
              (*p >= '0' && *p <= '9') || *p == '_' || *p == '-')) {
            fprintf(stderr, "beryl: package names use letters, digits, underscores, or hyphens\n"); return 2;
        }
    }

    char dir[512], src[512], path[640];
    snprintf(dir, sizeof dir, "%s", name);
    snprintf(src, sizeof src, "%s/src", name);
    if (!fs_mkdir(dir) || !fs_mkdir(src)) {
        fprintf(stderr, "beryl: cannot create a new package directory; existing paths are preserved\n"); return 2;
    }

    char toml[1024];
    snprintf(toml, sizeof toml,
             "[package]\n"
             "name    = \"%s\"\n"
             "version = \"0.1.0\"\n"
             "\n"
             "[security]\n"
             "# No dependency can execute code at build time; Beryl has no build\n"
             "# scripts and no procedural macros. This forbids @unsafe as well.\n"
             "forbid_unsafe = true\n"
             "\n"
             "# Uncomment to also emit EnforceScript for Arma Reforger:\n"
             "# [target.enfusion]\n"
             "# prefix = \"%s\"\n"
             "# out    = \"../MyMod/scripts/Game/MyMod\"\n",
             name, "MOD");
    snprintf(path, sizeof path, "%s/beryl.toml", dir);
    if (!write_text_file(path, toml)) {
        fprintf(stderr, "beryl: cannot write %s\n", path);
        return 2;
    }

    const char *main_be =
        "//! A new Beryl package.\n"
        "\n"
        "module main\n"
        "\n"
        "pub struct Counter {\n"
        "    n: i32 = 0\n"
        "    step: i32 = 1\n"
        "}\n"
        "\n"
        "pub fn Counter.bump(inout self) {\n"
        "    self.n += self.step\n"
        "}\n"
        "\n"
        "fn main() {\n"
        "    var c = Counter{ step: 5 }\n"
        "    c.bump()\n"
        "    c.bump()\n"
        "    print(\"counter = \")\n"
        "    println(c.n)\n"
        "}\n"
        "\n"
        "test \"bump advances by the step\" {\n"
        "    var c = Counter{ step: 5 }\n"
        "    c.bump()\n"
        "    assert(c.n == 5)\n"
        "    c.bump()\n"
        "    assert(c.n == 10)\n"
        "}\n";
    snprintf(path, sizeof path, "%s/src/main.be", dir);
    if (!write_text_file(path, main_be)) {
        fprintf(stderr, "beryl: cannot write %s\n", path);
        return 2;
    }

    printf("created %s\n", name);
    printf("  cd %s\n", name);
    printf("  beryl test     # runs the test block natively\n");
    printf("  beryl run      # builds and runs\n");
    return 0;
}

/* Derives `build/<stem>.exe` from the first input file. */
static Str default_out(Arena *a, const char *first) {
    Str  p    = str_from(first);
    uint32_t start = 0, end = p.len;
    for (uint32_t i = 0; i < p.len; i++)
        if (p.ptr[i] == '/' || p.ptr[i] == '\\') start = i + 1;
    for (uint32_t i = start; i < p.len; i++)
        if (p.ptr[i] == '.') end = i;
    SB sb;
    sb_init(&sb, a);
    sb_cstr(&sb, ".beryl-cache/");
    sb_str(&sb, str_new(p.ptr + start, end - start));
    sb_cstr(&sb, ".exe");
    return sb_finish(&sb);
}

static int cmd_build(int argc, char **argv, CgenMode mode, bool then_run) {
    Ctx      c = ctx_new();
    Flags    f = parse_flags(&c, argc, argv);
    if (f.backend && mode!=CGEN_TESTS) { diag_error(c.d,804,SPAN_NONE,"--backend is supported by test only"); f.invalid=true; }
    if (f.save_native_evidence && (f.enfusion || (f.backend && !strcmp(f.backend,"reference")))) {
        diag_error(c.d,804,SPAN_NONE,"native evidence requires native compilation"); f.invalid=true;
    }
    if (f.backend && !strcmp(f.backend,"reference") &&
        (f.optimization || f.disabled_optimizations_json.len > 2 || (f.lowering && strcmp(f.lowering,"ast")))) {
        diag_error(c.d,804,SPAN_NONE,"reference backend is AST-based; native lowering and optimization overrides are incompatible"); f.invalid=true;
    }
    if (f.backend && strcmp(f.backend,"native") && (f.enfusion || f.out || f.emit_c)) {
        diag_error(c.d,804,SPAN_NONE,"reference/differential tests use isolated native artifacts; output and target overrides are not supported"); f.invalid=true;
    }
    if (f.json) { diag_error(c.d, 804, SPAN_NONE, "--format is currently supported by check only"); f.invalid = true; }
    if (f.invalid) { report(&c); arena_free(c.a); return 2; }
    bool ir_differential = f.lowering && !strcmp(f.lowering,"ir") && mode == CGEN_TESTS &&
        f.backend && !strcmp(f.backend,"differential") && !f.enfusion;
    if (f.lowering && !strcmp(f.lowering,"ir") && (!ir_differential || f.reference.watch_root.enabled)) {
        fprintf(stderr,"beryl: status=unavailable; capability=lowering.ir; only bounded differential IR tests are admitted; production entry points, Enfusion and observed roots remain unavailable\n");
        arena_free(c.a); return 3;
    }
    Manifest m = resolve_inputs(&c, &f);
    if (f.nfiles < 1) {
        report(&c);
        fprintf(stderr, "usage: beryl %s [--release] [--emit-c] [-o out] <file.be>...\n",
                then_run ? "run" : "build");
        fprintf(stderr, "       (or run inside a package with beryl.toml and src/)\n");
        arena_free(c.a);
        return 2;
    }

    if (!frontend(&c, f.nfiles, f.files, m.forbid_unsafe)) {
        int rc = report(&c);
        arena_free(c.a);
        return rc ? rc : 1;
    }
    report(&c); /* warnings, if any */

    if (mode == CGEN_TESTS) {
        uint32_t count = 0;
        for (uint32_t mi = 0; mi < c.p->modules.len; mi++) {
            Module *module = c.p->modules.data[mi];
            for (uint32_t ti = 0; ti < module->items.len; ti++)
                if (module->items.data[ti]->kind == IT_TEST && module->items.data[ti]->test.body) count++;
        }
        if (!count) {
            diag_error(c.d, 804, SPAN_NONE, "no test blocks selected; no tests were executed");
            report(&c); arena_free(c.a); return 2;
        }
    }

    if (f.enfusion) {
        if (then_run || mode == CGEN_TESTS) {
            fprintf(stderr, "beryl: Enfusion execution is unavailable in this command; use build to generate and Workbench to validate\n");
            arena_free(c.a); return 2;
        }
        EnfusionOpts eo = {0};
        eo.prefix       = str_from(f.prefix);
        eo.out_dir      = str_from(f.out_dir ? f.out_dir : ".");
        eo.exports      = f.exports;
        if (f.source_map) eo.source_map = str_from(f.source_map);

        if (!enfusion_lint(c.d, c.p, eo)) {
            report(&c);
            arena_free(c.a);
            return 1;
        }
        if (f.out_dir) {
            if (!enfusion_emit(c.a, c.sm, c.d, c.p, eo)) {
                report(&c);
                arena_free(c.a);
                return 1;
            }
            printf("emitted EnforceScript into %s\n", f.out_dir);
        } else {
            Str out = enfusion_render_all(c.a, c.sm, c.d, c.p, eo);
            if (diag_errors(c.d)) { report(&c); arena_free(c.a); return 1; }
            if (fwrite(out.ptr,1,out.len,stdout)!=out.len) { arena_free(c.a); return 2; }
        }
        arena_free(c.a);
        return 0;
    }

    if ((!f.backend || strcmp(f.backend,"reference")) && !native_lint(c.d,c.a,c.p)) {
        report(&c); arena_free(c.a); return 1;
    }

    BuildOpts o = {0};
    o.cache_dir = ".beryl-cache";
    o.release   = f.release;
    o.clang     = f.clang;
    o.timeout_ms = f.timeout_ms;
    o.mode      = mode;
    o.save_native_evidence = f.save_native_evidence;
    o.requested_lowering = f.lowering;
    o.optimization_policy = f.optimization;
    o.disabled_optimizations_json = f.disabled_optimizations_json;
    o.out_exe   = f.out ? f.out : (then_run ? NULL : str_cstr(c.a, default_out(c.a, f.files[0])));

    if (f.backend && strcmp(f.backend,"native")) {
        int result=driver_reference_tests(c.a,c.sm,c.d,c.p,f.reference,o,!strcmp(f.backend,"differential"));
        if (diag_errors(c.d)) report(&c);
        arena_free(c.a); return result;
    }

    int rc = 0;
    BuildResult result = {0};
    if (then_run) {
        int code = 0;
        if (!build_and_run(c.a, c.sm, c.d, c.p, o, &result, &code)) rc = 1;
        else rc = code;
    } else {
        if (!build_native(c.a, c.sm, c.d, c.p, o, &result)) rc = 1;
        else printf("built %s\n", o.out_exe);
    }
    /* The backends can report too — the native profile lint, for one. */
    if (rc != 0 && diag_errors(c.d)) report(&c);

    if (f.emit_c && result.c_source) printf("generated C kept at %s\n", result.c_source);
    if (f.save_native_evidence && result.native_evidence_path) printf("native evidence kept at %s\n", result.native_evidence_path);
    arena_free(c.a);
    return rc;
}

static int cmd_check(int argc, char **argv) {
    Ctx      c = ctx_new();
    Flags    f = parse_flags(&c, argc, argv);
    reject_build_options(&c, &f);
    if (f.backend) { diag_error(c.d,804,SPAN_NONE,"--backend is supported by test only"); f.invalid=true; }
    Manifest m = {0};
    if (!f.invalid) m = resolve_inputs(&c, &f);
    if (!f.nfiles && !diag_errors(c.d)) diag_error(c.d, 804, SPAN_NONE,
        "no input files; supply .be files or run in a package containing beryl.toml and src/");
    bool ok = !diag_errors(c.d) && frontend(&c, f.nfiles, f.files, m.forbid_unsafe);
    if (ok && f.enfusion) {
        EnfusionOpts eo = {.prefix = str_from(f.prefix), .exports = f.exports};
        ok = enfusion_lint(c.d, c.p, eo);
    } else if (ok) ok = native_lint(c.d, c.a, c.p);
    int rc;
    if (f.json) {
        SB b; sb_init(&b, c.a);
        sb_cstr(&b, "{\"schema_version\":1,\"operation\":\"check\",\"stage\":\"semantic\",\"status\":");
        json_string(&b, str_from(ok ? "success" : "failure"));
        sb_cstr(&b, ",\"compiler_version\":\"" BERYL_VERSION "\",\"target\":");
        json_string(&b, str_from(f.enfusion ? "enfusion" : "native"));
        Str sources = identity_sources(c.a, c.sm);
        sb_cstr(&b, ",\"sources\":"); sb_str(&b, sources);
        sb_cstr(&b, ",\"source_fingerprint\":"); json_string(&b, hash256_str(c.a, sources));
        sb_cstr(&b, ",\"compiler_fingerprint\":");
        Str compiler = identity_compiler(c.a);
        if (compiler.len) json_string(&b, compiler); else sb_cstr(&b, "null");
        sb_cstr(&b, ",\"binding_fingerprint\":null,\"artifact_fingerprint\":null");
        sb_cstr(&b, ",\"diagnostics\":"); sb_str(&b, diag_render_json(c.a, c.d));
        sb_cstr(&b, "}\n");
        Str json = sb_finish(&b);
        rc = fwrite(json.ptr, 1, json.len, stdout) == json.len ? (ok ? 0 : 1) : 2;
    } else {
        rc = report(&c);
        if (ok && rc == 0) printf("ok\n");
    }
    arena_free(c.a);
    return ok ? rc : (rc ? rc : 1);
}

/* A deterministic, compiler-only seam for external build systems and AI
 * tools. No shell, cache file, linker or executable launch is involved. */
static int cmd_emit_c(int argc, char **argv) {
    Ctx c = ctx_new();
    Flags f = parse_flags(&c, argc, argv);
    reject_build_options(&c, &f);
    if (f.backend) { diag_error(c.d,804,SPAN_NONE,"--backend is supported by test only"); f.invalid=true; }
    if (f.json || f.enfusion) { diag_error(c.d, 804, SPAN_NONE, "emit-c supports native C text output only"); f.invalid = true; }
    if (f.invalid) { report(&c); arena_free(c.a); return 2; }
    Manifest m = resolve_inputs(&c, &f);
    if (!f.nfiles) {
        fprintf(stderr, "usage: beryl emit-c [--tests] <file.be>...\n");
        arena_free(c.a);
        return 2;
    }
    bool ok = frontend(&c, f.nfiles, f.files, m.forbid_unsafe);
    if (ok) {
        Str out = cgen_program(c.a, c.sm, c.d, c.p, f.tests ? CGEN_TESTS : CGEN_PROGRAM);
        ok = diag_errors(c.d) == 0 && out.len != 0;
        if (ok && fwrite(out.ptr, 1, out.len, stdout) != out.len) ok = false;
    }
    int rc = report(&c);
    arena_free(c.a);
    return ok ? rc : (rc ? rc : 1);
}

static int cmd_audit(int argc, char **argv) {
    Ctx      c = ctx_new();
    Flags    f = parse_flags(&c, argc, argv);
    reject_build_options(&c, &f);
    if (f.backend) { diag_error(c.d,804,SPAN_NONE,"--backend is supported by test only"); f.invalid=true; }
    if (f.json) { diag_error(c.d, 804, SPAN_NONE, "--format is currently supported by check only"); f.invalid = true; }
    if (f.invalid) { report(&c); arena_free(c.a); return 2; }
    Manifest m = resolve_inputs(&c, &f);
    if (f.nfiles < 1) {
        fprintf(stderr, "usage: beryl audit <file.be>...\n");
        arena_free(c.a);
        return 2;
    }
    if (!frontend(&c, f.nfiles, f.files, m.forbid_unsafe)) {
        int rc = report(&c);
        arena_free(c.a);
        return rc ? rc : 1;
    }
    int rc = audit_report(c.p, c.sm, m.name, m.forbid_unsafe);
    arena_free(c.a);
    return rc;
}

static void usage(void) {
    printf("beryl %s\n\n", BERYL_VERSION);
    printf("usage: beryl <command> [args]\n\n");
    printf("  check <file.be>...            parse, resolve, type-check, ownership\n");
    printf("  build [opts] <file.be>...     compile to a native executable\n");
    printf("  emit-c [--tests] <files>     write generated C to stdout without compiling\n");
    printf("  run   [opts] <file.be>...     compile and run\n");
    printf("  test  [opts] <file.be>...     execute selected test blocks; native by default\n");
    printf("  mod <command> [opts]        installed local companion tooling (Python)\n");
    printf("  context <topic> [args]      read-only JSON capabilities and declarations\n");
    printf("  doctor [--format json]     bounded environment inventory; probes are explicit\n");
    printf("  analyze --request <file>  analyze exact supplied source snapshot bytes\n");
    printf("  mcp --project <path>      optional local stdio assistant adapter\n");
    printf("  fmt [--check] <file.be>...    format source canonically\n");
    printf("  ast <file.be>                 dump the syntax tree\n");
    printf("  version                       print the version\n\n");
    printf("options:\n");
    printf("  --release    optimize (-O2, no unwind tables)\n");
    printf("  --emit-c     keep the generated C for inspection\n");
    printf("  --save-native-evidence      retain tool identity, C, LLVM IR, assembly and exact argv\n");
    printf("  --source-map <path>        Enfusion JSON sidecar (requires --out-dir)\n");
    printf("  --lowering auto|ast|ir      auto uses AST; IR is experimental differential-test only\n");
    printf("  --opt auto|off             Beryl families only; does not change Clang -O level\n");
    printf("  --disable-opt <family>     disable a registered optimization family\n");
    printf("  -o <path>    output executable path\n");
    printf("  --clang <path>       native compiler executable (or BERYL_CLANG)\n");
    printf("  --timeout-ms <n>     limit each native process/reference execution; default 120000\n");
    printf("  --format json        structured diagnostics for check\n");
    printf("  --backend native|reference|differential   explicit test execution mode\n");
    printf("  --max-steps <n> --max-bytes <n> --max-call-depth <n>   reference budgets\n");
    printf("  --expect-source-trap <kind@file:offset>   verify an expected differential source trap\n");
    printf("  --observe-root <file:offset>   inspect one admitted fixed i32 array before the expected trap\n");
    printf("  --export-class <qualified.Type=EngineName>   explicit Enfusion class name\n");
    printf("  --export-method <qualified.Type.method=Name>   explicit Enfusion method name\n");
    printf("  --export-constructor <qualified.Type.initializer=ClassName>   engine constructor\n");
}

static int main_utf8(int argc, char **argv) {
#ifdef _WIN32
    /* Child logs already contain their actual bytes. Avoid CRCRLF expansion
     * when forwarding them, and preserve generated UTF-8 output verbatim. */
    _setmode(_fileno(stdout), _O_BINARY);
    _setmode(_fileno(stderr), _O_BINARY);
#endif
    process_install_signals();
    if (argc < 2) {
        usage();
        return 2;
    }
    const char *cmd = argv[1];
    int         n   = argc - 2;
    char      **rest = argv + 2;

    if (strcmp(cmd, "check") == 0) return cmd_check(n, rest);
    if (strcmp(cmd, "emit-c") == 0) return cmd_emit_c(n, rest);
    if (strcmp(cmd, "build") == 0) return cmd_build(n, rest, CGEN_PROGRAM, false);
    if (strcmp(cmd, "run") == 0) return cmd_build(n, rest, CGEN_PROGRAM, true);
    if (strcmp(cmd, "test") == 0) return cmd_build(n, rest, CGEN_TESTS, true);
    if (strcmp(cmd, "mod") == 0) return driver_mod(n, rest);
    if (strcmp(cmd, "context") == 0) return context_command(n, rest, BERYL_VERSION);
    if (strcmp(cmd, "doctor") == 0) return doctor_command(n, rest, BERYL_VERSION);
    if (strcmp(cmd, "analyze") == 0) return analyze_command(n, rest, BERYL_VERSION);
    if (strcmp(cmd, "mcp") == 0) return driver_mcp(n, rest);
    if (strcmp(cmd, "audit") == 0) return cmd_audit(n, rest);
    if (strcmp(cmd, "new") == 0) return cmd_new(n, rest);
    if (strcmp(cmd, "fmt") == 0) return cmd_fmt(n, rest);
    if (strcmp(cmd, "ast") == 0) return cmd_ast(n, rest);
    if (strcmp(cmd, "version") == 0 || strcmp(cmd, "--version") == 0) {
        printf("beryl %s\n", BERYL_VERSION);
        return 0;
    }
    if (strcmp(cmd, "help") == 0 || strcmp(cmd, "--help") == 0) {
        usage();
        return 0;
    }

    fprintf(stderr, "beryl: unknown command `%s`\n", cmd);
    usage();
    return 2;
}

int main(int argc, char **argv) {
#ifdef _WIN32
    Arena *arguments=arena_new(0);
    if (!process_utf8_arguments(arguments,&argc,&argv)) {
        fprintf(stderr,"beryl: cannot decode Windows arguments as UTF-8\n");
        arena_free(arguments); return 2;
    }
    int code=main_utf8(argc,argv);
    arena_free(arguments); return code;
#else
    return main_utf8(argc,argv);
#endif
}
