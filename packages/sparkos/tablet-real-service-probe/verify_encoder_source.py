"""Source admission and extracted-format fixtures for the N1a scalar encoder.

No host, compiler, native process, engine or services execute. A small Python
denotation of the four extracted string expressions tests their field order,
nullable spellings and columns; it is not an EnforceScript interpreter.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tempfile
import types
from pathlib import Path

sys.dont_write_bytecode = True
PACKAGE = Path(__file__).resolve().parent
ROOT = PACKAGE.parents[2]
ENCODER_SHA256 = "1b4e462b4ce05e9c824a6fb41715ff02b22c1d0ad69fcd56f6af61c038100e9a"
FROZEN = {
    "observer.c.in": "fe8b9b38f4b7e6470652affdca79275aa00166eda634656c0b83f9af6259af3e",
    "wire.py": "39c0e05a13de39b4528cb99f969daafb71b0e2450c329fd47ef24b614fbb38f1",
    "wire-contract.json": "80abd295e0652346df82083ade1409731f3f0b3508a8cd75f09b6afe39920766",
    "oracle.py": "54b5b5a9816a39ed49abc89fd53db01ecb4b4318d5d9145bac1252e12fb96a88",
    "contract.json": "74aed85740e8d72b5c187eae9b537fffb921b90ec24ac0002500379897e8cd65",
}
MAX_BYTES = 65536
METHODS = ("Fail", "Boolean", "NullableBoolean", "Token", "Invocation", "CaseId", "Action",
           "EventCount", "ZeroText", "RowValid", "UpdateChecksum", "AppendRow", "SnapshotRow",
           "EventRow", "OutcomeRow", "InitRow", "EncodeInitialization", "Capture")
FORMATS = {
    "SnapshotRow": 'caseId + "|" + phase + "|" + role.ToString() + "|" + view.owner + "|" + view.state + "|" + view.mode.ToString() + "|" + view.accumulator + "|" + Token(view.ui) + "|" + Token(view.screen) + "|" + NullableBoolean(view.screen_enabled) + "|" + Token(view.widget)',
    "EventRow": 'caseId + "|event|" + serviceEvent.sequence.ToString() + "|" + serviceEvent.kind + "|" + Invocation(serviceEvent.invocation_id) + "|" + serviceEvent.owner + "|" + serviceEvent.state + "|" + Token(serviceEvent.screen) + "|" + serviceEvent.mode.ToString() + "|" + serviceEvent.accumulator + "|" + Token(serviceEvent.argument_owner) + "|" + NullableBoolean(serviceEvent.returned) + "|" + Boolean(serviceEvent.enabled) + "|" + Token(serviceEvent.widget)',
    "OutcomeRow": 'record.case_id + "|outcome|" + record.action + "|" + arguments + "|" + record.outcome.kind + "|" + value',
    "InitRow": 'sequence.ToString() + "|" + witness.token.ToString() + "|" + witness.stage + "|" + Boolean(witness.owner_matches) + "|" + Boolean(witness.owner_world_present) + "|" + Boolean(witness.game_world_present) + "|" + Boolean(witness.owner_is_game_world) + "|" + Boolean(witness.state_present) + "|" + Boolean(witness.same_state) + "|" + Boolean(witness.independence_observed) + "|" + Boolean(witness.independent_state) + "|" + witness.mode.ToString() + "|" + accumulator + "|" + witness.mask.ToString() + "|" + Boolean(witness.ui_absent) + "|" + Boolean(witness.screen_absent)',
}


class SourceFailure(ValueError):
    pass


def require(condition, detail):
    if not condition:
        raise SourceFailure(detail)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read(path):
    with Path(path).open("rb") as stream:
        data = stream.read(MAX_BYTES + 1)
    require(len(data) <= MAX_BYTES, "Bounded source read exceeded")
    return data


def mask(text):
    return re.sub(r'//[^\n]*|/\*[\s\S]*?\*/|"(?:\\.|[^"\\])*"',
                  lambda m: "".join("\n" if c == "\n" else " " for c in m[0]), text)


def body(text, name):
    code = mask(text)
    match = re.search(r'\bstatic\s+[\w<>]+\s+' + re.escape(name) + r'\s*\([^)]*\)\s*\{', code)
    require(match is not None, "Missing/changed encoder method: " + name)
    start = match.end()
    depth = 1
    cursor = start
    while cursor < len(code) and depth:
        depth += (code[cursor] == "{") - (code[cursor] == "}")
        cursor += 1
    require(depth == 0, "Unbalanced encoder method")
    return text[start:cursor - 1]


def expression(text, name):
    field = "row" if name == "InitRow" else "payload"
    method = body(text, name)
    found = re.findall(r'(?m)^\t\t(?:string )?' + field + r' (=|\+=) ([^;\n]+);', method)
    require(found and found[0][0] == "=" and all(op == "+=" for op, _ in found[1:]), "Missing/duplicate sequential field initialization: " + name)
    require(len(found) == len(re.findall(r'\b' + field + r'\s*(?:=|\+=)', mask(method))), "Unaccounted format mutation")
    require(all(len(re.findall(r' \+ ', expr)) <= 2 for _, expr in found), "Enforce field formula exceeds admitted complexity")
    return " + ".join(expr for _, expr in found)


def validate_source(data, *, pin=True):
    require(type(data) is bytes and 0 < len(data) <= MAX_BYTES, "Encoder byte/source bound")
    require(b"\r" not in data and b"\0" not in data, "Encoder must be LF text without NUL")
    try:
        text = data.decode("utf8")
    except UnicodeError as exc:
        raise SourceFailure("Encoder is not UTF-8") from exc
    code = mask(text)
    require(not re.search(r"\bSPK_BerylN1ServiceEvent\s+event\b", code), "Reserved Enforce event identifier")
    require("@" not in code, "Encoder has unsupported placeholders")
    require(re.findall(r'\bstatic\s+[\w<>]+\s+(\w+)\s*\([^)]*\)\s*\{', code) == list(METHODS), "Encoder method inventory changed")
    fields = re.findall(r'\b(?:bool|int|string|ref array<string>)\s+(\w+)\s*(?:=[^;]+)?;', text.split("class SPK_BerylN1WireEncoder")[0])
    require(fields == ["complete", "outside_domain", "failure", "checksum", "row_count", "raw_bytes", "init_checksum", "init_count", "owner_count", "rows", "caseIds", "init_rows"], "Receipt API fields changed")
    require(re.findall(r'\bnew\s+(\w+)\s*\(', code) == ["SPK_BerylN1WireReceipt"], "Encoder allocates a non-scalar/native object")
    require(not re.search(r'\b(?:Get\w+|Set\w+|RunSevenActions|Focus|Unfocus|SetHeld|Enable|Disable|Destroy|Open|Close|OnPostInit|EOnFrame|OnDelete|SpawnEntityPrefab|CallLater|Sleep)\s*\(', code), "Encoder performs native/service/state/async operation")
    require(not re.search(r'SPK_BerylTabletRealServiceRegistry\.\w+\s*(?:=(?!=)|\+\+|--|\+=|-=)', code), "Encoder mutates registry state")
    require(not re.search(r's_(?:Owners|States|Observers)\s*\[', code), "Encoder indexes a native owner/state/component")
    require(not re.search(r'\b(?:view|serviceEvent|record|witness)\.[\w.]+\s*(?:=(?!=)|\+\+|--|\+=|-=)', code), "Encoder mutates captured logical records")
    allowed = set(METHODS) | {"Count", "Insert", "Length", "ToAscii", "ToString", "SPK_BerylN1WireReceipt", "if", "for", "while", "return"}
    calls = set(re.findall(r'\b(\w+)\s*\(', code))
    require(calls <= allowed, "Encoder call path contains an unreviewed operation: " + repr(sorted(calls - allowed)))
    for name, bound in (("MAX_ROWS", 44), ("MAX_ROW_BYTES", 512), ("MAX_RAW_BYTES", 32768), ("MAX_ZERO_BYTES", 48), ("MODULUS", 1000003)):
        require(f"static const int {name} = {bound};" in text, "Encoder declared bound differs: " + name)
    require('PROFILE = "sparkos.tablet.real-services.n1a.wire.v1";' in text and 'WIRE_CONTRACT_SHA256 = "' + FROZEN["wire-contract.json"] + '";' in text, "Encoder wire identity changed")
    for name, expected in FORMATS.items():
        require(expression(text, name) == expected, "Field formatting/order differs: " + name)
    for name, columns in (("SnapshotRow", 12), ("EventRow", 15), ("OutcomeRow", 7)):
        require(f"return AppendRow(result, payload, {columns});" in body(text, name), "Encoder exact columns differ: " + name)
    anchors = {
        "Boolean": ['if (value) return "1";', 'return "0";'],
        "NullableBoolean": ['if (!value) return "none";', 'return Boolean(value.value);'],
        "Token": ['if (!value) return "none";', 'return value.value;'],
        "Invocation": ['if (!value) return "none";', 'return value.value.ToString();'],
        "ZeroText": ["size < 1 || size > MAX_ZERO_BYTES", "text.ToAscii(cursor) != 48", "cursor == decimalStart", "cursor == exponentStart", "return cursor == size;"],
        "RowValid": ["size < 1 || size > MAX_ROW_BYTES", "value < 32 || value > 126", "value == 124", "return actualColumns == columns;"],
        "UpdateChecksum": ["checksum = (checksum * 31 + row.ToAscii(i)) % MODULUS;", "return (checksum * 31 + 10) % MODULUS;"],
        "AppendRow": ["result.rows.Count() >= MAX_ROWS", "result.rows.Count() + 1", 'string row = sequence.ToString();', 'row += "|";', 'row += payload;', "!RowValid(row, columns)", "result.raw_bytes + row.Length() + 1 > MAX_RAW_BYTES", "result.rows.Insert(row);", "result.checksum = UpdateChecksum(result.checksum, row);", "result.row_count = result.rows.Count();"],
        "SnapshotRow": ["view.owner != owner", "view.state != state", "view.mode < 0 || view.mode > 1", "!ZeroText(view.accumulator) || view.ui", 'view.screen.value != "screen.1"', "!view.screen_enabled", "!view.screen && (view.screen_enabled || view.widget)", 'view.widget.value != "widget.1"'],
        "EventRow": ["serviceEvent.sequence != sequence", "sequence > 9", 'serviceEvent.owner != "owner.1"', 'serviceEvent.state != "state.1"', 'serviceEvent.screen.value != "screen.1"', "!ZeroText(serviceEvent.accumulator)", 'serviceEvent.argument_owner.value != "owner.1"', 'serviceEvent.kind == "screen.enable.exit" && !serviceEvent.returned', 'serviceEvent.kind != "screen.enable.exit" && serviceEvent.returned', 'serviceEvent.kind == "screen.create" && serviceEvent.invocation_id', "serviceEvent.invocation_id.value > 4"],
        "OutcomeRow": ['record.outcome.kind != "return"', "record.action != Action(index)", "record.arguments.Count() != 1", "record.arguments[0] != (index == 1 || index == 2)", "record.arguments.Count() != 0", "index == 6 && record.outcome.value", "index != 6 && !record.outcome.value", 'string value = "void";', "Boolean(record.outcome.value.value)"],
        "InitRow": ["index >= 2", "index == 1 || index == 3", "witness.token != token", "witness.stage != stage", "!witness.owner_matches", "!witness.owner_world_present", "!witness.game_world_present", "!witness.owner_is_game_world", "!witness.state_present", "!witness.same_state", "witness.independence_observed != (token == 2)", "witness.independent_state != (token == 2)", "witness.mode != 0", "witness.accumulator != 0", "witness.mask < 0", "!witness.ui_absent", "!witness.screen_absent", "(witness.mask & EntityEvent.FRAME) == 0", "witness.accumulator.ToString()", "!RowValid(row, 16)", "result.init_rows.Count() >= 4", "result.init_checksum = UpdateChecksum(result.init_checksum, row);"],
        "EncodeInitialization": ["result.complete || result.init_count != 0", "result.init_checksum != 0", "result.init_rows.Count() != 0", "s_InitWitnesses.Count() != 4", "initIndex < 4", "result.outside_domain = SPK_BerylTabletRealServiceRegistry.s_OutsideDomain;", "return result.init_count == 4;"],
        "Capture": ["s_Failure", "result.outside_domain = SPK_BerylTabletRealServiceRegistry.s_OutsideDomain;", "!SPK_BerylTabletRealServiceRegistry.s_Completed", "!SPK_BerylTabletRealServiceRegistry.s_RunRequested", "s_Running", "s_Observing", "s_OutsideDomain", "s_PendingToken != 0", "result.owner_count != 2", "s_States.Count() != 2", "s_Observers.Count() != 2", "s_InitWitnesses.Count() != 4", "s_Records.Count() != 7", "s_Events.Count() != 9", "s_InvocationCount != 4", "!EncodeInitialization(result)", "index < 7", "record.case_id != CaseId(index)", "record.before.Count() != 2", "record.after.Count() != 2", "record.services.Count() != EventCount(index)", "record.services[eventIndex] != SPK_BerylTabletRealServiceRegistry.s_Events[eventSequence - 1]", "result.row_count != MAX_ROWS", "result.init_count != 4", "result.caseIds.Count() != 7", "eventSequence != 9", "result.complete = true;"],
    }
    for name, markers in anchors.items():
        source_body = body(text, name)
        for marker in markers:
            present = marker in source_body
            if marker[-1].isdigit():
                present = re.search(re.escape(marker) + r"(?![0-9])", source_body) is not None
            require(present, "Missing/changed source contract anchor: " + name + ": " + marker)
    capture = body(text, "Capture")
    order = [capture.find(marker) for marker in ('"before", beforeRole', "EventRow(result,", "OutcomeRow(result,", '"after", afterRole', "result.caseIds.Insert(record.case_id);", "result.complete = true;")]
    require(all(index >= 0 for index in order) and order == sorted(order), "Capture row/effect order changed")
    require("result.complete = true" not in body(text, "EncodeInitialization"), "Initialization falsely marks seven actions complete")
    require(text.count("result.complete = true;") == 1, "Extra successful-completion publication")
    for index, case_id in enumerate(("n1a.focus-refused.stowed", "n1a.held.first", "n1a.held.repeated", "n1a.unfocus-refused.held", "n1a.stow", "n1a.stow.repeated", "n1a.independent-state")):
        require(f'if (index == {index}) return "{case_id}";' in body(text, "CaseId"), "Case identity/order changed")
    if pin:
        require(sha(data) == ENCODER_SHA256, "Encoder source bytes differ from frozen revision")
    return dict(status="source_admitted", sha256=sha(data), bytes=len(data), rows=44,
                init_rows=4, init_columns=16, runtime="not_run", compilation="not_run",
                numeric_encoding="stored_numeric_zero_text_only", native_lifetime="not_proven")


def extract_format(text, name, values):
    """Evaluate only a checked concatenation expression, never arbitrary code."""
    source = expression(text, name)
    parts = re.split(r' \+ (?=(?:[^"\\]*(?:\\.[^"\\]*)*"[^"\\]*(?:\\.[^"\\]*)*")*[^"\\]*(?:\\.[^"\\]*)*$)', source)
    def lookup(path):
        bits = path.split(".")
        value = values[bits[0]]
        for key in bits[1:]:
            value = value[key]
        return value
    def term(value):
        if value.startswith('"'):
            parsed = json.loads(value)
            require(type(parsed) is str, "Literal format term must be string")
            return parsed
        match = re.fullmatch(r'(Boolean|NullableBoolean|Token|Invocation)\(([\w.]+)\)', value)
        if match:
            item = lookup(match[2])
            if match[1] == "Boolean":
                require(type(item) is bool, "Boolean format needs actual Boolean")
                return "1" if item else "0"
            if item is None:
                return "none"
            if match[1] == "NullableBoolean":
                require(type(item) is bool, "NullableBoolean needs literal Boolean")
                return "1" if item else "0"
            if match[1] == "Invocation":
                require(type(item) is int, "Invocation format needs actual integer")
                return str(item)
            require(type(item) is str, "Token format needs actual string")
            return item
        match = re.fullmatch(r'([\w.]+)\.ToString\(\)', value)
        if match:
            item = lookup(match[1])
            require(type(item) is int, "Integer formatting is bounded typed decimal")
            return str(item)
        require(re.fullmatch(r'[\w.]+', value) is not None, "Unsupported extracted-format term")
        item = lookup(value)
        require(type(item) is str, "Plain format term must be literal text")
        return item
    return "".join(term(part.strip()) for part in parts)


def load_frozen(name, data):
    require(sha(data) == FROZEN[name], "Stale checked source: " + name)
    module = types.ModuleType("n1a_encoder_" + name.replace(".", "_"))
    module.__file__ = str(PACKAGE / name)
    exec(compile(data, module.__file__, "exec"), module.__dict__)
    return module


def self_test(data, inputs):
    text = data.decode("utf8")
    wire = load_frozen("wire.py", inputs["wire.py"])
    oracle = load_frozen("oracle.py", inputs["oracle.py"])
    typed_identity = oracle.expected_identity("a" * 64, "b" * 64, FROZEN["contract.json"])
    expected = wire.expected_identity(typed_identity, FROZEN["wire-contract.json"])
    cases = []
    def case(case_id, fn):
        require(case_id not in [value["id"] for value in cases], "Duplicate case identity")
        try:
            evidence = fn()
            cases.append(dict(id=case_id, status="success", evidence=evidence))
        except Exception as exc:
            cases.append(dict(id=case_id, status="failure", error=type(exc).__name__, detail=str(exc)))
    case("positive.frozen-source-admission", lambda: validate_source(data))
    case("positive.unpinned-structural-admission", lambda: validate_source(data, pin=False))
    def synthetic(branch, zero="0"):
        typed = oracle.evaluate([value == "T" for value in branch], typed_identity)
        rows = []
        def append(payload):
            rows.append(str(len(rows) + 1) + "|" + payload)
        for record in typed["records"]:
            for phase in ("before", "after"):
                for view in record[phase]:
                    view["accumulator"] = zero
            for event in record["services"]:
                event["accumulator"] = zero
            for role, view in enumerate(record["before"], 1):
                append(extract_format(text, "SnapshotRow", dict(caseId=record["case_id"], phase="before", role=role, view=view)))
            for event in record["services"]:
                append(extract_format(text, "EventRow", dict(caseId=record["case_id"], serviceEvent=event)))
            arguments = "none" if not record["arguments"] else ("1" if record["arguments"][0] else "0")
            value = "void" if record["outcome"]["value"] is None else ("1" if record["outcome"]["value"] else "0")
            append(extract_format(text, "OutcomeRow", dict(record=record, arguments=arguments, value=value)))
            for role, view in enumerate(record["after"], 1):
                append(extract_format(text, "SnapshotRow", dict(caseId=record["case_id"], phase="after", role=role, view=view)))
        typed["checksum"] = oracle.checksum(typed["records"])
        reference = wire.encode(typed, expected)
        require(rows == reference["rows"], "Native extracted expression fields differ from independent codec")
        require(len(rows) == 44 and [len(row.split("|")) for row in rows].count(12) == 28 and [len(row.split("|")) for row in rows].count(15) == 9 and [len(row.split("|")) for row in rows].count(7) == 7, "Wrong analytical columns/counts")
        require(rows[0] == "1|n1a.focus-refused.stowed|before|1|owner.1|state.1|0|" + zero + "|none|none|none|none", "First literal snapshot anchor")
        require(rows[2] == "3|n1a.focus-refused.stowed|outcome|Focus|none|return|0", "Literal refused outcome anchor")
        require(rows[41] == "42|n1a.independent-state|outcome|Observe|none|return|void", "Literal final void anchor")
        total = 0
        for row in rows:
            for byte in row.encode("ascii") + b"\n":
                total = (total * 31 + byte) % 1000003
        require(total == reference["checksum"], "Independent LF ASCII checksum differs")
        wire.decode(dict(reference, rows=rows, checksum=total), expected)
        return dict(branch=branch, zero_text=zero, rows=44, checksum=total,
                    scope="extracted concatenation denotation; native engine not run")
    for branch in ("FF", "FT", "TT"):
        case("positive.extracted-format." + branch, lambda branch=branch: synthetic(branch))
    for index, zero in enumerate(("-0", "0.000", "-0.0e-8")):
        case("positive.raw-zero-preserved." + str(index), lambda zero=zero: synthetic("TT", zero))
    def init_format():
        rows = []
        for index in range(4):
            token = 1 if index < 2 else 2
            stage = "init.before" if index % 2 == 0 else "init.after"
            witness = dict(token=token, stage=stage, owner_matches=True, owner_world_present=True,
                game_world_present=True, owner_is_game_world=True, state_present=True, same_state=True,
                independence_observed=token == 2, independent_state=token == 2, mode=0,
                mask=0 if index % 2 == 0 else 4, ui_absent=True, screen_absent=True)
            row = extract_format(text, "InitRow", dict(sequence=index + 1, witness=witness, accumulator="0"))
            require(len(row.split("|")) == 16, "Native init witness columns differ")
            rows.append(row)
        require(rows[0] == "1|1|init.before|1|1|1|1|1|1|0|0|0|0|0|1|1", "Literal first init witness anchor")
        require(rows[3] == "4|2|init.after|1|1|1|1|1|1|1|1|0|0|4|1|1", "Literal last init witness anchor")
        return dict(rows=rows, checksum=wire.checksum(rows), scope="synthetic scalar init format; actual mask not inferred")
    case("positive.init-format-and-independent-checksum", init_format)
    def change(old, new):
        require(data.count(old.encode()) == 1, "Source mutation selector must be exact")
        return data.replace(old.encode(), new.encode(), 1)
    def reject(candidate, pin=False):
        require(candidate != data, "Unchanged mutant is not a negative fixture")
        try:
            validate_source(candidate, pin=pin)
        except SourceFailure as exc:
            return dict(detected=str(exc), pinned=pin)
        raise AssertionError("Deliberate encoder source fault admitted")
    mutations = (
        ("snapshot-columns", "return AppendRow(result, payload, 12);", "return AppendRow(result, payload, 11);"),
        ("reserved-event-identifier", "SPK_BerylN1ServiceEvent serviceEvent)", "SPK_BerylN1ServiceEvent event)"),
        ("complex-field-formula", "string payload = caseId;\n\t\tpayload += \"|\";\n\t\tpayload += phase;", "string payload = caseId + \"|\" + \"x\" + \"|\" + \"y\";\n\t\tpayload += \"|\";\n\t\tpayload += phase;"),
        ("event-columns", "return AppendRow(result, payload, 15);", "return AppendRow(result, payload, 14);"),
        ("outcome-columns", "return AppendRow(result, payload, 7);", "return AppendRow(result, payload, 8);"),
        ("init-columns", "!RowValid(row, 16)", "!RowValid(row, 15)"),
        ("snapshot-token-order", 'payload += view.owner;\n\t\tpayload += "|";\n\t\tpayload += view.state;', 'payload += view.state;\n\t\tpayload += "|";\n\t\tpayload += view.owner;'),
        ("event-return-forged", "NullableBoolean(serviceEvent.returned)", '"0"'),
        ("event-boolean-text", "Boolean(serviceEvent.enabled)", "serviceEvent.enabled.ToString()"),
        ("nullable-boolean-text", 'if (!value) return "none";\n\t\treturn Boolean(value.value);', 'if (!value) return "null";\n\t\treturn Boolean(value.value);'),
        ("checksum-newline", "return (checksum * 31 + 10) % MODULUS;", "return checksum;"),
        ("checksum-multiplier", "checksum = (checksum * 31 + row.ToAscii(i)) % MODULUS;", "checksum = (checksum * 32 + row.ToAscii(i)) % MODULUS;"),
        ("sequence-zero", "int sequence = result.rows.Count() + 1;", "int sequence = result.rows.Count();"),
        ("row-budget", "static const int MAX_ROWS = 44;", "static const int MAX_ROWS = 45;"),
        ("byte-budget", "static const int MAX_RAW_BYTES = 32768;", "static const int MAX_RAW_BYTES = 65536;"),
        ("zero-budget", "static const int MAX_ZERO_BYTES = 48;", "static const int MAX_ZERO_BYTES = 500;"),
        ("ascii-guard", "value < 32 || value > 126", "value < 0 || value > 255"),
        ("row-size-guard", "size < 1 || size > MAX_ROW_BYTES", "size < 1"),
        ("total-size-guard", "result.raw_bytes + row.Length() + 1 > MAX_RAW_BYTES", "false"),
        ("owner-getter", "int eventSequence;", "GetOwner();\n\t\tint eventSequence;"),
        ("game-getter", "int eventSequence;", "GetGame();\n\t\tint eventSequence;"),
        ("service-call", "int eventSequence;", "Enable(null);\n\t\tint eventSequence;"),
        ("public-action", "int eventSequence;", "RunSevenActions();\n\t\tint eventSequence;"),
        ("callback-call", "int eventSequence;", "OnDelete(null);\n\t\tint eventSequence;"),
        ("native-owner-deref", "int eventSequence;", "SPK_BerylTabletRealServiceRegistry.s_Owners[0].ToString();\n\t\tint eventSequence;"),
        ("logical-record-write", "int eventSequence;", "record.action = \"Focus\";\n\t\tint eventSequence;"),
        ("registry-reset", "int eventSequence;", "SPK_BerylTabletRealServiceRegistry.s_Completed = true;\n\t\tint eventSequence;"),
        ("unreviewed-helper", "int eventSequence;", "Unreviewed();\n\t\tint eventSequence;"),
        ("outside-domain-forged", "result.outside_domain = SPK_BerylTabletRealServiceRegistry.s_OutsideDomain;\n\t\t\treturn result;", "result.outside_domain = false;\n\t\t\treturn result;"),
        ("incomplete-success", "!SPK_BerylTabletRealServiceRegistry.s_Completed", "false"),
        ("record-bound", "s_Records.Count() != 7", "s_Records.Count() != 6"),
        ("event-bound", "s_Events.Count() != 9", "s_Events.Count() != 8"),
        ("pair-bound", "s_InvocationCount != 4", "s_InvocationCount != 3"),
        ("record-order", "record.case_id != CaseId(index)", "false"),
        ("service-cardinality", "record.services.Count() != EventCount(index)", "false"),
        ("successful-row-count", "result.row_count != MAX_ROWS", "false"),
        ("successful-prefix", "eventSequence != 9", "false"),
        ("init-order", "witness.stage != stage", "false"),
        ("init-world", "!witness.owner_is_game_world", "false"),
        ("init-state", "!witness.same_state", "false"),
        ("init-independence", "witness.independent_state != (token == 2)", "false"),
        ("init-mask", "(witness.mask & EntityEvent.FRAME) == 0", "false"),
        ("init-snapshot-columns", 'row += Boolean(witness.ui_absent);\n\t\trow += "|";\n\t\trow += Boolean(witness.screen_absent);', 'row += Boolean(witness.screen_absent);\n\t\trow += "|";\n\t\trow += Boolean(witness.ui_absent);'),
        ("init-helper-false-complete", "return result.init_count == 4;", "result.complete = true;\n\t\treturn result.init_count == 4;"),
        ("void-value", 'string value = "void";', 'string value = "none";'),
        ("set-held-argument", "record.arguments[0] != (index == 1 || index == 2)", "false"),
        ("missing-actual-return", 'serviceEvent.kind == "screen.enable.exit" && !serviceEvent.returned', "false"),
        ("unknown-invocation", "serviceEvent.invocation_id.value > 4", "serviceEvent.invocation_id.value > 400"),
        ("unknown-screen", 'view.screen.value != "screen.1"', 'view.screen.value != "screen.2"'),
        ("unknown-case", 'if (index == 6) return "n1a.independent-state";', 'if (index == 6) return "n1a.unknown";'),
    )
    for name, old, new in mutations:
        case("negative." + name, lambda old=old, new=new: reject(change(old, new)))
    case("negative.nonbytes", lambda: reject(data.decode()))
    case("negative.byte-limit", lambda: reject(data + b" " * MAX_BYTES))
    case("negative.crlf", lambda: reject(data.replace(b"\n", b"\r\n")))
    case("negative.nul", lambda: reject(data + b"\0"))
    case("negative.unpinned-whitespace", lambda: reject(data + b"\n", pin=True))
    return cases


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", required=True, action="store_true")
    parser.parse_args()
    owned = Path(tempfile.mkdtemp(prefix="tablet-real-service-encoder-", dir=ROOT / "build"))
    result = dict(schema_version=1, operation="n1a.encoder.source-admission", status="failure",
                  scope="source and extracted-expression synthetic fixtures only", host="not_run",
                  compiler="not_run", engine="not_run", native_callbacks="not_run", cases=[])
    try:
        files = {name: read(PACKAGE / name) for name in ["encoder.c.in", "verify_encoder_source.py"] + list(FROZEN)}
        for name, data in files.items():
            path = owned / name
            require(path.write_bytes(data) == len(data) and read(path) == data, "Retained source write/readback failed")
        result["retained"] = [dict(path=name, bytes=len(data), sha256=sha(data)) for name, data in files.items()]
        for name, digest in FROZEN.items():
            require(sha(files[name]) == digest, "Source dependency changed: " + name)
        result["admission"] = validate_source(files["encoder.c.in"])
        result["cases"] = self_test(files["encoder.c.in"], files)
        result["expected_case_ids"] = [value["id"] for value in result["cases"]]
        result["passed_cases"] = sum(value["status"] == "success" for value in result["cases"])
        result["failed_cases"] = len(result["cases"]) - result["passed_cases"]
        for name, data in files.items():
            require(read(PACKAGE / name) == data, "Source changed during gate: " + name)
        result["status"] = "success" if result["failed_cases"] == 0 else "failure"
    except Exception as exc:
        result["error"] = dict(kind=type(exc).__name__, detail=str(exc))
    receipt = owned / "result.json"
    serialized = json.dumps(result, indent=2, sort_keys=True, ensure_ascii=True).encode("ascii") + b"\n"
    require(receipt.write_bytes(serialized) == len(serialized) and read(receipt) == serialized, "Receipt write/readback failed")
    print(json.dumps(dict(status=result["status"], receipt=str(receipt), sha256=sha(serialized),
                         passed=result.get("passed_cases", 0), failed=result.get("failed_cases", 0))))
    return 0 if result["status"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
