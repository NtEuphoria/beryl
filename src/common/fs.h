#ifndef BERYL_FS_H
#define BERYL_FS_H

#include <stdio.h>
#include "str.h"

/* UTF-8 paths at this boundary. All reads/writes check the complete operation. */
FILE *fs_open(const char *path, const char *mode);
bool fs_read(Arena *a, const char *path, Str *out);
bool fs_write(const char *path, Str data);
bool fs_mkdir(const char *path); /* exclusive: existing directory is failure */
bool fs_mkdirs(Arena *a, const char *path);
const char *fs_join(Arena *a, const char *dir, const char *name);
const char *fs_absolute(Arena *a, const char *path);
const char *fs_executable(Arena *a); /* current executable; NULL if unavailable */
const char *fs_job_dir(Arena *a, const char *root);
/* Atomically replace a file; callers provide their own synchronization. */
bool fs_replace(const char *from, const char *to);
bool fs_remove(const char *path);
bool fs_rmdir(const char *path);

#ifdef _WIN32
#include <wchar.h>
wchar_t *fs_wide(Arena *a, const char *utf8);
#endif
#endif
