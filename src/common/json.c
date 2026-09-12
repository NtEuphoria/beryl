#include "json.h"
/* Invalid input bytes must not make diagnostics invalid JSON. Valid UTF-8 is
 * preserved; malformed bytes are escaped individually as U+00xx. */
static unsigned utf8_width(const unsigned char *p, uint32_t n) {
    unsigned w = p[0] >= 0xc2 && p[0] <= 0xdf ? 2 :
                 p[0] >= 0xe0 && p[0] <= 0xef ? 3 :
                 p[0] >= 0xf0 && p[0] <= 0xf4 ? 4 : 0;
    if (!w || n < w) return 0;
    for (unsigned i = 1; i < w; i++) if ((p[i] & 0xc0) != 0x80) return 0;
    if (w == 3 && ((p[0] == 0xe0 && p[1] < 0xa0) || (p[0] == 0xed && p[1] >= 0xa0))) return 0;
    if (w == 4 && ((p[0] == 0xf0 && p[1] < 0x90) || (p[0] == 0xf4 && p[1] >= 0x90))) return 0;
    return w;
}
void json_string(SB *b, Str s) {
    sb_char(b, '"');
    for (uint32_t i = 0; i < s.len; i++) {
        unsigned char c = (unsigned char)s.ptr[i];
        if (c >= 128) {
            unsigned width = utf8_width((const unsigned char *)s.ptr + i, s.len - i);
            if (width) { sb_str(b, str_new(s.ptr + i, width)); i += width - 1; }
            else sb_fmt(b, "\\u%04x", (unsigned)c);
            continue;
        }
        switch (c) {
        case '"': sb_cstr(b, "\\\""); break;
        case '\\': sb_cstr(b, "\\\\"); break;
        case '\n': sb_cstr(b, "\\n"); break;
        case '\r': sb_cstr(b, "\\r"); break;
        case '\t': sb_cstr(b, "\\t"); break;
        default:
            if (c < 32) sb_fmt(b, "\\u%04x", (unsigned)c);
            else sb_char(b, (char)c);
        }
    }
    sb_char(b, '"');
}
