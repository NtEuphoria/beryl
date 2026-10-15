#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

typedef struct {
    int32_t *data;
    int32_t len;
    int32_t cap;
} List;

static void push(List *xs, int32_t v) {
    if (xs->len == xs->cap) {
        int32_t cap = xs->cap ? xs->cap * 2 : 8;
        int32_t *data = realloc(xs->data, (size_t)cap * sizeof(int32_t));
        if (!data) abort();
        xs->data = data;
        xs->cap = cap;
    }
    xs->data[xs->len++] = v;
}

int main(void) {
    List xs = {0};
    int32_t last = 0;
    for (int32_t round = 0; round < 2000; round++) {
        for (int32_t i = 0; i < 256; i++) push(&xs, i);
        last = xs.len;
        xs.len = 0;
    }
    printf("%d\n%d\n", (int)last, (int)xs.len);
    free(xs.data);
    return 0;
}
