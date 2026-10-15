#!/usr/bin/env python3
"""Independent Python-only admission tests for the fixed tablet suite source profile.

This runner never invokes a compiler, PowerShell, engine, suite or process signal.
It copies the declared reviewed assets once into owned fixtures, then exercises
the real resource and profile validators. Source preservation is not native
registration, binary dependency closure, gameplay or visual evidence.
"""
from pathlib import Path
import argparse
import copy
import hashlib
import importlib.util
import json
import os
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "scripts/verify-tablet-service-candidate.py"
MANIFEST = ROOT / "packages/sparkos/tablet-service-prototype/tablet-suites.v1.json"
COMPANION = MANIFEST.parent / "beryl.mod.json"
DEFAULT_MESH = Path("C:/Users/moham/Documents/My Games/ArmaReforgerWorkbench/addons/SparkOS_Mesh")
sys.dont_write_bytecode = True


def identity(path):
    raw = Path(path).read_bytes()
    return {"path": str(path), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def save(path, value):
    raw = (json.dumps(value, indent=2, ensure_ascii=True) + "\n").encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        if stream.write(raw) != len(raw):
            raise OSError("Short inert receipt write")
    if path.read_bytes() != raw:
        raise OSError("Inert receipt readback differs")


def put(value, path, replacement):
    for key in path[:-1]:
        value = value[key]
    value[path[-1]] = copy.deepcopy(replacement)


def drop(value, path):
    for key in path[:-1]:
        value = value[key]
    value.pop(path[-1])


def compile_fixture():
    return {"schema_version": 1, "status": "success", "stage": "workbench_compile",
            "result": {"Ok": True, "Stage": "Compiled", "ExitCode": 0, "ErrorCount": 0}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mesh-project", type=Path, default=DEFAULT_MESH,
                        help="Read-only source of the exact reviewed assets; copies are owned fixtures")
    args = parser.parse_args()
    work = Path(tempfile.mkdtemp(prefix="tablet-suite-admission-inert-", dir=ROOT / "build"))
    spec = importlib.util.spec_from_file_location("tablet_suite_admission_target", TARGET)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    raw_manifest = MANIFEST.read_bytes()
    baseline = json.loads(raw_manifest)
    companion = COMPANION.read_bytes()
    cases = []

    def register(name, action, expected):
        cases.append((name, action, expected))

    def profile_case(name, mutate=None, accepted=False):
        def action():
            value = copy.deepcopy(baseline)
            if mutate:
                mutate(value)
            before = copy.deepcopy(value)
            try:
                result = module.validate_suite_profile(value)
                return {"accepted": True, "input_unchanged": value == before,
                        "returned_input": result is value}
            except module.mod.Failure as exc:
                return {"accepted": False, "input_unchanged": value == before,
                        "rejection": {"status": exc.status, "type": type(exc).__name__, "message": str(exc)}}
        register("profile." + name, action, {"accepted": accepted, "input_unchanged": True})

    profile_case("exact-installed", accepted=True)
    register("profile.raw-installed-identity", lambda: {
        "matches": module.tablet_suite_profile() == baseline,
        "raw_hash_matches": identity(MANIFEST)["sha256"] == module.SUITE_MANIFEST_SHA},
        {"matches": True, "raw_hash_matches": True})
    for key in baseline:
        profile_case("missing." + key, lambda value, k=key: value.pop(k))
    profile_case("unknown-top-key", lambda value: value.update(shell_command="must not execute"))
    for label, replacement in (("bool", True), ("float", 1.0), ("zero", 0), ("version2", 2), ("string", "1")):
        profile_case("schema." + label, lambda value, r=replacement: value.update(schema_version=r))
    profile_case("unknown-profile", lambda value: value.update(profile="sparkos.tablet.other.v1"))
    resource = "Prefabs/SPK_Tablet.et"
    sidecar = resource + ".meta"
    for label, replacement in (("bool-size", True), ("negative-size", -1), ("oversize", 8388609),
                               ("float-size", 593.0), ("wrong-size", 594)):
        profile_case("resource." + label, lambda value, r=replacement: put(value, ("resources", resource, "bytes"), r))
    for label, replacement in (("bool-hash", True), ("wrong-hash", "0" * 64), ("upper-hash", "A" * 64),
                               ("short-hash", "a" * 63), ("null-hash", None)):
        profile_case("resource." + label, lambda value, r=replacement: put(value, ("resources", resource, "sha256"), r))
    profile_case("resource.missing-sidecar", lambda value: value["resources"].pop(sidecar))
    profile_case("resource.partial-closure", lambda value: value["resources"].pop("Prefabs/SPK_BoltM_Item.et"))
    profile_case("resource.extra-flying", lambda value: value["resources"].update({"Prefabs/SPK_BoltM.et": value["resources"][resource]}))
    profile_case("resource.extra-field", lambda value: value["resources"][resource].update(code="ignored?"))
    def rename_resource(value, name):
        value["resources"][name] = value["resources"].pop(resource)
    for label, name in (("parent", "Prefabs/../outside.et"), ("backslash", "Prefabs\\SPK_Tablet.et"),
                        ("absolute", "/Prefabs/SPK_Tablet.et"), ("colon", "Prefabs/C:tablet.et"),
                        ("other-root", "scripts/Game/tablet.et"), ("case-change", "Prefabs/spk_tablet.et")):
        profile_case("resource.path." + label, lambda value, n=name: rename_resource(value, n))
    for field, replacement in (("guid", "0000000000000000"), ("guid", True), ("resource", "{0000000000000000}" + resource),
                               ("sidecar", "Prefabs/other.et.meta"), ("line", True), ("line", 3)):
        profile_case("registration." + field + "." + repr(replacement),
                     lambda value, f=field, r=replacement: put(value, ("resource_registrations", resource, f), r))
    profile_case("registration.missing", lambda value: value["resource_registrations"].pop(resource))
    profile_case("registration.unknown-field", lambda value: value["resource_registrations"][resource].update(imported=True))
    def duplicate_registration(value):
        other = "Prefabs/SPK_MeshCoreEntity.et"
        guid = value["resource_registrations"][resource]["guid"]
        value["resource_registrations"][other].update(guid=guid, resource="{" + guid + "}" + other)
    profile_case("registration.guid-collision", duplicate_registration)
    for name, action in (("missing", lambda v: v["external_base_references_unresolved"].pop()),
                         ("duplicate", lambda v: v["external_base_references_unresolved"].__setitem__(0, v["external_base_references_unresolved"][1])),
                         ("bool-element", lambda v: v["external_base_references_unresolved"].__setitem__(0, True)),
                         ("unknown-resource", lambda v: v["external_base_references_unresolved"].__setitem__(0, "{0000000000000000}Configs/other.conf")),
                         ("reorder", lambda v: v["external_base_references_unresolved"].reverse())):
        profile_case("base-reference." + name, action)
    for index, row in enumerate(baseline["suite_selections"]):
        profile_case("suite.missing." + row["suite"], lambda value, i=index: value["suite_selections"].pop(i))
        profile_case("suite.bool-name." + row["suite"], lambda value, i=index: value["suite_selections"][i].update(suite=True))
        profile_case("suite.wrong-arg." + row["suite"], lambda value, i=index: value["suite_selections"][i].update(arg="{0000000000000000}Prefabs/Other.et"))
    profile_case("suite.duplicate", lambda value: value["suite_selections"].__setitem__(1, value["suite_selections"][0]))
    profile_case("suite.reordered", lambda value: value["suite_selections"].reverse())
    profile_case("suite.extra", lambda value: value["suite_selections"].append({"suite": "flight", "arg": ""}))
    profile_case("suite.embedded-command", lambda value: value["suite_selections"][0].update(command="must not execute"))
    profile_case("suite.boolean-success", lambda value: value["suite_response_contract"].update(successful_ok=True))
    profile_case("suite.noninteger-success", lambda value: value["suite_response_contract"].update(successful_ok=1.0))
    profile_case("suite.loosened-response", lambda value: value["suite_response_contract"].update(fields=["ok"]))
    for handler in baseline["workbench_handlers"]:
        name = Path(handler).name
        profile_case("handler.missing." + name, lambda value, h=handler: value["workbench_handlers"].pop(h))
        profile_case("handler.changed." + name, lambda value, h=handler: value["workbench_handlers"][h].update(sha256="0" * 64))
    for label, path, replacement in (
        ("addon.live-id", ("addon", "id"), "SparkOSMesh"),
        ("addon.live-guid", ("addon", "guid"), "4008B09320C27BA6"),
        ("addon.extra-dependency", ("addon", "dependencies"), ["58D0FB3206B6F859", "4008B09320C27BA6"]),
        ("limits.excess-resources", ("limits", "resource_files"), 40),
        ("limits.bool-resource-count", ("limits", "resource_files"), True),
        ("limits.changed-stage-count", ("limits", "candidate_files"), 84),
        ("provenance.changed", ("source_provenance", "plan_sha256"), "0" * 64),
        ("provenance.false-runtime", ("source_provenance", "meaning"), "runtime verified"),
        ("limitations.omitted", ("limitations",), [])):
        profile_case(label, lambda value, p=path, r=replacement: put(value, p, r))

    def companion_positive(selected):
        before = copy.deepcopy(baseline)
        result = module.candidate_companion(companion, selected, baseline)
        original = module.mod.parse(companion)
        transformed = module.mod.parse(result)
        if selected == "source-only":
            return {"exact_bytes": result == companion, "profile_unchanged": baseline == before}
        unchanged_keys = {key: item for key, item in original.items() if key not in ("addon", "name")}
        actual_keys = {key: item for key, item in transformed.items() if key not in ("addon", "name")}
        return {"fixed_addon": transformed["addon"] == baseline["addon"], "other_fields_unchanged": actual_keys == unchanged_keys,
                "deterministic": result == module.candidate_companion(companion, selected, baseline),
                "profile_unchanged": baseline == before, "distinct_from_live": transformed["addon"]["id"] != "SparkOSMesh"}
    register("companion.default-exact-original", lambda: companion_positive("source-only"), {"exact_bytes": True, "profile_unchanged": True})
    register("companion.selected-isolated-identity", lambda: companion_positive("tablet-suites-v1"),
             {"fixed_addon": True, "other_fields_unchanged": True, "deterministic": True, "profile_unchanged": True, "distinct_from_live": True})
    for name, selection, value in (("unknown", "other", baseline), ("bool", True, baseline),
                                    ("selected-missing-profile", "tablet-suites-v1", None)):
        register("companion.reject." + name, lambda s=selection, v=value: module.candidate_companion(companion, s, v), {"rejected": True})
    register("companion.selected-scalar-not-object", lambda: module.candidate_companion(b"null", "tablet-suites-v1", baseline), {"rejected": True})

    def compile_case(name, mutation=None, success=False, target="not_run", scope="not_run"):
        def action():
            value = compile_fixture()
            if mutation:
                mutation(value)
            before = copy.deepcopy(value)
            admitted = module.compile_success(value)
            record = {"attempts": {"engine_compile": {"requested": True, "adapter_invocation_attempted": True,
                       "process_outcome": "not_run", "adapter_status": "not_run", "target_outcome": "not_run"}},
                      "commands": [], "raw_results": {"compile": {"result": value}}, "scope": {"engine_compilation": "not_run"}}
            module.classify_compile_attempt(record)
            return {"admitted": admitted, "raw_unchanged": value == before,
                    "target_outcome": record["attempts"]["engine_compile"]["target_outcome"],
                    "scope": record["scope"]["engine_compilation"]}
        register("compile." + name, action, {"admitted": success, "raw_unchanged": True, "target_outcome": target, "scope": scope})
    compile_case("exact-success", success=True, target="executed_success", scope="executed_success")
    compile_case("warnings-not-errors", lambda v: v["result"].update(WarningCount=3), True, "executed_success", "executed_success")
    for label, path, replacement in (("bool-schema", ("schema_version",), True), ("float-schema", ("schema_version",), 1.0),
        ("wrong-schema", ("schema_version",), 2), ("wrong-stage", ("stage",), "source_build"),
        ("null-inner", ("result",), None), ("scalar-inner", ("result",), "compiled"),
        ("bool-exit", ("result", "ExitCode"), False), ("float-exit", ("result", "ExitCode"), 0.0),
        ("int-ok", ("result", "Ok"), 1), ("missing-result-stage", ("result", "Stage"), "other")):
        compile_case(label, lambda v, p=path, r=replacement: put(v, p, r))
    for label, path, replacement in (("outer-failure", ("status",), "failure"), ("outer-unavailable", ("status",), "unavailable"),
        ("outer-timeout", ("status",), "timeout"), ("outer-stale", ("status",), "stale_input"),
        ("false-ok", ("result", "Ok"), False), ("exit1", ("result", "ExitCode"), 1),
        ("errors1", ("result", "ErrorCount"), 1), ("bool-errors", ("result", "ErrorCount"), False),
        ("float-errors", ("result", "ErrorCount"), 0.0)):
        compile_case(label, lambda v, p=path, r=replacement: put(v, p, r), target="executed_failure", scope="executed_failure")
    compile_case("missing-schema", lambda v: v.pop("schema_version"))
    compile_case("missing-error-count", lambda v: v["result"].pop("ErrorCount"), target="executed_failure", scope="executed_failure")
    compile_case("no-associated-log-unavailable", lambda v: (v.update(status="unavailable"), v["result"].update(Stage="DidNotStart", Ok=False, ExitCode=-1)),
                 target="startup_unavailable", scope="attempted_unconfirmed")
    compile_case("target-timeout-incomplete", lambda v: (v.update(status="timeout"), v["result"].update(Stage="Timeout", Ok=False, ExitCode=-1)),
                 target="timeout_incomplete", scope="attempted_incomplete")

    state = {}
    def physical_setup():
        profile = module.tablet_suite_profile()
        helper = module.resource_helper()
        source, retained = work / "physical/source", work / "physical/retained"
        source.mkdir(parents=True)
        original = {}
        for name, item in sorted(profile["resources"].items()):
            raw, item_identity, signature = helper.read_checked(args.mesh_project / name, (item["bytes"], item["sha256"]))
            helper.checked_write(source / name, raw, source)
            original[name] = {"identity": item_identity, "signature": signature}
        snapshot, receipt = module.capture_suite_resources(source, retained, profile)
        state.update(source=source, retained=retained, profile=profile, snapshot=snapshot, original=original)
        return {"files": receipt["selected_file_count"], "bytes": receipt["selected_bytes"],
                "registration_count": len(receipt["resource_registrations"]), "unresolved": len(receipt["external_base_references_unresolved"]),
                "scope": receipt["scope"], "native_registration": receipt["native_registration"],
                "binary_dependency_closure": receipt["binary_dependency_closure"], "target_resource_availability": receipt["target_resource_availability"]}
    register("physical.capture-exact28-once", physical_setup,
             {"files": 28, "bytes": 12655544, "registration_count": 13, "unresolved": 18,
              "scope": "source and sidecar preservation only", "native_registration": "not_run",
              "binary_dependency_closure": "unverified", "target_resource_availability": "unverified"})

    def physical_mutation(name, mutate):
        def action():
            if not state:
                raise RuntimeError("Physical prerequisite unavailable; no descendant case executed")
            path = state["source"] / name
            before = path.read_bytes()
            times = path.stat()
            cleanup = None
            try:
                mutate(path, before)
                try:
                    module.verify_suite_resources(state["snapshot"])
                    return {"rejected": False}
                except Exception as exc:
                    if type(exc).__name__ == "PreparationFailure" and type(exc).__module__ == "tablet_suite_resource_helpers":
                        return {"rejected": True, "status": exc.status, "message": str(exc)}
                    if isinstance(exc, module.mod.Failure):
                        return {"rejected": True, "status": exc.status, "message": str(exc)}
                    raise
            finally:
                if not path.exists():
                    path.write_bytes(before)
                    # A deletion changes file identity; refresh only the fixture's
                    # reference after checking the exact immutable bytes again.
                    helper = module.resource_helper()
                    _, _, signature = helper.read_checked(path, (len(before), hashlib.sha256(before).hexdigest()))
                    state["snapshot"]["signatures"][name] = signature
                else:
                    path.write_bytes(before)
                    os.utime(path, ns=(times.st_atime_ns, times.st_mtime_ns))
        return action
    register("physical.source-changed-asset", physical_mutation("Assets/Bolt/Data/MAT_SK_body.emat", lambda p, raw: p.write_bytes(raw + b"changed")),
             {"rejected": True, "status": "stale_input"})
    register("physical.source-changed-sidecar", physical_mutation("Prefabs/SPK_Tablet.et.meta", lambda p, raw: p.write_bytes(raw.replace(b"B37EEB64E149CBAD", b"0000000000000000"))),
             {"rejected": True, "status": "stale_input"})
    register("physical.source-missing-sidecar", physical_mutation("Prefabs/SPK_Tablet.et.meta", lambda p, raw: p.unlink()),
             {"rejected": True, "status": "unavailable"})
    register("physical.source-same-bytes-different-mtime", physical_mutation("Prefabs/SPK_MeshCoreEntity.et", lambda p, raw: os.utime(p, ns=(p.stat().st_atime_ns, p.stat().st_mtime_ns + 1000000000))),
             {"rejected": True, "status": "stale_input"})

    def retained_mutation(name, remove=False):
        def action():
            if not state:
                raise RuntimeError("Physical prerequisite unavailable")
            path = state["retained"] / name
            raw = path.read_bytes()
            try:
                path.unlink() if remove else path.write_bytes(raw + b"corrupt")
                module.verify_suite_resources(state["snapshot"])
                return {"rejected": False}
            except Exception as exc:
                if type(exc).__name__ == "PreparationFailure" and type(exc).__module__ == "tablet_suite_resource_helpers":
                    return {"rejected": True, "status": exc.status, "message": str(exc)}
                raise
            finally:
                path.write_bytes(raw)
        return action
    register("physical.retained-changed-asset", retained_mutation("Assets/Bolt/Data/MAT_SK_body.emat"), {"rejected": True, "status": "stale_input"})
    register("physical.retained-missing-sidecar", retained_mutation("Configs/SPK_MeshArsenal.conf.meta", True), {"rejected": True, "status": "unavailable"})

    def extra_fixture(name, expected_guard):
        def action():
            if not state:
                raise RuntimeError("Physical prerequisite unavailable")
            path = state["source"] / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"unselected owned fixture")
            try:
                try:
                    module.verify_suite_resources(state["snapshot"])
                    return {"guard": "admitted-declared-selection"}
                except Exception as exc:
                    if type(exc).__name__ == "PreparationFailure" and type(exc).__module__ == "tablet_suite_resource_helpers":
                        return {"guard": "rejected", "status": exc.status}
                    raise
            finally:
                path.unlink()
        return action
    register("physical.new-tablet-input-rejected", extra_fixture("Assets/Tablet/new.edds", True), {"guard": "rejected", "status": "stale_input"})
    register("physical.unselected-flying-input-preserved", extra_fixture("Prefabs/SPK_BoltM.et", False), {"guard": "admitted-declared-selection"})
    def retained_extra():
        if not state:
            raise RuntimeError("Physical prerequisite unavailable")
        root = state["retained"]
        before = module.files(root)
        path = root / "unknown-resource.conf"
        path.write_bytes(b"owned extra fixture")
        try:
            # This is the exact primitive used by main unchanged() to check the
            # full retained tree. The declared-file resource validator alone is
            # deliberately narrower and does not claim tree-set admission.
            actual = module.files(root)
            return {"full_set_changed": actual != before, "only_extra": set(actual) - set(before) == {path.name}}
        finally:
            path.unlink()
    register("physical.retained-extra-visible-to-main-set-guard", retained_extra, {"full_set_changed": True, "only_extra": True})
    def physical_final():
        if not state:
            raise RuntimeError("Physical prerequisite unavailable")
        module.verify_suite_resources(state["snapshot"])
        actual = module.files(state["retained"])
        expected = {name: item["sha256"] for name, item in baseline["resources"].items()}
        originals_unchanged = True
        helper = module.resource_helper()
        for name, saved in state["original"].items():
            _, current, signature = helper.read_checked(args.mesh_project / name, (saved["identity"]["bytes"], saved["identity"]["sha256"]))
            originals_unchanged &= current == saved["identity"] and signature == saved["signature"]
        return {"owned_source_and_retained_valid": True, "exact_retained_set": actual == expected,
                "original_source_unchanged_at_observed_boundaries": originals_unchanged}
    register("physical.final-restored-and-original-readonly", physical_final,
             {"owned_source_and_retained_valid": True, "exact_retained_set": True, "original_source_unchanged_at_observed_boundaries": True})

    expected_ids = [name for name, _, _ in cases]
    assert len(expected_ids) == len(set(expected_ids)), "Duplicate planned case ID"
    paths = [Path(__file__).resolve(), TARGET, MANIFEST, COMPANION, module.HELPER, module.RESOURCE_HELPER]
    paths += module.mod.bundle_paths()
    paths = sorted(set(paths))
    frozen = {str(path): identity(path) for path in paths}
    retained_inputs = []
    for index, path in enumerate(paths):
        destination = work / "inputs" / (str(index).zfill(2) + "-" + path.name)
        destination.parent.mkdir(parents=True, exist_ok=True)
        raw = path.read_bytes()
        with destination.open("xb") as stream:
            if stream.write(raw) != len(raw):
                raise OSError("Short inert source retention")
        if identity(destination)["sha256"] != frozen[str(path)]["sha256"]:
            raise OSError("Source retention changed")
        retained_inputs.append({"original": frozen[str(path)], "retained": identity(destination)})
    record = {"schema_version": 1, "operation": "verify.tablet_suite.source_admission.inert", "status": "failure",
              "expected_case_ids": expected_ids, "cases": [], "inputs": frozen, "retained_inputs": retained_inputs,
              "scope": {"python_admission": "executed_synthetic", "owned_resource_copy": "not_run",
                        "original_mesh": "read_only", "compiler": "not_run", "powershell": "not_run",
                        "host": "not_run", "engine": "not_run", "signals": "not_run", "source_generation": "not_run",
                        "tablet_suites": "declared_not_executed", "native_resource_registration": "not_run",
                        "binary_dependency_closure": "unverified", "gameplay": "not_run", "installation": "unchanged"}}
    save(work / "planned.json", {"expected_case_ids": expected_ids, "inputs": frozen, "scope": record["scope"]})
    for index, (name, action, expected) in enumerate(cases):
        observation = None
        exception = None
        try:
            observation = action()
        except module.mod.Failure as exc:
            observation = {"rejected": True, "status": exc.status, "message": str(exc)}
        except Exception as exc:
            exception = {"type": type(exc).__name__, "message": str(exc)}
        good = type(observation) is dict and all(type(observation.get(key)) is type(value) and observation.get(key) == value
                                                 for key, value in expected.items()) and exception is None
        row = {"id": name, "status": "success" if good else "failure", "expected": expected,
               "observation": observation, "exception": exception}
        record["cases"].append(row)
        save(work / "cases" / (str(index).zfill(3) + ".json"), row)
        if name == "physical.capture-exact28-once" and good:
            record["scope"]["owned_resource_copy"] = "executed_exact_source_copy"
    record["case_set_complete"] = [row["id"] for row in record["cases"]] == expected_ids
    record["source_unchanged"] = {str(path): identity(path) for path in paths} == frozen
    record["expected_count"] = len(expected_ids)
    record["passed_count"] = sum(row["status"] == "success" for row in record["cases"])
    record["status"] = "success" if record["case_set_complete"] and record["source_unchanged"] and record["passed_count"] == len(expected_ids) else "failure"
    save(work / "result.json", record)
    print(json.dumps({"receipt": identity(work / "result.json"), "status": record["status"],
                      "expected": len(expected_ids), "passed": record["passed_count"],
                      "source": frozen[str(TARGET)], "manifest": frozen[str(MANIFEST)],
                      "failed": [row for row in record["cases"] if row["status"] != "success"]}), flush=True)
    return 0 if record["status"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
