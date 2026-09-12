# Stage C performance collection packet

Status: collection infrastructure implemented; engine runs are separate evidence.
This packet does not close Stage C or release a performance optimization.
The [final installed checkpoint](../BERYL_ADVANCED_IMPLEMENTATION_STATE.md)
contains a fresh final-compiler collection and successful journal replay:
120 intervals / 60 dependent pairs / 960 constructions, with a descriptive
34.06% median paired time reduction. Its source identities and limits are
recorded separately from the initial 33.27% collection below.

## Objective and measured boundary

Collect defensible timings for the isolated direct-terrain construction candidate
through the existing owned Workbench bridge. Preserve the current 80×80 cached
height grid, 6,241 quads, 240-quad chunks, payloads and traversal order. The initial
candidate measures cached-height relief-command construction and release, with a
count observation that prevents silently omitting result construction.

Height capture, real terrain sampling, Canvas publication/consumption, other map
layers, widget interactions and full rendering are separate scopes. A construction
interval cannot answer how much faster the entire tablet will become.

## Implemented collection contract

[`collect.py`](../../tools/beryl-experiments/collect.py) makes a deterministic
schedule, validates exact target framing and identities, and retains raw evidence
in an immutable journal. [`COLLECTOR.md`](../../tools/beryl-experiments/COLLECTOR.md)
is the complete public schema and CLI contract.

Sixty pairs over six fixtures alternate first-side order independently within
each fixture. Repeated batches inside a single RPC remain dependent observations.
The `unit_id` label is bookkeeping, not evidence of physical independence.

The first timer is installed `System.GetTickCount`, returning integer
milliseconds. Clock advancement is probed inside the same synchronous RPC before
timing. Raw clock readings are retained; backward/wrapped ticks fail. Conversion
to integer nanoseconds changes units only. Zero-length intervals stay unresolved.
The collector does not infer clock resolution from minimum observed differences.

Raw `MemoryAllocationCount` and `MemoryAllocationKB` snapshots are whole-engine
observations. Their exact live/cumulative/attribution semantics and workload peak
measurement need separate probes. A length/capacity, KB delta or count delta is
not substituted for retained bytes, peak bytes or workload allocation count.

## Separation from evaluator v1

[`evaluate.py`](../../tools/beryl-experiments/evaluate.py) remains unchanged.
It requires complete paid-cost/resource measurements, a baseline-versus-baseline
pilot, a threshold frozen before candidate measurements, independent paired units,
held-out role and complete exact semantic observations.

Collector success means `collected_exploratory`, always with
`adoption_eligible: false`. It reports the descriptive paired median for the
observed batch only. Confidence intervals, tail latency, resource claims and
automatic adoption remain unavailable.

The eventual adoption run must include:

1. A reviewed independence unit: separate owned sessions, or a tested reset that
   establishes the relevant initial-state equivalence. Merely changing IDs or
   clearing an array does not establish independence.
2. A baseline-only paired pilot, with ≥30 actual independent balanced blocks, then
   a recorded freeze of the maximum of 5% and the pilot's P95 absolute variation.
3. Candidate selection sealed before the independent held-out measurements.
   Retain complete tuning history so a previously examined trace cannot silently
   become held-out again.
4. Separate and complete setup, capture, compute, maintenance, invalidation,
   conversion, cleanup and cold-refresh cost accounting where the application
   pays those costs. Joint intervals need an explicitly versioned accounting rule
   or separately measured components before evaluator-v1 export.
5. Actual per-workload physical peak/retained memory, allocation counts, code size,
   build and edit/check time. Optional-storage region/process limits and lifetime
   behavior need their own evidence beyond whole-workload totals.
6. Uninstrumented candidate and baseline source identities, complete semantic
   comparisons and deliberate mismatch rejection. Instrumented comparison harness
   duration must not be called construction performance.
7. A separately specified trace/population/uncertainty procedure for tail latency;
   a confidence interval for the median cannot prove reduced frame spikes.

## Validation and evidence

`test_collect.py` uses synthetic target replies and analytical 20% reduction
fixtures to test the parser and journaling. It tests per-case order balancing,
unresolved timer intervals, unavailable counters, stale identities, unknown and
duplicate fields, incomplete/failed runs, wrong operation counts, backwards and
wrapped clocks, unverified/reused sessions, missing paid scopes, fabricated
resource availability, semantic mismatch, input mutation and exclusive journal
publication. These are not measured performance results.

Initial execution including raw-journal replay and retained collector revisions:
18 synthetic tests passed in
`build/performance-collector-synthetic-oq0kt4ou/results.json`; six synthetic
terrain-import provenance tests passed in
`build/performance-collector-synthetic-1jvp3yoi/import-results.json`.
Later integrated checkpoint receipts supersede these implementation-time results.

`import_terrain.py` verifies the measurement and semantic scenario receipts,
source-template identity, exact staged source sets, raw result files, compiler,
tool bundle and integration scripts before constructing the collection request.
It rejects an old comparison paired with a changed timing implementation. Actual
engine execution remains solely with the existing bridge.

Actual engine experiments are executed only by the engine owner through the
existing bridge. Their journals must be cited separately with exact source, tool,
binding, workload and engine identities. A successful capability probe establishes
that an API was callable on that engine; it does not settle its entire lifetime,
resource or performance contract.

## Fallback and unfinished work

The production MESH implementation is unchanged by this collector. Failed or
partial capture produces no completed journal. Existing outputs are preserved.
Missing resource/independence/lifetime evidence leaves adoption unavailable.
Full rendering, independent-run automation, evaluator-v1 export, tail-latency
estimation and a matched native Rust workload remain explicit future work.

## First actual exploratory result

The engine owner executed the frozen six-case schedule: 60 pairs, 120 intervals,
eight construction-and-release operations per interval (960 operations total).
The corresponding complete payload comparison ran before timing with the same
source templates. The timed candidate is the v2 direct builder, including its
per-band palette preparation; this run does not isolate each change's contribution.

The immutable journal is
[`collection.json`](../../build/terrain-measurement%20%26%20spaces-bhegr908/collection-v2/journal/collection.json),
SHA-256 `31d47d32a9167b2b08cf4c9d63f76dcee761e746add4bf78e25d9f48582621b0`.
The importer and raw-journal replay succeeded. The initial importer rejected an
absolute environment-evidence reference after the engine finished; the original
failure remains in the job's `result.json`. `environment-v2.json` corrected only
that reference to the same evidence bytes, and `import-repair.json` records the
repair/import/replay. No engine measurement was rerun to repair metadata.

The **descriptive median of the 60 paired reductions** was `499/1500`, or
33.2667%. Two pairs were slower. All 120 intervals resolved to positive integer
millisecond durations. These observations are dependent batches from one owned
engine session; there is no confidence interval, adoption decision or language-wide
speed claim. The run does not measure full map rendering or native Rust performance.

| Fixture | Baseline median interval, ms | Candidate median interval, ms |
|---|---:|---:|
| Flat water | 203 | 132.5 |
| Flat land | 209 | 138.5 |
| Sea-threshold checker | 206 | 133 |
| Row/column ramp | 212.5 | 142.5 |
| Mixed integer seed | 207 | 145 |
| Narrow height range | 210.5 | 139 |

Every table entry is the median **eight-operation interval**, not an individual
render/frame time. Fractional medians arise from averaging two integer-millisecond
observations; they do not imply sub-millisecond timer resolution. The four raw
timer probes advanced by 14, 13, 14 and 15 ms. Those probe workloads demonstrate
advancement, not clock resolution or accuracy.

The result supports further investigation of this candidate. All resource,
independence, complete paid-workload, lifetime and visual gates above remain open.
