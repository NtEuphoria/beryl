# Beryl: an advanced performance architecture and implementation program

Approved for implementation on 2026-09-07. This is the consolidated program
requested by the user. Completion evidence lives in
[BERYL_ADVANCED_IMPLEMENTATION_STATE.md](BERYL_ADVANCED_IMPLEMENTATION_STATE.md).
A proposed interface or exit gate below is not a claim of implemented support.

## 1. Objective and governing decisions

Build Beryl into a language that lets Claude, ChatGPT, and human authors write
straightforward mod logic while the compiler safely handles increasingly
sophisticated execution: efficient target operations, storage reuse, incremental
maintenance, result-stability checks, and specialized native kernels.

The performance ambition has three independently measured outcomes:

| Outcome | Required evidence |
|---|---|
| Better Enfusion performance | Generated implementations improve complete MESH workloads against preserved handwritten implementations |
| Competitive or superior native performance | Equivalent workloads compared with idiomatic and matched tuned Rust |
| Easier AI authoring | Fewer repair rounds and unsupported-API attempts, with no manual generated-code edits |

This plan extends the [SPARKOS implementation plan](SPARKOS_IMPLEMENTATION_PLAN.md)
using the [performance research report](BERYL_PERFORMANCE_RESEARCH_2026-09-07.md).
M3's isolated MESH candidate remains the established baseline; M4–M8 remain
incomplete at the start of this program.

The following decisions are fixed:

- **Enfusion usefulness comes first.** Native research proceeds alongside it where dependencies allow.
- **MESH mutation APIs migrate in stages.** Preserve the existing adapter first; subsequently move writers behind generated, tracked interfaces while preserving gameplay, wire formats, and object identity.
- **Released optimizations enable automatically when eligible.** Unverified targets and unsupported program shapes retain the ordinary implementation.
- **Performance takes priority within explicit budgets.** Bounded memory, binary-size, and optimized-build increases are acceptable. Ordinary edit/check cycles remain fast.
- **Allocation-changing optimization uses `resource_adequate_exact` by default.** Equivalence is claimed within declared resource and lifetime bounds. Identical out-of-memory outcomes are not implied.
- **Complexity must earn adoption.** An experiment can be completed and rejected. A failed hypothesis does not become a production dependency.
- **Keep C11 and Clang.** Do not replace the native backend with LLVM or MLIR during this program.
- **Keep current language semantics.** Preserve parameter modes, value semantics, numeric behavior, and immediate `defer`. No new lifetime syntax or model API dependency.
- **Preserve source and evidence.** Existing dirty changes, original behavioral fixtures, and rollback artifacts remain intact.

The consolidated plan belongs under `docs/`; roadmap summaries point here.
Implementation authorization does not waive any semantic or release gate.

## 2. Architecture and public interfaces

### 2.1 Shared compiler foundation

```text
Beryl source + typed companion descriptions
                    ↓
Resolved declarations, types, target bindings
                    ↓
Structured IR: values, places, control flow, effects, origins
                    ↓
Verified ordinary implementation
                    ↓
Optional admitted optimization plan
             ↙                   ↘
      Native C → Clang       EnforceScript → Enfusion
             ↘                   ↙
          Semantic evidence and workload measurements
```

The ordinary implementation remains available as fallback and comparison baseline.

| Concept | Responsibility |
|---|---|
| Declaration identity | Distinguish declarations, methods, fields, and specializations without relying on spelling |
| Logical value | Represent Beryl's independently observable values |
| Storage identity | Track backing allocations and aliases separately from local variables |
| Place | Identify a storage root plus field/index projections |
| Effect summary | Describe reads, writes, shape changes, allocation, escape, failure, and engine effects |
| Source origin | Preserve original spans, expansion origins, generated spans, and companion JSON pointers |
| Observation epoch | Identify a coherent state available to a query |
| Optimization plan | Record eligibility, assumptions, resource bounds, transformation, fallback, and evidence |

Use arena-backed indexed IR tables and existing interned types. Serialized
identities must be deterministic; never serialize process pointers. Initially
maintain conservative sequencing for effectful and potentially failing operations.
Split sequencing only when a verified transformation needs finer independence.

### 2.2 Compiler and tool interfaces

Keep existing commands compatible. Add these interfaces progressively:

| Interface | Defined behavior |
|---|---|
| `beryl context project` | Actual targets, capabilities, versions, source identity, supported subsets |
| `beryl context symbol <qualified-name>` | Signature, access modes, origins, effects, target restrictions |
| `beryl context binding <name>` | Separate extracted declarations from reviewed and tested contracts |
| `beryl context optimization <qualified-name>` | Selected/rejected plans, invalidators, bounds, evidence |
| `beryl build --save-native-evidence` | Retain generated C, exact arguments, tool identities, requested compiler evidence |
| `beryl build --lowering auto\|ast\|ir` | Explicit unsupported IR returns unavailable; never silently switches |
| `beryl build --opt auto\|off` | Enable eligible released Beryl optimizations or disable those families |
| `--disable-opt <family>` | Disable a named family; unknown names are errors |
| `beryl test --backend differential --lowering ast\|ir` | Compare AST reference with the explicitly selected native candidate |
| `beryl mod verify --scenario <name> --artifact <id>` | Installed typed scenario against an immutable artifact |
| `beryl experiment run <name> --target native\|enfusion` | Registered isolated experiment with complete evidence |

`--opt off` disables the new Beryl transformation families; it does not silently
change the selected Clang optimization level or arithmetic flags.

`--lowering auto` initially selects AST lowering. It selects IR only after the
relevant whole-program subset passes its release gate. Never mix incompatible
ownership conventions silently. The reference backend remains AST-based; an
incompatible lowering override is an error.

### 2.3 Companion descriptions and evidence

Preserve strict version-1 companions. Introduce version 2 only when adding typed
scenario selections, optimization policy, tracked components, and subsequent
whole-mod descriptions. Both versions remain readable. New fields require the
new version; do not reinterpret old descriptions.

Descriptions may select installed scenarios with validated parameters. They may
not embed shell commands, arbitrary scripts, or unvalidated engine code strings.

New APIs use a common versioned evidence envelope containing:

- Operation, stage, status, and required capability.
- Source, compiler, runtime, binding, artifact, experiment fingerprints.
- Diagnostics with original and generated locations.
- Semantic outcome, comparison status, and coverage.
- Raw log and trace references.
- Measurements and resource limits.
- Selected optimization and fallback identities.

Adapt existing result formats instead of renaming fields consumed by scripts.
Keep successful verification distinct from successful program execution; source
traps from timeout/cancellation; extracted declarations from verified signatures;
verified signatures from verified lifetime/ordering; and semantic validation from
demonstrated performance.

### 2.4 Experiment and trace architecture

Extend the existing local mod orchestrator, process abstraction, and Workbench
transport. Do not create a second editor bridge.

Initial installed scenarios:

- `probe.map.cursor`
- `probe.array.storage`
- `probe.canvas.retention`
- `trace.mesh.query`
- `trace.mesh.sensor`
- `trace.mesh.expiry`
- `compare.terrain.chunks`

Each scenario defines typed inputs, required capabilities, timeout, expected case
IDs, permitted outputs, and result interpretation. Ordered traces contain case
identity, sequence, epoch, event kind, source origin, and payload. A final receipt
contains record count, checksum, and the complete expected case set.

Object identities use fixture-generated tokens, not portable memory addresses.
Verify exact floating-point encoding per target. If the engine cannot expose the
required distinction, report that comparison capability unavailable; rounded text
does not establish bitwise equality.

## 3. Implementation workstreams and dependency gates

### Stage A — Reconcile the baseline and close verification gaps

**Purpose:** make subsequent optimization evidence trustworthy.

1. Capture source fingerprints and reconcile capability inventories.
2. Preserve PID/MESH candidate evidence without treating it as proof for changed bytes.
3. Reproduce large-integer `min`, `max`, `clamp` and saturating add/sub near signed boundaries in Enfusion.
4. Fix confirmed defects using verified integer bindings and valid intermediates.
5. Reconcile stale global `restrict`, Rust overflow, and measured-overhead claims.

Extend semantic verification to expected failures. The starting differential
driver runs native comparison only after reference success. Add dedicated fixtures:

```text
Expected outcome:
    return
    source_trap(kind, source_site, successful_observation_prefix)
```

A fixture can successfully verify an expected trap while its program still has
a trap outcome. Ordinary failing tests retain failure behavior. Native checked-loop
fixtures use test-only registered output-root observations to inspect the successful
prefix before abnormal termination. Corroborate instrumented findings with optimized
IR/assembly, because instrumentation changes optimization.

**Exit gate:** missing traps, wrong first sites, missing prefix writes, and extra
writes are detected. Timeout, cancellation, missing tools, and incomplete traces
never match source traps.

### Stage B — Complete dependable engine context and AI tooling

**Purpose:** close M4 infrastructure needed by later engine experiments.

Generalize PID/MESH ownership and identity checks: executable version/hash,
plugin-tool identity, loaded projects, compiled artifact token, source hashes.
Separate headless compilation, VM execution, host gameplay, profiling, allocation
inspection, and visual inspection. Start/stop only owned sessions. Serialize
operations sharing Workbench. Reject stale completions and changed artifacts.

Generate source mappings for ordinary statements, prepared expressions, default
expansion, constructors/export wrappers, value helpers/later cleanup, and companion
locations. Retain raw diagnostics; expose raw locations when column/origin mapping
cannot be established reliably.

Implement project, symbol, binding context before MCP. Both assistants consume the
same CLI and evidence contracts.

**Exit gate:** wrong project, stale token, empty selection, unknown/duplicate cases,
partial results, changed sources, timeout, cancellation, and unrelated sessions
all produce accurate outcomes.

### Stage C — Run the first Enfusion performance experiments

These start as isolated application fixtures, establishing opportunities rather
than automatic compiler capabilities.

#### C1. Verified map traversal

Compile the installed iterator interface; compare complete ordered key/reference
sequences to indexed traversal across insertion, replacement, removal, reinsertion,
empty maps, and repeated histories. Measure 16, 64, 256, 1,024, 4,096 entries, then
complete queries. Change read-only enumeration first; sweep mutation is separate.
If order differs or the contract remains insufficient, keep indexed traversal.
Do not sort away differences or substitute unverified `foreach`.

#### C2. Query intermediate elimination

Introduce an append-preserving provider path where required. Remove temporaries
only when all caller contracts remain satisfied. Use invocation-owned workspace.
Preserve duplicate resolution before filtering, map order, eligibility, projection,
acquisition, and cap decisions. The marker counter increments after slot/root
acquisition even when rendering fails. Preserve that behavior.

Freshness remains time-dependent. Caching symbol/position eligibility does not
permit skipping opacity updates or effectful widget setters. Unsupported providers,
excessive nesting, insufficient capacity, or unverified mutation select the original
pipeline before UI effects occur.

#### C3. Direct terrain chunk construction

Capture heights and pane inputs for command-data comparison. Build final chunks
directly with one current builder per band. Preserve row-major cell evaluation,
band order, within-band quad order, the 240-quad limit, winding, colors, layers,
sample lattice, and diagnostic behavior. Compare payloads before visual review.

The existing grid produces 6,241 relief quads / 12,482 triangles. Command count
depends on band distribution. Do not pool or mutate published arrays without
verified consumer lifetime. Direct construction can proceed without cross-render
pooling; unresolved essential lifetime behavior blocks adoption.

#### C4. Sensor scan generations

Add one last-seen generation per remembered contact. Stamp at the current visibility
point before `NONE` rejection. Preserve repeated dwell accumulation for repeated
evaluation. Move metadata alongside contact/dwell entries on swap-with-last removal.
Reset coherently before generation reuse. Do not reduce scan frequency, gimbal
updates, position reads, or physics traces as an exact optimization.

**Exit gate:** each adopted candidate preserves relevant complete traces, improves
its complete workload, and meets memory/lifetime limits. Failed candidates remain
documented experiments.

### Stage D — Introduce structured IR without optimization

Start with reference-supported `bool`, signed `i32`, finite `f32`, plain records,
fixed arrays, existing supported output strings, calls/modes, conditionals,
structured loops, returns, short-circuit evaluation.

Represent initialization, reads, replacement, moves, calls, checked indexing,
arithmetic failures, control exits. Preserve operand/argument order, assignment
destination/index evaluation, compound-assignment old-value reads, default expansion,
conditional short-circuit operands, and immediate `defer`.

The IR verifier checks types, declaration identity, initialization, projections,
exits, source provenance, resource limits. Reject unsupported operations; no
placeholder values. An independent IR evaluator may share types/event serialization,
but not evaluation implementations with emitters or runtime arithmetic helpers.

Compare analytical fixtures, AST reference, IR evaluator, AST-to-C O0/O2, IR-to-C
O0/O2. Migrate the full PID corpus through that matrix. Only after native parity
introduce EnforceScript IR lowering for the same bounded subset and repeat engine
comparison.

**Exit gate:** admitted semantics agree; deliberate ordering, arithmetic, branch,
state-update mutations are detected. Discrepancies stop migration before optimization.

### Stage E — Complete admitted storage, effects, and ownership

Track binding, logical value, backing storage, borrow/access lifetime, and engine
identity/retention separately. Infer conservative interprocedural effects to a
fixed point over recursive call groups; unknown callees retain worst-case relevant
effects. Missing information is not purity.

Admit storage in order: plain aggregate lifecycle; `List<T>` with recursively
admitted elements; needed strings; MESH-adapter maps; other types through new gates.

Assignment initially uses eager recursive copying; read-only parameters borrow;
`sink` transfers. Replacement preserves source reads. Cleanup covers normal and
structured early exits. Check capacity and byte arithmetic before allocating.
Failed allocation cannot publish a partial header. Reject invalidating mutation
during active element/iteration access, including through callees. Engine objects
remain outside ordinary deep-copy semantics.

Extend AST reference with a logical heap independent of native growth/cleanup.
**Exit gate:** nested/overlapping/self copies, moves, growth, early exits, lifecycle
repetition, and failure injection pass. Unsupported owning paths remain unsupported;
a partial subset is not complete ownership.

### Stage F — Migrate MESH writes behind tracked interfaces

Begin at store/collection boundaries: publication, RPC receipt, join-in-progress,
debug paths, removal, teardown. Inventory every writer and mutable escape; add
tracked interfaces while preserving the adapter; migrate bounded groups; enclose
covered fields/nested state; enable regions only with complete coverage. Unknown
external mutation scopes use ordinary paths.

Keep shared entity references; `Get` must not return detached snapshots. Distinguish
actual store entry/key, mutable `entity.m_sEntityId`, object generation, nested shared
component identity, world/store lifetime, cache generation, and accepted sequence.
ID-field mutation does not rekey a map. An object/component may belong to several
entries; invalidate all affected entries. Rejected `Publish` may follow an alias
mutation; record the preceding mutation independently.

```text
Invalidate affected derived state
        ↓
Perform original mutation
        ↓
Record actual transition and outcome
        ↓
Update/invalidate dependent caches
        ↓
Expose complete observation epoch
```

Deliver synchronously to registered regions initially; no event history or
distributed ordering. Reentrant/incomplete mutation makes optimized observation
unavailable: use original behavior without reordering gameplay. Before counters
exhaust, invalidate/clear at a quiescent boundary before reuse; no retained token
may appear current after wraparound.

**Exit gate:** aliases, same-reference rejected publication, nested sharing,
same-key replacement, ID mutation, reentrancy, world reset cannot expose stale results.

### Stage G — Ship the conservative expiry certificate

Use private states `Invalid`, `NoPositiveDeadline`, `LowerBound(B)`. For finite
admitted deadlines B is no later than every current positive deadline. At the
existing sweep callback clear the output as required, validate coverage/epoch/
predicate/time, return zero only with proof, otherwise run the original backwards
sweep, then refresh from survivors.

Earlier insertion/mutation lowers the bound; removal/extension may leave it early.
Unknown mutation, nonfinite data, changed predicates, lost coverage invalidate it.
No heap, schedule change, precise callback, or reordered removals.

**Exit gate:** identical removal sequences at identical callback times, including
boundaries/time discontinuities, and whole-trace improvement including tracking cost.

### Stage H — Generate one static incremental query

Admit bounded keyed input, explicit optional presence, scalar comparisons/Boolean
composition, pure total predicates, projection, bounded counts, insert/delete/
covered update/identity replacement, deterministic ordered output. Initially exclude
joins, recursion, arbitrary callbacks, f32 reductions, unverified providers.

Generate concrete typed cache records, not one heap node per expression:

```text
initialize(snapshot) → result, cache
apply_transition(cache, transition) → replacement cache, result delta
evaluate_full(snapshot) → result
```

Initially admit only the verified MESH store-provider configuration; changes use
ordinary queries. Preserve order: rebuild ordered output after shape changes;
incrementally maintain field-only changes when order stays fixed. Prefer entry/
generation tokens and resolve references under the epoch, avoiding unnecessary
strong retention. Capacity exhaustion invalidates/falls back, never limits gameplay.

**Exit gate:** initialization/every transition preserve ordered values and identity;
include maintenance, materialization, capture, cleanup costs.

### Stage I — Add certificate templates and bounded demand

Implement deadline lower bounds, simple total scalar classification regions, then
bounded integer winner separation with a complete tie rule:

```text
construct_witness(inputs, result) → witness
check_witness(witness, new_inputs) → ProvenSame | Unknown
```

`ProvenSame` covers the complete selected observation; stable winner is not unchanged
score. Guards are total/non-observing. Unsupported checks return Unknown, never a
new source failure. Defer geometric prediction/general f32 interval synthesis;
future spatial certificates must cover actual rounded operations and verified
observations. Sampled velocity is not a future-motion guarantee.

Then add one static acyclic demand region: `Cold | Clean | Dirty | Evaluating`.
Only pure total derivations without skipped required failure, cleanup, allocation,
or other observations can defer. Controllers, commands, expiry, replication remain
eager. Reopening synchronously refreshes at the original observation boundary.
Use whole-region eviction; no cross-region sharing initially. Recursive forcing
or reentrant mutation invalidates and selects ordinary evaluation.

**Exit gate:** full observations preserved; hidden-update/reopen and eviction traces
correct; maintenance and cold-refresh latency justify adoption.

### Stage J — Optimize native storage and checked loops

Order: fixed-value lifetime/interference; compatible storage reuse; caller destination;
owned-buffer reuse after E; static loop proofs; non-throwing eligibility guards;
checked-block whole-block replay; successful-prefix publication as a separate study.

Start with a rectangular fixed-array kernel, pure arithmetic, one final store per
iteration. Require stable storage, valid lengths, disjoint output, no callbacks/
allocation, per-intermediate range proofs. First block uses i32 multiplication then
i32 addition with defined i64 intermediates; that argument does not extend to
arbitrary i64. Failure precedence is iteration then source operation. Inactive lanes
never load invalid storage. Global `restrict` stays disabled; stronger aliases only
inside specifically verified kernels.

**Exit gate:** all failure sites/lanes/tails/overlaps/invalidators pass; machine output
confirms reduced work. Prefer whole-block replay unless prefix publication earns
the extra complexity.

### Stage K — Add bounded specialization, PGO, and search

Evaluate individually: O2/O3 with identical arithmetic; PGO verified train/merge/use;
ThinLTO after local probes; one private layout; at most two specialized variants plus
generic. Private layouts cannot affect engine entities, exports, serialization,
replication, observable enumeration. Setters invalidate assumptions before next use.
PID state evolution remains mandatory even with constant-looking gains/inputs.

Separate training, selection, held-out workloads; reject incompatible profiles.
After manual plans succeed, add a deterministic finite selector and independently
checked records. Then investigate bounded equality saturation only in small pure
total integer regions: two retained plans, 10,000 nodes/region, 50,000 rewrites/region,
two-second checker timeout/candidate. Timeout/exhaustion uses ordinary plans.

Search is explicit/offline. Normal builds consume checked plans/applicability and
never invoke models or unbounded search.

**Exit gate:** held-out performance, semantics, size, compile time, memory pass.
Bounded checker evidence is not an unbounded proof.

### Stage L — Integrate with whole-mod authoring and release

Continue M7: resources/dependencies; generated components/properties; prefabs;
layouts/events; scenarios; asset import/packing. Callbacks invoke ordinary Beryl
functions with explicit state/inputs; generated mutation interfaces feed the same
effects/epochs.

SPARKOS branding/capabilities stay in its package: semantic colors, map affiliation
separate, rebindable hints, honest pending/degraded/unavailable states; different
node capabilities. Authority/taint remain explicit. Optimization cannot erase
validation, make clamp universal sanitization, or make proxy-local state authoritative.
Whole-mod and optimization share mappings, bindings, scenarios, identity, diagnostics.
Assistants use the same implementation.

**Exit gate:** assistants change logic/properties/events/prefabs/scenarios through
documented interfaces and validate generated output needing no manual correction.

## 4. Verification, performance budgets, and release rules

### 4.1 Correctness matrix

| Level | Evidence |
|---|---|
| Language | Parsing, resolution, types, ownership, effects, admission |
| Independent semantics | Analytical fixtures, AST reference, IR evaluation |
| Native execution | O0/O2 and selected optimized candidates |
| Engine compilation | Exact staged EnforceScript artifact |
| Engine semantic comparison | Original/generated implementations on admitted inputs |
| Host integration | Actual MESH behavior/handover |
| Multiplayer | Dedicated server with two independent clients |
| Visual interaction | Current ultrawide and 1920×1080 |

Unavailable clients, profiling, serialization, engine capabilities leave gates open.
Use all 25 research counterexamples plus mutation-before-rejected-publication,
mutable-ID/actual-key difference, nested shared state across entries, source-trap/
harness confusion, unsupported-IR silent fallback, and instrumentation hiding machine
work differences. Small relevant checks during implementation; complete suites at
integration boundaries.

### 4.2 Pilot budgets

Initial engineering policies, not measured properties or permanent restrictions:

| Area | Initial policy |
|---|---|
| Native private optimization storage | 8 MiB/region; 64 MiB/process |
| Static cache | 4,096 entries/region; eight active regions/world |
| Cache delivery | Synchronous; no retained history |
| Demand sharing | Within one region only |
| Sensor metadata | One generation/contact; no added strong retention |
| Terrain | Existing grid, bands, chunks, payload, order |
| Specialized native code | Two variants plus generic |
| Code size | ≤20% text-section growth for affected benchmark |
| Optimized build time | ≤2× equivalent verified baseline |
| Ordinary edit/check overhead | Optional optimization adds ≤10% versus same correct foundation disabled |

Enfusion entry limits bound structure, not allocator bytes. Measure physical peak/
retained memory separately. Capacity selects fallback, never rejects supported
gameplay inputs. Retained strings/keys and coexisting transitions must fit recorded
lifetime budgets. `resource_observable_exact` disables allocation-changing transforms
until stronger resource arguments pass. Fallible reservation must be independent
of aborting helpers; success alone does not prove future allocations unaffected.

### 4.3 Measurement protocol

1. Freeze metric, dataset, resource policy, budgets before candidate timing.
2. Measure paired baseline-versus-baseline noise.
3. Threshold is max(5%, pilot 95th-percentile absolute paired variation).
4. At least 30 independent paired blocks, balanced order.
5. Session state is part of independence; reuse only with verified reset equivalence, otherwise separate owned sessions.
6. Uncertainty uses actual independent units, not correlated frames.
7. Include paid setup/capture/maintenance/invalidation/conversion/cleanup/cold refresh.
8. Fail on semantic mismatch or incomplete execution.
9. Use held-out workloads after tuning.
10. Compare combined plans to current best verified baseline; never multiply overlapping speedups.

Automatic adoption requires CI support for the predeclared practical improvement.
Tail latency needs adequate traces and explicit uncertainty. Compare native Beryl
to idiomatic equivalent Rust, matched algorithm/layout/reuse/cache Rust, tuned Rust
with equivalent PGO/CPU, and diagnostic handwritten C where useful. Record arithmetic,
failure, allocation, output differences. Unmatched comparisons cannot support
language superiority.

### 4.4 Optimization lifecycle

```text
Proposed → Implemented experimentally → Semantically validated
  → Performance validated → Integrated in isolated candidate
  → Released for explicit target/domain
```

Failures become rejected/unavailable with retained evidence. Automatic enablement
requires released revision, matching target/bindings, successful legality, admitted
input/resources, fallback, relevant performance evidence, no disable override.
Source changes invalidate source-specific plans/profiles. Compiler/engine changes
invalidate corresponding evidence until defined revalidation.

### 4.5 Promotion and rollback

Promote compiler-owned destinations only with matching prior hashes. Preserve
handwritten files, fixtures, rollback artifacts. Server/client store/sensor/expiry
changes require multiplayer acceptance before release; host success remains separate.
A performance release needs one adopted complete-workload improvement. A Rust
advantage needs the matched native experiment. Negative findings do not justify
weakening comparisons.

## 5. Execution organization and completion criteria

| Workstream | Ownership | Dependency boundary |
|---|---|---|
| Engine/authoring | Context, bindings, scenarios, maps, MESH experiments, whole mods | One engine-session/promotion owner |
| Compiler/native | IR, independent execution, effects, storage, evidence, loop/storage experiments | One integration owner for shared semantics |
| Incremental semantics | Gateways, epochs, expiry, caches, certificates, demand | No admission before storage/mutation gates |

Parallelize independent fixtures/tooling/bounded implementations. Coordinate shared
types, effects, ownership, events before consumers proceed.

Every stage packet records objective/subset; sources/consumers; interfaces; state
invariants; migration; positive tests/mutants; performance/budgets; fallback/rejection/
rollback; raw completion evidence/limitations.

Execution order: A; B; C/D in parallel; E/F; G; H–K through gates; L progressively.
Completion is per capability. Cursor evidence is not incremental queries; PID is
not complete ownership; faster native kernels are not faster Enfusion gameplay.

The end state is simple Beryl source with sophisticated implementation and a
toolchain that explains, tests, and substantiates every selected optimization.
