#!/usr/bin/env python3
"""Import two actual, matching owned Workbench scenario receipts; never launch one."""
import argparse
from pathlib import Path
import re
import sys

import collect as co
import evaluate as ev


class Inputs:
    def __init__(self):
        self.files = {}

    def read(self, path):
        path = Path(path).resolve()
        ev.require(path.is_file() and path.stat().st_size <= ev.LIMIT, 'missing/excessive input: ' + str(path))
        data = path.read_bytes()
        ev.require(len(data) <= ev.LIMIT, 'input grew beyond limit')
        before = self.files.get(path)
        ev.require(before is None or before == data, 'input changed during import: ' + str(path))
        self.files[path] = data
        ev.require(len(self.files) <= 4096 and sum(len(value) for value in self.files.values()) <= 256 * 1024 * 1024,
                   'import input budget exceeded')
        return data

    def json(self, path):
        return ev.parse(self.read(path))

    def unchanged(self):
        for path, data in self.files.items():
            ev.require(path.is_file() and path.stat().st_size <= ev.LIMIT and path.read_bytes() == data,
                       'input changed during import: ' + str(path))


def contained(root, relative):
    ev.require(type(relative) is str and relative and ':' not in relative and '\\' not in relative
               and not ev.PurePosixPath(relative).is_absolute() and '..' not in ev.PurePosixPath(relative).parts
               and str(ev.PurePosixPath(relative)) == relative, 'unsafe manifest path')
    actual = (root / relative).resolve()
    ev.require(actual.is_relative_to(root), 'manifest path escapes root')
    return actual


def read_receipt(inputs, path, scenario, candidate_path, candidate_root):
    receipt = inputs.json(path)
    if 'scenario_receipt' in receipt:
        ev.require(receipt.get('status') == 'success', 'outer scenario did not succeed')
        receipt = receipt['scenario_receipt']
    ev.require(type(receipt) is dict and type(receipt.get('schema_version')) is int
               and receipt['schema_version'] == 1 and receipt.get('status') == 'success'
               and receipt.get('stage') == 'runtime_scenario' and receipt.get('scenario') == scenario,
               'wrong or incomplete scenario receipt: ' + scenario)
    manifest = inputs.json(candidate_path)
    ev.require(type(manifest) is dict and type(manifest.get('files')) is dict, 'missing candidate file manifest')
    files = manifest['files']
    # Match mod.canonical: all manifest path/hash characters are ASCII here.
    ev.require(ev.digest(ev.canonical(files)) == manifest.get('staged_artifact_sha256')
               == receipt.get('staged_artifact_sha256'), 'staged manifest fingerprint mismatch')
    ev.require(manifest.get('token') == receipt.get('compiled_token')
               and manifest.get('artifact_sha256') == receipt.get('artifact_sha256')
               and manifest.get('parameters') == receipt.get('parameters')
               and manifest.get('scenario_contract') == receipt.get('scenario_contract'), 'candidate/receipt identity mismatch')
    root = Path(candidate_root).resolve()
    wanted = {name: value for name, value in files.items() if name != 'resourceDatabase.rdb'}
    actual_names = {path.relative_to(root).as_posix() for path in root.rglob('*') if path.is_file()
                    and path.relative_to(root).as_posix() != 'resourceDatabase.rdb'}
    ev.require(actual_names == set(wanted), 'candidate source selection changed')
    for name, expected in wanted.items():
        ev.require(ev.digest(inputs.read(contained(root, name))) == expected, 'changed candidate source: ' + name)
    raw = receipt.get('raw_results')
    ev.require(type(raw) is dict and 1 <= len(raw) <= 16, 'missing raw scenario results')
    runtime = None
    runtime_path = None
    job_root = Path(candidate_path).resolve().parent
    for raw_path, expected in raw.items():
        actual = Path(raw_path).resolve()
        ev.require(actual.is_relative_to(job_root), 'raw result escapes scenario job')
        ev.require(ev.digest(inputs.read(actual)) == expected, 'raw result fingerprint mismatch')
        if actual.name == 'scenario-runtime.json':
            ev.require(runtime is None, 'duplicate runtime result')
            runtime, runtime_path = inputs.json(actual), actual
    ev.require(type(runtime) is dict and runtime.get('status') == 'success'
               and runtime.get('engine_sha256') == receipt.get('engine_sha256')
               and runtime.get('engine_version') == receipt.get('engine_version')
               and type(runtime.get('rpc')) is dict and runtime['rpc'].get('Ok') is True,
               'missing successful matching runtime')
    ev.require(runtime['rpc']['Response'].get('token') == receipt['compiled_token'], 'raw runtime token differs')
    return receipt, manifest, runtime, runtime_path


def build_bundle(args, evidence_kind='collector_measurements'):
    inputs = Inputs()
    plan = inputs.json(args.schedule)
    co.validate_plan(plan)
    # This importer deliberately rejects phase labels that could imply a frozen
    # independent pilot or held-out performance experiment it does not establish.
    ev.require(plan['phase'] == 'exploratory' and plan['role'] == 'exploratory', 'initial terrain importer is exploratory only')
    timing, manifest, runtime, runtime_path = read_receipt(inputs, args.measurement_receipt,
        'measure.terrain.construction', args.candidate, args.candidate_root)
    semantic, semantic_manifest, semantic_runtime, _ = read_receipt(inputs, args.semantic_receipt,
        'compare.terrain.chunks', args.semantic_candidate, args.semantic_candidate_root)
    for field in ('artifact_sha256', 'source_sha256', 'compiler_sha256', 'tool_sha256', 'engine_sha256', 'engine_version', 'integration_files'):
        ev.require(timing.get(field) == semantic.get(field) and timing.get(field) is not None,
                   'timing and semantic identity differs: ' + field)
    metadata = timing['scenario_contract']
    comparison = semantic['scenario_contract']
    templates = metadata.get('source_templates')
    ev.require(type(templates) is dict and templates and templates == comparison.get('source_templates'),
               'timing and comparison do not bind identical source templates')
    ev.require(metadata.get('datasets') == comparison.get('datasets') and type(metadata.get('datasets')) is list,
               'timing and comparison datasets differ')
    ev.require([dataset.get('id') for dataset in metadata['datasets']] == plan['case_ids'], 'dataset/case selection differs')
    ev.require(metadata.get('schedule_sha256') == ev.digest(inputs.read(args.schedule)), 'timing schedule fingerprint mismatch')
    co.parse_target(runtime['rpc']['Response'], plan, timing['compiled_token'])
    observed = semantic_runtime['rpc']['Response']
    ev.require(type(observed.get('executed')) is int and observed['executed'] == 1
               and type(observed.get('failures')) is int and observed['failures'] == 0
               and observed.get('caseIds') == plan['case_ids']
               and type(observed.get('checks')) is int and observed['checks'] > 0
               and observed['checks'] == semantic.get('trace', {}).get('checks'), 'semantic comparison incomplete or mismatched')
    ev.require(ev.digest(inputs.read(args.compiler)) == timing['compiler_sha256'], 'compiler binary changed')
    tool_manifest = inputs.json(args.tool_manifest)
    ev.require(type(tool_manifest) is dict and ev.digest(ev.canonical(tool_manifest)) == timing['tool_sha256'], 'tool manifest identity differs')
    tool_root, integration_root = Path(args.tool_root).resolve(), Path(args.integration_root).resolve()
    for name, expected in tool_manifest.items():
        ev.require(ev.digest(inputs.read(contained(tool_root, name))) == expected, 'tool file changed: ' + name)
    for name, expected in templates.items():
        ev.require(name in tool_manifest and tool_manifest[name] == expected, 'template differs from executed tool identity')
    plugin_files = timing['integration_files']
    ev.require(type(plugin_files) is dict and plugin_files, 'missing integration file identities')
    for name, expected in plugin_files.items():
        ev.require(ev.digest(inputs.read(contained(integration_root / 'scripts', name))) == expected, 'integration file changed: ' + name)
    environment = inputs.json(args.environment)
    co.schema(environment, 'beryl.performance.environment_review', ('status', 'description', 'evidence'))
    ev.require(environment['status'] == 'reviewed', 'unreviewed environment conditions')
    co.words(environment['description'], 'environment conditions')
    environment_reader = ev.Reader(Path(args.environment).resolve().parent)
    environment_evidence = environment_reader.bytes(environment['evidence'])
    ev.require(environment_evidence, 'empty environment review evidence')
    inputs.read(args.timer_evidence)
    inputs.unchanged(); environment_reader.unchanged()
    output = Path(args.output).resolve()
    ev.require(not output.exists(), 'import destination already exists')
    output.mkdir(parents=True, exist_ok=False)
    evidence_root = output / 'evidence'; evidence_root.mkdir()

    def ref(value):
        data = value if isinstance(value, bytes) else ev.canonical(value)
        sha = ev.digest(data)
        path = evidence_root / sha
        if not path.exists():
            with path.open('xb') as handle: handle.write(data)
        return {'path': 'evidence/' + sha, 'sha256': sha}

    captured = {str(path): ref(data) for path, data in inputs.files.items()}
    index = ref({'schema_version': 1, 'kind': 'beryl.performance.import_provenance', 'inputs': captured,
                 'importer_sha256': ev.digest(Path(__file__).read_bytes()),
                 'scope_review': 'Tool-owned exact cached-height fixture; timed construction+release; whole rendering excluded.'})
    engine_identity = ref({'schema_version': 1, 'kind': 'beryl.performance.engine_identity',
        'binary_sha256': timing['engine_sha256'], 'version': timing['engine_version'], 'evidence': captured[str(Path(runtime_path).resolve())]})
    semantic_contract = ref({'schema_version': 1, 'kind': 'beryl.performance.terrain_semantic_contract',
        'comparison': 'engine_operator_complete_payload', 'fields': ['m_iColor', 'm_Vertices', 'm_Indices', 'm_fUVScale', 'm_pTexture'],
        'order': 'full ordered command and payload sequence; original winding', 'source_templates': templates,
        'exclusions': ['bitwise f32 equivalence', 'sampling', 'Canvas consumer lifetime', 'other map layers', 'visual output']})
    fingerprint_refs = {
        'artifact': ref({'source_artifact_sha256': timing['artifact_sha256'], 'source_templates': templates}),
        'sources': ref({'source_sha256': timing['source_sha256'], 'measurement': manifest, 'semantic': semantic_manifest}),
        'compiler': captured[str(Path(args.compiler).resolve())],
        'toolchain': ref({'target': 'Enfusion', 'engine_binary_sha256': timing['engine_sha256'], 'version': timing['engine_version']}),
        'bindings': ref({'engine': engine_identity, 'capability_evidence': captured[str(Path(args.timer_evidence).resolve())]}),
        'engine': engine_identity,
        'environment': ref({**environment, 'evidence': ref(environment_evidence)}),
        'workload': ref({'datasets': metadata['datasets'], 'operations': plan['operations'], 'scope_name': plan['scope_name']}),
        'semantic_contract': semantic_contract,
        'tool': ref(tool_manifest), 'integration': ref(plugin_files)}
    scope = ref({'schema_version': 1, 'kind': 'beryl.performance.scope', 'status': 'reviewed',
        'scope_name': plan['scope_name'], 'description': 'Cached-height relief construction and release with command-count observation; no sampling, Canvas or complete rendering.',
        'paid_components': ['compute', 'cleanup'], 'excluded_components': [c for c in ev.COSTS if c not in ('compute', 'cleanup')],
        'resource_status': {r: {'status': 'unavailable', 'reason': 'No admitted per-workload physical/resource instrumentation in this scope.'} for r in ev.RESOURCES},
        'timer_evidence': captured[str(Path(args.timer_evidence).resolve())], 'review_evidence': index})
    session = runtime.get('session', {})
    ownership = ref({'schema_version': 1, 'kind': 'beryl.performance.ownership', 'status': 'verified',
        **{key: session.get(key) for key in ('process_id', 'start_time', 'project')},
        'evidence': captured[str(Path(runtime_path).resolve())]})
    semantic_ref = ref({'schema_version': 1, 'kind': 'beryl.performance.semantic', 'status': 'complete',
        'fingerprints': {key: fingerprint_refs[key]['sha256'] for key in ('artifact', 'workload', 'semantic_contract', 'engine')},
        'case_ids': plan['case_ids'], 'expected_cases': len(plan['case_ids']), 'completed_cases': len(plan['case_ids']),
        'failures': 0, 'comparison': 'engine_operator_complete_payload', 'evidence': captured[str(Path(args.semantic_receipt).resolve())]})
    # Retain every producer file, including source files; do not rely on references
    # nested in arbitrary manifests being automatically followed by the collector.
    raw_refs = list({item['sha256']: item for item in captured.values() if (evidence_root / item['sha256']).stat().st_size}.values())
    raw_refs += [index, ref(environment_evidence)]
    ev.require(len(raw_refs) <= 128, 'raw source collection exceeds bounded collector reference count')
    request = {'schema_version': 1, 'kind': 'beryl.performance.collection', 'evidence_kind': evidence_kind,
        'token': timing['compiled_token'], 'schedule': ref(plan), 'runtime': ref(runtime), 'semantic': semantic_ref,
        'scope': scope, 'ownership': ownership, 'fingerprints': fingerprint_refs, 'raw_evidence': raw_refs}
    with (output / 'request.json').open('xb') as handle: handle.write(ev.canonical(request) + b'\n')
    inputs.unchanged(); environment_reader.unchanged()
    return co.collect(output / 'request.json', output / 'journal')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('measurement-receipt', 'semantic-receipt', 'schedule', 'candidate', 'candidate-root',
                 'semantic-candidate', 'semantic-candidate-root', 'tool-root', 'tool-manifest',
                 'integration-root', 'compiler', 'timer-evidence', 'environment', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    try:
        result = build_bundle(args)
        print(ev.canonical(result).decode())
        return 0
    except (ev.Invalid, OSError, KeyError, TypeError, ValueError) as error:
        print(ev.canonical({'schema_version': 1, 'kind': 'beryl.performance.import_error',
                           'status': 'failed', 'error': str(error)}).decode())
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
