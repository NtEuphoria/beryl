#include "manifest.h"
#include "../common/fs.h"

#include <errno.h>
#include <stdio.h>
#include <string.h>

#ifdef _WIN32
#include <io.h>
#else
#include <dirent.h>
#endif

static Str trim(Str s) {
    uint32_t b = 0, e = s.len;
    while (b < e && (s.ptr[b] == ' ' || s.ptr[b] == '\t')) b++;
    while (e > b && (s.ptr[e - 1] == ' ' || s.ptr[e - 1] == '\t' || s.ptr[e - 1] == '\r'))
        e--;
    return str_new(s.ptr + b, e - b);
}

/* Supported TOML subset: one-line basic/literal strings. Comments only begin
 * outside strings. Unsupported escapes/syntax fail instead of being reinterpreted. */
static bool string_value(Arena *a, Str s, Str *out) {
    if (s.len < 2 || (s.ptr[0] != '"' && s.ptr[0] != '\'')) return false;
    char quote = s.ptr[0];
    SB b; sb_init(&b, a);
    for (uint32_t i = 1; i < s.len; i++) {
        char ch = s.ptr[i];
        if (ch == quote) {
            if (i != s.len - 1) return false;
            *out = sb_finish(&b); return true;
        }
        if ((unsigned char)ch < 32 || ch == 127) return false;
        if (ch == '\\' && quote == '"') {
            if (++i >= s.len) return false;
            switch (s.ptr[i]) {
            case '"': ch = '"'; break;
            case '\\': ch = '\\'; break;
            /* Paths/identities must remain single-line, non-NUL strings. */
            default: return false;
            }
        }
        sb_char(&b, ch);
    }
    return false;
}

static Str without_comment(Str s) {
    char quote = 0;
    for (uint32_t i = 0; i < s.len; i++) {
        char c = s.ptr[i];
        if (quote == '"' && c == '\\') { if (i + 1 < s.len) i++; continue; }
        if (quote && c == quote) quote = 0;
        else if (!quote && (c == '"' || c == '\'')) quote = c;
        else if (!quote && c == '#') return str_new(s.ptr, i);
    }
    return s;
}

Manifest manifest_load(Arena *a, DiagBag *d, const char *dir) {
    Manifest m = {0};

    SB pb;
    sb_init(&pb, a);
    sb_cstr(&pb, dir);
    sb_cstr(&pb, "/beryl.toml");
    Str path = sb_finish(&pb);

    Str txt;
    errno = 0;
    if (!fs_read(a, str_cstr(a, path), &txt)) {
        if (errno != ENOENT) diag_error(d, 801, SPAN_NONE, "cannot read manifest `%.*s`", (int)path.len, path.ptr);
        return m;
    }
    m.found = true;
    m.source_text = txt;

    Str section = STR_EMPTY;
    uint32_t i  = 0;
    uint32_t line_no = 0;
    unsigned seen = 0, sections = 0;

    while (i < txt.len) {
        uint32_t start = i;
        while (i < txt.len && txt.ptr[i] != '\n') i++;
        Str line = trim(without_comment(str_new(txt.ptr + start, i - start)));
        if (i < txt.len) i++;
        line_no++;

        if (line.len == 0 || line.ptr[0] == '#') continue;

        if (line.ptr[0] == '[') {
            if (line.ptr[line.len - 1] != ']') {
                diag_error(d, 801, SPAN_NONE,
                           "beryl.toml:%u: a section header must end with `]`", line_no);
                continue;
            }
            section = trim(str_new(line.ptr + 1, line.len - 2));
            unsigned bit = str_eq_c(section, "package") ? 1 :
                           str_eq_c(section, "target.enfusion") ? 2 :
                           str_eq_c(section, "security") ? 4 : 0;
            if (!bit) diag_error(d, 801, SPAN_NONE, "beryl.toml:%u: unsupported section `%.*s`", line_no, (int)section.len, section.ptr);
            else if (sections & bit) diag_error(d, 801, SPAN_NONE, "beryl.toml:%u: duplicate section", line_no);
            sections |= bit;
            continue;
        }

        uint32_t eq = 0;
        while (eq < line.len && line.ptr[eq] != '=') eq++;
        if (eq == line.len) {
            diag_error(d, 801, SPAN_NONE, "beryl.toml:%u: expected `key = value`", line_no);
            continue;
        }
        Str key = trim(str_new(line.ptr, eq));
        Str val = trim(str_new(line.ptr + eq + 1, line.len - eq - 1));
        Str *dest = NULL;
        unsigned bit = 0;
        if (str_eq_c(section, "package")) {
            if (str_eq_c(key, "name")) { dest = &m.name; bit = 1; }
            else if (str_eq_c(key, "version")) { dest = &m.version; bit = 2; }
        } else if (str_eq_c(section, "target.enfusion")) {
            if (str_eq_c(key, "prefix")) { dest = &m.enfusion_prefix; bit = 4; }
            else if (str_eq_c(key, "out")) { dest = &m.enfusion_out; bit = 8; }
        } else if (str_eq_c(section, "security")) {
            if (str_eq_c(key, "forbid_unsafe")) bit = 16;
        }
        if (!bit) {
            diag_error(d, 801, SPAN_NONE, "beryl.toml:%u: unsupported setting `%.*s`", line_no, (int)key.len, key.ptr);
            continue;
        }
        if (seen & bit) { diag_error(d, 801, SPAN_NONE, "beryl.toml:%u: duplicate setting", line_no); continue; }
        seen |= bit;
        if (dest) {
            if (!string_value(a, val, dest)) diag_error(d, 801, SPAN_NONE,
                "beryl.toml:%u: expected a single-line quoted string (only quote/backslash escapes supported)", line_no);
        } else if (str_eq_c(val, "true")) m.forbid_unsafe = true;
        else if (str_eq_c(val, "false")) m.forbid_unsafe = false;
        else diag_error(d, 801, SPAN_NONE, "beryl.toml:%u: expected boolean true or false", line_no);
    }

    if (str_empty(m.name)) {
        Diag *dg = diag_error(d, 802, SPAN_NONE, "beryl.toml has no `name` under [package]");
        diag_help(dg, "add:\n    [package]\n    name = \"my_package\"");
    }
    return m;
}

/* ---- directory listing -------------------------------------------------- */

static void sort_paths(PathVec *v) {
    for (uint32_t i = 1; i < v->len; i++) {
        Str      key = v->data[i];
        uint32_t j   = i;
        while (j > 0) {
            Str      prev = v->data[j - 1];
            uint32_t n    = prev.len < key.len ? prev.len : key.len;
            int      cmp  = memcmp(prev.ptr, key.ptr, n);
            if (cmp == 0) cmp = (int)prev.len - (int)key.len;
            if (cmp <= 0) break;
            v->data[j] = prev;
            j--;
        }
        v->data[j] = key;
    }
}

static bool ends_with_be(const char *name) {
    size_t n = strlen(name);
    return n > 3 && name[n - 3] == '.' && name[n - 2] == 'b' && name[n - 1] == 'e';
}

PathVec list_beryl_files(Arena *a, const char *dir) {
    PathVec v = {0};

#ifdef _WIN32
    SB pat;
    sb_init(&pat, a);
    sb_cstr(&pat, dir);
    sb_cstr(&pat, "/*.be");

    struct _finddata_t fd;
    intptr_t           h = _findfirst(str_cstr(a, sb_finish(&pat)), &fd);
    if (h == -1) return v;
    do {
        if (fd.attrib & _A_SUBDIR) continue;
        /* Windows can match a pattern against a file's 8.3 short name, so the
         * suffix is re-checked rather than trusted. */
        if (!ends_with_be(fd.name)) continue;
        SB fb;
        sb_init(&fb, a);
        sb_cstr(&fb, dir);
        sb_char(&fb, '/');
        sb_cstr(&fb, fd.name);
        vec_push(a, v, sb_finish(&fb));
    } while (_findnext(h, &fd) == 0);
    _findclose(h);
#else
    DIR *dp = opendir(dir);
    if (!dp) return v;
    struct dirent *de;
    while ((de = readdir(dp)) != NULL) {
        if (!ends_with_be(de->d_name)) continue;
        SB fb;
        sb_init(&fb, a);
        sb_cstr(&fb, dir);
        sb_char(&fb, '/');
        sb_cstr(&fb, de->d_name);
        vec_push(a, v, sb_finish(&fb));
    }
    closedir(dp);
#endif

    /* Sorted, so a package builds the same way every time. */
    sort_paths(&v);
    return v;
}
