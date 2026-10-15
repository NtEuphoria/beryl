"""Pure synthetic conformance/mutation checks; no engine, process or host launch."""
from __future__ import annotations
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import uuid

HERE = Path(__file__).resolve().parent
FROZEN_SOURCES = {p.name: p.read_bytes() for p in (HERE / "oracle.py", HERE / "verify_oracle.py")}
spec = importlib.util.spec_from_file_location("tablet_ui_original_oracle", HERE / "oracle.py")
oracle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(oracle)
IDENTITY = oracle.expected_identity("a" * 64, "b" * 64, "c" * 64)


class Fixture:
    """Explicit synthetic original methods, independently assembled row producer.

    This is a test producer, never used to manufacture observations in a native
    run. It imports field names/codec shape, but no checker evaluation code.
    """
    def __init__(self, *, has_map=False, first_enable=True, open_true=True,
                 dt_pair=(0.1, 0.2), reverse_deferred=False, deferred_retry=False):
        self.rows = []
        self.states = {i: dict(mode=0, accumulator=0.0, ui_present=False, ui_identity="none",
                               ui_open=False, has_map=False, root_present=False, root_generation=0,
                               screen_present=False, screen_enabled=False, screen_widget_present=False,
                               deleting=False) for i in (1, 2)}
        self.frame, self.action, self.invocation, self.after_super = 0, 0, 0, 0
        self.has_map, self.first_enable, self.open_true = has_map, first_enable, open_true
        self.dt_pair, self.reverse_deferred, self.deferred_retry = dt_pair, reverse_deferred, deferred_retry

    def append(self, values):
        self.rows.append(str(len(self.rows) + 1) + "|" + "|".join(values))

    def row(self, kind, phase, *, owner=1, code=0, invocation=0, dt=0.0,
            has_returned=False, returned=False):
        s = self.states[owner]
        v = dict(s, kind=kind, sequence=0, phase=phase, owner_token=owner, code=code,
                 invocation_id=invocation, dt=dt, has_returned=has_returned, returned=returned,
                 frame_index=self.frame, action_index=self.action)
        fields = []
        for name in oracle.MAIN_FIELDS[1:]:
            value = v[name]
            if type(value) is bool:
                fields.append("1" if value else "0")
            elif name in ("dt", "accumulator"):
                fields.append(format(value, ".8g"))
            else:
                fields.append(str(value))
        self.append(fields)

    def queue(self, event):
        s = self.states[1]
        self.append(["queue", event, "ui.1", str(int(s["root_present"])), str(s["root_generation"]),
                     str(int(s["ui_open"])), str(int(s["has_map"])), str(self.frame), str(self.action)])

    def service(self, code, mutate=None, returned=None, dt=0.0, owner=1):
        self.invocation += 1
        self.row("service", "enter", owner=owner, code=code, invocation=self.invocation, dt=dt)
        if mutate:
            mutate()
        self.row("service", "exit", owner=owner, code=code, invocation=self.invocation, dt=dt,
                 has_returned=returned is not None, returned=False if returned is None else returned)

    def enable(self):
        s = self.states[1]
        if not s["screen_present"]:
            self.service(10, lambda: s.update(screen_present=True))
        value = self.first_enable if self.action == 0 else True
        self.service(11, lambda: s.update(screen_enabled=value, screen_widget_present=value), value)

    def disable(self):
        s = self.states[1]
        if s["screen_present"]:
            self.service(12, lambda: s.update(screen_enabled=False))

    def focus(self):
        s = self.states[1]
        if s["mode"] != 1:
            return False
        if not s["ui_present"]:
            self.service(2, lambda: s.update(ui_present=True, ui_identity="ui.1"))
        def opening():
            if self.open_true:
                s.update(ui_open=True, root_present=True, root_generation=s["root_generation"] + 1)
                self.queue("enqueue.ReportRootSize")
                self.queue("enqueue.RefreshTerrain")
                s["has_map"] = self.has_map
        self.service(3, opening, self.open_true)
        if not self.open_true:
            return False
        self.service(4, returned=False)
        self.service(8)
        s["mode"] = 2
        self.disable()
        return True

    def unfocus(self):
        s = self.states[1]
        if s["mode"] != 2:
            return False
        self.service(13, lambda: s.update(ui_open=False, root_present=False, has_map=False))
        s["mode"] = 1
        self.enable()
        return True

    def held(self, value):
        s = self.states[1]
        if value:
            if s["mode"] == 0:
                s["mode"] = 1
            self.enable()
            return
        self.unfocus()
        s["mode"] = 0
        self.disable()

    def frame_call(self, dt, owner=1):
        self.frame += 1
        s = self.states[owner]
        self.row("frame", "before", owner=owner, dt=dt)
        if s["mode"] == 2 and s["ui_present"]:
            self.service(16, dt=dt)
            s["accumulator"] = struct.unpack("<f", struct.pack("<f", s["accumulator"] + dt))[0]
            if s["accumulator"] >= 0.25:
                s["accumulator"] = 0.0
                self.service(17, dt=dt)
        self.row("frame", "after", owner=owner, dt=dt)

    def execute(self):
        for owner in (1, 2):
            self.row("init", "before", owner=owner)
            self.row("init", "after", owner=owner, code=8)
        self.frame_call(0.02, 2)
        for index in range(7):
            self.row("action", "before")
            if index == 0:
                self.held(True); value = None
            elif index in (1, 2, 4):
                value = self.focus()
            elif index == 3:
                value = self.unfocus()
            elif index == 5:
                self.held(False); value = None
            else:
                self.held(True); value = self.focus()
            self.row("action", "after", has_returned=value is not None,
                     returned=False if value is None else value)
            self.action += 1
            if not self.open_true and index == 1:
                return self.rows
            if index in (1, 4):
                self.frame_call(self.dt_pair[0])
                self.frame_call(self.dt_pair[1])
                self.frame_call(0.03, 2)
                # Actual order can vary; method milestones do not claim FIFO.
                names = ["ReportRootSize", "RefreshTerrain"]
                if self.reverse_deferred:
                    names.reverse()
                for name in names:
                    self.queue("entry." + name)
                    if name == "RefreshTerrain" and self.deferred_retry:
                        self.queue("enqueue.RefreshTerrain")
                    self.queue("exit." + name)
            elif index in (2, 3, 5):
                self.frame_call(0.02)
        for owner in (2, 1):  # World teardown owner order is not specified.
            s = self.states[owner]
            s["deleting"] = True
            self.row("delete", "entry", owner=owner)
            if s["ui_present"]:
                self.service(13, lambda: s.update(ui_open=False, root_present=False, has_map=False), owner=owner)
            if s["screen_present"]:
                self.service(18, lambda: s.update(screen_enabled=False, screen_widget_present=False), owner=owner)
            self.row("service", "pre-super", owner=owner, code=19)
            self.after_super += 1
            self.append(["after-super", str(owner), str(self.after_super)])
        return self.rows


def envelope(rows):
    # Count the producer's literal records independently of checker evaluation.
    cells = [row.split("|") for row in rows]
    count = lambda kind, phase=None: sum(r[1] == kind and (phase is None or r[5] == phase) for r in cells)
    checksum = 0
    for row in rows:
        for value in row.encode("ascii") + b"\n":
            checksum = (checksum * 31 + value) % 1000003
    return dict(IDENTITY, status="complete", failure="", outside_domain=False,
                rows=rows, owner_count=2, action_count=7, executed=7,
                frame_count=count("frame", "before"), queue_count=count("queue"),
                init_count=count("init"), delete_count=count("delete"),
                presuper_count=count("service", "pre-super"), after_super_count=count("after-super"),
                row_count=len(rows), checksum=checksum, raw_bytes=sum(len(r) + 1 for r in rows),
                caseIds=list(oracle.CASE_IDS), first_progress_ready=True,
                reopen_progress_ready=True, final_focused=True)


def recode(rows):
    return [str(i) + "|" + r.split("|", 1)[1] for i, r in enumerate(rows, 1)]


def mutate(rows, predicate, field, value, *, occurrence=0):
    result = copy.deepcopy(rows)
    indexes = [i for i, row in enumerate(result) if predicate(row.split("|"))]
    require_index = indexes[occurrence]
    cells = result[require_index].split("|")
    fields = oracle.QUEUE_FIELDS if cells[1] == "queue" else oracle.MAIN_FIELDS
    cells[fields.index(field)] = value
    result[require_index] = "|".join(cells)
    return result


def main():
    cases = []
    def success(name, callback):
        callback(); cases.append(dict(case_id=name, expected="success", status="success"))
    def reject(name, callback, unavailable=False):
        try:
            callback()
        except oracle.AdmissionUnavailable:
            if not unavailable:
                raise AssertionError(name + " became unavailable instead of finding its mismatch")
        except oracle.VerificationFailure:
            if unavailable:
                raise AssertionError(name + " failed instead of truthfully becoming unavailable")
        else:
            raise AssertionError(name + " unexpectedly accepted")
        cases.append(dict(case_id=name, expected="unavailable" if unavailable else "failure", status="success"))

    rows = Fixture().execute()
    actual = envelope(rows)
    def analytical_totals():
        summary = oracle.validate_rows(rows, IDENTITY)
        totals = {name: summary[name] for name in ("actions", "frame_count", "queue_count", "service_invocations",
                                                 "init_count", "delete_count", "presuper_count", "after_super_count", "row_count")}
        expected = dict(actions=7, frame_count=10, queue_count=14, service_invocations=30, init_count=4,
                        delete_count=2, presuper_count=2, after_super_count=2, row_count=118)
        if totals != expected:
            raise AssertionError("Independent analytical totals differ: " + repr(totals))
    success("analytical.literal-counts", analytical_totals)
    success("complete.degraded-ui.native-shaped", lambda: oracle.validate(actual, IDENTITY))
    success("complete.map-present", lambda: oracle.validate_rows(Fixture(has_map=True).execute(), IDENTITY))
    success("complete.first-screen-enable-false", lambda: oracle.validate_rows(Fixture(first_enable=False).execute(), IDENTITY))
    success("complete.large-dt-once-no-catchup", lambda: oracle.validate_rows(Fixture(dt_pair=(0.9, 0.9)).execute(), IDENTITY))
    success("deferred-order-not-fifo", lambda: oracle.validate_rows(Fixture(reverse_deferred=True).execute(), IDENTITY))
    success("original-terrain-retry-milestone", lambda: oracle.validate_rows(Fixture(deferred_retry=True).execute(), IDENTITY))
    prefix = [r for r in rows if not (r.split("|")[1] in ("delete", "after-super") or
                                     (r.split("|")[1] == "service" and r.split("|")[22] == "1"))]
    success("complete-callback-prefix", lambda: oracle.validate_rows(prefix, IDENTITY, False))
    false_rows = Fixture(open_true=False).execute()
    success("actual-false-open-prefix", lambda: oracle.validate_rows(false_rows, IDENTITY, False))
    reject("actual-false-open-unavailable", lambda: oracle.validate_rows(false_rows, IDENTITY), True)
    reject("printed-threshold-exactness-unavailable", lambda: oracle.validate_rows(Fixture(dt_pair=(0.125, 0.125)).execute(), IDENTITY), True)

    # Mutants alter independently constructed observation data, not the checker.
    reject("partial-final-callback", lambda: oracle.validate_rows(rows[:-1], IDENTITY))
    reject("duplicate-sequence", lambda: oracle.validate_rows(rows[:5] + [rows[4]] + rows[5:], IDENTITY))
    reject("missing-row-resealed", lambda: oracle.validate_rows(recode(rows[:6] + rows[7:]), IDENTITY))
    reject("manual-frame-kind", lambda: oracle.validate_rows(mutate(rows, lambda c:c[1] == "frame", "kind", "manual-frame"), IDENTITY))
    reject("bool-column-2", lambda: oracle.validate_rows(mutate(rows, lambda c:c[1] == "action", "has_returned", "2"), IDENTITY))
    reject("counter-gap", lambda: oracle.validate_rows(mutate(rows, lambda c:c[1] == "frame", "frame_index", "100"), IDENTITY))
    reject("nonfinite-dt", lambda: oracle.validate_rows(mutate(rows, lambda c:c[1] == "frame", "dt", "NaN"), IDENTITY))
    reject("dt-domain", lambda: oracle.validate_rows(mutate(rows, lambda c:c[1] == "frame", "dt", "1.1"), IDENTITY))
    reject("owner2-ui", lambda: oracle.validate_rows(mutate(rows, lambda c:c[1] == "frame" and c[2] == "2", "ui_present", "1"), IDENTITY))
    reject("wrong-init-mask", lambda: oracle.validate_rows(mutate(rows, lambda c:c[1] == "init" and c[5] == "after", "code", "0"), IDENTITY))
    reject("wrong-focus-return", lambda: oracle.validate_rows(mutate(rows, lambda c:c[1] == "action" and c[5] == "after" and c[21] == "1", "returned", "0"), IDENTITY))
    reject("input-present", lambda: oracle.validate_rows(mutate(rows, lambda c:c[1] == "service" and c[4] == "4" and c[5] == "exit", "returned", "1"), IDENTITY))
    reject("open-true-no-root", lambda: oracle.validate_rows(mutate(rows, lambda c:c[1] == "service" and c[4] == "3" and c[5] == "exit", "root_present", "0"), IDENTITY))
    reject("marker-telemetry-order", lambda: oracle.validate_rows(mutate(rows, lambda c:c[1] == "service" and c[4] == "16", "code", "17"), IDENTITY))
    reject("telemetry-reset-missing", lambda: oracle.validate_rows(mutate(rows, lambda c:c[1] == "service" and c[4] == "17" and c[5] == "enter", "accumulator", "0.2"), IDENTITY))
    reject("closed-accumulator-lost", lambda: oracle.validate_rows(mutate(rows, lambda c:c[1] == "action" and c[5] == "after" and c[21] == "3", "accumulator", "0.1"), IDENTITY))
    reject("wrong-service-invocation", lambda: oracle.validate_rows(mutate(rows, lambda c:c[1] == "service" and c[5] == "exit", "invocation_id", "999"), IDENTITY))
    reject("marker-observes-premature-acc-update", lambda: oracle.validate_rows(mutate(rows, lambda c:c[1] == "service" and c[4] == "16" and c[5] == "enter", "accumulator", "0.1"), IDENTITY))
    reject("frame-pair-different-dt", lambda: oracle.validate_rows(mutate(rows, lambda c:c[1] == "frame" and c[5] == "after", "dt", "0.5"), IDENTITY))
    reject("service-pair-different-dt", lambda: oracle.validate_rows(mutate(rows, lambda c:c[1] == "service" and c[4] == "16" and c[5] == "exit", "dt", "0.5"), IDENTITY))
    reject("frame-pair-wrong-owner", lambda: oracle.validate_rows(mutate(rows, lambda c:c[1] == "frame" and c[5] == "after", "owner_token", "1"), IDENTITY))
    reject("service-exit-return-missing", lambda: oracle.validate_rows(mutate(rows, lambda c:c[1] == "service" and c[4] == "11" and c[5] == "exit", "has_returned", "0"), IDENTITY))
    reject("root-generation-skip", lambda: oracle.validate_rows(mutate(rows, lambda c:c[1] == "queue" and c[2].startswith("enqueue."), "root_generation", "4"), IDENTITY))
    reject("closed-ui-keeps-map", lambda: oracle.validate_rows(mutate(rows, lambda c:c[1] == "service" and c[4] == "13" and c[5] == "exit", "has_map", "1"), IDENTITY))
    reject("destroy-before-close", lambda: oracle.validate_rows(mutate(rows, lambda c:c[1] == "service" and c[4] == "13" and c[22] == "1", "code", "18"), IDENTITY))
    reject("destroy-keeps-widget", lambda: oracle.validate_rows(mutate(rows, lambda c:c[1] == "service" and c[4] == "18" and c[5] == "exit", "screen_widget_present", "1"), IDENTITY))
    reject("presuper-before-native-entry", lambda: oracle.validate_rows(mutate(rows, lambda c:c[1] == "delete", "kind", "service"), IDENTITY))
    reject("presuper-wrong-dt", lambda: oracle.validate_rows(mutate(rows, lambda c:c[1] == "service" and c[5] == "pre-super", "dt", "0.2"), IDENTITY))
    reject("queue-exit-without-entry", lambda: oracle.validate_rows(mutate(rows, lambda c:c[1] == "queue" and c[2].startswith("entry."), "event", "exit.ReportRootSize"), IDENTITY))
    reject("queue-origin-invented", lambda: oracle.validate_rows(mutate(rows, lambda c:c[1] == "queue", "event", "tick.RefreshTerrain"), IDENTITY))
    reject("queue-counter-gap", lambda: oracle.validate_rows(mutate(rows, lambda c:c[1] == "queue", "frame_index", "100"), IDENTITY))
    reject("queue-wrong-ui-identity", lambda: oracle.validate_rows(mutate(rows, lambda c:c[1] == "queue", "ui_identity", "ui.2"), IDENTITY))
    reject("unbounded-row", lambda: oracle.validate_rows(rows + ["x" * 1025], IDENTITY))
    reject("nonascii-row", lambda: oracle.validate_rows(rows + ["é"], IDENTITY))
    reject("rows-budget", lambda: oracle.validate_rows(["1|x"] * (oracle.MAX_ROWS + 1), IDENTITY))

    for name in ("token", "source_sha256", "source_contract_sha256", "profile", "schema_version", "row_count", "checksum",
                 "raw_bytes", "frame_count", "action_count", "executed", "delete_count", "presuper_count", "after_super_count"):
        changed = copy.deepcopy(actual)
        changed[name] = True if type(changed[name]) is int else "d" * 64
        reject("envelope." + name, lambda changed=changed: oracle.validate(changed, IDENTITY))
    for name in ("first_progress_ready", "reopen_progress_ready", "final_focused"):
        changed = copy.deepcopy(actual); changed[name] = False
        reject("envelope." + name, lambda changed=changed: oracle.validate(changed, IDENTITY))
    for name in ("caseIds", "rows"):
        changed = copy.deepcopy(actual); changed[name] = changed[name][:-1]
        reject("envelope.partial." + name, lambda changed=changed: oracle.validate(changed, IDENTITY))
    changed = copy.deepcopy(actual); changed["caseIds"][1] = changed["caseIds"][0]
    reject("envelope.duplicate-case", lambda: oracle.validate(changed, IDENTITY))
    for status in ("failure", "timeout", "cancelled", "unavailable", "pending"):
        changed = copy.deepcopy(actual); changed["status"] = status
        reject("envelope.status." + status, lambda changed=changed: oracle.validate(changed, IDENTITY))
    changed = copy.deepcopy(actual); changed["outside_domain"] = True
    reject("envelope.outside-domain", lambda: oracle.validate(changed, IDENTITY))
    changed = copy.deepcopy(actual); changed["failure"] = "launch failed"
    reject("envelope.harness-failure", lambda: oracle.validate(changed, IDENTITY))
    changed = copy.deepcopy(actual); changed["actions_ready"] = False
    reject("envelope.actions-completion-not-recorded", lambda: oracle.validate(changed, IDENTITY))

    # Global row ordering must survive an attacker recomputing sequence numbers
    # and checksums. Do not rely on a checksum as a semantic oracle.
    index = next(i for i, r in enumerate(rows) if r.split("|")[1] == "service" and r.split("|")[4] == "17")
    reject("extra-telemetry-pair-resealed", lambda: oracle.validate_rows(recode(rows[:index] + rows[index:index+2] + rows[index:]), IDENTITY))
    reject("missing-telemetry-pair-resealed", lambda: oracle.validate_rows(recode(rows[:index] + rows[index+2:]), IDENTITY))
    index = next(i for i, r in enumerate(rows) if r.split("|")[1] == "queue" and r.split("|")[2] == "entry.ReportRootSize")
    missing_progress = recode(rows[:index] + rows[index+2:])
    reject("missing-deferred-progress-resealed", lambda: oracle.validate_rows(missing_progress, IDENTITY))
    index = next(i for i, r in enumerate(rows) if r.split("|")[1] == "after-super")
    reject("duplicate-native-aftersuper-resealed", lambda: oracle.validate_rows(recode(rows[:index] + [rows[index]] + rows[index:]), IDENTITY))

    result = dict(schema_version=1, operation="tablet.ui.original-oracle.synthetic-verification", status="success",
                  scope="synthetic host observations; no native callbacks, compiler, PowerShell or engine executed",
                  expected=len(cases), passed=len(cases), cases=cases, synthetic_rows=len(rows),
                  checksum=oracle.checksum(rows), source_basis=oracle.SOURCE_BASIS,
                  sources={name: hashlib.sha256(data).hexdigest() for name, data in FROZEN_SOURCES.items()})
    for name, data in FROZEN_SOURCES.items():
        if (HERE / name).read_bytes() != data:
            raise AssertionError("Source changed during verification: " + name)
    out = HERE.parents[2] / "build" / ("tablet-ui-oracle-" + uuid.uuid4().hex)
    out.mkdir(parents=True, exist_ok=False)
    for name, data in FROZEN_SOURCES.items():
        (out / name).write_bytes(data)
    (out / "synthetic-complete.json").write_text(json.dumps(actual, sort_keys=True, ensure_ascii=True, allow_nan=False), encoding="utf8")
    result_path = out / "result.json"
    result_path.write_text(json.dumps(result, sort_keys=True, indent=2, ensure_ascii=True, allow_nan=False) + "\n", encoding="utf8")
    print(json.dumps(dict(status="success", expected=len(cases), passed=len(cases), result=str(result_path),
                          sha256=hashlib.sha256(result_path.read_bytes()).hexdigest()), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
