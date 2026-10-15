#!/usr/bin/env python3
"""Observe EnforceScript receiver capture and argument evaluation order.

Uses the existing owned compile/RPC bridge. This is a bounded ABI observation,
not a tablet-service, lifetime, world, multiplayer or bitwise-float test.
"""
import argparse
import importlib.util
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / "tools/beryl-mod"))
import mod

spec = importlib.util.spec_from_file_location("tablet_engine_replay_helpers", ROOT / "scripts/verify-tablet-engine-replay.py")
helpers = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helpers)

SOURCE = r'''
class BerylReceiverOrderRequest : JsonApiStruct {
 string token; void BerylReceiverOrderRequest() { RegV("token"); }
}
class BerylReceiverOrderResponse : JsonApiStruct {
 string token; int executed; ref array<string> rows = {};
 void BerylReceiverOrderResponse() { RegV("token"); RegV("executed"); RegV("rows"); }
}
class BerylReceiverOrderTarget {
 int id;
 BerylReceiverOrderHost host;
 void SetOne(int value) {
  host.rows.Insert("call|" + id.ToString() + "|" + value.ToString());
 }
 void SetTwo(int left, int right) {
  host.rows.Insert("call|" + id.ToString() + "|" + left.ToString() + "|" + right.ToString());
 }
}
class BerylReceiverOrderHost {
 ref BerylReceiverOrderTarget current;
 ref array<string> rows = {};
 void Select(int id) {
  current = new BerylReceiverOrderTarget(); current.id = id; current.host = this;
 }
 int Arg(int id, bool change) {
  rows.Insert("argument|" + id.ToString());
  if (change) Select(id + 1);
  return id * 10;
 }
 void Run(int kind) {
  Select(1);
  BerylReceiverOrderTarget original = current;
  if (kind == 0) current.SetOne(Arg(1, false));
  else if (kind == 1) current.SetOne(Arg(1, true));
  else current.SetTwo(Arg(1, true), Arg(2, true));
  rows.Insert("final|" + current.id.ToString());
  // Break only fixture cycles after the observed invocation completed.
  original.host = null; current.host = null;
 }
}
class BerylReceiverOrder : NetApiHandler {
 override JsonApiStruct GetRequest() { return new BerylReceiverOrderRequest(); }
 override JsonApiStruct GetResponse(JsonApiStruct request) {
  BerylReceiverOrderRequest req = BerylReceiverOrderRequest.Cast(request);
  BerylReceiverOrderResponse result = new BerylReceiverOrderResponse();
  result.token = "@TOKEN@";
  if (!req || req.token != result.token) return result;
  for (int i = 0; i < 3; i++) {
   result.rows.Insert("case|" + i.ToString());
   BerylReceiverOrderHost host = new BerylReceiverOrderHost();
   host.Run(i);
   foreach (string row : host.rows) result.rows.Insert(row);
  }
  result.executed = 1; return result;
 }
}
'''


def interpret(response, token):
    if type(response) is not dict or set(response) != {"token", "executed", "rows"} or response["token"] != token or type(response["executed"]) is not int or response["executed"] != 1:
        raise mod.Failure("Incomplete receiver-order response")
    rows = response["rows"]
    before = ["case|0", "argument|1", "call|1|10", "final|1",
              "case|1", "argument|1", "call|1|10", "final|2",
              "case|2", "argument|1", "argument|2", "call|1|10|20", "final|3"]
    after = before.copy()
    after[6] = "call|2|10"
    after[11] = "call|3|10|20"
    if rows == before:
        return "receiver_captured_before_arguments; arguments_left_to_right"
    if rows == after:
        return "receiver_selected_after_arguments; arguments_left_to_right"
    raise mod.Failure("Observed order outside the bounded declared alternatives", "unavailable")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--beryl", type=Path, required=True)
    parser.add_argument("--expect-compiler-sha256", required=True)
    parser.add_argument("--workbench-tools", type=Path, required=True)
    parser.add_argument("--engine", type=Path, required=True)
    parser.add_argument("--powershell-host", type=Path, required=True)
    args = parser.parse_args()
    compiler, tools, engine, host = [p.resolve(strict=True) for p in (args.beryl, args.workbench_tools, args.engine, args.powershell_host)]
    if compiler.parent == ROOT / "build" or not compiler.is_relative_to(ROOT / "build") or helpers.file_hash(compiler) != args.expect_compiler_sha256 or helpers.file_hash(engine) != helpers.ENGINE_SHA:
        raise mod.Failure("Explicit private compiler and reviewed engine identities required", "stale_input")
    work = Path(tempfile.mkdtemp(prefix="receiver-argument-order-", dir=ROOT / "build"))
    job = mod.Job(work, "experimental.receiver_argument_order", compiler)
    token = mod.digest(mod.canonical({"job": job.id, "script": helpers.file_hash(Path(__file__)), "source": mod.digest(SOURCE.encode())}))
    addon = work / "addon"
    script = addon / "scripts/WorkbenchGameCommon/BerylReceiverOrder.c"
    script.parent.mkdir(parents=True)
    source = SOURCE.replace("@TOKEN@", token).encode()
    if script.write_bytes(source) != len(source) or helpers.file_hash(script) != mod.digest(source):
        raise mod.Failure("Incomplete installed fixture write")
    project = ('GameProject {\n ID "BerylReceiverOrder"\n GUID "' + token[:16].upper() + '"\n TITLE "Beryl receiver order probe"\n Dependencies {\n "58D0FB3206B6F859"\n }\n}\n').encode()
    (addon / "addon.gproj").write_bytes(project)
    staged = {script.relative_to(addon).as_posix(): mod.digest(source), "addon.gproj": mod.digest(project)}
    if helpers.tree(addon) != staged:
        raise mod.Failure("Initial fixture differs")
    frozen = {str(p): helpers.file_hash(p) for p in [compiler, engine, host, Path(__file__), ROOT / "scripts/verify-tablet-engine-replay.py",
              *mod.bundle_paths(), *[tools / "scripts" / name for name in helpers.BRIDGE]]}
    record = {"schema_version": 1, "operation": "experimental.receiver_argument_order", "status": "failure", "token": token,
              "scope": "three actual plain-script receiver/argument observations, exact engine bytes only",
              "frozen": frozen, "staged_inputs": staged, "actual_tablet_services": "not_run", "callback_delivery": "not_run", "promotion": "not_run"}
    def unchanged():
        if any(helpers.file_hash(Path(p)) != h for p, h in frozen.items()):
            raise mod.Failure("Frozen ABI probe input changed", "stale_input")
        actual = helpers.tree(addon)
        cache = actual.pop("resourceDatabase.rdb", None)
        if cache:
            path = addon / "resourceDatabase.rdb"
            if path.stat().st_size > 8 * 1024 * 1024:
                raise mod.Failure("Derived cache exceeds probe bound", "unavailable")
            record["derived_cache"] = {"path": str(path), "sha256": cache, "bytes": path.stat().st_size}
        if actual != staged:
            raise mod.Failure("ABI probe fixture changed", "stale_input")
    print("Receiver/argument probe:", work, flush=True)
    try:
        for adapter, stage, params, timeout in (
            ("engine-compile.ps1", "compile", ["-ExpectedVersion", helpers.VERSION, "-TimeoutSeconds", "120"], 150),
            ("scenario-engine-run.ps1", "runtime", ["-ProjectId", "BerylReceiverOrder", "-Token", token, "-Function", "BerylReceiverOrder",
                "-ExpectedEngineHash", helpers.ENGINE_SHA, "-ExpectedEngineVersion", helpers.VERSION], 240)):
            unchanged()
            receipt = work / (stage + ".json")
            job.run([host, "-NoProfile", "-File", mod.HERE / adapter, "-ToolRoot", tools, "-ProjectDir", addon, "-ResultPath", receipt, *params], stage, work, timeout)
            result = mod.parse(mod.read(receipt))
            record[stage + "_result"] = result
            record.setdefault("raw_result_receipts", {})[stage] = {"path": str(receipt), "sha256": helpers.file_hash(receipt)}
            if result.get("schema_version") != 1 or result.get("engine_sha256") != helpers.ENGINE_SHA or result.get("engine_version") != helpers.VERSION:
                raise mod.Failure("Incomplete or mismatched engine probe")
            if result.get("status") != "success":
                status = result.get("status")
                raise mod.Failure("Engine probe did not complete", status if status in helpers.FAILURE_STATUSES else "failure")
            if stage == "compile":
                detail = result["result"]
                if result.get("stage") != "workbench_compile" or result.get("tools") != {n: frozen[str(tools / "scripts" / n)] for n in helpers.BRIDGE[:4]} or detail.get("Stage") != "Compiled" or detail.get("Ok") is not True or detail.get("ExitCode") != 0 or detail.get("ErrorCount") != 0:
                    raise mod.Failure("Incomplete ABI compile evidence")
            else:
                if result.get("stage") != "scenario_engine_execution" or result.get("rpc", {}).get("Ok") is not True or result.get("session", {}).get("reused") is not False or result["session"].get("project") != str(addon) or "BerylReceiverOrder" not in result.get("loaded_projects", {}).get("Response", {}).get("Loaded Projects", []):
                    raise mod.Failure("Unrelated or incomplete ABI execution")
                record["observed_contract"] = interpret(result["rpc"]["Response"], token)
            unchanged()
        record["status"] = job.result["status"] = "success"
        print(record["observed_contract"], flush=True)
    except BaseException as exc:
        status = "cancelled" if isinstance(exc, KeyboardInterrupt) else getattr(exc, "status", "failure")
        record.update(status=status if status in helpers.FAILURE_STATUSES else "failure", error=repr(exc))
        job.result["status"] = record["status"]
        raise
    finally:
        for stage in ("compile", "runtime"):
            receipt = work / (stage + ".json")
            if receipt.is_file():
                try:
                    record.setdefault("raw_result_receipts", {})[stage] = {"path": str(receipt), "sha256": helpers.file_hash(receipt)}
                    record[stage + "_result"] = mod.parse(mod.read(receipt))
                except BaseException as exc:
                    # A malformed raw receipt must not hide the original outcome
                    # or prevent its path/hash and failed attempt from being saved.
                    record.setdefault("evidence_errors", []).append({"stage": stage, "error": repr(exc)})
                    if record["status"] == "success":
                        record["status"] = job.result["status"] = "failure"
        try:
            compile_logs = record.get("compile_result", {}).get("result") or {}
            record["raw_engine_logs"] = []
            if compile_logs.get("LogDir"):
                for path in sorted(Path(compile_logs["LogDir"]).glob("*.log")):
                    before = helpers.file_hash(path)
                    target = work / "logs" / path.name
                    target.parent.mkdir(exist_ok=True)
                    target.write_bytes(path.read_bytes())
                    if helpers.file_hash(target) != before or helpers.file_hash(path) != before:
                        raise mod.Failure("Engine log changed during capture", "stale_input")
                    record["raw_engine_logs"].append({"path": str(target), "sha256": before})
            if record["status"] == "success" and not record["raw_engine_logs"]:
                raise mod.Failure("Raw engine logs unavailable")
            unchanged()
        except BaseException as exc:
            record["finalization_error"] = repr(exc)
            if record["status"] == "success":
                record["status"] = job.result["status"] = "failure"
        mod.write_json(Path(job.result["result_path"]), job.result)
        record["job"] = job.result
        record["job_receipt_sha256"] = helpers.file_hash(Path(job.result["result_path"]))
        mod.write_json(work / "result.json", record)
        print("Evidence:", work / "result.json", flush=True)
    return 0 if record["status"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
