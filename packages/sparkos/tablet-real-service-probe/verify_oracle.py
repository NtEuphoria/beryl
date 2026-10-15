"""Pure Python N1a fixture gate; no subprocess, host, compiler or engine calls."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import sys
import time
import uuid
from pathlib import Path

sys.dont_write_bytecode = True
PACKAGE = Path(__file__).resolve().parent
ROOT = PACKAGE.parents[2]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def load_oracle():
    spec = importlib.util.spec_from_file_location("n1a_original_oracle", PACKAGE / "oracle.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    started = time.time()
    output = ROOT / "build" / ("tablet-real-service-oracle-" + uuid.uuid4().hex)
    output.mkdir()
    (output / "cases").mkdir()
    (output / "inputs").mkdir()
    receipt = {"schema_version": 1, "operation": "n1a_independent_original_source_oracle",
               "status": "running", "scope": "pure Python synthetic records/source reads only",
               "engine": "not_run", "compiler": "not_run", "native_program": "not_run",
               "host": "not_run", "process_signals": "not_run", "production_edits": "not_run",
               "source_inputs": [], "cases": [], "expected_case_ids": [], "expected_cases": 0}

    def save():
        encoded = json.dumps(receipt, sort_keys=True, indent=2, ensure_ascii=True).encode("ascii") + b"\n"
        path = output / "result.json"
        assert path.write_bytes(encoded) == len(encoded)
        assert path.read_bytes() == encoded

    try:
        contract_bytes = (PACKAGE / "contract.json").read_bytes()
        contract = json.loads(contract_bytes)
        own_files = [PACKAGE / name for name in ("oracle.py", "contract.json", "README.md", "verify_oracle.py")]
        basis_files = [ROOT / row["path"] for row in contract["source_basis"]]
        source_data = []
        for index, path in enumerate(own_files + basis_files):
            data = path.read_bytes()
            retained = output / "inputs" / (str(index) + "-" + path.name)
            assert retained.write_bytes(data) == len(data) and retained.read_bytes() == data
            item = {"path": path.as_posix(), "bytes": len(data), "sha256": sha(data),
                    "retained": retained.as_posix()}
            receipt["source_inputs"].append(item)
            source_data.append((path, data))
        oracle = load_oracle()
        source_sha = sha(oracle.canonical(contract["source_basis"]))
        expected = oracle.expected_identity("a" * 64, source_sha, sha(contract_bytes))
        fixture = lambda branch="TT": oracle.evaluate([value == "T" for value in branch], expected)
        plans = []

        def add(case_id, action, scope="synthetic typed observation validation"):
            assert case_id not in {case[0] for case in plans}, "Duplicate planned ID"
            plans.append((case_id, action, scope))

        def positive(case_id, branch="TT", mutation=None):
            def run():
                value = fixture(branch)
                if mutation:
                    mutation(value)
                    value["checksum"] = oracle.checksum(value["records"])
                result = oracle.validate(value, expected)
                assert result["status"] == "success" and result["cases"] == 7
                return {"status": "success", "observation": result["verification"],
                        "enable_results": result["enable_results"], "completion_sha256": sha(oracle.canonical(value))}
            add(case_id, run)

        def mutant(case_id, mutation, branch="TT", outcome="failure", repair_checksum=True):
            def run():
                value = fixture(branch)
                mutation(value)
                if repair_checksum:
                    value["checksum"] = oracle.checksum(value["records"])
                try:
                    oracle.validate(value, expected)
                except oracle.AdmissionUnavailable as exc:
                    assert outcome == "unavailable", "Unexpected unavailable: " + str(exc)
                    return {"status": "success", "detected": "outside_admitted_domain", "detail": str(exc)}
                except oracle.VerificationFailure as exc:
                    assert outcome == "failure", "Expected domain unavailability: " + str(exc)
                    return {"status": "success", "detected": "verification_failure", "detail": str(exc)}
                raise AssertionError("Deliberate mutant accepted")
            add(case_id, run)

        def at(path, value):
            def mutate(record):
                cursor = record
                for key in path[:-1]:
                    cursor = cursor[key]
                cursor[path[-1]] = value
            return mutate

        def remove(path):
            def mutate(record):
                cursor = record
                for key in path[:-1]:
                    cursor = cursor[key]
                del cursor[path[-1]]
            return mutate

        for branch in ("FF", "FT", "TT"):
            positive("positive.normal-enable." + branch, branch)

        def anchors():
            actual = fixture("FT")
            assert actual["caseIds"] == [
                "n1a.focus-refused.stowed", "n1a.held.first", "n1a.held.repeated",
                "n1a.unfocus-refused.held", "n1a.stow", "n1a.stow.repeated", "n1a.independent-state"]
            assert [v["after"][0]["mode"] for v in actual["records"]] == [0, 1, 1, 1, 0, 0, 0]
            assert [v["outcome"]["value"] for v in actual["records"]] == [False, None, None, False, None, None, None]
            assert [len(v["services"]) for v in actual["records"]] == [0, 3, 2, 0, 2, 2, 0]
            events = [v for row in actual["records"] for v in row["services"]]
            assert [v["kind"] for v in events] == ["screen.create", "screen.enable.enter", "screen.enable.exit",
                "screen.enable.enter", "screen.enable.exit", "screen.disable.enter", "screen.disable.exit",
                "screen.disable.enter", "screen.disable.exit"]
            assert [v["sequence"] for v in events] == list(range(1, 10))
            assert [v["invocation_id"] for v in events] == [None, 1, 1, 2, 2, 3, 3, 4, 4]
            assert events[0]["mode"] == 1 and events[0]["widget"] is None and events[0]["enabled"] is False
            assert events[2]["returned"] is False and events[2]["mode"] == 1
            assert events[4]["returned"] is True and events[4]["widget"] == "widget.1"
            assert all(v["widget"] == "widget.1" for v in events[5:])
            assert all(v["after"][1]["mode"] == 0 and v["after"][1]["screen"] is None for v in actual["records"])
            return {"status": "success", "observed": "independent analytical state/order/pair anchors"}
        add("positive.analytical-anchors", anchors, "literal original-source analytical anchors")

        def contract_check():
            assert type(contract["schema_version"]) is int and contract["schema_version"] == 1
            assert contract["profile"] == oracle.PROFILE and contract["installed_scenario"] is False
            assert tuple(row["id"] for row in contract["cases"]) == oracle.CASE_IDS
            for key, expected_keys in (("completion_fields", oracle.COMPLETE_KEYS),
                ("identity_fields", oracle.IDENTITY_KEYS), ("record_fields", oracle.RECORD_KEYS),
                ("snapshot_fields", oracle.SNAPSHOT_KEYS), ("event_fields", oracle.EVENT_KEYS)):
                assert len(contract[key]) == len(set(contract[key])) and set(contract[key]) == expected_keys
            assert [row["service_events"] for row in contract["cases"]] == [0, 3, 2, 0, 2, 2, 0]
            return {"status": "success", "observed": "frozen typed contract agrees with independent checker"}
        add("positive.contract-field-case-registry", contract_check, "source contract consistency")

        for index, row in enumerate(contract["source_basis"]):
            def basis_check(index=index, row=row):
                data = source_data[4 + index][1]
                assert len(data) == row["bytes"] and sha(data) == row["sha256"]
                return {"status": "success", "source": row}
            add("source-basis." + str(index), basis_check, "actual immutable source hash, no execution")

        def all_zero(value, text):
            for row in value["records"]:
                for boundary in ("before", "after"):
                    for view in row[boundary]:
                        view["accumulator"] = text
                for view in row["services"]:
                    view["accumulator"] = text
        for index, text in enumerate(("0.0", "-0", "0e-3", "-0.0000E+20")):
            positive("positive.rounded-zero." + str(index), mutation=lambda v, text=text: all_zero(v, text))

        for key, value in (("schema_version", True), ("schema_version", 2), ("profile", "N0"),
                           ("token", "b" * 64), ("source_sha256", "b" * 64),
                           ("source_contract_sha256", "b" * 64)):
            suffix = "bool" if value is True else str(value)[:8]
            mutant("identity." + key + "." + suffix, at([key], value))
        for key in oracle.IDENTITY_KEYS:
            mutant("identity.missing." + key, remove([key]))
        for status in ("timeout", "cancelled", "unavailable", "failure", "stale_input", "running"):
            mutant("harness.status." + status, at(["status"], status))
        mutant("harness.error-not-return", at(["failure"], "Engine exception"))
        for key in ("executed", "failures", "record_count", "service_event_count", "checksum"):
            mutant("counts.boolean." + key, at([key], True), repair_checksum=key != "checksum")
        for key in ("executed", "record_count", "service_event_count"):
            mutant("counts.incomplete." + key, at([key], 0))
        mutant("counts.failure-one", at(["failures"], 1))
        mutant("checksum.corrupt", at(["checksum"], 1000002), repair_checksum=False)
        mutant("completion.unknown-field", at(["unknown"], 0))
        mutant("cases.missing", remove(["caseIds", 6]))
        mutant("cases.duplicate", at(["caseIds", 6], oracle.CASE_IDS[0]))
        mutant("cases.unknown", at(["caseIds", 0], "n1a.unknown"))
        mutant("cases.reordered", lambda v: v["caseIds"].reverse())
        mutant("records.missing", remove(["records", 6]))
        mutant("records.duplicate-id", at(["records", 6, "case_id"], oracle.CASE_IDS[0]))
        mutant("records.order", lambda v: v["records"].reverse())
        mutant("records.unknown-field", at(["records", 0, "unobserved"], 0))
        mutant("action.wrong-method", at(["records", 1, "action"], "Focus"))
        mutant("action.wrong-held", at(["records", 1, "arguments"], [False]))
        mutant("action.numeric-held", at(["records", 1, "arguments"], [1]))
        mutant("return.focus-true", at(["records", 0, "outcome", "value"], True))
        mutant("return.unfocus-true", at(["records", 3, "outcome", "value"], True))
        mutant("return.setheld-private-bool", at(["records", 1, "outcome", "value"], False))
        for kind in ("source_trap", "timeout", "engine_exception", "cancelled"):
            mutant("return.kind." + kind, at(["records", 0, "outcome", "kind"], kind))
        mutant("return.false-as-integer", at(["records", 0, "outcome", "value"], 0))

        for index in range(7):
            mutant("owner2.before-changed." + str(index), at(["records", index, "before", 1, "mode"], 1))
            mutant("owner2.after-changed." + str(index), at(["records", index, "after", 1, "screen"], "screen.1"))
        mutant("snapshot.other-owner-missing", remove(["records", 1, "before", 1]))
        mutant("snapshot.owner-order", lambda v: v["records"][1]["before"].reverse())
        mutant("snapshot.shared-state", at(["records", 1, "before", 1, "state"], "state.1"))
        mutant("snapshot.state-replacement", at(["records", 2, "after", 0, "state"], "state.2"))
        mutant("snapshot.mode-bool", at(["records", 0, "before", 0, "mode"], False))
        mutant("snapshot.focused-mode", at(["records", 2, "after", 0, "mode"], 2))
        mutant("snapshot.false-enable-reverts-held", at(["records", 1, "after", 0, "mode"], 0), branch="FF")
        mutant("snapshot.ui-appeared", at(["records", 1, "after", 0, "ui"], "ui.1"))
        mutant("snapshot.absent-screen-with-enabled", at(["records", 0, "before", 0, "screen_enabled"], False))
        mutant("snapshot.screen-flag-integer", at(["records", 1, "after", 0, "screen_enabled"], 1))
        mutant("snapshot.missing-accumulator", remove(["records", 0, "before", 0, "accumulator"]))
        for index, text in enumerate(("0.25", "NaN", "Infinity", "+0", "00", " 0", "0" * 49, 0, False)):
            mutant("snapshot.bad-accumulator." + str(index), at(["records", 2, "after", 0, "accumulator"], text))

        mutant("services.first-create-missing", remove(["records", 1, "services", 0]))
        mutant("services.repeated-enable-missing", at(["records", 2, "services"], []))
        mutant("services.repeated-disable-missing", at(["records", 5, "services"], []))
        mutant("services.refused-focus-extra", at(["records", 0, "services"], [fixture()["records"][1]["services"][0]]))
        mutant("services.refused-unfocus-extra", at(["records", 3, "services"], [fixture()["records"][4]["services"][0]]))
        mutant("services.reordered", lambda v: v["records"][1]["services"].reverse())
        mutant("services.extra-create", lambda v: v["records"][2]["services"].insert(0, copy.deepcopy(v["records"][1]["services"][0])))
        mutant("services.wrong-sequence", at(["records", 2, "services", 0, "sequence"], 3))
        mutant("services.bool-sequence", at(["records", 1, "services", 0, "sequence"], True))
        mutant("services.wrong-invocation", at(["records", 2, "services", 1, "invocation_id"], 1))
        mutant("services.shared-invocation-slot", at(["records", 2, "services", 0, "invocation_id"], 1))
        mutant("services.noop-hook-id-zero", at(["records", 1, "services", 1, "invocation_id"], 0))
        mutant("services.create-paired", at(["records", 1, "services", 0, "invocation_id"], 1))
        mutant("services.mode-before-held-publication", at(["records", 1, "services", 0, "mode"], 0))
        mutant("services.disable-before-stowed-publication", at(["records", 4, "services", 0, "mode"], 1))
        mutant("services.accumulator-changed", at(["records", 2, "services", 0, "accumulator"], "1"))
        mutant("services.wrong-owner-argument", at(["records", 1, "services", 1, "argument_owner"], "owner.2"))
        mutant("services.wrong-state", at(["records", 2, "services", 0, "state"], "state.2"))
        mutant("services.screen-replaced", at(["records", 2, "services", 0, "screen"], "screen.2"))
        mutant("services.create-build-inferred", at(["records", 1, "services", 0, "kind"], "screen.build"))
        mutant("services.return-not-boolean", at(["records", 1, "services", 2, "returned"], 1))
        mutant("services.inferred-disable-result", at(["records", 4, "services", 1, "returned"], True))
        mutant("services.false-result-became-success", at(["records", 1, "services", 2, "enabled"], True), branch="FF")
        mutant("services.flag-not-cleared", at(["records", 4, "services", 1, "enabled"], True))
        mutant("services.widget-lost", at(["records", 2, "before", 0, "widget"], None), outcome="unavailable")
        def tf(value):
            exit_event = value["records"][2]["services"][1]
            exit_event.update(returned=False, enabled=False, widget=None)
            value["records"][2]["after"][0].update(screen_enabled=False, widget=None)
        mutant("domain.failed-reuse.TF", tf, outcome="unavailable")

        def expected_bad(case_id, changes):
            def run():
                wrong = copy.deepcopy(expected)
                changes(wrong)
                try:
                    oracle.validate(fixture(), wrong)
                except oracle.VerificationFailure as exc:
                    return {"status": "success", "detected": "bad_expected_identity", "detail": str(exc)}
                raise AssertionError("Invalid expected identity accepted")
            add(case_id, run)
        expected_bad("expected.bool-schema", at(["schema_version"], True))
        expected_bad("expected.unknown-key", at(["unknown"], 0))
        expected_bad("expected.invalid-token", at(["token"], "address-0x123"))

        def source_unchanged():
            assert all(path.read_bytes() == data for path, data in source_data)
            return {"status": "success", "observed": "all eight current and retained inputs remain exact"}
        add("source-postflight.unchanged", source_unchanged, "source byte preservation")

        # Preserve the historical125 case IDs/order as a complete prefix.
        for name, widget in (("integer", 123), ("dict", {"value": "widget.1"}),
                             ("list", ["widget.1"]), ("unknown-string", "widget.2")):
            mutant("services.malformed-widget." + name,
                   at(["records", 2, "services", 1, "widget"], widget))

        receipt["expected_case_ids"] = [row[0] for row in plans]
        receipt["expected_cases"] = len(plans)
        receipt["expected_identity"] = expected
        receipt["semantic_cases"] = list(oracle.CASE_IDS)
        save()  # The case set is frozen before any action runs.
        for index, (case_id, action, scope) in enumerate(plans):
            try:
                result = action()
                row = dict(result, id=case_id, scope=scope)
            except BaseException as exc:
                row = {"id": case_id, "scope": scope, "status": "failure",
                       "exception_type": type(exc).__name__, "detail": str(exc)}
            receipt["cases"].append(row)
            encoded = json.dumps(row, sort_keys=True, ensure_ascii=True, indent=2).encode("ascii") + b"\n"
            case_path = output / "cases" / (f"{index:03d}.json")
            assert case_path.write_bytes(encoded) == len(encoded) and case_path.read_bytes() == encoded
        completed = [row["id"] for row in receipt["cases"]]
        assert completed == receipt["expected_case_ids"] and len(completed) == len(set(completed))
        receipt["passed"] = sum(row["status"] == "success" for row in receipt["cases"])
        receipt["failed"] = len(plans) - receipt["passed"]
        receipt["status"] = "success" if receipt["failed"] == 0 else "failure"
    except BaseException as exc:
        receipt.update(status="failure", harness_error={"type": type(exc).__name__, "detail": str(exc)})
    finally:
        receipt["elapsed_ms"] = int((time.time() - started) * 1000)
        save()
    print(json.dumps({"result": (output / "result.json").as_posix(), "sha256": sha((output / "result.json").read_bytes()),
                      "status": receipt["status"], "passed": receipt.get("passed", 0),
                      "failed": receipt.get("failed", 0), "expected_cases": receipt["expected_cases"]}))
    return 0 if receipt["status"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
