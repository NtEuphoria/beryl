#ifndef _WIN32
#define _POSIX_C_SOURCE 200809L
#endif
#include "process.h"
#include "../common/fs.h"
#include "../common/json_read.h"
#include <errno.h>
#include <signal.h>
#include <stdlib.h>
#include <string.h>
#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#else
#include <fcntl.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>
#endif

static volatile sig_atomic_t cancelled;
bool process_environment(Arena *a, const char *name, const char **value) {
    if (!value) return false;
    *value=NULL;
    if (!a || !name || !*name) return false;
    size_t name_size=0;
    while (name[name_size] && name_size<256) name_size++;
    if (name_size==256 || strchr(name,'=') || !json_utf8(str_new(name,(uint32_t)name_size),NULL)) return false;
#ifdef _WIN32
    wchar_t *wide_name=fs_wide(a,name);
    if (!wide_name) return false;
    SetLastError(ERROR_SUCCESS);
    DWORD count=GetEnvironmentVariableW(wide_name,NULL,0);
    if (!count) {
        DWORD error=GetLastError();
        if (error==ERROR_ENVVAR_NOT_FOUND) return true;
        if (error!=ERROR_SUCCESS) return false;
        *value=str_cstr(a,STR_EMPTY); return true;
    }
    if (count>32768) return false;
    wchar_t *wide=ARENA_ARRAY(a,wchar_t,count);
    SetLastError(ERROR_SUCCESS);
    DWORD written=GetEnvironmentVariableW(wide_name,wide,count);
    if (written>=count || (!written && GetLastError()!=ERROR_SUCCESS)) return false;
    if (!written) { *value=str_cstr(a,STR_EMPTY); return true; }
    int bytes=WideCharToMultiByte(CP_UTF8,WC_ERR_INVALID_CHARS,wide,(int)written,NULL,0,NULL,NULL);
    if (bytes<=0 || bytes>=131072) return false;
    char *utf8=arena_alloc(a,(size_t)bytes+1,1);
    if (WideCharToMultiByte(CP_UTF8,WC_ERR_INVALID_CHARS,wide,(int)written,utf8,bytes,NULL,NULL)!=bytes) return false;
    utf8[bytes]=0; *value=utf8; return true;
#else
    const char *found=getenv(name);
    if (!found) return true;
    size_t bytes=0; while (found[bytes] && bytes<131072) bytes++;
    if (bytes==131072 || !json_utf8(str_new(found,(uint32_t)bytes),NULL)) return false;
    *value=str_cstr(a,str_new(found,(uint32_t)bytes)); return true;
#endif
}
bool process_utf8_arguments(Arena *a, int *argc, char ***argv) {
    if (!a || !argc || !argv) return false;
#ifdef _WIN32
    HMODULE shell=LoadLibraryExW(L"shell32.dll",NULL,LOAD_LIBRARY_SEARCH_SYSTEM32);
    if (!shell) return false;
    typedef LPWSTR *(WINAPI *ParseArguments)(LPCWSTR,int *);
    ParseArguments parse=(ParseArguments)GetProcAddress(shell,"CommandLineToArgvW");
    LPWSTR *wide=NULL; char **utf8=NULL; int count=0; bool ok=false;
    if (!parse) goto done;
    wide=parse(GetCommandLineW(),&count);
    if (!wide || count<1 || count>32768) goto done;
    utf8=ARENA_ARRAY(a,char *,count+1);
    for (int i=0;i<count;i++) {
        int n=WideCharToMultiByte(CP_UTF8,WC_ERR_INVALID_CHARS,wide[i],-1,NULL,0,NULL,NULL);
        if (n<=0) goto done;
        utf8[i]=arena_alloc(a,(size_t)n,1);
        if (WideCharToMultiByte(CP_UTF8,WC_ERR_INVALID_CHARS,wide[i],-1,utf8[i],n,NULL,NULL)!=n) goto done;
    }
    utf8[count]=NULL; ok=true;
done:
    if (wide && LocalFree(wide)!=NULL) ok=false;
    if (!FreeLibrary(shell)) ok=false;
    if (ok) { *argc=count; *argv=utf8; }
    return ok;
#else
    return *argc>0 && *argv && (*argv)[0];
#endif
}
const char *process_find_executable(Arena *a, const char *name) {
    if (!name || !*name) return NULL;
    if (strchr(name, '/') || strchr(name, '\\') || strchr(name, ':'))
        return fs_absolute(a, name);
#ifdef _WIN32
    wchar_t *wname = fs_wide(a, name);
    const wchar_t *search = _wgetenv(L"PATH");
    if (!wname || !search || !*search) return NULL;
    DWORD n = SearchPathW(search, wname, L".exe", 0, NULL, NULL);
    if (!n || n>32768) return NULL;
    wchar_t *resolved = ARENA_ARRAY(a, wchar_t, (size_t)n + 1);
    DWORD written=SearchPathW(search, wname, L".exe", n + 1, resolved, NULL);
    if (!written || written>=n+1) return NULL;
    int bytes = WideCharToMultiByte(CP_UTF8, WC_ERR_INVALID_CHARS, resolved, -1, NULL, 0, NULL, NULL);
    if (!bytes) return NULL;
    char *utf8 = arena_alloc(a, (size_t)bytes, 1);
    if (!WideCharToMultiByte(CP_UTF8, WC_ERR_INVALID_CHARS, resolved, -1, utf8, bytes, NULL, NULL)) return NULL;
    return fs_absolute(a, utf8);
#else
    const char *path = getenv("PATH");
    if (!path) return NULL;
    while (true) {
        const char *end = strchr(path, ':');
        size_t n = end ? (size_t)(end - path) : strlen(path);
        const char *dir = n ? str_cstr(a, str_new(path, (uint32_t)n)) : ".";
        const char *candidate = fs_join(a, dir, name);
        if (access(candidate, X_OK) == 0) return fs_absolute(a, candidate);
        if (!end) break;
        path = end + 1;
    }
    return NULL;
#endif
}
bool process_cancelled(void) { return cancelled!=0; }
uint64_t process_clock_ms(void) {
#ifdef _WIN32
    return (uint64_t)GetTickCount64();
#else
    struct timespec value;
    if (clock_gettime(CLOCK_MONOTONIC,&value)!=0) return 0;
    return (uint64_t)value.tv_sec*1000+(uint64_t)value.tv_nsec/1000000;
#endif
}
static void on_signal(int sig) { (void)sig; cancelled = 1; }
#ifdef _WIN32
static BOOL WINAPI on_console(DWORD type) {
    if (type == CTRL_C_EVENT || type == CTRL_BREAK_EVENT || type == CTRL_CLOSE_EVENT) {
        cancelled = 1; return TRUE;
    }
    return FALSE;
}
#endif
void process_install_signals(void) {
    signal(SIGINT, on_signal); signal(SIGTERM, on_signal);
#ifdef _WIN32
    SetConsoleCtrlHandler(on_console, TRUE);
#endif
}

const char *process_status_name(ProcessStatus s) {
    switch (s) {
    case PROCESS_EXITED: return "exited";
    case PROCESS_START_FAILED: return "startup_failure";
    case PROCESS_TIMEOUT: return "timeout";
    case PROCESS_CANCELLED: return "cancelled";
    case PROCESS_IO_FAILED: return "io_failure";
    }
    return "invalid";
}

Str process_windows_command_line(Arena *a, const char *const *argv) {
    SB b; sb_init(&b, a);
    for (size_t i = 0; argv[i]; i++) {
        if (i) sb_char(&b, ' ');
        sb_char(&b, '"');
        const char *p = argv[i];
        for (;;) {
            size_t slashes = 0;
            while (*p == '\\') { slashes++; p++; }
            size_t count = (*p == '"' || *p == 0) ? slashes * 2 : slashes;
            for (size_t k = 0; k < count; k++) sb_char(&b, '\\');
            if (!*p) break;
            if (*p == '"') sb_char(&b, '\\');
            sb_char(&b, *p++);
        }
        sb_char(&b, '"');
    }
    return sb_finish(&b);
}

/* Default capture uses separate files: a child cannot deadlock by filling one
 * pipe while the parent reads the other. Inherited mode instead passes the
 * original streams directly to the owned child, without protocol buffering. */
ProcessResult process_run(Arena *a, ProcessOpts o) {
    ProcessResult r = {.status = PROCESS_START_FAILED};
    if (!o.argv || !o.argv[0] || (!o.inherit_stdio && (!o.log_dir || !o.log_name))) {
        r.os_error = EINVAL; return r;
    }
    if (!o.inherit_stdio) {
        SB name; sb_init(&name, a); sb_fmt(&name, "%s.stdout.log", o.log_name);
        r.stdout_path = fs_join(a, o.log_dir, str_cstr(a, sb_finish(&name)));
        sb_init(&name, a); sb_fmt(&name, "%s.stderr.log", o.log_name);
        r.stderr_path = fs_join(a, o.log_dir, str_cstr(a, sb_finish(&name)));
    }
    if (cancelled) { r.status = PROCESS_CANCELLED; return r; }
#ifdef _WIN32
    SECURITY_ATTRIBUTES sa = {sizeof(sa), NULL, TRUE};
    HANDLE out = INVALID_HANDLE_VALUE, err = INVALID_HANDLE_VALUE, input = INVALID_HANDLE_VALUE;
    HANDLE job = NULL;
    LPPROC_THREAD_ATTRIBUTE_LIST attrs = NULL;
    PROCESS_INFORMATION pi = {0};
    if (o.inherit_stdio) {
        const DWORD kinds[] = {STD_OUTPUT_HANDLE, STD_ERROR_HANDLE, STD_INPUT_HANDLE};
        HANDLE *targets[] = {&out, &err, &input};
        for (uint32_t i=0;i<3;i++) {
            HANDLE original=GetStdHandle(kinds[i]);
            if (!original || original==INVALID_HANDLE_VALUE) {
                r.status=PROCESS_IO_FAILED; r.os_error=ERROR_INVALID_HANDLE; goto finish;
            }
            if (!DuplicateHandle(GetCurrentProcess(), original, GetCurrentProcess(), targets[i],
                                 0, TRUE, DUPLICATE_SAME_ACCESS)) {
                r.status=PROCESS_IO_FAILED; r.os_error=GetLastError(); goto finish;
            }
        }
    } else {
        wchar_t *outpath = fs_wide(a, r.stdout_path), *errpath = fs_wide(a, r.stderr_path);
        if (!outpath || !errpath) { r.os_error = ERROR_NO_UNICODE_TRANSLATION; goto finish; }
        out = CreateFileW(outpath, GENERIC_WRITE, FILE_SHARE_READ, &sa, CREATE_NEW, FILE_ATTRIBUTE_NORMAL, NULL);
        err = CreateFileW(errpath, GENERIC_WRITE, FILE_SHARE_READ, &sa, CREATE_NEW, FILE_ATTRIBUTE_NORMAL, NULL);
        input = CreateFileW(L"NUL", GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE, &sa, OPEN_EXISTING, 0, NULL);
    }
    if (out == INVALID_HANDLE_VALUE || err == INVALID_HANDLE_VALUE || input == INVALID_HANDLE_VALUE) {
        r.status = PROCESS_IO_FAILED; r.os_error = GetLastError(); goto finish;
    }
    job = CreateJobObjectW(NULL, NULL);
    JOBOBJECT_EXTENDED_LIMIT_INFORMATION limits = {0};
    limits.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
    if (!job || !SetInformationJobObject(job, JobObjectExtendedLimitInformation, &limits, sizeof(limits))) {
        r.os_error = GetLastError(); goto finish;
    }
    SIZE_T attrsize = 0;
    InitializeProcThreadAttributeList(NULL, 1, 0, &attrsize);
    attrs = arena_alloc(a, attrsize, _Alignof(void *));
    if (!InitializeProcThreadAttributeList(attrs, 1, 0, &attrsize)) {
        attrs = NULL; r.os_error = GetLastError(); goto finish;
    }
    HANDLE handles[] = {out, err, input};
    if (!UpdateProcThreadAttribute(attrs, 0, PROC_THREAD_ATTRIBUTE_HANDLE_LIST,
                                   handles, sizeof(handles), NULL, NULL)) {
        r.os_error = GetLastError(); goto finish;
    }
    STARTUPINFOEXW si = {0}; si.StartupInfo.cb = sizeof(si); si.lpAttributeList = attrs;
    si.StartupInfo.dwFlags = STARTF_USESTDHANDLES;
    si.StartupInfo.hStdOutput = out; si.StartupInfo.hStdError = err; si.StartupInfo.hStdInput = input;
    wchar_t *application = fs_wide(a, o.argv[0]);
    wchar_t *cwd = o.cwd ? fs_wide(a, o.cwd) : NULL;
    wchar_t *command = fs_wide(a, str_cstr(a, process_windows_command_line(a, o.argv)));
    if (!application || !command || (o.cwd && !cwd)) {
        r.os_error = ERROR_NO_UNICODE_TRANSLATION; goto finish;
    }
    /* Resolve PATH explicitly; CreateProcess receives an unambiguous application
     * name. A .bat/.cmd is not a native executable and is not run via a shell. */
    if (!wcschr(application, L'/') && !wcschr(application, L'\\') && !wcschr(application, L':')) {
        const wchar_t *search = _wgetenv(L"PATH");
        if (!search || !*search) { r.os_error = ERROR_FILE_NOT_FOUND; goto finish; }
        DWORD n = SearchPathW(search, application, L".exe", 0, NULL, NULL);
        if (!n) { r.os_error = GetLastError(); goto finish; }
        if (n>32768) { r.os_error = ERROR_FILENAME_EXCED_RANGE; goto finish; }
        wchar_t *resolved = ARENA_ARRAY(a, wchar_t, (size_t)n + 1);
        DWORD written=SearchPathW(search, application, L".exe", n + 1, resolved, NULL);
        if (!written || written>=n+1) {
            r.os_error = written ? ERROR_INSUFFICIENT_BUFFER : GetLastError(); goto finish;
        }
        application = resolved;
    }
    if (!CreateProcessW(application, command, NULL, NULL, TRUE,
                         CREATE_NO_WINDOW | CREATE_SUSPENDED | EXTENDED_STARTUPINFO_PRESENT,
                         NULL, cwd, &si.StartupInfo, &pi)) {
        r.os_error = GetLastError(); goto finish;
    }
    if (!AssignProcessToJobObject(job, pi.hProcess) || ResumeThread(pi.hThread) == (DWORD)-1) {
        r.os_error = GetLastError(); TerminateProcess(pi.hProcess, 1);
        WaitForSingleObject(pi.hProcess, INFINITE); goto finish;
    }
    ULONGLONG start = GetTickCount64();
    for (;;) {
        DWORD waited = WaitForSingleObject(pi.hProcess, 10);
        if (waited == WAIT_OBJECT_0) {
            DWORD code;
            if (GetExitCodeProcess(pi.hProcess, &code)) { r.status = PROCESS_EXITED; r.exit_code = code; }
            else { r.status = PROCESS_IO_FAILED; r.os_error = GetLastError(); }
            break;
        }
        if (waited == WAIT_FAILED) { r.status = PROCESS_IO_FAILED; r.os_error = GetLastError(); break; }
        if (cancelled) { r.status = PROCESS_CANCELLED; break; }
        if (o.timeout_ms && GetTickCount64() - start >= o.timeout_ms) { r.status = PROCESS_TIMEOUT; break; }
    }
    /* Any descendants belong to this operation, including on normal completion. */
    if (!TerminateJobObject(job, 1) && r.status == PROCESS_EXITED) {
        r.status = PROCESS_IO_FAILED; r.os_error = GetLastError();
    }
    WaitForSingleObject(pi.hProcess, INFINITE);
finish:
    if (pi.hThread) CloseHandle(pi.hThread);
    if (pi.hProcess) CloseHandle(pi.hProcess);
    if (job) CloseHandle(job);
    if (attrs) DeleteProcThreadAttributeList(attrs);
    if (out != INVALID_HANDLE_VALUE) CloseHandle(out);
    if (err != INVALID_HANDLE_VALUE) CloseHandle(err);
    if (input != INVALID_HANDLE_VALUE) CloseHandle(input);
#else
    int out=-1, err=-1, input=-1;
    int ep[2] = {-1, -1};
    if (o.inherit_stdio) {
        /* Check originals before creating descriptors: an absent stdin must
         * not accidentally become a duplicate of stdout allocated as fd 0. */
        if (fcntl(STDIN_FILENO,F_GETFD)<0 || fcntl(STDOUT_FILENO,F_GETFD)<0 || fcntl(STDERR_FILENO,F_GETFD)<0) {
            r.status=PROCESS_IO_FAILED; r.os_error=(uint32_t)errno; goto finish;
        }
        out=fcntl(STDOUT_FILENO,F_DUPFD_CLOEXEC,3);
        err=fcntl(STDERR_FILENO,F_DUPFD_CLOEXEC,3);
        input=fcntl(STDIN_FILENO,F_DUPFD_CLOEXEC,3);
    } else {
        out = open(r.stdout_path, O_WRONLY | O_CREAT | O_EXCL, 0600);
        err = open(r.stderr_path, O_WRONLY | O_CREAT | O_EXCL, 0600);
        input = open("/dev/null", O_RDONLY);
    }
    if (out < 0 || err < 0 || input < 0 || pipe(ep) != 0 || fcntl(ep[1], F_SETFD, FD_CLOEXEC) != 0) {
        r.status = PROCESS_IO_FAILED; r.os_error = (uint32_t)errno; goto finish;
    }
    pid_t pid = fork();
    if (pid == 0) {
        close(ep[0]);
        if (setpgid(0, 0) == 0 && dup2(out, STDOUT_FILENO) >= 0 && dup2(err, STDERR_FILENO) >= 0 &&
            dup2(input, STDIN_FILENO) >= 0 && (!o.cwd || chdir(o.cwd) == 0)) {
            close(out); close(err); close(input);
            execvp(o.argv[0], (char *const *)o.argv);
        }
        int failed = errno;
        ssize_t ignored = write(ep[1], &failed, sizeof(failed)); (void)ignored;
        _exit(127);
    }
    if (pid < 0) { r.os_error = (uint32_t)errno; goto finish; }
    close(ep[1]); ep[1] = -1;
    setpgid(pid, pid);
    struct timespec begin; clock_gettime(CLOCK_MONOTONIC, &begin);
    int status = 0;
    for (;;) {
        pid_t w = waitpid(pid, &status, WNOHANG);
        if (w == pid) {
            r.status = PROCESS_EXITED;
            r.exit_code = WIFEXITED(status) ? (uint32_t)WEXITSTATUS(status) : (uint32_t)(128 + WTERMSIG(status));
            break;
        }
        if (w < 0 && errno != EINTR) { r.status = PROCESS_IO_FAILED; r.os_error = (uint32_t)errno; break; }
        if (cancelled) { r.status = PROCESS_CANCELLED; break; }
        struct timespec now; clock_gettime(CLOCK_MONOTONIC, &now);
        int64_t ms = (now.tv_sec - begin.tv_sec) * INT64_C(1000) + (now.tv_nsec - begin.tv_nsec) / 1000000;
        if (o.timeout_ms && ms >= o.timeout_ms) { r.status = PROCESS_TIMEOUT; break; }
        struct timespec pause = {0, 10000000}; nanosleep(&pause, NULL);
    }
    kill(-pid, SIGKILL);
    if (r.status != PROCESS_EXITED) while (waitpid(pid, &status, 0) < 0 && errno == EINTR) {}
    int failed = 0; ssize_t got;
    do { got = read(ep[0], &failed, sizeof(failed)); } while (got < 0 && errno == EINTR);
    if (got == sizeof(failed)) { r.status = PROCESS_START_FAILED; r.os_error = (uint32_t)failed; }
    else if (got != 0) { r.status = PROCESS_IO_FAILED; r.os_error = (uint32_t)errno; }
finish:
    if (out >= 0) close(out);
    if (err >= 0) close(err);
    if (input >= 0) close(input);
    if (ep[0] >= 0) close(ep[0]);
    if (ep[1] >= 0) close(ep[1]);
#endif
    if (!o.inherit_stdio) {
        bool out_ok = fs_read(a, r.stdout_path, &r.out);
        bool err_ok = fs_read(a, r.stderr_path, &r.err);
        if ((!out_ok || !err_ok) && r.status == PROCESS_EXITED) {
            r.status = PROCESS_IO_FAILED; r.os_error = (uint32_t)errno;
        }
    }
    return r;
}
