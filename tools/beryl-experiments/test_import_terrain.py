#!/usr/bin/env python3
"""Synthetic importer provenance/mismatch tests. Never runs Workbench."""
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
import sys

import collect as co
import evaluate as ev
import import_terrain as im
from test_collect import Bundle, WORK


class ImportBundle:
    def __init__(self, name):
        self.base = Bundle('import_' + name)
        b = self.base
        self.root = b.root
        self.tool = self.root / 'tool'; self.tool.mkdir()
        self.integration = self.root / 'integration'; (self.integration / 'scripts').mkdir(parents=True)
        (self.integration / 'scripts' / 'probe.ps1').write_bytes(b'# SYNTHETIC integration\n')
        (self.tool / 'terrain-reference.c.txt').write_bytes(b'// SYNTHETIC reference\n')
        (self.tool / 'terrain-adapter.c.in').write_bytes(b'// SYNTHETIC candidate\n')
        self.templates = {p.name: ev.digest(p.read_bytes()) for p in self.tool.iterdir()}
        b.ref('tool-manifest.json', self.templates)
        self.compiler = self.root / 'compiler.fake'; self.compiler.write_bytes(b'SYNTHETIC compiler; not executable')
        self.plugin = {'probe.ps1': ev.digest((self.integration / 'scripts' / 'probe.ps1').read_bytes())}
        b.ref('environment.json', {'schema_version': 1, 'kind': 'beryl.performance.environment_review', 'status': 'reviewed',
                                 'description': 'Synthetic test; no actual process/environment.', 'evidence': b.proof})
        datasets = [{'id': case, 'synthetic': True} for case in b.plan['case_ids']]
        self.receipts = {}
        for phase, scenario in (('timing', 'measure.terrain.construction'), ('semantic', 'compare.terrain.chunks')):
            job = self.root / phase; job.mkdir()
            candidate = job / 'candidate'; candidate.mkdir()
            (candidate / 'generated.c').write_bytes(('// SYNTHETIC ' + phase).encode())
            files = {'generated.c': ev.digest((candidate / 'generated.c').read_bytes())}
            contract = {'source_templates': self.templates, 'datasets': datasets, 'scope': 'synthetic'}
            if phase == 'timing': contract['schedule_sha256'] = ev.digest((self.root / 'schedule.json').read_bytes())
            params = {'case_ids': b.plan['case_ids']}
            manifest = {'token': 'synthetic-token', 'files': files, 'parameters': params, 'artifact_sha256': 'b' * 64,
                        'staged_artifact_sha256': ev.digest(ev.canonical(files)), 'scenario_contract': contract}
            (job / 'scenario-candidate.json').write_bytes(ev.canonical(manifest))
            runtime = ev.parse((self.root / 'runtime.json').read_bytes())
            if phase == 'semantic':
                runtime['rpc']['Response'] = {'token': 'synthetic-token', 'executed': 1, 'failures': 0,
                                             'caseIds': b.plan['case_ids'], 'checks': 123}
            (job / 'scenario-runtime.json').write_bytes(ev.canonical(runtime))
            receipt = {'schema_version': 1, 'stage': 'runtime_scenario', 'status': 'success', 'scenario': scenario,
                       'compiled_token': 'synthetic-token', 'artifact_sha256': 'b' * 64, 'source_sha256': 'c' * 64,
                       'staged_artifact_sha256': manifest['staged_artifact_sha256'], 'parameters': params,
                       'compiler_sha256': ev.digest(self.compiler.read_bytes()), 'tool_sha256': ev.digest(ev.canonical(self.templates)),
                       'engine_sha256': 'a' * 64, 'engine_version': 'synthetic-1', 'integration_files': self.plugin,
                       'scenario_contract': contract, 'trace': {'checks': 123},
                       'raw_results': {str(job / 'scenario-runtime.json'): ev.digest((job / 'scenario-runtime.json').read_bytes())}}
            self.receipts[phase] = receipt
            (job / 'receipt.json').write_bytes(ev.canonical(receipt))
        self.args = SimpleNamespace(measurement_receipt=self.root / 'timing/receipt.json', semantic_receipt=self.root / 'semantic/receipt.json',
            schedule=self.root / 'schedule.json', candidate=self.root / 'timing/scenario-candidate.json', candidate_root=self.root / 'timing/candidate',
            semantic_candidate=self.root / 'semantic/scenario-candidate.json', semantic_candidate_root=self.root / 'semantic/candidate',
            tool_root=self.tool, tool_manifest=self.root / 'tool-manifest.json', integration_root=self.integration,
            compiler=self.compiler, timer_evidence=self.root / 'producer.raw', environment=self.root / 'environment.json', output=self.root / 'imported')

    def run(self):
        return im.build_bundle(self.args, evidence_kind='synthetic_validation')


class ImportTests(unittest.TestCase):
    def fixture(self): return ImportBundle(self._testMethodName)

    def test_matching_raw_sources_import_and_replay(self):
        bundle = self.fixture()
        result = bundle.run()
        self.assertEqual(result['evidence_kind'], 'synthetic_validation')
        self.assertFalse(result['adoption_eligible'])
        self.assertEqual(co.verify_journal(bundle.args.output / 'journal')['status'], 'verified')

    def test_template_mismatch_cannot_reuse_old_semantics(self):
        bundle = self.fixture()
        path = bundle.args.semantic_candidate
        manifest = ev.parse(path.read_bytes()); manifest['scenario_contract']['source_templates']['terrain-adapter.c.in'] = 'd' * 64
        path.write_bytes(ev.canonical(manifest))
        receipt = bundle.receipts['semantic']; receipt['scenario_contract'] = manifest['scenario_contract']
        bundle.args.semantic_receipt.write_bytes(ev.canonical(receipt))
        with self.assertRaisesRegex(ev.Invalid, 'identical source templates'): bundle.run()
        self.assertFalse(bundle.args.output.exists())

    def test_changed_compiler_or_staged_source_rejected(self):
        bundle = self.fixture()
        bundle.compiler.write_bytes(b'changed')
        with self.assertRaisesRegex(ev.Invalid, 'compiler binary changed'): bundle.run()
        bundle.compiler.write_bytes(b'SYNTHETIC compiler; not executable')
        (bundle.args.candidate_root / 'generated.c').write_bytes(b'changed')
        with self.assertRaisesRegex(ev.Invalid, 'changed candidate source'): bundle.run()

    def test_raw_response_changed_or_semantic_failed_rejected(self):
        bundle = self.fixture()
        raw = bundle.root / 'semantic/scenario-runtime.json'
        data = ev.parse(raw.read_bytes()); data['rpc']['Response']['failures'] = 1
        raw.write_bytes(ev.canonical(data))
        with self.assertRaisesRegex(ev.Invalid, 'raw result fingerprint'): bundle.run()
        receipt = bundle.receipts['semantic']; receipt['raw_results'][str(raw)] = ev.digest(raw.read_bytes())
        bundle.args.semantic_receipt.write_bytes(ev.canonical(receipt))
        with self.assertRaisesRegex(ev.Invalid, 'semantic comparison incomplete'): bundle.run()

    def test_no_extra_source_or_held_out_relabeling(self):
        bundle = self.fixture()
        (bundle.args.candidate_root / 'extra.c').write_bytes(b'extra')
        with self.assertRaisesRegex(ev.Invalid, 'source selection changed'): bundle.run()

    def test_integration_change_and_unreviewed_environment(self):
        bundle = self.fixture()
        plugin = bundle.integration / 'scripts/probe.ps1'
        original = plugin.read_bytes(); plugin.write_bytes(b'changed')
        with self.assertRaisesRegex(ev.Invalid, 'integration file changed'): bundle.run()
        plugin.write_bytes(original)
        environment = ev.parse(bundle.args.environment.read_bytes()); environment['status'] = 'unknown'
        bundle.args.environment.write_bytes(ev.canonical(environment))
        with self.assertRaisesRegex(ev.Invalid, 'unreviewed environment'): bundle.run()


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(ImportTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    summary = {'schema_version': 1, 'kind': 'beryl.performance.import_tests', 'evidence_kind': 'synthetic_validation',
               'passed': result.wasSuccessful(), 'tests': result.testsRun, 'failures': len(result.failures),
               'errors': len(result.errors), 'measurements_collected': False, 'work': str(WORK)}
    (WORK / 'import-results.json').write_bytes(ev.canonical(summary) + b'\n')
    print(ev.canonical(summary).decode())
    sys.exit(0 if result.wasSuccessful() else 1)
