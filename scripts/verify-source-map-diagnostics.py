#!/usr/bin/env python3
"""Contained line-association faults; synthetic engine diagnostics, no VM claims."""
import argparse
import copy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools/beryl-mod'))
import mod
from source_maps import map_engine_diagnostics


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--beryl', required=True, type=Path)
    args = parser.parse_args()
    work = Path(tempfile.mkdtemp(prefix='map-diagnostics-', dir=ROOT / 'build'))
    project = work / 'project'; project.mkdir()
    for file in ('pid.be', 'pid_test.be', 'beryl.mod.json'):
        shutil.copyfile(ROOT / 'packages/sparkos/pid' / file, project / file)
    evidence = {'schema_version': 1, 'status': 'failure', 'checks': [],
                'compiler_sha256': mod.digest(mod.read(args.beryl.resolve())),
                'mapper_sha256': mod.digest(mod.read(ROOT / 'tools/beryl-mod/source_maps.py')),
                'scope': 'synthetic engine diagnostics for an actual generated artifact'}
    print(f'Mapped diagnostic artifacts: {work}', flush=True)
    try:
        argv = [sys.executable, ROOT / 'tools/beryl-mod/mod.py', '--beryl', args.beryl.resolve(),
                'build', '--project', project]
        proc = subprocess.run(list(map(str, argv)), capture_output=True, text=True, encoding='utf-8', timeout=45)
        evidence['build'] = {'argv': list(map(str, argv)), 'exit_code': proc.returncode,
                             'stdout': proc.stdout, 'stderr': proc.stderr}
        assert proc.returncode == 0, proc.stdout + proc.stderr
        result = json.loads(proc.stdout); path = Path(result['artifact_path'])
        artifact = mod.parse(mod.read(path / 'artifact.json'))
        mapping = mod.parse(mod.read(path / 'source-map.json'))
        origin = next(entry for entry in mapping['mappings'] if entry['kind'] == 'exported_constructor')
        relative = next(name for name in artifact['files'] if name.endswith('_Generated.c'))
        line = origin['generated']['line']
        diagnostics = [dict(File=relative, Line=line, Column=999, Message='deliberate error'),
                       dict(File='scripts/Unrelated/' + mapping['generated']['file'], Line=line, Message='same basename'),
                       dict(File=relative, Line=999999, Message='outside map'),
                       dict(File='../' + relative, Line=line, Message='escape'),
                       dict(File=str(path / 'addon' / relative), Line=line, Message='owned absolute'),
                       dict(File=relative, Line=True, Message='bool is not line')]
        engine = {'result': {'Diagnostics': diagnostics}}
        def associate(manifest=artifact, diagnostics=engine, root=project):
            return map_engine_diagnostics(mod, path, manifest, diagnostics, path / 'addon', source_root=root)
        mapped = associate()
        assert mapped[0]['raw'] == diagnostics[0] and mapped[0]['original'] == origin['original']
        assert mapped[0]['companion']['json_pointer'].endswith('/constructor')
        assert mapped[0]['column_mapping'].startswith('unavailable')
        assert mapped[4]['mapping_status'] == 'mapped_span'
        assert all(mapped[i]['mapping_status'] == 'unavailable' for i in (1, 2, 3, 5))
        evidence['checks'].append('exact owned paths, wrapper origins, companion pointer; raw/unknown columns preserved')
        old = copy.deepcopy(artifact); old.pop('sidecars')
        assert all(x['mapping_status'] == 'unavailable' for x in associate(old))
        assert all(x['mapping_status'] == 'unavailable' for x in associate(root=None))
        evidence['checks'].append('older artifacts retain raw diagnostics without fabricated locations')
        original = (path / 'source-map.json').read_bytes()
        def reject(data, update_hash):
            (path / 'source-map.json').write_bytes(data)
            mutant = copy.deepcopy(artifact)
            if update_hash: mutant['sidecars']['source-map.json'] = mod.digest(data)
            try:
                associate(mutant)
            except mod.Failure:
                return
            raise AssertionError('invalid source map accepted')
        reject(original + b' ', False)
        bad = copy.deepcopy(mapping); bad['generated']['sha256'] = '0' * 64
        reject(mod.canonical(bad), True)
        bad = copy.deepcopy(mapping); bad['mappings'][0]['generated']['line'] += 1
        reject(mod.canonical(bad), True)
        bad = copy.deepcopy(mapping); bad['sources'][0]['sha256'] = '0' * 64
        reject(mod.canonical(bad), True)
        for field in ('original', 'expansion_site'):
            for key, value in (('byte_offset', -1), ('byte_length', 999999999), ('line', 0), ('column', True), ('file_id', 99), ('path', '../escape.be')):
                bad = copy.deepcopy(mapping)
                entry = next(item for item in bad['mappings'] if item['original'])
                entry[field] = copy.deepcopy(entry['original'])
                entry[field][key] = value
                reject(mod.canonical(bad), True)
        for pointer in ('/exports/999', '/exports/0/name', '/exports/00', '/exports/~3', '/exports/' + '9' * 5000):
            bad = copy.deepcopy(mapping)
            next(item for item in bad['mappings'] if item.get('companion'))['companion']['json_pointer'] = pointer
            reject(mod.canonical(bad), True)
        for mutate in (lambda data: data['sources'].append(copy.deepcopy(data['sources'][0])),
                       lambda data: data.update(mappings=[None]),
                       lambda data: data.update(sources=[None]),
                       lambda data: data.update(generated=[]),
                       lambda data: data.update(schema_version=True),
                       lambda data: data['mappings'][0]['generated'].update(column=2),
                       lambda data: data['mappings'][0]['generated'].update(byte_length=data['generated']['bytes']),
                       lambda data: data['mappings'][0]['generated'].update(byte_length=data['mappings'][0]['generated']['byte_length'] - 1)):
            bad = copy.deepcopy(mapping); mutate(bad); reject(mod.canonical(bad), True)
        (path / 'source-map.json').write_bytes(original)
        evidence['checks'].append('changed bytes, output hashes, origins, expansions, companions, malformed shapes and incomplete lines rejected')
        old_source = (project / 'pid.be').read_bytes()
        (project / 'pid.be').write_bytes(old_source + b'\n')
        try:
            associate()
        except mod.Failure:
            pass
        else:
            raise AssertionError('changed source bytes accepted')
        finally:
            (project / 'pid.be').write_bytes(old_source)
        assert engine['result']['Diagnostics'] == diagnostics
        evidence['checks'].append('source bytes are rechecked and raw engine diagnostics remain unchanged')

        component_project = work / 'component-project'
        shutil.copytree(ROOT / 'packages/sparkos/tablet-admission', component_project)
        argv = [sys.executable, ROOT / 'tools/beryl-mod/mod.py', '--beryl', args.beryl.resolve(),
                'build', '--project', component_project]
        proc = subprocess.run(list(map(str, argv)), capture_output=True, text=True, encoding='utf-8', timeout=45)
        evidence['component_build'] = {'argv': list(map(str, argv)), 'exit_code': proc.returncode,
                                       'stdout': proc.stdout, 'stderr': proc.stderr}
        assert proc.returncode == 0, proc.stdout + proc.stderr
        built = json.loads(proc.stdout)
        component_path = Path(built['artifact_path'])
        component_artifact = mod.parse(mod.read(component_path / 'artifact.json'))
        component_mapping = mod.parse(mod.read(component_path / 'source-map.json'))
        component_relative = next(name for name in component_artifact['files'] if name.endswith('_Generated.c'))
        selected = [next(m for m in component_mapping['mappings'] if m['kind'] == kind)
                    for kind in ('component_descriptor', 'component_initializer', 'component_handler', 'component_event_mask', 'component_superclass')]
        component_raw = [dict(File=component_relative, Line=m['generated']['line'], Column=999,
                              Message='synthetic component diagnostic') for m in selected]
        def component_associate(manifest=component_artifact):
            return map_engine_diagnostics(mod, component_path, manifest, {'result': {'Diagnostics': component_raw}},
                                          component_path / 'addon', source_root=component_project)
        component_mapped = component_associate()
        assert component_mapped[0]['mapping_status'] == 'mapped_companion' and component_mapped[0]['original'] is None
        assert all(item['mapping_status'] == 'mapped_span' for item in component_mapped[1:])
        assert all(item['raw'] == original for item, original in zip(component_mapped, component_raw))
        assert all(item['companion']['json_pointer'].startswith('/components/0/') for item in component_mapped)
        assert all(item['column_mapping'].startswith('unavailable') for item in component_mapped)
        evidence['checks'].append('actual generated scalar component maps descriptor, initializer, handler, event-mask and superclass lines without column guesses')
        component_original = (component_path / 'source-map.json').read_bytes()
        for key, value in (('expected_value', 'WrongIdentity'), ('identity_kind', 'unknown'), ('json_pointer', '/components/0/state')):
            bad = copy.deepcopy(component_mapping)
            next(m for m in bad['mappings'] if m['kind'] == 'component_descriptor')['companion'][key] = value
            data = mod.canonical(bad)
            (component_path / 'source-map.json').write_bytes(data)
            mutant = copy.deepcopy(component_artifact)
            mutant['sidecars']['source-map.json'] = mod.digest(data)
            try:
                component_associate(mutant)
            except mod.Failure:
                pass
            else:
                raise AssertionError('invalid component identity origin accepted')
        (component_path / 'source-map.json').write_bytes(component_original)
        evidence['checks'].append('changed component identity, association kind and JSON pointer are rejected even with a recomputed sidecar hash')
        assert mod.digest(mod.read(ROOT / 'tools/beryl-mod/source_maps.py')) == evidence['mapper_sha256']
        evidence['status'] = 'success'
    except BaseException as exc:
        evidence['error'] = repr(exc)
        raise
    finally:
        mod.write_json(work / 'result.json', evidence)
    print(f"Passed {len(evidence['checks'])} mapped-diagnostic groups", flush=True)


if __name__ == '__main__':
    main()
