# P4/P5 tablet lifecycle contract inventory

Status: source inventory and implementation boundary, 2026-09-07. The tablet
migration described here is not implemented or engine-validated by this packet.
The inventory made no changes to MESH and launched no editor or game session.

The selected feature is the existing tablet's equip/open/close lifecycle and
telemetry cadence, with its real component, property, input, prefab and a bounded
UI event slice. It is not a new tablet or a replacement flight/control system.
The smallest meaningful UI slice is the existing **2D/3D map-mode button**.

## 1. Evidence identity and limits

The retained read-only inputs are in
[tablet-inventory-teqbgmaf](../../build/tablet-inventory-teqbgmaf/source-evidence.json).
That manifest's SHA-256 is
`bedcb75fed18e194b1e3985720696c76e98bc579085e0949c0495166be3ee754`.
It lists 37 files, their absolute source paths, byte lengths, line counts, hashes,
capture time and retained copies. Each original was rehashed after copying.
The hash table at the end of this packet identifies exactly which source bytes
support the inventory. This is a selected-feature capture, not a complete MESH,
engine installation or asset dependency snapshot.

Source prefixes used below:

| Prefix | Absolute root |
|---|---|
| `mesh/` | `C:/Users/moham/Documents/My Games/ArmaReforgerWorkbench/addons/SparkOS_Mesh` |
| `ui/` | The `mesh/` root plus `scripts/Game/SparkOSMesh/UI` |
| `input/` | The `mesh/` root plus `scripts/Game/SparkOSMesh/Input` |
| `core_api/` | `C:/Program Files (x86)/Steam/steamapps/common/Arma Reforger Tools/Workbench/docs/EnfusionScriptAPI/html` |
| `arma_api/` | `C:/Program Files (x86)/Steam/steamapps/common/Arma Reforger Tools/Workbench/docs/ArmaReforgerScriptAPIPublic/html` |
| `plugin/` | `C:/Users/moham/Desktop/reforger-workbench-plugin` |
| `brand/` | `C:/Users/moham/Desktop/sparkos-brandkit` |
| `beryl/` | `C:/Users/moham/Desktop/beryl` |

The installed `Workbench/ArmaReforgerWorkbenchSteamDiag.exe` was read, not run.
Its file and product versions were both `1.8.0.13`; its SHA-256 was
`7dd36ca1f662b0c13669a4f2f7f10e3c461c2906b021e742272d64b3ab7e9798`.
This matches the current extracted binding registry's engine identity. It does
not establish which project any running editor has loaded.

Line references name the original text files and are one-based. Installed
Doxygen declaration text is evidence of a documented interface, not automatic
evidence of ownership, retention, callback delivery, authority or runtime success.
MESH comments explain intent; executable statements establish the baseline here.

## 2. Existing lifecycle and exact seams

### Public component identity

`ui/SPK_TabletComponent.c:1` defines `ESPK_TabletState` with `STOWED`, `HELD`,
`FOCUSED`, in that order. The descriptor class at line 9 is
`SPK_TabletComponentClass : ScriptComponentClass`, with
`ComponentEditorProps(category: "SparkOSMesh", description: "MESH operator tablet")`.
The instance class at line 19 is `SPK_TabletComponent : ScriptComponent`.

| Current member | Contract to preserve |
|---|---|
| `SPK_ScreenRT GetScreen()` at line 30 | Returns the existing object reference; may be null before allocation |
| `SPK_TabletUI GetUI()` at line 37 | Returns the live UI object; may be null before first focus |
| `ESPK_TabletState GetState()` at line 62 | Reports current local component state |
| `bool Focus()` at line 69 | Only begins from HELD; success depends on UI opening |
| `bool Unfocus()` at line 102 | Only changes FOCUSED to HELD |
| `void SetHeld(bool held)` at line 117 | Preserves the existing ordered unfocus/stow side effects |
| `override void OnPostInit(IEntity owner)` at line 133 | Calls superclass first, sets STOWED, then requests FRAME events |
| `override void EOnFrame(IEntity owner, float timeSlice)` at line 150 | Marker update and bounded telemetry cadence while focused |
| `override void OnDelete(IEntity owner)` at line 171 | Closes UI, destroys screen target, then calls superclass |

State includes `float m_fTelemetryAccum`, the enum, `ref SPK_TabletUI m_UI` and
`ref SPK_ScreenRT m_ScreenRT`. Engine/UI references must stay references in a
reviewed adapter; they are not independent Beryl record copies.

### State transitions include observable work

`SyncScreen()` at line 47 enables the in-hand screen only in HELD. It lazily
allocates `SPK_ScreenRT`, calls `Enable(GetOwner())`, and ignores the returned
boolean. In other states it disables an existing screen. The first migration
must preserve this behavior; failure recovery is a separately specified change.

`Focus()` rejects any state except HELD without opening UI. It lazily creates
the UI and calls `Open()`. If opening fails it returns false before committing
FOCUSED. After successful opening it looks up `SPK_DroneInputComponent` on its
owner. If present, it passes that object and `input.GetKeybinds()` into the UI.
If absent, it logs an error but still commits FOCUSED, synchronizes the screen,
and returns true. Treating missing input as a failed focus would change behavior.

`Unfocus()` closes an existing UI before setting HELD and synchronizing the
screen. `SetHeld(true)` changes STOWED to HELD if needed and calls `SyncScreen`
even if the state did not change. `SetHeld(false)` calls `Unfocus()` first,
then sets STOWED and calls `SyncScreen()` again. Consequently, stowing a focused
tablet currently performs UI close, HELD screen enable, and STOWED screen disable
in that order. Collapsing this to the final state alone is not an exact port.

Use ordered adapter-call traces as the transition oracle. A state equality
assertion alone would miss failed opening, missing input, duplicate callbacks,
superclass order, and this intermediate screen transition.

### Cadence is precise behavior, not a new scheduling policy

The interval is the class constant `TELEMETRY_INTERVAL_S = 0.25` at line 23.
For each FRAME callback, the component:

1. Returns unless state is FOCUSED and the UI reference exists.
2. Calls `m_UI.UpdateMarkers()` once.
3. Adds `timeSlice` to `m_fTelemetryAccum`.
4. Returns when the accumulator is less than 0.25.
5. Sets the accumulator to zero and calls `RefreshTelemetry()` once.

There is no catch-up loop, remainder subtraction, or accumulator reset on close
and reopen. This component does not reject nonpositive `timeSlice`; the separate
input poller does. Preserve grouping, f32 storage and call order for admitted
finite input sequences, including zero/negative steps and large steps. Do not
silently add a clamp, faster cadence, tick decimation or a new editor-tunable
interval as part of the compatibility port. Nonfinite behavior requires an
explicit domain decision and engine evidence before it is advertised.

### Gadget integration

`ui/SPK_TabletGadget.c:2` defines
`SPK_TabletGadgetComponentClass : SCR_GadgetComponentClass`; its instance class
at line 18 extends `SCR_GadgetComponent`. Preserve both exported names and
descriptor inheritance.

`override EGadgetType GetType()` at line 23 returns `EGadgetType.GPS`.
`override void OnToggleActive(bool state)` at line 29 calls the superclass
first, then checks `IsLocalOwner()`. This helper at line 82 requires a non-null
`GetCharacterOwner()`, a non-null player controller, and identity equality
between `pc.GetControlledEntity()` and the character owner.

After the local-owner check, the gadget finds `SPK_TabletComponent` on the same
entity. Absence logs an error and returns. A false toggle calls `SetHeld(false)`
and returns. A true toggle calls `SetHeld(true)`, calls `Focus()`, and populates
the UI only if focus returned true.

`PopulateTablet(SPK_TabletComponent tablet)` at line 65 takes the live UI,
passes `SPK_MeshCore.GetInstance().GetAssets()` when a core exists, otherwise
logs a warning, then refreshes contact rows and order availability. Keep this
open-time behavior and existing shared asset identity. This packet does not
redefine the MESH store, serialize assets or create detached entity snapshots.

### Input integration remains a single existing poller

`input/SPK_DroneInputComponent.c:15` is already the component that polls tablet
and drone input. `GetKeybinds()` at line 49 lazily creates and initializes the
existing keybinding service. `OnPostInit` at line 81 calls the superclass,
initializes keybindings and requests FRAME events.

`EOnFrame` at line 90 returns when disabled or `timeSlice <= 0`, obtains the
input manager, then polls systems, tablet toggle, sensor controls and flight
controls under their existing conditions. Do not add a second tablet poller or
move the existing tablet poll after the autonomy early return.

`PollTabletToggle(InputManager im)` at line 195 checks
`GetActionTriggered(SPK_DroneActions.TABLET_TOGGLE)`, finds the same-owner
gadget, its character holder and the holder's gadget manager, and returns on
missing prerequisites. It calculates `wantOpen` as false only when the tablet
exists and is FOCUSED, then calls
`gadget.ToggleActive(wantOpen, SCR_EUseContext.CUSTOM)` at line 222.

That synchronization route must remain intact. Directly setting a local Beryl
state flag is not an equivalent replacement. The manager lookup is retained
even though its result is used as a guard rather than the receiver of the final
call. Its safety justification still needs reviewed engine implementation or a
bounded runtime probe; do not remove it merely because a compiler calls it unused.

`input/SPK_DroneActions.c:78` identifies `SPK_TabletToggle`; the BuildTable entry
at line 118 labels it "Raise Tablet" with default key `G`. The separate map-mode
action is already present. `SPK_DroneKeybinds.RegisterDefaults()` at line 34
checks existing keyboard bindings before adding defaults and saves only when it
adds bindings. Preserve user rebinds and derive displayed hints from the actual
keybinding service; do not bake the letter G into the generated UI contract.

## 3. Minimum complete companion/UI slice

### Existing property and prefab

The pilot can expose the existing typed editor property
`SPK_DroneInputComponent.m_bEnabled`, whose attribute has default `"1"` and
description `"Poll operator input"` at lines 17-19. This does not require
inventing a new telemetry tuning feature. Preserve the input component's
unrelated collective/gimbal/zoom rate properties and implementation.

The companion description must refer to this reviewed existing property and
its owning component. It must not synthesize a second property with the same
purpose on `SPK_TabletComponent`. Gadget prefab values also require typed
bindings to their actual inherited properties and enum definitions.

`mesh/addon.gproj` establishes ID `SparkOSMesh`, GUID `4008B09320C27BA6`, and
dependency `58D0FB3206B6F859`. `mesh/Prefabs/SPK_Tablet.et.meta` identifies the
existing prefab as `{B37EEB64E149CBAD}Prefabs/SPK_Tablet.et`. The prefab contains:

| Existing element | Preserve in the first candidate |
|---|---|
| `GenericEntity` with `MeshObject` | Object `{BB50496D23063970}Assets/Tablet/SPK_Tablet.xob` |
| `InventoryItemComponent` | Existing `SCR_ItemAttributeCollection` and its identity |
| `SPK_TabletComponent` | Exactly one component using the generated public class |
| `SPK_TabletGadgetComponent` | `m_eUseMask 15`, `m_eAnimVariable MAP` |
| `SPK_DroneInputComponent` | Existing poller and property semantics; exactly one instance |
| `SCR_EditableEntityComponent` | Existing UI-info identity, name and description |

The `.xob.meta` points to the current material and import configuration. The
binary model/material closure is not captured here. Before generating a
candidate prefab, resolve and hash the entire referenced resource closure and
check every stable ID. Do not regenerate the model, invent a GUID, or interpret
this text inventory as a successful prefab load.

### Reuse the actual map-mode button

The current tablet is constructed programmatically. No tablet `.layout` file
was identified in the selected source inspection. A new companion UI fragment
must describe the existing construction contract or a separately verified engine
template; this packet does not prescribe an invented layout serialization.

`ui/SPK_TabletChrome.c:247` builds `HeaderBar`. Lines 262-263 create:

```text
name: Btn_MapMode
initial label: 2D
action: SPK_UIAction.TOGGLE_MAPMODE ("toggle_mapmode")
index: -1
parent: existing HeaderBar
Place arguments: 0, 0, 0, 1, 250, 8, 320, -8
```

These are arguments to the existing `SPK_TabletChrome.Place` helper at line 64,
which negates right/bottom offsets before passing them to `FrameSlot.SetOffsets`.
They must not be copied blindly into a raw FrameSlot JSON representation.

`MakeButton` at line 127 creates the `ButtonWidget`, adds the `_Label` child,
constructs an `SPK_UIButton`, attaches it, and retains the handler in the
chrome's `array<ref SPK_UIButton>`. `FindButton` at line 146 later searches those
handlers. A generated fragment must remain part of that retained handler set;
merely drawing another clickable widget would break lookup/lifetime assumptions.

Use one deliberate source seam in the handwritten `BuildHeader`: invoke the
generated fragment factory in place of the existing two statements. The factory
can initially call reviewed `MakeButton`/`Place` adapters to preserve all hidden
construction details. This is an authored integration edit to handwritten code,
not a manual correction to generated output. Repeated generation must produce
exactly one `Btn_MapMode` and one callable event binding.

`ui/SPK_UIButton.c` contains all three relevant declarations:

| Declaration | Exact interface / behavior |
|---|---|
| `SPK_UIAction` at line 7 | `TOGGLE_MAPMODE = "toggle_mapmode"` at line 16 |
| `SPK_IUiActionReceiver` at line 43 | `void OnUiAction(string actionId, int index)` at line 46 |
| `SPK_UIButton` at line 55 | Extends `ScriptedWidgetEventHandler` |
| Constructor at line 66 | `(string actionId, int index, SPK_IUiActionReceiver receiver, int idleColour, int hoverColour)` |
| `SetEnabled(bool enabled)` at line 94 | Updates enabled state and presentation |
| `Attach(Widget w)` at line 108 | Stores target and calls `AddHandler(this)` |
| `override bool OnClick(Widget w, int x, int y, int button)` at line 118 | Returns false if disabled/no receiver; otherwise dispatches action/index and returns true |

The current click handler does not filter a particular mouse button. Do not add
such a filter during the port. Hover/disabled colors and the retained receiver
must also survive regeneration. A UI event description with no resolvable
callable handler must fail before producing a promotable artifact.

`SPK_TabletUI.OnUiAction` at line 522 already handles `toggle_mapmode`: it calls
`ToggleMapMode()`, then sets `Btn_MapMode_Label` to `3D` for MODE_3D or `2D`
otherwise. The pilot should generate the binding/dispatch slice while keeping
the actual map/render services behind reviewed adapters. All other UI actions,
manual control, orders, sensors, datalink and assets remain their current services.
This local map-mode action must not acquire a new networking protocol.

### Theme and display contract

Reuse `SPK_TabletTheme` tokens rather than duplicating literal colors in the
compiler. `MakeButton` supplies GRAPHITE and SELECTED_BG; disabled handlers use
TEXT_FAINT. The theme converts authored ARGB through `Color.FromIntSRGB`.
The MESH theme and brand README establish a project-owned design convention;
the compiler itself must not reserve amber/green meanings for every Beryl user.

`SPK_TabletUI.BuildWidgets()` at line 191 uses rendering resolution and workspace
fallbacks with DPI unscaling. Preserve this sizing seam and check both the user's
ultrawide display and 1920x1080. Property validation, a screenshot and direct
handler invocation establish different things; none substitutes for hit-testing,
clipping, focus, rebind hints, close/reopen or disabled-state interaction review.

## 4. Installed declaration evidence and semantic gaps

The following signatures were read from installed Doxygen member rows. HTML
line anchors refer to the captured files, not a remotely assumed API version.
Trailing implementation semantics are intentionally kept separate.

| Installed file / line | Visible declaration or documentation | Still needs review or execution |
|---|---|---|
| `core_api/interfaceScriptComponent.html:128` | `proto external GenericEntity GetOwner()` | Owner validity during deletion/callback reentry |
| same, line 137 | `proto external int SetEventMask(notnull IEntity owner, int mask)` | FRAME delivery, lifetime and mask inheritance |
| same, lines 210, 238, 240 | `void EOnFrame(IEntity owner, float timeSlice)`; `void OnPostInit(IEntity owner)`; `void OnDelete(IEntity owner)` | Actual callback ordering and superclass obligations |
| `core_api/interfaceIEntity.html:278` | `proto external Managed FindComponent(TypeName typeName)` | Nullability, cast compatibility and retention |
| `arma_api/interfaceSCR__GadgetComponent.html:140` | `void OnToggleActive(bool state)` | Local/remote delivery and duplicate callback behavior |
| same, line 154 | `void ToggleActive(bool state, SCR_EUseContext context)` | Authority, rejection, delivery latency and character lifecycle |
| same, lines 160, 162 | `ChimeraCharacter GetCharacterOwner()`; `EGadgetType GetType()` | Null holder during equip/drop/death and concrete GPS behavior |
| same, lines 202-203 | `EGadgetAnimVariable m_eAnimVariable`; `SCR_EUseContext m_eUseMask` | Reviewed enum values/property loading; protected access is recorded in detailed sections |
| `arma_api/interfaceSCR__GadgetManagerComponent.html:171` | `static SCR_GadgetManagerComponent GetGadgetManager(IEntity entity)` | Existence and validity at every gadget transition |
| same, line 161 | `void AskToggleGadget(SCR_GadgetComponent gadgetComp, bool state)` | Server validation and actual synchronization outcomes |
| `arma_api/interfacePlayerController.html:121` | `proto external IEntity GetControlledEntity()` | Ownership changes and independent-client behavior |
| `arma_api/interfaceChimeraGame.html:127` | `proto external PlayerController GetPlayerController()` | Dedicated-server/null and transition behavior |
| `core_api/interfaceInputManager.html:172` | `proto external bool GetActionTriggered(string actionName)` | Consumption/edge delivery and keyboard/context behavior |
| `core_api/interfaceWorkspaceWidget.html:153` | `proto external float DPIUnscale(float valueInPhysicalResolution)` | Actual DPI/layout result at target resolutions |
| same, line 155 | `proto external Widget CreateWidget(WidgetType type, WidgetFlags flags, Color color, int sort, Widget parentWidget=NULL)` | Parent/child ownership, null failure and visibility |
| same, line 157 | `proto external Widget CreateWidgetInWorkspace(WidgetType type, int left, int top, int width, int height, WidgetFlags flags, Color color, int sort)` | Root lifetime, focus and renderer interaction |
| `core_api/interfaceFrameSlot.html:134` | `static proto void SetOffsets(notnull Widget widget, float left, float top, float right, float bottom)` | Correct slot interpretation after existing Place conversion |
| same, lines 143-144 | `SetAnchorMin` / `SetAnchorMax` with widget and float x/y | Measured layout and pixel rounding |
| `core_api/interfaceWidget.html:154` | `proto external void AddHandler(ScriptedWidgetEventHandler eventHandler)` | Whether widget retention alone is sufficient; preserve explicit MESH retention meanwhile |
| same, lines 156, 194 | `RemoveHandler(...)`; `RemoveFromHierarchy()` | Callback detachment, retained references and destruction timing |
| `core_api/interfaceScriptedWidgetEventHandler.html:127` | `bool OnClick(Widget w, int x, int y, int button)` | Actual routed input and bubbling behavior |
| `core_api/interfaceScriptCallQueue.html:121` | `proto void CallLater(func fn, int delay=0, bool repeat=false, ... optional param1 through param9 ...)` | Callback binding identity, lifetime and cancellation ordering |
| same, line 125 | `proto void Remove(func fn)` | Exact matching/removal behavior for a scheduled instance method |

The detailed gadget docs describe `OnToggleActive` as an event from the manager
through an RPC request, describe `ToggleActive` as synchronizing gadget state,
and describe protected `RPC_AskToggleGadget` as an RPC to the server. These
support preserving the existing synchronization route. They do not prove that
an arbitrary caller is authorized or that host-only results cover clients.

`GetGame().GetCallqueue()` appears in the live UI and in the queue's documentation
examples. Its exact declaring-class signature was not resolved in this selected
declaration capture. Resolve it before admitting a direct generated binding;
do not turn an example call into an invented verified declaration.

`SPK_ScreenRT` remains an adapter: defaults are 4 FPS and resolution scale 0.5,
`Build()` at line 44 creates the target, `Enable(IEntity)` at line 92 rejects
null/failed construction, `Disable()` at line 108 removes the existing entity
target, and `Destroy()` at line 126 disables then removes the widget hierarchy.
Its render-target API signatures and complete lifetime semantics are not part
of this bounded declaration capture. The pilot must either review that contract
or leave the entire existing implementation intact behind its adapter boundary.

## 5. Minimum Beryl and tooling prerequisites

The initial pure logic needs bool, a three-state enum or explicitly checked
integer tag, f32 accumulator/interval, ordinary functions, explicit mutable
state access, conditionals and ordered calls. Records must contain only admitted
plain values. They must not contain engine entity/widget/service objects merely
because the EnforceScript target represents ordinary records as classes.

Adapters need a separately reviewed type category for engine identities with
explicit nullable lookup, validity, access and retention contracts. An initial
bounded generator can keep those objects wholly in generated EnforceScript
wrappers and feed plain observations/results into Beryl functions. That is a
deliberate foreign boundary, not proof that Beryl already supports every engine
type, function pointer, inheritance feature or reference container.

A single precomputed "final state" is insufficient for Focus/Unfocus/SetHeld.
Use an ordered, statically bounded adapter protocol with state commitment at the
same points as the baseline: prepare/check, perform the required call, inspect
its result when the original does, then commit/continue. Keep synchronous calls
synchronous. Do not postpone them to a generic queue or allocate an action List
per frame. Reentry assumptions must be reviewed; an adapter cannot advertise
purity just because the Beryl-facing values are scalar.

The captured `schemas/beryl.mod.v1.schema.json` supports addon identity, source
sets, a target/version binding and class exports with optional constructor and
method mappings. It rejects unknown fields. It does **not** yet describe engine
inheritance, component descriptors, editor properties, callbacks, resource/prefab
composition or layout/event fragments.

Add a separately versioned bounded companion profile with typed references for
the selected feature. Preserve v1 validation and behavior. The extension must:

- Resolve actual exported symbols and callback signatures, including descriptor
  and instance inheritance; reject duplicated production class names.
- Type-check existing editor properties and enum values against reviewed engine
  declarations rather than accepting arbitrary name/value pairs.
- Resolve stable resource IDs and reject missing/duplicate resources before
  promotion; preserve unrelated prefab components and resource metadata.
- Require each UI event to resolve to its actual action/receiver and lifetime
  owner; preserve stable widget identities, disabled behavior and FindButton.
- Generate all wrappers/factories from typed data. Do not embed project-provided
  code strings, shell commands or arbitrary build hooks in the description.
- Include ordinary statements, superclass calls, attributes, defaults, wrapper
  branches and companion JSON pointers in provenance; retain raw engine logs.

Current `tools/beryl-mod/mod.py` already stages generated output, attaches source
maps and companion pointers to class exports, records artifact identities,
verifies through the existing Workbench tools, and promotes only owned outputs
under hash/ownership checks. Extend this pipeline instead of introducing another
bridge or asking an assistant to edit generated EnforceScript.

Current source maps describe line spans and outermost default-expansion origin.
They do not justify exact engine-column interpolation. New wrapper/companion
origins require explicit mappings; unknown locations must remain unknown rather
than guessed. Test a deliberate callback signature error and UI property error
all the way from raw Workbench diagnostic to the responsible authored location.

The extracted binding registry currently supplies 35 selected declarations as
an authoring aid, with `verified_contract` unavailable. It is not a complete
engine typechecker or executable binding system. Add the selected tablet
declarations and separately reviewed annotations only when their sources and
bounded evidence exist. Missing coverage must remain explicit in shared AI
context; neither assistant may infer support from this inventory.

## 6. Existing tests versus required acceptance

The source of `mesh/scripts/WorkbenchGameCommon/SPK_MeshSelfTest.c` contains
useful checks. Reading them here did not execute them or refresh older receipts.

| Existing suite / source line | What its source actually checks | Gap for this migration |
|---|---|---|
| `RunUiSuite`, line 330 | Calls `BuildWidgets`, verifies widget structure and mode toggling | Does not exercise Open's world/map path, real equip or routed input |
| `RunScreenSuite`, line 511 | Build/verify, rejects `Enable(null)`, Disable and repeated Destroy | Does not prove a live entity render-target bind/release lifecycle |
| `RunClicksSuite`, line 1516 | Action/handler coverage, retained chrome controls, direct `OnClick`, disabled and reenabled handler behavior | Direct invocation is not UI hit-testing, focus or every real action body |
| `RunPrefabAuditSuite`, line 2169 | Loads/checks declared component structure | Does not prove equip, authority, replication or visual interaction |

The captured Beryl scenario registry contains map cursor, terrain comparison,
array storage, Canvas retention and terrain construction measurement entries;
selected MESH traces remain unavailable. It has no tablet lifecycle or tablet
UI scenario. Implement and register those through the existing transport with
exact selected-case counts and complete receipts. Do not relabel unrelated
scenario success as tablet validation.

Required cases for the bounded tablet milestone:

1. **Pure transition traces:** each state and operation; duplicate true/false
   toggles; focus from STOWED/FOCUSED; failed UI creation/open; missing input;
   missing tablet/core; all boolean returns and ordered adapter calls.
2. **Cadence traces:** below/exact/above 0.25; several small steps; large step
   refreshes once; zero and negative finite step; accumulator retained through
   close/reopen; no marker/telemetry calls while not focused; marker precedes
   telemetry in each observed frame. Use explicit f32 expected values.
3. **Component/gadget traces:** superclass call order; local/remote owner checks;
   absent player controller/holder/manager; GetType GPS; actual existing input
   route and unchanged rebind behavior; no duplicate FRAME input consumption.
4. **Generated interface:** exactly one descriptor/instance definition for each
   production class, exact signatures and attributes, stable prefab/resource
   identities, typed property defaults, deterministic output and regeneration
   without manual generated edits.
5. **UI fragment:** exactly one Btn_MapMode/label, actual callable binding, correct
   initial label and subsequent 2D/3D label, FindButton retention, disabled and
   reenabled behavior, open/close/reopen, handler detachment and no duplicate
   callbacks after repeated generation or repeated opening.
6. **Engine comparison:** retained original outside production discovery and
   generated candidate compare the same bounded traces. Then compile and load
   the complete isolated MESH candidate; run existing relevant self-tests plus
   the new scenarios with immutable source/compiler/tool/engine identities.
7. **Deployment:** equip, stow, switch item, drop/destroy, death/respawn, missing
   services, reset/handover and rapid reopen using actual engine interactions.
   Trace requested gadget state separately from observed synchronized state.
8. **Multiplayer and visual:** host plus dedicated server/two independent clients;
   remote player toggle must not open local fullscreen UI; join/ownership changes,
   delayed/duplicate events; actual ultrawide and 1920x1080 clicks, input hints,
   clipping, focus, missing entities and stale telemetry presentation.

The current UI's `Open()` at line 133 schedules `RefreshTerrain` after 400 ms.
`RefreshTerrain()` at line 1043 may schedule another attempt when canvas size is
too small. `Close()` at line 1110 removes several view/root objects but has no
explicit queue cancellation and does not clear every terrain/chrome field.
This is a **source-observed lifetime question**, not a demonstrated engine bug.
Before declaring repeated close/reopen safe, establish callback retention and
cancellation semantics, test old callbacks against a destroyed or reopened UI,
and specify whether a generation/epoch guard or removal is needed. Such a repair
must have its own behavioral evidence; do not quietly change scheduling inside
the port and then call a different trace equivalent.

All proposed cases above remain pending in this packet. The pure checks,
Workbench compile, real engine scenarios, multiplayer and visual checks are
separate gates. Unavailable independent clients leave the multiplayer gate open.

## 7. Implementation boundary and handoff

The pilot should generate the tablet descriptor/instance adapters, gadget
descriptor/instance adapters, bounded plain `.be` transition/cadence logic,
the selected UI fragment/event binding, and an owned candidate prefab/resource
description. Retain current input polling and render/map/control services behind
reviewed adapters. A small handwritten adapter seam is permitted and must be
source-owned, tested and hash-tracked; generated outputs require no manual edits.

Completion requires the actual existing feature to work in a staged MESH
candidate with this authoring path. A pure helper that compiles while the old
component still performs all the behavior does not satisfy the whole-feature
gate. Conversely, porting unrelated networking, store ownership or every UI
control is not a prerequisite for this bounded feature.

Before implementation starts, reconcile current files against this capture and
record any changed contracts. Preserve the original behavioral fixtures outside
production discovery, preserve existing dirty work, and promote only verified
owned destinations with expected prior hashes. Keep a rollback artifact and
an exact component/resource ownership manifest. Broader use waits for its own
deployment and multiplayer gates.

## 8. Captured content hashes

The following table is generated from the retained manifest. API HTML files are
source evidence only; they are not added to the executable binding registry by
this packet.

| Source group / relative path | SHA-256 |
|---|---|
| `mesh/addon.gproj` | `63cc2c9f6e815e74629867520b5bdb71fb62971490997e32a0a2a7ffb02db1bc` |
| `mesh/Prefabs/SPK_Tablet.et` | `dabd491efd1b27cf49b311948c1215acf1982f06f6b6de8a0e9ea0e001ae0c22` |
| `mesh/Prefabs/SPK_Tablet.et.meta` | `7cf10f188f52b7724564b78e7999274854948665b48015ae130dcb7fea267b3a` |
| `mesh/Assets/Tablet/SPK_Tablet.xob.meta` | `aecc3e22af19aa3c50b7beecbde13f2eaa9e0c5335ad55a85cde8afce06ff6ca` |
| `mesh/scripts/Game/SparkOSMesh/UI/SPK_TabletComponent.c` | `1f15962cf67a8cc513d7068757e89360260016fadff1c8843719784acc94be3a` |
| `mesh/scripts/Game/SparkOSMesh/UI/SPK_TabletGadget.c` | `d336244b7d178324eded5bc5e584f721cd2c4f9b7036ac90d1f757ba30b0199c` |
| `mesh/scripts/Game/SparkOSMesh/UI/SPK_TabletUI.c` | `4efeab8cce793939d748506f34691aae9b0b47aa8b32ed568ece05accf28a05d` |
| `mesh/scripts/Game/SparkOSMesh/UI/SPK_TabletChrome.c` | `53c2fccfb900371ce0ea409d98f0903a20e71e472630e6caea87b29477a1811e` |
| `mesh/scripts/Game/SparkOSMesh/UI/SPK_TabletTheme.c` | `2e54d966e20af86da093a414b28b2faa5e2f5ffa49887e6668b6a9ebdaef00e7` |
| `mesh/scripts/Game/SparkOSMesh/UI/SPK_UIButton.c` | `24f45c2d5cc8dc050290047bf8a9c902f536cfd7e3fa5569b07410816cd03c9a` |
| `mesh/scripts/Game/SparkOSMesh/UI/SPK_ScreenRT.c` | `6328c5e86787b75c8cf949fcbd914c4fb137e17534a6158150bdba13818e942b` |
| `mesh/scripts/Game/SparkOSMesh/Input/SPK_DroneInputComponent.c` | `440a493229775ab18233c76020763d4c724adfb4fece3dc41e9ca26747e5695b` |
| `mesh/scripts/Game/SparkOSMesh/Input/SPK_DroneActions.c` | `faeb200d3da43ea30b4d2db36152b9d634f4b74bf21c1173b6dfc55ec829a113` |
| `mesh/scripts/Game/SparkOSMesh/Input/SPK_DroneKeybinds.c` | `1123a60363291343d858f3106896260060160a89b340085236b0437808a962ce` |
| `mesh/scripts/WorkbenchGameCommon/SPK_MeshSelfTest.c` | `59213fecdd4ecd1ced6e0eee0716b5c86bf3cc184ee6261452da9ac3c4dcda46` |
| `core_api/interfaceScriptComponent.html` | `215f2ca81f0d47cbe1dc61dd8471c73c5b5f78c623a247d5f82e8a1e6471c3de` |
| `core_api/interfaceIEntity.html` | `ec2e7f4c76ab91af50a9448ccd13db7aa7590ba3584fbfdacbd6773d899ec585` |
| `core_api/interfaceInputManager.html` | `b995ee864365543988d5021f989a487c615aa55c70a868329753610c73475b4a` |
| `core_api/interfaceWorkspaceWidget.html` | `8d6e1d305bdf44ac5d1b1fdd4b373674ef506e742bc81d838fa120ad1d5a91e5` |
| `core_api/interfaceFrameSlot.html` | `34a050d4562940c4bb449a5da845bc1c59fe4756007c451b5ab110d64a1872c9` |
| `core_api/interfaceWidget.html` | `26f153143555452828452363d8ce0fbbdf2fd38caf1dcae83228b65d4155f332` |
| `core_api/interfaceScriptedWidgetEventHandler.html` | `dbf725d2013bc3f51dc34a5e9743f28e810a7972e17766754c85cb289064cc92` |
| `core_api/interfaceScriptCallQueue.html` | `6d9b2b3b8c4eba71f80cf10e987b5ce191c7321ebe50365c15fdba1d6cc88763` |
| `core_api/interfaceGame.html` | `dfcab6b926646b8b56cdcbf38bb3e5f9809e96c9e3efaabc11cf806d6ec4b22e` |
| `arma_api/interfaceSCR__GadgetComponent.html` | `54b0375869e9570671e238f1c599732f68b8dc527fdf716a315a430a95c52187` |
| `arma_api/interfaceSCR__GadgetManagerComponent.html` | `8ffd9ba5121286f736e3085bc04e94236e47bf47238fd6e5c2145235a1376131` |
| `arma_api/interfacePlayerController.html` | `843159e829ddc2bce2e2b5778d1f84856deb1f884a5a9d5f9f7df4d33cb4fe1c` |
| `arma_api/interfaceChimeraGame.html` | `57e1dce7ed1236d1bf50a7762582cccadf7100424dac495184a4b9921739f362` |
| `plugin/README.md` | `8ca6d736c51ea821dea9b9668ef36f7deea69999ea21216adadc81e0244d3e15` |
| `plugin/scripts/Search-ReforgerSource.ps1` | `3990c4b96000d15285ef388c858fc31050a00d617268da319f5a658fe1458474` |
| `brand/README.md` | `3bf1d69a66955ca813819b6a58a1781bfef3318b98fcf8ad2f23de66bb251dd4` |
| `beryl/schemas/beryl.mod.v1.schema.json` | `619ad1693807d87827c5160353f00fab84e1578d5e553e939d8620bea80aee95` |
| `beryl/tools/beryl-mod/mod.py` | `9f6bfaabdb7b67d425e0772989efc4181e4a2623c01c874b021d10f328bfbe4e` |
| `beryl/tools/beryl-mod/scenarios.py` | `46cf0ae10f238918e1a5c7b4cf01a370c984ae31a4e30a0f6654cbf4a6d459d0` |
| `beryl/tools/beryl-mod/source_maps.py` | `76895d72d359d6a45685bc4f9008802acef054b3d8b7381d8b921952dd35334d` |
| `beryl/tools/beryl-bindings/README.md` | `01a49930d2618e5eb13d34919e6705964f7e59de508636ff6b59b94757be5d2a` |
| `beryl/tools/beryl-bindings/snapshot.json` | `e2d6d788a06b934f3337f68b632fada92573cb9c4ce2382ddde13865bb5616b7` |
