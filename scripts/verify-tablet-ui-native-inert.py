#!/usr/bin/env python3
"""Prepare or explicitly execute frozen UI transport guards against inert data.

Default mode and --self-test do not launch hosts. Root-only --run starts pinned
readiness then bounded checker children. Adapter top-level is never executed.
Wait-NaturalProgress uses declared inert deadline/status stubs and bounded real
Stopwatch waits. It cannot deliver engine callbacks.
"""
from __future__ import annotations
import argparse, ast, copy, hashlib, importlib.util, json, re, sys, uuid
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'scripts/tablet-ui-native-engine.ps1'
DATA=ROOT/'build/oct11-ui-verifier-inert-fixtures.json'
HEADER_SOURCE=ROOT/'scripts/verify-tablet-native-checkers.py'
UTILITY=ROOT/'scripts/verify-host-readiness.py'
FROZEN_ADAPTER_SHA='1946ef58a63eb4c2fd246bdbb456413b622b781eab8ec4cd02751f1706fa709b'
PINS={
 'source':'97342ccf0c24c4d4376c2a8982e50690f1b964a59f2edb4b936dd93253fe59a9',
 'data':'2fd92a8768a0bb253ddf9985128e4c29cfaeaef2c9cff8a00786f957897012aa',
 'header':'38eb4a117ad2696cc720dfa06648cefe7067c76e1c4e634257a397abbd4a3dd1',
 'utility':'0067128fa4754d582a3930415ec77991773475d936b204e3be560f4d9928e648'}
NAMES=('Throw-Outcome','Normal-Path','Required-Field','Assert-Text','Assert-Names','Assert-Int','Normalize-Bool','Fixed-Arguments','Assert-Transport','Assert-Parameters','Assert-LoadedProjects','Check-Native','Assert-World','Stage-Ready','Assert-RawResponse','Wait-NaturalProgress')
OP='tablet-ui-native.checkers.inert'
def require(value,message):
 if not value:raise ValueError(message)
def identity(path):
 raw=Path(path).read_bytes();require(len(raw)<=2*1024*1024,'Input exceeds 2 MiB')
 return dict(path=str(path),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
def bounded_module():
 require(identity(UTILITY)['sha256']==PINS['utility'],'Readiness utility changed')
 spec=importlib.util.spec_from_file_location('ui_inert_owned_bounds',UTILITY)
 value=importlib.util.module_from_spec(spec);sys.modules[spec.name]=value;spec.loader.exec_module(value)
 return value
def pinned_inputs():
 result={}
 for key,path in (('source',SOURCE),('data',DATA),('header',HEADER_SOURCE),('utility',UTILITY)):
  item=identity(path);require(item['sha256']==PINS[key],'Frozen '+key+' changed');result[key]=item
 return result
def literal_header():
 tree=ast.parse(HEADER_SOURCE.read_bytes())
 nodes=[n for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name)and t.id=='HEADER'for t in n.targets)]
 require(len(nodes)==1 and isinstance(nodes[0].value,ast.Constant) and type(nodes[0].value.value)is str,'Frozen header unavailable')
 return nodes[0].value.value
def psquote(value):
 require(type(value)is str and "'"not in value and '\n'not in value and '\r'not in value,'Unsafe fixed PS literal')
 return "'"+value+"'"
def psarray(values):return '@('+','.join(psquote(v)for v in values)+')'
def prepare_packet(frozen):
 require(frozen['adapter_sha256']==FROZEN_ADAPTER_SHA,'Original frozen fixture adapter identity differs')
 require(PINS['source']!=FROZEN_ADAPTER_SHA,'Current and frozen adapter identities must remain distinct')
 packet=copy.deepcopy(frozen)
 previous=packet['prefix_mutation']['previous'];response=packet['prefix_mutation']['response']
 require(previous['rows'][0].split('|')[5]=='before'and response['rows'][0].split('|')[5]=='after','Frozen prefix mutation changed')
 actual=sum(len(row.encode('ascii'))+1 for row in response['rows'])
 require(response['raw_bytes']==actual+1,'Expected single-byte prefix fixture defect differs')
 checksum=0
 for row in response['rows']:
  for byte in row.encode('ascii')+b'\n':checksum=(checksum*31+byte)%1000003
 require(response['checksum']==checksum,'Original prefix checksum is not fully resealed')
 repair=dict(pointer='/prefix_mutation/response/raw_bytes',original=response['raw_bytes'],prepared=actual,reason='before to after shortens one ASCII trace row by one byte; preserve the prefix rejection target')
 response['raw_bytes']=actual
 original=copy.deepcopy(response);original['raw_bytes']=repair['original']
 require(original==frozen['prefix_mutation']['response'],'Unexpected prepared mutation')
 remap=dict(pointer='/adapter_sha256',original=FROZEN_ADAPTER_SHA,prepared=PINS['source'],reason='Original fixture provenance is frozen; current adapter adds only tested receipt writers and final dispatch while extracted guard bodies remain unchanged')
 packet['adapter_sha256']=PINS['source']
 restored=copy.deepcopy(packet);restored['adapter_sha256']=FROZEN_ADAPTER_SHA;restored['prefix_mutation']['response']['raw_bytes']=repair['original']
 require(restored==frozen,'Unexpected prepared fixture changes beyond disclosed metadata and raw-byte repair')
 repair['adapter_provenance_remap']=remap
 return packet,repair

def registry(packet):
 require(packet['operation']=='tablet.ui-native.verifier.inert-fixtures'and packet['adapter_sha256']==PINS['source'],'Fixture identity differs')
 require(len(packet['valid'])==16 and len(packet['invalid'])==25,'Fixture coverage differs')
 cases=[]
 def add(name,body,status=None):
  cases.append((name,'return'if status is None else'checker_rejection',status,body))
 for item in packet['valid']:
  name=item['id'];stage=item['expected_stage'];body="$v=Fixture "+psquote(name)+";$n=Check-Native $v $v.action;"
  body+="if(($v|ConvertTo-Json -Depth 24 -Compress) -cne (Fixture "+psquote(name)+"|ConvertTo-Json -Depth 24 -Compress)){throw 'Raw fixture mutated'};"
  if stage:body+="if(-not(Stage-Ready $n.response "+psquote(stage)+")){throw 'Admitted stage not ready'}"
  add('data.accept.'+name,body)
 for item in packet['invalid']:
  add('data.reject.'+item['id'],"$v=Fixture "+psquote(item['id'])+";$null=Check-Native $v $v.action",item['expected_status'])
 add('data.accept.resealed-mutant-without-prior',"$v=Prefix 'response';$null=Check-Native $v $v.action")
 add('data.reject.resealed-prefix',"$v=Prefix 'previous';$null=Check-Native $v $v.action;$v=Prefix 'response';try{$null=Check-Native $v $v.action}catch{if($_.Exception.Message -cne 'Native UI prior scalar row changed'){throw [Exception]::new('Prefix fixture missed intended invariant: '+$_.Exception.Message)};throw}",'stale_input')
 add('codec.numeric-bools',"$v=Fixture 'load.ready';foreach($k in $BooleanFields){$v.$k=[int]$v.$k};$n=Check-Native $v $v.action;if(($n.codec.numeric_boolean_fields -join '|') -cne ($BooleanFields -join '|')){throw 'Boolean codec differs'}")
 add('codec.omitted-empty',"$v=Fixture 'load.ready';foreach($k in @('caseIds','rows')){$v.PSObject.Properties.Remove($k)};$n=Check-Native $v $v.action;if(($n.codec.omitted_empty_arrays -join '|') -cne 'caseIds|rows'){throw 'Empty array codec differs'}")
 for action in ('load','status','play','spawn','run0','run1','run2','run3','run4','run5','run6','stop'):
  add('params.accept.'+action,"Assert-Parameters 'BerylTabletUINative' @{token=$Token;action="+psquote(action)+"}")
 for name,value in (('extra',"@{token=$Token;action='run1';code='x'}"),('wrong-token',"@{token='foreign';action='run1'}"),('missing-action',"@{token=$Token}"),('direct-delete',"@{token=$Token;action='delete'}"),('forced-frame',"@{token=$Token;action='frame'}"),('run7',"@{token=$Token;action='run7'}")):
  add('params.reject.'+name,"Assert-Parameters 'BerylTabletUINative' "+value,'failure')
 add('params.reject.save',"Assert-Parameters 'Save' @{}",'failure')
 add('params.accept.inventory',"Assert-Parameters 'GetLoadedProjects' @{}")
 add('world.reject.foreign',"$v=Fixture 'load.ready';$v.world_absolute_path='C:/foreign/world.ent';Assert-World $v",'stale_input')
 add('projects.accept.exact',"Assert-LoadedProjects ([pscustomobject]@{'Loaded Projects'=@($ProjectId,'ArmaReforger','core')})")
 add('projects.reject.foreign',"Assert-LoadedProjects ([pscustomobject]@{'Loaded Projects'=@($ProjectId,'foreign')})",'stale_input')
 add('raw.accept.exact',"Assert-RawResponse (Reply);Assert-Transport (Reply) 'BerylTabletUINative'")
 add('raw.reject.mismatch',"$v=Reply;$v.Raw='{}';Assert-RawResponse $v",'failure')
 add('transport.reject.numeric-ok',"$v=Reply;$v.Ok=1;Assert-Transport $v 'BerylTabletUINative'",'failure')
 add('stage.reject.unregistered',"$null=Stage-Ready (Fixture 'spawn.ready') 'delete'",'failure')
 for stage in ('spawn','run0','run1','run2','run3','run4','run5','run6'):
  name=stage+'.ready'
  add('stage.refuse-wrong-phase.'+stage,"$v=Fixture "+psquote(name)+";$v.phase=0;if(Stage-Ready $v "+psquote(stage)+"){throw 'Wrong phase advanced'}")
  add('stage.reject-outside-play.'+stage,"$v=Fixture "+psquote(name)+";$v.in_play_mode=$false;$null=Stage-Ready $v "+psquote(stage),'failure')
 for window,prefix in (('first','first.native-progress'),('reopen','reopen.native-progress')):
  body="$v=Fixture "+psquote(prefix)+";$script:lastUIProgress=$v;$script:stubReplies=@($v);$script:stubIndex=0;$null=Wait-NaturalProgress "+psquote(window)+";"
  body+="Assert-WaitReceipt "+psquote(window)+" 1"
  add('wait.accept.'+window,body)
  body="$v=Fixture "+psquote(prefix)+";$script:lastUIProgress=$v;$first=($v|ConvertTo-Json -Depth 24|ConvertFrom-Json);"
  field='first_progress_ready'if window=='first'else'reopen_progress_ready'
  body+="$first."+field+"=$false;$script:stubReplies=@($first,$v);$script:stubIndex=0;$null=Wait-NaturalProgress "+psquote(window)+";Assert-WaitReceipt "+psquote(window)+" 2"
  add('wait.accept.delayed.'+window,body)
 add('wait.reject.unknown',"$null=Wait-NaturalProgress 'unknown'",'failure')
 add('wait.reject.missing-prior',"$null=Wait-NaturalProgress 'first'",'failure')
 add('wait.reject.wrong-prior',"$script:lastUIProgress=Fixture 'spawn.ready';$null=Wait-NaturalProgress 'first'",'failure')
 add('wait.reject.lost-window',"$v=Fixture 'first.native-progress';$script:lastUIProgress=$v;$v=($v|ConvertTo-Json -Depth 24|ConvertFrom-Json);$v.action_count=3;$script:stubReplies=@($v);$script:stubIndex=0;$null=Wait-NaturalProgress 'first'",'failure')
 add('wait.reject.deadline',"$script:lastUIProgress=Fixture 'first.native-progress';$script:stubDeadlineFailure=$true;$null=Wait-NaturalProgress 'first'",'timeout')
 require(len({v[0]for v in cases})==len(cases),'Duplicate inert case')
 require(len(cases)<=128,'Case bound exceeded')
 return cases
STUBS=r"""
function Fixture([string]$Id) {
 $entries=@($packet.valid)+@($packet.invalid)
 $found=@($entries|Where-Object {$_.id -ceq $Id})
 if($found.Count -ne 1){throw 'Unknown fixture'}
 return ($found[0].response|ConvertTo-Json -Depth 24|ConvertFrom-Json)
}
function Prefix([string]$Name) {
 return ($packet.prefix_mutation.$Name|ConvertTo-Json -Depth 24|ConvertFrom-Json)
}
function Reply {
 $v=Fixture 'load.ready'
 return [pscustomobject]@{Ok=$true;Function='BerylTabletUINative';ErrorCode='Ok';Response=$v;Raw=($v|ConvertTo-Json -Depth 24 -Compress)}
}
# Explicit inert stubs; no process/engine/session/listener operation.
function Assert-Deadline {
 if($script:stubDeadlineFailure -or $clock.ElapsedMilliseconds -gt 10000){
  Throw-Outcome 'timeout' 'Inert declared deadline'
 }
}
function Invoke-Probe([string]$Action) {
 if($Action -cne 'status'){throw 'Inert probe forbids mutations'}
 if($script:stubIndex -ge $script:stubReplies.Count){throw 'Inert status queue exhausted'}
 $v=$script:stubReplies[$script:stubIndex];$script:stubIndex++
 return $v
}
function Assert-WaitReceipt([string]$Window,[int]$Polls) {
 if($record.natural_progress_windows.Count -ne 1){throw 'Missing inert wait'}
 $v=$record.natural_progress_windows[0]
 if($v.window -cne $Window -or $v.status -cne 'completed' -or $v.required_minimum_wall_ms -ne 600 -or
    $v.wait_elapsed_ms -lt 600 -or $v.end_wait_total_ms-$v.begin_total_ms -lt 600 -or
    $v.clock_source -cne 'Stopwatch' -or $v.stopwatch_frequency -ne [Diagnostics.Stopwatch]::Frequency -or
    $v.wait_end_ticks -lt 0.6*$v.stopwatch_frequency -or $v.polls -ne $Polls -or $v.mutation_requests -ne 0 -or
    $script:stubIndex -ne $Polls){throw 'Inert wall wait/status-only ledger differs'}
}
"""
def fixture_script(cases,packet):
 header=literal_header()
 header=header.replace("param([string]$Source,[string]$ExpectedAdapterHash,[string]$Result)","param([string]$Source,[string]$ExpectedAdapterHash,[string]$Result,[string]$FixturePath,[string]$ExpectedFixtureHash)")
 header=header.replace("$suiteProfile='sparkos.tablet.native-init-stowed.source.v1'","$suiteProfile='sparkos.tablet.ui-native.n1b-n3.source.v1'")
 header=header.replace("$ProjectId='BerylTabletNativeCheckProbe'","$ProjectId='BerylTabletUINativeN1bPrototype'")
 header=header.replace("C:/fixture/worlds/BerylTabletNativeStowed.ent",packet['expected_world'])
 header=header.replace("operation='tablet-native.checkers.inert'","operation='"+OP+"'")
 header=header.replace("$script:lastLoadProgress=$null","$script:lastLoadProgress=$null;$script:lastUIProgress=$null;$clock=[Diagnostics.Stopwatch]::StartNew();$script:stubReplies=@();$script:stubIndex=0;$script:stubDeadlineFailure=$false")
 header=header.replace("$record=@{status='failure';expected_world=","$record=@{status='failure';trace_checks=@();natural_progress_windows=@();expected_world=")
 header=header.replace("failure=$null}\nfunction Save-Receipt","failure=$null;inert_stubs=@('Assert-Deadline','Invoke-Probe');wait_scope='real bounded wall wait; synthetic status only; no callbacks'}\nfunction Save-Receipt")
 start=header.index('function Native(');end=header.index('try {\n Save-Receipt',start)
 header=header[:start]+STUBS+'\n'+header[end:]
 # Pin/load the fixture before executing any cases.
 marker=" $bytes=[IO.File]::ReadAllBytes($Source)"
 insertion=" $fixtureBytes=[IO.File]::ReadAllBytes($FixturePath)\n if($fixtureBytes.Length -gt 2MB -or [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($fixtureBytes)).ToLowerInvariant() -cne $ExpectedFixtureHash){throw 'Frozen fixture identity differs'}\n $packet=([Text.UTF8Encoding]::new($false,$true).GetString($fixtureBytes)|ConvertFrom-Json)\n"
 require(header.count(marker)==1,'Source marker changed');header=header.replace(marker,insertion+marker)
 actions=['Case '+psquote(name)+' '+psquote(outcome)+' '+('$null'if status is None else psquote(status))+' {'+body+'}'for name,outcome,status,body in cases]
 booleans=('addon_world_resolved','world_path_resolved','resource_name_resolved','module_present','api_present','module_open_requested','module_open_accepted','load_accepted','world_matches','edit_mode','game_mode','in_play_mode','world_present','game_world_present','actions_ready','stop_requested','outside_domain','first_progress_ready','reopen_progress_ready','final_focused')
 for marker,value in (('__EXPECTED__',psarray([c[0]for c in cases])),('__NAMES__',psarray(NAMES)),('__BOOLEANS__',psarray(booleans)),('__COUNT__',str(len(cases))),('__CASES__','\n'.join(actions))):header=header.replace(marker,value)
 require(not re.search(r'__[A-Z_]+__',header)and len(header.encode())<=256*1024,'Unresolved header or size bound')
 require('$record.trace_checks'not in STUBS,'Inert stubs must not forge source checks')
 require(not set(NAMES)&{'Run-Stage','Invoke-Call','Invoke-Probe','Assert-Deadline','Assert-OwnedSession','Wait-Listener','Open-ReadLease','Read-StartupIdentity'},'Unsafe source extraction')
 return header
def validate_result(value,cases,source,sha):
 require(type(value)is dict and type(value.get('schema_version'))is int and value['schema_version']==1,'Malformed receipt')
 require(value.get('operation')==OP and value.get('status')=='success'and value.get('failure')is None,'Checker execution not successful')
 require(value.get('source')==str(source)and value.get('source_sha256')==sha and value.get('function_names')==list(NAMES),'Source/helper identity differs')
 ids=[c[0]for c in cases]
 require(value.get('expected_case_ids')==ids and value.get('completed_case_ids')==ids and value.get('complete_expected_case_set')is True,'Incomplete/reordered cases')
 for key,expected in (('expected_cases',len(cases)),('case_count',len(cases)),('passed',len(cases)),('failed',0)):
  require(type(value.get(key))is int and value[key]==expected,'Incomplete count')
 require(value.get('inert_stubs')==['Assert-Deadline','Invoke-Probe']and value.get('wait_scope')=='real bounded wall wait; synthetic status only; no callbacks','Stub disclosure differs')
 require(type(value.get('cases'))is list and len(value['cases'])==len(cases),'Missing cases')
 for row,(name,outcome,status,_)in zip(value['cases'],cases):
  require(type(row)is dict and set(row)=={'id','status','expected','actual','expected_status','actual_status','original_exception'},'Case fields differ')
  require(row['id']==name and row['status']=='success'and row['expected']==outcome and row['actual']==outcome and row['expected_status']==status,'Unexpected case')
  if outcome=='return':require(row['actual_status']is None and row['original_exception']is None,'Return contains exception')
  else:
   error=row['original_exception'];require(row['actual_status']==status and type(error)is dict and set(error)=={'type','message','fully_qualified_error_id','position','script_stack'}and error['type']=='System.InvalidOperationException'and type(error['message'])is str and bool(error['message']),'Rejection lost original exception')
 require(all(value.get(f)=='not_run'for f in('compiler_execution','engine_execution','adapter_top_level','actual_process_stop','native_listener_inventory')),'Unsupported execution claim')
def checker_argv(host,script,source,pure,data,prepared):
 require(prepared['source']['sha256']==PINS['source'],'Prepared adapter identity differs')
 derived=prepared['data']['sha256']
 require(type(derived)is str and re.fullmatch(r'[0-9a-f]{64}',derived)is not None and derived!=PINS['data'],'Prepared fixture must have its distinct derived identity')
 return [str(host),'-NoProfile','-NonInteractive','-File',str(script),'-Source',str(source),'-ExpectedAdapterHash',prepared['source']['sha256'],'-Result',str(pure),'-FixturePath',str(data),'-ExpectedFixtureHash',derived]

def self_test(cases,source,frozen):
 good=dict(schema_version=1,operation=OP,status='success',failure=None,source=str(source),source_sha256=PINS['source'],function_names=list(NAMES),expected_case_ids=[c[0]for c in cases],completed_case_ids=[c[0]for c in cases],complete_expected_case_set=True,expected_cases=len(cases),case_count=len(cases),passed=len(cases),failed=0,inert_stubs=['Assert-Deadline','Invoke-Probe'],wait_scope='real bounded wall wait; synthetic status only; no callbacks')
 good.update({f:'not_run'for f in('compiler_execution','engine_execution','adapter_top_level','actual_process_stop','native_listener_inventory')})
 good['cases']=[dict(id=name,status='success',expected=outcome,actual=outcome,expected_status=status,actual_status=status,original_exception=None if status is None else dict(type='System.InvalidOperationException',message='Synthetic rejection',fully_qualified_error_id='synthetic',position='',script_stack=''))for name,outcome,status,_ in cases]
 validate_result(copy.deepcopy(good),cases,source,PINS['source']);checks=['synthetic.receipt.accept']
 for name,change in (
 ('missing-case',lambda v:v['cases'].pop()),('wrong-source',lambda v:v.update(source_sha256='0'*64)),
 ('missing-stubs',lambda v:v.update(inert_stubs=[])),('wrong-expected-count',lambda v:v.update(expected_cases=True)),
 ('reordered-completion',lambda v:v['completed_case_ids'].reverse()),('missing-complete',lambda v:v.update(complete_expected_case_set=False)),
 ('claimed-engine',lambda v:v.update(engine_execution='executed')),('failed-host',lambda v:v.update(status='timeout')),
 ('failure-retained',lambda v:v.update(failure={'message':'failed'})),('generic-exception',lambda v:next(r for r in v['cases']if r['original_exception'])['original_exception'].update(type='System.Exception'))):
  value=copy.deepcopy(good);change(value)
  try:validate_result(value,cases,source,PINS['source'])
  except ValueError:checks.append('synthetic.receipt.reject.'+name)
  else:raise ValueError('Mutant receipt admitted: '+name)
 prepared={'source':{'sha256':PINS['source']},'data':{'sha256':'d'*64}}
 argv=checker_argv('host with spaces.exe','checks.ps1','source.ps1','receipt.json','derived.json',prepared)
 require(argv[argv.index('-ExpectedFixtureHash')+1]=='d'*64 and PINS['data']not in argv,'Source packet hash leaked into derived fixture argument')
 require(argv[argv.index('-ExpectedAdapterHash')+1]==PINS['source']and argv[0]=='host with spaces.exe','Explicit argv/source identity differs')
 packet,repair=prepare_packet(frozen)
 require(packet['adapter_sha256']==PINS['source']and frozen['adapter_sha256']==FROZEN_ADAPTER_SHA and repair['adapter_provenance_remap']['original']==FROZEN_ADAPTER_SHA,'Frozen/current provenance separation differs')
 bad_fixture=copy.deepcopy(frozen);bad_fixture['adapter_sha256']='0'*64
 try:prepare_packet(bad_fixture)
 except ValueError:pass
 else:raise ValueError('Wrong original fixture identity admitted')
 checks.append('arguments.distinct-source-derived-and-frozen-identities')
 for name,field,value in (('old-source-pin','source',FROZEN_ADAPTER_SHA),('untransformed-data','data',PINS['data']),('malformed-data','data','invalid')):
  broken=copy.deepcopy(prepared);broken[field]['sha256']=value
  try:checker_argv('host','checks','source','receipt','data',broken)
  except ValueError:checks.append('arguments.reject.'+name)
  else:raise ValueError('Malformed checker argv identity admitted: '+name)
 return dict(scope='Python receipt and actual checker-argv construction tests; not PowerShell execution',passed=len(checks),expected_case_ids=checks,complete_expected_case_set=True)
def main():
 p=argparse.ArgumentParser(description=__doc__);m=p.add_mutually_exclusive_group()
 m.add_argument('--run',action='store_true');m.add_argument('--self-test',action='store_true')
 p.add_argument('--powershell-host',type=Path);p.add_argument('--expected-host-sha256')
 a=p.parse_args()
 if a.run and not(a.powershell_host and a.expected_host_sha256):p.error('--run requires pinned host path and hash')
 bounded=bounded_module();inputs=pinned_inputs()
 frozen=json.loads(DATA.read_bytes());packet,repair=prepare_packet(frozen);cases=registry(packet);fixture=fixture_script(cases,packet).encode();prepared_raw=(json.dumps(packet,indent=2)+'\n').encode('utf8')
 work=ROOT/'build'/('tablet-ui-native-inert-'+uuid.uuid4().hex);work.mkdir()
 journal=bounded.Journal(work/'outer');source=work/'source.ps1';script=work/'checks.ps1';data=work/'fixtures.json';pure=work/'checker-result.json'
 record=dict(schema_version=1,operation='tablet-ui-native.checkers.driver',status='running',phase='preparing',failure=None,inputs=inputs,driver=identity(Path(__file__)),expected_case_ids=[c[0]for c in cases],expected_cases=len(cases),scope='inert source helpers with synthetic status/deadline stubs; not engine semantics',fixture_repair=repair)
 record.update({f:'not_run'for f in('host_execution','compiler_execution','engine_execution','adapter_top_level','engine_session_inventory','actual_process_stop')})
 try:
  journal.save(record)
  for path,raw in ((source,SOURCE.read_bytes()),(script,fixture),(data,prepared_raw)):
   with path.open('xb')as out:require(out.write(raw)==len(raw),'Short source write')
  record['prepared']={key:identity(path)for key,path in(('source',source),('script',script),('data',data))}
  require(record['prepared']['source']['sha256']==PINS['source']and record['prepared']['data']['sha256']==hashlib.sha256(prepared_raw).hexdigest(),'Snapshot mismatch')
  record.update(status='success',phase='prepared_not_executed',verification='source preparation only')
  if a.self_test or a.run:record['synthetic_validation']=self_test(cases,source,frozen)
  journal.save(record)
  if a.run:
   host=a.powershell_host.absolute();hostid=dict(path=str(host),sha256=a.expected_host_sha256)
   record.update(status='running',phase='readiness_requested',host_execution='requested');journal.save(record)
   record['readiness']=bounded.run_bounded([str(host),'-NoProfile','-NonInteractive','-Command',"Write-Output 'BERYL_FIXED_HOST_PROBE'"],ROOT,work/'host-readiness',15,5,expected_executable=hostid,expected_stdout=bounded.MARKER)
   if record['readiness']['status']!='success':
    record['status']=record['readiness']['status'];raise ValueError('Pinned literal host readiness failed; inert checker not started')
   require(pinned_inputs()==inputs,'Inputs changed before checker')
   record.update(phase='checker_requested');journal.save(record)
   argv=checker_argv(host,script,source,pure,data,record['prepared']);record['host_arguments']=argv;journal.save(record)
   record['host_run']=bounded.run_bounded(argv,ROOT,work/'host-checker',45,5,expected_executable=hostid)
   record['host_execution']='attempted'
   if pure.exists():
    record['checker_receipt']=identity(pure);record['checker_result']=json.loads(pure.read_bytes())
   if record['host_run']['status']!='success':
    record['status']=record['host_run']['status'];raise ValueError('Inert host failed; preserved case exceptions')
   validate_result(record.get('checker_result'),cases,source,PINS['source'])
   record.update(status='success',phase='inert_complete',verification=str(len(cases))+' inert PowerShell source-helper cases executed',host_execution='executed_complete')
  require(pinned_inputs()==inputs,'Frozen source changed during gate')
  require(identity(Path(__file__))==record['driver'],'Driver changed during gate')
  for key,path in(('source',source),('script',script),('data',data)):require(identity(path)==record['prepared'][key],'Prepared '+key+' changed')
 except BaseException as error:
  if record['status']in('running','success'):record['status']='failure'
  record['failure']=bounded.error_info(error)
 finally:
  journal.save(record)
 print(json.dumps(dict(status=record['status'],receipt=str(work/'outer/result.json'),verification=record.get('verification'),expected=len(cases),failure=record['failure'])))
 return 0 if record['status']=='success'else 1
if __name__=='__main__':raise SystemExit(main())
