#!/usr/bin/env python3
"""Verify Python job ownership using owned fixtures; no engine or installation.

Windows gates: suspended launch, immediate descendant, kill-on-close after hard
host death, deliberate removal mutants and the existing mod.Job.run caller.
"""
from __future__ import annotations
import argparse
import ctypes
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]


def module(path):
    spec = importlib.util.spec_from_file_location("owned_job_fixture", path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def wait_file(path, timeout=10):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if path.is_file() and path.stat().st_size:
            return path.read_text(encoding="ascii")
        time.sleep(0.005)
    raise AssertionError("owned fixture did not produce " + str(path))


def host(helper, executable, case):
    with module(helper).ProcessJob() as owner:
        child = subprocess.Popen([str(executable), "--spawn", str(case)], creationflags=owner.flags,
                                 stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        owner.attach(child)
        wait_file(case / "leaf.pid")
        (case / "host.ready").write_text(str(os.getpid()), encoding="ascii")
        while True:
            time.sleep(0.1)


FIXTURE = r'''
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <windows.h>
static void marker(const char *root,const char *name) {
 char path[4096];if(snprintf(path,sizeof path,"%s/%s",root,name)>=(int)sizeof path)ExitProcess(80);
 FILE *f=fopen(path,"wb");if(!f)ExitProcess(81);fprintf(f,"%lu",(unsigned long)GetCurrentProcessId());fclose(f);
}
int main(int argc,char **argv){
 if(argc>1&&!strcmp(argv[1],"--success")){puts("BERYL_PROCESS_JOB_OK");return 0;}
 const char *mode=argc>1?argv[1]:"",*root=argc>2?argv[2]:NULL;
 if(!strcmp(mode,"context")){mode="--spawn";root=getenv("BERYL_PROCESS_FIXTURE_DIR");}
 if(!root)return 82;
 if(!strcmp(mode,"--leaf")){marker(root,"leaf.pid");for(;;)Sleep(10);}
 if(!strcmp(mode,"--marker")){marker(root,"marker.pid");for(;;)Sleep(10);}
 if(strcmp(mode,"--spawn"))return 83;
 marker(root,"parent.pid");
 char line[8192];if(snprintf(line,sizeof line,"\"%s\" --leaf \"%s\"",argv[0],root)>=(int)sizeof line)return 84;
 STARTUPINFOA startup={0};PROCESS_INFORMATION child={0};startup.cb=sizeof startup;
 if(!CreateProcessA(argv[0],line,NULL,NULL,FALSE,CREATE_NO_WINDOW,NULL,NULL,&startup,&child))return 85;
 CloseHandle(child.hThread);CloseHandle(child.hProcess);for(;;)Sleep(10);
}
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clang", type=Path)
    parser.add_argument("--helper", type=Path, default=ROOT / "tools/beryl-mod/process_job.py")
    parser.add_argument("--host", action="store_true")
    parser.add_argument("--executable", type=Path)
    parser.add_argument("--case", type=Path)
    parser.add_argument("--work-root", type=Path, default=ROOT / "build")
    args = parser.parse_args()
    if args.host:
        host(args.helper, args.executable, args.case)
        return 0
    if os.name != "nt":
        print(json.dumps({"status": "unavailable", "capability": "windows_job_ownership"}))
        return 3
    if not args.clang:
        parser.error("--clang is required for the fixed C fixture")
    args.work_root.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="process-job & spaces-", dir=args.work_root.resolve()))
    helper = work / "process_job.py"
    data = args.helper.resolve(strict=True).read_bytes()
    helper.write_bytes(data)
    fixture = work / "fixture.c"; fixture.write_text(FIXTURE, encoding="ascii")
    exe = work / "fixture.exe"
    evidence = {"schema_version": 1, "operation": "verify-process-job", "status": "running",
                "helper_sha256": hashlib.sha256(data).hexdigest(), "checks": [],
                "engine_execution": "not_run", "installation": "not_run"}
    api = ctypes.WinDLL("kernel32", use_last_error=True)
    api.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
    api.OpenProcess.restype = ctypes.c_void_p
    api.CloseHandle.argtypes = [ctypes.c_void_p]
    api.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    api.WaitForSingleObject.restype = ctypes.c_uint32
    api.TerminateProcess.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    api.QueryFullProcessImageNameW.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_uint32)]

    def opened(pid):
        handle = api.OpenProcess(0x100000 | 0x1000 | 0x0001, False, pid)
        if not handle:
            raise ctypes.WinError(ctypes.get_last_error())
        image = ctypes.create_unicode_buffer(32768); length = ctypes.c_uint32(len(image))
        if not api.QueryFullProcessImageNameW(handle, 0, image, ctypes.byref(length)) or Path(image.value).resolve() != exe.resolve():
            api.CloseHandle(handle)
            raise AssertionError("refusing to operate on a process outside the owned fixture")
        return handle

    def dispose(handles):
        for handle in handles:
            if api.WaitForSingleObject(handle, 0) == 258:
                if not api.TerminateProcess(handle, 90):
                    raise ctypes.WinError(ctypes.get_last_error())
                assert api.WaitForSingleObject(handle, 5000) == 0
            api.CloseHandle(handle)

    def suspended(selected, expected):
        case = work / ("suspended-positive" if expected else "suspended-mutant"); case.mkdir()
        with module(selected).ProcessJob() as owner:
            child = subprocess.Popen([str(exe), "--marker", str(case)], creationflags=owner.flags,
                                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                time.sleep(0.15)
                observed = not (case / "marker.pid").exists() and child.poll() is None
                assert observed == expected, ("suspension gate", selected, observed)
                if expected:
                    owner.attach(child)
                    assert int(wait_file(case / "marker.pid")) == child.pid
                    owner.stop(child)
            finally:
                if child.poll() is None:
                    child.kill(); child.wait(timeout=5)
        evidence["checks"].append({"case": case.name, "status": "success", "pre_attach_user_code_absent": observed})

    def descendants():
        case = work / "immediate-descendant"; case.mkdir(); handles = []
        try:
            with module(helper).ProcessJob() as owner:
                child = subprocess.Popen([str(exe), "--spawn", str(case)], creationflags=owner.flags,
                                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                owner.attach(child)
                parent_id, leaf_id = int(wait_file(case / "parent.pid")), int(wait_file(case / "leaf.pid"))
                assert parent_id == child.pid
                handles = [opened(parent_id), opened(leaf_id)]
                owner.stop(child)
                assert all(api.WaitForSingleObject(handle, 5000) == 0 for handle in handles)
        finally:
            dispose(handles)
        evidence["checks"].append({"case": case.name, "status": "success", "parent_pid": parent_id, "leaf_pid": leaf_id})

    def hard_kill(selected, expected):
        case = work / ("hard-kill-positive" if expected else "hard-kill-mutant"); case.mkdir(); handles = []
        with (case / "host.stdout").open("wb") as out, (case / "host.stderr").open("wb") as err:
            parent = subprocess.Popen([sys.executable, "-I", "-B", str(Path(__file__).resolve()), "--host", "--helper", str(selected),
                                       "--executable", str(exe), "--case", str(case)], stdout=out, stderr=err,
                                      creationflags=subprocess.CREATE_NO_WINDOW)
            try:
                assert int(wait_file(case / "host.ready")) == parent.pid
                handles = [opened(int(wait_file(case / name))) for name in ("parent.pid", "leaf.pid")]
                parent.kill(); parent.wait(timeout=5)
                observed = all(api.WaitForSingleObject(handle, 2000) == 0 for handle in handles)
                assert observed == expected, ("kill-on-close gate", selected, observed)
            finally:
                if parent.poll() is None:
                    parent.kill(); parent.wait(timeout=5)
                dispose(handles)
        assert not (case / "host.stderr").read_bytes()
        evidence["checks"].append({"case": case.name, "status": "success", "descendants_stopped_on_host_death": observed})

    try:
        argv = [str(args.clang.resolve(strict=True)), "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror", str(fixture), "-o", str(exe)]
        build = subprocess.run(argv, capture_output=True, timeout=60)
        (work / "compile.stdout").write_bytes(build.stdout); (work / "compile.stderr").write_bytes(build.stderr)
        assert build.returncode == 0, build.stderr.decode(errors="replace")
        evidence["compile_argv"] = argv; evidence["fixture_sha256"] = hashlib.sha256(exe.read_bytes()).hexdigest()
        suspended(helper, True)
        descendants()
        hard_kill(helper, True)
        unsuspended = work / "without-suspension.py"
        needle = b"subprocess.CREATE_NO_WINDOW | 0x00000004"
        assert data.count(needle) == 1
        unsuspended.write_bytes(data.replace(needle, b"subprocess.CREATE_NO_WINDOW"))
        suspended(unsuspended, False)
        unbounded = work / "without-kill-on-close.py"
        needle = b"limits.BasicLimitInformation.LimitFlags = 0x00002000"
        assert data.count(needle) == 1
        unbounded.write_bytes(data.replace(needle, b"limits.BasicLimitInformation.LimitFlags = 0"))
        hard_kill(unbounded, False)

        # Repeat hard-death containment through the real stdio MCP worker,
        # selecting only a trusted fixture compiler; no engine tool is invoked.
        case = work / "mcp-hard-kill"; case.mkdir(); handles = []
        server = case / "mcp_server.py"
        server_data = (ROOT / "tools/beryl-mod/mcp_server.py").read_bytes()
        server.write_bytes(server_data); (case / "process_job.py").write_bytes(data)
        environment = os.environ.copy(); environment["BERYL_PROCESS_FIXTURE_DIR"] = str(case)
        frames = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "ownership-fixture", "version": "1"}}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "beryl_context", "arguments": {"topic": "project"}}},
        ]
        raw = b"".join(json.dumps(frame, separators=(",", ":")).encode() + b"\n" for frame in frames)
        (case / "stdin.jsonl").write_bytes(raw)
        with (case / "stdout.jsonl").open("wb") as out, (case / "stderr.txt").open("wb") as err:
            parent = subprocess.Popen([sys.executable, "-I", "-B", str(server), "--beryl", str(exe), "--project", str(case)],
                                      stdin=subprocess.PIPE, stdout=out, stderr=err, env=environment,
                                      creationflags=subprocess.CREATE_NO_WINDOW)
            try:
                parent.stdin.write(raw); parent.stdin.flush()
                handles = [opened(int(wait_file(case / name))) for name in ("parent.pid", "leaf.pid")]
                parent.kill(); parent.wait(timeout=5)
                assert all(api.WaitForSingleObject(handle, 5000) == 0 for handle in handles)
            finally:
                if parent.poll() is None:
                    parent.kill(); parent.wait(timeout=5)
                parent.stdin.close()
                dispose(handles)
        assert not (case / "stderr.txt").read_bytes()
        evidence["checks"].append({"case": case.name, "status": "success", "server_sha256": hashlib.sha256(server_data).hexdigest(),
                                   "descendants_stopped_on_host_death": True})

        # Preserve the existing mod.Job.run call pattern and log/exit behavior.
        trusted = work / "trusted-tools"; trusted.mkdir()
        original = runpy.run_path(str(ROOT / "tools/beryl-mod/mod.py"))
        for path in original["bundle_paths"]():
            (trusted / path.name).write_bytes(path.read_bytes())
        (trusted / "process_job.py").write_bytes(data)
        mod = runpy.run_path(str(trusted / "mod.py"))
        case = work / "mod-caller"; case.mkdir()
        job = mod["Job"](case, "check", exe)
        out = job.run([str(exe), "--success"], "ownership-smoke", case, timeout=10)
        assert out.strip() == b"BERYL_PROCESS_JOB_OK"
        assert job.result["raw_logs"][0]["exit_code"] == 0
        evidence["checks"].append({"case": "mod.Job.run", "status": "success", "raw_logs": job.result["raw_logs"]})
        evidence["status"] = "success"
    except BaseException as error:
        evidence["status"] = "failure"; evidence["error"] = repr(error)
        raise
    finally:
        (work / "results.json").write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
        print(work / "results.json", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
