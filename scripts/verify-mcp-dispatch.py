#!/usr/bin/env python3
"""Exercise genuine inherited stdio dispatch and owned process lifecycle.

Builds an isolated harness from explicit sources; never installs the compiler.
Protocol/server semantics are intentionally tested separately.
"""
import argparse
import base64
import ctypes
import hashlib
import json
import os
from pathlib import Path
import queue
import shutil
import subprocess
import tempfile
import threading
import time

HARNESS = r'''
#ifndef _WIN32
#define _POSIX_C_SOURCE 200809L
#endif
#include "src/driver/process.h"
#include "src/driver/mcp_driver.h"
#include "tests/unit/test.h"
#include <signal.h>
#include <stdlib.h>
#include <string.h>
#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <io.h>
#include <fcntl.h>
static DWORD WINAPI cancel_later(LPVOID value) { Sleep((DWORD)(uintptr_t)value); raise(SIGTERM); return 0; }
#else
#include <pthread.h>
#include <time.h>
#include <unistd.h>
static void *cancel_later(void *value) { unsigned n=(unsigned)(uintptr_t)value; struct timespec t={n/1000,(n%1000)*1000000}; nanosleep(&t,NULL); raise(SIGTERM); return NULL; }
#endif
int driver_child(int,char **);
void run_driver_tests(const char *);
int main(int argc,char **argv) {
    Arena *arguments=arena_new(0); /* process-lifetime argv owner */
    if (!process_utf8_arguments(arguments,&argc,&argv)) return 92;
    if (argc>1 && !strcmp(argv[1],"--driver-child")) return driver_child(argc,argv);
#ifdef _WIN32
    _setmode(_fileno(stdout),_O_BINARY); _setmode(_fileno(stderr),_O_BINARY);
#endif
    process_install_signals();
    if (argc==3 && !strcmp(argv[1],"--environment")) {
        const char *value=NULL; bool ok=process_environment(arguments,argv[2],&value);
        if (ok && value) fwrite(value,1,strlen(value),stdout);
        fputs(ok?(value?"present":"absent"):"invalid",stderr); return ok?0:2;
    }
#ifdef _WIN32
    if (argc==2 && !strcmp(argv[1],"--environment-invalid")) {
        const wchar_t invalid[]={0xd800,0};
        if (!SetEnvironmentVariableW(L"BERYL_INVALID_UTF16",invalid)) return 93;
        const char *value=NULL; bool ok=process_environment(arguments,"BERYL_INVALID_UTF16",&value);
        fputs(!ok && !value?"invalid":"incorrect",stderr); return !ok && !value?0:2;
    }
#endif
    if (argc>1 && !strcmp(argv[1],"--unit")) { run_driver_tests(argv[0]); return t_summary(); }
    if (argc>5 && !strcmp(argv[1],"--process")) {
        unsigned timeout=(unsigned)strtoul(argv[2],NULL,10), cancel=(unsigned)strtoul(argv[3],NULL,10);
#ifdef _WIN32
        HANDLE thread=NULL;
        if (cancel) { thread=CreateThread(NULL,0,cancel_later,(LPVOID)(uintptr_t)cancel,0,NULL); if (!thread) return 91; }
        if (!strcmp(argv[4],"missing-input")) SetStdHandle(STD_INPUT_HANDLE,NULL);
        if (!strcmp(argv[4],"missing-output")) SetStdHandle(STD_OUTPUT_HANDLE,INVALID_HANDLE_VALUE);
        if (!strcmp(argv[4],"missing-error")) SetStdHandle(STD_ERROR_HANDLE,NULL);
#else
        pthread_t thread;
        if (cancel && pthread_create(&thread,NULL,cancel_later,(void *)(uintptr_t)cancel)) return 91;
        if (!strcmp(argv[4],"missing-input")) close(STDIN_FILENO);
#endif
        Arena *a=arena_new(0);
        ProcessResult r=process_run(a,(ProcessOpts){.argv=(const char *const *)(argv+5),.inherit_stdio=true,.timeout_ms=timeout});
        fprintf(stderr,"PROCESS_RESULT {\"status\":\"%s\",\"exit_code\":%u,\"os_error\":%u,\"captured\":%s}\n",
            process_status_name(r.status),r.exit_code,r.os_error,(r.stdout_path || r.stderr_path || r.out.len || r.err.len)?"true":"false");
        arena_free(a);
#ifdef _WIN32
        if (thread) { WaitForSingleObject(thread,INFINITE); CloseHandle(thread); }
#else
        if (cancel) pthread_join(thread,NULL);
#endif
        return 0;
    }
    return driver_mcp(argc-1,argv+1);
}
'''

ECHO = '''import base64,json,sys
print(json.dumps({"argv":sys.argv,"isolated":bool(sys.flags.isolated)}),flush=True)
sys.stderr.buffer.write(b"child-stderr\\n");sys.stderr.buffer.flush()
for line in sys.stdin.buffer:
    print(json.dumps({"echo":base64.b64encode(line).decode("ascii")}),flush=True)
sys.exit(7 if "exit-seven" in sys.argv else 0)
'''

TREE = '''import json,subprocess,sys,time
child=subprocess.Popen([sys.executable,"-I","-c","import time;time.sleep(60)"])
print(json.dumps({"descendant":child.pid}),flush=True)
if "normal-exit" not in sys.argv: time.sleep(60)
'''

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source-root',type=Path,default=Path(__file__).resolve().parents[1])
    ap.add_argument('--clang',required=True,type=Path)
    ap.add_argument('--python',required=True,type=Path)
    ap.add_argument('--beryl',type=Path,help='Optional full compiler for dispatcher protocol-pipe checks')
    ap.add_argument('--output-root',type=Path,default=Path('build'))
    args=ap.parse_args();source=args.source_root.resolve();clang=args.clang.resolve();python=args.python.resolve()
    args.output_root.mkdir(parents=True,exist_ok=True)
    out=Path(tempfile.mkdtemp(prefix='mcp-dispatch-',dir=args.output_root.resolve()));snap=out/'inputs'
    def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
    selected=[*sorted((source/'src/common').glob('*.[ch]'))]
    selected += [source/p for p in ('src/driver/process.c','src/driver/process.h','src/driver/mcp_driver.c','src/driver/mcp_driver.h','src/driver/manifest.c','src/driver/manifest.h','tests/unit/test.c','tests/unit/test.h','tests/unit/test_driver.c')]
    before={p.relative_to(source).as_posix():sha(p) for p in selected}
    for p in selected:
        dest=snap/p.relative_to(source);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest)
    if before!={p.relative_to(source).as_posix():sha(p) for p in selected}:raise RuntimeError('sources changed during capture')
    report={'schema_version':1,'status':'running','source_hashes':before,'commands':[],'checks':[],'platform':os.name,
            'runner_sha256':sha(Path(__file__)),'python_sha256':sha(python),'sessions':[],'process_cases':[],'environment_cases':[]}
    env=os.environ.copy();env['PATH']=str(clang.parent)+os.pathsep+env.get('PATH','')
    def run(command,**kwargs):
        command=list(map(str,command));start=time.monotonic()
        result=subprocess.run(command,cwd=snap,env=env,capture_output=True,timeout=30,**kwargs)
        report['commands'].append({'argv':command,'exit_code':result.returncode,'seconds':time.monotonic()-start,'stdout':result.stdout.decode('utf-8','replace'),'stderr':result.stderr.decode('utf-8','replace')})
        if result.returncode:raise AssertionError(report['commands'][-1])
        return result
    def check(name,condition):
        report['checks'].append({'name':name,'passed':bool(condition)})
        if not condition:raise AssertionError(name)
    def record_case(group,name,command,got):
        report[group].append({'name':name,'argv':list(map(str,command)),'exit_code':got.returncode,
            'stdout_base64':base64.b64encode(got.stdout).decode(),'stderr_base64':base64.b64encode(got.stderr).decode()})
    def line(proc):
        found=queue.Queue()
        def read(): found.put(proc.stdout.readline())
        threading.Thread(target=read,daemon=True).start()
        try:return found.get(timeout=8)
        except queue.Empty:
            proc.kill();raise AssertionError('no live protocol response before stdin EOF')
    def tree_stopped(pid):
        if os.name=='nt':
            kernel=ctypes.WinDLL('kernel32',use_last_error=True)
            kernel.OpenProcess.argtypes=[ctypes.c_ulong,ctypes.c_int,ctypes.c_ulong];kernel.OpenProcess.restype=ctypes.c_void_p
            kernel.WaitForSingleObject.argtypes=[ctypes.c_void_p,ctypes.c_ulong];kernel.WaitForSingleObject.restype=ctypes.c_ulong
            kernel.CloseHandle.argtypes=[ctypes.c_void_p]
            handle=kernel.OpenProcess(0x100000,False,pid)
            if not handle:return ctypes.get_last_error()==87
            try:return kernel.WaitForSingleObject(handle,2000)==0
            finally:kernel.CloseHandle(handle)
        # A killed child can remain a zombie until its new parent reaps it.
        status=Path('/proc')/str(pid)/'stat'
        if status.exists():return status.read_text().split(') ',1)[1].startswith('Z')
        try:os.kill(pid,0)
        except ProcessLookupError:return True
        return False
    print(out,flush=True)
    try:
        report['clang_version']=run([clang,'--version']).stdout.decode()
        report['python_version']=run([python,'--version']).stdout.decode()
        (snap/'harness.c').write_text(HARNESS)
        report['harness_source_sha256']=sha(snap/'harness.c')
        harness=out/('process harness & spaces.exe' if os.name=='nt' else 'process harness & spaces')
        sources=[*sorted((snap/'src/common').glob('*.c')),*sorted((snap/'src/driver').glob('*.c')),
                 snap/'tests/unit/test.c',snap/'tests/unit/test_driver.c',snap/'harness.c']
        flags=['-std=c11','-O2','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-I.', '-Isrc']
        if os.name!='nt':flags+=['-pthread']
        run([clang,*flags,*sources,'-o',harness]);report['harness_sha256']=sha(harness)
        unit=run([harness,'--unit']);check('existing captured process/manifest/quoting unit suite',b'ok ' in unit.stdout)
        installed=out/'beryl-tools/mcp.py';installed.parent.mkdir();installed.write_text(ECHO)
        override=out/'trusted override 雪 & spaces.py';override.write_text(ECHO)
        tree=out/'owned tree.py';tree.write_text(TREE)
        report['fixtures']={str(p):sha(p) for p in (installed,override,tree)}
        project=out/'project 雪 & spaces';project.mkdir();(project/'beryl-tools').mkdir()
        (project/'beryl-tools/mcp.py').write_text('raise RuntimeError("project script must not execute")\n')
        (project/'sitecustomize.py').write_text('raise RuntimeError("PYTHONPATH must not load")\n')
        child_env=env.copy();child_env['BERYL_PYTHON']=str(python);child_env['PYTHONPATH']=str(project)
        child_env.pop('BERYL_MCP_TOOL',None)
        for name,value in (('absent',None),('present','雪 & '+str(project)),('empty','')):
            chosen=child_env.copy();chosen.pop('BERYL_TEST_ENVIRONMENT',None)
            if value is not None:chosen['BERYL_TEST_ENVIRONMENT']=value
            got=subprocess.run([str(harness),'--environment','BERYL_TEST_ENVIRONMENT'],cwd=project,env=chosen,capture_output=True,timeout=8)
            record_case('environment_cases',name,[harness,'--environment','BERYL_TEST_ENVIRONMENT'],got)
            # Windows removes empty variables through some environment APIs;
            # the copied CreateProcess environment still exposes its own state.
            check(name+' checked environment lookup',got.returncode==0 and got.stdout==(value or '').encode() and got.stderr==(b'absent' if value is None else b'present'))
        if os.name=='nt':
            got=subprocess.run([str(harness),'--environment-invalid'],cwd=project,env=child_env,capture_output=True,timeout=8)
            record_case('environment_cases','invalid UTF16',[harness,'--environment-invalid'],got)
            check('invalid UTF16 environment fails without fallback',got.returncode==0 and got.stdout==b'' and got.stderr==b'invalid')
        for name in ('','invalid=name','x'*256):
            got=subprocess.run([str(harness),'--environment',name],cwd=project,env=child_env,capture_output=True,timeout=8)
            record_case('environment_cases','invalid name',[harness,'--environment',name],got)
            check('invalid or over-limit environment name fails closed',got.returncode==2 and got.stdout==b'' and got.stderr==b'invalid')
        payload=['','with spaces','a"b','end\\','two\\\\"quote','& | < > ^ %PATH% ! $() ` ;','雪',str(project)]
        targets=[('adjacent',harness,[])]
        unicode_harness=out/'process 雪 harness.exe' if os.name=='nt' else out/'process 雪 harness'
        shutil.copyfile(harness,unicode_harness)
        if os.name!='nt':unicode_harness.chmod(0o700)
        targets.append(('unicode executable',unicode_harness,[]))
        if args.beryl:targets.append(('compiler',args.beryl.resolve(),['mcp']))
        for label,binary,prefix in targets:
            # The external compiler fixture intentionally uses the trusted override.
            for use_override in ((False,True) if label!='compiler' else (True,)):
                chosen=child_env.copy()
                if use_override:chosen['BERYL_MCP_TOOL']=str(override)
                proc=subprocess.Popen([str(binary),*prefix,*payload],cwd=project,env=chosen,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
                session={'argv':[str(binary),*prefix,*payload],'cwd':str(project),'tool_override':str(override) if use_override else None,'messages':[]}
                report['sessions'].append(session)
                try:
                    ready=json.loads(line(proc));report.setdefault('protocol_ready',[]).append({'label':label,'override':use_override,'response':ready});check(label+' isolated Python',ready['isolated'])
                    check(label+' exact user argv',ready['argv'][3:]==payload)
                    check(label+' exact absolute compiler argument',ready['argv'][1]=='--beryl' and Path(ready['argv'][2]).resolve()==binary.resolve())
                    check(label+' trusted entrypoint',Path(ready['argv'][0]).resolve()==(override if use_override else installed).resolve())
                    for request in (b'{"id":1}\n',b'\x00binary\r\n',b'{"id":2,"text":"\xe9\x9b\xaa"}\n'):
                        proc.stdin.write(request);proc.stdin.flush();response=json.loads(line(proc))
                        session['messages'].append({'input_base64':base64.b64encode(request).decode(),'response':response})
                        check(label+' response before EOF preserves bytes',base64.b64decode(response['echo'])==request)
                    proc.stdin.close();proc.stdin=None;stdout,stderr=proc.communicate(timeout=8)
                    session.update(exit_code=proc.returncode,stdout_tail_base64=base64.b64encode(stdout).decode(),stderr_base64=base64.b64encode(stderr).decode())
                    check(label+' EOF exits transparently',proc.returncode==0 and stdout==b'' and stderr==b'child-stderr\n')
                finally:
                    if proc.poll() is None:proc.kill();proc.wait(timeout=8)
        check('no dispatcher job/capture directory in project',not (project/'.beryl-cache').exists())
        for name,extra,expected in (
            ('missing tool',{'BERYL_MCP_TOOL':str(out/'absent.py')},2),
            ('missing Python',{'BERYL_PYTHON':str(out/'missing-python.exe')},2),
            ('child exit',{'BERYL_MCP_TOOL':str(override)},7)):
            chosen=child_env.copy();chosen.update(extra)
            proc=subprocess.run([str(harness),*(['exit-seven'] if name=='child exit' else [])],cwd=project,env=chosen,input=b'',capture_output=True,timeout=8)
            record_case('process_cases',name,[harness,*(['exit-seven'] if name=='child exit' else [])],proc)
            check(name+' status',proc.returncode==expected)
            if name!='child exit':check(name+' stdout remains empty',proc.stdout==b'')
        for name,timeout,cancel,handle,args_tail,status in (
            ('missing stdin',0,0,'missing-input',[str(python),'-I',str(override)],'io_failure'),
            *(([('missing stdout',0,0,'missing-output',[str(python),'-I',str(override)],'io_failure'),
                ('missing stderr',0,0,'missing-error',[str(python),'-I',str(override)],'io_failure')]) if os.name=='nt' else []),
            ('startup',0,0,'valid',[str(out/'missing.exe')],'startup_failure'),
            ('timeout',1500,0,'valid',[str(python),'-I',str(tree)],'timeout'),
            ('cancel',0,1500,'valid',[str(python),'-I',str(tree)],'cancelled'),
            ('normal tree cleanup',0,0,'valid',[str(python),'-I',str(tree),'normal-exit'],'exited')):
            proc=subprocess.run([str(harness),'--process',str(timeout),str(cancel),handle,*args_tail],cwd=project,env=child_env,input=b'',capture_output=True,timeout=12)
            record_case('process_cases',name,[harness,'--process',str(timeout),str(cancel),handle,*args_tail],proc)
            record=json.loads(proc.stderr.decode().split('PROCESS_RESULT ',1)[1]);check(name+' exact process status',record['status']==status and proc.returncode==0)
            check(name+' no capture substitution',not record['captured'])
            if name in ('timeout','cancel','normal tree cleanup'):
                pid=json.loads(proc.stdout)['descendant'];check(name+' owned descendant stopped',tree_stopped(pid))
            else:check(name+' child did not execute',proc.stdout==b'')
        report['status']='passed'
    except BaseException as exc:
        report['status']='failed';report['failure']=repr(exc);raise
    finally:
        target=out/'results.json';target.write_text(json.dumps(report,indent=2));print(target,flush=True)

if __name__=='__main__':main()
