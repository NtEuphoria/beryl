#include <stdio.h>
#include <stdint.h>

typedef struct { float x, y, z; } Vec3;

int main(void) {
    int32_t acc = 0;
    for (int32_t k = 0; k < 4000; k++) {
        Vec3 p = {1.0f, 2.0f, 3.0f};
        Vec3 v = {1.0f, 0.5f, 0.25f};
        for (int32_t i = 0; i < 250; i++) {
            p.x += v.x; p.y += v.y; p.z += v.z;
        }
        acc += (int32_t)p.x;
    }
    printf("%d\n", (int)acc);
    return 0;
}
