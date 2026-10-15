#!/usr/bin/env python3
"""Verify explicit source traps and a bounded registered array observation.

Native mutants and test tool substitutes are built only in an isolated job.
Compiler/source/tool failures never qualify as an expected program trap.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests/reference/expected_traps"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--beryl", required=True, type=Path)
    parser.add_argument("--clang", required=True, type=Path)
    args = parser.parse_args()
    beryl, clang = args.beryl.resolve(), args.clang.resolve()
    work = Path(tempfile.mkdtemp(prefix="expected traps & ", dir=ROOT / "build"))
    env = os.environ.copy()
    env["PATH"] = str(clang.parent) + os.pathsep + env.get("PATH", "")
    input_paths = [Path(__file__).resolve(), clang, *sorted(FIXTURES.glob("*.be"))]
    evidence = {"schema_version": 1, "status": "running", "compiler_sha256": hashlib.sha256(beryl.read_bytes()).hexdigest(),
                "input_sha256": {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in input_paths},
                "checks": [], "commands": [], "coverage": "i32 source overflow/division_by_zero/fixed-array bounds; ordered observations; one registered flat i32 array"}
    print(f"Expected-trap artifacts: {work}", flush=True)

    def run(argv, expected=0, timeout=60):
        argv = list(map(str, argv))
        proc = subprocess.run(argv, cwd=work, env=env, capture_output=True, text=True,
                              encoding="utf-8", errors="strict", timeout=timeout)
        evidence["commands"].append({"argv": argv, "exit_code": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr})
        if expected is not None and proc.returncode != expected:
            raise AssertionError(f"Exit {proc.returncode}, expected {expected}: {argv}\n{proc.stdout}\n{proc.stderr}")
        return proc

    def passed(name):
        evidence["checks"].append(name)
        print(f"passed {name}", flush=True)

    def jobs():
        return set((work / ".beryl-cache").glob("job-*"))

    def execute(source, expectation=None, *, watch=None, extra=(), compiler=None, success=True, status=None):
        argv = [beryl, "test", "--backend", "differential", "--clang", compiler or clang]
        if expectation:
            argv += ["--expect-source-trap", expectation]
        if watch:
            argv += ["--observe-root", watch]
        argv += [*extra, source]
        previous = jobs()
        proc = run(argv, expected=None)
        fresh = jobs() - previous
        assert len(fresh) == 1, (fresh, proc.stdout, proc.stderr)
        job = fresh.pop()
        result = json.loads((job / "result.json").read_text(encoding="utf-8"))
        assert (proc.returncode == 0) == success, (result, proc.stderr)
        assert (result["status"] == "success") == success, result
        if status:
            assert result["status"] == status, result
        if expectation and success:
            assert result["verification"] == "expected_source_trap", result
            assert result["program_outcome"] == "trap" and result["reference_status"] == "trap", result
            assert result["compared"] and result["native_source_trap_verified"], result
            assert result["native_status"] == "exited" and result["native_exit_code"] != 0, result
            events = [json.loads(s) for s in (job / "reference.events.jsonl").read_text().splitlines()]
            assert events[-1]["event"] == "source_trap" and events[-1]["complete"] is True
            assert [e["seq"] for e in events] == list(range(len(events)))
            assert not any(e["event"] == "test_end" for e in events)
        elif expectation:
            assert result["native_source_trap_verified"] is False, result
        return result, job, proc

    def copy_fixture(name):
        path = work / name
        shutil.copyfile(FIXTURES / name, path)
        return path

    def expect(source, kind, text):
        data = source.read_bytes()
        assert data.count(text.encode()) == 1, (source, text)
        return f"{kind}@0:{data.index(text.encode())}"

    def compile_c(name, code, runtime=None):
        cfile, binary = work / f"{name}.c", work / f"{name}.exe"
        cfile.write_text(code, encoding="utf-8", newline="\n")
        argv = [clang, "-std=c11", "-O2", "-ffp-contract=off", "-fno-fast-math"]
        if runtime:
            argv += ["-I", runtime.parent, cfile]
            if '#include "beryl_rt.c"' not in code:
                argv.append(runtime)
        else:
            argv += [cfile]
        run([*argv, "-o", binary])
        return binary

    def publisher(payload, name):
        # A deliberately limited compiler substitute copies one already-built
        # mutant to the requested output. It never runs a shell or edits inputs.
        code = '#include <stdio.h>\n#include <string.h>\nint main(int argc,char **argv) {\n'
        code += 'const char *out=0; for(int i=1;i+1<argc;i++) if(!strcmp(argv[i],"-o")) out=argv[i+1];\n'
        code += f'FILE *in=fopen({json.dumps(str(payload))},"rb"); FILE *to=out?fopen(out,"wb"):0;\n'
        code += 'if(!in||!to)return 2; char bytes[16384]; size_t n; int bad=0; while((n=fread(bytes,1,sizeof bytes,in))) if(fwrite(bytes,1,n,to)!=n){bad=1;break;}\n'
        code += 'bad|=ferror(in); bad|=fclose(in)!=0; bad|=fclose(to)!=0; return bad?2:0;}\n'
        return compile_c(name, code)

    try:
        cases = [
            ("overflow_prefix.be", "overflow", "limit + one", "21\n21\n"),
            ("division.be", "division_by_zero", "numerator / denominator", "prefix:"),
            ("bounds.be", "bounds", "values[index]", "10\n"),
            ("first_failure.be", "division_by_zero", "1 / zero", "first\n"),
            ("compound.be", "overflow", "value += rhs()", "rhs\n"),
            ("negation.be", "overflow", "-minimum", "negate\n"),
            ("division_overflow.be", "overflow", "minimum / negative_one", ""),
            ("remainder_zero.be", "division_by_zero", "value % zero", ""),
        ]
        for name, kind, text, stdout in cases:
            source = copy_fixture(name)
            expectation = expect(source, kind, text)
            for extra in ((), ("--release",)):
                _, job, _ = execute(source, expectation, extra=extra)
                assert (job / "reference.stdout.log").read_text() == stdout
        passed("eight explicit first-source-trap fixtures and exact observation prefixes at O0/O2")

        defined = copy_fixture("remainder_defined.be")
        for extra in ((), ("--release",)):
            result, _, _ = execute(defined, extra=extra)
            assert result["reference_status"] == "success" and result["compared"]
        passed("independent oracle preserves defined INT_MIN remainder -1 as zero")

        source = copy_fixture("registered_root.be")
        expectation = expect(source, "overflow", "limit + one")
        watch = f'0:{source.read_bytes().index(b"var values")}'
        for extra in ((), ("--release",)):
            result, root_job, _ = execute(source, expectation, watch=watch, extra=extra)
            events = [json.loads(s) for s in (root_job / "reference.events.jsonl").read_text().splitlines()]
            root_values = [e["value"] for e in events if e["event"] == "root_i32"]
            assert root_values == [21, 21, 0, 0], events
            assert sum(e["event"] == "root_begin" for e in events) == 1
            assert sum(e["event"] == "root_end" for e in events) == 1
            assert not (root_job / "reference.stdout.log").read_bytes()
        passed("registered actual array captures complete successful write prefix without body prints")

        _, _, ordinary = execute(source, success=False)
        assert ordinary.returncode != 0
        execute(source, expectation.replace("overflow@", "bounds@"), success=False)
        execute(source, expectation + "0", success=False)
        execute(defined, "overflow@0:0", success=False)
        execute(source, expectation, extra=("--max-steps", "1"), success=False)
        execute(source, expectation, compiler=work / "missing compiler.exe", success=False)
        passed("ordinary traps, wrong expectations, successful programs, budget exhaustion and absent compiler never verify")

        unsupported = work / "unsupported.be"
        unsupported.write_text('module unsupported\ntest "wide" {\nlet n: i64 = 1\nprintln(n)\n}\n')
        execute(unsupported, "overflow@0:0", success=False, status="unavailable")
        execute(source, expectation, watch="0:0", success=False, status="unavailable")
        uninitialized = work / "uninitialized-root.be"
        uninitialized.write_text('module root_inactive\ntest "root comes later" {\nlet zero=0\nprintln(1 / zero)\nvar values=[0,0]\n}\n')
        execute(uninitialized, expect(uninitialized, "division_by_zero", "1 / zero"),
                watch=f'0:{uninitialized.read_bytes().index(b"var values")}', success=False, status="unavailable")
        passed("unsupported types, absent roots and roots not yet initialized remain unavailable")

        malformed = ["overflow", "overflow@0", "overflow@0:", "overflow@-1:0", "overflow@0:+1", "overflow@0:1junk",
                     "overflow@4294967295:0", "overflow@0:4294967296", "panic@0:0", " overflow@0:0"]
        for value in malformed:
            previous = jobs()
            rejected = run([beryl, "test", "--backend", "differential", "--expect-source-trap", value, source], expected=None)
            assert rejected.returncode != 0 and jobs() == previous
        for argv in (["--backend", "reference", "--expect-source-trap", expectation],
                     ["--backend", "differential", "--observe-root", watch],
                     ["--backend", "differential", "--expect-source-trap", expectation, "--expect-source-trap", expectation],
                     ["--backend", "differential", "--expect-source-trap", expectation, "--observe-root", watch, "--observe-root", watch]):
            previous = jobs()
            rejected = run([beryl, "test", *argv, source], expected=None)
            assert rejected.returncode != 0 and jobs() == previous
        passed("strict expectation/root CLI parsing, duplicates and incompatible backends reject before execution")

        native_job = Path(result["native_job"])
        baseline = (native_job / "out.c").read_text(encoding="utf-8")
        runtime_text = (native_job / "beryl_rt.c").read_text(encoding="utf-8")
        root_name = re.search(r'\b(be_l_\d+_values)\s*=', baseline)[1]
        assignment = re.search(r'\(\*_t\d+\) = be_add_i32_at\([^;]+;', baseline)
        assert assignment, "checked root update not found"
        site = expectation.rsplit(":", 1)[1]
        assert baseline.count(f", 0, {site})") == 1
        mutants = {
            "wrong-site": (baseline.replace(f", 0, {site})", f", 0, {int(site)+1})"), runtime_text),
            "missing-terminal": (baseline, runtime_text.replace('source_trap_trace("overflow");', '(void)0;', 1)),
            "wrong-kind": (baseline, runtime_text.replace('source_trap_trace("overflow");', 'source_trap_trace("bounds");', 1)),
            "incomplete-terminal": (baseline, runtime_text.replace('\\"complete\\":true', '\\"complete\\":false')),
            "missing-store-prefix": (baseline[:assignment.start()] + '(void)0;' + baseline[assignment.end():], runtime_text),
            "extra-array-write": (baseline[:assignment.start()] + f'{root_name}.v[3] = 99;\n' + baseline[assignment.start():], runtime_text),
            "missing-root-registration": (re.sub(r'beryl_test_root_i32\([^;]+;', '(void)0;', baseline), runtime_text),
            "truncated-root": (baseline, runtime_text.replace('i<g_root_length', 'i+1<g_root_length')),
            "extra-event": (baseline, runtime_text.replace('source_trap_trace("overflow");', 'source_trap_trace("overflow"); beryl_test_event("extra",0,0,true);', 1)),
            "zero-exit": (baseline, runtime_text.replace('abort();', 'exit(0);')),
        }
        for name, (code, runtime) in mutants.items():
            assert code != baseline or runtime != runtime_text, name
            mutant_dir = work / name
            mutant_dir.mkdir()
            shutil.copyfile(native_job / "beryl_rt.h", mutant_dir / "beryl_rt.h")
            runtime_path = mutant_dir / "beryl_rt.c"
            runtime_path.write_text(runtime, encoding="utf-8", newline="\n")
            payload = compile_c(name, code, runtime_path)
            fake = publisher(payload, f"publish-{name}")
            execute(source, expectation, watch=watch, compiler=fake, success=False)
        passed("ten compiled trace/root/first-site/process-outcome mutants are rejected")

        crash = compile_c("no-source-trap", 'int main(void) {return 42;}\n')
        execute(source, expectation, compiler=publisher(crash, "publish-crash"), success=False)
        hang = compile_c("hang", '#include <stdio.h>\n#ifdef _WIN32\n#include <windows.h>\n#else\n#include <unistd.h>\n#endif\nint main(void){puts("owned-native-start");fflush(stdout);for(;;){\n#ifdef _WIN32\nSleep(1000);\n#else\nsleep(1);\n#endif\n}}\n')
        hang_compiler = publisher(hang, "publish-hang")
        execute(source, expectation, compiler=hang_compiler, extra=("--timeout-ms", "500"), success=False, status="timeout")
        passed("arbitrary nonzero process exits and native timeouts cannot masquerade as source traps")

        previous = jobs()
        argv = list(map(str, [beryl, "test", "--backend", "differential", "--clang", hang_compiler,
                            "--expect-source-trap", expectation, "--timeout-ms", "10000", source]))
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
        proc = subprocess.Popen(argv, cwd=work, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True, encoding="utf-8", creationflags=creationflags)
        try:
            deadline = time.monotonic() + 10
            fresh = set()
            while time.monotonic() < deadline:
                fresh = jobs() - previous
                if len(fresh) == 1 and any("owned-native-start" in f.read_text(errors="replace") for f in fresh.copy().pop().rglob("differential.stdout.log")):
                    break
                assert proc.poll() is None, "verification exited before cancellation handshake"
                time.sleep(0.025)
            else:
                raise AssertionError("native cancellation handshake missing")
            proc.send_signal(signal.CTRL_BREAK_EVENT if os.name == "nt" else signal.SIGINT)
            stdout, stderr = proc.communicate(timeout=10)
            evidence["commands"].append({"argv": argv, "exit_code": proc.returncode, "stdout": stdout, "stderr": stderr, "external_cancellation": True})
            cancelled = json.loads((fresh.pop() / "result.json").read_text())
            assert proc.returncode != 0 and cancelled["status"] == "cancelled" and not cancelled["native_source_trap_verified"], cancelled
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait()
        passed("external cancellation during owned native execution remains cancelled")
        assert hashlib.sha256(beryl.read_bytes()).hexdigest() == evidence["compiler_sha256"], "compiler changed during verification"
        assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest() == digest for p, digest in evidence["input_sha256"].items()), "verification input changed"
        evidence["status"] = "passed"
    except Exception as exc:
        evidence["status"] = "failed"
        evidence["failure"] = str(exc)
        raise
    finally:
        path = work / "results.json"
        path.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
        print(f"Evidence: {path}", flush=True)


if __name__ == "__main__":
    main()
