#!/usr/bin/env python3
"""Bounded exploratory engine API observations through the existing bridge.

This reports raw capabilities; it is not a benchmark or a Canvas retention test.
"""
from pathlib import Path
import argparse
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools/beryl-mod"))
import mod

SOURCE = r'''
class BerylEngineCapsRequest : JsonApiStruct
{
    string token;
    void BerylEngineCapsRequest() { RegV("token"); }
}
class BerylEngineCapsResponse : JsonApiStruct
{
    string token;
    int executed;
    ref array<string> rows = {};
    void BerylEngineCapsResponse() { RegV("token"); RegV("executed"); RegV("rows"); }
}
class BerylEngineCaps : NetApiHandler
{
    override JsonApiStruct GetRequest() { return new BerylEngineCapsRequest(); }
    override JsonApiStruct GetResponse(JsonApiStruct request)
    {
        BerylEngineCapsRequest req = BerylEngineCapsRequest.Cast(request);
        BerylEngineCapsResponse result = new BerylEngineCapsResponse();
        result.token = "@TOKEN@";
        if (!req || req.token != result.token) return result;
        Game game = GetGame();
        WorkspaceWidget workspace;
        if (game) workspace = game.GetWorkspace();
        int hasGame = 0;
        int hasWorkspace = 0;
        if (game) hasGame = 1;
        if (workspace) hasWorkspace = 1;
        result.rows.Insert("workspace|" + hasGame.ToString() + "|" + hasWorkspace.ToString());
        int began = System.GetTickCount();
        int value = 0;
        for (int i = 0; i < 1000000; i++) value = (value + 17) % 1000003;
        int ended = System.GetTickCount();
        result.rows.Insert("ticks|" + began.ToString() + "|" + ended.ToString() + "|" + value.ToString());
        result.rows.Insert("memory-before|" + System.MemoryAllocationCount().ToString() + "|" + System.MemoryAllocationKB().ToString());
        array<int> values = {};
        values.Reserve(262144);
        result.rows.Insert("memory-reserve|" + System.MemoryAllocationCount().ToString() + "|" + System.MemoryAllocationKB().ToString() + "|" + values.Count().ToString());
        values.Resize(262144);
        result.rows.Insert("memory-resize|" + System.MemoryAllocationCount().ToString() + "|" + System.MemoryAllocationKB().ToString() + "|" + values.Count().ToString());
        values.Clear();
        result.rows.Insert("memory-clear|" + System.MemoryAllocationCount().ToString() + "|" + System.MemoryAllocationKB().ToString() + "|" + values.Count().ToString());
        values.Compact();
        result.rows.Insert("memory-compact|" + System.MemoryAllocationCount().ToString() + "|" + System.MemoryAllocationKB().ToString() + "|" + values.Count().ToString());
        values = null;
        result.rows.Insert("memory-drop|" + System.MemoryAllocationCount().ToString() + "|" + System.MemoryAllocationKB().ToString());
        result.executed = 1;
        return result;
    }
}
'''


def execute(source, label, expected_rows, owner):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--beryl", type=Path, required=True)
    parser.add_argument("--workbench-tools", type=Path, required=True)
    args = parser.parse_args()
    work = Path(tempfile.mkdtemp(prefix=label + "-", dir=ROOT / "build"))
    job = mod.Job(work, "engine-capabilities", args.beryl.resolve(strict=True))
    token = mod.digest(mod.canonical({"script": mod.digest(mod.read(owner)), "source": mod.digest(source.encode()), "compiler": job.result["compiler_sha256"], "operation": job.id}))
    addon = work / "addon"
    script = addon / "scripts/WorkbenchGameCommon/BerylEngineCaps.c"
    script.parent.mkdir(parents=True)
    script.write_text(source.replace("@TOKEN@", token), encoding="utf-8", newline="\n")
    (addon / "addon.gproj").write_text('GameProject {\n ID "BerylEngineCaps"\n GUID "' + token[:16].upper() + '"\n TITLE "Beryl bounded capability probe"\n Dependencies {\n "58D0FB3206B6F859"\n }\n}\n', encoding="utf-8")
    staged = {p.relative_to(addon).as_posix(): mod.digest(mod.read(p)) for p in addon.rglob("*") if p.is_file()}
    record = dict(schema_version=1, status="failure", scope="exploratory API observations, no performance or retention claim", token=token,
                  compiler_sha256=job.result["compiler_sha256"], script_sha256=mod.digest(mod.read(owner)), staged=staged)
    try:
        compile_path = work / "compile.json"
        runtime_path = work / "runtime.json"
        job.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", mod.HERE / "engine-compile.ps1", "-ToolRoot", args.workbench_tools.resolve(),
                 "-ProjectDir", addon, "-ResultPath", compile_path, "-ExpectedVersion", "1.8.0.13"], "compile", work, 300)
        compiled = mod.parse(mod.read(compile_path))
        job.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", mod.HERE / "scenario-engine-run.ps1", "-ToolRoot", args.workbench_tools.resolve(),
                 "-ProjectDir", addon, "-ProjectId", "BerylEngineCaps", "-ResultPath", runtime_path, "-Token", token, "-Function", "BerylEngineCaps",
                 "-ExpectedEngineHash", compiled["engine_sha256"], "-ExpectedEngineVersion", compiled["engine_version"]], "runtime", work, 300)
        runtime = mod.parse(mod.read(runtime_path))
        response = runtime["rpc"]["Response"]
        assert set(response) == {"token", "executed", "rows"} and response["token"] == token and response["executed"] == 1
        assert len(response["rows"]) == expected_rows and all(type(row) is str for row in response["rows"])
        assert all(mod.digest(mod.read(addon / name)) == value for name, value in staged.items())
        record.update(status="success", compile=compiled, runtime=runtime)
        print("\n".join(response["rows"]), flush=True)
    except BaseException as exc:
        record["failure"] = repr(exc)
        raise
    finally:
        record["job"] = job.result
        mod.write_json(work / "result.json", record)
        print("Evidence: " + str(work / "result.json"), flush=True)


if __name__ == "__main__":
    execute(SOURCE, "engine-caps", 8, __file__)
