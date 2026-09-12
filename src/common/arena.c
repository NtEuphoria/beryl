#include "arena.h"
#include "checked_size.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define ARENA_DEFAULT_BLOCK (256u * 1024u)

typedef struct Block Block;
struct Block {
    Block         *next;
    size_t         cap;
    size_t         used;
    unsigned char *data;
};

struct Arena {
    Block *head;         /* most recent block; allocation happens here */
    size_t block_size;
    size_t total_used;
    size_t total_reserved;
};

static _Noreturn void oom(size_t want) {
    fprintf(stderr, "beryl: out of memory allocating %zu bytes\n", want);
    abort();
}

static _Noreturn void size_failure(void) {
    fputs("beryl: allocation size overflow in compiler arena\n", stderr);
    abort();
}

static Block *block_new(size_t cap) {
    /* Alignment is applied to the actual payload address in arena_alloc. */
    size_t bytes;
    if (!checked_size_add(sizeof(Block), cap, &bytes)) size_failure();
    unsigned char *raw = (unsigned char *)malloc(bytes);
    if (!raw) oom(bytes);
    Block *b = (Block *)raw;
    b->next  = NULL;
    b->cap   = cap;
    b->used  = 0;
    b->data  = raw + sizeof(Block);
    return b;
}

Arena *arena_new(size_t block_size) {
    Arena *a = (Arena *)calloc(1, sizeof(Arena));
    if (!a) oom(sizeof(Arena));
    a->block_size     = block_size ? block_size : ARENA_DEFAULT_BLOCK;
    a->head           = block_new(a->block_size);
    a->total_reserved = a->block_size;
    return a;
}

void *arena_alloc(Arena *a, size_t size, size_t align) {
    if (size == 0) size = 1;
    if (align == 0) align = 1;
    if (align & (align - 1)) {
        fputs("beryl: invalid compiler arena alignment\n", stderr);
        abort();
    }

    size_t total_used;
    if (!checked_size_add(a->total_used, size, &total_used)) size_failure();
    Block *b = a->head;
    /* Offset-only alignment assumes the payload base is already aligned.
     * Instead calculate padding from the actual address, including for
     * over-aligned allocations and after an unaligned preceding request. */
    size_t remainder = (size_t)(uintptr_t)(b->data + b->used) & (align - 1);
    size_t padding = remainder ? align - remainder : 0;
    size_t start, end;
    bool fits = checked_size_add(b->used, padding, &start) &&
                checked_size_add(start, size, &end) && end <= b->cap;

    if (!fits) {
        /* Oversized requests get a dedicated block so they never waste a whole
         * standard block; ordinary requests start a fresh standard block. */
        size_t need, reserved;
        if (!checked_size_add(size, align - 1, &need)) size_failure();
        size_t cap = need > a->block_size ? need : a->block_size;
        if (!checked_size_add(a->total_reserved, cap, &reserved)) size_failure();
        Block *nb  = block_new(cap);
        remainder = (size_t)(uintptr_t)nb->data & (align - 1);
        start = remainder ? align - remainder : 0;
        if (!checked_size_add(start, size, &end) || end > cap) size_failure();
        nb->next   = a->head;
        a->head    = nb;
        a->total_reserved = reserved;
        b     = nb;
    }

    b->used = end;
    a->total_used = total_used;
    return b->data + start;
}

void *arena_calloc_array(Arena *a, size_t count, size_t elem, size_t align) {
    size_t bytes;
    if (!checked_size_mul(count, elem, &bytes)) size_failure();
    return arena_calloc(a, bytes, align);
}

void *arena_calloc(Arena *a, size_t size, size_t align) {
    void *p = arena_alloc(a, size, align);
    memset(p, 0, size ? size : 1);
    return p;
}

void arena_free(Arena *a) {
    if (!a) return;
    Block *b = a->head;
    while (b) {
        Block *next = b->next;
        free(b);
        b = next;
    }
    free(a);
}

size_t arena_bytes_used(const Arena *a) { return a->total_used; }
size_t arena_bytes_reserved(const Arena *a) { return a->total_reserved; }
