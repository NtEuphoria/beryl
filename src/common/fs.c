#ifndef _WIN32
#define _POSIX_C_SOURCE 200809L
#endif
#include "fs.h"
#include <errno.h>
#include <stdlib.h>
#include <string.h>
#include <limits.h>
#include <sys/stat.h>
#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <direct.h>
#else
#include <unistd.h>
#endif

#ifdef _WIN32
wchar_t *fs_wide(Arena *a, const char *s) {
    int n = MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, s, -1, NULL, 0);
    if (!n) { errno = EINVAL; return NULL; }
    wchar_t *w = ARENA_ARRAY(a, wchar_t, n);
    if (!MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, s, -1, w, n)) return NULL;
    return w;
}
#endif

FILE *fs_open(const char *path, const char *mode) {
#ifdef _WIN32
    Arena *a = arena_new(0);
    wchar_t *p = fs_wide(a, path), *m = fs_wide(a, mode);
    FILE *f = p && m ? _wfopen(p, m) : NULL;
    arena_free(a);
    return f;
#else
    return fopen(path, mode);
#endif
}

bool fs_read(Arena *a, const char *path, Str *out) {
    *out = STR_EMPTY;
    FILE *f = fs_open(path, "rb");
    if (!f) return false;
    bool ok = fseek(f, 0, SEEK_END) == 0;
    long n = ok ? ftell(f) : -1;
    /* Source/string representations are uint32_t. Bound before allocating. */
    ok = ok && n >= 0 && (unsigned long long)n <= 64 * 1024 * 1024;
    if (ok) ok = fseek(f, 0, SEEK_SET) == 0;
    char *buf = NULL;
    if (ok) {
        buf = arena_alloc(a, (size_t)n + 1, 1);
        ok = fread(buf, 1, (size_t)n, f) == (size_t)n && !ferror(f);
        if (ok) ok = fgetc(f) == EOF && !ferror(f); /* changed while reading */
    }
    if (fclose(f) != 0) ok = false;
    if (!ok) { if (!errno) errno = EIO; return false; }
    buf[n] = 0;
    *out = str_new(buf, (uint32_t)n);
    return true;
}

bool fs_write(const char *path, Str data) {
    FILE *f = fs_open(path, "wb");
    if (!f) return false;
    bool ok = fwrite(data.ptr, 1, data.len, f) == data.len;
    if (fclose(f) != 0) ok = false;
    return ok;
}

bool fs_mkdir(const char *path) {
#ifdef _WIN32
    Arena *a = arena_new(0);
    wchar_t *p = fs_wide(a, path);
    bool ok = p && _wmkdir(p) == 0;
    arena_free(a);
    return ok;
#else
    return mkdir(path, 0755) == 0;
#endif
}

static bool is_dir(const char *path) {
#ifdef _WIN32
    Arena *a = arena_new(0);
    wchar_t *p = fs_wide(a, path);
    DWORD attr = p ? GetFileAttributesW(p) : INVALID_FILE_ATTRIBUTES;
    arena_free(a);
    return attr != INVALID_FILE_ATTRIBUTES && (attr & FILE_ATTRIBUTE_DIRECTORY);
#else
    struct stat s;
    return stat(path, &s) == 0 && S_ISDIR(s.st_mode);
#endif
}

bool fs_mkdirs(Arena *a, const char *path) {
    if (!path || !*path) return false;
    if (is_dir(path)) return true;
    char *p = str_cstr(a, str_from(path));
    size_t n = strlen(p);
    while (n > 1 && (p[n-1] == '/' || p[n-1] == '\\')) p[--n] = 0;
    size_t cut = n;
    while (cut && p[cut-1] != '/' && p[cut-1] != '\\') --cut;
    if (cut > 1) {
        char old = p[cut-1];
        p[cut-1] = 0;
        bool ok = fs_mkdirs(a, p);
        p[cut-1] = old;
        if (!ok) return false;
    }
    return fs_mkdir(p) || is_dir(p);
}

const char *fs_join(Arena *a, const char *dir, const char *name) {
    SB b; sb_init(&b, a); sb_cstr(&b, dir); sb_char(&b, '/'); sb_cstr(&b, name);
    return str_cstr(a, sb_finish(&b));
}

const char *fs_absolute(Arena *a, const char *path) {
#ifdef _WIN32
    wchar_t *p = fs_wide(a, path);
    if (!p) return NULL;
    DWORD n = GetFullPathNameW(p, 0, NULL, NULL);
    if (!n || n>32768) return NULL;
    wchar_t *w = ARENA_ARRAY(a, wchar_t, (size_t)n + 1);
    DWORD written=GetFullPathNameW(p, n + 1, w, NULL);
    if (!written || written>=n+1) return NULL;
    int z = WideCharToMultiByte(CP_UTF8, 0, w, -1, NULL, 0, NULL, NULL);
    if (!z) return NULL;
    char *s = arena_alloc(a, (size_t)z, 1);
    if (!WideCharToMultiByte(CP_UTF8, 0, w, -1, s, z, NULL, NULL)) return NULL;
    return s;
#else
    if (path[0] == '/') return str_cstr(a, str_from(path));
    size_t n = 1024;
    for (;;) {
        char *buf = arena_alloc(a, n, 1);
        if (getcwd(buf, n)) return fs_join(a, buf, path);
        if (errno != ERANGE || n > 1024 * 1024) return NULL;
        n *= 2;
    }
#endif
}

const char *fs_job_dir(Arena *a, const char *root) {
    if (!fs_mkdirs(a, root)) return NULL;
#ifdef _WIN32
    static LONG counter;
    for (int i = 0; i < 128; i++) {
        SB b; sb_init(&b, a);
        sb_fmt(&b, "job-%lu-%llu-%lu", (unsigned long)GetCurrentProcessId(),
               (unsigned long long)GetTickCount64(), (unsigned long)InterlockedIncrement(&counter));
        const char *path = fs_join(a, root, str_cstr(a, sb_finish(&b)));
        if (fs_mkdir(path)) return fs_absolute(a, path);
        if (errno != EEXIST) return NULL;
    }
    return NULL;
#else
    char *s = str_cstr(a, str_from(fs_join(a, root, "job-XXXXXX")));
    return mkdtemp(s) ? fs_absolute(a, s) : NULL;
#endif
}

const char *fs_executable(Arena *a) {
#ifdef _WIN32
    wchar_t *path = arena_alloc(a, 32768 * sizeof(wchar_t), _Alignof(wchar_t));
    DWORD n = GetModuleFileNameW(NULL, path, 32768);
    if (!n || n >= 32768) return NULL;
    int bytes = WideCharToMultiByte(CP_UTF8, 0, path, -1, NULL, 0, NULL, NULL);
    if (!bytes) return NULL;
    char *utf8 = arena_alloc(a, (size_t)bytes, 1);
    if (!WideCharToMultiByte(CP_UTF8, 0, path, -1, utf8, bytes, NULL, NULL)) return NULL;
    return utf8;
#elif defined(__linux__)
    char *path = arena_alloc(a, 32768, 1);
    ssize_t n = readlink("/proc/self/exe", path, 32767);
    if (n < 0 || n >= 32767) return NULL;
    path[n] = 0; return path;
#else
    (void)a; return NULL;
#endif
}

bool fs_replace(const char *from, const char *to) {
#ifdef _WIN32
    Arena *a = arena_new(0);
    wchar_t *f = fs_wide(a, from), *t = fs_wide(a, to);
    bool ok = f && t && MoveFileExW(f, t, MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH);
    arena_free(a); return ok;
#else
    return rename(from, to) == 0;
#endif
}

bool fs_remove(const char *path) {
#ifdef _WIN32
    Arena *a = arena_new(0); wchar_t *p = fs_wide(a, path);
    bool ok = p && _wremove(p) == 0; arena_free(a); return ok;
#else
    return remove(path) == 0;
#endif
}

bool fs_rmdir(const char *path) {
#ifdef _WIN32
    Arena *a = arena_new(0); wchar_t *p = fs_wide(a, path);
    bool ok = p && _wrmdir(p) == 0; arena_free(a); return ok;
#else
    return rmdir(path) == 0;
#endif
}
