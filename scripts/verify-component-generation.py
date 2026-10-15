#!/usr/bin/env python3
"""Pure-Python scalar-wrapper regression gate; no compiler, engine or mod run."""
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
TOOLS = ROOT / "tools/beryl-mod"
sys.path.insert(0, str(TOOLS))
import component_contracts as contracts
import component_generation as generation


def digest(data):
    return hashlib.sha256(data).hexdigest()


def identity(kind, name):
    return digest(("beryl.declaration.v1:" + kind + ":" + name).encode())


def scalar(name):
    return {"name": name, "declaration": None}


def named(name):
    return {"name": name, "declaration": name}


def fixture(catalog):
    source = b"pub struct State {}\npub fn init() {}\npub fn frame() {}\npub fn drop() {}\n"
    starts = [0] + [i + 1 for i, byte in enumerate(source) if byte == 10]
    sources = [{"path": "synthetic/tablet.be", "sha256": digest(source)}]

    def origin(line):
        start, end = starts[line - 1], starts[line]
        return {"path": sources[0]["path"], "byte_offset": start, "byte_length": end - start - 1,
                "line": line, "column": 1, "column_unit": "byte", "text": source[start:end - 1].decode()}

    state_name = "fixture.State"
    state = {"declaration_id": identity("struct", state_name), "qualified_name": state_name,
             "name": "State", "kind": "struct", "visibility": "public", "source": origin(1),
             "generic_parameters": [], "fields": [{"name": name, "type": scalar(ty)} for name, ty in
                                                   (("ready", "bool"), ("count", "i32"), ("elapsed", "f32"))]}
    decls = [state]
    callbacks = []
    for line, (binding, suffix) in enumerate(zip(contracts.CALLBACKS, ("init", "frame", "drop")), 2):
        name = "fixture." + suffix
        params = [{"name": "state", "access_mode": "inout", "is_self": False, "type": named(state_name), "default": None}]
        if suffix == "frame":
            params.append({"name": "delta", "access_mode": "let", "is_self": False, "type": scalar("f32"), "default": None})
        decls.append({"declaration_id": identity("function", name), "qualified_name": name, "name": suffix,
                      "kind": "function", "visibility": "public", "source": origin(line), "receiver": None,
                      "generic_parameters": [], "return_type": scalar("void"), "parameters": params})
        callbacks.append({"binding": binding, "handler": name, "super_order": contracts.CALLBACKS[binding][1]})
    config = {"schema_version": 2, "name": "Synthetic scalar wrapper fixture",
              "addon": {"id": "Fixture", "guid": "DA00000000000001", "dependencies": []},
              "sources": {"native": ["synthetic/tablet.be"], "enfusion": ["synthetic/tablet.be"], "tests": []},
              "binding": {"target": "enfusion", "version": contracts.ENGINE_VERSION,
                                               "sha256": contracts.ENGINE_SHA256, "contract_profile": contracts.PROFILE},
              "exports": [], "components": [{"descriptor": {"name": "FixtureComponentClass", "parent": "ScriptComponentClass"},
                                              "instance": {"name": "FixtureComponent", "parent": "ScriptComponent"},
                                              "state": state_name, "callbacks": callbacks}]}
    context = {"schema_version": 1, "operation": "context.project", "stage": "context", "status": "success",
               "execution": "not_run", "diagnostics": [], "compiler_fingerprint": "1" * 64,
               "source_fingerprint": "2" * 64, "sources": sources, "data": {"declarations": decls}}
    mapping = {"schema_version": 1, "operation": "source_map", "target": "enfusion", "column_unit": "byte",
               "mapping_precision": "synthetic complete line origins", "sources": copy.deepcopy(sources),
               "exports": [], "linkage_schema_version": 1, "linkage": []}
    state_class, holder = "ExactStorage_47", "ExactHolder_53"
    field_names = ["F_ready_7", "F_count_8", "F_elapsed_9"]
    for decl in decls:
        span = {k: v for k, v in decl["source"].items() if k not in ("column_unit", "text")}
        span["file_id"] = 0
        row = {"declaration": decl["qualified_name"], "kind": decl["kind"], "source": span}
        if decl["kind"] == "struct":
            row.update({"class": state_class, "fields": [{"source": field["name"], "name": emitted}
                                                           for field, emitted in zip(decl["fields"], field_names)]})
        else:
            row.update({"holder": holder, "method": "Exact_" + decl["name"] + "_61"})
        mapping["linkage"].append(row)
    code = ("// class FakeType { }; and enum FakeEnum { };\n"
            "class " + state_class + "\n{\n"
            "    bool F_ready_7;\n    int F_count_8;\n    float F_elapsed_9;\n"
            "    void " + state_class + "()\n    {\n        F_count_8 = 2;\n    }\n"
            "    " + state_class + " BerylCopy()\n    {\n        return new " + state_class + "();\n    }\n}\n"
            "class " + holder + "\n{\n"
            "    static void Exact_init_61(out " + state_class + " exactArg)\n    {\n        exactArg.F_ready_7 = true;\n    }\n"
            "    static void Exact_frame_61(out " + state_class + " exactArg, float otherArg)\n    {\n        exactArg.F_elapsed_9 = otherArg;\n    }\n"
            "    static void Exact_drop_61(out " + state_class + " exactArg)\n    {\n        exactArg.F_ready_7 = false;\n    }\n}\n").encode()
    value = {"config": config, "context": context, "mapping": mapping, "generated": code,
             "companion": {"path": "beryl.mod.json", "sha256": "3" * 64}}
    remap(value)
    value["summary"] = contracts.validate_symbols(config, catalog, context)
    return value


def remap(value):
    data, mapping = value["generated"], value["mapping"]
    mapping["generated"] = {"file": "Beryl_Generated.c", "bytes": len(data), "sha256": digest(data)}
    mapping["mappings"] = []
    offset = 0
    for number, line in enumerate(data.splitlines(keepends=True), 1):
        if line.strip():
            mapping["mappings"].append({"generated": {"byte_offset": offset, "byte_length": len(line), "line": number, "column": 1},
                                        "kind": "synthetic", "original": copy.deepcopy(mapping["linkage"][0]["source"]),
                                        "expansion_site": None, "declaration": "fixture.State"})
        offset += len(line)


def run(value, catalog):
    return generation.generate(value["config"], catalog, value["context"], value["summary"],
                               value["generated"], value["mapping"], value["companion"])


def refresh(value, catalog):
    value["summary"] = contracts.validate_symbols(value["config"], catalog, value["context"])


def changed(value, path, replacement):
    target = value
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = replacement
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    build = (ROOT / "build").resolve()
    if args.output:
        work = args.output.resolve()
        if not work.is_relative_to(build):
            parser.error("Output must be a new directory under build")
        work.mkdir(parents=True, exist_ok=False)
    else:
        work = Path(tempfile.mkdtemp(prefix="component-generation-", dir=build))
    paths = [Path(__file__), TOOLS / "component_generation.py", TOOLS / "component_contracts.py", TOOLS / "tablet-component-contracts.v1.json"]
    hashes = {str(path): digest(path.read_bytes()) for path in paths}
    receipt = {"schema_version": 1, "operation": "verify_component_generation", "status": "running", "cases": [],
               "input_hashes": hashes, "context_kind": "synthetic", "compiler_execution": "not_run",
               "engine_execution": "not_run", "program_execution": "not_run",
               "scope": "pure bounded scalar wrapper transformation and rejection; no runtime or engine evidence"}

    planned = []

    def case(name, body):
        planned.append((name, body))

    def execute(name, body):
        try:
            body()
            receipt["cases"].append({"id": name, "status": "success"})
        except Exception as exc:
            receipt["cases"].append({"id": name, "status": "failure", "error": str(exc), "traceback": traceback.format_exc()})

    def reject(name, edit, status="failure", pointer=None, recalculate=False):
        def body():
            value = copy.deepcopy(base)
            edit(value)
            before = copy.deepcopy(value)
            try:
                if recalculate:
                    refresh(value, catalog)
                    before = copy.deepcopy(value)
                run(value, catalog)
            except contracts.ContractFailure as exc:
                assert exc.status == status, (exc.status, status, str(exc), exc.pointer)
                assert type(exc.pointer) is str and exc.pointer.startswith("/")
                if pointer is not None:
                    assert exc.pointer == pointer, (exc.pointer, pointer, str(exc))
                assert value == before, "Rejected input was mutated"
                return
            raise AssertionError("Invalid generation succeeded")
        case(name, body)

    catalog = json.loads((TOOLS / "tablet-component-contracts.v1.json").read_text(encoding="utf-8"))
    base = fixture(catalog)

    def valid():
        before = copy.deepcopy(base)
        output, mapping = run(base, catalog)
        assert base == before
        assert output.startswith(base["generated"]) and mapping["mappings"][:len(base["mapping"]["mappings"])] == base["mapping"]["mappings"]
        for key in base["mapping"]:
            if key not in ("generated", "mappings"):
                assert mapping[key] == base["mapping"][key]
        assert mapping["generated"]["sha256"] == digest(output) and mapping["generated"]["bytes"] == len(output)
        assert mapping["component_generation"]["runtime_verification"] == "not_run"
        assert run(base, catalog) == (output, mapping)
        suffix = output[len(base["generated"]):].decode()
        assert suffix.count("new ExactStorage_47();") == 1 and "BerylCopy" not in suffix
        assert suffix.count("protected ref ExactStorage_47 m_BerylState = new ExactStorage_47();") == 1
        assert "void " + base["config"]["components"][0]["instance"]["name"] + "()" not in suffix
        assert "ExactHolder_53.Exact_frame_61(m_BerylState, timeSlice);" in suffix
        assert suffix.index("super.OnPostInit(owner);") < suffix.index("ExactHolder_53.Exact_init_61") < suffix.index("SetEventMask(owner, EntityEvent.FRAME);")
        assert suffix.index("ExactHolder_53.Exact_drop_61") < suffix.index("super.OnDelete(owner);")
        assert "super.EOnFrame" not in suffix and suffix.count("override void ") == 3
        appended = mapping["mappings"][len(base["mapping"]["mappings"]):]
        expected = {i for i, line in enumerate(output.splitlines(keepends=True), 1)
                    if line.strip() and i > base["generated"].count(b"\n")}
        assert {row["generated"]["line"] for row in appended} == expected
        offset = len(base["generated"])
        for row in appended:
            loc = row["generated"]
            assert loc["byte_offset"] >= offset and loc["column"] == 1
            raw = output[loc["byte_offset"]:loc["byte_offset"] + loc["byte_length"]]
            assert raw.endswith(b"\n") and raw.count(b"\n") == 1
            origin = row["companion"]
            assert origin["path"] == "beryl.mod.json" and origin["sha256"] == "3" * 64
            tokens = origin["json_pointer"][1:].split("/")
            referred = base["config"]
            for token in tokens:
                referred = referred[int(token)] if isinstance(referred, list) else referred[token]
            if row["declaration"] is None:
                assert row["original"] is None and origin["identity_kind"] == "engine_class" and referred == origin["expected_value"]
            else:
                assert referred == row["declaration"] and row["original"] == next(v["source"] for v in base["mapping"]["linkage"] if v["declaration"] == referred)
            offset = loc["byte_offset"] + loc["byte_length"]
        assert {row["kind"] for row in appended} == {"component_descriptor", "component_state", "component_initializer", "component_callback", "component_superclass", "component_handler", "component_event_mask"}
        receipt["synthetic_output"] = {"sha256": digest(output), "bytes": len(output), "appended_nonblank_lines": len(appended),
                                       "mapping_sha256": digest(json.dumps(mapping, sort_keys=True, separators=(",", ":")).encode())}
    case("valid-deterministic-complete-origins-direct-state", valid)

    def multiple():
        value = copy.deepcopy(base)
        component = value["config"]["components"][0]
        value["config"]["components"] = []
        for i in range(16):
            clone = copy.deepcopy(component)
            clone["descriptor"]["name"] = "Fixture" + str(i) + "Class"
            clone["instance"]["name"] = "Fixture" + str(i)
            value["config"]["components"].append(clone)
        refresh(value, catalog)
        output, mapping = run(value, catalog)
        suffix = output[len(value["generated"]):].decode()
        assert suffix.count("new ExactStorage_47();") == 16 and suffix.count("SetEventMask(owner, EntityEvent.FRAME);") == 16
        assert suffix.index("class Fixture0Class") < suffix.index("class Fixture15Class")
        assert mapping["component_generation"]["components"] == 16
    case("sixteen-components-shared-code-independent-state", multiple)

    def constructor_facade():
        value = copy.deepcopy(base)
        fn = copy.deepcopy(value["context"]["data"]["declarations"][1])
        fn.update(qualified_name="fixture.State.initialize", name="initialize", receiver="fixture.State",
                  declaration_id=identity("function", "fixture.State.initialize"))
        value["context"]["data"]["declarations"].append(fn)
        value["config"]["exports"] = [{"source": "fixture.State", "name": "EngineState",
                                         "constructor": "fixture.State.initialize", "methods": []}]
        value["mapping"]["exports"] = [{"source": "fixture.State", "name": "EngineState"},
                                          {"source": "fixture.State.initialize", "name": "EngineState"}]
        value["generated"] += ("class EngineState\n{\n    protected ref ExactStorage_47 payload;\n"
                                "    void EngineState()\n    {\n        payload = new ExactStorage_47();\n    }\n}\n").encode()
        remap(value)
        refresh(value, catalog)
        output, _ = run(value, catalog)
        suffix = output[len(value["generated"]):]
        assert b"protected ref ExactStorage_47 m_BerylState = new ExactStorage_47();" in suffix
        assert b"new EngineState" not in suffix and suffix.count(b"new ExactStorage_47") == 1
    case("mapped-constructor-facade-keeps-exact-storage-class", constructor_facade)

    def scoped_exports():
        value = copy.deepcopy(base)
        child = copy.deepcopy(value["context"]["data"]["declarations"][0])
        child.update(qualified_name="fixture.OtherState", name="OtherState", declaration_id=identity("struct", "fixture.OtherState"))
        value["context"]["data"]["declarations"].append(child)
        row = copy.deepcopy(value["mapping"]["linkage"][0])
        row.update(declaration="fixture.OtherState", **{"class": "OtherStorage"})
        value["mapping"]["linkage"].append(row)
        for state, cls in (("fixture.State", "ExactStorage_47"), ("fixture.OtherState", "OtherStorage")):
            fn = copy.deepcopy(value["context"]["data"]["declarations"][1])
            fn.update(qualified_name=state + ".read", name="read", receiver=state,
                      declaration_id=identity("function", state + ".read"), return_type=scalar("i32"))
            fn["parameters"][0]["type"] = named(state)
            value["context"]["data"]["declarations"].append(fn)
            value["config"]["exports"].append({"source": state, "name": cls, "methods": [{"source": state + ".read", "name": "Read"}]})
            value["mapping"]["exports"].extend([{"source": state, "name": cls}, {"source": state + ".read", "name": "Read"}])
        value["generated"] = value["generated"].replace(b"    ExactStorage_47 BerylCopy()", b"    int Read()\n    {\n        return 1;\n    }\n    ExactStorage_47 BerylCopy()")
        value["generated"] += b"class OtherStorage\n{\n    bool F_ready_7;\n    int F_count_8;\n    float F_elapsed_9;\n    void OtherStorage()\n    {\n    }\n    int Read()\n    {\n        return 2;\n    }\n}\n"
        value["config"]["components"][0]["descriptor"]["name"] = "ReadClass"
        value["config"]["components"][0]["instance"]["name"] = "Read"
        remap(value)
        refresh(value, catalog)
        output, _ = run(value, catalog)
        assert b"class Read : ScriptComponent" in output[len(value["generated"]):]
    case("two-receiver-exported-Read-methods-and-Read-component", scoped_exports)

    reject("tampered-admission-summary", lambda v: v["summary"].update(status="admitted_structure"), "stale_input", "/summary")
    reject("changed-context-compiler", lambda v: v["context"].update(compiler_fingerprint="4" * 64), "stale_input", "/summary")
    reject("changed-context-source", lambda v: v["context"].update(source_fingerprint="4" * 64), "stale_input", "/summary")
    reject("missing-context-source-list", lambda v: v["context"].pop("sources"), "stale_input", "/context/sources")
    reject("changed-context-source-hash", lambda v: v["context"]["sources"][0].update(sha256="4" * 64), "stale_input", "/context/sources")
    for field, replacement in (("file", "Other.c"), ("bytes", 1), ("bytes", True), ("sha256", "4" * 64)):
        reject("generated-identity-" + field + "-" + str(replacement)[:8], lambda v, f=field, r=replacement: v["mapping"]["generated"].update({f: r}), "stale_input", "/mapping/generated")
    reject("generated-byte-tamper", lambda v: v.update(generated=v["generated"].replace(b"true", b"false")), "stale_input", "/mapping/generated")
    reject("generated-empty", lambda v: v.update(generated=b""), "unavailable", "/generated")
    reject("generated-not-bytes", lambda v: v.update(generated="class X {}\n"), "unavailable", "/generated")
    reject("generated-nonterminated", lambda v: v.update(generated=v["generated"].rstrip(b"\n")), pointer="/generated")
    reject("generated-nul", lambda v: v.update(generated=b"\x00\n"), pointer="/generated")
    reject("generated-invalid-utf8", lambda v: v.update(generated=b"\xff\n"), pointer="/generated")
    reject("generated-crlf", lambda v: v.update(generated=v["generated"].replace(b"\n", b"\r\n")), pointer="/generated")
    reject("generated-budget", lambda v: v.update(generated=b"x" * (generation.MAX_BYTES + 1)), "unavailable", "/generated")
    for field, replacement in (("schema_version", 2), ("schema_version", True), ("target", "native"), ("operation", "other"), ("column_unit", "utf16")):
        reject("map-profile-" + field + "-" + str(replacement), lambda v, f=field, r=replacement: v["mapping"].update({f: r}), "unavailable", "/mapping")
    reject("missing-linkage", lambda v: v["mapping"].pop("linkage"), "unavailable", "/mapping/linkage")
    reject("missing-linkage-version", lambda v: v["mapping"].pop("linkage_schema_version"), "unavailable", "/mapping/linkage_schema_version")
    reject("wrong-linkage-version", lambda v: v["mapping"].update(linkage_schema_version=2), "unavailable", "/mapping/linkage_schema_version")
    reject("boolean-linkage-version", lambda v: v["mapping"].update(linkage_schema_version=True), "unavailable", "/mapping/linkage_schema_version")
    reject("empty-linkage", lambda v: v["mapping"].update(linkage=[]), "unavailable", "/mapping/linkage")
    reject("duplicate-linkage", lambda v: v["mapping"]["linkage"].append(copy.deepcopy(v["mapping"]["linkage"][0])))
    reject("unknown-linkage-field", lambda v: v["mapping"]["linkage"][0].update(extra=True))
    reject("unknown-linkage-kind", lambda v: v["mapping"]["linkage"][0].update(kind="generic"), "unavailable")
    reject("unknown-linkage-declaration", lambda v: v["mapping"]["linkage"][0].update(declaration="fixture.Missing"))
    for field, replacement in (("file_id", 1), ("byte_offset", 1), ("byte_length", 1), ("line", 2), ("column", 2), ("path", "other.be")):
        reject("changed-linkage-origin-" + field, lambda v, f=field, r=replacement: v["mapping"]["linkage"][0]["source"].update({f: r}), "stale_input")
    for field, replacement in (("class", "MissingClass"), ("class", "int"), ("class", "bad-class")):
        reject("state-linkage-" + replacement, lambda v, f=field, r=replacement: v["mapping"]["linkage"][0].update({f: r}))
    reject("missing-state-linkage", lambda v: v["mapping"]["linkage"].pop(0), "unavailable")
    reject("missing-handler-linkage", lambda v: v["mapping"]["linkage"].pop(1), "unavailable")
    reject("missing-holder", lambda v: v["mapping"]["linkage"][1].update(holder="MissingHolder"))
    reject("missing-method", lambda v: v["mapping"]["linkage"][1].update(method="MissingMethod"))
    reject("duplicate-method-linkage", lambda v: v["mapping"]["linkage"][2].update(method="Exact_init_61"))
    reject("wrong-field-source", lambda v: v["mapping"]["linkage"][0]["fields"][0].update(source="count"))
    reject("wrong-field-name", lambda v: v["mapping"]["linkage"][0]["fields"][0].update(name="MissingField"))
    reject("duplicate-field", lambda v: v["mapping"]["linkage"][0]["fields"][1].update(name="F_ready_7"))
    reject("missing-field", lambda v: v["mapping"]["linkage"][0]["fields"].pop())
    reject("missing-mappings", lambda v: v["mapping"].pop("mappings"), "unavailable")
    reject("empty-mappings", lambda v: v["mapping"].update(mappings=[]), "unavailable")
    for field in ("original", "expansion_site", "declaration", "kind"):
        reject("missing-mapping-association-" + field, lambda v, f=field: v["mapping"]["mappings"][0].pop(f))
    for field, replacement in (("byte_offset", 1), ("byte_length", 1), ("line", 2), ("column", 2), ("column", True)):
        reject("invalid-generated-range-" + field + "-" + str(replacement), lambda v, f=field, r=replacement: v["mapping"]["mappings"][0]["generated"].update({f: r}))
    reject("overlapping-mappings", lambda v: v["mapping"]["mappings"].insert(1, copy.deepcopy(v["mapping"]["mappings"][0])))
    reject("origin-wrong-file-id", lambda v: v["mapping"]["mappings"][0]["original"].update(file_id=1))
    reject("origin-negative-offset", lambda v: v["mapping"]["mappings"][0]["original"].update(byte_offset=-1))
    reject("origin-unknown-key", lambda v: v["mapping"]["mappings"][0]["original"].update(column_unit="byte"))
    reject("prior-companion-expanded", lambda v: v["mapping"]["mappings"][0].update(companion={}), "unavailable")
    reject("missing-exports", lambda v: v["mapping"].pop("exports"), "unavailable")
    reject("duplicate-export-sources", lambda v: v["mapping"].update(exports=[{"source": "fixture.State", "name": "ExportA"}, {"source": "fixture.State", "name": "ExportB"}]))
    for role in ("descriptor", "instance"):
        for replacement in ("ExactStorage_47", "exactholder_53", "ScriptComponent", "INT", "beryl_private_name"):
            reject("collision-" + role + "-" + replacement, lambda v, r=role, n=replacement: v["config"]["components"][0][r].update(name=n), recalculate=True)
    reject("component-casefold-collision", lambda v: v["config"]["components"][0]["instance"].update(name="fixturecomponentclass"), recalculate=True)
    reject("unmatched-export-description", lambda v: v["mapping"].update(exports=[{"source": "fixture.State", "name": "ExportOther"}]), "stale_input")
    for field, replacement in (("path", "../beryl.mod.json"), ("path", "C:/beryl.mod.json"), ("sha256", "bad")):
        reject("companion-" + field + "-" + replacement, lambda v, f=field, r=replacement: v["companion"].update({f: r}))
    reject("companion-unknown-field", lambda v: v["companion"].update(extra=True))

    def replace_code(value, old, new):
        assert old in value["generated"]
        value["generated"] = value["generated"].replace(old, new)
        remap(value)
    for name, old, new, status in (
            ("wrong-scalar-storage", b"bool F_ready_7;", b"int F_ready_7;", "failure"),
            ("missing-default-constructor", b"void ExactStorage_47()", b"void OtherConstructor()", "unavailable"),
            ("nonstatic-handler", b"static void Exact_init_61", b"void Exact_init_61", "failure"),
            ("wrong-handler-mode", b"out ExactStorage_47 exactArg", b"ExactStorage_47 exactArg", "failure"),
            ("wrong-handler-return", b"void Exact_init_61", b"int Exact_init_61", "failure"),
            ("wrong-frame-width", b"float otherArg", b"int otherArg", "failure"),
            ("extra-generated-field", b"bool F_ready_7;", b"bool F_ready_7;\n    bool extra;", "failure"),
            ("duplicate-generated-field", b"bool F_ready_7;", b"bool F_ready_7;\n    bool f_READY_7;", "failure")):
        reject(name, lambda v, old=old, new=new: replace_code(v, old, new), status)

    def add_type(value, code):
        value["generated"] += code
        remap(value)
    reject("enum-class-collision", lambda v: add_type(v, b"enum fixturecomponent { A }\n"))
    reject("duplicate-generated-type-casefold", lambda v: add_type(v, b"class exactstorage_47 {}\n"))
    reject("unclosed-generated-type", lambda v: add_type(v, b"class Unclosed {\n"))

    def extra_record(value, path=None, bad_field=False):
        child = copy.deepcopy(value["context"]["data"]["declarations"][0])
        child.update(qualified_name="fixture.OtherState", name="OtherState", declaration_id=identity("struct", "fixture.OtherState"))
        if path is not None:
            child["source"]["path"] = path
        if bad_field:
            child["fields"][0] = "not-an-object"
        value["context"]["data"]["declarations"].append(child)
        row = copy.deepcopy(value["mapping"]["linkage"][0])
        row.update(declaration="fixture.OtherState", **{"class": "OtherStorage"})
        value["mapping"]["linkage"].append(row)
        add_type(value, b"class OtherStorage\n{\n    bool F_ready_7;\n    int F_count_8;\n    float F_elapsed_9;\n}\n")
    reject("malformed-unselected-source-path-object", lambda v: extra_record(v, path={}))
    reject("malformed-unselected-field-metadata", lambda v: extra_record(v, bad_field=True))
    reject("malformed-original-source-path-object", lambda v: v["mapping"]["mappings"][0]["original"].update(path={}))
    reject("missing-free-function-receiver-metadata", lambda v: v["context"]["data"]["declarations"][1].pop("receiver"))

    def nested(value):
        child = copy.deepcopy(value["context"]["data"]["declarations"][0])
        child.update(qualified_name="fixture.Child", name="Child", declaration_id=identity("struct", "fixture.Child"))
        value["context"]["data"]["declarations"].append(child)
        value["context"]["data"]["declarations"][0]["fields"][0]["type"] = named("fixture.Child")
        value["generated"] = value["generated"].replace(b"bool F_ready_7;", b"ChildStorage F_ready_7;")
        refresh(value, catalog)
        remap(value)
    reject("nested-record-check-admitted-generation-unavailable", nested, "unavailable", "/components/0/state")
    reject("unknown-profile", lambda v: v["config"]["binding"].update(contract_profile="unknown"), "unavailable")
    reject("unknown-super-order", lambda v: v["config"]["components"][0]["callbacks"][0].update(super_order="none"))
    reject("unknown-callback", lambda v: v["config"]["components"][0]["callbacks"][0].update(binding="ScriptComponent.Other"), "unavailable")
    reject("unknown-component-field", lambda v: v["config"]["components"][0].update(injected_code="raw"))
    reject("seventeen-components", lambda v: v["config"].update(components=[copy.deepcopy(v["config"]["components"][0]) for _ in range(17)]))
    reject("metadata-string-budget", lambda v: v["mapping"].update(large="x" * (generation.MAX_BYTES + 1)), "unavailable")
    reject("metadata-depth-budget", lambda v: v["mapping"].update(deep=deep(50)), "unavailable")

    expected_ids = [name for name, _ in planned]
    receipt["expected_case_ids"] = expected_ids
    receipt["expected_cases"] = len(expected_ids)
    if len(set(expected_ids)) != len(expected_ids):
        receipt["registration_error"] = "Duplicate planned case identity"
    else:
        for name, body in planned:
            execute(name, body)
    completed = [row["id"] for row in receipt["cases"]]
    receipt["complete_expected_case_set"] = completed == expected_ids and len(set(completed)) == len(completed)
    after = {str(path): digest(path.read_bytes()) for path in paths}
    receipt["inputs_unchanged"] = hashes == after
    receipt["passed_cases"] = sum(row["status"] == "success" for row in receipt["cases"])
    receipt["status"] = "success" if (receipt["passed_cases"] == receipt["expected_cases"] and receipt["inputs_unchanged"] and
                                       receipt["complete_expected_case_set"]) else "failure"
    target = work / "result.json"
    target.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": receipt["status"], "passed_cases": receipt["passed_cases"], "expected_cases": receipt["expected_cases"],
                      "receipt": str(target), "receipt_sha256": digest(target.read_bytes()),
                      "failures": [{"id": row["id"], "error": row.get("error")} for row in receipt["cases"] if row["status"] != "success"]}))
    return 0 if receipt["status"] == "success" else 1


def deep(level):
    value = None
    for _ in range(level):
        value = [value]
    return value


if __name__ == "__main__":
    raise SystemExit(main())
