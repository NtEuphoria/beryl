#!/usr/bin/env python3
"""Verify exactly three activation bundle sets using inert bytes in isolated fixtures.

No payload, compiler, installer or engine is launched. All activation targets are
nested, owned fixture directories; the live project build is never activated.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import traceback

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "scripts" / "activate-checkpoint.py"
spec = importlib.util.spec_from_file_location("checkpoint_profile_fixture", SOURCE)
activation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(activation)
LEGACY = frozenset(activation.BUNDLE_FILES)
COMPONENT = LEGACY | {"component_contracts.py", "tablet-component-contracts.v1.json", "beryl.mod.v2.schema.json"}
GENERATION = COMPONENT | {"component_generation.py"}
EXPECTED = (
    "legacy21-activation-rollback", "component24-activation-rollback",
    "legacy21-receipt-with-absent-mcp", "upgrade24-rollback-to-legacy21",
    "unknown24-payload", "incomplete23-payload", "extra22-payload",
    "stage-extra-entry", "stage-bundle-manifest-tamper", "stage-payload-hash-conflict",
    "destination-prior-conflict", "activation-fault-legacy21", "activation-fault-component24",
    "rollback-current-conflict", "rollback-unknown-current-bytes",
    "rollback-unknown-profile", "rollback-incomplete-profile", "rollback-extra-profile",
    "generation25-activation-rollback", "upgrade25-rollback-to-legacy21",
    "upgrade25-rollback-to-component24", "unknown25-payload", "incomplete25-payload",
    "extra26-payload", "generation25-stage-extra-entry", "activation-fault-generation25",
    "generation25-rollback-unknown-profile", "generation25-rollback-incomplete-profile",
    "generation25-rollback-extra-profile",
)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(value, detail):
    if not value:
        raise AssertionError(detail)


def tree(root):
    return {str(p.relative_to(root)): "directory" if p.is_dir() else sha(p)
            for p in sorted(root.rglob("*"))}


def install_inert_bundle(tools, files, marker):
    payload = {name: ("inert fixture payload " + marker + " " + name + "\n").encode()
               for name in sorted(files)}
    hashes = {name: activation.digest(data) for name, data in payload.items()}
    identity = activation.digest(json.dumps(hashes, sort_keys=True, separators=(",", ":")).encode())
    folder = tools / identity
    folder.mkdir()
    for name, data in payload.items():
        (folder / name).write_bytes(data)
    (folder / "bundle.json").write_bytes(activation.encoded(hashes))
    return identity


def setup(work, name, files, *, prior_mcp=True, prior_files=LEGACY):
    base = work / name
    base.mkdir()
    target, stage = base / "build", base / "stage"
    target.mkdir()
    stage.mkdir()
    for root in (target, stage):
        (root / "beryl-tools").mkdir()
    # Refuse a live target even if a future edit accidentally changes a path.
    require(target.resolve().is_relative_to(work.resolve()) and target != ROOT / "build",
            "target escaped the owned fixture directory")
    old_bundle = install_inert_bundle(target / "beryl-tools", prior_files, "old")
    old = {"beryl.exe": b"inert old compiler bytes; never execute\n",
           "beryl-tools/mod.py": b"inert old mod loader; never execute\n",
           "beryl-tools/active.json": activation.encoded({"bundle": old_bundle})}
    if prior_mcp:
        old["beryl-tools/mcp.py"] = b"inert old MCP loader; never execute\n"
    for path, data in old.items():
        (target / path).write_bytes(data)
    prior = activation.current_map(target)
    new_bundle = install_inert_bundle(stage / "beryl-tools", files, "new")
    controls = {"beryl.exe": b"inert new compiler bytes; never execute\n",
                "beryl-tools/mod.py": b"inert new mod loader; never execute\n",
                "beryl-tools/mcp.py": b"inert new MCP loader; never execute\n",
                "beryl-tools/active.json": activation.encoded({"bundle": new_bundle})}
    for path, data in controls.items():
        (stage / path).write_bytes(data)
    names = set(activation.MUTABLE) | {"beryl-tools/" + new_bundle + "/" + part
                                      for part in files | {"bundle.json"}}
    manifest = {"schema_version": 1, "target_root": str(target), "stage_root": str(stage),
                "files": [{"path": path, "sha256": sha(stage / path),
                           "expected_prior": activation.state(target / path) if path in activation.MUTABLE else None}
                          for path in sorted(names)]}
    request = base / "request.json"
    request.write_bytes(activation.encoded(manifest))
    return {"target": target, "stage": stage, "request": request, "manifest": manifest,
            "old": old, "prior": prior, "old_bundle": old_bundle, "bundle": new_bundle,
            "files": files, "base": base}


def activate(case, fault=None):
    return activation.activate(case["target"], case["request"], fault=fault)


def expected_file(case, expected):
    path = case["base"] / "expected-current.json"
    path.write_bytes(activation.encoded(expected))
    return path


def assert_restored(case):
    require(activation.current_map(case["target"]) == case["prior"], "rollback changed original mutable bytes")
    for path, data in case["old"].items():
        require((case["target"] / path).read_bytes() == data, "rollback failed exact old-byte restoration")
    if "beryl-tools/mcp.py" not in case["old"]:
        require(not (case["target"] / "beryl-tools/mcp.py").exists(), "rollback retained a previously absent MCP loader")
    require((case["target"] / "beryl-tools" / case["bundle"]).is_dir(), "rollback removed immutable bundle")
    require(not (case["target"] / ".checkpoint-lock").exists(), "rollback retained helper lock")


def roundtrip(work, name, files, prior_mcp=True, prior_files=LEGACY):
    case = setup(work, name, files, prior_mcp=prior_mcp, prior_files=prior_files)
    before_bundle = tree(case["target"] / "beryl-tools" / case["old_bundle"])
    receipt, record = activate(case)
    require(record["status"] == "activated" and record["schema_version"] == 1, record)
    require(set(record["mutable"]) == set(activation.MUTABLE), "mutable control set changed")
    expected = expected_file(case, dict(record["current_hashes"]))
    _, restored = activation.rollback(case["target"], receipt, expected)
    require(restored["status"] == "rolled_back", restored)
    assert_restored(case)
    require(tree(case["target"] / "beryl-tools" / case["old_bundle"]) == before_bundle,
            "upgrade/rollback changed prior immutable bundle")
    return {"receipt": str(receipt), "restored_prior": case["prior"], "bundle": case["bundle"]}


def rejection(case, mutate=None):
    if mutate:
        mutate(case)
    before = tree(case["target"])
    try:
        activate(case)
    except activation.GuardError as error:
        require(tree(case["target"]) == before, "rejected activation changed target bytes")
        return {"rejection": str(error)}
    raise AssertionError("invalid activation profile was accepted")


def fault_roundtrip(work, name, files):
    case = setup(work, name, files)

    def fault(when, path, target, record):
        if when == "after_replace" and path == activation.MUTABLE[0]:
            raise RuntimeError("deliberate fixture replacement failure")

    receipt, record = activate(case, fault)
    require(record["status"] == "activation_failed_rolled_back", record)
    assert_restored(case)
    return {"receipt": str(receipt), "failure": record["error"]}


def rollback_rejection(work, name, mode, files=COMPONENT):
    case = setup(work, name, files)
    receipt, record = activate(case)
    require(record["status"] == "activated", record)
    recorded_current = dict(record["current_hashes"])
    if mode in ("current", "unknown-current"):
        (case["target"] / "beryl.exe").write_bytes(b"inert unrelated writer bytes\n")
        expected = recorded_current if mode == "current" else activation.current_map(case["target"])
    else:
        saved = receipt.parent / "manifest.json"
        manifest = activation.parse(saved.read_bytes())
        prefix = "beryl-tools/" + case["bundle"] + "/"
        if mode == "unknown":
            row = next(r for r in manifest["files"] if r["path"] == prefix + "component_contracts.py")
            row["path"] = prefix + "arbitrary_module.py"
        elif mode == "incomplete":
            manifest["files"] = [r for r in manifest["files"] if r["path"] != prefix + "component_contracts.py"]
        else:
            manifest["files"].append({"path": prefix + "arbitrary_module.py",
                                      "sha256": "0" * 64, "expected_prior": None})
        raw = activation.encoded(manifest)
        saved.write_bytes(raw)
        record["manifest_sha256"] = activation.digest(raw)
        receipt.write_bytes(activation.encoded(record))
        expected = recorded_current
    before = activation.current_map(case["target"])
    try:
        activation.rollback(case["target"], receipt, expected_file(case, expected))
    except activation.GuardError as error:
        require(activation.current_map(case["target"]) == before, "rejected rollback changed mutable controls")
        require(not (case["target"] / ".checkpoint-lock").exists(), "rejected rollback retained a lock")
        return {"receipt": str(receipt), "rejection": str(error)}
    raise AssertionError("invalid rollback input was accepted")


def main():
    require(len(LEGACY) == 21 and len(COMPONENT) == 24 and len(GENERATION) == 25 and
            activation.BUNDLE_PROFILES == (LEGACY, COMPONENT, GENERATION),
            "activation profile constants differ from expected fixed sets")
    (ROOT / "build").mkdir(exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="checkpoint profiles & spaces-", dir=ROOT / "build"))
    inputs = {str(p): sha(p) for p in (SOURCE, Path(__file__).resolve())}
    receipt = {"schema_version": 1, "operation": "verify_checkpoint_bundle_profiles",
               "status": "running", "inputs": inputs, "expected_cases": list(EXPECTED),
               "completed_cases": [], "cases": [], "compiler_execution": "not_run",
               "payload_execution": "not_run", "engine_execution": "not_run",
               "live_installation": "not_run", "scope": "inert fixture activation and rollback only"}
    print("Checkpoint profile fixtures: " + str(work), flush=True)

    def run(name, action):
        require(name == EXPECTED[len(receipt["cases"])], "unexpected fixture sequence")
        row = {"case": name}
        receipt["cases"].append(row)
        row["result"] = action()
        receipt["completed_cases"].append(name)

    try:
        run(EXPECTED[0], lambda: roundtrip(work, EXPECTED[0], LEGACY))
        run(EXPECTED[1], lambda: roundtrip(work, EXPECTED[1], COMPONENT))
        run(EXPECTED[2], lambda: roundtrip(work, EXPECTED[2], LEGACY, prior_mcp=False))
        run(EXPECTED[3], lambda: roundtrip(work, EXPECTED[3], COMPONENT))
        unknown = (COMPONENT - {"component_contracts.py"}) | {"arbitrary_module.py"}
        run(EXPECTED[4], lambda: rejection(setup(work, EXPECTED[4], unknown)))
        run(EXPECTED[5], lambda: rejection(setup(work, EXPECTED[5], COMPONENT - {"component_contracts.py"})))
        run(EXPECTED[6], lambda: rejection(setup(work, EXPECTED[6], LEGACY | {"arbitrary_module.py"})))
        run(EXPECTED[7], lambda: rejection(setup(work, EXPECTED[7], COMPONENT),
            lambda c: (c["stage"] / "beryl-tools" / c["bundle"] / "arbitrary_module.py").write_bytes(b"inert extra\n")))

        def manifest_tamper(case):
            path = case["stage"] / "beryl-tools" / case["bundle"] / "bundle.json"
            hashes = activation.parse(path.read_bytes())
            hashes.pop("component_contracts.py")
            path.write_bytes(activation.encoded(hashes))
            row = next(r for r in case["manifest"]["files"] if r["path"].endswith("/bundle.json"))
            row["sha256"] = sha(path)
            case["request"].write_bytes(activation.encoded(case["manifest"]))

        run(EXPECTED[8], lambda: rejection(setup(work, EXPECTED[8], COMPONENT), manifest_tamper))
        run(EXPECTED[9], lambda: rejection(setup(work, EXPECTED[9], COMPONENT),
            lambda c: (c["stage"] / "beryl-tools" / c["bundle"] / "component_contracts.py").write_bytes(b"inert changed source\n")))
        run(EXPECTED[10], lambda: rejection(setup(work, EXPECTED[10], COMPONENT),
            lambda c: (c["target"] / "beryl-tools" / "mod.py").write_bytes(b"inert prior conflict\n")))
        run(EXPECTED[11], lambda: fault_roundtrip(work, EXPECTED[11], LEGACY))
        run(EXPECTED[12], lambda: fault_roundtrip(work, EXPECTED[12], COMPONENT))
        for index, mode in zip(range(13, 18), ("current", "unknown-current", "unknown", "incomplete", "extra")):
            run(EXPECTED[index], lambda i=index, m=mode: rollback_rejection(work, EXPECTED[i], m))
        run(EXPECTED[18], lambda: roundtrip(work, EXPECTED[18], GENERATION, prior_files=GENERATION))
        run(EXPECTED[19], lambda: roundtrip(work, EXPECTED[19], GENERATION))
        run(EXPECTED[20], lambda: roundtrip(work, EXPECTED[20], GENERATION, prior_files=COMPONENT))
        unknown_generation = (GENERATION - {"component_generation.py"}) | {"arbitrary_module.py"}
        run(EXPECTED[21], lambda: rejection(setup(work, EXPECTED[21], unknown_generation)))
        # Removing a required legacy payload leaves 24 entries, but does not
        # form the exact admitted component-24 profile. A complete component-24
        # bundle remains deliberately compatible and is not an invalid subset.
        run(EXPECTED[22], lambda: rejection(setup(work, EXPECTED[22], GENERATION - {"process_job.py"})))
        run(EXPECTED[23], lambda: rejection(setup(work, EXPECTED[23], GENERATION | {"arbitrary_module.py"})))
        run(EXPECTED[24], lambda: rejection(setup(work, EXPECTED[24], GENERATION),
            lambda c: (c["stage"] / "beryl-tools" / c["bundle"] / "arbitrary_module.py").write_bytes(b"inert extra\n")))
        run(EXPECTED[25], lambda: fault_roundtrip(work, EXPECTED[25], GENERATION))
        for index, mode in zip(range(26, 29), ("unknown", "incomplete", "extra")):
            run(EXPECTED[index], lambda i=index, m=mode: rollback_rejection(work, EXPECTED[i], m, GENERATION))
        require(receipt["completed_cases"] == list(EXPECTED), "incomplete expected fixture set")
        require({str(p): sha(p) for p in (SOURCE, Path(__file__).resolve())} == inputs, "verification source bytes changed")
        receipt["status"] = "success"
    except (AssertionError, OSError, activation.GuardError, KeyboardInterrupt) as error:
        receipt["status"] = "failure"
        receipt["failure"] = repr(error)
        receipt["traceback"] = traceback.format_exc()
    finally:
        (work / "results.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(f"{receipt['status']}: {len(receipt['completed_cases'])}/{len(EXPECTED)} inert fixture cases", flush=True)
    return 0 if receipt["status"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
