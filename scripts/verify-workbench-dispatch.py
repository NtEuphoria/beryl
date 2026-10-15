#!/usr/bin/env python3
"""Prepare by default; --run alone authorizes the isolated engine experiment."""
from pathlib import Path
import argparse
import copy
import importlib.util
import json
import re
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "packages/sparkos/workbench-dispatch-probe"
TRANSPORT = ROOT / "scripts/workbench-dispatch-engine.ps1"
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / "tools/beryl-mod"))
import mod


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


helper = load("dispatch_retained_helpers", ROOT / "scripts/verify-component-state.py")
require, write, identity = helper.require, helper.write, helper.identity
files, directories, save_result = helper.files, helper.directories, helper.save_result
CASE_IDS = ("dispatch.identity", "dispatch.arm", "dispatch.submit", "dispatch.entered", "dispatch.resumed", "dispatch.health-after")
PROFILE = "workbench-game.harmless-direct-thread.v1"
PLUGIN_FILES = ("Find-Workbench.ps1", "Invoke-ReforgerBuild.ps1", "Invoke-Workbench.ps1", "Get-WorkbenchErrors.ps1", "Start-WorkbenchDaemon.ps1", "Invoke-WorkbenchRpc.ps1")
COMPILE_FILES = PLUGIN_FILES[:4]
RUNTIME_FILES = (PLUGIN_FILES[0], PLUGIN_FILES[4], PLUGIN_FILES[5])
BOOLS = ("wb_module_present", "game_module_present")
COUNTERS = ("phase", "armed", "submitted", "entered", "resumed", "after_thread", "sequence", "arm_sequence", "enter_sequence", "after_sequence", "resume_sequence")
FIELDS = {"token", "action", "status", "failure", *BOOLS, *COUNTERS}
HASH = re.compile(r"[0-9a-f]{64}")


def compile_success(value, engine, plugin_hashes):
    """One predicate for the admission gate and its final evidence classification."""
    if type(value) is not dict or type(value.get("result")) is not dict or type(engine) is not dict:
        return False
    detail = value["result"]
    return (type(value.get("schema_version")) is int and value["schema_version"] == 1 and
            value.get("status") == "success" and value.get("stage") == "workbench_compile" and
            value.get("engine_sha256") == engine["sha256"] and value.get("engine_version") == engine["version"] and
            value.get("tools") == {name: plugin_hashes[name] for name in COMPILE_FILES} and
            detail.get("Ok") is True and detail.get("Stage") == "Compiled" and
            type(detail.get("ExitCode")) is int and detail["ExitCode"] == 0 and
            type(detail.get("ErrorCount")) is int and detail["ErrorCount"] == 0)


def compile_outcome(value, engine, plugin_hashes):
    if compile_success(value, engine, plugin_hashes):
        return "executed_success"
    detail = value.get("result") if type(value) is dict else None
    if type(detail) is dict and detail.get("Stage") == "Compiled":
        if detail.get("Ok") is False or (type(detail.get("ExitCode")) is int and detail["ExitCode"] != 0) or (
                type(detail.get("ErrorCount")) is int and detail["ErrorCount"] != 0):
            return "executed_failure"
        return "executed_unverified"
    return "attempted_unconfirmed"


def decode(value):
    require(type(value) is dict and set(value) == FIELDS, "Unknown or missing wire fields")
    result = copy.deepcopy(value)
    codec = {"schema_version": 1, "name": "enfusion.jsonapistruct.bool01.v1", "numeric_boolean_fields": []}
    for name in BOOLS:
        item = value[name]
        if type(item) is int and item in (0, 1):
            result[name] = bool(item)
            codec["numeric_boolean_fields"].append(name)
        else:
            require(type(item) is bool, "Invalid Boolean wire field: " + name)
    for name in COUNTERS:
        require(type(value[name]) is int and 0 <= value[name] <= 4, "Invalid wire counter: " + name)
    for name in ("token", "action", "status", "failure"):
        require(type(value[name]) is str and len(value[name]) <= 512, "Invalid wire string: " + name)
    require(value["status"] in {"pending", "complete", "failure", "unavailable"}, "Unknown response status")
    return result, codec


def validate(value, token, action, complete=False):
    require(value["token"] == token and value["action"] == action, "Wrong token/action", "stale_input")
    require(value["failure"] == "" and value["game_module_present"] is True, "Unavailable or failed native sentinel")
    require(value["armed"] == value["submitted"] == value["after_thread"] == 1 and value["arm_sequence"] == 1,
            "Missing arm/after-thread/submission")
    if complete:
        require(value["status"] == "complete" and value["phase"] == 3 and value["entered"] == value["resumed"] == 1 and
                value["sequence"] == value["resume_sequence"] == 4 and
                sorted((value["enter_sequence"], value["after_sequence"])) == [2, 3], "Incomplete native completion/order")
    else:
        require(value["status"] == "pending" and value["phase"] in (1, 2) and value["resumed"] == value["resume_sequence"] == 0,
                "Arm was not a before-completion snapshot")
        require(value["entered"] in (0, 1) and value["sequence"] == 2 + value["entered"] and
                ((value["entered"] == 0 and value["phase"] == 1 and value["enter_sequence"] == 0 and value["after_sequence"] == 2) or
                 (value["entered"] == 1 and value["phase"] == 2 and sorted((value["enter_sequence"], value["after_sequence"])) == [2, 3])),
                "Invalid arm prefix/order")


def verify_runtime(runtime, token, addon, engine, plugin_hashes):
    require(type(runtime) is dict and type(runtime.get("schema_version")) is int and runtime["schema_version"] == 1 and
            runtime.get("status") == "success" and runtime.get("stage") == "dispatch_transport_complete" and
            runtime.get("profile") == PROFILE and runtime.get("token") == token and runtime.get("function") == "BerylWorkbenchDispatch",
            "Missing successful exact runtime adapter receipt")
    require(runtime.get("engine_sha256") == engine["sha256"] and runtime.get("engine_version") == engine["version"] and
            runtime.get("tools") == {name: plugin_hashes[name] for name in RUNTIME_FILES}, "Engine/plugin runtime identity differs", "stale_input")
    session, loaded = runtime.get("session"), runtime.get("loaded_projects")
    require(type(session) is dict and session.get("reused") is False and session.get("project") == str(addon) and
            type(session.get("process_id")) is int and session["process_id"] > 0 and type(session.get("start_ticks")) is int and session["start_ticks"] > 0 and
            session.get("executable", "").replace("\\", "/").casefold() == engine["path"].replace("\\", "/").casefold(), "Missing owned session identity")
    require(type(loaded) is dict and loaded.get("Ok") is True and loaded.get("Function") == "GetLoadedProjects" and
            type(loaded.get("Raw")) is str and len(loaded["Raw"]) <= 65536 and type(loaded.get("Response")) is dict and
            mod.parse(loaded["Raw"].encode()) == loaded["Response"] and
            type(loaded["Response"].get("Loaded Projects")) is list and "BerylWorkbenchDispatchProbe" in loaded["Response"]["Loaded Projects"],
            "Incomplete raw loaded-project receipt")
    require(runtime.get("cleanup") in {"owned_process_stopped", "owned_process_already_exited"} and
            type(runtime.get("evidence_errors")) is list and runtime["evidence_errors"] == [] and
            type(runtime.get("raw_logs")) is list and 1 <= len(runtime["raw_logs"]) <= 4096, "Incomplete cleanup/log evidence")
    calls = runtime.get("rpcs")
    require(type(calls) is list and 2 <= len(calls) <= 65 and all(type(call) is dict for call in calls) and calls[0].get("action") == "arm" and
            all(call.get("action") == "status" for call in calls[1:]), "Wrong actual RPC set")
    elapsed = runtime.get("elapsed_ms")
    require(type(elapsed) is int and 0 <= elapsed < 180000, "Missing bounded runtime elapsed time")
    checks = runtime.get("session_checks")
    sites = ["startup.complete", "loaded.complete"]
    for call in calls:
        sites.extend(("before." + call["action"], "after." + call["action"]))
    sites.append("sentinel.complete")
    require(type(checks) is list and len(checks) == len(sites), "Missing exact session-check set")
    prior_elapsed = 0
    for check, site in zip(checks, sites):
        require(type(check) is dict and set(check) == {"site", "process_id", "start_ticks", "executable", "elapsed_ms"} and
                check["site"] == site and type(check["process_id"]) is int and check["process_id"] == session["process_id"] and
                type(check["start_ticks"]) is int and check["start_ticks"] == session["start_ticks"] and
                check["executable"] == session["executable"] and type(check["elapsed_ms"]) is int and
                prior_elapsed <= check["elapsed_ms"] <= elapsed, "Missing, stale or unordered process check")
        prior_elapsed = check["elapsed_ms"]
    decoded = []
    for index, call in enumerate(calls):
        before, after = checks[2 + index * 2], checks[3 + index * 2]
        require(type(call.get("elapsed_ms")) is int and before["elapsed_ms"] <= call["elapsed_ms"] <= after["elapsed_ms"] and
                type(call.get("timeout_ms")) is int and 1 <= call["timeout_ms"] <= 8000 and call.get("failure") is None,
                "Incomplete bounded RPC attempt")
        reply = call.get("result")
        require(type(reply) is dict and reply.get("Ok") is True and reply.get("Function") == "BerylWorkbenchDispatch" and
                type(reply.get("Raw")) is str and len(reply["Raw"]) <= 65536 and mod.parse(reply["Raw"].encode()) == reply.get("Response"),
                "Raw RPC differs from parsed response")
        response, codec = decode(reply["Response"])
        require(call.get("normalized_response") == response and call.get("codec") == codec,
                "Stored normalization differs from independent decoder")
        require(response["token"] == token and response["action"] == call["action"] and response["failure"] == "" and
                response["status"] in {"pending", "complete"}, "Failed/stale intermediate RPC")
        decoded.append(response)
    validate(decoded[0], token, "arm")
    validate(decoded[-1], token, "status", True)
    require(runtime.get("completion") == decoded[-1], "Completion differs from actual final RPC")
    prior = decoded[0]
    for response in decoded[1:]:
        require(response["armed"] == response["submitted"] == response["after_thread"] == 1 and
                response["sequence"] >= prior["sequence"] and response["entered"] >= prior["entered"] and response["resumed"] >= prior["resumed"],
                "Counter reset or reversed observation")
        prior = response
        if response["status"] == "pending":
            validate(response, token, "status")
        else:
            validate(response, token, "status", True)
    return {"expected_case_ids": list(CASE_IDS), "completed_case_ids": list(CASE_IDS), "complete_expected_case_set": True,
            "arm_snapshot": decoded[0], "completion_snapshot": decoded[-1], "rpc_count": len(calls),
            "scope": "GameCommon same-module worker; transport-send order, Workbench-only dispatch and native open not established"}


def self_test():
    # Register every case before executing any test; no derived expected list.
    ids = ("wire-bool", "wire-bool01", "arm-not-entered", "arm-entered", "complete-order-one", "complete-order-two",
           "reject-unknown", "reject-missing", "reject-bool-string", "reject-bool-float", "reject-bool-two", "reject-counter-bool",
           "reject-token", "reject-arm-complete", "reject-entry-zero", "reject-resume-zero", "reject-duplicate-sequence",
           "reject-reset", "reject-game-unavailable", "reject-source-failure", "raw-not-mutated",
           "compile-valid", "compile-errors", "compile-adapter-failure", "compile-schema-bool", "compile-exit-bool",
           "compile-errorcount-bool", "compile-wrong-engine", "compile-wrong-plugin", "compile-missing-result",
           "runtime-valid", "runtime-missing-errors", "runtime-reused-session", "runtime-missing-session-check",
           "runtime-wrong-session-check", "runtime-reversed-time", "runtime-wrong-site", "runtime-unconfirmed-cleanup",
           "runtime-missing-logs", "runtime-raw-mismatch", "runtime-codec-mismatch", "runtime-wrong-completion",
           "runtime-game-unavailable", "runtime-wrong-plugin", "runtime-rpc-timeout-bool", "runtime-schema-bool")
    token = "a" * 64
    base = {"token": token, "action": "status", "status": "complete", "failure": "", "wb_module_present": True, "game_module_present": True,
            "phase": 3, "armed": 1, "submitted": 1, "entered": 1, "resumed": 1, "after_thread": 1,
            "sequence": 4, "arm_sequence": 1, "enter_sequence": 2, "after_sequence": 3, "resume_sequence": 4}
    results = []
    def execute(case, operation, reject=False):
        try:
            operation()
        except mod.Failure as exc:
            require(reject, "Unexpected self-test failure: " + case)
            results.append({"id": case, "status": "rejected", "diagnostic": str(exc)})
        else:
            require(not reject, "Malformed receipt accepted: " + case)
            results.append({"id": case, "status": "passed"})
    execute(ids[0], lambda: decode(base))
    wire = copy.deepcopy(base)
    for name in BOOLS: wire[name] = int(wire[name])
    execute(ids[1], lambda: require(decode(wire)[0] == base, "Boolean normalization differs"))
    arm = {**base, "action": "arm", "status": "pending", "phase": 1, "entered": 0, "resumed": 0, "sequence": 2, "enter_sequence": 0, "after_sequence": 2, "resume_sequence": 0}
    execute(ids[2], lambda: validate(arm, token, "arm"))
    execute(ids[3], lambda: validate({**arm, "phase": 2, "entered": 1, "sequence": 3, "enter_sequence": 2, "after_sequence": 3}, token, "arm"))
    execute(ids[4], lambda: validate(base, token, "status", True))
    execute(ids[5], lambda: validate({**base, "enter_sequence": 3, "after_sequence": 2}, token, "status", True))
    mutations = [("extra", 0), ("phase", None), ("wb_module_present", "1"), ("wb_module_present", 1.0), ("wb_module_present", 2), ("entered", True),
                 ("token", "b"*64), ("action", "arm"), ("entered", 0), ("resumed", 0), ("after_sequence", 2), ("armed", 0),
                 ("game_module_present", False), ("failure", "actual failure")]
    for case, (name, value) in zip(ids[6:20], mutations):
        bad = copy.deepcopy(base)
        if value is None: bad.pop(name)
        else: bad[name] = value
        if case == "reject-arm-complete":
            execute(case, lambda bad=bad: (lambda pair: validate(pair[0], token, "arm"))(decode(bad)), True)
        else:
            execute(case, lambda bad=bad: (lambda pair: validate(pair[0], token, "status", True))(decode(bad)), True)
    before = copy.deepcopy(wire)
    execute(ids[20], lambda: (decode(wire), require(wire == before, "Raw wire mutated")))

    engine = {"path": "C:/fixture/Workbench.exe", "sha256": "e" * 64, "version": "1.0.fixture"}
    plugin = {name: "f" * 64 for name in PLUGIN_FILES}
    compiled = {"schema_version": 1, "status": "success", "stage": "workbench_compile", "engine_sha256": engine["sha256"],
                "engine_version": engine["version"], "tools": {name: plugin[name] for name in COMPILE_FILES},
                "result": {"Ok": True, "Stage": "Compiled", "ExitCode": 0, "ErrorCount": 0}}
    execute("compile-valid", lambda: require(compile_success(compiled, engine, plugin) and
            compile_outcome(compiled, engine, plugin) == "executed_success", "Valid compilation not admitted"))
    compile_mutants = (
        ("compile-errors", ("result", "ErrorCount"), 1, "executed_failure"),
        ("compile-adapter-failure", ("status",), "failure", "executed_unverified"),
        ("compile-schema-bool", ("schema_version",), True, "executed_unverified"),
        ("compile-exit-bool", ("result", "ExitCode"), False, "executed_unverified"),
        ("compile-errorcount-bool", ("result", "ErrorCount"), False, "executed_unverified"),
        ("compile-wrong-engine", ("engine_sha256",), "0" * 64, "executed_unverified"),
        ("compile-wrong-plugin", ("tools", "Find-Workbench.ps1"), "0" * 64, "executed_unverified"),
        ("compile-missing-result", ("result",), None, "attempted_unconfirmed"),
    )
    for case, path, value, expected in compile_mutants:
        bad = copy.deepcopy(compiled)
        target = bad
        for name in path[:-1]: target = target[name]
        target[path[-1]] = value
        execute(case, lambda bad=bad, expected=expected: require(not compile_success(bad, engine, plugin) and
                compile_outcome(bad, engine, plugin) == expected, "Invalid compile evidence mislabeled"))

    addon = Path("C:/fixture/addon")
    session = {"reused": False, "project": str(addon), "process_id": 123, "start_ticks": 456, "executable": engine["path"]}
    loaded_response = {"Loaded Projects": ["BerylWorkbenchDispatchProbe"]}
    runtime = {"schema_version": 1, "status": "success", "stage": "dispatch_transport_complete", "profile": PROFILE,
               "token": token, "function": "BerylWorkbenchDispatch", "engine_sha256": engine["sha256"], "engine_version": engine["version"],
               "tools": {name: plugin[name] for name in RUNTIME_FILES}, "session": session,
               "loaded_projects": {"Ok": True, "Function": "GetLoadedProjects", "Response": loaded_response,
                                   "Raw": json.dumps(loaded_response)},
               "cleanup": "owned_process_stopped", "evidence_errors": [], "raw_logs": [{"synthetic": True}], "elapsed_ms": 430,
               "rpcs": [], "completion": copy.deepcopy(base), "session_checks": []}
    for response, elapsed in ((arm, 100), (base, 400)):
        normalized, codec = decode(response)
        runtime["rpcs"].append({"action": response["action"], "elapsed_ms": elapsed, "timeout_ms": 8000, "failure": None,
                                "result": {"Ok": True, "Function": "BerylWorkbenchDispatch", "Raw": json.dumps(response), "Response": response},
                                "normalized_response": normalized, "codec": codec})
    for site, elapsed in zip(("startup.complete", "loaded.complete", "before.arm", "after.arm", "before.status", "after.status", "sentinel.complete"),
                             (10, 20, 90, 110, 390, 410, 420)):
        runtime["session_checks"].append({"site": site, "process_id": 123, "start_ticks": 456, "executable": engine["path"], "elapsed_ms": elapsed})
    execute("runtime-valid", lambda: verify_runtime(runtime, token, addon, engine, plugin))
    runtime_mutants = (
        ("runtime-missing-errors", ("evidence_errors",), None),
        ("runtime-reused-session", ("session", "reused"), True),
        ("runtime-missing-session-check", ("session_checks",), []),
        ("runtime-wrong-session-check", ("session_checks", 4, "process_id"), 124),
        ("runtime-reversed-time", ("session_checks", 4, "elapsed_ms"), 80),
        ("runtime-wrong-site", ("session_checks", 4, "site"), "before.arm"),
        ("runtime-unconfirmed-cleanup", ("cleanup",), "owned_process_exit_not_confirmed"),
        ("runtime-missing-logs", ("raw_logs",), []),
        ("runtime-raw-mismatch", ("rpcs", 1, "result", "Raw"), "{}"),
        ("runtime-codec-mismatch", ("rpcs", 1, "codec", "numeric_boolean_fields"), ["game_module_present"]),
        ("runtime-wrong-completion", ("completion", "sequence"), 3),
        ("runtime-game-unavailable", ("rpcs", 1, "result", "Response", "game_module_present"), False),
        ("runtime-wrong-plugin", ("tools", "Invoke-WorkbenchRpc.ps1"), "0" * 64),
        ("runtime-rpc-timeout-bool", ("rpcs", 1, "timeout_ms"), True),
        ("runtime-schema-bool", ("schema_version",), True),
    )
    for case, path, value in runtime_mutants:
        bad = copy.deepcopy(runtime)
        target = bad
        for name in path[:-1]: target = target[name]
        target[path[-1]] = value
        execute(case, lambda bad=bad: verify_runtime(bad, token, addon, engine, plugin), True)
    require([item["id"] for item in results] == list(ids), "Missing/duplicate synthetic cases")
    work = Path(tempfile.mkdtemp(prefix="dispatch-receipt-tests-", dir=ROOT / "build"))
    receipt = {"schema_version": 1, "operation": "dispatch.receipt.self_test", "status": "success", "expected_case_ids": list(ids),
               "completed_case_ids": [item["id"] for item in results], "complete_expected_case_set": True, "cases": results,
               "verifier": identity(Path(__file__)), "compiler_execution": "not_run", "engine_execution": "not_run"}
    save_result(work / "result.json", receipt)
    print(work / "result.json")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workbench-tools", type=Path, default=Path("C:/Users/moham/Desktop/reforger-workbench-plugin"))
    parser.add_argument("--powershell-host", type=Path)
    parser.add_argument("--engine-exe", type=Path)
    parser.add_argument("--engine-version")
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args()
    require(not args.run or (args.powershell_host and args.engine_exe and args.engine_version), "--run requires explicit host/engine/version", "unavailable")
    work = Path(tempfile.mkdtemp(prefix="workbench dispatch & spaces-", dir=ROOT / "build"))
    record = {"schema_version": 1, "operation": "verify.workbench_dispatch", "status": "failure", "stage": "prepare", "profile": PROFILE,
              "result_path": str(work / "result.json"), "scope": {"preparation": "not_run", "engine_compilation": "not_run", "engine_runtime": "not_run",
              "world_open": "not_run", "resource_open": "not_run", "module_open": "not_run", "component_callbacks": "not_run", "compiler": "not_used"},
              "expected_case_ids": list(CASE_IDS), "completed_case_ids": [], "complete_expected_case_set": False,
              "raw_results": {}, "commands": [], "evidence_errors": [], "failure": None}
    tracked = {}
    engine = None
    plugin = {}
    package_files = files(PACKAGE)
    addon = work / "addon"
    staged = None
    def track(path):
        path = path.resolve(strict=True)
        if str(path) in tracked:
            return dict(tracked[str(path)])
        item = helper.streamed_identity(path)
        require(item["bytes"] <= 512*1024*1024, "Input exceeds declared retention bound", "unavailable")
        tracked[str(path)] = dict(item)
        retained = work / "inputs" / (str(len(tracked)).zfill(3) + "-" + path.name)
        retained.parent.mkdir(exist_ok=True)
        with path.open("rb") as source, retained.open("xb") as destination:
            shutil.copyfileobj(source, destination, 1024*1024)
        require(helper.streamed_identity(path) == item and helper.streamed_identity(retained)["sha256"] == item["sha256"] and
                retained.stat().st_size == item["bytes"], "Input changed during retention", "stale_input")
        record.setdefault("inputs", []).append({**item, "retained": str(retained)})
        return item
    def unchanged():
        require(files(PACKAGE) == package_files, "Package set changed", "stale_input")
        for path, item in tracked.items(): require(helper.streamed_identity(Path(path)) == item, "Tracked input changed: " + path, "stale_input")
        for item in record.get("inputs", []):
            copied = helper.streamed_identity(Path(item["retained"]))
            require(copied["bytes"] == item["bytes"] and copied["sha256"] == item["sha256"], "Retained input changed", "stale_input")
        if staged is not None:
            actual = files(addon)
            derived = actual.pop("resourceDatabase.rdb", None)
            if derived is not None:
                require((addon / "resourceDatabase.rdb").stat().st_size <= 8*1024*1024, "Derived root cache too large", "unavailable")
                record["engine_derived_outputs"] = {"resourceDatabase.rdb": identity(addon / "resourceDatabase.rdb")}
            require(actual == staged and directories(addon) == helper.parent_directories(staged), "Staged exact set changed", "stale_input")
    def capture(label, path):
        helper.capture_adapter(record, label, path)
    try:
        require(set(package_files) == {"addon.gproj", "sentinel.c.in", "source-contracts.json", "README.md"}, "Unexpected fixture source set")
        contract = mod.parse(mod.read(PACKAGE / "source-contracts.json"))
        require(type(contract.get("schema_version")) is int and contract["schema_version"] == 1 and contract.get("profile") == PROFILE and type(contract.get("inputs")) is list,
                "Unsupported contract inventory")
        for path in [Path(__file__), TRANSPORT, ROOT / "scripts/verify-component-state.py", *mod.bundle_paths(),
                     ROOT / "tools/beryl-bench/run.py", ROOT / "tools/beryl-bench/receipts.py", *sorted(PACKAGE.iterdir())]: track(path)
        for item in contract["inputs"]:
            require(type(item) is dict and set(item) == {"path", "sha256"} and HASH.fullmatch(item["sha256"]), "Malformed primary source identity")
            require(track(Path(item["path"]))["sha256"] == item["sha256"], "Primary declaration bytes changed", "stale_input")
        tools = args.workbench_tools.resolve(strict=True)
        plugin = {name: track(tools / "scripts" / name)["sha256"] for name in PLUGIN_FILES}
        host = args.powershell_host.resolve(strict=True) if args.powershell_host else None
        if host: record["host"] = track(host)
        engine = None
        if args.engine_exe:
            engine = track(args.engine_exe.resolve(strict=True))
            engine["version"] = args.engine_version
            record["engine"] = engine
        record["plugin_hashes"] = plugin
        token = mod.digest(mod.canonical({"operation": work.name, "profile": PROFILE, "source": package_files, "inputs": tracked}))
        source = mod.read(PACKAGE / "sentinel.c.in").decode().replace("@TOKEN@", token)
        require("@TOKEN@" not in source, "Unresolved sentinel token")
        gproj = mod.read(PACKAGE / "addon.gproj")
        generated = {"addon.gproj": gproj, "scripts/WorkbenchGameCommon/BerylWorkbenchDispatch.c": source.encode()}
        for name, data in generated.items(): write(addon / name, data)
        staged = {name: mod.digest(data) for name, data in generated.items()}
        manifest = work / "staged-inputs.json"
        save_result(manifest, {"schema_version": 1, "files": staged})
        track(manifest)
        record.update(token=token, candidate_path=str(addon), staged_file_set=staged, staged_sha256=mod.digest(mod.canonical(staged)),
                      source_file_set=package_files, source_sha256=mod.digest(mod.canonical(package_files)))
        record["scope"]["preparation"] = "executed_success"
        unchanged()
        if args.run:
            sys.path.insert(0, str(ROOT / "tools/beryl-bench"))
            collector = load("dispatch_bounded_capture", ROOT / "tools/beryl-bench/run.py")
            def run(argv, label, timeout):
                unchanged()
                command = {"argv": [str(item) for item in argv], "stage": label, "status": "attempted", "exit_code": None}
                record["commands"].append(command)
                try:
                    value = collector.run_binary(argv, timeout=timeout, cwd=work, output_limit=4*1024*1024)
                    for stream in ("stdout", "stderr"):
                        target = work / (label + "." + stream + ".log")
                        write(target, value[stream]);command[stream] = identity(target)
                    command.update(status=value["status"], exit_code=value["exit_code"])
                    unchanged()
                    require(value["exit_code"] == 0, "Adapter exited with failure; inspect retained receipt/logs")
                except collector.CollectorError as exc:
                    command.update(status=exc.status, capture="incomplete; bounded capture failed, no synthetic stdout")
                    raise mod.Failure(str(exc), exc.status if exc.status in helper.FAILURE_STATUSES else "failure") from exc
            compiled_path = work / "engine-compile.json"
            record["stage"] = "compile";record["scope"]["engine_compilation"] = "attempted_unconfirmed"
            try:
                run([host, "-NoProfile", "-File", mod.HERE / "engine-compile.ps1", "-ToolRoot", tools, "-ProjectDir", addon,
                     "-ResultPath", compiled_path, "-ExpectedVersion", args.engine_version], "compile", 300)
            finally:
                capture("compile", compiled_path)
            compiled = record["raw_results"].get("compile", {}).get("result", {})
            require(compile_success(compiled, engine, plugin), "Missing exact successful engine compile receipt")
            record["scope"]["engine_compilation"] = "executed_success"
            runtime_path = work / "engine-runtime.json"
            record["stage"] = "runtime";record["scope"]["engine_runtime"] = "attempted_unconfirmed"
            try:
                run([host, "-NoProfile", "-File", TRANSPORT, "-ToolRoot", tools, "-ProjectDir", addon, "-ResultPath", runtime_path,
                     "-InputManifest", manifest, "-InputManifestHash", identity(manifest)["sha256"], "-Token", token,
                     "-ExpectedEngineHash", engine["sha256"], "-ExpectedEngineVersion", args.engine_version], "runtime", 240)
            finally:
                capture("runtime", runtime_path)
            runtime = record["raw_results"].get("runtime", {}).get("result", {})
            record["comparison"] = verify_runtime(runtime, token, addon, engine, plugin)
            for log in runtime["raw_logs"]:
                path = Path(log["retained"])
                require(path.is_relative_to(work) and helper.streamed_identity(path)["sha256"] == log["sha256"], "Runtime log identity changed", "stale_input")
            record["scope"]["engine_runtime"] = "executed_success"
            record["completed_case_ids"] = list(CASE_IDS);record["complete_expected_case_set"] = True
        unchanged()
        record["stage"] = "complete" if args.run else "prepared"
        record["status"] = "success"
    except mod.Failure as exc:
        record["status"] = exc.status;record["failure"] = str(exc)
        # The latest actual adapter may refine a generic failure. It cannot erase
        # an independently detected timeout, cancellation or changed input.
        if record["status"] == "failure" and record["stage"] in {"compile", "runtime"}:
            value = record["raw_results"].get(record["stage"], {}).get("result")
            if type(value) is dict and value.get("status") in helper.FAILURE_STATUSES:
                record["status"] = value["status"]
    except KeyboardInterrupt:
        record["status"] = "cancelled";record["failure"] = "Cancelled"
    except BaseException as exc:
        record["failure"] = type(exc).__name__ + ": " + str(exc)
    finally:
        try: unchanged()
        except BaseException as exc:
            record["evidence_errors"].append({"stage": "final_input_check", "message": str(exc)})
            if record["status"] == "success": record["status"] = "stale_input";record["failure"] = str(exc)
        compiled = record["raw_results"].get("compile", {}).get("result", {})
        try:
            record["compile_logs"] = helper.retain_engine_logs(work, compiled)
        except BaseException as exc:
            record["evidence_errors"].append({"stage": "compile_log_retention", "message": str(exc)})
            if record["status"] == "success" and args.run: record["status"] = "unavailable";record["failure"] = str(exc)
        if args.run and (record["scope"]["engine_compilation"] != "not_run" or compiled):
            record["scope"]["engine_compilation"] = compile_outcome(compiled, engine, record.get("plugin_hashes", {}))
        save_result(work / "result.json", record)
        print(work / "result.json")
    return 0 if record["status"] == "success" else 1


if __name__ == "__main__":
    if sys.argv[1:] == ["--self-test"]: self_test()
    else: raise SystemExit(main())
