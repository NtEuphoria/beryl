"""Predeclared pure ASCII codec fixtures; no hosts/native processes/engine."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import sys
import uuid
from pathlib import Path

sys.dont_write_bytecode = True
PACKAGE = Path(__file__).resolve().parent
ROOT = PACKAGE.parents[2]


def sha(value):
    return hashlib.sha256(value).hexdigest()


def main():
    out = ROOT / "build" / ("tablet-real-service-wire-" + uuid.uuid4().hex)
    out.mkdir()
    (out / "inputs").mkdir()
    (out / "cases").mkdir()
    receipt = {"schema_version": 1, "operation": "n1a_ascii_wire_fixture_validation", "status": "running",
               "scope": "pure Python synthetic wire/source reads only", "host": "not_run", "compiler": "not_run",
               "native_program": "not_run", "engine": "not_run", "process_signals": "not_run",
               "source_inputs": [], "expected_case_ids": [], "expected_cases": 0, "cases": []}
    def save():
        data = json.dumps(receipt, sort_keys=True, indent=2, ensure_ascii=True).encode("ascii") + b"\n"
        assert (out / "result.json").write_bytes(data) == len(data) and (out / "result.json").read_bytes() == data
    try:
        inputs = []
        for index, name in enumerate(("wire.py", "wire-contract.json", "verify_wire.py", "oracle.py", "contract.json")):
            path = PACKAGE / name
            data = path.read_bytes()
            retained = out / "inputs" / name
            assert retained.write_bytes(data) == len(data) and retained.read_bytes() == data
            inputs.append((path, data))
            receipt["source_inputs"].append({"path": path.as_posix(), "retained": retained.as_posix(),
                                            "bytes": len(data), "sha256": sha(data)})
        spec = importlib.util.spec_from_file_location("n1a_wire_codec", PACKAGE / "wire.py")
        wire = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(wire)
        oracle = wire._oracle()
        source_contract = json.loads((PACKAGE / "contract.json").read_bytes())
        typed_expected = oracle.expected_identity("a" * 64, sha(oracle.canonical(source_contract["source_basis"])),
                                                  sha((PACKAGE / "contract.json").read_bytes()))
        expected = wire.expected_identity(typed_expected, sha((PACKAGE / "wire-contract.json").read_bytes()))
        make = lambda branch="TT": wire.encode(oracle.evaluate([v == "T" for v in branch], typed_expected), expected)
        plans = []
        def add(case_id, action, scope="synthetic raw-wire validator"):
            assert case_id not in {v[0] for v in plans}
            plans.append((case_id, action, scope))
        def positive(case_id, branch="TT", zero_text=None):
            def run():
                typed = oracle.evaluate([v == "T" for v in branch], typed_expected)
                if zero_text is not None:
                    for record in typed["records"]:
                        for phase in ("before", "after"):
                            for view in record[phase]:
                                view["accumulator"] = zero_text
                        for event in record["services"]:
                            event["accumulator"] = zero_text
                    typed["checksum"] = oracle.checksum(typed["records"])
                raw = wire.encode(typed, expected)
                result = wire.decode(raw, expected)
                assert result["typed_completion"] == typed and result["raw_rows"] == raw["rows"]
                assert result["raw_checksum"] == raw["checksum"] and result["native_origin"] == "unverified"
                assert result["comparison"]["cases"] == 7 and len(raw["rows"]) == 44
                assert result["comparison"]["enable_results"] == [v == "T" for v in branch]
                return {"status": "success", "detected": "exact typed/raw roundtrip", "branch": branch,
                        "wire_checksum": raw["checksum"], "typed_checksum": typed["checksum"],
                        "raw_sha256": sha(oracle.canonical(raw))}
            add(case_id, run)
        def raw_sum(rows):
            total = 0
            for row in rows:
                for byte in row.encode("ascii") + b"\n":
                    total = (31 * total + byte) % 1000003
            return total
        def mutant(case_id, mutate, branch="TT", expected_outcome="failure", repair_checksum=True):
            def run():
                raw = make(branch)
                mutate(raw)
                if repair_checksum:
                    raw["checksum"] = raw_sum(raw["rows"])
                try:
                    wire.decode(raw, expected)
                except oracle.AdmissionUnavailable as exc:
                    assert expected_outcome == "unavailable", str(exc)
                    return {"status": "success", "detected": "outside_admitted_domain", "detail": str(exc)}
                except (wire.WireFailure, oracle.VerificationFailure) as exc:
                    assert expected_outcome == "failure", str(exc)
                    return {"status": "success", "detected": "malformed_or_mismatched_wire", "detail": str(exc),
                            "exception_type": type(exc).__name__}
                raise AssertionError("Deliberate wire mutant accepted")
            add(case_id, run)
        def field(row, column, value):
            def apply(raw):
                parts = raw["rows"][row].split("|")
                parts[column] = value
                raw["rows"][row] = "|".join(parts)
            return apply
        def top(key, value):
            return lambda raw: raw.__setitem__(key, value)

        for branch in ("FF", "FT", "TT"):
            positive("positive.roundtrip." + branch, branch)
        for index, text in enumerate(("-0", "0.000", "-0.0e-8")):
            positive("positive.rounded-zero-text." + str(index), zero_text=text)
        def analytical():
            raw = make("FT")
            assert raw["rows"][0] == "1|n1a.focus-refused.stowed|before|1|owner.1|state.1|0|0|none|none|none|none"
            assert raw["rows"][2] == "3|n1a.focus-refused.stowed|outcome|Focus|none|return|0"
            assert raw["rows"][7] == "8|n1a.held.first|event|1|screen.create|none|owner.1|state.1|screen.1|1|0|none|none|0|none"
            assert raw["rows"][10] == "11|n1a.held.first|outcome|SetHeld|1|return|void"
            assert raw["rows"][41] == "42|n1a.independent-state|outcome|Observe|none|return|void"
            assert [len(row.split("|")) for row in raw["rows"]].count(12) == 28
            assert [len(row.split("|")) for row in raw["rows"]].count(15) == 9
            assert [len(row.split("|")) for row in raw["rows"]].count(7) == 7
            assert raw_sum(raw["rows"]) == raw["checksum"]
            return {"status": "success", "detected": "literal ASCII column/order/count anchors"}
        add("positive.analytical-ascii-anchors", analytical, "independent literal wire anchors")
        def contract_check():
            contract = json.loads((PACKAGE / "wire-contract.json").read_bytes())
            assert contract["schema_version"] == 1 and type(contract["schema_version"]) is int
            assert contract["profile"] == wire.PROFILE and contract["typed_profile"] == oracle.PROFILE
            assert contract["source_contract_sha256"] == wire.SOURCE_CONTRACT_SHA256
            assert contract["cases"] == list(wire.CASE_IDS) and contract["service_event_counts"] == list(wire.EVENT_COUNTS)
            assert set(contract["identity_fields"]) == wire.IDENTITY_KEYS
            assert set(contract["completion_fields"]) == wire.COMPLETE_KEYS
            assert contract["limits"] == dict(rows=44, row_bytes=512, raw_bytes_including_lf=32768, accumulator_text_bytes=48)
            return {"status": "success", "detected": "exact source wire-contract and field registry"}
        add("positive.wire-contract-registry", contract_check, "source-only contract registry")

        for key in sorted(wire.COMPLETE_KEYS):
            mutant("envelope.missing." + key, lambda v, key=key: v.pop(key),
                   repair_checksum=key not in ("checksum", "rows"))
        for key in ("schema_version", "executed", "failures", "row_count", "checksum"):
            mutant("envelope.boolean-integer." + key, top(key, True), repair_checksum=key != "checksum")
        for key in ("token", "source_sha256", "source_contract_sha256", "wire_contract_sha256"):
            mutant("envelope.wrong-identity." + key, top(key, "b" * 64))
        mutant("envelope.typed-profile-substitution", top("profile", oracle.PROFILE))
        mutant("envelope.unknown-field", top("unknown", "field"))
        for status in ("pending", "ready", "timeout", "cancelled", "unavailable", "failure", "stale_input"):
            mutant("envelope.not-complete." + status, top("status", status))
        mutant("envelope.exception-not-normal-false", top("failure", "VM exception"))
        for key in ("executed", "row_count"):
            mutant("envelope.incomplete-count." + key, top(key, 0))
        mutant("envelope.failure-count", top("failures", 1))
        mutant("envelope.corrupt-checksum", top("checksum", -1), repair_checksum=False)
        mutant("envelope.rows-null", top("rows", None), repair_checksum=False)
        mutant("envelope.rows-string", top("rows", "[]"), repair_checksum=False)
        mutant("cases.missing", lambda v: v["caseIds"].pop())
        mutant("cases.duplicate", lambda v: v["caseIds"].__setitem__(6, v["caseIds"][0]))
        mutant("cases.unknown", lambda v: v["caseIds"].__setitem__(0, "unknown"))
        mutant("cases.order", lambda v: v["caseIds"].reverse())
        mutant("rows.missing", lambda v: v["rows"].pop())
        mutant("rows.extra", lambda v: v["rows"].append(v["rows"][-1]))
        mutant("rows.reordered", lambda v: v["rows"].reverse())
        mutant("rows.non-string", lambda v: v["rows"].__setitem__(0, 123), repair_checksum=False)
        mutant("rows.non-ascii", field(0, 4, "own\u00e9r.1"), repair_checksum=False)
        mutant("rows.newline", field(0, 4, "owner.1\n"))
        mutant("rows.nul", field(0, 4, "owner.1\0"))
        mutant("rows.empty", lambda v: v["rows"].__setitem__(0, ""))
        mutant("rows.too-long", lambda v: v["rows"].__setitem__(0, "x" * 513))
        mutant("row.truncated", lambda v: v["rows"].__setitem__(0, "|".join(v["rows"][0].split("|")[:-1])))
        mutant("row.extra-column", lambda v: v["rows"].__setitem__(0, v["rows"][0] + "|extra"))
        for value in ("01", "+1", "-1", "0", "2", "1.0", "true"):
            mutant("row.sequence." + value.replace("+", "plus").replace("-", "minus"), field(0, 0, value))
        mutant("row.wrong-case-id", field(0, 1, wire.CASE_IDS[1]))
        mutant("row.before-after-swap", field(0, 2, "after"))
        mutant("row.wrong-role", field(0, 3, "2"))
        mutant("row.unknown-owner", field(0, 4, "owner.3"))
        mutant("row.shared-state", field(1, 5, "state.1"))
        mutant("row.focused-mode", field(0, 6, "2"))
        mutant("row.no-owner", field(0, 4, "none"))
        mutant("row.no-state", field(0, 5, "none"))
        mutant("row.unexpected-ui", field(0, 8, "ui.1"))
        mutant("row.absent-screen-has-flag", field(0, 10, "0"))
        mutant("row.unknown-screen", field(5, 9, "screen.2"))
        mutant("row.malformed-widget", field(13, 11, "123"))
        for index, value in enumerate(("true", "false", "2", "01", "-0", "", "null")):
            mutant("bool.invalid-spelling." + str(index), field(11, 10, value))
        for index, value in enumerate(("1", "0.25", "NaN", "Infinity", "+0", "00", " 0", "0" * 49)):
            mutant("numeric.invalid-accumulator." + str(index), field(0, 7, value))
        mutant("event.unknown-kind", field(7, 4, "screen.build"))
        mutant("event.duplicate-service-sequence", field(15, 3, "3"))
        mutant("event.invocation-slot-overwritten", field(16, 5, "1"))
        mutant("event.noop-id-zero", field(8, 5, "0"))
        mutant("event.create-has-id", field(7, 5, "1"))
        mutant("event.before-held-publication", field(7, 9, "0"))
        mutant("event.disable-before-stowed", field(27, 9, "1"))
        mutant("event.wrong-owner-argument", field(8, 11, "owner.2"))
        mutant("event.create-has-return", field(7, 12, "1"))
        mutant("event.disable-has-result", field(28, 12, "1"))
        mutant("event.missing-enable-reply", field(9, 12, "none"))
        mutant("event.void-enable-reply", field(9, 12, "void"))
        mutant("event.false-result-not-flag", field(9, 13, "1"), branch="FF")
        mutant("event.failed-disable-flag", field(28, 13, "1"))
        mutant("event.widget-lost-admission", field(13, 11, "none"), expected_outcome="unavailable")
        mutant("event.malformed-widget-not-lifetime", field(16, 14, "123"))
        mutant("outcome.wrong-action", field(10, 3, "Focus"))
        mutant("outcome.wrong-held-argument", field(10, 4, "0"))
        mutant("outcome.missing-held-argument", field(10, 4, "none"))
        mutant("outcome.refused-focus-true", field(2, 6, "1"))
        mutant("outcome.false-not-void", field(10, 6, "0"))
        mutant("outcome.none-not-void", field(10, 6, "none"))
        mutant("outcome.focus-void", field(2, 6, "void"))
        for kind in ("timeout", "source_trap", "engine_exception"):
            mutant("outcome.kind." + kind, field(2, 5, kind))
        mutant("owner2.changed-at-final", field(40, 6, "1"))
        def tf(raw):
            field(16, 12, "0")(raw)
            for index in range(16, 44):
                parts = raw["rows"][index].split("|")
                if parts[2] == "event":
                    parts[13], parts[14] = "0", "none"
                elif parts[2] in ("before", "after") and parts[3] == "1":
                    parts[10], parts[11] = "0", "none"
                raw["rows"][index] = "|".join(parts)
        mutant("domain.TF-unavailable-after-structure", tf, expected_outcome="unavailable")
        def bad_structure_tf(raw):
            tf(raw)
            field(7, 9, "0")(raw)
        mutant("domain.TF-does-not-mask-order-mutation", bad_structure_tf)
        def expected_bad(case_id, change):
            def run():
                bad = copy.deepcopy(expected)
                change(bad)
                try:
                    wire.decode(make(), bad)
                except wire.WireFailure as exc:
                    return {"status": "success", "detected": "bad_expected_wire_identity", "detail": str(exc)}
                raise AssertionError("Bad expected identity accepted")
            add(case_id, run)
        expected_bad("expected.bool-schema", lambda v: v.__setitem__("schema_version", True))
        expected_bad("expected.wrong-profile", lambda v: v.__setitem__("profile", oracle.PROFILE))
        expected_bad("expected.unsupported-typed-contract", lambda v: v.__setitem__("source_contract_sha256", "b" * 64))
        expected_bad("expected.malformed-wire-hash", lambda v: v.__setitem__("wire_contract_sha256", "0x123"))
        def unchanged():
            assert all(path.read_bytes() == data for path, data in inputs)
            return {"status": "success", "detected": "all frozen current and retained sources unchanged"}
        add("source-postflight.unchanged", unchanged, "source preservation only")
        receipt["expected_identity"] = expected
        receipt["expected_case_ids"] = [row[0] for row in plans]
        receipt["expected_cases"] = len(plans)
        save()
        for index, (case_id, action, scope) in enumerate(plans):
            try:
                row = dict(action(), id=case_id, scope=scope)
            except BaseException as exc:
                row = dict(id=case_id, scope=scope, status="failure", exception_type=type(exc).__name__, detail=str(exc))
            receipt["cases"].append(row)
            data = json.dumps(row, sort_keys=True, indent=2).encode("ascii") + b"\n"
            path = out / "cases" / (f"{index:03d}.json")
            assert path.write_bytes(data) == len(data) and path.read_bytes() == data
        assert [v["id"] for v in receipt["cases"]] == receipt["expected_case_ids"]
        assert len(set(receipt["expected_case_ids"])) == len(plans)
        receipt["passed"] = sum(row["status"] == "success" for row in receipt["cases"])
        receipt["failed"] = len(plans) - receipt["passed"]
        receipt["status"] = "success" if receipt["failed"] == 0 else "failure"
    except BaseException as exc:
        receipt.update(status="failure", harness_error={"type": type(exc).__name__, "detail": str(exc)})
    finally:
        save()
    print(json.dumps({"result": (out / "result.json").as_posix(), "sha256": sha((out / "result.json").read_bytes()),
                      "status": receipt["status"], "passed": receipt.get("passed", 0),
                      "failed": receipt.get("failed", 0), "expected_cases": receipt["expected_cases"]}))
    return 0 if receipt["status"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
