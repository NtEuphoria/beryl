#include <stdio.h>
#include <stdint.h>

static int32_t kernel(void) {
    int32_t a[64][64];
    for (int32_t i = 0; i < 64; i++) {
        for (int32_t j = 0; j < 64; j++) a[i][j] = i + j;
    }
    int32_t s = 0;
    for (int32_t k = 0; k < 8000; k++) {
        s = 0;
        for (int32_t i = 0; i < 64; i++) {
            for (int32_t j = 0; j < 64; j++) s += a[i][j];
        }
    }
    return s;
}

int main(void) {
    printf("%d\n", (int)kernel());
    return 0;
}
