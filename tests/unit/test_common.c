/* Tests for arena, str, vec, map — the infrastructure everything else sits on. */
#include <string.h>

#include "../../src/common/arena.h"
#include "../../src/common/map.h"
#include "../../src/common/str.h"
#include "../../src/common/vec.h"
#include "test.h"

static void test_arena(void) {
    CASE("arena: alignment for 1/2/4/8/16-byte types");
    Arena *a = arena_new(1024);
    for (int i = 0; i < 32; i++) {
        CHECK(((uintptr_t)arena_alloc(a, 1, 1) % 1) == 0);
        CHECK(((uintptr_t)arena_alloc(a, 2, 2) % 2) == 0);
        CHECK(((uintptr_t)arena_alloc(a, 4, 4) % 4) == 0);
        CHECK(((uintptr_t)arena_alloc(a, 8, 8) % 8) == 0);
        CHECK(((uintptr_t)arena_alloc(a, 16, 16) % 16) == 0);
    }

    CASE("arena: calloc zeroes");
    unsigned char *z = (unsigned char *)arena_calloc(a, 64, 8);
    for (int i = 0; i < 64; i++) CHECK_EQ_I(z[i], 0);

    CASE("arena: crosses block boundaries and keeps data intact");
    /* Block size 1024, so this forces several fresh blocks. */
    enum { N = 200 };
    int *ptrs[N];
    for (int i = 0; i < N; i++) {
        ptrs[i]  = (int *)arena_alloc(a, sizeof(int) * 8, _Alignof(int));
        *ptrs[i] = i;
    }
    for (int i = 0; i < N; i++) CHECK_EQ_I(*ptrs[i], i);

    CASE("arena: oversized request larger than the block size still works");
    unsigned char *big = (unsigned char *)arena_alloc(a, 8192, 16);
    memset(big, 0xAB, 8192);
    CHECK_EQ_I(big[0], 0xAB);
    CHECK_EQ_I(big[8191], 0xAB);

    CASE("arena: bytes_used is monotonic");
    size_t before = arena_bytes_used(a);
    arena_alloc(a, 100, 1);
    CHECK(arena_bytes_used(a) >= before + 100);

    arena_free(a);
}

static void test_str(void) {
    Arena *a = arena_new(0);

    CASE("str: equality");
    CHECK(str_eq(str_from("hello"), str_from("hello")));
    CHECK(!str_eq(str_from("hello"), str_from("hell")));
    CHECK(!str_eq(str_from("a"), str_from("b")));
    CHECK(str_eq(STR_EMPTY, str_from("")));
    CHECK(str_eq_c(str_from("fn"), "fn"));

    CASE("str: hash distinguishes");
    CHECK(str_hash(str_from("a")) != str_hash(str_from("b")));
    CHECK(str_hash(str_from("ab")) != str_hash(str_from("ba")));
    CHECK_EQ_I(str_hash(str_from("x")), str_hash(str_from("x")));

    CASE("str: dup and cstr");
    Str d = str_dup(a, str_from("beryl"));
    CHECK(str_eq_c(d, "beryl"));
    CHECK(d.ptr != NULL);
    CHECK_EQ_I(strcmp(str_cstr(a, d), "beryl"), 0);

    CASE("str: slice and prefix");
    Str s = str_from("module flight");
    CHECK(str_eq_c(str_slice(s, 0, 6), "module"));
    CHECK(str_eq_c(str_slice(s, 7, 100), "flight")); /* clamps */
    CHECK(str_starts_with(s, "module"));
    CHECK(!str_starts_with(s, "modules"));

    CASE("sb: grows past initial capacity");
    SB sb;
    sb_init(&sb, a);
    for (int i = 0; i < 500; i++) sb_fmt(&sb, "%d,", i);
    Str out = sb_finish(&sb);
    CHECK(out.len > 1000);
    CHECK(str_starts_with(out, "0,1,2,"));

    CASE("sb: repeat emits tabs");
    SB tb;
    sb_init(&tb, a);
    sb_repeat(&tb, '\t', 3);
    sb_cstr(&tb, "x");
    CHECK(str_eq_c(sb_finish(&tb), "\t\t\tx"));

    CASE("interner: equal contents share a pointer");
    Interner *in = intern_new(a);
    char      buf1[8], buf2[8];
    memcpy(buf1, "ident", 6);
    memcpy(buf2, "ident", 6);
    Str i1 = intern(in, str_from(buf1));
    Str i2 = intern(in, str_from(buf2));
    CHECK(i1.ptr == i2.ptr); /* distinct source buffers, same canonical Str */
    Str i3 = intern(in, str_from("other"));
    CHECK(i1.ptr != i3.ptr);
    CHECK_EQ_I(intern_count(in), 2);

    CASE("interner: the empty string interns to a non-NULL pointer");
    Str e = intern(in, STR_EMPTY);
    CHECK(e.ptr != NULL);
    CHECK_EQ_I(e.len, 0);
    CHECK(intern(in, str_from("")).ptr == e.ptr);

    arena_free(a);
}

static void test_vec(void) {
    Arena *a = arena_new(0);

    CASE("vec: push preserves order across regrowth");
    VEC(int) v = {0};
    for (int i = 0; i < 1000; i++) vec_push(a, v, i * 3);
    CHECK_EQ_I(v.len, 1000);
    bool ok = true;
    for (int i = 0; i < 1000; i++)
        if (vec_at(v, i) != i * 3) ok = false;
    CHECK(ok);
    CHECK_EQ_I(vec_last(v), 999 * 3);

    CASE("vec: pop and clear");
    CHECK_EQ_I(vec_pop(v), 999 * 3);
    CHECK_EQ_I(v.len, 999);
    vec_clear(v);
    CHECK(vec_empty(v));

    CASE("vec: works with struct elements");
    VEC(Str) sv = {0};
    vec_push(a, sv, str_from("a"));
    vec_push(a, sv, str_from("bb"));
    CHECK_EQ_I(sv.len, 2);
    CHECK(str_eq_c(vec_at(sv, 1), "bb"));

    arena_free(a);
}

static void test_map(void) {
    Arena *a = arena_new(0);

    CASE("map: put/get/miss/overwrite");
    Map *m  = map_new(a);
    int  v1 = 1, v2 = 2;
    map_put(m, str_from("alpha"), &v1);
    CHECK(map_get(m, str_from("alpha")) == &v1);
    CHECK(map_get(m, str_from("beta")) == NULL);
    CHECK(map_has(m, str_from("alpha")));
    CHECK(!map_has(m, str_from("beta")));
    map_put(m, str_from("alpha"), &v2);
    CHECK(map_get(m, str_from("alpha")) == &v2);
    CHECK_EQ_I(map_len(m), 1); /* overwrite is not an insert */

    CASE("map: 1000-key stress, every key retrievable");
    Arena *a2 = arena_new(0);
    Map   *big = map_new(a2);
    char   keybuf[32];
    for (int i = 0; i < 1000; i++) {
        snprintf(keybuf, sizeof keybuf, "key_%d", i);
        map_put(big, str_dup(a2, str_from(keybuf)), (void *)(intptr_t)(i + 1));
    }
    CHECK_EQ_I(map_len(big), 1000);
    bool all = true;
    for (int i = 0; i < 1000; i++) {
        snprintf(keybuf, sizeof keybuf, "key_%d", i);
        if ((intptr_t)map_get(big, str_from(keybuf)) != i + 1) all = false;
    }
    CHECK(all);

    CASE("map: iteration visits every key exactly once");
    uint32_t cursor = 0, seen = 0;
    MapEntry e;
    long     sum = 0;
    while (map_next(big, &cursor, &e)) {
        seen++;
        sum += (intptr_t)e.val;
    }
    CHECK_EQ_I(seen, 1000);
    CHECK_EQ_I(sum, 1000L * 1001L / 2L); /* 1..1000 */

    CASE("map: empty string is a usable key");
    map_put(m, STR_EMPTY, &v1);
    CHECK(map_get(m, STR_EMPTY) == &v1);
    CHECK(map_get(m, str_from("")) == &v1);

    arena_free(a2);
    arena_free(a);
}

void run_common_tests(void) {
    test_arena();
    test_str();
    test_vec();
    test_map();
}
