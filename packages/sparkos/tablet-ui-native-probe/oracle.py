"""Independent bounded checker for actual tablet UI/frame/teardown scalar rows.

The protocol is written directly from the retained handwritten component (not
Beryl continuation PCs, generated code, or instrumenter evaluation). Passing
these rows proves only their admitted ordered observations. Native callback
origin, immutable artifact identity, session ownership and raw RPC linkage are
separate transport obligations. Printed finite floats are compared with an
explicit tolerance; this is never an exact binary32 codec or allocation proof.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import struct
from pathlib import Path

PROFILE = "sparkos.tablet.ui-native.n1b-n3.source.v1"
CASE_IDS = ("n1b.held", "n1b.focus", "n1b.focus.repeated", "n1b.unfocus",
            "n1b.reopen", "n1b.stow", "n3.focused.before-teardown")
SOURCE_BASIS = {
    "component": {"path": "scripts/Game/SparkOSMesh/UI/SPK_TabletComponent.c",
                  "sha256": "1f15962cf67a8cc513d7068757e89360260016fadff1c8843719784acc94be3a",
                  "methods": "SyncScreen 47-60; Focus 69-100; Unfocus 102-113; SetHeld 117-131; OnPostInit 133-138; EOnFrame 150-167; OnDelete 171-182"},
    "ui": {"path": "scripts/Game/SparkOSMesh/UI/SPK_TabletUI.c",
           "sha256": "4efeab8cce793939d748506f34691aae9b0b47aa8b32ed568ece05accf28a05d",
           "methods": "Open 133-160; ReportRootSize 168-187; BuildWidgets 191-349; RefreshTerrain 1043-1060; Close 1110-1140"},
    "screen": {"path": "scripts/Game/SparkOSMesh/UI/SPK_ScreenRT.c",
               "sha256": "6328c5e86787b75c8cf949fcbd914c4fb137e17534a6158150bdba13818e942b",
               "methods": "Build 44-89; Enable 92-104; Disable 108-115; Destroy 126-137"},
}
MAX_ROWS, MAX_BYTES, MAX_FRAMES, MAX_QUEUE = 12288, 8388608, 2048, 64
MAX_INVOCATIONS = 8192
IDENTITY_KEYS = {"schema_version", "profile", "token", "source_sha256", "source_contract_sha256"}
MAIN_FIELDS = ("sequence", "kind", "owner_token", "invocation_id", "code", "phase", "mode",
               "accumulator", "ui_present", "ui_identity", "ui_open", "has_map", "root_present",
               "root_generation", "screen_present", "screen_enabled", "screen_widget_present",
               "has_returned", "returned", "dt", "frame_index", "action_index", "deleting")
QUEUE_FIELDS = ("sequence", "kind", "event", "ui_identity", "root_present", "root_generation",
                "ui_open", "has_map", "frame_index", "action_index")
INTEGER = re.compile(r"(?:0|[1-9][0-9]*)\Z")
FLOAT = re.compile(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?\Z")
BOOLEAN_FIELDS = {"ui_present", "ui_open", "has_map", "root_present", "screen_present",
                  "screen_enabled", "screen_widget_present", "has_returned", "returned", "deleting"}
TEXT_FIELDS = {"kind", "phase", "ui_identity", "event"}


class VerificationFailure(ValueError):
    """Incomplete/malformed observations or a demonstrated semantic mismatch."""


class AdmissionUnavailable(VerificationFailure):
    """Actual service outcome/rounded numeric data leaves the admitted domain."""


def require(condition, detail):
    if not condition:
        raise VerificationFailure(detail)


def f32(value):
    try:
        result = struct.unpack("<f", struct.pack("<f", value))[0]
    except (OverflowError, struct.error) as exc:
        raise VerificationFailure("Binary32 numerical domain exceeded") from exc
    require(math.isfinite(result), "Finite numerical domain required")
    return result


def tolerance(a, b=0.0):
    return max(1e-6, 1e-5 * max(abs(a), abs(b)))


def near(actual, expected):
    return abs(actual - expected) <= tolerance(actual, expected)


def checksum(rows):
    require(type(rows) is list and len(rows) <= MAX_ROWS, "Bounded literal row array required")
    value = 0
    total = 0
    for row in rows:
        require(type(row) is str and 0 < len(row) <= 1024 and
                all(32 <= ord(c) <= 126 for c in row), "Printable bounded ASCII rows required")
        total += len(row) + 1
        require(total <= MAX_BYTES, "Aggregate row budget exceeded")
        for byte in row.encode("ascii") + b"\n":
            value = (value * 31 + byte) % 1000003
    return value


def validate_identity(expected):
    require(type(expected) is dict and set(expected) == IDENTITY_KEYS, "Exact five-field expected identity required")
    require(type(expected["schema_version"]) is int and expected["schema_version"] == 1 and
            type(expected["profile"]) is str and expected["profile"] == PROFILE, "Wrong UI profile/schema")
    for name in ("token", "source_sha256", "source_contract_sha256"):
        require(type(expected[name]) is str and re.fullmatch(r"[0-9a-f]{64}", expected[name]), "Invalid expected " + name)


def expected_identity(token, source_sha256, source_contract_sha256):
    result = dict(schema_version=1, profile=PROFILE, token=token,
                  source_sha256=source_sha256, source_contract_sha256=source_contract_sha256)
    validate_identity(result)
    return result


def parse_rows(rows):
    checksum(rows)
    records = []
    for index, row in enumerate(rows, 1):
        values = row.split("|")
        require(len(values) >= 2, "Missing row kind")
        if values[1] == "queue":
            fields = QUEUE_FIELDS
        elif values[1] == "after-super":
            fields = ("sequence", "kind", "owner_token", "callback_count")
        else:
            require(values[1] in ("init", "action", "frame", "service", "delete"), "Unknown/manual callback row kind")
            fields = MAIN_FIELDS
        require(len(values) == len(fields), "Exact row-kind columns required")
        record = {}
        for name, text in zip(fields, values):
            if name in TEXT_FIELDS:
                record[name] = text
            elif name in BOOLEAN_FIELDS:
                require(text in ("0", "1"), "Exact Boolean column required: " + name)
                record[name] = text == "1"
            elif name in ("accumulator", "dt"):
                require(len(text) <= 48 and FLOAT.fullmatch(text), "Finite bounded float text required")
                value = float(text)
                require(math.isfinite(value), "Nonfinite float observation")
                record[name] = value
                record[name + "_text"] = text
            else:
                require(len(text) <= 10 and INTEGER.fullmatch(text), "Exact bounded unsigned integer column: " + name)
                value = int(text)
                require(value <= 2147483647, "Integer representation exceeded")
                record[name] = value
        require(record["sequence"] == index, "Missing/duplicate/reordered sequence")
        if record["kind"] not in ("queue", "after-super"):
            require(record["owner_token"] in (1, 2) and record["mode"] in (0, 1, 2), "Unregistered owner or mode")
            require(0 <= record["accumulator"] < 0.25 and 0 <= record["dt"] <= 1,
                    "Admitted finite accumulator/timestep domain exceeded")
            require(record["ui_identity"] == ("ui.1" if record["ui_present"] else "none"), "UI identity/presence mismatch")
            require(record["ui_open"] == record["root_present"], "IsOpen/root getter mismatch")
            require(record["ui_present"] or (not record["ui_open"] and not record["has_map"] and record["root_generation"] == 0),
                    "Absent UI has observations")
            require(record["screen_present"] or (not record["screen_enabled"] and not record["screen_widget_present"]),
                    "Absent screen has observations")
            require(not record["screen_enabled"] or record["screen_widget_present"], "Enabled screen without widget")
            require(record["root_generation"] <= 8 and record["frame_index"] <= MAX_FRAMES and record["action_index"] <= 7,
                    "Observation counter budget exceeded")
            require(record["invocation_id"] <= MAX_INVOCATIONS, "Service budget exceeded")
            require(record["has_returned"] or not record["returned"], "Void observation fabricated a return")
        records.append(record)
    return records


def _blank():
    return dict(mode=0, accumulator=0.0, ui_present=False, ui_identity="none", ui_open=False,
                has_map=False, root_present=False, root_generation=0, screen_present=False,
                screen_enabled=False, screen_widget_present=False, deleting=False)


class _OriginalProtocol:
    """Direct handwritten method expectations, evaluated against actual replies."""
    def __init__(self, records, require_complete):
        self.records, self.complete = records, require_complete
        self.states = {1: _blank(), 2: _blank()}
        self.initialized, self.deleted, self.after_super = set(), set(), set()
        self.actions, self.frames, self.invocations, self.queue_count = 0, 0, 0, 0
        self.init_count = self.presuper_count = 0
        self.active = None
        self.service = None
        self.queue_stack = []
        self.focus_frames = {2: 0, 5: 0}
        self.progress = {2: set(), 5: set()}
        self.open_outcomes = []
        self.numeric_uncertain = False
        self.refused_open = False

    def snapshot(self, row, owner, *, allow_ui_update=False):
        state = self.states[owner]
        require(row["owner_token"] == owner and row["mode"] == state["mode"] and
                row["deleting"] == state["deleting"], "Original mode/deletion/owner differs")
        require(near(row["accumulator"], state["accumulator"]), "Persistent telemetry accumulator differs")
        for key in ("ui_present", "ui_identity", "screen_present", "screen_enabled", "screen_widget_present"):
            require(row[key] == state[key], "Original observed storage/service state differs: " + key)
        if allow_ui_update:
            self.update_ui(row)
        for key in ("ui_open", "has_map", "root_present", "root_generation"):
            require(row[key] == state[key], "Original observed UI state differs: " + key)

    def update_ui(self, row):
        state = self.states[1]
        require(row["ui_identity"] == "ui.1" and row["ui_open"] == row["root_present"], "UI observation identity differs")
        require(row["root_generation"] in (state["root_generation"], state["root_generation"] + 1), "Root generation skipped/reversed")
        if row["root_generation"] > state["root_generation"]:
            require(row["root_present"] and not state["root_present"], "New root generation without construction")
        elif row["root_present"] and not state["root_present"]:
            raise AdmissionUnavailable("Reopened root identity did not acquire a new observed generation")
        for key in ("ui_open", "has_map", "root_present", "root_generation"):
            state[key] = row[key]

    def boundary(self, row):
        require(row["frame_index"] == self.frames and row["action_index"] == self.actions,
                "Action/frame counters changed outside their actual boundary")

    def action_plan(self, index):
        s = self.states[1]
        if index == 0:
            s["mode"] = 1
            return ([10] if not s["screen_present"] else []) + [11], None, 1
        if index in (1, 4):
            require(s["mode"] == 1, "Focus requires original HELD state")
            return ([2] if not s["ui_present"] else []) + [3], "open", None
        if index == 2:
            require(s["mode"] == 2, "Repeated Focus needs actual focused branch")
            return [], False, 2
        if index == 3:
            require(s["mode"] == 2, "Unfocus needs actual focused branch")
            return [13, 11], True, 1
        if index == 5:
            require(s["mode"] == 2, "Stow must unfocus first")
            return [13, 11, 12], None, 0
        require(index == 6 and s["mode"] == 0, "Final focus starts from STOWED")
        s["mode"] = 1
        return [11, 3], "open", None

    def next_mode(self, code):
        a = self.active
        if a["kind"] != "action":
            return
        index = a["index"]
        if code == 11 and index in (3, 5):
            self.states[1]["mode"] = 1
        if code == 12:
            self.states[1]["mode"] = 0 if index == 5 else 2

    def service_enter(self, row):
        require(self.active is not None and self.service is None, "Orphan/reentrant service entry")
        a = self.active
        require(a["remaining"] and row["code"] == a["remaining"][0] and row["owner_token"] == a["owner"],
                "Original service ordering or selected owner differs")
        self.next_mode(row["code"])
        self.invocations += 1
        require(row["invocation_id"] == self.invocations and not row["has_returned"], "Service invocation/entry return differs")
        self.snapshot(row, a["owner"])
        require(near(row["dt"], a["dt"]), "Service timestep differs from actual frame")
        self.service = row

    def service_exit(self, row):
        entry = self.service
        require(entry is not None and row["code"] == entry["code"] and
                row["invocation_id"] == entry["invocation_id"] and row["owner_token"] == entry["owner_token"],
                "Missing/reordered/mismatched actual service exit")
        a, code, owner = self.active, row["code"], row["owner_token"]
        s = self.states[owner]
        has_return = code in (3, 4, 11)
        require(row["has_returned"] == has_return, "Actual service return presence differs")
        if code == 2:
            s["ui_present"], s["ui_identity"] = True, "ui.1"
        elif code == 10:
            s["screen_present"] = True
        elif code == 11:
            if not row["returned"] and s["screen_widget_present"]:
                raise AdmissionUnavailable("Observed failed screen reuse leaves reviewed storage domain")
            s["screen_enabled"] = row["returned"]
            s["screen_widget_present"] = row["returned"] or s["screen_widget_present"]
        elif code == 12:
            s["screen_enabled"] = False
        elif code == 3:
            self.open_outcomes.append(row["returned"])
            if row["returned"]:
                require(row["ui_open"] and row["root_present"], "True Open lacks actual root")
                self.update_ui(row)
                a["remaining"].extend([4, 8, 12])
                a["returned"], a["final_mode"] = True, 2
            else:
                require(not row["ui_open"] and not row["root_present"] and not row["has_map"], "False Open fabricated a UI")
                self.update_ui(row)
                a["returned"], a["final_mode"] = False, 1
                self.refused_open = True
        elif code == 4:
            require(row["returned"] is False, "Input-free domain violated by actual input lookup")
        elif code == 13:
            s["ui_open"] = s["root_present"] = s["has_map"] = False
        elif code == 18:
            s["screen_enabled"] = s["screen_widget_present"] = False
        self.snapshot(row, owner)
        require(near(row["dt"], a["dt"]), "Service exit timestep differs")
        a["remaining"].pop(0)
        self.service = None
        # Markers observe the old accumulator; its binary32 update occurs only
        # after the returned marker operation, before telemetry/reset checks.
        if a["kind"] == "frame" and code == 16:
            new_value = f32(f32(s["accumulator"]) + f32(a["dt"]))
            uncertainty = tolerance(s["accumulator"]) + tolerance(a["dt"]) + tolerance(new_value)
            if abs(new_value - 0.25) <= uncertainty:
                self.numeric_uncertain = True
                # The eventual actual trace selects the observed branch, but
                # this numeric decision is reported unavailable at completion.
                a["ambiguous"] = True
            elif new_value >= 0.25:
                s["accumulator"] = 0.0
                a["remaining"].append(17)
            else:
                s["accumulator"] = new_value

    def queue(self, row):
        self.boundary(row)
        self.queue_count += 1
        require(self.queue_count <= MAX_QUEUE and self.states[1]["ui_present"], "Queue budget/receiver mismatch")
        require(row["event"] in tuple(prefix + name for prefix in ("enqueue.", "entry.", "exit.")
                                      for name in ("ReportRootSize", "RefreshTerrain")), "Unknown queue observation")
        event, name = row["event"].split(".", 1)
        inside_open = self.service is not None and self.service["code"] == 3
        if event == "enqueue":
            require(inside_open or (name == "RefreshTerrain" and self.queue_stack and self.queue_stack[-1] == name),
                    "Queue enqueue without original Open/retry context")
            if inside_open:
                require(row["root_present"] and row["ui_open"], "Original BuildWidgets enqueue lacks root")
                self.update_ui(row)
        elif event == "entry":
            require(self.active is None and not self.queue_stack, "Deferred method interleaves synchronous operation")
            self.queue_stack.append(name)
        else:
            require(self.queue_stack and self.queue_stack.pop() == name, "Orphan/reordered deferred method exit")
            if self.actions in self.progress:
                self.progress[self.actions].add(name)
        s = self.states[1]
        require(row["ui_identity"] == "ui.1" and all(row[k] == s[k] for k in
                ("ui_open", "has_map", "root_present", "root_generation")), "Queue snapshot differs from observed UI state")

    def consume(self, row):
        kind = row["kind"]
        if kind == "queue":
            return self.queue(row)
        if kind == "after-super":
            owner = row["owner_token"]
            require(self.active is not None and self.active["kind"] == "delete" and
                    self.active["owner"] == owner and self.active["presuper"] and self.service is None and
                    not self.active["remaining"] and owner not in self.after_super,
                    "After-super scalar milestone precedes actual deletion/pre-super boundary")
            self.after_super.add(owner)
            require(row["callback_count"] == len(self.after_super), "After-super callback count differs")
            self.active = None
            return
        if kind == "frame" and row["phase"] == "before":
            require(row["frame_index"] == self.frames + 1 and row["action_index"] == self.actions,
                    "Missing/duplicate native frame counter")
        else:
            self.boundary(row)
        owner = row["owner_token"]
        if kind == "init":
            require(self.active is None and self.actions == 0 and self.frames == 0 and not row["has_returned"] and
                    near(row["dt"], 0) and row["invocation_id"] == 0, "Initialization outside native factory boundary")
            require(owner == self.init_count // 2 + 1 and row["phase"] == ("before" if self.init_count % 2 == 0 else "after"),
                    "Two-owner initialization order/cardinality differs")
            self.snapshot(row, owner)
            require(row["code"] == 0 if row["phase"] == "before" else (row["code"] & 8) != 0,
                    "FRAME initialization event mask differs")
            self.init_count += 1
            if row["phase"] == "after":
                self.initialized.add(owner)
            return
        require(owner in self.initialized and self.init_count == 4, "Observation before complete two-owner initialization")
        if kind == "service":
            if row["phase"] == "pre-super":
                require(self.active is not None and self.active["kind"] == "delete" and
                        self.active["owner"] == owner and not self.active["remaining"] and self.service is None and
                        row["code"] == 19 and row["invocation_id"] == 0 and not row["has_returned"] and
                        not self.active["presuper"] and near(row["dt"], 0),
                        "Superclass boundary before Close/Destroy or duplicated")
                self.snapshot(row, owner)
                self.active["presuper"] = True
                self.presuper_count += 1
                return
            require(row["phase"] in ("enter", "exit"), "Unknown service phase")
            if self.active is not None and self.active["kind"] == "frame" and self.active.get("ambiguous"):
                if row["phase"] == "enter" and row["code"] == 17 and not self.active["remaining"]:
                    self.states[owner]["accumulator"] = 0.0
                    self.active["remaining"].append(17)
            return self.service_enter(row) if row["phase"] == "enter" else self.service_exit(row)
        require(row["code"] == 0 and row["invocation_id"] == 0, "Callback/action fabricated service code")
        if kind == "action":
            require(owner == 1 and self.actions < 7 and near(row["dt"], 0), "Only seven selected-owner actions admitted")
            if row["phase"] == "before":
                require(self.active is None and not self.queue_stack and not row["has_returned"], "Action reentry or incomplete callback")
                self.snapshot(row, owner)
                if self.actions in (2, 5):
                    previous = 2 if self.actions == 2 else 5
                    if self.refused_open:
                        raise AdmissionUnavailable("Actual false Open leaves focused UI scenarios unavailable")
                    require(self.focus_frames[previous] >= 2 and self.progress[previous] == {"ReportRootSize", "RefreshTerrain"},
                            "Action advanced before actual native frame/deferred progress")
                plan, returned, final_mode = self.action_plan(self.actions)
                self.active = dict(kind="action", owner=owner, index=self.actions, remaining=plan,
                                   returned=returned, final_mode=final_mode, dt=0.0)
            else:
                require(row["phase"] == "after" and self.active is not None and self.active["kind"] == "action" and
                        not self.active["remaining"] and self.service is None, "Incomplete action/service outcome")
                a = self.active
                self.states[owner]["mode"] = a["final_mode"]
                expected_return = a["returned"]
                require(row["has_returned"] == (expected_return is not None) and
                        row["returned"] == (expected_return if expected_return is not None else False), "Original public return differs")
                self.snapshot(row, owner)
                self.actions += 1
                self.active = None
            return
        if kind == "frame":
            require(not row["has_returned"] and owner not in self.deleted, "Frame after deletion or invented return")
            if row["phase"] == "before":
                require(self.active is None and not self.queue_stack and self.frames < MAX_FRAMES, "Native frame reentry/budget exceeded")
                # Registry increments once immediately before the native entry.
                self.frames += 1
                require(row["frame_index"] == self.frames, "Native frame index differs")
                self.snapshot(row, owner)
                focused = self.states[owner]["mode"] == 2 and self.states[owner]["ui_present"]
                if focused and owner == 1 and self.actions in self.focus_frames:
                    self.focus_frames[self.actions] += 1
                self.active = dict(kind="frame", owner=owner, remaining=[16] if focused else [], dt=row["dt"])
            else:
                require(row["phase"] == "after" and self.active is not None and self.active["kind"] == "frame" and
                        self.active["owner"] == owner and not self.active["remaining"] and self.service is None and
                        near(row["dt"], self.active["dt"]), "Missing/reordered native frame completion")
                if self.active.get("ambiguous") and row["accumulator"] != 0:
                    self.states[owner]["accumulator"] = row["accumulator"]
                self.snapshot(row, owner)
                self.active = None
            return
        require(kind == "delete" and row["phase"] == "entry" and not row["has_returned"] and near(row["dt"], 0),
                "Only actual native deletion entry admitted")
        require(self.active is None and not self.queue_stack and owner not in self.deleted and self.actions == 7,
                "Deletion before complete actions, duplicate or reentrant")
        self.states[owner]["deleting"] = True
        self.snapshot(row, owner)
        self.deleted.add(owner)
        s = self.states[owner]
        self.active = dict(kind="delete", owner=owner, remaining=([13] if s["ui_present"] else []) +
                           ([18] if s["screen_present"] else []), dt=0.0, presuper=False)

    def run(self):
        for row in self.records:
            self.consume(row)
        require(self.active is None and self.service is None and not self.queue_stack, "Partial callback/service/deferred trace")
        require(self.init_count == 4, "Missing two-owner native initialization")
        if self.complete:
            if self.refused_open:
                raise AdmissionUnavailable("Actual false Open: complete focused UI/destruction gate unavailable")
            require(self.actions == 7 and self.deleted == self.after_super == {1, 2} and self.presuper_count == 2,
                    "Missing actions/native deletion/pre-super/after-super callbacks")
            require(self.states[1]["mode"] == 2 and self.states[2]["mode"] == 0 and
                    not self.states[1]["ui_open"] and not self.states[1]["screen_enabled"] and
                    not self.states[1]["screen_widget_present"], "Focused teardown observation differs")
        if self.numeric_uncertain:
            raise AdmissionUnavailable("Rounded finite text cannot establish a telemetry threshold decision")
        return dict(schema_version=1, status="success", verification="verified_ordered_scalar_observations",
                    profile=PROFILE, actions=self.actions, cases=list(CASE_IDS[:self.actions]),
                    row_count=len(self.records), frame_count=self.frames, service_invocations=self.invocations,
                    queue_count=self.queue_count, init_count=self.init_count, delete_count=len(self.deleted),
                    presuper_count=self.presuper_count, after_super_count=len(self.after_super),
                    first_progress_ready=self.focus_frames[2] >= 2 and len(self.progress[2]) == 2,
                    reopen_progress_ready=self.focus_frames[5] >= 2 and len(self.progress[5]) == 2,
                    final_focused=self.actions == 7 and self.states[1]["mode"] == 2,
                    open_results=self.open_outcomes, source_basis=SOURCE_BASIS,
                    numeric_encoding="rounded_finite_text_with_documented_tolerance",
                    numeric_tolerance="max(1e-6,1e-5*max(abs(actual),abs(expected)))",
                    native_origin="not_verified_by_this_checker", physical_release="unverified",
                    queue_claim="enqueue/method milestones only; no FIFO or per-enqueue origin",
                    input="absent by actual observed lookup", player_interaction="unverified",
                    pixels="unverified", multiplayer="unverified")


def validate_rows(rows, expected, require_complete=True):
    validate_identity(expected)
    require(type(require_complete) is bool, "Exact completion policy required")
    records = parse_rows(rows)
    return _OriginalProtocol(records, require_complete).run()


def validate(actual, expected, require_complete=True):
    """Validate additive native envelope; full RPC identity is transport-owned."""
    validate_identity(expected)
    require(type(actual) is dict, "Native UI envelope required")
    for name, value in expected.items():
        require(name in actual and type(actual[name]) is type(value) and actual[name] == value, "Stale UI identity: " + name)
    require(actual.get("status") in (("complete",) if require_complete else ("pending", "complete")) and
            actual.get("failure") == "" and actual.get("outside_domain") is False, "Harness failure/incomplete domain is not semantic success")
    require("rows" in actual, "Missing actual scalar rows")
    summary = validate_rows(actual["rows"], expected, require_complete)
    counts = {"owner_count": 2, "action_count": summary["actions"], "executed": summary["actions"],
              "frame_count": summary["frame_count"], "queue_count": summary["queue_count"],
              "init_count": summary["init_count"], "delete_count": summary["delete_count"],
              "presuper_count": summary["presuper_count"], "after_super_count": summary["after_super_count"],
              "row_count": len(actual["rows"]), "checksum": checksum(actual["rows"]),
              "raw_bytes": sum(len(row) + 1 for row in actual["rows"])}
    for name, value in counts.items():
        require(type(actual.get(name)) is int and actual[name] == value, "Exact completion count differs: " + name)
    require(type(actual.get("caseIds")) is list and actual["caseIds"] == summary["cases"], "Missing/duplicate/reordered action cases")
    for name in ("first_progress_ready", "reopen_progress_ready", "final_focused"):
        require(type(actual.get(name)) is bool and actual[name] == summary[name], "Actual progress flag differs: " + name)
    if "actions_ready" in actual:
        require(type(actual["actions_ready"]) is bool and actual["actions_ready"] ==
                (summary["actions"] == 7 and summary["first_progress_ready"] and summary["reopen_progress_ready"]),
                "Action completion flag differs from recorded progress")
    return summary


def _json(path):
    with Path(path).open("rb") as stream:
        data = stream.read(MAX_BYTES + 1)
    require(len(data) <= MAX_BYTES, "JSON input budget exceeded")
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "Duplicate JSON field")
            result[key] = value
        return result
    try:
        return json.loads(data, object_pairs_hook=pairs,
                          parse_constant=lambda value: (_ for _ in ()).throw(VerificationFailure("Nonfinite JSON")))
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise VerificationFailure("Invalid bounded JSON") from exc


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected", required=True)
    parser.add_argument("--verify", required=True)
    parser.add_argument("--prefix", action="store_true", help="Validate a complete callback prefix; not a release gate")
    args = parser.parse_args()
    try:
        result = validate(_json(args.verify), _json(args.expected), not args.prefix)
        print(json.dumps(result, sort_keys=True, ensure_ascii=True, allow_nan=False))
        return 0
    except AdmissionUnavailable as exc:
        print(json.dumps(dict(status="unavailable", detail=str(exc), profile=PROFILE)))
        return 2
    except VerificationFailure as exc:
        print(json.dumps(dict(status="failure", detail=str(exc), profile=PROFILE)))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
