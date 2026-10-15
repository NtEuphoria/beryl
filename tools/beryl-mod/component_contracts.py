"""Bounded component structure/signature admission. No generation or execution.

The installed catalog is source-controlled evidence, not a project hook. Engine
declarations, source-order review and missing runtime contracts remain separate.
The caller owns compiler invocation, snapshot checks and target admission.
"""
from __future__ import annotations

import hashlib
import json
import math
import re

PROFILE = "enfusion.tablet.script-component.v1"
ENGINE_VERSION = "1.8.0.13"
ENGINE_SHA256 = "7dd36ca1f662b0c13669a4f2f7f10e3c461c2906b021e742272d64b3ab7e9798"
CATALOG_SHA256 = "a48c7764b4e6cd47ee35001872f638e01edcbf764053d843d0d30cfb370b58b4"
CATALOG_CANONICAL_SHA256 = "3e18624104765e65dedb826a28089a6c25a4bab45bfbdc6aea41f10f185f6773"
MAX_CATALOG_BYTES = 64 * 1024
MAX_CONTEXT_DECLARATIONS = 4096
MAX_SUMMARY_BYTES = 1024 * 1024
CALLBACKS = {
    "ScriptComponent.OnPostInit": ("void OnPostInit(IEntity owner)", "first", 238),
    "ScriptComponent.EOnFrame": ("void EOnFrame(IEntity owner, float timeSlice)", "none", 210),
    "ScriptComponent.OnDelete": ("void OnDelete(IEntity owner)", "last", 240),
}
_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,119}\Z")
_SYMBOL = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+\Z")
_HASH = re.compile(r"[0-9a-f]{64}\Z")


class ContractFailure(Exception):
    def __init__(self, message, status="failure", pointer=None):
        super().__init__(message)
        self.status = status
        self.pointer = pointer


def _fail(message, pointer, status="failure"):
    raise ContractFailure(message, status, pointer)


def _escape(value):
    return value.replace("~", "~0").replace("/", "~1")


def _keys(value, required, pointer, optional=()):
    if type(value) is not dict:
        _fail("Expected object", pointer)
    unknown = set(value) - set(required) - set(optional)
    missing = set(required) - set(value)
    if unknown:
        key = sorted(unknown)[0]
        _fail("Unsupported field: " + key, pointer + "/" + _escape(key))
    if missing:
        key = sorted(missing)[0]
        _fail("Missing field: " + key, pointer + "/" + _escape(key))


def _text(value, pointer, symbol=False):
    pattern = _SYMBOL if symbol else _IDENTIFIER
    if type(value) is not str or len(value) > (512 if symbol else 120) or not pattern.fullmatch(value):
        _fail("Expected qualified symbol" if symbol else "Expected identifier", pointer)
    return value


def _fixed(value, expected, pointer, status="failure"):
    if type(value) is not type(expected) or value != expected:
        _fail("Unsupported value; expected " + repr(expected), pointer, status)


def _bounded(value, pointer, nodes, depth, string, total):
    """Bound already parsed JSON without unbounded recursive traversal."""
    stack = [(value, pointer, 0)]
    count = size = 0
    while stack:
        item, origin, level = stack.pop()
        count += 1
        if count > nodes or level > depth:
            _fail("JSON structure exceeds admission resource limit", origin, "unavailable")
        if type(item) is str:
            if len(item) > string:
                _fail("JSON string exceeds admission resource limit", origin, "unavailable")
            try:
                size += len(item.encode("utf-8"))
            except UnicodeEncodeError:
                _fail("Invalid Unicode JSON string", origin)
        elif type(item) is dict:
            if len(item) + len(stack) + count > nodes:
                _fail("JSON object exceeds admission resource limit", origin, "unavailable")
            for key, child in item.items():
                if type(key) is not str or len(key) > string:
                    _fail("Invalid or overlong JSON object key", origin)
                try:
                    size += len(key.encode("utf-8"))
                except UnicodeEncodeError:
                    _fail("Invalid Unicode JSON object key", origin)
                stack.append((child, origin + "/" + _escape(key), level + 1))
        elif type(item) is list:
            if len(item) + len(stack) + count > nodes:
                _fail("JSON array exceeds admission resource limit", origin, "unavailable")
            stack.extend((child, origin + "/" + str(i), level + 1) for i, child in enumerate(item))
        elif item is None or type(item) in (bool, int):
            if type(item) is int and item.bit_length() > 64:
                _fail("JSON integer exceeds admission resource limit", origin, "unavailable")
            size += 32
        elif type(item) is float and math.isfinite(item):
            size += 32
        else:
            _fail("Expected finite JSON value", origin)
        if size > total:
            _fail("JSON payload exceeds admission resource limit", origin, "unavailable")


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def _summary(value):
    if len(_canonical(value)) > MAX_SUMMARY_BYTES:
        _fail("Component summary exceeds 1 MiB", "/components", "unavailable")
    return value


def _origin(location, pointer):
    """Retain locations, never duplicate whole function bodies into summaries."""
    if location is None:
        return None
    if type(location) is not dict:
        _fail("Malformed compiler source origin", pointer, "unavailable")
    selected = {key: location[key] for key in ("path", "byte_offset", "byte_length", "line", "column", "column_unit") if key in location}
    if type(selected.get("path")) is not str or len(selected["path"]) > 4096:
        _fail("Missing or overlong compiler source path", pointer, "unavailable")
    for key in ("byte_offset", "byte_length", "line", "column"):
        if type(selected.get(key)) is not int or selected[key] < (1 if key in ("line", "column") else 0):
            _fail("Malformed compiler source position", pointer, "unavailable")
    _fixed(selected.get("column_unit"), "byte", pointer, "unavailable")
    return selected


def _catalog(catalog):
    _bounded(catalog, "/contract_profile", 4096, 16, 2048, MAX_CATALOG_BYTES)
    _keys(catalog, ("schema_version", "profile", "target", "engine", "parents", "limits",
                    "state_leaf_types", "extracted_declarations", "source_order_review",
                    "source_evidence", "unknown_contracts", "runtime_evidence", "generation"), "/contract_profile")
    _fixed(catalog["schema_version"], 1, "/contract_profile/schema_version")
    _fixed(catalog["profile"], PROFILE, "/binding/contract_profile", "unavailable")
    _fixed(catalog["target"], "enfusion", "/contract_profile/target")
    _fixed(catalog["engine"], {"version": ENGINE_VERSION, "sha256": ENGINE_SHA256}, "/contract_profile/engine", "stale_input")
    _fixed(catalog["parents"], {"descriptor": "ScriptComponentClass", "instance": "ScriptComponent"}, "/contract_profile/parents")
    _fixed(catalog["state_leaf_types"], ["bool", "i32", "f32"], "/contract_profile/state_leaf_types")
    _fixed(catalog["limits"], {"components": 16, "state_depth": 8, "fields_per_record": 64,
                              "expanded_state_fields": 256}, "/contract_profile/limits")
    _fixed(catalog["unknown_contracts"], {"lifetime": "unknown", "authority": "unknown",
                                          "reentrancy": "unknown", "callback_delivery": "unknown"}, "/contract_profile/unknown_contracts")
    _fixed(catalog["runtime_evidence"], {"status": "not_run", "receipts": []}, "/contract_profile/runtime_evidence")
    _fixed(catalog["generation"], "unavailable", "/contract_profile/generation")
    # A fixed catalog revision binds every declaration hash, line, review and
    # bound. A changed catalog requires a deliberate validator revision too.
    if hashlib.sha256(_canonical(catalog)).hexdigest() != CATALOG_CANONICAL_SHA256:
        _fail("Catalog content differs from the source-controlled revision", "/contract_profile", "stale_input")
    return catalog


def load_catalog(path, read, parse):
    """Load one exact installed catalog using the caller's bounded I/O helpers."""
    try:
        data = read(path)
        if type(data) is not bytes:
            _fail("Catalog reader must return bytes", "/contract_profile")
        if len(data) > MAX_CATALOG_BYTES:
            _fail("Catalog exceeds 64 KiB", "/contract_profile", "unavailable")
        value = parse(data)
        _catalog(value)
        if hashlib.sha256(data).hexdigest() != CATALOG_SHA256:
            _fail("Catalog bytes differ from the source-controlled revision", "/contract_profile", "stale_input")
        return value
    except ContractFailure:
        raise
    except Exception as exc:
        raise ContractFailure("Cannot load component catalog: " + str(exc),
                              getattr(exc, "status", "unavailable" if isinstance(exc, OSError) else "failure"),
                              "/contract_profile") from exc


def validate_components(config, catalog):
    """Validate component structure only; no source reads or execution."""
    _catalog(catalog)
    _bounded(config, "", 20000, 20, 4096, 3 * 1024 * 1024)
    _keys(config, ("schema_version", "name", "addon", "binding", "sources", "exports", "components"), "", ("$schema",))
    _fixed(config.get("schema_version"), 2, "/schema_version")
    binding = config.get("binding")
    _keys(binding, ("target", "version", "sha256", "contract_profile"), "/binding")
    _fixed(binding["target"], "enfusion", "/binding/target")
    _fixed(binding["contract_profile"], PROFILE, "/binding/contract_profile", "unavailable")
    _fixed(binding["version"], ENGINE_VERSION, "/binding/version", "stale_input")
    _fixed(binding["sha256"], ENGINE_SHA256, "/binding/sha256", "stale_input")
    components = config.get("components")
    if type(components) is not list or not 1 <= len(components) <= catalog["limits"]["components"]:
        _fail("Expected 1..16 components", "/components")
    exports = config.get("exports")
    if type(exports) is not list or len(exports) > 256:
        _fail("Expected bounded exports", "/exports")
    names = {}

    def reserve(name, origin):
        _text(name, origin)
        if name in catalog["parents"].values():
            _fail("Production identity conflicts with an admitted engine base class", origin)
        if name in names:
            _fail("Duplicate production class identity; first declared at " + names[name], origin)
        names[name] = origin

    export_sources = set()
    for i, export in enumerate(exports):
        origin = "/exports/" + str(i)
        if type(export) is not dict or "name" not in export:
            _fail("Export lacks public class name", origin + "/name")
        reserve(export["name"], origin + "/name")
        source = _text(export.get("source"), origin + "/source", True)
        if source in export_sources:
            _fail("Duplicate exported source declaration", origin + "/source")
        export_sources.add(source)
        methods = export.get("methods")
        if type(methods) is not list or len(methods) > 256:
            _fail("Expected bounded exported methods", origin + "/methods")
        method_names, method_sources = set(), set()
        for j, method in enumerate(methods):
            p = origin + "/methods/" + str(j)
            _keys(method, ("source", "name"), p)
            _text(method["name"], p + "/name")
            _text(method["source"], p + "/source", True)
            if method["name"] in method_names:
                _fail("Duplicate exported method identity", p + "/name")
            if method["source"] in method_sources:
                _fail("Duplicate exported method source", p + "/source")
            method_names.add(method["name"])
            method_sources.add(method["source"])
    result = []
    for i, component in enumerate(components):
        origin = "/components/" + str(i)
        _keys(component, ("descriptor", "instance", "state", "callbacks"), origin)
        for role in ("descriptor", "instance"):
            part = component[role]
            p = origin + "/" + role
            _keys(part, ("name", "parent"), p)
            reserve(part["name"], p + "/name")
            _fixed(part["parent"], catalog["parents"][role], p + "/parent")
        _text(component["state"], origin + "/state", True)
        callbacks = component["callbacks"]
        if type(callbacks) is not list or len(callbacks) > 3:
            _fail("Expected exactly the three admitted callbacks", origin + "/callbacks")
        seen, selected = set(), []
        for j, callback in enumerate(callbacks):
            p = origin + "/callbacks/" + str(j)
            _keys(callback, ("binding", "handler", "super_order"), p)
            name = callback["binding"]
            if type(name) is not str or name not in CALLBACKS:
                _fail("Callback binding is not admitted by this profile", p + "/binding", "unavailable")
            if name in seen:
                _fail("Duplicate callback binding", p + "/binding")
            seen.add(name)
            _fixed(callback["super_order"], CALLBACKS[name][1], p + "/super_order")
            _text(callback["handler"], p + "/handler", True)
            extracted = next(row for row in catalog["extracted_declarations"]["callbacks"] if row["binding"] == name)
            reviewed = next(row for row in catalog["source_order_review"]["callbacks"] if row["binding"] == name)
            selected.append({"binding": name, "handler": callback["handler"],
                             "super_order": callback["super_order"], "pointer": p,
                             "extracted_declaration": extracted, "source_order_review": reviewed})
        missing = sorted(set(CALLBACKS) - seen)
        if missing:
            _fail("Missing required callbacks: " + ", ".join(missing), origin + "/callbacks")
        result.append({"pointer": origin, "descriptor": component["descriptor"],
                       "instance": component["instance"], "state": component["state"],
                       "callbacks": selected})
    return _summary({"schema_version": 1, "stage": "component_admission", "status": "admitted_structure",
            "contract_profile": PROFILE, "catalog_sha256": CATALOG_SHA256,
            "engine_identity": {**catalog["engine"], "applicability": "declared_matches_catalog; local_not_checked"},
            "components": result, "source_origins": {"declarations": catalog["extracted_declarations"],
                                                      "review": catalog["source_order_review"],
                                                      "evidence": catalog["source_evidence"]},
            "unresolved_contracts": dict(catalog["unknown_contracts"]),
            "availability": {"structure": "admitted", "symbols": "not_checked", "targets": "not_checked",
                             "generation": "unavailable", "runtime_verification": "not_run", "promotion": "unavailable"},
            "handler_body_and_lifecycle": "not_verified", "execution": "not_run"})


def _context_index(context):
    _bounded(context, "/context", 100000, 32, 65536, 16 * 1024 * 1024)
    if type(context) is not dict:
        _fail("Expected checked compiler context envelope", "/context", "unavailable")
    for key, value in (("schema_version", 1), ("operation", "context.project"),
                       ("stage", "context"), ("status", "success"), ("execution", "not_run")):
        _fixed(context.get(key), value, "/context/" + key, "unavailable")
    _fixed(context.get("diagnostics"), [], "/context/diagnostics", "unavailable")
    for key in ("compiler_fingerprint", "source_fingerprint"):
        value = context.get(key)
        if type(value) is not str or not _HASH.fullmatch(value):
            _fail("Missing compiler/source snapshot identity", "/context/" + key, "unavailable")
    data = context.get("data")
    if type(data) is not dict or type(data.get("declarations")) is not list:
        _fail("Missing resolved declarations", "/context/data/declarations", "unavailable")
    declarations = data["declarations"]
    if len(declarations) > MAX_CONTEXT_DECLARATIONS:
        _fail("Context declaration limit exceeded", "/context/data/declarations", "unavailable")
    names, ids = {}, set()
    for i, declaration in enumerate(declarations):
        p = "/context/data/declarations/" + str(i)
        if type(declaration) is not dict:
            _fail("Malformed declaration", p, "unavailable")
        name, kind, identity = (declaration.get(key) for key in ("qualified_name", "kind", "declaration_id"))
        _text(name, p + "/qualified_name", True)
        if kind not in ("function", "struct", "enum", "constant", "trait"):
            _fail("Unsupported declaration kind", p + "/kind", "unavailable")
        expected = hashlib.sha256(("beryl.declaration.v1:" + kind + ":" + name).encode()).hexdigest()
        if identity != expected:
            _fail("Declaration identity does not match compiler identity contract", p + "/declaration_id", "unavailable")
        if name in names or identity in ids:
            _fail("Duplicate resolved declaration identity", p, "unavailable")
        names[name] = declaration
        ids.add(identity)
    return names


def _scalar(type_info, name):
    return (type(type_info) is dict and type_info.get("name") == name and
            "declaration" in type_info and type_info["declaration"] is None)


def _record(type_info, index, pointer):
    if type(type_info) is not dict:
        _fail("Expected resolved record type", pointer)
    name = type_info.get("declaration")
    if type(name) is not str or name not in index:
        _fail("Type lacks an exact loaded declaration identity", pointer)
    record = index[name]
    if record["kind"] != "struct" or type_info.get("name") != name:
        _fail("Expected exact resolved plain record type", pointer)
    return record


def _state(record, index, pointer, catalog):
    limits = catalog["limits"]
    active, memo = set(), {}

    def visit(current, depth):
        identity = current["declaration_id"]
        if current.get("generic_parameters") != []:
            _fail("State record requires explicit nongeneric compiler metadata", pointer, "unavailable")
        if depth > limits["state_depth"]:
            _fail("State nesting exceeds eight records", pointer, "unavailable")
        if identity in active:
            _fail("Recursive state records are not admitted", pointer)
        if identity in memo:
            count, height = memo[identity]
            if depth + height - 1 > limits["state_depth"]:
                _fail("State nesting exceeds eight records", pointer, "unavailable")
            return count, height
        fields = current.get("fields")
        if type(fields) is not list or len(fields) > limits["fields_per_record"]:
            _fail("State record requires at most 64 resolved fields", pointer, "unavailable")
        active.add(identity)
        count, height, names = 0, 1, set()
        for field in fields:
            if type(field) is not dict:
                _fail("Malformed resolved state field", pointer)
            name = field.get("name")
            _text(name, pointer)
            if name in names:
                _fail("Duplicate resolved state field", pointer)
            names.add(name)
            count += 1
            type_info = field.get("type")
            if any(_scalar(type_info, leaf) for leaf in catalog["state_leaf_types"]):
                continue
            child = _record(type_info, index, pointer)
            child_count, child_height = visit(child, depth + 1)
            count += child_count
            height = max(height, child_height + 1)
            if count > limits["expanded_state_fields"]:
                _fail("Expanded state exceeds 256 fields", pointer, "unavailable")
        active.remove(identity)
        if count > limits["expanded_state_fields"]:
            _fail("Expanded state exceeds 256 fields", pointer, "unavailable")
        memo[identity] = (count, height)
        return count, height

    count, height = visit(record, 1)
    return {"declaration_id": record["declaration_id"], "qualified_name": record["qualified_name"],
            "expanded_fields": count, "record_depth": height, "source": _origin(record.get("source"), pointer)}


def validate_symbols(config, catalog, context):
    """Resolve signatures from a checked exact context; never inspect behavior."""
    summary = validate_components(config, catalog)
    index = _context_index(context)
    for component in summary["components"]:
        origin = component["pointer"]
        record = index.get(component["state"])
        if record is None or record["kind"] != "struct" or record.get("visibility") != "public":
            _fail("State must resolve to a public record declaration", origin + "/state")
        component["resolved_state"] = _state(record, index, origin + "/state", catalog)
        for callback in component["callbacks"]:
            p = callback["pointer"] + "/handler"
            fn = index.get(callback["handler"])
            if fn is None or fn["kind"] != "function":
                _fail("Handler must resolve to a function declaration", p)
            if fn.get("visibility") != "public" or "receiver" not in fn or fn["receiver"] is not None:
                _fail("Handler must be public and have no receiver", p)
            if fn.get("generic_parameters") != []:
                _fail("Generic or unresolved handler signatures are not admitted", p)
            if not _scalar(fn.get("return_type"), "void"):
                _fail("Handler must return void", p)
            params = fn.get("parameters")
            frame = callback["binding"] == "ScriptComponent.EOnFrame"
            if type(params) is not list or len(params) != (2 if frame else 1):
                _fail("Handler parameter count differs from the callback contract", p)
            for param in params:
                if type(param) is not dict or param.get("is_self") is not False or "default" not in param or param["default"] is not None:
                    _fail("Handler parameters require explicit non-self arguments without defaults", p)
                _text(param.get("name"), p)
            state_param = params[0]
            if state_param.get("access_mode") != "inout":
                _fail("Handler first parameter must use inout state", p)
            target = _record(state_param.get("type"), index, p)
            if target["declaration_id"] != record["declaration_id"]:
                _fail("Handler state parameter resolves to a different declaration", p)
            if frame and (params[1].get("access_mode") != "let" or not _scalar(params[1].get("type"), "f32")):
                _fail("Frame handler second parameter must be let f32", p)
            callback["resolved_handler"] = {"declaration_id": fn["declaration_id"],
                                              "qualified_name": fn["qualified_name"], "source": _origin(fn.get("source"), p)}
    summary["status"] = "admitted_signatures"
    summary["availability"]["symbols"] = "admitted"
    summary["context_identity"] = {"compiler_fingerprint": context["compiler_fingerprint"],
                                   "source_fingerprint": context["source_fingerprint"]}
    return _summary(summary)
