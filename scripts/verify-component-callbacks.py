#!/usr/bin/env python3
"""Prepare or execute an isolated engine-delivered component callback probe.

Requires an explicitly identified private compiler. --prepare-only runs source
checks/generation but no native program or engine. Engine stages use the selected
PowerShell host and existing trusted transports, with no policy flags. No source
installation, promotion, generated-file correction or live MESH edit occurs.
"""
from pathlib import Path
import argparse
import contextlib
import copy
import importlib.util
import hashlib
import json
import os
import re
import shutil
import struct
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "packages/sparkos/component-callback-probe"
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / "tools/beryl-mod"))
import mod
import scenarios

CASE_IDS = (
    "runtime.post-init.1", "runtime.post-init.2", "runtime.frames.1", "runtime.frames.2",
    "runtime.independent-state", "runtime.delete.1", "runtime.delete.2",
)
FUNCTION = "BerylComponentCallbacks"
TRANSPORT = ROOT / "scripts/component-callback-engine.ps1"
WORLD_FIXTURES = ("legacy", "source-layered-v1")
ENGINE_UPDATES = ("focus-dependent", "force-update")
FRAME_DIAGNOSTICS = ("off", "world-state-v1")
FRAME_FUNCTION = "BerylComponentFrameState"
FRAME_SOURCE = "scripts/WorkbenchGameCommon/BerylComponentFrameState.c"
FRAME_CONTRACT_SHA = "562f7387520f70a0fa009d35fdda63a88ea058f6cda817e7995a96339e7f9e57"
FRAME_BOOLS = ("api_present", "game_present", "owner1_present", "owner2_present", "owner1_component_present",
               "owner2_component_present", "api_is_game", "owner1_is_api", "owner1_is_game", "owner2_is_api",
               "owner2_is_game", "owner1_active", "owner2_active", "owner1_frame_registered", "owner2_frame_registered")
FRAME_INTS = ("phase", "api_frame", "game_frame", "owner1_frame", "owner2_frame", "owner1_flags", "owner2_flags", "owner1_mask", "owner2_mask")
FRAME_FIELDS = {"token", "profile", "status", "failure", *FRAME_BOOLS, *FRAME_INTS}
UPDATE_DOCUMENT = Path("C:/Program Files (x86)/Steam/steamapps/common/Arma Reforger Tools/Workbench/docs/EnfusionScriptAPI/html/Page_CLI.html")
UPDATE_DOCUMENT_SHA = "b1fd25c1d02e3ac687bb310496f700acaf451f66d26c572afa9ac5fd343822d1"
LAYERED_DRIVER = ROOT / "scripts/verify-layered-world.py"
REL_WORLD = "worlds/BerylCallbackProbe.ent"
REL_LAYER = "worlds/BerylCallbackProbe_Layers/default.layer"
IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
HASH = re.compile(r"[0-9a-f]{64}")
COMPILE_TOOLS = ("Find-Workbench.ps1", "Invoke-ReforgerBuild.ps1", "Invoke-Workbench.ps1", "Get-WorkbenchErrors.ps1")
FAILURE_STATUSES = {"failure", "unavailable", "timeout", "cancelled", "stale_input"}
EXPECTED_WORLD_RESOURCE = "{BCCBA11B20261008}worlds/BerylCallbackProbe.ent"
WIRE_BOOLS = ("addon_world_resolved", "world_path_resolved", "world_matches", "edit_mode", "game_mode", "in_play_mode", "world_present",
              "resource_name_resolved", "module_present", "api_present", "module_open_requested", "module_open_accepted", "load_accepted")
LOAD_COUNTERS = ("load_requested", "load_submitted", "load_entered", "load_resumed", "load_returned")
WIRE_FIELDS = {"token", "action", "status", "failure", "world_path", "current_project", "addon_world_path",
               "world_absolute_path", "resource_name", "resource_path", "resource_absolute_path", *WIRE_BOOLS, *LOAD_COUNTERS, "phase", "executed", "checks", "failures", "event_count",
               "checksum", "caseIds", "rows"}


def require(condition, message, status="failure", pointer=None):
    if not condition:
        raise mod.Failure(message, status, pointer)


def frame_diagnostic_basis(profile):
    require(type(profile) is str and profile in FRAME_DIAGNOSTICS, "Unknown frame diagnostic profile")
    if profile == "off":
        return None, []
    contract_bytes = mod.read(PACKAGE / "frame-state-contracts.json")
    require(mod.digest(contract_bytes) == FRAME_CONTRACT_SHA, "Frame diagnostic fixed source contract changed", "stale_input")
    contract = mod.parse(contract_bytes)
    require(type(contract) is dict and type(contract.get("schema_version")) is int and contract["schema_version"] == 1 and
            contract.get("profile") == profile and type(contract.get("documents")) is list and len(contract["documents"]) == 5,
            "Malformed frame diagnostic source contract")
    docroot = UPDATE_DOCUMENT.parent
    inputs = []
    for row in contract["documents"]:
        require(type(row) is dict and set(row) == {"file", "sha256", "line", "signature"} and
                type(row["file"]) is str and re.fullmatch(r"interface[A-Za-z]+\.html", row["file"]) and
                type(row["sha256"]) is str and HASH.fullmatch(row["sha256"]) and type(row["line"]) is int and row["line"] > 0,
                "Malformed frame diagnostic declaration")
        path = docroot / row["file"]
        require(path.is_file() and not path.is_symlink(), "Frame diagnostic declaration unavailable", "unavailable")
        require(mod.digest(mod.read(path)) == row["sha256"], "Frame diagnostic declaration changed", "stale_input")
        inputs.append(("frame-primary/" + row["file"], path))
    return contract, inputs


def normalize_frame_state(raw, token):
    require(type(raw) is dict and set(raw) == FRAME_FIELDS, "Frame diagnostic response fields differ")
    require(all(type(raw[name]) is str and len(raw[name]) <= (64 if name == "token" else 2048)
                for name in ("token", "profile", "status", "failure")), "Invalid frame diagnostic strings")
    require(raw["token"] == token and raw["profile"] == "world-state-v1", "Frame diagnostic identity differs", "stale_input")
    require(raw["status"] in ("observed", "unavailable", "failure"), "Invalid frame diagnostic status")
    result, numeric = dict(raw), []
    for name in FRAME_BOOLS:
        value = raw[name]
        require(type(value) is bool or type(value) is int and value in (0, 1), "Invalid frame diagnostic boolean: " + name)
        if type(value) is int:
            result[name] = bool(value)
            numeric.append(name)
    require(all(type(raw[name]) is int and -(2**31) <= raw[name] < 2**31 for name in FRAME_INTS),
            "Invalid frame diagnostic integer")
    require(0 <= raw["phase"] <= 4, "Invalid diagnostic phase")
    if raw["status"] == "observed":
        require(raw["phase"] in (2, 3) and raw["failure"] == "" and all(result[name] for name in FRAME_BOOLS[:6]),
                "Observed frame diagnostic lacks admitted live references")
        require(not result["api_is_game"] or (result["owner1_is_api"] == result["owner1_is_game"] and
                result["owner2_is_api"] == result["owner2_is_game"]), "Contradictory diagnostic world identity")
        require(result["api_is_game"] or not (result["owner1_is_api"] and result["owner1_is_game"]) and
                not (result["owner2_is_api"] and result["owner2_is_game"]), "Contradictory owner/world identity")
    else:
        require(bool(raw["failure"]), "Unavailable/failed diagnostic lacks explanation")
    return result, {"schema_version": 1, "name": "enfusion.jsonapistruct.bool01.v1", "numeric_boolean_fields": numeric}


def validate_frame_diagnostics(runtime, profile, token, session):
    require(type(runtime) is dict and type(profile) is str and profile in FRAME_DIAGNOSTICS and
            runtime.get("frame_diagnostics") == profile, "Diagnostic profile differs", "stale_input")
    calls = runtime.get("frame_state_rpcs")
    require(type(calls) is list and len(calls) <= 2, "Invalid bounded diagnostic RPC list")
    if profile == "off":
        require(not calls, "Disabled diagnostics performed RPCs")
        return {"status": "not_run", "observations": []}
    require(type(session) is dict and type(session.get("process_id")) is int and session["process_id"] > 0 and
            type(session.get("start_ticks")) is int and session["start_ticks"] > 0 and type(session.get("executable")) is str,
            "Diagnostic owned session identity missing")
    elapsed = runtime.get("elapsed_ms")
    require(type(elapsed) is int and 0 <= elapsed < 180000, "Diagnostic enclosing receipt timing invalid")
    observations, errors, previous, last_after = [], [], -1, -1
    for call in calls:
        require(type(call) is dict and set(call) == {"function", "params", "stage", "phase", "elapsed_ms", "timeout_ms", "result", "failure", "identity_checks"},
                "Invalid diagnostic entry fields")
        require(call["function"] == FRAME_FUNCTION and call["params"] == {"token": token} and call["stage"] == "spawn" and
                type(call["phase"]) is int and call["phase"] in (2, 3), "Diagnostic invocation scope differs")
        require(type(call["elapsed_ms"]) is int and previous <= call["elapsed_ms"] <= elapsed and call["elapsed_ms"] >= 0 and
                type(call["timeout_ms"]) is int and 0 < call["timeout_ms"] <= min(8000, 180000-call["elapsed_ms"]),
                "Invalid diagnostic timing bounds")
        previous = call["elapsed_ms"]
        checks = call["identity_checks"]
        require(type(checks) is list and len(checks) in (1, 2), "Missing diagnostic identity checks")
        require([row.get("site") for row in checks if type(row) is dict] == ["before", "after"][:len(checks)],
                "Diagnostic identity check order differs")
        last = -1
        for row in checks:
            require(type(row) is dict and set(row) == {"site", "process_id", "start_ticks", "executable", "elapsed_ms"} and
                    type(row["process_id"]) is int and row["process_id"] == session["process_id"] and
                    type(row["start_ticks"]) is int and row["start_ticks"] == session["start_ticks"] and
                    type(row["executable"]) is str and row["executable"].replace("\\", "/").casefold() == session["executable"].replace("\\", "/").casefold() and
                    type(row["elapsed_ms"]) is int and 0 <= row["elapsed_ms"] <= elapsed and last <= row["elapsed_ms"],
                    "Diagnostic process identity/timing differs", "stale_input")
            last = row["elapsed_ms"]
        require(last_after <= checks[0]["elapsed_ms"] <= call["elapsed_ms"] and
                (len(checks) == 1 or checks[1]["elapsed_ms"] >= call["elapsed_ms"]), "Diagnostic invocation identity timing differs")
        last_after = checks[-1]["elapsed_ms"]
        if call["failure"] is not None:
            require(type(call["failure"]) is str and bool(call["failure"]) and len(call["failure"]) <= 4096,
                    "Invalid diagnostic failure")
            errors.append(call["failure"])
            continue
        reply = call["result"]
        require(len(checks) == 2 and type(reply) is dict and reply.get("Ok") is True and reply.get("Function") == FRAME_FUNCTION and
                type(reply.get("Raw")) is str and len(reply["Raw"]) <= 1024*1024,
                "Missing exact raw diagnostic reply")
        require(checks[1]["elapsed_ms"] - call["elapsed_ms"] <= call["timeout_ms"],
                "Frame observation exceeded its bounded RPC budget", "timeout")
        try:
            matches = mod.canonical(mod.parse(reply["Raw"].encode())) == mod.canonical(reply.get("Response"))
        except (ValueError, TypeError, UnicodeError, mod.Failure) as exc:
            raise mod.Failure("Malformed retained diagnostic JSON response") from exc
        require(matches, "Parsed frame diagnostic differs from retained raw response")
        response, codec = normalize_frame_state(reply["Response"], token)
        require(response["phase"] in (2, 3) or response["status"] != "observed", "Diagnostic observed after live phase")
        observations.append({"elapsed_ms": call["elapsed_ms"], "response": response, "codec": codec})
    return {"status": "observed" if any(item["response"]["status"] == "observed" for item in observations) else "unavailable",
            "observations": observations, "errors": errors,
            "scope": "read-only live-spawn observations; no callback success or performance claim"}


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    require(path.write_bytes(data) == len(data) and mod.read(path) == data,
            "Incomplete verifier fixture/evidence write: " + str(path))


def identity(path):
    return {"path": str(path), "bytes": path.stat().st_size, "sha256": mod.digest(mod.read(path))}


def streamed_identity(path):
    fingerprint = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            fingerprint.update(chunk)
    return {"path": str(path), "bytes": path.stat().st_size, "sha256": fingerprint.hexdigest()}


def save_result(path, value):
    mod.write_json(path, value)
    require(mod.parse(mod.read(path)) == value, "Written evidence does not match the complete result")


def failed_adapter(error, result):
    status = result.get("status", error.status) if type(result) is dict else error.status
    if status not in {"failure", "unavailable", "timeout", "cancelled", "stale_input"}:
        status = error.status
    return mod.Failure(str(error), status, error.pointer)


def compile_evidence_success(compiled, plugin_files, binding):
    if type(compiled) is not dict or type(compiled.get("result")) is not dict or type(plugin_files) is not dict or type(binding) is not dict:
        return False
    detail = compiled["result"]
    return (type(compiled.get("schema_version")) is int and compiled["schema_version"] == 1 and
            compiled.get("stage") == "workbench_compile" and compiled.get("status") == "success" and
            detail.get("Stage") == "Compiled" and detail.get("Ok") is True and
            type(detail.get("ExitCode")) is int and detail["ExitCode"] == 0 and
            type(detail.get("ErrorCount")) is int and detail["ErrorCount"] == 0 and
            all(name in plugin_files for name in COMPILE_TOOLS) and
            compiled.get("tools") == {name:plugin_files[name] for name in COMPILE_TOOLS} and
            type(binding.get("sha256")) is str and type(binding.get("version")) is str and
            compiled.get("engine_sha256") == binding["sha256"] and compiled.get("engine_version") == binding["version"])


def classify_attempts(record):
    """Separate launched adapters, target observations and verified outcomes."""
    for name, label in (("source_generation", "component_source_build"),
                        ("engine_compilation", "component_engine_compile"),
                        ("engine_runtime", "component_runtime_callbacks")):
        attempt = record["attempts"][name]
        matching = [log for log in record.get("commands", []) if type(log.get("stdout")) is str and
                    Path(log["stdout"]).name.endswith("-" + label + ".stdout.log")]
        if matching:
            attempt["process_outcome"] = matching[-1].get("status", "incomplete")
    compiled = record["raw_results"].get("compile", {}).get("result")
    compilation = record["attempts"]["engine_compilation"]
    if type(compiled) is dict:
        compilation["adapter_status"] = compiled.get("status", "incomplete")
        detail = compiled.get("result")
        if type(detail) is dict and detail.get("Stage") == "Compiled":
            if compile_evidence_success(compiled, record.get("plugin_file_set"), record.get("expected_compile_binding")):
                outcome = "executed_success"
            elif detail.get("Ok") is False or (type(detail.get("ExitCode")) is int and detail["ExitCode"] != 0) or (
                    type(detail.get("ErrorCount")) is int and detail["ErrorCount"] != 0):
                outcome = "executed_failure"
            else:
                outcome = "executed_unverified"
            compilation["target_compile"] = outcome
            record["scope"]["engine_compilation"] = outcome
        elif type(detail) is dict and detail.get("Stage") == "DidNotStart":
            compilation["target_compile"] = "startup_unavailable"
            record["scope"]["engine_compilation"] = "not_started"
        elif type(detail) is dict and detail.get("Stage") == "Timeout":
            compilation["target_compile"] = "timeout_incomplete"
            record["scope"]["engine_compilation"] = "attempted_incomplete"
    runtime = record["raw_results"].get("runtime", {}).get("result")
    execution = record["attempts"]["engine_runtime"]
    if type(runtime) is dict:
        execution["adapter_status"] = runtime.get("status", "incomplete")
        execution["owned_session_recorded"] = type(runtime.get("session")) is dict
        calls = runtime.get("rpcs")
        if type(calls) is list:
            execution["spawn_rpc_attempted"] = any(type(call) is dict and call.get("action") == "spawn" for call in calls)
            # A transport failure before spawn did not attempt callback delivery.
            if execution["spawn_rpc_attempted"] and record["scope"]["engine_callback_delivery"] != "executed_success":
                record["scope"]["engine_callback_delivery"] = "attempted_unconfirmed"
                record["scope"]["engine_runtime_callbacks"] = "attempted_unconfirmed"
            observations = []
            for call in calls:
                response = call.get("result", {}).get("Response") if type(call) is dict and type(call.get("result")) is dict else None
                if type(response) is dict and response.get("token") == record.get("token") and type(response.get("rows")) is list:
                    observations.extend(row for row in response["rows"] if type(row) is str and row.startswith("event|"))
            if observations:
                execution["callback_observations"] = "present_unverified"
    if record.get("callback_comparison", {}).get("status") == "verified":
        execution["callback_observations"] = "verified_complete"


def load_helper(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


bounded = load_helper("callback_bounded_tree", ROOT / "scripts/verify-component-engine.py")


def files(root):
    return bounded.tree_files(root)[0]


def directories(root):
    return sorted(bounded.tree_files(root)[1])


def parent_directories(names):
    return sorted({parent.as_posix() for name in names for parent in Path(name).parents if parent != Path(".")})


def capture_adapter(record, label, path):
    """Keep capture failures separate from an already active process failure."""
    try:
        if path.is_file():
            item = identity(path)
            record["raw_results"][label] = item
            item["result"] = mod.parse(mod.read(path))
    except BaseException as exc:
        record.setdefault("evidence_errors", []).append({"stage": label, "type": type(exc).__name__, "message": str(exc)})


def retain_engine_logs(work, result):
    detail = result.get("result") if type(result) is dict else None
    if type(detail) is not dict or not detail.get("LogDir"):
        return []
    root = Path(detail["LogDir"])
    require(root.is_dir() and not root.is_symlink(), "Raw engine log directory unavailable", "unavailable")
    paths = sorted(root.glob("*.log"))
    require(len(paths) <= 256, "Raw engine log count exceeds fixture bound", "unavailable")
    retained = []
    for index, path in enumerate(paths):
        require(path.is_file() and not path.is_symlink() and path.stat().st_size <= 64 * 1024 * 1024,
                "Raw engine log exceeds fixture bound or is linked", "unavailable")
        before = streamed_identity(path)
        target = work / "logs" / (str(index).zfill(4) + "-" + path.name)
        target.parent.mkdir(exist_ok=True)
        with path.open("rb") as source, target.open("xb") as output:
            shutil.copyfileobj(source, output, 1024 * 1024)
        copied = streamed_identity(target)
        require(streamed_identity(path) == before and copied["sha256"] == before["sha256"] and
                copied["bytes"] == before["bytes"], "Raw engine log changed during capture", "stale_input")
        retained.append({"original": str(path), "retained": str(target), "bytes": copied["bytes"], "sha256": copied["sha256"]})
    return retained


@contextlib.contextmanager
def source_tool_environment():
    values = {"BERYL_PYTHON": sys.executable, "BERYL_MOD_TOOL": str(mod.HERE / "mod.py")}
    prior = {name: os.environ.get(name) for name in values}
    os.environ.update(values)
    try:
        yield
    finally:
        for name, value in prior.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def basis():
    value = mod.parse(mod.read(PACKAGE / "source-contracts.json"))
    require(type(value) is dict and set(value) == {"schema_version", "scope", "inputs"} and
            type(value["schema_version"]) is int and value["schema_version"] == 1 and
            type(value["inputs"]) is list and len(value["inputs"]) == 21,
            "Exact installed source-contract inventory is required")
    paths, seen = [], set()
    for index, item in enumerate(value["inputs"]):
        require(type(item) is dict and set(item) == {"path", "sha256", "bytes"} and
                type(item["path"]) is str and item["path"] not in seen and
                type(item["bytes"]) is int and 0 < item["bytes"] <= 16 * 1024 * 1024 and
                type(item["sha256"]) is str and HASH.fullmatch(item["sha256"]), "Invalid source-contract identity")
        path = Path(item["path"])
        require(path.is_absolute() and path.is_file() and not path.is_symlink(), "Missing contract source", "unavailable")
        require(identity(path) == item, "Installed declaration/resource seed changed", "stale_input")
        seen.add(item["path"])
        paths.append(("contract/" + str(index).zfill(2) + "-" + path.name, path))
    return value, paths


def world_fixture_sources(profile="legacy", layered=None):
    require(type(profile) is str and profile in WORLD_FIXTURES,
            "Unknown installed callback world fixture", "stale_input")
    result = {name: mod.read(PACKAGE / name) for name in (
        REL_WORLD, REL_WORLD + ".meta", "Prefabs/BerylCallbackProbe.et", "Prefabs/BerylCallbackProbe.et.meta")}
    if profile == "source-layered-v1":
        require(layered is not None and layered.FORMAT == profile,
                "Selected layered source contract is unavailable", "stale_input")
        world = mod.read(layered.PACKAGE / REL_WORLD)
        layer = mod.read(layered.PACKAGE / REL_LAYER)
        require(world == layered.WORLD_BYTES and layer == layered.LAYER_BYTES,
                "Fixed callback layered templates changed", "stale_input")
        result.update({REL_WORLD: world, REL_LAYER: layer})
    return result


def world_fixture_basis(profile):
    require(type(profile) is str and profile in WORLD_FIXTURES,
            "Unknown installed callback world fixture", "stale_input")
    if profile == "legacy":
        return None, None, None, []
    layered = load_helper("callback_layered_source_contract", LAYERED_DRIVER)
    primary, guard, contract = layered.primary_inputs()
    package = files(layered.PACKAGE)
    require(set(package) == {REL_WORLD, REL_LAYER, "source-contracts.json", "README.md"},
            "Layered source package differs from its exact four-file profile", "stale_input")
    proof = {"fixture_format": profile, "source_contract_sha256": layered.CONTRACT_SHA,
             "source_package": package, "source_contract": contract,
             "engine_authored_serialization": "not_run"}
    inputs = [("layered/verifier/verify-layered-world.py", LAYERED_DRIVER),
              ("layered/verifier/verify-workbench-startup.py", layered.BASE_PATH)]
    inputs += [("layered/package/" + name, layered.PACKAGE / name) for name in package]
    inputs += [("layered/primary/" + str(index).zfill(2) + "-" + path.name, path) for index, path in enumerate(primary)]
    return layered, proof, guard, inputs


def fixture_token(inputs, profile="legacy", proof=None):
    require(type(profile) is str and profile in WORLD_FIXTURES,
            "Unknown installed callback token fixture", "stale_input")
    value = copy.deepcopy(inputs)
    if profile == "source-layered-v1":
        require(type(proof) is dict and proof.get("fixture_format") == profile and
                proof.get("engine_authored_serialization") == "not_run" and
                proof.get("source_contract_sha256") == "461b4c338e29ef7b9105e1e39f92d66e6861b112f8a77bd45046413600d0e45e",
                "Layered token lacks the fixed source-contract identity", "stale_input")
        value["world_fixture"] = proof
    return mod.digest(mod.canonical(value))


def admitted_stage(staged, generated_path, profile="legacy"):
    require(type(profile) is str and profile in WORLD_FIXTURES,
            "Unknown installed callback staged fixture", "stale_input")
    expected = {"addon.gproj", generated_path, "scripts/Game/SPK_BerylCallbackObserver.c",
                "scripts/WorkbenchGameCommon/BerylComponentCallbacks.c", REL_WORLD, REL_WORLD + ".meta",
                "Prefabs/BerylCallbackProbe.et", "Prefabs/BerylCallbackProbe.et.meta"}
    if profile == "source-layered-v1":
        expected.add(REL_LAYER)
    require(type(staged) is dict and set(staged) == expected and len(staged) == (9 if profile == "source-layered-v1" else 8),
            "Callback staged inputs differ from the selected exact profile", "stale_input")


def renderer(config, mapping, token, addon, generated, world_fixture="legacy", layered=None, frame_diagnostics="off"):
    require(type(frame_diagnostics) is str and frame_diagnostics in FRAME_DIAGNOSTICS, "Unknown frame diagnostic profile")
    world_sources = world_fixture_sources(world_fixture, layered)
    require(type(mapping.get("linkage_schema_version")) is int and mapping["linkage_schema_version"] == 1 and
            type(mapping.get("linkage")) is list, "Actual emitted version-one linkage required", "unavailable")
    declarations = [row for row in mapping["linkage"] if row.get("declaration") == "sparkos.component_callback_probe.State"]
    require(len(declarations) == 1 and declarations[0].get("kind") == "struct", "Missing exact emitted State declaration")
    state = declarations[0]
    require(type(state.get("fields")) is list and len(state["fields"]) == 5 and
            all(type(item) is dict and set(item) == {"source", "name"} for item in state["fields"]), "Malformed exact field linkage")
    fields = {item["source"]: item["name"] for item in state["fields"]}
    require(set(fields) == {"ready", "init_count", "frame_count", "delete_count", "elapsed"}, "Actual emitted fields differ")
    component = config["components"][0]["instance"]["name"]
    symbols = {"COMPONENT": component, "STATE": state["class"], **{name.upper(): value for name, value in fields.items()}}
    require(all(type(value) is str and IDENT.fullmatch(value) for value in symbols.values()), "Emitted fixture identity is not an identifier")
    require(("protected ref " + symbols["STATE"] + " m_BerylState = new " + symbols["STATE"] + "();").encode() in generated,
            "Generated component's exact retained member initializer is unavailable", "unavailable")
    require(("class " + component + " : ScriptComponent").encode() in generated and
            ("void " + component + "(").encode() not in generated, "Native engine construction boundary changed", "unavailable")
    strings = {"TOKEN": token, "WORLD_ABSOLUTE": (addon / "worlds/BerylCallbackProbe.ent").as_posix(),
               "PROJECT_ABSOLUTE": (addon / "addon.gproj").as_posix()}
    # The installed fixture may substitute only exact identifiers, hex tokens,
    # and owned absolute paths. String literal escaping is explicit.
    require(all('\n' not in value and '\r' not in value and '\x00' not in value for value in strings.values()), "Invalid owned string identity")
    strings = {key: value.replace('\\', '\\\\').replace('"', '\\"') for key, value in strings.items()}
    result = {}
    for source, target in (("observer.c.in", "scripts/Game/SPK_BerylCallbackObserver.c"),
                           ("rpc.c.in", "scripts/WorkbenchGameCommon/BerylComponentCallbacks.c")):
        text = mod.read(PACKAGE / source).decode("utf-8")
        for key, value in {**symbols, **strings}.items():
            text = text.replace("@" + key + "@", value)
        require(not re.search(r"@[A-Z_]+@", text), "Unresolved trusted callback placeholder")
        result[target] = text.encode("utf-8")
    result.update(world_sources)
    if frame_diagnostics == "world-state-v1":
        text = mod.read(PACKAGE / "frame-state.c.in").decode("utf-8").replace("@TOKEN@", token)
        require(not re.search(r"@[A-Z_]+@", text), "Unresolved diagnostic placeholder")
        result[FRAME_SOURCE] = text.encode("utf-8")
    return result, symbols


def admitted_diagnostic_stage(staged, generated_path, world_fixture, frame_diagnostics):
    require(type(frame_diagnostics) is str and frame_diagnostics in FRAME_DIAGNOSTICS, "Unknown frame diagnostic profile")
    ordinary = dict(staged)
    if frame_diagnostics == "world-state-v1":
        require(FRAME_SOURCE in ordinary, "Selected diagnostic handler missing", "stale_input")
        ordinary.pop(FRAME_SOURCE)
    admitted_stage(ordinary, generated_path, world_fixture)


def generated_source(addon, artifact, mapping):
    """Resolve the sole generated file through actual manifest/map identities."""
    generated = mapping.get("generated")
    require(type(generated) is dict and set(generated) == {"file", "bytes", "sha256"} and
            generated.get("file") == "Beryl_Generated.c" and type(generated.get("bytes")) is int and
            0 < generated["bytes"] <= 16 * 1024 * 1024 and type(generated.get("sha256")) is str and
            HASH.fullmatch(generated["sha256"]), "Exact bounded generated-source identity unavailable", "unavailable")
    matches = [name for name, fingerprint in artifact["files"].items()
               if Path(name).name == generated["file"]]
    require(len(matches) == 1 and matches[0].startswith("scripts/Game/") and
            artifact["files"][matches[0]] == generated["sha256"], "Ambiguous/mismatched emitted source path", "stale_input")
    path = mod.safe_path(addon, matches[0])
    data = mod.read(path)
    require(len(data) == generated["bytes"] and mod.digest(data) == generated["sha256"],
            "Actual generated source bytes differ from linkage identity", "stale_input")
    return data, matches[0]


def checksum(rows):
    value = 0
    for row in rows:
        for code in (row + "\n").encode("ascii"):
            value = (value * 31 + code) % 1000003
    return value


def validate_load_progress(value, previous=None):
    """Validate a snapshot and monotonic same-token progress, without inferring completion."""
    require(type(value) is dict and all(name in value for name in (*LOAD_COUNTERS, "load_accepted", "token")),
            "Incomplete native load progress")
    require(all(type(value[name]) is int and value[name] in (0,1) for name in LOAD_COUNTERS) and
            type(value["load_accepted"]) is bool, "Invalid exact native load progress counters")
    require(value["load_submitted"] <= value["load_requested"] and value["load_entered"] <= value["load_requested"] and
            value["load_resumed"] <= value["load_entered"] and value["load_resumed"] <= value["load_submitted"] and
            value["load_returned"] <= value["load_resumed"] and (not value["load_accepted"] or value["load_returned"] == 1),
            "Impossible native load progress order")
    if value.get("status") in ("ready", "complete"):
        require(all(value[name] == 1 for name in LOAD_COUNTERS) and value["load_accepted"],
                "Ready/completed response lacks accepted native load execution")
    if previous is not None:
        validate_load_progress(previous)
        require(type(value["token"]) is str and value["token"] == previous["token"],
                "Native load progress belongs to another compiled token", "stale_input")
        require(all(value[name] >= previous[name] for name in LOAD_COUNTERS) and
                (not previous["load_accepted"] or value["load_accepted"]), "Native load progress reset during the owned job", "stale_input")


def normalize_wire_response(raw):
    """Decode the observed JsonApiStruct wire form without mutating raw data."""
    require(type(raw) is dict and not (set(raw) - WIRE_FIELDS) and
            not ((WIRE_FIELDS - {"caseIds", "rows"}) - set(raw)), "Incomplete or unknown callback wire fields")
    normalized = copy.deepcopy(raw)
    codec = {"schema_version": 1, "name": "enfusion.jsonapistruct.bool01-emptyarrays.v1",
             "numeric_boolean_fields": [], "omitted_empty_arrays": []}
    for name in WIRE_BOOLS:
        value = raw[name]
        require(type(value) is bool or (type(value) is int and value in (0,1)), "Invalid exact bool/0/1 wire field: " + name)
        if type(value) is int:
            normalized[name] = value == 1
            codec["numeric_boolean_fields"].append(name)
    for name in ("resource_name", "resource_path", "resource_absolute_path"):
        require(type(raw[name]) is str and len(raw[name]) <= 2048, "Invalid bounded resource wire string: " + name)
    require(type(raw["executed"]) is int and raw["executed"] in (0,1) and
            type(raw["event_count"]) is int and 0 <= raw["event_count"] <= 4096, "Invalid wire empty-array counters")
    for name in ("caseIds", "rows"):
        if name not in raw:
            require(raw["executed"] == 0 and (name == "caseIds" or raw["event_count"] == 0),
                    "Missing nonempty/completed wire array: " + name)
            normalized[name] = []
            codec["omitted_empty_arrays"].append(name)
        else:
            require(type(raw[name]) is list and len(raw[name]) <= (16 if name == "caseIds" else 4096), "Invalid bounded wire array: " + name)
    require(len(normalized["rows"]) == raw["event_count"], "Wire event count differs from actual rows")
    validate_load_progress(normalized)
    return normalized, codec


def validate_callback_response(value, token, project, world):
    require(type(value) is dict and set(value) == WIRE_FIELDS, "Incomplete or unknown callback response fields")
    validate_load_progress(value)
    require(all(value[name] == 1 for name in LOAD_COUNTERS) and value["load_accepted"], "Completion lacks accepted native load execution")
    require(value["token"] == token and value["action"] in ("delete", "status") and value["status"] == "complete" and
            value["failure"] == "", "Callback completion identity/status differs", "stale_input")
    require(all(type(value[name]) is bool for name in WIRE_BOOLS) and value["addon_world_resolved"] and value["world_path_resolved"] and
            value["world_matches"] and value["resource_name_resolved"] and value["module_present"] and value["api_present"] and
            value["module_open_requested"] and value["module_open_accepted"] and
            not value["edit_mode"] and value["game_mode"] and value["in_play_mode"] and value["world_present"],
            "Completion lacks the actual owned running world")
    require(type(value["world_path"]) is str and 0 < len(value["world_path"]) <= 2048 and
            type(value["current_project"]) is str and len(value["current_project"]) <= 2048 and
            type(value["addon_world_path"]) is str and value["addon_world_path"].replace('\\', '/') == world and
            type(value["world_absolute_path"]) is str and value["world_absolute_path"].replace('\\', '/') == world,
            "Native addon/observed world resolution differs", "stale_input")
    require(type(value["resource_name"]) is str and value["resource_name"] == EXPECTED_WORLD_RESOURCE and
            type(value["resource_path"]) is str and 0 < len(value["resource_path"]) <= 2048 and
            type(value["resource_absolute_path"]) is str and value["resource_absolute_path"].replace('\\', '/') == world,
            "Native world resource identity/resolution differs", "stale_input")
    for key, minimum, maximum in (("phase",4,4),("executed",1,1),("failures",0,0),("checks",1,100000),
                                  ("event_count",1,4096),("checksum",0,1000002)):
        require(type(value[key]) is int and minimum <= value[key] <= maximum, "Invalid callback receipt integer: " + key)
    require(type(value["caseIds"]) is list and value["caseIds"] == list(CASE_IDS), "Missing, reordered or unknown callback cases")
    rows = value["rows"]
    require(type(rows) is list and len(rows) == value["event_count"] and len(rows) <= 4096 and
            all(type(row) is str and 0 < len(row) <= 512 and row.isascii() for row in rows), "Malformed bounded callback trace")
    require(checksum(rows) == value["checksum"], "Callback trace checksum differs")
    state = {1: {"phase": "cold", "frames": 0}, 2: {"phase": "cold", "frames": 0}}
    pending, authorities, independent, event_count, controls = None, [], False, 0, 0
    for sequence, row in enumerate(rows):
        parts = row.split("|")
        require(len(parts) >= 2 and parts[1] == str(sequence), "Missing or noncontiguous callback sequence")
        if parts[0] == "control":
            require(len(parts) == 5 and pending is None and parts[4] == "1", "Unknown/failed/interleaved callback control")
            kind, token_text = parts[2:4]
            if kind == "authority":
                expected = (1,2,1,2)
                require(len(authorities) < 4 and token_text == str(expected[len(authorities)]), "Authority order/token differs")
                require((len(authorities) < 2 and not independent) or (len(authorities) >= 2 and independent), "Authority observation boundary differs")
                require(state[int(token_text)]["phase"] == "alive", "Authority observed before initialization or after deletion")
                if not authorities:
                    require(state[2]["phase"] == "cold", "First authority observation moved past second spawn initialization")
                authorities.append(int(token_text))
            elif kind == "independent":
                require(token_text == "0" and not independent and authorities == [1,2] and
                        all(item["phase"] == "alive" and item["frames"] >= 3 for item in state.values()), "Independent-state observation is premature/duplicated")
                independent = True
            else:
                require(False, "Unknown callback control kind")
            controls += 1
            continue
        require(parts[0] == "event" and len(parts) == 12 and all(re.fullmatch(r"[0-9]+", item) for item in parts[3:]), "Malformed callback event")
        kind, identity_text = parts[2:4]
        identity_value = int(identity_text)
        require(identity_value in state, "Unknown callback fixture token")
        item = state[identity_value]
        inits, frames, deletes, ready, present, owner_same, state_same, float_equal = map(int, parts[4:])
        require((present,owner_same,state_same,float_equal) == (1,1,1,1), "State/owner/rounded-float observation differs")
        if kind.endswith("_before"):
            require(pending is None, "Reordered/interleaved callback body")
            pending = (identity_value, kind.replace("_before", "_after"))
            if kind == "init_before":
                require(item["phase"] == "cold" and (inits,frames,deletes,ready) == (0,0,0,1), "Initial callback defaults differ")
            elif kind == "frame_before":
                require(item["phase"] == "alive" and (inits,frames,deletes,ready) == (1,item["frames"],0,1), "Frame before state differs")
            elif kind == "delete_before":
                require(independent and authorities == [1,2,1,2] and item["phase"] == "alive" and
                        item["frames"] >= 3 and (inits,frames,deletes,ready) == (1,item["frames"],0,1), "Delete before state/order differs")
            else:
                require(False, "Unknown callback event kind")
        else:
            require(pending == (identity_value,kind), "Missing/reordered callback before/after")
            pending = None
            if kind == "init_after":
                require((inits,frames,deletes,ready) == (1,0,0,1), "Post-init handler did not update state")
                item["phase"] = "alive"
            elif kind == "frame_after":
                item["frames"] += 1
                require((inits,frames,deletes,ready) == (1,item["frames"],0,1), "Frame handler did not update exactly once")
            elif kind == "delete_after":
                require((inits,frames,deletes,ready) == (1,item["frames"],1,0), "Delete handler state differs")
                item["phase"] = "deleted"
            else:
                require(False, "Unknown callback event kind")
        event_count += 1
    require(pending is None and authorities == [1,2,1,2] and independent and
            all(item["phase"] == "deleted" and item["frames"] >= 3 for item in state.values()) and
            value["checks"] == event_count * 8 + controls, "Incomplete callback trace/check accounting")
    return {"status": "verified", "cases": len(CASE_IDS), "frames": [state[1]["frames"],state[2]["frames"]],
            "event_rows": event_count, "control_rows": controls, "checks": value["checks"],
            "base_game_project_raw": value["current_project"], "expected_project": project,
            "native_world_path": value["world_absolute_path"],
            "rows": len(rows), "checksum": value["checksum"], "float_comparison": "target rounded f32 equality; no bit serialization claim"}


def validate_runtime_envelope(runtime, token, project, project_id, engine_path, binding, plugin_files):
    """Admit the exact successful owned transport envelope, independently of trace values.

    The fixed caller invokes the adapter with its 180-second default deadline.
    Session checks are the sites the pinned adapter actually emits; no synthetic
    end marker or project field is expected in those individual rows.
    """
    runtime_tools = ("Find-Workbench.ps1", "Start-WorkbenchDaemon.ps1", "Invoke-WorkbenchRpc.ps1")
    require(type(runtime) is dict and type(runtime.get("schema_version")) is int and runtime["schema_version"] == 1 and
            runtime.get("status") == "success" and runtime.get("stage") == "callback_transport_complete" and
            runtime.get("token") == token and runtime.get("function") == FUNCTION and runtime.get("project_id") == project_id,
            "Missing exact successful callback transport envelope")
    require(type(runtime.get("evidence_errors")) is list and runtime["evidence_errors"] == [],
            "Missing explicitly complete callback evidence")
    require(type(binding) is dict and runtime.get("engine_sha256") == binding.get("sha256") and
            runtime.get("engine_version") == binding.get("version") and type(plugin_files) is dict and
            all(name in plugin_files for name in runtime_tools) and runtime.get("tools") == {name: plugin_files[name] for name in runtime_tools},
            "Callback engine or integration-tool identity differs", "stale_input")
    session = runtime.get("session")
    require(type(session) is dict and session.get("reused") is False and session.get("project") == project and
            type(session.get("process_id")) is int and session["process_id"] > 0 and
            type(session.get("start_ticks")) is int and session["start_ticks"] > 0 and
            type(session.get("executable")) is str and
            session["executable"].replace("\\", "/").casefold() == engine_path.replace("\\", "/").casefold(),
            "Missing exact pinned callback session identity", "stale_input")
    elapsed = runtime.get("elapsed_ms")
    require(type(elapsed) is int and 0 <= elapsed < 180000, "Missing bounded callback transport elapsed time")
    calls = runtime.get("rpcs")
    require(type(calls) is list and 5 <= len(calls) <= 325 and all(type(call) is dict for call in calls),
            "Missing or excessive callback RPC set")
    stages = ("load", "play", "spawn", "delete", "stop")
    sites = ["startup.complete", "loaded-projects.complete"]
    stage_index, stage_count = -1, 0
    for call in calls:
        action, stage = call.get("action"), call.get("stage")
        require(type(action) is str and action in (*stages, "status") and type(stage) is str and stage in stages,
                "Unregistered callback RPC action or stage")
        if stage_index < 0 or stage != stages[stage_index]:
            stage_index += 1
            require(stage_index < len(stages) and stage == stages[stage_index] and action == stage,
                    "Incomplete or reordered callback RPC stages")
            stage_count = 1
        else:
            stage_count += 1
            require(action == "status" and stage_count <= 65, "Repeated callback command or excessive status polls")
        sites.extend(("before." + action, "after." + action))
    require(stage_index == len(stages) - 1, "Callback RPC stages did not complete")
    checks = runtime.get("session_checks")
    require(type(checks) is list and len(checks) == len(sites), "Missing exact ordered callback session-check set")
    previous_elapsed = 0
    for check, site in zip(checks, sites):
        require(type(check) is dict and set(check) == {"site", "process_id", "start_ticks", "executable", "elapsed_ms"} and
                check["site"] == site and type(check["process_id"]) is int and check["process_id"] == session["process_id"] and
                type(check["start_ticks"]) is int and check["start_ticks"] == session["start_ticks"] and
                check["executable"] == session["executable"],
                "Missing, stale or reordered callback process check", "stale_input")
        require(type(check["elapsed_ms"]) is int and previous_elapsed <= check["elapsed_ms"] <= elapsed,
                "Missing or nonmonotonic callback session-check time")
        previous_elapsed = check["elapsed_ms"]
    for index, call in enumerate(calls):
        before, after = checks[2 + index * 2], checks[3 + index * 2]
        require(type(call.get("elapsed_ms")) is int and before["elapsed_ms"] <= call["elapsed_ms"] <= after["elapsed_ms"] and
                type(call.get("timeout_ms")) is int and 1 <= call["timeout_ms"] <= 8000 and
                "failure" in call and call["failure"] is None,
                "Incomplete bounded callback RPC attempt")
    return {"status": "verified", "scope": "owned transport envelope only", "rpcs": len(calls),
            "session_checks": len(checks), "elapsed_ms": elapsed}


def validate_engine_updates(runtime, policy, project, engine_path):
    """Validate additive startup-policy evidence; no callback inference is made."""
    require(type(policy) is str and policy in ENGINE_UPDATES and type(runtime) is dict and
            runtime.get("engine_updates") == policy, "Selected engine update policy differs", "stale_input")
    launch, ports, checks = (runtime.get(name) for name in ("engine_update_launch", "port_checks", "launch_checks"))
    errors = runtime.get("port_query_errors")
    if policy == "focus-dependent":
        require("engine_update_launch" in runtime and launch is None and ports == [] and checks == [] and errors == [],
                "Focus-dependent policy contains alternate startup evidence", "stale_input")
        return {"status": "verified", "policy": policy, "scope": "legacy installed-daemon selection only"}
    session = runtime.get("session")
    require(type(session) is dict and type(launch) is dict and set(launch) == {
        "schema_version", "mechanism", "arguments", "working_directory", "use_shell_execute", "create_no_window",
        "window_style", "launch_returned", "process_id", "start_ticks", "executable", "limits"},
        "Missing exact force-update launch receipt")
    same_path = lambda a, b: type(a) is str and type(b) is str and a.replace("\\", "/").rstrip("/").casefold() == b.replace("\\", "/").rstrip("/").casefold()
    arguments = launch["arguments"]
    require(type(launch["schema_version"]) is int and launch["schema_version"] == 1 and
            launch["mechanism"] == "force_update_argument_list" and type(arguments) is list and len(arguments) == 5 and
            arguments[0] == "-gproj" and same_path(arguments[1], project + "/addon.gproj") and
            arguments[2:] == ["-noOpenLastResource", "-scriptAuthorizeAll", "-forceUpdate"] and
            launch["use_shell_execute"] is False and launch["create_no_window"] is True and
            launch["window_style"] == "Hidden" and launch["launch_returned"] is True and
            type(launch["working_directory"]) is str and re.fullmatch(r"[A-Za-z]:[\\/].{1,2046}", launch["working_directory"]),
            "Force-update launch arguments or startup flags differ", "stale_input")
    for name in ("process_id", "start_ticks"):
        require(type(launch[name]) is int and launch[name] > 0 and launch[name] == session.get(name) and
                type(session.get(name)) is int, "Force-update launch process identity differs", "stale_input")
    startup = runtime.get("startup")
    require(type(startup) is dict and set(startup) == {"Ok", "Reused", "ProcessId", "Mechanism"} and
            startup["Ok"] is True and startup["Reused"] is False and type(startup["ProcessId"]) is int and
            startup["ProcessId"] == launch["process_id"] and startup["Mechanism"] == "force_update_argument_list",
            "Force-update startup receipt differs", "stale_input")
    require(same_path(launch["executable"], engine_path) and same_path(session.get("executable"), engine_path) and
            same_path(session.get("project"), project) and session.get("reused") is False,
            "Force-update launch executable/session differs", "stale_input")
    limits = {"startup_ms": 30000, "rpc_ms": 8000, "overall_ms": 180000, "cleanup_ms": 5000, "max_polls": 64}
    require(type(launch["limits"]) is dict and set(launch["limits"]) == set(limits) and
            all(type(launch["limits"][key]) is int and launch["limits"][key] == value for key, value in limits.items()),
            "Force-update launch bounds changed")
    require(type(ports) is list and 1 <= len(ports) <= 64 and type(checks) is list and len(checks) == len(ports) + 1 and
            type(errors) is list and len(errors) <= 128 and type(runtime.get("elapsed_ms")) is int and
            0 <= runtime["elapsed_ms"] < 180000, "Incomplete bounded force-update startup inventory")
    previous = -1
    for index, check in enumerate(checks):
        require(type(check) is dict and set(check) == {"site", "process_id", "start_ticks", "executable", "elapsed_ms"} and
                check["site"] == ("launch.identity" if index == 0 else "port.check") and
                type(check["process_id"]) is int and check["process_id"] == launch["process_id"] and
                type(check["start_ticks"]) is int and check["start_ticks"] == launch["start_ticks"] and
                same_path(check["executable"], engine_path) and type(check["elapsed_ms"]) is int and
                0 <= check["elapsed_ms"] < 30000 and previous <= check["elapsed_ms"] <= runtime["elapsed_ms"],
                "Force-update startup identity checks differ", "stale_input")
        previous = check["elapsed_ms"]
    for index, port in enumerate(ports):
        require(type(port) is dict and set(port) == {"elapsed_ms", "listening", "owning_process"} and
                type(port["elapsed_ms"]) is int and checks[index]["elapsed_ms"] <= port["elapsed_ms"] <= checks[index+1]["elapsed_ms"] and
                type(port["listening"]) is bool and
                (port["listening"] is (index == len(ports)-1)) and
                ((type(port["owning_process"]) is int and port["owning_process"] == launch["process_id"]) if port["listening"] else port["owning_process"] is None),
                "Force-update listener ownership or ordering differs", "stale_input")
    for error in errors:
        require(type(error) is dict and set(error) == {"elapsed_ms", "category", "id", "message"} and
                type(error["elapsed_ms"]) is int and checks[0]["elapsed_ms"] <= error["elapsed_ms"] <= checks[-1]["elapsed_ms"] and
                error["category"] == "ObjectNotFound" and all(type(error[name]) is str and len(error[name]) <= 2048 for name in ("id", "message")),
                "Unverified native listener query error")
    require(type(runtime.get("session_checks")) is list and runtime["session_checks"] and
            type(runtime["session_checks"][0]) is dict and type(runtime["session_checks"][0].get("elapsed_ms")) is int and
            0 <= runtime["session_checks"][0]["elapsed_ms"] <= runtime["elapsed_ms"] and
            checks[-1]["elapsed_ms"] <= runtime["session_checks"][0]["elapsed_ms"],
            "Force-update startup does not precede callback session validation")
    return {"status": "verified", "policy": policy, "scope": "fixed owned startup and listener identity only", "port_checks": len(ports)}


def engine_update_basis(policy):
    require(type(policy) is str and policy in ENGINE_UPDATES, "Unknown engine update policy", "stale_input")
    if policy == "focus-dependent":
        return None, []
    require(UPDATE_DOCUMENT.is_file() and not UPDATE_DOCUMENT.is_symlink(),
            "Installed update-policy primary declaration is unavailable", "unavailable")
    data = mod.read(UPDATE_DOCUMENT)
    require(mod.digest(data) == UPDATE_DOCUMENT_SHA and b"-forceUpdate" in data,
            "Installed update-policy declaration changed", "stale_input")
    return {"policy": policy, "primary": identity(UPDATE_DOCUMENT), "declaration_line": 157,
            "claim": "documented rendering/update while unfocused; experimental callback scheduling control; no observed cause claim"}, [
                ("engine-update-primary/Page_CLI.html", UPDATE_DOCUMENT)]


def engine_update_profile(policy, project):
    require(type(policy) is str and policy in ENGINE_UPDATES and type(project) is str,
            "Unknown update-policy token profile", "stale_input")
    if policy == "focus-dependent":
        return {"policy": policy, "mechanism": "installed_daemon", "arguments": None}
    return {"policy": policy, "mechanism": "force_update_argument_list",
            "arguments": ["-gproj", str(Path(project) / "addon.gproj"), "-noOpenLastResource", "-scriptAuthorizeAll", "-forceUpdate"],
            "use_shell_execute": False, "create_no_window": True, "window_style": "Hidden"}


def runtime_envelope_self_test():
    """Predeclared synthetic envelope faults; never execute an adapter or compiler."""
    token, project_id = "a" * 64, "BerylComponentCallbackProbe"
    project, engine_path = "C:/fixture/addon", "C:/fixture/Workbench.exe"
    binding = {"sha256": "e" * 64, "version": "fixture.engine"}
    plugin_files = {name: "f" * 64 for name in ("Find-Workbench.ps1", "Start-WorkbenchDaemon.ps1", "Invoke-WorkbenchRpc.ps1")}
    original = {"schema_version": 1, "status": "success", "stage": "callback_transport_complete", "token": token,
                "function": FUNCTION, "project_id": project_id, "engine_sha256": binding["sha256"],
                "engine_version": binding["version"], "tools": plugin_files, "evidence_errors": [], "elapsed_ms": 800,
                "session": {"reused": False, "project": project, "process_id": 123, "start_ticks": 456, "executable": engine_path},
                "rpcs": [], "session_checks": []}
    for stage, action, elapsed in (("load", "load", 100), ("load", "status", 200), ("play", "play", 300),
                                   ("spawn", "spawn", 400), ("delete", "delete", 500), ("stop", "stop", 600)):
        original["rpcs"].append({"stage": stage, "action": action, "elapsed_ms": elapsed, "timeout_ms": 8000, "failure": None})
    sites = [("startup.complete", 10), ("loaded-projects.complete", 20)]
    for call in original["rpcs"]:
        sites.extend((("before." + call["action"], call["elapsed_ms"] - 5), ("after." + call["action"], call["elapsed_ms"] + 5)))
    for site, elapsed in sites:
        original["session_checks"].append({"site": site, "process_id": 123, "start_ticks": 456,
                                           "executable": engine_path, "elapsed_ms": elapsed})
    faults = (
        ("missing-schema", ("schema_version",), None), ("schema-bool", ("schema_version",), True),
        ("schema-float", ("schema_version",), 1.0), ("wrong-schema", ("schema_version",), 2),
        ("missing-errors", ("evidence_errors",), None), ("errors-null", ("evidence_errors",), None),
        ("errors-object", ("evidence_errors",), {}), ("nonempty-errors", ("evidence_errors",), [{"stage": "cleanup"}]),
        ("missing-checks", ("session_checks",), None), ("checks-null", ("session_checks",), None),
        ("missing-check", ("session_checks",), original["session_checks"][:-1]),
        ("extra-check", ("session_checks",), original["session_checks"] + [copy.deepcopy(original["session_checks"][-1])]),
        ("reordered-checks", ("session_checks",), original["session_checks"][1:2] + original["session_checks"][:1] + original["session_checks"][2:]),
        ("wrong-site", ("session_checks", 2, "site"), "before.status"),
        ("wrong-pid", ("session_checks", 2, "process_id"), 124), ("check-pid-bool", ("session_checks", 2, "process_id"), True),
        ("wrong-start-ticks", ("session_checks", 2, "start_ticks"), 457), ("check-start-bool", ("session_checks", 2, "start_ticks"), True),
        ("wrong-check-path", ("session_checks", 2, "executable"), "C:/other/Workbench.exe"),
        ("wrong-project", ("session", "project"), "C:/other/addon"), ("wrong-pinned-path", ("session", "executable"), "C:/other/Workbench.exe"),
        ("reused-session", ("session", "reused"), True), ("elapsed-bool", ("elapsed_ms",), True),
        ("reversed-time", ("session_checks", 4, "elapsed_ms"), 1), ("future-time", ("session_checks", 13, "elapsed_ms"), 801),
        ("total-timeout", ("elapsed_ms",), 180000), ("unregistered-action", ("rpcs", 0, "action"), "save"),
        ("wrong-stage", ("rpcs", 0, "stage"), "play"), ("repeated-command", ("rpcs", 1, "action"), "load"),
        ("call-time-bool", ("rpcs", 0, "elapsed_ms"), True), ("call-before-check", ("rpcs", 0, "elapsed_ms"), 94),
        ("call-after-check", ("rpcs", 0, "elapsed_ms"), 106), ("timeout-bool", ("rpcs", 0, "timeout_ms"), True),
        ("timeout-excess", ("rpcs", 0, "timeout_ms"), 8001), ("call-failure", ("rpcs", 0, "failure"), "incomplete"),
        ("missing-calls", ("rpcs",), None), ("excess-calls", ("rpcs",), [copy.deepcopy(original["rpcs"][0])] * 326),
        ("outer-failure", ("status",), "failure"), ("wrong-token", ("token",), "b" * 64),
        ("wrong-engine", ("engine_sha256",), "0" * 64), ("wrong-tools", ("tools",), {}),
        ("session-pid-bool", ("session", "process_id"), True), ("session-start-bool", ("session", "start_ticks"), True),
        ("missing-check-field", ("session_checks", 2, "executable"), None),
        ("unknown-check-field", ("session_checks", 2, "project"), project),
        ("invented-end-marker", ("session_checks",), original["session_checks"] + [{"site": "callback.complete"}]),
        ("initial-status", ("rpcs", 0, "action"), "status"),
        ("excess-stage-polls", ("rpcs",), original["rpcs"][:1] + [copy.deepcopy(original["rpcs"][1])] * 65 + original["rpcs"][2:]),
        ("missing-call-failure", ("rpcs", 0, "failure"), None),
    )
    expected_ids = ["runtime-envelope-valid", *("runtime-envelope-" + case_id for case_id, _, _ in faults)]
    require(len(expected_ids) == len(set(expected_ids)) == 50, "Runtime envelope synthetic registration is invalid")
    result = validate_runtime_envelope(original, token, project, project_id, engine_path, binding, plugin_files)
    cases = [{"id": expected_ids[0], "status": "passed"}]
    removals = {"missing-schema", "missing-errors", "missing-checks", "missing-calls", "missing-check-field", "missing-call-failure"}
    for case_id, path, replacement in faults:
        value = copy.deepcopy(original)
        target = value
        for key in path[:-1]: target = target[key]
        if case_id in removals: del target[path[-1]]
        else: target[path[-1]] = copy.deepcopy(replacement)
        try:
            validate_runtime_envelope(value, token, project, project_id, engine_path, binding, plugin_files)
        except mod.Failure as exc:
            cases.append({"id": "runtime-envelope-" + case_id, "status": "rejected", "outcome": exc.status, "diagnostic": str(exc)})
        else:
            require(False, "Runtime envelope fault accepted: " + case_id)
    require([case["id"] for case in cases] == expected_ids, "Runtime envelope synthetic receipt is incomplete")
    work = Path(tempfile.mkdtemp(prefix="component-callback-envelope-tests-", dir=ROOT / "build"))
    receipt = {"schema_version": 1, "operation": "component.callback.runtime-envelope.self_test", "status": "success",
               "scope": "synthetic owned transport envelope and deliberate evidence faults only",
               "expected_case_ids": expected_ids, "completed_case_ids": [case["id"] for case in cases],
               "complete_expected_case_set": True, "cases": cases, "case_count": len(cases), "synthetic_envelope": result,
               "verifier": identity(Path(__file__)), "compiler_execution": "not_run", "engine_execution": "not_run",
               "callback_delivery": "not_run"}
    save_result(work / "result.json", receipt)
    print(str(work / "result.json"))


def self_test():
    """Synthetic receipt/parser faults only: no compiler or engine operation."""
    token = "a" * 64
    project, world = "C:/fixture/addon.gproj", "C:/fixture/worlds/BerylCallbackProbe.ent"
    expected_case_ids = [
        "complete-synthetic", "wrong-token", "boolean-as-phase", "unknown-field", "missing-field",
        "wrong-resolved-world", "wrong-addon-world", "not-playing", "partial-cases", "unknown-case", "checksum",
        "check-accounting", "sequence", "state-root-changed", "handler-skipped", "duplicate-frame-count",
        "unknown-owner-token", "authority-failed", "delete-skipped", "before-after-order",
        "authority-before-initialization", "first-authority-after-second-initialization",
        "wrong-resource-name", "wrong-resource-absolute-path", "resource-name-unresolved", "module-absent", "api-absent",
        "module-present-as-int", "api-present-as-int", "resource-name-as-int", "resource-absolute-path-as-null",
        "empty-resource-path", "resource-path-as-int", "resource-path-oversize",
        "module-open-not-requested", "module-open-not-accepted", "module-open-requested-as-int", "module-open-accepted-as-int",
        "completion-load-not-requested", "completion-load-not-submitted", "completion-load-not-entered", "completion-load-not-resumed",
        "completion-load-not-returned", "completion-load-not-accepted", "completion-load-accepted-as-int",
        "wire-complete-bool01-native-paths", "wire-known-empty-arrays", "wire-partial-rows-empty-cases",
        "wire-pending-absent-resource-and-editor", "wire-unavailable-absent-resource-and-editor",
        "wire-bool-string", "wire-bool-float", "wire-bool-two", "wire-complete-missing-cases",
        "wire-complete-missing-rows", "wire-partial-missing-nonempty-rows", "wire-unknown-field",
        "wire-boolean-counter", "wire-incomplete-counter", "wire-row-count-mismatch",
        "wire-missing-resource-name", "wire-resource-name-string-type", "wire-resource-absolute-path-string-type",
        "wire-resource-name-resolved-bool-two", "wire-module-bool-string", "wire-api-bool-float",
        "wire-missing-resource-path", "wire-resource-path-string-type", "wire-resource-path-string-oversize",
        "wire-missing-module-open-requested", "wire-missing-module-open-accepted",
        "wire-module-open-requested-string", "wire-module-open-requested-float", "wire-module-open-requested-two",
        "wire-module-open-accepted-string", "wire-module-open-accepted-float", "wire-module-open-accepted-two",
        "wire-missing-load-requested", "wire-missing-load-submitted", "wire-missing-load-entered", "wire-missing-load-resumed",
        "wire-missing-load-returned", "wire-missing-load-accepted",
        "wire-load-requested-bool", "wire-load-submitted-bool", "wire-load-entered-bool", "wire-load-resumed-bool", "wire-load-returned-bool",
        "wire-load-counter-float", "wire-load-counter-string", "wire-load-counter-two",
        "wire-load-accepted-string", "wire-load-accepted-float", "wire-load-accepted-two",
        "wire-load-cold", "wire-load-submitted-before-entry", "wire-load-entered-before-submit", "wire-load-resumed-prefix", "wire-load-returned-refused",
        "wire-load-submitted-without-request", "wire-load-entered-without-request", "wire-load-resumed-without-entry", "wire-load-resumed-without-submit",
        "wire-load-returned-without-resume", "wire-load-accepted-before-return",
        "progress-delayed-entry", "progress-immediate-entry", "progress-reset-all", "progress-reset-accepted", "progress-stale-token",
        "wire-ready-load-not-requested", "wire-ready-load-not-submitted", "wire-ready-load-not-entered", "wire-ready-load-not-resumed",
        "wire-ready-load-not-returned", "wire-ready-load-refused",
        "compile-evidence-valid", "compile-evidence-errors", "compile-evidence-outer-failure", "compile-evidence-schema-bool",
        "compile-evidence-errorcount-bool", "compile-evidence-exit-bool", "compile-evidence-wrong-tools", "compile-evidence-wrong-engine",
    ]
    require(len(expected_case_ids) == len(set(expected_case_ids)) == 124, "Synthetic case registration is invalid")
    rows = []
    def event(kind, owner, inits, frames, deletes, ready):
        rows.append("|".join(map(str, ("event", len(rows), kind, owner, inits, frames, deletes, ready, 1, 1, 1, 1))))
    def control(kind, owner):
        rows.append("|".join(map(str, ("control", len(rows), kind, owner, 1))))
    for owner in (1,2):
        event("init_before", owner, 0,0,0,1)
        event("init_after", owner, 1,0,0,1)
        control("authority", owner)
    for frame in range(3):
        for owner in (1,2):
            event("frame_before", owner, 1,frame,0,1)
            event("frame_after", owner, 1,frame+1,0,1)
    control("independent",0)
    control("authority",1)
    control("authority",2)
    for owner in (1,2):
        event("delete_before",owner,1,3,0,1)
        event("delete_after",owner,1,3,1,0)
    original = {"token": token, "action": "delete", "status": "complete", "failure": "", "world_path": "$BerylComponentCallbackProbe:worlds/BerylCallbackProbe.ent",
                "current_project": "./addons/data/ArmaReforger.gproj", "addon_world_path": world,
                "world_absolute_path": world, "addon_world_resolved": True, "world_path_resolved": True,
                "resource_name": EXPECTED_WORLD_RESOURCE, "resource_path": "worlds/BerylCallbackProbe.ent", "resource_absolute_path": world,
                "resource_name_resolved": True, "module_present": True, "api_present": True,
                "module_open_requested": True, "module_open_accepted": True,
                "load_requested": 1, "load_submitted": 1, "load_entered": 1, "load_resumed": 1, "load_returned": 1, "load_accepted": True,
                "world_matches": True, "edit_mode": False, "game_mode": True,
                "in_play_mode": True, "world_present": True, "phase": 4, "executed": 1, "checks": 165,
                "failures": 0, "event_count": 25, "checksum": checksum(rows), "caseIds": list(CASE_IDS), "rows": rows}
    result = validate_callback_response(original, token, project, world)
    cases = [{"id": "complete-synthetic", "status": "passed"}]
    def reject(name, change, repair_wire=False):
        value = copy.deepcopy(original)
        change(value)
        if repair_wire:
            value["checksum"] = checksum(value["rows"])
        try:
            validate_callback_response(value, token, project, world)
        except mod.Failure as exc:
            cases.append({"id": name, "status": "rejected", "diagnostic": str(exc)})
        else:
            require(False, "Receipt fault accepted: " + name)
    reject("wrong-token", lambda v: v.update(token="b"*64))
    reject("boolean-as-phase", lambda v: v.update(phase=True))
    reject("unknown-field", lambda v: v.update(extra=0))
    reject("missing-field", lambda v: v.pop("world_matches"))
    reject("wrong-resolved-world", lambda v: v.update(world_absolute_path="C:/other.ent"))
    reject("wrong-addon-world", lambda v: v.update(addon_world_path="C:/other.ent"))
    reject("not-playing", lambda v: v.update(in_play_mode=False))
    reject("partial-cases", lambda v: v.update(caseIds=list(CASE_IDS[:-1])))
    reject("unknown-case", lambda v: v["caseIds"].__setitem__(0,"unregistered"))
    reject("checksum", lambda v: v.update(checksum=0))
    reject("check-accounting", lambda v: v.update(checks=164))
    reject("sequence", lambda v: v["rows"].__setitem__(0,v["rows"][0].replace("event|0|","event|1|")), True)
    reject("state-root-changed", lambda v: v["rows"].__setitem__(1,v["rows"][1][:-3]+"0|1"), True)
    reject("handler-skipped", lambda v: v["rows"].__setitem__(1,v["rows"][1].replace("init_after|1|1|","init_after|1|0|")), True)
    reject("duplicate-frame-count", lambda v: v["rows"].__setitem__(7,v["rows"][7].replace("frame_after|1|1|1|","frame_after|1|1|0|")), True)
    reject("unknown-owner-token", lambda v: v["rows"].__setitem__(0,v["rows"][0].replace("init_before|1|","init_before|3|")), True)
    reject("authority-failed", lambda v: v["rows"].__setitem__(2,v["rows"][2][:-1]+"0"), True)
    reject("delete-skipped", lambda v: v["rows"].__setitem__(22,v["rows"][22].replace("delete_after|1|1|3|1|0|","delete_after|1|1|3|0|1|")), True)
    reject("before-after-order", lambda v: v["rows"].__setitem__(0,v["rows"][0].replace("init_before","init_after")), True)
    def reorder(value, indices):
        ordered = [value["rows"][index] for index in indices]
        for index, row in enumerate(ordered):
            parts = row.split("|")
            parts[1] = str(index)
            ordered[index] = "|".join(parts)
        value["rows"] = ordered
    reject("authority-before-initialization", lambda v: reorder(v,[2,5,0,1,3,4]+list(range(6,25))), True)
    reject("first-authority-after-second-initialization", lambda v: reorder(v,[0,1,3,4,2,5]+list(range(6,25))), True)
    reject("wrong-resource-name", lambda v: v.update(resource_name="{OTHER}worlds/BerylCallbackProbe.ent"))
    reject("wrong-resource-absolute-path", lambda v: v.update(resource_absolute_path="C:/other.ent"))
    reject("resource-name-unresolved", lambda v: v.update(resource_name_resolved=False))
    reject("module-absent", lambda v: v.update(module_present=False))
    reject("api-absent", lambda v: v.update(api_present=False))
    reject("module-present-as-int", lambda v: v.update(module_present=1))
    reject("api-present-as-int", lambda v: v.update(api_present=1))
    reject("resource-name-as-int", lambda v: v.update(resource_name=1))
    reject("resource-absolute-path-as-null", lambda v: v.update(resource_absolute_path=None))
    reject("empty-resource-path", lambda v: v.update(resource_path=""))
    reject("resource-path-as-int", lambda v: v.update(resource_path=1))
    reject("resource-path-oversize", lambda v: v.update(resource_path="x"*2049))
    reject("module-open-not-requested", lambda v: v.update(module_open_requested=False))
    reject("module-open-not-accepted", lambda v: v.update(module_open_accepted=False))
    reject("module-open-requested-as-int", lambda v: v.update(module_open_requested=1))
    reject("module-open-accepted-as-int", lambda v: v.update(module_open_accepted=1))
    for case_id, name in (("completion-load-not-requested", "load_requested"), ("completion-load-not-submitted", "load_submitted"),
                          ("completion-load-not-entered", "load_entered"), ("completion-load-not-resumed", "load_resumed"),
                          ("completion-load-not-returned", "load_returned")):
        reject(case_id, lambda v, name=name: v.update({name:0}))
    reject("completion-load-not-accepted", lambda v: v.update(load_accepted=False))
    reject("completion-load-accepted-as-int", lambda v: v.update(load_accepted=1))
    wire = copy.deepcopy(original)
    for name in WIRE_BOOLS:
        wire[name] = int(wire[name])
    before = copy.deepcopy(wire)
    normalized, codec = normalize_wire_response(wire)
    require(wire == before and normalized == original and codec["numeric_boolean_fields"] == list(WIRE_BOOLS), "Wire decode mutated raw data or lost exact booleans")
    cases.append({"id":"wire-complete-bool01-native-paths","status":"passed"})
    pending = copy.deepcopy(wire)
    pending.update(executed=0,event_count=0,checks=0,checksum=0,status="pending")
    pending.pop("caseIds"); pending.pop("rows")
    decoded, codec = normalize_wire_response(pending)
    require(decoded["rows"] == [] and decoded["caseIds"] == [] and codec["omitted_empty_arrays"] == ["caseIds","rows"], "Known-empty wire decode differs")
    cases.append({"id":"wire-known-empty-arrays","status":"passed"})
    partial = copy.deepcopy(wire); partial["executed"] = 0; partial["status"] = "ready"; partial.pop("caseIds")
    decoded, codec = normalize_wire_response(partial)
    require(decoded["rows"] == rows and decoded["caseIds"] == [], "Partial trace empty case list decode differs")
    cases.append({"id":"wire-partial-rows-empty-cases","status":"passed"})
    for case_id, status in (("wire-pending-absent-resource-and-editor", "pending"),
                            ("wire-unavailable-absent-resource-and-editor", "unavailable")):
        absent = copy.deepcopy(pending)
        absent.update(status=status, resource_name="", resource_path="", resource_absolute_path="",
                      resource_name_resolved=0, module_present=0, api_present=0,
                      module_open_requested=0, module_open_accepted=0, load_accepted=0)
        absent.update({name:0 for name in LOAD_COUNTERS})
        decoded, _ = normalize_wire_response(absent)
        require(decoded["status"] == status and all(decoded[name] is False for name in
                ("resource_name_resolved", "module_present", "api_present", "module_open_requested", "module_open_accepted", "load_accepted")),
                "Absent diagnostic state became ready")
        cases.append({"id":case_id,"status":"passed"})
    def reject_wire(name, change, base=wire):
        value = copy.deepcopy(base)
        change(value)
        try:
            normalize_wire_response(value)
        except mod.Failure as exc:
            cases.append({"id":name,"status":"rejected","diagnostic":str(exc)})
        else:
            require(False,"Wire fault accepted: "+name)
    reject_wire("wire-bool-string", lambda v:v.update(world_matches="1"))
    reject_wire("wire-bool-float", lambda v:v.update(world_matches=1.0))
    reject_wire("wire-bool-two", lambda v:v.update(world_matches=2))
    reject_wire("wire-complete-missing-cases", lambda v:v.pop("caseIds"))
    reject_wire("wire-complete-missing-rows", lambda v:v.pop("rows"))
    reject_wire("wire-partial-missing-nonempty-rows", lambda v:v.pop("rows"),partial)
    reject_wire("wire-unknown-field", lambda v:v.update(extra=0))
    reject_wire("wire-boolean-counter", lambda v:v.update(executed=False))
    reject_wire("wire-incomplete-counter", lambda v:v.pop("event_count"))
    reject_wire("wire-row-count-mismatch", lambda v:v.update(event_count=24))
    reject_wire("wire-missing-resource-name", lambda v:v.pop("resource_name"))
    reject_wire("wire-resource-name-string-type", lambda v:v.update(resource_name=1))
    reject_wire("wire-resource-absolute-path-string-type", lambda v:v.update(resource_absolute_path=None))
    reject_wire("wire-resource-name-resolved-bool-two", lambda v:v.update(resource_name_resolved=2))
    reject_wire("wire-module-bool-string", lambda v:v.update(module_present="1"))
    reject_wire("wire-api-bool-float", lambda v:v.update(api_present=1.0))
    reject_wire("wire-missing-resource-path", lambda v:v.pop("resource_path"))
    reject_wire("wire-resource-path-string-type", lambda v:v.update(resource_path=1))
    reject_wire("wire-resource-path-string-oversize", lambda v:v.update(resource_path="x"*2049))
    reject_wire("wire-missing-module-open-requested", lambda v:v.pop("module_open_requested"))
    reject_wire("wire-missing-module-open-accepted", lambda v:v.pop("module_open_accepted"))
    reject_wire("wire-module-open-requested-string", lambda v:v.update(module_open_requested="1"))
    reject_wire("wire-module-open-requested-float", lambda v:v.update(module_open_requested=1.0))
    reject_wire("wire-module-open-requested-two", lambda v:v.update(module_open_requested=2))
    reject_wire("wire-module-open-accepted-string", lambda v:v.update(module_open_accepted="1"))
    reject_wire("wire-module-open-accepted-float", lambda v:v.update(module_open_accepted=1.0))
    reject_wire("wire-module-open-accepted-two", lambda v:v.update(module_open_accepted=2))
    for case_id, name in (("wire-missing-load-requested", "load_requested"), ("wire-missing-load-submitted", "load_submitted"),
                          ("wire-missing-load-entered", "load_entered"), ("wire-missing-load-resumed", "load_resumed"),
                          ("wire-missing-load-returned", "load_returned"), ("wire-missing-load-accepted", "load_accepted")):
        reject_wire(case_id, lambda v, name=name:v.pop(name))
    for case_id, name in (("wire-load-requested-bool", "load_requested"), ("wire-load-submitted-bool", "load_submitted"),
                          ("wire-load-entered-bool", "load_entered"), ("wire-load-resumed-bool", "load_resumed"), ("wire-load-returned-bool", "load_returned")):
        reject_wire(case_id, lambda v, name=name:v.update({name:True}))
    reject_wire("wire-load-counter-float", lambda v:v.update(load_requested=1.0))
    reject_wire("wire-load-counter-string", lambda v:v.update(load_requested="1"))
    reject_wire("wire-load-counter-two", lambda v:v.update(load_requested=2))
    reject_wire("wire-load-accepted-string", lambda v:v.update(load_accepted="1"))
    reject_wire("wire-load-accepted-float", lambda v:v.update(load_accepted=1.0))
    reject_wire("wire-load-accepted-two", lambda v:v.update(load_accepted=2))
    def load_snapshot(counters, accepted=0, status="pending"):
        value = copy.deepcopy(pending)
        value.update(zip(LOAD_COUNTERS,counters))
        value.update(load_accepted=accepted, status=status)
        return value
    cold = load_snapshot((0,0,0,0,0))
    submitted = load_snapshot((1,1,0,0,0))
    entered_first = load_snapshot((1,0,1,0,0))
    resumed = load_snapshot((1,1,1,1,0))
    refused = load_snapshot((1,1,1,1,1),status="unavailable")
    for case_id, value in (("wire-load-cold",cold),("wire-load-submitted-before-entry",submitted),
                           ("wire-load-entered-before-submit",entered_first),("wire-load-resumed-prefix",resumed),
                           ("wire-load-returned-refused",refused)):
        before = copy.deepcopy(value)
        decoded, _ = normalize_wire_response(value)
        require(value == before and decoded["load_accepted"] is False, "Prefix/refusal changed or became accepted")
        cases.append({"id":case_id,"status":"passed"})
    for case_id, counters, accepted in (
            ("wire-load-submitted-without-request",(0,1,0,0,0),0), ("wire-load-entered-without-request",(0,0,1,0,0),0),
            ("wire-load-resumed-without-entry",(1,1,0,1,0),0), ("wire-load-resumed-without-submit",(1,0,1,1,0),0),
            ("wire-load-returned-without-resume",(1,1,1,0,1),0), ("wire-load-accepted-before-return",(1,1,1,1,0),1)):
        reject_wire(case_id, lambda v:None, load_snapshot(counters,accepted))
    complete_load = load_snapshot((1,1,1,1,1),1)
    for case_id, stream in (("progress-delayed-entry",(cold,submitted,resumed,complete_load)),
                            ("progress-immediate-entry",(cold,entered_first,resumed,complete_load))):
        previous = None
        for value in stream:
            decoded, _ = normalize_wire_response(value)
            validate_load_progress(decoded, previous)
            previous = decoded
        cases.append({"id":case_id,"status":"passed"})
    for case_id, current, prior in (("progress-reset-all",cold,complete_load), ("progress-reset-accepted",refused,complete_load),
                                   ("progress-stale-token",{**complete_load,"token":"b"*64},complete_load)):
        decoded, _ = normalize_wire_response(current)
        previous, _ = normalize_wire_response(prior)
        try:
            validate_load_progress(decoded, previous)
        except mod.Failure as exc:
            require(exc.status == "stale_input", "Wrong stale load-state outcome")
            cases.append({"id":case_id,"status":"rejected","diagnostic":str(exc),"outcome":exc.status})
        else:
            require(False,"Stale load progress accepted: "+case_id)
    for case_id, counters in (("wire-ready-load-not-requested",(0,0,0,0,0)), ("wire-ready-load-not-submitted",(1,0,1,0,0)),
                              ("wire-ready-load-not-entered",(1,1,0,0,0)), ("wire-ready-load-not-resumed",(1,1,1,0,0)),
                              ("wire-ready-load-not-returned",(1,1,1,1,0)), ("wire-ready-load-refused",(1,1,1,1,1))):
        reject_wire(case_id, lambda v:None, load_snapshot(counters,status="ready"))
    binding = {"sha256":"e"*64,"version":"fixture.engine"}
    plugin_files = {name:"f"*64 for name in COMPILE_TOOLS}
    compiled = {"schema_version":1,"stage":"workbench_compile","status":"success","engine_sha256":binding["sha256"],
                "engine_version":binding["version"],"tools":plugin_files,"result":{"Stage":"Compiled","Ok":True,"ExitCode":0,"ErrorCount":0}}
    def classified(value):
        record = {"attempts":{"source_generation":{},"engine_compilation":{},"engine_runtime":{}},"commands":[],
                  "raw_results":{"compile":{"result":value}},"scope":{"engine_compilation":"not_run"},
                  "expected_compile_binding":binding,"plugin_file_set":plugin_files}
        classify_attempts(record)
        require(record["attempts"]["engine_compilation"]["target_compile"] == record["scope"]["engine_compilation"], "Compile scope/outcome differ")
        return record["scope"]["engine_compilation"]
    require(classified(compiled) == "executed_success", "Exact compile evidence not admitted")
    cases.append({"id":"compile-evidence-valid","status":"passed"})
    for case_id, path, replacement, expected in (
            ("compile-evidence-errors",("result","ErrorCount"),1,"executed_failure"),
            ("compile-evidence-outer-failure",("status",),"failure","executed_unverified"),
            ("compile-evidence-schema-bool",("schema_version",),True,"executed_unverified"),
            ("compile-evidence-errorcount-bool",("result","ErrorCount"),False,"executed_unverified"),
            ("compile-evidence-exit-bool",("result","ExitCode"),False,"executed_unverified"),
            ("compile-evidence-wrong-tools",("tools",),{},"executed_unverified"),
            ("compile-evidence-wrong-engine",("engine_sha256",),"0"*64,"executed_unverified")):
        value = copy.deepcopy(compiled)
        target = value
        for key in path[:-1]:target = target[key]
        target[path[-1]] = replacement
        require(classified(value) == expected and mod.canonical(value) != mod.canonical(compiled), "Rejected compile evidence became successful")
        cases.append({"id":case_id,"status":"rejected","outcome":expected})
    completed_case_ids = [case["id"] for case in cases]
    require(completed_case_ids == expected_case_ids, "Synthetic receipt has missing, duplicate or reordered cases")
    work = Path(tempfile.mkdtemp(prefix="component-callback-receipt-tests-",dir=ROOT/"build"))
    receipt = {"schema_version":1,"operation":"component.callback.receipt.self_test","status":"success",
               "scope":"synthetic complete receipt and deliberate malformed/state/order mutants only",
               "expected_case_ids":expected_case_ids,"completed_case_ids":completed_case_ids,"complete_expected_case_set":True,
               "cases":cases,"case_count":len(cases),"synthetic_trace":result,"verifier":identity(Path(__file__)),
               "compiler_execution":"not_run","engine_execution":"not_run","callback_delivery":"not_run"}
    save_result(work/"result.json",receipt)
    print(str(work/"result.json"))


def world_fixture_self_test():
    """Passive source-format gates, separate from the 124/50 trace gates."""
    expected = ("world.legacy-default", "world.layered-two-files", "world.metadata-preserved",
                "world.prefab-preserved", "world.legacy-eight", "world.layered-nine-directories",
                "world.missing-layer", "world.extra-input", "world.legacy-rejects-layer",
                "world.unknown-profile", "world.boolean-profile", "world.legacy-token-compatible",
                "world.profile-token-distinct", "world.token-contract-required", "world.contract-mutation",
                "world.mutated-template", "world.rendered-handlers-unchanged", "world.source-only-basis")
    work = Path(tempfile.mkdtemp(prefix="callback-world-fixture-tests-", dir=ROOT / "build"))
    layered, proof, guard, inputs = world_fixture_basis("source-layered-v1")
    legacy = world_fixture_sources()
    selected = world_fixture_sources("source-layered-v1", layered)
    generated_path = "scripts/Game/Beryl/Beryl_Generated.c"
    eight = {name: "a" * 64 for name in ("addon.gproj", generated_path, "scripts/Game/SPK_BerylCallbackObserver.c",
        "scripts/WorkbenchGameCommon/BerylComponentCallbacks.c", *legacy)}
    nine = {**eight, REL_LAYER: mod.digest(selected[REL_LAYER])}
    token_input = {"scenario": "inert", "fixture": {"sample": "f" * 64}}
    config = {"components": [{"instance": {"name": "FixtureComponent"}}]}
    mapping = {"linkage_schema_version": 1, "linkage": [{"declaration": "sparkos.component_callback_probe.State",
        "kind": "struct", "class": "FixtureState", "fields": [{"source": key, "name": key} for key in (
            "ready", "init_count", "frame_count", "delete_count", "elapsed")]}]}
    generated = b"class FixtureComponent : ScriptComponent { protected ref FixtureState m_BerylState = new FixtureState(); }"
    cases = []
    negative = {"world.missing-layer", "world.extra-input", "world.legacy-rejects-layer", "world.unknown-profile",
                "world.boolean-profile", "world.token-contract-required", "world.contract-mutation", "world.mutated-template"}
    for case_id in expected:
        try:
            if case_id == "world.legacy-default":
                require(set(legacy) == {REL_WORLD, REL_WORLD + ".meta", "Prefabs/BerylCallbackProbe.et",
                    "Prefabs/BerylCallbackProbe.et.meta"} and world_fixture_basis("legacy") == (None, None, None, []),
                    "Legacy fixture default changed")
            elif case_id == "world.layered-two-files":
                require(selected[REL_WORLD] == layered.WORLD_BYTES and selected[REL_LAYER] == layered.LAYER_BYTES,
                        "Layered format differs")
            elif case_id == "world.metadata-preserved":
                require(selected[REL_WORLD + ".meta"] == legacy[REL_WORLD + ".meta"], "Stable world metadata changed")
            elif case_id == "world.prefab-preserved":
                require(all(selected[name] == legacy[name] for name in ("Prefabs/BerylCallbackProbe.et", "Prefabs/BerylCallbackProbe.et.meta")),
                        "Prefab inputs changed")
            elif case_id == "world.legacy-eight":
                admitted_stage(eight, generated_path)
            elif case_id == "world.layered-nine-directories":
                admitted_stage(nine, generated_path, "source-layered-v1")
                require("worlds/BerylCallbackProbe_Layers" in parent_directories(nine), "Layer directory omitted")
            elif case_id == "world.missing-layer":
                admitted_stage(eight, generated_path, "source-layered-v1")
            elif case_id == "world.extra-input":
                admitted_stage({**nine, "foreign.txt": "b" * 64}, generated_path, "source-layered-v1")
            elif case_id == "world.legacy-rejects-layer":
                admitted_stage(nine, generated_path)
            elif case_id == "world.unknown-profile":
                world_fixture_sources("unregistered")
            elif case_id == "world.boolean-profile":
                world_fixture_sources(True)
            elif case_id == "world.legacy-token-compatible":
                require(fixture_token(token_input) == mod.digest(mod.canonical(token_input)), "Legacy token identity changed")
            elif case_id == "world.profile-token-distinct":
                require(fixture_token(token_input) != fixture_token(token_input, "source-layered-v1", proof), "Profile omitted from token")
            elif case_id == "world.token-contract-required":
                fixture_token(token_input, "source-layered-v1", {**proof, "source_contract_sha256": "b" * 64})
            elif case_id == "world.contract-mutation":
                layered.validate_contract({**proof["source_contract"], "engine_loaded": True})
            elif case_id == "world.mutated-template":
                class Inert:
                    FORMAT = "source-layered-v1"
                    PACKAGE = work / "mutated-package"
                    WORLD_BYTES = layered.WORLD_BYTES
                    LAYER_BYTES = layered.LAYER_BYTES
                write(Inert.PACKAGE / REL_WORLD, b"foreign source")
                write(Inert.PACKAGE / REL_LAYER, layered.LAYER_BYTES)
                world_fixture_sources("source-layered-v1", Inert)
            elif case_id == "world.rendered-handlers-unchanged":
                old, _ = renderer(config, mapping, "a" * 64, work / "addon", generated)
                new, _ = renderer(config, mapping, "a" * 64, work / "addon", generated, "source-layered-v1", layered)
                require(all(old[name] == new[name] for name in old if name != REL_WORLD) and set(new) == set(old) | {REL_LAYER},
                        "Layer selection changed callback/scalar/prefab sources")
            elif case_id == "world.source-only-basis":
                require(proof["engine_authored_serialization"] == "not_run" and
                        proof["source_contract"]["source_basis"]["whole_archive_sha256"] is None and len(inputs) == 9,
                        "Layered source scope/dependency set changed")
                guard()
            require(case_id not in negative, "Malformed world fixture was admitted")
            cases.append({"id": case_id, "status": "passed", "outcome": "return"})
        except mod.Failure as exc:
            require(case_id in negative and exc.status == "stale_input", "Unexpected world-fixture failure: " + str(exc))
            cases.append({"id": case_id, "status": "rejected", "outcome": exc.status, "diagnostic": str(exc)})
    require([case["id"] for case in cases] == list(expected), "Incomplete world-fixture checks")
    save_result(work / "result.json", {"schema_version": 1, "operation": "component.callback.world-fixture.self_test",
        "status": "success", "expected_case_ids": list(expected), "completed_case_ids": [case["id"] for case in cases],
        "complete_expected_case_set": True, "cases": cases, "case_count": len(cases), "verifier": identity(Path(__file__)),
        "scope": "passive world-source staging/profile checks only", "compiler_execution": "not_run",
        "powershell_execution": "not_run", "engine_execution": "not_run", "callback_delivery": "not_run"})
    print(str(work / "result.json"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--beryl", type=Path, required=True)
    parser.add_argument("--expect-compiler-sha256", required=True)
    parser.add_argument("--workbench-tools", type=Path, required=True)
    parser.add_argument("--powershell-host", type=Path)
    parser.add_argument("--engine-exe", type=Path)
    parser.add_argument("--world-fixture", choices=WORLD_FIXTURES, default="legacy")
    parser.add_argument("--engine-updates", choices=ENGINE_UPDATES, default="focus-dependent")
    parser.add_argument("--frame-diagnostics", choices=FRAME_DIAGNOSTICS, default="off")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare-only", action="store_true")
    mode.add_argument("--engine-stage", choices=("compile", "runtime"))
    args = parser.parse_args()
    compiler = args.beryl.resolve(strict=True)
    require(compiler.is_relative_to(ROOT / "build") and compiler.parent != ROOT / "build",
            "Explicit private compiler candidate under build is required; active compiler is forbidden")
    require(HASH.fullmatch(args.expect_compiler_sha256) and mod.digest(mod.read(compiler)) == args.expect_compiler_sha256,
            "Selected compiler identity differs; nothing executed", "stale_input")
    toolroot = args.workbench_tools.resolve(strict=True)
    host = args.powershell_host.resolve(strict=True) if args.powershell_host else None
    engine = args.engine_exe.resolve(strict=True) if args.engine_exe else None
    if args.engine_stage:
        require(host is not None and engine is not None, "Engine stages require explicit --powershell-host and --engine-exe", "unavailable")
    work = Path(tempfile.mkdtemp(prefix="component callbacks & spaces-", dir=ROOT / "build"))
    record = {"schema_version": 1, "operation": "verify.component_callbacks.runtime", "status": "failure",
              "stage": "prepare", "world_fixture": args.world_fixture, "engine_updates": args.engine_updates,
              "frame_diagnostics": args.frame_diagnostics,
              "expected_case_ids": list(CASE_IDS), "commands": [], "raw_results": {},
              "scope": {"source_generation": "not_run", "engine_compilation": "not_run", "engine_runtime_callbacks": "not_run",
                        "engine_callback_delivery": "not_run", "tablet_service_connection": "not_run", "native_program": "not_run",
                        "component_runtime_state": "not_run", "component_construction": "not_run", "component_world_lifetime": "unverified",
                        "installation": "unchanged", "policy_changes": "not_run"},
              "limitation": "Bounded scalar generated components on two fixture entities only; no tablet services, full teardown lifetime, multiplayer or performance proof."}
    record["attempts"] = {
        "source_generation": {"requested": True, "adapter_invocation_attempted": False, "process_outcome": "not_run"},
        "engine_compilation": {"requested": bool(args.engine_stage), "adapter_invocation_attempted": False,
                               "process_outcome": "not_run", "adapter_status": None, "target_compile": "not_run"},
        "engine_runtime": {"requested": args.engine_stage == "runtime", "adapter_invocation_attempted": False,
                           "process_outcome": "not_run", "adapter_status": None, "owned_session_recorded": False,
                           "spawn_rpc_attempted": False, "callback_observations": "not_run"}}
    outer, staged, staged_dirs, tracked, unchanged = None, None, None, {}, None
    print("Component-callback evidence: " + str(work), flush=True)
    try:
        contract_basis, contract_inputs = basis()
        update_proof, update_inputs = engine_update_basis(args.engine_updates)
        frame_proof, frame_inputs = frame_diagnostic_basis(args.frame_diagnostics)
        record["frame_diagnostic_basis"] = frame_proof
        record["engine_update_basis"] = update_proof
        record["contract_basis"] = contract_basis
        record["probe_profile"] = "real-engine-callbacks.flat-bool-i32-f32.v1"
        package_files = files(PACKAGE)
        layered, world_proof, primary_guard, world_inputs = world_fixture_basis(args.world_fixture)
        if world_proof is not None:
            record["world_fixture_basis"] = world_proof
            record["scope"].update(world_format=args.world_fixture, engine_authored_serialization="not_run")
        plugin = sorted((toolroot / "scripts").glob("*.ps1"))
        require({"Find-Workbench.ps1", "Invoke-ReforgerBuild.ps1", "Invoke-Workbench.ps1", "Get-WorkbenchErrors.ps1",
                 "Start-WorkbenchDaemon.ps1", "Invoke-WorkbenchRpc.ps1"}.issubset({path.name for path in plugin}),
                "Required installed integration scripts are missing", "unavailable")
        inputs = [("compiler/compiler.input", compiler), ("python/python.input", Path(sys.executable).resolve()),
                  ("verifier/verify-component-callbacks.py", Path(__file__).resolve())]
        inputs += [("fixture/" + name, PACKAGE / name) for name in package_files]
        inputs += contract_inputs
        inputs += world_inputs
        inputs += update_inputs
        inputs += frame_inputs
        inputs += [("verifier/" + path.name, path) for path in (TRANSPORT, ROOT / "scripts/verify-component-engine.py")]
        inputs += [("tools/" + path.relative_to(ROOT).as_posix(), path) for path in mod.bundle_paths()]
        inputs += [("plugin/scripts/" + path.name, path) for path in plugin]
        if host:
            inputs.append(("host/powershell.input", host))
        # Executable bytes are retained as passive .input data and never launched
        # from the evidence directory. Only explicit original paths are invoked.
        for relative, path in inputs:
            require(path.is_file() and not path.is_symlink(), "Verification input is not an admitted regular file: " + str(path))
            item = identity(path)
            write(work / "inputs" / relative, mod.read(path))
            require(mod.digest(mod.read(work / "inputs" / relative)) == item["sha256"], "Retained input differs", "stale_input")
            tracked[str(path)] = item
        # Engine executables exceed the mod-tool per-file bound; retain a streamed
        # fingerprint and original path instead of copying an executable.
        if engine:
            record["engine_input"] = streamed_identity(engine)
        record["verification_inputs"] = tracked
        record["fixture_file_set"] = package_files
        record["plugin_file_set"] = {path.name: tracked[str(path)]["sha256"] for path in plugin}
        project = work / "project"
        project.mkdir()
        for name in ("beryl.mod.json", "src/state.be"):
            write(project / name, mod.read(PACKAGE / name))
        outer = mod.Job(project, "component-callback-probe", compiler)
        config, frozen_inputs, hashes = outer.snapshot()
        record["expected_compile_binding"] = copy.deepcopy(config["binding"])
        record["frozen_project_inputs"] = hashes
        if engine:
            require(record["engine_input"]["sha256"] == config["binding"]["sha256"], "Engine differs from admitted binding", "stale_input")
        with source_tool_environment():
            record["attempts"]["source_generation"]["adapter_invocation_attempted"] = True
            try:
                raw = outer.run([compiler, "mod", "build", "--project", project], "component_source_build", work, timeout=120)
            except mod.Failure as exc:
                log = outer.result["raw_logs"][-1] if outer.result["raw_logs"] else None
                if log and Path(log["stdout"]).is_file():
                    try:
                        failed = mod.parse(mod.read(Path(log["stdout"])))
                    except (ValueError, mod.Failure):
                        failed = None
                    if type(failed) is dict:
                        record["source_build_result"] = failed
                        raise failed_adapter(exc, failed) from exc
                raise
        result = mod.parse(raw)
        record["source_build_result"] = result
        require(result.get("status") == "success" and result.get("compiler_sha256") == args.expect_compiler_sha256 and
                result.get("tool_sha256") == outer.result["tool_sha256"] and result.get("source_sha256") == outer.result["source_sha256"],
                "Source build lacks matching compiler/tool/input evidence", "stale_input")
        require(type(result.get("artifact_id")) is str and re.fullmatch(r"[0-9a-f]{32}", result["artifact_id"]), "Source build lacks artifact identity")
        original, artifact = mod.load_artifact(outer, result["artifact_id"])
        require(artifact["artifact_sha256"] == result.get("artifact_sha256"), "Source result/artifact identity differs", "stale_input")
        retained = work / "original-artifact"
        shutil.copytree(original, retained)
        require(files(retained) == files(original) and directories(retained) == directories(original), "Original artifact retention differs", "stale_input")
        record["original_artifact"] = {"path": str(original), "retained": str(retained), "files": files(retained),
                                       "directories": directories(retained), "artifact_sha256": artifact["artifact_sha256"]}
        child_result = Path(result["result_path"])
        require(child_result.is_relative_to(project / ".beryl-mod/jobs"), "Child result path escaped owned project", "stale_input")
        shutil.copytree(child_result.parent, work / "source-build-job")
        require(files(child_result.parent) == files(work / "source-build-job"), "Source job receipt retention differs", "stale_input")
        mapping = mod.parse(mod.read(retained / "source-map.json"))
        token_inputs = {"scenario": "probe.component.callback_delivery", "operation_id": outer.id,
                    "artifact": artifact["artifact_sha256"], "fixture": package_files, "contracts": contract_basis,
                    "tool": outer.result["tool_sha256"], "plugin": record["plugin_file_set"]}
        record["engine_update_expected_launch"] = engine_update_profile(args.engine_updates, str(work / "probe-addon"))
        token_inputs["engine_updates"] = {"profile": record["engine_update_expected_launch"], "primary_basis": update_proof}
        token_inputs["frame_diagnostics"] = {"profile": args.frame_diagnostics, "primary_basis": frame_proof,
                                             "transport_sha256": tracked[str(TRANSPORT)]["sha256"]}
        token = fixture_token(token_inputs, args.world_fixture, world_proof)
        addon = work / "probe-addon"
        shutil.copytree(retained / "addon", addon)
        require(files(addon) == artifact["files"] and directories(addon) == parent_directories(artifact["files"]),
                "Copied generated addon differs from immutable artifact", "stale_input")
        generated, generated_path = generated_source(addon, artifact, mapping)
        record["generated_source_path"] = generated_path
        additions, symbols = renderer(config, mapping, token, addon, generated, args.world_fixture, layered, args.frame_diagnostics)
        for name, source in additions.items():
            target = addon / name
            require(not target.exists(), "Trusted callback fixture collides with generated output: " + name)
            write(target, source)
        staged = {**artifact["files"], **{name: mod.digest(data) for name,data in additions.items()}}
        admitted_diagnostic_stage(staged, generated_path, args.world_fixture, args.frame_diagnostics)
        staged_dirs = parent_directories(staged)
        require(files(addon) == staged and directories(addon) == staged_dirs,
                "Prepared addon differs from exact generated artifact and trusted fixture", "stale_input")
        record.update(token=token, symbols=symbols, candidate_path=str(addon), staged_file_set=staged,
                      staged_directory_set=staged_dirs, staged_sha256=mod.digest(mod.canonical(staged)),
                      float_comparison="target rounded f32 equality; no bitwise serialization claim")
        record["scope"]["source_generation"] = "executed_success"

        def unchanged():
            outer.unchanged(hashes)
            require(files(PACKAGE) == package_files, "Fixture source set changed", "stale_input")
            if primary_guard is not None:
                primary_guard()
                require(files(layered.PACKAGE) == world_proof["source_package"],
                        "Layered source package changed", "stale_input")
            require(sorted(path.name for path in (toolroot / "scripts").glob("*.ps1")) == [path.name for path in plugin], "Plugin file set changed", "stale_input")
            for path, item in tracked.items():
                require(identity(Path(path)) == item, "Verification input changed: " + path, "stale_input")
            if engine:
                require(streamed_identity(engine) == record["engine_input"], "Engine binary changed", "stale_input")
            require(files(original) == record["original_artifact"]["files"] and files(retained) == record["original_artifact"]["files"],
                    "Original artifact changed", "stale_input")
            require(directories(original) == record["original_artifact"]["directories"] and
                    directories(retained) == record["original_artifact"]["directories"], "Original artifact directory set changed", "stale_input")
            actual = files(addon)
            derived = {}
            if "resourceDatabase.rdb" not in staged and "resourceDatabase.rdb" in actual:
                path = addon / "resourceDatabase.rdb"
                require(path.stat().st_size <= 8 * 1024 * 1024,
                        "Engine root resource-cache output exceeds fixture bound", "unavailable")
                derived["resourceDatabase.rdb"] = identity(path)
                del actual["resourceDatabase.rdb"]
            require(actual == staged and directories(addon) == staged_dirs,
                    "Staged source/gproj/file or directory set changed", "stale_input")
            admitted_diagnostic_stage(actual, generated_path, args.world_fixture, args.frame_diagnostics)
            record["engine_derived_outputs"] = derived

        unchanged()
        if not args.prepare_only:
            record["stage"] = "engine_compile"
            record["attempts"]["engine_compilation"].update(adapter_invocation_attempted=True, target_compile="attempted_unconfirmed")
            record["scope"]["engine_compilation"] = "attempted_unconfirmed"
            compile_path = work / "engine-compile.json"
            try:
                outer.run([host, "-NoProfile", "-File", mod.HERE / "engine-compile.ps1", "-ToolRoot", toolroot,
                           "-ProjectDir", addon, "-ResultPath", compile_path, "-ExpectedVersion", config["binding"]["version"]],
                          "component_engine_compile", work, timeout=300)
            except mod.Failure as exc:
                capture_adapter(record, "compile", compile_path)
                raise failed_adapter(exc, record["raw_results"].get("compile", {}).get("result")) from exc
            finally:
                if "compile" not in record["raw_results"]:
                    capture_adapter(record, "compile", compile_path)
            compiled = record["raw_results"].get("compile", {}).get("result", {})
            detail = compiled.get("result", {})
            require(type(compiled.get("schema_version")) is int and compiled["schema_version"] == 1 and compiled.get("stage") == "workbench_compile" and
                    compiled.get("status") == "success" and type(detail) is dict and detail.get("Ok") is True and
                    detail.get("Stage") == "Compiled" and type(detail.get("ExitCode")) is int and detail["ExitCode"] == 0 and
                    type(detail.get("ErrorCount")) is int and detail["ErrorCount"] == 0 and
                    compiled.get("tools") == {name: record["plugin_file_set"][name] for name in COMPILE_TOOLS},
                    "Missing successful engine compilation evidence")
            require(compiled.get("engine_version") == config["binding"]["version"] and
                    compiled.get("engine_sha256") == config["binding"]["sha256"], "Compiled engine identity differs", "stale_input")
            record["scope"]["engine_compilation"] = "executed_success"
            unchanged()
            if args.engine_stage == "runtime":
                record["stage"] = "engine_callback_delivery"
                record["attempts"]["engine_runtime"]["adapter_invocation_attempted"] = True
                runtime_path = work / "engine-runtime.json"
                try:
                    outer.run([host, "-NoProfile", "-File", TRANSPORT, "-ToolRoot", toolroot,
                               "-ProjectDir", addon, "-ProjectId", config["addon"]["id"], "-ResultPath", runtime_path,
                               "-Token", token, "-Function", FUNCTION, "-ExpectedEngineHash", config["binding"]["sha256"],
                               "-ExpectedEngineVersion", config["binding"]["version"], "-EngineUpdates", args.engine_updates,
                               "-FrameDiagnostics", args.frame_diagnostics],
                              "component_runtime_callbacks", work, timeout=240)
                except mod.Failure as exc:
                    capture_adapter(record, "runtime", runtime_path)
                    raise failed_adapter(exc, record["raw_results"].get("runtime", {}).get("result")) from exc
                finally:
                    if "runtime" not in record["raw_results"]:
                        capture_adapter(record, "runtime", runtime_path)
                runtime = record["raw_results"].get("runtime", {}).get("result", {})
                record["engine_update_comparison"] = validate_engine_updates(runtime, args.engine_updates, str(addon), str(engine))
                validate_runtime_envelope(runtime, token, str(addon), config["addon"]["id"], str(engine),
                                          config["binding"], record["plugin_file_set"])
                require(runtime.get("schema_version") == 1 and runtime.get("stage") == "callback_transport_complete" and
                        runtime.get("status") == "success" and runtime.get("engine_sha256") == config["binding"]["sha256"] and
                        runtime.get("engine_version") == config["binding"]["version"] and runtime.get("token") == token and
                        runtime.get("function") == FUNCTION and runtime.get("tools") == {name: record["plugin_file_set"][name]
                        for name in ("Find-Workbench.ps1","Start-WorkbenchDaemon.ps1","Invoke-WorkbenchRpc.ps1")},
                        "Missing exact successful owned callback transport evidence")
                session, loaded = runtime.get("session"), runtime.get("loaded_projects")
                require(type(session) is dict and session.get("reused") is False and session.get("project") == str(addon) and
                        type(session.get("process_id")) is int and session["process_id"] > 0 and
                        type(session.get("start_ticks")) is int and session["start_ticks"] > 0 and
                        session.get("executable", "").replace("\\", "/").casefold() == str(engine).replace("\\", "/").casefold() and
                        type(loaded) is dict and loaded.get("Ok") is True and loaded.get("Function") == "GetLoadedProjects" and
                        type(loaded.get("Response")) is dict and type(loaded["Response"].get("Loaded Projects")) is list and
                        config["addon"]["id"] in loaded["Response"]["Loaded Projects"] and
                        runtime.get("cleanup") in ("owned_process_stopped", "owned_process_already_exited") and
                        not runtime.get("evidence_errors") and runtime.get("raw_logs"),
                        "Missing exact owned session, successful cleanup or raw callback logs")
                stages = runtime.get("stages")
                require(type(stages) is list and [item.get("action") for item in stages] == ["load","play","spawn","delete","stop"] and
                        all(item.get("status") == "completed" for item in stages) and
                        stages[3].get("response") == runtime.get("completion"), "Incomplete ordered world transition stages")
                calls = runtime.get("rpcs")
                require(type(calls) is list and 5 <= len(calls) <= 325, "Missing or excessive runtime RPC evidence")
                previous_load = None
                for call in calls:
                    reply = call.get("result") if type(call) is dict else None
                    require(type(reply) is dict and reply.get("Ok") is True and reply.get("Function") == FUNCTION and
                            type(reply.get("Raw")) is str and len(reply["Raw"]) <= 1024*1024 and
                            mod.parse(reply["Raw"].encode("utf-8")) == reply.get("Response"), "Parsed callback RPC differs from retained raw wire response")
                    normalized, codec = normalize_wire_response(reply["Response"])
                    validate_load_progress(normalized, previous_load)
                    previous_load = normalized
                    require(call.get("normalized_response") == normalized and call.get("codec") == codec,
                            "Stored callback wire normalization/codec differs from independent decode")
                response = runtime["completion"]
                delete_calls = [call for call in calls if call.get("stage") == "delete"]
                require(delete_calls and delete_calls[-1].get("normalized_response") == response,
                        "Completion differs from the last actual delete-stage wire receipt")
                comparison = validate_callback_response(response, token, (addon/"addon.gproj").as_posix(), (addon/"worlds/BerylCallbackProbe.ent").as_posix())
                for log in runtime["raw_logs"]:
                    require(type(log) is dict and identity(Path(log["retained"]))["sha256"] == log["sha256"] and
                            Path(log["retained"]).is_relative_to(work), "Raw callback log identity differs", "stale_input")
                write(work / "callback-trace.txt", ("\n".join(response["rows"]) + "\n").encode("ascii"))
                comparison["trace"] = identity(work / "callback-trace.txt")
                record["callback_comparison"] = comparison
                for name in ("engine_runtime_callbacks", "engine_callback_delivery", "component_runtime_state", "component_construction"):
                    record["scope"][name] = "executed_success"
                unchanged()
        record.update(status="success", stage="prepared" if args.prepare_only else record["stage"],
                      success_means="isolated source candidate prepared" if args.prepare_only else
                                    ("exact generated-component callback fixture script compilation" if args.engine_stage == "compile" else "bounded engine-delivered component callback traces match"))
    except BaseException as exc:
        status = getattr(exc, "status", "cancelled" if isinstance(exc, KeyboardInterrupt) else "failure")
        if status not in {"failure", "unavailable", "timeout", "cancelled", "stale_input"}:
            status = "failure"
        record.update(status=status, failure={"type": type(exc).__name__, "message": str(exc), "pointer": getattr(exc, "pointer", None)})
        raise
    finally:
        active_failure = sys.exc_info()[1]
        final_failure = None
        runtime_diagnostics = record["raw_results"].get("runtime", {}).get("result")
        if type(runtime_diagnostics) is dict:
            try:
                record["frame_state_comparison"] = validate_frame_diagnostics(runtime_diagnostics, args.frame_diagnostics,
                    record.get("token"), runtime_diagnostics.get("session"))
            except BaseException as exc:
                record["frame_state_evidence_failure"] = {"type": type(exc).__name__, "message": str(exc),
                                                          "status": getattr(exc, "status", "failure")}
                if active_failure is None and record["status"] == "success":
                    record["status"] = "failure"
                    final_failure = exc
        try:
            if unchanged is not None:
                unchanged()
        except BaseException as exc:
            record["final_integrity_failure"] = {"type": type(exc).__name__, "message": str(exc), "status": getattr(exc, "status", "failure")}
            final_failure = exc
            if record["status"] == "success":
                record["status"] = getattr(exc, "status", "failure") if getattr(exc, "status", "failure") in FAILURE_STATUSES else "failure"
        try:
            compiled = record["raw_results"].get("compile", {}).get("result", {})
            record["raw_engine_logs"] = retain_engine_logs(work, compiled)
            if record["status"] == "success" and not args.prepare_only:
                require(record["raw_engine_logs"], "Raw engine compilation logs unavailable", "unavailable")
            if record.get("evidence_errors") and record["status"] == "success":
                raise mod.Failure("Adapter evidence capture was incomplete")
        except BaseException as exc:
            record["final_evidence_failure"] = {"type": type(exc).__name__, "message": str(exc), "status": getattr(exc, "status", "failure")}
            final_failure = exc
            if record["status"] == "success":
                record["status"] = getattr(exc, "status", "failure") if getattr(exc, "status", "failure") in FAILURE_STATUSES else "failure"
        if outer is not None:
            record["job"] = outer.result
            record["commands"] = outer.result["raw_logs"]
            try:
                for command in record["commands"]:
                    for stream in ("stdout", "stderr"):
                        path = Path(command[stream])
                        if path.is_file():
                            command[stream + "_sha256"] = streamed_identity(path)["sha256"]
            except BaseException as exc:
                record["process_log_capture_error"] = {"type": type(exc).__name__, "message": str(exc)}
                final_failure = exc
                if record["status"] == "success":
                    record["status"] = "failure"
            outer.result.update(status=record["status"], stage=record["stage"])
            try:
                save_result(outer.path / "result.json", outer.result)
            except Exception as exc:
                record.update(status="failure", receipt_failure={"type": type(exc).__name__, "message": str(exc)})
                final_failure = exc
        classify_attempts(record)
        save_result(work / "results.json", record)
        print("Receipt: " + str(work / "results.json"), flush=True)
        if final_failure is not None and active_failure is None:
            raise mod.Failure("Final evidence retention or integrity check failed: " + str(final_failure), record["status"]) from final_failure


if __name__ == "__main__":
    if sys.argv[1:] == ["--self-test"]:
        self_test()
    elif sys.argv[1:] == ["--world-fixture-self-test"]:
        world_fixture_self_test()
    else:
        main()
