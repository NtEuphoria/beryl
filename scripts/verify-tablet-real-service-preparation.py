#!/usr/bin/env python3
"""Pure gates for the N1a preparer's expansion and truthful compile outcomes."""
from pathlib import Path
import ast
import copy
import hashlib
import json
import re
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "scripts/prepare-tablet-real-services.py"


def main():
    raw = SOURCE.read_bytes()
    if len(raw) > 64 * 1024:
        raise ValueError("Preparer exceeds source gate bound")
    tree = ast.parse(raw, str(SOURCE))
    nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in ("expanded", "classify_compile")]
    assert len(nodes) == 2 and {node.name for node in nodes} == {"expanded", "classify_compile"}
    scope = {"re": re}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(SOURCE), "exec"), scope)
    folder = ROOT / "build" / ("tablet-real-service-preparation-checkers-" + uuid.uuid4().hex)
    folder.mkdir()
    (folder / "preparer.py").write_bytes(raw)
    plans = []

    def expanded_ok():
        assert scope["expanded"](b"@STATE@ field;\n", {"STATE": "Beryl_State"}) == b"Beryl_State field;\n"

    plans.append(("expand.declaration-identity", expanded_ok))
    for name, text, symbols in (
        ("missing-placeholder", b"@UNKNOWN@", {"STATE": "Beryl_State"}),
        ("unsafe-whitespace", b"@STATE@", {"STATE": "class Bad"}),
        ("unsafe-punctuation", b"@STATE@", {"STATE": "X;"}),
        ("unsafe-empty", b"@STATE@", {"STATE": ""}),
        ("unsafe-leading-digit", b"@STATE@", {"STATE": "1State"}),
        ("invalid-utf8", b"\xff", {"STATE": "Beryl_State"}),
    ):
        def rejected(text=text, symbols=symbols):
            try:
                scope["expanded"](text, symbols)
            except (ValueError, UnicodeError):
                return
            raise AssertionError("Invalid expansion admitted")
        plans.append(("expand.reject." + name, rejected))

    valid = {"schema_version": 1, "stage": "workbench_compile", "result": {"Stage": "Compiled", "Ok": True, "ExitCode": 0, "ErrorCount": 0}}
    scenarios = [("success", valid, "executed_success")]
    failed = copy.deepcopy(valid)
    failed["result"].update(Ok=False, ExitCode=-1, ErrorCount=3)
    scenarios.append(("actual-script-failure", failed, "executed_failure"))
    for label, stage, outcome in (("startup-unavailable", "DidNotStart", "startup_unavailable"), ("timeout", "Timeout", "timeout_incomplete")):
        value = copy.deepcopy(valid)
        value["result"]["Stage"] = stage
        scenarios.append((label, value, outcome))
    for label, mutation in (
        ("wrong-schema", lambda value: value.update(schema_version=2)),
        ("boolean-schema", lambda value: value.update(schema_version=True)),
        ("wrong-stage", lambda value: value.update(stage="other")),
        ("missing-detail", lambda value: value.pop("result")),
        ("boolean-exitcode", lambda value: value["result"].update(ExitCode=False)),
        ("boolean-errorcount", lambda value: value["result"].update(ErrorCount=False)),
        ("numeric-ok", lambda value: value["result"].update(Ok=1)),
        ("unknown-stage", lambda value: value["result"].update(Stage="Unknown")),
        ("inconsistent-success-errors", lambda value: value["result"].update(ErrorCount=1)),
    ):
        value = copy.deepcopy(valid)
        mutation(value)
        scenarios.append((label, value, "attempted_unconfirmed"))

    for label, adapter, outcome in scenarios:
        def classified(adapter=adapter, outcome=outcome):
            record = {"status": "failure", "scope": {"engine_compilation": "attempted_unconfirmed"},
                      "raw_results": {"compile": {"result": copy.deepcopy(adapter)}}}
            before = copy.deepcopy(record["raw_results"])
            scope["classify_compile"](record)
            assert record["scope"]["engine_compilation"] == outcome
            assert record["status"] == "failure" and record["raw_results"] == before
        plans.append(("compile.classify." + label, classified))

    # Read the retained failed adapter, without modifying or reinterpreting its
    # immutable parent receipt. The new classification is a separate observation.
    old = ROOT / "build/tablet-real-services-preparation-ywo3u7mt/engine-compile.json"
    old_raw = old.read_bytes()
    old_adapter = json.loads(old_raw)
    def retained_failure():
        record = {"status": "failure", "scope": {"engine_compilation": "attempted_unconfirmed"}, "raw_results": {"compile": {"result": old_adapter}}}
        scope["classify_compile"](record)
        assert record["scope"]["engine_compilation"] == "executed_failure"
        assert old.read_bytes() == old_raw
    plans.append(("compile.retained-failure-readable", retained_failure))

    result = {"schema_version": 1, "operation": "verify.n1a_preparation_checkers", "scope": "AST-extracted Python helpers only",
              "host": "not_run", "engine": "not_run", "compiler": "not_run", "native": "not_run",
              "source_sha256": hashlib.sha256(raw).hexdigest(), "retained_failure": {"path": str(old), "sha256": hashlib.sha256(old_raw).hexdigest()},
              "expected_case_ids": [name for name, action in plans], "cases": []}
    for name, action in plans:
        try:
            action()
            row = {"id": name, "status": "success"}
        except BaseException as error:
            row = {"id": name, "status": "failure", "error": {"type": type(error).__name__, "message": str(error)}}
        result["cases"].append(row)
    result["passed"] = sum(row["status"] == "success" for row in result["cases"])
    result["failed"] = len(plans) - result["passed"]
    result["status"] = "success" if result["failed"] == 0 else "failure"
    assert SOURCE.read_bytes() == raw and old.read_bytes() == old_raw
    payload = json.dumps(result, sort_keys=True, indent=2).encode("ascii") + b"\n"
    path = folder / "result.json"
    with path.open("xb") as stream:
        assert stream.write(payload) == len(payload)
    assert path.read_bytes() == payload
    print(json.dumps({"result": str(path), "sha256": hashlib.sha256(payload).hexdigest(), "status": result["status"], "passed": result["passed"], "failed": result["failed"]}))
    return 0 if result["status"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
