#!/usr/bin/env python3
"""Capture compiler, tool, test and document inputs for an isolated verification.

This records source bytes only; it does not claim verification, capture external
engine dependencies or install an executable. Failed captures remain recorded.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import stat
import tempfile

ROOT = Path(__file__).resolve().parent.parent
FOLDERS = ("src", "runtime", "tests", "scripts", "examples", "lib", "packages", "schemas", "tools", "docs")
EXCLUDED = {"__pycache__", ".beryl-cache", ".beryl-mod", ".beryl-mcp", "node_modules", ".git"}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--label", default="delivery-candidate")
    args = parser.parse_args()
    if not re.fullmatch("[a-z][a-z0-9-]{0,60}", args.label):
        parser.error("label must be lowercase letters/digits/hyphens")
    files = [p for folder in FOLDERS for p in (ROOT / folder).rglob("*")
             if p.is_file() and not EXCLUDED.intersection(p.relative_to(ROOT).parts)]
    files += [p for p in ROOT.iterdir() if p.is_file() and p.suffix in (".md", ".toml", ".txt", ".json")]
    paths = sorted(set(files))
    (ROOT / "build").mkdir(exist_ok=True)
    target = Path(tempfile.mkdtemp(prefix=args.label + "-", dir=ROOT / "build"))
    record = {"schema_version": 1, "operation": "source_capture", "status": "running",
              "root": str(ROOT), "captured_root": str(target), "verification": "not_run", "files": {}}
    total = 0
    try:
        if len(paths) > 8192:
            raise RuntimeError("source capture file limit exceeded")
        for path in paths:
            relative = path.relative_to(ROOT)
            current = ROOT
            for part in relative.parts:
                current = current / part
                if current.is_symlink() or getattr(current.lstat(), "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
                    raise RuntimeError("linked capture input: " + str(relative))
            data = path.read_bytes()
            total += len(data)
            if total > 1024 * 1024 * 1024:
                raise RuntimeError("source capture byte limit exceeded")
            output = target / relative
            output.parent.mkdir(parents=True, exist_ok=True)
            with output.open("xb") as stream:
                stream.write(data)
            record["files"][relative.as_posix()] = {"sha256": sha(data), "bytes": len(data)}
        for relative, identity in record["files"].items():
            if sha((ROOT / relative).read_bytes()) != identity["sha256"] or sha((target / relative).read_bytes()) != identity["sha256"]:
                raise RuntimeError("source changed during capture: " + relative)
        record.update(status="success", total_bytes=total)
    except Exception as exc:
        record.update(status="failure", error=str(exc))
        raise
    finally:
        with (target / "snapshot.json").open("x", encoding="utf-8") as output:
            json.dump(record, output, indent=2)
            output.write("\n")
        print(str(target), flush=True)


if __name__ == "__main__":
    main()
