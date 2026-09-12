#!/usr/bin/env python3
"""Verify exact bounded binding lookup and optionally its installed doc/engine identity.

Reads files and runs compiler context only. It never launches the engine or
equates a successful lookup with signature execution or a lifetime contract.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--beryl", type=Path, required=True)
    parser.add_argument("--api-root", type=Path)
    parser.add_argument("--engine-executable", type=Path)
    args = parser.parse_args()
    beryl = args.beryl.resolve(strict=True)
    work = Path(tempfile.mkdtemp(prefix="binding registry & ", dir=ROOT / "build"))
    snapshot_path = ROOT / "tools/beryl-bindings/snapshot.json"
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    hashes = {str(path.relative_to(ROOT)): sha(path) for path in
              [snapshot_path, ROOT / "src/driver/binding_registry.inc", ROOT / "src/driver/binding_context.c",
               ROOT / "src/driver/binding_context.h", ROOT / "src/driver/context.c", Path(__file__)]}
    evidence = {"schema_version": 1, "status": "running", "compiler_sha256": sha(beryl),
                "input_hashes": hashes, "commands": [], "checks": [], "engine_execution": "not_run",
                "semantic_contracts": "unavailable"}
    print(f"Binding evidence: {work}", flush=True)

    def run(argv, expected=0):
        proc = subprocess.run(list(map(str, argv)), cwd=work, capture_output=True,
                              text=True, encoding="utf-8", errors="strict", timeout=30)
        evidence["commands"].append({"argv": list(map(str, argv)), "exit_code": proc.returncode,
                                     "stdout": proc.stdout, "stderr": proc.stderr})
        assert proc.returncode == expected, evidence["commands"][-1]
        return proc.stdout

    try:
        run([sys.executable, "-B", ROOT / "tools/beryl-bindings/generate.py", "--check"])
        run([sys.executable, "-B", ROOT / "tools/beryl-bindings/test_generate.py"])
        expected_fingerprint = hashlib.sha256(json.dumps(snapshot, sort_keys=True, ensure_ascii=True,
                                                         separators=(",", ":")).encode()).hexdigest()
        for declaration in snapshot["declarations"]:
            result = json.loads(run([beryl, "context", "binding", declaration["name"]]))
            assert result["status"] == "success" and result["execution"] == "not_run"
            assert result["compiler_fingerprint"] == evidence["compiler_sha256"]
            assert result["binding_fingerprint"] == expected_fingerprint
            assert result["data"]["extracted_declaration"]["declarations"] == [declaration]
            assert result["data"]["verified_contract"]["status"] == "unavailable"
            assert result["data"]["applicability"]["engine"] == "not_checked"
            if args.api_root:
                origin = declaration["source"]
                raw = (args.api_root / origin["document"]).read_bytes()
                assert hashlib.sha256(raw).hexdigest() == origin["document_sha256"]
                fragment = raw[origin["byte_offset"]:origin["byte_offset"] + origin["byte_length"]]
                assert hashlib.sha256(fragment).hexdigest() == origin["fragment_sha256"]
                assert raw[:origin["byte_offset"]].count(b"\n") + 1 == origin["line"]
        evidence["checks"].append(f"all {len(snapshot['declarations'])} declarations exactly match the compiled snapshot")
        if args.api_root:
            for owner in sorted({row["owner"] for row in snapshot["declarations"]}):
                result = json.loads(run([beryl, "context", "binding", owner, "--api-root", args.api_root]))
                assert result["data"]["applicability"]["document"] == "match"
            evidence["checks"].append("all selected installed documents and exact declaration fragments match")
        if args.engine_executable:
            options = ["--api-root", args.api_root] if args.api_root else []
            result = json.loads(run([beryl, "context", "binding", "Math.ClampInt",
                                     "--engine-executable", args.engine_executable, *options]))
            assert result["data"]["applicability"]["engine"] == "match"
            assert result["data"]["applicability"]["engine_sha256_read"] == snapshot["engine"]["sha256"]
            assert result["data"]["applicability"]["loaded_session"] == "not_checked"
            assert result["data"]["verified_contract"]["status"] == "unavailable"
            evidence["checks"].append("streamed installed engine identity matches; execution/contracts remain unclaimed")
        else:
            evidence["installed_engine_identity"] = "not_checked"
        assert sha(beryl) == evidence["compiler_sha256"]
        assert {name: sha(ROOT / name) for name in hashes} == hashes
        evidence["status"] = "success"
    except Exception as exc:
        evidence["status"] = "failure"
        evidence["error"] = repr(exc)
        raise
    finally:
        (work / "results.json").write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
