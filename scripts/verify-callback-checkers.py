#!/usr/bin/env python3
"""Prepare, or explicitly run, 89 pure callback checker fixtures.

No dependency on historical build scripts. The PowerShell program parses a
retained exact source snapshot and loads only eight named function definitions.
It never invokes adapter entry, engine startup, or process controls.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys
import uuid

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "scripts" / "component-callback-engine.ps1"
UTILITY = ROOT / "scripts" / "verify-host-readiness.py"
NAMES = ["Normal-Path", "Required-Field", "Assert-Int", "Throw-Outcome", "Assert-LoadProgress",
         "Check-Response", "Assert-PinnedWorld", "Stage-Ready"]
PASS_IDS = {
    "json-bools", "native-bool01", "raw-unchanged", "pending-absent", "unavailable-absent",
    "pin-exact", "stage-pending-no-pin", "pin-resource-path-alternate-spelling",
    "stage-pending-open-refused", "stage-ready-open-exact", "load-cold",
    "load-submitted-before-entry", "load-entered-before-submit", "load-resumed-prefix",
    "load-returned-refused", "progress-delayed-entry", "progress-immediate-entry", "stage-pending-load-resumed",
}
STALE_IDS = {
    "pin-resource-name", "pin-resource-path", "pin-resource-unresolved", "pin-module-absent", "pin-api-absent",
    "stage-ready-module-absent", "stage-ready-api-absent", "stage-ready-resource-mismatch",
    "pin-resource-path-empty", "pin-open-not-requested", "pin-open-not-accepted",
    "stage-ready-open-not-requested", "stage-ready-open-not-accepted", "progress-reset-all",
    "progress-reset-accepted", "progress-stale-token", "pin-load-cold", "stage-ready-load-not-returned",
    "stage-ready-load-refused", "stage-ready-load-not-requested", "stage-ready-load-not-submitted",
    "stage-ready-load-not-entered", "stage-ready-load-not-resumed",
}

SCRIPT = r'''param([string]$Source,[string]$ExpectedSourceHash,[string]$Result)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$expected=@('json-bools','native-bool01','raw-unchanged','pending-absent','unavailable-absent',
 'missing-resource-name','resource-name-type','resource-path-null','missing-module','resource-bool-two','module-bool-string','api-bool-double','unknown-field',
 'pin-exact','pin-resource-name','pin-resource-path','pin-resource-unresolved','pin-module-absent','pin-api-absent',
 'stage-pending-no-pin','stage-ready-module-absent','stage-ready-api-absent','stage-ready-resource-mismatch',
 'missing-resource-path','resource-path-type','resource-path-oversize','pin-resource-path-empty','pin-resource-path-alternate-spelling',
 'missing-open-requested','missing-open-accepted','open-requested-string','open-requested-double','open-requested-two',
 'open-accepted-string','open-accepted-double','open-accepted-two','pin-open-not-requested','pin-open-not-accepted',
 'stage-ready-open-not-requested','stage-ready-open-not-accepted','stage-pending-open-refused','stage-ready-open-exact',
 'missing-load-requested','missing-load-submitted','missing-load-entered','missing-load-resumed','missing-load-returned','missing-load-accepted',
 'load-requested-bool','load-submitted-bool','load-entered-bool','load-resumed-bool','load-returned-bool',
 'load-counter-double','load-counter-string','load-counter-two','load-accepted-string','load-accepted-double','load-accepted-two',
 'load-submitted-without-request','load-entered-without-request','load-resumed-without-entry','load-resumed-without-submit','load-returned-without-resume','load-accepted-before-return',
 'load-cold','load-submitted-before-entry','load-entered-before-submit','load-resumed-prefix','load-returned-refused',
 'progress-delayed-entry','progress-immediate-entry','progress-reset-all','progress-reset-accepted','progress-stale-token',
 'pin-load-cold','stage-ready-load-not-returned','stage-ready-load-refused','stage-pending-load-resumed',
 'ready-load-requested','ready-load-submitted','ready-load-entered','ready-load-resumed','ready-load-returned','ready-load-accepted',
 'stage-ready-load-not-requested','stage-ready-load-not-submitted','stage-ready-load-not-entered','stage-ready-load-not-resumed')
$names=@('Normal-Path','Required-Field','Assert-Int','Throw-Outcome','Assert-LoadProgress','Check-Response','Assert-PinnedWorld','Stage-Ready')
$cases=[Collections.Generic.List[object]]::new()
$record=@{status='failure'}
$lastReceiptHash=$null
$receipt=[ordered]@{schema_version=1;operation='callback.checkers.inert';status='running';source=$Source;source_sha256=$ExpectedSourceHash;
 scope='Only eight AST-extracted checker functions; no adapter entry, startup, cleanup, compiler, engine or process controls';
 function_names=$names;expected_case_ids=$expected;expected_cases=89;cases=@();completed_case_ids=@();complete_expected_case_set=$false;
 compiler_execution='not_run';engine_execution='not_run';adapter_top_level='not_run';actual_process_stop='not_run';failure=$null}
function Save-Receipt {
 $receipt.cases=@($cases.ToArray());$receipt.completed_case_ids=@($cases | ForEach-Object {$_.id});$receipt.case_count=$cases.Count
 $receipt.complete_expected_case_set=(($receipt.completed_case_ids -join '|') -ceq ($expected -join '|'))
 if ([IO.File]::Exists($Result)) {
  if ($null -eq $script:lastReceiptHash -or (Get-FileHash -LiteralPath $Result -Algorithm SHA256).Hash.ToLowerInvariant() -cne $script:lastReceiptHash) { throw 'Checker receipt changed by another writer' }
 }
 $tmp=$Result+'.'+[Guid]::NewGuid().ToString('N')+'.tmp'
 $bytes=[Text.UTF8Encoding]::new($false).GetBytes(($receipt|ConvertTo-Json -Depth 20)+[Environment]::NewLine)
 $stream=[IO.File]::Open($tmp,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
 try {$stream.Write($bytes,0,$bytes.Length);$stream.Flush($true)} finally {$stream.Dispose()}
 $hash=[Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($bytes)).ToLowerInvariant()
 if ((Get-FileHash -LiteralPath $tmp -Algorithm SHA256).Hash.ToLowerInvariant() -cne $hash) { throw 'Checker receipt write mismatch' }
 [IO.File]::Move($tmp,$Result,$true)
 if ((Get-FileHash -LiteralPath $Result -Algorithm SHA256).Hash.ToLowerInvariant() -cne $hash) { throw 'Checker receipt atomic readback mismatch' }
 $script:lastReceiptHash=$hash
}
function Exception-Detail([object]$ErrorRecord) {
 return [ordered]@{type=$ErrorRecord.Exception.GetType().FullName;message=$ErrorRecord.Exception.Message;
  fully_qualified_error_id=$ErrorRecord.FullyQualifiedErrorId;position=$ErrorRecord.InvocationInfo.PositionMessage;script_stack=$ErrorRecord.ScriptStackTrace}
}
function Register-Case([object]$Case) {
 if ($Case.id -cnotin $expected -or @($cases|Where-Object {$_.id -ceq $Case.id}).Count) { throw ('Unknown/duplicate case: '+$Case.id) }
 $cases.Add($Case);Save-Receipt
}
function Pass([string]$Id,[scriptblock]$Action) {
 $record.status='failure'
 $case=[ordered]@{id=$Id;status='success';expected='return';actual='return';expected_status=$null;actual_status=$null;original_exception=$null}
 try {& $Action} catch {$case.status='failure';$case.actual='exception';$case.actual_status=$record.status;$case.original_exception=Exception-Detail $_}
 Register-Case $case
}
function Reject([string]$Id,[scriptblock]$Action,[string]$Status='failure') {
 $record.status='failure'
 $case=[ordered]@{id=$Id;status='failure';expected='checker_rejection';actual='return';expected_status=$Status;actual_status=$null;original_exception=$null}
 try {& $Action} catch {
  $case.actual='exception';$case.actual_status=$record.status;$case.original_exception=Exception-Detail $_
  if ($_.Exception -is [InvalidOperationException] -and $record.status -ceq $Status) {$case.status='success';$case.actual='checker_rejection'}
 }
 Register-Case $case
}
function Base {
 return [pscustomobject]@{token=$Token;action='delete';status='complete';failure='';world_path='$BerylComponentCallbackProbe:worlds/BerylCallbackProbe.ent';
 current_project='./addons/data/ArmaReforger.gproj';addon_world_path='C:/fixture/worlds/BerylCallbackProbe.ent';world_absolute_path='C:/fixture/worlds/BerylCallbackProbe.ent';
 resource_name='{BCCBA11B20261008}worlds/BerylCallbackProbe.ent';resource_path='worlds/BerylCallbackProbe.ent';resource_absolute_path='C:/fixture/worlds/BerylCallbackProbe.ent';
 addon_world_resolved=$true;world_path_resolved=$true;world_matches=$true;edit_mode=$false;game_mode=$true;in_play_mode=$true;world_present=$true;
 resource_name_resolved=$true;module_present=$true;api_present=$true;module_open_requested=$true;module_open_accepted=$true;
 load_requested=1;load_submitted=1;load_entered=1;load_resumed=1;load_returned=1;load_accepted=$true;phase=4;executed=1;checks=1;failures=0;event_count=0;checksum=0;caseIds=@();rows=@()}
}
function Absent {
 $value=Base;$value.status='pending';$value.executed=0;$value.checks=0;$value.phase=0
 $value.resource_name='';$value.resource_path='';$value.resource_absolute_path='';$value.resource_name_resolved=$false;$value.module_present=$false;$value.api_present=$false
 $value.module_open_requested=$false;$value.module_open_accepted=$false;$value.load_requested=0;$value.load_submitted=0;$value.load_entered=0;$value.load_resumed=0;$value.load_returned=0;$value.load_accepted=$false
 $value.PSObject.Properties.Remove('caseIds');$value.PSObject.Properties.Remove('rows');return $value
}
function Load-Snapshot([int[]]$Counters,[bool]$Accepted=$false,[string]$Status='pending') {
 $value=Base;$value.status=$Status;$value.load_requested=$Counters[0];$value.load_submitted=$Counters[1];$value.load_entered=$Counters[2];$value.load_resumed=$Counters[3];$value.load_returned=$Counters[4];$value.load_accepted=$Accepted;return $value
}
try {
 Save-Receipt
 if ($expected.Count -ne 89 -or @($expected|Select-Object -Unique).Count -ne 89) {throw 'Invalid expected 89-case registration'}
 $sourceBytes=[IO.File]::ReadAllBytes($Source)
 $sourceHash=[Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($sourceBytes)).ToLowerInvariant()
 if ($sourceHash -cne $ExpectedSourceHash) {throw 'Retained source identity differs'}
 $sourceText=[Text.UTF8Encoding]::new($false,$true).GetString($sourceBytes)
 $tokens=$null;$errors=$null
 $ast=[Management.Automation.Language.Parser]::ParseInput($sourceText,[ref]$tokens,[ref]$errors)
 if ($errors.Count) {throw 'Source PowerShell parse error'}
 foreach($name in $names) {
  $definitions=@($ast.FindAll({param($node) $node -is [Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -ceq $name},$true))
  if ($definitions.Count -ne 1) {throw ('Missing/duplicate pure function '+$name)}
  Invoke-Expression $definitions[0].Extent.Text
 }
 $Token='a'*64;$canonicalWorld='C:\fixture\worlds\BerylCallbackProbe.ent'
 Pass 'json-bools' {$decoded=Check-Response (Base) 'delete';if(-not $decoded.response.module_present -or -not $decoded.response.api_present){throw 'Presence lost'}}
 Pass 'native-bool01' {$value=Base;foreach($name in @('addon_world_resolved','world_path_resolved','world_matches','edit_mode','game_mode','in_play_mode','world_present','resource_name_resolved','module_present','api_present','module_open_requested','module_open_accepted','load_accepted')){$value.$name=[int]$value.$name};$decoded=Check-Response $value 'delete';if($decoded.codec.numeric_boolean_fields.Count -ne 13 -or $decoded.response.module_present -isnot [bool] -or -not $decoded.response.resource_name_resolved){throw 'Native bool codec differs'}}
 Pass 'raw-unchanged' {$value=Base;$before=$value|ConvertTo-Json -Depth 8 -Compress;$null=Check-Response $value 'delete';if(($value|ConvertTo-Json -Depth 8 -Compress)-cne $before){throw 'Raw mutation'}}
 Pass 'pending-absent' {$decoded=Check-Response (Absent) 'delete';if($decoded.response.status -cne 'pending' -or $decoded.response.module_present -or $decoded.response.api_present -or $decoded.response.resource_name_resolved){throw 'False readiness'}}
 Pass 'unavailable-absent' {$value=Absent;$value.status='unavailable';$decoded=Check-Response $value 'delete';if($decoded.response.status -cne 'unavailable' -or $decoded.response.api_present){throw 'Unavailable changed'}}
 Reject 'missing-resource-name' {$value=Base;$value.PSObject.Properties.Remove('resource_name');$null=Check-Response $value 'delete'}
 Reject 'resource-name-type' {$value=Base;$value.resource_name=1;$null=Check-Response $value 'delete'}
 Reject 'resource-path-null' {$value=Base;$value.resource_absolute_path=$null;$null=Check-Response $value 'delete'}
 Reject 'missing-module' {$value=Base;$value.PSObject.Properties.Remove('module_present');$null=Check-Response $value 'delete'}
 Reject 'resource-bool-two' {$value=Base;$value.resource_name_resolved=2;$null=Check-Response $value 'delete'}
 Reject 'module-bool-string' {$value=Base;$value.module_present='1';$null=Check-Response $value 'delete'}
 Reject 'api-bool-double' {$value=Base;$value.api_present=1.0;$null=Check-Response $value 'delete'}
 Reject 'unknown-field' {$value=Base;$value|Add-Member extra 0;$null=Check-Response $value 'delete'}
 Pass 'pin-exact' {Assert-PinnedWorld (Base)}
 Reject 'pin-resource-name' {$value=Base;$value.resource_name='{OTHER}worlds/BerylCallbackProbe.ent';Assert-PinnedWorld $value} 'stale_input'
 Reject 'pin-resource-path' {$value=Base;$value.resource_absolute_path='C:/other.ent';Assert-PinnedWorld $value} 'stale_input'
 Reject 'pin-resource-unresolved' {$value=Base;$value.resource_name_resolved=$false;Assert-PinnedWorld $value} 'stale_input'
 Reject 'pin-module-absent' {$value=Base;$value.module_present=$false;Assert-PinnedWorld $value} 'stale_input'
 Reject 'pin-api-absent' {$value=Base;$value.api_present=$false;Assert-PinnedWorld $value} 'stale_input'
 Pass 'stage-pending-no-pin' {if(Stage-Ready ((Check-Response (Absent) 'delete').response) 'load'){throw 'Pending became ready'}}
 Reject 'stage-ready-module-absent' {$value=Base;$value.status='ready';$value.module_present=$false;$null=Stage-Ready $value 'load'} 'stale_input'
 Reject 'stage-ready-api-absent' {$value=Base;$value.status='ready';$value.api_present=$false;$null=Stage-Ready $value 'load'} 'stale_input'
 Reject 'stage-ready-resource-mismatch' {$value=Base;$value.status='ready';$value.resource_name='{OTHER}worlds/BerylCallbackProbe.ent';$null=Stage-Ready $value 'load'} 'stale_input'
 Reject 'missing-resource-path' {$value=Base;$value.PSObject.Properties.Remove('resource_path');$null=Check-Response $value 'delete'}
 Reject 'resource-path-type' {$value=Base;$value.resource_path=1;$null=Check-Response $value 'delete'}
 Reject 'resource-path-oversize' {$value=Base;$value.resource_path='x'*2049;$null=Check-Response $value 'delete'}
 Reject 'pin-resource-path-empty' {$value=Base;$value.resource_path='';Assert-PinnedWorld $value} 'stale_input'
 Pass 'pin-resource-path-alternate-spelling' {$value=Base;$value.resource_path='$BerylComponentCallbackProbe:worlds/BerylCallbackProbe.ent';Assert-PinnedWorld $value}
 Reject 'missing-open-requested' {$value=Base;$value.PSObject.Properties.Remove('module_open_requested');$null=Check-Response $value 'delete'}
 Reject 'missing-open-accepted' {$value=Base;$value.PSObject.Properties.Remove('module_open_accepted');$null=Check-Response $value 'delete'}
 Reject 'open-requested-string' {$value=Base;$value.module_open_requested='1';$null=Check-Response $value 'delete'}
 Reject 'open-requested-double' {$value=Base;$value.module_open_requested=1.0;$null=Check-Response $value 'delete'}
 Reject 'open-requested-two' {$value=Base;$value.module_open_requested=2;$null=Check-Response $value 'delete'}
 Reject 'open-accepted-string' {$value=Base;$value.module_open_accepted='1';$null=Check-Response $value 'delete'}
 Reject 'open-accepted-double' {$value=Base;$value.module_open_accepted=1.0;$null=Check-Response $value 'delete'}
 Reject 'open-accepted-two' {$value=Base;$value.module_open_accepted=2;$null=Check-Response $value 'delete'}
 Reject 'pin-open-not-requested' {$value=Base;$value.module_open_requested=$false;Assert-PinnedWorld $value} 'stale_input'
 Reject 'pin-open-not-accepted' {$value=Base;$value.module_open_accepted=$false;Assert-PinnedWorld $value} 'stale_input'
 Reject 'stage-ready-open-not-requested' {$value=Base;$value.status='ready';$value.module_open_requested=$false;$null=Stage-Ready $value 'load'} 'stale_input'
 Reject 'stage-ready-open-not-accepted' {$value=Base;$value.status='ready';$value.module_open_accepted=$false;$null=Stage-Ready $value 'load'} 'stale_input'
 Pass 'stage-pending-open-refused' {$value=Base;$value.status='pending';$value.module_open_requested=$true;$value.module_open_accepted=$false;$decoded=Check-Response $value 'delete';if(Stage-Ready $decoded.response 'load'){throw 'Refused pending became ready'};if(-not $decoded.response.module_open_requested -or $decoded.response.module_open_accepted){throw 'Open result changed'}}
 Pass 'stage-ready-open-exact' {$value=Base;$value.status='ready';$value.edit_mode=$true;$value.game_mode=$false;$value.in_play_mode=$false;if(-not(Stage-Ready $value 'load')){throw 'Exact ready rejected'}}
 foreach($name in @('requested','submitted','entered','resumed','returned','accepted')) {Reject ('missing-load-'+$name) {$value=Base;$value.PSObject.Properties.Remove('load_'+$name);$null=Check-Response $value 'delete'}}
 foreach($name in @('requested','submitted','entered','resumed','returned')) {Reject ('load-'+$name+'-bool') {$value=Base;$value.('load_'+$name)=$true;$null=Check-Response $value 'delete'}}
 Reject 'load-counter-double' {$value=Base;$value.load_requested=1.0;$null=Check-Response $value 'delete'}
 Reject 'load-counter-string' {$value=Base;$value.load_requested='1';$null=Check-Response $value 'delete'}
 Reject 'load-counter-two' {$value=Base;$value.load_requested=2;$null=Check-Response $value 'delete'}
 Reject 'load-accepted-string' {$value=Base;$value.load_accepted='1';$null=Check-Response $value 'delete'}
 Reject 'load-accepted-double' {$value=Base;$value.load_accepted=1.0;$null=Check-Response $value 'delete'}
 Reject 'load-accepted-two' {$value=Base;$value.load_accepted=2;$null=Check-Response $value 'delete'}
 Reject 'load-submitted-without-request' {$null=Check-Response (Load-Snapshot @(0,1,0,0,0)) 'delete'}
 Reject 'load-entered-without-request' {$null=Check-Response (Load-Snapshot @(0,0,1,0,0)) 'delete'}
 Reject 'load-resumed-without-entry' {$null=Check-Response (Load-Snapshot @(1,1,0,1,0)) 'delete'}
 Reject 'load-resumed-without-submit' {$null=Check-Response (Load-Snapshot @(1,0,1,1,0)) 'delete'}
 Reject 'load-returned-without-resume' {$null=Check-Response (Load-Snapshot @(1,1,1,0,1)) 'delete'}
 Reject 'load-accepted-before-return' {$null=Check-Response (Load-Snapshot @(1,1,1,1,0) $true) 'delete'}
 foreach($fixture in @(
 @{id='load-cold';counters=@(0,0,0,0,0);status='pending'},@{id='load-submitted-before-entry';counters=@(1,1,0,0,0);status='pending'},
 @{id='load-entered-before-submit';counters=@(1,0,1,0,0);status='pending'},@{id='load-resumed-prefix';counters=@(1,1,1,1,0);status='pending'},
 @{id='load-returned-refused';counters=@(1,1,1,1,1);status='unavailable'})) {Pass $fixture.id {$value=Load-Snapshot $fixture.counters $false $fixture.status;$decoded=Check-Response $value 'delete';if($decoded.response.load_accepted){throw 'Prefix/refusal became accepted'}}}
 Pass 'progress-delayed-entry' {$previous=$null;foreach($snapshot in @((Load-Snapshot @(0,0,0,0,0)),(Load-Snapshot @(1,1,0,0,0)),(Load-Snapshot @(1,1,1,1,0)),(Load-Snapshot @(1,1,1,1,1) $true))){Assert-LoadProgress $snapshot $previous;$previous=$snapshot}}
 Pass 'progress-immediate-entry' {$previous=$null;foreach($snapshot in @((Load-Snapshot @(0,0,0,0,0)),(Load-Snapshot @(1,0,1,0,0)),(Load-Snapshot @(1,1,1,1,0)),(Load-Snapshot @(1,1,1,1,1) $true))){Assert-LoadProgress $snapshot $previous;$previous=$snapshot}}
 Reject 'progress-reset-all' {Assert-LoadProgress (Load-Snapshot @(0,0,0,0,0)) (Load-Snapshot @(1,1,1,1,1) $true)} 'stale_input'
 Reject 'progress-reset-accepted' {Assert-LoadProgress (Load-Snapshot @(1,1,1,1,1)) (Load-Snapshot @(1,1,1,1,1) $true)} 'stale_input'
 Reject 'progress-stale-token' {$value=Load-Snapshot @(1,1,1,1,1) $true;$value.token='b'*64;Assert-LoadProgress $value (Load-Snapshot @(1,1,1,1,1) $true)} 'stale_input'
 Reject 'pin-load-cold' {Assert-PinnedWorld (Load-Snapshot @(0,0,0,0,0))} 'stale_input'
 Reject 'stage-ready-load-not-returned' {$null=Stage-Ready (Load-Snapshot @(1,1,1,1,0) $false 'ready') 'load'} 'stale_input'
 Reject 'stage-ready-load-refused' {$null=Stage-Ready (Load-Snapshot @(1,1,1,1,1) $false 'ready') 'load'} 'stale_input'
 Pass 'stage-pending-load-resumed' {if(Stage-Ready (Load-Snapshot @(1,1,1,1,0)) 'load'){throw 'Incomplete load became ready'}}
 foreach($fixture in @(
 @{id='ready-load-requested';counters=@(0,0,0,0,0)},@{id='ready-load-submitted';counters=@(1,0,1,0,0)},
 @{id='ready-load-entered';counters=@(1,1,0,0,0)},@{id='ready-load-resumed';counters=@(1,1,1,0,0)},
 @{id='ready-load-returned';counters=@(1,1,1,1,0)},@{id='ready-load-accepted';counters=@(1,1,1,1,1)})) {
  Reject $fixture.id {$value=Load-Snapshot $fixture.counters $false 'ready';$value.action='load';$null=Check-Response $value 'load'}
 }
 foreach($fixture in @(
 @{id='stage-ready-load-not-requested';counters=@(0,0,0,0,0)},@{id='stage-ready-load-not-submitted';counters=@(1,0,1,0,0)},
 @{id='stage-ready-load-not-entered';counters=@(1,1,0,0,0)},@{id='stage-ready-load-not-resumed';counters=@(1,1,1,0,0)})) {
  Reject $fixture.id {$null=Stage-Ready (Load-Snapshot $fixture.counters $false 'ready') 'load'} 'stale_input'
 }
 if((Get-FileHash -LiteralPath $Source -Algorithm SHA256).Hash.ToLowerInvariant() -cne $sourceHash){throw 'Source changed during checker execution'}
 $receipt.passed=@($cases|Where-Object {$_.status -ceq 'success'}).Count;$receipt.failed=$cases.Count-$receipt.passed
 if($cases.Count -ne 89 -or ($cases.id -join '|') -cne ($expected -join '|') -or $receipt.failed -ne 0){throw 'Checker case failure or incomplete expected set; inspect each original_exception'}
 $receipt.status='success'
} catch {$receipt.status='failure';$receipt.failure=Exception-Detail $_}
finally {Save-Receipt}
if($receipt.status -cne 'success'){exit 1}
'''

def load_utility():
    spec = importlib.util.spec_from_file_location("beryl_bounded_host_checker", UTILITY)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def expected_ids():
    block = SCRIPT.split("$expected=@(", 1)[1].split("\n$names=", 1)[0]
    values = re.findall(r"'([A-Za-z0-9._-]+)'", block)
    if len(values) != 89 or len(set(values)) != 89:
        raise ValueError("Invalid predeclared 89-case fixture set")
    if len(PASS_IDS) != 18 or len(STALE_IDS) != 23 or not (PASS_IDS | STALE_IDS) <= set(values) or PASS_IDS & STALE_IDS:
        raise ValueError("Invalid checker case outcome contracts")
    return values


def validate_result(result, ids, source, source_hash):
    if not isinstance(result, dict) or type(result.get("schema_version")) is not int or result["schema_version"] != 1:
        raise ValueError("Malformed checker receipt schema")
    if result.get("operation") != "callback.checkers.inert" or result.get("status") != "success":
        raise ValueError("Checker execution did not succeed; inspect original_exception")
    if result.get("source") != str(source) or result.get("source_sha256") != source_hash:
        raise ValueError("Checker source receipt differs from frozen snapshot")
    if result.get("function_names") != NAMES or result.get("expected_case_ids") != ids or result.get("completed_case_ids") != ids:
        raise ValueError("Checker identities missing/unknown/duplicate/reordered")
    if result.get("complete_expected_case_set") is not True or any(type(result.get(key)) is not int or result[key] != value for key, value in (("expected_cases", 89), ("case_count", 89), ("passed", 89), ("failed", 0))):
        raise ValueError("Incomplete checker counts")
    cases = result.get("cases")
    if not isinstance(cases, list) or [row.get("id") for row in cases if isinstance(row, dict)] != ids:
        raise ValueError("Incomplete checker case records")
    for row in cases:
        if set(row) != {"id", "status", "expected", "actual", "expected_status", "actual_status", "original_exception"}:
            raise ValueError("Malformed checker case fields")
        if row.get("status") != "success" or row.get("expected") != row.get("actual"):
            raise ValueError("Unexpected checker outcome")
        if row["id"] not in PASS_IDS:
            wanted = "stale_input" if row["id"] in STALE_IDS else "failure"
            if row["expected"] != "checker_rejection" or row.get("expected_status") != wanted or row.get("actual_status") != wanted or not isinstance(row.get("original_exception"), dict):
                raise ValueError("Checker rejection lost original exception/status")
            original = row["original_exception"]
            if set(original) != {"type", "message", "fully_qualified_error_id", "position", "script_stack"} or original.get("type") != "System.InvalidOperationException" or not isinstance(original.get("message"), str) or not original["message"]:
                raise ValueError("Checker rejection lacks the expected original exception")
        elif row["expected"] != "return" or row.get("original_exception") is not None or row.get("expected_status") is not None or row.get("actual_status") is not None:
            raise ValueError("Invalid checker success record")
    if result.get("failure") is not None:
        raise ValueError("Checker success has a harness failure")
    for key in ("compiler_execution", "engine_execution", "adapter_top_level", "actual_process_stop"):
        if result.get(key) != "not_run":
            raise ValueError("Checker receipt has unsupported execution scope")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true", help="Explicitly execute the pure checker host once")
    parser.add_argument("--powershell-host", type=Path)
    parser.add_argument("--expected-host-sha256")
    parser.add_argument("--expected-source-sha256")
    parser.add_argument("--output-root", type=Path, default=ROOT / "build")
    args = parser.parse_args(argv)
    if args.run and (args.powershell_host is None or args.expected_host_sha256 is None or args.expected_source_sha256 is None):
        parser.error("--run requires explicit host path/hash and source hash")
    bounded = load_utility()
    ids = expected_ids()
    work = args.output_root.absolute() / ("callback-checkers-" + uuid.uuid4().hex)
    work.mkdir()
    journal = bounded.Journal(work / "outer")
    source = work / "callback-source.ps1"
    script = work / "checks.ps1"
    pure_result = work / "pure-checks.json"
    record = {"schema_version": 1, "operation": "callback.checkers.driver", "status": "running",
              "phase": "prepared", "expected_case_ids": ids, "expected_cases": 89,
              "compiler_execution": "not_run", "engine_execution": "not_run", "adapter_top_level": "not_run",
              "host_execution": "not_run", "source": bounded.file_identity(SOURCE),
              "driver": bounded.file_identity(Path(__file__)), "utility": bounded.file_identity(UTILITY),
              "failure": None}
    try:
        journal.save(record)
        if args.expected_source_sha256 and record["source"]["sha256"] != args.expected_source_sha256:
            record["status"] = "stale_input"
            raise ValueError("Current checker source differs from requested immutable identity")
        source.write_bytes(SOURCE.read_bytes())
        script.write_bytes(SCRIPT.encode("utf-8"))
        record["source_snapshot"] = bounded.file_identity(source)
        record["script"] = bounded.file_identity(script)
        if record["script"]["sha256"] != hashlib.sha256(SCRIPT.encode("utf-8")).hexdigest():
            raise ValueError("Checker fixture write changed expected script bytes")
        if record["source_snapshot"]["sha256"] != record["source"]["sha256"] or bounded.file_identity(SOURCE) != record["source"]:
            record["status"] = "stale_input"
            raise ValueError("Source changed while retaining snapshot")
        record["phase"] = "source_prepared"
        record["status"] = "success"
        record["verification"] = "not_run; preparation only"
        journal.save(record)
        if args.run:
            record.update(status="running", phase="host_requested", host_execution="requested")
            journal.save(record)
            host_path = args.powershell_host.absolute()
            explicit = [str(host_path), "-NoProfile", "-File", str(script), "-Source", str(source),
                        "-ExpectedSourceHash", record["source"]["sha256"], "-Result", str(pure_result)]
            record["host_run"] = bounded.run_bounded(explicit, ROOT, work / "host", 45, 5,
                                                     expected_executable={"path": str(host_path), "sha256": args.expected_host_sha256})
            record["host_execution"] = "attempted"
            if pure_result.exists():
                record["pure_receipt"] = bounded.file_identity(pure_result, 1024 * 1024)
                record["pure_result"] = json.loads(pure_result.read_text(encoding="utf-8"))
            if record["host_run"]["status"] != "success":
                record["status"] = record["host_run"]["status"]
                raise ValueError("Host checker operation failed; inspect raw logs and per-case original_exception")
            if not pure_result.exists():
                raise ValueError("Host returned without checker receipt")
            validate_result(record["pure_result"], ids, source, record["source"]["sha256"])
            if bounded.file_identity(SOURCE) != record["source"] or bounded.file_identity(source) != record["source_snapshot"] or bounded.file_identity(script) != record["script"] or bounded.file_identity(UTILITY) != record["utility"] or bounded.file_identity(Path(__file__)) != record["driver"]:
                record["status"] = "stale_input"
                raise ValueError("Pinned checker input changed during operation")
            record.update(status="success", verification="89 pure checker cases verified", host_execution="executed_complete")
        if bounded.file_identity(UTILITY) != record["utility"] or bounded.file_identity(Path(__file__)) != record["driver"]:
            record["status"] = "stale_input"
            raise ValueError("Checker driver or utility source changed")
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
