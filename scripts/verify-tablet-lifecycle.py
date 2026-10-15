#!/usr/bin/env python3
"""Verify the isolated scalar tablet protocol against an independent source oracle.

Reference execution is the default. --native permits one differential attempt;
blocked native launches remain incomplete and are never retried by this verifier.
"""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parent.parent
PACKAGE = ROOT / "packages/sparkos/tablet-lifecycle-prototype"
SOURCE = PACKAGE / "src/lifecycle.be"
sys.path.insert(0, str(PACKAGE))
from oracle import OriginalBackend, World, bits, f32
from protocol_model import ProtocolBackend
sys.path.insert(0, str(ROOT / "tools/beryl-mod"))
from process_job import ProcessJob

RETAINED = ROOT / "build/tablet-recovery-1ae28bbb58d4499d808b467a390b6fc1/inputs/mesh/scripts/Game/SparkOSMesh/UI"
PROVENANCE = {
    "SPK_TabletComponent.c": "1f15962cf67a8cc513d7068757e89360260016fadff1c8843719784acc94be3a",
    "SPK_TabletGadget.c": "d336244b7d178324eded5bc5e584f721cd2c4f9b7036ac90d1f757ba30b0199c",
    "SPK_TabletUI.c": "4efeab8cce793939d748506f34691aae9b0b47aa8b32ed568ece05accf28a05d",
    "SPK_ScreenRT.c": "6328c5e86787b75c8cf949fcbd914c4fb137e17534a6158150bdba13818e942b",
    "SPK_TabletChrome.c": "53c2fccfb900371ce0ea409d98f0903a20e71e472630e6caea87b29477a1811e",
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def corpus():
    cases = []
    def add(name, ops, *, mode=0, accumulator=0, config=None, hooks=()):
        cases.append({"id": name, "ops": ops, "mode": mode, "accumulator": f32(accumulator),
                      "config": config or {}, "hooks": hooks})
    for mode in range(3):
        for ui in (False, True):
            for screen in (False, True):
                for operation, argument in (("focus", False), ("unfocus", False), ("held", True), ("held", False), ("delete", False)):
                    add(f"mode{mode}-ui{int(ui)}-screen{int(screen)}-{operation}{int(argument)}",
                        [(operation, argument, 0)], mode=mode,
                        config={"ui_present": ui, "screen_present": screen})
    add("defaults-init-frame", [("init", False, 0), ("frame", False, 1)])
    add("init-preserves-accumulator", [("init", False, 0)], mode=2, accumulator=0.125,
        config={"ui_present": True, "screen_present": True})
    add("init-preserves-negative-zero", [("init", False, 0)], mode=2, accumulator=-0.0)
    add("rejected-focus-preserves-negative-zero", [("focus", False, 0)], accumulator=-0.0)
    add("failed-open", [("held", True, 0), ("focus", False, 0)], config={"open": False})
    add("degraded-map-missing-input-core", [("gadget", True, 0), ("gadget", False, 0)],
        config={"map": False, "input": False, "core": False})
    add("screen-enable-failure", [("held", True, 0), ("focus", False, 0), ("held", False, 0)],
        config={"screen_build": False})
    add("screen-owner-missing", [("held", True, 0), ("held", True, 0)], config={"owner": False})
    add("duplicate-held-and-gadget", [("held", True, 0), ("held", True, 0), ("gadget", True, 0),
                                      ("gadget", True, 0), ("gadget", False, 0), ("gadget", False, 0)])
    for field in ("local_owner", "controller", "controlled_owner", "tablet"):
        add("gadget-guard-" + field, [("gadget", True, 0), ("gadget", False, 0)], config={field: False})
    add("reopen-preserves-accumulator-and-bindings", [("held", True, 0), ("focus", False, 0),
        ("frame", False, 0.125), ("unfocus", False, 0), ("focus", False, 0), ("frame", False, 0.125)])
    for label, dt in (("below", 0.2499999850988388), ("exact", 0.25), ("above", 0.2500000298023224),
                      ("large", 4.0), ("zero", 0.0), ("negative", -0.125), ("negative-zero", -0.0)):
        add("dt-" + label, [("frame", False, dt)], mode=2, config={"ui_present": True})
    add("rounds-to-threshold", [("frame", False, 2**-27)], mode=2, accumulator=0.2499999850988388,
        config={"ui_present": True})
    add("rounds-stays-below", [("frame", False, 2**-29)], mode=2, accumulator=0.2499999850988388,
        config={"ui_present": True})
    add("focused-without-ui-frame", [("frame", False, 0.5)], mode=2, accumulator=0.125)
    add("negative-accumulator-recovery", [("frame", False, -0.5), ("frame", False, 0.5), ("frame", False, 0.25)],
        mode=2, config={"ui_present": True})
    add("long-rounding-sequence", [("frame", False, 0.1)] * 33, mode=2, config={"ui_present": True})
    add("open-reentry-stow", [("held", True, 0), ("focus", False, 0)], hooks=[("ui.open", "held", False, 0)])
    add("marker-reentry-stow", [("frame", False, 0.125)], mode=2, accumulator=0.125,
        config={"ui_present": True, "screen_present": True}, hooks=[("ui.markers", "held", False, 0)])
    add("close-reentry-held", [("held", False, 0)], mode=2,
        config={"ui_present": True, "screen_present": True}, hooks=[("ui.close", "held", True, 0)])
    add("init-super-reentry-held", [("init", False, 0)], accumulator=0.125,
        hooks=[("super.init", "held", True, 0)])
    add("delete-close-reentry-init", [("delete", False, 0)], mode=2, accumulator=0.125,
        config={"ui_present": True, "screen_present": True}, hooks=[("ui.close", "init", False, 0)])
    add("telemetry-reentry-focus", [("frame", False, 0.25)], mode=2,
        config={"ui_present": True}, hooks=[("ui.telemetry", "held", False, 0)])
    if len({case["id"] for case in cases}) != len(cases):
        raise AssertionError("duplicate fixture case identity")
    return cases


def evaluate(case, backend, world_type=World, mutant=None):
    world = world_type(case["config"], case["hooks"], mode=case["mode"], accumulator=case["accumulator"])
    world.backend = OriginalBackend(world) if backend == "original" else ProtocolBackend(world, mutant=mutant)
    for operation, argument, dt in case["ops"]:
        world.invoke(operation, argument, dt)
    return {"events": world.events, "steps": world.steps, "final": world.snapshot(),
            "hooks_used": [hook["used"] for hook in world.hooks]}


def observable(result):
    return {name: result[name] for name in ("events", "final", "hooks_used")}


def literal(value):
    if bits(value) == 0x80000000:
        return "-0f32"
    return repr(f32(value)) + "f32"


def generate(cases, outputs, *, shared=False):
    lines = ["//! Generated bounded replay; script service responses are immutable fixture data.",
             "module sparkos.tablet_lifecycle_replay",
             "use sparkos.tablet_lifecycle_prototype.State", "use sparkos.tablet_lifecycle_prototype.Operation",
             "use sparkos.tablet_lifecycle_prototype.next"]
    expected_bits = []
    assertions = 0
    for case in cases:
        lines += [f'test "{case["id"]}" {{', "var state = State{}", f'state.mode = {case["mode"]}',
                  f'state.telemetry_accumulator = {literal(case["accumulator"])}']
        if shared:
            lines.append("var shared_operation = Operation{}")
        active = {}
        count = 0
        for sequence, step in enumerate(outputs[case["id"]]["steps"]):
            if step.get("seq") != sequence:
                raise ValueError("missing/extra/out-of-order transcript record")
            identity = step["id"]
            variable = "shared_operation" if shared else "op_" + str(identity)
            if step["event"] == "begin":
                if identity in active:
                    raise ValueError("duplicate active operation")
                active[identity] = None
                op = step["operation"]
                lines += [(variable + " = Operation{}") if shared else ("var " + variable + " = Operation{}"),
                          f'{variable}.kind = {op["kind"]}', f'{variable}.held = {str(op["held"]).lower()}',
                          f'{variable}.time_slice = {literal(op["time_slice"])}']
            elif step["event"] == "step":
                if identity not in active or not 0 <= step["opcode"] <= 19 or step["reply"] not in (0, 1):
                    raise ValueError("unknown/missing operation or invalid opcode/reply")
                count += 1
                if count > 4096:
                    raise ValueError("replay step limit")
                op = step["operation"]
                lines += [f'assert(next(inout state, inout {variable}, {step["reply"]}) == {step["opcode"]})',
                          f'assert(state.mode == {step["mode"]})', f'assert({variable}.pc == {op["pc"]})',
                          f'assert({variable}.screen_pc == {op["screen_pc"]})',
                          f'assert({variable}.answer == {str(op["answer"]).lower()})',
                          f'assert(state.telemetry_accumulator == {literal(struct.unpack("<f", struct.pack("<I", step["accumulator_bits"]))[0])})',
                          "println(state.telemetry_accumulator)"]
                assertions += 6
                expected_bits.append(step["accumulator_bits"])
                active[identity] = step
            elif step["event"] == "end":
                if identity not in active:
                    raise ValueError("extra operation response")
                terminal = active.pop(identity)
                if terminal is None or terminal["opcode"] != 0 or terminal["operation"]["pc"] != 999 or terminal["operation"]["answer"] != step["answer"]:
                    raise ValueError("missing completion or wrong outcome response")
            else:
                raise ValueError("unknown transcript record")
        if active:
            raise ValueError("incomplete operation transcript")
        lines.append("}")
    return "\n".join(lines) + "\n", expected_bits, assertions


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--beryl", type=Path, required=True)
    parser.add_argument("--expect-sha256", required=True)
    parser.add_argument("--native", action="store_true")
    parser.add_argument("--clang", type=Path)
    args = parser.parse_args()
    compiler = args.beryl.resolve()
    if not re.fullmatch("[0-9a-f]{64}", args.expect_sha256) or digest(compiler) != args.expect_sha256:
        parser.error("explicit compiler identity does not match; nothing executed")
    if args.native and args.clang is None:
        parser.error("--native requires explicit --clang")
    path = Path(tempfile.mkdtemp(prefix="tablet-lifecycle-", dir=ROOT / "build"))
    record = {"schema_version": 1, "operation": "verify.tablet.lifecycle.prototype", "stage": "fixture",
              "status": "running", "compiler": {"path": str(compiler), "sha256": digest(compiler)},
              "source_provenance": [], "inputs": {}, "checks": [], "commands": [], "mutants": [],
              "limits": {"fixture_depth": 8, "operations_per_case": 128, "services_per_case": 1024,
                         "ordered_records_per_case": 4096, "next_calls_per_operation": 64,
                         "continuation_records_per_case": 4096, "reference_steps": 10000000,
                         "reference_bytes": 536870912, "compiler_timeout_ms": 30000,
                         "owned_harness_timeout_ms": 45000},
              "capabilities": {"actual_beryl_reference": "not_run", "native": "not_selected",
                               "engine": "not_run", "multiplayer": "not_run", "generated_component": "unavailable",
                               "tablet_port": "not_implemented", "queued_callback_execution": "not_run"}}
    print("Tablet lifecycle evidence: " + str(path), flush=True)
    def check(name):
        record["checks"].append(name)
        print("passed " + name, flush=True)
    def run_test(source, *, expected_success=True, native=False, replay=None, expected_bits_mismatch=False):
        previous = set((path / ".beryl-cache").glob("job-*"))
        backend = "differential" if native else "reference"
        argv = [str(compiler), "test", "--backend", backend, "--max-steps", "10000000", "--max-bytes", "536870912",
                "--timeout-ms", "30000"]
        if native:
            argv += ["--clang", str(args.clang.resolve())]
        argv += [str(SOURCE if source is None else source), str(replay or path / "replay.be")]
        started = time.monotonic_ns()
        try:
            with ProcessJob() as owner:
                process = subprocess.Popen(argv, cwd=path, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                           shell=False, creationflags=ProcessJob.flags,
                                           start_new_session=(os.name != "nt"))
                try:
                    owner.attach(process)
                    stdout, stderr = process.communicate(timeout=45)
                except BaseException:
                    if process.poll() is None:
                        owner.stop(process)
                    raise
        except (OSError, subprocess.TimeoutExpired) as exc:
            record["commands"].append({"argv": argv, "status": "startup_failure" if isinstance(exc, OSError) else "timeout",
                                       "error": str(exc), "duration_ns": time.monotonic_ns() - started})
            raise
        fresh = set((path / ".beryl-cache").glob("job-*")) - previous
        command = {"argv": argv, "exit_code": process.returncode, "duration_ns": time.monotonic_ns() - started,
                   "stdout": stdout.decode("utf-8", "replace"), "stderr": stderr.decode("utf-8", "replace")}
        record["commands"].append(command)
        if len(fresh) != 1:
            raise AssertionError("missing/extra compiler result receipt")
        job = fresh.pop()
        result = json.loads((job / "result.json").read_text(encoding="utf-8"))
        command["receipt"] = {"path": str(job / "result.json"), "sha256": digest(job / "result.json")}
        command["result"] = result
        expected_sources = [{"path": name, "sha256": digest(Path(name))} for name in argv[-2:]]
        if (type(result.get("schema_version")) is not int or result["schema_version"] != 1 or
                result.get("operation") != "test" or result.get("compiler_fingerprint") != record["compiler"]["sha256"] or
                result.get("sources") != expected_sources or result.get("reference_attempted") is not True or
                type(result.get("tests")) is not int or result["tests"] != len(cases) or
                type(result.get("assertions")) is not int or result["assertions"] != expected_assertions):
            raise AssertionError("compiler/replay identity or executed fixture coverage differs")
        events_path = job / "reference.events.jsonl"
        output_path = job / "reference.stdout.log"
        if (digest(events_path) != result.get("reference_events_sha256") or
                digest(output_path) != result.get("reference_output_sha256")):
            raise AssertionError("reference event/output stream fingerprint differs")
        events = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines()]
        if any(type(event.get("seq")) is not int or event["seq"] != sequence for sequence, event in enumerate(events)):
            raise AssertionError("reference event stream is incomplete or out of order")
        headers = [(match.group(1).decode("ascii"), match.start()) for match in
                   re.finditer(br'test "([^"\n]+)" \{', Path(argv[-1]).read_bytes())]
        if [name for name, _ in headers] != [case["id"] for case in cases]:
            raise AssertionError("replay does not contain the exact predeclared case set")
        begin_events = [event for event in events if event.get("event") == "test_begin"]
        end_events = [event for event in events if event.get("event") == "test_end"]
        expected_sites = [(1, offset) for _, offset in headers]
        if ([(event.get("file"), event.get("offset")) for event in begin_events] != expected_sites or
                [(event.get("file"), event.get("offset")) for event in end_events] != expected_sites or
                any(type(event.get("flag")) is not bool for event in begin_events + end_events)):
            raise AssertionError("reference case origins or completion receipts differ")
        assertions = [event for event in events if event.get("event") == "assert"]
        if len(assertions) != expected_assertions or any(type(event.get("flag")) is not bool for event in assertions):
            raise AssertionError("reference assertion events are incomplete")
        if any(event.get("event") in {"source_trap", "trap", "budget_exhausted", "timeout", "cancelled"} for event in events):
            raise AssertionError("trap or incomplete execution cannot detect a semantic fixture mutant")
        failed_ends = sum(event["flag"] is False for event in end_events)
        if type(result.get("failed_tests")) is not int or result["failed_tests"] != failed_ends:
            raise AssertionError("failed-case receipt does not match completed event stream")
        command["event_audit"] = {"status": "complete", "records": len(events), "case_origins": "exact",
                                  "events_sha256": digest(events_path), "source_identity": "exact"}
        if not expected_success and not expected_bits_mismatch:
            if (process.returncode == 0 or result.get("status") != "failure" or
                    result.get("reference_status") != "failure" or result.get("stage") != "reference_execution" or
                    failed_ends <= 0 or not any(event["flag"] is False for event in assertions) or
                    not any(diag.get("code") == "BE1002" and diag.get("level") == "error"
                            for diag in result.get("diagnostics", []) if type(diag) is dict)):
                raise AssertionError("deliberate mutation did not fail a Beryl assertion")
            command["semantic_comparison"] = {"status": "mismatch_detected", "kind": "source_assertion",
                                               "program_outcome": "failed_assertions", "failed_tests": failed_ends}
            return result
        if process.returncode != 0 or result.get("status") != "success" or result.get("reference_status") != "success":
            if native:
                return result
            raise AssertionError("Beryl reference fixture failed: " + command["stderr"])
        if failed_ends or any(event["flag"] is False for event in assertions) or (not native and result.get("stage") != "reference_execution"):
            raise AssertionError("successful fixture has failed assertions or an incompatible execution stage")
        actual_bits = [event["bits"] for event in events if event["event"] == "f32"]
        if expected_bits_mismatch:
            if len(actual_bits) != len(expected_bits) or result.get("tests") != len(cases) or result.get("assertions") != expected_assertions:
                raise AssertionError("signed-zero mutant did not completely execute its declared cases")
            changed = [i for i, pair in enumerate(zip(expected_bits, actual_bits)) if pair[0] != pair[1]]
            if not changed or any(expected_bits[i] != 0x80000000 or actual_bits[i] != 0 for i in changed):
                raise AssertionError("signed-zero mutant was not detected as the expected exact-bit mismatch")
            command["semantic_comparison"] = {"status": "mismatch_detected", "kind": "binary32_signed_zero_loss",
                                               "program_outcome": "successful_return", "changed_observation_indices": changed,
                                               "expected_bits": 0x80000000, "actual_bits": 0}
            return result
        if actual_bits != expected_bits or result.get("tests") != len(cases) or result.get("assertions") != expected_assertions:
            raise AssertionError("missing/extra case, assertion or exact binary32 observation")
        if native and (not result.get("compared") or result.get("native_status") != "exited"):
            raise AssertionError("native verification lacks executed matching result")
        return result
    try:
        for name, expected in PROVENANCE.items():
            actual = digest(RETAINED / name)
            record["source_provenance"].append({"path": str(RETAINED / name), "sha256": actual})
            if actual != expected:
                raise AssertionError("retained behavioral source changed: " + name)
        for item in sorted(PACKAGE.rglob("*")):
            if item.is_file() and "__pycache__" not in item.parts:
                record["inputs"][str(item.relative_to(ROOT))] = digest(item)
        record["inputs"][str(Path(__file__).resolve().relative_to(ROOT))] = digest(Path(__file__).resolve())
        record["inputs"]["tools/beryl-mod/process_job.py"] = digest(ROOT / "tools/beryl-mod/process_job.py")
        record["python"] = {"path": sys.executable, "sha256": digest(Path(sys.executable)), "version": sys.version}
        if args.native:
            record["clang"] = {"path": str(args.clang.resolve()), "sha256": digest(args.clang.resolve())}
        for name in record["inputs"]:
            retained_input = path / "inputs" / name
            retained_input.parent.mkdir(parents=True, exist_ok=True)
            retained_input.write_bytes((ROOT / name).read_bytes())
        cases = corpus()
        outputs = {}
        for case in cases:
            original = evaluate(case, "original")
            protocol = evaluate(case, "protocol")
            if observable(original) != observable(protocol):
                dump(path / (case["id"] + "-mismatch.json"), {"case": case, "original": original, "protocol": protocol})
                raise AssertionError("ordered service/state mismatch: " + case["id"])
            outputs[case["id"]] = protocol
        dump(path / "cases.json", cases)
        dump(path / "traces.json", outputs)
        record["case_ids"] = [case["id"] for case in cases]
        record["cases"] = len(cases)
        record["ordered_records"] = sum(len(result["events"]) for result in outputs.values())
        record["service_calls"] = sum(sum(event["phase"] == "service_begin" for event in result["events"]) for result in outputs.values())
        record["next_calls"] = sum(sum(step["event"] == "step" for step in result["steps"]) for result in outputs.values())
        check("independent original decisions match ordered protocol services/state after each service and operation")
        # Expected bits below are independent analytical anchors, not two matching evaluators.
        anchors = {"dt-below": 0x3E7FFFFF, "dt-exact": 0, "dt-above": 0,
                   "dt-large": 0, "dt-zero": 0, "dt-negative": 0xBE000000,
                   "rounds-to-threshold": 0, "rounds-stays-below": 0x3E7FFFFF,
                   "init-preserves-negative-zero": 0x80000000,
                   "rejected-focus-preserves-negative-zero": 0x80000000}
        for name, expected in anchors.items():
            if outputs[name]["final"]["accumulator_bits"] != expected:
                raise AssertionError("independent numerical anchor: " + name)
        fresh = outputs["reopen-preserves-accumulator-and-bindings"]
        opens = [event for event in fresh["events"] if event["phase"] == "service_end" and event["name"] == "ui.open"]
        assert [event["snapshot"]["hint"] for event in opens] == ["?", "fixture-bound-key"]
        assert fresh["final"]["accumulator_bits"] == 0
        focused_stow = outputs["mode2-ui1-screen1-held0"]
        names = [event["name"] for event in focused_stow["events"] if event["phase"] == "service_begin"]
        assert names == ["ui.close", "screen.enable", "screen.disable"]
        marker_reentry = outputs["marker-reentry-stow"]
        telemetry = [event for event in marker_reentry["events"] if event["phase"] == "service_begin" and event["name"] == "ui.telemetry"]
        assert len(telemetry) == 1 and telemetry[0]["snapshot"]["mode"] == 0 and telemetry[0]["snapshot"]["accumulator_bits"] == 0
        check("analytical threshold/rounding, intermediate screen calls, retained first-open hints and reentrant frame anchors")
        # Transcript admission rejects missing/extra/unknown records, before compiler invocation.
        one = copy.deepcopy(outputs)
        target = cases[0]["id"]
        for name, mutation in (("missing-end", lambda steps: steps.pop()),
                               ("missing-step", lambda steps: steps.pop(1)),
                               ("unknown-record", lambda steps: steps.append({"event": "unknown", "id": 0})),
                               ("unknown-reply", lambda steps: next(item for item in steps if item["event"] == "step").update(reply=99)),
                               ("extra-end", lambda steps: steps.append({"event": "end", "id": 9999}))):
            malformed = copy.deepcopy(one)
            mutation(malformed[target]["steps"])
            try:
                generate(cases, malformed)
            except ValueError:
                continue
            raise AssertionError("malformed transcript admitted: " + name)
        check("missing, extra, unknown and invalid scalar replies are rejected")
        bounded = World({}, hooks=[("screen.enable", "held", True, 0)] * 10)
        bounded.backend = ProtocolBackend(bounded)
        try:
            bounded.invoke("held", True)
        except ValueError as exc:
            assert "budget" in str(exc)
        else:
            raise AssertionError("reentry depth budget is not enforced")
        try:
            bounded.invoke("unknown-operation")
        except ValueError:
            pass
        else:
            raise AssertionError("unknown operation was accepted")
        check("fixture reentry limits and unknown operations fail as harness errors, not source traps")
        # Reentrant mutation deliberately uses one shared continuation: the oracle must detect it.
        reentry = next(case for case in cases if case["id"] == "marker-reentry-stow")
        damaged = evaluate(reentry, "protocol", mutant="reentry_overwrite")
        assert observable(damaged) != observable(evaluate(reentry, "original"))
        record["mutants"].append({"name": "global-continuation-overwrite", "layer": "Python scheduler", "detected": True})
        class DuplicatePopulation(World):
            def gadget(self, active):
                answer = super().gadget(active)
                if answer:
                    self.service("ui.contact_rows")
                return answer
        population = next(case for case in cases if case["id"] == "duplicate-held-and-gadget")
        assert observable(evaluate(population, "protocol", world_type=DuplicatePopulation)) != observable(evaluate(population, "original"))
        record["mutants"].append({"name": "duplicate-gadget-population", "layer": "Python fixture host", "detected": True})
        check("independent oracle detects shared-continuation reentry loss and duplicate gadget population")
        text, expected_bits, expected_assertions = generate(cases, outputs)
        if expected_bits.count(0x80000000) != 4:
            raise AssertionError("signed-zero fixtures do not expose all four preserved negative-zero observations")
        (path / "replay.be").write_text(text, encoding="utf-8")
        dump(path / "expected-f32-bits.json", expected_bits)
        record["expected_assertions"] = expected_assertions
        result = run_test(None)
        record["capabilities"]["actual_beryl_reference"] = "success"
        check("actual Beryl next functions replay all service responses/reentry interleavings with exact binary32 observations")
        baseline = SOURCE.read_text(encoding="utf-8")
        mutations = {
            "skipped-markers": ("return 16", "return 17"),
            "reordered-input-hookup": ("operation.pc = 5\n            return 5", "operation.pc = 5\n            return 6"),
            "init-resets-accumulator": ("state.mode = 0\n            operation.pc = 2\n            return 15", "state.mode = 0\n            state.telemetry_accumulator = 0f32\n            operation.pc = 2\n            return 15"),
            "focus-commits-before-open": ("if state.mode != 1 { return finish(inout operation, false) }\n            operation.pc = 1", "if state.mode != 1 { return finish(inout operation, false) }\n            state.mode = 2\n            operation.pc = 1"),
            "second-frame-gate-after-markers": ("state.telemetry_accumulator += operation.time_slice", "if state.mode != 2 { return finish(inout operation, false) }\n            state.telemetry_accumulator += operation.time_slice"),
        }
        mutations["duplicate-telemetry-catchup"] = ("        return finish(inout operation, false)\n    }\n\n    // OnDelete", "        if operation.pc == 3 {\n            operation.pc = 4\n            return 17\n        }\n        return finish(inout operation, false)\n    }\n\n    // OnDelete")
        for name, (old, new) in mutations.items():
            if baseline.count(old) != 1:
                raise AssertionError("mutation anchor is not unique: " + name)
            mutated = path / (name + ".be")
            mutated.write_text(baseline.replace(old, new, 1), encoding="utf-8")
            run_test(mutated, expected_success=False)
            record["mutants"].append({"name": name, "layer": "actual Beryl reference", "source_sha256": digest(mutated), "detected": True})
        shared, _, _ = generate(cases, outputs, shared=True)
        shared_path = path / "replay-shared-continuation.be"
        shared_path.write_text(shared, encoding="utf-8")
        run_test(None, expected_success=False, replay=shared_path)
        record["mutants"].append({"name": "Beryl-replay-shared-continuation-overwrite", "layer": "actual Beryl reference", "detected": True})
        signed_path = path / "replay-lost-negative-zero.be"
        signed_text = text.replace("state.telemetry_accumulator = -0f32", "state.telemetry_accumulator = 0f32")
        if signed_text == text:
            raise AssertionError("signed-zero replay mutation has no input anchor")
        signed_path.write_text(signed_text, encoding="utf-8")
        run_test(None, replay=signed_path, expected_bits_mismatch=True)
        record["mutants"].append({"name": "negative-zero-initialization-loss", "layer": "actual Beryl reference",
                                  "source_sha256": digest(signed_path), "detected": True,
                                  "program_outcome": "successful_return", "comparison": "binary32_observation_mismatch"})
        check("actual Beryl assertion fixtures reject ordering, cadence, premature commits, extra guards and shared reentry state")
        if args.native:
            native = run_test(None, native=True)
            if native.get("status") == "success":
                record["capabilities"]["native"] = "success"
                check("explicit native candidate executed and matched reference event stream")
            else:
                record["capabilities"]["native"] = native.get("native_status", "failure")
                record["status"] = "incomplete"
                record["native_result"] = native
        record["inputs_unchanged"] = all(digest(ROOT / name) == value for name, value in record["inputs"].items())
        if not record["inputs_unchanged"] or digest(compiler) != record["compiler"]["sha256"]:
            raise AssertionError("input/compiler identity changed during verification")
        record["status"] = "success" if record["status"] == "running" else record["status"]
        record["success_means"] = "bounded scripted lifecycle decisions and exact Beryl reference replay; no engine, deployment or complete tablet claim"
        record["trace_receipt"] = {"case_ids": record["case_ids"], "case_count": len(cases),
                                   "ordered_record_count": record["ordered_records"],
                                   "service_call_count": record["service_calls"],
                                   "next_call_count": record["next_calls"], "sha256": digest(path / "traces.json")}
        record["artifacts"] = [{"path": str(path / name), "sha256": digest(path / name)} for name in
                               ("cases.json", "traces.json", "replay.be", "expected-f32-bits.json")]
    except BaseException as exc:
        record["status"] = "timeout" if isinstance(exc, subprocess.TimeoutExpired) else "startup_failure" if isinstance(exc, OSError) else "cancelled" if isinstance(exc, KeyboardInterrupt) else "failure"
        record["error"] = {"type": type(exc).__name__, "message": str(exc),
                           "source_trap_claimed": False,
                           "scope": "harness_or_fixture_check; retained compiler receipts separately identify program outcomes"}
        raise
    finally:
        dump(path / "results.json", record)
        print("Receipt: " + str(path / "results.json"), flush=True)
    return 0 if record["status"] == "success" else 3


if __name__ == "__main__":
    sys.exit(main())
