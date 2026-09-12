#!/usr/bin/env python3
"""Stage the current MESH bytes and replace PID only in an isolated candidate."""
from pathlib import Path
import argparse
import hashlib
import os
import re
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools/beryl-mod"))
import mod

PID_PATH = "scripts/Game/SparkOSMesh/Flight/SPK_PID.c"
ORIGINAL_HASH = "f03f8588b9c4c4298db1e933b4aafab5e778725faf30b4c734e23aa2b1bb2460"


def hash_file(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def inventory(root):
    result = {}
    for directory, folders, names in os.walk(root):
        folders[:] = sorted(name for name in folders if name not in (".git", ".beryl-cache", ".beryl-mod", "__pycache__"))
        for name in sorted(names):
            path = Path(directory) / name
            if path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction()):
                raise RuntimeError("Linked MESH inputs require explicit admission: " + str(path))
            result[path.relative_to(root).as_posix()] = hash_file(path)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--beryl", type=Path, required=True)
    parser.add_argument("--comparison", type=Path, required=True, help="Successful verify-pid evidence directory")
    parser.add_argument("--mesh", type=Path, required=True)
    parser.add_argument("--workbench-tools", type=Path, required=True)
    args = parser.parse_args()
    source = args.mesh.resolve(strict=True)
    comparison = args.comparison.resolve(strict=True)
    proof = mod.parse(mod.read(comparison / "result.json"))
    if proof.get("status") != "success" or proof.get("engine", {}).get("status") != "success":
        raise RuntimeError("Complete PID engine comparison must pass first")
    compiler = args.beryl.resolve(strict=True)
    if proof["compiler_sha256"] != hash_file(compiler):
        raise RuntimeError("Compiler differs from the verified PID comparison")
    for name, expected in proof["source_hashes"].items():
        if hash_file(ROOT / "packages/sparkos/pid" / name) != expected:
            raise RuntimeError("PID source differs from verified comparison")
    generated = comparison / "comparison/scripts/Game/Beryl/Beryl_Generated.c"
    if hash_file(generated) != proof["artifact_files"]["scripts\\Game\\Beryl\\Beryl_Generated.c"]:
        raise RuntimeError("Verified generated PID artifact changed")
    if hash_file(source / PID_PATH) != ORIGINAL_HASH:
        raise RuntimeError("Current MESH PID differs from the preserved original fixture")
    work = Path(tempfile.mkdtemp(prefix="mesh-pid-", dir=ROOT / "build"))
    job = mod.Job(work, "mesh-pid-integration", compiler)
    job.result["status"] = "failure"
    print("MESH candidate artifacts: " + str(work), flush=True)
    try:
        baseline = inventory(source)
        candidate = work / "addons/SparkOS_Mesh"
        candidate.mkdir(parents=True)
        for name in baseline:
            target = mod.safe_path(candidate, name)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(mod.safe_path(source, name, True), target)
        if inventory(candidate) != baseline or inventory(source) != baseline:
            raise RuntimeError("MESH source changed while staging")
        mod.write_json(work / "mesh-baseline.json", {"source": str(source), "files": baseline})
        token = mod.digest(mod.canonical({"mesh": baseline, "pid_comparison": proof["token"], "handover": hash_file(ROOT / "tests/pid/MeshHandover.c.in")}))
        # Explicit migration: preserve original bytes outside script discovery.
        rollback = work / "rollback"
        rollback.mkdir()
        shutil.copyfile(candidate / PID_PATH, rollback / "SPK_PID.c.fixture")
        shutil.copyfile(generated, candidate / PID_PATH)
        fixture = (ROOT / "tests/pid/MeshHandover.c.in").read_text().replace("@TOKEN@", token)
        (candidate / "scripts/Game/SparkOSMesh/Debug/BerylPidHandover.c").write_text(fixture, encoding="utf-8", newline="\n")
        identity = '''class BerylMeshIdentityRequest : JsonApiStruct {
string token;
void BerylMeshIdentityRequest() { RegV("token"); }
}
class BerylMeshIdentityResponse : JsonApiStruct {
int ok;
string token;
void BerylMeshIdentityResponse() { RegV("ok"); RegV("token"); }
}
class BerylMeshIdentity : NetApiHandler {
override JsonApiStruct GetRequest() { return new BerylMeshIdentityRequest(); }
override JsonApiStruct GetResponse(JsonApiStruct request) {
BerylMeshIdentityRequest req = BerylMeshIdentityRequest.Cast(request);
BerylMeshIdentityResponse response = new BerylMeshIdentityResponse();
response.token = "@TOKEN@";
if (req && req.token == response.token) response.ok = 1;
return response;
}
}
'''.replace("@TOKEN@", token)
        (candidate / "scripts/WorkbenchGameCommon/BerylMeshIdentity.c").write_text(identity, encoding="utf-8", newline="\n")
        definitions = sum(len(re.findall(r"\bclass\s+SPK_PID\b", p.read_text(encoding="utf-8-sig")))
                          for p in (candidate / "scripts").rglob("*.c"))
        if definitions != 1:
            raise RuntimeError(f"Expected exactly one production SPK_PID, found {definitions}")
        # Harden the existing acceptance launcher in this owned candidate only.
        wrapper = candidate / "tools/Run-MeshAcceptance.ps1"
        text = wrapper.read_text(encoding="utf-8-sig")
        begin = text.index("if ($mine.Count -gt 0) {")
        end = text.index("\n}", begin) + 2
        text = text[:begin] + "if ($mine.Count -gt 0) { throw 'An existing acceptance session is not owned by this run' }" + text[end:]
        wrapper.write_text(text, encoding="utf-8-sig", newline="\n")
        staged = inventory(candidate)
        job.result.update(token=token, candidate=str(candidate), source_sha256=mod.digest(mod.canonical(baseline)),
                          artifact_sha256=mod.digest(mod.canonical(staged)), pid_comparison=str(comparison / "result.json"),
                          changed={name: value for name, value in staged.items() if baseline.get(name) != value})
        mod.write_json(work / "candidate.json", {"files": staged, "token": token})
        toolroot = args.workbench_tools.resolve()
        job.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", ROOT / "tools/beryl-mod/engine-compile.ps1",
                 "-ToolRoot", toolroot, "-ProjectDir", candidate, "-ResultPath", work / "engine-compile.json", "-ExpectedVersion", "1.8.0.13"], "mesh_compile", work, 300)
        job.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", ROOT / "scripts/mesh-engine-run.ps1",
                 "-ToolRoot", toolroot, "-ProjectDir", candidate, "-ResultPath", work / "engine-tests.json", "-Token", token], "mesh_suites", work, 300)
        stdout = job.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", wrapper,
                          "-ProjectDir", candidate, "-KeepLog"], "mesh_host_acceptance", work, 240).decode("utf-8-sig")
        if "[BERYL-PID-HANDOVER] PASS " + token not in stdout:
            # Existing wrapper filters MESH lines; use its exact logged run directory.
            matches = re.findall(r"log=(logs_[^\s]+)", stdout)
            if len(set(matches)) != 1:
                raise RuntimeError("No unique host acceptance log identity")
            logroot = Path(os.environ["USERPROFILE"]) / "Documents/My Games/ArmaReforger/logs"
            rawlog = mod.read(logroot / matches[0] / "console.log")
            (work / "game-console.log").write_bytes(rawlog)
            console = rawlog.decode("utf-8", errors="replace")
        else:
            console = stdout
        if console.count("[BERYL-PID-HANDOVER] PASS " + token) != 1 or "[BERYL-PID-HANDOVER] FAIL" in console:
            raise RuntimeError("Actual takeover/release did not pass exactly once for the candidate")
        outcomes = re.findall(r"\[MESH-ACCEPT\]\s+(\S+)\s+(PASS|FAIL|SKIP)\b", console)
        expected = {"A0_no_autospawn", "A1_spawn", "A2_components", "A3_physics", "A4_rotors", "A5_hover", "A6_arsenal",
                    "A10_realbox", "A11_task_order", "A12_task_flown", "A7_interlock", "A13_arm_button", "A8_arming",
                    "A14_disarm", "A9_warhead", "A15_strike_safety", "A16_strike_order", "A17_strike_flown"}
        if len(outcomes) != len(expected) or {name for name, _ in outcomes} != expected or any(state != "PASS" for _, state in outcomes):
            raise RuntimeError("Existing host acceptance contains missing/duplicate/failed/skipped checks")
        if "[MESH-ACCEPT] DONE" not in console:
            raise RuntimeError("Host acceptance did not finish")
        for name, value in staged.items():
            if name != "resourceDatabase.rdb" and hash_file(candidate / name) != value:
                raise RuntimeError("Candidate source changed during verification: " + name)
        if inventory(source) != baseline:
            raise RuntimeError("Original MESH changed during verification; candidate is stale")
        job.result.update(status="success", host_checks=outcomes, handover="takeover and release reset all three controllers",
                          dedicated_two_clients="unverified")
        print("Passed MESH compilation, nine suites, 18 host acceptance checks and real handover", flush=True)
    except (Exception, KeyboardInterrupt) as exc:
        job.result.update(status=getattr(exc, "status", "failure"), failure=str(exc))
        raise
    finally:
        mod.write_json(work / "result.json", job.result)
        print("Evidence: " + str(work / "result.json"), flush=True)


if __name__ == "__main__":
    main()
