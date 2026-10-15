#!/usr/bin/env python3
"""Independent admission of five preserved tablet-suite runtime receipts.

This module never launches a process, executes engine code, or promotes files.
Its pure fixtures validate receipt admission, not suite/lifecycle execution.
"""
from pathlib import Path
import argparse
import copy
import hashlib
import json
import re
import sys

PROFILE = "sparkos.tablet.existing-suites-runtime.v1"
PROJECT = "BerylTabletSuitesPrototype"
SUITES = ("ui", "screen", "actions", "clicks", "schema")
SCHEMA_RESOURCE = "{B37EEB64E149CBAD}Prefabs/SPK_Tablet.et"
SELECTIONS = [{"suite": name, "arg": SCHEMA_RESOURCE if name == "schema" else ""} for name in SUITES]
DETAILS = {
    "ui": "ui suite passed",
    "screen": "screen suite passed",
    "actions": "actions suite passed (29 controls)",
    "clicks": "clicks suite passed (23 controls)",
}
COMPONENTS = ("MeshObject", "InventoryItemComponent", "SPK_TabletComponent", "SPK_TabletGadgetComponent",
              "SPK_DroneInputComponent", "SCR_EditableEntityComponent")
# This tuple identifies membership, not native enumeration order. The preserved
# handler emits GetComponent(i), whose installed declaration has no order promise.
SCHEMA_POLICY = "six-exact-distinct-components-preserve-native-order.v2"
Q93_SCHEMA_DETAIL = (
    " InventoryItemComponent[Enabled,components,Attributes,WbPlacementFromAttributes]"
    " MeshObject[Enabled,Object,Materials,LODFactors,PixelSizeScale,CastShadow,InheritSkeleton,CastFarShadow,PixelSizeFilter,InheritVisibility,InheritLOD,RainOccluder,WetnessOccluder,WetnessAdder,ObjectHeightmapBias,ObjectHeightmapTraceBias,ReceiveLight,ClutterOccluder,ClutterOccluderClipPlane,ClutterOccluderEnlarge,BoundingBox]"
    " SCR_EditableEntityComponent[Enabled,components,m_EntityType,m_UIInfo,m_sIconBoneName,m_EntityInteraction,m_VariantData,m_bAutoRegister,m_vIconPos,m_bVisible,m_bStatic,m_fMaxDrawDistance,m_AccessKey,m_Flags]"
    " SPK_DroneInputComponent[Enabled,components,m_bEnabled,m_fCollectiveRate,m_fGimbalRateDegS,m_fZoomRate]"
    " SPK_TabletComponent[Enabled,components]"
    " SPK_TabletGadgetComponent[Enabled,components,m_eAnimVariable,m_eUseMask,m_vEquipmentSlotOffset,m_fWeaponNoFireTime,m_bCanBeHeld,m_fClothesOffsetStrength]"
)
HASH = re.compile(r"[0-9a-f]{64}\Z")
IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")
MAX_JSON_BYTES = 16 * 1024 * 1024
MAX_DETAIL_BYTES = 65536
LIMITS = {"stage_ms": 30000, "rpc_ms": 8000, "total_ms": 180000, "cleanup_ms": 5000, "max_polls": 64,
          "native_launch_and_bridge_calls_not_hard_cancelled": True, "raw_logs_aggregate_bytes": 67108864}
NO_EXECUTION = ("play", "spawn", "save", "world_open", "tablet_callback_delivery", "physical_ui_input",
                "multiplayer", "visual_review", "policy_changes")


class SuiteReceiptFailure(Exception):
    def __init__(self, message, status="failure", pointer="/"):
        super().__init__(message)
        self.status = status
        self.pointer = pointer


def require(condition, message, pointer="/", status="failure"):
    if not condition:
        raise SuiteReceiptFailure(message, status, pointer)


def names(value, expected, pointer):
    require(type(value) is dict and set(value) == set(expected), "Exact object fields required", pointer)


def integer(value, minimum, maximum, pointer):
    require(type(value) is int and minimum <= value <= maximum, "Bounded JSON integer required", pointer)
    return value


def text(value, bound, pointer, allow_empty=False):
    require(type(value) is str and (allow_empty or bool(value)) and "\0" not in value, "Bounded text required", pointer)
    try:
        size = len(value.encode("utf-8"))
    except UnicodeEncodeError as exc:
        raise SuiteReceiptFailure("Invalid Unicode scalar in text", pointer=pointer) from exc
    require(size <= bound, "Bounded text required", pointer)
    return value


def digest(value, pointer):
    require(type(value) is str and HASH.fullmatch(value), "Lowercase SHA-256 required", pointer)
    return value


def typed_equal(a, b, depth=0):
    if depth > 64:
        return False
    if type(a) is not type(b):
        return False
    if type(a) is dict:
        return set(a) == set(b) and all(typed_equal(a[k], b[k], depth + 1) for k in a)
    if type(a) is list:
        return len(a) == len(b) and all(typed_equal(x, y, depth + 1) for x, y in zip(a, b))
    return a == b


def path_key(value, pointer):
    text(value, 4096, pointer)
    require(re.match(r"[A-Za-z]:[/\\]", value) is not None and not any(
        part in (".", "..") for part in value.replace("\\", "/").split("/")),
        "Absolute Windows path without traversal required", pointer)
    return value.replace("\\", "/").casefold()


def same_path(a, b, pointer):
    require(path_key(a, pointer) == path_key(b, pointer), "Pinned absolute path differs", pointer, "stale_input")


def decode_json(raw, pointer="/"):
    if type(raw) is bytes:
        require(len(raw) <= MAX_JSON_BYTES, "JSON input exceeds bound", pointer)
        try:
            raw = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise SuiteReceiptFailure("JSON input is not UTF-8", pointer=pointer) from exc
    text(raw, MAX_JSON_BYTES, pointer)

    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise SuiteReceiptFailure("Duplicate JSON field", pointer=pointer)
            result[key] = value
        return result

    def constant(_):
        raise SuiteReceiptFailure("Nonfinite JSON constant is not admitted", pointer=pointer)

    try:
        return json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)
    except (json.JSONDecodeError, RecursionError) as exc:
        raise SuiteReceiptFailure("Malformed or excessively nested JSON", pointer=pointer) from exc


def validate_identity(value, expected, pointer):
    names(value, ("token", "profile", "source_sha256"), pointer)
    for key in value:
        text(value[key], 256, pointer + "/" + key)
    require(typed_equal(value, {key: expected[key] for key in ("token", "profile", "source_sha256")}),
            "Compiled identity differs", pointer, "stale_input")
    return dict(value)


def validate_schema(detail, pointer):
    text(detail, MAX_DETAIL_BYTES, pointer)
    position = 0
    rows = []
    pattern = re.compile(r"\s+([A-Za-z_][A-Za-z0-9_]*)\[([^\[\]]*)\]")
    while position < len(detail):
        match = pattern.match(detail, position)
        require(match is not None, "Malformed tablet entity component dump", pointer)
        class_name, payload = match.groups()
        fields = [] if payload == "" else payload.split(",")
        require(len(fields) <= 256 and all(len(field) <= 128 and IDENTIFIER.fullmatch(field) for field in fields) and
                len(fields) == len(set(fields)), "Malformed or repeated component variable names", pointer)
        rows.append({"class": class_name, "fields": fields})
        require(len(rows) <= len(COMPONENTS), "Too many tablet components", pointer)
        position = match.end()
    classes = [row["class"] for row in rows]
    require(len(classes) == len(COMPONENTS) and len(set(classes)) == len(COMPONENTS) and
            set(classes) == set(COMPONENTS), "Expected six exact distinct tablet components", pointer)
    return rows


def validate_suite(value, name, pointer):
    names(value, ("ok", "detail"), pointer)
    integer(value["ok"], -2147483648, 2147483647, pointer + "/ok")
    text(value["detail"], MAX_DETAIL_BYTES, pointer + "/detail")
    require(value["ok"] == 1, "Executed source suite returned failure", pointer + "/ok")
    if name == "schema":
        parsed = validate_schema(value["detail"], pointer + "/detail")
        return {"id": name, "status": "success", "response": dict(value), "components": parsed}
    require(value["detail"] == DETAILS[name], "Source-defined suite success detail differs", pointer + "/detail")
    return {"id": name, "status": "success", "response": dict(value)}


def validate_reply(reply, function, pointer):
    names(reply, ("Ok", "Function", "ErrorCode", "Response", "Raw"), pointer)
    require(reply["Ok"] is True and reply["Function"] == function and type(reply["Function"]) is str and
            reply["ErrorCode"] == "Ok" and type(reply["ErrorCode"]) is str,
            "Exact successful installed bridge envelope required", pointer)
    text(reply["Raw"], 1024 * 1024, pointer + "/Raw")
    raw = decode_json(reply["Raw"], pointer + "/Raw")
    require(typed_equal(raw, reply["Response"]), "Untouched decoded response differs from raw JSON", pointer + "/Response")
    return reply["Response"]


def validate_loaded(value, expected, pointer):
    names(value, ("Loaded Projects",), pointer)
    projects = value["Loaded Projects"]
    require(type(projects) is list and 1 <= len(projects) <= 8 and all(type(p) is str for p in projects) and
            len(projects) == len(set(projects)) and expected["project_id"] in projects and
            set(projects) <= {expected["project_id"], "ArmaReforger", "core"},
            "Selected addon inventory differs or contains an unrelated addon", pointer, "stale_input")
    return list(projects)


def expected_calls(expected):
    calls = [("GetLoadedProjects", {}, None)]
    sites = [("initial", 1)]
    calls.append(("BerylTabletSuiteIdentity", {"token": expected["token"]}, "initial"))
    for selection in SELECTIONS:
        site = "before." + selection["suite"]
        sites.append((site, len(calls)))
        calls.append(("BerylTabletSuiteIdentity", {"token": expected["token"]}, site))
        calls.append(("SPK_MeshSelfTest", dict(selection), selection["suite"]))
        site = "after." + selection["suite"]
        sites.append((site, len(calls)))
        calls.append(("BerylTabletSuiteIdentity", {"token": expected["token"]}, site))
    sites.append(("final", len(calls)))
    calls.append(("BerylTabletSuiteIdentity", {"token": expected["token"]}, "final"))
    return calls, sites


def validate_expected(expected):
    names(expected, ("token", "profile", "source_sha256", "project_dir", "project_id", "engine", "engine_version",
                     "tools", "manifest_path", "manifest_sha256", "manifest", "adapter_sha256", "argv"), "/expected")
    require(expected["profile"] == PROFILE and expected["project_id"] == PROJECT, "Installed suite profile required", "/expected")
    for key in ("token", "source_sha256", "manifest_sha256", "adapter_sha256"):
        digest(expected[key], "/expected/" + key)
    path_key(expected["project_dir"], "/expected/project_dir")
    path_key(expected["manifest_path"], "/expected/manifest_path")
    text(expected["engine_version"], 128, "/expected/engine_version")
    names(expected["engine"], ("path", "bytes", "sha256"), "/expected/engine")
    path_key(expected["engine"]["path"], "/expected/engine/path")
    integer(expected["engine"]["bytes"], 1, 1024 * 1024 * 1024, "/expected/engine/bytes")
    digest(expected["engine"]["sha256"], "/expected/engine/sha256")
    names(expected["tools"], ("Find-Workbench.ps1", "Invoke-WorkbenchRpc.ps1"), "/expected/tools")
    for name, value in expected["tools"].items():
        digest(value, "/expected/tools/" + name)
    manifest = expected["manifest"]
    names(manifest, ("schema_version", "profile", "files"), "/expected/manifest")
    require(type(manifest["schema_version"]) is int and manifest["schema_version"] == 1 and manifest["profile"] == PROFILE,
            "Exact manifest version/profile required", "/expected/manifest")
    require(type(manifest["files"]) is dict and len(manifest["files"]) == 87, "Eighty-seven source identities required", "/expected/manifest/files")
    case_names = set()
    for name, value in manifest["files"].items():
        text(name, 512, "/expected/manifest/files")
        require("\\" not in name and not name.startswith("/") and ":" not in name and
                all(part not in ("", ".", "..") for part in name.split("/")) and name.casefold() not in case_names,
                "Unsafe or duplicate staged relative path", "/expected/manifest/files")
        case_names.add(name.casefold())
        digest(value, "/expected/manifest/files/" + name)
    require(type(expected["argv"]) is list and len(expected["argv"]) == 6 and
            expected["argv"][0] == "-gproj" and expected["argv"][2:] ==
            ["-noOpenLastResource", "-scriptAuthorizeAll", "-wbmodule=WorldEditor", "-run"],
            "Exact module activation argv without load required", "/expected/argv")
    same_path(expected["argv"][1], expected["project_dir"].rstrip("/\\") + "/addon.gproj", "/expected/argv/1")


def validate_runtime(record, expected):
    validate_expected(expected)
    fields = ("schema_version", "stage", "status", "profile", "mechanism", "token", "source_sha256", "project_id", "scope",
              "engine_path", "engine_sha256", "engine_bytes", "engine_version", "tools", "adapter_sha256", "input_manifest",
              "staged_inputs", "engine_outputs", "arguments", "startup", "session", "loaded_projects", "suite_selections",
              "suites", "identity_observations", "completion", "rpcs", "session_checks", "port_checks", "port_query_errors",
              "raw_logs", "log_directories", "evidence_errors", "cleanup", "cleanup_errors", "failure", "elapsed_ms", "limits",
              "requested_editor_context", "raw_log_observation") + NO_EXECUTION
    names(record, fields, "/")
    require(type(record["schema_version"]) is int and record["schema_version"] == 1 and record["status"] == "success" and
            record["stage"] == "suites_complete", "Complete successful suite transport receipt required", "/status")
    require(record["mechanism"] == "owned_empty_editor_existing_suites" and
            record["scope"] == "existing MESH ui, screen, actions, clicks and schema suites only" and
            record["requested_editor_context"] == "WorldEditor startup requested; no resource load requested",
            "Fixed experimental operation scope required", "/scope")
    for key in ("token", "profile", "source_sha256", "project_id", "engine_version", "tools", "adapter_sha256"):
        require(typed_equal(record[key], expected[key]), "Pinned operation identity differs", "/" + key, "stale_input")
    require(record["engine_sha256"] == expected["engine"]["sha256"] and type(record["engine_sha256"]) is str and
            type(record["engine_bytes"]) is int and record["engine_bytes"] == expected["engine"]["bytes"],
            "Engine content identity differs", "/engine_sha256", "stale_input")
    same_path(record["engine_path"], expected["engine"]["path"], "/engine_path")
    require(typed_equal(record["limits"], LIMITS), "Fixed budgets and capture limits required", "/limits")
    for key in NO_EXECUTION:
        require(record[key] == "not_run" and type(record[key]) is str, "Unexecuted scope must remain explicit", "/" + key)
    require(record["failure"] is None and record["evidence_errors"] == [] and type(record["evidence_errors"]) is list and
            record["cleanup_errors"] == [] and type(record["cleanup_errors"]) is list and
            record["cleanup"] in ("owned_process_stopped", "owned_process_already_exited"),
            "Failure-free evidence and confirmed owned cleanup required", "/cleanup")
    require(record["raw_log_observation"] == "snapshot_after_confirmed_owned_exit",
            "Retained logs must follow confirmed owned exit", "/raw_log_observation")
    elapsed = integer(record["elapsed_ms"], 0, LIMITS["total_ms"] - 1, "/elapsed_ms")
    names(record["input_manifest"], ("path", "sha256"), "/input_manifest")
    same_path(record["input_manifest"]["path"], expected["manifest_path"], "/input_manifest/path")
    require(record["input_manifest"]["sha256"] == expected["manifest_sha256"] and
            typed_equal(record["staged_inputs"], expected["manifest"]), "Pinned manifest or staged source hashes differ",
            "/staged_inputs", "stale_input")
    require(typed_equal(record["arguments"], expected["argv"]), "Recorded native argv differs", "/arguments", "stale_input")
    names(record["session"], ("process_id", "start_ticks", "executable", "project", "reused", "start_time"), "/session")
    session = record["session"]
    pid = integer(session["process_id"], 1, 2147483647, "/session/process_id")
    ticks = integer(session["start_ticks"], 1, 3155378975999999999, "/session/start_ticks")
    same_path(session["executable"], expected["engine"]["path"], "/session/executable")
    same_path(session["project"], expected["project_dir"], "/session/project")
    require(session["reused"] is False, "Owned fresh session required", "/session/reused")
    text(session["start_time"], 128, "/session/start_time")
    require(re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{7}Z", session["start_time"]) is not None,
            "Native UTC start-time observation required", "/session/start_time")
    startup = record["startup"]
    names(startup, ("mechanism", "argv", "working_directory", "use_shell_execute", "create_no_window", "window_style",
                    "launch_returned", "polls", "process_id"), "/startup")
    require(startup["mechanism"] == record["mechanism"] and typed_equal(startup["argv"], expected["argv"]) and
            startup["use_shell_execute"] is False and startup["create_no_window"] is True and
            startup["window_style"] == "Hidden" and startup["launch_returned"] is True and
            type(startup["process_id"]) is int and startup["process_id"] == pid,
            "Hidden non-shell owned launch contract differs", "/startup")
    path_key(startup["working_directory"], "/startup/working_directory")
    polls = integer(startup["polls"], 0, 63, "/startup/polls")
    ports = record["port_checks"]
    require(type(ports) is list and len(ports) == polls + 1, "Complete bounded listener observations required", "/port_checks")
    last_port = -1
    for index, port in enumerate(ports):
        pointer = "/port_checks/" + str(index)
        names(port, ("elapsed_ms", "listening", "owning_process"), pointer)
        timestamp = integer(port["elapsed_ms"], 0, elapsed, pointer + "/elapsed_ms")
        require(timestamp >= last_port and type(port["listening"]) is bool, "Ordered typed listener observation required", pointer)
        last_port = timestamp
        if index == len(ports) - 1:
            require(port["listening"] is True and type(port["owning_process"]) is int and port["owning_process"] == pid,
                    "Final listener must belong to retained owned process", pointer)
        else:
            require(port["listening"] is False and port["owning_process"] is None, "No foreign listener or retry after ready", pointer)
    queries = record["port_query_errors"]
    require(type(queries) is list and len(queries) <= 128, "Bounded listener diagnostics required", "/port_query_errors")
    for index, item in enumerate(queries):
        pointer = "/port_query_errors/" + str(index)
        names(item, ("elapsed_ms", "category", "id", "message"), pointer)
        integer(item["elapsed_ms"], ports[0]["elapsed_ms"], elapsed, pointer + "/elapsed_ms")
        require(item["category"] == "ObjectNotFound", "Only absent-listener inventory may remain pending", pointer)
        text(item["id"], 4096, pointer + "/id")
        text(item["message"], 4096, pointer + "/message")
    calls, sites = expected_calls(expected)
    require(type(record["rpcs"]) is list and len(record["rpcs"]) == len(calls), "Exact eighteen RPC ledger required", "/rpcs")
    expected_sites = ["startup.identity"] + ["port.check"] * len(ports)
    for function, _, _ in calls:
        expected_sites += ["before." + function, "after." + function]
    checks = record["session_checks"]
    require(type(checks) is list and len(checks) == len(expected_sites), "Complete boundary ownership observations required", "/session_checks")
    last = -1
    for index, (check, site) in enumerate(zip(checks, expected_sites)):
        pointer = "/session_checks/" + str(index)
        names(check, ("site", "process_id", "start_ticks", "executable", "elapsed_ms"), pointer)
        timestamp = integer(check["elapsed_ms"], 0, elapsed, pointer + "/elapsed_ms")
        require(check["site"] == site and type(check["process_id"]) is int and check["process_id"] == pid and
                type(check["start_ticks"]) is int and check["start_ticks"] == ticks and timestamp >= last,
                "Owned PID/start and ordered boundary site differ", pointer, "stale_input")
        same_path(check["executable"], expected["engine"]["path"], pointer + "/executable")
        last = timestamp
    for index, port in enumerate(ports):
        require(checks[index + 1]["elapsed_ms"] >= port["elapsed_ms"], "Listener identity must follow its native query", "/port_checks")
    require(ports[0]["elapsed_ms"] >= checks[0]["elapsed_ms"] and
            checks[len(ports) + 1]["elapsed_ms"] >= last_port and last_port - checks[0]["elapsed_ms"] < LIMITS["stage_ms"],
            "Listener/first RPC ordering or bounded startup observation differs", "/session_checks")
    require(all(item["elapsed_ms"] <= checks[len(ports) + 1]["elapsed_ms"] for item in queries) and
            all(a["elapsed_ms"] <= b["elapsed_ms"] for a, b in zip(queries, queries[1:])),
            "Listener diagnostics must precede the first RPC and remain ordered", "/port_query_errors")
    normalized = []
    group_times = {}
    offset = 1 + len(ports)
    for index, (call, specification) in enumerate(zip(record["rpcs"], calls)):
        function, params, meaning = specification
        pointer = "/rpcs/" + str(index)
        names(call, ("stage", "function", "params", "elapsed_ms", "timeout_ms", "result", "normalized_response", "failure",
                     "failure_kind", "duration_ms"), pointer)
        stage = "startup" if index == 0 else "identity.initial" if meaning == "initial" else "identity.final" if meaning == "final" else "suite." + (meaning.split(".")[-1])
        require(call["stage"] == stage and call["function"] == function and typed_equal(call["params"], params) and
                call["failure"] is None and call["failure_kind"] is None, "Fixed RPC stage/function/parameters or outcome differs", pointer)
        start = integer(call["elapsed_ms"], 0, elapsed, pointer + "/elapsed_ms")
        timeout = integer(call["timeout_ms"], 1, LIMITS["rpc_ms"], pointer + "/timeout_ms")
        duration = integer(call["duration_ms"], 0, timeout - 1, pointer + "/duration_ms")
        before, after = checks[offset + index * 2:offset + index * 2 + 2]
        # The adapter reports separate integer-millisecond stopwatch floors.
        # One unit permits only that representational boundary; duration itself
        # still must be strictly below the exact selected response deadline.
        require(before["elapsed_ms"] <= start <= after["elapsed_ms"] and after["elapsed_ms"] - start < timeout and
                after["elapsed_ms"] <= start + duration + 1 and start + duration <= elapsed + 1,
                "RPC paid duration or boundary time exceeds its deadline", pointer)
        if index:
            previous = record["rpcs"][index - 1]
            require(before["elapsed_ms"] + 1 >= previous["elapsed_ms"] + previous["duration_ms"],
                    "RPC capture overlaps the next operation", pointer)
        group_times.setdefault(stage, [start, start + duration])[1] = start + duration
        value = validate_reply(call["result"], function, pointer + "/result")
        if index == 0:
            validate_loaded(value, expected, pointer + "/result/Response")
            require(call["normalized_response"] is None, "Builtin inventory has no invented normalization", pointer)
        elif function == "BerylTabletSuiteIdentity":
            validate_identity(value, expected, pointer + "/result/Response")
            require(typed_equal(call["normalized_response"], value), "Identity normalization differs from actual reply", pointer)
        else:
            validate_suite(value, params["suite"], pointer + "/result/Response")
            require(typed_equal(call["normalized_response"], value), "Suite normalization differs from actual reply", pointer)
        normalized.append(value)
    require(all(end - start < LIMITS["stage_ms"] for start, end in group_times.values()), "Recorded stage span exceeds budget", "/rpcs")
    require(typed_equal(record["loaded_projects"], record["rpcs"][0]["result"]), "Loaded-project receipt is not its actual RPC", "/loaded_projects")
    require(typed_equal(record["suite_selections"], SELECTIONS), "Five fixed suite selections required", "/suite_selections")
    identities = record["identity_observations"]
    require(type(identities) is list and len(identities) == len(sites), "Twelve identity observations required", "/identity_observations")
    for index, (item, specification) in enumerate(zip(identities, sites)):
        site, rpc_index = specification
        pointer = "/identity_observations/" + str(index)
        names(item, ("site", "rpc_index", "response"), pointer)
        require(item["site"] == site and type(item["rpc_index"]) is int and item["rpc_index"] == rpc_index and
                typed_equal(item["response"], normalized[rpc_index]), "Identity site must name its exact actual reply", pointer)
    require(type(record["suites"]) is list and len(record["suites"]) == 5, "Complete five source-suite receipts required", "/suites")
    summaries = []
    for index, (item, selection) in enumerate(zip(record["suites"], SELECTIONS)):
        pointer = "/suites/" + str(index)
        names(item, ("suite", "arg", "rpc_index", "response", "status"), pointer)
        rpc_index = 3 + index * 3
        require(item["suite"] == selection["suite"] and item["arg"] == selection["arg"] and item["status"] == "success" and
                type(item["rpc_index"]) is int and item["rpc_index"] == rpc_index and typed_equal(item["response"], normalized[rpc_index]),
                "Suite receipt must name its fixed exact actual reply", pointer)
        summaries.append(validate_suite(item["response"], selection["suite"], pointer + "/response"))
    require(typed_equal(record["completion"], {"suite_count": 5, "identity_count": 12, "suite_ids": list(SUITES), "requests_executed": 5}),
            "Exact five-suite completion required", "/completion")
    outputs = record["engine_outputs"]
    require(type(outputs) is list and len(outputs) <= 1, "Only bounded root resource database may be derived", "/engine_outputs")
    for index, output in enumerate(outputs):
        pointer = "/engine_outputs/" + str(index)
        names(output, ("path", "relative", "sha256", "bytes"), pointer)
        require(output["relative"] == "resourceDatabase.rdb" and "resourceDatabase.rdb" not in expected["manifest"]["files"],
                "Unexpected engine-derived output", pointer)
        same_path(output["path"], expected["project_dir"].rstrip("/\\") + "/resourceDatabase.rdb", pointer + "/path")
        digest(output["sha256"], pointer + "/sha256")
        integer(output["bytes"], 0, 8 * 1024 * 1024, pointer + "/bytes")
    directories = record["log_directories"]
    require(type(directories) is list and 1 <= len(directories) <= 16, "Bounded owned log-directory observations required", "/log_directories")
    directory_keys = [path_key(name, "/log_directories") for name in directories]
    require(len(set(directory_keys)) == len(directory_keys), "Duplicate owned log directory", "/log_directories")
    logs = record["raw_logs"]
    require(type(logs) is list and 1 <= len(logs) <= 4096, "Retained raw owned-session logs required", "/raw_logs")
    total = 0
    originals, retained = set(), set()
    log_root = path_key(expected["project_dir"], "/expected/project_dir").rsplit("/", 1)[0] + "/tablet-suite-logs/"
    for index, item in enumerate(logs):
        pointer = "/raw_logs/" + str(index)
        names(item, ("original", "retained", "sha256", "bytes"), pointer)
        original_key = path_key(item["original"], pointer + "/original")
        retained_key = path_key(item["retained"], pointer + "/retained")
        require(original_key.rsplit("/", 1)[0] in directory_keys and original_key.endswith(".log") and
                retained_key == log_root + "/".join(original_key.split("/")[-2:]) and
                original_key not in originals and retained_key not in retained,
                "Raw log paths or uniqueness differ from owned capture", pointer)
        originals.add(original_key)
        retained.add(retained_key)
        digest(item["sha256"], pointer + "/sha256")
        total += integer(item["bytes"], 0, LIMITS["raw_logs_aggregate_bytes"], pointer + "/bytes")
    require(0 < total <= LIMITS["raw_logs_aggregate_bytes"], "Raw log aggregate bounds exceeded", "/raw_logs")
    return {"schema_version": 1, "status": "success", "profile": PROFILE, "expected_cases": list(SUITES),
            "executed_suites": 5, "passed_suites": 5, "rpc_count": 18, "identity_observations": 12,
            "suites": summaries, "schema_policy": SCHEMA_POLICY, "cleanup": record["cleanup"], "elapsed_ms": elapsed,
            "assertion_count": None, "coverage": "five preserved source-defined suite returns",
            "generated_tablet_execution": "not_run", "tablet_callback_delivery": "not_run",
            "physical_ui_input": "not_run", "multiplayer": "not_run", "visual_review": "not_run",
            "queued_callback_lifetime": "not_verified", "resource_closure": "not_verified",
            "recorded_file_hashes": "admitted; physical current-file guards belong to the owning runner"}


def fixture():
    expected = {"token": "1" * 64, "profile": PROFILE, "source_sha256": "2" * 64,
                "project_dir": "C:/beryl/build/pure/candidate-addon", "project_id": PROJECT,
                "engine": {"path": "C:/engine/Workbench.exe", "bytes": 100000, "sha256": "3" * 64},
                "engine_version": "1.8.0.13", "tools": {"Find-Workbench.ps1": "4" * 64, "Invoke-WorkbenchRpc.ps1": "5" * 64},
                "manifest_path": "C:/beryl/build/pure/input-manifest.json", "manifest_sha256": "6" * 64,
                "manifest": {"schema_version": 1, "profile": PROFILE, "files": {"source/" + str(i).zfill(3) + ".c": "7" * 64 for i in range(87)}},
                "adapter_sha256": "8" * 64,
                "argv": ["-gproj", "C:/beryl/build/pure/candidate-addon/addon.gproj", "-noOpenLastResource",
                         "-scriptAuthorizeAll", "-wbmodule=WorldEditor", "-run"]}
    pid, ticks = 1234, 639272500000000000

    def check(site, timestamp):
        return {"site": site, "process_id": pid, "start_ticks": ticks, "executable": expected["engine"]["path"], "elapsed_ms": timestamp}

    record = {"schema_version": 1, "stage": "suites_complete", "status": "success", "profile": PROFILE,
              "mechanism": "owned_empty_editor_existing_suites", "token": expected["token"], "source_sha256": expected["source_sha256"],
              "project_id": PROJECT, "scope": "existing MESH ui, screen, actions, clicks and schema suites only",
              "requested_editor_context": "WorldEditor startup requested; no resource load requested",
              "engine_path": expected["engine"]["path"], "engine_sha256": expected["engine"]["sha256"], "engine_bytes": expected["engine"]["bytes"],
              "engine_version": expected["engine_version"], "tools": copy.deepcopy(expected["tools"]), "adapter_sha256": expected["adapter_sha256"],
              "input_manifest": {"path": expected["manifest_path"], "sha256": expected["manifest_sha256"]},
              "staged_inputs": copy.deepcopy(expected["manifest"]), "engine_outputs": [], "arguments": list(expected["argv"]),
              "startup": {"mechanism": "owned_empty_editor_existing_suites", "argv": list(expected["argv"]),
                          "working_directory": "C:/engine/game", "use_shell_execute": False, "create_no_window": True,
                          "window_style": "Hidden", "launch_returned": True, "polls": 1, "process_id": pid},
              "session": {"process_id": pid, "start_ticks": ticks, "executable": expected["engine"]["path"],
                          "project": expected["project_dir"], "reused": False, "start_time": "2026-10-10T19:00:00.0000000Z"},
              "loaded_projects": None, "suite_selections": copy.deepcopy(SELECTIONS), "suites": [], "identity_observations": [],
              "completion": {"suite_count": 5, "identity_count": 12, "suite_ids": list(SUITES), "requests_executed": 5}, "rpcs": [],
              "session_checks": [check("startup.identity", 5), check("port.check", 11), check("port.check", 21)],
              "port_checks": [{"elapsed_ms": 10, "listening": False, "owning_process": None}, {"elapsed_ms": 20, "listening": True, "owning_process": pid}],
              "port_query_errors": [], "raw_logs": [{"original": "C:/engine/logs/session001/console.log",
                    "retained": "C:/beryl/build/pure/tablet-suite-logs/session001/console.log", "sha256": "9" * 64, "bytes": 1000}],
              "log_directories": ["C:/engine/logs/session001"], "evidence_errors": [], "cleanup": "owned_process_stopped", "cleanup_errors": [],
              "failure": None, "elapsed_ms": 500, "limits": copy.deepcopy(LIMITS)}
    record["raw_log_observation"] = "snapshot_after_confirmed_owned_exit"
    record.update({key: "not_run" for key in NO_EXECUTION})
    identity = {key: expected[key] for key in ("token", "profile", "source_sha256")}
    schema = "".join(" " + name + "[field]" for name in COMPONENTS)
    calls, sites = expected_calls(expected)
    for index, (function, params, meaning) in enumerate(calls):
        timestamp = 100 + index * 10
        if index == 0:
            response = {"Loaded Projects": ["core", "ArmaReforger", PROJECT]}
        elif function == "BerylTabletSuiteIdentity":
            response = dict(identity)
        else:
            response = {"ok": 1, "detail": schema if meaning == "schema" else DETAILS[meaning]}
        reply = {"Ok": True, "Function": function, "ErrorCode": "Ok", "Response": response,
                 "Raw": json.dumps(response, separators=(",", ":"))}
        stage = "startup" if index == 0 else "identity.initial" if meaning == "initial" else "identity.final" if meaning == "final" else "suite." + meaning.split(".")[-1]
        record["rpcs"].append({"stage": stage, "function": function, "params": dict(params), "elapsed_ms": timestamp + 1,
                               "timeout_ms": 8000, "result": reply, "normalized_response": None if index == 0 else copy.deepcopy(response),
                               "failure": None, "failure_kind": None, "duration_ms": 4})
        record["session_checks"] += [check("before." + function, timestamp), check("after." + function, timestamp + 4)]
    record["loaded_projects"] = copy.deepcopy(record["rpcs"][0]["result"])
    record["identity_observations"] = [{"site": site, "rpc_index": index, "response": copy.deepcopy(record["rpcs"][index]["result"]["Response"])} for site, index in sites]
    record["suites"] = [{"suite": selection["suite"], "arg": selection["arg"], "rpc_index": 3 + index * 3,
                         "response": copy.deepcopy(record["rpcs"][3 + index * 3]["result"]["Response"]), "status": "success"}
                        for index, selection in enumerate(SELECTIONS)]
    return record, expected


SELFTEST_IDS = (
    "valid.complete-source-suites", "valid.confirmed-already-exited", "valid.bounded-derived-cache", "valid.absent-listener-diagnostic",
    "negative.top-unknown-field", "negative.schema-boolean", "negative.status-timeout", "negative.stage-partial",
    "negative.profile", "negative.token", "negative.source-stamp", "negative.project", "negative.engine-hash", "negative.engine-bytes-boolean",
    "negative.engine-path", "negative.engine-version", "negative.tool-identity", "negative.adapter-identity", "negative.manifest-hash",
    "negative.manifest-path", "negative.staged-input-hash", "negative.staged-version-boolean", "negative.arguments-load", "negative.limits-widened",
    "negative.scope-claim", "negative.play-claim", "negative.callback-claim", "negative.failure-text", "negative.evidence-error", "negative.cleanup-error",
    "negative.cleanup-not-confirmed", "negative.total-late", "negative.total-boolean", "negative.reused-session", "negative.session-pid-boolean",
    "negative.session-project", "negative.startup-visible", "negative.startup-shell", "negative.startup-returned-boolean", "negative.startup-argv",
    "negative.startup-pid", "negative.listener-foreign", "negative.listener-unowned", "negative.listener-boolean-number", "negative.listener-poll-missing",
    "negative.listener-query-failure", "negative.rpc-missing", "negative.rpc-duplicate", "negative.rpc-order", "negative.rpc-function", "negative.rpc-params",
    "negative.rpc-extra-opener", "negative.rpc-timeout-widened", "negative.rpc-late-duration", "negative.rpc-late-boundary", "negative.rpc-negative-duration",
    "negative.rpc-failure", "negative.rpc-failure-kind", "negative.rpc-stage", "negative.transport-bool-number", "negative.transport-function",
    "negative.transport-error", "negative.transport-unknown-field", "negative.raw-malformed", "negative.raw-duplicate-field", "negative.raw-nonfinite",
    "negative.raw-parsed-mismatch", "negative.normalized-mismatch", "negative.identity-response", "negative.identity-site", "negative.identity-index-boolean",
    "negative.identity-row-missing", "negative.identity-row-response", "negative.suite-missing", "negative.suite-order", "negative.suite-index", "negative.suite-row-response",
    "negative.suite-ok-boolean", "negative.suite-ok-float", "negative.suite-ok-string", "negative.suite-ok-zero", "negative.suite-unknown-field",
    "negative.ui-detail", "negative.actions-controls", "negative.clicks-controls", "negative.schema-container", "negative.schema-missing-component",
    "negative.schema-order", "negative.schema-extra-component", "negative.schema-duplicate-field", "negative.schema-malformed", "negative.schema-too-long",
    "negative.loaded-unrelated", "negative.loaded-duplicate", "negative.loaded-missing-selected", "negative.loaded-detached-receipt",
    "negative.session-check-missing", "negative.session-check-site", "negative.session-check-pid", "negative.session-check-start", "negative.session-check-time-backward",
    "negative.session-check-time-beyond-end", "negative.completion-count-boolean", "negative.completion-cases-missing", "negative.completion-count",
    "negative.output-unexpected", "negative.output-path", "negative.output-cap", "negative.logs-missing", "negative.logs-duplicate", "negative.logs-unowned",
    "negative.logs-retained-outside", "negative.logs-cap", "negative.logs-hash", "negative.expected-unsafe-path", "negative.expected-case-collision",
    "negative.expected-version-boolean", "negative.expected-engine-boolean", "negative.expected-profile", "negative.expected-argv",
    "negative.unpaired-unicode", "negative.raw-exceeds-bridge-bound", "negative.deep-response", "negative.listener-query-after-rpc",
    "negative.raw-logs-before-confirmed-exit",
    "valid.schema-native-observed-permutation", "valid.schema-captured-q93-fields",
    "negative.schema-repeated-component", "negative.schema-replaced-component",
    "valid.schema-returned-order-preserved",
)


def self_test():
    source_path = Path(__file__).resolve()
    source_bytes = source_path.read_bytes()
    cases = []

    def set_path(target, path, value):
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value

    def changed(path, value, expected=False):
        return lambda record, exp: set_path(exp if expected else record, path, value)

    def coherent_reply(index, value):
        def mutation(record, _):
            record["rpcs"][index]["result"]["Response"] = copy.deepcopy(value)
            record["rpcs"][index]["result"]["Raw"] = json.dumps(value, separators=(",", ":"))
            record["rpcs"][index]["normalized_response"] = copy.deepcopy(value)
            for row in record["suites"] + record["identity_observations"]:
                if row["rpc_index"] == index:
                    row["response"] = copy.deepcopy(value)
            if index == 0:
                record["loaded_projects"] = copy.deepcopy(record["rpcs"][0]["result"])
                record["rpcs"][0]["normalized_response"] = None
        return mutation

    def run(case_id, mutation, accepted=False, component_order=None):
        record, expected = fixture()
        mutation(record, expected)
        error = None
        try:
            summary = validate_runtime(record, expected)
            passed = accepted and summary["passed_suites"] == 5 and summary["assertion_count"] is None
            if passed and component_order is not None:
                passed = ([row["class"] for row in summary["suites"][4]["components"]] == component_order and
                          summary["suites"][4]["response"]["detail"] == record["rpcs"][15]["result"]["Response"]["detail"])
        except SuiteReceiptFailure as exc:
            passed = not accepted and exc.status in ("failure", "stale_input", "unavailable")
            error = {"status": exc.status, "pointer": exc.pointer, "message": str(exc)}
        cases.append({"id": case_id, "status": "success" if passed else "failure", "expected": "admit" if accepted else "reject", "rejection": error})

    run("valid.complete-source-suites", lambda r, e: None, True)
    run("valid.confirmed-already-exited", changed(("cleanup",), "owned_process_already_exited"), True)
    output = {"path": "C:/beryl/build/pure/candidate-addon/resourceDatabase.rdb", "relative": "resourceDatabase.rdb", "sha256": "a" * 64, "bytes": 8 * 1024 * 1024}
    run("valid.bounded-derived-cache", changed(("engine_outputs",), [output]), True)
    run("valid.absent-listener-diagnostic", changed(("port_query_errors",), [{"elapsed_ms": 11, "category": "ObjectNotFound", "id": "Absent", "message": "No listener yet"}]), True)
    scalar_faults = (
        ("negative.top-unknown-field", ("guessed_callback_count",), 5), ("negative.schema-boolean", ("schema_version",), True),
        ("negative.status-timeout", ("status",), "timeout"), ("negative.stage-partial", ("stage",), "suite.schema"),
        ("negative.profile", ("profile",), "other"), ("negative.token", ("token",), "a" * 64),
        ("negative.source-stamp", ("source_sha256",), "a" * 64), ("negative.project", ("project_id",), "SparkOSMesh"),
        ("negative.engine-hash", ("engine_sha256",), "a" * 64), ("negative.engine-bytes-boolean", ("engine_bytes",), True),
        ("negative.engine-path", ("engine_path",), "C:/other/Workbench.exe"), ("negative.engine-version", ("engine_version",), "1.8"),
        ("negative.tool-identity", ("tools", "Find-Workbench.ps1"), "a" * 64), ("negative.adapter-identity", ("adapter_sha256",), "a" * 64),
        ("negative.manifest-hash", ("input_manifest", "sha256"), "a" * 64), ("negative.manifest-path", ("input_manifest", "path"), "C:/other/manifest.json"),
        ("negative.staged-input-hash", ("staged_inputs", "files", "source/000.c"), "a" * 64), ("negative.staged-version-boolean", ("staged_inputs", "schema_version"), True),
        ("negative.arguments-load", ("arguments",), ["-gproj", "C:/x", "-load", "world.ent"]), ("negative.limits-widened", ("limits", "rpc_ms"), 60000),
        ("negative.scope-claim", ("scope",), "complete tablet"), ("negative.play-claim", ("play",), "success"), ("negative.callback-claim", ("tablet_callback_delivery",), "success"),
        ("negative.failure-text", ("failure",), "failed"), ("negative.evidence-error", ("evidence_errors",), [{"stage": "logs", "message": "missing"}]),
        ("negative.cleanup-error", ("cleanup_errors",), [{"stage": "cleanup", "message": "failed"}]), ("negative.cleanup-not-confirmed", ("cleanup",), "owned_process_exit_not_confirmed"),
        ("negative.total-late", ("elapsed_ms",), 180000), ("negative.total-boolean", ("elapsed_ms",), True), ("negative.reused-session", ("session", "reused"), True),
        ("negative.session-pid-boolean", ("session", "process_id"), True), ("negative.session-project", ("session", "project"), "C:/live/addon"),
        ("negative.startup-visible", ("startup", "window_style"), "Normal"), ("negative.startup-shell", ("startup", "use_shell_execute"), True),
        ("negative.startup-returned-boolean", ("startup", "launch_returned"), 1), ("negative.startup-argv", ("startup", "argv"), ["-gproj", "wrong"]),
        ("negative.startup-pid", ("startup", "process_id"), 9999), ("negative.listener-foreign", ("port_checks", 1, "owning_process"), 9999),
        ("negative.listener-unowned", ("port_checks", 1, "owning_process"), None), ("negative.listener-boolean-number", ("port_checks", 1, "listening"), 1),
        ("negative.listener-poll-missing", ("startup", "polls"), 0), ("negative.listener-query-failure", ("port_query_errors",), [{"elapsed_ms": 11, "category": "PermissionDenied", "id": "Denied", "message": "denied"}]),
    )
    for case_id, path, value in scalar_faults:
        run(case_id, changed(path, value))
    run("negative.rpc-missing", lambda r, e: r["rpcs"].pop())
    run("negative.rpc-duplicate", lambda r, e: r["rpcs"].append(copy.deepcopy(r["rpcs"][-1])))
    run("negative.rpc-order", lambda r, e: r["rpcs"].__setitem__(slice(2, 4), list(reversed(r["rpcs"][2:4]))))
    rpc_faults = (
        ("negative.rpc-function", ("function",), "OpenResource"), ("negative.rpc-params", ("params",), {"suite": "prefabaudit", "arg": ""}),
        ("negative.rpc-extra-opener", ("params", "load"), True), ("negative.rpc-timeout-widened", ("timeout_ms",), 60000),
        ("negative.rpc-late-duration", ("duration_ms",), 8000), ("negative.rpc-late-boundary", ("elapsed_ms",), 0),
        ("negative.rpc-negative-duration", ("duration_ms",), -1), ("negative.rpc-failure", ("failure",), "failed"),
        ("negative.rpc-failure-kind", ("failure_kind",), "transport_failure_unclassified"), ("negative.rpc-stage", ("stage",), "play"),
        ("negative.transport-bool-number", ("result", "Ok"), 1), ("negative.transport-function", ("result", "Function"), "Other"),
        ("negative.transport-error", ("result", "ErrorCode"), "Failure"), ("negative.transport-unknown-field", ("result", "Verified"), True),
        ("negative.raw-malformed", ("result", "Raw"), "{"), ("negative.raw-duplicate-field", ("result", "Raw"), '{"ok":1,"ok":1,"detail":"ui suite passed"}'),
        ("negative.raw-nonfinite", ("result", "Raw"), '{"ok":NaN,"detail":"ui suite passed"}'),
        ("negative.raw-parsed-mismatch", ("result", "Response", "detail"), "different"), ("negative.normalized-mismatch", ("normalized_response", "detail"), "different"),
    )
    for case_id, path, value in rpc_faults:
        run(case_id, changed(("rpcs", 3) + path, value))
    run("negative.identity-response", coherent_reply(2, {"token": "a" * 64, "profile": PROFILE, "source_sha256": "2" * 64}))
    run("negative.identity-site", changed(("identity_observations", 1, "site"), "after.ui"))
    run("negative.identity-index-boolean", changed(("identity_observations", 1, "rpc_index"), True))
    run("negative.identity-row-missing", lambda r, e: r["identity_observations"].pop())
    run("negative.identity-row-response", changed(("identity_observations", 1, "response", "token"), "a" * 64))
    run("negative.suite-missing", lambda r, e: r["suites"].pop())
    run("negative.suite-order", lambda r, e: r["suites"].reverse())
    run("negative.suite-index", changed(("suites", 0, "rpc_index"), 6))
    run("negative.suite-row-response", changed(("suites", 0, "response", "detail"), "other"))
    for case_id, ok in (("negative.suite-ok-boolean", True), ("negative.suite-ok-float", 1.0), ("negative.suite-ok-string", "1"), ("negative.suite-ok-zero", 0)):
        run(case_id, coherent_reply(3, {"ok": ok, "detail": DETAILS["ui"]}))
    run("negative.suite-unknown-field", coherent_reply(3, {"ok": 1, "detail": DETAILS["ui"], "cases": 5}))
    run("negative.ui-detail", coherent_reply(3, {"ok": 1, "detail": "ui passed"}))
    run("negative.actions-controls", coherent_reply(9, {"ok": 1, "detail": "actions suite passed (28 controls)"}))
    run("negative.clicks-controls", coherent_reply(12, {"ok": 1, "detail": "clicks suite passed (22 controls)"}))
    schema = "".join(" " + name + "[field]" for name in COMPONENTS)
    for case_id, detail in (
        ("negative.schema-container", "GenericEntity[field]"), ("negative.schema-missing-component", "".join(" " + name + "[]" for name in COMPONENTS[:-1])),
        ("negative.schema-order", "".join(" " + name + "[]" for name in reversed(COMPONENTS))),
        ("negative.schema-extra-component", schema + " Extra[]"), ("negative.schema-duplicate-field", schema.replace("MeshObject[field]", "MeshObject[field,field]")),
        ("negative.schema-malformed", schema + " garbage"), ("negative.schema-too-long", " " + "x" * 65536)):
        # Keep this historical ID and position, but explicitly revise the old
        # unsupported order-rejection expectation. Other failures still reject.
        run(case_id, coherent_reply(15, {"ok": 1, "detail": detail}), case_id == "negative.schema-order")
    for case_id, projects in (("negative.loaded-unrelated", [PROJECT, "SparkOSMesh"]), ("negative.loaded-duplicate", [PROJECT, PROJECT]), ("negative.loaded-missing-selected", ["core", "ArmaReforger"])):
        run(case_id, coherent_reply(0, {"Loaded Projects": projects}))
    run("negative.loaded-detached-receipt", changed(("loaded_projects", "Response", "Loaded Projects"), [PROJECT]))
    run("negative.session-check-missing", lambda r, e: r["session_checks"].pop())
    for case_id, key, value in (("negative.session-check-site", "site", "after.Other"), ("negative.session-check-pid", "process_id", 9999),
                               ("negative.session-check-start", "start_ticks", 100), ("negative.session-check-time-backward", "elapsed_ms", 1),
                               ("negative.session-check-time-beyond-end", "elapsed_ms", 501)):
        run(case_id, changed(("session_checks", 5, key), value))
    for case_id, key, value in (("negative.completion-count-boolean", "suite_count", True), ("negative.completion-cases-missing", "suite_ids", list(SUITES[:-1])), ("negative.completion-count", "identity_count", 11)):
        run(case_id, changed(("completion", key), value))
    for case_id, key, value in (("negative.output-unexpected", "relative", "world.ent"), ("negative.output-path", "path", "C:/outside/resourceDatabase.rdb"), ("negative.output-cap", "bytes", 8 * 1024 * 1024 + 1)):
        def mutate(record, _, key=key, value=value):
            row = dict(output)
            row[key] = value
            record["engine_outputs"] = [row]
        run(case_id, mutate)
    run("negative.logs-missing", changed(("raw_logs",), []))
    run("negative.logs-duplicate", lambda r, e: r["raw_logs"].append(copy.deepcopy(r["raw_logs"][0])))
    for case_id, key, value in (("negative.logs-unowned", "original", "C:/other/logs/console.log"),
                              ("negative.logs-retained-outside", "retained", "C:/outside/console.log"),
                              ("negative.logs-cap", "bytes", 67108865), ("negative.logs-hash", "sha256", "bad")):
        run(case_id, changed(("raw_logs", 0, key), value))
    run("negative.expected-unsafe-path", changed(("manifest", "files"), {"../source/" + str(i) + ".c": "7" * 64 for i in range(87)}, True))
    def collide(_, expected):
        del expected["manifest"]["files"]["source/001.c"]
        expected["manifest"]["files"]["SOURCE/000.c"] = "7" * 64
    run("negative.expected-case-collision", collide)
    for case_id, path, value in (("negative.expected-version-boolean", ("manifest", "schema_version"), True),
                                 ("negative.expected-engine-boolean", ("engine", "bytes"), True),
                                 ("negative.expected-profile", ("profile",), "other"), ("negative.expected-argv", ("argv",), ["-load", "world.ent"])):
        run(case_id, changed(path, value, True))
    run("negative.unpaired-unicode", coherent_reply(3, {"ok": 1, "detail": "\ud800"}))
    run("negative.raw-exceeds-bridge-bound", changed(("rpcs", 3, "result", "Raw"), '{"ok":1,"detail":"ui suite passed"}' + " " * (1024 * 1024)))
    deep = []
    for _ in range(100):
        deep = [deep]
    run("negative.deep-response", coherent_reply(0, {"Loaded Projects": deep}))
    run("negative.listener-query-after-rpc", changed(("port_query_errors",), [{"elapsed_ms": 200, "category": "ObjectNotFound", "id": "Absent", "message": "No listener"}]))
    run("negative.raw-logs-before-confirmed-exit", changed(("raw_log_observation",), "point_in_time_exit_unconfirmed"))
    native_order = ["InventoryItemComponent", "MeshObject", "SCR_EditableEntityComponent", "SPK_DroneInputComponent",
                    "SPK_TabletComponent", "SPK_TabletGadgetComponent"]
    native_dump = "".join(" " + name + "[field]" for name in native_order)
    run("valid.schema-native-observed-permutation", coherent_reply(15, {"ok": 1, "detail": native_dump}), True, native_order)
    run("valid.schema-captured-q93-fields", coherent_reply(15, {"ok": 1, "detail": Q93_SCHEMA_DETAIL}), True, native_order)
    duplicate = "".join(" " + name + "[]" for name in COMPONENTS[:-1] + (COMPONENTS[0],))
    run("negative.schema-repeated-component", coherent_reply(15, {"ok": 1, "detail": duplicate}))
    replaced = "".join(" " + name + "[]" for name in COMPONENTS[:-1] + ("OtherComponent",))
    run("negative.schema-replaced-component", coherent_reply(15, {"ok": 1, "detail": replaced}))
    reverse_order = list(reversed(COMPONENTS))
    reverse_dump = "".join(" " + name + "[first,second]" for name in reverse_order)
    run("valid.schema-returned-order-preserved", coherent_reply(15, {"ok": 1, "detail": reverse_dump}), True, reverse_order)
    require(tuple(case["id"] for case in cases) == SELFTEST_IDS and len(set(SELFTEST_IDS)) == len(SELFTEST_IDS),
            "Pure fixture registry is missing, duplicate or out of order")
    require(source_path.read_bytes() == source_bytes, "Checker source changed during pure fixtures", status="stale_input")
    passed = sum(case["status"] == "success" for case in cases)
    return {"schema_version": 1, "operation": "test.tablet.existing_suites.receipt_admission", "status": "success" if passed == len(cases) else "failure",
            "scope": "pure synthetic receipt admission; no host/compiler/engine executed", "expected_cases": list(SELFTEST_IDS),
            "passed_cases": passed, "failed_cases": len(cases) - passed, "cases": cases,
            "schema_policy": SCHEMA_POLICY,
            "revised_expectations": [{"id": "negative.schema-order", "previous": "reject", "current": "admit",
                "reason": "Historical ID retained; native GetComponent(i) has no source-order guarantee",
                "previous_checker_sha256": "29e4154e0ba226ed7f7bde3c260ee05f50bb5a48166ade5ccebbc3c62120213c"}],
            "source": {"path": str(source_path), "bytes": len(source_bytes), "sha256": hashlib.sha256(source_bytes).hexdigest()}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--expected", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        result = self_test()
        print(json.dumps(result, sort_keys=True, indent=2))
        return 0 if result["status"] == "success" else 1
    require(args.receipt is not None and args.expected is not None, "Both receipt and expected identities required")
    result = validate_runtime(decode_json(args.receipt.read_bytes()), decode_json(args.expected.read_bytes()))
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SuiteReceiptFailure as exc:
        print(json.dumps({"schema_version": 1, "status": exc.status, "pointer": exc.pointer, "failure": str(exc)}), file=sys.stderr)
        raise SystemExit(1)
