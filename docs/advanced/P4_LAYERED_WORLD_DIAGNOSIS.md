# P4: source-layered world diagnosis

Checkpoint: 2026-10-10. This packet records source preparation and narrowly scoped native observations. The explicit layered `startup-cli` trial `qd5tufrg` passed exact named edit-world readiness. Callback trials `merbrapz`, `a7u0gcvh`, and `bbe8mikw` reached load/play and native post-init, but did not complete frame delivery. The two read-only `bbe8mikw` snapshots establish that the fixture owners belonged to the stationary editor world while a distinct game world advanced. The minimal fresh-game-world spawn correction then passed all seven bounded callback cases in `idjip0_z`, including real frames, independent scalar state, and both native deletion callbacks. Full world lifetime, tablet services, gameplay deployment, and multiplayer remain unverified.

## 1. The gate and its evidence boundaries

The callback experiment needs an owned, identified world that the native World Editor actually reports as loaded. A file existing, a GUID resolving, an editor API existing, an unnamed edit world existing, and an `OpenResource` request returning true are separate observations. None individually proves that the selected world was loaded.

The source-layered candidate has two fixed text files. Its content comes from an installed world-authoring helper. This establishes the provenance of the authored text; it does not establish successful native loading, engine-authored serialization, gameplay configuration, or callback delivery.

The installed helper was inspected and retained. It was **not invoked**. No native save operation produced these templates.

## 2. Installed primary source

The retained source is [SCR_WorldFilesHelper.c](../../build/world-authoring-source-research-20261010-b274dc91/selected/SCR_WorldFilesHelper.c), extracted by a bounded read of one selected installed archive entry:

| Identity | Recorded value |
|---|---|
| Installed resource path | `scripts/WorkbenchGame/WorldEditor/Helpers/SCR_WorldFilesHelper.c` |
| Source module and compilation guard | `WorkbenchGame`; `#ifdef WORKBENCH` |
| Archive | `C:/Program Files (x86)/Steam/steamapps/common/Arma Reforger/addons/data/data007.pak` |
| Selected packed entry | Offset `1493110121`; `2909` bytes |
| Packed SHA256 | `67063d478bfd438eec97ed3ab18d2b7eddaef17751a8bb6eac5065395b327a6c` |
| Decoded source | `13536` bytes |
| Decoded SHA256 | `528602403fa19c909d450394bab04ad582b20cd89de0c1962b394249d269071c` |
| Selected-entry receipt | [selected-entry-observations.json](../../build/world-authoring-source-research-20261010-b274dc91/selected-entry-observations.json) |

The entire approximately 2 GB archive was not hashed. The provenance claim covers the selected metadata and packed entry, the retained decoded bytes, and the recorded archive size/mtime. It is not a general archive-format or whole-archive verification claim.

The exact source signature at line 22 is:

```c
static string CreateWorld(string relativeWorldDirectory, string worldName,
    array<ResourceName> defaultLayerEntities = null,
    bool overwriteWorldFile = false, bool overwriteDefaultLayerFile = false)
```

The corresponding installed declaration is `ArmaReforgerScriptAPIPublic/html/interfaceSCR__WorldFilesHelper.html`, SHA256 `d1e6e5c9c62b7392e584309909895480d2b61e1a043718a8a93f89c0952f6516`. Its signature is at line 112, addon-prefixed directory description at line 180, and returned-path description at line 188.

Relevant implementation observations:

- Lines 43–45 construct `<worldName>.ent`, `<worldName>_Layers`, and `default.layer` paths.
- Lines 70–72 write the three lines of the `.ent` below.
- Lines 106–107 write the two default-layer lines when no world-entity prefab is supplied.
- Line 134 returns the addon-prefixed relative world path.

The comment says the helper registers the world, but the `CreateWorld` body does not call `RegisterResourceFile`. Calls elsewhere in the file belong to other operations. A returned path would therefore not, by itself, establish native registration. Cross-module invocation of this helper was not tested.

The full bounded extraction scope, failed passive decoder assumptions, and retained primary evidence remain in [RESEARCH.md](../../build/world-authoring-source-research-20261010-b274dc91/RESEARCH.md).

## 3. Exact selected source files

The source-controlled package is [workbench-layered-world](../../packages/sparkos/workbench-layered-world/README.md). Its immutable [source-contracts.json](../../packages/sparkos/workbench-layered-world/source-contracts.json) has SHA256 `461b4c338e29ef7b9105e1e39f92d66e6861b112f8a77bd45046413600d0e45e`.

`worlds/BerylCallbackProbe.ent` is exactly 27 bytes:

```text
Layer default {
 Index 0
}
```

Its bytes are `b"Layer default {\n Index 0\n}\n"`; SHA256 `f1e51134fb42a814e072493a46a67a76853723964cc6eb87a24e45e15921385d`.

`worlds/BerylCallbackProbe_Layers/default.layer` is exactly 29 bytes:

```text
GenericWorldEntity world {
}
```

Its bytes are `b"GenericWorldEntity world {\n}\n"`; SHA256 `e4584f0b154cbeea1bd4c9c9db96d5f062580f1886cbf40267392512800dcd4a`.

Both staged files use UTF-8 without a BOM, LF line endings, and a final LF. The text lines are supported by the installed source. Native `FileHandle.WriteLine` newline bytes were not measured; LF is the explicit staging choice.

The orchestrator replaces only the world text inside a new owned candidate and adds the layer. It preserves the original world metadata and `{BCCBA11B20261008}worlds/BerylCallbackProbe.ent` identity. Preserving or resolving that metadata does not prove its native resource type or import/load completeness.

## 4. Why shipped EmptyEden was not selected

Passive installed metadata identified the candidate resource name `{55A3176BBDD01AAE}worlds/Eden/EmptyEden.ent`. A bounded selected-entry decode retained its compiled binary payload at [EmptyEden.ent.decoded.bin](../../build/world-authoring-source-research-20261010-b274dc91/selected/EmptyEden.ent.decoded.bin): `9795` bytes, SHA256 `06acfc36caad0610bff9c4a275dbd663fd17e250b6799f8281858993f3437f50`.

That payload starts with `EBIN` and contains `GenericTerrainEntity`, ocean, cloud, time, and weather tokens. It was rejected as an established minimal no-terrain fixture. This is a passive selection decision, **not an engine loading failure**. Its complete dependency closure, serialization schema, and paid load cost were not established, and this research did not load it.

The smaller source-layered experiment avoids relying on the name “EmptyEden” as evidence that terrain or other systems are absent. This does not establish why any previous native operation failed to reach readiness.

## 5. Actual registered-opener trial: y5o7m0kt

The retained result is [source layered world & spaces-y5o7m0kt/results.json](<../../build/source layered world & spaces-y5o7m0kt/results.json>).

This trial used the explicit `module-netapi-registered` profile. Its six startup arguments opened World Editor without `-load`; after health, loaded-addon, and native resource proofs, it submitted exactly one built-in `OpenResource` with:

```text
ResourceName = {BCCBA11B20261008}worlds/BerylCallbackProbe.ent
```

Observed evidence:

- Exact source preparation and headless script compilation succeeded.
- The fresh candidate contained exactly ten declared files: the original eight, with only the world text replaced, plus the layer and the separately named read-only startup observer.
- The original eight files and retained original compiler artifact remained exact during an independent passive audit.
- The only admitted derived candidate output was the root `resourceDatabase.rdb`, `756` bytes, within the existing bound.
- All 68 actual RPC replies returned `Ok`.
- The native request returned `Opened: true`.
- All 65 normalized observer replies remained `pending`, with module/API/edit/world present and `world_path` empty.
- Native addon-world resolution and the registered resource roundtrip identified the exact owned candidate path.
- The adapter exhausted its bounded readiness polls and reported `timeout`; owned process cleanup was confirmed, with no evidence errors.

The three retained console/error/script logs matched their recorded SHA256 values in a passive audit. They contain no `LoadWorld` marker and no `BerylCallbackProbe.ent` filename. The console does contain an initial unnamed `CreateEntities` during Workbench startup. Consequently the evidence does not support saying that no world or entities existed at all.

Receipt scope is accurate: `source_copy` and `engine_compilation` are `executed_success`; `startup_world_readiness` remains `attempted_unconfirmed`. Callback delivery, tablet services, save, gameplay, multiplayer, visual, and performance gates are not closed.

This result does not distinguish an authored-format problem from resource routing, opener semantics, import state, or another native prerequisite. The lack of a named-world load observation makes this opener trial insufficient to reject the installed-source format.

## 6. Historical startup-cli control used the legacy format

The earlier result is [workbench startup & spaces-6lzpapeq/results.json](<../../build/workbench startup & spaces-6lzpapeq/results.json>). It used the legacy single-file experimental world, not the new layered source.

Its exact argument vector was:

```text
-gproj <owned absolute addon.gproj>
-noOpenLastResource
-scriptAuthorizeAll
-wbmodule=WorldEditor
-run
-load worlds/BerylCallbackProbe.ent
```

Headless compilation succeeded. The native console recorded owned `Entities load` and `WorldEditor: LoadWorld: 72.299800 ms`. Nevertheless, the owned NetAPI listener was not observed within the existing startup deadline: 42 passive port checks, zero RPCs, terminal `timeout`, confirmed owned cleanup, and no evidence errors.

A native load timing line did not establish complete readiness. This historical result also cannot determine what the same documented startup route would do with the newly source-supported two-file format.

## 7. Explicit layered startup-cli control: qd5tufrg

This control is a separate source-layered `startup-cli` selection. It changes the opening mechanism from the y5 trial while retaining the fixed source-layered candidate; it does not retry or fall back inside the previous job. Its actual outcome is recorded below.

The installed primary `EnfusionScriptAPI/html/Page_CLI.html`, SHA256 `b1fd25c1d02e3ac687bb310496f700acaf451f66d26c572afa9ac5fd343822d1`, documents:

- Line 121: `-gproj` accepts the full project-file path.
- Line 129: Workbench ignores `-world`; use `-load`.
- Line 411: `-wbmodule=WorldEditor -run` opens the selected module.
- Line 413: `-load FILE_PATH` loads a resource in the selected module at startup; the example uses a relative world resource path.

The control uses the same eight-argument startup-cli vector shown above and the same fixed `worlds/BerylCallbackProbe.ent` resource path. This provided documentary support for the experiment. The docs do not guarantee startup completion, listener availability, absence of modal interaction, or runtime load success.

Required unchanged boundaries:

1. Stage exactly ten declared inputs in a new owned workspace; preserve the original eight and retained compiler artifact.
2. Bind the receipt/token/manifest to the selected opening profile, source format, and exact bytes.
3. Use no native or script opener RPC under the startup-cli profile, and no fallback or resubmission.
4. Retain the current 30-second stage, 8-second RPC, 180-second total, 5-second cleanup, and bounded-poll policies.
5. Require actual owned listener/health and loaded-addon evidence before accepting observer results.
6. Require native addon/resource roundtrips and a nonempty native observed world path resolving to the exact owned world, with valid API/world, edit mode, and no game/play mode.
7. Preserve raw responses, logs, source identities, deadline failures, and confirmed ownership/cleanup evidence.

The common validator admits only the explicit installed combinations: source-layered format with startup-cli or module-netapi-registered. Unknown and cross-profile combinations remain errors.

### Actual outcome

The retained result is [source layered world & spaces-qd5tufrg/results.json](<../../build/source layered world & spaces-qd5tufrg/results.json>), SHA256 `a68af34eda58d95523d56b97308783701ed0542d58c2ff812cd0b43afc855fb1`. Its [engine-runtime.json](<../../build/source layered world & spaces-qd5tufrg/engine-runtime.json>) has SHA256 `f750bdfdf7acf2118c641b790424f3e5f955ed5f6ec5c16db8bb0cf4a961a71d`.

Observed and admitted evidence:

- Exact ten-file source staging and headless compilation succeeded.
- The owned startup adapter completed in `13604` milliseconds. This is its recorded elapsed duration, not total compilation/preparation time or a performance benchmark.
- Exactly three actual RPCs ran, in order: `IsWorkbenchRunning`, `GetLoadedProjects`, and `BerylStartupReadiness`. No `OpenResource` or callback action was submitted.
- The final normalized reply was `ready`, with an empty failure string and `mechanism = startup_cli`.
- The native observed `world_path` was `$BerylComponentCallbackProbe:worlds/BerylCallbackProbe.ent`. Its native absolute resolution, addon-world resolution, and registered-resource roundtrip all identified the exact owned candidate world.
- Module/API/world presence, path resolution, world equality, and edit mode were true. Game mode and `InPlayMode` were false.
- The owned process identity was PID `4052`, start ticks `639272541485736188`, with no reuse. Owned process exit was confirmed; both orchestration host exits were confirmed and successful, with no cleanup or evidence errors.

The six completed readiness IDs are `startup.loaded-addon`, `startup.native-addon-world`, `startup.resource-roundtrip`, `startup.editor-api`, `startup.owned-edit-world`, and `startup.confirmed-cleanup`. They name asserted obligations supported by the recorded process/resource/RPC observations. They are not six engine callback cases.

The receipt retained the same limits: `30000` ms stage, `8000` ms RPC, `180000` ms total, `5000` ms cleanup, at most `64` polls, and at most `67108864` bytes of raw logs. It explicitly records that native launch and bridge calls are not hard-cancelled by the inner adapter; the parent owned-host job has its separate bound. This success is not a hard real-time guarantee.

`startup_world_readiness` is now `executed_success` for this exact trial. Callback delivery, tablet services, native program execution, world save, engine-authored serialization, gameplay, multiplayer, visual, and performance remain outside its successful scope.

This establishes a usable named edit-world checkpoint for the exact source-layered startup configuration. It does **not** establish a sole cause for prior stalls or refusals, show that the registered opener must work, or validate all authored-world formats. Prior failed trials remain retained as their own outcomes.

## 8. Callback continuation and acceptance boundary

The named edit-world readiness gate has the scoped `qd5tufrg` receipt. The separate `source-layered-v1` callback candidate contains nine inputs: the original callback eight, with its world text replaced, plus the layer. Its token includes the selected profile and layered evidence identities. The actual callback attempt is described below; readiness from the earlier job did not replace this job's native observations.

The callback bridge must preserve its actual deferred-load counters, native path/resource/mode checks, and load → play → spawn → delete → stop protocol. A startup readiness result cannot substitute fabricated successful counters. Two native-spawned fixture entities must deliver the seven registered post-init/frame/independent-state/delete cases; no callback may be invoked manually to complete the gate.

Play-mode availability, authority, frame delivery, deletion delivery, tablet services, full teardown lifetime, and multiplayer remain separate acceptance work. A partial post-init trace does not close the seven-case callback receipt.

## 9. Actual partial callback trial: merbrapz

The retained [results.json](<../../build/component callbacks & spaces-merbrapz/results.json>) has SHA256 `9d451e130128993e60ca51aa9110bea51ae5e7bf10a1fe7a2a10c25cc93db1ea`; its [engine-runtime.json](<../../build/component callbacks & spaces-merbrapz/engine-runtime.json>) has SHA256 `00c3618ce90a8e2c3001a96707e82659d547a7f68c9453ed0e012526e1db015c`.

Observed stages were:

| Stage | Actual outcome | Polls | Recorded elapsed ms |
|---|---|---:|---:|
| Load | Completed; exact named world, edit mode, all deferred-load counters one | 2 | 2019 |
| Play | Completed; game mode and `InPlayMode` true, edit mode false | 3 | 1133 |
| Spawn/frame collection | Timeout; two post-init pairs, no frame rows | 64 | 15196 |

The six-row successful observation prefix is retained unchanged:

```text
event|0|init_before|1|0|0|0|1|1|1|1|1
event|1|init_after|1|1|0|0|1|1|1|1|1
control|2|authority|1|1
event|3|init_before|2|0|0|0|1|1|1|1|1
event|4|init_after|2|1|0|0|1|1|1|1|1
control|5|authority|2|1
```

These are actual native-spawn observations from two fixture entities; the experiment did not manually invoke their callbacks. The prefix records the initialized state and authority check for each token. It does not establish frame-state evolution or deletion. The final spawn response remained phase `2`, `executed = 0`. The job reported `timeout`, confirmed owned process exit, and retained no evidence errors. It did not report the seven cases as passed.

Source generation and headless compilation succeeded. The generated component registers `EntityEvent.FRAME` in `OnPostInit`, after its superclass and initialization handler. The spawn code calls `owner.SetFlags(EntityFlags.ACTIVE, false)`; that second argument means nonrecursive flag application. It spawns into `api.GetWorld()`. Those source calls are known, but this attempt did not record native readbacks of entity flags, component/owner event masks, editor/game/owner world equality, or world-time progression. Their runtime state cannot be inferred from the absence of frame rows.

The retained console notes a missing game mode and fallback; that observation is not proof of the scheduling cause. In particular, play-mode predicates alone did not demonstrate advancing simulation or frame delivery. The named world loaded successfully in this attempt, so its outcome must not be described as another resource-load refusal.

## 10. Explicit controlled background-update policy

Installed primary documentation [Page_CLI.html](../../build/force-update-primary-evidence-20261010-891d30c4/Page_CLI.html), line 157, declares `-forceUpdate`: “Forces the application to render and update even when window looses focus.” Its exact SHA256 remains `b1fd25c1d02e3ac687bb310496f700acaf451f66d26c572afa9ac5fd343822d1`. Line 159 describes `-noFocus` separately as preventing focus stealing during initialization; that is not a substitute for updating an unfocused application.

The new passive [primary evidence receipt](../../build/force-update-primary-evidence-20261010-891d30c4/observations.json), SHA256 `4e592e716f6786179ddc7ee81fed5492180ab8620dd8ca95972c38721aaa75fb`, retains the checked document bytes, exact clause lines, and the `merbrapz` receipt identities and partial prefix. This capture only read primary/retained inputs and wrote its new owned build evidence. It executed no compiler, host adapter, or engine and sent no process signal.

The authorized controlled experiment is an explicit opt-in startup policy that adds only the documented `-forceUpdate` argument. It keeps `api.GetWorld()` as the spawn receiver, the layered world and generated component/observer behavior, all seven callback case obligations, resource/session guards, ownership, and existing deadlines. The existing plugin daemon has no general startup-argument option; the separate owned launch seam preserves exact argument encoding and process ownership without changing that external tool or reusing a session. Per-job tokens and absolute paths still differ as required for fresh artifact identities.

The first selected attempts stopped before runtime, as recorded below. The mechanism subsequently executed in `a7u0gcvh`, with the same init-only prefix and no frame rows. The hypothesis was that application focus/background updating might contribute to the outcome; neither the primary clause nor this result proves that it did. The actual negative control shows that adding this flag was insufficient to complete this fixture's frame gate. It does not prove editor/game world equality or settle unrelated engine configurations.

Any future scheduling diagnosis can observe native flags/masks, current world identities, and time progression at bounded existing observation points. Such added observations require a separate source/receipt identity; they are not present in `merbrapz` and are not part of the single-variable control described here.

## 11. Selected control stopped before runtime: j71odte1

The fresh [results.json](<../../build/component callbacks & spaces-j71odte1/results.json>), SHA256 `1f43ca6bb9a293bd6e637395ac7d328a99264fdb5a02dfcc33250f008c66d32f`, records `engine_updates = force-update`, `world_fixture = source-layered-v1`, terminal status `unavailable`, and stage `engine_compile`. Its [engine-compile.json](<../../build/component callbacks & spaces-j71odte1/engine-compile.json>) has SHA256 `415a060454982f56c67459273f7e8fe17410c6e89f1fbf778a1ee61266cb83d3`.

Source generation succeeded and staged the exact nine-file callback candidate. The headless compile adapter was invoked and returned `unavailable`; its nested bridge result reports `Ok = false`, `Stage = DidNotStart`, `ExitCode = -1`, `LogDir = null`, an eight-second reported duration, and no script diagnostics. Its failure text attributes the result to absence of a Workbench log directory. This is the **adapter's startup-unavailable classification**, not evidence that `-forceUpdate` failed, a proved script error, or a confirmed native scheduling cause.

The compile orchestration PowerShell process exited with code `1` after approximately `10.977` seconds, with exit confirmed and no recorded host cleanup errors. The successful source-build host also confirmed exit. These are host-process observations. There was no callback-runtime adapter invocation, runtime session receipt, spawn request, callback trace, or `engine-runtime.json` in this attempt. The force-update startup branch therefore was not exercised. The absence of a runtime session also means this receipt does not supply runtime engine-process cleanup evidence.

Independent passive inspection found that all `97` recorded source/tool inputs, all nine staged inputs, the four original artifact files and their four retained copies, and all four command stdout/stderr files matched their recorded hashes. The actual compile JSON matches the raw result embedded in the main receipt. The only recorded derived staged output is the bounded root `resourceDatabase.rdb`, `686` bytes; it does not establish compilation success.

This attempt remains a separate retained `unavailable` outcome. The earlier `merbrapz` init-only prefix remains valid within its own identity and coverage; it cannot complete the new control. The callback gate, background-update hypothesis, tablet service runtime, and later release gates remain open. No retry, fallback, security-setting change, or deadline widening is implied by this packet.

## 12. Startup diagnostics and process-visibility correction

The separate [headless startup diagnostic](../../build/oct10-compile-startup-ir9l0jhj/result.json), SHA256 `a906d73edd29af903d6dab662d426034c0181ab3073b84af7d68c5520187bf35`, cloned the declared source inputs into a new owned workspace. It used the same fixed headless compilation arguments and identified executable/game working directory. The actual direct child was PID `12844`; it returned exit code `4294967295` after approximately `8.216` seconds, with exit confirmed, empty captured stdout/stderr, and no new log directory. No stop was requested because that child had already exited. The receipt explicitly leaves descendant exit unobserved and labels verification `not_verified`; this is process-startup evidence, not script compilation or callback evidence.

An initial [passive process/events inventory](../../build/oct10-startup-events-74iga84j/observations.json) and [Steam prerequisite observation](../../build/oct10-steam-prerequisite-sdnguh25/result.json) were made within a restricted process-visibility context. The latter recorded no existing visible Steam process and an owned hidden no-argument launch observation. This did **not** establish that Steam was globally closed. A later [inventory outside that restricted view](../../build/oct10-steam-prerequisite-6t2qxts0/result.json), SHA256 `85e730b9bdc9c40d4a46036925353f8037384e1b7f774350f82eba2eca0344bf`, found an existing Steam process, PID `19964`, with start time `2026-10-10T12:35:48.8286349-04:00`, and `launch = null`.

Both prerequisite receipts explicitly cover process presence only. They do not establish account/API readiness, compilation success, or a cause of the earlier engine exit. An absent process in one restricted inventory must not be described as machine-wide absence. No conclusion that starting Steam repaired the engine is supported.

The intervening fresh callback attempt [je7jvfs1/results.json](<../../build/component callbacks & spaces-je7jvfs1/results.json>), SHA256 `11c51085a1c90618e96d65041fe459526cd1c2684d6464ad0f4aee03f24bc3f5`, again stopped before runtime at the compile adapter's startup-unavailable outcome. Its compile receipt SHA256 is `ae463f5feae0067c730f98810d15e203be51079998e0c4754384d4dd0340b2d2`. This negative attempt is retained independently; it did not execute the force-update runtime branch.

## 13. Actual force-update control: a7u0gcvh

The fresh [results.json](<../../build/component callbacks & spaces-a7u0gcvh/results.json>) has SHA256 `d40362f3b3d3f8fa6d9e2eebaf3dd560dd27c23a2645be03475c2f6e05bf2b59`. Its successful [engine-compile.json](<../../build/component callbacks & spaces-a7u0gcvh/engine-compile.json>) has SHA256 `0812f14817bc767d17de1facea9075e17db7c3b44eb805e7de9da72b0e902fbc`; its terminal [engine-runtime.json](<../../build/component callbacks & spaces-a7u0gcvh/engine-runtime.json>) has SHA256 `53852125be342447786c351625ecadde201fe3a1766dcd7d1261dfe8bd8c2b48`.

This trial executed the selected startup policy. The raw launch receipt records `force_update_argument_list`, exactly five arguments (`-gproj`, owned absolute `addon.gproj`, `-noOpenLastResource`, `-scriptAuthorizeAll`, `-forceUpdate`), the identified game working directory, `UseShellExecute = false`, `CreateNoWindow = true`, and requested hidden window style. The process identity was PID `18420`, start ticks `639272562713034857`, with no reuse. Eleven bounded listener observations ended with a listener exclusively owned by that PID. The recorded startup object matches that same PID and mechanism.

Because the main verifier exits on the transport timeout before its successful semantic-admission path, the startup evidence was checked separately during this passive audit. Only the pure `validate_engine_updates` function was extracted from the retained verifier source, SHA256 `2d20c386de20e44f6ef0946d6743e1949742b8fca717441039e94b9e36748a91`, and evaluated against the actual receipt. It admitted **fixed owned startup and listener identity only**. This check did not execute an adapter, compiler, or engine and did not admit callback correctness.

Observed runtime stages:

| Stage | Actual outcome | Polls | Recorded elapsed ms |
|---|---|---:|---:|
| Load | Completed; exact named world/edit mode and accepted native load counters | 2 | 4174 |
| Play | Completed; game mode and `InPlayMode` true | 3 | 1735 |
| Spawn/frame collection | Timeout; same six-row init/authority prefix, no frame rows | 64 | 15621 |

The final response remained phase `2`, `executed = 0`, `checks = 34`, `failures = 0`, `event_count = 6`, and `caseIds = []`. Its trace is byte-for-byte identical to the six-row prefix in section 9. This is partial successful observation, not a passed case set; deletion and the seven-case completion were not reached.

The runtime adapter's total recorded elapsed duration was `32054` ms. The fixed startup/RPC/overall/cleanup bounds were retained. Owned process exit was confirmed with `cleanup = owned_process_stopped`, and `evidence_errors = []`. All three orchestration hosts confirmed exit with no cleanup errors; source generation and compilation returned zero, while the runtime host returned one for its timeout.

Passive hash checks found that the nine staged inputs, four original artifact files and four retained copies, six command logs, and three retained session logs matched their recorded identities. All `97` retained input byte identities matched. At the time of review, `96` original input paths remained unchanged; the compile-adapter source was being separately corrected after this receipt, and the retained bytes preserve this trial's exact earlier identity. The compile/runtime JSON files match the raw objects embedded in the main result.

The opt-in update flag is therefore tested for this exact configuration and did not complete frame delivery. This does not support a general claim that the flag never helps, that focus was or was not the sole cause, or that spawning into `api.GetWorld()` selected the actual advancing gameplay world. Flags/masks, owner/editor/game world equality, and world-time progression remain unobserved here. Those are the next bounded diagnostic observations; they require a new identified fixture and must not synthesize any missing callbacks.

## 14. Actual live world readbacks: bbe8mikw

The new [results.json](<../../build/component callbacks & spaces-bbe8mikw/results.json>) has SHA256 `cb3cc3aeeb19a5ef02680b86958ac159f2b75c9c8492d5b07722ec92305d3b79`. Its successful [engine-compile.json](<../../build/component callbacks & spaces-bbe8mikw/engine-compile.json>) has SHA256 `762cdd22143b5d40a73aa3e770f811cbf4071dafa941990281f55e32b3c80ac8`; its terminal [engine-runtime.json](<../../build/component callbacks & spaces-bbe8mikw/engine-runtime.json>) has SHA256 `7763dc875b36a33b1f07e1e3ca9143171e59797c5845602a40d5db8e859cc5d4`.

This trial retains the opt-in `force-update` startup and adds the separate `world-state-v1` observer. The observer makes read-only native identity, frame-number, flag, and component-mask queries on the two live fixture owners before deletion. It does not create an entity, change a mask or flag, invoke a callback, or replace the original seven-case comparison.

The exact source identities are:

| Input | SHA256 |
|---|---|
| Callback verifier | `7844132cb9aed4c1ca2f0ad0eddc1fb2c3368857510137d6c4d23223d375db23` |
| Runtime adapter | `9bbb7fdbb4312a792bfe4a90cdb6fc0bccc318b6a8906d054fe2c5816c0c783d` |
| Read-only observer template | `fcf4b756c0eb32935e2e15c69d2db6c06d52171528d5d19e53a6aa136c72f2e2` |
| Observer primary contract | `562f7387520f70a0fa009d35fdda63a88ea058f6cda817e7995a96339e7f9e57` |
| Original spawn RPC template | `ce6324bdbab75aebfaf6f832e76c59fd9dbd1617506a5c9c96c6bbc83caa8099` |

Source generation and engine compilation succeeded. Load completed after two polls in `2722` ms; play completed after three polls in `1116` ms. The existing spawn/frame gate timed out after `64` polls in `16036` ms. The runtime adapter recorded `32458` ms overall, an owned session PID `22972` with start ticks `639272575252558904`, confirmed process exit, and no evidence errors. These elapsed durations are harness evidence, not performance measurements.

Both diagnostic calls returned `observed`, with empty failure strings and phase `2`. Raw numeric Boolean values remain preserved; the separately recorded codec interprets only exact `0`/`1` values. The first observation began at elapsed `16404` ms and its owned-identity check completed at `16543` ms. The second began at `31998` ms and completed its identity check at `32133` ms. Neither call exceeded its recorded `8000` ms budget.

| Native readback | First observation | Second observation |
|---|---:|---:|
| Editor API world frame number | 0 | 0 |
| Game world frame number | 185 | 7566 |
| Owner 1 / owner 2 world frame number | 0 / 0 | 0 / 0 |
| Editor API world equals game world | false | false |
| Each owner world equals editor API world | true | true |
| Each owner world equals game world | false | false |
| Each owner flags | 515 | 515 |
| Each owner ACTIVE bit | true | true |
| Each observer component event mask | 8 | 8 |
| Each observer component FRAME bit | true | true |

The mask is obtained from `GenericComponent.GetEventMask()`. It is a component readback; the packet does not label it as the parent entity's mask. Frame numbers are native world counters, not wall-clock or simulation-time measurements.

These observations establish a concrete fixture-world mismatch. The original factory call passed `api.GetWorld()`, and both returned owners belonged to that world. The independently identified game world was different and advanced between the two observations. ACTIVE and the component FRAME registration were present. This supplies a specific harness explanation for why the previous observations did not establish delivery in the advancing game world; it does not establish a defect in the generated callback body or every possible scheduling prerequisite.

The receipt still reports the original callback observations as `present_unverified`, callback delivery as `attempted_unconfirmed`, and full world lifetime as `unverified`. No complete case set or native deletion trace was reached. The diagnostic comparison has status `observed` and an empty error list; that status must not be promoted into callback success.

### Controlled correction frozen before the next trial

The fresh RPC template SHA256 is `bbf9630ac3de4f335943ddfdd46f6c2332e0533f5def1e32e6f1d187170413f8`. An exact comparison against the retained `bbe8mikw` template found changes only in the spawn action:

1. Check the fresh `GetGame()` reference and `InPlayMode()` in addition to the existing owned-world, mode, and fresh-registry checks.
2. Capture nonnull `BaseWorld runtimeWorld = GetGame().GetWorld()` within the invocation.
3. Call `GetGame().SpawnEntityPrefab(prefab, runtimeWorld, null)`.
4. Require the returned owner to belong to `runtimeWorld` and contain the observer before applying ACTIVE and authority checks.

The pending-token and `Bind` ordering, generated functions, event hooks, native authority/deletion operations, response schema, seven-case obligations, bounds, and diagnostic observer remain unchanged. There is no manual callback, GameMode addition, terrain addition, fallback, or deadline widening.

Installed `EnfusionScriptAPI/html/interfaceGame.html` declares `SpawnEntityPrefab(Resource, BaseWorld, EntitySpawnParams)` at lines `172` and `1299–1323`, SHA256 `dfcab6b926646b8b56cdcbf38bb3e5f9809e96c9e3efaabc11cf806d6ec4b22e`. Its documentation says the factory instantiates the entity with its components; it does not equate the editor and game worlds. The retained installed [Game.c](../../build/world-authoring-source-research-20261010-b274dc91/selected/Game.c) implements sealed `GetWorld()` as the game object's `m_World` at lines `9` and `13`.

The primary `Page_Replication.html` uses an existing live owner's `GetWorld()` explicitly in prefab factory calls at lines `561` and `572`, SHA256 `7bb668998217037917a9e259dee27b1fb1f74f72b43efaf90d5c71f9dcec480c`. It also registers component FRAME events in `OnPostInit` at lines `224–241`. These are source examples, not a guarantee of the pending fixture's execution.

The unchanged native teardown contract is `RplComponent.DeleteRplEntity(entity, false)`. `ArmaReforgerScriptAPIPublic/html/interfaceRplComponent.html` declares the operation at line `130` and distinguishes authority physical deletion from proxy behavior at lines `168–169`, SHA256 `bf2a18873cce62ca6d3777ff7fbe2078049cb467e4660b8f682bffce7424dbe2`. The existing authority checks and requirement for real deletion callbacks remain essential.

At the source-review checkpoint, this correction was frozen for a new identified root-owned trial and had not run. No result was inferred from source review alone. The later actual outcome is recorded separately below.

## 15. Corrected game-world callback trial: idjip0_z

The fresh [results.json](<../../build/component callbacks & spaces-idjip0_z/results.json>) has SHA256 `b60885738f091d22deb366451dcb096b6a6e6ae2eb774fa26d9090de3b987290`. Its successful [engine-compile.json](<../../build/component callbacks & spaces-idjip0_z/engine-compile.json>) has SHA256 `94a85aef7324e63527e8a1533d60a598016f31f4b0cb87e49417af5b2e5173de`; its successful [engine-runtime.json](<../../build/component callbacks & spaces-idjip0_z/engine-runtime.json>) has SHA256 `22b90321187b2f117f48a95d969978675c516150c099cfd9cc4b976763462d64`.

This trial used the corrected RPC template `bbf9630ac3de4f335943ddfdd46f6c2332e0533f5def1e32e6f1d187170413f8`. The verifier, transport, generated callback bodies, observer, source-layered world, authority/deletion operations, case set, and limits remained as described in section 14. The fixed change passed a fresh nonnull game world to the factory and checked each returned owner's world before further fixture use.

Source generation and exact staged script compilation succeeded. All runtime stages completed:

| Stage | Recorded polls | Recorded elapsed ms |
|---|---:|---:|
| Load | 2 | 2123 |
| Play | 3 | 1197 |
| Spawn/frame collection | 1 | 832 |
| Native deletion | 0 | 287 |
| Return to edit mode | 1 | 692 |

The completed deletion reply had phase `4`, `executed = 1`, `failures = 0`, and all seven expected case IDs exactly:

- `runtime.post-init.1`
- `runtime.post-init.2`
- `runtime.frames.1`
- `runtime.frames.2`
- `runtime.independent-state`
- `runtime.delete.1`
- `runtime.delete.2`

The comparison reports `verified`: each owner received `340` real frame callbacks. The complete trace contains `1373` rows (`1368` event rows and `5` control rows), checksum `538030`, and `10949` recorded checks. The final ordered events include both `delete_before` / `delete_after` pairs following the authority controls. No fixture code directly invoked the engine callbacks.

The retained [callback-trace.txt](<../../build/component callbacks & spaces-idjip0_z/callback-trace.txt>) is `58091` bytes, SHA256 `54c708557701a3378d8e3387f1f93f5f3e1a3cf8b6d525553cc3c7f652b3eed8`. Floating-state comparison is explicitly target-rounded `f32` equality; it does not claim bitwise floating serialization or universal cross-target equivalence.

The single read-only live snapshot began at elapsed `14658` ms. It reported editor API frame `0`, game frame `185`, and both owner frames `185`. The editor API world remained distinct from the game world; both owners now equaled the game world and did not equal the editor API world. Each owner still had flags `515`, ACTIVE true, component mask `8`, and FRAME true. The raw reply is preserved independently from Boolean normalization. This confirms that the intended spawn-world change was exercised; callback success is established by the complete native trace, not by the snapshot alone.

The runtime adapter recorded `16551` ms overall, an owned non-reused PID `26412` with start ticks `639272578291467525`, `cleanup = owned_process_stopped`, and an empty evidence-error list. The main job returned success. These durations are execution evidence, not a performance benchmark.

The before/after trial pair identifies the previous fixture receiver as a concrete harness mistake: the original owners were created in the stationary editor world; the corrected owners belonged to the advancing game world and delivered the required callbacks. This finding does not establish a general editor/game equality rule or invalidate other scheduling prerequisites. The result retains `force-update`; no trial here establishes whether that flag is necessary once the factory world is correct.

The completed scope is **the bounded generic generated scalar-component fixture on two entities**. It establishes the tested native component construction, post-init/frame/delete ordering, and independent state for these exact bytes and engine configuration. `component_world_lifetime` remains `unverified`: broad teardown retention, world transitions, reloads, ownership transfer, and all other lifetime contracts have not been proved by this fixture. The tablet service adapter was not connected, a complete tablet was not exercised, native Beryl programs were not executed, engine-authored serialization was not performed, and multiplayer, visual, installation/promotion, and performance gates remain open. An independent comprehensive receipt audit was pending when this additive outcome was written; no such audit is implied by this document update.
