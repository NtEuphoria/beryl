# P5: post-restart UI lifecycle execution

Checkpoint: 2026-10-10 local time. **The isolated UI opening/frame/destruction
candidate passes complete Enfusion verification. Real player interaction and
release acceptance remain open.**

This packet supersedes the source-only and host-blocked status in the earlier
[UI candidate](P5_TABLET_UI_NATIVE_CANDIDATE.md). Failed attempts stay failed;
the successful receipt applies to its exact bytes and admitted workload.

## Actual successful execution

[Complete result](../../build/tablet-ui-native-cw72uq1x/results.json), SHA-256
`6392681dda2e7be009db352a9af0e3dbebff8d479a443e93c79f24ff60d32f68`:

| Observation | Result |
|---|---|
| Fixed host marker and confirmed exit | Success |
| Exact candidate compilation | Success |
| Public actions | All seven, in order |
| Actual UI openings | Three successful returns |
| Native initialization | Four milestones across two owners |
| Native frame observations | 2,022 before/after frame observations |
| Ordered trace | 5,723 rows; 809 service invocations; 37 queue observations |
| Natural progress | Both focus/reopen windows pass |
| Native destruction | Two callbacks, two pre-superclass and two post-superclass witnesses |
| Owned process cleanup | Confirmed stopped; no cleanup errors |
| Source/evidence checks | No final integrity or evidence errors |

The trace verifies the existing marker/telemetry order, binary32 accumulator
behavior within the documented text-encoding tolerance, persistence across
close/reopen, and close/screen-destroy/superclass ordering. It does not establish
bitwise floating-point identity, physical graphics-memory release, rendered
appearance, per-enqueue FIFO, handler retention through real clicks, multiplayer,
or actual equipment/holder behavior. The fixture deliberately omits the input
component and observes its actual absence. Successful opening may be degraded
when no map service is attached.

The eight-file package fingerprint for this candidate is
`c4ff162e45929fbc4329f6571d0c6073d702721d24967d375ebe1b488e41da86`.
The original trace limits remain unchanged: 2,048 frames, 12,288 rows,
8,192 service invocations, and 64 queue records. This one success does not
establish that every host-speed/session configuration fits those bounds.

## Confirmed harness repairs

1. **Enforce expression limit.** The first compiled candidate rejected two long
   Boolean expressions as `Formula too complex`. Their equivalent sequential
   early-return guards preserve null checks, operand order, and all compared
   fields. The failed [attempt](../../build/tablet-ui-native-djglv_gs/results.json)
   is retained. Independent source reconstruction verifies the change.
2. **Evidence lost during final serialization.** The repaired script compiled
   and opened real UI, but the original pretty JSON exceeded its 2 MiB cap and
   threw before publishing the receipt. Compact serialization alone was also
   insufficient: the next [failure capsule](../../build/tablet-ui-native-340i57bl/engine-runtime.json)
   records 6,931,373 full bytes and the prior stop/action failure, without claiming
   a complete trace.
3. **Bounded immutable evidence bundle.** The adapter now publishes a small
   unavailable header plus independently hashed, non-overwritten byte parts.
   Each part is at most 1 MiB; at most 16 parts and 16 MiB aggregate are admitted.
   The existing raw RPC cap remains 1 MiB and the header cap remains 2 MiB.
   UTF-8 parsing, exact partitions, hashes, file identity, path ownership, and
   original outcome are checked before full-record interpretation. The header
   cannot claim runtime success by itself. Oversize/write/serialization failures
   retain an explicitly incomplete failure capsule and bounded log references.
4. **Masked native failure.** Failed readiness/stop branches returned default
   phase and empty rows. The strict transport correctly rejected that reset,
   obscuring the native diagnostic. Those branches now run the existing plain
   capture/prefix checks and publish the validated prefix before generic fallback
   text. They preserve the first registry failure. No success checks, budgets,
   gameplay calls, or teardown getters were relaxed.

The earlier [fully retained failure](../../build/tablet-ui-native-0wv4tvs9/results.json)
proves all seven actions and 1,968 frames in its partial trace, followed by the
default empty stop failure. It does **not** identify the underlying lost-readiness
cause. Proximity to the frame ceiling is a hypothesis, not a confirmed cause.
The subsequent successful run cannot retroactively classify that failure.

## Supporting tests

These are separate evidence categories, not additional engine cases:

| Check | Evidence |
|---|---|
| Current adapter helpers | [97 actual inert PowerShell cases](../../build/tablet-ui-native-inert-df6ce0be90ec41de85d4333edfedd344/outer/result.json) |
| Bounded writer | [Seven actual PowerShell byte fixtures](../../build/tablet-ui-bundle-v2-actual-it6552xu/producer-result.json) |
| Independent bundle/fault checks | [28 cases](../../build/ui-bundle-hydration-tests-155465b56a464e22b68ede0803d204c7/result.json) |
| Driver diagnostics/source mutants | [87 cases](../../build/tablet-ui-native-runtime-source-sokdd5kn/result.json) |
| Preserved adapter functions | [36 originals unchanged; four helpers match tested bytes](../../build/ui-bundle-source-audit-d2f30f5fb39e408da79ea12e9fde87b1/result.json) |
| Earlier partial execution audit | [Independent retained-byte and partial-trace checks](../../build/ui-actual-prefix-audit-c2680d0e8f704ea08d9fa81e5a209bf9/result.json) |
| Complete lifecycle audit | [Independent source, byte, complete-oracle and terminal-fault checks](../../build/ui-actual-complete-audit-7068d1e8c59049858a0ba5d0071ddd48/result.json) |

The complete successful adapter record is 11,234,249 compact UTF-8 bytes across
11 parts. Its whole SHA-256 is
`67acef5f39af8d6bdb71bee463de28399bc99c838734f626b3dc14160a7f1b81`.
Byte hydration and semantic validation are recorded separately.

## Player interaction prerequisite

The isolated player-profile probe has progressed through distinct failures:

- Its first protected-registry traversal stopped at depth eight; a read-only
  inventory found an actual depth-nine tree. The repaired traversal has explicit
  depth/node/value/UTF-8 limits, with 12 actual mock-helper tests.
- A fresh forced INI was reset during native Qt-version migration; the log
  explicitly reported `unknown -> 6.8.3`, and the private-port keys disappeared.
- A seed containing the observed Qt version and migration marker retained those
  keys and produced a private 5783 listener owned by the launched process.
- That [attempt](../../build/tablet-owned-profile-run-2781upj7/results.json)
  then exposed stale lease-category guards copied from the 99-file UI fixture.
  It failed before any inventory RPC. Corrected guards require exactly
  100-addon plus six-pinned-input coverage; all
  [16 actual pure PowerShell guard tests](../../build/tablet-profile-lease-actual-w2usmek7/cases/results.json)
  pass.
- The [next actual inventory](../../build/tablet-owned-profile-run-duuklb4e/results.json)
  compiled, held all 106 leases and executed both expected RPCs. The native
  sentinel path and 149-byte exact-marker read passed. Workbench reported the
  exact owned **directory** with one terminal `/`; the checker incorrectly
  required the spelling without that separator. The new predicate accepts
  only the exact directory or that same spelling with one final `/`. It retains
  the raw observed path and keeps sentinel **file** identity exact. It does not
  canonicalize dot segments, fold case, accept another parent, or relax ownership.
  Independent validator/source fixtures pass
  [48 cases](../../build/tablet-profile-inventory-source-ubu7695_/result.json),
  and [64 wrapper cases](../../build/tablet-profile-root-wrapper-inert-ndlixaye/result.json).
  The exact seven PowerShell checker/helper definitions pass all
  [38 independently specified actual PowerShell cases](../../build/tablet-profile-check-native-actual-_w1lh8_2/result.json),
  including mixed numeric Booleans and directory/file path faults. This extraction
  test does not execute the adapter's process, engine or registry code.
  The [fresh native execution](../../build/tablet-owned-profile-run-a7x0cqwz/results.json),
  SHA-256 `44d6ed135a8b586da5ffac48aaffc00abecf940ab62c880c8784c2a8a079b9ac`,
  **passes** the namespace witness, both RPCs, 106 leases, protected-profile and
  registry preservation, and owned cleanup. Actual inventory confirms a game
  object, workspace and input manager, with no world, play mode, controller,
  controlled entity or gadget in this editor session. Input initialization and
  play remain unadmitted by this inventory-only experiment. The witness establishes
  Workbench's namespace; it must not be generalized to another game session or
  a later input-saving boundary without applicable verification.
  In the earlier failed result, player
  presence fields were defaults because the probe returned before inventory;
  they do not establish actual player absence.

A separate [host receipt failure](../../build/tablet-owned-profile-run-38s4ud59/results.json)
contains an exact host marker, empty stderr and confirmed exit in 0.441 seconds,
followed by Windows `WinError 5` while replacing the final mutable receipt.
The immutable final checkpoint survives. The attempt remains failed because
final evidence publication failed; it is not evidence of a PowerShell stall.
The file holder or cause of the denied replacement remains unknown.
An [isolated journal prototype](../../build/immutable-host-journal-prototype-b6b880c4148543f39768192bdc811f21/immutable_journal.py)
uses the existing `Hooks.journal` seam, numbered immutable checkpoints and a
single final CreateNew write, avoiding mutable replacement. Its
[20 file/fake-process tests](../../build/immutable-host-journal-tests-40f233bb91ba449196967e84777a0ec0/result.json)
pass, including final-write denial and collision failures. A
[fresh actual fixed-host probe with this hook](../../build/immutable-host-journal-actual-c9a8n_hq/result.json),
SHA-256 `3daa1bc1f72f5aa9df5684e0fb932db8377aecdef57a22c69c76fe7413ffb09b`,
also passes the exact marker, empty stderr, confirmed exit and final receipt
identity. This verifies fixed-host integration only; it does not eliminate all
file-write failure modes or identify the cause of the older denial. The base
utility and installed tools remain unchanged.

Private listener appearance is not native profile-path confirmation. Input
initialization, player spawning, equipment, activation, local-owner behavior,
and destruction after player handover remain unexecuted until their actual
prerequisites pass. Do not simulate them with manually invoked gadget callbacks.

### Resource inspection and a premature native accessor

The separate [v2 resource attempt](../../build/tablet-player-resource-inspection-run-260pn2ta/results.json),
SHA-256 `f710e9d6360d8983bbaf5371bbc3fab72e4a33e5123138741fd82c1ded296fde`,
passes the revised fixed-host journal and compilation but fails native inventory.
The retained [crash log](../../build/tablet-owned-profile-preparation-meuo0em6/tablet-native-logs/session/crash.log)
reports an access violation at `BerylTabletOwnedProfile.c:135`. That exact source
line calls `GetGame().GetSystemsConfig()` in an editor session with no loaded
world. The preceding nonnull `GetGame()` check did not establish applicability
of this native accessor. Declaration existence and successful compilation were
insufficient; the engine's internal invalid-read cause is not established.

The completed `GetLoadedProjects` reply is retained. The inventory RPC has no
response, and the fixed `GetResourceInfo` request never ran. Protected-profile
and registry comparisons remain unchanged, and owned cleanup observes that the
engine already exited. The transport's generic timeout explanation about modal
dialogs is not the diagnosis: the actual retained native crash establishes this
attempt's failure. Source-only audits remain source evidence, even when they pass.

The bounded repair removes premature systems/editor accessors from this
inventory. It does not invent a guard that claims those accessors safe. A new
candidate must establish the actual game lifecycle and each accessor's admitted
context separately before using it in play/equipment tests.

The [v3 native attempt](../../build/tablet-player-resource-inspection-run-wq3k4f6i/results.json),
SHA-256 `d4420bdcc78d6af5ab3e3ea855113f1ede27a97fa504b3baf799c18ea6e37340`,
passes the fixed-host probe, compilation, namespace inventory, all three RPC
transports, preservation checks and owned cleanup. Its actual settings root is
`GameProject`, with 12 enumerated variable names/types. These are observed
metadata, not guessed nested configuration values. The third response reports
`Resource not found` for the GUID-prefixed default-controller resource from the
installed project. Successful RPC transport does not establish a found resource.
An [independent audit](../../build/resource-v3-actual-independent-audit-glut02ns/result.json)
passes 242 retained-evidence checks while preserving this negative outcome.

The pure PowerShell checker fixture initially exceeded its unchanged 128 KiB
input limit before executing any helper. Compact JSON serialization reduces the
same 46 parsed cases from 134,079 to 106,649 bytes; helper definitions and the
input limit remain unchanged. All
[46 actual PowerShell checker cases](../../build/tablet-resource-v3-powershell-actual-ih68z6ka/result.json)
then pass with empty stderr. The failed fixture remains a separate failed attempt.

The [v4 native attempt](../../build/tablet-player-resource-inspection-run-dw98upx9/results.json),
SHA-256 `72fcf5f6af9226be40180c7b0acec237f8852a3c1761d2e6124db40511127c89`,
tests only the alternative fixed relative path
`Prefabs/Characters/Core/DefaultPlayerController.et`. Host readiness, compilation,
inventory, all three transports, preservation and cleanup pass again. The actual
resource response still has status `1`, empty resource identity/path, and
`Resource not found`. The hypothesis that removing the GUID alone resolves this
lookup is therefore unsupported. Neither attempt admits a player/controller
fixture. Further investigation must distinguish resource-info lookup support
from the resource loader and actual game configuration before choosing a spawn
path; repeating the same lookup is not acceptance evidence.
The [independent v4 audit](../../build/resource-v4-actual-independent-audit-43her0qs/result.json)
passes 242 retained-evidence checks, including the negative response, 106 lease
releases and protected-profile preservation.

The [v5 fixed GUID query](../../build/tablet-player-resource-inspection-run-tays692b/results.json),
SHA-256 `c8cc12ffbc9de7db2b982f4348caab997444b7c1516baa7f14885fbd884b2f32`,
uses Bohemia's installed `CheckGUID` handler with exactly
`matName="6E2BB64764E3BE9B"`. All three transports, host readiness, compilation,
fresh namespace witness, preservation and owned cleanup pass. Its actual raw
reply is `{"exists":1}`. The retained installed handler calls
`Workbench.GetResourceName` and compares its result with the input GUID. This
positive handler signal distinguishes it from the earlier resource-info lookup
failures, but does not expose the resolved name, prove `Resource.Load` success,
validate a controller class, or establish a real player. No new Game/native
getter was added. The root's [63 source/fault checks](../../build/tablet-resource-source-test-6mqs6pgs/result.json)
and actual PowerShell parser check are separate from this engine execution.
The [independent v5 execution audit](../../build/resource-v5-actual-independent-audit-41e9_zlg/result.json)
passes 242 retained-evidence checks and preserves the limited handler interpretation.

### Actual Game callback profile witness

The [fresh neutral Game execution](../../build/tablet-owned-profile-run-dx9pm4wi/results.json),
SHA-256 `8ea4da4ffa9b2cb69812d56c88f6c6b37ae39ddad2846c07af247b990cc94967`,
**passes** compilation and the complete 12-RPC load/status/play/spawn/stop
sequence. The eight-file addon has 14 leased inputs. One native prefab spawn
delivers one natural `OnPostInit`; its owner and world match the running Game.
That callback observes the explicit profile argument, opens the unique
`$profile:` sentinel once, reads the exact 149-character token/source marker once,
and returns from `Close`. No callback is manually invoked. The observer contains
no tablet, input, controller or player creation.

The v2 source splits 22 completeness predicates and nine spawn predicates into
ordered guards to avoid the established Enforce expression-complexity pitfall.
This was a preventive source change; v1 was not engine-compiled and is not
recorded as a failed compile. The
[independent guard audit](../../build/game-v2-guard-equivalence-audit-16orhz_x/result.json)
passes 116 source/order checks, and the root's
[100 checker/source fault cases](../../build/game-profile-validator-source-faults-cwbsliqz/result.json)
pass independently of the actual engine run.

Owned process cleanup is confirmed. Protected Workbench profile/registry checks
pass. The additional [passive operator Game-profile comparison](../../build/operator-game-profile-preservation-gpusg7uu/result.json)
finds all 1,293 files, directory names and 1,234,504 content bytes unchanged across
the observed interval. This comparison detects changes; it does not confine
native writes or prove an input-binding save destination.

This closes the bounded **Game callback token-read** prerequisite. It does not
provide a Game absolute-path resolver, verify `InputBinding.Save`, initialize
tablet input, create a player, or prove physical resource release. Stop fields
retain scalar context captured before the mode switch; they must not be read as
a claim that the prior Game world remains alive after stopping. Actual running
controller/character inventory and the normal player creation path are next.
The [independent actual Game audit](../../build/game-v2-actual-independent-audit-8d7bplbk/result.json),
SHA-256 `47a153859cc5996cf127d7ea9923510262005585faa5b2f90975f61b99f6086f`,
passes 110 retained-evidence checks. Its initial audit harness used an incorrect
guessed session key and failed; that attempt is retained separately. Correcting
the checker to the recorded PID/start/reuse identity did not rerun or rewrite the
successful native fixture.

The [subsequent running-Game context inventory](../../build/tablet-owned-profile-run-d5eaktg6/results.json),
SHA-256 `949464f5cf45b8dce665f72373682a48afb77412fc5a59131d6b3810a0e410b4`,
passes the same lifecycle and actually observes its player context after the
token read. No player controller, controlled entity or `ChimeraCharacter` is
present. These are observed absences, not default response fields. The
[independent actual audit](../../build/game-v3-actual-independent-audit-hfbavsdd/result.json)
passes 111 checks. A [fresh passive Game-profile comparison](../../build/operator-game-profile-preservation-f0u_425z/result.json)
remains unchanged and is separate from the native receipt.

This explains the current fixture limitation: running an empty world through
Workbench's `SwitchToGameMode(debugMode, fullScreen)` has not created a player.
Those arguments do not select camera-player spawning. The installed
`Game.GetWorldEditor()` contract explicitly requires `InPlayMode()` to be false;
it must not be queried from the running callback. The next receiver observation
belongs to the verified loaded **editor** world before play. That context has a
nonnull Workbench editor world and no Game world; requiring a Game world there
would invent a precondition and incorrectly block the documented editor domain.

## Isolated native UI construction repair

Actual successful lifecycle logs still report labels with ButtonWidgetSlot being
passed to FrameSlot operations, plus rejected additional button children.
This is an existing captured Chrome construction defect. A reviewed isolated
repair creates one ButtonSlot-stretched content frame per button and places the
existing labels inside it. The
[repaired native candidate](../../build/tablet-ui-native-0vz39ha1/results.json),
SHA-256 `a167978822a1ebf8c5e95febfd2b66862383e30d48f7cdee5595482029b109dc`,
passes compilation and the complete seven-action lifecycle oracle: 5,714 rows,
2,010 actual frame observations and both native destruction/superclass sets.
Retained, independently hash-checked native logs contain **zero** invalid-slot,
parent-capacity or other `GUI (E)` diagnostics. Earlier counts of 414 slot and
180 parent messages are logged occurrences across overlapping streams, not
unique errors.

The [independent native audit](../../build/ui-isolated-chrome-native-independent-audit-2_dgtll2/result.json),
SHA-256 `bb26a2ed5e1b0b8d8cb6e3249fde6316ddea176186130f316bbeefcb4749ddf1`,
confirms that only `MakeLabel` and `MakeButton` changed and that the transform
reverses byte-for-byte to the captured original. The
[28 construction/source fault tests](../../build/tablet-chrome-content-source-faults-s0mwryxg/result.json)
and [38 raw-log checker tests](../../build/tablet-ui-gui-log-source-faults-x7v3zu1k/result.json)
are separate pure checks. Native click delivery, rendered geometry, physical
input and visual acceptance remain unverified. A nonzero UI root measurement
is not evidence of correct appearance.

The optional `--repair-widget-slots` experiment changes only the captured
candidate. It preserves the live MESH sources. It must not be presented as
unchanged hierarchy parity with the original invalid construction.

## Preservation and next gates

[Fresh passive preservation](../../build/tablet-post-restart-preservation-dw217118/result.json)
matches all 107 recorded compiler/runtime sources, five installation artifacts,
and 25 private tool payloads. Live MESH and installed output were not promoted.

Next: establish the actual player/gadget fixture and input persistence behavior
within the verified owned Game session, then run dedicated-client, visual, physical-lifetime,
AI authoring, and rollback acceptance. This is a useful exact-candidate checkpoint,
not a complete-tablet or performance release.
