#!/usr/bin/env python3
"""Compile the last frozen scalar v2 artifact using an explicit PowerShell host.

This experimental verifier is separate from public v2 verification/promotion.
It launches only the installed headless compile adapter. No callback, state
write-through, lifecycle, multiplayer, visual or promotion evidence is implied.
Both successful and failed attempts retain a job receipt and raw logs. No
execution-policy override, project hook, compiler launch or runtime is used.
"""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools/beryl-mod"))
sys.dont_write_bytecode = True
import mod
from source_maps import map_engine_diagnostics

STATUSES = {"success", "failure", "unavailable", "stale_input", "timeout", "cancelled"}
PLUGIN_FILES = ("Find-Workbench.ps1", "Invoke-ReforgerBuild.ps1",
                "Invoke-Workbench.ps1", "Get-WorkbenchErrors.ps1")
MAX_ENTRIES = 4096
MAX_RESOURCE_DATABASE = 8 * 1024 * 1024


def fail(message, status="failure"):
    raise mod.Failure(message, status)


def file_hash(path):
    """Hash large executable/log files without loading them into memory."""
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def fingerprint(path):
    path = Path(path)
    return {"path": str(path), "sha256": file_hash(path), "bytes": path.stat().st_size}


def linked(path):
    return path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction())


def tree_files(root):
    """A bounded exact file set; links and unaccounted empty directories fail."""
    root = Path(root)
    if linked(root) or not root.is_dir():
        fail("Missing or linked immutable directory: " + str(root), "stale_input")
    files, directories, count = {}, set(), 0
    for directory, names, leaves in os.walk(root, followlinks=False):
        for name in sorted(names + leaves):
            path = Path(directory) / name
            count += 1
            if count > MAX_ENTRIES:
                fail("Immutable file-set limit exceeded", "unavailable")
            if linked(path):
                fail("Linked immutable entry: " + str(path), "stale_input")
            relative = path.relative_to(root).as_posix()
            if path.is_dir():
                directories.add(relative)
            elif path.is_file():
                files[relative] = file_hash(path)
            else:
                fail("Unsupported immutable entry: " + str(path), "stale_input")
    return files, directories


def expected_directories(files):
    result = set()
    for name in files:
        parent = Path(name).parent
        while parent.as_posix() != ".":
            result.add(parent.as_posix())
            parent = parent.parent
    return result


def exact_tree(root, files):
    actual, directories = tree_files(root)
    if actual != files or directories != expected_directories(files):
        fail("Immutable file/directory set or bytes changed: " + str(root), "stale_input")


def staged_tree(root, files):
    """Only Workbench's root resource database may be a derived noninput."""
    name = "resourceDatabase.rdb"
    derived = Path(root) / name
    outputs = []
    before = None
    if name not in files and (derived.exists() or linked(derived)):
        if linked(derived) or not derived.is_file():
            fail("Engine resource database is linked or nonregular", "stale_input")
        before = derived.stat()
        if before.st_size > MAX_RESOURCE_DATABASE:
            fail("Engine resource database exceeds the 8 MiB output limit", "unavailable")
    actual, directories = tree_files(root)
    if before is not None:
        after = derived.stat()
        if after.st_size != before.st_size or after.st_mtime_ns != before.st_mtime_ns:
            fail("Engine resource database changed during capture", "stale_input")
        outputs.append({"path": str(derived), "relative_path": name,
                        "sha256": actual.pop(name), "bytes": before.st_size,
                        "kind": "engine_derived_noninput", "limit_bytes": MAX_RESOURCE_DATABASE})
    if actual != files or directories != expected_directories(files):
        fail("Staged source file/directory set or bytes changed: " + str(root), "stale_input")
    return outputs


def hash_table(value, name):
    if type(value) is not dict or not value or len(value) > MAX_ENTRIES:
        fail("Missing or invalid " + name)
    for key, fingerprint_value in value.items():
        if type(key) is not str or type(fingerprint_value) is not str or not re.fullmatch("[0-9a-f]{64}", fingerprint_value):
            fail("Invalid " + name + " entry")
        # Validate paths before any joined read/copy; no traversal or links.
        mod.safe_path(ROOT, key)
    return value


def artifact_identity(path, selected):
    raw = mod.read(path / "artifact.json")
    value = mod.parse(raw)
    if type(value) is not dict or type(value.get("schema_version")) is not int or value["schema_version"] != 1:
        fail("Unsupported artifact manifest")
    body = {key: item for key, item in value.items() if key not in ("id", "artifact_sha256")}
    if (value.get("id") != selected.get("artifact_id") or
            not re.fullmatch("[0-9a-f]{32}", str(value.get("id", ""))) or
            mod.digest(mod.canonical(body)) != value.get("artifact_sha256") or
            value.get("artifact_sha256") != selected.get("artifact_sha256")):
        fail("Artifact canonical identity changed", "stale_input")
    for name in ("inputs", "files", "sidecars"):
        hash_table(value.get(name), name)
    if set(value["sidecars"]) != {"source-map.json"}:
        fail("Only the exact source-map sidecar is supported", "unavailable")
    for name in ("compiler_sha256", "tool_sha256", "source_sha256"):
        if value.get(name) != selected.get(name):
            fail("Workflow/artifact identity differs: " + name, "stale_input")
    if mod.digest(mod.canonical(value["inputs"])) != value["source_sha256"]:
        fail("Artifact source identity is not its input set", "stale_input")
    return value, mod.digest(raw)


def validate_build(selected):
    if type(selected) is not dict:
        fail("Invalid mod build receipt")
    generation = selected.get("component_generation", {})
    if (type(selected.get("schema_version")) is not int or selected["schema_version"] != 1 or
            selected.get("status") != "success" or selected.get("operation") != "mod build" or
            selected.get("stage") != "candidate" or type(selected.get("companion_version")) is not int or
            selected["companion_version"] != 2 or type(generation) is not dict or
            generation.get("status") != "generated" or
            generation.get("subset") != "depth_one_bool_i32_f32_state"):
        fail("Selected build is not a successful frozen scalar v2 artifact", "unavailable")
    return selected


def select_artifact(workflow):
    if type(workflow) is not dict or workflow.get("status") != "success":
        fail("Only a successful component workflow receipt can select an artifact")
    commands = workflow.get("commands")
    if type(commands) is not list:
        fail("Workflow commands are missing")
    builds = []
    for command in commands:
        if type(command) is not dict:
            fail("Invalid workflow command")
        argv, result = command.get("argv"), command.get("result")
        if type(argv) is list and argv[1:3] == ["mod", "build"] and type(result) is dict and result.get("status") == "success":
            if command.get("status") != "exited" or command.get("exit_code") != 0:
                fail("Successful build lacks a successful process receipt")
            builds.append(result)
    if not builds:
        fail("Workflow contains no completed generated artifact")
    return validate_build(builds[-1])


def capture_engine_logs(work, result):
    """Retain actual engine logs on failure as well as success; never invent one."""
    info = result.get("result")
    if type(info) is not dict or not info.get("LogDir"):
        return [], "unavailable"
    directory = Path(info["LogDir"])
    if linked(directory) or not directory.is_dir():
        return [], "unavailable"
    logs = sorted(directory.glob("*.log"))
    if len(logs) > MAX_ENTRIES:
        fail("Engine log count limit exceeded", "unavailable")
    retained = []
    for index, original in enumerate(logs):
        if linked(original) or not original.is_file():
            fail("Linked or missing raw engine log", "stale_input")
        before = fingerprint(original)
        target = work / "logs" / (str(index).zfill(4) + "-" + original.name)
        target.parent.mkdir(exist_ok=True)
        with original.open("rb") as source, target.open("xb") as destination:
            shutil.copyfileobj(source, destination, 1024 * 1024)
        after, copied = fingerprint(original), fingerprint(target)
        if before != after or copied["sha256"] != before["sha256"] or copied["bytes"] != before["bytes"]:
            fail("Raw engine log changed during capture", "stale_input")
        retained.append({"original": before["path"], "retained": copied["path"],
                         "sha256": copied["sha256"], "bytes": copied["bytes"]})
    return retained, "retained" if retained else "unavailable"


def process_logs(job):
    result = []
    for record in job.result["raw_logs"]:
        for stream in ("stdout", "stderr"):
            path = Path(record[stream])
            item = {"stage": job.result["stage"], "stream": stream, "path": str(path)}
            if path.is_file():
                item.update(status="retained", **{k: v for k, v in fingerprint(path).items() if k != "path"})
                record[stream + "_sha256"] = item["sha256"]
                record[stream + "_bytes"] = item["bytes"]
            else:
                item["status"] = "unavailable"
            result.append(item)
    return result


def status_for(exc):
    if isinstance(exc, KeyboardInterrupt):
        return "cancelled"
    if isinstance(exc, OSError):
        return "unavailable"
    status = getattr(exc, "status", "failure")
    return status if status in STATUSES - {"success"} else "failure"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--workflow", type=Path, help="Successful component workflow; select its last successful build")
    selection.add_argument("--build-receipt", type=Path, help="Actual successful scalar v2 mod build result")
    parser.add_argument("--compiler", type=Path, required=True)
    parser.add_argument("--tools", type=Path, required=True, help="Installed Workbench plugin root")
    parser.add_argument("--engine", type=Path, required=True, help="Exact recorded Workbench executable")
    parser.add_argument("--powershell-host", type=Path, required=True,
                        help="Explicit installed PowerShell executable; its configured policy is preserved")
    parser.add_argument("--timeout-seconds", type=int, default=120)
    args = parser.parse_args(argv)
    if not 1 <= args.timeout_seconds <= 600:
        parser.error("--timeout-seconds must be between 1 and 600")
    work = Path(tempfile.mkdtemp(prefix="component-engine-", dir=ROOT / "build"))
    outer = work / "result.json"
    result_path = work / "compile.json"
    record = {"schema_version": 1, "operation": "experimental.scalar_component_compile", "status": "failure",
              "stage": "preflight", "scope": "headless script compilation of one frozen scalar v2 artifact only",
              "result_path": str(outer), "raw_process_logs": [], "raw_engine_logs": [], "errors": [],
              "engine_generated_outputs": [],
              "compilation": "not_run", "callback_execution": "not_run", "state_write_through": "not_run",
              "runtime": "not_run", "tablet_lifecycle": "not_run", "multiplayer": "not_run", "visual": "not_run",
              "promotion": "not_run", "execution_policy": "host_configuration_unchanged; no override",
              "requested": {name: str(getattr(args, name)) if getattr(args, name) is not None else None for name in
                            ("workflow", "build_receipt", "compiler", "tools", "engine", "powershell_host")},
              "job_receipt": {"status": "unavailable", "reason": "job not yet created"}}
    job, unchanged, engine_result = None, None, None
    print("Component engine evidence:", work, flush=True)
    try:
        selection_kind = "workflow" if args.workflow is not None else "build"
        selection_path = (args.workflow or args.build_receipt).resolve(strict=True)
        selection_raw = mod.read(selection_path)
        receipt = mod.parse(selection_raw)
        record.update(selection_kind=selection_kind, selection_receipt=str(selection_path),
                      selection_receipt_sha256=mod.digest(selection_raw))
        record[selection_kind + "_receipt"] = str(selection_path)
        record[selection_kind + "_receipt_sha256"] = mod.digest(selection_raw)
        selected = select_artifact(receipt) if args.workflow is not None else validate_build(receipt)
        compiler = args.compiler.resolve(strict=True)
        artifact = Path(selected["artifact_path"]).resolve(strict=True)
        if artifact.parent.name != "artifacts" or artifact.parent.parent.name != ".beryl-mod":
            fail("Artifact path is outside the generated artifact layout")
        project = artifact.parents[2]
        manifest, manifest_hash = artifact_identity(artifact, selected)
        if artifact.name != manifest["id"]:
            fail("Artifact directory identity differs from its manifest", "stale_input")
        if (file_hash(compiler) != manifest["compiler_sha256"] or
                receipt.get("compiler_sha256") != manifest["compiler_sha256"] or
                mod.tool_identity() != manifest["tool_sha256"]):
            fail("Selected compiler/tool bytes do not match the artifact", "stale_input")
        config, _, source_hashes = mod.description_snapshot(project)
        if config.get("schema_version") != 2 or source_hashes != manifest["inputs"] or config["binding"] != manifest["binding"]:
            fail("Companion/source/binding differs from the frozen v2 artifact", "stale_input")
        binding = manifest["binding"]
        if binding.get("target") != "enfusion" or binding.get("contract_profile") != "enfusion.tablet.script-component.v1":
            fail("Unsupported engine binding profile", "unavailable")
        engine = args.engine.resolve(strict=True)
        host = args.powershell_host.resolve(strict=True)
        tools = args.tools.resolve(strict=True)
        if not engine.is_file() or not host.is_file() or not tools.is_dir():
            fail("Configured engine, PowerShell host or plugin is unavailable", "unavailable")
        if file_hash(engine) != binding["sha256"]:
            fail("Engine differs from the frozen binding", "stale_input")
        bridge = {name: mod.safe_path(tools, "scripts/" + name, True) for name in PLUGIN_FILES}
        plugin_hashes = {name: file_hash(path) for name, path in bridge.items()}
        adapter = mod.HERE / "engine-compile.ps1"
        frozen = {str(path): file_hash(path) for path in
                  [Path(__file__).resolve(), selection_path, compiler, engine, host, adapter,
                   *mod.bundle_paths(), *bridge.values()]}
        expected_artifact = {"artifact.json": manifest_hash, **manifest["sidecars"],
                             **{"addon/" + name: value for name, value in manifest["files"].items()}}
        record.update(artifact_id=manifest["id"], artifact_sha256=manifest["artifact_sha256"],
                      compiler_sha256=manifest["compiler_sha256"], tool_sha256=manifest["tool_sha256"],
                      source_sha256=manifest["source_sha256"], engine_sha256=binding["sha256"],
                      engine_version=binding["version"], plugin_hashes=plugin_hashes,
                      original_artifact=str(artifact), source_root=str(project), frozen_hashes=frozen,
                      original_file_hashes=expected_artifact, source_hashes=source_hashes,
                      powershell_host=fingerprint(host), adapter_script=fingerprint(adapter))

        def check_original():
            current, raw_hash = artifact_identity(artifact, selected)
            if current != manifest or raw_hash != manifest_hash:
                fail("Artifact manifest changed during verification", "stale_input")
            exact_tree(artifact, expected_artifact)
            for name, expected in source_hashes.items():
                if file_hash(mod.safe_path(project, name, True)) != expected:
                    fail("Original authoring input changed: " + name, "stale_input")
            for name, expected in frozen.items():
                if file_hash(Path(name)) != expected:
                    fail("Frozen compiler/tool/plugin/engine/script input changed: " + name, "stale_input")
            if mod.tool_identity() != manifest["tool_sha256"]:
                fail("Tool input set changed", "stale_input")

        check_original()
        staged = work / "candidate" / "addon"
        staged.parent.mkdir()
        shutil.copytree(artifact / "addon", staged)
        record.update(stage="staged", staged_addon=str(staged), staged_file_hashes=manifest["files"])

        def unchanged():
            try:
                check_original()
                record["engine_generated_outputs"] = staged_tree(staged, manifest["files"])
            except OSError as exc:
                raise mod.Failure("Frozen input disappeared or is unreadable: " + str(exc), "stale_input") from exc

        unchanged()
        # Job owns only this compile process tree. Its project is the evidence
        # directory, not the author's project; explicit guards cover both the
        # original project and the copied immutable addon before/after Job.run.
        job = mod.Job(work, "experimental.scalar_component_compile", compiler)
        job.result.update(artifact_id=manifest["id"], artifact_sha256=manifest["artifact_sha256"],
                          source_sha256=manifest["source_sha256"], binding_sha256=mod.digest(mod.canonical(binding)))
        record.update(stage="headless_compile", compilation="attempted")
        job.run([host, "-NoProfile", "-File", adapter, "-ToolRoot", tools,
                 "-ProjectDir", staged, "-ResultPath", result_path, "-ExpectedVersion", binding["version"],
                 "-TimeoutSeconds", str(args.timeout_seconds)], "headless_compile", work,
                args.timeout_seconds + 30)
        record["process_outcome"] = "exited_zero"
    except BaseException as exc:
        record["status"] = status_for(exc)
        record["errors"].append({"stage": record["stage"], "status": record["status"],
                                 "type": type(exc).__name__, "message": str(exc)})
    finally:
        # Parse/capture adapter evidence even after a nonzero exit, timeout or
        # cancellation. Missing results are explicitly unavailable, not success.
        if result_path.is_file():
            try:
                raw = mod.read(result_path)
                engine_result = mod.parse(raw)
                if type(engine_result) is not dict:
                    fail("Engine result is not an object")
                record.update(engine_result=engine_result,
                              engine_result_receipt={"path": str(result_path), "sha256": mod.digest(raw), "bytes": len(raw)})
                adapter_status = engine_result.get("status")
                if adapter_status not in STATUSES:
                    fail("Engine adapter returned an unknown status")
                if record["status"] not in {"timeout", "cancelled", "stale_input"} and adapter_status != "success":
                    record["status"] = adapter_status
                if job is not None:
                    logs, log_status = capture_engine_logs(work, engine_result)
                    record.update(raw_engine_logs=logs, raw_engine_log_status=log_status)
                    if type(engine_result.get("result")) is dict:
                        record["mapped_diagnostics"] = map_engine_diagnostics(
                            mod, artifact, manifest, engine_result, staged, source_root=project)
                info = engine_result.get("result", {})
                complete = (engine_result.get("schema_version") == 1 and engine_result.get("stage") == "workbench_compile" and
                            adapter_status == "success" and record.get("process_outcome") == "exited_zero" and
                            engine_result.get("engine_sha256") == binding["sha256"] and
                            engine_result.get("engine_version") == binding["version"] and
                            engine_result.get("tools") == plugin_hashes and type(info) is dict and
                            info.get("Stage") == "Compiled" and info.get("Ok") is True and
                            type(info.get("ExitCode")) is int and info["ExitCode"] == 0 and
                            type(info.get("ErrorCount")) is int and info["ErrorCount"] == 0 and
                            record.get("raw_engine_log_status") == "retained")
                if complete and not record["errors"]:
                    record.update(status="success", compilation="verified")
                elif adapter_status == "success" and record["status"] == "failure" and not record["errors"]:
                    fail("Incomplete or mismatched engine compile evidence")
            except BaseException as exc:
                record["errors"].append({"stage": "engine_evidence", "status": status_for(exc),
                                         "type": type(exc).__name__, "message": str(exc)})
                if record["status"] not in {"timeout", "cancelled", "stale_input"}:
                    record["status"] = status_for(exc)
        else:
            record["engine_result_receipt"] = {"path": str(result_path), "status": "unavailable"}
            record["raw_engine_log_status"] = "unavailable"
            if record.get("process_outcome") == "exited_zero":
                record["errors"].append({"stage": "engine_evidence", "status": "failure",
                                         "type": "IncompleteResult", "message": "Adapter exited zero without a compile receipt"})
        if unchanged is not None:
            try:
                unchanged()
                record["postflight_integrity"] = "success"
            except BaseException as exc:
                record["postflight_integrity"] = status_for(exc)
                record["errors"].append({"stage": "postflight", "status": status_for(exc),
                                         "type": type(exc).__name__, "message": str(exc)})
                record["status"] = status_for(exc)
        if job is not None:
            try:
                record["raw_process_logs"] = process_logs(job)
                job.result.update(status=record["status"], engine=engine_result,
                                  diagnostics=record.get("mapped_diagnostics", []),
                                  verification_errors=record["errors"], scope=record["scope"])
                mod.write_json(job.result["result_path"], job.result)
                record["job"] = job.result
                record["job_receipt"] = {"status": "retained", **fingerprint(Path(job.result["result_path"]))}
            except BaseException as exc:
                record["status"] = status_for(exc)
                record["job_receipt"] = {"status": "unavailable", "path": job.result["result_path"], "reason": str(exc)}
                record["errors"].append({"stage": "job_receipt", "status": status_for(exc),
                                         "type": type(exc).__name__, "message": str(exc)})
        record["stage"] = "complete"
        mod.write_json(outer, record)
        print("Headless compilation:", record["status"], "(runtime not run)", flush=True)
        print(outer, flush=True)
    return 0 if record["status"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
