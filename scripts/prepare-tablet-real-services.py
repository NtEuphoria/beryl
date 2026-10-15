#!/usr/bin/env python3
"""Stage a separately pinned N1a fixture; optionally headless-compile it.

No runtime launch, callback delivery, installation, or live MESH write is provided.
The source-only observer and reversible hooks have independent fixture gates.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys
import tempfile

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "packages/sparkos/tablet-real-service-probe"
PREPARER = ROOT / "scripts/prepare-tablet-native-callbacks.py"
PREPARER_SHA = "62bb44d64e4fb830777196855eb8febdf0df3afa2cb3c86e7c900c62090e9471"
SOURCE = ROOT / "build/tablet native preparation & spaces-flxq8l36/results.json"
SOURCE_SHA = "4f5250df9a163cb91c362345c848d997d7fb9c096a654d0805052b015cd4e424"
INSTRUMENTER_SHA = "0754460a8ca606eb8ef7030ea234c3410400a4340c9ee720ac0117dd3249d1c4"
CONTRACT_SHA = "74aed85740e8d72b5c187eae9b537fffb921b90ec24ac0002500379897e8cd65"
PROJECT_ID = "BerylTabletRealServicesN1aPrototype"
PROJECT_GUID = "BE71571C20261010"
OBSERVER_PATH = "scripts/Game/BerylTabletRealServicesN1aObserver.c"
ASSETS = {
    "Prefabs/BerylTabletRealServicesN1a.et": b"GenericEntity {\n components {\n  SPK_BerylTabletRealServicesObserver {\n  }\n }\n}\n",
    "Prefabs/BerylTabletRealServicesN1a.et.meta": b'MetaFileClass {\n Name "{BE71571B20261010}Prefabs/BerylTabletRealServicesN1a.et"\n Configurations {\n  EntityTemplateResourceClass PC {\n  }\n }\n}\n',
    "worlds/BerylTabletRealServicesN1a.ent": b"Layer default {\n Index 0\n}\n",
    "worlds/BerylTabletRealServicesN1a.ent.meta": b'MetaFileClass {\n Name "{BE71571A20261010}worlds/BerylTabletRealServicesN1a.ent"\n Configurations {\n  ENTResourceClass PC {\n  }\n  ENTResourceClass HEADLESS : PC {\n  }\n }\n}\n',
    "worlds/BerylTabletRealServicesN1a_Layers/default.layer": b"GenericWorldEntity world {\n}\n",
}
HOST = Path("C:/Users/moham/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/powershell/pwsh.exe")
HOST_SHA = "362a356ce7f0940ec74f73a8fc2c990a2cc24a38a11c90bbd8eca947110ad139"
ENGINE = Path("C:/Program Files (x86)/Steam/steamapps/common/Arma Reforger Tools/Workbench/ArmaReforgerWorkbenchSteamDiag.exe")
ENGINE_SHA = "7dd36ca1f662b0c13669a4f2f7f10e3c461c2906b021e742272d64b3ab7e9798"
TOOLROOT = Path("C:/Users/moham/Desktop/reforger-workbench-plugin")
COMPILER = ROOT / "build/oct08-wrapper-cli-l8ci669v/beryl.exe"
COMPILER_SHA = "76aeaacfea6866e66e3020f983eaa22089d545ad0f3b60fedfd28c3d58972bd7"
COMPILE_SHA = "ea923399c2060123812a6ea205760372de0e2fff29071117e0cf58ed64877121"


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def loaded(name, path, expected):
    raw = path.read_bytes()
    if digest(raw) != expected:
        raise RuntimeError("Pinned executable Python source differs: " + str(path))
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    exec(compile(raw, str(path), "exec"), value.__dict__)
    return value


def expanded(raw, symbols):
    text = raw.decode("utf8", "strict")
    for name, actual in symbols.items():
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", actual):
            raise ValueError("Unsafe declaration linkage")
        text = text.replace("@" + name + "@", actual)
    if re.search(r"@[A-Z_]+@", text):
        raise ValueError("Unresolved trusted fixture placeholder")
    return text.encode("utf8")


def classify_compile(record):
    """Add scope from an actual adapter outcome; never turn failure into success."""
    value = record.get("raw_results", {}).get("compile", {}).get("result")
    if type(value) is not dict or type(value.get("schema_version")) is not int or value["schema_version"] != 1 or value.get("stage") != "workbench_compile":
        return
    detail = value.get("result")
    if type(detail) is not dict:
        return
    if detail.get("Stage") == "Compiled" and type(detail.get("Ok")) is bool and type(detail.get("ExitCode")) is int and type(detail.get("ErrorCount")) is int:
        if detail["Ok"] is True and detail["ExitCode"] == 0 and detail["ErrorCount"] == 0:
            record["scope"]["engine_compilation"] = "executed_success"
        elif detail["Ok"] is False and (detail["ExitCode"] != 0 or detail["ErrorCount"] > 0):
            record["scope"]["engine_compilation"] = "executed_failure"
    elif detail.get("Stage") == "DidNotStart":
        record["scope"]["engine_compilation"] = "startup_unavailable"
    elif detail.get("Stage") == "Timeout":
        record["scope"]["engine_compilation"] = "timeout_incomplete"


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--expect-package-sha256", required=True)
    cli.add_argument("--compile", action="store_true", help="Only headless compilation; never runtime")
    args = cli.parse_args()
    if not re.fullmatch(r"[0-9a-f]{64}", args.expect_package_sha256):
        cli.error("Full frozen package digest required")
    work = Path(tempfile.mkdtemp(prefix="tablet-real-services-preparation-", dir=ROOT / "build"))
    record = {"schema_version": 1, "operation": "prepare.tablet_real_services.n1a", "status": "failure",
              "stage": "source_admission", "commands": [], "raw_results": {}, "evidence_errors": [],
              "scope": {"source_preparation": "attempted", "engine_compilation": "not_run", "native_initialization": "not_run",
                        "public_actions": "not_run", "screen_services": "not_run", "ui": "not_admitted", "profile_isolation": "unverified",
                        "gadget": "not_admitted", "deletion": "not_admitted", "multiplayer": "not_run", "visual_review": "not_run",
                        "runtime_transport": "not_installed", "installation": "unchanged"}}
    p = job = guard = None
    try:
        p = loaded("n1a_prior_preparer", PREPARER, PREPARER_SHA)
        h, mod = p.h, p.mod
        require = h.require
        raw = mod.read(SOURCE)
        require(digest(raw) == SOURCE_SHA, "Pinned N0 preparation receipt differs", "stale_input")
        prior = mod.parse(raw)
        require(prior["status"] == "success" and prior["stage"] == "source_prepared" and len(prior["staged_file_set"]) == 92,
                "Exact successful N0 source preparation required")
        source_files = dict(prior["prepared_file_set"], **{"results.json": SOURCE_SHA})
        require(h.files(SOURCE.parent) == source_files and set(h.directories(SOURCE.parent)) == set(h.parent_directories(source_files)),
                "Retained N0 preparation tree differs", "stale_input")
        for path, item in prior["verification_inputs"].items():
            require(h.identity(Path(path)) == item, "Prior source preparation input differs: " + path, "stale_input")
        package_files = h.files(PACKAGE)
        require(mod.digest(mod.canonical(package_files)) == args.expect_package_sha256,
                "Frozen N1a package selection differs", "stale_input")
        require(h.directories(PACKAGE) == h.parent_directories(package_files) and len(package_files) <= 32,
                "N1a package namespace differs")
        contract_raw = mod.read(PACKAGE / "contract.json")
        require(digest(contract_raw) == CONTRACT_SHA, "Typed oracle contract differs", "stale_input")
        contract = mod.parse(contract_raw)
        for item in contract["source_basis"]:
            require(h.identity(ROOT / item["path"]) == {"path": str(ROOT / item["path"]), "bytes": item["bytes"], "sha256": item["sha256"]},
                    "Original source/oracle basis differs", "stale_input")
        instrumenter = loaded("n1a_reversible_instrumenter", PACKAGE / "instrument_adapter.py", INSTRUMENTER_SHA)
        source_payloads = {}
        for name, sha in prior["staged_file_set"].items():
            payload = mod.read(Path(prior["candidate_path"]) / name)
            require(digest(payload) == sha, "Prior candidate bytes differ", "stale_input")
            source_payloads[name] = payload
        mapping_bytes = mod.read(SOURCE.parent / "generated_source_map.json")
        require(digest(mapping_bytes) == source_files["generated_source_map.json"], "Captured generated source-map bytes differ", "stale_input")
        mapping = mod.parse(mapping_bytes)
        require(h.identity(Path(prior["observer_source_map"]["path"])) == prior["observer_source_map"], "N0 observer mapping differs")
        generated_name = prior["generated_file"]["path"]
        rendered, symbols, unused = p.s1.render(mapping, source_payloads[generated_name])
        require(rendered == source_payloads[p.s1.TABLET], "Actual original rendered adapter differs", "stale_input")
        symbols.update(prior["symbols"])
        original_template = mod.read(instrumenter.SOURCE)
        instrumented = instrumenter.instrument_adapter(original_template)
        require(expanded(instrumenter.strip_instrumentation(instrumented), symbols) == rendered,
                "Removing hooks does not reconstruct the complete production adapter")
        observer_template = mod.read(PACKAGE / "observer.c.in")
        require(digest(observer_template) == package_files["observer.c.in"], "Captured trusted observer bytes differ", "stale_input")
        observer = expanded(observer_template, symbols)
        source_payloads[p.s1.TABLET] = expanded(instrumented, symbols)
        source_payloads[OBSERVER_PATH] = observer
        addon_profile = dict(prior["source_contract"]["addon"])
        addon_profile.update(id=PROJECT_ID, guid=PROJECT_GUID, title="Beryl Tablet Real Services N1a Experimental")
        config = 'GameProject {\n ID "' + addon_profile["id"] + '"\n GUID "' + addon_profile["guid"] + '"\n TITLE "' + addon_profile["title"] + '"\n Dependencies {\n'
        for dependency in addon_profile["dependencies"]:
            config += '  "' + dependency + '"\n'
        source_payloads["addon.gproj"] = (config + ' }\n}\n').encode("utf8")
        for name, payload in ASSETS.items():
            require(name not in source_payloads, "Fixture path collision")
            for existing in source_payloads.values():
                if name.endswith(".meta"):
                    for identifier in re.findall(rb"\{[0-9A-F]{16}\}", payload):
                        require(identifier not in existing, "Fixture resource ID collision")
            source_payloads[name] = payload
        require(len(source_payloads) == 98, "Exact 98-file headless N1a candidate required")
        preserved = {name: sha for name, sha in prior["staged_file_set"].items() if name not in ("addon.gproj", p.s1.TABLET)}
        require(all(digest(source_payloads[name]) == sha for name, sha in preserved.items()), "Preserved prior payload differs")
        require(sum(len(re.findall(rb"\bclass\s+SPK_TabletComponent\s*:\s*ScriptComponent\b", data))
                    for name, data in source_payloads.items() if name.endswith(".c")) == 1, "Production tablet definition is not unique")
        addon = work / "candidate-addon"
        for name, payload in source_payloads.items():
            h.write(addon / name, payload)
        expected = {name: digest(data) for name, data in source_payloads.items()}
        p.prior_guard.checked_tree(addon, expected)
        tracked_paths = [Path(__file__).resolve(), PREPARER] + [PACKAGE / name for name in sorted(package_files)]
        tracked_paths += sorted(path for path in mod.HERE.glob("*") if path.is_file() and path.suffix in (".py", ".json", ".ps1"))
        tracked_paths += sorted((TOOLROOT / "scripts").glob("*.ps1"))
        if args.compile:
            tracked_paths += [HOST, COMPILER]
        require(len(tracked_paths) == len(set(tracked_paths)) and len(tracked_paths) <= 256,
                "Bounded distinct N1a verification input selection required")
        tracked = {str(path): h.identity(path) for path in tracked_paths}
        for index, path in enumerate(tracked_paths):
            captured = mod.read(path)
            require(digest(captured) == tracked[str(path)]["sha256"] and len(captured) == tracked[str(path)]["bytes"],
                    "Captured N1a verification input differs", "stale_input")
            h.write(work / "inputs" / (str(index).zfill(3) + "-" + path.name), captured)
        h.write(work / "source-preparation-result.json", raw)
        h.write(work / "generated-source-map.json", mapping_bytes)
        h.save_result(work / "instrumented-adapter-origins.json", instrumenter.origin_map(original_template))
        h.save_result(work / "observer-source-map.json", {"schema_version": 1, "kind": "trusted_fixture_line_origins",
                      "source": h.identity(PACKAGE / "observer.c.in"), "generated_path": OBSERVER_PATH,
                      "generated_sha256": expected[OBSERVER_PATH], "columns": "unavailable_after_placeholder_expansion",
                      "lines": [{"generated_line": i, "source_line": i} for i in range(1, len(observer.splitlines()) + 1)]})
        retained_evidence = {name: h.identity(work / name) for name in
                             ("source-preparation-result.json", "generated-source-map.json", "instrumented-adapter-origins.json", "observer-source-map.json")}
        record.update(source_preparation=h.identity(SOURCE), candidate_path=str(addon), staged_file_set=expected,
                      staged_directory_set=h.directories(addon), staged_sha256=mod.digest(mod.canonical(expected)),
                      package_sha256=args.expect_package_sha256, package_files=package_files, verification_inputs=tracked,
                      retained_input_files=h.files(work / "inputs"), retained_evidence=retained_evidence,
                      source_profile=contract["profile"], project=addon_profile,
                      linkage=symbols, preserved_prior_files=preserved, expected_runtime_case_ids=[row["id"] for row in contract["cases"]],
                      instrumentation=instrumenter.validate_instrumented(instrumented, original_template),
                      native_observer_execution="not_run", source_contract_sha256=CONTRACT_SHA)

        def unchanged():
            require(h.files(SOURCE.parent) == source_files and set(h.directories(SOURCE.parent)) == set(h.parent_directories(source_files)),
                    "Prior retained preparation changed", "stale_input")
            for path, item in prior["verification_inputs"].items():
                require(h.identity(Path(path)) == item, "Prior input changed", "stale_input")
            for path, item in tracked.items():
                require(h.identity(Path(path)) == item, "N1a source changed", "stale_input")
            require(h.files(PACKAGE) == package_files and h.files(work / "inputs") == record["retained_input_files"],
                    "Package or retained source set changed", "stale_input")
            for name, item in retained_evidence.items():
                require(h.identity(work / name) == item, "Retained N1a origin/source evidence changed", "stale_input")
            if "engine_input" in record:
                require(h.streamed_identity(ENGINE) == record["engine_input"], "Selected native engine changed", "stale_input")
            record["engine_derived_outputs"] = p.prior_guard.checked_tree(addon, expected, True)
            if job:
                job.unchanged(job.input_hashes)

        guard = unchanged
        guard()
        record["scope"]["source_preparation"] = "verified_source_only"
        record["stage"] = "source_prepared"
        if args.compile:
            compile_adapter = mod.HERE / "engine-compile.ps1"
            for path, sha in ((HOST, HOST_SHA), (COMPILER, COMPILER_SHA), (compile_adapter, COMPILE_SHA)):
                require(h.identity(path)["sha256"] == sha, "Pinned compile tool differs", "stale_input")
            engine_identity = h.streamed_identity(ENGINE)
            require(engine_identity["sha256"] == ENGINE_SHA, "Pinned engine differs", "stale_input")
            record["engine_input"] = engine_identity
            project = work / "project"
            for name in ("beryl.mod.json", "src/lifecycle.be"):
                h.write(project / name, mod.read(ROOT / "build/tablet service & spaces-soii5z39/project" / name))
            job = mod.Job(project, "tablet-real-services-headless", COMPILER)
            job.snapshot()
            compile_result = work / "engine-compile.json"
            record["scope"]["engine_compilation"] = "attempted_unconfirmed"
            record["stage"] = "engine_compile"
            try:
                job.run([HOST, "-NoProfile", "-File", compile_adapter, "-ToolRoot", TOOLROOT,
                         "-ProjectDir", addon, "-ResultPath", compile_result, "-ExpectedVersion", "1.8.0.13"],
                        "tablet_real_services_headless_compile", work, timeout=300)
            except mod.Failure as error:
                h.capture_adapter(record, "compile", compile_result)
                raise h.failed_adapter(error, record["raw_results"].get("compile", {}).get("result")) from error
            finally:
                if "compile" not in record["raw_results"]:
                    h.capture_adapter(record, "compile", compile_result)
                classify_compile(record)
            compiled = record["raw_results"]["compile"]["result"]
            require(p.s1.compile_success(compiled) and compiled["engine_sha256"] == ENGINE_SHA,
                    "Exact N1a headless compilation is not proven")
            record["compile_logs"] = h.retain_engine_logs(work, compiled)
            require(record["compile_logs"], "Missing raw compile logs", "unavailable")
            record["scope"]["engine_compilation"] = "executed_success"
            guard()
        record["status"] = "success"
        record["success_means"] = "Exact N1a headless compilation only" if args.compile else "Exact N1a source candidate prepared only"
    except BaseException as error:
        record.update(status=getattr(error, "status", "cancelled" if isinstance(error, KeyboardInterrupt) else "failure"),
                      failure={"type": type(error).__name__, "message": str(error)})
    finally:
        try:
            if guard:
                guard()
        except BaseException as error:
            record["evidence_errors"].append({"stage": "final_integrity", "type": type(error).__name__, "message": str(error)})
            if record["status"] == "success":
                record["status"] = "stale_input"
        if job:
            try:
                record["commands"] = job.result["raw_logs"]
                for command in record["commands"]:
                    for stream in ("stdout", "stderr"):
                        path = Path(command[stream])
                        if path.is_file():
                            command[stream + "_sha256"] = h.streamed_identity(path)["sha256"]
                job.result.update(status=record["status"], stage=record["stage"])
                p.h.save_result(job.path / "result.json", job.result)
                record["job"] = job.result
            except BaseException as error:
                record["evidence_errors"].append({"stage": "job_retention", "type": type(error).__name__, "message": str(error)})
                if record["status"] == "success":
                    record["status"] = "failure"
        if p and args.compile and "compile_logs" not in record:
            try:
                record["compile_logs"] = p.h.retain_engine_logs(work, record["raw_results"].get("compile", {}).get("result"))
            except BaseException as error:
                record["evidence_errors"].append({"stage": "compile_log_retention", "type": type(error).__name__, "message": str(error)})
                if record["status"] == "success":
                    record["status"] = "failure"
        if p:
            p.h.save_result(work / "results.json", record)
        else:
            payload = json.dumps(record, sort_keys=True, indent=2).encode("ascii") + b"\n"
            (work / "results.json").write_bytes(payload)
        result = work / "results.json"
        print(json.dumps({"result": str(result), "sha256": digest(result.read_bytes()), "status": record["status"],
                          "stage": record["stage"], "failure": record.get("failure"), "evidence_errors": record["evidence_errors"]}), flush=True)
    return 0 if record["status"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
