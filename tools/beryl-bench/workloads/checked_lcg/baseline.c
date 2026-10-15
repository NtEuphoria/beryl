#include <stdio.h>
#include <stdint.h>

int main(void) {
    int32_t x = 1;
    for (int32_t i = 0; i < 20000000; i++) {
        x = x + 2;
        x = x - 1;
    }
    printf("%d\n", (int)x);
    return 0;
}
