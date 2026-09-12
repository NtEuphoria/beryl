#!/usr/bin/env python3
"""Isolated terrain payload comparison, protocol negatives and loader migration.

Synthetic response mutations and the loader marker are explicitly policy tests.
--workbench-tools executes all admitted datasets and a deliberately broken
candidate in separately owned sessions. No runtime timing is a speed benchmark.
"""
from pathlib import Path
import argparse
import copy
import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools/beryl-mod"))
import mod
import install
import terrain_scenarios as terrain


def checksum(rows):
    value = 0
    for byte in ("\n".join(rows) + "\n").encode("ascii"):
        value = (value * 31 + byte) % 1000003
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--beryl", type=Path, required=True)
    parser.add_argument("--workbench-tools", type=Path)
    parser.add_argument("--map-tool-snapshot", type=Path, required=True,
                        help="Earlier verified eight-file tools/beryl-mod directory, including its installer")
    args = parser.parse_args()
    work = Path(tempfile.mkdtemp(prefix="terrain-scenario & spaces-", dir=ROOT / "build"))
    tool = work / "tool-snapshot"
    tool.mkdir()
    for path in [*mod.bundle_paths(), mod.HERE / "install.py"]:
        shutil.copyfile(path, tool / path.name)
    compiler = work / "beryl.exe"
    shutil.copyfile(args.beryl.resolve(strict=True), compiler)
    project = work / "project"
    project.mkdir()
    for name in ("pid.be", "pid_test.be", "beryl.mod.json"):
        shutil.copyfile(ROOT / "packages/sparkos/pid" / name, project / name)
    record = dict(schema_version=1, status="failure", compiler_sha256=mod.digest(mod.read(compiler)),
                  tool_sha256=mod.tool_identity(), checks=[], commands=[],
                  scope=terrain.SCOPE, runtime="unavailable: --workbench-tools not selected")
    env = os.environ.copy()
    env.update(BERYL_PYTHON=sys.executable, BERYL_MOD_TOOL=str(tool / "mod.py"))

    def run(*arguments, status="success", timeout=120):
        argv = [str(compiler), "mod", *arguments, "--project", str(project)]
        proc = subprocess.run(argv, env=env, cwd=work, capture_output=True, text=True, encoding="utf-8", timeout=timeout)
        result = json.loads(proc.stdout)
        record["commands"].append(dict(argv=argv, returncode=proc.returncode, stderr=proc.stderr, result=result))
        assert result["status"] == status and (proc.returncode == 0) == (status == "success"), result
        return result

    def passed(name):
        record["checks"].append(name)
        print("passed " + name, flush=True)

    try:
        params = dict(grid=80, case_ids=list(terrain.CASES))
        rows, checks = terrain.expected(mod, params)
        assert all(sum(terrain.dataset(mod, name)["band_quads"]) == 6241 for name in terrain.CASES)
        for name, band in (("flat_water", 7), ("flat_land", 0), ("sea_threshold_checker", 7), ("narrow_height_range", 0)):
            data = terrain.dataset(mod, name)
            # Analytic constant classification: 26 full chunks and one 1-quad tail.
            assert data["chunks"] == [(band, 240)] * 26 + [(band, 1)]
        valid = dict(token="a" * 64, executed=1, checks=checks, failures=0, checksum=checksum(rows), caseIds=params["case_ids"], rows=rows)
        terrain.validate_response(mod, valid, "a" * 64, params)
        corrupt = []
        for field, value in (("checks", checks - 1), ("checksum", valid["checksum"] + 1), ("caseIds", []), ("executed", 0), ("failures", 1)):
            bad = copy.deepcopy(valid); bad[field] = value; corrupt.append(bad)
        for suffix in ("|239|0|1912|1434", "|240|0|1920|1440"):
            bad = copy.deepcopy(valid)
            bad["rows"][2] = "chunk|flat_water|0|7" + suffix
            bad["checksum"] = checksum(bad["rows"])
            corrupt.append(bad)
        bad = copy.deepcopy(valid); bad["rows"][0] = "float-equality|unverified"; bad["checksum"] = checksum(bad["rows"]); corrupt.append(bad)
        for bad in corrupt:
            try:
                terrain.validate_response(mod, bad, "a" * 64, params)
                raise AssertionError("corrupt terrain response passed")
            except mod.Failure:
                pass
        passed("analytic chunk boundary fixtures and eight corrupt synthetic replies")
        first = run("build")
        artifact = first["artifact_id"]
        options = ("verify", "--artifact", artifact, "--scenario", "compare.terrain.chunks")
        for invalid in (("--scenario-count", "80"), ("--scenario-case", "unknown"),
                        ("--scenario-case", "flat_land", "--scenario-case", "flat_land"), ("--stage", "compile")):
            run(*options, *invalid, status="failure")
        run(*options, status="unavailable")
        passed("typed terrain cases reject arbitrary counts, duplicates and unavailable engine execution")

        # Actual prior eight-file installer plus an explicit synthetic v1 marker.
        local = work / "installed"
        local.mkdir()
        local_compiler = local / "beryl.exe"
        shutil.copyfile(compiler, local_compiler)
        base = local / "beryl-tools"
        base.mkdir()
        old = {"mod.py": b'print("synthetic-v1-policy-marker")\n', "process_job.py": b"", "engine-compile.ps1": b"", "beryl.mod.v1.schema.json": b"{}"}
        hashes = {name: mod.digest(value) for name, value in old.items()}
        old_id = mod.digest(mod.canonical(hashes))
        (base / old_id).mkdir()
        for name, value in old.items(): (base / old_id / name).write_bytes(value)
        mod.write_json(base / old_id / "bundle.json", hashes)
        (base / "mod.py").write_bytes(install.LEGACY_LOADER)
        mod.write_json(base / "active.json", {"bundle": old_id})
        map_install = subprocess.run([sys.executable, str(args.map_tool_snapshot.resolve() / "install.py"), "--compiler", str(local_compiler)], capture_output=True, text=True, timeout=60)
        assert map_install.returncode == 0, map_install.stderr
        map_id = json.loads(map_install.stdout)["bundle"]
        assert (base / "mod.py").read_bytes() == install.MAP_LOADER
        upgrade = [sys.executable, str(tool / "install.py"), "--compiler", str(local_compiler)]
        current_install = subprocess.run(upgrade, capture_output=True, text=True, timeout=60)
        assert current_install.returncode == 0, current_install.stderr
        current_id = json.loads(current_install.stdout)["bundle"]
        assert (base / "mod.py").read_bytes() == install.LOADER
        assert (base / ("loader-v2-" + mod.digest(install.MAP_LOADER) + ".py")).read_bytes() == install.MAP_LOADER
        clean_env = env.copy(); clean_env.pop("BERYL_MOD_TOOL", None)
        for identity in (old_id, map_id, current_id):
            mod.write_json(base / "active.json", {"bundle": identity})
            restored = subprocess.run([str(local_compiler), "mod", "scenarios"], env=clean_env, capture_output=True, text=True, timeout=30)
            assert restored.returncode == 0, restored.stderr
            if identity == old_id: assert "synthetic-v1-policy-marker" in restored.stdout
            else: assert json.loads(restored.stdout)["status"] == "success"
        prior = (base / "mod.py").read_bytes()
        (base / "mod.py").write_bytes(b"# unrecognized loader\n")
        refused = subprocess.run(upgrade, capture_output=True, text=True, timeout=60)
        assert refused.returncode != 0 and "unrecognized" in refused.stderr
        (base / "mod.py").write_bytes(prior)
        reference = base / current_id / "terrain-reference.c.txt"
        previous_reference = reference.read_bytes()
        reference.write_bytes(previous_reference + b"\n")
        changed = subprocess.run([str(local_compiler), "mod", "scenarios"], env=clean_env, capture_output=True, text=True, timeout=30)
        assert changed.returncode != 0 and "bytes changed" in changed.stderr
        reference.write_bytes(previous_reference)
        passed(f"original4 to verified map8 to current{len(mod.bundle_paths())} upgrade, both rollbacks and tamper refusal")

        if args.workbench_tools:
            # Use the installed trusted current bundle for the actual run.
            compiler = local_compiler
            env = clean_env
            result = run(*options, "--workbench-tools", str(args.workbench_tools.resolve()), timeout=700)
            receipt = result["scenario_receipt"]
            assert receipt["trace"]["checks"] == checks and receipt["trace"]["events"] == len(rows)
            record["runtime"] = receipt
            passed(f"actual installed engine comparison: {checks} payload checks across six datasets")
            # Deliberately broken isolated candidate proves VM differences cannot
            # be promoted to a successful comparison receipt. Production is untouched.
            compiler = work / "beryl.exe"
            env = clean_env.copy(); env["BERYL_MOD_TOOL"] = str(tool / "mod.py")
            adapter = tool / "terrain-adapter.c.in"
            data = adapter.read_text(encoding="utf-8")
            assert data.count("float x2 = x + cw;") == 1
            adapter.write_text(data.replace("float x2 = x + cw;", "float x2 = x + cw + 1.0;"), encoding="utf-8", newline="\n")
            broken_artifact = run("build")["artifact_id"]
            failed = run("verify", "--artifact", broken_artifact, "--scenario", "compare.terrain.chunks", "--scenario-case", "flat_land",
                         "--workbench-tools", str(args.workbench_tools.resolve()), status="failure", timeout=700)
            raw = failed.get("scenario_runtime", {}).get("rpc", {}).get("Response", {})
            assert raw.get("failures", 0) > 0 and raw.get("executed") == 0, failed
            record["mutation_runtime"] = {"status": "expected_failure", "result": failed}
            passed("actual changed-vertex candidate fails VM comparison and produces no success receipt")
        record["status"] = "success"
    finally:
        mod.write_json(work / "result.json", record)
        print("Evidence: " + str(work / "result.json"), flush=True)


if __name__ == "__main__":
    main()
