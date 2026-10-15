#!/usr/bin/env python3
"""Experimental engine execution of the scalar tablet continuation corpus.

Prepare-only is the default. --run explicitly compiles and executes a separate
immutable fixture through the existing owned Workbench transport. Scripted
replies are fixture data: this does not exercise actual tablet services, engine
callback delivery, widgets, or multiplayer. Numeric equality is checked; the
engine's binary32 bit encoding and signed-zero distinction remain unverified.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import re
import shutil
import struct
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / "tools/beryl-mod"))
import mod

ENGINE_SHA = "7dd36ca1f662b0c13669a4f2f7f10e3c461c2906b021e742272d64b3ab7e9798"
VERSION = "1.8.0.13"
BRIDGE = ("Find-Workbench.ps1", "Invoke-ReforgerBuild.ps1", "Invoke-Workbench.ps1",
          "Get-WorkbenchErrors.ps1", "Start-WorkbenchDaemon.ps1", "Invoke-WorkbenchRpc.ps1")
FAILURE_STATUSES = {"failure", "unavailable", "stale_input", "timeout", "cancelled"}


def file_hash(path):
    import hashlib
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def tree(path):
    entries = sorted(path.rglob("*"))
    if len(entries) > 4096:
        raise mod.Failure("Fixture file-set limit exceeded", "unavailable")
    if path.is_symlink() or any(p.is_symlink() or (hasattr(p, "is_junction") and p.is_junction()) for p in entries):
        raise mod.Failure("Linked fixture input is not admitted", "stale_input")
    return {p.relative_to(path).as_posix(): file_hash(p) for p in entries if p.is_file()}


def load_corpus():
    path = ROOT / "scripts/verify-tablet-lifecycle.py"
    spec = importlib.util.spec_from_file_location("tablet_scalar_verifier", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for name, expected in module.PROVENANCE.items():
        if file_hash(module.RETAINED / name) != expected:
            raise mod.Failure("Retained tablet reference changed", "stale_input")
    cases = module.corpus()
    outputs = {}
    for case in cases:
        original = module.evaluate(case, "original")
        protocol = module.evaluate(case, "protocol")
        if module.observable(original) != module.observable(protocol):
            raise mod.Failure("Independent scalar oracle mismatch: " + case["id"])
        outputs[case["id"]] = protocol
    return module, cases, outputs


def identifier(name):
    if type(name) is not str or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
        raise mod.Failure("Invalid compiler-published linkage identifier")
    return name


def emit_replay(mapping, cases, outputs, token):
    if mapping.get("linkage_schema_version") != 1:
        raise mod.Failure("Compiler linkage unavailable", "unavailable")
    links = mapping["linkage"]
    def symbol(name, kind):
        items = [x for x in links if x["declaration"] == "sparkos.tablet_lifecycle_prototype." + name and x["kind"] == kind]
        if len(items) != 1:
            raise mod.Failure("Missing/ambiguous compiler linkage for " + name)
        return items[0]
    state, operation, function = symbol("State", "struct"), symbol("Operation", "struct"), symbol("next", "function")
    state_type, operation_type = identifier(state["class"]), identifier(operation["class"])
    fn = identifier(function["holder"]) + "." + identifier(function["method"])
    def fields(item, expected):
        rows = item["fields"]
        if len(rows) != len(expected) or {x["source"] for x in rows} != set(expected):
            raise mod.Failure("Unexpected state/operation fields")
        return {x["source"]: identifier(x["name"]) for x in rows}
    sf = fields(state, ("mode", "telemetry_accumulator"))
    of = fields(operation, ("kind", "pc", "screen_pc", "held", "time_slice", "answer"))
    def number(value):
        # Nine significant decimal digits round-trip a finite binary32 value.
        result = format(value, ".9g")
        if "e" not in result and "." not in result:
            result += ".0"
        return result
    def scalar_bits(value):
        return number(struct.unpack("<f", struct.pack("<I", value))[0])
    lines = ["// Installed experimental fixture, generated from frozen scalar transcripts.",
             "class BerylTabletReplayRequest : JsonApiStruct {",
             " string token; void BerylTabletReplayRequest() { RegV(\"token\"); }", "}",
             "class BerylTabletReplayResponse : JsonApiStruct {",
             " string token; int executed; ref array<string> rows = {};",
             " void BerylTabletReplayResponse() { RegV(\"token\"); RegV(\"executed\"); RegV(\"rows\"); }", "}",
             "class BerylTabletReplay : NetApiHandler {",
             " override JsonApiStruct GetRequest() { return new BerylTabletReplayRequest(); }",
             " override JsonApiStruct GetResponse(JsonApiStruct request) {",
             "  BerylTabletReplayRequest req = BerylTabletReplayRequest.Cast(request);",
             "  BerylTabletReplayResponse result = new BerylTabletReplayResponse();",
             f'  result.token = "{token}";',
             "  if (!req || req.token != result.token) return result;"]
    expected = []
    for index, case in enumerate(cases):
        lines.append(f"  Case{index}(result);")
        count = sum(s["event"] == "step" for s in outputs[case["id"]]["steps"])
        expected.append(case["id"] + "|" + str(count) + "|numeric-pass")
    lines += ["  result.executed = 1; return result;", " }"]
    assertions = 0
    calls = 0
    for index, case in enumerate(cases):
        transcript = outputs[case["id"]]["steps"]
        lines += [f" void Case{index}(BerylTabletReplayResponse result) {{",
                  f"  {state_type} state = new {state_type}();",
                  f"  state.{sf['mode']} = {case['mode']};",
                  f"  state.{sf['telemetry_accumulator']} = {number(case['accumulator'])};", "  bool passed = true;", "  int code;"]
        active = {}
        declared_operations = set()
        count = 0
        for sequence, step in enumerate(transcript):
            if step.get("seq") != sequence:
                raise mod.Failure("Incomplete ordered transcript")
            name = "operation" + str(step["id"])
            if step["event"] == "begin":
                if name in active:
                    raise mod.Failure("Duplicate active operation")
                if name in declared_operations or len(declared_operations) >= 56:
                    raise mod.Failure("Replay operation-local variable budget exceeded", "unavailable")
                declared_operations.add(name)
                active[name] = None
                op = step["operation"]
                lines += [f"  {operation_type} {name} = new {operation_type}();",
                          f"  {name}.{of['kind']} = {op['kind']};",
                          f"  {name}.{of['held']} = {str(op['held']).lower()};",
                          f"  {name}.{of['time_slice']} = {number(op['time_slice'])};"]
            elif step["event"] == "step":
                if name not in active or step["reply"] not in (0, 1) or not 0 <= step["opcode"] <= 19:
                    raise mod.Failure("Unknown operation/reply/opcode")
                op = step["operation"]
                lines.append(f"  code = {fn}(state, {name}, {step['reply']});")
                conditions = [f"code == {step['opcode']}", f"state.{sf['mode']} == {step['mode']}",
                              f"{name}.{of['pc']} == {op['pc']}", f"{name}.{of['screen_pc']} == {op['screen_pc']}",
                              f"{name}.{of['answer']} == {str(op['answer']).lower()}",
                              f"state.{sf['telemetry_accumulator']} == {scalar_bits(step['accumulator_bits'])}"]
                lines.append("  if (!(" + " && ".join(conditions) + ")) passed = false;")
                active[name] = step
                count += 1
                calls += 1
                assertions += len(conditions)
            elif step["event"] == "end":
                last = active.pop(name, None)
                if not last or last["opcode"] != 0 or last["operation"]["pc"] != 999 or last["operation"]["answer"] != step["answer"]:
                    raise mod.Failure("Missing completion/wrong outcome")
            else:
                raise mod.Failure("Unknown replay record")
        if active:
            raise mod.Failure("Incomplete operation transcript")
        prefix = case["id"] + "|" + str(count) + "|"
        lines += [f'  if (passed) result.rows.Insert("{prefix}numeric-pass");',
                  f'  else result.rows.Insert("{prefix}numeric-FAIL");', " }"]
    lines.append("}")
    return ("\n".join(lines) + "\n").encode(), expected, calls, assertions


def validate_response(response, token, expected):
    if (type(response) is not dict or set(response) != {"token", "executed", "rows"} or
            response["token"] != token or type(response["executed"]) is not int or response["executed"] != 1 or
            response["rows"] != expected):
        raise mod.Failure("Stale, incomplete, unordered or semantically mismatched tablet replay response")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--beryl", type=Path, required=True)
    parser.add_argument("--expect-compiler-sha256", required=True)
    parser.add_argument("--workbench-tools", type=Path, required=True)
    parser.add_argument("--engine", type=Path, required=True)
    parser.add_argument("--powershell-host", type=Path, required=True)
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args()
    compiler = args.beryl.resolve(strict=True)
    if compiler.parent == ROOT / "build" or not compiler.is_relative_to(ROOT / "build"):
        raise mod.Failure("Private compiler candidate required")
    if file_hash(compiler) != args.expect_compiler_sha256:
        raise mod.Failure("Compiler changed", "stale_input")
    engine, tools, host = args.engine.resolve(strict=True), args.workbench_tools.resolve(strict=True), args.powershell_host.resolve(strict=True)
    if file_hash(engine) != ENGINE_SHA:
        raise mod.Failure("Engine differs from reviewed binding", "stale_input")
    verifier, cases, outputs = load_corpus()
    work = Path(tempfile.mkdtemp(prefix="tablet-engine-replay-", dir=ROOT / "build"))
    project = work / "source"
    project.mkdir()
    (project / "lifecycle.be").write_bytes(verifier.SOURCE.read_bytes())
    token = mod.digest(mod.canonical({"source": file_hash(verifier.SOURCE), "script": file_hash(Path(__file__)),
                                     "corpus": mod.digest(mod.canonical(outputs)), "job": work.name}))
    config = {"schema_version": 1, "name": "Beryl scalar tablet engine replay; no live services",
              "addon": {"id": "BerylTabletReplay", "guid": token[:16].upper(), "dependencies": ["58D0FB3206B6F859"]},
              "binding": {"target": "enfusion", "version": VERSION},
              "sources": {"native": ["lifecycle.be"], "enfusion": ["lifecycle.be"], "tests": []}, "exports": []}
    mod.write_json(project / "beryl.mod.json", config)
    frozen = {str(p): file_hash(p) for p in [compiler, engine, host, Path(__file__), ROOT / "scripts/verify-tablet-lifecycle.py",
              verifier.SOURCE, verifier.PACKAGE / "oracle.py", verifier.PACKAGE / "protocol_model.py",
              *[tools / "scripts" / n for n in BRIDGE], *mod.bundle_paths()]}
    job = mod.Job(work, "experimental.tablet_engine_replay", compiler)
    record = {"schema_version": 1, "operation": "experimental.tablet_engine_replay", "status": "failure",
              "scope": "numeric scalar continuation replay with scripted replies; no actual services or engine callback delivery",
              "runtime": "not_run", "callback_delivery": "not_run", "tablet_services": "not_run", "promotion": "not_run",
              "floating_encoding": "unavailable; numeric equality only, signed zero excluded from engine equivalence",
              "frozen": frozen, "token": token, "corpus_sha256": mod.digest(mod.canonical(outputs)), "case_ids": [c["id"] for c in cases]}
    addon = work / "addon"
    staged = None
    artifact = None
    artifact_hashes = None
    source_hashes = tree(project)
    def project_inputs():
        return {p.relative_to(project).as_posix(): file_hash(p) for p in sorted(project.rglob("*"))
                if p.is_file() and ".beryl-mod" not in p.relative_to(project).parts}
    def unchanged():
        if any(file_hash(Path(p)) != h for p, h in frozen.items()) or project_inputs() != source_hashes:
            raise mod.Failure("Fixture/tool/source input changed", "stale_input")
        if artifact is not None and tree(artifact) != artifact_hashes:
            raise mod.Failure("Immutable original artifact changed", "stale_input")
        if staged is not None:
            actual = tree(addon)
            # Workbench creates this documented-by-log resource cache at startup.
            # It is derived output, never an authoring input or an accepted extra.
            cache = "resourceDatabase.rdb"
            outputs = []
            if cache in actual and cache not in staged:
                path = addon / cache
                if path.stat().st_size > 8 * 1024 * 1024:
                    raise mod.Failure("Engine resource-cache output exceeds fixture bound", "unavailable")
                outputs.append({"path": str(path), "bytes": path.stat().st_size, "sha256": actual.pop(cache)})
            record["engine_generated_outputs"] = outputs
            if actual != staged:
                raise mod.Failure("Staged fixture changed", "stale_input")
    print("Tablet engine replay evidence:", work, flush=True)
    try:
        unchanged()
        # Explicit installed orchestration, not arbitrary project scripts.
        built_raw = job.run([sys.executable, mod.HERE / "mod.py", "build", "--project", project, "--beryl", compiler], "generate", work, 90)
        built = mod.parse(built_raw)
        if built.get("status") != "success":
            raise mod.Failure("Source generation did not succeed")
        artifact = Path(built["artifact_path"]).resolve(strict=True)
        manifest = mod.parse(mod.read(artifact / "artifact.json"))
        domain = {k: v for k, v in manifest.items() if k not in ("id", "artifact_sha256")}
        if mod.digest(mod.canonical(domain)) != built["artifact_sha256"] or manifest["artifact_sha256"] != built["artifact_sha256"]:
            raise mod.Failure("Original artifact identity mismatch")
        if manifest["compiler_sha256"] != args.expect_compiler_sha256 or manifest["tool_sha256"] != mod.tool_identity() or manifest["inputs"] != source_hashes:
            raise mod.Failure("Artifact has mismatched source/compiler/tool identities")
        expected_files = {"addon/" + name: value for name, value in manifest["files"].items()}
        expected_files.update(manifest["sidecars"])
        actual_files = tree(artifact)
        if {k: v for k, v in actual_files.items() if k != "artifact.json"} != expected_files:
            raise mod.Failure("Artifact file set/hashes differ from manifest")
        mapping = mod.parse(mod.read(artifact / "source-map.json"))
        artifact_hashes = tree(artifact)
        shutil.copytree(artifact / "addon", addon)
        if tree(addon) != manifest["files"]:
            raise mod.Failure("Copied generated addon differs from manifest", "stale_input")
        generated, expected, calls, assertions = emit_replay(mapping, cases, outputs, token)
        target = addon / "scripts/WorkbenchGameCommon/BerylTabletReplay.c"
        target.parent.mkdir(parents=True)
        if target.write_bytes(generated) != len(generated) or file_hash(target) != mod.digest(generated):
            raise mod.Failure("Incomplete fixture write")
        staged = {**manifest["files"], target.relative_to(addon).as_posix(): mod.digest(generated)}
        if tree(addon) != staged:
            raise mod.Failure("Unexpected staged fixture bytes/file set", "stale_input")
        record.update(artifact_path=str(artifact), artifact_sha256=built["artifact_sha256"], artifact_files=artifact_hashes,
                      staged_files=staged, expected_rows=expected, calls=calls, assertions=assertions,
                      expected_sha256=mod.digest(mod.canonical(expected)), generated_fixture=str(target))
        mod.write_json(work / "transcripts.json", outputs)
        record["transcript_file_sha256"] = file_hash(work / "transcripts.json")
        frozen[str(work / "transcripts.json")] = record["transcript_file_sha256"]
        unchanged()
        if not args.run:
            record.update(status="success", stage="prepared", execution="not_run")
            job.result.update(status="success", stage="prepared")
            return
        for adapter, stage, parameters, timeout in (
            ("engine-compile.ps1", "compile", ["-ExpectedVersion", VERSION, "-TimeoutSeconds", "120"], 150),
            ("scenario-engine-run.ps1", "runtime", ["-ProjectId", "BerylTabletReplay", "-Token", token,
                  "-Function", "BerylTabletReplay", "-ExpectedEngineHash", ENGINE_SHA, "-ExpectedEngineVersion", VERSION], 240)):
            unchanged()
            result_path = work / (stage + ".json")
            record["stage"] = stage
            if stage == "runtime":
                record["runtime"] = "attempted"
            job.run([host, "-NoProfile", "-File", mod.HERE / adapter, "-ToolRoot", tools, "-ProjectDir", addon,
                     "-ResultPath", result_path, *parameters], stage, work, timeout)
            result = mod.parse(mod.read(result_path))
            record["runtime_result" if stage == "runtime" else stage] = result
            record.setdefault("raw_result_receipts", {})[stage] = {"path": str(result_path), "sha256": file_hash(result_path)}
            expected_stage = "workbench_compile" if stage == "compile" else "scenario_engine_execution"
            if (result.get("schema_version") != 1 or result.get("stage") != expected_stage or
                    result.get("status") != "success" or result["engine_sha256"] != ENGINE_SHA or result["engine_version"] != VERSION):
                raise mod.Failure("Incomplete engine " + stage + " receipt")
            if stage == "compile":
                detail = result["result"]
                if (detail.get("Stage") != "Compiled" or detail.get("Ok") is not True or detail.get("ExitCode") != 0 or detail.get("ErrorCount") != 0 or
                        result.get("tools") != {name: frozen[str(tools / "scripts" / name)] for name in BRIDGE[:4]} or
                        not detail.get("LogDir") or not list(Path(detail["LogDir"]).glob("*.log"))):
                    raise mod.Failure("Incomplete compile outcome")
            else:
                if (result.get("rpc", {}).get("Ok") is not True or result.get("session", {}).get("reused") is not False or
                        result["session"].get("project") != str(addon) or
                        result.get("loaded_projects", {}).get("Ok") is not True or
                        "BerylTabletReplay" not in result["loaded_projects"].get("Response", {}).get("Loaded Projects", [])):
                    raise mod.Failure("Incomplete or unrelated engine session receipt")
                validate_response(result["rpc"]["Response"], token, expected)
            unchanged()
        record.update(status="success", stage="engine_numeric_replay", runtime="success", execution="engine_executed")
        job.result.update(status="success", stage="engine_numeric_replay")
        print(f"Engine numeric replay passed: {len(cases)} cases / {calls} calls / {assertions} checks", flush=True)
    except BaseException as exc:
        failed_status = "cancelled" if isinstance(exc, KeyboardInterrupt) else getattr(exc, "status", "failure")
        record.update(status=failed_status if failed_status in FAILURE_STATUSES else "failure", error=repr(exc))
        job.result.update(status=record["status"])
        for stage in ("compile", "runtime"):
            path = work / (stage + ".json")
            if path.is_file():
                detail = mod.parse(mod.read(path))
                record["runtime_result" if stage == "runtime" else stage] = detail
                record.setdefault("raw_result_receipts", {})[stage] = {"path": str(path), "sha256": file_hash(path)}
                if detail.get("status") in FAILURE_STATUSES:
                    record["status"] = job.result["status"] = detail["status"]
        raise
    finally:
        compiled = record.get("compile", {}).get("result") or {}
        log_dir = compiled.get("LogDir")
        record["raw_engine_logs"] = []
        try:
            if log_dir and Path(log_dir).is_dir():
                for path in sorted(Path(log_dir).glob("*.log")):
                    original_hash = file_hash(path)
                    target = work / "logs" / path.name
                    target.parent.mkdir(exist_ok=True)
                    with path.open("rb") as source, target.open("xb") as dest:
                        shutil.copyfileobj(source, dest, 1024 * 1024)
                    if file_hash(target) != original_hash or file_hash(path) != original_hash:
                        raise mod.Failure("Raw engine log changed during capture", "stale_input")
                    record["raw_engine_logs"].append({"path": str(target), "sha256": original_hash})
            if record["status"] == "success" and args.run and not record["raw_engine_logs"]:
                raise mod.Failure("Raw engine compile logs unavailable")
        except BaseException as exc:
            record["log_capture_error"] = repr(exc)
            if record["status"] == "success":
                status = getattr(exc, "status", "failure")
                record["status"] = status if status in FAILURE_STATUSES else "failure"
                job.result["status"] = record["status"]
        for raw in job.result["raw_logs"]:
            for key in ("stdout", "stderr"):
                path = Path(raw[key])
                if path.is_file():
                    raw[key + "_sha256"] = file_hash(path)
        mod.write_json(Path(job.result["result_path"]), job.result)
        record["job"] = job.result
        record["job_receipt_sha256"] = file_hash(Path(job.result["result_path"]))
        mod.write_json(work / "result.json", record)
        print("Evidence:", work / "result.json", flush=True)


if __name__ == "__main__":
    main()
