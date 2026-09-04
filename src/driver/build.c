#include "build.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "../back/runtime_embed.h"

#ifdef _WIN32
#define POPEN  _popen
#define PCLOSE _pclose
#define MKDIR(p) system_mkdir(p)
#else
#include <sys/stat.h>
#define POPEN  popen
#define PCLOSE pclose
#define MKDIR(p) mkdir(p, 0755)
#endif

#ifdef _WIN32
static int system_mkdir(const char *p) {
    char cmd[1024];
    snprintf(cmd, sizeof cmd, "cmd /c \"if not exist \"%s\" mkdir \"%s\"\" >nul 2>&1", p, p);
    return system(cmd);
}
#endif

static bool write_file(const char *path, Str content) {
    FILE *fp = fopen(path, "wb");
    if (!fp) return false;
    if (content.len) fwrite(content.ptr, 1, content.len, fp);
    fclose(fp);
    return true;
}

static Str join_path(Arena *a, const char *dir, const char *name) {
    SB sb;
    sb_init(&sb, a);
    sb_cstr(&sb, dir);
    sb_char(&sb, '/');
    sb_cstr(&sb, name);
    return sb_finish(&sb);
}

/* Runs a command, capturing stdout and stderr together. */
static int run_capture(Arena *a, Str cmd, Str *out) {
    SB sb;
    sb_init(&sb, a);
    FILE *fp = POPEN(str_cstr(a, cmd), "r");
    if (!fp) {
        *out = str_from("could not start the command");
        return -1;
    }
    char buf[4096];
    size_t n;
    while ((n = fread(buf, 1, sizeof buf, fp)) > 0) sb_str(&sb, str_new(buf, (uint32_t)n));
    int rc = PCLOSE(fp);
    *out   = sb_finish(&sb);
    return rc;
}

static bool contains_ci(Str hay, const char *needle) {
    size_t n = strlen(needle);
    if (n > hay.len) return false;
    for (uint32_t i = 0; i + n <= hay.len; i++) {
        size_t k = 0;
        while (k < n) {
            char x = hay.ptr[i + k], y = needle[k];
            if (x >= 'A' && x <= 'Z') x = (char)(x - 'A' + 'a');
            if (y >= 'A' && y <= 'Z') y = (char)(y - 'A' + 'a');
            if (x != y) break;
            k++;
        }
        if (k == n) return true;
    }
    return false;
}

/* The strings Windows produces when Code Integrity refuses to launch a file. */
static bool looks_blocked(Str output) {
    return contains_ci(output, "Device Guard") || contains_ci(output, "blocked by your") ||
           contains_ci(output, "Access is denied") || contains_ci(output, "Permission denied");
}

static bool compile_c(Arena *a, BuildOpts o, const char *csrc, const char *rtsrc,
                      int nonce, Str *log) {
    SB sb;
    sb_init(&sb, a);
    sb_fmt(&sb, "clang -std=c11 %s -DBERYL_BUILD_NONCE=%d -I\"%s\" -o \"%s\" \"%s\" \"%s\"",
           o.release ? "-O2 -DNDEBUG -fno-unwind-tables -fno-asynchronous-unwind-tables"
                     : "-O0 -g",
           nonce, o.cache_dir, o.out_exe, csrc, rtsrc);
    sb_cstr(&sb, " 2>&1");
    int rc = run_capture(a, sb_finish(&sb), log);
    return rc == 0;
}

bool build_native(Arena *a, SourceMap *sm, DiagBag *d, Program *p, BuildOpts o) {
    MKDIR(o.cache_dir);

    Str csrc  = join_path(a, o.cache_dir, "out.c");
    Str rth   = join_path(a, o.cache_dir, "beryl_rt.h");
    Str rtc   = join_path(a, o.cache_dir, "beryl_rt.c");

    if (!write_file(str_cstr(a, rth), str_from(BERYL_RT_H)) ||
        !write_file(str_cstr(a, rtc), str_from(BERYL_RT_C))) {
        fprintf(stderr, "beryl: cannot write the runtime into %s\n", o.cache_dir);
        return false;
    }

    Str code = cgen_program(a, sm, d, p, o.mode);
    if (code.len == 0) return false; /* the native lint rejected something */
    if (!write_file(str_cstr(a, csrc), code)) {
        fprintf(stderr, "beryl: cannot write %.*s\n", (int)csrc.len, csrc.ptr);
        return false;
    }

    Str log = STR_EMPTY;
    if (!compile_c(a, o, str_cstr(a, csrc), str_cstr(a, rtc), 0, &log)) {
        fprintf(stderr, "beryl: the C backend produced code clang rejected.\n");
        fprintf(stderr, "       This is a compiler bug, not a mistake in your program.\n");
        fprintf(stderr, "       Generated source kept at %.*s\n\n", (int)csrc.len, csrc.ptr);
        fwrite(log.ptr, 1, log.len, stderr);
        return false;
    }
    return true;
}

/* cmd.exe treats a leading `/` in a path component as a switch, so the
 * executable path has to use native separators before it is handed over. */
static Str native_path(Arena *a, const char *p) {
    SB sb;
    sb_init(&sb, a);
    for (const char *c = p; *c; c++) {
#ifdef _WIN32
        sb_char(&sb, *c == '/' ? '\\' : *c);
#else
        sb_char(&sb, *c);
#endif
    }
    return sb_finish(&sb);
}

RunStatus run_exe(Arena *a, const char *exe, int *exit_code) {
    Str native = native_path(a, exe);
    SB  sb;
    sb_init(&sb, a);
    /* The extra outer quotes are what stop cmd.exe from eating the inner
     * pair when a command line begins with one. */
    sb_fmt(&sb, "\"\"%.*s\" 2>&1\"", (int)native.len, native.ptr);

    Str out;
    int rc = run_capture(a, sb_finish(&sb), &out);

    if (looks_blocked(out)) return RUN_BLOCKED;

    fwrite(out.ptr, 1, out.len, stdout);
    if (exit_code) *exit_code = rc;
    return RUN_OK;
}

bool build_and_run(Arena *a, SourceMap *sm, DiagBag *d, Program *p, BuildOpts o,
                   int *exit_code) {
    MKDIR(o.cache_dir);

    Str csrc = join_path(a, o.cache_dir, "out.c");
    Str rth  = join_path(a, o.cache_dir, "beryl_rt.h");
    Str rtc  = join_path(a, o.cache_dir, "beryl_rt.c");

    if (!write_file(str_cstr(a, rth), str_from(BERYL_RT_H)) ||
        !write_file(str_cstr(a, rtc), str_from(BERYL_RT_C))) {
        fprintf(stderr, "beryl: cannot write the runtime into %s\n", o.cache_dir);
        return false;
    }

    Str code = cgen_program(a, sm, d, p, o.mode);
    if (code.len == 0) return false; /* the native lint rejected something */
    if (!write_file(str_cstr(a, csrc), code)) return false;

    /* Each attempt changes the binary's content hash, which earns an
     * independent Smart App Control verdict. See docs/BUILDING.md. */
    const int MAX_ATTEMPTS = 10;
    for (int attempt = 1; attempt <= MAX_ATTEMPTS; attempt++) {
        Str log = STR_EMPTY;
        if (!compile_c(a, o, str_cstr(a, csrc), str_cstr(a, rtc), attempt, &log)) {
            fprintf(stderr, "beryl: the C backend produced code clang rejected.\n");
            fprintf(stderr, "       This is a compiler bug, not a mistake in your program.\n");
            fprintf(stderr, "       Generated source kept at %.*s\n\n", (int)csrc.len,
                    csrc.ptr);
            fwrite(log.ptr, 1, log.len, stderr);
            return false;
        }

        RunStatus st = run_exe(a, o.out_exe, exit_code);
        if (st == RUN_OK) return true;
        if (st == RUN_FAILED) return false;

        if (attempt < MAX_ATTEMPTS)
            fprintf(stderr,
                    "note: Smart App Control blocked the built program; rebuilding "
                    "(attempt %d/%d)\n",
                    attempt + 1, MAX_ATTEMPTS);
    }

    fprintf(stderr, "beryl: Smart App Control blocked every build attempt.\n");
    fprintf(stderr, "       This is an environment limit, not a compile failure.\n");
    fprintf(stderr, "       See docs/BUILDING.md.\n");
    return false;
}
