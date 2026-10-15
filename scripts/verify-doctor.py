#!/usr/bin/env python3
"""Verify doctor inventory and explicit native probes in isolated owned directories.

No Beryl source program, Python tool bundle or engine session is executed.
The positive native case and fault-injection helpers use the selected Clang.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parent.parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--beryl", required=True, type=Path)
    parser.add_argument("--clang", required=True, type=Path)
    args = parser.parse_args()
    beryl, clang = args.beryl.resolve(strict=True), args.clang.resolve(strict=True)
    work = Path(tempfile.mkdtemp(prefix="doctor & spaces-", dir=ROOT / "build"))
    inventory = work / "inventory"
    inventory.mkdir()
    inputs = [Path(__file__), ROOT / "src/driver/doctor.c", ROOT / "src/driver/doctor.h"]
    before = {str(path): sha(path) for path in inputs}
    evidence = {"schema_version": 1, "status": "running", "compiler_sha256": sha(beryl),
                "clang_sha256": sha(clang), "input_hashes": before, "commands": [], "checks": [],
                "engine_execution": "not_run", "Beryl_program_execution": "not_run"}
    print(f"Doctor artifacts: {work}", flush=True)
    env = os.environ.copy()
    for key in ("BERYL_CLANG", "BERYL_PYTHON", "BERYL_MOD_TOOL"):
        env.pop(key, None)
    env["PATH"] = str(clang.parent) + os.pathsep + env.get("PATH", "")

    def run(*arguments, expected=0, cwd=inventory, timeout=45):
        command = [str(beryl), "doctor", "--format", "json", *map(str, arguments)]
        proc = subprocess.run(command, cwd=cwd, env=env, capture_output=True,
                              text=True, encoding="utf-8", errors="strict", timeout=timeout)
        evidence["commands"].append({"argv": command, "exit_code": proc.returncode,
                                     "stdout": proc.stdout, "stderr": proc.stderr})
        assert proc.returncode == expected, evidence["commands"][-1]
        result = json.loads(proc.stdout)
        assert result["schema_version"] == 1 and result["operation"] == "doctor"
        assert result["engine_execution"] == "not_run" and result["measurements"] is None
        if result.get("evidence_path"):
            assert json.loads(Path(result["evidence_path"]).read_text()) == result
        return result

    def passed(name):
        evidence["checks"].append(name)
        print(f"passed {name}", flush=True)

    try:
        missing = work / "missing.exe"
        first = run("--clang", clang, "--python", missing)
        assert first["status"] == "success" and first["stage"] == "inventory"
        assert first["compiler_fingerprint"] == evidence["compiler_sha256"]
        assert first["inventory"]["native_compiler"]["sha256"] == evidence["clang_sha256"]
        assert first["inventory"]["python_optional"]["status"] == "unavailable"
        assert first["inventory"]["job_writability"] == "not_checked"
        assert first["probe"] is None and first["program_execution"] == "not_run"
        assert first["source_fingerprint"] is None and first["project"]["source_admission"] == "not_checked"
        assert not list(inventory.iterdir())
        assert run("--clang", missing, "--python", missing)["inventory"]["native_compiler"]["status"] == "unavailable"
        assert not list(inventory.iterdir())
        passed("default inventory is read-only and optional missing Python/native tools are explicit")

        tool_root = work / "fake tool bundle"
        tool_root.mkdir()
        (tool_root / "mod.py").write_text("raise RuntimeError('inventory must never execute the loader')\n")
        contents = {"mod.py": b"raise RuntimeError('never execute')\n", "process_job.py": b"# fixture\n",
                    "engine-compile.ps1": b"# never execute\n", "beryl.mod.v1.schema.json": b"{}\n"}
        hashes = {name: hashlib.sha256(data).hexdigest() for name, data in contents.items()}
        identity = hashlib.sha256(canonical(hashes)).hexdigest()
        bundle = tool_root / identity
        bundle.mkdir()
        for name, data in contents.items():
            (bundle / name).write_bytes(data)
        (bundle / "bundle.json").write_bytes(canonical(hashes))
        active = tool_root / "active.json"
        active.write_text(json.dumps({"bundle": identity}))
        result = run("--tool-dir", tool_root)
        tool = result["inventory"]["installed_mod_tool"]
        assert tool["status"] == "content_match" and tool["observed_bundle_sha256"] == identity
        assert tool["dispatch_execution"] == "not_run" and tool["loader_recognition"] == "not_checked"
        (bundle / "mod.py").write_text("# changed\n")
        assert run("--tool-dir", tool_root)["inventory"]["installed_mod_tool"]["status"] == "stale_input"
        (bundle / "mod.py").write_bytes(contents["mod.py"])
        active.write_text('{"bundle":"' + identity + '","bundle":"' + identity + '"}')
        assert run("--tool-dir", tool_root)["inventory"]["installed_mod_tool"]["status"] == "failure"
        active.write_text('{"bundle":"../escape"}')
        assert run("--tool-dir", tool_root)["inventory"]["installed_mod_tool"]["status"] == "failure"
        active.write_text(json.dumps({"bundle": identity}))
        (bundle / "bundle.json").write_text(json.dumps({**hashes, "../escape": "0" * 64}))
        assert run("--tool-dir", tool_root)["inventory"]["installed_mod_tool"]["status"] != "content_match"
        passed("bundle content fingerprints reject changed or malformed identity data without executing tools")


        # Match the installer's fixed historical/component/generation sets, not
        # an arbitrary map with the right number of members. Payload bytes are
        # deliberately inert and are never imported or executed by these cases.
        profile_files = (
            "mod.py", "process_job.py", "engine-compile.ps1", "beryl.mod.v1.schema.json",
            "scenarios.py", "map-cursor.c.in", "scenario-engine-run.ps1", "source_maps.py",
            "terrain_scenarios.py", "terrain-reference.c.txt", "terrain-reference.json",
            "terrain-adapter.c.in", "terrain-handler.c.in", "storage_scenarios.py",
            "array-storage.c.in", "canvas-retention.c.in", "terrain_measurements.py",
            "terrain-measurement.c.in", "terrain-adapter-v1.c.txt", "mcp_server.py",
            "beryl.analysis.v1.schema.json", "component_contracts.py",
            "tablet-component-contracts.v1.json", "beryl.mod.v2.schema.json",
            "component_generation.py",
        )
        profile_counts = (8, 13, 16, 19, 21, 24, 25)
        fault_names = ("missing-payload", "tampered-payload", "missing-member", "extra-member",
                       "unknown-member", "bad-member-hash", "duplicate-member",
                       "bad-active-identity", "wrong-bundle-identity")
        expected_cases = tuple(f"profile{count}.valid" for count in profile_counts) + tuple(
            f"profile{count}.{fault}" for count in (24, 25) for fault in fault_names)
        bundle_cases = []
        evidence["bundle_profile_cases"] = bundle_cases

        def profile_case(count, fault=None):
            label = f"profile{count}." + (fault or "valid")
            folder = work / ("inert bundle " + label)
            folder.mkdir()
            (folder / "mod.py").write_bytes(b"raise RuntimeError('doctor inventory must not execute this loader')\n")
            payloads = {name: ("inert doctor inventory " + name + "\n").encode("ascii")
                        for name in profile_files[:count]}
            manifest = {name: hashlib.sha256(data).hexdigest() for name, data in payloads.items()}
            identity = hashlib.sha256(canonical(manifest)).hexdigest()
            declared = "0" * 64 if fault == "wrong-bundle-identity" else identity
            staged = folder / declared
            staged.mkdir()
            for name, data in payloads.items():
                (staged / name).write_bytes(data)
            manifest_bytes = canonical(manifest)
            selected = "component_contracts.py" if count == 24 else "component_generation.py"
            expected_status = "content_match"
            if fault == "missing-payload":
                (staged / selected).unlink()
                expected_status = "stale_input"
            elif fault == "tampered-payload":
                (staged / selected).write_bytes(b"changed inert payload\n")
                expected_status = "stale_input"
            elif fault == "missing-member":
                # Removing an arbitrary required member from 25 must not be
                # mistaken for the legitimate complete 24-member profile.
                del manifest["component_contracts.py"]
                manifest_bytes = canonical(manifest)
                expected_status = "unavailable" if count == 24 else "failure"
            elif fault == "extra-member":
                manifest["unexpected.py"] = "1" * 64
                manifest_bytes = canonical(manifest)
                expected_status = "failure" if count == 24 else "unavailable"
            elif fault == "unknown-member":
                manifest["unexpected.py"] = manifest.pop(selected)
                manifest_bytes = canonical(manifest)
                expected_status = "failure"
            elif fault == "bad-member-hash":
                manifest[selected] = "z" * 64
                manifest_bytes = canonical(manifest)
                expected_status = "failure"
            elif fault == "duplicate-member":
                manifest_bytes = manifest_bytes[:-1] + b',' + canonical(selected) + b':' + canonical(manifest[selected]) + b'}'
                expected_status = "failure"
            elif fault == "bad-active-identity":
                expected_status = "failure"
            elif fault == "wrong-bundle-identity":
                expected_status = "stale_input"
            elif fault is not None:
                raise AssertionError("Unknown bundle fixture fault")
            (staged / "bundle.json").write_bytes(manifest_bytes)
            active_value = {"bundle": "g" * 64 if fault == "bad-active-identity" else declared}
            (folder / "active.json").write_bytes(canonical(active_value))
            before_files = {str(p.relative_to(folder)): sha(p) for p in folder.rglob("*") if p.is_file()}
            observed = run("--tool-dir", folder)["inventory"]["installed_mod_tool"]
            assert observed["status"] == expected_status, (label, observed)
            assert observed["dispatch_execution"] == "not_run" and observed["loader_recognition"] == "not_checked"
            if fault is None:
                assert observed["declared_bundle_sha256"] == observed["observed_bundle_sha256"] == identity
                assert {row["name"] for row in observed["files"]} == set(profile_files[:count])
                assert len(observed["files"]) == count
                assert all(row["expected_sha256"] == row["actual_sha256"] == manifest[row["name"]]
                           for row in observed["files"])
            assert before_files == {str(p.relative_to(folder)): sha(p) for p in folder.rglob("*") if p.is_file()}, label
            bundle_cases.append({"case_id": label, "expected_status": expected_status,
                                 "observed_status": observed["status"], "passed": True})

        for count in profile_counts:
            profile_case(count)
        for count in (24, 25):
            for fault in fault_names:
                profile_case(count, fault)
        assert tuple(case["case_id"] for case in bundle_cases) == expected_cases
        assert len(set(expected_cases)) == len(expected_cases) == 25
        assert not list(inventory.iterdir())
        passed("exact historical and 24/25-file bundle profiles reject missing, extra, tampered and malformed identities without execution")

        engine = work / "fake-engine.exe"
        engine.write_bytes(b"not the registered engine\n")
        mismatch = run("--engine-executable", engine)
        assert mismatch["inventory"]["binding_check_status"] == "stale_input"
        assert mismatch["inventory"]["binding_snapshot"]["applicability"]["engine"] == "mismatch"
        assert mismatch["inventory"]["binding_snapshot"]["verified_contract"]["status"] == "unavailable"
        absent = run("--api-root", work / "absent-api")
        assert absent["inventory"]["binding_check_status"] == "unavailable"
        unavailable = run("--probe", "enfusion-compile", expected=3)
        assert unavailable["status"] == "unavailable" and unavailable["probe"]["job"] is None
        assert not list(inventory.iterdir())
        passed("binding identity mismatches and unavailable Enfusion probes never launch an editor")

        bad_project = work / "bad project"
        bad_project.mkdir()
        (bad_project / "beryl.toml").write_text("[unknown]\nx = true\n")
        failure = run("--project", bad_project, expected=1)
        assert failure["stage"] == "manifest" and failure["diagnostics"]
        for extra in (("--unknown",), ("--probe", "unknown"), ("--job-root", work),
                      ("--timeout-ms", "1"), ("--probe", "native", "--timeout-ms", "0"),
                      ("--probe", "native", "--timeout-ms", "-1"),
                      ("--probe", "native", "--timeout-ms", "120001"),
                      ("--clang", clang, "--clang", missing)):
            failure = run(*extra, expected=1)
            assert failure["status"] == "failure" and failure["probe"] is None
        passed("manifest and argument errors remain structured and do not launch probes")

        absent_probe = run("--probe", "native", "--clang", missing, "--job-root", work / "absent jobs", expected=3)
        assert absent_probe["probe"]["job"] is None and not (work / "absent jobs").exists()
        blocked = work / "a file not a directory"
        blocked.write_text("preserve me\n")
        denied = run("--probe", "native", "--clang", clang, "--job-root", blocked, expected=2)
        assert denied["probe"]["stage"] == "job_directory" and denied["probe"]["tool_version"] is None
        assert blocked.read_text() == "preserve me\n"
        invalid = work / "invalid.exe"
        invalid.write_bytes(b"This cannot be an executable.\n")
        if os.name != "nt":
            invalid.chmod(0o700)
        startup = run("--probe", "native", "--clang", invalid, "--job-root", work / "startup", expected=2)
        assert startup["probe"]["tool_version"]["status"] == "startup_failure"
        assert startup["probe"]["compile"] is None and startup["probe"]["run"] is None
        passed("missing tools, failed job creation and denied/invalid launches cannot reuse a prior executable")

        helper_source = work / "helper.c"
        helper_source.write_text(r'''#include <stdio.h>
#include <string.h>
#ifdef _WIN32
#include <windows.h>
#else
#include <unistd.h>
#endif
int main(int argc, char **argv) {
    if (strstr(argv[0], "timeout") || strstr(argv[0], "cancel")) {
        puts("waiting"); fflush(stdout);
#ifdef _WIN32
        Sleep(10000);
#else
        sleep(10);
#endif
        return 0;
    }
    if (argc > 1 && !strcmp(argv[1], "--version")) { puts("doctor fault fixture"); return 0; }
    return strstr(argv[0], "exit") ? 31 : 0;
}
''')
        suffix = ".exe" if os.name == "nt" else ""
        helper = work / ("helper" + suffix)
        command = [str(clang), "-std=c11", "-O0", str(helper_source), "-o", str(helper)]
        compiled = subprocess.run(command, cwd=work, env=env, capture_output=True, text=True, timeout=45)
        evidence["commands"].append({"argv": command, "exit_code": compiled.returncode,
                                     "stdout": compiled.stdout, "stderr": compiled.stderr})
        assert compiled.returncode == 0
        helpers = {}
        for name in ("missing_output", "compile_exit", "timeout", "cancel"):
            helpers[name] = work / (name + suffix)
            shutil.copy2(helper, helpers[name])
        missing_output = run("--probe", "native", "--clang", helpers["missing_output"], "--job-root", work / "missing output", expected=1)
        assert missing_output["probe"]["compile"]["exit_code"] == 0
        assert missing_output["probe"]["artifact_sha256"] is None and missing_output["probe"]["run"] is None
        exited = run("--probe", "native", "--clang", helpers["compile_exit"], "--job-root", work / "compile exit", expected=1)
        assert exited["probe"]["compile"]["exit_code"] == 31 and exited["probe"]["run"] is None
        timed = run("--probe", "native", "--clang", helpers["timeout"], "--job-root", work / "timeout jobs", "--timeout-ms", "50", expected=2)
        assert timed["probe"]["status"] == "timeout" and timed["probe"]["tool_version"]["exit_code"] is None
        passed("zero-exit missing output, compiler failure and timeout have distinct unsuccessful outcomes")

        cancel_root = work / "cancel jobs"
        command = [str(beryl), "doctor", "--format", "json", "--probe", "native", "--clang", str(helpers["cancel"]),
                   "--job-root", str(cancel_root), "--timeout-ms", "30000"]
        flags = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {"start_new_session": True}
        proc = subprocess.Popen(command, cwd=inventory, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True, encoding="utf-8", **flags)
        try:
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                if proc.poll() is not None:
                    raise AssertionError("cancellation fixture exited before signal")
                logs = list(cancel_root.glob("*/version.stdout.log"))
                if any("waiting" in path.read_text(errors="replace") for path in logs):
                    break
                time.sleep(0.02)
            else:
                raise AssertionError("cancellation fixture did not reach the owned child")
            proc.send_signal(signal.CTRL_BREAK_EVENT if os.name == "nt" else signal.SIGINT)
            stdout, stderr = proc.communicate(timeout=10)
            evidence["commands"].append({"argv": command, "exit_code": proc.returncode,
                                         "stdout": stdout, "stderr": stderr, "external_cancellation": True})
            cancelled = json.loads(stdout)
            assert proc.returncode == 2 and cancelled["status"] == "cancelled"
            assert cancelled["probe"]["tool_version"]["status"] == "cancelled"
            assert cancelled["probe"]["compile"] is None and cancelled["probe"]["run"] is None
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait(timeout=10)
        passed("external cancellation is distinguished from timeout and source/program failure")

        positive = run("--probe", "native", "--clang", clang, "--python", missing,
                       "--job-root", work / "native & spaces ! jobs")
        p = positive["probe"]
        assert positive["status"] == "success" and p["status"] == "success"
        assert p["tool_before_sha256"] == p["tool_after_sha256"] == evidence["clang_sha256"]
        assert p["run"]["stdout"].replace("\r\n", "\n") == "BERYL_DOCTOR_NATIVE_V1\n"
        assert p["run"]["exit_code"] == 0 and p["run"]["stderr"] == ""
        assert sha(Path(p["run"]["argv"][0])) == p["artifact_sha256"]
        assert p["run"]["argv"][0] in p["compile"]["argv"]
        plan = json.loads((Path(p["job"]) / "plan.json").read_text())
        assert plan["steps"] == [p["tool_version"]["argv"], p["compile"]["argv"], p["run"]["argv"]]
        assert not list(inventory.iterdir())
        passed("explicit native probe preserves exact argv and executes only its freshly built artifact")

        assert before == {str(path): sha(path) for path in inputs}, "doctor sources changed during verification"
        evidence["status"] = "success"
    except Exception as error:
        evidence["status"] = "failure"
        evidence["error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        (work / "results.json").write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
