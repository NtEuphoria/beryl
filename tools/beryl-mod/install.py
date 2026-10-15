#!/usr/bin/env python3
"""Install a versioned trusted mod-tool bundle beside an existing Beryl compiler."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import uuid

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import mod

LEGACY_LOADER = b'''# Beryl installed-tool loader; project files cannot select the implementation.
import hashlib, json, pathlib, runpy
root = pathlib.Path(__file__).resolve().parent
active = json.loads((root / "active.json").read_text(encoding="utf-8"))
identity = active["bundle"]
if len(identity) != 64 or any(c not in "0123456789abcdef" for c in identity):
    raise SystemExit("invalid installed mod-tool identity")
bundle = root / identity
if bundle.is_symlink() or bundle.resolve().parent != root.resolve():
    raise SystemExit("invalid installed mod-tool location")
manifest = json.loads((bundle / "bundle.json").read_text(encoding="utf-8"))
expected = {"mod.py", "process_job.py", "engine-compile.ps1", "beryl.mod.v1.schema.json"}
if set(manifest) != expected:
    raise SystemExit("invalid installed mod-tool manifest")
actual = {}
for name in sorted(expected):
    path = bundle / name
    if path.is_symlink() or path.resolve().parent != bundle.resolve():
        raise SystemExit("linked installed mod-tool file")
    actual[name] = hashlib.sha256(path.read_bytes()).hexdigest()
encoded = json.dumps(actual, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
if actual != manifest or hashlib.sha256(encoded).hexdigest() != identity:
    raise SystemExit("installed mod-tool bytes changed")
runpy.run_path(str(bundle / "mod.py"), run_name="__main__")
'''

# Exact admitted file sets preserve rollback to a verified v1 bundle. Project
# descriptions cannot add loader modules or choose the trusted implementation.
MAP_LOADER = LEGACY_LOADER.replace(
    b'if set(manifest) != expected:\n',
    b'current = expected | {"scenarios.py", "map-cursor.c.in", "scenario-engine-run.ps1", "source_maps.py"}\n'
    b'if set(manifest) not in (expected, current):\n'
).replace(b'actual = {}\n', b'expected = set(manifest)\nactual = {}\n')

TERRAIN_LOADER = MAP_LOADER.replace(
    b'if set(manifest) not in (expected, current):\n',
    b'terrain = current | {"terrain_scenarios.py", "terrain-reference.c.txt", "terrain-reference.json", "terrain-adapter.c.in", "terrain-handler.c.in"}\n'
    b'if set(manifest) not in (expected, current, terrain):\n')

STORAGE_LOADER = TERRAIN_LOADER.replace(
    b'if set(manifest) not in (expected, current, terrain):\n',
    b'storage = terrain | {"storage_scenarios.py", "array-storage.c.in", "canvas-retention.c.in"}\n'
    b'if set(manifest) not in (expected, current, terrain, storage):\n')

MEASUREMENT_LOADER = STORAGE_LOADER.replace(
    b'if set(manifest) not in (expected, current, terrain, storage):\n',
    b'measurement = storage | {"terrain_measurements.py", "terrain-measurement.c.in", "terrain-adapter-v1.c.txt"}\n'
    b'if set(manifest) not in (expected, current, terrain, storage, measurement):\n')

LOADER = MEASUREMENT_LOADER.replace(
    b'if set(manifest) not in (expected, current, terrain, storage, measurement):\n',
    b'assistant = measurement | {"mcp_server.py", "beryl.analysis.v1.schema.json"}\n'
    b'if set(manifest) not in (expected, current, terrain, storage, measurement, assistant):\n')
LOADER = LOADER.replace(b'import hashlib, json, pathlib, runpy\n',
                       b'import hashlib, json, pathlib, runpy, sys\nsys.dont_write_bytecode = True\n')

ASSISTANT_LOADER = LOADER
ASSISTANT_MCP_LOADER = ASSISTANT_LOADER.replace(
    b'runpy.run_path(str(bundle / "mod.py"), run_name="__main__")\n',
    b'if "mcp_server.py" not in manifest:\n'
    b'    raise SystemExit("MCP unavailable in the selected historical tool bundle")\n'
    b'runpy.run_path(str(bundle / "mcp_server.py"), run_name="__main__")\n')

# Preserve the exact previous loaders above. Installation recognizes and backs
# up those bytes; changing this template does not change a tool-bundle identity.
LOADER = ASSISTANT_LOADER.replace(
    b'import hashlib, json, pathlib, runpy, sys\n',
    b'import hashlib, json, pathlib, runpy, sys, os, stat\n'
    b'def installed_bytes(path):\n'
    b'    before = path.lstat()\n'
    b'    if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or getattr(before, "st_file_attributes", 0) & 1024:\n'
    b'        raise SystemExit("installed tool input must be a regular, single-link, non-reparse file")\n'
    b'    with path.open("rb") as stream:\n'
    b'        opened = os.fstat(stream.fileno())\n'
    b'        if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino) or not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1:\n'
    b'            raise SystemExit("installed tool input changed before reading")\n'
    b'        data = stream.read(16 * 1024 * 1024 + 1)\n'
    b'    if len(data) > 16 * 1024 * 1024:\n'
    b'        raise SystemExit("installed tool input exceeds byte limit")\n'
    b'    return data\n'
    b'def unique_pairs(items):\n'
    b'    result = {}\n'
    b'    for key, value in items:\n'
    b'        if key in result:\n'
    b'            raise SystemExit("duplicate installed-tool JSON key")\n'
    b'        result[key] = value\n'
    b'    return result\n'
).replace(
    b'active = json.loads((root / "active.json").read_text(encoding="utf-8"))\n',
    b'active = json.loads(installed_bytes(root / "active.json"), object_pairs_hook=unique_pairs)\n'
    b'if type(active) is not dict or set(active) != {"bundle"} or type(active["bundle"]) is not str:\n'
    b'    raise SystemExit("invalid installed mod-tool pointer")\n'
).replace(
    b'if bundle.is_symlink() or bundle.resolve().parent != root.resolve():\n',
    b'if not bundle.is_dir() or bundle.is_symlink() or getattr(bundle.lstat(), "st_file_attributes", 0) & 1024 or bundle.resolve().parent != root.resolve():\n'
).replace(
    b'manifest = json.loads((bundle / "bundle.json").read_text(encoding="utf-8"))\n',
    b'manifest = json.loads(installed_bytes(bundle / "bundle.json"), object_pairs_hook=unique_pairs)\n'
    b'if type(manifest) is not dict:\n'
    b'    raise SystemExit("invalid installed mod-tool manifest")\n'
).replace(
    b'expected = set(manifest)\nactual = {}\n',
    b'expected = set(manifest)\n'
    b'if {p.name for p in bundle.iterdir()} != expected | {"bundle.json"}:\n'
    b'    raise SystemExit("installed mod-tool bundle contains untracked files")\n'
    b'actual = {}\n'
).replace(b'hashlib.sha256(path.read_bytes()).hexdigest()',
          b'hashlib.sha256(installed_bytes(path)).hexdigest()')

MCP_LOADER = LOADER.replace(
    b'runpy.run_path(str(bundle / "mod.py"), run_name="__main__")\n',
    b'if "mcp_server.py" not in manifest:\n'
    b'    raise SystemExit("MCP unavailable in the selected historical tool bundle")\n'
    b'runpy.run_path(str(bundle / "mcp_server.py"), run_name="__main__")\n')

# Preserve hardened 21-file loaders for exact rollback and guarded upgrades.
# Component admission adds data/schema/module files; projects cannot select
# another contract implementation or add arbitrary files to this bundle.
HARDENED_ASSISTANT_LOADER = LOADER
HARDENED_ASSISTANT_MCP_LOADER = MCP_LOADER
LOADER = LOADER.replace(
    b'if set(manifest) not in (expected, current, terrain, storage, measurement, assistant):\n',
    b'component = assistant | {"component_contracts.py", "tablet-component-contracts.v1.json", "beryl.mod.v2.schema.json"}\n'
    b'if set(manifest) not in (expected, current, terrain, storage, measurement, assistant, component):\n')
MCP_LOADER = LOADER.replace(
    b'runpy.run_path(str(bundle / "mod.py"), run_name="__main__")\n',
    b'if "mcp_server.py" not in manifest:\n'
    b'    raise SystemExit("MCP unavailable in the selected historical tool bundle")\n'
    b'runpy.run_path(str(bundle / "mcp_server.py"), run_name="__main__")\n')


# Preserve the exact 24-file admission loaders before extending the fixed set.
COMPONENT_ADMISSION_LOADER = LOADER
COMPONENT_ADMISSION_MCP_LOADER = MCP_LOADER
LOADER = LOADER.replace(
    b'if set(manifest) not in (expected, current, terrain, storage, measurement, assistant, component):\n',
    b'generation = component | {"component_generation.py"}\n'
    b'if set(manifest) not in (expected, current, terrain, storage, measurement, assistant, component, generation):\n')
MCP_LOADER = LOADER.replace(
    b'runpy.run_path(str(bundle / "mod.py"), run_name="__main__")\n',
    b'if "mcp_server.py" not in manifest:\n'
    b'    raise SystemExit("MCP unavailable in the selected historical tool bundle")\n'
    b'runpy.run_path(str(bundle / "mcp_server.py"), run_name="__main__")\n')


def read_regular(path):
    path = Path(path)
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or getattr(before, "st_file_attributes", 0) & 1024:
        raise RuntimeError("Installed input must be a regular, single-link, non-reparse file: " + str(path))
    with path.open("rb") as stream:
        opened = os.fstat(stream.fileno())
        if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino) or not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1:
            raise RuntimeError("Installed input changed before reading: " + str(path))
        data = stream.read(mod.MAX_FILE + 1)
    if len(data) > mod.MAX_FILE:
        raise RuntimeError("Installed input exceeds byte limit: " + str(path))
    return data


def existing_bytes(path):
    return read_regular(path) if os.path.lexists(path) else None


def write_pending(root, data):
    path = root / ("pending-" + uuid.uuid4().hex)
    with path.open("xb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    return path


def preserve_backup(path, data):
    existing = existing_bytes(path)
    if existing is not None:
        if existing != data:
            raise RuntimeError("Prior loader backup changed")
    else:
        with path.open("xb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())


def install(compiler):
    compiler = compiler.resolve(strict=True)
    compiler_bytes = read_regular(compiler)
    root = compiler.parent / "beryl-tools"
    if os.path.lexists(root) and (not root.is_dir() or root.is_symlink() or getattr(root.lstat(), "st_file_attributes", 0) & 1024):
        raise RuntimeError("Tool installation root cannot be a link or non-directory")
    root.mkdir(exist_ok=True)
    lock = root / ".install-lock"
    lock.mkdir()
    changed = []
    controls = {}
    try:
        # Validate all existing control files before changing either loader or
        # the active pointer. An unknown MCP loader cannot partially upgrade mod.
        loader, mcp_loader, active = (root / name for name in ("mod.py", "mcp.py", "active.json"))
        prior_loader, prior_mcp, prior_active = (existing_bytes(path) for path in (loader, mcp_loader, active))
        known_mod = (LOADER, COMPONENT_ADMISSION_LOADER, HARDENED_ASSISTANT_LOADER, ASSISTANT_LOADER, MEASUREMENT_LOADER, STORAGE_LOADER, TERRAIN_LOADER, MAP_LOADER, LEGACY_LOADER)
        if prior_loader is not None and prior_loader not in known_mod:
            raise RuntimeError("Refusing to replace an unrecognized installed loader")
        if prior_mcp is not None and prior_mcp not in (MCP_LOADER, COMPONENT_ADMISSION_MCP_LOADER, HARDENED_ASSISTANT_MCP_LOADER, ASSISTANT_MCP_LOADER):
            raise RuntimeError("Refusing to replace an unrecognized MCP loader")
        previous = mod.parse(prior_active) if prior_active is not None else None
        if previous is not None and (type(previous) is not dict or set(previous) != {"bundle"} or type(previous["bundle"]) is not str or len(previous["bundle"]) != 64 or any(c not in "0123456789abcdef" for c in previous["bundle"])):
            raise RuntimeError("Invalid existing installed tool pointer")
        controls = {loader: prior_loader, mcp_loader: prior_mcp, active: prior_active}

        paths = mod.bundle_paths()
        data = {path.name: read_regular(path) for path in paths}
        hashes = {name: mod.digest(value) for name, value in data.items()}
        identity = mod.digest(mod.canonical(hashes))
        destination = root / identity
        if os.path.lexists(destination):
            if not destination.is_dir() or destination.is_symlink() or getattr(destination.lstat(), "st_file_attributes", 0) & 1024:
                raise RuntimeError("Existing versioned bundle was modified")
            if any(read_regular(destination / name) != value for name, value in data.items()):
                raise RuntimeError("Existing versioned bundle was modified")
            if mod.parse(read_regular(destination / "bundle.json")) != hashes:
                raise RuntimeError("Existing versioned bundle manifest was modified")
            if {p.name for p in destination.iterdir()} != set(hashes) | {"bundle.json"}:
                raise RuntimeError("Existing versioned bundle contains untracked files")
        else:
            temporary = root / ("install-" + uuid.uuid4().hex)
            temporary.mkdir()
            for name, value in data.items():
                with (temporary / name).open("xb") as stream:
                    stream.write(value)
                    stream.flush()
                    os.fsync(stream.fileno())
            mod.write_json(temporary / "bundle.json", hashes)
            os.rename(temporary, destination)

        if prior_loader is not None and prior_loader != LOADER:
            generation = "v8" if prior_loader == COMPONENT_ADMISSION_LOADER else "v7" if prior_loader == HARDENED_ASSISTANT_LOADER else "v6" if prior_loader == ASSISTANT_LOADER else "v1" if prior_loader == LEGACY_LOADER else "v2" if prior_loader == MAP_LOADER else "v3" if prior_loader == TERRAIN_LOADER else "v4" if prior_loader == STORAGE_LOADER else "v5"
            preserve_backup(root / ("loader-" + generation + "-" + mod.digest(prior_loader) + ".py"), prior_loader)
        if prior_mcp is not None and prior_mcp != MCP_LOADER:
            preserve_backup(root / ("mcp-loader-v1-" + mod.digest(prior_mcp) + ".py"), prior_mcp)

        # Prepare both loader replacements and durable intent before changing
        # controls. The active-pointer replacement is last. An intent receipt
        # records an attempted activation, not a claim that its commit executed.
        replacements = [(path, wanted, write_pending(root, wanted)) for path, wanted in
                        ((loader, LOADER), (mcp_loader, MCP_LOADER)) if controls[path] != wanted]
        new_active = (json.dumps({"bundle": identity}, indent=2, ensure_ascii=True) + "\n").encode()
        active_pending = write_pending(root, new_active)
        record = {"schema_version": 1, "stage": "activation_intent", "bundle": identity, "previous": previous,
                  "previous_loader_sha256": mod.digest(prior_loader) if prior_loader else None,
                  "previous_mcp_loader_sha256": mod.digest(prior_mcp) if prior_mcp else None,
                  "loader_sha256": mod.digest(LOADER), "mcp_loader_sha256": mod.digest(MCP_LOADER),
                  "compiler_sha256": mod.digest(compiler_bytes)}
        receipt = root / ("installation-" + uuid.uuid4().hex + ".json")
        mod.write_json(receipt, record)
        for path, wanted, pending in replacements + [(active, new_active, active_pending)]:
            if existing_bytes(path) != controls[path]:
                raise RuntimeError("Installed control changed during activation")
            # Register the attempt before the rename: a caught interruption or
            # wrapper failure can happen after the OS has committed replacement.
            changed.append((path, wanted))
            os.replace(pending, path)
        answer = {"status": "success", "bundle": identity, "path": str(root), "previous": previous,
                  "activation_intent": str(receipt)}
        print(json.dumps(answer, indent=2), flush=True)
        return answer
    except BaseException:
        # Restore only bytes that still match this install attempt. Concurrent
        # external edits are never silently overwritten during rollback.
        for path, wanted in reversed(changed):
            current = existing_bytes(path)
            previous_bytes = controls[path]
            if current == previous_bytes:
                continue  # The attempted replacement did not commit.
            if current != wanted:
                raise RuntimeError("Installed control changed during rollback; retained installation evidence")
            if previous_bytes is None:
                path.unlink()
            else:
                os.replace(write_pending(root, previous_bytes), path)
        raise
    finally:
        lock.rmdir()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", type=Path, required=True)
    args = parser.parse_args()
    install(args.compiler)


if __name__ == "__main__":
    main()
