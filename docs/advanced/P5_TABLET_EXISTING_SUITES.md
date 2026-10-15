# P5 tablet: preserved-suite candidate and execution gates

Checkpoint: 2026-10-10. This packet separates source capture, script compilation,
existing suite execution, and full tablet lifecycle acceptance. None implies the
next. The live MESH installation and active compiler remain protected inputs.

## S1 — Resource and handler compilation, completed

The explicit `tablet-suites-v1` profile extends the existing isolated source
candidate. It admits exactly 28 resource files, their 13 distinct metadata
identities, and the two original Workbench handlers. All 56 original scripts are
retained; the production tablet alone is replaced by the trusted adapter calling
the Beryl lifecycle implementation. The generated logic and project descriptor
bring the staged total to 86 files. There is exactly one production tablet class.

The copied resources total 12,655,544 bytes. The selection includes the tablet,
MESH core, arsenal configuration and carried BOLT dependencies. The flying BOLT
branch is outside this selection. Eighteen base configuration references remain
unresolved by the lexical source audit. Binary embedded dependencies, native
registration, platform availability and consumer lifetime are not closed by this
capture or script compilation.

The installed profile is
`packages/sparkos/tablet-service-prototype/tablet-suites.v1.json`, SHA-256
`22a8a3b18f93599765e61b34c7c9cd3b13a011d4f8c4e8649b4e24b9d6531514`.
The verifier revision is SHA-256
`6f05262452a21705e9e14ff9c4d697481480b0568b47c84d3e9f0d8708f54ac0`.
The original checked-resource helper is reused; the verifier executes its checked
bytes and checks source, retained and staged inputs at observed boundaries.

| Gate | Receipt | Result and scope |
|---|---|---|
| Independent admission | `build/tablet-suite-admission-inert-tttb73h9/result.json` | 132/132 Python-only cases; no compiler or engine launched |
| Default compatibility | `build/tablet service & spaces-psbau6hd/results.json` | Original companion bytes, 56 staged files, no resource/handler extension; source generation only |
| Selected candidate | `build/tablet service & spaces-j_t2z5u0/results.json` | Exact 86-file candidate script compilation passed; 140 retained inputs |
| Independent terminal audit | `build/oct10-tablet-suite-terminal-audit-27c4aaf7f3d2445182602d72feb6675c.json` | 88 checks; exact artifacts, source maps, jobs, logs and protected installation identities matched |

The selected result has SHA-256
`1ab81b4e6a44272d79a676f2fa50789e2ed94198867404bd20a052776aa20a90`.
It used private compiler
`76aeaacfea6866e66e3020f983eaa22089d545ad0f3b60fedfd28c3d58972bd7`
and Workbench 1.8.0.13 executable
`7dd36ca1f662b0c13669a4f2f7f10e3c461c2906b021e742272d64b3ab7e9798`.
The isolated addon is `BerylTabletSuitesPrototype`, GUID `BE71551720261010`,
with only base dependency `58D0FB3206B6F859`. No installation or promotion ran.

### Diagnostic interpretation

The plugin reported zero admitted compilation errors and zero counted warnings
in 7.2 seconds. This revision of Beryl did not pass `-IncludeWarnings`, and the
installed parser excludes warnings by default. The raw console contains 19
obsolete-API warnings: five in preserved candidate scripts and fourteen in base
scripts. The raw error log also has a shutdown resource-leak marker and 24
resource rows excluded by that parser. These are retained diagnostics, not a
tablet-specific leak diagnosis or evidence of leak-free execution. Historical
receipts keep their original counters and filters.

The source adapter's supported `-IncludeWarnings` forwarding is now repaired.
Its new SHA-256 is
`ea923399c2060123812a6ea205760372de0e2fff29071117e0cf58ed64877121`.
Fresh S1 `build/tablet service & spaces-soii5z39/results.json`, SHA-256
`79211ad4191492442553d8e67f6d6aa9c823a2a193d2a3207ffaf9a94a8822f9`,
compiled successfully in 8.1 seconds with zero admitted errors and 19 warnings.
The 19 retained warning diagnostics match the raw console: five candidate and
fourteen base. Its 86 staged files are byte-identical to the earlier candidate;
all 140 retained inputs were checked by the independent peer review. The tool
bundle and receipt are new identities. Old source-tool receipts are not current
verification after this adapter change.

The installed parser still suppresses the resource-leak block, and the plugin
does not forward its suppression count. `Summary="Build clean."` continues to
mean zero admitted errors; it does not mean warning-free or leak-free. This
repair changes the source adapter, not the active installation or MESH scripts.

### Declared requests

All five selections target the existing `SPK_MeshSelfTest` handler:

| Order | Suite | Argument |
|---|---|---|
| 1 | `ui` | Empty string |
| 2 | `screen` | Empty string |
| 3 | `actions` | Empty string |
| 4 | `clicks` | Empty string |
| 5 | `schema` | `{B37EEB64E149CBAD}Prefabs/SPK_Tablet.et` |

The S1 receipt explicitly says `declared_not_executed`, with zero executions.
Handler compilation is not a successful suite result.

## S2 — Bounded execution runner, completed for the five preserved suites

The runner derives a fresh isolated candidate from S1's exact bytes and adds
one trusted identity handler. Its 87 input files receive a new manifest, fresh
compilation and their own receipts. S1's immutable artifact is not modified.
The identity response contains compiled literal token, profile and source
fingerprint; it does not echo input values as evidence of the loaded code.

The transport uses the existing Workbench RPC bridge. One owner launches and
stops the job's engine process, checks its executable/start identity and TCP
listener ownership, holds the shared session mutex, and rejects unrelated
sessions. Source and manifest checks run around operations. Fixed budgets are
30 seconds for startup, eight seconds per RPC, 180 seconds overall and five
seconds for cleanup. Timeouts, cancellation, missing results and stale sources
remain failures or unavailable capabilities, never successful suite responses.

The exact RPC ledger is one loaded-project query, one initial identity query,
five groups of before-identity/suite/after-identity, and one final identity query:
18 calls total. Each fixed request executes once, without retrying a failed test.
Response admission checks exact typed fields, raw/decoded agreement, ordering,
candidate identity and the complete expected suite set.

The requested context is the job's own editor session with no last-resource
opening and no world-load argument. There is no opener, play, spawn, save or
manually invoked tablet lifecycle callback. `ui`, `screen` and `clicks` need a
game workspace. The UI suite builds widgets without `Open()`: no terrain refresh
is queued, but a root-size callback is queued, and map-mode switching can touch
the current game-world camera/render target. Suite return alone cannot establish
subsequent queued-callback lifetime.

The click suite calls handlers directly. It does not prove native mouse dispatch.
The action and click success details count controls, not assertions. The schema
suite enumerates a loaded prefab's component fields; it does not verify modeled
resource rendering, component property values, real gadget ownership or spawning.
The complete lifecycle and multiplayer gates remain in
[the tablet runtime packet](P5_TABLET_RUNTIME_ACCEPTANCE.md).

### Failure, root cause and corrected admission

The first real execution at `build/tablet existing suites & spaces-q93fbdjk/results.json`
remains **failure**, SHA-256
`313a2f7543db60d2871fe650fe095ca306d0e1035d9bf684244e3712fb409e91`.
The transport retained all five successful responses, 18 calls, 12 identities
and owned cleanup. The independent checker rejected the schema component order.
An 868-check passive audit verified its exact physical evidence at
`build/oct10-tablet-q93-passive-audit-49fee33660684438928e30ebcde9b9a3/result.json`.
That audit reproduces the old checker failure; it does not rewrite it as success.

This was a checker defect. The preserved handler enumerates native
`IEntitySource.GetComponent(i)` (`SPK_MeshSelfTest.c:2491–2507`); the installed
interface declares indexed access without a prefab lexical-order guarantee.
The observed six components differ from source order. The repaired policy is
`six-exact-distinct-components-preserve-native-order.v2`: exact count and
membership, no duplicate or unexpected class, bounded unique field names, and
untouched raw/parsed order. It does not assume alphabetic order either.

The corrected checker SHA-256 is
`a4b043093a365c8dc9cd2d173eec5f2dbf4f9516b78384341dd492a7da3db60f`.
Its 130 pure cases pass at
`build/tablet-suite-receipts-pure-d4734ebdf7634922906dc6eeba9d27ba/result.json`.
The previous 125 case IDs remain a prefix; the historical ordering case's
changed expectation is explicit, with the old policy/hash retained. Five new
cases cover the observed dump, repeated/replaced identities and raw
order preservation. No identity, timing, raw-response, input or cleanup gate was
relaxed.

The transport's 107 actual pure PowerShell cases pass at
`build/tablet-suites-checkers-8d11e12bb35a4e8985ee12e91369ed7a/outer/result.json`.
The entire adapter is parsed before extracting only 13 registered pure checker
functions; adapter startup, listener, engine execution and process stopping are
not run by this gate. The preceding 105/107 result remains failed. An empty
property enumeration is repaired, and the duplicate-selection fixture now
constructs two explicit rows; its earlier `+=` behavior has no established
root cause. Independent source staging also passes 92 inert cases, including
rejection of a two-link derived resource cache.

### Fresh engine result

Using the warning-aware S1 and corrected checker, the fresh result is:
`build/tablet existing suites & spaces-wbymk7mx/results.json`, SHA-256
`b08fec466e261541542cdf44e38739e8e7216f94c057a25b83c1d20939f9dfb3`.
All five suite requests passed with 18 raw-linked RPCs, 12 compiled identity
observations, no evidence errors and confirmed owned-process exit. Runtime
receipt admission reports 26,640 ms. Its fresh headless compilation took 7.1
seconds and reports zero admitted errors / 19 warnings. Timing describes these
operations, not a performance comparison.

The independent terminal audit passed 894 physical/hash checks at
`build/oct10-tablet-suites-complete-audit-833f51b0d0e44937aad986370030ee09/result.json`,
SHA-256 `426d666110d0359ecd773978795683d22cf3588481ca9929192ab2bec73f9b2b`.
It independently decodes the retained raw runtime receipt; its result exactly
matches the recorded five-suite verification. It checks the exact 87-file tree,
prior 86-file candidate, 140 retained inputs, source artifact/job/maps, logs,
live resources/scripts, 25 current tool sources, 107 compiler/runtime inputs,
private compiler and protected active compiler/pointer. There are no failures.

This closes S2 for the recorded five preserved suite returns. It does not execute
the Beryl tablet component or close lifecycle, queued-work, screen-owner,
physical-input, multiplayer or visual gates. The next bounded work is in
[the native lifecycle admission packet](P5_TABLET_NATIVE_LIFECYCLE_ADMISSION.md).
