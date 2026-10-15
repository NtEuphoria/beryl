#!/usr/bin/env python3
"""Bounded passive source audit and AST-extracted synthetic N1a receipt checks.

No root-runner imports, PowerShell, hosts, listeners, compilers or engines.
Physical source identity and synthetic receipt interpretation are separate gates.
"""
from __future__ import annotations
import argparse,ast,copy,hashlib,json,re,types,uuid
from decimal import Decimal,InvalidOperation
from pathlib import Path
import sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'scripts/verify-tablet-real-services.py'
ADAPTER=ROOT/'scripts/tablet-real-services-engine.ps1'
PREDECESSOR=ROOT/'scripts/tablet-native-leased-startup-engine.ps1'
PACKAGE=ROOT/'packages/sparkos/tablet-real-service-probe'
NAMES=('normalized_native','validate_init_rows','typed_equal','validate_read_lease','validate_startup_identity','validate_runtime')
SOURCE_SHA='74aed85740e8d72b5c187eae9b537fffb921b90ec24ac0002500379897e8cd65'
WIRE_SHA='80abd295e0652346df82083ade1409731f3f0b3508a8cd75f09b6afe39920766'
BASE_SHA='a7af515454f543babde755e9fb19fe4e363acea93edd2240fab76f492cb38306'

class Rejected(ValueError):
 def __init__(self,detail,status='failure'):
  super().__init__(detail);self.status=status

def require(condition,detail,status='failure'):
 if not condition:raise Rejected(detail,status)

def digest(data):return hashlib.sha256(data).hexdigest()
def identity(path):
 raw=Path(path).read_bytes();return {'path':str(path),'bytes':len(raw),'sha256':digest(raw)}

def ps_functions(data):
 """Extract brace-delimited source function bodies without evaluating PowerShell."""
 text=data.decode('utf8').replace('\r\n','\n');out={}
 for found in re.finditer(r'(?m)^function ([A-Za-z][A-Za-z0-9-]*)(?:\(|\s)',text):
  name=found[1];require(name not in out,'Duplicate PowerShell function')
  begin=text.find('{',found.end());require(begin>=0,'Missing function body')
  i=begin;depth=0;quote=None;comment=False;block=False
  while i<len(text):
   ch=text[i];pair=text[i:i+2]
   if comment:
    if ch=='\n':comment=False
   elif block:
    if pair=='#>':block=False;i+=1
   elif quote:
    if ch=='`' and quote=='"':i+=1
    elif ch==quote:
     if quote=="'" and text[i+1:i+2]=="'":i+=1
     else:quote=None
   elif pair=='<#':block=True;i+=1
   elif ch=='#':comment=True
   elif ch in ('"',"'"):quote=ch
   elif ch=='{':depth+=1
   elif ch=='}':
    depth-=1
    if depth==0:break
   i+=1
  require(depth==0 and not quote and not block,'Unterminated PowerShell function')
  out[name]=text[found.start():i+1]
 return out

def source_relation(actual,prior):
 require(digest(prior)==BASE_SHA,'Frozen predecessor source changed','stale_input')
 old,new=ps_functions(prior),ps_functions(actual)
 require(set(old)==set(new),'Unexpected PowerShell helper addition/removal')
 required_changes={'Assert-Parameters','Check-Native','Assert-World','Stage-Ready','Run-Stage','Invoke-Probe','Invoke-Call'}
 count_changes={'Read-LeaseBasis','Open-ReadLease','Assert-HeldReadLease','Assert-FastInputs'}
 results=[]
 for name in old:
  expected=old[name]
  if name in count_changes:
   expected=re.sub(r'\b93\b','99',expected);expected=re.sub(r'\b98\b','104',expected)
  if name in required_changes:
   require(new[name]!=old[name],'N1-specific helper unexpectedly unchanged: '+name)
   policy='N1 function reviewed separately'
  else:
   require(new[name]==expected,'Protected predecessor function changed: '+name)
   policy='only 93/98 to 99/104 counts'if name in count_changes else'byte-identical normalized function'
  results.append({'name':name,'policy':policy,'prior_sha256':digest(old[name].encode()),'current_sha256':digest(new[name].encode())})
 oldtail=prior.decode('utf8').replace('\r\n','\n');newtail=actual.decode('utf8').replace('\r\n','\n')
 oldcleanup=oldtail[oldtail.index('    # Release every acquired source handle'):]
 newcleanup=newtail[newtail.index('    # Release every acquired source handle'):]
 expected=oldcleanup.replace('native_stowed_transport_complete','native_services_transport_complete')
 require(newcleanup==expected,'Final cleanup changed beyond the completion stage identity')
 return {'functions':results,'function_count':len(results),'cleanup':'unchanged except completion stage identity',
         'startup_helpers':'Read-StartupIdentity/Wait-StartupIdentity unchanged',
         'PowerShell_syntax':'not_parsed_or_executed; passive brace extraction only'}

def pure_package(path):
 """Copy only pure definitions/constants; skip all imports, entrypoints and mains."""
 raw=path.read_bytes();tree=ast.parse(raw,filename=str(path));chosen=[]
 for node in tree.body:
  if isinstance(node,(ast.FunctionDef,ast.ClassDef)):
   if isinstance(node,ast.FunctionDef)and node.name=='main':continue
   chosen.append(node)
  elif isinstance(node,ast.Assign):
   require(all(isinstance(t,ast.Name)for t in node.targets),'Unexpected pure package target')
   chosen.append(node)
 env={'__file__':str(path),'__name__':'ast_extracted_pure_fixture','Path':Path,'copy':copy,'hashlib':hashlib,
      'json':json,'re':re,'types':types,'Decimal':Decimal,'InvalidOperation':InvalidOperation}
 exec(compile(ast.Module(body=chosen,type_ignores=[]),str(path),'exec'),env)
 return types.SimpleNamespace(**env)

def load_functions(env,raw=None):
 if raw is None:raw=SOURCE.read_bytes()
 tree=ast.parse(raw,filename=str(SOURCE))
 chosen=[n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name in NAMES]
 require([n.name for n in chosen]==list(NAMES),'Registered AST function set changed')
 forbidden={'module','main','run','capture_adapter','capture_engine_logs','streamed_identity','Popen','subprocess','exec','eval','__import__'}
 for node in ast.walk(ast.Module(body=chosen,type_ignores=[])):
  if isinstance(node,ast.Call):
   name=node.func.id if isinstance(node.func,ast.Name)else node.func.attr if isinstance(node.func,ast.Attribute)else''
   require(name not in forbidden,'Unsafe root function call during extraction: '+name)
 exec(compile(ast.Module(body=chosen,type_ignores=[]),str(SOURCE),'exec'),env)
 return env

def fixture(env,wire,oracle):
 addon=ROOT/'build/synthetic-n1-transport-addon';work=ROOT/'build/synthetic-n1-transport-work'
 adapter=ADAPTER;engine=Path('C:/Program Files (x86)/Steam/steamapps/common/Arma Reforger Tools/Workbench/ArmaReforgerWorkbenchSteamDiag.exe')
 toolroot=Path('C:/Users/moham/Desktop/reforger-workbench-plugin')
 basis={};manifest={'schema_version':1,'profile':wire.PROFILE,'files':{}}
 def fake_id(path,sha='d'*64,size=16):
  item={'path':str(path),'bytes':size,'sha256':sha};basis[str(Path(path).resolve())]=item;return item
 for i in range(99):
  name=f'scripts/Game/Synthetic{i}.c';manifest['files'][name]='d'*64;fake_id(addon/name)
 manifest_identity=fake_id(work/'input-manifest.json','e'*64,200)
 tracked={str(adapter):fake_id(adapter,'b'*64,300)}
 for name in ('Find-Workbench.ps1','Invoke-WorkbenchRpc.ps1'):
  path=toolroot/'scripts'/name;tracked[str(path)]=fake_id(path,'c'*64,400)
 engine_id=fake_id(engine,'a'*64,67576376)
 logfile=fake_id(work/'raw.log','f'*64,3)
 def synthetic_identity(path):
  require(str(Path(path).resolve())in basis,'Unregistered synthetic file lookup')
  return copy.deepcopy(basis[str(Path(path).resolve())])
 env.update(addon=addon,work=work,adapter=adapter,engine=engine,toolroot=toolroot,record={'engine_input':engine_id})
 env['h']=types.SimpleNamespace(require=require,identity=synthetic_identity,parent_directories=lambda _:['scripts','scripts/Game'])
 env['mod']=types.SimpleNamespace(parse=lambda raw:json.loads(raw))
 expected={'schema_version':1,'profile':wire.PROFILE,'token':'a'*64,'source_sha256':'b'*64,'source_contract_sha256':SOURCE_SHA,'wire_contract_sha256':WIRE_SHA}
 typed={key:oracle.PROFILE if key=='profile'else expected[key]for key in oracle.IDENTITY_KEYS}
 rows=wire.encode(oracle.evaluate([True,True],typed),expected)
 init=[f"{i+1}|{i//2+1}|{('init.before','init.after')[i%2]}|1|1|1|1|1|1|{0 if i<2 else 1}|{0 if i<2 else 1}|0|0|{8 if i%2 else 0}|1|1"for i in range(4)]
 texts=('world_path','current_project','addon_world_path','world_absolute_path','resource_name','resource_path','resource_absolute_path')
 flags=('addon_world_resolved','world_path_resolved','resource_name_resolved','module_present','api_present','module_open_requested','module_open_accepted','load_accepted','world_matches','world_present','game_world_present')
 def native(action):
  n=dict(expected,action=action,status='ready'if action in('load','play')else'pending',failure='',outside_domain=False,
         phase=0 if action in('load','play')else 2,executed=0,failures=0,owner_count=0 if action in('load','play')else 2,
         row_count=0,checksum=0,raw_bytes=0,init_count=0 if action in('load','play')else 4,
         init_rows=[]if action in('load','play')else copy.deepcopy(init),init_checksum=0 if action in('load','play')else wire.checksum(init),
         caseIds=[],rows=[],edit_mode=action in('load','stop'),game_mode=action not in('load','stop'),in_play_mode=action not in('load','stop'),
         actions_ready=action in('run','stop'),stop_requested=action=='stop')
  n.update({k:''for k in texts});n.update({k:True for k in flags})
  n.update({k:1 for k in('load_requested','load_submitted','load_entered','load_resumed','load_returned')})
  for k in('addon_world_path','world_absolute_path','resource_absolute_path'):n[k]=str(addon/'worlds/BerylTabletRealServicesN1a.ent')
  n.update(world_path='worlds/BerylTabletRealServicesN1a.ent',current_project='./addons/data/ArmaReforger.gproj',resource_name='{BE71571A20261010}worlds/BerylTabletRealServicesN1a.ent',resource_path='worlds/BerylTabletRealServicesN1a.ent')
  if action in('run','stop'):
   n.update({k:copy.deepcopy(rows[k])for k in('executed','row_count','checksum','caseIds','rows')})
   n['raw_bytes']=sum(len(s.encode('ascii'))+1 for s in n['rows'])
  if action=='stop':n.update(phase=4,status='complete')
  return n
 stages=[];ledger=[]
 def rpc(stage,function,params,response,elapsed):
  n,codec=env['normalized_native'](response)if function!='GetLoadedProjects'else(None,None)
  entry={'stage':stage,'function':function,'params':params,'elapsed_ms':elapsed,'duration_ms':10,'timeout_ms':1000,'failure':None,'failure_kind':None,
         'result':{'Ok':True,'Function':function,'ErrorCode':'Ok','Raw':json.dumps(response),'Response':copy.deepcopy(response)}}
  if n is not None:entry.update(normalized_response=n,codec=codec)
  ledger.append(entry)
 rpc('loaded_projects','GetLoadedProjects',{}, {'Loaded Projects':['BerylTabletRealServicesN1aPrototype','ArmaReforger','core']},100)
 for index,stage in enumerate(('load','play','spawn','run','stop')):
  response=native(stage);rpc(stage,'BerylTabletRealServicesNative',{'token':expected['token'],'action':stage},response,200+index*100)
  stages.append({'action':stage,'status':'completed','polls':0,'response':response,'elapsed_ms':10})
 pid=123;ticks=639272520000000000;stamp='2026-10-11T10:00:00.0000000Z'
 # Compute the exact .NET ticks rather than assuming Unix units.
 import datetime
 instant=datetime.datetime(2026,10,11,10)
 ticks=((instant.toordinal()-1)*86400+10*3600)*10000000
 checks=[{'site':'startup.identity','process_id':pid,'start_ticks':ticks,'executable':str(engine),'elapsed_ms':2},
         {'site':'port.check','process_id':pid,'start_ticks':ticks,'executable':str(engine),'elapsed_ms':4}]
 for entry in ledger:
  for prefix,offset in(('before.',-1),('after.',9)):
   checks.append({'site':prefix+entry['function'],'process_id':pid,'start_ticks':ticks,'executable':str(engine),'elapsed_ms':entry['elapsed_ms']+offset})
 argv=['-gproj',str(addon/'addon.gproj'),'-noOpenLastResource','-scriptAuthorizeAll','-forceUpdate']
 startup={'mechanism':'owned_tablet_real_services_n1a','argv':argv,'working_directory':'C:/fixture','use_shell_execute':False,'create_no_window':True,'window_style':'Hidden',
          'launch_returned':True,'polls':0,'process_id':pid,'identity_status':'verified','identity_polls':0,'identity_start_ticks':ticks,'identity_start_ticks_unit':'dotnet_datetime_0001_utc_100ns',
          'identity_start_time':stamp,'identity_started_ms':1,'identity_completed_ms':2,'identity_duration_ms':1,'identity_checks':[{'attempt':0,'elapsed_ms':2,'process_id':pid,'start_ticks':ticks,
          'start_ticks_unit':'dotnet_datetime_0001_utc_100ns','module_present':True,'raw_path':str(engine),'normalized_path':str(engine).replace('/','\\').rstrip('\\'),'status':'verified','query_error':None}]}
 lease={'schema_version':1,'policy':'FileMode.Open/FileAccess.Read/FileShare.Read','status':'released','acquisition_status':'complete','release_status':'complete',
        'expected_count':104,'opened_count':104,'released_count':104,'entries':[],'errors':[],'open_started_ms':320,'open_completed_ms':330,'open_duration_ms':10,
        'close_started_ms':620,'close_completed_ms':630,'close_duration_ms':10,'fast_checks':[],'fast_check_count':6,'full_checks_with_handles':1,'post_release_full_check':True,
        'byte_identity':'hashed_while_held; fast_checks_length_and_readability_only','native_open_dispose_not_hard_cancelled':True}
 add_entries=[(addon/name,'addon')for name in manifest['files']]+[(adapter,'adapter'),(Path(manifest_identity['path']),'manifest')]+[(toolroot/'scripts'/name,'plugin')for name in('Find-Workbench.ps1','Invoke-WorkbenchRpc.ps1')]+[(engine,'engine')]
 for path,kind in add_entries:
  item=synthetic_identity(path);lease['entries'].append({'path':str(path),'kind':kind,'expected_sha256':item['sha256'],'sha256':item['sha256'],'bytes':item['bytes'],'status':'verified_held','release_status':'released'})
 for call in ledger[3:]:
  for ms in(call['elapsed_ms']-1,call['elapsed_ms']+9):lease['fast_checks'].append({'elapsed_ms':ms,'duration_ms':1,'held_count':104,'file_count':99,'directory_count':2,'bytehash':'not_reexecuted; read-sharing leases held'})
 r={'schema_version':1,'elapsed_ms':1000,'status':'success','stage':'native_services_transport_complete','failure':None,'evidence_errors':[],'cleanup_errors':[],'cleanup':'owned_process_stopped',
    'profile':wire.PROFILE,'token':expected['token'],'source_sha256':expected['source_sha256'],'source_contract_sha256':SOURCE_SHA,'project_id':'BerylTabletRealServicesN1aPrototype',
    'engine_sha256':engine_id['sha256'],'engine_bytes':engine_id['bytes'],'engine_path':str(engine),'engine_version':'1.8.0.13','adapter_sha256':tracked[str(adapter)]['sha256'],
    'input_manifest':{'path':manifest_identity['path'],'sha256':manifest_identity['sha256']},'staged_inputs':manifest,'arguments':argv,'startup':startup,
    'session':{'process_id':pid,'start_ticks':ticks,'executable':str(engine),'project':str(addon),'reused':False,'start_time':stamp},
    'raw_log_observation':'snapshot_after_confirmed_owned_exit','stages':stages,'rpcs':ledger,'completion':copy.deepcopy(stages[-1]['response']),
    'session_checks':checks,'port_checks':[{'elapsed_ms':3,'listening':True,'owning_process':pid}],'port_query_errors':[],
    'tools':{name:tracked[str(toolroot/'scripts'/name)]['sha256']for name in('Find-Workbench.ps1','Invoke-WorkbenchRpc.ps1')},
    'raw_logs':[{'retained':logfile['path'],'bytes':logfile['bytes'],'sha256':logfile['sha256']}],'read_lease':lease}
 r.update({k:'not_run'for k in('save','physical_ui_input','multiplayer','visual_review','policy_changes')})
 return r,expected,manifest,manifest_identity,tracked,native,init

HOST_NAMES=('Throw-Outcome','Normal-Path','Required-Field','Assert-Text','Assert-Names','Assert-Int','Normalize-Bool','Fixed-Arguments',
            'Assert-Transport','Assert-Parameters','Assert-LoadedProjects','Check-Native','Assert-World','Stage-Ready','Assert-RawResponse')

def prepare_host(out,native,adapter_bytes=None,source_bytes=None):
 predecessor=ROOT/'scripts/verify-tablet-native-checkers.py';raw=predecessor.read_bytes();tree=ast.parse(raw)
 definitions=[n for n in tree.body if isinstance(n,ast.Assign)and any(isinstance(t,ast.Name)and t.id=='HEADER'for t in n.targets)]
 require(len(definitions)==1 and isinstance(definitions[0].value,ast.Constant)and isinstance(definitions[0].value.value,str),'Literal frozen host HEADER unavailable')
 header=definitions[0].value.value
 expected_names=set(HOST_NAMES);require(not expected_names&{'Invoke-Call','Run-Stage','Wait-Listener','Assert-OwnedSession','Open-ReadLease','Read-StartupIdentity'},'Unsafe host extraction')
 source=out/'source.ps1';source.write_bytes(ADAPTER.read_bytes()if adapter_bytes is None else adapter_bytes);source_sha=digest(source.read_bytes())
 expected=out/'host-expected.json';script=out/'checks.ps1';cases=[]
 def add(name,body,status=None):cases.append((name,'return'if status is None else'checker_rejection',status,body))
 for stage in ('load','play','spawn','run','stop'):
  add('n1.positive.'+stage,f"$v=Native '{stage}';$n=Check-Native $v '{stage}';if(-not(Stage-Ready $n.response '{stage}')){{throw 'Exact stage was not ready'}}")
 add('n1.raw-preserved',"$v=Native 'run';$before=$v|ConvertTo-Json -Depth 24 -Compress;$null=Check-Native $v 'run';if(($v|ConvertTo-Json -Depth 24 -Compress) -cne $before){throw 'Input mutated'}")
 add('n1.omitted-empty-arrays',"$v=Native 'load';foreach($k in @('caseIds','init_rows','rows')){$v.PSObject.Properties.Remove($k)};$n=Check-Native $v 'load';if(($n.codec.omitted_empty_arrays -join '|') -cne 'caseIds|init_rows|rows'){throw 'Omission registry differs'}")
 add('n1.numeric-bools',"$v=Native 'load';foreach($k in $BooleanFields){$v.$k=[int]$v.$k};$n=Check-Native $v 'load';if(($n.codec.numeric_boolean_fields -join '|') -cne ($BooleanFields -join '|')){throw 'Numeric bool registry differs'}")
 for stage,key,expr in (
  ('load','token',"'0'*64"),('load','source_sha256',"'0'*64"),('load','source_contract_sha256',"'0'*64"),('load','wire_contract_sha256',"'0'*64"),
  ('load','profile',"'foreign'"),('run','row_count','43'),('run','owner_count','1'),('run','init_count','0'),('run','executed','0'),('run','actions_ready','$false'),
  ('run','outside_domain','$true'),('run','failure',"'failure'"),('stop','stop_requested','$false'),('stop','edit_mode','$false'),('stop','in_play_mode','$true'),
  ('stop','phase','3'),('load','checksum','1000003'),('load','raw_bytes','32769'),('load','load_entered','0'),('load','schema_version','$true'),
  ('spawn','owner_count','$true'),('spawn','actions_ready','2'),('run','rows',"@('row')"),('spawn','init_rows',"'row'")):
  status='stale_input'if key in ('token','source_sha256','source_contract_sha256','wire_contract_sha256','profile')else'failure'
  add(f'n1.reject.{stage}.{key}',f"$v=Native '{stage}';$v.{key}={expr};$null=Check-Native $v '{stage}'",status)
 for key in ('token','schema_version','actions_ready','outside_domain','raw_bytes','wire_contract_sha256'):
  add('n1.reject.missing.'+key,f"$v=Native 'load';$v.PSObject.Properties.Remove('{key}');$null=Check-Native $v 'load'",'failure')
 for key in ('caseIds','init_rows','rows'):
  add('n1.reject.nonempty-omission.'+key,f"$v=Native 'run';$v.PSObject.Properties.Remove('{key}');$null=Check-Native $v 'run'",'failure')
 add('n1.reject.extra-field',"$v=Native 'spawn';$v|Add-Member unknown 1;$null=Check-Native $v 'spawn'",'failure')
 add('n1.reject.row-nonascii',"$v=Native 'run';$v.rows[0]='x'+[char]255;$null=Check-Native $v 'run'",'failure')
 add('n1.reject.row-newline',"$v=Native 'run';$v.rows[0]=\"bad`nrow\";$null=Check-Native $v 'run'",'failure')
 add('n1.reject.row-overflow',"$v=Native 'run';$v.rows[0]='x'*513;$null=Check-Native $v 'run'",'failure')
 add('n1.reject.case-type',"$v=Native 'run';$v.caseIds[0]=1;$null=Check-Native $v 'run'",'failure')
 add('n1.reject.case-shape',"$v=Native 'run';$v.caseIds[0]='foreign.case';$null=Check-Native $v 'run'",'failure')
 add('n1.reject.bool-text',"$v=Native 'spawn';$v.actions_ready='false';$null=Check-Native $v 'spawn'",'failure')
 add('n1.reject.bool-float',"$v=Native 'spawn';$v.actions_ready=0.0;$null=Check-Native $v 'spawn'",'failure')
 add('n1.reject.int-string',"$v=Native 'spawn';$v.owner_count='2';$null=Check-Native $v 'spawn'",'failure')
 add('n1.reject.int-overflow',"$v=Native 'spawn';$v.owner_count=2147483648L;$null=Check-Native $v 'spawn'",'failure')
 add('n1.reject.deferred-load-reset',"$v=Native 'run';$script:lastLoadProgress=$v;$x=Native 'load';$x.status='pending';$x.load_returned=0;$x.load_accepted=$false;$null=Check-Native $x 'load'",'stale_input')
 for stage in ('spawn','run'):
  add('n1.stage.refuse-ready.'+stage,f"$v=Native '{stage}';$v.status='ready';if(Stage-Ready $v '{stage}'){{throw 'Wrong native status advanced'}}")
  add('n1.stage.refuse-phase0.'+stage,f"$v=Native '{stage}';$v.phase=0;if(Stage-Ready $v '{stage}'){{throw 'Wrong native phase advanced'}}")
  add('n1.stage.reject-outside-play.'+stage,f"$v=Native '{stage}';$v.in_play_mode=$false;$null=Stage-Ready $v '{stage}'",'failure')
 add('n1.stage.reject-world',"$v=Native 'spawn';$v.world_matches=$false;$null=Stage-Ready $v 'spawn'",'stale_input')
 add('n1.stage.reject-delete',"$null=Stage-Ready (Native 'spawn') 'delete'",'failure')
 for action in ('load','status','play','spawn','run','stop'):
  add('n1.params.positive.'+action,f"Assert-Parameters 'BerylTabletRealServicesNative' @{{token=$Token;action='{action}'}}")
 for name,params in (('delete',"@{token=$Token;action='delete'}"),('input',"@{token=$Token;action='input'}"),('token',"@{token='foreign';action='run'}"),('extra',"@{token=$Token;action='run';code='anything'}"),('missing',"@{token=$Token}")):
  add('n1.params.reject.'+name,"Assert-Parameters 'BerylTabletRealServicesNative' "+params,'failure')
 add('n1.params.reject-unregistered',"Assert-Parameters 'Save' @{}",'failure')
 add('n1.projects.positive',"Assert-LoadedProjects ([pscustomobject]@{'Loaded Projects'=@($ProjectId,'ArmaReforger','core')})")
 add('n1.projects.reject-foreign',"Assert-LoadedProjects ([pscustomobject]@{'Loaded Projects'=@($ProjectId,'foreign')})",'stale_input')
 add('n1.raw.positive',"Assert-RawResponse (Reply)")
 add('n1.raw.reject-mismatch',"$v=Reply;$v.Raw='{}';Assert-RawResponse $v",'failure')
 add('n1.transport.positive',"Assert-Transport (Reply) 'BerylTabletRealServicesNative'")
 add('n1.transport.reject-failure',"$v=Reply;$v.Ok=$false;Assert-Transport $v 'BerylTabletRealServicesNative'",'failure')
 require(len({c[0]for c in cases})==len(cases),'Duplicate host cases')
 array=lambda xs:'@('+','.join("'"+v+"'"for v in xs)+')'
 actions=["Case '"+name+"' '"+outcome+"' "+('$null'if status is None else"'"+status+"'")+" {"+body+"}"for name,outcome,status,body in cases]
 source_text=SOURCE.read_bytes()if source_bytes is None else source_bytes;node=next(n for n in ast.parse(source_text).body if isinstance(n,ast.FunctionDef)and n.name=='normalized_native')
 bools=next(ast.literal_eval(n.value)for n in ast.walk(node)if isinstance(n,ast.Assign)and any(isinstance(t,ast.Name)and t.id=='bools'for t in n.targets))
 replacement="function Native([string]$Action) {\n switch -CaseSensitive ($Action) {\n"
 for stage in ('load','play','spawn','run','stop'):
  v=native(stage)
  for k in('addon_world_path','world_absolute_path','resource_absolute_path'):v[k]='C:/fixture/worlds/BerylTabletRealServicesN1a.ent'
  raw=json.dumps(v,separators=(',',':'));require("'"not in raw,'Unsafe synthetic literal quote')
  replacement+="  '"+stage+"' {$text='"+raw+"'}\n"
 replacement+="  default {throw 'Unknown synthetic stage'}\n };return ($text|ConvertFrom-Json)\n}\n"
 start=header.index('function Native(');end=header.index('function Reply',start);header=header[:start]+replacement+header[end:]
 header=header.replace('BerylTabletNativeCallbacks','BerylTabletRealServicesNative').replace('BerylTabletNativeStowed','BerylTabletRealServicesN1a')
 header=header.replace("$ExpectedContractHash='c'*64","$ExpectedContractHash='"+SOURCE_SHA+"'")
 header=header.replace("$suiteProfile='sparkos.tablet.native-init-stowed.source.v1'","$suiteProfile='sparkos.tablet.real-services.n1a.wire.v1'")
 header=header.replace("$ProjectId='BerylTabletNativeCheckProbe'","$ProjectId='BerylTabletRealServicesN1aPrototype'")
 header=header.replace("operation='tablet-native.checkers.inert'","operation='tablet-real-services.checkers.inert'")
 for marker,value in(('__EXPECTED__',array([c[0]for c in cases])),('__NAMES__',array(HOST_NAMES)),('__BOOLEANS__',array(bools)),('__COUNT__',str(len(cases))),('__CASES__','\n'.join(actions))):header=header.replace(marker,value)
 require(not re.search(r'__[A-Z_]+__',header)and len(header.encode())<=256*1024,'Host preparation placeholders/size differ')
 script.write_text(header,encoding='utf8',newline='\n');meta={'schema_version':1,'operation':'n1a_transport_host_fixture_preparation','status':'prepared_not_executed',
  'source':identity(source),'script':identity(script),'header_source':identity(predecessor),'function_names':list(HOST_NAMES),
  'expected_case_ids':[c[0]for c in cases],'expected_cases':len(cases),'cases':[{'id':n,'expected':o,'expected_status':s}for n,o,s,_ in cases],
  'result_path':str(out/'host-result.json'),'host':'not_run','engine':'not_run','compiler':'not_run','adapter_top_level':'not_run'}
 expected.write_bytes(json.dumps(meta,indent=2,sort_keys=True).encode()+b'\n')
 return {'expected':identity(expected),'source':identity(source),'script':identity(script),'expected_cases':len(cases),'host':'not_run'}

def check_host(path):
 """Passive admission of an independently executed inert-host receipt."""
 path=Path(path).resolve();meta_path=path.parent/'host-expected.json'
 require(path.is_relative_to((ROOT/'build').resolve())and path.is_file()and meta_path.is_file(),'Retained host receipt/metadata required')
 def read_json(p):
  require(p.stat().st_size<=2*1024*1024,'Bounded host receipt required')
  data=p.read_bytes();return json.loads(data),data
 meta,meta_raw=read_json(meta_path);value,raw=read_json(path)
 require(type(meta)is dict and meta.get('operation')=='n1a_transport_host_fixture_preparation'and meta.get('status')=='prepared_not_executed'and
         meta.get('schema_version')==1 and type(meta.get('schema_version'))is int,'Host preparation envelope differs')
 require(meta.get('function_names')==list(HOST_NAMES)and type(meta.get('cases'))is list and len(meta['cases'])==meta['expected_cases']<=256,'Host allowlist/case bounds differ')
 require(meta['expected_case_ids']==[c['id']for c in meta['cases']]and len(set(meta['expected_case_ids']))==len(meta['cases']),'Host case registry incomplete')
 for name in('source','script','header_source'):
  require(type(meta[name])is dict and identity(Path(meta[name]['path']))==meta[name],'Host prepared input changed: '+name,'stale_input')
 require(Path(meta['result_path']).resolve()==path,'Host result path differs')
 pred=ROOT/'scripts/verify-tablet-native-checkers.py';tree=ast.parse(pred.read_bytes(),filename=str(pred))
 chosen=[n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name=='validate_result']
 require(len(chosen)==1,'Registered host receipt function missing')
 env={'NAMES':list(HOST_NAMES)};exec(compile(ast.Module(body=chosen,type_ignores=[]),str(pred),'exec'),env)
 require(value.get('operation')=='tablet-real-services.checkers.inert','Host outcome profile differs')
 normalized=copy.deepcopy(value);normalized['operation']='tablet-native.checkers.inert'
 cases=[(c['id'],c['expected'],c['expected_status'],'')for c in meta['cases']]
 env['validate_result'](normalized,cases,Path(meta['source']['path']),meta['source']['sha256'])
 out=ROOT/'build'/('tablet-real-services-host-audit-'+uuid.uuid4().hex);out.mkdir()
 result={'schema_version':1,'operation':'n1a_transport_inert_host_receipt_admission','status':'success','scope':'passive exact receipt/source/case verification',
         'host':'not_run_by_this_checker','engine':'not_run','compiler':'not_run','adapter_top_level':'not_run','process_queries':'not_run',
         'executed_source_helpers':15,'executed_fixture_cases':len(cases),'receipt':identity(path),'preparation':identity(meta_path),
         'source':meta['source'],'script':meta['script'],'header_source':meta['header_source'],'expected_case_ids':meta['expected_case_ids'],
         'complete_expected_case_set':True}
 data=json.dumps(result,indent=2,sort_keys=True).encode()+b'\n';dest=out/'result.json';dest.write_bytes(data)
 print(json.dumps({'status':'success','result':str(dest),'sha256':digest(data),'cases':len(cases),'source_sha256':meta['source']['sha256']}))
 return 0

def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--prepare-host',action='store_true');parser.add_argument('--check-host',type=Path);args=parser.parse_args()
 if args.check_host:return check_host(args.check_host)
 out=ROOT/'build'/('tablet-real-services-transport-'+uuid.uuid4().hex);out.mkdir();(out/'inputs').mkdir()
 result={'schema_version':1,'operation':'n1a_transport_ast_synthetic_checks','status':'running','scope':'passive physical source relation plus AST-extracted Python synthetic receipt checks',
         'host':'not_run','engine':'not_run','compiler':'not_run','PowerShell':'not_run','root_runner_top_level':'not_run','process_queries':'not_run','actual_leases':'not_run','cases':[],'source_inputs':[]}
 failures=[];plans=[];captured={}
 def case(name,action,reject=False):plans.append((name,action,reject))
 try:
  for index,path in enumerate((SOURCE,ADAPTER,PREDECESSOR,Path(__file__),PACKAGE/'wire.py',PACKAGE/'oracle.py',PACKAGE/'wire-contract.json',PACKAGE/'contract.json')):
   raw=path.read_bytes();captured[path]=raw;item={'path':str(path),'bytes':len(raw),'sha256':digest(raw)};retained=out/'inputs'/(str(index)+'-'+path.name);retained.write_bytes(raw)
   require(retained.read_bytes()==raw,'Source capture changed');item['retained']=str(retained);result['source_inputs'].append(item)
  relation=source_relation(captured[ADAPTER],captured[PREDECESSOR]);result['source_relation']=relation
  oracle=pure_package(PACKAGE/'oracle.py');wire=pure_package(PACKAGE/'wire.py');wire.__dict__['_ORACLE_CACHE']=oracle
  # Function globals use their original extracted namespace, so pin its cache too.
  wire._oracle.__globals__['_ORACLE_CACHE']=oracle
  env={'Path':Path,'Decimal':Decimal,'re':re,'wire':wire,'WIRE_SOURCE_SHA':SOURCE_SHA,'WIRE_CONTRACT_SHA':WIRE_SHA,'h':types.SimpleNamespace(require=require)}
  load_functions(env,captured[SOURCE]);r,expected,manifest,mid,tracked,native,init=fixture(env,wire,oracle)
  verify=lambda value:env['validate_runtime'](value,expected,manifest,mid,tracked)
  case('receipt.positive.TT',lambda:verify(copy.deepcopy(r)))
  for name,action in (
   ('status-failure',lambda v:v.update(status='failure')),('status-timeout',lambda v:v.update(status='timeout')),
   ('status-cancelled',lambda v:v.update(status='cancelled')),('status-unavailable',lambda v:v.update(status='unavailable')),
   ('missing-cleanup',lambda v:v.update(cleanup='owned_process_exit_not_confirmed')),('cleanup-errors',lambda v:v['cleanup_errors'].append({'message':'failed'})),
   ('stale-token',lambda v:v.update(token='0'*64)),('stale-engine',lambda v:v.update(engine_sha256='0'*64)),('stale-adapter',lambda v:v.update(adapter_sha256='0'*64)),
   ('missing-stage',lambda v:v['stages'].pop(2)),('stage-reorder',lambda v:v['stages'].reverse()),('stage-64plus',lambda v:v['stages'][0].update(polls=65)),
   ('schema-bool',lambda v:v.update(schema_version=True)),('elapsed-late',lambda v:v.update(elapsed_ms=180000)),
   ('rpc-timeout',lambda v:v['rpcs'][3].update(timeout_ms=10)),('rpc-raw-mismatch',lambda v:v['rpcs'][4]['result'].update(Raw='{}')),
   ('foreign-loaded-project',lambda v:v['rpcs'][0]['result']['Response']['Loaded Projects'].append('foreign')),
   ('missing-rpc',lambda v:v['rpcs'].pop(3)),('missing-session-check',lambda v:v['session_checks'].pop()),
   ('listener-foreign',lambda v:v['port_checks'][-1].update(owning_process=456)),('source-lease-count',lambda v:v['read_lease'].update(opened_count=103)),
   ('source-lease-entry-missing',lambda v:v['read_lease']['entries'].pop()),('source-lease-entry-duplicate',lambda v:v['read_lease']['entries'].__setitem__(0,copy.deepcopy(v['read_lease']['entries'][1]))),
   ('source-lease-wrong-hash',lambda v:v['read_lease']['entries'][0].update(sha256='0'*64)),('missing-held-check',lambda v:v['read_lease']['fast_checks'].pop()),
   ('startup-unverified',lambda v:v['startup'].update(identity_status='pending')),('startup-timestamp-unit',lambda v:v['startup'].update(identity_start_ticks_unit='unix_100ns')),
   ('startup-pid-reset',lambda v:v['startup']['identity_checks'][-1].update(process_id=456)),('startup-image-foreign',lambda v:v['startup']['identity_checks'][-1].update(raw_path='C:/foreign.exe')),
   ('forbidden-player-input',lambda v:v.update(physical_ui_input='executed')),('missing-raw-log',lambda v:v.update(raw_logs=[]))):
   def action(change=action):
    v=copy.deepcopy(r);change(v);return verify(v)
   case('receipt.reject.'+name,action,True)
  def changed_response(stage,change):
   v=copy.deepcopy(r);i=('load','play','spawn','run','stop').index(stage);change(v['stages'][i]['response'])
   raw=v['stages'][i]['response'];entry=v['rpcs'][i+1];entry['result'].update(Raw=json.dumps(raw),Response=copy.deepcopy(raw))
   n,codec=env['normalized_native'](raw);entry.update(normalized_response=n,codec=codec)
   if stage=='stop':v['completion']=copy.deepcopy(raw)
   return v
  for stage,key,value in (
   ('spawn','owner_count',1),('spawn','init_count',0),('spawn','actions_ready',True),('run','executed',0),('run','row_count',43),
   ('stop','phase',3),('stop','stop_requested',False),('stop','status','pending'),('spawn','phase',0),('spawn','status','ready'),('run','phase',0),('run','status','ready'),
   ('run','outside_domain',True),('stop','failure','actual_failure'),('stop','rows',[]),('stop','init_rows',[])):
   case(f'receipt.reject.{stage}.{key}',lambda s=stage,k=key,x=value:verify(changed_response(s,lambda v:v.update({k:x}))),True)
  case('init.positive',lambda:env['validate_init_rows'](copy.deepcopy(init),wire.checksum(init)))
  for name,index,column,value in (('owner-false',0,3,'0'),('wrong-world',0,7,'0'),('shared-state',2,10,'0'),('wrong-init-order',1,2,'init.before'),('FRAME-missing',1,13,'0'),('nonzero-acc',0,12,'0.1'),('nan-acc',0,12,'NaN'),('mode-focused',0,11,'2')):
   def changed(index=index,column=column,value=value):
    rows=copy.deepcopy(init);parts=rows[index].split('|');parts[column]=value;rows[index]='|'.join(parts)
    return env['validate_init_rows'](rows,wire.checksum(rows))
   case('init.reject.'+name,changed,True)
  case('normalization.positive',lambda:env['normalized_native'](native('spawn')))
  def normalize_change(change):
   v=native('spawn');change(v);return env['normalized_native'](v)
  for name,change in (
   ('unknown-field',lambda v:v.update(unknown=1)),('missing-identity',lambda v:v.pop('token')),('bool-as-int',lambda v:v.update(owner_count=True)),
   ('float-as-bool',lambda v:v.update(actions_ready=0.0)),('string-as-bool',lambda v:v.update(actions_ready='false')),('int2-as-bool',lambda v:v.update(actions_ready=2)),
   ('init-omitted-nonempty',lambda v:v.pop('init_rows')),('rows-dict',lambda v:v.update(rows={})),('oversize-text',lambda v:v.update(token='x'*2049))):
   case('normalization.reject.'+name,lambda c=change:normalize_change(c),True)
  case('source.positive-predecessor',lambda:source_relation(ADAPTER.read_bytes(),PREDECESSOR.read_bytes()))
  case('source.reject-startup-mutant',lambda:source_relation(ADAPTER.read_bytes().replace(b'$Process.Refresh()',b'$Process.ToString()',1),PREDECESSOR.read_bytes()),True)
  require(len({name for name,_,_ in plans})==len(plans),'Duplicate case IDs')
  result['expected_case_ids']=[name for name,_,_ in plans];result['expected_cases']=len(plans)
  for name,action,reject in plans:
   try:
    action()
    if reject:raise AssertionError('Deliberate mutant accepted')
    row={'id':name,'status':'success','interpretation':'synthetic accepted'}
   except Exception as error:
    if reject and isinstance(error,(Rejected,wire.WireFailure,oracle.VerificationFailure,KeyError,TypeError,InvalidOperation)):
     row={'id':name,'status':'success','interpretation':'synthetic rejected','exception':type(error).__name__,'detail':str(error),'outcome':getattr(error,'status','structural_exception')}
    else:row={'id':name,'status':'failure','exception':type(error).__name__,'detail':str(error)};failures.append(row)
   result['cases'].append(row)
  result.update(status='failure'if failures else'success',failures=failures,passed=len(plans)-len(failures),complete_expected_case_set=[v['id']for v in result['cases']]==result['expected_case_ids'])
  if args.prepare_host:result['host_fixture']=prepare_host(out,native,captured[ADAPTER],captured[SOURCE])
  for path,raw in captured.items():require(path.read_bytes()==raw,'Source changed during passive gate: '+str(path),'stale_input')
 except Exception as error:result.update(status='failure',failure={'type':type(error).__name__,'message':str(error)})
 raw=json.dumps(result,sort_keys=True,indent=2).encode()+b'\n';(out/'result.json').write_bytes(raw)
 require((out/'result.json').read_bytes()==raw,'Receipt write mismatch')
 print(json.dumps({'status':result['status'],'result':str(out/'result.json'),'sha256':digest(raw),'passed':result.get('passed'),'expected':result.get('expected_cases'),'failures':result.get('failures',[]),'failure':result.get('failure')}))
 return 0 if result['status']=='success'else 1

if __name__=='__main__':raise SystemExit(main())
