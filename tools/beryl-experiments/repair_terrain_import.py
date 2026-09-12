#!/usr/bin/env python3
"""Preserve a failed terrain import and repair its absolute environment reference.

No engine work runs. The only launched programs are this repository's importer
and journal verifier under the current Python interpreter, using validated flags.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys

import evaluate as ev


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--job', type=Path, required=True)
    args = parser.parse_args()
    job = args.job.resolve(strict=True)
    importer = Path(__file__).with_name('import_terrain.py').resolve()
    collector = Path(__file__).with_name('collect.py').resolve()
    original_path = job / 'result.json'
    original = ev.parse(original_path.read_bytes())
    prior = original['import']
    ev.require(prior['returncode'] != 0, 'original import was not a failure')
    old_argv = prior['argv']
    ev.require(type(old_argv) is list and len(old_argv) >= 2 and Path(old_argv[1]).resolve() == importer,
               'recorded command is not the owned terrain importer')
    expected_flags = ('measurement-receipt', 'semantic-receipt', 'schedule', 'candidate', 'candidate-root',
                      'semantic-candidate', 'semantic-candidate-root', 'tool-root', 'tool-manifest',
                      'integration-root', 'compiler', 'timer-evidence', 'environment', 'output')
    ev.require(len(old_argv) == 2 + 2 * len(expected_flags), 'recorded importer argument count differs')
    options = {}
    for at in range(2, len(old_argv), 2):
        key, value = old_argv[at:at + 2]
        ev.require(key.startswith('--') and key[2:] in expected_flags and key not in options and type(value) is str,
                   'recorded importer contains unknown/repeated arguments')
        options[key] = value
    environment_path = Path(options['--environment']).resolve()
    ev.require(environment_path == job / 'environment.json', 'unexpected original environment descriptor')
    environment = ev.parse(environment_path.read_bytes())
    proof = environment['evidence']
    expected_proof = job / 'environment-evidence.json'
    ev.require(Path(proof['path']).resolve() == expected_proof and ev.digest(expected_proof.read_bytes()) == proof['sha256'],
               'environment evidence identity differs')
    repaired_path, destination, receipt_path = job / 'environment-v2.json', job / 'collection-v2', job / 'import-repair.json'
    ev.require(not repaired_path.exists() and not destination.exists() and not receipt_path.exists(), 'repair destination already exists')
    environment['evidence'] = {'path': expected_proof.name, 'sha256': proof['sha256']}
    with repaired_path.open('xb') as stream: stream.write(ev.canonical(environment) + b'\n')
    options['--environment'], options['--output'] = str(repaired_path), str(destination)
    argv = [sys.executable, str(importer)]
    for flag in expected_flags: argv += ['--' + flag, options['--' + flag]]
    process = subprocess.run(argv, capture_output=True, text=True, encoding='utf-8', timeout=120)
    receipt = {'schema_version': 1, 'kind': 'beryl.performance.import_repair', 'status': 'failure',
               'original_result_sha256': ev.digest(original_path.read_bytes()),
               'change': 'new descriptor uses relative path to identical environment evidence; original files preserved',
               'argv': argv, 'returncode': process.returncode, 'stdout': process.stdout, 'stderr': process.stderr}
    if process.returncode == 0:
        verify = subprocess.run([sys.executable, str(collector), 'verify-journal', '--journal', str(destination / 'journal')],
                                capture_output=True, text=True, encoding='utf-8', timeout=120)
        receipt['journal_replay'] = {'returncode': verify.returncode, 'stdout': verify.stdout, 'stderr': verify.stderr}
        if verify.returncode == 0: receipt['status'] = 'success'
    with receipt_path.open('xb') as stream: stream.write(ev.canonical(receipt) + b'\n')
    print(ev.canonical({'status': receipt['status'], 'receipt': str(receipt_path), 'journal': str(destination / 'journal')}).decode())
    return 0 if receipt['status'] == 'success' else 2


if __name__ == '__main__':
    raise SystemExit(main())
