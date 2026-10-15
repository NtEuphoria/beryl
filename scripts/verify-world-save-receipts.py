#!/usr/bin/env python3
"""Inert world-save eligibility receipt faults; no subprocess or engine use."""
from pathlib import Path
import copy
import hashlib
import importlib.util
import json
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
SPEC = importlib.util.spec_from_file_location('world_save_receipt_target', ROOT / 'scripts/verify-world-save.py')
target = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(target)


def file_identity(path):
    data = Path(path).read_bytes()
    return {'path': str(path), 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def put(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('wb') as stream:
        if stream.write(data) != len(data):
            raise OSError('Incomplete synthetic fixture write')


def replace_observation(value, mutate):
    row = value['rpcs'][-1]
    body = copy.deepcopy(row['result']['Response'])
    mutate(body)
    normalized, codec = target.normalize(body)
    row['result']['Response'] = body
    row['result']['Raw'] = json.dumps(body, separators=(',', ':'))
    row['normalized_response'], row['codec'] = normalized, codec
    value['completion'] = copy.deepcopy(normalized)


def fixture(work, number):
    directory = work / ('fixture-' + str(number).zfill(3))
    addon = directory / 'probe-addon'
    files = {}
    for name in sorted(target.base.BASE_FILES | {target.HANDLER_PATH}):
        path = addon / name
        data = ('INERT SYNTHETIC INPUT ' + name + '\n').encode()
        put(path, data)
        files[name] = hashlib.sha256(data).hexdigest()
    manifest = {'schema_version': 1, 'files': files, 'directories': sorted(target.bounded.expected_directories(files))}
    manifest_path = directory / 'input-manifest.json'
    put(manifest_path, (json.dumps(manifest, indent=2) + '\n').encode())
    put(addon / 'resourceDatabase.rdb', b'INERT DERIVED RESOURCE DATABASE\n')
    engine = directory / 'engine.fixture'
    put(engine, b'NOT AN EXECUTABLE; NEVER LAUNCHED\n')
    engine_id = file_identity(engine)
    binding = {'sha256': engine_id['sha256'], 'version': 'inert.synthetic.engine'}
    tools = {name: hashlib.sha256(('INERT TOOL ' + name).encode()).hexdigest() for name in target.base.RUNTIME_TOOLS}
    token = 'a' * 64
    output = addon / target.OUTPUT_REL
    body = {name: '' for name in target.STRINGS}
    body.update({name: name not in ('in_play_mode', 'wb_game_mode') for name in target.BOOLS})
    body.update(token=token, action='observe', status='eligible', output_path=output.as_posix())
    normalized, codec = target.normalize(body)
    session = {'process_id': 2222, 'start_ticks': 639272000000000001, 'reused': False,
               'project': str(addon), 'executable': str(engine)}
    calls = []
    for function, response, start, duration in (
            ('IsWorkbenchRunning', {'IsRunning': True, 'ScriptsCompiled': True}, 100, 20),
            ('GetLoadedProjects', {'Loaded Projects': [target.base.PROJECT_ID]}, 200, 10),
            (target.FUNCTION, body, 300, 30)):
        reply = {'Ok': True, 'Function': function, 'ErrorCode': 'Ok', 'Response': copy.deepcopy(response),
                 'Raw': json.dumps(response, separators=(',', ':'))}
        row = {'function': function, 'params': {'token': token, 'action': 'observe'} if function == target.FUNCTION else {},
               'action': 'observe' if function == target.FUNCTION else None, 'elapsed_ms': start,
               'duration_ms': duration, 'timeout_ms': 8000, 'result': reply}
        if function == target.FUNCTION:
            row.update(normalized_response=copy.deepcopy(normalized), codec=codec)
        calls.append(row)
    checks = []
    for site, elapsed in [('startup.identity', 1), ('port.check', 10),
            ('before.IsWorkbenchRunning', 100), ('after.IsWorkbenchRunning', 120),
            ('before.GetLoadedProjects', 200), ('after.GetLoadedProjects', 210),
            ('before.' + target.FUNCTION, 300), ('after.' + target.FUNCTION, 330)]:
        checks.append({'site': site, 'process_id': session['process_id'], 'start_ticks': session['start_ticks'],
                       'executable': str(engine), 'elapsed_ms': elapsed})
    log = directory / 'eligibility-logs' / 'retained-script.log'
    put(log, b'INERT SYNTHETIC LOG; NO ENGINE EXECUTION\n')
    derived = target.bounded.staged_tree(addon, files)
    value = {
        'schema_version': 1, 'stage': 'eligibility_complete', 'status': 'success', 'function': target.FUNCTION,
        'token': token, 'project_id': target.base.PROJECT_ID, 'engine_sha256': binding['sha256'],
        'engine_version': binding['version'], 'engine_path': str(engine), 'tools': copy.deepcopy(tools),
        'adapter_sha256': file_identity(target.ADAPTER)['sha256'],
        'scope': 'read-only world-save eligibility observation only', 'mechanism': 'empty_world_save_eligibility', 'callback_execution': 'not_run',
        'play': 'not_run', 'spawn': 'not_run', 'save': 'not_run', 'policy_changes': 'not_run',
        'limits': {'stage_ms': 30000, 'rpc_ms': 8000, 'total_ms': 180000, 'cleanup_ms': 5000,
                   'max_polls': 64, 'native_launch_and_bridge_calls_not_hard_cancelled': True, 'raw_logs_aggregate_bytes': 67108864},
        'evidence_errors': [], 'cleanup_errors': [], 'cleanup': 'owned_process_stopped', 'elapsed_ms': 2000,
        'raw_log_observation': 'snapshot_after_confirmed_owned_exit',
        'input_manifest': {'path': str(manifest_path), 'sha256': file_identity(manifest_path)['sha256']},
        'staged_inputs': copy.deepcopy(manifest),
        'engine_outputs': [{'path': row['path'], 'relative': row['relative_path'], 'bytes': row['bytes'], 'sha256': row['sha256']} for row in derived],
        'expected_output': str(output), 'session': session,
        'arguments': ['-gproj', str(addon / 'addon.gproj'), '-noOpenLastResource', '-scriptAuthorizeAll', '-wbmodule=WorldEditor', '-run'],
        'port_checks': [{'elapsed_ms': 10, 'listening': True, 'owning_process': session['process_id']}],
        'rpcs': calls, 'health': copy.deepcopy(calls[0]['result']), 'loaded_projects': copy.deepcopy(calls[1]['result']),
        'completion': normalized, 'session_checks': checks,
        'raw_logs': [{'retained': str(log), 'bytes': log.stat().st_size, 'sha256': file_identity(log)['sha256']}],
    }
    value['startup'] = {'mechanism': 'empty_world_save_eligibility', 'argv': copy.deepcopy(value['arguments']),
                        'working_directory': str(directory), 'use_shell_execute': False, 'create_no_window': True,
                        'window_style': 'Hidden', 'launch_returned': True, 'process_id': session['process_id'], 'polls': 0}
    args = (token, addon, engine, binding, tools, manifest_path, manifest, value['adapter_sha256'])
    return value, args, directory


def main():
    work = Path(tempfile.mkdtemp(prefix='world-save-receipts-', dir=ROOT / 'build'))
    print('Inert eligibility receipt evidence: ' + str(work), flush=True)
    registry = []
    def case(name, change=None, accept=False, eligibility=None):
        registry.append((name, change, accept, eligibility))
    case('positive.eligible', accept=True, eligibility='eligible')
    def unavailable(v, a, d):
        replace_observation(v, lambda b: b.update(game_editor_present=False, game_api_present=False, game_world_present=False,
                            api_same=False, world_same=False, status='unavailable', failure='Game editor unavailable'))
        v['status'] = 'unavailable'
    case('positive.unavailable', unavailable, True, 'unavailable')
    def numeric(v, a, d):
        replace_observation(v, lambda b: b.update({key: int(b[key]) for key in target.BOOLS}))
    case('positive.bool01', numeric, True, 'eligible')
    case('positive.already-exited', lambda v, a, d: v.update(cleanup='owned_process_already_exited'), True, 'eligible')
    for name, key, replacement in (
            ('schema-bool', 'schema_version', True), ('schema-wrong', 'schema_version', 2),
            ('stage', 'stage', 'prepared'), ('status', 'status', 'failure'), ('function', 'function', 'UnknownHandler'),
            ('token', 'token', 'b' * 64), ('project', 'project_id', 'UnknownProject'),
            ('engine-hash', 'engine_sha256', 'b' * 64), ('engine-version', 'engine_version', 'wrong'),
            ('engine-path', 'engine_path', 'C:/unowned.fixture'), ('adapter', 'adapter_sha256', 'b' * 64),
            ('scope', 'scope', 'whole world authored'), ('save', 'save', 'executed_success'),
            ('mechanism', 'mechanism', 'native_netapi'),
            ('callback', 'callback_execution', 'executed_success'), ('policy', 'policy_changes', 'changed'),
            ('cleanup', 'cleanup', 'stop_requested'), ('elapsed-bool', 'elapsed_ms', True),
            ('elapsed-expired', 'elapsed_ms', 180000), ('elapsed-negative', 'elapsed_ms', -1),
            ('errors', 'evidence_errors', [{'message': 'unconfirmed exit'}]),
            ('cleanup-errors', 'cleanup_errors', [{'message': 'unconfirmed exit'}]),
            ('log-observation', 'raw_log_observation', 'point_in_time_exit_unconfirmed'),
            ('expected-output', 'expected_output', 'C:/unowned.ent')):
        case('envelope.' + name, lambda v, a, d, k=key, r=replacement: v.update({k: r}))
    for key in ('schema_version', 'evidence_errors', 'cleanup', 'raw_logs', 'completion', 'session', 'input_manifest', 'startup', 'cleanup_errors', 'raw_log_observation'):
        case('envelope.missing.' + key, lambda v, a, d, k=key: v.pop(k))
    for key in ('stage_ms', 'rpc_ms', 'total_ms', 'cleanup_ms', 'max_polls', 'raw_logs_aggregate_bytes'):
        case('limit.' + key, lambda v, a, d, k=key: v['limits'].update({k: True}))
    case('limit.nonhardcancel-bool01', lambda v, a, d: v['limits'].update(native_launch_and_bridge_calls_not_hard_cancelled=1))
    case('tools.missing', lambda v, a, d: v['tools'].pop(next(iter(v['tools']))))
    case('manifest.hash', lambda v, a, d: v['input_manifest'].update(sha256='b' * 64))
    case('manifest.staged', lambda v, a, d: v['staged_inputs']['files'].update({'extra': 'b' * 64}))
    case('manifest.source-changed', lambda v, a, d: put(a[1] / next(iter(a[6]['files'])), b'CHANGED\n'))
    case('manifest.extra-source', lambda v, a, d: put(a[1] / 'unexpected.txt', b'UNACCOUNTED\n'))
    def manifest_bool(v, a, d):
        altered = {**a[6], 'schema_version': True}
        put(a[5], (json.dumps(altered) + '\n').encode())
        v['input_manifest']['sha256'] = file_identity(a[5])['sha256']
    case('manifest.boolean-schema', manifest_bool)
    case('output.namespace-created', lambda v, a, d: (a[1] / target.OUTPUT_REL).parent.mkdir())
    for name, key, replacement in (('relative', 'relative', 'other.rdb'), ('hash', 'sha256', 'b' * 64),
                                   ('bytes', 'bytes', 1), ('bytes-bool', 'bytes', True), ('path', 'path', 'C:/foreign.rdb')):
        case('derived.' + name, lambda v, a, d, k=key, r=replacement: v['engine_outputs'][0].update({k: r}))
    case('derived.missing', lambda v, a, d: v['engine_outputs'].clear())
    case('derived.unknown-field', lambda v, a, d: v['engine_outputs'][0].update(extra=True))
    case('derived.removed', lambda v, a, d: (a[1] / 'resourceDatabase.rdb').unlink())
    for name, key, replacement in (('pid-bool', 'process_id', True), ('pid-float', 'process_id', 2222.0),
            ('ticks-bool', 'start_ticks', True), ('ticks-float', 'start_ticks', 639272000000000001.0),
            ('executable', 'executable', 'C:/foreign.fixture'), ('project', 'project', 'C:/foreign'), ('reused', 'reused', True)):
        case('session.' + name, lambda v, a, d, k=key, r=replacement: v['session'].update({k: r}))
    case('arguments.load', lambda v, a, d: v['arguments'].append('-load=unknown.ent'))
    for name, key, replacement in (('mechanism', 'mechanism', 'wrong'), ('argv', 'argv', []),
            ('relative-cwd', 'working_directory', 'relative'), ('shell', 'use_shell_execute', True),
            ('shell-bool01', 'use_shell_execute', 0), ('window', 'create_no_window', False),
            ('style', 'window_style', 'Normal'), ('launch', 'launch_returned', False),
            ('launch-bool01', 'launch_returned', 1), ('pid-float', 'process_id', 2222.0),
            ('pid-foreign', 'process_id', 2223), ('polls-bool', 'polls', True),
            ('polls-count', 'polls', 1), ('polls-bound', 'polls', 64)):
        case('startup.' + name, lambda v, a, d, k=key, r=replacement: v['startup'].update({k: r}))
    case('ports.empty', lambda v, a, d: v['port_checks'].clear())
    case('ports.missing', lambda v, a, d: v.pop('port_checks'))
    case('ports.scalar', lambda v, a, d: v.update(port_checks=['wrong']))
    for name, key, replacement in (('foreign-pid', 'owning_process', 2223), ('bool-pid', 'owning_process', True),
                                   ('not-ready', 'listening', False), ('elapsed-bool', 'elapsed_ms', True)):
        case('ports.' + name, lambda v, a, d, k=key, r=replacement: v['port_checks'][0].update({k: r}))
    case('rpc.missing', lambda v, a, d: v['rpcs'].pop())
    case('rpc.extra', lambda v, a, d: v['rpcs'].append(copy.deepcopy(v['rpcs'][-1])))
    case('rpc.reorder', lambda v, a, d: v['rpcs'].reverse())
    case('rpc.scalar', lambda v, a, d: v.update(rpcs=['wrong', v['rpcs'][1], v['rpcs'][2]]))
    for name, key, replacement in (('params', 'params', {'token': 'a' * 64, 'action': 'save'}),
            ('action', 'action', 'save'), ('timeout-bool', 'timeout_ms', True), ('timeout-large', 'timeout_ms', 8001),
            ('duration-bool', 'duration_ms', True), ('duration-deadline', 'duration_ms', 8000),
            ('elapsed-bool', 'elapsed_ms', True), ('elapsed-outside', 'elapsed_ms', 2000)):
        case('rpc.' + name, lambda v, a, d, k=key, r=replacement: v['rpcs'][-1].update({k: r}))
    case('rpc.raw-divergence', lambda v, a, d: v['rpcs'][-1]['result'].update(Raw='{"different":true}'))
    case('rpc.raw-malformed', lambda v, a, d: v['rpcs'][-1]['result'].update(Raw='{'))
    case('rpc.reply-extra', lambda v, a, d: v['rpcs'][-1]['result'].update(extra=True))
    case('rpc.reply-missing', lambda v, a, d: v['rpcs'][-1]['result'].pop('Raw'))
    case('rpc.reply-not-ok', lambda v, a, d: v['rpcs'][-1]['result'].update(Ok=False))
    case('rpc.reply-wrong-function', lambda v, a, d: v['rpcs'][-1]['result'].update(Function='Other'))
    case('rpc.codec', lambda v, a, d: v['rpcs'][-1]['codec'].update(numeric_boolean_fields=['api_same']))
    case('rpc.codec-boolean-schema', lambda v, a, d: v['rpcs'][-1]['codec'].update(schema_version=True))
    case('rpc.completion', lambda v, a, d: v['completion'].update(api_same=False))
    case('rpc.normalized', lambda v, a, d: v['rpcs'][-1]['normalized_response'].update(world_same=False))
    case('rpc.health', lambda v, a, d: v['health']['Response'].update(ScriptsCompiled=False))
    case('rpc.loaded', lambda v, a, d: v['loaded_projects']['Response'].update({'Loaded Projects': []}))
    case('rpc.health-boolean-equivalence', lambda v, a, d: v['health'].update(Ok=1))
    case('rpc.loaded-boolean-equivalence', lambda v, a, d: v['loaded_projects'].update(Ok=1))
    for name, key, replacement in (('stale-token', 'token', 'b' * 64), ('wrong-action', 'action', 'save'),
            ('foreign-output', 'output_path', 'C:/foreign.ent'), ('named-world', 'wb_world_path', 'world.ent'),
            ('play', 'in_play_mode', True), ('wrong-reason', 'failure', 'wrong')):
        case('observation.' + name, lambda v, a, d, k=key, r=replacement: replace_observation(v, lambda b: b.update({k: r})))
    case('observation.unavailable-envelope-success', lambda v, a, d: (unavailable(v, a, d), v.update(status='success')))
    case('observation.eligible-envelope-unavailable', lambda v, a, d: v.update(status='unavailable'))
    case('checks.missing', lambda v, a, d: v['session_checks'].pop())
    case('checks.extra', lambda v, a, d: v['session_checks'].append(copy.deepcopy(v['session_checks'][-1])))
    case('checks.reorder', lambda v, a, d: v['session_checks'].reverse())
    case('checks.scalar', lambda v, a, d: v['session_checks'].__setitem__(0, 'wrong'))
    for name, key, replacement in (('pid-float', 'process_id', 2222.0), ('ticks-float', 'start_ticks', 639272000000000001.0),
            ('foreign-pid', 'process_id', 2223), ('foreign-ticks', 'start_ticks', 639272000000000002),
            ('executable', 'executable', 'C:/other.fixture'), ('site', 'site', 'unknown'), ('elapsed-bool', 'elapsed_ms', True)):
        case('checks.' + name, lambda v, a, d, k=key, r=replacement: v['session_checks'][0].update({k: r}))
    case('logs.empty', lambda v, a, d: v['raw_logs'].clear())
    case('logs.scalar', lambda v, a, d: v.update(raw_logs=['wrong']))
    case('logs.hash', lambda v, a, d: v['raw_logs'][0].update(sha256='b' * 64))
    case('logs.bytes', lambda v, a, d: v['raw_logs'][0].update(bytes=1))
    case('logs.bytes-bool', lambda v, a, d: v['raw_logs'][0].update(bytes=True))
    case('logs.outside', lambda v, a, d: v['raw_logs'][0].update(retained=str(d / 'engine.fixture')))
    expected = [row[0] for row in registry]
    if len(expected) != len(set(expected)):
        raise AssertionError('Duplicate predeclared case identity')
    frozen_paths = [Path(__file__).resolve(), ROOT / 'scripts/verify-world-save.py', target.ADAPTER,
                    ROOT / 'scripts/verify-workbench-startup.py', ROOT / 'scripts/verify-component-engine.py',
                    target.PACKAGE / 'rpc.c.in', target.PACKAGE / 'README.md', *target.mod.bundle_paths()]
    frozen = {str(p): file_identity(p) for p in frozen_paths}
    retained = []
    for number, (name, item) in enumerate(frozen.items()):
        path = work / 'inputs' / (str(number).zfill(3) + '-' + Path(name).name + '.input')
        put(path, Path(name).read_bytes())
        if file_identity(path)['sha256'] != item['sha256']:
            raise AssertionError('Source changed during retention')
        retained.append({**item, 'retained': str(path)})
    record = {'schema_version': 1, 'operation': 'verify.world_save.receipts.inert', 'status': 'failure',
              'expected_case_ids': expected, 'expected_count': len(expected), 'cases': [], 'verification_inputs': frozen,
              'retained_inputs': retained, 'scope': {'host': 'not_run', 'compiler': 'not_run', 'engine': 'not_run',
                    'process_signals': 'not_run', 'save': 'not_run', 'semantic_mutants': 'not_run',
                    'receipt_validation': 'synthetic_only'}}
    try:
        for number, (name, change, accept, eligibility) in enumerate(registry):
            value, args, directory = fixture(work, number)
            target.saved(directory / 'original-envelope.json', value)
            caught, outcome = None, None
            try:
                if change:
                    change(value, args, directory)
                target.saved(directory / 'tested-envelope.json', value)
                outcome = target.validate_runtime(value, *args)
            except (target.mod.Failure, OSError, ValueError) as exc:
                caught = {'type': type(exc).__name__, 'status': getattr(exc, 'status', 'failure'), 'message': str(exc)}
            except Exception as exc:
                record['cases'].append({'id': name, 'status': 'failed', 'reason': 'validator_crashed',
                                        'exception': {'type': type(exc).__name__, 'message': str(exc)}})
                continue
            passed = (caught is None and outcome.get('eligibility') == eligibility) if accept else caught is not None
            record['cases'].append({'id': name, 'status': 'passed' if passed else 'failed',
                    'expected': {'accept': accept, 'eligibility': eligibility}, 'outcome': outcome, 'rejection': caught})
        completed = [row['id'] for row in record['cases']]
        exact = completed == expected and len(set(completed)) == len(expected)
        current = {str(p): file_identity(p) for p in frozen_paths}
        record['source_unchanged'] = current == frozen
        record['completed_count'] = len(completed)
        record['passed_count'] = sum(row['status'] == 'passed' for row in record['cases'])
        record['failed_count'] = len(completed) - record['passed_count']
        record['case_set_complete'] = exact
        record['status'] = 'success' if exact and not record['failed_count'] and record['source_unchanged'] else 'failure'
    finally:
        target.saved(work / 'result.json', record)
        print(json.dumps({'path': str(work / 'result.json'), **file_identity(work / 'result.json'),
                          'status': record['status'], 'expected_count': len(expected),
                          'completed_count': record.get('completed_count'), 'passed_count': record.get('passed_count')}))
    return 0 if record['status'] == 'success' else 1


if __name__ == '__main__':
    raise SystemExit(main())
