# Research counterexample and implementation-gate coverage

This inventory maps all 25 cases in [research §20](../research/performance-2026-09-07/report-source.md#20-counterexamples-every-implementation-packet-should-include) and the additional [advanced-plan cases](../BERYL_ADVANCED_IMPLEMENTATION_PLAN.md#41-correctness-matrix) to inspected tests. It is not a new execution receipt.

The established baseline is the immutable checkpoint in [implementation state](../BERYL_ADVANCED_IMPLEMENTATION_STATE.md): 331 unit cases / 2,163 checks, separate native/reference/driver suites, map cursor probes at counts 1 and 64, and six terrain-payload fixtures. New source/tool changes need their own captured-source verification. A test existing in the tree does not establish that changed live bytes passed it.

**Partial foundation** means an actual test covers a narrower prerequisite; the full counterexample remains pending. **Pending** means no matching transformation/adversarial fixture is established. **Policy tested** means synthetic receipts exercise evidence admission, not engine execution or measured performance. No unimplemented optimization receives coverage from an unrelated arithmetic or driver test.

## All 25 research cases

| ID | Required adversarial case | Actual evidence | Remaining gate |
|---|---|---|---|
| C01 | Newer duplicate outside view; older duplicate inside | Pending. A single-map traversal has no provider winner/filter pipeline. | Complete query trace and reversed-filter-order mutant; winner before filtering. |
| C02 | Equal timestamps from two providers | Pending. No multi-provider tie fixture established. | Preserve first-encountered winner and provider order. |
| C03 | More than 128 candidates with eligibility/projection/symbol failures | Pending. Map count is not marker acquisition. | Exact cap boundaries and counter increment after acquisition, including failed symbol rendering. |
| C04 | Time advances without publication | Pending. Map probes have no freshness clock. | Unchanged entity data with changing time, exact freshness/opacity thresholds and observations. |
| C05 | Shared alias shortens expiry | Pending. No tracked expiry certificate admitted. | All alias/writer paths invalidate before mutation, including rejected-publication paths. |
| C06 | Same key replaced by another object with equal fields | Partial: [`map-cursor.c.in`](../../tools/beryl-mod/map-cursor.c.in) compares cursor/indexed references after replacement; existing replacement changes serial fields. | Equal-field/different-object replacement and entity-generation/cache invalidation. |
| C07 | Deadline queue removes correct IDs in wrong order | Pending. Ordered enumeration is not expiry removal. | Full original removal trace and intermediate state; no sorting away differences. |
| C08 | Sequence wraps or bounded log loses entries | Pending. No epoch/log implementation admitted. | Forced wrap, generation reuse and missing-event rebuild/invalidation. |
| C09 | Cache survives missing dependency edges | Pending. No dependency graph admitted. | Edge-corruption mutant and coherent region invalidation. |
| C10 | Nested callback reuses outer scratch | Pending. Filesystem job isolation does not test callback reentrancy. | Separate active workspace or fallback before effects; preserve outer invocation state. |
| C11 | Canvas reads reclaimed/mutated pooled arrays | Pending for consumer lifetime. [`verify-terrain-scenario.py`](../../scripts/verify-terrain-scenario.py) compares payloads before publication. | Actual publication, reference/array retention and asynchronous consumption; immediate alias probes alone cannot authorize reuse. |
| C12 | Visible target remains classification NONE | Pending. No sensor-generation candidate admitted. | Stamp at visibility point before classification rejection; preserve repeated dwell updates. |
| C13 | Swap removal moves contact without stamp | Pending. No sensor parallel-metadata fixture established. | Contact/dwell/generation alignment after removal and following scans; deliberate misalignment mutant. |
| C14 | Final result fits but intermediate overflows | Partial: [`test_reference.c`](../../tests/unit/test_reference.c), [`verify-expected-traps.py`](../../scripts/verify-expected-traps.py), [`test_ir.c`](../../tests/unit/test_ir.c) check overflow/first-site/prefix and compound ordering. | Explicit fit-after-overflow expression and reassociation mutant for each admitted transform/backend. |
| C15 | SIMD tail reads beyond storage | Partial scalar prerequisite: fixed-array bounds traps in reference/native tests. | No SIMD implementation yet; test every active tail, storage boundary and speculative load when introduced. |
| C16 | Two lanes fail at different source operations | Partial: expected-trap prefix/site tests and IR first-failing-argument ordering. | Actual lane/iteration-major failure precedence and successful write prefix in the block/vector implementation. |
| C17 | Guard fails after engine command sent | Pending. No engine-effect replay admitted. | Reject replay across observable command; runtime test proves no duplicate command. |
| C18 | Optional allocation aborts rather than fallback | Partial: reference/IR budget exhaustion is distinguished from source traps. | Independently fallible reservation, allocator-failure injection and ordinary fallback; interpreter budgets are not allocator failure. |
| C19 | Setter leaves specialization active | Pending. No specialization family released. | Versioned assumptions, setter/alias invalidation and behavior after reconfiguration. |
| C20 | Real-arithmetic margin fails under f32 | Partial: independent binary32 parsing/grouping tests and engine terrain equality. | No spatial certificate exists; test actual machine-arithmetic witnesses at rounding/boundary cases. |
| C21 | Hidden UI skips authoritative state | Pending. No demand-based suppression admitted. | Hidden/shown transitions while controllers, commands and replication remain active. |
| C22 | Wins only on training trace | Policy tested: `test_evaluate.py::test_role_and_held_out_contamination` rejects declared contamination and marks selection-only results. | Real independent held-out runs and complete tuning-history review; unreported tuning cannot be detected from JSON. |
| C23 | Hidden pure calculation would overflow | Partial: scalar traps/short circuit and unsupported dead-expression admission tests. | Demand-region totality and the exact hidden-overflow fixture; admission scanning does not prove totality. |
| C24 | Cache depends on evicted region | Pending. No cache/demand regions admitted. | Reject initial cross-region sharing; later sharing requires transitive invalidation and eviction tests. |
| C25 | Eligibility guard overflows or cannot allocate | Pending. No certificate guard admitted. | Total non-observing guards, boundary/resource injection and fallback before effects. |

## Additional advanced-plan counterexamples

| ID | Case | Actual evidence and unfinished work |
|---|---|---|
| P01 | Mutation before rejected publication | Pending. Mutate through a shared alias, reject the later publication and still invalidate dependents. |
| P02 | Mutable ID differs from actual key | Pending. Cursor fixture uses fixed keys. Test ID mutation without key migration, replacement/removal by actual key and identity semantics. |
| P03 | Nested shared state across entries | Pending. Reference nested-value copy tests cover independent values, not shared engine aliases. Test shared nested writers and affected-entry invalidation. |
| P04 | Source trap versus harness failure | Bounded foundation tested: `verify-expected-traps.py` rejects wrong sites/roots, ordinary nonzero exits, timeouts, cancellation, missing tools and budgets; IR tests separate harness outcomes. Extend for each new failure kind. |
| P05 | Unsupported IR silently falls back | Bounded foundation tested: `verify-native-evidence.py` rejects unsupported public IR before jobs/publication; IR unit tests reject operations outside the current record/PID admission subset. Public IR selection remains gated; future paths must still fail explicitly outside admission. |
| P06 | Instrumentation hides machine work | Partial: native-evidence tests retain generated C/runtime hashes, argv/version, LLVM IR/assembly and reject incomplete artifacts. Still compare separately uninstrumented timing artifacts; evidence files alone do not prove useful machine transformation. |
| P07 | RHS or index evaluation replaces a projected destination's ancestor | Confirmed earlier reference/native disagreement, preserved in `build/ir-record-stage/destination-repro/`. New reference admission and IR destination guards reject the conflict; `verify-reference-destinations.py` requires ten fixtures, checks zero execution for nine rejected shapes, preserves disjoint cases and repeats full PID parity. This is conservative admission, not a specification decision or proof for a new optimization. |

## Supporting tests and evidence boundaries

| Gate | Actual inspected entry point | Limit |
|---|---|---|
| Wrong/empty/duplicate selections and corrupt engine replies | [`verify-mod-scenarios.py`](../../scripts/verify-mod-scenarios.py), [`verify-terrain-scenario.py`](../../scripts/verify-terrain-scenario.py) | Synthetic negatives; actual engine execution requires the explicit engine option. |
| Terrain complete finite payloads and changed-vertex mutant | `verify-terrain-scenario.py` | Six grids, all vertex/index values and public command fields; no sampling, Canvas, pooling or full-render claim. |
| Scoped identity/ownership/completeness | [`test_collect.py`](../../tools/beryl-experiments/test_collect.py) | Analytical parser tests; owner review is an external assertion, not statistical independence. |
| Per-fixture order balance and operation counts | `test_balances_every_case_not_only_global_order`, `test_wrong_order_operation_count_and_duplicate_run` | Exact schedule framing; no claim that same-session batches are independent. |
| Clock wrap/backwards/sub-granularity behavior | `test_collect.py` timer tests | Raw increments do not establish clock resolution/accuracy. Zero intervals remain explicit. |
| Unavailable allocation/peak evidence | `test_unavailable_counters_are_not_zero`, `test_unknown_allocation_is_not_admitted_metric` | Whole-engine snapshots are not reclassified as workload metrics. |
| Semantic mismatch and journal integrity | `test_semantic_failure_missing_case_or_stale_identity`, `test_journal_replay_rejects_altered_summary_or_raw_objects` | Receipt/hash/replay validation; complete producer semantics still need actual comparison evidence. |
| Pilot, threshold, paired blocks, held-out roles | [`test_evaluate.py`](../../tools/beryl-experiments/test_evaluate.py) | Analytical admission rules only; execution, independence and truthful history remain external obligations. |
| Full paid costs and budgets | Evaluator full-cost/resource tests | Whole-workload totals do not prove region/lifetime/allocation-failure behavior. |
| Tail latency | Pending | Neither evaluator nor collector v1 supplies a tail estimator or tail uncertainty. |
| Concurrency, metacharacters, publication, timeout/cancellation | [`verify-driver.py`](../../scripts/verify-driver.py), [`verify-native-evidence.py`](../../scripts/verify-native-evidence.py) | Command/artifact integrity, not callback reentrancy, multiplayer or cache semantics. |
| Source mapping and unavailable columns | [`verify-source-maps.py`](../../scripts/verify-source-maps.py), [`verify-source-map-diagnostics.py`](../../scripts/verify-source-map-diagnostics.py) | Bounded line/span association; column interpolation/full nested expansion chains remain limited. |

The collector implementation passed 18 analytical tests in `build/performance-collector-synthetic-oq0kt4ou/results.json`; six raw terrain-import provenance tests passed in `build/performance-collector-synthetic-1jvp3yoi/import-results.json`. The latter reject old candidate templates, changed compiler/staged sources, failed or altered raw semantic replies, changed integrations and unreviewed environments. Neither result is engine or performance evidence. Concurrent new engine/IR work must update this inventory only after its own immutable receipts establish the exact behavior.

An actual exploratory terrain collection subsequently completed 60 pairs / 120
eight-operation intervals, with its preceding complete payload comparison and
successful raw-journal replay. See the [measurement packet](STAGE_C_PERFORMANCE_COLLECTION.md#first-actual-exploratory-result).
This establishes real scoped timing collection, not C22 held-out performance
coverage: all batches share one session, resource/lifetime measurements remain
unavailable, and no optimization is adopted from this journal.

The [final installed checkpoint](../BERYL_ADVANCED_IMPLEMENTATION_STATE.md)
repeats the complete foundation and selected engine gates against its exact
compiler/tool hashes. Its separate 60-pair journal recorded a descriptive 34.06%
median reduction and replayed successfully. This does not close the pending
resource, independence, held-out, full-render or transformed-workload rows above.

## Closing a pending row

Each packet names its row, constructs the adversarial program/history, records reference observations, tests the actual candidate under the admitted contract, and demonstrates rejection of a deliberate fault. Reuse narrow prerequisite tests without substituting them for transformed-workload tests. Keep semantics, resources, authority, visuals and performance separate. Negative or unavailable outcomes remain useful evidence and must not be relabeled as complete coverage.
