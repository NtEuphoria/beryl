#!/usr/bin/env python3
"""Capture selected installed Doxygen declarations; generate a read-only C registry.

This is an offline maintainer tool. Ordinary compilation and context lookup do
not invoke Python, the editor, project scripts, or a model. A declaration is not
a lifetime/effect contract. Regeneration never imports old semantic annotations.
"""
import argparse
import hashlib
import html
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT = Path(__file__).with_name("snapshot.json")
GENERATED = ROOT / "src/driver/binding_registry.inc"
SELECTION = {
    "Math": ("interfaceMath.html", "Min Max Clamp MinInt MaxInt ClampInt AbsInt AbsFloat Sqrt"),
    "array": ("interfacearray-1-g.html", "Count IsEmpty Clear Compact Set Get Insert InsertAll Remove RemoveOrdered Resize Reserve Copy Swap"),
    "CanvasWidget": ("interfaceCanvasWidget.html", "SetDrawCommands"),
    "TriMeshDrawCommand": ("interfaceTriMeshDrawCommand.html", "m_iColor m_Vertices m_Indices m_fUVScale m_pTexture"),
    "System": ("interfaceSystem.html", "GetTickCount MemoryAllocationCount MemoryAllocationKB"),
    "WorkspaceWidget": ("interfaceWorkspaceWidget.html", "CreateWidget CreateWidgetInWorkspace"),
    "Game": ("interfaceGame.html", "GetWorkspace"),
}
ROW = re.compile(r'<tr class="memitem:[^"<>]+"[^<>]*><td class="memItemLeft">(?P<left>.*?)</td><td class="memItemRight">(?P<right>.*?)</td></tr>', re.S)
MEMBER = re.compile(r'^<a class="el" href="#(?P<anchor>[A-Za-z0-9_]+)">(?P<name>[A-Za-z_][A-Za-z0-9_]*)</a>(?P<tail>.*)$', re.S)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def plain(value):
    # The supported Doxygen member summary uses links and spans, not scripts.
    if re.search(r"<(script|style)\b", value, re.I):
        raise ValueError("executable markup in a declaration")
    return " ".join(html.unescape(re.sub(r"<[^>]*>", "", value)).split())


def extract(data, owner, filename, names):
    if not 0 < len(data) <= 8 * 1024 * 1024:
        raise ValueError("API document must contain 1 byte through 8 MiB")
    text = data.decode("utf-8", errors="strict")
    if '<meta name="generator" content="Doxygen 1.16.1"/>' not in text:
        raise ValueError("unsupported API document generator/layout")
    found = {}
    for row in ROW.finditer(text):
        member = MEMBER.fullmatch(row["right"])
        if not member or member["name"] not in names:
            continue
        name = member["name"]
        if name in found:
            raise ValueError(f"duplicate or overloaded selection: {owner}.{name}")
        left, tail = plain(row["left"]), plain(member["tail"])
        if not left or len(left) + len(tail) > 4096:
            raise ValueError("invalid declaration size")
        fragment = row[0].encode("utf-8")
        offset = len(text[:row.start()].encode("utf-8"))
        found[name] = {
            "name": f"{owner}.{name}", "owner": owner,
            "signature": f"{left} {name}" + (" " + tail if tail else ""),
            "kind": "method" if tail.startswith("(") else "field",
            "source": {"document": filename, "document_sha256": digest(data),
                       "anchor": member["anchor"], "byte_offset": offset,
                       "byte_length": len(fragment), "line": data[:offset].count(b"\n") + 1,
                       "fragment_sha256": digest(fragment)},
        }
    if set(found) != set(names):
        raise ValueError(f"missing selected declarations for {owner}: {sorted(set(names) - set(found))}")
    return [found[name] for name in sorted(found)]


def validate(snapshot):
    if set(snapshot) != {"schema_version", "scope", "engine", "extractor_sha256", "declarations"} or type(snapshot["schema_version"]) is not int or snapshot["schema_version"] != 1:
        raise ValueError("invalid registry schema")
    if snapshot["scope"] != "selected installed EnfusionScriptAPI declarations; no semantic contracts":
        raise ValueError("invalid registry scope")
    engine = snapshot["engine"]
    if set(engine) != {"version", "sha256", "bytes"} or not re.fullmatch(r"[0-9]+(?:\.[0-9]+){1,4}", engine["version"]):
        raise ValueError("invalid engine identity")
    if type(engine["bytes"]) is not int or not 0 < engine["bytes"] <= 1024 * 1024 * 1024:
        raise ValueError("invalid engine size")
    hashes = [engine["sha256"], snapshot["extractor_sha256"]]
    expected = {f"{owner}.{name}" for owner, (_, names) in SELECTION.items() for name in names.split()}
    rows = snapshot["declarations"]
    if len(rows) != len(expected) or {row["name"] for row in rows} != expected:
        raise ValueError("registry selections changed or duplicated")
    document_hashes = {}
    for row in rows:
        if set(row) != {"name", "owner", "signature", "kind", "source"} or row["owner"] not in SELECTION or row["name"].rsplit(".", 1)[0] != row["owner"]:
            raise ValueError("invalid declaration fields")
        if row["kind"] not in ("method", "field") or not isinstance(row["signature"], str) or not 0 < len(row["signature"]) <= 4096:
            raise ValueError("invalid signature")
        src = row["source"]
        if set(src) != {"document", "document_sha256", "anchor", "byte_offset", "byte_length", "line", "fragment_sha256"}:
            raise ValueError("invalid source origin")
        if src["document"] != SELECTION[row["owner"]][0] or not re.fullmatch(r"[A-Za-z0-9_]+", src["anchor"]):
            raise ValueError("invalid document path or anchor")
        if any(type(src[key]) is not int for key in ("byte_offset", "byte_length", "line")) or not (0 <= src["byte_offset"] < 8 * 1024 * 1024 and 0 < src["byte_length"] <= 32768 and src["byte_offset"] + src["byte_length"] <= 8 * 1024 * 1024 and src["line"] > 0):
            raise ValueError("invalid source span")
        hashes += [src["document_sha256"], src["fragment_sha256"]]
        previous = document_hashes.setdefault(src["document"], src["document_sha256"])
        if previous != src["document_sha256"]:
            raise ValueError("one API document has conflicting source fingerprints")
    if any(not isinstance(value, str) or not re.fullmatch(r"[a-f0-9]{64}", value) for value in hashes):
        raise ValueError("invalid SHA-256")
    if rows != sorted(rows, key=lambda row: row["name"]):
        raise ValueError("registry must be deterministically ordered")


def render(snapshot):
    validate(snapshot)
    quote = lambda value: json.dumps(value, ensure_ascii=True)
    lines = ["/* Generated by tools/beryl-bindings/generate.py; do not edit. */",
             "static const char registry_sha256[] = " + quote(digest(canonical(snapshot).encode())) + ";",
             "static const char registry_engine_version[] = " + quote(snapshot["engine"]["version"]) + ";",
             "static const char registry_engine_sha256[] = " + quote(snapshot["engine"]["sha256"]) + ";",
             "static const BindingRow registry_rows[] = {"]
    for row in snapshot["declarations"]:
        lines.append("    {" + ", ".join(quote(value) for value in (row["name"], row["owner"], row["source"]["document"], row["source"]["document_sha256"], canonical(row))) + "},")
    lines += ["};", ""]
    return "\n".join(lines)


def no_duplicates(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate JSON field")
        value[key] = item
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="compare shipped snapshot with generated C; no installed engine needed")
    parser.add_argument("--api-root", type=Path)
    parser.add_argument("--engine-executable", type=Path)
    parser.add_argument("--engine-version")
    args = parser.parse_args()
    if args.check:
        if any((args.api_root, args.engine_executable, args.engine_version)):
            parser.error("--check does not extract installed files")
        if SNAPSHOT.stat().st_size > 4 * 1024 * 1024:
            raise ValueError("oversized snapshot")
        snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"), object_pairs_hook=no_duplicates)
        if GENERATED.read_bytes() != render(snapshot).encode("utf-8"):
            raise ValueError("generated registry differs from its snapshot")
        if snapshot["extractor_sha256"] != digest(Path(__file__).read_bytes()):
            raise ValueError("extractor changed; recapture and review the snapshot")
        print(f"verified {len(snapshot['declarations'])} snapshot declarations")
        return
    if not all((args.api_root, args.engine_executable, args.engine_version)):
        parser.error("extraction requires --api-root, --engine-executable, and --engine-version")
    declarations = []
    for owner, (filename, names) in SELECTION.items():
        path = args.api_root / filename
        if path.stat().st_size > 8 * 1024 * 1024:
            raise ValueError("oversized installed document")
        with path.open("rb") as source:
            declarations += extract(source.read(8 * 1024 * 1024 + 1), owner, filename, names.split())
    if not 0 < args.engine_executable.stat().st_size <= 1024 * 1024 * 1024:
        raise ValueError("engine executable size outside capture bound")
    engine_hash, engine_size = hashlib.sha256(), 0
    with args.engine_executable.open("rb") as executable:
        while chunk := executable.read(1024 * 1024):
            engine_size += len(chunk)
            if engine_size > 1024 * 1024 * 1024:
                raise ValueError("engine grew beyond capture bound")
            engine_hash.update(chunk)
    if not engine_size:
        raise ValueError("engine became empty during capture")
    snapshot = {"schema_version": 1, "scope": "selected installed EnfusionScriptAPI declarations; no semantic contracts",
                "engine": {"version": args.engine_version, "sha256": engine_hash.hexdigest(), "bytes": engine_size},
                "extractor_sha256": digest(Path(__file__).read_bytes()),
                "declarations": sorted(declarations, key=lambda row: row["name"])}
    generated = render(snapshot)
    # Validate all inputs before replacing either source-owned output. These are
    # build inputs, not a live install; --check detects interrupted pair updates.
    SNAPSHOT.write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8", newline="\n")
    GENERATED.write_text(generated, encoding="utf-8", newline="\n")
    print(f"captured {len(declarations)} declarations; no engine program executed")


if __name__ == "__main__":
    main()
