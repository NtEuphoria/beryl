#include "symbol.h"
Str symbol_encode(Arena *a, const char *category, Str name) {
    SB b; sb_init(&b, a); sb_cstr(&b,"be_"); sb_cstr(&b,category); sb_char(&b,'_');
    for (uint32_t i=0;i<name.len;i++) {
        unsigned char c=(unsigned char)name.ptr[i];
        if ((c>='a' && c<='z') || (c>='A' && c<='Z') || (c>='0' && c<='9')) sb_char(&b,(char)c);
        else sb_fmt(&b,"_%02x",(unsigned)c);
    }
    return sb_finish(&b);
}
