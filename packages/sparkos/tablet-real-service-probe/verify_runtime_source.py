"""Bounded source gate for the trusted N1a native transport.

This reads text and tests deliberate source faults. It does not parse EnforceScript
fully, compile, create owners, execute callbacks/services, inspect processes, or
establish native lifetime, rendering, user interaction, or cleanup behavior.
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
TEMPLATE = PACKAGE / "runtime-driver.c.in"
TEMPLATE_SHA256 = "c124f5ee4eb1d26fd2bd5101f5be767673c87d5e5471ba522e8fa6ddb071e8d5"
N0_SHA256 = "ff6021f598da79a8e9160825b885a064c85b64e4b207fdb824f5ddcf0f3ef132"
SOURCE_CONTRACT_SHA256 = "74aed85740e8d72b5c187eae9b537fffb921b90ec24ac0002500379897e8cd65"
WIRE_CONTRACT_SHA256 = "80abd295e0652346df82083ade1409731f3f0b3508a8cd75f09b6afe39920766"
MAX_BYTES = 65536

STRING_FIELDS = (
    "token", "action", "status", "failure", "profile", "source_contract_sha256",
    "source_sha256", "wire_contract_sha256", "world_path", "current_project",
    "addon_world_path", "world_absolute_path", "resource_name", "resource_path",
    "resource_absolute_path",
)
BOOL_FIELDS = (
    "addon_world_resolved", "world_path_resolved", "resource_name_resolved",
    "module_present", "api_present", "module_open_requested", "module_open_accepted",
    "load_accepted", "world_matches", "edit_mode", "game_mode", "in_play_mode",
    "world_present", "game_world_present", "actions_ready", "stop_requested", "outside_domain",
)
INT_FIELDS = (
    "schema_version", "load_requested", "load_submitted", "load_entered",
    "load_resumed", "load_returned", "phase", "executed", "failures", "owner_count",
    "row_count", "checksum", "init_count", "init_checksum", "raw_bytes",
)
ARRAY_FIELDS = ("caseIds", "rows", "init_rows")
FIELDS = STRING_FIELDS + BOOL_FIELDS + INT_FIELDS + ARRAY_FIELDS
CASE_IDS = (
    "positive.frozen-template", "positive.typed-envelope", "positive.native-factory",
    "positive.native-init-witnesses", "positive.single-public-run", "positive.freeze-copy",
    "positive.scalar-handoff", "positive.pending-versus-complete", "positive.source-identities",
    "positive.preserved-predecessor", "negative.nonbytes", "negative.byte-budget",
    "negative.crlf", "negative.unknown-placeholder", "negative.missing-project-pin",
    "negative.missing-worker-project-pin", "negative.missing-token-pin", "negative.wrong-source-contract",
    "negative.wrong-wire-contract", "negative.wrong-world-id", "negative.wrong-prefab-id",
    "negative.manual-init", "negative.manual-frame", "negative.manual-delete",
    "negative.manual-component", "negative.mask-write", "negative.flag-write",
    "negative.profile-write", "negative.duplicate-native-spawn", "negative.spawn-world",
    "negative.claim-owner", "negative.claim-component", "negative.claim-state",
    "negative.missing-init-order", "negative.missing-init-mask", "negative.shared-state",
    "negative.missing-world-owner", "negative.repeat-run-guard", "negative.run-marker-order",
    "negative.duplicate-public-run", "negative.run-count", "negative.missing-final-snapshot",
    "negative.frozen-array-alias", "negative.init-prefix-omitted", "negative.main-prefix-omitted",
    "negative.case-prefix-omitted", "negative.scalar-owner-getter", "negative.scalar-widget-getter",
    "negative.scalar-live-validator", "negative.handoff-no-frozen-receipt", "negative.handoff-after-stop-capture",
    "negative.complete-before-edit", "negative.complete-in-play", "negative.failure-laundering",
    "negative.outside-domain-laundering", "negative.duplicate-regv", "negative.missing-regv",
    "negative.response-field", "negative.old-frame-fields", "negative.extra-yield",
    "negative.unpinned-whitespace",
)


class SourceFailure(ValueError):
    pass


def require(condition, detail):
    if not condition:
        raise SourceFailure(detail)


def sha(value):
    return hashlib.sha256(value).hexdigest()


def read(path):
    path = Path(path)
    require(not path.is_symlink() and path.is_file(), "Required regular source file")
    with path.open("rb") as stream:
        value = stream.read(MAX_BYTES + 1)
    require(len(value) <= MAX_BYTES, "Source byte budget exceeded")
    return value


def mask(text):
    pattern = r'//[^\n]*|/\*[\s\S]*?\*/|"(?:\\.|[^"\\])*"'
    return re.sub(pattern, lambda found: "".join("\n" if c == "\n" else " " for c in found[0]), text)


def block(text, start):
    masked = mask(text)
    depth = 0
    for index in range(start, len(masked)):
        if masked[index] == "{":
            depth += 1
        elif masked[index] == "}":
            depth -= 1
            if depth == 0:
                return text[start + 1:index]
    raise SourceFailure("Unbalanced source block")


def body(text, name):
    pattern = r"(?m)^[ \t]*(?:(?:override|protected|static)[ \t]+)*[A-Za-z_@][A-Za-z0-9_@]*[ \t]+" + re.escape(name) + r"[ \t]*\([^;{}]*\)\s*\{"
    found = list(re.finditer(pattern, mask(text)))
    require(len(found) == 1, "Expected exactly one method: " + name)
    return block(text, found[0].end() - 1)


def has(text, expected, detail):
    require(expected in text, detail)


def ordered(text, values, detail):
    position = -1
    for value in values:
        new = text.find(value, position + 1)
        require(new >= 0, detail)
        position = new


def validate_source(value, *, pin=True):
    require(type(value) is bytes, "Native transport must be exact bytes")
    require(0 < len(value) <= MAX_BYTES, "Native transport byte budget exceeded")
    require(b"\r" not in value and b"\0" not in value, "LF UTF-8 source without NUL required")
    try:
        text = value.decode("utf8")
    except UnicodeError as exc:
        raise SourceFailure("Native transport is not UTF-8") from exc
    require(set(re.findall(r"@[A-Z0-9_]+@", text)) == {"@TOKEN@", "@SOURCE_SHA256@", "@CURRENT_GAME_PROJECT@", "@WORLD_ABSOLUTE@"}, "Unknown/missing trusted placeholder")
    code = mask(text)
    require(not re.search(r"\b(?:OnPostInit|EOnFrame|OnDelete|Destroy|DeleteEntity|SetFlags|SetEventMask|Save|SaveProfile|CreateUserBinding|AddBinding|Open|Close|Enable|Disable|Focus|Unfocus|SetHeld)\s*\(", code), "Transport invokes a callback, service, profile operation or state mutation directly")
    require(not re.search(r"\bnew\s+SPK_(?:TabletComponent|BerylTabletRealServicesObserver)\b", code), "Manual component construction")
    require(len(re.findall(r"\bSpawnEntityPrefab\s*\(", code)) == 1, "Exactly one native factory site required")
    require(len(re.findall(r"\bRunSevenActions\s*\(", code)) == 1, "Exactly one public run site required")
    require(len(re.findall(r"\bSwitchToEditMode\s*\(", code)) == 1, "Exactly one native edit handoff required")
    require(len(re.findall(r"\bSleep\s*\(", code)) == 1 and "Sleep(200);" in text, "Exactly one predecessor deferred-world yield required")
    require(len(re.findall(r"\bthread\b", code)) == 1, "Only installed deferred-world worker permitted")
    worker = body(text, "Beryl_OpenTabletRealServicesWorld")
    ordered(worker, ['Sleep(200);', 'workerProject != "@CURRENT_GAME_PROJECT@"', 'WorldEditor editor = Workbench.GetModule(WorldEditor);', 'normalizedWorld != "@WORLD_ABSOLUTE@"', 'registered != "{BE71571A20261010}worlds/BerylTabletRealServicesN1a.ent"', 'editor.SetOpenedResource(absoluteWorld)'], "Deferred native world identity/yield order changed")
    request = body(text, "GetResponse")
    ordered(request, ['req.token != resp.token', 'resp.current_project = Workbench.GetCurrentGameProjectFile();', 'projectPath != "@CURRENT_GAME_PROJECT@"', 'req.action == "load"'], "Native request token/project guards changed")
    has(request, 'resp.source_contract_sha256 = "' + SOURCE_CONTRACT_SHA256 + '";', "Source contract differs")
    has(request, 'resp.wire_contract_sha256 = "' + WIRE_CONTRACT_SHA256 + '";', "Wire contract differs")
    has(request, 'resp.profile = "sparkos.tablet.real-services.n1a.wire.v1";', "Wire profile differs")
    for action in ("load", "status", "play", "spawn", "run", "stop"):
        has(request, 'req.action != "' + action + '"', "Unknown-action guard lost " + action)
    has(request, 'Resource.Load("{BE71571B20261010}Prefabs/BerylTabletRealServicesN1a.et")', "Owned native prefab identity differs")
    has(request, 'for (int i = 1; i <= 2; i++)', "Native two-owner spawn bound differs")
    has(request, 'IEntity owner = GetGame().SpawnEntityPrefab(prefab, runtimeWorld, null);', "Native creation world differs")
    for check in ('s_Owners[i - 1] != owner', '!SPK_BerylTabletRealServiceRegistry.s_States[i - 1]', 'owner.FindComponent(SPK_BerylTabletRealServicesObserver) != SPK_BerylTabletRealServiceRegistry.s_Observers[i - 1]', 'SPK_BerylTabletRealServiceRegistry.s_InitWitnesses.Count() != i * 2'):
        has(request, check, "Native claim identity guard changed")
    init = body(text, "ValidateInitWitnesses")
    for check in ('witness.token != expectedToken', 'witness.stage != expectedStage', 'witness.independence_observed != (expectedToken == 2)', '!witness.independent_state', '(witness.mask & EntityEvent.FRAME) == 0', 'witness.accumulator != 0', '!witness.same_state', '!witness.owner_is_game_world'):
        has(init, check, "Native init scalar contract changed")
    live = body(text, "ValidateLiveOwners")
    for check in ('!GetGame().InPlayMode()', 'owner.GetWorld() != currentWorld', 'owner.FindComponent(SPK_BerylTabletRealServicesObserver) != observer', '!observer.InitComplete()', '!observer.ClaimMatchesOwner()'):
        has(live, check, "Current native owner/component/world identity guard changed")
    run = request[request.index('if (req.action == "run")'):request.index('if (req.action == "stop")')]
    ordered(run, ['if (s_RunRequested || s_Phase != 2', 's_RunRequested = true;', 'ValidateLiveOwners()', 'RunSevenActions();', 'SPK_BerylN1WireEncoder.Capture();', '!SameInitialization(s_InitFrozen, capture)', '!ValidateFinalLiveState()', 's_Frozen = CopyReceipt(capture);'], "One-shot public execution/freeze ordering changed")
    has(run, '!s_InitFrozen', "Public run requires frozen initialization prefix")
    final = body(text, "ValidateFinalLiveState")
    has(final, 'SPK_BerylTabletRealServiceRegistry.s_Observers[i].Snapshot()', "Last live snapshot missing")
    has(final, 'SameSnapshot(last.after[i], current)', "Final live comparison missing")
    copy = body(text, "CopyReceipt")
    for array in ("rows", "caseIds", "init_rows"):
        require(not re.search(r"result\." + array + r"\s*=", mask(copy)), "Frozen scalar arrays must not alias source arrays")
        has(copy, 'source.' + array + ') result.' + array + '.Insert(', "Frozen scalar array copy missing")
    same = body(text, "SameReceipt")
    for expected in ('SameInitialization(a, b)', 'a.row_count != 44', 'b.row_count != 44', 'a.caseIds.Count() != 7', 'b.caseIds.Count() != 7', 'a.rows[i] != b.rows[i]', 'a.caseIds[j] != b.caseIds[j]', 'a.checksum != b.checksum', 'a.raw_bytes != b.raw_bytes'):
        has(same, expected, "Complete scalar receipt comparison missing")
    same_init = body(text, "SameInitialization")
    has(same_init, 'a.init_rows[i] != b.init_rows[i]', "Initialization scalar prefix comparison missing")
    stop = request[request.index('if (req.action == "stop")'):request.index('if (s_Phase == 0 && resp.world_matches')]
    ordered(stop, ['!s_Frozen', 'ValidateFinalLiveState()', 'SPK_BerylN1WireEncoder.Capture();', 'SameReceipt(s_Frozen, stopCapture)', 'PublishFrozen(resp);', 's_StopRequested = true; s_Phase = 3;', 'editor.SwitchToEditMode();', 'return resp;'], "Stop must freeze before native handoff and return without live reads")
    after_switch = stop[stop.index('editor.SwitchToEditMode();'):]
    require(not re.search(r"\b(?:Capture|ValidateLiveOwners|ValidateFinalLiveState|Snapshot|GetOwner|GetWorld|GetWidget|GetScreen)\s*\(", mask(after_switch)), "Stop performs post-handoff live/scalar capture instead of fresh status")
    progress = body(text, "Progress")
    require(not re.search(r"\b(?:ValidateLiveOwners|ValidateFinalLiveState|Snapshot|GetOwner|GetWidget|GetScreen|GetState|ClaimMatchesOwner|GetUI|GetEventMask)\s*\(", mask(progress)), "Post-stop progress follows live owner/service references")
    require(not re.search(r"s_(?:Owners|States|Observers)\s*\[", mask(progress)), "Post-stop progress indexes retained live references")
    ordered(progress, ['s_Phase == 2 && !s_RunRequested', 'EncodeInitialization(initialization)', 's_InitFrozen = CopyReceipt(initialization)', 's_Frozen && s_TraceFailure == ""', 'SPK_BerylN1WireEncoder.Capture()', 'SameReceipt(s_Frozen, current)', 's_Phase == 3 && resp.edit_mode && !resp.game_mode && !resp.in_play_mode', 's_Phase = 4;', 'if (s_Phase == 4) resp.status = "complete";'], "Native stop completion requires scalar agreement and fresh no-play edit observations")
    has(progress, 's_Phase == 4 && (!resp.edit_mode || resp.game_mode || resp.in_play_mode || !resp.world_matches || !resp.world_present)', "Repeated complete response must recheck current owned edit world")
    published = body(text, "PublishFrozen")
    has(published, 'resp.actions_ready = true; resp.executed = 7;', "Complete seven-case execution count changed")
    failed = body(text, "FailureResponse")
    for check in ('resp.status = "failure";', 'if (s_OutsideDomain) resp.status = "unavailable";', 'resp.outside_domain = s_OutsideDomain;', 'resp.failures = 1; resp.executed = 0;', 'resp.rows.Clear(); resp.caseIds.Clear(); resp.init_rows.Clear();'):
        has(failed, check, "Failure/outside-domain response was laundered into success")
    require('frames_ready' not in code and 'frame_counts' not in code, "Predecessor frame evidence cannot be reused for service execution")
    response = re.search(r'class BerylTabletRealServicesNativeResponse : JsonApiStruct\s*\{', code)
    require(response is not None, "Typed response missing")
    response_text = block(text, response.end() - 1)
    declaration = response_text[:response_text.index('void BerylTabletRealServicesNativeResponse()')]
    actual_fields = []
    field_types = {}
    for kind, names in re.findall(r'(?m)^\s*(string|bool|int)\s+([^;]+);', declaration):
        for name in names.split(','):
            name = name.strip()
            actual_fields.append(name)
            field_types[name] = kind
    for name in re.findall(r'(?m)^\s*ref array<string>\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*\{\};', declaration):
        actual_fields.append(name)
        field_types[name] = 'array<string>'
    require(tuple(actual_fields) == FIELDS, "Typed response field order/types changed")
    require(all(field_types[n] == 'string' for n in STRING_FIELDS) and all(field_types[n] == 'bool' for n in BOOL_FIELDS) and all(field_types[n] == 'int' for n in INT_FIELDS), "Typed response scalar types changed")
    registered = tuple(re.findall(r'RegV\("([A-Za-z_][A-Za-z0-9_]*)"\)', response_text))
    require(len(registered) == len(FIELDS) and len(set(registered)) == len(FIELDS) and set(registered) == set(FIELDS), "Each typed response field needs exactly one RegV")
    require(tuple(re.findall(r'RegV\("([A-Za-z_][A-Za-z0-9_]*)"\)', body(text, "BerylTabletRealServicesNativeRequest"))) == ("token", "action"), "Request registration differs")
    if pin:
        require(sha(value) == TEMPLATE_SHA256, "Native transport differs from frozen reviewed template")
    return {"status": "success", "bytes": len(value), "sha256": sha(value), "response_fields": list(FIELDS), "placeholders": ["@TOKEN@", "@SOURCE_SHA256@", "@CURRENT_GAME_PROJECT@", "@WORLD_ABSOLUTE@"], "scope": "source_only_not_engine_execution"}


def self_test():
    original = read(TEMPLATE)
    text = original.decode('utf8')
    results = []

    def positive(case_id, action):
        try:
            detail = action()
            results.append({"case_id": case_id, "status": "success", "detail": detail})
        except Exception as exc:
            results.append({"case_id": case_id, "status": "failure", "error": str(exc)})

    def reject(case_id, value, pin=False):
        try:
            validate_source(value, pin=pin)
        except SourceFailure as exc:
            results.append({"case_id": case_id, "status": "success", "rejection": str(exc)})
        else:
            results.append({"case_id": case_id, "status": "failure", "error": "Deliberate source fault accepted"})

    def mutant(case_id, old, new):
        require(old in text and old != new, "Invalid deliberate fault: " + case_id)
        reject(case_id, text.replace(old, new, 1).encode('utf8'))

    checked = validate_source(original)
    positives = (
        ("positive.frozen-template", lambda: checked),
        ("positive.typed-envelope", lambda: {"response_fields": len(checked['response_fields']), "registered": True}),
        ("positive.native-factory", lambda: {"native_factory_sites": 1, "owner_bound": 2}),
        ("positive.native-init-witnesses", lambda: {"init_witnesses": 4, "original_native_callback": "not_manually_called"}),
        ("positive.single-public-run", lambda: {"RunSevenActions_sites": 1, "case_count": 7}),
        ("positive.freeze-copy", lambda: {"rows": 44, "init_rows": 4, "array_aliasing": False}),
        ("positive.scalar-handoff", lambda: {"after_stop": "plain_records_only"}),
        ("positive.pending-versus-complete", lambda: {"pending_executed_after_run": 7, "terminal_phase": 4}),
        ("positive.source-identities", lambda: {"source_contract": sha(read(PACKAGE/'contract.json')), "wire_contract": sha(read(PACKAGE/'wire-contract.json'))}),
        ("positive.preserved-predecessor", lambda: {"predecessor_sha256": sha(read(ROOT/'packages/sparkos/tablet-native-runtime-probe/rpc.c.in'))}),
    )
    require(sha(read(PACKAGE/'contract.json')) == SOURCE_CONTRACT_SHA256 and sha(read(PACKAGE/'wire-contract.json')) == WIRE_CONTRACT_SHA256, "Contract input changed")
    require(sha(read(ROOT/'packages/sparkos/tablet-native-runtime-probe/rpc.c.in')) == N0_SHA256, "Frozen predecessor changed")
    for case_id, action in positives:
        positive(case_id, action)
    reject('negative.nonbytes', text)
    reject('negative.byte-budget', b'x'*(MAX_BYTES+1))
    reject('negative.crlf', original.replace(b'\n', b'\r\n'))
    faults = (
        ('negative.unknown-placeholder', '@TOKEN@', '@UNKNOWN@'),
        ('negative.missing-project-pin', 'projectPath != "@CURRENT_GAME_PROJECT@"', 'projectPath == "@CURRENT_GAME_PROJECT@"'),
        ('negative.missing-worker-project-pin', 'workerProject != "@CURRENT_GAME_PROJECT@"', 'workerProject == "@CURRENT_GAME_PROJECT@"'),
        ('negative.missing-token-pin', 'req.token != resp.token', 'req.token == resp.token'),
        ('negative.wrong-source-contract', SOURCE_CONTRACT_SHA256, '0'*64),
        ('negative.wrong-wire-contract', WIRE_CONTRACT_SHA256, '0'*64),
        ('negative.wrong-world-id', '{BE71571A20261010}', '{BE71570A20261010}'),
        ('negative.wrong-prefab-id', '{BE71571B20261010}', '{BE71570B20261010}'),
        ('negative.manual-init', 's_Phase = 2;', 's_Phase = 2; owner.OnPostInit(owner);'),
        ('negative.manual-frame', 's_Phase = 2;', 's_Phase = 2; observer.EOnFrame(owner, 0.1);'),
        ('negative.manual-delete', 's_Phase = 2;', 's_Phase = 2; observer.OnDelete(owner);'),
        ('negative.manual-component', 's_Phase = 2;', 's_Phase = 2; new SPK_TabletComponent();'),
        ('negative.mask-write', 's_Phase = 2;', 's_Phase = 2; observer.SetEventMask(owner, 0);'),
        ('negative.flag-write', 's_Phase = 2;', 's_Phase = 2; owner.SetFlags(EntityFlags.ACTIVE, false);'),
        ('negative.profile-write', 's_Phase = 2;', 's_Phase = 2; SaveProfile();'),
        ('negative.duplicate-native-spawn', 'IEntity owner = GetGame().SpawnEntityPrefab(prefab, runtimeWorld, null);', 'IEntity owner = GetGame().SpawnEntityPrefab(prefab, runtimeWorld, null); GetGame().SpawnEntityPrefab(prefab, runtimeWorld, null);'),
        ('negative.spawn-world', 'SpawnEntityPrefab(prefab, runtimeWorld, null)', 'SpawnEntityPrefab(prefab, null, null)'),
        ('negative.claim-owner', 's_Owners[i - 1] != owner', 's_Owners[i - 1] == owner'),
        ('negative.claim-component', 'owner.FindComponent(SPK_BerylTabletRealServicesObserver) != SPK_BerylTabletRealServiceRegistry.s_Observers[i - 1]', 'owner.FindComponent(SPK_BerylTabletRealServicesObserver) == SPK_BerylTabletRealServiceRegistry.s_Observers[i - 1]'),
        ('negative.claim-state', '!SPK_BerylTabletRealServiceRegistry.s_States[i - 1]', 'SPK_BerylTabletRealServiceRegistry.s_States[i - 1]'),
        ('negative.missing-init-order', 'witness.stage != expectedStage', 'witness.stage == expectedStage'),
        ('negative.missing-init-mask', '(witness.mask & EntityEvent.FRAME) == 0', '(witness.mask & EntityEvent.FRAME) != 0'),
        ('negative.shared-state', '!witness.independent_state', 'witness.independent_state'),
        ('negative.missing-world-owner', 'owner.GetWorld() != currentWorld', 'owner.GetWorld() == currentWorld'),
        ('negative.repeat-run-guard', 's_RunRequested || s_Phase != 2', '!s_RunRequested || s_Phase != 2'),
        ('negative.run-marker-order', 's_RunRequested = true;', 's_RunRequested = false;'),
        ('negative.duplicate-public-run', 'bool returned = SPK_BerylTabletRealServiceRegistry.RunSevenActions();', 'bool returned = SPK_BerylTabletRealServiceRegistry.RunSevenActions(); SPK_BerylTabletRealServiceRegistry.RunSevenActions();'),
        ('negative.run-count', 'resp.executed = 7;', 'resp.executed = 6;'),
        ('negative.missing-final-snapshot', '!ValidateFinalLiveState()', 'false'),
        ('negative.frozen-array-alias', 'foreach (string row : source.rows) result.rows.Insert(row);', 'result.rows = source.rows;'),
        ('negative.init-prefix-omitted', 'a.init_rows[i] != b.init_rows[i]', 'false'),
        ('negative.main-prefix-omitted', 'a.rows[i] != b.rows[i]', 'false'),
        ('negative.case-prefix-omitted', 'a.caseIds[j] != b.caseIds[j]', 'false'),
        ('negative.scalar-owner-getter', 'resp.phase = s_Phase; resp.stop_requested = s_StopRequested;', 'resp.phase = s_Phase; resp.stop_requested = s_StopRequested; SPK_BerylTabletRealServiceRegistry.s_Owners[0].GetWorld();'),
        ('negative.scalar-widget-getter', 'resp.phase = s_Phase; resp.stop_requested = s_StopRequested;', 'resp.phase = s_Phase; resp.stop_requested = s_StopRequested; SPK_BerylTabletRealServiceRegistry.s_Widget.GetWidget();'),
        ('negative.scalar-live-validator', 'resp.phase = s_Phase; resp.stop_requested = s_StopRequested;', 'resp.phase = s_Phase; resp.stop_requested = s_StopRequested; ValidateLiveOwners();'),
        ('negative.handoff-no-frozen-receipt', 's_Phase != 2 || !s_RunRequested || !s_Frozen', 's_Phase != 2 || !s_RunRequested || false'),
        ('negative.handoff-after-stop-capture', 'editor.SwitchToEditMode();', 'editor.SwitchToEditMode(); SPK_BerylN1WireEncoder.Capture();'),
        ('negative.complete-before-edit', 's_Phase == 3 && resp.edit_mode && !resp.game_mode && !resp.in_play_mode', 's_Phase == 2 && resp.edit_mode && !resp.game_mode && !resp.in_play_mode'),
        ('negative.complete-in-play', 's_Phase == 3 && resp.edit_mode && !resp.game_mode && !resp.in_play_mode', 's_Phase == 3 && resp.edit_mode && resp.game_mode && resp.in_play_mode'),
        ('negative.failure-laundering', 'resp.status = "failure";\n        if (s_OutsideDomain)', 'resp.status = "complete";\n        if (s_OutsideDomain)'),
        ('negative.outside-domain-laundering', 'if (s_OutsideDomain) resp.status = "unavailable";', 'if (s_OutsideDomain) resp.status = "complete";'),
        ('negative.duplicate-regv', 'RegV("outside_domain");', 'RegV("outside_domain"); RegV("outside_domain");'),
        ('negative.missing-regv', 'RegV("outside_domain");', ''),
        ('negative.response-field', 'int phase, executed, failures, owner_count, row_count, checksum, init_count, init_checksum, raw_bytes;', 'int phase, executed, failures, owner_count, row_count, checksum, init_count, init_checksum;'),
        ('negative.old-frame-fields', 'ref array<string> init_rows = {};', 'ref array<string> init_rows = {}; ref array<int> frame_counts = {};'),
        ('negative.extra-yield', 'Sleep(200);', 'Sleep(200); Sleep(1);'),
    )
    for fault in faults:
        mutant(*fault)
    reject('negative.unpinned-whitespace', original + b'\n', pin=True)
    require(tuple(item['case_id'] for item in results) == CASE_IDS, "Self-test expected case inventory changed")
    directory = Path(tempfile.mkdtemp(prefix='tablet-real-services-runtime-source-', dir=ROOT/'build'))
    failures = sum(item['status'] != 'success' for item in results)
    receipt = {"schema_version": 1, "operation": "tablet_real_services_runtime_source_self_test", "status": "success" if failures == 0 else "failure", "scope": "source_only_not_engine_execution", "executed": len(results), "failures": failures, "caseIds": list(CASE_IDS), "source": {"path": str(TEMPLATE), "bytes": len(original), "sha256": sha(original)}, "checker": {"path": str(Path(__file__).resolve()), "sha256": sha(read(Path(__file__)))}, "results": results, "runtime": "not_run", "native_services": "not_run", "engine_compilation": "not_run"}
    result = directory/'result.json'
    result.write_text(json.dumps(receipt, indent=2, ensure_ascii=True)+'\n', encoding='utf8')
    print(json.dumps({"result": str(result), "status": receipt['status'], "executed": len(results), "failures": failures, "sha256": sha(result.read_bytes())}))
    return int(failures != 0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--check-source', type=Path)
    args = parser.parse_args()
    if args.self_test:
        return self_test()
    if args.check_source:
        print(json.dumps(validate_source(read(args.check_source)), sort_keys=True))
        return 0
    parser.error('Select --self-test or --check-source')


if __name__ == '__main__':
    raise SystemExit(main())
