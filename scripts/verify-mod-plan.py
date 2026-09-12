#!/usr/bin/env python3
"""Bounded non-executing workflow-plan and CLI/MCP parity regressions.

Creates isolated input fixtures and test receipts. It does not install tooling,
compile generated programs, run native Beryl code, or launch an engine.
"""
from pathlib import Path
import argparse
import builtins
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
import mod
import mcp_server


def tree(root):
    return {str(p.relative_to(root)): mod.digest(p.read_bytes()) if p.is_file() else "directory"
            for p in sorted(root.rglob("*"))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--beryl", type=Path, required=True)
    args = parser.parse_args()
    compiler = args.beryl.resolve(strict=True)
    work = Path(tempfile.mkdtemp(prefix="mod-plan & spaces-", dir=ROOT / "build"))
    project = work / "project"
    project.mkdir()
    for name in ("pid.be", "pid_test.be", "beryl.mod.json"):
        shutil.copyfile(ROOT / "packages/sparkos/pid" / name, project / name)
    description = project / "beryl.mod.json"
    original = description.read_bytes()
    config = mod.parse(original)
    input_paths = [Path(__file__), Path(mod.__file__), Path(mcp_server.__file__), mod.SCHEMA, compiler]
    fingerprints = {str(p): mod.digest(p.read_bytes()) for p in input_paths}
    record = {"schema_version": 1, "status": "failed", "compiler_sha256": fingerprints[str(compiler)],
              "input_hashes": fingerprints, "checks": [], "commands": [], "unavailable": [],
              "program_execution": "not_run", "engine_execution": "not_run", "installation": "not_run"}
    print("Mod plan evidence:", work, flush=True)

    def passed(label):
        record["checks"].append(label)
        mod.write_json(work / "results.json", record)
        print("passed", label, flush=True)

    def invoke(*options, expected="success", selected_project=project, selected_compiler=compiler, guarded=False):
        before = tree(selected_project)
        captured = io.StringIO()
        argv = ["plan", "--beryl", str(selected_compiler), "--project", str(selected_project), *options]
        with contextlib.ExitStack() as stack:
            stack.enter_context(contextlib.redirect_stdout(captured))
            if guarded:
                for owner, name in ((mod.Job, "__init__"), (subprocess, "Popen"), (subprocess, "run"),
                                    (mod, "write_json"), (Path, "mkdir"), (Path, "write_bytes"), (Path, "write_text")):
                    stack.enter_context(mock.patch.object(owner, name, side_effect=AssertionError("plan attempted side effect: " + name)))
                for owner in (builtins, io):
                    actual = owner.open
                    def read_only_open(file, mode="r", *a, _open=actual, **kw):
                        assert not any(ch in mode for ch in "wax+"), "plan attempted writable open"
                        return _open(file, mode, *a, **kw)
                    stack.enter_context(mock.patch.object(owner, "open", side_effect=read_only_open))
            code = mod.main(argv)
        value = mod.parse(captured.getvalue().encode())
        assert value["status"] == expected, value
        assert (code == 0) == (expected == "success"), (code, value)
        assert value["execution"] == "not_run", value
        assert tree(selected_project) == before, "planner changed project files"
        assert not (selected_project / ".beryl-mod").exists()
        record["commands"].append({"mode": "in_process", "argv": argv, "exit_code": code, "result": value})
        return value

    def configure(value):
        description.write_bytes(mod.canonical(value))

    try:
        first = invoke(guarded=True)
        second = invoke(guarded=True)
        assert first["plan"] == second["plan"] and first["plan_sha256"] == second["plan_sha256"]
        assert first["operation_id"] != second["operation_id"]
        assert first["plan_sha256"] == mod.digest(mod.canonical(first["plan"]))
        assert first["source_sha256"] == mod.digest(mod.canonical({name: mod.digest((project / name).read_bytes()) for name in ("beryl.mod.json", "pid.be", "pid_test.be")}))
        assert first["artifact_sha256"] is None and first["raw_logs"] == first["measurements"] == []
        assert first["plan"]["admission"]["symbols"] == first["plan"]["admission"]["target_semantics"] == "not_checked"
        assert all(not row["executed"] and row["evidence"] == [] for row in first["plan"]["stages"])
        unavailable = {row["id"] for row in first["plan"]["stages"] if row["status"] == "unavailable"}
        assert {"companion_v2", "tablet_lifecycle", "project_gameplay_runtime", "multiplayer_acceptance", "visual_acceptance", "whole_mod_authoring"} <= unavailable
        assert first["plan"]["installed_scenarios"]["selected"] is None
        assert any(v["name"] == "probe.map.cursor" and v["implementation"] == "implemented" for v in first["plan"]["installed_scenarios"]["definitions"])
        assert all(v["local_availability"] == "not_checked" for v in first["plan"]["capabilities"] if v["implementation"] == "required_by_workflow")
        passed("deterministic exact snapshot plan; no jobs, writes, subprocesses, execution, invented admission or evidence")

        source = project / "pid.be"
        before_source = source.read_bytes()
        source.write_bytes(b"this is deliberately not valid Beryl syntax\n")
        bad_source = invoke()
        assert bad_source["source_sha256"] != first["source_sha256"]
        assert bad_source["plan"]["admission"]["target_semantics"] == "not_checked"
        source.write_bytes(before_source)
        dummy = work / "not-an-executable.bin"
        dummy.write_bytes(b"identity-only; never launch this file")
        identified = invoke(selected_compiler=dummy, guarded=True)
        assert identified["compiler_sha256"] == mod.digest(dummy.read_bytes())
        assert next(v for v in identified["plan"]["capabilities"] if v["id"] == "compiler_check_native")["local_availability"] == "not_checked"
        passed("invalid Beryl source and non-executable compiler bytes remain structurally planned, never semantically accepted")

        no_tests = copy.deepcopy(config)
        no_tests["sources"]["tests"] = []
        configure(no_tests)
        empty = invoke()
        assert next(v for v in empty["plan"]["stages"] if v["id"] == "native_tests")["status"] == "unavailable"
        description.write_bytes(original)
        passed("absent tests are unavailable rather than a successful empty run")

        for name, edit in (
            ("unknown", lambda c: c.update(build_script="do not execute")),
            ("v2", lambda c: c.update(schema_version=2)),
            ("boolean-version", lambda c: c.update(schema_version=True)),
            ("test-overlap", lambda c: c["sources"].update(tests=["pid.be"])),
            ("case-alias", lambda c: c["sources"].update(enfusion=["PID.be"])),
            ("missing", lambda c: c["sources"].update(enfusion=["missing.be"])),
            ("traversal", lambda c: c["sources"].update(enfusion=["../outside.be"])),
            ("absolute", lambda c: c["sources"].update(enfusion=["C:/outside.be"])),
            ("self-dependency", lambda c: c["addon"].update(dependencies=[c["addon"]["guid"]])),
            ("receiver", lambda c: c["exports"][0]["methods"][0].update(source="other.Record.step")),
        ):
            changed = copy.deepcopy(config)
            edit(changed)
            configure(changed)
            rejected = invoke(expected="failure", guarded=True)
            assert rejected["diagnostics"] and rejected["diagnostics"][-1]["help"]
            description.write_bytes(original)
        for malformed in (b'{"schema_version":1,"schema_version":1}', b'{/* no comments */}', b'[{"x":NaN}]'):
            description.write_bytes(malformed)
            invoke(expected="failure", guarded=True)
            description.write_bytes(original)
        passed("strict v1 schema, duplicate keys, paths, inputs, source-set and receiver errors fail with repair guidance")

        for option in (("--artifact", "a" * 32), ("--stage", "compile"), ("--scenario", "probe.map.cursor"),
                       ("--scenario-count", "1"), ("--scenario-case", "empty"), ("--measurement-plan", "plan.json"),
                       ("--workbench-tools", "absent"), ("--destination", "absent")):
            invoke(*option, expected="failure", guarded=True)
        passed("all execution and promotion options are rejected before job creation")

        with mock.patch.object(mod, "MAX_PLAN_INPUT", 1024):
            invoke(expected="unavailable", guarded=True)
        with mock.patch.object(mod, "MAX_PLAN_OUTPUT", 128):
            invoke(expected="unavailable", guarded=True)
        actual_read = mod.read
        reads = 0
        def changing_read(path):
            nonlocal reads
            data = actual_read(path)
            if Path(path) == source:
                reads += 1
                if reads == 3:
                    return data + b"\n// concurrent change\n"
            return data
        with mock.patch.object(mod, "read", side_effect=changing_read):
            invoke(expected="stale_input", guarded=True)
        actual_identity = mod.tool_identity()
        with mock.patch.object(mod, "tool_identity", side_effect=[actual_identity, "f" * 64]):
            invoke(expected="stale_input", guarded=True)
        passed("input/output bounds and changed source/tool identity fail closed without writes")

        shared = mod.description_snapshot(project)
        output = work / "snapshot-job"
        output.mkdir()
        job = object.__new__(mod.Job)
        job.project, job.path, job.result = project, output, {}
        snap, inputs, hashes = job.snapshot()
        assert snap == shared[0] and hashes == shared[2]
        assert {name: (inputs / name).read_bytes() for name in hashes} == shared[1]
        assert job.result["source_sha256"] == first["source_sha256"]
        passed("existing Job.snapshot reuses exactly the same structural inputs and fingerprint")

        env = os.environ.copy()
        env.update(BERYL_PYTHON=sys.executable, BERYL_MOD_TOOL=str(ROOT / "tools/beryl-mod/mod.py"), PYTHONDONTWRITEBYTECODE="1")
        before_tree = tree(project)
        command = [str(compiler), "mod", "plan", "--project", str(project)]
        cli = subprocess.run(command, cwd=work, env=env, capture_output=True, text=True, encoding="utf-8", timeout=30)
        value = mod.parse(cli.stdout.encode())
        record["commands"].append({"mode": "C_dispatch", "argv": command, "exit_code": cli.returncode, "result": value, "stderr": cli.stderr})
        assert cli.returncode == 0 and value["plan"] == first["plan"], value
        assert tree(project) == before_tree
        passed("real C dispatcher returns the same plan; transport logs are outside the declared project")

        server = mcp_server.Server(compiler, project, 30)
        mcp_server.validate({"operation": "plan"}, mcp_server.TOOL_BY_NAME["beryl_mod"]["inputSchema"])
        argv, sources = server.command("beryl_mod", {"operation": "plan"}, work)
        assert argv == command and sources == []
        for extra in ({"artifact": "a" * 32}, {"stage": "compile"}, {"scenario": "probe.map.cursor"}):
            try:
                server.command("beryl_mod", {"operation": "plan", **extra}, work)
            except mcp_server.Invalid:
                pass
            else:
                raise AssertionError("MCP plan accepted execution fields")
        server.validate_response("beryl_mod", {"operation": "plan"}, first, work)
        for mutation in (lambda v: v.update(plan_sha256="0" * 64), lambda v: v.update(execution="executed"),
                         lambda v: v["plan"].update(identities=[]), lambda v: v["plan"]["admission"].update(target_semantics="passed")):
            invalid = copy.deepcopy(first)
            mutation(invalid)
            if invalid["plan_sha256"] != "0" * 64:
                invalid["plan_sha256"] = mod.digest(mod.canonical(invalid["plan"]))
            try:
                server.validate_response("beryl_mod", {"operation": "plan"}, invalid, work)
            except mcp_server.Invalid:
                pass
            else:
                raise AssertionError("invalid plan response accepted")
        passed("MCP reuses typed plan dispatch and rejects altered plan identity or fabricated execution/admission")

        spec = importlib.util.spec_from_file_location("protocol_fixture", ROOT / "scripts/verify-mcp.py")
        protocol = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(protocol)
        session = protocol.Session(work, ROOT / "tools/beryl-mod/mcp_server.py", compiler, project, env, timeout=30)
        try:
            session.initialize()
            response = protocol.tool_result(session.call("beryl_mod", {"operation": "plan"}))
            assert response["status"] == "success" and response["result"]["plan"] == first["plan"], response
            assert response["result"]["execution"] == "not_run"
            rejected = protocol.tool_result(session.call("beryl_mod", {"operation": "plan", "scenario": "probe.map.cursor"}))
            assert rejected["status"] == "failure"
        finally:
            session.close()
        assert not (project / ".beryl-mod").exists()
        record["mcp_session"] = str(session.folder / "session.json")
        passed("real local stdio MCP returns identical plan and rejects scenario execution parameters")

        assert fingerprints == {str(p): mod.digest(p.read_bytes()) for p in input_paths}, "verifier inputs changed"
        record["status"] = "success"
    except BaseException as error:
        record["failure"] = repr(error)
        raise
    finally:
        mod.write_json(work / "results.json", record)
        print("Evidence:", work / "results.json", flush=True)


if __name__ == "__main__":
    sys.dont_write_bytecode = True
    main()
