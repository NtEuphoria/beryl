"""Proposed ASCII N1a wire codec; typed semantic evidence, no native provenance."""
from __future__ import annotations

import copy
import hashlib
import json
import re
import types
from decimal import Decimal, InvalidOperation
from pathlib import Path

PROFILE = "sparkos.tablet.real-services.n1a.wire.v1"
ORACLE_SHA256 = "54b5b5a9816a39ed49abc89fd53db01ecb4b4318d5d9145bac1252e12fb96a88"
SOURCE_CONTRACT_SHA256 = "74aed85740e8d72b5c187eae9b537fffb921b90ec24ac0002500379897e8cd65"
MAX_ROW_BYTES = 512
MAX_RAW_BYTES = 32768
ROW_COUNT = 44
CASE_IDS = ("n1a.focus-refused.stowed", "n1a.held.first", "n1a.held.repeated",
            "n1a.unfocus-refused.held", "n1a.stow", "n1a.stow.repeated", "n1a.independent-state")
EVENT_COUNTS = (0, 3, 2, 0, 2, 2, 0)
IDENTITY_KEYS = {"schema_version", "profile", "token", "source_sha256",
                 "source_contract_sha256", "wire_contract_sha256"}
COMPLETE_KEYS = IDENTITY_KEYS | {"status", "failure", "executed", "failures", "caseIds",
                                "row_count", "checksum", "rows"}
INT = re.compile(r"(?:0|[1-9][0-9]{0,7})\Z")
FLOAT = re.compile(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?\Z")
_ORACLE_CACHE = None


class WireFailure(ValueError):
    """Malformed or mismatched raw wire, distinct from lifetime admission."""


def _require(condition, detail):
    if not condition:
        raise WireFailure(detail)


def _keys(value, keys, detail):
    _require(type(value) is dict and set(value) == keys, detail)


def _hash(value):
    return type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _oracle():
    global _ORACLE_CACHE
    path = Path(__file__).with_name("oracle.py")
    with path.open("rb") as stream:
        data = stream.read(128 * 1024 + 1)
    _require(len(data) <= 128 * 1024 and hashlib.sha256(data).hexdigest() == ORACLE_SHA256,
             "Unsupported oracle source revision")
    if _ORACLE_CACHE is not None:
        return _ORACLE_CACHE
    # Compile exactly the hash-checked bytes, rather than rereading the path.
    module = types.ModuleType("n1a_frozen_original_source_oracle")
    module.__file__ = str(path)
    exec(compile(data, str(path), "exec"), module.__dict__)
    _ORACLE_CACHE = module
    return module


def validate_identity(expected):
    _keys(expected, IDENTITY_KEYS, "Expected wire identity must have six exact fields")
    _require(type(expected["schema_version"]) is int and expected["schema_version"] == 1, "Wrong integer schema")
    _require(type(expected["profile"]) is str and expected["profile"] == PROFILE, "Wrong wire profile")
    for key in ("token", "source_sha256", "source_contract_sha256", "wire_contract_sha256"):
        _require(_hash(expected[key]), "Invalid wire identity: " + key)
    _require(expected["source_contract_sha256"] == SOURCE_CONTRACT_SHA256, "Unsupported typed source contract")


def expected_identity(typed_expected, wire_contract_sha256):
    oracle = _oracle()
    oracle.validate_identity(typed_expected)
    expected = dict(typed_expected, profile=PROFILE, wire_contract_sha256=wire_contract_sha256)
    validate_identity(expected)
    return expected


def _typed_identity(expected, oracle):
    return {key: oracle.PROFILE if key == "profile" else expected[key] for key in oracle.IDENTITY_KEYS}


def checksum(rows):
    _require(type(rows) is list and len(rows) <= ROW_COUNT, "Unbounded raw row array")
    total = 0
    aggregate = 0
    for row in rows:
        _require(type(row) is str, "Raw row must be literal ASCII text")
        try:
            data = row.encode("ascii")
        except UnicodeError as exc:
            raise WireFailure("Non-ASCII raw row") from exc
        _require(0 < len(data) <= MAX_ROW_BYTES and b"\r" not in data and b"\n" not in data and
                 all(32 <= byte <= 126 for byte in data), "Invalid raw row byte/size")
        aggregate += len(data) + 1
        _require(aggregate <= MAX_RAW_BYTES, "Raw row byte budget exhausted")
        for byte in data + b"\n":
            total = (31 * total + byte) % 1000003
    return total


def _int(text, minimum, maximum):
    _require(INT.fullmatch(text) is not None, "Noncanonical integer text")
    value = int(text)
    _require(minimum <= value <= maximum, "Integer outside field bounds")
    return value


def _bool(text, nullable=False):
    if nullable and text == "none":
        return None
    _require(text in ("0", "1"), "Boolean wire must be exact 0/1")
    return text == "1"


def _token(text, kind, nullable=False):
    if nullable and text == "none":
        return None
    allowed = {"owner": ("owner.1", "owner.2"), "state": ("state.1", "state.2"),
               "screen": ("screen.1",), "widget": ("widget.1",), "ui": ()}
    _require(text in allowed[kind], "Unknown " + kind + " fixture token")
    return text


def _zero(text):
    _require(len(text) <= 48 and FLOAT.fullmatch(text) is not None, "Invalid rounded accumulator text")
    try:
        value = Decimal(text)
    except InvalidOperation as exc:
        raise WireFailure("Invalid finite accumulator") from exc
    _require(value.is_finite() and value == 0, "N1a accumulator is not numeric zero")
    return text  # Preserve original rounded text; never infer a bit/signed-zero encoding.


def _value(value, null="none"):
    if value is None:
        return null
    if type(value) is bool:
        return "1" if value else "0"
    return str(value)


def encode(typed, expected):
    validate_identity(expected)
    oracle = _oracle()
    oracle.validate(typed, _typed_identity(expected, oracle))
    rows = []
    def append(fields):
        rows.append("|".join([str(len(rows) + 1)] + fields))
    def snapshot(case_id, phase, role, value):
        append([case_id, phase, str(role)] + [_value(value[key]) for key in
            ("owner", "state", "mode", "accumulator", "ui", "screen", "screen_enabled", "widget")])
    for record in typed["records"]:
        case_id = record["case_id"]
        for role, view in enumerate(record["before"], 1):
            snapshot(case_id, "before", role, view)
        for event in record["services"]:
            append([case_id, "event"] + [_value(event[key]) for key in
                ("sequence", "kind", "invocation_id", "owner", "state", "screen", "mode",
                 "accumulator", "argument_owner", "returned", "enabled", "widget")])
        arguments = _value(record["arguments"][0]) if record["arguments"] else "none"
        append([case_id, "outcome", record["action"], arguments, record["outcome"]["kind"],
                _value(record["outcome"]["value"], null="void")])
        for role, view in enumerate(record["after"], 1):
            snapshot(case_id, "after", role, view)
    _require(len(rows) == ROW_COUNT, "Incomplete encoded row count")
    return dict(expected, status="complete", failure=None, executed=7, failures=0,
                caseIds=list(CASE_IDS), row_count=ROW_COUNT, checksum=checksum(rows), rows=rows)


def decode(actual, expected):
    validate_identity(expected)
    _keys(actual, COMPLETE_KEYS, "Unknown or missing wire completion field")
    for key in IDENTITY_KEYS:
        _require(type(actual[key]) is type(expected[key]) and actual[key] == expected[key],
                 "Stale wire identity: " + key)
    _require(type(actual["status"]) is str and actual["status"] == "complete" and actual["failure"] is None,
             "Missing completion or harness outcome is not a semantic return")
    for key, value in (("executed", 7), ("failures", 0), ("row_count", ROW_COUNT)):
        _require(type(actual[key]) is int and actual[key] == value, "Wrong exact wire count: " + key)
    _require(type(actual["caseIds"]) is list and actual["caseIds"] == list(CASE_IDS) and
             all(type(value) is str for value in actual["caseIds"]), "Incomplete/wrong/reordered cases")
    _require(type(actual["rows"]) is list and len(actual["rows"]) == ROW_COUNT, "Incomplete raw row set")
    _require(type(actual["checksum"]) is int and 0 <= actual["checksum"] < 1000003 and
             actual["checksum"] == checksum(actual["rows"]), "Corrupt raw ASCII checksum")
    cursor = 0
    def row(case_id, phase, length):
        nonlocal cursor
        fields = actual["rows"][cursor].split("|")
        cursor += 1
        _require(len(fields) == length and _int(fields[0], 1, ROW_COUNT) == cursor and
                 fields[1] == case_id and fields[2] == phase, "Truncated/missing/extra/reordered raw fields")
        return fields
    def snapshot(case_id, phase, role):
        f = row(case_id, phase, 12)
        _require(_int(f[3], 1, 2) == role, "Wrong boundary owner role/order")
        return dict(owner=_token(f[4], "owner"), state=_token(f[5], "state"), mode=_int(f[6], 0, 2),
            accumulator=_zero(f[7]), ui=_token(f[8], "ui", True), screen=_token(f[9], "screen", True),
            screen_enabled=_bool(f[10], True), widget=_token(f[11], "widget", True))
    records = []
    for index, case_id in enumerate(CASE_IDS):
        before = [snapshot(case_id, "before", role) for role in (1, 2)]
        events = []
        for _ in range(EVENT_COUNTS[index]):
            f = row(case_id, "event", 15)
            events.append(dict(sequence=_int(f[3], 1, 9), kind=f[4],
                invocation_id=None if f[5] == "none" else _int(f[5], 1, 4),
                owner=_token(f[6], "owner"), state=_token(f[7], "state"), screen=_token(f[8], "screen"),
                mode=_int(f[9], 0, 1), accumulator=_zero(f[10]), argument_owner=_token(f[11], "owner", True),
                returned=_bool(f[12], True), enabled=_bool(f[13]), widget=_token(f[14], "widget", True)))
        f = row(case_id, "outcome", 7)
        arguments = [] if f[4] == "none" else [_bool(f[4])]
        outcome = dict(kind=f[5], value=None if f[6] == "void" else _bool(f[6]))
        after = [snapshot(case_id, "after", role) for role in (1, 2)]
        records.append(dict(case_id=case_id, action=f[3], arguments=arguments, before=before,
                            services=events, outcome=outcome, after=after))
    _require(cursor == ROW_COUNT, "Incomplete raw observation prefix")
    oracle = _oracle()
    typed = dict(_typed_identity(expected, oracle), status="complete", failure=None, executed=7,
                 failures=0, caseIds=list(CASE_IDS), record_count=7, service_event_count=9,
                 checksum=oracle.checksum(records), records=records)
    comparison = oracle.validate(typed, _typed_identity(expected, oracle))
    return dict(schema_version=1, status="success", verification="semantic_trace_only",
                raw_rows=copy.deepcopy(actual["rows"]), raw_checksum=actual["checksum"],
                typed_completion=typed, comparison=comparison,
                codec={"profile": PROFILE, "boolean_encoding": "literal_0_1_to_boolean",
                       "nullable_encoding": "none", "void_encoding": "void", "rows": ROW_COUNT,
                       "numeric_encoding": "finite_rounded_numeric_zero_no_bit_proof"},
                native_origin="unverified", binding="unverified", pixels="unverified")
