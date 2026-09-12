#include "test.h"
#include "../../src/common/fs.h"
#include "../../src/common/hash.h"
#include "../../src/driver/manifest.h"
#include "../../src/driver/process.h"
#include <string.h>
#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#else
#include <unistd.h>
#endif

/* Executed as a real child. This checks the OS-delivered argv, not the encoder. */
int driver_child(int argc, char **argv) {
    if (argc < 3) return 81;
    if (!strcmp(argv[2], "wait")) {
#ifdef _WIN32
        Sleep(10000);
#else
        sleep(10);
#endif
        return 82;
    }
    if (!strcmp(argv[2], "127")) return 127;
    const char *want[] = {"", "plain", "with spaces", "a\"b", "end\\", "two\\\\\"quote",
                          "& | < > ^ %PATH% ! $() ` ;", "\\\\server\\share\\", NULL};
    if (argc != 11) return 83;
    for (int i = 0; want[i]; i++) if (strcmp(argv[i + 3], want[i])) return 90 + i;
    fputs("stdout only\n", stdout); fputs("stderr only\n", stderr);
    return 0;
}

static void manifests(Arena *a, const char *dir) {
    const char *path = fs_join(a, dir, "beryl.toml");
    CASE("manifest: comments respect quotes and boolean policy");
    CHECK(fs_write(path, str_from("[package] # comment\nname = \"x#y\" # comment\nversion='0.1'\n"
        "[security]\nforbid_unsafe = true # still true\n[target.enfusion]\nout='C:\\mods\\x'\n")));
    DiagBag *d = diag_new(a, srcmap_new(a));
    Manifest m = manifest_load(a, d, dir);
    CHECK(m.found); CHECK(m.forbid_unsafe); CHECK_EQ_S(m.name, "x#y");
    CHECK_EQ_S(m.enfusion_out, "C:\\mods\\x"); CHECK_EQ_I(diag_errors(d), 0);

    const char *bad[] = {"[security]\nforbid_unsafe = typo\n", "[security]\nforbid_unsafe = \"true\"\n",
        "[security]\nforbid_unsafe = true false\n", "[security]\nforbid_unsafe =\n",
        "[security]\nforbid_unsfe = true\n", "[future]\nx = true\n",
        "[package]\nname='again'\n", "[target.enfusion]\nprefix = bare\n",
        "[target.enfusion]\nprefix = \"unfinished\n", "[target.enfusion]\nprefix = \"a\"junk\n",
        "[target.enfusion]\nprefix = \"a\\n\"\n", "[security] junk\nforbid_unsafe=true\n",
        "[security]\nforbid_unsafe=true\nforbid_unsafe=false\n", NULL};
    CASE("manifest: malformed and unsupported settings fail closed");
    for (int i = 0; bad[i]; i++) {
        SB b; sb_init(&b, a); sb_cstr(&b, "[package]\nname='x'\n"); sb_cstr(&b, bad[i]);
        CHECK(fs_write(path, sb_finish(&b)));
        d = diag_new(a, srcmap_new(a)); manifest_load(a, d, dir);
        CHECK(diag_errors(d) > 0);
    }
    CASE("manifest: duplicate values cannot override a security policy");
    CHECK(fs_write(path, str_from("[package]\nname='x'\n[security]\nforbid_unsafe=true\nforbid_unsafe=false\n")));
    d = diag_new(a, srcmap_new(a)); m = manifest_load(a, d, dir);
    CHECK(m.forbid_unsafe); CHECK(diag_errors(d) > 0);
    CASE("manifest: missing is optional, unreadable is not");
    CHECK(fs_remove(path));
    d = diag_new(a, srcmap_new(a)); m = manifest_load(a, d, dir);
    CHECK(!m.found); CHECK_EQ_I(diag_errors(d), 0);
    CHECK(fs_mkdir(path));
    d = diag_new(a, srcmap_new(a)); manifest_load(a, d, dir);
    CHECK(diag_errors(d) > 0);
}

void run_driver_tests(const char *self) {
    Arena *a = arena_new(0);
    CASE("source identity: SHA-256 known answers and streaming block boundaries");
    CHECK_EQ_S(hash256_str(a, STR_EMPTY), "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855");
    CHECK_EQ_S(hash256_str(a, str_from("abc")), "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad");
    Hash256 hash; hash256_init(&hash);
    for (int i = 0; i < 1000000; i++) hash256_update(&hash, "a", 1);
    CHECK_EQ_S(hash256_finish(a, &hash), "cdc76e5c9914fb9281a1c7e284d73e67f1809a48a497200e046d39ccc7112cd0");
    const char *dir = fs_job_dir(a, "build/driver unit & spaces");
    CASE("filesystem: isolated job creation under metacharacter path");
    CHECK(dir != NULL);
    if (!dir) { arena_free(a); return; }
    manifests(a, dir);

    CASE("process: exact argv and distinct stdout/stderr");
    const char *argv[] = {fs_absolute(a, self), "--driver-child", "args", "", "plain", "with spaces",
        "a\"b", "end\\", "two\\\\\"quote", "& | < > ^ %PATH% ! $() ` ;", "\\\\server\\share\\", NULL};
    ProcessOpts opts = {.argv = argv, .log_dir = dir, .log_name = "args", .timeout_ms = 5000};
    ProcessResult r = process_run(a, opts);
    CHECK_EQ_I(r.status, PROCESS_EXITED); CHECK_EQ_I(r.exit_code, 0);
#ifdef _WIN32
    CHECK_EQ_S(r.out, "stdout only\r\n"); CHECK_EQ_S(r.err, "stderr only\r\n");
#else
    CHECK_EQ_S(r.out, "stdout only\n"); CHECK_EQ_S(r.err, "stderr only\n");
#endif

    CASE("process: child exit 127 is not startup failure");
    const char *fail[] = {argv[0], "--driver-child", "127", NULL};
    opts.argv = fail; opts.log_name = "127"; r = process_run(a, opts);
    CHECK_EQ_I(r.status, PROCESS_EXITED); CHECK_EQ_I(r.exit_code, 127);

    CASE("process: missing executable reports startup failure");
    const char *missing[] = {fs_join(a, dir, "does-not-exist.exe"), NULL};
    opts.argv = missing; opts.log_name = "missing"; r = process_run(a, opts);
    CHECK_EQ_I(r.status, PROCESS_START_FAILED); CHECK(r.os_error != 0);

    CASE("process: timeout is distinct from child failure");
    const char *waiting[] = {argv[0], "--driver-child", "wait", NULL};
    opts.argv = waiting; opts.log_name = "timeout"; opts.timeout_ms = 50;
    r = process_run(a, opts); CHECK_EQ_I(r.status, PROCESS_TIMEOUT);

    CASE("process: capture write failure prevents child launch");
    opts.log_dir = fs_join(a, dir, "missing-dir"); opts.log_name = "failure";
    r = process_run(a, opts); CHECK_EQ_I(r.status, PROCESS_IO_FAILED);
    arena_free(a);
}
