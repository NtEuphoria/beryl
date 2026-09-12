#!/usr/bin/env python3
"""Compare generated integer intrinsics with independent fixtures in the real VM.

No engine or game source is modified. Every run stages a unique addon and keeps
the generated scripts, independent expected values, raw logs and hashes. A
baseline defect is a failed comparison, never a successful verification.
"""
from pathlib import Path
import argparse
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools/beryl-mod"))
import mod

FIXTURES = ROOT / "tests/engine-integers"
MINIMUM, MAXIMUM = -(1 << 31), (1 << 31) - 1
EXPORTS = {"minimum": "Minimum", "maximum": "Maximum", "bounded": "Bounded",
           "add": "Add", "subtract": "Subtract", "minimum_float": "MinimumFloat",
           "maximum_float": "MaximumFloat", "bounded_float": "BoundedFloat",
           "order": "Order", "clamp_order": "ClampOrder", "capture": "Capture",
           "short_circuit": "ShortCircuit", "compound_order": "CompoundOrder",
           "range_order": "RangeOrder", "range_once": "RangeOnce",
           "record_order": "RecordOrder", "record_capture": "RecordCapture",
           "array_capture": "ArrayCapture"}
TARGET_EXPORTS = {"vector_capture": "VectorCapture"}


def cases():
    out = []
    def add(method, values, expected, binding=None):
        out.append({"id": f"{method}-{len(out):04}", "method": method,
                    "args": values, "expected": expected, "binding": binding})
    edges = [MINIMUM, MINIMUM + 1, -16777217, -16777216, -1, 0, 1,
             16777216, 16777217, MAXIMUM - 1, MAXIMUM]
    for a in edges:
        for b in edges:
            add("minimum", [a, b], min(a, b), "MinInt")
            add("maximum", [a, b], max(a, b), "MaxInt")
            add("add", [a, b], min(MAXIMUM, max(MINIMUM, a + b)))
            add("subtract", [a, b], min(MAXIMUM, max(MINIMUM, a - b)))
    for a in edges:
        for lo, hi in [(MINIMUM, MAXIMUM), (16777217, MAXIMUM),
                       (MINIMUM, -16777217), (-1, 1), (1, -1)]:
            add("bounded", [a, lo, hi], lo if a < lo else hi if a > hi else a, "ClampInt")
    for a, b in [(-1.25, 2.5), (0.0, 0.125), (16777216.0, 16777218.0)]:
        add("minimum_float", [a, b], min(a, b), "Min")
        add("maximum_float", [a, b], max(a, b), "Max")
    for a, lo, hi in [(-2.5, -1.25, 0.5), (3.0, -1.25, 0.5), (0.125, -1.25, 0.5), (0.0, 1.0, -1.0)]:
        add("bounded_float", [a, lo, hi], lo if a < lo else hi if a > hi else a, "Clamp")
    add("order", [], 199)
    add("clamp_order", [], 302)
    add("capture", [], 100)
    add("short_circuit", [], 0)
    add("compound_order", [], 9)
    add("range_order", [], 3100)
    add("range_once", [], 3)
    add("record_order", [], 221)
    add("record_capture", [], 110)
    add("array_capture", [], 1011)
    add("vector_capture", [], 911)
    out[-1]["coverage"] = "native_and_engine_only"
    return out


def literal(value, beryl=False):
    if type(value) is float:
        return repr(value) + ("f32" if beryl else "")
    return str(value)


def harness(data, token):
    lines = []
    for case in data:
        arguments = ", ".join(literal(value) for value in case["args"])
        check = "ExpectFloat" if type(case["expected"]) is float else "Expect"
        target_only = case.get("coverage") == "native_and_engine_only"
        receiver = "BerylTargetOps" if target_only else "BerylIntegerOps"
        method = (TARGET_EXPORTS if target_only else EXPORTS)[case["method"]]
        lines.append(f'{check}("{case["id"]}", {receiver}.{method}({arguments}), {literal(case["expected"])});')
        if case["binding"]:
            lines.append(f'{check}("binding-{case["id"]}", Math.{case["binding"]}({arguments}), {literal(case["expected"])});')
    batches, calls = [], []
    for start in range(0, len(lines), 32):
        name = "Batch" + str(start // 32)
        calls.append(name + "();")
        batches.append("void " + name + "() {\n" + "\n".join(lines[start:start + 32]) + "\n}")
    text = (FIXTURES / "Comparison.c.in").read_text(encoding="utf-8")
    return text.replace("@TOKEN@", token).replace("@RUN@", "\n".join(calls)).replace("@BATCHES@", "\n\n".join(batches)), len(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--beryl", type=Path, required=True)
    parser.add_argument("--clang", type=Path, required=True)
    parser.add_argument("--workbench-tools", type=Path, required=True)
    parser.add_argument("--engine-version", default="1.8.0.13")
    args = parser.parse_args()
    path = Path(tempfile.mkdtemp(prefix="engine-integers-", dir=ROOT / "build"))
    job = mod.Job(path, "integer-verification", args.beryl.resolve(strict=True))
    print("Integer artifacts: " + str(path), flush=True)
    tracked = [FIXTURES / "operations.be", FIXTURES / "target_operations.be", FIXTURES / "Comparison.c.in",
               Path(__file__).resolve(), ROOT / "scripts/integer-engine-run.ps1"]
    hashes = {str(p.relative_to(ROOT)): mod.digest(mod.read(p)) for p in tracked}
    job.result.update(source_hashes=hashes, status="failure")
    try:
        inputs = path / "inputs"
        inputs.mkdir()
        (inputs / "operations.be").write_bytes(mod.read(FIXTURES / "operations.be"))
        (inputs / "target_operations.be").write_bytes(mod.read(FIXTURES / "target_operations.be"))
        data = cases()
        mod.write_json(path / "cases.json", data)
        checks = ["module engine.integer_tests", "use engine.integers.Ops", 'test "independent integer and finite-float fixtures" {']
        for case in data:
            if case.get("coverage") == "native_and_engine_only":
                continue
            arguments = ", ".join(literal(value, True) for value in case["args"])
            checks.append(f'assert(Ops.{case["method"]}({arguments}) == {literal(case["expected"], True)})')
        (inputs / "cases_test.be").write_text("\n".join(checks + ["}", ""]), encoding="utf-8")
        job.run([job.compiler, "test", "--backend", "differential", "--clang", args.clang.resolve(strict=True),
                 inputs / "operations.be", inputs / "cases_test.be"], "native_reference", inputs)
        target_checks = ["module engine.target_tests", "use engine.target_order.TargetOps", 'test "analytical target-only order fixtures" {']
        for case in data:
            if case.get("coverage") == "native_and_engine_only":
                arguments = ", ".join(literal(value, True) for value in case["args"])
                target_checks.append(f'assert(TargetOps.{case["method"]}({arguments}) == {literal(case["expected"], True)})')
        (inputs / "target_test.be").write_text("\n".join(target_checks + ["}", ""]), encoding="utf-8")
        job.run([job.compiler, "test", "--backend", "native", "--clang", args.clang.resolve(strict=True),
                 inputs / "target_operations.be", inputs / "target_test.be"], "native_analytical", inputs)
        addon = path / "addons/BerylIntegerComparison"
        scripts = addon / "scripts/Game"
        scripts.mkdir(parents=True)
        flags = ["--export-class", "engine.integers.Ops=BerylIntegerOps",
                 "--export-class", "engine.target_order.TargetOps=BerylTargetOps"]
        for source, target in EXPORTS.items():
            flags += ["--export-method", "engine.integers.Ops." + source + "=" + target]
        for source, target in TARGET_EXPORTS.items():
            flags += ["--export-method", "engine.target_order.TargetOps." + source + "=" + target]
        job.run([job.compiler, "build", "-t", "enfusion", "--prefix", "Beryl", "--out-dir", scripts,
                 *flags, inputs / "operations.be", inputs / "target_operations.be"], "enfusion_emit", inputs)
        generated = {str(p.relative_to(addon)): mod.digest(mod.read(p)) for p in scripts.rglob("*") if p.is_file()}
        token = mod.digest(mod.canonical({"compiler": job.result["compiler_sha256"], "source": hashes,
                                         "cases": data, "generated": generated}))
        (addon / "addon.gproj").write_text('GameProject {\n ID "BerylIntegerComparison"\n GUID "' + token[:16].upper() +
            '"\n TITLE "Beryl integer comparison"\n Dependencies {\n "58D0FB3206B6F859"\n }\n}\n', encoding="utf-8")
        handler = addon / "scripts/WorkbenchGameCommon/BerylIntegerComparison.c"
        handler.parent.mkdir()
        text, count = harness(data, token)
        handler.write_text(text, encoding="utf-8", newline="\n")
        artifact_files = {str(p.relative_to(addon)): mod.digest(mod.read(p)) for p in addon.rglob("*") if p.is_file()}
        job.result.update(token=token, cases=len(data), expected_checks=count, artifact_files=artifact_files,
            reference_cases=[case["id"] for case in data if case.get("coverage") != "native_and_engine_only"],
            native_engine_only_cases=[case["id"] for case in data if case.get("coverage") == "native_and_engine_only"])
        toolroot = args.workbench_tools.resolve(strict=True)
        job.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", ROOT / "tools/beryl-mod/engine-compile.ps1",
                 "-ToolRoot", toolroot, "-ProjectDir", addon, "-ResultPath", path / "engine-compile.json",
                 "-ExpectedVersion", args.engine_version], "workbench_compile", path, 300)
        job.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", ROOT / "scripts/integer-engine-run.ps1",
                 "-ToolRoot", toolroot, "-ProjectDir", addon, "-ResultPath", path / "engine-runtime.json", "-Token", token,
                 "-ExpectedChecks", str(count)], "engine_execution", path, 300)
        if any(mod.digest(mod.read(addon / name)) != value for name, value in artifact_files.items()):
            raise mod.Failure("Staged source changed during verification", "stale_input")
        if any(mod.digest(mod.read(ROOT / name)) != value for name, value in hashes.items()):
            raise mod.Failure("Fixture source changed during verification", "stale_input")
        if mod.digest(mod.read(job.compiler)) != job.result["compiler_sha256"]:
            raise mod.Failure("Compiler changed during verification", "stale_input")
        job.result.update(status="success", engine=mod.parse(mod.read(path / "engine-runtime.json")))
        print(f"Passed {len(data)} fixtures and {count} engine checks", flush=True)
    except (Exception, KeyboardInterrupt) as exc:
        job.result.update(status=getattr(exc, "status", "failure"), failure=str(exc))
        raise
    finally:
        mod.write_json(path / "result.json", job.result)
        print("Evidence: " + str(path / "result.json"), flush=True)


if __name__ == "__main__":
    main()
