#!/usr/bin/env python3
"""Freeze an exploratory terrain schedule, compare payloads, then collect actual target intervals."""
import argparse
import copy
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools/beryl-mod"))
sys.path.insert(0, str(ROOT / "tools/beryl-experiments"))
import mod
import terrain_measurements as measurement
import terrain_scenarios as terrain
import collect


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--beryl", type=Path, required=True)
    parser.add_argument("--workbench-tools", type=Path)
    parser.add_argument("--timer-evidence", type=Path)
    args = parser.parse_args()
    work = Path(tempfile.mkdtemp(prefix="terrain-measurement & spaces-", dir=ROOT / "build"))
    tool = work / "tool-snapshot"
    tool.mkdir()
    for path in [*mod.bundle_paths(), mod.HERE / "install.py"]:
        shutil.copyfile(path, tool / path.name)
    manifest = {p.name: mod.digest(mod.read(p)) for p in mod.bundle_paths()}
    mod.write_json(tool / "bundle.json", manifest)
    compiler = work / "beryl.exe"
    shutil.copyfile(args.beryl.resolve(strict=True), compiler)
    project = work / "project"
    project.mkdir()
    for name in ("pid.be", "pid_test.be", "beryl.mod.json"):
        shutil.copyfile(ROOT / "packages/sparkos/pid" / name, project / name)
    schedule = collect.make_plan("terrain-v2-construction", "exploratory", "exploratory", list(terrain.CASES), 60, 8, measurement.SCOPE_NAME)
    plan_path = work / "schedule.json"
    mod.write_json(plan_path, schedule)
    params = dict(grid=80, case_ids=schedule["case_ids"], plan=schedule, plan_path=str(plan_path), plan_sha256=mod.digest(mod.read(plan_path)))
    record = dict(schema_version=1, status="failure", checks=[], commands=[], compiler_sha256=mod.digest(mod.read(compiler)),
                  tool_sha256=mod.digest(mod.canonical(manifest)), schedule_sha256=params["plan_sha256"], runtime="unavailable: --workbench-tools not selected",
                  scope=measurement.SCOPE, classification="exploratory only; no adoption")
    env = os.environ.copy()
    env["BERYL_PYTHON"] = sys.executable
    env.pop("BERYL_MOD_TOOL", None)

    def passed(name):
        record["checks"].append(name)
        print("passed " + name, flush=True)

    def run(*options, status="success", timeout=120):
        argv = [str(compiler), "mod", *options, "--project", str(project)]
        proc = subprocess.run(argv, env=env, cwd=work, capture_output=True, text=True, encoding="utf-8", timeout=timeout)
        result = json.loads(proc.stdout)
        record["commands"].append(dict(argv=argv, returncode=proc.returncode, stderr=proc.stderr, result=result))
        assert result["status"] == status and (proc.returncode == 0) == (status == "success"), result
        return result

    try:
        measurement.validate_plan(mod, schedule)
        bad_plans = []
        for key, value in (("operations", True), ("operations", 33), ("pair_count", 30), ("scope_name", "renderer"), ("experiment_id", 'bad"; code'), ("phase", "candidate")):
            bad = copy.deepcopy(schedule); bad[key] = value; bad_plans.append(bad)
        bad = copy.deepcopy(schedule); bad["runs"][0]["side"] = "b"; bad_plans.append(bad)
        bad = copy.deepcopy(schedule); bad["runs"].pop(); bad_plans.append(bad)
        bad = copy.deepcopy(schedule); bad["unknown"] = True; bad_plans.append(bad)
        for bad in bad_plans:
            try:
                measurement.validate_plan(mod, bad)
                raise AssertionError("malformed plan passed")
            except mod.Failure:
                pass
        rows = [f"timer|{i}|{i * 2}|{i * 2 + 1}" for i in range(4)]
        for run_info in schedule["runs"]:
            tick = 10 + run_info["ordinal"] * 3
            rows.append(f'run|{run_info["unit_id"]}|{run_info["side"]}|{run_info["ordinal"]}|{run_info["case_id"]}|{tick}|{tick + 2}|8|100|101|1000|1000')
        reply = dict(schema_version=1, kind="beryl.performance.target", token="a" * 64, scope_name=measurement.SCOPE_NAME,
                     timer_api="System.GetTickCount", tick_unit="ms", executed=1, failures=0, expected_runs=120, rows=rows)
        measurement.validate_response(mod, reply, "a" * 64, params)
        for mutate in ("missing", "extra", "reordered", "wrapped", "wrongcounter", "same-timer", "wrongcase", "wrongcount"):
            bad = copy.deepcopy(reply)
            if mutate == "missing": bad["rows"].pop()
            if mutate == "extra": bad["unknown"] = 0
            if mutate == "reordered": bad["rows"][4:6] = bad["rows"][4:6][::-1]
            if mutate == "wrapped": bad["rows"][4] = bad["rows"][4].replace("|10|12|", "|2147483647|0|")
            if mutate == "wrongcounter": bad["rows"][4] = bad["rows"][4].replace("|100|101|", "|-1|101|")
            if mutate == "same-timer": bad["rows"][:4] = [f"timer|{i}|0|0" for i in range(4)]
            if mutate == "wrongcase": bad["rows"][4] = bad["rows"][4].replace("|flat_water|", "|flat_land|")
            if mutate == "wrongcount": bad["expected_runs"] = True
            try:
                measurement.validate_response(mod, bad, "a" * 64, params)
                raise AssertionError("malformed target reply passed: " + mutate)
            except mod.Failure:
                pass
        passed("nine malformed schedules and eight corrupt synthetic target replies rejected")
        installed = subprocess.run([sys.executable, str(tool / "install.py"), "--compiler", str(compiler)], capture_output=True, text=True, timeout=60)
        assert installed.returncode == 0, installed.stderr
        assert json.loads(installed.stdout)["bundle"] == record["tool_sha256"]
        artifact = run("build")["artifact_id"]
        options = ("verify", "--artifact", artifact, "--scenario", "measure.terrain.construction")
        run(*options, status="failure")
        run(*options, "--measurement-plan", str(plan_path), "--measurement-plan", str(plan_path), status="failure")
        run(*options, "--measurement-plan", str(plan_path), "--scenario-case", "flat_water", status="failure")
        run(*options, "--measurement-plan", str(plan_path), status="unavailable")
        passed("typed measurement CLI rejects absent, repeated and conflicting plans")
        if args.workbench_tools:
            if not args.timer_evidence: raise ValueError("actual collection requires --timer-evidence")
            semantic = run("verify", "--artifact", artifact, "--scenario", "compare.terrain.chunks", "--workbench-tools", str(args.workbench_tools.resolve()), timeout=700)
            mod.write_json(work / "semantic-result.json", semantic)
            passed("actual complete terrain v2 payload comparison before timing")
            # This call consumes the already frozen schedule. It does not adapt
            # operation count, pairing or scope after observing performance.
            timing = run(*options, "--measurement-plan", str(plan_path), "--workbench-tools", str(args.workbench_tools.resolve()), timeout=700)
            mod.write_json(work / "measurement-result.json", timing)
            record["runtime"] = timing["scenario_receipt"]
            passed("actual frozen 60-pair / 120-interval / 960-construction target collection")
            environment = {"schema_version": 1, "kind": "beryl.performance.environment_observation", "platform": platform.platform(),
                           "processor": platform.processor(), "logical_processors": os.cpu_count(),
                           "limitations": "No frequency/thermal/process-load instrumentation. Root coordinated no sustained CPU validation during timing; background OS activity unmeasured. One owned Workbench session, no independent reset proof."}
            mod.write_json(work / "environment-evidence.json", environment)
            mod.write_json(work / "environment.json", {"schema_version": 1, "kind": "beryl.performance.environment_review", "status": "reviewed",
                "description": environment["limitations"], "evidence": {"path": "environment-evidence.json", "sha256": mod.digest(mod.read(work / "environment-evidence.json"))}})
            timing_job = Path(timing["result_path"]).parent
            semantic_job = Path(semantic["result_path"]).parent
            argv = [sys.executable, str(ROOT / "tools/beryl-experiments/import_terrain.py"), "--measurement-receipt", str(work / "measurement-result.json"),
                    "--semantic-receipt", str(work / "semantic-result.json"), "--schedule", str(plan_path), "--candidate", str(timing_job / "scenario-candidate.json"),
                    "--candidate-root", str(timing_job / "candidate"), "--semantic-candidate", str(semantic_job / "scenario-candidate.json"), "--semantic-candidate-root", str(semantic_job / "candidate"),
                    "--tool-root", str(tool), "--tool-manifest", str(tool / "bundle.json"), "--integration-root", str(args.workbench_tools.resolve()), "--compiler", str(compiler),
                    "--timer-evidence", str(args.timer_evidence.resolve()), "--environment", str(work / "environment.json"), "--output", str(work / "collection")]
            imported = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8", timeout=120)
            record["import"] = dict(argv=argv, returncode=imported.returncode, stdout=imported.stdout, stderr=imported.stderr)
            assert imported.returncode == 0, record["import"]
            passed("actual receipt import and immutable exploratory journal")
        record["status"] = "success"
    finally:
        mod.write_json(work / "result.json", record)
        print("Evidence: " + str(work / "result.json"), flush=True)


if __name__ == "__main__":
    main()
