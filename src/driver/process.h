#ifndef BERYL_PROCESS_H
#define BERYL_PROCESS_H

#include "../common/str.h"

typedef enum {
    PROCESS_EXITED, PROCESS_START_FAILED, PROCESS_TIMEOUT, PROCESS_CANCELLED,
    PROCESS_IO_FAILED
} ProcessStatus;
typedef struct {
    const char *const *argv; /* NULL terminated; no command interpreter */
    const char *cwd;        /* NULL inherits current directory */
    const char *log_dir;    /* capture mode: existing, exclusively owned job directory */
    const char *log_name;   /* capture mode: trusted stage name, e.g. compile or run */
    uint32_t timeout_ms;    /* 0 means no timeout */
    bool inherit_stdio;    /* stream original stdin/out/err; no capture paths/data */
} ProcessOpts;
typedef struct {
    ProcessStatus status;
    uint32_t exit_code;     /* meaningful only for PROCESS_EXITED */
    uint32_t os_error;      /* launch/I/O error, not child's exit code */
    const char *stdout_path;
    const char *stderr_path;
    Str out, err;
} ProcessResult;

ProcessResult process_run(Arena *a, ProcessOpts opts);
const char *process_status_name(ProcessStatus status);
/* Install once in CLI; cancellation remains sticky for this invocation. */
void process_install_signals(void);
bool process_cancelled(void);
uint64_t process_clock_ms(void);
/* Public so quoting is testable on either host. Always quotes each argument. */
Str process_windows_command_line(Arena *a, const char *const *argv);
/* Resolve a native executable against the current process PATH, never a shell.
 * The returned absolute path can be fingerprinted and passed as argv[0]. */
const char *process_find_executable(Arena *a, const char *name);
/* Capture lossless OS arguments before using Windows main(char**) strings.
 * The returned pointers belong to a; POSIX arguments remain unchanged. */
bool process_utf8_arguments(Arena *a, int *argc, char ***argv);
/* Bounded UTF-8 environment lookup: true/NULL means absent. False means
 * conversion, size or read failure and callers must not silently default. */
bool process_environment(Arena *a, const char *name, const char **value);

#endif
