#!/usr/bin/env python3
"""Prepare or explicitly execute the bounded native-tablet pure checker gate.

The exact fifteen source functions of the predecessor gate are extracted by
PowerShell AST. The adapter entry, engine and listeners are never evaluated by
this gate. Added argument-vector faults exercise a fixture-only validator of the
returned launch vector, since Fixed-Arguments accepts no arbitrary configuration.
Default operation only prepares sources. --self-test runs Python checks only.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import uuid

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "scripts/tablet-native-bounded-engine.ps1"
PREDECESSOR_SOURCE = ROOT / "scripts/tablet-native-engine.ps1"
PREDECESSOR = ROOT / "scripts/verify-tablet-native-checkers.py"
UTILITY = ROOT / "scripts/verify-host-readiness.py"
PREDECESSOR_SHA = "38eb4a117ad2696cc720dfa06648cefe7067c76e1c4e634257a397abbd4a3dd1"
PREDECESSOR_SOURCE_SHA = "d2aa186f5a8f83d310734aa5624792a482b58b244cbfa5bc8c7649960309f38f"
SOURCE_SHA = "83a75f4510a74c1cd71f141c870d19a08358bf510806518eb6c7dd1c9bfad53c"
COMMENTS = (b"# Fixed 30 FPS limit applies only to this owned diagnostic session.\n"
            b"# All native callbacks through stop remain recorded; the 200-frame cap still fails.\n")
OLD_ARGUMENTS = b"return @('-gproj',(Join-Path $OwnedProject 'addon.gproj'),'-noOpenLastResource','-scriptAuthorizeAll','-forceUpdate')"
NEW_ARGUMENTS = OLD_ARGUMENTS[:-1] + b",'-maxFPS','30')"
OLD_CASE = "startup.fixed-five-argv"
NEW_CASE = "bounded.startup.fixed-seven-argv"


def load_module(path, name, expected=None):
    raw = path.read_bytes()
    if expected is not None and hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError("Pinned checker dependency differs: " + str(path))
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def validate_source_relation(old, new):
    """Require the reviewed two comments and one fixed-vector change only."""
    if type(old) is not bytes or type(new) is not bytes or old.count(OLD_ARGUMENTS) != 1:
        raise ValueError("Predecessor Fixed-Arguments identity is unavailable")
    expected = COMMENTS + old.replace(OLD_ARGUMENTS, NEW_ARGUMENTS, 1)
    if new != expected:
        raise ValueError("Bounded adapter differs beyond the reviewed FPS vector/comments")


ARGUMENT_FAULTS = (
    ("missing-cap", "$v=@($v[0..4])"),
    ("missing-value", "$v=@($v[0..5])"),
    ("value-below", "$v[6]='29'"),
    ("value-above", "$v[6]='31'"),
    ("value-zero", "$v[6]='0'"),
    ("value-decimal", "$v[6]='30.0'"),
    ("value-bool", "$v[6]=$true"),
    ("missing-force-update", "$v=@($v[0..3]) + @($v[5..6])"),
    ("extra-argument", "$v+=@('-load')"),
    ("changed-cap", "$v[5]='-maxFps'"),
    ("changed-project", "$v[1]='C:/foreign/addon.gproj'"),
    ("changed-order", "$v[4]='-maxFPS';$v[5]='30';$v[6]='-forceUpdate'"),
    ("scalar-vector", "$v='joined arguments'"),
    ("duplicate-cap", "$v+=@('-maxFPS','30')"),
)


def case_registry(base):
    old = base.case_registry()
    if len(old) != 277 or sum(c[0] == OLD_CASE for c in old) != 1:
        raise ValueError("Predeclared predecessor checker registry changed")
    positive = ("$v=@(Fixed-Arguments $canonicalProject);Assert-BoundedArgumentVector $v $canonicalProject")
    cases = [(NEW_CASE, "return", None, positive) if c[0] == OLD_CASE else c for c in old]
    for name, mutation in ARGUMENT_FAULTS:
        cases.append(("bounded.argv-contract." + name, "checker_rejection", "failure",
                      "$v=@(Fixed-Arguments $canonicalProject);" + mutation + ";Assert-BoundedArgumentVector $v $canonicalProject"))
    ids = [c[0] for c in cases]
    if len(ids) != 291 or len(set(ids)) != len(ids):
        raise ValueError("Bounded case registry missing or duplicate")
    return tuple(cases)


ARGUMENT_CHECKER = r'''# Fixture-only returned-vector contract; not an adapter configuration API.
function Assert-BoundedArgumentVector([object] $Value,[string] $Project) {
 $wanted=@('-gproj',(Join-Path $Project 'addon.gproj'),'-noOpenLastResource','-scriptAuthorizeAll','-forceUpdate','-maxFPS','30')
 if($Value -isnot [Array] -or $Value.Count -ne 7){Throw-Outcome 'failure' 'Returned bounded launch vector must contain seven arguments'}
 for($i=0;$i -lt 7;$i++){
  if($Value[$i] -isnot [string] -or $Value[$i] -cne $wanted[$i]){Throw-Outcome 'failure' ('Returned bounded launch argument differs at '+$i)}
 }
}
'''


def fixture_script(base, cases):
    text = base.fixture_script(cases)
    marker = "function Reply {"
    if text.count(marker) != 1:
        raise ValueError("Predecessor fixture marker changed")
    text = text.replace(marker, ARGUMENT_CHECKER + "\n" + marker, 1)
    text = text.replace("tablet-native.checkers.inert", "tablet-native-bounded.checkers.inert")
    scopes = [{"id": c[0], "scope": "synthetic returned-vector contract" if c[0].startswith("bounded.argv-contract.")
               else "actual extracted Fixed-Arguments output" if c[0] == NEW_CASE else "actual extracted adapter checker"} for c in cases]
    # The provenance record is additive; only NAMES from the original gate can be
    # read from the adapter AST. The script-local argument helper is not extracted.
    scope_literal = "ConvertFrom-Json '" + json.dumps(scopes, separators=(",", ":")) + "'"
    text = text.replace(" compiler_execution='not_run';", " case_scopes=(" + scope_literal + ");\n compiler_execution='not_run';", 1)
    return text


def validate_result(base, value, cases, source, sha):
    if type(value) is not dict or value.get("operation") != "tablet-native-bounded.checkers.inert":
        raise ValueError("Wrong bounded checker operation")
    expected_scopes = [{"id": c[0], "scope": "synthetic returned-vector contract" if c[0].startswith("bounded.argv-contract.")
                        else "actual extracted Fixed-Arguments output" if c[0] == NEW_CASE else "actual extracted adapter checker"} for c in cases]
    if value.get("case_scopes") != expected_scopes:
        raise ValueError("Returned-vector fault scope is missing or changed")
    adapted = copy.deepcopy(value)
    adapted["operation"] = "tablet-native.checkers.inert"
    base.validate_result(adapted, cases, source, sha)


def self_test(base, cases, sha):
    planned = ["predecessor-receipt-fixture-validation", "bounded-source-positive", "bounded-source-missing-cap",
               "bounded-source-changed-value", "bounded-source-unrelated-budget", "bounded-registry-preservation",
               "bounded-whitelist", "bounded-positive-receipt", "bounded-missing-scope", "bounded-changed-scope",
               "bounded-wrong-operation", "bounded-missing-argument-case", "bounded-lost-rejection-status"]
    results = []
    def check(name, fn, rejected=False):
        if name not in planned or any(r["id"] == name for r in results):
            raise ValueError("Unknown or duplicate self-test")
        try:
            fn()
        except ValueError as error:
            if not rejected:
                raise
            results.append({"id": name, "status": "success", "expected": "rejection", "failure": str(error)})
        else:
            if rejected:
                raise ValueError("Malformed bounded fixture admitted: " + name)
            results.append({"id": name, "status": "success", "expected": "return"})
    prior = base.self_test(base.case_registry(), PREDECESSOR_SOURCE_SHA)
    check("predecessor-receipt-fixture-validation", lambda: None)
    old = PREDECESSOR_SOURCE.read_bytes()
    new = SOURCE.read_bytes()
    check("bounded-source-positive", lambda: validate_source_relation(old, new))
    check("bounded-source-missing-cap", lambda: validate_source_relation(old, new.replace(b",'-maxFPS','30'", b"", 1)), True)
    check("bounded-source-changed-value", lambda: validate_source_relation(old, new.replace(b",'-maxFPS','30'", b",'-maxFPS','31'", 1)), True)
    check("bounded-source-unrelated-budget", lambda: validate_source_relation(old, new.replace(b"max_polls=64", b"max_polls=65", 1)), True)
    def registry():
        old_cases = base.case_registry()
        if cases[:len(old_cases)] != tuple((NEW_CASE, "return", None, "$v=@(Fixed-Arguments $canonicalProject);Assert-BoundedArgumentVector $v $canonicalProject") if c[0] == OLD_CASE else c for c in old_cases):
            raise ValueError("Historical checker cases changed")
    check("bounded-registry-preservation", registry)
    script = fixture_script(base, cases)
    def whitelist():
        if len(base.NAMES) != 15 or "Invoke-Call" in base.NAMES or "Assert-BoundedArgumentVector" in base.NAMES or any(p in script for p in ("__EXPECTED__", "__CASES__", "__NAMES__", "__BOOLEANS__", "__COUNT__")):
            raise ValueError("Source extraction whitelist changed")
    check("bounded-whitelist", whitelist)
    source = Path("synthetic-bounded-source.ps1")
    sample = base.synthetic_result(cases, source, sha)
    sample["operation"] = "tablet-native-bounded.checkers.inert"
    sample["case_scopes"] = [{"id": c[0], "scope": "synthetic returned-vector contract" if c[0].startswith("bounded.argv-contract.") else "actual extracted Fixed-Arguments output" if c[0] == NEW_CASE else "actual extracted adapter checker"} for c in cases]
    check("bounded-positive-receipt", lambda: validate_result(base, copy.deepcopy(sample), cases, source, sha))
    for name, mutate in [("bounded-missing-scope", lambda v: v.pop("case_scopes")),
                         ("bounded-changed-scope", lambda v: v["case_scopes"][-1].update(scope="engine configuration rejection")),
                         ("bounded-wrong-operation", lambda v: v.update(operation="tablet-native.checkers.inert")),
                         ("bounded-missing-argument-case", lambda v: v["cases"].pop()),
                         ("bounded-lost-rejection-status", lambda v: v["cases"][-1].update(actual_status="unavailable"))]:
        value = copy.deepcopy(sample)
        mutate(value)
        check(name, lambda value=value: validate_result(base, value, cases, source, sha), True)
    if [r["id"] for r in results] != planned:
        raise ValueError("Python expected self-test set incomplete")
    return {"scope": "Python receipt/source/fixture validation only; all PowerShell cases prepared, not executed",
            "expected_case_ids": planned, "cases": results, "expected_cases": len(planned), "passed": len(results),
            "complete_expected_case_set": True, "predecessor_synthetic_validation": prior}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--run", action="store_true")
    modes.add_argument("--self-test", action="store_true")
    parser.add_argument("--powershell-host", type=Path)
    parser.add_argument("--expected-host-sha256")
    parser.add_argument("--expected-source-sha256")
    parser.add_argument("--output-root", type=Path, default=ROOT / "build")
    args = parser.parse_args(argv)
    if args.run and not all((args.powershell_host, args.expected_host_sha256, args.expected_source_sha256)):
        parser.error("--run requires an explicit host path/hash and bounded adapter hash")
    base = load_module(PREDECESSOR, "tablet_bounded_predecessor", PREDECESSOR_SHA)
    bounded = load_module(UTILITY, "tablet_bounded_host")
    cases = case_registry(base)
    work = args.output_root.absolute() / ("tablet-native-bounded-checkers-" + uuid.uuid4().hex)
    work.mkdir()
    journal = bounded.Journal(work / "outer")
    source, script, pure = work / "tablet-native-bounded-source.ps1", work / "checks.ps1", work / "pure-checks.json"
    identities = {"source": SOURCE, "predecessor_source": PREDECESSOR_SOURCE, "predecessor_driver": PREDECESSOR,
                  "driver": Path(__file__), "utility": UTILITY}
    record = {"schema_version": 1, "operation": "tablet-native-bounded.checkers.driver", "status": "running", "phase": "preparing", "failure": None,
              **{k: bounded.file_identity(p) for k, p in identities.items()},
              "expected_case_ids": [c[0] for c in cases], "expected_cases": len(cases),
              "predecessor_expected_case_ids": [c[0] for c in base.case_registry()],
              "revised_case": {"previous": OLD_CASE, "current": NEW_CASE, "previous_arguments": 5, "current_arguments": 7},
              "argument_fault_scope": "synthetic returned-vector contract; no arbitrary adapter configuration API",
              **{f: "not_run" for f in ("compiler_execution", "engine_execution", "adapter_top_level", "host_execution", "actual_process_stop", "native_listener_inventory")}}
    try:
        journal.save(record)
        if record["source"]["sha256"] != SOURCE_SHA or record["predecessor_source"]["sha256"] != PREDECESSOR_SOURCE_SHA or (args.expected_source_sha256 and args.expected_source_sha256 != record["source"]["sha256"]):
            record["status"] = "stale_input"
            raise ValueError("Pinned source identity differs")
        raw = SOURCE.read_bytes()
        validate_source_relation(PREDECESSOR_SOURCE.read_bytes(), raw)
        fixture = fixture_script(base, cases).encode("utf-8")
        if source.write_bytes(raw) != len(raw) or script.write_bytes(fixture) != len(fixture):
            raise ValueError("Short checker preparation write")
        record["source_snapshot"], record["script"] = bounded.file_identity(source), bounded.file_identity(script)
        if record["source_snapshot"]["sha256"] != record["source"]["sha256"] or record["script"]["sha256"] != hashlib.sha256(fixture).hexdigest():
            record["status"] = "stale_input"
            raise ValueError("Retained checker source differs")
        record.update(status="success", phase="source_prepared", verification="not_run; preparation only")
        journal.save(record)
        if args.self_test:
            record["synthetic_validation"] = self_test(base, cases, record["source"]["sha256"])
            record["verification"] = "13 bounded and 15 predecessor Python synthetic cases; PowerShell execution not_run"
        if args.run:
            record.update(status="running", phase="host_requested", verification="incomplete; checker run requested", host_execution="requested")
            journal.save(record)
            host = args.powershell_host.absolute()
            command = [str(host), "-NoProfile", "-File", str(script), "-Source", str(source), "-ExpectedAdapterHash", record["source"]["sha256"], "-Result", str(pure)]
            record["host_run"] = bounded.run_bounded(command, ROOT, work / "host", 45, 5, expected_executable={"path": str(host), "sha256": args.expected_host_sha256})
            record["host_execution"] = "attempted"
            if pure.exists():
                record["pure_receipt"] = bounded.file_identity(pure, 1024 * 1024)
                record["pure_result"] = json.loads(pure.read_text(encoding="utf-8"))
            if record["host_run"]["status"] != "success":
                record["status"] = record["host_run"]["status"]
                raise ValueError("Bounded checker host failed; retained case exceptions identify cause")
            validate_result(base, record.get("pure_result"), cases, source, record["source"]["sha256"])
            record.update(status="success", verification=str(len(cases)) + " pure bounded transport/returned-vector checker cases verified", host_execution="executed_complete")
        for key, path in {**identities, "source_snapshot": source, "script": script}.items():
            if bounded.file_identity(path) != record[key]:
                record["status"] = "stale_input"
                raise ValueError("Pinned bounded checker input changed")
    except BaseException as error:
        if record["status"] in ("running", "success"):
            record["status"] = "failure"
        record["failure"] = bounded.error_info(error)
    finally:
        record["phase"] = "finalized"
        try:
            journal.save(record)
        except BaseException as error:
            record["status"] = "failure"
            record["receipt_failure"] = bounded.error_info(error)
    print(json.dumps({"receipt": str(work / "outer/result.json"), "status": record["status"], "verification": record.get("verification"), "failure": record.get("failure")}))
    return 0 if record["status"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
