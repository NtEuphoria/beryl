#!/usr/bin/env python3
"""Verify bounded implicit/explicit receiver-mode parity without engine jobs."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent.parent
PLAIN = "struct R { x: i32 }\n"
SINK = "fn R.take(sink self, tag: i32 = 0) -> i32 { return self.x + tag }\n"
SINK_EXPLICIT = "fn take(sink r: R, tag: i32 = 0) -> i32 { return r.x + tag }\n"
SET = "fn R.fill(set self, value: i32 = 7) { self = R{x: value} }\n"
SET_EXPLICIT = "fn fill(set r: R, value: i32 = 7) { r = R{x: value} }\n"
READ = "fn R.read(let self) -> i32 { return self.x }\n"
INDEX = "fn index(sink n: i32) -> i32 { println(90)\nreturn n }\n"
ROUTES = ("check-native", "check-native-json", "check-enfusion", "check-enfusion-json",
          "emit-c", "build-ast", "run-ast", "build-enfusion", "test-native-O0",
          "test-native-O2", "test-reference-ast", "test-differential-ast-O0",
          "test-differential-ast-O2", "test-differential-ir-O0", "test-differential-ir-O2")
# Owning declarations have native/Enfusion storage admission. The bounded
# reference and IR subsets reject these types through different unavailable
# stages, so those routes are not claimed as physical-storage frontend gates.
STORAGE_ROUTES = ROUTES[:10]

# This is a declaration-reviewed target inventory, not a diagnostic guess or a
# search for receiver spelling. The current Enfusion backend rejects declared
# SET/SINK self because its implicit instance cannot implement those caller
# storage contracts. All fixtures and native/reference cases remain selected.
# A new safe fixture needs an explicit oracle before this runner will proceed.
SAFE_ENFUSION_ADMISSION = {
    "uninit_method": "BE0701",       # SET self declaration
    "uninit_explicit": None,          # ordinary explicit SET parameter
    "set_reinitialize": "BE0701",    # SET and SINK self declarations
    "let_first_init": "BE0701",      # SET self declaration
    "outer_set": "BE0701",           # SET self declaration in nested helper
    "sink_literal": "BE0701",        # SINK self declaration
    "index_let_once": None,           # LET self; sink is an explicit scalar
    "index_set_once": "BE0701",      # SET self declaration
    "defaults": "BE0701",            # SET and SINK self declarations
    "method_explicit_parity": "BE0701",  # SET and SINK self declarations
}


def fixtures():
    negative = {}
    for form in ("method", "explicit"):
        take = "r.take()" if form == "method" else "take(sink r)"
        decl = SINK if form == "method" else SINK_EXPLICIT
        negative[f"sink_{form}_use"] = (PLAIN + decl + f'fn f() {{ var r = R{{x: 1}}\n{take}\nprintln(r.x) }}\n', "BE0403")
        for mode in ("let", "inout"):
            negative[f"sink_{form}_borrow_{mode}"] = (PLAIN + decl + f'fn f({mode} r: R) -> i32 {{ return {take} }}\n', "BE0406")
        partial = "p.child.take()" if form == "method" else "take(sink p.child)"
        negative[f"sink_{form}_partial"] = (PLAIN + "struct P { child: R }\n" + decl + f'fn f() {{ var p = P{{child: R{{x: 1}}}}\n{partial} }}\n', "BE0406")
        indexed = "xs[0].take()" if form == "method" else "take(sink xs[0])"
        negative[f"sink_{form}_index"] = (PLAIN + decl + f'fn f() {{ var xs = [R{{x: 1}}]\n{indexed} }}\n', "BE0406")
        later = "r.take(r.x)" if form == "method" else "take(sink r, r.x)"
        negative[f"sink_{form}_later_read"] = (PLAIN + decl + f'fn f() {{ var r = R{{x: 1}}\n{later} }}\n', "BE0403")
        fill = "r.fill()" if form == "method" else "fill(set r)"
        decl = SET if form == "method" else SET_EXPLICIT
        negative[f"set_{form}_immutable"] = (PLAIN + decl + f'fn f() {{ let r = R{{x: 1}}\n{fill} }}\n', "BE0407")
        negative[f"set_{form}_borrow_let"] = (PLAIN + decl + f'fn f(let r: R) {{ {fill} }}\n', "BE0407")
        later = "r.fill(r.x)" if form == "method" else "fill(set r, r.x)"
        negative[f"set_{form}_later_read"] = (PLAIN + decl + f'fn f() {{ var r: R\n{later} }}\n', "BE0405")
        partial = "p.child.fill()" if form == "method" else "fill(set p.child)"
        negative[f"set_{form}_parent_uninit"] = (PLAIN + "struct P { child: R }\n" + decl + f'fn f() {{ var p: P\n{partial} }}\n', "BE0405")
        conditional = "fn R.fill(set self, flag: bool) { if flag { self = R{x: 7} } }\n" if form == "method" else "fn fill(set r: R, flag: bool) { if flag { r = R{x: 7} } }\n"
        negative[f"set_{form}_noninit"] = (PLAIN + conditional, "BE0404")
        owned = "struct Owned { xs: List<i32> }\n"
        decl = "fn Owned.take(sink self) { }\n" if form == "method" else "fn take(sink r: Owned) { }\n"
        negative[f"owning_sink_{form}"] = (owned + decl, {"native": "BE0903", "enfusion": "BE0701"})
        decl = "fn Owned.fill(set self) { self = Owned{} }\n" if form == "method" else "fn fill(set r: Owned) { r = Owned{} }\n"
        negative[f"owning_set_{form}"] = (owned + decl, {"native": "BE0903", "enfusion": "BE0701"})
    negative["let_index_after_move"] = (PLAIN + READ + INDEX + 'fn f() { var xs = [R{x: 1}]\nvar n = 0\nxs[index(sink n)].read()\nprintln(n) }\n', "BE0403")
    negative["set_rvalue"] = (PLAIN + SET + 'fn f() { R{x: 1}.fill() }\n', "BE0401")
    negative["inout_rvalue"] = (PLAIN + 'fn R.bump(inout self) { self.x += 1 }\nfn f() { R{x: 1}.bump() }\n', "BE0401")
    safe = {
        "uninit_method": (PLAIN + SET + 'test "set initializes" { var r: R\nr.fill()\nassert(r.x == 7)\nprintln(r.x) }\n', 1, "7\n"),
        "uninit_explicit": (PLAIN + SET_EXPLICIT + 'test "explicit set initializes" { var r: R\nfill(set r)\nassert(r.x == 7)\nprintln(r.x) }\n', 1, "7\n"),
        "set_reinitialize": (PLAIN + SET + SINK + 'test "set after move" { var r = R{x: 1}\nlet got = r.take()\nr.fill()\nassert(got == 1)\nassert(r.x == 7)\nprintln(got)\nprintln(r.x) }\n', 2, "1\n7\n"),
        "let_first_init": (PLAIN + SET + 'test "first initialization" { let r: R\nr.fill(13)\nassert(r.x == 13)\nprintln(r.x) }\n', 1, "13\n"),
        "outer_set": (PLAIN + SET + 'fn initialize(set r: R) { r.fill(17) }\ntest "outer set" { var r: R\ninitialize(set r)\nassert(r.x == 17)\nprintln(r.x) }\n', 1, "17\n"),
        "sink_literal": (PLAIN + SINK + 'test "fresh sink receiver" { let got = R{x: 1}.take(2)\nassert(got == 3)\nprintln(got) }\n', 1, "3\n"),
        "index_let_once": (PLAIN + READ + INDEX + 'test "index once" { var xs = [R{x: 17}]\nvar n = 0\nlet got = xs[index(sink n)].read()\nassert(got == 17)\nprintln(got) }\n', 1, "90\n17\n"),
        "index_set_once": (PLAIN + SET + INDEX + 'test "set index once" { var xs = [R{x: 1}]\nvar n = 0\nxs[index(sink n)].fill(23)\nassert(xs[0].x == 23)\nprintln(xs[0].x) }\n', 1, "90\n23\n"),
        "defaults": (PLAIN + 'fn mark(value: i32) -> i32 { println(value)\nreturn value }\nfn R.fill(set self, value: i32 = mark(7)) { self = R{x: value} }\nfn R.take(sink self, tag: i32 = mark(5)) -> i32 { return self.x + tag }\ntest "default order" { var r: R\nr.fill()\nlet got = r.take()\nassert(got == 12)\nprintln(got) }\n', 1, "7\n5\n12\n"),
        "method_explicit_parity": (PLAIN + SET + SET_EXPLICIT + SINK + SINK_EXPLICIT + 'test "mode parity" { var r = R{x: 1}\nvar q = R{x: 1}\nr.fill()\nfill(set q)\nassert(r.x == q.x)\nlet a = r.take(2)\nlet b = take(sink q, 2)\nassert(a == 9)\nassert(a == b)\nprintln(a)\nprintln(b) }\n', 3, "9\n9\n"),
    }
    return negative, safe


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(value, message):
    if not value:
        raise AssertionError(message)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--beryl", required=True, type=Path)
    parser.add_argument("--clang", required=True, type=Path)
    parser.add_argument("--expect-compiler-sha256")
    args = parser.parse_args()
    beryl, clang = args.beryl.resolve(strict=True), args.clang.resolve(strict=True)
    compiler_hash = sha(beryl)
    require(not args.expect_compiler_sha256 or compiler_hash == args.expect_compiler_sha256,
            "candidate hash differs from explicitly selected compiler")
    work = Path(tempfile.mkdtemp(prefix="receiver modes verified & spaces-", dir=ROOT / "build"))
    negative, safe = fixtures()
    require(set(SAFE_ENFUSION_ADMISSION) == set(safe),
            "safe fixture target oracle inventory differs from declarations")
    safe_target_oracles = {name: {
        "native": {"outcome": "admitted", "compiler_status": "success", "diagnostic": None},
        "enfusion": {"outcome": "unavailable" if code else "admitted",
                     "compiler_status": "failure" if code else "success", "diagnostic": code},
    } for name, code in SAFE_ENFUSION_ADMISSION.items()}
    paths = {}
    for name, data in (*negative.items(), *safe.items()):
        path = work / (name + ".be")
        # Storage admission runs after test selection. A neutral real test keeps
        # declaration-only owning negatives from stopping at an empty selection.
        selected_test = '\ntest "frontend selection guard" { assert(true) }\n' if name in negative else ""
        path.write_text("module receiver.verified." + name + "\n" + data[0] + selected_test, encoding="utf-8")
        paths[name] = path
    negative_routes = {name: STORAGE_ROUTES if isinstance(data[1], dict) else ROUTES
                       for name, data in negative.items()}
    expected_cases = [f"reject:{name}:{route}" for name in negative for route in negative_routes[name]]
    for name in safe:
        expected_cases.extend([f"safe:{name}:check-native", f"safe:{name}:check-enfusion",
                               f"safe:{name}:reference:O0", f"safe:{name}:differential:O0",
                               f"safe:{name}:differential:O2"])
    expected_cases.extend(["e2e:run:O0", "e2e:run:O2"])
    tracked = [Path(__file__).resolve(), beryl, clang, *paths.values(),
               ROOT / "tests/unit/test_ownership.c", ROOT / "tests/e2e/receiver_mode_order.be",
               ROOT / "tests/e2e/receiver_mode_order.expected",
               *sorted(p for p in (ROOT / "src").rglob("*") if p.is_file()),
               *sorted(p for p in (ROOT / "runtime").rglob("*") if p.is_file())]

    def identities():
        return {str(path): sha(path) for path in tracked}

    record = {"schema_version": 1, "operation": "verify_receiver_modes", "status": "running",
              "compiler_path": str(beryl), "compiler_sha256": compiler_hash,
              "clang_path": str(clang), "clang_sha256": sha(clang), "inputs": identities(),
              "expected_cases": expected_cases, "completed_cases": [], "commands": [],
              "executions": [], "checks": [], "engine_execution": "not_run", "installation": "not_run",
              "scope": "bounded plain-value receiver admission; no new owning storage or IR release",
              "negative_oracles": {name: data[1] for name, data in negative.items()},
              "negative_routes": negative_routes,
              "safe_target_oracles": safe_target_oracles, "target_checks": [],
              "target_policy": "Enfusion SET/SINK self declaration containment; explicit plain SET and LET self remain admitted"}
    env = os.environ.copy()
    env["PATH"] = str(clang.parent) + os.pathsep + env.get("PATH", "")
    env["BERYL_CLANG"] = str(clang)
    print(f"Receiver-mode artifacts: {work}", flush=True)

    def run(case, flags, expected=0):
        require(expected_cases[len(record["commands"])] == case, "unexpected command sequence")
        argv = list(map(str, [beryl, *flags]))
        try:
            proc = subprocess.run(argv, cwd=work, env=env, capture_output=True, timeout=120)
        except (OSError, subprocess.TimeoutExpired) as error:
            record["commands"].append({"case": case, "argv": argv, "harness_failure": type(error).__name__, "detail": str(error)})
            raise
        entry = {"case": case, "argv": argv, "exit_code": proc.returncode,
                 "stdout": proc.stdout.decode("utf-8", errors="strict"),
                 "stderr": proc.stderr.decode("utf-8", errors="strict")}
        record["commands"].append(entry)
        require(expected is None or proc.returncode == expected, entry)
        return proc, entry

    def complete(case):
        require(case not in record["completed_cases"], "duplicate case completion")
        record["completed_cases"].append(case)

    def cache_state():
        return {str(p.relative_to(work)): "directory" if p.is_dir() else sha(p)
                for p in sorted((work / ".beryl-cache").rglob("*"))}

    def reject(name, oracle):
        source = paths[name]
        output = work / (name + "-prior.exe")
        output.write_bytes(b"previous executable sentinel\n")
        output_dir = work / (name + "-enfusion")
        output_dir.mkdir()
        previous_source = output_dir / "prior.c"
        previous_source.write_bytes(b"previous generated source sentinel\n")
        prior = {output: sha(output), previous_source: sha(previous_source)}
        routes = [
            ("check-native", ["check", source]),
            ("check-native-json", ["check", "--format", "json", source]),
            ("check-enfusion", ["check", "-t", "enfusion", source]),
            ("check-enfusion-json", ["check", "-t", "enfusion", "--format", "json", source]),
            ("emit-c", ["emit-c", "--tests", source]),
            ("build-ast", ["build", "--lowering", "ast", "--clang", clang, "-o", output, source]),
            ("run-ast", ["run", "--lowering", "ast", "--clang", clang, "-o", output, source]),
            ("build-enfusion", ["build", "-t", "enfusion", "--out-dir", output_dir, source]),
            ("test-native-O0", ["test", "--backend", "native", "--lowering", "ast", "--clang", clang, source]),
            ("test-native-O2", ["test", "--backend", "native", "--lowering", "ast", "--release", "--clang", clang, source]),
            ("test-reference-ast", ["test", "--backend", "reference", "--lowering", "ast", source]),
        ]
        for lowering in ("ast", "ir"):
            for release in (False, True):
                routes.append((f"test-differential-{lowering}-O{2 if release else 0}",
                               ["test", "--backend", "differential", "--lowering", lowering,
                                *(["--release"] if release else []), "--clang", clang, source]))
        routes = [(route, flags) for route, flags in routes if route in negative_routes[name]]
        require(tuple(route for route, _ in routes) == negative_routes[name], "negative route inventory changed")
        for route, flags in routes:
            case = f"reject:{name}:{route}"
            before = cache_state()
            proc, entry = run(case, flags, expected=None)
            target = "enfusion" if "enfusion" in route else "native"
            code = oracle[target] if isinstance(oracle, dict) else oracle
            require(proc.returncode != 0 and code in entry["stdout"] + entry["stderr"], entry)
            require(cache_state() == before, f"{case}: rejection created a job")
            require(all(path.is_file() and sha(path) == value for path, value in prior.items()),
                    f"{case}: rejection replaced prior output")
            require(set(output_dir.iterdir()) == {previous_source}, f"{case}: rejection generated output")
            if route == "emit-c":
                require(not proc.stdout, f"{case}: rejection emitted C")
            if route.endswith("-json"):
                payload = json.loads(proc.stdout)
                require(payload["status"] == "failure" and payload["compiler_fingerprint"] == compiler_hash, payload)
                require(any(d["code"] == code for d in payload["diagnostics"]), payload)
            complete(case)
        record["checks"].append(f"{name}: correct mode/admission failure in {len(routes)} routes before jobs or output changes")

    def execute(name, backend, release):
        source = paths[name]
        _, assertions, output = safe[name]
        case = f"safe:{name}:{backend}:O{2 if release else 0}"
        before = set((work / ".beryl-cache").glob("job-*"))
        proc, entry = run(case, ["test", "--backend", backend, "--lowering", "ast",
                                *(["--release"] if release else []), "--clang", clang, source])
        fresh = set((work / ".beryl-cache").glob("job-*")) - before
        require(len(fresh) == 1, "expected one root verification job")
        job = fresh.pop()
        receipt = job / "result.json"
        result = json.loads(receipt.read_bytes())
        require(result["status"] == "success" and result["reference_status"] == "success", result)
        require(result["tests"] == 1 and result["failed_tests"] == 0 and result["assertions"] == assertions, result)
        require(result["compiler_fingerprint"] == compiler_hash and result["selected_lowering"] == "ast", result)
        require(result["sources"] == [{"path": str(source), "sha256": sha(source)}], result)
        expected_output = output + f"ok  1 test, {assertions} assertion{'s' if assertions != 1 else ''}\n"
        require(proc.stdout == expected_output.encode(), entry)
        events = job / "reference.events.jsonl"
        trace = [json.loads(line) for line in events.read_bytes().splitlines()]
        require(trace[0]["event"] == "test_begin" and trace[-1]["event"] == "test_end", trace)
        require([e["seq"] for e in trace] == list(range(len(trace))), "incomplete ordered events")
        require(sum(e["event"] == "assert" for e in trace) == assertions, trace)
        require(result["reference_events_sha256"] == sha(events), result)
        retained = {"case": case, "receipt": str(receipt), "receipt_sha256": sha(receipt),
                    "events_sha256": sha(events), "source_sha256": sha(source), "assertions": assertions}
        if backend == "differential":
            require(result["compared"] is True and result["native_status"] == "exited" and result["native_exit_code"] == 0, result)
            native_job = Path(result["native_job"])
            if not native_job.is_absolute():
                native_job = work / native_job
            executable = native_job / "program.exe"
            require(executable.is_file() and sha(executable) == result["native_executable_sha256"], result)
            retained.update(native_executable_sha256=sha(executable), generated_c_sha256=sha(native_job / "out.c"))
        else:
            require(result["compared"] is False and result["native_job"] is None, result)
        record["executions"].append(retained)
        complete(case)

    try:
        for name, (_, oracle) in negative.items():
            reject(name, oracle)
        for name in safe:
            for target in ("native", "enfusion"):
                case = f"safe:{name}:check-{target}"
                before = cache_state()
                oracle = safe_target_oracles[name][target]
                proc, entry = run(case, ["check", *(["-t", "enfusion"] if target == "enfusion" else []),
                                         "--format", "json", paths[name]],
                                  expected=None if oracle["diagnostic"] else 0)
                payload = json.loads(entry["stdout"])
                require(payload["status"] == oracle["compiler_status"] and
                        payload["compiler_fingerprint"] == compiler_hash, payload)
                codes = [diagnostic["code"] for diagnostic in payload["diagnostics"]]
                if oracle["diagnostic"]:
                    require(proc.returncode != 0 and oracle["diagnostic"] in codes, entry)
                else:
                    require(proc.returncode == 0, entry)
                require(cache_state() == before, "target check unexpectedly executed a job")
                record["target_checks"].append({"case": case, "target": target,
                    "expected_outcome": oracle["outcome"], "outcome": oracle["outcome"],
                    "compiler_status": payload["status"], "diagnostic_codes": codes,
                    "source_sha256": sha(paths[name]), "program_execution": "not_run"})
                complete(case)
            execute(name, "reference", False)
            execute(name, "differential", False)
            execute(name, "differential", True)
            record["checks"].append(f"{name}: native check and analytical reference/native AST O0/O2 parity; Enfusion {safe_target_oracles[name]['enfusion']['outcome']}")
        source = ROOT / "tests/e2e/receiver_mode_order.be"
        expected = (ROOT / "tests/e2e/receiver_mode_order.expected").read_text(encoding="utf-8")
        for release in (False, True):
            case = f"e2e:run:O{2 if release else 0}"
            executable = work / ("receiver-mode-O2.exe" if release else "receiver-mode-O0.exe")
            _, entry = run(case, ["run", "--lowering", "ast", *(["--release"] if release else []),
                                  "--clang", clang, "-o", executable, source])
            require(entry["stdout"].replace("\r\n", "\n") == expected, entry)
            require(executable.is_file(), "e2e output executable missing")
            record["executions"].append({"case": case, "source_sha256": sha(source),
                                         "native_executable_sha256": sha(executable), "output_comparison": "ordered text; CRLF normalized"})
            complete(case)
        record["inputs_after"] = identities()
        require(record["inputs"] == record["inputs_after"], "compiler, tool or source changed during verification")
        require(record["completed_cases"] == expected_cases, "incomplete expected case receipt")
        record["status"] = "success"
    except BaseException as error:
        record["status"] = "cancelled" if isinstance(error, KeyboardInterrupt) else "failure"
        record["failure"] = type(error).__name__ + ": " + str(error)
        raise
    finally:
        receipt = work / "results.json"
        receipt.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        print(f"Receipt: {receipt}", flush=True)
    print(f"passed {len(record['checks'])} receiver-mode groups / {len(expected_cases)} cases", flush=True)


if __name__ == "__main__":
    main()
