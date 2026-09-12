# Advanced implementation state

Updated 2026-09-07. Implementation is authorized under
[the advanced plan](BERYL_ADVANCED_IMPLEMENTATION_PLAN.md).

## Installed record/PID and engine-collection checkpoint

The next bounded checkpoint is implemented, independently reviewed, verified and
installed. It extends the engine context, storage probes, actual performance
collection and experimental IR. **The full A–L program is not complete.** Public
IR lowering and automatic optimization remain unavailable. Live MESH is unchanged.

The final isolated terrain experiment recorded **34.06% median paired reduction
in command construction/release time** over 60 dependent pairs. This is a measured
phase-level opportunity, not an adopted optimization, game frame-rate improvement
or Rust comparison. The exact scope and remaining gates are below.

| Installed artifact | SHA-256 |
|---|---|
| `build/beryl.exe` | `aa7e9d51360cb8980f51e69313f0d8ee4dda59e54c3319f34697087b6a9d9b04` |
| Nineteen-file local mod-tool bundle | `6641a45fd8936d7e52185b50e627ddc7b2e07b83ddf3c2d01d863badba9f4f97` |

[Installation and smoke evidence](../build/next-install-y297nl0k/installation.json)
records the exact required gates, source manifests, previous files and new
identities. Version lookup, binding lookup against the installed engine/docs,
scenario discovery, installed mod checking and the complete native PID smoke all
passed after installation.

## What changed

| Area | Implemented boundary | Still outside this checkpoint |
|---|---|---|
| Engine context | `context binding` exposes 35 exact selected declarations with document/fragment hashes, spans and optional engine/document matching | Full typed bindings, reviewed lifetime/effect/authority contracts and complete API coverage |
| Reference admission | BE1001 rejects projected assignments whose destination evaluation or RHS may mutate overlapping storage; disjoint admitted operations still work | A language-wide decision on the previously disagreeing assignment boundary |
| Enfusion admission | BE0701 rejects unsupported generated struct-copy fields containing reference-element arrays/lists | General recursive owning-container copying and cleanup |
| Experimental IR | Finite f32, independent source manifests, record identities and copies, static projections, methods/defaults and `let`/`inout` captures; actual PID parity | Fixed arrays, dynamic projections, partial initialization, `set`/`sink`, owning storage, IR-to-C and IR-to-EnforceScript |
| Engine probes | Installed array-storage and Canvas-reference scenarios with controlled positive/negative observations | Native renderer retention, frame-boundary consumption, pooling and physical peak-memory guarantees |
| Terrain candidate | Preserved original/v1 fixtures, direct-v2 construction, complete payload comparison and typed actual timing scenario | Live MESH integration, full-render timing and release/adoption |
| Evidence collection | Strict schedules, raw target import, immutable journals and replay; absent capabilities remain unavailable | Independent-session statistical acceptance, complete paid costs, held-out evidence and `beryl experiment run` |

Packets: [binding context](advanced/STAGE_B_BINDING_CONTEXT.md),
[IR and PID](advanced/STAGE_D_IR.md),
[engine storage and collection](advanced/STAGE_C_STORAGE_AND_COLLECTION.md),
[performance collection](advanced/STAGE_C_PERFORMANCE_COLLECTION.md),
[counterexample coverage](advanced/RESEARCH_TEST_COVERAGE.md).
Both assistants use the updated [AI workflow](AI_WORKFLOW.md).

### Confirmed reference discrepancy and its repair boundary

The earlier compiler printed `10` in reference execution and `7` in native O0/O2
for a field assignment whose RHS replaces the enclosing record. Its reproducer
is retained at `build/ir-record-stage/destination-repro/results.json`.
Reference admission and the IR destination guard now reject the conflicting
pattern before treating either result as verified semantics. Ordinary native
behavior is unchanged; no value is declared normative by this repair.

The new CLI suite requires all ten fixture files, rejects nine conflicting
fixtures through both reference and differential execution with zero executed
steps/events/native jobs, admits the safe fixture, and runs the full unchanged
PID through both backends. This narrows the advertised reference subset honestly.

### Experimental PID evidence

The IR runs the actual unmodified `packages/sparkos/pid` implementation and tests:
**8 tests, 2,206 assertions, 208,908 IR steps**. Reference and IR stdout agree on
63,834 bytes; ordered events agree on 1,516,831 bytes. The original AST arena is
freed before IR execution. A type-valid integral-update mutation is detected.

The private D2 O2 and O0+UBSan records and raw streams are retained under
`build/ir-record-stage/`; the final integrated unit suite repeats the admitted
PID parity after the reference guard. This is interpreter parity. It does not
complete the planned emitted-code matrix or make `--lowering ir` available.

## Final verification evidence

The compiler was built from the 242-file immutable tree
`build/next-final-msmna9ek`, manifest SHA-256
`39eabf88f05ad3f5fe961f5a6a57dfc37e6683beb5fe7ee57fde4592b2e32f56`.
Paths in this table are relative to that tree's `build/`, except where explicit.

| Gate | Actual result | Evidence |
|---|---|---|
| Normal foundation | 356 unit cases / 2,681 checks; 15 programs at O0/O2; passed | `foundation-e94z0ibp/results.json` |
| UBSan foundation | Same full suite; passed | `foundation-dh2rdjmy/results.json` |
| Nine compiler/CLI groups | Driver, reference, expected traps, context, native evidence, source maps, diagnostic mapping, binding registry and destination admission; passed | Individual successful reports in `checkpoint-regressions-ncq8h9md/` |
| Analytical tools | 8 extractor tests, 18 evaluator tests, 18 collector tests, 6 importer tests and registry consistency; passed | `checkpoint-analytical-re279lng/results.json` |
| Engine integers | 553 fixtures / 860 checks; passed | `engine-integers-26de1k7g/result.json` |
| Engine PID | 2,195 operations / 65,850 comparisons; passed | `pid-9gv1xcjs/result.json` |
| Array and Canvas | 36 array + 30 Canvas observations; passed | `storage-scenarios & spaces-it1a93hs/result.json` |
| Terrain semantics | 750,095 payload checks; deliberate vertex mutant rejected with 12,482 mismatches and no success receipt | `terrain-scenario & spaces-ax28wb3r/result.json` |
| Actual terrain collection | 120 intervals / 60 dependent pairs / 960 constructions; imported and replayed | `terrain-measurement & spaces-xxo5lvo8/result.json` |
| Corrected map harness | Count 1: 10 checks; count 64: 294 checks; protocol, installation and session-policy checks passed | `build/next-final-5fx330hy/build/mod-scenarios & spaces-wde4xh02/result.json` in the repository |
| Corrected ordinary mod harness | Seven workflow, promotion/rollback and installed-tool groups passed | `build/next-final-mhj_ucus/build/harness-correction-0dylk_fv/results.json` in the repository |

[The final engine gate](../build/final-engine-gate-71fkjuq0/result.json) hashes all
six successful engine reports, compiler/tool identities, source equivalence,
mutant evidence, journal and replay. Workbench is `1.8.0.13`, executable SHA-256
`7dd36ca1f662b0c13669a4f2f7f10e3c461c2906b021e742272d64b3ab7e9798`.
All owned engine sessions were closed. No MESH artifact was promoted.

### Preserved test-harness failures

Final integration exposed two stale tests: the ordinary mod verifier's manually
constructed options lacked `measurement_plan`, and the map verifier assumed
every scenario after the first two was unavailable. The corrected fixtures
explicitly include the new optional fields and exact supported/unavailable names.
The original failures remain failures in their retained reports.

The corrected 242-file snapshot is `build/next-final-5fx330hy`, manifest SHA-256
`012091fc19c87a781aab1b77780a860ad292283e3f344dae48e7272c0ace4ec3`.
It differs from the compiled snapshot **only** in `scripts/verify-mod.py` and
`scripts/verify-mod-scenarios.py`; all other 240 files, including every compiler
and installed-tool source, are identical. Each corrected harness passed. The
installation record preserves this distinction rather than relabeling old runs
or claiming the failed aggregate succeeded.

## What the actual timing says

The [final immutable journal](<../build/next-final-msmna9ek/build/terrain-measurement & spaces-xxo5lvo8/collection/journal/collection.json>)
has SHA-256 `af9d1d0c4cead25f1aba23fbfb39d3f7e440c68b54375d89e5a20ec15cb49227`.
Its exact descriptive median paired reduction is `5837 / 17138` (34.0588%).
No pair was slower and no interval was zero in this run. These observations do
not establish an independent confidence interval or a release decision.

Each interval constructs and releases eight complete relief-command graphs from
a previously captured 80×80 height grid, with command-count observation. All six
fixtures preserve the 6,241 quads, band order, within-band ordering and 240-quad
chunk limit. The comparison excludes height capture, terrain sampling, Canvas
publication/consumption, other layers and MESH integration.

The earlier run's 33.27% median reduction and two slower pairs remain separately
recorded at `build/terrain-measurement & spaces-bhegr908/collection-v2/`.
The two runs are not pooled. Both are dependent, exploratory collections.
Physical peak/retained memory, complete consumer lifetime, full paid costs,
baseline-noise acceptance, held-out workloads and independent sessions remain
open gates. No whole-game or native-versus-Rust result follows from them.

## Installation, rollback and next work

The previous compiler, active-tool metadata and loader are preserved under
`build/next-install-y297nl0k/`. The prior compiler was `99f10cf5…171e5`; the prior
thirteen-file bundle was `53152704…136cbb`. All version directories remain.
Installation checked expected prior hashes and every captured source byte.
It includes guarded restoration on a failed install/smoke, with unknown later
writes preserved; four isolated-file rollback checks passed at
`build/checkpoint-restore-test-ksx4gd5f/results.json`. No rollback was needed.

For manual rollback, compare the current compiler, active pointer and loader
against the installation record first. Restore the three saved files together
only if their current hashes still belong to this installation; never overwrite
a later checkpoint. Retain the record and versioned bundles, then run the prior
capability set's smoke checks.

Next dependency gates remain:

1. Complete fixed-array/place/mode admission and the unoptimized IR-to-C O0/O2
   matrix; then add IR EnforceScript lowering and repeat engine PID parity.
2. Establish native Canvas consumption/lifetime and real physical-resource
   measurements; include full paid terrain work and independent held-out runs
   before adopting the terrain candidate.
3. Finish typed binding contracts, complete source origins and fixed AI authoring
   tasks; the new API snapshot is bounded context rather than full M4 completion.
4. Implement admitted owned storage and complete tracked mutation coverage before
   enabling store caches, expiry certificates, incremental queries or demand.
5. Continue whole-mod descriptions, authority/taint, dedicated multiplayer and
   visual acceptance through their existing gates. Native Rust comparisons,
   vectorization, specialization and PGO remain subsequent experiments.

No optimizer family is released by this checkpoint. The first substantial timing
signal now justifies further terrain investigation under the original gates.

## Historical: preceding advanced installation

The material below preserves earlier checkpoints and their exact evidence.
Their installed identities, capability limits and next steps describe those
earlier states; the installed checkpoint above supersedes them.

**Previously installed checkpoint:** Stage A/B foundations, isolated Stage C
semantic experiments and the experimental D0 scalar IR. The full A–L program
is not complete. No performance optimization family is released or automatically
enabled, and no complete-workload speedup or Rust advantage has been measured.

`build/beryl.exe` and its local mod-tool bundle have been installed and smoke
verified. The final compiler SHA-256 is
`99f10cf5e818e5a8f509fd3505146500b8a2ce4730aece6cbbcdb96c8ee171e5`;
the tool bundle is
`5315270444c998b091fd8043d32366e2362f862f4d652c5000bce11355136cbb`.

## Entry baseline

- Existing M3 isolated candidate remains historical evidence for its exact bytes.
- M4–M8 and advanced stages have not passed merely because this program started.
- Entry snapshot: `build/advanced-baseline-dc967edfaaae445a812d34d8c9ecbe53/sources.json`.
- Original compiler retained there as `previous-beryl.exe`.
- Original Git status retained alongside it; preexisting dirty changes preserved.
- Previous installed compiler SHA-256: `c7a7b3b10221b74f9078aeded70206f34f2c76d9b4242f8d0bea6455dac31f85`.

## Previous checkpoint stage status

| Stage | State | Evidence needed |
|---|---|---|
| A | Bounded verification repairs passed on immutable checkpoint | Expected traps/prefixes and integer edge cases; exact results below |
| B | Bounded interfaces implemented and verified | Context, native evidence, line-span maps and map-cursor scenario; complete binding/scenario/AI usability gates remain open |
| C | Map and terrain semantic fixtures passed in isolated engine runs | Complete engine workload timing, lifetime/resource validation and adoption remain open |
| D | Experimental scalar IR implemented, reviewed and tested | Full bool/i32/f32/record/array/mode/PID matrix and backend lowering remain open |
| E–L | Pending | Their explicit dependency and release gates |

No new optimization family is released or automatically enabled at this checkpoint.
No timing improvement had been measured at that earlier checkpoint. Live MESH was unchanged.

## Coordination

- Compiler agent: expected-trap verification, instrumentation and scalar IR.
- Engine agent: integer lowering, owned Workbench comparisons and typed scenarios.
- Context/evidence agent: context inventory, source-map review, evidence evaluator and independent IR review.
- Integrator: public CLI, native evidence, plan/state, shared validation/publication.
- The engine agent alone owned engine sessions. All owned sessions are now closed.

## Previous checkpoint integration gate

The final immutable tree is `build/advanced-final-_evwcnjm`, containing 206 captured
files. Its `snapshot.json` SHA-256 is
`fac3fd85aec9b423b25998d87c17e5484378168dbb202d1b18b1ff0e7703c355`.
Installation is recorded separately below; all selected checks passed. A
successful prototype does not close its full stage or enable an optimization.

Final compiler: `build/foundation-yldqgqqh/beryl.exe` inside that tree, SHA-256
`99f10cf5e818e5a8f509fd3505146500b8a2ce4730aece6cbbcdb96c8ee171e5`.

Evidence paths in the next table are relative to the final tree's `build/`:

| Evidence | Result |
|---|---|
| `foundation-yldqgqqh/results.json` | 331 unit cases / 2,163 checks, 15 programs at O0/O2 and example tests; passed |
| `foundation-fqkn6oj9/results.json` | Same full suite under UBSan; passed |
| `performance-evidence-synthetic-kdg5y3eh/results.json` | 18 analytical evaluator tests; passed; no benchmark execution |
| `advanced-regressions-wqh0blno/results.json` | All seven driver/reference/trap/context/native-evidence/source-map/diagnostic-map suites passed; individual raw reports retained |
| `engine-integers-jd06wnrq/result.json` | 553 fixtures / 860 actual engine checks, zero mismatches; passed |
| `pid-06n9xzna/result.json` | 2,195 complete operations / 65,850 actual Enfusion VM comparisons; passed |
| `mod & spaces-lgdvx5fx/result.json` | Seven ordinary mod workflow, staging, validation, promotion-policy and installation groups; passed |
| `mod-scenarios & spaces-axkgwcuw/result.json` | Seven typed-scenario, receipt, ownership and session policy groups; passed |
| `mod-scenarios & spaces-wguxtqv7/result.json` | Final-compiler map execution: six histories at counts 1 and 64, 10 + 294 checks; passed |
| `terrain-scenario & spaces-u9vdggxe/result.json` | Final-compiler terrain: six grids, 750,095 payload checks, 177 trace rows; passed; changed-vertex mutant rejected with 12,482 mismatches |

Final engine checks used Workbench 1.8.0.13, SHA-256
`7dd36ca1f662b0c13669a4f2f7f10e3c461c2906b021e742272d64b3ab7e9798`.
The terrain fixture compares engine equality on the five public command fields;
it does not prove bitwise floating equality, Canvas retention or rendering speed.

The scalar IR contributes 18 unit cases. It has indexed tables, an independent
verifier/evaluator, bounded execution and ordered scalar observations. Review
repairs cover repeated initialization, enum validation, missing timeout clocks
and unsupported dead expressions. The AST arena is freed before IR parity
execution. Source spans are retained; independent bounds validation against a
source manifest is not implemented. Public IR lowering remains unavailable.

The separate performance evaluator validates frozen receipt consistency and
statistics. It does not collect timings or prove externally asserted execution,
independence or observation completeness. Synthetic tests cannot yield a measured
performance adoption result.

## Previous installation and rollback

Installation record:
`build/advanced-install-b30_lkge/installation.json`.
It records every required gate's file hash, the final source manifest, prior and
new identities, installation argv/results and post-install smoke checks. All 206
captured files were checked against both live source and the final snapshot
immediately before publication. Default installation used only the verified
compiler and frozen tool sources.

The prior executable is preserved as
`build/advanced-install-b30_lkge/previous-beryl.exe`; prior active-bundle metadata
and loader are beside it. Versioned tool directories are retained under
`build/beryl-tools/`. The prior tool bundle is
`73d0ab5bb1ffb3bd2afed2bf8486be1a86fe092f9c7768e7d03b0078315eeaef`.

For a rollback, first confirm that the current installation still has the
recorded new hashes; do not overwrite a later installation. Restore the saved
executable and prior active-bundle metadata together. The new loader accepts the
verified four-, eight- and thirteen-file bundle formats; the original loader is
also retained. Run version and smoke checks supported by the selected rollback
capability set. Historical engine receipts remain tied to
their original artifact/compiler identities.

This installation changes the compiler and its local tooling. It does not
promote a generated MESH artifact or replace any live MESH script. Preexisting
working-tree changes and original reference fixtures remain preserved.

## Gates recorded at the previous checkpoint

1. Extend the IR through finite f32, records, arrays and access modes, with the
   independent PID matrix, before any public/backend migration.
2. Complete the required engine binding and retention probes, context contracts
   and mappings beyond the current bounded source associations.
3. Build complete-workload collectors for map/query and terrain candidates,
   including actual resource/lifetime evidence and held-out paired measurements.
4. Proceed to storage and tracked mutation only under their explicit gates; no
   cache, expiry certificate or demand mechanism is admitted by this checkpoint.

## Verified integrated A/B checkpoint

Immutable source tree: `build/advanced-gate-48gvf_3c`, with `snapshot.json` recording
the copied bytes. The first sandbox-owned snapshot `advanced-gate-w4bp38po` could
not be read by the normal compiler account; it was not tested. No denied launch
was counted as success. The readable replacement preserves the same snapshot method.

Compiler: `build/advanced-gate-48gvf_3c/build/foundation-djfdqlf0/beryl.exe`.
The following paths are relative to that immutable tree's `build/`:

| Evidence | Result |
|---|---|
| `foundation-djfdqlf0/results.json` | 313 unit cases, 1,850 checks, 15 O0/O2 programs; passed |
| `foundation-jand3khm/results.json` | Same foundation under UBSan; passed |
| `driver & spaces-qj27adps/results.json` | Ordinary commands, arguments, errors, concurrent builds, cancellation; passed |
| `reference-qx_2vkpg/results.json` | Existing independent reference/native corpus and mutants; passed |
| `expected traps & ieqm96t7/results.json` | Eight trap fixtures O0/O2, registered array, ten mutants, timeout/cancellation; passed |
| `context & spaces-7704vdap/results.json` | Nine context/admission groups; passed |
| `native evidence & spaces-x7lztxr1/results.json` | Eighteen native-evidence/admission/failure groups; passed |
| `source-maps & spaces-vd_h82s9/result.json` | Six generation/origin/determinism groups; passed |
| `map-diagnostics-s3hyc4xz/result.json` | Four malformed-map/diagnostic groups; passed (synthetic diagnostic inputs) |
| `mod & spaces-kumwvy4_/result.json` | Seven companion/artifact/promotion/installation groups; passed (promotion policy receipts synthetic) |
| `pid-7wc5r108/result.json` | 2,195 PID operations and 65,850 actual Enfusion VM comparisons; passed on this compiler |

Engine results on the preceding shared candidate are retained separately:

- `build/engine-integers-dbw_0wfp/result.json`: 553 fixtures, 860 VM checks, zero mismatches.
- `build/mod-scenarios & spaces-czrpgj8d/result.json`: eight tooling groups and real
  map-cursor VM comparison. Six histories at count 1: 10 checks/16 rows; count 64:
  294 checks/300 rows. Keys, order, and reference identity matched in those histories.
- Both used Workbench 1.8.0.13, SHA-256
  `7dd36ca1f662b0c13669a4f2f7f10e3c461c2906b021e742272d64b3ab7e9798`.
- These are semantic/contract results. They do not establish iterator complexity,
  safety during mutation, gameplay performance, or a Rust advantage.

Implementation details and actual CLI contracts:
[Stage A/B packet](advanced/STAGE_A_B_FOUNDATION.md),
[shared AI workflow](AI_WORKFLOW.md),
[engine experiment packet](advanced/STAGE_C_ENGINE_EXPERIMENTS.md),
[Stage D admission packet](advanced/STAGE_D_IR.md),
[performance evidence contract](../tools/beryl-experiments/README.md).
