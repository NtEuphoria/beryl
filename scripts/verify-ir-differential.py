#!/usr/bin/env python3
"""Verify the explicit experimental IR differential-test route in isolated jobs.

No engine use, installation, production IR release or performance claim.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent.parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise AssertionError(message)


COPY_COMPILER = r'''
#define _POSIX_C_SOURCE 200809L
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#ifdef _WIN32
#include <windows.h>
#else
#include <time.h>
#endif
int main(int argc,char **argv) {
    const char *input=getenv("BERYL_IR_TEST_EXECUTABLE"), *output=NULL;
    for(int i=1;i<argc;i++) {
        if(!strcmp(argv[i],"--version")) { puts("IR evidence test compiler"); return 0; }
        if(!strcmp(argv[i],"-emit-llvm") && getenv("BERYL_IR_TEST_EVIDENCE_TIMEOUT")) {
#ifdef _WIN32
            Sleep(2000);
#else
            struct timespec delay={2,0}; nanosleep(&delay,NULL);
#endif
        }
    }
    for(int i=1;i<argc;i++) if(!strcmp(argv[i],"-o") && i+1<argc) output=argv[++i];
    if(!input || !output) return 93;
    FILE *a=fopen(input,"rb"), *b=fopen(output,"wb");
    if(!a || !b) return 94;
    unsigned char data[32768]; size_t n; int ok=1;
    while((n=fread(data,1,sizeof data,a))) if(fwrite(data,1,n,b)!=n) {ok=0;break;}
    if(ferror(a)) ok=0;
    if(fclose(a)) ok=0;
    if(fclose(b)) ok=0;
    return ok?0:95;
}
'''


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--beryl",type=Path,required=True)
    parser.add_argument("--clang",type=Path,required=True)
    args=parser.parse_args()
    beryl,clang=args.beryl.resolve(strict=True),args.clang.resolve(strict=True)
    work=Path(tempfile.mkdtemp(prefix="ir differential & spaces-",dir=ROOT/"build"))
    env=os.environ.copy()
    env["PATH"]=str(clang.parent)+os.pathsep+env.get("PATH","")
    inputs=[Path(__file__).resolve(),beryl,clang,*sorted((ROOT/"src").rglob("*"))]
    inputs=[p for p in inputs if p.is_file()]
    record={"schema_version":1,"status":"running","compiler_sha256":sha(beryl),
            "inputs":{str(p):sha(p) for p in inputs},"commands":[],"groups":[]}
    print(f"IR differential artifacts: {work}",flush=True)

    def run(argv,expected=0):
        argv=list(map(str,argv))
        try:
            p=subprocess.run(argv,cwd=work,env=env,capture_output=True,timeout=180)
        except (OSError,subprocess.TimeoutExpired) as error:
            record["commands"].append({"argv":argv,"harness_failure":str(error)})
            raise
        record["commands"].append({"argv":argv,"exit":p.returncode,
            "stdout":p.stdout.decode("utf-8",errors="replace"),"stderr":p.stderr.decode("utf-8",errors="replace")})
        require(expected is None or p.returncode==expected,record["commands"][-1])
        return p

    def fixture(name,text):
        p=work/(name+".be");p.write_bytes(text.encode("utf-8"));return p

    def jobs():
        return set((work/".beryl-cache").glob("job-*"))

    def execute(sources,expected=0,extra=(),native_compiler=None,lowering="ir"):
        before=jobs()
        p=run([beryl,"test","--backend","differential","--lowering",lowering,
               "--clang",native_compiler or clang,*extra,*sources],expected)
        fresh=jobs()-before;require(len(fresh)==1,(fresh,p.stderr))
        job=fresh.pop();result=json.loads((job/"result.json").read_bytes())
        require(result["selected_lowering"]==("ast" if lowering=="auto" else lowering),result)
        require(result["status"]=="success" if expected==0 else result["status"]!="success",result)
        if result["status"]=="success":
            require(result["compared"] is True and result["native_status"]=="exited",result)
            if lowering=="ir":
                profile=result["ir_test_profile"]
                require(profile["admitted"] is True and profile["production_backend"] is False,profile)
                generated=Path(result["native_job"])/"out.c"
                require(sha(generated)==profile["generated_c_sha256"],profile)
        return result,job,p

    def passed(name):
        record["groups"].append(name);print("passed "+name,flush=True)

    try:
        value=fixture("values",'''module irroute
struct R { a: i32, b: i32 }
fn mark(let n: i32) -> i32 { println(n)\nreturn n }
fn value(let r: R) -> R { return r }
test "ordered values" {
    let r = R { b: mark(2), a: mark(1) }
    var xs = [value(r), R { a: 3, b: 4 }]
    var copy = xs\ncopy[0].a += 8
    assert(xs[0].a == 1)\nassert(copy[0].a == 9)
    for v in xs { xs[1].a = 7\nprintln(v.a) }
    assert(false && (mark(99) == 99) == false)
    let big: f32 = 16777216\nassert((big + 1) - big == 0)
    println(-0f32)\ndefer println(5)\nprintln(6)
}
''')
        # Parenthesize the complete Boolean observation explicitly.
        value.write_bytes(value.read_bytes().replace(b"assert(false && (mark(99) == 99) == false)",
                                                     b"assert((false && (mark(99) == 99)) == false)"))
        for release in (False,True):
            result,job,p=execute([value],extra=(["--release"] if release else [])+["--save-native-evidence"])
            require(p.stdout==b"2\n1\n1\n3\n-0\n5\n6\nok  1 test, 4 assertions\n",p.stdout)
            native=Path(result["native_job"])
            evidence=json.loads((native/"native-evidence.json").read_bytes())
            require(evidence["selected_lowering"]=="ir" and evidence["requested_lowering"]=="ir",evidence)
            require(evidence["status"]=="success" and evidence["measurement_status"]=="not_measured",evidence)
            require([x["name"] for x in evidence["passes"]]==["llvm-ir","assembly","driver-jobs"],evidence)
            require(all(x["process"]["status"]=="exited" and x["process"]["exit_code"]==0 for x in evidence["passes"]),evidence)
        passed("ordered plain-value IR execution and native evidence at O0/O2")

        pid=[]
        for source in (ROOT/"packages/sparkos/pid/pid.be",ROOT/"packages/sparkos/pid/pid_test.be"):
            dest=work/source.name;dest.write_bytes(source.read_bytes());pid.append(dest)
            record["inputs"][str(source)]=sha(source)
        for release in (False,True):
            result,_,_=execute(pid,extra=["--release"] if release else [])
            require(result["tests"]==8 and result["assertions"]==2206,result)
        passed("full PID: eight tests and 2206 assertions at O0/O2")

        traps=[
            ("overflow","overflow","var n = 2147483647\nprintln(1)\nn += 1\nprintln(2)","n += 1"),
            ("division","division_by_zero","let z = 0\nprintln(3)\nprintln(1 / z)","1 / z"),
            ("division-overflow","overflow","let n = -2147483648\nlet m = -1\nprintln(n / m)","n / m"),
            ("bounds","bounds","var xs = [1, 2]\nprintln(4)\nxs[2] = 9\nprintln(5)","xs[2]"),
            ("negative","bounds","let xs = [1]\nprintln(xs[-1])","xs[-1]"),
            ("negation","overflow","let n = -2147483648\nprintln(-n)","-n"),
        ]
        trap_products={}
        for name,kind,body,needle in traps:
            source=fixture(name,'module trapcase\ntest "first trap" {\n'+body+'\n}\n')
            site=source.read_bytes().index(needle.encode())
            expectation=f"{kind}@0:{site}"
            for release in (False,True):
                result,job,_=execute([source],extra=(["--release"] if release else [])+["--expect-source-trap",expectation])
                require(result["native_source_trap_verified"] is True and result["program_outcome"]=="trap",result)
                trap_products[name]=(source,expectation,result,job)
        passed("all three certified trap categories, exact first sites and prefixes at O0/O2")

        source,expectation,baseline,_=trap_products["overflow"]
        execute([source],expected=1)  # ordinary traps still fail tests
        execute([source],expected=1,extra=["--expect-source-trap",expectation+"0"])
        unsupported=fixture("unsupported",'module outside\ntest "f64" { let n: f64 = 1\nprintln(n) }\n')
        result,job,_=execute([unsupported],expected=3)
        require(result["status"]=="unavailable" and result["reference_attempted"] is False,result)
        require(result["native_job"] is None and not list(job.glob("job-*")),result)
        passed("unsupported IR never executes reference/native or falls back; ordinary traps fail")

        for name,body in (
            ("nonfinite","let z: f32 = 0\nprintln(1f32 / z)"),
            ("cast","let n: f32 = 2147483648\nprintln(n as i32)"),
            ("shift","let n = 32\nprintln(1 << n)"),
            ("budget","while true { }"),
            ("assertion","assert(false)\nprintln(1)")):
            bad=fixture(name,'module outside\ntest "domain" { '+body+' }\n')
            result,_,_=execute([bad],expected=1,extra=["--expect-source-trap","overflow@0:0","--max-steps","10000"])
            require(result["native_source_trap_verified"] is False and result["native_job"] is None,result)
        passed("numeric-domain, budget and assertion failures cannot satisfy source-trap verification")

        before=jobs()
        for command in ("build","run","test"):
            run([beryl,command,"--lowering","ir",value],expected=3)
        run([beryl,"test","--backend","reference","--lowering","ir",value],expected=2)
        run([beryl,"test","--backend","differential","--lowering","ir","--observe-root","0:0",
             "--expect-source-trap","overflow@0:0",value],expected=3)
        run([beryl,"test","--backend","differential","--lowering","ir","--target","enfusion",value],expected=2)
        require(jobs()==before,"unavailable option combination created execution job")
        empty=fixture("empty","module empty\nfn main() {}\n")
        run([beryl,"test","--backend","differential","--lowering","ir",empty],expected=2)
        require(jobs()==before,"empty test selection created execution job")
        auto,_,_=execute([value],lowering="auto")
        require(auto["ir_test_profile"] is None,auto)
        passed("production/reference/watch/engine/empty selections stay unavailable and auto remains AST")

        result,_,_=execute([source],expected=1,extra=["--expect-source-trap",expectation],native_compiler=work/"missing-clang.exe")
        require(result["compared"] is False and result["native_source_trap_verified"] is False,result)
        passed("native startup failure is not a source trap")

        compiler_c=work/"copy-compiler.c";compiler_c.write_text(COPY_COMPILER,encoding="utf-8")
        fake=work/"copy-compiler.exe"
        run([clang,"-std=c11","-O2",compiler_c,"-o",fake])
        native=Path(baseline["native_job"])
        original=(native/"out.c").read_text(encoding="utf-8")
        mutants={"missing-trap":original.replace("be_add_i32_at(","be_sub_i32_at(",1),
                 "extra-prefix":original.replace("int main(void){","int main(void){\nputs(\"unexpected\");",1),
                 "wrong-site":re.sub(r"(be_add_i32_at\(v_\d+, v_\d+, be_ir_file_\d+, \d+, \d+, )(\d+)(\))",
                     lambda m:m[1]+str(int(m[2])+1)+m[3],original,count=1),
                 "native-domain":original.replace("beryl_test_trace_enable();",'beryl_test_trace_enable();\nbe_ir_domain("outside finite IR domain",be_ir_file_0,1);',1),
                 "native-budget":original.replace("beryl_test_trace_enable();",'beryl_test_trace_enable();\nbe_ir_steps=UINT64_C(1000000); be_ir_tick(be_ir_file_0,1);',1)}
        for name,code in mutants.items():
            require(code!=original,"mutant failed to change source: "+name)
            c=work/(name+".c");exe=work/(name+".exe");c.write_text(code,encoding="utf-8")
            run([clang,"-std=c11","-O2","-ffp-contract=off","-fno-fast-math","-I",native,c,native/"beryl_rt.c","-o",exe])
            env["BERYL_IR_TEST_EXECUTABLE"]=str(exe)
            result,_,_=execute([source],expected=1,extra=["--expect-source-trap",expectation],native_compiler=fake)
            require(result["native_source_trap_verified"] is False,result)
        passed("five executed native mutants: missing trap, wrong site, extra prefix and uncertified domain/budget exits rejected")
        env["BERYL_IR_TEST_EXECUTABLE"]=str(native/"program.exe")
        env["BERYL_IR_TEST_EVIDENCE_TIMEOUT"]="1"
        result,_,_=execute([source],expected=1,native_compiler=fake,
                          extra=["--expect-source-trap",expectation,"--save-native-evidence","--timeout-ms","500"])
        require(result["status"]=="timeout" and result["native_source_trap_verified"] is False and result["native_status"] is None,result)
        passed("native compiler-evidence timeout retains its distinct top-level outcome")
        require(all(sha(Path(path))==digest for path,digest in record["inputs"].items()),"verification input changed")
        record["status"]="passed"
    except Exception as error:
        record.update(status="failure",error=str(error));raise
    finally:
        (work/"results.json").write_text(json.dumps(record,indent=2)+"\n",encoding="utf-8")
        print(work/"results.json",flush=True)


if __name__=="__main__":
    main()
