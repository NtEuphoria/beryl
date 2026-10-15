#!/usr/bin/env python3
"""Prepare an isolated source-layered world; native readiness is a separate gate.

Two explicit profiles are available: startup-cli and module-netapi-registered.
The registered profile remains the default; neither profile falls back to the
other. The original eight-file prepared addon and compiler output remain intact.
This is a source-backed format experiment, not engine-authored serialization.
"""
from pathlib import Path
import argparse
import copy
import importlib.util
import json
import sys
import tempfile
import zlib

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
BASE_PATH = ROOT / "scripts/verify-workbench-startup.py"
spec = importlib.util.spec_from_file_location("layered_startup_foundation", BASE_PATH)
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
mod, bounded = base.mod, base.bounded
require, identity, write, saved = base.require, base.identity, base.write, base.saved
PACKAGE = ROOT / "packages/sparkos/workbench-layered-world"
LEGACY_RECEIPT = ROOT / "build/component callbacks & spaces-gryodekv/results.json"
LEGACY_SHA = "d45aa8d6d24b83cb1dec7908d21471143fa184e71e008ae76d0b5dbc1ac91437"
OPENING = "module-netapi-registered"
OPENINGS = ("startup-cli", OPENING)
FORMAT = "source-layered-v1"
LAYER = "worlds/BerylCallbackProbe_Layers/default.layer"
WORLD_BYTES = b"Layer default {\n Index 0\n}\n"
LAYER_BYTES = b"GenericWorldEntity world {\n}\n"
CONTRACT_SHA = "461b4c338e29ef7b9105e1e39f92d66e6861b112f8a77bd45046413600d0e45e"
CONTRACT_CANONICAL_SHA = "cc2e9df5b896e27cd7b8e21e2e9750a4ea11b866a3cb98fc310129fa30c1817a"
SOURCE_SHA = "528602403fa19c909d450394bab04ad582b20cd89de0c1962b394249d269071c"
PACKED_SHA = "67063d478bfd438eec97ed3ab18d2b7eddaef17751a8bb6eac5065395b327a6c"
STAGE_CASES = ("stage.exact-ten", "stage.original-unchanged", "stage.meta-preserved",
              "stage.missing-original", "stage.extra-original-key", "stage.invalid-hash",
              "stage.changed-original", "stage.extra-original-file", "stage.existing-destination",
              "stage.wrong-world-template", "stage.wrong-layer-template", "stage.legacy-nine-distinct")
PROFILE_CASES = ("profile.registered-default", "profile.cli-wire", "profile.distinct-token",
                 "profile.distinct-render", "profile.contract-bound-token", "profile.unknown-rejected")
SELF_CASES = STAGE_CASES + PROFILE_CASES


def profile_wire(opening):
    require(type(opening) is str and opening in OPENINGS,
            "Unknown layered-world opening profile", "stale_input")
    return base.OPENING_PROFILES[opening]


def profile_token(original_files, world, layer, template, addon, opening=OPENING,
                  source_contract_sha256=CONTRACT_SHA):
    profile_wire(opening)
    require(source_contract_sha256 == CONTRACT_SHA,
            "Layered token source-contract identity differs", "stale_input")
    return mod.digest(mod.canonical({"receipt": LEGACY_SHA, "files": original_files,
        "world": mod.digest(world), "layer": mod.digest(layer), "handler": mod.digest(template),
        "addon": str(addon), "profile": opening, "fixture_format": FORMAT,
        "source_contract_sha256": source_contract_sha256}))


def stage(original, original_files, addon, world, layer, handler):
    require(type(original_files) is dict and set(original_files) == base.BASE_FILES and
            all(type(v) is str and base.HASH.fullmatch(v) for v in original_files.values()),
            "Original stage is not the exact eight-file profile", "stale_input")
    require(world == WORLD_BYTES and layer == LAYER_BYTES,
            "Layered source templates differ from the installed fixed format", "stale_input")
    require(not addon.exists(), "Layered destination must be a new owned addon", "stale_input")
    bounded.exact_tree(original, original_files)
    expected = {**original_files, base.REL_WORLD: mod.digest(world), LAYER: mod.digest(layer),
                base.HANDLER_PATH: mod.digest(handler)}
    for name, fingerprint in original_files.items():
        data = mod.read(mod.safe_path(original, name, True))
        require(mod.digest(data) == fingerprint, "Original input changed while copying", "stale_input")
        if name != base.REL_WORLD:
            write(mod.safe_path(addon, name), data)
    # Replacement is explicit before the manifest. The old world is never
    # overwritten in either the selected addon or its retained artifact.
    for name, data in ((base.REL_WORLD, world), (LAYER, layer), (base.HANDLER_PATH, handler)):
        write(mod.safe_path(addon, name), data)
    actual, dirs = bounded.tree_files(addon)
    require(actual == expected and set(actual) == base.runtime_input_files(FORMAT) and
            sorted(dirs) == sorted(bounded.expected_directories(expected)),
            "Layered stage differs from the independently declared exact ten inputs", "stale_input")
    bounded.exact_tree(original, original_files)
    return expected, sorted(dirs)


def validate_contract(value):
    """Admit this exact immutable contract, not a generic authoring policy."""
    # This checkpoint binds every nested field, including provenance and
    # limitations. A later contract revision requires its own source freeze.
    try:
        exact = mod.digest(mod.canonical(value)) == CONTRACT_CANONICAL_SHA
    except (TypeError, ValueError):
        exact = False
    require(exact, "Immutable source-contract content differs", "stale_input")
    require(type(value) is dict and set(value) == {"schema_version", "profile", "state", "world_name", "engine_authored",
            "engine_loaded", "native_creation_helper_called", "source_basis", "primary_declaration", "files", "preservation", "limitations"} and
            type(value.get("schema_version")) is int and value["schema_version"] == 1 and
            value.get("profile") == "enfusion.layered-minimal-world.source.v1" and value.get("world_name") == "BerylCallbackProbe" and
            value.get("state") == "source_supported_experimental" and
            all(value.get(k) is False for k in ("engine_authored", "engine_loaded", "native_creation_helper_called")),
            "Source contract claims an unsupported profile/evidence state", "stale_input")
    sb, declaration, files = value["source_basis"], value["primary_declaration"], value["files"]
    require(type(sb) is dict and sb.get("decoded_sha256") == SOURCE_SHA and sb.get("packed_sha256") == PACKED_SHA and
            sb.get("whole_archive_sha256") is None and sb.get("class") == "SCR_WorldFilesHelper" and sb.get("method") == "CreateWorld" and
            sb.get("source_module") == "WorkbenchGame" and sb.get("conditional_compilation") == "WORKBENCH" and
            sb.get("archive_path") == "C:/Program Files (x86)/Steam/steamapps/common/Arma Reforger/addons/data/data007.pak" and
            sb.get("retained_source_path") == "build/world-authoring-source-research-20261010-b274dc91/selected/SCR_WorldFilesHelper.c" and
            sb.get("retained_receipt_path") == "build/world-authoring-source-research-20261010-b274dc91/selected-entry-observations.json" and
            sb.get("retained_receipt_sha256") == "9a24665c09f5aa6879533b2f0591b93445aa4885e21ad7d0357c0a633024072d" and
            all(type(sb.get(k)) is int and sb[k] == wanted for k, wanted in (
                ("archive_size_bytes", 1994525893), ("archive_mtime_ns", 1788469039264200100),
                ("directory_name_offset", 1994298845), ("packed_offset", 1493110121), ("packed_size_bytes", 2909), ("decoded_size_bytes", 13536))),
            "Source contract selected archive/source identity differs", "stale_input")
    require(type(declaration) is dict and declaration.get("path") ==
            "C:/Program Files (x86)/Steam/steamapps/common/Arma Reforger Tools/Workbench/docs/ArmaReforgerScriptAPIPublic/html/interfaceSCR__WorldFilesHelper.html" and
            declaration.get("sha256") == "d1e6e5c9c62b7392e584309909895480d2b61e1a043718a8a93f89c0952f6516",
            "Primary declaration identity differs", "stale_input")
    require(type(files) is list and len(files) == 2, "Layered contract must describe exactly two source templates", "stale_input")
    for row, name, data in zip(files, (base.REL_WORLD, LAYER), (WORLD_BYTES, LAYER_BYTES)):
        require(type(row) is dict and row.get("path") == name and type(row.get("size_bytes")) is int and row["size_bytes"] == len(data) and
                row.get("sha256") == mod.digest(data) and row.get("exact_text") == data.decode() and
                row.get("encoding") == "UTF-8 without BOM" and row.get("line_ending") == "LF" and row.get("trailing_newline") is True,
                "Layered source-template contract differs", "stale_input")
    return sb, declaration


def primary_inputs():
    """Re-read only the selected packed bytes/metadata; no whole-archive claim."""
    require(identity(PACKAGE / "source-contracts.json")["sha256"] == CONTRACT_SHA, "Fixed source contract changed", "stale_input")
    value = mod.parse(mod.read(PACKAGE / "source-contracts.json"))
    sb, declaration = validate_contract(value)
    source = ROOT / sb["retained_source_path"]
    receipt = ROOT / sb["retained_receipt_path"]
    doc = Path(declaration["path"])
    require(identity(source)["sha256"] == SOURCE_SHA and identity(source)["bytes"] == 13536 and
            identity(receipt)["sha256"] == sb["retained_receipt_sha256"] and identity(doc)["sha256"] == declaration["sha256"],
            "Retained primary source/receipt/declaration changed", "stale_input")
    archive = Path(sb["archive_path"])

    def observe():
        base.clean_path(archive)
        before = archive.stat()
        require(archive.is_file() and (before.st_size, before.st_mtime_ns) == (sb["archive_size_bytes"], sb["archive_mtime_ns"]),
                "Selected archive size/mtime changed", "stale_input")
        with archive.open("rb") as stream:
            stream.seek(sb["directory_name_offset"])
            # This selected observed directory entry has no NUL between its
            # filename bytes and the retained metadata. No general PAC parser
            # or filename-framing rule is claimed.
            name = b"SCR_WorldFilesHelper.c"
            require(stream.read(len(name)) == name, "Selected archive filename changed", "stale_input")
            metadata = bytes.fromhex(sb["metadata_after_name_hex"])
            require(len(metadata) == 28 and mod.digest(metadata) == sb["metadata_after_name_sha256"] and
                    stream.read(28) == metadata, "Selected archive metadata changed", "stale_input")
            stream.seek(sb["packed_offset"])
            packed = stream.read(sb["packed_size_bytes"])
        require(len(packed) == 2909 and mod.digest(packed) == PACKED_SHA, "Selected archive payload changed", "stale_input")
        decoder = zlib.decompressobj()
        decoded = decoder.decompress(packed, 13537)
        require(len(decoded) == 13536 and decoder.eof and not decoder.unconsumed_tail and not decoder.unused_data and
                mod.digest(decoded) == SOURCE_SHA and decoded == mod.read(source), "Bounded selected source decoding differs", "stale_input")
        require((archive.stat().st_size, archive.stat().st_mtime_ns) == (before.st_size, before.st_mtime_ns),
                "Archive changed during bounded selected-entry read", "stale_input")
    observe()
    return [source, receipt, doc], observe, value


def self_test():
    work = Path(tempfile.mkdtemp(prefix="layered-world-inert-", dir=ROOT / "build"))
    cases = []
    for case_id in STAGE_CASES:
        root = work / case_id
        original, addon = root / "original", root / "addon"
        table = {}
        for name in sorted(base.BASE_FILES):
            data = ("inert-original:" + name + "\n").encode()
            write(mod.safe_path(original, name), data)
            table[name] = mod.digest(data)
        original_table = copy.deepcopy(table)
        world, layer, handler = WORLD_BYTES, LAYER_BYTES, b"inert-readonly-handler\n"
        negative = case_id not in STAGE_CASES[:3] and case_id != "stage.legacy-nine-distinct"
        if case_id == "stage.missing-original":
            table.pop("addon.gproj")
        elif case_id == "stage.extra-original-key":
            table["foreign.txt"] = "a" * 64
        elif case_id == "stage.invalid-hash":
            table["addon.gproj"] = True
        elif case_id == "stage.changed-original":
            (original / "addon.gproj").write_bytes(b"changed")
        elif case_id == "stage.extra-original-file":
            write(original / "foreign.txt", b"foreign")
        elif case_id == "stage.existing-destination":
            addon.mkdir()
        elif case_id == "stage.wrong-world-template":
            world += b"unsupported\n"
        elif case_id == "stage.wrong-layer-template":
            layer += b"unsupported\n"
        try:
            actual, dirs = stage(original, table, addon, world, layer, handler)
            require(not negative, "Malformed inert stage was admitted")
            if case_id == "stage.original-unchanged":
                bounded.exact_tree(original, original_table)
            elif case_id == "stage.meta-preserved":
                require(mod.read(addon / (base.REL_WORLD + ".meta")) == mod.read(original / (base.REL_WORLD + ".meta")),
                        "Stable metadata changed")
            elif case_id == "stage.legacy-nine-distinct":
                require(len(base.runtime_input_files()) == 9 and len(actual) == 10 and
                        LAYER not in base.runtime_input_files(), "Default legacy admission was expanded")
            cases.append({"id": case_id, "status": "success", "outcome": "return"})
        except mod.Failure as exc:
            if not negative or exc.status != "stale_input":
                raise
            cases.append({"id": case_id, "status": "success", "outcome": "stale_input",
                          "original_error": {"type": type(exc).__name__, "message": str(exc)}})
    # Profile checks are passive: token/rendering only, no adapter invocation.
    template = b'fixed "@TOKEN@" "@MECHANISM@" "@WORLD_ABSOLUTE@"\n'
    token_args = ({"inert": "a" * 64}, WORLD_BYTES, LAYER_BYTES, template, work / "profile-addon")
    for case_id in PROFILE_CASES:
        negative = case_id in ("profile.contract-bound-token", "profile.unknown-rejected")
        try:
            if case_id == "profile.registered-default":
                require(profile_wire(OPENING) == "module_registered_netapi" and
                        profile_token(*token_args) == profile_token(*token_args, OPENING),
                        "Registered default profile changed")
            elif case_id == "profile.cli-wire":
                require(profile_wire("startup-cli") == "startup_cli", "CLI profile wire identity changed")
            elif case_id == "profile.distinct-token":
                require(profile_token(*token_args, OPENING) != profile_token(*token_args, "startup-cli"),
                        "Distinct profiles share a token")
            elif case_id == "profile.distinct-render":
                registered = base.render(template, profile_token(*token_args, OPENING), "C:/inert/world.ent", OPENING)
                cli = base.render(template, profile_token(*token_args, "startup-cli"), "C:/inert/world.ent", "startup-cli")
                require(registered != cli and b'"module_registered_netapi"' in registered and
                        b'"startup_cli"' in cli, "Profile renderer did not retain the selected mechanism")
            elif case_id == "profile.contract-bound-token":
                profile_token(*token_args, source_contract_sha256="b" * 64)
            elif case_id == "profile.unknown-rejected":
                profile_token(*token_args, "netapi-resource")
            require(not negative, "Unsupported profile/token identity was admitted")
            cases.append({"id": case_id, "status": "success", "outcome": "return"})
        except mod.Failure as exc:
            if not negative or exc.status != "stale_input":
                raise
            cases.append({"id": case_id, "status": "success", "outcome": "stale_input",
                          "original_error": {"type": type(exc).__name__, "message": str(exc)}})
    require([row["id"] for row in cases] == list(SELF_CASES), "Incomplete inert fixture set")
    result = {"schema_version": 1, "operation": "verify.layered_world.inert", "status": "success",
              "expected_case_ids": list(SELF_CASES), "cases": cases, "complete_expected_case_set": True,
              "source": identity(Path(__file__)), "base": identity(BASE_PATH),
              "scope": {"compiler": "not_run", "engine": "not_run", "powershell": "not_run",
                        "engine_authored_serialization": "not_run"}}
    saved(work / "result.json", result)
    print(str(work / "result.json"))
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--prepared-receipt", type=Path)
    parser.add_argument("--expect-prepared-sha256")
    parser.add_argument("--beryl", type=Path)
    parser.add_argument("--expect-compiler-sha256")
    parser.add_argument("--workbench-tools", type=Path)
    parser.add_argument("--powershell-host", type=Path)
    parser.add_argument("--engine-exe", type=Path)
    parser.add_argument("--opening-mechanism", choices=OPENINGS, default=OPENING)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--prepare-only", action="store_true")
    modes.add_argument("--engine-stage", choices=("compile", "runtime"))
    args = parser.parse_args()
    opening = args.opening_mechanism
    mechanism = profile_wire(opening)
    if args.self_test:
        require(not args.prepared_receipt and not args.prepare_only and not args.engine_stage,
                "Inert checks cannot select execution or prepared inputs")
        return self_test()
    require(args.prepared_receipt is not None and args.expect_prepared_sha256 == LEGACY_SHA and
            (args.prepare_only or args.engine_stage), "Exact identified original receipt and explicit stage are required")
    work = Path(tempfile.mkdtemp(prefix="source layered world & spaces-", dir=ROOT / "build"))
    print("Layered world evidence: " + str(work), flush=True)
    record = {"schema_version": 1, "operation": "verify.workbench.source_layered_world", "status": "failure",
              "stage": "prepare", "opening_mechanism": opening, "mechanism": mechanism,
              "fixture_format": FORMAT, "expected_case_ids": list(base.READY_CASES), "scope": base.scope(),
              "attempts": {"compile": {"requested": bool(args.engine_stage), "adapter_attempted": False},
                           "runtime": {"requested": args.engine_stage == "runtime", "adapter_attempted": False}},
              "commands": [], "raw_results": {}, "evidence_errors": [], "limitations": [
                  "Source-backed layered format, not engine-authored serialization; no world-save API is invoked.",
                  "Native resource acceptance and named editor readiness remain separate from source preparation.",
                  "No callback delivery, tablet services, gameplay, multiplayer, visual or performance claim.",
                  "The copied historical callback handler is dormant; only the unchanged read-only startup observer is selected."]}
    record["scope"].update(world_format=FORMAT, engine_authored_serialization="not_run")
    job, unchanged = None, None
    try:
        selection = args.prepared_receipt.absolute()
        require(selection == LEGACY_RECEIPT, "A different historical receipt was selected", "stale_input")
        receipt_bytes = mod.read(selection)
        require(mod.digest(receipt_bytes) == LEGACY_SHA, "Selected receipt changed", "stale_input")
        selected = mod.parse(receipt_bytes)
        original, original_files, binding, retained, retained_files, retained_dirs = base.prepared(selected, selection)
        record.update(prepared_receipt=identity(selection), original_addon=str(original), original_files=original_files,
                      original_artifact=str(retained), prepared_artifact_sha256=selected["original_artifact"]["artifact_sha256"],
                      historical_compiler_sha256=selected["source_build_result"]["compiler_sha256"], binding=binding)
        primary, primary_guard, source_contract = primary_inputs()
        record["source_contract"] = source_contract
        inputs = [Path(__file__).resolve(), BASE_PATH, PACKAGE / base.REL_WORLD, PACKAGE / LAYER,
                  PACKAGE / "source-contracts.json", PACKAGE / "README.md", base.PACKAGE / "rpc.c.in",
                  base.PACKAGE / "README.md", base.ADAPTER, ROOT / "scripts/verify-component-engine.py",
                  *mod.bundle_paths(), *primary]
        for name, fingerprint in base.DOCS.items():
            path = base.DOC_ROOT / name
            require(identity(path)["sha256"] == fingerprint, "Installed declaration changed", "stale_input")
            inputs.append(path)
        tools, compiler, host, engine = {}, None, None, None
        if args.engine_stage:
            require(all((args.beryl, args.expect_compiler_sha256, args.workbench_tools, args.powershell_host, args.engine_exe)),
                    "Engine stage needs explicit private compiler/hash, tools, host and engine", "unavailable")
            compiler, host, engine = (p.absolute() for p in (args.beryl, args.powershell_host, args.engine_exe))
            require(compiler.is_relative_to(ROOT / "build") and compiler.parent != ROOT / "build" and
                    base.HASH.fullmatch(args.expect_compiler_sha256) and identity(compiler)["sha256"] == args.expect_compiler_sha256,
                    "Configured private compiler differs", "stale_input")
            require(identity(engine)["sha256"] == binding["sha256"] and identity(host)["bytes"] > 0,
                    "Configured engine/host unavailable or changed", "stale_input")
            for name in sorted(set(base.COMPILE_TOOLS + base.RUNTIME_TOOLS)):
                path = mod.safe_path(args.workbench_tools.absolute(), "scripts/" + name, True)
                tools[name] = identity(path)["sha256"]
                inputs.append(path)
            inputs += [compiler, host, engine, mod.HERE / "engine-compile.ps1"]
        frozen = {str(p): identity(p) for p in inputs}
        record.update(verification_inputs=frozen, plugin_file_set=tools, retained_inputs=[])
        for index, (name, item) in enumerate(frozen.items()):
            if item["bytes"] > 16 * 1024 * 1024:
                record["retained_inputs"].append({**item, "retention": "fingerprint_only_large_binary"})
                continue
            data = mod.read(Path(name))
            require(len(data) == item["bytes"] and mod.digest(data) == item["sha256"], "Input changed before retention", "stale_input")
            target = work / "inputs" / (str(index).zfill(4) + "-" + Path(name).name + ".input")
            write(target, data)
            record["retained_inputs"].append({**item, "retained": str(target), "retention": "exact_bytes"})
        write(work / "prepared-receipt.raw.json", receipt_bytes)
        addon = work / "probe-addon"
        template = mod.read(base.PACKAGE / "rpc.c.in")
        world, layer = mod.read(PACKAGE / base.REL_WORLD), mod.read(PACKAGE / LAYER)
        token = profile_token(original_files, world, layer, template, addon, opening)
        handler = base.render(template, token, (addon / base.REL_WORLD).as_posix(), opening)
        table, dirs = stage(original, original_files, addon, world, layer, handler)
        manifest = {"schema_version": 1, "files": table, "directories": dirs}
        saved(work / "input-manifest.json", manifest)
        record.update(token=token, function=base.FUNCTION, candidate_path=str(addon), staged_file_set=table,
                      staged_directory_set=dirs, staged_sha256=mod.digest(mod.canonical(table)),
                      declared_replacements={base.REL_WORLD: {"original": original_files[base.REL_WORLD], "replacement": mod.digest(world)}},
                      declared_additions={LAYER: mod.digest(layer), base.HANDLER_PATH: mod.digest(handler)})
        record["scope"]["source_copy"] = "executed_success"

        def check():
            require(mod.read(selection) == receipt_bytes and mod.read(work / "prepared-receipt.raw.json") == receipt_bytes,
                    "Original/retained receipt changed", "stale_input")
            bounded.exact_tree(original, original_files)
            bounded.exact_tree(retained, retained_files)
            require(sorted(bounded.tree_files(retained)[1]) == retained_dirs, "Original artifact directory set changed", "stale_input")
            primary_guard()
            for path, item in frozen.items():
                require(identity(Path(path)) == item, "Frozen source/tool changed: " + path, "stale_input")
            for item in record["retained_inputs"]:
                if item["retention"] == "exact_bytes":
                    copied = identity(Path(item["retained"]))
                    require(copied["sha256"] == item["sha256"] and copied["bytes"] == item["bytes"], "Retained input changed", "stale_input")
            record["engine_derived_outputs"] = bounded.staged_tree(addon, table)
            require(mod.canonical(mod.parse(mod.read(work / "input-manifest.json"))) == mod.canonical(manifest),
                    "Fixed ten-input manifest changed", "stale_input")
        unchanged = check
        check()
        if args.prepare_only:
            record.update(status="success", stage="prepared", success_means="exact source-layered ten-input stage; native readiness not run")
        else:
            project = work / "job-project"
            project.mkdir()
            job = mod.Job(project, "source-layered-world-" + opening, compiler)
            job.result.update(source_sha256=record["staged_sha256"], binding_sha256=mod.digest(mod.canonical(binding)))
            compile_path = work / "engine-compile.json"
            record["stage"] = "engine_compile"
            record["attempts"]["compile"]["adapter_attempted"] = True
            record["scope"]["engine_compilation"] = "attempted_unconfirmed"
            try:
                job.run([host, "-NoProfile", "-File", mod.HERE / "engine-compile.ps1", "-ToolRoot", args.workbench_tools.absolute(),
                         "-ProjectDir", addon, "-ResultPath", compile_path, "-ExpectedVersion", binding["version"],
                         "-TimeoutSeconds", "30"], "layered_engine_compile", work, timeout=60)
            finally:
                base.capture_result(record, "compile", compile_path)
                if "compile" in record["raw_results"]:
                    raw = record["raw_results"]["compile"]["result"]
                    record["scope"]["engine_compilation"] = base.compile_status(raw, binding, tools)
                    try:
                        record["compile_logs"] = base.retained_logs(work, raw)
                    except (mod.Failure, OSError, ValueError) as exc:
                        record["evidence_errors"].append({"stage": "compile_log_capture", "message": str(exc)})
            require(record["scope"]["engine_compilation"] == "executed_success" and not record["evidence_errors"],
                    "No exact complete headless success")
            check()
            if args.engine_stage == "runtime":
                runtime_path = work / "engine-runtime.json"
                record["stage"] = "source_layered_world_readiness"
                record["attempts"]["runtime"]["adapter_attempted"] = True
                record["scope"]["startup_world_readiness"] = "attempted_unconfirmed"
                try:
                    job.run([host, "-NoProfile", "-File", base.ADAPTER, "-ToolRoot", args.workbench_tools.absolute(), "-ProjectDir", addon,
                             "-ProjectId", base.PROJECT_ID, "-ResultPath", runtime_path, "-InputManifest", work / "input-manifest.json",
                             "-Token", token, "-ExpectedEngineHash", binding["sha256"], "-ExpectedEngineVersion", binding["version"],
                             "-ExpectedEnginePath", engine, "-OpeningMechanism", opening], "layered_runtime_readiness", work, timeout=240)
                finally:
                    base.capture_result(record, "runtime", runtime_path)
                require("runtime" in record["raw_results"], "Missing owned runtime observation", "unavailable")
                record["readiness_comparison"] = base.validate_runtime(record["raw_results"]["runtime"]["result"], token, addon, engine,
                    binding, tools, work / "input-manifest.json", manifest, frozen[str(base.ADAPTER)]["sha256"],
                    opening=opening, fixture_format=FORMAT)
                record["scope"]["startup_world_readiness"] = "executed_success"
                check()
            record.update(status="success", stage="verified", success_means="exact headless compile" if args.engine_stage == "compile"
                          else "exact native named layered-world readiness; callbacks and serialization not run")
    except (mod.Failure, OSError, ValueError, KeyboardInterrupt) as exc:
        record["status"] = "cancelled" if isinstance(exc, KeyboardInterrupt) else getattr(exc, "status", "failure")
        if record["status"] == "failure":
            for label in ("runtime", "compile"):
                raw = record["raw_results"].get(label, {}).get("result")
                if type(raw) is dict and raw.get("status") in ("failure", "unavailable", "timeout", "cancelled", "stale_input"):
                    record["status"] = raw["status"]
                    break
        record["failure"] = {"type": type(exc).__name__, "message": str(exc)}
    finally:
        if unchanged is not None:
            try:
                unchanged()
            except (mod.Failure, OSError, ValueError) as exc:
                record["evidence_errors"].append({"stage": "final_input_guard", "message": str(exc)})
                if record["status"] == "success":
                    record["status"] = getattr(exc, "status", "stale_input")
        if job is not None:
            record["commands"] = job.result["raw_logs"]
            for label, stage_name in (("compile", "layered_engine_compile"), ("runtime", "layered_runtime_readiness")):
                rows = [row for row in record["commands"] if Path(row.get("stdout", "")).name.endswith("-" + stage_name + ".stdout.log")]
                if rows:
                    row = rows[-1]
                    record["attempts"][label].update(process_outcome=row["status"], exit_confirmed=row.get("exit_confirmed"),
                                                      cleanup_errors=row.get("cleanup_errors", []))
                    if record["status"] == "success" and (row.get("exit_confirmed") is not True or row.get("cleanup_errors")):
                        record["status"] = "unavailable"
                        record["evidence_errors"].append({"stage": label + "_host_cleanup", "message": "Owned host exit/cleanup incomplete"})
            job.result.update(status=record["status"], stage=record["stage"])
            saved(job.path / "result.json", job.result)
            record["job"] = job.result
        saved(work / "results.json", record)
        print(str(work / "results.json"), flush=True)
    return 0 if record["status"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
