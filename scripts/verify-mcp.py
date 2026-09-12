#!/usr/bin/env python3
"""Independent stdio MCP protocol/CLI boundary regression; never runs an engine.

Real compiler context/doctor/analysis results are distinguished from trusted
fault-injection CLI fixtures. This is not a Claude or ChatGPT usability trial.
"""
import argparse
import copy
import ctypes
import hashlib
import json
import os
from pathlib import Path
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = "2025-11-25"
TOOLS = {"beryl_context", "beryl_doctor", "beryl_analyze", "beryl_test", "beryl_mod", "beryl_evidence"}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def encoded(value):
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def strict_json(raw):
    def pairs(items):
        obj = {}
        for key, value in items:
            if key in obj:
                raise ValueError("duplicate JSON response key")
            obj[key] = value
        return obj
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))


class Session:
    def __init__(self, work, server, compiler, project, env, *, timeout=8, workbench_tools=None, via_cli=False):
        self.folder = Path(tempfile.mkdtemp(prefix="session-", dir=work))
        self.infile = (self.folder / "stdin.jsonl").open("wb")
        self.outfile = (self.folder / "stdout.jsonl").open("wb")
        self.errfile = (self.folder / "stderr.bin").open("wb")
        self.next_id = 1
        self.closed = False
        self.messages = queue.Queue()
        self.argv = ([str(compiler),"mcp"] if via_cli else [sys.executable,str(server),"--beryl",str(compiler)])
        self.argv += ["--project",str(project),"--timeout-seconds",str(timeout)]
        if workbench_tools is not None:
            self.argv += ["--workbench-tools",str(workbench_tools)]
        self.proc = subprocess.Popen(self.argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE, cwd=project, env=env)

        def stdout():
            try:
                while True:
                    line = self.proc.stdout.readline(16 * 1024 * 1024)
                    if not line:
                        self.messages.put(("eof", None)); return
                    self.outfile.write(line); self.outfile.flush()
                    if not line.endswith(b"\n"):
                        raise AssertionError("oversized/non-newline server frame")
                    self.messages.put(("response", strict_json(line.decode("utf-8", "strict"))))
            except BaseException as exc:
                self.messages.put(("error", repr(exc)))

        def stderr():
            while True:
                data = self.proc.stderr.read(65536)
                if not data:
                    return
                self.errfile.write(data); self.errfile.flush()

        self.readers = [threading.Thread(target=stdout, daemon=True), threading.Thread(target=stderr, daemon=True)]
        for thread in self.readers:
            thread.start()

    def raw(self, data):
        if isinstance(data, str):
            data = data.encode("utf-8")
        self.infile.write(data); self.infile.flush()
        self.proc.stdin.write(data); self.proc.stdin.flush()

    def send(self, method, params=None, *, notification=False):
        request = {"jsonrpc": "2.0", "method": method}
        ident = None
        if not notification:
            ident = self.next_id; self.next_id += 1; request["id"] = ident
        if params is not None:
            request["params"] = params
        self.raw(encoded(request)+b"\n")
        return ident

    def receive(self, ident, *, timeout=20):
        kind, response = self.messages.get(timeout=timeout)
        assert kind == "response", (kind, response, self.folder)
        assert type(response) is dict and response.get("jsonrpc") == "2.0", response
        assert type(response.get("id")) is type(ident) and response.get("id") == ident, response
        assert ("result" in response) != ("error" in response), response
        return response

    def request(self, method, params=None):
        return self.receive(self.send(method, params))

    def initialize(self):
        result = self.request("initialize", {"protocolVersion": PROTOCOL, "capabilities": {},
                                              "clientInfo": {"name": "beryl-independent-verifier", "version": "1"}})
        assert result["result"]["protocolVersion"] == PROTOCOL, result
        assert type(result["result"].get("capabilities")) is dict
        self.send("notifications/initialized", notification=True)
        assert self.request("ping")["result"] == {}

    def call(self, name, arguments):
        return self.request("tools/call", {"name": name, "arguments": arguments})

    def close(self):
        if self.closed:
            return
        self.closed = True
        try:
            if not self.proc.stdin.closed:
                try:
                    self.proc.stdin.close()
                except BrokenPipeError:
                    pass
            self.proc.wait(timeout=12)
        except subprocess.TimeoutExpired:
            self.proc.kill(); self.proc.wait(timeout=10)
            raise AssertionError("MCP server failed to stop after EOF")
        finally:
            for thread in self.readers:
                thread.join(timeout=3)
            for stream in (self.infile, self.outfile, self.errfile):
                stream.close()
            (self.folder / "session.json").write_text(json.dumps({"argv": self.argv,
                "exit_code": self.proc.returncode, "stdout_sha256": sha(self.folder / "stdout.jsonl"),
                "stderr_sha256": sha(self.folder / "stderr.bin"),
                "stdin_sha256": sha(self.folder / "stdin.jsonl")}, indent=2)+"\n", encoding="utf-8")


def rpc_error(response, code):
    assert response.get("error", {}).get("code") == code, response


def tool_result(response):
    assert "error" not in response, response
    result = response["result"]
    assert type(result) is dict and type(result.get("isError")) is bool, result
    content = result.get("content")
    assert type(content) is list and len(content) == 1 and content[0].get("type") == "text", result
    envelope = strict_json(content[0]["text"])
    assert envelope == result.get("structuredContent"), "text/structuredContent differ"
    assert type(envelope) is dict and type(envelope.get("schema_version")) is int and envelope["schema_version"] == 1, envelope
    assert type(envelope.get("status")) is str, envelope
    assert result["isError"] == (envelope["status"] != "success"), envelope
    return envelope


def rejected(response):
    """Static schema errors and post-schema path admission have distinct layers."""
    if "error" in response:
        rpc_error(response,-32602)
    else:
        report=tool_result(response)
        assert report["status"]=="failure" and report["execution"]=="not_run" and report["result"] is None,report


FAKE_C = r'''
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#ifdef _WIN32
#include <windows.h>
#include <wchar.h>
#define pause_ms(n) Sleep(n)
#define my_pid() GetCurrentProcessId()
#else
#include <unistd.h>
#define pause_ms(n) usleep((n)*1000)
#define my_pid() getpid()
#endif
static char root[4096];
static void marker(const char *name) {
 char path[4300]; snprintf(path,sizeof path,"%s/%s",root,name);
 FILE *f=fopen(path,"w"); if(!f) exit(90); fprintf(f,"%lu\n",(unsigned long)my_pid()); fclose(f);
}
static void quote(FILE *file,const char *s) {
 fputc('"',file); for(;*s;s++){ unsigned char c=(unsigned char)*s;
 if(c=='"'||c=='\\'){fputc('\\',file);fputc(c,file);}else if(c<32) fprintf(file,"\\u%04x",c);else fputc(c,file); } fputc('"',file);
}
static unsigned response(void) {
 char path[4300];snprintf(path,sizeof path,"%s/response.json",root);FILE *f=fopen(path,"rb");if(!f)exit(96);
 unsigned n=0;int c;while((c=fgetc(f))!=EOF){fputc(c,stdout);n++;}fclose(f);return n;
}
int main(int argc,char **argv) {
 setvbuf(stdout,NULL,_IOFBF,65536);setvbuf(stderr,NULL,_IOFBF,65536);
 const char *home=getenv("BERYL_MCP_FIXTURE_HOME"); if(!home) return 91;
 snprintf(root,sizeof root,"%s",home);
 if(argc>1 && !strcmp(argv[1],"--child")){marker("child.pid");for(;;)pause_ms(20);}
 char path[4300],mode[64]={0}; snprintf(path,sizeof path,"%s/mode.txt",root);
 FILE *f=fopen(path,"r");if(!f)return 92;fgets(mode,sizeof mode,f);fclose(f);
 marker("started.pid");
 snprintf(path,sizeof path,"%s/argv.json",root);f=fopen(path,"w");if(!f)return 97;
 fputc('[',f);for(int n=1;n<argc;n++){if(n>1)fputc(',',f);quote(f,argv[n]);}fputs("]\n",f);fclose(f);
 if(!strcmp(mode,"hang")) {
#ifdef _WIN32
  wchar_t binary[4096],line[8192];
  if(!GetModuleFileNameW(NULL,binary,4096))return 94;
  swprintf(line,8192,L"\"%ls\" --child",binary);
  STARTUPINFOW start={0};PROCESS_INFORMATION child={0};start.cb=sizeof start;
  if(!CreateProcessW(NULL,line,NULL,NULL,TRUE,CREATE_NO_WINDOW,NULL,NULL,&start,&child)){marker("spawn-failed.pid");return 95;}
  CloseHandle(child.hThread);CloseHandle(child.hProcess);
#else
  if(!fork()){execl(argv[0],argv[0],"--child",NULL);_exit(93);}
#endif
  for(;;)pause_ms(20);
 }
 if(!strcmp(mode,"hold_success")) {
  snprintf(path,sizeof path,"%s/release.txt",root);
  for(;;){f=fopen(path,"r");if(f){fclose(f);break;}pause_ms(10);}
 }
 if(!strcmp(mode,"stdout_exact")||!strcmp(mode,"stdout_over_one")) {
  unsigned size=response(),maximum=4u*1024u*1024u+(!strcmp(mode,"stdout_over_one"));
  for(unsigned i=size;i<maximum;i++)fputc(' ',stdout);fflush(stdout);return 0;
 }
 if(!strcmp(mode,"stderr_exact")||!strcmp(mode,"stderr_over_one")) {
  unsigned maximum=4u*1024u*1024u+(!strcmp(mode,"stderr_over_one"));
  for(unsigned i=0;i<maximum;i++)fputc(' ',stderr);fflush(stderr);
  response();return 0;
 }
 if(!strcmp(mode,"stdout_limit")||!strcmp(mode,"stderr_limit")) {
  FILE *to=!strcmp(mode,"stderr_limit")?stderr:stdout;
  for(unsigned i=0;i<5u*1024u*1024u;i++)fputc('x',to);fflush(to);return 0;
 }
 if(!strcmp(mode,"invalid_json")){puts("{broken json");return 0;}
 if(!strcmp(mode,"duplicate_json")){puts("{\"status\":\"success\",\"status\":\"failure\"}");return 0;}
 if(!strcmp(mode,"bare_success")){puts("{\"schema_version\":1,\"status\":\"success\"}");return 0;}
 if(!strcmp(mode,"escaped_text")){for(unsigned i=0;i<4u*1024u*1024u;i++)fputc(1,stdout);return 0;}
 response();return !strcmp(mode,"nonzero")?7:0;
}
'''


def fake_response(folder,exe,operation="context.project",**changes):
    value={"schema_version":1,"status":"success","operation":operation,"compiler_fingerprint":sha(exe),
           "compiler_sha256":sha(exe),"execution":"not_run","fixture":True}
    value.update(changes)
    (folder/"response.json").write_bytes(encoded(value))


def wait_path(path, timeout=5):
    deadline = time.monotonic()+timeout
    while time.monotonic() < deadline:
        if path.is_file() and path.stat().st_size:
            return
        time.sleep(0.01)
    raise AssertionError(f"owned fixture did not start: {path}")


def alive(pid):
    if os.name == "nt":
        from ctypes import wintypes
        api = ctypes.WinDLL("kernel32", use_last_error=True)
        api.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        api.OpenProcess.restype = wintypes.HANDLE
        api.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        api.GetExitCodeProcess.restype = wintypes.BOOL
        api.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = api.OpenProcess(0x1000, False, pid)
        if not handle:
            return False
        try:
            code = wintypes.DWORD()
            assert api.GetExitCodeProcess(handle, ctypes.byref(code))
            return code.value == 259
        finally:
            api.CloseHandle(handle)
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--beryl", required=True, type=Path)
    parser.add_argument("--clang", required=True, type=Path)
    parser.add_argument("--server", type=Path, default=ROOT/"tools/beryl-mod/mcp_server.py")
    args = parser.parse_args()
    compiler, clang, server = (p.resolve(strict=True) for p in (args.beryl,args.clang,args.server))
    work = Path(tempfile.mkdtemp(prefix="mcp & spaces-", dir=ROOT/"build"))
    project = work/"project"; project.mkdir()
    source = project/"source.be"
    source.write_text('module mcp_fixture\npub fn value()->i32{return 7}\ntest "value" {assert(value()==7)}\n',encoding="utf-8")
    paths = [Path(__file__).resolve(),server,server.parent/"process_job.py",server.parent/"install.py",
             server.parent/"mod.py",compiler,source]
    before = {str(p):sha(p) for p in paths}
    evidence = {"schema_version":1,"status":"running","server_path":str(server),"input_hashes":before,"checks":[],"sessions":[],
                "commands":[],"unavailable":[],"engine_execution":"not_run","assistant_usability_trials":"not_run",
                "verification_scope":"full_protocol_cli_and_fault_fixture_gate","expected_check_groups":17,
                "real_compiler_checks":[],"synthetic_fault_injection_checks":[]}
    env = os.environ.copy()
    env["PATH"] = str(clang.parent)+os.pathsep+env.get("PATH","")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    for key in ("BERYL_CLANG","BERYL_PYTHON","BERYL_MOD_TOOL"):
        env.pop(key,None)
    sessions = []
    print(f"MCP artifacts: {work}",flush=True)

    def session(exe=compiler, *, timeout=8, environment=env, workbench_tools=None, via_cli=False):
        instance = Session(work,server,exe,project,environment,timeout=timeout,workbench_tools=workbench_tools,via_cli=via_cli)
        sessions.append(instance); evidence["sessions"].append(str(instance.folder.relative_to(work)))
        return instance

    def passed(name, category=None):
        evidence["checks"].append(name)
        if category:
            evidence[category].append(name)
        print("passed "+name,flush=True)

    def command(argv):
        p = subprocess.run(list(map(str,argv)),cwd=project,env=env,capture_output=True,timeout=45)
        record={"argv":list(map(str,argv)),"exit_code":p.returncode,
                "stdout":p.stdout.decode("utf-8","strict"),"stderr":p.stderr.decode("utf-8","strict")}
        evidence["commands"].append(record)
        return p,record

    try:
        run_checks(session, passed, command, evidence, work, project, source, compiler, clang, env)
        for instance in sessions:
            instance.close()
        sessions.clear()
        assert before == {str(p):sha(p) for p in paths}, "source/compiler/server changed during verification"
        assert len(evidence["checks"])==evidence["expected_check_groups"], "empty or partial verification corpus"
        assert len(evidence["real_compiler_checks"])==5, "incomplete actual compiler parity/execution corpus"
        evidence["status"]="success"
    except BaseException as exc:
        evidence["status"]="failure"; evidence["error"]=repr(exc)
        raise
    finally:
        for instance in sessions:
            try:
                instance.close()
            except BaseException as exc:
                evidence.setdefault("cleanup_errors",[]).append(repr(exc))
        (work/"results.json").write_text(json.dumps(evidence,indent=2,ensure_ascii=True)+"\n",encoding="utf-8")
    print(f"passed {len(evidence['checks'])} MCP checks; no engine execution or assistant-trial claim",flush=True)


def run_checks(session, passed, command, evidence, work, project, source, compiler, clang, env):
    s = session()
    rpc_error(s.request("tools/list"), -32002)
    s.initialize()
    listed = s.request("tools/list")["result"]["tools"]
    assert {tool["name"] for tool in listed} == TOOLS and len(listed) == len(TOOLS), listed
    for tool in listed:
        schema = tool["inputSchema"]
        assert schema["type"] == "object" and schema["additionalProperties"] is False, tool
    (work/"tools-list.json").write_text(json.dumps(listed,indent=2)+"\n",encoding="utf-8")
    rpc_error(s.request("not/a/method"), -32601)
    rpc_error(s.request("tools/call", {"name":"beryl_missing","arguments":{}}), -32602)
    rpc_error(s.request("tools/call", {"name":"beryl_context","arguments":{},"argv":["--unsafe"]}), -32602)
    rpc_error(s.request("tools/call", {"name":"beryl_context"}), -32602)
    assert s.request("ping",{"_meta":{"fixture":"standard metadata"}})["result"]=={}
    rpc_error(s.request("tools/list",{"_meta":True}),-32602)
    s.raw(b'{"jsonrpc":"2.0","id":12000,"method":true}\n');rpc_error(s.receive(None),-32600)
    passed("initialization, ping, exact typed tool discovery and unknown method/tool rejection")

    malformed = [b'{\n', b'{"jsonrpc":"2.0","jsonrpc":"2.0","id":10000,"method":"ping"}\n',
                 b'{"jsonrpc":"2.0","id":10001,"method":"ping","\\u006dethod":"ping"}\n',
                 b'{"jsonrpc":"2.0","id":10002,"method":"ping","params":{"value":NaN}}\n',
                 b'{"jsonrpc":"2.0","id":10003,"method":"\xff"}\n']
    for raw in malformed:
        s.raw(raw); rpc_error(s.receive(None), -32700)
    assert s.request("ping")["result"] == {}
    passed("malformed UTF-8/JSON, literal and escaped duplicate keys, nonfinite JSON rejected")

    # Typed parameter negatives must reject before invoking any compiler.
    fake = work/"trusted-fixture"; fake.mkdir()
    code = fake/"fake.c"; code.write_text(FAKE_C,encoding="utf-8")
    exe = fake/("fake.exe" if os.name=="nt" else "fake")
    p, _ = command([clang,"-std=c11","-O0",code,"-o",exe])
    assert p.returncode == 0, "trusted fault-injection CLI failed to compile"
    evidence["synthetic_fixture"]={"source_sha256":sha(code),"executable_sha256":sha(exe),"compiler_sha256":sha(clang)}
    fake_response(fake,exe)
    (fake/"mode.txt").write_text("echo",encoding="ascii")
    fakeenv=env.copy(); fakeenv["BERYL_MCP_FIXTURE_HOME"]=str(fake)
    f = session(exe,environment=fakeenv); f.initialize()
    bad_calls = [
        ("beryl_context",{}),
        ("beryl_context",{"topic":"native","sources":[]}),
        ("beryl_context",{"topic":"project","shell":"forbidden"}),
        ("beryl_context",{"topic":"project","sources":"source.be"}),
        ("beryl_context",{"topic":"symbol","sources":["source.be"]}),
        ("beryl_context",{"topic":"symbol","name":"mcp_fixture.value","sources":[]}),
        ("beryl_context",{"topic":"project","sources":[True]}),
        ("beryl_doctor",{"probe":True}),
        ("beryl_doctor",{"probe":"engine"}),
        ("beryl_doctor",{"argv":["--clang","arbitrary"]}),
        ("beryl_test",{"sources":[],"backend":"reference"}),
        ("beryl_test",{"sources":["source.be"],"backend":"rust"}),
        ("beryl_test",{"sources":["source.be"],"backend":"reference","release":True}),
        ("beryl_mod",{"operation":"promote","artifact":"x"}),
        ("beryl_mod",{"operation":"verify","stage":"runtime"}),
        ("beryl_mod",{"operation":"check","shell":"forbidden"}),
        ("beryl_evidence",{"path":"source.be"}),
        ("beryl_evidence",{"path":True}),
    ]
    for name, arguments in bad_calls:
        rejected(f.call(name,arguments))
        assert not (fake/"started.pid").exists(), "invalid tool arguments executed a compiler"
    for bad in ["../outside.be","/absolute.be","C:/absolute.be","dir/../source.be","./source.be",
                "dir//source.be","source.be:stream","dir\\source.be","source.txt","source.be\0"]:
        rejected(f.call("beryl_context",{"topic":"project","sources":[bad]}))
        assert not (fake/"started.pid").exists(), "invalid source path executed a compiler"
    passed("unknown keys/types/tool modes and traversal paths reject before execution","synthetic_fault_injection_checks")

    outside=work/"outside.be"; outside.write_text("module external\n",encoding="utf-8")
    hard=project/"hard.be"; os.link(outside,hard)
    rejected(f.call("beryl_context",{"topic":"project","sources":["hard.be"]}))
    assert not (fake/"started.pid").exists()
    try:
        (project/"symbolic.be").symlink_to(outside)
    except OSError as exc:
        evidence["unavailable"].append({"check":"source symbolic link rejection","reason":str(exc)})
    else:
        rejected(f.call("beryl_context",{"topic":"project","sources":["symbolic.be"]}))
        assert not (fake/"started.pid").exists()
    passed("hard-linked source rejected; symbolic-link capability separately recorded","synthetic_fault_injection_checks")

    run_tool_checks(s,f,session,passed,command,evidence,work,project,source,compiler,fake,exe,fakeenv)


def run_tool_checks(s,f,session,passed,command,evidence,work,project,source,compiler,fake,exe,fakeenv):
    def payload(response, expected="success"):
        report=tool_result(response)
        assert report["status"]==expected,report
        if report.get("receipt") and Path(report["receipt"]).exists():
            assert strict_json(Path(report["receipt"]).read_bytes())==report,"retained and returned receipt differ"
        return report

    contexts=[({"topic":"project","sources":["source.be"]},["context","project",str(source)]),
              ({"topic":"symbol","name":"mcp_fixture.value","sources":["source.be"]},
               ["context","symbol","mcp_fixture.value",str(source)]),
              ({"topic":"capabilities"},["context","capabilities"]),
              ({"topic":"examples"},["context","examples"]),
              ({"topic":"binding","name":"Math.ClampInt"},["context","binding","Math.ClampInt"]),
              ({"topic":"optimization"},["context","optimization","--list"])]
    for arguments,argv in contexts:
        direct,_=command([compiler,*argv]); assert direct.returncode==0
        report=payload(s.call("beryl_context",arguments))
        assert report["result"]==strict_json(direct.stdout),"context response differs from actual CLI"
        assert report["result"]["execution"]=="not_run"
        assert report["compiler_sha256"]==sha(compiler)
    unknown=payload(s.call("beryl_context",{"topic":"symbol","name":"mcp_fixture.absent","sources":["source.be"]}),"failure")
    assert unknown["result"]["status"]!="success"
    passed("six actual compiler context topics preserve exact direct CLI responses and unknown-symbol failure","real_compiler_checks")

    direct,_=command([compiler,"doctor","--format","json"]); assert direct.returncode==0
    doctor=payload(s.call("beryl_doctor",{}))
    assert doctor["result"]==strict_json(direct.stdout),"doctor inventory differs from actual CLI"
    assert doctor["result"]["engine_execution"]=="not_run" and doctor["result"]["probe"] is None
    omitted=payload(s.request("tools/call",{"name":"beryl_doctor","_meta":{"fixture":"omitted zero-argument object"}}))
    assert omitted["result"]==doctor["result"]
    readiness=payload(s.call("beryl_doctor",{"probe":"native"}))
    assert readiness["result"]["status"]=="success" and readiness["result"]["engine_execution"]=="not_run"
    passed("actual doctor inventory parity and explicit fixed native readiness probe","real_compiler_checks")

    text='module mcp_fixture\n// supplied λ snapshot\npub fn value()->i32{return 42}\n'
    request={"schema_version":1,"request_id":"mcp.snapshot","snapshot_version":17,"target":"native",
             "forbid_unsafe":True,"expected_compiler_sha256":sha(compiler),"sources":[
                 {"path":"source.be","sha256":hashlib.sha256(text.encode()).hexdigest(),
                  "document_version":23,"content_file":"overlay.be"}]}
    exact=work/"analysis-expected";exact.mkdir()
    (exact/"overlay.be").write_bytes(text.encode("utf-8"))
    (exact/"request.json").write_bytes(encoded(request))
    direct,_=command([compiler,"analyze","--request",exact/"request.json"])
    assert direct.returncode==0,"selected compiler must include the authorized C analysis command"
    analyzed=payload(s.call("beryl_analyze",{"request":request,"contents":{"overlay.be":text}}))
    assert analyzed["result"]==strict_json(direct.stdout),"MCP analysis did not preserve exact supplied snapshot"
    assert analyzed["result"]["sources"][0]["sha256"]==request["sources"][0]["sha256"]!=sha(source)
    assert analyzed["result"]["execution"]=="not_run" and analyzed["result"]["engine_verification"]=="not_run"
    for changes in ({"schema_version":True},{"unknown":"forbidden"},{"snapshot_version":1.0}):
        bad=copy.deepcopy(request);bad.update(changes)
        report=payload(s.call("beryl_analyze",{"request":bad,"contents":{"overlay.be":text}}),"failure")
        assert report["result"] is None or report["result"]["status"]=="failure"
    for contents in ({},{"overlay.be":text,"extra.be":"module extra\n"}):
        rejected(s.call("beryl_analyze",{"request":request,"contents":contents}))
    stale=copy.deepcopy(request);stale["sources"][0]["sha256"]="0"*64
    report=payload(s.call("beryl_analyze",{"request":stale,"contents":{"overlay.be":text}}),"stale_input")
    assert report["result"]["status"]=="stale_input"
    passed("actual C analysis retains unsaved UTF-8/version/hash identity; schema, completeness and stale hash failures survive adapter","real_compiler_checks")

    tested=payload(s.call("beryl_test",{"sources":["source.be"],"backend":"reference"}))
    assert "1 test, 1 assertion" in tested["result"]["stdout"],tested
    passed("explicit reference test executes the selected real Beryl fixture","real_compiler_checks")

    claimed={"schema_version":1,"status":"success","engine_claim":"unverified fixture text"}
    receipt=project/"claimed.json";receipt.write_bytes(encoded(claimed))
    report=payload(s.call("beryl_evidence",{"path":"claimed.json"}))
    assert report["result"]==claimed and report["evidence_sha256"]==sha(receipt)
    assert report["applicability"]=="not_checked" and report["execution"]=="not_run"
    for filename,raw in (("malformed.json",b'{bad}'),("duplicate.json",b'{"status":"success","status":"failure"}'),
                         ("deep.json",b'['*3000+b'0'+b']'*3000)):
        (project/filename).write_bytes(raw)
        rejected(s.call("beryl_evidence",{"path":filename}))
    recovered=payload(s.call("beryl_evidence",{"path":"claimed.json"}))
    assert recovered["result"]==claimed
    passed("evidence reader preserves exact bytes/hash without validating externally asserted claims")

    installed=work/"installed";installed.mkdir()
    installed_compiler=installed/compiler.name;shutil.copyfile(compiler,installed_compiler)
    assert sha(installed_compiler)==sha(compiler)
    installer=Path(evidence["server_path"]).parent/"install.py"
    completed,install_record=command([sys.executable,installer,"--compiler",installed_compiler])
    assert completed.returncode==0,install_record
    installation=strict_json(completed.stdout)
    assert installation["status"]=="success"
    installed_env=fakeenv.copy();installed_env.pop("BERYL_MCP_FIXTURE_HOME",None)
    installed_env.pop("BERYL_MCP_TOOL",None);installed_env["BERYL_PYTHON"]=sys.executable
    deployed=session(installed_compiler,environment=installed_env,via_cli=True);deployed.initialize()
    deployed_context=payload(deployed.call("beryl_context",{"topic":"project","sources":["source.be"]}))
    assert deployed_context["result"]["compiler_fingerprint"]==sha(compiler)
    assert deployed_context["result"]["execution"]=="not_run"
    deployed_analysis=payload(deployed.call("beryl_analyze",{"request":request,"contents":{"overlay.be":text}}))
    assert deployed_analysis["result"]==analyzed["result"],"installed C/loader path changed the supplied analysis snapshot"
    bundle=installed/"beryl-tools"/installation["bundle"]
    manifest=strict_json((bundle/"bundle.json").read_bytes())
    assert set(p.name for p in bundle.iterdir())==set(manifest)|{"bundle.json"}
    assert all(sha(bundle/name)==expected for name,expected in manifest.items())
    assert not list((installed/"beryl-tools").rglob("__pycache__")),"installed loader wrote bytecode into its immutable bundle"
    evidence["installed_bridge"]={"compiler_sha256":sha(installed_compiler),"bundle":installation["bundle"],
        "loader_sha256":sha(installed/"beryl-tools/mcp.py"),"manifest_sha256":sha(bundle/"bundle.json"),
        "session":str(deployed.folder.relative_to(work)),"launch":"beryl mcp through inherited stdio"}
    passed("installed compiler dispatch and hash-verified loader carry real context/analysis through C inherited pipes","real_compiler_checks")

    # Only a trusted fake executable receives these argv mapping tests. No mod
    # operation or scenario reaches the real Beryl/Workbench bridge here.
    absent=payload(f.call("beryl_mod",{"operation":"verify","artifact":"a"*32,"stage":"compile"}),"unavailable")
    assert absent["execution"]=="not_run" and absent["result"] is None
    integration=fake/"integration";integration.mkdir()
    configured=session(exe,environment=fakeenv,workbench_tools=integration);configured.initialize()
    mappings=[("beryl_test",{"sources":["source.be"],"backend":"native"},["test","--backend","native",str(source)]),
              ("beryl_test",{"sources":["source.be"],"backend":"differential"},["test","--backend","differential",str(source)]),
              ("beryl_mod",{"operation":"check"},["mod","check","--project",str(project)]),
              ("beryl_mod",{"operation":"build"},["mod","build","--project",str(project)]),
              ("beryl_mod",{"operation":"scenarios"},["mod","scenarios","--project",str(project)]),
              ("beryl_mod",{"operation":"verify","artifact":"a"*32,"stage":"compile"},
               ["mod","verify","--project",str(project),"--workbench-tools",str(integration),"--artifact","a"*32,"--stage","compile"]),
              ("beryl_mod",{"operation":"verify","artifact":"a"*32,"scenario":"fixture.only"},
               ["mod","verify","--project",str(project),"--workbench-tools",str(integration),"--artifact","a"*32,"--scenario","fixture.only"])]
    for name,arguments,argv in mappings:
        fake_response(fake,exe,"mod "+arguments["operation"] if name=="beryl_mod" else "test")
        report=payload(configured.call(name,arguments))
        fake_result=strict_json(report["result"]["stdout"]) if name=="beryl_test" else report["result"]
        assert fake_result["fixture"] is True and strict_json((fake/"argv.json").read_bytes())==argv,(argv,report)
    passed("typed execution tools map to exact argv using fake CLI only; no engine operation executed","synthetic_fault_injection_checks")

    fake_response(fake,exe)
    for mode,expected in (("invalid_json","invalid_response"),("duplicate_json","invalid_response"),
                          ("bare_success","invalid_response"),("nonzero","failure"),("stdout_exact","success"),("stdout_over_one","output_limit"),
                          ("stderr_exact","success"),("stderr_over_one","output_limit"),
                          ("stdout_limit","output_limit"),("stderr_limit","output_limit")):
        (fake/"mode.txt").write_text(mode,encoding="ascii")
        report=payload(f.call("beryl_context",{"topic":"project"}),expected)
        if expected not in ("failure","success"):assert report["result"] is None,report
        for log in report["raw_logs"]:
            assert Path(log).stat().st_size<=4*1024*1024,"raw log exceeded declared output bound"
    passed("invalid/duplicate CLI JSON, nonzero exit and each output-stream limit fail closed","synthetic_fault_injection_checks")

    (fake/"mode.txt").write_text("echo",encoding="ascii")
    for bad in ({"compiler_fingerprint":"0"*64},{"operation":"context.symbol"},{"schema_version":True},{"execution":"program_ran"}):
        fake_response(fake,exe,**bad)
        failed=payload(f.call("beryl_context",{"topic":"project"}),"invalid_response")
        assert failed["result"] is None
    fake_request=copy.deepcopy(request);fake_request["expected_compiler_sha256"]=sha(exe)
    descriptors=[{"path":item["path"],"sha256":item["sha256"],"document_version":item["document_version"],"file_id":index}
                 for index,item in enumerate(fake_request["sources"])]
    identity={"request_id":fake_request["request_id"],"snapshot_version":fake_request["snapshot_version"],
              "sources":descriptors,"request_fingerprint":hashlib.sha256(encoded(fake_request)).hexdigest(),
              "source_fingerprint":"1"*64,"snapshot_fingerprint":"2"*64,"admission":{"target":"native"}}
    for change in ({"snapshot_version":18},{"request_id":"another.request"},{"request_fingerprint":"0"*64},{"sources":[]}):
        fake_response(fake,exe,"analyze",**{**identity,**change})
        failed=payload(f.call("beryl_analyze",{"request":fake_request,"contents":{"overlay.be":text}}),"invalid_response")
        assert failed["result"] is None
    one_request=copy.deepcopy(fake_request);one_request["snapshot_version"]=1
    one_request["sources"][0]["document_version"]=1
    one_identity=copy.deepcopy(identity);one_identity["snapshot_version"]=1
    one_identity["sources"][0]["document_version"]=1
    one_identity["request_fingerprint"]=hashlib.sha256(encoded(one_request)).hexdigest()
    for field in ("snapshot_version","document_version","file_id"):
        bad=copy.deepcopy(one_identity)
        if field=="snapshot_version":bad[field]=True
        else:bad["sources"][0][field]=(field=="document_version")
        fake_response(fake,exe,"analyze",**bad)
        failed=payload(f.call("beryl_analyze",{"request":one_request,"contents":{"overlay.be":text}}),"invalid_response")
        assert failed["result"] is None
    (fake/"mode.txt").write_text("escaped_text",encoding="ascii")
    expanded=payload(f.call("beryl_test",{"sources":["source.be"],"backend":"reference"}),"output_limit")
    assert expanded["result"] is None and Path(expanded["raw_logs"][0]).stat().st_size==4*1024*1024
    passed("success envelopes require operation/compiler/snapshot identity; escaped outgoing expansion remains bounded","synthetic_fault_injection_checks")

    fake_response(fake,exe)
    (fake/"mode.txt").write_text("hold_success",encoding="ascii")
    if (fake/"started.pid").exists():(fake/"started.pid").unlink()
    mutable=project/"changing.be";mutable.write_text("module changing\n",encoding="utf-8")
    ident=f.send("tools/call",{"name":"beryl_context","arguments":{"topic":"project","sources":["changing.be"]}})
    wait_path(fake/"started.pid")
    mutable.write_text("module changed\n",encoding="utf-8")
    (fake/"release.txt").write_text("release",encoding="ascii")
    stale=payload(f.receive(ident),"stale_input");assert stale["result"] is None
    passed("changed project source invalidates a completed CLI response before publication","synthetic_fault_injection_checks")

    run_cancellation_checks(session,passed,evidence,project,fake,exe,fakeenv,payload)
    run_protocol_limits(session,passed)


def run_cancellation_checks(session,passed,evidence,project,fake,exe,fakeenv,payload):
    fake_response(fake,exe)
    (fake/"mode.txt").write_text("hang",encoding="ascii")
    for name in ("started.pid","child.pid"):
        path=fake/name
        if path.exists():path.unlink()
    # The unrelated process is another explicitly owned verifier fixture. The
    # adapter must not stop it while cancelling its own active process tree.
    unrelated=subprocess.Popen([sys.executable,"-c","import time; time.sleep(60)"],cwd=project,
                               stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        s=session(exe,environment=fakeenv);s.next_id=100;s.initialize();s.next_id=1
        ident=s.send("tools/call",{"name":"beryl_context","arguments":{"topic":"project"}})
        wait_path(fake/"started.pid");wait_path(fake/"child.pid")
        owner_pid=int((fake/"started.pid").read_text());child_pid=int((fake/"child.pid").read_text())
        busy=s.send("tools/call",{"name":"beryl_context","arguments":{"topic":"project"}})
        rpc_error(s.receive(busy),-32001)
        s.send("notifications/cancelled",{"requestId":True},notification=True)
        assert s.request("ping")["result"]=={} and alive(owner_pid),"boolean cancelled integer request ID"
        s.send("notifications/cancelled",{"requestId":ident,"reason":True},notification=True)
        assert s.request("ping")["result"]=={} and alive(owner_pid),"invalid reason cancelled active request"
        s.send("notifications/cancelled",{"requestId":str(ident)},notification=True)
        assert s.request("ping")["result"]=={} and alive(owner_pid),"wrong ID type cancelled the active request"
        s.send("notifications/cancelled",{"requestId":ident,"reason":"owned verifier cancellation"},notification=True)
        report=payload(s.receive(ident),"cancelled")
        assert report["result"] is None and unrelated.poll() is None
        deadline=time.monotonic()+5
        while time.monotonic()<deadline and (alive(owner_pid) or alive(child_pid)):time.sleep(0.01)
        assert not alive(owner_pid) and not alive(child_pid),"cancelled owned process tree survived"
        (fake/"mode.txt").write_text("echo",encoding="ascii")
        payload(s.call("beryl_context",{"topic":"project"}))
        assert unrelated.poll() is None
        evidence["cancelled_processes"]={"parent_pid":owner_pid,"child_pid":child_pid,"unrelated_pid":unrelated.pid,
                                         "owned_exited":True,"unrelated_survived":True}
        passed("busy serialization, typed cancellation, owned child cleanup and subsequent recovery","synthetic_fault_injection_checks")
    finally:
        unrelated.terminate();unrelated.wait(timeout=10)

    (fake/"mode.txt").write_text("hang",encoding="ascii")
    short=session(exe,timeout=0.2,environment=fakeenv);short.initialize()
    timed=payload(short.call("beryl_context",{"topic":"project"}),"timeout")
    assert timed["result"] is None
    passed("host-selected timeout produces explicit incomplete result without stale success","synthetic_fault_injection_checks")


def run_protocol_limits(session,passed):
    deep=session();deep.initialize()
    deep.raw(b'['*66+b'0'+b']'*66+b'\n');rpc_error(deep.receive(None),-32700)
    assert deep.request("ping")["result"]=={}
    huge=session();huge.initialize()
    try:
        huge.raw(b'"'+b'x'*(12*1024*1024)+b'"\n')
    except BrokenPipeError:
        pass  # Server closes after its bounded frame prefix.
    rpc_error(huge.receive(None),-32700)
    huge.proc.wait(timeout=10)
    assert huge.proc.returncode==0
    quota=session();quota.initialize()
    # initialize and its ping already consumed two distinct request IDs.
    for _ in range(4096-2):
        assert quota.request("ping")["result"]=={}
    rpc_error(quota.request("ping"),-32600)
    passed("bounded JSON depth, frame size and 4096 request-ID quota are enforced")


if __name__ == "__main__":
    main()
