#!/usr/bin/env python3
"""Check a frozen N0 native tablet observation receipt, without execution.

This is trace admission only. A separate owned engine harness must establish
origin, world/session identity, native delivery and final registry failure state.
"""
from pathlib import Path
import argparse
import hashlib
import json
import math
import re
import sys
import os
import stat
from decimal import Decimal

sys.dont_write_bytecode = True
PROFILE = "sparkos.tablet.native-init-stowed.source.v1"
CONTRACT_SHA = "e31da81b7b8b18beaf4d8760b8ead4b1358a273b0936e42958cfc6e2e5bbc792"
CASE_IDS = ("native.init.1", "native.init.2", "native.stowed-frames.1",
            "native.stowed-frames.2", "native.independent-state")
FIELDS = ("sequence", "token", "stage", "ordinal", "ownerMatches", "ownerWorldPresent",
          "gameWorldPresent", "gameWorldMatches", "statePresent", "sameState",
          "independenceObserved", "independentState", "mode", "accumulator", "timeSlice",
          "mask", "uiAbsent", "screenAbsent")
BOOL_FIELDS = ("ownerMatches", "ownerWorldPresent", "gameWorldPresent", "gameWorldMatches",
               "statePresent", "sameState", "independenceObserved", "independentState", "uiAbsent", "screenAbsent")
ENVELOPE_FIELDS = {"schema_version", "profile", "token", "source_contract_sha256", "source_sha256", "status", "failure",
                   "executed", "failures", "caseIds", "owner_count", "frame_counts", "row_count", "checksum", "rows"}
EXPECTED_FIELDS = {"schema_version", "profile", "token", "source_contract_sha256", "source_sha256", "frame_mask"}
INTEGER = re.compile(r"(?:0|[1-9][0-9]*|-[1-9][0-9]*)\Z")
FLOAT = re.compile(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?\Z")
HASH = re.compile(r"[0-9a-f]{64}\Z")
MAX_JSON_BYTES = 2 * 1024 * 1024


class TraceFailure(ValueError):
    def __init__(self, message, status="failure", pointer=None):
        super().__init__(message)
        self.status, self.pointer = status, pointer


def require(condition, message, status="failure", pointer=None):
    if not condition:
        raise TraceFailure(message, status, pointer)


def checksum(rows):
    value = 0
    for row in rows:
        require(type(row) is str and row.isascii(), "Checksum requires exact ASCII rows")
        for code in (row + "\n").encode("ascii"):
            value = (value * 31 + code) % 1000003
    return value


def validate_expected(value):
    require(type(value) is dict and set(value) == EXPECTED_FIELDS, "Exact expected N0 admission fields required")
    require(type(value["schema_version"]) is int and value["schema_version"] == 1 and value["profile"] == PROFILE,
            "Expected N0 schema/profile differs")
    require(type(value["token"]) is str and HASH.fullmatch(value["token"]) and value["source_contract_sha256"] == CONTRACT_SHA and
            type(value["source_sha256"]) is str and HASH.fullmatch(value["source_sha256"]),
            "Expected token or frozen observer contract differs", "stale_input")
    mask = value["frame_mask"]
    require(type(mask) is int and 0 < mask <= 2147483648 and mask & (mask - 1) == 0,
            "A reviewed single-bit native FRAME binding must be supplied")
    return value


def parse_row(raw):
    require(type(raw) is str and raw.isascii() and 0 < len(raw) <= 512 and "\n" not in raw and "\r" not in raw,
            "Malformed bounded ASCII N0 row")
    parts = raw.split("|")
    require(len(parts) == len(FIELDS), "N0 row must contain sequence and exactly seventeen observer fields")
    result = dict(zip(FIELDS, parts))
    for key in BOOL_FIELDS:
        require(result[key] in ("0", "1"), "Nonliteral wire Boolean: " + key)
        result[key] = result[key] == "1"
    for key in ("sequence", "token", "ordinal", "mode", "mask"):
        text = result[key]
        require(len(text) <= 11 and INTEGER.fullmatch(text), "Noncanonical bounded integer: " + key)
        result[key] = int(text)
    require(0 <= result["sequence"] < 1024 and result["token"] in (1, 2) and
            1 <= result["ordinal"] <= 200 and -2147483648 <= result["mode"] <= 2147483647 and
            -2147483648 <= result["mask"] <= 2147483647, "Wire integer outside admitted width/domain")
    require(result["stage"] in ("init.before", "init.after", "frame.before", "frame.after"), "Unknown native event stage")
    for key in ("accumulator", "timeSlice"):
        text = result[key]
        require(0 < len(text) <= 64 and FLOAT.fullmatch(text), "Malformed rounded numeric text: " + key)
        number = float(text)
        require(math.isfinite(number), "Nonfinite decoded numeric observation: " + key)
        result[key] = number
        result[key + "_text"] = text
    require(0 <= Decimal(result["timeSlice_text"]) <= 10, "Decoded native timestep outside admitted finite domain")
    return result


def validate_trace(value, expected):
    expected = validate_expected(expected)
    require(type(value) is dict, "N0 completion must be an object")
    # A failed/absent harness result never becomes source failure or successful
    # verification merely because it lacks a complete trace.
    if value.get("status") in ("failure", "unavailable", "timeout", "cancelled", "stale_input"):
        raise TraceFailure("N0 receipt is not a successful completion", value["status"])
    require(set(value) == ENVELOPE_FIELDS, "Incomplete or unknown N0 completion fields")
    require(type(value["schema_version"]) is int and value["schema_version"] == 1 and
            value["profile"] == PROFILE and value["status"] == "complete" and value["failure"] == "",
            "N0 schema/profile/status/failure differs")
    require(value["token"] == expected["token"] and value["source_contract_sha256"] == expected["source_contract_sha256"] and
            value["source_sha256"] == expected["source_sha256"],
            "N0 token or frozen source contract differs", "stale_input")
    require(type(value["executed"]) is int and value["executed"] == 1 and type(value["failures"]) is int and value["failures"] == 0,
            "N0 execution/failure counters differ")
    require(type(value["caseIds"]) is list and value["caseIds"] == list(CASE_IDS) and
            type(value["owner_count"]) is int and value["owner_count"] == 2,
            "Exact five N0 cases and two owners required")
    require(type(value["frame_counts"]) is list and len(value["frame_counts"]) == 2 and
            all(type(number) is int and 3 <= number <= 200 for number in value["frame_counts"]), "Invalid exact native frame counts")
    require(type(value["row_count"]) is int and 16 <= value["row_count"] <= 1024 and
            type(value["checksum"]) is int and 0 <= value["checksum"] <= 1000002,
            "Malformed bounded trace counters")
    rows = value["rows"]
    require(type(rows) is list and len(rows) == value["row_count"] and
            value["row_count"] == 4 + 2 * sum(value["frame_counts"]), "Incomplete N0 row/count accounting")
    parsed = [parse_row(row) for row in rows]
    require(checksum(rows) == value["checksum"], "N0 exact raw trace checksum differs")
    phases = {1: "cold", 2: "cold"}
    frames = {1: 0, 2: 0}
    masks = {}
    claimed = 0
    pending = None
    for sequence, row in enumerate(parsed):
        require(row["sequence"] == sequence, "Missing, duplicate or reordered native sequence")
        owner = row["token"]
        stage = row["stage"]
        if stage == "init.before":
            require(pending is None and phases[owner] == "cold" and owner == claimed + 1 and row["ordinal"] == 1,
                    "Native initialization order or multiplicity differs")
            claimed += 1
            phases[owner] = "initializing"
            pending = row
        elif stage == "frame.before":
            require(pending is None and phases[owner] == "alive" and row["ordinal"] == frames[owner] + 1,
                    "Frame before initialization, duplicate frame or nested callback pair")
            pending = row
        else:
            require(pending is not None and stage == pending["stage"].replace("before", "after") and
                    owner == pending["token"] and row["ordinal"] == pending["ordinal"],
                    "Missing, reordered, interleaved or mismatched callback after observation")
            require(Decimal(row["timeSlice_text"]) == Decimal(pending["timeSlice_text"]), "Before/after native timestep differs")
            if stage == "init.after":
                require((row["mask"] & expected["frame_mask"]) != 0, "Initialization lacks observed FRAME registration")
                masks[owner] = row["mask"]
                phases[owner] = "alive"
            else:
                require(row["mask"] == pending["mask"], "Frame callback changed its observed event mask")
                frames[owner] += 1
            pending = None
        require(all(row[name] for name in ("ownerMatches", "ownerWorldPresent", "gameWorldPresent", "gameWorldMatches",
                                           "statePresent", "sameState", "uiAbsent", "screenAbsent")),
                "N0 owner/world/state/service-null observations differ")
        require(row["independenceObserved"] == (claimed == 2) and row["independentState"] == (claimed == 2),
                "State independence absent, aliased or claimed before second native owner")
        require(row["mode"] == 0 and Decimal(row["accumulator_text"]) == 0, "Decoded stowed state or accumulator observation differs")
        if stage.startswith("init."):
            require(Decimal(row["timeSlice_text"]) == 0, "Initialization observation has a frame timestep")
        else:
            require(row["mask"] == masks[owner] and row["mask"] & expected["frame_mask"] != 0,
                    "Stowed frame lacks stable observed FRAME registration")
    require(pending is None and claimed == 2 and all(phase == "alive" for phase in phases.values()) and
            [frames[1], frames[2]] == value["frame_counts"], "Incomplete native owners/frame pairs")
    return {"status": "verified", "scope": "N0 decoded ordered trace only; runtime provenance checked separately",
            "caseIds": list(CASE_IDS), "cases": 5, "frames": [frames[1], frames[2]], "rows": len(rows),
            "checksum": value["checksum"], "normalized_rows": parsed,
            "numeric_comparison": "rounded finite native numeric text; decoded numeric zero only; no bit or signed-zero proof",
            "limitations": ["No initialization-reset mutation proof from fresh zero state.", "No count of mask-setting calls.",
                            "No original/generated engine parity, UI service, deletion, lifetime, profile or multiplayer proof.",
                            "An earlier snapshot does not prove later callbacks stayed within budget; stop/final failure recheck belongs to the transport."]}


def read_json(path):
    path = Path(path)
    def signature(value):
        return (value.st_dev, value.st_ino, value.st_nlink, value.st_size, value.st_mtime_ns)
    try:
        before = path.lstat()
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and not path.is_symlink() and
                not (hasattr(path, "is_junction") and path.is_junction()),
                "Trace/request input must be a regular unlinked file", "stale_input")
        require(before.st_size <= MAX_JSON_BYTES, "Trace/request file exceeds bounded input size", "unavailable")
        with path.open("rb") as stream:
            opened = os.fstat(stream.fileno())
            require(signature(opened) == signature(before), "Trace/request file replaced before reading", "stale_input")
            raw = stream.read(MAX_JSON_BYTES + 1)
            require(len(raw) <= MAX_JSON_BYTES, "Actual trace/request read exceeded input limit", "unavailable")
            finished = os.fstat(stream.fileno())
        require(signature(before) == signature(finished) == signature(path.lstat()) and len(raw) == before.st_size,
                "Trace/request file changed or incomplete read", "stale_input")
    except OSError as error:
        raise TraceFailure("Unable to read bounded trace/request input: " + str(error), "unavailable") from error
    def pairs(items):
        value = {}
        for name, item in items:
            require(name not in value, "Duplicate JSON field: " + name)
            value[name] = item
        return value
    try:
        return json.loads(raw, object_pairs_hook=pairs,
                          parse_constant=lambda value: (_ for _ in ()).throw(TraceFailure("Nonstandard JSON number: " + value)))
    except TraceFailure:
        raise
    except (ValueError, UnicodeError, RecursionError) as error:
        raise TraceFailure("Malformed bounded JSON input: " + str(error)) from error


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--expected", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = validate_trace(read_json(args.receipt), read_json(args.expected))
        print(json.dumps(result, separators=(",", ":")), flush=True)
        return 0
    except TraceFailure as error:
        print(json.dumps({"status": error.status, "diagnostic": str(error), "pointer": error.pointer}), flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
