#include "arena.h"

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

static size_t align_up(size_t n, size_t a) { return (n + a - 1u) & ~(a - 1u); }

static void oom(size_t want) {
    fprintf(stderr, "beryl: out of memory allocating %zu bytes\n", want);
    abort();
}

static Block *block_new(size_t cap) {
    /* Header and payload in one allocation; payload start is aligned up to 16. */
    size_t         header = align_up(sizeof(Block), 16u);
    unsigned char *raw    = (unsigned char *)malloc(header + cap);
    if (!raw) oom(header + cap);
    Block *b = (Block *)raw;
    b->next  = NULL;
    b->cap   = cap;
    b->used  = 0;
    b->data  = raw + header;
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

    Block *b     = a->head;
    size_t start = align_up(b->used, align);

    if (start + size > b->cap) {
        /* Oversized requests get a dedicated block so they never waste a whole
         * standard block; ordinary requests start a fresh standard block. */
        size_t cap = (size + align > a->block_size) ? (size + align) : a->block_size;
        Block *nb  = block_new(cap);
        nb->next   = a->head;
        a->head    = nb;
        a->total_reserved += cap;
        b     = nb;
        start = align_up(b->used, align);
    }

    b->used = start + size;
    a->total_used += size;
    return b->data + start;
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
