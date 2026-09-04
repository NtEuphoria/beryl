#include "beryl_rt.h"

#include <stdio.h>
#include <stdlib.h>

_Noreturn void beryl_trap_overflow(const char *file, int line, const char *op) {
    fprintf(stderr, "beryl: arithmetic overflow on `%s` at %s:%d\n", op, file, line);
    abort();
}

_Noreturn void beryl_trap_bounds(const char *file, int line, int64_t idx, int64_t len) {
    fprintf(stderr, "beryl: index %lld out of bounds for length %lld at %s:%d\n",
            (long long)idx, (long long)len, file, line);
    abort();
}

_Noreturn void beryl_trap_div_zero(const char *file, int line) {
    fprintf(stderr, "beryl: division by zero at %s:%d\n", file, line);
    abort();
}

_Noreturn void beryl_panic(const char *msg, const char *file, int line) {
    fprintf(stderr, "beryl: panic: %s at %s:%d\n", msg, file, line);
    abort();
}

void beryl_print_str(BeStr s) { fwrite(s.ptr, 1, s.len, stdout); }
void beryl_print_i64(int64_t v) { printf("%lld", (long long)v); }
void beryl_print_u64(uint64_t v) { printf("%llu", (unsigned long long)v); }
void beryl_print_bool(bool v) { fputs(v ? "true" : "false", stdout); }
void beryl_print_char(uint32_t v) { putchar((int)v); }
void beryl_newline(void) { putchar('\n'); }

void beryl_print_f64(double v) {
    /* %g drops trailing zeros, which keeps expected-output tests readable. */
    printf("%g", v);
}

/* ---- test harness ------------------------------------------------------ */

static int         g_tests   = 0;
static int         g_failed  = 0;
static int         g_asserts = 0;
static const char *g_current = "";
static bool        g_this_failed = false;

void beryl_test_begin(const char *name) {
    if (g_this_failed) g_failed++;
    g_current     = name;
    g_this_failed = false;
    g_tests++;
}

void beryl_test_assert(bool ok, const char *expr, const char *file, int line) {
    g_asserts++;
    if (ok) return;
    if (!g_this_failed) fprintf(stderr, "FAIL %s\n", g_current);
    g_this_failed = true;
    fprintf(stderr, "  assertion failed: %s\n    at %s:%d\n", expr, file, line);
}

int beryl_test_summary(void) {
    if (g_this_failed) g_failed++;
    if (g_failed == 0) {
        printf("ok  %d test%s, %d assertion%s\n", g_tests, g_tests == 1 ? "" : "s",
               g_asserts, g_asserts == 1 ? "" : "s");
        return 0;
    }
    printf("FAILED  %d of %d test%s\n", g_failed, g_tests, g_tests == 1 ? "" : "s");
    return 1;
}
