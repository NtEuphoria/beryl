#!/usr/bin/env python3
"""Experimental exact N1a native actions; isolated addon, no live promotion."""
from pathlib import Path
import argparse,hashlib,importlib.util,json,re,sys,tempfile
from decimal import Decimal
sys.dont_write_bytecode=True
root=Path(__file__).resolve().parents[1]
def module(name,path,sha=None):
    raw=path.read_bytes()
    if sha is not None: assert hashlib.sha256(raw).hexdigest()==sha,str(path)
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec)
    exec(compile(raw,str(path),'exec'),m.__dict__);return m
p=module('n1_source_foundation',root/'scripts/prepare-tablet-native-callbacks.py',
         '62bb44d64e4fb830777196855eb8febdf0df3afa2cb3c86e7c900c62090e9471')
h,mod,s1=p.h,p.mod,p.s1
package=root/'packages/sparkos/tablet-real-service-probe'
WIRE_SOURCE_SHA='74aed85740e8d72b5c187eae9b537fffb921b90ec24ac0002500379897e8cd65'
WIRE_CONTRACT_SHA='80abd295e0652346df82083ade1409731f3f0b3508a8cd75f09b6afe39920766'
wire=module('n1_actual_wire',package/'wire.py','39c0e05a13de39b4528cb99f969daafb71b0e2450c329fd47ef24b614fbb38f1')
host=Path('C:/Users/moham/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/powershell/pwsh.exe')
engine=Path('C:/Program Files (x86)/Steam/steamapps/common/Arma Reforger Tools/Workbench/ArmaReforgerWorkbenchSteamDiag.exe')
toolroot=Path('C:/Users/moham/Desktop/reforger-workbench-plugin')
compiler=root/'build/oct08-wrapper-cli-l8ci669v/beryl.exe'
adapter=root/'scripts/tablet-real-services-engine.ps1'
base_project=Path('C:/Program Files (x86)/Steam/steamapps/common/Arma Reforger/addons/data/ArmaReforger.gproj')
def normalized_native(value):
    texts=('token','action','status','failure','profile','source_contract_sha256','wire_contract_sha256','source_sha256','world_path','current_project',
        'addon_world_path','world_absolute_path','resource_name','resource_path','resource_absolute_path')
    bools=('addon_world_resolved','world_path_resolved','resource_name_resolved','module_present','api_present','module_open_requested',
        'module_open_accepted','load_accepted','world_matches','edit_mode','game_mode','in_play_mode','world_present','game_world_present','actions_ready','outside_domain','stop_requested')
    ints=('schema_version','load_requested','load_submitted','load_entered','load_resumed','load_returned','phase','executed','failures','owner_count','row_count','checksum','init_count','init_checksum','raw_bytes')
    arrays=('caseIds','init_rows','rows');names=set(texts+bools+ints+arrays)
    h.require(type(value)is dict and not(set(value)-names) and names-set(value)<=set(arrays),'Native N1 envelope fields differ')
    n={};codec={'schema_version':1,'numeric_boolean_fields':[],'omitted_empty_arrays':[]}
    for key in texts:
        h.require(type(value[key])is str and len(value[key])<=2048 and '\0'not in value[key],'Native wire text differs');n[key]=value[key]
    for key in bools:
        v=value[key];h.require(type(v)is bool or type(v)is int and v in (0,1),'Native wire Boolean differs');n[key]=bool(v)
        if type(v)is int:codec['numeric_boolean_fields'].append(key)
    for key in ints:
        v=value[key];h.require(type(v)is int and -2147483648<=v<=2147483647,'Native wire integer differs');n[key]=v
    for key in arrays:
        if key in value:n[key]=value[key]
        else:
            h.require((key=='init_rows' and n['init_count']==0)or(key in ('caseIds','rows')and n['executed']==0),'Omitted nonempty wire collection')
            n[key]=[];codec['omitted_empty_arrays'].append(key)
        h.require(type(n[key])is list,'Wire collection not a list')
    return n,codec
def validate_init_rows(rows,checksum):
    h.require(type(rows)is list and len(rows)==4 and type(checksum)is int and checksum==wire.checksum(rows),
              'Native initialization rows/checksum differ')
    for i,row in enumerate(rows):
        f=row.split('|');token=str(i//2+1);stage=('init.before','init.after')[i%2]
        h.require(len(f)==16 and f[:3]==[str(i+1),token,stage],'Native initialization order differs')
        wire._zero(f[12])
        h.require(all(x in ('0','1')for x in f[3:11]) and f[3:8]==['1']*5 and f[8]=='1' and
                  f[11]=='0' and Decimal(f[12]).is_finite() and Decimal(f[12])==0 and f[14:]==['1','1'],
                  'Native owner/world/state/default witness differs')
        h.require(re.fullmatch(r'0|[1-9][0-9]{0,8}',f[13]) is not None and int(f[13])<=2147483647,
                  'Native event mask encoding differs')
        if i%2:h.require(int(f[13])&8!=0,'Native FRAME event mask missing')
        h.require(f[9:11]==(['0','0']if i<2 else['1','1']),'Native state independence witness order differs')
    return {'schema_version':1,'status':'success','native_initialization_rows':4,'owner_count':2,'numeric_encoding':'rounded_zero_only'}
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
    calls=[entry for entry in r['rpcs']if entry['stage']in('spawn','run','stop')]
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
    h.require(startup['mechanism']=='owned_tablet_real_services_n1a'and type(startup['argv'])is list and
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
    h.require(type(r)is dict and type(r.get('schema_version'))is int and r['schema_version']==1 and
              type(r.get('elapsed_ms'))is int and 0<=r['elapsed_ms']<180000,'Native receipt schema/time differs')
    for key in('evidence_errors','cleanup_errors'):
        h.require(type(r.get(key))is list and r[key]==[],'Native receipt error collection differs')
    h.require(r['status']=='success'and r['stage']=='native_services_transport_complete'and r['failure']is None and
              not r['evidence_errors']and not r['cleanup_errors']and r['cleanup']in('owned_process_stopped','owned_process_already_exited'),
              'Native runtime lacks final success and confirmed owned cleanup')
    h.require(r['profile']==wire.PROFILE and r['token']==expected['token']and r['source_sha256']==expected['source_sha256']and
              r['source_contract_sha256']==WIRE_SOURCE_SHA and r['project_id']=='BerylTabletRealServicesN1aPrototype'and
              r['engine_sha256']==record['engine_input']['sha256']and r['engine_bytes']==record['engine_input']['bytes']and
              Path(r['engine_path']).resolve()==engine.resolve()and r['engine_version']=='1.8.0.13'and
              r['adapter_sha256']==tracked[str(adapter)]['sha256'],'Native runtime source/engine identity differs','stale_input')
    h.require(r['input_manifest']=={'path':str(manifest_identity['path']),'sha256':manifest_identity['sha256']}and
              typed_equal(r['staged_inputs'],manifest),'Pinned native runtime manifest differs','stale_input')
    argv=['-gproj',str(addon/'addon.gproj'),'-noOpenLastResource','-scriptAuthorizeAll','-forceUpdate']
    h.require(r['arguments']==argv and r['startup']['argv']==argv and r['startup']['launch_returned']is True and
              r['startup']['use_shell_execute']is False and r['startup']['create_no_window']is True and r['startup']['window_style']=='Hidden',
              'Owned native launch profile differs')
    session=r['session'];h.require(type(session['process_id'])is int and session['process_id']>0 and type(session['start_ticks'])is int and
                                  session['reused']is False and Path(session['project']).resolve()==addon.resolve(),'Owned native session differs')
    h.require(r['elapsed_ms']<180000 and r['raw_log_observation']=='snapshot_after_confirmed_owned_exit','Late or live-only native terminal evidence')
    for key in('save','physical_ui_input','multiplayer','visual_review','policy_changes'):h.require(r[key]=='not_run','Unexpected native operation')
    h.require([x['action']for x in r['stages']]==['load','play','spawn','run','stop']and all(x['status']=='completed'and
              type(x['polls'])is int and 0<=x['polls']<=64 and x['elapsed_ms']<30000 for x in r['stages']),'Native stage ledger incomplete')
    ledger=r['rpcs'];h.require(5<=len(ledger)<=326,'Native RPC count exceeds stage bounds')
    previous=None;stage_calls={name:[]for name in('load','play','spawn','run','stop')}
    for index,entry in enumerate(ledger):
        reply=entry['result'];h.require(type(reply)is dict and set(reply)=={'Ok','Function','ErrorCode','Response','Raw'}and
            reply['Ok']is True and reply['ErrorCode']=='Ok'and entry['failure']is None and entry['failure_kind']is None and
            type(entry['timeout_ms'])is int and 0<entry['timeout_ms']<=8000 and 0<=entry['duration_ms']<entry['timeout_ms'],
            'RPC failure/late/transport evidence differs')
        raw=mod.parse(reply['Raw'].encode());h.require(typed_equal(raw,reply['Response']),'Raw native RPC response differs')
        h.require(reply['Function']==entry['function'],'RPC function ledger differs')
        if index==0:
            h.require(entry['function']=='GetLoadedProjects'and entry['params']=={}and set(raw)=={'Loaded Projects'},'Initial native inventory missing')
            projects=raw['Loaded Projects'];h.require(type(projects)is list and len(projects)==len(set(projects))and
                'BerylTabletRealServicesN1aPrototype'in projects and set(projects)<={'BerylTabletRealServicesN1aPrototype','ArmaReforger','core'},'Loaded native addons differ')
            continue
        h.require(entry['function']=='BerylTabletRealServicesNative'and entry['stage']in stage_calls and
            entry['params']=={'token':expected['token'],'action':entry['params']['action']}and entry['params']['action']in(entry['stage'],'status'),
            'Unregistered native request')
        n,codec=normalized_native(raw)
        h.require(typed_equal(n,entry['normalized_response'])and typed_equal(codec,entry['codec']),'Independent native wire normalization differs')
        h.require(n['token']==expected['token']and n['source_sha256']==expected['source_sha256']and n['source_contract_sha256']==WIRE_SOURCE_SHA and
                  n['profile']==wire.PROFILE and n['wire_contract_sha256']==WIRE_CONTRACT_SHA and
                  n['current_project']=='./addons/data/ArmaReforger.gproj' and
                  n['action']==entry['params']['action']and n['failure']==''and n['failures']==0 and n['outside_domain']is False,
                  'Compiled native progress stamp/outcome differs')
        counters=[n[k]for k in('load_requested','load_submitted','load_entered','load_resumed','load_returned')]
        h.require(all(v in(0,1)for v in counters)and counters[1]<=counters[0]and counters[2]<=counters[0]and
                  counters[3]<=min(counters[1],counters[2])and counters[4]<=counters[3]and(not n['load_accepted']or counters[4]==1),'Native load progress differs')
        if previous:h.require(all(a>=b for a,b in zip(counters,previous)),'Native load progress reset','stale_input')
        previous=counters;stage_calls[entry['stage']].append(n)
    for stage in r['stages']:
        calls=stage_calls[stage['action']]
        h.require(len(calls)==stage['polls']+1 and typed_equal(calls[-1],stage['response']),'Native stage response linkage differs')
        h.require(calls[0]['action']==stage['action']and all(n['action']=='status'for n in calls[1:]),'Native stage retried a mutation')
        n=calls[-1]
        wanted={'load':('ready',0),'play':('ready',0),'spawn':('pending',2),'run':('pending',2),'stop':('complete',4)}[stage['action']]
        h.require((n['status'],n['phase'])==wanted,'Native stage status/phase boundary differs')
        h.require(n['module_present']and n['api_present']and n['world_matches']and n['world_present']and
            all(n[k]for k in('addon_world_resolved','world_path_resolved','resource_name_resolved'))and
            all(Path(n[k]).resolve()==(addon/'worlds/BerylTabletRealServicesN1a.ent').resolve()for k in('addon_world_path','world_absolute_path','resource_absolute_path'))and
            n['resource_name']=='{BE71571A20261010}worlds/BerylTabletRealServicesN1a.ent'and n['resource_path']=='worlds/BerylTabletRealServicesN1a.ent',
            'Native stage world provenance differs')
        h.require(previous is not None and all(n[k]==1 for k in('load_requested','load_submitted','load_entered','load_resumed','load_returned'))and
                  n['load_accepted'],'Native stage lacks complete one-shot load')
        if stage['action']in('load','stop'):h.require(n['edit_mode']and not n['game_mode']and not n['in_play_mode'],'Native edit boundary differs')
        else:h.require(not n['edit_mode']and n['game_mode']and n['in_play_mode']and n['game_world_present'],'Native play boundary differs')
    completion=r['completion'];h.require(typed_equal(completion,stage_calls['stop'][-1])and completion['phase']==4 and
               completion['stop_requested']is True,'Native final completion was not observed after stop')
    subset={key:completion[key]for key in wire.COMPLETE_KEYS};subset['failure']=None
    h.require(completion['failure']=='' and completion['outside_domain'] is False,
              'Failure or unavailable outcome is not semantic completion')
    verified=wire.decode(subset,expected)
    validate_init_rows(completion['init_rows'],completion['init_checksum'])
    h.require(completion['init_count']==4 and completion['raw_bytes']==sum(len(x.encode('ascii'))+1 for x in completion['rows']),
              'Native scalar raw count differs')
    spawn=stage_calls['spawn'][-1];run=stage_calls['run'][-1]
    h.require(spawn['executed']==0 and spawn['owner_count']==2 and spawn['init_count']==4 and spawn['actions_ready'] is False,
              'Native initialization boundary differs')
    validate_init_rows(spawn['init_rows'],spawn['init_checksum'])
    h.require(run['executed']==7 and run['actions_ready'] is True and run['row_count']==44,
              'Native synchronous run boundary differs')
    for key in ('rows','caseIds','checksum','row_count','raw_bytes','init_rows','init_checksum','init_count'):
        h.require(typed_equal(run[key],completion[key]),'Frozen service completion changed across stop: '+key,'stale_input')
    h.require(typed_equal(spawn['init_rows'],run['init_rows']) and spawn['init_checksum']==run['init_checksum'],
              'Native initialization witnesses changed across public actions','stale_input')
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

def main():
    global work,record,addon
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--source',type=Path,required=True)
    cli.add_argument('--source-sha256',required=True)
    cli.add_argument('--package-sha256',required=True)
    cli.add_argument('--run',action='store_true')
    args=cli.parse_args()
    for value in(args.source_sha256,args.package_sha256):
        if re.fullmatch(r'[0-9a-f]{64}',value)is None:cli.error('Full input fingerprints required')
    source=args.source.resolve()
    work=Path(tempfile.mkdtemp(prefix='tablet-real-services-native-',dir=root/'build'))
    record={'schema_version':1,'operation':'verify.tablet_real_services.n1a.native','status':'failure','stage':'source_admission',
            'scope':{'engine_compilation':'not_run','native_initialization':'not_run','public_actions':'not_run','screen_services':'not_run',
                     'ui':'not_admitted','player_interaction':'not_admitted','deletion':'not_admitted','multiplayer':'not_run',
                     'visual_review':'not_run','installation':'unchanged'},'commands':[],'raw_results':{},'evidence_errors':[]}
    job=guard=None
    try:
        h.require(source.is_relative_to((root/'build').resolve()),'Source preparation must be a retained workspace receipt')
        raw=mod.read(source);h.require(mod.digest(raw)==args.source_sha256,'Source preparation changed','stale_input');prior=mod.parse(raw)
        h.require(prior['status']=='success'and prior['stage']=='source_prepared'and len(prior['staged_file_set'])==98 and
                  prior['source_contract_sha256']==WIRE_SOURCE_SHA,'Exact successful N1a source preparation required')
        source_files=h.files(source.parent);source_dirs=set(h.directories(source.parent))
        package_files=h.files(package)
        h.require(mod.digest(mod.canonical(package_files))==args.package_sha256==prior['package_sha256'],'N1 package selection changed','stale_input')
        pins={host:'362a356ce7f0940ec74f73a8fc2c990a2cc24a38a11c90bbd8eca947110ad139',
              compiler:'76aeaacfea6866e66e3020f983eaa22089d545ad0f3b60fedfd28c3d58972bd7',
              mod.HERE/'engine-compile.ps1':'ea923399c2060123812a6ea205760372de0e2fff29071117e0cf58ed64877121'}
        for path,sha in pins.items():h.require(h.identity(path)['sha256']==sha,'Pinned execution tool changed','stale_input')
        engine_identity=h.streamed_identity(engine)
        h.require(engine_identity['sha256']=='7dd36ca1f662b0c13669a4f2f7f10e3c461c2906b021e742272d64b3ab7e9798','Engine changed','stale_input')
        paths=[Path(__file__).resolve(),root/'scripts/prepare-tablet-native-callbacks.py',root/'scripts/prepare-tablet-real-services.py',adapter,host,compiler,base_project]
        paths+=sorted(package.glob('*'))+sorted(mod.HERE.glob('*.py'))+sorted(mod.HERE.glob('*.ps1'))+sorted(mod.HERE.glob('*.json'))+sorted((toolroot/'scripts').glob('*.ps1'))
        h.require(all(path.is_file()for path in paths)and len(paths)==len(set(paths))and len(paths)<=256,'Bounded distinct trusted inputs required')
        tracked={str(path):h.identity(path)for path in paths}
        source_hash=mod.digest(mod.canonical(prior['staged_file_set']))
        token=mod.digest(mod.canonical({'source':source_hash,'source_contract':WIRE_SOURCE_SHA,'wire_contract':WIRE_CONTRACT_SHA,'inputs':tracked,'engine':engine_identity}))
        addon=work/'candidate-addon';expected_files=dict(prior['staged_file_set'])
        for name,sha in expected_files.items():
            data=mod.read(Path(prior['candidate_path'])/name);h.require(mod.digest(data)==sha,'Prepared N1 payload changed','stale_input');h.write(addon/name,data)
        encoder=mod.read(package/'encoder.c.in');driver=mod.read(package/'runtime-driver.c.in')
        h.require(mod.digest(encoder)==package_files['encoder.c.in']and mod.digest(driver)==package_files['runtime-driver.c.in'],
                  'Captured native encoder/driver differs','stale_input')
        rpc=(encoder+b'\n'+driver).decode('utf8')
        replacements={'TOKEN':token,'SOURCE_SHA256':source_hash,'SOURCE_CONTRACT_SHA256':WIRE_SOURCE_SHA,'WIRE_CONTRACT_SHA256':WIRE_CONTRACT_SHA,
                      'WORLD_ABSOLUTE':(addon/'worlds/BerylTabletRealServicesN1a.ent').as_posix(),'CURRENT_GAME_PROJECT':'./addons/data/ArmaReforger.gproj'}
        for name,value in replacements.items():rpc=rpc.replace('@'+name+'@',value)
        h.require(re.search(r'@[A-Z_]+@',rpc)is None,'Unresolved trusted native transport placeholder')
        h.require(not any(text in rpc for text in('DeleteRplEntity','OnPostInit(','EOnFrame(','OnDelete(')),
                  'Trusted N1 RPC cannot manually invoke callbacks or deletion')
        rpc_path='scripts/WorkbenchGameCommon/BerylTabletRealServicesNative.c'
        h.require(rpc_path not in expected_files,'Native RPC collision')
        payload=rpc.encode('utf8');h.write(addon/rpc_path,payload);expected_files[rpc_path]=mod.digest(payload)
        h.require(len(expected_files)==99,'Exact 99-file native N1 candidate required')
        h.save_result(work/'rpc-source-map.json',{'schema_version':1,'kind':'trusted_fixture_line_origins','generated_path':rpc_path,
                      'generated_sha256':expected_files[rpc_path],'source_parts':[h.identity(package/'encoder.c.in'),h.identity(package/'runtime-driver.c.in')],
                      'driver_generated_start_line':len(encoder.splitlines())+2,'columns':'unavailable_after_literal_expansion'})
        rpc_map_identity=h.identity(work/'rpc-source-map.json')
        p.prior_guard.checked_tree(addon,expected_files)
        h.write(work/'source-preparation-result.json',raw)
        for i,path in enumerate(paths):
            data=mod.read(path);h.require(mod.digest(data)==tracked[str(path)]['sha256'],'Captured runtime input differs','stale_input')
            h.write(work/'inputs'/(str(i).zfill(4)+'-'+path.name),data)
        own_inputs=h.files(work/'inputs')
        manifest={'schema_version':1,'profile':wire.PROFILE,'files':expected_files};h.save_result(work/'input-manifest.json',manifest)
        manifest_identity=h.identity(work/'input-manifest.json')
        expected={'schema_version':1,'profile':wire.PROFILE,'token':token,'source_contract_sha256':WIRE_SOURCE_SHA,'source_sha256':source_hash,
                  'wire_contract_sha256':WIRE_CONTRACT_SHA};h.save_result(work/'runtime-expected.json',expected)
        expected_identity=h.identity(work/'runtime-expected.json')
        record.update(source_preparation_result=h.identity(source),engine_input=engine_identity,verification_inputs=tracked,
                      candidate_path=str(addon),staged_file_set=expected_files,input_manifest=manifest_identity,runtime_expected=expected_identity,
                      rpc_source_map=rpc_map_identity,token=token,package_sha256=args.package_sha256,package_files=package_files,
                      current_project_contract={'role':'base_game_project','expected_raw':'./addons/data/ArmaReforger.gproj','file':tracked[str(base_project)],
                                                'addon_identity':'strict loaded-project set, compiled token and exact resource/world path'})
        project=work/'project'
        for name in('beryl.mod.json','src/lifecycle.be'):h.write(project/name,mod.read(root/'build/tablet service & spaces-soii5z39/project'/name))
        job=mod.Job(project,'tablet-real-services-n1a',compiler);job.snapshot()
        def unchanged():
            h.require(h.files(source.parent)==source_files and set(h.directories(source.parent))==source_dirs,'Retained preparation tree changed','stale_input')
            for name,item in prior['verification_inputs'].items():h.require(h.identity(Path(name))==item,'Preparation input changed','stale_input')
            for name,item in tracked.items():h.require(h.identity(Path(name))==item,'Native runtime input changed: '+name,'stale_input')
            h.require(h.files(package)==package_files and h.files(work/'inputs')==own_inputs and h.identity(work/'input-manifest.json')==manifest_identity and
                      h.identity(work/'runtime-expected.json')==expected_identity and h.identity(work/'rpc-source-map.json')==rpc_map_identity,
                      'Captured native runtime input changed','stale_input')
            h.require(h.streamed_identity(engine)==engine_identity,'Engine changed','stale_input');job.unchanged(job.input_hashes)
            record['engine_derived_outputs']=p.prior_guard.checked_tree(addon,expected_files,True)
        guard=unchanged;guard()
        if args.run:
            record['stage']='engine_compile';record['scope']['engine_compilation']='attempted_unconfirmed';cp=work/'engine-compile.json'
            try:job.run([host,'-NoProfile','-File',mod.HERE/'engine-compile.ps1','-ToolRoot',toolroot,'-ProjectDir',addon,'-ResultPath',cp,
                         '-ExpectedVersion','1.8.0.13'],'tablet_real_services_compile',work,timeout=300)
            except mod.Failure as error:
                h.capture_adapter(record,'compile',cp);raise h.failed_adapter(error,record['raw_results'].get('compile',{}).get('result'))from error
            finally:
                if 'compile'not in record['raw_results']:h.capture_adapter(record,'compile',cp)
            c=record['raw_results']['compile']['result']
            h.require(s1.compile_success(c)and c['engine_sha256']==engine_identity['sha256'],'Native services compilation not proven')
            record['compile_logs']=h.retain_engine_logs(work,c);h.require(record['compile_logs'],'Compile raw logs missing','unavailable')
            record['scope']['engine_compilation']='executed_success';guard()
            record['stage']='native_services';record['scope']['public_actions']='attempted_unconfirmed';rp=work/'engine-runtime.json'
            try:job.run([host,'-NoProfile','-File',adapter,'-ToolRoot',toolroot,'-ProjectDir',addon,'-ProjectId','BerylTabletRealServicesN1aPrototype',
                         '-InputManifest',work/'input-manifest.json','-InputManifestHash',manifest_identity['sha256'],'-ResultPath',rp,'-Token',token,
                         '-ExpectedSourceHash',source_hash,'-ExpectedContractHash',WIRE_SOURCE_SHA,'-ExpectedEnginePath',engine,
                         '-ExpectedEngineHash',engine_identity['sha256'],'-ExpectedEngineVersion','1.8.0.13'],'tablet_real_services_runtime',work,timeout=220)
            except mod.Failure as error:
                h.capture_adapter(record,'runtime',rp);raise h.failed_adapter(error,record['raw_results'].get('runtime',{}).get('result'))from error
            finally:
                if 'runtime'not in record['raw_results']:h.capture_adapter(record,'runtime',rp)
            r=record['raw_results']['runtime']['result'];guard()
            record['trace_verification']=validate_runtime(r,expected,manifest,manifest_identity,tracked)
            record['native_origin']={'status':'verified_owned_fixture','scope':'Factory-created owners, native initialization, actual public actions, exact compiled artifact and owned RPC session'}
            for key in('native_initialization','public_actions','screen_services'):record['scope'][key]='executed_success'
            record['stage']='native_services_complete'
        else:record['stage']='source_prepared'
        record.update(status='success',success_means='Seven exact public-service cases and native init only'if args.run else'Prepared 99-file candidate only')
    except BaseException as error:
        record.update(status=getattr(error,'status','cancelled'if isinstance(error,KeyboardInterrupt)else'failure'),
                      failure={'type':type(error).__name__,'message':str(error)})
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
        print(json.dumps({'result':str(work/'results.json'),'sha256':mod.digest((work/'results.json').read_bytes()),'status':record['status'],
                          'stage':record['stage'],'failure':record.get('failure'),'evidence_errors':record['evidence_errors']}),flush=True)
    return 0 if record['status']=='success' else 1

if __name__=='__main__':raise SystemExit(main())
