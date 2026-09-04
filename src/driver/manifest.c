#include "manifest.h"

#include <stdio.h>
#include <string.h>

#ifdef _WIN32
#include <io.h>
#else
#include <dirent.h>
#endif

static Str read_all(Arena *a, const char *path, bool *ok) {
    *ok      = false;
    FILE *fp = fopen(path, "rb");
    if (!fp) return STR_EMPTY;
    fseek(fp, 0, SEEK_END);
    long n = ftell(fp);
    fseek(fp, 0, SEEK_SET);
    if (n < 0) {
        fclose(fp);
        return STR_EMPTY;
    }
    char  *buf = (char *)arena_alloc(a, (size_t)n + 1, 1);
    size_t got = fread(buf, 1, (size_t)n, fp);
    fclose(fp);
    buf[got] = '\0';
    *ok      = true;
    return str_new(buf, (uint32_t)got);
}

static Str trim(Str s) {
    uint32_t b = 0, e = s.len;
    while (b < e && (s.ptr[b] == ' ' || s.ptr[b] == '\t')) b++;
    while (e > b && (s.ptr[e - 1] == ' ' || s.ptr[e - 1] == '\t' || s.ptr[e - 1] == '\r'))
        e--;
    return str_new(s.ptr + b, e - b);
}

static Str unquote(Str s) {
    if (s.len >= 2 && s.ptr[0] == '"' && s.ptr[s.len - 1] == '"')
        return str_new(s.ptr + 1, s.len - 2);
    return s;
}

Manifest manifest_load(Arena *a, DiagBag *d, const char *dir) {
    Manifest m = {0};

    SB pb;
    sb_init(&pb, a);
    sb_cstr(&pb, dir);
    sb_cstr(&pb, "/beryl.toml");
    Str path = sb_finish(&pb);

    bool ok  = false;
    Str  txt = read_all(a, str_cstr(a, path), &ok);
    if (!ok) return m;
    m.found = true;

    Str section = STR_EMPTY;
    uint32_t i  = 0;
    uint32_t line_no = 0;

    while (i < txt.len) {
        uint32_t start = i;
        while (i < txt.len && txt.ptr[i] != '\n') i++;
        Str line = trim(str_new(txt.ptr + start, i - start));
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
            continue;
        }

        uint32_t eq = 0;
        while (eq < line.len && line.ptr[eq] != '=') eq++;
        if (eq == line.len) {
            diag_error(d, 801, SPAN_NONE, "beryl.toml:%u: expected `key = value`", line_no);
            continue;
        }
        Str key = trim(str_new(line.ptr, eq));
        Str val = unquote(trim(str_new(line.ptr + eq + 1, line.len - eq - 1)));

        if (str_eq_c(section, "package")) {
            if (str_eq_c(key, "name")) m.name = val;
            else if (str_eq_c(key, "version")) m.version = val;
        } else if (str_eq_c(section, "target.enfusion")) {
            if (str_eq_c(key, "prefix")) m.enfusion_prefix = val;
            else if (str_eq_c(key, "out")) m.enfusion_out = val;
        } else if (str_eq_c(section, "security")) {
            if (str_eq_c(key, "forbid_unsafe")) m.forbid_unsafe = str_eq_c(val, "true");
        }
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
