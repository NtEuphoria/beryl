#include <stdio.h>
#include <stdint.h>

static void add(int32_t *y, int32_t *x) {
    for (int32_t i = 0; i < 256; i++) y[i] = y[i] + x[i];
}

int main(void) {
    int32_t x[256], y[256];
    for (int32_t i = 0; i < 256; i++) { x[i] = 1; y[i] = 0; }
    for (int32_t k = 0; k < 20000; k++) add(y, x);
    int32_t s = 0;
    for (int32_t i = 0; i < 256; i++) s += y[i];
    printf("%d\n", (int)s);
    return 0;
}
