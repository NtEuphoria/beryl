#!/usr/bin/env python3
"""Experimental receipt evaluator. Collects no timings and enables no optimizer."""
import argparse
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import re
import sys
import time

COSTS = ('setup', 'capture', 'compute', 'maintenance', 'invalidation', 'conversion', 'cleanup', 'cold_refresh')
RESOURCES = ('peak_bytes', 'retained_bytes', 'allocations', 'text_bytes', 'build_ns', 'edit_check_ns')
IDENTITIES = ('baseline', 'compiler', 'toolchain', 'environment', 'workload', 'semantic_contract')
BUDGETS = ('peak_bytes', 'retained_bytes', 'allocations', 'text_growth_ppm', 'build_ratio_ppm', 'edit_check_growth_ppm')
LIMIT = 16 * 1024 * 1024
TRUST = 'Receipt consistency and exact file hashes checked; collector execution, completeness, independence, IID sampling and chronology remain externally asserted facts.'


class Invalid(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise Invalid(message)


def fields(value, names, label):
    require(type(value) is dict and set(value) == set(names), label + ': missing or unknown fields')


def integer(value, label, minimum=0):
    require(type(value) is int and minimum <= value <= 2**63 - 1, label + ': invalid integer')
    return value


def token(value, label):
    require(type(value) is str and re.fullmatch(r'[A-Za-z0-9_.:-]{1,128}', value), label + ': invalid identifier')
    return value


def digest(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode('utf-8')


def parse(data):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'duplicate JSON key: ' + key)
            result[key] = value
        return result
    def constant(value):
        raise Invalid('nonfinite JSON number: ' + value)
    try:
        return json.loads(data, object_pairs_hook=pairs, parse_constant=constant)
    except (ValueError, RecursionError) as error:
        raise Invalid('invalid JSON: ' + str(error)) from error


class Reader:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.seen = {}
        self.unique_bytes = 0

    def bytes(self, ref):
        fields(ref, ('path', 'sha256'), 'file reference')
        path = ref['path']
        require(type(path) is str and path and '\\' not in path and ':' not in path and '\0' not in path,
                'reference path must be relative POSIX spelling')
        parts = PurePosixPath(path)
        require(not parts.is_absolute() and '..' not in parts.parts and str(parts) == path, 'unsafe reference path')
        actual = (self.root / path).resolve()
        require(actual.is_relative_to(self.root) and actual.is_file(), 'missing or escaped referenced file: ' + path)
        require(type(ref['sha256']) is str and re.fullmatch('[0-9a-f]{64}', ref['sha256']), 'invalid SHA-256')
        require(actual.stat().st_size <= LIMIT, 'referenced file exceeds 16 MiB: ' + path)
        if actual not in self.seen:
            require(len(self.seen) < 16384 and self.unique_bytes + actual.stat().st_size <= 256 * 1024 * 1024,
                    'evidence exceeds file-count or cumulative byte budget')
        content = actual.read_bytes()
        require(len(content) <= LIMIT, 'referenced file grew beyond byte budget')
        require(digest(content) == ref['sha256'], 'stale fingerprint: ' + path)
        require(actual not in self.seen or self.seen[actual] == ref['sha256'], 'conflicting file identity: ' + path)
        if actual not in self.seen:
            self.unique_bytes += len(content)
            require(self.unique_bytes <= 256 * 1024 * 1024, 'evidence exceeds cumulative byte budget')
        self.seen[actual] = ref['sha256']
        return content

    def json(self, ref):
        return parse(self.bytes(ref))

    def unchanged(self):
        for path, expected in self.seen.items():
            require(path.is_file() and path.stat().st_size <= LIMIT and digest(path.read_bytes()) == expected,
                    'input changed during evaluation: ' + str(path))


def rational(value):
    return {'numerator': value.numerator, 'denominator': value.denominator}


def median_interval(values):
    """Exact binomial order-statistic interval; no bootstrap seed or float math."""
    ordered = sorted(values)
    n = len(ordered)
    require(30 <= n <= 1024, 'paired interval requires 30..1024 units')
    denominator, tail, rank = 1 << n, 0, 0
    for k in range(1, n // 2 + 1):
        candidate = tail + math.comb(n, k - 1)
        if 40 * candidate > denominator:  # two-sided tail <= 0.05
            break
        tail, rank = candidate, k
    median = (ordered[(n - 1) // 2] + ordered[n // 2]) / 2
    return median, ordered[rank - 1], ordered[n - rank], Fraction(denominator - 2 * tail, denominator), rank


def identities(reader, pilot):
    fields(pilot['fingerprints'], IDENTITIES, 'fingerprints')
    return {key: digest(reader.bytes(ref)) for key, ref in pilot['fingerprints'].items()}


def policy(pilot):
    return {key: value for key, value in pilot.items() if key != 'blocks'}


def validate_pilot(pilot):
    fields(pilot, ('schema_version', 'kind', 'experiment_id', 'evidence_kind', 'resource_policy', 'metric', 'population', 'fingerprints', 'budgets', 'blocks'), 'pilot')
    require(type(pilot['schema_version']) is int and pilot['schema_version'] == 1 and pilot['kind'] == 'beryl.performance.pilot', 'unsupported pilot schema')
    token(pilot['experiment_id'], 'experiment ID')
    require(pilot['evidence_kind'] in ('synthetic_validation', 'collector_measurements'), 'unknown evidence kind')
    require(pilot['resource_policy'] in ('resource_adequate_exact', 'resource_observable_exact'), 'unknown resource policy')
    require(pilot['metric'] == 'median_paired_total_paid_ns', 'unsupported metric')
    fields(pilot['population'], ('sampling', 'description'), 'population')
    require(pilot['population']['sampling'] == 'independent_identically_distributed', 'unverified sampling model')
    require(type(pilot['population']['description']) is str and 1 <= len(pilot['population']['description']) <= 4096, 'missing population description')
    fields(pilot['budgets'], BUDGETS, 'budgets')
    for key, value in pilot['budgets'].items():
        integer(value, 'budget ' + key)
    require(pilot['budgets']['text_growth_ppm'] <= 200000, 'text budget exceeds approved 20% policy')
    require(pilot['budgets']['build_ratio_ppm'] <= 2000000, 'build budget exceeds approved 2x policy')
    require(pilot['budgets']['edit_check_growth_ppm'] <= 100000, 'edit/check budget exceeds approved 10% policy')


def collect(reader, blocks, fingerprints, second_artifact, start_after, end_before,
            prior_units=(), prior_sessions=(), prior_measurements=()):
    require(type(blocks) is list and 30 <= len(blocks) <= 1024 and len(blocks) % 2 == 0,
            'requires an even 30..1024 independent paired blocks')
    units, sessions, measurements = set(prior_units), set(prior_sessions), set(prior_measurements)
    fresh_units, fresh_sessions, fresh_measurements, values, resources = [], [], [], [], []
    orders = []
    for block in blocks:
        fields(block, ('unit_id', 'first', 'independence', 'a', 'b'), 'block')
        unit = token(block['unit_id'], 'unit ID')
        require(unit not in units, 'duplicate or reused independent unit')
        units.add(unit); fresh_units.append(unit)
        require(block['first'] in ('a', 'b'), 'unknown pair order')
        orders.append(block['first'])
        runs = []
        for position in ('a', 'b'):
            run = reader.json(block[position])
            fields(run, ('schema_version', 'kind', 'measurement_id', 'unit_id', 'session_id', 'status',
                         'started_utc_ns', 'ended_utc_ns', 'fingerprints', 'paid_ns', 'total_paid_ns', 'resources', 'semantic'), 'measurement')
            require(type(run['schema_version']) is int and run['schema_version'] == 1 and run['kind'] == 'beryl.performance.measurement', 'unsupported measurement schema')
            require(run['status'] == 'complete' and run['unit_id'] == unit, 'incomplete measurement or wrong unit')
            mid = token(run['measurement_id'], 'measurement ID')
            require(mid not in measurements, 'duplicate measurement ID')
            measurements.add(mid); fresh_measurements.append(mid)
            token(run['session_id'], 'session ID')
            start = integer(run['started_utc_ns'], 'start', 1)
            end = integer(run['ended_utc_ns'], 'end', 1)
            require(start_after < start < end <= end_before, 'measurement chronology precedes freeze or is incomplete/future')
            expected = {key: value for key, value in fingerprints.items() if key != 'baseline'}
            expected['artifact'] = fingerprints['baseline'] if position == 'a' else second_artifact
            require(run['fingerprints'] == expected, 'measurement fingerprints differ from frozen inputs')
            fields(run['paid_ns'], COSTS, 'paid cost components')
            for key, value in run['paid_ns'].items():
                integer(value, 'paid ' + key)
            total = integer(run['total_paid_ns'], 'total paid', 1)
            require(total == sum(run['paid_ns'].values()) and total <= end - start, 'paid costs are incomplete, overlap, or exceed recorded interval')
            fields(run['resources'], RESOURCES, 'resource metrics')
            for key, value in run['resources'].items():
                integer(value, 'resource ' + key)
            require(run['resources']['retained_bytes'] <= run['resources']['peak_bytes'], 'retained bytes exceed peak')
            semantic = run['semantic']
            fields(semantic, ('status', 'expected_cases', 'completed_cases', 'events', 'stdout', 'state'), 'semantic receipt')
            expected_cases = integer(semantic['expected_cases'], 'expected cases', 1)
            integer(semantic['completed_cases'], 'completed cases', 1)
            require(semantic['status'] == 'complete' and semantic['completed_cases'] == expected_cases, 'incomplete semantic receipt')
            for key in ('events', 'stdout', 'state'):
                reader.bytes(semantic[key])
            runs.append(run)
        first, second = runs if block['first'] == 'a' else runs[::-1]
        require(first['ended_utc_ns'] <= second['started_utc_ns'], 'pair order disagrees with measured chronology')
        independence = reader.json(block['independence'])
        fields(independence, ('schema_version', 'kind', 'status', 'unit_id', 'method', 'measurement_ids', 'evidence'), 'independence receipt')
        require(type(independence['schema_version']) is int and independence['schema_version'] == 1
                and independence['kind'] == 'beryl.performance.independence' and independence['status'] == 'verified', 'unverified independence')
        require(independence['unit_id'] == unit and independence['measurement_ids'] == [run['measurement_id'] for run in runs], 'independence receipt identifies different runs')
        require(independence['method'] in ('separate_owned_sessions', 'verified_reset_equivalence'), 'unsupported independent unit')
        require(reader.bytes(independence['evidence']), 'empty independence evidence')
        if independence['method'] == 'separate_owned_sessions':
            for run in runs:
                session = run['session_id']
                require(session not in sessions, 'session reused without verified reset equivalence')
                sessions.add(session); fresh_sessions.append(session)
        else:
            # The receipt must cover reset equivalence for BOTH named runs. Its
            # physical correctness is a collector/reviewer obligation, not inferred.
            for run in runs:
                sessions.add(run['session_id']); fresh_sessions.append(run['session_id'])
        a, b = runs
        require(a['semantic']['expected_cases'] == b['semantic']['expected_cases'], 'semantic selections differ')
        for key in ('events', 'stdout', 'state'):
            require(a['semantic'][key]['sha256'] == b['semantic'][key]['sha256'], 'semantic mismatch: ' + key)
        values.append(Fraction(a['total_paid_ns'] - b['total_paid_ns'], a['total_paid_ns']))
        resources.append((a['resources'], b['resources']))
    require(orders.count('a') == orders.count('b'), 'unbalanced pair order')
    return values, resources, fresh_units, sorted(set(fresh_sessions)), fresh_measurements


def freeze(reader, pilot_ref, now):
    pilot = reader.json(pilot_ref)
    validate_pilot(pilot)
    fingerprints = identities(reader, pilot)
    values, _, units, sessions, measurements = collect(reader, pilot['blocks'], fingerprints, fingerprints['baseline'], 0, now)
    noise = sorted(abs(value) for value in values)[math.ceil(95 * len(values) / 100) - 1]
    threshold = max(Fraction(1, 20), noise)
    return {'schema_version': 1, 'kind': 'beryl.performance.freeze', 'pilot': pilot_ref,
            'frozen_utc_ns': now, 'policy_sha256': digest(canonical(policy(pilot))),
            'threshold': rational(threshold), 'pilot_p95_absolute_variation': rational(noise),
            'unit_ids': units, 'session_ids': sessions, 'measurement_ids': measurements,
            'evaluator_sha256': digest(Path(__file__).read_bytes())}


def evaluate(reader, request_ref, now):
    request = reader.json(request_ref)
    fields(request, ('schema_version', 'kind', 'freeze', 'candidate', 'selection', 'role', 'blocks'), 'evaluation')
    require(type(request['schema_version']) is int and request['schema_version'] == 1 and request['kind'] == 'beryl.performance.evaluation', 'unsupported evaluation schema')
    require(request['role'] in ('training', 'selection', 'held_out'), 'unknown dataset role')
    sealed = reader.json(request['freeze'])
    fields(sealed, ('schema_version', 'kind', 'pilot', 'frozen_utc_ns', 'policy_sha256', 'threshold',
                   'pilot_p95_absolute_variation', 'unit_ids', 'session_ids', 'measurement_ids', 'evaluator_sha256'), 'freeze receipt')
    require(type(sealed['schema_version']) is int and sealed['schema_version'] == 1, 'unsupported freeze version')
    frozen_time = integer(sealed.get('frozen_utc_ns'), 'freeze timestamp', 1)
    require(frozen_time < now, 'freeze is not earlier than evaluation')
    expected = freeze(reader, sealed.get('pilot'), frozen_time)
    require(canonical(sealed) == canonical(expected), 'stale, changed or unsupported freeze receipt')
    pilot = reader.json(sealed['pilot'])
    fingerprints = identities(reader, pilot)
    candidate = digest(reader.bytes(request['candidate']))
    selection = reader.json(request['selection'])
    fields(selection, ('schema_version', 'kind', 'status', 'candidate_sha256', 'selected_utc_ns', 'prior_workload_sha256', 'evidence'), 'selection receipt')
    require(type(selection['schema_version']) is int and selection['schema_version'] == 1 and selection['kind'] == 'beryl.performance.selection'
            and selection['status'] == 'frozen' and selection['candidate_sha256'] == candidate, 'unfrozen or stale candidate selection')
    selected = integer(selection['selected_utc_ns'], 'candidate selection timestamp', 1)
    require(frozen_time <= selected < now, 'candidate selection predates frozen policy or is future')
    prior = selection['prior_workload_sha256']
    require(type(prior) is list and all(type(value) is str and re.fullmatch('[0-9a-f]{64}', value) for value in prior)
            and len(set(prior)) == len(prior), 'invalid previous workload identities')
    require(reader.bytes(selection['evidence']), 'missing candidate selection evidence')
    if request['role'] == 'held_out':
        require(fingerprints['workload'] not in prior, 'held-out workload was used during tuning')
    values, resources, _, _, _ = collect(reader, request['blocks'], fingerprints, candidate, selected, now,
                                        sealed['unit_ids'], sealed['session_ids'], sealed['measurement_ids'])
    median, low, high, coverage, rank = median_interval(values)
    threshold = Fraction(sealed['threshold']['numerator'], sealed['threshold']['denominator'])
    violations = []
    budgets = pilot['budgets']
    for index, (base, candidate_resources) in enumerate(resources):
        for metric in ('peak_bytes', 'retained_bytes', 'allocations'):
            if pilot['resource_policy'] == 'resource_observable_exact' and candidate_resources[metric] != base[metric]:
                violations.append({'block': index, 'metric': metric, 'reason': 'observable resource metric changed'})
            if candidate_resources[metric] > budgets[metric]:
                violations.append({'block': index, 'metric': metric})
        for metric, limit in (('text_bytes', 1000000 + budgets['text_growth_ppm']),
                              ('build_ns', budgets['build_ratio_ppm']),
                              ('edit_check_ns', 1000000 + budgets['edit_check_growth_ppm'])):
            if candidate_resources[metric] * 1000000 > base[metric] * limit:
                violations.append({'block': index, 'metric': metric})
    decision = 'resource_budget_failed' if violations else 'threshold_not_supported' if low < threshold else 'eligible_held_out' if request['role'] == 'held_out' else 'selection_only'
    if decision == 'eligible_held_out' and pilot['evidence_kind'] == 'synthetic_validation':
        decision = 'synthetic_gate_pass'
    return {'schema_version': 1, 'kind': 'beryl.performance.result', 'status': 'evaluated',
            'decision': decision, 'evidence_kind': pilot['evidence_kind'], 'role': request['role'], 'independent_units': len(values),
            'metric': pilot['metric'], 'resource_policy': pilot['resource_policy'], 'threshold': rational(threshold), 'median': rational(median),
            'confidence_interval': {'method': 'exact_binomial_order_statistics', 'minimum_coverage': rational(coverage),
                                    'lower': rational(low), 'upper': rational(high), 'lower_rank_one_based': rank},
            'paired_improvements': list(map(rational, values)), 'resource_violations': violations,
            'candidate_sha256': candidate, 'policy_sha256': sealed['policy_sha256'],
            'evaluator_sha256': digest(Path(__file__).read_bytes()), 'trust_boundary': TRUST,
            'measurement_execution': 'not_run_by_evaluator', 'automatic_adoption': False,
            'tail_latency_claim': 'unavailable; no tail-latency estimator implemented'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=('freeze', 'evaluate'))
    parser.add_argument('--input', required=True, type=Path)
    parser.add_argument('--output', type=Path, help='new file only; existing files are never replaced')
    args = parser.parse_args()
    status = 0
    try:
        path = args.input.resolve(strict=True)
        reader = Reader(path.parent)
        require(path.stat().st_size <= LIMIT, 'input exceeds 16 MiB')
        ref = {'path': path.name, 'sha256': digest(path.read_bytes())}
        result = (freeze if args.operation == 'freeze' else evaluate)(reader, ref, time.time_ns())
        reader.unchanged()
        encoded = canonical(result) + b'\n'
        if args.output:
            with args.output.open('xb') as output:
                output.write(encoded)
    except (Invalid, OSError, OverflowError, RecursionError) as error:
        result = {'schema_version': 1, 'kind': 'beryl.performance.error', 'status': 'invalid_evidence',
                  'error': str(error), 'measurement_execution': 'not_run_by_evaluator', 'automatic_adoption': False}
        status = 2
    sys.stdout.buffer.write(canonical(result) + b'\n')
    return status


if __name__ == '__main__':
    raise SystemExit(main())
