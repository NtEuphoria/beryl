#!/usr/bin/env python3
"""Deterministic host-readiness faults with fake children only; no host launches."""
from __future__ import annotations
import contextlib
import copy
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import uuid

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "scripts" / "verify-host-readiness.py"
SPEC = importlib.util.spec_from_file_location("beryl_host_readiness", SOURCE)
host = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = host
SPEC.loader.exec_module(host)


def require(condition, detail):
    if not condition:
        raise AssertionError(detail)


class FakeChild:
    def __init__(self, harness):
        self.harness = harness
        self.pid = 73123
        self.returncode = None
        self.waits = []
        self.stops = 0

    def poll(self):
        if self.harness.options.get("poll_error"):
            raise OSError("synthetic poll failure")
        if self.harness.options.get("exit_before_cleanup"):
            self.returncode = 17
        return self.returncode

    def wait(self, timeout):
        self.waits.append(timeout)
        current = json.loads((self.harness.receipt_dir / "result.json").read_text())
        require(current["phase"] in {"primary_wait_requested", "cleanup_exit_wait_requested"}, "Wait preceded its boundary receipt")
        require(timeout == (10 if current["phase"] == "primary_wait_requested" else 5), "Wait has wrong bound")
        require(current.get("owned_pid") == self.pid and current.get("owned_process"), "Wait lost child identity")
        instruction = self.harness.instructions.pop(0)
        if self.harness.options.get("change_host"):
            self.harness.executable.write_bytes(b"changed synthetic executable")
        if self.harness.options.get("tamper_latest"):
            (self.harness.receipt_dir / "result.json").write_text('{"changed":true}\n')
        if instruction == "timeout":
            raise subprocess.TimeoutExpired(["synthetic-child"], timeout)
        if instruction == "cancel":
            raise KeyboardInterrupt("synthetic cancellation")
        if instruction == "error":
            raise OSError("synthetic wait failure")
        if instruction == "missing_exit":
            return None
        self.returncode = instruction
        return instruction

    def kill(self):
        current = json.loads((self.harness.receipt_dir / "result.json").read_text())
        require(current["phase"] == "direct_child_stop_requested", "Stop preceded its boundary receipt")
        require(current["primary_outcome"]["status"] != "not_started", "Stop lost original outcome")
        self.stops += 1
        if self.harness.options.get("kill_error"):
            raise OSError("synthetic stop failure")


class Harness:
    def __init__(self, folder, **options):
        self.folder = folder
        self.folder.mkdir()
        self.executable = folder / "pwsh.exe"
        self.executable.write_bytes(b"synthetic executable; never launched")
        self.expected = {"path": str(self.executable), "sha256": host.file_identity(self.executable)["sha256"]}
        self.receipt_dir = folder / "attempt"
        self.options = options
        self.instructions = list(options.get("instructions", [0]))
        self.child = FakeChild(self)
        self.launch_count = 0
        self.identity_count = 0
        self.time = 0.0
        self.write_failures = 0

    def clock(self):
        self.time += 0.001
        return self.time

    def popen(self, argv, **kwargs):
        self.launch_count += 1
        current = json.loads((self.receipt_dir / "result.json").read_text())
        require(current["phase"] == "launch_requested", "Launch preceded initial/boundary receipt")
        require(kwargs["shell"] is False and kwargs["stdin"] == subprocess.DEVNULL, "Wrong launch semantics")
        for name in ("stdout", "stderr"):
            host.regular(Path(kwargs[name].name))
            require(kwargs[name].fileno() >= 0, "Log is not a direct file descriptor")
        if self.options.get("startup_error"):
            raise OSError("synthetic launch failure")
        kwargs["stdout"].write(self.options.get("stdout", host.MARKER))
        kwargs["stderr"].write(self.options.get("stderr", b""))
        return self.child

    def identity(self, child, expected):
        self.identity_count += 1
        if self.options.get("identity_error") and self.identity_count == 1:
            raise OSError("synthetic identity unavailable")
        value = {"pid": child.pid, "start_ticks": 100001,
                 "start_ticks_unit": "windows_filetime_1601_utc_100ns",
                 "executable": str(self.executable), "executable_sha256": self.expected["sha256"]}
        if self.identity_count == 1 and self.options.get("initial_identity"):
            value.update(self.options["initial_identity"])
        if self.identity_count > 1 and self.options.get("cleanup_identity"):
            value.update(self.options["cleanup_identity"])
        return value

    def journal(self, directory):
        owner = self
        class FaultJournal(host.Journal):
            def _write_file(self, path, data):
                fault = owner.options.get("write_fault")
                selected = ("result-" in path.name) if owner.options.get("write_fault_latest") else path.name.startswith("receipt-")
                selected = selected and getattr(self, "phase", None) == owner.options.get("write_fault_phase", "prepared")
                if fault and selected and owner.write_failures == 0:
                    owner.write_failures += 1
                    if fault == "short_count":
                        return super()._write_file(path, data) - 1
                    if fault == "wrong_bytes":
                        super()._write_file(path, b"x" * len(data))
                        return len(data)
                return super()._write_file(path, data)

            def _replace_latest(self, pending, latest):
                super()._replace_latest(pending, latest)
                if owner.options.get("replace_fault") and self.phase == owner.options.get("write_fault_phase", "prepared") and owner.write_failures == 0:
                    owner.write_failures += 1
                    latest.write_bytes(b"changed latest")

            def save(self, record):
                self.phase = record["phase"]
                if record["phase"] == owner.options.get("receipt_fault"):
                    owner.write_failures += 1
                    if owner.write_failures == 1 or owner.options.get("receipt_fault_always"):
                        raise OSError("synthetic receipt write failure")
                super().save(record)
        return FaultJournal(directory)

    def run(self, **overrides):
        args = {"argv": [str(self.executable), "-NoProfile", "-Command", "literal"],
                "cwd": self.folder, "receipt_dir": self.receipt_dir,
                "timeout": 10, "cleanup_timeout": 5, "expected_executable": self.expected,
                "expected_stdout": host.MARKER,
                "hooks": host.Hooks(self.popen, self.identity, self.clock, self.journal)}
        args.update(overrides)
        return host.run_bounded(**args)


def check_result(harness, record, status, primary=None, cleanup=None, stops=None):
    require(record["status"] == status, f"Expected {status}, got {record['status']}")
    if primary:
        require(record["primary_outcome"]["status"] == primary, "Original primary outcome was replaced")
    if cleanup:
        require(record["cleanup"]["status"] == cleanup, "Wrong cleanup classification")
    if stops is not None:
        require(harness.child.stops == stops, "Wrong direct-child stop count")
    if record["receipt_saved"]:
        actual = json.loads((harness.receipt_dir / "result.json").read_text())
        require(actual == record | {"receipt_revision": actual["receipt_revision"]}, "Final receipt differs from outcome")
    if status != "success":
        require(record["verification"] == "not_verified", "Failure counted as readiness")


def scenario(folder, options, status, primary=None, cleanup=None, stops=None):
    harness = Harness(folder, **options)
    record = harness.run()
    check_result(harness, record, status, primary, cleanup, stops)
    return {"receipt": host.file_identity(harness.receipt_dir / "result.json"),
            "primary_outcome": record["primary_outcome"], "cleanup": record["cleanup"],
            "status": record["status"], "receipt_saved": record["receipt_saved"]}


def main():
    work = ROOT / "build" / ("host-readiness-tests-" + uuid.uuid4().hex)
    work.mkdir()
    planned = []
    def add(name, action):
        planned.append((name, action))

    scenarios = [
        ("return.zero.marker", {}, "success", "returned", "already_exited", 0),
        ("return.nonzero", {"instructions": [9]}, "failure", "returned", "already_exited", 0),
        ("return.wrong.stdout", {"stdout": b"wrong\r\n"}, "failure", "returned", "already_exited", 0),
        ("return.stderr", {"stderr": b"warning"}, "failure", "returned", "already_exited", 0),
        ("timeout.confirmed.stop", {"instructions": ["timeout", 2]}, "timeout", "timeout", "confirmed", 1),
        ("timeout.unconfirmed.exit", {"instructions": ["timeout", "timeout"]}, "timeout", "timeout", "unconfirmed", 1),
        ("timeout.stop.error", {"instructions": ["timeout"], "kill_error": True}, "timeout", "timeout", "unconfirmed", 1),
        ("timeout.poll.error", {"instructions": ["timeout"], "poll_error": True}, "timeout", "timeout", "unconfirmed", 0),
        ("timeout.exited.before.stop", {"instructions": ["timeout"], "exit_before_cleanup": True}, "timeout", "timeout", "already_exited", 0),
        ("identity.initial.unavailable", {"identity_error": True}, "unavailable", "unavailable", "unavailable", 0),
        ("identity.cleanup.start.changed", {"instructions": ["timeout"], "cleanup_identity": {"start_ticks": 100002}}, "timeout", "timeout", "unconfirmed", 0),
        ("identity.cleanup.pid.changed", {"instructions": ["timeout"], "cleanup_identity": {"pid": 73124}}, "timeout", "timeout", "unconfirmed", 0),
        ("identity.cleanup.hash.changed", {"instructions": ["timeout"], "cleanup_identity": {"executable_sha256": "0" * 64}}, "timeout", "timeout", "unconfirmed", 0),
        ("identity.initial.bool.pid", {"initial_identity": {"pid": True}}, "unavailable", "unavailable", "unavailable", 0),
        ("identity.initial.bool.start", {"initial_identity": {"start_ticks": True}}, "unavailable", "unavailable", "unavailable", 0),
        ("identity.initial.wrong.unit", {"initial_identity": {"start_ticks_unit": "dotnet_ticks"}}, "unavailable", "unavailable", "unavailable", 0),
        ("primary.wait.error", {"instructions": ["error", 2]}, "failure", "harness_failure", "confirmed", 1),
        ("primary.cancelled", {"instructions": ["cancel", 2]}, "cancelled", "cancelled", "confirmed", 1),
        ("primary.exit.missing", {"instructions": ["missing_exit", 2]}, "failure", "harness_failure", "confirmed", 1),
        ("cleanup.exit.missing", {"instructions": ["timeout", "missing_exit"]}, "timeout", "timeout", "unconfirmed", 1),
        ("startup.failure", {"startup_error": True}, "failure", "startup_failure", "not_needed", 0),
        ("receipt.initial.failure", {"receipt_fault": "prepared"}, "failure", "harness_failure", "not_needed", 0),
        ("receipt.launch.boundary.failure", {"receipt_fault": "launch_requested"}, "failure", "harness_failure", "not_needed", 0),
        ("receipt.pid.boundary.failure", {"receipt_fault": "launched_identity_requested"}, "failure", "harness_failure", "unavailable", 0),
        ("receipt.wait.boundary.failure", {"receipt_fault": "primary_wait_requested", "instructions": [2]}, "failure", "harness_failure", "confirmed", 1),
        ("receipt.primary.timeout.failure", {"receipt_fault": "primary_outcome_recorded", "instructions": ["timeout", 2]}, "timeout", "timeout", "confirmed", 1),
        ("receipt.cleanup.identity.failure", {"receipt_fault": "cleanup_identity_requested", "instructions": ["timeout"]}, "timeout", "timeout", "unavailable", 0),
        ("receipt.stop.boundary.failure", {"receipt_fault": "direct_child_stop_requested", "instructions": ["timeout"]}, "timeout", "timeout", "unavailable", 0),
        ("receipt.cleanup.wait.failure", {"receipt_fault": "cleanup_exit_wait_requested", "instructions": ["timeout"]}, "timeout", "timeout", "unconfirmed", 1),
        ("receipt.final.failure", {"receipt_fault": "finalized"}, "failure", "returned", "already_exited", 0),
        ("receipt.external.changed", {"tamper_latest": True}, "failure", "returned", "already_exited", 0),
        ("pin.changed.after.launch", {"change_host": True}, "failure", "returned", "already_exited", 0),
        ("log.evidence.bound", {"stdout": b"x" * (host.LOG_LIMIT + 1)}, "failure", "returned", "already_exited", 0),
    ]
    for name, options, status, primary, cleanup, stops in scenarios:
        add(name, lambda folder, opts=options, s=status, p=primary, c=cleanup, n=stops:
            scenario(folder, opts, s, p, c, n))

    def pin_mismatch(folder):
        harness = Harness(folder)
        wrong = dict(harness.expected, sha256="0" * 64)
        record = harness.run(expected_executable=wrong)
        check_result(harness, record, "stale_input", "stale_input", "not_needed", 0)
        require(harness.launch_count == 0, "Stale executable launched")
    add("pin.changed.before.launch", pin_mismatch)

    def missing_host(folder):
        harness = Harness(folder)
        harness.executable.unlink()
        record = harness.run()
        check_result(harness, record, "unavailable", "unavailable", "not_needed", 0)
        require(harness.launch_count == 0, "Missing executable launched")
    add("pin.missing", missing_host)

    def revisions(folder):
        harness = Harness(folder, instructions=["timeout", "timeout"])
        record = harness.run()
        revisions = sorted(harness.receipt_dir.glob("receipt-*.json"))
        require(len(revisions) == 9, "Missing timeout/cleanup revisions")
        rows = [json.loads(path.read_text()) for path in revisions]
        require([row["receipt_revision"] for row in rows] == list(range(len(rows))), "Receipt sequence not contiguous")
        require(rows[-1]["primary_outcome"]["status"] == "timeout" and rows[-1]["cleanup"]["status"] == "unconfirmed", "Final lost original timeout")
        require(rows[-1]["log_observation"] == "point_in_time_exit_unconfirmed", "Unconfirmed logs labeled complete")
        require(rows[2]["owned_pid"] == harness.child.pid, "PID not recorded immediately after launch")
    add("receipt.immutable.revisions", revisions)

    def inventory(folder):
        harness = Harness(folder)
        output = folder / "inventory"
        output.mkdir()
        with contextlib.redirect_stdout(io.StringIO()) as printed:
            code = host.main(["--powershell-host", str(harness.executable), "--output-root", str(output)])
        require(code == 0, "Inventory failed")
        reported = json.loads(printed.getvalue())
        receipt = json.loads(Path(reported["receipt"]).read_text())
        require(receipt["process_execution"] == "not_run" and receipt["readiness"] == "not_probed", "Inventory inferred execution")
        require(harness.launch_count == 0 and harness.child.stops == 0, "Inventory signaled process")
    add("inventory.nonexecuting", inventory)

    for name, options in [
        ("immutable.short.count", {"write_fault": "short_count"}),
        ("immutable.wrong.bytes", {"write_fault": "wrong_bytes"}),
        ("latest.short.count", {"write_fault": "short_count", "write_fault_latest": True}),
        ("latest.wrong.bytes", {"write_fault": "wrong_bytes", "write_fault_latest": True}),
        ("latest.replaced.wrong.bytes", {"replace_fault": True}),
        ("final.latest.short.count", {"write_fault": "short_count", "write_fault_latest": True, "write_fault_phase": "finalized"}),
        ("final.latest.wrong.bytes", {"write_fault": "wrong_bytes", "write_fault_latest": True, "write_fault_phase": "finalized"}),
        ("final.latest.replaced.wrong.bytes", {"replace_fault": True, "write_fault_phase": "finalized"}),
    ]:
        def write_fault(folder, options=options, name=name):
            harness = Harness(folder, **options)
            record = harness.run()
            require(record["status"] == "failure" and record["verification"] == "not_verified", "Corrupt receipt counted as verification")
            require(not record["receipt_saved"] and record["evidence_errors"], "Missing receipt failure classification")
            require(harness.child.stops == 0, "Write fault signaled child")
            if name.startswith("final."):
                require(record["primary_outcome"]["status"] == "returned", "Final write replaced original return")
                require(harness.launch_count == 1, "Final fault did not exercise execution seam")
            else:
                require(record["primary_outcome"]["status"] == "harness_failure" and harness.launch_count == 0, "Initial write fault still launched")
            return {"primary_outcome": record["primary_outcome"], "receipt_saved": False,
                    "retained_files": [host.file_identity(path) for path in sorted(harness.receipt_dir.glob("*.json"))]}
        add("receipt." + name, write_fault)

    invalids = [
        ("timeout.zero", {"timeout": 0}), ("timeout.nan", {"timeout": float("nan")}),
        ("timeout.bool", {"timeout": True}), ("timeout.excessive", {"timeout": 301}),
        ("cleanup.zero", {"cleanup_timeout": 0}), ("cleanup.bool", {"cleanup_timeout": True}),
        ("cleanup.excessive", {"cleanup_timeout": 11}), ("argv.empty", {"argv": []}),
        ("argv.relative", {"argv": ["pwsh.exe"]}), ("argv.null", {"argv": ["NULL"]}),
        ("pin.malformed", {"expected_executable": {"path": "relative", "sha256": "0" * 64}}),
        ("expected.stdout.unbounded", {"expected_stdout": b"x" * (host.LOG_LIMIT + 1)}),
    ]
    for name, overrides in invalids:
        def invalid(folder, overrides=overrides, name=name):
            harness = Harness(folder)
            fields = copy.deepcopy(overrides)
            if name == "argv.null":
                fields["argv"] = [str(harness.executable), "bad\0arg"]
            try:
                harness.run(**fields)
            except ValueError:
                require(harness.launch_count == 0 and not harness.receipt_dir.exists(), "Invalid input created execution artifact")
                return
            raise AssertionError("Invalid bounded input was accepted")
        add("reject." + name, invalid)

    expected = [name for name, _ in planned]
    require(len(expected) == len(set(expected)), "Duplicate predeclared case")
    receipt = {"schema_version": 1, "operation": "host.readiness.synthetic_regression", "status": "running",
               "expected_case_ids": expected, "expected_cases": len(expected), "cases": [],
               "source": host.file_identity(SOURCE), "runner": host.file_identity(Path(__file__)),
               "scope": "Fake process factories/identities only; filesystem receipts are real",
               "host_execution": "not_run", "compiler_execution": "not_run", "engine_execution": "not_run",
               "actual_process_signals": "not_run"}
    result = work / "result.json"
    result.write_text(json.dumps(receipt, indent=2) + "\n")
    for index, (name, action) in enumerate(planned):
        try:
            evidence = action(work / f"case-{index:03d}")
            receipt["cases"].append({"id": name, "status": "success", "evidence": evidence})
        except BaseException as exc:
            receipt["cases"].append({"id": name, "status": "failure", "failure": host.error_info(exc)})
    completed = [case["id"] for case in receipt["cases"]]
    receipt["case_set_complete"] = completed == expected and len(completed) == len(set(completed))
    receipt["passed"] = sum(case["status"] == "success" for case in receipt["cases"])
    receipt["failed"] = len(receipt["cases"]) - receipt["passed"]
    receipt["source_unchanged"] = host.file_identity(SOURCE) == receipt["source"] and host.file_identity(Path(__file__)) == receipt["runner"]
    receipt["status"] = "success" if not receipt["failed"] and receipt["case_set_complete"] and receipt["source_unchanged"] else "failure"
    result.write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"receipt": host.file_identity(result), "status": receipt["status"],
                      "passed": receipt["passed"], "failed": receipt["failed"],
                      "failures": [case for case in receipt["cases"] if case["status"] != "success"]}))
    return 0 if receipt["status"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
