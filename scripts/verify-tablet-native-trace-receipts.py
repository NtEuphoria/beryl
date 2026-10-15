#!/usr/bin/env python3
"""Pure N0 trace completeness/order/type mutants; no processes or engines."""
from pathlib import Path
import copy
import hashlib
import importlib.util
import json
import sys
import tempfile
import stat
from types import SimpleNamespace
from unittest.mock import patch

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "scripts/verify-tablet-native-trace.py"
PACKAGE = ROOT / "packages/sparkos/tablet-native-callback-probe"
WIRE = ("sequence", "token", "stage", "ordinal", "ownerMatches", "ownerWorldPresent", "gameWorldPresent",
        "gameWorldMatches", "statePresent", "sameState", "independenceObserved", "independentState", "mode",
        "accumulator", "timeSlice", "mask", "uiAbsent", "screenAbsent")


def identity(path):
    raw=path.read_bytes()
    return {"path":str(path),"bytes":len(raw),"sha256":hashlib.sha256(raw).hexdigest()}


def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    raw=(json.dumps(value,indent=2,allow_nan=False)+"\n").encode()
    if path.write_bytes(raw)!=len(raw) or path.read_bytes()!=raw:raise RuntimeError("Incomplete evidence write")


def load():
    spec=importlib.util.spec_from_file_location("tablet_native_trace_inert",SOURCE)
    module=importlib.util.module_from_spec(spec)
    exec(compile(SOURCE.read_bytes(),str(SOURCE),"exec"),module.__dict__)
    return module


def fixture(m,counts=(3,3),early=0):
    rows=[]
    def emit(token,stage,ordinal,independent,time="0.016",mask=8):
        value={"sequence":str(len(rows)),"token":str(token),"stage":stage,"ordinal":str(ordinal),
               "ownerMatches":"1","ownerWorldPresent":"1","gameWorldPresent":"1","gameWorldMatches":"1",
               "statePresent":"1","sameState":"1","independenceObserved":str(int(independent)),
               "independentState":str(int(independent)),"mode":"0","accumulator":"0","timeSlice":time,
               "mask":str(mask),"uiAbsent":"1","screenAbsent":"1"}
        rows.append("|".join(value[key] for key in WIRE))
    emit(1,"init.before",1,False,"0",0);emit(1,"init.after",1,False,"0",8)
    for ordinal in range(1,early+1):
        emit(1,"frame.before",ordinal,False);emit(1,"frame.after",ordinal,False)
    emit(2,"init.before",1,True,"0",0);emit(2,"init.after",1,True,"0",8)
    for ordinal in range(1,max(counts)+1):
        for token in (1,2):
            if ordinal<=counts[token-1] and not(token==1 and ordinal<=early):
                emit(token,"frame.before",ordinal,True);emit(token,"frame.after",ordinal,True)
    return {"schema_version":1,"profile":m.PROFILE,"token":"a"*64,"source_contract_sha256":m.CONTRACT_SHA,"source_sha256":"b"*64,
            "status":"complete","failure":"","executed":1,"failures":0,"caseIds":list(m.CASE_IDS),"owner_count":2,
            "frame_counts":list(counts),"row_count":len(rows),"checksum":m.checksum(rows),"rows":rows}


def main():
    m=load();work=Path(tempfile.mkdtemp(prefix="tablet native trace inert & spaces-",dir=ROOT/"build"))
    expected={"schema_version":1,"profile":m.PROFILE,"token":"a"*64,"source_contract_sha256":m.CONTRACT_SHA,"source_sha256":"b"*64,"frame_mask":8}
    base=fixture(m)
    actions=[]
    def add(name,action,reject=False):actions.append((name,action,reject))
    def check(condition,message):
        if not condition:raise AssertionError(message)
    def value_fault(key,value):
        changed=copy.deepcopy(base);changed[key]=value
        return m.validate_trace(changed,expected)
    def expected_fault(key,value):
        changed=copy.deepcopy(expected);changed[key]=value
        return m.validate_trace(base,changed)
    def row_fault(index,key,value):
        changed=copy.deepcopy(base);parts=changed['rows'][index].split('|');parts[WIRE.index(key)]=value
        changed['rows'][index]='|'.join(parts);changed['checksum']=m.checksum(changed['rows'])
        return m.validate_trace(changed,expected)
    def rows_fault(action):
        changed=copy.deepcopy(base);action(changed['rows'])
        changed['checksum']=m.checksum(changed['rows']);changed['row_count']=len(changed['rows'])
        return m.validate_trace(changed,expected)
    add('positive.minimum',lambda:m.validate_trace(base,expected))
    add('positive.maximum',lambda:m.validate_trace(fixture(m,(200,200)),expected))
    add('positive.unequal-counts',lambda:m.validate_trace(fixture(m,(3,7)),expected))
    add('positive.owner1-frames-before-second-init',lambda:m.validate_trace(fixture(m,early=2),expected))
    add('positive.unrelated-inherited-mask',lambda:mask_fixture(m,expected,10))
    add('positive.signed-zero',lambda:numeric_fixture(m,expected,'-0','-0'))
    add('positive.zero-timestep',lambda:numeric_fixture(m,expected,'0','0'))
    add('positive.maximum-timestep',lambda:numeric_fixture(m,expected,'0','10'))
    add('positive.scientific-text',lambda:numeric_fixture(m,expected,'0e-30','1.6e-2'))
    add('positive.precise-subnormal-text',lambda:numeric_fixture(m,expected,'0','1.4013e-45'))
    add('positive.normalized-five-cases',lambda:check(m.validate_trace(base,expected)['cases']==5,'Wrong case count'))
    add('positive.frozen-wire-order',lambda:check(m.FIELDS==WIRE,'Wire order differs from frozen observer fields'))
    for key in sorted(m.ENVELOPE_FIELDS-{'source_sha256'}):
        add('envelope.missing.'+key,lambda key=key:m.validate_trace({k:v for k,v in base.items() if k!=key},expected),True)
    add('envelope.extra',lambda:m.validate_trace(dict(base,extra=True),expected),True)
    for key,val in [('schema_version',True),('profile','other'),('token','b'*64),('source_contract_sha256','f'*64),
                    ('status','success'),('failure','registry budget exhausted'),('executed',True),('executed',0),
                    ('failures',False),('failures',1),('owner_count',True),('owner_count',1),('row_count',True),
                    ('row_count',15),('row_count',1025),('checksum',True),('checksum',-1),('checksum',1000003),
                    ('frame_counts',[True,3]),('frame_counts',[2,3]),('frame_counts',[201,3]),('frame_counts',[3]),
                    ('frame_counts',[4,3]),('caseIds',list(reversed(m.CASE_IDS))),('caseIds',[m.CASE_IDS[0]]*5),
                    ('rows',None),('rows','not-a-list')]:
        name='envelope.'+key+'.'+repr(val)
        add(name,lambda key=key,val=val:value_fault(key,val),True)
    for status in ('failure','unavailable','timeout','cancelled','stale_input'):
        def action(status=status):
            try:value_fault('status',status)
            except m.TraceFailure as error:
                check(error.status==status,'Terminal status was laundered');raise
        add('envelope.preserve-'+status,action,True)
    add('envelope.wrong-checksum',lambda:value_fault('checksum',(base['checksum']+1)%1000003),True)
    for key in sorted(m.EXPECTED_FIELDS-{'source_sha256'}):
        add('expected.missing.'+key,lambda key=key:m.validate_trace(base,{k:v for k,v in expected.items() if k!=key}),True)
    for key,val in [('schema_version',True),('profile','other'),('token','short'),('source_contract_sha256','f'*64),
                    ('frame_mask',True),('frame_mask',0),('frame_mask',3),('frame_mask',2147483649)]:
        add('expected.'+key+'.'+repr(val),lambda key=key,val=val:expected_fault(key,val),True)
    add('expected.extra',lambda:m.validate_trace(base,dict(expected,extra=True)),True)
    for key in m.BOOL_FIELDS:
        add('wire.nonliteral-bool.'+key,lambda key=key:row_fault(4,key,'true'),True)
    for key in ('sequence','token','ordinal','mode','mask'):
        for text in ('+1','01','-0','1.0','21474836480'):
            add('wire.integer.'+key+'.'+text,lambda key=key,text=text:row_fault(4,key,text),True)
    for key in ('accumulator','timeSlice'):
        for text in ('nan','NaN','inf','-inf','1e9999','','1,0','1x',' 0','0 ','1'*65):
            add('wire.numeric.'+key+'.'+repr(text),lambda key=key,text=text:row_fault(4,key,text),True)
    add('wire.numeric-underflow-is-not-zero',lambda:row_fault(4,'accumulator','1e-500'),True)
    add('wire.negative-time',lambda:row_fault(4,'timeSlice','-0.01'),True)
    add('wire.over-time',lambda:row_fault(4,'timeSlice','10.0001'),True)
    add('wire.nonzero-init-time',lambda:row_fault(0,'timeSlice','0.016'),True)
    add('wire.different-pair-time',lambda:row_fault(5,'timeSlice','0.017'),True)
    add('wire.rounded-parser-alias-time',lambda:row_fault(5,'timeSlice','0.0160000000000000000000000001'),True)
    add('wire.nonzero-accumulator',lambda:row_fault(4,'accumulator','0.00000001'),True)
    add('wire.nonstowed-mode',lambda:row_fault(4,'mode','1'),True)
    for key in ('ownerMatches','ownerWorldPresent','gameWorldPresent','gameWorldMatches','statePresent','sameState','uiAbsent','screenAbsent'):
        add('state.false.'+key,lambda key=key:row_fault(4,key,'0'),True)
    add('state.unobserved-independence',lambda:row_fault(0,'independenceObserved','1'),True)
    add('state.unobserved-result',lambda:row_fault(0,'independentState','1'),True)
    add('state.missing-second-independence',lambda:row_fault(2,'independenceObserved','0'),True)
    add('state.aliased-second-state',lambda:row_fault(2,'independentState','0'),True)
    add('mask.missing-init-frame-bit',lambda:row_fault(1,'mask','2'),True)
    add('mask.changed-frame',lambda:row_fault(4,'mask','10'),True)
    add('mask.changed-after',lambda:row_fault(5,'mask','10'),True)
    for key,text in [('sequence','1'),('token','2'),('ordinal','2'),('stage','frame.after')]:
        add('order.first-init-'+key,lambda key=key,text=text:row_fault(0,key,text),True)
    add('order.owner2-before-owner1',lambda:row_fault(0,'token','2'),True)
    add('order.missing-before',lambda:row_fault(4,'stage','frame.after'),True)
    add('order.wrong-after-token',lambda:row_fault(5,'token','2'),True)
    add('order.wrong-after-ordinal',lambda:row_fault(5,'ordinal','2'),True)
    add('order.wrong-after-stage',lambda:row_fault(5,'stage','init.after'),True)
    add('order.unknown-stage',lambda:row_fault(4,'stage','delete.before'),True)
    add('order.duplicate-frame-ordinal',lambda:row_fault(8,'ordinal','1'),True)
    add('order.skipped-frame-ordinal',lambda:row_fault(8,'ordinal','3'),True)
    add('rows.truncated-prefix',lambda:rows_fault(lambda rows:rows.pop()),True)
    add('rows.extra-suffix',lambda:rows_fault(lambda rows:rows.append(rows[-1])),True)
    add('rows.pair-interleaving',lambda:rows_fault(lambda rows:swap(rows,5,6)),True)
    add('rows.owner2-frame-before-init-repaired',lambda:rows_fault(lambda rows:swap_pairs(rows,2,6)),True)
    add('wire.missing-column',lambda:rows_fault(lambda rows:rows.__setitem__(4,'|'.join(rows[4].split('|')[:-1]))),True)
    add('wire.extra-column',lambda:rows_fault(lambda rows:rows.__setitem__(4,rows[4]+'|0')),True)
    add('wire.newline',lambda:rows_fault(lambda rows:rows.__setitem__(4,rows[4]+'\n')),True)
    add('wire.non-ascii',lambda:m.parse_row('é'),True)
    add('wire.too-long',lambda:m.parse_row('0'*513),True)
    add('wire.nonstring',lambda:m.parse_row(True),True)
    for name,raw in [('duplicate',b'{"schema_version":1,"schema_version":1}'),('nonstandard',b'{"x":NaN}'),
                     ('malformed',b'{"x":'),('bad-utf8',b'\xff')]:
        p=work/(name+'.json');p.write_bytes(raw)
        add('json.'+name,lambda p=p:m.read_json(p),True)
    valid=work/'valid.json';save(valid,base)
    add('json.valid',lambda:check(m.read_json(valid)==base,'JSON changed'))
    large=work/'too-large.json';large.write_bytes(b' '*(2*1024*1024+1))
    add('json.bounded',lambda:m.read_json(large),True)
    add('source.expected-missing',lambda:m.validate_trace(base,{k:v for k,v in expected.items() if k!='source_sha256'}),True)
    add('source.completion-missing',lambda:m.validate_trace({k:v for k,v in base.items() if k!='source_sha256'},expected),True)
    add('source.expected-boolean',lambda:expected_fault('source_sha256',True),True)
    add('source.expected-short',lambda:expected_fault('source_sha256','short'),True)
    add('source.completion-mismatch',lambda:value_fault('source_sha256','c'*64),True)
    add('source.completion-boolean',lambda:value_fault('source_sha256',True),True)
    add('wire.precise-over-time',lambda:row_fault(4,'timeSlice','10.00000000000000000001'),True)
    add('wire.negative-underflow-time',lambda:row_fault(4,'timeSlice','-1e-500'),True)
    def oversized_actual_read():
        observed=[]
        original_open=Path.open
        class InjectedGrowingRead:
            def __enter__(self):self.real=original_open(valid,'rb');return self
            def __exit__(self,*args):self.real.close()
            def fileno(self):return self.real.fileno()
            def read(self,maximum):observed.append(maximum);return b' '*(maximum)
        def opening(path,*args,**kwargs):
            return InjectedGrowingRead() if path==valid else original_open(path,*args,**kwargs)
        try:
            with patch.object(Path,'open',opening):m.read_json(valid)
        finally:check(observed==[m.MAX_JSON_BYTES+1],'Actual read was not bounded at max+1')
    add('reader.actual-read-excess-injected',oversized_actual_read,True)
    def incomplete_read():
        original_open=Path.open
        class InjectedShortRead:
            def __enter__(self):self.real=original_open(valid,'rb');return self
            def __exit__(self,*args):self.real.close()
            def fileno(self):return self.real.fileno()
            def read(self,maximum):return self.real.read(maximum)[:-1]
        def opening(path,*args,**kwargs):return InjectedShortRead() if path==valid else original_open(path,*args,**kwargs)
        with patch.object(Path,'open',opening):return m.read_json(valid)
    add('reader.incomplete-read-injected',incomplete_read,True)
    add('reader.missing-input',lambda:m.read_json(work/'absent.json'),True)
    def injected_stat(**changes):
        original_lstat=Path.lstat
        observed=original_lstat(valid)
        fields={name:getattr(observed,name) for name in ('st_dev','st_ino','st_nlink','st_size','st_mtime_ns','st_mode')}
        fields.update(changes)
        def reading(path,*args,**kwargs):return SimpleNamespace(**fields) if path==valid else original_lstat(path,*args,**kwargs)
        with patch.object(Path,'lstat',reading):return m.read_json(valid)
    add('reader.nonregular-injected',lambda:injected_stat(st_mode=stat.S_IFIFO),True)
    add('reader.multilink-injected',lambda:injected_stat(st_nlink=2),True)
    add('reader.replaced-handle-injected',lambda:injected_stat(st_ino=valid.lstat().st_ino+1),True)
    planned=[name for name,_,_ in actions]
    check(len(planned)==len(set(planned)),'Duplicate planned test case')
    inputs=[Path(__file__).resolve(),SOURCE,PACKAGE/'source-contracts.json',PACKAGE/'observer.c.in']
    tracked={str(p):identity(p) for p in inputs}
    for i,p in enumerate(inputs):
        raw=p.read_bytes();dest=work/'inputs'/(str(i).zfill(2)+'-'+p.name);dest.parent.mkdir(parents=True,exist_ok=True)
        check(dest.write_bytes(raw)==len(raw) and dest.read_bytes()==raw,'Incomplete retained input')
    record={'schema_version':1,'operation':'verify.tablet_native_trace.inert','status':'failure','expected_case_ids':planned,
            'expected_cases':len(planned),'cases':[],'failures':[],'verification_inputs':tracked,'synthetic_completion':base,
            'synthetic_expected':expected,'scope':{'python':'pure_checker_and_owned_json','compiler':'not_run','host':'not_run',
                                                  'engine':'not_run','native_callbacks':'not_run','signals':'not_run'}}
    save(work/'result.json',record)
    for name,action,reject in actions:
        item={'id':name,'status':'failure','expected_outcome':'rejection' if reject else 'success'}
        try:
            action();check(not reject,'Expected rejection missing');item['status']='success'
        except m.TraceFailure as error:
            item['actual_rejection']={'status':error.status,'message':str(error)}
            if reject:item['status']='success'
        except BaseException as error:item['error']={'type':type(error).__name__,'message':str(error)}
        record['cases'].append(item)
        if item['status']!='success':record['failures'].append(name)
        save(work/'cases'/(str(len(record['cases'])).zfill(3)+'.json'),item)
    check({str(p):identity(p) for p in inputs}==tracked,'Source changed during inert gate')
    record.update(completed_case_ids=[case['id'] for case in record['cases']],source_unchanged=True,
                  passed=len(planned)-len(record['failures']),failed=len(record['failures']))
    check(record['completed_case_ids']==planned,'Incomplete planned case set')
    record['status']='success' if not record['failures'] else 'failure';save(work/'result.json',record)
    print(json.dumps({'path':str(work/'result.json'),'sha256':identity(work/'result.json')['sha256'],
                      'expected':len(planned),'passed':record['passed'],'failed':record['failed'],'failures':record['failures']}),flush=True)
    return 0 if record['status']=='success' else 1


def mask_fixture(m,expected,mask):
    value=fixture(m)
    for i,row in enumerate(value['rows']):
        parts=row.split('|')
        if parts[2]!='init.before':parts[15]=str(mask)
        value['rows'][i]='|'.join(parts)
    value['checksum']=m.checksum(value['rows'])
    return m.validate_trace(value,expected)


def numeric_fixture(m,expected,accumulator,time):
    value=fixture(m)
    for i,row in enumerate(value['rows']):
        parts=row.split('|');parts[13]=accumulator
        if parts[2].startswith('frame.'):parts[14]=time
        value['rows'][i]='|'.join(parts)
    value['checksum']=m.checksum(value['rows'])
    return m.validate_trace(value,expected)


def swap(rows,a,b):rows[a],rows[b]=rows[b],rows[a]


def swap_pairs(rows,a,b):
    rows[a:a+2],rows[b:b+2]=rows[b:b+2],rows[a:a+2]
    for i,row in enumerate(rows):
        parts=row.split('|');parts[0]=str(i);rows[i]='|'.join(parts)


if __name__=='__main__':raise SystemExit(main())
