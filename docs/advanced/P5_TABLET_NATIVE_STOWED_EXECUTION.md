# P5: native tablet initialization and STOWED frames

Updated 2026-10-10. This experimental checkpoint follows the
[native lifecycle admission packet](P5_TABLET_NATIVE_LIFECYCLE_ADMISSION.md).
It is separate from the five preserved structural tablet suites.

## Current checkpoint: the bounded N0 runtime passes

The fresh [complete runtime receipt](<../../build/tablet native runtime & spaces-s1ajq0z6/results.json>)
has SHA-256 `c83c6a0080ecedd80def17a083034e5a8af0a1720b11d328677b96ddf0a0d05d`.
It passes all five predeclared native initialization, STOWED-frame and independent
state cases. Each of the two owners received 64 complete before/after frame pairs.
The final 260-row ordered trace has checksum 993937. Its stop completion is freshly
observed in edit mode, with no subsequent owner/state dereference by the scanner.
This closes the bounded runtime gate for these exact bytes and this profile.
The [independent terminal audit](../../build/oct10-native-n0-success-audit-9p5o_0a5/result.json)
passes 40 named, grouped obligations, with no issues. Its SHA-256 is
`abde8317f2668c10ace10bef5dc76bf1c6d2fa4c753ae4d00e6a6227fd487355`.
It independently reconstructs all raw trace rows and their checksum, checks
transport/codec/stage/session/stop linkage and all 98 lease entries, and rehashes
602 distinct physical input/evidence files. The helper's printed count of 603
also includes readback of the newly written audit receipt itself. The physical-file
count is separate from the named
obligation count. It also verifies the 107 compiler/runtime files and private/
active compiler/tool identities remain unchanged. This audit starts no compiler,
PowerShell host or engine, and makes no live process query.

Compilation took 8.2 seconds and reports zero admitted errors and 19 warnings.
The runtime adapter records 24,317 milliseconds, ten actual RPCs, 32 session
identity observations and eleven listener observations. Owned engine cleanup and
both direct PowerShell host exits are confirmed; cleanup and evidence-error
collections are empty. These are execution facts, not a language-performance
measurement or a general lifecycle/descendant cleanup claim.

The successful candidate holds all 98 read leases during the capture window,
retains a full input check while they are held, records eight bounded namespace
checks, releases every lease and repeats full byte checks afterward. The existing
200-frame-per-owner and 1,024-row limits, ordinary production tablet callbacks,
fixed launch arguments and five-case trace contract are unchanged. The earlier
failed pacing and startup attempts below remain failed historical evidence.

The final [startup adapter](../../scripts/tablet-native-leased-startup-engine.ps1),
SHA-256 `a7af515454f543babde755e9fb19fe4e363acea93edd2240fab76f492cb38306`,
retains PID, creation ticks, module presence and raw/normalized image before
comparison. Direct native getter calls surface query errors. An absent image can
remain pending for at most 64 observations under the original deadlines; a foreign
image or changed identity fails immediately. The actual successful startup had a
matching image at its **first** observation, with a 43-millisecond identity window.
It did not exercise the pending branch and does not establish why `fea8zh4c` failed.

The [final pure startup gate](../../build/tablet-native-startup-checkers-3dda2404460642b38bafbc4d02a7f3d4/outer/result.json)
passes 33 scripted-process cases. The first 32-case attempt remains failed:
PowerShell suppressed two scripted `Path` getter exceptions into null values,
leading to timeout. The repaired fixture and adapter use direct getter methods;
the missing-module case is separately covered. These tests launch no engine.
The [frozen runner's independent validator gate](../../build/oct10-startup-runner-inert-170fc980082843afa0e21d715ca1a15a/result.json)
passes 91 Python-only cases for typed startup ledgers, identity/timestamp domains,
ordering, image admission and incomplete evidence. Those are synthetic outcomes,
separate from the five actual engine cases.

## Completed source and compilation gates

The default [preparer](../../scripts/prepare-tablet-native-callbacks.py) executed
successfully against the exact warning-aware S1 candidate. Its
[source receipt](<../../build/tablet native preparation & spaces-flxq8l36/results.json>)
has SHA-256 `4f5250df9a163cb91c362345c848d997d7fb9c096a654d0805052b015cd4e424`.
There are 92 staged files: the 86-file source candidate with a distinct addon
identity and six new trusted fixture files. The production tablet adapter,
generated Beryl logic, original scripts and selected resources are unchanged.
The exact original implementation remains outside production discovery as a
reference input; it is not renamed or executed.

The [independent source audit](../../build/oct10-tablet-native-preparation-audit-un9pyiru/result.json)
passed 1,681 checks. It covers the exact staged tree, 85 preserved prior files,
287 retained payload files, artifact/job/maps/log copies, current input identities,
107 unchanged compiler/runtime files and unchanged private/active installation.
Source preparation itself neither generates code nor starts a compiler or engine.

A separate copied 92-file candidate then passed
[owned headless compilation](<../../build/tablet native compile & spaces-fp_ukpx_/results.json>),
SHA-256 `80c2b99ca64ba00e481239540f4c39c95fd20e01593e5802f60ce52894e42321`.
The recorded compile duration is 9.3 seconds, with zero admitted script errors
and 19 warnings: five preserved MESH warnings and fourteen base-script warnings.
The wrapper host exited with code zero and confirmed cleanup. Three raw engine
logs are retained. The [separate terminal audit](../../build/oct10-tablet-native-compile-audit-76dqp1_k/result.json)
passed 534 checks. These results establish compilation, not native callbacks,
resource loadability, services or gameplay.

The source preparation's independent pure gate passed 59 cases. Its final
source receipt is retained under `build/tablet native preparation inert & spaces-gydcwyex/result.json`.
The [trace decoder](../../scripts/verify-tablet-native-trace.py) and
[pure receipt gate](../../scripts/verify-tablet-native-trace-receipts.py) separately
passed 196 cases, including ordering, identity, incomplete pairs, frame bounds,
numeric-text and bounded-file-reader faults. Those fixtures are synthetic;
their counts must never be presented as executed engine callbacks.

## Admitted runtime experiment

The first composition contains only a derived observer of the unchanged
`SPK_TabletComponent`. It excludes input, gadget, inventory, editable-entity,
mesh and replication components. This deliberate composition is narrower than
the six-component production prefab. Initialization cannot reach the excluded
input component's user-keybinding registration path.

A separate trusted runtime package adds one fixed Workbench handler, making a
93-file candidate. It has five actions: load, status, play, spawn and stop.
Two owners are spawned through the engine factory into the freshly observed
`Game.GetWorld()`. The engine delivers post-init and frame callbacks; each
observer override calls the unchanged production superclass exactly once in its
source. No component constructor or callback is invoked manually by the RPC.

The admitted cases are:

- `native.init.1` and `native.init.2`.
- `native.stowed-frames.1` and `native.stowed-frames.2`.
- `native.independent-state`.

Each owner must produce at least three and no more than 200 complete native
frame pairs. Before/after observations include owner identity, nonnull Game and
owner worlds, state identity, STOWED mode, accumulator, timestep, event mask and
absent UI/screen services. State independence is unavailable until both owners
have been claimed. Two owners at the maximum produce 804 rows, within the
1,024-row observer budget.

The wire has 18 ASCII columns: a zero-based sequence plus the 17 observer fields.
The checksum covers the exact raw row bytes and newline, rather than a floating
point JSON reserialization. Numeric text is rounded finite engine output; it
does not prove binary32 bit identity or distinguish signed zero.

The first complete frame snapshot only permits requesting stop. Final success
requires fresh native observations of edit mode outside game/play, then a
complete scalar trace and a repeated failure/cap/prefix check. No retained owner
or engine-state reference is dereferenced after leaving play. An earlier complete
snapshot cannot conceal a later frame-budget failure.

The separate [PowerShell adapter](../../scripts/tablet-native-engine.ps1) pins the
93-input manifest and engine/tool identities around every RPC. It starts a hidden
owned process, verifies the listener belongs to that process, permits no unrelated
addon/session, retains raw replies/logs, and confirms owned cleanup. Stage, RPC,
overall and cleanup budgets remain separate. Native OS/bridge calls are observed
against deadlines; they are not claimed to support hard cancellation.

## Retained harness defects

The first actual 93-file runtime attempt
[compiled, loaded and entered play, then failed its frame budget](<../../build/tablet native runtime & spaces-5hnsg1gj/results.json>),
SHA-256 `2d84befe4dbba25ecd93c3170558b337cce1c91b9b3daf72bfe31c498a74f37a`.
The returned failure was `Native tablet frame observation budget exhausted`.
The frozen observer sets this failure when at least one owner receives its 201st
native frame callback. Failed response counts are not evidence of zero callbacks:
the scanner exits before counting rows when that failure is present. No complete
trace or stop receipt exists for this attempt.

The spawn request began at 19,215 ms; its transport returned by the recorded
after-identity check at 19,235 ms. The full request and evidence work took 402 ms.
The next status request began at 20,115 ms and returned its explicit failure by
20,134 ms. Input/engine hashing, evidence checks and the poll delay therefore
allowed roughly 880 ms of live engine work between these observations. At the
observed callback pace, that gap was incompatible with the fixed 200-frame budget.
This is a harness scheduling defect; the receipt does not establish a tablet
logic failure. PowerShell completed with exit code one, retained raw replies/logs,
and confirmed that its owned Workbench process had stopped.

A separate [bounded adapter](../../scripts/tablet-native-bounded-engine.ps1)
requests `-maxFPS 30` for its owned diagnostic process. The pinned installed
`Page_CLI.html` documents this public common parameter. The adapter retains
`-forceUpdate`, the original observer, every callback/superclass call, the
200-frame failure cap and all identity, deadline and cleanup checks. It does not
change user settings or live MESH. A requested limiter is not a measured frame
rate: a fresh complete trace must establish that the actual trial stayed within
its bounds. No performance claim follows from this scheduling control.

That limiter control was also executed and
[failed the same native observation cap](<../../build/tablet native runtime & spaces-e7uej0ix/results.json>),
SHA-256 `eced7892e7d7963b65132fd98ca09daf5738608391d603e621d7f5092580aa35`.
The console and exact argv confirm `-forceUpdate -maxFPS 30` was supplied;
they do not establish a 30 Hz frame-callback limit. The first status request
began 1,089 ms after spawn. Compilation again returned zero admitted errors
and 19 warnings, and owned cleanup was confirmed. Independent terminal audits
passed 1,081 and 246 checks while preserving the failed outcome.

The [bounded pure checker gate](../../scripts/verify-tablet-native-bounded-checkers.py)
passed 291 executed PowerShell cases: 277 existing checker positions with the
fixed-argument positive revised, plus 14 explicitly synthetic returned-vector
faults. Its independent audit passed 353 checks. These tests validate transport
admission, not engine pacing. A root command with a mistyped expected host hash
was rejected before launch and retained separately.

A third [ordinary-scheduling control](../../scripts/tablet-native-ordinary-engine.ps1)
removes only `-forceUpdate` and keeps the requested limiter. Primary CLI line 157
documents forced render/update while the window lacks focus; it does not promise
a particular callback frequency. This control therefore tests a scheduling
hypothesis. Hidden-window progress may be unavailable. Its original callback,
trace, deadline, cleanup and 200-frame failure requirements remain unchanged.

That third control also [failed the same cap](<../../build/tablet native runtime & spaces-w07_qfs9/results.json>),
SHA-256 `3318889c8596885855e3dcac86ae60131e180177fc07e6ebffa8dd4bcc17d60b`.
It compiled with zero admitted errors and 19 warnings, returned its failure and
confirmed owned cleanup. Its independent terminal audit passed 1,081 checks.
Removing `-forceUpdate` did not establish the callback pacing needed by this
fixture. The separately executed ordinary-argument checker gate passed 291 cases;
its independent audit passed 354 checks. Those checker cases do not validate
engine scheduling.

A fourth [diagnostic trial](<../../build/tablet native runtime & spaces-159zkrbw/results.json>),
SHA-256 `388b01e195df3c681966a5eb71dc172d501e7db1a23eedc994c34d2272019d38`,
preserved the original launch arguments, observer and failure cap. Its separate
trusted RPC delta scans at most 1,024 existing scalar rows only after failure,
without invoking or suppressing a callback, changing state or dereferencing
owners. It reported 804 rows, no null rows and 200 recorded `frame.after`
observations per owner, each with last ordinal 200. These aggregate counters do
not independently validate every before/after pair or establish a complete trace.
Each owner's recorded binary32 timestep sum printed as `0.520623`; the reported
application FPS average was `515.212`. Timestep sums are rounded input-time
quantities, not wallclock durations. The installed System API documents its FPS
and frame-time getters as averages of ten application frames, not an EOnFrame
pacing contract. The diagnostic supports the harness-latency hypothesis without
claiming a precise wallclock callback rate.

The diagnostic remained a failure with zero accepted cases and no complete trace
or observed stop. Its independent terminal audit passed 1,081 checks; its source
audit passed 21 checks, including ten deliberate diagnostic-source mutations.
Console and script logs retain the same diagnostic marker. Neither diagnostic
statistics nor integrity checks turn the failed run into successful execution.

The [leased harness](../../scripts/tablet-native-leased-engine.ps1) replaces
repeated byte hashing during bounded live capture with Windows read leases. It
pins 98 files: 93 addon inputs, its adapter and manifest, two integration scripts
and the engine executable. The file streams use Open/Read/FileShare.Read; each
file is hashed while held. Acquisition completes before the original full hash
guard runs again with all handles held. Fast checks retain exact namespace,
pathname/held-stream lengths, owned session, transport, token, timeout and
observation guards. Only spawn/stop polling changes to one millisecond. Release
follows the observed stop boundary, then full hashing resumes. Partial acquisition
and failed release cannot select an unleased fallback. The observer, native
callbacks, row contract and 200-frame cap are unchanged.

The [lease checker](../../scripts/verify-tablet-native-leased-checkers.py) passed
314 registered PowerShell cases in a fresh
[owned-file gate](../../build/tablet-native-leased-checkers-0cf0151a592a491e84a41a8c74b08009/outer/result.json):
the original 277 transport checks and 37 bounded lease/helper cases. Real owned
files test blocked writing, deletion and renaming, restored access after release,
partial acquisition, stale bytes, namespace faults, limits and release failures.
The optional symlink-creation probe reported unavailable because the process lacks
the required privilege; its source guard did not execute. No privilege or policy
was changed. This gate starts no compiler, engine or adapter entry point.

The preceding [failed lease gate](../../build/tablet-native-leased-checkers-f96d81859e8440298743bf3ee10c67ff/outer/result.json)
retains 305 passing and nine failing positions. Ten fixtures wrapped an already
array-valued return with a second array; nine failed before their intended guard,
and the extra-field case reached the wrong count guard. The fixture-only repair
consumes the direct return and checks its initial count. The exact prior driver,
generated script, source and failed receipt remain preserved; the live adapter
did not change. Synthetic Python receipt checks and an independent 32-case
wrapper admission audit are distinct from file-sharing and engine execution.

At this point in the investigation, the lease repair still required its own fresh
complete engine receipt. The current checkpoint above subsequently supplies it.
Neither the pure checker gate nor the failed pacing trials themselves close N0.

Two subsequent startup attempts are retained separately. The
[sandboxed trial](<../../build/tablet native runtime & spaces-weijzymo/results.json>)
returned unavailable at compilation: the installed plugin recorded exit code -1
without an associated new log directory. That result cannot establish whether
engine initialization or script compilation executed. Its receipt hash is
`f95c102104a5d3069c36e4e4e9a9601f2f43661aad0ce5c2f02e717226a9ec15`.

The [unrestricted trial](<../../build/tablet native runtime & spaces-fea8zh4c/results.json>),
SHA-256 `2a6c49af85cee483223f8a28a4e90bbb9de1620aed77d50455c872bb50bf3c2e`,
compiled successfully in 9.2 seconds with zero admitted errors and 19 warnings.
Its runtime then failed the initial executable-path guard before any RPC or lease
acquisition. The receipt records PID 7644 but does not retain the path that failed
comparison or the locally captured creation ticks. It therefore cannot distinguish
a genuinely different image from unavailable module information during startup.
The PowerShell cleanup explicitly declined to stop a process whose full identity
was unverified. Outer job cleanup is separate; the original engine receipt lacks
confirmed engine exit. A later read-only OS snapshot found a signaled process
object at that PID, but lacks the original creation ticks needed to prove identity.
No unverified PID was signaled by that diagnostic.

The subsequently implemented additive startup repair retains actual path and
creation-tick
observations before comparing them. Empty initial module information may remain
pending only under explicit bounds and the same process/PID/ticks; a nonempty
foreign path must fail immediately. Query errors and confirmed early exit remain
unavailable, not accepted identity. The successful trial observed a matching image
immediately; unavailable startup module information remains a hypothesis for the
earlier failure, and does not explain the historical OS stall.

The first compile wrapper attempt
[stopped before any process launch](<../../build/tablet native compile & spaces-uqdkol7g/results.json>).
It applied a staged-tree helper to the full retained evidence tree and compared
directory enumeration order. Windows `Path` sorting and string-path sorting
differed at `source-inputs/mesh/scripts` versus `source-inputs/mesh-resources`.
Every file hash and exact directory membership matched. A fresh wrapper checks
the full retained tree's membership and hashes; staged-addon checks remain intact.
The failed receipt and its original wrapper are preserved.

The independent source audit also retained failed audit-only attempts. Comparing
Windows path-stat and handle-fstat executable permission bits produced a false
identity discrepancy; all native volume/inode/link/size/mtime/attribute fields
and the executable hash agreed. The corrected audit compares file type and the
native identity tuple, while independently rejecting links and reparse points.
A mistaken baseline row-count assumption was likewise diagnosed separately.
None of those attempts changes the original source or compilation receipts.

Before runtime execution, review found a one-based row encoder versus the
decoder's zero-based sequence contract. The new trusted RPC was corrected before
engine launch. This is a recorder defect, not a Beryl language semantic change.

## Remaining gates

Native N0 execution and independent terminal validation pass for the current
exact receipt. A compiled observer alone did not close N0.

The successful N0 result does not establish original/generated engine parity,
nonzero-state reset behavior, the number of mask-setting calls, Focus/Unfocus,
real UI or screen services, player/gadget ownership, physical clicks, queued
callback lifetime, native deletion, profile isolation, multiplayer, visual
acceptance or promotion. Strong fixture references are deliberately bounded and
are not a general cleanup proof. The next work follows the remaining N1–N5
admissions rather than borrowing the generic replicated fixture's deletion policy.
The [real-service admission packet](P5_TABLET_REAL_SERVICES_ADMISSION.md) defines
the subsequent public-state/screen and UI/focused-frame experiments separately.

Live MESH and the active compiler/tool installation remain unchanged. The
historical operating-system PowerShell stall's exact cause remains unknown;
successful current jobs do not retroactively diagnose it.
