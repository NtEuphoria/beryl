#!/usr/bin/env python3
"""Verify bounded provenance/range admission through both public target checks.

No engine execution or machine-level security guarantee is inferred. Expected
diagnostics must be security diagnostics; a parser/type error cannot satisfy a
negative case. Every command, source and compiler identity is retained.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent.parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


CASES = [
    ("bounded_fixed", None, "@untrusted\nfn f(i:i32)->i32{let a=[1,2]\nreturn a[clamp(i,0,1)]}"),
    ("field_disjoint", None, "struct R{bad:i32,good:i32}\n@untrusted\nfn f(i:i32)->i32{var r=R{bad:0,good:0}\nr.bad=i\nlet a=[1,2]\nreturn a[r.good]}"),
    ("bounded_helper", None, "fn bound(i:i32)->i32{return clamp(i,0,1)}\n@untrusted\nfn f(i:i32)->i32{let a=[1,2]\nreturn a[bound(i)]}"),
    ("minimum", "BE0601", "@untrusted\nfn f(i:i32)->i32{let a=[1,2]\nreturn a[min(i,1)]}"),
    ("maximum", "BE0601", "@untrusted\nfn f(i:i32)->i32{let a=[1,2]\nreturn a[max(i,0)]}"),
    ("wrong_storage_bound", "BE0601", "@untrusted\nfn f(i:i32)->i32{let a=[1,2]\nreturn a[clamp(i,0,3)]}"),
    ("bare_validator", "BE0601", "@validator\nfn bound(i:i32)->i32{return i}\n@untrusted\nfn f(i:i32)->i32{let a=[1,2]\nreturn a[bound(i)]}"),
    ("helper_sink", "BE0601", "fn helper(i:i32)->i32{let a=[1,2]\nreturn a[i]}\n@untrusted\nfn f(i:i32)->i32{return helper(i)}"),
    ("field_write", "BE0601", "struct R{value:i32}\nfn put(inout r:R,i:i32){r.value=i}\n@untrusted\nfn f(i:i32)->i32{var r=R{value:0}\nput(inout r,i)\nlet a=[1,2]\nreturn a[r.value]}"),
    ("list_write", "BE0601", "fn put(inout xs:List<i32>,i:i32){xs.push(i)}\n@untrusted\nfn f(i:i32)->i32{var xs:List<i32>\nput(inout xs,i)\nlet a=[1,2]\nreturn a[xs.get(0)]}"),
    ("loop_backedge", "BE0601", "@untrusted\nfn f(i:i32){var j=0\nlet a=[1,2]\nwhile true{let x=a[j]\nj=i}}"),
    ("secret_short_circuit", "BE0602", "@secret\nfn f(key:bool)->bool{return key && true}"),
    ("secret_bounded_index", "BE0603", "@secret\nfn f(key:i32)->i32{let a=[1,2]\nreturn a[clamp(key,0,1)]}"),
    ("catch_binding", "BE0601", "@untrusted\nfn source()->!i32{return error.Bad}\nfn f(){let a=[1,2]\nlet v=source() catch |err| {let x=a[err]}}"),
    ("try_summary", "BE0601", "@untrusted\nfn source()->!i32{return error.Bad}\nfn middle()->!i32{let x=try source()\nreturn 0}\nfn f(){let a=[1,2]\nlet v=middle() catch |err| {let x=a[err]}}"),
    ("initializer_return", "BE0601", "fn bound(i:i32)->i32{let x=if i>2{return i}\nreturn clamp(i,0,1)}\n@untrusted\nfn f(i:i32)->i32{let a=[1,2]\nreturn a[bound(i)]}"),
    ("immediate_defer_return", "BE0601", "fn bound(i:i32)->i32{defer{if i>2{return i}}\nreturn clamp(i,0,1)}\n@untrusted\nfn f(i:i32)->i32{let a=[1,2]\nreturn a[bound(i)]}"),
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--beryl", required=True, type=Path)
    args = parser.parse_args()
    compiler = args.beryl.resolve(strict=True)
    (ROOT / "build").mkdir(exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="taint-", dir=ROOT / "build"))
    inputs = [Path(__file__), ROOT / "src/sema/taint.c", ROOT / "src/sema/taint.h",
              ROOT / "tests/unit/test_security.c"]
    before = {str(path.relative_to(ROOT)): sha(path) for path in inputs}
    report = {"schema_version": 1, "operation": "verify_taint", "status": "running",
              "compiler_sha256": sha(compiler), "inputs": before, "cases": [],
              "program_execution": "not_run", "engine_execution": "not_run"}
    print(f"Taint artifacts: {work}", flush=True)
    try:
        for name, expected, text in CASES:
            source = work / (name + ".be")
            source.write_text("module t\n" + text + "\n", encoding="utf-8", newline="\n")
            source_hash = sha(source)
            for target in ("native", "enfusion"):
                argv = [str(compiler), "check", "--format", "json", "--target", target, str(source)]
                case = {"id": f"{name}.{target}", "source": str(source), "sha256": source_hash,
                        "expected": expected or "success", "argv": argv, "status": "running"}
                report["cases"].append(case)
                run = subprocess.run(argv, cwd=work, capture_output=True, text=True,
                                     encoding="utf-8", errors="strict", timeout=30)
                case.update(exit_code=run.returncode, stdout=run.stdout, stderr=run.stderr)
                if run.stderr:
                    raise RuntimeError(f"Unexpected process stderr: {case['id']}")
                response = json.loads(run.stdout)
                codes = {item["code"] for item in response["diagnostics"] if item["level"] == "error"}
                if expected:
                    if run.returncode != 1 or response["status"] != "failure" or expected not in codes:
                        raise RuntimeError(f"Expected security rejection missing: {case['id']}")
                    if not codes.issubset({"BE0601", "BE0602", "BE0603"}):
                        raise RuntimeError(f"Unrelated diagnostic cannot satisfy security fixture: {case['id']}: {codes}")
                elif run.returncode != 0 or response["status"] != "success" or codes:
                    raise RuntimeError(f"Positive admission failed: {case['id']}")
                if response["compiler_fingerprint"] != report["compiler_sha256"]:
                    raise RuntimeError("Compiler identity mismatch")
                if sha(source) != source_hash:
                    raise RuntimeError("Fixture changed during checking")
                case["status"] = "passed"
        if before != {str(path.relative_to(ROOT)): sha(path) for path in inputs} or sha(compiler) != report["compiler_sha256"]:
            raise RuntimeError("Verification inputs changed")
        report["status"] = "passed"
        print(f"passed {len(report['cases'])} target checks", flush=True)
        return 0
    except Exception as exc:
        report["status"] = "failed"
        report["error"] = f"{type(exc).__name__}: {exc}"
        print(report["error"], flush=True)
        return 1
    finally:
        (work / "results.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
