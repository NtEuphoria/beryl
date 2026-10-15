# P4 — Workbench dispatch diagnosis and bounded async sentinel proposal

Date: 2026-10-08. Status: **proposal and passive source review only**.

This packet defines a small trusted diagnostic experiment. It does not implement
an editor bridge, release a compiler capability, launch Workbench, execute a
compiler, or establish engine callback delivery. The current engine owner must
review, prepare, compile, and execute any subsequent fixture in a fresh owned
session. Only this document was added for this packet.

## 1. Question and evidence boundary

The immediate question is whether an owned Workbench session can execute a
fixed harmless script function asynchronously, return a NetAPI response, and
then report the function's completion without opening a world.

This is deliberately smaller than the world/callback experiment. Its positive
result would establish a particular dispatch route on an exact installation.
It would not establish that native resource opening is safe on that route, that
it avoids a dialog, that script state survives a world reload, or that a
generated component receives engine callbacks.

The preceding resource-opening investigations have separate outcomes:

- An inherited `WBModuleDef.SetOpenedResource` attempt can finish a logged
  `WorldEditor: LoadWorld` phase while its calling status RPC still times out.
  The retained `gl3c63j7` console also explicitly reports `Can't open Subscene`;
  its 62.1688 ms load phase does not establish a valid world or healthy RPC.
- The subsequently reported GenericWorldEntity fixture removes that particular
  malformed SubScene basis, but a short logged native load phase still does not
  establish that the enclosing request returned.
- A static `Workbench.OpenResource` call using an absolute filename was refused.
  Refusal is distinct from a blocking call or a completed world transition.
- The engine owner is investigating one native resource-name spelling with an
  exact native identity roundtrip. That experiment remains separate from the
  async sentinel proposed here.

This packet does not reinterpret any failed or incomplete receipt as success.
The authoritative result for an executed attempt is its immutable receipt and
raw logs. A new source or dispatch policy requires a new attempt.

## 2. Exact primary API inventory

Installed Enfusion API root:

`C:/Program Files (x86)/Steam/steamapps/common/Arma Reforger Tools/Workbench/docs/EnfusionScriptAPI/html/`

Installed game-script API root:

`C:/Program Files (x86)/Steam/steamapps/common/Arma Reforger Tools/Workbench/docs/ArmaReforgerScriptAPIPublic/html/`

| Primary file and lines | Exact declaration or documented behavior | What remains unknown |
|---|---|---|
| `interfaceScriptModule.html:114,155–223` | `proto bool Call(Class inst, string function, bool async, out void returnVal, void param1=NULL, ... void param9=NULL)` | Target module/function availability in this addon; survival across reload; native editor-operation suitability |
| `interfaceScriptModule.html:223` | `inst == null` calls a global function; a non-null receiver calls a class method. `async=true` creates a thread where sleep/wait is legal. `async=false` uses the main thread and blocks. The called result is returned through `returnVal` only for synchronous calls. | A true dispatch result does not establish later async completion or native operation success |
| `interfaceScriptModule.html:126–136` | The official example declares `string output;` and calls `mod.Call(null, "WatchResult", false, output);` | The example uses a dynamically compiled module; this proposal does not use dynamic compilation |
| `Page_Enforce_Syntax.html:821–833` | Script threading is cooperative. No switch occurs until `Sleep` or `Wait`. The example uses `Sleep(1000)` for 1 second, and `thread TestThread()` creates an async script thread. | Editor pumping before a world exists; ordering between RPC transport transmission and thread resumption |
| `interfaceWorkbench.html:144,559` | `static proto ref ScriptModule GetWBScriptModule()` | No documented lifetime or reload-stability promise |
| `interfaceWorkbench.html:145,534` | `static proto ref ScriptModule GetWBGameScriptModule()` | It must not be treated as the same module/state as the Workbench module |
| `interfaceWorkbench.html:111–113,667` | `GetModule(TypeName) -> WBModuleDef`, `OpenModule(TypeName) -> bool`, `CloseModule(TypeName) -> bool` | No documented synchronous module/API/world readiness contract |
| `interfaceWorldEditor.html:122–125` | `GetApi() -> WorldEditorAPI`; `SwitchToGameMode(bool debugMode=false, bool fullScreen=false)`; `SwitchToEditMode()` | No async completion guarantee for these calls |
| `interfaceWBModuleDef.html:132,278–286` | `proto external bool SetOpenedResource(string filename)` | Detailed documentation is empty; path formats, dialog behavior, reload behavior, and completion are not specified |
| `interfaceWorkbench.html:142,484` | `static proto ResourceName GetResourceName(string path)` | Detailed documentation is empty; conversion of a particular input must be observed |
| `interfaceWorkbench.html:143,692` | `static proto bool OpenResource(string filename)` | Detailed documentation is empty; an accepted request is not proof of readiness |
| `interfaceResourceName.html:120,197` | `proto external string GetPath()` | Detailed documentation is empty; do not equate its result with an absolute path without a native check |
| `interfaceResourceName.html:121–124,222,241` | `IsExternal()` means GUID plus store-name/extension; `IsInternal()` means GUID only | Representation checks alone do not prove this owned file resolved |
| `interfaceScriptCallQueue.html:109–122,139–151,614` | `Call`/`CallLater` queue work for later frame update, retain arguments until execution/removal/destruction, and `Tick(timeslice)` executes elapsed calls | No Workbench-owned queue or pre-world queue pump is established |
| `interfaceArmaReforgerScripted.html:140,536,176,1522` | `GetCallqueue() -> ScriptCallQueue`; `OnUpdate(BaseWorld world, float timeslice)` | The declaration does not establish that the game queue ticks in an empty editor |

The complete local Workbench, WBModuleDef, WorkbenchPlugin, and WorldEditor API
tables inspected here expose no dedicated editor timer or deferred-resource
opening method. `WorkbenchPlugin` exposes `Run`, `RunCommandline`, `Configure`,
and `OnResourceContextMenu`; their presence is not an async scheduling contract.

### 2.1 Exact passive input identities

These are content hashes read while preparing this document, not execution
receipts. A future experiment captures and retains its own exact inputs.

| Input | SHA-256 |
|---|---|
| `EnfusionScriptAPI/html/interfaceScriptModule.html` | `37db95134ae2c214c23169a268e3504aed864c169f99551ec26ed75934ed0210` |
| `EnfusionScriptAPI/html/Page_Enforce_Syntax.html` | `df83332c65707ce3e9a751c76fe323f1e5fee5459814ba7b5ee850fb325a572d` |
| `EnfusionScriptAPI/html/interfaceScriptCallQueue.html` | `6d9b2b3b8c4eba71f80cf10e987b5ce191c7321ebe50365c15fdba1d6cc88763` |
| `EnfusionScriptAPI/html/interfaceResourceName.html` | `ad6bacd660254a8f476338de963a59ae1f525cad9bd00680c6d7a7ba15764c9f` |
| `EnfusionScriptAPI/html/interfaceWorkbench.html` | `6da66bb00dd8cadb84463605e7272d93a01e179c8bd651dbdc614d3a68bbdf0f` |
| `EnfusionScriptAPI/html/interfaceWBModuleDef.html` | `ca3377a5fa8aea08913f782ed770fe9421e8adfe6abb40d40c594d6aa13d550d` |
| `ArmaReforgerScriptAPIPublic/html/interfaceArmaReforgerScripted.html` | `092859330a59462fb963db8ea6c4d99b087f03fdbe1831c6a017ee8258b0b9a1` |
| `C:/Program Files (x86)/Steam/steamapps/common/Arma Reforger/addons/core/data.pak` | `a2f2aee2b1043ebee24995581fc53fb5f3713195fda432e6c2b4c5acdcc64ea4` |
| Existing plugin `scripts/Invoke-WorkbenchRpc.ps1` | `d5a26658c8beed24d864f1b6842a667413acb929ef7684cdb321e5018e485ca1` |
| Existing plugin `scripts/Start-WorkbenchDaemon.ps1` | `25f481f771109f0d3007b507e947d46aae20ca935ec99a1ff03721d334196c70` |
| Existing Beryl `scripts/component-callback-engine.ps1` | `2994f9b6a1a748017ae403c97dc22f5cb2e660f1d4e26a753d51fedb191f66a6` |
| Callback `rpc.c.in`, passive snapshot during native-name investigation | `c411d8a1038c8a33e86b0233bfd844d05e55a1885990daf0308f40d425cb0d90` |

The last entry identifies one observed source snapshot. It is not a freeze of
the engine owner's ongoing experiment and cannot substitute for its receipt.

### 2.2 First-party installed examples and their limits

A bounded direct text read of the installed `core/data.pak` found:

1. `CheckGUID : NetApiHandler` constructs a GUID-only `ResourceName`, calls
   `Workbench.GetResourceName(guid)`, and treats an unchanged GUID string as
   unresolved. This is concrete native-name conversion usage.
2. `OpenXOB : NetApiHandler` calls
   `Workbench.GetModule(ResourceManager).SetOpenedResource(req.path)`. It ignores
   the Boolean result and returns a response whose `Output` is not assigned.
   This is XOB/ResourceManager behavior, not a reliable world-load gate.
3. No `Workbench.OpenResource` call-site example was found in that core archive
   or either inspected local documentation set. This is a bounded search
   finding, not a claim that no such example exists elsewhere in the game.

The installed-source search PowerShell script was denied by the local script
execution policy during the earlier passive investigation. It was not changed,
copied, retried with a policy override, or used to launch Workbench. The primary
archive snippets above were read directly as bounded data instead.

## 3. Proposed isolated fixture

Use a new addon, token, job directory, and fixed trusted source inventory. Do not
change the existing callback fixture while its resource-spelling attempt is
running. The initial fixture contains no world, prefab, entity spawn, component,
UI, terrain, or native resource-opening call.

Two separately identified script sources are proposed:

- A Workbench-side source containing fixed global functions and private static
  sentinel state, tentatively under `scripts/Workbench/`.
- A WorkbenchGameCommon NetApiHandler containing the bounded RPC facade,
  tentatively under `scripts/WorkbenchGameCommon/`.

Directory naming alone is not proof of module membership. The prepare/compile
gate must establish source discovery. The runtime gate must resolve the fixed
functions through the corresponding native module getter. An unresolved
function/module reports unavailable; do not force discovery with `LoadScript`,
`CompileScript`, arbitrary code strings, or a guessed startup flag.

### 3.1 Receiver and function choice

Prefer **fixed global functions with `inst=null`**. This matches the documented
global-call contract and official `WatchResult` example. It avoids retaining
the NetApiHandler instance as the async receiver while that request completes.

Do not substitute a `WorkbenchPlugin` instance created with `new`: the primary
core declaration has private construction/destruction, and this proposal does
not establish how a newly declared plugin is acquired or retained.

Use distinct fixed function names, for example:

| Fixed function | Module | Contract |
|---|---|---|
| `Beryl_WBDispatchArm(string token) -> int` | Workbench | Arm once; set phase `Armed`; reject empty/mismatched/duplicate token |
| `Beryl_WBDispatchRun(string token) -> int` | Workbench | Perform one cooperative yield, then mark harmless completion for the same token |
| `Beryl_WBDispatchObserve(string token) -> int` | Workbench | Total bounded scalar observation; no allocation beyond ordinary response/log construction, sleep, native editor effect, or state mutation |
| `Beryl_WBDispatchHealth(string token) -> int` | Workbench | Verify the fixed compiled-token identity and return the known module marker |
| `Beryl_WBGameDispatchHealth(string token) -> int` | WorkbenchGameCommon | Independently verify that module's compiled-token identity and marker |

These names and signatures are proposed trusted fixture interfaces, not
existing public Beryl capabilities. Use scalar marker constants and separate
observations; do not return a Workbench-private state object across modules.

### 3.2 State and successful transitions

Use a single private static state class in the Workbench source. No worker
instance or component is required. Its proposed fields are the compiled token,
armed token, phase, and bounded entered/resumed counters.

```text
Cold -> Armed -> Entered -> Yielding -> Completed
          \______________________________> Invalid
```

Required invariants:

- One arm and one async submission per fresh owned job.
- The supplied token equals the separately compiled token in both modules.
- Each entered/resumed counter is zero or one. Duplicate entry is failure.
- Worker resumption rechecks the token and expected phase before publishing
  completion.
- A module reset to `Cold` after arming is stale/unavailable, not an invitation
  to arm or submit again.
- A response from another token is stale even if its counters look correct.
- The worker writes only its sentinel state and fixed token-tagged diagnostic
  lines. It does not open resources or inspect gameplay objects.

An unexpected transition should produce a bounded invalid status/code. Do not
silently reset it to make the fixture pass.

### 3.3 Concrete `out void` binding pattern

`out void` is the API's generic output parameter. The documented call example
passes an ordinary `string` local directly; it does not allocate a `void`, use
an `out` call-site keyword, or build a return-value pointer manually.

The following is **proposed call-site code requiring compile verification**:

```c
ScriptModule wbModule = Workbench.GetWBScriptModule();
int armedPhase = -1;
bool armCallReturned = wbModule.Call(null, "Beryl_WBDispatchArm", false,
    armedPhase, compiledToken);

int ignoredAsyncReturn = 0;
bool asyncCallReturned = wbModule.Call(null, "Beryl_WBDispatchRun", true,
    ignoredAsyncReturn, compiledToken);

int observedPhase = -1;
bool observeCallReturned = wbModule.Call(null, "Beryl_WBDispatchObserve", false,
    observedPhase, compiledToken);
```

Check `wbModule` for null before any call. Validate the synchronous `Arm`
result before submitting async work. `ignoredAsyncReturn` is supplied only to
satisfy the declared parameter list: **never read it as an async result**. A
true `asyncCallReturned` is recorded as dispatch-return success, not completion
of the worker, successful resource loading, or successful engine execution.

The asynchronous function should begin with a fixed diagnostic entry and a
cooperative yield:

```c
// Proposed fixed global worker, compiled as trusted addon source.
// State/token checks surround each transition; omitted here for readability.
int Beryl_WBDispatchRun(string token)
{
    // Record Entered/Yielding and one token-tagged trace line.
    Sleep(200);
    // Recheck compiled token, armed token and expected phase.
    // Record Completed, increment resumed once, and print one completion line.
    return 1;
}
```

This is a deliberately bounded 200 ms yield, not a repeated sleep or a timeout
widening. Cooperative threading means `async=true` alone does not establish
that the native caller has yielded. The sentinel first establishes actual
execution on this installation; source ordering and the `Sleep` declaration
alone are insufficient evidence.

The worker's integer return is not consumed asynchronously. Completion is
observed by a later synchronous scalar call and matching raw trace records.
Compile verification must check the exact global-function lookup, scalar
output binding, and worker syntax. No successful compile is claimed here.

### 3.4 Simpler direct `thread` alternative

The same official syntax page supports a simpler first experiment:

```c
void Beryl_RunSentinel()
{
    // Verify the fixed compiled token and Armed state in this module.
    // Record Entered/Yielding exactly once.
    Sleep(200);
    // Recheck the token and phase, then record Completed exactly once.
}

// Proposed call inside a fixed trusted same-module handler/function:
thread Beryl_RunSentinel();
```

The zero-argument form follows the actual `thread TestThread();` example and
avoids guessing an extra argument-binding contract. The worker uses only the
already armed private static state, not a request object, receiver, pointer, or
captured local. Its source retains the same compiled token as the handler.

Prefer this direct syntax for the first same-module sentinel if source
discovery permits it. It eliminates reflected async function lookup, the async
`out void` placeholder, and interpretation of `ScriptModule.Call`'s Boolean.
The `submit` case instead means that the handler reached its explicit
after-`thread` observation and returned a complete reply. That is still not
worker completion. Keep the later observe/resume checks.

Two module-placement hypotheses must remain distinct:

- **Workbench-only sentinel:** handler, fixed worker, and private state belong
  to the Workbench script module. Source discovery and native module/marker
  lookup must first verify this. `scripts/Workbench/` is a proposed source path,
  not proof that NetAPI discovers addon handlers there. An unavailable route
  must remain unavailable; do not add a world to force its availability.
- **WorkbenchGameCommon sentinel:** handler, fixed worker, and private state
  use the already observed custom GameCommon handler route. A positive result
  is scoped to that module. It cannot establish a separate Workbench-only
  scheduling/lifetime contract or survive a later Game script reload by
  implication.

The first-party core archive supplies `CheckGUID`, `EBTInfo`, and `OpenXOB`
NetApiHandler implementations using Workbench APIs. A bounded archive search
found metadata for generated `NetApiHandler.c`, but not its base definition or
the module-getter implementations. Consequently the primary core snippets
support the handler/callback pattern; they do not establish initial addon
Workbench-module membership, discovery, or pre-world pumping.

The direct-thread variant does not need `GetGame()`, a game call queue, a world,
or a component to perform its own harmless scalar work. It nevertheless needs
actual compile, discovery, handler-response, yield/resumption, and module
identity evidence. The keyword's existence does not supply those results.

No inspected declaration gives a script-thread handle, a join/cancel API, or a
promise that the thread survives module destruction/recompile. Apply the same
owned-session cleanup, stale-state, deadline, and no-resubmission rules. A
GameCommon deferred opener remains a later distinct experiment even when its
same-module direct-thread sentinel passes.

## 4. Keep health, state, and transport observations separate

The current callback NetApiHandler is emitted into
`scripts/WorkbenchGameCommon/BerylComponentCallbacks.c`. It is not evidence
that arbitrary functions declared for the Workbench module share its state or
its reload lifetime.

Record these independent observations:

1. **Process identity:** the existing owned PID, creation time, executable
   path/hash/version, loaded-project list, and frozen inputs still match.
2. **Transport health:** a complete exact-token RPC response arrived within its
   bound. A running process or successful listener connection is not enough.
3. **Workbench module health:** its getter is non-null and its fixed health
   function returns the exact compiled marker/token.
4. **WorkbenchGame module health:** its getter is non-null and the separate
   fixed health function returns its exact compiled marker/token.
5. **Sentinel state:** the Workbench observer reports the permitted transition,
   and matching raw entered/resumed records are complete and unique.
6. **World/editor state:** not requested by the initial sentinel fixture.

If an enclosing Game-side RPC times out, a retained Workbench-worker completion
log can establish that particular worker event, but cannot establish healthy
Game-side transport or successful full verification. Conversely, an RPC health
reply does not establish that the Workbench worker ran.

Module getters and observation functions are looked up afresh for each RPC.
Do not retain and reuse a module reference across an actual world/script
reload. Do not serialize process pointers as module identities. A getter
returning an object alone does not prove the same compiled code is present;
the fixed compiled markers and exact retained source bytes provide the bounded
identity check.

Do not automatically re-arm, resubmit, or change the token after missing state.
World loading can compile/reload script code; whether it resets these particular
static fields is an experimental outcome. Use a new job for any new policy.

## 5. Predeclared initial cases and outcome interpretation

Predeclare this exact initial case set before execution:

| Case ID | Required observation |
|---|---|
| `dispatch.identity` | Exact owned session/project/input/token identity |
| `dispatch.wb-health` | Workbench getter and fixed marker call succeed |
| `dispatch.game-health` | WorkbenchGame getter and separate marker call succeed |
| `dispatch.arm` | One synchronous arm reaches the expected scalar phase |
| `dispatch.submit` | One async call returns true; no async output is consumed |
| `dispatch.complete` | One entered and one resumed event; observer reaches Completed under the same token |
| `dispatch.health-after` | Both health markers and RPC remain valid after completion |

The seven cases above describe the proposed two-module dispatch profile. If
the engine owner first selects a standalone direct-thread diagnostic, freeze
one of these smaller profiles before compilation:

- `workbench-only-sentinel.v1`: exactly `dispatch.identity`,
  `dispatch.wb-health`, `dispatch.arm`, `dispatch.submit`,
  `dispatch.complete`, and `dispatch.health-after`. The last case requires
  Workbench health and transport. GameCommon health is separately recorded as
  not selected; its absence is not converted to successful execution.
- `workbench-game-sentinel.v1`: exactly `dispatch.identity`,
  `dispatch.game-health`, `dispatch.arm`, `dispatch.submit`,
  `dispatch.complete`, and `dispatch.health-after`. The last case requires
  WorkbenchGame health and transport. Workbench-private sentinel health is
  separately not selected.

Profiles are fixed source/receipt contracts. Never select a smaller case set
after a missing result, reinterpret a GameCommon receipt as Workbench-only, or
change the meaning of `submit` without recording the selected dispatch route.

Record expected and completed IDs independently. A partial set, duplicate,
unknown ID, or extra event is failure; absent results are never completion.

The fixture should retain caller-before-dispatch, worker-entered,
caller-after-dispatch, and worker-resumed source records with bounded sequence
numbers and the compiled token. Preserve actual order rather than inventing
one from the intended implementation. Do not compare engine and host timestamps
as though they were a single exact clock. A successful sentinel establishes
dispatch and later observable completion. It does not by itself prove that a
subsequent native operation will begin after transport response transmission.

Use the current owned-job limits as explicit upper bounds unless the engine
owner freezes a separately justified policy: 8 s per RPC, 30 s per stage,
64 polls per stage, 200 ms between polls, and 180 s overall. The intentional
200 ms worker yield must be retained separately from these harness limits.

Statuses remain distinct:

- Unavailable: missing module/function/capability or refused fixed dispatch.
- Failure: wrong marker/token/state/order/counter or incomplete case set.
- Stale input: modified source/artifact/session identity or lost expected state.
- Timeout/cancellation: harness outcomes, not source traps or completed work.
- Success: complete initial case set, evidence, identity, and owned cleanup.

Late completion after a harness deadline remains a timed-out attempt. Neither
its log nor a later successful poll may overwrite that terminal result.

## 6. Later native-open experiment: separate gate

Only after the harmless sentinel passes may the engine owner propose a fresh
fixture whose fixed Workbench worker performs one native resource-open call.
Keep the original sentinel fixture and its receipt unchanged.

That later fixture must:

1. Pin one owned world and one filename spelling before execution.
2. Prove native addon resolution and any required native resource-name
   roundtrip to the exact frozen world before scheduling work.
3. Prove both module health markers and a fresh armed worker state.
4. Use one fixed worker function and the same explicit cooperative yield.
5. Recheck the token/state and permitted session/world conditions immediately
   before the native operation.
6. Record native call entry and, only if it actually returns, its Boolean value
   and call-exit event. Do not manufacture an exit event after an interrupted
   or reset VM.
7. Independently re-observe module health, native world identity, edit/game/play
   state, and transport after the call. An accepted Boolean is not readiness.
8. Stop on state reset, unresolved/wrong world, timeout, or partial evidence.

No installed documentation inspected here establishes that `SetOpenedResource`
or `OpenResource` is safe in the async script thread. The experiment tests that
bounded hypothesis. It does not bypass a native modal loop, add CPU parallelism,
or prove general thread safety.

A failed native-open experiment does not invalidate a separately successful
harmless dispatch result. It also cannot advance component or tablet runtime
acceptance.

## 7. Queue alternative and its prerequisites

`GetGame().GetCallqueue().CallLater(...)` is a different proposed route. Its
first prerequisite is another harmless queued sentinel proving the queue is
non-null and actually pumped before a world exists. The installed example
shows `ScriptCallQueue.Tick` being called during `OnUpdate`; creating a queue
does not make it self-pumping.

Do not manually `Tick` a private queue from inside the NetApiHandler and call
that asynchronous editor dispatch: the native work would still execute inside
the request. Do not assume an empty WorldEditor receives game-frame updates.
Do not retain the request handler as a bound callback without a verified
retention/lifetime contract. This route is considered only as a separately
identified experiment if the ScriptModule route is unavailable or rejected.

## 8. Optional passive native-window diagnosis

If a fresh, source-valid native-open attempt blocks, the engine owner may add
a passive window inventory at startup, immediately before the operation, and
before timeout cleanup. This is optional diagnostic evidence, not a success
gate or permission to interact with a dialog.

Use `EnumWindows`, filter by `GetWindowThreadProcessId` to the verified owned
PID, then record bounded window class/caption, visibility, enabled state, and
owner relationship. Check PID/start-time/executable identity before and after
the inventory. Do not collect unrelated application titles. Cap the collected
owned-window set and string lengths; expose truncation/incomplete enumeration.

`EnumWindows` covers top-level desktop windows; it does not enumerate ordinary
child windows. Prefer its bounded callback to walking an unbounded `GetWindow`
chain. [Microsoft EnumWindows documentation](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-enumwindows).

`GetWindowTextW` can read another process's caption without waiting for that
process, but it cannot read arbitrary controls in another application. Empty
captions are inconclusive. Do not add `SendMessage(WM_GETTEXT)` as an unbounded
fallback. [Microsoft GetWindowTextW documentation](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-getwindowtextw).

An enabled owned pop-up with a disabled owner can support a modal-dialog
hypothesis. `IsWindowEnabled` specifically measures keyboard/mouse enablement;
it is not a test of VM or RPC health. Custom editor windows can behave
differently. Retain observations and avoid a definitive modal classification
from one heuristic. [Microsoft IsWindowEnabled documentation](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-iswindowenabled),
[Microsoft discussion of modal-window identification](https://devblogs.microsoft.com/oldnewthing/20111212-00/?p=8923%2F).

No clicks, focus changes, dismissal, `PostMessage`, world saves, or unrelated
process stops are part of this inventory. Window handles are transient debug
observations, not portable module/world identities.

## 9. Ownership, evidence, and next implementation packet

Reuse the existing Workbench bridge and explicit configured PowerShell host.
Keep the `Local\BerylOwnedWorkbenchSessionV1` ownership mutex, existing-session
refusal, exact PID/start/executable checks, immutable inputs, raw RPC replies,
and raw log retention. Do not create another listening service or enable NetAPI
implicitly. Do not change execution policy or add guessed startup flags.

The initial fixture receipt must retain:

- Proposed-source bytes, exact discovered script paths, generated/staged file
  and directory sets, addon identity/dependencies, and source hashes.
- Compiler/tool/plugin/engine/host identities and separate preparation,
  compilation, runtime, and semantic outcomes.
- Every raw RPC response and its independently derived normalized fields.
- Both health-marker observations, each `ScriptModule.Call` Boolean result,
  each synchronous scalar output, sentinel events, expected/completed case IDs,
  and raw logs on success and failure.
- Monotonic stage/total deadline checks and cancellation status.
- Owned cleanup outcome. The existing callback adapter checks
  `WaitForExit(5000)`; unconfirmed exit is not `owned_process_stopped` and cannot
  remain nominal success.

There is no verified individual-thread cancellation API in the inspected
surface. A cancelled/timed-out fixture must not publish late completion as
success; use the existing bounded stop of the identity-checked owned process.
No stronger stop or unrelated process action is implied.

The next implementation packet should add only the trusted sentinel sources,
a strict bounded preparer/receipt validator, and the required isolated
transport adaptation. Compile/function-discovery evidence comes first; actual
owned runtime evidence follows. Any native world-open extension is a later
packet with its own source freeze, expected cases, and receipt.

This document closes a passive diagnosis task. It leaves actual dispatch,
resource opening, world readiness, prefab spawning, engine-delivered callbacks,
tablet services, and multiplayer acceptance explicitly unverified.

## 10. Subsequent bounded dispatch evidence

The primary direct-thread sentinel is now implemented separately in
`packages/sparkos/workbench-dispatch-probe`, with its preparer and transport in
`scripts/verify-workbench-dispatch.py` and `scripts/workbench-dispatch-engine.ps1`.
It does not implement the Workbench-only/reflected alternatives above.

Synthetic receipts passed 46 cases at
`build/dispatch-receipt-tests-q5jsndd8/result.json`. Default preparation passed
at `build/workbench dispatch & spaces-cf5vo4n5/result.json`; those receipts did
not execute the engine. Actual root-owned execution then passed at
`build/workbench dispatch & spaces-csb3u27_/result.json`, SHA-256
`f1e0c1251497ba4c06ccdba0bd8a0cd85fd4d26b6825d1c0e1b935d1cdc06880`.

Compilation was clean. The exact six installed cases completed across two
native RPC responses. The first snapshot recorded worker entry with zero
resumptions. The next recorded one resumption and completion. Source stamps
were arm=1, worker entered=2, caller submitted/after-thread=3, worker resumed=4.
The worker therefore entered before the caller's continuation and resumed after
submission. Seven recorded session checks identified the same owned process;
exit was confirmed and all retained input/log/receipt hashes passed passive
review. This does not measure network-send order or a native API's asynchronous
behavior. Raw log warnings outside the fixture's compile case are preserved.

The callback fixture now proposes a separately frozen extension: a single
global worker yields for 200 ms, reacquires native module/API references, checks
exact resource/world/mode identity, and calls SetOpenedResource once. Requested,
submitted, entered, resumed, returned and accepted observations are separate.
Readiness cannot pass before returned and accepted; lost state cannot resubmit.
No editor API reference survives the yield. A blocked native call remains a
timeout, and confirmed owned process exit is the cancellation boundary.
That extension is not established by the harmless sentinel receipt.
