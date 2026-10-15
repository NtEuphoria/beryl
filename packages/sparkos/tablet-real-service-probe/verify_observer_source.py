"""Bounded source admission for the trusted N1a observer, never engine execution.

Checks the frozen template, logical field projection, and admitted call paths.
Deliberate source faults demonstrate containment checks; they are not native
semantic, lifetime, compilation, callback, or non-interference evidence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[3]
PACKAGE = Path(__file__).resolve().parent
OBSERVER = PACKAGE / "observer.c.in"
OBSERVER_SHA256 = "fe8b9b38f4b7e6470652affdca79275aa00166eda634656c0b83f9af6259af3e"
CONTRACT_SHA256 = "74aed85740e8d72b5c187eae9b537fffb921b90ec24ac0002500379897e8cd65"
ORIGINAL_SHA256 = "21479adf12a76a48ad7be9419e6e5047d663cce0ebee1341e5d8bfaf8d20d3c7"
HOOKS_SHA256 = "9efacf44be76da7b4a464dd66e8e5fa076c20c352144f1ffc48775e089c250e5"
INSTRUMENTER_SHA256 = "0754460a8ca606eb8ef7030ea234c3410400a4340c9ee720ac0117dd3249d1c4"
MAX_BYTES = 65536
CASE_IDS = (
    "positive.frozen-template", "positive.logical-fields", "positive.hook-read-path",
    "positive.native-init-order", "positive.public-action-order", "positive.owner-witnesses",
    "positive.bounded-identities", "positive.null-projection", "positive.placeholder-origins",
    "positive.original-and-hooks-unchanged", "negative.nonbytes", "negative.byte-budget",
    "negative.crlf", "negative.unbound-placeholder", "negative.snapshot-field",
    "negative.event-field", "negative.outcome-field", "negative.record-field",
    "negative.hook-get-owner", "negative.hook-get-game", "negative.hook-service-call",
    "negative.hook-public-action", "negative.hook-callback", "negative.state-write",
    "negative.shared-invocation-slot", "negative.manual-constructor", "negative.init-super-missing",
    "negative.init-super-duplicate", "negative.init-order", "negative.mask-write",
    "negative.owner-witness", "negative.world-witness", "negative.state-witness",
    "negative.independence-witness", "negative.native-init-guard", "negative.live-world-guard",
    "negative.returned-owner-guard", "negative.repeat-run-guard", "negative.both-before",
    "negative.both-after", "negative.action-order", "negative.duplicate-focus",
    "negative.forged-void-result", "negative.forged-enable-result", "negative.local-id-zero",
    "negative.event-budget", "negative.invocation-budget", "negative.record-budget",
    "negative.frame-override", "negative.delete-override", "negative.external-state-reset",
    "negative.hook-async", "negative.identity-replacement", "negative.omitted-final-count",
    "negative.outside-domain-classification", "negative.outside-domain-primary",
    "negative.unpinned-whitespace",
    "negative.strong-component-ref",
)


class SourceFailure(ValueError):
    pass


def _require(condition, detail):
    if not condition:
        raise SourceFailure(detail)


def _sha(value):
    return hashlib.sha256(value).hexdigest()


def _read(path):
    path = Path(path)
    _require(not path.is_symlink() and path.is_file(), "Required regular source file")
    with path.open("rb") as stream:
        value = stream.read(MAX_BYTES + 1)
    _require(len(value) <= MAX_BYTES, "Source byte budget exceeded")
    return value


def _mask(text):
    # Length-preserving token masking for brace/call inspection, not a language parser.
    pattern = r'//[^\n]*|/\*[\s\S]*?\*/|"(?:\\.|[^"\\])*"'
    return re.sub(pattern, lambda item: "".join("\n" if c == "\n" else " " for c in item[0]), text)


def _block(text, start):
    masked = _mask(text)
    depth = 0
    for index in range(start, len(masked)):
        if masked[index] == "{":
            depth += 1
        elif masked[index] == "}":
            depth -= 1
            if depth == 0:
                return text[start + 1:index]
    raise SourceFailure("Unbalanced source block")


def _body(text, name):
    pattern = r"(?m)^[ \t]*(?:(?:override|protected|static)[ \t]+)*[A-Za-z_@][A-Za-z0-9_@]*[ \t]+" + re.escape(name) + r"[ \t]*\([^;{}]*\)\s*\{"
    found = list(re.finditer(pattern, _mask(text)))
    _require(len(found) == 1, "Expected exactly one method: " + name)
    return _block(text, found[0].end() - 1)


def _fields(text, name):
    found = re.search(r"\bclass[ \t]+" + re.escape(name) + r"\s*\{", _mask(text))
    _require(found is not None, "Missing typed record class: " + name)
    body = _block(text, found.end() - 1)
    fields = []
    for line in body.splitlines():
        line = line.strip()
        if not line:
            continue
        field = re.fullmatch(r"(?:ref )?(?:array<[^;]+>|[A-Za-z_][A-Za-z0-9_]*) ([a-z_]+)(?: = \{\})?;", line)
        _require(field is not None, "Unexpected typed field declaration in " + name)
        fields.append(field[1])
    _require(len(fields) == len(set(fields)), "Duplicate typed field")
    return fields


def _calls(body):
    code = _mask(body)
    result = set()
    for found in re.finditer(r"\b([A-Za-z_][A-Za-z0-9_]*)[ \t]*\(", code):
        name = found[1]
        if name in {"if", "for", "while", "switch"}:
            continue
        if re.search(r"\bnew[ \t]+$", code[:found.start()]):
            continue
        result.add(name)
    return result


def _contains(body, text, detail):
    _require(text in body, detail)


def validate_source(value, *, pin=True):
    _require(type(value) is bytes, "Observer must be exact bytes")
    _require(0 < len(value) <= MAX_BYTES, "Observer byte budget exceeded")
    _require(b"\r" not in value and b"\0" not in value, "Observer requires LF text without NUL")
    try:
        text = value.decode("utf8")
    except UnicodeError as exc:
        raise SourceFailure("Observer is not UTF-8") from exc
    _require(set(re.findall(r"@[A-Z_]+@", text)) == {"@STATE@", "@MODE@", "@ACCUMULATOR@"}, "Unknown/missing trusted placeholder")
    expected_fields = {
        "SPK_BerylN1Snapshot": ["owner", "state", "mode", "accumulator", "ui", "screen", "screen_enabled", "widget"],
        "SPK_BerylN1ServiceEvent": ["sequence", "kind", "invocation_id", "owner", "state", "screen", "mode", "accumulator", "argument_owner", "returned", "enabled", "widget"],
        "SPK_BerylN1Outcome": ["kind", "value"],
        "SPK_BerylN1ActionRecord": ["case_id", "action", "arguments", "before", "services", "outcome", "after"],
    }
    for name, fields in expected_fields.items():
        _require(_fields(text, name) == fields, "Logical typed record fields differ: " + name)
    for name in ("SPK_BerylN1Token", "SPK_BerylN1Bool", "SPK_BerylN1Int"):
        _require(_fields(text, name) == ["value"], "Nullable box shape differs")
    code = _mask(text)
    _require(not re.search(r"m_BerylState\.@[A-Z_]+@[ \t]*=(?!=)", code), "Observer writes production state")
    _require(not re.search(r"s_States\[[^]]+\]\.@[A-Z_]+@[ \t]*=(?!=)", code), "Observer resets registered state")
    _require(not re.search(r"s_(?:Current|Active|Selected).*Invocation", code), "Shared current invocation slot")
    _require(not re.search(r"new[ \t]+SPK_(?:TabletComponent|BerylTabletRealServicesObserver)[ \t]*\(", code), "Manual component construction")
    _contains(text, "static ref array<SPK_BerylTabletRealServicesObserver> s_Observers = {};", "Component references cannot use a strong inner ref")
    _require(not re.search(r"\b(?:thread|Sleep|CallLater|CallQueue|Invoke|SetEventMask|SetFlags|SpawnEntityPrefab|Destroy|Enable|Disable|Open|Close)[ \t]*\(", code), "Observer adds service/native mutation or async work")
    _require("override void EOnFrame" not in code and "override void OnDelete" not in code, "Observer captures frame or deletion callbacks")
    allowed = {
        "BerylObserveScreenCreated": {"BeginObservation", "Event", "Snapshot"},
        "BerylObserveScreenEnableEnter": {"BeginObservation", "Enter", "Snapshot"},
        "BerylObserveScreenEnableExit": {"BeginObservation", "Exit", "Snapshot"},
        "BerylObserveScreenDisableEnter": {"BeginObservation", "Enter", "Snapshot"},
        "BerylObserveScreenDisableExit": {"BeginObservation", "Exit", "Snapshot"},
        "BeginObservation": {"Fail"},
        "Snapshot": {"Fail", "GetState", "Capture", "GetUI", "GetScreen"},
        "Capture": {"IsRegistered", "Fail", "OutsideDomain", "ToString", "Token", "Boolean", "IsEnabled", "GetWidget"},
        "IsRegistered": {"Count"}, "Token": set(), "Boolean": set(), "Integer": set(),
        "Fail": set(), "OutsideDomain": set(), "Event": {"Count", "Fail", "Integer", "Token", "Boolean", "Insert"},
        "Enter": {"Fail", "Event"}, "Exit": {"Count", "Fail", "Event"},
    }
    for name, calls in allowed.items():
        _require(_calls(_body(text, name)) == calls, "Hook reachable call path differs: " + name)
    init = _body(text, "OnPostInit")
    markers = [".Claim(owner, m_BerylState, this)", 'ObserveInit("init.before", owner);', "super.OnPostInit(owner);", 'ObserveInit("init.after", owner);']
    _require(init.count("super.OnPostInit(owner);") == 1, "Native init superclass must run exactly once")
    positions = [init.find(item) for item in markers]
    _require(all(v >= 0 for v in positions) and positions == sorted(positions), "Native init observation order differs")
    _require(code.count(".OnPostInit(") == 1 and ".EOnFrame(" not in code and ".OnDelete(" not in code, "Manual protected callback")
    witness = _body(text, "ObserveInit")
    for item in ("owner == GetOwner()", "owner.GetWorld()", "GetGame().GetWorld()", "ownerWorld == gameWorld", "m_BerylState == SPK_BerylTabletRealServiceRegistry.s_States[m_ObservationToken - 1]", "GetEventMask()", "row.independence_observed && !row.independent_state", '(row.mask & EntityEvent.FRAME) == 0'):
        _contains(witness, item, "Missing independently observed init witness: " + item)
    claim = _body(text, "Claim")
    for item in ("s_States[0] == state", "s_Owners[0] == owner", "s_Observers[0] == observer", "token != s_Owners.Count() + 1", "s_PendingToken = 0;"):
        _contains(claim, item, "Claim does not contain exact identity/cardinality guard")
    run = _body(text, "RunSevenActions")
    for item in ("s_RunRequested || s_Running || s_Observing", "s_RunRequested = true;", "s_InitWitnesses.Count() != 4", "s_Observers[ownerIndex].InitComplete()", "!GetGame().InPlayMode()", "s_Owners[ownerIndex].GetWorld() != gameWorld", "s_Observers[ownerIndex].ClaimMatchesOwner()", "actionIndex < MAX_RECORDS", "s_Running = true;", "s_Running = false;", "s_Events.Count() != MAX_EVENTS", "s_InvocationCount != MAX_INVOCATIONS"):
        _contains(run, item, "Missing one-shot/native/action completion guard: " + item)
    ordered_cases = ("n1a.focus-refused.stowed", "n1a.held.first", "n1a.held.repeated", "n1a.unfocus-refused.held", "n1a.stow", "n1a.stow.repeated", "n1a.independent-state")
    positions = [run.find('"' + item + '"') for item in ordered_cases]
    _require(all(v >= 0 for v in positions) and positions == sorted(positions), "Seven public action cases changed order")
    _require(run.count("selected.Focus();") == 1 and run.count("selected.Unfocus();") == 1 and run.count("selected.SetHeld(true);") == 1 and run.count("selected.SetHeld(false);") == 1, "Public action source cardinality differs")
    _require('actionIndex == 1 || actionIndex == 2' in run and 'actionIndex == 4 || actionIndex == 5' in run, "Repeated public actions are not executed twice")
    _require(run.count("FinishRecord(record, eventStart, null);") == 3 and run.count("FinishRecord(record, eventStart, Boolean(returned));") == 2, "Known void/outcome observation changed")
    _contains(_body(text, "BeginRecord"), "CaptureBoth(result.before);", "Missing both-owner before snapshots")
    _contains(_body(text, "FinishRecord"), "CaptureBoth(record.after);", "Missing both-owner after snapshots")
    _contains(_body(text, "CaptureBoth"), "i < MAX_OWNERS", "Unbounded or partial owner snapshots")
    _contains(_body(text, "BerylObserveScreenEnableExit"), 'Exit("screen.enable.exit", invocationId, true, returned, Snapshot());', "Enable Boolean was forged or fed elsewhere")
    _contains(_body(text, "Enter"), "int invocationId = s_InvocationCount + 1;", "Invocation identifier is not positive/local")
    _contains(_body(text, "Capture"), "s_Screen != screen", "Screen equality token domain replaced")
    _contains(_body(text, "Capture"), "widget != s_Widget", "Widget equality token domain replaced")
    _contains(_body(text, "Capture"), 'OutsideDomain("N1a observed widget loss/replacement outside the retained-widget domain");', "Widget lifetime departure misclassified as structural failure")
    _contains(_body(text, "OutsideDomain"), 'if (s_Failure == "")', "Outside-domain result overwrites a preceding failure")
    _contains(_body(text, "OutsideDomain"), "s_OutsideDomain = true;", "Missing typed outside-domain flag")
    for name, number in (("MAX_OWNERS", 2), ("MAX_RECORDS", 7), ("MAX_EVENTS", 9), ("MAX_INVOCATIONS", 4)):
        _contains(text, f"static const int {name} = {number};", "Declared bound differs")
    _contains(text, f'SOURCE_CONTRACT_SHA256 = "{CONTRACT_SHA256}";', "Stale contract identity")
    _contains(text, 'PROFILE = "sparkos.tablet.real-services.n1a.source.v1";', "Wrong profile")
    if pin:
        _require(_sha(value) == OBSERVER_SHA256, "Observer bytes differ from frozen trusted source")
    return dict(status="source_admitted", bytes=len(value), sha256=_sha(value),
                placeholder_names=["STATE", "MODE", "ACCUMULATOR"], owner_count=2,
                action_count=7, service_events=9, invocation_pairs=4,
                engine_compilation="not_run", engine_execution="not_run",
                hook_non_interference="not_verified_by_source_gate", native_wire="not_implemented_here")


def self_test(value):
    results = []
    def case(case_id, fn):
        try:
            fn()
            results.append(dict(id=case_id, status="success"))
        except Exception as exc:
            results.append(dict(id=case_id, status="failure", error=type(exc).__name__, detail=str(exc)))
    def reject(candidate, *, pin=False):
        _require(candidate != value, "Deliberate source fault is identical to its baseline")
        try:
            validate_source(candidate, pin=pin)
        except SourceFailure:
            return
        raise AssertionError("Deliberate source fault was admitted")
    def change(old, new):
        _require(value.count(old.encode()) == 1, "Mutant source selection must be exact")
        return value.replace(old.encode(), new.encode(), 1)
    for case_id in CASE_IDS[:10]:
        case(case_id, lambda: validate_source(value))
    mutants = (
        ("negative.nonbytes", lambda: reject(value.decode())),
        ("negative.byte-budget", lambda: reject(value + b" " * MAX_BYTES)),
        ("negative.crlf", lambda: reject(value.replace(b"\n", b"\r\n"))),
        ("negative.unbound-placeholder", lambda: reject(change("@MODE@", "@UNKNOWN@"))),
        ("negative.snapshot-field", lambda: reject(change("string accumulator;\n\tref SPK_BerylN1Token ui;", "string extra;\n\tref SPK_BerylN1Token ui;"))),
        ("negative.event-field", lambda: reject(change("int sequence;", "int guessed_sequence;"))),
        ("negative.outcome-field", lambda: reject(change("class SPK_BerylN1Outcome\n{\n\tstring kind;", "class SPK_BerylN1Outcome\n{\n\tstring extra;"))),
        ("negative.record-field", lambda: reject(change("string case_id;", "string guessed_case;"))),
        ("negative.hook-get-owner", lambda: reject(change("int observedMode = GetState();", "GetOwner();\n\t\tint observedMode = GetState();"))),
        ("negative.hook-get-game", lambda: reject(change("int observedMode = GetState();", "GetGame();\n\t\tint observedMode = GetState();"))),
        ("negative.hook-service-call", lambda: reject(change("int observedMode = GetState();", "m_ScreenRT.Enable(GetOwner());\n\t\tint observedMode = GetState();"))),
        ("negative.hook-public-action", lambda: reject(change("int observedMode = GetState();", "SetHeld(true);\n\t\tint observedMode = GetState();"))),
        ("negative.hook-callback", lambda: reject(change("int observedMode = GetState();", "super.EOnFrame(null, 0);\n\t\tint observedMode = GetState();"))),
        ("negative.state-write", lambda: reject(change("int observedMode = GetState();", "m_BerylState.@MODE@ = 0;\n\t\tint observedMode = GetState();"))),
        ("negative.shared-invocation-slot", lambda: reject(change("static int s_InvocationCount;", "static int s_InvocationCount;\n\tstatic int s_CurrentInvocation;"))),
        ("negative.manual-constructor", lambda: reject(change("int observedMode = GetState();", "new SPK_BerylTabletRealServicesObserver();\n\t\tint observedMode = GetState();"))),
        ("negative.init-super-missing", lambda: reject(change("super.OnPostInit(owner);", "/* removed native superclass */"))),
        ("negative.init-super-duplicate", lambda: reject(change("super.OnPostInit(owner);", "super.OnPostInit(owner);\n\t\tsuper.OnPostInit(owner);"))),
        ("negative.init-order", lambda: reject(change('ObserveInit("init.before", owner);\n\t\tsuper.OnPostInit(owner);', 'super.OnPostInit(owner);\n\t\tObserveInit("init.before", owner);'))),
        ("negative.mask-write", lambda: reject(change("row.mask = GetEventMask();", "SetEventMask(owner, EntityEvent.FRAME);\n\t\trow.mask = GetEventMask();"))),
        ("negative.owner-witness", lambda: reject(change("row.owner_matches = owner == GetOwner();", "row.owner_matches = true;"))),
        ("negative.world-witness", lambda: reject(change("ownerWorld == gameWorld", "true"))),
        ("negative.state-witness", lambda: reject(change("row.same_state = m_BerylState == SPK_BerylTabletRealServiceRegistry.s_States[m_ObservationToken - 1];", "row.same_state = true;"))),
        ("negative.independence-witness", lambda: reject(change("row.independence_observed && !row.independent_state", "false"))),
        ("negative.native-init-guard", lambda: reject(change("!s_Observers[ownerIndex].InitComplete()", "false"))),
        ("negative.live-world-guard", lambda: reject(change("!GetGame().InPlayMode()", "false"))),
        ("negative.returned-owner-guard", lambda: reject(change("s_Owners[ownerIndex].GetWorld() != gameWorld", "false"))),
        ("negative.repeat-run-guard", lambda: reject(change("s_RunRequested || s_Running || s_Observing", "s_Running || s_Observing"))),
        ("negative.both-before", lambda: reject(change("CaptureBoth(result.before);", "/* removed before */"))),
        ("negative.both-after", lambda: reject(change("CaptureBoth(record.after);", "/* removed after */"))),
        ("negative.action-order", lambda: reject(value.replace(b"n1a.held.first", b"n1a.temporary-swap").replace(b"n1a.held.repeated", b"n1a.held.first").replace(b"n1a.temporary-swap", b"n1a.held.repeated"))),
        ("negative.duplicate-focus", lambda: reject(change("returned = selected.Focus();", "selected.Focus();\n\t\t\t\treturned = selected.Focus();"))),
        ("negative.forged-void-result", lambda: reject(change("FinishRecord(record, eventStart, null); // The public signature is void.\n\t\t\t}\n\t\t\telse if (actionIndex == 3)", "FinishRecord(record, eventStart, Boolean(false)); // Forged void.\n\t\t\t}\n\t\t\telse if (actionIndex == 3)"))),
        ("negative.forged-enable-result", lambda: reject(change('Exit("screen.enable.exit", invocationId, true, returned, Snapshot());', 'Exit("screen.enable.exit", invocationId, true, false, Snapshot());'))),
        ("negative.local-id-zero", lambda: reject(change("int invocationId = s_InvocationCount + 1;", "int invocationId = 0;"))),
        ("negative.event-budget", lambda: reject(change("static const int MAX_EVENTS = 9;", "static const int MAX_EVENTS = 10;"))),
        ("negative.invocation-budget", lambda: reject(change("static const int MAX_INVOCATIONS = 4;", "static const int MAX_INVOCATIONS = 100;"))),
        ("negative.record-budget", lambda: reject(change("static const int MAX_RECORDS = 7;", "static const int MAX_RECORDS = 8;"))),
        ("negative.frame-override", lambda: reject(value + b"\noverride void EOnFrame(IEntity owner, float timeSlice) {}\n")),
        ("negative.delete-override", lambda: reject(value + b"\noverride void OnDelete(IEntity owner) {}\n")),
        ("negative.external-state-reset", lambda: reject(change("int observedMode = GetState();", "s_States[0].@MODE@ = 0;\n\t\tint observedMode = GetState();"))),
        ("negative.hook-async", lambda: reject(change("int observedMode = GetState();", "Sleep(1);\n\t\tint observedMode = GetState();"))),
        ("negative.identity-replacement", lambda: reject(change("s_Screen != screen", "false"))),
        ("negative.omitted-final-count", lambda: reject(change("s_Events.Count() != MAX_EVENTS", "false"))),
        ("negative.outside-domain-classification", lambda: reject(change('OutsideDomain("N1a observed widget loss/replacement outside the retained-widget domain");', 'Fail("N1a observed widget loss/replacement outside the retained-widget domain");'))),
        ("negative.outside-domain-primary", lambda: reject(change('if (s_Failure == "")\n\t\t{\n\t\t\ts_Failure = detail;', 'if (true)\n\t\t{\n\t\t\ts_Failure = detail;'))),
        ("negative.unpinned-whitespace", lambda: reject(value + b"\n", pin=True)),
        ("negative.strong-component-ref", lambda: reject(change("static ref array<SPK_BerylTabletRealServicesObserver> s_Observers = {};", "static ref array<ref SPK_BerylTabletRealServicesObserver> s_Observers = {};"))),
    )
    for case_id, fn in mutants:
        case(case_id, fn)
    _require(tuple(row["id"] for row in results) == CASE_IDS and len(set(row["id"] for row in results)) == len(CASE_IDS), "Fixed source case inventory changed")
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true", required=True)
    parser.parse_args()
    owned = Path(tempfile.mkdtemp(prefix="tablet-real-service-observer-", dir=ROOT / "build"))
    own_bytes = _read(Path(__file__))
    result = dict(schema_version=1, operation="n1a.observer.source-admission", status="failure",
                  expected_cases=list(CASE_IDS), cases=[], scope="source-only: no compiler, engine, services, native callbacks or wire execution")
    try:
        files = {"observer.c.in": _read(OBSERVER), "contract.json": _read(PACKAGE / "contract.json"),
                 "original.c.in": _read(ROOT / "packages/sparkos/tablet-service-prototype/tablet-service.c.in"),
                 "hooks.c.in": _read(PACKAGE / "screen-observation-hooks.c.in"),
                 "instrumenter.py": _read(PACKAGE / "instrument_adapter.py"), "gate.py": own_bytes}
        for name, data in files.items():
            (owned / name).write_bytes(data)
            _require(_read(owned / name) == data, "Retained source readback failed")
        result["retained"] = [{"path": name, "bytes": len(data), "sha256": _sha(data)} for name, data in files.items()]
        for name, digest in (("contract.json", CONTRACT_SHA256), ("original.c.in", ORIGINAL_SHA256), ("hooks.c.in", HOOKS_SHA256), ("instrumenter.py", INSTRUMENTER_SHA256)):
            _require(_sha(files[name]) == digest, "Changed source dependency: " + name)
        contract = json.loads(files["contract.json"])
        _require(contract["snapshot_fields"] == _fields(files["observer.c.in"].decode(), "SPK_BerylN1Snapshot"), "Contract snapshot projection differs")
        _require(contract["event_fields"] == _fields(files["observer.c.in"].decode(), "SPK_BerylN1ServiceEvent"), "Contract event projection differs")
        admission = validate_source(files["observer.c.in"])
        result["admission"] = admission
        result["cases"] = self_test(files["observer.c.in"])
        result["passed_cases"] = sum(row["status"] == "success" for row in result["cases"])
        result["failed_cases"] = len(CASE_IDS) - result["passed_cases"]
        origins = dict(schema_version=1, source="packages/sparkos/tablet-real-service-probe/observer.c.in",
                       sha256=admission["sha256"], line_count=len(files["observer.c.in"].splitlines()),
                       origin_kind="trusted_fixture_source", expanded_columns="unavailable",
                       generated_origins="not_a_compiler_generated_source_map", placeholders=admission["placeholder_names"])
        (owned / "origins.json").write_text(json.dumps(origins, indent=2) + "\n", encoding="utf8")
        _require(_read(OBSERVER) == files["observer.c.in"] and _read(PACKAGE / "contract.json") == files["contract.json"] and _read(Path(__file__)) == own_bytes, "Source changed during source gate")
        _require(_read(ROOT / "packages/sparkos/tablet-service-prototype/tablet-service.c.in") == files["original.c.in"] and _read(PACKAGE / "screen-observation-hooks.c.in") == files["hooks.c.in"] and _read(PACKAGE / "instrument_adapter.py") == files["instrumenter.py"], "Frozen source dependency changed during gate")
        result["status"] = "success" if result["failed_cases"] == 0 else "failure"
    except Exception as exc:
        result["error"] = dict(kind=type(exc).__name__, detail=str(exc))
    receipt = owned / "result.json"
    receipt.write_text(json.dumps(result, indent=2) + "\n", encoding="utf8")
    print(json.dumps(dict(status=result["status"], receipt=str(receipt), passed=result.get("passed_cases", 0), failed=result.get("failed_cases", 0))))
    return 0 if result["status"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
