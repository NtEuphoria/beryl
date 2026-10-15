# P4: bounded real component callback delivery probe

## Current continuation: October 10

The [layered-world diagnosis](P4_LAYERED_WORLD_DIAGNOSIS.md) supersedes the
single-file world hypothesis below for newly selected candidates. The original
trials and their failed outcomes remain historical evidence.

The real `merbrapz` candidate completed deferred loading and play, and delivered
both post-init callbacks. It timed out waiting for frames: six initialization
and authority rows, zero frame/deletion events, and no complete seven-case
receipt. Its transport remained responsive and owned cleanup was confirmed.
Generated FRAME registration and explicit activation are present. The separately
identified `a7u0gcvh` trial used the opt-in `force-update` hidden launch profile.
It compiled cleanly and completed load/play, but again timed out at spawn with
the same six-row initialization/authority prefix and zero frame events. Its
owned process was stopped; the seven-case runtime gate remains open.
The next bounded diagnostic ran at
`build/component callbacks & spaces-bbe8mikw/results.json`. Its two raw-linked
readbacks establish that the probe entities belong to the editor world, which
remains at frame zero, while the distinct game world advances from frame 185 to
7,566. Both owners have ACTIVE set and their components have FRAME registered.
The original result is still timeout/spawn after 64 polls; owned cleanup is
confirmed. The diagnostic did not switch worlds, invoke callbacks or change the
generated component.

The concrete harness repair selects the running `Game.GetWorld()` for prefab
spawning and verifies the returned owner world. Fresh candidate `idjip0_z`
compiled cleanly and passed all seven cases. Each entity received one native
post-init, 340 native frame callbacks and one native deletion; the 1,373 ordered
rows and 10,949 state/ordering checks matched. All five mode/lifecycle stages and
owned cleanup completed. Its separate readback confirms both owners belong to
the game world. No timeout widening, manual callback or partial-prefix acceptance
was used. The negative attempts remain preserved.

The successful receipt is
`build/component callbacks & spaces-idjip0_z/results.json`, SHA-256
`b60885738f091d22deb366451dcb096b6a6e6ae2eb774fa26d9090de3b987290`.
This is bounded scalar component evidence for the exact private candidate,
Workbench 1.8.0.13, source-layered world and force-update launch profile.

The independent terminal audit is
`build/oct10-callback-complete-terminal-audit-354cc474b1ae4dc5893e42d07a0ce26b.json`,
SHA-256 `afbc90de3a9adef90435b00f5f73b9088cdcf9b7558d0e66062e586de65c8823`.
It rechecks raw-linked RPCs, the complete seven-case trace, staged inputs, tool
identities, all five completed stages and confirmed cleanup. Comparing the two
observed candidates isolates the trusted RPC spawn-world correction; compiler,
generated component, observer, transport and diagnostic handler inputs match.

For a fresh run of this tested profile, use the existing verifier with explicit
private compiler/tool/engine identities plus `--world-fixture source-layered-v1
--engine-updates force-update --frame-diagnostics world-state-v1 --engine-stage
runtime`. Arguments above describe the profile; each new run produces a new
receipt. The legacy single-file world is not this verified configuration.

Tablet services, multiplayer, full engine-reference/world lifetime and release
capability remain separate gates.

## Original implementation packet

Checkpoint: 2026-10-08. This packet prepares an experiment. Source review and
synthetic receipt validation do not establish engine callback delivery. The root
integration owner must run the explicitly selected private compiler and owned
engine job before any runtime gate closes.

## Why this is the next dependency

The generated flat scalar component compiles after its retained Beryl state was
changed to a member initializer. A plain script member-box probe can check emitted
handler calls and state replacement. It cannot establish actual component
creation, `OnPostInit`, frame delivery, or destruction. Direct construction of a
derived ScriptComponent was rejected by the engine because its inherited
constructor is private. That failure is retained; this fixture does not add a
constructor or invoke lifecycle callbacks manually.

The installed engine exposes prefab creation with all its components. The probe
therefore enters an owned world, loads a fixed fixture prefab, and observes native
entity lifecycle callbacks on two entities. Its seven cases are:

1. `runtime.post-init.1`
2. `runtime.post-init.2`
3. `runtime.frames.1`
4. `runtime.frames.2`
5. `runtime.independent-state`
6. `runtime.delete.1`
7. `runtime.delete.2`

This is a prerequisite for a real tablet adapter. It is not that adapter and does
not open tablet UI, query input, render a screen, execute gadget callbacks, or
establish multiplayer behavior.

## Exact declaration and resource basis

`packages/sparkos/component-callback-probe/source-contracts.json` now pins 21 passive
inputs: 17 installed API files and four MESH world/prefab source seeds. The
GenericWorldEntity, ResourceName and Enforce syntax declarations extend the
preceding 18 inputs, whose old inventories remain retained beside their
immutable attempts. Each row
has the original absolute path, bytes and SHA-256. Preparation requires those
identities still to match and retains their bytes. Extracted declarations are
separate from the runtime observations that remain to be executed.

The admitted engine is Workbench 1.8.0.13, executable SHA-256
`7dd36ca1f662b0c13669a4f2f7f10e3c461c2906b021e742272d64b3ab7e9798`.
The declarations below come from that installation's local documentation:

| Declaration | Exact relevant interface | What it does not establish |
|---|---|---|
| Workbench module discovery | `Workbench.GetModule(TypeName) -> WBModuleDef`; `OpenModule(TypeName) -> bool` | Successful world loading or play-mode completion |
| Game-project observation | `Workbench.GetCurrentGameProjectFile() -> string` | Identity of the separately loaded candidate addon |
| Native resource resolution | `Workbench.GetAbsolutePath(string relativePath, out string absPath, bool mustExist=true) -> bool`; exact addon path syntax documented as `$addonName:Prefabs` | A successful resolution or ownership match before the target returns it |
| WorldEditor API | `WorldEditor.GetApi() -> WorldEditorAPI` | Session ownership |
| Current resource-opening hypothesis | inherited `WBModuleDef.SetOpenedResource(string filename) -> bool`, on the explicitly opened WorldEditor; rejected global `Workbench.OpenResource` trials remain historical | Completion, asynchronous or non-modal loading, or request acceptance before the actual return |
| Play request | `WorldEditor.SwitchToGameMode(bool debugMode=false, bool fullScreen=false) -> void` | A synchronous successful transition |
| Edit request | `WorldEditor.SwitchToEditMode() -> void` | Completion of teardown |
| World observations | `WorldEditorAPI.GetWorldPath(out string path) -> void`, `IsEditMode() -> bool`, `IsGameMode() -> bool`, `GetWorld() -> BaseWorld` | Undocumented canonicalization or a completed callback trace |
| Game observation | `Game.InPlayMode() -> bool` | Dedicated-server behavior |
| Prefab admission | `Resource.Load(ResourceName) -> Resource`, `IsValid() -> bool`, `GetResource() -> BaseResourceObject`, `BaseResourceObject.ToEntitySource() -> IEntitySource` | Closure of all inherited world resources |
| Runtime construction | `Game.SpawnEntityPrefab(notnull Resource, BaseWorld world=null, EntitySpawnParams params=null) -> IEntity` | Validity of an arbitrary class constructed directly |
| Component lookup | `IEntity.FindComponent(TypeName) -> Managed` | Validity after the owner has been deleted |
| Active updating | `IEntity.SetFlags(EntityFlags flags, bool recursive=false)` and `EntityFlags.ACTIVE` | Automatic callback delivery without a frame event mask |
| Component events | `OnPostInit(IEntity)`, `EOnFrame(IEntity,float)`, `OnDelete(IEntity)`; `SetEventMask(notnull IEntity,int)` | Reviewed tablet service ordering or all inheritance chains |
| Owner observation | `ScriptComponent.GetOwner() -> GenericEntity` | Retention beyond deletion |
| Authority | inherited `BaseRplComponent.Role() -> RplRole`, `RplRole.Authority` | Proxy-local state becoming authoritative |
| Native deletion | `RplComponent.DeleteRplEntity(IEntity,bool releaseFromReplication) -> void` | Physical deletion when called on a proxy |
| Slash comparison | `string.Replace(string sample,string replace) -> int` | Relative, GUID, case, or other path equivalence |
| Experimental world-root class | documented `GenericWorldEntity : GenericEntity` | Valid serialized standalone .ent root syntax, world services, or successful loading |

The RplComponent documentation distinguishes authority-side physical deletion
from proxy behavior. The fixture includes an RplComponent and requires authority
both after spawning and before deletion. It does not treat a deletion request as
a delivered `OnDelete` callback.

The world seed is the retained live MESH `worlds/test1.ent` pattern:

```text
SubScene {
 Parent "{853E92315D1D9EFE}worlds/Eden/Eden.ent"
}
```

This is the original source-reviewed inherited world, not an independently
resolved empty world. Its companion metadata uses the seed's `ENTResourceClass`
platform shape. After the inherited-world timeout and rejected empty SubScene
experiment described below, the current candidate tests this minimal root:

```text
GenericWorldEntity {
}
```

The installed primary `interfaceGenericWorldEntity.html` is 98,965 bytes with
SHA-256 `a8b06ae27be50a3edb343b88480e29d0f1fd184e928c499ad779dda1196353c1`.
It establishes the class and its inheritance; it does not establish this .ent
serialization or usable standalone-world services. Both are unverified target
hypotheses. No default terrain, game mode or other required world service is
assumed. The unchanged path and metadata identities select this candidate only
within a newly captured owned attempt.
The prefab metadata uses `EntityTemplateResourceClass PC`, exactly as the current
`Prefabs/SPK_MeshCoreEntity.et.meta` seed does. No new resource-class spelling is
invented. New addon/world/prefab IDs are fixed in this experimental package; no
existing MESH identifiers are replaced.

World loading, inherited resource resolution and prefab instantiation are still
target gates. A missing resource is reported unavailable, not repaired by changing
live MESH or rewriting a resource into a different behavior.

## New source and generated boundary

The experiment owns only:

- `packages/sparkos/component-callback-probe/src/state.be`
- Its strict version-2 companion, world, prefab, metadata and trusted templates.
- `scripts/verify-component-callbacks.py`
- `scripts/component-callback-engine.ps1`
- This packet.

The record has five plain fields: `ready`, `init_count`, `frame_count`,
`delete_count`, and `elapsed`. Its Beryl handlers increment initialization,
increment frame count and add the supplied finite timestep, then increment
deletion and clear ready. These handlers are actual Beryl source, not host-side
substitutes. This is deliberately a scalar probe rather than the tablet lifecycle.

The generated component is `SPK_BerylCallbackProbe` with descriptor
`SPK_BerylCallbackProbeClass`. The authored callback orders remain first/none/last.
The current generator's initialization enables `EntityEvent.FRAME`. The trusted
observer subclass wraps those generated callbacks to inspect the state before
and after the superclass call. It does not construct the component or call
callbacks from the RPC handler.

The renderer consumes actual emitter linkage from the immutable source map. It
requires one exact qualified State declaration, its five exact field mappings,
identifier-only emitted names, and the actual generated retained member:

```text
protected ref <emitted State> m_BerylState = new <emitted State>();
```

It rejects a changed native construction boundary. It never reproduces the C
compiler's name-mangling algorithm. The immutable generated artifact remains
untouched; the verifier clones its addon and adds only the predeclared fixture
files. Every staged input is hashed. The sole permitted extra engine-generated
file is the root `resourceDatabase.rdb`, bounded to 8 MiB and recorded separately.
Unexpected files, directories, links or modified source bytes fail integrity.

## Multi-request execution and ownership

One blocked NetAPI request cannot also be assumed to deliver frame callbacks.
The trusted RPC handler therefore returns promptly between every operation. The
PowerShell adapter extends the existing installed Workbench bridge with these
fixed actions and no arbitrary script input:

| Stage/action | Readiness required |
|---|---|
| `load` | Exact owned absolute world path, world present, edit mode, no play mode |
| `play` | Same world path, world present, game mode and `Game.InPlayMode()` |
| `spawn` | Two registered prefab entities, one post-init each, at least three frames each, distinct state roots; phase 3 |
| `delete` | Authority confirmed before both native deletion requests; both complete delete observations; phase 4, executed 1, failures 0 |
| `stop` | Same world identity observed in edit mode with play mode off |

The first `load` action records a single installed module-open request and
returns pending. Subsequent `status` requests progress that setup: they await the
module and issue the owned `Workbench.OpenResource` request exactly once. This
static method is documented in the pinned Workbench declaration; its boolean
return is observed rather than treated as an asynchronous guarantee. If an API
is already available, its actual
world/mode observations guard against replacing another world. In the fresh
owned `-noOpenLastResource` session, setup can request the owned resource before
GetApi becomes available, avoiding an invented circular API prerequisite.
Its actual native acceptance and later API availability remain target gates.
After setup, `status` polls observations without issuing another world-load,
play, spawn or delete request. Native request refusal is retained and never
retried. Duplicate installed load requests fail. Phase-zero readiness describes
world/mode availability only.
It cannot complete a callback case. Failed or partial callbacks remain pending,
failure or unavailable under the separately bounded transport deadline.

Raw game-project/editor-world strings are retained. The actual engine may report
the base game project while the candidate addon is separately loaded. The bridge
therefore calls the installed native resolver on
`$BerylComponentCallbackProbe:worlds/BerylCallbackProbe.ent` with `mustExist=true`.
`addon_world_resolved` must be true and `addon_world_path` must exactly identify
the owned absolute world. Independently, the nonempty raw editor world path is
passed to the same native resolver. `world_path_resolved` and
`world_absolute_path` must establish the same absolute world before any stage is
ready. Only slash spelling is normalized when comparing native output. No path
is synthesized from a GUID, relative string, base project, or failed resolver.
Failure to resolve or an ownership mismatch remains unavailable. An initially
empty editor world while loading may remain pending; it does not pass readiness.

The adapter uses `Local\BerylOwnedWorkbenchSessionV1`, refuses an existing
Workbench, starts without force or reuse, checks PID/start time/executable path
before and after operations, and verifies installed script/executable hashes.
It does not save the world, enable NetAPI, alter security settings, install an
addon or stop another user's session. Cleanup requires the same owned process
identity. The final delete response is retained before the edit-mode request.
Raw session logs are captured after owned cleanup on success and failure.
The revised cleanup must observe `WaitForExit(5000)` returning true before
reporting `owned_process_stopped`. Unconfirmed exit records an evidence error
and cannot pass nominal success; an earlier timeout/failure remains that outcome.
Its six inert mocked checks establish harness branching only, not actual engine
shutdown. Historical attempts lacking that check are not upgraded retrospectively.

Default bounds are 30 seconds per stage, 64 status polls, 200 ms between polls,
and 180 seconds for the whole transport. Monotonic deadlines include capture and
cleanup already paid. The outer existing owned process job has a 240-second
budget. A late return, startup failure, timeout, cancellation or stale input is
never interpreted as a source trap or a matching callback failure.

## Callback observations and receipt interpretation

Fixture identities are registered tokens 1 and 2, not memory addresses. Each
callback emits adjacent before/after observations including:

- Actual state-root presence and retained root identity.
- Callback owner matching the component's current owner.
- Ready, initialization, frame and deletion counts.
- Target-rounded elapsed-value equality against the observer's separately
  maintained accumulator.

Floating-point equality here is a target-side rounded equality check. There is
no claim of bit serialization, independent numerical proof or universal f32
equivalence. The independent scalar lifecycle corpus remains separate evidence.

Initialization must occur exactly once on each owner. Frames must begin after
initialization, progress exactly once per callback and never resume after the
observed deletion. Distinct owners and distinct plain state roots are checked
after at least three frames per entity. Four authority observations are ordered
1,2 before readiness and 1,2 before deletion. Both delete handlers must publish
their state changes. Unexpected or duplicate callbacks fail the experiment.

The complete receipt carries the exact token, loaded addon identity, native
resolved world identities, raw base-project/editor observations, world/mode,
seven ordered case IDs, contiguous event sequence, total row count, check count,
and a rolling ASCII checksum. A maximum of 4,096 rows is admitted. The Python
validator independently parses the callback protocol, verifies the per-owner
state machine and before/after pairing, requires successful identity/equality
observations, and verifies eight checks per callback row plus each control check.
It rejects generic complete flags without the expected observations.

The explicit codec `enfusion.jsonapistruct.bool01-emptyarrays.v1` admits Boolean
fields only as JSON booleans or integer 0/1. Strings, floating-point substitutes,
other integers and missing Boolean fields fail. Omitted `caseIds` means an empty
array only when integer `executed` is zero. Omitted `rows` means empty only when
both integer `executed` and `event_count` are zero. Completed execution requires
both actual arrays and the full strict seven-case trace. Unknown fields fail.
Each RPC retains untouched `Raw` and `Response`; a separate
`normalized_response` and codec metadata record the conversions. Python parses
the original Raw JSON independently, checks it against Response, recomputes the
codec result, and checks it against the stored normalized response and the final
delete-stage completion. Decoding is not an execution or semantic result.

The final focused pure receipt/codec gate passes 35 cases in
`build/component-callback-receipt-tests-b_vexo6k/result.json`: the 22-case protocol
corpus plus three admitted wire cases and ten deliberate wire faults. The earlier
22-case receipt remains at `build/component-callback-receipt-tests-cb4_y22s/result.json`.
The earlier
20-case receipt remains historical at `build/component-callback-receipt-tests-uq9trfkp/result.json`.
An independent reviewer demonstrated that the earlier parser admitted repaired
traces moving authority before initialization. The final parser requires the
corresponding owner to be alive and authority 1 before initialization of owner 2;
both repaired sequence/checksum counterexamples are rejected. It catches wrong
tokens, Boolean integer fields, unknown/missing fields, wrong project/world,
missing play mode, partial/unknown cases, checksum/count/sequence errors, state
root changes, skipped handlers, duplicate counts, unknown owners, failed
authority, skipped delete and reversed callback order. This is synthetic harness
evidence only. Compiler and engine execution were not performed for that gate.

## Root-owned commands and release gates

Use the identified trusted Python runtime and an explicitly hashed private
compiler under a build subdirectory. The active `build/beryl.exe` is rejected.
The first root preparation attempt at
`build/component callbacks & spaces-auqqvvoi/results.json` failed before any engine
execution because a verifier hardcoded the wrong generated directory. It remains
a failure. The corrected verifier resolves the unique emitted source through the
actual artifact manifest and source-map basename/bytes/hash, rejecting ambiguity
or an identity mismatch. No generated source was relocated or edited.

The next root-owned preparation and actual headless compilation at
`build/component callbacks & spaces-mh6oehf9/results.json` failed with four
project-script diagnostics before runtime started. The trusted observer's long
trace concatenation exceeded the engine expression-complexity limit (including
an incompatible `|` diagnostic), and the engine rejected increment operators on
indexed array-value temporaries. These are confirmed experimental fixture
defects. The source template now constructs the identical trace through short
sequential concatenations and updates initialization/deletion counts through an
explicit index, integer next value and indexed assignment. The old attempt
remains a failure; neither its generated artifact nor its receipt was changed.
A new exact candidate must compile before callback delivery can be attempted.
The historical failure's raw engine receipt establishes an executed failed
compilation even though its older summary scope incorrectly said `not_run`.
New receipts add requested/invocation/process/adapter/target outcome fields and
classify returned `Compiled` failures as `executed_failure`. A transport attempt
before any spawn request leaves callback delivery `not_run`; a spawn attempt or
partial observations remains unconfirmed until the complete trace is verified.

The following owned compilation at
`build/component callbacks & spaces-we9l6mo3/results.json` also failed before
runtime: the engine rejected `WorldEditor.Cast(...)` in the trusted RPC bridge.
The repaired observer compiled. The pinned WorldEditor declaration inherits
WBModuleDef through native pointer classes rather than exposing a Managed `Cast`
method. The installed primary example in `interfaceResourceManager.html:260`
uses `ResourceManager rm = Workbench.GetModule(ResourceManager);` directly.
That file's SHA-256 is
`c9dc9088b5dbe1437e25b630e927a35a1f287900cc5b5b5692eb0a69cd653995`.
The bridge now applies that documented native-module assignment form:
`WorldEditor editor = Workbench.GetModule(WorldEditor);`.
The WorldEditor-specific assignment remains subject to the next exact engine
compilation; no missing `Cast` method or unchecked cast is invented. The failed
receipt remains unchanged and callback delivery has not yet executed.

The next attempt at `build/component callbacks & spaces-umgx3dcq/results.json`
compiled all probe scripts successfully, then stopped before loading a world or
spawning either entity. Its unchanged raw runtime receipt reports the base game
project `./addons/data/ArmaReforger.gproj` while GetLoadedProjects includes the
candidate addon. It also establishes JsonApiStruct's numeric Boolean wire form
and omitted empty arrays. The former strict schema hid the bridge's legitimate
unavailable diagnostic behind a missing-field failure. The native identity and
explicit codec changes above repair those confirmed harness assumptions; they
do not retroactively turn that attempt into success. The revised PowerShell
codec has separate 18-case pure evidence at
`build/callback-wire-codec-bc7f1933192648588cfdd0e373b44062/result.json`.
Neither that receipt nor Python's 35-case codec receipt executed an engine or
closed callback delivery.

At `build/component callbacks & spaces-9a_h8ibc/results.json`, all probe scripts
again compiled and the native addon-world resolver returned the exact owned
absolute world. The revised wire codec preserved and decoded the raw response.
Runtime remained unavailable before world loading because GetApi returned null
immediately after OpenModule. That observation does not establish whether module
initialization is asynchronous or the API requires a loaded world. The bounded
setup above tests those interfaces through separate requests without inventing
a readiness guarantee, repeating unknown errors, or declaring pending as success.
The 9a receipt remains unchanged; no callbacks were delivered in that attempt.

At `build/component callbacks & spaces-gbikvh1v/results.json`, the first load
response returned pending. The first subsequent status request reached native
SetOpenedResource and timed out after its existing eight-second RPC budget.
Retained console logs show loading of the exact addon world and its inherited
Eden world, including GenericTerrainEntity terrain loading reported at about
2,885.6 ms. No VM exception, prefab spawn or callback trace was recorded. That
evidence establishes actual loading began; it does not isolate every paid cost
or justify changing a timeout into success.

The bounded local inventory found only readable Eden, CombatOps-Eden and Arland
SubScene seeds; it did not find a verified smaller standalone world. Base assets
are FORM/PAC1 archives, not ZIP files, and no guessed archive parser was used.
The empty SubScene attempt is retained at
`build/component callbacks & spaces-gl3c63j7/results.json`. Source generation and
engine compilation succeeded. Native loading then logged `Can't open Subscene`
and a 62.1688 ms LoadWorld phase. The first status RPC timed out before any spawn,
and no callbacks were observed. The empty standalone SubScene hypothesis is
rejected. This shorter native load is distinct from the earlier inherited Eden
attempt; neither result identifies terrain as the general setup failure cause.

The exact inherited and rejected 13-byte world payloads are retained in
`packages/sparkos/component-callback-probe/fixtures/original-eden-world.ent.txt`
and `fixtures/rejected-empty-subscene.ent.txt`, respectively. Every old receipt
and its 18-input inventory remain unchanged. The following GenericWorldEntity
candidate added only the documented root shown above and its primary declaration
as the nineteenth source input. Its Python helper changed only the required
inventory count; observer, RPC, transport, time budgets, resource identities,
native path proof, authority and complete trace guards were unchanged.

At `build/component callbacks & spaces-r1n7z589/results.json`, source generation
and engine compilation succeeded. Native logs show loading the exact owned
GenericWorldEntity resource in 10.4442 ms, CreateEntities in 51.1593 ms and
LoadWorld in 69.5813 ms, with no recorded world error or VM exception. The first
status RPC nevertheless timed out without returning readiness. No entity was
spawned and no callbacks were recorded. These observations distinguish loading
from proven readiness; they do not establish a generally supported standalone
world format or all required services.

The final single-call diagnostic candidate retained that exact world and replaced
`editor.SetOpenedResource(resp.addon_world_path)` with
`Workbench.OpenResource(resp.addon_world_path)`. The existing pinned
`interfaceWorkbench.html` declares this exact static boolean signature. Its
documentation supplies no asynchronous or non-modal completion contract, so
acceptance and subsequent native world readiness must be observed in a new owned
attempt. No new API input or parser behavior is assumed. The exact preceding
10,247-byte RPC source, SHA-256
`035b3705cf6aebd85459b6872b71fd7ea7292107e5d70dc4f8b6204d18e026f4`,
is retained at
`packages/sparkos/component-callback-probe/fixtures/previous-set-opened-resource-rpc.c.txt`.
Python, world, 19-input inventory, observer and transport remain unchanged.
There is no automatic fallback, timeout widening, repeated resource request,
identity exemption, authority bypass or weakened trace requirement. Failure
leaves callback delivery and usable world readiness incomplete.

At `build/component callbacks & spaces-it3wl_wr/results.json`, source generation
and engine compilation passed. The first load RPC returned pending, then the
status RPC returned normalized `status="unavailable"` and
`failure="Owned world load request refused"`. Native resolution identified the
exact owned addon-world file. The recorded load stage took 461 ms. The raw reply
and its derived normalization are retained separately; the preceding pending
reply is not a successful load receipt. No world-loading message, spawn or
callback was recorded, and owned process exit was confirmed. The experiment
therefore remains unavailable and is not adopted as a working opening route.
The callback, real component state and world-lifetime gates remain open.

Neither this refusal nor an earlier timeout proves a modal prompt, a terrain
cause, an invalid resource path or a generally unsupported engine API. The next
diagnosis must establish its specific preconditions before another candidate:

- Inspect metadata from the owned editor window for an unready module or an
  actual modal prompt. Logs without an exception do not establish either state.
- Check the fixture's resource registration and the documented filename/path
  expectations against actual native observations. Exact resolver success alone
  does not prove an opening method accepts that representation.
- Establish how the documented global opening call routes a world resource to
  the owned WorldEditor module; no generic ResourceManager example proves that
  routing or its readiness requirements.
- Separate request acceptance, native load completion and subsequent API/RPC
  responsiveness using an explicitly supported owned setup. A short LoadWorld
  log or a timeout alone cannot substitute for the missing readiness response.

These are bounded investigation hypotheses, not implemented fixes or known
causes. No further trial, guessed flag, new API alias, retry, timeout change or
weakened world/session/authority/trace guard is selected in this checkpoint.

```text
python scripts/verify-component-callbacks.py --self-test

python scripts/verify-component-callbacks.py
  --beryl <identified private compiler>
  --expect-compiler-sha256 <exact hash>
  --workbench-tools <existing plugin root>
  --prepare-only
```

Preparation executes compiler checks/generation, retains the original artifact
and compiler/tool/plugin/source/API identities, and creates an isolated fixture.
It does not launch the engine. The root integration owner then reviews actual
emitted linkage and prepared source before selecting an engine stage:

```text
... --powershell-host <identified trusted PowerShell>
    --engine-exe <exact installed Workbench executable>
    --engine-stage compile

... --powershell-host <identified trusted PowerShell>
    --engine-exe <exact installed Workbench executable>
    --engine-stage runtime
```

Compile proves only exact script compilation. Runtime success requires all seven
actual callback cases, owned world/session observations, raw logs, exact artifact
identity, and unchanged inputs through final cleanup. The `results.json` keeps
each scope separate and failed attempts remain immutable evidence.

## Remaining interpretations and next packet

### Native resource-name and readiness diagnosis — selected experiment

The current trusted RPC separately observes `module_present` and `api_present`.
Both are obtained from actual `GetModule(WorldEditor)` / `GetApi()` results,
including before a resource-registration rejection. Neither substitutes for
world presence, mode, path, authority or trace evidence.

The same installed Workbench declaration inventory includes
`GetResourceName(string path) -> ResourceName` and `OpenResource(string filename)
-> bool`. Their detailed descriptions are empty: they do not specify an accepted
path spelling or a synchronous initialization contract. This experiment therefore
does not infer that a resolver-supported absolute path must be accepted by the
opening call.

For each fresh owned job, request the native resource name of the pinned absolute
file. Require `{BCCBA11B20261008}worlds/BerylCallbackProbe.ent`, as frozen in its
metadata, then require native `GetAbsolutePath` of that name to identify the same
absolute file. Open exactly that observed name once. A failed identity, failed
roundtrip, empty name or refused opening returns unavailable with the raw
observations retained. There is no alternate spelling or automatic fallback.

The strict response gains five fields: the resource name and its absolute
roundtrip, resource-name resolution, module presence and API presence. Completion
requires all three new Booleans true and both resource identities exact, in
addition to every existing world/mode/authority/callback requirement. Earlier
receipts remain evidence for their own earlier response and source bytes.

The exact previous 10,240-byte RPC template is retained at
`packages/sparkos/component-callback-probe/fixtures/previous-absolute-open-resource-rpc.c.txt`,
SHA-256 `ba32d6b0071ce6031fc245dd775e2cfb91992e1925db81837f41c35d018d3216`.
The 23-byte world, observer, prefab, metadata and 19-input declaration inventory
are unchanged. This is a selected diagnostic experiment; no runtime success is
implied by the new fields or its preparation.

#### First native-name outcome and resolver correction

`build/component callbacks & spaces-zbkxr69s/results.json` retains a successful
source build and script compilation, followed by an unavailable load stage.
The first RPC observed the exact resource name
`{BCCBA11B20261008}worlds/BerylCallbackProbe.ent`, `module_present=true`,
`api_present=false`, and a successful addon-alias absolute resolution. Passing
the complete resource name to `GetAbsolutePath(string relativePath, ...)`
returned false and an empty path. The admission gate stopped before any resource
opening request. No world was loaded, entity spawned or callback observed.
Owned process exit was confirmed. This distinguishes successful registration
from that failed resolver input; it does not establish general world readiness
or an invalid ENT resource.

The next fixed correction uses `ResourceName.GetPath() -> string`, an exact
installed declaration with no additional behavioral documentation. The raw
`resource_path` is retained and used as the resolver argument. Exact resource
name and exact absolute-file requirements remain unchanged. There is no manual
GUID stripping, guessed addon prefix, alternative spelling or same-job retry.
`fixtures/previous-guid-roundtrip-rpc.c.txt` preserves the 11,765-byte preceding
template, SHA-256
`c411d8a1038c8a33e86b0233bfd844d05e55a1885990daf0308f40d425cb0d90`.
The current source contract adds the exact 29,087-byte installed ResourceName
HTML, SHA-256
`ad6bacd660254a8f476338de963a59ae1f525cad9bd00680c6d7a7ba15764c9f`,
bringing the inventory to 20 inputs. Earlier inventories are retained in their
own receipts. The corrected opening route is still experimental until executed.

#### Native path outcome and explicit module opening

`build/component callbacks & spaces-6d_vvfs5/results.json` compiled successfully.
Both load/status replies observed the exact native resource name,
`resource_path="worlds/BerylCallbackProbe.ent"`, and the exact owned absolute
roundtrip. `module_present=true` and `api_present=false` were observed throughout.
The first load reply was pending; the single global native-name opening call in
the next status request returned false, producing unavailable. The recorded
load stage took 453 ms. No world-load log, entity spawn or callback was observed;
owned process exit was confirmed. Resolver correction is supported by this
observation; successful opening is not.

The preceding load guard only called `OpenModule` when `GetModule` was null.
It therefore skipped an explicit open request in this observed non-null-module /
null-API configuration. No inspected primary contract equates a registered module
pointer with an initialized/open editor. The next fixed candidate explicitly
requests `OpenModule(WorldEditor)` exactly once per fresh owned load. It retains
`module_open_requested` and the actual `module_open_accepted` Boolean. False is
unavailable; true is only pending. Completion also requires both flags true,
in addition to actual module/API/world/mode/native identities and every callback
check. A reset or missing receipt cannot manufacture opening acceptance.

The global native-name resource opener remains unchanged for this experiment,
so setup is tested independently of another route change. There is no retry,
timeout widening, automatic fallback, force flag, guessed UI action or authority
exemption. `fixtures/previous-resource-path-opener-rpc.c.txt` preserves the
preceding 11,954-byte RPC, SHA-256
`0ff202eff2068a59927422a93d39420d8bc7a181bb843edcb55f3750a8f46c83`.
The 20-input API inventory and exact world/observer/prefab remain unchanged.

#### Explicit opening outcome and activated module-specific route

`build/component callbacks & spaces-spoin57k/results.json` compiled successfully.
The load RPC recorded the explicit module request and Boolean acceptance, with
`module_present=true`, `api_present=true`, and a pending status. The next status
RPC observed edit mode, an existing unnamed world and the same non-null API.
Its single global native-name resource opener returned false, so the terminal
status was unavailable. Native resource identity and path roundtrip remained
exact; owned process exit was confirmed. This establishes the bounded module/API
setup repair, not pinned-world readiness or component callbacks.

The current fixed candidate waits for a non-null API after the explicit request,
then calls the documented inherited `editor.SetOpenedResource(pinnedAbsolutePath)`
once. The earlier module-specific trials skipped `OpenModule` whenever a
registered module pointer existed. Their missing active-API precondition is now
separately observed. This is a new candidate with an explicitly established
precondition; it is not a same-job fallback or an identical retry. It retains
every resource, world, mode, authority, state, case and trace guard and the
unchanged deadlines. The post-open API diagnostic is explicitly recomputed even
if the module disappears, avoiding a stale presence value.

`fixtures/previous-explicit-module-global-opener-rpc.c.txt` retains the preceding
12,506-byte RPC, SHA-256
`c5d9edfdfb79d8b2cc911eeb06b605b80ec853bb85a2c41961da549723d8a08b`.
No async/non-modal behavior, reload stability or lifetime guarantee is inferred
from the primary declaration or the now-successful module activation.

At `build/component callbacks & spaces-7gdcd8fr/results.json`, the activated
module-specific candidate compiled successfully. Initial load returned pending
with actual opening acceptance, non-null API and exact resource/path identity.
The first status request logged the exact owned world loading,
CreateEntities 44.4227 ms and LoadWorld 56.9505 ms, but returned no response within
its unchanged eight-second RPC deadline. Its terminal outcome is timeout, not
refusal or a matching source trap. No readiness receipt, spawn or callback was
recorded. Owned process exit was confirmed with no cleanup evidence errors.
Selected logs contain no world or VM exception; this absence does not diagnose
the cause, establish non-modal behavior or prove world services are usable.

The [separate dispatch diagnosis](P4_WORKBENCH_DISPATCH_DIAGNOSIS.md) defines the
next harmless prerequisite. Its fixed direct-thread worker does no world/resource
opening. Actual snapshots can establish bounded cooperative dispatch and retained
sentinel state, not native-operation safety or transport-send order. A deferred
opening, if selected later, receives its own fresh source, explicit action/token
count, post-load context/identity checks and immutable receipt. No timeout retry
or production promotion is authorized by the sentinel result alone.

The following are measured gates, not assumptions supplied by declarations:

1. Whether the owned absolute world/project paths are exposed as required.
2. Whether the experimental documented-class root is admitted as a standalone
   world and the fixed prefab resolves with sufficient world services.
3. Whether Workbench RPC and runtime component observations access the required
   fixture registry in this mode and preserve state through mode changes.
4. Whether the two fixtures hold replication authority and physically delete.
5. Whether frame callbacks and callback-owner observations remain valid at each
   admitted point, including after the superclass deletion hook.

If an instrumentation observation itself has no supported lifetime, its failure
cannot automatically be diagnosed as a Beryl compiler defect. Preserve logs and
classify the observation capability before changing an implementation.

A successful probe closes only bounded scalar component creation and callback
delivery. It does not prove arbitrary component inheritance, owner retention,
world teardown, resource closure, tablet service reentry, queued work, client UI
isolation or multiplayer. The next packet connects one reviewed tablet service
adapter to the existing operation-local lifecycle protocol, preserving current
service references and actual receiver-after-argument ordering, then compares
ordered real service observations. Full tablet deployment remains a later gate.

## Deferred native-opening candidate

The harmless dispatch probe passed six actual cases on the pinned engine at
`build/workbench dispatch & spaces-csb3u27_/result.json`. Its worker entered
before caller continuation and resumed afterward; it did not open any resource.
The new callback template `ce6324bdbab75aebfaf6f832e76c59fd9dbd1617506a5c9c96c6bbc83caa8099`
uses that separately observed dispatch form for one experimental native open.

A global GameCommon worker yields for 200 ms, then obtains fresh native editor
references. It checks the same exact addon/resource/native roundtrip, edit mode,
no play mode and no unrelated opened world. It calls SetOpenedResource on the
pinned absolute path once. The handler returns pending at submission; subsequent
requests expose requested/submitted/entered/resumed/returned as exact 0/1
integers plus Boolean acceptance. Readiness and all gameplay actions wait for
returned=1 and accepted=true, as well as their existing identity/mode gates.
No native object is retained across the yield. Lost state cannot resubmit, and
there is no synchronous fallback. Premature stop remains pending; confirmed
owned process exit is the cancellation boundary. Source contracts now include
the exact installed Enforce thread/Sleep declaration page (21 passive inputs).

The preserved previous synchronous template has SHA-256
`c7f91fd70da71a51997b9b071ac13e17ed2b57a0d085eef032237ed62889dbfa`.
Strict Python/PowerShell field and ordering validators must admit the new
37-field response before execution. A native open that blocks, reloads state
or never returns stays incomplete even if logs report LoadWorld. The harmless
sentinel supplies no stronger native-operation guarantee.

The matching deferred response/checkpoint passed 124 Python-only cases at
`build/component-callback-receipt-tests-_0hslqt1/result.json`. Its 89-case inert
PowerShell attempt remains incomplete; the configured host also stopped
returning from an independent fixed-output diagnostic. Requested stop did not
confirm exit. No new engine compile or deferred native-opening run followed.
This is an unavailable local harness capability with unknown cause, not a
successful transport or callback gate and not established policy denial.
Raw earlier failures, the original interrupted diagnostic and the manual
recovery record `build/oct08-host-interruption-_k33mwzs/result.json` remain
separate from source review and successful harmless dispatch.

The final Python envelope follow-up additionally requires exact integer schema1,
an explicit empty evidence_errors list, ordered actual session-check sites and
same pinned PID/start/executable, bounded times/action groups, and matching
engine/tool/project identities. It does not add an end marker the adapter never
emits or a project field to individual session-check rows. Fifty synthetic
envelope/fault cases pass at
`build/component-callback-envelope-tests-tk4etbbz/result.json`; the existing
124-case gate passes against the same final verifier at
`build/component-callback-receipt-tests-h5p1oexj/result.json`. Both are pure
validation, separate from engine execution.

Root source preparation passes at
`build/component callbacks & spaces-gxs19pd4/results.json` with private compiler
`76aeaacfea6866e66e3020f983eaa22089d545ad0f3b60fedfd28c3d58972bd7`.
It preserves the exact staged candidate, original generated artifact, source
maps, source/tool/compiler hashes and source-job receipt. No host, native program
or engine ran. New template parsing by Enfusion and actual native opening remain
incomplete while the local host is unavailable. Live MESH and installation are
unchanged.
