/* arena.h — bump allocator, block-chained, freed wholesale.
 *
 * Arena allocations have a shared lifetime. Checked allocation arithmetic
 * does not establish memory safety for the rest of the compiler.
 */
#ifndef BERYL_ARENA_H
#define BERYL_ARENA_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

typedef struct Arena Arena;

/* block_size of 0 selects the default (256 KiB). */
Arena *arena_new(size_t block_size);

/* Returns memory aligned to `align` (must be a power of two). Never returns
 * NULL: allocation failure aborts, because a compiler that cannot allocate
 * cannot produce a correct answer either. */
void *arena_alloc(Arena *a, size_t size, size_t align);
void *arena_calloc(Arena *a, size_t size, size_t align);
void *arena_calloc_array(Arena *a, size_t count, size_t elem, size_t align);

void   arena_free(Arena *a);
size_t arena_bytes_used(const Arena *a);
size_t arena_bytes_reserved(const Arena *a);

#define ARENA_NEW(a, T)      ((T *)arena_calloc((a), sizeof(T), _Alignof(T)))
#define ARENA_ARRAY(a, T, n) ((T *)arena_calloc_array((a), (size_t)(n), sizeof(T), _Alignof(T)))

#endif /* BERYL_ARENA_H */
