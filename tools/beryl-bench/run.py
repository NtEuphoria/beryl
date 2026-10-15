#!/usr/bin/env python3
"""Native performance collector with bounded process capture.

Every binary is built, then its stdout and exit status are checked against the
workload golden before any timing receipt is written. A mismatch stops the run.
Complete collection is currently unavailable: mandatory resource observations
are not implemented. Synthetic evaluator-v1 receipt compatibility remains tested.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

import receipts as rec

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
WORKLOADS = HERE / "workloads"
EVALUATOR = ROOT / "tools" / "beryl-experiments" / "evaluate.py"
sys.path.insert(0, str(ROOT / "tools" / "beryl-mod"))
from process_job import ProcessJob

OUTPUT_LIMIT = 4 * 1024 * 1024  # separately bounded stdout and stderr
CLANG_FLAGS = [
    "-std=c11", "-O2", "-DNDEBUG",
    "-fno-unwind-tables", "-fno-asynchronous-unwind-tables",
    "-ffp-contract=off", "-fno-fast-math",
]


class CollectorError(RuntimeError):
    def __init__(self, message: str, *, status: str = "failure"):
        super().__init__(message)
        self.status = status


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def exe_name(path: Path) -> Path:
    return path.with_suffix(".exe") if os.name == "nt" else path


def load_workload(name: str) -> tuple[Path, dict]:
    if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", name):
        raise CollectorError(f"invalid workload id: {name}")
    folder = WORKLOADS / name
    spec = json.loads((folder / "workload.json").read_text(encoding="utf-8"))
    if spec.get("id") != name:
        raise CollectorError(f"{folder}/workload.json id must equal directory name")
    return folder, spec


def query_peak(proc: subprocess.Popen) -> int | None:
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        class Counters(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        GetProcessMemoryInfo = ctypes.windll.psapi.GetProcessMemoryInfo
        GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
        GetProcessMemoryInfo.restype = wintypes.BOOL
        info = Counters(); info.cb = ctypes.sizeof(Counters)
        handle = int(getattr(proc, "_handle", 0) or 0)
        if handle and GetProcessMemoryInfo(handle, ctypes.byref(info), info.cb):
            return int(info.PeakWorkingSetSize)
        return None
    # Popen/ProcessJob owns reaping. RUSAGE_CHILDREN is cumulative and cannot
    # establish this process's peak; do not relabel it or substitute zero.
    return None


def run_binary(argv, *, timeout: float, cwd: Path | None = None,
               cancel: threading.Event | None = None,
               output_limit: int = OUTPUT_LIMIT) -> dict:
    """Bounded captures and a deadline cover this exact owned process tree.

    UTC timestamps identify the receipt window. Only the monotonic clock pays
    duration. Backward timestamps fail; shorter UTC windows stay explicit and
    cannot be used for evaluator-v1 measurements. Timestamps are never extended.
    """
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or not 0 < timeout <= 3600:
        raise CollectorError("timeout must be finite and within (0, 3600] seconds", status="invalid_input")
    if type(output_limit) is not int or not 1 <= output_limit <= 64 * 1024 * 1024:
        raise CollectorError("output limit must be 1..67108864 bytes per stream", status="invalid_input")
    args = [str(x) for x in argv]
    if not args:
        raise CollectorError("process argv must not be empty", status="invalid_input")
    if cancel is not None and cancel.is_set():
        raise CollectorError("process cancelled before startup", status="cancelled")
    started = time.time_ns()
    monotonic_start = time.monotonic_ns()
    deadline = monotonic_start + int(timeout * 1_000_000_000)
    captured = {"stdout": bytearray(), "stderr": bytearray()}
    overflow = threading.Event()
    capture_failure = threading.Event()
    capture_progress = threading.Event()
    readers = []
    proc = None
    peak = None

    def read_stream(name, stream):
        try:
            while True:
                chunk = os.read(stream.fileno(), 65536)
                if not chunk:
                    break
                available = output_limit - len(captured[name])
                captured[name].extend(chunk[:available])
                if len(chunk) > available:
                    overflow.set()
                    break
        except OSError:
            capture_failure.set()
        finally:
            stream.close()
            capture_progress.set()

    try:
        with ProcessJob() as job:
            try:
                try:
                    proc = subprocess.Popen(
                        args, cwd=cwd, stdin=subprocess.DEVNULL,
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                        bufsize=0, creationflags=job.flags,
                        start_new_session=os.name != "nt",
                    )
                    job.attach(proc)
                except (OSError, ValueError) as exc:
                    raise CollectorError(f"process startup failed: {args[0]}: {exc}", status="startup_failure") from exc
                for name in captured:
                    reader = threading.Thread(target=read_stream, args=(name, getattr(proc, name)), daemon=True)
                    readers.append(reader)
                    reader.start()
                while True:
                    if cancel is not None and cancel.is_set():
                        raise CollectorError(f"process cancelled: {args[0]}", status="cancelled")
                    if overflow.is_set():
                        raise CollectorError(f"process output exceeds {output_limit} bytes per stream: {args[0]}", status="output_limit")
                    if capture_failure.is_set():
                        raise CollectorError(f"process capture failed: {args[0]}", status="capture_failure")
                    if time.monotonic_ns() >= deadline:
                        raise CollectorError(f"process timed out after {timeout} seconds: {args[0]}", status="timeout")
                    if proc.poll() is not None and not any(reader.is_alive() for reader in readers):
                        break
                    remaining = (deadline - time.monotonic_ns()) / 1_000_000_000
                    if proc.poll() is None:
                        try:
                            proc.wait(timeout=max(0, min(0.02, remaining)))
                        except subprocess.TimeoutExpired:
                            pass
                    else:
                        capture_progress.wait(timeout=max(0, min(0.02, remaining)))
                        capture_progress.clear()
                peak = query_peak(proc)
            finally:
                # Close our tree even when its direct child returned while a
                # descendant still retains capture handles. Never match names.
                cleanup_error = None
                if proc is not None:
                    try:
                        job.stop(proc)
                    except (OSError, subprocess.TimeoutExpired) as exc:
                        cleanup_error = exc
                for reader in readers:
                    reader.join(timeout=2)
                if any(reader.is_alive() for reader in readers):
                    raise CollectorError("owned process capture did not close after cleanup", status="cleanup_failure")
                if proc is not None:
                    for name in captured:
                        stream = getattr(proc, name)
                        if stream is not None and not stream.closed:
                            stream.close()
                if cleanup_error is not None:
                    raise CollectorError(f"owned process cleanup failed: {cleanup_error}", status="cleanup_failure") from cleanup_error
    except KeyboardInterrupt as exc:
        raise CollectorError(f"process cancelled: {args[0]}", status="cancelled") from exc
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise CollectorError(f"owned process cleanup/startup failed: {args[0]}: {exc}", status="cleanup_failure" if proc is not None else "startup_failure") from exc
    # Workers can publish their terminal flag between the loop's flag checks
    # and its child/readers-complete branch. Joined workers establish the final
    # capture outcome; a truncated capture must never become an exited result.
    if cancel is not None and cancel.is_set():
        raise CollectorError(f"process cancelled: {args[0]}", status="cancelled")
    if overflow.is_set():
        raise CollectorError(f"process output exceeds {output_limit} bytes per stream: {args[0]}", status="output_limit")
    if capture_failure.is_set():
        raise CollectorError(f"process capture failed: {args[0]}", status="capture_failure")
    monotonic_end = time.monotonic_ns()
    if monotonic_end >= deadline:
        raise CollectorError(f"process/capture/cleanup timed out after {timeout} seconds: {args[0]}", status="timeout")
    ended = time.time_ns()
    paid = monotonic_end - monotonic_start
    if paid <= 0 or ended <= started:
        raise CollectorError("invalid observed monotonic duration or backwards UTC window", status="clock_failure")
    return {
        "status": "exited",
        "argv": args,
        "exit_code": proc.returncode,
        "stdout": bytes(captured["stdout"]),
        "stderr": bytes(captured["stderr"]),
        "started": started,
        "ended": ended,
        "paid": paid,
        "duration_clock": "monotonic",
        "clock_window": {"status": "compatible" if ended - started >= paid else "unavailable",
                         "reason": None if ended - started >= paid else "raw UTC interval is shorter than the monotonic paid duration"},
        "peak_bytes": peak,
        "memory_capability": {"status": "measured" if peak is not None else "unavailable",
                              "scope": "direct_child_peak_working_set",
                              "retained_bytes": "unavailable", "allocations": "unavailable"},
    }


def check_golden(result: dict, expected: bytes, label: str) -> None:
    if result["exit_code"] != 0:
        raise CollectorError(
            f"{label} exited {result['exit_code']}\n{result['stderr'].decode('utf-8', 'replace')}", status="program_failure"
        )
    actual = result["stdout"].replace(b"\r\n", b"\n")
    want = expected.replace(b"\r\n", b"\n")
    if actual != want:
        raise CollectorError(
            f"{label} stdout mismatch\n--- expected ---\n{want!r}\n--- actual ---\n{actual!r}", status="semantic_mismatch"
        )


def timed_compile(argv, *, timeout: int) -> tuple[int, subprocess.CompletedProcess]:
    result = run_binary(argv, timeout=timeout, cwd=ROOT)
    proc = subprocess.CompletedProcess(result["argv"], result["exit_code"], result["stdout"], result["stderr"])
    if proc.returncode != 0:
        raise CollectorError(
            f"compile failed: {argv}\n{proc.stdout.decode('utf-8', 'replace')}\n{proc.stderr.decode('utf-8', 'replace')}", status="program_failure"
        )
    return result["paid"], proc


def environment_blob() -> bytes:
    return (
        f"os={platform.system()}\n"
        f"release={platform.release()}\n"
        f"machine={platform.machine()}\n"
        f"processor={platform.processor()}\n"
        f"python={sys.version.split()[0]}\n"
    ).encode()


def workload_blob(folder: Path) -> bytes:
    parts = []
    for path in sorted(p for p in folder.rglob("*") if p.is_file()):
        rel = path.relative_to(folder).as_posix()
        parts.append(rel.encode() + b"\n" + path.read_bytes() + b"\n")
    return b"".join(parts)


def build_artifacts(folder: Path, spec: dict, job: Path, args) -> dict:
    clang = shutil.which(args.clang) or args.clang
    beryl = Path(args.beryl)
    if not Path(clang).exists() and not shutil.which(args.clang):
        raise CollectorError(f"clang not found: {args.clang}")
    if not beryl.is_file():
        raise CollectorError(f"beryl compiler not found: {beryl}")
    name = spec["id"]
    expected = (folder / "expected.txt").read_bytes()
    c_src = folder / "baseline.c"
    c_exe = exe_name(job / "baseline")
    c_build, _ = timed_compile([clang, *CLANG_FLAGS, c_src, "-o", c_exe], timeout=args.timeout)
    be_exe = exe_name(job / "beryl-candidate")
    be_build, _ = timed_compile(
        [beryl, "build", "--release", "-o", be_exe, folder / "src" / "main.be"],
        timeout=args.timeout,
    )
    check_ns, _ = timed_compile([beryl, "check", folder / "src" / "main.be"], timeout=args.timeout)
    syntax_ns, _ = timed_compile([clang, "-fsyntax-only", "-std=c11", c_src], timeout=args.timeout)
    artifacts = {
        "c": {"path": c_exe, "build_ns": c_build, "edit_check_ns": syntax_ns, "label": "c-baseline"},
        "beryl": {"path": be_exe, "build_ns": be_build, "edit_check_ns": check_ns, "label": "beryl"},
    }
    for key, art in artifacts.items():
        probe = run_binary([art["path"]], timeout=args.timeout)
        check_golden(probe, expected, art["label"])
        art["text_bytes"] = art["path"].stat().st_size
    return artifacts, expected


def paid_costs(compute: int) -> dict:
    costs = {key: 0 for key in rec.COSTS}
    costs["compute"] = compute
    return costs


def resources_of(art: dict, peak: int | None) -> dict:
    # Evaluator-v1 requires numeric resource observations. The current runner
    # has no retained-storage/allocation instrumentation or text-section parser.
    # File size is not text size, and peak RSS is not retained storage.
    raise CollectorError("complete resource evidence unavailable: retained storage, allocation counts and text-section size are unmeasured"
                         + ("; direct-child peak memory unavailable" if peak is None else ""), status="unavailable")


def write_identities(job: Path, artifacts: dict, folder: Path, spec: dict, args) -> dict:
    beryl = Path(args.beryl)
    clang = shutil.which(args.clang) or args.clang
    clang_query = run_binary([clang, "--version"], timeout=args.timeout)
    if clang_query["exit_code"] != 0:
        raise CollectorError("clang version query failed", status="program_failure")
    clang_ver = clang_query["stdout"]
    refs = {
        "baseline": rec.write_bytes(job, "identities/baseline.bin", artifacts["c"]["path"].read_bytes()),
        "compiler": rec.write_bytes(job, "identities/compiler.bin", beryl.read_bytes()),
        "toolchain": rec.write_bytes(job, "identities/toolchain.txt", clang_ver),
        "environment": rec.write_bytes(job, "identities/environment.txt", environment_blob()),
        "workload": rec.write_bytes(job, "identities/workload.bin", workload_blob(folder)),
        "semantic_contract": rec.write_text(
            job, "identities/semantic_contract.txt",
            "Admitted kernel: complete stdout must match expected.txt; exit 0; "
            "checked i32/f32 as specified by the source; no omitted loops.\n"
            + (folder / "expected.txt").read_text(encoding="utf-8"),
        ),
    }
    return refs


def collect_blocks(job: Path, prefix: str, a_art: dict, b_art: dict, pairs: int,
                   fingerprints: dict, a_hash: str, b_hash: str, semantic: dict,
                   evidence: dict, timeout: int) -> list:
    blocks = []
    for index in range(pairs):
        unit = f"{prefix}:{index}"
        order = "a" if index % 2 == 0 else "b"
        block = {"unit_id": unit, "first": order}
        sequence = (("a", a_art, a_hash), ("b", b_art, b_hash))
        if order == "b":
            sequence = sequence[::-1]
        for side, art, artifact_hash in sequence:
            result = run_binary([art["path"]], timeout=timeout)
            check_golden(result, semantic["_expected"], f"{unit}:{side}")
            if result["clock_window"]["status"] != "compatible":
                raise CollectorError("actual UTC window cannot represent the monotonic measurement in evaluator-v1; no receipt written", status="clock_failure")
            fps = {key: fingerprints[key]["sha256"] for key in rec.IDENTITIES if key != "baseline"}
            fps["artifact"] = artifact_hash
            run = rec.measurement(
                measurement_id=f"{unit}:{side}",
                unit_id=unit,
                session_id=f"{unit}:session:{side}",
                started=result["started"],
                ended=result["ended"],
                fingerprints=fps,
                paid=paid_costs(result["paid"]),
                resources=resources_of(art, result["peak_bytes"]),
                semantic={
                    "status": "complete",
                    "expected_cases": 1,
                    "completed_cases": 1,
                    "events": semantic["events"],
                    "stdout": semantic["stdout"],
                    "state": semantic["state"],
                },
            )
            block[side] = rec.write_json(job, f"runs/{prefix}-{index}-{side}.json", run)
        block["independence"] = rec.write_json(
            job, f"runs/{prefix}-{index}-independence.json",
            rec.independence(unit_id=unit, measurement_ids=[f"{unit}:a", f"{unit}:b"], evidence=evidence),
        )
        blocks.append(block)
    return blocks


def invoke_evaluator(operation: str, source: Path, dest: Path) -> dict:
    result = run_binary(
        [sys.executable, str(EVALUATOR), operation, "--input", str(source), "--output", str(dest)],
        cwd=ROOT, timeout=60,
    )
    proc = subprocess.CompletedProcess(result["argv"], result["exit_code"], result["stdout"], result["stderr"])
    if proc.returncode not in (0, 2):
        raise CollectorError(f"evaluator crashed: {proc.stderr.decode('utf-8', 'replace')}")
    payload = json.loads(dest.read_text(encoding="utf-8") if dest.is_file() else proc.stdout.decode())
    if proc.returncode == 2:
        raise CollectorError(f"evaluator rejected evidence: {payload}")
    return payload


def collect(args) -> dict:
    folder, spec = load_workload(args.workload)
    # Fail before builds, measurements or files when the evaluator's mandatory
    # resource observations are unavailable. A partial timing is no release gate.
    resources_of({}, None)
    job = Path(args.out).resolve()
    job.mkdir(parents=True, exist_ok=True)
    artifacts, expected = build_artifacts(folder, spec, job, args)
    against = args.against
    if against != "c":
        raise CollectorError("only --against c is implemented in this collector revision")
    identities = write_identities(job, artifacts, folder, spec, args)
    evidence = rec.write_text(
        job, "independence-method.txt",
        "Each measurement is a new OS process. Sessions are not reused. "
        "Process captures are bounded and paid duration uses a monotonic clock. "
        "Retained-storage/allocation/text-section evidence is unavailable; complete resource receipts are blocked.\n",
    )
    semantic_files = {
        "events": rec.write_bytes(job, "semantic/events.raw", b""),
        "stdout": rec.write_bytes(job, "semantic/stdout.raw", expected.replace(b"\r\n", b"\n")),
        "state": rec.write_bytes(job, "semantic/state.raw", expected.replace(b"\r\n", b"\n")),
        "_expected": expected.replace(b"\r\n", b"\n"),
    }
    baseline_hash = identities["baseline"]["sha256"]
    candidate_ref = rec.write_bytes(job, "identities/candidate.bin", artifacts["beryl"]["path"].read_bytes())
    candidate_hash = candidate_ref["sha256"]
    population = (
        f"Independent OS processes of workload {spec['id']} on this host; "
        "pair sides are complete program executions with validated stdout."
    )[:4096]
    pilot_blocks = collect_blocks(
        job, "pilot", artifacts["c"], artifacts["c"], args.pairs,
        identities, baseline_hash, baseline_hash, semantic_files, evidence, args.timeout,
    )
    pilot_doc = rec.pilot(
        experiment_id=spec["id"], population=population,
        fingerprints=identities, budgets=spec["budgets"], blocks=pilot_blocks,
    )
    rec.write_json(job, "pilot.json", pilot_doc)
    freeze = invoke_evaluator("freeze", job / "pilot.json", job / "freeze.json")
    selected = time.time_ns()
    if selected <= freeze["frozen_utc_ns"]:
        raise CollectorError("selection timestamp does not follow the actual freeze", status="clock_failure")
    selection_ref = rec.write_json(
        job, "selection.json",
        rec.selection(candidate_sha256=candidate_hash, selected_utc_ns=selected, evidence=evidence),
    )
    eval_blocks = collect_blocks(
        job, "candidate", artifacts["c"], artifacts["beryl"], args.pairs,
        identities, baseline_hash, candidate_hash, semantic_files, evidence, args.timeout,
    )
    rec.write_json(
        job, "request.json",
        rec.evaluation(
            freeze={"path": "freeze.json", "sha256": sha256_file(job / "freeze.json")},
            candidate=candidate_ref, selection_ref=selection_ref, blocks=eval_blocks,
        ),
    )
    result = invoke_evaluator("evaluate", job / "request.json", job / "result.json")
    summary = {
        "workload": spec["id"],
        "out": str(job),
        "decision": result.get("decision"),
        "threshold": result.get("threshold"),
        "median": result.get("median"),
        "automatic_adoption": False,
        "reject_check": reject_check(job, expected, args.timeout),
    }
    rec.write_json(job, "summary.json", summary)
    return summary


def reject_check(job: Path, expected: bytes, timeout: int) -> str:
    """A binary that prints the wrong result must not produce a complete measurement."""
    src = job / "wrong.c"
    src.write_text("int main(void) { return 0; }\n", encoding="utf-8")
    exe = exe_name(job / "wrong")
    clang = shutil.which("clang") or "clang"
    timed_compile([clang, *CLANG_FLAGS, src, "-o", exe], timeout=timeout)
    result = run_binary([exe], timeout=timeout)
    try:
        check_golden(result, expected, "deliberately-wrong-candidate")
    except CollectorError:
        return "stopped_before_receipt"
    raise CollectorError("reject-check: wrong stdout was accepted")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("collect", "list"))
    parser.add_argument("--workload", help="workload directory name under tools/beryl-bench/workloads")
    parser.add_argument("--beryl", default=str(ROOT / "build" / ("beryl.exe" if os.name == "nt" else "beryl")))
    parser.add_argument("--clang", default="clang")
    parser.add_argument("--against", default="c", choices=("c",))
    parser.add_argument("--pairs", type=int, default=30)
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("--out", default="")
    args = parser.parse_args()
    if args.command == "list":
        for path in sorted(WORKLOADS.iterdir()):
            if (path / "workload.json").is_file():
                print(path.name)
        return 0
    if not args.workload:
        raise SystemExit("collect requires --workload")
    if not (30 <= args.pairs <= 1024) or args.pairs % 2:
        raise SystemExit("--pairs must be an even integer from 30 through 1024")
    if not args.out:
        args.out = str(ROOT / "build" / f"bench-{args.workload}")
    summary = collect(args)
    sys.stdout.write(json.dumps(summary, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except CollectorError as error:
        sys.stderr.write(f"beryl-bench: status={error.status}; {error}\n")
        raise SystemExit(1)
