#include "build.h"
#include "../back/runtime_embed.h"
#include "../common/fs.h"
#include "../common/json.h"
#include "../common/hash.h"
#include "identity.h"
#include "../ir/c_emit.h"
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#ifndef _WIN32
#include <sys/stat.h>
#endif

static void process_json(SB *b, ProcessResult *r) {
    sb_cstr(b, "{\"status\":"); json_string(b, str_from(process_status_name(r->status)));
    sb_cstr(b, ",\"exit_code\":");
    if (r->status == PROCESS_EXITED) sb_fmt(b, "%u", r->exit_code); else sb_cstr(b, "null");
    sb_fmt(b, ",\"os_error\":%u,\"stdout_log\":", r->os_error);
    if (r->stdout_path) json_string(b, str_from(r->stdout_path)); else sb_cstr(b, "null");
    sb_cstr(b, ",\"stderr_log\":");
    if (r->stderr_path) json_string(b, str_from(r->stderr_path)); else sb_cstr(b, "null");
    sb_char(b, '}');
}

static bool evidence(Arena *a, BuildResult *r, const char *status) {
    SB b; sb_init(&b, a);
    sb_cstr(&b, "{\"schema_version\":1,\"operation\":\"native_build\",\"artifact_id\":");
    json_string(&b, str_from(r->job_dir));
    sb_cstr(&b, ",\"status\":"); json_string(&b, str_from(status));
    sb_cstr(&b, ",\"selected_lowering\":"); json_string(&b, str_from(r->selected_lowering));
    sb_cstr(&b, ",\"source_fingerprint\":"); json_string(&b, r->source_fingerprint);
    sb_cstr(&b, ",\"sources\":"); sb_str(&b, r->sources_json);
    sb_cstr(&b, ",\"compiler_fingerprint\":");
    if (r->compiler_fingerprint.len) json_string(&b, r->compiler_fingerprint); else sb_cstr(&b, "null");
    sb_cstr(&b, ",\"artifact_fingerprint\":");
    if (r->executable_fingerprint.len) json_string(&b, r->executable_fingerprint); else sb_cstr(&b, "null");
    sb_cstr(&b, ",\"binding_fingerprint\":null");
    sb_cstr(&b, ",\"native_evidence\":");
    if (r->native_evidence_path) json_string(&b, str_from(r->native_evidence_path)); else sb_cstr(&b, "null");
    sb_cstr(&b, ",\"compiler_identity\":");
    if (r->identity_attempted) process_json(&b, &r->compiler_identity); else sb_cstr(&b, "null");
    sb_cstr(&b, ",\"compiler_evidence_process\":");
    if (r->evidence_attempted) process_json(&b, &r->compiler_evidence); else sb_cstr(&b, "null");
    sb_cstr(&b, ",\"compile\":"); process_json(&b, &r->compile);
    sb_cstr(&b, ",\"run\":");
    if (r->executed) process_json(&b, &r->run); else sb_cstr(&b, "null");
    sb_cstr(&b, "}\n");
    return fs_write(fs_join(a, r->job_dir, "result.json"), sb_finish(&b));
}

static void report_process(const char *stage, ProcessResult r) {
    if (r.status != PROCESS_EXITED)
        fprintf(stderr, "beryl: %s %s (OS error %u)\n", stage, process_status_name(r.status), r.os_error);
    else if (r.exit_code)
        fprintf(stderr, "beryl: %s exited with status %u\n", stage, r.exit_code);
    if (r.out.len) fwrite(r.out.ptr, 1, r.out.len, stdout);
    if (r.err.len) fwrite(r.err.ptr, 1, r.err.len, stderr);
}

/* Streaming tool hashes avoid the source-reader's 64 MiB input bound. This
 * captures the selected executable, not every SDK/linker dependency. */
static Str file_hash(Arena *a, const char *path) {
    FILE *file = fs_open(path, "rb");
    if (!file) return STR_EMPTY;
    unsigned char block[32768]; size_t n;
    Hash256 hash; hash256_init(&hash);
    while ((n = fread(block, 1, sizeof block, file)) != 0) hash256_update(&hash, block, n);
    bool ok = !ferror(file);
    if (fclose(file) != 0) ok = false;
    return ok ? hash256_finish(a, &hash) : STR_EMPTY;
}

static bool save_argv(Arena *a, const char *dir, const char *name, const char *const *argv) {
    SB b; sb_init(&b, a); sb_char(&b, '[');
    for (size_t i = 0; argv[i]; i++) {
        if (i) sb_char(&b, ',');
        json_string(&b, str_from(argv[i]));
    }
    sb_cstr(&b, "]\n"); return fs_write(fs_join(a, dir, name), sb_finish(&b));
}

static bool native_evidence(Arena *a, BuildOpts o, BuildResult *r,
                            const char *clang, Str clang_hash, ProcessResult version,
                            const char *const *compile_argv) {
    SB b; sb_init(&b, a);
    sb_cstr(&b, "{\"schema_version\":1,\"operation\":\"native_evidence\",\"stage\":\"compiler_evidence\"");
    sb_cstr(&b, ",\"required_capability\":\"clang.c11.ir.assembly\",\"source_fingerprint\":"); json_string(&b, r->source_fingerprint);
    sb_cstr(&b, ",\"compiler_fingerprint\":"); json_string(&b, r->compiler_fingerprint);
    sb_cstr(&b, ",\"artifact_fingerprint\":"); json_string(&b, r->executable_fingerprint);
    Str generated_c = file_hash(a, r->c_source);
    sb_cstr(&b, ",\"generated_c_fingerprint\":");
    if (generated_c.len) json_string(&b, generated_c); else sb_cstr(&b, "null");
    sb_cstr(&b, ",\"clang\":{\"path\":"); json_string(&b, str_from(clang));
    sb_cstr(&b, ",\"sha256\":"); json_string(&b, clang_hash);
    sb_cstr(&b, ",\"version\":"); process_json(&b, &version);
    sb_cstr(&b, ",\"identity_scope\":\"selected executable; dependent SDK and linker binaries not fingerprinted\"}");
    sb_cstr(&b, ",\"requested_lowering\":"); json_string(&b, str_from(o.requested_lowering ? o.requested_lowering : "auto"));
    sb_cstr(&b, ",\"selected_lowering\":"); json_string(&b, str_from(r->selected_lowering));
    sb_cstr(&b, ",\"optimization_policy\":"); json_string(&b, str_from(o.optimization_policy ? o.optimization_policy : "auto"));
    sb_cstr(&b, ",\"selected_optimizations\":[],\"disabled_optimizations\":");
    sb_str(&b, o.disabled_optimizations_json.len ? o.disabled_optimizations_json : STR_LIT("[]"));
    sb_cstr(&b, ",\"runtime_fingerprints\":{\"header\":"); json_string(&b, hash256_str(a, str_from(BERYL_RT_H)));
    sb_cstr(&b, ",\"implementation\":"); json_string(&b, hash256_str(a, str_from(BERYL_RT_C)));
    sb_cstr(&b, "},\"measurement_status\":\"not_measured\",\"program_execution\":\"not_executed_by_evidence_capture\",\"passes\":[");
    bool ok = generated_c.len != 0;
    const char *names[] = {"llvm-ir", "assembly", "driver-jobs"};
    const char *outputs[] = {"out.ll", "out.s", NULL};
    for (unsigned pass = 0; pass < 3 && ok; pass++) {
        const char *argv[24]; unsigned argc = 0;
        if (pass == 2) {
            for (; compile_argv[argc]; argc++) argv[argc] = compile_argv[argc];
            argv[argc++] = "-###";
        } else {
            argv[argc++] = clang; argv[argc++] = "-std=c11";
            argv[argc++] = o.release ? "-O2" : "-O0";
            if (o.release) {
                argv[argc++] = "-DNDEBUG"; argv[argc++] = "-fno-unwind-tables";
                argv[argc++] = "-fno-asynchronous-unwind-tables";
            } else argv[argc++] = "-g";
            argv[argc++] = "-ffp-contract=off"; argv[argc++] = "-fno-fast-math";
            argv[argc++] = "-I"; argv[argc++] = r->job_dir;
            argv[argc++] = "-S";
            if (pass == 0) argv[argc++] = "-emit-llvm";
            argv[argc++] = r->c_source; argv[argc++] = "-o";
            argv[argc++] = fs_join(a, r->job_dir, outputs[pass]);
        }
        argv[argc] = NULL;
        SB name; sb_init(&name, a); sb_fmt(&name, "%s.argv.json", names[pass]);
        bool args_ok = save_argv(a, r->job_dir, str_cstr(a, sb_finish(&name)), argv);
        ProcessResult result = {.status = PROCESS_IO_FAILED};
        if (args_ok) result = process_run(a, (ProcessOpts){.argv = argv, .log_dir = r->job_dir,
            .log_name = names[pass], .timeout_ms = o.timeout_ms});
        r->evidence_attempted = args_ok;
        r->compiler_evidence = result;
        if (pass) sb_char(&b, ',');
        sb_cstr(&b, "{\"name\":"); json_string(&b, str_from(names[pass]));
        sb_cstr(&b, ",\"process\":"); process_json(&b, &result);
        Str hash = outputs[pass] ? file_hash(a, fs_join(a, r->job_dir, outputs[pass])) : STR_EMPTY;
        sb_cstr(&b, ",\"output_sha256\":");
        if (hash.len) json_string(&b, hash); else sb_cstr(&b, "null");
        sb_char(&b, '}');
        Str output_bytes = STR_EMPTY;
        bool nonempty = outputs[pass] ? (fs_read(a, fs_join(a, r->job_dir, outputs[pass]), &output_bytes) && output_bytes.len) :
                                       (result.out.len || result.err.len);
        ok = args_ok && result.status == PROCESS_EXITED && result.exit_code == 0 && (!outputs[pass] || hash.len) && nonempty;
        if (!ok) report_process(names[pass], result);
    }
    Str after = file_hash(a, clang);
    bool stable = after.len && str_eq(after, clang_hash);
    ok = ok && stable;
    sb_fmt(&b, "],\"tool_unchanged\":%s,\"status\":\"%s\"}\n", stable ? "true" : "false", ok ? "success" : "failure");
    r->native_evidence_path = fs_join(a, r->job_dir, "native-evidence.json");
    return fs_write(r->native_evidence_path, sb_finish(&b)) && ok;
}

/* Same-directory temporary plus exclusive lock. We never run this public path:
 * another invocation may replace it after our lock is released. */
static bool publish(Arena *a, const char *exe, const char *out) {
    if (!out) return true;
    SB b; sb_init(&b, a); sb_fmt(&b, "%s.beryl-lock", out);
    const char *lock = str_cstr(a, sb_finish(&b));
    if (!fs_mkdir(lock)) {
        fprintf(stderr, "beryl: cannot lock output `%s` (busy, missing parent, or not writable)\n", out);
        return false;
    }
    const char *tmp = fs_join(a, lock, "publish.tmp");
    Str bytes;
    bool ok = fs_read(a, exe, &bytes) && fs_write(tmp, bytes);
#ifndef _WIN32
    if (ok) ok = chmod(tmp, 0755) == 0;
#endif
    if (ok) ok = fs_replace(tmp, out);
    if (!ok) fs_remove(tmp);
    if (!fs_rmdir(lock)) ok = false;
    if (!ok) fprintf(stderr, "beryl: cannot publish `%s`; isolated artifact retained\n", out);
    return ok;
}

bool build_native(Arena *a, SourceMap *sm, DiagBag *d, Program *p, BuildOpts o, BuildResult *r) {
    *r = (BuildResult){.compile = {.status = PROCESS_START_FAILED}};
    r->sources_json = identity_sources(a, sm);
    r->source_fingerprint = hash256_str(a, r->sources_json);
    r->compiler_fingerprint = identity_compiler(a);
    bool use_ir = o.requested_lowering && !strcmp(o.requested_lowering, "ir");
    r->selected_lowering = use_ir ? "ir" : "ast";
    Str code = STR_EMPTY;
    if (use_ir) {
        if (!o.ir_tests || o.mode != CGEN_TRACE_TESTS || o.trace_watch.enabled || o.out_exe) {
            diag_error(d, 1101, SPAN_NONE, "IR emission requires an admitted isolated differential test; production entry points and observed roots remain unavailable");
            return false;
        }
        IrVerification verified = ir_verify(o.ir_tests);
        if (!verified.ok) {
            diag_error(d, 1102, verified.source, "invalid IR at native build boundary: %s", verified.reason);
            return false;
        }
        bool same_sources = srcmap_count(sm) == o.ir_tests->sources.len;
        for (uint32_t i = 0; same_sources && i < o.ir_tests->sources.len; i++) {
            SourceFile *source = srcmap_get(sm, i);
            same_sources = source && str_eq(source->path, o.ir_tests->sources.data[i].path) &&
                str_eq(source->text, o.ir_tests->sources.data[i].text);
        }
        if (!same_sources) {
            diag_error(d, 1102, SPAN_NONE, "IR source identity differs from the native build source snapshot");
            return false;
        }
        IrCResult emitted = ir_emit_c(a, o.ir_tests, (IrCOpts){.trace_tests = true});
        if (!emitted.ok) {
            diag_error(d, 1101, emitted.error, "IR test C emission unavailable: %s", emitted.reason);
            return false;
        }
        code = emitted.source;
    } else {
        if (o.ir_tests) {
            diag_error(d, 1102, SPAN_NONE, "IR input cannot silently cross an AST build boundary");
            return false;
        }
        code = cgen_program_watched(a, sm, d, p, o.mode, o.trace_watch);
    }
    if (code.len == 0 || diag_errors(d)) return false;
    r->job_dir = fs_job_dir(a, o.cache_dir ? o.cache_dir : ".beryl-cache");
    if (!r->job_dir) {
        fprintf(stderr, "beryl: cannot create isolated native job (error %d)\n", errno);
        return false;
    }
    r->exe = fs_join(a, r->job_dir, "program.exe");
    r->c_source = fs_join(a, r->job_dir, "out.c");
    const char *rtc = fs_join(a, r->job_dir, "beryl_rt.c");
    if (!fs_write(r->c_source, code) || !fs_write(rtc, str_from(BERYL_RT_C)) ||
        !fs_write(fs_join(a, r->job_dir, "beryl_rt.h"), str_from(BERYL_RT_H))) {
        fprintf(stderr, "beryl: cannot write native job `%s`\n", r->job_dir); return false;
    }
    const char *clang = o.clang;
    if (!clang && !process_environment(a,"BERYL_CLANG",&clang)) {
        fprintf(stderr,"beryl: cannot read BERYL_CLANG as a bounded UTF-8 path\n"); return false;
    }
    if (!clang || !*clang) clang = "clang";
    Str clang_hash = STR_EMPTY;
    ProcessResult version = {.status = PROCESS_START_FAILED};
    if (o.save_native_evidence) {
        clang = process_find_executable(a, clang);
        if (clang) clang_hash = file_hash(a, clang);
        if (!clang_hash.len) {
            fprintf(stderr, "beryl: native evidence unavailable: cannot identify the selected compiler\n");
            evidence(a, r, "unavailable"); return false;
        }
        const char *version_argv[] = {clang, "--version", NULL};
        if (!save_argv(a, r->job_dir, "version.argv.json", version_argv)) return false;
        version = process_run(a, (ProcessOpts){.argv = version_argv, .log_dir = r->job_dir,
            .log_name = "version", .timeout_ms = o.timeout_ms});
        r->identity_attempted = true;
        r->compiler_identity = version;
        if (version.status != PROCESS_EXITED || version.exit_code || !version.out.len) {
            report_process("compiler identity", version); evidence(a, r, "evidence_failure"); return false;
        }
    }
    const char *argv[20]; unsigned argc = 0;
    argv[argc++] = clang; argv[argc++] = "-std=c11";
    argv[argc++] = o.release ? "-O2" : "-O0";
    if (o.release) {
        argv[argc++] = "-DNDEBUG";
        argv[argc++] = "-fno-unwind-tables";
        argv[argc++] = "-fno-asynchronous-unwind-tables";
    } else argv[argc++] = "-g";
    argv[argc++] = "-ffp-contract=off"; argv[argc++] = "-fno-fast-math";
    argv[argc++] = "-I"; argv[argc++] = r->job_dir;
    argv[argc++] = "-o"; argv[argc++] = r->exe;
    argv[argc++] = r->c_source; argv[argc++] = rtc; argv[argc] = NULL;
    SB args; sb_init(&args, a); sb_char(&args, '[');
    for (size_t i = 0; argv[i]; i++) {
        if (i) sb_char(&args, ',');
        json_string(&args, str_from(argv[i]));
    }
    sb_cstr(&args, "]\n");
    if (!fs_write(fs_join(a, r->job_dir, "compile.argv.json"), sb_finish(&args))) return false;
    r->compile = process_run(a, (ProcessOpts){.argv = argv, .log_dir = r->job_dir,
        .log_name = "compile", .timeout_ms = o.timeout_ms});
    report_process("native compiler", r->compile);
    bool ok = r->compile.status == PROCESS_EXITED && r->compile.exit_code == 0;
    Str exe_bytes;
    if (ok) ok = fs_read(a, r->exe, &exe_bytes) && exe_bytes.len != 0;
    if (!ok) {
        fprintf(stderr, "beryl: native build failed; sources/logs retained in %s\n", r->job_dir);
        evidence(a, r, "failure"); return false;
    }
    r->executable_fingerprint = hash256_str(a, exe_bytes);
    if (o.save_native_evidence && !native_evidence(a, o, r, clang, clang_hash, version, argv)) {
        fprintf(stderr, "beryl: requested native evidence failed; candidate was not published\n");
        evidence(a, r, "evidence_failure"); return false;
    }
    if (!evidence(a, r, "compiled")) return false;
    if (!publish(a, r->exe, o.out_exe)) { evidence(a, r, "publication_failure"); return false; }
    return evidence(a, r, "success");
}

bool build_and_run(Arena *a, SourceMap *sm, DiagBag *d, Program *p,
                   BuildOpts o, BuildResult *r, int *exit_code) {
    if (!build_native(a, sm, d, p, o, r)) return false;
    const char *argv[] = {r->exe, NULL};
    r->executed = true;
    r->run = process_run(a, (ProcessOpts){.argv = argv, .log_dir = r->job_dir,
        .log_name = "run", .timeout_ms = o.timeout_ms});
    report_process("program", r->run);
    bool ok = r->run.status == PROCESS_EXITED;
    if (ok && exit_code) *exit_code = (int)r->run.exit_code;
    if (!evidence(a, r, ok && r->run.exit_code == 0 ? "success" : "failure")) return false;
    return ok;
}
