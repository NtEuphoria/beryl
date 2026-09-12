"""Map exact generated artifact lines; never interpolate unknown engine columns."""
from pathlib import Path, PurePosixPath
from bisect import bisect_right
import re


def map_engine_diagnostics(api, artifact_path, artifact, engine_result, project_root=None, source_root=None):
    if type(engine_result) is not dict or type(engine_result.get('result', {})) is not dict:
        raise api.Failure('Engine result is not an object')
    raw = engine_result.get('result', {}).get('Diagnostics', [])
    if type(raw) is not list:
        raise api.Failure('Engine diagnostics are not a list')
    records = [{'raw': item, 'mapping_status': 'unavailable', 'original': None,
                'expansion_site': None, 'companion': None} for item in raw]
    sidecars = artifact.get('sidecars', {})
    if 'source-map.json' not in sidecars:
        return records
    data = api.read(Path(artifact_path) / 'source-map.json')
    if api.digest(data) != sidecars['source-map.json']:
        raise api.Failure('Generated source map changed', 'stale_input')
    mapping = api.parse(data)
    if type(mapping) is not dict or type(mapping.get('schema_version')) is not int:
        raise api.Failure('Source map is not a versioned object')
    if mapping['schema_version'] != 1 or mapping.get('column_unit') != 'byte':
        return records
    if mapping.get('operation') != 'source_map' or mapping.get('target') != 'enfusion':
        raise api.Failure('Unsupported source map operation or target')
    generated = mapping.get('generated', {})
    if type(generated) is not dict:
        raise api.Failure('Invalid generated source-map record')
    name = generated.get('file')
    if type(name) is not str or not name or '/' in name or '\\' in name or name in ('.', '..'):
        raise api.Failure('Invalid generated source-map filename')
    candidates = [entry for entry in artifact['files'] if PurePosixPath(entry).name == name]
    if len(candidates) != 1:
        return records
    relative = candidates[0]
    generated_bytes = api.read(api.safe_path(Path(artifact_path) / 'addon', relative, True))
    generated_hash = api.digest(generated_bytes)
    if generated_hash != generated.get('sha256') or generated_hash != artifact['files'][relative]:
        raise api.Failure('Source map does not describe the generated artifact', 'stale_input')
    if type(generated.get('bytes')) is not int or len(generated_bytes) != generated['bytes']:
        raise api.Failure('Source map byte count differs', 'stale_input')
    # Without exact source bytes, retain raw errors rather than trust coordinates.
    if source_root is None:
        return records
    source_root = Path(source_root).resolve()
    contents, source_lines, source_ids, documents = {}, {}, {}, {}

    def line_starts(content):
        return [0] + [index + 1 for index, byte in enumerate(content) if byte == 10]

    def load_source(path, fingerprint):
        if type(path) is not str or type(fingerprint) is not str or not re.fullmatch('[0-9a-f]{64}', fingerprint):
            raise api.Failure('Invalid source identity')
        if artifact['inputs'].get(path) != fingerprint:
            raise api.Failure('Source map source identity differs: ' + path, 'stale_input')
        if path not in contents:
            content = api.read(api.safe_path(source_root, path, True))
            if api.digest(content) != fingerprint:
                raise api.Failure('Source map source bytes changed: ' + path, 'stale_input')
            contents[path], source_lines[path] = content, line_starts(content)
        return contents[path]

    sources = mapping.get('sources')
    if type(sources) is not list:
        raise api.Failure('Source-map sources are not a list')
    for index, source in enumerate(sources):
        if type(source) is not dict:
            raise api.Failure('Invalid source-map source record')
        path = source.get('path')
        load_source(path, source.get('sha256'))
        if path in source_ids:
            raise api.Failure('Duplicate source-map source')
        source_ids[path] = index

    def validate_span(span):
        if span is None:
            return
        if type(span) is not dict or type(span.get('path')) is not str or span['path'] not in source_ids:
            raise api.Failure('Source-map origin is not a fingerprinted source')
        path = span['path']
        numbers = [span.get(key) for key in ('file_id', 'byte_offset', 'byte_length', 'line', 'column')]
        if any(type(value) is not int for value in numbers):
            raise api.Failure('Invalid source-map origin coordinates')
        file_id, start, length, line, column = numbers
        if file_id != source_ids[path] or start < 0 or length < 0 or start + length > len(contents[path]):
            raise api.Failure('Source-map origin exceeds its identified source')
        actual_line = bisect_right(source_lines[path], start)
        if line != actual_line or column != 1 + start - source_lines[path][actual_line - 1]:
            raise api.Failure('Source-map origin line/column differs from its byte position')

    def validate_companion(companion, declaration):
        if companion is None:
            return
        if type(companion) is not dict:
            raise api.Failure('Invalid companion source-map origin')
        path, pointer = companion.get('path'), companion.get('json_pointer')
        content = load_source(path, companion.get('sha256'))
        if type(pointer) is not str or not pointer.startswith('/') or re.search(r'~(?![01])', pointer):
            raise api.Failure('Invalid companion source-map JSON pointer')
        if path not in documents:
            documents[path] = api.parse(content)
        value = documents[path]
        for token in pointer[1:].split('/'):
            token = token.replace('~1', '/').replace('~0', '~')
            if type(value) is dict and token in value:
                value = value[token]
            elif (type(value) is list and re.fullmatch('0|[1-9][0-9]*', token)
                  and len(token) <= len(str(len(value))) and int(token) < len(value)):
                value = value[int(token)]
            else:
                raise api.Failure('Companion source-map JSON pointer does not resolve')
        referred = value.get('source') if type(value) is dict else value
        if referred != declaration:
            raise api.Failure('Companion source-map pointer refers to a different declaration')

    entries = mapping.get('mappings')
    if type(entries) is not list:
        raise api.Failure('Source-map mappings are not a list')
    generated_lines = line_starts(generated_bytes)
    lines = {}
    previous_end = 0
    for item in entries:
        if type(item) is not dict or type(item.get('generated')) is not dict:
            raise api.Failure('Invalid source-map entry')
        loc = item.get('generated', {})
        start, length, line = loc.get('byte_offset'), loc.get('byte_length'), loc.get('line')
        if any(type(n) is not int for n in (start, length, line)) or start < previous_end or length <= 0:
            raise api.Failure('Invalid or overlapping source-map range')
        if start + length > len(generated_bytes) or line <= 0:
            raise api.Failure('Source-map range exceeds generated bytes')
        if type(loc.get('column')) is not int or loc['column'] != 1:
            raise api.Failure('Source-map generated column must be one')
        if line != bisect_right(generated_lines, start) or generated_lines[line - 1] != start:
            raise api.Failure('Source-map line differs from generated byte position')
        segment = generated_bytes[start:start + length]
        if not segment.endswith(b'\n') or segment.count(b'\n') != 1:
            raise api.Failure('Source-map range must describe one complete generated line')
        previous_end = start + length
        if type(item.get('kind')) is not str or (item.get('declaration') is not None and type(item['declaration']) is not str):
            raise api.Failure('Invalid source-map association metadata')
        validate_span(item.get('original'))
        validate_span(item.get('expansion_site'))
        validate_companion(item.get('companion'), item.get('declaration'))
        if line in lines:
            raise api.Failure('Ambiguous source-map line')
        lines[line] = item
    root = Path(project_root).resolve() if project_root else None
    for record in records:
        item = record['raw']
        if type(item) is not dict or type(item.get('File')) is not str or type(item.get('Line')) is not int:
            continue
        reported = item['File'].replace('\\', '/')
        # Absolute engine paths are accepted only under this exact owned candidate.
        if Path(reported).is_absolute():
            if not root:
                continue
            try:
                reported = Path(reported).resolve().relative_to(root).as_posix()
            except (ValueError, OSError):
                continue
        if '..' in PurePosixPath(reported).parts or reported != relative:
            continue
        origin = lines.get(item['Line'])
        if not origin or origin.get('original') is None:
            continue
        record.update(mapping_status='mapped_span', original=origin['original'],
                      expansion_site=origin.get('expansion_site'), companion=origin.get('companion'),
                      declaration=origin.get('declaration'), kind=origin.get('kind'),
                      generated_sha256=generated_hash,
                      column_mapping='unavailable; source span association only')
    return records
