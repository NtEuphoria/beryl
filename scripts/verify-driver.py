#!/usr/bin/env python3
"""Behavioral native-driver gates. Run against an explicitly selected compiler.

All fixtures and raw subprocess results are retained in a unique directory. Only
Python's standard library is required. A missing/denied tool is failure, not skip.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import signal
import shutil
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--beryl", required=True, type=Path)
    parser.add_argument("--clang", required=True, type=Path)
    args = parser.parse_args()
    beryl, clang = args.beryl.resolve(), args.clang.resolve()
    work = Path(tempfile.mkdtemp(prefix="driver & spaces-", dir=ROOT / "build"))
    env = os.environ.copy()
    env["PATH"] = str(clang.parent) + os.pathsep + env.get("PATH", "")
    env["BERYL_CLANG"] = str(clang)
    evidence = {"schema_version": 1, "status": "running", "checks": [], "commands": [],
                "beryl_sha256": hashlib.sha256(beryl.read_bytes()).hexdigest(),
                "clang_sha256": hashlib.sha256(clang.read_bytes()).hexdigest()}
    def source_hashes():
        return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                for folder in ("src", "runtime", "tests", "scripts", "examples", "lib", "packages", "schemas", "tools")
                for p in sorted((ROOT / folder).rglob("*"))
                if p.is_file() and not {"__pycache__", ".beryl-mod", ".beryl-cache"}.intersection(p.parts)}
    evidence["source_hashes"] = source_hashes()
    print(f"Driver artifacts: {work}", flush=True)

    def run(argv, cwd=work, expected=0, timeout=30, extra_env=None):
        command = [str(p) for p in argv]
        started = time.monotonic()
        proc = subprocess.run(command, cwd=cwd, env=extra_env or env, capture_output=True,
                              text=True, encoding="utf-8", errors="strict", timeout=timeout)
        evidence["commands"].append({"argv": command, "cwd": str(cwd),
            "exit_code": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr,
            "seconds": time.monotonic() - started})
        if expected is not None and proc.returncode != expected:
            raise AssertionError(f"expected exit {expected}, got {proc.returncode}: {command}\n{proc.stderr}")
        return proc

    def passed(name):
        evidence["checks"].append(name)
        print(f"passed {name}", flush=True)

    def check_failure(argv, cwd=work):
        r = run([beryl, "check", "--format", "json", *argv], cwd=cwd, expected=None)
        data = json.loads(r.stdout)
        assert r.returncode != 0 and data["status"] == "failure" and data["diagnostics"]
        assert not r.stderr
        return data

    try:
        src = work / "logic & space.be"
        src.write_text('module driver\nfn main() { println("exact candidate") }\n'
                       'test "executes" { assert(2 + 3 == 5) }\n', encoding="utf-8")
        r = run([beryl, "check", "--format", "json", src])
        identity = json.loads(r.stdout)
        assert identity["status"] == "success" and not r.stderr
        assert identity["compiler_fingerprint"] == evidence["beryl_sha256"]
        assert identity["sources"][0]["sha256"] == hashlib.sha256(src.read_bytes()).hexdigest()
        check_failure([work / 'missing "quoted".be'])
        check_failure(["--misspelled", src])
        check_failure(["--target", "imaginary", src])
        check_failure(["--timeout-ms", "-1", src])
        check_failure([])
        bad = work / "bad.be"
        bad.write_text("module bad\nfn main() {\n    let n: i32 = true\n}\n", encoding="utf-8")
        data = check_failure([bad])
        loc = next(d["primary"] for d in data["diagnostics"] if d["primary"])
        assert loc["file"] == str(bad) and loc["line"] == 3 and loc["offset"] >= 20
        bad.write_bytes(b"module bad\nfn main() {\xff}\n")
        check_failure([bad])
        passed("JSON success, errors, escaping, option errors, and source locations")

        package = work / "package"
        (package / "src").mkdir(parents=True)
        (package / "src/main.be").write_text('module m\n@unsafe(raw_ptr)\nfn f() {}\n', encoding="utf-8")
        manifest = package / "beryl.toml"
        manifest.write_text('[package]\nname="fixture"\n[security]\nforbid_unsafe=true # trailing comment\n', encoding="utf-8")
        data = check_failure([], cwd=package)
        assert any(d["code"] == "BE0605" for d in data["diagnostics"])
        for value in ['truth', '"true"', '', 'false trailing']:
            manifest.write_text(f'[package]\nname="fixture"\n[security]\nforbid_unsafe={value}\n', encoding="utf-8")
            data = check_failure([], cwd=package)
            assert any(d["code"] == "BE0801" for d in data["diagnostics"])
        passed("manifest comments preserve forbid_unsafe; malformed values fail")

        r = run([beryl, "run", src])
        assert r.stdout == "exact candidate\n"
        r = run([beryl, "run", "--release", src])
        assert r.stdout == "exact candidate\n"
        r = run([beryl, "test", src])
        assert r.stdout == "ok  1 test, 1 assertion\n"
        r = run([beryl, "run", "--target", "enfusion", src], expected=None)
        assert r.returncode != 0 and "unavailable" in r.stderr
        empty = work / "no-tests.be"
        empty.write_text("module empty\nfn main() {}\n", encoding="utf-8")
        assert run([beryl, "test", empty], expected=None).returncode != 0
        passed("run and test execute; absent tests and unsupported engine execution fail")

        out = work / "public & spaces.exe"
        run([beryl, "build", "-o", out, src])
        previous = out.read_bytes()
        r = run([beryl, "run", "--clang", work / "missing-clang.exe", "-o", out, src], expected=None)
        assert r.returncode != 0 and "startup_failure" in r.stderr and not r.stdout
        assert out.read_bytes() == previous
        assert run([out]).stdout == "exact candidate\n"
        r = run([beryl, "run", "-o", work / "absent/output.exe", src], expected=None)
        assert r.returncode != 0 and "cannot lock output" in r.stderr and not r.stdout
        passed("failed compiler/publication cannot run or overwrite previous executable")

        # A compiler wrapper that lies about success must not reuse any old output.
        helper_c = work / "tool.c"
        helper_c.write_text('int main(void) { return 0; }\n', encoding="utf-8")
        helper = work / "false success & tool.exe"
        run([clang, helper_c, "-o", helper])
        r = run([beryl, "run", "--clang", helper, "-o", out, src], expected=None)
        assert r.returncode != 0 and out.read_bytes() == previous and not r.stdout
        helper_c.write_text('int main(void) { return 127; }\n', encoding="utf-8")
        fail127 = work / "exit-127.exe"
        run([clang, helper_c, "-o", fail127])
        r = run([beryl, "run", "--clang", fail127, src], expected=None)
        assert r.returncode != 0 and "status 127" in r.stderr and "startup_failure" not in r.stderr
        passed("false-success compiler and child exit 127 remain failures")

        # Windows must not implicitly prefer a project-local clang.exe over PATH.
        # The fixture would exit 0 without output if it were accidentally selected.
        shutil.copyfile(helper, work / "clang.exe")
        path_env = env.copy()
        path_env.pop("BERYL_CLANG", None)
        r = run([beryl, "run", src], extra_env=path_env)
        assert r.stdout == "exact candidate\n"
        passed("default compiler resolves from PATH without implicit project shadowing")

        files = []
        for i in range(6):
            source = work / f"parallel-{i}.be"
            source.write_text(f'module p{i}\nfn main() {{ println({i}) }}\n', encoding="utf-8")
            files.append(source)
        def parallel(item):
            i, source = item
            r = run([beryl, "run", "-o", work / f"parallel-{i}.exe", source])
            assert r.stdout == f"{i}\n"
        with ThreadPoolExecutor(max_workers=6) as pool:
            list(pool.map(parallel, enumerate(files)))
        jobs = list((work / ".beryl-cache").glob("job-*/compile.argv.json"))
        generated_paths = [json.loads(p.read_text(encoding="utf-8"))[-2] for p in jobs]
        assert len(jobs) >= 6 and len(set(generated_paths)) == len(generated_paths)
        passed("six concurrent native jobs retain independent code and executable outputs")

        # Deliberately hold the output lock; the compiler cannot silently publish.
        lock = Path(str(out) + ".beryl-lock")
        lock.mkdir()
        r = run([beryl, "build", "-o", out, src], expected=None)
        assert r.returncode != 0 and out.read_bytes() == previous
        lock.rmdir()
        passed("contended publication fails without replacing existing output")

        loop = work / "loop.be"
        loop.write_text("module loop\nfn main() { while true {} }\n", encoding="utf-8")
        # Compile the real fixture under the ordinary compilation budget first.
        # A short per-process timeout during a busy Clang build would test the
        # compiler phase rather than the intended program-execution phase.
        loop_exe = work / "verified-loop.exe"
        run([beryl, "build", "-o", loop_exe, loop], timeout=120)
        copy_c = work / "copy-timeout-fixture.c"
        copy_c.write_text(r'''
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
int main(int argc,char **argv) {
 const char *target=NULL;
 for(int i=1;i+1<argc;i++) if(!strcmp(argv[i],"-o")) target=argv[i+1];
 const char *source=getenv("BERYL_TIMEOUT_FIXTURE");
 if(!source||!target) return 2;
 FILE *input=fopen(source,"rb"); if(!input) return 3;
 FILE *output=fopen(target,"wb"); if(!output){fclose(input);return 4;}
 unsigned char bytes[8192]; size_t count; int failed=0;
 while((count=fread(bytes,1,sizeof bytes,input))) if(fwrite(bytes,1,count,output)!=count){failed=1;break;}
 if(ferror(input)) failed=1;
 if(fclose(input)) failed=1;
 if(fclose(output)) failed=1;
 return failed?5:0;
}
''', encoding="utf-8")
        copy_tool = work / "copy-timeout-fixture.exe"
        run([clang, copy_c, "-o", copy_tool])
        loop_env = env.copy()
        loop_env["BERYL_TIMEOUT_FIXTURE"] = str(loop_exe)
        evidence["runtime_timeout_fixture"] = {
            "kind": "real Beryl loop, precompiled and copied by trusted fixture tool",
            "program_sha256": hashlib.sha256(loop_exe.read_bytes()).hexdigest(),
            "copy_tool_sha256": hashlib.sha256(copy_tool.read_bytes()).hexdigest()}
        r = run([beryl, "run", "--clang", copy_tool, "--timeout-ms", "1500", loop], expected=None, extra_env=loop_env)
        assert r.returncode != 0 and "program timeout" in r.stderr
        passed("runtime timeout terminates operation and is not success")

        argv = [str(beryl), "run", "--timeout-ms", "30000", str(loop)]
        kwargs = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {"start_new_session": True}
        before = set((work / ".beryl-cache").glob("job-*"))
        proc = subprocess.Popen(argv, cwd=work, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True, encoding="utf-8", **kwargs)
        try:
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline:
                fresh = set((work / ".beryl-cache").glob("job-*")) - before
                if any((p / "run.stdout.log").exists() for p in fresh):
                    break
                if proc.poll() is not None:
                    raise AssertionError("cancel fixture exited before signal")
                time.sleep(0.02)
            else:
                raise AssertionError("cancel fixture did not reach execution")
            proc.send_signal(signal.CTRL_BREAK_EVENT if os.name == "nt" else signal.SIGINT)
            stdout, stderr = proc.communicate(timeout=10)
            evidence["commands"].append({"argv": argv, "exit_code": proc.returncode,
                "stdout": stdout, "stderr": stderr, "signal": "CTRL_BREAK" if os.name == "nt" else "SIGINT"})
            assert proc.returncode != 0 and "cancelled" in stderr
            result = json.loads(next(iter(fresh)).joinpath("result.json").read_text(encoding="utf-8"))
            assert result["run"]["status"] == "cancelled" and result["run"]["exit_code"] is None
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait()
        passed("external cancellation is recorded separately from exit and timeout")

        # New package creation is data-only and refuses to overwrite existing paths.
        run([beryl, "new", "new-package"])
        created = work / "new-package/src/main.be"
        original = created.read_bytes()
        assert run([beryl, "new", "new-package"], expected=None).returncode != 0
        assert created.read_bytes() == original
        assert run([beryl, "new", "bad & name"], expected=None).returncode != 0
        passed("package creation preserves existing files and rejects injected names")
        if source_hashes() != evidence["source_hashes"] or hashlib.sha256(beryl.read_bytes()).hexdigest() != evidence["beryl_sha256"]:
            raise RuntimeError("Source/compiler changed during driver verification; stale run")
        evidence["status"] = "passed"
    except Exception as exc:
        evidence["status"] = "failed"
        evidence["failure"] = repr(exc)
        raise
    finally:
        result_path = work / "results.json"
        result_path.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
        print(f"Evidence: {result_path}", flush=True)


if __name__ == "__main__":
    main()
