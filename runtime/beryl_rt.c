#include "beryl_rt.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#ifdef _WIN32
#include <io.h>
#include <fcntl.h>
#endif

static void source_trap_trace(const char *kind);

_Noreturn void beryl_trap_overflow(const char *file, int line, const char *op) {
    source_trap_trace("overflow");
    fprintf(stderr, "beryl: arithmetic overflow on `%s` at %s:%d\n", op, file, line);
    abort();
}

_Noreturn void beryl_trap_bounds(const char *file, int line, int64_t idx, int64_t len) {
    source_trap_trace("bounds");
    fprintf(stderr, "beryl: index %lld out of bounds for length %lld at %s:%d\n",
            (long long)idx, (long long)len, file, line);
    abort();
}

_Noreturn void beryl_trap_div_zero(const char *file, int line) {
    source_trap_trace("division_by_zero");
    fprintf(stderr, "beryl: division by zero at %s:%d\n", file, line);
    abort();
}

_Noreturn void beryl_panic(const char *msg, const char *file, int line) {
    fprintf(stderr, "beryl: panic: %s at %s:%d\n", msg, file, line);
    abort();
}

void *beryl_grow(void *p, size_t bytes) {
    void *n = realloc(p, bytes);
    if (!n && bytes) {
        fprintf(stderr, "beryl: out of memory growing a list to %zu bytes\n", bytes);
        abort();
    }
    return n;
}

_Noreturn void beryl_allocation_size_failure(void) {
    fputs("beryl: list allocation size or capacity limit exceeded\n", stderr);
    abort();
}

void beryl_release(void *p) { free(p); }

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
static bool        g_trace_enabled, g_trace_failed;
static uint64_t    g_event_sequence, g_event_bytes;
static uint32_t    g_trap_file, g_trap_offset;
static bool        g_trap_site_valid;
static bool        g_root_required, g_root_registered;
static uint32_t    g_root_file, g_root_offset, g_root_length;
static const int32_t *g_root_data;

void beryl_test_require_root(uint32_t file, uint32_t offset) {
    g_root_required=true; g_root_file=file; g_root_offset=offset;
    g_root_registered=false; g_root_data=NULL; g_root_length=0;
}
void beryl_test_root_i32(uint32_t file, uint32_t offset, const int32_t *data, uint32_t length) {
    if (!g_trace_enabled || !g_root_required || file!=g_root_file || offset!=g_root_offset ||
        !data || !length || length>4096) { g_trace_failed=true; return; }
    g_root_registered=true; g_root_data=data; g_root_length=length;
}

void beryl_test_trap_site(uint32_t file, uint32_t offset) {
    if (!g_trace_enabled) return;
    g_trap_file=file; g_trap_offset=offset; g_trap_site_valid=true;
}
void beryl_test_trap_site_clear(void) { g_trap_site_valid=false; }

void beryl_test_trace_enable(void) {
    g_trace_enabled=true;
#ifdef _WIN32
    if (_setmode(_fileno(stdout),_O_BINARY)==-1 || _setmode(_fileno(stderr),_O_BINARY)==-1)
        g_trace_failed=true;
#endif
}
bool beryl_test_current_ok(void) { return !g_this_failed; }
static void event_write(const char *buffer, int n) {
    if (!g_trace_enabled || g_trace_failed) return;
    if (n<0 || n>=200 || g_event_bytes>UINT64_C(67108864)-(unsigned)n ||
        fwrite(buffer,1,(size_t)n,stderr)!=(size_t)n) { g_trace_failed=true; return; }
    g_event_bytes+=(unsigned)n;
}
static void source_trap_trace(const char *kind) {
    if (!g_trace_enabled || g_trace_failed || !g_trap_site_valid) return;
    if (g_root_required && !g_root_registered) return;
    /* abort need not flush stdout. Only certify observations that were
     * successfully flushed before this terminal event. */
    if (ferror(stdout) || ferror(stderr) || fflush(stdout)!=0 || fflush(stderr)!=0) {
        g_trace_failed=true; return;
    }
    char buffer[200];
    if (g_root_required) {
        int n=snprintf(buffer,sizeof buffer,
            "{\"event\":\"root_begin\",\"seq\":%llu,\"file\":%u,\"offset\":%u,\"length\":%u,\"element\":\"i32\"}\n",
            (unsigned long long)g_event_sequence++,g_root_file,g_root_offset,g_root_length);
        event_write(buffer,n);
        for (uint32_t i=0;i<g_root_length;i++) {
            n=snprintf(buffer,sizeof buffer,
                "{\"event\":\"root_i32\",\"seq\":%llu,\"file\":%u,\"offset\":%u,\"index\":%u,\"value\":%ld}\n",
                (unsigned long long)g_event_sequence++,g_root_file,g_root_offset,i,(long)g_root_data[i]);
            event_write(buffer,n);
        }
        n=snprintf(buffer,sizeof buffer,
            "{\"event\":\"root_end\",\"seq\":%llu,\"file\":%u,\"offset\":%u,\"length\":%u}\n",
            (unsigned long long)g_event_sequence++,g_root_file,g_root_offset,g_root_length);
        event_write(buffer,n);
        if (g_trace_failed) return;
    }
    int n=snprintf(buffer,sizeof buffer,
        "{\"event\":\"source_trap\",\"seq\":%llu,\"file\":%u,\"offset\":%u,\"kind\":\"%s\",\"complete\":true}\n",
        (unsigned long long)g_event_sequence++,g_trap_file,g_trap_offset,kind);
    event_write(buffer,n);
    if (fflush(stderr)!=0) g_trace_failed=true;
    g_trap_site_valid=false;
}
void beryl_test_event(const char *kind,uint32_t file,uint32_t offset,bool flag) {
    if (!g_trace_enabled) return;
    char buffer[200];
    int n=snprintf(buffer,sizeof buffer,"{\"event\":\"%s\",\"seq\":%llu,\"file\":%u,\"offset\":%u,\"flag\":%s}\n",
        kind,(unsigned long long)g_event_sequence++,file,offset,flag?"true":"false");
    event_write(buffer,n);
}
void beryl_test_f32(uint32_t file,uint32_t offset,float value) {
    if (!g_trace_enabled) return;
    _Static_assert(sizeof(float)==sizeof(uint32_t),"binary32 trace requires four-byte float");
    uint32_t bits; memcpy(&bits,&value,sizeof bits);
    char buffer[200];
    int n=snprintf(buffer,sizeof buffer,"{\"event\":\"f32\",\"seq\":%llu,\"file\":%u,\"offset\":%u,\"bits\":%u}\n",
        (unsigned long long)g_event_sequence++,file,offset,bits);
    event_write(buffer,n);
}

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
    if (g_trace_enabled && (fflush(stderr)!=0 || g_trace_failed)) return 2;
    if (g_this_failed) g_failed++;
    if (g_failed == 0) {
        printf("ok  %d test%s, %d assertion%s\n", g_tests, g_tests == 1 ? "" : "s",
               g_asserts, g_asserts == 1 ? "" : "s");
        return 0;
    }
    printf("FAILED  %d of %d test%s\n", g_failed, g_tests, g_tests == 1 ? "" : "s");
    return 1;
}
