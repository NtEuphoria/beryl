#!/usr/bin/env python3
"""Prepare/explicitly run isolated native-tablet read-sharing lease checkers.

The original 277 checker IDs/order remain unchanged. Added cases execute only
registered lease/namespace functions against owned small files, never an engine,
listener, adapter entry, native callback, compiler, or process-stop operation.
The Python self-test validates synthetic receipts and source preparation only.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys
import uuid

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "scripts/tablet-native-leased-engine.ps1"
PREDECESSOR = ROOT / "scripts/verify-tablet-native-checkers.py"
BASE_SOURCE = ROOT / "scripts/tablet-native-engine.ps1"
UTILITY = ROOT / "scripts/verify-host-readiness.py"
BASE_SHA = "d2aa186f5a8f83d310734aa5624792a482b58b244cbfa5bc8c7649960309f38f"
PREDECESSOR_SHA = "38eb4a117ad2696cc720dfa06648cefe7067c76e1c4e634257a397abbd4a3dd1"
ADDED_NAMES = ["Lease-HandleHash", "Read-LeaseBasis", "Open-ReadLease", "Assert-HeldReadLease",
               "Fast-NamespaceSnapshot", "Assert-FastInputs", "Close-ReadLease", "Relative-Name", "Assert-Deadline"]


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def predecessor():
    if hashlib.sha256(PREDECESSOR.read_bytes()).hexdigest() != PREDECESSOR_SHA or hashlib.sha256(BASE_SOURCE.read_bytes()).hexdigest() != BASE_SHA:
        raise ValueError("Frozen predecessor identity changed")
    return load(PREDECESSOR, "native_leased_predecessor")


def admitted_source(base, raw, prior):
    text, original = raw.decode("utf-8").replace("\r\n", "\n"), prior.decode("utf-8").replace("\r\n", "\n")
    def functions(value):
        starts = list(re.finditer(r"(?m)^function ([A-Za-z][A-Za-z0-9-]*)(?:\(|\s|$)", value))
        rows = {}
        for i, match in enumerate(starts):
            name = match.group(1)
            if name in rows: raise ValueError("Duplicate source function identity")
            rows[name] = value[match.start():starts[i + 1].start() if i + 1 < len(starts) else len(value)].rstrip()
        return rows
    actual, expected = functions(text), functions(original)
    if any(name not in actual or actual[name] != expected[name] for name in base.NAMES):
        raise ValueError("Frozen original pure transport function changed")
    if any(name not in actual for name in ADDED_NAMES): raise ValueError("Missing registered lease helper")
    return True


def extra_cases():
    rows = []
    def add(name, body, status=None):
        rows.append(("lease." + name, "return" if status is None else "checker_rejection", status,
                     "With-LeaseFixture {" + body + "}"))
    add("basis-exact98", "$v=Read-LeaseBasis;if($v.Count -ne 98 -or @($v|Where-Object {$_.kind -ceq 'addon'}).Count -ne 93){throw 'Basis count differs'}")
    add("acquire-hash98-release", "Open-ReadLease (Read-LeaseBasis);Assert-HeldReadLease;if($record.read_lease.opened_count -ne 98 -or @($record.read_lease.entries|Where-Object {$_.sha256 -cne $_.expected_sha256}).Count){throw 'Held hashes differ'};if(-not(Close-ReadLease) -or $record.read_lease.released_count -ne 98){throw 'Release incomplete'}")
    add("fast-namespace-positive", "Open-ReadLease (Read-LeaseBasis);$script:nativeLeaseFast=$true;Assert-FastInputs;if($record.read_lease.fast_check_count -ne 1 -or $record.read_lease.fast_checks[0].file_count -ne 93){throw 'Fast coverage missing'}")
    add("write-denied-restored", "Open-ReadLease (Read-LeaseBasis);$p=Join-Path $canonicalProject 'data/f000.txt';$denied=$false;try{$s=[IO.File]::Open($p,[IO.FileMode]::Open,[IO.FileAccess]::Write,[IO.FileShare]::Read);$s.Dispose()}catch [IO.IOException]{$denied=$true};if(-not $denied){throw 'Ordinary writer was admitted'};if(-not(Close-ReadLease)){throw 'Release failed'};$s=[IO.File]::Open($p,[IO.FileMode]::Open,[IO.FileAccess]::Write,[IO.FileShare]::Read);$s.Dispose()")
    add("delete-denied-restored", "Open-ReadLease (Read-LeaseBasis);$p=Join-Path $canonicalProject 'data/f000.txt';$denied=$false;try{[IO.File]::Delete($p)}catch [IO.IOException]{$denied=$true};if(-not $denied -or -not [IO.File]::Exists($p)){throw 'Delete was admitted'};if(-not(Close-ReadLease)){throw 'Release failed'};[IO.File]::Delete($p);if([IO.File]::Exists($p)){throw 'Delete not restored'}")
    add("rename-denied-restored", "Open-ReadLease (Read-LeaseBasis);$p=Join-Path $canonicalProject 'data/f000.txt';$q=$p+'.moved';$denied=$false;try{[IO.File]::Move($p,$q)}catch [IO.IOException]{$denied=$true};if(-not $denied -or -not [IO.File]::Exists($p)){throw 'Rename was admitted'};if(-not(Close-ReadLease)){throw 'Release failed'};[IO.File]::Move($p,$q);if(-not [IO.File]::Exists($q)){throw 'Rename not restored'}")
    add("held-after-release", "Open-ReadLease (Read-LeaseBasis);$null=Close-ReadLease;Assert-HeldReadLease", "unavailable")
    add("second-acquisition", "Open-ReadLease (Read-LeaseBasis);Open-ReadLease (Read-LeaseBasis)", "failure")
    add("idempotent-normal-release", "Open-ReadLease (Read-LeaseBasis);$null=Close-ReadLease;$before=$record.read_lease|ConvertTo-Json -Depth 24 -Compress;$null=Close-ReadLease;if(($record.read_lease|ConvertTo-Json -Depth 24 -Compress) -cne $before){throw 'Normal release evidence rewritten'}")
    for name, body in [
        ("basis-count", "$v=Read-LeaseBasis;if($v.Count -ne 98){throw 'Fixture basis must contain98 entries'};Open-ReadLease $v[0..96]"),
        ("basis-duplicate", "$v=Read-LeaseBasis;if($v.Count -ne 98){throw 'Fixture basis must contain98 entries'};$v[97]=$v[0];Open-ReadLease $v"),
        ("basis-unknown-kind", "$v=Read-LeaseBasis;if($v.Count -ne 98){throw 'Fixture basis must contain98 entries'};$v[0].kind='unknown';Open-ReadLease $v"),
        ("basis-relative-path", "$v=Read-LeaseBasis;if($v.Count -ne 98){throw 'Fixture basis must contain98 entries'};$v[0].path='relative.txt';Open-ReadLease $v"),
        ("basis-wrong-kind-count", "$v=Read-LeaseBasis;if($v.Count -ne 98){throw 'Fixture basis must contain98 entries'};$v[0].kind='plugin';Open-ReadLease $v"),
        ("basis-hash-shape", "$v=Read-LeaseBasis;if($v.Count -ne 98){throw 'Fixture basis must contain98 entries'};$v[0].sha256='wrong';Open-ReadLease $v"),
        ("basis-extra-field", "$v=Read-LeaseBasis;if($v.Count -ne 98){throw 'Fixture basis must contain98 entries'};$v[0]|Add-Member extra 1;Open-ReadLease $v")]:
        add(name, body, "failure")
    add("wrong-hash-partial-release", "$v=Read-LeaseBasis;if($v.Count -ne 98){throw 'Fixture basis must contain98 entries'};$v[4].sha256='0'*64;try{Open-ReadLease $v}catch{if($record.read_lease.opened_count -ne 5 -or $record.read_lease.acquisition_status -cne 'failed'){throw 'Wrong partial acquisition evidence'};if(-not(Close-ReadLease) -or $record.read_lease.released_count -ne 5){throw 'Partial handles not released'};throw}", "stale_input")
    add("open-conflict-partial-release", "$v=Read-LeaseBasis;if($v.Count -ne 98){throw 'Fixture basis must contain98 entries'};$block=[IO.File]::Open($v[4].path,[IO.FileMode]::Open,[IO.FileAccess]::Write,[IO.FileShare]::Read);try{try{Open-ReadLease $v}catch{if($record.read_lease.opened_count -ne 4 -or $record.read_lease.acquisition_status -cne 'failed'){throw 'Open failure evidence differs'};if(-not(Close-ReadLease) -or $record.read_lease.released_count -ne 4){throw 'Open failure cleanup missing'};throw}}finally{$block.Dispose()}", "unavailable")
    add("changed-bytes-before-acquire", "$p=Join-Path $canonicalProject 'data/f000.txt';[IO.File]::WriteAllText($p,'altered');Open-ReadLease (Read-LeaseBasis)", "stale_input")
    add("stream-short-length", "$s=[IO.MemoryStream]::new([byte[]](1,2));try{$null=Lease-HandleHash $s 3}finally{$s.Dispose()}", "stale_input")
    add("stream-closed", "$s=[IO.MemoryStream]::new([byte[]](1,2));$s.Dispose();$null=Lease-HandleHash $s 2", "stale_input")
    add("stream-bool-length", "$s=[IO.MemoryStream]::new([byte[]](1,2));try{$null=Lease-HandleHash $s $true}finally{$s.Dispose()}", "stale_input")
    add("stream-byte-budget", "$s=[IO.MemoryStream]::new();try{$null=Lease-HandleHash $s (128MB+1)}finally{$s.Dispose()}", "stale_input")
    add("held-descriptor-size", "Open-ReadLease (Read-LeaseBasis);$script:nativeLeaseHandles[0].entry.bytes++;Assert-HeldReadLease", "stale_input")
    add("held-descriptor-hash", "Open-ReadLease (Read-LeaseBasis);$script:nativeLeaseHandles[0].entry.sha256='0'*64;Assert-HeldReadLease", "stale_input")
    add("held-stream-closed", "Open-ReadLease (Read-LeaseBasis);$script:nativeLeaseHandles[0].stream.Dispose();Assert-HeldReadLease", "stale_input")
    add("namespace-extra-file", "Open-ReadLease (Read-LeaseBasis);[IO.File]::WriteAllText((Join-Path $canonicalProject 'extra.txt'),'x');Assert-FastInputs", "stale_input")
    add("namespace-extra-directory", "Open-ReadLease (Read-LeaseBasis);$null=[IO.Directory]::CreateDirectory((Join-Path $canonicalProject 'extra'));Assert-FastInputs", "stale_input")
    add("derived-rdb-bounded", "Open-ReadLease (Read-LeaseBasis);[IO.File]::WriteAllText((Join-Path $canonicalProject 'resourceDatabase.rdb'),'derived');Assert-FastInputs;if($record.engine_outputs.Count -ne 1 -or $null -ne $record.engine_outputs[0].sha256){throw 'Fast derived output confused with byte proof'}")
    add("derived-rdb-oversize", "Open-ReadLease (Read-LeaseBasis);$s=[IO.File]::Create((Join-Path $canonicalProject 'resourceDatabase.rdb'));try{$s.SetLength(8MB+1)}finally{$s.Dispose()};Assert-FastInputs", "stale_input")
    add("fast-check-budget", "Open-ReadLease (Read-LeaseBasis);$record.read_lease.fast_check_count=512;$record.read_lease.fast_checks=@(1)*512;Assert-FastInputs", "failure")
    add("fast-check-boundary511", "Open-ReadLease (Read-LeaseBasis);$record.read_lease.fast_check_count=511;$record.read_lease.fast_checks=@(1)*511;Assert-FastInputs;if($record.read_lease.fast_check_count -ne 512){throw 'Last admitted fast check missing'}")
    add("namespace-length-link-injected", "Open-ReadLease (Read-LeaseBasis);$original=(Get-Item Function:Fast-NamespaceSnapshot).ScriptBlock;$script:injectedLeaseTree=Fast-NamespaceSnapshot;$script:injectedLeaseTree.files['data/f000.txt']++;Set-Item Function:Fast-NamespaceSnapshot -Value {$script:injectedLeaseTree};try{Assert-FastInputs}finally{Set-Item Function:Fast-NamespaceSnapshot -Value $original;Remove-Variable injectedLeaseTree -Scope Script}", "stale_input")
    add("ancestor-rename-denied-restored", "Open-ReadLease (Read-LeaseBasis);$old=$canonicalProject+'.moved';$denied=$false;try{[IO.Directory]::Move($canonicalProject,$old)}catch [IO.IOException]{$denied=$true}catch [UnauthorizedAccessException]{$denied=$true};if(-not $denied -or -not [IO.Directory]::Exists($canonicalProject) -or [IO.Directory]::Exists($old)){throw 'Ancestor rename denial not demonstrated'};Assert-FastInputs;if(-not(Close-ReadLease)){throw 'Release incomplete'};[IO.Directory]::Move($canonicalProject,$old);if([IO.Directory]::Exists($canonicalProject) -or -not [IO.File]::Exists((Join-Path $old 'data/f000.txt'))){throw 'Ancestor rename not restored after release'}")
    add("regular-directory-not-file", "$v=Read-LeaseBasis;if($v.Count -ne 98){throw 'Fixture basis must contain98 entries'};$v[4].path=Join-Path $canonicalProject 'data';Open-ReadLease $v", "stale_input")
    add("reparse-extra-when-available", "Open-ReadLease (Read-LeaseBasis);$link=Join-Path $canonicalProject 'linked.txt';$target=Join-Path $canonicalProject 'data/f000.txt';$cap=[ordered]@{id='lease.reparse-extra';status='unavailable';failure=$null;source_guard_executed=$false};$created=$false;try{$null=[IO.File]::CreateSymbolicLink($link,$target);$created=$true}catch{$cap.failure=Exception-Detail $_};if($created){$caught=$false;try{Assert-FastInputs}catch [InvalidOperationException]{$caught=($record.status -ceq 'stale_input')};if(-not $caught){throw 'Linked namespace falsely admitted'};$cap.status='verified';$cap.source_guard_executed=$true};$receipt.capability_observations+= $cap")
    add("release-fault-no-retry", "Open-ReadLease (Read-LeaseBasis);$owned=$script:nativeLeaseHandles[0];$real=$owned.stream;$fake=[pscustomobject]@{CanRead=$true;Calls=0};$fake|Add-Member -MemberType ScriptMethod -Name Dispose -Value {$this.Calls++;throw [IO.IOException]::new('injected release failure')};$owned.stream=$fake;try{if(Close-ReadLease){throw 'Release failure promoted'};if($record.read_lease.status -cne 'release_failed' -or $record.read_lease.released_count -ne 97 -or $record.read_lease.errors.Count -ne 1){throw 'Release evidence lost'};$null=Close-ReadLease;if($fake.Calls -ne 1){throw 'Unconfirmed release retried'}}finally{$real.Dispose();$owned.released=$true}")
    return tuple(rows)


LEASE_FIXTURE = r'''
function New-LeaseRecord {
 return [ordered]@{schema_version=1;policy='FileMode.Open/FileAccess.Read/FileShare.Read';status='not_requested';acquisition_status='not_requested';release_status='not_requested';expected_count=98;opened_count=0;released_count=0;entries=@();errors=@();open_started_ms=$null;open_completed_ms=$null;open_duration_ms=$null;close_started_ms=$null;close_completed_ms=$null;close_duration_ms=$null;fast_checks=@();fast_check_count=0;full_checks_with_handles=0;post_release_full_check=$false;byte_identity='hashed_while_held; fast_checks_length_and_readability_only';native_open_dispose_not_hard_cancelled=$true}
}
function Fixture-Hash([string]$Path) {
 $b=[IO.File]::ReadAllBytes($Path);return [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($b)).ToLowerInvariant()
}
function With-LeaseFixture([scriptblock]$Body) {
 $fixture=Join-Path $FixtureRoot ([Guid]::NewGuid().ToString('N'))
 $canonicalProject=Join-Path $fixture 'addon';$null=[IO.Directory]::CreateDirectory((Join-Path $canonicalProject 'data'))
 $manifest=@{files=[ordered]@{}};$expectedDirectories=@('data');$pluginPaths=@{};$pluginHashes=@{}
 for($i=0;$i -lt 93;$i++){$n=('data/f{0:D3}.txt' -f $i);$p=Join-Path $canonicalProject $n;[IO.File]::WriteAllText($p,'fixture');$manifest.files[$n]=Fixture-Hash $p}
 $adapterPath=Join-Path $fixture 'adapter.ps1';$InputManifest=Join-Path $fixture 'inputs.json';$enginePath=Join-Path $fixture 'engine.bin'
 foreach($p in @($adapterPath,$InputManifest,$enginePath)){[IO.File]::WriteAllText($p,'fixture')}
 $adapterHash=Fixture-Hash $adapterPath;$manifestHash=Fixture-Hash $InputManifest;$ExpectedEngineHash=Fixture-Hash $enginePath
 foreach($n in @('Find-Workbench.ps1','Invoke-WorkbenchRpc.ps1')){$p=Join-Path $fixture $n;[IO.File]::WriteAllText($p,'fixture');$pluginPaths[$n]=$p;$pluginHashes[$n]=Fixture-Hash $p}
 $record.engine_path=$enginePath;$record.engine_outputs=@();$record.read_lease=New-LeaseRecord
 $clock=[Diagnostics.Stopwatch]::StartNew();$stageClock=[Diagnostics.Stopwatch]::StartNew()
 $script:nativeLeaseHandles=[Collections.Generic.List[object]]::new();$script:nativeLeaseFast=$false;$script:nativeLeaseComplete=$false
 try{&$Body}finally{
  $null=Close-ReadLease
  # These paths are freshly created under the exclusive fixture directory. A
  # bounded failed fixture may leave evidence files; do not recursively delete.
 }
}
'''


def fixture_script(base, cases):
    header = base.HEADER.replace("param([string]$Source,[string]$ExpectedAdapterHash,[string]$Result)",
                               "param([string]$Source,[string]$ExpectedAdapterHash,[string]$Result,[string]$FixtureRoot)")
    header = header.replace("operation='tablet-native.checkers.inert'", "operation='tablet-native.leased-checkers.inert'")
    header = header.replace("function_names=$names;expected_case_ids=", "function_names=$names;capability_observations=@();expected_case_ids=")
    header = header.replace("try {\n Save-Receipt", LEASE_FIXTURE + "\ntry {\n Save-Receipt")
    actions = ["Case '" + name + "' '" + outcome + "' " + ("$null" if status is None else "'" + status + "'") + " {" + body + "}"
               for name, outcome, status, body in cases]
    names = base.NAMES + ADDED_NAMES
    return header.replace("__EXPECTED__", base.ps_array([c[0] for c in cases])).replace("__NAMES__", base.ps_array(names)).replace("__BOOLEANS__", base.ps_array(base.BOOLEANS)).replace("__COUNT__", str(len(cases))).replace("__CASES__", "\n".join(actions))


def validate_result(base, value, cases, source, sha):
    if type(value) is not dict or value.get("operation") != "tablet-native.leased-checkers.inert" or value.get("function_names") != base.NAMES + ADDED_NAMES:
        raise ValueError("Leased checker operation/whitelist differs")
    capabilities = value.get("capability_observations")
    if type(capabilities) is not list or len(capabilities) != 1:
        raise ValueError("Missing exact optional reparse observation")
    cap = capabilities[0]
    if type(cap) is not dict or set(cap) != {"id", "status", "failure", "source_guard_executed"} or cap["id"] != "lease.reparse-extra":
        raise ValueError("Malformed optional reparse observation")
    if cap["status"] == "verified":
        if cap["source_guard_executed"] is not True or cap["failure"] is not None: raise ValueError("Unverified reparse guard")
    elif cap["status"] == "unavailable":
        if cap["source_guard_executed"] is not False or type(cap["failure"]) is not dict or type(cap["failure"].get("message")) is not str: raise ValueError("Missing optional capability failure")
    else: raise ValueError("Unknown optional capability outcome")
    translated = copy.deepcopy(value)
    translated["operation"] = "tablet-native.checkers.inert"
    translated["function_names"] = base.NAMES
    base.validate_result(translated, cases, source, sha)


def self_test(base, cases, sha):
    sample = base.synthetic_result(cases, Path("synthetic-leased.ps1"), sha)
    sample.update(operation="tablet-native.leased-checkers.inert", function_names=base.NAMES + ADDED_NAMES)
    sample["capability_observations"] = [{"id": "lease.reparse-extra", "status": "verified", "failure": None, "source_guard_executed": True}]
    ids = ["predecessor277-prefix", "fixture-whitelist", "synthetic-positive", "missing-lease-case", "wrong-added-function", "false-engine-claim", "generic-domain-error", "source-hash", "wrong-count",
           "source-old15-preserved", "source-old-function-mutant", "optional-reparse-unavailable", "missing-reparse-observation", "false-reparse-promotion", "unknown-reparse-status"]
    out = []
    if tuple(cases[:277]) != base.case_registry() or len(base.case_registry()) != 277:
        raise ValueError("Original277 cases changed")
    out.append({"id": ids[0], "status": "success"})
    fixture = fixture_script(base, cases)
    if any(x in fixture for x in ("__EXPECTED__", "__NAMES__", "__BOOLEANS__", "__COUNT__", "__CASES__")) or any(x in base.NAMES + ADDED_NAMES for x in ("Invoke-Call", "Run-Stage", "Assert-Inputs", "Wait-Listener", "Assert-OwnedSession", "Content-Hash")):
        raise ValueError("Unsafe extraction/fixture markers")
    out.append({"id": ids[1], "status": "success"})
    validate_result(base, sample, cases, Path("synthetic-leased.ps1"), sha)
    out.append({"id": ids[2], "status": "success"})
    mutations = [lambda v: v["cases"].pop(), lambda v: v["function_names"].append("Invoke-Call"), lambda v: v.update(engine_execution="executed"),
                 lambda v: v["cases"][-17]["original_exception"].update(type="System.Exception"), lambda v: v.update(source_sha256="0" * 64), lambda v: v.update(passed=0)]
    # Locate a declared domain rejection instead of relying on its row position.
    rejected = next(i for i, c in enumerate(cases) if c[2] is not None)
    mutations[3] = lambda v: v["cases"][rejected]["original_exception"].update(type="System.Exception")
    for name, mutation in zip(ids[3:9], mutations):
        value = copy.deepcopy(sample);mutation(value)
        try: validate_result(base, value, cases, Path("synthetic-leased.ps1"), sha)
        except ValueError: out.append({"id": name, "status": "success"})
        else: raise ValueError("Malformed leased synthetic receipt admitted: " + name)
    prior, raw = BASE_SOURCE.read_bytes(), SOURCE.read_bytes()
    admitted_source(base, raw, prior);out.append({"id": ids[9], "status": "success"})
    changed = raw.replace(b"return $Path.Replace", b"return $Path.Trim().Replace", 1)
    if changed == raw: raise ValueError("Original function mutation not applied")
    try: admitted_source(base, changed, prior)
    except ValueError: out.append({"id": ids[10], "status": "success"})
    else: raise ValueError("Changed original checker body admitted")
    unavailable = copy.deepcopy(sample)
    unavailable["capability_observations"][0].update(status="unavailable", source_guard_executed=False, failure={"message": "Synthetic unavailable filesystem privilege"})
    validate_result(base, unavailable, cases, Path("synthetic-leased.ps1"), sha);out.append({"id": ids[11], "status": "success"})
    changes = [lambda v: v.pop("capability_observations"), lambda v: v["capability_observations"][0].update(source_guard_executed=False), lambda v: v["capability_observations"][0].update(status="unknown")]
    for name, mutate in zip(ids[12:], changes):
        value=copy.deepcopy(sample);mutate(value)
        try: validate_result(base, value, cases, Path("synthetic-leased.ps1"), sha)
        except ValueError: out.append({"id": name, "status": "success"})
        else: raise ValueError("Malformed optional capability admitted: " + name)
    return {"scope": "Python synthetic receipt/fixture validation only; lease filesystem effects/PowerShell not_run", "expected_case_ids": ids, "cases": out, "complete_expected_case_set": [r["id"] for r in out] == ids}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group();modes.add_argument("--run", action="store_true");modes.add_argument("--self-test", action="store_true")
    parser.add_argument("--powershell-host", type=Path);parser.add_argument("--expected-host-sha256");parser.add_argument("--expected-source-sha256")
    parser.add_argument("--output-root", type=Path, default=ROOT / "build")
    args = parser.parse_args(argv)
    if args.run and not all((args.powershell_host, args.expected_host_sha256, args.expected_source_sha256)):
        parser.error("--run requires explicit pinned host and adapter identities")
    base = predecessor();bounded = load(UTILITY, "native_leased_bounded_host")
    cases = base.case_registry() + extra_cases()
    if len({c[0] for c in cases}) != len(cases): raise ValueError("Duplicate predeclared IDs")
    work = args.output_root.absolute() / ("tablet-native-leased-checkers-" + uuid.uuid4().hex);work.mkdir()
    journal = bounded.Journal(work / "outer")
    source, script, pure, fixtures = work / "tablet-native-leased-source.ps1", work / "checks.ps1", work / "pure-checks.json", work / "owned-fixtures"
    fixtures.mkdir()
    record = {"schema_version": 1, "operation": "tablet-native.leased-checkers.driver", "status": "running", "phase": "preparing", "failure": None,
              "source": bounded.file_identity(SOURCE), "driver": bounded.file_identity(Path(__file__)), "utility": bounded.file_identity(UTILITY),
              "predecessor": bounded.file_identity(PREDECESSOR), "base_source": bounded.file_identity(BASE_SOURCE),
              "expected_case_ids": [c[0] for c in cases], "expected_cases": len(cases), "predecessor_cases": 277,
              "case_scopes": {c[0]: ("original pure transport checker" if i < 277 else "owned-file lease/namespace helper; no engine") for i, c in enumerate(cases)},
              **{f: "not_run" for f in ("compiler_execution", "engine_execution", "adapter_top_level", "host_execution", "actual_process_stop", "native_listener_inventory")}}
    try:
        journal.save(record)
        if args.expected_source_sha256 and args.expected_source_sha256 != record["source"]["sha256"]:
            record["status"] = "stale_input";raise ValueError("Requested source identity differs")
        raw, fixture = SOURCE.read_bytes(), fixture_script(base, cases).encode("utf-8")
        admitted_source(base, raw, BASE_SOURCE.read_bytes())
        if source.write_bytes(raw) != len(raw) or script.write_bytes(fixture) != len(fixture): raise ValueError("Short fixture write")
        record["source_snapshot"], record["script"] = bounded.file_identity(source), bounded.file_identity(script)
        if record["source_snapshot"]["sha256"] != record["source"]["sha256"] or record["script"]["sha256"] != hashlib.sha256(fixture).hexdigest(): raise ValueError("Fixture capture mismatch")
        record.update(status="success", verification="source preparation only; lease filesystem effects not_run")
        if args.self_test:
            record["synthetic_validation"] = self_test(base, cases, record["source"]["sha256"])
            record["verification"] = "15 Python synthetic receipt/fixture cases; PowerShell and lease filesystem effects not_run"
        if args.run:
            record.update(status="running", phase="host_requested", verification="incomplete; isolated lease checker requested", host_execution="requested");journal.save(record)
            host = args.powershell_host.absolute()
            argv = [str(host), "-NoProfile", "-File", str(script), "-Source", str(source), "-ExpectedAdapterHash", record["source"]["sha256"], "-Result", str(pure), "-FixtureRoot", str(fixtures)]
            record["host_run"] = bounded.run_bounded(argv, ROOT, work / "host", 120, 5, expected_executable={"path": str(host), "sha256": args.expected_host_sha256})
            record["host_execution"] = "attempted"
            if pure.exists():
                record["pure_receipt"] = bounded.file_identity(pure, 2 * 1024 * 1024);record["pure_result"] = json.loads(pure.read_text(encoding="utf-8"))
            if record["host_run"]["status"] != "success":
                record["status"] = record["host_run"]["status"];raise ValueError("Isolated checker host failed; inspect retained original exceptions")
            validate_result(base, record.get("pure_result"), cases, source, record["source"]["sha256"])
            record["optional_capabilities"] = copy.deepcopy(record["pure_result"]["capability_observations"])
            record.update(status="success", verification=str(len(cases)) + " registered pure/owned-file checker cases verified", host_execution="executed_complete")
        for path, key in ((SOURCE, "source"), (source, "source_snapshot"), (script, "script"), (UTILITY, "utility"), (PREDECESSOR, "predecessor"), (BASE_SOURCE, "base_source"), (Path(__file__), "driver")):
            if bounded.file_identity(path) != record[key]:
                record["status"] = "stale_input";raise ValueError("Pinned checker input changed")
    except BaseException as error:
        if record["status"] in ("running", "success"): record["status"] = "failure"
        record["failure"] = bounded.error_info(error)
    finally:
        record["phase"] = "finalized"
        try: journal.save(record)
        except BaseException as error: record["status"] = "failure";record["receipt_failure"] = bounded.error_info(error)
    print(json.dumps({"receipt": str(work / "outer/result.json"), "status": record["status"], "verification": record.get("verification"), "failure": record.get("failure")}))
    return 0 if record["status"] == "success" else 1


if __name__ == "__main__": raise SystemExit(main())
