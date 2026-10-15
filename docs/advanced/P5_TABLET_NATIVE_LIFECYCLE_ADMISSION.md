# P5: admit a native tablet lifecycle scenario in bounded steps

Date: 2026-10-10. Status: **source-reviewed next implementation packet**.

This packet was prepared through passive source and installed-documentation reads.
It adds no compiler capability, installed scenario, engine receipt, callback proof,
profile isolation, promotion or gameplay change. This packet documents the source
review; any later source preparation receives its own receipt. The proposed scenario names and interfaces below are
not existing public commands.

The earliest implementable seam is a **native component-only tablet fixture**:
instantiate the actual original or Beryl-authored tablet component in the running
Game world, let the engine deliver initialization and stowed frames, and record
the observed state and owner. Exclude the input poller and gadget from that first
fixture. Spawning the complete current prefab already reaches user keybinding
registration before `Focus`, so a fresh addon directory alone does not contain
all of its effects.

The complete prefab, real services, player equipment and native deletion are
subsequent explicit admissions. This keeps useful work possible while preserving
the difference between a real tablet component and the complete player feature.

## 1. Evidence available at this checkpoint

| Evidence | Actual result | Boundary |
|---|---|---|
| [Beryl lifecycle protocol](../../packages/sparkos/tablet-lifecycle-prototype/src/lifecycle.be) and [prototype packet](P5_TABLET_LIFECYCLE_PROTOTYPE.md) | Scalar decisions have independent fixtures and bounded execution evidence | No real engine services or native equipment |
| [Service template](../../packages/sparkos/tablet-service-prototype/tablet-service.c.in) and [adapter contract](P5_TABLET_SERVICE_ADAPTER_CONTRACT.md) | Current synchronous adapter preserves the reviewed public surface and source order | Source contract and compilation do not establish service lifetime |
| [Current S1 selected candidate](<../../build/tablet service & spaces-soii5z39/results.json>) | Exact 86-file candidate compiled; 28 copied resource files, 13 registrations; parsed errors zero, 19 warnings retained | Five suite selections were declared and not executed by S1 |
| [Historical S1 independent audit](../../build/oct10-tablet-suite-terminal-audit-27c4aaf7f3d2445182602d72feb6675c.json) | 88 passive identity/artifact/log checks passed on its recorded candidate | Historical scope; current S1 inputs also checked by the fresh S2 audit |
| [Generic native callback run](<../../build/component callbacks & spaces-idjip0_z/results.json>) | Seven cases, 340 frames for each of two owners, 1,373 trace rows, 10,949 checks; native deletion and confirmed owned-process cleanup | A separate generated component, replicated fixture and its own lifecycle domain |
| [Generic callback audit](../../build/oct10-callback-complete-terminal-audit-354cc474b1ae4dc5893e42d07a0ce26b.json) | Actual trace, source identities and protected installation checks retained | Does not extend replication or deletion eligibility to the tablet |
| S2 `q93fbdjk` | Actual transport returned all five requested suite successes; the pinned checker rejected the schema-order expectation | **Retained result remains failure.** Repair and a new receipt are required; do not amend the attempt |
| [New S2 attempt](<../../build/tablet existing suites & spaces-wbymk7mx/results.json>) | All five suites, 18 RPCs, 12 identity checks and confirmed owned cleanup passed; corrected decoder and 130 pure cases | Five source-defined suite responses; no native tablet callback claim |
| [Current S2 independent audit](../../build/oct10-tablet-suites-complete-audit-833f51b0d0e44937aad986370030ee09/result.json) | 894 passive input, receipt, source and installation checks passed; decoder output matches the recorded result | No new runtime execution; retained `q93fbdjk` failure remains unchanged |

The existing [suite execution plan](P5_TABLET_SUITES_RUNTIME_PLAN.md) and
[runtime acceptance packet](P5_TABLET_RUNTIME_ACCEPTANCE.md) remain authoritative
for their respective scopes. This document adds the next native admission ladder.

The historical `j_t2z5u0` S1 parsed error and warning counters were zero under its
warning-excluding filter. Current `soii5z39` reports zero errors and 19 warnings
(five project and fourteen base). Historical raw logs also contain shutdown
resource-leak diagnostics. Retain those logs without
calling the run literally warning-free or attributing the shutdown diagnostics
to the tablet. A successful structural suite must not erase these observations.

## 2. Source identities and exact behavior to preserve

The live source root read for this packet was
`C:/Users/moham/Documents/My Games/ArmaReforgerWorkbench/addons/SparkOS_Mesh`.
The following files matched their captured source-profile identities during this
read. This is a passive observation, not a freeze of future live edits.

| Source | SHA-256 | Relevant contract |
|---|---|---|
| [Tablet component](<C:/Users/moham/Documents/My Games/ArmaReforgerWorkbench/addons/SparkOS_Mesh/scripts/Game/SparkOSMesh/UI/SPK_TabletComponent.c:19>) | `1f15962cf67a8cc513d7068757e89360260016fadff1c8843719784acc94be3a` | STOWED/HELD/FOCUSED state, UI and screen references, native callbacks |
| [Gadget](<C:/Users/moham/Documents/My Games/ArmaReforgerWorkbench/addons/SparkOS_Mesh/scripts/Game/SparkOSMesh/UI/SPK_TabletGadget.c:29>) | `d336244b7d178324eded5bc5e584f721cd2c4f9b7036ac90d1f757ba30b0199c` | Superclass first, local-owner guard, held/focus/populate ordering |
| [Input component](<C:/Users/moham/Documents/My Games/ArmaReforgerWorkbench/addons/SparkOS_Mesh/scripts/Game/SparkOSMesh/Input/SPK_DroneInputComponent.c:81>) | `440a493229775ab18233c76020763d4c724adfb4fece3dc41e9ca26747e5695b` | Initialization registers bindings; frames poll systems and tablet toggle |
| [Keybindings](<C:/Users/moham/Documents/My Games/ArmaReforgerWorkbench/addons/SparkOS_Mesh/scripts/Game/SparkOSMesh/Input/SPK_DroneKeybinds.c:34>) | `1123a60363291343d858f3106896260060160a89b340085236b0437808a962ce` | Missing defaults can be added and saved to the player's profile |
| [UI](<C:/Users/moham/Documents/My Games/ArmaReforgerWorkbench/addons/SparkOS_Mesh/scripts/Game/SparkOSMesh/UI/SPK_TabletUI.c:133>) | `4efeab8cce793939d748506f34691aae9b0b47aa8b32ed568ece05accf28a05d` | Real widget services, degraded map, delayed work and close/reopen behavior |
| [Screen](<C:/Users/moham/Documents/My Games/ArmaReforgerWorkbench/addons/SparkOS_Mesh/scripts/Game/SparkOSMesh/UI/SPK_ScreenRT.c:92>) | `6328c5e86787b75c8cf949fcbd914c4fb137e17534a6158150bdba13818e942b` | Owner binding, enable flag, unbind-before-removal order |
| [Chrome](<C:/Users/moham/Documents/My Games/ArmaReforgerWorkbench/addons/SparkOS_Mesh/scripts/Game/SparkOSMesh/UI/SPK_TabletChrome.c:35>) | `53c2fccfb900371ce0ea409d98f0903a20e71e472630e6caea87b29477a1811e` | Retained button array and action receiver |
| [Tablet prefab](<C:/Users/moham/Documents/My Games/ArmaReforgerWorkbench/addons/SparkOS_Mesh/Prefabs/SPK_Tablet.et:1>) | `dabd491efd1b27cf49b311948c1215acf1982f06f6b6de8a0e9ea0e001ae0c22` | Six component classes; no explicit `RplComponent` |

The service template is SHA-256
`21479adf12a76a48ad7be9419e6e5047d663cce0ebee1341e5d8bfaf8d20d3c7`.
The protocol is SHA-256
`34c2b848e94a7a68132804d08a58fcf31d644f2d0e9eb2b4973e84a39249f792`.
Use those actual bytes and emitted linkage, not guessed mangled type/field names.

### 2.1 Initialization and frames

Original component lines 133–137 call superclass first, publish STOWED, then
request `EntityEvent.FRAME`. They do not reset the telemetry accumulator.
The candidate template has a dedicated native override which acknowledges
protocol opcode 14 after the superclass call, performs the state/mask phase,
requests FRAME once, and completes the invocation.

Original frame lines 150–166 guard FOCUSED plus nonnull UI once; call markers;
add the actual `timeSlice`; return while the accumulator is below 0.25; otherwise
reset to zero and refresh telemetry once. Preserve accumulator across close and
reopen. Do not add catch-up refreshes, retained remainder, a new nonpositive-time
guard or a second focused-state check after marker service reentry.

A fresh component's default STOWED value alone cannot prove the reset operation
occurred. A FRAME bit observation cannot count duplicate `SetEventMask` calls.
Initial callback delivery, source ordering and mutation-sensitive semantic tests
are different evidence. Advertise only the observations the fixture can establish.

### 2.2 Public lifecycle and services

`Focus` succeeds only from HELD. It creates UI if necessary and calls `Open`
before finding/connecting input. A failed `Open` does not publish FOCUSED.
Successful widget construction with absent/refused map attachment still opens a
degraded UI. Input and keybind identities are retained at their original source
points; FOCUSED is then published and the screen synchronized.

`SetHeld(true)` publishes HELD only from STOWED and synchronizes the screen even
on repeated calls. `SetHeld(false)` runs Unfocus first, then publishes STOWED and
synchronizes again. From FOCUSED, preserve Close at FOCUSED, HELD plus screen
Enable, followed by STOWED plus Disable. Do not coalesce those service calls.

The candidate has one persistent Beryl state object. Every invocation owns its
own Operation, reply, input and keybind locals. It calls the generated `next`
function directly against the same state. No copyback at operation end is allowed.
The existing source-replay reentry cases remain required independently of the
native fixture, which may not happen to trigger those nested service paths.

### 2.3 Gadget and local ownership

The original gadget calls superclass before its local-owner guard. The guard
requires a `ChimeraCharacter` character owner, a player controller, and equality
between that controller's controlled entity and the character owner. A truthy
entity, server flag or component reference does not establish this condition.

Activation performs SetHeld, Focus, then Populate only when Focus returned true.
Populate captures the current UI, reads the current MESH core/assets, refreshes
contact rows and order availability. Repeated activation while already FOCUSED
does not populate again. The input component's actual toggle path calls the
gadget's `ToggleActive(..., SCR_EUseContext.CUSTOM)` after holder/manager guards.
Calling `OnToggleActive` directly would bypass this path and is inadmissible as
native gadget evidence.

## 3. Primary APIs: declaration, observed use and remaining contracts

Installed documentation was read beneath
`C:/Program Files (x86)/Steam/steamapps/common/Arma Reforger Tools/Workbench/docs`.
The evidence below concerns the pinned 1.8.0.13 toolchain. A signature is not a
verified lifetime or scheduling contract.

| Primary input | SHA-256 | What is established |
|---|---|---|
| `EnfusionScriptAPI/html/interfaceGame.html` | `dfcab6b926646b8b56cdcbf38bb3e5f9809e96c9e3efaabc11cf806d6ec4b22e` | `GetWorld()`; `SpawnEntityPrefab(notnull Resource, BaseWorld=null, EntitySpawnParams=null) -> IEntity` |
| `EnfusionScriptAPI/html/interfaceScriptComponent.html` | `215f2ca81f0d47cbe1dc61dd8471c73c5b5f78c623a247d5f82e8a1e6471c3de` | Protected post-init/frame/delete callbacks; event-mask access |
| `EnfusionScriptAPI/html/interfaceWorldEditor.html` | `51af7415047780b9efa7302dfa3b4573dd89d78c4d90b46968273f010f16f275` | `SwitchToGameMode(bool=false,bool=false)` and `SwitchToEditMode()` |
| `EnfusionScriptAPI/html/interfaceIEntity.html` | `ec2e7f4c76ab91af50a9448ccd13db7aa7590ba3584fbfdacbd6773d899ec585` | `IsDeleted()` documentation limits pointer validity to the end of the frame |
| `ArmaReforgerScriptAPIPublic/html/interfaceSCR__EntityHelper.html` | `04728aede2cc4fa93b77eedfbca102d8083517d48b6acc8f3247ac4cdee67cac` | `DeleteEntityAndChildren(IEntity)` is described as a `DeleteRplEntity(entity,false)` wrapper |
| `EnfusionScriptAPI/html/interfaceRTTextureWidget.html` | `af9141774584f07813c4e9962a8e9ad4f412c082af4598ab30b7fb7d986ede41` | Set/RemoveRenderTarget declarations and documented object-selection/removal conditions |
| `EnfusionScriptAPI/html/Page_CLI.html` | `b1fd25c1d02e3ac687bb310496f700acaf451f66d26c572afa9ac5fd343822d1` | Public `-profile` path option and `-forceUpdate`; platform-dependent profile location |
| `EnfusionScriptAPI/html/Page_Enforce_Syntax.html` | `df83332c65707ce3e9a751c76fe323f1e5fee5459814ba7b5ee850fb325a572d` | Generic object deletion and managed-pointer behavior; not a tablet authority/lifetime contract |

### 3.1 Use the Game world; do not copy the generic authority assumptions

The failed generic `bbe8mikw` run had initialized owners in the API world and
zero owner frames while the Game world advanced. The corrected
[RPC template](../../packages/sparkos/component-callback-probe/rpc.c.in:216)
selects `GetGame().GetWorld()` and rejects an owner whose world differs. The
actual `idjip0_z` comparison subsequently passed native frames and deletion.
This supports a concrete world-selection repair, not a universal explanation of
all earlier engine timeouts.

Retain native named-world/mode checks and additionally record Game world versus
API world and each owner's world. Do not require Game and API references to be
equal: the successful run observed that they differed. Owner equality with the
running Game world is the relevant spawn obligation.

The generic fixture has a replication component and checks authority before
`DeleteRplEntity`. The actual tablet prefab has no such component. Its next
scenario must not add RplComponent, fabricate authority, or inherit that deletion
admission merely to make the generic registry succeed.

### 3.2 Profile isolation is an explicit prerequisite for complete prefab spawn

Input `OnPostInit` calls `GetKeybinds` before registering FRAME. `GetKeybinds`
constructs `SPK_DroneKeybinds` and calls `RegisterDefaults`; the latter creates a
user binding, skips already bound actions, adds missing defaults and calls Save
when any were added. Turning input polling off does not suppress initialization.

The primary CLI documents `-profile ABSOLUTE_PATH`, but also qualifies the final
location by platform/path behavior. Add a separately admitted launch profile
using a fresh owned absolute profile parent only after checking exact argv,
actual output locations, native binding behavior and owned listener identity.
Do not append an unvalidated arbitrary switch to an existing released profile.

The retained plugin daemon accepts no profile argument. Its compile launcher
uses the default LogsDir obtained through Find-Workbench. The retained NetAPI
configuration helper writes HKCU QSettings independently of addon paths. Thus
an owned profile variant also needs profile-aware log capture and explicit
settings/output coverage; `-profile` alone proves none of those.

Prefer a fresh isolated profile over modifying/restoring the operator's real
profile. If isolation is unavailable, keep the complete-prefab case unavailable.
A backup/restore alternative requires verified locations, exact original hashes,
exclusive ownership and tested restoration even after timeout; it must never
overwrite a concurrently changed user profile. No profile was written by this
source review.

### 3.3 No suitable non-Rpl deletion contract has been established yet

The bounded current MESH source search found entity destruction only through
`SCR_EntityHelper.DeleteEntityAndChildren`, at DeployAction line 156 and Warhead
line 165. Its documented wrapper does not independently establish the behavior
of the current tablet without RplComponent. This search is not a claim that the
engine has no other deletion API.

Do not promote generic `delete` object syntax, `IsDeleted`, a missing component
reference or process exit into proof of native tablet destruction. Extract the
actual applicable declaration/source and verify it against the intended owner
before selecting an item-deletion operation.

An earlier bounded alternative is **owned world teardown** through the already
declared mode transition. It can be investigated without adding replication.
The target claim would be OnDelete during that exact teardown, not equipment
deletion, inventory consumption or arbitrary player death. Capture callback
records before module/world state becomes unavailable, and retain raw log markers
externally. Switching to edit mode or stopping the process is not itself a delete
case success; the actual callback and ordered service records are required.

## 4. Admission ladder and fixed coverage

| Gate | Source shape and action | Required evidence | Coverage explicitly left open |
|---|---|---|---|
| N0 — component callbacks | Trusted component-only owner; original or candidate tablet component, no gadget, input poller, UI service calls or replication | Native init and bounded stowed frames; correct Game-world/owner identity; stable state root; unchanged mode/accumulator | Full prefab, screen/UI, local owner, delete, gameplay |
| N1 — component services | Live owner under the same callback admission; explicit public SetHeld/Focus/Unfocus calls; actual services, missing-input branch declared | State/service ordering and real frame-driven telemetry; screen/UI identities and actual replies | Physical equip, gadget RPC, real key event, complete input hookup |
| N2 — complete prefab | Exact six-component tablet resource, fresh verified owned profile and full resource inputs | Native component initialization; actual input/keybind identity; recorded profile outputs; same public service behavior | Controlled character, actual gear-slot ownership, native player input |
| N3 — teardown | Explicitly admitted world or item destruction path | Actual OnDelete, Close/Destroy/super ordering, external trace retention and confirmed transport cleanup | Other destruction causes and general lifetime proof |
| N4 — player/gadget | Verified character, player controller, inventory/equipment and gadget-manager setup | Genuine ToggleActive path and local-owner comparisons; successful-only population | Dedicated two-client acceptance until executed |
| N5 — lifetime/UI/MP | Deferred work, native input/click, real ownership transitions and independent clients | Separate named cases and visual/runtime evidence | No generalized release from a subset |

Each gate produces a new immutable candidate and receipt. An unavailable N2 or
N3 capability must not prevent N0 development or be silently bypassed in N0's
completion record. The original eight lifecycle IDs in the runtime packet remain
the full acceptance set; an N0 receipt is not that eight-case receipt.

## 5. N0: earliest safe implementation

Implement a fixed installed fixture, provisionally named
`tablet.native.component-callbacks.v1`. This name is a proposal, not currently
discoverable capability.

1. Capture current protocol, trusted service template, original component,
   generated linkage/source map, tool/engine and layered-world identities.
   Generate one source set for the candidate and a separate original reference
   source set. Avoid duplicate production classes by using separate owned jobs;
   do not load original MESH alongside the candidate.
2. Use the exact admitted layered world and force-update ownership transport from
   the successful callback fixture. Keep existing startup/RPC/overall/cleanup
   budgets and fixed owner/session checks. A new addon has its own identity and
   compiled token; every additional source/resource is enumerated before compile.
3. Create a fixture prefab containing the admitted tablet component or a trusted
   observer derived from it, with an explicit descriptor and no input, gadget or
   Rpl component. If the observer replaces a prefab component identity, record
   that as a fixture-only composition delta. It is not the unchanged six-component
   production prefab and must not claim its schema/resource/equipment acceptance.
4. Let `SpawnEntityPrefab` construct the owner in the running Game world. Validate
   the resource as an entity source and record returned owner versus callback
   owner; record entity active/frame-mask observations rather than assuming them.
   Any ACTIVE setting is a declared fixture action and separately recorded.
5. An observer may surround `super.OnPostInit` and `super.EOnFrame` to count native
   delivery and inspect plain state. It must never call those callbacks from a
   request, constructor helper, timer or manual test loop. Its public methods call
   actual tablet methods only in later N1 actions.
6. Capture state/mode before and after each actual callback, owner token, component
   token, world relation, ordinal, actual timestep admission and plain-state-root
   identity. Keep those data in the trusted observer/registry, outside ordinary
   Beryl engine-reference copying. No component-root copyback or field mirroring.
7. Predeclare N0 case IDs for each admitted owner, e.g. init.1/2 and stowed-frame.1/2,
   and independence. Require actual unique delivery and minimum real frame counts.
   Count variable observed frames exactly; never derive expected IDs from output.
   Do not include delete in a complete N0 set until N3 is admitted.
8. Finish through a separately reported owned teardown/cleanup path. Until native
   delete is verified, the receipt records it as not selected or unavailable.
   Confirmed process exit is required for transport completion and does not stand
   in for the application callback.

Keep original and candidate expected domains equal. N0 does not call UI/screen
services in either variant and does not infer equivalence outside STOWED callback
inputs. The full source replay still covers unsupported-to-native reentry and
numeric boundary cases. A fresh-state run alone cannot detect removal of the
STOWED reset; retain the independent semantic mutant fixture for that operation.

## 6. N1/N2: observe real service flow without claiming real equipment

After N0, add fixed synchronous requests for refused Focus from STOWED, held,
focus, repeated-held, stow and reopen. Those are ordinary public method calls on
a natively constructed live component. They are not manually delivered engine
callbacks and are not physical gear-slot or key events.

N1 may intentionally omit input; the expected missing-input diagnostic is part
of that domain. N2 must use the full input component and verified owned profile.
Do not populate a fake input pointer in N1 and report the production hookup done.

Record each immediate service call/reply at its original point. Trusted
fixture-only observational hooks may call through to actual UI/screen methods,
but must not substitute successful return values, skip queued work, clear fields,
disable terrain or reroute input. Declare instrumentation as separate source
bytes and preserve the uninstrumented adapter. External callback wrappers alone
do not observe every internal service ordering point.

Expected finite frame behavior is computed from each run's actual captured input
sequence and original source model. Separate runs will have different timesteps;
never drop frames or force a shared clock to make transcripts match. Keep exact
discrete state and ordered service counts. Report float comparison according to
the independently admitted encoding: rounded `ToString` data is not bitwise f32
evidence. Exact threshold/reset/signed-zero anchors remain in the scalar replay
unless the target encoding is independently established.

UI opening with no map is an admitted degraded result. A missing workspace or
failed widget tree is an actual service outcome; retain it without manufacturing
a successful focus. A service-admission receipt may record the refused branch
correctly while leaving the successful-open capability unavailable.

Screen `IsEnabled()` is the script flag set after `SetRenderTarget`, not proof
that the model displays pixels or that object-selection requirements held.
Record the exact live owner, widget identity, enable reply and removal ordering.
Native render-target binding/selection and a visual check remain separate.

## 7. Deferred lifetime, native events and player boundaries

### UI and handler retention

UI `BuildWidgets` queues `ReportRootSize` at 500 ms; `Open` queues `RefreshTerrain`
at 400 ms. `RefreshTerrain` can queue another attempt when canvas size is small.
Close detaches maps/markers and removes the root, but does not clear terrain map,
terrain canvas, Chrome, input, keybindings or queued methods. This is source
evidence of retained fields and scheduled work, not a proven dangling-reference
bug or a proof of safe cancellation.

Add independent close-before-delay, close/reopen-before-delay, destroy-before-delay,
and repeated-cycle fixtures. Retain enqueue/execution/receiver/world identities
and actual native failures. A quiet log for one interval cannot establish universal
absence of retained storage. Do not retrofit queue cancellation into exact parity
testing; any repair receives a separate behavioral contract and before/after test.

Chrome retains buttons in `ref array<ref SPK_UIButton>` and stores the receiver.
The existing click suite calls `OnClick` directly. A native map-mode case requires
an actual widget event path with the correct widget lifetime, one dispatch and
the real 2D/3D label/action transition. Do not invent an input-injection API or use
another direct handler call to claim this gate. Human interaction can supply the
event in an owned session if automation is unavailable, with separately retained
observations and visual review.

### Player equipment and authority

Before N4, extract exact installed character/controller, inventory slot,
gadget-manager and toggle declarations or original native source. Verify that
the fixture creates a genuine controlled character and that the gadget belongs
to it. The current empty layered world and a free-standing tablet cannot establish
that. The method name `ToggleActive` does not authorize inventing a player setup.

Preserve `m_eUseMask=15`, `m_eAnimVariable=MAP`, GPS gadget type and input-enabled
default. Retain superclass-first toggle behavior and the original controlled-owner
equality guard. A test cannot bypass the guard to make local UI appear. Server
status and Rpl authority are separate from local UI ownership.

Multiplayer then requires the dedicated server and two independent clients with
remote UI isolation, death/respawn, ownership changes, disconnect/reconnect,
join-in-progress, repeated equip/stow and multiple tablet instances. No result in
this packet closes those gates. Do not add replication to the tablet as an
unreviewed fixture convenience.

## 8. Root-cause fixtures and receipt admission

The next implementation must retain small counterexamples with exact identities:

| Fixture | Required detected outcome |
|---|---|
| Owner spawned in API world while Game world advances | Wrong-world admission or genuine missing-frame outcome; no fake frame success |
| Native initialization/frame manually called by handler | Rejected fixture/source admission; no native-callback claim |
| Lost or substituted state root | Exact identity failure; no mirrored state success |
| Focus from STOWED; failed Open from HELD | Refused transition with source state publication preserved |
| Nested service entry mutates current mode/state | Invocation-local PC/reply/bindings; current shared state survives |
| Marker service changes state during frame | Original single entry guard and subsequent update order preserved |
| Frame threshold, reset, close/reopen | Correct actual sequence; no catch-up/remainder/reset-on-reopen mutation |
| Full prefab without admitted profile output handling | N2 unavailable; no claim that addon isolation contained settings |
| Generic Rpl-required registry applied to actual tablet | Rejected target/domain mismatch; no fabricated authority |
| OnDelete missing but owned process exits | Cleanup success plus callback incomplete, never deletion success |
| Queue executes after close/reopen/destruction | Record real receiver/field/world outcome; do not assume cancellation |
| Missing/duplicate/unknown/reordered IDs or trace rows | Harness failure with raw data retained |
| Bool/int coercion, corrupt codec, wrong token/world/source | Admission failure or stale input as appropriate |
| Timeout/cancellation/late response plus successful prefix | Primary terminal status preserved; prefix separately retained |

Keep source traps, service refusal, unsupported capability, harness failure,
timeout, cancellation, stale source and cleanup failure distinct. An expected
failure fixture closes only its declared comparison. It is not native success
and does not allow a different failure, missing result or timeout to match.

A runtime result binds source bytes, compiler, generated artifact, original model,
instrumentation, bindings, engine, scenario revision, native world and owned
process. Expected IDs/limits are written before execution. Raw RPC strings remain
unchanged alongside separately normalized values and explicit codecs. Ordered
observations require contiguous ordinals and a complete expected set/checksum.
Keep ordinary session checks and auxiliary world diagnostics separate.

Guard exact original, retained and staged trees around every operation. Admit only
enumerated derived output such as the bounded regular root `resourceDatabase.rdb`;
do not ignore it when it was itself an original input. Missing current hashes,
extra files, linked cache outputs or unconfirmed cleanup cannot close a gate.

## 9. Implementation handoff and completion rule

Recommended next files are a new installed native-tablet fixture package, a
bounded runner and an independent receipt checker. Their exact names are decided
when their actual admission API is implemented. Reuse the existing ownership,
source-copy/resource guards, transport and diagnostic primitives. Do not reuse
the seven generic expected cases or its Rpl authority registry unchanged.

Order the work:

1. Independently admit the new successful S2 suite receipt, preserving
   `q93fbdjk` as a failure. That is a useful structural gate, not N0 eligibility.
2. Implement N0 source-only staging and pure receipt faults, then clean compile.
3. Run one owned N0 original/candidate comparison through genuine callbacks.
4. Admit N1 service traces with reviewed failure/reentry fixtures.
5. Verify the `-profile` isolation/output contract before N2 full-prefab spawn.
6. Separately verify world/item teardown and trace survival before N3 deletion.
7. Add genuine player/equipment setup before N4 local-owner/gadget delivery.
8. Finish queue/handler lifetime, native UI event, visual and dedicated-client gates.

N0 is complete when its exact native init/stowed-frame and independence evidence
passes, with its teardown status explicit. It does not wait for the whole mod or
complete player setup. The complete tablet release still requires the original
full lifecycle, real input/gadget, lifetime, deployment and visual acceptance
matrix. Source simplicity and zero manual generated-file repair remain delivery
requirements throughout.
