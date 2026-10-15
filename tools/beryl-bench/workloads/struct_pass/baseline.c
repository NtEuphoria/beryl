#include <stdio.h>
#include <stdint.h>
#include <string.h>

typedef struct { int32_t a[32]; } Blob;

static int32_t checksum(Blob b) {
    int32_t s = 0;
    for (int32_t i = 0; i < 32; i++) s += b.a[i];
    return s;
}

static int32_t layer(Blob b) {
    return checksum(b) + checksum(b);
}

int main(void) {
    Blob b;
    memset(&b, 0, sizeof b);
    for (int32_t i = 0; i < 32; i++) b.a[i] = i;
    int32_t s = 0;
    for (int32_t k = 0; k < 100000; k++) s = layer(b);
    printf("%d\n", (int)s);
    return 0;
}
