#!/usr/bin/env python3
"""Verify exact Enfusion sidecar bytes and source associations; no engine claims."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--beryl', required=True, type=Path)
    args = parser.parse_args()
    beryl = args.beryl.resolve(strict=True)
    work = Path(tempfile.mkdtemp(prefix='source-maps & spaces-', dir=ROOT / 'build'))
    result = {'schema_version': 1, 'status': 'running', 'commands': [], 'checks': [],
              'compiler_sha256': hashlib.sha256(beryl.read_bytes()).hexdigest()}
    print(f'Source map artifacts: {work}', flush=True)

    def run(argv, expected=0):
        proc = subprocess.run([str(beryl), *map(str, argv)], cwd=work,
                              capture_output=True, text=True, encoding='utf-8', timeout=30)
        result['commands'].append({'argv': list(map(str, argv)), 'exit_code': proc.returncode,
                                   'stdout': proc.stdout, 'stderr': proc.stderr})
        assert (proc.returncode == 0) == (expected == 0), result['commands'][-1]
        return proc

    try:
        # Preserve the former shallow-copy fixture as a rejection obligation.
        unsupported = work / 'optional-copy.be'
        unsupported.write_text('module mapped\npub struct OptionalHolder { field: i32? }\n', encoding='utf-8')
        rejected = run(['build', '--target', 'enfusion', unsupported], expected=1)
        assert 'BE0701' in rejected.stderr and 'storage admission' in rejected.stderr
        assert not rejected.stdout, 'unsupported helper emitted generated code'
        result['checks'].append('legacy optional field copy stays an explicit unsupported regression')
        source = work / 'logic & origin.be'
        source.write_text('''//! Mapped UTF-8 comment: αβ.
module mapped
pub struct Value { n: i32 = 7 }
pub fn Value.initialize(inout self, seed: i32 = 3) { self.n = seed }
pub fn Value.read(let self) -> i32 { return self.n }
fn default_value() -> Value { return Value{n: 13} }
fn consume(value: Value = default_value()) -> i32 {
    var copy = value
    copy.n += 1
    return copy.n
}
pub fn evaluate() -> i32 {
    var total = consume()
    total += nested()
    while total < 16 { total += 1 }
    return total
}
pub fn optional_local() { var held: i32? }
''', encoding='utf-8', newline='\n')
        other = work / 'other & origin.be'
        other.write_text('module mapped\nfn auxiliary(value: i32 = 23) -> i32 { return value }\n'
                         'pub fn nested(value: i32 = auxiliary()) -> i32 { return value }\n', encoding='utf-8', newline='\n')
        source_bytes = {str(path): path.read_bytes() for path in (source, other)}
        exports = ['--export-class', 'mapped.Value=MappedValue',
                   '--export-constructor', 'mapped.Value.initialize=MappedValue',
                   '--export-method', 'mapped.Value.read=Read']
        plain, mapped = work / 'plain', work / 'mapped'
        plain.mkdir(); mapped.mkdir()
        mapfile = work / 'source-map.json'
        common = ['build', '--target', 'enfusion', '--prefix', 'MAP', *exports, source, other]
        run([*common, '--out-dir', plain])
        run([*common, '--out-dir', mapped, '--source-map', mapfile])
        generated = (mapped / 'MAP_Generated.c').read_bytes()
        assert generated == (plain / 'MAP_Generated.c').read_bytes()
        original_map = mapfile.read_bytes()
        mapping = json.loads(original_map)
        assert mapping['generated']['sha256'] == hashlib.sha256(generated).hexdigest()
        assert mapping['generated']['bytes'] == len(generated)
        assert mapping['column_unit'] == 'byte'
        assert mapping['sources'][0]['sha256'] == hashlib.sha256(source.read_bytes()).hexdigest()
        assert mapping['sources'][1]['sha256'] == hashlib.sha256(other.read_bytes()).hexdigest()
        assert mapping['mapping_precision'].startswith('generated line associated')
        result['checks'].append('opt-in sidecar leaves generated code byte-identical and binds exact source/output')

        origins = source.read_bytes()
        previous = -1
        for entry in mapping['mappings']:
            location = entry['generated']
            start, size = location['byte_offset'], location['byte_length']
            assert start >= previous and size > 0 and start + size <= len(generated)
            assert start == 0 or generated[start - 1] == 10
            assert generated[start:start + size].endswith(b'\n')
            assert location['line'] == 1 + generated[:start].count(b'\n')
            previous = start + size
            for field in ('original', 'expansion_site'):
                loc = entry[field]
                if loc:
                    content = source_bytes[loc['path']]
                    assert mapping['sources'][loc['file_id']]['path'] == loc['path']
                    assert loc['byte_offset'] + loc['byte_length'] <= len(content)
                    assert loc['line'] == 1 + content[:loc['byte_offset']].count(b'\n')
                    assert loc['column'] == loc['byte_offset'] - content.rfind(b'\n', 0, loc['byte_offset'])
        assert mapping['mappings']
        result['checks'].append('all line-byte ranges and original spans are bounded and correctly positioned')

        kinds = {entry['kind'] for entry in mapping['mappings']}
        assert {'statement', 'prepared_expression', 'value_helper', 'constructor',
                'field_default', 'exported_constructor', 'default_expansion'} <= kinds, kinds
        expanded = [entry for entry in mapping['mappings'] if entry['kind'] == 'default_expansion']
        assert expanded and all(entry['expansion_site'] for entry in expanded)
        assert any(origins[e['expansion_site']['byte_offset']:e['expansion_site']['byte_offset'] +
                          e['expansion_site']['byte_length']] == b'consume()' for e in expanded)
        wrapper = [e for e in mapping['mappings'] if e['kind'] == 'exported_constructor']
        assert wrapper and all(e['declaration'] == 'mapped.Value.initialize' for e in wrapper)
        nested = [e for e in expanded if e['original']['path'] == str(other)]
        assert any(source_bytes[str(other)][e['original']['byte_offset']:e['original']['byte_offset'] +
                       e['original']['byte_length']] == b'auxiliary()' and
                   origins[e['expansion_site']['byte_offset']:e['expansion_site']['byte_offset'] +
                           e['expansion_site']['byte_length']] == b'nested()' for e in nested)
        statements = [e for e in mapping['mappings'] if e['kind'] == 'statement' and e['declaration'] == 'mapped.evaluate']
        assert any(origins[e['original']['byte_offset']:e['original']['byte_offset'] + e['original']['byte_length']].startswith(b'return total') for e in statements)
        result['checks'].append('statements, preparations, defaults, helpers and exported constructor provenance')
        result['checks'].append('cross-file nested default identifies template and outermost request, with exact byte columns')
        result['metadata'] = {'generated_bytes': len(generated), 'sidecar_bytes': len(original_map),
                              'mapping_records': len(mapping['mappings']), 'generated_lines': generated.count(b'\n'),
                              'timing_claim': 'not measured; byte counts only'}
        assert len(mapping['mappings']) <= generated.count(b'\n')

        run([*common, '--out-dir', mapped, '--source-map', mapfile])
        assert mapfile.read_bytes() == original_map
        result['checks'].append('deterministic sidecar for identical inputs')
        run([*common, '--source-map', mapfile], expected=1)
        run(['check', '--source-map', mapfile, source], expected=1)
        run([*common, '--out-dir', mapped, '--source-map', work / 'missing' / 'map.json'], expected=1)
        before_source = source.read_bytes()
        run([*common, '--out-dir', mapped, '--source-map', source], expected=1)
        assert source.read_bytes() == before_source
        before_generated = (mapped / 'MAP_Generated.c').read_bytes()
        run([*common, '--out-dir', mapped, '--source-map', mapped / 'MAP_Generated.c'], expected=1)
        assert (mapped / 'MAP_Generated.c').read_bytes() == before_generated
        result['checks'].append('incompatible options and failed sidecar writes fail explicitly')
        result['status'] = 'success'
    except BaseException as exc:
        result['status'] = 'failure'
        result['error'] = repr(exc)
        raise
    finally:
        (work / 'result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(f"Passed {len(result['checks'])} source map groups", flush=True)


if __name__ == '__main__':
    main()
