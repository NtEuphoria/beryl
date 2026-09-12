#!/usr/bin/env python3
"""Exercise parser resource rejection through both check and AST-print routes.

Every run uses a copied candidate executable, bounded generated inputs, explicit
subprocess timeouts and retained raw evidence. Success requires BE0210, not just
a failing exit status. The complete current PID sources remain a positive gate.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--beryl', required=True)
    parser.add_argument('--source-root', type=Path, default=ROOT)
    parser.add_argument('--output-root', type=Path, default=ROOT/'build')
    args = parser.parse_args()
    found = shutil.which(args.beryl)
    if not found: raise RuntimeError('Beryl executable unavailable: '+args.beryl)
    original = Path(found).resolve()
    args.output_root.mkdir(parents=True,exist_ok=True)
    out = Path(tempfile.mkdtemp(prefix='parser-limits-',dir=args.output_root.resolve()))
    report = out/'results.json'
    evidence = {'schema_version':1,'operation':'parser_limits_verification','status':'running',
                'compiler_input':str(original),'commands':[],'fixtures':[]}
    def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()
    def run(argv, *, expected=0, timeout=30):
        argv=list(map(str,argv)); started=time.monotonic()
        try:
            result=subprocess.run(argv,cwd=out,capture_output=True,text=True,
                encoding='utf-8',errors='replace',timeout=timeout)
        except (OSError,subprocess.TimeoutExpired) as exc:
            evidence['commands'].append({'argv':argv,'failure':type(exc).__name__,'detail':str(exc)})
            raise
        evidence['commands'].append({'argv':argv,'exit_code':result.returncode,
            'seconds':time.monotonic()-started,'stdout':result.stdout,'stderr':result.stderr})
        if expected is not None and result.returncode!=expected:
            raise RuntimeError(f'Wrong exit {result.returncode}: {argv}\n{result.stdout}\n{result.stderr}')
        return result
    print(out,flush=True)
    try:
        before=digest(original); compiler=out/('beryl'+original.suffix)
        shutil.copyfile(original,compiler)
        if digest(compiler)!=before or digest(original)!=before: raise RuntimeError('Compiler changed while copying')
        evidence['compiler_sha256']=before
        evidence['script_sha256']=digest(Path(__file__))
        run([compiler,'version'])
        def body(expression): return 'module limits\nfn f()->i32{return '+expression+'\n}\n'
        fixtures={
            'parentheses':(body('('*2048+'1'+')'*2048),'recursive parse depth'),
            'unary':(body('!'*2048+'true'),'recursive parse depth'),
            'generic_types':('module limits\nfn f(x:'+'List<'*1024+'i32'+'>'*1024+'){}\n','recursive parse depth'),
            'array_types':('module limits\nfn f(x:'+'['*1024+'i32'+';1]'*1024+'){}\n','recursive parse depth'),
            'error_union_types':('module limits\nfn f(x:'+'!'*1024+'i32){}\n','recursive parse depth'),
            'optional_chain':('module limits\nfn f(x:i32'+'?'*2048+'){}\n','syntax tree depth'),
            'else_if':('module limits\nfn f(){'+'if true {} else '*1024+'{}\n}\n','recursive parse depth'),
            'blocks':('module limits\nfn f(){'+'{'*1024+'}'*1024+'}\n','recursive parse depth'),
            'left_associative':(body('1'+'+1'*5000),'syntax tree depth'),
            'fields':(body('a'+'.x'*5000),'syntax tree depth'),
            'calls':(body('a'+'()'*5000),'syntax tree depth'),
            'indices':(body('a'+'[0]'*5000),'syntax tree depth'),
            'casts':(body('1'+' as i32'*5000),'syntax tree depth'),
            'parameter_work':('module limits\nfn f('+','.join(f'x{i}:i32' for i in range(2048))+'){}\n','parser work'),
            'tokens':('module limits\nfn f(){\n'+'0\n'*131080+'}\n','tokens per file'),
        }
        for name,(source,reason) in fixtures.items():
            path=out/(name+'.be'); path.write_text(source,encoding='utf-8',newline='\n')
            evidence['fixtures'].append({'name':name,'sha256':digest(path),'bytes':path.stat().st_size,'expected':reason})
            for command in ('check','ast'):
                result=run([compiler,command,path],expected=None)
                if result.returncode!=1 or 'BE0210' not in result.stderr or reason not in result.stderr:
                    raise RuntimeError(f'{name}/{command} did not reject through BE0210: {result.returncode}')
                if 'runtime error:' in result.stderr or 'AddressSanitizer' in result.stderr:
                    raise RuntimeError(f'Sanitizer failure in {name}/{command}')
                if command=='ast' and len(result.stdout)>1024:
                    raise RuntimeError('Resource rejection exposed a partial deep AST')
        ordinary=out/'ordinary.be'
        ordinary.write_text(body('('*32+'1+2*3'+')'*32),encoding='utf-8')
        run([compiler,'check',ordinary]); run([compiler,'ast',ordinary])
        pid=[]; evidence['pid_sources']={}
        for name in ('pid.be','pid_test.be'):
            source=args.source_root.resolve()/'packages/sparkos/pid'/name
            expected_hash=digest(source); dest=out/name; shutil.copyfile(source,dest)
            if digest(dest)!=expected_hash or digest(source)!=expected_hash: raise RuntimeError('PID source changed while copying')
            evidence['pid_sources'][name]=expected_hash; pid.append(dest)
        run([compiler,'check',*pid])
        result=run([compiler,'test','--backend','reference',*pid],timeout=90)
        if '8 tests' not in result.stdout or '2206 assertions' not in result.stdout:
            raise RuntimeError('PID reference did not report the complete expected corpus')
        evidence['status']='passed'
    except BaseException as exc:
        evidence['status']='cancelled' if isinstance(exc,KeyboardInterrupt) else 'failed'
        evidence['failure']={'type':type(exc).__name__,'detail':str(exc)}
        raise
    finally:
        report.write_text(json.dumps(evidence,indent=2),encoding='utf-8')
        print(report,flush=True)

if __name__=='__main__': main()
