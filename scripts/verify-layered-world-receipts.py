#!/usr/bin/env python3
"""Inert complete layered/legacy startup envelopes; never launch a subprocess."""
from pathlib import Path
import copy
import hashlib
import importlib.util
import json
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location('layered_receipts_common', ROOT / 'scripts/verify-workbench-startup.py')
common = importlib.util.module_from_spec(spec)
spec.loader.exec_module(common)
PACKAGE = ROOT / 'packages/sparkos/workbench-layered-world'
LAYER = 'worlds/BerylCallbackProbe_Layers/default.layer'


def identity(path):
    data = Path(path).read_bytes()
    return {'path': str(path), 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def put(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('wb') as stream:
        if stream.write(data) != len(data):
            raise OSError('Incomplete inert fixture write')


def fixture(work, number, layered=True, opening='module-netapi-registered'):
    directory = work / ('fixture-' + str(number).zfill(3))
    addon = directory / 'probe-addon'
    token = 'a' * 64
    selected_format = 'source-layered-v1' if layered else 'legacy'
    files = {}
    for name in sorted(common.runtime_input_files(selected_format)):
        data = ((PACKAGE / name).read_bytes() if layered and name in (common.REL_WORLD, LAYER) else
                ('INERT SOURCE ' + name + '\n').encode())
        if name == common.HANDLER_PATH:
            data = common.render((common.PACKAGE / 'rpc.c.in').read_bytes(), token, (addon / common.REL_WORLD).as_posix(), opening)
        put(addon / name, data)
        files[name] = hashlib.sha256(data).hexdigest()
    manifest = {'schema_version': 1, 'files': files, 'directories': sorted(common.bounded.expected_directories(files))}
    manifest_path = directory / 'input-manifest.json'
    put(manifest_path, (json.dumps(manifest, indent=2) + '\n').encode())
    put(addon / 'resourceDatabase.rdb', b'INERT ENGINE DERIVED BYTES\n')
    engine = directory / 'engine.fixture'
    put(engine, b'NOT AN EXECUTABLE; NEVER LAUNCHED\n')
    binding = {'version': 'synthetic.inert', 'sha256': identity(engine)['sha256']}
    tools = {name: hashlib.sha256(('INERT TOOL ' + name).encode()).hexdigest() for name in common.RUNTIME_TOOLS}
    body = {key: '' for key in common.WIRE_STRINGS}
    body.update({key: key not in ('game_mode', 'in_play_mode') for key in common.WIRE_BOOLS})
    body.update(token=token, action='observe', status='ready', mechanism=common.OPENING_PROFILES[opening],
                addon_world_path=(addon / common.REL_WORLD).as_posix(), resource_name=common.RESOURCE,
                resource_path=common.REL_WORLD, resource_absolute_path=(addon / common.REL_WORLD).as_posix(),
                world_path=common.RESOURCE, world_absolute_path=(addon / common.REL_WORLD).as_posix())
    preliminary = {**body, 'status': 'pending', 'world_path': '', 'world_absolute_path': '', 'world_path_resolved': False, 'world_matches': False}
    calls = []
    selected_calls = (
            ('IsWorkbenchRunning', {'IsRunning': True, 'ScriptsCompiled': True}),
            ('GetLoadedProjects', {'Loaded Projects': [common.PROJECT_ID]}),
            (common.FUNCTION, body)) if opening == 'startup-cli' else (
            ('IsWorkbenchRunning', {'IsRunning': True, 'ScriptsCompiled': True}),
            ('GetLoadedProjects', {'Loaded Projects': [common.PROJECT_ID]}),
            (common.FUNCTION, preliminary), ('OpenResource', {'Opened': True}), (common.FUNCTION, body))
    for index, (function, response) in enumerate(selected_calls):
        reply = {'Ok': True, 'Function': function, 'ErrorCode': 'Ok', 'Response': copy.deepcopy(response), 'Raw': json.dumps(response)}
        row = {'function': function, 'action': 'observe' if function == common.FUNCTION else None,
               'params': {'token': token, 'action': 'observe'} if function == common.FUNCTION else
                         ({'ResourceName': common.RESOURCE} if function == 'OpenResource' else {}),
               'elapsed_ms': (index + 1) * 100, 'timeout_ms': 8000, 'duration_ms': 10, 'result': reply}
        if function == common.FUNCTION:
            row['normalized_response'], row['codec'] = common.normalize(response)
        elif function == 'OpenResource':
            row.update(normalized_response={'Opened': True}, codec={'schema_version': 1, 'name': 'enfusion.jsonapistruct.bool01.v1', 'numeric_boolean_fields': []})
        calls.append(row)
    log = directory / 'startup-logs' / 'inert.log'
    put(log, b'INERT LOG; NO ENGINE OR HOST RUN\n')
    pid, ticks = 2222, 639272000000000001
    checks = [{'site': 'startup.identity', 'process_id': pid, 'start_ticks': ticks, 'executable': str(engine), 'elapsed_ms': 1},
              {'site': 'port.check', 'process_id': pid, 'start_ticks': ticks, 'executable': str(engine), 'elapsed_ms': 10}]
    for call in calls:
        for kind, elapsed in (('before.', call['elapsed_ms']), ('after.', call['elapsed_ms'] + call['duration_ms'])):
            checks.append({'site': kind + call['function'], 'process_id': pid, 'start_ticks': ticks, 'executable': str(engine), 'elapsed_ms': elapsed})
    derived = common.bounded.staged_tree(addon, files)
    value = {'schema_version': 1, 'stage': 'startup_readiness_complete', 'status': 'success',
             'mechanism': common.OPENING_PROFILES[opening], 'opening_mechanism': opening, 'token': token, 'function': common.FUNCTION,
             'project_id': common.PROJECT_ID, 'engine_sha256': binding['sha256'], 'engine_version': binding['version'], 'engine_path': str(engine),
             'tools': copy.deepcopy(tools), 'adapter_sha256': identity(common.ADAPTER)['sha256'], 'scope': common.OPENING_SCOPES[opening],
             'callback_execution': 'not_run', 'play': 'not_run', 'spawn': 'not_run', 'save': 'not_run', 'policy_changes': 'not_run',
             'limits': {'stage_ms': 30000, 'rpc_ms': 8000, 'total_ms': 180000, 'cleanup_ms': 5000, 'max_polls': 64,
                        'native_launch_and_bridge_calls_not_hard_cancelled': True, 'raw_logs_aggregate_bytes': 67108864},
             'input_manifest': {'path': str(manifest_path), 'sha256': identity(manifest_path)['sha256']}, 'staged_inputs': copy.deepcopy(manifest),
             'engine_outputs': [{'path': row['path'], 'relative': row['relative_path'], 'bytes': row['bytes'], 'sha256': row['sha256']} for row in derived],
             'evidence_errors': [], 'cleanup': 'owned_process_stopped', 'elapsed_ms': 1000,
             'session': {'process_id': pid, 'start_ticks': ticks, 'reused': False, 'project': str(addon), 'executable': str(engine)},
             'arguments': ['-gproj', str(addon / 'addon.gproj'), '-noOpenLastResource', '-scriptAuthorizeAll', '-wbmodule=WorldEditor', '-run'] +
                          (['-load', common.REL_WORLD] if opening == 'startup-cli' else []),
             'port_checks': [{'elapsed_ms': 10, 'listening': True, 'owning_process': pid}], 'rpcs': calls,
             'health': copy.deepcopy(calls[0]['result']), 'loaded_projects': copy.deepcopy(calls[1]['result']),
             'preliminary': None if opening == 'startup-cli' else copy.deepcopy(calls[2]['normalized_response']),
             'native_open': None if opening == 'startup-cli' else copy.deepcopy(calls[3]['result']),
             'completion': copy.deepcopy(calls[-1]['normalized_response']), 'session_checks': checks,
             'raw_logs': [{'retained': str(log), 'bytes': log.stat().st_size, 'sha256': identity(log)['sha256']}]}
    args = [token, addon, engine, binding, tools, manifest_path, manifest, value['adapter_sha256'], opening]
    if layered:
        args.append('source-layered-v1')
    return value, args, directory


def declared_mutation(value, args, name, data):
    put(args[1] / name, data)
    args[6]['files'][name] = hashlib.sha256(data).hexdigest()
    put(args[5], (json.dumps(args[6], indent=2) + '\n').encode())
    value['staged_inputs'] = copy.deepcopy(args[6])
    value['input_manifest']['sha256'] = identity(args[5])['sha256']


def main():
    work = Path(tempfile.mkdtemp(prefix='layered-world-receipts-', dir=ROOT / 'build'))
    print('Inert layered receipt evidence: ' + str(work), flush=True)
    planned = []
    def case(name, mutate=None, accept=False, layered=True):
        planned.append((name, mutate, accept, layered))
    case('positive.layered-ten-inputs', accept=True)
    case('positive.legacy-default-nine-inputs', accept=True, layered=False)
    case('layer.missing', lambda v, a, d: (a[1] / LAYER).unlink())
    case('layer.changed-with-honest-manifest', lambda v, a, d: declared_mutation(v, a, LAYER, b'GenericWorldEntity {\n}\n'))
    case('world.changed-with-honest-manifest', lambda v, a, d: declared_mutation(v, a, common.REL_WORLD, b'SubScene {\n}\n'))
    case('format.unknown', lambda v, a, d: a.__setitem__(-1, 'invented-format'))
    case('format.layered-as-legacy', lambda v, a, d: a.__setitem__(-1, 'legacy'))
    case('format.legacy-as-layered', lambda v, a, d: a.append('source-layered-v1'), layered=False)
    case('profile.unknown', lambda v, a, d: a.__setitem__(-2, 'invented-profile'))
    case('profile.absolute-opener', lambda v, a, d: a.__setitem__(-2, 'module-netapi-resource'))
    case('profile.argv-load', lambda v, a, d: v['arguments'].append('-load=world.ent'))
    for name, key, replacement in (('schema-bool', 'schema_version', True), ('status', 'status', 'timeout'),
            ('stage', 'stage', 'prepared'), ('token', 'token', 'b' * 64), ('engine-hash', 'engine_sha256', 'b' * 64),
            ('binding-version', 'engine_version', 'wrong'), ('adapter', 'adapter_sha256', 'b' * 64),
            ('errors', 'evidence_errors', [{'message': 'incomplete'}]), ('cleanup', 'cleanup', 'stop_requested'),
            ('callback-claim', 'callback_execution', 'executed_success'), ('save-claim', 'save', 'executed_success')):
        case('envelope.' + name, lambda v, a, d, k=key, r=replacement: v.update({k: r}))
    case('manifest.bool-schema', lambda v, a, d: a[6].update(schema_version=True))
    case('manifest.directory', lambda v, a, d: a[6]['directories'].append('unaccounted'))
    case('manifest.hash', lambda v, a, d: v['input_manifest'].update(sha256='b' * 64))
    case('manifest.unknown-source', lambda v, a, d: put(a[1] / 'extra.input', b'INERT EXTRA\n'))
    case('derived.hash', lambda v, a, d: v['engine_outputs'][0].update(sha256='b' * 64))
    case('derived.missing', lambda v, a, d: v['engine_outputs'].clear())
    case('rpc.missing', lambda v, a, d: v['rpcs'].pop())
    case('rpc.extra-opener', lambda v, a, d: v['rpcs'].insert(4, copy.deepcopy(v['rpcs'][3])))
    case('rpc.raw-changed', lambda v, a, d: v['rpcs'][-1]['result'].update(Raw='{}'))
    case('rpc.native-refusal', lambda v, a, d: v['rpcs'][3]['result']['Response'].update(Opened=False))
    case('rpc.native-wrong-spelling', lambda v, a, d: v['rpcs'][3]['params'].update(ResourceName=str(a[1] / common.REL_WORLD)))
    case('rpc.codec-schema-bool', lambda v, a, d: v['rpcs'][-1]['codec'].update(schema_version=True))
    case('rpc.final-ready-forged', lambda v, a, d: v['rpcs'][-1]['normalized_response'].update(world_matches=False))
    case('rpc.preliminary-missing', lambda v, a, d: v.update(preliminary=None))
    case('rpc.health-boolean-equivalence', lambda v, a, d: v['health'].update(Ok=1))
    case('rpc.duration-expired', lambda v, a, d: v['rpcs'][-1].update(duration_ms=8000))
    case('ownership.missing', lambda v, a, d: v['session_checks'].pop())
    case('ownership.reorder', lambda v, a, d: v['session_checks'].reverse())
    case('ownership.scalar', lambda v, a, d: v['session_checks'].__setitem__(0, 'wrong'))
    case('ownership.pid-float', lambda v, a, d: v['session_checks'][0].update(process_id=2222.0))
    case('ownership.ticks-float', lambda v, a, d: v['session_checks'][0].update(start_ticks=float(v['session']['start_ticks'])))
    case('ownership.foreign', lambda v, a, d: v['session_checks'][0].update(process_id=2223))
    case('logs.hash', lambda v, a, d: v['raw_logs'][0].update(sha256='b' * 64))
    case('logs.missing', lambda v, a, d: v.update(raw_logs=[]))
    contract_spec = importlib.util.spec_from_file_location('layered_receipts_driver', ROOT / 'scripts/verify-layered-world.py')
    driver = importlib.util.module_from_spec(contract_spec)
    contract_spec.loader.exec_module(driver)
    contract = common.mod.parse((PACKAGE / 'source-contracts.json').read_bytes())
    metadata = [('contract.exact-source-only', None, True)]
    def metadata_case(name, mutate):
        metadata.append(('contract.' + name, mutate, False))
    for name, key, value in (('schema-bool', 'schema_version', True), ('profile', 'profile', 'invented'),
            ('authored-claim', 'engine_authored', True), ('loaded-claim', 'engine_loaded', True),
            ('helper-called-claim', 'native_creation_helper_called', True), ('world-name', 'world_name', 'foreign')):
        metadata_case(name, lambda v, k=key, r=value: v.update({k: r}))
    metadata_case('unknown-outer', lambda v: v.update(unreviewed=True))
    for name, key, value in (('packed-hash', 'packed_sha256', 'b' * 64), ('decoded-size-bool', 'decoded_size_bytes', True),
            ('offset-bool', 'packed_offset', True), ('whole-archive-claim', 'whole_archive_sha256', 'b' * 64),
            ('metadata-hex-type', 'metadata_after_name_hex', False), ('resource-path', 'resource_path', 'scripts/foreign.c')):
        metadata_case(name, lambda v, k=key, r=value: v['source_basis'].update({k: r}))
    metadata_case('unknown-source-basis', lambda v: v['source_basis'].update(unreviewed=True))
    metadata_case('overwrite-parameter', lambda v: v['source_basis']['parameters'].update(overwriteWorldFile=True))
    metadata_case('unknown-primary', lambda v: v['primary_declaration'].update(unreviewed=True))
    metadata_case('primary-hash', lambda v: v['primary_declaration'].update(sha256='b' * 64))
    metadata_case('primary-line-bool', lambda v: v['primary_declaration'].update(signature_line=True))
    metadata_case('file-order', lambda v: v['files'].reverse())
    metadata_case('unknown-file', lambda v: v['files'][0].update(unreviewed=True))
    metadata_case('file-size-bool', lambda v: v['files'][0].update(size_bytes=True))
    metadata_case('trailing-newline-bool01', lambda v: v['files'][0].update(trailing_newline=1))
    metadata_case('file-hash', lambda v: v['files'][1].update(sha256='b' * 64))
    metadata_case('file-source-lines', lambda v: v['files'][0].update(source_write_lines=[70, 71, True]))
    metadata_case('file-newlines', lambda v: v['files'][0].update(line_ending='CRLF'))
    metadata_case('file-path', lambda v: v['files'][1].update(path='foreign.layer'))
    metadata_case('preservation-override', lambda v: v['preservation'].update(original_prepared_artifact='replace in place'))
    metadata_case('unknown-preservation', lambda v: v['preservation'].update(unreviewed=True))
    metadata_case('limits-removed', lambda v: v.update(limitations=[]))
    # Preserve the original76 ID/order exactly; new CLI cases follow metadata.
    extra = []
    def extra_case(name, mutate=None, accept=False, opening='startup-cli'):
        extra.append(('cli.' + name, mutate, accept, opening))
    extra_case('positive.ten-inputs-exact-eight-argv-no-native-opener', accept=True)
    extra_case('selected-as-registered', lambda v, a, d: a.__setitem__(8, 'module-netapi-registered'))
    extra_case('registered-selected-as-cli', lambda v, a, d: a.__setitem__(8, 'startup-cli'), opening='module-netapi-registered')
    extra_case('profile.normal-native-rejected', lambda v, a, d: a.__setitem__(8, 'netapi-resource'))
    extra_case('profile.module-absolute-native-rejected', lambda v, a, d: a.__setitem__(8, 'module-netapi-resource'))
    extra_case('profile.unknown-rejected', lambda v, a, d: a.__setitem__(8, 'invented-profile'))
    extra_case('arguments.six-native', lambda v, a, d: v['arguments'].__delitem__(slice(6, None)))
    extra_case('arguments.load-missing', lambda v, a, d: v['arguments'].pop(6))
    extra_case('arguments.world-absolute-instead-of-relative', lambda v, a, d: v['arguments'].__setitem__(7, str(a[1] / common.REL_WORLD)))
    extra_case('arguments.world-foreign', lambda v, a, d: v['arguments'].__setitem__(7, 'worlds/foreign.ent'))
    extra_case('arguments.extra-opener', lambda v, a, d: v['arguments'].append('-open=foreign.ent'))
    extra_case('native-open.nonnull', lambda v, a, d: v.update(native_open={'Opened': True}))
    extra_case('preliminary.nonnull', lambda v, a, d: v.update(preliminary=copy.deepcopy(v['completion'])))
    extra_case('native-open.missing', lambda v, a, d: v.pop('native_open'))
    extra_case('preliminary.missing', lambda v, a, d: v.pop('preliminary'))
    extra_case('rpc.inserted-openresource', lambda v, a, d: v['rpcs'].insert(2, {
        'function': 'OpenResource', 'action': None, 'params': {'ResourceName': common.RESOURCE},
        'elapsed_ms': 250, 'timeout_ms': 8000, 'duration_ms': 10,
        'result': {'Ok': True, 'Function': 'OpenResource', 'ErrorCode': 'Ok', 'Response': {'Opened': True}, 'Raw': '{"Opened":true}'},
        'normalized_response': {'Opened': True},
        'codec': {'schema_version': 1, 'name': 'enfusion.jsonapistruct.bool01.v1', 'numeric_boolean_fields': []}}))
    extra_case('rpc.mechanism-native', lambda v, a, d: v['rpcs'][-1]['normalized_response'].update(mechanism='module_registered_netapi'))
    extra_case('layer.missing', lambda v, a, d: (a[1] / LAYER).unlink())
    extra_case('layer.changed-with-honest-manifest', lambda v, a, d: declared_mutation(v, a, LAYER, b'GenericWorldEntity {\n}\n'))
    extra_case('world.changed-with-honest-manifest', lambda v, a, d: declared_mutation(v, a, common.REL_WORLD, b'SubScene {\n}\n'))
    original_expected = [row[0] for row in planned] + [row[0] for row in metadata]
    if len(original_expected) != 76:
        raise AssertionError('Original76 registry changed')
    expected = original_expected + [row[0] for row in extra]
    if len(expected) != len(set(expected)):
        raise AssertionError('Duplicate expected case identity')
    paths = [Path(__file__).resolve(), ROOT / 'scripts/verify-layered-world.py', ROOT / 'scripts/verify-workbench-startup.py', ROOT / 'scripts/verify-component-engine.py',
             common.ADAPTER, common.PACKAGE / 'rpc.c.in', PACKAGE / common.REL_WORLD, PACKAGE / LAYER,
             PACKAGE / 'source-contracts.json', PACKAGE / 'README.md', *common.mod.bundle_paths()]
    frozen = {str(path): identity(path) for path in paths}
    retained = []
    for index, (name, item) in enumerate(frozen.items()):
        dest = work / 'inputs' / (str(index).zfill(3) + '-' + Path(name).name + '.input')
        put(dest, Path(name).read_bytes())
        if identity(dest)['sha256'] != item['sha256']:
            raise AssertionError('Source changed during retention')
        retained.append({**item, 'retained': str(dest)})
    record = {'schema_version': 1, 'operation': 'verify.layered_world.receipts.inert', 'status': 'failure', 'expected_case_ids': expected,
              'expected_count': len(expected), 'original_expected_case_ids': original_expected, 'added_case_ids': [row[0] for row in extra],
              'cases': [], 'verification_inputs': frozen, 'retained_inputs': retained,
              'scope': {'host': 'not_run', 'compiler': 'not_run', 'engine': 'not_run', 'signals': 'not_run',
                        'readiness': 'synthetic_envelope_only', 'callback_delivery': 'not_run'}}
    try:
        def execute(name, mutate, accept, layered, index, opening='module-netapi-registered'):
            value, args, directory = fixture(work, index, layered, opening)
            common.saved(directory / 'original-envelope.json', value)
            outcome, rejection = None, None
            try:
                if mutate:
                    mutate(value, args, directory)
                common.saved(directory / 'tested-envelope.json', value)
                outcome = common.validate_runtime(value, *args)
            except (common.mod.Failure, OSError, ValueError) as exc:
                rejection = {'type': type(exc).__name__, 'status': getattr(exc, 'status', 'failure'), 'message': str(exc)}
            except Exception as exc:
                record['cases'].append({'id': name, 'status': 'failed', 'reason': 'validator_crashed', 'exception': {'type': type(exc).__name__, 'message': str(exc)}})
                return
            passed = (rejection is None and outcome.get('completed_case_ids') == list(common.READY_CASES) and outcome.get('callback_delivery') == 'not_run') if accept else rejection is not None
            record['cases'].append({'id': name, 'status': 'passed' if passed else 'failed', 'expected_accept': accept, 'outcome': outcome, 'rejection': rejection})
        for index, (name, mutate, accept, layered) in enumerate(planned):
            execute(name, mutate, accept, layered, index)
        for name, mutate, accept in metadata:
            value, rejection = copy.deepcopy(contract), None
            try:
                if mutate:
                    mutate(value)
                driver.validate_contract(value)
            except (driver.mod.Failure, OSError, ValueError) as exc:
                rejection = {'type': type(exc).__name__, 'status': getattr(exc, 'status', 'failure'), 'message': str(exc)}
            except Exception as exc:
                record['cases'].append({'id': name, 'status': 'failed', 'reason': 'validator_crashed', 'exception': {'type': type(exc).__name__, 'message': str(exc)}})
                continue
            record['cases'].append({'id': name, 'status': 'passed' if ((rejection is None) == accept) else 'failed',
                                    'expected_accept': accept, 'rejection': rejection})
        for index, (name, mutate, accept, opening) in enumerate(extra, len(planned)):
            execute(name, mutate, accept, True, index, opening)
        actual = [row['id'] for row in record['cases']]
        record['case_set_complete'] = actual == expected and len(actual) == len(set(actual))
        record['completed_count'] = len(actual)
        record['passed_count'] = sum(row['status'] == 'passed' for row in record['cases'])
        record['failed_count'] = len(actual) - record['passed_count']
        record['source_unchanged'] = {str(path): identity(path) for path in paths} == frozen
        record['status'] = 'success' if record['case_set_complete'] and not record['failed_count'] and record['source_unchanged'] else 'failure'
    finally:
        common.saved(work / 'result.json', record)
        print(json.dumps({'receipt': identity(work / 'result.json'), 'status': record['status'], 'expected_count': len(expected),
                          'completed_count': record.get('completed_count'), 'passed_count': record.get('passed_count')}))
    return 0 if record['status'] == 'success' else 1


if __name__ == '__main__':
    raise SystemExit(main())
