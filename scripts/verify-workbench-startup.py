#!/usr/bin/env python3
"""Copy an identified prepared addon and test only Workbench startup readiness.

--prepare-only writes source/evidence, not an executable. --engine-stage uses
the existing headless compile bridge, then optionally the owned startup adapter.
--self-test executes inert filesystem/receipt fixtures only. No installation,
security configuration, live addon edit, callback invocation or fallback occurs.
"""
from pathlib import Path
import argparse
import copy
import hashlib
import importlib.util
import json
import re
import shutil
import stat
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / "tools/beryl-mod"))
import mod

PACKAGE = ROOT / "packages/sparkos/workbench-startup-probe"
ADAPTER = ROOT / "scripts/workbench-startup-engine.ps1"
FUNCTION = "BerylStartupReadiness"
OPENING_PROFILES = {"startup-cli": "startup_cli", "netapi-resource": "native_netapi", "module-netapi-resource": "module_native_netapi",
                    "module-netapi-registered": "module_registered_netapi"}
OPENING_SCOPES = {"startup-cli": "startup-world readiness observation only",
                  "netapi-resource": "native NetAPI resource request and owned-world readiness observation only",
                  "module-netapi-resource": "native NetAPI resource request and owned-world readiness observation only",
                  "module-netapi-registered": "native NetAPI resource request and owned-world readiness observation only"}
PROJECT_ID = "BerylComponentCallbackProbe"
RESOURCE = "{BCCBA11B20261008}worlds/BerylCallbackProbe.ent"
REL_WORLD = "worlds/BerylCallbackProbe.ent"
HANDLER_PATH = "scripts/WorkbenchGameCommon/BerylStartupReadiness.c"
HASH = re.compile(r"[0-9a-f]{64}")
BASE_FILES = frozenset(("addon.gproj", "scripts/Game/Beryl/Beryl_Generated.c", "scripts/Game/SPK_BerylCallbackObserver.c",
    "scripts/WorkbenchGameCommon/BerylComponentCallbacks.c", REL_WORLD, REL_WORLD + ".meta",
    "Prefabs/BerylCallbackProbe.et", "Prefabs/BerylCallbackProbe.et.meta"))
CALLBACK_CASES = ("runtime.post-init.1", "runtime.post-init.2", "runtime.frames.1", "runtime.frames.2",
                  "runtime.independent-state", "runtime.delete.1", "runtime.delete.2")
READY_CASES = ("startup.loaded-addon", "startup.native-addon-world", "startup.resource-roundtrip",
               "startup.editor-api", "startup.owned-edit-world", "startup.confirmed-cleanup")
WIRE_BOOLS = ("addon_world_resolved", "resource_name_resolved", "module_present", "api_present", "world_path_resolved",
              "world_matches", "edit_mode", "game_mode", "in_play_mode", "world_present")
WIRE_STRINGS = ("token", "action", "status", "failure", "mechanism", "current_project", "addon_world_path", "resource_name",
                "resource_path", "resource_absolute_path", "world_path", "world_absolute_path")
WIRE_FIELDS = frozenset((*WIRE_STRINGS, *WIRE_BOOLS))
COMPILE_TOOLS = ("Find-Workbench.ps1", "Invoke-ReforgerBuild.ps1", "Invoke-Workbench.ps1", "Get-WorkbenchErrors.ps1")
RUNTIME_TOOLS = ("Find-Workbench.ps1", "Invoke-WorkbenchRpc.ps1")
DOC_ROOT = Path("C:/Program Files (x86)/Steam/steamapps/common/Arma Reforger Tools/Workbench/docs/EnfusionScriptAPI/html")
DOCS = {"Page_CLI.html": "b1fd25c1d02e3ac687bb310496f700acaf451f66d26c572afa9ac5fd343822d1",
        "Page_NetApi.html": "e39e4a346fe6ed70358f2be6745424f543c21b225a2ac9d7967c403d256cd51c",
        "interfaceWorkbench.html": "6da66bb00dd8cadb84463605e7272d93a01e179c8bd651dbdc614d3a68bbdf0f",
        "interfaceWorldEditor.html": "51af7415047780b9efa7302dfa3b4573dd89d78c4d90b46968273f010f16f275",
        "interfaceWorldEditorAPI.html": "202fbc3822d1c8d9cd465ad4968a9541e90353b51cf4329046187ef8cba1d7b2"}
SELF_CASES = ("prepared.valid", "prepared.schema-bool", "prepared.failed", "prepared.not-prepared", "prepared.wrong-operation",
    "prepared.callbacks-claimed", "prepared.wrong-cases", "prepared.wrong-path", "prepared.wrong-files", "prepared.bad-hash",
    "prepared.changed-copy", "prepared.extra-directory", "prepared.world-changed", "prepared.artifact-mismatch",
    "wire.valid", "wire.bool01", "wire.no-mutation", "wire.extra", "wire.missing", "wire.string-bool", "wire.float-bool",
    "wire.two-bool", "wire.oversize", "ready.token", "ready.action", "ready.mechanism", "ready.pending", "ready.failure",
    "ready.addon", "ready.resource", "ready.roundtrip", "ready.observed-world", "ready.no-world", "ready.no-api",
    "ready.no-edit", "ready.game-mode", "ready.play-mode", "ready.failure-text", "render.exact", "render.unresolved",
    "scope.no-callbacks", "compile.success", "compile.failed", "compile.schema-bool", "compile.wrong-engine", "compile.wrong-tools",
    "prepared.extra-artifact", "prepared.traversal", "handler.read-only", "envelope.valid",
    "envelope.raw-changed", "envelope.stage", "envelope.schema-bool", "envelope.expired", "envelope.engine",
    "envelope.arguments", "envelope.cleanup", "envelope.evidence-errors", "envelope.loaded-missing", "envelope.rpc-missing",
    "envelope.token", "envelope.codec", "envelope.null-health-unknown", "envelope.spawn-rpc", "envelope.ownership-missing",
    "envelope.duplicate-loaded", "envelope.time-order", "envelope.log-hash", "envelope.logs-missing", "envelope.health-not-ready",
    "envelope.port-missing", "envelope.port-foreign", "envelope.health-duplicate", "envelope.pending-foreign",
    "envelope.adapter", "envelope.manifest-path", "envelope.manifest-hash", "envelope.manifest-fields",
    "envelope.manifest-files", "envelope.output-unaccounted", "envelope.callback-scope", "envelope.play-scope",
    "envelope.spawn-scope", "envelope.save-scope", "envelope.policy-scope", "envelope.limit-change",
    "envelope.rpc-duration", "envelope.rpc-late-duration", "envelope.derived-valid", "envelope.derived-hash",
    "envelope.derived-size", "envelope.derived-boolean-size", "envelope.derived-relative", "envelope.extra-staged-file",
    "envelope.handler-action", "envelope.builtin-action", "envelope.health-receipt",
    "profile.render", "profile.unknown", "profile.native-valid", "profile.open-missing", "profile.open-duplicate",
    "profile.open-order", "profile.open-param", "profile.opened-false", "profile.opened-string", "profile.opened-float",
    "profile.opened-extra", "profile.open-codec", "profile.open-raw", "profile.open-link", "profile.preliminary-link",
    "profile.preliminary-identity", "profile.mechanism", "profile.arguments", "profile.default-no-opener",
    "profile.default-params", "profile.handler-params", "profile.opened-bool-valid", "profile.open-normalized-int",
    "profile.observer-normalized-int", "profile.codec-boolean-version", "third.render", "third.valid", "third.load-forbidden",
    "third.module-missing", "third.run-missing", "third.vector-order", "third.native-wire", "third.native-profile",
    "third.startup-profile", "third.scope", "third.no-opener", "third.as-native", "third.native-as-third",
    "registered.render", "registered.valid", "registered.absolute-forbidden", "registered.relative-forbidden",
    "registered.foreign-guid", "registered.extra-param", "registered.third-wire", "registered.third-profile",
    "registered.load-forbidden", "registered.no-module", "registered.preliminary-missing", "registered.preliminary-guid",
    "registered.as-absolute", "registered.absolute-as-registered")


def require(test, message, status="failure"):
    if not test:
        raise mod.Failure(message, status)


def load_helper(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


bounded = load_helper("startup_bounded_tree", ROOT / "scripts/verify-component-engine.py")


def identity(path):
    path = Path(path)
    clean_path(path)
    require(path.is_file(), "Missing regular input: " + str(path), "stale_input")
    before = path.stat()
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    after = path.stat()
    require((before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns), "Input changed during hash", "stale_input")
    return {"path": str(path), "bytes": before.st_size, "sha256": digest.hexdigest()}


def clean_path(path):
    """Reject lexical traversal and every existing linked ancestor before use."""
    path = Path(path)
    require(".." not in path.parts, "Traversal is not an admitted input path", "stale_input")
    for current in (path, *path.parents):
        if current.exists() or current.is_symlink():
            require(not bounded.linked(current) and not (getattr(current.lstat(), "st_file_attributes", 0) &
                    getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)), "Linked input ancestor: " + str(current), "stale_input")
    return path


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        require(stream.write(data) == len(data), "Incomplete owned write")
    require(mod.read(path) == data, "Owned write differs from input")


def saved(path, value):
    write(path, json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False).encode("utf-8") + b"\n")
    require(mod.parse(mod.read(path)) == value, "Evidence write did not preserve complete result")


def scope():
    return {"source_copy": "not_run", "engine_compilation": "not_run", "startup_world_readiness": "not_run",
            "callback_delivery": "not_run", "tablet_services": "not_run", "native_program": "not_run",
            "compiler_execution": "not_run", "world_format": "experimental_unverified", "installation": "unchanged",
            "policy_changes": "not_run", "world_save": "not_run"}


def prepared(value, receipt_path):
    """Admit a successful prepare-only receipt, never a timed-out engine job."""
    require(type(value) is dict and type(value.get("schema_version")) is int and value["schema_version"] == 1 and
            value.get("operation") == "verify.component_callbacks.runtime" and value.get("status") == "success" and
            value.get("stage") == "prepared", "Selected receipt is not successful prepare-only evidence", "unavailable")
    require(value.get("expected_case_ids") == list(CALLBACK_CASES) and type(value.get("scope")) is dict and
            value["scope"].get("source_generation") == "executed_success" and
            all(value["scope"].get(name) == "not_run" for name in ("engine_compilation", "engine_runtime_callbacks", "engine_callback_delivery")),
            "Prepare receipt scope/cases differ", "stale_input")
    addon = Path(value.get("candidate_path", ""))
    clean_path(addon)
    require(addon.is_absolute() and addon == receipt_path.parent / "probe-addon", "Prepared candidate path is not its owned addon", "stale_input")
    table = bounded.hash_table(value.get("staged_file_set"), "prepared source set")
    require(set(table) == BASE_FILES and value.get("staged_directory_set") == sorted(bounded.expected_directories(table)) and
            value.get("staged_sha256") == mod.digest(mod.canonical(table)), "Prepared file/directory identity differs", "stale_input")
    require(table[REL_WORLD] == "817cdce027c83f67e04bffd886f04672a1a48b163386e489766c9e2d2b8fdee4" and
            table[REL_WORLD + ".meta"] == "de1a5d7ee9afdd841773c6d00cea2a0e7352cba39550cfb63b05a90872d51550",
            "Selected experimental world/meta bytes differ", "stale_input")
    bounded.exact_tree(addon, table)
    require(mod.read(addon / "addon.gproj").count(b'ID "BerylComponentCallbackProbe"') == 1 and
            mod.read(addon / "addon.gproj").count(b'GUID "BCBCA11B20261008"') == 1,
            "Prepared addon identity differs", "stale_input")
    selected = bounded.validate_build(value.get("source_build_result"))
    original = value.get("original_artifact")
    require(type(original) is dict and original.get("retained") == str(receipt_path.parent / "original-artifact"),
            "Original artifact retention path differs", "stale_input")
    retained = Path(original["retained"])
    clean_path(retained)
    manifest, _ = bounded.artifact_identity(retained, selected)
    actual, dirs = bounded.tree_files(retained)
    expected_artifact = {"artifact.json": mod.digest(mod.read(retained / "artifact.json")), **manifest["sidecars"],
                         **{"addon/" + name: fingerprint for name, fingerprint in manifest["files"].items()}}
    require(set(manifest["files"]) == {"addon.gproj", "scripts/Game/Beryl/Beryl_Generated.c"} and
            actual == expected_artifact == original.get("files") and sorted(dirs) == original.get("directories") and
            manifest["artifact_sha256"] == original.get("artifact_sha256") and
            all(table[name] == fingerprint for name, fingerprint in manifest["files"].items()),
            "Original artifact/source candidate mismatch", "stale_input")
    binding = value.get("expected_compile_binding")
    require(type(binding) is dict and binding == manifest.get("binding") and binding.get("target") == "enfusion" and
            binding.get("contract_profile") == "enfusion.tablet.script-component.v1" and
            type(binding.get("sha256")) is str and HASH.fullmatch(binding["sha256"]) and
            type(binding.get("version")) is str and len(binding["version"]) <= 80,
            "Exact prepared engine binding unavailable", "unavailable")
    return addon, dict(table), binding, retained, actual, sorted(dirs)


def normalize(raw):
    require(type(raw) is dict and set(raw) == WIRE_FIELDS, "Missing or unknown startup response fields")
    result = copy.deepcopy(raw)
    codec = {"schema_version": 1, "name": "enfusion.jsonapistruct.bool01.v1", "numeric_boolean_fields": []}
    for name in WIRE_BOOLS:
        value = raw[name]
        require(type(value) is bool or (type(value) is int and value in (0, 1)), "Invalid exact startup Boolean: " + name)
        if type(value) is int:
            result[name] = value == 1
            codec["numeric_boolean_fields"].append(name)
    require(all(type(raw[name]) is str and len(raw[name]) <= 2048 and "\x00" not in raw[name] for name in WIRE_STRINGS),
            "Invalid bounded startup string")
    require(result["status"] in ("pending", "ready", "failure", "unavailable"), "Unknown startup status")
    return result, codec


def ready(response, token, world, opening="startup-cli"):
    require(set(response) == WIRE_FIELDS and all(type(response[name]) is bool for name in WIRE_BOOLS), "Not normalized startup response")
    require(opening in OPENING_PROFILES and response["token"] == token and response["action"] == "observe" and response["mechanism"] == OPENING_PROFILES[opening],
            "Startup response identity differs", "stale_input")
    require(response["status"] == "ready" and response["failure"] == "", "Startup did not reach exact readiness", "unavailable")
    required = set(WIRE_BOOLS) - {"game_mode", "in_play_mode"}
    require(all(response[name] for name in required) and not response["game_mode"] and not response["in_play_mode"],
            "Startup response does not prove owned edit-world readiness")
    require(response["resource_name"] == RESOURCE and response["resource_path"] != "" and response["world_path"] != "" and
            all(response[name].replace("\\", "/") == world for name in ("addon_world_path", "resource_absolute_path", "world_absolute_path")),
            "Native startup resource/world identity differs", "stale_input")


def render(template, token, world, opening="startup-cli"):
    require(opening in OPENING_PROFILES, "Unknown installed resource-opening profile")
    require(HASH.fullmatch(token) and all(code not in world for code in ("\x00", "\n", "\r")), "Invalid literal rendering input")
    text = template.decode("utf-8").replace("@TOKEN@", token).replace("@MECHANISM@", OPENING_PROFILES[opening]).replace("@WORLD_ABSOLUTE@", world.replace("\\", "\\\\").replace('"', '\\"'))
    require(not re.search(r"@[A-Z_]+@", text), "Unresolved trusted startup placeholder")
    return text.encode("utf-8")


def compile_status(value, binding, tools):
    if type(value) is not dict or type(value.get("result")) is not dict:
        return "attempted_incomplete"
    detail = value["result"]
    if detail.get("Stage") == "Compiled":
        if (detail.get("Ok") is False or (type(detail.get("ExitCode")) is int and detail["ExitCode"] != 0) or
                (type(detail.get("ErrorCount")) is int and detail["ErrorCount"] != 0)):
            return "executed_failure"
        if (type(value.get("schema_version")) is int and value["schema_version"] == 1 and value.get("stage") == "workbench_compile" and
                value.get("status") == "success" and detail.get("Ok") is True and type(detail.get("ExitCode")) is int and
                detail["ExitCode"] == 0 and type(detail.get("ErrorCount")) is int and detail["ErrorCount"] == 0 and
                value.get("engine_sha256") == binding["sha256"] and value.get("engine_version") == binding["version"] and
                value.get("tools") == {name: tools[name] for name in COMPILE_TOOLS}):
            return "executed_success"
        return "executed_unverified"
    if detail.get("Stage") == "DidNotStart":
        return "not_started"
    return "attempted_incomplete"


def retained_logs(root, raw):
    detail = raw.get("result") if type(raw) is dict else None
    if type(detail) is not dict or not detail.get("LogDir"):
        return []
    source = Path(detail["LogDir"])
    require(source.is_dir() and not bounded.linked(source), "Raw compile logs unavailable", "unavailable")
    paths = sorted(source.glob("*.log"))
    require(0 < len(paths) <= 256, "Raw compile log count exceeds bound", "unavailable")
    result, total = [], 0
    for index, path in enumerate(paths):
        item = identity(path)
        total += item["bytes"]
        require(item["bytes"] <= 64 * 1024 * 1024 and total <= 128 * 1024 * 1024, "Compile log bytes exceed bound", "unavailable")
        target = root / "compile-logs" / (str(index).zfill(4) + "-" + path.name)
        target.parent.mkdir(exist_ok=True)
        with path.open("rb") as incoming, target.open("xb") as outgoing:
            shutil.copyfileobj(incoming, outgoing, 1024 * 1024)
        copied = identity(target)
        require(identity(path) == item and copied["sha256"] == item["sha256"] and copied["bytes"] == item["bytes"],
                "Compile log changed during retention", "stale_input")
        result.append({"original": str(path), "retained": str(target), "sha256": copied["sha256"], "bytes": copied["bytes"]})
    return result


def capture_result(record, label, path):
    """Capture errors are additional evidence, never a replacement exit cause."""
    try:
        if path.is_file():
            item = identity(path)
            data = mod.read(path)
            require(len(data) == item["bytes"] and mod.digest(data) == item["sha256"], "Adapter receipt changed during capture", "stale_input")
            record["raw_results"][label] = {**item, "result": mod.parse(data)}
    except (mod.Failure, OSError, ValueError) as exc:
        record["evidence_errors"].append({"stage": label + "_receipt_capture", "type": type(exc).__name__, "message": str(exc)})


def runtime_input_files(fixture_format="legacy"):
    require(fixture_format in ("legacy", "source-layered-v1"), "Unknown installed world-fixture format")
    return BASE_FILES | {HANDLER_PATH} | ({"worlds/BerylCallbackProbe_Layers/default.layer"} if fixture_format == "source-layered-v1" else set())


def validate_runtime(value, token, addon, engine, binding, tools, manifest_path, expected_manifest, adapter_hash,
                     opening="startup-cli", fixture_format="legacy"):
    require(opening in OPENING_PROFILES, "Unknown installed resource-opening profile")
    expected_files = runtime_input_files(fixture_format)
    if fixture_format == "source-layered-v1":
        require(opening in ("startup-cli", "module-netapi-registered"),
                "Layered fixture requires an explicit installed CLI or registered opening profile")
        source_package = ROOT / "packages/sparkos/workbench-layered-world"
        for name in (REL_WORLD, "worlds/BerylCallbackProbe_Layers/default.layer"):
            require(mod.read(mod.safe_path(addon, name, True)) == mod.read(mod.safe_path(source_package, name, True)),
                    "Layered fixture differs from its installed fixed template", "stale_input")
    require(type(value) is dict and type(value.get("schema_version")) is int and value["schema_version"] == 1 and
            value.get("status") == "success" and value.get("stage") == "startup_readiness_complete" and
            value.get("opening_mechanism") == opening and value.get("mechanism") == OPENING_PROFILES[opening] and value.get("token") == token and value.get("function") == FUNCTION and
            value.get("project_id") == PROJECT_ID and value.get("engine_sha256") == binding["sha256"] and
            value.get("engine_version") == binding["version"] and value.get("engine_path", "").replace("\\", "/").casefold() == str(engine).replace("\\", "/").casefold() and
            value.get("tools") == {name: tools[name] for name in RUNTIME_TOOLS}, "No exact successful startup transport envelope")
    require(value.get("adapter_sha256") == adapter_hash == identity(ADAPTER)["sha256"],
            "Startup adapter receipt/current source identity differs", "stale_input")
    require(value.get("scope") == OPENING_SCOPES[opening] and
            all(value.get(name) == "not_run" for name in ("callback_execution", "play", "spawn", "save", "policy_changes")),
            "Startup receipt claims or omits unsupported callback/play/spawn/save/policy scope")
    require(value.get("limits") == {"stage_ms": 30000, "rpc_ms": 8000, "total_ms": 180000, "cleanup_ms": 5000,
            "max_polls": 64, "native_launch_and_bridge_calls_not_hard_cancelled": True, "raw_logs_aggregate_bytes": 67108864},
            "Startup execution budgets differ")
    require(all(type(value["limits"][name]) is int for name in ("stage_ms", "rpc_ms", "total_ms", "cleanup_ms", "max_polls", "raw_logs_aggregate_bytes")) and
            value["limits"]["native_launch_and_bridge_calls_not_hard_cancelled"] is True, "Startup execution budget types differ")
    require(type(expected_manifest) is dict and set(expected_manifest) == {"schema_version", "files", "directories"} and
            type(expected_manifest["schema_version"]) is int and expected_manifest["schema_version"] == 1 and
            type(expected_manifest["files"]) is dict and
            set(expected_manifest["files"]) == expected_files and
            expected_manifest["directories"] == sorted(bounded.expected_directories(expected_manifest["files"])) and
            mod.canonical(mod.parse(mod.read(manifest_path))) == mod.canonical(expected_manifest),
            "Expected exact selected startup manifest changed", "stale_input")
    manifest_record = value.get("input_manifest")
    require(type(manifest_record) is dict and set(manifest_record) == {"path", "sha256"} and
            manifest_record.get("path", "").replace("\\", "/").casefold() == str(manifest_path).replace("\\", "/").casefold() and
            manifest_record.get("sha256") == identity(manifest_path)["sha256"] and
            mod.canonical(value.get("staged_inputs")) == mod.canonical(expected_manifest),
            "Startup receipt is not bound to the exact input manifest", "stale_input")
    derived = bounded.staged_tree(addon, expected_manifest["files"])
    outputs = value.get("engine_outputs")
    require(type(outputs) is list and len(outputs) == len(derived), "Derived engine outputs are missing or unaccounted")
    for observed_output, actual_output in zip(outputs, derived):
        require(type(observed_output) is dict and set(observed_output) == {"path", "relative", "sha256", "bytes"} and
                observed_output.get("path", "").replace("\\", "/").casefold() == actual_output["path"].replace("\\", "/").casefold() and
                observed_output["relative"] == "resourceDatabase.rdb" and observed_output["sha256"] == actual_output["sha256"] and
                type(observed_output["bytes"]) is int and observed_output["bytes"] == actual_output["bytes"] <= 8 * 1024 * 1024,
                "Derived root resource database identity or bound differs", "stale_input")
    require(value.get("evidence_errors") == [] and value.get("cleanup") in ("owned_process_stopped", "owned_process_already_exited") and
            type(value.get("elapsed_ms")) is int and 0 <= value["elapsed_ms"] < 180000,
            "Startup receipt has incomplete cleanup, evidence errors or expired deadline")
    session = value.get("session")
    require(type(session) is dict and type(session.get("process_id")) is int and session["process_id"] > 0 and
            type(session.get("start_ticks")) is int and session["start_ticks"] > 0 and session.get("reused") is False and
            session.get("project") == str(addon) and session.get("executable", "").replace("\\", "/").casefold() == str(engine).replace("\\", "/").casefold(),
            "Startup owned session identity differs")
    argv = ["-gproj", str(addon / "addon.gproj"), "-noOpenLastResource", "-scriptAuthorizeAll"]
    if opening == "startup-cli":
        argv += ["-wbmodule=WorldEditor", "-run", "-load", REL_WORLD]
    elif opening in ("module-netapi-resource", "module-netapi-registered"):
        argv += ["-wbmodule=WorldEditor", "-run"]
    require(value.get("arguments") == argv, "Recorded opening-profile argument vector differs")
    calls = value.get("rpcs")
    require(type(calls) is list and 2 <= len(calls) <= 132, "Missing or excessive startup RPCs")
    ports = value.get("port_checks")
    require(type(ports) is list and 1 <= len(ports) <= 64, "Missing or excessive passive listener observations")
    require(all(type(row) is dict and type(row.get("elapsed_ms")) is int and 0 <= row["elapsed_ms"] < value["elapsed_ms"] and
                type(row.get("listening")) is bool and
                ((row["listening"] and type(row.get("owning_process")) is int and row["owning_process"] == session["process_id"]) or
                 (not row["listening"] and row.get("owning_process") is None)) for row in ports) and ports[-1]["listening"],
            "Transport listener is not the exact owned process")
    require([row["elapsed_ms"] for row in ports] == sorted(row["elapsed_ms"] for row in ports), "Listener observations are out of order")
    previous, observed, sites, order, health_ready = -1, [], ["startup.identity"] + ["port.check"] * len(ports), [], False
    for call in calls:
        require(type(call) is dict and call.get("function") in ("IsWorkbenchRunning", "GetLoadedProjects", FUNCTION, "OpenResource") and
                "action" in call and call["action"] == ("observe" if call["function"] == FUNCTION else None) and
                type(call.get("elapsed_ms")) is int and previous <= call["elapsed_ms"] < 180000 and
                type(call.get("timeout_ms")) is int and 1 <= call["timeout_ms"] <= 8000 and
                type(call.get("duration_ms")) is int and 0 <= call["duration_ms"] < call["timeout_ms"] and
                call["elapsed_ms"] + call["duration_ms"] < value["elapsed_ms"], "Invalid bounded startup RPC entry")
        previous = call["elapsed_ms"]
        expected_params = {"token": token, "action": "observe"} if call["function"] == FUNCTION else (
            {"ResourceName": str(addon / REL_WORLD)} if call["function"] == "OpenResource" else {})
        actual_params = call.get("params")
        if call["function"] == "OpenResource":
            require(type(actual_params) is dict and set(actual_params) == {"ResourceName"} and type(actual_params["ResourceName"]) is str,
                    "Recorded native resource request has invalid typed parameters")
            if opening == "module-netapi-registered":
                require(actual_params["ResourceName"] == RESOURCE, "Recorded native request is not the exact verified registered resource name")
            else:
                require(actual_params["ResourceName"].replace("\\", "/") == (addon / REL_WORLD).as_posix(),
                        "Recorded native resource request is not the exact owned absolute path")
        else:
            require(actual_params == expected_params, "Recorded native request arguments differ")
        order.append(call["function"])
        sites.append("before." + call["function"])
        if call.get("result") is None:
            require(False, "Missing RPC result; failed calls are never retried into success")
        reply = call["result"]
        require(type(reply) is dict and reply.get("Ok") is True and reply.get("Function") == call["function"] and
                reply.get("ErrorCode") == "Ok" and type(reply.get("Raw")) is str and len(reply["Raw"]) <= 1024 * 1024 and
                type(reply.get("Response")) is dict and mod.canonical(mod.parse(reply["Raw"].encode("utf-8"))) == mod.canonical(reply["Response"]),
                "Missing or unrelated raw startup result")
        sites.append("after." + call["function"])
        if call["function"] == "IsWorkbenchRunning":
            require(not health_ready and set(reply["Response"]) == {"IsRunning", "ScriptsCompiled"} and
                    all(type(val) is bool or (type(val) is int and val in (0, 1)) for val in reply["Response"].values()),
                    "Unknown health fields/codec or health retry after readiness")
            health_ready = all(bool(val) for val in reply["Response"].values())
        else:
            require(health_ready, "Addon/readiness lookup preceded actual healthy compiled Workbench")
        if call["function"] == "OpenResource":
            raw_open = reply["Response"]
            require(opening in ("netapi-resource", "module-netapi-resource", "module-netapi-registered") and type(raw_open) is dict and set(raw_open) == {"Opened"} and
                    (type(raw_open["Opened"]) is bool or (type(raw_open["Opened"]) is int and raw_open["Opened"] in (0, 1))),
                    "Native OpenResource outcome fields or exact Boolean codec differ")
            open_codec = {"schema_version": 1, "name": "enfusion.jsonapistruct.bool01.v1",
                          "numeric_boolean_fields": ["Opened"] if type(raw_open["Opened"]) is int else []}
            require(mod.canonical(call.get("normalized_response")) == mod.canonical({"Opened": bool(raw_open["Opened"])}) and
                    mod.canonical(call.get("codec")) == mod.canonical(open_codec) and bool(raw_open["Opened"]) and
                    mod.canonical(value.get("native_open")) == mod.canonical(reply),
                    "Native OpenResource was refused or lacks its exact retained outcome")
        if call["function"] == FUNCTION:
            response, codec = normalize(reply["Response"])
            require(mod.canonical(response) == mod.canonical(call.get("normalized_response")) and mod.canonical(codec) == mod.canonical(call.get("codec")) and
                    response["token"] == token and response["action"] == "observe" and response["mechanism"] == OPENING_PROFILES[opening] and
                    response["status"] in ("pending", "ready") and response["failure"] == "", "Startup wire/normalized response identity differs")
            observed.append(response)
            require(response["addon_world_resolved"] and response["resource_name_resolved"] and
                    response["resource_name"] == RESOURCE and response["resource_path"] != "" and
                    response["addon_world_path"].replace("\\", "/") == (addon / REL_WORLD).as_posix() and
                    response["resource_absolute_path"].replace("\\", "/") == (addon / REL_WORLD).as_posix() and
                    not response["game_mode"] and not response["in_play_mode"] and
                    (not response["api_present"] or response["module_present"]),
                    "Pending observation has wrong resource, mode or inconsistent API identity")
            if response["world_path"] != "":
                require(response["world_path_resolved"] and response["world_matches"] and
                        response["world_absolute_path"].replace("\\", "/") == (addon / REL_WORLD).as_posix(),
                        "Nonempty pending world is foreign or unresolved")
    minimum_observations = 2 if opening != "startup-cli" else 1
    require(minimum_observations <= len(observed) <= 64 + minimum_observations - 1 and
            mod.canonical(observed[-1]) == mod.canonical(value.get("completion")),
            "Final completion is not the actual last observed reply")
    expected_prefix = ["IsWorkbenchRunning", "GetLoadedProjects"]
    if opening != "startup-cli":
        expected_prefix += [FUNCTION, "OpenResource"]
        require(mod.canonical(value.get("preliminary")) == mod.canonical(observed[0]) and observed[0]["addon_world_resolved"] and observed[0]["resource_name_resolved"],
                "Native opener lacks its actual prior owned-resource observation")
    else:
        require("native_open" in value and "preliminary" in value and
                value["native_open"] is None and value["preliminary"] is None,
                "Startup CLI profile includes unselected native opening evidence")
    require(order[:len(expected_prefix)] == expected_prefix and order[len(expected_prefix):] == [FUNCTION] * (len(order) - len(expected_prefix)) and
            len(order) > len(expected_prefix), "Opening profile RPC order/count differs")
    require(mod.canonical(value.get("health")) == mod.canonical(calls[0]["result"]), "Top-level health is not the actual single retained health reply")
    ready(observed[-1], token, (addon / REL_WORLD).as_posix(), opening)
    loaded = value.get("loaded_projects")
    require(type(loaded) is dict and loaded.get("Ok") is True and loaded.get("Function") == "GetLoadedProjects" and
            type(loaded.get("Response")) is dict and type(loaded["Response"].get("Loaded Projects")) is list and
            PROJECT_ID in loaded["Response"]["Loaded Projects"] and
            sum(call.get("function") == "GetLoadedProjects" and mod.canonical(call.get("result")) == mod.canonical(loaded) for call in calls) == 1,
            "Loaded addon identity is not an actual unique retained reply")
    checks = value.get("session_checks")
    require(type(checks) is list and all(type(check) is dict for check in checks) and
            [check.get("site") for check in checks] == sites, "Startup boundary ownership observations are incomplete")
    require(all(type(check.get("process_id")) is int and check["process_id"] == session["process_id"] and
                type(check.get("start_ticks")) is int and check["start_ticks"] == session["start_ticks"] and
                check.get("executable", "").replace("\\", "/").casefold() == str(engine).replace("\\", "/").casefold() and
                type(check.get("elapsed_ms")) is int and 0 <= check["elapsed_ms"] < 180000 for check in checks),
            "Startup boundary process identity changed")
    require([check["elapsed_ms"] for check in checks] == sorted(check["elapsed_ms"] for check in checks), "Startup ownership observations are out of order")
    logs = value.get("raw_logs")
    require(type(logs) is list and 0 < len(logs) <= 4096, "No bounded raw startup logs")
    total = 0
    for row in logs:
        require(type(row) is dict and type(row.get("retained")) is str and type(row.get("bytes")) is int and
                0 <= row["bytes"] <= 64 * 1024 * 1024 and type(row.get("sha256")) is str and HASH.fullmatch(row["sha256"]), "Invalid startup raw log identity")
        path = Path(row["retained"])
        require(path.is_relative_to(addon.parent / "startup-logs"), "Raw startup log escaped owned output")
        item = identity(path)
        require(item["sha256"] == row["sha256"] and item["bytes"] == row["bytes"], "Raw startup log changed", "stale_input")
        total += row["bytes"]
    require(total <= 64 * 1024 * 1024, "Raw startup logs exceed aggregate bound", "unavailable")
    return {"status": "verified", "expected_case_ids": list(READY_CASES), "completed_case_ids": list(READY_CASES),
            "complete_expected_case_set": True, "callback_delivery": "not_run", "world_format": "exact_fixture_only"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--prepared-receipt", type=Path)
    parser.add_argument("--expect-prepared-sha256")
    parser.add_argument("--beryl", type=Path)
    parser.add_argument("--expect-compiler-sha256")
    parser.add_argument("--workbench-tools", type=Path)
    parser.add_argument("--powershell-host", type=Path)
    parser.add_argument("--engine-exe", type=Path)
    parser.add_argument("--opening-mechanism", choices=tuple(OPENING_PROFILES), default="startup-cli")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--prepare-only", action="store_true")
    modes.add_argument("--engine-stage", choices=("compile", "runtime"))
    args = parser.parse_args()
    if args.self_test:
        require(not args.prepared_receipt and not args.prepare_only and not args.engine_stage, "Self-test cannot select engine/prepared work")
        self_test()
        return 0
    require(args.prepared_receipt is not None and args.expect_prepared_sha256 is not None and
            (args.prepare_only or args.engine_stage), "Explicit prepared receipt, hash and stage are required")
    work = Path(tempfile.mkdtemp(prefix="workbench startup & spaces-", dir=ROOT / "build"))
    print("Workbench startup evidence: " + str(work), flush=True)
    record = {"schema_version": 1, "operation": "verify.workbench.startup_readiness", "opening_mechanism": args.opening_mechanism,
              "mechanism": OPENING_PROFILES[args.opening_mechanism],
              "status": "failure", "stage": "prepare", "expected_case_ids": list(READY_CASES), "scope": scope(),
              "attempts": {"compile": {"requested": bool(args.engine_stage), "adapter_attempted": False},
                           "runtime": {"requested": args.engine_stage == "runtime", "adapter_attempted": False}},
              "commands": [], "raw_results": {}, "evidence_errors": [], "limitations": [
              "Only exact fixture startup readiness; no callbacks, tablet services, play, multiplayer, visual or performance claim.",
              "GenericWorldEntity serialization remains experimental until exact native readiness is observed.",
              "Existing copied callback opener is dormant: the new handler never invokes it or its actions."]}
    job, unchanged = None, None
    try:
        selection = args.prepared_receipt.absolute()
        clean_path(selection)
        require(selection.is_relative_to(ROOT / "build") and not bounded.linked(selection.parent) and HASH.fullmatch(args.expect_prepared_sha256),
                "Prepared receipt must be an identified owned build input")
        receipt_bytes = mod.read(selection)
        require(mod.digest(receipt_bytes) == args.expect_prepared_sha256, "Prepared receipt hash differs", "stale_input")
        selected = mod.parse(receipt_bytes)
        original, original_files, binding, retained, retained_files, retained_dirs = prepared(selected, selection)
        record.update(prepared_receipt=identity(selection), prepared_artifact_sha256=selected["original_artifact"]["artifact_sha256"],
                      original_addon=str(original), original_files=original_files, original_artifact=str(retained),
                      historical_compiler_sha256=selected["source_build_result"]["compiler_sha256"], binding=binding)
        inputs = [Path(__file__).resolve(), PACKAGE / "rpc.c.in", PACKAGE / "README.md", ADAPTER,
                  ROOT / "scripts/verify-component-engine.py", *mod.bundle_paths()]
        for name, fingerprint in DOCS.items():
            path = DOC_ROOT / name
            require(identity(path)["sha256"] == fingerprint, "Installed startup declaration changed", "stale_input")
            inputs.append(path)
        tools, compiler, host, engine = {}, None, None, None
        if args.engine_stage:
            require(all((args.beryl, args.expect_compiler_sha256, args.workbench_tools, args.powershell_host, args.engine_exe)),
                    "Engine stage requires explicit compiler/hash, tools, host and engine paths", "unavailable")
            compiler, host, engine = (path.absolute() for path in (args.beryl, args.powershell_host, args.engine_exe))
            require(compiler.is_relative_to(ROOT / "build") and compiler.parent != ROOT / "build" and
                    HASH.fullmatch(args.expect_compiler_sha256) and identity(compiler)["sha256"] == args.expect_compiler_sha256,
                    "Private configured compiler identity differs", "stale_input")
            require(identity(engine)["sha256"] == binding["sha256"], "Configured engine differs from retained binding", "stale_input")
            require(identity(host)["bytes"] > 0, "Configured PowerShell host unavailable", "unavailable")
            for name in sorted(set(COMPILE_TOOLS + RUNTIME_TOOLS)):
                path = mod.safe_path(args.workbench_tools.absolute(), "scripts/" + name, True)
                tools[name] = identity(path)["sha256"]
                inputs.append(path)
            inputs += [compiler, host, engine, mod.HERE / "engine-compile.ps1"]
        frozen = {str(path): identity(path) for path in inputs}
        record["verification_inputs"] = frozen
        record["plugin_file_set"] = tools
        record["retained_inputs"] = []
        for index, (name, item) in enumerate(frozen.items()):
            if item["bytes"] > 16 * 1024 * 1024:
                record["retained_inputs"].append({**item, "retention": "fingerprint_only_large_binary"})
                continue
            data = mod.read(Path(name))
            require(len(data) == item["bytes"] and mod.digest(data) == item["sha256"], "Verification input changed before capture", "stale_input")
            target = work / "inputs" / (str(index).zfill(4) + "-" + Path(name).name + ".input")
            write(target, data)
            record["retained_inputs"].append({**item, "retained": str(target), "retention": "exact_bytes"})
        record["selected_receipt_raw"] = {"retained": str(work / "prepared-receipt.raw.json"), "sha256": mod.digest(receipt_bytes)}
        write(work / "prepared-receipt.raw.json", receipt_bytes)
        saved(work / "prepared-receipt.json", selected)
        template = mod.read(PACKAGE / "rpc.c.in")
        addon = work / "probe-addon"
        token = mod.digest(mod.canonical({"receipt": args.expect_prepared_sha256, "files": original_files,
                          "handler": mod.digest(template), "addon": str(addon), "profile": args.opening_mechanism + ".v1"}))
        for name, fingerprint in original_files.items():
            data = mod.read(mod.safe_path(original, name, True))
            require(mod.digest(data) == fingerprint, "Prepared source changed during copy", "stale_input")
            write(mod.safe_path(addon, name), data)
        write(mod.safe_path(addon, HANDLER_PATH), render(template, token, (addon / REL_WORLD).as_posix(), args.opening_mechanism))
        table, dirs = bounded.tree_files(addon)
        require(set(table) == BASE_FILES | {HANDLER_PATH}, "Unexpected staged startup files")
        manifest = {"schema_version": 1, "files": table, "directories": sorted(dirs)}
        saved(work / "input-manifest.json", manifest)
        record.update(token=token, function=FUNCTION, candidate_path=str(addon), staged_file_set=table,
                      staged_directory_set=sorted(dirs), staged_sha256=mod.digest(mod.canonical(table)), passive_documents=DOCS)
        record["scope"]["source_copy"] = "executed_success"

        def check():
            require(mod.read(selection) == receipt_bytes, "Prepared receipt changed", "stale_input")
            bounded.exact_tree(original, original_files)
            bounded.exact_tree(retained, retained_files)
            require(sorted(bounded.tree_files(retained)[1]) == retained_dirs, "Artifact directories changed", "stale_input")
            for path, item in frozen.items():
                require(identity(Path(path)) == item, "Verification input changed: " + path, "stale_input")
            require(mod.read(work / "prepared-receipt.raw.json") == receipt_bytes, "Retained selected receipt changed", "stale_input")
            for item in record["retained_inputs"]:
                if item["retention"] == "exact_bytes":
                    copied = identity(Path(item["retained"]))
                    require(copied["sha256"] == item["sha256"] and copied["bytes"] == item["bytes"], "Retained verification input changed", "stale_input")
            record["engine_derived_outputs"] = bounded.staged_tree(addon, table)
            require(mod.parse(mod.read(work / "input-manifest.json")) == manifest, "Input manifest changed", "stale_input")
        unchanged = check
        check()
        if args.prepare_only:
            record.update(status="success", stage="prepared", success_means="identified source copied and read-only handler staged; no engine execution")
        else:
            project = work / "job-project"
            project.mkdir()
            job = mod.Job(project, "workbench-startup-probe", compiler)
            job.result.update(source_sha256=record["staged_sha256"], binding_sha256=mod.digest(mod.canonical(binding)))
            compile_path = work / "engine-compile.json"
            record["stage"] = "engine_compile"
            record["attempts"]["compile"]["adapter_attempted"] = True
            record["scope"]["engine_compilation"] = "attempted_unconfirmed"
            try:
                job.run([host, "-NoProfile", "-File", mod.HERE / "engine-compile.ps1", "-ToolRoot", args.workbench_tools.absolute(),
                         "-ProjectDir", addon, "-ResultPath", compile_path, "-ExpectedVersion", binding["version"],
                         "-TimeoutSeconds", "30"], "startup_engine_compile", work, timeout=60)
            finally:
                capture_result(record, "compile", compile_path)
                if "compile" in record["raw_results"]:
                    raw = record["raw_results"]["compile"]["result"]
                    record["scope"]["engine_compilation"] = compile_status(raw, binding, tools)
                    try:
                        record["compile_logs"] = retained_logs(work, raw)
                    except (mod.Failure, OSError, ValueError) as exc:
                        record["evidence_errors"].append({"stage": "compile_log_capture", "type": type(exc).__name__, "message": str(exc)})
            require(record["scope"]["engine_compilation"] == "executed_success" and not record["evidence_errors"], "Headless compile did not provide exact complete success")
            check()
            if args.engine_stage == "runtime":
                runtime_path = work / "engine-runtime.json"
                record["stage"] = "startup_world_readiness"
                record["attempts"]["runtime"]["adapter_attempted"] = True
                record["scope"]["startup_world_readiness"] = "attempted_unconfirmed"
                try:
                    job.run([host, "-NoProfile", "-File", ADAPTER, "-ToolRoot", args.workbench_tools.absolute(), "-ProjectDir", addon,
                             "-ProjectId", PROJECT_ID, "-ResultPath", runtime_path, "-InputManifest", work / "input-manifest.json",
                             "-Token", token, "-ExpectedEngineHash", binding["sha256"], "-ExpectedEngineVersion", binding["version"],
                             "-ExpectedEnginePath", engine, "-OpeningMechanism", args.opening_mechanism], "startup_runtime_readiness", work, timeout=240)
                finally:
                    capture_result(record, "runtime", runtime_path)
                require("runtime" in record["raw_results"], "Missing startup adapter result", "unavailable")
                record["readiness_comparison"] = validate_runtime(record["raw_results"]["runtime"]["result"], token, addon, engine, binding, tools,
                    work / "input-manifest.json", manifest, frozen[str(ADAPTER)]["sha256"], args.opening_mechanism)
                record["scope"]["startup_world_readiness"] = "executed_success"
                check()
            record.update(status="success", stage="verified", success_means="exact engine compile" if args.engine_stage == "compile" else "exact owned startup-world readiness; callbacks not run")
    except (mod.Failure, OSError, ValueError, KeyboardInterrupt) as exc:
        record["status"] = "cancelled" if isinstance(exc, KeyboardInterrupt) else getattr(exc, "status", "failure")
        # Preserve the returned adapter's actual failure classification separately
        # from a nonzero host exit. Never turn missing evidence into success.
        if isinstance(exc, mod.Failure):
            for label in ("runtime", "compile"):
                raw = record["raw_results"].get(label, {}).get("result")
                if type(raw) is dict and raw.get("status") in ("failure", "unavailable", "timeout", "cancelled", "stale_input"):
                    record["status"] = raw["status"]
                    break
        record["failure"] = {"type": type(exc).__name__, "message": str(exc)}
    finally:
        if unchanged is not None:
            try:
                unchanged()
            except (mod.Failure, OSError, ValueError) as exc:
                record["evidence_errors"].append({"stage": "final_input_guard", "message": str(exc)})
                if record["status"] == "success":
                    record["status"] = getattr(exc, "status", "stale_input")
        if job is not None:
            record["commands"] = job.result["raw_logs"]
            for label, stage in (("compile", "startup_engine_compile"), ("runtime", "startup_runtime_readiness")):
                logs = [log for log in record["commands"] if Path(log.get("stdout", "")).name.endswith("-" + stage + ".stdout.log")]
                if logs:
                    record["attempts"][label]["process_outcome"] = logs[-1]["status"]
                    record["attempts"][label]["exit_confirmed"] = logs[-1].get("exit_confirmed")
                    record["attempts"][label]["cleanup_errors"] = logs[-1].get("cleanup_errors", [])
                    if record["status"] == "success" and (logs[-1].get("exit_confirmed") is not True or logs[-1].get("cleanup_errors")):
                        record["status"] = "unavailable"
                        record["evidence_errors"].append({"stage": label + "_host_cleanup", "message": "Host process exit/owned cleanup did not confirm complete success"})
            job.result.update(status=record["status"], stage=record["stage"])
            saved(job.path / "result.json", job.result)
            record["job"] = job.result
        saved(work / "results.json", record)
        print(str(work / "results.json"), flush=True)
    return 0 if record["status"] == "success" else 1


def self_test():
    """No subprocesses: prepared trees, codecs and deliberate evidence faults."""
    work = Path(tempfile.mkdtemp(prefix="workbench-startup-inert-", dir=ROOT / "build"))
    own_bytes = Path(__file__).read_bytes()
    test_inputs = {str(path): identity(path) for path in
                   (Path(__file__).resolve(), ADAPTER, PACKAGE / "rpc.c.in", PACKAGE / "README.md",
                    ROOT / "scripts/verify-component-engine.py", *mod.bundle_paths())}
    retained_inputs = []
    for index, (name, item) in enumerate(test_inputs.items()):
        data = mod.read(Path(name))
        require(len(data) == item["bytes"] and mod.digest(data) == item["sha256"], "Inert input changed before retention", "stale_input")
        target = work / "inputs" / (str(index).zfill(4) + "-" + Path(name).name + ".input")
        write(target, data)
        retained_inputs.append({**item, "retained": str(target)})
    cases = []
    def passed(name, fn):
        fn()
        cases.append({"id": name, "status": "passed"})
    def rejected(name, fn):
        try:
            fn()
        except (mod.Failure, OSError, ValueError) as exc:
            cases.append({"id": name, "status": "rejected", "outcome": getattr(exc, "status", "failure"), "diagnostic": str(exc)})
        else:
            raise AssertionError("Deliberate fault was admitted: " + name)

    fixture = work / "fixture"
    addon = fixture / "probe-addon"
    data = {name: b"fixture\n" for name in BASE_FILES}
    data["addon.gproj"] = b'GameProject { ID "BerylComponentCallbackProbe" GUID "BCBCA11B20261008" }\n'
    # Known source bytes, used only as passive text in an inert directory.
    data[REL_WORLD] = mod.read(ROOT / "packages/sparkos/component-callback-probe" / REL_WORLD)
    data[REL_WORLD + ".meta"] = mod.read(ROOT / "packages/sparkos/component-callback-probe" / (REL_WORLD + ".meta"))
    for name, value in data.items():
        write(mod.safe_path(addon, name), value)
    table, dirs = bounded.tree_files(addon)
    binding = {"target": "enfusion", "version": "fixture.1", "sha256": "e" * 64, "contract_profile": "enfusion.tablet.script-component.v1"}
    body = {"schema_version": 1, "inputs": {"src/state.be": "a" * 64}, "files": {"addon.gproj": table["addon.gproj"],
            "scripts/Game/Beryl/Beryl_Generated.c": table["scripts/Game/Beryl/Beryl_Generated.c"]},
            "sidecars": {"source-map.json": mod.digest(b"{}")}, "binding": binding, "compiler_sha256": "b" * 64,
            "tool_sha256": "c" * 64, "source_sha256": mod.digest(mod.canonical({"src/state.be": "a" * 64}))}
    manifest = {**body, "id": "d" * 32, "artifact_sha256": mod.digest(mod.canonical(body))}
    original = fixture / "original-artifact"
    saved(original / "artifact.json", manifest)
    write(original / "source-map.json", b"{}")
    for name in body["files"]:
        write(original / "addon" / name, data[name])
    original_table, original_dirs = bounded.tree_files(original)
    selected = {"schema_version": 1, "operation": "mod build", "stage": "candidate", "status": "success", "companion_version": 2,
                "component_generation": {"status": "generated", "subset": "depth_one_bool_i32_f32_state"},
                "artifact_id": manifest["id"], **{name: manifest[name] for name in ("artifact_sha256", "compiler_sha256", "tool_sha256", "source_sha256")}}
    value = {"schema_version": 1, "operation": "verify.component_callbacks.runtime", "status": "success", "stage": "prepared",
             "expected_case_ids": list(CALLBACK_CASES), "candidate_path": str(addon), "staged_file_set": table,
             "staged_directory_set": sorted(dirs), "staged_sha256": mod.digest(mod.canonical(table)), "source_build_result": selected,
             "expected_compile_binding": binding, "original_artifact": {"retained": str(original), "files": original_table,
             "directories": sorted(original_dirs), "artifact_sha256": manifest["artifact_sha256"]},
             "scope": {"source_generation": "executed_success", "engine_compilation": "not_run", "engine_runtime_callbacks": "not_run", "engine_callback_delivery": "not_run"}}
    receipt = fixture / "results.json"
    passed("prepared.valid", lambda: prepared(value, receipt))
    for case, key, replacement in (("schema-bool", "schema_version", True), ("failed", "status", "failure"),
                                  ("not-prepared", "stage", "verified"), ("wrong-operation", "operation", "other")):
        mutated = {**value, key: replacement}
        rejected("prepared." + case, lambda v=mutated: prepared(v, receipt))
    altered = copy.deepcopy(value); altered["scope"]["engine_callback_delivery"] = "executed_success"
    rejected("prepared.callbacks-claimed", lambda: prepared(altered, receipt))
    rejected("prepared.wrong-cases", lambda: prepared({**value, "expected_case_ids": []}, receipt))
    rejected("prepared.wrong-path", lambda: prepared({**value, "candidate_path": str(work)}, receipt))
    rejected("prepared.wrong-files", lambda: prepared({**value, "staged_file_set": {}}, receipt))
    bad = {**table, "addon.gproj": "0" * 64}
    rejected("prepared.bad-hash", lambda: prepared({**value, "staged_file_set": bad}, receipt))
    target = addon / "Prefabs/BerylCallbackProbe.et"
    target.write_bytes(b"changed")
    rejected("prepared.changed-copy", lambda: prepared(value, receipt))
    target.write_bytes(data["Prefabs/BerylCallbackProbe.et"])
    (addon / "empty-extra").mkdir()
    rejected("prepared.extra-directory", lambda: prepared(value, receipt))
    (addon / "empty-extra").rmdir()
    bad = {**table, REL_WORLD: "0" * 64}
    rejected("prepared.world-changed", lambda: prepared({**value, "staged_file_set": bad, "staged_sha256": mod.digest(mod.canonical(bad))}, receipt))
    altered = copy.deepcopy(value); altered["original_artifact"]["artifact_sha256"] = "0" * 64
    rejected("prepared.artifact-mismatch", lambda: prepared(altered, receipt))
    world = (addon / REL_WORLD).as_posix()
    good = {name: "" for name in WIRE_STRINGS}
    good.update({name: name not in ("game_mode", "in_play_mode") for name in WIRE_BOOLS})
    good.update(token="a" * 64, action="observe", status="ready", mechanism="startup_cli", addon_world_path=world,
                resource_name=RESOURCE, resource_path=REL_WORLD, resource_absolute_path=world, world_path=REL_WORLD, world_absolute_path=world)
    passed("wire.valid", lambda: ready(normalize(good)[0], "a" * 64, world))
    numeric = {**good, **{name: int(good[name]) for name in WIRE_BOOLS}}
    passed("wire.bool01", lambda: ready(normalize(numeric)[0], "a" * 64, world))
    before = copy.deepcopy(numeric)
    normalize(numeric)
    passed("wire.no-mutation", lambda: require(numeric == before, "Wire input mutated"))
    rejected("wire.extra", lambda: normalize({**good, "unexpected": 1}))
    rejected("wire.missing", lambda: normalize({key: val for key, val in good.items() if key != "world_matches"}))
    for name, replacement in (("string-bool", "1"), ("float-bool", 1.0), ("two-bool", 2)):
        rejected("wire." + name, lambda v=replacement: normalize({**good, "world_matches": v}))
    rejected("wire.oversize", lambda: normalize({**good, "world_path": "x" * 2049}))
    for name, key, replacement in (("token", "token", "b" * 64), ("action", "action", "play"), ("mechanism", "mechanism", "deferred"),
            ("pending", "status", "pending"), ("failure", "status", "failure"), ("addon", "addon_world_path", "foreign"),
            ("resource", "resource_name", "foreign"), ("roundtrip", "resource_absolute_path", "foreign"),
            ("observed-world", "world_absolute_path", "foreign"), ("no-world", "world_present", False), ("no-api", "api_present", False),
            ("no-edit", "edit_mode", False), ("game-mode", "game_mode", True), ("play-mode", "in_play_mode", True),
            ("failure-text", "failure", "native refusal")):
        rejected("ready." + name, lambda k=key, v=replacement: ready({**good, k: v}, "a" * 64, world))
    passed("render.exact", lambda: require(render(b'"@TOKEN@" "@WORLD_ABSOLUTE@"', "a" * 64, world) == ('"' + "a" * 64 + '" "' + world + '"').encode(), "Literal rendering differs"))
    rejected("render.unresolved", lambda: render(b"@OTHER@", "a" * 64, world))
    passed("scope.no-callbacks", lambda: require(scope()["callback_delivery"] == "not_run" and scope()["compiler_execution"] == "not_run", "Scope invented execution"))
    tools = {name: "f" * 64 for name in COMPILE_TOOLS}
    compiled = {"schema_version": 1, "stage": "workbench_compile", "status": "success", "engine_sha256": binding["sha256"],
                "engine_version": binding["version"], "tools": tools, "result": {"Stage": "Compiled", "Ok": True, "ExitCode": 0, "ErrorCount": 0}}
    passed("compile.success", lambda: require(compile_status(compiled, binding, tools) == "executed_success", "Compile evidence rejected"))
    for name, change in (("failed", {"result": {"Stage": "Compiled", "Ok": False, "ExitCode": -1, "ErrorCount": 1}}),
                        ("schema-bool", {"schema_version": True}), ("wrong-engine", {"engine_sha256": "0" * 64}), ("wrong-tools", {"tools": {}})):
        passed("compile." + name, lambda v=change: require(compile_status({**compiled, **v}, binding, tools) != "executed_success", "Bad compile evidence accepted"))
    write(original / "extra.txt", b"unadmitted")
    altered = copy.deepcopy(value)
    altered["original_artifact"]["files"], extra_dirs = bounded.tree_files(original)
    altered["original_artifact"]["directories"] = sorted(extra_dirs)
    rejected("prepared.extra-artifact", lambda: prepared(altered, receipt))
    (original / "extra.txt").unlink()
    rejected("prepared.traversal", lambda: clean_path(work / ".." / "other"))
    template = mod.read(PACKAGE / "rpc.c.in")
    passed("handler.read-only", lambda: require(not any(verb in template for verb in (
        b"OpenModule(", b"SetOpenedResource(", b"OpenResource(", b"SwitchToGameMode(", b"SwitchToEditMode(",
        b"SpawnEntityPrefab(", b"DeleteRplEntity(", b"Sleep(", b"thread ")), "Handler contains an execution request"))
    write(addon / HANDLER_PATH, render(template, "a" * 64, world))
    startup_table, startup_dirs = bounded.tree_files(addon)
    startup_manifest = {"schema_version": 1, "files": startup_table, "directories": sorted(startup_dirs)}
    startup_manifest_path = fixture / "input-manifest.json"
    saved(startup_manifest_path, startup_manifest)
    adapter_hash = identity(ADAPTER)["sha256"]
    engine = work / "passive-engine.input"
    write(engine, b"passive bytes; not an executable\n")
    log = fixture / "startup-logs" / "synthetic" / "console.log"
    write(log, b"inert test log\n")
    def reply(function, response):
        return {"Ok": True, "Function": function, "ErrorCode": "Ok", "Raw": json.dumps(response), "Response": copy.deepcopy(response)}
    calls = [
        {"function": "IsWorkbenchRunning", "action": None, "params": {}, "elapsed_ms": 1, "timeout_ms": 8000, "duration_ms": 0,
         "result": reply("IsWorkbenchRunning", {"IsRunning": True, "ScriptsCompiled": True}), "normalized_response": None, "codec": None},
        {"function": "GetLoadedProjects", "action": None, "params": {}, "elapsed_ms": 2, "timeout_ms": 8000, "duration_ms": 0,
         "result": reply("GetLoadedProjects", {"Loaded Projects": ["ArmaReforger", PROJECT_ID]}), "normalized_response": None, "codec": None},
        {"function": FUNCTION, "action": "observe", "params": {"token": "a" * 64, "action": "observe"}, "elapsed_ms": 3, "timeout_ms": 8000, "duration_ms": 0,
         "result": reply(FUNCTION, numeric), "normalized_response": normalize(numeric)[0], "codec": normalize(numeric)[1]},
    ]
    sites = ["startup.identity"] + [site for call in calls for site in ("before." + call["function"], "after." + call["function"])]
    runtime = {"schema_version": 1, "stage": "startup_readiness_complete", "status": "success", "mechanism": "startup_cli", "opening_mechanism": "startup-cli",
               "token": "a" * 64, "function": FUNCTION, "project_id": PROJECT_ID, "engine_sha256": binding["sha256"],
               "engine_version": binding["version"], "engine_path": str(engine), "tools": {name: "f" * 64 for name in RUNTIME_TOOLS},
               "adapter_sha256": adapter_hash, "scope": "startup-world readiness observation only",
               "callback_execution": "not_run", "play": "not_run", "spawn": "not_run", "save": "not_run", "policy_changes": "not_run",
               "limits": {"stage_ms": 30000, "rpc_ms": 8000, "total_ms": 180000, "cleanup_ms": 5000, "max_polls": 64,
                          "native_launch_and_bridge_calls_not_hard_cancelled": True, "raw_logs_aggregate_bytes": 67108864},
               "input_manifest": {"path": str(startup_manifest_path), "sha256": identity(startup_manifest_path)["sha256"]},
               "staged_inputs": startup_manifest, "engine_outputs": [],
               "evidence_errors": [], "cleanup": "owned_process_stopped", "elapsed_ms": 10,
               "session": {"process_id": 123, "start_ticks": 456, "reused": False, "project": str(addon), "executable": str(engine)},
               "arguments": ["-gproj", str(addon / "addon.gproj"), "-noOpenLastResource", "-scriptAuthorizeAll",
                             "-wbmodule=WorldEditor", "-run", "-load", REL_WORLD],
               "port_checks": [{"elapsed_ms": 0, "listening": True, "owning_process": 123}],
               "rpcs": calls, "health": calls[0]["result"], "completion": normalize(numeric)[0], "loaded_projects": calls[1]["result"],
               "native_open": None, "preliminary": None,
               "session_checks": [{"site": name, "process_id": 123, "start_ticks": 456, "executable": str(engine), "elapsed_ms": i}
                                  for i, name in enumerate([sites[0], "port.check", *sites[1:]])],
               "raw_logs": [{"retained": str(log), "bytes": len(log.read_bytes()), "sha256": mod.digest(log.read_bytes())}]}
    runtime_tools = {**tools, **{name: "f" * 64 for name in RUNTIME_TOOLS}}
    def runtime_check(v):
        return validate_runtime(v, "a" * 64, addon, engine, binding, runtime_tools, startup_manifest_path, startup_manifest, adapter_hash)
    passed("envelope.valid", lambda: require(runtime_check(runtime)["completed_case_ids"] == list(READY_CASES), "Synthetic complete evidence rejected"))
    for case, mutate in (
        ("raw-changed", lambda v: v["rpcs"][2]["result"].update(Raw="{}")),
        ("stage", lambda v: v.update(stage="other")),
        ("schema-bool", lambda v: v.update(schema_version=True)),
        ("expired", lambda v: v.update(elapsed_ms=180000)),
        ("engine", lambda v: v.update(engine_sha256="0" * 64)),
        ("arguments", lambda v: v["arguments"].append("-wbsilent")),
        ("cleanup", lambda v: v.update(cleanup="owned_process_exit_not_confirmed")),
        ("evidence-errors", lambda v: v.update(evidence_errors=[{"message": "cleanup failed"}])),
        ("loaded-missing", lambda v: v.update(loaded_projects=None)),
        ("rpc-missing", lambda v: v.update(rpcs=[])),
        ("token", lambda v: v.update(token="b" * 64)),
        ("codec", lambda v: v["rpcs"][2].update(codec={})),
        ("null-health-unknown", lambda v: v["rpcs"][0].update(result=None, failure="timeout", failure_kind="unknown")),
        ("spawn-rpc", lambda v: v["rpcs"][2].update(function="BerylComponentCallbacks", action="spawn")),
        ("ownership-missing", lambda v: v["session_checks"].pop()),
        ("duplicate-loaded", lambda v: v["rpcs"].insert(2, copy.deepcopy(v["rpcs"][1]))),
        ("time-order", lambda v: v["rpcs"][1].update(elapsed_ms=0)),
        ("log-hash", lambda v: v["raw_logs"][0].update(sha256="0" * 64)),
        ("logs-missing", lambda v: v.update(raw_logs=[])),
        ("health-not-ready", lambda v: v["rpcs"][0].update(result=reply("IsWorkbenchRunning", {"IsRunning": False, "ScriptsCompiled": True}))),
        ("port-missing", lambda v: v.update(port_checks=[])),
        ("port-foreign", lambda v: v["port_checks"][0].update(owning_process=999)),
        ("health-duplicate", lambda v: v["rpcs"].insert(1, copy.deepcopy(v["rpcs"][0]))),
        ("pending-foreign", lambda v: v["rpcs"][2].update(result=reply(FUNCTION, {**numeric, "status": "pending", "world_absolute_path": "foreign"}),
             normalized_response=normalize({**numeric, "status": "pending", "world_absolute_path": "foreign"})[0])),
        ("adapter", lambda v: v.update(adapter_sha256="0" * 64)),
        ("manifest-path", lambda v: v["input_manifest"].update(path=str(work / "foreign.json"))),
        ("manifest-hash", lambda v: v["input_manifest"].update(sha256="0" * 64)),
        ("manifest-fields", lambda v: v["staged_inputs"].update(shell="arbitrary")),
        ("manifest-files", lambda v: v["staged_inputs"]["files"].update({HANDLER_PATH: "0" * 64})),
        ("output-unaccounted", lambda v: v.update(engine_outputs=[{"path": str(addon / "other.rdb"), "relative": "other.rdb", "sha256": "0" * 64, "bytes": 1}])),
        ("callback-scope", lambda v: v.update(callback_execution="executed_success")),
        ("play-scope", lambda v: v.update(play="executed_success")),
        ("spawn-scope", lambda v: v.update(spawn="executed_success")),
        ("save-scope", lambda v: v.update(save="executed_success")),
        ("policy-scope", lambda v: v.update(policy_changes="executed_success")),
        ("limit-change", lambda v: v["limits"].update(rpc_ms=9000)),
        ("rpc-duration", lambda v: v["rpcs"][2].update(duration_ms=8000)),
        ("rpc-late-duration", lambda v: v["rpcs"][2].update(duration_ms=7)),
    ):
        mutant = copy.deepcopy(runtime)
        mutate(mutant)
        rejected("envelope." + case, lambda v=mutant: runtime_check(v))
    database = addon / "resourceDatabase.rdb"
    write(database, b"inert derived database\n")
    derived_runtime = copy.deepcopy(runtime)
    derived_runtime["engine_outputs"] = [{"path": str(database), "relative": database.name,
                                         "sha256": identity(database)["sha256"], "bytes": database.stat().st_size}]
    passed("envelope.derived-valid", lambda: runtime_check(derived_runtime))
    for case, key, val in (("derived-hash", "sha256", "0" * 64), ("derived-size", "bytes", 8 * 1024 * 1024 + 1),
                           ("derived-boolean-size", "bytes", True), ("derived-relative", "relative", "other.rdb")):
        mutant = copy.deepcopy(derived_runtime)
        mutant["engine_outputs"][0][key] = val
        rejected("envelope." + case, lambda v=mutant: runtime_check(v))
    write(addon / "unaccounted.c", b"unaccounted\n")
    rejected("envelope.extra-staged-file", lambda: runtime_check(derived_runtime))
    (addon / "unaccounted.c").unlink()
    for case, mutate in (("handler-action", lambda v: v["rpcs"][2].update(action="spawn")),
                         ("builtin-action", lambda v: v["rpcs"][0].pop("action")),
                         ("health-receipt", lambda v: v.update(health=None))):
        mutant = copy.deepcopy(derived_runtime)
        mutate(mutant)
        rejected("envelope." + case, lambda v=mutant: runtime_check(v))
    passed("profile.render", lambda: require(render(b"@MECHANISM@", "a" * 64, world, "netapi-resource") == b"native_netapi", "Installed native profile render differs"))
    rejected("profile.unknown", lambda: render(b"@MECHANISM@", "a" * 64, world, "arbitrary"))
    native_runtime = copy.deepcopy(derived_runtime)
    native_runtime.update(opening_mechanism="netapi-resource", mechanism="native_netapi", scope=OPENING_SCOPES["netapi-resource"], elapsed_ms=20)
    native_runtime["arguments"] = native_runtime["arguments"][:4]
    native_wire = {**numeric, "mechanism": "native_netapi"}
    prelim_wire = {**native_wire, "status": "pending", "module_present": 0, "api_present": 0,
                   "world_path": "", "world_absolute_path": "", "world_path_resolved": 0, "world_matches": 0, "edit_mode": 0, "world_present": 0}
    preliminary = copy.deepcopy(calls[2])
    preliminary.update(result=reply(FUNCTION, prelim_wire), normalized_response=normalize(prelim_wire)[0], codec=normalize(prelim_wire)[1])
    opening_call = {"function": "OpenResource", "action": None, "params": {"ResourceName": str(addon / REL_WORLD)},
                    "elapsed_ms": 4, "timeout_ms": 8000, "duration_ms": 0, "result": reply("OpenResource", {"Opened": 1}),
                    "normalized_response": {"Opened": True}, "codec": {"schema_version": 1, "name": "enfusion.jsonapistruct.bool01.v1", "numeric_boolean_fields": ["Opened"]}}
    final_call = copy.deepcopy(calls[2])
    final_call.update(elapsed_ms=5, result=reply(FUNCTION, native_wire), normalized_response=normalize(native_wire)[0], codec=normalize(native_wire)[1])
    native_runtime.update(rpcs=[copy.deepcopy(calls[0]), copy.deepcopy(calls[1]), preliminary, opening_call, final_call],
                          preliminary=preliminary["normalized_response"], native_open=opening_call["result"], completion=final_call["normalized_response"])
    native_sites = ["startup.identity", "port.check"] + [site for call in native_runtime["rpcs"] for site in ("before." + call["function"], "after." + call["function"])]
    native_runtime["session_checks"] = [{"site": name, "process_id": 123, "start_ticks": 456, "executable": str(engine), "elapsed_ms": i}
                                       for i, name in enumerate(native_sites)]
    def native_check(v):
        return validate_runtime(v, "a" * 64, addon, engine, binding, runtime_tools, startup_manifest_path, startup_manifest, adapter_hash, "netapi-resource")
    passed("profile.native-valid", lambda: native_check(native_runtime))
    for case, mutate in (
        ("open-missing", lambda v: v["rpcs"].pop(3)),
        ("open-duplicate", lambda v: v["rpcs"].insert(4, copy.deepcopy(v["rpcs"][3]))),
        ("open-order", lambda v: v["rpcs"].__setitem__(slice(2, 4), list(reversed(v["rpcs"][2:4])))),
        ("open-param", lambda v: v["rpcs"][3]["params"].update(ResourceName="foreign")),
        ("opened-false", lambda v: v["rpcs"][3].update(result=reply("OpenResource", {"Opened": 0}), normalized_response={"Opened": False})),
        ("opened-string", lambda v: v["rpcs"][3].update(result=reply("OpenResource", {"Opened": "1"}))),
        ("opened-float", lambda v: v["rpcs"][3].update(result=reply("OpenResource", {"Opened": 1.0}))),
        ("opened-extra", lambda v: v["rpcs"][3].update(result=reply("OpenResource", {"Opened": 1, "Unknown": True}))),
        ("open-codec", lambda v: v["rpcs"][3].update(codec={})),
        ("open-raw", lambda v: v["rpcs"][3]["result"].update(Raw="{}")),
        ("open-link", lambda v: v.update(native_open=None)),
        ("preliminary-link", lambda v: v.update(preliminary=None)),
        ("preliminary-identity", lambda v: v["rpcs"][2].update(result=reply(FUNCTION, {**prelim_wire, "addon_world_resolved": 0}),
             normalized_response=normalize({**prelim_wire, "addon_world_resolved": 0})[0])),
        ("mechanism", lambda v: v.update(mechanism="startup_cli")),
        ("arguments", lambda v: v["arguments"].extend(["-wbmodule=WorldEditor", "-run"])),
    ):
        mutant = copy.deepcopy(native_runtime)
        mutate(mutant)
        rejected("profile." + case, lambda v=mutant: native_check(v))
    for case, mutate in (("default-no-opener", lambda v: v.update(native_open=opening_call["result"])),
                         ("default-params", lambda v: v["rpcs"][0].update(params={"Force": True})),
                         ("handler-params", lambda v: v["rpcs"][2]["params"].update(action="play"))):
        mutant = copy.deepcopy(derived_runtime)
        mutate(mutant)
        rejected("profile." + case, lambda v=mutant: runtime_check(v))
    bool_open = copy.deepcopy(native_runtime)
    bool_reply = reply("OpenResource", {"Opened": True})
    bool_open["rpcs"][3].update(result=bool_reply, codec={"schema_version": 1, "name": "enfusion.jsonapistruct.bool01.v1", "numeric_boolean_fields": []})
    bool_open["native_open"] = bool_reply
    passed("profile.opened-bool-valid", lambda: native_check(bool_open))
    for case, mutate in (("open-normalized-int", lambda v: v["rpcs"][3].update(normalized_response={"Opened": 1})),
                         ("observer-normalized-int", lambda v: v["rpcs"][4]["normalized_response"].update(world_matches=1)),
                         ("codec-boolean-version", lambda v: v["rpcs"][3]["codec"].update(schema_version=True))):
        mutant = copy.deepcopy(native_runtime)
        mutate(mutant)
        rejected("profile." + case, lambda v=mutant: native_check(v))
    passed("third.render", lambda: require(render(b"@MECHANISM@", "a" * 64, world, "module-netapi-resource") == b"module_native_netapi", "Installed module/native profile render differs"))
    third_runtime = copy.deepcopy(native_runtime)
    third_runtime.update(opening_mechanism="module-netapi-resource", mechanism="module_native_netapi", scope=OPENING_SCOPES["module-netapi-resource"])
    third_runtime["arguments"] += ["-wbmodule=WorldEditor", "-run"]
    for call in third_runtime["rpcs"]:
        if call["function"] == FUNCTION:
            response = {**call["result"]["Response"], "mechanism": "module_native_netapi"}
            call.update(result=reply(FUNCTION, response), normalized_response=normalize(response)[0], codec=normalize(response)[1])
    third_runtime.update(preliminary=third_runtime["rpcs"][2]["normalized_response"], completion=third_runtime["rpcs"][-1]["normalized_response"])
    def third_check(v):
        return validate_runtime(v, "a" * 64, addon, engine, binding, runtime_tools, startup_manifest_path, startup_manifest, adapter_hash, "module-netapi-resource")
    passed("third.valid", lambda: third_check(third_runtime))
    for case, mutate in (
        ("load-forbidden", lambda v: v["arguments"].extend(["-load", REL_WORLD])),
        ("module-missing", lambda v: v["arguments"].pop(4)),
        ("run-missing", lambda v: v["arguments"].pop(5)),
        ("vector-order", lambda v: v["arguments"].__setitem__(slice(4, 6), ["-run", "-wbmodule=WorldEditor"])),
        ("native-wire", lambda v: v.update(mechanism="native_netapi")),
        ("native-profile", lambda v: v.update(opening_mechanism="netapi-resource")),
        ("startup-profile", lambda v: v.update(opening_mechanism="startup-cli")),
        ("scope", lambda v: v.update(scope=OPENING_SCOPES["startup-cli"])),
        ("no-opener", lambda v: v["rpcs"].pop(3)),
    ):
        mutant = copy.deepcopy(third_runtime)
        mutate(mutant)
        rejected("third." + case, lambda v=mutant: third_check(v))
    rejected("third.as-native", lambda: native_check(third_runtime))
    rejected("third.native-as-third", lambda: third_check(native_runtime))
    passed("registered.render", lambda: require(render(b"@MECHANISM@", "a" * 64, world, "module-netapi-registered") == b"module_registered_netapi", "Installed registered-name profile render differs"))
    registered_runtime = copy.deepcopy(third_runtime)
    registered_runtime.update(opening_mechanism="module-netapi-registered", mechanism="module_registered_netapi",
                              scope=OPENING_SCOPES["module-netapi-registered"])
    registered_runtime["rpcs"][3]["params"] = {"ResourceName": RESOURCE}
    for call in registered_runtime["rpcs"]:
        if call["function"] == FUNCTION:
            response = {**call["result"]["Response"], "mechanism": "module_registered_netapi"}
            call.update(result=reply(FUNCTION, response), normalized_response=normalize(response)[0], codec=normalize(response)[1])
    registered_runtime.update(preliminary=registered_runtime["rpcs"][2]["normalized_response"], completion=registered_runtime["rpcs"][-1]["normalized_response"])
    def registered_check(v):
        return validate_runtime(v, "a" * 64, addon, engine, binding, runtime_tools, startup_manifest_path, startup_manifest, adapter_hash, "module-netapi-registered")
    passed("registered.valid", lambda: registered_check(registered_runtime))
    for case, mutate in (
        ("absolute-forbidden", lambda v: v["rpcs"][3]["params"].update(ResourceName=str(addon / REL_WORLD))),
        ("relative-forbidden", lambda v: v["rpcs"][3]["params"].update(ResourceName=REL_WORLD)),
        ("foreign-guid", lambda v: v["rpcs"][3]["params"].update(ResourceName="{AAAAAAAAAAAAAAAA}" + REL_WORLD)),
        ("extra-param", lambda v: v["rpcs"][3]["params"].update(ModuleName="WorldEditor")),
        ("third-wire", lambda v: v.update(mechanism="module_native_netapi")),
        ("third-profile", lambda v: v.update(opening_mechanism="module-netapi-resource")),
        ("load-forbidden", lambda v: v["arguments"].extend(["-load", REL_WORLD])),
        ("no-module", lambda v: v["arguments"].pop(4)),
        ("preliminary-missing", lambda v: v.update(preliminary=None)),
        ("preliminary-guid", lambda v: v["rpcs"][2].update(result=reply(FUNCTION, {**prelim_wire, "mechanism": "module_registered_netapi", "resource_name": "{AAAAAAAAAAAAAAAA}" + REL_WORLD}),
             normalized_response=normalize({**prelim_wire, "mechanism": "module_registered_netapi", "resource_name": "{AAAAAAAAAAAAAAAA}" + REL_WORLD})[0])),
    ):
        mutant = copy.deepcopy(registered_runtime)
        mutate(mutant)
        rejected("registered." + case, lambda v=mutant: registered_check(v))
    rejected("registered.as-absolute", lambda: third_check(registered_runtime))
    rejected("registered.absolute-as-registered", lambda: registered_check(third_runtime))
    require(tuple(case["id"] for case in cases) == SELF_CASES and len({case["id"] for case in cases}) == len(SELF_CASES), "Inert cases are missing/duplicated/reordered")
    require(Path(__file__).read_bytes() == own_bytes, "Verifier changed during inert tests", "stale_input")
    require(all(identity(Path(name)) == item for name, item in test_inputs.items()) and
            all(identity(Path(item["retained"]))["sha256"] == item["sha256"] for item in retained_inputs),
            "Inert test input or retained bytes changed", "stale_input")
    write(work / "verify-workbench-startup.py.input", own_bytes)
    result = {"schema_version": 1, "operation": "workbench.startup.inert_self_test", "status": "success",
              "expected_case_ids": list(SELF_CASES), "completed_case_ids": [case["id"] for case in cases],
              "complete_expected_case_set": True, "case_count": len(cases), "cases": cases,
              "verifier": {"path": str(Path(__file__).resolve()), "bytes": len(own_bytes), "sha256": mod.digest(own_bytes)},
              "verification_inputs": test_inputs, "retained_inputs": retained_inputs,
              "scope": "inert source trees, wire normalization and deliberately malformed readiness/compile receipts only",
              "compiler_execution": "not_run", "powershell_execution": "not_run", "engine_execution": "not_run", "callback_delivery": "not_run"}
    saved(work / "result.json", result)
    print(str(work / "result.json"))


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (mod.Failure, OSError, ValueError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1)
