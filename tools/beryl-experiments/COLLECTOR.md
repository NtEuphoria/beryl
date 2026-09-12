# Enfusion exploratory measurement collector, version 1

`collect.py` retains actual bridge data for a bounded timed operation. The initial
adapter measures integer-millisecond intervals in a single owned Workbench RPC.
It does not start an engine, create a second bridge, infer physical memory from
container lengths, or export incomplete data to `evaluate.py`.

The existing evaluator-v1 schema and decisions are unchanged. A successful
collection is always `collected_exploratory`, with `adoption_eligible: false`.
Thirty or more pairs inside one process do not establish thirty independent units.
Synthetic tests remain explicitly synthetic.

## Workflow

```powershell
python tools/beryl-experiments/collect.py schedule --experiment-id terrain-construction-01 --scope-name terrain_construct_release --case flat_water --case flat_land --case sea_threshold_checker --case row_column_ramp --case mixed_integer_seed --case narrow_height_range --pairs 60 --operations 1 --output experiment/schedule.json
# The existing owned Workbench bridge generates and executes this exact schedule.
# Its adapter writes the typed response and reviewed, hash-bound descriptors below.
python tools/beryl-experiments/collect.py ingest --input experiment/request.json --output experiment/journal
python tools/beryl-experiments/collect.py verify-journal --journal experiment/journal
python tools/beryl-experiments/test_collect.py
```

The parent of the schedule output must already exist. Schedule files and journal
destinations are created exclusively. `journal/collection.json` is the completion
marker, written only after all inputs have been validated and retained. A partial
directory without that marker is incomplete and must not be consumed as evidence.
The tool does not overwrite or clean existing experiment directories.

## Schedule

All following keys are exact; version fields accept integer `1` only. Unknown,
missing and duplicate JSON keys fail. File references have evaluator-v1's exact
`path`/`sha256` format, containment, byte limits and stale-input checks.

The schedule has `schema_version`, `kind` (`beryl.performance.schedule`),
`experiment_id`, `phase`, `role`, `created_utc_ns`, `scope_name`, `operations`,
`case_ids`, `pair_count`, `runs`.

Phases/roles are `exploratory/exploratory`, `pilot/calibration`, or
`candidate/{training,selection,held_out}`. These labels express intended use;
they do not establish a pilot freeze, sealed selection or held-out history.
Those remain explicit adoption blockers in every result from this adapter.

Select 1–64 unique case IDs, 30–1,024 pairs and 1–10,000 operations per interval.
Pair count must be divisible by twice the number of cases. The schedule cycles
through cases and alternates AB/BA on successive complete cycles. Consequently
**each fixture**, as well as the total, has balanced first-side counts. Sixty pairs
work for six cases; thirty pairs do not balance six fixtures individually.

Each scheduled run has `unit_id`, `side` (`a`/`b`), `ordinal` (global, zero-based),
`case_id`, `operations`. IDs identify actual collected intervals, but the name
`unit_id` does not itself establish statistical independence. The target adapter
must bind A/B to the baseline/candidate defined by the retained artifact and
workload descriptor; a pilot must bind both sides to the baseline. The collector
validates framing, not engine source semantics or a declared variant mapping.

Python API: `make_plan(experiment_id, phase, role, case_ids, pair_count,
operations, scope_name, now=None)`. `now` supports analytical tests; ordinary CLI
calls record the current time. Recorded dates are bookkeeping, not authenticated
chronology. The adapter must freeze its schedule before executing it.

## Raw target response

Keep this object in the existing bridge's `rpc.Response`:

```json
{
  "schema_version": 1,
  "kind": "beryl.performance.target",
  "token": "compiled-artifact-token",
  "scope_name": "terrain_construct_release",
  "timer_api": "System.GetTickCount",
  "tick_unit": "ms",
  "executed": 1,
  "failures": 0,
  "expected_runs": 120,
  "rows": []
}
```

Rows use these exact forms:

```text
timer|index|start_tick|end_tick
run|unit_id|side|ordinal|case_id|start_tick|end_tick|operations|alloc_before|alloc_after|kb_before|kb_after
```

One to 4,096 timer probes precede all runs; indices start at zero with no gaps.
At least one probe must observe advancement. Each run must match the schedule in
every identity/order/count field. Runs cannot be skipped, duplicated or appended.
Ticks and counters are canonical decimal integers in `[0, INT32_MAX]`. Counter
slots can instead contain the literal `unavailable`. All intervals must be
nondecreasing and nonoverlapping in response order. A backwards/wrapped timer
fails collection; wrap is not silently corrected.

The adapter uses the installed declaration: `System.GetTickCount(int prev=0)`
returns integer milliseconds. Multiplying a tick difference by 1,000,000 records
the unit conversion; it does not create nanosecond precision. The result reports
`resolution_ns: null` and keeps every raw probe. Minimum observed increments are
not a proof of clock resolution or accuracy. Zero-duration intervals remain zero,
are flagged as below observed granularity, and are never divided into a fabricated
speedup. They also prevent any interpretation that all intervals resolved.

`MemoryAllocationCount` and `MemoryAllocationKB`, when available, are retained as
whole-engine snapshots. No delta is reclassified as per-operation allocations,
retained storage or a peak. Negative deltas are possible between nonnegative
snapshots; there is no monotonic-counter assumption.

## Collection request and reviewed descriptors

The request has `schema_version`, `kind` (`beryl.performance.collection`),
`evidence_kind` (`collector_measurements`/`synthetic_validation`), `token`,
`schedule`, `runtime`, `semantic`, `scope`, `ownership`, `fingerprints`,
`raw_evidence`. Schedule/runtime/semantic/scope/ownership are file references;
`raw_evidence` is a nonempty list of up to 128 file references.

Fingerprints are references for exactly `artifact`, `sources`, `compiler`,
`toolchain`, `bindings`, `engine`, `environment`, `workload`, `semantic_contract`,
`tool`, `integration`. Retain actual source or file manifests, compiler identities,
binding/timer declaration evidence, environment conditions and complete scope
definitions. A descriptor hash identifies descriptor bytes; it does not prove the
external binary/CPU described inside it. Preserve producer verification evidence.

The engine descriptor has `schema_version`, `kind`
(`beryl.performance.engine_identity`), `binary_sha256`, `version`, `evidence`.
Its binary hash and version must match the runtime receipt. The potentially large
engine binary need not be copied; the check that established its identity must be
retained. The `engine` fingerprint used by semantic receipts is the **descriptor
hash**, while `binary_sha256` identifies the executable.

The scope descriptor has `schema_version`, `kind` (`beryl.performance.scope`),
`status` (`reviewed`), `scope_name`, `description`, `paid_components`,
`excluded_components`, `resource_status`, `timer_evidence`, `review_evidence`.
The two component lists partition these names exactly once:
`setup`, `capture`, `compute`, `maintenance`, `invalidation`, `conversion`,
`cleanup`, `cold_refresh`. A measured interval can jointly include compute and
cleanup; it is not partitioned into invented separate timings. Excluded categories
are explicitly outside the scope, not asserted to have zero application cost.
Resource status has `peak_bytes`, `retained_bytes`, `allocations`, `text_bytes`,
`build_ns`, `edit_check_ns`; every value is exactly `{status: "unavailable",
reason: <nonempty explanation>}`. Version 1 rejects purported measured resources
because this target adapter has not admitted their instrumentation.

The ownership descriptor has `schema_version`, `kind`
(`beryl.performance.ownership`), `status` (`verified`), `process_id`, `start_time`,
`project`, `evidence`. All three session identity fields must exactly match the
successful bridge receipt; `reused` must be the JSON boolean false. Reused-session
collection needs a separately designed reset policy rather than a bypass flag.
Ownership and independence are separate: a verified owner does not make repeated
batches independent.

The semantic descriptor has `schema_version`, `kind`
(`beryl.performance.semantic`), `status` (`complete`), `fingerprints`, `case_ids`,
`expected_cases`, `completed_cases`, `failures`, `comparison`, `evidence`.
Its fingerprints are digest strings for exactly `artifact`, `workload`,
`semantic_contract`, `engine`, matching the collection descriptors. Case IDs must
match the schedule's ordered selection. Counts must be positive and complete;
failures must be integer zero. `comparison` is
`engine_operator_complete_payload` or `byte_exact_complete_observations`.
The former does not imply bitwise floating-point equality. The referenced
producer comparison must actually validate the complete admitted payload under
the stated contract, separately from timing instrumentation.

The parser checks receipt consistency. It cannot discover a producer lying about
successful comparisons or omitted observable state. Raw comparison responses,
source identity, scoped review and deliberate mutant tests remain necessary.
`test_collect.py:Bundle` provides a complete synthetic construction example.

## Importing the existing terrain scenario receipts

`import_terrain.py` prepares those descriptors from the existing bridge's
`measure.terrain.construction` and `compare.terrain.chunks` receipts. It launches
no process or engine. Supply these explicit paths:

```text
--measurement-receipt  successful measurement receipt or outer result
--semantic-receipt     successful comparison receipt or outer result
--schedule             the exact schedule frozen before timing
--candidate            timing scenario-candidate.json
--candidate-root       timing staged addon directory
--semantic-candidate   comparison scenario-candidate.json
--semantic-candidate-root comparison staged addon directory
--tool-root            exact frozen installed mod-tool bundle
--tool-manifest        complete filename-to-SHA256 bundle manifest
--integration-root     Workbench integration root containing scripts/
--compiler             compiler executable identified by both receipts
--timer-evidence       actual timer/counter capability receipt
--environment          reviewed environment descriptor
--output               fresh directory for descriptors, raw files and journal/
```

The environment descriptor has exactly `schema_version: 1`,
`kind: "beryl.performance.environment_review"`, `status: "reviewed"`,
`description` and `evidence` (a relative file reference). Describe actual
conditions and unresolved details, rather than filling invented CPU/load facts.

Both scenarios must share exact compiler, source artifact, tool, integration and
engine identities. Their `scenario_contract.source_templates` mappings and
`datasets` must match. The timing contract also binds the raw schedule hash.
The importer checks the staged source sets and hashes, raw result hashes, compiler
binary, tool manifest and integration scripts before creating descriptors. Raw
results must reside inside each respective scenario job. `resourceDatabase.rdb`
is excluded from post-execution source checks consistently with the existing
bridge; script sources and all other manifest files remain checked.

A semantic comparison of an older adapter cannot validate a changed timing
candidate merely because the fixture names match. A template change requires a
new comparison using the same frozen tool identity. Source-template metadata
still comes from the reviewed producer; hashes do not prove source semantics.

This importer accepts only the exploratory phase. It refuses held-out/pilot
relabeling because it does not establish a sealed pilot or independent sessions.
`test_import_terrain.py` validates matching raw bundles, changed templates,
compiler/staged sources, raw responses, semantic failures, integration changes and
unreviewed environments using synthetic fixtures. No such fixture is an engine
measurement.

## Journal, results and next admission layer

The journal retains every validated source file under `objects/<sha256>` and
records original paths, object paths and hashes. It also records the request and
collector hashes, collection time, all raw target intervals, paired observations,
engine-wide counter snapshots, timer probes and blockers. Input bytes are checked
again immediately before capture and before the completion marker.

The exact collector and evaluator dependency source bytes are retained too, under
reserved `__collector_revision__/` provenance names. Replay checks both revisions.

`verify-journal` replays validation from retained objects and compares the full
derived summary. Altered summary claims or raw objects fail. Replay requires the
exact recorded collector revision; this is integrity validation, not producer
authentication or a performance-adoption gate.

The only statistic is a **descriptive median paired reduction for this observed
batch**, excluding zero-baseline pairs explicitly and reporting the included
count. There is no confidence interval, tail estimate, normalized nanosecond
precision, resource claim or automatic adoption. Display raw intervals alongside
this statistic; do not call it a release speedup or generalize to gameplay/Rust.

The next collector must establish separate owned sessions or reviewed reset
equivalence, capture full paid components and admitted physical resources,
produce complete byte-exact evaluator-v1 semantic receipts where applicable, and
run the evaluator's baseline-only frozen pilot and held-out selection protocol.
It must also track actual tuning history, region/lifetime budgets and a separately
specified tail-latency experiment. Nothing in this file relaxes those gates.
