#!/usr/bin/env python3
"""Experimental actual UI/frame/native-destruction fixture; no live promotion."""
from pathlib import Path
import argparse,hashlib,importlib.util,json,re,sys,tempfile
sys.dont_write_bytecode=True
root=Path(__file__).resolve().parents[1]
def module(name,path,sha=None):
    raw=path.read_bytes()
    if sha is not None: assert hashlib.sha256(raw).hexdigest()==sha,str(path)
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec)
    sys.modules[name]=m
    exec(compile(raw,str(path),'exec'),m.__dict__);return m
p=module('ui_source_foundation',root/'scripts/prepare-tablet-native-callbacks.py','62bb44d64e4fb830777196855eb8febdf0df3afa2cb3c86e7c900c62090e9471')
h,mod,s1=p.h,p.mod,p.s1
readiness_path=root/'scripts/verify-host-readiness.py'
readiness=module('ui_bounded_host_preflight',readiness_path,'0067128fa4754d582a3930415ec77991773475d936b204e3be560f4d9928e648')
package=root/'packages/sparkos/tablet-ui-native-probe'
CONTRACT_SHA='b06b5181b084787fa8b3fa959930b72d5544d21045a9397307f7179067858f27'
SOURCE=root/'build/tablet native preparation & spaces-flxq8l36/results.json'
SOURCE_SHA='4f5250df9a163cb91c362345c848d997d7fb9c096a654d0805052b015cd4e424'
oracle=module('ui_independent_oracle',package/'oracle.py','8524b05471b57bb09a82a3f71c7979d239e71535fe298711ad32895062cb3f10')
fields=module('ui_transport_fields',package/'verify_runtime_source.py','25801b76333f54693d2d63ec262670d1eff8a628d4143599a6929a7bfed0c5e6')
instrumenter=module('ui_native_instrumentation',package/'instrumentation.py','0167c3025abc3c8aa9c31417f2ff28c283f5d0350a65b0dcbd7a6b6fe442f1a6')
PROFILE=fields.PROFILE
STAGES=['load','play','spawn']+['run'+str(i)for i in range(7)]+['stop']
RPC_STAGES=['load','play','spawn','run0','run1','natural.first','run2','run3','run4','natural.reopen','run5','run6','stop']
host=Path('C:/Users/moham/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/powershell/pwsh.exe')
engine=Path('C:/Program Files (x86)/Steam/steamapps/common/Arma Reforger Tools/Workbench/ArmaReforgerWorkbenchSteamDiag.exe')
toolroot=Path('C:/Users/moham/Desktop/reforger-workbench-plugin')
compiler=root/'build/oct08-wrapper-cli-l8ci669v/beryl.exe'
adapter=root/'scripts/tablet-ui-native-engine.ps1'
bundle_path=root/'build/ui-receipt-bundle-prototype-15652ce152a543b8870a52673188ed59/hydrate_bundle_v2.py'
bundle=module('ui_bounded_receipt_hydration',bundle_path,'b3e1d08c4d386779b1a87b0671740b59de75ef627e809f3445b95b1138569022')
base_project=Path('C:/Program Files (x86)/Steam/steamapps/common/Arma Reforger/addons/data/ArmaReforger.gproj')
PROJECT_ID='BerylTabletUINativeN1bPrototype'
WORLD='worlds/BerylTabletUINative.ent'
RPC_PATH='scripts/WorkbenchGameCommon/BerylTabletUINative.c'
UI_PATH='scripts/Game/SparkOSMesh/UI/SPK_TabletUI.c'
def selected_package():
    required={'contract.json','instrumentation.py','observer.c.in','runtime-driver.c.in','verify_source.py','verify_runtime_source.py','oracle.py','verify_oracle.py'}
    actual={x.name for x in package.iterdir()if x.is_file()}
    h.require(required<=actual and actual-required<= {'README.md'},'UI package source set differs')
    h.require(all(x.is_file()or x.name=='__pycache__'and x.is_dir()for x in package.iterdir()),'Unexpected UI package namespace')
    return {name:mod.digest(mod.read(package/name))for name in sorted(actual)}
def normalized_native(value):
    texts=fields.STRING_FIELDS;bools=fields.BOOL_FIELDS;ints=fields.INT_FIELDS;arrays=fields.ARRAY_FIELDS
    names=set(texts+bools+ints+arrays)
    h.require(type(value)is dict and not(set(value)-names) and names-set(value)<=set(arrays),'Native UI envelope fields differ')
    n={};codec={'schema_version':1,'numeric_boolean_fields':[],'omitted_empty_arrays':[]}
    for key in texts:
        h.require(type(value[key])is str and len(value[key])<=2048 and '\0'not in value[key],'Native UI wire text differs');n[key]=value[key]
    for key in bools:
        v=value[key];h.require(type(v)is bool or type(v)is int and v in (0,1),'Native UI Boolean differs');n[key]=bool(v)
        if type(v)is int:codec['numeric_boolean_fields'].append(key)
    for key in ints:
        v=value[key];h.require(type(v)is int and -2147483648<=v<=2147483647,'Native UI integer differs');n[key]=v
    for key in arrays:
        if key in value:n[key]=value[key]
        else:
            h.require((key=='rows'and n['row_count']==0)or(key=='caseIds'and n['executed']==0),'Omitted nonempty UI collection')
            n[key]=[];codec['omitted_empty_arrays'].append(key)
        h.require(type(n[key])is list,'UI wire collection not a list')
    h.require(0<=n['action_count']<=7 and len(n['rows'])==n['row_count']and len(n['caseIds'])==n['action_count']==n['executed'],'Native UI row/case count differs')
    h.require(n['caseIds']==list(oracle.CASE_IDS[:n['action_count']]),'Native UI action prefix differs')
    h.require(n['checksum']==oracle.checksum(n['rows'])and n['raw_bytes']==sum(len(x)+1 for x in n['rows']),'Native UI checksum/bytes differ')
    return n,codec
def typed_equal(a,b):
    if type(a)is not type(b):return False
    if type(a)is dict:return set(a)==set(b)and all(typed_equal(a[k],b[k])for k in a)
    if type(a)is list:return len(a)==len(b)and all(typed_equal(x,y)for x,y in zip(a,b))
    return a==b


def validate_read_lease(r,manifest,manifest_identity,tracked):
    lease=r.get('read_lease')
    keys={'schema_version','policy','status','acquisition_status','release_status','expected_count','opened_count','released_count',
          'entries','errors','open_started_ms','open_completed_ms','open_duration_ms','close_started_ms','close_completed_ms',
          'close_duration_ms','fast_checks','fast_check_count','full_checks_with_handles','post_release_full_check',
          'byte_identity','native_open_dispose_not_hard_cancelled'}
    h.require(type(lease)is dict and set(lease)==keys,'Read lease envelope differs')
    h.require(type(lease['schema_version'])is int and lease['schema_version']==1 and
              lease['policy']=='FileMode.Open/FileAccess.Read/FileShare.Read' and lease['status']=='released' and
              lease['acquisition_status']=='complete' and lease['release_status']=='complete' and
              lease['errors']==[] and type(lease['errors'])is list and lease['post_release_full_check']is True and
              lease['native_open_dispose_not_hard_cancelled']is True and
              lease['byte_identity']=='hashed_while_held; fast_checks_length_and_readability_only','Incomplete read lease outcome')
    for key in('expected_count','opened_count','released_count'):
        h.require(type(lease[key])is int and lease[key]==104,'Read lease count differs')
    h.require(type(lease['full_checks_with_handles'])is int and lease['full_checks_with_handles']==1,'Held full-check coverage differs')
    expected={}
    def add(path,kind,identity):
        key=str(Path(path).resolve()).casefold()
        h.require(key not in expected,'Duplicate read lease identity')
        expected[key]=(kind,identity['sha256'],identity['bytes'])
    for name,sha in manifest['files'].items():
        item=h.identity(addon/name);h.require(item['sha256']==sha,'Leased addon bytes changed','stale_input');add(addon/name,'addon',item)
    add(adapter,'adapter',tracked[str(adapter)])
    add(manifest_identity['path'],'manifest',manifest_identity)
    for name in('Find-Workbench.ps1','Invoke-WorkbenchRpc.ps1'):
        path=toolroot/'scripts'/name;add(path,'plugin',tracked[str(path)])
    add(engine,'engine',record['engine_input'])
    h.require(len(expected)==104 and type(lease['entries'])is list and len(lease['entries'])==104,'Read lease basis differs')
    seen=set()
    for entry in lease['entries']:
        h.require(type(entry)is dict and set(entry)=={'path','kind','expected_sha256','sha256','bytes','status','release_status'},'Read lease entry differs')
        h.require(type(entry['path'])is str and len(entry['path'])<=32768 and '\0'not in entry['path'] and
                  Path(entry['path']).is_absolute(),'Read lease path shape differs')
        key=str(Path(entry['path']).resolve()).casefold()
        h.require(key in expected and key not in seen,'Read lease path is absent or duplicated');seen.add(key)
        kind,sha,size=expected[key]
        h.require(entry['kind']==kind and entry['expected_sha256']==sha and entry['sha256']==sha and
                  type(entry['bytes'])is int and entry['bytes']==size and entry['status']=='verified_held' and
                  entry['release_status']=='released','Read lease source/release identity differs')
    for key in('open_started_ms','open_completed_ms','open_duration_ms','close_started_ms','close_completed_ms','close_duration_ms'):
        h.require(type(lease[key])is int and 0<=lease[key]<=r['elapsed_ms'],'Read lease timing unavailable')
    calls=[entry for entry in r['rpcs']if entry['stage']in RPC_STAGES and entry['stage']not in('load','play')]
    play=[entry for entry in r['rpcs']if entry['stage']=='play']
    h.require(play and calls and play[-1]['elapsed_ms']+play[-1]['duration_ms']<=lease['open_started_ms']<=
              lease['open_completed_ms']<=calls[0]['elapsed_ms'] and calls[-1]['elapsed_ms']+calls[-1]['duration_ms']<=
              lease['close_started_ms']<=lease['close_completed_ms']<=r['elapsed_ms'],'Read lease capture boundary differs')
    h.require(lease['open_duration_ms']<=lease['open_completed_ms']-lease['open_started_ms']+2 and
              lease['close_duration_ms']<=lease['close_completed_ms']-lease['close_started_ms']+2,'Read lease operation duration differs')
    checks=lease['fast_checks']
    h.require(type(checks)is list and type(lease['fast_check_count'])is int and
              lease['fast_check_count']==len(checks)==2*len(calls) and len(checks)<=512,'Read lease fast-check coverage differs')
    previous=lease['open_completed_ms']
    for check in checks:
        h.require(type(check)is dict and set(check)=={'elapsed_ms','duration_ms','held_count','file_count','directory_count','bytehash'},'Read lease check fields differ')
        h.require(type(check['elapsed_ms'])is int and previous<=check['elapsed_ms']<=lease['close_started_ms'] and
                  type(check['duration_ms'])is int and 0<=check['duration_ms']<=check['elapsed_ms'] and
                  type(check['held_count'])is int and check['held_count']==104 and
                  type(check['file_count'])is int and check['file_count']==99 and
                  type(check['directory_count'])is int and check['directory_count']==len(h.parent_directories(manifest['files'])) and
                  check['bytehash']=='not_reexecuted; read-sharing leases held','Read lease fast-check evidence differs')
        previous=check['elapsed_ms']
    for index,call in enumerate(calls):
        before,after=checks[2*index:2*index+2]
        h.require(before['elapsed_ms']<=call['elapsed_ms']<=after['elapsed_ms']<=call['elapsed_ms']+call['duration_ms'],
                  'Read lease checks are not linked to their RPC')


def validate_startup_identity(r,expected_engine):
    # The source-owned Assert-Deadline also bounds the real startup stage.
    # Its pre-Start clock origin is not serialized, so this independently
    # checks the observed identity window rather than reconstructing it.
    import datetime
    def integer(value,minimum,maximum):
        return type(value)is int and minimum<=value<=maximum
    def image(value):
        h.require(type(value)is str and 0<len(value)<=32768 and value.isascii()and
                  '\0'not in value and re.match(r'^[A-Za-z]:[\\/]',value)is not None,
                  'Startup image path shape differs')
        return value.replace('/','\\').rstrip('\\').lower()
    h.require(type(r)is dict and r.get('status')=='success'and
              integer(r.get('elapsed_ms'),0,179999),'Startup success/time envelope differs')
    startup=r.get('startup')
    fields={'mechanism','argv','working_directory','use_shell_execute','create_no_window','window_style',
            'launch_returned','polls','process_id','identity_checks','identity_status','identity_polls',
            'identity_start_ticks','identity_start_ticks_unit','identity_start_time','identity_started_ms',
            'identity_completed_ms','identity_duration_ms'}
    h.require(type(startup)is dict and set(startup)==fields,'Startup identity envelope fields differ')
    h.require(startup['mechanism']=='owned_tablet_ui_native_n1b_n3'and type(startup['argv'])is list and
              all(type(v)is str and 0<len(v)<=32768 and '\0'not in v for v in startup['argv'])and
              type(startup['working_directory'])is str and 0<len(startup['working_directory'])<=32768 and
              '\0'not in startup['working_directory']and startup['use_shell_execute']is False and
              startup['create_no_window']is True and startup['window_style']=='Hidden'and
              startup['launch_returned']is True and integer(startup['polls'],0,63),
              'Startup launch typed fields differ')
    unit='dotnet_datetime_0001_utc_100ns'
    ticks=startup['identity_start_ticks'];pid=startup['process_id']
    h.require(integer(pid,1,2147483647)and integer(ticks,1,3155378975999999999)and
              startup['identity_start_ticks_unit']==unit and startup['identity_status']=='verified',
              'Startup retained identity differs')
    stamp=startup['identity_start_time']
    match=re.fullmatch(r'(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})\.(\d{7})Z',stamp)if type(stamp)is str else None
    h.require(match is not None,'Startup UTC start-time shape differs')
    try:
        y,mo,d,hh,mm,ss,fraction=map(int,match.groups())
        instant=datetime.datetime(y,mo,d,hh,mm,ss)
        actual_ticks=((instant.toordinal()-1)*86400+hh*3600+mm*60+ss)*10000000+fraction
    except (ValueError,OverflowError):
        h.require(False,'Startup UTC start-time calendar differs')
    h.require(actual_ticks==ticks,'Startup UTC timestamp/ticks differ')
    started,completed,duration=(startup[k]for k in('identity_started_ms','identity_completed_ms','identity_duration_ms'))
    h.require(all(integer(v,0,r['elapsed_ms'])for v in(started,completed,duration))and
              started<=completed and duration==completed-started and duration<30000,
              'Startup recorded identity window exceeds deadline or differs')
    rows=startup['identity_checks']
    h.require(type(rows)is list and 1<=len(rows)<=64 and
              integer(startup['identity_polls'],0,63)and startup['identity_polls']==len(rows)-1,
              'Startup identity observation count differs')
    row_fields={'attempt','elapsed_ms','process_id','start_ticks','start_ticks_unit','module_present','raw_path',
                'normalized_path','status','query_error'}
    previous=started;expected_image=image(str(expected_engine))
    for index,row in enumerate(rows):
        h.require(type(row)is dict and set(row)==row_fields,'Startup identity row fields differ')
        h.require(integer(row['attempt'],0,63)and row['attempt']==index and
                  integer(row['elapsed_ms'],started,completed)and row['elapsed_ms']>=previous and
                  integer(row['process_id'],1,2147483647)and row['process_id']==pid and
                  integer(row['start_ticks'],1,3155378975999999999)and row['start_ticks']==ticks and
                  row['start_ticks_unit']==unit and type(row['module_present'])is bool and row['query_error']is None,
                  'Startup identity sequence/PID/ticks/query/timing differs')
        previous=row['elapsed_ms']
        if index<len(rows)-1:
            h.require(row['status']=='pending'and(row['raw_path']is None or
                      type(row['raw_path'])is str and row['raw_path']=='')and row['normalized_path']is None and
                      (row['module_present']is True or row['raw_path']is None),
                      'Startup preceding identity is not a pending empty image')
        else:
            h.require(row['status']=='verified'and row['module_present']is True and image(row['raw_path'])==expected_image and
                      type(row['normalized_path'])is str and
                      row['normalized_path']==row['raw_path'].replace('/','\\').rstrip('\\')and
                      image(row['normalized_path'])==expected_image,
                      'Startup final image identity differs')
    session=r.get('session')
    h.require(type(session)is dict and set(session)=={'process_id','start_ticks','executable','project','reused','start_time'}and
              integer(session['process_id'],1,2147483647)and session['process_id']==pid and
              integer(session['start_ticks'],1,3155378975999999999)and session['start_ticks']==ticks and
              session['start_time']==stamp and session['reused']is False and image(session['executable'])==expected_image,
              'Startup final identity differs from retained session')
    checks=r.get('session_checks')
    h.require(type(checks)is list and len(checks)>0 and type(checks[0])is dict and checks[0].get('site')=='startup.identity',
              'Startup identity session check missing')
    previous=completed
    for row in checks:
        h.require(type(row)is dict and set(row)=={'site','process_id','start_ticks','executable','elapsed_ms'}and
                  type(row['site'])is str and 0<len(row['site'])<=256 and
                  integer(row['process_id'],1,2147483647)and row['process_id']==pid and
                  integer(row['start_ticks'],1,3155378975999999999)and row['start_ticks']==ticks and
                  image(row['executable'])==expected_image and integer(row['elapsed_ms'],previous,r['elapsed_ms']),
                  'Startup/session ledger identity or timing differs')
        previous=row['elapsed_ms']
    return {'schema_version':1,'status':'verified','identity_observations':len(rows),'identity_polls':len(rows)-1,
            'start_ticks_unit':unit,'recorded_identity_window_ms':duration,
            'stage_clock_scope':'pre-Start stage origin not serialized; source guard separately bounds entire startup stage'}


def validate_runtime(r,expected,manifest,manifest_identity,tracked):
    h.require(type(r)is dict and type(r.get('schema_version'))is int and r['schema_version']==1 and type(r.get('elapsed_ms'))is int and 0<=r['elapsed_ms']<180000,'UI runtime schema/time differs')
    h.require(r['status']=='success'and r['stage']=='native_ui_transport_complete'and r['failure']is None and r['evidence_errors']==[]and r['cleanup_errors']==[]and r['cleanup']in('owned_process_stopped','owned_process_already_exited'),'UI runtime lacks confirmed success/cleanup')
    h.require(r['profile']==PROFILE and r['token']==expected['token']and r['source_sha256']==expected['source_sha256']and r['source_contract_sha256']==CONTRACT_SHA and r['project_id']==PROJECT_ID,'UI artifact identity differs','stale_input')
    h.require(r['engine_sha256']==record['engine_input']['sha256']and r['engine_bytes']==record['engine_input']['bytes']and Path(r['engine_path']).resolve()==engine.resolve()and r['engine_version']=='1.8.0.13'and r['adapter_sha256']==tracked[str(adapter)]['sha256'],'UI engine/adapter differs','stale_input')
    h.require(r['input_manifest']=={'path':str(manifest_identity['path']),'sha256':manifest_identity['sha256']}and typed_equal(r['staged_inputs'],manifest),'Pinned UI manifest differs','stale_input')
    argv=['-gproj',str(addon/'addon.gproj'),'-noOpenLastResource','-scriptAuthorizeAll','-forceUpdate']
    h.require(r['arguments']==argv and r['startup']['argv']==argv,'UI launch arguments differ')
    session=r['session'];h.require(type(session['process_id'])is int and session['process_id']>0 and type(session['start_ticks'])is int and session['reused']is False and Path(session['project']).resolve()==addon.resolve(),'Owned UI session differs')
    h.require(r['raw_log_observation']=='snapshot_after_confirmed_owned_exit','UI logs captured before owned exit')
    for key in('save','physical_ui_input','multiplayer','visual_review','policy_changes'):h.require(r[key]=='not_run','Unexpected UI operation')
    h.require([x['action']for x in r['stages']]==STAGES and all(x['status']=='completed'and type(x['polls'])is int and 0<=x['polls']<=64 and type(x['elapsed_ms'])is int and 0<=x['elapsed_ms']<30000 and type(x['mutation_requests'])is int and x['mutation_requests']==1 for x in r['stages']),'UI stage ledger incomplete')
    ledger=r['rpcs'];h.require(12<=len(ledger)<=716,'UI RPC count exceeds bounds')
    stage_calls={name:[]for name in RPC_STAGES};previous_counters=None;prefix=[];previous_actions=0;previous_stage_index=0
    for index,entry in enumerate(ledger):
        reply=entry['result'];h.require(type(reply)is dict and set(reply)=={'Ok','Function','ErrorCode','Response','Raw'}and reply['Ok']is True and reply['ErrorCode']=='Ok'and entry['failure']is None and entry['failure_kind']is None and type(entry['timeout_ms'])is int and 0<entry['timeout_ms']<=8000 and 0<=entry['duration_ms']<entry['timeout_ms'],'UI RPC failure/time differs')
        raw=mod.parse(reply['Raw'].encode());h.require(typed_equal(raw,reply['Response'])and reply['Function']==entry['function'],'Raw UI RPC differs')
        if index==0:
            h.require(entry['stage']=='startup'and entry['function']=='GetLoadedProjects'and entry['params']=={}and set(raw)=={'Loaded Projects'},'Initial UI inventory missing')
            projects=raw['Loaded Projects'];h.require(type(projects)is list and len(projects)==len(set(projects))and PROJECT_ID in projects and set(projects)<={PROJECT_ID,'ArmaReforger','core'},'Loaded UI addons differ')
            continue
        h.require(entry['function']=='BerylTabletUINative'and entry['stage']in stage_calls and entry['params']=={'token':expected['token'],'action':entry['params']['action']}and entry['params']['action']in(entry['stage'],'status'),'Unregistered UI request')
        current_stage_index=RPC_STAGES.index(entry['stage'])
        h.require(previous_stage_index<=current_stage_index<=previous_stage_index+1,'UI RPC stages reordered or skipped')
        previous_stage_index=current_stage_index
        n,codec=normalized_native(raw)
        h.require(typed_equal(n,entry['normalized_response'])and typed_equal(codec,entry['codec']),'UI independent normalization differs')
        for k in expected:h.require(type(n[k])is type(expected[k])and n[k]==expected[k],'Compiled UI identity differs: '+k,'stale_input')
        h.require(n['current_project']=='./addons/data/ArmaReforger.gproj'and n['action']==entry['params']['action']and n['failure']==''and n['failures']==0 and n['outside_domain']is False,'UI progress outcome differs')
        h.require(n['rows'][:len(prefix)]==prefix and n['action_count']>=previous_actions,'UI progress lost/replaced prior observations','stale_input')
        prefix=n['rows'];previous_actions=n['action_count']
        h.require(n['stop_requested']is (entry['stage']=='stop'),'UI stop marker appeared at wrong boundary')
        if entry['stage']in('load','play'):
            h.require(all(n[k]==0 for k in('executed','owner_count','row_count','checksum','raw_bytes','action_count','frame_count','queue_count','init_count','delete_count','presuper_count','after_super_count'))and not any(n[k]for k in('actions_ready','first_progress_ready','reopen_progress_ready','final_focused')),'UI observations appeared before native spawn')
        else:
            h.require(n['phase']in(2,3,4)and n['status']in('pending','complete'),'UI observation phase/status differs')
            oracle.validate(n,expected,require_complete=False)
            if entry['stage'].startswith('natural.'):
                h.require(n['world_matches']and n['world_present']and n['game_world_present']and n['game_mode']and n['in_play_mode']and not n['edit_mode']and n['module_present']and n['api_present']and all(n[k]for k in('addon_world_resolved','world_path_resolved','resource_name_resolved'))and all(Path(n[k]).resolve()==(addon/WORLD).resolve()for k in('addon_world_path','world_absolute_path','resource_absolute_path'))and n['resource_name']=='{BE71572A20261010}'+WORLD and n['resource_path']==WORLD,'UI natural progress world provenance differs')
            if entry['stage']!='stop':h.require(all(n[k]==0 for k in('delete_count','presuper_count','after_super_count')),'UI deletion appeared before stop')
        counters=[n[k]for k in('load_requested','load_submitted','load_entered','load_resumed','load_returned')]
        h.require(all(v in(0,1)for v in counters)and counters[1]<=counters[0]and counters[2]<=counters[0]and counters[3]<=min(counters[1],counters[2])and counters[4]<=counters[3]and(not n['load_accepted']or counters[4]==1),'UI load progress differs')
        if previous_counters:h.require(all(a>=b for a,b in zip(counters,previous_counters)),'UI load progress reset')
        previous_counters=counters;stage_calls[entry['stage']].append(n)
    for stage in r['stages']:
        calls=stage_calls[stage['action']]
        h.require(len(calls)==stage['polls']+1 and typed_equal(calls[-1],stage['response']),'UI stage linkage differs')
        h.require(calls[0]['action']==stage['action']and all(n['action']=='status'for n in calls[1:]),'UI stage repeated mutation')
        n=calls[-1];wanted=('ready',0)if stage['action']in('load','play')else('complete',4)if stage['action']=='stop'else('pending',2)
        h.require((n['status'],n['phase'])==wanted,'UI stage phase/status differs')
        h.require(n['module_present']and n['api_present']and n['world_matches']and n['world_present']and all(n[k]for k in('addon_world_resolved','world_path_resolved','resource_name_resolved'))and all(Path(n[k]).resolve()==(addon/WORLD).resolve()for k in('addon_world_path','world_absolute_path','resource_absolute_path'))and n['resource_name']=='{BE71572A20261010}'+WORLD and n['resource_path']==WORLD,'UI world provenance differs')
        h.require(all(n[k]==1 for k in('load_requested','load_submitted','load_entered','load_resumed','load_returned'))and n['load_accepted'],'UI stage lacks one-shot load')
        if stage['action']in('load','stop'):h.require(n['edit_mode']and not n['game_mode']and not n['in_play_mode'],'UI edit boundary differs')
        else:h.require(not n['edit_mode']and n['game_mode']and n['in_play_mode']and n['game_world_present'],'UI play boundary differs')
        if stage['action'].startswith('run'):
            index=int(stage['action'][3:]);h.require(n['action_count']==index+1 and n['init_count']==4 and n['owner_count']==2,'UI action boundary differs')
        if stage['action']=='spawn':h.require(n['action_count']==0 and n['init_count']==4 and n['owner_count']==2,'UI native initialization differs')
    waits=r['natural_progress_windows'];h.require(type(waits)is list and len(waits)==2,'UI timed progress waits missing')
    wait_fields={'window','after_action','required_minimum_wall_ms','status','begin_total_ms','end_wait_total_ms','wait_elapsed_ms','clock_source','stopwatch_frequency','wait_begin_ticks','wait_end_ticks','ready_total_ms','elapsed_ms','polls','response','mutation_requests'}
    for wait,window,action_index in zip(waits,('first','reopen'),(1,4)):
        h.require(type(wait)is dict and set(wait)==wait_fields and wait['window']==window and wait['status']=='completed'and wait['clock_source']=='Stopwatch','UI progress ledger fields differ')
        for k in wait_fields-{'window','status','clock_source','response'}:h.require(type(wait[k])is int,'UI progress ledger integer differs')
        h.require(wait['after_action']==action_index and wait['required_minimum_wall_ms']==600 and wait['mutation_requests']==0 and wait['wait_begin_ticks']==0 and wait['stopwatch_frequency']>0 and wait['wait_end_ticks']>=0,'UI timed progress policy differs')
        h.require(600<=wait['wait_elapsed_ms']<=wait['end_wait_total_ms']-wait['begin_total_ms']+2 and 600<=wait['end_wait_total_ms']-wait['begin_total_ms'] and 0<=wait['begin_total_ms']<=wait['end_wait_total_ms']<=wait['ready_total_ms']<=r['elapsed_ms']and 600<=wait['elapsed_ms']<30000 and 1<=wait['polls']<=64,'UI bounded natural wait differs')
        h.require(all(0<=wait[k]<=9223372036854775807 for k in wait_fields-{'window','status','clock_source','response'}),'UI progress integer outside signed-i64')
        h.require(wait['elapsed_ms']+2>=wait['ready_total_ms']-wait['begin_total_ms'],'UI progress stage elapsed cannot cover its observed window')
        h.require(600*wait['stopwatch_frequency']<=wait['wait_end_ticks']*1000<=(wait['wait_elapsed_ms']+2)*wait['stopwatch_frequency'],'UI progress ticks and elapsed differ')
        calls=[x for x in ledger if x['stage']=='natural.'+window];prior_calls=[x for x in ledger if x['stage']=='run'+str(action_index)]
        h.require(len(calls)==wait['polls']and all(x['params']['action']=='status'for x in calls)and typed_equal(wait['response'],stage_calls['natural.'+window][-1]),'UI natural wait response/RPC linkage differs')
        h.require(prior_calls[-1]['elapsed_ms']+prior_calls[-1]['duration_ms']<=wait['begin_total_ms']and wait['end_wait_total_ms']<=calls[0]['elapsed_ms']and calls[-1]['elapsed_ms']+calls[-1]['duration_ms']<=wait['ready_total_ms'],'UI wait not linked to actual action/status')
        n=stage_calls['natural.'+window][-1]
        h.require(n['phase']==2 and n['status']=='pending'and n['action_count']==action_index+1 and n[window+'_progress_ready']and n['game_mode']and n['in_play_mode']and not n['edit_mode'],'UI observed progress unavailable')
    completion=r['completion'];h.require(typed_equal(completion,stage_calls['stop'][-1])and completion['stop_requested']is True,'UI final completion differs')
    verified=oracle.validate(completion,expected)
    for row in r['session_checks']:
        h.require(row['process_id']==session['process_id']and row['start_ticks']==session['start_ticks']and
                  Path(row['executable']).resolve()==engine.resolve(),'Owned native session check differs')
    h.require(len(r['session_checks'])==2*len(ledger)+r['startup']['polls']+2,'Owned session check coverage differs')
    checks=r['session_checks'];polls=r['startup']['polls']
    h.require(type(polls)is int and 0<=polls<64,'Native startup poll bound differs')
    sites=['startup.identity']+['port.check']*(polls+1)
    for entry in ledger:sites+=['before.'+entry['function'],'after.'+entry['function']]
    h.require([row['site']for row in checks]==sites,'Native ownership check sites/order differ')
    times=[row['elapsed_ms']for row in checks]
    h.require(all(type(v)is int and 0<=v<=r['elapsed_ms']for v in times) and times==sorted(times),
              'Native ownership check times differ')
    port=r['port_checks'];h.require(type(port)is list and len(port)==polls+1,'Native listener check coverage differs')
    for index,row in enumerate(port):
        h.require(type(row['elapsed_ms'])is int and 0<=row['elapsed_ms']<=checks[index+1]['elapsed_ms'] and
                  type(row['listening'])is bool,'Native listener check fields differ')
        if index<polls:h.require(row['listening']is False and row['owning_process']is None,'Native listener appeared before final poll')
        else:h.require(row['listening']is True and type(row['owning_process'])is int and
                       row['owning_process']==session['process_id'],'Native listener ownership differs')
    h.require([row['elapsed_ms']for row in port]==sorted(row['elapsed_ms']for row in port),
              'Native listener check times reversed')
    h.require(type(r['port_query_errors'])is list and len(r['port_query_errors'])<=128 and
              all(row['category']=='ObjectNotFound' and type(row['elapsed_ms'])is int and
                  0<=row['elapsed_ms']<=r['elapsed_ms'] for row in r['port_query_errors']),
              'Native listener diagnostic interpretation differs')
    offset=polls+2
    for index,entry in enumerate(ledger):
        before,after=checks[offset+2*index:offset+2*index+2]
        h.require(type(entry['elapsed_ms'])is int and type(entry['duration_ms'])is int and
                  before['elapsed_ms']<=entry['elapsed_ms']<=after['elapsed_ms']<=entry['elapsed_ms']+entry['duration_ms']<=r['elapsed_ms'],
                  'Native RPC timing linkage differs')
        if index+1<len(ledger):h.require(entry['elapsed_ms']+entry['duration_ms']<=ledger[index+1]['elapsed_ms'],
                                       'Native RPC operations overlap or reverse')
    expected_tools={name:tracked[str(toolroot/'scripts'/name)]['sha256']for name in('Find-Workbench.ps1','Invoke-WorkbenchRpc.ps1')}
    h.require(r['tools']==expected_tools and r['raw_logs'],'Native tool identity or raw logs missing')
    total=0
    for row in r['raw_logs']:
        path=Path(row['retained']);h.require(path.resolve().is_relative_to(work.resolve())and h.identity(path)==
            {'path':str(path),'bytes':row['bytes'],'sha256':row['sha256']},'Native retained log differs','stale_input');total+=row['bytes']
    h.require(0<total<=64*1024*1024,'Native retained log aggregate differs')
    validate_startup_identity(r,engine)
    validate_read_lease(r,manifest,manifest_identity,tracked)
    return verified

def capture_runtime(record,path):
    h.capture_adapter(record,'runtime',path)
    item=record['raw_results'].get('runtime')
    if item is None:
        return
    header=item.get('result')
    try:
        full,evidence=bundle.hydrate(path,item['sha256'],scope=work)
    except (bundle.BundleFailure,OSError) as error:
        record['evidence_errors'].append({'stage':'runtime_bundle','type':type(error).__name__,'message':str(error)})
        raise mod.Failure('Runtime evidence bundle failed byte validation: '+str(error),'failure')from error
    item['physical_receipt_result']=header
    item['receipt_hydration']=evidence
    item['result']=full

def main():
    global work,record,addon
    cli=argparse.ArgumentParser(description=__doc__);cli.add_argument('--package-sha256',required=True);cli.add_argument('--run',action='store_true');cli.add_argument('--repair-widget-slots',action='store_true',help='Admit the pinned, candidate-only button content-frame repair')
    args=cli.parse_args()
    if re.fullmatch(r'[0-9a-f]{64}',args.package_sha256)is None:cli.error('Full frozen package fingerprint required')
    work=Path(tempfile.mkdtemp(prefix='tablet-ui-native-',dir=root/'build'))
    record={'schema_version':1,'operation':'verify.tablet_ui.n1b_n3.native','status':'failure','stage':'source_admission','scope':{'engine_compilation':'not_run','ui_opening':'not_run','native_frames':'not_run','native_deletion':'not_run','player_interaction':'not_admitted','multiplayer':'not_run','visual_review':'not_run','installation':'unchanged'},'commands':[],'raw_results':{},'evidence_errors':[]}
    guard=job=None
    try:
        raw=mod.read(SOURCE);h.require(mod.digest(raw)==SOURCE_SHA,'N0 receipt differs','stale_input');prior=mod.parse(raw)
        h.require(prior['status']=='success'and prior['stage']=='source_prepared'and len(prior['staged_file_set'])==92,'Exact N0 source baseline required')
        source_files=dict(prior['prepared_file_set'],**{'results.json':SOURCE_SHA})
        h.require(h.files(SOURCE.parent)==source_files,'Retained N0 tree differs','stale_input')
        for name,item in prior['verification_inputs'].items():h.require(h.identity(Path(name))==item,'N0 source input differs','stale_input')
        package_files=selected_package();h.require(mod.digest(mod.canonical(package_files))==args.package_sha256 and package_files['contract.json']==CONTRACT_SHA,'UI package selection differs','stale_input')
        fields.validate_source(mod.read(package/'runtime-driver.c.in'))
        for path,sha in ((host,'362a356ce7f0940ec74f73a8fc2c990a2cc24a38a11c90bbd8eca947110ad139'),(compiler,'76aeaacfea6866e66e3020f983eaa22089d545ad0f3b60fedfd28c3d58972bd7'),(mod.HERE/'engine-compile.ps1','ea923399c2060123812a6ea205760372de0e2fff29071117e0cf58ed64877121')):
            h.require(h.identity(path)['sha256']==sha,'Execution tool differs','stale_input')
        engine_identity=h.streamed_identity(engine);h.require(engine_identity['sha256']=='7dd36ca1f662b0c13669a4f2f7f10e3c461c2906b021e742272d64b3ab7e9798','Engine differs','stale_input')
        paths=[Path(__file__).resolve(),root/'scripts/prepare-tablet-native-callbacks.py',readiness_path,adapter,bundle_path,host,compiler,base_project]+[package/n for n in sorted(package_files)]+sorted(mod.HERE.glob('*.py'))+sorted(mod.HERE.glob('*.ps1'))+sorted(mod.HERE.glob('*.json'))+sorted((toolroot/'scripts').glob('*.ps1'))
        paths+= [root/'packages/sparkos/tablet-service-prototype/tablet-service.c.in']
        widget_patch=None
        if args.repair_widget_slots:
            patch_path=root/'build/oct10-tablet-chrome-content-transform.py'
            widget_patch=module('ui_reviewed_button_content_repair',patch_path,'450430b2ba4bc01f36b763edce0fea3703ab501d3673b009a650d80fd3975515')
            paths.append(patch_path)
            gui_path=root/'build/oct10-tablet-ui-gui-log-checker.py'
            gui_checker=module('ui_native_slot_log_gate',gui_path,'92c0844080fa14a9c51429cc4bfda5ad16e7e9aff451c3b4a4c2f8d22f579260')
            paths.append(gui_path)
        h.require(all(x.is_file()for x in paths)and len(paths)==len(set(paths))and len(paths)<=256,'Distinct bounded UI inputs required')
        tracked={str(path):h.identity(path)for path in paths}
        payloads={name:mod.read(Path(prior['candidate_path'])/name)for name in prior['staged_file_set']}
        h.require({name:mod.digest(data)for name,data in payloads.items()}==prior['staged_file_set'],'N0 candidate changed','stale_input')
        mapping_raw=mod.read(SOURCE.parent/'generated_source_map.json');h.require(mod.digest(mapping_raw)==source_files['generated_source_map.json'],'Source map changed','stale_input')
        rendered,symbols,_=s1.render(mod.parse(mapping_raw),payloads[prior['generated_file']['path']]);symbols.update(prior['symbols'])
        h.require(rendered==payloads[s1.TABLET],'Adapter linkage changed','stale_input')
        def expand(data):
            value=data.decode()
            for name,actual in symbols.items():
                h.require(re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*',actual)is not None,'Unsafe linkage')
                value=value.replace('@'+name+'@',actual)
            h.require(re.search(r'@[A-Z_]+@',value)is None,'Unresolved linkage');return value.encode()
        original=mod.read(root/'packages/sparkos/tablet-service-prototype/tablet-service.c.in');overlaid=instrumenter.adapter_overlay(original)
        h.require(expand(instrumenter.strip_adapter(overlaid,original))==rendered,'Adapter hooks not reversible')
        original_ui=payloads[UI_PATH];h.require(original_ui==payloads[UI_PATH],'Actual UI basis differs','stale_input')
        ui_overlay=instrumenter.ui_overlay(original_ui);h.require(instrumenter.strip_ui(ui_overlay,original_ui)==original_ui,'UI hooks not reversible')
        payloads[s1.TABLET]=expand(overlaid);payloads[UI_PATH]=ui_overlay
        record['widget_slot_repair']={'selected':bool(widget_patch),'scope':'candidate_only; no live MESH promotion'}
        if widget_patch:
            chrome_path='scripts/Game/SparkOSMesh/UI/SPK_TabletChrome.c'
            chrome_original=payloads[chrome_path];chrome_repaired=widget_patch.transform(chrome_original)
            admission=widget_patch.validate(chrome_repaired,chrome_original)
            h.require(widget_patch.restore(chrome_repaired,chrome_original)==chrome_original,'Widget repair is not reversible')
            payloads[chrome_path]=chrome_repaired
            record['widget_slot_repair'].update(admission=admission,generated_path=chrome_path,
                native_gui_errors='not_checked',native_event_propagation='not_run')
        payloads['scripts/Game/BerylTabletUINativeObserver.c']=expand(mod.read(package/'observer.c.in'))
        config='GameProject {\n ID "'+PROJECT_ID+'"\n GUID "BE71572C20261010"\n TITLE "Beryl Tablet UI Native Experimental"\n Dependencies {\n'
        for dep in prior['source_contract']['addon']['dependencies']:config+='  "'+dep+'"\n'
        payloads['addon.gproj']=(config+' }\n}\n').encode()
        assets={'Prefabs/BerylTabletUINative.et':b'GenericEntity {\n components {\n  SPK_BerylTabletUINativeObserver {\n  }\n }\n}\n','Prefabs/BerylTabletUINative.et.meta':b'MetaFileClass {\n Name "{BE71572B20261010}Prefabs/BerylTabletUINative.et"\n Configurations {\n  EntityTemplateResourceClass PC {\n  }\n }\n}\n',WORLD:b'Layer default {\n Index 0\n}\n',WORLD+'.meta':b'MetaFileClass {\n Name "{BE71572A20261010}worlds/BerylTabletUINative.ent"\n Configurations {\n  ENTResourceClass PC {\n  }\n  ENTResourceClass HEADLESS : PC {\n  }\n }\n}\n','worlds/BerylTabletUINative_Layers/default.layer':b'GenericWorldEntity world {\n}\n'}
        for name,data in assets.items():
            h.require(name not in payloads,'Fixture path collision')
            for ident in re.findall(rb'\{[0-9A-F]{16}\}',data):h.require(all(ident not in old for old in payloads.values()),'Fixture identifier collision')
            payloads[name]=data
        h.require(len(payloads)==98,'Exact 98-file UI foundation required')
        source_hash=mod.digest(mod.canonical({n:mod.digest(v)for n,v in payloads.items()}))
        token=mod.digest(mod.canonical({'source':source_hash,'source_contract':CONTRACT_SHA,'inputs':tracked,'engine':engine_identity}))
        addon=work/'candidate-addon';rpc=mod.read(package/'runtime-driver.c.in').decode()
        for name,value in {'TOKEN':token,'SOURCE_SHA256':source_hash,'SOURCE_CONTRACT_SHA256':CONTRACT_SHA,'WORLD_ABSOLUTE':(addon/WORLD).as_posix(),'CURRENT_GAME_PROJECT':'./addons/data/ArmaReforger.gproj'}.items():rpc=rpc.replace('@'+name+'@',value)
        h.require(re.search(r'@[A-Z_]+@',rpc)is None and RPC_PATH not in payloads,'RPC placeholder/collision')
        payloads[RPC_PATH]=rpc.encode();h.require(len(payloads)==99,'Exact UI candidate99 required')
        for name,data in payloads.items():h.write(addon/name,data)
        expected_files={n:mod.digest(v)for n,v in payloads.items()};p.prior_guard.checked_tree(addon,expected_files)
        h.write(work/'source-preparation-result.json',raw);h.write(work/'generated-source-map.json',mapping_raw)
        for i,path in enumerate(paths):
            data=mod.read(path);h.require(mod.digest(data)==tracked[str(path)]['sha256'],'Captured UI input differs','stale_input');h.write(work/'inputs'/(str(i).zfill(4)+'-'+path.name),data)
        own_inputs=h.files(work/'inputs')
        manifest={'schema_version':1,'profile':PROFILE,'files':expected_files};h.save_result(work/'input-manifest.json',manifest);manifest_identity=h.identity(work/'input-manifest.json')
        expected=oracle.expected_identity(token,source_hash,CONTRACT_SHA);h.save_result(work/'runtime-expected.json',expected);expected_identity=h.identity(work/'runtime-expected.json')
        h.save_result(work/'fixture-source-origins.json',{'schema_version':1,'policy':'trusted reversible overlays; raw generated lines retained; columns unavailable','basis':tracked,'generated_paths':[s1.TABLET,UI_PATH,'scripts/Game/BerylTabletUINativeObserver.c',RPC_PATH],'linkage':symbols})
        origin_identity=h.identity(work/'fixture-source-origins.json')
        record.update(source_preparation_result=h.identity(SOURCE),engine_input=engine_identity,verification_inputs=tracked,candidate_path=str(addon),staged_file_set=expected_files,input_manifest=manifest_identity,runtime_expected=expected_identity,source_origins=origin_identity,token=token,source_sha256=source_hash,source_contract_sha256=CONTRACT_SHA,package_sha256=args.package_sha256,package_files=package_files)
        project=work/'project'
        for name in('beryl.mod.json','src/lifecycle.be'):h.write(project/name,mod.read(root/'build/tablet service & spaces-soii5z39/project'/name))
        job=mod.Job(project,'tablet-ui-native-n1b-n3',compiler);job.snapshot()
        def unchanged():
            h.require(h.files(SOURCE.parent)==source_files,'Retained source changed','stale_input')
            for name,item in prior['verification_inputs'].items():h.require(h.identity(Path(name))==item,'N0 preparation input changed','stale_input')
            for name,item in tracked.items():h.require(h.identity(Path(name))==item,'UI runtime input changed: '+name,'stale_input')
            h.require(selected_package()==package_files and h.files(work/'inputs')==own_inputs and h.identity(work/'input-manifest.json')==manifest_identity and h.identity(work/'runtime-expected.json')==expected_identity and h.identity(work/'fixture-source-origins.json')==origin_identity,'Retained UI evidence changed','stale_input')
            h.require(h.streamed_identity(engine)==engine_identity,'Engine changed','stale_input');job.unchanged(job.input_hashes)
            record['engine_derived_outputs']=p.prior_guard.checked_tree(addon,expected_files,True)
        guard=unchanged;guard()
        if args.run:
            record['stage']='host_readiness';record['scope']['host_readiness']='attempted_unconfirmed'
            host_probe=readiness.run_bounded([str(host),'-NoProfile','-NonInteractive','-Command',"Write-Output 'BERYL_FIXED_HOST_PROBE'"],root,work/'host-readiness',15,5,expected_executable={'path':str(host),'sha256':tracked[str(host)]['sha256']},expected_stdout=readiness.MARKER)
            record['host_readiness']=host_probe
            record['scope']['host_readiness']='executed_'+host_probe['status']
            h.require(host_probe['status']=='success','Pinned host readiness did not return the exact marker and confirmed exit',host_probe['status'])
            guard()
            record['stage']='engine_compile';record['scope']['engine_compilation']='attempted_unconfirmed';cp=work/'engine-compile.json'
            try:job.run([host,'-NoProfile','-File',mod.HERE/'engine-compile.ps1','-ToolRoot',toolroot,'-ProjectDir',addon,'-ResultPath',cp,'-ExpectedVersion','1.8.0.13'],'tablet_ui_compile',work,timeout=300)
            except mod.Failure as error:
                h.capture_adapter(record,'compile',cp);raise h.failed_adapter(error,record['raw_results'].get('compile',{}).get('result'))from error
            finally:
                if 'compile'not in record['raw_results']:h.capture_adapter(record,'compile',cp)
            c=record['raw_results']['compile']['result'];h.require(s1.compile_success(c)and c['engine_sha256']==engine_identity['sha256'],'UI compilation not proven')
            record['compile_logs']=h.retain_engine_logs(work,c);h.require(record['compile_logs'],'Compile raw logs missing','unavailable')
            record['scope']['engine_compilation']='executed_success';guard()
            record['stage']='native_ui';rp=work/'engine-runtime.json'
            try:job.run([host,'-NoProfile','-File',adapter,'-ToolRoot',toolroot,'-ProjectDir',addon,'-ProjectId',PROJECT_ID,'-InputManifest',work/'input-manifest.json','-InputManifestHash',manifest_identity['sha256'],'-ResultPath',rp,'-Token',token,'-ExpectedSourceHash',source_hash,'-ExpectedContractHash',CONTRACT_SHA,'-ExpectedEnginePath',engine,'-ExpectedEngineHash',engine_identity['sha256'],'-ExpectedEngineVersion','1.8.0.13'],'tablet_ui_runtime',work,timeout=220)
            except mod.Failure as error:
                capture_runtime(record,rp)
                runtime=record['raw_results'].get('runtime',{}).get('result')
                if type(runtime)is dict:
                    replies=[x.get('normalized_response')for x in runtime.get('rpcs',[])if type(x.get('normalized_response'))is dict and x['normalized_response'].get('rows')]
                    if replies:
                        try:record['partial_trace_verification']=oracle.validate_rows(replies[-1]['rows'],expected,require_complete=False)
                        except oracle.VerificationFailure as issue:record['partial_trace_verification']={'status':'failure','detail':str(issue)}
                raise h.failed_adapter(error,runtime)from error
            finally:
                if 'runtime'not in record['raw_results']:capture_runtime(record,rp)
            r=record['raw_results']['runtime']['result'];guard();record['trace_verification']=validate_runtime(r,expected,manifest,manifest_identity,tracked)
            for key in('ui_opening','native_frames','native_deletion'):record['scope'][key]='executed_success'
            if args.repair_widget_slots:
                record['stage']='native_widget_slot_logs'
                record['widget_slot_repair']['native_gui_errors']=gui_checker.check_raw_logs(r['raw_logs'],scope=work)
                gui=record['widget_slot_repair']['native_gui_errors']
                h.require(gui['status']=='success','Native widget construction log gate did not pass',gui['status'])
            record['stage']='native_ui_complete'
        else:record['stage']='source_prepared'
        record.update(status='success',success_means='Actual admitted UI/frame/native deletion observations'if args.run else'Prepared99-file candidate only')
    except BaseException as error:
        record.update(status=getattr(error,'status','unavailable'if isinstance(error,oracle.AdmissionUnavailable)else'cancelled'if isinstance(error,KeyboardInterrupt)else'failure'),failure={'type':type(error).__name__,'message':str(error)})
    finally:
        try:
            if guard:guard()
        except BaseException as error:
            record['evidence_errors'].append({'stage':'final_integrity','type':type(error).__name__,'message':str(error)})
            if record['status']=='success':record['status']='stale_input'
        if job:
            record['commands']=job.result['raw_logs']
            try:
                for command in record['commands']:
                    for stream in('stdout','stderr'):
                        path=Path(command[stream])
                        if path.is_file():command[stream+'_sha256']=h.streamed_identity(path)['sha256']
                job.result.update(status=record['status'],stage=record['stage']);h.save_result(job.path/'result.json',job.result);record['job']=job.result
            except BaseException as error:
                record['evidence_errors'].append({'stage':'job_retention','type':type(error).__name__,'message':str(error)})
                if record['status']=='success':record['status']='failure'
        try:
            if 'compile_logs'not in record:record['compile_logs']=h.retain_engine_logs(work,record['raw_results'].get('compile',{}).get('result'))
        except BaseException as error:
            record['evidence_errors'].append({'stage':'compile_logs','type':type(error).__name__,'message':str(error)})
            if record['status']=='success':record['status']='failure'
        h.save_result(work/'results.json',record)
        print(json.dumps({'result':str(work/'results.json'),'sha256':mod.digest((work/'results.json').read_bytes()),'status':record['status'],'stage':record['stage'],'failure':record.get('failure'),'evidence_errors':record['evidence_errors']}),flush=True)
    return 0 if record['status']=='success'else 1
if __name__=='__main__':raise SystemExit(main())
