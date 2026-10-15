#!/usr/bin/env python3
"""V2 source admission/generation, v1 compatibility and installed CLI/MCP checks.

Never compiles/runs generated native programs or launches an engine. Installation
is restricted to the explicitly selected private candidate directory, not build/.
"""
from pathlib import Path
import argparse
import contextlib
import copy
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools/beryl-mod"))
sys.dont_write_bytecode = True
import mod
import install as installer

SOURCE = '''module sparkos.tablet.admission
pub struct State { phase: i32 = 0, elapsed: f32 = 0 }
pub fn on_init(inout state: State) { state.phase = 0 }
pub fn on_frame(inout state: State, time_slice: f32) { state.elapsed += time_slice }
pub fn on_delete(inout state: State) { state.phase = 0 }
'''


def tree(root):
    return {str(p.relative_to(root)): mod.digest(p.read_bytes()) if p.is_file() else "directory"
            for p in sorted(root.rglob("*"))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--beryl", type=Path, required=True)
    parser.add_argument("--expect-compiler-sha256", required=True)
    parser.add_argument("--legacy-bundle", type=Path, help="Previously verified exact 21- or 24-file bundle for a private hardened-loader upgrade fixture")
    args = parser.parse_args()
    compiler = args.beryl.resolve(strict=True)
    if compiler.parent == ROOT / "build" or not compiler.is_relative_to(ROOT / "build"):
        raise RuntimeError("Explicit private compiler candidate under build required; active build/beryl.exe is forbidden")
    if mod.digest(compiler.read_bytes()) != args.expect_compiler_sha256:
        raise RuntimeError("Candidate compiler differs from selected identity")
    work = Path(tempfile.mkdtemp(prefix="component workflow & spaces-", dir=ROOT / "build"))
    project = work / "v2"
    project.mkdir()
    source = project / "tablet.be"
    source.write_text(SOURCE, encoding="utf-8", newline="\n")
    config = {"schema_version": 2, "name": "Signature admission fixture; no tablet implementation",
              "addon": {"id": "Beryl_ComponentAdmission", "guid": "1234567890ABCDEF", "dependencies": []},
              "binding": {"target": "enfusion", "version": "1.8.0.13",
                          "sha256": "7dd36ca1f662b0c13669a4f2f7f10e3c461c2906b021e742272d64b3ab7e9798",
                          "contract_profile": "enfusion.tablet.script-component.v1"},
              "sources": {"native": ["tablet.be"], "enfusion": ["tablet.be"], "tests": []}, "exports": [],
              "components": [{"descriptor": {"name": "SPK_AdmissionFixtureClass", "parent": "ScriptComponentClass"},
                              "instance": {"name": "SPK_AdmissionFixture", "parent": "ScriptComponent"},
                              "state": "sparkos.tablet.admission.State", "callbacks": [
                                  {"binding": "ScriptComponent.OnPostInit", "handler": "sparkos.tablet.admission.on_init", "super_order": "first"},
                                  {"binding": "ScriptComponent.EOnFrame", "handler": "sparkos.tablet.admission.on_frame", "super_order": "none"},
                                  {"binding": "ScriptComponent.OnDelete", "handler": "sparkos.tablet.admission.on_delete", "super_order": "last"}]}]}
    description = project / "beryl.mod.json"
    description.write_bytes(mod.canonical(config))
    tracked = [Path(__file__), compiler, Path(installer.__file__), *mod.bundle_paths()]
    identities = {str(p): mod.digest(p.read_bytes()) for p in tracked}
    record = {"schema_version": 1, "operation": "verify_component_workflow", "status": "failure",
              "compiler_sha256": args.expect_compiler_sha256, "input_hashes": identities,
              "checks": [], "commands": [], "program_execution": "not_run", "engine_execution": "not_run",
              "active_installation": "unchanged", "limitation": "Structure/signature, generated-source artifacts and CLI/MCP protocol evidence only; no native program, engine component or tablet runtime"}
    env = os.environ.copy()
    env.update(BERYL_PYTHON=sys.executable, BERYL_MOD_TOOL=str(ROOT / "tools/beryl-mod/mod.py"))
    print("Component workflow evidence:", work, flush=True)

    def passed(label):
        record["checks"].append(label)
        mod.write_json(work / "results.json", record)
        print("passed", label, flush=True)

    def invoke(operation, *options, status="success", selected=project, installed=False):
        selected_env = env.copy()
        if installed:
            selected_env.pop("BERYL_MOD_TOOL", None)
        argv = [str(compiler), "mod", operation, "--project", str(selected), *map(str, options)]
        entry = {"argv": argv, "status": "startup_failure", "exit_code": None, "installed_bundle": installed}
        record["commands"].append(entry)
        try:
            proc = subprocess.run(argv, env=selected_env, cwd=work, capture_output=True, timeout=60)
        except (OSError, subprocess.TimeoutExpired) as exc:
            entry.update(status="timeout" if isinstance(exc, subprocess.TimeoutExpired) else "startup_failure", error=str(exc))
            if isinstance(exc, subprocess.TimeoutExpired):
                entry["partial_stdout"] = (exc.stdout or b"").decode("utf-8", errors="replace")
                entry["partial_stderr"] = (exc.stderr or b"").decode("utf-8", errors="replace")
            raise
        stem = work / ("command-" + str(len(record["commands"]) - 1).zfill(4))
        out_path, err_path = Path(str(stem) + ".stdout.bin"), Path(str(stem) + ".stderr.bin")
        out_path.write_bytes(proc.stdout)
        err_path.write_bytes(proc.stderr)
        entry.update(status="exited", exit_code=proc.returncode, stdout_path=str(out_path), stderr_path=str(err_path),
                     stdout_sha256=mod.digest(proc.stdout), stderr_sha256=mod.digest(proc.stderr),
                     stderr=proc.stderr.decode("utf-8", errors="replace"))
        value = mod.parse(proc.stdout)
        entry["result"] = value
        assert value["status"] == status and (proc.returncode == 0) == (status == "success"), value
        if operation != "build" or status != "success":
            assert value.get("artifact_sha256") is None, value
        return value

    try:
        before = tree(project)
        with contextlib.ExitStack() as stack:
            for owner, name in ((mod.Job, "__init__"), (subprocess, "Popen"), (subprocess, "run"),
                                (mod, "write_json"), (Path, "mkdir"), (Path, "write_bytes"), (Path, "write_text")):
                stack.enter_context(mock.patch.object(owner, name, side_effect=AssertionError("planner side effect: " + name)))
            first = mod.workflow_plan(project, compiler)
            second = mod.workflow_plan(project, compiler)
        assert tree(project) == before and first["plan"] == second["plan"]
        assert first["execution"] == "not_run" and first["plan"]["project"]["companion_version"] == 2
        assert first["plan_sha256"] == mod.digest(mod.canonical(first["plan"]))
        assert first["plan"]["admission"]["symbols"] == first["plan"]["admission"]["target_semantics"] == "not_checked"
        assert all(s["status"] == "unavailable" and not s["actions"] for s in first["plan"]["stages"] if s["id"] not in ("semantic_check", "candidate_build"))
        assert next(s for s in first["plan"]["stages"] if s["id"] == "candidate_build")["status"] == "not_checked"
        assert len(first["plan"]["outputs"]) == 2 and not (project / ".beryl-mod").exists()
        passed("guarded deterministic v2 planning performs no compiler calls, jobs or generation")
        real_read = mod.read
        reads = 0
        snapshot_reads = sum(names.count("tablet.be") for names in config["sources"].values())
        def changed_source(path):
            nonlocal reads
            if Path(path) == source:
                reads += 1
                if reads > snapshot_reads:
                    return b"source bytes changed after the planning snapshot\n"
            return real_read(path)
        with mock.patch.object(mod, "read", side_effect=changed_source):
            try:
                mod.workflow_plan(project, compiler)
            except mod.Failure as exc:
                assert exc.status == "stale_input"
            else:
                raise AssertionError("Changed planning source was accepted")
        with mock.patch.object(mod, "tool_identity", side_effect=[mod.tool_identity(), "0" * 64]):
            try:
                mod.workflow_plan(project, compiler)
            except mod.Failure as exc:
                assert exc.status == "stale_input"
            else:
                raise AssertionError("Changed planning tool was accepted")
        assert tree(project) == before
        passed("planning rejects changed source/tool snapshots without creating an artifact")
        dispatched = invoke("plan")
        assert dispatched["plan"] == first["plan"]
        good = invoke("check")
        assert good["stage"] == "component_admission" and good["execution"] == "not_run"
        assert [r["stage"] if "stage" in r else Path(r["stdout"]).stem for r in good["raw_logs"]]
        assert len(good["raw_logs"]) == 3 and all(r["exit_code"] == 0 for r in good["raw_logs"])
        assert good["component_symbol_admission"], good
        passed("real compiler checks both targets and resolves exact public state/handler declarations")

        for changed, reason in (
            (SOURCE.replace("pub fn on_frame", "fn on_frame"), "private handler"),
            (SOURCE.replace("pub struct State", "struct State"), "private root state"),
            (SOURCE.replace("pub fn on_init(inout state: State) { state.phase = 0 }", "pub fn on_init(inout state: State) -> i32 { return 0 }"), "wrong return"),
            (SOURCE.replace("pub fn on_frame(inout state: State, time_slice: f32) { state.elapsed += time_slice }", "pub fn on_frame(state: State, time_slice: f32) { }"), "wrong state access"),
            (SOURCE.replace("time_slice: f32", "time_slice: i32").replace("state.elapsed += time_slice", "state.phase += time_slice"), "wrong timestep width"),
            (SOURCE.replace("pub fn on_frame", "pub fn missing_frame"), "unresolved callback"),
            (SOURCE.replace("time_slice: f32", "time_slice: f32 = 0"), "unsupported callback default"),
        ):
            source.write_text(changed, encoding="utf-8", newline="\n")
            bad = invoke("check", status="failure")
            assert bad["diagnostics"][-1]["json_pointer"].startswith("/components/0/"), (reason, bad)
        source.write_text(SOURCE, encoding="utf-8", newline="\n")
        passed("real signature violations map to companion origins without engine execution")

        for mutate, status in (
            (lambda c: c["binding"].update(sha256="0" * 64), "stale_input"),
            (lambda c: c["components"][0]["descriptor"].update(parent="ScriptComponent"), "failure"),
            (lambda c: c["components"][0]["callbacks"][0].update(super_order="last"), "failure"),
            (lambda c: c["components"][0]["instance"].update(name=c["components"][0]["descriptor"]["name"]), "failure"),
            (lambda c: c.update(shell="arbitrary code is forbidden"), "failure"),
        ):
            bad_config = copy.deepcopy(config)
            mutate(bad_config)
            description.write_bytes(mod.canonical(bad_config))
            bad = invoke("plan", status=status)
            assert bad["execution"] == "not_run" and not bad["raw_logs"]
        description.write_bytes(mod.canonical(config))
        passed("stale declared engine identity, parent/order/name conflicts and arbitrary fields fail planning")

        sentinel = project / ".beryl-mod/artifacts/preserved.txt"
        sentinel.parent.mkdir(parents=True, exist_ok=True)
        sentinel.write_bytes(b"prior artifacts remain intact\n")
        built = invoke("build")
        assert built["component_generation"]["runtime_verification"] == "not_run"
        artifact = Path(built["artifact_path"])
        manifest = mod.parse((artifact / "artifact.json").read_bytes())
        assert manifest["files"] and manifest["artifact_sha256"] == built["artifact_sha256"]
        generated = (artifact / "addon/scripts/Game/Beryl/Beryl_Generated.c").read_bytes()
        mapped = mod.parse((artifact / "source-map.json").read_bytes())
        assert mapped["generated"]["sha256"] == mod.digest(generated) and mapped["generated"]["bytes"] == len(generated)
        assert b"class SPK_AdmissionFixtureClass : ScriptComponentClass" in generated
        assert b"class SPK_AdmissionFixture : ScriptComponent" in generated
        assert b"SetEventMask(owner, EntityEvent.FRAME);" in generated
        assert any(m["kind"] == "component_handler" for m in mapped["mappings"])
        baseline = tree(project)
        invoke("verify", "--stage", "compile", "--artifact", "a" * 32, status="unavailable")
        invoke("promote", "--artifact", "a" * 32, "--destination", work / "forbidden-promotion", status="unavailable")
        assert tree(project) == baseline and sentinel.read_bytes() == b"prior artifacts remain intact\n"
        assert not (work / "forbidden-promotion").exists()
        passed("scalar component wrappers build an immutable source artifact; v2 engine verify/promote remain unavailable and preserve prior artifacts")

        # Fault-injection checks transport identities, not compiler behavior.
        with mock.patch.object(mod.Job, "run", return_value=mod.canonical({"schema_version": 1, "status": "success"})):
            fake_job = mock.Mock(compiler=compiler, result={"compiler_sha256": args.expect_compiler_sha256}, run=mod.Job.run)
            try:
                mod.checks(fake_job, config, project)
            except mod.Failure:
                pass
            else:
                raise AssertionError("fabricated context was accepted")
        passed("missing context operation/source/compiler identity cannot establish symbol admission")
        real_context = mod.parse(Path(good["raw_logs"][-1]["stdout"]).read_bytes())
        for mutate in (lambda c: c.update(compiler_fingerprint="0" * 64),
                       lambda c: c["sources"][0].update(sha256="0" * 64)):
            wrong = copy.deepcopy(real_context)
            mutate(wrong)
            fake_job = mock.Mock(compiler=compiler, result={"compiler_sha256": args.expect_compiler_sha256})
            fake_job.run.side_effect = [mod.canonical({"status": "success"}), mod.canonical({"status": "success"}), mod.canonical(wrong)]
            try:
                mod.checks(fake_job, config, project)
            except mod.Failure as exc:
                assert exc.status == "stale_input"
            else:
                raise AssertionError("Wrong checked context identity was accepted")
        passed("valid-shaped context with another compiler or source snapshot is rejected")

        legacy = work / "v1"
        legacy.mkdir()
        for name in ("pid.be", "pid_test.be", "beryl.mod.json"):
            (legacy / name).write_bytes((ROOT / "packages/sparkos/pid" / name).read_bytes())
        v1 = invoke("plan", selected=legacy)
        assert v1["plan"]["project"]["companion_version"] == 1
        old = mod.parse((legacy / "beryl.mod.json").read_bytes())
        old["components"] = config["components"]
        (legacy / "beryl.mod.json").write_bytes(mod.canonical(old))
        invoke("plan", selected=legacy, status="failure")
        passed("unchanged v1 export planning rejects v2 component fields")

        # Install only beside this explicitly selected private candidate.
        active_controls = {p: p.read_bytes() for p in (ROOT / "build/beryl.exe", ROOT / "build/beryl-tools/active.json") if p.exists()}
        if args.legacy_bundle:
            legacy_bundle = args.legacy_bundle.resolve(strict=True)
            legacy_manifest = mod.parse((legacy_bundle / "bundle.json").read_bytes())
            legacy21 = {"mod.py", "process_job.py", "engine-compile.ps1", "beryl.mod.v1.schema.json",
                        "scenarios.py", "map-cursor.c.in", "scenario-engine-run.ps1", "source_maps.py",
                        "terrain_scenarios.py", "terrain-reference.c.txt", "terrain-reference.json", "terrain-adapter.c.in", "terrain-handler.c.in",
                        "storage_scenarios.py", "array-storage.c.in", "canvas-retention.c.in",
                        "terrain_measurements.py", "terrain-measurement.c.in", "terrain-adapter-v1.c.txt",
                        "mcp_server.py", "beryl.analysis.v1.schema.json"}
            legacy24 = legacy21 | {"component_contracts.py", "tablet-component-contracts.v1.json", "beryl.mod.v2.schema.json"}
            assert type(legacy_manifest) is dict and set(legacy_manifest) in (legacy21, legacy24)
            legacy_names = set(legacy_manifest)
            assert {p.name for p in legacy_bundle.iterdir()} == legacy_names | {"bundle.json"}
            assert legacy_bundle.name == mod.digest(mod.canonical(legacy_manifest))
            assert all(mod.digest((legacy_bundle / name).read_bytes()) == value for name, value in legacy_manifest.items())
            previous_loader = installer.COMPONENT_ADMISSION_LOADER if legacy_names == legacy24 else installer.HARDENED_ASSISTANT_LOADER
            previous_mcp_loader = installer.COMPONENT_ADMISSION_MCP_LOADER if legacy_names == legacy24 else installer.HARDENED_ASSISTANT_MCP_LOADER
            previous_loader_version = "v8" if legacy_names == legacy24 else "v7"
            previous_root = compiler.parent / "beryl-tools"
            assert not previous_root.exists(), "Legacy upgrade fixture requires a pristine private candidate"
            previous_root.mkdir()
            shutil.copytree(legacy_bundle, previous_root / legacy_bundle.name)
            (previous_root / "mod.py").write_bytes(previous_loader)
            (previous_root / "mcp.py").write_bytes(previous_mcp_loader)
            mod.write_json(previous_root / "active.json", {"bundle": legacy_bundle.name})
            if legacy_names == legacy24:
                previous_v2_plan = invoke("plan", selected=project, installed=True)
                assert previous_v2_plan["execution"] == "not_run"
                assert next(s for s in previous_v2_plan["plan"]["stages"] if s["id"] == "candidate_build")["status"] == "unavailable"
                previous_v2_check = invoke("check", selected=project, installed=True)
                assert previous_v2_check["execution"] == "not_run" and previous_v2_check["component_symbol_admission"]["status"] == "admitted_signatures"
                prior_artifacts = tree(project / ".beryl-mod/artifacts")
                invoke("build", selected=project, installed=True, status="unavailable")
                assert tree(project / ".beryl-mod/artifacts") == prior_artifacts
            else:
                invoke("plan", selected=project, installed=True, status="failure")
            previous_plan = invoke("plan", selected=legacy, installed=True, status="failure")
            assert previous_plan["execution"] == "not_run"
            # V1 fixture currently contains a v2-only field from its negative case.
            old.pop("components")
            (legacy / "beryl.mod.json").write_bytes(mod.canonical(old))
            invoke("plan", selected=legacy, installed=True)
            record["legacy_upgrade"] = {"bundle_sha256": legacy_bundle.name, "payload_files": len(legacy_names),
                                        "loader_generation": previous_loader_version,
                                        "scope": "actual hardened " + str(len(legacy_names)) + "-file CLI followed by source 25-file installed CLI/MCP; generated-source/protocol evidence, no runtime"}
        with contextlib.redirect_stdout(io.StringIO()):
            installed = installer.install(compiler)
        record["private_installation"] = installed
        if args.legacy_bundle:
            previous_root = compiler.parent / "beryl-tools"
            assert (previous_root / ("loader-" + previous_loader_version + "-" + mod.digest(previous_loader) + ".py")).read_bytes() == previous_loader
            assert (previous_root / ("mcp-loader-v1-" + mod.digest(previous_mcp_loader) + ".py")).read_bytes() == previous_mcp_loader
        actual = invoke("plan", installed=True)
        assert actual["plan"] == first["plan"]
        checked = invoke("check", installed=True)
        assert checked["component_symbol_admission"] == good["component_symbol_admission"]
        spec = importlib.util.spec_from_file_location("protocol_fixture", ROOT / "scripts/verify-mcp.py")
        protocol = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(protocol)
        mcp_env = env.copy()
        mcp_env.pop("BERYL_MOD_TOOL", None)
        mcp_env.pop("BERYL_MCP_TOOL", None)
        session = protocol.Session(work, ROOT / "tools/beryl-mod/mcp_server.py", compiler, project, mcp_env, via_cli=True, timeout=30)
        try:
            session.initialize()
            result = protocol.tool_result(session.call("beryl_mod", {"operation": "plan"}))
            assert result["status"] == "success" and result["result"]["plan"] == first["plan"], result
            result = protocol.tool_result(session.call("beryl_mod", {"operation": "check"}))
            assert result["status"] == "success" and result["result"]["component_symbol_admission"] == good["component_symbol_admission"], result
            result = protocol.tool_result(session.call("beryl_mod", {"operation": "build"}))
            assert result["status"] == "success" and result["result"]["component_generation"]["runtime_verification"] == "not_run", result
        finally:
            session.close()
        record["mcp_session"] = str(session.folder / "session.json")
        assert all(p.read_bytes() == value for p, value in active_controls.items()), "active controls changed"
        passed("private installed CLI and local stdio MCP agree; active installation remains unchanged")
        assert identities == {str(p): mod.digest(p.read_bytes()) for p in tracked}, "verification inputs changed"
        record["status"] = "success"
    except BaseException as exc:
        record["failure"] = repr(exc)
        raise
    finally:
        mod.write_json(work / "results.json", record)
        print(work / "results.json", flush=True)


if __name__ == "__main__":
    main()
