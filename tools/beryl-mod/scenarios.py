"""Installed typed scenario definitions and receipt validation.

The map scenario compares real engine enumeration on bounded histories. It does
not measure traversal speed or establish iterator validity during mutation.
"""
from pathlib import Path
import re
import shutil

CASE_IDS = ("empty", "insert", "replace", "remove", "reinsert", "reverse_insert")
UNAVAILABLE = ("trace.mesh.query",
               "trace.mesh.sensor", "trace.mesh.expiry")


def registry():
    import terrain_scenarios
    import storage_scenarios
    import terrain_measurements
    return [{"name": "probe.map.cursor", "implementation": "implemented",
             "runtime_status": "requires execution for the selected engine/artifact",
             "count": {"type": "integer", "minimum": 1, "maximum": 4096, "default": 64},
             "case_ids": list(CASE_IDS), "case_selection": "nonempty unique ordered subset; default all",
             "evidence_scope": "ordered string-key/reference enumeration after mutations; no active-cursor mutation or performance claim"},
            terrain_scenarios.registry(), *storage_scenarios.registry(), terrain_measurements.registry(), *[{"name": name, "implementation": "unavailable"} for name in UNAVAILABLE]]


def parameters(api, args):
    if args.scenario == "measure.terrain.construction":
        import terrain_measurements
        return terrain_measurements.parameters(api, args)
    if getattr(args, "measurement_plan", None) is not None:
        raise api.Failure("--measurement-plan applies only to measure.terrain.construction")
    if args.scenario in ("probe.array.storage", "probe.canvas.retention"):
        import storage_scenarios
        return storage_scenarios.parameters(api, args)
    if args.scenario == "compare.terrain.chunks":
        import terrain_scenarios
        return terrain_scenarios.parameters(api, args)
    if args.scenario != "probe.map.cursor":
        raise api.Failure("Scenario is unknown or not implemented: " + args.scenario, "unavailable")
    if args.stage:
        raise api.Failure("Select a scenario or --stage compile, not both")
    if args.scenario_count and len(args.scenario_count) != 1:
        raise api.Failure("--scenario-count must occur once")
    count = args.scenario_count[0] if args.scenario_count else 64
    if type(count) is not int or not 1 <= count <= 4096:
        raise api.Failure("Scenario count must be an integer from 1 to 4096")
    selected = args.scenario_case if args.scenario_case is not None else list(CASE_IDS)
    if not selected or len(selected) != len(set(selected)) or any(name not in CASE_IDS for name in selected):
        raise api.Failure("Scenario cases must be a nonempty unique subset of " + ", ".join(CASE_IDS))
    return {"count": count, "case_ids": selected}


def expected_entries(case, count):
    if case == "empty":
        return {}
    entries = {"entity:" + str(i): i + 1 for i in range(count)}
    if case == "replace":
        entries.update({"entity:" + str(i): count + i + 1 for i in range(0, count, 2)})
    if case in ("remove", "reinsert"):
        for i in range(0, count, 2):
            del entries["entity:" + str(i)]
    if case == "reinsert":
        entries.update({"entity:" + str(i): 2 * count + i + 1 for i in range(0, count, 2)})
    return entries


def validate_wire(api, response, token, case_ids, expected_checks, expected_rows):
    required = {"token", "executed", "checks", "failures", "checksum", "caseIds", "rows"}
    if type(response) is not dict or set(response) != required:
        raise api.Failure("Missing or unknown scenario response fields")
    if response["token"] != token:
        raise api.Failure("Scenario compiled token differs", "stale_input")
    for name in ("executed", "checks", "failures", "checksum"):
        if type(response[name]) is not int:
            raise api.Failure("Scenario numeric response has the wrong type: " + name)
    if response["executed"] != 1 or response["failures"] != 0:
        raise api.Failure("Scenario did not complete successfully")
    if response["caseIds"] != case_ids:
        raise api.Failure("Scenario case selection is missing, duplicated, reordered or unexpected")
    rows = response["rows"]
    if response["checks"] != expected_checks or type(rows) is not list or len(rows) != expected_rows:
        raise api.Failure("Scenario check/trace counts are incomplete")
    checksum = 0
    for row in rows:
        if type(row) is not str or len(row) > 256 or not row.isascii():
            raise api.Failure("Scenario trace record has the wrong type or exceeds its bound")
        for value in (row + "\n").encode("ascii"):
            checksum = (checksum * 31 + value) % 1000003
    if checksum != response["checksum"]:
        raise api.Failure("Scenario trace checksum mismatch")
    return rows, checksum


def validate_response(api, response, token, params):
    expected = {case: expected_entries(case, params["count"]) for case in params["case_ids"]}
    expected_checks = sum(1 + len(entries) for entries in expected.values())
    expected_rows = sum(2 + len(entries) for entries in expected.values())
    rows, checksum = validate_wire(api, response, token, params["case_ids"], expected_checks, expected_rows)
    offset = 0
    for case, entries in expected.items():
        n = len(entries)
        if rows[offset] != f"case|{case}|{n}" or rows[offset + n + 1] != f"end|{case}|{n}":
            raise api.Failure("Scenario case boundaries differ")
        seen = set()
        for index in range(n):
            fields = rows[offset + index + 1].split("|")
            if len(fields) != 8 or fields[:3] != ["entry", case, str(index)]:
                raise api.Failure("Malformed or out-of-order scenario entry")
            key, cursor_key, serial, cursor_serial, same = fields[3:]
            if key not in entries or key in seen or cursor_key != key or same != "1":
                raise api.Failure("Map cursor differs from indexed keys/reference identity")
            if serial != str(entries[key]) or cursor_serial != serial:
                raise api.Failure("Map contents differ from independent history fixture")
            seen.add(key)
        if seen != set(entries):
            raise api.Failure("Scenario omitted map entries")
        offset += n + 2
    trace = ("\n".join(rows) + "\n").encode("ascii")
    return trace, {"checks": expected_checks, "events": expected_rows,
                   "case_ids": params["case_ids"], "checksum": checksum,
                   "checksum_algorithm": "polynomial31_mod1000003_ascii_lf",
                   "sha256": api.digest(trace)}


def plugin_hashes(api, toolroot):
    paths = sorted((toolroot / "scripts").glob("*.ps1"))
    if not paths:
        raise api.Failure("Installed Workbench scripts unavailable", "unavailable")
    return {path.name: api.digest(api.read(path)) for path in paths}


def run(api, job, args, path, artifact):
    params = parameters(api, args)
    if not args.workbench_tools:
        raise api.Failure("Scenario execution requires --workbench-tools", "unavailable")
    toolroot = Path(args.workbench_tools).resolve(strict=True)
    integrations = plugin_hashes(api, toolroot)
    config = api.parse(api.read(job.project / "beryl.mod.json"))
    token = api.digest(api.canonical({"scenario": args.scenario, "parameters": params, "operation_id": job.id,
        "artifact": artifact["artifact_sha256"], "tool": job.result["tool_sha256"],
        "integration": integrations}))
    class_name = "BerylScenario_" + token[:16]
    addon = job.path / "candidate"
    shutil.copytree(path / "addon", addon)
    validator = validate_response
    metadata = {"scope": "bounded ordered map enumeration; no performance or active-cursor mutation guarantee"}
    if args.scenario == "measure.terrain.construction":
        import terrain_measurements
        sources, metadata = terrain_measurements.sources(api, class_name, token, params)
        validator = terrain_measurements.validate_response
        api.write_json(job.path / "measurement-plan.json", params["plan"])
    elif args.scenario in ("probe.array.storage", "probe.canvas.retention"):
        import storage_scenarios
        sources, metadata = storage_scenarios.sources(api, class_name, token, params)
        validator = storage_scenarios.validate_response
    elif args.scenario == "compare.terrain.chunks":
        import terrain_scenarios
        sources, metadata = terrain_scenarios.sources(api, class_name, token, params)
        validator = terrain_scenarios.validate_response
    else:
        source = api.read(api.HERE / "map-cursor.c.in").decode("utf-8")
        calls = [f'if (!RunCase("{name}", {CASE_IDS.index(name)}, {params["count"]})) return m_Result;' for name in params["case_ids"]]
        source = source.replace("@CLASS@", class_name).replace("@TOKEN@", token).replace("@RUN@", "\n".join(calls))
        sources = {"scripts/WorkbenchGameCommon/" + class_name + ".c": source}
    for name, source in sources.items():
        handler = api.safe_path(addon, name)
        handler.parent.mkdir(parents=True, exist_ok=True)
        with handler.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(source)
    staged = {str(p.relative_to(addon)).replace("\\", "/"): api.digest(api.read(p))
              for p in sorted(addon.rglob("*")) if p.is_file()}
    staged_hash = api.digest(api.canonical(staged))
    job.result.update(scenario=args.scenario, scenario_parameters=params, compiled_token=token,
                      staged_artifact_sha256=staged_hash, integration_tool_sha256=api.digest(api.canonical(integrations)))
    api.write_json(job.path / "scenario-candidate.json", {"token": token, "files": staged, "parameters": params,
                   "artifact_sha256": artifact["artifact_sha256"], "staged_artifact_sha256": staged_hash,
                   "integration_files": integrations, "scenario_contract": metadata})
    compile_path, runtime_path = job.path / "scenario-compile.json", job.path / "scenario-runtime.json"
    try:
        job.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", api.HERE / "engine-compile.ps1",
                 "-ToolRoot", toolroot, "-ProjectDir", addon, "-ResultPath", compile_path,
                 "-ExpectedVersion", artifact["binding"]["version"]], "scenario_compile", job.path, 300)
    except api.Failure as exc:
        if compile_path.is_file():
            failed = api.parse(api.read(compile_path))
            api.engine_diagnostics(job, path, artifact, failed, addon)
            raise api.engine_failure(exc, failed) from exc
        raise
    compiled = api.parse(api.read(compile_path))
    api.engine_diagnostics(job, path, artifact, compiled, addon)
    if (compiled.get("stage") != "workbench_compile" or compiled.get("result", {}).get("Ok") is not True or
            compiled.get("engine_version") != artifact["binding"]["version"]):
        raise api.Failure("Scenario compilation did not establish expected engine identity")
    engine_hash = compiled.get("engine_sha256", "")
    if not re.fullmatch("[0-9a-f]{64}", engine_hash):
        raise api.Failure("Scenario compilation omitted engine content hash")
    try:
        runtime_args = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", api.HERE / "scenario-engine-run.ps1",
                 "-ToolRoot", toolroot, "-ProjectDir", addon, "-ProjectId", config["addon"]["id"], "-ResultPath", runtime_path,
                 "-Token", token, "-Function", class_name, "-ExpectedEngineHash", engine_hash,
                 "-ExpectedEngineVersion", compiled["engine_version"]]
        if args.scenario == "measure.terrain.construction":
            runtime_args += ["-RpcTimeoutMs", "240000"]
        job.run(runtime_args, "scenario_execution", job.path, 300)
    except api.Failure as exc:
        if runtime_path.is_file():
            failed = api.parse(api.read(runtime_path))
            job.result["scenario_runtime"] = failed
            raise api.engine_failure(exc, failed) from exc
        raise
    runtime = api.parse(api.read(runtime_path))
    if (runtime.get("stage") != "scenario_engine_execution" or runtime.get("status") != "success" or runtime.get("engine_sha256") != engine_hash or
            runtime.get("engine_version") != compiled["engine_version"] or runtime.get("rpc", {}).get("Ok") is not True):
        raise api.Failure("Missing matching engine execution evidence")
    trace, summary = validator(api, runtime["rpc"]["Response"], token, params)
    api.load_artifact(job, args.artifact)
    if plugin_hashes(api, toolroot) != integrations:
        raise api.Failure("Integration tools changed during scenario", "stale_input")
    actual = {str(p.relative_to(addon)).replace("\\", "/"): api.digest(api.read(p))
              for p in sorted(addon.rglob("*")) if p.is_file() and p.relative_to(addon).as_posix() != "resourceDatabase.rdb"}
    if actual != {name: value for name, value in staged.items() if name != "resourceDatabase.rdb"}:
        raise api.Failure("Staged scenario inputs changed during execution", "stale_input")
    trace_path = job.path / "scenario-trace.jsonl"
    # Each JSONL record preserves its exact ASCII source row; the wire checksum
    # and SHA above cover unescaped rows, while this file has its own SHA below.
    with trace_path.open("xb") as stream:
        for sequence, row in enumerate(trace.decode("ascii").splitlines()):
            stream.write(api.canonical({"schema_version": 1, "token": token, "sequence": sequence, "row": row}) + b"\n")
    receipt = {"schema_version": 1, "stage": "runtime_scenario", "status": "success", "scenario": args.scenario,
        "operation_id": job.id, "parameters": params, "compiled_token": token,
        "artifact_sha256": artifact["artifact_sha256"], "staged_artifact_sha256": staged_hash,
        "source_sha256": artifact["source_sha256"], "compiler_sha256": artifact["compiler_sha256"],
        "tool_sha256": job.result["tool_sha256"], "integration_files": integrations,
        "engine_sha256": engine_hash, "engine_version": compiled["engine_version"], "trace": summary,
        "raw_results": {str(p): api.digest(api.read(p)) for p in (compile_path, runtime_path, trace_path)},
        "scenario_contract": metadata, "scope": metadata["scope"]}
    api.write_json(path / ("scenario-" + job.id + ".json"), receipt)
    job.result.update(stage="runtime_scenario", scenario_receipt=receipt, binding_status="engine version/hash and selected probe verified")
