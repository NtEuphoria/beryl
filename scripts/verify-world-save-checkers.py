#!/usr/bin/env python3
"""Prepare, or explicitly execute, pure read-only eligibility checker fixtures.

Only fourteen named PowerShell function definitions are AST-extracted. The adapter
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
SOURCE = ROOT / "scripts" / "world-save-engine.ps1"
UTILITY = ROOT / "scripts" / "verify-host-readiness.py"
NAMES = ["Throw-Outcome", "Normal-Path", "Required-Field", "Assert-Text",
         "Normalize-Bool", "Assert-Names", "Check-Response", "Eligibility-Status",
         "Fixed-Arguments", "Assert-Transport", "Assert-Parameters",
         "Assert-LoadedProjects", "Assert-FutureOutput", "Record-CleanupError"]
STRINGS = ["token", "action", "status", "failure", "output_path", "wb_world_path", "game_world_path"]
BOOLS = ["game_present", "in_play_mode", "module_present", "wb_api_present",
         "wb_world_present", "wb_edit_mode", "wb_game_mode", "game_editor_present",
         "game_api_present", "game_world_present", "api_same", "world_same"]


def case_registry():
    """Fixed actions and expected outcomes exist before checker execution."""
    cases = [
        ("decode-json-bools", "return", None,
         "$v=Base;$d=Check-Response $v;if($d.codec.numeric_boolean_fields.Count -ne 0 -or $d.response.wb_edit_mode -isnot [bool]){throw 'JSON bool codec mismatch'}"),
        ("decode-bool01", "return", None,
         "$v=Base;foreach($name in $bools){$v.$name=[int]$v.$name};$d=Check-Response $v;if(($d.codec.numeric_boolean_fields -join '|') -cne ($bools -join '|')){throw 'Numeric codec ordering mismatch'}"),
        ("raw-response-unchanged", "return", None,
         "$v=Base;foreach($name in $bools){$v.$name=[int]$v.$name};$before=$v|ConvertTo-Json -Depth 10 -Compress;$null=Check-Response $v;if(($v|ConvertTo-Json -Depth 10 -Compress) -cne $before){throw 'Decoder modified raw fields'}"),
        ("eligible-exact", "return", None,
         "if((Eligibility-Status (Check-Response (Base)).response) -cne 'success'){throw 'Exact eligibility rejected'}"),
        ("output-slash-case-equivalent", "return", None,
         "$v=Base;$v.output_path=$canonicalOutput.Replace([char]47,[char]92).ToUpperInvariant();$null=Check-Response $v"),
        ("normal-path", "return", None,
         "if((Normal-Path 'C:/fixture/') -cne ('C:'+ [char]92+'fixture')){throw 'Path normalization differs'}"),
        ("unavailable-named-world", "return", None,
         "$v=Base;$v.status='unavailable';$v.failure='Editor world is already named';$v.wb_world_path='worlds/named.ent';if((Eligibility-Status (Check-Response $v).response) -cne 'unavailable'){throw 'Honest unavailable was rejected'}"),
        ("unavailable-identity-difference", "return", None,
         "$v=Base;$v.status='unavailable';$v.failure='Editor world identities differ';$v.world_same=$false;if((Eligibility-Status (Check-Response $v).response) -cne 'unavailable'){throw 'Identity difference promoted'}"),
        ("unavailable-missing-game-context", "return", None,
         "$v=Base;$v.status='unavailable';$v.failure='Game unavailable';foreach($n in @('game_present','game_editor_present','game_api_present','game_world_present','api_same','world_same')){$v.$n=$false};if((Eligibility-Status (Check-Response $v).response) -cne 'unavailable'){throw 'Missing game promoted'}"),
        ("unavailable-missing-wb-context", "return", None,
         "$v=Base;$v.status='unavailable';$v.failure='Workbench context unavailable';foreach($n in @('module_present','wb_api_present','wb_world_present','wb_edit_mode','api_same','world_same')){$v.$n=$false};if((Eligibility-Status (Check-Response $v).response) -cne 'unavailable'){throw 'Missing WB context promoted'}"),
        ("future-output-virtual-absent", "return", None, "Assert-FutureOutput"),
        ("fixed-six-argv", "return", None,
         "$v=@(Fixed-Arguments $canonicalProject);$wanted=@('-gproj',(Join-Path $canonicalProject 'addon.gproj'),'-noOpenLastResource','-scriptAuthorizeAll','-wbmodule=WorldEditor','-run');if($v.Count -ne 6 -or ($v -join '|') -cne ($wanted -join '|') -or '-load' -cin $v){throw 'Fixed startup arguments differ'}"),
        ("cleanup-errors-additive-primary-preserved", "return", None,
         "$record.status='timeout';$record.failure='primary';Record-CleanupError 'owned_cleanup' 'secondary';Record-CleanupError 'gate_cleanup' 'third';if($record.status -cne 'timeout' -or $record.failure -cne 'primary' -or $record.cleanup_errors.Count -ne 2 -or $record.evidence_errors.Count -ne 2){throw 'Cleanup replaced primary failure'}"),
    ]
    for field in STRINGS + BOOLS:
        cases.append(("missing-" + field.replace("_", "-"), "checker_rejection", "failure",
                      f"$v=Base;$v.PSObject.Properties.Remove('{field}');$null=Check-Response $v"))
    for field in BOOLS:
        for kind, value in (("two", "2"), ("string", "'1'"), ("double", "[double]1"), ("null", "$null")):
            cases.append(("bool-" + field.replace("_", "-") + "-" + kind, "checker_rejection", "failure",
                          f"$v=Base;$v.{field}={value};$null=Check-Response $v"))
        expression = "$true" if field in ("in_play_mode", "wb_game_mode") else "$false"
        cases.append(("false-eligible-" + field.replace("_", "-"), "checker_rejection", "failure",
                      f"$v=Base;$v.{field}={expression};$null=Eligibility-Status (Check-Response $v).response"))
    for field in STRINGS:
        for kind, value in (("integer", "1"), ("oversize", "'x'*2049"), ("nul", "'x'+[char]0")):
            cases.append(("text-" + field.replace("_", "-") + "-" + kind, "checker_rejection", "failure",
                          f"$v=Base;$v.{field}={value};$null=Check-Response $v"))
    cases += [
        ("response-null", "checker_rejection", "failure", "$null=Check-Response $null"),
        ("response-extra", "checker_rejection", "failure", "$v=Base;$v|Add-Member extra 1;$null=Check-Response $v"),
        ("wrong-token", "checker_rejection", "stale_input", "$v=Base;$v.token='b'*64;$null=Check-Response $v"),
        ("wrong-action", "checker_rejection", "stale_input", "$v=Base;$v.action='save';$null=Check-Response $v"),
        ("wrong-output", "checker_rejection", "stale_input", "$v=Base;$v.output_path='C:/foreign/world.ent';$null=Check-Response $v"),
        ("relative-output", "checker_rejection", "stale_input", "$v=Base;$v.output_path='engine-authored/BerylEngineAuthored.ent';$null=Check-Response $v"),
        ("unknown-status", "checker_rejection", "failure", "$v=Base;$v.status='success';$null=Check-Response $v"),
        ("eligible-with-failure", "checker_rejection", "failure", "$v=Base;$v.failure='failed';$null=Eligibility-Status (Check-Response $v).response"),
        ("unavailable-but-eligible", "checker_rejection", "failure", "$v=Base;$v.status='unavailable';$v.failure='wrong';$null=Eligibility-Status (Check-Response $v).response"),
        ("unavailable-no-reason", "checker_rejection", "failure", "$v=Base;$v.status='unavailable';$v.world_same=$false;$null=Eligibility-Status (Check-Response $v).response"),
        ("observer-failure", "checker_rejection", "failure", "$v=Base;$v.status='failure';$v.failure='observed failure';$null=Eligibility-Status (Check-Response $v).response"),
        ("eligible-wb-named", "checker_rejection", "failure", "$v=Base;$v.wb_world_path='named.ent';$null=Eligibility-Status (Check-Response $v).response"),
        ("eligible-game-named", "checker_rejection", "failure", "$v=Base;$v.game_world_path='named.ent';$null=Eligibility-Status (Check-Response $v).response"),
        ("future-file-present", "checker_rejection", "stale_input", "$mockFile=$true;Assert-FutureOutput"),
        ("future-parent-present", "checker_rejection", "stale_input", "$mockParent=$true;Assert-FutureOutput"),
        ("future-linked-ancestor", "checker_rejection", "stale_input", "$mockLink=$true;Assert-FutureOutput"),
        ("future-foreign-path", "checker_rejection", "stale_input", "$canonicalOutput='C:/foreign/world.ent';Assert-FutureOutput"),
    ]
    # Each dependency contradiction is retained as a separate fixed case.
    for name, action in [
        ("play-without-game", "$v.game_present=$false;$v.in_play_mode=$true"),
        ("wb-api-without-module", "$v.module_present=$false"),
        ("wb-world-without-api", "$v.wb_api_present=$false"),
        ("game-editor-in-play", "$v.in_play_mode=$true"),
        ("game-api-without-editor", "$v.game_editor_present=$false"),
        ("game-world-without-api", "$v.game_api_present=$false"),
        ("api-equality-without-api", "$v.game_api_present=$false;$v.game_world_present=$false;$v.world_same=$false"),
        ("world-equality-without-world", "$v.game_world_present=$false"),
    ]:
        cases.append(("contradiction-" + name, "checker_rejection", "failure",
                      "$v=Base;$v.status='unavailable';$v.failure='missing context';" + action + ";$null=Eligibility-Status (Check-Response $v).response"))
    cases += [
        ("parameters-health", "return", None, "Assert-Parameters 'IsWorkbenchRunning' @{}"),
        ("parameters-loaded", "return", None, "Assert-Parameters 'GetLoadedProjects' @{}"),
        ("parameters-observe", "return", None, "Assert-Parameters 'BerylWorldSaveEligibility' @{token=$Token;action='observe'}"),
        ("parameters-health-extra", "checker_rejection", "failure", "Assert-Parameters 'IsWorkbenchRunning' @{extra=1}"),
        ("parameters-loaded-extra", "checker_rejection", "failure", "Assert-Parameters 'GetLoadedProjects' @{extra=1}"),
        ("parameters-token", "checker_rejection", "stale_input", "Assert-Parameters 'BerylWorldSaveEligibility' @{token='b'*64;action='observe'}"),
        ("parameters-action", "checker_rejection", "stale_input", "Assert-Parameters 'BerylWorldSaveEligibility' @{token=$Token;action='save'}"),
        ("parameters-missing", "checker_rejection", "stale_input", "Assert-Parameters 'BerylWorldSaveEligibility' @{token=$Token}"),
        ("parameters-extra", "checker_rejection", "stale_input", "Assert-Parameters 'BerylWorldSaveEligibility' @{token=$Token;action='observe';extra=1}"),
    ]
    for name in ("OpenResource", "Save", "CreateWorld", "Play", "Spawn"):
        cases.append(("forbidden-rpc-" + name.lower(), "checker_rejection", "failure", f"Assert-Parameters '{name}' @{{}}"))
    cases += [
        ("transport-valid", "return", None, "Assert-Transport (Reply) 'BerylWorldSaveEligibility'"),
        ("transport-ok01-rejected", "checker_rejection", "failure", "$v=Reply;$v.Ok=1;Assert-Transport $v 'BerylWorldSaveEligibility'"),
        ("transport-error", "checker_rejection", "failure", "$v=Reply;$v.ErrorCode='Error';Assert-Transport $v 'BerylWorldSaveEligibility'"),
        ("transport-wrong-function", "checker_rejection", "failure", "$v=Reply;$v.Function='Save';Assert-Transport $v 'BerylWorldSaveEligibility'"),
        ("transport-raw-type", "checker_rejection", "failure", "$v=Reply;$v.Raw=1;Assert-Transport $v 'BerylWorldSaveEligibility'"),
        ("transport-extra", "checker_rejection", "failure", "$v=Reply;$v|Add-Member extra 1;Assert-Transport $v 'BerylWorldSaveEligibility'"),
        ("transport-null", "checker_rejection", "failure", "Assert-Transport $null 'BerylWorldSaveEligibility'"),
        ("loaded-valid", "return", None, "Assert-LoadedProjects ([pscustomobject]@{'Loaded Projects'=@('ArmaReforger',$ProjectId)})"),
        ("loaded-missing-owned", "checker_rejection", "stale_input", "Assert-LoadedProjects ([pscustomobject]@{'Loaded Projects'=@('ArmaReforger')})"),
        ("loaded-scalar", "checker_rejection", "stale_input", "Assert-LoadedProjects ([pscustomobject]@{'Loaded Projects'=$ProjectId})"),
        ("loaded-wrong-member-type", "checker_rejection", "failure", "Assert-LoadedProjects ([pscustomobject]@{'Loaded Projects'=@($ProjectId,1)})"),
        ("loaded-extra", "checker_rejection", "failure", "Assert-LoadedProjects ([pscustomobject]@{'Loaded Projects'=@($ProjectId);extra=1})"),
    ]
    ids = [case[0] for case in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate predeclared eligibility checker identity")
    return tuple(cases)


HEADER = r'''param([string]$Source,[string]$ExpectedSourceHash,[string]$Result)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$expectedCaseIds=__EXPECTED__
$names=__NAMES__
$bools=__BOOLS__
$Token='a'*64
$ProjectId='BerylWorldSaveEligibilityProbe'
$canonicalProject='C:/fixture'
$canonicalOutput='C:/fixture/engine-authored/BerylEngineAuthored.ent'
$record=@{status='failure';failure=$null;cleanup_errors=@();evidence_errors=@()}
$mockFile=$false;$mockParent=$false;$mockLink=$false
$cases=[Collections.Generic.List[object]]::new()
$lastReceiptHash=$null
$receipt=[ordered]@{schema_version=1;operation='world-save.checkers.inert';status='running';source=$Source;source_sha256=$ExpectedSourceHash;
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
 $canonicalProject='C:/fixture';$canonicalOutput='C:/fixture/engine-authored/BerylEngineAuthored.ent'
 $mockFile=$false;$mockParent=$false;$mockLink=$false
 $case=[ordered]@{id=$Id;status='failure';expected=$Expected;actual='return';expected_status=$ExpectedStatus;actual_status=$null;original_exception=$null}
 try {&$Action;if($Expected -ceq 'return'){$case.status='success'}} catch {
  $case.actual='exception';$case.actual_status=$record.status;$case.original_exception=Exception-Detail $_
  if($Expected -ceq 'checker_rejection' -and $_.Exception -is [InvalidOperationException] -and $record.status -ceq $ExpectedStatus){$case.status='success';$case.actual='checker_rejection'}
 }
 $cases.Add($case);Save-Receipt
}
function Base {
 return [pscustomobject]@{token=$Token;action='observe';status='eligible';failure='';output_path=$canonicalOutput;wb_world_path='';game_world_path='';
 game_present=$true;in_play_mode=$false;module_present=$true;wb_api_present=$true;wb_world_present=$true;wb_edit_mode=$true;wb_game_mode=$false;
 game_editor_present=$true;game_api_present=$true;game_world_present=$true;api_same=$true;world_same=$true}
}
function Reply {
 return [pscustomobject]@{Ok=$true;Function='BerylWorldSaveEligibility';ErrorCode='Ok';Response=(Base);Raw='{}'}
}
# These mocks exercise only the path admission function. No actual filesystem
# inventory, directory creation, process ownership or process stop is requested.
function Test-Path([string]$LiteralPath) {
 if([StringComparer]::OrdinalIgnoreCase.Equals((Normal-Path $LiteralPath),(Normal-Path $canonicalOutput))){return $mockFile}
 if([StringComparer]::OrdinalIgnoreCase.Equals((Normal-Path $LiteralPath),(Normal-Path ([IO.Path]::GetDirectoryName($canonicalOutput))))){return $mockParent}
 throw 'Unexpected mocked path query'
}
function Get-Item([string]$LiteralPath) {
 return [pscustomobject]@{PSIsContainer=$true;Attributes=$(if($mockLink){[IO.FileAttributes]::ReparsePoint}else{[IO.FileAttributes]::Directory})}
}
try {
 Save-Receipt
 if($expectedCaseIds.Count -ne __COUNT__ -or @($expectedCaseIds|Select-Object -Unique).Count -ne __COUNT__){throw 'Invalid expected fixture identities'}
 $sourceBytes=[IO.File]::ReadAllBytes($Source)
 if([Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($sourceBytes)).ToLowerInvariant() -cne $ExpectedSourceHash){throw 'Retained source identity differs'}
 $sourceText=[Text.UTF8Encoding]::new($false,$true).GetString($sourceBytes)
 $tokens=$null;$errors=$null
 $ast=[Management.Automation.Language.Parser]::ParseInput($sourceText,[ref]$tokens,[ref]$errors)
 if($errors.Count){throw 'World-save adapter PowerShell parse error'}
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
if($receipt.status -cne 'success'){Write-Error 'Pure world-save checker failure; inspect original_exception';exit 1}
'''


def ps_array(values):
    return "@(" + ",".join("'" + value + "'" for value in values) + ")"


def fixture_script(cases):
    actions = []
    for case_id, expected, status, action in cases:
        status_arg = "$null" if status is None else "'" + status + "'"
        actions.append(f" Case '{case_id}' '{expected}' {status_arg} {{{action}}}")
    return HEADER.replace("__COUNT__", str(len(cases))).replace("__EXPECTED__", ps_array([case[0] for case in cases])).replace("__NAMES__", ps_array(NAMES)).replace(
        "__BOOLS__", ps_array(BOOLS)).replace("__CASES__", "\n".join(actions))


def utility_module():
    spec = importlib.util.spec_from_file_location("world-save_checker_host_bounds", UTILITY)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def validate_result(value, cases, source, source_hash):
    ids = [case[0] for case in cases]
    if type(value) is not dict or type(value.get("schema_version")) is not int or value["schema_version"] != 1:
        raise ValueError("Malformed pure checker receipt")
    if value.get("operation") != "world-save.checkers.inert" or value.get("status") != "success" or value.get("failure") is not None:
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
    return {"schema_version": 1, "operation": "world-save.checkers.inert", "status": "success", "failure": None,
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
              ("wrong-count", lambda v: v.update(passed=96)),
              ("missing-exception", lambda v: v["cases"][rejection].update(original_exception=None)),
              ("wrong-status", lambda v: v["cases"][rejection].update(actual_status="unavailable")),
              ("generic-exception", lambda v: v["cases"][rejection]["original_exception"].update(type="System.Exception")),
              ("false-scope", lambda v: v.update(engine_execution="executed")),
              ("failure-retained", lambda v: v.update(failure={"message": "failed"})),
              ("unexpected-field", lambda v: v["cases"][0].update(extra=True))]
    results = []
    fixture = fixture_script(cases)
    if ("$expected=" in fixture or "$expectedCaseIds=" not in fixture or "\f" in fixture or
            ".Replace([char]47,[char]92)" not in fixture or "('C:'+ [char]92+'fixture')" not in fixture):
        raise ValueError("Generated fixture shadows its registry or corrupts path literals")
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
    work = args.output_root.absolute() / ("world-save-checkers-" + uuid.uuid4().hex)
    work.mkdir()
    journal = bounded.Journal(work / "outer")
    source, script, pure_receipt = work / "world-save-source.ps1", work / "checks.ps1", work / "pure-checks.json"
    record = {"schema_version": 1, "operation": "world-save.checkers.driver", "status": "running", "phase": "preparing",
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
                         "-ExpectedSourceHash", record["source"]["sha256"], "-Result", str(pure_receipt)]
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
            record.update(status="success", verification=f"{len(cases)} pure world-save/profile checker cases verified", host_execution="executed_complete")
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
