"""Experimental scalar ScriptComponent wrappers; pure, bounded transformation.

The caller supplies checked, frozen compiler output/context and rechecks source
and companion bytes. This module neither reads files nor executes any program.
Exact linkage comes from the emitter, never from a Python mangling substitute.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
from bisect import bisect_right

import component_contracts as contracts

MAX_BYTES = 16 * 1024 * 1024
MAX_TOKENS = 1_000_000
_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,4095}\Z")
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_TOKEN = re.compile(r"\s+|//[^\n]*(?:\n|$)|/\*.*?\*/|\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*'|[A-Za-z_][A-Za-z0-9_]*|[0-9]+|.", re.S)
_RESERVED = frozenset(("abstract auto bool break case cast class const continue default delete do else enum "
                      "event external false float for foreach func if inout int managed native new null out "
                      "override private protected proto ref return sealed static string super switch this true "
                      "typedef typename vector void while scriptcomponent scriptcomponentclass ientity "
                      "entityevent beryl_generated array map set modded owned notnull volatile autoptr local sizeof result").split())
_TYPE = {"bool": "bool", "i32": "int", "f32": "float"}
_SPAN_KEYS = {"path", "file_id", "byte_offset", "byte_length", "line", "column"}
_STATE_MEMBER = "m_BerylState"


def _fail(message, pointer, status="failure"):
    raise contracts.ContractFailure(message, status, pointer)


def _bounded(value, pointer):
    contracts._bounded(value, pointer, nodes=1_000_000, depth=48, string=MAX_BYTES, total=MAX_BYTES)
    if len(json.dumps(value, ensure_ascii=True, separators=(",", ":")).encode("utf-8")) > MAX_BYTES:
        _fail("Serialized metadata exceeds 16 MiB", pointer, "unavailable")


def _name(value, pointer, engine=False):
    if type(value) is not str or not _IDENTIFIER.fullmatch(value):
        _fail("Malformed emitted identifier", pointer)
    if value.casefold() in _RESERVED or (engine and value.casefold().startswith("beryl")):
        _fail("Reserved engine or compiler identifier", pointer)
    return value


def validate_engine_name(value, pointer):
    """Shared engine-facing name policy for preflight and final generation."""
    return _name(value, pointer, engine=True)


def _keys(value, keys, pointer):
    if type(value) is not dict or set(value) != set(keys):
        _fail("Missing or unknown metadata fields", pointer)


def _sources(context, mapping):
    sources = mapping.get("sources")
    if type(sources) is not list or not sources:
        _fail("Missing fingerprinted source list", "/mapping/sources", "unavailable")
    if context.get("sources") != sources:
        _fail("Context and source-map identities differ", "/context/sources", "stale_input")
    ids, folded = {}, set()
    for i, row in enumerate(sources):
        p = "/mapping/sources/" + str(i)
        _keys(row, ("path", "sha256"), p)
        path = row["path"]
        if (type(path) is not str or not path or len(path) > 4096 or "\\" in path or
                path.startswith("/") or ":" in path or any(s in ("", ".", "..") for s in path.split("/"))):
            _fail("Expected canonical relative source path", p + "/path")
        if path.casefold() in folded or type(row["sha256"]) is not str or not _HASH.fullmatch(row["sha256"]):
            _fail("Duplicate source or malformed fingerprint", p)
        ids[path] = i
        folded.add(path.casefold())
    return ids


def _span(value, ids, pointer):
    _keys(value, _SPAN_KEYS, pointer)
    if type(value["path"]) is not str or value["path"] not in ids:
        _fail("Origin has no fingerprinted source", pointer)
    if any(type(value[k]) is not int for k in _SPAN_KEYS - {"path"}):
        _fail("Malformed source coordinates", pointer)
    if (value["file_id"] != ids[value["path"]] or value["byte_offset"] < 0 or value["byte_length"] < 0 or
            value["line"] < 1 or value["column"] < 1 or
            value["byte_offset"] + value["byte_length"] > 0xffffffff):
        _fail("Invalid source coordinate or identity", pointer)
    return value


def _declaration_span(declaration, ids, pointer):
    source = declaration.get("source")
    if type(source) is not dict or source.get("column_unit") != "byte":
        _fail("Missing exact declaration origin", pointer, "unavailable")
    span = {key: source.get(key) for key in _SPAN_KEYS - {"file_id"}}
    if type(span["path"]) is not str:
        _fail("Malformed declaration source path", pointer)
    span["file_id"] = ids.get(span["path"])
    return _span(span, ids, pointer)


def _generated_metadata(generated, mapping, ids):
    if type(generated) is not bytes or not generated:
        _fail("Missing generated source bytes", "/generated", "unavailable")
    if len(generated) > MAX_BYTES:
        _fail("Generated source exceeds 16 MiB", "/generated", "unavailable")
    if not generated.endswith(b"\n") or b"\x00" in generated or b"\r" in generated:
        _fail("Expected LF-terminated compiler source", "/generated")
    try:
        text = generated.decode("utf-8")
    except UnicodeDecodeError:
        _fail("Invalid generated UTF-8", "/generated")
    if (type(mapping.get("schema_version")) is not int or mapping["schema_version"] != 1 or
            mapping.get("operation") != "source_map" or mapping.get("target") != "enfusion" or
            mapping.get("column_unit") != "byte"):
        _fail("Unsupported source-map profile", "/mapping", "unavailable")
    meta = mapping.get("generated")
    _keys(meta, ("file", "bytes", "sha256"), "/mapping/generated")
    if (meta["file"] != "Beryl_Generated.c" or type(meta["bytes"]) is not int or
            meta["bytes"] != len(generated) or meta["sha256"] != hashlib.sha256(generated).hexdigest()):
        _fail("Source map does not identify exact generated bytes", "/mapping/generated", "stale_input")
    entries = mapping.get("mappings")
    if type(entries) is not list or not entries:
        _fail("Missing source mappings", "/mapping/mappings", "unavailable")
    starts = [0] + [i + 1 for i, byte in enumerate(generated) if byte == 10]
    end = 0
    for i, entry in enumerate(entries):
        p = "/mapping/mappings/" + str(i)
        if (type(entry) is not dict or not {"generated", "kind", "original", "expansion_site", "declaration"}.issubset(entry) or
                set(entry) - {"generated", "kind", "original", "expansion_site", "declaration", "companion"}):
            _fail("Malformed source mapping", p)
        loc = entry.get("generated")
        _keys(loc, ("byte_offset", "byte_length", "line", "column"), p + "/generated")
        if any(type(v) is not int for v in loc.values()):
            _fail("Malformed generated coordinates", p)
        start, length, line = loc["byte_offset"], loc["byte_length"], loc["line"]
        if (start < end or length <= 0 or start + length > len(generated) or line < 1 or
                line != bisect_right(starts, start) or starts[line - 1] != start or loc["column"] != 1):
            _fail("Overlapping or invalid generated range", p)
        segment = generated[start:start + length]
        if not segment.endswith(b"\n") or segment.count(b"\n") != 1:
            _fail("Mapping must cover one complete generated line", p)
        end = start + length
        if type(entry.get("kind")) is not str or not entry["kind"]:
            _fail("Missing mapping kind", p)
        if entry.get("declaration") is not None and type(entry["declaration"]) is not str:
            _fail("Malformed mapping declaration", p)
        for key in ("original", "expansion_site"):
            if entry.get(key) is not None:
                _span(entry[key], ids, p + "/" + key)
        if entry.get("companion") is not None:
            _fail("Prior component-expanded output cannot be expanded again", p + "/companion", "unavailable")
    exports = mapping.get("exports")
    if type(exports) is not list:
        _fail("Missing emitter exports", "/mapping/exports", "unavailable")
    export_sources = set()
    for i, row in enumerate(exports):
        _keys(row, ("source", "name"), "/mapping/exports/" + str(i))
        contracts._text(row["source"], "/mapping/exports/" + str(i) + "/source", True)
        _name(row["name"], "/mapping/exports/" + str(i) + "/name")
        if row["source"] in export_sources:
            _fail("Duplicate exported declaration identity", "/mapping/exports/" + str(i))
        export_sources.add(row["source"])
    return text


def _classes(text):
    tokens = []
    for match in _TOKEN.finditer(text):
        token = match.group()
        if token.isspace() or token.startswith(("//", "/*", '"', "'")):
            continue
        tokens.append(token)
        if len(tokens) > MAX_TOKENS:
            _fail("Generated token budget exceeded", "/generated", "unavailable")
    classes, names, depth, i = {}, set(), 0, 0
    while i < len(tokens):
        token = tokens[i]
        if token in ("class", "enum") and depth == 0:
            if i + 2 >= len(tokens):
                _fail("Incomplete generated type", "/generated")
            name = _name(tokens[i + 1], "/generated/type")
            if name.casefold() in names:
                _fail("Conflicting emitted type identities", "/generated/type")
            names.add(name.casefold())
            begin = i + 2
            while begin < len(tokens) and tokens[begin] not in ("{", ";"):
                begin += 1
            if begin == len(tokens) or tokens[begin] != "{":
                _fail("Generated type has no definition", "/generated/type")
            nesting, stop = 1, begin + 1
            while stop < len(tokens) and nesting:
                nesting += (tokens[stop] == "{") - (tokens[stop] == "}")
                if nesting > 128:
                    _fail("Generated nesting budget exceeded", "/generated", "unavailable")
                stop += 1
            if nesting:
                _fail("Unclosed generated type", "/generated/type")
            if token == "class":
                classes[name] = tokens[begin + 1:stop - 1]
            i = stop
            continue
        depth += (token == "{") - (token == "}")
        if depth < 0 or depth > 128:
            _fail("Malformed generated braces", "/generated")
        i += 1
    if depth:
        _fail("Unclosed generated braces", "/generated")
    return classes, names


def _members(body):
    fields, methods, seen, start, i = {}, {}, set(), 0, 0
    while i < len(body):
        if body[i] in (";", "{"):
            header = body[start:i]
            if body[i] == ";" and header and "(" not in header:
                if header[-1].casefold() in seen:
                    _fail("Duplicate emitted member identity", "/generated")
                seen.add(header[-1].casefold())
                fields[header[-1]] = header[:-1]
            elif body[i] == "{" and "(" in header:
                opening = header.index("(")
                if opening < 1 or not header or header[-1] != ")":
                    _fail("Malformed emitted member signature", "/generated")
                name = header[opening - 1]
                if name.casefold() in seen:
                    _fail("Duplicate emitted method identity", "/generated")
                seen.add(name.casefold())
                methods[name] = header
                depth = 1
                i += 1
                while i < len(body) and depth:
                    depth += (body[i] == "{") - (body[i] == "}")
                    i += 1
                start = i
                continue
            start = i + 1
        i += 1
    return fields, methods


def _linkage(mapping, context, index, ids, classes):
    if type(mapping.get("linkage_schema_version")) is not int or mapping["linkage_schema_version"] != 1:
        _fail("Exact version-1 emitter linkage is required", "/mapping/linkage_schema_version", "unavailable")
    rows = mapping.get("linkage")
    if type(rows) is not list or not rows:
        _fail("Emitter linkage is required", "/mapping/linkage", "unavailable")
    linked, identities, members = {}, set(), {name: _members(body) for name, body in classes.items()}
    for i, row in enumerate(rows):
        p = "/mapping/linkage/" + str(i)
        if type(row) is not dict or row.get("kind") not in ("struct", "function"):
            _fail("Unsupported linkage kind", p, "unavailable")
        kind = row["kind"]
        _keys(row, ("declaration", "kind", "source", "class", "fields") if kind == "struct" else
              ("declaration", "kind", "source", "holder", "method"), p)
        name = row["declaration"]
        if type(name) is not str or name in linked or name not in index or index[name]["kind"] != kind:
            _fail("Missing, duplicate or conflicting linkage declaration", p + "/declaration")
        decl = index[name]
        if decl.get("generic_parameters") != [] or (kind == "function" and ("receiver" not in decl or decl["receiver"] is not None)):
            _fail("Nonconcrete or receiver linkage is unsupported", p, "unavailable")
        expected = _declaration_span(decl, ids, p + "/source")
        if row["source"] != expected:
            _fail("Linkage origin differs from resolved declaration", p + "/source", "stale_input")
        cls = _name(row.get("class") if kind == "struct" else row.get("holder"), p)
        if cls not in members:
            _fail("Linkage type is absent from exact generated bytes", p)
        fields, methods = members[cls]
        if kind == "struct":
            if cls.casefold() in identities:
                _fail("Duplicate emitted record identity", p)
            identities.add(cls.casefold())
            values = row["fields"]
            declared = decl.get("fields")
            if type(values) is not list or type(declared) is not list or len(values) != len(declared):
                _fail("Linkage fields differ from resolved record", p + "/fields")
            seen = set()
            for j, (value, source) in enumerate(zip(values, declared)):
                q = p + "/fields/" + str(j)
                _keys(value, ("source", "name"), q)
                if type(source) is not dict:
                    _fail("Malformed resolved field metadata", q)
                field = _name(value["name"], q + "/name")
                if (value["source"] != source.get("name") or field.casefold() in seen or field not in fields):
                    _fail("Field linkage is absent, conflicting or changed", q)
                seen.add(field.casefold())
            if set(fields) != {value["name"] for value in values}:
                _fail("Generated record fields differ from linkage", p + "/fields")
        else:
            method = _name(row["method"], p + "/method")
            identity = (cls.casefold(), method.casefold())
            if identity in identities or method not in methods or methods[method][0] != "static":
                _fail("Function linkage is absent, conflicting or nonstatic", p)
            identities.add(identity)
        linked[name] = row
    record_classes = {row["class"] for row in linked.values() if row["kind"] == "struct"}
    if any(row["holder"] in record_classes for row in linked.values() if row["kind"] == "function"):
        _fail("A function holder conflicts with record storage", "/mapping/linkage")
    return linked, members


def generate(config, catalog, context, summary, generated: bytes, mapping: dict, companion: dict):
    """Append verified-shape wrappers and line origins; no I/O or execution.

    This is experimental generation, not engine compilation/runtime evidence.
    Hash agreement proves metadata consistency; the caller rechecks input bytes.
    """
    for value, pointer in ((mapping, "/mapping"), (context, "/context"), (summary, "/summary"),
                           (config, "/config"), (companion, "/companion")):
        _bounded(value, pointer)
    if type(mapping) is not dict:
        _fail("Expected source-map object", "/mapping")
    admitted = contracts.validate_symbols(config, catalog, context)
    if admitted != summary:
        _fail("Component summary does not match checked inputs", "/summary", "stale_input")
    _keys(companion, ("path", "sha256"), "/companion")
    path = companion["path"]
    if (type(path) is not str or not path or len(path) > 4096 or "\\" in path or ":" in path or path.startswith("/") or
            any(v in ("", ".", "..") for v in path.split("/")) or
            type(companion["sha256"]) is not str or not _HASH.fullmatch(companion["sha256"])):
        _fail("Malformed companion identity", "/companion")
    ids = _sources(context, mapping)
    text = _generated_metadata(generated, mapping, ids)
    classes, names = _classes(text)
    expected_exports = []
    for row in config["exports"]:
        expected_exports.append({"source": row["source"], "name": row["name"]})
        if "constructor" in row:
            expected_exports.append({"source": row["constructor"], "name": row["name"]})
        expected_exports.extend({"source": method["source"], "name": method["name"]} for method in row["methods"])
    if mapping["exports"] != expected_exports:
        _fail("Emitter exports differ from companion descriptions", "/mapping/exports", "stale_input")
    if not {row["name"].casefold() for row in config["exports"]}.issubset(names):
        _fail("Exported classes are absent from generated bytes", "/mapping/exports")
    index = contracts._context_index(context)
    linked, members = _linkage(mapping, context, index, ids, classes)
    # Exported methods/constructors are scoped to their classes. Only actual
    # top-level class/enum names share the generated component namespace.
    occupied = names
    for component in summary["components"]:
        for role in ("descriptor", "instance"):
            name = validate_engine_name(component[role]["name"], component["pointer"] + "/" + role + "/name")
            if name.casefold() in occupied:
                _fail("Component engine identity conflicts with emitted/exported identity", component["pointer"] + "/" + role + "/name")
            occupied.add(name.casefold())
        if component["resolved_state"]["record_depth"] != 1:
            _fail("Generation currently admits only flat scalar state", component["pointer"] + "/state", "unavailable")
        state = linked.get(component["state"])
        if state is None or state["kind"] != "struct":
            _fail("Missing exact state linkage", component["pointer"] + "/state", "unavailable")
        fields, methods = members[state["class"]]
        if methods.get(state["class"]) != ["void", state["class"], "(", ")"]:
            _fail("State default constructor is missing or changed", component["pointer"] + "/state", "unavailable")
        for original, emitted in zip(index[component["state"]]["fields"], state["fields"]):
            ty = original["type"]
            if fields[emitted["name"]] != [_TYPE.get(ty.get("name"))] or ty.get("declaration") is not None:
                _fail("Emitted state storage differs from admitted scalar type", component["pointer"] + "/state")
        for callback in component["callbacks"]:
            handler = linked.get(callback["handler"])
            if handler is None or handler["kind"] != "function":
                _fail("Missing exact callback handler linkage", callback["pointer"] + "/handler", "unavailable")
            header = members[handler["holder"]][1][handler["method"]]
            frame = callback["binding"] == "ScriptComponent.EOnFrame"
            # The actual parameter identifiers may be emitter-mangled; all other
            # signature tokens are fixed by reviewed admission and target ABI.
            if (len(header) != (11 if frame else 8) or
                    header[:6] != ["static", "void", handler["method"], "(", "out", state["class"]] or
                    not _IDENTIFIER.fullmatch(header[6]) or header[-1] != ")" or
                    (frame and (header[7:9] != [",", "float"] or not _IDENTIFIER.fullmatch(header[9]))) or
                    (not frame and header[7] != ")")):
                _fail("Emitted handler signature differs from admitted callback", callback["pointer"] + "/handler")
    result = copy.deepcopy(mapping)
    additions, offset, line = [], len(generated), generated.count(b"\n") + 1

    def emit(code, kind, component, role="state", callback=None):
        nonlocal offset, line
        data = (code + "\n").encode("utf-8")
        if offset + len(data) > MAX_BYTES:
            _fail("Component-expanded output exceeds 16 MiB", "/generated", "unavailable")
        additions.append(data)
        if code.strip():
            if role in ("descriptor", "instance"):
                declaration = original = None
                pointer = component["pointer"] + "/" + role + "/name"
                origin = dict(companion, json_pointer=pointer, expected_value=component[role]["name"], identity_kind="engine_class")
            else:
                declaration = callback["handler"] if callback else component["state"]
                original = copy.deepcopy(linked[declaration]["source"])
                pointer = (callback["pointer"] + "/handler") if callback else component["pointer"] + "/state"
                origin = dict(companion, json_pointer=pointer)
            result["mappings"].append({"generated": {"byte_offset": offset, "byte_length": len(data), "line": line, "column": 1},
                                      "kind": kind, "original": original, "expansion_site": None,
                                      "declaration": declaration, "companion": origin})
        offset += len(data)
        line += 1

    for component in summary["components"]:
        state = linked[component["state"]]["class"]
        emit("", "component_descriptor", component)
        for code in ("class " + component["descriptor"]["name"] + " : ScriptComponentClass", "{", "}"):
            emit(code, "component_descriptor", component, "descriptor")
        emit("", "component_state", component)
        for code in ("class " + component["instance"]["name"] + " : ScriptComponent", "{"):
            emit(code, "component_state", component, "instance")
        # ScriptComponent's native construction contract cannot be replaced by
        # a zero-argument script constructor. Initialize the retained member
        # directly and leave engine component construction to the engine.
        emit("    protected ref " + state + " " + _STATE_MEMBER + " = new " + state + "();",
             "component_initializer", component)
        for callback in component["callbacks"]:
            binding = callback["binding"].split(".")[-1]
            frame = binding == "EOnFrame"
            signature = contracts.CALLBACKS[callback["binding"]][0]
            emit("", "component_callback", component)
            emit("    override " + signature, "component_callback", component, callback=callback)
            emit("    {", "component_callback", component, callback=callback)
            if callback["super_order"] == "first":
                emit("        super." + binding + "(owner);", "component_superclass", component, callback=callback)
            handler = linked[callback["handler"]]
            emit("        " + handler["holder"] + "." + handler["method"] + "(" + _STATE_MEMBER + (", timeSlice" if frame else "") + ");",
                 "component_handler", component, callback=callback)
            if binding == "OnPostInit":
                emit("        SetEventMask(owner, EntityEvent.FRAME);", "component_event_mask", component, callback=callback)
            if callback["super_order"] == "last":
                emit("        super." + binding + "(owner);", "component_superclass", component, callback=callback)
            emit("    }", "component_callback", component, callback=callback)
        emit("}", "component_state", component, "instance")
    output = generated + b"".join(additions)
    result["generated"] = {"file": "Beryl_Generated.c", "bytes": len(output), "sha256": hashlib.sha256(output).hexdigest()}
    result["component_generation"] = {"schema_version": 1, "status": "generated_experimental",
                                      "subset": "flat_bool_i32_f32_script_component", "components": len(summary["components"]),
                                      "contract_profile": contracts.PROFILE, "execution": "not_run",
                                      "engine_compilation": "not_run", "runtime_verification": "not_run",
                                      "unknown_contracts": copy.deepcopy(summary["unresolved_contracts"]),
                                      "context_identity": copy.deepcopy(summary["context_identity"]),
                                      "companion": copy.deepcopy(companion)}
    _bounded(result, "/mapping")
    return output, result
