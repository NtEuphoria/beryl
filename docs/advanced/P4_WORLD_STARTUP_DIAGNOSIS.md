# P4: isolated Workbench startup-world diagnosis

Date: 2026-10-10. Scope: the historical single-file startup diagnostics.
Headless compilation passed, but their startup listener and native-opening
readiness gates remained incomplete. No released component contract is claimed.

The later [source-layered investigation](P4_LAYERED_WORLD_DIAGNOSIS.md) records
the installed two-file authoring template and a successful isolated CLI loading
control. The
historical trials below used the earlier single-file fixture. Their receipts
remain evidence for those captured inputs only.

This packet prepares one small alternative to the blocked native world-opening
path. The installed CLI documentation explicitly describes loading a resource
when a Workbench module starts. Loading the same immutable fixture at startup
would separate that operation from the GameCommon RPC stack and its deferred
worker. The first actual startup route did not establish readiness.

The initial review authored only this document. In that review, no compiler, Workbench,
game, PowerShell host or native program was launched; no process was stopped;
no live project, installed plugin, existing fixture or historical receipt was
modified. The integration owner's later execution is recorded separately below.

## 0. Actual October 10 continuation

The original deferred opener was engine-compiled and executed at
`build/component callbacks & spaces-asb7eaon/results.json`. The worker resumed
and reached `SetOpenedResource`; the owned world load appears in the log, but
no return marker followed and the next RPC timed out. Owned cleanup was confirmed.

The standalone startup observer initially failed compilation because its local
variable was named `owned`, an EnforceScript keyword. Renaming that local resolves
the error. The corrected candidate is
`build/workbench startup & spaces-6lzpapeq/results.json`: headless compile succeeds,
the startup CLI logs owned-world loading in 72.2998 ms, and 42 listener queries
find no listener on port 5775 before the 30-second startup deadline expires.
No health or observer RPC ran; cleanup was confirmed. Loading messages are not
readiness evidence. The cause of the absent listener remains unestablished.

The experimental source runner and adapter are
`scripts/verify-workbench-startup.py` and `scripts/workbench-startup-engine.ps1`.
The read-only handler is under `packages/sparkos/workbench-startup-probe/`.
Exact source and receipt fault gates precede actual runs. The six predeclared
readiness IDs describe harness obligations checked from native observations;
they are not component callback cases.

The native NetAPI `OpenResource` profile was executed separately at
`build/workbench startup & spaces-mg5x7fk8/results.json`. Its 128 pure PowerShell
checks and 122 inert evidence cases passed before the run. Headless compile,
owned listener, health, loaded-addon identity and native resource roundtrip passed.
The exact absolute `ResourceName` request returned `Opened=true` in 162 ms.
However, all 64 subsequent read-only observers remained pending: module present,
API absent, no observed world path or world. The retained runtime logs contain
no `LoadWorld` entry. The adapter failed on the poll bound with confirmed owned
cleanup; NetAPI returned all 68 RPC replies successfully. These observations do
not establish module activation or a loaded world.

The exact built-in result remains separate from script `Workbench.OpenResource`
and `SetOpenedResource`. No fallback, deadline increase, play transition, world
save or manually delivered callback ran. The next isolated investigation selects
`module-netapi-resource`: the established daemon arguments plus
`-wbmodule=WorldEditor -run`, omitting `-load`, then the same single native
opening request. The installed CLI documents module startup and resource loading
separately. This six-argument profile tests activation independently; it does
not presume listener, API or world readiness. Earlier profiles remain available
as separate choices, with unchanged guards and budgets.

The actual third attempt is
`build/workbench startup & spaces-c3kcvxx_/results.json`. Its cleanly compiled
observer found the WorldEditor API, edit mode and a world before the native
opening request. The absolute request returned `Opened=true` in 46 ms; all 64
following observers still found API/edit/world but no world path. All 68 RPC
replies arrived and owned cleanup was confirmed. The poll-bound failure therefore
does not reproduce a host or RPC stall. Module startup established API availability
in this configuration, but did not establish fixture loading.

The final bounded spelling experiment selects `module-netapi-registered`: the
same six arguments, then one native request using the exact registered GUID name
instead of an absolute pathname. Preliminary native identity and absolute
roundtrip remain required. The installed NetAPI declaration specifies a string
`ResourceName`; it does not guarantee admission or readiness for this spelling.

The fourth attempt is
`build/workbench startup & spaces-z95lbuxg/results.json`. Clean compilation and
the preliminary native identity checks passed. Its one exact registered request
returned `Opened=true` in 37 ms, but all 64 readiness observations retained an
empty world path despite API/edit/world presence. All 68 RPC replies arrived;
no `LoadWorld` entry appears in the retained runtime logs. The adapter failed on
its poll bound after 37.809 seconds with confirmed owned cleanup and no evidence
errors. Changing resource spelling alone did not establish readiness.

No opener profile is released by these runs. Module activation is established
only for the tested six-argument startup configurations. Next investigate a
known-valid engine-authored fixture and the actual module loading contract,
keeping serialization, resource opening, named-world readiness and callbacks as
separate evidence levels. The current handcrafted `GenericWorldEntity` bytes
remain unverified as a suitable runtime world.

### Executed follow-up: engine-authored fixture eligibility

The [eligibility packet](P4_WORLD_SAVE_ELIGIBILITY.md) records the now-executed
read-only probe. It compiled cleanly and observed an empty Workbench edit world,
but `Game.GetWorldEditor()` returned null. Its completed result is unavailable;
no serializer, save, fixture reload, play or callback ran. The design below
retains the original prerequisite contract; a working save is not implied.
The installed API declares `Game.GetWorldEditor()` and
`GameWorldEditor.GetEditorAPI()`. The Game documentation limits its editor lookup
to non-play mode. Neither declaration proves that the handle is nonnull in the
current Workbench configuration, or that it represents the same API/world as
`Workbench.GetModule(WorldEditor).GetApi()`.

The declared serializer is
`GameWorldEditor.SaveWorldAs(string savePath, bool overridePath=false) -> bool`.
Its documentation limits the path to 256 characters. Its prose names the
overwrite flag `overrideWorld`, differing from the declared `overridePath`.
Do not infer an overwrite/lifetime contract beyond the tested behavior.

A separate job should first observe the native editor handles and exact world
identity in the fresh empty edit-mode session. If they are absent, mismatched,
in play mode, or expose a named/foreign world, report unavailable. Only an admitted
same-world configuration may attempt one save to a new, short, compiler-owned
output path, with the overwrite argument false. Confirm that output is absent,
its parents are owned and unlinked, and the original eight/nine frozen inputs
remain unchanged. No alternate serializer, overwrite or `BaseWorld.CreateWorld`
fallback is implied.

Retain the actual return, post-save native world path, produced bytes/metadata
and dependency inventory. A true return alone does not establish a valid fixture.
Use a separate fresh process to load the captured result and prove exact named
world readiness before returning to the seven callback cases. This preserves
the distinction between serialization, load admission, runtime readiness and
actual callback delivery.

The passive signature research and exact primary-file hashes are retained in
[the serializer research packet](../../build/world-save-primary-20261010/source-research.md).
The declarations come from installed
[interfaceGame.html](<C:/Program Files (x86)/Steam/steamapps/common/Arma Reforger Tools/Workbench/docs/EnfusionScriptAPI/html/interfaceGame.html:649>)
and
[interfaceGameWorldEditor.html](<C:/Program Files (x86)/Steam/steamapps/common/Arma Reforger Tools/Workbench/docs/EnfusionScriptAPI/html/interfaceGameWorldEditor.html:189>).
No serializer probe, save, new fixture or reload was executed during that research.

Read [the host recovery packet](P6_HOST_RECOVERY_2026_10_10.md) for all current
harness fixes and exact passing/failing scopes. The following sections preserve
the initial documented rationale; proposed operations remain unverified until
their own actual receipts pass.

## 1. Exact reviewed inputs

The primary pages below were read and hashed from the installed Tools docs at
`C:/Program Files (x86)/Steam/steamapps/common/Arma Reforger Tools/Workbench/docs/EnfusionScriptAPI/html/`.
Line numbers refer to those exact HTML bytes. These documents identify API and
CLI declarations; they do not certify this engine's loading or lifetime behavior.

| Installed primary page | SHA-256 | Relevant source locations |
|---|---|---|
| [Page_CLI.html](<C:/Program Files (x86)/Steam/steamapps/common/Arma Reforger Tools/Workbench/docs/EnfusionScriptAPI/html/Page_CLI.html:387>) | `b1fd25c1d02e3ac687bb310496f700acaf451f66d26c572afa9ac5fd343822d1` | 121: project path; 129: Workbench ignores generic `-world`; 379: silent initialization exits; 387: module selection; 411–413: module startup and resource loading; 429: loaded-world example; 575: LocalizationEditor resource-name example |
| [Page_NetApi.html](<C:/Program Files (x86)/Steam/steamapps/common/Arma Reforger Tools/Workbench/docs/EnfusionScriptAPI/html/Page_NetApi.html:145>) | `e39e4a346fe6ed70358f2be6745424f543c21b225a2ac9d7967c403d256cd51c` | 145–154: built-in `OpenResource`; 181–189: `IsWorldEditorRunning` |
| [interfaceWorkbench.html](<C:/Program Files (x86)/Steam/steamapps/common/Arma Reforger Tools/Workbench/docs/EnfusionScriptAPI/html/interfaceWorkbench.html:133>) | `6da66bb00dd8cadb84463605e7272d93a01e179c8bd651dbdc614d3a68bbdf0f` | 111–112: module lookup/opening; 133: native absolute resolution; 142–145: resource naming, script opening and module handles |
| [interfaceWorldEditor.html](<C:/Program Files (x86)/Steam/steamapps/common/Arma Reforger Tools/Workbench/docs/EnfusionScriptAPI/html/interfaceWorldEditor.html:122>) | `51af7415047780b9efa7302dfa3b4573dd89d78c4d90b46968273f010f16f275` | 122–125: API and mode requests; 131: inherited resource opener; 150–158: API declaration without completion documentation |
| [interfaceWorldEditorAPI.html](<C:/Program Files (x86)/Steam/steamapps/common/Arma Reforger Tools/Workbench/docs/EnfusionScriptAPI/html/interfaceWorldEditorAPI.html:185>) | `202fbc3822d1c8d9cd465ad4968a9541e90353b51cf4329046187ef8cba1d7b2` | 185–186: edit/game observations; 210: world; 225 and 1444–1452: world path; 1516–1524: edit-mode declaration |
| [interfaceWBModuleDef.html](<C:/Program Files (x86)/Steam/steamapps/common/Arma Reforger Tools/Workbench/docs/EnfusionScriptAPI/html/interfaceWBModuleDef.html:132>) | `ca3377a5fa8aea08913f782ed770fe9421e8adfe6abb40d40c594d6aa13d550d` | 132, 278–286: `SetOpenedResource(string filename) -> bool`; no documented asynchronous guarantee |
| [interfaceScriptModule.html](<C:/Program Files (x86)/Steam/steamapps/common/Arma Reforger Tools/Workbench/docs/EnfusionScriptAPI/html/interfaceScriptModule.html:223>) | `37db95134ae2c214c23169a268e3504aed864c169f99551ec26ed75934ed0210` | `Call(..., bool async, ...)`: thread dispatch and synchronous return-value distinctions; no Game reload lifetime contract |
| [Page_Enforce_Syntax.html](<C:/Program Files (x86)/Steam/steamapps/common/Arma Reforger Tools/Workbench/docs/EnfusionScriptAPI/html/Page_Enforce_Syntax.html:821>) | `df83332c65707ce3e9a751c76fe323f1e5fee5459814ba7b5ee850fb325a572d` | 821–833: cooperative `thread` and `Sleep` behavior |

The source review was made against these current fixture/tool bytes:

| Source | SHA-256 |
|---|---|
| `packages/sparkos/component-callback-probe/rpc.c.in` | `ce6324bdbab75aebfaf6f832e76c59fd9dbd1617506a5c9c96c6bbc83caa8099` |
| `scripts/component-callback-engine.ps1` | `14e1b721e5efc191c9e97fb2c73432a7d74526acf63365fc6200b58da7a6fc25` |
| `scripts/verify-component-callbacks.py` | `934eb90eaba91d5649fa4863eff626dd2f4a4cedac6f042df28513f5bf3d9595` |
| `packages/sparkos/component-callback-probe/source-contracts.json` | `1ae2f281e8e99c3c40ed7620768feeaa392c183215a93e48fcb17dba7cdf72d9` |
| `packages/sparkos/component-callback-probe/worlds/BerylCallbackProbe.ent` | `817cdce027c83f67e04bffd886f04672a1a48b163386e489766c9e2d2b8fdee4` |
| `packages/sparkos/component-callback-probe/worlds/BerylCallbackProbe.ent.meta` | `de1a5d7ee9afdd841773c6d00cea2a0e7352cba39550cfb63b05a90872d51550` |
| External `reforger-workbench-plugin/scripts/Start-WorkbenchDaemon.ps1` | `25f481f771109f0d3007b507e947d46aae20ca935ec99a1ff03721d334196c70` |
| External `reforger-workbench-plugin/scripts/Invoke-Workbench.ps1` | `69169459a9e93b523e5bf68340e370ae892700bc2a6bf737897bb4b962d56f9a` |

These are review identities, not assertions that current source has passed an
engine run. A changed file requires a new source capture and applicable checks.

## 2. What the installed documentation establishes

The Workbench CLI has this documented shape:

```text
-wbmodule=WorldEditor -run -load "world/myworld.ent"
```

The module selector is documented with `-wbModule=MODULE_NAME`; its examples
use `-wbmodule`. The documentation says to include `-run` after each module
selection to launch it. `-load FILE_PATH` loads a resource into that selected
module at startup. The WorldEditor/GenerateFlowMaps example also uses
`-wbmodule=WorldEditor -run -load "worlds/Eden/Eden.ent"`.

The WorldEditor examples supply relative resource paths. They do not establish
that those paths are relative to the operating-system working directory. A separate
LocalizationEditor example at line 575 supplies a GUID resource name after
`-load`; this establishes that example's spelling, not WorldEditor acceptance
of every GUID/absolute spelling. The examples do not specify every
accepted absolute, addon-prefixed or GUID spelling, guarantee that NetAPI is
responsive during startup loading, or establish the minimum contents of a
standalone world. The current `GenericWorldEntity {}` fixture remains an
experimental serialized world, even though the class itself is documented.

The generic game `-world WORLD_FILE` is explicitly described as ignored by
Workbench. It cannot replace Workbench's documented `-load` route. The optional
plugin examples are not evidence that a custom WorkbenchPlugin `Run()` executes
on this installation: the installed integration's own NetAPI guidance records
earlier unsuccessful `-plugin`/`-wbrun` trials for that separate purpose.
The `-gproj` declaration specifies a full project path, allowing a working-
directory-relative path only with a `./` prefix. Preserve the owned absolute
project path. `-wbSilent` is documented as initializing and exiting; it is a
different compile/initialization mode and must not be inherited accidentally by
a persistent startup-world diagnostic.

The built-in NetAPI has a distinct documented operation:

```json
{"APIFunc":"OpenResource","ResourceName":"string"}
```

Its documented result contains `Opened` as a Boolean. The parameter is exactly
`ResourceName`, not `path`, `filename` or `resourcePath`. This built-in APIFunc is
different from the script declaration `Workbench.OpenResource(string filename)`
and from a custom GameCommon `NetApiHandler`. The built-in's availability,
accepted filename spelling and readiness semantics have not been established
by the current callback fixture. `Opened` alone cannot prove the exact world is
ready to play.

Likewise, `IsWorldEditorRunning` is documented with `IsRunning` and
`ScriptsCompiled`. Those fields can establish a bounded module/compile
observation; they do not identify the loaded world, its mode or its readiness.

## 3. Historical observation that motivates the diagnostic

The retained [7gd results](<C:/Users/moham/Desktop/beryl/build/component callbacks & spaces-7gdcd8fr/results.json>)
have SHA-256 `63d771816f09e53a57bac91d8472db024ffbfa565c5e21f2b7ad920ce43bcb40`.
Its [raw runtime envelope](<C:/Users/moham/Desktop/beryl/build/component callbacks & spaces-7gdcd8fr/engine-runtime.json>)
has SHA-256 `67c189c57d02befc713ebf46d51d6b10f840129ef45763d99aacc0c3061c6d86`.

The recorded engine is Tools `1.8.0.13`, executable SHA-256
`7dd36ca1f662b0c13669a4f2f7f10e3c461c2906b021e742272d64b3ab7e9798`.
That is the retained attempt's identity. The next launcher must independently
check the configured current executable instead of assuming it is unchanged.

The actual sequence was:

1. Source generation and engine script compilation succeeded.
2. The first `load` RPC returned `pending`. The addon world resolved natively to
   the exact owned file. Its registered resource was
   `{BCCBA11B20261008}worlds/BerylCallbackProbe.ent`, with an exact native
   filesystem roundtrip. WorldEditor and its API were present; opening the
   module had been requested and accepted.
3. That snapshot had `edit_mode=false`, `game_mode=false`,
   `in_play_mode=false`, `world_present=false` and an empty raw world path.
4. The first `status` RPC then received no response inside its existing
   eight-second deadline. There was no spawn attempt or callback observation.
5. Retained logs record Workbench Reload Game, followed by loading the exact
   owned world. They report Entities load 9.2934 ms, CreateEntities 44.4227 ms
   and WorldEditor LoadWorld 56.9505 ms. No selected log contains a world-load
   error or VM exception for that attempt.
6. The outcome remained timeout. The owned process exit was confirmed and the
   envelope's evidence-error list was empty.

The short native profiling phase is not a returned API value or a readiness
response. Absence of a logged exception does not diagnose a modal, deadlock,
reload invalidation, incomplete world or UI routing problem. The external
helper's generic timeout text suggesting a modal is not a measured window
observation. Earlier inherited-terrain timing and the explicitly rejected
empty-SubScene fixture cannot determine this attempt's cause.

## 4. Current deferred path: preserved boundaries and an open prerequisite

The current `rpc.c.in` submits one cooperative worker, yields for 200 ms, and
acquires editor/API references only after the yield. Before the one native
`SetOpenedResource` call, it checks the baked token, exact native addon-world
resolution, exact resource registration/roundtrip, current mode and any observed
world path. A wrong or unresolved existing world is rejected. Native API
references are not retained across `Sleep`.

Its source distinguishes requested, submitted, entered, resumed and returned
states. A request that does not return remains pending; acceptance is recorded
only after the native Boolean return. State reset is an error, not an invitation
to resubmit. Play, spawn, deletion and normal edit-mode stop are gated behind
the worker's returned-and-accepted result. The outer owned-session cleanup is
the cancellation boundary while that worker is incomplete.

The current PowerShell adapter now checks these progress counters and their
order, rejects reset counters, and requires actual accepted native loading
before a ready/complete response. Those checks must remain applicable to the
deferred experiment. The startup experiment must not fill those counters with
fabricated ones simply to reuse that response contract.

One current prerequisite is not established by the primary docs: the worker
requires `WorldEditorAPI.IsEditMode()==true` before it opens the world. The 7gd
pre-world snapshot reported false. The docs declare the observation but give
no rule that a newly opened, empty editor must already report edit mode.
The API might change by the time a deferred worker resumes; that is unmeasured.
Therefore this is an eligibility uncertainty, not a proven compiler defect or
permission to weaken the guard. If it fails, retain the exact observed modes
and classify that rejection explicitly.

## 5. Recommended smallest orthogonal experiment

Create one new immutable startup-world diagnostic, retaining the same selected
world bytes, resource IDs, generated component and observer sources. Select
`startup_cli` as the actual opening mechanism before launch. Do not run the
deferred native opener in the same job or fall back to another opener.

The provisional startup arguments are the existing explicit project startup
arguments plus the documented module sequence:

```text
-gproj <owned addon.gproj>
-noOpenLastResource
-scriptAuthorizeAll
-wbmodule=WorldEditor
-run
-load worlds/BerylCallbackProbe.ent
```

Use the relative resource path shown above for this single planned experiment,
because it follows the primary examples. Its interpretation in the loaded
addon is an experimental input, not an assumption. After startup, native addon
and observed-world resolution must both identify the pinned owned absolute
file; resolving to a same-named base resource fails the experiment. A later
absolute/GUID spelling trial would be a different predeclared experiment and
receipt, never an automatic fallback.

The interaction between `-noOpenLastResource` and an explicit `-load` also
requires an actual observation. Preserve the current flag for the initial
experiment to avoid changing ambient last-resource behavior. Do not replace it
with settings reset, forced save, or undocumented flags.

### 5.1 Trusted launch seam

The existing external `Start-WorkbenchDaemon.ps1` accepts project, port,
timeout, Force and output-format parameters. Its current launch arguments are
fixed to `-gproj`, `-noOpenLastResource` and `-scriptAuthorizeAll`; it has no
reviewed additional-arguments parameter. Passing an unsupported parameter or
editing the installed plugin in place is not an implementation of this packet.
The installed `Invoke-Workbench.ps1` accepts `string[] Arguments`, quotes/joins
them and launches with the game-root working directory, but then waits for the
process to exit. Its reviewed source is a bounded terminating-job wrapper, not
an established persistent daemon seam. It cannot substitute for the daemon
solely because it accepts arbitrary arguments.

The integration owner must provide an explicitly reviewed local startup-profile
seam through the existing owned launcher. Record the exact argument vector and
its Windows encoding; keep the configured executable, working directory,
hidden-window behavior, mutex and process ownership checks. No project-provided
shell command or arbitrary startup argument string becomes admissible.

Before an engine attempt, unit/fixture checks must establish that the new seam
preserves ownership on startup failure, launch timeout and cleanup failure.
Changing how the executable is launched must not discard a known owned PID or
turn a failed stop into an empty-error success.

### 5.2 Observation-only startup readiness

Use a separately versioned, trusted read-only diagnostic handler. It must not
call `OpenModule`, `SetOpenedResource`, script `OpenResource`, the built-in
opener, or the deferred worker. Its setup action reports observations only.
This avoids requesting a second world load after the CLI has already done so.

After the existing port/startup checks, obtain these independent observations
within the unchanged deadlines:

1. Exact owned process PID, start identity and executable; expected engine
   hash/version; the exact candidate addon in `GetLoadedProjects`.
2. Native resolution of
   `$BerylComponentCallbackProbe:worlds/BerylCallbackProbe.ent` to the pinned
   absolute path, with `mustExist=true`.
3. Native registration of that absolute path as
   `{BCCBA11B20261008}worlds/BerylCallbackProbe.ent`, and resolution of its native
   resource path back to the same file.
4. Fresh `WorldEditor` and `WorldEditorAPI` observations, acquired per request.
   Preserve raw `GetWorldPath` and its native absolute-resolution result.
5. Exact observed world equality, non-null native world, edit mode true, game
   mode false and `GetGame().InPlayMode()` false.
6. A fixture token and ordinary registry observation after startup that identify
   the compiled candidate and show no premature spawn, stale case receipt or
   retained callback events.

An empty path, absent API or a non-ready permitted mode is pending within the
existing deadline. A known foreign world, failed exact resource identity,
unexpected active play, changed source or wrong token is a rejection. The
current base `current_project` observation is retained informationally; it must
not again be compared to the addon project when native addon identity is the
actual contract.

Startup readiness requires a real response from the current owned session.
A log line, an open port, `ScriptsCompiled=true`, a worker entry marker or a
previous receipt cannot stand in for it. If reload resets any required state,
classify it as stale/incomplete and do not arm it again in that job.

### 5.3 Scope after readiness

The initial startup diagnostic can finish without entering play or spawning.
That is the smallest useful answer: whether this exact world can become
observable and ready through documented startup loading while NetAPI remains
responsive. It does not prove callback delivery or tablet services.

If this prerequisite passes, a separately admitted callback continuation may
use the existing play, spawn, frame, delete and edit-mode observation rules.
Its setup contract must explicitly identify `startup_cli`; the recorded CLI
request plus exact ready-world response supply its opening evidence. It cannot
pretend that the deferred worker returned. Both opening profiles retain the
same strict resource, mode, authority, trace and cleanup requirements.

The existing seven callback cases stay unchanged:

```text
runtime.post-init.1
runtime.post-init.2
runtime.frames.1
runtime.frames.2
runtime.independent-state
runtime.delete.1
runtime.delete.2
```

No direct callback invocation, detached component, scripted reply, manually
seeded event or changed entity authority can satisfy them. Spawn must precede
each actual callback observation; authority is checked at its existing points;
ordered rows, count/checksum and the exact final case set remain required.

## 6. Fixed limits and proposed tests

Keep the current pilot defaults: at most 8 seconds per RPC, 30 seconds per
stage, 64 polls, 200 ms between polls, 180 seconds overall and the existing
outer owned-process bound. A remaining stage/overall budget shortens an RPC;
it never extends it. Existing monotonic late-result and cleanup/evidence
checks remain in force. Cleanup waits at most the existing 5 seconds for
confirmed owned exit and does not stop an unrelated session or apply a stronger
termination strategy.

The following are proposed test obligations, not tests executed by this review.
Freeze their complete IDs before the first source-only validator attempt:

| Planned case | Required check |
|---|---|
| `startup.arguments.exact` | Exact explicit module/run/load sequence, exactly one `-load`, no deferred opening or arbitrary arguments; preserve ordinary default launch profile |
| `startup.arguments.encoding` | Paths containing spaces and metacharacters remain exact single process arguments; no shell evaluation or truncated project path |
| `startup.identity.pinned` | Wrong engine, tool, addon, token, registered resource or absolute world path fails with a precise outcome |
| `startup.readiness.pending` | Missing module/API/world, empty world path and permitted non-ready mode remain pending; no success inferred from logs or an open port |
| `startup.readiness.foreign` | Foreign/unresolved nonempty world, existing play or stale/reloaded token is rejected; no second request or implicit fallback |
| `startup.receipt.strict` | Required fields/types, Boolean-or-exact-0/1 codec, immutable raw RPC, separately derived normalized response, exact selected mechanism and bounded counters |
| `startup.ownership.cleanup` | Startup/timeout/cancellation retain owned process identity; failed/unconfirmed cleanup is visible and cannot leave a nominal success |
| `startup.scope.callback` | Readiness-only completion has callback execution not run and no seven-case claim; complete callback results still require the real unchanged trace/case checks |

For a runtime diagnostic, predeclare a separate case set and interpretation
before timing. Do not manufacture a complete startup test receipt out of the
number of observed responses. Semantic return, native request refusal,
unavailable capability, timeout, cancellation, stale source and harness failure
remain distinct statuses. An incomplete case set is not verification success.

Preserve raw failed receipts as historical failures. A corrected validator,
launcher or handler receives a fresh source identity and receipt. This packet
does not request retries of denied artifacts, changes to security settings,
longer deadlines, saves or edits in the user project.

## 7. Alternative single diagnostic: built-in OpenResource

If selected instead of startup loading, use one fresh owned session and the
documented built-in APIFunc through the existing `Invoke-WorkbenchRpc` transport.
Pass the exact already-verified registered resource name in `ResourceName` and
record the built-in's raw result separately. Do not rename its `Opened` field
or turn it into the script opener's return value.

Predeclare this as `netapi_builtin_open_resource`. The builtin's request can be
sent only after exact addon-world/resource roundtrip checks. A successful
`Opened` must be followed by the same read-only exact-world and edit-mode
readiness observations. A refusal, unavailable function, unexpected response
shape or timeout ends that experiment without trying script opening or CLI
opening afterward.

This route has a primary-supported request shape, but is not listed among the
installed integration's actually verified OpenResource operations. Its behavior
on this engine remains a hypothesis. It is a possible follow-up, not an adopted
replacement or an automatic recovery step in the startup diagnostic.

## 8. Decision and next dependency

The first recommended experiment is a reviewed owned startup profile with one
documented relative `-load` argument and observation-only readiness. It changes
the location of the native load while preserving its world bytes and exact
post-load admission. This is more informative than another unclassified
variation of a native call inside a live GameCommon handler.

If startup reaches exact readiness, investigate play and callback delivery with
the unchanged runtime cases. If it returns a precise native refusal, record the
route as unavailable for this input. If it again loads quickly in logs but
never exposes readiness, retain that distinction; possible world completeness,
native routing/window state and reload behavior remain hypotheses requiring
their own bounded observations.

A failed mode precondition in the deferred route would answer a narrower
question and should be reported directly. It does not establish why synchronous
7gd timed out, nor justify accepting an arbitrary world or bypassing authority.
No result from this packet closes the tablet UI, queued-service lifetime,
resource closure, dedicated multiplayer, visual or full-feature release gates.
