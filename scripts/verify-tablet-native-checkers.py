#!/usr/bin/env python3
"""Prepare/explicitly run AST-extracted pure native-tablet transport checkers.

The full transport is parsed, but only fifteen registered pure functions are
evaluated. No adapter entry, process/listener/engine/native callback is invoked.
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
SOURCE = ROOT / "scripts/tablet-native-engine.ps1"
UTILITY = ROOT / "scripts/verify-host-readiness.py"
NAMES = ["Throw-Outcome", "Normal-Path", "Required-Field", "Assert-Text", "Assert-Names", "Assert-Int", "Normalize-Bool",
         "Fixed-Arguments", "Assert-Transport", "Assert-Parameters", "Assert-LoadedProjects", "Check-Native", "Assert-World", "Stage-Ready", "Assert-RawResponse"]
TEXTS = ("token", "action", "status", "failure", "profile", "source_contract_sha256", "source_sha256", "world_path", "current_project",
         "addon_world_path", "world_absolute_path", "resource_name", "resource_path", "resource_absolute_path")
BOOLEANS = ("addon_world_resolved", "world_path_resolved", "resource_name_resolved", "module_present", "api_present", "module_open_requested",
            "module_open_accepted", "load_accepted", "world_matches", "edit_mode", "game_mode", "in_play_mode", "world_present", "game_world_present", "frames_ready", "stop_requested")
INTS = ("schema_version", "load_requested", "load_submitted", "load_entered", "load_resumed", "load_returned", "phase", "executed", "failures", "owner_count", "row_count", "checksum")


def case_registry():
    cases = []
    def add(name, body, status=None):
        cases.append((name, "return" if status is None else "checker_rejection", status, body))
    add("native.ready-load", "$v=Native 'load';$null=Check-Native $v 'load';if(-not (Stage-Ready $v 'load')){throw 'Ready load not selected'}")
    add("native.ready-play", "$v=Native 'play';$null=Check-Native $v 'play';if(-not (Stage-Ready $v 'play')){throw 'Ready play not selected'}")
    add("native.ready-spawn", "$v=Native 'spawn';$null=Check-Native $v 'spawn';if(-not (Stage-Ready $v 'spawn')){throw 'Ready spawn not selected'}")
    add("native.complete-stop", "$v=Native 'stop';$null=Check-Native $v 'stop';if(-not (Stage-Ready $v 'stop')){throw 'Complete stop not selected'}")
    add("native.raw-unchanged", "$v=Native 'stop';$before=$v|ConvertTo-Json -Depth 20 -Compress;$null=Check-Native $v 'stop';if(($v|ConvertTo-Json -Depth 20 -Compress) -cne $before){throw 'Raw input mutated'}")
    add("native.empty-arrays-preserved", "$v=Native 'load';$n=Check-Native $v 'load';if($n.response.rows.Count -ne 0 -or $n.response.caseIds.Count -ne 0 -or $n.response.frame_counts.Count -ne 0){throw 'Empty arrays lost'}")
    add("native.omitted-empty-arrays", "$v=Native 'load';foreach($k in @('caseIds','frame_counts','rows')){$v.PSObject.Properties.Remove($k)};$n=Check-Native $v 'load';if(($n.codec.omitted_empty_arrays -join '|') -cne 'caseIds|frame_counts|rows'){throw 'Omission codec differs'}")
    add("native.partial-rows-omission", "$v=Native 'spawn';$v.frames_ready=$false;$v.status='pending';$v.row_count=4;$v.frame_counts=@(0,0);$v.PSObject.Properties.Remove('rows');$n=Check-Native $v 'spawn';if($n.response.row_count -ne 4 -or $n.response.rows.Count -ne 0){throw 'Capture counter replaced by materialized rows'}")
    add("native.all-numeric-bools", "$v=Native 'load';foreach($k in $BooleanFields){$v.$k=[int]$v.$k};$n=Check-Native $v 'load';if(($n.codec.numeric_boolean_fields -join '|') -cne ($BooleanFields -join '|')){throw 'Numeric boolean codec differs'}")
    add("native.all-json-bools", "$v=Native 'load';$n=Check-Native $v 'load';if($n.codec.numeric_boolean_fields.Count -ne 0){throw 'JSON bool misreported'}")
    add("native.extra-field", "$v=Native 'load';$v|Add-Member extra 1;$null=Check-Native $v 'load'", "failure")
    add("native.null-response", "$null=Check-Native $null 'load'", "failure")
    for name in TEXTS + BOOLEANS + INTS:
        add("native.missing." + name, f"$v=Native 'load';$v.PSObject.Properties.Remove('{name}');$null=Check-Native $v 'load'", "failure")
    for name in ("token", "action", "profile", "source_sha256", "source_contract_sha256"):
        add("native.stale." + name, f"$v=Native 'load';$v.{name}='different';$null=Check-Native $v 'load'", "stale_input")
    for name in TEXTS:
        add("native.text-type." + name, f"$v=Native 'load';$v.{name}=1;$null=Check-Native $v 'load'", "failure")
    add("native.text-boundary", "$v=Native 'load';$v.current_project='x'*2048;$null=Check-Native $v 'load'")
    add("native.text-overflow", "$v=Native 'load';$v.current_project='x'*2049;$null=Check-Native $v 'load'", "failure")
    add("native.text-nul", "$v=Native 'load';$v.current_project='x'+[char]0;$null=Check-Native $v 'load'", "failure")
    for name in BOOLEANS:
        for kind, literal in (("two", "2"), ("double", "[double]1"), ("string", "'true'")):
            add("native.bool." + name + "." + kind, f"$v=Native 'load';$v.{name}={literal};$null=Check-Native $v 'load'", "failure")
    for name in INTS:
        for kind, literal in (("bool", "$true"), ("double", "[double]1")):
            add("native.int." + name + "." + kind, f"$v=Native 'load';$v.{name}={literal};$null=Check-Native $v 'load'", "failure")
    for name, literal in (("schema_version", "2"), ("phase", "1"), ("executed", "2"), ("failures", "2"), ("owner_count", "3"),
                          ("row_count", "805"), ("checksum", "1000003"), ("row_count", "-1"), ("checksum", "-1")):
        add("native.domain." + name + "." + literal.replace("-", "minus"), f"$v=Native 'load';$v.{name}={literal};$null=Check-Native $v 'load'", "failure")
    for literal in ("2147483648L", "-2147483649L", "'0'", "$null"):
        add("native.i32." + literal.replace("-", "minus").replace("'", "").replace("$", ""), f"$v=Native 'load';$v.checksum={literal};$null=Check-Native $v 'load'", "failure")
    for name in ("caseIds", "frame_counts", "rows"):
        add("native.array-scalar." + name, f"$v=Native 'load';$v.{name}='x';$null=Check-Native $v 'load'", "failure")
        add("native.complete-array-missing." + name, f"$v=Native 'stop';$v.PSObject.Properties.Remove('{name}');$null=Check-Native $v 'stop'", "failure")
    for name, body in [
        ("frame-count-number", "$v.frame_counts=@($true,3)"), ("frame-count-negative", "$v.frame_counts=@(-1,3)"),
        ("frame-count-overflow", "$v.frame_counts=@(201,3)"), ("frame-count-length", "$v.frame_counts=@(3)"),
        ("row-byte-bound", "$v.rows=@('x'*513)"), ("row-nonascii", "$v.rows=@([string][char]233)"),
        ("row-type", "$v.rows=@(1)"), ("row-count-cap", "$v.rows=@('x')*805"),
        ("case-type", "$v.caseIds=@(1)"), ("case-name", "$v.caseIds=@('other')"), ("case-cap", "$v.caseIds=@('native.init.1')*6")]:
        add("native.collection." + name, "$v=Native 'stop';" + body + ";$null=Check-Native $v 'stop'", "failure")
    add("native.capture-cap-boundary", "$v=Native 'stop';$v.row_count=804;$v.rows=@('synthetic-schema-row')*804;$v.frame_counts=@(200,200);$null=Check-Native $v 'stop'")
    for name, body in [
        ("submitted-before-request", "$v.load_requested=0"), ("entered-before-request", "$v.load_requested=0;$v.load_submitted=0"),
        ("resumed-before-entered", "$v.load_entered=0"), ("resumed-before-submitted", "$v.load_submitted=0"),
        ("returned-before-resumed", "$v.load_resumed=0"), ("accepted-before-return", "$v.load_returned=0"),
        ("counter-domain", "$v.load_requested=2")]:
        add("native.load-order." + name, "$v=Native 'load';" + body + ";$null=Check-Native $v 'load'", "failure")
    for name in ("load_requested", "load_submitted", "load_entered", "load_resumed", "load_returned"):
        add("native.ready-missing." + name, f"$v=Native 'load';$v.{name}=0;$null=Check-Native $v 'load'", "failure")
    add("native.ready-missing-acceptance", "$v=Native 'load';$v.load_accepted=$false;$null=Check-Native $v 'load'", "failure")
    for name, body in [("ready-failure-text", "$v.failure='bad'"), ("ready-failure-count", "$v.failures=1"),
                       ("ready-wrong-phase", "$v.phase=2"), ("pending-terminal-phase", "$v.status='pending';$v.phase=4")]:
        add("native.contradiction." + name, "$v=Native 'load';" + body + ";$null=Check-Native $v 'load'", "failure")
    add("native.pending-no-load", "$v=Native 'load';$v.status='pending';foreach($k in @('load_requested','load_submitted','load_entered','load_resumed','load_returned')){$v.$k=0};$v.load_accepted=$false;$null=Check-Native $v 'load'")
    add("native.pending-entered-before-submitted", "$v=Native 'load';$v.status='pending';$v.load_submitted=0;$v.load_resumed=0;$v.load_returned=0;$v.load_accepted=$false;$null=Check-Native $v 'load'")
    add("native.honest-failure-retained", "$v=Native 'load';$v.status='failure';$v.failure='fixture failed';$v.failures=1;$n=Check-Native $v 'load';if($n.response.status -cne 'failure'){throw 'Failure promoted'}")
    add("native.honest-unavailable-retained", "$v=Native 'load';$v.status='unavailable';$v.failure='capability missing';$n=Check-Native $v 'load';if($n.response.status -cne 'unavailable'){throw 'Unavailable promoted'}")
    add("native.load-reset", "$v=Native 'load';$script:lastLoadProgress=($v|ConvertTo-Json -Depth 20|ConvertFrom-Json);$v.load_entered=0;$v.load_resumed=0;$v.load_returned=0;$v.load_accepted=$false;$v.status='pending';$null=Check-Native $v 'load'", "stale_input")
    add("native.acceptance-reset", "$v=Native 'load';$script:lastLoadProgress=($v|ConvertTo-Json -Depth 20|ConvertFrom-Json);$v.load_accepted=$false;$v.status='pending';$null=Check-Native $v 'load'", "stale_input")
    for name, body in [
        ("missing-executed", "$v.executed=0"), ("wrong-phase", "$v.phase=2"), ("missing-stop", "$v.stop_requested=$false"),
        ("failure-count", "$v.failures=1"), ("failure-detail", "$v.failure='bad'"), ("owner-count", "$v.owner_count=1;$v.frame_counts=@(3)"),
        ("row-count-mismatch", "$v.row_count=15"), ("missing-cases", "$v.caseIds=@('native.init.1')"), ("frames-not-ready", "$v.frames_ready=$false"),
        ("not-edit", "$v.edit_mode=$false"), ("still-game", "$v.game_mode=$true"), ("still-play", "$v.in_play_mode=$true")]:
        add("native.terminal." + name, "$v=Native 'stop';" + body + ";$null=Check-Native $v 'stop'", "failure")
    add("native.executed-nonterminal", "$v=Native 'stop';$v.status='ready';$null=Check-Native $v 'stop'", "failure")
    for name, body in [("rows", "$v.rows=@('x')"), ("cases", "$v.caseIds=@('native.init.1')"), ("checksum", "$v.checksum=1")]:
        add("native.premature." + name, "$v=Native 'load';" + body + ";$null=Check-Native $v 'load'", "failure")
    for action in ("load", "play", "spawn"):
        add("stage.pending." + action, f"$v=Native '{action}';$v.status='pending';$v.frames_ready=$false;if(Stage-Ready $v '{action}'){{throw 'Pending response advanced'}}")
    for name, body in [("module", "$v.module_present=$false"), ("api", "$v.api_present=$false"), ("world-resolution", "$v.world_path_resolved=$false"),
                       ("resource", "$v.resource_name='different'"), ("absolute-world", "$v.world_absolute_path='C:/foreign/world.ent'"),
                       ("addon-world", "$v.addon_world_path='C:/foreign/world.ent'"), ("world-matches", "$v.world_matches=$false")]:
        add("stage.foreign." + name, "$v=Native 'load';" + body + ";$null=Stage-Ready $v 'load'", "stale_input")
    add("stage.spawn-outside-play", "$v=Native 'spawn';$v.in_play_mode=$false;$null=Stage-Ready $v 'spawn'", "failure")
    for name, body in [("below-minimum", "$v.frame_counts=@(2,3)"), ("above-maximum", "$v.frame_counts=@(201,3)"),
                       ("wrong-count", "$v.frame_counts=@(3)"), ("failure-count", "$v.failures=1"), ("failure-text", "$v.failure='bad'")]:
        add("stage.spawn-counter." + name, "$v=Native 'spawn';" + body + ";$null=Stage-Ready $v 'spawn'", "failure")
    add("stage.spawn-wrong-status-pending-only", "$v=Native 'spawn';$v.status='ready';if(Stage-Ready $v 'spawn'){throw 'Wrong spawn status advanced'}")
    add("stage.unregistered", "$null=Stage-Ready (Native 'load') 'delete'", "failure")
    add("parameters.loaded", "Assert-Parameters 'GetLoadedProjects' @{}")
    for action in ("load", "status", "play", "spawn", "stop"):
        add("parameters.native." + action, f"Assert-Parameters 'BerylTabletNativeCallbacks' @{{token=$Token;action='{action}'}}")
    for name, body in [("missing", "@{token=$Token}"), ("extra", "@{token=$Token;action='load';extra=1}"), ("token", "@{token='wrong';action='load'}"),
                       ("bool", "@{token=$Token;action=$true}"), ("case", "@{token=$Token;action='LOAD'}"), ("delete", "@{token=$Token;action='delete'}")]:
        add("parameters.reject." + name, "Assert-Parameters 'BerylTabletNativeCallbacks' " + body, "failure")
    for name in ("OpenResource", "CreateWorld", "Save", "Delete", "BerylTabletSuiteIdentity", "IsWorkbenchRunning"):
        add("parameters.forbidden." + name, f"Assert-Parameters '{name}' @{{}}", "failure")
    add("parameters.loaded-extra", "Assert-Parameters 'GetLoadedProjects' @{extra=1}", "failure")
    add("startup.fixed-five-argv", "$v=@(Fixed-Arguments $canonicalProject);$wanted=@('-gproj',(Join-Path $canonicalProject 'addon.gproj'),'-noOpenLastResource','-scriptAuthorizeAll','-forceUpdate');if($v.Count -ne 5 -or ($v -join '|') -cne ($wanted -join '|')){throw 'Native fixed argv changed'}")
    add("path.normalization", "if((Normal-Path 'C:/fixture/') -cne ('C:'+ [char]92+'fixture')){throw 'Path normalization differs'}")
    add("loaded.exact", "Assert-LoadedProjects ([pscustomobject]@{'Loaded Projects'=@('ArmaReforger','core',$ProjectId)})")
    for name, values in [("empty", "@()"), ("foreign", "@($ProjectId,'Foreign')"), ("duplicate", "@($ProjectId,$ProjectId)"), ("scalar", "$ProjectId")]:
        add("loaded.reject." + name, "Assert-LoadedProjects ([pscustomobject]@{'Loaded Projects'=" + values + "})", "stale_input")
    add("loaded.type", "Assert-LoadedProjects ([pscustomobject]@{'Loaded Projects'=@($ProjectId,1)})", "failure")
    add("transport.exact", "Assert-Transport (Reply) 'BerylTabletNativeCallbacks'")
    add("raw.exact", "Assert-RawResponse (Reply)")
    for name, body in [("numeric-ok", "$v.Ok=1"), ("false", "$v.Ok=$false"), ("function", "$v.Function='Save'"), ("error", "$v.ErrorCode='Failure'"),
                       ("raw-type", "$v.Raw=1"), ("raw-cap", "$v.Raw='x'*(1MB+1)"), ("extra", "$v|Add-Member extra 1")]:
        add("transport.reject." + name, "$v=Reply;" + body + ";Assert-Transport $v 'BerylTabletNativeCallbacks'", "failure")
    for name, body in [("malformed", "$v.Raw='{bad'"), ("null", "$v.Raw='null'"), ("empty-object", "$v.Raw='{}'"),
                       ("value", "$v.Response.token='wrong'"), ("bool-type", "$v.Response.frames_ready=1")]:
        add("raw.reject." + name, "$v=Reply;" + body + ";Assert-RawResponse $v", "failure")
    ids = [c[0] for c in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate predeclared native checker case")
    return tuple(cases)


HEADER = r'''param([string]$Source,[string]$ExpectedAdapterHash,[string]$Result)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$expectedCaseIds=__EXPECTED__
$names=__NAMES__
$BooleanFields=__BOOLEANS__
$Token='a'*64;$ExpectedSourceHash='b'*64;$ExpectedContractHash='c'*64
$suiteProfile='sparkos.tablet.native-init-stowed.source.v1'
$ProjectId='BerylTabletNativeCheckProbe';$canonicalProject='C:/fixture'
$record=@{status='failure';expected_world='C:/fixture/worlds/BerylTabletNativeStowed.ent'}
$script:lastLoadProgress=$null
$cases=[Collections.Generic.List[object]]::new();$lastReceiptHash=$null
$receipt=[ordered]@{schema_version=1;operation='tablet-native.checkers.inert';status='running';source=$Source;source_sha256=$ExpectedAdapterHash;
 function_names=$names;expected_case_ids=$expectedCaseIds;expected_cases=$expectedCaseIds.Count;cases=@();completed_case_ids=@();complete_expected_case_set=$false;
 compiler_execution='not_run';engine_execution='not_run';adapter_top_level='not_run';actual_process_stop='not_run';native_listener_inventory='not_run';failure=$null}
function Save-Receipt {
 $receipt.cases=@($cases.ToArray());$receipt.completed_case_ids=@($cases | ForEach-Object {$_.id});$receipt.case_count=$cases.Count
 $receipt.complete_expected_case_set=(($receipt.completed_case_ids -join '|') -ceq ($expectedCaseIds -join '|'))
 if([IO.File]::Exists($Result)) {
  if($null -eq $script:lastReceiptHash -or (Get-FileHash -LiteralPath $Result -Algorithm SHA256).Hash.ToLowerInvariant() -cne $script:lastReceiptHash){throw 'Checker receipt changed by another writer'}
 }
 $tmp=$Result+'.'+[Guid]::NewGuid().ToString('N')+'.tmp'
 $bytes=[Text.UTF8Encoding]::new($false).GetBytes(($receipt|ConvertTo-Json -Depth 24)+[Environment]::NewLine)
 $stream=[IO.File]::Open($tmp,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
 try{$stream.Write($bytes,0,$bytes.Length);$stream.Flush($true)}finally{$stream.Dispose()}
 $hash=[Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($bytes)).ToLowerInvariant()
 if((Get-FileHash -LiteralPath $tmp -Algorithm SHA256).Hash.ToLowerInvariant() -cne $hash){throw 'Checker receipt readback mismatch'}
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
 $record=@{status='failure';expected_world='C:/fixture/worlds/BerylTabletNativeStowed.ent'};$script:lastLoadProgress=$null
 $canonicalProject='C:/fixture'
 $case=[ordered]@{id=$Id;status='failure';expected=$Expected;actual='return';expected_status=$ExpectedStatus;actual_status=$null;original_exception=$null}
 try{&$Action;if($Expected -ceq 'return'){$case.status='success'}}catch{
  $case.actual='exception';$case.actual_status=$record.status;$case.original_exception=Exception-Detail $_
  if($Expected -ceq 'checker_rejection' -and $_.Exception -is [InvalidOperationException] -and $record.status -ceq $ExpectedStatus){$case.status='success';$case.actual='checker_rejection'}
 }
 $cases.Add($case);Save-Receipt
}
function Native([string]$Action) {
 $v=[pscustomobject][ordered]@{
  token=$Token;action=$Action;status='ready';failure='';profile=$suiteProfile;source_contract_sha256=$ExpectedContractHash;source_sha256=$ExpectedSourceHash;
  world_path='$BerylTabletNativeStowedPrototype:worlds/BerylTabletNativeStowed.ent';current_project='./addons/data/ArmaReforger.gproj';
  addon_world_path='C:/fixture/worlds/BerylTabletNativeStowed.ent';world_absolute_path='C:/fixture/worlds/BerylTabletNativeStowed.ent';
  resource_name='{BE71570A20261010}worlds/BerylTabletNativeStowed.ent';resource_path='worlds/BerylTabletNativeStowed.ent';resource_absolute_path='C:/fixture/worlds/BerylTabletNativeStowed.ent';
  addon_world_resolved=$true;world_path_resolved=$true;resource_name_resolved=$true;module_present=$true;api_present=$true;
  module_open_requested=$true;module_open_accepted=$true;load_accepted=$true;world_matches=$true;edit_mode=$true;game_mode=$false;in_play_mode=$false;
  world_present=$true;game_world_present=$true;frames_ready=$false;stop_requested=$false;
  schema_version=1;load_requested=1;load_submitted=1;load_entered=1;load_resumed=1;load_returned=1;phase=0;executed=0;failures=0;owner_count=0;row_count=0;checksum=0;
  caseIds=@();frame_counts=@();rows=@()
 }
 if($Action -cin @('play','spawn')){$v.edit_mode=$false;$v.game_mode=$true;$v.in_play_mode=$true}
 if($Action -ceq 'spawn'){$v.status='pending';$v.phase=2;$v.owner_count=2;$v.frames_ready=$true;$v.frame_counts=@(3,3)}
 if($Action -ceq 'stop'){
  $v.status='complete';$v.phase=4;$v.executed=1;$v.stop_requested=$true;$v.owner_count=2;$v.frames_ready=$true;$v.frame_counts=@(3,3);
  $v.rows=@('synthetic-schema-only-row')*16;$v.row_count=16;$v.checksum=12;
  $v.caseIds=@('native.init.1','native.init.2','native.stowed-frames.1','native.stowed-frames.2','native.independent-state')
 }
 return $v
}
function Reply {
 $v=Native 'load'
 return [pscustomobject][ordered]@{Ok=$true;Function='BerylTabletNativeCallbacks';ErrorCode='Ok';Response=$v;Raw=($v|ConvertTo-Json -Depth 20 -Compress)}
}
try {
 Save-Receipt
 if($expectedCaseIds.Count -ne __COUNT__ -or @($expectedCaseIds|Select-Object -Unique).Count -ne __COUNT__){throw 'Invalid expected fixture identities'}
 $bytes=[IO.File]::ReadAllBytes($Source)
 if([Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($bytes)).ToLowerInvariant() -cne $ExpectedAdapterHash){throw 'Retained source identity differs'}
 $text=[Text.UTF8Encoding]::new($false,$true).GetString($bytes);$tokens=$null;$errors=$null
 $ast=[Management.Automation.Language.Parser]::ParseInput($text,[ref]$tokens,[ref]$errors)
 if($errors.Count){throw 'Native-tablet adapter PowerShell parse error'}
 foreach($name in $names){
  $defs=@($ast.FindAll({param($node)$node -is [Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -ceq $name},$true))
  if($defs.Count -ne 1){throw ('Missing/duplicate pure checker '+$name)}
  Invoke-Expression $defs[0].Extent.Text
 }
 __CASES__
 if(($cases.id -join '|') -cne ($expectedCaseIds -join '|')){throw 'Completed checker set differs'}
 $receipt.passed=@($cases|Where-Object {$_.status -ceq 'success'}).Count;$receipt.failed=@($cases|Where-Object {$_.status -cne 'success'}).Count
 if($receipt.failed){throw 'Pure native checker contracts failed'}
 $receipt.status='success'
}catch{$receipt.failure=Exception-Detail $_;$receipt.status='failure'}finally{Save-Receipt}
if($receipt.status -cne 'success'){Write-Error 'Pure native-tablet checker failure; inspect original_exception';exit 1}
'''


def ps_array(values):
    return "@(" + ",".join("'" + value + "'" for value in values) + ")"


def fixture_script(cases):
    actions = []
    for case_id, outcome, status, action in cases:
        actions.append(f"Case '{case_id}' '{outcome}' " + ("$null" if status is None else "'" + status + "'") + " {" + action + "}")
    return HEADER.replace("__EXPECTED__", ps_array([c[0] for c in cases])).replace("__NAMES__", ps_array(NAMES)).replace("__BOOLEANS__", ps_array(BOOLEANS)).replace("__COUNT__", str(len(cases))).replace("__CASES__", "\n".join(actions))


def validate_result(value, cases, source, sha):
    if type(value) is not dict or type(value.get("schema_version")) is not int or value["schema_version"] != 1:
        raise ValueError("Malformed pure receipt")
    if value.get("operation") != "tablet-native.checkers.inert" or value.get("status") != "success" or value.get("failure") is not None:
        raise ValueError("Native checker execution not successful")
    ids = [c[0] for c in cases]
    if value.get("source") != str(source) or value.get("source_sha256") != sha or value.get("function_names") != NAMES:
        raise ValueError("Source/function identity differs")
    if value.get("expected_case_ids") != ids or value.get("completed_case_ids") != ids or value.get("complete_expected_case_set") is not True:
        raise ValueError("Incomplete, duplicate or reordered native checker cases")
    for name, expected in (("expected_cases", len(cases)), ("case_count", len(cases)), ("passed", len(cases)), ("failed", 0)):
        if type(value.get(name)) is not int or value[name] != expected:
            raise ValueError("Incomplete checker counts")
    rows = value.get("cases")
    fields = {"id", "status", "expected", "actual", "expected_status", "actual_status", "original_exception"}
    if type(rows) is not list or len(rows) != len(cases):
        raise ValueError("Missing per-case outcomes")
    for row, (case_id, outcome, status, _) in zip(rows, cases):
        if type(row) is not dict or set(row) != fields or row["id"] != case_id or row["status"] != "success" or row["expected"] != outcome or row["actual"] != outcome or row["expected_status"] != status:
            raise ValueError("Unexpected case identity/outcome")
        if outcome == "return":
            if row["actual_status"] is not None or row["original_exception"] is not None:
                raise ValueError("Successful return contains exception")
        else:
            error = row["original_exception"]
            if row["actual_status"] != status or type(error) is not dict or set(error) != {"type", "message", "fully_qualified_error_id", "position", "script_stack"} or error["type"] != "System.InvalidOperationException" or type(error["message"]) is not str or not error["message"]:
                raise ValueError("Domain rejection lost original exception")
    if any(value.get(f) != "not_run" for f in ("compiler_execution", "engine_execution", "adapter_top_level", "actual_process_stop", "native_listener_inventory")):
        raise ValueError("Unsupported execution claim")


def synthetic_result(cases, source, sha):
    return {"schema_version": 1, "operation": "tablet-native.checkers.inert", "status": "success", "failure": None,
            "source": str(source), "source_sha256": sha, "function_names": list(NAMES), "expected_case_ids": [c[0] for c in cases], "completed_case_ids": [c[0] for c in cases],
            "complete_expected_case_set": True, "expected_cases": len(cases), "case_count": len(cases), "passed": len(cases), "failed": 0,
            "cases": [{"id": name, "status": "success", "expected": expected, "actual": expected, "expected_status": status, "actual_status": status,
                       "original_exception": None if status is None else {"type": "System.InvalidOperationException", "message": "Synthetic rejection", "fully_qualified_error_id": "synthetic", "position": "", "script_stack": ""}}
                      for name, expected, status, _ in cases],
            **{f: "not_run" for f in ("compiler_execution", "engine_execution", "adapter_top_level", "actual_process_stop", "native_listener_inventory")}}


def self_test(cases, sha):
    source = Path("source-only-synthetic.ps1")
    sample = synthetic_result(cases, source, sha)
    rejected = next(i for i, c in enumerate(cases) if c[2] is not None)
    faults = [("schema-bool", lambda v: v.update(schema_version=True)), ("missing-case", lambda v: v["cases"].pop()),
              ("unknown-function", lambda v: v["function_names"].append("Invoke-Call")), ("missing-completion", lambda v: v["completed_case_ids"].pop()),
              ("duplicate-completion", lambda v: v["completed_case_ids"].append(v["completed_case_ids"][0])), ("wrong-source", lambda v: v.update(source_sha256="0" * 64)),
              ("wrong-count", lambda v: v.update(passed=len(cases) + 1)), ("lost-exception", lambda v: v["cases"][rejected].update(original_exception=None)),
              ("wrong-status", lambda v: v["cases"][rejected].update(actual_status="unavailable")),
              ("generic-exception", lambda v: v["cases"][rejected]["original_exception"].update(type="System.Exception")),
              ("false-scope", lambda v: v.update(engine_execution="executed")), ("retained-failure", lambda v: v.update(failure={"message": "failure"})),
              ("unknown-row-field", lambda v: v["cases"][0].update(extra=True))]
    fixture = fixture_script(cases)
    if "$expected=" in fixture or "$expectedCaseIds=" not in fixture or any(x in fixture for x in ("__EXPECTED__", "__CASES__", "__NAMES__", "__BOOLEANS__", "__COUNT__")) or len(NAMES) != 15 or any(name in NAMES for name in ("Run-Stage", "Invoke-Call", "Assert-Inputs", "Wait-Listener", "Assert-OwnedSession")):
        raise ValueError("Fixture registry/pure extraction differs")
    result = [{"id": "fixture-pure-extraction", "status": "success"}]
    validate_result(copy.deepcopy(sample), cases, source, sha)
    result.append({"id": "synthetic-positive", "status": "success"})
    for name, change in faults:
        value = copy.deepcopy(sample)
        change(value)
        try:
            validate_result(value, cases, source, sha)
        except ValueError:
            result.append({"id": name, "status": "success"})
        else:
            raise ValueError("Malformed synthetic receipt admitted: " + name)
    return {"scope": "Python receipt/fixture validation only; PowerShell execution not_run", "expected_case_ids": [r["id"] for r in result], "cases": result, "complete_expected_case_set": True}


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
        parser.error("--run requires an explicit host path/hash and source hash")
    spec = importlib.util.spec_from_file_location("native_checker_host_bounds", UTILITY)
    bounded = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = bounded
    spec.loader.exec_module(bounded)
    cases = case_registry()
    work = args.output_root.absolute() / ("tablet-native-checkers-" + uuid.uuid4().hex)
    work.mkdir()
    journal = bounded.Journal(work / "outer")
    source, script, pure = work / "tablet-native-source.ps1", work / "checks.ps1", work / "pure-checks.json"
    record = {"schema_version": 1, "operation": "tablet-native.checkers.driver", "status": "running", "phase": "preparing", "failure": None,
              "source": bounded.file_identity(SOURCE), "driver": bounded.file_identity(Path(__file__)), "utility": bounded.file_identity(UTILITY),
              "expected_case_ids": [c[0] for c in cases], "expected_cases": len(cases),
              **{f: "not_run" for f in ("compiler_execution", "engine_execution", "adapter_top_level", "host_execution", "actual_process_stop", "native_listener_inventory")}}
    try:
        journal.save(record)
        if args.expected_source_sha256 and args.expected_source_sha256 != record["source"]["sha256"]:
            record["status"] = "stale_input"
            raise ValueError("Requested source identity differs")
        raw, fixture = SOURCE.read_bytes(), fixture_script(cases).encode("utf-8")
        if source.write_bytes(raw) != len(raw) or script.write_bytes(fixture) != len(fixture):
            raise ValueError("Short fixture preparation write")
        record["source_snapshot"], record["script"] = bounded.file_identity(source), bounded.file_identity(script)
        if record["source_snapshot"]["sha256"] != record["source"]["sha256"] or record["script"]["sha256"] != hashlib.sha256(fixture).hexdigest() or bounded.file_identity(SOURCE) != record["source"]:
            record["status"] = "stale_input"
            raise ValueError("Fixture source changed during capture")
        record.update(status="success", phase="source_prepared", verification="not_run; preparation only")
        journal.save(record)
        if args.self_test:
            record["synthetic_validation"] = self_test(cases, record["source"]["sha256"])
            record["verification"] = "15 Python synthetic receipt/fixture cases; PowerShell execution not_run"
        if args.run:
            record.update(status="running", phase="host_requested", verification="incomplete; checker run requested", host_execution="requested")
            journal.save(record)
            host = args.powershell_host.absolute()
            argv = [str(host), "-NoProfile", "-File", str(script), "-Source", str(source), "-ExpectedAdapterHash", record["source"]["sha256"], "-Result", str(pure)]
            record["host_run"] = bounded.run_bounded(argv, ROOT, work / "host", 45, 5, expected_executable={"path": str(host), "sha256": args.expected_host_sha256})
            record["host_execution"] = "attempted"
            if pure.exists():
                record["pure_receipt"] = bounded.file_identity(pure, 1024 * 1024)
                record["pure_result"] = json.loads(pure.read_text(encoding="utf-8"))
            if record["host_run"]["status"] != "success":
                record["status"] = record["host_run"]["status"]
                raise ValueError("Pure checker host failed; retained per-case exceptions identify cause")
            validate_result(record.get("pure_result"), cases, source, record["source"]["sha256"])
            record.update(status="success", verification=str(len(cases)) + " pure native transport checker cases verified", host_execution="executed_complete")
        for p, key in ((SOURCE, "source"), (source, "source_snapshot"), (script, "script"), (UTILITY, "utility"), (Path(__file__), "driver")):
            if bounded.file_identity(p) != record[key]:
                record["status"] = "stale_input"
                raise ValueError("Pinned checker input changed")
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
