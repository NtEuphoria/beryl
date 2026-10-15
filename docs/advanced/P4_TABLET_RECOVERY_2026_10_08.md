# P4 tablet recovery and next implementation packet

Status: refreshed source evidence and proposed implementation boundary, 2026-10-08.
This packet does not implement or validate the tablet migration. No engine,
Workbench, game or unknown compiler executable was run. MESH, the Workbench
plugin and the engine installation were read only. Existing receipts and the
September inventory are preserved.

## 1. What changed, and what did not

The selected tablet baseline remains usable as source evidence. Of the 37 inputs
in the [previous inventory](P4_TABLET_CONTRACT_INVENTORY.md), 36 are byte-identical
and one changed: Beryl's `tools/beryl-mod/mod.py`. The captured current file adds
the pending strict-v1, non-executing operation-plan path. It does not add tablet
components, companion v2 or verified engine contracts.

| Input | Previous SHA-256 | Refreshed SHA-256 |
|---|---|---|
| `beryl/tools/beryl-mod/mod.py` | `9f6bfaabdb7b67d425e0772989efc4181e4a2623c01c874b021d10f328bfbe4e` | `cfe83db0cbb7ea506e57b46adb7e9e5ba0b465246a9c331d0abcef074c728030` |

The selected MESH lifecycle, input, chrome/button, theme, screen service,
self-test, prefab and metadata files match their prior captured hashes. The old
selected API documents, binding snapshot, plugin README and source-search script
also match. Git working-tree modifications do not contradict this result: a
file can be dirty relative to Git while matching a previously captured dirty
baseline. No dirty file was reset, normalized or replaced.

This is not a whole-project drift audit. Additional plugin scripts and metadata
were captured for the first time, so they have no prior selected-file comparison.
Likewise, unchanged selected prefab text does not prove unchanged binary assets,
dependency resources, behavior or loaded editor state.

## 2. Fresh evidence identity

The new evidence directory is
[`tablet-recovery-1ae28bbb58d4499d808b467a390b6fc1`](../../build/tablet-recovery-1ae28bbb58d4499d808b467a390b6fc1/source-evidence.json).

| Receipt | SHA-256 | Coverage |
|---|---|---|
| Previous `tablet-inventory-teqbgmaf/source-evidence.json` | `bedcb75fed18e194b1e3985720696c76e98bc579085e0949c0495166be3ee754` | Original 37 selected inputs, preserved |
| New `source-evidence.json` | `5be54c47925528e9f585c8dcd92d6988cfda6b82478d5e021fcf1f8080737a78` | 67 selected inputs; 36 old inputs unchanged, one changed, 30 newly captured, zero missing |
| New `contract-addendum.json` | `86dfdedce75d1e169dd5660d1e91257d5bba228abb3bc472a61b781075bc860b` | Two additional installed API documents resolving the queue accessor; primary manifest unchanged |

The primary capture retains 902 Doxygen member rows. These include inherited
rows and are **not 902 distinct verified bindings**. A typed registry must resolve
declaring-class identity and inheritance instead of registering every rendered
row as a new declaration. The addendum retains one selected queue declaration.
All captured originals were reread after copying and compared with retained bytes.

The capture extends the old inputs with the current MESH core and terrain source,
component descriptor/base-class documents, Color/TextWidget/ButtonWidget
documents, Beryl's feature registry and MCP adapter, plugin metadata and all 17
top-level plugin PowerShell scripts. The evidence manifest records individual
absolute source paths, byte lengths, line counts, hashes and retained paths.

The installed engine was hashed twice without execution:

| Field | Observed value |
|---|---|
| Executable | `C:/Program Files (x86)/Steam/steamapps/common/Arma Reforger Tools/Workbench/ArmaReforgerWorkbenchSteamDiag.exe` |
| File/product versions read from metadata | `1.8.0.13` / `1.8.0.13` |
| Bytes | `67576376` |
| SHA-256 | `7dd36ca1f662b0c13669a4f2f7f10e3c461c2906b021e742272d64b3ab7e9798` |

That hash matches the prior inventory and extracted binding registry. It says
nothing about a running session's project, plugin loading, compilation or runtime
success. No executable copy, engine compilation, scenario, promotion, resource
load, multiplayer check or visual check is claimed here.

## 3. Exact feature contract to carry forward

Paths and one-based line numbers below refer to retained copies under
`inputs/mesh/` or `inputs/core_api/` and `inputs/arma_api/` in the fresh directory.
They identify the source bytes in these receipts, rather than future live files.

### Tablet component and gadget

| Source | Required behavior |
|---|---|
| `scripts/Game/SparkOSMesh/UI/SPK_TabletComponent.c:9,19` | Preserve `SPK_TabletComponentClass : ScriptComponentClass` and `SPK_TabletComponent : ScriptComponent`, their public names and existing `ComponentEditorProps` |
| Same file, lines 30,37,62 | Preserve `SPK_ScreenRT GetScreen()`, `SPK_TabletUI GetUI()` and `ESPK_TabletState GetState()`; service getters return the existing references and can be null before allocation |
| Same file, line 69 | `bool Focus()` begins only from HELD; failed `Open()` leaves HELD; successful opening with missing input still focuses after logging |
| Same file, lines 102,117 | `bool Unfocus()` and `void SetHeld(bool held)` preserve UI close and intermediate screen transitions; stowing a focused tablet closes UI, enables HELD screen, then disables STOWED screen |
| Same file, line 133 | `override void OnPostInit(IEntity owner)` calls superclass first, sets STOWED, then requests FRAME events |
| Same file, line 150 | `override void EOnFrame(IEntity owner, float timeSlice)` has no superclass frame call; it updates markers before adding the f32 timestep; at `>= 0.25` it resets to zero and refreshes telemetry once |
| Same file, line 171 | `override void OnDelete(IEntity owner)` closes UI, destroys the screen service, then calls superclass |
| `scripts/Game/SparkOSMesh/UI/SPK_TabletGadget.c:2,18` | Preserve descriptor parent `SCR_GadgetComponentClass` and instance parent `SCR_GadgetComponent` |
| Same file, line 23 | `override EGadgetType GetType()` returns the existing symbolic `GPS` member |
| Same file, line 29 | `override void OnToggleActive(bool state)` calls superclass before the local-owner guard; false stows; true sets HELD, attempts focus and populates only after successful focus |
| Same file, line 82 | `IsLocalOwner()` requires a character owner, player controller and reference identity equality with the controlled entity |

Do not fold these into one final-state assignment. The adapter calls are
observations, including `SyncScreen()` when state is unchanged. The existing
`Enable(GetOwner())` return is ignored; adding recovery changes behavior and
needs a separately specified repair.

The frame cadence has no catch-up loop or preserved remainder. The accumulator
survives close/reopen. The tablet callback has no nonpositive-timestep guard,
whereas the input poller does. Admit finite f32 test sequences explicitly; do
not promise nonfinite parity without a defined domain and target evidence.

Repeated activation while already focused does not repopulate: `SetHeld(true)`
still synchronizes the screen, but `Focus()` returns false. Preserve all three
observable details.

### Existing input and UI boundaries

`SPK_DroneInputComponent.c:195` retains the action-trigger, same-entity gadget,
character-holder and gadget-manager guards before the existing
`gadget.ToggleActive(wantOpen, SCR_EUseContext.CUSTOM)` call at line 222. The
tablet poll remains before the autonomy early return in `EOnFrame`. Keep one
poller, the actual rebindable action service and current keybinding persistence.
A direct Beryl state change would bypass the existing gadget route.

The existing `m_bEnabled` editor property at lines 17-19 has default `"1"` and
description `"Poll operator input"`. Preserve unrelated collective, gimbal and
zoom properties. Do not introduce a second input flag on the tablet merely to
demonstrate companion properties.

The first UI slice is still `Btn_MapMode` plus `Btn_MapMode_Label`, built inside
the existing HeaderBar:

| Contract | Exact source |
|---|---|
| Initial label `2D`, action `toggle_mapmode`, index `-1` | `SPK_TabletChrome.c:262-263`; `SPK_UIButton.c:16` |
| Existing Place arguments `0,0,0,1,250,8,320,-8` | `SPK_TabletChrome.c:263` |
| Place negates right/bottom before FrameSlot offsets | `SPK_TabletChrome.c:64` |
| Button, label, attached handler and retained handler array | `SPK_TabletChrome.c:37,127-143` |
| One dispatch per admitted click; disabled/no receiver returns false | `SPK_UIButton.c:118-124` |
| Hover behavior and disabled presentation | `SPK_UIButton.c:94,127,136` |
| Toggle actual map service and update label to `2D`/`3D` | `SPK_TabletUI.c:522` |

Call the reviewed MakeButton/Place adapters initially. Do not reinterpret their
arguments as raw layout units, omit FindButton membership, add a mouse-button
filter, duplicate the button or replace theme tokens with compiler brand rules.
The current construction uses `Color.FromIntSRGB`; rendered color and resolution
acceptance remain separate from signature extraction.

## 4. Installed declarations and missing typed contracts

### Inheritance and callback identity

The installed documents show `SCR_GadgetComponent`'s direct parent as
`ScriptGameComponent` (`interfaceSCR__GadgetComponent.html:118`) and its descriptor
parent as `ScriptGameComponentClass`
(`interfaceSCR__GadgetComponentClass.html:115`). Do not flatten those to a
direct ScriptComponent/ScriptComponentClass relationship. The complete cross-API
base chain still needs declaring-source resolution wherever the public document
omits an upstream link.

For the ordinary tablet, the source explicitly extends ScriptComponent and
ScriptComponentClass. The latter's installed diagram identifies
GenericComponentClass and EntityComponentPrefabData at lines 114-115 of
`interfaceScriptComponentClass.html`. A descriptor and an instance are separate
types, not interchangeable bindings.

| Declaring document / line | Exact extracted signature | Missing reviewed contract |
|---|---|---|
| `core_api/interfaceScriptComponent.html:128` | `proto external GenericEntity GetOwner()` | Validity during deletion/reentry and reference retention |
| Same, line 137 | `proto external int SetEventMask(notnull IEntity owner, int mask)` | FRAME registration semantics, inherited masks and delivery lifetime |
| Same, lines 210,238,240 | `void EOnFrame(IEntity owner, float timeSlice)`; `void OnPostInit(IEntity owner)`; `void OnDelete(IEntity owner)` | Callback/superclass ordering, teardown and reentry obligations |
| `core_api/interfaceIEntity.html:278` | `proto external Managed FindComponent(TypeName typeName)` | Nullable lookup, cast compatibility and component validity |
| `arma_api/interfaceSCR__GadgetComponent.html:140,154` | `void OnToggleActive(bool state)`; `void ToggleActive(bool state, SCR_EUseContext context)` | Synchronized delivery, rejection, duplicate events and authority |
| Same, lines 160,162 | `ChimeraCharacter GetCharacterOwner()`; `EGadgetType GetType()` | Null holder across equip/drop/death and admitted GPS behavior |
| `arma_api/interfaceSCR__GadgetManagerComponent.html:171` | `static SCR_GadgetManagerComponent GetGadgetManager(IEntity entity)` | Validity during transitions; existing manager guard must remain |
| Same, lines 161,216 | `void AskToggleGadget(SCR_GadgetComponent gadgetComp, bool state)`; protected `void RPC_AskToggleGadget(RplId id, bool state)` | Server-side authorization and actual client/server outcomes |
| `arma_api/interfaceChimeraGame.html:127` | `proto external PlayerController GetPlayerController()` | Dedicated-server absence and controller lifecycle |
| `arma_api/interfacePlayerController.html:121` | `proto external IEntity GetControlledEntity()` | Ownership-change timing and identity validity |
| `core_api/interfaceInputManager.html:172` | `proto external bool GetActionTriggered(string actionName)` | Trigger consumption, edge delivery and active input contexts |

Preserving MESH's source order is a compatibility requirement. It does not prove
the engine's implementation is reentrant-safe, that `@server_only` executes on
the server, or that a requested gadget toggle was accepted. Record requests and
observed callbacks separately. Host results cannot close independent-client gates.

### Properties and enums

`interfaceSCR__GadgetComponent.html:202-203` declares protected inherited fields
`EGadgetAnimVariable m_eAnimVariable` and `SCR_EUseContext m_eUseMask`; detailed
sections at 1034 and 1056 retain that identity/access information. The prefab
sets `m_eUseMask 15` and `m_eAnimVariable MAP`. The sources use `EGadgetType.GPS`
and `SCR_EUseContext.CUSTOM`.

Those symbolic uses and the documented field types are available. Complete enum
declarations, underlying values, accepted flag combinations, property loading
rules and descriptor-to-instance correspondence are not established by the
selected capture. Do not invent what the bits in 15 mean or silently convert
MAP/CUSTOM/GPS to guessed integers. Unknown enum/property admission must remain
unavailable until actual declaring evidence and validation exist.

### Widget and queue retention

| Declaring document / line | Exact extracted signature | Required boundary |
|---|---|---|
| `core_api/interfaceWorkspaceWidget.html:155` | `proto external Widget CreateWidget(WidgetType type, WidgetFlags flags, Color color, int sort, Widget parentWidget=NULL)` | Nullable creation, parent ownership and widget lifecycle |
| Same, lines 153,157 | `proto external float DPIUnscale(float valueInPhysicalResolution)`; `proto external Widget CreateWidgetInWorkspace(WidgetType type, int left, int top, int width, int height, WidgetFlags flags, Color color, int sort)` | Actual DPI/root lifetime and input focus |
| `core_api/interfaceFrameSlot.html:134,143,144` | `static proto void SetOffsets(notnull Widget widget, float left, float top, float right, float bottom)`; `SetAnchorMin` / `SetAnchorMax` with widget and float x/y | Preserve existing Place conversion; verify actual layout separately |
| `core_api/interfaceWidget.html:154,156,194` | `proto external void AddHandler(ScriptedWidgetEventHandler eventHandler)`; `RemoveHandler(...)`; `RemoveFromHierarchy()` | Apply documented reference retention/release and deferred destruction; validate full receiver/teardown behavior |
| `core_api/interfaceScriptedWidgetEventHandler.html:127,149,151` | `bool OnClick(Widget w, int x, int y, int button)`; `bool OnMouseEnter(Widget w, int x, int y)`; `bool OnMouseLeave(Widget w, Widget enterW, int x, int y)` | Routed events, return/bubbling behavior and receiver lifetime |
| `core_api/interfaceTextWidget.html:182` | `proto external void SetText(string text)` | Text encoding/units and retained label validity |
| `core_api/interfaceColor.html:191` | `static proto ref Color FromIntSRGB(int color)` | Reference ownership and rendered color interpretation |
| Addendum `arma_api/interfaceArmaReforgerScripted.html:140,536` | `ScriptCallQueue GetCallqueue()` | Global GetGame receiver typing, queue lifetime and validity |
| `core_api/interfaceScriptCallQueue.html:121,125` | `proto void CallLater(func fn, int delay=0, bool repeat=false, void param1=NULL, ... void param9=NULL)`; `proto void Remove(func fn)` | Bound-method identity, retention, cancellation and invocation ordering |

The addendum resolves the previously missing queue declaring signature from the
installed function index. `ArmaReforgerScripted`'s diagram names ChimeraGame as
parent at line 118. This narrows an extraction gap; it does not verify the global
GetGame signature or the lifetime of scheduled instance methods.

The installed Widget documentation states that AddHandler adds a reference and
RemoveHandler releases it (lines 155 and 157). RemoveFromHierarchy removes the
widget from its parent and manager; destruction waits until strong references
are gone (lines 941-942). The event-handler documentation at lines 194-195
describes child-event bubbling and true as processed. These are documented
contracts, with no refreshed runtime validation in this packet.

The current chrome also explicitly retains each SPK_UIButton in its own `ref`
array. Keep that ownership and FindButton membership. Documented widget retention
does not settle receiver lifetime, retained cycles, callback delivery during
teardown or the behavior of a reopened UI.

The existing UI schedules RefreshTerrain at `Open():133-143`, may reschedule it
at `RefreshTerrain():1043-1055`, and removes view/root objects at `Close():1110`.
It also schedules ReportRootSize during widget setup. Close has no explicit
queue removal for those callbacks. This remains a source-observed lifetime
question, not a demonstrated bug. Test close-before-delivery, reopen-before-old-
delivery and world teardown before deciding whether removal or a generation
guard is needed. Any repair needs its own behavioral fixture; do not change
scheduling invisibly inside a supposedly exact migration.

The queue's detailed CallLater documentation at line 395 states that supplied
arguments remain retained until execution, removal or queue destruction. That
does not independently establish retention of a bound-method receiver or the
identity matching used by Remove. Those distinct questions need specific tests.

The full existing SPK_ScreenRT remains a service adapter. Its source at lines
92-114 binds an owner using SetRenderTarget, then removes the target before
clearing the owner on Disable; Destroy disables before removing the widget.
The selected capture has no RTTextureWidget declaration file. The existing
self-test source explicitly distinguishes structural screen checks from binding
a real entity. Capture that API and test live binding/teardown before extending
the screen adapter's verified contract. No render-target failure is demonstrated
by this inventory.

## 5. Resources, tooling and current admission gaps

Keep the existing addon GUID `4008B09320C27BA6`, dependency `58D0FB3206B6F859`,
prefab `{B37EEB64E149CBAD}Prefabs/SPK_Tablet.et`, model reference
`{BB50496D23063970}Assets/Tablet/SPK_Tablet.xob`, inventory-attribute identity
`{6A2000000000A001}` and editable UI-info identity `{6A5000000000E001}`.
The prefab contains one tablet, one gadget and one existing input component.
Its model/material/binary dependency closure is still not captured or loaded.
An initial lockfile must seed those existing identities and resolve every
reference before a generated prefab becomes promotable.

The captured `.xob.meta` also references material GUID `2E845CA43E3FFF43` and
platform import configurations. Those references are part of the unresolved
closure, not permission to regenerate the model or infer missing-resource errors.

The captured compiler feature registry accurately separates experimental IR,
strict-v1 exports and unavailable whole-mod authoring. Its 35 selected binding
declarations are extraction context; `verified_contract` remains unavailable.
No API-table change, complete typed binding system, v2 schema, tablet generation
or tablet runtime scenario was installed during this recovery.

The strict v1 schema has no component inheritance, callbacks, typed editor
properties, resources, prefab composition or layout/event profile. V1 validation
must remain unchanged. Structurally valid future v2 data must still fail target
admission if its specific capability is unavailable.

The existing immutable artifact/source-map/session transport is the integration
foundation. The plugin's 17 captured top-level scripts identify the source tools
that need per-operation identity checks; metadata or script hashing alone does
not prove the plugin is installed or active. Do not create a second bridge.

New generated origins must cover descriptors, superclass calls, callback
branches, properties, UI adapters, default expansion and companion JSON pointers.
Raw diagnostics must remain available when exact mapping is unavailable. Do not
interpolate an unsupported column into a plausible authored position.

Existing UI/screen/click/prefab tests remain useful source fixtures. They were
not executed here, and their source does not establish equip behavior, real
hit-testing or client authority. The captured installed scenario registry has
no tablet lifecycle or widget-event scenario.

## 6. Smallest next implementation packet: P4-A contract admission

Objective: make the selected tablet boundary machine-checkable before generating
or replacing a production component. This packet is proposed, not completed.

1. Add a versioned, bounded typed contract bundle and loader using exact
   declaring identities and source hashes. Keep extracted signatures, reviewed
   source-order requirements and runtime evidence as separate fields/states.
   Unknown nullability, retention, authority and reentry facts stay unknown.
2. Admit only ScriptComponent descriptor/instance pairs and the three exact
   tablet callback signatures initially. Add the gadget hierarchy only when
   its base-chain and required enum/property evidence are resolved. Reject an
   unresolved callback instead of inserting arbitrary EnforceScript strings.
3. Define one strict v2 component profile alongside v1, containing typed parent
   references, public identities, callback-to-Beryl symbols and reviewed service
   references. Validate in `mod check` and describe available/unavailable stages
   in `mod plan`. Generation/promotion stays unavailable until implemented.
4. Specify the Beryl/service boundary as a synchronous, statically bounded
   protocol: observe state, perform the same reviewed call, observe its result,
   commit at the baseline point and continue. No per-frame action List, queued
   mutation or engine object in an ordinary Beryl value record is needed.
5. Add isolated declaration/admission fixtures and negative cases: wrong
   instance/descriptor parent, mismatched callback argument/return, private
   property, unknown enum, duplicate production name, missing contract, stale
   API/engine hash and v2 fields incorrectly accepted by v1. Check exact
   companion JSON-pointer diagnostics. These checks launch no engine.

Dependencies: the integration owner's current compiler repair/verification
checkpoint; unchanged v1 regressions; declaration identity; a bounded loader;
an explicit decision about unresolved contracts. Do not rely on the unknown
working compiler executable or make old engine receipts apply to new bytes.

Potential affected consumers are the binding registry/context, companion schema
and validator, mod plan, generated-origin format and capability inventory. The
compiler's ordinary AST path and reviewed engine services remain separate.
Source-controlled typed templates may implement the later generator; project
descriptions may not supply shell commands or engine-code strings.

P4-A is complete only when CLI/MCP context and validation agree about exactly
this admitted profile, the positive/negative fixtures pass, and unavailable
generation/engine evidence is reported honestly. It does not close P4, P5 or R2.

The following [P4-A implementation packet](P4_COMPONENT_ADMISSION.md) now records
that bounded admission checkpoint: 102 pure validator cases and 10 real CLI/MCP
workflow groups passed against the identified private candidate. The implemented
profile covers plain ScriptComponent state and three callback signatures only.
Property/gadget admission and generated wrappers remain outside it; the broader
inventory above is not a claim that those capabilities shipped.

## 7. Following packet and release gates

After P4-A, implement plain tablet state/cadence logic and generated
SPK_TabletComponent descriptor/instance wrappers in an isolated addon. Keep
engine identities in the reviewed wrapper and use plain bool/i32/f32 state in
Beryl. Preserve synchronous result-dependent calls and visibility of committed
state during reentry; an action sequence computed without service results is
insufficient. The three-state feature does not require general Map ownership or
a full MESH store migration.

Retain the original implementation outside production script discovery and
compare ordered service traces and state after every operation. Required cases
include failed opening, degraded opening, missing input/core, duplicate toggles,
all three states, superclass order, intermediate stow screen transitions,
exact/below/above telemetry thresholds, large/zero/negative finite timesteps,
close/reopen accumulator preservation and destruction. Deliberate mutants must
detect skipped calls, reordered commits, duplicate population and cadence changes.

Then admit the gadget, inherited properties, map-mode fragment and owned prefab
in separate bounded packets as their contracts pass. Preserve exactly one
production definition for each migrated class. A working pure helper while the
old component still performs the entire lifecycle does not satisfy the selected
feature gate.

Execution gates remain distinct: analytical/reference/native checks; exact
Workbench compilation; engine-executed original/generated comparison; host
lifecycle; dedicated server with two independent clients; ultrawide and
1920x1080 interaction; resource/lifetime/rollback checks. Missing clients or
other capabilities leave their release gates open. Source inspection is useful
preparation and cannot substitute for any executed gate.

Only the exact verified candidate may later be promoted into compiler-owned
destinations with matching expected prior hashes. Keep original fixtures,
handwritten services, dirty changes and rollback artifacts intact. This recovery
packet authorizes no live MESH edit or promotion by itself.
