#!/usr/bin/env python3
"""Independent inert admission faults for separate callback frame observations.

Only pure Python validators are called. Successful synthetic observations are
diagnostic data, never engine frames, callbacks, performance or release proof.
"""
from pathlib import Path
import copy,hashlib,importlib.util,json,sys,tempfile

ROOT=Path(__file__).resolve().parents[1]
TARGET=ROOT/'scripts/verify-component-callbacks.py'
ADAPTER=ROOT/'scripts/component-callback-engine.ps1'
TOKEN='a'*64
FUNCTION='BerylComponentFrameState'
BOOLS=('api_present','game_present','owner1_present','owner2_present','owner1_component_present','owner2_component_present',
       'api_is_game','owner1_is_api','owner1_is_game','owner2_is_api','owner2_is_game','owner1_active','owner2_active',
       'owner1_frame_registered','owner2_frame_registered')
INTS=('phase','api_frame','game_frame','owner1_frame','owner2_frame','owner1_flags','owner2_flags','owner1_mask','owner2_mask')
sys.dont_write_bytecode=True

def identity(path):
 data=Path(path).read_bytes();return{'path':str(path),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
def write(path,value):
 data=(json.dumps(value,indent=2,ensure_ascii=True)+'\n').encode()
 with path.open('xb')as stream:
  if stream.write(data)!=len(data):raise OSError('Short inert diagnostic write')
 if path.read_bytes()!=data:raise OSError('Diagnostic receipt readback differs')
def wire():
 return{'token':TOKEN,'profile':'world-state-v1','status':'observed','failure':'',
        **{name:name in BOOLS[:6]for name in BOOLS},**{name:2 if name=='phase'else 0 for name in INTS}}
def session():return{'process_id':123,'start_ticks':456,'executable':'C:/fixture/Workbench.exe','project':'C:/fixture/addon','reused':False}
def entry(elapsed=100):
 owner=session();response=wire()
 checks=[{'site':site,'process_id':owner['process_id'],'start_ticks':owner['start_ticks'],'executable':owner['executable'],
          'elapsed_ms':elapsed+delta}for site,delta in(('before',-10),('after',10))]
 return{'function':FUNCTION,'params':{'token':TOKEN},'stage':'spawn','phase':2,'elapsed_ms':elapsed,'timeout_ms':8000,
        'result':{'Ok':True,'Function':FUNCTION,'Raw':json.dumps(response),'Response':response},'failure':None,'identity_checks':checks}
def fixture():return{'frame_diagnostics':'world-state-v1','frame_state_rpcs':[entry()],'elapsed_ms':1000},['world-state-v1',TOKEN,session()]
def response(v):return v['frame_state_rpcs'][0]['result']['Response']
def sync(v):
 for call in v['frame_state_rpcs']:
  if isinstance(call.get('result'),dict)and'Response'in call['result']:call['result']['Raw']=json.dumps(call['result']['Response'])
def change(v,path,value):
 target=v
 for key in path[:-1]:target=target[key]
 target[path[-1]]=copy.deepcopy(value)

def main():
 spec=importlib.util.spec_from_file_location('callback_frame_admission',TARGET)
 module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
 work=Path(tempfile.mkdtemp(prefix='callback-frame-diagnostics-inert-',dir=ROOT/'build'))
 cases=[]
 def case(name,mutate=None,expected='reject',sync_wire=False):cases.append((name,mutate,expected,sync_wire))
 case('positive.boolean-wire',expected='observed')
 case('positive.numeric-bool-wire',lambda v,a:response(v).update({name:int(response(v)[name])for name in BOOLS}),expected='observed',sync_wire=True)
 case('positive.false-world-equality-and-inactive-is-data',expected='observed')
 case('positive.two-sequential-samples',lambda v,a:v['frame_state_rpcs'].append(entry(200)),expected='observed')
 case('positive.phase-advances-during-observation',lambda v,a:response(v).update(phase=3),expected='observed',sync_wire=True)
 def off(v,a):v.update(frame_diagnostics='off',frame_state_rpcs=[]);a[0]='off';a[2]=None
 case('positive.default-off',off,expected='not_run')
 case('positive.selected-before-spawn-no-observation',lambda v,a:v.update(frame_state_rpcs=[]),expected='unavailable')
 def transport_failure(v,a):
  call=v['frame_state_rpcs'][0];call.update(failure='INERT bounded diagnostic RPC timeout',result=None);call['identity_checks'].pop()
 case('positive.failed-diagnostic-is-unavailable',transport_failure,expected='unavailable')
 case('positive.unavailable-reply-not-observed',lambda v,a:response(v).update(status='unavailable',failure='INERT missing valid world'),expected='unavailable',sync_wire=True)
 case('positive.failed-reply-not-observed',lambda v,a:response(v).update(status='failure',failure='INERT failed native query'),expected='unavailable',sync_wire=True)
 for name in ('token','profile','status','failure',*BOOLS,*INTS):
  case('wire.missing.'+name,lambda v,a,k=name:response(v).pop(k),sync_wire=True)
 case('wire.unknown-field',lambda v,a:response(v).update(guessed=True),sync_wire=True)
 for name,value in(('wrong-token','b'*64),('bool-token',True),('overlong-token','a'*65)):
  case('wire.'+name,lambda v,a,x=value:response(v).update(token=x),sync_wire=True)
 for name,field,value in(('wrong-profile','profile','other'),('bool-profile','profile',True),('wrong-status','status','success'),
                         ('bool-status','status',True),('failure-bool','failure',False),('failure-overlong','failure','x'*2049),
                         ('observed-with-failure','failure','unexpected'),('observed-after-delete','phase',4)):
  case('wire.'+name,lambda v,a,k=field,x=value:response(v).update({k:x}),sync_wire=True)
 for name in BOOLS:
  case('wire.bool-float.'+name,lambda v,a,k=name:response(v).update({k:1.0}),sync_wire=True)
  case('wire.bool-outside01.'+name,lambda v,a,k=name:response(v).update({k:2}),sync_wire=True)
 for name in BOOLS[:6]:
  case('wire.observed-missing-live-reference.'+name,lambda v,a,k=name:response(v).update({k:False}),sync_wire=True)
 for name in INTS:
  case('wire.int-bool.'+name,lambda v,a,k=name:response(v).update({k:True}),sync_wire=True)
  case('wire.int-overflow.'+name,lambda v,a,k=name:response(v).update({k:2**31}),sync_wire=True)
 case('wire.negative-phase',lambda v,a:response(v).update(phase=-1),sync_wire=True)
 for field in('function','params','stage','phase','elapsed_ms','timeout_ms','result','failure','identity_checks'):
  case('entry.missing.'+field,lambda v,a,k=field:v['frame_state_rpcs'][0].pop(k))
 case('entry.unknown',lambda v,a:v['frame_state_rpcs'][0].update(fallback=True))
 for name,field,value in(('wrong-function','function','Other'),('params-extra','params',{'token':TOKEN,'op':'save'}),
  ('params-stale','params',{'token':'b'*64}),('wrong-stage','stage','delete'),('phase-bool','phase',True),('phase-deleted','phase',4),
  ('elapsed-bool','elapsed_ms',True),('elapsed-negative','elapsed_ms',-1),('elapsed-expired','elapsed_ms',180000),
  ('timeout-bool','timeout_ms',True),('timeout-zero','timeout_ms',0),('timeout-excessive','timeout_ms',8001),
  ('failure-bool','failure',True),('failure-empty','failure',''),('failure-overlong','failure','x'*4097)):
  case('entry.'+name,lambda v,a,k=field,x=value:v['frame_state_rpcs'][0].update({k:x}))
 case('entry.third-sample',lambda v,a:v['frame_state_rpcs'].extend([entry(200),entry(300)]))
 case('entry.elapsed-after-runtime',lambda v,a:v.update(elapsed_ms=99))
 case('entry.identity-after-runtime',lambda v,a:v.update(elapsed_ms=105))
 case('runtime.elapsed-bool',lambda v,a:v.update(elapsed_ms=True))
 case('runtime.elapsed-missing',lambda v,a:v.pop('elapsed_ms'))
 def overlap(v,a):
  later=entry(105);v['frame_state_rpcs'].append(later)
 case('entry.second-check-overlaps-first',overlap)
 case('entry.reversed-samples',lambda v,a:v['frame_state_rpcs'].append(entry(50)))
 for field,value in(('Ok',False),('Ok',1),('Function','Other'),('Raw','null'),('Raw','{bad'),('Raw',None)):
  case('reply.'+field+'.'+repr(value),lambda v,a,k=field,x=value:v['frame_state_rpcs'][0]['result'].update({k:x}))
 case('reply.raw-bool-int-substitution',lambda v,a:v['frame_state_rpcs'][0]['result'].update(Raw=json.dumps({**response(v),'api_present':1})))
 case('reply.response-null',lambda v,a:v['frame_state_rpcs'][0]['result'].update(Response=None))
 for index in(0,1):
  for name,field,value in(('pid-bool','process_id',True),('pid-foreign','process_id',124),('ticks-bool','start_ticks',True),
   ('ticks-foreign','start_ticks',457),('exe-foreign','executable','C:/other/Workbench.exe'),('time-bool','elapsed_ms',True),
   ('time-negative','elapsed_ms',-1),('time-expired','elapsed_ms',180000),('site-wrong','site','callback')):
   case('identity.'+str(index)+'.'+name,lambda v,a,i=index,k=field,x=value:v['frame_state_rpcs'][0]['identity_checks'][i].update({k:x}))
 case('identity.before-after-call',lambda v,a:v['frame_state_rpcs'][0]['identity_checks'][0].update(elapsed_ms=101))
 case('identity.after-before-call',lambda v,a:v['frame_state_rpcs'][0]['identity_checks'][1].update(elapsed_ms=99))
 case('identity.success-missing-after',lambda v,a:v['frame_state_rpcs'][0]['identity_checks'].pop())
 case('identity.scalar',lambda v,a:v['frame_state_rpcs'][0]['identity_checks'].__setitem__(0,'bad'))
 case('identity.unknown-field',lambda v,a:v['frame_state_rpcs'][0]['identity_checks'][0].update(extra=True))
 for name,field,value in(('pid-bool','process_id',True),('ticks-bool','start_ticks',True),('pid-zero','process_id',0),
                         ('ticks-zero','start_ticks',0),('exe-null','executable',None)):
  case('session.'+name,lambda v,a,k=field,x=value:a[2].update({k:x}))
 case('selection.unknown',lambda v,a:a.__setitem__(0,'other'))
 case('selection.bool',lambda v,a:a.__setitem__(0,True))
 case('selection.substituted',lambda v,a:v.update(frame_diagnostics='off'))
 case('selection.missing',lambda v,a:v.pop('frame_diagnostics'))
 case('selection.off-with-observations',lambda v,a:(a.__setitem__(0,'off'),v.update(frame_diagnostics='off')))
 case('selection.rpc-list-missing',lambda v,a:v.pop('frame_state_rpcs'))
 case('selection.rpc-list-null',lambda v,a:v.update(frame_state_rpcs=None))
 def returned_at_budget(v,a):
  v['elapsed_ms']=9000
  v['frame_state_rpcs'][0]['identity_checks'][1]['elapsed_ms']=8100
 case('positive.success-exact-return-budget',returned_at_budget,expected='observed')
 def late_success(v,a):
  returned_at_budget(v,a)
  v['frame_state_rpcs'][0]['identity_checks'][1]['elapsed_ms']=8101
 case('entry.success-after-rpc-return-budget',late_success)
 expected=[row[0]for row in cases];assert len(expected)==len(set(expected))
 sources=[Path(__file__).resolve(),TARGET,ADAPTER]
 frozen={str(path):identity(path)for path in sources};retained=[]
 for index,path in enumerate(sources):
  target=work/(str(index).zfill(2)+'-'+path.name+'.input');data=path.read_bytes()
  with target.open('xb')as stream:
   if stream.write(data)!=len(data):raise OSError('Short frozen source retention')
  assert identity(target)['sha256']==frozen[str(path)]['sha256'];retained.append({'source':frozen[str(path)],'retained':identity(target)})
 record={'schema_version':1,'operation':'verify.callback.frame_diagnostics.inert','status':'failure','expected_case_ids':expected,
  'cases':[],'inputs':frozen,'retained_inputs':retained,'scope':{'python_validator':'synthetic_admission_only','host':'not_run','powershell':'not_run',
  'compiler':'not_run','engine':'not_run','signals':'not_run','callback_delivery':'not_run','performance':'not_run'}}
 for index,(name,mutate,wanted,sync_wire)in enumerate(cases):
  runtime,args=fixture()
  if mutate:mutate(runtime,args)
  if sync_wire:sync(runtime)
  outcome,rejection,crash=None,None,None
  before=copy.deepcopy(runtime)
  try:outcome=module.validate_frame_diagnostics(runtime,*args)
  except module.mod.Failure as exc:rejection={'type':type(exc).__name__,'status':exc.status,'message':str(exc)}
  except Exception as exc:crash={'type':type(exc).__name__,'message':str(exc)}
  good=(rejection is not None and crash is None)if wanted=='reject'else(outcome is not None and outcome.get('status')==wanted and crash is None and rejection is None)
  row={'id':name,'status':'passed'if good and before==runtime else'failed','expected':wanted,'outcome':outcome,'rejection':rejection,'exception':crash,'input_unchanged':before==runtime}
  record['cases'].append(row);write(work/('case-'+str(index).zfill(3)+'.json'),{'id':name,'runtime':runtime,'selected_arguments':args,'result':row})
 record['case_set_complete']=[row['id']for row in record['cases']]==expected
 record['source_unchanged']={str(path):identity(path)for path in sources}==frozen
 record['expected_count']=len(expected);record['passed_count']=sum(row['status']=='passed'for row in record['cases'])
 record['status']='success'if record['case_set_complete']and record['source_unchanged']and record['passed_count']==len(expected)else'failure'
 write(work/'result.json',record)
 print(json.dumps({'receipt':identity(work/'result.json'),'status':record['status'],'expected':len(expected),'passed':record['passed_count'],
                   'source':frozen[str(TARGET)],'runner':frozen[str(Path(__file__).resolve())],'nonpassing':[row for row in record['cases']if row['status']!='passed']}),flush=True)
 return 0 if record['status']=='success'else 1

if __name__=='__main__':raise SystemExit(main())
