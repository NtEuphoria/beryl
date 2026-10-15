#!/usr/bin/env python3
"""Verify bounded captured-call admission and independent plain-value repairs.

No engine execution, installation, or production IR release. Rejected programs
must fail in the frontend before creating jobs or replacing previous output.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests/reference/call-captures"
REJECTED = (
    "array_element", "direct_sink", "loop_mutation", "method_inout",
    "method_receiver", "nested_block", "nested_mutation", "nested_set",
    "nested_sink", "projected_array", "projected_inout", "projected_record",
    "projected_set", "selection_index", "short_circuit",
)
REJECTION_ROUTES = (
    "check-native", "check-native-json", "check-enfusion", "check-enfusion-json",
    "emit-c", "build-ast", "run-ast", "build-enfusion", "test-native-O0",
    "test-native-O2", "test-reference-ast", "test-differential-ast-O0",
    "test-differential-ast-O2", "test-differential-ir-O0", "test-differential-ir-O2",
)
# Expected values and complete stdout are independent, fixed analytical oracles.
# Only snapshot selects the separately admitted experimental IR test path.
SAFE = {
    "defaults": {"assertions": 2, "output": "77\n77\n1\n1\n", "ir": False},
    "disjoint": {"assertions": 8, "output": "1\n11\n11\n", "ir": False},
    "scalar": {"assertions": 3, "output": "8\n", "ir": False},
    "sink_temporary": {"assertions": 3, "output": "8\n4\n", "ir": False},
    "snapshot": {"assertions": 6, "output": "1\n1\n", "ir": True},
}


def case_inventory():
    cases = [f"reject:{name}:{route}" for name in REJECTED for route in REJECTION_ROUTES]
    for name, oracle in SAFE.items():
        cases.append(f"safe:{name}:reference:ast:O0")
        for release in (False, True):
            cases.append(f"safe:{name}:differential:ast:O{2 if release else 0}")
            if oracle["ir"]:
                cases.append(f"safe:{name}:differential:ir:O{2 if release else 0}")
    return cases


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--beryl", required=True, type=Path)
    parser.add_argument("--clang", required=True, type=Path)
    args = parser.parse_args()
    beryl, clang = args.beryl.resolve(strict=True), args.clang.resolve(strict=True)
    require(beryl.is_file() and clang.is_file(), "compiler paths must name regular files")
    work = Path(tempfile.mkdtemp(prefix="call captures & spaces-", dir=ROOT / "build"))
    env = os.environ.copy()
    env["PATH"] = str(clang.parent) + os.pathsep + env.get("PATH", "")
    env["BERYL_CLANG"] = str(clang)
    expected_fixtures = sorted(name + ".be" for name in (*REJECTED, *SAFE))
    tracked = [Path(__file__).resolve(), beryl, clang,
               *sorted(path for path in (ROOT / "src").rglob("*") if path.is_file()),
               *sorted(path for path in (ROOT / "runtime").rglob("*") if path.is_file()),
               *sorted(FIXTURES.glob("*.be"))]

    def identities():
        return {str(path): sha(path) for path in tracked}

    record = {
        "schema_version": 1, "operation": "verify_call_captures", "status": "running",
        "compiler_path": str(beryl), "compiler_sha256": sha(beryl),
        "clang_path": str(clang), "clang_sha256": sha(clang),
        "inputs": identities(), "expected_fixtures": expected_fixtures,
        "expected_cases": case_inventory(), "completed_cases": [], "commands": [], "checks": [],
        "executions": [], "engine_execution": "not_run", "installation": "not_run",
        "verification_scope": "bounded frontend rejection and plain-value execution; no complete ownership/effects claim",
    }
    print(f"Call-capture artifacts: {work}", flush=True)

    def run(case, argv, expected=0):
        argv = list(map(str, argv))
        position = len(record["commands"])
        require(position < len(record["expected_cases"]) and
                record["expected_cases"][position] == case, f"unexpected case at {position}: {case}")
        try:
            proc = subprocess.run(argv, cwd=work, env=env, capture_output=True, timeout=120)
        except (OSError, subprocess.TimeoutExpired) as error:
            record["commands"].append({"case": case, "argv": argv,
                                       "harness_failure": type(error).__name__, "detail": str(error)})
            raise
        entry = {"case": case, "argv": argv, "exit_code": proc.returncode,
                 "stdout": proc.stdout.decode("utf-8", errors="strict"),
                 "stderr": proc.stderr.decode("utf-8", errors="strict")}
        record["commands"].append(entry)
        require(expected is None or proc.returncode == expected, entry)
        return proc, entry

    def cache_state():
        cache = work / ".beryl-cache"
        if not cache.exists():
            return None
        return {str(path.relative_to(cache)): "directory" if path.is_dir() else sha(path)
                for path in sorted(cache.rglob("*"))}

    def complete(case):
        require(case not in record["completed_cases"], f"duplicate completion: {case}")
        record["completed_cases"].append(case)

    def rejection(name):
        source = FIXTURES / (name + ".be")
        previous_output = work / (name + "-previous.exe")
        previous_output.write_bytes(b"prior executable must survive frontend rejection\n")
        output_dir = work / (name + "-enfusion")
        output_dir.mkdir()
        previous_source = output_dir / "previous.c"
        previous_source.write_bytes(b"prior generated source must survive frontend rejection\n")
        sentinels = {previous_output: previous_output.read_bytes(),
                     previous_source: previous_source.read_bytes()}
        routes = [
            ("check-native", ["check", source]),
            ("check-native-json", ["check", "--format", "json", source]),
            ("check-enfusion", ["check", "-t", "enfusion", source]),
            ("check-enfusion-json", ["check", "-t", "enfusion", "--format", "json", source]),
            ("emit-c", ["emit-c", "--tests", source]),
            ("build-ast", ["build", "--lowering", "ast", "--clang", clang, "-o", previous_output, source]),
            ("run-ast", ["run", "--lowering", "ast", "--clang", clang, "-o", previous_output, source]),
            ("build-enfusion", ["build", "-t", "enfusion", "--out-dir", output_dir, source]),
            ("test-native-O0", ["test", "--backend", "native", "--lowering", "ast", "--clang", clang, source]),
            ("test-native-O2", ["test", "--backend", "native", "--lowering", "ast", "--release", "--clang", clang, source]),
            ("test-reference-ast", ["test", "--backend", "reference", "--lowering", "ast", source]),
        ]
        for lowering in ("ast", "ir"):
            for release in (False, True):
                routes.append((f"test-differential-{lowering}-O{2 if release else 0}",
                               ["test", "--backend", "differential", "--lowering", lowering,
                                *(["--release"] if release else []), "--clang", clang, source]))
        require(tuple(route for route, _ in routes) == REJECTION_ROUTES,
                "rejection command inventory differs from predeclared cases")
        for route, flags in routes:
            case = f"reject:{name}:{route}"
            before = cache_state()
            proc, entry = run(case, [beryl, *flags], expected=None)
            rendered = entry["stdout"] + entry["stderr"]
            require(proc.returncode != 0 and "BE0401" in rendered, entry)
            require("captured call argument" in rendered and "separate binding" in rendered, entry)
            require(cache_state() == before, f"{case}: rejected source created or changed a job")
            require(all(path.read_bytes() == content for path, content in sentinels.items()),
                    f"{case}: rejected source replaced previous output")
            require(set(output_dir.iterdir()) == {previous_source}, f"{case}: rejected source generated files")
            if route == "emit-c":
                require(proc.stdout == b"", f"{case}: rejected source emitted native C")
            if route.endswith("-json"):
                payload = json.loads(proc.stdout)
                require(payload["status"] == "failure", payload)
                require(payload["compiler_fingerprint"] == record["compiler_sha256"], payload)
                require(any(item["code"] == "BE0401" for item in payload["diagnostics"]), payload)
            complete(case)
        record["checks"].append(f"{name}: BE0401 in {len(routes)} supported routes before jobs, generation or execution; prior outputs preserved")

    def execution(name, backend, lowering, release=False):
        source = FIXTURES / (name + ".be")
        oracle = SAFE[name]
        case = f"safe:{name}:{backend}:{lowering}:O{2 if release else 0}"
        before = set((work / ".beryl-cache").glob("job-*"))
        proc, entry = run(case, [beryl, "test", "--backend", backend, "--lowering", lowering,
                                 *(["--release"] if release else []), "--clang", clang, source])
        fresh = set((work / ".beryl-cache").glob("job-*")) - before
        require(len(fresh) == 1, f"{case}: expected exactly one root job, found {fresh}")
        job = fresh.pop()
        receipt_path = job / "result.json"
        result = json.loads(receipt_path.read_bytes())
        require(result["status"] == "success" and result["reference_status"] == "success", result)
        require(result["tests"] == 1 and result["failed_tests"] == 0, result)
        require(result["assertions"] == oracle["assertions"], result)
        require(result["compiler_fingerprint"] == record["compiler_sha256"], result)
        require(result["requested_lowering"] == lowering and result["selected_lowering"] == lowering, result)
        require(result["sources"] == [{"path": str(source), "sha256": sha(source)}], result)
        expected_output = oracle["output"] + f"ok  1 test, {oracle['assertions']} assertions\n"
        require(proc.stdout == expected_output.encode("utf-8"), entry)
        events_path = job / "reference.events.jsonl"
        events = [json.loads(line) for line in events_path.read_bytes().splitlines()]
        require(events and events[0]["event"] == "test_begin" and events[-1]["event"] == "test_end", events)
        require([event["seq"] for event in events] == list(range(len(events))), "incomplete or unordered event sequence")
        require(sum(event["event"] == "assert" for event in events) == oracle["assertions"], events)
        require(result["reference_events_sha256"] == sha(events_path), result)
        retained = {"case": case, "receipt": str(receipt_path), "receipt_sha256": sha(receipt_path),
                    "source_sha256": sha(source), "events_sha256": sha(events_path),
                    "tests": result["tests"], "assertions": result["assertions"],
                    "selected_lowering": result["selected_lowering"]}
        if backend == "differential":
            require(result["compared"] is True and result["native_status"] == "exited" and
                    result["native_exit_code"] == 0, result)
            require(result["native_job"] and result["native_executable_sha256"], result)
            native_job = Path(result["native_job"])
            if not native_job.is_absolute():
                native_job = work / native_job
            generated = native_job / "out.c"
            require(generated.is_file(), f"{case}: generated candidate missing")
            native_executable = native_job / "program.exe"
            require(native_executable.is_file() and
                    sha(native_executable) == result["native_executable_sha256"],
                    f"{case}: executed native candidate identity missing or mismatched")
            retained["generated_c_sha256"] = sha(generated)
            retained["native_executable"] = str(native_executable)
            retained["native_executable_sha256"] = sha(native_executable)
            if lowering == "ir":
                profile = result["ir_test_profile"]
                require(profile["admitted"] is True and profile["production_backend"] is False, profile)
                require(profile["generated_c_sha256"] == retained["generated_c_sha256"], profile)
        else:
            require(result["compared"] is False and result["native_status"] is None and
                    result["native_job"] is None, result)
        record["executions"].append(retained)
        complete(case)

    try:
        require(sorted(path.name for path in FIXTURES.glob("*.be")) == expected_fixtures,
                "missing or unexpected call-capture fixtures")
        # Run all negative cases before any positive job exists so admission
        # checks can certify an empty cache remains absent.
        for name in REJECTED:
            rejection(name)
        for name, oracle in SAFE.items():
            execution(name, "reference", "ast")
            for release in (False, True):
                execution(name, "differential", "ast", release)
                if oracle["ir"]:
                    execution(name, "differential", "ir", release)
            record["checks"].append(f"{name}: complete analytical outputs/assertions, reference and AST native O0/O2" +
                                     ("; admitted snapshot also explicit experimental IR O0/O2" if oracle["ir"] else ""))
        record["inputs_after"] = identities()
        require(record["inputs_after"] == record["inputs"], "compiler, tool or source changed during verification")
        require(record["expected_cases"] == record["completed_cases"], "incomplete or out-of-order case receipt")
        require(len(record["expected_cases"]) == len(REJECTED) * 15 + len(SAFE) * 3 + 2,
                "unexpected command inventory")
        record["status"] = "success"
    except BaseException as error:
        record["status"] = "cancelled" if isinstance(error, KeyboardInterrupt) else "failure"
        record["failure"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        receipt = work / "results.json"
        receipt.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        print(f"Receipt: {receipt}", flush=True)
    print(f"passed {len(record['checks'])} call-capture groups / {len(record['completed_cases'])} cases", flush=True)


if __name__ == "__main__":
    main()
