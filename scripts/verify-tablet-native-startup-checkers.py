#!/usr/bin/env python3
"""Prepare/explicitly run pure bounded startup-image readiness checkers.

Only five registered source functions are evaluated with scripted process and
clock objects. The adapter entry, real Process, engine, compiler, listener, RPC,
file lease and process-stop paths are never invoked by this checker.
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
ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'scripts/tablet-native-leased-startup-engine.ps1'
BASE=ROOT/'scripts/tablet-native-leased-engine.ps1'
UTILITY=ROOT/'scripts/verify-host-readiness.py'
PREDECESSOR=ROOT/'scripts/verify-tablet-native-checkers.py'
BASE_SHA='9efeb5234acb1f01465eb6b94ba5a3b3b3b37363a6792f596fbef5f64afdd948'
NAMES=['Throw-Outcome','Normal-Path','Assert-Deadline','Read-StartupIdentity','Wait-StartupIdentity']
OLD_NAMES=['Throw-Outcome','Normal-Path','Required-Field','Assert-Text','Assert-Names','Assert-Int','Normalize-Bool','Fixed-Arguments','Assert-Transport','Assert-Parameters','Assert-LoadedProjects','Check-Native','Assert-World','Stage-Ready','Assert-RawResponse','Lease-HandleHash','Read-LeaseBasis','Open-ReadLease','Assert-HeldReadLease','Fast-NamespaceSnapshot','Assert-FastInputs','Close-ReadLease','Relative-Name','Assert-Deadline']


def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m


def source_relation(raw,old):
    def funcs(b):
        s=b.decode('utf-8').replace('\r\n','\n');starts=list(re.finditer(r'(?m)^function ([A-Za-z][A-Za-z0-9-]*)(?:\(|\s|$)',s));d={}
        for i,x in enumerate(starts):
            if x[1] in d: raise ValueError('Duplicate source function')
            d[x[1]]=s[x.start():starts[i+1].start() if i+1<len(starts) else len(s)].rstrip()
        return d
    actual,prior=funcs(raw),funcs(old)
    if any(name not in actual or actual[name]!=prior[name] for name in OLD_NAMES): raise ValueError('Frozen24 predecessor helper bodies changed')
    if set(actual)-set(prior)!={'Read-StartupIdentity','Wait-StartupIdentity'}: raise ValueError('Unexpected source function addition')


def case_registry():
    cases=[]
    def add(name,body,status=None): cases.append(('startup.'+name,'return' if status is None else 'checker_rejection',status,'With-StartupFixture {'+body+'}'))
    add('initial-image',"$p=Fake-Process @((Frame 'C:/fixture/Workbench.exe'));$v=Wait-StartupIdentity $p;if($v.status -cne 'verified' -or $p.Refreshes -ne 1 -or $record.startup.identity_checks.Count -ne 1){throw 'Initial identity not verified'}")
    add('null-pending',"$p=Fake-Process @((Frame $null));$v=Read-StartupIdentity $p 0;if($v.status -cne 'pending' -or $null -ne $v.raw_path -or $null -ne $v.normalized_path -or $record.startup.identity_start_ticks -ne $Start.Ticks){throw 'Null image was invented'}")
    add('empty-pending',"$p=Fake-Process @((Frame ''));$v=Read-StartupIdentity $p 0;if($v.status -cne 'pending' -or $v.raw_path -cne ''){throw 'Empty image promoted'}")
    add('null-empty-success',"$p=Fake-Process @((Frame $null),(Frame ''),(Frame 'C:/fixture/Workbench.exe'));$v=Wait-StartupIdentity $p;if($p.Refreshes -ne 3 -or ($record.startup.identity_checks.status -join '|') -cne 'pending|pending|verified' -or $record.startup.identity_polls -ne 2){throw 'Pending order differs'}")
    add('canonical-case-slashes',"$p=Fake-Process @((Frame 'c:/FIXTURE/Workbench.exe'));$v=Wait-StartupIdentity $p;if($v.status -cne 'verified'){throw 'Canonical image not admitted'}")
    add('ledger-before-foreign-rejection',"$p=Fake-Process @((Frame 'C:/foreign/Workbench.exe'));try{$null=Wait-StartupIdentity $p}catch{if($p.Refreshes -ne 1 -or $record.startup.identity_checks[0].raw_path -cne 'C:/foreign/Workbench.exe' -or $record.startup.identity_checks[0].start_ticks -ne $Start.Ticks){throw 'Actual rejected identity not retained'};throw}",'stale_input')
    add('foreign-no-retry',"$p=Fake-Process @((Frame 'C:/foreign/Workbench.exe'),(Frame 'C:/fixture/Workbench.exe'));try{$null=Wait-StartupIdentity $p}catch{if($p.Refreshes -ne 1){throw 'Foreign path retried'};throw}",'stale_input')
    add('pid-change',"$a=Frame $null;$b=Frame 'C:/fixture/Workbench.exe';$b.Id=124;$p=Fake-Process @($a,$b);$null=Wait-StartupIdentity $p",'stale_input')
    add('initial-pid-mismatch',"$a=Frame 'C:/fixture/Workbench.exe';$a.Id=124;$p=Fake-Process @($a);$null=Wait-StartupIdentity $p",'stale_input')
    add('ticks-change',"$a=Frame $null;$b=Frame 'C:/fixture/Workbench.exe';$b.Start=$Start.AddTicks(1);$p=Fake-Process @($a,$b);$null=Wait-StartupIdentity $p",'stale_input')
    add('captured-ticks-mismatch',"$script:ownedStartTicks=$Start.AddTicks(1).Ticks;$p=Fake-Process @((Frame 'C:/fixture/Workbench.exe'));$null=Wait-StartupIdentity $p",'stale_input')
    add('null-budget64',"$p=Fake-Process @((Frame $null));try{$null=Wait-StartupIdentity $p}catch{if($p.Refreshes -ne 64 -or $record.startup.identity_checks.Count -ne 64 -or $record.startup.identity_polls -ne 63){throw 'Null image poll bound differs'};throw}",'timeout')
    add('last-observation-success',"$a=@();for($i=0;$i -lt 63;$i++){$a+=Frame $null};$a+=Frame 'C:/fixture/Workbench.exe';$p=Fake-Process $a;$v=Wait-StartupIdentity $p;if($p.Refreshes -ne 64 -or $v.status -cne 'verified'){throw 'Final bounded observation missing'}")
    add('confirmed-exit',"$a=Frame $null;$a.Exited=$true;$p=Fake-Process @($a);$null=Wait-StartupIdentity $p",'unavailable')
    add('exit-after-pending',"$a=Frame $null;$b=Frame 'C:/fixture/Workbench.exe';$b.Exited=$true;$p=Fake-Process @($a,$b);$null=Wait-StartupIdentity $p",'unavailable')
    for name,field,value in [('bool-pid','Id','$true'),('zero-pid','Id','0'),('bad-start','Start','$true'),('bad-path','Path','1'),('oversize-path','Path',"'x'*32769"),('bad-exit','Exited','1')]:
        add(name,"$a=Frame 'C:/fixture/Workbench.exe';$a."+field+'='+value+';$p=Fake-Process @($a);$null=Wait-StartupIdentity $p','unavailable')
    for site in ['Refresh','Id','Start','Path','Exit']:
        add('query-error-'+site.lower(),"$a=Frame 'C:/fixture/Workbench.exe';$a.ThrowSite='"+site+"';$p=Fake-Process @($a);try{$null=Wait-StartupIdentity $p}catch{$e=$record.startup.identity_checks[-1].query_error;if($null -eq $e -or $e.type -isnot [string] -or $e.hresult -isnot [int] -or $e.message.Length -eq 0){throw 'Query exception identity lost'};throw}",'unavailable')
    add('query-error-after-null',"$a=Frame $null;$b=Frame 'C:/fixture/Workbench.exe';$b.ThrowSite='Path';$p=Fake-Process @($a,$b);try{$null=Wait-StartupIdentity $p}catch{if($p.Refreshes -ne 2 -or $record.startup.identity_checks.Count -ne 2 -or $record.startup.identity_checks[0].status -cne 'pending' -or $record.startup.identity_checks[1].status -cne 'query_error'){throw 'Pending query failure provenance lost'};throw}",'unavailable')
    add('stage-deadline-before-query',"$stageClock.ElapsedMilliseconds=30000;$p=Fake-Process @((Frame 'C:/fixture/Workbench.exe'));try{$null=Wait-StartupIdentity $p}catch{if($p.Refreshes -ne 0){throw 'Expired stage queried process'};throw}",'timeout')
    add('total-deadline-before-query',"$clock.ElapsedMilliseconds=180000;$p=Fake-Process @((Frame 'C:/fixture/Workbench.exe'));try{$null=Wait-StartupIdentity $p}catch{if($p.Refreshes -ne 0){throw 'Expired total queried process'};throw}",'timeout')
    add('late-positive-rejected',"$a=Frame 'C:/fixture/Workbench.exe';$a.Elapsed=30000;$p=Fake-Process @($a);$null=Wait-StartupIdentity $p",'timeout')
    add('pending-budget-exhausted',"$a=Frame $null;$a.Elapsed=29999;$b=Frame 'C:/fixture/Workbench.exe';$b.Elapsed=30000;$p=Fake-Process @($a,$b);$null=Wait-StartupIdentity $p",'timeout')
    add('start-unit-explicit',"$p=Fake-Process @((Frame 'C:/fixture/Workbench.exe'));$v=Wait-StartupIdentity $p;if($v.start_ticks_unit -cne 'dotnet_datetime_0001_utc_100ns' -or $record.startup.identity_start_ticks_unit -cne $v.start_ticks_unit){throw 'Timestamp domains ambiguous'}")
    add('null-module-pending-success',"$a=Frame $null;$a.ModulePresent=$false;$b=Frame 'C:/fixture/Workbench.exe';$p=Fake-Process @($a,$b);$v=Wait-StartupIdentity $p;if($p.Refreshes -ne 2 -or $record.startup.identity_checks[0].module_present -ne $false -or $record.startup.identity_checks[0].status -cne 'pending' -or $v.module_present -ne $true){throw 'Null module not distinguished from query failure'}")
    if len({c[0] for c in cases})!=len(cases): raise ValueError('Duplicate startup case')
    return tuple(cases)


HELPERS=r'''
function Frame([object]$Path) {return [pscustomobject]@{Id=123;Start=$Start;Path=$Path;ModulePresent=$true;Exited=$false;ThrowSite='';Elapsed=0}}
function Fake-Process([Array]$Frames) {
 $p=[pscustomobject]@{Frames=$Frames;Index=-1;Refreshes=0;Clock=$clock;StageClock=$stageClock}
 $p|Add-Member ScriptMethod Refresh {$this.Refreshes++;$this.Index=[Math]::Min($this.Index+1,$this.Frames.Count-1);$f=$this.Frames[$this.Index];$this.Clock.ElapsedMilliseconds=$f.Elapsed;$this.StageClock.ElapsedMilliseconds=$f.Elapsed;if($f.ThrowSite -ceq 'Refresh'){throw [IO.IOException]::new('injected refresh query')}}
 $p|Add-Member ScriptMethod get_Id {if($this.Frames[$this.Index].ThrowSite -ceq 'Id'){throw [IO.IOException]::new('injected PID query')};return $this.Frames[$this.Index].Id}
 $p|Add-Member ScriptMethod get_StartTime {if($this.Frames[$this.Index].ThrowSite -ceq 'Start'){throw [IO.IOException]::new('injected start query')};return $this.Frames[$this.Index].Start}
 $p|Add-Member ScriptMethod get_MainModule {if(-not $this.Frames[$this.Index].ModulePresent){return $null};$module=[pscustomobject]@{Frame=$this.Frames[$this.Index]};$module|Add-Member ScriptMethod get_FileName {if($this.Frame.ThrowSite -ceq 'Path'){throw [IO.IOException]::new('injected image query')};return $this.Frame.Path};return $module}
 $p|Add-Member ScriptMethod WaitForExit {param($milliseconds);if($milliseconds -ne 0){throw 'Unexpected nonzero wait'};if($this.Frames[$this.Index].ThrowSite -ceq 'Exit'){throw [IO.IOException]::new('injected exit query')};return $this.Frames[$this.Index].Exited}
 return $p
}
function With-StartupFixture([scriptblock]$Body) {
 $Start=[DateTime]::SpecifyKind([DateTime]::new(2026,10,10,12,0,0),[DateTimeKind]::Utc)
 $clock=[pscustomobject]@{ElapsedMilliseconds=0};$stageClock=[pscustomobject]@{ElapsedMilliseconds=0}
 $script:ownedPid=123;$script:ownedStartTicks=$null
 $record.engine_path='C:/fixture/Workbench.exe';$record.startup=@{identity_checks=@();identity_status='not_requested';identity_polls=0;identity_start_ticks=$null;identity_start_time=$null;identity_start_ticks_unit='dotnet_datetime_0001_utc_100ns';identity_started_ms=$null;identity_completed_ms=$null;identity_duration_ms=$null}
 &$Body
}
'''


def fixture_script(base,cases):
    header=base.HEADER.replace("operation='tablet-native.checkers.inert'","operation='tablet-native.startup-checkers.inert'")
    header=header.replace('try {\n Save-Receipt',HELPERS+'\ntry {\n Save-Receipt')
    actions=["Case '"+name+"' '"+outcome+"' "+('$null' if status is None else "'"+status+"'")+" {"+body+"}" for name,outcome,status,body in cases]
    return header.replace('__EXPECTED__',base.ps_array([c[0] for c in cases])).replace('__NAMES__',base.ps_array(NAMES)).replace('__BOOLEANS__',base.ps_array(base.BOOLEANS)).replace('__COUNT__',str(len(cases))).replace('__CASES__','\n'.join(actions))


def validate_result(base,value,cases,path,sha):
    if type(value) is not dict or value.get('operation')!='tablet-native.startup-checkers.inert' or value.get('function_names')!=NAMES: raise ValueError('Wrong startup function/scope envelope')
    v=copy.deepcopy(value);v['operation']='tablet-native.checkers.inert';v['function_names']=base.NAMES;base.validate_result(v,cases,path,sha)


def self_test(base,cases,sha):
    ids=['source-old24-preserved','source-mutation-rejected','source-fixture-pure','synthetic-positive','wrong-function','missing-case','schema-bool','generic-exception','false-engine','wrong-status','wrong-source']
    rows=[];raw,old=SOURCE.read_bytes(),BASE.read_bytes();source_relation(raw,old);rows.append({'id':ids[0],'status':'success'})
    try: source_relation(raw.replace(b'return $Path.Replace',b'return $Path.Trim().Replace',1),old)
    except ValueError: rows.append({'id':ids[1],'status':'success'})
    else: raise ValueError('Changed predecessor function admitted')
    f=fixture_script(base,cases)
    if len(NAMES)!=5 or any(n in NAMES for n in ('Invoke-Call','Run-Stage','Open-ReadLease','Assert-OwnedSession')) or any(x in f for x in ('__EXPECTED__','__NAMES__','__COUNT__','__CASES__','__BOOLEANS__')): raise ValueError('Unsafe source extraction')
    rows.append({'id':ids[2],'status':'success'})
    value=base.synthetic_result(cases,Path('synthetic-startup.ps1'),sha);value.update(operation='tablet-native.startup-checkers.inert',function_names=NAMES)
    validate_result(base,value,cases,Path('synthetic-startup.ps1'),sha);rows.append({'id':ids[3],'status':'success'})
    rejection=next(i for i,c in enumerate(cases) if c[2] is not None)
    changes=[lambda v:v['function_names'].append('Invoke-Call'),lambda v:v['cases'].pop(),lambda v:v.update(schema_version=True),lambda v:v['cases'][rejection]['original_exception'].update(type='System.Exception'),lambda v:v.update(engine_execution='executed'),lambda v:v['cases'][rejection].update(actual_status='failure'),lambda v:v.update(source_sha256='0'*64)]
    for name,change in zip(ids[4:],changes):
        v=copy.deepcopy(value);change(v)
        try:validate_result(base,v,cases,Path('synthetic-startup.ps1'),sha)
        except ValueError:rows.append({'id':name,'status':'success'})
        else:raise ValueError('Synthetic malformed receipt admitted: '+name)
    return {'scope':'Python source/receipt synthetics only; fake-process PowerShell execution not_run','expected_case_ids':ids,'cases':rows,'complete_expected_case_set':[x['id'] for x in rows]==ids}


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);mode=p.add_mutually_exclusive_group();mode.add_argument('--run',action='store_true');mode.add_argument('--self-test',action='store_true')
    p.add_argument('--powershell-host',type=Path);p.add_argument('--expected-host-sha256');p.add_argument('--expected-source-sha256');p.add_argument('--output-root',type=Path,default=ROOT/'build');a=p.parse_args(argv)
    if a.run and not all((a.powershell_host,a.expected_host_sha256,a.expected_source_sha256)):p.error('--run requires exact host path/hash and source hash')
    base=load(PREDECESSOR,'native_startup_predecessor');bounded=load(UTILITY,'native_startup_bounds');cases=case_registry()
    work=a.output_root.absolute()/('tablet-native-startup-checkers-'+uuid.uuid4().hex);work.mkdir();journal=bounded.Journal(work/'outer')
    snapshot,script,pure=work/'startup-source.ps1',work/'checks.ps1',work/'pure-checks.json'
    r={'schema_version':1,'operation':'tablet-native.startup-checkers.driver','status':'running','phase':'preparing','failure':None,'source':bounded.file_identity(SOURCE),'base_source':bounded.file_identity(BASE),'driver':bounded.file_identity(Path(__file__)),'utility':bounded.file_identity(UTILITY),'predecessor':bounded.file_identity(PREDECESSOR),'expected_case_ids':[c[0] for c in cases],'expected_cases':len(cases),**{k:'not_run' for k in ('compiler_execution','engine_execution','host_execution','adapter_top_level','actual_process_stop','native_listener_inventory','file_lease_effects')}}
    try:
        journal.save(r)
        if r['base_source']['sha256']!=BASE_SHA or (a.expected_source_sha256 and a.expected_source_sha256!=r['source']['sha256']):r['status']='stale_input';raise ValueError('Pinned source mismatch')
        raw=SOURCE.read_bytes();source_relation(raw,BASE.read_bytes());f=fixture_script(base,cases).encode('utf-8')
        if snapshot.write_bytes(raw)!=len(raw) or script.write_bytes(f)!=len(f):raise ValueError('Short source preparation write')
        r['source_snapshot'],r['script']=bounded.file_identity(snapshot),bounded.file_identity(script)
        if r['source_snapshot']['sha256']!=r['source']['sha256'] or r['script']['sha256']!=hashlib.sha256(f).hexdigest():raise ValueError('Capture mismatch')
        r.update(status='success',verification='source preparation only; no actual process queries')
        if a.self_test:r['synthetic_validation']=self_test(base,cases,r['source']['sha256']);r['verification']='11 Python source/receipt synthetics; PowerShell not_run'
        if a.run:
            r.update(status='running',phase='host_requested',host_execution='requested',verification='incomplete; fake-process checker requested');journal.save(r)
            host=a.powershell_host.absolute();args=[str(host),'-NoProfile','-File',str(script),'-Source',str(snapshot),'-ExpectedAdapterHash',r['source']['sha256'],'-Result',str(pure)]
            r['host_run']=bounded.run_bounded(args,ROOT,work/'host',30,5,expected_executable={'path':str(host),'sha256':a.expected_host_sha256});r['host_execution']='attempted'
            if pure.exists():r['pure_receipt']=bounded.file_identity(pure,1024*1024);r['pure_result']=json.loads(pure.read_text(encoding='utf-8'))
            if r['host_run']['status']!='success':r['status']=r['host_run']['status'];raise ValueError('Fake-process checker failed; original exceptions retained')
            validate_result(base,r.get('pure_result'),cases,snapshot,r['source']['sha256']);r.update(status='success',verification=str(len(cases))+' pure scripted-process cases verified; real process queries not_run',host_execution='executed_complete')
        for path,key in ((SOURCE,'source'),(BASE,'base_source'),(snapshot,'source_snapshot'),(script,'script'),(UTILITY,'utility'),(PREDECESSOR,'predecessor'),(Path(__file__),'driver')):
            if bounded.file_identity(path)!=r[key]:r['status']='stale_input';raise ValueError('Pinned checker input changed')
    except BaseException as e:
        if r['status'] in ('success','running'):r['status']='failure'
        r['failure']=bounded.error_info(e)
    finally:
        r['phase']='finalized'
        try:journal.save(r)
        except BaseException as e:r['status']='failure';r['receipt_failure']=bounded.error_info(e)
    print(json.dumps({'receipt':str(work/'outer/result.json'),'status':r['status'],'verification':r.get('verification'),'failure':r.get('failure')}));return 0 if r['status']=='success' else 1


if __name__=='__main__':raise SystemExit(main())
