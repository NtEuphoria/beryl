# P5 tablet lifecycle: scalar continuation prototype

Checkpoint: 2026-10-08. This packet implements an isolated decision protocol and
fixtures. It does not complete P5, generate a production tablet, establish engine
retention/authority contracts, or promote any MESH files. The compiler, runtime,
mod orchestrator and retained/live MESH sources are not modified by this packet.

## Objective and exact scope

Separate Beryl-authored state decisions from handwritten reviewed service seams
without changing the existing synchronous call order. A persistent record stores
only `mode: i32` and `telemetry_accumulator: f32`. Modes 0, 1 and 2 represent STOWED,
HELD and FOCUSED. UI, widget, screen, entity, input and world identities remain in
the host, outside Beryl value copying.

Each invocation owns `Operation { kind, pc, screen_pc, held, time_slice, answer }`.
Kinds 0 through 5 select post-init, focus, unfocus, held-state change, frame and
delete respectively. The operation has no engine references and no shared active
continuation. `next(inout state, inout operation, reply)` executes plain scalar
decisions until it yields exactly one opcode or finishes. It is not a batch of
effects or an asynchronous coroutine scheduler.

The fixture host executes each yielded service immediately. If a scripted
service reenters tablet logic, the nested invocation gets a fresh operation and
shares the authoritative current state. Once it returns, the original operation
resumes with its own program counter intact. No rollback, lock, rejection,
deferred action list or final-state commit is added.

Presence opcodes represent direct host field reads at the original source points.
They are not additional engine method calls and do not admit reentry. Observed
service opcodes can reenter in fixtures. No source evidence proves the real engine
services non-reentrant; these adversarial fixtures preserve the original decision
behavior without asserting that the engine actually produces every interleaving.

## Opcode and host contract

| Opcode | Host operation | Reply |
|---|---|---|
| 0 | Invocation complete; inspect its `answer` | None |
| 1 | Read existing UI-reference presence | 0 or 1 |
| 2 | Construct/retain UI service | 0 |
| 3 | Call UI.Open synchronously | 0 or 1 |
| 4 | Find input component at the existing point | 0 or 1 |
| 5 | UI.SetInput using that input reference | 0 |
| 6 | Input.GetKeybinds | 0; host retains returned reference |
| 7 | UI.SetKeybinds using that returned reference | 0 |
| 8 | Existing missing-input diagnostic | 0 |
| 9 | Read existing screen-reference presence | 0 or 1 |
| 10 | Construct/retain screen service | 0 |
| 11 | Screen.Enable using the current owner | 0 or 1, intentionally ignored |
| 12 | Screen.Disable | 0 |
| 13 | UI.Close | 0 |
| 14 | Superclass post-init | 0 |
| 15 | Register FRAME event mask | 0 |
| 16 | UI.UpdateMarkers | 0; returned count intentionally ignored |
| 17 | UI.RefreshTelemetry | 0 |
| 18 | Screen.Destroy | 0 |
| 19 | Superclass delete | 0 |

The protocol uses scalar replies only. Their underlying input/keybind references
belong to each host invocation, not to one global reply slot. A production adapter
must preserve this distinction under reentry; the present fixture models those
services using stable tokens and scripted responses rather than real objects.

The host rejects unknown operations/opcodes, invalid reply domains and incomplete,
extra or out-of-order transcript records. `next` alone is not an untrusted-input
validator: arbitrary operation kinds/PCs and nonfinite numbers are outside this
fixture's admission. Internal counters never authorize an engine action.

## State and service commit points

Post-init calls superclass first, writes STOWED, then registers FRAME. It does
not reset the accumulator and does not synchronize an existing screen.

Focus rejects any initial state other than HELD. It retains a newly created UI
even if Open later fails. Without intervening reentry, failed Open leaves state
HELD and performs no input hookup or screen synchronization. If Open reenters
and changes mode, failure preserves those changes; it does not restore HELD or
commit FOCUSED. The current corpus tests failed opening and successful-opening
reentry separately; their combined false-return case is not recorded as executed.
A constructed widget tree with a missing map
still counts as successful Open. SetInput, GetKeybinds and SetKeybinds precede the
FOCUSED commit. Screen disabling follows that commit. A missing input logs the
existing diagnostic and still permits focus.

Unfocus rejects any initial state other than FOCUSED. Close observes FOCUSED.
Only after it returns does the component write HELD and synchronize the screen.

SetHeld(true) changes STOWED to HELD and always synchronizes, including repeated
calls in HELD or FOCUSED. SetHeld(false) first performs the admitted Unfocus
sequence, including transient HELD and screen enabling, then writes STOWED and
synchronizes again. Screen-enable failure is ignored by the existing component;
it does not roll back mode or suppress later calls.

Frame evaluates its state/UI guard once. It calls markers before the binary32
addition. Values below 0.25 return; otherwise it writes positive zero and calls
telemetry exactly once. Large timesteps do not catch up, remainder is discarded,
zero and negative timesteps receive the original behavior, and close/reopen does
not reset accumulation. If markers reenter and change mode, the original frame
still performs its addition and eligible refresh after the service returns.

Delete closes an existing UI, destroys an existing screen, then calls superclass.
It does not explicitly reset mode, accumulator, UI reference or screen reference.
The scripted screen-destroy service separately models its Disable-before-removal
contract; this is not proof of real widget/entity lifetime behavior.

Gadget orchestration is fixture-host code only. It preserves superclass-before-
local-owner checks, held-before-focus and population only after successful focus.
Repeated activation while FOCUSED does not repopulate. Remote/missing-controller/
missing-tablet branches remain separate from server authority. No public generated
gadget or multiplayer guarantee is introduced.

## Preserved source discrepancy and service limitations

Fresh Focus calls UI.Open before SetKeybinds. BuildWidgets constructs Chrome with
the UI's existing keybind reference, while SetKeybinds only assigns that reference.
Chrome.AddHint materializes `?` for null bindings. The fixture therefore expects
the first open to retain `?` hints and a subsequent rebuilt tree to use the retained
bindings. This packet does not repair that ordering. Any hint-refresh repair needs
its own reviewed before/after contract and checks.

The service fixture records declared 500 ms root-size and 400 ms terrain work in
their enqueue order. It does not execute queued callbacks or simulate engine
layout timing. Close preserves those queue declarations and retained service
fields. Bound-method receiver retention, removed-widget validity, close/reopen
delivery and teardown require real engine evidence before a production adapter
can choose a cancellation or lifecycle policy.

## Independent verification and fixtures

`oracle.py` transcribes the original decisions directly, without invoking the
continuation evaluator. `protocol_model.py` is the scheduling model of the Beryl
protocol and is explicitly not an independent language oracle. Both use the same
scripted service fixture, so this comparison checks caller decisions and service
ordering; it does not independently validate the fixture's engine semantics.

The verifier compares snapshots at every observed service entry/exit and every
operation entry/exit, including mode, exact accumulator bits, tokenized ownership,
UI open status, retained bindings and queue declarations. Reentry nests the same
ordered observation stream. It then emits a bounded unrolled `.be` replay with
separate local operation records. Every call to the actual Beryl `next` checks its
opcode, mode, PC, screen PC, answer and accumulator; exact f32 print events also
check all binary32 bits, including signed zero distinctions.

The current corpus contains 92 cases and 572 `next` calls, giving 3,432 assertions:

- All three states crossed with UI/screen presence, focus/unfocus, repeated held
  synchronization and deletion.
- Defaults, post-init accumulator preservation, failed Open, degraded map,
  missing input/core, missing owner and failed screen construction.
- Gadget ownership guards, duplicate toggles and successful-only population.
- Close/reopen accumulation and binding retention.
- Below/exact/above threshold, large/zero/negative timesteps, signed zero,
  independent rounding anchors and a longer 0.1 sequence.
- Negative-zero initial accumulation preserved through post-init and rejected
  focus, without addition that would otherwise turn `+0 + -0` into positive zero.
- Scripted reentry from Open, markers, Close, superclass init and telemetry.

The independent numeric anchors include accumulator bits `0x3e7fffff` immediately
below the threshold, exact positive zero after threshold refresh and `0xbe000000`
after a -0.125 step. Adding `2^-27` to the admitted value immediately below 0.25
rounds to 0.25 and refreshes; adding `2^-29` remains below. The oracle uses explicit
pack/unpack rounding for every input and original binary32 addition.
The two preserved-negative-zero cases independently require `0x80000000` and
produce four actual Beryl f32 observations with that bit pattern.

Ten deliberate mutants must be detected. Eight execute actual Beryl reference
fixtures: skipped markers, reordered input hookup, init accumulator reset,
premature focus commit, an added frame guard, duplicate telemetry and a shared
continuation replay, plus negative-zero initialization loss. The signed-zero
mutant deliberately returns successfully and passes numeric equality assertions,
while its exact f32 events differ. This is an observed semantic comparison failure,
not an assertion failure or source trap. Two mutate the Python host/scheduler: duplicate gadget
population and global-continuation overwrite. Their evidence layers remain distinct.

Every baseline and mutant receipt must identify the exact compiler and both input
source hashes. Reference event/output hashes, contiguous sequence numbers, exact
test-header file/offset identities, complete begin/end records and declared
assertion counts are checked. Assertion mutants require a nonzero process exit,
reference-execution failure, false assertion events, matching positive failed-case
counts and a BE1002 assertion diagnostic. Generic failures, startup failures,
timeouts, traps or incomplete traces cannot satisfy a mutation check. Replay
variants use separate retained files rather than overwriting prior receipt inputs.

Malformed transcript and depth-limit checks run before compiler invocation.
Limits are eight nested operations, 128 operations and 1,024 service calls per
case, 4,096 ordered/continuation records, and 64 `next` calls per invocation.
Reference execution has explicit 10-million-step/512-MiB budgets and a 30-second
compiler timeout. The process wrapper owns only its child tree and has a 45-second
harness deadline. Harness budget exhaustion, startup failure, cancellation and
timeout never constitute a source trap or matching successful execution.

## Source provenance

All references are retained sources under
`build/tablet-recovery-1ae28bbb58d4499d808b467a390b6fc1/inputs/mesh/scripts/Game/SparkOSMesh/UI/`.
The verifier pins their exact hashes before execution:

| Source | SHA256 | Relevant source lines |
|---|---|---|
| SPK_TabletComponent.c | `1f15962cf67a8cc513d7068757e89360260016fadff1c8843719784acc94be3a` | 47–181 |
| SPK_TabletGadget.c | `d336244b7d178324eded5bc5e584f721cd2c4f9b7036ac90d1f757ba30b0199c` | 29–92 |
| SPK_TabletUI.c | `4efeab8cce793939d748506f34691aae9b0b47aa8b32ed568ece05accf28a05d` | 133–160, 339–360, 905–908, 1043–1140 |
| SPK_ScreenRT.c | `6328c5e86787b75c8cf949fcbd914c4fb137e17534a6158150bdba13818e942b` | 92–136 |
| SPK_TabletChrome.c | `53c2fccfb900371ce0ea409d98f0903a20e71e472630e6caea87b29477a1811e` | 450–475 |

## Recorded checkpoint and remaining gates

The initial completed reference checkpoint is
`build/tablet-lifecycle-g9jqye57/results.json`, SHA256
`3b08c33ba2b03c4c8a23456de29231cdf783e9cc2dbe382f9fa632d8f724abc8`.
It used the already identified private compiler SHA256
`61f3510b2d6024c22d0a21abf972df33f0e6e16d3e68d921103b581c3864828a`.
It records 90 tests, 3,408 assertions, 84,567 reference steps and nine detected
mutants. No native attempt was selected. Its scope is historical: subsequent
additive receipt/documentation changes and any new compiler receive a fresh run.

The historical completed 90-case reference receipt is
`build/tablet-lifecycle-zvzn8wz8/results.json`, SHA256
`6545fa4d37ebd50b72805cce9da4c9623f6976a54a92ae5f17ceb67487d5d6ff`.
It uses the same identified `61f3510b…` compiler and retains identical 90/3,408
reference coverage, 568 next calls, 970 ordered records, 325 service calls and nine
detected mutants. Inputs remained unchanged throughout this run. Native was not
selected; engine, queued-callback execution and multiplayer were not run. The
receipt retains package/verifier/process-owner bytes, source hashes and tool
identities. Its success is limited to this bounded fixture and reference scope.

The current completed reference receipt is
`build/tablet-lifecycle-i7r4jsze/results.json`, SHA256
`df74857a6f5ea9a2133d937cf232d377505493bf4cfe9777506fe924a30e5fbf`.
It uses the identified `61f3510b…` compiler and records 92 tests, 3,432 assertions,
85,003 reference steps, 572 next calls, 978 ordered records, 327 service calls and
ten detected mutants. Verifier SHA256 is
`39c7e8d76ac1388a32cfb2377c0d78279dc7f0a46541cb2630bbfd77172363a6`;
the Beryl protocol source remains
`34c2b848e94a7a68132804d08a58fcf31d644f2d0e9eb2b4973e84a39249f792`.
The signed-zero mutant completes every test with successful program return, while
observations 225–228 lose `0x80000000`; the independent exact-bit comparison detects
that loss. The earlier 90-case receipts contained no negative-zero accumulator
observation: a negative-zero timestep added to positive zero was insufficient.
Their historical corpus scope is preserved rather than retrospectively expanded.
`tablet-lifecycle-o_62d9pv` records the intervening successful signed-zero addition
before the final receipt/event guard hardening. No native or engine run was selected.

Early attempts remain recorded failures. `tablet-lifecycle-8w6ij7z6` rejected
unsupported semicolon syntax; `tablet-lifecycle-e5858_bp` rejected missing explicit
inout call modes; `tablet-lifecycle-br79y78j` exposed a verifier gap because an
accumulator-reset mutant changed printed bits without failing an assertion.
Numerical state assertions repaired that gap. Their receipts are not converted
to successes. `tablet-lifecycle-rn86zaw6` is an intermediate successful checkpoint.

The smallest next integration packet is an explicit synchronous adapter that
holds real service references and operation-local input/keybind results, maps
these opcodes at the preserved source points and compares original/generated
ordered service traces. Generic scalar component wrappers alone do not implement
this adapter or the tablet lifecycle.

Before tablet adoption: release its actual calling/ownership subset, review exact
engine bindings and retention/validity/authority contracts, generate its real
callbacks/properties/resources with source origins, run original/generated engine
comparisons, host lifecycle tests, dedicated two-client acceptance and visual
interaction review. A native differential attempt is useful language evidence;
it cannot close any of those engine gates. No performance improvement is claimed.

## Integrated compiler and bounded native comparison

The final ordinary compiler used by the integration trial is SHA-256
`76aeaacfea6866e66e3020f983eaa22089d545ad0f3b60fedfd28c3d58972bd7`.
`build/tablet-lifecycle-n5vv10fu/results.json` records success for all 92 cases,
572 `next` calls, 3,432 assertions, 85,003 reference steps, 978 ordered fixture
observations and 327 service calls. It uses the same frozen protocol/verifier
identities as the hardened reference-only checkpoint above.

This trial also selected one actual native differential configuration. The
generated executable launched and matched the reference event stream. Its
compiler arguments, outcomes and exact source identities are retained in the
underlying compiler receipt. It is not an O0/O2 release matrix, an engine
comparison, a benchmark, or closure of earlier denied native fixtures.

All ten deliberate faults were detected with their layer recorded: eight actual
Beryl/protocol-replay faults and two Python host/scheduler faults. Native execution
was selected for the admitted positive corpus; the faults were checked through
the reference/independent fixture comparison, not claimed as native mutants.
The original engine service implementation remains source provenance and a
scripted oracle, not an independently executed engine comparison.

The new generic component wrappers are a separate fixture. They do not call this
service protocol or generate `SPK_TabletComponent`. The engine adapter attempt
was blocked by PowerShell policy before Workbench launched. Real service
references, binding validity/retention, callback delivery, property/UI/prefab
generation, multiplayer and visual acceptance still require their own evidence.
