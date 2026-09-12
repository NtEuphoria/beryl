#!/usr/bin/env python3
"""Verify typed storage probes, strict replies, trusted installation and real VM evidence."""
import argparse
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools/beryl-mod"))
import mod
import install
import storage_scenarios as storage


def checksum(rows):
    out = 0
    for byte in ("\n".join(rows) + "\n").encode("ascii"):
        out = (out * 31 + byte) % 1000003
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--beryl", type=Path, required=True)
    parser.add_argument("--workbench-tools", type=Path)
    parser.add_argument("--terrain-tool-snapshot", type=Path)
    args = parser.parse_args()
    work = Path(tempfile.mkdtemp(prefix="storage-scenarios & spaces-", dir=ROOT / "build"))
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
    env = os.environ.copy()
    env["BERYL_PYTHON"] = sys.executable
    env.pop("BERYL_MOD_TOOL", None)
    record = dict(schema_version=1, status="failure", checks=[], commands=[], compiler_sha256=mod.digest(mod.read(compiler)),
                  tool_sha256=mod.tool_identity(), runtime="unavailable: --workbench-tools not selected")

    def passed(name):
        record["checks"].append(name)
        print("passed " + name, flush=True)

    def run(*options, status="success", timeout=120):
        argv = [str(compiler), "mod", *options, "--project", str(project)]
        proc = subprocess.run(argv, cwd=work, env=env, capture_output=True, text=True, encoding="utf-8", timeout=timeout)
        result = json.loads(proc.stdout)
        record["commands"].append(dict(argv=argv, returncode=proc.returncode, stderr=proc.stderr, result=result))
        assert result["status"] == status and (proc.returncode == 0) == (status == "success"), result
        return result

    try:
        params = {"probe": "array", "case_ids": list(storage.ARRAY_CASES)}
        rows, checks = storage.expected(params)
        valid = dict(token="a" * 64, executed=1, checks=checks, failures=0, checksum=checksum(rows), caseIds=params["case_ids"], rows=rows)
        storage.validate_response(mod, valid, "a" * 64, params)
        canvas_params = {"probe": "canvas", "case_ids": list(storage.CANVAS_CASES)}
        canvas_rows, canvas_checks = storage.expected(canvas_params)
        canvas_valid = dict(token="a" * 64, executed=1, checks=canvas_checks, failures=0, checksum=checksum(canvas_rows), caseIds=canvas_params["case_ids"], rows=canvas_rows)
        storage.validate_response(mod, canvas_valid, "a" * 64, canvas_params)
        canvas_bad = copy.deepcopy(canvas_valid)
        canvas_bad["rows"][1] = "value|control-held-outer|0"
        canvas_bad["checksum"] = checksum(canvas_bad["rows"])
        try:
            storage.validate_response(mod, canvas_bad, "a" * 64, canvas_params)
            raise AssertionError("broken observer control passed")
        except mod.Failure:
            pass
        mutations = []
        for field, value in (("checks", checks - 1), ("checks", True), ("executed", 0), ("failures", 1),
                             ("caseIds", params["case_ids"][::-1]), ("caseIds", []), ("token", "b" * 64),
                             ("checksum", valid["checksum"] + 1), ("rows", rows[:-1])):
            bad = copy.deepcopy(valid); bad[field] = value; mutations.append(bad)
        bad = copy.deepcopy(valid); bad["unknown"] = 0; mutations.append(bad)
        bad = copy.deepcopy(valid); bad["rows"][1] = "value|alias-first|11"; bad["checksum"] = checksum(bad["rows"]); mutations.append(bad)
        for bad in mutations:
            try:
                storage.validate_response(mod, bad, "a" * 64, params)
                raise AssertionError("malformed or incomplete storage response passed")
            except mod.Failure:
                pass
        passed("eleven synthetic reply corruptions rejected, including recomputed checksum semantic mutation")

        if args.terrain_tool_snapshot:
            prior = subprocess.run([sys.executable, str(args.terrain_tool_snapshot.resolve() / "install.py"), "--compiler", str(compiler)], capture_output=True, text=True, timeout=60)
            assert prior.returncode == 0, prior.stderr
            prior_id = json.loads(prior.stdout)["bundle"]
            assert (work / "beryl-tools/mod.py").read_bytes() == install.TERRAIN_LOADER
        installed = subprocess.run([sys.executable, str(tool / "install.py"), "--compiler", str(compiler)], capture_output=True, text=True, timeout=60)
        assert installed.returncode == 0, installed.stderr
        current_id = json.loads(installed.stdout)["bundle"]
        base = work / "beryl-tools"
        if args.terrain_tool_snapshot:
            assert (base / ("loader-v3-" + mod.digest(install.TERRAIN_LOADER) + ".py")).read_bytes() == install.TERRAIN_LOADER
            mod.write_json(base / "active.json", {"bundle": prior_id})
            run("scenarios")
            mod.write_json(base / "active.json", {"bundle": current_id})
            passed("exact prior terrain13 loader upgrade and bundle rollback")
        listed = run("scenarios")
        artifact = run("build")["artifact_id"]
        options = ("verify", "--artifact", artifact, "--scenario", "probe.array.storage")
        for invalid in (("--scenario-count", "3"), ("--scenario-case", "unknown"),
                        ("--scenario-case", "nested_copy", "--scenario-case", "nested_copy"), ("--stage", "compile")):
            run(*options, *invalid, status="failure")
        run(*options, status="unavailable")
        passed("installed typed parameters, unknown/duplicate cases, count and unavailable execution")
        template = base / current_id / "array-storage.c.in"
        original = template.read_bytes()
        template.write_bytes(original + b"\n")
        proc = subprocess.run([str(compiler), "mod", "scenarios"], env=env, capture_output=True, text=True, timeout=30)
        assert proc.returncode != 0 and "bytes changed" in proc.stderr
        template.write_bytes(original)
        passed("installed template tampering rejected before dispatch")
        if args.workbench_tools:
            result = run(*options, "--workbench-tools", str(args.workbench_tools.resolve()), timeout=700)
            receipt = result["scenario_receipt"]
            assert receipt["trace"]["checks"] == checks and receipt["trace"]["events"] == len(rows)
            record["runtime"] = receipt
            passed(f"actual engine array storage: {checks} observations across six cases")
            canvas_result = run("verify", "--artifact", artifact, "--scenario", "probe.canvas.retention", "--workbench-tools", str(args.workbench_tools.resolve()), timeout=700)
            record["canvas_runtime"] = canvas_result["scenario_receipt"]
            assert record["canvas_runtime"]["trace"]["checks"] == canvas_checks
            assert record["canvas_runtime"]["scenario_contract"]["pooling_admission"] == "unavailable"
            passed(f"actual Canvas script-reference probe: {canvas_checks} observations; rendered-consumer gate remains unavailable")
        record["status"] = "success"
    finally:
        mod.write_json(work / "result.json", record)
        print("Evidence: " + str(work / "result.json"), flush=True)


if __name__ == "__main__":
    main()
