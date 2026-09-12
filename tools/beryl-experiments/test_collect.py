#!/usr/bin/env python3
"""Analytical collector validation. These fixtures are not engine measurements."""
import copy
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import collect as co
import evaluate as ev

ROOT = Path(__file__).resolve().parents[2]
WORK = Path(tempfile.mkdtemp(prefix='performance-collector-synthetic-', dir=ROOT / 'build'))


class Bundle:
    def __init__(self, name):
        self.root = WORK / name
        self.root.mkdir()
        proof = self.ref('producer.raw', b'SYNTHETIC producer/reviewer evidence, not actual engine execution.\n')
        self.proof = proof
        self.plan = co.make_plan(name, 'exploratory', 'exploratory', ['flat', 'slope', 'water'], 30, 2,
                                 'terrain_construct_release', 1)
        identities = {name: self.ref(name + '.identity', ('SYNTHETIC ' + name).encode()) for name in co.FINGERPRINTS}
        identities['engine'] = self.ref('engine.json', {'schema_version': 1, 'kind': 'beryl.performance.engine_identity',
              'binary_sha256': 'a' * 64, 'version': 'synthetic-1', 'evidence': proof})
        scope = {'schema_version': 1, 'kind': 'beryl.performance.scope', 'status': 'reviewed',
                 'scope_name': self.plan['scope_name'], 'description': 'Synthetic cached construction+release interval.',
                 'paid_components': ['compute', 'cleanup'],
                 'excluded_components': [key for key in ev.COSTS if key not in ('compute', 'cleanup')],
                 'resource_status': {key: {'status': 'unavailable', 'reason': 'No admitted instrumentation.'} for key in ev.RESOURCES},
                 'timer_evidence': proof, 'review_evidence': proof}
        rows, tick = ['timer|0|0|1', 'timer|1|1|2'], 3
        for run in self.plan['runs']:
            cost = 10 if run['side'] == 'a' else 8
            rows.append('run|{unit_id}|{side}|{ordinal}|{case_id}|'.format(**run) + f'{tick}|{tick + cost}|2|100|101|1024|1020')
            tick += cost + 1
        self.target = {'schema_version': 1, 'kind': 'beryl.performance.target', 'token': 'synthetic-token',
                       'scope_name': self.plan['scope_name'], 'timer_api': co.TIMER, 'tick_unit': 'ms',
                       'executed': 1, 'failures': 0, 'expected_runs': 60, 'rows': rows}
        self.runtime = {'schema_version': 1, 'status': 'success', 'rpc': {'Ok': True, 'Response': self.target},
                        'session': {'process_id': 1, 'start_time': 'synthetic-start', 'project': 'synthetic-project', 'reused': False},
                        'engine_sha256': 'a' * 64, 'engine_version': 'synthetic-1'}
        owner = {'schema_version': 1, 'kind': 'beryl.performance.ownership', 'status': 'verified',
                 **{key: self.runtime['session'][key] for key in ('process_id', 'start_time', 'project')}, 'evidence': proof}
        semantic = {'schema_version': 1, 'kind': 'beryl.performance.semantic', 'status': 'complete',
                    'fingerprints': {key: identities[key]['sha256'] for key in ('artifact', 'workload', 'semantic_contract', 'engine')},
                    'case_ids': self.plan['case_ids'], 'expected_cases': 3, 'completed_cases': 3,
                    'failures': 0, 'comparison': 'engine_operator_complete_payload', 'evidence': proof}
        self.request = {'schema_version': 1, 'kind': 'beryl.performance.collection', 'evidence_kind': 'synthetic_validation',
                        'token': 'synthetic-token', 'schedule': self.ref('schedule.json', self.plan),
                        'runtime': self.ref('runtime.json', self.runtime), 'semantic': self.ref('semantic.json', semantic),
                        'scope': self.ref('scope.json', scope), 'ownership': self.ref('ownership.json', owner),
                        'fingerprints': identities, 'raw_evidence': [proof]}

    def ref(self, name, value):
        data = value if isinstance(value, bytes) else ev.canonical(value)
        (self.root / name).write_bytes(data)
        return {'path': name, 'sha256': ev.digest(data)}

    def change(self, field, mutation):
        ref = self.request[field]
        value = ev.parse((self.root / ref['path']).read_bytes())
        mutation(value)
        ref.update(self.ref(ref['path'], value))

    def target_change(self, mutation):
        self.change('runtime', lambda runtime: mutation(runtime['rpc']['Response']))

    def validate(self):
        reader = ev.Reader(self.root)
        result = co.validate_request(reader, self.request)
        reader.unchanged()
        return result

    def publish(self, name='journal'):
        self.ref('request.json', self.request)
        return co.collect(self.root / 'request.json', self.root / name)


class CollectionTests(unittest.TestCase):
    def fixture(self):
        return Bundle(self._testMethodName)

    def test_analytical_reduction_never_adoption(self):
        result = self.fixture().validate()
        self.assertEqual(result['descriptive_paired_median_reduction'], {'numerator': 1, 'denominator': 5})
        self.assertEqual(result['nonzero_baseline_pairs'], 30)
        self.assertFalse(result['adoption_eligible'])
        self.assertIsNone(result['confidence_interval'])
        self.assertIsNone(result['timer']['resolution_ns'])
        self.assertEqual(result['runs'][0]['elapsed_ns'], 10000000)
        self.assertEqual(result['runs'][0]['raw_whole_engine_counters']['allocation_kb_after'], 1020)

    def test_balances_every_case_not_only_global_order(self):
        plan = self.fixture().plan
        for case in plan['case_ids']:
            firsts = [plan['runs'][i]['side'] for i in range(0, 60, 2) if plan['runs'][i]['case_id'] == case]
            self.assertEqual(firsts.count('a'), firsts.count('b'))
        with self.assertRaisesRegex(ev.Invalid, 'balanced separately'):
            co.make_plan('six-cases', 'exploratory', 'exploratory', list('abcdef'), 30, 1, 'scope')

    def test_zero_intervals_retained_as_unresolved(self):
        bundle = self.fixture()
        def zero(target):
            parts = target['rows'][2].split('|'); parts[6] = parts[5]; target['rows'][2] = '|'.join(parts)
        bundle.target_change(zero)
        result = bundle.validate()
        self.assertEqual(result['nonzero_baseline_pairs'], 29)
        self.assertIsNone(result['pairs'][0]['relative_reduction'])
        self.assertTrue(any('granularity' in reason for reason in result['adoption_blockers']))

    def test_unavailable_counters_are_not_zero(self):
        bundle = self.fixture()
        bundle.target_change(lambda t: t['rows'].__setitem__(2, '|'.join(t['rows'][2].split('|')[:8] + ['unavailable'] * 4)))
        self.assertTrue(all(value is None for value in bundle.validate()['runs'][0]['raw_whole_engine_counters'].values()))

    def test_wrong_token_engine_and_scope(self):
        bundle = self.fixture()
        for change, message in ((lambda t: t.update(token='wrong'), 'token/scope'),
                                (lambda t: t.update(scope_name='wrong'), 'token/scope')):
            original = copy.deepcopy(bundle.request['runtime'])
            data = (bundle.root / original['path']).read_bytes()
            bundle.target_change(change)
            with self.assertRaisesRegex(ev.Invalid, message): bundle.validate()
            bundle.request['runtime'] = bundle.ref(original['path'], data)
        bundle.change('runtime', lambda r: r.update(engine_sha256='b' * 64))
        with self.assertRaisesRegex(ev.Invalid, 'engine fingerprint'): bundle.validate()

    def test_unknown_boolean_float_and_duplicate_fields(self):
        bundle = self.fixture()
        bundle.request['schema_version'] = True
        with self.assertRaisesRegex(ev.Invalid, 'schema'): bundle.validate()
        bundle.request['schema_version'] = 1.0
        with self.assertRaisesRegex(ev.Invalid, 'schema'): bundle.validate()
        bundle.request['schema_version'] = 1; bundle.request['surprise'] = 1
        with self.assertRaisesRegex(ev.Invalid, 'unknown fields'): bundle.validate()
        with self.assertRaisesRegex(ev.Invalid, 'duplicate JSON'): ev.parse(b'{"kind":1,"kind":2}')

    def test_incomplete_failed_or_extra_target(self):
        bundle = self.fixture()
        original = (bundle.root / 'runtime.json').read_bytes()
        for change, message in ((lambda t: t.update(executed=0), 'incomplete target'),
                                (lambda t: t.update(failures=1), 'incomplete target'),
                                (lambda t: t['rows'].pop(), 'incomplete timer/run'),
                                (lambda t: t['rows'].append(t['rows'][-1]), 'extra target')):
            bundle.request['runtime'] = bundle.ref('runtime.json', original)
            bundle.target_change(change)
            with self.assertRaisesRegex(ev.Invalid, message): bundle.validate()

    def test_wrong_order_operation_count_and_duplicate_run(self):
        bundle = self.fixture()
        original = (bundle.root / 'runtime.json').read_bytes()
        for column, value in ((1, 'another-unit'), (2, 'b'), (3, '1'), (4, 'wrong-case'), (7, '1')):
            bundle.request['runtime'] = bundle.ref('runtime.json', original)
            def corrupt(t):
                row = t['rows'][2].split('|'); row[column] = value; t['rows'][2] = '|'.join(row)
            bundle.target_change(corrupt)
            with self.assertRaisesRegex(ev.Invalid, 'identity/order/count'): bundle.validate()

    def test_backwards_overlapping_or_wrapped_ticks(self):
        bundle = self.fixture()
        original = (bundle.root / 'runtime.json').read_bytes()
        for column, value, message in ((5, '0', 'backwards'), (6, '2', 'backwards'),
                                       (6, '-1', 'invalid raw integer'), (6, '2147483648', 'exceeds admitted')):
            bundle.request['runtime'] = bundle.ref('runtime.json', original)
            def corrupt(t):
                row = t['rows'][2].split('|'); row[column] = value; t['rows'][2] = '|'.join(row)
            bundle.target_change(corrupt)
            with self.assertRaisesRegex(ev.Invalid, message): bundle.validate()

    def test_timer_must_advance_and_precede_runs(self):
        bundle = self.fixture()
        bundle.target_change(lambda t: t['rows'].__setitem__(slice(0, 2), ['timer|0|0|0', 'timer|1|0|0']))
        with self.assertRaisesRegex(ev.Invalid, 'advancement'): bundle.validate()

    def test_unverified_wrong_or_reused_session(self):
        bundle = self.fixture()
        bundle.change('ownership', lambda owner: owner.update(status='unverified'))
        with self.assertRaisesRegex(ev.Invalid, 'unverified session'): bundle.validate()
        bundle.change('ownership', lambda owner: owner.update(status='verified', process_id=2))
        with self.assertRaisesRegex(ev.Invalid, 'ownership mismatch'): bundle.validate()
        bundle.change('ownership', lambda owner: owner.update(process_id=1))
        bundle.change('runtime', lambda r: r['session'].update(reused=True))
        with self.assertRaisesRegex(ev.Invalid, 'reused session'): bundle.validate()

    def test_missing_or_double_counted_paid_scope(self):
        bundle = self.fixture()
        bundle.change('scope', lambda scope: scope['excluded_components'].pop())
        with self.assertRaisesRegex(ev.Invalid, 'costs must'): bundle.validate()

    def test_unknown_allocation_is_not_admitted_metric(self):
        bundle = self.fixture()
        bundle.change('scope', lambda scope: scope['resource_status']['allocations'].update(status='measured'))
        with self.assertRaisesRegex(ev.Invalid, 'instrumentation is not admitted'): bundle.validate()

    def test_semantic_failure_missing_case_or_stale_identity(self):
        bundle = self.fixture()
        original = (bundle.root / 'semantic.json').read_bytes()
        for change, message in ((lambda s: s.update(failures=1), 'semantic mismatch'),
                                (lambda s: s.update(completed_cases=2), 'semantic mismatch'),
                                (lambda s: s.update(case_ids=['flat']), 'case selection'),
                                (lambda s: s['fingerprints'].update(artifact='a' * 64), 'stale semantic')):
            bundle.request['semantic'] = bundle.ref('semantic.json', original)
            bundle.change('semantic', change)
            with self.assertRaisesRegex(ev.Invalid, message): bundle.validate()

    def test_stale_input_and_path_escape_no_completed_journal(self):
        bundle = self.fixture()
        (bundle.root / bundle.proof['path']).write_bytes(b'changed')
        with self.assertRaisesRegex(ev.Invalid, 'stale fingerprint'): bundle.publish()
        self.assertFalse((bundle.root / 'journal').exists())
        bundle.request['raw_evidence'] = [{'path': '../outside', 'sha256': 'a' * 64}]
        with self.assertRaises(ev.Invalid): bundle.validate()

    def test_immutable_journal_retains_all_validated_raw_files(self):
        bundle = self.fixture()
        result = bundle.publish()
        journal = bundle.root / 'journal'
        self.assertTrue((journal / 'collection.json').is_file())
        for item in result['retained_files']:
            data = (journal / item['object_path']).read_bytes()
            self.assertEqual(ev.digest(data), item['sha256'])
        retained_paths = {item['original_path'] for item in result['retained_files']}
        self.assertTrue({'request.json', 'runtime.json', 'schedule.json', 'semantic.json', 'producer.raw'} <= retained_paths)
        self.assertEqual(co.verify_journal(journal)['status'], 'verified')
        with self.assertRaisesRegex(ev.Invalid, 'already exists'): bundle.publish()

    def test_journal_replay_rejects_altered_summary_or_raw_objects(self):
        bundle = self.fixture()
        result = bundle.publish()
        marker = bundle.root / 'journal' / 'collection.json'
        changed = copy.deepcopy(result); changed['adoption_eligible'] = True
        marker.write_bytes(ev.canonical(changed))
        with self.assertRaisesRegex(ev.Invalid, 'summary differs'): co.verify_journal(marker.parent)
        marker.write_bytes(ev.canonical(result))
        obj = marker.parent / result['retained_files'][0]['object_path']
        obj.write_bytes(obj.read_bytes() + b'changed')
        with self.assertRaisesRegex(ev.Invalid, 'stale fingerprint'): co.verify_journal(marker.parent)

    def test_cli_collects_and_rejects_publication_overwrite(self):
        bundle = self.fixture()
        bundle.ref('request.json', bundle.request)
        argv = [sys.executable, str(Path(co.__file__)), 'ingest', '--input', str(bundle.root / 'request.json'),
                '--output', str(bundle.root / 'cli-journal')]
        first = subprocess.run(argv, capture_output=True, text=True)
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        self.assertFalse(ev.parse(first.stdout)['adoption_eligible'])
        second = subprocess.run(argv, capture_output=True, text=True)
        self.assertEqual(second.returncode, 2)
        self.assertEqual(ev.parse(second.stdout)['status'], 'failed')


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(CollectionTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    summary = {'schema_version': 1, 'kind': 'beryl.performance.collector_tests',
               'evidence_kind': 'synthetic_validation', 'passed': result.wasSuccessful(),
               'tests': result.testsRun, 'failures': len(result.failures), 'errors': len(result.errors),
               'measurements_collected': False, 'work': str(WORK)}
    (WORK / 'results.json').write_bytes(ev.canonical(summary) + b'\n')
    print(ev.canonical(summary).decode())
    sys.exit(0 if result.wasSuccessful() else 1)
