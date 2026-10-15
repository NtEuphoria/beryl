#!/usr/bin/env python3
"""Inert independent admission checks for callback startup-policy receipts.

This imports the pure Python admission function only. No host, compiler, engine,
process inventory, signals, executable fixture or subprocess is used.
"""
from pathlib import Path
import copy
import hashlib
import importlib.util
import json
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
TARGET=ROOT/'scripts/verify-component-callbacks.py'
ADAPTER=ROOT/'scripts/component-callback-engine.ps1'
sys.dont_write_bytecode=True

def identity(path):
    data=Path(path).read_bytes()
    return {'path':str(path),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}

def write(path,value):
    data=(json.dumps(value,indent=2,ensure_ascii=True)+'\n').encode()
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('xb')as stream:
        if stream.write(data)!=len(data):raise OSError('Short inert receipt write')
    if path.read_bytes()!=data:raise OSError('Inert receipt readback differs')

def fixture(policy='force-update'):
    project,engine='C:/fixture/addon','C:/fixture/Workbench.exe'
    runtime={'engine_updates':policy,'elapsed_ms':1000,
        'session':{'process_id':123,'start_ticks':456,'executable':engine,'project':project,'reused':False},
        'engine_update_launch':None,'port_checks':[],'launch_checks':[],'port_query_errors':[],
        'session_checks':[{'elapsed_ms':40}]}
    if policy=='force-update':
        runtime['startup']={'Ok':True,'Reused':False,'ProcessId':123,'Mechanism':'force_update_argument_list'}
        runtime['engine_update_launch']={'schema_version':1,'mechanism':'force_update_argument_list',
            'arguments':['-gproj',project+'/addon.gproj','-noOpenLastResource','-scriptAuthorizeAll','-forceUpdate'],
            'working_directory':'C:/fixture/Game','use_shell_execute':False,'create_no_window':True,
            'window_style':'Hidden','launch_returned':True,'process_id':123,'start_ticks':456,'executable':engine,
            'limits':{'startup_ms':30000,'rpc_ms':8000,'overall_ms':180000,'cleanup_ms':5000,'max_polls':64}}
        runtime['port_checks']=[{'elapsed_ms':20,'listening':True,'owning_process':123}]
        runtime['launch_checks']=[{'site':'launch.identity','elapsed_ms':10,'process_id':123,'start_ticks':456,'executable':engine},
                                  {'site':'port.check','elapsed_ms':30,'process_id':123,'start_ticks':456,'executable':engine}]
    return runtime,[policy,project,engine]

def replace(value,path,replacement):
    target=value
    for key in path[:-1]:target=target[key]
    target[path[-1]]=copy.deepcopy(replacement)

def remove(value,path):
    target=value
    for key in path[:-1]:target=target[key]
    del target[path[-1]]

def main():
    spec=importlib.util.spec_from_file_location('callback_update_policy_admission',TARGET)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    work=Path(tempfile.mkdtemp(prefix='callback-update-policy-inert-',dir=ROOT/'build'))
    cases=[]
    def case(name,mutate=None,accept=False,policy='force-update'):
        cases.append((name,mutate,accept,policy))
    case('positive.force-single-listener',accept=True)
    case('positive.default-focus-only',accept=True,policy='focus-dependent')
    def delayed(v,a):
        v['port_checks'].insert(0,{'elapsed_ms':15,'listening':False,'owning_process':None})
        v['launch_checks'].insert(1,{**v['launch_checks'][1],'elapsed_ms':17})
        v['port_query_errors'].append({'elapsed_ms':16,'category':'ObjectNotFound',
                                     'id':'CmdletizationQuery_NotFound,Get-NetTCPConnection','message':'INERT no listener yet'})
    case('positive.force-delayed-owned-listener',delayed,accept=True)
    for name,policy in (('unknown','invented'),('bool',True),('null',None)):
        case('selection.'+name,lambda v,a,p=policy:a.__setitem__(0,p))
    case('selection.receipt-substituted',lambda v,a:v.update(engine_updates='focus-dependent'))
    case('selection.force-receipt-as-default',lambda v,a:a.__setitem__(0,'focus-dependent'))
    case('selection.default-receipt-as-force',lambda v,a:a.__setitem__(0,'force-update'),policy='focus-dependent')
    for field in ('engine_updates','engine_update_launch','launch_checks','port_checks','port_query_errors'):
        case('force.missing.'+field,lambda v,a,k=field:v.pop(k))
        case('default.missing.'+field,lambda v,a,k=field:v.pop(k),policy='focus-dependent')
    for field,value in (('engine_update_launch',{}),('launch_checks',[{}]),('port_checks',[{}]),('port_query_errors',[{}])):
        case('default.alternate.'+field,lambda v,a,k=field,x=value:v.update({k:copy.deepcopy(x)}),policy='focus-dependent')
    for name,field,replacement in (
        ('schema-bool','schema_version',True),('schema-float','schema_version',1.0),('schema-wrong','schema_version',2),
        ('mechanism','mechanism','other'),('shell-enabled','use_shell_execute',True),('shell-bool01','use_shell_execute',0),
        ('visible','create_no_window',False),('hidden-bool01','create_no_window',1),('window-visible','window_style','Normal'),
        ('launch-not-returned','launch_returned',False),('launch-returned-bool01','launch_returned',1),
        ('relative-cwd','working_directory','fixture/Game'),('null-cwd','working_directory',None),
        ('foreign-executable','executable','C:/other/Workbench.exe'),('pid-bool','process_id',True),
        ('pid-float','process_id',123.0),('pid-foreign','process_id',124),('ticks-bool','start_ticks',True),
        ('ticks-float','start_ticks',456.0),('ticks-foreign','start_ticks',457)):
        case('launch.'+name,lambda v,a,k=field,x=replacement:v['engine_update_launch'].update({k:copy.deepcopy(x)}))
    case('launch.missing-flag',lambda v,a:v['engine_update_launch']['arguments'].pop())
    case('launch.extra-flag',lambda v,a:v['engine_update_launch']['arguments'].append('-load=foreign.ent'))
    case('launch.policy-flag-substituted',lambda v,a:v['engine_update_launch']['arguments'].__setitem__(4,'-noUpdate'))
    case('launch.argument-order',lambda v,a:v['engine_update_launch']['arguments'].reverse())
    case('launch.foreign-project',lambda v,a:v['engine_update_launch']['arguments'].__setitem__(1,'C:/other/addon.gproj'))
    case('launch.argument-null',lambda v,a:v['engine_update_launch']['arguments'].__setitem__(1,None))
    case('launch.unknown-field',lambda v,a:v['engine_update_launch'].update(fallback=True))
    case('launch.missing-arguments',lambda v,a:v['engine_update_launch'].pop('arguments'))
    case('startup.missing',lambda v,a:v.pop('startup'))
    case('startup.scalar',lambda v,a:v.update(startup='wrong'))
    for name,field,replacement in (
        ('not-ok','Ok',False),('ok-int','Ok',1),('reused','Reused',True),('reused-int','Reused',0),
        ('foreign-pid','ProcessId',124),('pid-bool','ProcessId',True),('pid-float','ProcessId',123.0),
        ('mechanism','Mechanism','installed_daemon')):
        case('startup.'+name,lambda v,a,k=field,x=replacement:v['startup'].update({k:x}))
    case('startup.unknown-field',lambda v,a:v['startup'].update(fallback=True))
    case('startup.missing-field',lambda v,a:v['startup'].pop('Mechanism'))
    for key in ('startup_ms','rpc_ms','overall_ms','cleanup_ms','max_polls'):
        case('limits.changed.'+key,lambda v,a,k=key:v['engine_update_launch']['limits'].__setitem__(k,1))
        case('limits.bool.'+key,lambda v,a,k=key:v['engine_update_launch']['limits'].__setitem__(k,True))
    case('limits.unknown',lambda v,a:v['engine_update_launch']['limits'].update(retry_ms=1000))
    case('limits.missing',lambda v,a:v['engine_update_launch']['limits'].pop('max_polls'))
    for name,field,value in (('pid-bool','process_id',True),('ticks-bool','start_ticks',True),
                            ('foreign-path','executable','C:/other/Workbench.exe'),('foreign-project','project','C:/other/addon'),('reused','reused',True)):
        case('session.'+name,lambda v,a,k=field,x=value:v['session'].update({k:x}))
    for name,path,value in (
        ('scalar',('launch_checks',0),'wrong'),('unknown-field',('launch_checks',0,'extra'),True),
        ('wrong-site',('launch_checks',0,'site'),'startup.complete'),('negative-time',('launch_checks',0,'elapsed_ms'),-1),
        ('time-bool',('launch_checks',0,'elapsed_ms'),True),('expired-time',('launch_checks',1,'elapsed_ms'),30000),
        ('reversed-time',('launch_checks',1,'elapsed_ms'),9),('wrong-pid',('launch_checks',0,'process_id'),124),
        ('wrong-ticks',('launch_checks',1,'start_ticks'),457),('foreign-exe',('launch_checks',1,'executable'),'C:/other/Workbench.exe')):
        case('launch-check.'+name,lambda v,a,p=path,x=value:replace(v,p,x))
    case('launch-check.missing',lambda v,a:v['launch_checks'].pop())
    case('launch-check.extra',lambda v,a:v['launch_checks'].append(copy.deepcopy(v['launch_checks'][-1])))
    case('listener.empty',lambda v,a:v.update(port_checks=[]))
    case('listener.scalar',lambda v,a:v['port_checks'].__setitem__(0,'wrong'))
    for name,field,value in (('foreign-owner','owning_process',124),('owner-bool','owning_process',True),
                            ('not-listening','listening',False),('listening-int','listening',1),
                            ('before-launch','elapsed_ms',9),('after-check','elapsed_ms',31),('time-bool','elapsed_ms',True)):
        case('listener.'+name,lambda v,a,k=field,x=value:v['port_checks'][0].update({k:x}))
    case('listener.unknown-field',lambda v,a:v['port_checks'][0].update(extra=True))
    def early_owner(v,a):
        delayed(v,a);v['port_checks'][0].update(listening=True,owning_process=123)
    case('listener.repeated-ready',early_owner)
    for name,value in (('scalar','wrong'),('unknown-category',{'elapsed_ms':20,'category':'PermissionDenied','id':'x','message':'x'}),
        ('out-of-interval',{'elapsed_ms':9,'category':'ObjectNotFound','id':'x','message':'x'}),
        ('malformed-id',{'elapsed_ms':20,'category':'ObjectNotFound','id':False,'message':'x'}),
        ('unknown-field',{'elapsed_ms':20,'category':'ObjectNotFound','id':'x','message':'x','extra':True})):
        case('query-error.'+name,lambda v,a,x=value:v['port_query_errors'].append(copy.deepcopy(x)))
    case('elapsed.bool',lambda v,a:v.update(elapsed_ms=True))
    case('elapsed.expired',lambda v,a:v.update(elapsed_ms=180000))
    case('elapsed.before-launch-check',lambda v,a:v.update(elapsed_ms=29))
    case('callback-boundary.missing',lambda v,a:v.pop('session_checks'))
    case('callback-boundary.empty',lambda v,a:v.update(session_checks=[]))
    case('callback-boundary.scalar',lambda v,a:v['session_checks'].__setitem__(0,'wrong'))
    case('callback-boundary.time-bool',lambda v,a:v['session_checks'][0].update(elapsed_ms=True))
    case('callback-boundary.before-launch',lambda v,a:v['session_checks'][0].update(elapsed_ms=29))
    case('callback-boundary.missing-time',lambda v,a:v['session_checks'][0].pop('elapsed_ms'))
    expected=[x[0]for x in cases]
    if len(expected)!=len(set(expected)):raise AssertionError('Repeated independent policy caseID')
    frozen={str(p):identity(p)for p in (Path(__file__).resolve(),TARGET,ADAPTER)}
    retained=[]
    for index,(path,row)in enumerate(frozen.items()):
        output=work/(str(index).zfill(3)+'-'+Path(path).name+'.input')
        data=Path(path).read_bytes()
        with output.open('xb')as stream:
            if stream.write(data)!=len(data):raise OSError('Short inert source retention')
        if identity(output)['sha256']!=row['sha256']:raise AssertionError('Source changed during retention')
        retained.append({**row,'retained':str(output)})
    record={'schema_version':1,'operation':'verify.callback.update_policy.inert','status':'failure','expected_case_ids':expected,
            'cases':[],'verification_inputs':frozen,'retained_inputs':retained,
            'scope':{'host':'not_run','engine':'not_run','compiler':'not_run','process_inventory':'not_run','signals':'not_run',
                     'callback_delivery':'not_run','startup_policy':'synthetic_admission_only'}}
    try:
        for index,(name,mutate,accept,policy)in enumerate(cases):
            value,args=fixture(policy);outcome,rejection,crash=None,None,None
            if mutate:mutate(value,args)
            try:outcome=module.validate_engine_updates(value,*args)
            except module.mod.Failure as exc:rejection={'type':type(exc).__name__,'status':exc.status,'message':str(exc)}
            except Exception as exc:crash={'type':type(exc).__name__,'message':str(exc)}
            passed=(outcome is not None and outcome.get('status')=='verified' and rejection is None and crash is None)if accept else(rejection is not None and crash is None)
            record['cases'].append({'id':name,'status':'passed'if passed else'failed','expected_accept':accept,
                'outcome':outcome,'rejection':rejection,'validator_exception':crash})
            write(work/('case-'+str(index).zfill(3)+'.json'),{'id':name,'selected_policy':args[0],'project':args[1],'engine_path':args[2],
                                                        'synthetic_runtime':value,'result':record['cases'][-1]})
        record['case_set_complete']=[x['id']for x in record['cases']]==expected
        record['expected_count']=len(expected);record['completed_count']=len(record['cases'])
        record['passed_count']=sum(x['status']=='passed'for x in record['cases']);record['failed_count']=len(expected)-record['passed_count']
        record['source_unchanged']={str(p):identity(p)for p in(Path(__file__).resolve(),TARGET,ADAPTER)}==frozen
        record['status']='success'if record['case_set_complete']and not record['failed_count']and record['source_unchanged']else'failure'
    finally:
        write(work/'result.json',record)
        print(json.dumps({'receipt':identity(work/'result.json'),'status':record['status'],'expected':record.get('expected_count'),
                         'passed':record.get('passed_count'),'failures':[x for x in record['cases']if x['status']!='passed']}),flush=True)
    return 0 if record['status']=='success'else 1

if __name__=='__main__':raise SystemExit(main())
