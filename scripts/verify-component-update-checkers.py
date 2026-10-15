#!/usr/bin/env python3
"""Prepare an inert PowerShell AST checker; only the root may execute it.

The generated script parses the complete callback adapter and evaluates only
its pure update-policy selector, never its launcher or transport.
"""
from pathlib import Path
import hashlib
import json
import tempfile

ROOT = Path(__file__).resolve().parents[1]
ADAPTER = ROOT / "scripts/component-callback-engine.ps1"
CASE_IDS = (
    "policy.focus-dependent-null", "policy.force-update-five-arguments",
    "policy.spaces-and-metacharacters-preserved", "policy.no-world-or-module-opening",
    "policy.reject-unknown", "policy.reject-upper-case", "policy.reject-empty",
)


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.write_bytes(data) != len(data) or path.read_bytes() != data:
        raise RuntimeError("Incomplete checker fixture write")


def main():
    data = ADAPTER.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    work = Path(tempfile.mkdtemp(prefix="component-update-checkers-", dir=ROOT / "build"))
    frozen = work / "adapter.source.ps1"
    write(frozen, data)
    ps = r'''param([Parameter(Mandatory)][string]$ResultPath)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$source='@SOURCE@'
$hash='@HASH@'
$expectedCaseIds=@(@CASES@)
$record=[ordered]@{schema_version=1;operation='component.update-policy.checkers';status='failure';
 adapter_sha256=$hash;expected_case_ids=$expectedCaseIds;completed_case_ids=@();cases=@();
 scope='AST parse and pure update-policy selection only';engine_execution='not_run';compiler_execution='not_run';
 process_launch='not_run';failure=$null}
$callbackRecord=[ordered]@{status='failure'}
# Throw-Outcome is extracted with its original global variable name.
$recordForEvidence=$record
$record=$callbackRecord
try {
 if((Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash.ToLowerInvariant() -cne $hash){throw 'Frozen source mismatch'}
 $tokens=$null;$errors=$null
 $ast=[Management.Automation.Language.Parser]::ParseFile($source,[ref]$tokens,[ref]$errors)
 if($errors.Count){throw 'Callback adapter did not parse'}
 foreach($name in @('Throw-Outcome','Select-EngineUpdateProfile')){
  $nodes=@($ast.FindAll({param($n) $n -is [Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -ceq $name},$true))
  if($nodes.Count -ne 1){throw 'Missing or duplicate pure checker function'}
  . ([scriptblock]::Create($nodes[0].Extent.Text))
 }
 foreach($id in $expectedCaseIds){
  $negative=$id -cin @('policy.reject-unknown','policy.reject-upper-case','policy.reject-empty')
  $policy='force-update';$project='C:\fixture\addon'
  if($id -ceq 'policy.focus-dependent-null'){$policy='focus-dependent'}
  if($id -ceq 'policy.spaces-and-metacharacters-preserved'){$project='C:\fixture & spaces\addon (owned)'}
  if($id -ceq 'policy.reject-unknown'){$policy='automatic'}
  if($id -ceq 'policy.reject-upper-case'){$policy='FORCE-UPDATE'}
  if($id -ceq 'policy.reject-empty'){$policy=''}
  $outcome='return';$original=$null
  try {
   $actual=Select-EngineUpdateProfile $policy $project
   if($policy -ceq 'focus-dependent'){
    if($null -ne $actual){throw 'Legacy policy acquired a new argument vector'}
   }else{
    $expected=@('-gproj',(Join-Path $project 'addon.gproj'),'-noOpenLastResource','-scriptAuthorizeAll','-forceUpdate')
    if($actual -isnot [Array] -or $actual.Count -ne 5){throw 'Wrong force-update argument count'}
    for($i=0;$i -lt 5;$i++){if($actual[$i] -cne $expected[$i]){throw 'Argument bytes differ'}}
    if(@($actual | Where-Object {$_ -cmatch '^-load|^-wbmodule|^-run$'}).Count){throw 'Opening side effect in update policy'}
   }
  }catch{
   $original=$_.Exception.Message
   if($negative -and $record.status -ceq 'failure' -and $original -ceq 'Unknown engine update policy'){$outcome='failure'}else{throw}
  }
  if($negative -and $outcome -cne 'failure'){throw 'Unknown policy was accepted'}
  $recordForEvidence.completed_case_ids+= $id
  $recordForEvidence.cases+= [ordered]@{id=$id;status='passed';outcome=$outcome;original_exception=$original}
 }
 if(($recordForEvidence.completed_case_ids | ConvertTo-Json -Compress) -cne ($expectedCaseIds | ConvertTo-Json -Compress)){throw 'Incomplete checker case set'}
 if((Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash.ToLowerInvariant() -cne $hash){throw 'Frozen source changed'}
 $recordForEvidence.status='success';$recordForEvidence.complete_expected_case_set=$true
}catch{$recordForEvidence.failure=$_.Exception.Message}
$json=$recordForEvidence | ConvertTo-Json -Depth 12
[IO.File]::WriteAllText($ResultPath,$json,[Text.UTF8Encoding]::new($false))
if([IO.File]::ReadAllText($ResultPath) -cne $json){throw 'Incomplete checker receipt write'}
if($recordForEvidence.status -cne 'success'){Write-Error $recordForEvidence.failure;exit 1}
'''
    # Literal single-quoted PowerShell paths, with apostrophes encoded exactly.
    ps = ps.replace("@SOURCE@", str(frozen).replace("'", "''")).replace("@HASH@", digest)
    ps = ps.replace("@CASES@", ",".join("'" + case + "'" for case in CASE_IDS))
    script = work / "checkers.ps1"
    write(script, ps.encode("utf-8"))
    result = {"schema_version": 1, "status": "prepared", "verification": "not_run; root-owned PowerShell checker execution required",
              "adapter": {"path": str(ADAPTER), "sha256": digest}, "frozen_source": str(frozen),
              "checker": {"path": str(script), "sha256": hashlib.sha256(script.read_bytes()).hexdigest()},
              "expected_case_ids": list(CASE_IDS), "host_execution": "not_run", "engine_execution": "not_run"}
    write(work / "prepare.json", (json.dumps(result, indent=2) + "\n").encode("utf-8"))
    if ADAPTER.read_bytes() != data:
        raise RuntimeError("Adapter changed during preparation")
    print(work / "prepare.json")


if __name__ == "__main__":
    main()
