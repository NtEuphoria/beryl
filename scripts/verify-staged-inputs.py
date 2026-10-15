#!/usr/bin/env python3
"""Verify immutable mod-job inputs using inert bytes and simulated processes.

No compiler, native program, engine, installed loader or live installation runs.
The real Job snapshot/run guards are exercised; subprocess and job ownership are
mocked throughout. All fixture mutations stay inside a fresh build directory.
"""
from pathlib import Path
import copy
import hashlib
import json
import sys
import tempfile
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / "tools/beryl-mod"))
import mod
import process_job

SOURCE = b"""module fixture.staged
pub struct State { mode: i32 = 0, elapsed: f32 = 0 }
pub fn init(inout state: State) { state.mode = 0 }
pub fn frame(inout state: State, time_slice: f32) { state.elapsed += time_slice }
pub fn delete(inout state: State) { state.mode = 0 }
"""
STDOUT = b"inert simulated stdout\n"
STDERR = b"inert simulated stderr\n"
CASE_KINDS = (
    "normal-snapshot", "normal-simulated-run",
    "staged-source-tampered-before", "staged-source-missing-before",
    "staged-companion-tampered-before", "staged-companion-missing-before",
    "staged-source-tampered-after", "staged-source-missing-after",
    "staged-companion-tampered-after", "staged-companion-missing-after",
    "project-source-tampered-before", "project-companion-tampered-before",
    "project-source-tampered-after", "project-companion-tampered-after",
    "frozen-hashes-entry-dropped-before", "frozen-hashes-consistently-replaced-before",
    "snapshot-source-short-write", "snapshot-companion-short-write",
    "snapshot-source-full-count-wrong-bytes", "snapshot-companion-full-count-wrong-bytes",
    "build-emitter-source-map-mismatch",
)
EXPECTED_CASES = tuple(f"v{version}.{kind}" for version in (1, 2) for kind in CASE_KINDS)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def ensure(condition, message):
    if not condition:
        raise AssertionError(message)


def write(path, data):
    ensure(path.write_bytes(data) == len(data), "verifier fixture/evidence write was incomplete")
    ensure(path.read_bytes() == data, "verifier fixture/evidence bytes differ after writing")


def receipt(path, value):
    write(path, (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode())


def config(version):
    value = {
        "schema_version": version, "name": "Inert staged-input identity fixture",
        "addon": {"id": "Beryl_StagedInputFixture", "guid": "1234567890ABCDEF", "dependencies": []},
        "binding": {"target": "enfusion", "version": "1.8.0.13"},
        "sources": {"native": ["src/state.be"], "enfusion": ["src/state.be"], "tests": []},
        "exports": [],
    }
    if version == 2:
        value["binding"].update(
            sha256="7dd36ca1f662b0c13669a4f2f7f10e3c461c2906b021e742272d64b3ab7e9798",
            contract_profile="enfusion.tablet.script-component.v1")
        value["components"] = [{
            "descriptor": {"name": "SPK_StagedFixtureClass", "parent": "ScriptComponentClass"},
            "instance": {"name": "SPK_StagedFixture", "parent": "ScriptComponent"},
            "state": "fixture.staged.State", "callbacks": [
                {"binding": "ScriptComponent.OnPostInit", "handler": "fixture.staged.init", "super_order": "first"},
                {"binding": "ScriptComponent.EOnFrame", "handler": "fixture.staged.frame", "super_order": "none"},
                {"binding": "ScriptComponent.OnDelete", "handler": "fixture.staged.delete", "super_order": "last"},
            ],
        }]
    return value


def expect_failure(action, statuses):
    try:
        action()
    except mod.Failure as exc:
        ensure(exc.status in statuses, f"unexpected failure status {exc.status}: {exc}")
        return {"status": exc.status, "message": str(exc), "pointer": exc.pointer}
    raise AssertionError("required input-identity failure did not occur")


def simulated_run(job, cwd, mutation=None):
    """Exercise Job.run log and before/after checks without creating a process."""
    calls = {"popen": 0, "attach": 0, "wait": 0, "ownership_exit": 0}

    class SimulatedProcess:
        pid = 12345  # Fixture identity only; no process is started or signalled.
        def __init__(self, argv, **options):
            calls["popen"] += 1
            ensure(options["cwd"] == cwd, "simulated cwd differs")
            ensure(options["stdin"] == mod.subprocess.DEVNULL, "unexpected simulated stdin")
            options["stdout"].write(STDOUT)
            options["stderr"].write(STDERR)
            self.returncode = None

        def wait(self, timeout):
            calls["wait"] += 1
            ensure(timeout == 2, "unexpected simulated timeout")
            if mutation is not None:
                mutation()
            self.returncode = 0
            return 0

    class SimulatedOwner:
        flags = 0

        def __enter__(self):
            self.cleanup_errors = []
            return self

        def attach(self, process):
            ensure(isinstance(process, SimulatedProcess), "unexpected owned process")
            calls["attach"] += 1

        def __exit__(self, *args):
            calls["ownership_exit"] += 1

    with mock.patch.object(mod.subprocess, "Popen", SimulatedProcess), \
            mock.patch.object(process_job, "ProcessJob", SimulatedOwner):
        try:
            output = job.run([str(job.compiler), "never-executed"], "simulated", cwd, timeout=2)
            outcome = {"status": "success", "output_sha256": sha(output)}
            ensure(output == STDOUT, "simulated stdout was not read back accurately")
        except mod.Failure as exc:
            outcome = {"status": exc.status, "message": str(exc), "pointer": exc.pointer}
    ensure(calls == {"popen": 1, "attach": 1, "wait": 1, "ownership_exit": 1},
           "simulated execution or owned cleanup did not complete exactly once")
    ensure(len(job.result["raw_logs"]) == 1, "simulated execution log is missing or duplicated")
    log = job.result["raw_logs"][0]
    ensure(log["status"] == "exited" and log["exit_code"] == 0,
           "simulated process execution outcome must remain distinct from stale-input rejection")
    outcome["simulated_process_calls"] = calls
    outcome["raw_logs"] = {key: {"path": log[key], "sha256": sha(Path(log[key]).read_bytes())}
                           for key in ("stdout", "stderr")}
    ensure(outcome["raw_logs"]["stdout"]["sha256"] == sha(STDOUT), "stdout log differs")
    ensure(outcome["raw_logs"]["stderr"]["sha256"] == sha(STDERR), "stderr log differs")
    return outcome


def main():
    ensure(len(set(EXPECTED_CASES)) == len(EXPECTED_CASES), "duplicate registered case")
    work = Path(tempfile.mkdtemp(prefix="staged inputs & spaces-", dir=ROOT / "build"))
    compiler = work / "inert-compiler.bin"
    write(compiler, b"Beryl verifier inert bytes; not an executable and never launched.\n")
    tracked = [Path(__file__).resolve(), *mod.bundle_paths(), Path(process_job.__file__).resolve()]
    tracked = list(dict.fromkeys(path.resolve() for path in tracked))
    identities = {str(path): sha(path.read_bytes()) for path in tracked}
    record = {
        "schema_version": 1, "operation": "verify.staged_inputs", "status": "running",
        "expected_case_ids": list(EXPECTED_CASES), "cases": [], "verification_inputs": identities,
        "tool_identity": mod.tool_identity(), "inert_compiler": {"path": str(compiler), "sha256": sha(compiler.read_bytes())},
        "python": {"path": sys.executable, "sha256": sha(Path(sys.executable).read_bytes()), "version": sys.version},
        "scope": {"job_snapshot": "actual", "job_run_identity_guards": "actual",
                  "subprocess_and_process_ownership": "simulated", "compiler_execution": "not_run",
                  "native_execution": "not_run", "engine_execution": "not_run", "live_installation": "unchanged"},
        "limitation": "Checks staged-byte identity and checked writes; simulated execution establishes no compiler, engine, component or gameplay behavior.",
    }
    result_path = work / "results.json"
    print("Staged-input evidence: " + str(work), flush=True)
    for path in tracked:
        retained = work / "verification-inputs" / path.relative_to(ROOT)
        retained.parent.mkdir(parents=True, exist_ok=True)
        write(retained, path.read_bytes())

    def test(version, kind):
        case_id = f"v{version}.{kind}"
        project = work / case_id
        (project / "src").mkdir(parents=True)
        original = {"beryl.mod.json": mod.canonical(config(version)), "src/state.be": SOURCE}
        hashes = {name: sha(data) for name, data in original.items()}
        for name, data in original.items():
            write(project / name, data)
            retained = work / "original-inputs" / case_id / name
            retained.parent.mkdir(parents=True, exist_ok=True)
            write(retained, data)
        job = mod.Job(project, "check", compiler)
        ensure(job.input_hashes is None and job.staged_inputs is None, "new job has a prematurely frozen snapshot")
        entry = {"id": case_id, "companion_version": version, "expected_input_hashes": hashes,
                 "expected_aggregate_sha256": sha(mod.canonical(hashes)), "job_path": str(job.path),
                 "source_scope": "isolated fixture project and its own staged copies"}
        if kind.startswith("snapshot-"):
            name = "beryl.mod.json" if "companion" in kind else "src/state.be"
            target = job.path / "inputs" / name
            real_write = Path.write_bytes
            faults = []

            def faulty_write(path, data):
                if path == target:
                    faults.append(str(path))
                    real_write(path, data[:-1])
                    return len(data) - 1 if kind.endswith("short-write") else len(data)
                return real_write(path, data)

            with mock.patch.object(Path, "write_bytes", faulty_write):
                entry["outcome"] = expect_failure(job.snapshot, {"failure"})
            ensure(faults == [str(target)], "snapshot write injection did not occur exactly once")
            ensure(job.input_hashes is None and job.staged_inputs is None and job.result["source_sha256"] is None,
                   "incomplete writes published a frozen successful input identity")
            entry["injected_write"] = {"path": str(target), "retained_sha256": sha(target.read_bytes()),
                                       "expected_sha256": hashes[name], "kind": kind}
        else:
            selected, inputs, frozen = job.snapshot()
            ensure(selected == config(version), "snapshot companion differs")
            ensure(frozen == hashes and job.input_hashes == hashes and job.input_hashes is not frozen,
                   "snapshot did not retain an independent exact frozen hash mapping")
            ensure(job.staged_inputs == inputs and inputs == job.path / "inputs", "snapshot staged path differs")
            ensure(job.result["source_sha256"] == entry["expected_aggregate_sha256"], "snapshot aggregate differs")
            entry["staged_initial_hashes"] = {name: sha((inputs / name).read_bytes()) for name in hashes}
            ensure(entry["staged_initial_hashes"] == hashes, "staged copy differs before fault injection")
            job.unchanged(frozen)
            if kind == "normal-snapshot":
                entry["outcome"] = {"status": "success", "unchanged_checks": 1}
            elif kind == "normal-simulated-run":
                entry["outcome"] = simulated_run(job, inputs)
                ensure(entry["outcome"]["status"] == "success", "unchanged simulated run was rejected")
            elif kind == "build-emitter-source-map-mismatch":
                import component_generation
                emitted = b"// Inert simulated generation; never compiled.\nclass FixtureStaleBytes {}\n"
                changed = original["src/state.be"] + b"// bytes observed by simulated emitter only\n"
                mapping = {"schema_version": 1, "operation": "source_map", "target": "enfusion",
                           "column_unit": "byte", "mapping_precision": "inert identity fixture",
                           "sources": [{"path": "src/state.be", "sha256": sha(changed)}],
                           "generated": {"file": "Beryl_Generated.c", "bytes": len(emitted), "sha256": sha(emitted)},
                           "exports": [], "mappings": [], "linkage_schema_version": 1, "linkage": []}

                def fake_generation(argv, stage, cwd, timeout=120):
                    ensure(stage == "generation" and cwd == inputs and argv[1] == "build",
                           "mismatch fixture reached an unexpected compiler/context operation")
                    output = Path(argv[argv.index("--out-dir") + 1]) / "Beryl_Generated.c"
                    source_map = Path(argv[argv.index("--source-map") + 1])
                    ensure(output.is_relative_to(job.path) and source_map == job.path / "source-map.json",
                           "simulated generation escaped its isolated job")
                    # Model change-and-restore while the emitter reads. Ordinary
                    # pre/post filesystem comparisons then see the original bytes.
                    write(inputs / "src/state.be", changed)
                    try:
                        write(output, emitted)
                        receipt(source_map, mapping)
                    finally:
                        write(inputs / "src/state.be", original["src/state.be"])
                    return b""

                with mock.patch.object(job, "run", side_effect=fake_generation) as generation, \
                        mock.patch.object(mod, "component_admission", side_effect=AssertionError("stale map reached component admission")) as admission, \
                        mock.patch.object(component_generation, "generate", side_effect=AssertionError("stale map reached component generation")) as wrappers:
                    entry["outcome"] = expect_failure(lambda: mod.build(job, selected, inputs, frozen), {"stale_input"})
                    ensure(entry["outcome"]["pointer"] == "/sources/enfusion",
                           "emitter identity mismatch did not report the precise source pointer")
                    ensure(generation.call_count == 1 and admission.call_count == 0 and wrappers.call_count == 0,
                           "stale emitter evidence reached context/admission/wrapper work")
                job.unchanged(frozen)
                ensure(not (project / ".beryl-mod/artifacts").exists(), "stale emitter evidence published an artifact")
                ensure("component_generation" not in job.result and job.result["raw_logs"] == [],
                       "simulated mismatch acquired component/real execution evidence")
                entry["outcome"].update(generation_calls=1, component_admission_calls=0,
                                         component_generation_calls=0, artifact_publication="not_run",
                                         original_and_staged_bytes_restored=True)
                entry["simulated_emitter_evidence"] = {
                    "source_map": {"path": str(job.path / "source-map.json"),
                                   "sha256": sha((job.path / "source-map.json").read_bytes())},
                    "reported_source_sha256": sha(changed), "frozen_source_sha256": frozen["src/state.be"],
                    "generated_sha256": sha(emitted), "compiler_execution": "not_run"}
            else:
                name = "beryl.mod.json" if "companion" in kind else "src/state.be"
                target = (project if kind.startswith("project-") else inputs) / name

                def mutation():
                    if kind == "frozen-hashes-entry-dropped-before":
                        del job.input_hashes["src/state.be"]
                    elif kind == "frozen-hashes-consistently-replaced-before":
                        changed = original["src/state.be"] + b"// consistent but unverified replacement\n"
                        write(project / "src/state.be", changed)
                        write(inputs / "src/state.be", changed)
                        job.input_hashes["src/state.be"] = sha(changed)
                    elif "missing" in kind:
                        ensure(target.is_relative_to(work), "fault deletion escaped the isolated fixture")
                        target.unlink()
                    else:
                        write(target, target.read_bytes() + b"\n// deliberate staged/source mutation\n")

                if kind.endswith("-after"):
                    entry["outcome"] = simulated_run(job, inputs, mutation)
                    ensure(entry["outcome"]["status"] == "stale_input", "post-run stale bytes were accepted")
                else:
                    mutation()
                    with mock.patch.object(mod.subprocess, "Popen", side_effect=AssertionError("stale snapshot reached Popen")) as launch:
                        entry["outcome"] = expect_failure(
                            lambda: job.run([str(compiler), "never-executed"], "forbidden", inputs), {"stale_input"})
                        ensure(launch.call_count == 0, "process creation was attempted for a stale snapshot")
                    ensure(job.result["raw_logs"] == [], "stale pre-run input reached execution/logging")
                    entry["outcome"]["popen_calls"] = 0
        ensure(job.result["artifact_sha256"] is None and job.result["measurements"] == [],
               "input fixtures produced an artifact identity or measurements")
        entry["status"] = "success"
        entry["job_result"] = copy.deepcopy(job.result)
        return entry

    try:
        # This outer sentinel also covers snapshot-only cases. Only the explicit
        # simulated-run helper temporarily replaces it with an inert Python object.
        with mock.patch.object(mod.subprocess, "Popen", side_effect=AssertionError("real subprocess creation is forbidden")):
            for version in (1, 2):
                for kind in CASE_KINDS:
                    entry = test(version, kind)
                    record["cases"].append(entry)
                    receipt(result_path, record)
                    print("passed " + entry["id"], flush=True)
        completed = [entry["id"] for entry in record["cases"]]
        ensure(completed == list(EXPECTED_CASES) and len(set(completed)) == len(EXPECTED_CASES),
               "missing, duplicate, extra or out-of-order completed case")
        ensure(all(sha(Path(path).read_bytes()) == value for path, value in identities.items()),
               "verification implementation inputs changed during the run")
        ensure(mod.tool_identity() == record["tool_identity"], "tool identity changed during the run")
        ensure(sha(compiler.read_bytes()) == record["inert_compiler"]["sha256"], "inert compiler bytes changed")
        record.update(status="success", complete_expected_case_set=True, completed_cases=len(completed))
    except BaseException as exc:
        record.update(status="failure", complete_expected_case_set=False,
                      error={"type": type(exc).__name__, "message": str(exc)})
        receipt(result_path, record)
        raise
    receipt(result_path, record)
    print("passed " + str(len(EXPECTED_CASES)) + "/" + str(len(EXPECTED_CASES)) +
          "; receipt sha256 " + sha(result_path.read_bytes()), flush=True)


if __name__ == "__main__":
    main()
