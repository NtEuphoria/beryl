/* beryl_rt.h — the entire Beryl runtime.
 *
 * There is no runtime initialization, no allocator by default, no unwinding
 * machinery and no personality routine. Failure aborts; it never unwinds.
 * Binary-size and performance comparisons require matched measured builds.
 *
 * Everything here is either a trap (which does not return) or an inline
 * arithmetic guard that the optimizer folds away when it can prove safety.
 */
#ifndef BERYL_RT_H
#define BERYL_RT_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>

/* Every guard below is false on every step of a correct program, so the branch
 * predictor and the block layout should both assume that. `cold` keeps the trap
 * bodies and their argument setup out of the straight-line path; it does not
 * change when a trap fires. Both are hints, not semantics: a compiler without
 * them produces identical behavior. */
#if defined(__GNUC__) || defined(__clang__)
#define BE_COLD __attribute__((cold))
#define BE_UNLIKELY(x) __builtin_expect(!!(x), 0)
#else
#define BE_COLD
#define BE_UNLIKELY(x) (x)
#endif

/* ---- strings ----------------------------------------------------------- */

typedef struct {
    const char *ptr;
    uint32_t    len;
} BeStr;

#define BE_STR(lit) ((BeStr){(lit), (uint32_t)(sizeof(lit) - 1)})

/* `str` is a slice, so `==` on the struct is not equality — and C rejects it
 * outright. Comparison is by content, which is what the language promises. */
static inline bool be_str_eq(BeStr a, BeStr b) {
    if (a.len != b.len) return false;
    /* `memcmp` on a null pointer is undefined even for zero length, and an
     * empty `str` carries a null base, so the length test comes first. */
    return a.len == 0 || memcmp(a.ptr, b.ptr, a.len) == 0;
}

/* ---- traps ------------------------------------------------------------- */

BE_COLD _Noreturn void beryl_trap_overflow(const char *file, int line, const char *op);
BE_COLD _Noreturn void beryl_trap_bounds(const char *file, int line, int64_t idx, int64_t len);
BE_COLD _Noreturn void beryl_trap_div_zero(const char *file, int line);
BE_COLD _Noreturn void beryl_panic(const char *msg, const char *file, int line);

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
void beryl_test_trace_enable(void);
bool beryl_test_current_ok(void);
void beryl_test_event(const char *kind, uint32_t file, uint32_t offset, bool flag);
void beryl_test_f32(uint32_t file, uint32_t offset, float value);
/* Test-only call-site identity. Ordinary generated arithmetic does not call
 * these functions; wrappers below establish the site after operands evaluate. */
void beryl_test_trap_site(uint32_t file, uint32_t offset);
void beryl_test_trap_site_clear(void);
void beryl_test_require_root(uint32_t file, uint32_t offset);
void beryl_test_root_i32(uint32_t file, uint32_t offset, const int32_t *data, uint32_t length);

/* ---- allocation -------------------------------------------------------- */
/* List allocation failure aborts. Capacity/byte-size rejection is a resource
 * failure too; it must not produce an arithmetic-overflow source-trap event. */

void *beryl_grow(void *p, size_t bytes);
void  beryl_release(void *p);
BE_COLD _Noreturn void beryl_allocation_size_failure(void);

/* Pure capacity planning, independently testable without a large allocation.
 * Output arguments are unchanged on invalid input or exhausted capacity.
 * Length/capacity use i32; bytes are additionally bounded by SIZE_MAX.
 * Callers commit the returned capacity only after successful allocation. */
static inline bool be_list_growth_plan(int32_t len, int32_t cap, size_t elem,
                                       int32_t *next, size_t *bytes) {
    if (len < 0 || cap < len || !elem || len == INT32_MAX) return false;
    size_t limit = SIZE_MAX / elem;
    if (limit > INT32_MAX) limit = INT32_MAX;
    size_t current = (size_t)cap, need = (size_t)len + 1;
    if (current > limit || need > limit) return false;
    size_t grown = current;
    if (grown < need) {
        if (!grown) grown = limit < 8 ? limit : 8;
        else grown = grown > limit / 2 ? limit : grown * 2;
    }
    *next = (int32_t)grown;
    *bytes = grown * elem; /* grown <= SIZE_MAX / elem */
    return true;
}

/* ---- bounds ------------------------------------------------------------ */

static inline int64_t be_idx(int64_t i, int64_t n, const char *f, int l) {
    if (BE_UNLIKELY(i < 0 || i >= n)) beryl_trap_bounds(f, l, i, n);
    return i;
}

/* ---- checked integer arithmetic ---------------------------------------- */
/* Overflow traps in every Beryl build, release included. Rust's overflow
 * policy is configurable; comparison requires matched settings. The cost of
 * these checks is workload-dependent and has not been established here.
 * `wrapping_*` explicitly selects wrapping behavior. */

#define BE_ARITH(T, S, MINV)                                                               \
    static inline T be_add_##S(T a, T b, const char *f, int l) {                           \
        T r;                                                                               \
        if (BE_UNLIKELY(__builtin_add_overflow(a, b, &r))) beryl_trap_overflow(f, l, "+"); \
        return r;                                                                          \
    }                                                                                      \
    static inline T be_sub_##S(T a, T b, const char *f, int l) {                           \
        T r;                                                                               \
        if (BE_UNLIKELY(__builtin_sub_overflow(a, b, &r))) beryl_trap_overflow(f, l, "-"); \
        return r;                                                                          \
    }                                                                                      \
    static inline T be_mul_##S(T a, T b, const char *f, int l) {                           \
        T r;                                                                               \
        if (BE_UNLIKELY(__builtin_mul_overflow(a, b, &r))) beryl_trap_overflow(f, l, "*"); \
        return r;                                                                          \
    }                                                                                      \
    static inline T be_div_##S(T a, T b, const char *f, int l) {                           \
        if (BE_UNLIKELY(b == 0)) beryl_trap_div_zero(f, l);                                \
        if (BE_UNLIKELY(MINV != 0 && a == (T)MINV && b == (T)-1))                          \
            beryl_trap_overflow(f, l, "/");                                                \
        return (T)(a / b);                                                                 \
    }                                                                                      \
    static inline T be_rem_##S(T a, T b, const char *f, int l) {                           \
        if (BE_UNLIKELY(b == 0)) beryl_trap_div_zero(f, l);                                \
        if (BE_UNLIKELY(MINV != 0 && a == (T)MINV && b == (T)-1)) return 0;                \
        return (T)(a % b);                                                                 \
    }                                                                                      \
    static inline T be_neg_##S(T a, const char *f, int l) {                                \
        T r;                                                                               \
        if (BE_UNLIKELY(__builtin_sub_overflow((T)0, a, &r)))                              \
            beryl_trap_overflow(f, l, "-");                                                \
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

/* Trace wrappers are deliberately limited to the independently admitted i32
 * operations. No source trap is inferred from an arbitrary process crash. */
#define BE_TRACE_I32_BINARY(OP)                                                        \
    static inline int32_t be_##OP##_i32_at(int32_t a, int32_t b, const char *f, int l,   \
                                          uint32_t file, uint32_t offset) {             \
        beryl_test_trap_site(file, offset);                                             \
        int32_t value = be_##OP##_i32(a, b, f, l);                                       \
        beryl_test_trap_site_clear();                                                   \
        return value;                                                                  \
    }
BE_TRACE_I32_BINARY(add)
BE_TRACE_I32_BINARY(sub)
BE_TRACE_I32_BINARY(mul)
BE_TRACE_I32_BINARY(div)
BE_TRACE_I32_BINARY(rem)
#undef BE_TRACE_I32_BINARY
static inline int32_t be_neg_i32_at(int32_t a, const char *f, int l,
                                    uint32_t file, uint32_t offset) {
    beryl_test_trap_site(file, offset);
    int32_t value = be_neg_i32(a, f, l);
    beryl_test_trap_site_clear();
    return value;
}
static inline int64_t be_idx_at(int64_t i, int64_t n, const char *f, int l,
                                uint32_t file, uint32_t offset) {
    beryl_test_trap_site(file, offset);
    int64_t value = be_idx(i, n, f, l);
    beryl_test_trap_site_clear();
    return value;
}

/* The explicit opt-outs select wrapping or saturating arithmetic at the call
 * site. Their performance relative to checked operations must be measured.
 *
 * Wrapping goes through the unsigned type because signed overflow is
 * undefined in C, and "undefined" is not what `wrapping_add` promises. */
#define BE_WRAP(T, U, S, MINV, MAXV)                                                       \
    static inline T be_wadd_##S(T a, T b) { return (T)((uint64_t)(U)a + (uint64_t)(U)b); } \
    static inline T be_wsub_##S(T a, T b) { return (T)((uint64_t)(U)a - (uint64_t)(U)b); } \
    static inline T be_wmul_##S(T a, T b) { return (T)((uint64_t)(U)a * (uint64_t)(U)b); } \
    static inline T be_satadd_##S(T a, T b) {                                              \
        T r;                                                                               \
        if (!__builtin_add_overflow(a, b, &r)) return r;                                   \
        return (b > 0) ? (T)(MAXV) : (T)(MINV);                                            \
    }                                                                                      \
    static inline T be_satsub_##S(T a, T b) {                                              \
        T r;                                                                               \
        if (!__builtin_sub_overflow(a, b, &r)) return r;                                   \
        return (b < 0) ? (T)(MAXV) : (T)(MINV);                                            \
    }

BE_WRAP(int8_t, uint8_t, i8, INT8_MIN, INT8_MAX)
BE_WRAP(int16_t, uint16_t, i16, INT16_MIN, INT16_MAX)
BE_WRAP(int32_t, uint32_t, i32, INT32_MIN, INT32_MAX)
BE_WRAP(int64_t, uint64_t, i64, INT64_MIN, INT64_MAX)
BE_WRAP(uint8_t, uint8_t, u8, 0, UINT8_MAX)
BE_WRAP(uint16_t, uint16_t, u16, 0, UINT16_MAX)
BE_WRAP(uint32_t, uint32_t, u32, 0, UINT32_MAX)
BE_WRAP(uint64_t, uint64_t, u64, 0, UINT64_MAX)

#undef BE_WRAP
#undef BE_ARITH

/* Shifts: a shift by >= the width is undefined in C, so it traps here. */
#define BE_SHIFT(T, S, BITS)                                                               \
    static inline T be_shl_##S(T a, T b, const char *f, int l) {                           \
        if (BE_UNLIKELY((uint64_t)b >= (BITS))) beryl_trap_overflow(f, l, "<<");           \
        return (T)((uint64_t)a << (uint64_t)b);                                             \
    }                                                                                      \
    static inline T be_shr_##S(T a, T b, const char *f, int l) {                           \
        if (BE_UNLIKELY((uint64_t)b >= (BITS))) beryl_trap_overflow(f, l, ">>");           \
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

/* ---- vectors ----------------------------------------------------------- */
/* Components are f32 on both targets, because EnforceScript's `vector` is
 * three 32-bit floats and a native/Enfusion mismatch in width would make the
 * two back ends disagree on rounding — which is precisely the class of
 * difference differential testing exists to catch.
 *
 * The anonymous struct/union member is C11 (6.7.2.1p13). It buys `.x` and
 * `.v[i]` over one representation, so generated C reads the way the source
 * did rather than turning every component access into an index. */

typedef union {
    struct {
        float x, y;
    };
    float v[2];
} BeVec2;

typedef union {
    struct {
        float x, y, z;
    };
    float v[3];
} BeVec3;

typedef union {
    struct {
        float x, y, z, w;
    };
    float v[4];
} BeVec4;

static inline BeVec2 be_vec2(float x, float y) {
    BeVec2 r;
    r.x = x;
    r.y = y;
    return r;
}
static inline BeVec3 be_vec3(float x, float y, float z) {
    BeVec3 r;
    r.x = x;
    r.y = y;
    r.z = z;
    return r;
}
static inline BeVec4 be_vec4(float x, float y, float z, float w) {
    BeVec4 r;
    r.x = x;
    r.y = y;
    r.z = z;
    r.w = w;
    return r;
}

/* Component-wise arithmetic and scaling. Float arithmetic is unchecked
 * IEEE-754 here exactly as it is for scalars (SPEC §9), so a zero divisor
 * yields an infinity rather than trapping.
 *
 * Clang evaluates the lanes in a 4-wide vector temporary. The stored union
 * (named components and `.v[]`) stays a plain float array so sizeof and
 * alignment do not change. */
#if defined(__clang__)
typedef float BeF32x4 __attribute__((ext_vector_type(4)));
static inline BeF32x4 be_f32x4_load(const float *p, int n) {
    BeF32x4 v = (BeF32x4){0, 0, 0, 0};
    if (n > 0) v[0] = p[0];
    if (n > 1) v[1] = p[1];
    if (n > 2) v[2] = p[2];
    if (n > 3) v[3] = p[3];
    return v;
}
static inline void be_f32x4_store(float *p, BeF32x4 v, int n) {
    if (n > 0) p[0] = v[0];
    if (n > 1) p[1] = v[1];
    if (n > 2) p[2] = v[2];
    if (n > 3) p[3] = v[3];
}
static inline void be_lane_add(float *r, const float *a, const float *b, int n) {
    be_f32x4_store(r, be_f32x4_load(a, n) + be_f32x4_load(b, n), n);
}
static inline void be_lane_sub(float *r, const float *a, const float *b, int n) {
    be_f32x4_store(r, be_f32x4_load(a, n) - be_f32x4_load(b, n), n);
}
static inline void be_lane_mul(float *r, const float *a, const float *b, int n) {
    be_f32x4_store(r, be_f32x4_load(a, n) * be_f32x4_load(b, n), n);
}
static inline void be_lane_div(float *r, const float *a, const float *b, int n) {
    be_f32x4_store(r, be_f32x4_load(a, n) / be_f32x4_load(b, n), n);
}
static inline void be_lane_scale(float *r, const float *a, float s, int n) {
    be_f32x4_store(r, be_f32x4_load(a, n) * s, n);
}
static inline void be_lane_unscale(float *r, const float *a, float s, int n) {
    be_f32x4_store(r, be_f32x4_load(a, n) / s, n);
}
static inline void be_lane_neg(float *r, const float *a, int n) {
    be_f32x4_store(r, -be_f32x4_load(a, n), n);
}
static inline float be_lane_dot(const float *a, const float *b, int n) {
    BeF32x4 p = be_f32x4_load(a, n) * be_f32x4_load(b, n);
    float s = 0;
    for (int i = 0; i < n; i++) s += p[i];
    return s;
}
#else
static inline void be_lane_add(float *r, const float *a, const float *b, int n) {
    for (int i = 0; i < n; i++) r[i] = a[i] + b[i];
}
static inline void be_lane_sub(float *r, const float *a, const float *b, int n) {
    for (int i = 0; i < n; i++) r[i] = a[i] - b[i];
}
static inline void be_lane_mul(float *r, const float *a, const float *b, int n) {
    for (int i = 0; i < n; i++) r[i] = a[i] * b[i];
}
static inline void be_lane_div(float *r, const float *a, const float *b, int n) {
    for (int i = 0; i < n; i++) r[i] = a[i] / b[i];
}
static inline void be_lane_scale(float *r, const float *a, float s, int n) {
    for (int i = 0; i < n; i++) r[i] = a[i] * s;
}
static inline void be_lane_unscale(float *r, const float *a, float s, int n) {
    for (int i = 0; i < n; i++) r[i] = a[i] / s;
}
static inline void be_lane_neg(float *r, const float *a, int n) {
    for (int i = 0; i < n; i++) r[i] = -a[i];
}
static inline float be_lane_dot(const float *a, const float *b, int n) {
    float s = 0;
    for (int i = 0; i < n; i++) s += a[i] * b[i];
    return s;
}
#endif

#define BE_VEC_OPS(T, S, N)                                                                \
    static inline T be_##S##_add(T a, T b) {                                               \
        T r;                                                                               \
        be_lane_add(r.v, a.v, b.v, (N));                                                   \
        return r;                                                                          \
    }                                                                                      \
    static inline T be_##S##_sub(T a, T b) {                                               \
        T r;                                                                               \
        be_lane_sub(r.v, a.v, b.v, (N));                                                   \
        return r;                                                                          \
    }                                                                                      \
    static inline T be_##S##_mul(T a, T b) {                                               \
        T r;                                                                               \
        be_lane_mul(r.v, a.v, b.v, (N));                                                   \
        return r;                                                                          \
    }                                                                                      \
    static inline T be_##S##_div(T a, T b) {                                               \
        T r;                                                                               \
        be_lane_div(r.v, a.v, b.v, (N));                                                   \
        return r;                                                                          \
    }                                                                                      \
    static inline T be_##S##_scale(T a, float s) {                                         \
        T r;                                                                               \
        be_lane_scale(r.v, a.v, s, (N));                                                   \
        return r;                                                                          \
    }                                                                                      \
    static inline T be_##S##_unscale(T a, float s) {                                       \
        T r;                                                                               \
        be_lane_unscale(r.v, a.v, s, (N));                                                 \
        return r;                                                                          \
    }                                                                                      \
    static inline T be_##S##_neg(T a) {                                                    \
        T r;                                                                               \
        be_lane_neg(r.v, a.v, (N));                                                        \
        return r;                                                                          \
    }                                                                                      \
    static inline bool be_##S##_eq(T a, T b) {                                             \
        for (int i = 0; i < (N); i++)                                                      \
            if (a.v[i] != b.v[i]) return false;                                            \
        return true;                                                                       \
    }                                                                                      \
    static inline float be_##S##_dot(T a, T b) {                                           \
        return be_lane_dot(a.v, b.v, (N));                                                 \
    }                                                                                      \
    static inline float be_##S##_length_sq(T a) { return be_##S##_dot(a, a); }             \
    static inline float be_##S##_length(T a) {                                             \
        return be_sqrt_f32(be_##S##_dot(a, a));                                            \
    }                                                                                      \
    static inline float be_##S##_distance(T a, T b) {                                      \
        return be_##S##_length(be_##S##_sub(a, b));                                        \
    }                                                                                      \
    /* Zero-length normalizes to zero rather than to NaN. IEEE would give      \
     * 0.0/0.0 here, but the Enfusion target's own Normalized() returns zero,  \
     * and two back ends that disagree on a value is worse than either rule. */\
    static inline T be_##S##_normalized(T a) {                                             \
        float len = be_##S##_length(a);                                                    \
        if (len == 0.0f) {                                                                 \
            T z;                                                                           \
            for (int i = 0; i < (N); i++) z.v[i] = 0.0f;                                   \
            return z;                                                                      \
        }                                                                                  \
        return be_##S##_unscale(a, len);                                                   \
    }

BE_VEC_OPS(BeVec2, vec2, 2)
BE_VEC_OPS(BeVec3, vec3, 3)
BE_VEC_OPS(BeVec4, vec4, 4)

#undef BE_VEC_OPS

static inline BeVec3 be_vec3_cross(BeVec3 a, BeVec3 b) {
    return be_vec3(a.y * b.z - a.z * b.y, a.z * b.x - a.x * b.z, a.x * b.y - a.y * b.x);
}

#endif /* BERYL_RT_H */
