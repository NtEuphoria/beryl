#!/usr/bin/env python3
"""Observe eligibility for a future engine-authored world; never save a world.

Select an immutable prepare-only callback receipt. Copy its eight inputs into a
new owned addon, install one read-only observer, compile, and optionally observe
both editor APIs in a fresh owned session. Missing native capability is retained
as unavailable, rather than inferred from documentation or fabricated state.
"""
from pathlib import Path
import argparse
import copy
import importlib.util
import json
import re
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location("world_save_startup_foundation", ROOT / "scripts/verify-workbench-startup.py")
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
mod, bounded = base.mod, base.bounded
require, identity, write, saved, clean_path = base.require, base.identity, base.write, base.saved, base.clean_path
PACKAGE = ROOT / "packages/sparkos/workbench-world-save"
ADAPTER = ROOT / "scripts/world-save-engine.ps1"
FUNCTION = "BerylWorldSaveEligibility"
HANDLER_PATH = "scripts/WorkbenchGameCommon/BerylWorldSaveEligibility.c"
OUTPUT_REL = "engine-authored/BerylEngineAuthored.ent"
STRINGS = ("token", "action", "status", "failure", "output_path", "wb_world_path", "game_world_path")
BOOLS = ("game_present", "in_play_mode", "module_present", "wb_api_present", "wb_world_present", "wb_edit_mode", "wb_game_mode",
         "game_editor_present", "game_api_present", "game_world_present", "api_same", "world_same")
FIELDS = frozenset((*STRINGS, *BOOLS))
DOCS = {**base.DOCS,
        "interfaceGame.html": "dfcab6b926646b8b56cdcbf38bb3e5f9809e96c9e3efaabc11cf806d6ec4b22e",
        "interfaceGameWorldEditor.html": "7cc3930f097af572521b6d4caddaeb38faf963294bbd5f0a763c49291728abe6"}


def same_path(left, right):
    return type(left) is str and left.replace("\\", "/").casefold() == str(right).replace("\\", "/").casefold()


def output_absent(addon, output):
    clean_path(output)
    require(output == addon / OUTPUT_REL and output.is_absolute(), "Future output is not the fixed owned path", "stale_input")
    text = output.as_posix()
    require(text.isascii() and len(text) < 256 and not any(c in text for c in ('\x00', '\n', '\r', '"')),
            "Future engine save path is outside the bounded literal contract", "unavailable")
    require(not output.exists() and not output.parent.exists(), "Eligibility-only output namespace must remain absent", "stale_input")


def render(data, token, output):
    require(base.HASH.fullmatch(token) and output.isascii() and len(output) < 256 and
            not any(c in output for c in ('\x00', '\r', '\n')), "Invalid observer literal")
    text = data.decode("utf-8").replace("@TOKEN@", token).replace("@OUTPUT_ABSOLUTE@", output.replace("\\", "\\\\").replace('"', '\\"'))
    require(not re.search(r"@[A-Z_]+@", text), "Unresolved installed observer placeholder")
    return text.encode("utf-8")


def normalize(raw):
    require(type(raw) is dict and set(raw) == FIELDS, "Unknown or missing eligibility response fields")
    result = copy.deepcopy(raw)
    codec = {"schema_version": 1, "name": "enfusion.jsonapistruct.bool01.v1", "numeric_boolean_fields": []}
    for key in STRINGS:
        require(type(raw[key]) is str and len(raw[key]) <= 2048 and "\x00" not in raw[key], "Invalid bounded eligibility text: " + key)
    for key in BOOLS:
        val = raw[key]
        require(type(val) is bool or (type(val) is int and val in (0, 1)), "Invalid exact eligibility Boolean: " + key)
        if type(val) is int:
            result[key] = val == 1
            codec["numeric_boolean_fields"].append(key)
    require(result["status"] in ("eligible", "unavailable", "failure"), "Unknown eligibility status")
    return result, codec


def observation(value, token, output):
    require(set(value) == FIELDS and all(type(value[k]) is bool for k in BOOLS), "Eligibility response is not normalized")
    require(value["token"] == token and value["action"] == "observe" and same_path(value["output_path"], output),
            "Eligibility response identity differs", "stale_input")
    for present, prerequisite in (("wb_api_present", "module_present"), ("wb_world_present", "wb_api_present"),
            ("wb_edit_mode", "wb_api_present"), ("wb_game_mode", "wb_api_present"),
            ("game_editor_present", "game_present"), ("game_api_present", "game_editor_present"), ("game_world_present", "game_api_present")):
        require(not value[present] or value[prerequisite], "Contradictory editor presence: " + present)
    require(not value["game_editor_present"] or not value["in_play_mode"], "Game editor queried during play")
    require(not value["in_play_mode"] or value["game_present"], "Play without game context")
    require(not value["api_same"] or (value["wb_api_present"] and value["game_api_present"]), "Equality without APIs")
    require(not value["world_same"] or (value["wb_world_present"] and value["game_world_present"]), "Equality without worlds")
    require(value["wb_api_present"] or value["wb_world_path"] == "", "World path without Workbench API")
    require(value["game_api_present"] or value["game_world_path"] == "", "World path without game editor API")
    eligible = (all(value[k] for k in BOOLS if k not in ("in_play_mode", "wb_game_mode")) and
                not value["in_play_mode"] and not value["wb_game_mode"] and value["wb_world_path"] == value["game_world_path"] == "")
    require((value["status"] == "eligible") == eligible, "Eligibility status contradicts observed prerequisites")
    require((value["failure"] == "") == (value["status"] == "eligible"), "Eligibility reason/status mismatch")
    require(value["status"] != "failure", "Native observer rejected its installed request")
    return {"status": "verified_observation", "eligibility": value["status"], "world_save": "not_run",
            "world_reload": "not_run", "callback_delivery": "not_run"}


def validate_runtime(value, token, addon, engine, binding, tools, manifest_path, manifest, adapter_hash):
    """Validate eligible AND unavailable observations without changing their outcome."""
    require(type(value) is dict and type(value.get("schema_version")) is int and value["schema_version"] == 1 and
            value.get("stage") == "eligibility_complete" and value.get("status") in ("success", "unavailable") and
            value.get("function") == FUNCTION and value.get("token") == token and value.get("project_id") == base.PROJECT_ID,
            "No complete eligibility observation envelope")
    require(value.get("engine_sha256") == binding["sha256"] and value.get("engine_version") == binding["version"] and
            same_path(value.get("engine_path"), engine) and value.get("tools") == {k: tools[k] for k in base.RUNTIME_TOOLS} and
            value.get("adapter_sha256") == adapter_hash == identity(ADAPTER)["sha256"], "Eligibility tool identity differs", "stale_input")
    require(value.get("scope") == "read-only world-save eligibility observation only" and
            value.get("mechanism") == "empty_world_save_eligibility" and
            all(value.get(k) == "not_run" for k in ("callback_execution", "play", "spawn", "save", "policy_changes")),
            "Eligibility receipt omitted or claimed unexecuted operations")
    require(value.get("limits") == {"stage_ms": 30000, "rpc_ms": 8000, "total_ms": 180000, "cleanup_ms": 5000,
            "max_polls": 64, "native_launch_and_bridge_calls_not_hard_cancelled": True, "raw_logs_aggregate_bytes": 67108864} and
            all(type(value["limits"][k]) is int for k in ("stage_ms", "rpc_ms", "total_ms", "cleanup_ms", "max_polls", "raw_logs_aggregate_bytes")) and
            value["limits"]["native_launch_and_bridge_calls_not_hard_cancelled"] is True,
            "Eligibility execution bounds differ")
    require(value.get("evidence_errors") == [] and value.get("cleanup_errors") == [] and
            value.get("raw_log_observation") == "snapshot_after_confirmed_owned_exit" and
            value.get("cleanup") in ("owned_process_stopped", "owned_process_already_exited") and
            type(value.get("elapsed_ms")) is int and 0 <= value["elapsed_ms"] < 180000, "Incomplete cleanup/evidence or expired eligibility job")
    require(type(manifest) is dict and set(manifest) == {"schema_version", "files", "directories"} and
            type(manifest["schema_version"]) is int and manifest["schema_version"] == 1 and
            type(manifest["files"]) is dict and set(manifest["files"]) == base.BASE_FILES | {HANDLER_PATH} and
            manifest["directories"] == sorted(bounded.expected_directories(manifest["files"])), "Invalid exact eligibility manifest")
    require(value.get("input_manifest") == {"path": str(manifest_path), "sha256": identity(manifest_path)["sha256"]} and
            mod.canonical(value.get("staged_inputs")) == mod.canonical(manifest) and
            mod.canonical(mod.parse(mod.read(manifest_path))) == mod.canonical(manifest),
            "Eligibility input manifest differs", "stale_input")
    derived = bounded.staged_tree(addon, manifest["files"])
    outputs = value.get("engine_outputs")
    require(type(outputs) is list and len(outputs) == len(derived), "Unaccounted derived output")
    for row, actual in zip(outputs, derived):
        require(type(row) is dict and set(row) == {"path", "relative", "bytes", "sha256"} and same_path(row["path"], actual["path"]) and
                row["relative"] == actual["relative_path"] == "resourceDatabase.rdb" and type(row["bytes"]) is int and
                row["bytes"] == actual["bytes"] <= 8 * 1024 * 1024 and row["sha256"] == actual["sha256"], "Derived output identity differs")
    output = addon / OUTPUT_REL
    output_absent(addon, output)
    require(same_path(value.get("expected_output"), output), "Future output identity differs")
    session = value.get("session")
    require(type(session) is dict and type(session.get("process_id")) is int and session["process_id"] > 0 and
            type(session.get("start_ticks")) is int and session["start_ticks"] > 0 and session.get("reused") is False and
            session.get("project") == str(addon) and same_path(session.get("executable"), engine), "Owned eligibility session identity differs")
    require(value.get("arguments") == ["-gproj", str(addon / "addon.gproj"), "-noOpenLastResource", "-scriptAuthorizeAll", "-wbmodule=WorldEditor", "-run"],
            "Eligibility startup argument vector differs")
    startup = value.get("startup")
    require(type(startup) is dict and startup.get("mechanism") == "empty_world_save_eligibility" and startup.get("argv") == value["arguments"] and
            type(startup.get("working_directory")) is str and Path(startup["working_directory"]).is_absolute() and
            startup.get("use_shell_execute") is False and startup.get("create_no_window") is True and startup.get("window_style") == "Hidden" and
            startup.get("launch_returned") is True and type(startup.get("process_id")) is int and startup["process_id"] == session["process_id"] and
            type(startup.get("polls")) is int and 0 <= startup["polls"] < 64, "Recorded native launch contract differs")
    ports = value.get("port_checks")
    require(type(ports) is list and 1 <= len(ports) <= 64 and all(type(r) is dict for r in ports) and
            ports[-1].get("listening") is True and len(ports) == startup["polls"] + 1, "No owned listener readiness")
    sites, times = ["startup.identity"], []
    for row in ports:
        require(type(row) is dict and type(row.get("elapsed_ms")) is int and 0 <= row["elapsed_ms"] < value["elapsed_ms"] and
                type(row.get("listening")) is bool and ((row["listening"] and type(row.get("owning_process")) is int and
                row["owning_process"] == session["process_id"]) or (not row["listening"] and row.get("owning_process") is None)), "Foreign listener observation")
        sites.append("port.check")
        times.append(row["elapsed_ms"])
    require(times == sorted(times), "Listener observations out of order")
    calls = value.get("rpcs")
    require(type(calls) is list and all(type(r) is dict for r in calls) and
            [r.get("function") for r in calls] == ["IsWorkbenchRunning", "GetLoadedProjects", FUNCTION],
            "Eligibility RPC sequence differs; no retries or openers admitted")
    previous, result = -1, None
    for row in calls:
        function = row["function"]
        require(row.get("params") == ({"token": token, "action": "observe"} if function == FUNCTION else {}) and
                "action" in row and row["action"] == ("observe" if function == FUNCTION else None) and
                type(row.get("elapsed_ms")) is int and previous <= row["elapsed_ms"] < value["elapsed_ms"] and
                type(row.get("timeout_ms")) is int and 1 <= row["timeout_ms"] <= 8000 and
                type(row.get("duration_ms")) is int and 0 <= row["duration_ms"] < row["timeout_ms"] and
                row["elapsed_ms"] + row["duration_ms"] < value["elapsed_ms"], "Unbounded or wrong eligibility RPC")
        previous = row["elapsed_ms"]
        sites += ["before." + function, "after." + function]
        reply = row.get("result")
        require(type(reply) is dict and set(reply) == {"Ok", "Function", "ErrorCode", "Response", "Raw"} and reply["Ok"] is True and
                reply["Function"] == function and reply["ErrorCode"] == "Ok" and type(reply["Raw"]) is str and len(reply["Raw"]) <= 1024 * 1024 and
                type(reply["Response"]) is dict and mod.canonical(mod.parse(reply["Raw"].encode())) == mod.canonical(reply["Response"]), "Raw eligibility RPC differs")
        if function == "IsWorkbenchRunning":
            require(set(reply["Response"]) == {"IsRunning", "ScriptsCompiled"} and
                    all(type(v) is bool or (type(v) is int and v in (0, 1)) for v in reply["Response"].values()) and
                    all(bool(v) for v in reply["Response"].values()) and
                    mod.canonical(value.get("health")) == mod.canonical(reply), "Workbench health not compiled/ready")
        elif function == "GetLoadedProjects":
            require(set(reply["Response"]) == {"Loaded Projects"} and type(reply["Response"]["Loaded Projects"]) is list and
                    0 < len(reply["Response"]["Loaded Projects"]) <= 256 and
                    all(type(v) is str and len(v) <= 2048 for v in reply["Response"]["Loaded Projects"]) and
                    base.PROJECT_ID in reply["Response"]["Loaded Projects"] and
                    mod.canonical(value.get("loaded_projects")) == mod.canonical(reply), "Loaded addon differs")
        else:
            normalized, codec = normalize(reply["Response"])
            require(mod.canonical(row.get("normalized_response")) == mod.canonical(normalized) and
                    mod.canonical(row.get("codec")) == mod.canonical(codec) and
                    mod.canonical(value.get("completion")) == mod.canonical(normalized), "Eligibility codec/completion differs")
            result = observation(normalized, token, output)
            require((value["status"] == "success") == (normalized["status"] == "eligible"), "Envelope confuses unavailable with eligible")
    checks = value.get("session_checks")
    require(type(checks) is list and all(type(r) is dict for r in checks) and [r.get("site") for r in checks] == sites and all(
            type(r.get("process_id")) is int and r["process_id"] == session["process_id"] and
            type(r.get("start_ticks")) is int and r["start_ticks"] == session["start_ticks"] and
            same_path(r.get("executable"), engine) and type(r.get("elapsed_ms")) is int and 0 <= r["elapsed_ms"] < value["elapsed_ms"] for r in checks),
            "Missing ownership checks at eligibility boundaries")
    require([r["elapsed_ms"] for r in checks] == sorted(r["elapsed_ms"] for r in checks), "Ownership checks out of order")
    logs = value.get("raw_logs")
    require(type(logs) is list and 0 < len(logs) <= 4096, "No owned raw session logs")
    total = 0
    for row in logs:
        require(type(row) is dict and type(row.get("retained")) is str and type(row.get("bytes")) is int and
                0 <= row["bytes"] <= 64 * 1024 * 1024, "Invalid retained raw log")
        path = Path(row["retained"])
        require(path.is_relative_to(addon.parent / "eligibility-logs"), "Log outside owned output")
        item = identity(path)
        require(row.get("sha256") == item["sha256"] and row["bytes"] == item["bytes"], "Raw log identity changed", "stale_input")
        total += row["bytes"]
    require(total <= 64 * 1024 * 1024, "Aggregate raw log limit exceeded")
    return result


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
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--prepare-only", action="store_true")
    modes.add_argument("--engine-stage", choices=("compile", "runtime"))
    args = parser.parse_args()
    if args.self_test:
        require(not args.prepared_receipt and not args.prepare_only and not args.engine_stage, "Self-test cannot launch engine work")
        return self_test()
    require(args.prepared_receipt and args.expect_prepared_sha256 and (args.prepare_only or args.engine_stage), "Explicit prepared input/hash/stage required")
    work = Path(tempfile.mkdtemp(prefix="world eligibility & spaces-", dir=ROOT / "build"))
    print("World eligibility evidence: " + str(work), flush=True)
    record = {"schema_version": 1, "operation": "verify.workbench.world_save_eligibility", "stage": "prepare", "status": "failure",
              "scope": {"source_copy": "not_run", "engine_compilation": "not_run", "eligibility_observation": "not_run",
                        "compiler_execution": "not_run",
                        "world_save": "not_run", "world_reload": "not_run", "callback_delivery": "not_run", "play": "not_run",
                        "installation": "unchanged", "policy_changes": "not_run"}, "commands": [], "raw_results": {}, "evidence_errors": [],
              "limitations": ["Experimental identity observation, not a released save scenario.",
                              "No world serialization, reload, callback, tablet, multiplayer, visual or performance evidence.",
                              "Old copied callback handler remains dormant; only the three installed read-only RPCs are admitted."]}
    job, check = None, None
    try:
        selection = args.prepared_receipt.absolute()
        clean_path(selection)
        require(selection.is_relative_to(ROOT / "build") and base.HASH.fullmatch(args.expect_prepared_sha256), "Prepared input must be owned and hashed")
        receipt_bytes = mod.read(selection)
        require(mod.digest(receipt_bytes) == args.expect_prepared_sha256, "Prepared receipt changed", "stale_input")
        selected = mod.parse(receipt_bytes)
        original, files, binding, retained, retained_files, retained_dirs = base.prepared(selected, selection)
        record.update(prepared_receipt=identity(selection), binding=binding, original_addon=str(original), original_files=files,
                      original_artifact=str(retained), prepared_artifact_sha256=selected["original_artifact"]["artifact_sha256"])
        inputs = [Path(__file__).resolve(), ROOT / "scripts/verify-workbench-startup.py", ROOT / "scripts/verify-component-engine.py",
                  ADAPTER, PACKAGE / "rpc.c.in", PACKAGE / "README.md", *mod.bundle_paths()]
        for name, fingerprint in DOCS.items():
            path = base.DOC_ROOT / name
            require(identity(path)["sha256"] == fingerprint, "Installed primary declaration changed", "stale_input")
            inputs.append(path)
        tools, compiler, host, engine = {}, None, None, None
        if args.engine_stage:
            require(all((args.beryl, args.expect_compiler_sha256, args.workbench_tools, args.powershell_host, args.engine_exe)), "Explicit engine configuration required")
            compiler, host, engine = (p.absolute() for p in (args.beryl, args.powershell_host, args.engine_exe))
            require(compiler.is_relative_to(ROOT / "build") and compiler.parent != ROOT / "build" and base.HASH.fullmatch(args.expect_compiler_sha256) and
                    identity(compiler)["sha256"] == args.expect_compiler_sha256, "Private compiler identity differs", "stale_input")
            require(identity(engine)["sha256"] == binding["sha256"], "Engine differs from binding", "stale_input")
            for name in sorted(set(base.COMPILE_TOOLS + base.RUNTIME_TOOLS)):
                path = mod.safe_path(args.workbench_tools.absolute(), "scripts/" + name, True)
                tools[name] = identity(path)["sha256"]
                inputs.append(path)
            inputs += [compiler, host, engine, mod.HERE / "engine-compile.ps1"]
        frozen = {str(p): identity(p) for p in inputs}
        record.update(verification_inputs=frozen, plugin_file_set=tools, retained_inputs=[])
        for index, (name, item) in enumerate(frozen.items()):
            if item["bytes"] > 16 * 1024 * 1024:
                record["retained_inputs"].append({**item, "retention": "fingerprint_only_large_binary"})
            else:
                data = mod.read(Path(name))
                require(mod.digest(data) == item["sha256"], "Input changed during retention", "stale_input")
                target = work / "inputs" / (str(index).zfill(4) + "-" + Path(name).name + ".input")
                write(target, data)
                record["retained_inputs"].append({**item, "retained": str(target), "retention": "exact_bytes"})
        write(work / "prepared-receipt.raw.json", receipt_bytes)
        addon = work / "probe-addon"
        output = addon / OUTPUT_REL
        output_absent(addon, output)
        template = mod.read(PACKAGE / "rpc.c.in")
        token = mod.digest(mod.canonical({"receipt": args.expect_prepared_sha256, "files": files, "handler": mod.digest(template),
                                        "addon": str(addon), "output": output.as_posix(), "profile": "world-save.eligibility.v1"}))
        for name, fingerprint in files.items():
            data = mod.read(mod.safe_path(original, name, True))
            require(mod.digest(data) == fingerprint, "Prepared source changed during copy", "stale_input")
            write(mod.safe_path(addon, name), data)
        write(mod.safe_path(addon, HANDLER_PATH), render(template, token, output.as_posix()))
        table, dirs = bounded.tree_files(addon)
        require(set(table) == base.BASE_FILES | {HANDLER_PATH}, "Eligibility source set differs")
        manifest = {"schema_version": 1, "files": table, "directories": sorted(dirs)}
        saved(work / "input-manifest.json", manifest)
        record.update(token=token, function=FUNCTION, candidate_path=str(addon), expected_output=str(output), staged_file_set=table,
                      staged_directory_set=sorted(dirs), staged_sha256=mod.digest(mod.canonical(table)))
        record["scope"]["source_copy"] = "executed_success"

        def unchanged():
            require(mod.read(selection) == receipt_bytes and mod.read(work / "prepared-receipt.raw.json") == receipt_bytes, "Selected receipt changed", "stale_input")
            bounded.exact_tree(original, files)
            bounded.exact_tree(retained, retained_files)
            require(sorted(bounded.tree_files(retained)[1]) == retained_dirs, "Retained artifact directories changed", "stale_input")
            for name, item in frozen.items():
                require(identity(Path(name)) == item, "Verification source changed: " + name, "stale_input")
            for item in record["retained_inputs"]:
                if item["retention"] == "exact_bytes":
                    observed = identity(Path(item["retained"]))
                    require(observed["bytes"] == item["bytes"] and observed["sha256"] == item["sha256"], "Retained input changed", "stale_input")
            record["engine_derived_outputs"] = bounded.staged_tree(addon, table)
            output_absent(addon, output)
            require(mod.canonical(mod.parse(mod.read(work / "input-manifest.json"))) == mod.canonical(manifest), "Staged manifest changed", "stale_input")
        check = unchanged
        check()
        if args.prepare_only:
            record.update(status="success", stage="prepared", success_means="eight preserved inputs plus one read-only observer; no execution")
        else:
            project = work / "job-project"
            project.mkdir()
            job = mod.Job(project, "world-save-eligibility", compiler)
            job.result.update(source_sha256=record["staged_sha256"], binding_sha256=mod.digest(mod.canonical(binding)))
            compile_path = work / "engine-compile.json"
            record["stage"] = "engine_compile"
            record["scope"]["engine_compilation"] = "attempted_unconfirmed"
            try:
                job.run([host, "-NoProfile", "-File", mod.HERE / "engine-compile.ps1", "-ToolRoot", args.workbench_tools.absolute(),
                         "-ProjectDir", addon, "-ResultPath", compile_path, "-ExpectedVersion", binding["version"], "-TimeoutSeconds", "30"],
                        "eligibility_engine_compile", work, timeout=60)
            finally:
                base.capture_result(record, "compile", compile_path)
                if "compile" in record["raw_results"]:
                    raw = record["raw_results"]["compile"]["result"]
                    record["scope"]["engine_compilation"] = base.compile_status(raw, binding, tools)
                    try:
                        record["compile_logs"] = base.retained_logs(work, raw)
                    except (mod.Failure, OSError, ValueError) as exc:
                        record["evidence_errors"].append({"stage": "compile_log_capture", "message": str(exc)})
            require(record["scope"]["engine_compilation"] == "executed_success" and not record["evidence_errors"], "Incomplete headless compile success")
            check()
            if args.engine_stage == "runtime":
                runtime_path = work / "engine-runtime.json"
                record["stage"] = "world_save_eligibility"
                record["scope"]["eligibility_observation"] = "attempted_unconfirmed"
                try:
                    job.run([host, "-NoProfile", "-File", ADAPTER, "-ToolRoot", args.workbench_tools.absolute(), "-ProjectDir", addon,
                             "-ProjectId", base.PROJECT_ID, "-InputManifest", work / "input-manifest.json", "-ResultPath", runtime_path,
                             "-OutputPath", output, "-Token", token, "-ExpectedEnginePath", engine, "-ExpectedEngineHash", binding["sha256"],
                             "-ExpectedEngineVersion", binding["version"]], "world_save_eligibility", work, timeout=240)
                finally:
                    base.capture_result(record, "runtime", runtime_path)
                    if "runtime" in record["raw_results"]:
                        try:
                            record["observation_comparison"] = validate_runtime(record["raw_results"]["runtime"]["result"], token, addon, engine, binding,
                                tools, work / "input-manifest.json", manifest, frozen[str(ADAPTER)]["sha256"])
                            record["scope"]["eligibility_observation"] = "executed_" + record["observation_comparison"]["eligibility"]
                        except (mod.Failure, OSError, ValueError) as exc:
                            record["evidence_errors"].append({"stage": "eligibility_envelope_validation", "message": str(exc)})
                require(record.get("observation_comparison", {}).get("eligibility") == "eligible" and not record["evidence_errors"],
                        "Observed world-save capability is not eligible", "unavailable")
                check()
            record.update(status="success", stage="verified", success_means="exact compile" if args.engine_stage == "compile" else
                          "matching empty native editor context; serialization, reload and callbacks not run")
    except (mod.Failure, OSError, ValueError, KeyboardInterrupt) as exc:
        record["status"] = "cancelled" if isinstance(exc, KeyboardInterrupt) else getattr(exc, "status", "failure")
        if record["status"] == "failure" and not record["evidence_errors"]:
            for label in ("runtime", "compile"):
                raw = record["raw_results"].get(label, {}).get("result")
                if type(raw) is dict and raw.get("status") in ("failure", "unavailable", "timeout", "cancelled", "stale_input"):
                    record["status"] = raw["status"]
                    break
        record["failure"] = {"type": type(exc).__name__, "message": str(exc)}
    finally:
        if check:
            try:
                check()
            except (mod.Failure, OSError, ValueError) as exc:
                record["evidence_errors"].append({"stage": "final_input_guard", "message": str(exc)})
                if record["status"] == "success":
                    record["status"] = getattr(exc, "status", "stale_input")
        if job:
            record["commands"] = job.result["raw_logs"]
            if record["status"] == "success" and any(r.get("exit_confirmed") is not True or r.get("cleanup_errors") for r in record["commands"]):
                record["status"] = "unavailable"
                record["evidence_errors"].append({"stage": "host_cleanup", "message": "Host exit/cleanup incomplete"})
            job.result.update(status=record["status"], stage=record["stage"])
            saved(job.path / "result.json", job.result)
            record["job"] = job.result
        saved(work / "results.json", record)
        print(str(work / "results.json"), flush=True)
    return 0 if record["status"] == "success" else 1


def self_test():
    """Inert codecs/contracts only: no host, compiler, engine, or subprocess."""
    work = Path(tempfile.mkdtemp(prefix="world-save-inert-", dir=ROOT / "build"))
    cases = []
    def accept(name, fn):
        fn()
        cases.append({"id": name, "status": "passed"})
    def reject(name, fn):
        try:
            fn()
        except (mod.Failure, OSError, ValueError):
            cases.append({"id": name, "status": "rejected"})
        else:
            raise AssertionError("Deliberate fault admitted: " + name)
    token, output = "a" * 64, work / "probe-addon" / OUTPUT_REL
    good = {k: "" for k in STRINGS}
    good.update({k: k not in ("in_play_mode", "wb_game_mode") for k in BOOLS})
    good.update(token=token, action="observe", status="eligible", output_path=output.as_posix())
    accept("wire.eligible", lambda: observation(normalize(good)[0], token, output))
    numeric = {k: int(v) if type(v) is bool else v for k, v in good.items()}
    before = copy.deepcopy(numeric)
    accept("wire.bool01", lambda: observation(normalize(numeric)[0], token, output))
    accept("wire.no-mutation", lambda: require(numeric == before, "Normalization mutated raw response"))
    missing = {**good, "game_editor_present": False, "game_api_present": False, "game_world_present": False,
               "api_same": False, "world_same": False, "status": "unavailable", "failure": "Game editor unavailable"}
    accept("wire.unavailable", lambda: require(observation(normalize(missing)[0], token, output)["eligibility"] == "unavailable", "Unavailable lost"))
    for key in BOOLS:
        reject("bool.type." + key, lambda k=key: normalize({**good, k: "1"}))
    for name, key, val in (("float", "world_same", 1.0), ("two", "world_same", 2), ("status", "status", "success"),
            ("token", "token", "b" * 64), ("action", "action", "save"), ("output", "output_path", "C:/unowned.ent"),
            ("named-wb", "wb_world_path", "world.ent"), ("named-game", "game_world_path", "world.ent"),
            ("reason", "failure", "wrong"), ("play", "in_play_mode", True), ("game-mode", "wb_game_mode", True)):
        reject("wire." + name, lambda k=key, v=val: observation(normalize({**good, k: v})[0], token, output))
    for key in BOOLS:
        if key not in ("in_play_mode", "wb_game_mode"):
            reject("eligible.missing." + key, lambda k=key: observation(normalize({**good, k: False})[0], token, output))
    reject("wire.extra", lambda: normalize({**good, "extra": 1}))
    reject("wire.missing", lambda: normalize({k: v for k, v in good.items() if k != "token"}))
    reject("wire.oversized", lambda: normalize({**good, "failure": "x" * 2049}))
    reject("wire.unavailable-contradiction", lambda: observation(normalize({**good, "status": "unavailable", "failure": "absent"})[0], token, output))
    accept("output.absent", lambda: output_absent(work / "probe-addon", output))
    reject("output.foreign", lambda: output_absent(work / "probe-addon", work / "other.ent"))
    accept("render.exact", lambda: require(render(b'@TOKEN@ @OUTPUT_ABSOLUTE@', token, output.as_posix()) ==
                                           (token + " " + output.as_posix()).encode(), "Literal differs"))
    reject("render.unresolved", lambda: render(b'@OTHER@', token, output.as_posix()))
    template = mod.read(PACKAGE / "rpc.c.in").decode()
    executable_text = re.sub(r"//[^\n]*", "", template)
    accept("handler.read-only", lambda: require(not re.search(r"\b(SaveWorldAs|SaveWorld|OpenResource|SetOpenedResource|LoadWorld|CreateWorld|PlayGame|DeleteEntity)\s*\(", executable_text), "Handler mutates engine"))
    output.parent.mkdir(parents=True)
    reject("output.namespace-existing", lambda: output_absent(work / "probe-addon", output))
    frozen = {str(p): identity(p) for p in (Path(__file__).resolve(), PACKAGE / "rpc.c.in", PACKAGE / "README.md",
                                          ROOT / "scripts/verify-workbench-startup.py", ROOT / "scripts/verify-component-engine.py", *mod.bundle_paths())}
    saved(work / "result.json", {"schema_version": 1, "operation": "verify.world_save.inert", "status": "success", "cases": cases,
          "completed_count": len(cases), "verification_inputs": frozen, "scope": "inert contracts; no host/compiler/engine execution"})
    print(str(work / "result.json"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
