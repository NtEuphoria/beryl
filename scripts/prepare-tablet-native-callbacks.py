#!/usr/bin/env python3
"""Prepare a pinned tablet candidate plus trusted native init/stowed observers.

Source-only operation: no compiler, native program, host, editor, process, model,
promotion or live-source write. Runtime and reference emission are unavailable.
"""
from pathlib import Path
import argparse
import importlib.util
import json
import re
import sys
import tempfile

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
GUARD = ROOT / "scripts/verify-tablet-existing-suites.py"
GUARD_SHA = "b5126d057af16efe08fb1371c69fdd6c8f9fdc3a4f8186d399244325ea4baab2"
PACKAGE = ROOT / "packages/sparkos/tablet-native-callback-probe"
PRIMARY_ROOT = Path("C:/Program Files (x86)/Steam/steamapps/common/Arma Reforger Tools/Workbench/docs/EnfusionScriptAPI/html")
CONTRACT_SHA = "e8b5f9b549ebd75addaf8c776ab09ddab1166bec57b1902eaf2b606910a6ed32"
DEFAULT_RECEIPT = ROOT / "build/tablet service & spaces-soii5z39/results.json"
DEFAULT_RECEIPT_SHA = "79211ad4191492442553d8e67f6d6aa9c823a2a193d2a3207ffaf9a94a8822f9"
PROFILE = "sparkos.tablet.native-init-stowed.source.v1"
OBSERVER_PATH = "scripts/Game/BerylTabletNativeStowedObserver.c"
CASE_IDS = ("native.init.1", "native.init.2", "native.stowed-frames.1",
            "native.stowed-frames.2", "native.independent-state")
NAMES = ("SPK_BerylTabletNativeObservation", "SPK_BerylTabletNativeRegistry",
         "SPK_BerylTabletNativeObserverClass", "SPK_BerylTabletNativeObserver")
ASSETS = ("Prefabs/BerylTabletNativeStowed.et", "Prefabs/BerylTabletNativeStowed.et.meta",
          "worlds/BerylTabletNativeStowed.ent", "worlds/BerylTabletNativeStowed.ent.meta",
          "worlds/BerylTabletNativeStowed_Layers/default.layer")


def checked_module(path, expected):
    import hashlib
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise RuntimeError("Installed source guard identity differs: " + str(path))
    spec = importlib.util.spec_from_file_location("native_tablet_prior_guard", path)
    value = importlib.util.module_from_spec(spec)
    exec(compile(raw, str(path), "exec"), value.__dict__)
    return value


prior_guard = checked_module(GUARD, GUARD_SHA)
h, s1, mod = prior_guard.h, prior_guard.s1, prior_guard.mod
require, write, identity = h.require, h.write, h.identity


def validate_contract(value):
    require(type(value) is dict and type(value.get("schema_version")) is int and value["schema_version"] == 1,
            "Exact integer source contract schema required")
    require(mod.digest(mod.canonical(value)) == CONTRACT_SHA,
            "Unsupported or modified native tablet source contract", "stale_input")
    return value


def admit_assets(contract, payloads):
    contract = validate_contract(contract)
    require(type(payloads) is dict and set(payloads) == set(contract["files"]), "Exact trusted package file set required", "stale_input")
    for name, row in contract["files"].items():
        require(type(payloads[name]) is bytes and len(payloads[name]) == row["bytes"] and
                mod.digest(payloads[name]) == row["sha256"], "Trusted package bytes changed: " + name, "stale_input")
    require(contract["fixture"]["runtime_case_ids"] == list(CASE_IDS), "Scenario obligations differ")
    return contract


def package_inputs():
    expected = set(ASSETS) | {"observer.c.in", "README.md", "source-contracts.json"}
    require(set(h.files(PACKAGE)) == expected and h.directories(PACKAGE) == h.parent_directories(expected),
            "Installed native tablet package set changed", "stale_input")
    raw = {name: mod.read(PACKAGE / name) for name in expected}
    contract = validate_contract(mod.parse(raw.pop("source-contracts.json")))
    admit_assets(contract, raw)
    return contract, raw


def render_observer(mapping, generated, production, template):
    # Validate the actual source-map convention and reconstruct the exact existing
    # service seam. This neither generates nor changes its production source.
    expected, symbols, _ = s1.render(mapping, generated)
    require(production == expected, "Production adapter differs from its pinned emitted linkage", "stale_input")
    rows = [row for row in mapping["linkage"] if row.get("declaration") ==
            "sparkos.tablet_lifecycle_prototype.State" and row.get("kind") == "struct"]
    require(len(rows) == 1, "Unique emitted State declaration required", "unavailable")
    fields = {row["source"]: row["name"] for row in rows[0]["fields"]}
    accumulator = fields.get("telemetry_accumulator")
    require(type(accumulator) is str and s1.IDENT.fullmatch(accumulator), "Exact emitted accumulator field unavailable", "unavailable")
    values = {"STATE": symbols["STATE"], "MODE": symbols["MODE"], "ACCUMULATOR": accumulator}
    require(type(template) is bytes, "Observer template bytes required")
    text = template.decode("utf-8")
    for name, actual in values.items():
        text = text.replace("@" + name + "@", actual)
    require(not re.search(r"@[A-Z_]+@", text), "Unresolved observer source placeholder")
    require(text.count("super.OnPostInit(owner);") == 1 and text.count("super.EOnFrame(owner, timeSlice);") == 1 and
            re.findall(r"override\s+void\s+(\w+)\s*\(", text) == ["OnPostInit", "EOnFrame"],
            "Only two super-delegating native observer overrides are admitted")
    # Source-shape protection is supplementary to the immutable template hashes.
    require(not re.search(r"\b(?:Focus|Unfocus|SetHeld|OnDelete|DeleteRplEntity|ToggleActive|SetEventMask|new\s+SPK_TabletComponent)\s*\(", text),
            "Manual lifecycle, service or mask mutation is outside this fixture")
    return text.encode("utf-8"), values, [{"generated_line": i, "template_line": i,
            "kind": "trusted_native_observer_template", "column_mapping": "unavailable"}
            for i, line in enumerate(text.splitlines(), 1) if line.strip()]


def validate_identity_collisions(source_payloads, observer, assets):
    require(type(source_payloads) is dict, "Source payload table required")
    existing = set()
    for name, raw in source_payloads.items():
        if name.endswith(".c"):
            existing.update(name.casefold() for name in re.findall(r"(?m)^\s*(?:modded\s+)?class\s+(\w+)\b", raw.decode("utf-8-sig")))
    require(not (existing & {name.casefold() for name in NAMES}), "Trusted observer class collides with existing source", "unavailable")
    declared = re.findall(r"(?m)^\s*class\s+(\w+)\b", observer.decode("utf-8"))
    require(declared == list(NAMES), "Unexpected trusted observer declarations")
    require(sum(len(re.findall(r"\bclass\s+SPK_TabletComponent\s*:\s*ScriptComponent\b", raw.decode("utf-8-sig")))
                for name, raw in source_payloads.items() if name.endswith(".c")) == 1,
            "Exactly one production SPK_TabletComponent definition required", "stale_input")
    ids = set()
    for name, raw in source_payloads.items():
        if name.endswith(".meta"):
            ids.update(re.findall(rb'\{([0-9A-Fa-f]{16})\}', raw))
    new_ids = []
    for name in ASSETS:
        require(name not in source_payloads, "Fixture path collides with source candidate", "unavailable")
        if name.endswith(".meta"):
            found = re.findall(rb'\{([0-9A-Fa-f]{16})\}', assets[name])
            require(len(found) == 1, "One fixed resource identifier required")
            new_ids += [found[0].upper()]
    require(len(set(new_ids)) == len(new_ids) and not ({item.upper() for item in ids} & set(new_ids)),
            "Fixture resource identity collides with selected source candidate", "unavailable")


def candidate_project(contract):
    value = validate_contract(contract)["addon"]
    # Fixed typed configuration. No project-controlled engine-code strings.
    text = 'GameProject {\n ID "' + value["id"] + '"\n GUID "' + value["guid"] + '\"\n TITLE "' + value["title"] + '\"\n Dependencies {\n'
    for dependency in value["dependencies"]:
        text += '  "' + dependency + '"\n'
    return (text + ' }\n}\n').encode("utf-8")


def prepare(source, expected_sha, work, record):
    source = source.resolve(strict=True)
    require(source.is_relative_to(ROOT / "build") and source.name == "results.json" and
            type(expected_sha) is str and s1.HASH.fullmatch(expected_sha) and mod.digest(mod.read(source)) == expected_sha,
            "Pinned successful source receipt under build required", "stale_input")
    require(work.resolve(strict=True).is_relative_to(ROOT / "build") and not list(work.iterdir()),
            "Preparation requires a fresh empty owned build directory")
    prior = mod.parse(mod.read(source))
    profile = prior_guard.validate_source_receipt(prior)
    source_identity = identity(source)
    prior_guard.verify_prior(source.parent, prior, source_identity)
    contract, assets = package_inputs()
    tracked_paths = [Path(__file__).resolve(), GUARD, Path(s1.__file__), Path(h.__file__)]
    tracked_paths += sorted(p for p in mod.HERE.rglob("*") if p.is_file() and p.suffix in (".py", ".json", ".ps1"))
    tracked_paths += sorted(p for p in PACKAGE.rglob("*") if p.is_file())
    tracked_paths += [ROOT / contract["source_basis"]["layered_contract_path"]]
    tracked_paths += [PRIMARY_ROOT / item["file"] for item in contract["source_basis"]["primary_declarations"]]
    tracked = {str(p): identity(p) for p in tracked_paths}
    require(tracked[str(ROOT / contract["source_basis"]["layered_contract_path"])]["sha256"] ==
            contract["source_basis"]["layered_contract_sha256"], "Layered-world source basis changed", "stale_input")
    for item in contract["source_basis"]["primary_declarations"]:
        require(tracked[str(PRIMARY_ROOT / item["file"])]["sha256"] == item["sha256"],
                "Installed primary callback declaration changed", "stale_input")
    for i, p in enumerate(tracked_paths):
        raw = mod.read(p)
        require(mod.digest(raw) == tracked[str(p)]["sha256"] and len(raw) == tracked[str(p)]["bytes"],
                "Actual captured preparation input differs", "stale_input")
        write(work / "inputs" / (str(i).zfill(4) + "-" + p.name), raw)
    write(work / "source-candidate-result.json", mod.read(source))
    for key in ("generated_source_map", "adapter_source_map"):
        raw = mod.read(Path(prior[key]["path"]))
        require(mod.digest(raw) == prior[key]["sha256"] and len(raw) == prior[key]["bytes"],
                "Actual captured source map bytes differ", "stale_input")
        write(work / (key + ".json"), raw)
    source_payloads = {name: mod.read(Path(prior["candidate_path"]) / name) for name in sorted(prior["staged_file_set"])}
    require({name: mod.digest(raw) for name, raw in source_payloads.items()} == prior["staged_file_set"],
            "Actual copied source input bytes differ", "stale_input")
    mapping = mod.parse(mod.read(work / "generated_source_map.json"))
    observer, symbols, origins = render_observer(mapping, source_payloads[prior["generated_file"]],
                                               source_payloads[s1.TABLET], assets["observer.c.in"])
    validate_identity_collisions(source_payloads, observer, assets)
    source_payloads["addon.gproj"] = candidate_project(contract)
    payloads = dict(source_payloads)
    payloads[OBSERVER_PATH] = observer
    payloads.update({name: assets[name] for name in ASSETS})
    addon = work / "candidate-addon"
    for name, raw in payloads.items():
        write(addon / name, raw)
    expected = {name: mod.digest(raw) for name, raw in payloads.items()}
    require(len(expected) == 92, "Exact source candidate plus six fixture files required")
    prior_guard.checked_tree(addon, expected)
    # Retain exact original code without unsafe second-class identity translation.
    source_tablet_inputs = [Path(name) for name, item in prior["verification_inputs"].items()
                           if name.replace("\\", "/").endswith("/" + s1.TABLET) and
                           item["sha256"] == contract["source_basis"]["original_tablet_sha256"]]
    require(len(source_tablet_inputs) == 1, "Unique original tablet reference input required", "unavailable")
    original_tablet = mod.read(source_tablet_inputs[0])
    require(mod.digest(original_tablet) == contract["source_basis"]["original_tablet_sha256"],
            "Actual retained original tablet bytes differ", "stale_input")
    write(work / "reference/SPK_TabletComponent.original.c.txt", original_tablet)
    original = prior["original_artifact"]
    manifest = mod.parse(mod.read(Path(original["retained"]) / "artifact.json"))
    require(type(manifest) is dict and manifest.get("artifact_sha256") == original["artifact_sha256"] and
            mod.digest(mod.canonical({k: v for k, v in manifest.items() if k not in ("id", "artifact_sha256")})) == original["artifact_sha256"],
            "Original artifact manifest canonical identity differs", "stale_input")
    for name, sha in original["files"].items():
        raw = mod.read(Path(original["retained"]) / name)
        require(mod.digest(raw) == sha, "Original immutable artifact changed during capture", "stale_input")
        write(work / "original-artifact" / name, raw)
    require(h.files(work / "original-artifact") == original["files"] and
            h.directories(work / "original-artifact") == original["directories"], "Immutable artifact copy differs", "stale_input")
    for name, sha in prior["source_build_job_files"].items():
        raw = mod.read(source.parent / "source-build-job" / name)
        require(mod.digest(raw) == sha, "Source-build job changed during capture", "stale_input")
        write(work / "source-build-job" / name, raw)
    for name, sha in prior["retained_input_files"].items():
        raw = mod.read(source.parent / "inputs" / name)
        require(mod.digest(raw) == sha, "Original retained input changed during capture", "stale_input")
        write(work / "source-inputs" / name, raw)
    require(h.files(work / "source-inputs") == prior["retained_input_files"], "Original retained input copy differs", "stale_input")
    retained_logs = []
    for i, row in enumerate(prior["raw_engine_logs"]):
        original_path = Path(row["retained"])
        destination = work / "source-compile-logs" / (str(i).zfill(2) + "-" + original_path.name)
        # Raw source compilation logs are bounded here; no current engine runs.
        require(type(row["bytes"]) is int and row["bytes"] <= 16 * 1024 * 1024 and original_path.stat().st_size == row["bytes"],
                "Source compilation log exceeds capture bound or changed size", "stale_input")
        raw = original_path.read_bytes()
        require(mod.digest(raw) == row["sha256"] and len(raw) == row["bytes"],
                "Source compilation log changed or exceeds capture bound", "stale_input")
        write(destination, raw)
        retained_logs.append({"original": row, "retained": identity(destination)})
    write(work / "observer-source-map.json", mod.canonical({"schema_version": 1, "profile": PROFILE,
          "generated_path": OBSERVER_PATH, "generated_sha256": expected[OBSERVER_PATH],
          "template": tracked[str(PACKAGE / "observer.c.in")], "linkage": symbols, "mappings": origins}))
    # Read again after every copy. A receipt describes frozen inputs, not an
    # unchecked mutable selection made before the preparation operation.
    prior_guard.verify_prior(source.parent, prior, source_identity)
    require({str(p): identity(p) for p in tracked_paths} == tracked, "Preparation inputs changed", "stale_input")
    package_inputs()
    prior_guard.checked_tree(addon, expected)
    require(all(expected[name] == sha for name, sha in prior["staged_file_set"].items() if name != "addon.gproj"),
            "Preserved production source/resource bytes changed", "stale_input")
    record.update({"status": "success", "stage": "source_prepared", "source_candidate_result": source_identity,
                   "candidate_path": str(addon), "source_contract": contract, "source_profile": profile,
                   "verification_inputs": tracked, "retained_input_files": h.files(work / "inputs"),
                   "staged_file_set": expected, "staged_directory_set": h.directories(addon),
                   "staged_sha256": mod.digest(mod.canonical(expected)), "symbols": symbols,
                   "production_adapter": {"path": s1.TABLET, "sha256": expected[s1.TABLET]},
                   "generated_file": {"path": prior["generated_file"], "sha256": expected[prior["generated_file"]]},
                   "original_artifact": {"path": str(work / "original-artifact"), "files": original["files"], "directories": original["directories"],
                                         "artifact_sha256": original["artifact_sha256"]},
                   "source_build_job_files": prior["source_build_job_files"], "retained_source_compile_logs": retained_logs,
                   "retained_source_input_files": prior["retained_input_files"],
                   "reference_input": identity(work / "reference/SPK_TabletComponent.original.c.txt"),
                   "observer_source_map": identity(work / "observer-source-map.json"),
                   "prepared_file_set": h.files(work), "success_means": "Exact source and trusted fixture copied; no new compilation or callback execution."})
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-receipt", type=Path, default=DEFAULT_RECEIPT)
    parser.add_argument("--expect-receipt-sha256", default=DEFAULT_RECEIPT_SHA)
    args = parser.parse_args()
    work = Path(tempfile.mkdtemp(prefix="tablet native preparation & spaces-", dir=ROOT / "build"))
    record = {"schema_version": 1, "operation": "prepare.tablet_native_callbacks", "profile": PROFILE,
              "status": "failure", "stage": "source_preparation", "expected_runtime_case_ids": list(CASE_IDS),
              "runtime_case_state": "proposed_not_installed", "commands": [], "evidence_errors": [],
              "scope": {"source_preparation": "attempted", "compiler_generation": "not_run", "trusted_fixture_rendering": "not_run",
                        "engine_compilation": "not_run", "native_callbacks": "not_run", "reference_execution": "unavailable",
                        "public_services": "not_run", "deletion": "not_admitted", "profile_isolation": "unverified",
                        "multiplayer": "not_run", "installation": "unchanged"}}
    try:
        prepare(args.candidate_receipt, args.expect_receipt_sha256, work, record)
        record["scope"]["source_preparation"] = "verified_source_only"
        record["scope"]["trusted_fixture_rendering"] = "verified_source_only"
    except BaseException as error:
        record["status"] = getattr(error, "status", "failure")
        record["diagnostic"] = {"type": type(error).__name__, "message": str(error)}
        record["evidence_errors"].append(str(error))
    finally:
        h.save_result(work / "results.json", record)
        print(json.dumps({"result": str(work / "results.json"), "status": record["status"], "stage": record["stage"]}), flush=True)
    return 0 if record["status"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
