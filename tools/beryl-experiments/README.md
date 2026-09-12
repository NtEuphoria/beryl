# Experimental performance evidence evaluator, version 1

This standard-library tool evaluates a bounded evidence bundle. It does not run
benchmarks, launch Enfusion, enable an optimization, verify a model's proposed
proof, or establish that an external collector actually measured what it reports.
Its output is a conditional admission decision for one frozen workload/metric.

The governing protocol is
[advanced plan §4.3](../../docs/BERYL_ADVANCED_IMPLEMENTATION_PLAN.md).
No Beryl/Rust performance result is supplied by the analytical fixtures.

The separate [Enfusion collector](COLLECTOR.md) retains actual typed bridge
responses and scoped exploratory timings. Its first adapter deliberately does not
export incomplete resource or same-session data into this evaluator's v1 contract.

```powershell
python tools/beryl-experiments/evaluate.py freeze --input experiment/pilot.json --output experiment/freeze.json
# Collect the selected candidate only after the freeze, using a separate receipt.
python tools/beryl-experiments/evaluate.py evaluate --input experiment/request.json --output experiment/result.json
python tools/beryl-experiments/test_evaluate.py
```

Outputs are also printed as JSON. Output files are created exclusively: an existing
file is never replaced. Valid evaluations exit 0 even when the performance or
resource gate fails. Invalid/incomplete/stale evidence exits 2 with a versioned
`beryl.performance.error` object. Read `decision`, not exit status, for eligibility.

## Trust and identity

The evaluator checks exact file bytes/hashes, schema, chronology consistency,
receipt completeness fields, distinct unit/run identifiers, pair order, output
equality and the statistical/budget rule. These checks do not authenticate
timestamps, prove physical independence, establish reset equivalence, prove IID
sampling, or discover omitted observations. Those remain collector and reviewer
obligations. A verified status in a receipt is an externally asserted fact.

Run IDs must identify actual independently collected measurements. Generating new
IDs for correlated frames or copied observations does not make them independent.
An evidence reviewer must establish the declared sampling population and reset
contract, including any effects of execution order. Record that review in the
hash-bound independence evidence; do not infer it from timing variance.

Every file reference has exactly `path` and `sha256`. Paths are relative POSIX
spellings inside the input JSON's directory; traversal, absolute paths and escaped
symlinks fail. Digests are lowercase SHA-256. The tool checks all referenced bytes
again before returning a CLI result. A descriptor's hash identifies that
descriptor; it does not independently identify external executables or hardware
mentioned inside it. Collectors must retain and verify the underlying identities.

Limits are 16 MiB/file, 256 MiB of unique referenced bytes, 16,384 files, and
30–1,024 paired blocks. These are evaluator admission limits, not mod limits.

## Strict JSON contract

All keys listed below are required. Unknown keys, duplicate JSON keys, missing
measurements, nonfinite numbers and unsupported enum values fail. Integer fields
accept JSON integers only, never booleans or floats. Counts/times/bytes are
nonnegative signed-64-bit-range integers; positive minima are specified below.

All objects use `schema_version: 1` where a version is listed. Version 1 does not
silently interpret future versions. Exact canonical comparison distinguishes
`true`, `1` and `1.0` in freeze receipts.

### Pilot document

Keys: `schema_version`, `kind`, `experiment_id`, `evidence_kind`, `resource_policy`,
`metric`, `population`, `fingerprints`, `budgets`, `blocks`.

- `kind`: `beryl.performance.pilot`.
- `experiment_id`: 1–128 ASCII letters/digits or `_ . : -`.
- `evidence_kind`: `synthetic_validation` or `collector_measurements`.
- `resource_policy`: `resource_adequate_exact` or `resource_observable_exact`.
- `metric`: exactly `median_paired_total_paid_ns`.
- `population`: exactly `sampling` (`independent_identically_distributed`) and
  `description` (1–4,096 characters defining the admitted population).
- `fingerprints`: exactly file references for `baseline`, `compiler`, `toolchain`,
  `environment`, `workload`, `semantic_contract`.
- `budgets`: exactly integer limits for `peak_bytes`, `retained_bytes`,
  `allocations`, `text_growth_ppm`, `build_ratio_ppm`, `edit_check_growth_ppm`.
- `blocks`: an even number of complete paired blocks, at least 30 and at most
  1,024. Both sides of a pilot pair identify the same baseline artifact.

The compiler, toolchain, environment, workload and semantic-contract identities
must match every run. The semantic contract must describe admitted inputs,
arithmetic/failure semantics, complete observables, resource/lifetime assumptions,
units, measurement boundaries and the treatment of setup/cold execution.

### Paired block and independence receipt

Block keys: `unit_id`, `first`, `independence`, `a`, `b`.
`first` is `a` or `b`; these occur equally often. `a` and `b` reference measurement
JSON files. A is the baseline; B is the second baseline during calibration or the
candidate during evaluation. Recorded intervals must agree with the order and
must not overlap within a pair. Unit and measurement IDs cannot be reused across
pilot and evaluation.

`independence` references an object with exactly `schema_version`, `kind`,
`status`, `unit_id`, `method`, `measurement_ids`, `evidence`.
The kind is `beryl.performance.independence`, status must be `verified`, and
measurement IDs are exactly `[a.measurement_id, b.measurement_id]` in that order.
`evidence` references nonempty retained review/collector evidence.

`method` is `separate_owned_sessions` or `verified_reset_equivalence`. Separate
sessions cannot be reused by another measurement. A reset-equivalence receipt
must cover both named runs and their initial-state equivalence; shared session
IDs are permitted only under that explicitly reviewed method. Frame-level
sampling is not an admitted independence method.

### Measurement receipt

Keys: `schema_version`, `kind`, `measurement_id`, `unit_id`, `session_id`, `status`,
`started_utc_ns`, `ended_utc_ns`, `fingerprints`, `paid_ns`, `total_paid_ns`,
`resources`, `semantic`.

Kind is `beryl.performance.measurement`; status must be `complete`. Identifiers
use the experiment-ID spelling rule. UTC nanosecond timestamps are positive,
strictly ordered, and consistent with the freeze/selection/evaluation boundaries.
`fingerprints` contains digest strings for exactly `artifact`, `compiler`,
`toolchain`, `environment`, `workload`, `semantic_contract`. Artifact identity
selects the baseline or candidate according to the side of the pair.

`paid_ns` contains exactly `setup`, `capture`, `compute`, `maintenance`,
`invalidation`, `conversion`, `cleanup`, `cold_refresh`. Components must describe
disjoint costs actually paid by the admitted application operation. Their sum
equals positive `total_paid_ns` and cannot exceed the recorded interval. Include
warmup/cold or compilation costs in an appropriate paid component when the
application actually pays them. Harness duration is not a substitute for these
measurements. Zero is an explicit measured/applicability assertion, not a default
for an unknown or unavailable component.

`resources` contains exactly `peak_bytes`, `retained_bytes`, `allocations`,
`text_bytes`, `build_ns`, `edit_check_ns`. Physical peak and retained bytes cover
the frozen workload boundary; retained cannot exceed peak. Allocation counts
must be measured by an admitted collector. Missing instrumentation is unavailable
evidence, not zero allocations. Compile/edit measurements are separate resource
budgets even when the gameplay operation does not pay compilation time.

`semantic` contains exactly `status`, `expected_cases`, `completed_cases`, `events`,
`stdout`, `state`. Status is `complete`; case counts are positive and equal.
The three observations are file references. Both sides must have equal complete
case selections and byte-identical ordered events, stdout and final state.
This format admits exact byte comparisons only; numerical tolerances or omitted
state require a separately versioned contract. Empty output/event files are
permitted when the complete admitted operation truly has no such observations.

### Freeze and candidate evaluation

`freeze` produces `beryl.performance.freeze` with `schema_version`, `kind`, `pilot`,
`frozen_utc_ns`, `policy_sha256`, `threshold`, `pilot_p95_absolute_variation`,
`unit_ids`, `session_ids`, `measurement_ids`, `evaluator_sha256`.
It records the actual CLI freeze time. Retain that file unchanged. Candidate
evaluation reloads/rechecks the pilot and recomputes the freeze contents rather
than trusting a threshold copied into a request.

An evaluation request contains exactly `schema_version`, `kind`, `freeze`,
`candidate`, `selection`, `role`, `blocks`. Kind is
`beryl.performance.evaluation`. Freeze, candidate artifact and selection are file
references. Role is `training`, `selection` or `held_out`.

The selection receipt contains exactly `schema_version`, `kind`, `status`,
`candidate_sha256`, `selected_utc_ns`, `prior_workload_sha256`, `evidence`. Kind is
`beryl.performance.selection`; status is `frozen`; evidence is nonempty. Selection
must occur after the pilot freeze and before every evaluation measurement.
Prior workload digests are unique lowercase SHA-256 strings. A held-out workload
cannot appear in this prior tuning list. Completeness of that history is another
external review obligation; the evaluator cannot detect unreported tuning.

## Statistical and resource decision

For each independent pair, improvement is `(A_paid - B_paid) / A_paid`. Positive
values mean lower candidate whole-operation cost. Pilot noise is the nearest-rank
95th percentile of absolute paired relative variation. The frozen practical
threshold is `max(1/20, pilot_noise)`. Arithmetic and thresholds use exact rational
numbers. Execution order does not change which labeled baseline is the denominator.

The estimator is the median paired improvement, not ratio of pooled totals, mean
speedup or tail latency. Sort N paired improvements and choose the largest rank k
whose two binomial tails at probability 1/2 total at most 0.05. The interval is
`[x_(k), x_(N-k+1)]`. The finite-sample coverage is reported; no random seed or
bootstrap is needed. This is the standard order-statistic/binomial median
construction described by [NIST](https://itl.nist.gov/div898/software/dataplot/refman1/auxillar/mediancl.htm).
Coverage relies on the admitted independent sampling population, not merely
distinct labels. No independence claim is inferred from the interval itself.

The lower interval bound must meet the frozen threshold. Every candidate block
must also meet absolute peak/retained/allocation limits and paired resource
ratios. Maximum configurable policies are 20% text growth, 2× build time and 10%
edit/check growth; callers may set stricter limits. A zero baseline resource
allows only zero candidate resource for a relative budget.

These whole-workload limits do not establish the separate 8 MiB/region or
64 MiB/process private-storage policies from the advanced plan. Additional
region/lifetime evidence remains necessary. `resource_observable_exact` rejects
changed peak, retained or allocation metrics even within budgets. Matching counts
still do not prove allocation ordering, failure behavior or counterfactual OOM
equivalence; the external semantic/resource gate must establish those claims.

## Results and evidence boundaries

Result kind is `beryl.performance.result`, status `evaluated`. Decisions are:

- `resource_budget_failed`: at least one candidate resource constraint failed.
- `threshold_not_supported`: the lower interval bound missed the frozen threshold.
- `selection_only`: numeric gates passed on training/selection data.
- `synthetic_gate_pass`: analytical synthetic data passed; no performance claim.
- `eligible_held_out`: collector evidence passed these held-out admission checks,
  conditional on the explicitly stated external trust obligations.

The output includes paired rational improvements, median, interval/rank/coverage,
threshold, violated resource metrics, policy/candidate/evaluator identities and
the trust boundary. `automatic_adoption` is always false. Measurement execution is
`not_run_by_evaluator`; tail-latency claims are unavailable. The evaluator must not
be used to multiply overlapping optimizations' speedups or claim general language
superiority from one admitted workload.

The tests retain synthetic input bundles and `results.json` under a fresh `build/`
directory. Their known margins, boundary/noise cases and malformed receipts test
the admission rule. They never turn their invented durations into benchmark data.
