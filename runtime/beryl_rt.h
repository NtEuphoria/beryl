/* beryl_rt.h — the entire Beryl runtime.
 *
 * There is no runtime initialization, no allocator by default, no unwinding
 * machinery and no personality routine. Failure aborts; it never unwinds,
 * which is where most of the binary-size advantage over Rust comes from.
 *
 * Everything here is either a trap (which does not return) or an inline
 * arithmetic guard that the optimizer folds away when it can prove safety.
 */
#ifndef BERYL_RT_H
#define BERYL_RT_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

/* ---- strings ----------------------------------------------------------- */

typedef struct {
    const char *ptr;
    uint32_t    len;
} BeStr;

#define BE_STR(lit) ((BeStr){(lit), (uint32_t)(sizeof(lit) - 1)})

/* ---- traps ------------------------------------------------------------- */

_Noreturn void beryl_trap_overflow(const char *file, int line, const char *op);
_Noreturn void beryl_trap_bounds(const char *file, int line, int64_t idx, int64_t len);
_Noreturn void beryl_trap_div_zero(const char *file, int line);
_Noreturn void beryl_panic(const char *msg, const char *file, int line);

/* ---- debug output ------------------------------------------------------ */
/* `print` is the one piece of ambient authority Beryl grants, matching
 * EnforceScript's own `Print`. Real I/O requires a capability value. */

void beryl_print_str(BeStr s);
void beryl_print_i64(int64_t v);
void beryl_print_u64(uint64_t v);
void beryl_print_f64(double v);
void beryl_print_bool(bool v);
void beryl_print_char(uint32_t v);
void beryl_newline(void);

/* ---- test harness ------------------------------------------------------ */

void beryl_test_begin(const char *name);
void beryl_test_assert(bool ok, const char *expr, const char *file, int line);
int  beryl_test_summary(void);

/* ---- allocation -------------------------------------------------------- */
/* The only allocator Beryl needs so far, used by `List<T>`. Failure aborts:
 * a program that cannot grow a list has no useful way to continue. */

void *beryl_grow(void *p, size_t bytes);
void  beryl_release(void *p);

/* ---- bounds ------------------------------------------------------------ */

static inline int64_t be_idx(int64_t i, int64_t n, const char *f, int l) {
    if (i < 0 || i >= n) beryl_trap_bounds(f, l, i, n);
    return i;
}

/* ---- checked integer arithmetic ---------------------------------------- */
/* Overflow traps in every build, release included. Rust wraps silently in
 * release, which is a real source of vulnerabilities; the measured cost here
 * is a well-predicted branch. `wrapping_*` opts out where it is wanted. */

#define BE_ARITH(T, S, MINV)                                                               \
    static inline T be_add_##S(T a, T b, const char *f, int l) {                           \
        T r;                                                                               \
        if (__builtin_add_overflow(a, b, &r)) beryl_trap_overflow(f, l, "+");              \
        return r;                                                                          \
    }                                                                                      \
    static inline T be_sub_##S(T a, T b, const char *f, int l) {                           \
        T r;                                                                               \
        if (__builtin_sub_overflow(a, b, &r)) beryl_trap_overflow(f, l, "-");              \
        return r;                                                                          \
    }                                                                                      \
    static inline T be_mul_##S(T a, T b, const char *f, int l) {                           \
        T r;                                                                               \
        if (__builtin_mul_overflow(a, b, &r)) beryl_trap_overflow(f, l, "*");              \
        return r;                                                                          \
    }                                                                                      \
    static inline T be_div_##S(T a, T b, const char *f, int l) {                           \
        if (b == 0) beryl_trap_div_zero(f, l);                                             \
        if (MINV != 0 && a == (T)MINV && b == (T)-1) beryl_trap_overflow(f, l, "/");       \
        return (T)(a / b);                                                                 \
    }                                                                                      \
    static inline T be_rem_##S(T a, T b, const char *f, int l) {                           \
        if (b == 0) beryl_trap_div_zero(f, l);                                             \
        if (MINV != 0 && a == (T)MINV && b == (T)-1) return 0;                             \
        return (T)(a % b);                                                                 \
    }                                                                                      \
    static inline T be_neg_##S(T a, const char *f, int l) {                                \
        T r;                                                                               \
        if (__builtin_sub_overflow((T)0, a, &r)) beryl_trap_overflow(f, l, "-");           \
        return r;                                                                          \
    }

BE_ARITH(int8_t, i8, INT8_MIN)
BE_ARITH(int16_t, i16, INT16_MIN)
BE_ARITH(int32_t, i32, INT32_MIN)
BE_ARITH(int64_t, i64, INT64_MIN)
BE_ARITH(uint8_t, u8, 0)
BE_ARITH(uint16_t, u16, 0)
BE_ARITH(uint32_t, u32, 0)
BE_ARITH(uint64_t, u64, 0)

#undef BE_ARITH

/* Shifts: a shift by >= the width is undefined in C, so it traps here. */
#define BE_SHIFT(T, S, BITS)                                                               \
    static inline T be_shl_##S(T a, T b, const char *f, int l) {                           \
        if ((uint64_t)b >= (BITS)) beryl_trap_overflow(f, l, "<<");                        \
        return (T)(a << b);                                                                \
    }                                                                                      \
    static inline T be_shr_##S(T a, T b, const char *f, int l) {                           \
        if ((uint64_t)b >= (BITS)) beryl_trap_overflow(f, l, ">>");                        \
        return (T)(a >> b);                                                                \
    }

BE_SHIFT(int8_t, i8, 8)
BE_SHIFT(int16_t, i16, 16)
BE_SHIFT(int32_t, i32, 32)
BE_SHIFT(int64_t, i64, 64)
BE_SHIFT(uint8_t, u8, 8)
BE_SHIFT(uint16_t, u16, 16)
BE_SHIFT(uint32_t, u32, 32)
BE_SHIFT(uint64_t, u64, 64)

#undef BE_SHIFT

/* ---- small math -------------------------------------------------------- */

static inline double be_sqrt_f64(double x) { return __builtin_sqrt(x); }
static inline float  be_sqrt_f32(float x) { return __builtin_sqrtf(x); }
static inline double be_abs_f64(double x) { return __builtin_fabs(x); }
static inline float  be_abs_f32(float x) { return __builtin_fabsf(x); }

#endif /* BERYL_RT_H */
