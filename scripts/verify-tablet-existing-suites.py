#!/usr/bin/env python3
"""Compile or execute five preserved tablet suites in an isolated editor session.

Default prepares an exact copy of a successful tablet-suites-v1 candidate with a
trusted compiled identity handler. --run adds compilation and the five installed
suite requests. Never promotes files, changes policy, opens a world, enters play,
spawns a tablet, or treats direct handler tests as native input/lifecycle tests.
"""
from pathlib import Path
import argparse
import importlib.util
import json
import re
import shutil
import stat
import sys
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "scripts/verify-tablet-service-candidate.py"
SOURCE_SHA = "6f05262452a21705e9e14ff9c4d697481480b0568b47c84d3e9f0d8708f54ac0"
PROFILE = "sparkos.tablet.existing-suites-runtime.v1"
IDENTITY_PATH = "scripts/WorkbenchGameCommon/BerylTabletSuiteIdentity.c"
TEMPLATE = ROOT / "packages/sparkos/tablet-suites-runtime-probe/identity.c.in"
TRANSPORT = ROOT / "scripts/tablet-suites-engine.ps1"
CHECKER = ROOT / "scripts/verify-tablet-suite-runtime-receipts.py"
sys.dont_write_bytecode = True


def checked_module(path, expected=None):
    import hashlib
    raw = path.read_bytes()
    if expected is not None and hashlib.sha256(raw).hexdigest() != expected:
        raise RuntimeError("Installed source identity differs: " + str(path))
    spec = importlib.util.spec_from_file_location("tablet_suites_" + path.stem.replace("-", "_"), path)
    module = importlib.util.module_from_spec(spec)
    exec(compile(raw, str(path), "exec"), module.__dict__)
    return module


s1 = checked_module(SOURCE, SOURCE_SHA)
h, mod = s1.helpers, s1.mod
require, write, identity = h.require, h.write, h.identity


def checked_tree(path, expected, allow_cache=False):
    actual = h.files(path)
    derived = {}
    if allow_cache and "resourceDatabase.rdb" not in expected and "resourceDatabase.rdb" in actual:
        cache = path / "resourceDatabase.rdb"
        before = cache.stat(follow_symlinks=False)
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1, "Derived root cache must be a regular unlinked file", "stale_input")
        require(before.st_size <= 8 * 1024 * 1024, "Derived root resource cache exceeds bound", "unavailable")
        item = identity(cache)
        after = cache.stat(follow_symlinks=False)
        require((before.st_dev, before.st_ino, before.st_nlink, before.st_size, before.st_mtime_ns) ==
                (after.st_dev, after.st_ino, after.st_nlink, after.st_size, after.st_mtime_ns),
                "Derived cache changed during its observed read", "stale_input")
        derived["resourceDatabase.rdb"] = item
        del actual["resourceDatabase.rdb"]
    require(actual == expected and h.directories(path) == h.parent_directories(expected),
            "Exact staged input tree changed", "stale_input")
    return derived


def validate_source_receipt(value):
    require(type(value) is dict and type(value.get("schema_version")) is int and value["schema_version"] == 1 and
            value.get("operation") == "verify.tablet_service.source_candidate" and value.get("status") == "success" and
            value.get("stage") == "engine_compile" and value.get("candidate_profile") == "tablet-suites-v1",
            "Successful exact tablet-suites-v1 compilation receipt required")
    require(all(type(value.get(key)) is dict for key in
                ("scope", "suite_selection", "raw_results", "source_profile", "original_artifact", "job", "source_build_result",
                 "generated_source_map", "adapter_source_map", "source_build_job_files")),
            "Malformed source receipt evidence structures")
    require(value.get("scope", {}).get("tablet_suite_execution") == "not_run" and
            value.get("suite_selection", {}).get("status") == "declared_not_executed" and
            type(value["suite_selection"].get("executed")) is int and value["suite_selection"]["executed"] == 0,
            "Source receipt must distinguish suites from compilation")
    profile = s1.validate_suite_profile(value.get("tablet_suite_profile"))
    require(value.get("candidate_addon") == profile["addon"] and value["suite_selection"].get("requests") == profile["suite_selections"],
            "Source candidate identity or suite selection differs")
    staged = value.get("staged_file_set")
    require(type(staged) is dict and len(staged) == 86 and all(type(k) is str and type(v) is str and s1.HASH.fullmatch(v)
            for k, v in staged.items()) and mod.digest(mod.canonical(staged)) == value.get("staged_sha256"),
            "Exact eighty-six source identities required")
    source_profile = s1.source_profile()
    require(mod.canonical(value["source_profile"]) == mod.canonical(source_profile), "Source profile differs from installed admission", "stale_input")
    require(set(staged) == set(source_profile["scripts"]) | set(profile["resources"]) |
            {"addon.gproj", "scripts/Game/Beryl/Beryl_Generated.c"}, "Source paths differ from exact installed source set")
    require(value.get("generated_file") == "scripts/Game/Beryl/Beryl_Generated.c", "Generated file path differs")
    require(all(staged[name] == sha for name, sha in source_profile["scripts"].items() if name != s1.TABLET),
            "Unchanged MESH source identity differs", "stale_input")
    for name, item in profile["resources"].items():
        require(staged.get(name) == item["sha256"], "Resource identity differs from installed profile", "stale_input")
    require(type(value["raw_results"].get("compile")) is dict, "Raw compilation envelope is missing")
    compiled = value["raw_results"]["compile"].get("result")
    require(s1.compile_success(compiled), "Source candidate lacks successful exact compilation")
    require(compiled.get("engine_sha256") == value.get("source_profile", {}).get("engine_sha256") and
            compiled.get("engine_version") == value["source_profile"].get("engine_version"), "Source engine identity differs")
    require(type(value.get("verification_inputs")) is dict and value["verification_inputs"] and
            type(value.get("retained_input_files")) is dict and len(value["retained_input_files"]) == 140 and
            type(value.get("raw_engine_logs")) is list and value["raw_engine_logs"], "Source input/log retention is incomplete")
    require(len(value["verification_inputs"]) <= 256 and all(type(name) is str and type(item) is dict and
            set(item) == {"path", "bytes", "sha256"} and item["path"] == name and type(item["bytes"]) is int and
            0 <= item["bytes"] <= 16 * 1024 * 1024 and type(item["sha256"]) is str and s1.HASH.fullmatch(item["sha256"])
            for name, item in value["verification_inputs"].items()), "Malformed bounded verification input identity")
    require(type(value.get("commands")) is list and len(value["commands"]) == 2 and
            all(type(row) is dict and type(row.get("stdout")) is str and type(row.get("stderr")) is str and
                type(row.get("stdout_sha256")) is str and s1.HASH.fullmatch(row["stdout_sha256"]) and
                type(row.get("stderr_sha256")) is str and s1.HASH.fullmatch(row["stderr_sha256"])
                for row in value["commands"]), "Malformed source command ledger")
    return profile


def verify_prior(work, receipt, receipt_identity):
    require(identity(work / "results.json") == receipt_identity, "Original source receipt changed", "stale_input")
    require(h.files(work / "inputs") == receipt["retained_input_files"], "Original retained inputs changed", "stale_input")
    for name, item in receipt["verification_inputs"].items():
        require(identity(Path(name)) == item, "Original verification input changed: " + name, "stale_input")
    mesh_projects = [Path(name).parent for name, item in receipt["verification_inputs"].items()
                     if Path(name).name == "addon.gproj" and item["sha256"] == receipt["source_profile"]["addon_gproj_sha256"]]
    require(len(mesh_projects) == 1 and s1.mesh_sources(mesh_projects[0]) == receipt["source_profile"]["scripts"],
            "MESH source selection changed", "stale_input")
    require(h.files(s1.PACKAGE) == {p.relative_to(s1.PACKAGE).as_posix(): item["sha256"]
            for name, item in receipt["verification_inputs"].items() if (p := Path(name)).is_relative_to(s1.PACKAGE)},
            "Installed source candidate package selection changed", "stale_input")
    require(Path(receipt["candidate_path"]).resolve(strict=True) == work / "candidate-addon", "Source candidate escaped its owned directory")
    checked_tree(work / "candidate-addon", receipt["staged_file_set"], True)
    original = receipt["original_artifact"]
    for path in (Path(original["path"]), Path(original["retained"])):
        require(path.resolve(strict=True).is_relative_to(work), "Original artifact escaped its source job")
        require(h.files(path) == original["files"] and h.directories(path) == original["directories"], "Original immutable artifact changed", "stale_input")
    for name in receipt["tablet_suite_profile"]["resources"]:
        retained = work / "inputs/mesh-resources" / name
        require(mod.digest(mod.read(retained)) == receipt["staged_file_set"][name], "Retained resource changed", "stale_input")
    for row in receipt["raw_engine_logs"]:
        current = h.streamed_identity(Path(row["retained"]))
        require(current["sha256"] == row["sha256"] and current["bytes"] == row["bytes"], "Original raw engine log changed", "stale_input")
    source_job = Path(receipt["source_build_result"]["result_path"]).parent
    require(source_job.resolve(strict=True).is_relative_to(work / "project/.beryl-mod/jobs") and
            h.files(source_job) == receipt["source_build_job_files"] and
            h.files(work / "source-build-job") == receipt["source_build_job_files"], "Original source build job changed", "stale_input")
    require(mod.parse(mod.read(source_job / "result.json")) == receipt["source_build_result"],
            "Original source build receipt differs from embedded evidence", "stale_input")
    outer_path = Path(receipt["job"]["result_path"])
    require(outer_path.resolve(strict=True).is_relative_to(work / "project/.beryl-mod/jobs") and
            mod.parse(mod.read(outer_path)) == receipt["job"], "Original outer job receipt changed", "stale_input")
    compiled = receipt["raw_results"]["compile"]
    require(Path(compiled["path"]).resolve(strict=True) == work / "engine-compile.json" and
            identity(Path(compiled["path"])) == {k: compiled[k] for k in ("path", "bytes", "sha256")} and
            mod.parse(mod.read(Path(compiled["path"]))) == compiled["result"], "Original raw compilation receipt changed", "stale_input")
    require(receipt["commands"] == receipt["job"]["raw_logs"], "Original command ledger differs")
    for command in receipt["commands"]:
        for stream in ("stdout", "stderr"):
            path = Path(command[stream])
            require(path.resolve(strict=True).is_relative_to(work / "project/.beryl-mod/jobs") and
                    h.streamed_identity(path)["sha256"] == command[stream + "_sha256"], "Original process log changed", "stale_input")
    for key in ("generated_source_map", "adapter_source_map"):
        row = receipt[key]
        require(identity(Path(row["path"])) == row, "Original source mapping changed", "stale_input")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-receipt", type=Path, required=True)
    parser.add_argument("--expect-receipt-sha256", required=True)
    parser.add_argument("--powershell-host", type=Path)
    parser.add_argument("--engine-exe", type=Path)
    parser.add_argument("--workbench-tools", type=Path)
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args()
    source_receipt = args.candidate_receipt.resolve(strict=True)
    require(source_receipt.is_relative_to(ROOT / "build") and source_receipt.name == "results.json" and
            s1.HASH.fullmatch(args.expect_receipt_sha256) and mod.digest(mod.read(source_receipt)) == args.expect_receipt_sha256,
            "Pinned successful source receipt under build required", "stale_input")
    work = Path(tempfile.mkdtemp(prefix="tablet existing suites & spaces-", dir=ROOT / "build"))
    print("Tablet suite evidence: " + str(work), flush=True)
    record = {"schema_version": 1, "operation": "verify.tablet_existing_suites", "profile": PROFILE,
              "status": "failure", "stage": "prepare", "commands": [], "raw_results": {}, "evidence_errors": [],
              "scope": {"source_generation": "reused_exact_prior_artifact", "engine_compilation": "not_run",
                        "existing_tablet_suites": "not_run", "world_open": "not_run", "play": "not_run",
                        "native_tablet_callbacks": "not_run", "physical_input": "not_run", "multiplayer": "not_run",
                        "service_lifetime": "unverified", "resource_binary_closure": "unverified",
                        "visual_review": "not_run", "installation": "unchanged", "policy_changes": "not_run"},
              "limitation": "Five source-defined suite responses only; no individual assertion count, real equip/stow/lifecycle, native mouse events, leak freedom or multiplayer acceptance."}
    job, guard = None, None
    try:
        prior = mod.parse(mod.read(source_receipt))
        profile = validate_source_receipt(prior)
        prior_identity = identity(source_receipt)
        verify_prior(source_receipt.parent, prior, prior_identity)
        write(work / "source-candidate-result.json", mod.read(source_receipt))
        record["source_candidate_result"] = prior_identity
        host = args.powershell_host.resolve(strict=True) if args.powershell_host else None
        engine = args.engine_exe.resolve(strict=True) if args.engine_exe else None
        toolroot = args.workbench_tools.resolve(strict=True) if args.workbench_tools else None
        require(not args.run or (host is not None and engine is not None and toolroot is not None), "Engine run requires explicit installed tools", "unavailable")
        compiler_inputs = [Path(name) for name in prior["verification_inputs"] if name.endswith("beryl.exe")]
        require(len(compiler_inputs) == 1, "Private compiler identity is ambiguous")
        compiler = compiler_inputs[0]
        require(compiler.is_relative_to(ROOT / "build") and compiler.parent != ROOT / "build", "Active compiler is forbidden")
        tracked_paths = [Path(__file__).resolve(), SOURCE, TEMPLATE, CHECKER, TRANSPORT]
        if args.run:
            tracked_paths += [host, mod.HERE / "engine-compile.ps1"]
            plugins = sorted((toolroot / "scripts").glob("*.ps1"))
            require(0 < len(plugins) <= 128, "Installed plugin inventory outside bounds", "unavailable")
            tracked_paths += plugins
        tracked = {str(p): identity(p) for p in tracked_paths}
        for index, p in enumerate(tracked_paths):
            write(work / "inputs" / (str(index).zfill(4) + "-" + p.name), mod.read(p))
        record["verification_inputs"] = tracked
        mesh_projects = [Path(name).parent for name, item in prior["verification_inputs"].items()
                         if Path(name).name == "addon.gproj" and item["sha256"] == prior["source_profile"]["addon_gproj_sha256"]]
        require(len(mesh_projects) == 1, "Live resource source project is ambiguous")
        resource_snapshot, resource_receipt = s1.capture_suite_resources(mesh_projects[0], work / "inputs/mesh-resources", profile)
        record["resource_source_snapshot"] = resource_receipt
        if engine:
            record["engine_input"] = h.streamed_identity(engine)
            require(record["engine_input"]["sha256"] == prior["source_profile"]["engine_sha256"], "Pinned engine differs", "stale_input")
        token = mod.digest(mod.canonical({"operation": PROFILE, "source_receipt": args.expect_receipt_sha256,
                                        "verifier": tracked[str(Path(__file__).resolve())]["sha256"], "nonce": uuid.uuid4().hex}))
        source_hash = prior["staged_sha256"]
        template = mod.read(TEMPLATE).decode("utf-8")
        text = template.replace("@TOKEN@", token).replace("@SOURCE_SHA256@", source_hash)
        require(not re.search(r"@[A-Z_]+@", text), "Unresolved identity source placeholder")
        addon = work / "candidate-addon"
        for name in sorted(prior["staged_file_set"]):
            write(addon / name, mod.read(Path(prior["candidate_path"]) / name))
        write(addon / IDENTITY_PATH, text.encode("utf-8"))
        expected = dict(prior["staged_file_set"])
        require(IDENTITY_PATH not in expected, "Identity helper conflicts with candidate source")
        expected[IDENTITY_PATH] = mod.digest(text.encode("utf-8"))
        require(len(expected) == 87, "Exact derived eighty-seven input tree required")
        checked_tree(addon, expected)
        manifest = {"schema_version": 1, "profile": PROFILE, "files": expected}
        h.save_result(work / "input-manifest.json", manifest)
        manifest_identity = identity(work / "input-manifest.json")
        record.update(token=token, source_sha256=source_hash, staged_sha256=mod.digest(mod.canonical(expected)),
                      staged_file_set=expected, input_manifest=manifest_identity, candidate_path=str(addon),
                      candidate_addon=profile["addon"], suite_selections=profile["suite_selections"])
        own_inputs = h.files(work / "inputs")
        record["retained_input_files"] = own_inputs

        def unchanged():
            verify_prior(source_receipt.parent, prior, prior_identity)
            require(identity(work / "source-candidate-result.json")["sha256"] == prior_identity["sha256"], "Retained source receipt changed", "stale_input")
            for name, item in tracked.items():
                require(identity(Path(name)) == item, "New verification source changed: " + name, "stale_input")
            require(h.files(work / "inputs") == own_inputs and identity(work / "input-manifest.json") == manifest_identity,
                    "New retained evidence inputs changed", "stale_input")
            s1.verify_suite_resources(resource_snapshot)
            if engine:
                require(h.streamed_identity(engine) == record["engine_input"], "Engine identity changed", "stale_input")
            if args.run:
                require(sorted(p.name for p in (toolroot / "scripts").glob("*.ps1")) == [p.name for p in plugins], "Plugin selection changed", "stale_input")
            if record.get("runtime_expected"):
                require(identity(Path(record["runtime_expected"]["path"])) == record["runtime_expected"],
                        "Predeclared runtime expectation changed", "stale_input")
            record["engine_derived_outputs"] = checked_tree(addon, expected, True)
        guard = unchanged
        guard()
        if not args.run:
            record.update(status="success", stage="prepared", success_means="exact derived source candidate; no engine executed")
            return
        project = work / "project"
        for name in ("beryl.mod.json", "src/lifecycle.be"):
            write(project / name, mod.read(source_receipt.parent / "project" / name))
        job = mod.Job(project, "tablet-existing-suites", compiler)
        job.snapshot()
        record["stage"] = "engine_compile"
        compile_path = work / "engine-compile.json"
        record["scope"]["engine_compilation"] = "attempted_unconfirmed"
        try:
            job.run([host, "-NoProfile", "-File", mod.HERE / "engine-compile.ps1", "-ToolRoot", toolroot,
                     "-ProjectDir", addon, "-ResultPath", compile_path, "-ExpectedVersion", prior["source_profile"]["engine_version"]],
                    "tablet_suite_engine_compile", work, timeout=300)
        except mod.Failure as exc:
            h.capture_adapter(record, "compile", compile_path)
            raise h.failed_adapter(exc, record["raw_results"].get("compile", {}).get("result")) from exc
        finally:
            if "compile" not in record["raw_results"]:
                h.capture_adapter(record, "compile", compile_path)
        compiled = record["raw_results"].get("compile", {}).get("result")
        require(s1.compile_success(compiled), "Derived candidate compilation lacks exact success")
        require(compiled.get("engine_sha256") == record["engine_input"]["sha256"] and
                compiled.get("engine_version") == prior["source_profile"]["engine_version"] and
                compiled.get("tools") == {name: tracked[str(toolroot / "scripts" / name)]["sha256"] for name in h.COMPILE_TOOLS},
                "Compile engine/tool identity differs", "stale_input")
        record["compile_logs"] = h.retain_engine_logs(work, compiled)
        require(record["compile_logs"], "Raw engine compilation logs missing", "unavailable")
        record["scope"]["engine_compilation"] = "executed_success"
        guard()
        runtime_path = work / "engine-runtime.json"
        record["stage"] = "engine_suites"
        record["scope"]["existing_tablet_suites"] = "attempted_unconfirmed"
        expected_runtime = {"token": token, "profile": PROFILE, "source_sha256": source_hash,
                            "project_dir": str(addon), "project_id": profile["addon"]["id"], "engine": record["engine_input"],
                            "engine_version": prior["source_profile"]["engine_version"],
                            "tools": {name: tracked[str(toolroot / "scripts" / name)]["sha256"]
                                      for name in ("Find-Workbench.ps1", "Invoke-WorkbenchRpc.ps1")},
                            "manifest_path": str(work / "input-manifest.json"), "manifest_sha256": manifest_identity["sha256"],
                            "manifest": manifest, "adapter_sha256": tracked[str(TRANSPORT)]["sha256"],
                            "argv": ["-gproj", str(addon / "addon.gproj"), "-noOpenLastResource", "-scriptAuthorizeAll",
                                     "-wbmodule=WorldEditor", "-run"]}
        h.save_result(work / "runtime-expected.json", expected_runtime)
        record["runtime_expected"] = identity(work / "runtime-expected.json")
        guard()
        try:
            job.run([host, "-NoProfile", "-File", TRANSPORT, "-ToolRoot", toolroot, "-ProjectDir", addon,
                     "-ProjectId", profile["addon"]["id"], "-InputManifest", work / "input-manifest.json",
                     "-InputManifestHash", manifest_identity["sha256"], "-ResultPath", runtime_path,
                     "-Token", token, "-ExpectedSourceHash", source_hash, "-ExpectedEnginePath", engine,
                     "-ExpectedEngineHash", record["engine_input"]["sha256"], "-ExpectedEngineVersion", prior["source_profile"]["engine_version"]],
                    "tablet_suite_runtime", work, timeout=210)
        except mod.Failure as exc:
            h.capture_adapter(record, "runtime", runtime_path)
            raise h.failed_adapter(exc, record["raw_results"].get("runtime", {}).get("result")) from exc
        finally:
            if "runtime" not in record["raw_results"]:
                h.capture_adapter(record, "runtime", runtime_path)
        runtime = record["raw_results"].get("runtime", {}).get("result")
        checker = checked_module(CHECKER, tracked[str(CHECKER)]["sha256"])
        comparison = checker.validate_runtime(runtime, expected_runtime)
        record["suite_verification"] = comparison
        guard()
        record["scope"]["existing_tablet_suites"] = "executed_success"
        record.update(status="success", stage="engine_suites_complete", success_means="five exact preserved source-suite responses; full lifecycle remains unverified")
    except BaseException as exc:
        status = getattr(exc, "status", "cancelled" if isinstance(exc, KeyboardInterrupt) else "failure")
        record.update(status=status if status in s1.STATUSES else "failure", failure={"type": type(exc).__name__, "message": str(exc)})
        raise
    finally:
        active, final = sys.exc_info()[1], None
        try:
            if guard:
                guard()
        except BaseException as exc:
            final = exc
            record["final_integrity_failure"] = {"type": type(exc).__name__, "message": str(exc)}
            if record["status"] == "success":
                record["status"] = "stale_input"
        if job:
            record["commands"] = job.result["raw_logs"]
            try:
                for command in record["commands"]:
                    for stream in ("stdout", "stderr"):
                        p = Path(command[stream])
                        if p.is_file():
                            command[stream + "_sha256"] = h.streamed_identity(p)["sha256"]
                job.result.update(status=record["status"], stage=record["stage"])
                h.save_result(job.path / "result.json", job.result)
            except BaseException as exc:
                final = exc
                record["evidence_errors"].append({"stage": "process_retention", "type": type(exc).__name__, "message": str(exc)})
                if record["status"] == "success":
                    record["status"] = "failure"
            record["job"] = job.result
        try:
            if "compile_logs" not in record:
                record["compile_logs"] = h.retain_engine_logs(work, record["raw_results"].get("compile", {}).get("result"))
            require(not record["evidence_errors"] or record["status"] != "success", "Incomplete evidence cannot count as success")
        except BaseException as exc:
            final = exc
            record["evidence_errors"].append({"stage": "compile_log_retention", "type": type(exc).__name__, "message": str(exc)})
            if record["status"] == "success":
                record["status"] = "failure"
        try:
            h.save_result(work / "results.json", record)
        except BaseException as exc:
            final = exc
            record["status"] = "failure"
            print("Result retention failed: " + str(exc), file=sys.stderr, flush=True)
        print("Receipt: " + str(work / "results.json"), flush=True)
        if final is not None and active is None:
            raise mod.Failure("Final source integrity failed: " + str(final), record["status"]) from final


if __name__ == "__main__":
    main()
