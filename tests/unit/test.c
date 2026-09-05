#include "test.h"

#include <string.h>

int t_checks = 0;
int t_fails  = 0;
int t_cases  = 0;

static const char *t_current = "(none)";

void t_case(const char *name) {
    t_current = name;
    t_cases++;
}

static void fail_header(const char *file, int line) {
    t_fails++;
    fprintf(stderr, "FAIL %s\n  at %s:%d\n", t_current, file, line);
}

void t_check_(bool ok, const char *expr, const char *file, int line) {
    t_checks++;
    if (ok) return;
    fail_header(file, line);
    fprintf(stderr, "  expected true: %s\n", expr);
}

void t_check_eq_i_(long long a, long long b, const char *ea, const char *eb,
                   const char *file, int line) {
    t_checks++;
    if (a == b) return;
    fail_header(file, line);
    fprintf(stderr, "  %s == %s\n  left:  %lld\n  right: %lld\n", ea, eb, a, b);
}

void t_check_eq_s_(Str a, const char *b, const char *ea, const char *file, int line) {
    t_checks++;
    if (str_eq_c(a, b)) return;
    fail_header(file, line);
    fprintf(stderr, "  %s\n  left:  \"%.*s\"\n  right: \"%s\"\n", ea, (int)a.len,
            a.ptr ? a.ptr : "", b);
}

static bool contains_(Str hay, const char *needle) {
    size_t n = strlen(needle);
    if (n > hay.len) return false;
    for (uint32_t i = 0; i + n <= hay.len; i++)
        if (memcmp(hay.ptr + i, needle, n) == 0) return true;
    return false;
}

void t_check_missing_(Str hay, const char *needle, const char *ea, const char *file,
                      int line) {
    t_checks++;
    if (!contains_(hay, needle)) return;
    fail_header(file, line);
    fprintf(stderr, "  %s should NOT contain \"%s\"\n  actual:\n%.*s\n", ea, needle,
            (int)hay.len, hay.ptr ? hay.ptr : "");
}

void t_check_contains_(Str hay, const char *needle, const char *ea, const char *file,
                       int line) {
    t_checks++;
    size_t n = strlen(needle);
    if (n <= hay.len) {
        for (uint32_t i = 0; i + n <= hay.len; i++) {
            if (memcmp(hay.ptr + i, needle, n) == 0) return;
        }
    }
    fail_header(file, line);
    fprintf(stderr, "  %s should contain \"%s\"\n  actual:\n%.*s\n", ea, needle,
            (int)hay.len, hay.ptr ? hay.ptr : "");
}

int t_summary(void) {
    if (t_fails == 0) {
        printf("ok  %d cases, %d checks\n", t_cases, t_checks);
        return 0;
    }
    printf("FAILED  %d of %d checks across %d cases\n", t_fails, t_checks, t_cases);
    return 1;
}
