# P5 tablet: next runtime acceptance packet

## October 10 dependency audit

The source-only inventory at
`build/oct10-tablet-resource-closure-source-86131ee71f7544bbbadac69ff12036ce.json`
retains 40 exact local files, 30 resource nodes and 13 local reference edges with
matching metadata. The original eight selected tablet resources still match
their retained snapshot. Eighteen distinct base platform configuration references
remain unresolved by this source audit; this does not establish that the installed
engine lacks them.

The retained game-mode bootstrap can schedule MESH core creation, whose arsenal
configuration references the tablet and carried BOLT. The carried BOLT adds
model, material and texture dependencies. The flying BOLT is a separate deploy
and prefab-audit branch. Including the scripts alone does not prove bootstrap
execution: game-mode, world and server conditions require actual observation.

The tablet source orders UI close, screen destruction and superclass destruction.
The installed render-target declaration additionally describes selection and
reset/removal conditions. Neither that source order nor compilation establishes
the actual screen binding, owner validity or teardown lifetime. These remain
runtime contract questions.

The generic callback prerequisite now passes all seven actual cases in the
corrected `idjip0_z` candidate. The preceding read-only diagnostic isolated the
harness's wrong-world spawn argument; using the game world delivered 340 frame
callbacks and native deletion per entity. Exact evidence belongs to
[the callback packet](P4_COMPONENT_CALLBACK_DELIVERY.md). This clears that bounded
dependency. The subsequent candidate admits 28 selected resources and the original
suite handlers, and the five preserved suite requests now return success.
Their exact execution/audit scope is in [the suite packet](P5_TABLET_EXISTING_SUITES.md).
These structural widget/handler/schema checks do not execute the Beryl tablet's
native callbacks or close actual owner/service/deployment acceptance. The next
bounded gate is native tablet initialization and stowed frames; full prefab
spawning additionally requires reviewed profile-write and non-replication
deletion contracts. The original packet below retains its October 8 scope.

## Original acceptance packet

Checkpoint: 2026-10-08. This is a source and retained-evidence review. No compiler,
native program, Workbench, game, asset importer or multiplayer client was launched
for this packet. No live MESH, compiler, candidate source or resource was edited.
The proposed fixtures below are not installed scenarios or completed tests.

## Current evidence and the missing dependency

The trusted synchronous tablet adapter exists and compiles. The retained result
`build/tablet service & spaces-_wtl2u2m/results.json` has SHA-256
`c58506f0f3691403aaf0ccefc01b5db27fde6d6884ca3a1ca69a22ef890606f1`.
Its success means exact candidate script compilation. Its runtime case list is
empty. Tablet services, engine callback delivery, gameplay, multiplayer and visual
review were not executed; resource closure and service lifetime remain unverified.

That candidate used compiler SHA-256
`76aeaacfea6866e66e3020f983eaa22089d545ad0f3b60fedfd28c3d58972bd7`,
Workbench 1.8.0.13 executable SHA-256
`7dd36ca1f662b0c13669a4f2f7f10e3c461c2906b021e742272d64b3ab7e9798`,
and generated artifact SHA-256
`1e0b2811b42ad378cdf34e872a59fceafca63163c1ecd6e5ce1154a8dbb5818f`.
The staged candidate fingerprint is
`df2b59c4959ad447271bf37a14c91f74a6777245ee3fd77f3ba3a13be9319638`.
These identities describe that retained attempt; they are not assertions about a
later compiler, expanded resource set or changed candidate.

The actual source path is `scripts/Game/Beryl/Beryl_Generated.c`, obtained from
the retained artifact/source map. The adapter occupies the original production
`scripts/Game/SparkOSMesh/UI/SPK_TabletComponent.c` path. It uses one persistent
plain scalar State and an invocation-local Operation/input/keybinding result.
It does not generate properties, prefab composition or the map-mode UI fragment.

Two earlier kinds of evidence must remain distinct:

| Receipt | Actual coverage | Remaining limitation |
|---|---|---|
| `build/tablet-lifecycle-n5vv10fu/results.json` | 92 bounded cases, 572 protocol calls, 3,432 assertions; reference and one native differential configuration | Scripted services; no engine object/callback or deployment evidence |
| `build/tablet-engine-replay-gaqdgxi3/result.json`, SHA `6da93ec0354a8d11a659732b523bbe70f4b451724afd2c050bb0f6883a64e887` | Engine numeric continuation replay with scripted replies, 572 calls | No actual tablet services or engine-delivered component callbacks |

The separate owned component callback experiment has not closed world readiness,
spawn or callback delivery. Its diagnostic history and current source hypothesis
belong to `docs/advanced/P4_COMPONENT_CALLBACK_DELIVERY.md`. The known refusal or
RPC timeout must not become a matching source failure or successful lifecycle
receipt. Root owns the subsequent world-opening investigation; this packet does
not select another world format, API, flag, timeout or fallback.

The smallest immediate dependency is a successful exact owned-world readiness
observation followed by the existing seven-case native callback probe. Tablet
service runtime follows that gate; a detached object, manually invoked callback,
headless script compile or bare widget tree cannot substitute for it.

## Source baseline reviewed here

The live project was read from
`C:/Users/moham/Documents/My Games/ArmaReforgerWorkbench/addons/SparkOS_Mesh`.
All 56 current `.c` files and `addon.gproj` matched the frozen tablet source
profile during this read. This is source identity evidence, not executed behavior.
The profile has SHA-256
`768ad8989ee05f84efdc4afd765450ff2f1cf3552ae631cd61ff1d558f895692`.
The original project is `SparkOSMesh`, GUID `4008B09320C27BA6`, with base dependency
`58D0FB3206B6F859`. Its `addon.gproj` SHA is
`63cc2c9f6e815e74629867520b5bdb71fb62971490997e32a0a2a7ffb02db1bc`.

The compile-only candidate is `BerylTabletServicePrototype`, GUID
`BE715E7A20261008`, with that same base dependency. It retains all 56 originals
outside production discovery, stages 54 Game scripts, and replaces exactly the
tablet component. It excludes the two original WorkbenchGameCommon handlers.
Adding them for acceptance is a new, explicitly captured test input and rebuild.

| Source | SHA-256 | Relevant contract |
|---|---|---|
| `UI/SPK_TabletComponent.c` | `1f15962cf67a8cc513d7068757e89360260016fadff1c8843719784acc94be3a` | Public state/service methods; init 133–137, frame 150–166, delete 171–181 |
| `UI/SPK_TabletGadget.c` | `d336244b7d178324eded5bc5e584f721cd2c4f9b7036ac90d1f757ba30b0199c` | Superclass-first toggle, local owner guard, held/focus/population order |
| `Input/SPK_DroneInputComponent.c` | `440a493229775ab18233c76020763d4c724adfb4fece3dc41e9ca26747e5695b` | Lazy keybindings 49–57; actual tablet toggle 195–223 |
| `Input/SPK_DroneKeybinds.c` | `1123a60363291343d858f3106896260060160a89b340085236b0437808a962ce` | Actual binding object and default registration |
| `UI/SPK_TabletUI.c` | `4efeab8cce793939d748506f34691aae9b0b47aa8b32ed568ece05accf28a05d` | Open, map degradation, markers, telemetry, deferred work and Close |
| `UI/SPK_ScreenRT.c` | `6328c5e86787b75c8cf949fcbd914c4fb137e17534a6158150bdba13818e942b` | Build; owner binding 92–103; unbind 108–114; destroy 126–136 |
| `UI/SPK_TabletChrome.c` | `53c2fccfb900371ce0ea409d98f0903a20e71e472630e6caea87b29477a1811e` | Handler retention; actual map-mode fragment 247–263 |
| `UI/SPK_UIButton.c` | `24f45c2d5cc8dc050290047bf8a9c902f536cfd7e3fa5569b07410816cd03c9a` | Attach/AddHandler; one dispatch per admitted OnClick; disabled/hover behavior |
| `UI/SPK_TabletTheme.c` | `2e54d966e20af86da093a414b28b2faa5e2f5ffa49887e6668b6a9ebdaef00e7` | Semantic state/hazard colors and interface geometry |
| `Core/SPK_MeshBootstrap.c` | `704f60b43b9c010272d98cefdf64d78a96b3e0b2eaa08d22d717c76d08b3d9e1` | Deferred server-side core installation; test/shot requests are separate |
| `scripts/WorkbenchGameCommon/SPK_MeshSelfTest.c` | `59213fecdd4ecd1ced6e0eee0716b5c86bf3cc184ee6261452da9ac3c4dcda46` | Existing suite implementation and retained-resource enumeration |

The first ten paths in that table are relative to
`scripts/Game/SparkOSMesh/`. The last is relative to the project root.

The service adapter template SHA is
`21479adf12a76a48ad7be9419e6e5047d663cce0ebee1341e5d8bfaf8d20d3c7`.
The unchanged Beryl protocol SHA is
`34c2b848e94a7a68132804d08a58fcf31d644f2d0e9eb2b4973e84a39249f792`.
Its existing source/service contract remains
`docs/advanced/P5_TABLET_SERVICE_ADAPTER_CONTRACT.md`.

## Actual integration consumers and entry points

The shipping toggle is `SPK_DroneInputComponent.PollTabletToggle`, not a separate
tablet toggle component. It checks the triggered action, gadget, character holder
and gadget manager; derives wantOpen from the current tablet state; then calls
`gadget.ToggleActive(wantOpen, SCR_EUseContext.CUSTOM)`. The original comments
describe the vanilla request/broadcast path. Actual authority and ownership timing
still need dedicated execution rather than acceptance from those comments.

`SPK_TabletGadgetComponent.OnToggleActive` calls superclass before the local-owner
guard. Activation calls SetHeld(true), then Focus, then PopulateTablet only if
Focus succeeds. Populate obtains the current UI, uses the current MESH core when
available, then refreshes contact rows and order availability. Remote, missing
holder/controller, missing tablet and missing core branches remain observable.

`SPK_MeshHarnessComponent` holds a separate `ref SPK_TabletUI`. Opening its diag
tablet view bypasses `SPK_TabletComponent` and the player gadget. `SPK_ShotMode`
is likewise a visual capture facility, not lifecycle or local ownership proof.
Keep existing debug entry points useful while labeling the tested path precisely.

The bootstrap can run because all 54 Game scripts remain included. Its server
installation requests the core prefab after two seconds. An apparently tablet-only
world therefore still needs either the corresponding preserved resources or an
explicitly reviewed test-world boundary. Silently suppressing bootstrap or accepting
its missing-resource errors would change the tested configuration.

## Reuse the existing suites before adding new runtime cases

The installed handler is `SPK_MeshSelfTest`; request fields are `suite` and `arg`.
It returns only integer `ok` and string `detail`. It has no per-assertion case IDs,
event checksum, compiler token or completed-run receipt. The outer verifier must
retain each exact request/response and independently bind it to the owned candidate.

| Existing suite | Source lines | Coverage to reuse | It does not prove |
|---|---|---|---|
| `ui` | 330–398 | Workspace, BuildWidgets, Verify, direct 2D→3D→2D mode changes, repeated Close | Open/AttachMap, gadget, component frame/delete delivery or native click dispatch |
| `screen` | 507–564 | Build/Verify, Enable(null) rejection, disabled initial state, repeated Destroy and cleared widget | Binding to a real tablet entity, screen pixels, owner invalidation or final render-target lifetime |
| `actions` | 1366–1443 | Action/key uniqueness, labels/hints/defaults, group partition | Actual input polling, rebinding persistence, ownership or server request acceptance |
| `clicks` | 1516–1643 | Declared action/handler coverage, rows, direct RETURN/row/LOITER handler calls, disabled/re-enabled dispatch | Engine-delivered mouse events or an explicitly clicked map-mode control |
| `schema` | 2380 onward | Existing prefab field introspection for the selected arg | Automatic admission of inherited property semantics or gameplay effects |
| `prefabaudit` | 2169–2270 | Tablet, carried drone, flying drone and core source composition/mesh checks | Instantiation, callbacks, render appearance, authority or inventory lifecycle |

For the first reuse step, freeze the outer expected selections as exactly
`ui`, `screen`, `actions`, `clicks`, plus `schema` with the captured tablet resource
argument `arg="{B37EEB64E149CBAD}Prefabs/SPK_Tablet.et"`. RunSchemaSuite 2382
assigns req.arg to ResourceName and 2449 loads that resource. Its separate
`class:` branch introspects a bare class; it is not this prefab selection.
Add `prefabaudit` only with its complete resource
closure. Each selection must occur once, return a real successful RPC and integer
ok=1, and retain its detail. An unknown, empty, duplicate, omitted, partial or
unavailable selection fails its gate. These are suite receipts, not invented
per-assertion engine cases.

The old `scripts/mesh-engine-run.ps1` selects exactly nine other suites:
pid, flightspec, rotor, mixer, manual, guidance, task, loiter and datalink. The
historical `build/mesh-pid-ej8h72g_/engine-tests.json` SHA is
`6b52d89630e1fea32851e3c9238b4618b3b5db5ff84e4bb357af94f093e759fe`.
It records those nine successful selections. It does not record the proposed five
tablet selections. Reuse its suite interpretation through the current owned-job
and identity discipline; its hardcoded SparkOSMesh check must not be silently
reused for BerylTabletServicePrototype.

The same historical MESH result, SHA
`98710dda17b7396b98761028e4ba72e94000e71e8b10a64a26362d8cfc190b89`,
records 18 host checks and PID handover. The fixed names are A0_no_autospawn,
A1_spawn, A2_components, A3_physics, A4_rotors, A5_hover, A6_arsenal,
A10_realbox, A11_task_order, A12_task_flown, A7_interlock, A13_arm_button,
A8_arming, A14_disarm, A9_warhead, A15_strike_safety, A16_strike_order and
A17_strike_flown. They are flight/arsenal/weapon integration evidence for that
old candidate. They are not equip/focus/stow/delete tablet cases or dedicated
two-client acceptance; the old receipt itself labels that latter gate unverified.

## Resource closure to capture before a real tablet world

The present source candidate stages no models, prefabs, material files or world.
All proposed additions must be compiler/test-owned copies from a frozen inventory,
preserve existing resource identifiers, and receive a fresh candidate fingerprint.
The live original addon must not be loaded beside a clone that duplicates its
production classes or resource identities. Use separate owned baseline and candidate
projects/sessions, or establish a specifically reviewed alternative isolation scheme.

Minimum tablet asset edges read here:

| Resource / stable ID | Current bytes / SHA-256 | Edge or required check |
|---|---|---|
| `Prefabs/SPK_Tablet.et`, `B37EEB64E149CBAD` | 593 / `dabd491efd1b27cf49b311948c1215acf1982f06f6b6de8a0e9ea0e001ae0c22` | Six components; model Object below; preserve inherited use mask 15 and anim variable MAP |
| Tablet prefab `.meta` | 133 / `7cf10f188f52b7724564b78e7999274854948665b48015ae130dcb7fea267b3a` | EntityTemplateResourceClass PC; exact resource registration |
| `Assets/Tablet/SPK_Tablet.xob`, `BB50496D23063970` | 605161 / `7c0444ce12f0dae2d2d1b030c38d9c56f576a1eaa4a8269af7bcb424c1aea52d` | Existing imported model; target load and visual binding remain gates |
| Tablet model `.meta` | 1466 / `aecc3e22af19aa3c50b7beecbde13f2eaa9e0c5335ad55a85cde8afce06ff6ca` | AssignedMaterial plus platform Common configuration references |
| `Assets/Tablet/SPK_Tablet.txo` | 3235675 / `24739df0fc55f7632eaade144bdf581898d363fa289445cc0fa2047f947b1585` | Retain existing intermediate/source asset if required by the selected import profile; no regeneration here |
| `Assets/Tablet/SPK_Tablet.fbx` | 1114732 / `8fd22da071c552266526289bbedbb223305e38141fc0eebb949ce6621a1b19a5` | Authoring/rollback input, not proof that a runtime load uses it |
| `Assets/Tablet/Data/Material.emat`, `2E845CA43E3FFF43` | 15 / `324a4d878cbd343d17e60f25455eca9dbc7b40dfab562a6e0b91e627fc43f255` | Current source is MatPBRBasic {}; do not invent missing texture or screen-slot semantics |
| Material `.meta` | 319 / `d320ffbe164b5ec6a4fa635769c229f6fc4fe31df371b52b9eaed8216ceb04c0` | Existing EMATResourceClass profiles |

The tablet prefab's six declared components are MeshObject,
InventoryItemComponent, SPK_TabletComponent, SPK_TabletGadgetComponent,
SPK_DroneInputComponent and SCR_EditableEntityComponent. It has no explicit
RplComponent. Inline inventory/UI-info block identifiers such as
`6A2000000000A001` and `6A5000000000E001` are not automatically external asset
references; classify actual fields rather than treating every GUID-shaped string
as a resource to copy.

The model metadata refers to base platform MeshObjectCommon.conf resources.
The PC identifier is `0877E7C4BB2B2C9A`; HEADLESS is `3A5B3356978039E8`.
XBOX_ONE, XBOX_SERIES, PS4 and PS5 have separate recorded IDs. Confirm the selected
platform closure through the installed dependency/resource resolver; do not claim
all platforms from a successful PC script compile. The local binary model hash is
not an inspection of embedded resource tables or a verified surface material.

Bootstrap/full-suite additions extend the closure:

- Core: `{CC0A1009F9F60365}Prefabs/SPK_MeshCoreEntity.et`, SHA
  `26ee49311764b61a4efb34bc70792a1b4960b1cf8180d897e50f7bbb669ca564`,
  with its metadata; this includes RplComponent, SPK_MeshCore and arsenal registration.
- Arsenal: `{770D5A8799BDCBB2}Configs/SPK_MeshArsenal.conf`, SHA
  `437296a39d9a42a3f093b86457ea4bd64120f29ae503511940916f0b8054ba98`,
  plus metadata. It references both the tablet and carried BOLT item.
- Full prefabaudit: carried BOLT `{F4CFA48A57868B92}Prefabs/SPK_BoltM_Item.et`
  and flying BOLT `{EBD7200A0E6F88CC}Prefabs/SPK_BoltM.et`, their metadata,
  body/carried model assets and their actual recursive material/configuration edges.
  Their model IDs are `1C7182023A2C32C6` and `B2400E443C90DB8F`, respectively.
- Existing host acceptance also loads a vanilla US arsenal box
  `{45C675ED3CFBBEC5}Prefabs/Props/Military/Compositions/US/ArsenalBox_US.et`
  and requires an appropriate world/game mode/faction context.
- Map attach uses the base MapPlain `A786DD4868598F15`, MapSpawnMenu
  `418989FA279F1257` and MapFullscreen `1B8AC767E06A0ACD` configurations, then
  the existing empty-config fallback. Resolve those dependencies and observe the
  actual SCR_MapEntity/world context. A degraded no-map Open remains valid.

This is an inspected initial closure inventory, not complete engine resolution.
Enumerate the actual edges and retain source/metadata/compiled-resource hashes
before resource acceptance. Neither the tablet nor screen UI requires an invented
.layout file: current widgets are built programmatically. Native .layout generation
is a separate unfinished authoring capability.

The existing `Test-ReforgerPrefab.ps1` is source-reviewed, SHA
`8e1e348de3769995ef36d3c266c9d9d1de69baebfd73d7eeda9e71b2af0b0cd8`.
It accepts ProjectDir and ResourceName, deploys ValidatePrefab if missing, then
uses the existing RPC. Do not let that deployment modify a frozen candidate
during verification: stage the exact reviewed handler as a declared test input
before capture/build, then invoke it through the owned session. Its result proves
Resource/ToEntitySource/component structure, not runtime creation or callbacks.

Preserve the existing prefabaudit Resource retention at SelfTest 2294–2310.
It keeps ref Resource handles while using IEntitySource; a bare returned source
must not be assumed to retain its loaded resource. That rule belongs to the
reviewed test fixture, not a newly established universal engine lifetime contract.

## Selected-source preparation completed at this checkpoint

The new `scripts/prepare-tablet-resources.py` is a source-only preparation tool.
It invokes no compiler, engine, importer or installer. Its reviewed SHA-256 is
`9b0136821c05f79bc44093d5658936aef5714b93da6eab3631c846d6a41f1df6`.
It pins its own bytes once, retains those exact bytes, and rechecks its source
identity before the result. It copies only the eight files in the table above
into a fresh owned directory. It preserves the three metadata resource names,
checks the selected model/material edges, and explicitly retains the six base
platform configurations as unresolved references rather than copying them.

The file budget is 8 MiB per selected file and 16 MiB total; tablet-directory
enumeration is bounded to 64 entries. Reads and checked writes reject linked
paths, reparse points, multiple hard links, unexpected asset additions, changed
source bytes/file identities and existing output. These are checks at the observed
boundaries, not an atomic filesystem snapshot or a general Enfusion format parser.

The actual source capture is retained at
`build/tablet resource snapshot & spaces-xh9hj6bm/result.json`, SHA-256
`78afaad183113c4ae975837893341f7d18eb16ff921cf08d7e981e688b6893c2`.
All eight selected source/copy hashes matched, and the source and retained resource
fingerprint is `376258b38b7a04619d004274a749f4edfe17df25f01d28740c8891821ec956e5`.
The retained copies are under that directory's `resources/`; they are not installed
in the candidate or live addon. Preparation succeeded; complete resource closure,
binary dependencies, imported resource availability, model/intermediate freshness,
screen material binding and platform admission remain unverified. The current
material declares no standalone texture. The existing txo bytes are preserved
without claiming a texture/import role.

The fixed self-test selection contains 17 synthetic filesystem cases. Its receipt
is `build/tablet resource tests & spaces-1ieptvzp/result.json`, SHA-256
`86dff8bfc76a4160fcc5dd732cceaff8a674b4ee2aa16624bd92918a899fe6b8`.
Sixteen executed and passed; zero failed. The symbolic-link rejection fixture
was unavailable because creating its test link returned WinError 1314. It is
excluded from passed_cases, retained separately, and the aggregate is explicitly
`status=unavailable`, `coverage=partial`, exit 2. Existing path/reparse rejection
is implemented, but the unavailable fixture is not presented as exercised.
The hard-link rejection case did execute and pass. No privilege or security policy
was changed. The self-tests establish filesystem behavior, not engine import,
callback, service, UI, multiplayer or performance evidence.

## Smallest new runtime fixture after world readiness

Use the existing process/Workbench transport, snapshot receipts and shared-session
serialization. First add an explicit full-resource tablet acceptance profile and
the reviewed test handlers. Do not broaden the compile-only profile in place or
reinterpret its previous success. Keep exactly one production SPK_TabletComponent
and one descriptor in each candidate.

The first fixture has eight proposed static case IDs:

| Proposed ID | Actual observation needed |
|---|---|
| `tablet.callback.init` | Engine constructs the exact tablet prefab and delivers OnPostInit; superclass first, STOWED commit and one FRAME mask |
| `tablet.callback.frame` | Real EOnFrame delivery occurs on the created owner; record actual finite timestep and verify caller state/service transitions |
| `tablet.services.held` | Public SetHeld(true) publishes HELD and attempts screen enable using that exact current owner |
| `tablet.services.focus` | HELD-only Focus; actual Open/input/keybind hookups before FOCUSED; screen disable after commit; record actual degraded-map outcome |
| `tablet.services.repeated-held` | Repeated SetHeld(true) preserves current mode and still synchronizes screen; no implicit repopulation |
| `tablet.services.stow` | Focused stow: Close at FOCUSED, HELD plus Enable, then STOWED plus Disable |
| `tablet.services.reopen` | Close/reopen retains the accumulator and existing bindings; capture queue/widget identities without assuming retention policy |
| `tablet.callback.delete` | Actual supported owner/item/world destruction delivers Close, Screen.Destroy and superclass last; no direct callback invocation |

Public Focus/SetHeld fixture calls exercise caller logic and actual services. They
are not player input or gadget delivery. OnPostInit, EOnFrame and OnDelete must
come from native entity lifecycle; calling those methods manually cannot satisfy
the corresponding cases. Precise synthetic timesteps remain in the existing scalar
replay layer; a real callback fixture records actual delivered timesteps.

The ordinary tablet prefab has no explicit RplComponent. The generic probe's
authority/deletion assumptions therefore require new admission on the actual owner.
The installed `interfaceSCR__EntityHelper.html`, SHA
`04728aede2cc4fa93b77eedfbca102d8083517d48b6acc8f3247ac4cdee67cac`,
declares static DeleteEntityAndChildren(IEntity) and describes it as a wrapper for
RplComponent.DeleteRplEntity(entity,false). Existing MESH calls it at DeployAction
156 and WarheadComponent 165. This provides an existing route to review, not an
authority bypass or guaranteed deletion on a tablet proxy. Prefer actual item/world
teardown where appropriate and observe delivery; do not insert a new RplComponent
into the production prefab solely to make the probe pass.

Capture ordered service entry/exit and state publication observations. Each record
needs case/invocation/parent-invocation identities, sequence, event, mode,
accumulator representation, fixture-tokenized owner/UI/screen/input/keybinding
identity and relevant service result. Reads of presence remain at the original
source points; a logger must not add an engine call, second frame guard or global
active continuation. Per-invocation results cannot be overwritten by nested calls.

Run original and adapter configurations in isolated owned environments with the
same frozen resource/source domain. Compare matching public-operation inputs and
service outcomes. Real frame timing may differ between runs: retain each actual
callback timestep and evaluate its expected transition independently. Unequal input
or reply streams are not evidence of implementation disagreement or equality;
report them not_comparable instead of dropping records or fabricating equal clocks.
A fully matched original/adapter frame trace needs an explicitly verified shared
input/capture mechanism before that stronger gate can close.

Exact f32 encoding is a separate target capability. Rounded ToString payloads must
not be labeled bitwise state equality. Numeric target checks, independently rounded
finite expectations and exact-bit checks must state their actual comparison mode.
Service/root observers also need reviewed access/validity at deletion boundaries;
failure of an observation cannot automatically be called a compiler defect.

The final receipt must contain the complete declared case set, contiguous ordered
records, count/checksum, actual outcome, source/tool/binding/artifact identities,
raw logs and owned cleanup confirmation. Missing frames, a refused service,
startup failure, timeout, cancellation, stale input, unknown case or incomplete
trace keeps its appropriate gate incomplete. An unavailable UI host is not a
successful negative Open case unless that failure was an explicitly executed,
admitted fixture whose expected source behavior was actually observed.

## Follow-on actual UI, queue and player acceptance

After the first eight cases, extend one bounded layer at a time:

1. Map-mode event: preserve HeaderBar, Btn_MapMode and Btn_MapMode_Label;
   the action is toggle_mapmode with index -1. Existing MakeButton uses sort 2,
   label sort 3, placement (250,8,320,-8), semantic colors and retained handler.
   A direct handler unit invocation verifies dispatch only. A real widget click
   must independently show exactly one dispatch and the 2D/3D label/state update.
   Disabled and hover behavior need their actual event/visual checks.
2. Deferred close/reopen: BuildWidgets queues ReportRootSize at 500 ms; Open
   queues RefreshTerrain at 400 ms; unresolved canvas layout can requeue terrain
   work. Close clears roots/map views but does not clear TerrainMap, terrain canvas
   or Chrome, or remove those queued methods. Test close before delivery, reopen
   before old delivery, repeated close, and destruction with pending work. Preserve
   the baseline first; this source pattern is a lifetime question, not a proven bug
   or permission to cancel work silently.
3. Binding/retention: observe screen Enable→SetRenderTarget on the live owner,
   Disable→RemoveRenderTarget before owner clearing, and Destroy disabling before
   hierarchy removal. Verify handler/receiver behavior across widget destruction.
   Logical fields saying enabled or null do not prove a released engine render pass.
4. Actual player path: equip the existing prefab, use the existing rebindable
   tablet action, traverse the gadget request, local-owner guard and successful-only
   population. Repeated activation while focused must not repopulate. Preserve
   input defaults and inherited m_eUseMask=15/m_eAnimVariable=MAP. A standalone
   component test does not establish those inherited gadget properties.
5. Dedicated/visual deployment: two independent clients; remote toggles never
   open another player's UI; death/respawn/transfer/disconnect/reconnect/JIP and
   repeated instances/world teardown. Test current ultrawide and 1920×1080,
   clipping/hints/map interaction/missing services and degraded states. Preserve
   SPARKOS greyscale structure, hazard amber, state green and separate map
   affiliation colors; inspect actual rendered handling.

Fresh Focus currently builds UI before SetKeybinds, so first-open Chrome hints can
be `?`, while a later rebuilt tree uses retained bindings. A parity fixture must
preserve and record that ordering. A hint refresh repair would be a separate
behavior change with its own acceptance; it is not folded into this migration.

The additional State/Operation allocations use the existing
resource_adequate_exact policy. No equal out-of-memory behavior, physical engine
memory count, leak freedom, faster gameplay or Rust advantage is established by
this packet. Measure paid allocation/lifetime costs only after semantic acceptance.

## Completion and next implementation packet

This document completes a bounded review/plan only. The next code packet should
declare the full-resource fixture inputs, exact test-handler additions, actual
world readiness dependency, the eight ordered cases and their evidence contract.
Root remains engine/session owner. No production install or promotion follows
from preparation, structural checks or the already retained compile receipt.

Close each evidence level separately: resource/source admission; existing suite
execution; native callback delivery; actual synchronous services; queued/widget
lifetime; player input/gadget path; dedicated clients; visual interaction.
Only the exact final candidate that passes the required levels is eligible for
hash-checked promotion and rollback testing. Generated property/prefab/UI authoring
and zero manual generated-file edits remain independent P5 delivery requirements.
