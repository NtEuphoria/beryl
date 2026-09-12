#!/usr/bin/env python3
"""Installed local mod orchestrator. Standard library only; no project hooks."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import time
import uuid

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))  # Installed helper directory; never the project cwd.
SCHEMA = HERE / "beryl.mod.v1.schema.json"
if not SCHEMA.exists():
    SCHEMA = HERE.parent.parent / "schemas/beryl.mod.v1.schema.json"
ANALYSIS_SCHEMA = HERE / "beryl.analysis.v1.schema.json"
if not ANALYSIS_SCHEMA.exists():
    ANALYSIS_SCHEMA = HERE.parent.parent / "schemas/beryl.analysis.v1.schema.json"
MAX_FILE = 16 * 1024 * 1024
MAX_PLAN_INPUT = 64 * 1024 * 1024
MAX_PLAN_OUTPUT = 3 * 1024 * 1024


class Failure(Exception):
    def __init__(self, message, status="failure", pointer=None):
        super().__init__(message)
        self.status, self.pointer = status, pointer


def digest(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def bundle_paths():
    return [HERE / name for name in ("mod.py", "process_job.py", "engine-compile.ps1",
            "scenarios.py", "map-cursor.c.in", "scenario-engine-run.ps1", "source_maps.py",
            "terrain_scenarios.py", "terrain-reference.c.txt", "terrain-reference.json",
            "terrain-adapter.c.in", "terrain-handler.c.in", "storage_scenarios.py", "array-storage.c.in", "canvas-retention.c.in",
            "terrain_measurements.py", "terrain-measurement.c.in", "terrain-adapter-v1.c.txt",
            "mcp_server.py")] + [SCHEMA, ANALYSIS_SCHEMA]


def tool_identity():
    return digest(canonical({path.name: digest(read(path)) for path in bundle_paths()}))


def read(path):
    with Path(path).open("rb") as stream:
        data = stream.read(MAX_FILE + 1)
    if len(data) > MAX_FILE:
        raise Failure(f"File exceeds {MAX_FILE} bytes: {path}")
    return data


def pairs(items):
    out = {}
    for key, value in items:
        if key in out:
            raise Failure(f"Duplicate JSON key: {key}")
        out[key] = value
    return out


def parse(data):
    return json.loads(data.decode("utf-8-sig"), object_pairs_hook=pairs,
                      parse_constant=lambda value: (_ for _ in ()).throw(Failure(f"Nonfinite JSON: {value}")))


def write_json(path, value):
    path = Path(path)
    temporary = path.with_name(path.name + ".pending-" + uuid.uuid4().hex)
    with temporary.open("xb") as stream:
        stream.write(json.dumps(value, indent=2, ensure_ascii=True).encode() + b"\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def validate(value, node, schema, pointer=""):
    """Interpret the exact small vocabulary used by our published JSON schema."""
    if "$ref" in node:
        node = schema["$defs"][node["$ref"].removeprefix("#/$defs/")]
    kind = node.get("type")
    kinds = {"object": dict, "array": list, "string": str, "integer": int}
    if kind and type(value) is not kinds[kind]:
        raise Failure(f"Expected {kind}", pointer=pointer)
    if "const" in node and (value != node["const"] or type(value) is not type(node["const"])):
        raise Failure(f"Unsupported value; expected {node['const']!r}", pointer=pointer)
    if isinstance(value, dict):
        unknown = set(value) - set(node.get("properties", {}))
        missing = set(node.get("required", [])) - set(value)
        if unknown or missing:
            raise Failure(f"Unknown fields: {sorted(unknown)}; missing fields: {sorted(missing)}", pointer=pointer)
        for key, child in value.items():
            validate(child, node["properties"][key], schema, pointer + "/" + key)
    elif isinstance(value, list):
        if not node.get("minItems", 0) <= len(value) <= node.get("maxItems", 100000):
            raise Failure("Array length outside schema limit", pointer=pointer)
        if node.get("uniqueItems") and len({canonical(v) for v in value}) != len(value):
            raise Failure("Duplicate array entries", pointer=pointer)
        for i, child in enumerate(value):
            validate(child, node["items"], schema, pointer + f"/{i}")
    elif isinstance(value, str):
        if not node.get("minLength", 0) <= len(value) <= node.get("maxLength", 4096):
            raise Failure("String length outside schema limit", pointer=pointer)
        if "pattern" in node and not re.fullmatch(node["pattern"], value):
            raise Failure("String does not match schema pattern", pointer=pointer)


def safe_path(root, name, must_exist=False):
    pure = PurePosixPath(name)
    if not name or "\\" in name or ":" in name or pure.is_absolute() or any(p in (".", "..", "") for p in name.split("/")):
        raise Failure(f"Expected a relative path without traversal: {name}")
    target = root.joinpath(*pure.parts)
    current = root
    for part in pure.parts:
        current = current / part
        if current.is_symlink() or (hasattr(current, "is_junction") and current.is_junction()):
            raise Failure(f"Linked paths are not admitted: {name}")
    if not target.resolve().is_relative_to(root.resolve()):
        raise Failure(f"Path escapes project: {name}")
    if must_exist and not target.is_file():
        raise Failure(f"Missing input: {name}")
    return target


def description_snapshot(project, max_total=None):
    """Shared v1 structural validation; no compiler calls or filesystem writes."""
    data = read(safe_path(project, "beryl.mod.json", True))
    schema = parse(read(SCHEMA))
    config = parse(data)
    validate(config, schema, schema)
    contents = {"beryl.mod.json": data}
    total = len(data)
    seen = {}
    for mode, names in config["sources"].items():
        local = set()
        for name in names:
            folded = name.casefold()
            if folded in local or (folded in seen and seen[folded] != name):
                raise Failure(f"Duplicate/case-conflicting source: {name}", pointer="/sources/" + mode)
            local.add(folded)
            seen[folded] = name
            value = read(safe_path(project, name, True))
            total += len(value) - len(contents.get(name, b""))
            if max_total is not None and total > max_total:
                raise Failure(f"Planning inputs exceed {max_total} bytes", "unavailable", "/sources")
            contents[name] = value
    if set(config["sources"]["native"]) & set(config["sources"]["tests"]):
        raise Failure("Tests must not repeat a native implementation input")
    if config["addon"]["guid"] in config["addon"]["dependencies"]:
        raise Failure("An addon cannot depend on itself", pointer="/addon/dependencies")
    return config, contents, {name: digest(value) for name, value in contents.items()}


class Job:
    def __init__(self, project, command, compiler):
        self.project, self.compiler = project, compiler
        self.id = uuid.uuid4().hex
        root = project / ".beryl-mod"
        if root.is_symlink() or (hasattr(root, "is_junction") and root.is_junction()):
            raise Failure("Linked .beryl-mod directory is not admitted")
        self.path = safe_path(root, "jobs/" + self.id)
        self.path.mkdir(parents=True, exist_ok=False)
        self.result = {"schema_version": 1, "operation_id": self.id, "operation": "mod " + command,
                       "stage": "description", "status": "failure", "diagnostics": [],
                       "compiler_sha256": digest(read(compiler)), "tool_sha256": tool_identity(),
                       "source_sha256": None, "binding_sha256": None, "artifact_sha256": None,
                       "raw_logs": [], "measurements": [], "result_path": str(self.path / "result.json")}

    def run(self, argv, stage, cwd, timeout=120):
        self.result["stage"] = stage
        stem = self.path / f"{len(self.result['raw_logs']):03d}-{stage}"
        out_path, err_path = Path(str(stem) + ".stdout.log"), Path(str(stem) + ".stderr.log")
        record = {"argv": [str(v) for v in argv], "cwd": str(cwd), "stdout": str(out_path),
                  "stderr": str(err_path), "status": "startup_failure", "exit_code": None}
        self.result["raw_logs"].append(record)
        started = time.monotonic()
        # The C driver owns the enclosing process tree when invoked through
        # `beryl mod`. Direct Python invocation uses a local job on Windows too.
        from process_job import ProcessJob
        with out_path.open("xb") as out, err_path.open("xb") as err, ProcessJob() as owner:
            try:
                process = subprocess.Popen(record["argv"], cwd=cwd, stdin=subprocess.DEVNULL,
                                           stdout=out, stderr=err, creationflags=owner.flags,
                                           start_new_session=(os.name != "nt"))
                owner.attach(process)
                try:
                    code = process.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    record["status"] = "timeout"
                    owner.stop(process)
                    raise Failure(f"{stage} timed out", "timeout")
                except KeyboardInterrupt:
                    record["status"] = "cancelled"
                    owner.stop(process)
                    raise Failure(f"{stage} cancelled", "cancelled")
                record.update(status="exited", exit_code=code, seconds=time.monotonic() - started)
            except OSError as exc:
                raise Failure(f"Cannot start {stage}: {exc}", "unavailable") from exc
        if code:
            raise Failure(f"{stage} exited with {code}; inspect retained logs")
        return read(out_path)

    def snapshot(self):
        config, contents, hashes = description_snapshot(self.project)
        inputs = self.path / "inputs"
        inputs.mkdir()
        for name, value in contents.items():
            target = safe_path(inputs, name)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(value)
        self.result["source_sha256"] = digest(canonical(hashes))
        self.result["binding_sha256"] = digest(canonical(config["binding"]))
        self.result["binding_status"] = "declared; not engine-verified by check/build"
        return config, inputs, hashes

    def unchanged(self, hashes):
        if any(digest(read(safe_path(self.project, name, True))) != value for name, value in hashes.items()):
            raise Failure("Source changed since this artifact was built", "stale_input")
        if digest(read(self.compiler)) != self.result["compiler_sha256"]:
            raise Failure("Compiler changed during this operation", "stale_input")
        if tool_identity() != self.result["tool_sha256"]:
            raise Failure("Installed tooling changed during this operation", "stale_input")


def export_flags(config):
    flags = []
    for item in config["exports"]:
        flags += ["--export-class", item["source"] + "=" + item["name"]]
        if "constructor" in item:
            flags += ["--export-constructor", item["constructor"] + "=" + item["name"]]
        for method in item["methods"]:
            if not method["source"].startswith(item["source"] + "."):
                raise Failure("Method receiver differs from its containing export")
            flags += ["--export-method", method["source"] + "=" + method["name"]]
    return flags


def workflow_plan(project, compiler):
    """Describe installed workflows for exact v1 bytes, without semantic checks."""
    compiler_hash = digest(read(compiler))
    tool_hash = tool_identity()
    schema_hash = digest(read(SCHEMA))
    config, contents, hashes = description_snapshot(project, MAX_PLAN_INPUT)
    # Reuse the existing pure export-contract validation. The compiler still
    # owns symbol resolution, signature checking, conflicts and target admission.
    export_flags(config)
    source_hash = digest(canonical(hashes))
    binding_hash = digest(canonical(config["binding"]))
    import scenarios
    registry = scenarios.registry()
    identities = {"compiler_sha256": compiler_hash, "tool_sha256": tool_hash,
                  "schema_sha256": schema_hash, "source_sha256": source_hash,
                  "binding_sha256": binding_hash, "artifact_sha256": None}

    def action(arguments, required=()):
        # Required placeholders are data references, never interpolated shell
        # strings. A consumer must supply and validate them before explicit use.
        return {"executable": str(compiler), "arguments": arguments,
                "required_values": list(required), "executed": False}

    def mod_action(command, arguments=(), required=()):
        return action(["mod", command, "--project", str(project), *arguments], required)

    def stage(name, depends, capabilities, actions, outputs, status="not_checked", reason=None):
        item = {"id": name, "depends_on": depends, "requires": capabilities,
                "status": status, "actions": actions, "outputs": outputs,
                "executed": False, "evidence": [], "requires_explicit_invocation": True}
        if reason:
            item["reason"] = reason
        return item

    tests = config["sources"]["tests"]
    stages = [
        stage("semantic_check", [], ["compiler_check_native", "compiler_check_enfusion"],
              [mod_action("check")], ["compiler diagnostics"],
              reason="Both declared targets and export signatures must be checked by the compiler."),
        stage("native_tests", ["semantic_check"], ["selected_test_backend"],
              [action(["test", "--backend", {"value": "backend"},
                       *[str(project / name) for name in config["sources"]["native"] + tests]], ["backend"])] if tests else [],
              ["test execution receipt"], status="not_checked" if tests else "unavailable",
              reason="Select reference, native or differential explicitly; their admitted subsets differ." if tests else "The companion declares no test sources; an empty selection is not success."),
        stage("candidate_build", ["semantic_check"], ["compiler_check_native", "compiler_check_enfusion", "enfusion_generation"],
              [mod_action("build")], ["candidate_addon", "source_map", "artifact_identity"],
              reason="Build repeats target checks and generates an isolated artifact; plan does neither."),
        stage("workbench_compile", ["candidate_build"], ["matching_engine", "workbench_transport", "unchanged_artifact"],
              [mod_action("verify", ["--stage", "compile", "--artifact", {"value": "artifact_id"},
                                     "--workbench-tools", {"value": "workbench_tools"}], ["artifact_id", "workbench_tools"])],
              ["artifact-bound compilation receipt", "raw and mapped engine diagnostics"]),
        stage("installed_scenario", ["candidate_build"], ["matching_engine", "workbench_transport", "engine_runtime", "unchanged_artifact"],
              [mod_action("verify", ["--scenario", {"value": "installed_scenario"}, "--artifact", {"value": "artifact_id"},
                                     "--workbench-tools", {"value": "workbench_tools"}], ["installed_scenario", "artifact_id", "workbench_tools"])],
              ["scenario-specific execution receipt"],
              reason="Optional installed fixture selected separately; validate its specific typed parameters before using the template. Measurement scenarios need additional --measurement-plan input. No scenario is selected by this v1 companion and no gameplay acceptance is implied."),
        stage("promotion", ["workbench_compile"], ["unchanged_artifact", "owned_destination"],
              [mod_action("promote", ["--artifact", {"value": "artifact_id"}, "--destination", {"value": "destination"}], ["artifact_id", "destination"])],
              ["guarded ownership manifest", "rollback records"],
              reason="A separate explicit command; this plan does not authorize, perform or validate promotion."),
    ]
    missing = [
        ("companion_v2", "Version 2 descriptions and typed scenario selections are not admitted by the current schema."),
        ("tablet_lifecycle", "The v1 class-export profile cannot generate the planned tablet lifecycle, map-mode button or prefab fragment."),
        ("project_gameplay_runtime", "No project gameplay scenario is selected or supplied by the v1 description; installed probe fixtures are separate."),
        ("multiplayer_acceptance", "Dedicated-server/two-client acceptance is not a supplied v1 workflow stage."),
        ("visual_acceptance", "Ultrawide/1080p appearance and interaction require separate review; no visual evidence is collected."),
        ("whole_mod_authoring", "Resource composition, components, prefabs, layouts, asset import and packing are outside this v1 profile."),
    ]
    for name, reason in missing:
        stages.append(stage(name, [], [], [], [], "unavailable", reason))
    capabilities = [{"id": "v1_structure", "implementation": "implemented", "local_availability": "available",
                     "input_admission": "validated_this_operation", "evidence": "exact description, declared paths and byte hashes only"}]
    for name in dict.fromkeys(c for item in stages for c in item["requires"]):
        capabilities.append({"id": name, "implementation": "required_by_workflow",
                             "local_availability": "not_checked", "input_admission": "not_checked", "evidence": None})
    for name, reason in missing:
        capabilities.append({"id": name, "implementation": "unavailable_in_v1_workflow",
                             "local_availability": "unavailable", "input_admission": "unavailable", "evidence": None, "reason": reason})
    plan = {"schema_version": 1, "kind": "beryl.mod.workflow", "identities": identities,
            "project": {"path": str(project), "name": config["name"], "addon": config["addon"],
                        "companion_version": 1, "binding": {"declared": config["binding"], "verification": "not_checked"}},
            "admission": {"structure": "validated", "symbols": "not_checked", "target_semantics": "not_checked",
                          "exports": "receiver_spelling_checked; declaration identity/signatures/conflicts not_checked"},
            "inputs": [{"path": name, "sha256": hashes[name], "bytes": len(contents[name]),
                        "roles": [mode for mode, names in config["sources"].items() if name in names] or ["description"]}
                       for name in sorted(hashes)],
            "source_sets": config["sources"],
            "parameters": {"backend": {"type": "string", "enum": ["reference", "native", "differential"]},
                           "artifact_id": {"type": "string", "pattern": "^[0-9a-f]{32}$", "origin": "successful candidate_build result"},
                           "workbench_tools": {"type": "host_configured_path", "verification": "not_checked"},
                           "destination": {"type": "explicit_user_selected_path", "ownership": "must be verified by promote"},
                           "installed_scenario": {"type": "string", "enum": [v["name"] for v in registry if v["implementation"] == "implemented"],
                                                  "parameters": "validate against selected installed_scenarios definition; this template is not an executable script"}},
            "export_summaries": [{"source": item["source"], "name": item["name"], "constructor": item.get("constructor"),
                                  "methods": len(item["methods"]), "json_pointer": "/exports/" + str(i)} for i, item in enumerate(config["exports"])],
            "outputs": [{"id": name, "location_template": location, "produced_by_this_operation": False, "prior_existence": "not_checked"}
                        for name, location in (("candidate_addon", ".beryl-mod/artifacts/{artifact_id}/addon/addon.gproj and scripts/Game/Beryl/*.c"),
                                               ("source_map", ".beryl-mod/artifacts/{artifact_id}/source-map.json"),
                                               ("artifact_identity", ".beryl-mod/artifacts/{artifact_id}/artifact.json"))],
            "capabilities": capabilities, "stages": stages,
            "installed_scenarios": {"selected": None, "availability": "execution_not_checked", "definitions": registry},
            "limits": {"individual_input_bytes": MAX_FILE, "snapshot_bytes": MAX_PLAN_INPUT, "plan_json_bytes": MAX_PLAN_OUTPUT},
            "limitations": ["Plan construction is structural validation, not compiler, engine, test or performance evidence.",
                            "All declared source bytes are captured and rechecked; this is not an atomic filesystem snapshot or an ownership/ACL audit.",
                            "No artifact or previous receipt is consulted; existing success cannot be inferred.",
                            "The existing C dispatcher and MCP adapter can create their own transport logs; this planner creates no jobs or files."]}
    encoded_plan = canonical(plan)
    if len(encoded_plan) > MAX_PLAN_OUTPUT:
        raise Failure(f"Workflow plan exceeds {MAX_PLAN_OUTPUT} output bytes", "unavailable")
    for name, expected in hashes.items():
        if digest(read(safe_path(project, name, True))) != expected:
            raise Failure("Input changed during planning: " + name, "stale_input")
    if digest(read(compiler)) != compiler_hash or tool_identity() != tool_hash or digest(read(SCHEMA)) != schema_hash:
        raise Failure("Compiler, tooling or schema changed during planning", "stale_input")
    return {"schema_version": 1, "operation_id": uuid.uuid4().hex, "operation": "mod plan", "stage": "planning", "status": "success",
            "success_means": "v1 structural snapshot validation and workflow construction succeeded",
            **identities, "execution": "not_run", "raw_logs": [], "measurements": [],
            "diagnostics": [{"code": "BEMPLAN001", "severity": "information", "message": "Source semantics, target admission and execution remain unverified.",
                             "help": "Run the described semantic check explicitly, then build and validate the resulting artifact through the applicable stages."}],
            "plan_sha256": digest(encoded_plan), "plan": plan}


def checks(job, config, inputs):
    for mode in ("native", "enfusion"):
        flags = ["-t", "enfusion", "--prefix", "Beryl", *export_flags(config)] if mode == "enfusion" else []
        sources = config["sources"][mode] + (config["sources"]["tests"] if mode == "native" else [])
        try:
            output = job.run([job.compiler, "check", "--format", "json", *flags, *sources], mode + "_check", inputs)
        except Failure:
            output = read(job.result["raw_logs"][-1]["stdout"])
            try:
                job.result["diagnostics"].extend(parse(output)["diagnostics"])
            except (ValueError, KeyError, Failure):
                pass
            raise
        result = parse(output)
        if result.get("status") != "success":
            raise Failure("Compiler did not report successful checking")


def build(job, config, inputs, hashes):
    addon = job.path / "addon"
    scripts = addon / "scripts/Game/Beryl"
    scripts.mkdir(parents=True)
    source_map = job.path / "source-map.json"
    job.run([job.compiler, "build", "-t", "enfusion", "--prefix", "Beryl", "--out-dir", scripts,
             "--source-map", source_map,
             *export_flags(config), *config["sources"]["enfusion"]], "generation", inputs)
    mapping = parse(read(source_map))
    if mapping.get("schema_version") != 1 or mapping.get("target") != "enfusion":
        raise Failure("Missing supported generated source map")
    exports = {}
    for index, item in enumerate(config["exports"]):
        pointer = "/exports/" + str(index)
        exports[item["source"]] = pointer
        if "constructor" in item:
            exports[item["constructor"]] = pointer + "/constructor"
        for method_index, method in enumerate(item["methods"]):
            exports[method["source"]] = pointer + "/methods/" + str(method_index)
    companion = {"path": "beryl.mod.json", "sha256": hashes["beryl.mod.json"]}
    for item in mapping.get("exports", []):
        if item.get("source") in exports:
            item["companion"] = {**companion, "json_pointer": exports[item["source"]]}
    for item in mapping.get("mappings", []):
        if item.get("declaration") in exports:
            item["companion"] = {**companion, "json_pointer": exports[item["declaration"]]}
    write_json(source_map, mapping)
    identity = config["addon"]
    lines = ["GameProject {", " ID " + json.dumps(identity["id"]), " GUID " + json.dumps(identity["guid"]),
             " TITLE " + json.dumps(config["name"]), " Dependencies {"]
    lines += ["  " + json.dumps(guid) for guid in identity["dependencies"]]
    (addon / "addon.gproj").write_text("\n".join(lines + [" }", "}", ""]), encoding="utf-8", newline="\n")
    files = {str(p.relative_to(addon)).replace("\\", "/"): digest(read(p)) for p in sorted(addon.rglob("*")) if p.is_file()}
    if not any(name.endswith(".c") for name in files):
        raise Failure("No generated script artifact")
    identity = {"schema_version": 1, "compiler_sha256": job.result["compiler_sha256"],
                "tool_sha256": job.result["tool_sha256"], "source_sha256": job.result["source_sha256"],
                "binding": config["binding"], "inputs": hashes, "files": files,
                "sidecars": {"source-map.json": digest(read(source_map))}}
    artifact_hash = digest(canonical(identity))
    job.unchanged(hashes)
    artifact = safe_path(job.project, ".beryl-mod/artifacts/" + job.id)
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.mkdir()
    shutil.copytree(addon, artifact / "addon")
    shutil.copyfile(source_map, artifact / "source-map.json")
    write_json(artifact / "artifact.json", {**identity, "id": job.id, "artifact_sha256": artifact_hash})
    job.result.update(artifact_id=job.id, artifact_sha256=artifact_hash, artifact_path=str(artifact), stage="candidate")


def load_artifact(job, identity):
    if not identity or not re.fullmatch("[0-9a-f]{32}", identity):
        raise Failure("--artifact must name a generated artifact id")
    path = safe_path(job.project, ".beryl-mod/artifacts/" + identity, False)
    artifact = parse(read(path / "artifact.json"))
    body = {key: value for key, value in artifact.items() if key not in ("id", "artifact_sha256")}
    if artifact.get("id") != identity or digest(canonical(body)) != artifact.get("artifact_sha256"):
        raise Failure("Artifact manifest fingerprint mismatch", "stale_input")
    for name, value in artifact["files"].items():
        if digest(read(safe_path(path / "addon", name, True))) != value:
            raise Failure(f"Generated artifact changed: {name}", "stale_input")
    actual = {str(p.relative_to(path / "addon")).replace("\\", "/") for p in (path / "addon").rglob("*") if p.is_file()}
    if actual != set(artifact["files"]):
        raise Failure("Untracked files were added to the artifact", "stale_input")
    for name, value in artifact.get("sidecars", {}).items():
        if name != "source-map.json" or digest(read(safe_path(path, name, True))) != value:
            raise Failure("Artifact sidecar changed or is unsupported: " + name, "stale_input")
    job.unchanged(artifact["inputs"])
    if artifact["compiler_sha256"] != job.result["compiler_sha256"] or artifact["tool_sha256"] != job.result["tool_sha256"]:
        raise Failure("Artifact compiler/tool version differs from current installation", "stale_input")
    job.result.update(artifact_id=identity, artifact_sha256=artifact["artifact_sha256"],
                      source_sha256=artifact["source_sha256"], binding_sha256=digest(canonical(artifact["binding"])))
    return path, artifact


def verify(job, args):
    path, artifact = load_artifact(job, args.artifact)
    if args.scenario:
        import scenarios
        scenarios.run(sys.modules[__name__], job, args, path, artifact)
        return
    if args.scenario_count is not None or args.scenario_case is not None or args.measurement_plan is not None:
        raise Failure("Scenario parameters require --scenario")
    if args.stage != "compile" or not args.workbench_tools:
        raise Failure("Compilation requires --stage compile and --workbench-tools <installed plugin directory>", "unavailable")
    addon = job.path / "candidate"
    shutil.copytree(path / "addon", addon)
    engine_result = job.path / "engine.json"
    try:
        job.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", HERE / "engine-compile.ps1",
                 "-ToolRoot", Path(args.workbench_tools).resolve(), "-ProjectDir", addon, "-ResultPath", engine_result,
                 "-ExpectedVersion", artifact["binding"]["version"]], "workbench_compile", job.path, timeout=300)
    except Failure as exc:
        if engine_result.is_file():
            failed = parse(read(engine_result))
            engine_diagnostics(job, path, artifact, failed, addon)
            raise engine_failure(exc, failed) from exc
        raise
    result = parse(read(engine_result))
    engine_diagnostics(job, path, artifact, result, addon)
    if result.get("stage") != "workbench_compile" or result.get("result", {}).get("Ok") is not True:
        raise Failure("Missing successful engine compilation evidence")
    load_artifact(job, args.artifact)
    for name, value in artifact["files"].items():
        if digest(read(safe_path(addon, name, True))) != value:
            raise Failure("Engine candidate sources changed during compilation", "stale_input")
    receipt = {"schema_version": 1, "stage": "compile", "status": "success", "artifact_sha256": artifact["artifact_sha256"],
               "operation_id": job.id, "engine": result, "raw_result": str(engine_result)}
    write_json(path / ("compile-" + job.id + ".json"), receipt)
    job.result.update(stage="workbench_compile", binding_status="engine version verified", engine=result)


def engine_diagnostics(job, artifact_path, artifact, result, candidate):
    job.result["engine"] = result
    if type(result.get("result")) is not dict:
        return
    from source_maps import map_engine_diagnostics
    job.result["diagnostics"].extend(map_engine_diagnostics(sys.modules[__name__], artifact_path,
                                   artifact, result, project_root=candidate, source_root=job.project))


def engine_failure(error, result):
    status = result.get("status", getattr(error, "status", "failure"))
    if status not in ("failure", "unavailable", "timeout", "cancelled", "stale_input"):
        status = "failure"
    return Failure(str(error), status)


def promote(job, args):
    path, artifact = load_artifact(job, args.artifact)
    if args.stage or args.scenario or getattr(args, "scenario_count", None) is not None or getattr(args, "scenario_case", None) is not None or args.measurement_plan is not None or args.workbench_tools or not args.destination:
        raise Failure("Promotion requires --artifact and --destination only")
    verified = None
    for receipt_path in sorted(path.glob("compile-*.json")):
        receipt = parse(read(receipt_path))
        operation = receipt.get("operation_id", "")
        if not re.fullmatch("[0-9a-f]{32}", operation):
            continue
        raw = safe_path(job.project, ".beryl-mod/jobs/" + operation + "/engine.json")
        if (receipt.get("artifact_sha256") == artifact["artifact_sha256"] and
                receipt.get("status") == "success" and receipt.get("stage") == "compile" and
                raw.is_file() and parse(read(raw)) == receipt.get("engine") and
                receipt["engine"].get("result", {}).get("Ok") is True and
                receipt["engine"].get("engine_version") == artifact["binding"]["version"]):
            verified = receipt
    if verified is None:
        raise Failure("No successful compilation receipt for this exact artifact", "unavailable")
    destination = Path(args.destination).absolute()
    if destination.is_symlink() or (hasattr(destination, "is_junction") and destination.is_junction()):
        raise Failure("Promotion destination cannot be a link")
    destination = destination.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    lock = destination.with_name(destination.name + ".beryl-promotion-lock")
    try:
        lock.mkdir()
    except FileExistsError as exc:
        raise Failure("Another promotion owns this destination lock") from exc
    job.result.update(stage="promotion", destination=str(destination), compile_operation=verified["operation_id"])
    mutated = []
    before = {}
    owned_name = ".beryl-owned.json"
    try:
        destination.mkdir(exist_ok=True)
        owner_file = safe_path(destination, owned_name)
        previous = parse(read(owner_file)) if owner_file.exists() else {"schema_version": 1, "files": {}}
        if previous.get("schema_version") != 1 or type(previous.get("files")) is not dict:
            raise Failure("Invalid prior ownership manifest")
        old_files = previous["files"]
        files = artifact["files"]
        if owned_name in files or owned_name in old_files:
            raise Failure("Artifact overlaps its ownership manifest")
        for name in sorted(set(old_files) | set(files) | {owned_name}):
            target = safe_path(destination, name)
            if target.exists() and not target.is_file():
                raise Failure(f"Destination is not a regular file: {name}")
            data = read(target) if target.exists() else None
            before[name] = data
            if name in old_files and (data is None or digest(data) != old_files[name]):
                raise Failure(f"Previously generated output changed: {name}", "stale_input")
            if name != owned_name and name in files and name not in old_files and data is not None:
                raise Failure(f"Refusing to replace handwritten/unowned file: {name}")
        rollback = job.path / "rollback"
        rollback.mkdir()
        for name, data in before.items():
            if data is not None:
                backup = safe_path(rollback, name)
                backup.parent.mkdir(parents=True, exist_ok=True)
                backup.write_bytes(data)
        write_json(job.path / "rollback.json", {"destination": str(destination),
                   "previous": {name: digest(data) if data is not None else None for name, data in before.items()}})
        load_artifact(job, args.artifact)
        after = {name: read(safe_path(path / "addon", name, True)) for name in files}
        after.update({name: None for name in set(old_files) - set(files)})
        ownership = {"schema_version": 1, "artifact_sha256": artifact["artifact_sha256"], "artifact_id": args.artifact,
                     "source_sha256": artifact["source_sha256"], "files": files, "compile_operation": verified["operation_id"]}
        after[owned_name] = canonical(ownership) + b"\n"
        # Ownership is written last. Each mutation compares the exact prior bytes.
        for name in [n for n in sorted(after) if n != owned_name] + [owned_name]:
            target = safe_path(destination, name)
            current = read(target) if target.exists() else None
            if current != before[name]:
                raise Failure(f"Destination changed during promotion: {name}", "stale_input")
            target.parent.mkdir(parents=True, exist_ok=True)
            data = after[name]
            if data is None:
                target.unlink()
            else:
                temporary = target.with_name(target.name + ".pending-" + job.id)
                with temporary.open("xb") as stream:
                    stream.write(data)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary, target)
            mutated.append((name, data))
        job.result.update(stage="promoted", rollback=str(job.path / "rollback.json"),
                          verification_level="Workbench compilation; runtime acceptance is a separate gate")
    except (Exception, KeyboardInterrupt):
        conflicts = []
        for name, installed in reversed(mutated):
            target = safe_path(destination, name)
            current = read(target) if target.exists() else None
            if current != installed:
                conflicts.append(name)
                continue
            if before[name] is None:
                target.unlink()
            else:
                temporary = target.with_name(target.name + ".rollback-" + job.id)
                temporary.write_bytes(before[name])
                os.replace(temporary, target)
        job.result["rollback_conflicts"] = conflicts
        if conflicts:
            job.result["diagnostics"].append({"code": "BEM002", "message": "Rollback preserved externally changed files: " + ", ".join(conflicts)})
        raise
    finally:
        lock.rmdir()


def main(argv=None):
    class Parser(argparse.ArgumentParser):
        def error(self, message):
            raise Failure(message)
    parser = Parser(description=__doc__)
    parser.add_argument("command", choices=("plan", "check", "build", "verify", "promote", "scenarios"))
    parser.add_argument("--project", default=".")
    parser.add_argument("--beryl", required=True)
    parser.add_argument("--artifact")
    parser.add_argument("--stage", choices=("compile",))
    parser.add_argument("--scenario")
    parser.add_argument("--scenario-count", type=int, action="append")
    parser.add_argument("--scenario-case", action="append")
    parser.add_argument("--measurement-plan", action="append")
    parser.add_argument("--workbench-tools")
    parser.add_argument("--destination")
    try:
        args = parser.parse_args(argv)
    except Failure as exc:
        print(json.dumps({"schema_version": 1, "operation": "mod", "stage": "arguments", "status": "failure",
                          "diagnostics": [{"code": "BEM001", "message": str(exc)}]}))
        return 2
    job = None
    try:
        if args.command == "plan":
            if args.artifact or args.stage or args.scenario or args.scenario_count is not None or args.scenario_case is not None or args.measurement_plan is not None or args.destination or args.workbench_tools:
                raise Failure("Planning accepts only --project and --beryl; execution options are not admitted")
            sys.dont_write_bytecode = True
            result = workflow_plan(Path(args.project).resolve(strict=True), Path(args.beryl).resolve(strict=True))
            print(json.dumps(result, indent=2))
            return 0
        if args.command == "scenarios":
            if args.artifact or args.stage or args.scenario or args.scenario_count is not None or args.scenario_case is not None or args.measurement_plan is not None or args.destination or args.workbench_tools:
                raise Failure("Scenario discovery does not accept execution options")
            import scenarios
            print(json.dumps({"schema_version": 1, "operation": "mod scenarios", "stage": "discovery",
                              "status": "success", "tool_sha256": tool_identity(), "scenarios": scenarios.registry()}, indent=2))
            return 0
        job = Job(Path(args.project).resolve(strict=True), args.command, Path(args.beryl).resolve(strict=True))
        if args.command in ("check", "build"):
            if args.artifact or args.stage or args.scenario or args.scenario_count is not None or args.scenario_case is not None or args.measurement_plan is not None or args.destination or args.workbench_tools:
                raise Failure("Options do not apply to check/build")
            config, inputs, hashes = job.snapshot()
            checks(job, config, inputs)
            job.unchanged(hashes)
            if args.command == "build":
                build(job, config, inputs, hashes)
        elif args.command == "verify":
            if args.destination:
                raise Failure("--destination applies only to promotion")
            verify(job, args)
        else:
            promote(job, args)
        job.result["status"] = "success"
    except (Failure, OSError, ValueError, KeyError, TypeError, RecursionError, KeyboardInterrupt) as exc:
        result = job.result if job else {"schema_version": 1, "operation": "mod " + args.command, "stage": "startup", "diagnostics": []}
        result["status"] = "cancelled" if isinstance(exc, KeyboardInterrupt) else getattr(exc, "status", "failure")
        result["diagnostics"].append({"code": "BEM001", "message": str(exc), "source": "beryl.mod.json",
                                      "json_pointer": getattr(exc, "pointer", None), "help": "Repair the source/description or inspect the retained stage logs, then rebuild."})
        if args.command == "plan":
            result.update(stage="planning", execution="not_run", raw_logs=[], measurements=[])
            result["diagnostics"][-1]["help"] = "Repair the reported description/input and rerun plan. No compiler or engine checks were executed."
    else:
        result = job.result
    if job:
        write_json(job.path / "result.json", result)
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "success" else 1


if __name__ == "__main__":
    sys.exit(main())
