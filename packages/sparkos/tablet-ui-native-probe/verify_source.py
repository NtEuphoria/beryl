"""Bounded N1b/N3 source/overlay fixtures. No engine or native callbacks run."""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import sys
import tempfile
import types
from pathlib import Path

sys.dont_write_bytecode = True
PACKAGE = Path(__file__).resolve().parent
ROOT = PACKAGE.parents[2]
OBSERVER_SHA256 = "37197ea005a1d988e3824d5ca0db7ba333ac73a65b07275828d0f2a5f9c76d36"
INSTRUMENTATION_SHA256 = "0167c3025abc3c8aa9c31417f2ff28c283f5d0350a65b0dcbd7a6b6fe442f1a6"
CONTRACT_SHA256 = "b06b5181b084787fa8b3fa959930b72d5544d21045a9397307f7179067858f27"
MAX_BYTES = 128 * 1024


class SourceFailure(ValueError):
    pass


def require(value, message):
    if not value:
        raise SourceFailure(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read(path):
    with Path(path).open("rb") as stream:
        data = stream.read(MAX_BYTES + 1)
    require(len(data) <= MAX_BYTES, "Source read exceeded bounded budget")
    return data


def mask(text):
    return re.sub(r'//[^\n]*|/\*[\s\S]*?\*/|"(?:\\.|[^"\\])*"',
                  lambda m: "".join("\n" if c == "\n" else " " for c in m[0]), text)


def body(text, name):
    code = mask(text)
    match = re.search(r'\b(?:static |override |protected )*[\w@]+\s+' + re.escape(name) + r'\s*\([^)]*\)\s*\{', code)
    require(match is not None, "Missing reviewed method: " + name)
    start = match.end()
    depth = 1
    cursor = start
    while cursor < len(code) and depth:
        depth += (code[cursor] == "{") - (code[cursor] == "}")
        cursor += 1
    require(depth == 0, "Unbalanced source method")
    return text[start:cursor - 1]


def validate(data, *, pin=True):
    require(type(data) is bytes and 0 < len(data) <= MAX_BYTES, "Observer requires bounded literal bytes")
    require(b"\r" not in data and b"\0" not in data, "Observer requires LF without NUL")
    try:
        text = data.decode("utf8")
    except UnicodeError as exc:
        raise SourceFailure("Observer requires UTF-8") from exc
    code = mask(text)
    require(set(re.findall(r'@[A-Z_]+@', code)) == {"@STATE@", "@ACCUMULATOR@"}, "Unexpected/missing Beryl source placeholders")
    require(not re.search(r'\bm_BerylState\.@[A-Z_]+@\s*=(?!=)', code), "Observer changes production state")
    require(not re.search(r'\bnew\s+(?:SPK_TabletUI|SPK_ScreenRT|SPK_TabletComponent|SPK_BerylTabletUINativeObserver|SPK_Drone\w+)\s*\(', code), "Observer manually constructs native/production services")
    require(not re.search(r'\b(?:CallLater|CallQueue|GetCallqueue|Tick|RemoveByName|Clear|Sleep|DeleteEntityAndChildren|DeleteRplEntity|SpawnEntityPrefab|SetControlledEntity|ToggleActive|Save|RegisterDefaults|GetKeybinds)\s*\(', code), "Observer performs async/manual deletion/player/profile operation")
    require(not re.search(r'\bevent\b', code), "Reserved EnforceScript event identifier")
    require('PROFILE = "sparkos.tablet.ui-native.n1b-n3.source.v1";' in text, "Wrong distinct source profile")
    require('static ref array<SPK_BerylTabletUINativeObserver> s_Observers = {};' in text, "Native component observation adds strong inner reference")
    require('static SPK_TabletUI s_UI;' in text and 'static Widget s_LastRoot;' in text, "UI/widget equality handles add explicit strong retention")
    require('static ref SPK_TabletUI' not in code and 'static ref Widget' not in code, "Strong UI/widget registry retention")
    for name, bound in (("MAX_ROWS", 12288), ("MAX_BYTES", 8388608), ("MAX_FRAMES", 2048), ("MAX_INVOCATIONS", 8192), ("MAX_QUEUE", 64)):
        require(f"static const int {name} = {bound};" in text, "Bounded observation policy changed: " + name)
    append = body(text, "Append")
    for marker in ("s_Rows.Count() >= MAX_ROWS", "row.Length() > 1024", "s_Bytes + row.Length() + 1 > MAX_BYTES", "value < 32 || value > 126", "count != columns", "s_Checksum * 31 + row.ToAscii(j)", "s_Checksum * 31 + 10", "% 1000003"):
        require(marker in append, "Incomplete ASCII/count/checksum guard: " + marker)
    capture = body(text, "Capture")
    capture_calls = set(re.findall(r'\b(\w+)\s*\(', mask(capture)))
    require(capture_calls <= {"SPK_BerylTabletUIReceipt", "FirstProgressReady", "ReopenProgressReady", "Count", "Insert", "for"}, "Post-stop Capture reaches native service/getter")
    require('result.rows.Insert(s_Rows[i]);' in capture and 's_Owners.Count()' in capture, "Scalar Capture does not clone bounded rows/counters")
    require('s_Owners[' not in capture and 's_Observers[' not in capture and 's_UI' not in capture and 's_LastRoot' not in capture, "Post-stop Capture dereferences native observation handles")
    live = body(text, "LiveReady")
    for marker in ("s_InitCount != 4", "s_DeleteCount != 0", "!GetGame().InPlayMode()", "s_Observers[i].GetOwner() != s_Owners[i]", "s_Owners[i].GetWorld() != world", "s_Owners[i].FindComponent(SPK_DroneInputComponent)"):
        require(marker in live, "Missing live owner/world/input prerequisite")
    outside = body(text, "OutsideDomain")
    require('if (s_Failure == "")' in outside and "s_OutsideDomain = true;" in outside, "Unavailable result overwrites structural failure")
    run = body(text, "RunAction")
    for marker in ("index != s_ActionCount", "s_ActionRunning || !LiveReady()", "index == 2 && !FirstProgressReady()", "index == 5 && !ReopenProgressReady()", 'selected.Record("action", 0, "before"', 'selected.Record("action", 0, "after"', "s_ActionCount++;", "(index == 1 || index == 4 || index == 6) && !returned", "OutsideDomain("):
        require(marker in run, "Missing public-action sequencing/readiness/refusal contract: " + marker)
    positions = [run.find(marker) for marker in ('selected.Record("action", 0, "before"', "selected.SetHeld(true)", "selected.Focus()", "selected.Unfocus()", "selected.SetHeld(false)", 'selected.Record("action", 0, "after"', "s_ActionCount++;")]
    require(all(index >= 0 for index in positions) and positions == sorted(positions), "Public action recording/order differs")
    require("index == 1 || index == 2 || index == 4" in run and "index == 3" in run and "index == 5" in run and "selected.SetHeld(true); returned = selected.Focus();" in run, "Exact seven-action branch sequence differs")
    for name, frame_marker, report_marker, terrain_marker in (("FirstProgressReady", "s_FirstFocusedFrames >= 2", "s_FirstReport", "s_FirstTerrain"), ("ReopenProgressReady", "s_ReopenFocusedFrames >= 2", "s_ReopenReport", "s_ReopenTerrain")):
        for marker in (frame_marker, report_marker, terrain_marker):
            require(marker in body(text, name), "Progress admits missing actual frame/queue exit")
    init = body(text, "OnPostInit")
    init_markers = [init.find(marker) for marker in (".Claim(owner, this)", 'Record("init", 0, "before"', "super.OnPostInit(owner);", 'Record("init", GetEventMask(), "after"')]
    require(all(index >= 0 for index in init_markers) and init_markers == sorted(init_markers) and init.count("super.OnPostInit(owner);") == 1, "Native initialization/source superclass order differs")
    frame = body(text, "EOnFrame")
    require(frame.count("super.EOnFrame(owner, timeSlice);") == 1, "Native frame source timestep/superclass cardinality differs")
    require(frame.find('Record("frame", 0, "before"') < frame.find("super.EOnFrame(owner, timeSlice);") < frame.find('Record("frame", 0, "after"'), "Native frame observation order differs")
    require("s_FrameCount >= SPK_BerylTabletUINativeRegistry.MAX_FRAMES" in frame and "m_InsideFrame" in frame, "Native frame budget/reentry guard missing")
    require("m_ObservationToken == 1 && GetState() == ESPK_TabletState.FOCUSED" in frame and "s_ActionCount == 2" in frame and "s_ActionCount == 5" in frame, "Progress counter counts unrelated frames")
    delete = body(text, "OnDelete")
    require(delete.count("super.OnDelete(owner);") == 1, "Native deletion superclass cardinality differs")
    before, after = delete.split("super.OnDelete(owner);")
    require('Record("delete", 0, "entry"' in before and "int capturedToken = m_ObservationToken;" in before, "Native deletion entry/local token missing")
    require(mask(after).strip() == "SPK_BerylTabletUINativeRegistry.AfterSuper(capturedToken);", "Native object/component access added after superclass destruction")
    after_super = body(text, "AfterSuper")
    require(not re.search(r'\b(?:Get\w+|Record|RootGeneration|Queue)\s*\(', mask(after_super)), "After-super scalar milestone dereferences native service")
    require('Append(row, 4);' in after_super and "s_AfterSuperCount >= 2" in after_super and "s_AfterSuper1" in after_super and "s_AfterSuper2" in after_super, "After-super cardinality/duplicate guard missing")
    pre = body(text, "BerylObserveUiDeletePreSuper")
    require("!m_Deleting || m_PreSuperSeen" in pre and 'Record("service", 19, "pre-super"' in pre, "Delete inner superclass boundary missing")
    service = body(text, "BerylObserveUiServiceExit")
    require("code == 4 && (!hasReturned || returned)" in service, "Actual input absence contract missing")
    require("code == 18" in service and "GetScreen().IsEnabled()" in service and "GetScreen().GetWidget()" in service, "Destroy return script-state observation missing")
    record = body(text, "Record")
    require("SPK_BerylTabletUINativeRegistry.Append(row, 23);" in record, "Main scalar trace columns differ")
    for marker in ("dt != dt || dt < 0 || dt > 1", "accumulator != accumulator || accumulator < 0 || accumulator >= 0.25", "SPK_TabletUI ui = GetUI();", "SPK_ScreenRT screen = GetScreen();", "screen.IsEnabled()", "screen.GetWidget() != null"):
        require(marker in record, "Main live scalar/getter/numeric capture contract changed")
    require(body(text, "Queue").count("Append(row, 10)") == 1 and "s_QueueCount >= MAX_QUEUE" in body(text, "Queue"), "Queue observation bounds/columns differ")
    require('kind == "exit.ReportRootSize"' in body(text, "Queue") and 'kind == "exit.RefreshTerrain"' in body(text, "Queue"), "Queue readiness is not based on actual method exits")
    if pin:
        require(sha(data) == OBSERVER_SHA256, "Observer bytes differ from frozen revision")
    return dict(status="source_admitted", bytes=len(data), sha256=sha(data),
                engine="not_run", callbacks="not_run", queue_origin="unavailable",
                native_lifetime="unverified", f32_exact_codec="unavailable")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", required=True, action="store_true")
    parser.parse_args()
    owned = Path(tempfile.mkdtemp(prefix="tablet-ui-native-source-", dir=ROOT / "build"))
    result = dict(schema_version=1, operation="n1b.n3.source-admission", status="failure",
                  scope="source/overlay only; compiler engine callbacks services not run", cases=[])
    try:
        basis = ROOT / "packages/sparkos/tablet-service-prototype/tablet-service.c.in"
        ui_path = Path("C:/Users/moham/Documents/My Games/ArmaReforgerWorkbench/addons/SparkOS_Mesh/scripts/Game/SparkOSMesh/UI/SPK_TabletUI.c")
        files = {"observer.c.in": read(PACKAGE / "observer.c.in"), "instrumentation.py": read(PACKAGE / "instrumentation.py"),
                 "contract.json": read(PACKAGE / "contract.json"), "gate.py": read(Path(__file__)),
                 "adapter-original.c.in": read(basis), "ui-original.c": read(ui_path)}
        for name, data in files.items():
            require((owned / name).write_bytes(data) == len(data) and read(owned / name) == data, "Retained source write/readback failed")
        result["retained"] = [dict(path=name, bytes=len(data), sha256=sha(data)) for name, data in files.items()]
        require(sha(files["instrumentation.py"]) == INSTRUMENTATION_SHA256 and sha(files["contract.json"]) == CONTRACT_SHA256, "Frozen package dependency changed")
        contract = json.loads(files["contract.json"])
        require(contract["profile"] == "sparkos.tablet.ui-native.n1b-n3.source.v1" and len(contract["row_columns"]) == 23 and len(contract["queue_columns"]) == 10 and len(contract["after_super_columns"]) == 4, "Contract profile/columns differ")
        module = types.ModuleType("n1b_frozen_instrumentation")
        module.__file__ = str(PACKAGE / "instrumentation.py")
        exec(compile(files["instrumentation.py"], module.__file__, "exec"), module.__dict__)
        def case(case_id, fn):
            require(case_id not in [value["id"] for value in result["cases"]], "Duplicate source case")
            try:
                fn()
                result["cases"].append(dict(id=case_id, status="success"))
            except Exception as exc:
                result["cases"].append(dict(id=case_id, status="failure", error=type(exc).__name__, detail=str(exc)))
        original_adapter = files["adapter-original.c.in"]
        original_ui = files["ui-original.c"]
        adapter = module.adapter_overlay(original_adapter)
        ui = module.ui_overlay(original_ui)
        require((owned / "adapter-instrumented.c.in").write_bytes(adapter) == len(adapter), "Overlay retention failed")
        require((owned / "ui-instrumented.c").write_bytes(ui) == len(ui), "UI overlay retention failed")
        result["overlay"] = dict(adapter_sha256=sha(adapter), adapter_bytes=len(adapter), ui_sha256=sha(ui), ui_bytes=len(ui))
        def overlay_check():
            require(module.strip_adapter(adapter, original_adapter) == original_adapter, "Adapter stripping loses original bytes")
            require(module.strip_ui(ui, original_ui) == original_ui, "UI stripping loses original bytes")
            acode = adapter.decode()
            require(acode.count("m_UI.Open()") == 1 and acode.count("m_ScreenRT.Enable(GetOwner())") == 1 and acode.count("m_UI.Close()") == 2, "Real service cardinality changed")
            require(acode.count("super.OnDelete(owner);") == 1 and "BerylObserveUiDeletePreSuper();\n\t\t\t\tsuper.OnDelete(owner);" in acode, "Immediate superclass deletion hook changed")
            require('bool berylUiReturned3 = m_UI.Open();' in acode and 'if (berylUiReturned3) reply = 1;' in acode, "Actual Open result does not drive original reply")
            require('bool berylUiReturned11 = m_ScreenRT.Enable(GetOwner());' in acode and 'if (berylUiReturned11)' not in acode, "Observed Enable result changed production state")
            require(acode.count("GetOwner()") == original_adapter.decode().count("GetOwner()"), "Instrumentation evaluates GetOwner twice")
            ucode = ui.decode().replace("\r\n", "\n")
            ocode = original_ui.decode().replace("\r\n", "\n")
            require(ucode.count(".CallLater(") == ocode.count(".CallLater("), "Queue cardinality changed")
            require(ucode.count('Queue("enqueue.RefreshTerrain"') == 2 and ucode.count('Queue("enqueue.ReportRootSize"') == 1, "Real enqueue source observation missing")
            require(ucode.count('Queue("entry.RefreshTerrain"') == 1 and ucode.count('Queue("exit.RefreshTerrain"') == 3 and ucode.count('Queue("entry.ReportRootSize"') == 1 and ucode.count('Queue("exit.ReportRootSize"') == 3, "Actual queue-method return observations incomplete")
            for target, delay in (("RefreshTerrain", 400), ("ReportRootSize", 500)):
                require(ucode.count(f"CallLater({target}, {delay}, false);") == ocode.count(f"CallLater({target}, {delay}, false);"), "Queue delay/target/argument changed")
        case("positive.frozen-observer", lambda: validate(files["observer.c.in"]))
        case("positive.structural-observer", lambda: validate(files["observer.c.in"], pin=False))
        case("positive.reversible-real-service-overlays", overlay_check)
        def reject_overlay(candidate, which):
            try:
                if which == "adapter": module.strip_adapter(candidate, original_adapter)
                else: module.strip_ui(candidate, original_ui)
            except module.InstrumentationFailure:
                return
            raise AssertionError("Deliberate overlay source change admitted")
        for name, candidate, which in (("changed-open", adapter.replace(b"m_UI.Open()", b"false", 1), "adapter"), ("missing-delete-boundary", adapter.replace(b"BerylObserveUiDeletePreSuper();", b"", 1), "adapter"), ("queue-delay", ui.replace(b"RefreshTerrain, 400", b"RefreshTerrain, 100", 1), "ui"), ("queue-target", ui.replace(b"ReportRootSize, 500", b"RefreshTerrain, 500", 1), "ui"), ("extra-queue", ui + b"\nCallLater(RefreshTerrain, 400, false);\n", "ui")):
            case("negative.overlay." + name, lambda candidate=candidate, which=which: reject_overlay(candidate, which))
        data = files["observer.c.in"]
        def mutate(old, new):
            require(data.count(old.encode()) == 1, "Exact mutant source selection failed")
            return data.replace(old.encode(), new.encode(), 1)
        def reject(candidate, pin=False):
            require(candidate != data, "Unchanged source is not a mutant")
            try:
                validate(candidate, pin=pin)
            except SourceFailure:
                return
            raise AssertionError("Deliberate source fault admitted")
        faults = (
            ("manual-frame", "super.EOnFrame(owner, timeSlice);", "super.EOnFrame(owner, 0);"),
            ("frame-super-duplicate", "super.EOnFrame(owner, timeSlice);", "super.EOnFrame(owner, timeSlice); super.EOnFrame(owner, timeSlice);"),
            ("frame-budget", "static const int MAX_FRAMES = 2048;", "static const int MAX_FRAMES = 4096;"),
            ("row-budget", "static const int MAX_ROWS = 12288;", "static const int MAX_ROWS = 99999;"),
            ("row-columns", "SPK_BerylTabletUINativeRegistry.Append(row, 23);", "SPK_BerylTabletUINativeRegistry.Append(row, 22);"),
            ("queue-columns", "if (Append(row, 10))", "if (Append(row, 9))"),
            ("after-super-getter", "SPK_BerylTabletUINativeRegistry.AfterSuper(capturedToken);", "GetScreen(); SPK_BerylTabletUINativeRegistry.AfterSuper(capturedToken);"),
            ("after-super-state", "SPK_BerylTabletUINativeRegistry.AfterSuper(capturedToken);", "m_BerylState.@ACCUMULATOR@ = 0; SPK_BerylTabletUINativeRegistry.AfterSuper(capturedToken);"),
            ("delete-super-missing", "super.OnDelete(owner);", "/* omitted */"),
            ("delete-super-duplicate", "super.OnDelete(owner);", "super.OnDelete(owner); super.OnDelete(owner);"),
            ("delete-local-token", "int capturedToken = m_ObservationToken;", "int capturedToken = 1;"),
            ("capture-native-getter", "result.failure = s_Failure;", "GetGame(); result.failure = s_Failure;"),
            ("capture-owner-deref", "result.owner_count = s_Owners.Count();", "s_Owners[0].GetWorld(); result.owner_count = s_Owners.Count();"),
            ("strong-component", "array<SPK_BerylTabletUINativeObserver> s_Observers", "array<ref SPK_BerylTabletUINativeObserver> s_Observers"),
            ("strong-ui", "static SPK_TabletUI s_UI;", "static ref SPK_TabletUI s_UI;"),
            ("strong-root", "static Widget s_LastRoot;", "static ref Widget s_LastRoot;"),
            ("manual-input", "bool uiOpen, hasMap", "new SPK_DroneInputComponent(); bool uiOpen, hasMap"),
            ("keybinding-write", "bool uiOpen, hasMap", "GetKeybinds(); bool uiOpen, hasMap"),
            ("fake-deletion", "bool uiOpen, hasMap", "DeleteEntityAndChildren(null); bool uiOpen, hasMap"),
            ("manual-queue", "bool uiOpen, hasMap", "Tick(); bool uiOpen, hasMap"),
            ("action-replay", "index != s_ActionCount", "false"),
            ("first-natural-progress", "index == 2 && !FirstProgressReady()", "false"),
            ("reopen-natural-progress", "index == 5 && !ReopenProgressReady()", "false"),
            ("unavailable-failure-priority", 'if (s_Failure == "") { s_Failure = detail; s_OutsideDomain = true; }', 'if (true) { s_Failure = detail; s_OutsideDomain = true; }'),
            ("actual-false-open", "(index == 1 || index == 4 || index == 6) && !returned", "false"),
            ("frame-unrelated-owner", "m_ObservationToken == 1 && GetState() == ESPK_TabletState.FOCUSED", "GetState() == ESPK_TabletState.FOCUSED"),
            ("queue-early-readiness", 'kind == "exit.ReportRootSize"', 'kind == "enqueue.ReportRootSize"'),
            ("delete-destroy-return", "GetScreen().IsEnabled() || GetScreen().GetWidget()", "false"),
            ("owner-input-admission", "s_Owners[i].FindComponent(SPK_DroneInputComponent)", "false"),
            ("reserved-keyword", "bool uiOpen, hasMap", "bool event; bool uiOpen, hasMap"),
        )
        for name, old, new in faults:
            if name == "queue-early-readiness":
                candidate = data.replace(old.encode(), new.encode())
                case("negative." + name, lambda candidate=candidate: reject(candidate))
            else:
                case("negative." + name, lambda old=old, new=new: reject(mutate(old, new)))
        for name, candidate, pinned in (("nonbytes", data.decode(), False), ("crlf", data.replace(b"\n", b"\r\n"), False), ("nul", data + b"\0", False), ("size", data + b" " * MAX_BYTES, False), ("pinned-whitespace", data + b"\n", True)):
            case("negative." + name, lambda candidate=candidate, pinned=pinned: reject(candidate, pinned))
        result["expected_case_ids"] = [value["id"] for value in result["cases"]]
        result["passed"] = sum(value["status"] == "success" for value in result["cases"])
        result["failed"] = len(result["cases"]) - result["passed"]
        for name in ("observer.c.in", "instrumentation.py", "contract.json"):
            require(read(PACKAGE / name) == files[name], "Source changed during source gate")
        require(read(basis) == original_adapter and read(ui_path) == original_ui, "Original source basis changed during gate")
        result["status"] = "success" if result["failed"] == 0 else "failure"
    except Exception as exc:
        result["error"] = dict(kind=type(exc).__name__, detail=str(exc))
    path = owned / "result.json"
    payload = json.dumps(result, sort_keys=True, indent=2, ensure_ascii=True).encode("ascii") + b"\n"
    require(path.write_bytes(payload) == len(payload) and read(path) == payload, "Receipt checked write/readback failed")
    print(json.dumps(dict(status=result["status"], receipt=str(path), sha256=sha(payload), passed=result.get("passed", 0), failed=result.get("failed", 0))))
    return 0 if result["status"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
