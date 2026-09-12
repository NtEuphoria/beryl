/* Allocation boundaries are tested without asking the OS for huge storage. */
#include <limits.h>
#include <stdint.h>
#include <string.h>

#include "../../src/common/arena.h"
#include "../../src/common/checked_size.h"
#include "../../src/common/vec.h"
#include "../../runtime/beryl_rt.h"
#include "test.h"

void run_allocation_tests(void) {
    CASE("allocation: checked size boundaries preserve failed outputs");
    size_t out = 123;
    CHECK(checked_size_add(SIZE_MAX - 1, 1, &out) && out == SIZE_MAX);
    out = 123;
    CHECK(!checked_size_add(SIZE_MAX, 1, &out) && out == 123);
    CHECK(!checked_size_mul(SIZE_MAX, 2, &out) && out == 123);
    CHECK(checked_size_mul(SIZE_MAX, 0, &out) && out == 0);
    CHECK(checked_size_mul(SIZE_MAX / 7, 7, &out) && out == SIZE_MAX / 7 * 7);
    out = 123;
    CHECK(!checked_size_mul(SIZE_MAX / 7 + 1, 7, &out) && out == 123);
    CHECK(!checked_size_align(2, 0, &out) && out == 123);
    CHECK(!checked_size_align(2, 3, &out) && out == 123);
    CHECK(!checked_size_align(SIZE_MAX, 8, &out) && out == 123);
    CHECK(checked_size_align(SIZE_MAX, 1, &out) && out == SIZE_MAX);
    CHECK(checked_size_align(SIZE_MAX - 7, 8, &out) && out == SIZE_MAX - 7);
    CHECK(checked_size_align(17, 16, &out) && out == 32);

    CASE("allocation: geometric growth saturates without wrap");
    CHECK(checked_size_grow(0, 1, UINT32_MAX, 8, &out) && out == 8);
    CHECK(checked_size_grow(8, 9, UINT32_MAX, 8, &out) && out == 16);
    CHECK(checked_size_grow(UINT32_MAX / 2 + 1u, UINT32_MAX, UINT32_MAX, 8,
                            &out) && out == UINT32_MAX);
    CHECK(checked_size_grow(SIZE_MAX / 2 + 1, SIZE_MAX, SIZE_MAX, 8,
                            &out) && out == SIZE_MAX);
    CHECK(checked_size_grow(0, 1, 3, 8, &out) && out == 3);
    CHECK(checked_size_grow(0, 0, 0, 8, &out) && out == 0);
    out = 123;
    CHECK(!checked_size_grow(4, 1, 3, 8, &out) && out == 123);
    CHECK(!checked_size_grow(0, 4, 3, 8, &out) && out == 123);
    CHECK(!checked_size_grow(0, 1, 3, 0, &out) && out == 123);
    bool bounded = true;
    for (size_t limit = 0; limit < 65; limit++)
        for (size_t cap = 0; cap <= limit; cap++)
            for (size_t need = 0; need <= limit; need++) {
                if (!checked_size_grow(cap, need, limit, 8, &out) ||
                    out < cap || out < need || out > limit ||
                    (need <= cap && out != cap)) bounded = false;
            }
    CHECK(bounded);

    CASE("allocation: masked hash-table capacity stays a power of two");
    CHECK(checked_size_grow_power2(0, 64, UINT32_MAX, &out) && out == 64);
    CHECK(checked_size_grow_power2(64, 64, UINT32_MAX, &out) && out == 128);
    CHECK(checked_size_grow_power2((size_t)1 << 30, 64, UINT32_MAX, &out) &&
          out == (size_t)1 << 31);
    out = 123;
    CHECK(!checked_size_grow_power2((size_t)1 << 31, 64, UINT32_MAX, &out) && out == 123);
    CHECK(!checked_size_grow_power2(0, 64, 63, &out) && out == 123);
    CHECK(!checked_size_grow_power2(3, 64, UINT32_MAX, &out) && out == 123);
    CHECK(!checked_size_grow_power2(0, 3, UINT32_MAX, &out) && out == 123);
    CHECK(!checked_size_grow_power2(0, 0, UINT32_MAX, &out) && out == 123);
    CHECK(!checked_size_grow_power2((SIZE_MAX / 2) + 1, 64, SIZE_MAX, &out) && out == 123);

    CASE("allocation: string slicing clamps without unsigned wrap");
    CHECK_EQ_S(str_slice(STR_LIT("abcdef"), 2, UINT32_MAX), "cdef");
    CHECK_EQ_S(str_slice(STR_LIT("abcdef"), 6, UINT32_MAX), "");
    CHECK(str_empty(str_slice(STR_LIT("abcdef"), UINT32_MAX, 1)));
    CHECK(str_slice(STR_EMPTY, 0, UINT32_MAX).ptr == NULL);

    CASE("allocation: actual arena address alignment and retained bytes");
    Arena *a = arena_new(37);
    unsigned char *kept[10];
    size_t used = 0;
    for (size_t i = 0, alignment = 1; i < 10; i++, alignment *= 2) {
        unsigned char *odd = arena_alloc(a, 3, 1);
        memset(odd, 0x39, 3);
        kept[i] = arena_alloc(a, 13, alignment);
        CHECK((uintptr_t)kept[i] % alignment == 0);
        memset(kept[i], (int)i, 13);
        CHECK(odd[0] == 0x39 && odd[2] == 0x39);
        used += 16;
        CHECK(arena_bytes_used(a) == used);
        CHECK(arena_bytes_reserved(a) >= used);
    }
    bool intact = true;
    for (size_t i = 0; i < 10; i++)
        for (size_t j = 0; j < 13; j++) if (kept[i][j] != i) intact = false;
    CHECK(intact);
    unsigned char *zero = arena_calloc_array(a, 7, 5, 32);
    CHECK((uintptr_t)zero % 32 == 0);
    for (size_t i = 0; i < 35; i++) CHECK(zero[i] == 0);
    unsigned char *empty = arena_calloc_array(a, 0, SIZE_MAX, 0);
    CHECK(empty && empty[0] == 0);
    CHECK(arena_bytes_used(a) == used + 36);
    arena_free(a);

    CASE("allocation: vector prefix survives reserve and growth");
    a = arena_new(41);
    VEC(uint64_t) v = {0};
    for (uint32_t i = 0; i < 257; i++) vec_push(a, v, (uint64_t)i * i);
    bool prefix = v.len == 257 && v.cap >= v.len;
    for (uint32_t i = 0; i < v.len; i++)
        if (v.data[i] != (uint64_t)i * i) prefix = false;
    CHECK(prefix);
    uint64_t *prior = v.data;
    uint32_t prior_cap = v.cap;
    vec_reserve(a, v, 1);
    CHECK(v.data == prior && v.cap == prior_cap && v.len == 257);
    vec_reserve(a, v, 1025);
    CHECK(v.cap >= 1025 && v.len == 257);
    for (uint32_t i = 0; i < v.len; i++) CHECK(v.data[i] == (uint64_t)i * i);
    CHECK(vec_push_need_(UINT32_MAX - 1, UINT32_MAX) == UINT32_MAX);
    arena_free(a);

    CASE("allocation: native List i32 and byte-size limits");
    int32_t cap = -7;
    size_t bytes = 123;
    CHECK(be_list_growth_plan(0, 0, sizeof(int32_t), &cap, &bytes));
    CHECK(cap == 8 && bytes == 8 * sizeof(int32_t));
    CHECK(be_list_growth_plan(8, 8, 1, &cap, &bytes) && cap == 16 && bytes == 16);
    CHECK(be_list_growth_plan(INT32_MAX - 1, INT32_MAX - 1, 1, &cap, &bytes));
    CHECK(cap == INT32_MAX && bytes == INT32_MAX);
    CHECK(be_list_growth_plan(INT32_MAX - 1, INT32_MAX, 1, &cap, &bytes));
    CHECK(cap == INT32_MAX && bytes == INT32_MAX);
    cap = -7; bytes = 123;
    CHECK(!be_list_growth_plan(INT32_MAX, INT32_MAX, 1, &cap, &bytes));
    CHECK(cap == -7 && bytes == 123);
    CHECK(!be_list_growth_plan(-1, 0, 1, &cap, &bytes));
    CHECK(!be_list_growth_plan(2, 1, 1, &cap, &bytes));
    CHECK(!be_list_growth_plan(0, -1, 1, &cap, &bytes));
    CHECK(!be_list_growth_plan(0, 0, 0, &cap, &bytes));
    CHECK(cap == -7 && bytes == 123);
    size_t large_elem = SIZE_MAX / 3 + 1; /* At most two elements fit. */
    CHECK(be_list_growth_plan(0, 0, large_elem, &cap, &bytes));
    CHECK(cap == 2 && bytes == large_elem * 2);
    cap = -7; bytes = 123;
    CHECK(!be_list_growth_plan(2, 2, large_elem, &cap, &bytes));
    CHECK(!be_list_growth_plan(1, 3, large_elem, &cap, &bytes));
    CHECK(cap == -7 && bytes == 123);
}
