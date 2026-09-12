#!/usr/bin/env python3
"""Verify compiler-owned catalogue/context contracts without executing Beryl programs.

--write-doc regenerates docs/FEATURES.md from this compiler's catalogue. Otherwise
the generated document must already match. This does not install a compiler,
execute examples, resolve verification receipts or start Workbench.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent.parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def document(catalog, examples):
    def cell(value):
        return str(value).replace("|", "\\|").replace("\n", " ")
    lines = ["# Compiler capability catalogue", "",
        "Generated from `beryl context capabilities` and `beryl context examples`.",
        "Regenerate with `python scripts/verify-capabilities.py --beryl <compiler> --write-doc`.", "",
        f"Registry schema: 1. Metadata fingerprint: `{catalog['registry_fingerprint']}`.", "",
        "This inventory describes compiled implementation boundaries. It does not establish",
        "admission of a particular source set, local tool availability, current execution,",
        "or applicable verification evidence. Test groups identify obligations, not passing",
        "receipts. Use `context project` for actual source admission and the implementation",
        "state for separately identified historical evidence. Receipt resolution remains unimplemented.", "",
        "The repository paths below are discovery references. An installed compiler can list",
        "them without the source repository; it does not claim those files exist locally.", "",
        "| Capability | Implementation | Targets | Interface | Boundary |",
        "|---|---|---|---|---|"]
    for feature in catalog["entries"]:
        impl = feature["implementation"]
        lines.append("| " + " | ".join(map(cell, [f"`{feature['id']}`", impl["status"],
            ", ".join(impl["targets"]), impl["interface"], impl["bounds"]])) + " |")
    lines += ["", "## Example discovery", "",
        "Every command below is informational and requires the source repository and its",
        "admitted target environment. Catalogue discovery does not execute or verify it.", ""]
    for example in examples["examples"]:
        lines += [f"### {example['id']}", "", example["title"], "",
                  "Targets: " + ", ".join(example["targets"]) + ".", "",
                  example["usage"], "", example["bounds"], ""]
        lines += [f"- `{path}`" for path in example["sources"]] + [""]
    lines += ["## Regression obligations", "",
              "| Group | Suite source | Positive obligation | Negative obligation |",
              "|---|---|---|---|"]
    for group in catalog["test_groups"]:
        lines.append("| " + " | ".join(map(cell, [group["id"], group["source"],
            group["positive_obligation"], group["negative_obligation"]])) + " |")
    lines += ["", "## Compatibility and limits", "",
        "The context envelope remains version 1. Existing project/symbol/optimization",
        "fields remain present; the `catalogue` discovery field and the two catalogue",
        "topics are additive. The catalogue itself has an independent versioned identity.", "",
        "Implementation labels are `unavailable`, `experimental`, `partial`, and `bounded`.",
        "A partial capability is not a safety guarantee. An experimental interpreter does",
        "not release code generation. Target filters limit discovery and do not run admission.", "",
        "Registered optimization families remain proposed. No released Beryl optimization",
        "plan, current performance measurement, engine contract or Rust advantage is implied.", ""]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--beryl", required=True, type=Path)
    parser.add_argument("--write-doc", action="store_true")
    args = parser.parse_args()
    compiler = args.beryl.resolve(strict=True)
    (ROOT / "build").mkdir(exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="capability-context-", dir=ROOT / "build"))
    tracked = [Path(__file__), ROOT / "src/driver/features.c", ROOT / "src/driver/features.h",
               ROOT / "src/driver/context.c", ROOT / "tests/unit/test_capabilities.c"]
    before = {str(path): sha(path) for path in tracked}
    report = {"schema_version": 1, "status": "running", "compiler_sha256": sha(compiler),
              "inputs": before, "commands": [], "checks": [], "program_execution": "not_run",
              "engine_execution": "not_run", "document_write_requested": args.write_doc}
    print(f"Capability artifacts: {work}", flush=True)

    def run(*argv, expected=0):
        command = [str(compiler), "context", *argv]
        process = subprocess.run(command, cwd=work, capture_output=True,
                                 text=True, encoding="utf-8", errors="strict", timeout=30)
        report["commands"].append({"argv": command, "exit_code": process.returncode,
                                   "stdout": process.stdout, "stderr": process.stderr})
        assert process.returncode == expected, report["commands"][-1]
        reply = json.loads(process.stdout)
        assert reply["schema_version"] == 1 and reply["execution"] == "not_run"
        assert reply["compiler_fingerprint"] == report["compiler_sha256"]
        assert reply["sources"] == [] and reply["artifact_fingerprint"] is None
        assert not list(work.iterdir()), "read-only context created a file"
        return reply

    def passed(name):
        report["checks"].append(name)
        print(f"passed {name}", flush=True)

    def source_exists(relative):
        path = (ROOT / relative).resolve(strict=True)
        assert path.is_relative_to(ROOT.resolve()) and path.is_file(), relative
        return sha(path)

    try:
        catalogue = run("capabilities")
        assert catalogue == run("capabilities")
        catalog = catalogue["data"]
        example_data = run("examples")["data"]
        assert catalog["registry_fingerprint"] == example_data["registry_fingerprint"]
        assert len(catalog["registry_fingerprint"]) == 64
        entries = {entry["id"]: entry for entry in catalog["entries"]}
        groups = {group["id"]: group for group in catalog["test_groups"]}
        assert len(entries) == len(catalog["entries"]) and entries
        assert len(groups) == len(catalog["test_groups"]) and groups
        source_hashes = {}
        for feature in entries.values():
            assert feature["admission"]["status"] == "not_checked"
            assert feature["local_availability"] == {"status": "not_checked"}
            assert feature["applicable_evidence"]["status"] == "not_checked"
            assert feature["applicable_evidence"]["receipts"] == []
            assert all(key in entries for key in feature["dependencies"])
            assert all(key in groups for key in feature["test_groups"])
            if feature["implementation"]["status"] != "unavailable":
                assert feature["test_groups"]
            path = feature["implementation"]["source"]
            source_hashes[path] = source_exists(path)
        for group in groups.values():
            assert group["positive_obligation"] and group["negative_obligation"]
            assert group["execution"] == "not_run"
            source_hashes[group["source"]] = source_exists(group["source"])
        assert entries["ir.codegen"]["implementation"]["status"] == "unavailable"
        assert entries["optimizer.released"]["implementation"]["status"] == "unavailable"
        assert entries["native.owned_storage"]["implementation"]["status"] == "partial"
        assert catalog["released_plans"] == [] and catalog["measurements"] is None
        passed("deterministic catalogue with separate evidence, admission and implementation states")

        for target in ("native", "reference", "enfusion", "compiler", "tooling"):
            filtered = run("capabilities", "--target", target)["data"]
            assert filtered["registry_fingerprint"] == catalog["registry_fingerprint"]
            assert {entry["id"] for entry in filtered["entries"]} == {
                key for key, entry in entries.items() if target in entry["implementation"]["targets"]}
        one = run("capabilities", "ir.codegen", "--target", "native")["data"]
        assert len(one["entries"]) == 1 and one["entries"][0] == entries["ir.codegen"]
        passed("exact ID and target filtering do not perform source admission")

        example_ids = set()
        for example in example_data["examples"]:
            assert example["id"] not in example_ids
            example_ids.add(example["id"])
            assert example["source_identity"] == "not_checked" and example["execution"] == "not_run"
            assert example["applicable_evidence"] == {"status": "not_checked", "receipts": []}
            assert all(key in entries for key in example["features"])
            assert all(key in groups for key in example["test_groups"])
            for path in example["sources"]:
                source_hashes[path] = source_exists(path)
        native = run("examples", "arithmetic.native")["data"]["examples"]
        assert len(native) == 1 and native[0]["targets"] == ["native"]
        engine = run("examples", "--target", "enfusion")["data"]["examples"]
        assert {entry["id"] for entry in engine} == {"pid.complete"}
        passed("examples preserve their exact target domains and repository references")

        for argv in (("capabilities", "unknown"), ("examples", "unknown"),
                     ("capabilities", "--target", "unknown"), ("examples", "--target"),
                     ("capabilities", "--target", "native", "--target", "enfusion"),
                     ("capabilities", "ir.codegen", "extra.be"),
                     ("examples", "arithmetic.native", "--target", "enfusion"),
                     ("examples", "../outside"), ("capabilities", "--list")):
            failure = run(*argv, expected=1)
            assert failure["status"] == "failure" and failure["data"] is None
        passed("unknown selections, malformed options and incompatible targets fail")

        project = run("project")["data"]
        optimization = run("optimization", "--list")["data"]
        assert project["catalogue"]["registry_fingerprint"] == catalog["registry_fingerprint"]
        assert project["capabilities"]["native"]["status"] == "not_checked"
        assert project["capabilities"]["structured_IR"] == "not_released"
        assert project["optimization_families"] == optimization["optimization_families"]
        assert len(project["optimization_families"]) == 14
        for family in project["optimization_families"]:
            assert family["status"] == "proposed" and not family["released"] and not family["eligible"]
        passed("existing context fields and optimization family shape are preserved")

        output = ROOT / "docs/FEATURES.md"
        expected = document(catalog, example_data)
        if args.write_doc:
            output.write_text(expected, encoding="utf-8", newline="\n")
        assert output.read_text(encoding="utf-8") == expected, "FEATURES.md is stale; regenerate from the intended compiler"
        report["document_sha256"] = sha(output)
        report["registry_fingerprint"] = catalog["registry_fingerprint"]
        report["referenced_source_hashes"] = source_hashes
        assert before == {str(path): sha(path) for path in tracked}, "catalogue sources changed during verification"
        assert all(source_exists(path) == digest for path, digest in source_hashes.items())
        report["status"] = "success"
        passed("generated documentation matches compiler metadata and source inputs stayed unchanged")
    except Exception as error:
        report["status"] = "failure"
        report["error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        (work / "results.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
