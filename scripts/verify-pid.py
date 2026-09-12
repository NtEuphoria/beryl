#!/usr/bin/env python3
"""Complete PID: analytical tests, generated finite corpus, and real engine parity."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import struct
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools/beryl-mod"))
import mod

PACKAGE = ROOT / "packages/sparkos/pid"
ORIGINAL_HASH = "f03f8588b9c4c4298db1e933b4aafab5e778725faf30b4c734e23aa2b1bb2460"


def operations():
    out = [(7, [])]
    for configuration in ([0, 0, 0, 1, 0], [1, 2, 3, -1, -0.5], [0.5, 0.25, 0.125, 2, 0.0625]):
        out.append((0, configuration))
        out += [(1, [0, 0, 0.5, False]), (1, [-4, 0, 0.5, False]), (0, configuration)]
        for timestep in (0, -0.5, 0.5):
            out.append((1, [4, 1, timestep, False]))
        out += [(6, []), (4, [-1]), (1, [-4, 1, 0.5, True]), (1, [-4, 1, 0.5, False]),
                (4, [2]), (5, [0.5]), (1, [0, 2, 0.5, False]), (5, [0]),
                (1, [0, 4, 0.5, False]), (5, [0.5]), (1, [0, 4, 0.5, False]),
                (2, []), (3, [1, 2, 3]), (1, [4, 3, 0.5, False])]
    out.append((0, [0.5, 0.25, 0.125, 2, 0.0625]))
    seed = 104729
    for i in range(1024):
        seed = (seed * 1664525 + 1013904223) & 0xffffffff
        signed = seed if seed < 0x80000000 else seed - 0x100000000
        if i % 79 == 0: out.append((2, []))
        if i % 43 == 0: out.append((5, [0.0625]))
        if i % 47 == 0: out.append((5, [-1]))
        if i % 97 == 0: out.append((3, [0.5, 0.25, 0.125]))
        if i % 89 == 0: out.append((4, [i % 3]))
        dt = 0.015625
        if i % 31 == 0: dt = 0
        if i % 53 == 0: dt = -0.015625
        out.append((1, [(signed >> 16) / 8192, ((seed & 65535) - 32768) / 8192, dt, i % 7 == 0]))
        out.append((6, []))
    return out


def number(value):
    if type(value) is bool:
        return str(value).lower()
    return repr(float(value))


def beryl_corpus(ops):
    fields = ["kp", "ki", "kd", "integral_limit", "integral", "last_measurement", "has_last", "derivative_tau", "derivative_filtered"]
    lines = ["module pid.comparison", "use sparkos.flight.pid.Pid", "fn observe(let p: Pid, output: f32) {", "println(output)"]
    for field in fields:
        if field == "has_last":
            lines.append("if p.has_last { println(1f32) } else { println(0f32) }")
        else:
            lines.append("println(p." + field + ")")
    lines += ["}", 'test "complete operation corpus" {', "var p = Pid{}", "var output: f32 = 0"]
    for op, values in ops:
        args = ", ".join(number(v) for v in values)
        lines.append("output = 0")
        lines.append({0: f"p = Pid.make({args})", 1: f"output = p.step({args})", 2: "p.reset()",
                      3: f"p.set_gains({args})", 4: f"p.set_integral_limit({args})",
                      5: f"p.set_derivative_tau({args})", 6: "output = p.get_integral()", 7: "p = Pid.make()"}[op])
        lines.append("observe(p, output)")
    return "\n".join(lines + ["}", ""])


def original_instrumented(data):
    source = data.decode("utf-8")
    if source.count("SPK_PID") != 2:
        raise RuntimeError("Unexpected original fixture declaration/constructor")
    source = source.replace("SPK_PID", "SPK_PID_Original")
    fields = ["m_fKp", "m_fKi", "m_fKd", "m_fIntegralLimit", "m_fIntegral", "m_fLastMeasurement", "m_bHasLast", "m_fDerivTau", "m_fDerivFiltered"]
    observe = ["\nfloat BerylObserve(int field) {"]
    for index, field in enumerate(fields, 1):
        if index == 7:
            observe.append(f"if (field == 7) {{ if ({field}) return 1; return 0; }}")
        else:
            observe.append(f"if (field == {index}) return {field};")
    observe += ["return 0;", "}\n"]
    end = source.rfind("}")
    return source[:end] + "\n".join(observe) + source[end:]


def harness(ops, expected, token):
    template = (ROOT / "tests/pid/Comparison.c.in").read_text(encoding="utf-8")
    batches, calls = [], []
    for start in range(0, len(ops), 32):
        name = "Batch" + str(start // 32)
        calls.append(f"if (!{name}()) return m_Response;")
        lines = [f"bool {name}() {{"]
        for i in range(start, min(start + 32, len(ops))):
            op, values = ops[i]
            if op == 1:
                values = [*values[:3], 0, 0, values[3]]
            lines.append(f"Apply({op}" + (", " + ", ".join(number(v) for v in values) if values else "") + ");")
            for field, value in enumerate(expected[i]):
                lines.append(f"if (!Expect({field}, {number(value)})) return false;")
        batches.append("\n".join(lines + ["return true;", "}"]))
    return template.replace("@TOKEN@", token).replace("@RUN@", "\n".join(calls)).replace("@BATCHES@", "\n\n".join(batches))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--beryl", required=True)
    parser.add_argument("--clang", required=True)
    parser.add_argument("--workbench-tools")
    args = parser.parse_args()
    path = Path(tempfile.mkdtemp(prefix="pid-", dir=ROOT / "build"))
    job = mod.Job(path, "pid-verification", Path(args.beryl).resolve())
    print("PID artifacts: " + str(path), flush=True)
    job.result["status"] = "failure"
    try:
        inputs = path / "inputs"
        inputs.mkdir()
        for name in ("pid.be", "pid_test.be", "beryl.mod.json"):
            shutil.copyfile(PACKAGE / name, inputs / name)
        source_hashes = {name: mod.digest(mod.read(PACKAGE / name)) for name in ("pid.be", "pid_test.be", "beryl.mod.json")}
        original = mod.read(PACKAGE / "reference/SPK_PID.c.fixture")
        if mod.digest(original) != ORIGINAL_HASH:
            raise RuntimeError("Original behavioral fixture changed")
        job.result.update(source_hashes=source_hashes, original_sha256=ORIGINAL_HASH)
        output = job.run([job.compiler, "test", "--backend", "differential", "--max-bytes", "268435456",
                          "--clang", Path(args.clang).resolve(), "pid.be", "pid_test.be"], "analytical", inputs)
        if b"8 tests, 2206 assertions" not in output:
            raise RuntimeError("Analytical PID corpus did not complete")
        ops = operations()
        mod.write_json(path / "operations.json", ops)
        (inputs / "corpus.be").write_text(beryl_corpus(ops), encoding="utf-8", newline="\n")
        job.run([job.compiler, "test", "--backend", "differential", "--max-steps", "10000000", "--max-bytes", "536870912",
                 "--clang", Path(args.clang).resolve(), "pid.be", "corpus.be"], "differential", inputs)
        reports = [{**mod.parse(mod.read(p)), "report_path": str(p)} for p in (inputs / ".beryl-cache").glob("job-*/result.json")]
        reports = [r for r in reports if r.get("operation") == "test" and r.get("backend") == "differential"]
        # Identify the generated corpus by its loaded bytes, not newest-file time.
        corpus_hash = mod.digest(mod.read(inputs / "corpus.be"))
        reports = [r for r in reports if any(s.get("sha256") == corpus_hash for s in r.get("sources", []))]
        if len(reports) != 1 or reports[0]["status"] != "success":
            raise RuntimeError("Missing exact corpus differential report")
        report = reports[0]
        job.result["differential"] = report
        events_path = Path(report["report_path"]).parent / "reference.events.jsonl"
        bits = [event["bits"] for event in (json.loads(line) for line in Path(events_path).read_text().splitlines()) if event["event"] == "f32"]
        if len(bits) != 10 * len(ops):
            raise RuntimeError("Missing output/state observations")
        floats = [struct.unpack("<f", struct.pack("<I", value))[0] for value in bits]
        expected = [floats[i:i+10] for i in range(0, len(floats), 10)]
        mod.write_json(path / "expected-state.json", {"bits": bits, "operations": len(ops)})
        config = mod.parse(mod.read(inputs / "beryl.mod.json"))
        addon = path / "comparison"
        scripts = addon / "scripts/Game/Beryl"
        scripts.mkdir(parents=True)
        job.run([job.compiler, "build", "-t", "enfusion", "--prefix", "Beryl", "--out-dir", scripts,
                 *mod.export_flags(config), "pid.be"], "generation", inputs)
        token = mod.digest(mod.canonical({"operations": ops, "expected": bits, "source": source_hashes, "compiler": job.result["compiler_sha256"]}))
        guid = token[:16].upper()
        (addon / "addon.gproj").write_text(f'GameProject {{\n ID "BerylPidComparison"\n GUID "{guid}"\n TITLE "Beryl PID comparison"\n Dependencies {{\n "58D0FB3206B6F859"\n }}\n}}\n', encoding="utf-8")
        (scripts / "Original.c").write_text(original_instrumented(original), encoding="utf-8", newline="\n")
        handlers = addon / "scripts/WorkbenchGameCommon"
        handlers.mkdir()
        (handlers / "BerylPidComparison.c").write_text(harness(ops, expected, token), encoding="utf-8", newline="\n")
        job.result.update(operations=len(ops), expected_checks=30*len(ops), token=token)
        files = {str(p.relative_to(addon)): mod.digest(mod.read(p)) for p in addon.rglob("*") if p.is_file()}
        job.result["artifact_files"] = files
        if not args.workbench_tools:
            raise mod.Failure("Engine comparison was not requested; runtime gate remains unavailable", "unavailable")
        toolroot = Path(args.workbench_tools).resolve()
        job.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", ROOT / "tools/beryl-mod/engine-compile.ps1",
                 "-ToolRoot", toolroot, "-ProjectDir", addon, "-ResultPath", path / "engine-compile.json", "-ExpectedVersion", config["binding"]["version"]], "workbench_compile", path, 300)
        job.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", ROOT / "scripts/pid-engine-run.ps1",
                 "-ToolRoot", toolroot, "-ProjectDir", addon, "-ResultPath", path / "engine-runtime.json", "-Token", token,
                 "-ExpectedOperations", str(len(ops))], "engine_execution", path, 300)
        engine = mod.parse(mod.read(path / "engine-runtime.json"))
        if engine["status"] != "success":
            raise RuntimeError("Engine runtime did not pass")
        if any(mod.digest(mod.read(addon / name)) != value for name, value in files.items()):
            raise mod.Failure("Comparison source changed during execution", "stale_input")
        if any(mod.digest(mod.read(PACKAGE / name)) != value for name, value in source_hashes.items()):
            raise mod.Failure("PID source changed during execution", "stale_input")
        job.result.update(status="success", engine=engine)
        print(f"Passed {len(ops)} complete operations and {30*len(ops)} engine comparisons", flush=True)
    except (Exception, KeyboardInterrupt) as exc:
        job.result.update(status=getattr(exc, "status", "failure"), failure=str(exc))
        raise
    finally:
        mod.write_json(path / "result.json", job.result)
        print("Evidence: " + str(path / "result.json"), flush=True)


if __name__ == "__main__":
    main()
