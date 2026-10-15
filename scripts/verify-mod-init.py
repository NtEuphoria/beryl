#!/usr/bin/env python3
"""Focused mod-init regressions; compiler execution requires explicit --beryl/--clang."""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from unittest import mock

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools/beryl-mod"))
import mod

PURE_CASES = (
    "render.deterministic", "render.admission", "render.shared-implementation", "render.dependencies",
    "render.shared-engine-name-policy", "reject.engine-name-prefix",
    "reject.template", "reject.name-empty", "reject.name-newline", "reject.name-unicode",
    "reject.addon-id", "reject.generated-name-length", "reject.guid", "reject.duplicate-dependency",
    "reject.self-dependency", "reject.dependency-limit", "create.exact-files",
    "create.path-metacharacters", "reject.existing-empty", "reject.existing-populated", "reject.existing-file",
    "reject.missing-parent", "reject.traversal", "reject.linked-ancestor",
    "failure.partial-write-retained", "failure.cancelled", "failure.short-write", "failure.tool-changed",
    "cli.init-no-execution", "cli.required-options", "cli.execution-options", "cli.empty-execution-options", "cli.init-options-on-check",
    "cli.unknown-option", "cli.failure-retains-partial",
)
INTEGRATION_CASES = (
    "cli.actual-init", "cli.semantic-check", "cli.immutable-build",
    "execute.reference", "execute.native", "execute.differential", "execute.implementation-mutant",
    "cli.version2-boundaries",
)
DEFAULTS = ("scalar-component", "Scalar starter", "ScalarStarter", "DA00000000000015", [])
TEST_NAMES = (
    "default state is inactive", "initialization resets state", "active frame records binary32 input",
    "inactive frame leaves state unchanged", "deletion stops later frame updates",
    "reinitialization starts a fresh state",
)


def check(condition, message):
    if not condition:
        raise AssertionError(message)


def tree(root):
    return {str(p.relative_to(root)).replace("\\", "/"): mod.digest(p.read_bytes())
            for p in sorted(root.rglob("*")) if p.is_file()}


def expect_failure(fn, status="failure"):
    try:
        fn()
    except (mod.Failure, OSError) as exc:
        check(getattr(exc, "status", "failure") == status, str(exc))
        return exc
    raise AssertionError("Expected failure was accepted")


def run_main(arguments):
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        code = mod.main(arguments)
    value = json.loads(output.getvalue())
    check((code == 0) == (value["status"] == "success"), value)
    return code, value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--beryl", type=Path)
    parser.add_argument("--clang", type=Path)
    parser.add_argument("--expect-compiler-sha256")
    args = parser.parse_args()
    integration = args.beryl is not None
    if integration != (args.clang is not None) or integration != (args.expect_compiler_sha256 is not None):
        parser.error("Integration requires --beryl, --clang and --expect-compiler-sha256 together")
    work = Path(tempfile.mkdtemp(prefix="mod-init-", dir=ROOT / "build"))
    record = {"schema_version": 1, "status": "failure", "scope": "source scaffold and explicit compiler modes only",
              "engine_execution": "not_run", "cases": [], "commands": []}
    expected = list(PURE_CASES + (INTEGRATION_CASES if integration else ()))
    check(expected and len(expected) == len(set(expected)), "Invalid case inventory")
    record["expected_case_ids"] = expected
    record["input_hashes"] = {str(p): mod.digest(mod.read(p))
                              for p in [Path(__file__).resolve(), *mod.bundle_paths()]}
    fake = work / "identity-only-compiler.bin"
    fake.write_bytes(b"nonexecutable identity fixture; no process may use this\n")

    def case(name, fn):
        check(name in expected and name not in [c["case_id"] for c in record["cases"]], name)
        try:
            fn()
        except BaseException as exc:
            record["cases"].append({"case_id": name, "status": "failure", "error": repr(exc)})
            raise
        record["cases"].append({"case_id": name, "status": "success"})

    def rendered(*values):
        return mod.init_files(*(values or DEFAULTS))

    def init(path, *values):
        return mod.init_project(path, fake, *(values or DEFAULTS))

    def rejection(index, value):
        values = list(DEFAULTS)
        values[index] = value
        expect_failure(lambda: rendered(*values))

    def cli_args(target):
        return ["init", "--beryl", str(fake), "--project", str(target), "--template", DEFAULTS[0],
                "--name", DEFAULTS[1], "--addon-id", DEFAULTS[2], "--addon-guid", DEFAULTS[3]]

    try:
        first, files = rendered()
        case("render.deterministic", lambda: check(rendered() == (first, files), "Nondeterministic bytes"))
        def admission():
            schema = mod.parse(mod.read(mod.COMPONENT_SCHEMA))
            mod.validate(first, schema, schema)
            _, summary = mod.component_admission(first)
            check(summary and first["schema_version"] == 2 and first["exports"] == [], "Wrong admitted scope")
            check(set(files) == set(mod.INIT_FILES) and len(files) == 4, "Wrong files")
            check(all(b.endswith(b"\n") and b"\r" not in b for b in files.values()), "Noncanonical newlines")
        case("render.admission", admission)
        def shared():
            text = files["tests/component_test.be"].decode()
            check(tuple(re.findall(r'^test "([^"]+)"', text, re.M)) == TEST_NAMES, "Wrong real test inventory")
            check(text.count("assert(") == 13 and text.count("(inout state") == 13 and "pub struct" not in text and "fn on_" not in text,
                  "Tests duplicate implementation or omit expected assertions")
            for symbol in ("State", "on_init", "on_frame", "on_delete"):
                check("use starter.component." + symbol + "\n" in text, "Missing import " + symbol)
        case("render.shared-implementation", shared)
        case("render.dependencies", lambda: check(
            rendered(*DEFAULTS[:-1], ["58D0FB3206B6F859", "DA00000000000016"])[0]["addon"]["dependencies"]
            == ["58D0FB3206B6F859", "DA00000000000016"], "Dependency order changed"))
        def shared_engine_name_policy():
            import component_generation
            actual = component_generation.validate_engine_name
            with mock.patch.object(component_generation, "validate_engine_name", wraps=actual) as guarded:
                accepted, _ = rendered()
            expected_names = [(("ScalarStarterComponentClass", "/components/0/descriptor/name"), {}),
                              (("ScalarStarterComponent", "/components/0/instance/name"), {})]
            check([(call.args, call.kwargs) for call in guarded.call_args_list] == expected_names,
                  "Init bypasses common generated-name policy")
            check(accepted["components"][0]["instance"]["name"] == "ScalarStarterComponent",
                  "Ordinary nonreserved name rejected")
            for reserved in ("class", "ScriptComponent", "BerylGenerated", "bErYlGenerated"):
                try:
                    actual(reserved, "/engine/name")
                except component_generation.contracts.ContractFailure as exc:
                    check(exc.status == "failure" and exc.pointer == "/engine/name", str(exc))
                else:
                    raise AssertionError("Public generator policy accepted a reserved identifier")
        case("render.shared-engine-name-policy", shared_engine_name_policy)
        def reserved_engine_prefix():
            for index, addon_id in enumerate(("BerylScalarDemo", "bErYlScalarDemo", "beryl", "BERYL")):
                target = work / ("reserved-engine-name-" + str(index))
                values = list(DEFAULTS)
                values[2] = addon_id
                error = expect_failure(lambda: init(target, *values))
                check(error.pointer == "/components/0/descriptor/name", "Missing repair location")
                check(not target.exists(), "Reserved engine name created a project")
        case("reject.engine-name-prefix", reserved_engine_prefix)
        for name, index, value in (
            ("reject.template", 0, "../../script.py"),
            ("reject.name-empty", 1, ""), ("reject.name-newline", 1, "line\nbreak"),
            ("reject.name-unicode", 1, "\u00e9"), ("reject.addon-id", 2, "Bad-ID"),
            ("reject.generated-name-length", 2, "A" * 120), ("reject.guid", 3, "da00000000000015"),
            ("reject.duplicate-dependency", 4, ["DA00000000000016"] * 2),
            ("reject.self-dependency", 4, [DEFAULTS[3]]),
            ("reject.dependency-limit", 4, [format(i, "016X") for i in range(65)]),
        ):
            case(name, lambda i=index, v=value: rejection(i, v))
        def created():
            target = work / "created"
            with mock.patch.object(mod.Job, "__init__", side_effect=AssertionError("Job ran")), \
                 mock.patch.object(subprocess, "Popen", side_effect=AssertionError("Process ran")):
                result = init(target)
            check(result["status"] == "success" and result["execution"] == "not_run", result)
            check(result["created_files"] == list(mod.INIT_FILES) and tree(target) == result["files"], result)
            check(result["source_sha256"] == mod.digest(mod.canonical(tree(target))), result)
            check(set(result["verification"].values()) == {"not_run"} and not result["raw_logs"], result)
            config, contents, _ = mod.description_snapshot(target)
            check(config == first and set(contents) == set(files) - {"README.md"}, "Invalid source snapshot")
        case("create.exact-files", created)
        case("create.path-metacharacters", lambda: check(
            init(work / "space & (literal) $dollar;")["status"] == "success", "Literal path rejected"))
        for name, setup in (
            ("reject.existing-empty", lambda p: p.mkdir()),
            ("reject.existing-populated", lambda p: (p.mkdir(), (p / "keep.txt").write_bytes(b"keep"))),
            ("reject.existing-file", lambda p: p.write_bytes(b"keep")),
        ):
            def existing(n=name, make=setup):
                target = work / n
                make(target)
                before = tree(work)
                expect_failure(lambda: init(target))
                check(tree(work) == before, "Existing data changed")
            case(name, existing)
        case("reject.missing-parent", lambda: expect_failure(lambda: init(work / "absent-parent/child")))
        case("reject.traversal", lambda: expect_failure(lambda: init(work / "../traversal")))
        def linked():
            target = work / "linked-child"
            actual = Path.is_symlink
            with mock.patch.object(Path, "is_symlink", lambda p: p == work or actual(p)):
                expect_failure(lambda: init(target))
            check(not target.exists(), "Linked ancestor created output")
        case("reject.linked-ancestor", linked)
        actual_open = Path.open
        def denied_open(path, *a, **kw):
            if path.name == "component.be" and a and a[0] == "xb":
                raise PermissionError("injected exclusive write failure")
            return actual_open(path, *a, **kw)
        def partial():
            target = work / "partial"
            with mock.patch.object(Path, "open", denied_open):
                error = expect_failure(lambda: init(target))
            result = error.initialization
            check(result["destination_created"] and result["partial_project"] == str(target), result)
            check(result["created_files"] == ["beryl.mod.json"], result)
            check((target / "beryl.mod.json").read_bytes() == files["beryl.mod.json"], "Lost owned prefix")
            check(not (target / "README.md").exists(), "Continued after failed write")
        case("failure.partial-write-retained", partial)
        def cancelled():
            target = work / "cancelled"
            def interrupted(p, *a, **kw):
                if p.name == "component.be" and a and a[0] == "xb":
                    raise KeyboardInterrupt()
                return actual_open(p, *a, **kw)
            with mock.patch.object(Path, "open", interrupted):
                code, value = run_main(cli_args(target))
            check(code != 0 and value["status"] == "cancelled" and
                  value["partial_project"] == str(target) and
                  value["created_files"] == ["beryl.mod.json"], value)
            check((target / "beryl.mod.json").read_bytes() == files["beryl.mod.json"] and
                  not (target / "README.md").exists(), "Cancellation lost prefix or continued")
        case("failure.cancelled", cancelled)
        class ShortWriter:
            def __init__(self, stream): self.stream = stream
            def __enter__(self): self.stream.__enter__(); return self
            def __exit__(self, *values): return self.stream.__exit__(*values)
            def write(self, data): return self.stream.write(data[:-1])
            def flush(self): return self.stream.flush()
            def fileno(self): return self.stream.fileno()
        def short_write():
            target = work / "short"
            def opened(p, *a, **kw):
                stream = actual_open(p, *a, **kw)
                return ShortWriter(stream) if p.name == "beryl.mod.json" and a and a[0] == "xb" else stream
            with mock.patch.object(Path, "open", opened):
                error = expect_failure(lambda: init(target))
            check(error.initialization["destination_created"] and not (target / "src").exists(), "Short write continued")
        case("failure.short-write", short_write)
        def changed_tool():
            with mock.patch.object(mod, "tool_identity", side_effect=["1" * 64, "2" * 64]):
                error = expect_failure(lambda: init(work / "changed-tool"), "stale_input")
            check(error.initialization["created_files"] == list(mod.INIT_FILES), "Completed bytes not retained")
        case("failure.tool-changed", changed_tool)
        def cli_no_execution():
            with mock.patch.object(mod.Job, "__init__", side_effect=AssertionError("Job ran")), \
                 mock.patch.object(subprocess, "Popen", side_effect=AssertionError("Process ran")):
                code, value = run_main(cli_args(work / "cli"))
            check(code == 0 and value["operation"] == "mod init" and value["execution"] == "not_run", value)
        case("cli.init-no-execution", cli_no_execution)
        def cli_negative(arguments, target):
            before = tree(work)
            code, value = run_main(arguments)
            check(code != 0 and value["status"] == "failure" and not target.exists(), value)
            check(tree(work) == before, "Rejected CLI request wrote files")
        target = work / "bad-cli"
        case("cli.required-options", lambda: cli_negative(cli_args(target)[:-2], target))
        case("cli.execution-options", lambda: cli_negative(cli_args(target) + ["--artifact", "bad"], target))
        def empty_execution_options():
            for option in ("--artifact", "--scenario", "--destination", "--workbench-tools"):
                cli_negative(cli_args(target) + [option, ""], target)
        case("cli.empty-execution-options", empty_execution_options)
        case("cli.init-options-on-check", lambda: cli_negative(
            ["check", "--beryl", str(fake), "--project", str(target), "--template", DEFAULTS[0]], target))
        case("cli.unknown-option", lambda: cli_negative(cli_args(target) + ["--shell", "bad"], target))
        def cli_partial():
            target = work / "cli-partial"
            with mock.patch.object(Path, "open", denied_open):
                code, value = run_main(cli_args(target))
            check(code != 0 and value["partial_project"] == str(target) and value["created_files"] == ["beryl.mod.json"], value)
        case("cli.failure-retains-partial", cli_partial)

        if integration:
            compiler, clang = args.beryl.resolve(strict=True), args.clang.resolve(strict=True)
            check(mod.digest(mod.read(compiler)) == args.expect_compiler_sha256, "Wrong compiler identity")
            record["compiler_sha256"] = args.expect_compiler_sha256
            record["clang_sha256"] = mod.digest(mod.read(clang))
            project = work / "actual starter & spaces"
            env = os.environ.copy()
            env.update(BERYL_MOD_TOOL=str(ROOT / "tools/beryl-mod/mod.py"), BERYL_PYTHON=sys.executable)
            env["PATH"] = str(clang.parent) + os.pathsep + env.get("PATH", "")
            def run(arguments, cwd, expected_code=0):
                argv = [str(x) for x in arguments]
                row = {"argv": argv, "cwd": str(cwd), "status": "startup_failure"}
                record["commands"].append(row)
                try:
                    proc = subprocess.run(argv, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
                except subprocess.TimeoutExpired:
                    row["status"] = "timeout"
                    raise
                stem = work / ("command-" + str(len(record["commands"])).zfill(3))
                for suffix, data in (("stdout", proc.stdout), ("stderr", proc.stderr)):
                    path = Path(str(stem) + "." + suffix + ".log")
                    path.write_bytes(data)
                    row[suffix + "_path"] = str(path)
                    row[suffix + "_sha256"] = mod.digest(data)
                row.update(status="exited", exit_code=proc.returncode)
                check((proc.returncode == 0) == (expected_code == 0), row)
                return proc
            def invoke(command, *extras, success=True):
                proc = run([compiler, "mod", command, "--project", project, *extras], work,
                           0 if success else 1)
                value = mod.parse(proc.stdout)
                check((value["status"] == "success") == success, value)
                return value
            def actual_init():
                value = invoke("init", "--template", DEFAULTS[0], "--name", DEFAULTS[1],
                               "--addon-id", DEFAULTS[2], "--addon-guid", DEFAULTS[3])
                check(tree(project) == value["files"] and value["execution"] == "not_run", value)
            case("cli.actual-init", actual_init)
            case("cli.semantic-check", lambda: check(
                invoke("check")["component_symbol_admission"]["status"] == "admitted_signatures",
                "Starter signatures not admitted"))
            def actual_build():
                built = invoke("build")
                artifact = Path(built["artifact_path"])
                manifest = mod.parse(mod.read(artifact / "artifact.json"))
                check(manifest["artifact_sha256"] == built["artifact_sha256"], "Artifact identity mismatch")
                generated = mod.read(artifact / "addon/scripts/Game/Beryl/Beryl_Generated.c")
                source_map = mod.parse(mod.read(artifact / "source-map.json"))
                check(b"class ScalarStarterComponentClass : ScriptComponentClass" in generated and
                      b"class ScalarStarterComponent : ScriptComponent" in generated, "Missing wrappers")
                check(source_map["generated"]["sha256"] == mod.digest(generated) and
                      any(m["kind"] == "component_handler" for m in source_map["mappings"]), "Missing mapped origins")
                check(built["component_generation"]["runtime_verification"] == "not_run", "Invented runtime claim")
                record["artifact_sha256"] = built["artifact_sha256"]
            case("cli.immutable-build", actual_build)
            def execute(backend, success=True):
                before = set((project / ".beryl-cache").glob("job-*"))
                proc = run([compiler, "test", "--backend", backend, "--clang", clang,
                            "src/component.be", "tests/component_test.be"], project, 0 if success else 1)
                fresh = set((project / ".beryl-cache").glob("job-*")) - before
                check(len(fresh) == 1, "Missing or ambiguous execution receipt")
                job = fresh.pop()
                result = mod.parse(mod.read(job / "result.json"))
                if backend in ("reference", "differential") and success:
                    check(result["status"] == result["reference_status"] == "success" and
                          result["tests"] == 6 and result["assertions"] == 13, result)
                    events = [json.loads(line) for line in (job / "reference.events.jsonl").read_text().splitlines()]
                    check(sum(e["event"] == "test_begin" for e in events) == 6 and
                          sum(e["event"] == "test_end" for e in events) == 6, "Incomplete executed cases")
                    if backend == "differential":
                        check(result["compared"] and result["native_status"] == "exited", result)
                elif not success:
                    check(result["status"] != "success" and result.get("reference_status") == "failure", result)
                else:
                    check(b"ok  6 tests, 13 assertions\n" in proc.stdout.replace(b"\r\n", b"\n"),
                          "Native result did not confirm six tests and 13 assertions")
                record.setdefault("execution_receipts", []).append(str(job / "result.json"))
            for backend in ("reference", "native", "differential"):
                case("execute." + backend, lambda b=backend: execute(b))
            def mutant():
                source = project / "src/component.be"
                original = source.read_bytes()
                mutated = original.replace(b"state.last_delta = time_slice", b"state.last_delta = 0.0f32")
                check(mutated != original, "Mutation was not applied")
                source.write_bytes(mutated)
                try:
                    execute("reference", success=False)
                finally:
                    source.write_bytes(original)
            case("execute.implementation-mutant", mutant)
            def unavailable():
                for operation, extras in (("verify", ("--stage", "compile", "--artifact", "a" * 32)),
                                          ("promote", ("--artifact", "a" * 32, "--destination", str(work / "never-promoted")))):
                    value = invoke(operation, *extras, success=False)
                    check(value["status"] == "unavailable", value)
                check(not (work / "never-promoted").exists(), "Unexpected promotion")
            case("cli.version2-boundaries", unavailable)

        check([r["case_id"] for r in record["cases"]] == expected, "Missing, duplicate or reordered cases")
        check(all(c["status"] == "success" for c in record["cases"]), "Failed cases")
        check(record["input_hashes"] == {p: mod.digest(mod.read(p)) for p in record["input_hashes"]},
              "Source changed during verification")
        record.update(status="success", passed=len(record["cases"]), expected=len(expected))
    except BaseException as exc:
        record["error"] = repr(exc)
        raise
    finally:
        mod.write_json(work / "results.json", record)
        print(json.dumps({"status": record["status"], "passed": sum(c["status"] == "success" for c in record["cases"]),
                          "expected": len(expected), "receipt": str(work / "results.json")}), flush=True)


if __name__ == "__main__":
    main()
