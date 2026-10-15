#!/usr/bin/env python3
"""Independent nonexecuting source/staging faults for the preserved tablet suites.

Only Python admission functions and owned files are used. Targeted filesystem
observation faults call the actual prior-receipt verifier; one optional full
preparation fixture replaces Job with a nonexecuting timeout stub. No host,
compiler, engine, process signal or suite is executed.
"""
from pathlib import Path
import argparse,contextlib,copy,hashlib,importlib.util,io,json,os,sys,tempfile
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
TARGET=ROOT/'scripts/verify-tablet-existing-suites.py'
PRIOR=ROOT/'build/tablet service & spaces-j_t2z5u0/results.json'

def identity(path):
 raw=Path(path).read_bytes()
 return{'path':str(path),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
def save(path,value):
 path.parent.mkdir(parents=True,exist_ok=True)
 raw=(json.dumps(value,indent=2,ensure_ascii=True)+'\n').encode()
 with path.open('xb')as stream:
  if stream.write(raw)!=len(raw):raise OSError('Short inert staging receipt write')
 if path.read_bytes()!=raw:raise OSError('Inert staging receipt readback differs')
def set_path(value,path,replacement):
 for key in path[:-1]:value=value[key]
 value[path[-1]]=copy.deepcopy(replacement)

def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--include-main-fault',action='store_true',help='Exercise real main with nonexecuting Job timeout stub')
 args=parser.parse_args()
 work=Path(tempfile.mkdtemp(prefix='tablet-existing-suite-staging-inert-',dir=ROOT/'build'))
 raw=TARGET.read_bytes();spec=importlib.util.spec_from_file_location('existing_suite_staging_target',TARGET)
 module=importlib.util.module_from_spec(spec);exec(compile(raw,str(TARGET),'exec'),module.__dict__)
 prior=json.loads(PRIOR.read_bytes());prior_id=module.identity(PRIOR);cases=[]
 def register(name,action,expected):cases.append((name,action,expected))
 def rejection(action):
  try:action();return{'rejected':False}
  except module.mod.Failure as exc:return{'rejected':True,'status':exc.status,'message':str(exc)}
 def source_case(name,mutate=None,accepted=False):
  def action():
   value=copy.deepcopy(prior)
   if mutate:mutate(value)
   before=module.mod.canonical(value)
   try:module.validate_source_receipt(value);out={'accepted':True}
   except module.mod.Failure as exc:out={'accepted':False,'status':exc.status,'message':str(exc)}
   out['unchanged']=module.mod.canonical(value)==before
   return out
  register('source.'+name,action,{'accepted':accepted,'unchanged':True})
 source_case('actual-S1',accepted=True)
 for key in('schema_version','operation','status','stage','candidate_profile','scope','suite_selection','tablet_suite_profile',
             'candidate_addon','staged_file_set','staged_sha256','source_profile','generated_file','raw_results',
             'verification_inputs','retained_input_files','raw_engine_logs'):
  source_case('missing.'+key,lambda v,k=key:v.pop(k))
 for name,path,replacement in(
  ('bool-schema',('schema_version',),True),('float-schema',('schema_version',),1.0),('wrong-schema',('schema_version',),2),
  ('wrong-operation',('operation',),'mod build'),('failed-source',('status',),'failure'),('unavailable-source',('status',),'unavailable'),
  ('prepared-only',('stage',),'prepared'),('default-profile',('candidate_profile',),'source-only'),
  ('scope-null',('scope',),None),('suite-selection-null',('suite_selection',),None),('raw-results-null',('raw_results',),None),
  ('raw-compile-null',('raw_results','compile'),None),('raw-compile-result-null',('raw_results','compile','result'),None),
  ('suite-executed',('suite_selection','executed'),1),('bool-suite-count',('suite_selection','executed'),False),
  ('suite-outcome-forged',('suite_selection','status'),'success'),('suite-scope-forged',('scope','tablet_suite_execution'),'executed_success'),
  ('source-profile-bool-schema',('source_profile','schema_version'),True),('source-profile-engine-other',('source_profile','engine_sha256'),'0'*64),
  ('candidate-live-id',('candidate_addon','id'),'SparkOSMesh'),('wrong-generated-path',('generated_file',),'scripts/Game/Other.c'),
  ('bool-compile-schema',('raw_results','compile','result','schema_version'),True),
  ('bool-compile-exit',('raw_results','compile','result','result','ExitCode'),False),
  ('compile-errors',('raw_results','compile','result','result','ErrorCount'),1),
  ('bool-compile-errors',('raw_results','compile','result','result','ErrorCount'),False),
  ('compile-timeout',('raw_results','compile','result','status'),'timeout'),
  ('compile-engine-other',('raw_results','compile','result','engine_sha256'),'0'*64),
  ('logs-empty',('raw_engine_logs',),[]),('logs-null',('raw_engine_logs',),None),
  ('input-ledger-empty',('verification_inputs',),{}),('retained-inputs-null',('retained_input_files',),None)):
  source_case(name,lambda v,p=path,r=replacement:set_path(v,p,r))
 def staged_mutation(name,mutate):
  def action(value):
   mutate(value['staged_file_set']);value['staged_sha256']=module.mod.digest(module.mod.canonical(value['staged_file_set']))
  source_case(name,action)
 staged_mutation('stage85',lambda v:v.pop('Prefabs/SPK_Tablet.et.meta'))
 staged_mutation('stage87',lambda v:v.update({'unknown.conf':'0'*64}))
 staged_mutation('resource-sha-other',lambda v:v.update({'Prefabs/SPK_Tablet.et':'0'*64}))
 staged_mutation('original-script-other',lambda v:v.update({'scripts/WorkbenchGameCommon/ValidatePrefab.c':'0'*64}))
 for name,path in(('parent','../outside.conf'),('absolute','C:/outside.conf'),('rooted','/outside.conf'),
                   ('backslash','Prefabs\\SPK_Tablet.et'),('case','Prefabs/spk_tablet.et')):
  def change(v,p=path):v[p]=v.pop('Prefabs/SPK_Tablet.et')
  staged_mutation('unsafe-stage-path.'+name,change)
 source_case('partial-suite-selection',lambda v:v['suite_selection']['requests'].pop())
 source_case('reordered-suite-selection',lambda v:v['suite_selection']['requests'].reverse())
 source_case('suite-arg-other',lambda v:v['suite_selection']['requests'][-1].update(arg='{0000000000000000}Prefabs/Other.et'))

 # Small actual owned trees exercise shape and cache policy without duplicating
 # the selected12MiB source candidate for each negative.
 def tree_case(name,mutate=None,cache=False,accepted=False):
  def action():
   home=work/'trees'/name;home.mkdir(parents=True)
   (home/'scripts/Game').mkdir(parents=True);(home/'scripts/Game/A.c').write_bytes(b'inert source\n')
   expected={'scripts/Game/A.c':hashlib.sha256(b'inert source\n').hexdigest()}
   if mutate:mutate(home,expected)
   try:derived=module.checked_tree(home,expected,cache);return{'accepted':True,'derived':sorted(derived)}
   except module.mod.Failure as exc:return{'accepted':False,'status':exc.status,'message':str(exc)}
  wanted={'accepted':accepted}
  if accepted:wanted['derived']=['resourceDatabase.rdb']if cache else[]
  register('tree.'+name,action,wanted)
 tree_case('exact-owned',accepted=True)
 tree_case('changed-source',lambda h,e:(h/'scripts/Game/A.c').write_bytes(b'changed'))
 tree_case('missing-source',lambda h,e:(h/'scripts/Game/A.c').unlink())
 tree_case('unknown-file',lambda h,e:(h/'scripts/Game/Other.c').write_bytes(b'extra'))
 tree_case('unknown-directory',lambda h,e:(h/'unexpected').mkdir())
 tree_case('root-cache-default-rejected',lambda h,e:(h/'resourceDatabase.rdb').write_bytes(b'derived'))
 tree_case('root-cache-selected-bounded',lambda h,e:(h/'resourceDatabase.rdb').write_bytes(b'derived'),cache=True,accepted=True)
 tree_case('nested-cache-rejected',lambda h,e:(h/'scripts/resourceDatabase.rdb').write_bytes(b'not admitted'),cache=True)
 tree_case('root-cache-is-directory',lambda h,e:(h/'resourceDatabase.rdb').mkdir(),cache=True)
 tree_case('root-cache-oversize',lambda h,e:(h/'resourceDatabase.rdb').write_bytes(b'x'*(8388608+1)),cache=True)

 # Actual prior positive establishes the observed file snapshot. Targeted test
 # observations below use cached exact tables plus one altered observation;
 # these are synthetic filesystem-service faults, never altered actual S1 files.
 originals={'files':module.h.files,'identity':module.identity,'streamed':module.h.streamed_identity,'read':module.mod.read}
 tables={};identities={};streams={}
 def cached_files(path):
  key=str(Path(path))
  if key not in tables:tables[key]=originals['files'](Path(path))
  return dict(tables[key])
 def cached_identity(path):
  key=str(Path(path))
  if key not in identities:identities[key]=originals['identity'](Path(path))
  return dict(identities[key])
 def cached_streamed(path):
  key=str(Path(path))
  if key not in streams:streams[key]=originals['streamed'](Path(path))
  return dict(streams[key])
 def prior_positive():
  module.verify_prior(PRIOR.parent,prior,prior_id)
  return{'accepted':True}
 register('prior.actual-original-evidence',prior_positive,{'accepted':True})
 def prior_fault(name,kind,path):
  path=Path(path)
  def action():
   def fake_files(p):
    observed=cached_files(p)
    if Path(p)==path:observed['INERT.extra.input']='0'*64
    return observed
   def fake_identity(p):
    observed=cached_identity(p)
    if Path(p)==path:observed['sha256']='0'*64
    return observed
   def fake_streamed(p):
    observed=cached_streamed(p)
    if Path(p)==path:observed['sha256']='0'*64
    return observed
   def fake_read(p,*a,**k):
    raw=originals['read'](p,*a,**k)
    if Path(p)==path:
     value=json.loads(raw);value['INERT.unexpected']=True;return module.mod.canonical(value)
    return raw
   try:
    module.h.files=fake_files if kind=='files'else cached_files
    module.identity=fake_identity if kind=='identity'else cached_identity
    module.h.streamed_identity=fake_streamed if kind=='streamed'else cached_streamed
    module.mod.read=fake_read if kind=='read'else originals['read']
    return rejection(lambda:module.verify_prior(PRIOR.parent,prior,prior_id))
   finally:
    module.h.files=originals['files'];module.identity=originals['identity']
    module.h.streamed_identity=originals['streamed'];module.mod.read=originals['read']
  register('prior.reject.'+name,action,{'rejected':True,'status':'stale_input'})
 prior_fault('receipt-hash','identity',PRIOR)
 prior_fault('retained-input-tree','files',PRIOR.parent/'inputs')
 prior_fault('original-verifier-input','identity',module.s1.SUITE_MANIFEST)
 prior_fault('live-package-selection','files',module.s1.PACKAGE)
 prior_fault('staged-candidate-tree','files',PRIOR.parent/'candidate-addon')
 prior_fault('original-artifact','files',prior['original_artifact']['path'])
 prior_fault('retained-artifact','files',prior['original_artifact']['retained'])
 prior_fault('retained-engine-log','streamed',prior['raw_engine_logs'][0]['retained'])
 prior_fault('source-job-tree','files',Path(prior['source_build_result']['result_path']).parent)
 prior_fault('retained-source-job-tree','files',PRIOR.parent/'source-build-job')
 prior_fault('source-job-receipt-read','read',prior['source_build_result']['result_path'])
 prior_fault('outer-job-receipt-read','read',prior['job']['result_path'])
 prior_fault('raw-compile-receipt-hash','identity',prior['raw_results']['compile']['path'])
 prior_fault('raw-compile-receipt-read','read',prior['raw_results']['compile']['path'])
 prior_fault('process-log','streamed',prior['commands'][0]['stdout'])
 prior_fault('generated-source-map','identity',prior['generated_source_map']['path'])
 prior_fault('adapter-source-map','identity',prior['adapter_source_map']['path'])

 if args.include_main_fault:
  def main_fault():
   original_job=module.mod.Job;original_argv=list(sys.argv);output=io.StringIO();status=None
   class InertJob:
    def __init__(self,project,*a,**k):
     self.project=Path(project);self.path=self.project/'.beryl-mod/jobs/INERT';self.path.mkdir(parents=True)
     self.result={'raw_logs':[],'inert_stub':True,'actual_processes_started':0}
    def snapshot(self):return None
    def run(self,*a,**k):
     home=self.project.parent
     save(home/'INERT.marker.json',{'scope':'Python-only Job.run replacement; no host/compiler/engine executed'})
     save(home/'engine-compile.json',{'schema_version':1,'stage':'workbench_compile','status':'timeout',
       'result':{'Ok':False,'Stage':'Timeout','ExitCode':-1,'ErrorCount':None,'LogDir':None},'INERT':True})
     (home/'inputs/INERT.extra').write_bytes(b'secondary stale evidence')
     raise module.mod.Failure('INERT primary compile timeout','timeout')
   engine=Path(prior['engine_input']['path']);tool=next(Path(n).parents[1]for n in prior['verification_inputs']if Path(n).name=='Find-Workbench.ps1')
   fake_host=work/'INERT-pwsh.exe';fake_host.write_bytes(b'nonexecuting fixture; never launched')
   try:
    module.mod.Job=InertJob
    sys.argv=[str(TARGET),'--candidate-receipt',str(PRIOR),'--expect-receipt-sha256',prior_id['sha256'],
              '--powershell-host',str(fake_host),'--engine-exe',str(engine),'--workbench-tools',str(tool),'--run']
    try:
     with contextlib.redirect_stdout(output):module.main()
    except module.mod.Failure as exc:status=exc.status
   finally:module.mod.Job=original_job;sys.argv=original_argv
   lines=[line.removeprefix('Receipt: ')for line in output.getvalue().splitlines()if line.startswith('Receipt: ')]
   if len(lines)!=1:raise AssertionError('Inert main did not retain exactly one final receipt: '+output.getvalue())
   path=Path(lines[0]);saved=json.loads(path.read_bytes())
   save(work/'inert-main-observation.json',{'receipt':identity(path),'stdout':output.getvalue(),'scope':'synthetic Job.run timeout, no process executed'})
   return{'primary_status':status,'receipt_status':saved['status'],'primary_message':saved['failure']['message'],
          'secondary_guard_recorded':'final_integrity_failure'in saved,'raw_timeout_retained':saved['raw_results']['compile']['result']['status']=='timeout',
          'no_processes':saved['job']['actual_processes_started']==0,'marker_present':(path.parent/'INERT.marker.json').is_file()}
  register('main.primary-timeout-preserved-through-stale-final-guard',main_fault,
           {'primary_status':'timeout','receipt_status':'timeout','primary_message':'INERT primary compile timeout',
            'secondary_guard_recorded':True,'raw_timeout_retained':True,'no_processes':True,'marker_present':True})
 register('prior.final-original-evidence-still-valid',prior_positive,{'accepted':True})

 def hardlinked_cache():
  home=work/'trees/hardlinked-cache';addon=home/'addon';addon.mkdir(parents=True)
  (addon/'addon.gproj').write_bytes(b'inert project\n')
  target=home/'owned-alias-target.rdb';target.write_bytes(b'owned cache fixture')
  os.link(target,addon/'resourceDatabase.rdb')
  if (addon/'resourceDatabase.rdb').stat().st_nlink!=2:
   raise AssertionError('Owned cache hardlink fixture does not have two links')
  observed=rejection(lambda:module.checked_tree(addon,{'addon.gproj':hashlib.sha256(b'inert project\n').hexdigest()},True))
  observed['fixture_link_count']=2
  return observed
 register('tree.root-cache-hardlink-rejected',hardlinked_cache,{'rejected':True,'status':'stale_input','fixture_link_count':2})

 expected_ids=[name for name,_,_ in cases]
 assert len(expected_ids)==len(set(expected_ids))
 paths=[Path(__file__).resolve(),TARGET,PRIOR,module.SOURCE,module.TEMPLATE,module.s1.HELPER,module.s1.SUITE_MANIFEST,module.s1.RESOURCE_HELPER]
 paths += [p for p in(module.TRANSPORT,module.CHECKER)if p.exists()]
 paths += module.mod.bundle_paths()
 frozen={str(p):identity(p)for p in sorted(set(paths))};retained=[]
 for index,p in enumerate(sorted(set(paths))):
  destination=work/'inputs'/(str(index).zfill(3)+'-'+p.name);destination.parent.mkdir(parents=True,exist_ok=True)
  raw=p.read_bytes()
  with destination.open('xb')as stream:
   if stream.write(raw)!=len(raw):raise OSError('Short source retention')
  assert identity(destination)['sha256']==frozen[str(p)]['sha256']
  retained.append({'original':frozen[str(p)],'retained':identity(destination)})
 record={'schema_version':1,'operation':'verify.tablet_existing_suites.staging.inert','status':'failure',
  'expected_case_ids':expected_ids,'cases':[],'inputs':frozen,'retained_inputs':retained,
  'scope':{'python':'pure admission and owned filesystem fixtures','prior_S1':'read_only','filesystem_faults':'injected_observations',
   'main_fault':'nonexecuting Job.run stub'if args.include_main_fault else'not_selected','host':'not_run','powershell':'not_run',
   'compiler':'not_run','engine':'not_run','process_signals':'not_run','tablet_suites':'not_run','installation':'unchanged'}}
 save(work/'planned.json',{'expected_case_ids':expected_ids,'inputs':frozen,'scope':record['scope']})
 for index,(name,action,wanted)in enumerate(cases):
  observation=None;exception=None
  try:observation=action()
  except BaseException as exc:exception={'type':type(exc).__name__,'message':str(exc),'status':getattr(exc,'status',None)}
  good=type(observation)is dict and exception is None and all(type(observation.get(k))is type(v)and observation[k]==v for k,v in wanted.items())
  row={'id':name,'status':'success'if good else'failure','expected':wanted,'observation':observation,'exception':exception}
  record['cases'].append(row);save(work/'cases'/(str(index).zfill(3)+'.json'),row)
 record['case_set_complete']=[row['id']for row in record['cases']]==expected_ids
 record['source_unchanged']={str(p):identity(p)for p in sorted(set(paths))}==frozen
 record['expected_count']=len(expected_ids);record['passed_count']=sum(row['status']=='success'for row in record['cases'])
 record['status']='success'if record['case_set_complete']and record['source_unchanged']and record['passed_count']==len(expected_ids)else'failure'
 save(work/'result.json',record)
 print(json.dumps({'receipt':identity(work/'result.json'),'status':record['status'],'expected':len(expected_ids),'passed':record['passed_count'],
  'target':frozen[str(TARGET)],'nonpassing':[row for row in record['cases']if row['status']!='success']}),flush=True)
 return 0 if record['status']=='success'else 1
if __name__=='__main__':raise SystemExit(main())
