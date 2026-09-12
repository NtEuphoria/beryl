#include "hash.h"
#include <string.h>

static uint32_t rotate(uint32_t x, unsigned n) { return (x >> n) | (x << (32 - n)); }
static void compress(Hash256 *h) {
    static const uint32_t k[64] = {
        0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
        0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
        0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
        0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
        0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
        0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
        0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
        0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2
    };
    uint32_t w[64];
    for (unsigned i = 0; i < 16; i++) {
        const unsigned char *p = h->block + i * 4;
        w[i] = (uint32_t)p[0] << 24 | (uint32_t)p[1] << 16 | (uint32_t)p[2] << 8 | p[3];
    }
    for (unsigned i = 16; i < 64; i++) {
        uint32_t x = w[i-15], y = w[i-2];
        w[i] = w[i-16] + (rotate(x,7) ^ rotate(x,18) ^ (x >> 3)) + w[i-7] +
               (rotate(y,17) ^ rotate(y,19) ^ (y >> 10));
    }
    uint32_t a=h->h[0], b=h->h[1], c=h->h[2], d=h->h[3], e=h->h[4], f=h->h[5], g=h->h[6], z=h->h[7];
    for (unsigned i = 0; i < 64; i++) {
        uint32_t t1 = z + (rotate(e,6)^rotate(e,11)^rotate(e,25)) + ((e&f)^(~e&g)) + k[i]+w[i];
        uint32_t t2 = (rotate(a,2)^rotate(a,13)^rotate(a,22)) + ((a&b)^(a&c)^(b&c));
        z=g; g=f; f=e; e=d+t1; d=c; c=b; b=a; a=t1+t2;
    }
    h->h[0]+=a; h->h[1]+=b; h->h[2]+=c; h->h[3]+=d;
    h->h[4]+=e; h->h[5]+=f; h->h[6]+=g; h->h[7]+=z;
}
void hash256_init(Hash256 *h) {
    *h = (Hash256){.h={0x6a09e667,0xbb67ae85,0x3c6ef372,0xa54ff53a,0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19}};
}
void hash256_update(Hash256 *h, const void *data, size_t n) {
    const unsigned char *p = data;
    h->bytes += n;
    while (n) {
        size_t take = 64 - h->used;
        if (take > n) take = n;
        memcpy(h->block + h->used, p, take);
        h->used += (unsigned)take; p += take; n -= take;
        if (h->used == 64) { compress(h); h->used = 0; }
    }
}
Str hash256_finish(Arena *a, Hash256 *h) {
    uint64_t bits = h->bytes * 8;
    unsigned char one = 0x80, zero = 0;
    hash256_update(h, &one, 1);
    while (h->used != 56) hash256_update(h, &zero, 1);
    unsigned char len[8];
    for (unsigned i = 0; i < 8; i++) len[i] = (unsigned char)(bits >> ((7-i)*8));
    hash256_update(h, len, 8);
    SB b; sb_init(&b, a);
    for (unsigned i = 0; i < 8; i++) sb_fmt(&b, "%08x", h->h[i]);
    return sb_finish(&b);
}
Str hash256_str(Arena *a, Str data) {
    Hash256 h; hash256_init(&h); hash256_update(&h, data.ptr, data.len);
    return hash256_finish(a, &h);
}
