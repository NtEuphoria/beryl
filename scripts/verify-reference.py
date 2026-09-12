#!/usr/bin/env python3
"""Verify admitted reference/native semantics, negative outcomes and isolated mutants."""
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--beryl", required=True, type=Path)
    parser.add_argument("--clang", required=True, type=Path)
    args = parser.parse_args()
    beryl, clang = args.beryl.resolve(), args.clang.resolve()
    work = Path(tempfile.mkdtemp(prefix="reference-", dir=ROOT / "build"))
    env = os.environ.copy()
    env["PATH"] = str(clang.parent) + os.pathsep + env.get("PATH", "")
    def hashes():
        return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                for directory in ("src", "runtime", "tests", "scripts", "examples", "lib", "packages", "schemas", "tools")
                for p in sorted((ROOT / directory).rglob("*")) if p.is_file() and not {"__pycache__", ".beryl-mod", ".beryl-cache"}.intersection(p.parts)}
    evidence = {"schema_version": 1, "status": "running", "compiler_sha256": hashlib.sha256(beryl.read_bytes()).hexdigest(),
                "source_hashes": hashes(), "commands": [], "checks": []}
    print(f"Reference artifacts: {work}", flush=True)
    def run(argv, expected=0, timeout=30):
        argv = [str(x) for x in argv]
        proc = subprocess.run(argv, cwd=work, env=env, capture_output=True, text=True,
                              encoding="utf-8", errors="strict", timeout=timeout)
        evidence["commands"].append({"argv": argv, "exit_code": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr})
        if expected is not None and proc.returncode != expected:
            raise AssertionError(f"Exit {proc.returncode}, expected {expected}: {argv}\n{proc.stdout}\n{proc.stderr}")
        return proc
    def jobs():
        return set(work.joinpath(".beryl-cache").glob("job-*"))
    def execute(sources, *, backend="differential", expected_status="success", extra=()):
        previous = jobs()
        proc = run([beryl, "test", "--backend", backend, "--clang", clang, *extra, *sources], expected=None)
        fresh = jobs() - previous
        assert len(fresh) == 1, (fresh, proc.stderr)
        job = fresh.pop()
        result = json.loads(job.joinpath("result.json").read_text(encoding="utf-8"))
        assert result["reference_status"] == expected_status, (result, proc.stderr)
        if expected_status == "success":
            assert proc.returncode == 0 and result["status"] == "success", proc.stderr
            if backend == "differential":
                assert result["compared"] and result["native_status"] == "exited"
            events = [json.loads(line) for line in job.joinpath("reference.events.jsonl").read_text().splitlines()]
            assert events and [e["seq"] for e in events] == list(range(len(events)))
            assert sum(e["event"] == "test_begin" for e in events) == result["tests"]
            assert sum(e["event"] == "test_end" for e in events) == result["tests"]
        else:
            outer = expected_status if expected_status in ("unavailable", "timeout", "cancelled") else "failure"
            assert proc.returncode != 0 and result["status"] == outer and not result["compared"]
        return result, job
    def passed(name):
        evidence["checks"].append(name)
        print(f"passed {name}", flush=True)
    try:
        corpus = ROOT / "tests/reference/corpus.be"
        result, corpus_job = execute([corpus])
        assert (result["tests"], result["assertions"]) == (4, 19)
        output = corpus_job.joinpath("reference.stdout.log").read_text()
        assert "side:7\n" in output
        events = [json.loads(line) for line in corpus_job.joinpath("reference.events.jsonl").read_text().splitlines()]
        bits = [e["bits"] for e in events if e["event"] == "f32"]
        assert bits == [0, 0x80000000, 0x3DCCCCCD], bits
        passed("admitted corpus, exact float observations, access modes and ordered events")
        result, _ = execute([ROOT / "tests/reference/rounding.be"])
        assert (result["tests"], result["assertions"]) == (1, 1)
        formatted = work / "formatted-rounding.be"
        shutil.copyfile(ROOT / "tests/reference/rounding.be", formatted)
        run([beryl, "fmt", formatted])
        run([beryl, "fmt", "--check", formatted])
        execute([formatted])
        passed("independently calculated binary32 rounding survives formatting")
        for backend in ("reference", "differential"):
            result, _ = execute([ROOT / "examples/pid.be", ROOT / "examples/pid_test.be"], backend=backend)
            assert (result["tests"], result["assertions"]) == (4, 5)
        result, _ = execute(sorted(ROOT.joinpath("tests/modules").glob("*.be")))
        assert (result["tests"], result["assertions"]) == (4, 4)
        passed("shared PID and multi-module implementations execute through both paths")
        negatives = [
            ("unsupported", "var xs: List<i32>\nxs.push(1)", "unavailable", ()),
            ("assert", "assert(1 == 2)", "failure", ()),
            ("overflow", "var x = 2147483647\nx += 1", "trap", ()),
            ("division", "var zero = 0\nprintln(1 / zero)", "trap", ()),
            ("bounds", "let xs = [1]\nlet n = 1\nprintln(xs[n])", "trap", ()),
            ("steps", "while true {}", "budget_exhausted", ("--max-steps", "50")),
            ("memory", "let xs = [1, 2, 3, 4]\nassert(xs[0] == 1)", "budget_exhausted", ("--max-bytes", "128")),
            ("timeout", "while true {}", "timeout", ("--max-steps", "1000000000", "--max-bytes", "536870912", "--timeout-ms", "1")),
        ]
        for name, body, status, extra in negatives:
            source = work / (name + ".be")
            source.write_text('module t\ntest "negative" {\n' + body + '\n}\n', encoding="utf-8")
            execute([source], expected_status=status, extra=extra)
        empty = work / "empty.be"
        empty.write_text("module empty\nfn nothing() {}\n", encoding="utf-8")
        assert run([beryl, "test", "--backend", "reference", empty], expected=None).returncode != 0
        passed("unsupported, empty, failed, trapped and budget/timeout runs never pass")

        previous = jobs()
        argv = [str(beryl), "test", "--backend", "reference", "--max-steps", "1000000000",
                "--max-bytes", "536870912", str(work / "timeout.be")]
        flags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
        proc = subprocess.Popen(argv, cwd=work, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True, encoding="utf-8", creationflags=flags)
        try:
            deadline = time.monotonic() + 5
            fresh = set()
            while time.monotonic() < deadline:
                fresh = jobs() - previous
                if fresh and any(p.joinpath("reference.events.jsonl").exists() for p in fresh):
                    break
                if proc.poll() is not None:
                    raise AssertionError("reference cancellation fixture completed before signal")
                time.sleep(0.005)
            else:
                raise AssertionError("reference cancellation fixture did not start")
            proc.send_signal(signal.CTRL_BREAK_EVENT if os.name == "nt" else signal.SIGINT)
            stdout, stderr = proc.communicate(timeout=10)
            evidence["commands"].append({"argv": argv, "exit_code": proc.returncode, "stdout": stdout,
                                         "stderr": stderr, "external_cancellation": True})
            assert proc.returncode != 0
            result = json.loads(fresh.pop().joinpath("result.json").read_text(encoding="utf-8"))
            assert result["reference_status"] == "cancelled", result
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait()
        passed("external cancellation has a distinct incomplete status")

        # Mutants are isolated generated C files. Production compiler/source stays unchanged.
        native_job = Path(json.loads(corpus_job.joinpath("result.json").read_text())["native_job"])
        baseline = native_job.joinpath("out.c").read_text(encoding="utf-8")
        assert "be_add_i32" in baseline
        mutants = {"arithmetic": baseline.replace("be_add_i32", "be_sub_i32", 1)}
        lines = baseline.splitlines(keepends=True)
        calls = [i for i, line in enumerate(lines) if re.search(r"= be_i_reference_2ecorpus_2enext\(", line)]
        assert len(calls) >= 2, "ordered argument calls not found"
        assert " = &(" in lines[calls[0] - 1] and " = &(" in lines[calls[1] - 1]
        first_block = lines[calls[0] - 1:calls[0] + 1]
        second_block = lines[calls[1] - 1:calls[1] + 1]
        lines[calls[0] - 1:calls[0] + 1] = second_block
        lines[calls[1] - 1:calls[1] + 1] = first_block
        mutants["ordering"] = "".join(lines)
        pattern = r"(void be_i_reference_2ecorpus_2eP_2emark\([^;]*?\) \{)(.*?)(\n\})"
        found = re.search(pattern, baseline, re.S)
        assert found, "state-update fixture not found"
        body, changes = re.subn(r"\(\*_t\d+\) = [^;]+;", "(void)0;", found[2], count=1)
        assert changes == 1, "state write not found"
        mutants["state-update"] = baseline[:found.start(2)] + body + baseline[found.end(2):]
        for name, code in mutants.items():
            cfile = work / (name + ".c")
            binary = work / (name + (".exe" if os.name == "nt" else ""))
            cfile.write_text(code, encoding="utf-8", newline="\n")
            run([clang, "-std=c11", "-O2", "-ffp-contract=off", "-fno-fast-math", "-I", ROOT / "runtime",
                 cfile, ROOT / "runtime/beryl_rt.c", "-o", binary])
            rejected = run([binary], expected=None)
            assert rejected.returncode != 0, f"{name} mutant was not detected"
        passed("compiled arithmetic, ordering and missing-state-update mutants are detected")
        if hashes() != evidence["source_hashes"] or hashlib.sha256(beryl.read_bytes()).hexdigest() != evidence["compiler_sha256"]:
            raise AssertionError("Sources/compiler changed during reference validation")
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
