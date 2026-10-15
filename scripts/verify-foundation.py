#!/usr/bin/env python3
"""Build once; check unit tests and execute generated C at O0/O2.

Uses argv subprocesses, isolated output directories, checked exit statuses and
timeouts. A denied launch stops the run. No binary mutation or launch retries.
Requires Python 3 and the existing Clang toolchain. No third-party packages.
"""
import argparse
import hashlib
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clang", default="clang")
    parser.add_argument("--sanitize", action="store_true", help="enable UBSan, failing on its first report")
    parser.add_argument("--unit-only", action="store_true", help="build the candidate and run compiler unit tests only; no generated-program or engine-export coverage")
    opts = parser.parse_args()
    compiler = shutil.which(opts.clang)
    if not compiler:
        raise RuntimeError(f"Clang not found: {opts.clang}")
    (ROOT / "build").mkdir(exist_ok=True)
    output = Path(tempfile.mkdtemp(prefix="foundation-", dir=ROOT / "build"))
    env = os.environ.copy()
    env["PATH"] = str(Path(compiler).parent) + os.pathsep + env.get("PATH", "")
    evidence = {"status": "running", "sanitizers": opts.sanitize, "commands": [], "programs": [],
                "execution_scope": "compiler_build_and_unit_tests" if opts.unit_only else "full_foundation",
                "native_regression_execution": "not_selected" if opts.unit_only else "incomplete"}
    def source_hashes():
        return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                for folder in ("src", "runtime", "tests", "scripts", "examples", "lib", "packages", "schemas", "tools")
                for p in sorted(ROOT.joinpath(folder).rglob("*"))
                if p.is_file() and not {"__pycache__", ".beryl-mod", ".beryl-cache"}.intersection(p.parts)}
    evidence["source_hashes"] = source_hashes()
    report = output / "results.json"
    print(f"Artifacts: {output}", flush=True)

    def run(args, *, expected=0, timeout=90):
        args = [str(x) for x in args]
        started = time.monotonic()
        try:
            proc = subprocess.run(args, cwd=ROOT, env=env, capture_output=True,
                                  text=True, encoding="utf-8", errors="replace", timeout=timeout)
        except (OSError, subprocess.TimeoutExpired) as exc:
            evidence["commands"].append({"argv": args, "failure": str(exc)})
            raise RuntimeError(f"Process did not complete; no retry: {args[0]}: {exc}") from exc
        evidence["commands"].append({"argv": args, "exit_code": proc.returncode,
            "seconds": time.monotonic() - started, "stdout": proc.stdout, "stderr": proc.stderr})
        if expected is not None and proc.returncode != expected:
            raise RuntimeError(f"Exit {proc.returncode}, expected {expected}: {args}\n{proc.stdout}\n{proc.stderr}")
        return proc

    try:
        evidence["toolchain"] = run([compiler, "--version"]).stdout
        paths = sorted(ROOT.joinpath("src").rglob("*.c"))
        codes = set()
        for path in paths:
            codes.update(re.findall(r"\b(?:diag_error|diag_warn|err|fail)\s*\(\s*[^,]+,\s*([0-9]{3,4})\b",
                                    path.read_text(encoding="utf-8")))
        documented = ROOT.joinpath("docs/DIAGNOSTICS.md").read_text(encoding="utf-8")
        missing_codes = sorted(code for code in codes if f"BE{int(code):04d}" not in documented)
        if not codes or missing_codes:
            raise RuntimeError(f"Diagnostic documentation check failed: {missing_codes or 'no codes found'}")
        evidence["documented_literal_codes"] = len(codes)
        source = [str(p.relative_to(ROOT)) for p in paths]
        checks = [s for s in source if s.replace("\\", "/") != "src/driver/main.c"]
        checks += [str(p.relative_to(ROOT)) for p in sorted(ROOT.joinpath("tests").rglob("*.c"))]
        common = ["-std=c11", "-Wall", "-Wextra", "-Werror", "-Wno-unused-parameter", "-Isrc"]
        sanitize = ["-fsanitize=undefined", "-fno-sanitize-recover=all"] if opts.sanitize else []
        exe = ".exe" if os.name == "nt" else ""
        unit = output / ("unit" + exe)
        beryl = output / ("beryl" + exe)
        run([compiler, *common, "-O0", "-g", *sanitize, *checks, "-o", unit])
        evidence["unit_summary"] = run([unit]).stdout.strip()
        print(evidence["unit_summary"], flush=True)
        run([compiler, *common, "-O2", *sanitize, *source, "-o", beryl])
        evidence["compiler_sha256"] = hashlib.sha256(beryl.read_bytes()).hexdigest()
        if opts.unit_only:
            if source_hashes() != evidence["source_hashes"]:
                raise RuntimeError("Source changed during unit verification; this run is stale")
            evidence["status"] = "passed"
            return

        # Regression: a diagnostic/read failure cannot count as successful check.
        missing = output / "missing.be"
        failed = run([beryl, "check", missing], expected=None)
        if failed.returncode == 0 or "BE0803" not in failed.stderr:
            raise RuntimeError("Missing-source check incorrectly passed or lost its diagnostic")
        failed = run([beryl, "check", "--target", "misspelled", "tests/e2e/arith.be"], expected=None)
        if failed.returncode == 0:
            raise RuntimeError("Unknown target incorrectly passed")
        profile = output / "profile.be"
        profile.write_text("module t\nfn f() { var x: f64 }\n", encoding="utf-8")
        failed = run([beryl, "check", "-t", "enfusion", profile], expected=None)
        if failed.returncode == 0 or "BE0701" not in failed.stderr:
            raise RuntimeError("Enfusion check did not apply its type profile")
        profile.write_text("module t\nfn f() { var x: Map<i32, i32> }\n", encoding="utf-8")
        failed = run([beryl, "check", profile], expected=None)
        if failed.returncode == 0 or "BE0901" not in failed.stderr:
            raise RuntimeError("Native check did not apply its type profile")

        for src in sorted(ROOT.joinpath("tests/e2e").glob("*.be")):
            name = src.stem
            expected = src.with_suffix(".expected")
            trap = src.with_suffix(".trap")
            if expected.exists() == trap.exists():
                raise RuntimeError(f"Exactly one .expected or .trap required: {src}")
            code = run([beryl, "emit-c", src.relative_to(ROOT)]).stdout
            # Reproducibility assertion compares generated bytes, not timing.
            again = run([beryl, "emit-c", src.relative_to(ROOT)]).stdout
            if code != again:
                raise RuntimeError(f"Generated C is not deterministic: {name}")
            cfile = output / (name + ".c")
            cfile.write_text(code, encoding="utf-8", newline="\n")
            outputs = []
            for opt in ("-O0", "-O2"):
                target = output / (name + opt + exe)
                run([compiler, "-std=c11", "-Wall", "-Wextra", "-Wno-unused-variable",
                     "-Wno-unused-parameter", "-Wno-unused-function", opt, *sanitize,
                     "-Iruntime", cfile, "-o", target])
                result = run([target], expected=None, timeout=20)
                if expected.exists():
                    want = expected.read_text(encoding="utf-8")
                    if result.returncode != 0 or result.stdout != want or result.stderr:
                        raise RuntimeError(f"Wrong result {name} {opt}: exit {result.returncode}\n"
                                           f"expected {want!r}\nactual {result.stdout!r}\n{result.stderr}")
                else:
                    want = trap.read_text(encoding="utf-8").splitlines()[0]
                    if result.returncode == 0 or want not in result.stdout + result.stderr:
                        raise RuntimeError(f"Expected nonzero trap for {name} {opt}: {result}")
                    if "runtime error:" in result.stderr:
                        raise RuntimeError(f"UBSan failure is not a Beryl trap: {name} {opt}")
                outputs.append((result.returncode, result.stdout, result.stderr))
            if outputs[0] != outputs[1]:
                raise RuntimeError(f"O0/O2 outcomes differ: {name}")
            evidence["programs"].append({"name": name, "C_sha256": hashlib.sha256(code.encode()).hexdigest(),
                                         "status": "passed", "modes": ["O0", "O2"]})
            print(f"passed {name}: O0/O2", flush=True)

        # Multi-file declaration identity must survive both native optimization modes.
        module_sources = sorted(ROOT.joinpath("tests/modules").glob("*.be"))
        if not module_sources:
            raise RuntimeError("Module regression source set is empty")
        for test_mode in (False, True):
            arguments = [beryl, "emit-c", *(["--tests"] if test_mode else []),
                         *[p.relative_to(ROOT) for p in module_sources]]
            code = run(arguments).stdout
            if code != run(arguments).stdout:
                raise RuntimeError("Multi-module generated C changed on identical input")
            name = "module-tests" if test_mode else "module-program"
            cfile = output / (name + ".c")
            cfile.write_text(code, encoding="utf-8", newline="\n")
            for opt in ("-O0", "-O2"):
                target = output / (name + opt + exe)
                run([compiler, "-std=c11", opt, "-ffp-contract=off", "-fno-fast-math",
                     *sanitize, "-Iruntime", cfile, "-o", target])
                result = run([target], timeout=20)
                if result.stderr or (not test_mode and result.stdout != "32\n"):
                    raise RuntimeError(f"Wrong multi-module result: {result.stdout!r} {result.stderr!r}")
                if test_mode and "4 tests, 4 assertions" not in result.stdout:
                    raise RuntimeError(f"Incomplete module test execution: {result.stdout!r}")
            evidence["programs"].append({"name": name, "C_sha256": hashlib.sha256(code.encode()).hexdigest(),
                                         "status": "passed", "modes": ["O0", "O2"]})
            print(f"passed {name}: O0/O2", flush=True)

        export_args = ["--export-class", "collision.left.P=SPK_PID_Sample",
                       "--export-method", "collision.left.P.get=Step"]
        engine_args = [beryl, "build", "-t", "enfusion", "--prefix", "M1", *export_args,
                       *[p.relative_to(ROOT) for p in module_sources]]
        engine = run(engine_args).stdout
        if engine != run(engine_args).stdout or "class SPK_PID_Sample\n" not in engine or "int Step(" not in engine:
            raise RuntimeError("Exported engine source is missing names or is nondeterministic")
        (output / "module-export.c").write_text(engine, encoding="utf-8", newline="\n")
        evidence["engine_export_sha256"] = hashlib.sha256(engine.encode()).hexdigest()
        for mapping in ("collision.left.P=../escape", "missing.P=SPK_PID_Sample"):
            bad = run([beryl, "check", "--format", "json", "-t", "enfusion", "--export-class", mapping,
                       *[p.relative_to(ROOT) for p in module_sources]], expected=None)
            diagnostic = json.loads(bad.stdout)
            if bad.returncode == 0 or diagnostic["status"] != "failure" or not diagnostic["diagnostics"]:
                raise RuntimeError("Invalid export was admitted")

        # Run example test blocks against their real sibling implementation.
        for src in sorted(ROOT.joinpath("examples").glob("*_test.be")):
            implementation = src.with_name(src.name.replace("_test.be", ".be"))
            inputs = ([implementation.relative_to(ROOT)] if implementation.exists() else []) + [src.relative_to(ROOT)]
            code = run([beryl, "emit-c", "--tests", *inputs]).stdout
            cfile = output / (src.stem + ".c")
            cfile.write_text(code, encoding="utf-8", newline="\n")
            target = output / (src.stem + exe)
            run([compiler, "-std=c11", "-O2", *sanitize, "-Iruntime", cfile, "-o", target])
            result = run([target], timeout=20)
            print(f"passed {src.name}: {result.stdout.strip()}", flush=True)
        if source_hashes() != evidence["source_hashes"]:
            raise RuntimeError("Source changed during verification; this run is stale")
        evidence["compiler_sha256"] = hashlib.sha256(beryl.read_bytes()).hexdigest()
        evidence["native_regression_execution"] = "completed"
        evidence["status"] = "passed"
    except Exception as exc:
        evidence["status"] = "failed"
        evidence["failure"] = str(exc)
        raise
    finally:
        report.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
        print(f"Evidence: {report}", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as failure:
        print(f"FAILED: {failure}", file=sys.stderr)
        sys.exit(1)
