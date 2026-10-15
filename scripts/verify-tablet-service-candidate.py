#!/usr/bin/env python3
"""Prepare an isolated source-only MESH tablet service candidate.

Default: source checks and generation only. --run explicitly adds owned headless
Workbench compilation. This experiment does not run tablet services or gameplay,
and does not install, promote, edit live MESH, or change execution policy.
"""
from pathlib import Path
import argparse
import importlib.util
import json
import re
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "packages/sparkos/tablet-service-prototype"
LIFECYCLE = ROOT / "packages/sparkos/tablet-lifecycle-prototype/src/lifecycle.be"
HELPER = ROOT / "scripts/verify-component-state.py"
sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location("tablet_service_evidence_helpers", HELPER)
helpers = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helpers)
mod = helpers.mod
require, write = helpers.require, helpers.write
identity, streamed_identity = helpers.identity, helpers.streamed_identity
files, directories = helpers.files, helpers.directories
parent_directories, save_result = helpers.parent_directories, helpers.save_result
IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
HASH = re.compile(r"[0-9a-f]{64}")
TABLET = "scripts/Game/SparkOSMesh/UI/SPK_TabletComponent.c"
MODULE = "sparkos.tablet_lifecycle_prototype."
STATUSES = {"failure", "unavailable", "timeout", "cancelled", "stale_input"}
EXCLUDED = ("scripts/WorkbenchGameCommon/SPK_MeshSelfTest.c", "scripts/WorkbenchGameCommon/ValidatePrefab.c")
SUITE_MANIFEST = PACKAGE / "tablet-suites.v1.json"
SUITE_MANIFEST_SHA = "22a8a3b18f93599765e61b34c7c9cd3b13a011d4f8c4e8649b4e24b9d6531514"
SUITE_CANONICAL_SHA = "d0e9253dff5ee5678a658c0cf34fefbf4f537b00c59ac84f79d3b275eddfebf3"
RESOURCE_HELPER = ROOT / "scripts/prepare-tablet-resources.py"
RESOURCE_HELPER_SHA = "9b0136821c05f79bc44093d5658936aef5714b93da6eab3631c846d6a41f1df6"
CANDIDATE_PROFILES = ("source-only", "tablet-suites-v1")
PROFILE_KEYS = {"schema_version", "profile", "engine_version", "engine_sha256", "lifecycle_sha256",
                "addon_gproj_sha256", "scripts", "excluded_production_scripts", "included_game_debug_probe_scripts",
                "ignored_non_source_paths"}


def validate_suite_profile(value):
    """Admit one installed immutable source profile, never project commands."""
    keys = {"schema_version", "profile", "source_provenance", "addon", "resources", "resource_registrations",
            "external_base_references_unresolved", "workbench_handlers", "suite_selections", "suite_response_contract",
            "limits", "limitations"}
    require(type(value) is dict and set(value) == keys and type(value["schema_version"]) is int and value["schema_version"] == 1 and
            value["profile"] == "sparkos.tablet.suites-source.v1", "Unsupported tablet suite source profile")
    resources = value["resources"]
    require(type(resources) is dict and len(resources) == 28, "Exact 28-resource profile required")
    for name, item in resources.items():
        require(type(name) is str and not name.startswith("/") and "\\" not in name and ":" not in name and
                ".." not in name.split("/") and name.startswith(("Assets/", "Prefabs/", "Configs/")) and
                type(item) is dict and set(item) == {"bytes", "sha256"} and type(item["bytes"]) is int and
                0 <= item["bytes"] <= 8 * 1024 * 1024 and type(item["sha256"]) is str and HASH.fullmatch(item["sha256"]),
                "Invalid bounded resource identity")
    require(sum(item["bytes"] for item in resources.values()) == 12655544, "Resource aggregate differs from reviewed profile")
    registrations = value["resource_registrations"]
    require(type(registrations) is dict and len(registrations) == 13, "Exact thirteen registrations required")
    guids = set()
    for name, item in registrations.items():
        require(name in resources and name + ".meta" in resources and type(item) is dict and
                set(item) == {"resource", "guid", "sidecar", "line"} and type(item["guid"]) is str and
                re.fullmatch(r"[0-9A-F]{16}", item["guid"]) and item["guid"] not in guids and
                item["resource"] == "{" + item["guid"] + "}" + name and item["sidecar"] == name + ".meta" and
                type(item["line"]) is int and item["line"] == 2, "Invalid or duplicate native registration")
        guids.add(item["guid"])
    require(type(value["external_base_references_unresolved"]) is list and len(value["external_base_references_unresolved"]) == 18 and
            all(type(item) is str for item in value["external_base_references_unresolved"]) and
            len(set(value["external_base_references_unresolved"])) == 18, "Explicit eighteen unresolved base references required")
    expected_suites = [{"suite": name, "arg": ""} for name in ("ui", "screen", "actions", "clicks")]
    expected_suites.append({"suite": "schema", "arg": "{B37EEB64E149CBAD}Prefabs/SPK_Tablet.et"})
    require(type(value["suite_selections"]) is list and value["suite_selections"] == expected_suites and
            all(type(row) is dict and set(row) == {"suite", "arg"} and type(row["suite"]) is str and type(row["arg"]) is str
                for row in value["suite_selections"]), "Only the five installed typed suite requests are admitted")
    require(type(value["suite_response_contract"]) is dict and type(value["suite_response_contract"].get("successful_ok")) is int,
            "Suite success requires an integer outcome")
    # This fixed canonical identity also admits exact nested provenance, handlers,
    # addon identity, limits, and limitations, rejecting all unknown nested keys.
    require(mod.digest(mod.canonical(value)) == SUITE_CANONICAL_SHA, "Installed tablet suite profile changed", "stale_input")
    return value


def tablet_suite_profile():
    raw = mod.read(SUITE_MANIFEST)
    require(mod.digest(raw) == SUITE_MANIFEST_SHA, "Installed tablet suite manifest changed", "stale_input")
    return validate_suite_profile(mod.parse(raw))


def candidate_companion(raw, candidate_profile, suite_profile=None):
    require(candidate_profile in CANDIDATE_PROFILES, "Unknown candidate profile")
    if candidate_profile == "source-only":
        return raw
    value = mod.parse(raw)
    require(type(value) is dict, "Scalar companion must be an object")
    suite = validate_suite_profile(suite_profile)
    value["addon"] = dict(suite["addon"])
    value["name"] = "Beryl experimental tablet suite source candidate"
    return mod.canonical(value)


def resource_helper():
    raw = mod.read(RESOURCE_HELPER)
    require(mod.digest(raw) == RESOURCE_HELPER_SHA, "Installed checked-resource helper changed", "stale_input")
    spec = importlib.util.spec_from_file_location("tablet_suite_resource_helpers", RESOURCE_HELPER)
    module = importlib.util.module_from_spec(spec)
    # Execute exactly the checked installed helper bytes, rather than reopening
    # the path during import and trusting a later before/after hash alone.
    exec(compile(raw, str(RESOURCE_HELPER), "exec"), module.__dict__)
    return module


def capture_suite_resources(source, retained_dir, profile):
    """Compose the existing checked resource primitives; no import or engine."""
    profile = validate_suite_profile(profile)
    helper = resource_helper()
    specification = {name: (item["bytes"], item["sha256"]) for name, item in profile["resources"].items()}
    require(sum(item[0] for item in specification.values()) <= helper.MAX_TOTAL_BYTES, "Resource capture exceeds existing byte limit")
    helper.no_links(source)
    selected = helper.asset_selection(source, specification)
    data, identities, signatures = {}, {}, {}
    for name in sorted(specification):
        data[name], identities[name], signatures[name] = helper.read_checked(source / name, specification[name])
    for name, item in profile["resource_registrations"].items():
        sidecar = helper.text(data[item["sidecar"]], item["sidecar"])
        require(re.findall(r'^\s*Name\s+"([^"\r\n]+)"\s*$', sidecar, re.M) == [item["resource"]],
                "Native resource registration differs", "stale_input")
    reviewed_tablet = helper.reviewed_edges(data)
    for name, raw in data.items():
        helper.checked_write(retained_dir / name, raw, retained_dir)
    snapshot = {"source": source, "retained": retained_dir, "profile": profile, "identities": identities,
                "signatures": signatures, "tablet_selection": selected}
    verify_suite_resources(snapshot)
    receipt = {"selected_files": identities, "selected_file_count": len(identities),
               "selected_bytes": sum(item["bytes"] for item in identities.values()),
               "source_sha256": mod.digest(mod.canonical(identities)), "resource_registrations": profile["resource_registrations"],
               "tablet_source_review": reviewed_tablet, "external_base_references_unresolved": profile["external_base_references_unresolved"],
               "scope": "source and sidecar preservation only", "native_registration": "not_run",
               "binary_dependency_closure": "unverified", "target_resource_availability": "unverified"}
    return snapshot, receipt


def verify_suite_resources(snapshot):
    helper = resource_helper()
    profile = validate_suite_profile(snapshot["profile"])
    require(helper.asset_selection(snapshot["source"], profile["resources"]) == snapshot["tablet_selection"],
            "Tablet source selection changed", "stale_input")
    for name, item in profile["resources"].items():
        expected = item["bytes"], item["sha256"]
        _, current, signature = helper.read_checked(snapshot["source"] / name, expected)
        require(current == snapshot["identities"][name] and signature == snapshot["signatures"][name],
                "Resource source changed between observed checks", "stale_input")
        _, retained, _ = helper.read_checked(snapshot["retained"] / name, expected)
        require(retained == current, "Retained resource changed", "stale_input")


def compile_success(value):
    if type(value) is not dict or type(value.get("schema_version")) is not int or value["schema_version"] != 1:
        return False
    detail = value.get("result")
    return (value.get("stage") == "workbench_compile" and value.get("status") == "success" and type(detail) is dict and
            detail.get("Ok") is True and detail.get("Stage") == "Compiled" and type(detail.get("ExitCode")) is int and
            detail["ExitCode"] == 0 and type(detail.get("ErrorCount")) is int and detail["ErrorCount"] == 0)


def source_profile():
    value = mod.parse(mod.read(PACKAGE / "source-profile.json"))
    require(type(value) is dict and set(value) == PROFILE_KEYS and type(value["schema_version"]) is int and value["schema_version"] == 1 and
            value["profile"] == "tablet-service-source-candidate.v1", "Unsupported source fixture profile")
    require(type(value["scripts"]) is dict and len(value["scripts"]) == 56 and
            value["excluded_production_scripts"] == list(EXCLUDED), "Exact 56-source profile required")
    for name, sha in value["scripts"].items():
        require(type(name) is str and name.endswith(".c") and
                (name.startswith("scripts/Game/SparkOSMesh/") or name in EXCLUDED) and
                ".." not in Path(name).parts and type(sha) is str and HASH.fullmatch(sha), "Invalid profile source identity")
    require(len([name for name in value["scripts"] if name.startswith("scripts/Game/")]) == 54 and
            TABLET in value["scripts"], "Exact Game source set required")
    for key in ("engine_sha256", "lifecycle_sha256", "addon_gproj_sha256"):
        require(type(value[key]) is str and HASH.fullmatch(value[key]), "Malformed profile fingerprint")
    require(value["lifecycle_sha256"] == "34c2b848e94a7a68132804d08a58fcf31d644f2d0e9eb2b4973e84a39249f792" and
            value["scripts"][TABLET] == "1f15962cf67a8cc513d7068757e89360260016fadff1c8843719784acc94be3a",
            "Reviewed protocol or original tablet baseline differs", "stale_input")
    require(type(value["ignored_non_source_paths"]) is list and len(value["ignored_non_source_paths"]) == 4 and
            all(type(name) is str and "/.claude-flow/" in name and name.endswith(".json") for name in value["ignored_non_source_paths"]),
            "Only the declared non-source state paths are excluded")
    require(type(value["included_game_debug_probe_scripts"]) is list and len(value["included_game_debug_probe_scripts"]) == 6 and
            all(name in value["scripts"] and name.startswith("scripts/Game/") for name in value["included_game_debug_probe_scripts"]),
            "Debug/probe source consumers must be explicitly inventoried")
    return value


def mesh_sources(root):
    result = {}
    for path in sorted((root / "scripts").rglob("*")):
        require(not path.is_symlink() and not (hasattr(path, "is_junction") and path.is_junction()),
                "Linked MESH source path is not admitted", "stale_input")
        if path.is_file() and path.suffix == ".c":
            result[path.relative_to(root).as_posix()] = mod.digest(mod.read(path))
    require(len(result) == 56, "MESH source selection changed", "stale_input")
    return result


def inventory(root, names):
    """Lexical inventory is a bounded source review, not a general type proof."""
    matches, definitions, extensions = [], [], []
    for name in sorted(names):
        source = mod.read(root / name).decode("utf-8-sig")
        if re.search(r"(?:class\s+\w+\s*:\s*SPK_TabletComponent\b|modded\s+class\s+SPK_TabletComponent\b)", source):
            extensions.append(name)
        definitions += [name for _ in re.finditer(r"\bclass\s+SPK_TabletComponent\s*:\s*ScriptComponent\b", source)]
        for line, text in enumerate(source.splitlines(), 1):
            if re.search(r"\b(?:SPK_TabletComponent|m_fTelemetryAccum|m_eState|SyncScreen)\b", text):
                matches.append({"path": name, "line": line, "text": text.strip()})
            if name != TABLET:
                require(not re.search(r"\b(?:m_fTelemetryAccum|SyncScreen)\b|\.\s*m_eState\b", text),
                        "Unreviewed external protected tablet storage consumer", "unavailable")
    require(definitions == [TABLET] and not extensions, "Unexpected production tablet definition or extension", "unavailable")
    return {"kind": "lexical_source_inventory", "scope": "exact 56 admitted .c files", "matches": matches,
            "tablet_definitions": definitions, "tablet_extensions": extensions,
            "note": "Other unqualified m_eState references belong to independently reviewed health, warhead and laser classes; external extension compatibility is not claimed."}


def render(mapping, generated):
    require(type(mapping) is dict and type(mapping.get("schema_version")) is int and mapping["schema_version"] == 1 and mapping.get("target") == "enfusion" and
            type(mapping.get("linkage_schema_version")) is int and mapping["linkage_schema_version"] == 1 and type(mapping.get("linkage")) is list,
            "Exact emitted linkage/source map is unavailable", "unavailable")
    def row(name, kind):
        items = [item for item in mapping["linkage"] if type(item) is dict and item.get("declaration") == MODULE + name]
        require(len(items) == 1 and items[0].get("kind") == kind, "Missing exact emitted declaration: " + name)
        return items[0]
    def fields(item, expected):
        require(type(item.get("fields")) is list and len(item["fields"]) == len(expected), "Wrong emitted field set")
        values = {}
        for field in item["fields"]:
            require(type(field) is dict and type(field.get("source")) is str and field["source"] not in values,
                    "Malformed or duplicate emitted field")
            values[field["source"]] = field.get("name")
        require(set(values) == set(expected), "Emitted state/operation fields differ")
        return values
    state, operation, nxt = row("State", "struct"), row("Operation", "struct"), row("next", "function")
    sf = fields(state, ("mode", "telemetry_accumulator"))
    of = fields(operation, ("kind", "pc", "screen_pc", "held", "time_slice", "answer"))
    symbols = {"STATE": state.get("class"), "OPERATION": operation.get("class"),
               "MODE": sf["mode"], "NEXT_HOLDER": nxt.get("holder"), "NEXT_METHOD": nxt.get("method")}
    symbols.update({key.upper(): value for key, value in of.items()})
    require(all(type(value) is str and IDENT.fullmatch(value) for value in symbols.values()), "Unsafe emitted identity")
    native = generated.decode("utf-8")
    signature = r"\bstatic\s+int\s+" + re.escape(symbols["NEXT_METHOD"]) + r"\s*\(\s*out\s+" + re.escape(symbols["STATE"]) + \
                r"\s+\w+\s*,\s*out\s+" + re.escape(symbols["OPERATION"]) + r"\s+\w+\s*,\s*int\s+\w+\s*\)"
    require(len(re.findall(signature, native)) == 1, "Expected direct inout State/Operation calling convention is unavailable", "unavailable")
    for key in ("STATE", "OPERATION"):
        name = symbols[key]
        require(len(re.findall(r"\bclass\s+" + re.escape(name) + r"\b", native)) == 1 and
                len(re.findall(r"\bvoid\s+" + re.escape(name) + r"\s*\(\s*\)", native)) == 1,
                "Required generated record constructor is unavailable", "unavailable")
    template = mod.read(PACKAGE / "tablet-service.c.in").decode("utf-8")
    text = template
    for key, value in symbols.items():
        text = text.replace("@" + key + "@", value)
    require(not re.search(r"@[A-Z_]+@", text) and len(text.splitlines()) == len(template.splitlines()), "Unresolved adapter placeholder")
    require(text.count("super.OnPostInit(owner);") == 1 and text.count("super.OnDelete(owner);") == 1 and
            text.count("SetEventMask(owner, EntityEvent.FRAME);") == 1 and "BerylCopy" not in text,
            "Duplicate lifecycle ownership or copied-state adapter")
    origins = [{"generated_line": line, "template_line": line, "kind": "trusted_adapter_template", "column_mapping": "unavailable"}
               for line, contents in enumerate(text.splitlines(), 1) if contents.strip()]
    return text.encode("utf-8"), symbols, origins


def classify_compile_attempt(record):
    """Record actual adapter/target outcomes separately from verification."""
    attempt = record["attempts"]["engine_compile"]
    matching = [row for row in record.get("commands", []) if type(row) is dict and
                type(row.get("stdout")) is str and
                Path(row["stdout"]).name.endswith("-tablet_service_engine_compile.stdout.log")]
    if matching:
        attempt["process_outcome"] = matching[-1].get("status", "incomplete")
    compiled = record["raw_results"].get("compile", {}).get("result")
    if type(compiled) is not dict:
        return
    attempt["adapter_status"] = compiled.get("status", "incomplete")
    if type(compiled.get("schema_version")) is not int or compiled["schema_version"] != 1 or compiled.get("stage") != "workbench_compile":
        return
    detail = compiled.get("result")
    if type(detail) is not dict:
        return
    if detail.get("Stage") == "Compiled" and type(detail.get("Ok")) is bool and type(detail.get("ExitCode")) is int:
        succeeded = compile_success(compiled)
        attempt["target_outcome"] = "executed_success" if succeeded else "executed_failure"
        if record["scope"]["engine_compilation"] != "executed_success":
            record["scope"]["engine_compilation"] = attempt["target_outcome"]
    elif detail.get("Stage") == "DidNotStart":
        attempt["target_outcome"] = "startup_unavailable"
        record["scope"]["engine_compilation"] = "attempted_unconfirmed"
    elif detail.get("Stage") == "Timeout":
        attempt["target_outcome"] = "timeout_incomplete"
        record["scope"]["engine_compilation"] = "attempted_incomplete"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--beryl", type=Path, required=True)
    parser.add_argument("--expect-compiler-sha256", required=True)
    parser.add_argument("--mesh-project", type=Path, required=True)
    parser.add_argument("--workbench-tools", type=Path, required=True)
    parser.add_argument("--powershell-host", type=Path)
    parser.add_argument("--engine-exe", type=Path)
    parser.add_argument("--candidate-profile", choices=CANDIDATE_PROFILES, default="source-only",
                        help="Explicit resource/handler source profile; neither profile executes suites")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--prepare-only", action="store_true", help="Default; source generation without engine launch")
    mode.add_argument("--run", action="store_true", help="Explicitly compile the prepared addon; no runtime test")
    args = parser.parse_args()
    compiler = args.beryl.resolve(strict=True)
    require(compiler.is_relative_to(ROOT / "build") and compiler.parent != ROOT / "build" and HASH.fullmatch(args.expect_compiler_sha256) and
            mod.digest(mod.read(compiler)) == args.expect_compiler_sha256, "Exact private compiler candidate required; no execution occurred", "stale_input")
    mesh = args.mesh_project.resolve(strict=True)
    toolroot = args.workbench_tools.resolve(strict=True)
    host = args.powershell_host.resolve(strict=True) if args.powershell_host else None
    engine = args.engine_exe.resolve(strict=True) if args.engine_exe else None
    require(not args.run or (host is not None and engine is not None), "--run requires explicit PowerShell host and engine executable", "unavailable")
    work = Path(tempfile.mkdtemp(prefix="tablet service & spaces-", dir=ROOT / "build"))
    record = {"schema_version": 1, "operation": "verify.tablet_service.source_candidate", "stage": "prepare", "status": "failure",
              "commands": [], "raw_results": {}, "expected_runtime_case_ids": [], "measurements": [],
              "scope": {"source_generation": "not_run", "engine_compilation": "not_run", "engine_callback_delivery": "not_run",
                        "tablet_services": "not_run", "host_gameplay": "not_run", "multiplayer": "not_run", "visual_review": "not_run",
                        "resource_closure": "unverified", "service_lifetime": "unverified", "installation": "unchanged", "policy_changes": "not_run"},
              "resource_policy": "resource_adequate_exact; persistent scalar state plus one new Operation per synchronous invocation",
              "limitation": "Trusted experimental source adapter only. No runtime equivalence, queue/handler lifetime, prefab/resources, authority, multiplayer, UI or performance acceptance. Strict version-one scalar generation is separate from the trusted service seam."}
    record["candidate_profile"] = args.candidate_profile
    record["scope"]["tablet_suite_execution"] = "not_run"
    record["attempts"] = {"engine_compile": {"requested": bool(args.run), "adapter_invocation_attempted": False,
                                            "process_outcome": "not_run", "adapter_status": "not_run", "target_outcome": "not_run"}}
    outer, guard = None, None
    tracked = {}
    print("Tablet-service evidence: " + str(work), flush=True)
    try:
        profile = source_profile()
        suite = tablet_suite_profile() if args.candidate_profile == "tablet-suites-v1" else None
        resource_snapshot = None
        package_set = files(PACKAGE)
        sources = mesh_sources(mesh)
        require(sources == profile["scripts"] and mod.digest(mod.read(mesh / "addon.gproj")) == profile["addon_gproj_sha256"],
                "MESH source baseline changed", "stale_input")
        require(mod.digest(mod.read(LIFECYCLE)) == profile["lifecycle_sha256"], "Reviewed lifecycle source changed", "stale_input")
        record["protected_consumer_inventory"] = inventory(mesh, sources)
        record["source_profile"] = profile
        if suite:
            require(all(profile["scripts"].get(name) == item["sha256"] for name, item in suite["workbench_handlers"].items()),
                    "Suite handlers differ from admitted source baseline", "stale_input")
            record["tablet_suite_profile"] = suite
            record["tablet_suite_manifest"] = identity(SUITE_MANIFEST)
            record["suite_selection"] = {"status": "declared_not_executed", "requests": suite["suite_selections"],
                                         "response_contract": suite["suite_response_contract"], "executed": 0}
        plugins = sorted((toolroot / "scripts").glob("*.ps1"))
        require(len(plugins) <= 128 and set(helpers.COMPILE_TOOLS).issubset({path.name for path in plugins}), "Missing/bounded installed compile transport", "unavailable")
        inputs = [("compiler/compiler.input", compiler), ("python/python.input", Path(sys.executable).resolve()),
                  ("verifier/verify-tablet-service-candidate.py", Path(__file__).resolve()), ("verifier/verify-component-state.py", HELPER),
                  ("lifecycle/lifecycle.be", LIFECYCLE), ("mesh/addon.gproj", mesh / "addon.gproj"),
                  ("contracts/P5_TABLET_SERVICE_ADAPTER_CONTRACT.md", ROOT / "docs/advanced/P5_TABLET_SERVICE_ADAPTER_CONTRACT.md")]
        inputs += [("fixture/" + name, PACKAGE / name) for name in package_set]
        inputs += [("mesh/" + name, mesh / name) for name in sources]
        inputs += [("tools/" + path.relative_to(ROOT).as_posix(), path) for path in mod.bundle_paths()]
        inputs += [("plugin/scripts/" + path.name, path) for path in plugins]
        if suite:
            inputs.append(("verifier/prepare-tablet-resources.py", RESOURCE_HELPER))
        if host:
            inputs.append(("host/powershell.input", host))
        for relative, path in inputs:
            require(path.is_file() and not path.is_symlink(), "Verification input is not a regular file")
            item = identity(path)
            write(work / "inputs" / relative, mod.read(path))
            require(mod.digest(mod.read(work / "inputs" / relative)) == item["sha256"], "Retained input changed", "stale_input")
            tracked[str(path)] = item
        if suite:
            resource_snapshot, resource_receipt = capture_suite_resources(mesh, work / "inputs/mesh-resources", suite)
            record["resource_source_snapshot"] = resource_receipt
        record["verification_inputs"] = tracked
        retained_inputs = files(work / "inputs")
        record["retained_input_files"] = retained_inputs
        record["retained_input_sha256"] = mod.digest(mod.canonical(retained_inputs))
        record["plugin_file_set"] = {path.name: tracked[str(path)]["sha256"] for path in plugins}
        if engine:
            record["engine_input"] = streamed_identity(engine)
            require(record["engine_input"]["sha256"] == profile["engine_sha256"], "Engine differs from reviewed profile", "stale_input")
        project = work / "project"
        write(project / "beryl.mod.json", candidate_companion(mod.read(PACKAGE / "beryl.mod.json"), args.candidate_profile, suite))
        write(project / "src/lifecycle.be", mod.read(LIFECYCLE))
        outer = mod.Job(project, "tablet-service-candidate", compiler)
        config, frozen, hashes = outer.snapshot()
        require(config["schema_version"] == 1 and config["exports"] == [] and config["binding"]["version"] == profile["engine_version"] and
                config["addon"]["guid"] not in ("4008B09320C27BA6", "58D0FB3206B6F859") and config["addon"]["id"] != "SparkOSMesh" and
                config["addon"]["dependencies"] == ["58D0FB3206B6F859"], "Unexpected scalar generation/candidate identity")
        if suite:
            require(config["addon"] == suite["addon"], "Selected candidate identity differs", "stale_input")
        record["frozen_project_inputs"] = hashes
        with helpers.source_tool_environment():
            try:
                raw = outer.run([compiler, "mod", "build", "--project", project], "lifecycle_source_build", work, timeout=120)
            except mod.Failure as exc:
                command = outer.result["raw_logs"][-1] if outer.result["raw_logs"] else None
                if command:
                    try:
                        failed = mod.parse(mod.read(Path(command["stdout"])))
                    except (ValueError, mod.Failure):
                        failed = None
                    if type(failed) is dict:
                        record["source_build_result"] = failed
                        raise helpers.failed_adapter(exc, failed) from exc
                raise
        result = mod.parse(raw)
        record["source_build_result"] = result
        require(type(result) is dict and result.get("status") == "success" and result.get("compiler_sha256") == args.expect_compiler_sha256 and
                result.get("tool_sha256") == outer.result["tool_sha256"] and result.get("source_sha256") == outer.result["source_sha256"],
                "Source build lacks exact source/compiler/tool evidence", "stale_input")
        original, artifact = mod.load_artifact(outer, result.get("artifact_id"))
        require(artifact["artifact_sha256"] == result.get("artifact_sha256"), "Artifact/result identity differs", "stale_input")
        retained = work / "original-artifact"
        shutil.copytree(original, retained)
        original_files, original_dirs = files(original), directories(original)
        require(files(retained) == original_files and directories(retained) == original_dirs, "Original artifact copy changed", "stale_input")
        record["original_artifact"] = {"path": str(original), "retained": str(retained), "files": original_files,
                                       "directories": original_dirs, "artifact_sha256": artifact["artifact_sha256"]}
        child_result = Path(result["result_path"])
        require(child_result.is_relative_to(project / ".beryl-mod/jobs"), "Source job escaped owned project", "stale_input")
        shutil.copytree(child_result.parent, work / "source-build-job")
        child_files = files(child_result.parent)
        require(files(work / "source-build-job") == child_files, "Source job retention differs", "stale_input")
        record["source_build_job_files"] = child_files
        mapping = mod.parse(mod.read(retained / "source-map.json"))
        require(mapping.get("sources") == [{"path": "src/lifecycle.be", "sha256": profile["lifecycle_sha256"]}], "Emitted source differs from frozen protocol", "stale_input")
        generated = mapping.get("generated")
        require(type(generated) is dict and type(generated.get("file")) is str and Path(generated["file"]).name == generated["file"] and
                type(generated.get("sha256")) is str and HASH.fullmatch(generated["sha256"]) and type(generated.get("bytes")) is int,
                "Missing exact generated-file identity")
        generated_paths = [name for name, sha in artifact["files"].items() if Path(name).name == generated["file"] and sha == generated["sha256"]]
        require(len(generated_paths) == 1, "Generated file identity is not unique in immutable manifest")
        generated_path = generated_paths[0]
        generated_bytes = mod.read(retained / "addon" / generated_path)
        require(len(generated_bytes) == generated["bytes"] and mod.digest(generated_bytes) == generated["sha256"], "Generated bytes differ from source-map identity", "stale_input")
        adapter, symbols, origins = render(mapping, generated_bytes)
        addon = work / "candidate-addon"
        shutil.copytree(retained / "addon", addon)
        require(files(addon) == artifact["files"] and directories(addon) == parent_directories(artifact["files"]),
                "Copied original addon differs from exact manifest", "stale_input")
        expected = dict(artifact["files"])
        for name in sorted(sources):
            if name in EXCLUDED and not suite:
                continue
            require(name not in expected and not (addon / name).exists(), "MESH source collides with generated artifact")
            data = adapter if name == TABLET else mod.read(work / "inputs/mesh" / name)
            write(addon / name, data)
            expected[name] = mod.digest(data)
        if suite:
            verify_suite_resources(resource_snapshot)
            resource = resource_helper()
            for name, item in suite["resources"].items():
                require(name not in expected and not (addon / name).exists(), "Resource collides with generated candidate")
                raw, _, _ = resource.read_checked(resource_snapshot["retained"] / name, (item["bytes"], item["sha256"]))
                resource.checked_write(addon / name, raw, addon)
                expected[name] = item["sha256"]
            require(len(expected) == suite["limits"]["candidate_files"], "Exact 86 candidate input files required")
        require(files(addon) == expected and directories(addon) == parent_directories(expected), "Candidate source set differs", "stale_input")
        definition_count = sum(len(re.findall(r"\bclass\s+SPK_TabletComponent\s*:\s*ScriptComponent\b", mod.read(addon / name).decode("utf-8-sig")))
                               for name in expected if name.endswith(".c"))
        require(definition_count == 1, "Candidate requires exactly one production tablet class")
        origin_map = {"schema_version": 1, "operation": "trusted_adapter_source_map", "target": "enfusion",
                      "generated": {"file": TABLET, "sha256": mod.digest(adapter), "bytes": len(adapter)},
                      "template": {"path": str(PACKAGE / "tablet-service.c.in"), "sha256": package_set["tablet-service.c.in"]},
                      "mapping_precision": "Exact template lines; original Beryl/engine statement association and columns unavailable",
                      "mappings": origins, "linkage": symbols}
        save_result(work / "adapter-source-map.json", origin_map)
        record.update(candidate_path=str(addon), candidate_addon=config["addon"], generated_file=generated_path,
                      generated_source_map=identity(retained / "source-map.json"), adapter_source_map=identity(work / "adapter-source-map.json"),
                      symbols=symbols, staged_file_set=expected, staged_directory_set=parent_directories(expected),
                      staged_sha256=mod.digest(mod.canonical(expected)), excluded_production_scripts=[] if suite else list(EXCLUDED),
                      included_game_debug_probe_scripts=profile["included_game_debug_probe_scripts"])
        record["scope"]["source_generation"] = "executed_success"
        if suite:
            record["scope"]["resource_source_copy"] = "executed_success"

        def unchanged():
            outer.unchanged(hashes)
            require(files(PACKAGE) == package_set and mesh_sources(mesh) == sources, "Fixture/MESH sources changed", "stale_input")
            require(files(work / "inputs") == retained_inputs, "Retained verification inputs changed", "stale_input")
            require(sorted(path.name for path in (toolroot / "scripts").glob("*.ps1")) == [path.name for path in plugins], "Plugin set changed", "stale_input")
            for path, item in tracked.items():
                require(identity(Path(path)) == item, "Verification input changed: " + path, "stale_input")
            if resource_snapshot:
                verify_suite_resources(resource_snapshot)
            if engine:
                require(streamed_identity(engine) == record["engine_input"], "Engine changed", "stale_input")
            require(files(original) == original_files and files(retained) == original_files and directories(original) == original_dirs and
                    directories(retained) == original_dirs, "Original artifact changed", "stale_input")
            require(files(child_result.parent) == child_files and files(work / "source-build-job") == child_files,
                    "Source build job changed", "stale_input")
            require(mod.parse(mod.read(work / "adapter-source-map.json")) == origin_map, "Adapter source map changed", "stale_input")
            actual, derived = files(addon), {}
            if "resourceDatabase.rdb" not in expected and "resourceDatabase.rdb" in actual:
                path = addon / "resourceDatabase.rdb"
                require(path.stat().st_size <= 8 * 1024 * 1024, "Derived engine cache exceeds bound", "unavailable")
                derived["resourceDatabase.rdb"] = identity(path)
                del actual["resourceDatabase.rdb"]
            require(actual == expected and directories(addon) == parent_directories(expected), "Staged source/gproj/tree changed", "stale_input")
            if suite:
                resource = resource_helper()
                for name, item in suite["resources"].items():
                    resource.read_checked(addon / name, (item["bytes"], item["sha256"]))
            record["engine_derived_outputs"] = derived
        guard = unchanged
        guard()
        if args.run:
            record["stage"] = "engine_compile"
            compile_path = work / "engine-compile.json"
            try:
                guard()
                record["attempts"]["engine_compile"].update(adapter_invocation_attempted=True, target_outcome="attempted_unconfirmed")
                record["scope"]["engine_compilation"] = "attempted_unconfirmed"
                outer.run([host, "-NoProfile", "-File", mod.HERE / "engine-compile.ps1", "-ToolRoot", toolroot,
                           "-ProjectDir", addon, "-ResultPath", compile_path, "-ExpectedVersion", profile["engine_version"]],
                          "tablet_service_engine_compile", work, timeout=300)
            except mod.Failure as exc:
                helpers.capture_adapter(record, "compile", compile_path)
                raise helpers.failed_adapter(exc, record["raw_results"].get("compile", {}).get("result")) from exc
            finally:
                if "compile" not in record["raw_results"]:
                    helpers.capture_adapter(record, "compile", compile_path)
            compiled = record["raw_results"].get("compile", {}).get("result", {})
            require(compile_success(compiled),
                    "Missing successful exact engine compilation evidence")
            require(compiled.get("engine_sha256") == profile["engine_sha256"] and compiled.get("engine_version") == profile["engine_version"] and
                    compiled.get("tools") == {name: record["plugin_file_set"][name] for name in helpers.COMPILE_TOOLS},
                    "Compile engine/tool identities differ", "stale_input")
            record["scope"]["engine_compilation"] = "executed_success"
            guard()
        record.update(status="success", stage="engine_compile" if args.run else "prepared",
                      success_means="exact candidate script compilation" if args.run else "isolated source candidate prepared; engine not run")
    except BaseException as exc:
        status = getattr(exc, "status", "cancelled" if isinstance(exc, KeyboardInterrupt) else "failure")
        record.update(status=status if status in STATUSES else "failure",
                      failure={"type": type(exc).__name__, "message": str(exc), "pointer": getattr(exc, "pointer", None)})
        raise
    finally:
        active = sys.exc_info()[1]
        final = None
        try:
            if guard:
                guard()
        except BaseException as exc:
            final = exc
            record["final_integrity_failure"] = {"type": type(exc).__name__, "message": str(exc), "status": getattr(exc, "status", "failure")}
            if record["status"] == "success":
                record["status"] = getattr(exc, "status", "failure") if getattr(exc, "status", "failure") in STATUSES else "failure"
        try:
            record["raw_engine_logs"] = helpers.retain_engine_logs(work, record["raw_results"].get("compile", {}).get("result", {}))
            if args.run and record["status"] == "success":
                require(record["raw_engine_logs"], "Raw compilation logs unavailable", "unavailable")
            if record.get("evidence_errors") and record["status"] == "success":
                raise mod.Failure("Adapter receipt capture incomplete")
        except BaseException as exc:
            final = exc
            record["final_evidence_failure"] = {"type": type(exc).__name__, "message": str(exc), "status": getattr(exc, "status", "failure")}
            if record["status"] == "success":
                record["status"] = getattr(exc, "status", "failure") if getattr(exc, "status", "failure") in STATUSES else "failure"
        if outer:
            record["commands"] = outer.result["raw_logs"]
            classify_compile_attempt(record)
            try:
                for command in record["commands"]:
                    for stream in ("stdout", "stderr"):
                        path = Path(command[stream])
                        if path.is_file():
                            command[stream + "_sha256"] = streamed_identity(path)["sha256"]
            except BaseException as exc:
                final = exc
                record["process_log_capture_failure"] = {"type": type(exc).__name__, "message": str(exc)}
                if record["status"] == "success":
                    record["status"] = "failure"
            outer.result.update(status=record["status"], stage=record["stage"])
            try:
                save_result(outer.path / "result.json", outer.result)
            except BaseException as exc:
                final = exc
                record.update(status="failure", receipt_failure={"type": type(exc).__name__, "message": str(exc)})
            record["job"] = outer.result
        save_result(work / "results.json", record)
        print("Receipt: " + str(work / "results.json"), flush=True)
        if final is not None and active is None:
            raise mod.Failure("Final evidence/integrity check failed: " + str(final), record["status"]) from final


if __name__ == "__main__":
    main()
