/* main.c — the beryl CLI.
 *
 * Subcommands grow as the compiler does; `build`, `run` and `test` arrive with
 * the backends. Everything here is deliberately thin: the driver reads files,
 * runs passes in order, and prints diagnostics.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "../common/arena.h"
#include "../common/diag.h"
#include "../common/source.h"
#include "../lex/lexer.h"
#include "../parse/parser.h"
#include "../parse/print.h"
#include "../sema/check.h"
#include "build.h"
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
    *ok      = false;
    FILE *fp = fopen(path, "rb");
    if (!fp) return STR_EMPTY;
    fseek(fp, 0, SEEK_END);
    long n = ftell(fp);
    fseek(fp, 0, SEEK_SET);
    if (n < 0) {
        fclose(fp);
        return STR_EMPTY;
    }
    char  *buf = (char *)arena_alloc(a, (size_t)n + 1, 1);
    size_t got = fread(buf, 1, (size_t)n, fp);
    fclose(fp);
    buf[got] = '\0';
    *ok      = true;
    return str_new(buf, (uint32_t)got);
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
        fprintf(stderr, "beryl: cannot read %s\n", path);
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

static int cmd_check(int argc, char **argv) {
    if (argc < 1) {
        fprintf(stderr, "usage: beryl check <file.be>...\n");
        return 2;
    }
    Ctx c = ctx_new();
    for (int i = 0; i < argc; i++)
        if (!load(&c, argv[i])) return 2;

    if (diag_errors(c.d) == 0) {
        resolve_program(c.d, c.p);
        check_program(c.d, c.p);
        if (diag_errors(c.d) == 0) ownership_check(c.d, c.p);
    }
    int rc = report(&c);
    if (rc == 0) printf("ok\n");
    arena_free(c.a);
    return rc;
}

static int cmd_ast(int argc, char **argv) {
    if (argc < 1) {
        fprintf(stderr, "usage: beryl ast <file.be>\n");
        return 2;
    }
    Ctx     c = ctx_new();
    Module *m = load(&c, argv[0]);
    if (!m) return 2;
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
            FILE *fp = fopen(argv[i], "wb");
            if (!fp) {
                fprintf(stderr, "beryl: cannot write %s\n", argv[i]);
                arena_free(c.a);
                return 2;
            }
            fwrite(out.ptr, 1, out.len, fp);
            fclose(fp);
            printf("formatted %s\n", argv[i]);
        }
        arena_free(c.a);
    }
    return rc;
}

/* Loads every file, then runs resolve, check and ownership in order. Each
 * stage only runs when the previous one was clean, so a syntax error never
 * produces a cascade of invented type errors. */
static bool frontend(Ctx *c, int nfiles, char **files) {
    for (int i = 0; i < nfiles; i++)
        if (!load(c, files[i])) return false;
    if (diag_errors(c->d)) return false;

    if (!resolve_program(c->d, c->p)) return false;
    if (!check_program(c->d, c->p)) return false;
    if (!ownership_check(c->d, c->p)) return false;
    return true;
}

typedef struct {
    const char *out;
    bool        release;
    bool        emit_c;
    int         nfiles;
    char      **files;
} Flags;

static Flags parse_flags(Arena *a, int argc, char **argv) {
    Flags f = {0};
    f.files = (char **)arena_alloc(a, sizeof(char *) * (size_t)(argc > 0 ? argc : 1), 8);
    for (int i = 0; i < argc; i++) {
        if (strcmp(argv[i], "--release") == 0) f.release = true;
        else if (strcmp(argv[i], "--emit-c") == 0) f.emit_c = true;
        else if (strcmp(argv[i], "-o") == 0 && i + 1 < argc) f.out = argv[++i];
        else f.files[f.nfiles++] = argv[i];
    }
    return f;
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
    Ctx   c = ctx_new();
    Flags f = parse_flags(c.a, argc, argv);
    if (f.nfiles < 1) {
        fprintf(stderr, "usage: beryl %s [--release] [--emit-c] [-o out] <file.be>...\n",
                then_run ? "run" : "build");
        arena_free(c.a);
        return 2;
    }

    if (!frontend(&c, f.nfiles, f.files)) {
        int rc = report(&c);
        arena_free(c.a);
        return rc ? rc : 1;
    }
    report(&c); /* warnings, if any */

    BuildOpts o = {0};
    o.cache_dir = ".beryl-cache";
    o.release   = f.release;
    o.mode      = mode;
    o.out_exe   = f.out ? f.out : str_cstr(c.a, default_out(c.a, f.files[0]));

    int rc = 0;
    if (then_run) {
        int code = 0;
        if (!build_and_run(c.a, c.sm, c.d, c.p, o, &code)) rc = 1;
        else rc = code;
    } else {
        if (!build_native(c.a, c.sm, c.d, c.p, o)) rc = 1;
        else printf("built %s\n", o.out_exe);
    }

    if (f.emit_c) printf("generated C kept at %s/out.c\n", o.cache_dir);
    arena_free(c.a);
    return rc;
}

static void usage(void) {
    printf("beryl %s\n\n", BERYL_VERSION);
    printf("usage: beryl <command> [args]\n\n");
    printf("  check <file.be>...            parse, resolve, type-check, ownership\n");
    printf("  build [opts] <file.be>...     compile to a native executable\n");
    printf("  run   [opts] <file.be>...     compile and run\n");
    printf("  test  [opts] <file.be>...     run every `test` block natively\n");
    printf("  fmt [--check] <file.be>...    format source canonically\n");
    printf("  ast <file.be>                 dump the syntax tree\n");
    printf("  version                       print the version\n\n");
    printf("options:\n");
    printf("  --release    optimize (-O2, no unwind tables)\n");
    printf("  --emit-c     keep the generated C for inspection\n");
    printf("  -o <path>    output executable path\n");
}

int main(int argc, char **argv) {
    if (argc < 2) {
        usage();
        return 2;
    }
    const char *cmd = argv[1];
    int         n   = argc - 2;
    char      **rest = argv + 2;

    if (strcmp(cmd, "check") == 0) return cmd_check(n, rest);
    if (strcmp(cmd, "build") == 0) return cmd_build(n, rest, CGEN_PROGRAM, false);
    if (strcmp(cmd, "run") == 0) return cmd_build(n, rest, CGEN_PROGRAM, true);
    if (strcmp(cmd, "test") == 0) return cmd_build(n, rest, CGEN_TESTS, true);
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
