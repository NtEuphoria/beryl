#!/usr/bin/env python3
"""Prepare, or explicitly execute, pure startup-observer checker fixtures.

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
SOURCE = ROOT / "scripts" / "workbench-startup-engine.ps1"
UTILITY = ROOT / "scripts" / "verify-host-readiness.py"
NAMES = ["Throw-Outcome", "Normal-Path", "Required-Field", "Assert-Text",
         "Normalize-Bool", "Assert-Names", "Check-Response", "Stage-Ready",
         "Select-OpeningProfile", "Assert-Transport", "Assert-Parameters",
         "Check-NativeOpen", "Assert-NativeOpened", "Assert-LoadedProjects"]
STRINGS = ["token", "action", "status", "failure", "mechanism", "current_project", "addon_world_path",
           "resource_name", "resource_path", "resource_absolute_path", "world_path", "world_absolute_path"]
BOOLS = ["addon_world_resolved", "resource_name_resolved", "module_present", "api_present", "world_path_resolved",
         "world_matches", "edit_mode", "game_mode", "in_play_mode", "world_present"]


def case_registry():
    """Fixed trusted actions; identities/outcomes exist before any execution."""
    cases = [
        ("decode-json-bools", "return", None,
         "$v=Base;$d=Check-Response $v;if($d.codec.numeric_boolean_fields.Count -ne 0 -or $d.response.edit_mode -isnot [bool]){throw 'JSON bool codec mismatch'}"),
        ("decode-native-bool01", "return", None,
         "$v=Base;foreach($name in $bools){$v.$name=[int]$v.$name};$d=Check-Response $v;if(($d.codec.numeric_boolean_fields -join '|') -cne ($bools -join '|')){throw 'Numeric codec ordering mismatch'}"),
        ("decode-raw-unchanged", "return", None,
         "$v=Base;foreach($name in $bools){$v.$name=[int]$v.$name};$before=$v|ConvertTo-Json -Depth 10 -Compress;$null=Check-Response $v;if(($v|ConvertTo-Json -Depth 10 -Compress) -cne $before){throw 'Decoder modified raw fields'}"),
        ("stage-ready-exact", "return", None,
         "if(-not (Stage-Ready (Base))){throw 'Exact ready response rejected'}"),
        ("stage-ready-slashes", "return", None,
         "$v=Base;foreach($name in @('addon_world_path','resource_absolute_path','world_absolute_path')){$v.$name=$v.$name.Replace([char]47,[char]92)};if(-not(Stage-Ready $v)){throw 'Slash normalization differs'}"),
        ("stage-pending-module", "return", None,
         "$v=Base;$v.status='pending';$v.module_present=$false;$v.api_present=$false;$v.world_path='';$v.world_absolute_path='';$v.world_path_resolved=$false;$v.world_matches=$false;$v.world_present=$false;$v.edit_mode=$false;if(Stage-Ready $v){throw 'Missing module promoted'}"),
        ("stage-base-project-informational", "return", None,
         "$v=Base;$v.current_project='./addons/data/ArmaReforger.gproj';if(-not(Stage-Ready $v)){throw 'Base project was treated as addon identity'}"),
        ("normal-path-slashes", "return", None,
         "if((Normal-Path 'C:/fixture/') -cne ('C:'+ [char]92+'fixture')){throw 'Path normalization differs'}"),
    ]
    for field in STRINGS + BOOLS:
        cases.append(("missing-" + field.replace("_", "-"), "checker_rejection", "failure",
                      f"$v=Base;$v.PSObject.Properties.Remove('{field}');$null=Check-Response $v"))
    for field in BOOLS:
        for kind, expression in (("two", "2"), ("string", "'1'"), ("double", "[double]1")):
            cases.append(("bool-" + field.replace("_", "-") + "-" + kind, "checker_rejection", "failure",
                          f"$v=Base;$v.{field}={expression};$null=Check-Response $v"))
    for field in STRINGS:
        cases.append(("text-" + field.replace("_", "-") + "-null", "checker_rejection", "failure",
                      f"$v=Base;$v.{field}=$null;$null=Check-Response $v"))
    cases.extend([
        ("unknown-field", "checker_rejection", "failure", "$v=Base;$v|Add-Member -NotePropertyName extra -NotePropertyValue 1;$null=Check-Response $v"),
        ("text-oversize", "checker_rejection", "failure", "$v=Base;$v.world_path='x'*2049;$null=Check-Response $v"),
        ("text-nul", "checker_rejection", "failure", "$v=Base;$v.world_path='x'+[char]0;$null=Check-Response $v"),
        ("stale-token", "checker_rejection", "stale_input", "$v=Base;$v.token='b'*64;$null=Check-Response $v"),
        ("stale-action", "checker_rejection", "stale_input", "$v=Base;$v.action='load';$null=Check-Response $v"),
        ("stale-mechanism", "checker_rejection", "stale_input", "$v=Base;$v.mechanism='deferred';$null=Check-Response $v"),
        ("unknown-status", "checker_rejection", "failure", "$v=Base;$v.status='complete';$null=Check-Response $v"),
    ])
    stage_cases = [
        ("native-unavailable", "unavailable", "$v.status='unavailable';$v.failure='fixture unavailable'"),
        ("native-failure", "failure", "$v.status='failure';$v.failure='fixture failure'"),
        ("addon-foreign", "stale_input", "$v.addon_world_path='C:/foreign/world.ent'"),
        ("resource-name-foreign", "stale_input", "$v.resource_name='{0000000000000000}worlds/BerylCallbackProbe.ent'"),
        ("resource-path-foreign", "stale_input", "$v.resource_absolute_path='C:/foreign/world.ent'"),
        ("world-foreign", "unavailable", "$v.world_absolute_path='C:/foreign/world.ent'"),
        ("world-unresolved", "unavailable", "$v.world_path_resolved=$false"),
        ("game-mode", "unavailable", "$v.game_mode=$true"),
        ("in-play", "unavailable", "$v.in_play_mode=$true"),
        ("module-absent", "stale_input", "$v.module_present=$false"),
        ("api-absent", "stale_input", "$v.api_present=$false"),
        ("edit-absent", "stale_input", "$v.edit_mode=$false"),
        ("world-absent", "stale_input", "$v.world_present=$false"),
        ("addon-unresolved", "stale_input", "$v.addon_world_resolved=$false"),
        ("resource-unresolved", "stale_input", "$v.resource_name_resolved=$false"),
        ("world-empty", "stale_input", "$v.world_path=''"),
        ("resource-empty", "stale_input", "$v.resource_path=''"),
        ("pending-foreign-addon", "stale_input", "$v.status='pending';$v.addon_world_path='C:/foreign/world.ent'"),
        ("ready-failure-evidence", "failure", "$v.failure='fixture failure evidence'"),
        ("pending-failure-evidence", "failure", "$v.status='pending';$v.failure='fixture failure evidence'"),
        ("pending-addon-unresolved", "stale_input", "$v.status='pending';$v.addon_world_resolved=$false"),
        ("pending-resource-unresolved", "stale_input", "$v.status='pending';$v.resource_name_resolved=$false"),
    ]
    for name, status, mutation in stage_cases:
        cases.append(("stage-" + name, "checker_rejection", status, "$v=Base;" + mutation + ";$null=Stage-Ready $v"))
    cases.extend([
        ("profile-startup-fixed-vector", "return", None,
         "$p=Select-OpeningProfile 'startup-cli' 'C:/fixture';if($p.mechanism -cne 'startup_cli' -or $p.arguments.Count -ne 8 -or $p.arguments[4] -cne '-wbmodule=WorldEditor' -or $p.arguments[7] -cne 'worlds/BerylCallbackProbe.ent'){throw 'Startup vector changed'}"),
        ("profile-native-fixed-vector", "return", None,
         "$p=Select-OpeningProfile 'netapi-resource' 'C:/fixture';if($p.mechanism -cne 'native_netapi' -or $p.arguments.Count -ne 4 -or $p.arguments[0] -cne '-gproj' -or $p.arguments[2] -cne '-noOpenLastResource' -or $p.arguments[3] -cne '-scriptAuthorizeAll'){throw 'Native vector changed'}"),
        ("profile-unknown", "checker_rejection", "failure", "$null=Select-OpeningProfile 'fallback' 'C:/fixture'"),
        ("profile-uppercase", "checker_rejection", "failure", "$null=Select-OpeningProfile 'NETAPI-RESOURCE' 'C:/fixture'"),
        ("native-open-json-true", "return", None,
         "$d=Check-NativeOpen ([pscustomobject]@{Opened=$true});Assert-NativeOpened $d.response;if($d.codec.numeric_boolean_fields.Count -ne 0){throw 'JSON native codec changed'}"),
        ("native-open-bool01-true", "return", None,
         "$d=Check-NativeOpen ([pscustomobject]@{Opened=1});Assert-NativeOpened $d.response;if(($d.codec.numeric_boolean_fields -join '|') -cne 'Opened'){throw 'Native bool01 codec changed'}"),
        ("native-open-false-retained", "return", None,
         "$d=Check-NativeOpen ([pscustomobject]@{Opened=0});if($d.response.Opened -isnot [bool] -or $d.response.Opened -or ($d.codec.numeric_boolean_fields -join '|') -cne 'Opened'){throw 'Refusal was promoted or lost'}"),
        ("native-open-false-rejected", "checker_rejection", "unavailable",
         "$d=Check-NativeOpen ([pscustomobject]@{Opened=$false});Assert-NativeOpened $d.response"),
        ("native-open-missing", "checker_rejection", "failure", "$null=Check-NativeOpen ([pscustomobject]@{})"),
        ("native-open-two", "checker_rejection", "failure", "$null=Check-NativeOpen ([pscustomobject]@{Opened=2})"),
        ("native-open-string", "checker_rejection", "failure", "$null=Check-NativeOpen ([pscustomobject]@{Opened='true'})"),
        ("native-open-double", "checker_rejection", "failure", "$null=Check-NativeOpen ([pscustomobject]@{Opened=[double]1})"),
        ("native-open-unknown-field", "checker_rejection", "failure", "$null=Check-NativeOpen ([pscustomobject]@{Opened=$true;extra=1})"),
        ("native-transport-failure", "checker_rejection", "failure", "$r=Native-Reply;$r.Ok=$false;Assert-Transport $r 'OpenResource'"),
        ("native-transport-wrong-function", "checker_rejection", "failure", "$r=Native-Reply;$r.Function='BerylStartupReadiness';Assert-Transport $r 'OpenResource'"),
        ("native-transport-wrong-error", "checker_rejection", "failure", "$r=Native-Reply;$r.ErrorCode='failure';Assert-Transport $r 'OpenResource'"),
        ("native-foreign-resource-parameters", "checker_rejection", "stale_input",
         "$record.mechanism='native_netapi';Assert-Parameters 'OpenResource' @{ResourceName='C:/foreign/world.ent'}"),
        ("native-disabled-default-profile", "checker_rejection", "failure", "Assert-Parameters 'OpenResource' @{ResourceName=$canonicalWorld}"),
        ("loaded-project-missing", "checker_rejection", "stale_input", "Assert-LoadedProjects ([pscustomobject]@{'Loaded Projects'=@('ArmaReforger')})"),
        ("loaded-project-array-required", "checker_rejection", "stale_input", "Assert-LoadedProjects ([pscustomobject]@{'Loaded Projects'=$ProjectId})"),
        ("loaded-project-unknown-field", "checker_rejection", "failure", "Assert-LoadedProjects ([pscustomobject]@{'Loaded Projects'=@($ProjectId);extra=1})"),
        ("native-observer-selected", "return", None,
         "$record.mechanism='native_netapi';$v=Base;$v.mechanism='native_netapi';$null=Check-Response $v"),
        ("native-observer-wrong-profile", "checker_rejection", "stale_input",
         "$record.mechanism='native_netapi';$null=Check-Response (Base)"),
        ("native-resource-key-case", "checker_rejection", "stale_input",
         "$record.mechanism='native_netapi';Assert-Parameters 'OpenResource' @{resourcename=$canonicalWorld}"),
        ("builtin-unexpected-parameters", "checker_rejection", "failure", "Assert-Parameters 'IsWorkbenchRunning' @{unexpected=1}"),
        ("observer-stale-parameters", "checker_rejection", "stale_input", "Assert-Parameters 'BerylStartupReadiness' @{token='b'*64;action='observe'}"),
        ("unregistered-rpc-parameters", "checker_rejection", "failure", "Assert-Parameters 'Save' @{}"),
        ("profile-module-native-fixed-vector", "return", None,
         "$p=Select-OpeningProfile 'module-netapi-resource' 'C:/fixture';$expectedArguments=@('-gproj','C:/fixture/addon.gproj','-noOpenLastResource','-scriptAuthorizeAll','-wbmodule=WorldEditor','-run');if($p.mechanism -cne 'module_native_netapi' -or $p.arguments.Count -ne 6){throw 'Module-native profile identity changed'};for($index=0;$index -lt 6;$index++){if($index -eq 1){if((Normal-Path $p.arguments[$index]) -cne (Normal-Path $expectedArguments[$index])){throw 'Module-native project path changed'}}elseif($p.arguments[$index] -cne $expectedArguments[$index]){throw 'Module-native argument changed'}}"),
        ("module-observer-selected", "return", None,
         "$record.mechanism='module_native_netapi';$v=Base;$v.mechanism='module_native_netapi';$null=Check-Response $v"),
        ("module-observer-reject-native", "checker_rejection", "stale_input",
         "$record.mechanism='module_native_netapi';$v=Base;$v.mechanism='native_netapi';$null=Check-Response $v"),
        ("module-observer-reject-startup", "checker_rejection", "stale_input",
         "$record.mechanism='module_native_netapi';$null=Check-Response (Base)"),
        ("module-native-parameters", "return", None,
         "$record.mechanism='module_native_netapi';Assert-Parameters 'OpenResource' @{ResourceName=$canonicalWorld}"),
        ("module-native-foreign-resource", "checker_rejection", "stale_input",
         "$record.mechanism='module_native_netapi';Assert-Parameters 'OpenResource' @{ResourceName='C:/foreign/world.ent'}"),
        ("native-observer-reject-module", "checker_rejection", "stale_input",
         "$record.mechanism='native_netapi';$v=Base;$v.mechanism='module_native_netapi';$null=Check-Response $v"),
        ("startup-observer-reject-module", "checker_rejection", "stale_input",
         "$v=Base;$v.mechanism='module_native_netapi';$null=Check-Response $v"),
        ("profile-module-registered-fixed-vector", "return", None,
         "$p=Select-OpeningProfile 'module-netapi-registered' 'C:/fixture';$ordinary=Select-OpeningProfile 'module-netapi-resource' 'C:/fixture';if($p.mechanism -cne 'module_registered_netapi' -or $p.arguments.Count -ne 6 -or ($p.arguments -join '|') -cne ($ordinary.arguments -join '|') -or $p.arguments -ccontains '-load'){throw 'Registered profile changed the six-argument no-load vector'}"),
        ("registered-observer-selected", "return", None,
         "$record.mechanism='module_registered_netapi';$v=Base;$v.mechanism='module_registered_netapi';$null=Check-Response $v"),
        ("registered-native-guid-parameters", "return", None,
         "$record.mechanism='module_registered_netapi';Assert-Parameters 'OpenResource' @{ResourceName='{BCCBA11B20261008}worlds/BerylCallbackProbe.ent'}"),
        ("registered-reject-absolute-parameters", "checker_rejection", "stale_input",
         "$record.mechanism='module_registered_netapi';Assert-Parameters 'OpenResource' @{ResourceName=$canonicalWorld}"),
        ("registered-reject-wrong-guid", "checker_rejection", "stale_input",
         "$record.mechanism='module_registered_netapi';Assert-Parameters 'OpenResource' @{ResourceName='{0000000000000000}worlds/BerylCallbackProbe.ent'}"),
        ("registered-reject-relative-parameters", "checker_rejection", "stale_input",
         "$record.mechanism='module_registered_netapi';Assert-Parameters 'OpenResource' @{ResourceName='worlds/BerylCallbackProbe.ent'}"),
        ("module-absolute-reject-registered-guid", "checker_rejection", "stale_input",
         "$record.mechanism='module_native_netapi';Assert-Parameters 'OpenResource' @{ResourceName='{BCCBA11B20261008}worlds/BerylCallbackProbe.ent'}"),
        ("native-absolute-reject-registered-guid", "checker_rejection", "stale_input",
         "$record.mechanism='native_netapi';Assert-Parameters 'OpenResource' @{ResourceName='{BCCBA11B20261008}worlds/BerylCallbackProbe.ent'}"),
        ("startup-reject-registered-guid", "checker_rejection", "failure",
         "Assert-Parameters 'OpenResource' @{ResourceName='{BCCBA11B20261008}worlds/BerylCallbackProbe.ent'}"),
        ("registered-observer-reject-module", "checker_rejection", "stale_input",
         "$record.mechanism='module_registered_netapi';$v=Base;$v.mechanism='module_native_netapi';$null=Check-Response $v"),
        ("module-observer-reject-registered", "checker_rejection", "stale_input",
         "$record.mechanism='module_native_netapi';$v=Base;$v.mechanism='module_registered_netapi';$null=Check-Response $v"),
        ("native-observer-reject-registered", "checker_rejection", "stale_input",
         "$record.mechanism='native_netapi';$v=Base;$v.mechanism='module_registered_netapi';$null=Check-Response $v"),
    ])
    if len(cases) != 148 or len({case[0] for case in cases}) != len(cases):
        raise ValueError("Invalid predeclared 148-case registry")
    return tuple(cases)


HEADER = r'''param([string]$Source,[string]$ExpectedSourceHash,[string]$Result)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$expectedCaseIds=__EXPECTED__
$names=__NAMES__
$bools=__BOOLS__
$Token='a'*64
$ProjectId='BerylStartupReadinessProbe'
$canonicalWorld='C:/fixture/worlds/BerylCallbackProbe.ent'
$record=@{status='failure';mechanism='startup_cli'}
$cases=[Collections.Generic.List[object]]::new()
$lastReceiptHash=$null
$receipt=[ordered]@{schema_version=1;operation='startup.checkers.inert';status='running';source=$Source;source_sha256=$ExpectedSourceHash;
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
 $record.status='failure';$record.mechanism='startup_cli'
 $case=[ordered]@{id=$Id;status='failure';expected=$Expected;actual='return';expected_status=$ExpectedStatus;actual_status=$null;original_exception=$null}
 try {&$Action;if($Expected -ceq 'return'){$case.status='success'}} catch {
  $case.actual='exception';$case.actual_status=$record.status;$case.original_exception=Exception-Detail $_
  if($Expected -ceq 'checker_rejection' -and $_.Exception -is [InvalidOperationException] -and $record.status -ceq $ExpectedStatus){$case.status='success';$case.actual='checker_rejection'}
 }
 $cases.Add($case);Save-Receipt
}
function Base {
 return [pscustomobject]@{token=$Token;action='observe';status='ready';failure='';mechanism='startup_cli';current_project='./addons/data/ArmaReforger.gproj';
 addon_world_path=$canonicalWorld;resource_name='{BCCBA11B20261008}worlds/BerylCallbackProbe.ent';resource_path='worlds/BerylCallbackProbe.ent';
 resource_absolute_path=$canonicalWorld;world_path='$BerylComponentCallbackProbe:worlds/BerylCallbackProbe.ent';world_absolute_path=$canonicalWorld;
 addon_world_resolved=$true;resource_name_resolved=$true;module_present=$true;api_present=$true;world_path_resolved=$true;world_matches=$true;
 edit_mode=$true;game_mode=$false;in_play_mode=$false;world_present=$true}
}
function Native-Reply {
 return [pscustomobject]@{Ok=$true;Function='OpenResource';ErrorCode='Ok';Response=[pscustomobject]@{Opened=$true};Raw='{"Opened":true}'}
}
try {
 Save-Receipt
 if($expectedCaseIds.Count -ne __COUNT__ -or @($expectedCaseIds|Select-Object -Unique).Count -ne __COUNT__){throw 'Invalid expected fixture identities'}
 $sourceBytes=[IO.File]::ReadAllBytes($Source)
 if([Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($sourceBytes)).ToLowerInvariant() -cne $ExpectedSourceHash){throw 'Retained source identity differs'}
 $sourceText=[Text.UTF8Encoding]::new($false,$true).GetString($sourceBytes)
 $tokens=$null;$errors=$null
 $ast=[Management.Automation.Language.Parser]::ParseInput($sourceText,[ref]$tokens,[ref]$errors)
 if($errors.Count){throw 'Startup adapter PowerShell parse error'}
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
if($receipt.status -cne 'success'){Write-Error 'Pure startup checker failure; inspect original_exception';exit 1}
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
    spec = importlib.util.spec_from_file_location("startup_checker_host_bounds", UTILITY)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def validate_result(value, cases, source, source_hash):
    ids = [case[0] for case in cases]
    if type(value) is not dict or type(value.get("schema_version")) is not int or value["schema_version"] != 1:
        raise ValueError("Malformed pure checker receipt")
    if value.get("operation") != "startup.checkers.inert" or value.get("status") != "success" or value.get("failure") is not None:
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
    return {"schema_version": 1, "operation": "startup.checkers.inert", "status": "success", "failure": None,
            "source": str(source), "source_sha256": source_hash, "function_names": NAMES,
            "expected_case_ids": [case[0] for case in cases], "completed_case_ids": [case[0] for case in cases],
            "complete_expected_case_set": True, "expected_cases": len(cases), "case_count": len(cases), "passed": len(cases), "failed": 0,
            "cases": rows, **{field: "not_run" for field in ("compiler_execution", "engine_execution", "adapter_top_level", "actual_process_stop", "native_listener_inventory")}}


def self_test(cases, source_hash):
    source = Path("source-only-synthetic.ps1")
    sample = synthetic_result(cases, source, source_hash)
    faults = [("schema-bool", lambda v: v.update(schema_version=True)),
              ("missing-case", lambda v: v["cases"].pop()),
              ("wrong-function", lambda v: v["function_names"].append("Invoke-Call")),
              ("missing-completion", lambda v: v["completed_case_ids"].pop()),
              ("duplicate-completion", lambda v: v["completed_case_ids"].append(v["completed_case_ids"][0])),
              ("wrong-source", lambda v: v.update(source_sha256="0" * 64)),
              ("wrong-count", lambda v: v.update(passed=96)),
              ("missing-exception", lambda v: v["cases"][8].update(original_exception=None)),
              ("wrong-status", lambda v: v["cases"][8].update(actual_status="unavailable")),
              ("generic-exception", lambda v: v["cases"][8]["original_exception"].update(type="System.Exception")),
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
    work = args.output_root.absolute() / ("startup-checkers-" + uuid.uuid4().hex)
    work.mkdir()
    journal = bounded.Journal(work / "outer")
    source, script, pure_receipt = work / "startup-source.ps1", work / "checks.ps1", work / "pure-checks.json"
    record = {"schema_version": 1, "operation": "startup.checkers.driver", "status": "running", "phase": "preparing",
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
            record.update(status="success", verification=f"{len(cases)} pure startup/profile checker cases verified", host_execution="executed_complete")
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
