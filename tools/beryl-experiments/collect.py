#!/usr/bin/env python3
"""Collect raw Enfusion construction intervals into an immutable evidence journal.

The first collector is intentionally exploratory: engine-wide counters are not
workload allocations, and repeated batches in one RPC are not independent units.
It never exports incomplete observations as evaluator-v1 measurements.
"""
import argparse
from fractions import Fraction
import json
from pathlib import Path
import re
import sys
import time

import evaluate as ev

FINGERPRINTS = ('artifact', 'sources', 'compiler', 'toolchain', 'bindings', 'engine',
                'environment', 'workload', 'semantic_contract', 'tool', 'integration')
TIMER = 'System.GetTickCount'
TARGET_FIELDS = ('schema_version', 'kind', 'token', 'scope_name', 'timer_api',
                 'tick_unit', 'executed', 'failures', 'expected_runs', 'rows')
TRUST = ('File identity, target framing, order, completeness and receipt consistency checked. '
         'Bridge ownership, scope review, underlying executable identities and semantic '
         'coverage still depend on the retained producer/reviewer evidence.')


def schema(value, kind, names):
    ev.fields(value, ('schema_version', 'kind', *names), kind)
    ev.require(type(value['schema_version']) is int and value['schema_version'] == 1
               and value['kind'] == kind, 'unsupported ' + kind + ' schema')


def words(value, label):
    ev.require(type(value) is str and 0 < len(value) <= 4096, label + ': missing description')
    return value


def make_plan(experiment_id, phase, role, case_ids, pair_count, operations, scope_name, now=None):
    plan = {'schema_version': 1, 'kind': 'beryl.performance.schedule',
            'experiment_id': experiment_id, 'phase': phase, 'role': role,
            'created_utc_ns': time.time_ns() if now is None else now,
            'scope_name': scope_name, 'operations': operations,
            'case_ids': case_ids, 'pair_count': pair_count, 'runs': []}
    ev.token(experiment_id, 'experiment ID')
    validate_schedule_head(plan)
    for pair in range(pair_count):
        case = case_ids[pair % len(case_ids)]
        first = 'a' if (pair // len(case_ids)) % 2 == 0 else 'b'
        for side in (first, 'b' if first == 'a' else 'a'):
            plan['runs'].append({'unit_id': f'{experiment_id}:{phase}:{pair:04}',
                                 'side': side, 'ordinal': len(plan['runs']),
                                 'case_id': case, 'operations': operations})
    return plan


def validate_schedule_head(plan):
    schema(plan, 'beryl.performance.schedule', ('experiment_id', 'phase', 'role',
           'created_utc_ns', 'scope_name', 'operations', 'case_ids', 'pair_count', 'runs'))
    ev.token(plan['experiment_id'], 'experiment ID')
    ev.token(plan['scope_name'], 'scope name')
    ev.integer(plan['created_utc_ns'], 'schedule creation', 1)
    ev.require(plan['phase'] in ('exploratory', 'pilot', 'candidate'), 'unknown phase')
    roles = {'exploratory': ('exploratory',), 'pilot': ('calibration',),
             'candidate': ('training', 'selection', 'held_out')}
    ev.require(plan['role'] in roles[plan['phase']], 'phase/role mismatch')
    cases = plan['case_ids']
    ev.require(type(cases) is list and 1 <= len(cases) <= 64, 'invalid case selection')
    for case in cases:
        ev.token(case, 'case ID')
    ev.require(len(set(cases)) == len(cases), 'duplicate case selection')
    n = ev.integer(plan['pair_count'], 'pair count', 30)
    ev.require(n <= 1024 and n % (2 * len(cases)) == 0,
               'pairs must be <=1024 and balanced separately for every case')
    ev.require(ev.integer(plan['operations'], 'operations', 1) <= 10000, 'operation quota')


def validate_plan(plan):
    validate_schedule_head(plan)
    expected = make_plan(plan['experiment_id'], plan['phase'], plan['role'], plan['case_ids'],
                         plan['pair_count'], plan['operations'], plan['scope_name'], plan['created_utc_ns'])
    ev.require(ev.canonical(plan) == ev.canonical(expected), 'altered or unbalanced schedule')


def raw_integer(text, label, maximum=2**31 - 1):
    ev.require(type(text) is str and re.fullmatch(r'0|[1-9][0-9]*', text), label + ': invalid raw integer')
    value = int(text)
    ev.require(value <= maximum, label + ': integer exceeds admitted range')
    return value


def parse_target(target, plan, token):
    ev.fields(target, TARGET_FIELDS, 'target response')
    ev.require(type(target['schema_version']) is int and target['schema_version'] == 1
               and target['kind'] == 'beryl.performance.target', 'unsupported target schema')
    ev.require(target['token'] == token and target['scope_name'] == plan['scope_name'],
               'target token/scope mismatch')
    ev.require(target['timer_api'] == TIMER and target['tick_unit'] == 'ms', 'unsupported timer')
    for key in ('executed', 'failures', 'expected_runs'):
        ev.integer(target[key], key)
    ev.require(target['executed'] == 1 and target['failures'] == 0, 'failed or incomplete target execution')
    ev.require(target['expected_runs'] == len(plan['runs']), 'target expected-run mismatch')
    rows = target['rows']
    ev.require(type(rows) is list and len(plan['runs']) + 1 <= len(rows) <= len(plan['runs']) + 4096,
               'missing or excessive timer/run rows')
    runs, probes, previous_end = [], [], None
    for row in rows:
        ev.require(type(row) is str and len(row) <= 2048, 'invalid raw row')
        parts = row.split('|')
        if parts[0] == 'timer':
            ev.require(not runs and len(parts) == 4, 'timer rows must precede measurements')
            ev.require(raw_integer(parts[1], 'timer index') == len(probes), 'timer index mismatch')
            start, end = raw_integer(parts[2], 'probe start'), raw_integer(parts[3], 'probe end')
            probes.append({'start_tick': start, 'end_tick': end})
        else:
            ev.require(parts[0] == 'run' and len(parts) == 12, 'unknown or malformed target row')
            ev.require(len(runs) < len(plan['runs']), 'extra target measurement')
            expected = plan['runs'][len(runs)]
            observed = {'unit_id': parts[1], 'side': parts[2], 'ordinal': raw_integer(parts[3], 'ordinal'),
                        'case_id': parts[4], 'operations': raw_integer(parts[7], 'operations')}
            ev.require(observed == expected, 'measurement identity/order/count differs from schedule')
            start, end = raw_integer(parts[5], 'run start'), raw_integer(parts[6], 'run end')
            counters = {}
            for key, value in zip(('allocation_count_before', 'allocation_count_after',
                                   'allocation_kb_before', 'allocation_kb_after'), parts[8:]):
                counters[key] = None if value == 'unavailable' else raw_integer(value, key)
            runs.append({**observed, 'start_tick': start, 'end_tick': end,
                         'elapsed_ns': (end - start) * 1000000, 'raw_whole_engine_counters': counters})
        ev.require(end >= start and (previous_end is None or start >= previous_end),
                   'timer went backwards, wrapped, or measurement intervals overlap')
        previous_end = end
    ev.require(probes and len(runs) == len(plan['runs']), 'incomplete timer/run selection')
    ev.require(any(probe['end_tick'] > probe['start_tick'] for probe in probes), 'timer advancement unverified')
    return runs, probes


def validate_request(reader, request):
    schema(request, 'beryl.performance.collection', ('evidence_kind', 'token', 'schedule', 'runtime',
           'semantic', 'scope', 'ownership', 'fingerprints', 'raw_evidence'))
    ev.require(request['evidence_kind'] in ('synthetic_validation', 'collector_measurements'), 'unknown evidence kind')
    ev.token(request['token'], 'target token')
    ev.fields(request['fingerprints'], FINGERPRINTS, 'collection fingerprints')
    fingerprints = {name: ev.digest(reader.bytes(ref)) for name, ref in request['fingerprints'].items()}
    engine = reader.json(request['fingerprints']['engine'])
    schema(engine, 'beryl.performance.engine_identity', ('binary_sha256', 'version', 'evidence'))
    ev.require(type(engine['binary_sha256']) is str and re.fullmatch('[0-9a-f]{64}', engine['binary_sha256']),
               'invalid engine binary fingerprint')
    words(engine['version'], 'engine version')
    ev.require(reader.bytes(engine['evidence']), 'missing engine identity evidence')
    ev.require(type(request['raw_evidence']) is list and 1 <= len(request['raw_evidence']) <= 128,
               'retain raw producer evidence')
    for ref in request['raw_evidence']:
        ev.require(reader.bytes(ref), 'empty producer evidence')
    plan = reader.json(request['schedule'])
    validate_plan(plan)
    scope = reader.json(request['scope'])
    schema(scope, 'beryl.performance.scope', ('status', 'scope_name', 'description',
           'paid_components', 'excluded_components', 'resource_status', 'timer_evidence', 'review_evidence'))
    ev.require(scope['status'] == 'reviewed' and scope['scope_name'] == plan['scope_name'], 'unverified or wrong scope')
    words(scope['description'], 'scope')
    included, excluded = scope['paid_components'], scope['excluded_components']
    ev.require(type(included) is list and included and type(excluded) is list, 'invalid cost coverage')
    ev.require(all(type(v) is str for v in included + excluded), 'invalid cost name')
    ev.require(len(set(included + excluded)) == len(included + excluded)
               and set(included + excluded) == set(ev.COSTS), 'costs must be explicitly included or excluded once')
    ev.fields(scope['resource_status'], ev.RESOURCES, 'resource availability')
    # First adapter has no admitted per-workload physical memory instrumentation.
    for name, metric in scope['resource_status'].items():
        ev.fields(metric, ('status', 'reason'), name)
        ev.require(metric['status'] == 'unavailable', 'resource instrumentation is not admitted by collector v1')
        words(metric['reason'], name)
    for name in ('timer_evidence', 'review_evidence'):
        ev.require(reader.bytes(scope[name]), 'missing ' + name)
    runtime = reader.json(request['runtime'])
    ev.require(type(runtime) is dict and type(runtime.get('schema_version')) is int
               and runtime['schema_version'] == 1 and runtime.get('status') == 'success', 'failed/incomplete bridge session')
    rpc, session = runtime.get('rpc'), runtime.get('session')
    ev.require(type(rpc) is dict and rpc.get('Ok') is True and type(session) is dict,
               'missing successful owned RPC')
    ev.require(session.get('reused') is False, 'reused session is not admitted by this collector')
    owner = reader.json(request['ownership'])
    schema(owner, 'beryl.performance.ownership', ('status', 'process_id', 'start_time', 'project', 'evidence'))
    ev.require(owner['status'] == 'verified', 'unverified session ownership')
    ev.integer(owner['process_id'], 'owned process ID', 1)
    for key in ('process_id', 'start_time', 'project'):
        ev.require(type(session.get(key)) is type(owner[key]) and session[key] == owner[key], 'session ownership mismatch')
    words(owner['start_time'], 'session start'); words(owner['project'], 'owned project')
    ev.require(reader.bytes(owner['evidence']), 'missing ownership evidence')
    ev.require(runtime.get('engine_sha256') == engine['binary_sha256'] and runtime.get('engine_version') == engine['version'],
               'bridge engine fingerprint/version mismatch')
    runs, probes = parse_target(rpc.get('Response'), plan, request['token'])
    semantic = reader.json(request['semantic'])
    schema(semantic, 'beryl.performance.semantic', ('status', 'fingerprints', 'case_ids', 'expected_cases',
           'completed_cases', 'failures', 'comparison', 'evidence'))
    ev.fields(semantic['fingerprints'], ('artifact', 'workload', 'semantic_contract', 'engine'), 'semantic fingerprints')
    ev.require(all(semantic['fingerprints'][k] == fingerprints[k] for k in semantic['fingerprints']), 'stale semantic fingerprints')
    ev.require(semantic['status'] == 'complete', 'incomplete semantic receipt')
    ev.require(semantic['case_ids'] == plan['case_ids'], 'semantic case selection differs from measured schedule')
    expected = ev.integer(semantic['expected_cases'], 'semantic expected cases', 1)
    ev.require(expected == len(plan['case_ids']) and type(semantic['completed_cases']) is int and semantic['completed_cases'] == expected
               and type(semantic['failures']) is int and semantic['failures'] == 0, 'semantic mismatch/incomplete selection')
    ev.require(semantic['comparison'] in ('engine_operator_complete_payload', 'byte_exact_complete_observations'),
               'unadmitted semantic comparison')
    ev.require(reader.bytes(semantic['evidence']), 'missing semantic evidence')
    pairs = []
    for index in range(0, len(runs), 2):
        a, b = sorted(runs[index:index + 2], key=lambda run: run['side'])
        base, candidate = a['elapsed_ns'], b['elapsed_ns']
        pairs.append({'unit_id': a['unit_id'], 'case_id': a['case_id'], 'first': runs[index]['side'],
                      'a_elapsed_ns': base, 'b_elapsed_ns': candidate,
                      'relative_reduction': ev.rational(Fraction(base - candidate, base)) if base else None})
    positive = [Fraction(pair['a_elapsed_ns'] - pair['b_elapsed_ns'], pair['a_elapsed_ns'])
                for pair in pairs if pair['a_elapsed_ns'] > 0]
    ordered = sorted(positive)
    median = ((ordered[(len(ordered) - 1) // 2] + ordered[len(ordered) // 2]) / 2) if ordered else None
    blockers = ['same-session batches are dependent; no reset-equivalence or IID evidence',
                'per-workload physical resources and allocation/lifetime behavior unavailable',
                'no evaluator-v1 complete paid-component receipts',
                'pilot freeze, candidate selection and held-out history not established by this collector']
    if excluded:
        blockers.append('excluded paid-cost categories: ' + ', '.join(excluded))
    if any(run['elapsed_ns'] == 0 for run in runs):
        blockers.append('one or more intervals are below the observed integer-millisecond timer granularity')
    return {'schema_version': 1, 'kind': 'beryl.performance.collection_result',
            'status': 'collected_exploratory', 'evidence_kind': request['evidence_kind'],
            'experiment_id': plan['experiment_id'], 'phase': plan['phase'], 'role': plan['role'],
            'scope': scope['description'], 'fingerprints': fingerprints,
            'session': {key: session[key] for key in ('process_id', 'start_time', 'project')},
            'timer': {'api': TIMER, 'raw_unit': 'ms', 'ns_per_tick_unit': 1000000,
                      'resolution_ns': None, 'resolution_status': 'not established by observed increments',
                      'probes': probes},
            'runs': runs, 'pairs': pairs,
            'descriptive_paired_median_reduction': ev.rational(median) if median is not None else None,
            'nonzero_baseline_pairs': len(positive), 'confidence_interval': None,
            'tail_latency_claim': 'unavailable', 'resource_claim': 'unavailable',
            'independence': 'not established; one owned engine session',
            'adoption_eligible': False, 'automatic_adoption': False, 'adoption_blockers': blockers,
            'trust_boundary': TRUST}


def collect(input_path, output_path):
    input_path, output_path = Path(input_path).resolve(), Path(output_path).resolve()
    ev.require(not output_path.exists(), 'journal destination already exists')
    reader = ev.Reader(input_path.parent)
    ev.require(input_path.is_file() and input_path.stat().st_size <= ev.LIMIT, 'missing or excessive input document')
    input_bytes = input_path.read_bytes()
    ev.require(len(input_bytes) <= ev.LIMIT, 'input document exceeds byte budget')
    source_ref = {'path': input_path.name, 'sha256': ev.digest(input_bytes)}
    request = reader.json(source_ref)
    result = validate_request(reader, request)
    reader.unchanged()
    # Capture all validated bytes before any writes; content-addressed objects are
    # immutable. A completion marker is written last; a partial directory is not success.
    captured = {str(path.relative_to(reader.root)).replace('\\', '/'): (expected, path.read_bytes())
                for path, expected in reader.seen.items()}
    ev.require(all(ev.digest(data) == expected for expected, data in captured.values()), 'input changed before capture')
    revisions = {}
    for name, source in (('collect.py', Path(__file__)), ('evaluate.py', Path(ev.__file__))):
        original = '__collector_revision__/' + name
        ev.require(original not in captured, 'reserved collector provenance path')
        data = source.read_bytes()
        revisions[name] = ev.digest(data)
        captured[original] = (revisions[name], data)
    output_path.mkdir(parents=True, exist_ok=False)
    objects = output_path / 'objects'; objects.mkdir()
    retained = []
    for name, (expected, data) in sorted(captured.items()):
        destination = objects / expected
        if not destination.exists():
            with destination.open('xb') as handle:
                handle.write(data)
        retained.append({'original_path': name, 'sha256': expected, 'object_path': 'objects/' + expected})
    result['collected_utc_ns'] = time.time_ns()
    result['collector_sha256'] = revisions['collect.py']
    result['evaluator_sha256'] = revisions['evaluate.py']
    result['request_sha256'] = source_ref['sha256']
    result['retained_files'] = retained
    reader.unchanged()
    with (output_path / 'collection.json').open('xb') as handle:
        handle.write(ev.canonical(result) + b'\n')
    return result


def verify_journal(journal_path):
    """Replay validation from retained objects without trusting the result summary."""
    root = Path(journal_path).resolve()
    path = root / 'collection.json'
    ev.require(path.is_file() and path.stat().st_size <= ev.LIMIT, 'missing or excessive journal completion marker')
    result = ev.parse(path.read_bytes())
    ev.require(type(result) is dict, 'invalid journal result')
    retained = result.get('retained_files')
    ev.require(type(retained) is list and 1 <= len(retained) <= 16384, 'invalid retained object list')
    mapping, underlying = {}, ev.Reader(root)
    for item in retained:
        ev.fields(item, ('original_path', 'sha256', 'object_path'), 'retained object')
        original = item['original_path']
        ev.require(type(original) is str and original and original not in mapping, 'duplicate or invalid retained source path')
        # Validate the original spelling using the same grammar as the file reader.
        ev.require('\\' not in original and ':' not in original and '\0' not in original
                   and not ev.PurePosixPath(original).is_absolute()
                   and '..' not in ev.PurePosixPath(original).parts
                   and str(ev.PurePosixPath(original)) == original, 'unsafe retained source path')
        ev.require(item['object_path'] == 'objects/' + item['sha256'], 'noncanonical retained object path')
        mapping[original] = item
        underlying.bytes({'path': item['object_path'], 'sha256': item['sha256']})

    class ArchiveReader:
        def bytes(self, ref):
            ev.fields(ref, ('path', 'sha256'), 'archived reference')
            item = mapping.get(ref['path']) if type(ref['path']) is str else None
            ev.require(item is not None and item['sha256'] == ref['sha256'], 'missing or stale archived reference')
            return underlying.bytes({'path': item['object_path'], 'sha256': item['sha256']})

        def json(self, ref):
            return ev.parse(self.bytes(ref))

    requests = [item for item in retained if item['sha256'] == result.get('request_sha256')]
    ev.require(requests, 'request object missing from journal')
    request_item = requests[0]
    archived = ArchiveReader()
    request = archived.json({'path': request_item['original_path'], 'sha256': request_item['sha256']})
    expected = validate_request(archived, request)
    extra = ('collected_utc_ns', 'collector_sha256', 'evaluator_sha256', 'request_sha256', 'retained_files')
    ev.fields(result, (*expected.keys(), *extra), 'journal result')
    ev.integer(result['collected_utc_ns'], 'collection time', 1)
    ev.require(result['collector_sha256'] == ev.digest(Path(__file__).read_bytes()),
               'journal collector revision differs; use the retained original collector revision')
    ev.require(result['evaluator_sha256'] == ev.digest(Path(ev.__file__).read_bytes()),
               'journal evaluator dependency differs; use the retained original evaluator revision')
    for name, key in (('collect.py', 'collector_sha256'), ('evaluate.py', 'evaluator_sha256')):
        item = mapping.get('__collector_revision__/' + name)
        ev.require(item is not None and item['sha256'] == result[key], 'collector source revision missing from journal')
    ev.require(ev.canonical(expected) == ev.canonical({key: result[key] for key in expected}),
               'journal summary differs from replayed raw evidence')
    underlying.unchanged()
    return {'schema_version': 1, 'kind': 'beryl.performance.journal_verification',
            'status': 'verified', 'request_sha256': result['request_sha256'],
            'retained_files': len(retained), 'adoption_eligible': False, 'trust_boundary': TRUST}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    plan = sub.add_parser('schedule')
    plan.add_argument('--experiment-id', required=True)
    plan.add_argument('--phase', choices=('exploratory', 'pilot', 'candidate'), default='exploratory')
    plan.add_argument('--role', default='exploratory')
    plan.add_argument('--scope-name', required=True)
    plan.add_argument('--case', action='append', required=True)
    plan.add_argument('--pairs', type=int, default=60)
    plan.add_argument('--operations', type=int, default=1)
    plan.add_argument('--output', required=True)
    capture = sub.add_parser('ingest')
    capture.add_argument('--input', required=True)
    capture.add_argument('--output', required=True)
    verify = sub.add_parser('verify-journal')
    verify.add_argument('--journal', required=True)
    args = parser.parse_args()
    try:
        if args.command == 'schedule':
            result = make_plan(args.experiment_id, args.phase, args.role, args.case, args.pairs,
                               args.operations, args.scope_name)
            with Path(args.output).open('xb') as handle:
                handle.write(ev.canonical(result) + b'\n')
        elif args.command == 'ingest':
            result = collect(args.input, args.output)
        else:
            result = verify_journal(args.journal)
        print(json.dumps(result, sort_keys=True, allow_nan=False))
        return 0
    except (ev.Invalid, OSError, KeyError, TypeError, OverflowError) as error:
        print(json.dumps({'schema_version': 1, 'kind': 'beryl.performance.collection_error',
                          'status': 'failed', 'error': str(error)}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
