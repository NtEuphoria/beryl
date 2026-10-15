#!/usr/bin/env python3
"""Prepare, or explicitly execute, pure existing-suite protocol checker fixtures.

Only thirteen named PowerShell function definitions are AST-extracted. The adapter
entry, native listener inventory, process launch/cleanup, compiler and engine
are never invoked by the generated checker program.
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
SOURCE = ROOT / "scripts" / "tablet-suites-engine.ps1"
UTILITY = ROOT / "scripts" / "verify-host-readiness.py"
NAMES = ["Throw-Outcome", "Normal-Path", "Required-Field", "Assert-Text", "Assert-Names", "Assert-Int", "Fixed-Arguments", "Assert-Transport", "Assert-Parameters", "Assert-LoadedProjects", "Check-Identity", "Check-Suite", "Assert-RawResponse"]


def case_registry():
    """Complete positive/negative action identities exist before any execution."""
    cases = [
        ("identity-exact", "return", None,
         "$v=Check-Identity (Identity);if($v.token -cne $Token){throw 'Identity changed'}"),
        ("identity-source-unchanged", "return", None,
         "$v=Identity;$before=$v|ConvertTo-Json -Compress;$null=Check-Identity $v;if(($v|ConvertTo-Json -Compress) -cne $before){throw 'Decoder changed raw identity'}"),
        ("suite-exact", "return", None,
         "$v=Check-Suite (Suite);if($v.ok -ne 1 -or $v.detail -cne 'ui suite passed'){throw 'Suite changed'}"),
        ("suite-empty-detail", "return", None, "$v=Suite;$v.detail='';$null=Check-Suite $v"),
        ("suite-failure-zero-not-promoted", "return", None,
         "$v=Suite;$v.ok=0;$d=Check-Suite $v;if($d.ok -ne 0){throw 'Failed suite promoted'}"),
        ("suite-i32-min", "return", None, "$v=Suite;$v.ok=-2147483648L;$null=Check-Suite $v"),
        ("suite-i32-max", "return", None, "$v=Suite;$v.ok=2147483647L;$null=Check-Suite $v"),
        ("suite-detail-limit", "return", None, "$v=Suite;$v.detail='x'*65536;$null=Check-Suite $v"),
        ("suite-source-unchanged", "return", None,
         "$v=Suite;$before=$v|ConvertTo-Json -Compress;$null=Check-Suite $v;if(($v|ConvertTo-Json -Compress) -cne $before){throw 'Decoder changed raw suite'}"),
        ("transport-exact", "return", None, "Assert-Transport (Reply) 'BerylTabletSuiteIdentity'"),
        ("raw-exact", "return", None, "Assert-RawResponse (Reply)"),
        ("raw-suite-exact", "return", None,
         "$v=Reply;$v.Response=Suite;$v.Raw=$v.Response|ConvertTo-Json -Compress;Assert-RawResponse $v"),
        ("loaded-exact", "return", None,
         "Assert-LoadedProjects ([pscustomobject]@{'Loaded Projects'=@('ArmaReforger','core',$ProjectId)})"),
        ("loaded-owned-only", "return", None,
         "Assert-LoadedProjects ([pscustomobject]@{'Loaded Projects'=@($ProjectId)})"),
        ("parameters-loaded", "return", None, "Assert-Parameters 'GetLoadedProjects' @{}"),
        ("parameters-identity", "return", None, "Assert-Parameters 'BerylTabletSuiteIdentity' @{token=$Token}"),
        ("fixed-six-argv", "return", None,
         "$v=@(Fixed-Arguments $canonicalProject);$wanted=@('-gproj',(Join-Path $canonicalProject 'addon.gproj'),'-noOpenLastResource','-scriptAuthorizeAll','-wbmodule=WorldEditor','-run');if($v.Count -ne 6 -or ($v -join '|') -cne ($wanted -join '|') -or '-load' -cin $v){throw 'Fixed startup arguments differ'}"),
        ("normal-path", "return", None,
         "if((Normal-Path 'C:/fixture/') -cne ('C:'+ [char]92+'fixture')){throw 'Path normalization differs'}"),
    ]
    for field in ("token", "profile", "source_sha256"):
        cases += [
            ("identity-missing-" + field, "checker_rejection", "failure",
             f"$v=Identity;$v.PSObject.Properties.Remove('{field}');$null=Check-Identity $v"),
            ("identity-wrong-" + field, "checker_rejection", "stale_input",
             f"$v=Identity;$v.{field}='wrong';$null=Check-Identity $v"),
        ]
        for kind, value in (("int", "1"), ("bool", "$true"), ("null", "$null"),
                            ("oversize", "'x'*2049"), ("nul", "'x'+[char]0")):
            cases.append(("identity-" + field + "-" + kind, "checker_rejection", "failure",
                          f"$v=Identity;$v.{field}={value};$null=Check-Identity $v"))
    cases += [
        ("identity-extra", "checker_rejection", "failure", "$v=Identity;$v|Add-Member extra 1;$null=Check-Identity $v"),
        ("identity-null", "checker_rejection", "failure", "$null=Check-Identity $null"),
        ("suite-missing-ok", "checker_rejection", "failure", "$v=Suite;$v.PSObject.Properties.Remove('ok');$null=Check-Suite $v"),
        ("suite-missing-detail", "checker_rejection", "failure", "$v=Suite;$v.PSObject.Properties.Remove('detail');$null=Check-Suite $v"),
        ("suite-extra", "checker_rejection", "failure", "$v=Suite;$v|Add-Member extra 1;$null=Check-Suite $v"),
        ("suite-null", "checker_rejection", "failure", "$null=Check-Suite $null"),
    ]
    for kind, value in (("bool", "$true"), ("double", "[double]1"), ("string", "'1'"),
                        ("null", "$null"), ("high", "2147483648L"), ("low", "-2147483649L")):
        cases.append(("suite-ok-" + kind, "checker_rejection", "failure", f"$v=Suite;$v.ok={value};$null=Check-Suite $v"))
    for kind, value in (("bool", "$true"), ("int", "1"), ("null", "$null"),
                        ("oversize", "'x'*65537"), ("nul", "'x'+[char]0")):
        cases.append(("suite-detail-" + kind, "checker_rejection", "failure", f"$v=Suite;$v.detail={value};$null=Check-Suite $v"))
    for field in ("Ok", "Function", "ErrorCode", "Response", "Raw"):
        cases.append(("transport-missing-" + field, "checker_rejection", "failure",
                      f"$v=Reply;$v.PSObject.Properties.Remove('{field}');Assert-Transport $v 'BerylTabletSuiteIdentity'"))
    cases += [
        ("transport-ok01", "checker_rejection", "failure", "$v=Reply;$v.Ok=1;Assert-Transport $v 'BerylTabletSuiteIdentity'"),
        ("transport-false", "checker_rejection", "failure", "$v=Reply;$v.Ok=$false;Assert-Transport $v 'BerylTabletSuiteIdentity'"),
        ("transport-error", "checker_rejection", "failure", "$v=Reply;$v.ErrorCode='Error';Assert-Transport $v 'BerylTabletSuiteIdentity'"),
        ("transport-wrong-function", "checker_rejection", "failure", "$v=Reply;$v.Function='Save';Assert-Transport $v 'BerylTabletSuiteIdentity'"),
        ("transport-raw-type", "checker_rejection", "failure", "$v=Reply;$v.Raw=1;Assert-Transport $v 'BerylTabletSuiteIdentity'"),
        ("transport-raw-limit", "checker_rejection", "failure", "$v=Reply;$v.Raw='x'*(1MB+1);Assert-Transport $v 'BerylTabletSuiteIdentity'"),
        ("transport-extra", "checker_rejection", "failure", "$v=Reply;$v|Add-Member extra 1;Assert-Transport $v 'BerylTabletSuiteIdentity'"),
        ("transport-null", "checker_rejection", "failure", "Assert-Transport $null 'BerylTabletSuiteIdentity'"),
        ("raw-malformed", "checker_rejection", "failure", "$v=Reply;$v.Raw='{bad';Assert-RawResponse $v"),
        ("raw-null", "checker_rejection", "failure", "$v=Reply;$v.Raw='null';Assert-RawResponse $v"),
        ("raw-decoded-null", "checker_rejection", "failure", "$v=Reply;$v.Response=$null;Assert-RawResponse $v"),
        ("raw-field-extra", "checker_rejection", "failure", "$v=Reply;$v.Raw='{}';Assert-RawResponse $v"),
        ("raw-value-mismatch", "checker_rejection", "failure", "$v=Reply;$v.Response.token='c'*64;Assert-RawResponse $v"),
        ("raw-type-mismatch", "checker_rejection", "failure", "$v=Reply;$v.Response=Suite;$v.Raw='{\"ok\":true,\"detail\":\"ui suite passed\"}';Assert-RawResponse $v"),
        ("loaded-empty", "checker_rejection", "stale_input", "Assert-LoadedProjects ([pscustomobject]@{'Loaded Projects'=@()})"),
        ("loaded-scalar", "checker_rejection", "stale_input", "Assert-LoadedProjects ([pscustomobject]@{'Loaded Projects'=$ProjectId})"),
        ("loaded-foreign", "checker_rejection", "stale_input", "Assert-LoadedProjects ([pscustomobject]@{'Loaded Projects'=@($ProjectId,'Foreign')})"),
        ("loaded-duplicate", "checker_rejection", "stale_input", "Assert-LoadedProjects ([pscustomobject]@{'Loaded Projects'=@($ProjectId,$ProjectId)})"),
        ("loaded-overflow", "checker_rejection", "stale_input", "Assert-LoadedProjects ([pscustomobject]@{'Loaded Projects'=@($ProjectId)*9})"),
        ("loaded-int", "checker_rejection", "failure", "Assert-LoadedProjects ([pscustomobject]@{'Loaded Projects'=@($ProjectId,1)})"),
        ("loaded-extra-field", "checker_rejection", "failure", "Assert-LoadedProjects ([pscustomobject]@{'Loaded Projects'=@($ProjectId);extra=1})"),
        ("loaded-missing-field", "checker_rejection", "failure", "Assert-LoadedProjects ([pscustomobject]@{})"),
        ("parameters-loaded-extra", "checker_rejection", "failure", "Assert-Parameters 'GetLoadedProjects' @{extra=1}"),
        ("parameters-identity-wrong-token", "checker_rejection", "stale_input", "Assert-Parameters 'BerylTabletSuiteIdentity' @{token='c'*64}"),
        ("parameters-identity-missing", "checker_rejection", "stale_input", "Assert-Parameters 'BerylTabletSuiteIdentity' @{}"),
        ("parameters-identity-extra", "checker_rejection", "stale_input", "Assert-Parameters 'BerylTabletSuiteIdentity' @{token=$Token;extra=1}"),
        ("parameters-identity-bool", "checker_rejection", "stale_input", "Assert-Parameters 'BerylTabletSuiteIdentity' @{token=$true}"),
        ("parameters-suite-missing", "checker_rejection", "failure", "Assert-Parameters 'SPK_MeshSelfTest' @{suite='ui'}"),
        ("parameters-suite-extra", "checker_rejection", "failure", "Assert-Parameters 'SPK_MeshSelfTest' @{suite='ui';arg='';extra=1}"),
        ("parameters-suite-unknown", "checker_rejection", "failure", "Assert-Parameters 'SPK_MeshSelfTest' @{suite='all';arg=''}"),
        ("parameters-suite-case", "checker_rejection", "failure", "Assert-Parameters 'SPK_MeshSelfTest' @{suite='UI';arg=''}"),
        ("parameters-suite-bool", "checker_rejection", "failure", "Assert-Parameters 'SPK_MeshSelfTest' @{suite=$true;arg=''}"),
        ("parameters-suite-wrong-arg", "checker_rejection", "failure", "Assert-Parameters 'SPK_MeshSelfTest' @{suite='schema';arg='Prefabs/SPK_Tablet.et'}"),
        ("parameters-suite-empty-selection", "checker_rejection", "failure", "$selections=@();Assert-Parameters 'SPK_MeshSelfTest' @{suite='ui';arg=''}"),
        ("parameters-suite-duplicate-selection", "checker_rejection", "failure", "$selections=@(@{suite='ui';arg=''},@{suite='ui';arg=''});if($selections.Count -ne 2){throw 'Duplicate fixture incomplete'};Assert-Parameters 'SPK_MeshSelfTest' @{suite='ui';arg=''}"),
    ]
    for name, arg in (("ui", ""), ("screen", ""), ("actions", ""), ("clicks", ""),
                      ("schema", "{B37EEB64E149CBAD}Prefabs/SPK_Tablet.et")):
        cases.append(("parameters-suite-" + name, "return", None,
                      f"Assert-Parameters 'SPK_MeshSelfTest' @{{suite='{name}';arg='{arg}'}}"))
    for name in ("OpenResource", "Save", "CreateWorld", "Play", "Spawn", "IsWorkbenchRunning"):
        cases.append(("forbidden-rpc-" + name.lower(), "checker_rejection", "failure",
                      f"Assert-Parameters '{name}' @{{}}"))
    ids = [case[0] for case in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate predeclared suite protocol identity")
    return tuple(cases)


HEADER = r'''param([string]$Source,[string]$ExpectedAdapterHash,[string]$Result)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$expectedCaseIds=__EXPECTED__
$names=__NAMES__
$ExpectedSourceHash='b'*64
$suiteProfile='sparkos.tablet.existing-suites-runtime.v1'
$selections=@(@{suite='ui';arg=''},@{suite='screen';arg=''},@{suite='actions';arg=''},@{suite='clicks';arg=''},@{suite='schema';arg='{B37EEB64E149CBAD}Prefabs/SPK_Tablet.et'})
$Token='a'*64
$ProjectId='BerylTabletSuiteCheckProbe'
$canonicalProject='C:/fixture'

$record=@{status='failure';failure=$null;cleanup_errors=@();evidence_errors=@()}

$cases=[Collections.Generic.List[object]]::new()
$lastReceiptHash=$null
$receipt=[ordered]@{schema_version=1;operation='tablet-suites.checkers.inert';status='running';source=$Source;source_sha256=$ExpectedAdapterHash;
 function_names=$names;expected_case_ids=$expectedCaseIds;expected_cases=$expectedCaseIds.Count;cases=@();completed_case_ids=@();complete_expected_case_set=$false;
 compiler_execution='not_run';engine_execution='not_run';adapter_top_level='not_run';actual_process_stop='not_run';native_listener_inventory='not_run';failure=$null}
function Save-Receipt {
 $receipt.cases=@($cases.ToArray());$receipt.completed_case_ids=@($cases | ForEach-Object {$_.id});$receipt.case_count=$cases.Count
 $receipt.complete_expected_case_set=(($receipt.completed_case_ids -join '|') -ceq ($expectedCaseIds -join '|'))
 if([IO.File]::Exists($Result)) {
  if($null -eq $script:lastReceiptHash -or (Get-FileHash -LiteralPath $Result -Algorithm SHA256).Hash.ToLowerInvariant() -cne $script:lastReceiptHash){throw 'Checker receipt changed by another writer'}
 }
 $tmp=$Result+'.'+[Guid]::NewGuid().ToString('N')+'.tmp'
 $bytes=[Text.UTF8Encoding]::new($false).GetBytes(($receipt|ConvertTo-Json -Depth 20)+[Environment]::NewLine)
 $stream=[IO.File]::Open($tmp,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
 try{$stream.Write($bytes,0,$bytes.Length);$stream.Flush($true)}finally{$stream.Dispose()}
 $hash=[Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($bytes)).ToLowerInvariant()
 if((Get-FileHash -LiteralPath $tmp -Algorithm SHA256).Hash.ToLowerInvariant() -cne $hash){throw 'Checker receipt temporary readback mismatch'}
 [IO.File]::Move($tmp,$Result,$true)
 if((Get-FileHash -LiteralPath $Result -Algorithm SHA256).Hash.ToLowerInvariant() -cne $hash){throw 'Checker receipt final readback mismatch'}
 $script:lastReceiptHash=$hash
}
function Exception-Detail([object]$ErrorRecord) {
 return [ordered]@{type=$ErrorRecord.Exception.GetType().FullName;message=$ErrorRecord.Exception.Message;
  fully_qualified_error_id=$ErrorRecord.FullyQualifiedErrorId;position=$ErrorRecord.InvocationInfo.PositionMessage;script_stack=$ErrorRecord.ScriptStackTrace}
}
function Case([string]$Id,[string]$Expected,[object]$ExpectedStatus,[scriptblock]$Action) {
 if($Id -cnotin $expectedCaseIds -or @($cases | Where-Object {$_.id -ceq $Id}).Count){throw 'Unknown/duplicate predeclared case'}
 $record=@{status='failure';failure=$null;cleanup_errors=@();evidence_errors=@()}
 $canonicalProject='C:/fixture';$selections=Fixed-Selections;
 
 $case=[ordered]@{id=$Id;status='failure';expected=$Expected;actual='return';expected_status=$ExpectedStatus;actual_status=$null;original_exception=$null}
 try {&$Action;if($Expected -ceq 'return'){$case.status='success'}} catch {
  $case.actual='exception';$case.actual_status=$record.status;$case.original_exception=Exception-Detail $_
  if($Expected -ceq 'checker_rejection' -and $_.Exception -is [InvalidOperationException] -and $record.status -ceq $ExpectedStatus){$case.status='success';$case.actual='checker_rejection'}
 }
 $cases.Add($case);Save-Receipt
}
function Fixed-Selections { return @(@{suite='ui';arg=''},@{suite='screen';arg=''},@{suite='actions';arg=''},@{suite='clicks';arg=''},@{suite='schema';arg='{B37EEB64E149CBAD}Prefabs/SPK_Tablet.et'}) }
function Identity { return [pscustomobject][ordered]@{token=$Token;profile=$suiteProfile;source_sha256=$ExpectedSourceHash} }
function Suite { return [pscustomobject][ordered]@{ok=1;detail='ui suite passed'} }
function Reply {
 $response=Identity
 return [pscustomobject][ordered]@{Ok=$true;Function='BerylTabletSuiteIdentity';ErrorCode='Ok';Response=$response;Raw=($response|ConvertTo-Json -Depth 10 -Compress)}
}
try {
 Save-Receipt
 if($expectedCaseIds.Count -ne __COUNT__ -or @($expectedCaseIds|Select-Object -Unique).Count -ne __COUNT__){throw 'Invalid expected fixture identities'}
 $sourceBytes=[IO.File]::ReadAllBytes($Source)
 if([Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($sourceBytes)).ToLowerInvariant() -cne $ExpectedAdapterHash){throw 'Retained source identity differs'}
 $sourceText=[Text.UTF8Encoding]::new($false,$true).GetString($sourceBytes)
 $tokens=$null;$errors=$null
 $ast=[Management.Automation.Language.Parser]::ParseInput($sourceText,[ref]$tokens,[ref]$errors)
 if($errors.Count){throw 'Tablet-suite adapter PowerShell parse error'}
 foreach($name in $names) {
  $definitions=@($ast.FindAll({param($node) $node -is [Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -ceq $name},$true))
  if($definitions.Count -ne 1){throw ('Missing/duplicate pure checker '+$name)}
  Invoke-Expression $definitions[0].Extent.Text
 }
__CASES__
 if(($cases.id -join '|') -cne ($expectedCaseIds -join '|')){throw 'Completed fixture set differs'}
 $receipt.passed=@($cases|Where-Object {$_.status -ceq 'success'}).Count
 $receipt.failed=@($cases|Where-Object {$_.status -cne 'success'}).Count
 if($receipt.failed){throw 'One or more pure checker contracts failed'}
 $receipt.status='success'
} catch {$receipt.failure=Exception-Detail $_;$receipt.status='failure'} finally {Save-Receipt}
if($receipt.status -cne 'success'){Write-Error 'Pure tablet-suites checker failure; inspect original_exception';exit 1}
'''


def ps_array(values):
    return "@(" + ",".join("'" + value + "'" for value in values) + ")"


def fixture_script(cases):
    actions = []
    for case_id, expected, status, action in cases:
        status_arg = "$null" if status is None else "'" + status + "'"
        actions.append(f" Case '{case_id}' '{expected}' {status_arg} {{{action}}}")
    return HEADER.replace("__COUNT__", str(len(cases))).replace("__EXPECTED__", ps_array([case[0] for case in cases])).replace("__NAMES__", ps_array(NAMES)).replace("__CASES__", "\n".join(actions))


def utility_module():
    spec = importlib.util.spec_from_file_location("tablet-suites_checker_host_bounds", UTILITY)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def validate_result(value, cases, source, source_hash):
    ids = [case[0] for case in cases]
    if type(value) is not dict or type(value.get("schema_version")) is not int or value["schema_version"] != 1:
        raise ValueError("Malformed pure checker receipt")
    if value.get("operation") != "tablet-suites.checkers.inert" or value.get("status") != "success" or value.get("failure") is not None:
        raise ValueError("Pure checker execution did not succeed")
    if value.get("source") != str(source) or value.get("source_sha256") != source_hash or value.get("function_names") != NAMES:
        raise ValueError("Checker function/source identity differs")
    if value.get("expected_case_ids") != ids or value.get("completed_case_ids") != ids or value.get("complete_expected_case_set") is not True:
        raise ValueError("Missing/unknown/duplicate/reordered checker identities")
    for name, wanted in (("expected_cases", len(cases)), ("case_count", len(cases)), ("passed", len(cases)), ("failed", 0)):
        if type(value.get(name)) is not int or value[name] != wanted:
            raise ValueError("Incomplete pure checker counts")
    rows = value.get("cases")
    if type(rows) is not list or len(rows) != len(cases):
        raise ValueError("Incomplete pure checker rows")
    fields = {"id", "status", "expected", "actual", "expected_status", "actual_status", "original_exception"}
    exception_fields = {"type", "message", "fully_qualified_error_id", "position", "script_stack"}
    for row, (case_id, expected, wanted_status, _) in zip(rows, cases):
        if type(row) is not dict or set(row) != fields or row["id"] != case_id or row["status"] != "success" or row["expected"] != expected or row["actual"] != expected or row["expected_status"] != wanted_status:
            raise ValueError("Unexpected pure checker row/outcome")
        if expected == "return":
            if row["actual_status"] is not None or row["original_exception"] is not None:
                raise ValueError("Successful return contains an exception")
        else:
            original = row["original_exception"]
            if row["actual_status"] != wanted_status or type(original) is not dict or set(original) != exception_fields or original["type"] != "System.InvalidOperationException" or type(original["message"]) is not str or not original["message"]:
                raise ValueError("Checker rejection lost original exception/status")
    for field in ("compiler_execution", "engine_execution", "adapter_top_level", "actual_process_stop", "native_listener_inventory"):
        if value.get(field) != "not_run":
            raise ValueError("Unsupported execution scope in pure receipt")


def synthetic_result(cases, source, source_hash):
    rows = []
    for case_id, expected, status, _ in cases:
        rows.append({"id": case_id, "status": "success", "expected": expected, "actual": expected, "expected_status": status,
                     "actual_status": status, "original_exception": None if expected == "return" else
                     {"type": "System.InvalidOperationException", "message": "synthetic checker rejection",
                      "fully_qualified_error_id": "synthetic", "position": "", "script_stack": ""}})
    return {"schema_version": 1, "operation": "tablet-suites.checkers.inert", "status": "success", "failure": None,
            "source": str(source), "source_sha256": source_hash, "function_names": NAMES,
            "expected_case_ids": [case[0] for case in cases], "completed_case_ids": [case[0] for case in cases],
            "complete_expected_case_set": True, "expected_cases": len(cases), "case_count": len(cases), "passed": len(cases), "failed": 0,
            "cases": rows, **{field: "not_run" for field in ("compiler_execution", "engine_execution", "adapter_top_level", "actual_process_stop", "native_listener_inventory")}}


def self_test(cases, source_hash):
    source = Path("source-only-synthetic.ps1")
    sample = synthetic_result(cases, source, source_hash)
    rejection = next(i for i, case in enumerate(cases) if case[1] == "checker_rejection")
    faults = [("schema-bool", lambda v: v.update(schema_version=True)),
              ("missing-case", lambda v: v["cases"].pop()),
              ("wrong-function", lambda v: v["function_names"].append("Invoke-Call")),
              ("missing-completion", lambda v: v["completed_case_ids"].pop()),
              ("duplicate-completion", lambda v: v["completed_case_ids"].append(v["completed_case_ids"][0])),
              ("wrong-source", lambda v: v.update(source_sha256="0" * 64)),
              ("wrong-count", lambda v: v.update(passed=len(cases)+1)),
              ("missing-exception", lambda v: v["cases"][rejection].update(original_exception=None)),
              ("wrong-status", lambda v: v["cases"][rejection].update(actual_status="unavailable")),
              ("generic-exception", lambda v: v["cases"][rejection]["original_exception"].update(type="System.Exception")),
              ("false-scope", lambda v: v.update(engine_execution="executed")),
              ("failure-retained", lambda v: v.update(failure={"message": "failed"})),
              ("unexpected-field", lambda v: v["cases"][0].update(extra=True))]
    results = []
    fixture = fixture_script(cases)
    if ("$expected=" in fixture or "$expectedCaseIds=" not in fixture or "\f" in fixture or
            "('C:'+ [char]92+'fixture')" not in fixture or "__CASES__" in fixture or
            "param([string]$Source,[string]$ExpectedAdapterHash" not in fixture or
            len(NAMES) != 13 or any(name in NAMES for name in ("Invoke-Call", "Assert-Inputs", "Wait-Listener", "Assert-OwnedSession"))):
        raise ValueError("Generated fixture registry, source identity or pure extraction differs")
    results.append({"id": "synthetic-fixture-literals", "status": "success"})
    validate_result(copy.deepcopy(sample), cases, source, source_hash)
    results.append({"id": "synthetic-positive", "status": "success"})
    for name, mutation in faults:
        value = copy.deepcopy(sample)
        mutation(value)
        try:
            validate_result(value, cases, source, source_hash)
        except ValueError:
            results.append({"id": name, "status": "success"})
        else:
            raise ValueError("Synthetic malformed receipt admitted: " + name)
    return {"scope": "Python receipt/fixture validation only; PowerShell checker execution not_run", "expected_case_ids": ["synthetic-fixture-literals", "synthetic-positive"] + [name for name, _ in faults],
            "cases": results, "complete_expected_case_set": True}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--run", action="store_true", help="Explicitly execute pure checker functions only")
    modes.add_argument("--self-test", action="store_true", help="Python synthetic receipt validation only")
    parser.add_argument("--powershell-host", type=Path)
    parser.add_argument("--expected-host-sha256")
    parser.add_argument("--expected-source-sha256")
    parser.add_argument("--output-root", type=Path, default=ROOT / "build")
    args = parser.parse_args(argv)
    if args.run and (args.powershell_host is None or args.expected_host_sha256 is None or args.expected_source_sha256 is None):
        parser.error("--run requires explicit host path/hash and source hash")
    bounded = utility_module()
    cases = case_registry()
    work = args.output_root.absolute() / ("tablet-suites-checkers-" + uuid.uuid4().hex)
    work.mkdir()
    journal = bounded.Journal(work / "outer")
    source, script, pure_receipt = work / "tablet-suites-source.ps1", work / "checks.ps1", work / "pure-checks.json"
    record = {"schema_version": 1, "operation": "tablet-suites.checkers.driver", "status": "running", "phase": "preparing",
              "expected_case_ids": [case[0] for case in cases], "expected_cases": len(cases), "source": bounded.file_identity(SOURCE),
              "driver": bounded.file_identity(Path(__file__)), "utility": bounded.file_identity(UTILITY), "failure": None,
              **{field: "not_run" for field in ("compiler_execution", "engine_execution", "adapter_top_level", "host_execution", "actual_process_stop", "native_listener_inventory")}}
    try:
        journal.save(record)
        if args.expected_source_sha256 and record["source"]["sha256"] != args.expected_source_sha256:
            record["status"] = "stale_input"
            raise ValueError("Current adapter differs from requested source identity")
        content = SOURCE.read_bytes()
        fixture = fixture_script(cases).encode("utf-8")
        if source.write_bytes(content) != len(content) or script.write_bytes(fixture) != len(fixture):
            raise ValueError("Short checker preparation write")
        record["source_snapshot"] = bounded.file_identity(source)
        record["script"] = bounded.file_identity(script)
        if record["source_snapshot"]["sha256"] != record["source"]["sha256"] or record["script"]["sha256"] != hashlib.sha256(fixture).hexdigest() or bounded.file_identity(SOURCE) != record["source"]:
            record["status"] = "stale_input"
            raise ValueError("Source/fixture changed while preparing exact bytes")
        record.update(status="success", phase="source_prepared", verification="not_run; preparation only")
        journal.save(record)
        if args.self_test:
            record["synthetic_validation"] = self_test(cases, record["source"]["sha256"])
            record["verification"] = "15 Python synthetic receipt/fixture cases; PowerShell execution not_run"
        if args.run:
            record.update(status="running", phase="host_requested", host_execution="requested",
                          verification="incomplete; checker run requested")
            journal.save(record)
            host = args.powershell_host.absolute()
            arguments = [str(host), "-NoProfile", "-File", str(script), "-Source", str(source),
                         "-ExpectedAdapterHash", record["source"]["sha256"], "-Result", str(pure_receipt)]
            record["host_run"] = bounded.run_bounded(arguments, ROOT, work / "host", 45, 5,
                                                      expected_executable={"path": str(host), "sha256": args.expected_host_sha256})
            record["host_execution"] = "attempted"
            if pure_receipt.exists():
                record["pure_receipt"] = bounded.file_identity(pure_receipt, 1024 * 1024)
                record["pure_result"] = json.loads(pure_receipt.read_text(encoding="utf-8"))
            if record["host_run"]["status"] != "success":
                record["status"] = record["host_run"]["status"]
                raise ValueError("Pure checker host failed; inspect retained per-case exceptions")
            validate_result(record.get("pure_result"), cases, source, record["source"]["sha256"])
            record.update(status="success", verification=f"{len(cases)} pure existing-suite protocol checker cases verified", host_execution="executed_complete")
        for path, key in ((SOURCE, "source"), (source, "source_snapshot"), (script, "script"), (UTILITY, "utility"), (Path(__file__), "driver")):
            if bounded.file_identity(path) != record[key]:
                record["status"] = "stale_input"
                raise ValueError("Pinned checker input changed during operation")
    except BaseException as exc:
        if record["status"] in ("success", "running"):
            record["status"] = "failure"
        record["failure"] = bounded.error_info(exc)
    finally:
        record["phase"] = "finalized"
        try:
            journal.save(record)
        except BaseException as exc:
            record["status"] = "failure"
            record["receipt_failure"] = bounded.error_info(exc)
    print(json.dumps({"receipt": str(work / "outer" / "result.json"), "status": record["status"],
                      "verification": record.get("verification"), "failure": record.get("failure")}))
    return 0 if record["status"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
