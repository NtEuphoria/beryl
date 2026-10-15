#!/usr/bin/env python3
"""Behavioral gates for explicit lowering/optimization and native evidence.

Uses an explicitly selected Beryl and Clang. All inputs, fault-injection tools,
commands, compiler products, and results stay in a new build directory. This
executes native fixtures only; it never launches an engine or changes a mod.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent.parent


def sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


# A contained compiler double: version/compile succeed, one requested evidence
# stage fails or emits an empty result. Compilation copies an already verified
# fixture executable; it never invokes a shell or executes that fixture itself.
FAULT_SOURCE = r'''
#ifndef _WIN32
#define _POSIX_C_SOURCE 200809L
#endif
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#ifdef _WIN32
#include <direct.h>
#include <windows.h>
#define make_directory(p) _mkdir(p)
static void delay(void) { Sleep(2000); }
#else
#include <sys/stat.h>
#include <time.h>
#define make_directory(p) mkdir(p, 0700)
static void delay(void) { struct timespec time = {2, 0}; nanosleep(&time, NULL); }
#endif
static int copy_file(const char *source, const char *target) {
    FILE *in = fopen(source, "rb"), *out = NULL;
    if (!in || !(out = fopen(target, "wb"))) { if (in) fclose(in); return 91; }
    unsigned char block[32768]; size_t size; int ok = 1;
    while ((size = fread(block, 1, sizeof block, in)))
        if (fwrite(block, 1, size, out) != size) { ok = 0; break; }
    if (ferror(in)) ok = 0;
    if (fclose(in)) ok = 0;
    if (fclose(out)) ok = 0;
    return ok ? 0 : 92;
}
int main(int argc, char **argv) {
    const char *mode = getenv("BERYL_EVIDENCE_FAULT");
    const char *binary = getenv("BERYL_EVIDENCE_BINARY"), *output = NULL;
    int assembly = 0, ir = 0, jobs = 0;
    if (!mode || !binary) return 93;
    for (int i = 1; i < argc; ++i) {
        if (!strcmp(argv[i], "--version")) {
            if (!strcmp(mode, "timeout-version")) delay();
            if (!strcmp(mode, "fail-version")) return 23;
            if (strcmp(mode, "empty-version")) puts("Beryl evidence regression compiler double");
            return 0;
        }
        if (!strcmp(argv[i], "-o") && i + 1 < argc) output = argv[++i];
        else if (!strcmp(argv[i], "-S")) assembly = 1;
        else if (!strcmp(argv[i], "-emit-llvm")) ir = 1;
        else if (!strcmp(argv[i], "-###")) jobs = 1;
    }
    if (jobs) {
        if (strcmp(mode, "empty-jobs")) fputs("regression compiler driver jobs\n", stderr);
        return !strcmp(mode, "fail-jobs") ? 23 : 0;
    }
    if (!output) return 94;
    if (assembly) {
        if (!strcmp(mode, "timeout-ir") && ir) delay();
        if ((!strcmp(mode, "fail-ir") && ir) || (!strcmp(mode, "fail-assembly") && !ir)) return 23;
        FILE *file = fopen(output, "wb");
        if (!file) return 95;
        if (!((!strcmp(mode, "empty-ir") && ir) || (!strcmp(mode, "empty-assembly") && !ir)))
            fputs("regression nonempty compiler output\n", file);
        return fclose(file) ? 96 : 0;
    }
    int result = copy_file(binary, output);
    if (!result && !strcmp(mode, "unwritable-manifest")) {
        char directory[32768]; size_t length = strlen(output);
        if (length >= sizeof directory) return 97;
        memcpy(directory, output, length + 1);
        char *slash = strrchr(directory, '/'), *back = strrchr(directory, '\\');
        if (!slash || (back && back > slash)) slash = back;
        if (!slash || (size_t)(slash - directory) + sizeof "/native-evidence.json" > sizeof directory) return 98;
        strcpy(slash + 1, "native-evidence.json");
        if (make_directory(directory)) return 99;
    }
    return result;
}
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--beryl", required=True, type=Path)
    parser.add_argument("--clang", required=True, type=Path)
    args = parser.parse_args()
    beryl, clang = args.beryl.resolve(strict=True), args.clang.resolve(strict=True)
    work = Path(tempfile.mkdtemp(prefix="native evidence & spaces-", dir=ROOT / "build"))
    env = os.environ.copy()
    env["PATH"] = str(clang.parent) + os.pathsep + env.get("PATH", "")
    env["BERYL_CLANG"] = str(clang)
    evidence = {"schema_version": 1, "status": "running", "compiler_sha256": sha(beryl),
                "clang_sha256": sha(clang), "script_sha256": sha(Path(__file__)),
                "commands": [], "checks": [], "engine_execution": "not_run"}
    print(f"Native evidence artifacts: {work}", flush=True)

    def run(*argv, expected=0, extra_env=None):
        command = list(map(str, argv))
        process = subprocess.run(command, cwd=work, env=extra_env or env,
                                 capture_output=True, text=True, encoding="utf-8",
                                 errors="strict", timeout=120)
        evidence["commands"].append({"argv": command, "cwd": str(work),
                                     "exit_code": process.returncode,
                                     "stdout": process.stdout, "stderr": process.stderr})
        if expected is not None:
            assert process.returncode == expected, (command, process.returncode, process.stdout, process.stderr)
        return process

    def jobs():
        return set((work / ".beryl-cache").glob("job-*"))

    def invoke(*argv, expected=0, extra_env=None, creates_job=True):
        before = jobs()
        process = run(beryl, *argv, expected=expected, extra_env=extra_env)
        added = jobs() - before
        assert len(added) == int(creates_job), (argv, added)
        return process, next(iter(added)) if added else None

    def passed(name):
        evidence["checks"].append(name)
        print(f"passed {name}", flush=True)

    def inspect_native(job, source, *, release, lowering, optimization, disabled, executed=False):
        result = read_json(job / "result.json")
        details = read_json(job / "native-evidence.json")
        assert result["schema_version"] == details["schema_version"] == 1
        assert result["operation"] == "native_build" and result["status"] == "success"
        assert details["operation"] == "native_evidence" and details["stage"] == "compiler_evidence"
        assert details["status"] == "success" and details["tool_unchanged"]
        assert details["requested_lowering"] == lowering and details["selected_lowering"] == "ast"
        assert details["optimization_policy"] == optimization and details["selected_optimizations"] == []
        assert details["disabled_optimizations"] == disabled
        assert details["measurement_status"] == "not_measured"
        assert details["program_execution"] == "not_executed_by_evidence_capture"
        assert Path(result["native_evidence"]).resolve() == (job / "native-evidence.json").resolve()
        assert result["compiler_fingerprint"] == details["compiler_fingerprint"] == evidence["compiler_sha256"]
        assert result["artifact_fingerprint"] == details["artifact_fingerprint"] == sha(job / "program.exe")
        assert details["generated_c_fingerprint"] == sha(job / "out.c")
        assert result["sources"] == [{"path": str(source), "sha256": sha(source)}]
        serialized = json.dumps(result["sources"], separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        assert result["source_fingerprint"] == details["source_fingerprint"] == hashlib.sha256(serialized).hexdigest()
        assert details["runtime_fingerprints"] == {"header": sha(job / "beryl_rt.h"), "implementation": sha(job / "beryl_rt.c")}
        assert Path(details["clang"]["path"]).resolve() == clang
        assert details["clang"]["sha256"] == evidence["clang_sha256"]
        assert read_json(job / "version.argv.json") == [str(clang), "--version"]
        version = details["clang"]["version"]
        assert result["compiler_identity"] == version
        assert version["status"] == "exited" and version["exit_code"] == 0
        assert Path(version["stdout_log"]).read_bytes() == (work / "clang-version.txt").read_bytes()
        expected_flags = [str(clang), "-std=c11", "-O2" if release else "-O0"]
        expected_flags += ["-DNDEBUG", "-fno-unwind-tables", "-fno-asynchronous-unwind-tables"] if release else ["-g"]
        expected_flags += ["-ffp-contract=off", "-fno-fast-math", "-I", str(job)]
        # fs_join deliberately retains the absolute job prefix and appends '/'.
        generated = lambda name: str(job) + "/" + name
        compile_argv = read_json(job / "compile.argv.json")
        assert compile_argv == expected_flags + ["-o", generated("program.exe"), generated("out.c")]
        assert read_json(job / "driver-jobs.argv.json") == compile_argv + ["-###"]
        assert [item["name"] for item in details["passes"]] == ["llvm-ir", "assembly", "driver-jobs"]
        for index, (name, suffix) in enumerate((("llvm-ir", "ll"), ("assembly", "s"))):
            output = job / f"out.{suffix}"
            expected = expected_flags + ["-S"] + (["-emit-llvm"] if suffix == "ll" else [])
            assert read_json(job / f"{name}.argv.json") == expected + [generated("out.c"), "-o", generated(f"out.{suffix}")]
            assert output.stat().st_size > 0 and details["passes"][index]["output_sha256"] == sha(output)
        assert b"define" in (job / "out.ll").read_bytes()
        assert details["passes"][2]["output_sha256"] is None
        for item in details["passes"]:
            assert item["process"]["status"] == "exited" and item["process"]["exit_code"] == 0
            assert Path(item["process"]["stdout_log"]).is_file() and Path(item["process"]["stderr_log"]).is_file()
        if executed:
            assert result["run"]["status"] == "exited" and result["run"]["exit_code"] == 0
        else:
            assert result["run"] is None and not (job / "run.stdout.log").exists()
        return result, details

    try:
        source = work / "logic & literal $.be"
        source.write_text('module evidence_fixture\nfn main() { println("exact native fixture") }\n'
                          'test "arithmetic" { assert(2 + 3 == 5) }\n', encoding="utf-8")
        test_source = work / "test & space.be"
        test_source.write_text('module evidence_test\ntest "arithmetic" { assert(2 + 3 == 5) }\n', encoding="utf-8")
        evidence["fixture_hashes"] = {str(path): sha(path) for path in (source, test_source)}
        version = run(clang, "--version")
        (work / "clang-version.txt").write_bytes(version.stdout.encode("utf-8"))
        published = work / "published & exact.exe"
        _, off = invoke("build", "--release", "--save-native-evidence", "--lowering", "ast", "--opt", "off",
                        "--disable-opt", "expiry-certificate", "--disable-opt", "checked-search", "-o", published, source)
        inspect_native(off, source, release=True, lowering="ast", optimization="off", disabled=["expiry-certificate", "checked-search"])
        assert sha(published) == sha(off / "program.exe")
        passed("release off retains exact O2/FP argv, tool version, source/runtime/product hashes, LLVM IR and assembly")

        _, auto = invoke("build", "--release", "--save-native-evidence", "--clang", "clang", "-o", published, source)
        inspect_native(auto, source, release=True, lowering="auto", optimization="auto", disabled=[])
        assert (off / "out.c").read_bytes() == (auto / "out.c").read_bytes()
        assert (off / "beryl_rt.c").read_bytes() == (auto / "beryl_rt.c").read_bytes()
        passed("auto/off use the same generated C and release Clang policy with zero released Beryl families")

        process, debug = invoke("run", "--save-native-evidence", "--lowering", "auto", "--opt", "off", source)
        inspect_native(debug, source, release=False, lowering="auto", optimization="off", disabled=[], executed=True)
        assert process.stdout.splitlines()[0] == "exact native fixture"
        assert (debug / "run.stdout.log").read_text(encoding="utf-8") == "exact native fixture\n"
        passed("debug keeps O0 and requested run executes the isolated candidate after evidence capture")

        _, differential = invoke("test", "--backend", "differential", "--save-native-evidence", "--lowering", "ast", "--opt", "off", test_source)
        comparison = read_json(differential / "result.json")
        assert comparison["status"] == "success" and comparison["stage"] == "comparison"
        nested = list(differential.rglob("native-evidence.json"))
        assert len(nested) == 1
        inspect_native(nested[0].parent, test_source, release=False, lowering="ast", optimization="off", disabled=[])
        passed("differential mode retains native evidence and independently reaches comparison")

        for arguments in (("--save-native-evidence",), ("--opt", "off"), ("--opt", "auto"),
                          ("--disable-opt", "expiry-certificate"), ("--lowering", "auto"), ("--lowering", "ir")):
            process, _ = invoke("test", "--backend", "reference", *arguments, test_source, expected=2, creates_job=False)
            assert "BE0804" in process.stderr
        _, reference = invoke("test", "--backend", "reference", "--lowering", "ast", test_source)
        assert read_json(reference / "result.json")["status"] == "success"
        assert not list(reference.rglob("compile.argv.json"))
        passed("reference rejects native controls while explicit AST remains accepted without native compilation")

        previous_source = work / "previous published.be"
        previous_source.write_text('module previous_fixture\nfn main() { println("previous public artifact") }\n', encoding="utf-8")
        evidence["fixture_hashes"][str(previous_source)] = sha(previous_source)
        _, previous = invoke("build", "-o", published, previous_source)
        assert not (previous / "native-evidence.json").exists()
        assert read_json(previous / "result.json")["compiler_identity"] is None
        old_hash = sha(published)
        # A faulty promotion must be visible even when the candidate can execute.
        assert old_hash != sha(auto / "program.exe")
        for command in ("build", "run", "test"):
            process, _ = invoke(command, "--lowering", "ir", "-o", published, source, expected=3, creates_job=False)
            assert "status=unavailable; capability=lowering.ir" in process.stderr and sha(published) == old_hash
        for arguments in (("--lowering", "bogus"), ("--opt", "on"), ("--lowering", "ast", "--lowering", "ast"),
                          ("--opt", "off", "--opt", "off"), ("--disable-opt", "not-a-registered-family"),
                          ("--target", "enfusion", "--save-native-evidence")):
            process, _ = invoke("build", *arguments, "-o", published, source, expected=2, creates_job=False)
            assert "BE0804" in process.stderr and sha(published) == old_hash
        process, _ = invoke("check", "--format", "json", "--opt", "off", source, expected=1, creates_job=False)
        assert any(item["code"] == "BE0804" for item in json.loads(process.stdout)["diagnostics"])
        passed("unsupported IR and invalid options fail before jobs or publication; unknown family cannot silently succeed")

        process, missing = invoke("run", "--save-native-evidence", "--clang", work / "missing compiler.exe", "-o", published, source, expected=1)
        assert read_json(missing / "result.json")["status"] == "unavailable"
        assert read_json(missing / "result.json")["compiler_identity"] is None
        assert sha(published) == old_hash and not (missing / "run.stdout.log").exists()
        passed("missing tool identity is unavailable and cannot publish or run a previous artifact")

        fault_source = work / "fault compiler.c"
        fault_source.write_text(FAULT_SOURCE, encoding="utf-8")
        fault = work / "fault compiler & spaces.exe"
        run(clang, "-std=c11", "-Wall", "-Wextra", "-Werror", fault_source, "-o", fault)
        evidence["fault_source_sha256"] = sha(fault_source)
        evidence["fault_compiler_sha256"] = sha(fault)
        for mode in ("fail-ir", "fail-assembly", "fail-jobs", "empty-version", "fail-version", "timeout-version",
                     "timeout-ir", "empty-ir", "empty-assembly", "empty-jobs", "unwritable-manifest"):
            fault_env = dict(env, BERYL_EVIDENCE_FAULT=mode, BERYL_EVIDENCE_BINARY=str(auto / "program.exe"))
            timeout = ["--timeout-ms", "500"] if mode.startswith("timeout-") else []
            process, failed = invoke("run", "--save-native-evidence", "--clang", fault, *timeout, "-o", published, source, expected=1, extra_env=fault_env)
            result = read_json(failed / "result.json")
            assert result["status"] == "evidence_failure" and result["run"] is None
            assert sha(published) == old_hash and not (failed / "run.stdout.log").exists()
            identity = result["compiler_identity"]
            if mode == "timeout-version":
                assert identity["status"] == "timeout" and identity["exit_code"] is None
            elif mode == "fail-version":
                assert identity["status"] == "exited" and identity["exit_code"] == 23
            else:
                assert identity["status"] == "exited" and identity["exit_code"] == 0
            if mode.endswith("version"):
                assert not (failed / "compile.argv.json").exists()
            if mode not in ("empty-version", "fail-version", "timeout-version", "unwritable-manifest"):
                details = read_json(failed / "native-evidence.json")
                assert details["status"] == "failure"
                if mode == "timeout-ir":
                    assert details["passes"][0]["process"]["status"] == "timeout"
                    assert details["passes"][0]["process"]["exit_code"] is None
            passed(f"{mode}: incomplete evidence cannot publish or execute; previous output is preserved")

        assert sha(beryl) == evidence["compiler_sha256"] and sha(clang) == evidence["clang_sha256"]
        assert sha(Path(__file__)) == evidence["script_sha256"]
        assert all(sha(Path(path)) == digest for path, digest in evidence["fixture_hashes"].items())
        evidence["status"] = "success"
    except BaseException as error:
        evidence["status"] = "failure"
        evidence["error"] = repr(error)
        raise
    finally:
        (work / "results.json").write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"All {len(evidence['checks'])} native evidence groups passed.", flush=True)


if __name__ == "__main__":
    main()
