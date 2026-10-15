# P5-S2: execute the five existing tablet suites

Date: 2026-10-10. The fresh owned run `wbymk7mx` passed the five existing suite selections, and its exact receipts and files passed an independent passive audit. This is engine-executed structural/service-helper evidence. It makes no generated tablet lifecycle, multiplayer, visual, resource-closure, or performance claim.

## 1. Objective and boundary

Execute the five unchanged `SPK_MeshSelfTest` selections admitted by `tablet-suites-v1`, against an exclusively owned copy of the exact verified candidate. Preserve the original candidate and its compilation receipt.

This gate concerns engine-executed structural widgets, the declared action table, synchronous manual button-handler dispatch, and the tablet prefab's component schema. The suites do not instantiate the generated `SPK_TabletComponent`, drive the gadget protocol, call its engine callbacks, or establish the lifecycle/service trace contract. The generated class remains covered by compilation and earlier independent scalar evidence until a separate actual tablet gate executes it.

The five suite names are the five expected receipt IDs. They are not individual assertion IDs. Their original response contains no assertion count, trace, token, final checksum, or case list.

## 2. Exact source identity

The files below were read without modification from `C:/Users/moham/Documents/My Games/ArmaReforgerWorkbench/addons/SparkOS_Mesh`. Their bytes match the selected source profile at this review.

| Input | Bytes | SHA-256 |
|---|---:|---|
| `scripts/WorkbenchGameCommon/SPK_MeshSelfTest.c` | 129607 | `59213fecdd4ecd1ced6e0eee0716b5c86bf3cc184ee6261452da9ac3c4dcda46` |
| `scripts/Game/SparkOSMesh/UI/SPK_TabletUI.c` | 36025 | `4efeab8cce793939d748506f34691aae9b0b47aa8b32ed568ece05accf28a05d` |
| `scripts/Game/SparkOSMesh/UI/SPK_ScreenRT.c` | 4053 | `6328c5e86787b75c8cf949fcbd914c4fb137e17534a6158150bdba13818e942b` |
| `scripts/Game/SparkOSMesh/UI/SPK_TabletChrome.c` | 25331 | `53c2fccfb900371ce0ea409d98f0903a20e71e472630e6caea87b29477a1811e` |
| `scripts/Game/SparkOSMesh/UI/SPK_UIButton.c` | 4079 | `24f45c2d5cc8dc050290047bf8a9c902f536cfd7e3fa5569b07410816cd03c9a` |
| `scripts/Game/SparkOSMesh/UI/SPK_MapView3D.c` | 3261 | `0c27575d1736acc42175078549d5ace422e8c13be000bf686c3cf69469a34f58` |
| `scripts/Game/SparkOSMesh/Input/SPK_DroneActions.c` | 8589 | `faeb200d3da43ea30b4d2db36152b9d634f4b74bf21c1173b6dfc55ec829a113` |
| `Prefabs/SPK_Tablet.et` | 593 | `dabd491efd1b27cf49b311948c1215acf1982f06f6b6de8a0e9ea0e001ae0c22` |

Source references in subsequent sections use line numbers in these exact bytes. The candidate's own retained hashes, source-map linkage, resource inventory and compilation receipt govern execution; these live-source observations do not supersede them.

The selected profile is [tablet-suites.v1.json](C:/Users/moham/Desktop/beryl/packages/sparkos/tablet-service-prototype/tablet-suites.v1.json), SHA-256 `22a8a3b18f93599765e61b34c7c9cd3b13a011d4f8c4e8649b4e24b9d6531514`. It declares the five suites; it does not execute them.

## 3. Original execution interface

`SPK_MeshSelfTest` is the fixed NetAPI function. Its request has exactly two registered string fields, `suite` and `arg` (`SPK_MeshSelfTest.c:19–30`). Its response has exactly two registered fields: signed integer `ok` and string `detail` (`:33–42`).

The requests are fixed and ordered:

| Receipt ID | Function | Exact request |
|---|---|---|
| `ui` | `SPK_MeshSelfTest` | `{"suite":"ui","arg":""}` |
| `screen` | `SPK_MeshSelfTest` | `{"suite":"screen","arg":""}` |
| `actions` | `SPK_MeshSelfTest` | `{"suite":"actions","arg":""}` |
| `clicks` | `SPK_MeshSelfTest` | `{"suite":"clicks","arg":""}` |
| `schema` | `SPK_MeshSelfTest` | `{"suite":"schema","arg":"{B37EEB64E149CBAD}Prefabs/SPK_Tablet.et"}` |

A response is a successful suite return only when the bridge succeeded, the raw reply parses into the same retained response, the response fields are exact, `ok` is the JSON integer `1`, and `detail` satisfies the particular success contract. Boolean `true`, strings, floats, empty objects, default-initialized responses, and missing details are rejected.

The frozen source constructs 29 action definitions (`SPK_DroneActions.c:92–124`: 10 flight, 12 sensor, 7 systems) and 23 chrome buttons (`SPK_TabletChrome.c:262,294–314,373,398,412–421`: one header, six asset rows, eight contact rows, two toggles, five orders, one strike). These are control counts, not assertion counts.

Expected successful details are:

- `ui suite passed`
- `screen suite passed`
- `actions suite passed (29 controls)`
- `clicks suite passed (23 controls)`
- A bounded, successfully parsed tablet entity-component dump for `schema`, as specified below.

## 4. Prerequisites, side effects and actual coverage

### UI

`RunUiSuite` (`SPK_MeshSelfTest.c:326–398`) requires a game object and workspace. It calls `BuildWidgets`, verifies names, observes 2D → 3D → 2D state, closes twice, and checks that the UI reports closed. It deliberately does not call `Open`, attach the 2D game map, populate from MESH, or exercise the generated tablet component.

`BuildWidgets` attaches the terrain object without rendering or sampling it (`SPK_TabletUI.c:312–313`). It queues `ReportRootSize` after 500 ms (`:346`), but the suite closes and returns synchronously. The suite does not wait for that callback or validate its cancellation, receiver retention, layout measurements or later cleanup.

The 3D toggle is not pure. `SetMapMode` invokes `SPK_MapView3D.Attach` (`SPK_TabletUI.c:1022–1028`); when `GetGame().GetWorld()` is nonnull, `Attach` changes the render target and world camera (`SPK_MapView3D.c:41–60`). This is why the probe must own the session and empty editor context. No play transition is required by this source. Never run it against an unrelated player's or editor's world.

`RefreshTerrain` is queued by `Open` (`SPK_TabletUI.c:143`), which this suite does not call. There is no reason to add terrain loading or terrain sampling to this gate.

### Screen

`RunScreenSuite` (`SPK_MeshSelfTest.c:507–564`) requires game/workspace, creates the render-texture widget and content, checks names, rejects a null owner, and calls disable/destroy twice. It cannot establish binding to a real tablet entity, model material behavior, rendered output, owner invalidation or teardown through native entity deletion. Its own source comment explicitly makes that distinction.

### Actions

`RunActionsSuite` (`SPK_MeshSelfTest.c:1366–1443`) constructs the action table, checks unique names/default keys, presentation fields, selected defaults/kinds, group partitioning, and unknown lookup. It has no game, world, workspace or asynchronous prerequisite. It does not verify native key events, rebinding persistence or authoritative commands.

### Clicks

`RunClicksSuite` (`SPK_MeshSelfTest.c:1516–1643`) requires game/workspace and builds chrome on an owned temporary widget. It verifies declared/handled actions, row discovery, direct handler dispatch, index forwarding and disabled/re-enabled behavior.

It directly calls `OnClick(null,0,0,0)` (`:1591,1598,1609,1614`). This is engine-executed script dispatch through the original handler, not a native physical click event. `Chrome.Build` is synchronous; this path does not queue terrain rendering or open the full tablet. The suite verifies map-mode control reachability, but does not specifically dispatch that control through the actual tablet component.

### Schema

`RunSchemaSuite` (`SPK_MeshSelfTest.c:2380–2511`) loads the fixed tablet resource while keeping its `Resource` handle in the same function scope. It can return `ok=1` for a generic container as well as an entity. Consequently the selected tablet gate rejects the container fallback and requires these six component classes exactly once:

- `MeshObject`
- `InventoryItemComponent`
- `SPK_TabletComponent`
- `SPK_TabletGadgetComponent`
- `SPK_DroneInputComponent`
- `SCR_EditableEntityComponent`

The detail format is whitespace-prefixed `ClassName[varName,...]` segments. Parse it with explicit byte, component, field and identifier limits. Reject malformed, duplicate, missing or unexpected component classes and duplicate or malformed variable names. Preserve the original detail and parsed row order without sorting. Do not guess a complete inherited-variable list. This response reports variable names, not their values. It cannot independently prove `m_eUseMask=15`, `m_eAnimVariable=MAP`, material/texture freshness, imported resource closure, or successful prefab spawning.

The handler enumerates native `IEntitySource.GetComponent(i)` (`:2491–2507`); it does not reconstruct the prefab's authored order. The installed [IEntitySource declaration](<C:/Program Files (x86)/Steam/steamapps/common/Arma Reforger Tools/Workbench/docs/EnfusionScriptAPI/html/interfaceIEntitySource.html>), SHA-256 `ef3cf0443dfb5f50a266b1f6fbcfea85f7546c287e89dfe7b0e9ec2c30e10196`, has empty documentation for `GetComponent` and `GetComponentCount` (`:198–201`, `:215–218`); it supplies no order guarantee. The actual returned order differed from the prefab source order. That observation establishes neither a universal alphabetical ordering rule nor a prefab defect.

## 5. Minimal owned transport

The new adapter reuses the installed Workbench RPC bridge and established ownership primitives. The old [mesh-engine-run.ps1](C:/Users/moham/Desktop/beryl/scripts/mesh-engine-run.ps1) is not sufficient unchanged: it targets `SparkOSMesh`, selects nine different suites, uses coercive response checks and does not retain confirmed cleanup.

Required boundaries:

1. Capture a new immutable clone of the 86-file suite candidate, preserve the original, and retain any added trusted identity handler as a distinct input. Compile the resulting exact staged source set before runtime.
2. Use the fixed six-argument module-startup vector in an exclusively owned process: `-gproj`, the exact owned `addon.gproj`, `-noOpenLastResource`, `-scriptAuthorizeAll`, `-wbmodule=WorldEditor`, `-run`. Do not add `-load`, open a resource, enter play, spawn/delete entities, request manual component callbacks, save resources, reuse an editor, or fall back after an error. The declared editor context is a startup request; it is not a claim that a world path or workspace was independently observed.
3. Verify retained process ID/start/executable identity and an owned NetAPI listener. Execute exactly one loaded-project request as the initial actual connection check. Require `BerylTabletSuitesPrototype` and permit only it, `ArmaReforger`, and `core`; reject unrelated addons, including the original MESH addon or duplicate production class/resource identity providers. There is no separate health request or fabricated health evidence.
4. Use a separately compiled fixed identity handler initially, before and after each suite, and finally. Its response has exactly three strings: `token`, `profile`, `source_sha256`. All must equal the expected immutable candidate identity. Do not add a token to, or rewrite, the original self-test handler. This yields twelve identity requests, five suite requests and one loaded-project request: eighteen actual RPCs.
5. Execute the five fixed suite requests exactly once in the declared order. Retain function, parameters, raw response, parsed response, elapsed time and surrounding process/identity observations. A failed request terminates the operation; there is no retry, alternate mode or partial-success release.
6. Recheck source, staged tree, artifact, tool and engine identities after execution. Admit only separately enumerated compiler-owned derived output. A new native resource write is not evidence that an original input remained unchanged.
7. Stop only the owned process and require confirmed exit. Cleanup failure cannot be hidden by otherwise successful suites.

Keep the current approved 30-second stage, 8-second RPC, 180-second overall and 5-second cleanup bounds. These are the implemented harness bounds for this gate, not a guarantee that another configuration will complete. Enforce paid monotonic duration through receipt capture and cleanup. Late replies, timeout, cancellation, startup failure, missing capability, raw parse failure and suite failure remain distinct outcomes.

`no game`/`no workspace` are actual executed suite failures with the original detail. The wrapper may additionally report the unmet UI capability; it must not turn them into a matching success or infer that the suite never ran.

## 6. Independent receipt admission

The independent [receipt checker](C:/Users/moham/Desktop/beryl/scripts/verify-tablet-suite-runtime-receipts.py) binds the exact recorded source manifest, adapter and engine identities; enforces the predeclared operation and RPC sequence; checks process ownership, surrounding identity responses, strict raw/parsed agreement and late-result bounds; and requires all five successful suite receipts plus confirmed owned cleanup. Physical current-file rehashes remain the owning runner's explicit responsibility; admitting a recorded file fingerprint is not a new physical measurement.

Keep expected suite IDs as a fixed tuple, never derive the expected set from returned results. Invalid data, duplicated/missing selections, incorrect parameters, source changes, stale identity, unknown fields, coerced `ok`, wrong success details, malformed schema, incomplete logs/receipts and false cleanup claims are negative fixtures.

Pure receipt tests validate harness admission only. They do not execute these suites, verify the handler inside Workbench or establish engine resource loading.

## 7. What closes, and what remains

The admitted `wbymk7mx` run closes only the five original source-defined suite selections for its exact candidate/engine/tool configuration. It records five suite successes and no fabricated assertion count.

The next distinct actual tablet gate must then establish native component creation and callbacks in the Game world; real `Focus`/`Unfocus`/screen/UI/input service flow; lifecycle state at every reviewed commit point; one native UI event; queued-close/reopen/destruction behavior; local-owner isolation; and retained resource identity. Dedicated clients, visual interaction, stable generated prefab/property/layout authoring, promotion and performance remain separate gates.

The successful generic component callback fixture is a prerequisite for that later construction, not a substitute for the tablet services.

## 8. Pure harness checkpoint

The historical independent checker had 125 fixed, predeclared synthetic receipt cases. All passed against checker SHA-256 `29e4154e0ba226ed7f7bde3c260ee05f50bb5a48166ade5ccebbc3c62120213c` (52,738 bytes). The exact bytes remain retained with [the historical pure result](C:/Users/moham/Desktop/beryl/build/tablet-suite-receipts-pure-zd3otim3/result.json), SHA-256 `e4ed54c030eb802ce658916958b453d0036d81229b798b95df3cfc24761e293e`.

The actual first runtime attempt `q93fbdjk` returned five successful source suites, but that checker rejected its component order. Its [root receipt](<C:/Users/moham/Desktop/beryl/build/tablet existing suites & spaces-q93fbdjk/results.json>), SHA-256 `313a2f7543db60d2871fe650fe095ca306d0e1035d9bf684244e3712fb409e91`, remains **failure**. A [frozen passive audit](C:/Users/moham/Desktop/beryl/build/oct10-tablet-q93-passive-audit-49fee33660684438928e30ebcde9b9a3/result.json), SHA-256 `f0aa8b0957a4c4fba253b7ff490efa3510a7bdc7d0fa154107ea1b2d0dff5c81`, reproduced the order rejection using those exact checker bytes while all 868 physical/hash checks passed. That attempt is historical after the later compile-adapter change; its receipt was not rewritten.

The corrected checker uses policy `six-exact-distinct-components-preserve-native-order.v2`, SHA-256 `a4b043093a365c8dc9cd2d173eec5f2dbf4f9516b78384341dd492a7da3db60f` (56,332 bytes). Its [130-case pure result](C:/Users/moham/Desktop/beryl/build/tablet-suite-receipts-pure-d4734ebdf7634922906dc6eeba9d27ba/result.json), SHA-256 `816c6b3d0bf956cbc993061a110af0172867f1e4d7caea15c18b0a92fe6fdd7e`, passed. The original 125 IDs and positions are retained; the historical `negative.schema-order` ID now explicitly expects admission, with its revised contract recorded. Five appended fixtures cover the observed permutation, the exact captured field dump, repeated and replaced classes, and preservation of returned order. These are synthetic admission checks, not tablet assertions or new engine executions.

## 9. Verified actual checkpoint

The fresh runtime used the warning-aware [S1 candidate receipt](<C:/Users/moham/Desktop/beryl/build/tablet service & spaces-soii5z39/results.json>), SHA-256 `79211ad4191492442553d8e67f6d6aa9c823a2a193d2a3207ffaf9a94a8822f9`. It preserved the exact 86-file candidate and added only the trusted fixed identity handler, for 87 staged files. The original MESH self-test handler remained unchanged.

| Evidence | Exact result |
|---|---|
| [Root receipt](<C:/Users/moham/Desktop/beryl/build/tablet existing suites & spaces-wbymk7mx/results.json>) | Success; SHA-256 `b08fec466e261541542cdf44e38739e8e7216f94c057a25b83c1d20939f9dfb3` |
| [Runtime transport receipt](<C:/Users/moham/Desktop/beryl/build/tablet existing suites & spaces-wbymk7mx/engine-runtime.json>) | Success; SHA-256 `3fceecc86713bea8f4607569983cfe56f88361666d05311412cd9be3fd530b18` |
| [Expected identity](<C:/Users/moham/Desktop/beryl/build/tablet existing suites & spaces-wbymk7mx/runtime-expected.json>) | Exact prewritten `runtime-expected.json`; SHA-256 `7a5c434a2a751fdf7f74054dddb4d4b4bd79491eeaf817fd5bf463bc06e8a27c` |
| Execution | Five successful selections, 18 actual RPCs and 12 compiled identity responses; 26,640 ms paid runtime duration |
| Owned cleanup | Workbench PID 3612, start ticks `639272605435507791`; confirmed `owned_process_stopped`; no evidence or cleanup errors |
| [Headless compilation](<C:/Users/moham/Desktop/beryl/build/tablet existing suites & spaces-wbymk7mx/engine-compile.json>) | Zero errors and 19 retained warnings: five candidate warnings and fourteen base-game warnings |
| [Independent passive audit](C:/Users/moham/Desktop/beryl/build/oct10-tablet-suites-complete-audit-833f51b0d0e44937aad986370030ee09/result.json) | Success; 894 physical/hash checks, zero mismatches; SHA-256 `426d666110d0359ecd773978795683d22cf3588481ca9929192ab2bec73f9b2b` |

The actual configuration used Workbench `1.8.0.13`, executable SHA-256 `7dd36ca1f662b0c13669a4f2f7f10e3c461c2906b021e742272d64b3ab7e9798`; root runner `b5126d057af16efe08fb1371c69fdd6c8f9fdc3a4f8186d399244325ea4baab2`; transport `64ef05120d04e45c64f71165c589bef606b1243c8cc93f4f19c70c59e40004ac`; identity template `28b478997e11784de4af07404342072149704901d52e38204286198e9664d340`; corrected checker `a4b043093a365c8dc9cd2d173eec5f2dbf4f9516b78384341dd492a7da3db60f`; and warning-aware compile adapter `ea923399c2060123812a6ea205760372de0e2fff29071117e0cf58ed64877121`.

The passive audit reran the pinned checker, matched every raw reply to its retained parsed response, checked the exact staged tree, retained/original logs, source job and artifacts, source maps, live selected resources and original scripts, and current 25 tool-source files. All 107 compiler core inputs matched their established baseline. The private compiler `76aeaacfea6866e66e3020f983eaa22089d545ad0f3b60fedfd28c3d58972bd7`, public `build/beryl.exe` `bce2edd80b9a0d278b683ed790100dad0ae73322549522418dfc3ff94e455d99`, and public tool pointer `0f0f6f0909e3c0eac533412e8c0cd7a3c5f27e32743cbac25ebfe091583783ed` remained unchanged. Nothing was promoted to live MESH or the public installation.

The suites' structural and synchronous behavior passed. This does not establish leak-free operation, queued-callback teardown, a real tablet screen binding, native click delivery, generated tablet component execution, full lifecycle services, multiplayer, visual correctness, binary dependency closure or performance. The native tablet lifecycle gate in section 7 remains the next separate acceptance step.
