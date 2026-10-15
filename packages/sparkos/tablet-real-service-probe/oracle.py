"""Independent, bounded original-public-method oracle for planned N1a.

No Beryl continuation execution, engine calls, process operations, or fake service
replies for a native run. ``evaluate`` creates explicitly synthetic fixtures.
``validate`` consumes captured service outcomes within the contract's live,
non-reentrant domain. Native origin and transport remain separate obligations.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path

PROFILE = "sparkos.tablet.real-services.n1a.source.v1"
CASE_IDS = (
    "n1a.focus-refused.stowed", "n1a.held.first", "n1a.held.repeated",
    "n1a.unfocus-refused.held", "n1a.stow", "n1a.stow.repeated",
    "n1a.independent-state",
)
TOKENS = {"owner1": "owner.1", "owner2": "owner.2", "state1": "state.1",
          "state2": "state.2", "screen1": "screen.1", "widget1": "widget.1"}
IDENTITY_KEYS = {"schema_version", "profile", "token", "source_sha256",
                 "source_contract_sha256"}
COMPLETE_KEYS = IDENTITY_KEYS | {"status", "failure", "executed", "failures",
    "caseIds", "record_count", "service_event_count", "checksum", "records"}
SNAPSHOT_KEYS = {"owner", "state", "mode", "accumulator", "ui", "screen",
                 "screen_enabled", "widget"}
EVENT_KEYS = {"sequence", "kind", "invocation_id", "owner", "state", "screen",
              "mode", "accumulator", "argument_owner", "returned", "enabled", "widget"}
RECORD_KEYS = {"case_id", "action", "arguments", "before", "services", "outcome", "after"}
FLOAT_TEXT = re.compile(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?\Z")
MAX_INPUT = 2 * 1024 * 1024


class VerificationFailure(ValueError):
    """A typed-record contract or semantic comparison failure, not a source trap."""


class AdmissionUnavailable(VerificationFailure):
    """The observed widget lifetime leaves the selected comparison domain."""


def canonical(value):
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                          allow_nan=False).encode("ascii")
    except (ValueError, TypeError, RecursionError) as exc:
        raise VerificationFailure("Malformed typed-record serialization") from exc


def checksum(records):
    total = 0
    for record in records:
        for byte in canonical(record) + b"\n":
            total = (total * 31 + byte) % 1000003
    return total


def _require(condition, detail):
    if not condition:
        raise VerificationFailure(detail)


def _keys(value, expected, detail):
    _require(type(value) is dict and set(value) == expected, detail)


def _hash(value):
    return type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def expected_identity(token, source_sha256, source_contract_sha256):
    value = dict(schema_version=1, profile=PROFILE, token=token,
                 source_sha256=source_sha256, source_contract_sha256=source_contract_sha256)
    validate_identity(value)
    return value


def validate_identity(value):
    _keys(value, IDENTITY_KEYS, "Expected identity must have exactly five fields")
    _require(type(value["schema_version"]) is int and value["schema_version"] == 1,
             "Expected schema must be exact integer 1")
    _require(value["profile"] == PROFILE and type(value["profile"]) is str, "Wrong N1a profile")
    for key in ("token", "source_sha256", "source_contract_sha256"):
        _require(_hash(value[key]), "Invalid identity: " + key)


def _zero(value):
    _require(type(value) is str and len(value) <= 48 and FLOAT_TEXT.fullmatch(value),
             "Accumulator must be bounded finite numeric text")
    try:
        number = Decimal(value)
    except InvalidOperation as exc:
        raise VerificationFailure("Malformed accumulator") from exc
    _require(number.is_finite() and number == 0, "N1a accumulator changed")
    return "0"


def _snapshot(value):
    _keys(value, SNAPSHOT_KEYS, "Unknown or missing snapshot field")
    _require(type(value["mode"]) is int and 0 <= value["mode"] <= 2, "Invalid snapshot mode")
    _require(value["owner"] in (TOKENS["owner1"], TOKENS["owner2"]) and
             value["state"] in (TOKENS["state1"], TOKENS["state2"]), "Unknown owner/state token")
    _require(value["ui"] is None, "UI is outside N1a")
    _require(value["screen"] in (None, TOKENS["screen1"]) and
             value["widget"] in (None, TOKENS["widget1"]), "Unknown service token")
    if value["screen"] is None:
        _require(value["screen_enabled"] is None and value["widget"] is None,
                 "Absent screen has service observations")
    else:
        _require(type(value["screen_enabled"]) is bool, "Screen flag must be Boolean")
    result = copy.deepcopy(value)
    result["accumulator"] = _zero(value["accumulator"])
    return result


def _event(value):
    _keys(value, EVENT_KEYS, "Unknown or missing service event field")
    _require(type(value["sequence"]) is int and 1 <= value["sequence"] <= 9,
             "Invalid service sequence")
    _require(type(value["kind"]) is str and value["kind"] in
             ("screen.create", "screen.enable.enter", "screen.enable.exit",
              "screen.disable.enter", "screen.disable.exit"), "Unknown adapter service event")
    if value["kind"] == "screen.create":
        _require(value["invocation_id"] is None, "Creation is not an invocation pair")
    else:
        _require(type(value["invocation_id"]) is int and 1 <= value["invocation_id"] <= 4,
                 "Invalid invocation-local identifier")
    _require(type(value["mode"]) is int and value["mode"] in (0, 1), "Invalid intermediate mode")
    _require(type(value["enabled"]) is bool, "Service flag must be Boolean")
    _require(value["widget"] is None or (type(value["widget"]) is str and value["widget"] == TOKENS["widget1"]),
             "Unknown or malformed service widget token")
    if value["kind"] == "screen.enable.exit":
        _require(type(value["returned"]) is bool, "Enable exit must record actual Boolean result")
    else:
        _require(value["returned"] is None, "Unexpected service return")
    result = copy.deepcopy(value)
    result["accumulator"] = _zero(value["accumulator"])
    return result


class _OriginalPublicLogic:
    """Direct model of the retained component methods; no continuation PCs."""
    def __init__(self, enable_results):
        _require(type(enable_results) is list and len(enable_results) == 2 and
                 all(type(v) is bool for v in enable_results), "Need two actual Enable results")
        if enable_results == [True, False]:
            raise AdmissionUnavailable("Observed failed reuse leaves the admitted widget-lifetime domain")
        self.enable_results = iter(enable_results)
        self.mode = 0
        self.screen = None
        self.enabled = None
        self.widget = None
        self.sequence = 0
        self.invocation = 0
        self.services = []

    def snapshots(self):
        return [dict(owner=TOKENS["owner1"], state=TOKENS["state1"], mode=self.mode,
                     accumulator="0", ui=None, screen=self.screen,
                     screen_enabled=self.enabled, widget=self.widget),
                dict(owner=TOKENS["owner2"], state=TOKENS["state2"], mode=0,
                     accumulator="0", ui=None, screen=None, screen_enabled=None, widget=None)]

    def event(self, kind, invocation_id=None, returned=None):
        self.sequence += 1
        self.services.append(dict(sequence=self.sequence, kind=kind, invocation_id=invocation_id,
            owner=TOKENS["owner1"], state=TOKENS["state1"], screen=self.screen,
            mode=self.mode, accumulator="0",
            argument_owner=TOKENS["owner1"] if kind.startswith("screen.enable.") else None,
            returned=returned, enabled=self.enabled, widget=self.widget))

    def sync_screen(self):
        if self.mode == 1:
            if self.screen is None:
                self.screen, self.enabled = TOKENS["screen1"], False
                self.event("screen.create")  # after allocation AND publication
            self.invocation += 1
            self.event("screen.enable.enter", self.invocation)
            returned = next(self.enable_results)
            # Retained SPK_ScreenRT: false is normal, true sets script flag/widget.
            # The component ignores this reply and leaves HELD unchanged.
            self.enabled = returned
            self.widget = TOKENS["widget1"] if returned else None
            self.event("screen.enable.exit", self.invocation, returned)
            return
        if self.screen is not None:
            self.invocation += 1
            self.event("screen.disable.enter", self.invocation)
            self.enabled = False
            self.event("screen.disable.exit", self.invocation)

    def focus(self):
        _require(self.mode != 1, "Successful Focus is outside N1a")
        return False

    def unfocus(self):
        _require(self.mode != 2, "Focused Unfocus is outside N1a")
        return False

    def set_held(self, held):
        if held:
            if self.mode == 0:
                self.mode = 1
            self.sync_screen()
            return
        self.unfocus()
        self.mode = 0
        self.sync_screen()


def evaluate(enable_results, expected):
    """Create a SYNTHETIC trace from original logic and selected normal outcomes."""
    validate_identity(expected)
    model = _OriginalPublicLogic(enable_results)
    actions = (("Focus", []), ("SetHeld", [True]), ("SetHeld", [True]),
               ("Unfocus", []), ("SetHeld", [False]), ("SetHeld", [False]), ("Observe", []))
    records = []
    for case_id, (action, arguments) in zip(CASE_IDS, actions):
        before = model.snapshots()
        model.services = []
        if action == "Focus":
            returned = model.focus()
        elif action == "Unfocus":
            returned = model.unfocus()
        elif action == "SetHeld":
            returned = model.set_held(arguments[0])
        else:
            returned = None
        records.append(dict(case_id=case_id, action=action, arguments=arguments, before=before,
            services=copy.deepcopy(model.services), outcome={"kind": "return", "value": returned},
            after=model.snapshots()))
    result = dict(expected, status="complete", failure=None, executed=7, failures=0,
                  caseIds=list(CASE_IDS), record_count=7, service_event_count=9,
                  checksum=checksum(records), records=records)
    return result


def _typed_equal(actual, expected):
    if type(actual) is not type(expected):
        return False
    if type(expected) is dict:
        return set(actual) == set(expected) and all(_typed_equal(actual[k], expected[k]) for k in expected)
    if type(expected) is list:
        return len(actual) == len(expected) and all(_typed_equal(a, b) for a, b in zip(actual, expected))
    return actual == expected


def validate(actual, expected):
    """Verify complete typed observations; this does not verify their native origin."""
    validate_identity(expected)
    _keys(actual, COMPLETE_KEYS, "Unknown or missing completion field")
    _require(_typed_equal({key: actual[key] for key in IDENTITY_KEYS}, expected), "Stale source/token/profile")
    _require(actual["status"] == "complete" and type(actual["status"]) is str and
             actual["failure"] is None, "Harness or incomplete outcome is not a semantic return")
    for key, number in (("executed", 7), ("failures", 0), ("record_count", 7), ("service_event_count", 9)):
        _require(type(actual[key]) is int and actual[key] == number, "Wrong exact completion count: " + key)
    _require(_typed_equal(actual["caseIds"], list(CASE_IDS)), "Missing/duplicate/unknown/reordered case")
    _require(type(actual["records"]) is list and len(actual["records"]) == 7, "Incomplete record set")
    _require(type(actual["checksum"]) is int and 0 <= actual["checksum"] < 1000003 and
             checksum(actual["records"]) == actual["checksum"], "Corrupt typed-record checksum")
    normalized = copy.deepcopy(actual)
    outcomes = []
    for index, record in enumerate(actual["records"]):
        _keys(record, RECORD_KEYS, "Unknown or missing action record field")
        _require(record["case_id"] == CASE_IDS[index], "Action records changed order or identity")
        for boundary in ("before", "after"):
            _require(type(record[boundary]) is list and len(record[boundary]) == 2,
                     "Both owners must be observed at each action boundary")
            normalized["records"][index][boundary] = [_snapshot(v) for v in record[boundary]]
        _require(type(record["services"]) is list and len(record["services"]) <= 3,
                 "Unbounded or missing service records")
        normalized["records"][index]["services"] = [_event(v) for v in record["services"]]
        _keys(record["outcome"], {"kind", "value"}, "Malformed public outcome")
        _require(record["outcome"]["kind"] == "return", "Trap/timeout is not a normal public return")
        if index in (1, 2):
            exits = [v for v in record["services"] if v["kind"] == "screen.enable.exit"]
            _require(len(exits) == 1, "One actual Enable exit is required per HELD action")
            outcomes.append(exits[0]["returned"])
    # Validate structure/order/identity BEFORE a lifetime-domain classification;
    # a reordered creation/exit must not masquerade as external widget loss.
    structural_reference = evaluate([True, True], expected)
    event_structure = {"sequence", "kind", "invocation_id", "owner", "state", "screen",
                       "mode", "accumulator", "argument_owner"}
    snapshot_structure = {"owner", "state", "mode", "accumulator", "ui", "screen"}
    for actual_record, reference_record in zip(normalized["records"], structural_reference["records"]):
        for key in ("case_id", "action", "arguments", "outcome"):
            _require(_typed_equal(actual_record[key], reference_record[key]), "Public action/outcome differs")
        _require(len(actual_record["services"]) == len(reference_record["services"]), "Service count differs")
        for a, b in zip(actual_record["services"], reference_record["services"]):
            _require(_typed_equal({k: a[k] for k in event_structure}, {k: b[k] for k in event_structure}),
                     "Service order/intermediate state/identity differs")
        for boundary in ("before", "after"):
            for a, b in zip(actual_record[boundary], reference_record[boundary]):
                _require(_typed_equal({k: a[k] for k in snapshot_structure}, {k: b[k] for k in snapshot_structure}),
                         "Boundary state/identity differs")
    reference = evaluate(outcomes, expected)
    previously_seen_widget = None
    for record in normalized["records"]:
        views = [record["before"][0]] + record["services"] + [record["after"][0]]
        for view in views:
            widget = view["widget"]
            if previously_seen_widget is not None and widget != previously_seen_widget:
                raise AdmissionUnavailable("Observed widget loss/replacement leaves the admitted lifetime domain")
            if widget is not None:
                previously_seen_widget = widget
    normalized["checksum"] = checksum(normalized["records"])
    _require(_typed_equal(normalized, reference), "Original-source ordered state/service comparison differs")
    return dict(schema_version=1, status="success", verification="verified_typed_observations",
                profile=PROFILE, cases=7, service_events=9, enable_results=outcomes,
                native_origin="not_verified_by_this_checker", numeric_encoding="rounded_zero_only",
                screen_availability="observed_true" if any(outcomes) else "not_observed",
                binding="unverified", pixels="unverified", normalized_records=normalized["records"])


def _json(path):
    with Path(path).open("rb") as stream:
        data = stream.read(MAX_INPUT + 1)
    _require(len(data) <= MAX_INPUT, "Input exceeds 2 MiB")
    def pairs(rows):
        value = {}
        for key, item in rows:
            _require(key not in value, "Duplicate JSON field")
            value[key] = item
        return value
    try:
        return json.loads(data, object_pairs_hook=pairs,
                          parse_constant=lambda value: (_ for _ in ()).throw(VerificationFailure("Nonfinite JSON")))
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise VerificationFailure("Invalid bounded JSON") from exc


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected", required=True, help="Exact five-field expected identity JSON")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--verify", help="Typed observation completion JSON; no execution")
    group.add_argument("--synthetic", choices=("FF", "FT", "TT"), help="Generate explicitly synthetic fixture")
    args = parser.parse_args()
    try:
        expected = _json(args.expected)
        if args.synthetic:
            result = {"scope": "synthetic source oracle; engine not run",
                      "completion": evaluate([v == "T" for v in args.synthetic], expected)}
        else:
            result = validate(_json(args.verify), expected)
        print(json.dumps(result, sort_keys=True, ensure_ascii=True, allow_nan=False))
        return 0
    except AdmissionUnavailable as exc:
        print(json.dumps({"status": "unavailable", "verification": "outside_admitted_domain", "detail": str(exc)}))
        return 2
    except VerificationFailure as exc:
        print(json.dumps({"status": "failure", "verification": "failed", "detail": str(exc)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
