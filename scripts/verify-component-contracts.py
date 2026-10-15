#!/usr/bin/env python3
"""Pure-Python P4-A admission regressions. No compiler/engine/program execution."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import traceback

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent.parent
HERE = ROOT / "tools/beryl-mod"
sys.path.insert(0, str(HERE))
import component_contracts as contracts
import mod as schema_api


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def identity(kind, name):
    return hashlib.sha256(("beryl.declaration.v1:" + kind + ":" + name).encode()).hexdigest()


def scalar(name):
    return {"name": name, "declaration": None}


def named(name):
    return {"name": name, "declaration": name}


def location():
    return {"path": "synthetic/tablet.be", "byte_offset": 0, "byte_length": 0,
            "line": 1, "column": 1, "column_unit": "byte", "text": "synthetic; no body evidence"}


def record(name, fields, visibility="public"):
    return {"declaration_id": identity("struct", name), "qualified_name": name,
            "name": name.rsplit(".", 1)[-1], "kind": "struct", "visibility": visibility,
            "source": location(), "generic_parameters": [],
            "fields": [{"name": key, "type": ty} for key, ty in fields]}


def function(name, state, frame=False):
    parameters = [{"name": "state", "access_mode": "inout", "is_self": False,
                   "type": named(state), "default": None}]
    if frame:
        parameters.append({"name": "any_time_name", "access_mode": "let", "is_self": False,
                           "type": scalar("f32"), "default": None})
    return {"declaration_id": identity("function", name), "qualified_name": name,
            "name": name.rsplit(".", 1)[-1], "kind": "function", "visibility": "public",
            "source": location(), "receiver": None, "generic_parameters": [],
            "return_type": scalar("void"), "parameters": parameters}


def context(config):
    component = config["components"][0]
    state = component["state"]
    declarations = [record(state, [("ready", scalar("bool")), ("state", scalar("i32")), ("elapsed", scalar("f32"))])]
    declarations += [function(c["handler"], state, c["binding"].endswith("EOnFrame")) for c in component["callbacks"]]
    return {"schema_version": 1, "operation": "context.project", "stage": "context", "status": "success",
            "execution": "not_run", "diagnostics": [], "compiler_fingerprint": "1" * 64,
            "source_fingerprint": "2" * 64, "data": {"declarations": declarations}}


def change(value, path, replacement):
    target = value
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = replacement
    return value


def fail(call, pointer, status="failure"):
    try:
        call()
    except (contracts.ContractFailure, schema_api.Failure) as exc:
        assert exc.pointer == pointer, (str(exc), exc.pointer, pointer)
        assert exc.status == status, (str(exc), exc.status, status)
        assert str(exc)
        return
    raise AssertionError("Invalid admission unexpectedly succeeded")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.output:
        work = args.output.resolve()
        if not work.is_relative_to((ROOT / "build").resolve()):
            parser.error("Evidence output must be a new directory under build")
        work.mkdir(parents=True, exist_ok=False)
    else:
        work = Path(tempfile.mkdtemp(prefix="component-contracts-", dir=ROOT / "build"))
    paths = [Path(__file__), HERE / "component_contracts.py", HERE / "tablet-component-contracts.v1.json",
             HERE / "mod.py", ROOT / "schemas/beryl.mod.v1.schema.json", ROOT / "schemas/beryl.mod.v2.schema.json",
             ROOT / "packages/sparkos/tablet-admission/beryl.mod.json",
             ROOT / "packages/sparkos/tablet-admission/src/tablet.be", ROOT / "src/driver/context.c"]
    before = {str(p): sha(p) for p in paths}
    evidence = {"schema_version": 1, "operation": "verify_component_contracts", "status": "running",
                "input_hashes": before, "cases": [], "compiler_execution": "not_run",
                "engine_execution": "not_run", "program_execution": "not_run", "context_kind": "synthetic",
                "scope": "catalog, structure, schema and resolved-signature validation; no lifecycle evidence"}
    base = schema_api.parse((ROOT / "packages/sparkos/tablet-admission/beryl.mod.json").read_bytes())
    v1 = schema_api.parse((ROOT / "schemas/beryl.mod.v1.schema.json").read_bytes())
    v2 = schema_api.parse((ROOT / "schemas/beryl.mod.v2.schema.json").read_bytes())
    catalog = contracts.load_catalog(HERE / "tablet-component-contracts.v1.json", schema_api.read, schema_api.parse)
    ctx = context(base)
    actions = []

    def case(name, fn):
        actions.append((name, fn))

    def config_failure(name, path, replacement, pointer, status="failure"):
        case(name, lambda: fail(lambda: contracts.validate_components(change(copy.deepcopy(base), path, replacement), catalog), pointer, status))

    def context_failure(name, path, replacement, pointer="/components/0/callbacks/0/handler", status="failure"):
        case(name, lambda: fail(lambda: contracts.validate_symbols(base, catalog, change(copy.deepcopy(ctx), path, replacement)), pointer, status))

    def valid():
        schema_api.validate(base, v2, v2)
        a, b, c = copy.deepcopy(base), copy.deepcopy(catalog), copy.deepcopy(ctx)
        summary = contracts.validate_symbols(a, b, c)
        assert (a, b, c) == (base, catalog, ctx)
        assert summary["status"] == "admitted_signatures"
        assert summary["availability"]["symbols"] == "admitted"
        assert summary["availability"]["targets"] == "not_checked"
        assert summary["availability"]["generation"] == "unavailable"
        assert summary["availability"]["runtime_verification"] == "not_run"
        assert summary["handler_body_and_lifecycle"] == "not_verified"
        assert summary["unresolved_contracts"] == catalog["unknown_contracts"]
        assert len(summary["components"][0]["callbacks"]) == 3
        assert summary["components"][0]["resolved_state"]["expanded_fields"] == 3
        assert "text" not in summary["components"][0]["resolved_state"]["source"]
        (work / "synthetic-admission.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    case("exact profile/signatures; no lifecycle/runtime/generation claim", valid)

    def common():
        for key in ("name", "addon", "sources", "exports", "$schema"):
            assert v1["properties"][key] == v2["properties"][key]
        for key, node in v1["$defs"].items():
            assert v2["$defs"][key] == node
        for key in ("target", "version"):
            assert v2["properties"]["binding"]["properties"][key] == v1["properties"]["binding"]["properties"][key]
        fail(lambda: schema_api.validate(base, v1, v1), "")
        old = {k: copy.deepcopy(v) for k, v in base.items() if k != "components"}
        old["schema_version"] = 1
        old["binding"] = {k: v for k, v in old["binding"].items() if k in ("target", "version")}
        schema_api.validate(old, v1, v1)
        fail(lambda: contracts.validate_components(old, catalog), "/components")
    case("v1 common schema preserved and v2 fields never reinterpreted", common)

    for field in ("gadget", "properties", "resources", "ui", "scenarios", "generation", "scripts"):
        config_failure("unsupported top-level " + field, [field], [], "/" + field)
        case("v2 schema rejects " + field, lambda field=field: fail(lambda: schema_api.validate(change(copy.deepcopy(base), [field], []), v2, v2), ""))
    for role, parent in (("descriptor", "SCR_GadgetComponentClass"), ("instance", "SCR_GadgetComponent")):
        config_failure("wrong " + role + " parent", ["components", 0, role, "parent"], parent, "/components/0/" + role + "/parent")
    for version in (1, True, "2"):
        config_failure("strict version type " + repr(version), ["schema_version"], version, "/schema_version")
    config_failure("unresolved profile", ["binding", "contract_profile"], "enfusion.unknown.v1", "/binding/contract_profile", "unavailable")
    config_failure("stale engine version", ["binding", "version"], "1.8.0.14", "/binding/version", "stale_input")
    config_failure("stale engine hash", ["binding", "sha256"], "0" * 64, "/binding/sha256", "stale_input")
    config_failure("missing required engine hash", ["binding"], {k: v for k, v in base["binding"].items() if k != "sha256"}, "/binding/sha256")
    config_failure("empty components", ["components"], [], "/components")
    config_failure("over component limit", ["components"], [copy.deepcopy(base["components"][0])] * 17, "/components")
    config_failure("descriptor/instance collision", ["components", 0, "descriptor", "name"], base["components"][0]["instance"]["name"], "/components/0/instance/name")
    config_failure("engine base identity collision", ["components", 0, "instance", "name"], "ScriptComponent", "/components/0/instance/name")
    config_failure("export/component collision", ["exports"], [{"source": "fixture.Exported", "name": base["components"][0]["instance"]["name"], "methods": []}], "/components/0/instance/name")
    for field in ("name", "source"):
        exports = [{"source": "fixture.First", "name": "First", "methods": []}, {"source": "fixture.Second", "name": "Second", "methods": []}]
        exports[1][field] = exports[0][field]
        config_failure("duplicate export " + field, ["exports"], exports, "/exports/1/" + field)
    for field in ("name", "source"):
        methods = [{"source": "fixture.First.a", "name": "a"}, {"source": "fixture.First.b", "name": "b"}]
        methods[1][field] = methods[0][field]
        config_failure("duplicate exported method " + field, ["exports"], [{"source": "fixture.First", "name": "First", "methods": methods}], "/exports/0/methods/1/" + field)
    config_failure("missing callback", ["components", 0, "callbacks"], base["components"][0]["callbacks"][:2], "/components/0/callbacks")
    config_failure("duplicate callback", ["components", 0, "callbacks", 1, "binding"], "ScriptComponent.OnPostInit", "/components/0/callbacks/1/binding")
    config_failure("unknown callback", ["components", 0, "callbacks", 0, "binding"], "ScriptComponent.Invented", "/components/0/callbacks/0/binding", "unavailable")
    for i, order in enumerate(("last", "first", "none")):
        config_failure("wrong superclass order " + str(i), ["components", 0, "callbacks", i, "super_order"], order, "/components/0/callbacks/" + str(i) + "/super_order")
    config_failure("arbitrary engine code not accepted", ["components", 0, "callbacks", 0, "code"], "doAnything()", "/components/0/callbacks/0/code")
    config_failure("invalid Unicode JSON string", ["name"], "\ud800", "/name")
    config_failure("oversized JSON integer bounded", ["schema_version"], 1 << 1000, "/schema_version", "unavailable")

    def maximum():
        value = copy.deepcopy(base)
        value["components"] = []
        for i in range(16):
            item = copy.deepcopy(base["components"][0])
            item["descriptor"]["name"] = "FixtureClass" + str(i)
            item["instance"]["name"] = "Fixture" + str(i)
            value["components"].append(item)
        schema_api.validate(value, v2, v2)
        result = contracts.validate_symbols(value, catalog, ctx)
        assert len(result["components"]) == 16
        assert len(json.dumps(result).encode()) < contracts.MAX_SUMMARY_BYTES
    case("maximum component count with deterministic bounded summary", maximum)

    for key, value in (("status", "failure"), ("execution", "executed"), ("operation", "context.symbol"), ("schema_version", True), ("compiler_fingerprint", None), ("source_fingerprint", "bad"), ("diagnostics", [{"message": "failure"}]), ("data", None)):
        pointer = "/context/data/declarations" if key == "data" else "/context/" + key
        context_failure("reject incomplete/failed context " + key, [key], value, pointer, "unavailable")
    context_failure("duplicate context declaration", ["data", "declarations"], ctx["data"]["declarations"] + [ctx["data"]["declarations"][0]], "/context/data/declarations/4", "unavailable")
    context_failure("wrong context declaration hash", ["data", "declarations", 0, "declaration_id"], "0" * 64, "/context/data/declarations/0/declaration_id", "unavailable")
    context_failure("excess context declarations", ["data", "declarations"], [{}] * 4097, "/context/data/declarations", "unavailable")
    context_failure("private root state", ["data", "declarations", 0, "visibility"], "module_private", "/components/0/state")
    context_failure("missing state fields", ["data", "declarations", 0, "fields"], None, "/components/0/state", "unavailable")
    context_failure("missing nongeneric state metadata", ["data", "declarations", 0, "generic_parameters"], None, "/components/0/state", "unavailable")
    context_failure("unused generic state rejected", ["data", "declarations", 0, "generic_parameters"], [{"name": "T", "bound": None}], "/components/0/state", "unavailable")
    for ty in ("string", "i64", "u32", "f64", "List<i32>", "[i32; 4]", "?i32", "IEntity", "T"):
        context_failure("unsupported state field " + ty, ["data", "declarations", 0, "fields", 0, "type"], scalar(ty), "/components/0/state")
    context_failure("duplicate state field", ["data", "declarations", 0, "fields"], [ctx["data"]["declarations"][0]["fields"][0]] * 2, "/components/0/state")
    for key, value in (("visibility", "module_private"), ("receiver", base["components"][0]["state"]), ("generic_parameters", [{"name": "T", "bound": None}]), ("return_type", scalar("i32")), ("parameters", [])):
        context_failure("invalid callback " + key, ["data", "declarations", 1, key], value)
    for key, value in (("access_mode", "let"), ("is_self", True), ("default", {"text": "0"}), ("type", scalar("i32"))):
        context_failure("invalid state parameter " + key, ["data", "declarations", 1, "parameters", 0, key], value)
    for key, value in (("access_mode", "inout"), ("type", scalar("f64")), ("default", {"text": "0f32"})):
        context_failure("invalid frame parameter " + key, ["data", "declarations", 2, "parameters", 1, key], value, "/components/0/callbacks/1/handler")
    context_failure("overlong context source string", ["data", "declarations", 1, "source", "text"], "x" * 65537, "/context/data/declarations/1/source/text", "unavailable")

    def other_state():
        value = copy.deepcopy(ctx)
        value["data"]["declarations"].append(record("other.State", [("state", scalar("i32"))]))
        value["data"]["declarations"][1]["parameters"][0]["type"] = named("other.State")
        fail(lambda: contracts.validate_symbols(base, catalog, value), "/components/0/callbacks/0/handler")
    case("same short spelling cannot substitute declaration identity", other_state)

    def graph(depth, width=1):
        value = copy.deepcopy(ctx)
        state = base["components"][0]["state"]
        names = [state] + ["fixture.Nested" + str(i) for i in range(1, depth)]
        records = [record(name, [("child", named(names[i + 1]))] if i + 1 < depth else [("f" + str(j), scalar("i32")) for j in range(width)], "public" if i == 0 else "module_private") for i, name in enumerate(names)]
        value["data"]["declarations"] = records + value["data"]["declarations"][1:]
        return value
    case("private nested records admitted by exact resolved identity", lambda: contracts.validate_symbols(base, catalog, graph(2)))
    case("nested generic record rejected", lambda: fail(lambda: contracts.validate_symbols(base, catalog, change(graph(2), ["data", "declarations", 1, "generic_parameters"], [{"name": "T", "bound": None}])), "/components/0/state", "unavailable"))
    case("eight record levels admitted", lambda: contracts.validate_symbols(base, catalog, graph(8)))
    case("nine record levels rejected", lambda: fail(lambda: contracts.validate_symbols(base, catalog, graph(9)), "/components/0/state", "unavailable"))
    case("64 fields admitted", lambda: contracts.validate_symbols(base, catalog, graph(1, 64)))
    case("65 fields rejected", lambda: fail(lambda: contracts.validate_symbols(base, catalog, graph(1, 65)), "/components/0/state", "unavailable"))

    def expanded(extra, expected):
        value = copy.deepcopy(ctx)
        child = record("fixture.Shared", [("f" + str(j), scalar("bool")) for j in range(60)], "module_private")
        fields = [("child" + str(i), named(child["qualified_name"])) for i in range(4)]
        fields += [("tail" + str(i), scalar("i32")) for i in range(extra)]
        value["data"]["declarations"][0] = record(base["components"][0]["state"], fields)
        value["data"]["declarations"].append(child)
        if expected:
            result = contracts.validate_symbols(base, catalog, value)
            assert result["components"][0]["resolved_state"]["expanded_fields"] == 256
        else:
            fail(lambda: contracts.validate_symbols(base, catalog, value), "/components/0/state", "unavailable")
    case("memoized shared records count each logical field: 256 admitted", lambda: expanded(12, True))
    case("scalar tail crossing 256 rejected", lambda: expanded(13, False))

    def cycle():
        value = copy.deepcopy(ctx)
        state = base["components"][0]["state"]
        value["data"]["declarations"][0] = record(state, [("self_value", named(state))])
        fail(lambda: contracts.validate_symbols(base, catalog, value), "/components/0/state")
    case("recursive state graph rejected", cycle)

    def catalog_change(path, replacement, pointer, status="failure"):
        value = change(copy.deepcopy(catalog), path, replacement)
        data = json.dumps(value).encode()
        fail(lambda: contracts.load_catalog("fixture", lambda p: data, schema_api.parse), pointer, status)
    case("catalog version cannot be boolean", lambda: catalog_change(["schema_version"], True, "/contract_profile/schema_version"))
    case("catalog cannot claim runtime success", lambda: catalog_change(["runtime_evidence", "status"], "verified", "/contract_profile/runtime_evidence"))
    case("catalog cannot claim known lifetime", lambda: catalog_change(["unknown_contracts", "lifetime"], "verified", "/contract_profile/unknown_contracts"))
    case("catalog engine tamper", lambda: catalog_change(["engine", "sha256"], "0" * 64, "/contract_profile/engine", "stale_input"))
    case("catalog declaration hash tamper", lambda: catalog_change(["extracted_declarations", "document_sha256"], "0" * 64, "/contract_profile", "stale_input"))
    case("catalog source-order tamper", lambda: catalog_change(["source_order_review", "callbacks", 0, "super_order"], "last", "/contract_profile", "stale_input"))
    case("catalog 64 KiB bound", lambda: fail(lambda: contracts.load_catalog("fixture", lambda p: b" " * (contracts.MAX_CATALOG_BYTES + 1), schema_api.parse), "/contract_profile", "unavailable"))
    case("catalog exact-byte tamper", lambda: fail(lambda: contracts.load_catalog("fixture", lambda p: (HERE / "tablet-component-contracts.v1.json").read_bytes() + b" ", schema_api.parse), "/contract_profile", "stale_input"))
    case("catalog malformed JSON", lambda: fail(lambda: contracts.load_catalog("fixture", lambda p: b"{", schema_api.parse), "/contract_profile"))
    case("catalog deep malformed input bounded", lambda: fail(lambda: contracts.load_catalog("fixture", lambda p: b"[" * 10000 + b"]" * 10000, schema_api.parse), "/contract_profile"))

    for name, action in actions:
        try:
            action()
            evidence["cases"].append({"case_id": name, "status": "success"})
        except Exception as exc:
            evidence["cases"].append({"case_id": name, "status": "failure", "error": str(exc), "traceback": traceback.format_exc()})
    after = {str(p): sha(p) for p in paths}
    evidence["inputs_unchanged"] = before == after
    evidence["final_input_hashes"] = after
    failed = [case for case in evidence["cases"] if case["status"] != "success"]
    evidence["summary"] = {"expected": len(actions), "executed": len(evidence["cases"]), "passed": len(actions) - len(failed), "failed": len(failed), "skipped": 0}
    evidence["status"] = "success" if not failed and before == after else "failure"
    (work / "result.json").write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"receipt": str(work / "result.json"), "sha256": sha(work / "result.json"), "status": evidence["status"], "summary": evidence["summary"]}, indent=2))
    for item in failed:
        print(item["case_id"] + ": " + item["error"], file=sys.stderr)
    return 0 if evidence["status"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
