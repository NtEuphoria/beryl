#!/usr/bin/env python3
"""Inventory a host, or explicitly run one pinned, owned readiness probe.

The reusable run_bounded API uses regular files rather than subprocess pipes.
Every potentially blocking boundary has a preceding atomic receipt. Its timeout
bounds wait(), not an operating-system launch/termination call that never returns.
Only the direct child created by this call can be stopped. No old PID is accepted.
"""
from __future__ import annotations

import argparse
import copy
import ctypes
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass
from typing import Callable

SCHEMA_VERSION = 1
HOST_LIMIT = 256 * 1024 * 1024
LOG_LIMIT = 8 * 1024 * 1024
MARKER = b"BERYL_FIXED_HOST_PROBE\r\n"
ROOT = Path(__file__).resolve().parents[1]
SHA = re.compile(r"[0-9a-f]{64}\Z")


def regular(path: Path) -> os.stat_result:
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
        raise ValueError(f"Not a direct regular file: {path}")
    return info


def file_identity(path: Path, limit: int = HOST_LIMIT) -> dict:
    path = Path(os.path.abspath(path))
    before = regular(path)
    if before.st_size > limit:
        raise ValueError(f"File exceeds {limit}-byte evidence bound: {path}")
    digest = hashlib.sha256()
    total = 0
    with path.open("rb") as source:
        for block in iter(lambda: source.read(65536), b""):
            total += len(block)
            if total > limit:
                raise ValueError(f"File grew beyond evidence bound: {path}")
            digest.update(block)
    after = regular(path)
    if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
        after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns
    ) or total != after.st_size:
        raise ValueError(f"File changed during identity read: {path}")
    return {"path": str(path), "bytes": total, "sha256": digest.hexdigest()}


def canonical(path: str | Path) -> str:
    return os.path.normcase(os.path.realpath(path))


def error_info(exc: BaseException) -> dict:
    value = {"type": type(exc).__name__, "message": str(exc)[:4096]}
    for name in ("errno", "winerror"):
        if type(getattr(exc, name, None)) is int:
            value[name] = getattr(exc, name)
    return value


class Journal:
    """New immutable revisions, plus an atomic latest pointer in a new directory."""
    def __init__(self, directory: Path):
        self.directory = Path(directory)
        self.directory.mkdir(parents=False, exist_ok=False)
        self.sequence = 0
        self.latest_hash: str | None = None

    def _write_file(self, path: Path, data: bytes) -> int:
        with path.open("xb") as output:
            count = output.write(data)
            output.flush()
            os.fsync(output.fileno())
        return count

    def _replace_latest(self, pending: Path, latest: Path) -> None:
        os.replace(pending, latest)

    def save(self, record: dict) -> None:
        if self.sequence >= 64:
            raise ValueError("Receipt revision budget exhausted")
        payload = copy.deepcopy(record)
        payload["receipt_revision"] = self.sequence
        data = (json.dumps(payload, indent=2, allow_nan=False) + "\n").encode("utf-8")
        if len(data) > 1024 * 1024:
            raise ValueError("Receipt exceeds 1 MiB")
        revision = self.directory / f"receipt-{self.sequence:04d}.json"
        wanted_hash = hashlib.sha256(data).hexdigest()
        if self._write_file(revision, data) != len(data):
            raise OSError("Short immutable receipt write")
        if file_identity(revision, 1024 * 1024)["sha256"] != wanted_hash:
            raise OSError("Immutable receipt readback mismatch")
        latest = self.directory / "result.json"
        if self.latest_hash is None:
            if latest.exists() or latest.is_symlink():
                raise ValueError("Unexpected prior result file")
        elif file_identity(latest, 1024 * 1024)["sha256"] != self.latest_hash:
            raise ValueError("Latest receipt was changed by another writer")
        pending = self.directory / f"result-{self.sequence:04d}.tmp"
        if self._write_file(pending, data) != len(data):
            raise OSError("Short latest receipt write")
        if file_identity(pending, 1024 * 1024)["sha256"] != wanted_hash:
            raise OSError("Latest pending receipt readback mismatch")
        self._replace_latest(pending, latest)
        if file_identity(latest, 1024 * 1024)["sha256"] != wanted_hash:
            raise OSError("Atomic latest receipt readback mismatch")
        self.latest_hash = wanted_hash
        self.sequence += 1


def windows_child_identity(child: subprocess.Popen, expected: dict) -> dict:
    """Read the handle owned by Popen; never reopen a potentially reused PID."""
    if os.name != "nt":
        raise OSError("Pinned host process identity is currently Windows-only")
    from ctypes import wintypes
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetProcessId.argtypes = [wintypes.HANDLE]
    kernel.GetProcessId.restype = wintypes.DWORD
    kernel.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
    kernel.GetProcessTimes.restype = wintypes.BOOL
    kernel.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR,
                                                ctypes.POINTER(wintypes.DWORD)]
    kernel.QueryFullProcessImageNameW.restype = wintypes.BOOL
    handle = wintypes.HANDLE(int(child._handle))
    pid = int(kernel.GetProcessId(handle))
    if pid <= 0 or pid != child.pid:
        raise OSError("Owned process handle PID mismatch")
    created, exited, kernel_time, user_time = [wintypes.FILETIME() for _ in range(4)]
    if not kernel.GetProcessTimes(handle, ctypes.byref(created), ctypes.byref(exited),
                                  ctypes.byref(kernel_time), ctypes.byref(user_time)):
        raise ctypes.WinError(ctypes.get_last_error())
    size = wintypes.DWORD(32768)
    buffer = ctypes.create_unicode_buffer(size.value)
    if not kernel.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
        raise ctypes.WinError(ctypes.get_last_error())
    ticks = (int(created.dwHighDateTime) << 32) | int(created.dwLowDateTime)
    executable = Path(buffer.value)
    actual = file_identity(executable)
    if canonical(executable) != canonical(expected["path"]) or actual["sha256"] != expected["sha256"]:
        raise ValueError("Owned executable differs from the pinned host")
    return {"pid": pid, "start_ticks": ticks,
            "start_ticks_unit": "windows_filetime_1601_utc_100ns",
            "executable": str(executable), "executable_sha256": actual["sha256"]}


def launch(argv: list[str], **kwargs) -> subprocess.Popen:
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    return subprocess.Popen(argv, **kwargs)


@dataclass
class Hooks:
    """Injection seam for deterministic tests; defaults perform real operations."""
    popen: Callable = launch
    child_identity: Callable = windows_child_identity
    clock: Callable = time.monotonic
    journal: Callable = Journal


def validate_identity(value: dict, child, expected: dict) -> dict:
    fields = {"pid", "start_ticks", "start_ticks_unit", "executable", "executable_sha256"}
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError("Incomplete owned-child identity")
    if type(value["pid"]) is not int or value["pid"] <= 0 or value["pid"] != child.pid:
        raise ValueError("Owned-child PID mismatch")
    if type(value["start_ticks"]) is not int or value["start_ticks"] <= 0:
        raise ValueError("Invalid process creation time")
    if value["start_ticks_unit"] != "windows_filetime_1601_utc_100ns":
        raise ValueError("Unsupported process creation-time unit")
    if not isinstance(value["executable"], str) or canonical(value["executable"]) != canonical(expected["path"]):
        raise ValueError("Owned-child executable path mismatch")
    if value["executable_sha256"] != expected["sha256"]:
        raise ValueError("Owned-child executable hash mismatch")
    return copy.deepcopy(value)


def _arguments(argv, cwd, timeout, cleanup_timeout, expected):
    if not isinstance(expected, dict) or set(expected) != {"path", "sha256"} or not isinstance(expected["path"], str) or not Path(expected["path"]).is_absolute() or not isinstance(expected["sha256"], str) or not SHA.fullmatch(expected["sha256"]):
        raise ValueError("Expected explicit absolute executable path and lowercase SHA-256")
    if not isinstance(argv, list) or not 1 <= len(argv) <= 64 or any(
        not isinstance(arg, str) or not arg or "\0" in arg or len(arg) > 32768 for arg in argv
    ):
        raise ValueError("Expected bounded explicit argv")
    if not Path(argv[0]).is_absolute() or canonical(argv[0]) != canonical(expected["path"]):
        raise ValueError("argv[0] must be the pinned absolute executable")
    if type(timeout) not in (int, float) or not math.isfinite(timeout) or not 0 < timeout <= 300:
        raise ValueError("timeout must be in (0, 300] seconds")
    if type(cleanup_timeout) not in (int, float) or not math.isfinite(cleanup_timeout) or not 0 < cleanup_timeout <= 10:
        raise ValueError("cleanup_timeout must be in (0, 10] seconds")
    if not Path(cwd).is_dir():
        raise ValueError("Missing working directory")


def run_bounded(argv: list[str], cwd: Path, receipt_dir: Path, timeout: float,
                cleanup_timeout: float, *, expected_executable: dict,
                expected_stdout: bytes | None = None, hooks: Hooks | None = None) -> dict:
    """Run source-controlled argv once; return separate primary/cleanup evidence.

    receipt_dir must be new. No process is launched if initial evidence cannot be
    saved. Receipt errors prevent readiness success. Cleanup verifies the same
    handle-derived identity before stopping only this call's direct child.
    OS calls themselves are not promised a hard wall-clock deadline.
    """
    hooks = hooks or Hooks()
    _arguments(argv, cwd, timeout, cleanup_timeout, expected_executable)
    if expected_stdout is not None and (not isinstance(expected_stdout, bytes) or len(expected_stdout) > LOG_LIMIT):
        raise ValueError("Expected output must be bounded bytes")
    directory = Path(receipt_dir).absolute()
    start = hooks.clock()
    record = {"schema_version": SCHEMA_VERSION, "operation": "host.owned_bounded_probe",
              "operation_id": uuid.uuid4().hex, "status": "running", "phase": "prepared",
              "source": file_identity(Path(__file__)),
              "argv": list(argv), "cwd": str(Path(cwd).absolute()),
              "expected_executable": copy.deepcopy(expected_executable),
              "timeout_seconds": timeout, "cleanup_timeout_seconds": cleanup_timeout,
              "primary_outcome": {"status": "not_started"},
              "cleanup": {"status": "not_needed", "stop_requested": False, "exit_confirmed": False},
              "owned_process": None, "evidence_errors": [], "receipt_saved": False,
              "child_behavior_scope": "source-controlled argv supplied by caller; no inferred engine/runtime coverage",
              "policy_override": False,
              "limits": {"receipt_bytes": 1024 * 1024, "log_evidence_bytes": LOG_LIMIT,
                         "wait_deadlines_do_not_bound_os_launch_or_stop": True,
                         "direct_file_output_is_not_a_physical_disk_quota": True}}
    journal = None
    child = None
    streams = []
    original_identity = None

    def checkpoint(phase):
        record["phase"] = phase
        record["elapsed_seconds"] = max(0.0, hooks.clock() - start)
        try:
            record["receipt_saved"] = True
            journal.save(record)
            return True
        except BaseException as exc:
            record["receipt_saved"] = False
            record["evidence_errors"].append({"stage": "receipt." + phase, **error_info(exc)})
            return False

    def cleanup():
        info = record["cleanup"]
        if child is None:
            return
        try:
            if child.poll() is not None:
                if type(child.returncode) is not int:
                    raise ValueError("Missing exact integer child exit status")
                info.update(status="already_exited", exit_confirmed=True, exit_code=child.returncode)
                return
            if original_identity is None:
                info.update(status="unavailable", reason="No complete pinned child identity; stop not attempted")
                return
            if not checkpoint("cleanup_identity_requested"):
                info.update(status="unavailable", reason="Cleanup boundary receipt could not be saved")
                return
            observed = validate_identity(hooks.child_identity(child, expected_executable), child, expected_executable)
            if observed != original_identity:
                raise ValueError("Owned child identity changed before cleanup")
            info["identity_before_stop"] = observed
            info.update(status="stop_requested", stop_requested=True)
            if not checkpoint("direct_child_stop_requested"):
                info.update(status="unavailable", stop_requested=False,
                            reason="Stop-request receipt could not be saved; no stop attempted")
                return
            child.kill()
            info["stop_call_returned"] = True
            info["status"] = "exit_wait_requested"
            if not checkpoint("cleanup_exit_wait_requested"):
                info.update(status="unconfirmed", reason="Exit-wait boundary receipt could not be saved")
                return
            try:
                child.wait(timeout=cleanup_timeout)
                if type(child.returncode) is not int:
                    raise ValueError("Cleanup wait returned without an exact integer exit status")
                info.update(status="confirmed", exit_confirmed=True, exit_code=child.returncode)
            except subprocess.TimeoutExpired as exc:
                info.update(status="unconfirmed", exit_confirmed=False, error=error_info(exc))
        except BaseException as exc:
            info.update(status="unconfirmed", exit_confirmed=False, error=error_info(exc))

    try:
        journal = hooks.journal(directory)
        record["receipt_directory"] = str(directory)
        if not checkpoint("prepared"):
            record["primary_outcome"] = {"status": "harness_failure", "reason": "Initial receipt write failed; no launch"}
        else:
            try:
                actual = file_identity(Path(expected_executable["path"]))
            except BaseException as exc:
                record["primary_outcome"] = {"status": "unavailable", "error": error_info(exc)}
                raise
            record["executable_before"] = actual
            if actual["sha256"] != expected_executable["sha256"]:
                record["primary_outcome"] = {"status": "stale_input", "reason": "Pinned executable hash mismatch"}
            else:
                for name in ("stdout", "stderr"):
                    stream = (directory / (name + ".log")).open("xb", buffering=0)
                    regular(Path(stream.name))
                    streams.append(stream)
                if not checkpoint("launch_requested"):
                    record["primary_outcome"] = {"status": "harness_failure", "reason": "Launch boundary receipt failed; no launch"}
                else:
                    child = hooks.popen(list(argv), cwd=str(Path(cwd).absolute()), stdin=subprocess.DEVNULL,
                                        stdout=streams[0], stderr=streams[1], shell=False)
                    record["owned_pid"] = child.pid
                    if not checkpoint("launched_identity_requested"):
                        record["primary_outcome"] = {"status": "harness_failure", "reason": "Launched PID receipt failed"}
                    else:
                        original_identity = validate_identity(hooks.child_identity(child, expected_executable), child, expected_executable)
                        record["owned_process"] = original_identity
                        if not checkpoint("primary_wait_requested"):
                            record["primary_outcome"] = {"status": "harness_failure", "reason": "Wait boundary receipt failed"}
                        else:
                            try:
                                child.wait(timeout=timeout)
                                if type(child.returncode) is not int:
                                    raise ValueError("Primary wait returned without an exact integer exit status")
                                record["primary_outcome"] = {"status": "returned", "exit_code": child.returncode,
                                                             "exit_confirmed": True}
                            except subprocess.TimeoutExpired as exc:
                                record["primary_outcome"] = {"status": "timeout", "error": error_info(exc)}
                            except KeyboardInterrupt as exc:
                                record["primary_outcome"] = {"status": "cancelled", "error": error_info(exc)}
                            except BaseException as exc:
                                record["primary_outcome"] = {"status": "harness_failure", "error": error_info(exc)}
    except KeyboardInterrupt as exc:
        record["primary_outcome"] = {"status": "cancelled", "error": error_info(exc)}
    except BaseException as exc:
        if record["primary_outcome"]["status"] == "not_started":
            record["primary_outcome"] = {"status": "startup_failure" if child is None else "unavailable",
                                         "error": error_info(exc)}
    finally:
        if journal is not None:
            checkpoint("primary_outcome_recorded")
            cleanup()
        for stream in streams:
            try:
                stream.close()
            except BaseException as exc:
                record["evidence_errors"].append({"stage": "log_close", **error_info(exc)})
        complete = bool(child is not None and (record["primary_outcome"].get("exit_confirmed") or
                                               record["cleanup"]["exit_confirmed"]))
        record["log_observation"] = "snapshot_after_confirmed_direct_child_exit" if complete else "point_in_time_exit_unconfirmed"
        record["descendant_exit"] = "not_observed; inherited log writers are not covered by direct-child exit"
        for name in ("stdout", "stderr"):
            path = directory / (name + ".log")
            if path.exists() or path.is_symlink():
                try:
                    record[name] = file_identity(path, LOG_LIMIT)
                except BaseException as exc:
                    record["evidence_errors"].append({"stage": name + "_identity", **error_info(exc)})
        try:
            record["executable_after"] = file_identity(Path(expected_executable["path"]))
            if record["executable_after"] != record.get("executable_before"):
                record["evidence_errors"].append({"stage": "executable_after", "message": "Executable identity changed"})
        except BaseException as exc:
            record["evidence_errors"].append({"stage": "executable_after", **error_info(exc)})
        try:
            if file_identity(Path(__file__)) != record["source"]:
                record["evidence_errors"].append({"stage": "source_after", "message": "Diagnostic utility source changed"})
        except BaseException as exc:
            record["evidence_errors"].append({"stage": "source_after", **error_info(exc)})
        primary = record["primary_outcome"]["status"]
        record["status"] = {"timeout": "timeout", "cancelled": "cancelled", "unavailable": "unavailable",
                            "stale_input": "stale_input"}.get(primary, "failure")
        if primary == "returned" and record["primary_outcome"]["exit_code"] == 0 and not record["evidence_errors"]:
            output_ok = True
            if expected_stdout is not None:
                try:
                    output_ok = (directory / "stdout.log").read_bytes() == expected_stdout and record["stderr"]["bytes"] == 0
                except BaseException as exc:
                    record["evidence_errors"].append({"stage": "output_contract", **error_info(exc)})
                    output_ok = False
            record["output_contract_verified"] = output_ok
            if output_ok and complete and original_identity is not None:
                record["status"] = "success"
        record["verification"] = "verified" if record["status"] == "success" else "not_verified"
        if journal is not None and not checkpoint("finalized"):
            if record["status"] == "success":
                record["status"] = "failure"
            record["verification"] = "not_verified"
    return record


def default_host() -> Path:
    return Path(sys.executable).resolve().parents[1] / "native" / "powershell" / "pwsh.exe"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--powershell-host", type=Path, default=default_host())
    parser.add_argument("--expected-host-sha256")
    parser.add_argument("--probe", action="store_true", help="Explicitly execute the fixed literal probe once")
    parser.add_argument("--timeout", type=float, default=10)
    parser.add_argument("--cleanup-timeout", type=float, default=5)
    parser.add_argument("--output-root", type=Path, default=ROOT / "build")
    args = parser.parse_args(argv)
    if args.probe and not args.expected_host_sha256:
        parser.error("--probe requires --expected-host-sha256")
    if args.expected_host_sha256 is not None and not SHA.fullmatch(args.expected_host_sha256):
        parser.error("Expected lowercase SHA-256")
    if not args.output_root.is_dir():
        parser.error("--output-root must be an existing directory")
    directory = args.output_root.absolute() / ("host-readiness-" + uuid.uuid4().hex)
    host = args.powershell_host.absolute()
    if not args.probe:
        record = {"schema_version": 1, "operation": "host.readiness_inventory", "status": "unavailable",
                  "source": file_identity(Path(__file__)),
                  "process_execution": "not_run", "engine_execution": "not_run", "compiler_execution": "not_run",
                  "policy_override": False, "readiness": "not_probed", "host": {"path": str(host)}}
        try:
            record["host"] = file_identity(host)
            record["status"] = "success"
            if args.expected_host_sha256 and record["host"]["sha256"] != args.expected_host_sha256:
                record["status"] = "stale_input"
        except BaseException as exc:
            record["failure"] = error_info(exc)
        journal = Journal(directory)
        journal.save(record)
    elif os.name != "nt":
        record = {"schema_version": 1, "operation": "host.owned_bounded_probe", "status": "unavailable",
                  "process_execution": "not_run", "reason": "Verified host-process identity is Windows-only"}
        Journal(directory).save(record)
    else:
        fixed_argv = [str(host), "-NoProfile", "-NonInteractive", "-Command", "Write-Output 'BERYL_FIXED_HOST_PROBE'"]
        record = run_bounded(fixed_argv, ROOT, directory, args.timeout, args.cleanup_timeout,
                             expected_executable={"path": str(host), "sha256": args.expected_host_sha256},
                             expected_stdout=MARKER)
    print(json.dumps({"receipt": str(directory / "result.json"), "status": record["status"],
                      "primary_outcome": record.get("primary_outcome"), "cleanup": record.get("cleanup"),
                      "receipt_saved": record.get("receipt_saved", True)}, allow_nan=False))
    return 0 if record["status"] == "success" else 2 if record["status"] == "unavailable" else 1


if __name__ == "__main__":
    raise SystemExit(main())
