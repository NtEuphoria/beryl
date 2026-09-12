"""Experimental IR C matrix; never enables a public compiler lowering path."""
import argparse,ast,hashlib,json,os,re,shutil,subprocess,tempfile,time,sys
from pathlib import Path
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parent))
from receipt_validation import validate_probe, selftest as receipt_selftest
if not __debug__:raise SystemExit('verification requires Python assertions; do not use -O or -OO')
ap=argparse.ArgumentParser();ap.add_argument('--baseline',type=Path,default=Path(__file__).resolve().parents[2],help='source root; defaults to this package\'s checkout');ap.add_argument('--clang',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--limit',type=int,default=0);ap.add_argument('--ast-backend-overlay',type=Path);args=ap.parse_args()
if args.limit<0:ap.error('--limit must be nonnegative; zero selects the full gate')
args.baseline=args.baseline.resolve(strict=True);args.clang=args.clang.resolve(strict=True);args.output=args.output.resolve(strict=True)
if args.ast_backend_overlay:args.ast_backend_overlay=args.ast_backend_overlay.resolve(strict=True)
stage=Path(__file__).resolve().parent;out=Path(tempfile.mkdtemp(prefix='ir-c-',dir=args.output));snap=out/'inputs'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def source_manifest(root):
    result={}
    for name in ('src','runtime','packages','tests'):
        folder=root/name
        if not folder.is_dir():raise RuntimeError('source root is missing directory: '+str(folder))
        for p in sorted(folder.rglob('*')):
            if p.is_file():result[p.relative_to(root).as_posix()]=sha(p)
    return result
owned=[stage/'src/ir/c_emit.c',stage/'src/ir/c_emit.h',stage/'probe.c',stage/'check.py',stage/'receipt_validation.py'];before={p.relative_to(stage).as_posix():sha(p) for p in owned}
baseline_before=source_manifest(args.baseline)
for name in ('src','runtime','packages','tests'):shutil.copytree(args.baseline/name,snap/name)
baseline_copied=source_manifest(snap);baseline_after=source_manifest(args.baseline)
if not baseline_before==baseline_copied==baseline_after:raise RuntimeError('source capture changed; no compiler or test executable was built')
for p in owned:shutil.copyfile(p,snap/p.relative_to(stage))
if not before=={p.relative_to(stage).as_posix():sha(p) for p in owned}=={name:sha(snap/name) for name in before}:raise RuntimeError('experimental overlay changed during capture; no compiler or test executable was built')
backend_overlay=None
if args.ast_backend_overlay:
    expected_hash=sha(args.ast_backend_overlay);shutil.copyfile(args.ast_backend_overlay,snap/'src/back/c_backend.c')
    assert sha(args.ast_backend_overlay)==sha(snap/'src/back/c_backend.c')==expected_hash
    backend_overlay={'path':str(args.ast_backend_overlay.resolve()),'sha256':expected_hash}
r={'status':'running','baseline':str(args.baseline),'overlay':before,'sources':{p.relative_to(snap).as_posix():sha(p) for p in sorted(snap.rglob('*')) if p.is_file()},'commands':[],'cases':[],'ast_parity_failures':[]}
r['source_capture']={'status':'verified_before_copy_after','baseline_files':baseline_before,'file_count':len(baseline_before),'overlay_files':before}
r['ast_backend_overlay']=backend_overlay
r['mode']='pilot' if args.limit else 'full';r['gate_complete']=False
env=os.environ.copy();env['PATH']=str(args.clang.parent)+os.pathsep+env.get('PATH','')
def run(argv):
    start=time.monotonic();p=subprocess.run(list(map(str,argv)),cwd=snap,env=env,capture_output=True,timeout=600)
    r['commands'].append({'argv':list(map(str,argv)),'exit':p.returncode,'seconds':time.monotonic()-start,'stdout':p.stdout.decode(errors='replace'),'stderr':p.stderr.decode(errors='replace')})
    if p.returncode:raise RuntimeError(p.stdout.decode(errors='replace')+'\n'+p.stderr.decode(errors='replace'))
    return p
def strings(s):return ''.join(ast.literal_eval(x) for x in re.findall(r'"(?:\\.|[^"\\])*"',s))
def extract():
    text=(snap/'tests/unit/test_ir.c').read_text();result=[]
    for match in re.finditer(r'\bparity\(\s*"',text):
        pos=match.start()+len('parity(');start=pos;depth=0;quoted=False;escape=False;parts=[]
        while pos<len(text):
            c=text[pos]
            if quoted:
                if escape:escape=False
                elif c=='\\':escape=True
                elif c=='"':quoted=False
            elif c=='"':quoted=True
            elif c=='(':depth+=1
            elif c==')':
                if depth==0:parts.append(text[start:pos]);break
                depth-=1
            elif c==',' and depth==0:parts.append(text[start:pos]);start=pos+1
            pos+=1
        if len(parts)!=5:raise RuntimeError(parts)
        result.append({'name':strings(parts[0]),'source':strings(parts[1]),'status':parts[2].strip(),'assertions':int(parts[3]),'output':strings(parts[4])})
    return result
def logs(folder,name):
    # process_run retains binary raw logs. Only whole JSON event lines count.
    stdout=(folder/(name+'.stdout.log')).read_bytes();stderr=(folder/(name+'.stderr.log')).read_bytes()
    events=b''.join(x+b'\n' for x in stderr.splitlines() if x.startswith(b'{"event":'))
    for x in events.splitlines():json.loads(x)
    return stdout,events
def mutation_checks():
    definitions=[
        ('missing_print_event','structured control',lambda c:re.sub(r'beryl_test_event\("print"[^\n]*\n','',c,count=1)),
        ('arithmetic_replacement','structured control',lambda c:c.replace('be_add_i32_at(', 'be_sub_i32_at(',1)),
        ('missing_trap_terminal','bounds failure precedes destination',lambda c:re.sub(r'be_idx_at\((v_\d+), (\d+), (be_ir_file_\d+), (\d+), \d+, \d+\)',r'be_idx(\1, \2, \3, \4)',c,count=1)),
        ('wrong_trap_site','bounds failure precedes destination',lambda c:re.sub(r'(be_idx_at\(v_\d+, \d+, be_ir_file_\d+, \d+, \d+, )(\d+)(\))',lambda m:m[1]+str(int(m[2])+1)+m[3],c,count=1)),
        ('extra_array_write','dynamic compound destination',lambda c:re.sub(r'(v_(\d+)\.items\[1\] = v_(\d+);)',lambda m:m[1]+f'\nv_{m[2]}.items[0] = v_{m[3]};',c,count=1)),
        ('missing_finite_guard','nonfinite result stays',lambda c:c.replace('if(!isfinite(y))be_ir_domain("outside finite IR domain",f,l);','',1)),
    ]
    r['mutation_checks']=[]
    for name,phrase,edit in definitions:
        match=next(i for i,x in enumerate(cases) if phrase in x['name']);baseline=out/f'case-{match:02d}'
        original=(baseline/'ir.c').read_text();mutated=edit(original);assert original!=mutated,(name,'mutation missing')
        folder=out/('mutant-'+name);folder.mkdir();c=folder/'mutant.c';c.write_text(mutated);exe=folder/'mutant.exe'
        cmd=[args.clang,'-std=c11','-O2','-ffp-contract=off','-fno-fast-math','-fsanitize=undefined','-fno-sanitize-recover=all','-I',snap/'runtime',c,snap/'runtime/beryl_rt.c','-o',exe]
        run(cmd);start=time.monotonic();p=subprocess.run([str(exe)],cwd=snap,env=env,capture_output=True,timeout=20)
        (folder/'run.stdout.log').write_bytes(p.stdout);(folder/'run.stderr.log').write_bytes(p.stderr)
        stdout,events=logs(folder,'run');expected=(baseline/'ir-eval.stdout').read_bytes();expected_events=(baseline/'ir-eval.events').read_bytes()
        assert (stdout,events)!=(expected,expected_events),(name,'survived independent observations')
        r['mutation_checks'].append({'name':name,'case':match,'exit':p.returncode,'seconds':time.monotonic()-start,'source_sha256':sha(c),'executable_sha256':sha(exe),'stdout_sha256':sha(folder/'run.stdout.log'),'stderr_sha256':sha(folder/'run.stderr.log'),'status':'detected'})
    # Fast-math must fail during compilation, not merely happen to pass fixtures.
    folder=out/'reject-fast-math';folder.mkdir();cmd=[args.clang,'-std=c11','-ffast-math','-I',snap/'runtime','-c',out/'case-00/ir.c','-o',folder/'ir.o']
    p=subprocess.run(list(map(str,cmd)),cwd=snap,env=env,capture_output=True,timeout=120)
    (folder/'compile.stderr.log').write_bytes(p.stderr);assert p.returncode and b'IR C requires finite checks' in p.stderr
    r['fast_math_rejected']={'exit':p.returncode,'argv':list(map(str,cmd)),'stderr_sha256':sha(folder/'compile.stderr.log')}
    # This is valid bounded IR but intentionally outside C stack-storage
    # admission. Rejection must leave no usable IR-generated C artifact.
    folder=out/'reject-large-frame';folder.mkdir();fixture=snap/'large-frame.be'
    array='['+','.join(map(str,range(256)))+']'
    fixture.write_text('module t\ntest "frame" {\n'+''.join(f'let x{i} = {array}\n' for i in range(33))+'}\n')
    cmd=[probe,folder,args.clang,snap/'runtime',fixture.name]
    p=subprocess.run(list(map(str,cmd)),cwd=snap,env=env,capture_output=True,timeout=120)
    (folder/'probe.stderr.log').write_bytes(p.stderr)
    assert p.returncode==2 and b'C test function exceeds 64 KiB declared-storage admission' in p.stderr and not (folder/'ir.c').exists()
    r['large_frame_rejected']={'exit':p.returncode,'argv':list(map(str,cmd)),'fixture_sha256':sha(fixture),'stderr_sha256':sha(folder/'probe.stderr.log')}
    r['frontend_admission_checks']=[]
    for name,literal in [('missing_effectful_default','R{b: 2}'),('copy_effectful_default','R{}')]:
        folder=out/('reject-'+name);folder.mkdir();fixture=snap/(name+'.be')
        fixture.write_text('module t\nfn mark(let n: i32) -> i32 { println(n)\nreturn n }\nstruct R { a: i32 = mark(10)\nb: i32 = 20 }\ntest "rejected" { let r = '+literal+'\nlet copy = r\nassert(copy.b == 2) }\n')
        p=subprocess.run(list(map(str,[probe,folder,args.clang,snap/'runtime',fixture.name])),cwd=snap,env=env,capture_output=True,timeout=120)
        (folder/'probe.stderr.log').write_bytes(p.stderr)
        assert p.returncode==2 and b'BE0501' in p.stderr and not (folder/'ir.c').exists() and not (folder/'ast.c').exists()
        r['frontend_admission_checks'].append({'name':name,'exit':p.returncode,'fixture_sha256':sha(fixture),'stderr_sha256':sha(folder/'probe.stderr.log'),'status':'rejected_BE0501'})
def selection_checks():
    folder=out/'selection-checks';folder.mkdir()
    common=[sys.executable,'-I',snap/'check.py','--baseline',args.baseline,'--clang',args.clang,'--output',folder]
    if args.ast_backend_overlay:common+=['--ast-backend-overlay',args.ast_backend_overlay]
    p=subprocess.run(list(map(str,[*common,'--limit','-1'])),cwd=snap,env=env,capture_output=True,timeout=30)
    (folder/'negative.stderr.log').write_bytes(p.stderr)
    assert p.returncode==2 and b'--limit must be nonnegative' in p.stderr
    assert not any(x.is_dir() for x in folder.iterdir())
    pilot=run([*common,'--limit','1']);receipt=Path(pilot.stdout.decode().strip().splitlines()[-1]).resolve()
    assert receipt.is_relative_to(folder.resolve())
    selected=json.loads(receipt.read_text());assert selected['status']=='pilot_passed' and selected['gate_complete'] is False and selected['mode']=='pilot' and len(selected['cases'])==1
    r['selection_checks']={'negative_exit':p.returncode,'negative_stderr_sha256':sha(folder/'negative.stderr.log'),'pilot_receipt':str(receipt),'pilot_receipt_sha256':sha(receipt),'pilot_status':selected['status'],'pilot_gate_complete':selected['gate_complete']}
print(out,flush=True)
try:
    r['receipt_validation_checks']={'kind':'synthetic_malformed_receipts','checks':receipt_selftest()}
    r['clang']=run([args.clang,'--version']).stdout.decode();r['clang_sha256']=sha(args.clang);probe=out/'probe.exe'
    sources=[p for p in sorted((snap/'src').rglob('*.c')) if p.name!='main.c']+[snap/'probe.c']
    run([args.clang,'-std=c11','-O1','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-ffp-contract=off','-fsanitize=undefined','-fno-sanitize-recover=all','-Isrc',*sources,'-o',probe]);r['probe_sha256']=sha(probe)
    cases=extract()
    expected_names=[x['name'] for x in cases]
    assert len(cases)==31 and len(set(expected_names))==31 and hashlib.sha256(json.dumps(expected_names,ensure_ascii=True,separators=(',',':')).encode()).hexdigest()=='4664a60c79a68a7f5b727247adf8a9f56303780192102ad5da8c22fb0a18e0e0','full analytical fixture-name set changed; review its admission and expected outputs'
    if args.limit:cases=cases[:args.limit]
    else:
        cases += [
            {'name':'Native record missing constant defaults preserve explicit overrides','source':'module t\nfn mark(let n: i32) -> i32 { println(n)\nreturn n }\nstruct R { a: i32 = 10\nb: i32 = 20 }\ntest "defaults" { let r = R{b: mark(2)}\nassert(r.a == 10)\nassert(r.b == 2) }\n','status':'IR_RUN_SUCCESS','assertions':2,'output':'2\nok  1 test, 2 assertions\n'},
            {'name':'Native record copy and return retain values changed from defaults','source':'module t\nstruct R { a: i32 = 10\nb: i32 = 20 }\nfn copy(let value: R) -> R { return value }\ntest "copy" { let r = R{}\nvar c = r\nc.a = 99\nlet returned = copy(c)\nprintln(returned.a)\nassert(r.a == 10)\nassert(returned.a == 99)\nassert(returned.b == 20) }\n','status':'IR_RUN_SUCCESS','assertions':3,'output':'99\nok  1 test, 3 assertions\n'},
            {'name':'IR-C step guard stays uncertified','source':'module t\ntest "budget" { println(1)\nwhile true { } }\n','status':'IR_RUN_BUDGET','assertions':0,'output':'1\n','diagnostic':'IR step budget'},
            {'name':'IR-C recursive call guard stays uncertified','source':'module t\nfn recurse(let n: i32) -> i32 { return recurse(n + 1) }\ntest "budget" { println(1)\nprintln(recurse(0)) }\n','status':'IR_RUN_BUDGET','assertions':0,'output':'1\n','diagnostic':'IR call depth'},
            {'name':'complete existing SPARKOS PID','paths':['packages/sparkos/pid/pid.be','packages/sparkos/pid/pid_test.be'],'status':'IR_RUN_SUCCESS','assertions':2206}]
    r['expected_case_names']=[x['name'] for x in cases]
    assert cases and (args.limit or len(cases)==36)
    for index,case in enumerate(cases):
        failures_before=len(r['ast_parity_failures'])
        folder=out/f'case-{index:02d}';folder.mkdir();record={k:v for k,v in case.items() if k!='source'};r['cases'].append(record)
        if 'source'in case:
            fixture=snap/f'fixture-{index:02d}.be';fixture.write_text(case['source'],encoding='utf-8',newline='');paths=[fixture.name]
        else:paths=case['paths']
        record['input_hashes']={x:sha(snap/x) for x in paths}
        run([probe,folder,args.clang,snap/'runtime',*paths]);result=json.loads((folder/'probe.json').read_text());record['probe']=result
        validate_probe(result,case['status'],case['assertions'],8 if 'paths' in case else 1)
        expected=(folder/'reference.stdout').read_bytes();events=(folder/'reference.events').read_bytes()
        assert expected==(folder/'ir-eval.stdout').read_bytes(),(case['name'],'reference/IR output')
        assert events==(folder/'ir-eval.events').read_bytes(),(case['name'],'reference/IR events')
        if 'output'in case:assert expected==case['output'].encode(),(case['name'],'analytical output')
        assert result['assertions']==case['assertions']
        assert result['ir_status']=={'IR_RUN_SUCCESS':0,'IR_RUN_FAILED':1,'IR_RUN_TRAP':2,'IR_RUN_BUDGET':3}[case['status']]
        assert result['reference_status']=={'IR_RUN_SUCCESS':0,'IR_RUN_FAILED':1,'IR_RUN_TRAP':3,'IR_RUN_BUDGET':4}[case['status']]
        # Nonfinite/cast exits are deliberately excluded from the AST-C parity
        # matrix; ordinary native AST code currently has a wider numeric domain.
        domain_exit=(case['status']=='IR_RUN_TRAP' and result['ir_trap']==0) or case['status']=='IR_RUN_BUDGET'
        record['ast_c_admitted']=not domain_exit
        for execution in result['processes']:
            name=execution['name']
            if domain_exit and name.startswith('ast'):
                assert execution.get('skipped')=='outside AST-C admitted execution domain';continue
            assert execution['compile_status']==0 and execution['compile_exit']==0,(name,'compile',folder)
            assert execution.get('run_status')==0,(name,'not an executed program',execution)
            stdout,trace=logs(folder,name)
            if name.startswith('ast') and (stdout!=expected or trace!=events):
                # Keep gathering independent IR evidence, but fail the complete
                # cross-backend gate. A known baseline defect is not a pass.
                r['ast_parity_failures'].append({'case':index,'name':case['name'],'backend':name,'stdout_equal':stdout==expected,'events_equal':trace==events})
                continue
            assert stdout==expected,(case['name'],name,'stdout',folder)
            assert trace==events,(case['name'],name,'events',folder)
            if case['status']=='IR_RUN_SUCCESS':assert execution['run_exit']==0
            elif case['status']=='IR_RUN_FAILED':assert execution['run_exit']==1
            else:
                assert execution['run_exit']!=0
                if not domain_exit:assert result['ir_complete'] and result['reference_complete'] and json.loads(trace.splitlines()[-1])['event']=='source_trap'
                else:assert not result['ir_complete'] and not any(json.loads(x)['event']=='source_trap' for x in trace.splitlines())
                if 'diagnostic'in case:assert case['diagnostic'].encode() in (folder/(name+'.stderr.log')).read_bytes()
        record['artifacts']={p.name:sha(p) for p in folder.iterdir() if p.is_file()};record['status']='passed' if failures_before==len(r['ast_parity_failures']) else 'ir_passed_ast_failed';print(index,case['name'],record['status'],flush=True)
    if not args.limit:mutation_checks();selection_checks()
    assert not r['ast_parity_failures'],r['ast_parity_failures']
    r['gate_complete']=not args.limit;r['status']='pilot_passed' if args.limit else 'passed'
except BaseException as exc:r['status']='failed';r['failure']=repr(exc);raise
finally:(out/'results.json').write_text(json.dumps(r,indent=2));print(out/'results.json',flush=True)
