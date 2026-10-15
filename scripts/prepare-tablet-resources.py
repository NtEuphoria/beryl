#!/usr/bin/env python3
"""Capture the reviewed tablet resource inputs only; never compile or launch tools."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import re
import stat
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build"
PROFILE = "sparkos.tablet.selected-resource-source.v1"
MAX_FILE_BYTES = 8 * 1024 * 1024
MAX_TOTAL_BYTES = 16 * 1024 * 1024
MAX_TEXT_BYTES = 16 * 1024
MAX_ASSET_ENTRIES = 64
SHA = re.compile(r"[0-9a-f]{64}\Z")
SELECTED = {
    "Prefabs/SPK_Tablet.et": (593, "dabd491efd1b27cf49b311948c1215acf1982f06f6b6de8a0e9ea0e001ae0c22"),
    "Prefabs/SPK_Tablet.et.meta": (133, "7cf10f188f52b7724564b78e7999274854948665b48015ae130dcb7fea267b3a"),
    "Assets/Tablet/SPK_Tablet.xob": (605161, "7c0444ce12f0dae2d2d1b030c38d9c56f576a1eaa4a8269af7bcb424c1aea52d"),
    "Assets/Tablet/SPK_Tablet.xob.meta": (1466, "aecc3e22af19aa3c50b7beecbde13f2eaa9e0c5335ad55a85cde8afce06ff6ca"),
    "Assets/Tablet/SPK_Tablet.txo": (3235675, "24739df0fc55f7632eaade144bdf581898d363fa289445cc0fa2047f947b1585"),
    "Assets/Tablet/SPK_Tablet.fbx": (1114732, "8fd22da071c552266526289bbedbb223305e38141fc0eebb949ce6621a1b19a5"),
    "Assets/Tablet/Data/Material.emat": (15, "324a4d878cbd343d17e60f25455eca9dbc7b40dfab562a6e0b91e627fc43f255"),
    "Assets/Tablet/Data/Material.emat.meta": (319, "d320ffbe164b5ec6a4fa635769c229f6fc4fe31df371b52b9eaed8216ceb04c0"),
}
RESOURCE_NAMES = {
    "Prefabs/SPK_Tablet.et": "{B37EEB64E149CBAD}Prefabs/SPK_Tablet.et",
    "Assets/Tablet/SPK_Tablet.xob": "{BB50496D23063970}Assets/Tablet/SPK_Tablet.xob",
    "Assets/Tablet/Data/Material.emat": "{2E845CA43E3FFF43}Assets/Tablet/Data/Material.emat",
}
EXTERNAL_COMMON = [
    "{0877E7C4BB2B2C9A}Configs/System/ResourceTypes/PC/MeshObjectCommon.conf",
    "{9D5B6207F7628CE2}Configs/System/ResourceTypes/XBOX_ONE/MeshObjectCommon.conf",
    "{DD9F02115C764647}Configs/System/ResourceTypes/XBOX_SERIES/MeshObjectCommon.conf",
    "{53EC476BC921D99A}Configs/System/ResourceTypes/PS4/MeshObjectCommon.conf",
    "{F62AA8E7B8EA9D26}Configs/System/ResourceTypes/PS5/MeshObjectCommon.conf",
    "{3A5B3356978039E8}Configs/System/ResourceTypes/HEADLESS/MeshObjectCommon.conf",
]
EXPECTED_TEST_CASES = (
    "exact-copy-and-identities", "changed-source-before-copy", "changed-source-after-copy",
    "undeclared-texture", "missing-sidecar", "incorrect-native-resource-id", "incorrect-material-edge",
    "bounded-asset-enumeration", "file-size-admission", "aggregate-size-admission",
    "existing-output-preserved", "corrupt-copied-bytes", "failed-output-write", "output-path-containment",
    "symbolic-link-rejection", "hardlink-rejection", "changed-helper-identity",
)


class PreparationFailure(Exception):
    def __init__(self, message, status="failure", path=None):
        super().__init__(message)
        self.status, self.path = status, str(path) if path is not None else None


class FixtureUnavailable(Exception):
    def __init__(self, capability, reason):
        super().__init__(reason)
        self.capability = capability


def require(condition, message, status="failure", path=None):
    if not condition:
        raise PreparationFailure(message, status, path)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode("utf-8")


def no_links(path):
    path = Path(os.path.abspath(path))
    for part in (path, *path.parents):
        require(not part.is_symlink() and not (hasattr(part, "is_junction") and part.is_junction()),
                "Linked paths are not admitted", "stale_input", part)
        if part.exists():
            info = part.lstat()
            require(not (getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)),
                    "Reparse-point paths are not admitted", "stale_input", part)


def file_signature(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)


def read_checked(path, expected=None):
    no_links(path)
    require(path.is_file(), "Selected input is unavailable", "unavailable", path)
    before = path.stat()
    require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1,
            "Input must be a regular file with one link", "stale_input", path)
    require(0 <= before.st_size <= MAX_FILE_BYTES, "Selected file exceeds the byte budget", path=path)
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    with os.fdopen(os.open(path, flags), "rb") as stream:
        opened = os.fstat(stream.fileno())
        require(file_signature(opened) == file_signature(before), "Input changed while opening", "stale_input", path)
        raw = stream.read(MAX_FILE_BYTES + 1)
        after_handle = os.fstat(stream.fileno())
    no_links(path)
    after = path.stat()
    require(len(raw) <= MAX_FILE_BYTES and file_signature(before) == file_signature(after_handle) == file_signature(after),
            "Input changed during bounded read", "stale_input", path)
    identity = {"bytes": len(raw), "sha256": digest(raw)}
    if expected is not None:
        require(identity == {"bytes": expected[0], "sha256": expected[1]},
                "Selected input differs from the reviewed source profile", "stale_input", path)
    return raw, identity, file_signature(after)


def asset_selection(source, specification):
    folder = source / "Assets/Tablet"
    no_links(folder)
    require(folder.is_dir(), "Selected tablet asset directory is unavailable", "unavailable", folder)
    found, pending, entries = [], [folder], 0
    while pending:
        current = pending.pop()
        for item in sorted(current.iterdir()):
            entries += 1
            require(entries <= MAX_ASSET_ENTRIES, "Tablet asset entry budget exceeded", path=folder)
            no_links(item)
            if item.is_dir():
                pending.append(item)
            else:
                require(item.is_file(), "Unknown non-file asset entry", "stale_input", item)
                found.append(item.relative_to(source).as_posix())
    expected = sorted(name for name in specification if name.startswith("Assets/Tablet/"))
    require(sorted(found) == expected, "Tablet asset selection changed; new inputs need a reviewed profile", "stale_input", folder)
    return sorted(found)


def text(raw, path):
    require(len(raw) <= MAX_TEXT_BYTES, "Metadata text budget exceeded", path=path)
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise PreparationFailure("Selected metadata is not UTF-8", path=path) from exc


def reviewed_edges(data):
    """Bounded lexical checks on pinned inputs, not a general Enfusion parser."""
    for name, resource in RESOURCE_NAMES.items():
        meta = text(data[name + ".meta"], name + ".meta")
        names = re.findall(r'^\s*Name\s+"([^"\r\n]+)"\s*$', meta, re.M)
        require(names == [resource], "Metadata does not preserve the reviewed resource name", path=name + ".meta")
    prefab = text(data["Prefabs/SPK_Tablet.et"], "Prefabs/SPK_Tablet.et")
    objects = re.findall(r'\bObject\s+"([^"\r\n]+)"', prefab)
    require(objects == [RESOURCE_NAMES["Assets/Tablet/SPK_Tablet.xob"]], "Unexpected tablet model reference", path="Prefabs/SPK_Tablet.et")
    model_meta = text(data["Assets/Tablet/SPK_Tablet.xob.meta"], "Assets/Tablet/SPK_Tablet.xob.meta")
    materials = re.findall(r'\bAssignedMaterial\s+"([^"\r\n]+)"', model_meta)
    require(materials == [RESOURCE_NAMES["Assets/Tablet/Data/Material.emat"]], "Unexpected assigned material", path="Assets/Tablet/SPK_Tablet.xob.meta")
    common = re.findall(r':\s*"(\{[0-9A-F]{16}\}Configs/[^"\r\n]+)"', model_meta)
    require(common == EXTERNAL_COMMON, "Platform Common references changed", path="Assets/Tablet/SPK_Tablet.xob.meta")
    material = text(data["Assets/Tablet/Data/Material.emat"], "Assets/Tablet/Data/Material.emat")
    require(re.fullmatch(r'\s*MatPBRBasic\s*\{\s*\}\s*', material) is not None,
            "Material source needs a new dependency review", path="Assets/Tablet/Data/Material.emat")
    return {"status": "source_reviewed_not_engine_resolved", "resource_names": RESOURCE_NAMES,
            "selected_edges": [{"from": "Prefabs/SPK_Tablet.et", "to": RESOURCE_NAMES["Assets/Tablet/SPK_Tablet.xob"]},
                               {"from": "Assets/Tablet/SPK_Tablet.xob.meta", "to": RESOURCE_NAMES["Assets/Tablet/Data/Material.emat"]}],
            "external_base_references": [{"resource": item, "status": "unresolved_not_copied"} for item in common],
            "inline_subobject_ids": "not automatically treated as external resource edges",
            "validation": "lexical checks of the exact selected profile; not general file-format admission"}


def checked_write(path, raw, owned_root):
    require(path.is_relative_to(owned_root), "Output escapes the owned preparation directory", path=path)
    no_links(owned_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    no_links(path.parent)
    require(not path.exists() and not path.is_symlink(), "Output already exists; previous evidence is preserved", path=path)
    with path.open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    written, identity, _ = read_checked(path)
    require(written == raw and identity["sha256"] == digest(raw), "Checked output write did not preserve bytes", path=path)


def capture(source, work, specification=SELECTED, checkpoint=None, writer=checked_write):
    source = Path(os.path.abspath(source))
    no_links(source)
    require(source.is_dir(), "Source directory is unavailable", "unavailable", source)
    require(set(specification) == set(SELECTED) and all(type(size) is int and 0 <= size <= MAX_FILE_BYTES and SHA.fullmatch(sha)
            for size, sha in specification.values()), "Invalid bounded selected profile")
    require(sum(size for size, _ in specification.values()) <= MAX_TOTAL_BYTES, "Total source budget exceeded")
    selected = asset_selection(source, specification)
    data, original, signatures = {}, {}, {}
    for name in sorted(specification):
        raw, identity, signature = read_checked(source / name, specification[name])
        data[name], original[name], signatures[name] = raw, identity, signature
    graph = reviewed_edges(data)
    for name in sorted(data):
        writer(work / "resources" / name, data[name], work)
    if checkpoint is not None:
        checkpoint()
    require(asset_selection(source, specification) == selected, "Asset selection changed while copying", "stale_input")
    for name in sorted(specification):
        _, current, signature = read_checked(source / name, specification[name])
        require(current == original[name] and signature == signatures[name], "Source changed between observed capture checks", "stale_input", source / name)
        _, retained, _ = read_checked(work / "resources" / name, specification[name])
        require(retained == original[name], "Retained copy changed", "stale_input", name)
    fingerprint = digest(canonical(original))
    return {"source_root": str(source), "selected_files": original, "selected_file_count": len(original),
            "source_fingerprint": fingerprint, "retained_resource_fingerprint": fingerprint,
            "before_after": "selected bytes, file identities and directory selection matched at observed checks",
            "resource_graph": graph, "preserved_native_resource_ids": True,
            "unresolved": {"complete_resource_closure": "unverified", "binary_embedded_dependencies": "unverified",
                           "engine_imported_resource_availability": "unverified", "model_intermediate_freshness": "unverified",
                           "material_render_target_binding": "unverified", "external_base_resources": "unresolved_not_copied",
                           "standalone_texture": "none declared in selected material/profile; no inferred texture path",
                           "txo_role": "retained existing intermediate; binary format/import role not established",
                           "platform_admission": "unverified", "native_resource_registration": "not_run"}}


def owned_directory(prefix):
    no_links(ROOT)
    BUILD.mkdir(exist_ok=True)
    no_links(BUILD)
    require(BUILD.resolve().is_relative_to(ROOT), "Build directory escapes workspace")
    work = Path(tempfile.mkdtemp(prefix=prefix, dir=BUILD))
    require(work.resolve().is_relative_to(BUILD.resolve()), "Preparation directory escapes build workspace")
    return work


def pin_script(path):
    path = Path(os.path.abspath(path))
    raw, identity, signature = read_checked(path)
    return path, raw, identity, signature


def verify_script(snapshot):
    path, raw, identity, signature = snapshot
    current, current_identity, current_signature = read_checked(path, (identity["bytes"], identity["sha256"]))
    require(current == raw and current_identity == identity and current_signature == signature,
            "Preparation helper changed during the operation", "stale_input", path)


def envelope(operation, script):
    return {"schema_version": 1, "operation": operation, "stage": "source_capture", "status": "failure",
            "profile": PROFILE, "script_sha256": script[2]["sha256"], "script_identity": script[2],
            "scope": {"selected_source_copy": "not_run", "compiler": "not_run", "engine": "not_run",
                      "native_program": "not_run", "asset_import": "not_run", "complete_resource_closure": "unverified",
                      "resource_admission": "unverified", "installation": "unchanged", "policy_changes": "not_run"},
            "measurements": [], "limits": {"files": 8, "asset_entries": MAX_ASSET_ENTRIES,
                                            "per_file_bytes": MAX_FILE_BYTES, "total_bytes": MAX_TOTAL_BYTES}}


def save(work, result):
    result["result_path"] = str(work / "result.json")
    checked_write(work / "result.json", canonical(result), work)


def fixture(source):
    values = {
        "Prefabs/SPK_Tablet.et": ('GenericEntity {\n components {\n MeshObject { Object "' + RESOURCE_NAMES["Assets/Tablet/SPK_Tablet.xob"] + '" }\n }\n}\n').encode(),
        "Assets/Tablet/SPK_Tablet.xob": b"synthetic compiled-model fixture; not an engine asset",
        "Assets/Tablet/SPK_Tablet.txo": b"synthetic intermediate",
        "Assets/Tablet/SPK_Tablet.fbx": b"synthetic authoring input",
        "Assets/Tablet/Data/Material.emat": b"MatPBRBasic {\n}\n",
    }
    for name, resource in RESOURCE_NAMES.items():
        extra = ""
        if name.endswith(".xob"):
            extra = ' AssignedMaterial "' + RESOURCE_NAMES["Assets/Tablet/Data/Material.emat"] + '"\n'
            extra += "".join(' Common {} : "{}" {{ }}\n'.format(index, item) for index, item in enumerate(EXTERNAL_COMMON))
        values[name + ".meta"] = ('MetaFileClass {\n Name "' + resource + '"\n' + extra + '}\n').encode()
    for name, raw in values.items():
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    return {name: (len(raw), digest(raw)) for name, raw in values.items()}


def self_test(script):
    work = owned_directory("tablet resource tests & spaces-")
    result = envelope("verify.tablet_resource_preparation", script)
    result.update(stage="source_fixture_tests", cases=[], capability_unavailable=[])
    checked_write(work / "inputs/prepare-tablet-resources.py", script[1], work)
    def case(name, action):
        home = work / name
        home.mkdir()
        source, output = home / "source", home / "output"
        output.mkdir()
        specification = fixture(source)
        try:
            action(source, output, specification)
            result["cases"].append({"id": name, "status": "success", "scope": "synthetic filesystem fixture"})
        except FixtureUnavailable as exc:
            result["capability_unavailable"].append({"case_id": name, "capability": exc.capability, "reason": str(exc)})
            result["cases"].append({"id": name, "status": "unavailable", "capability": exc.capability, "reason": str(exc)})
        except Exception as exc:
            result["cases"].append({"id": name, "status": "failure", "failure": str(exc)})
    def fails(source, output, specification, status="failure", **kwargs):
        try:
            capture(source, output, specification, **kwargs)
        except PreparationFailure as exc:
            require(exc.status == status, "Wrong failure classification: " + exc.status)
            return
        raise AssertionError("Invalid preparation was accepted")
    def good(source, output, specification):
        receipt = capture(source, output, specification)
        require(receipt["selected_file_count"] == 8 and receipt["source_fingerprint"] == receipt["retained_resource_fingerprint"], "Wrong successful inventory")
        require(receipt["resource_graph"]["resource_names"] == RESOURCE_NAMES and len(receipt["resource_graph"]["external_base_references"]) == 6, "Lost native IDs/edges")
        require(receipt["unresolved"]["complete_resource_closure"] == "unverified", "Preparation claimed closure")
    case("exact-copy-and-identities", good)
    def changed(source, output, specification):
        (source / "Assets/Tablet/SPK_Tablet.xob").write_bytes(b"changed")
        fails(source, output, specification, "stale_input")
    case("changed-source-before-copy", changed)
    def during(source, output, specification):
        def mutate(): (source / "Assets/Tablet/SPK_Tablet.xob").write_bytes(b"changed during copy")
        fails(source, output, specification, "stale_input", checkpoint=mutate)
    case("changed-source-after-copy", during)
    def extra(source, output, specification):
        (source / "Assets/Tablet/new-texture.edds").write_bytes(b"new")
        fails(source, output, specification, "stale_input")
    case("undeclared-texture", extra)
    def missing(source, output, specification):
        (source / "Prefabs/SPK_Tablet.et.meta").unlink()
        fails(source, output, specification, "unavailable")
    case("missing-sidecar", missing)
    def wrong_id(source, output, specification):
        name = "Prefabs/SPK_Tablet.et.meta"
        raw = (source / name).read_bytes().replace(b"B37EEB64E149CBAD", b"0000000000000000")
        (source / name).write_bytes(raw)
        specification[name] = (len(raw), digest(raw))
        fails(source, output, specification)
    case("incorrect-native-resource-id", wrong_id)
    def wrong_edge(source, output, specification):
        name = "Assets/Tablet/SPK_Tablet.xob.meta"
        raw = (source / name).read_bytes().replace(b"2E845CA43E3FFF43", b"0000000000000000")
        (source / name).write_bytes(raw)
        specification[name] = (len(raw), digest(raw))
        fails(source, output, specification)
    case("incorrect-material-edge", wrong_edge)
    def limit(source, output, specification):
        for index in range(MAX_ASSET_ENTRIES): (source / "Assets/Tablet" / (str(index) + ".tmp")).write_bytes(b"")
        fails(source, output, specification)
    case("bounded-asset-enumeration", limit)
    def oversized(source, output, specification):
        specification["Assets/Tablet/SPK_Tablet.xob"] = (MAX_FILE_BYTES + 1, "0" * 64)
        fails(source, output, specification)
    case("file-size-admission", oversized)
    def aggregate(source, output, specification):
        for name in specification: specification[name] = (MAX_FILE_BYTES, "0" * 64)
        fails(source, output, specification)
    case("aggregate-size-admission", aggregate)
    def existing(source, output, specification):
        path = output / "resources/Prefabs/SPK_Tablet.et"
        path.parent.mkdir(parents=True)
        path.write_bytes(b"previous evidence")
        fails(source, output, specification)
        require(path.read_bytes() == b"previous evidence", "Previous output overwritten")
    case("existing-output-preserved", existing)
    def bad_write(source, output, specification):
        def writer(path, raw, owned):
            checked_write(path, raw, owned)
            path.write_bytes(b"corrupt copied resource")
        fails(source, output, specification, "stale_input", writer=writer)
    case("corrupt-copied-bytes", bad_write)
    def write_failure(source, output, specification):
        def writer(path, raw, owned): raise OSError("injected failed output write")
        try: capture(source, output, specification, writer=writer)
        except OSError: return
        raise AssertionError("Failed write admitted")
    case("failed-output-write", write_failure)
    def escape(source, output, specification):
        try: checked_write(source / "escape.tmp", b"must not write", output)
        except PreparationFailure: return
        raise AssertionError("Escaping output accepted")
    case("output-path-containment", escape)
    def linked(source, output, specification):
        name = "Assets/Tablet/SPK_Tablet.xob"
        path = source / name
        target = source / "retained-link-target"
        path.rename(target)
        try: path.symlink_to(target)
        except OSError as exc:
            raise FixtureUnavailable("create-symbolic-link", str(exc)) from exc
        fails(source, output, specification, "stale_input")
    case("symbolic-link-rejection", linked)
    def hardlinked(source, output, specification):
        path = source / "Prefabs/SPK_Tablet.et"
        try: os.link(path, source / "second-hardlink")
        except OSError as exc:
            raise FixtureUnavailable("create-hard-link", str(exc)) from exc
        fails(source, output, specification, "stale_input")
    case("hardlink-rejection", hardlinked)
    def changed_helper(source, output, specification):
        path = source / "helper.py"
        path.write_bytes(b"pinned fixture helper\n")
        snapshot = pin_script(path)
        path.write_bytes(b"changed fixture helper\n")
        try: verify_script(snapshot)
        except PreparationFailure as exc:
            require(exc.status == "stale_input", "Wrong helper drift classification")
            return
        raise AssertionError("Changed helper identity was accepted")
    case("changed-helper-identity", changed_helper)
    actual = [row["id"] for row in result["cases"]]
    require(tuple(actual) == EXPECTED_TEST_CASES and len(set(actual)) == len(actual), "Incomplete or duplicate test case set")
    failed = [row for row in result["cases"] if row["status"] == "failure"]
    unavailable = [row for row in result["cases"] if row["status"] == "unavailable"]
    result.update(status="failure" if failed else "unavailable" if unavailable else "success", expected_cases=list(EXPECTED_TEST_CASES),
                  passed_cases=sum(row["status"] == "success" for row in result["cases"]), failed_cases=len(failed),
                  unavailable_cases=len(unavailable), coverage="partial" if unavailable else "complete",
                  evidence_layer="synthetic filesystem fixtures; no engine file-format/import/runtime validation")
    try:
        verify_script(script)
        result["helper_before_after"] = "exact pinned bytes and file identity matched"
    except PreparationFailure as exc:
        result.update(status=exc.status, failure=str(exc), diagnostic_path=exc.path)
    save(work, result)
    print(str(work / "result.json"))
    return 0 if result["status"] == "success" else 2 if result["status"] == "unavailable" else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mesh-project", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    require(args.self_test != (args.mesh_project is not None), "Choose --self-test or --mesh-project exactly once")
    script = pin_script(Path(__file__))
    if args.self_test:
        return self_test(script)
    work = owned_directory("tablet resource snapshot & spaces-")
    result = envelope("prepare.tablet_resources", script)
    try:
        checked_write(work / "inputs/prepare-tablet-resources.py", script[1], work)
        result.update(capture(args.mesh_project, work))
        verify_script(script)
        result["helper_before_after"] = "exact pinned bytes and file identity matched"
        result["scope"]["selected_source_copy"] = "executed_success"
        result.update(status="success", success_means="exact reviewed selected-source copy; not resource admission or complete closure")
    except KeyboardInterrupt:
        result.update(status="cancelled", failure="Source capture cancelled; no candidate installation occurred")
    except Exception as exc:
        result.update(status=getattr(exc, "status", "failure"), failure=str(exc), diagnostic_path=getattr(exc, "path", None))
    save(work, result)
    print(str(work / "result.json"))
    return 0 if result["status"] == "success" else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except PreparationFailure as exc:
        print(json.dumps({"status": exc.status, "failure": str(exc), "path": exc.path}), file=sys.stderr)
        raise SystemExit(1)
