#!/usr/bin/env python3
"""CLI regressions for strict companions, staged artifacts and owned promotion.

Promotion policy tests use clearly marked synthetic compilation receipts; real
Workbench compile/runtime acceptance is exercised by verify-pid and mod verify.
"""
from pathlib import Path
import argparse
import copy
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools/beryl-mod"))
import mod
import install as install_tool


def verify_installed_loaders(work, project, compiler, tool_root, bundle, env, record, passed):
    """Actual installed launch checks plus labelled activation fault injection."""
    version_dir = tool_root / bundle
    install_argv = [sys.executable, str(ROOT / "tools/beryl-mod/install.py"), "--compiler", str(compiler)]
    env = env.copy()
    env.pop("BERYL_MCP_TOOL", None)
    env["PYTHONDONTWRITEBYTECODE"] = "1"

    def invoke(argv, data=None):
        process = subprocess.run(list(map(str, argv)), env=env, cwd=work, input=data,
                                 capture_output=True, timeout=30)
        record["commands"].append({"argv": list(map(str, argv)), "exit_code": process.returncode,
                                  "stdout": process.stdout.decode("utf-8", "replace"),
                                  "stderr": process.stderr.decode("utf-8", "replace")})
        return process

    spec = importlib.util.spec_from_file_location("installed_mcp_verifier", ROOT / "scripts/verify-mcp.py")
    verifier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(verifier)

    def bootstrap():
        session = verifier.Session(work, ROOT / "tools/beryl-mod/mcp_server.py", compiler, project, env, via_cli=True)
        try:
            session.initialize()
            report = verifier.tool_result(session.call("beryl_context", {"topic": "project", "sources": ["pid.be"]}))
            assert report["status"] == "success" and report["result"]["execution"] == "not_run", report
            assert report["result"]["compiler_fingerprint"] == record["compiler_sha256"]
        finally:
            session.close()

    def rejected_launch(needle):
        for argv in ([compiler, "mod", "check", "--project", project],
                     [compiler, "mcp", "--project", project]):
            process = invoke(argv, b'{"jsonrpc":"2.0","id":1,"method":"ping"}\n')
            assert process.returncode != 0 and not process.stdout and needle in process.stderr, process

    controls = {name: (tool_root / name).read_bytes() for name in ("mod.py", "mcp.py", "active.json")}
    marker = work / "unexpected-import-executed.txt"
    extra = version_dir / "ctypes.py"
    extra.write_bytes(('from pathlib import Path\nPath(' + repr(str(marker)) + ').write_bytes(b"must not execute")\n').encode())
    rejected_launch(b"untracked files")
    assert not marker.exists()
    assert all((tool_root / name).read_bytes() == data for name, data in controls.items())
    extra.unlink()
    cache = version_dir / "__pycache__"
    cache.mkdir()
    rejected_launch(b"untracked files")
    cache.rmdir()  # Only the empty directory created by this fixture.
    bootstrap()
    passed("installed mod/MCP launch reject extra import siblings and cache directories before runpy")

    # Hardlink a tracked file and the manifest without changing their contents.
    # Hashes alone cannot establish the admitted single-link input contract.
    for filename in ("process_job.py", "bundle.json"):
        path = version_dir / filename
        previous = path.read_bytes()
        outside = work / (filename + ".owned-link-target")
        outside.write_bytes(previous)
        path.unlink()
        os.link(outside, path)
        try:
            rejected_launch(b"single-link")
            rejected = invoke(install_argv)
            assert rejected.returncode != 0 and b"single-link" in rejected.stderr
        finally:
            path.unlink()
            path.write_bytes(previous)
        assert all((tool_root / name).read_bytes() == data for name, data in controls.items())
    passed("installed tracked inputs and manifest reject same-byte hardlinks at launch and reinstall")

    symbolic = version_dir / "bundle.json"
    original = symbolic.read_bytes()
    target = work / "symbolic-manifest-target.json"
    target.write_bytes(original)
    symbolic.unlink()
    try:
        try:
            symbolic.symlink_to(target)
        except OSError as exc:
            record.setdefault("unavailable", []).append({"check": "installed manifest symbolic-link rejection", "reason": str(exc)})
        else:
            rejected_launch(b"single-link")
            record.setdefault("filesystem_checks", []).append("actual symbolic manifest rejected")
    finally:
        if os.path.lexists(symbolic):
            symbolic.unlink()
        symbolic.write_bytes(original)

    # A bad MCP loader must fail before an otherwise-needed mod-loader upgrade.
    (tool_root / "mod.py").write_bytes(install_tool.ASSISTANT_LOADER)
    (tool_root / "mcp.py").write_bytes(install_tool.ASSISTANT_MCP_LOADER + b"\n# unknown owned fixture\n")
    before = {name: (tool_root / name).read_bytes() for name in controls}
    rejected = invoke(install_argv)
    assert rejected.returncode != 0 and b"unrecognized MCP loader" in rejected.stderr
    assert all((tool_root / name).read_bytes() == data for name, data in before.items())
    (tool_root / "mcp.py").write_bytes(install_tool.ASSISTANT_MCP_LOADER)
    previous = {name: (tool_root / name).read_bytes() for name in controls}
    upgraded = invoke(install_argv)
    assert upgraded.returncode == 0 and json.loads(upgraded.stdout)["bundle"] == bundle, upgraded.stderr
    for filename, old, prefix in (("mod.py", install_tool.ASSISTANT_LOADER, "loader-v6-"),
                                  ("mcp.py", install_tool.ASSISTANT_MCP_LOADER, "mcp-loader-v1-")):
        assert (tool_root / (prefix + mod.digest(old) + ".py")).read_bytes() == old
        assert (tool_root / filename).read_bytes() == controls[filename]
    bootstrap()
    passed("exact historical mod/MCP loaders migrate with backups; unknown MCP bytes preserve every control")

    # Inject bounded install I/O failures. The raw intent can remain as evidence;
    # no intent record is described as a committed activation receipt.
    for failure in ("intent", "active", "active_after_replace"):
        (tool_root / "mod.py").write_bytes(install_tool.ASSISTANT_LOADER)
        (tool_root / "mcp.py").write_bytes(install_tool.ASSISTANT_MCP_LOADER)
        before = {name: (tool_root / name).read_bytes() for name in controls}
        replace = os.replace
        triggered = False
        def fail_once(src, dst):
            nonlocal triggered
            destination = Path(dst)
            chosen = destination.name.startswith("installation-") if failure == "intent" else destination.name == "active.json"
            if chosen and not triggered:
                triggered = True
                if failure == "active_after_replace":
                    replace(src, dst)
                raise OSError("injected loader " + failure + " failure")
            return replace(src, dst)
        with mock.patch.object(os, "replace", side_effect=fail_once):
            try:
                install_tool.install(compiler)
                raise AssertionError("activation failure was ignored")
            except OSError as exc:
                assert "injected loader" in str(exc), exc
        assert triggered
        assert all((tool_root / name).read_bytes() == data for name, data in before.items())
        assert not (tool_root / ".install-lock").exists()
        assert invoke(install_argv).returncode == 0
    bootstrap()
    assert not list(version_dir.rglob("__pycache__"))
    record["loader_hardening"] = {"bundle": bundle,
        "mod_loader_sha256": mod.digest((tool_root / "mod.py").read_bytes()),
        "mcp_loader_sha256": mod.digest((tool_root / "mcp.py").read_bytes()),
        "fault_injection": ["intent write before activation", "active pointer replacement after loader changes", "exception after active rename committed"],
        "engine_execution": "not_run"}
    passed("intent and active-pointer failures preserve or restore both prior loaders and active bytes")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--beryl", required=True, type=Path)
    args = parser.parse_args()
    compiler = args.beryl.resolve()
    work = Path(tempfile.mkdtemp(prefix="mod & spaces-", dir=ROOT / "build"))
    project = work / "project"
    project.mkdir()
    for name in ("pid.be", "pid_test.be", "beryl.mod.json"):
        shutil.copyfile(ROOT / "packages/sparkos/pid" / name, project / name)
    description = project / "beryl.mod.json"
    baseline = mod.parse(mod.read(description))
    record = {"schema_version": 1, "status": "failure", "compiler_sha256": mod.digest(mod.read(compiler)),
              "tool_sha256": mod.tool_identity(), "checks": [], "commands": [],
              "limitation": "Synthetic compile receipts exercise promotion policy, not actual engine execution"}
    env = os.environ.copy()
    env.update(BERYL_PYTHON=sys.executable, BERYL_MOD_TOOL=str(ROOT / "tools/beryl-mod/mod.py"))

    def run(*arguments, status="success"):
        argv = [str(compiler), "mod", *arguments, "--project", str(project)]
        process = subprocess.run(argv, env=env, cwd=work, capture_output=True, text=True, encoding="utf-8", timeout=60)
        result = json.loads(process.stdout)
        record["commands"].append({"argv": argv, "exit_code": process.returncode, "result": result, "stderr": process.stderr})
        assert result["status"] == status, result
        assert (process.returncode == 0) == (status == "success"), result
        return result

    def passed(label):
        record["checks"].append(label)
        print("passed " + label, flush=True)

    def receipt(artifact_id):
        # Explicit synthetic fixture, restricted to this isolated policy-test tree.
        artifact_path = project / ".beryl-mod/artifacts" / artifact_id
        artifact = mod.parse(mod.read(artifact_path / "artifact.json"))
        operation = "f" * 32
        raw = project / ".beryl-mod/jobs" / operation / "engine.json"
        raw.parent.mkdir(parents=True, exist_ok=True)
        engine = {"fixture": "synthetic promotion policy test", "engine_version": "1.8.0.13", "result": {"Ok": True}}
        mod.write_json(raw, engine)
        mod.write_json(artifact_path / ("compile-" + operation + ".json"), {"schema_version": 1, "stage": "compile", "status": "success",
                       "operation_id": operation, "engine": engine, "artifact_sha256": artifact["artifact_sha256"]})

    try:
        run("check")
        first = run("build")
        second = run("build")
        assert first["artifact_sha256"] == second["artifact_sha256"]
        assert first["artifact_id"] != second["artifact_id"]
        passed("typed companion checks and deterministic independent artifacts")
        mutations = []
        bad = copy.deepcopy(baseline); bad["build_script"] = "echo unsafe"; mutations.append(bad)
        bad = copy.deepcopy(baseline); bad["schema_version"] = True; mutations.append(bad)
        bad = copy.deepcopy(baseline); bad["sources"]["native"] = []; mutations.append(bad)
        bad = copy.deepcopy(baseline); bad["sources"]["enfusion"] = ["../pid.be"]; mutations.append(bad)
        bad = copy.deepcopy(baseline); bad["sources"]["native"] = ["missing.be"]; mutations.append(bad)
        bad = copy.deepcopy(baseline); bad["sources"]["native"] = ["pid.be", "PID.be"]; mutations.append(bad)
        bad = copy.deepcopy(baseline); bad["exports"][0]["constructor"] = "sparkos.flight.pid.Pid.step"; mutations.append(bad)
        bad = copy.deepcopy(baseline); bad["exports"][0]["methods"][1]["name"] = "Reset"; mutations.append(bad)
        bad = copy.deepcopy(baseline); bad["exports"][0]["methods"][0]["source"] = "sparkos.flight.pid.Pid.missing"; mutations.append(bad)
        for bad in mutations:
            mod.write_json(description, bad)
            run("check", status="failure")
        description.write_text('{"schema_version":1,"schema_version":1}', encoding="utf-8")
        run("check", status="failure")
        mod.write_json(description, baseline)
        passed("unknown fields, duplicate keys, wrong types, path escapes, missing files and export conflicts fail")
        # Rebuild after serialization changed the exact original description bytes.
        first = run("build")
        identity = first["artifact_id"]
        run("verify", "--artifact", identity, "--scenario", "unknown", status="unavailable")
        run("verify", "--artifact", identity, "--stage", "compile", status="unavailable")
        destination = work / "generated addon"
        run("promote", "--artifact", identity, "--destination", str(destination), status="unavailable")
        passed("unavailable capabilities and missing compilation receipt cannot pass")
        receipt(identity)
        destination.mkdir()
        (destination / "addon.gproj").write_text("handwritten", encoding="utf-8")
        run("promote", "--artifact", identity, "--destination", str(destination), status="failure")
        assert (destination / "addon.gproj").read_text() == "handwritten"
        (destination / "addon.gproj").unlink()
        (destination / "notes.txt").write_text("preserve", encoding="utf-8")
        run("promote", "--artifact", identity, "--destination", str(destination))
        assert (destination / "notes.txt").read_text() == "preserve"
        owned = destination / "scripts/Game/Beryl/Beryl_Generated.c"
        previous = owned.read_bytes()
        owned.write_bytes(previous + b"\n// handwritten edit\n")
        run("promote", "--artifact", identity, "--destination", str(destination), status="stale_input")
        assert owned.read_bytes() != previous
        owned.write_bytes(previous)
        passed("promotion preserves handwritten files and rejects edited generated output")
        lock = destination.with_name(destination.name + ".beryl-promotion-lock")
        lock.mkdir()
        run("promote", "--artifact", identity, "--destination", str(destination), status="failure")
        lock.rmdir()
        source = project / "pid.be"
        previous_source = source.read_bytes()
        source.write_bytes(previous_source + b"\n")
        run("verify", "--artifact", identity, "--stage", "compile", status="stale_input")
        source.write_bytes(previous_source)
        artifact_source = project / ".beryl-mod/artifacts" / identity / "addon/scripts/Game/Beryl/Beryl_Generated.c"
        artifact_bytes = artifact_source.read_bytes()
        artifact_source.write_bytes(artifact_bytes + b"\n")
        run("promote", "--artifact", identity, "--destination", str(destination), status="stale_input")
        artifact_source.write_bytes(artifact_bytes)
        passed("source changes, artifact changes and concurrent publication locks fail closed")
        # Inject a real rename failure after a previous output was already installed.
        job = mod.Job(project, "promotion-rollback-test", compiler)
        original_replace = os.replace
        calls = 0
        def fail_second(src, dst):
            nonlocal calls
            if str(dst).startswith(str(destination)) and ".rollback-" not in str(src):
                calls += 1
                if calls == 2:
                    raise OSError("injected second publication failure")
            return original_replace(src, dst)
        prior = {str(p.relative_to(destination)): p.read_bytes() for p in destination.rglob("*") if p.is_file()}
        options = argparse.Namespace(artifact=identity, stage=None, scenario=None,
            scenario_count=None, scenario_case=None, measurement_plan=None,
            workbench_tools=None, destination=str(destination))
        with mock.patch.object(os, "replace", side_effect=fail_second):
            try:
                mod.promote(job, options)
                raise AssertionError("publication failure was ignored")
            except OSError as exc:
                assert "injected" in str(exc)
        for name, data in prior.items():
            assert (destination / name).read_bytes() == data
        assert not lock.exists()
        passed("mid-publication write failure restores prior owned files and ownership record")
        installed = work / "installed compiler"
        installed.mkdir()
        local_compiler = installed / compiler.name
        shutil.copyfile(compiler, local_compiler)
        install = subprocess.run([sys.executable, str(ROOT / "tools/beryl-mod/install.py"), "--compiler", str(local_compiler)],
                                 capture_output=True, text=True, encoding="utf-8", timeout=30)
        assert install.returncode == 0, install.stderr
        bundle = json.loads(install.stdout)["bundle"]
        clean_env = env.copy()
        clean_env.pop("BERYL_MOD_TOOL", None)
        command = [str(local_compiler), "mod", "check", "--project", str(project)]
        installed_run = subprocess.run(command, env=clean_env, cwd=work, capture_output=True, text=True, encoding="utf-8", timeout=30)
        assert installed_run.returncode == 0 and json.loads(installed_run.stdout)["status"] == "success", installed_run.stderr
        tool_root = installed / "beryl-tools"
        version_dir = tool_root / bundle
        assert not (version_dir / "__pycache__").exists(), "immutable installed bundle wrote bytecode caches"
        install_argv = [sys.executable, str(ROOT / "tools/beryl-mod/install.py"), "--compiler", str(local_compiler)]
        repeated = subprocess.run(install_argv, capture_output=True, text=True, encoding="utf-8", timeout=30)
        assert repeated.returncode == 0 and json.loads(repeated.stdout)["bundle"] == bundle, repeated.stderr
        controls = {name: (tool_root / name).read_bytes() for name in ("active.json", "mod.py", "mcp.py")}
        installed_manifest = version_dir / "bundle.json"
        manifest_bytes = installed_manifest.read_bytes()
        installed_manifest.write_bytes(b"{}\n")
        rejected = subprocess.run(install_argv, capture_output=True, text=True, encoding="utf-8", timeout=30)
        assert rejected.returncode != 0 and "manifest was modified" in rejected.stderr
        assert all((tool_root / name).read_bytes() == data for name, data in controls.items())
        installed_manifest.write_bytes(manifest_bytes)
        unexpected = version_dir / "unexpected.txt"
        unexpected.write_bytes(b"untracked tool file")
        rejected = subprocess.run(install_argv, capture_output=True, text=True, encoding="utf-8", timeout=30)
        assert rejected.returncode != 0 and "untracked files" in rejected.stderr
        assert all((tool_root / name).read_bytes() == data for name, data in controls.items())
        unexpected.unlink()
        passed("reinstallation validates existing bundle manifests and preserves pointers on corruption")
        verify_installed_loaders(work, project, local_compiler, tool_root, bundle, clean_env, record, passed)
        installed_script = installed / "beryl-tools" / bundle / "mod.py"
        installed_script.write_bytes(installed_script.read_bytes() + b"\n# modified after installation\n")
        tampered = subprocess.run(command, env=clean_env, cwd=work, capture_output=True, text=True, encoding="utf-8", timeout=30)
        assert tampered.returncode != 0 and "installed mod-tool bytes changed" in tampered.stderr
        passed("installed CLI resolves its trusted versioned bundle and rejects changed tool bytes")
        assert record["tool_sha256"] == mod.tool_identity(), "tool changed during verification"
        record["status"] = "success"
    finally:
        mod.write_json(work / "result.json", record)
        print("Evidence: " + str(work / "result.json"), flush=True)


if __name__ == "__main__":
    main()
