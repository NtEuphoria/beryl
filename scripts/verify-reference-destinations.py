#!/usr/bin/env python3
"""Verify common projected-destination safety before generation or execution."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--beryl", required=True, type=Path)
    parser.add_argument("--clang", required=True, type=Path)
    args = parser.parse_args()
    beryl, clang = args.beryl.resolve(), args.clang.resolve()
    work = Path(tempfile.mkdtemp(prefix="reference-destinations-", dir=ROOT / "build"))
    fixtures = ROOT / "tests/reference/destinations"
    tracked = [ROOT / "src/reference/admit.c", ROOT / "tests/unit/test_reference.c", ROOT / "tests/unit/test_destinations.c",
               ROOT / "src/sema/access.c", ROOT / "src/sema/access.h", ROOT / "src/sema/ownership.c", Path(__file__),
               *sorted(fixtures.glob("*.be")), *sorted((ROOT / "packages/sparkos/pid").glob("*.be"))]

    def hashes():
        return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in tracked}

    evidence = {"schema_version": 1, "status": "running", "commands": [], "checks": [],
                "compiler_sha256": hashlib.sha256(beryl.read_bytes()).hexdigest(), "source_hashes": hashes()}
    env = os.environ.copy()
    env["PATH"] = str(clang.parent) + os.pathsep + env.get("PATH", "")
    print(f"Artifacts: {work}", flush=True)

    def run(argv, expected=0):
        argv = [str(x) for x in argv]
        proc = subprocess.run(argv, cwd=work, env=env, capture_output=True, text=True,
                              encoding="utf-8", errors="strict", timeout=90)
        evidence["commands"].append({"argv": argv, "exit_code": proc.returncode,
                                     "stdout": proc.stdout, "stderr": proc.stderr})
        if expected is not None and proc.returncode != expected:
            raise AssertionError(f"exit {proc.returncode}, expected {expected}: {argv}\n{proc.stderr}")
        return proc

    def rejected(source):
        target = work / (source.stem + "-old-output.exe")
        target.write_bytes(b"previous artifact must survive semantic rejection")
        out_dir = work / (source.stem + "-enfusion")
        out_dir.mkdir()
        sentinel = out_dir / "previous.c"
        sentinel.write_bytes(b"previous generated source")
        expected = {str(target): target.read_bytes(), str(sentinel): sentinel.read_bytes()}
        commands = [
            ["check", source], ["check", "--format", "json", source],
            ["check", "-t", "enfusion", source], ["emit-c", "--tests", source],
            ["build", "--clang", clang, "-o", target, source],
            ["run", "--clang", clang, "-o", target, source],
            ["build", "-t", "enfusion", "--out-dir", out_dir, source],
            ["test", "--clang", clang, source], ["test", "--release", "--clang", clang, source],
            ["test", "--backend", "reference", source],
            ["test", "--backend", "differential", "--clang", clang, source],
        ]
        for command in commands:
            previous = set(work.joinpath(".beryl-cache").rglob("*"))
            proc = run([beryl, *command], expected=None)
            assert proc.returncode != 0 and "BE0401" in proc.stdout + proc.stderr, (command, proc.stdout, proc.stderr)
            assert "projected assignment" in proc.stdout + proc.stderr
            assert set(work.joinpath(".beryl-cache").rglob("*")) == previous, "rejected source started a build/execution job"
            assert all(Path(path).read_bytes() == content for path, content in expected.items())
            assert list(out_dir.iterdir()) == [sentinel], "rejected source generated output"
            if command[0] == "emit-c":
                assert not proc.stdout, "rejected source emitted native C"
        return len(commands)

    def execution(paths, backend, expected_assertions):
        previous = set(work.joinpath(".beryl-cache").glob("job-*"))
        proc = run([beryl, "test", "--backend", backend, "--clang", clang, *paths], expected=None)
        fresh = set(work.joinpath(".beryl-cache").glob("job-*")) - previous
        assert len(fresh) == 1, (fresh, proc.stderr)
        result = json.loads(fresh.pop().joinpath("result.json").read_text(encoding="utf-8"))
        assert proc.returncode == 0 and result["status"] == "success", (result, proc.stderr)
        assert result["assertions"] == expected_assertions, result
        if backend == "differential":
            assert result["compared"] and result["native_status"] == "exited", result
        return result

    try:
        expected_fixtures = {"array.be", "compound.be", "dynamic.be", "method.be", "nested.be",
                             "replacement.be", "safe.be", "set.be", "skipped.be", "target_index.be",
                             "default_call.be", "nested_call.be", "unreachable.be", "shared_list.be", "sink.be"}
        selected = sorted(fixtures.glob("*.be"))
        assert {p.name for p in selected} == expected_fixtures, "missing or unexpected destination fixtures"
        pid = ROOT / "packages/sparkos/pid"
        assert all((pid / name).is_file() for name in ("pid.be", "pid_test.be")), "missing PID implementation or tests"
        evidence["expected_fixtures"] = sorted(expected_fixtures)
        evidence["executed_fixtures"] = []
        for source in selected:
            if source.name == "safe.be":
                for backend in ("reference", "differential"):
                    execution([source], backend, expected_assertions=8)
                evidence["checks"].append("disjoint fields/indices, unrelated index effect, separate statements and scalar root remain supported")
            else:
                count = rejected(source)
                evidence["checks"].append(f"{source.name}: BE0401 in {count} command variants, before generation/execution")
            evidence["executed_fixtures"].append(source.name)

        for release in ([], ["--release"]):
            run([beryl, "test", "--clang", clang, *release, fixtures / "safe.be"])
        run([beryl, "check", "-t", "enfusion", fixtures / "safe.be"])
        (work / "safe-enfusion").mkdir()
        run([beryl, "build", "-t", "enfusion", "--out-dir", work / "safe-enfusion", fixtures / "safe.be"])
        evidence["checks"].append("safe fixture: native O0/O2 and Enfusion checking/generation pass")

        for backend in ("reference", "differential"):
            result = execution([pid / "pid.be", pid / "pid_test.be"], backend, expected_assertions=2206)
            assert result["tests"] == 8, result
        evidence["checks"].append("full unchanged PID: 8 tests / 2206 assertions through reference and differential")
        evidence["source_hashes_after"] = hashes()
        assert evidence["source_hashes_after"] == evidence["source_hashes"], "input changed during verification"
        evidence["compiler_sha256_after"] = hashlib.sha256(beryl.read_bytes()).hexdigest()
        assert evidence["compiler_sha256_after"] == evidence["compiler_sha256"], "compiler changed during verification"
        assert evidence["executed_fixtures"] == evidence["expected_fixtures"], "incomplete fixture execution"
        evidence["status"] = "success"
    except Exception as exc:
        evidence["status"] = "failure"
        evidence["failure"] = str(exc)
        raise
    finally:
        work.joinpath("results.json").write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(f"passed {len(evidence['checks'])} destination-admission checks", flush=True)


if __name__ == "__main__":
    main()
