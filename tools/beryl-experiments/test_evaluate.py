#!/usr/bin/env python3
"""Analytical synthetic tests. No timings are collected or speedups claimed."""
import copy
from fractions import Fraction
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import evaluate as ev

ROOT = Path(__file__).resolve().parents[2]
WORK = Path(tempfile.mkdtemp(prefix='performance-evidence-synthetic-', dir=ROOT / 'build'))
FREEZE_TIME = 10**18
EVALUATION_TIME = FREEZE_TIME + 10**12


class Bundle:
    def __init__(self, name, candidate_cost=800000, pilot_cost=1000000):
        self.root = WORK / name
        self.root.mkdir()
        self.empty = self.ref('empty.raw', b'')
        self.state = self.ref('state.raw', b'synthetic complete final state\n')
        self.proof = self.ref('external-receipt.txt', b'SYNTHETIC TEST ONLY: external receipt assertion, not a measured fact.\n')
        self.identities = {key: self.ref(key + '.identity', ('SYNTHETIC ' + key).encode()) for key in ev.IDENTITIES}
        self.hashes = {key: ref['sha256'] for key, ref in self.identities.items()}
        self.candidate = self.ref('candidate.identity', b'SYNTHETIC candidate')
        self.pilot = {'schema_version': 1, 'kind': 'beryl.performance.pilot', 'experiment_id': name,
                      'evidence_kind': 'synthetic_validation', 'resource_policy': 'resource_adequate_exact', 'metric': 'median_paired_total_paid_ns',
                      'population': {'sampling': 'independent_identically_distributed', 'description': 'Analytical fixture, no real population sampled.'},
                      'fingerprints': self.identities,
                      'budgets': {'peak_bytes': 4096, 'retained_bytes': 1024, 'allocations': 100,
                                  'text_growth_ppm': 200000, 'build_ratio_ppm': 2000000, 'edit_check_growth_ppm': 100000},
                      'blocks': self.blocks('pilot', FREEZE_TIME - 10**11, pilot_cost, self.hashes['baseline'])}
        self.seal()
        selection = self.ref('selection.json', {'schema_version': 1, 'kind': 'beryl.performance.selection', 'status': 'frozen',
                             'candidate_sha256': self.candidate['sha256'], 'selected_utc_ns': FREEZE_TIME + 1,
                             'prior_workload_sha256': [], 'evidence': self.proof})
        self.request = {'schema_version': 1, 'kind': 'beryl.performance.evaluation', 'freeze': self.freeze_ref,
                        'candidate': self.candidate, 'selection': selection, 'role': 'held_out',
                        'blocks': self.blocks('candidate', FREEZE_TIME + 10**10, candidate_cost, self.candidate['sha256'])}

    def ref(self, name, value):
        data = value if isinstance(value, bytes) else ev.canonical(value)
        (self.root / name).write_bytes(data)
        return {'path': name, 'sha256': ev.digest(data)}

    def mutate(self, ref, action):
        data = ev.parse((self.root / ref['path']).read_bytes())
        action(data)
        updated = self.ref(ref['path'], data)
        ref.update(updated)

    def seal(self):
        self.pilot_ref = self.ref('pilot.json', self.pilot)
        seal = ev.freeze(ev.Reader(self.root), self.pilot_ref, FREEZE_TIME)
        self.freeze_ref = self.ref('freeze.json', seal)

    def blocks(self, prefix, beginning, b_cost, b_hash):
        output = []
        for index in range(30):
            unit = f'{prefix}:{index}'
            order = 'a' if index % 2 == 0 else 'b'
            block = {'unit_id': unit, 'first': order}
            for side, cost, artifact in (('a', 1000000, self.hashes['baseline']), ('b', b_cost, b_hash)):
                start = beginning + index * 10**8 + (0 if side == order else 10**7)
                metrics = {key: 0 for key in ev.COSTS}; metrics['compute'] = cost
                run = {'schema_version': 1, 'kind': 'beryl.performance.measurement', 'measurement_id': unit + ':' + side,
                       'unit_id': unit, 'session_id': unit + ':session:' + side, 'status': 'complete',
                       'started_utc_ns': start, 'ended_utc_ns': start + 5000000,
                       'fingerprints': {**{key: value for key, value in self.hashes.items() if key != 'baseline'}, 'artifact': artifact},
                       'paid_ns': metrics, 'total_paid_ns': cost,
                       'resources': {'peak_bytes': 2048, 'retained_bytes': 512, 'allocations': 20,
                                     'text_bytes': 1000, 'build_ns': 1000000, 'edit_check_ns': 10000},
                       'semantic': {'status': 'complete', 'expected_cases': 1, 'completed_cases': 1,
                                    'events': self.empty, 'stdout': self.empty, 'state': self.state}}
                block[side] = self.ref(f'{prefix}-{index}-{side}.json', run)
            block['independence'] = self.ref(f'{prefix}-{index}-independence.json',
                {'schema_version': 1, 'kind': 'beryl.performance.independence', 'status': 'verified', 'unit_id': unit,
                 'method': 'separate_owned_sessions', 'measurement_ids': [unit + ':a', unit + ':b'], 'evidence': self.proof})
            output.append(block)
        return output

    def evaluate(self):
        request = self.ref('request.json', self.request)
        reader = ev.Reader(self.root)
        result = ev.evaluate(reader, request, EVALUATION_TIME)
        reader.unchanged()
        return result


class EvidenceTests(unittest.TestCase):
    def bundle(self, **kwargs):
        return Bundle(self._testMethodName, **kwargs)

    def invalid(self, bundle, fragment):
        with self.assertRaisesRegex(ev.Invalid, fragment):
            bundle.evaluate()

    def test_analytical_margin_and_determinism(self):
        bundle = self.bundle()
        result = bundle.evaluate()
        self.assertEqual(result, bundle.evaluate())
        self.assertEqual(result['decision'], 'synthetic_gate_pass')
        self.assertEqual(result['median'], ev.rational(Fraction(1, 5)))
        self.assertEqual(result['confidence_interval']['lower_rank_one_based'], 10)
        self.assertGreaterEqual(Fraction(**result['confidence_interval']['minimum_coverage']), Fraction(95, 100))
        self.assertFalse(result['automatic_adoption'])
        self.assertEqual(result['measurement_execution'], 'not_run_by_evaluator')

    def test_exact_practical_boundary(self):
        bundle = self.bundle(candidate_cost=950000)
        self.assertEqual(bundle.evaluate()['decision'], 'synthetic_gate_pass')
        bundle.mutate(bundle.request['blocks'][0]['b'], lambda r: r.update(total_paid_ns=950001, paid_ns={**r['paid_ns'], 'compute': 950001}))
        # One below-threshold pair does not change the lower 95% median bound.
        self.assertEqual(bundle.evaluate()['decision'], 'synthetic_gate_pass')
        for block in bundle.request['blocks'][1:10]:
            bundle.mutate(block['b'], lambda r: r.update(total_paid_ns=950001, paid_ns={**r['paid_ns'], 'compute': 950001}))
        self.assertEqual(bundle.evaluate()['decision'], 'threshold_not_supported')

    def test_noise_threshold(self):
        bundle = self.bundle(candidate_cost=950000, pilot_cost=1060000)
        result = bundle.evaluate()
        self.assertEqual(result['threshold'], ev.rational(Fraction(3, 50)))
        self.assertEqual(result['decision'], 'threshold_not_supported')

    def test_positive_median_insufficient_interval(self):
        bundle = self.bundle()
        for block in bundle.request['blocks'][:15]:
            bundle.mutate(block['b'], lambda r: r.update(total_paid_ns=1000000, paid_ns={**r['paid_ns'], 'compute': 1000000}))
        result = bundle.evaluate()
        self.assertEqual(result['median'], ev.rational(Fraction(1, 10)))
        self.assertEqual(result['decision'], 'threshold_not_supported')

    def test_full_paid_cost_not_compute_alone(self):
        bundle = self.bundle()
        for block in bundle.request['blocks']:
            bundle.mutate(block['b'], lambda r: r.update(total_paid_ns=1000000, paid_ns={**r['paid_ns'], 'capture': 200000}))
        self.assertEqual(bundle.evaluate()['decision'], 'threshold_not_supported')

    def test_role_and_held_out_contamination(self):
        bundle = self.bundle()
        for role in ('training', 'selection'):
            bundle.request['role'] = role
            self.assertEqual(bundle.evaluate()['decision'], 'selection_only')
        bundle.request['role'] = 'held_out'
        bundle.mutate(bundle.request['selection'], lambda s: s.update(prior_workload_sha256=[bundle.hashes['workload']]))
        self.invalid(bundle, 'held-out workload')

    def test_resource_budget_boundary_and_excess(self):
        bundle = self.bundle()
        ref = bundle.request['blocks'][0]['b']
        bundle.mutate(ref, lambda r: r['resources'].update(peak_bytes=4096, retained_bytes=1024, allocations=100,
                                                         text_bytes=1200, build_ns=2000000, edit_check_ns=11000))
        self.assertEqual(bundle.evaluate()['decision'], 'synthetic_gate_pass')
        bundle.mutate(ref, lambda r: r['resources'].update(text_bytes=1201))
        self.assertEqual(bundle.evaluate()['decision'], 'resource_budget_failed')

    def test_missing_unknown_and_incomplete_metrics(self):
        bundle = self.bundle()
        ref = bundle.request['blocks'][0]['a']; original = ev.parse((bundle.root / ref['path']).read_bytes())
        for action, message in ((lambda r: r['paid_ns'].pop('cleanup'), 'paid cost'),
                                (lambda r: r['paid_ns'].update(unknown=0), 'paid cost'),
                                (lambda r: r.update(total_paid_ns=0), 'invalid integer'),
                                (lambda r: r['resources'].update(peak_bytes=True), 'invalid integer'),
                                (lambda r: r.update(status='timeout'), 'incomplete measurement')):
            ref.update(bundle.ref(ref['path'], copy.deepcopy(original)))
            bundle.mutate(ref, action); self.invalid(bundle, message)

    def test_semantic_mismatch_and_incomplete_receipts(self):
        bundle = self.bundle()
        ref = bundle.request['blocks'][0]['b']; original = ev.parse((bundle.root / ref['path']).read_bytes())
        changed = bundle.ref('different-state.raw', b'different state')
        bundle.mutate(ref, lambda r: r['semantic'].update(state=changed)); self.invalid(bundle, 'semantic mismatch')
        ref.update(bundle.ref(ref['path'], original))
        bundle.mutate(ref, lambda r: r['semantic'].update(completed_cases=0)); self.invalid(bundle, 'invalid integer')

    def test_independence_duplicates_order_and_small_sample(self):
        bundle = self.bundle()
        saved = copy.deepcopy(bundle.request['blocks'])
        bundle.request['blocks'] = saved[:28]; self.invalid(bundle, '30..1024')
        bundle.request['blocks'] = copy.deepcopy(saved)
        bundle.request['blocks'][1] = bundle.request['blocks'][0]; self.invalid(bundle, 'duplicate or reused independent unit')
        bundle.request['blocks'] = copy.deepcopy(saved)
        bundle.request['blocks'][0]['first'] = 'b'; self.invalid(bundle, 'pair order')
        bundle.request['blocks'] = copy.deepcopy(saved)
        ref = bundle.request['blocks'][0]['independence']
        bundle.mutate(ref, lambda r: r.update(status='unverified')); self.invalid(bundle, 'unverified independence')

    def test_reused_session_and_measurement_rejected(self):
        bundle = self.bundle()
        a = bundle.request['blocks'][0]['a']; b = bundle.request['blocks'][1]['a']
        previous = ev.parse((bundle.root / a['path']).read_bytes())
        bundle.mutate(b, lambda r: r.update(session_id=previous['session_id']))
        self.invalid(bundle, 'session reused')

    def test_stale_input_and_freeze_receipt(self):
        bundle = self.bundle()
        bundle.mutate(bundle.request['freeze'], lambda s: s.update(threshold=ev.rational(Fraction(1, 100))))
        self.invalid(bundle, 'freeze receipt')
        bundle.request['freeze'] = bundle.freeze_ref = bundle.ref('freeze.json', ev.freeze(ev.Reader(bundle.root), bundle.pilot_ref, FREEZE_TIME))
        (bundle.root / bundle.identities['environment']['path']).write_bytes(b'changed environment')
        self.invalid(bundle, 'stale fingerprint')

    def test_freeze_boolean_and_float_equality_rejected(self):
        bundle = self.bundle()
        seal = ev.parse((bundle.root / bundle.freeze_ref['path']).read_bytes())
        for action, fragment in ((lambda s: s.update(schema_version=True), 'freeze version'),
                                 (lambda s: s['threshold'].update(numerator=True), 'freeze receipt'),
                                 (lambda s: s['threshold'].update(denominator=20.0), 'freeze receipt')):
            bundle.request['freeze'] = bundle.ref('freeze.json', copy.deepcopy(seal))
            bundle.mutate(bundle.request['freeze'], action)
            self.invalid(bundle, fragment)

    def test_unbalanced_order_with_consistent_timestamps(self):
        bundle = self.bundle()
        for block in bundle.request['blocks'][1::2]:
            first = ev.parse((bundle.root / block['a']['path']).read_bytes())
            second = ev.parse((bundle.root / block['b']['path']).read_bytes())
            bundle.mutate(block['a'], lambda r: r.update(started_utc_ns=second['started_utc_ns'], ended_utc_ns=second['ended_utc_ns']))
            bundle.mutate(block['b'], lambda r: r.update(started_utc_ns=first['started_utc_ns'], ended_utc_ns=first['ended_utc_ns']))
            block['first'] = 'a'
        self.invalid(bundle, 'unbalanced pair order')

    def test_resource_observable_policy_is_stricter(self):
        bundle = self.bundle()
        bundle.pilot['resource_policy'] = 'resource_observable_exact'
        bundle.seal(); bundle.request['freeze'] = bundle.freeze_ref
        bundle.mutate(bundle.request['blocks'][0]['b'], lambda r: r['resources'].update(allocations=19))
        self.assertEqual(bundle.evaluate()['decision'], 'resource_budget_failed')

    def test_unknown_keys_unsafe_refs_and_strict_json(self):
        bundle = self.bundle()
        bundle.request['bogus'] = 1; self.invalid(bundle, 'unknown fields')
        for data in (b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":Infinity}'):
            with self.assertRaises(ev.Invalid): ev.parse(data)
        for path in ('../escape', '/absolute', 'C:/absolute', 'bad\0path'):
            with self.assertRaises(ev.Invalid): ev.Reader(bundle.root).bytes({'path': path, 'sha256': '0' * 64})

    def test_candidate_measurement_before_freeze(self):
        bundle = self.bundle()
        bundle.mutate(bundle.request['blocks'][0]['a'], lambda r: r.update(started_utc_ns=FREEZE_TIME - 1))
        self.invalid(bundle, 'chronology')

    def test_cli_json_and_exclusive_output(self):
        bundle = self.bundle()
        request = bundle.ref('request.json', bundle.request)
        output = bundle.root / 'result.json'
        command = [sys.executable, str(Path(ev.__file__)), 'evaluate', '--input', str(bundle.root / request['path']), '--output', str(output)]
        proc = subprocess.run(command, capture_output=True, timeout=30)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        data = output.read_bytes()
        self.assertEqual(ev.parse(proc.stdout)['decision'], 'synthetic_gate_pass')
        proc = subprocess.run(command, capture_output=True, timeout=30)
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(ev.parse(proc.stdout)['status'], 'invalid_evidence')
        self.assertEqual(output.read_bytes(), data)


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(EvidenceTests)
    outcome = unittest.TextTestRunner(verbosity=2).run(suite)
    (WORK / 'results.json').write_bytes(ev.canonical({'schema_version': 1, 'status': 'success' if outcome.wasSuccessful() else 'failure',
        'synthetic_only': True, 'benchmark_execution': 'not_run', 'speedup_claim': None,
        'test_count': outcome.testsRun, 'errors': [name.id() for name, _ in outcome.errors],
        'failures': [name.id() for name, _ in outcome.failures], 'evaluator_sha256': ev.digest(Path(ev.__file__).read_bytes()),
        'tests_sha256': ev.digest(Path(__file__).read_bytes())}) + b'\n')
    print('Synthetic evaluator artifacts:', WORK)
    raise SystemExit(0 if outcome.wasSuccessful() else 1)
