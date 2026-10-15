#!/usr/bin/env python3
"""Prepare or execute an isolated plain member-box state ABI probe.

Requires an explicitly identified private compiler. --prepare-only runs source
checks/generation but no native program or engine. Engine stages use the selected
PowerShell host and existing trusted transports, with no policy flags. No source
installation, promotion, generated-file correction or live MESH edit occurs.
"""
from pathlib import Path
import argparse
import contextlib
import hashlib
import json
import os
import re
import shutil
import struct
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "packages/sparkos/component-state-probe"
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / "tools/beryl-mod"))
import mod
import scenarios

CASE_IDS = (
    "record-defaults", "member-box-defaults", "member-box-field-write-through",
    "member-box-whole-record-replacement", "member-box-reset-after-replacement",
    "manual-handler-repeated-frame", "manual-handler-frame-replace-frame",
    "independent-member-boxes", "direct-handler-init", "direct-handler-delete",
    "manual-member-box-nested-field-call",
)
IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
HASH = re.compile(r"[0-9a-f]{64}")
COMPILE_TOOLS = ("Find-Workbench.ps1", "Invoke-ReforgerBuild.ps1", "Invoke-Workbench.ps1", "Get-WorkbenchErrors.ps1")
FAILURE_STATUSES = {"failure", "unavailable", "timeout", "cancelled", "stale_input"}


def require(condition, message, status="failure", pointer=None):
    if not condition:
        raise mod.Failure(message, status, pointer)


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


def files(root):
    result = {}
    for path in sorted(root.rglob("*")):
        require(not path.is_symlink() and not (hasattr(path, "is_junction") and path.is_junction()),
                "Linked fixture/staged path is not admitted", "stale_input")
        if path.is_file():
            result[path.relative_to(root).as_posix()] = mod.digest(mod.read(path))
    return result


def directories(root):
    return [path.relative_to(root).as_posix() for path in sorted(root.rglob("*")) if path.is_dir()]


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


def expected():
    value = mod.parse(mod.read(PACKAGE / "expected-cases.json"))
    require(type(value) is dict and value.get("schema_version") == 1 and
            value.get("scenario") == "probe.state.member_box.manual" and
            value.get("profile") == "plain-script-member-box.bool-i32-f32.v1", "Unsupported expected-case manifest")
    require(type(value.get("cases")) is list and [case.get("id") for case in value["cases"]] == list(CASE_IDS),
            "Expected cases must be the statically registered complete ordered set")
    rows, checks = [], 0
    for case in value["cases"]:
        require(set(case) == {"id", "states", "identities"}, "Unknown expected case fields")
        rows.append("case|" + case["id"])
        for state in case["states"]:
            require(type(state) is dict and set(state) == {"prefix", "ready", "count", "elapsed"} and
                    type(state["prefix"]) is str and IDENT.fullmatch(state["prefix"]) and
                    type(state["ready"]) is bool and type(state["count"]) is int and
                    -100 <= state["count"] <= 100 and type(state["elapsed"]) in (int, float) and
                    0 <= state["elapsed"] <= 1 and
                    struct.unpack("<f", struct.pack("<f", state["elapsed"]))[0] == state["elapsed"],
                    "Expected state exceeds admitted exact scalar domain")
            prefix = "|" + case["id"] + "|" + state["prefix"]
            rows += ["int" + prefix + ".present|1", "bool" + prefix + ".ready|" + str(int(state["ready"])),
                     "int" + prefix + ".count|" + str(state["count"]), "float_equal" + prefix + ".elapsed|1"]
            checks += 4
        for relation in case["identities"]:
            require(type(relation) is dict and set(relation) == {"key", "equal"} and
                    type(relation["key"]) is str and re.fullmatch("[a-z-]{1,40}", relation["key"]) and
                    type(relation["equal"]) is bool, "Malformed expected identity relation")
            rows.append("identity_equal|" + case["id"] + "|" + relation["key"] + "|" + str(int(relation["equal"])))
            checks += 1
        rows.append("end|" + case["id"])
    require(checks == 73 and len(rows) == 95, "Expected observation matrix differs from trusted template")
    return value, rows, checks


def renderer(config, mapping, token):
    linkage = mapping.get("linkage")
    require(type(linkage) is list and mapping.get("linkage_schema_version") == 1,
            "Actual emitted version-one linkage is required", "unavailable")
    def row(name, kind):
        matches = [item for item in linkage if item.get("declaration") == "sparkos.component_state_probe." + name]
        require(len(matches) == 1 and matches[0].get("kind") == kind, "Missing exact emitted probe declaration: " + name)
        return matches[0]
    state = row("State", "struct")
    fields = {item["source"]: item["name"] for item in state["fields"]}
    require(set(fields) == {"ready", "count", "elapsed"}, "Actual emitted state fields differ")
    component = config["components"][0]["instance"]["name"]
    symbols = {"CLASS": "BerylStateMemberBox_" + token[:16], "COMPONENT": component,
               "STATE": state["class"], "READY": fields["ready"], "COUNT": fields["count"], "ELAPSED": fields["elapsed"]}
    for key, name in (("MUTATE", "mutate_fields"), ("REPLACE", "replace"), ("RESET", "reset"),
                      ("INIT", "on_init"), ("DELETE", "on_delete"), ("FRAME", "on_frame")):
        item = row(name, "function")
        symbols[key + "_HOLDER"], symbols[key + "_METHOD"] = item["holder"], item["method"]
    require(all(type(value) is str and IDENT.fullmatch(value) for value in symbols.values()),
            "Emitted probe identity is not an identifier")
    text = mod.read(PACKAGE / "component-state.c.in").decode("utf-8")
    for key, value in {**symbols, "TOKEN": token}.items():
        text = text.replace("@" + key + "@", value)
    require(not re.search(r"@[A-Z_]+@", text), "Unresolved trusted probe placeholder")
    return text.encode("utf-8"), symbols


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--beryl", type=Path, required=True)
    parser.add_argument("--expect-compiler-sha256", required=True)
    parser.add_argument("--workbench-tools", type=Path, required=True)
    parser.add_argument("--powershell-host", type=Path)
    parser.add_argument("--engine-exe", type=Path)
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
    work = Path(tempfile.mkdtemp(prefix="component state & spaces-", dir=ROOT / "build"))
    record = {"schema_version": 1, "operation": "verify.state_member_box.manual", "status": "failure",
              "stage": "prepare", "expected_case_ids": list(CASE_IDS), "commands": [], "raw_results": {},
              "scope": {"source_generation": "not_run", "engine_compilation": "not_run", "engine_vm_manual_probe": "not_run",
                        "engine_callback_delivery": "not_run", "tablet_service_connection": "not_run", "native_program": "not_run",
                        "component_runtime_state": "not_run", "component_construction": "not_run", "component_world_lifetime": "unverified",
                        "installation": "unchanged", "policy_changes": "not_run"},
              "limitation": "Plain script member-box ABI and actual emitted handler calls only; compiled generated component remains separate. No component runtime state/construction, engine-delivered callbacks, world/prefab lifetime, tablet services, authority or multiplayer proof."}
    outer, staged, staged_dirs, tracked, unchanged = None, None, None, {}, None
    print("Component-state evidence: " + str(work), flush=True)
    try:
        manifest, expected_rows, expected_checks = expected()
        record["probe_profile"] = manifest["profile"]
        package_files = files(PACKAGE)
        plugin = sorted((toolroot / "scripts").glob("*.ps1"))
        require({"Find-Workbench.ps1", "Invoke-ReforgerBuild.ps1", "Invoke-Workbench.ps1", "Get-WorkbenchErrors.ps1",
                 "Start-WorkbenchDaemon.ps1", "Invoke-WorkbenchRpc.ps1"}.issubset({path.name for path in plugin}),
                "Required installed integration scripts are missing", "unavailable")
        inputs = [("compiler/compiler.input", compiler), ("python/python.input", Path(sys.executable).resolve()),
                  ("verifier/verify-component-state.py", Path(__file__).resolve())]
        inputs += [("fixture/" + name, PACKAGE / name) for name in package_files]
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
        outer = mod.Job(project, "component-state-probe", compiler)
        config, frozen_inputs, hashes = outer.snapshot()
        record["frozen_project_inputs"] = hashes
        if engine:
            require(record["engine_input"]["sha256"] == config["binding"]["sha256"], "Engine differs from admitted binding", "stale_input")
        with source_tool_environment():
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
        token = mod.digest(mod.canonical({"scenario": manifest["scenario"], "operation_id": outer.id,
                    "artifact": artifact["artifact_sha256"], "fixture": package_files, "expected": manifest,
                    "tool": outer.result["tool_sha256"], "plugin": record["plugin_file_set"]}))
        source, symbols = renderer(config, mapping, token)
        addon = work / "probe-addon"
        shutil.copytree(retained / "addon", addon)
        require(files(addon) == artifact["files"] and directories(addon) == parent_directories(artifact["files"]),
                "Copied generated addon differs from the immutable artifact manifest", "stale_input")
        bridge_path = addon / ("scripts/WorkbenchGameCommon/" + symbols["CLASS"] + ".c")
        require(not bridge_path.exists(), "Probe handler collides with generated artifact")
        write(bridge_path, source)
        require(files(retained) == record["original_artifact"]["files"], "Original artifact changed while preparing probe", "stale_input")
        staged = {**artifact["files"], bridge_path.relative_to(addon).as_posix(): mod.digest(source)}
        staged_dirs = parent_directories(staged)
        require(files(addon) == staged and directories(addon) == staged_dirs,
                "Prepared addon differs from manifest plus the exact trusted bridge", "stale_input")
        record.update(token=token, symbols=symbols, candidate_path=str(addon), staged_file_set=staged,
                      staged_directory_set=staged_dirs, staged_sha256=mod.digest(mod.canonical(staged)),
                      expected_checks=expected_checks, expected_rows=expected_rows, float_comparison=manifest["float_comparison"])
        record["scope"]["source_generation"] = "executed_success"

        def unchanged():
            outer.unchanged(hashes)
            require(files(PACKAGE) == package_files, "Fixture source set changed", "stale_input")
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
            record["engine_derived_outputs"] = derived

        unchanged()
        if not args.prepare_only:
            record["stage"] = "engine_compile"
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
            require(compiled.get("schema_version") == 1 and compiled.get("stage") == "workbench_compile" and
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
                record["stage"] = "engine_vm_manual_probe"
                runtime_path = work / "engine-runtime.json"
                try:
                    outer.run([host, "-NoProfile", "-File", mod.HERE / "scenario-engine-run.ps1", "-ToolRoot", toolroot,
                               "-ProjectDir", addon, "-ProjectId", config["addon"]["id"], "-ResultPath", runtime_path,
                               "-Token", token, "-Function", symbols["CLASS"], "-ExpectedEngineHash", config["binding"]["sha256"],
                               "-ExpectedEngineVersion", config["binding"]["version"]], "component_manual_probe", work, timeout=300)
                except mod.Failure as exc:
                    capture_adapter(record, "runtime", runtime_path)
                    raise failed_adapter(exc, record["raw_results"].get("runtime", {}).get("result")) from exc
                finally:
                    if "runtime" not in record["raw_results"]:
                        capture_adapter(record, "runtime", runtime_path)
                runtime = record["raw_results"].get("runtime", {}).get("result", {})
                require(runtime.get("schema_version") == 1 and runtime.get("stage") == "scenario_engine_execution" and
                        runtime.get("status") == "success" and runtime.get("engine_sha256") == config["binding"]["sha256"] and
                        runtime.get("engine_version") == config["binding"]["version"] and runtime.get("rpc", {}).get("Ok") is True,
                        "Missing matching engine VM execution evidence")
                session, loaded = runtime.get("session"), runtime.get("loaded_projects")
                require(type(session) is dict and session.get("reused") is False and session.get("project") == str(addon) and
                        type(session.get("process_id")) is int and session["process_id"] > 0 and
                        type(session.get("start_time")) is str and session["start_time"] and
                        type(loaded) is dict and loaded.get("Ok") is True and
                        type(loaded.get("Response")) is dict and
                        type(loaded["Response"].get("Loaded Projects")) is list and
                        config["addon"]["id"] in loaded["Response"]["Loaded Projects"],
                        "Missing owned runtime session or exact loaded addon identity")
                rows, checksum = scenarios.validate_wire(mod, runtime["rpc"]["Response"], token, list(CASE_IDS), expected_checks, len(expected_rows))
                require(rows == expected_rows, "Manual state observations differ from independent fixture values")
                write(work / "manual-trace.txt", ("\n".join(rows) + "\n").encode("ascii"))
                record["manual_comparison"] = {"status": "verified", "cases": len(CASE_IDS), "checks": expected_checks,
                    "rows": len(rows), "checksum": checksum, "trace": identity(work / "manual-trace.txt"), "complete_expected_case_set": True}
                record["scope"]["engine_vm_manual_probe"] = "executed_success"
                unchanged()
        record.update(status="success", stage="prepared" if args.prepare_only else record["stage"],
                      success_means="isolated source candidate prepared" if args.prepare_only else
                                    ("exact generated-component and member-box script compilation" if args.engine_stage == "compile" else "bounded plain member-box ABI observations match"))
    except BaseException as exc:
        status = getattr(exc, "status", "cancelled" if isinstance(exc, KeyboardInterrupt) else "failure")
        if status not in {"failure", "unavailable", "timeout", "cancelled", "stale_input"}:
            status = "failure"
        record.update(status=status, failure={"type": type(exc).__name__, "message": str(exc), "pointer": getattr(exc, "pointer", None)})
        raise
    finally:
        active_failure = sys.exc_info()[1]
        final_failure = None
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
        save_result(work / "results.json", record)
        print("Receipt: " + str(work / "results.json"), flush=True)
        if final_failure is not None and active_failure is None:
            raise mod.Failure("Final evidence retention or integrity check failed: " + str(final_failure), record["status"]) from final_failure


if __name__ == "__main__":
    main()
