#!/usr/bin/env python3
"""Read-only compiler context regressions; no Beryl/engine code is executed."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent.parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--beryl", required=True, type=Path)
    args = parser.parse_args()
    beryl = args.beryl.resolve(strict=True)
    work = Path(tempfile.mkdtemp(prefix="context & spaces-", dir=ROOT / "build"))
    fixtures = ROOT / "tests" / "context"
    left, right, wide = (fixtures / name for name in ("left.be", "right.be", "wide.be"))
    inputs = [Path(__file__), ROOT / "src/driver/context.c", ROOT / "src/driver/context.h", left, right, wide]
    before = {str(p): sha(p) for p in inputs}
    evidence = {"schema_version": 1, "status": "running", "compiler_sha256": sha(beryl),
                "input_hashes": before, "commands": [], "checks": [], "program_execution": "not_run",
                "engine_execution": "not_run"}
    print(f"Context artifacts: {work}", flush=True)

    def run(*arguments, expected=0):
        argv = [str(beryl), "context", *map(str, arguments)]
        proc = subprocess.run(argv, cwd=work, capture_output=True, text=True,
                              encoding="utf-8", errors="strict", timeout=30)
        evidence["commands"].append({"argv": argv, "exit_code": proc.returncode,
                                     "stdout": proc.stdout, "stderr": proc.stderr})
        assert proc.returncode == expected, (argv, proc.returncode, proc.stdout, proc.stderr)
        obj = json.loads(proc.stdout)
        assert obj["schema_version"] == 1
        assert obj["compiler_fingerprint"] == evidence["compiler_sha256"]
        assert obj["execution"] == "not_run"
        assert Path(obj["working_directory"]).resolve() == work.resolve()
        assert obj["artifact_fingerprint"] is None
        if obj["operation"] == "context.binding" and obj["data"] is not None:
            assert len(obj["binding_fingerprint"]) == 64
        else:
            assert obj["binding_fingerprint"] is None
        assert len(obj["source_fingerprint"]) == 64
        return obj, proc.stdout

    def passed(name):
        evidence["checks"].append(name)
        print(f"passed {name}", flush=True)

    try:
        empty, _ = run("project")
        assert empty["status"] == "success" and empty["sources"] == []
        assert empty["data"]["capabilities"]["native"]["status"] == "not_checked"
        passed("empty project reports compiler inventory without invented admission")

        project, raw = run("project", left, right, "--format", "json")
        again, second = run("project", left, right, "--format", "json")
        assert raw == second and project == again
        declarations = project["data"]["declarations"]
        assert [d["qualified_name"] for d in declarations] == sorted(d["qualified_name"] for d in declarations)
        states = [d for d in declarations if d["name"] == "State"]
        assert len(states) == 2 and states[0]["declaration_id"] != states[1]["declaration_id"]
        assert all(d["effects"]["status"] == "unavailable" for d in declarations)
        assert project["data"]["released_plans"] == [] and project["data"]["measurements"] is None
        capabilities = project["data"]["capabilities"]
        assert capabilities["native_evidence"]["status"] == "implemented"
        assert capabilities["native_evidence"]["execution"] == "not_run"
        assert capabilities["expected_trap_differential"]["maximum_watched_elements"] == 4096
        assert capabilities["expected_trap_differential"]["execution"] == "not_run"
        assert capabilities["enfusion_source_map"]["schema_version"] == 1
        assert capabilities["enfusion_source_map"]["engine_column_interpolation"] == "unavailable"
        assert "outermost" in capabilities["enfusion_source_map"]["default_expansion"]
        assert capabilities["engine_scenarios"]["status"] == "tool_owned"
        for target in ("reference", "native", "enfusion"):
            probe = project["data"]["capabilities"][target]
            assert probe["status"] == "admitted", probe
            assert probe["scope"] == "all_loaded_declarations" and probe["execution"] == "not_run"
        passed("deterministic qualified identity and separated admission probes")

        symbol, _ = run("symbol", "context.left.State.replace", left, right)
        item = symbol["data"]["symbol"]
        assert item["receiver"] == "context.left.State"
        assert item["parameters"][0]["access_mode"] == "inout"
        assert item["parameters"][1]["access_mode"] == "let"
        assert item["parameters"][1]["default"]["text"] == "1f32"
        assert item["parameters"][1]["type"]["name"] == "f32"
        loc = item["source"]
        source = Path(loc["path"]).read_bytes()
        actual = source[loc["byte_offset"]:loc["byte_offset"] + loc["byte_length"]].decode("utf-8")
        assert actual == loc["text"] and loc["column_unit"] == "byte"
        private, _ = run("symbol", "context.left.private_value", left)
        assert private["data"]["symbol"]["visibility"] == "module_private"
        passed("exact source spans, receiver, parameter modes/defaults and visibility")

        ambiguous, _ = run("symbol", "shared", left, right, expected=1)
        assert ambiguous["status"] == "failure" and ambiguous["data"] is None
        assert ambiguous["candidates"] == ["context.left.shared", "context.right.shared"]
        unknown, _ = run("symbol", "context.left.absent", left, expected=1)
        assert unknown["status"] == "failure" and unknown["candidates"] == []
        for name in ("context..State", "../escape", "State<T>", ".State", "State."):
            failure, _ = run("symbol", name, left, expected=1)
            assert failure["status"] == "failure"
        passed("unknown, ambiguous and unsupported names fail explicitly")

        wider, _ = run("project", wide)
        cap = wider["data"]["capabilities"]
        assert wider["status"] == "success" and wider["diagnostics"] == []
        assert cap["native"]["status"] == "admitted"
        assert cap["reference"]["status"] == "unavailable" and cap["reference"]["diagnostics"]
        assert cap["enfusion"]["status"] == "unavailable" and cap["enfusion"]["diagnostics"]
        passed("one target's unavailable subset does not contaminate other admission")

        binding, _ = run("binding", "Math.Clamp")
        assert binding["status"] == "success"
        assert binding["data"]["extracted_declaration"]["status"] == "snapshot_available"
        assert binding["data"]["extracted_declaration"]["declarations"][0]["signature"] == "static proto float Clamp (float value, float min, float max)"
        assert binding["data"]["applicability"]["engine"] == "not_checked"
        assert binding["data"]["verified_contract"]["status"] == "unavailable"
        assert binding["data"]["verified_contract"]["effects"] is None
        integer, _ = run("binding", "Math.ClampInt")
        assert integer["data"]["extracted_declaration"]["declarations"][0]["signature"] == "static proto int ClampInt (int value, int min, int max)"
        missing_binding, _ = run("binding", "Math.Invented", expected=3)
        assert missing_binding["data"]["extracted_declaration"]["declarations"] == []
        methods, _ = run("binding", "array")
        assert len(methods["data"]["extracted_declaration"]["declarations"]) == 14
        assert methods["data"]["verified_contract"]["retention"] is None
        mismatch, _ = run("binding", "Math.MinInt", "--engine-executable", beryl, expected=3)
        assert mismatch["status"] == "stale_input"
        assert mismatch["data"]["applicability"]["engine"] == "mismatch"
        unreadable, _ = run("binding", "Math.MinInt", "--engine-executable", work / "absent.exe", expected=3)
        assert unreadable["status"] == "unavailable"
        api = work / "api & docs"
        api.mkdir()
        (api / "interfaceMath.html").write_text("changed documentation", encoding="utf-8")
        changed_doc, _ = run("binding", "Math.MinInt", "--api-root", api, expected=3)
        assert changed_doc["status"] == "stale_input"
        assert changed_doc["data"]["applicability"]["document"] == "mismatch"
        listing, _ = run("optimization", "--list")
        families = listing["data"]["optimization_families"]
        assert len(families) == 14 and len({f["family"] for f in families}) == 14
        assert all(f["status"] == "proposed" and not f["released"] and not f["eligible"] for f in families)
        opt, _ = run("optimization", "context.left.shared", left)
        assert opt["data"]["symbol"]["qualified_name"] == "context.left.shared"
        assert opt["data"]["released_plans"] == []
        passed("bounded binding provenance, unknown contracts, stale identities and unreleased plans")

        for arguments in ((), ("no-such-topic",), ("symbol",), ("symbol", "x"),
                          ("project", "--format", "human"), ("project", "--format"),
                          ("binding", "Math.Clamp", left), ("project", "--bogus"),
                          ("optimization", "context.left.shared", "--list"),
                          ("optimization", "--list", left), ("project", "missing.be")):
            obj, _ = run(*arguments, expected=1)
            assert obj["status"] == "failure" and obj["diagnostics"]
        for arguments in (("binding", "Math.MinInt", "--api-root"),
                          ("binding", "Math.MinInt", "--engine-executable", ""),
                          ("binding", "Math.MinInt", "--api-root", api, "--api-root", api),
                          ("project", "--engine-executable", beryl)):
            obj, _ = run(*arguments, expected=1)
            assert obj["status"] == "failure" and obj["diagnostics"]
        passed("malformed requests produce the same JSON envelope")

        malformed = work / "invalid.be"
        malformed.write_text("module broken\npub fn broken( {", encoding="utf-8")
        bad, _ = run("project", malformed, expected=1)
        assert bad["data"] is None and bad["diagnostics"]
        passed("parse failure does not expose partially resolved declarations")

        (work / "src").mkdir()
        (work / "src/main.be").write_text(left.read_text(encoding="utf-8"), encoding="utf-8")
        manifest = work / "beryl.toml"
        manifest.write_text('[package]\nname = "context-fixture"\nversion = "1.0.0"\n'
                            '[target.enfusion]\nprefix = "not-an-identifier"\n', encoding="utf-8")
        package, _ = run("project")
        assert package["data"]["project"]["manifest_found"]
        assert package["data"]["project"]["name"] == "context-fixture"
        assert package["data"]["capabilities"]["native"]["status"] == "admitted"
        assert package["data"]["capabilities"]["enfusion"]["status"] == "unavailable"
        assert {Path(s["path"]).name for s in package["sources"]} == {"beryl.toml", "main.be"}
        passed("package discovery and target admission use the loaded manifest")

        assert {str(p): sha(p) for p in inputs} == before, "context inputs changed during verification"
        assert sha(beryl) == evidence["compiler_sha256"], "compiler changed during verification"
        assert not (work / ".beryl-cache").exists() and not (work / ".beryl-mod").exists()
        evidence["status"] = "success"
    except Exception as exc:
        evidence["status"] = "failure"
        evidence["error"] = repr(exc)
        raise
    finally:
        (work / "results.json").write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
