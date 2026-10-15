# P5 tablet service adapter: source contract and next implementation packet

Checkpoint: 2026-10-08, local time. Status: **source-reviewed contract proposal**.
This document specifies the next isolated adapter; it does not implement it.
No compiler, generated program, Workbench, game, or multiplayer session was run
while preparing this packet. No live MESH, plugin, engine, or existing evidence
file was changed. The integration owner owns engine execution and promotion.

## 1. Delivery boundary

Connect the existing Beryl scalar lifecycle protocol to the existing MESH services
through an explicit synchronous EnforceScript adapter. Preserve the public tablet
interface and each original state publication and service observation point.
Keep engine identities in the adapter, outside ordinary Beryl value copying.

The first adapter is an isolated comparison fixture. A successful generic component
compile is a prerequisite, not evidence that the tablet service adapter works.
Its initial claim must remain bounded to the precise classes, calls, inputs,
and engine identity that its own receipts cover.

The current protocol is
[lifecycle.be](C:/Users/moham/Desktop/beryl/packages/sparkos/tablet-lifecycle-prototype/src/lifecycle.be),
module `sparkos.tablet_lifecycle_prototype`. Its persistent state contains only
`mode: i32` and `telemetry_accumulator: f32`. Each invocation has its own
`Operation { kind, pc, screen_pc, held, time_slice, answer }`.
`next(inout state, inout operation, reply) -> i32` yields one service opcode.
It is not an asynchronous scheduler or a list of effects to apply later.

The existing
[prototype packet](C:/Users/moham/Desktop/beryl/docs/advanced/P5_TABLET_LIFECYCLE_PROTOTYPE.md)
records independent decision fixtures, actual Beryl reference execution, and a
bounded native comparison. Those receipts do not execute the real UI, screen,
input, queue, gadget, or rendering services. They do not establish the engine
receiver-evaluation, retention, validity, or multiplayer contracts below.

## 2. Source baseline and passive identity checks

The retained source root is
`C:/Users/moham/Desktop/beryl/build/tablet-recovery-1ae28bbb58d4499d808b467a390b6fc1/inputs/`.
The corresponding live MESH root is
`C:/Users/moham/Documents/My Games/ArmaReforgerWorkbench/addons/SparkOS_Mesh/`.
Paths in the table are relative to each root's MESH script directory,
`scripts/Game/SparkOSMesh/`. Lines below refer to retained files.

| Source | SHA-256 | Principal adapter contract |
|---|---|---|
| UI/SPK_TabletComponent.c | `1f15962cf67a8cc513d7068757e89360260016fadff1c8843719784acc94be3a` | State, synchronous services, callbacks |
| UI/SPK_TabletGadget.c | `d336244b7d178324eded5bc5e584f721cd2c4f9b7036ac90d1f757ba30b0199c` | Local UI ownership and population |
| UI/SPK_TabletUI.c | `4efeab8cce793939d748506f34691aae9b0b47aa8b32ed568ece05accf28a05d` | Open/close, setters, queue, marker and telemetry services |
| UI/SPK_ScreenRT.c | `6328c5e86787b75c8cf949fcbd914c4fb137e17534a6158150bdba13818e942b` | Screen construction, binding and teardown |
| Input/SPK_DroneInputComponent.c | `440a493229775ab18233c76020763d4c724adfb4fece3dc41e9ca26747e5695b` | Existing poller, toggle route, lazy keybind identity |
| Input/SPK_DroneKeybinds.c | `1123a60363291343d858f3106896260060160a89b340085236b0437808a962ce` | Actual bindings, registration and persistence |
| UI/SPK_TabletChrome.c | `53c2fccfb900371ce0ea409d98f0903a20e71e472630e6caea87b29477a1811e` | Handler storage and materialized hints |
| UI/SPK_UIButton.c | `24f45c2d5cc8dc050290047bf8a9c902f536cfd7e3fa5569b07410816cd03c9a` | Event dispatch and receiver/target fields |

All eight live files matched the retained hashes during the passive reads for this
packet. This observation does not freeze future live edits. The primary manifest,
[source-evidence.json](C:/Users/moham/Desktop/beryl/build/tablet-recovery-1ae28bbb58d4499d808b467a390b6fc1/source-evidence.json),
remains unchanged, SHA-256
`5be54c47925528e9f585c8dcd92d6988cfda6b82478d5e021fcf1f8080737a78`.

The protocol source is SHA-256
`34c2b848e94a7a68132804d08a58fcf31d644f2d0e9eb2b4973e84a39249f792`;
the independent source-order oracle is
`0aa242b1c56069b04403f3a2ab622e12f3432dbb5f22b12b2fe44345a94e5f30`.
These are input identities, not assertions of current compiler or engine success.

Workbench was passively hashed, without executing it:
`C:/Program Files (x86)/Steam/steamapps/common/Arma Reforger Tools/Workbench/ArmaReforgerWorkbenchSteamDiag.exe`,
67,576,376 bytes, SHA-256
`7dd36ca1f662b0c13669a4f2f7f10e3c461c2906b021e742272d64b3ab7e9798`.
It matched the manifest's executable identity; that manifest records metadata
version `1.8.0.13`. The passive check at `2026-10-09T00:35:52Z` is on October 8
in the workspace timezone. It is not a launch, compile, or runtime receipt.

## 3. Preserved public interfaces

| Class/interface | Existing inheritance and signatures | Required preservation |
|---|---|---|
| SPK_TabletComponentClass | ScriptComponentClass | Existing descriptor identity |
| SPK_TabletComponent | ScriptComponent | GetScreen(): SPK_ScreenRT; GetUI(): SPK_TabletUI; GetState(): ESPK_TabletState; Focus(): bool; Unfocus(): bool; SetHeld(bool): void |
| Component callbacks | OnPostInit(IEntity): void; EOnFrame(IEntity, float): void; OnDelete(IEntity): void | Original callback argument and ordering |
| SPK_TabletGadgetComponentClass | SCR_GadgetComponentClass | Existing gadget descriptor identity |
| SPK_TabletGadgetComponent | SCR_GadgetComponent | GetType(): EGadgetType; OnToggleActive(bool): void |
| SPK_TabletUI | SPK_IUiActionReceiver | Existing object, widget tree, actions and service methods |
| SPK_ScreenRT | Existing script class | Enable(IEntity): bool; Disable(): void; Destroy(): void; GetWidget(): RTTextureWidget; IsEnabled(): bool |
| SPK_DroneInputComponent | ScriptComponent | Existing input poller and GetKeybinds(): SPK_DroneKeybinds |

`GetUI()` and `GetScreen()` return the actual stored service references. They must
not produce detached Beryl snapshots or new service instances. `GetState()` maps
the plain mode to the existing enum symbolically: STOWED, HELD, FOCUSED. Reject
an unsupported internal mode in fixture admission; do not invent a fourth
gameplay state. Keep `EGadgetType.GPS`, `SCR_EUseContext.CUSTOM`, and
`EntityEvent.FRAME` as verified engine symbols, rather than guessed integers.

The gadget is a separate inheritance family. A ScriptComponent-only generation
profile does not authorize SCR_GadgetComponent generation. Preserve the current
gadget and input services initially, using the same public tablet interface.

## 4. State ownership and invocation-local bindings

There is one authoritative persistent Beryl state per tablet component. Each
synchronous entry creates a separate operation continuation. A reentrant entry
uses the same current state and its own continuation. The outer operation keeps
its PC and resumes after the service returns.

Do not run against a state copy and write it back at operation completion: that
would overwrite nested changes and hide the original intermediate state from
service calls. Generated parameter passing must be shown to preserve the same
state storage identity during the entire reentrant stack. The current protocol
updates fields and does not replace the state root.

The following host bindings are required. Their actual EnforceScript retention
strength and invalidation behavior must be verified; a local binding is not
automatically evidence that a deleted engine object remains valid.

| Binding | Lifetime/capture point | Contract |
|---|---|---|
| Component UI and screen fields | Component lifetime, original assignment points | Keep the existing `ref SPK_TabletUI` and `ref SPK_ScreenRT` behavior |
| Persistent plain State | Component lifetime | Share directly across nested operations; never publish a final batch |
| Operation | One synchronous invocation | Separate PCs/results; no component-wide active operation |
| Callback owner argument | Its original callback invocation | Use the supplied argument for superclass calls and event-mask registration |
| Screen Enable owner | Evaluate GetOwner at the original Enable point | Do not replace it with an owner captured when the outer callback began |
| Focus input | Capture the cast FindComponent result after successful Open | Reuse that exact input binding for SetInput and GetKeybinds, even if a later lookup would differ |
| Focus keybind result | Capture the result of that input's GetKeybinds | Pass the exact result to SetKeybinds; do not recreate defaults or substitute another poller's bindings |
| Method receiver | Capture/evaluate according to the verified EnforceScript call contract | Preserve the original expression's receiver and argument ordering |
| Gadget population UI | Local result of tablet.GetUI | Reuse this local UI for SetAssets, RefreshContactRows, RefreshOrderAvailability |
| Gadget population core/assets | Existing GetInstance/GetAssets expression points | Preserve the returned shared array and component identities |

The component's separate UI expressions read `m_UI` at their own source call
points; do not cache one UI for the whole Focus/frame/delete operation. Gadget
population deliberately captures a local UI once. Those are different source
contracts. Ordinary lifecycle entry points do not currently replace a nonnull
component UI reference, but this is not a complete effect/retention proof for
every engine callback, extension, or nested service.

### Receiver and argument ordering: bounded engine evidence

Focus line 90 is a nested expression:
`m_UI.SetKeybinds(input.GetKeybinds())`. The protocol splits GetKeybinds and
SetKeybinds into opcodes 6 and 7. The three-case plain-script engine probe in
`build/receiver-argument-order-bi6_dbc7/result.json` observed
`receiver_selected_after_arguments` and `arguments_left_to_right` on the pinned
1.8.0.13 engine (`7dd36ca1f662b0c13669a4f2f7f10e3c461c2906b021e742272d64b3ab7e9798`).
Opcode 6 therefore calls GetKeybinds on invocation-local input and retains that
result. Opcode 7 resolves the current `m_UI` after argument completion and passes
the retained result. Do not capture `m_UI` before GetKeybinds for this expression.
The probe establishes ordering for its admitted plain-script expressions; it did
not execute real tablet services, engine callbacks, queue receiver retention, or
multiplayer. Those contracts remain open. Apply the same source-expression review
to newly split nested service expressions, including core.GetAssets.

## 5. Exact synchronous service dispatch

Every nonzero opcode must be serviced immediately before resuming that operation.
Presence reads are direct field checks at the original source point. They are
not new engine method calls and do not introduce reentrant observation points.
Replies are invocation-local; a nested call must not overwrite the outer input,
keybind result, receiver binding, reply, owner argument, or continuation.

| Opcode | Adapter action | Reply and constraints |
|---|---|---|
| 0 | Return the operation's answer or complete the void callback | No service |
| 1 | Read whether the current component UI field is nonnull | 0/1; no allocation |
| 2 | Construct SPK_TabletUI and assign the component field at the original point | 0; retain the actual object |
| 3 | Call the source-selected UI.Open() synchronously | Exact bool as 0/1; no mode rollback |
| 4 | Cast GetOwner().FindComponent(SPK_DroneInputComponent), retain result locally | Presence 0/1; owner validity is a separate admission requirement |
| 5 | Call the source-selected UI.SetInput with the captured input | 0; no extra lookup or auto-binding |
| 6 | Call captured input.GetKeybinds, retain exact result locally | 0; source lazy registration may have effects |
| 7 | Resolve current UI after GetKeybinds completion and call SetKeybinds with the invocation-local result | 0; scoped receiver-order evidence is in Section 4 |
| 8 | Emit the existing missing-input error diagnostic | 0; exact branch, no fabricated input |
| 9 | Read whether the current screen field is nonnull | 0/1; screen presence differs from enabled state |
| 10 | Construct SPK_ScreenRT and assign the component field | 0; no eager widget construction |
| 11 | Call current screen.Enable(GetOwner()) at that source point | Bool 0/1, deliberately ignored by the decisions |
| 12 | Call source-selected screen.Disable() | 0; preserve original internal unbind order |
| 13 | Call source-selected UI.Close() | 0; no automatic cancellation, field clear, or mode change |
| 14 | Call super.OnPostInit with the invocation's original owner argument | 0; exactly once, before the STOWED write |
| 15 | Call SetEventMask(original owner, EntityEvent.FRAME) | 0; ignore returned mask as the original does |
| 16 | Call source-selected UI.UpdateMarkers() | 0; preserve effects, ignore returned count |
| 17 | Call source-selected UI.RefreshTelemetry() | 0; accumulator has already been reset |
| 18 | Call source-selected screen.Destroy() | 0; Disable before widget removal |
| 19 | Call super.OnDelete with the original owner argument | 0; exactly once, after UI and screen services |

Only reviewed internal opcodes/replies drive the adapter. They are not remote
commands or authorization tokens. Unknown opcodes, corrupt PCs, missing responses,
or inadmissible scalar state are fixture/protocol failures; do not issue guessed
services. The fixture's call/depth budgets are test limits, not new gameplay input
limits or permission checks. Production admission needs its own boundedness and
failure policy before the adapter can be enabled.

### One owner for superclass and frame-registration effects

The current generic renderer, component_generation.py lines 415-423, already
emits configured superclass calls and a post-init FRAME registration around a
plain void handler. The protocol independently yields 14, 15, and 19. Connecting
it unchanged would duplicate effects and alter reentry timing.

Use a separately admitted adapter wrapper policy with one owner of these effects.
For this protocol, the synchronous dispatcher must service 14/15/19 exactly where
yielded, and the surrounding wrapper must not emit them again. This requires a
new reviewed generation/admission capability. Do not bypass the current strict
catalog, reinterpret existing descriptions, insert arbitrary project code strings,
or manually repair the generated file. An alternative phased protocol needs a
new contract and replay corpus before removing those opcodes.

## 6. Required state publication and reentry behavior

1. **Post-init:** superclass first, then mode=STOWED, then FRAME registration.
   Preserve the accumulator, existing UI/screen references, and screen state.
2. **Focus:** admit only initial HELD; create/retain UI if absent; Open before
   input lookup and hookup; then mode=FOCUSED; then screen synchronization.
   Failed Open does not commit FOCUSED or restore a pre-call mode. Without
   reentry it leaves HELD; an intervening nested change survives the failure.
3. **Unfocus:** admit only initial FOCUSED; Close observes that state; then
   mode=HELD; then screen synchronization. Reentry does not authorize a rollback.
4. **SetHeld(true):** write HELD only from STOWED, but synchronize on every call,
   including repeated HELD and FOCUSED calls.
5. **SetHeld(false):** run the original Unfocus decision first. From FOCUSED,
   this includes Close, HELD publication and screen Enable. Then publish STOWED
   and synchronize again, producing Disable. Do not coalesce Enable/Disable.
6. **Frame:** test FOCUSED/UI presence once; call markers; add timeSlice to the
   current shared binary32 accumulator; below 0.25 return; otherwise reset to
   positive zero and refresh once. No second guard after marker reentry, no
   remainder, catch-up refreshes, new nonpositive-time guard, or reopen reset.
7. **Delete:** Close existing UI, Destroy existing screen, superclass last.
   Do not add a mode/accumulator reset or clear the component service references.

Screen synchronization chooses its branch at the original state read. If an
effectful service reenters after that choice, the outer branch continues as the
original would; it is not replanned from a later state. Each actual subsequent
service expression still uses its original reference/owner evaluation point.

## 7. Existing service behavior and unresolved lifetimes

### UI.Open, setters and hints

UI.Open lines 133-159 returns false only when BuildWidgets fails. A successful
widget tree with failed map attachment still returns true and logs degradation.
BuildWidgets returns true immediately when a root already exists. Newly built
Chrome receives the UI's current keybind reference at line 340, queues root-size
reporting at 500 ms, then Open queues terrain work at 400 ms. This is enqueue
order, not a claim about callback execution order under engine scheduling.

Focus attaches input and keybinds only after Open. SetInput and SetKeybinds simply
assign existing fields. The latter does not refresh materialized hint text.
Chrome.AddHint constructs `?` when the supplied keybind reference is null.
Preserve the first-open hint behavior during this exact migration; repair it only
as a separately specified product change with independent before/after evidence.

GetKeybinds lazily constructs one SPK_DroneKeybinds and calls RegisterDefaults.
That service avoids existing bindings, can register defaults and save the profile.
It is effectful; do not move it before Open, duplicate it, or label it pure.

### UI.Close and queued work

Close lines 1110-1140 detaches 3D map, marker layer and 2D map in that order,
clearing each reference after its Detach call. It then removes/clears the root,
followed by map-root, marker-canvas, 3D-target and header fields. It does not clear
TerrainMap, terrain canvas, Chrome, input, keybinds, or queued methods.

ReportRootSize returns if the current root is absent. RefreshTerrain instead
checks retained TerrainMap/canvas fields, reads current canvas dimensions, and
queues itself again after 400 ms if either dimension is below 2. Reopening can
replace fields before an older callback executes. The current scalar fixture
records enqueue declarations but does not execute these callbacks.

The queue documentation states argument retention until execution, removal or
queue destruction. It does not by itself settle the retention of a bound-method
receiver, invalid-widget behavior, or cross-open delivery. These are concrete
questions, not established bugs. Do not add cancellation or generation filtering
to the exact adapter without a separate changed-behavior contract. An unresolved
essential teardown condition blocks production release while source/fixture work
can continue.

### Screen validity and teardown

Enable first rejects null owner, then calls Build; only after success does it
assign the owner, bind the render target and set enabled=true. A failed Enable
does not promise to clear an earlier owner/binding. The caller ignores its bool.
Do not roll back HELD, suppress later synchronization, or normalize screen state.

Disable removes the render target only when both widget and stored owner exist,
then clears owner and enabled. Destroy calls Disable before removing the widget,
then clears the widget/content fields. The component retains the screen service
object. Widget absence, enabled state and component screen presence are distinct.

Focus's GetOwner().FindComponent expression has no null-owner guard. The nullable
owner handling inside screen.Enable does not make Focus safe on a null/deleted
owner. Initially admit only the verified valid-owner callback domain; record
missing validity capability explicitly. Adding a protective return changes behavior
and requires an intentional repair packet, not an undocumented adapter choice.

### Handler and receiver retention

Chrome stores handlers in `ref array<ref SPK_UIButton>` and each handler attaches
to its widget. Official Widget docs explicitly describe AddHandler retaining the
handler and RemoveHandler releasing it; RemoveFromHierarchy destroys the widget
only after remaining strong references disappear. UI, Chrome, button receiver,
button target and queued method references must be included in the lifetime audit.

Preserve one OnUiAction dispatch for enabled clicks and the processed=true result;
disabled/missing-receiver clicks return false. Preserve child-event bubbling,
Btn_MapMode and Btn_MapMode_Label identities, `toggle_mapmode`, index -1, and the
existing label update. This adapter does not yet generate that UI fragment or
prove that old handlers/roots disappear after close and world teardown.

## 8. Gadget, input and multiplayer seams

Keep existing gadget orchestration handwritten for the first adapter. Its toggle
calls superclass before testing local ownership. Local ownership compares actual
GetCharacterOwner and GetControlledEntity references with null checks on the
character/controller. It is separate from authority for networked commands.

Activation finds the tablet on the same entity, calls SetHeld(true), then Focus,
and populates only on a true result. Population captures one UI locally, reads
the current core, passes the actual assets array if present, or logs absence,
then refreshes contact rows and order availability. A repeated activation while
already FOCUSED still synchronizes the screen but does not repopulate.

Keep the original input poller. Its frame guard rejects disabled/nonpositive
timesteps; it polls systems and tablet toggle before the missing-autonomy return.
This guard must not be copied into the separate tablet frame callback. Tablet
toggle uses the current action, same-entity gadget lookup, holder/manager guards,
current tablet state and ToggleActive(wantOpen, CUSTOM). Do not create a second
poller, replace the gadget route with local mode assignment, or conflate local UI
isolation with server confirmation.

The source comments describe the vanilla gadget networking route. The adapter's
multiplayer claim still requires independent dedicated clients, ownership changes,
death/respawn, disconnect/reconnect and join-in-progress receipts. Source annotations
or a successful host UI do not supply that evidence.

## 9. Exact extracted API evidence

Installed API roots are the Workbench `docs/EnfusionScriptAPI/html/` and
`docs/ArmaReforgerScriptAPIPublic/html/` directories. The following declarations
were read passively. They supply signature evidence, not runtime verification.

| Declaring type / file | Exact relevant declaration | Source lines |
|---|---|---|
| ScriptComponent | proto external GenericEntity GetOwner(); proto external int SetEventMask(notnull IEntity owner, int mask) | 128, 137 |
| ScriptComponent | void EOnFrame(IEntity owner, float timeSlice); void OnPostInit(IEntity owner); void OnDelete(IEntity owner) | 210, 238, 240 |
| IEntity | proto external Managed FindComponent(TypeName typeName) | 278 |
| WorkspaceWidget | proto external Widget CreateWidget(WidgetType type, WidgetFlags flags, Color color, int sort, Widget parentWidget=NULL) | 155 |
| WorkspaceWidget | proto external Widget CreateWidgetInWorkspace(WidgetType type, int left, int top, int width, int height, WidgetFlags flags, Color color, int sort) | 157 |
| RTTextureWidget | proto external void SetMaxFPS(int fps); proto external void SetResolutionScale(float scale) | 122, 126 |
| RTTextureWidget | proto external void SetRenderTarget(IEntity ent); proto external void RemoveRenderTarget(IEntity ent) | 132, 134 |
| Widget | proto external void AddHandler(ScriptedWidgetEventHandler eventHandler); proto external void RemoveHandler(ScriptedWidgetEventHandler eventHandler); proto external void RemoveFromHierarchy() | 154, 156, 194 |
| ScriptedWidgetEventHandler | bool OnClick(Widget w, int x, int y, int button) | 127 |
| ScriptCallQueue | proto void CallLater(func fn, int delay=0, bool repeat=false, void param1=NULL, ..., void param9=NULL); proto void Remove(func fn) | 121, 125 |
| ArmaReforgerScripted | ScriptCallQueue GetCallqueue() | 140 |
| InputManager | proto external bool GetActionTriggered(string actionName); proto external ref InputBinding CreateUserBinding() | 172, 157 |
| SCR_GadgetComponent | void OnToggleActive(bool state); void ToggleActive(bool state, SCR_EUseContext context); ChimeraCharacter GetCharacterOwner(); EGadgetType GetType() | 140, 154, 160, 162 |
| SCR_GadgetManagerComponent | static SCR_GadgetManagerComponent GetGadgetManager(IEntity entity) | 171 |
| ChimeraGame / PlayerController | proto external PlayerController GetPlayerController(); proto external IEntity GetControlledEntity() | 127 / 121 |

The ellipsis above abbreviates nine separate optional `void` parameters only; the
typed registry must retain the complete original declaration. Do not use the
table as executable binding syntax or infer nullability from an unannotated type.

The selected retained capture omitted RTTextureWidget.html. It is available in
the installed official docs and was newly located for this packet: 47,407 bytes,
SHA-256 `af9141774584f07813c4e9962a8e9ad4f412c082af4598ab30b7fb7d986ede41`.
Its SetRenderTarget description, lines 336-337, includes object-selection and
rebinding conditions and removal on widget destruction. The precise application
of those conditions to a gameplay tablet remains an engine probe; neither success
nor failure follows from the description alone. Add the exact file to the next
new evidence capture before using it as an admitted contract. Do not mutate the
older manifest to pretend it was included.

Additional document hashes read for this packet:

| Document | SHA-256 |
|---|---|
| interfaceScriptComponent.html | `215f2ca81f0d47cbe1dc61dd8471c73c5b5f78c623a247d5f82e8a1e6471c3de` |
| interfaceIEntity.html | `ec2e7f4c76ab91af50a9448ccd13db7aa7590ba3584fbfdacbd6773d899ec585` |
| interfaceWorkspaceWidget.html | `8d6e1d305bdf44ac5d1b1fdd4b373674ef506e742bc81d838fa120ad1d5a91e5` |
| interfaceWidget.html | `26f153143555452828452363d8ce0fbbdf2fd38caf1dcae83228b65d4155f332` |
| interfaceScriptedWidgetEventHandler.html | `dbf725d2013bc3f51dc34a5e9743f28e810a7972e17766754c85cb289064cc92` |
| interfaceScriptCallQueue.html | `6d9b2b3b8c4eba71f80cf10e987b5ce191c7321ebe50365c15fdba1d6cc88763` |
| interfaceArmaReforgerScripted.html | `092859330a59462fb963db8ea6c4d99b087f03fdbe1831c6a017ee8258b0b9a1` |
| interfaceInputManager.html | `b995ee864365543988d5021f989a487c615aa55c70a868329753610c73475b4a` |
| interfaceSCR__GadgetComponent.html | `54b0375869e9570671e238f1c599732f68b8dc527fdf716a315a430a95c52187` |
| interfaceSCR__GadgetManagerComponent.html | `8ffd9ba5121286f736e3085bc04e94236e47bf47238fd6e5c2145235a1376131` |
| interfaceChimeraGame.html | `57e1dce7ed1236d1bf50a7762582cccadf7100424dac495184a4b9921739f362` |
| interfacePlayerController.html | `843159e829ddc2bce2e2b5778d1f84856deb1f884a5a9d5f9f7df4d33cb4fe1c` |

The current installed contract catalog is still the limited
`enfusion.tablet.script-component.v1` profile. It separates extracted callbacks
and source-order review from unknown lifetime, authority, reentry and delivery.
It does not admit these service calls. This document does not change that catalog.

## 10. Smallest next implementation packet

### P5-S1: isolated synchronous service adapter

**Dependencies:** exact compiler/emitter identity and source set; generic component
engine gate owned by the integration owner; closed wrapper superclass/mask policy;
plain State/Operation calling convention; reviewed adapter service signatures.

**Sources and seams:** place an explicitly owned adapter in an isolated fixture
addon. Preserve the original component as a separately named comparison fixture,
outside production discovery. Keep the existing UI/screen/input/gadget classes as
reviewed service consumers. Do not change live MESH or include two production
SPK_TabletComponent definitions. The fixture adapter may have its own class name;
the eventual candidate must preserve the original public identity and interfaces.

**Implementation:** dispatch one opcode at a time; keep shared state and local
continuations; capture input/keybind/receiver results at reviewed points; implement
exact getters and callback signatures. Generate wrappers from an installed typed
profile, with complete Beryl/companion/source origins. Project descriptions select
that profile and validated symbols, never arbitrary engine snippets or commands.
An initially handwritten adapter seam must have its ownership and generated
boundary recorded, so later routine authoring never edits generated output.

**Explicit deferred capabilities:** gadget generation, properties, UI fragments,
prefab/resource lockfile and complete tablet promotion remain subsequent packets.
The existing prefab's property values and stable resource identities are preserved;
their inclusion in this contract does not claim inherited-property or resource
closure validation. No zero-allocation or performance claim is made for an
invocation record or adapter loop; measure actual paid work separately.

### Required comparison cases

| Case | Ordered observations to preserve |
|---|---|
| Fresh successful/degraded focus | UI creation/Open; deferred enqueue declarations; input lookup/setter/GetKeybinds/setter; FOCUSED publication; screen Disable |
| Failed Open, including nested stow | Failure without FOCUSED publication; retain created UI; preserve nested changes instead of restoring HELD |
| Focused stow and repeated SetHeld | Close at FOCUSED; HELD/Enable; STOWED/Disable; repeated same-state synchronization |
| Marker reentry | Exactly one entry guard; nested changes visible; binary32 addition after markers; reset before one telemetry call |
| Lifecycle callbacks | Super-init before reset/mask exactly once; no accumulator reset; Close then Destroy then super-delete exactly once |
| Nested keybind argument | Capture receiver/input/result according to actual engine evaluation; no cross-invocation reply replacement |
| Screen failure/owner changes | Null/failed enable, previous binding behavior, current owner lookup, disable-before-removal |
| Queue and handlers | Close before 400/500 ms, repeated Open, close/reopen before old work, destroyed owner/world, one click dispatch and detached-root lifetime |
| Gadget/local ownership | Superclass precedes guard; missing owner/controller/tablet/core; populate only after successful Focus; repeated activation |

Instrument both original and adapter at matching service entry/exit and state
publication points. Include operation ID, nesting depth, source site, event
sequence, fixture-generated object token and scalar state. Tokens identify real
reference equality within a fixture; never serialize memory addresses. Every
receipt requires expected cases, contiguous sequences, count/checksum and a
terminal completeness marker. Extra, unknown, duplicate or missing cases fail.

For engine float comparisons, establish exact binary32 encoding capability first.
Rounded decimal logs cannot prove signed-zero or bitwise equality. If exact
encoding is unavailable, report that capability unavailable and use only the
explicit weaker numeric comparison domain; do not close exact-bit parity.

Deliberate faults must detect duplicate superclass/mask calls, omitted transient
screen synchronization, reordered hookup, shared continuations, copied-state
writeback, reset/catch-up cadence, skipped queued work, receiver substitution,
duplicate population and incorrect local-owner suppression. A timeout or startup
failure cannot count as a detected semantic fault.

### Evidence and rollout

Use the existing orchestrator and Workbench transport. The passively checked plugin
README, Invoke-ReforgerBuild.ps1 and Invoke-WorkbenchRpc.ps1 still matched their
retained hashes. The README distinguishes headless compilation from live NetAPI;
its historical timing/version statements are not current measured capabilities.
No competing editor bridge or model API is needed.

Record headless compilation, engine-executed fixture comparison, host gameplay,
dedicated clients and visual checks as separate gates. Pin engine, plugin,
compiler, bindings, source set and candidate artifact. Serialize shared editor
operations, own only the job's session, and reject stale results. Keep policy/startup
failure, unavailable capability, cancellation, timeout and source/engine failure
distinct. The previous generic-wrapper engine attempt is historical evidence;
its policy block is not a tablet compile result or a success for this adapter.

After isolated comparison, build an isolated MESH candidate with exact resource
identities and one production class definition. Reuse existing lifecycle/UI/input/
screen/prefab suites with complete case receipts. Multiplayer and visual acceptance
remain required before the PvE release gate closes. Promote only verified,
compiler-owned destinations with prior-hash checks and a retained rollback.

This packet's completion is the reviewed source contract. The adapter's completion
requires a new implemented capability and its own complete evidence; the full P5
tablet remains incomplete until its component, properties, real UI event, prefab,
runtime, multiplayer and visual workflow gates pass.
