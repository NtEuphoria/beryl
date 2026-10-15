#!/usr/bin/env python3
"""Guarded compiler/tool activation with retained rollback bytes (Python stdlib).

This performs individually atomic replacements at a quiescent boundary, NOT a
multi-file transaction or protection against an adversarial concurrent writer.
The caller supplies a trusted, previously verified stage and explicit expected
prior hashes. No project code, build hook, installer, or engine is executed.

activate --build-dir BUILD --manifest REQUEST.json
rollback --build-dir BUILD --receipt BUILD/checkpoint-*/receipt.json
         --expected-current HASHES.json

The strict version-1 activation manifest has target_root, stage_root, and files.
Each file has path, sha256, expected_prior (a SHA256 or null for absent). Paths
are exactly the four MUTABLE paths and the complete legacy 21-file, component-
admission 24-file, or component-generation 25-file bundle, plus bundle.json.
No other payload sets are admitted. HASHES.json is exactly a MUTABLE hash/null map.
The returned receipt records where to find backups and the observed current
hashes for a subsequent explicitly reviewed rollback. Rollback retains bundles.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import re
import stat
import sys
import uuid

MUTABLE = ("beryl-tools/mod.py", "beryl-tools/mcp.py", "beryl-tools/active.json", "beryl.exe")
BUNDLE_FILES = {
    "mod.py", "process_job.py", "engine-compile.ps1", "beryl.mod.v1.schema.json",
    "scenarios.py", "map-cursor.c.in", "scenario-engine-run.ps1", "source_maps.py",
    "terrain_scenarios.py", "terrain-reference.c.txt", "terrain-reference.json", "terrain-adapter.c.in", "terrain-handler.c.in",
    "storage_scenarios.py", "array-storage.c.in", "canvas-retention.c.in",
    "terrain_measurements.py", "terrain-measurement.c.in", "terrain-adapter-v1.c.txt",
    "mcp_server.py", "beryl.analysis.v1.schema.json",
}
COMPONENT_FILES = {"component_contracts.py", "tablet-component-contracts.v1.json", "beryl.mod.v2.schema.json"}
GENERATION_FILES = {"component_generation.py"}
BUNDLE_PROFILES = (frozenset(BUNDLE_FILES), frozenset(BUNDLE_FILES | COMPONENT_FILES),
                   frozenset(BUNDLE_FILES | COMPONENT_FILES | GENERATION_FILES))
MAX_FILE = 32 * 1024 * 1024
MAX_TOTAL = 128 * 1024 * 1024
HASH = re.compile(r"[0-9a-f]{64}\Z")
OP = re.compile(r"checkpoint-[0-9a-f]{32}\Z")


class GuardError(RuntimeError):
    pass


def digest(data):
    return hashlib.sha256(data).hexdigest()


def need(condition, message):
    if not condition:
        raise GuardError(message)


def strict_object(pairs):
    result = {}
    for key, value in pairs:
        need(key not in result, "duplicate JSON member: " + key)
        result[key] = value
    return result


def parse(data):
    need(len(data) <= 1024 * 1024, "JSON input exceeds 1 MiB")
    try:
        return json.loads(data.decode("utf-8"), object_pairs_hook=strict_object,
                          parse_constant=lambda x: (_ for _ in ()).throw(GuardError("nonfinite JSON")))
    except (UnicodeError, ValueError, RecursionError) as error:
        raise GuardError("invalid bounded JSON: " + str(error)) from error


def encoded(value):
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n").encode("ascii")


def shape(value, keys, name):
    need(type(value) is dict and set(value) == set(keys), "invalid " + name + " members")


def hash_or_absent(value):
    return value is None or (type(value) is str and HASH.fullmatch(value) is not None)


def absolute(value):
    need(type(value) is str and Path(value).is_absolute(), "absolute directory path required")
    result = Path(os.path.abspath(value))
    # Do not resolve links before inspecting them.
    need(str(result) == str(Path(value)), "directory path must be normalized")
    return result


def attributes(path, directory=False):
    info = path.lstat()
    need(not stat.S_ISLNK(info.st_mode) and not (getattr(info, "st_file_attributes", 0) & 0x400),
         "symlink/reparse path rejected: " + str(path))
    if directory:
        need(stat.S_ISDIR(info.st_mode), "directory required: " + str(path))
    else:
        need(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, "single-link regular file required: " + str(path))
        need(info.st_size <= MAX_FILE, "file exceeds size bound: " + str(path))
    return info


def directory(path):
    for part in reversed((path, *path.parents)):
        attributes(part, True)


def read_file(path, absent=False):
    directory(path.parent)
    try:
        before = attributes(path)
    except FileNotFoundError:
        if absent:
            return None
        raise GuardError("missing file: " + str(path))
    with path.open("rb") as stream:
        opened = os.fstat(stream.fileno())
        need(opened.st_nlink == 1 and stat.S_ISREG(opened.st_mode), "file changed before read")
        need((before.st_dev, before.st_ino) == (opened.st_dev, opened.st_ino), "file replaced before read")
        data = stream.read(MAX_FILE + 1)
        final = os.fstat(stream.fileno())
    after = attributes(path)
    need(len(data) <= MAX_FILE and len(data) == before.st_size == final.st_size == after.st_size,
         "file changed length during read: " + str(path))
    need((before.st_dev, before.st_ino, before.st_mtime_ns) ==
         (after.st_dev, after.st_ino, after.st_mtime_ns) ==
         (final.st_dev, final.st_ino, final.st_mtime_ns), "file changed during read: " + str(path))
    return data


def state(path):
    data = read_file(path, True)
    return None if data is None else digest(data)


def create_file(path, data):
    directory(path.parent)
    with path.open("xb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    need(read_file(path) == data, "written bytes did not match: " + str(path))


def replace_file(path, data, expected, pending_root):
    need(state(path) == expected, "destination changed: " + str(path))
    pending = pending_root / ("pending-" + uuid.uuid4().hex)
    create_file(pending, data)
    need(state(path) == expected, "destination changed before replacement: " + str(path))
    os.replace(pending, path)
    need(state(path) == digest(data), "destination changed after replacement: " + str(path))


def write_receipt(path, value):
    previous = state(path)
    replace_file(path, encoded(value), previous, path.parent)


def current_map(root):
    return {name: state(root / name) for name in MUTABLE}


def bundle_files_for_destinations(paths, prefix, name):
    """Select from three fixed complete profiles before any manifest path is joined."""
    for profile in BUNDLE_PROFILES:
        allowed = set(MUTABLE) | {prefix + part for part in profile | {"bundle.json"}}
        if set(paths) == allowed:
            return profile
    raise GuardError(name + " contains unsupported destinations or incomplete bundle")


def validate_manifest(root, raw):
    request = parse(raw)
    shape(request, ("schema_version", "target_root", "stage_root", "files"), "manifest")
    need(type(request["schema_version"]) is int and request["schema_version"] == 1, "unsupported manifest schema")
    need(absolute(request["target_root"]) == root, "manifest target differs from explicit build directory")
    stage = absolute(request["stage_root"])
    need(root.name.lower() == "build", "target must be an explicit compiler-owned build directory")
    need(stage != root and stage not in root.parents and stage != root / "beryl-tools" and (root / "beryl-tools") not in stage.parents,
         "stage cannot overlap installed compiler/tool destinations")
    directory(root)
    directory(root / "beryl-tools")
    directory(stage)
    directory(stage / "beryl-tools")
    files = request["files"]
    need(type(files) is list and len(files) in {len(MUTABLE) + len(p) + 1 for p in BUNDLE_PROFILES},
         "complete fixed file set required")
    rows = {}
    for entry in files:
        shape(entry, ("path", "sha256", "expected_prior"), "file entry")
        path = entry["path"]
        need(type(path) is str and path not in rows, "duplicate/invalid destination path")
        need(type(entry["sha256"]) is str and HASH.fullmatch(entry["sha256"]) is not None,
             "staged hash required")
        need(hash_or_absent(entry["expected_prior"]), "explicit prior hash or null required")
        rows[path] = entry
    # Only inspect the active pointer after the names are bounded; no manifest
    # path is joined until it matches the derived fixed allowlist below.
    need(set(MUTABLE) <= set(rows), "four mutable installation files required")
    need(all(rows[p]["expected_prior"] is not None for p in MUTABLE if p != "beryl-tools/mcp.py"),
         "existing compiler, mod loader, and active pointer require expected prior hashes")
    active = read_file(stage / "beryl-tools/active.json")
    pointer = parse(active)
    shape(pointer, ("bundle",), "active pointer")
    bundle = pointer["bundle"]
    need(type(bundle) is str and HASH.fullmatch(bundle) is not None, "invalid bundle identity")
    prefix = "beryl-tools/" + bundle + "/"
    bundle_files = bundle_files_for_destinations(rows, prefix, "manifest")
    bundle_root = stage / "beryl-tools" / bundle
    directory(bundle_root)
    need({p.name for p in bundle_root.iterdir()} == bundle_files | {"bundle.json"}, "stage bundle has extra/missing entries")
    staged, previous = {}, {}
    total = 0
    for path in sorted(rows):
        content = read_file(stage / path)
        total += len(content)
        need(total <= MAX_TOTAL, "staged byte budget exceeded")
        need(digest(content) == rows[path]["sha256"], "staged hash mismatch: " + path)
        staged[path] = content
        if path.startswith(prefix):
            target_bundle = root / "beryl-tools" / bundle
            if os.path.lexists(target_bundle):
                directory(target_bundle)
                prior = read_file(root / path, True)
            else:
                need(not target_bundle.is_symlink(), "linked destination bundle")
                prior = None
        else:
            prior = read_file(root / path, True)
        previous[path] = prior
        actual = None if prior is None else digest(prior)
        need(actual == rows[path]["expected_prior"], "expected-prior mismatch: " + path)
        if path.startswith(prefix):
            need(prior is None or prior == content, "immutable bundle cannot be overwritten: " + path)
    hashes = parse(staged[prefix + "bundle.json"])
    shape(hashes, bundle_files, "bundle manifest")
    need(all(hashes[name] == digest(staged[prefix + name]) for name in bundle_files), "bundle payload identity mismatch")
    canonical = json.dumps(hashes, sort_keys=True, separators=(",", ":")).encode()
    need(digest(canonical) == bundle, "bundle directory does not match canonical payload identity")
    existing = root / "beryl-tools" / bundle
    if os.path.lexists(existing):
        need({p.name for p in existing.iterdir()} == bundle_files | {"bundle.json"}, "existing bundle has extra/missing entries")
    return request, stage, bundle, rows, staged, previous


def validate_current(root, expected):
    shape(expected, MUTABLE, "expected-current hashes")
    need(all(hash_or_absent(v) for v in expected.values()), "invalid expected-current hash")
    need(current_map(root) == expected, "current installation differs from explicit expected hashes")


def restore(root, operation, record, expected):
    validate_current(root, expected)
    entries = record["mutable"]
    backups = {}
    for path in MUTABLE:
        row = entries[path]
        prior = row["prior_sha256"]
        observed = expected[path]
        need(observed in (prior, row["installed_sha256"]), "unknown installation bytes block rollback: " + path)
        if prior is None:
            need(row["backup"] is None, "absent prior file must have no backup")
            backups[path] = None
        else:
            backup = read_file(operation / row["backup"])
            need(digest(backup) == prior, "rollback backup changed: " + path)
            backups[path] = backup
    # Restore the pointer/loaders first and compiler last. Quiescence is needed
    # during this sequence just as during activation.
    for path in MUTABLE:
        row = entries[path]
        destination = root / path
        need(state(destination) == expected[path], "concurrent change blocks rollback: " + path)
        if expected[path] == row["prior_sha256"]:
            continue
        if backups[path] is None:
            destination.unlink()
            need(state(destination) is None, "absent restoration failed")
        else:
            replace_file(destination, backups[path], expected[path], operation)
        expected[path] = row["prior_sha256"]


def activate(root, manifest, *, fault=None):
    """fault is a test-only callback, never a CLI/project-defined command."""
    raw = read_file(manifest)
    request, stage, bundle, rows, staged, previous = validate_manifest(root, raw)
    # The lock coordinates this helper only, not arbitrary compiler processes,
    # installers, editors, or writers. Existing locks fail; none are stolen.
    lock = root / ".checkpoint-lock"
    lock.mkdir()
    operation = root / ("checkpoint-" + uuid.uuid4().hex)
    try:
        operation.mkdir()
        create_file(operation / "manifest.json", raw)
        record = {"schema_version": 1, "operation": operation.name, "target_root": str(root),
                  "status": "prepared", "manifest_sha256": digest(raw), "bundle": bundle,
                  "mutable": {}, "attempted": [], "written": [], "error": None,
                  "limitation": "Individual replacements; requires quiescent writers. No multi-file atomicity or concurrent-writer proof."}
        for index, path in enumerate(MUTABLE):
            prior = previous[path]
            backup = None if prior is None else "previous-" + str(index) + ".bin"
            if prior is not None:
                create_file(operation / backup, prior)
            record["mutable"][path] = {"prior_sha256": rows[path]["expected_prior"],
                                      "installed_sha256": rows[path]["sha256"], "backup": backup}
        receipt = operation / "receipt.json"
        write_receipt(receipt, record)
        try:
            # Revalidate every staged/prior byte before the first installation
            # write, including any changes while backups were being prepared.
            need(read_file(manifest) == raw, "manifest changed during preparation")
            validate_manifest(root, raw)
            prefix = "beryl-tools/" + bundle + "/"
            destination_bundle = root / "beryl-tools" / bundle
            if not os.path.lexists(destination_bundle):
                pending_bundle = operation / "bundle"
                pending_bundle.mkdir()
                for path in sorted(staged):
                    if path.startswith(prefix):
                        create_file(pending_bundle / path[len(prefix):], staged[path])
                need(not os.path.lexists(destination_bundle), "bundle appeared during staging")
                os.rename(pending_bundle, destination_bundle)
            for path in MUTABLE:
                need(state(root / path) == rows[path]["expected_prior"], "destination changed before activation: " + path)
                record["attempted"].append(path)
                write_receipt(receipt, record)  # intention precedes replacement
                if fault:
                    fault("before_replace", path, root, record)
                replace_file(root / path, staged[path], rows[path]["expected_prior"], operation)
                record["written"].append(path)
                if fault:
                    fault("after_replace", path, root, record)
                write_receipt(receipt, record)
            validate_current(root, {p: rows[p]["sha256"] for p in MUTABLE})
            record["status"] = "activated"
            record["current_hashes"] = current_map(root)
            write_receipt(receipt, record)
            return receipt, record
        except BaseException as error:
            record["error"] = repr(error)
            try:
                observed = current_map(root)
                # Only a path for which replacement was journalled may contain
                # our new bytes. Unknown or unrelated changes block restoration.
                for path in MUTABLE:
                    permitted = {rows[path]["expected_prior"]}
                    if path in record["attempted"]:
                        permitted.add(rows[path]["sha256"])
                    need(observed[path] in permitted, "unknown bytes block automatic rollback: " + path)
                restore(root, operation, record, observed)
                record["status"] = "activation_failed_rolled_back"
            except BaseException as restore_error:
                record["status"] = "activation_failed_rollback_blocked"
                record["rollback_error"] = repr(restore_error)
            try:
                record["current_hashes"] = current_map(root)
                write_receipt(receipt, record)
            except BaseException as receipt_error:
                raise GuardError("activation failed; receipt update failed; inspect " + str(operation) + ": " + repr(receipt_error)) from error
            return receipt, record
    finally:
        lock.rmdir()


def rollback(root, receipt, expected_path):
    directory(root)
    need(root.name.lower() == "build", "target must be an explicit compiler-owned build directory")
    need(receipt.name == "receipt.json" and OP.fullmatch(receipt.parent.name) is not None and receipt.parent.parent == root,
         "receipt must be an operation directly inside the explicit build directory")
    operation = receipt.parent
    directory(operation)
    expected = parse(read_file(expected_path))
    record = parse(read_file(receipt))
    required = {"schema_version", "operation", "target_root", "status", "manifest_sha256", "bundle", "mutable", "attempted", "written", "error", "limitation"}
    need(type(record) is dict and required <= set(record) <= required | {"current_hashes", "rollback_error", "rollback_expected"}, "invalid receipt members")
    need(type(record["schema_version"]) is int and record["schema_version"] == 1 and record["operation"] == operation.name and absolute(record["target_root"]) == root,
         "receipt identity does not match target")
    raw = read_file(operation / "manifest.json")
    need(digest(raw) == record["manifest_sha256"], "receipt manifest changed")
    manifest = parse(raw)
    shape(manifest, ("schema_version", "target_root", "stage_root", "files"), "rollback manifest")
    need(type(manifest["schema_version"]) is int and manifest["schema_version"] == 1 and manifest["target_root"] == str(root), "rollback manifest target/schema mismatch")
    need(type(record["bundle"]) is str and HASH.fullmatch(record["bundle"]), "invalid rollback bundle")
    need(type(manifest["files"]) is list and len(manifest["files"]) in
         {len(MUTABLE) + len(p) + 1 for p in BUNDLE_PROFILES}, "invalid rollback manifest file count")
    rows = {}
    for row in manifest["files"]:
        shape(row, ("path", "sha256", "expected_prior"), "rollback manifest row")
        need(type(row["path"]) is str and row["path"] not in rows,
             "invalid rollback manifest path")
        need(type(row["sha256"]) is str and HASH.fullmatch(row["sha256"]) and hash_or_absent(row["expected_prior"]),
             "invalid rollback manifest hash")
        rows[row["path"]] = row
    bundle_files_for_destinations(rows, "beryl-tools/" + record["bundle"] + "/", "rollback manifest")
    shape(record["mutable"], MUTABLE, "receipt mutable files")
    for index, path in enumerate(MUTABLE):
        row = record["mutable"][path]
        shape(row, ("prior_sha256", "installed_sha256", "backup"), "rollback row")
        need(hash_or_absent(row["prior_sha256"]) and type(row["installed_sha256"]) is str and HASH.fullmatch(row["installed_sha256"]), "invalid receipt hashes")
        need(row["backup"] == (None if row["prior_sha256"] is None else "previous-" + str(index) + ".bin"), "invalid backup path")
        need(row["prior_sha256"] == rows[path]["expected_prior"] and row["installed_sha256"] == rows[path]["sha256"],
             "rollback receipt differs from preserved manifest")
    lock = root / ".checkpoint-lock"
    lock.mkdir()
    try:
        validate_current(root, expected)
        record["rollback_expected"] = dict(expected)
        write_receipt(receipt, record)
        try:
            restore(root, operation, record, expected)
            record["status"] = "rolled_back"
            record["current_hashes"] = current_map(root)
            write_receipt(receipt, record)
        except BaseException as error:
            record["status"] = "rollback_blocked"
            record["rollback_error"] = repr(error)
            write_receipt(receipt, record)
            raise
        return receipt, record
    finally:
        lock.rmdir()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    activation = sub.add_parser("activate")
    activation.add_argument("--build-dir", required=True)
    activation.add_argument("--manifest", type=Path, required=True)
    restoration = sub.add_parser("rollback")
    restoration.add_argument("--build-dir", required=True)
    restoration.add_argument("--receipt", type=Path, required=True)
    restoration.add_argument("--expected-current", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        root = absolute(args.build_dir)
        if args.command == "activate":
            receipt, value = activate(root, args.manifest.absolute())
        else:
            receipt, value = rollback(root, args.receipt.absolute(), args.expected_current.absolute())
        print(json.dumps({"status": value["status"], "receipt": str(receipt), "current_hashes": value.get("current_hashes")}))
        return 0 if value["status"] in ("activated", "rolled_back") else 1
    except (OSError, GuardError, ValueError, KeyError, TypeError, RecursionError) as error:
        print(json.dumps({"status": "failure", "error": str(error)}))
        return 1


if __name__ == "__main__":
    sys.dont_write_bytecode = True
    sys.exit(main())
