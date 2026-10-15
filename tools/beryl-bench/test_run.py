#!/usr/bin/env python3
"""Collector unit tests. Do not time real Beryl programs or claim speedups."""
from __future__ import annotations

import json
import hashlib
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from contextlib import contextmanager
from types import SimpleNamespace
from unittest import mock
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "tools" / "beryl-experiments"))

import evaluate as ev
import receipts as rec
import run as collector


class ProcessCaptureTests(unittest.TestCase):
    def run_code(self, code: str, **kwargs):
        return collector.run_binary([sys.executable, "-I", "-c", code], timeout=kwargs.pop("timeout", 5), **kwargs)

    def assert_status(self, expected: str, code: str, **kwargs):
        with self.assertRaises(collector.CollectorError) as caught:
            self.run_code(code, **kwargs)
        self.assertEqual(caught.exception.status, expected)

    @contextmanager
    def scheduled_terminal_readers(self, *, delay=0, on_release=None):
        """Release actual pipe reads only inside the completion branch."""
        original_thread = threading.Thread
        gate = threading.Event()
        workers = []
        def scheduled_thread(*args, **kwargs):
            target, target_args = kwargs["target"], kwargs["args"]
            def delayed_reader():
                if not gate.wait(5):
                    raise RuntimeError("capture scheduling fixture never released reader")
                target(*target_args)
            kwargs = dict(kwargs, target=delayed_reader, args=())
            worker = original_thread(*args, **kwargs)
            original_alive = worker.is_alive
            def finish_at_completion_check():
                if not gate.is_set():
                    if delay:
                        time.sleep(delay)
                    if on_release is not None:
                        on_release()
                    gate.set()
                worker.join(timeout=3)
                return original_alive()
            worker.is_alive = finish_at_completion_check
            workers.append(worker)
            return worker
        try:
            with mock.patch.object(collector.threading, "Thread", side_effect=scheduled_thread):
                yield gate
        finally:
            gate.set()
            for worker in workers:
                worker.join(timeout=3)

    def test_exact_output_and_separate_stderr(self):
        result = self.run_code("import os; os.write(1, b'exact\\x00bytes\\r\\n'); os.write(2, b'notice\\n')")
        self.assertEqual(result["status"], "exited")
        self.assertEqual(result["exit_code"], 0)
        self.assertEqual(result["stdout"], b"exact\x00bytes\r\n")
        self.assertEqual(result["stderr"], b"notice\n")
        collector.check_golden(result, b"exact\x00bytes\n", "exact")
        self.assertGreater(result["paid"], 0)
        self.assertEqual(result["duration_clock"], "monotonic")
        self.assertEqual(result["clock_window"]["status"], "compatible" if result["paid"] <= result["ended"] - result["started"] else "unavailable")

    def test_stderr_before_stdout_does_not_deadlock(self):
        # This order filled the stderr pipe while the old runner blocked reading
        # stdout. Both streams remain independently bounded and exact.
        result = self.run_code("import os\nfor _ in range(64): os.write(2, b'e'*32768)\nfor _ in range(64): os.write(1, b'o'*32768)")
        self.assertEqual(result["stdout"], b"o" * 2097152)
        self.assertEqual(result["stderr"], b"e" * 2097152)

    def test_infinite_silence_times_out(self):
        started = time.monotonic()
        self.assert_status("timeout", "import time; time.sleep(60)", timeout=0.3)
        self.assertLess(time.monotonic() - started, 5)

    def test_closed_pipes_do_not_hide_infinite_execution(self):
        self.assert_status("timeout", "import os,time; os.close(1); os.close(2); time.sleep(60)", timeout=0.3)

    def test_stdout_cap_is_a_distinct_failure(self):
        self.assert_status("output_limit", "import os,time; os.write(1, b'x'*1048576); time.sleep(60)", output_limit=65536)

    def test_stderr_cap_is_a_distinct_failure(self):
        self.assert_status("output_limit", "import os,time; os.write(2, b'x'*1048576); time.sleep(60)", output_limit=65536)

    def test_fast_exit_overflow_of_either_stream_is_rejected(self):
        for stream in (1, 2):
            self.assert_status("output_limit", f"import os; os.write({stream}, b'x'*2048)", output_limit=1024)

    def test_terminal_overflow_after_main_flag_checks_is_rejected(self):
        # Real child output with controlled scheduling: readers publish their
        # overflow only during the completion check, after initial flag reads.
        with self.scheduled_terminal_readers():
            self.assert_status("output_limit", "import os; os.write(1, b'x'*2048)", output_limit=1024)

    def test_terminal_capture_after_deadline_is_rejected(self):
        with self.scheduled_terminal_readers(delay=1.1) as gate:
            self.assert_status("timeout", "import os; os.write(1, b'ok\\n')", timeout=1)
            self.assertTrue(gate.is_set(), "fixture did not reach the delayed terminal completion branch")

    def test_terminal_cancellation_after_main_flag_checks_is_rejected(self):
        cancellation = threading.Event()
        with self.scheduled_terminal_readers(on_release=cancellation.set) as gate:
            self.assert_status("cancelled", "import os; os.write(1, b'ok\\n')", cancel=cancellation)
            self.assertTrue(gate.is_set(), "fixture did not reach terminal completion")

    def test_exact_cap_is_admitted(self):
        result = self.run_code("import os; os.write(1, b'x'*65536)", output_limit=65536)
        self.assertEqual(result["stdout"], b"x" * 65536)

    def test_nonzero_exit_is_execution_not_timeout(self):
        result = self.run_code("import os; os.write(1, b'ok\\n'); os.write(2, b'failed\\n'); raise SystemExit(9)")
        self.assertEqual(result["exit_code"], 9)
        self.assertEqual(result["stderr"], b"failed\n")
        with self.assertRaises(collector.CollectorError) as caught:
            collector.check_golden(result, b"ok\n", "nonzero")
        self.assertEqual(caught.exception.status, "program_failure")

    def test_startup_failure(self):
        with tempfile.TemporaryDirectory(prefix="beryl-bench-missing-", dir=ROOT / "build") as folder:
            with self.assertRaises(collector.CollectorError) as caught:
                collector.run_binary([Path(folder) / "absent.exe"], timeout=1)
            self.assertEqual(caught.exception.status, "startup_failure")

    def test_cancellation_terminates_the_owned_process(self):
        cancellation = threading.Event()
        timer = threading.Timer(0.3, cancellation.set)
        timer.start()
        try:
            self.assert_status("cancelled", "import time; time.sleep(60)", cancel=cancellation)
        finally:
            timer.cancel()
            timer.join()

    def test_pre_cancelled_does_not_launch(self):
        cancellation = threading.Event()
        cancellation.set()
        with mock.patch.object(collector.subprocess, "Popen") as launch:
            self.assert_status("cancelled", "raise SystemExit(0)", cancel=cancellation)
        launch.assert_not_called()

    def test_owned_descendant_is_removed_but_unrelated_process_survives(self):
        with tempfile.TemporaryDirectory(prefix="beryl-bench-owned-", dir=ROOT / "build") as folder:
            marker = Path(folder) / "descendant-survived.txt"
            descendant = "import time,pathlib; time.sleep(1); pathlib.Path(" + repr(str(marker)) + ").write_text('escaped')"
            parent = "import subprocess,sys,time; subprocess.Popen([sys.executable,'-I','-c'," + repr(descendant) + "]); time.sleep(60)"
            unrelated = subprocess.Popen([sys.executable, "-I", "-c", "import time; time.sleep(60)"],
                                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                self.assert_status("timeout", parent, timeout=0.4)
                time.sleep(1.1)
                self.assertFalse(marker.exists(), "owned descendant escaped timeout cleanup")
                self.assertIsNone(unrelated.poll(), "an unrelated Python process was terminated")
            finally:
                unrelated.kill()
                unrelated.wait(timeout=5)

    def test_utc_clock_rollback_fails_instead_of_fabricating_time(self):
        with mock.patch.object(collector.time, "time_ns", side_effect=[10**18, 10**18 - 1]):
            self.assert_status("clock_failure", "raise SystemExit(0)")

    def test_paid_duration_comes_from_monotonic_clock(self):
        with mock.patch.object(collector.time, "time_ns", side_effect=[10**18, 10**18 + 10**12]):
            result = self.run_code("raise SystemExit(0)")
        self.assertLess(result["paid"], 5 * 10**9)
        self.assertEqual(result["ended"] - result["started"], 10**12)

    def test_short_utc_window_is_retained_without_invented_timestamps(self):
        with mock.patch.object(collector.time, "time_ns", side_effect=[10**18, 10**18 + 1]):
            result = self.run_code("raise SystemExit(0)")
        self.assertEqual(result["started"], 10**18)
        self.assertEqual(result["ended"], 10**18 + 1)
        self.assertGreater(result["paid"], 1)
        self.assertEqual(result["clock_window"]["status"], "unavailable")

    def test_invalid_deadline_or_output_bound_never_launches(self):
        with mock.patch.object(collector.subprocess, "Popen") as launch:
            for kwargs in ({"timeout": 0}, {"timeout": float("inf")}, {"timeout": True}, {"timeout": 1e300},
                           {"output_limit": 0}, {"output_limit": True}, {"output_limit": 67108865}):
                self.assert_status("invalid_input", "raise SystemExit(0)", **kwargs)
        launch.assert_not_called()

    def test_missing_memory_capability_is_explicit(self):
        with mock.patch.object(collector, "query_peak", return_value=None):
            result = self.run_code("raise SystemExit(0)")
        self.assertIsNone(result["peak_bytes"])
        self.assertEqual(result["memory_capability"]["status"], "unavailable")
        with self.assertRaises(collector.CollectorError) as caught:
            collector.resources_of({}, result["peak_bytes"])
        self.assertEqual(caught.exception.status, "unavailable")

    def test_collect_stops_before_build_or_receipt_without_resources(self):
        with tempfile.TemporaryDirectory(prefix="beryl-bench-unavailable-", dir=ROOT / "build") as folder:
            output = Path(folder) / "never-created"
            args = SimpleNamespace(workload="checked_lcg", out=str(output))
            with mock.patch.object(collector, "build_artifacts") as build:
                with self.assertRaises(collector.CollectorError) as caught:
                    collector.collect(args)
            self.assertEqual(caught.exception.status, "unavailable")
            build.assert_not_called()
            self.assertFalse(output.exists())

    def test_compile_uses_the_same_deadline_and_capture(self):
        with self.assertRaises(collector.CollectorError) as caught:
            collector.timed_compile([sys.executable, "-I", "-c", "import time; time.sleep(60)"], timeout=0.3)
        self.assertEqual(caught.exception.status, "timeout")


class CollectorTests(unittest.TestCase):
    def test_lists_six_workloads(self) -> None:
        names = sorted(
            p.name for p in collector.WORKLOADS.iterdir() if (p / "workload.json").is_file()
        )
        self.assertEqual(
            names,
            ["array_sum_2d", "checked_lcg", "inout_axpy", "list_grow_reuse", "struct_pass", "vec3_particles"],
        )

    def test_golden_mismatch_stops_before_receipt(self) -> None:
        with self.assertRaisesRegex(collector.CollectorError, "stdout mismatch"):
            collector.check_golden(
                {"exit_code": 0, "stdout": b"nope\n", "stderr": b""},
                b"20000001\n",
                "probe",
            )

    def test_nonzero_exit_is_a_failure(self) -> None:
        with self.assertRaisesRegex(collector.CollectorError, "exited 9"):
            collector.check_golden(
                {"exit_code": 9, "stdout": b"20000001\n", "stderr": b""},
                b"20000001\n",
                "probe",
            )

    def test_receipts_freeze_in_the_evaluator(self) -> None:
        root = Path(tempfile.mkdtemp(prefix="beryl-bench-receipts-", dir=ROOT / "build"))
        empty = rec.write_bytes(root, "empty.raw", b"")
        state = rec.write_bytes(root, "state.raw", b"ok\n")
        proof = rec.write_text(root, "proof.txt", "synthetic collector test; not a timed run.\n")
        identities = {
            key: rec.write_text(root, f"{key}.identity", f"synthetic {key}\n")
            for key in rec.IDENTITIES
        }
        hashes = {key: ref["sha256"] for key, ref in identities.items()}
        beginning = 10**18 - 10**11
        blocks = []
        for index in range(30):
            unit = f"pilot:{index}"
            order = "a" if index % 2 == 0 else "b"
            block = {"unit_id": unit, "first": order}
            for side in ("a", "b"):
                start = beginning + index * 10**8 + (0 if side == order else 10**7)
                paid = {key: 0 for key in rec.COSTS}
                paid["compute"] = 1000000
                run = rec.measurement(
                    measurement_id=f"{unit}:{side}",
                    unit_id=unit,
                    session_id=f"{unit}:session:{side}",
                    started=start,
                    ended=start + 5000000,
                    fingerprints={**{k: v for k, v in hashes.items() if k != "baseline"}, "artifact": hashes["baseline"]},
                    paid=paid,
                    resources={
                        "peak_bytes": 2048, "retained_bytes": 512, "allocations": 0,
                        "text_bytes": 1000, "build_ns": 1000000, "edit_check_ns": 10000,
                    },
                    semantic={
                        "status": "complete", "expected_cases": 1, "completed_cases": 1,
                        "events": empty, "stdout": empty, "state": state,
                    },
                )
                block[side] = rec.write_json(root, f"{index}-{side}.json", run)
            block["independence"] = rec.write_json(
                root, f"{index}-independence.json",
                rec.independence(unit_id=unit, measurement_ids=[f"{unit}:a", f"{unit}:b"], evidence=proof),
            )
            blocks.append(block)
        spec = json.loads((collector.WORKLOADS / "checked_lcg" / "workload.json").read_text(encoding="utf-8"))
        rec.write_json(
            root, "pilot.json",
            rec.pilot(
                experiment_id="checked_lcg",
                population="Analytical fixture, no real population sampled.",
                fingerprints=identities,
                budgets=spec["budgets"],
                blocks=blocks,
            ),
        )
        freeze = ev.freeze(ev.Reader(root), {"path": "pilot.json", "sha256": ev.digest((root / "pilot.json").read_bytes())}, 10**18)
        self.assertEqual(freeze["kind"], "beryl.performance.freeze")
        self.assertEqual(len(freeze["unit_ids"]), 30)


if __name__ == "__main__":
    (ROOT / "build").mkdir(exist_ok=True)
    receipt_root = Path(tempfile.mkdtemp(prefix="bench-harness-check-", dir=ROOT / "build"))
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    case_ids = []
    def remember(group):
        for entry in group:
            if isinstance(entry, unittest.TestSuite):
                remember(entry)
            else:
                case_ids.append(entry.id())
    remember(suite)
    sources = [HERE / "run.py", HERE / "test_run.py", HERE / "receipts.py", ROOT / "tools" / "beryl-mod" / "process_job.py"]
    before = {str(path.relative_to(ROOT)).replace("\\", "/"): hashlib.sha256(path.read_bytes()).hexdigest() for path in sources}
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    after = {str(path.relative_to(ROOT)).replace("\\", "/"): hashlib.sha256(path.read_bytes()).hexdigest() for path in sources}
    passed = result.wasSuccessful() and before == after
    receipt = {"schema_version": 1, "operation": "native_collector_capture_verification", "status": "success" if passed else "failure",
               "tests_run": result.testsRun, "expected_cases": case_ids, "failures": [case.id() for case, _ in result.failures],
               "errors": [case.id() for case, _ in result.errors], "skipped": [(case.id(), reason) for case, reason in result.skipped],
               "source_hashes": before, "sources_unchanged": before == after,
               "python_sha256": hashlib.sha256(Path(sys.executable).read_bytes()).hexdigest(),
               "scope": "executable process-capture failures and synthetic receipt compatibility; no benchmark or speedup"}
    (receipt_root / "result.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print("receipt: " + str(receipt_root / "result.json"))
    raise SystemExit(0 if passed else 1)
