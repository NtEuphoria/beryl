"""Exact, reversible screen-call observations for a pinned tablet seam.

This source-only transformation adds no runtime receipt or service proof.
Only the trusted hook template and RunOperation opcodes 10/11/12 change.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import tempfile

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SOURCE = ROOT / 'packages/sparkos/tablet-service-prototype/tablet-service.c.in'
SOURCE_SHA256 = '21479adf12a76a48ad7be9419e6e5047d663cce0ebee1341e5d8bfaf8d20d3c7'
HOOKS = HERE / 'screen-observation-hooks.c.in'
HOOKS_SHA256 = '9efacf44be76da7b4a464dd66e8e5fa076c20c352144f1ffc48775e089c250e5'
MAX_SOURCE_BYTES = 65536
ANCHOR = b'\t// Each entry has its own PC, reply, input and keybind binding. State is shared.\n'
OLD = b'''\t\t\telse if (code == 10)
\t\t\t\tm_ScreenRT = new SPK_ScreenRT();
\t\t\telse if (code == 11)
\t\t\t\tm_ScreenRT.Enable(GetOwner());
\t\t\telse if (code == 12)
\t\t\t\tm_ScreenRT.Disable();
'''
NEW = b'''\t\t\telse if (code == 10)
\t\t\t{
\t\t\t\tm_ScreenRT = new SPK_ScreenRT();
\t\t\t\tBerylObserveScreenCreated();
\t\t\t}
\t\t\telse if (code == 11)
\t\t\t{
\t\t\t\tint berylScreenEnableInvocation = BerylObserveScreenEnableEnter();
\t\t\t\tbool berylScreenEnableReturned = m_ScreenRT.Enable(GetOwner());
\t\t\t\tBerylObserveScreenEnableExit(berylScreenEnableInvocation, berylScreenEnableReturned);
\t\t\t}
\t\t\telse if (code == 12)
\t\t\t{
\t\t\t\tint berylScreenDisableInvocation = BerylObserveScreenDisableEnter();
\t\t\t\tm_ScreenRT.Disable();
\t\t\t\tBerylObserveScreenDisableExit(berylScreenDisableInvocation);
\t\t\t}
'''
EXPECTED_CASE_IDS = (
    'positive.exact-strip', 'positive.native-call-counts', 'positive.local-results',
    'positive.lifecycle-methods-unchanged', 'positive.all-other-methods-unchanged',
    'positive.origin-map', 'positive.no-op-base', 'negative.create-removed',
    'negative.create-duplicated', 'negative.create-hook-before-publication',
    'negative.enable-removed', 'negative.enable-duplicated', 'negative.enable-reply',
    'negative.enable-hook-before-return', 'negative.enable-enter-after-call',
    'negative.disable-removed', 'negative.disable-duplicated', 'negative.disable-exit-before-return',
    'negative.shared-slot', 'negative.extra-owner-read', 'negative.manual-callback',
    'negative.other-init', 'negative.other-frame', 'negative.other-delete',
    'negative.hook-template-return', 'negative.hook-template-effect', 'negative.original-identity',
    'negative.hook-omitted', 'negative.hook-duplicated', 'negative.delta-duplicated',
    'negative.nonbytes', 'negative.source-budget', 'negative.source-crlf',
)


class InstrumentationFailure(ValueError):
    """A source contract was rejected; never a runtime/source-trap outcome."""


def require(value: bool, message: str) -> None:
    if not value:
        raise InstrumentationFailure(message)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_fixed(path: Path) -> bytes:
    require(path.is_file() and not path.is_symlink(), 'Pinned input is not a direct regular file')
    with path.open('rb') as stream:
        value = stream.read(MAX_SOURCE_BYTES+1)
    require(0 < len(value) <= MAX_SOURCE_BYTES, 'Pinned input exceeds bounded source read')
    return value


def _bounded(data: bytes, name: str) -> None:
    require(type(data) is bytes and 0 < len(data) <= MAX_SOURCE_BYTES, name + ' bytes exceed the exact source domain')
    require(b'\r' not in data and b'\0' not in data and data.endswith(b'\n'), name + ' line/encoding shape differs')
    try:
        data.decode('utf8', 'strict')
    except UnicodeDecodeError as exc:
        raise InstrumentationFailure(name + ' UTF-8 differs') from exc


def _hooks(hooks: bytes | None) -> bytes:
    value = _read_fixed(HOOKS) if hooks is None else hooks
    _bounded(value, 'Hook template')
    require(digest(value) == HOOKS_SHA256, 'Trusted hook template identity differs')
    return value


def _original(original: bytes) -> None:
    _bounded(original, 'Original adapter')
    require(digest(original) == SOURCE_SHA256, 'Original tablet-service adapter identity differs')
    require(original.count(ANCHOR) == original.count(OLD) == 1, 'Pinned insertion boundaries differ')


def instrument_adapter(original: bytes, hooks: bytes | None = None) -> bytes:
    """Return unexpanded EnforceScript template; perform no engine operation."""
    _original(original)
    hook_bytes = _hooks(hooks)
    value = original.replace(ANCHOR, hook_bytes + ANCHOR, 1).replace(OLD, NEW, 1)
    validate_instrumented(value, original, hook_bytes)
    return value


def strip_instrumentation(value: bytes, hooks: bytes | None = None) -> bytes:
    """Accept only the exact delta, returning the complete pinned original."""
    _bounded(value, 'Instrumented adapter')
    hook_bytes = _hooks(hooks)
    require(value.count(hook_bytes + ANCHOR) == value.count(NEW) == 1, 'Trusted hook/delta count or placement differs')
    restored = value.replace(hook_bytes + ANCHOR, ANCHOR, 1).replace(NEW, OLD, 1)
    _original(restored)
    return restored


def validate_instrumented(value: bytes, original: bytes, hooks: bytes | None = None) -> dict:
    _original(original)
    hook_bytes = _hooks(hooks)
    restored = strip_instrumentation(value, hook_bytes)
    require(restored == original, 'Stripping instrumentation did not reconstruct every original byte')
    require(value.count(b'm_ScreenRT.Enable(GetOwner())') == 1 and
            value.count(b'm_ScreenRT.Disable();') == 1 and
            value.count(b'm_ScreenRT = new SPK_ScreenRT();') == 1 and
            value.count(b'GetOwner()') == original.count(b'GetOwner()'),
            'Original exactly-once native calls or owner evaluation changed')
    return {
        'schema_version': 1, 'status': 'source_admitted',
        'original_sha256': digest(original), 'hooks_sha256': digest(hook_bytes),
        'instrumented_sha256': digest(value), 'original_reconstructed': True,
        'changed_region': 'RunOperation opcodes 10/11/12 plus protected no-op hooks',
        'invocation_identity': 'Enable/Disable IDs are separate local int values; no shared current-operation slot',
        'enable_return_policy': 'Actual bool is observed after the call; not used for reply or Beryl state',
        'base_hook_policy': 'No-op; enter hooks return zero, which is not an admitted runtime observer ID',
        'engine_compilation': 'not_run', 'engine_execution': 'not_run',
        'native_service_or_lifetime_contract': 'not_verified',
    }


def origin_map(original: bytes, hooks: bytes | None = None) -> dict:
    """Byte-pinned template line origins; expansion columns remain unavailable."""
    _original(original)
    hook_bytes = _hooks(hooks)
    before, remaining = original.split(ANCHOR, 1)
    between, after = (ANCHOR + remaining).split(OLD, 1)
    rows = []
    def append(chunk, path, first, kind):
        for offset, unused in enumerate(chunk.splitlines()):
            rows.append({'instrumented_line': len(rows)+1, 'source': path,
                         'source_line': first+offset, 'kind': kind})
    append(before, str(SOURCE), 1, 'original_adapter')
    append(hook_bytes, str(HOOKS), 1, 'trusted_hook_definition')
    begin = before.count(b'\n') + 1
    append(between, str(SOURCE), begin, 'original_adapter')
    old_begin = begin + between.count(b'\n')
    opcode = 10
    for line in NEW.splitlines():
        if b'code == 11' in line: opcode = 11
        elif b'code == 12' in line: opcode = 12
        anchor = old_begin + (opcode-10)*2
        if b'm_ScreenRT' in line: anchor += 1
        rows.append({'instrumented_line': len(rows)+1, 'source': str(SOURCE),
                     'source_line': anchor, 'kind': 'trusted_opcode_observation_delta'})
    append(after, str(SOURCE), old_begin + OLD.count(b'\n'), 'original_adapter')
    value = instrument_adapter(original, hook_bytes)
    require(len(rows) == len(value.splitlines()), 'Instrumented source-map line coverage differs')
    return {'schema_version': 1, 'kind': 'trusted_unexpanded_template_origins',
            'original_sha256': digest(original), 'hooks_sha256': digest(hook_bytes),
            'instrumented_sha256': digest(value), 'columns': 'unavailable_after_placeholder_expansion',
            'origins': rows}


def _method(value: bytes, name: str) -> bytes:
    # The pinned source has no brace-bearing strings in these method bodies.
    matches = list(re.finditer(rb'^\t(?:protected |override )?(?:void|bool|ESPK_TabletState|SPK_ScreenRT|SPK_TabletUI) '
                              + name.encode() + rb'\([^\n]*\)\n\t\{', value, re.M))
    require(len(matches) == 1, 'Expected exact method declaration: ' + name)
    start = matches[0].start();opening = matches[0].end()-1;depth = 0
    for index in range(opening, len(value)):
        if value[index:index+1] == b'{': depth += 1
        elif value[index:index+1] == b'}':
            depth -= 1
            if depth == 0: return value[start:index+1]
    raise InstrumentationFailure('Unclosed pinned method')


def self_test() -> dict:
    original = _read_fixed(SOURCE);hooks = _read_fixed(HOOKS)
    value = instrument_adapter(original, hooks)
    cases = []
    def case(name, body, rejected=False):
        require(name in EXPECTED_CASE_IDS and not any(r['id'] == name for r in cases), 'Unknown/duplicate fixture identity')
        outcome = 'returned';detail = None
        try: body()
        except InstrumentationFailure as exc: outcome = 'rejected';detail = str(exc)
        cases.append({'id':name, 'status':'success' if (outcome == 'rejected') == rejected else 'failure',
                      'expected':'rejected' if rejected else 'returned', 'actual':outcome, 'detail':detail})
    case('positive.exact-strip', lambda: require(strip_instrumentation(value, hooks) == original, 'Exact reconstruction failed'))
    case('positive.native-call-counts', lambda: require(value.count(b'Enable(GetOwner())') == value.count(b'm_ScreenRT.Disable();') ==
         value.count(b'm_ScreenRT = new SPK_ScreenRT();') == 1 and value.count(b'GetOwner()') == original.count(b'GetOwner()'), 'Native call counts changed'))
    case('positive.local-results', lambda: require(NEW.index(b'EnableEnter()') < NEW.index(b'Enable(GetOwner())') < NEW.index(b'EnableExit(') and
         NEW.index(b'DisableEnter()') < NEW.index(b'm_ScreenRT.Disable();') < NEW.index(b'DisableExit(') and b'reply' not in NEW and b'm_BerylState' not in NEW, 'Invocation-local call/order contract differs'))
    case('positive.lifecycle-methods-unchanged', lambda: require(all(_method(value,n) == _method(original,n) for n in ('OnPostInit','EOnFrame','OnDelete')), 'Lifecycle methods changed'))
    case('positive.all-other-methods-unchanged', lambda: require(all(_method(value,n) == _method(original,n) for n in ('GetScreen','GetUI','GetState','Focus','Unfocus','SetHeld')), 'Other method changed'))
    case('positive.origin-map', lambda: require(origin_map(original,hooks)['origins'][-1]['instrumented_line'] == len(value.splitlines()), 'Origin map is partial'))
    case('positive.no-op-base', lambda: require(hooks.count(b'return 0;') == 2 and b'reply' not in hooks and b'GetOwner' not in hooks and b'm_ScreenRT' not in hooks, 'Base hook behavior changed'))
    mutations = (
        ('create-removed', value.replace(b'\t\t\t\tm_ScreenRT = new SPK_ScreenRT();\n', b'', 1)),
        ('create-duplicated', value.replace(b'm_ScreenRT = new SPK_ScreenRT();', b'm_ScreenRT = new SPK_ScreenRT(); m_ScreenRT = new SPK_ScreenRT();', 1)),
        ('create-hook-before-publication', value.replace(b'm_ScreenRT = new SPK_ScreenRT();\n\t\t\t\tBerylObserveScreenCreated();', b'BerylObserveScreenCreated();\n\t\t\t\tm_ScreenRT = new SPK_ScreenRT();', 1)),
        ('enable-removed', value.replace(b'bool berylScreenEnableReturned = m_ScreenRT.Enable(GetOwner());', b'bool berylScreenEnableReturned = false;', 1)),
        ('enable-duplicated', value.replace(b'm_ScreenRT.Enable(GetOwner());', b'm_ScreenRT.Enable(GetOwner()); m_ScreenRT.Enable(GetOwner());', 1)),
        ('enable-reply', value.replace(b'BerylObserveScreenEnableExit(berylScreenEnableInvocation, berylScreenEnableReturned);', b'BerylObserveScreenEnableExit(berylScreenEnableInvocation, berylScreenEnableReturned); if (berylScreenEnableReturned) reply = 1;', 1)),
        ('enable-hook-before-return', value.replace(b'bool berylScreenEnableReturned = m_ScreenRT.Enable(GetOwner());\n\t\t\t\tBerylObserveScreenEnableExit(berylScreenEnableInvocation, berylScreenEnableReturned);', b'BerylObserveScreenEnableExit(berylScreenEnableInvocation, false);\n\t\t\t\tbool berylScreenEnableReturned = m_ScreenRT.Enable(GetOwner());', 1)),
        ('enable-enter-after-call', value.replace(b'int berylScreenEnableInvocation = BerylObserveScreenEnableEnter();\n\t\t\t\tbool berylScreenEnableReturned = m_ScreenRT.Enable(GetOwner());', b'bool berylScreenEnableReturned = m_ScreenRT.Enable(GetOwner());\n\t\t\t\tint berylScreenEnableInvocation = BerylObserveScreenEnableEnter();', 1)),
        ('disable-removed', value.replace(b'\t\t\t\tm_ScreenRT.Disable();\n', b'', 1)),
        ('disable-duplicated', value.replace(b'm_ScreenRT.Disable();', b'm_ScreenRT.Disable(); m_ScreenRT.Disable();', 1)),
        ('disable-exit-before-return', value.replace(b'm_ScreenRT.Disable();\n\t\t\t\tBerylObserveScreenDisableExit(berylScreenDisableInvocation);', b'BerylObserveScreenDisableExit(berylScreenDisableInvocation);\n\t\t\t\tm_ScreenRT.Disable();', 1)),
        ('shared-slot', value.replace(b'int berylScreenEnableInvocation =', b'berylCurrentInvocation =', 1).replace(b'berylScreenEnableInvocation,', b'berylCurrentInvocation,', 1).replace(b'\tprotected ref SPK_ScreenRT m_ScreenRT;', b'\tprotected ref SPK_ScreenRT m_ScreenRT;\n\tprotected int berylCurrentInvocation;', 1)),
        ('extra-owner-read', value.replace(b'bool berylScreenEnableReturned =', b'IEntity berylExtraOwner = GetOwner(); bool berylScreenEnableReturned =', 1)),
        ('manual-callback', value.replace(b'BerylObserveScreenCreated();', b'BerylObserveScreenCreated(); OnPostInit(GetOwner());', 1)),
        ('other-init', value.replace(b'SetEventMask(owner, EntityEvent.FRAME);', b'SetEventMask(owner, EntityEvent.INIT);', 1)),
        ('other-frame', value.replace(b'RunOperation(4, false, timeSlice);', b'RunOperation(4, false, 0);', 1)),
        ('other-delete', value.replace(b'super.OnDelete(owner);', b'super.OnDelete(owner); m_UI.Close();', 1)),
    )
    for name, mutant in mutations:
        case('negative.' + name, lambda m=mutant: validate_instrumented(m, original, hooks), True)
    case('negative.hook-template-return', lambda: instrument_adapter(original,hooks.replace(b'return 0;',b'return 1;',1)), True)
    case('negative.hook-template-effect', lambda: instrument_adapter(original,hooks.replace(b'\t\treturn 0;',b'\t\tPrint("effect"); return 0;',1)), True)
    case('negative.original-identity', lambda: instrument_adapter(original+b'// changed\n',hooks), True)
    case('negative.hook-omitted', lambda: validate_instrumented(value.replace(hooks,b'',1),original,hooks), True)
    case('negative.hook-duplicated', lambda: validate_instrumented(value.replace(hooks,hooks+hooks,1),original,hooks), True)
    case('negative.delta-duplicated', lambda: validate_instrumented(value.replace(NEW,NEW+NEW,1),original,hooks), True)
    case('negative.nonbytes', lambda: instrument_adapter(original.decode(),hooks), True)
    case('negative.source-budget', lambda: instrument_adapter(b'x'*(MAX_SOURCE_BYTES+1),hooks), True)
    case('negative.source-crlf', lambda: instrument_adapter(original.replace(b'\n',b'\r\n'),hooks), True)
    require([r['id'] for r in cases] == list(EXPECTED_CASE_IDS), 'Exact expected fixture set/order differs')
    require(_read_fixed(SOURCE) == original and _read_fixed(HOOKS) == hooks, 'Source changed during pure fixtures')
    return {'schema_version':1,'operation':'tablet-real-services.instrumentation.source-fixtures',
            'status':'success' if all(r['status'] == 'success' for r in cases) else 'failure',
            'expected_case_ids':list(EXPECTED_CASE_IDS),'complete_expected_case_set':True,
            'cases':cases,'passed':sum(r['status'] == 'success' for r in cases),
            'failed':sum(r['status'] == 'failure' for r in cases),
            'source_admission':validate_instrumented(value,original,hooks),
            'scope':'Source reconstruction and exact-delta faults only; no compilation, engine, services, reentry or runtime observer',
            'instrumenter':{'path':str(Path(__file__)), 'sha256':digest(Path(__file__).read_bytes())}}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--self-test',action='store_true')
    args = parser.parse_args()
    if not args.self_test:
        parser.error('Only the source-only --self-test interface is installed here')
    work = Path(tempfile.mkdtemp(prefix='tablet-real-service-instrument-',dir=ROOT/'build'))
    result = {'schema_version':1,'operation':'tablet-real-services.instrumentation.source-fixtures','status':'failure','failure':None}
    try:
        instrumenter = _read_fixed(Path(__file__))
        result = self_test()
        original = _read_fixed(SOURCE);hooks = _read_fixed(HOOKS);value = instrument_adapter(original,hooks)
        retained = {'original.c.in':original, 'hooks.c.in':hooks, 'instrumented.c.in':value,
                    'origins.json':(json.dumps(origin_map(original,hooks),indent=2)+'\n').encode(),
                    'instrumenter.py':instrumenter}
        for name,data in retained.items():
            (work/name).write_bytes(data)
            require((work/name).read_bytes() == data, 'Retained source readback differs: '+name)
        result['retained_files'] = {name:{'bytes':len(data),'sha256':digest(data)} for name,data in retained.items()}
        require(result['instrumenter']['sha256'] == digest(instrumenter) and _read_fixed(Path(__file__)) == instrumenter,
                'Instrumenter changed during pure evidence')
        require(_read_fixed(SOURCE) == original and _read_fixed(HOOKS) == hooks, 'Source changed before evidence retention')
    except Exception as exc:
        result.update(status='failure',failure={'type':type(exc).__name__,'message':str(exc)})
    path = work/'result.json';path.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'path':str(path),'sha256':digest(path.read_bytes()),'status':result['status'],
                      'passed':result.get('passed',0),'failed':result.get('failed',0),'failure':result.get('failure')}))
    return 0 if result['status'] == 'success' else 1


if __name__ == '__main__':
    raise SystemExit(main())
