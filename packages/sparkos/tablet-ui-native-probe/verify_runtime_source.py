"""Source-only admission for the distinct tablet UI/native deletion RPC.

Bounded text checks and deliberate faults do not establish engine compilation,
callback execution, queue order/lifetime, deletion, UI correctness, or release.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[3]
PACKAGE = Path(__file__).resolve().parent
DRIVER = PACKAGE/'runtime-driver.c.in'
DRIVER_SHA256 = '215b697c93bedccbc30fefe4a054ec114e840672ba861db3f56e17728fc416fc'
MAX_BYTES = 65536
PROFILE = 'sparkos.tablet.ui-native.n1b-n3.source.v1'
STRING_FIELDS = ('token','action','status','failure','profile','source_contract_sha256','source_sha256','world_path','current_project','addon_world_path','world_absolute_path','resource_name','resource_path','resource_absolute_path')
BOOL_FIELDS = ('addon_world_resolved','world_path_resolved','resource_name_resolved','module_present','api_present','module_open_requested','module_open_accepted','load_accepted','world_matches','edit_mode','game_mode','in_play_mode','world_present','game_world_present','actions_ready','stop_requested','outside_domain','first_progress_ready','reopen_progress_ready','final_focused')
INT_FIELDS = ('schema_version','load_requested','load_submitted','load_entered','load_resumed','load_returned','phase','executed','failures','owner_count','row_count','checksum','raw_bytes','action_count','frame_count','queue_count','init_count','delete_count','presuper_count','after_super_count')
ARRAY_FIELDS = ('caseIds','rows')
FIELDS = STRING_FIELDS+BOOL_FIELDS+INT_FIELDS+ARRAY_FIELDS
PLACEHOLDERS = ('@TOKEN@','@SOURCE_SHA256@','@WORLD_ABSOLUTE@','@CURRENT_GAME_PROJECT@','@SOURCE_CONTRACT_SHA256@')
CASES = (
    'positive.frozen-driver','positive.typed-response','positive.native-world-and-factory',
    'positive.seven-separate-actions','positive.native-progress-windows','positive.scalar-prefix',
    'positive.actual-deletion-milestones','positive.source-only-scope',
    'positive.prefix-ordered-null-guards','positive.seal-prefix-before-fields',
    'positive.action-failure-snapshot','positive.stop-failure-snapshot',
    'negative.nonbytes','negative.byte-budget','negative.crlf','negative.unknown-placeholder',
    'negative.token-pin','negative.project-pin','negative.worker-project-pin','negative.world-guid',
    'negative.prefab-guid','negative.profile','negative.direct-init','negative.direct-frame',
    'negative.direct-delete','negative.native-delete-api','negative.component-constructor',
    'negative.profile-save','negative.queue-tick','negative.frame-mask-write','negative.frame-flags-write',
    'negative.extra-yield','negative.second-worker','negative.extra-spawn','negative.spawn-world',
    'negative.claim-owner','negative.claim-component','negative.claim-init-count',
    'negative.repeat-action','negative.marker-after-call','negative.first-window-bypass',
    'negative.reopen-window-bypass','negative.run-direct-public-action','negative.complete-case-count',
    'negative.mutable-frozen-array','negative.scalar-checksum','negative.prefix-row-check',
    'negative.prefix-frame-check','negative.prefix-queue-check','negative.init-count-change',
    'negative.outside-domain-before-validation','negative.outside-domain-success',
    'negative.final-live-ready','negative.stop-prefix-after-switch','negative.capture-after-switch',
    'negative.post-stop-live-ready','negative.post-stop-widget-read','negative.post-stop-owner-read',
    'negative.phase-complete-before-edit','negative.phase-complete-in-play','negative.delete-count-one',
    'negative.presuper-count-one','negative.after-super-count-one','negative.after-super-seal-omitted',
    'negative.terminal-mode-recheck','negative.terminal-prefix-recheck','negative.duplicate-regv',
    'negative.missing-regv','negative.response-type','negative.old-n1a-envelope',
    'negative.unpinned-whitespace',
    'negative.prefix-null-before-read','negative.prefix-current-null-before-read',
    'negative.prefix-ordered-guard-swap','negative.prefix-guard-effect',
    'negative.seal-null-before-read','negative.seal-ordered-guard-swap',
    'negative.prefix-long-formula','negative.seal-long-formula',
    'negative.action-missing-progress','negative.action-progress-after-generic',
    'negative.action-overwrite-primary','negative.action-failure-as-success',
    'negative.stop-missing-progress','negative.stop-progress-after-generic',
    'negative.stop-overwrite-primary','negative.stop-failure-as-success',
)


class SourceFailure(ValueError):
    pass


def require(condition, message):
    if not condition: raise SourceFailure(message)


def sha(value):
    return hashlib.sha256(value).hexdigest()


def read(path):
    path = Path(path)
    require(path.is_file() and not path.is_symlink(), 'Regular source required')
    with path.open('rb') as stream: value = stream.read(MAX_BYTES+1)
    require(len(value) <= MAX_BYTES, 'Source byte budget exceeded')
    return value


def mask(text):
    return re.sub(r'//[^\n]*|/\*[\s\S]*?\*/|"(?:\\.|[^"\\])*"', lambda m: ''.join('\n' if c == '\n' else ' ' for c in m[0]), text)


def block(text, start):
    code = mask(text); depth = 0
    for index in range(start, len(code)):
        if code[index] == '{': depth += 1
        elif code[index] == '}':
            depth -= 1
            if depth == 0: return text[start+1:index]
    raise SourceFailure('Unbalanced source braces')


def body(text, name):
    matches = list(re.finditer(r'(?m)^\s*(?:(?:override|protected|static)\s+)*[A-Za-z_][A-Za-z0-9_]*\s+'+re.escape(name)+r'\s*\([^;{}]*\)\s*\{', mask(text)))
    require(len(matches) == 1, 'Exactly one method required: '+name)
    return block(text, matches[0].end()-1)


def has(text, needle, detail):
    require(needle in text, detail)


def ordered(text, needles, detail):
    start = -1
    for needle in needles:
        start = text.find(needle, start+1)
        require(start >= 0, detail)


def receipt_guard_contract(text):
    # These fields/order are the original OR operands. Null checks precede any
    # dereference, and the seal's prefix check precedes every exact field read.
    # One guard per operand avoids Enforce's demonstrated formula-size limit.
    prefix_guards = (
        '!prefix', '!current', 'current.row_count < prefix.row_count',
        'current.owner_count != prefix.owner_count', 'current.init_count != prefix.init_count',
        'current.action_count < prefix.action_count', 'current.frame_count < prefix.frame_count',
        'current.queue_count < prefix.queue_count', 'current.delete_count < prefix.delete_count',
        'current.presuper_count < prefix.presuper_count',
        'current.after_super_count < prefix.after_super_count',
        '(prefix.first_progress_ready && !current.first_progress_ready) || (prefix.reopen_progress_ready && !current.reopen_progress_ready)',
    )
    seal_guards = ('!PreservesPrefix(a, b)',) + tuple('a.'+name+' != b.'+name for name in (
        'row_count', 'checksum', 'bytes', 'action_count', 'frame_count', 'queue_count',
        'delete_count', 'presuper_count', 'after_super_count', 'first_progress_ready',
        'reopen_progress_ready', 'final_focused'))
    prefix_expected = ''.join('if ('+guard+') return false;' for guard in prefix_guards)
    prefix_expected += 'for (int i = 0; i < prefix.row_count; i++) if (prefix.rows[i] != current.rows[i]) return false; return true;'
    seal_expected = ''.join('if ('+guard+') return false;' for guard in seal_guards) + 'return true;'
    compact = lambda value: re.sub(r'\s+', '', mask(value))
    require(compact(body(text, 'PreservesPrefix')) == compact(prefix_expected),
            'Prefix guards must preserve original operand order, null-before-read, and effect-free row comparison')
    require(compact(body(text, 'SameSealedReceipt')) == compact(seal_expected),
            'Sealed receipt guards must check prefix before fields and preserve original operand order without effects')


def readiness_failure_contract(text):
    # Diagnostic capture precedes fallback text, uses the existing scalar
    # validator/publication path, and preserves a nonempty primary failure.
    # Exact failure-only bodies prohibit added engine/service effects.
    request = body(text, 'GetResponse')
    contracts = (
        ('if (!SPK_BerylTabletUINativeRegistry.LiveReady())',
         'UI action lost native owner/world/component/input/init readiness'),
        ('if (s_TraceFailure != "" || !SPK_BerylTabletUINativeRegistry.FinalReady())',
         'UI stop requires the actual final focused/independent live state'),
    )
    compact = lambda value: re.sub(r'\s+', '', value)
    for guard, message in contracts:
        require(request.count(guard) == 1, 'Exact original readiness guard required')
        start = request.index('{', request.index(guard)+len(guard))
        actual = block(request, start)
        expected = ('Progress(resp); if (s_TraceFailure == "") s_TraceFailure = "'+message+'"; '
                    'FailureResponse(resp); return resp;')
        require(compact(actual) == compact(expected),
                'Readiness failure must preserve validated scalar snapshot and primary failure before generic fallback')


def validate_source(value, *, pin=True):
    require(type(value) is bytes, 'Literal source bytes required')
    require(0 < len(value) <= MAX_BYTES, 'Source byte budget exceeded')
    require(b'\r' not in value and b'\0' not in value, 'LF source without NUL required')
    try: text = value.decode('utf8')
    except UnicodeError as exc: raise SourceFailure('Invalid UTF-8') from exc
    require(set(re.findall(r'@[A-Z0-9_]+@', text)) == set(PLACEHOLDERS), 'Unknown/missing installed placeholder')
    code = mask(text)
    forbidden = r'\b(?:OnPostInit|EOnFrame|OnDelete|DeleteEntity|DeleteEntityAndChildren|Destroy|Focus|Unfocus|SetHeld|Open|Close|Enable|Disable|SetEventMask|SetFlags|Save|SaveProfile|Tick|CallLater|CreateUserBinding|AddBinding)\s*\('
    require(not re.search(forbidden, code), 'Transport adds direct lifecycle/service/input/profile/queue mutation')
    require(not re.search(r'\bnew\s+SPK_(?:TabletComponent|BerylTabletUINativeObserver)\b', code), 'Manual component construction')
    require(len(re.findall(r'\bSpawnEntityPrefab\s*\(', code)) == 1, 'Exactly one two-owner factory site required')
    require(len(re.findall(r'\bRunAction\s*\(', code)) == 1, 'Exactly one fixed-index public-action group site required')
    require(len(re.findall(r'\bSleep\s*\(', code)) == 1 and 'Sleep(200);' in text, 'Only original fixed deferred load yield permitted')
    require(len(re.findall(r'\bthread\b', code)) == 1, 'Only one installed deferred world worker permitted')
    worker = body(text, 'Beryl_OpenTabletUINativeWorld')
    ordered(worker, ['Sleep(200);','workerProject != "@CURRENT_GAME_PROJECT@"','WorldEditor editor = Workbench.GetModule(WorldEditor);','normalizedWorld != "@WORLD_ABSOLUTE@"','registered != "{BE71572A20261010}worlds/BerylTabletUINative.ent"','editor.SetOpenedResource(absoluteWorld)'], 'Deferred world project/native resource/mode gates changed')
    request = body(text, 'GetResponse')
    ordered(request, ['req.token != resp.token','resp.current_project = Workbench.GetCurrentGameProjectFile();','projectPath != "@CURRENT_GAME_PROJECT@"','req.action == "load"'], 'Native token/base-project request gates changed')
    has(request, 'resp.profile = "'+PROFILE+'";', 'Distinct UI profile required')
    has(request, 'resp.source_contract_sha256 = "@SOURCE_CONTRACT_SHA256@";', 'Caller-pinned frozen UI contract required')
    for action in ('load','status','play','spawn','run0','run1','run2','run3','run4','run5','run6','stop'):
        has(request, 'req.action != "'+action+'"', 'Unknown native action guard changed')
    has(request, 'Resource.Load("{BE71572B20261010}Prefabs/BerylTabletUINative.et")', 'Owned UI prefab GUID differs')
    has(request, 'for (int i = 1; i <= 2; i++)', 'Two-owner factory bound differs')
    has(request, 'IEntity owner = GetGame().SpawnEntityPrefab(prefab, runtimeWorld, null);', 'Native factory must use current Game world')
    ordered(request, ['SPK_BerylTabletUINativeRegistry.s_Observers.Count() != i','SPK_BerylTabletUINativeRegistry.s_InitCount != i * 2','SPK_BerylTabletUINativeRegistry.s_Owners[i - 1] != owner','owner.FindComponent(SPK_BerylTabletUINativeObserver) != SPK_BerylTabletUINativeRegistry.s_Observers[i - 1]'], 'Native claim counts must precede indexed owner/component checks')
    run = request[request.index('if (index >= 0)'):request.index('if (req.action == "stop")')]
    has(run, 'index != s_RequestedActions', 'Public action order/replay guard missing')
    has(run, '(index == 2 && !s_Last.first_progress_ready)', 'First native progress window missing')
    has(run, '(index == 5 && !s_Last.reopen_progress_ready)', 'Reopen native progress window missing')
    ordered(run, ['s_RequestedActions++;','SPK_BerylTabletUINativeRegistry.LiveReady()','SPK_BerylTabletUINativeRegistry.RunAction(index);','SPK_BerylTabletUINativeRegistry.Capture();','AcceptCapture(actionCapture)','actionCapture.action_count != s_RequestedActions'], 'One-shot marker, live precondition, action and scalar receipt order changed')
    indices = body(text, 'ActionIndex')
    for index in range(7): has(indices, 'if (action == "run'+str(index)+'") return '+str(index)+';', 'Only fixed RunAction indices admitted')
    clone = body(text, 'CopyReceipt')
    has(clone, 'foreach (string row : source.rows) result.rows.Insert(row);', 'Independent immutable scalar prefix copy missing')
    require(not re.search(r'result\.rows\s*=', mask(clone)), 'Frozen prefix aliases mutable row array')
    scalar = body(text, 'ValidScalarReceipt')
    for needle in ('capture.owner_count != 2','capture.init_count != 4','capture.action_count > 7','capture.frame_count > 2048','capture.queue_count > 64','capture.row_count > 12288','capture.bytes > 8388608','row.Length() > 1024','checksum == capture.checksum && bytes == capture.bytes'):
        has(scalar, needle, 'Bounded raw scalar trace validation changed')
    prefix = body(text, 'PreservesPrefix')
    receipt_guard_contract(text)
    readiness_failure_contract(text)
    for needle in ('current.init_count != prefix.init_count','current.frame_count < prefix.frame_count','current.queue_count < prefix.queue_count','prefix.rows[i] != current.rows[i]','current.after_super_count < prefix.after_super_count'):
        has(prefix, needle, 'Append-only native observation prefix changed')
    accepted = body(text, 'AcceptCapture')
    require(mask(accepted).find('current.outside_domain') > mask(accepted).find('ValidScalarReceipt(current)'), 'Unavailable classification cannot bypass structural validation')
    ordered(accepted, ['ValidScalarReceipt(current)','PreservesPrefix(s_Last, current)','PreservesPrefix(s_StopPrefix, current)','SameSealedReceipt(s_Final, current)','s_Last = CopyReceipt(current);','current.failure != "" || current.outside_domain','s_OutsideDomain = current.outside_domain;'], 'Structure and prefix must be checked before unavailable classification')
    sealed = body(text, 'SameSealedReceipt')
    has(sealed, 'a.after_super_count != b.after_super_count', 'Terminal native superclass-return milestone count must be sealed')
    stop = request[request.index('if (req.action == "stop")'):request.index('if (s_Phase == 0 && resp.world_matches')]
    ordered(stop, ['s_RequestedActions != 7','SPK_BerylTabletUINativeRegistry.FinalReady()','SPK_BerylTabletUINativeRegistry.Capture();','stopCapture.action_count != 7','s_StopPrefix = CopyReceipt(stopCapture);','s_StopRequested = true; s_Phase = 3;','editor.SwitchToEditMode();','return resp;'], 'Stop requires seven actions, actual focused live state and pre-handoff scalar prefix')
    after = stop[stop.index('editor.SwitchToEditMode();'):]
    require(not re.search(r'\b(?:Capture|LiveReady|FinalReady|GetOwner|GetWorld|GetUI|GetRoot|GetScreen|GetWidget)\s*\(', mask(after)), 'Stop performs native/object reads after requesting destruction')
    progress = body(text, 'Progress')
    require(not re.search(r'\b(?:LiveReady|FinalReady|GetOwner|GetWorld|GetUI|GetRoot|GetScreen|GetWidget|Snapshot|GetState)\s*\(', mask(progress)), 'Post-stop progress follows native object references')
    require(not re.search(r's_(?:Owners|Observers)\s*\[', mask(progress)), 'Post-stop progress indexes retained owners/components')
    ordered(progress, ['SPK_BerylTabletUINativeRegistry.Capture();','AcceptCapture(current)','s_Phase == 3 && resp.edit_mode && !resp.game_mode && !resp.in_play_mode','current.action_count == 7','current.delete_count == 2','current.presuper_count == 2','current.after_super_count == 2','s_Final = CopyReceipt(current);','s_Phase = 4;','resp.status = "complete";'], 'Complete requires fresh edit/no-play observations and actual two-owner native deletion milestones')
    has(progress, 's_Phase == 4 && (!resp.edit_mode || resp.game_mode || resp.in_play_mode || !resp.world_matches || !resp.world_present)', 'Terminal mode/world must be rechecked')
    failure = body(text, 'FailureResponse')
    has(failure, 'if (s_OutsideDomain) resp.status = "unavailable";', 'Actual unavailable branch cannot become success')
    require('frame_counts' not in code and 'init_rows' not in code and 'wire_contract_sha256' not in code, 'Distinct UI transcript cannot reuse the fixed N1a codec envelope')
    response = re.search(r'class BerylTabletUINativeResponse : JsonApiStruct\s*\{', code)
    require(response is not None, 'Typed response class missing')
    response_text = block(text, response.end()-1)
    declaration = response_text[:response_text.index('void BerylTabletUINativeResponse()')]
    actual = []; kinds = {}
    for kind, names in re.findall(r'(?m)^\s*(string|bool|int)\s+([^;]+);', declaration):
        for name in names.split(','):
            name = name.strip(); actual.append(name); kinds[name] = kind
    actual.extend(re.findall(r'(?m)^\s*ref array<string>\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*\{\};', declaration))
    require(tuple(actual) == FIELDS, 'Typed response fields/order differ')
    require(all(kinds[n] == 'string' for n in STRING_FIELDS) and all(kinds[n] == 'bool' for n in BOOL_FIELDS) and all(kinds[n] == 'int' for n in INT_FIELDS), 'Typed response scalar types differ')
    registered = re.findall(r'RegV\("([A-Za-z_][A-Za-z0-9_]*)"\)', response_text)
    require(len(registered) == len(FIELDS) and len(set(registered)) == len(FIELDS) and set(registered) == set(FIELDS), 'Exactly one RegV per typed response field required')
    require(tuple(re.findall(r'RegV\("([A-Za-z_][A-Za-z0-9_]*)"\)', body(text,'BerylTabletUINativeRequest'))) == ('token','action'), 'Request registration differs')
    if pin: require(sha(value) == DRIVER_SHA256, 'Driver differs from reviewed frozen bytes')
    return {'status':'success','bytes':len(value),'sha256':sha(value),'fields':list(FIELDS),'string_fields':list(STRING_FIELDS),'bool_fields':list(BOOL_FIELDS),'int_fields':list(INT_FIELDS),'array_fields':list(ARRAY_FIELDS),'placeholders':list(PLACEHOLDERS),'scope':'source_only_not_execution'}


def self_test():
    data = read(DRIVER); text = data.decode('utf8'); checked = validate_source(data); results = []
    for case in CASES[:12]: results.append({'case_id':case,'status':'success','source_obligations':'validated_frozen_source_only'})
    def reject(case, candidate, pin=False):
        try: validate_source(candidate,pin=pin)
        except SourceFailure as exc: results.append({'case_id':case,'status':'success','rejection':str(exc)})
        else: results.append({'case_id':case,'status':'failure','error':'Deliberate source fault accepted'})
    def mutant(case, before, after):
        require(before in text and before != after, 'Invalid mutation selector: '+case)
        reject(case,text.replace(before,after,1).encode('utf8'))
    reject('negative.nonbytes',text); reject('negative.byte-budget',b'x'*(MAX_BYTES+1)); reject('negative.crlf',data.replace(b'\n',b'\r\n'))
    faults = (
        ('negative.unknown-placeholder','@TOKEN@','@UNKNOWN@'),
        ('negative.token-pin','req.token != resp.token','req.token == resp.token'),
        ('negative.project-pin','projectPath != "@CURRENT_GAME_PROJECT@"','projectPath == "@CURRENT_GAME_PROJECT@"'),
        ('negative.worker-project-pin','workerProject != "@CURRENT_GAME_PROJECT@"','workerProject == "@CURRENT_GAME_PROJECT@"'),
        ('negative.world-guid','{BE71572A20261010}','{BE71571A20261010}'),
        ('negative.prefab-guid','{BE71572B20261010}','{BE71571B20261010}'),
        ('negative.profile',PROFILE,'sparkos.tablet.real-services.n1a.wire.v1'),
        ('negative.direct-init','s_Phase = 2;','s_Phase = 2; observer.OnPostInit(owner);'),
        ('negative.direct-frame','s_Phase = 2;','s_Phase = 2; observer.EOnFrame(owner,0.1);'),
        ('negative.direct-delete','s_Phase = 2;','s_Phase = 2; observer.OnDelete(owner);'),
        ('negative.native-delete-api','s_Phase = 2;','s_Phase = 2; DeleteEntityAndChildren(owner);'),
        ('negative.component-constructor','s_Phase = 2;','s_Phase = 2; new SPK_TabletComponent();'),
        ('negative.profile-save','s_Phase = 2;','s_Phase = 2; SaveProfile();'),
        ('negative.queue-tick','s_Phase = 2;','s_Phase = 2; GetGame().GetCallqueue().Tick(1);'),
        ('negative.frame-mask-write','s_Phase = 2;','s_Phase = 2; observer.SetEventMask(owner,0);'),
        ('negative.frame-flags-write','s_Phase = 2;','s_Phase = 2; owner.SetFlags(EntityFlags.ACTIVE,false);'),
        ('negative.extra-yield','Sleep(200);','Sleep(200); Sleep(1);'),
        ('negative.second-worker','thread Beryl_OpenTabletUINativeWorld();','thread Beryl_OpenTabletUINativeWorld(); thread Beryl_OpenTabletUINativeWorld();'),
        ('negative.extra-spawn','IEntity owner = GetGame().SpawnEntityPrefab(prefab, runtimeWorld, null);','IEntity owner = GetGame().SpawnEntityPrefab(prefab, runtimeWorld, null); GetGame().SpawnEntityPrefab(prefab,runtimeWorld,null);'),
        ('negative.spawn-world','SpawnEntityPrefab(prefab, runtimeWorld, null)','SpawnEntityPrefab(prefab,null,null)'),
        ('negative.claim-owner','s_Owners[i - 1] != owner','s_Owners[i - 1] == owner'),
        ('negative.claim-component','owner.FindComponent(SPK_BerylTabletUINativeObserver) != SPK_BerylTabletUINativeRegistry.s_Observers[i - 1]','owner.FindComponent(SPK_BerylTabletUINativeObserver) == SPK_BerylTabletUINativeRegistry.s_Observers[i - 1]'),
        ('negative.claim-init-count','s_InitCount != i * 2','s_InitCount == i * 2'),
        ('negative.repeat-action','index != s_RequestedActions','index == s_RequestedActions'),
        ('negative.marker-after-call','s_RequestedActions++;','s_RequestedActions--;'),
        ('negative.first-window-bypass','(index == 2 && !s_Last.first_progress_ready)','(index == 2 && false)'),
        ('negative.reopen-window-bypass','(index == 5 && !s_Last.reopen_progress_ready)','(index == 5 && false)'),
        ('negative.run-direct-public-action','RunAction(index);','RunAction(index); observer.Focus();'),
        ('negative.complete-case-count','s_RequestedActions != 7','s_RequestedActions != 6'),
        ('negative.mutable-frozen-array','foreach (string row : source.rows) result.rows.Insert(row);','result.rows = source.rows;'),
        ('negative.scalar-checksum','checksum == capture.checksum && bytes == capture.bytes','true'),
        ('negative.prefix-row-check','prefix.rows[i] != current.rows[i]','false'),
        ('negative.prefix-frame-check','current.frame_count < prefix.frame_count','false'),
        ('negative.prefix-queue-check','current.queue_count < prefix.queue_count','false'),
        ('negative.init-count-change','current.init_count != prefix.init_count','false'),
        ('negative.outside-domain-before-validation','if (!ValidScalarReceipt(current)','if (current.outside_domain) return true;\n        if (!ValidScalarReceipt(current)'),
        ('negative.outside-domain-success','if (s_OutsideDomain) resp.status = "unavailable";','if (s_OutsideDomain) resp.status = "complete";'),
        ('negative.final-live-ready','!SPK_BerylTabletUINativeRegistry.FinalReady()','false'),
        ('negative.stop-prefix-after-switch','s_StopPrefix = CopyReceipt(stopCapture);','s_StopPrefix = null;'),
        ('negative.capture-after-switch','editor.SwitchToEditMode();','editor.SwitchToEditMode(); SPK_BerylTabletUINativeRegistry.Capture();'),
        ('negative.post-stop-live-ready','resp.phase = s_Phase; resp.stop_requested = s_StopRequested;','resp.phase = s_Phase; resp.stop_requested = s_StopRequested; SPK_BerylTabletUINativeRegistry.LiveReady();'),
        ('negative.post-stop-widget-read','resp.phase = s_Phase; resp.stop_requested = s_StopRequested;','resp.phase = s_Phase; resp.stop_requested = s_StopRequested; ui.GetRoot();'),
        ('negative.post-stop-owner-read','resp.phase = s_Phase; resp.stop_requested = s_StopRequested;','resp.phase = s_Phase; resp.stop_requested = s_StopRequested; SPK_BerylTabletUINativeRegistry.s_Owners[0].GetWorld();'),
        ('negative.phase-complete-before-edit','s_Phase == 3 && resp.edit_mode && !resp.game_mode && !resp.in_play_mode','s_Phase == 2 && resp.edit_mode && !resp.game_mode && !resp.in_play_mode'),
        ('negative.phase-complete-in-play','s_Phase == 3 && resp.edit_mode && !resp.game_mode && !resp.in_play_mode','s_Phase == 3 && resp.edit_mode && resp.game_mode && resp.in_play_mode'),
        ('negative.delete-count-one','current.delete_count == 2','current.delete_count == 1'),
        ('negative.presuper-count-one','current.presuper_count == 2','current.presuper_count == 1'),
        ('negative.after-super-count-one','current.after_super_count == 2','current.after_super_count == 1'),
        ('negative.after-super-seal-omitted','a.after_super_count != b.after_super_count','false'),
        ('negative.terminal-mode-recheck','s_Phase == 4 && (!resp.edit_mode || resp.game_mode || resp.in_play_mode || !resp.world_matches || !resp.world_present)','s_Phase == 4 && false'),
        ('negative.terminal-prefix-recheck','SameSealedReceipt(s_Final, current)','true'),
        ('negative.duplicate-regv','RegV("after_super_count");','RegV("after_super_count"); RegV("after_super_count");'),
        ('negative.missing-regv','RegV("after_super_count");',''),
        ('negative.response-type','bool first_progress_ready, reopen_progress_ready, final_focused;','int first_progress_ready, reopen_progress_ready, final_focused;'),
        ('negative.old-n1a-envelope','ref array<string> rows = {};','ref array<string> rows = {}; ref array<string> init_rows = {};'),
    )
    for fault in faults: mutant(*fault)
    reject('negative.unpinned-whitespace',data+b'\n',pin=True)
    guard_faults = (
        ('negative.prefix-null-before-read',
         'if (!prefix) return false;',
         'if (current.row_count < prefix.row_count) return false;\n        if (!prefix) return false;'),
        ('negative.prefix-current-null-before-read',
         'if (!current) return false;',
         'if (current.row_count < prefix.row_count) return false;\n        if (!current) return false;'),
        ('negative.prefix-ordered-guard-swap',
         'if (current.row_count < prefix.row_count) return false;\n        if (current.owner_count != prefix.owner_count) return false;',
         'if (current.owner_count != prefix.owner_count) return false;\n        if (current.row_count < prefix.row_count) return false;'),
        ('negative.prefix-guard-effect',
         'if (!prefix) return false;',
         'if (!prefix) return false;\n        GetGame();'),
        ('negative.seal-null-before-read',
         'if (!PreservesPrefix(a, b)) return false;',
         'if (a.row_count != b.row_count) return false;\n        if (!PreservesPrefix(a, b)) return false;'),
        ('negative.seal-ordered-guard-swap',
         'if (a.row_count != b.row_count) return false;\n        if (a.checksum != b.checksum) return false;',
         'if (a.checksum != b.checksum) return false;\n        if (a.row_count != b.row_count) return false;'),
        ('negative.prefix-long-formula',
         'if (!prefix) return false;\n        if (!current) return false;',
         'if (!prefix || !current) return false;'),
        ('negative.seal-long-formula',
         'if (!PreservesPrefix(a, b)) return false;\n        if (a.row_count != b.row_count) return false;',
         'if (!PreservesPrefix(a, b) || a.row_count != b.row_count) return false;'),
    )
    for fault in guard_faults: mutant(*fault)
    diagnostic_faults = []
    for family, message in (
        ('action', 'UI action lost native owner/world/component/input/init readiness'),
        ('stop', 'UI stop requires the actual final focused/independent live state'),
    ):
        fallback = 'if (s_TraceFailure == "") s_TraceFailure = "'+message+'";'
        section = ('Progress(resp);\n                '+fallback+'\n                '
                   'FailureResponse(resp); return resp;')
        diagnostic_faults.extend((
            ('negative.'+family+'-missing-progress', section,
             fallback+'\n                FailureResponse(resp); return resp;'),
            ('negative.'+family+'-progress-after-generic', section,
             fallback+'\n                Progress(resp);\n                FailureResponse(resp); return resp;'),
            ('negative.'+family+'-overwrite-primary', section,
             section.replace('if (s_TraceFailure == "") ', '')),
            ('negative.'+family+'-failure-as-success', section,
             section.replace('FailureResponse(resp);', 'resp.status = "complete";')),
        ))
    for fault in diagnostic_faults: mutant(*fault)
    require(tuple(item['case_id'] for item in results) == CASES, 'Expected source case set changed')
    failures = sum(item['status'] != 'success' for item in results)
    directory = Path(tempfile.mkdtemp(prefix='tablet-ui-native-runtime-source-',dir=ROOT/'build'))
    receipt = {'schema_version':1,'operation':'tablet_ui_native_runtime_source_self_test','status':'success' if failures == 0 else 'failure','executed':len(results),'failures':failures,'caseIds':list(CASES),'source':{'path':str(DRIVER),'bytes':len(data),'sha256':sha(data)},'checker':{'path':str(Path(__file__).resolve()),'sha256':sha(read(Path(__file__)))},'scope':'source_only_not_engine_execution','engine_compilation':'not_run','native_ui':'not_run','native_destruction':'not_run','response_contract':checked,'results':results}
    result = directory/'result.json'; result.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'result':str(result),'status':receipt['status'],'executed':len(results),'failures':failures,'sha256':sha(result.read_bytes())}))
    return int(failures != 0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--self-test',action='store_true'); parser.add_argument('--check-source',type=Path)
    args = parser.parse_args()
    if args.self_test: return self_test()
    if args.check_source:
        print(json.dumps(validate_source(read(args.check_source)),sort_keys=True)); return 0
    parser.error('Select --self-test or --check-source')


if __name__ == '__main__': raise SystemExit(main())
