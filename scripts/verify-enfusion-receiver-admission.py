#!/usr/bin/env python3
"""Verify bounded Enfusion receiver admission; never run source programs or an engine."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "beryl-mod"))
from process_job import ProcessJob

OUTPUT_LIMIT = 1024 * 1024
TIMEOUT_SECONDS = 60
PLAIN = "struct R{x:i32}\n"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, detail):
    if not condition:
        raise AssertionError(detail)


class CaptureFailure(RuntimeError):
    def __init__(self, status, detail):
        super().__init__(detail)
        self.status = status


def capture(argv, cwd, entry):
    """The exact owned compiler tree, its pipe readers and cleanup share one deadline."""
    deadline = time.monotonic() + TIMEOUT_SECONDS
    buffers = {"stdout": bytearray(), "stderr": bytearray()}
    overflow, failed, progress = threading.Event(), threading.Event(), threading.Event()
    readers, process = [], None

    def read(name, stream):
        try:
            while True:
                chunk = os.read(stream.fileno(), 65536)
                if not chunk:
                    break
                remaining = OUTPUT_LIMIT - len(buffers[name])
                buffers[name].extend(chunk[:remaining])
                if len(chunk) > remaining:
                    overflow.set()
                    break
        except (OSError, ValueError):
            failed.set()
        finally:
            stream.close()
            progress.set()

    try:
        with ProcessJob() as job:
            try:
                try:
                    process = subprocess.Popen(
                        argv, cwd=cwd, stdin=subprocess.DEVNULL,
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0,
                        creationflags=job.flags, start_new_session=os.name != "nt")
                    job.attach(process)
                except (OSError, ValueError) as error:
                    raise CaptureFailure("startup_failure", str(error)) from error
                for name in buffers:
                    worker = threading.Thread(target=read, args=(name, getattr(process, name)), daemon=True)
                    readers.append(worker)
                    worker.start()
                while True:
                    if overflow.is_set():
                        raise CaptureFailure("output_limit", "compiler output exceeds the per-stream limit")
                    if failed.is_set():
                        raise CaptureFailure("capture_failure", "compiler pipe reading failed")
                    if time.monotonic() >= deadline:
                        raise CaptureFailure("timeout", "compiler capture exceeded the monotonic deadline")
                    if process.poll() is not None and not any(worker.is_alive() for worker in readers):
                        break
                    remaining = max(0, min(0.02, deadline - time.monotonic()))
                    if process.poll() is None:
                        try:
                            process.wait(timeout=remaining)
                        except subprocess.TimeoutExpired:
                            pass
                    else:
                        progress.wait(timeout=remaining)
                        progress.clear()
            finally:
                cleanup_error = None
                if process is not None:
                    try:
                        job.stop(process)
                    except (OSError, subprocess.TimeoutExpired) as error:
                        cleanup_error = error
                for worker in readers:
                    worker.join(timeout=2)
                if any(worker.is_alive() for worker in readers):
                    raise CaptureFailure("cleanup_failure", "owned compiler readers did not finish")
                if process is not None:
                    for name in buffers:
                        stream = getattr(process, name)
                        if stream is not None and not stream.closed:
                            stream.close()
                if cleanup_error is not None:
                    raise CaptureFailure("cleanup_failure", str(cleanup_error)) from cleanup_error
        # Readers may set a terminal error between the loop's checks and its
        # completion branch. Final joined outcomes, including paid cleanup,
        # must be checked before an exited result can become successful.
        if overflow.is_set():
            raise CaptureFailure("output_limit", "compiler output exceeds the per-stream limit")
        if failed.is_set():
            raise CaptureFailure("capture_failure", "compiler pipe reading failed")
        if time.monotonic() >= deadline:
            raise CaptureFailure("timeout", "compiler capture/cleanup exceeded the deadline")
        entry["exit_code"] = process.returncode
        entry["capture_status"] = "exited"
    except KeyboardInterrupt as error:
        entry["capture_status"] = "cancelled"
        raise CaptureFailure("cancelled", "compiler job cancelled") from error
    except CaptureFailure as error:
        entry["capture_status"] = error.status
        raise
    except (OSError, subprocess.TimeoutExpired) as error:
        entry["capture_status"] = "cleanup_failure" if process is not None else "startup_failure"
        raise CaptureFailure(entry["capture_status"], str(error)) from error
    finally:
        for name, data in buffers.items():
            raw = bytes(data)
            log = cwd / (entry["log_id"] + "." + name + ".log")
            log.write_bytes(raw)
            entry[name + "_log"] = str(log)
            entry[name + "_sha256"] = hashlib.sha256(raw).hexdigest()
    return {name: bytes(data) for name, data in buffers.items()}


def fixtures():
    negative = {
        "unused_sink": PLAIN + "fn R.take(sink self)->i32{return self.x}\n",
        "sink_temporary": PLAIN + "fn R.take(sink self)->i32{return self.x}\nfn f()->i32{return R{x:1}.take()}\n",
        "set_uninitialized": PLAIN + "fn R.fill(set self){self=R{x:7}}\nfn f()->i32{var r:R\nr.fill()\nreturn r.x}\n",
        "set_initialized": PLAIN + "fn R.fill(set self){self=R{x:7}}\nfn f()->i32{var r=R{x:1}\nr.fill()\nreturn r.x}\n",
        "inout_whole": PLAIN + "fn R.reset(inout self){self=R{x:7}}\n",
        "inout_nested": PLAIN + "fn R.reset(inout self,flag:bool){if flag{self=R{x:7}}}\n",
        "inout_self_copy": PLAIN + "fn R.reset(inout self){self=self}\n",
        "inout_self_set_helper": PLAIN + "fn fill(set r:R){r=R{x:7}}\nfn R.reset(inout self){fill(set self)}\n",
        "inout_self_inout_helper": PLAIN + "fn fill(inout r:R){r=R{x:7}}\nfn R.reset(inout self){fill(inout self)}\n",
    }
    positive = {
        "field_methods": PLAIN + "fn R.read(let self)->i32{return self.x}\nfn R.reset(inout self){self.x=7}\n",
        "explicit_set": PLAIN + "fn fill(set r:R){r=R{x:7}}\nfn f()->i32{var r:R\nfill(set r)\nreturn r.x}\n",
        "explicit_sink": PLAIN + "fn take(sink r:R)->i32{return r.x}\nfn f()->i32{var r=R{x:1}\nreturn take(sink r)}\n",
        "field_record": "struct C{x:i32}\nstruct R{child:C}\nfn R.reset(inout self){self.child=C{x:7}}\n",
        "field_helpers": PLAIN + "fn fill(set x:i32){x=7}\nfn bump(inout x:i32){x+=1}\nfn R.reset(inout self){fill(set self.x)\nbump(inout self.x)}\n",
    }
    return negative, positive


def directory_state(folder):
    return {str(p.relative_to(folder)): "directory" if p.is_dir() else sha(p)
            for p in sorted(folder.rglob("*"))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--beryl", required=True, type=Path)
    parser.add_argument("--expect-compiler-sha256", required=True)
    args = parser.parse_args()
    compiler = args.beryl.resolve(strict=True)
    require(sha(compiler) == args.expect_compiler_sha256.lower(), "explicit compiler hash mismatch")
    (ROOT / "build").mkdir(exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="enfusion receiver admission & spaces-", dir=ROOT / "build"))
    negative, positive = fixtures()
    sources = {}
    for name, body in (*negative.items(), *positive.items()):
        source = work / (name + ".be")
        source.write_text("module admission." + name + "\n" + body, encoding="utf-8")
        sources[name] = source
    # The complete current controller remains a source-generation regression,
    # not an engine execution or revalidation of older PID runtime receipts.
    pid_source = ROOT / "packages" / "sparkos" / "pid" / "pid.be"
    sources["full_pid"] = work / "full_pid.be"
    sources["full_pid"].write_bytes(pid_source.read_bytes())
    positive["full_pid"] = None
    routes = ("check-enfusion", "check-enfusion-json", "emit-enfusion", "build-enfusion")
    positive_routes = ("check-native-json", "check-enfusion-json", "emit-enfusion", "build-enfusion")
    expected = [f"reject:{name}:{route}" for name in negative for route in routes]
    expected += [f"admit:{name}:{route}" for name in positive for route in positive_routes]
    tracked = [Path(__file__).resolve(), compiler, pid_source, *sources.values(),
               ROOT / "tools" / "beryl-mod" / "process_job.py",
               ROOT / "tests" / "unit" / "test_enfusion.c",
               *sorted(p for p in (ROOT / "src").rglob("*") if p.is_file()),
               *sorted(p for p in (ROOT / "runtime").rglob("*") if p.is_file())]

    def identities():
        return {str(path): sha(path) for path in tracked}

    receipt = {"schema_version": 1, "operation": "verify_enfusion_receiver_admission",
               "status": "running", "compiler_path": str(compiler),
               "compiler_sha256": sha(compiler), "inputs": identities(),
               "expected_cases": expected, "completed_cases": [], "commands": [],
               "source_program_execution": "not_run", "engine_execution": "not_run",
               "installation": "not_run", "measurements": "not_measured",
               "scope": "plain receiver target admission and EnforceScript source generation",
               "capture_limits": {"seconds": TIMEOUT_SECONDS, "bytes_per_stream": OUTPUT_LIMIT}}
    print("Enfusion receiver admission artifacts: " + str(work), flush=True)
    outcome = 1
    try:
        for is_negative, cases in ((True, negative), (False, positive)):
            for name in cases:
                output = work / (name + "-enfusion")
                output.mkdir()
                sentinel = output / "SPK_Generated.c"
                if is_negative:
                    sentinel.write_bytes(b"preserved generated-source sentinel\n")
                prior_output = directory_state(output)
                for route in routes if is_negative else positive_routes:
                    case = f"{'reject' if is_negative else 'admit'}:{name}:{route}"
                    require(case == expected[len(receipt["commands"])], "unexpected command sequence")
                    flags = ["check", "-t", "enfusion", sources[name]]
                    if route == "check-native-json":
                        flags = ["check", "--format", "json", sources[name]]
                    elif route == "check-enfusion-json":
                        flags = ["check", "-t", "enfusion", "--format", "json", sources[name]]
                    elif route in ("emit-enfusion", "build-enfusion"):
                        flags = ["build", "-t", "enfusion", "--prefix", "SPK",
                                 *(["--out-dir", output] if route == "build-enfusion" else []), sources[name]]
                    entry = {"case": case, "argv": list(map(str, [compiler, *flags])),
                             "log_id": f"command-{len(receipt['commands']):03d}"}
                    receipt["commands"].append(entry)
                    cache = directory_state(work / ".beryl-cache")
                    raw = capture(entry["argv"], work, entry)
                    text = (raw["stdout"] + raw["stderr"]).decode("utf-8", errors="strict")
                    require(directory_state(work / ".beryl-cache") == cache, "source-only command created a native job")
                    if is_negative:
                        require(entry["exit_code"] != 0 and "BE0701" in text, entry)
                        require(directory_state(output) == prior_output, "rejection changed prior generated output")
                        if route == "emit-enfusion":
                            require(not raw["stdout"], "rejection emitted EnforceScript")
                    else:
                        require(entry["exit_code"] == 0, entry)
                        if route == "emit-enfusion":
                            require(b"class SPK_" in raw["stdout"], "positive source was not generated")
                            require(b"this =" not in raw["stdout"], "positive source replaces implicit self")
                        if route == "build-enfusion":
                            require(sentinel.is_file(), "positive source output is missing")
                            require(b"class SPK_" in sentinel.read_bytes(), "positive source output is incomplete")
                            require(b"this =" not in sentinel.read_bytes(), "positive output replaces implicit self")
                            entry["generated_source_sha256"] = sha(sentinel)
                    if route.endswith("-json"):
                        payload = json.loads(raw["stdout"])
                        require(payload["compiler_fingerprint"] == receipt["compiler_sha256"], "JSON compiler identity mismatch")
                        require(payload["status"] == ("failure" if is_negative else "success"), payload)
                        if is_negative:
                            require(any(d["code"] == "BE0701" for d in payload["diagnostics"]), payload)
                    receipt["completed_cases"].append(case)
        require(receipt["completed_cases"] == expected, "incomplete case set")
        require(identities() == receipt["inputs"], "source/compiler/tool bytes changed during verification")
        receipt["status"] = "success"
        outcome = 0
    except (AssertionError, OSError, ValueError, CaptureFailure, KeyboardInterrupt) as error:
        receipt["status"] = "failure"
        receipt["failure_kind"] = (error.status if isinstance(error, CaptureFailure) else
                                   "cancelled" if isinstance(error, KeyboardInterrupt) else type(error).__name__)
        receipt["failure"] = str(error)
    finally:
        try:
            receipt["inputs_after"] = identities()
            if receipt["inputs_after"] != receipt["inputs"]:
                receipt["status"] = "failure"
                receipt["failure_kind"] = "stale_input"
                receipt["failure"] = "source/compiler/tool bytes changed before the final receipt"
                outcome = 1
        except OSError as error:
            receipt["inputs_after"] = {"status": "unavailable", "detail": str(error)}
            receipt["status"] = "failure"
            receipt["failure_kind"] = "stale_input"
            receipt["failure"] = "input identity could not be reread: " + str(error)
            outcome = 1
        (work / "results.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(f"{receipt['status']}: {len(receipt['completed_cases'])}/{len(expected)} source-only cases", flush=True)
    return outcome


if __name__ == "__main__":
    raise SystemExit(main())
