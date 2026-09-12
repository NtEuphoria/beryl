#!/usr/bin/env python3
"""Typed scenario protocol/installation regressions; optional real owned engine probes.

Synthetic replies exercise validation only. Only --workbench-tools runs the VM.
All projects, installs, receipts and engine candidates stay in an isolated build tree.
"""
from pathlib import Path
import argparse
import copy
import ctypes
import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools/beryl-mod"))
import mod
import scenarios
import install


def reply(params, token):
    rows = []
    checks = 0
    for case in params["case_ids"]:
        entries = scenarios.expected_entries(case, params["count"])
        rows.append(f"case|{case}|{len(entries)}")
        for index, (key, serial) in enumerate(entries.items()):
            rows.append(f"entry|{case}|{index}|{key}|{key}|{serial}|{serial}|1")
        rows.append(f"end|{case}|{len(entries)}")
        checks += 1 + len(entries)
    result = dict(token=token, executed=1, checks=checks, failures=0,
                  checksum=0, caseIds=params["case_ids"], rows=rows)
    recheck(result)
    return result


def recheck(result):
    checksum = 0
    for value in ("\n".join(result["rows"]) + "\n").encode("ascii"):
        checksum = (checksum * 31 + value) % 1000003
    result["checksum"] = checksum


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--beryl", required=True, type=Path)
    parser.add_argument("--workbench-tools", type=Path)
    args = parser.parse_args()
    compiler = args.beryl.resolve(strict=True)
    work = Path(tempfile.mkdtemp(prefix="mod-scenarios & spaces-", dir=ROOT / "build"))
    project = work / "project"
    project.mkdir()
    for name in ("pid.be", "pid_test.be", "beryl.mod.json"):
        shutil.copyfile(ROOT / "packages/sparkos/pid" / name, project / name)
    record = dict(schema_version=1, status="failure", checks=[], commands=[],
                  compiler_sha256=mod.digest(mod.read(compiler)), tool_sha256=mod.tool_identity(),
                  runtime="unavailable: --workbench-tools not selected")
    env = os.environ.copy()
    env.update(BERYL_PYTHON=sys.executable, BERYL_MOD_TOOL=str(ROOT / "tools/beryl-mod/mod.py"))

    def run(*arguments, status="success", timeout=120):
        argv = [str(compiler), "mod", *arguments, "--project", str(project)]
        process = subprocess.run(argv, env=env, cwd=work, capture_output=True, text=True, encoding="utf-8", timeout=timeout)
        result = json.loads(process.stdout)
        record["commands"].append(dict(argv=argv, exit_code=process.returncode, result=result, stderr=process.stderr))
        assert result["status"] == status and (process.returncode == 0) == (status == "success"), result
        return result

    def passed(name):
        record["checks"].append(name)
        print("passed " + name, flush=True)

    try:
        discovered = run("scenarios")
        assert not (project / ".beryl-mod").exists(), "discovery created a job"
        expected = {name: "implemented" for name in (
            "probe.map.cursor", "compare.terrain.chunks", "probe.array.storage",
            "probe.canvas.retention", "measure.terrain.construction")}
        expected.update({name: "unavailable" for name in (
            "trace.mesh.query", "trace.mesh.sensor", "trace.mesh.expiry")})
        entries = discovered["scenarios"]
        assert len(entries) == len(expected)
        by_name = {item["name"]: item for item in entries}
        assert len(by_name) == len(entries), "duplicate scenario identity"
        assert {name: item["implementation"] for name, item in by_name.items()} == expected
        assert by_name["probe.map.cursor"]["case_ids"] == list(scenarios.CASE_IDS)
        passed("read-only typed registry reports the exact implemented and unavailable scenario sets")
        params = dict(count=7, case_ids=list(scenarios.CASE_IDS))
        valid = reply(params, "a" * 64)
        scenarios.validate_response(mod, valid, "a" * 64, params)
        mutations = []
        for field, value in (("executed", 0), ("checks", valid["checks"] - 1), ("failures", 1),
                             ("checksum", valid["checksum"] + 1), ("token", "b" * 64),
                             ("executed", True), ("caseIds", list(reversed(scenarios.CASE_IDS))),
                             ("caseIds", ["empty"] * 6), ("rows", valid["rows"][:-1])):
            bad = copy.deepcopy(valid); bad[field] = value; mutations.append(bad)
        bad = copy.deepcopy(valid); bad["unknown"] = 1; mutations.append(bad)
        bad = copy.deepcopy(valid); del bad["checksum"]; mutations.append(bad)
        entry = next(i for i, row in enumerate(valid["rows"]) if row.startswith("entry|"))
        for field, value in ((2, "9"), (3, "unknown"), (4, "entity:999"), (5, "999"), (7, "0")):
            bad = copy.deepcopy(valid); parts = bad["rows"][entry].split("|"); parts[field] = value
            bad["rows"][entry] = "|".join(parts); recheck(bad); mutations.append(bad)
        bad = copy.deepcopy(valid); bad["rows"][entry + 1] = bad["rows"][entry]; recheck(bad); mutations.append(bad)
        for bad in mutations:
            try:
                scenarios.validate_response(mod, bad, "a" * 64, params)
                raise AssertionError("corrupt synthetic receipt passed")
            except mod.Failure:
                pass
        passed(f"synthetic protocol validation rejects {len(mutations)} incomplete or corrupt replies")
        artifact = run("build")["artifact_id"]
        artifact_path = project / ".beryl-mod/artifacts" / artifact
        source_map = artifact_path / "source-map.json"
        mapping = mod.parse(mod.read(source_map))
        assert any(item.get("companion", {}).get("json_pointer") == "/exports/0" for item in mapping["exports"])
        saved_map = source_map.read_bytes()
        source_map.write_bytes(saved_map + b"\n")
        run("verify", "--artifact", artifact, "--scenario", "probe.map.cursor", status="stale_input")
        source_map.write_bytes(saved_map)
        passed("source-map sidecar is hashed and resolves companion export locations")
        options = ("verify", "--artifact", artifact, "--scenario", "probe.map.cursor")
        for invalid in (("--scenario-count", "0"), ("--scenario-count", "4097"),
                        ("--scenario-count", "2", "--scenario-count", "3"),
                        ("--scenario-case", "unknown"), ("--scenario-case", ""),
                        ("--scenario-case", "empty", "--scenario-case", "empty"),
                        ("--stage", "compile")):
            run(*options, *invalid, status="failure")
        run("check", "--scenario-case", "empty", status="failure")
        run("verify", "--artifact", artifact, "--scenario-count", "1", status="failure")
        run(*options, status="unavailable")
        for name in ("unknown", *scenarios.UNAVAILABLE):
            run("verify", "--artifact", artifact, "--scenario", name, status="unavailable")
        passed("typed count and case selections reject invalid or unavailable execution")

        # Explicit synthetic v1 bundle tests compatibility, never engine success.
        local = work / "installed"
        local.mkdir()
        local_compiler = local / compiler.name
        shutil.copyfile(compiler, local_compiler)
        toolroot = local / "beryl-tools"
        toolroot.mkdir()
        legacy = {"mod.py": b'print("synthetic-v1-loader-accepted")\n', "process_job.py": b"",
                  "engine-compile.ps1": b"", "beryl.mod.v1.schema.json": b"{}"}
        hashes = {name: mod.digest(data) for name, data in legacy.items()}
        legacy_id = mod.digest(mod.canonical(hashes))
        legacy_path = toolroot / legacy_id
        legacy_path.mkdir()
        for name, data in legacy.items():
            (legacy_path / name).write_bytes(data)
        mod.write_json(legacy_path / "bundle.json", hashes)
        mod.write_json(toolroot / "active.json", {"bundle": legacy_id})
        (toolroot / "mod.py").write_bytes(install.LEGACY_LOADER)
        command = [sys.executable, str(ROOT / "tools/beryl-mod/install.py"), "--compiler", str(local_compiler)]
        installed = subprocess.run(command, capture_output=True, text=True, timeout=60)
        assert installed.returncode == 0, installed.stderr
        current_id = json.loads(installed.stdout)["bundle"]
        assert (toolroot / "mod.py").read_bytes() == install.LOADER
        assert (toolroot / ("loader-v1-" + mod.digest(install.LEGACY_LOADER) + ".py")).read_bytes() == install.LEGACY_LOADER
        mod.write_json(toolroot / "active.json", {"bundle": legacy_id})
        rollback = subprocess.run([sys.executable, str(toolroot / "mod.py")], capture_output=True, text=True, timeout=30)
        assert rollback.returncode == 0 and "synthetic-v1-loader-accepted" in rollback.stdout
        mod.write_json(toolroot / "active.json", {"bundle": current_id})
        clean = env.copy(); clean.pop("BERYL_MOD_TOOL", None)
        installed_command = [str(local_compiler), "mod", "scenarios"]
        discovered = subprocess.run(installed_command, env=clean, capture_output=True, text=True, timeout=30)
        assert discovered.returncode == 0 and json.loads(discovered.stdout)["status"] == "success", discovered.stderr
        handler = toolroot / current_id / "map-cursor.c.in"
        handler.write_bytes(handler.read_bytes() + b"\n")
        tampered = subprocess.run(installed_command, env=clean, capture_output=True, text=True, timeout=30)
        assert tampered.returncode != 0 and "bytes changed" in tampered.stderr
        passed("known v1 loader upgrades atomically, supports rollback and rejects changed probe bytes")
        if os.name == "nt":
            from ctypes import wintypes
            kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel.CreateMutexW.argtypes = (ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR)
            kernel.CreateMutexW.restype = wintypes.HANDLE
            kernel.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
            kernel.ReleaseMutex.argtypes = (wintypes.HANDLE,)
            kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
            mutex = kernel.CreateMutexW(None, False, "Local\\BerylOwnedWorkbenchSessionV1")
            assert mutex and kernel.WaitForSingleObject(mutex, 0) == 0, "another engine job owns the gate"
            try:
                for name in ("engine-compile.ps1", "scenario-engine-run.ps1"):
                    result_path = work / (name + "-busy.json")
                    argv = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                            str(mod.HERE / name), "-ToolRoot", str(work / "missing-tools"),
                            "-ProjectDir", str(project), "-ResultPath", str(result_path)]
                    if name == "engine-compile.ps1":
                        argv += ["-ExpectedVersion", "0.0.0.0"]
                    else:
                        argv += ["-ProjectId", "Probe", "-Token", "0" * 64, "-Function", "Probe",
                                 "-ExpectedEngineHash", "0" * 64, "-ExpectedEngineVersion", "0.0.0.0"]
                    busy = subprocess.run(argv, capture_output=True, text=True, timeout=30)
                    result = mod.parse(mod.read(result_path))
                    assert busy.returncode != 0 and result["status"] == "unavailable" and "session gate" in result["failure"], result
                    assert result.get("engine_sha256") is None, "busy operation inspected or launched an engine"
            finally:
                kernel.ReleaseMutex(mutex)
                kernel.CloseHandle(mutex)
            for status in ("failure", "unavailable", "timeout", "cancelled", "stale_input"):
                assert mod.engine_failure(mod.Failure("process exited"), {"status": status}).status == status
            passed("cross-process session mutex rejects both compile and runtime contenders before engine access")
            # Fake build adapter returns a timeout without launching any engine.
            fake = work / "synthetic-timeout-tools/scripts"
            fake.mkdir(parents=True)
            quoted_python = str(Path(sys.executable).resolve()).replace("'", "''")
            (fake / "Find-Workbench.ps1").write_text("[pscustomobject]@{WorkbenchExe='" + quoted_python + "'}\n", encoding="utf-8")
            (fake / "Invoke-ReforgerBuild.ps1").write_text("param($ProjectDir,$TimeoutSeconds)\n[pscustomobject]@{Ok=$false;Stage='Timeout';Summary='synthetic adapter timeout';Diagnostics=@()}\n", encoding="utf-8")
            for name in ("Invoke-Workbench.ps1", "Get-WorkbenchErrors.ps1"):
                (fake / name).write_text("# synthetic adapter; does not execute an engine\n", encoding="utf-8")
            version = subprocess.run(["powershell.exe", "-NoProfile", "-Command", "(Get-Item -LiteralPath '" + quoted_python + "').VersionInfo.FileVersion"],
                                     capture_output=True, text=True, check=True, timeout=30).stdout.strip()
            assert version
            timed_path = work / "synthetic-timeout.json"
            timed = subprocess.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(mod.HERE / "engine-compile.ps1"),
                "-ToolRoot", str(fake.parent), "-ProjectDir", str(project), "-ResultPath", str(timed_path), "-ExpectedVersion", version],
                capture_output=True, text=True, timeout=30)
            timed_result = mod.parse(mod.read(timed_path))
            assert timed.returncode != 0 and timed_result["status"] == "timeout", timed_result
            passed("synthetic compile timeout is retained as timeout, independently of process exit code")
        if args.workbench_tools:
            probes = []
            for count in (1, 64):
                result = run(*options, "--scenario-count", str(count), "--workbench-tools", str(args.workbench_tools.resolve()), timeout=700)
                receipt = result["scenario_receipt"]
                assert receipt["parameters"] == dict(count=count, case_ids=list(scenarios.CASE_IDS))
                assert receipt["trace"]["events"] == sum(2 + len(scenarios.expected_entries(case, count)) for case in scenarios.CASE_IDS)
                probes.append(receipt)
                print(f"passed actual engine map probe count={count}, checks={receipt['trace']['checks']}", flush=True)
            record["runtime"] = probes
            passed("actual engine complete ordered histories at counts 1 and 64")
        assert record["tool_sha256"] == mod.tool_identity(), "tool changed during verification"
        record["status"] = "success"
    finally:
        mod.write_json(work / "result.json", record)
        print("Evidence: " + str(work / "result.json"), flush=True)


if __name__ == "__main__":
    main()
