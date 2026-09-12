# Beryl: an execution architecture for exceptional performance and AI authoring

**Document type:** technical research blueprint and proposed implementation contract.
**Prepared:** September 5, 2026.
**Repository anchor:** c9400fd1c9430174ed10e3907a7cfca4555dc966.
**Scope of this delivery:** this document only; no implementation or benchmark run.
**Audience:** the Beryl owner, Claude Code, ChatGPT/Codex, compiler contributors.
**Status:** proposals awaiting experiments; executable examples below are design pseudocode.
**Review integration:** September 5, 2026; section 45 records solutions to the subsequent static compatibility review.
**Second review integration:** September 6, 2026; section 46 specifies repairs for the additional findings and corrects the affected contracts in place.

The review integration changes this blueprint only.
It does not mean the identified compiler defects have been fixed or reproduced by execution.
Sections 45 and 46 resolve earlier recommendations where they explicitly name a replacement policy.
The current language specification remains the authority for implemented behavior.

**Implementation follow-up (September 6, 2026):** the owner subsequently authorized
code changes. [FOUNDATION_IMPLEMENTATION.md](FOUNDATION_IMPLEMENTATION.md) records
the implemented foundation repairs, executing tests, real Workbench compile probes
and remaining blockers. Read it before implementing a historical finding again.
The performance models and larger subsystems in this blueprint remain proposals.

The ambition is to make Beryl unusually good at expressing and executing game logic:
fast enough to challenge carefully optimized Rust on selected native workloads,
efficient when lowered to EnforceScript, and straightforward for an AI to author,
check, debug, and validate against an actual Enfusion project.

This document turns that ambition into a candidate architecture with explicit
semantics, algorithms, data structures, acceptance criteria, and implementation tasks.
It deliberately makes choices so that an implementer can start a bounded experiment.
Those choices remain revisable when evidence contradicts them.

No performance figure in this document is a measured Beryl result.
All numerical examples are analytical illustrations or proposed experiment thresholds.
No snippet, command, annotation, schema, or subsystem introduced here should be
assumed to exist in the current compiler unless explicitly identified as existing.

## 01. How to use this blueprint

Read sections 02–05 first to understand the intended product and architecture.
Read sections 06–12 before implementing any optimization.
Read sections 13–23 to choose a bounded performance experiment.
Read sections 24–34 for Enfusion and AI development workflows.
Read sections 35–40 for measurements, validation, and implementation sequencing.
Read sections 41–44 for unresolved decisions, research context, and handoff rules.
Read section 45 before choosing implementation work: it connects the code review to
compatibility decisions, concrete repair designs, and experiment-specific gates.
Read section 46 with it: implicit returns, constants, defaults, observation ordering,
resource assumptions, and command outcomes are prerequisites for the affected tickets.

Quick navigation:

| Start here | Coverage |
|---|---|
| [Product and competition](#02-product-definition-what-beryl-is-for) | What Beryl should deliver and how to compare it with Rust |
| [Architecture](#05-the-proposed-architecture-in-one-model) | Phases, meaning, legality, and execution cost |
| [Semantics](#06-observable-semantics-the-optimizers-contract) | Effects, ownership, arithmetic, and observable failures |
| [Structured IR](#10-structured-semantic-ir) | Internal representation and proof records |
| [Performance experiments](#13-experiment-a-checked-block-execution-with-scalar-recovery) | Block execution, incremental work, layouts, bounds, and plan selection |
| [Target integration](#24-target-lowering-native-and-enforcescript) | Native lowering, EnforceScript, bindings, and engine phases |
| [AI authoring](#28-a-small-authoring-surface-for-ai-written-mods) | Canonical patterns, context, and repairs |
| [Workbench bridge](#31-a-local-workbench-bridge-with-explicit-capabilities) | Jobs, lifecycle, staging, provenance, and replay |
| [Measurements](#35-benchmark-methodology-that-can-support-a-strong-claim) | Fair baselines, statistics, and worked cost models |
| [Validation catalog](#37-validation-catalog) | 232 proposed acceptance cases |
| [Implementation tickets](#38-implementation-tickets-and-dependency-order) | 20 primary tasks and three bounded foundation tasks |
| [Assistant handoff](#43-handoff-instructions-for-claude-or-chatgpt) | Instructions for future authorized implementation |
| [Review solutions](#45-solutions-to-the-static-compatibility-review) | Compatibility rules, compiler repairs, and blocking evidence |
| [Second review repairs](#46-repairs-from-the-second-comprehensive-review) | Additional compiler defects, corrected semantic contracts, and regression requirements |

The companion documents are:

- [Original repository review](CODEX_REVIEW_HANDOFF.md).
- [Earlier performance hypotheses](PERFORMANCE_AND_ENFUSION_HYPOTHESES.md).
- [Current language specification](SPEC.md).
- [Current implementation status](STATUS.md).
- [Current compiler architecture](INTERNALS.md).
- [Current Enfusion workflow](ENFUSION.md).

The original review and hypotheses describe earlier repository snapshots.
They are context, not proof that every historical defect remains present.
In particular, ownership work is already in progress in the current working tree.
An implementer must reproduce a finding before treating it as an open defect.

Within this proposed architecture:

- MUST means a correctness or interoperability requirement for the proposed feature.
- SHOULD means the default engineering choice, with documented exceptions.
- MAY means an optional extension that is not needed for the initial experiment.
- RESEARCH means the mechanism has a plausible argument but needs validation.
- DEFER means implementation should wait for an identified prerequisite.

These words govern the proposed design, not the current implementation.
They do not authorize edits outside a future implementation task.

Each optimization must eventually have five artifacts:

1. A precise semantic precondition.
2. A transformation with a correct fallback.
3. A machine-checkable account of why the transformation is legal.
4. Tests that expose a plausible incorrect implementation.
5. A reproducible measurement against a competitive alternative.

An attractive name, a generated graph, or an impressive speedup estimate is not
one of those artifacts.

The central research question is:

> Can a language preserve enough domain meaning that its compiler automatically
> performs optimizations which otherwise require substantial manual engineering,
> while making the resulting program easier for an AI to understand and validate?

## 02. Product definition: what Beryl is for

Beryl is the language an assistant writes.
The assistant is a development tool, not a required part of program execution.
A normal Beryl build must not need a Claude API key, an OpenAI API key,
a network connection to a model, or an autonomous optimization agent.

The intended everyday workflow is:

1. Describe or edit a mod feature in Beryl.
2. Check types, ownership, target compatibility, and binding contracts locally.
3. Run fast tests of the engine-independent logic.
4. Generate readable EnforceScript and a precise source map.
5. Validate the generated artifact in the intended Workbench project.
6. Run an explicit scenario when engine behavior must be tested.
7. Read errors and profiles in terms of Beryl source.

AI friendliness means fewer ambiguities, fewer invented APIs, smaller repair loops,
and reliable evidence of completion.
It does not mean making the compiler interpret natural-language program semantics.

Beryl has two distinct performance products.

| Product | Executed artifact | Main comparison |
|---|---|---|
| Native Beryl | Native code through the C/Clang path initially | Equivalent optimized Rust |
| Beryl for Enfusion | Generated EnforceScript in the engine | Equivalent handwritten EnforceScript |

Native testing is valuable for pure logic, differential checks, and rapid iteration.
It does not demonstrate how fast the script VM will execute the same algorithm.
The Enfusion integration proposed here continues to use the script path.
It does not depend on loading a user-created native library into the game.

The language should make common mod tasks compact:

- Store and update controller state.
- Read a documented engine value.
- Validate client-originated data.
- Process a bounded collection of entities.
- Maintain a derived selection or membership set.
- Generate a component wrapper.
- Express a replicated operation with explicit authority.
- Write a test without starting the editor.
- Find the original source of a generated error.

The compiler should absorb mechanical complexity:

- Consistent generated names.
- Exact callback signatures.
- Ownership-preserving copies and moves.
- Bounds and arithmetic checks.
- Legal allocation reuse.
- Target-specific result representations.
- Binding version checks.
- Stable source provenance.

The author should choose observable behavior.
The compiler should choose equivalent physical execution where it can prove legality.

## 03. What would count as outperforming Rust

The strongest useful claim is workload-specific:

> On workload W, under contract C, using hardware H and toolchains T,
> Beryl implementation B completes the same observable work faster than
> Rust implementation R, with a reproducible uncertainty estimate.

A language name by itself is not a performance measurement.
An unoptimized Rust translation is useful as a starting baseline but cannot
establish superiority over carefully optimized Rust.

For every serious native comparison, keep three Rust baselines:

1. Clear idiomatic Rust implementing the reference algorithm.
2. Tuned Rust using the same algorithm, layout, and allocation strategy as Beryl.
3. A specialist Rust implementation using relevant libraries or manual techniques.

The third baseline is required when a mature implementation of the core technique
exists and can satisfy the same workload contract.
Record when integration effort prevents that comparison.
Do not quietly classify a missing competitor as a win.

Match these conditions:

- Input data and update traces.
- Integer overflow policy.
- Bounds behavior.
- Floating-point policy.
- Output ordering and tie-breaking.
- Allocation accounting.
- Thread count.
- CPU instruction availability.
- Initialization and warm-up policy.
- Profile-guided optimization access.
- Inclusion of plan transitions and index maintenance.
- Inclusion of input capture and output consumption.

Rust already supports profile-guided optimization.
Beryl using PGO is a useful implementation technique, not a unique advantage.
See the [Rust PGO documentation](https://doc.rust-lang.org/rustc/profile-guided-optimization.html).

The proposed competitive advantage has three levels:

| Level | Proposed advantage | Evidence required |
|---|---|---|
| A | Ordinary Beryl obtains an optimization automatically | Source and effort comparison |
| B | Beryl selects a better plan for a changing workload | Held-out end-to-end measurements |
| C | Beryl beats an equally tuned Rust implementation | Matched strongest-baseline measurements |

Level A is valuable even when machine-code performance is equal.
Level B is a systems result, including dispatch and transition costs.
Level C is the stretch performance goal.

Do not multiply several isolated speedups to predict an application result.
Two transformations may remove the same work.
A faster kernel may expose an engine bottleneck.
A new index may reduce CPU time while increasing memory pressure.

Report both successes and the fraction of programs where the optimization applies.
A compiler that accelerates one narrow loop and regresses common code needs
different product decisions from one that improves a broad workload family.

## 04. Repository grounding and migration boundaries

The current documented compiler is written in C11.
Its pipeline performs lexing, parsing, resolution, type checking, ownership checks,
and taint analysis before emitting either C or EnforceScript.
The backends currently use a typed AST.

The current architecture document explicitly rejects a shared low-level SSA IR
because reconstructing readable EnforceScript would be difficult.
That concern is valid.
This blueprint therefore proposes a structured semantic representation,
with native SSA-style lowering only after target-independent decisions.

Do not replace both backends in one change.
Do not treat an IR rewrite as a prerequisite for every useful tool improvement.
Preserve the current path while validating small supported subsets.

| Existing area | Proposed responsibility |
|---|---|
| src/parse/ | Preserve source syntax and stable source spans |
| src/sema/ | Resolve symbols and establish semantic contracts |
| Proposed structured IR module | Normalize meaning without discarding control structure |
| Proposed analysis module | Track effects, ranges, ownership, shapes, and versions |
| Proposed plan module | Construct and validate equivalent execution plans |
| src/back/ | Lower supported plans to the selected target |
| src/driver/ | Orchestrate builds with explicit artifacts and status |
| runtime/ | Provide small, specified target support operations |
| Proposed binding tooling | Describe and verify installed engine APIs |
| Proposed bridge adapter | Operate Workbench through a versioned protocol |

Names for new modules are provisional.
Choose concrete directory names during implementation after reviewing conventions.

Historical findings that matter as prerequisites include:

- Correct cleanup and ownership behavior.
- Exact evaluation order.
- Correct checked arithmetic lowering.
- Real module identity and visibility.
- Consistent target rejection for unsupported types.
- Reliable build failure propagation.
- Complete effect handling for intrinsic operations.

The subsequent static review mapped concrete instances of these issues to the
working tree at the repository anchor above; see section 45.1.
Use IMP-00 to refresh that evidence, IMP-00A for identity and compatibility,
IMP-00B for trustworthy local tooling, and IMP-00C for selected legacy execution repairs.
These are bounded dependencies, not a requirement to perfect the whole language
before measuring one safe native kernel.

This list is a dependency list, not a fresh audit finding.
Re-run focused reproductions against the implementation being changed.

The current working tree contains changes outside this document.
This blueprint does not interpret them as completed or failed implementations.
Future implementation work should record its own clean comparison point.

Preserve useful existing decisions:

- Small compiler deployment footprint where practical.
- Explicit numeric conversions.
- Explicit parameter access conventions.
- Stable diagnostic codes.
- Native tests for engine-independent logic.
- Readable generated script.
- A documented target profile.

Change a decision only with a concrete benefit and a migration plan.

## 05. The proposed architecture in one model

The proposed optimization unit is a **phase**.
A phase is a bounded computation over explicitly identified input and state.
It has known observable effects and a defined publication rule.

A phase is not necessarily a new language keyword.
Initially it can be an internal boundary inferred from a function
whose calls and effects are sufficiently understood.

The compiler separates three questions:

1. Meaning: what values, failures, writes, and commands must occur?
2. Legality: which changes preserve that meaning?
3. Cost: which legal implementation is likely to run best here?

The cost model must never answer the legality question.
A profile saying an index is usually valid does not prove it is valid.
A model recommending a rewrite does not establish equivalence.

The proposed compilation path is:

```text
Beryl source
  -> parsed syntax with source identity
  -> typed and resolved syntax
  -> structured semantic IR
  -> ownership, effect, range, and dependency facts
  -> reference execution plan
  -> optional equivalent candidate plans
  -> legality validation
  -> target feasibility checks
  -> bounded cost selection
  -> structured target lowering
  -> C/Clang or EnforceScript
  -> artifact manifest and source map
```

Every optimized phase retains a reference plan.
The reference plan is simple enough to inspect and use as a semantic oracle.
It is not merely the optimizer run with a different flag.

The architecture combines six sources of performance:

- Eliminate work that cannot change an observable result.
- Maintain derived results from changes instead of recomputing everything.
- Arrange data so each operation moves fewer irrelevant bytes.
- Reuse storage when lifetimes prove reuse safe.
- Move checks out of repeated execution only when their obligations remain satisfied.
- Choose among a small number of validated plans when workload shape changes.

An additional engine layer reduces avoidable crossings and boilerplate.
It does so only through documented binding contracts.

The proposed distinctive contribution is the composition:

> One semantic model connects incremental work, data layout, checked execution,
> engine boundaries, and AI-readable evidence.

That is an integration hypothesis.
Historical novelty and actual speedups require separate investigation.

## 06. Observable semantics: the optimizer's contract

Before optimizing a phase, define its observable outcome.
The proposed outcome model is:

```text
Outcome {
    schema_version
    semantic_profile
    resource_profile
    termination: Returned | Trapped | Diverged | Unknown
    return_value: optional typed value
    events: one ordered sequence of ObservableEvent
    trace_completeness: Complete | Truncated | Unavailable
}

ObservableEvent {
    sequence_in_observation_domain
    invocation_id
    parent_invocation_id
    kind: PublishedWrite | ExternalCallBegin | ExternalCallEnd |
          ObservableCleanup | Failure | Log | StatePublication
    typed_payload
    source_operation_id
}
```

An implementation does not have to allocate this structure at runtime.
It is a semantic description used by interpreters, tests, and proofs.
The single event order preserves ordering between writes, calls, cleanup, and failure.
Per-kind lists may be derived for display, but cannot be the independent equality oracle.
External call begin/end events contain the callbacks that occur between them.
Section 46.7 defines the observation domain, comparison fields, and truncation rules.
Unknown is an evidence state, not an additional language termination behavior.
Exact comparison requires complete evidence with established termination;
two unknown or incomplete records cannot establish equivalence.

For an exact transformation P -> P':

```text
for every supported initial state S and input I admitted by resource_profile:
    observe(execute(P, S, I)) == observe(execute(P', S, I))
```

The observation relation must be defined before using the equality.
For example, internal scratch addresses are normally unobservable.
Engine entity identity is observable.
Allocation counts are performance measurements unless allocation failure or
allocator callbacks are explicitly part of the language contract.
Resource adequacy must be an explicit domain restriction, not inferred from purity.
Under a resource-observable contract, changing an allocation can change termination
even when failure aborts without unwinding. Section 46.8 defines the two profiles.

The initial semantics should make these choices explicit:

- Expressions evaluate in a documented order.
- Short-circuit operators evaluate the second operand only when required.
- Assignment evaluates its destination according to one specified rule.
- Compound assignment evaluates an effectful destination exactly once.
- A checked operation fails at its own source site.
- A failing operation does not publish its result.
- Earlier visible writes remain visible under ordinary imperative semantics.
- Cleanup follows the defined scope-exit and failure policy.
- Undefined behavior is not an optimization permission in safe Beryl.

Decide whether a trap aborts the process, aborts a script operation,
or becomes a target-specific reported failure.
The targets need a common semantic category even if their termination mechanisms differ.
A target that cannot provide the selected category must reject that construct
or use a separately documented target contract.

### 06.1 Ordinary functions and staged phases

Ordinary functions preserve ordinary sequential effects.
They must not silently gain transactional behavior.

A proposed staged phase has a different explicit contract:

1. Read declared inputs.
2. Compute into private output/state storage.
3. Fail without publishing staged Beryl-owned outputs if computation fails.
4. Publish the completed Beryl-owned result.
5. Apply external commands through a separate, fallible adapter protocol.

This does not make arbitrary engine calls atomic.
Publishing Beryl-owned state and applying engine commands are separate events.
Their order must be selected deliberately for each adapter.

The first implementation should use ordinary functions.
Add staged phases only after their failure behavior is specified and tested.
Never use staged semantics to justify a rewrite of an existing imperative function.

### 06.2 Observation boundaries

An observation boundary is an operation that could expose intermediate state.
Examples include callbacks, engine calls, volatile access, and public state publication.
Logging is observable unless the source contract explicitly classifies it otherwise.

A local variable assignment can still matter because later cleanup may inspect it.
A destructor can make the timing of a move or drop observable.
An exception-like unwind can expose previously hidden intermediate work.

The initial optimizer should conservatively treat unknown calls as boundaries.
An explicit, verified summary may later narrow that treatment.

### 06.3 Correctness categories

Every optimization report must use one of these categories:

| Category | Meaning |
|---|---|
| Exact | Preserves the selected observation relation |
| Target-specific exact | Exact only under a named target contract |
| Approximate | Uses an explicit error/freshness contract |
| Heuristic choice | Chooses between already legal plans |
| Unsupported | No implementation satisfying the contract is available |

Do not label a heuristic plan choice as an approximate computation.
Do not label an approximate computation exact because typical inputs match.

## 07. Arithmetic, floating point, and failure precision

Arithmetic semantics are an optimization interface.
If they are vague, aggressive transformations cannot be justified.

The proposed initial exact integer contract is:

- Integer width and signedness are part of the type.
- Checked addition, subtraction, and multiplication fail on out-of-range results.
- Division by zero fails.
- Signed minimum divided by negative one follows an explicit failure rule.
- Shift counts outside the allowed range fail.
- Signed right shift has an explicitly specified result.
- Wrapping operations use modular arithmetic at the declared width.
- Saturating operations clamp to the declared type's endpoints.
- Conversions distinguish checked, wrapping, and explicitly lossy behavior.
- Constant evaluation uses exactly the same rules as runtime evaluation.

Do not implement narrow wrapping arithmetic through a wider signed C expression
that can overflow because of integer promotion.
Use defined unsigned operations or checked helpers with an established derivation.

### 07.1 Checked arithmetic creates order constraints

For checked i8 arithmetic:

```text
(127 + 1) + (-1)  -> fails at the first addition
127 + (1 + (-1))  -> returns 127
```

Associativity of mathematical integers does not justify this rewrite.
The fact that the final mathematical result fits is insufficient.
Each source intermediate has its own obligation.

The optimizer may reassociate only when:

1. Every removed intermediate is proven non-failing.
2. Every new intermediate is proven non-failing.
3. Remaining effects keep their required order.
4. The final value is equal under the declared arithmetic.

### 07.2 Floating-point modes

Start with a conservative strict mode.
Specify operand width, rounding points, contraction, signed zero, NaN handling,
and the relationship between native and engine arithmetic.

Strict mode should disable unapproved reassociation and contraction.
Bitwise equality across targets is a separate, stronger promise.
It may require software-defined operations or restricted expressions.
Do not promise it solely because both targets expose a type named f32.

Proposed modes:

| Mode | Contract | Initial use |
|---|---|---|
| strict-target | Fixed expression order and target FP contract | Default candidate |
| portable-exact | Explicitly portable operations and encodings | Selected replay/network logic |
| relaxed | Named permitted FP transformations | Opt-in performance experiments |
| approximate | Error and freshness contract | Isolated cosmetic systems |

A relaxed mode must enumerate allowed changes.
The phrase fast math is too broad to serve as a user-facing semantic contract.

### 07.3 Failure order as data

Represent a potentially failing operation with:

```text
FailureSite {
    source_span
    operation_kind
    sequence_region
    position_within_region
    cleanup_scope
}
```

Vector execution, loop fusion, and speculative evaluation must preserve the first
observable failure under the source order.
If two failures are independent but observable, independence does not authorize
choosing a different one.

### 07.4 Guard safety

A guard must be total over its input domain.
It must not contain the very undefined or failing arithmetic it intends to prevent.

For example, a buffer-size guard must check multiplication safely.
Computing count * element_size in a narrow type and then comparing it is invalid.
Guard construction must use checked operations or a proven wider representation.

LLVM has explicit undefined-behavior concepts that downstream optimizations use.
Generated code must not accidentally grant those permissions.
See the [LLVM undefined behavior manual](https://llvm.org/docs/UndefinedBehavior.html).

## 08. Ownership, value semantics, and storage

Retain the existing conceptual parameter modes:

- let: read access.
- inout: exclusive mutation access.
- sink: ownership transfer.
- set: initialize an output.

The implementation must establish the actual guarantees before emitting aliases
or attributes that depend on them.

This blueprint proposes the following ownership policy:

1. Small copyable values can be copied implicitly.
2. An owning value transferred through sink is no longer usable by the caller.
3. Read access does not grant independent ownership.
4. Mutable access is exclusive for its defined lifetime.
5. A value copy, implicit where already permitted or explicitly requested, produces independent logical values.
6. Storage reuse is allowed only when it preserves those logical values.

Do not introduce reference-sharing behavior accidentally through backend representation.
A generated class used to implement a Beryl value needs correct copy semantics.
A native list header copy must not become a double owner of one allocation.

Preserve existing value assignment: a permitted `var b = a` does not become a move
or a new compile error merely because the representation owns heap storage.
Represent that operation internally as a semantic copy; optimize its physical cost
only when independence, failure behavior, and cleanup remain correct.
An optional explicit duplication API may make cost visible without replacing
existing assignment semantics. Its name and availability remain undecided.
Do not introduce mandatory explicit cloning in this implementation sequence.
Section 45.5 specifies recursive copying, storage ownership, and staged rollout.

### 08.1 Places and projections

Ownership analysis should operate on structured places:

```text
Place {
    root: LocalId | ParameterId | GlobalId | StorageId
    projections: [FieldId | ConstantIndex | DynamicIndex | Dereference]
}
```

Do not cap the projection path at an arbitrary small field depth.
Do not cap checked argument access at a small fixed number of parameters.
If the analysis has a resource budget, exhaustion must produce a conservative result.

Places can be classified:

- Equal.
- Proven disjoint.
- Potentially overlapping.
- Unknown because the representation escapes.

Different fields are disjoint only when their representation and operation support it.
Different dynamic indices are not disjoint without an inequality fact.

### 08.2 Definite initialization

Track initialization per relevant field or place.
At a branch merge, a place is initialized only if every reachable predecessor
initializes it.
Zero-iteration loops do not establish initialization after the loop.
Break, continue, return, and failure edges participate in the analysis.

An inout argument requires an initialized value.
A set argument requires a legal writable destination; it may be uninitialized
or an already initialized mutable value, as the current checker permits.
The callee cannot read the logical output before assigning it.
Every ordinary return must discharge the assignment obligation, including a
return carrying an error-union value; a returned error is not an aborting trap.
Initialized immutable bindings and read-only borrows remain invalid destinations.
Owning replacement and cleanup require the additional policy in section 45.2.
Compound assignment reads before it writes.
Cleanup must not read a field whose initialization never completed.

### 08.3 Borrow duration and escape

The first view system should be second-class:

- A view can exist within a function or phase.
- It can be passed to a verified non-escaping call.
- It cannot be stored in a heap object.
- It cannot outlive the owner.
- It cannot survive structural mutation of its backing collection.

This restriction keeps authoring and implementation tractable.
General stored references can remain a later language decision.

Inferred short-lived views should cover ordinary iteration.
The author should not need to annotate every loop with proof machinery.

### 08.4 Cleanup and allocation failure

Define destruction order before aggressively eliminating copies.
Move analysis must transfer responsibility for cleanup exactly once.
Partially initialized aggregates need a known cleanup policy.

Preserve v0.1's documented immediate `defer` behavior during compatibility repairs.
Both backends must execute its expression exactly once where written.
Introducing lexical scope-exit `defer` is a separate, versioned language change;
an optimizer must not introduce it incidentally by adding cleanup scopes.
Compiler-managed ownership cleanup is a separate obligation from user `defer`.
See section 45.7 for the migration boundary.

Choose and document an allocation failure contract.
Aborting out-of-memory still changes the Returned-versus-Trapped observation.
It does not by itself justify removing or adding allocations.
Use the resource profile in section 46.8 to state the supported execution domain.
Preserve the existing public abort behavior; recovery from an optional private
allocation requires a separate fallible internal operation and a resource argument.

## 09. Effects and dependency versions

An effect summary must describe more than pure versus impure.
Use a small compositional vocabulary:

```text
Effects {
    reads: set of abstract storage regions
    writes: set of abstract storage regions
    changes_shape: set of collection identities
    allocates: None | Bounded(bytes) | Unknown
    may_fail: set of failure kinds
    calls_engine: set of binding identities
    reads_time: boolean
    reads_random: boolean
    observes_identity: boolean
    publishes_state: boolean
    escapes_access: boolean
    unknown: boolean
}
```

Set elements must use resolved identities, not source spelling.
Summaries for recursion require a conservative fixed point.
If convergence is not reached within a budget, widen toward unknown effects.
Never silently accept a partially computed optimistic summary.

### 09.1 Version dimensions

One global mutation counter is safe but often too coarse.
Use version dimensions that match actual dependencies:

- Content version of a field or column.
- Shape version of a collection.
- Identity version of a slot.
- Membership version of a query.
- Configuration version.
- Snapshot epoch.
- Binding contract version.

Range facts about a length depend on the relevant shape version.
Cached scores depend on the input fields actually read.
An engine handle lookup depends on identity validity at application time.

### 09.2 Invalidation examples

| Operation | Invalidates |
|---|---|
| Change row.health | Facts and derived values reading row.health |
| Push to list | Length, backing storage, and relevant iterator facts |
| Change list element | Facts about that element's content |
| Delete entity | Identity-dependent and membership-dependent values |
| Change scoring weights | Scores derived from those weights |
| Unknown engine call | Every affected region that cannot be excluded |
| Advance simulation time | Computations that read time or evolve state |

An immutable snapshot may retain facts even if the live engine changes.
Those facts describe the snapshot, not the current world.

### 09.3 Effect inference for authoring simplicity

Infer effects from code and binding contracts.
Use annotations to require a property, not to assert it without checking.

Proposed examples:

```text
@no_alloc means: reject if any reachable operation may allocate.
@pure means: reject observable writes and uncontrolled external inputs.
@budget means: check a named resource bound when one is derivable.
```

These annotations are proposed contracts, not existing language guarantees.
An unknown effect should explain the responsible call in a diagnostic.
The assistant should receive a path from the requested property to the blocking call.
Current taint labels and user annotations are not range or authority proofs.
Until these contracts are implemented, feature context must mark them unavailable.
The future strict checking path must diagnose unsupported contract annotations;
parsing an attribute name must never count as implementing its guarantee.

## 10. Structured semantic IR

Call the proposed representation Structured IR in implementation discussions.
The exact abbreviation and directory name are secondary.
Its important property is retaining source-level control structure and meaning.

The IR must represent:

- Typed values and resolved symbols.
- Structured sequences, branches, and loops.
- Explicit evaluation order.
- Places and access modes.
- Potential failure sites.
- Cleanup scopes.
- Collection shape operations.
- Engine bindings by stable identity.
- Provenance from source to generated operations.

It should not initially represent CPU registers, calling-convention details,
or every instruction available in LLVM.

### 10.1 Core entities

```text
Program {
    modules: Module[]
    types: TypeTable
    symbols: SymbolTable
    bindings: BindingTable
    semantic_version: Version
}

Function {
    id: FunctionId
    signature: Signature
    parameters: Parameter[]
    body: Region
    effects: EffectSummary
    origin: OriginId
}

Region {
    id: RegionId
    parameters: ValueId[]
    operations: Operation[]
    exit: RegionExit
    cleanup_scope: ScopeId
}

RegionExit =
    Yield(values)
  | Return(values)
  | Break(loop_id, values)
  | Continue(loop_id, values)
  | Fail(failure_site)
  | Unreachable(proof)
```

Regions preserve nesting for script emission.
An analysis may build a temporary control-flow graph view.
That view does not replace the structured representation used by the backend.

### 10.2 Operation families

```text
Value operations:
    Constant, MakeAggregate, ExtractField, SelectValue

Place operations:
    ReadPlace, InitializePlace, AssignPlace, MovePlace, DuplicateValue

Arithmetic operations:
    CheckedAdd, CheckedSub, CheckedMul, CheckedDiv
    WrappingAdd, WrappingSub, WrappingMul
    FloatAdd, FloatMul, CheckedConvert

Collection operations:
    Length, ReadElement, WriteElement, Reserve, Resize, Push
    BeginView, EndView, IterateStable

Control operations:
    IfRegion, LoopRegion, ShortCircuitRegion, Call, ScopeRegion

Lifetime operations:
    Allocate, InitializeStorage, DropValue, ReleaseStorage

Boundary operations:
    CaptureInput, CallBinding, PublishState, AppendCommand
```

The first prototype needs only the subset used by one experiment.
An unsupported AST form remains on the current backend path.
If unsupported forms enter a requested optimized region, reject the plan clearly.

### 10.3 Ordered effects without flattening everything

Use logical effect dependencies between operations.
For initial implementation, one sequence token per region is acceptable.
Later, partition tokens by proven independent effect domains.

A read of private immutable input need not consume a global engine token.
A checked operation must retain its failure-order dependency.
A call with unknown effects consumes every relevant conservative token.

An operation may have several dependencies:

```text
score = CheckedMul(a, b)
    data_dependencies: [a, b]
    failure_predecessor: previous_checked_operation
    origin: source multiplication
    policy: checked_i32
```

Do not erase failure dependencies when proving memory independence.
Memory disjointness and exception ordering are different obligations.

### 10.4 Normalization rules

Normalize complex expressions into explicit evaluation steps.
Retain the structured branch for short-circuit evaluation.
Introduce temporaries for destinations whose computation has effects.
Bind every local to a unique identity before name generation.

Example input meaning:

```text
items[next_index()] += compute_delta()
```

Required normalized sequence, assuming this chosen evaluation order:

```text
i = call next_index()
p = checked_element_place(items, i)
old = read(p)
d = call compute_delta()
new = checked_add(old, d)
write(p, new)
```

The language specification must select the exact order first.
The normalizer must implement that order, not invent it.
The recommended initial contract is explicit in section 45.4, including calls,
short-circuit branches, destination validity, and cross-pipeline calls.

### 10.5 Verifier invariants

Every IR verifier run must check:

- Every value use refers to a valid definition.
- Definitions dominate their uses under structured control flow.
- Types match the operation's semantic rule.
- Region exits match the enclosing construct.
- Place roots and projections are valid.
- Moves are not duplicated.
- Cleanup obligations remain discharged.
- Effect dependencies are well formed.
- Failure sites retain valid source provenance.
- Facts referenced by an operation are valid at that operation.
- Target-independent IR does not contain unexplained target assumptions.

Verification should run after each experimental transformation in development builds.
Release compiler builds may combine checks only after profiling their cost.
A malformed IR must produce a compiler error, not generated source.

## 11. Facts, proof obligations, and versioned capabilities

Optimization facts are structured records, not comments.
The proposed format is:

```text
Fact {
    id: FactId
    proposition: TypedPredicate
    subjects: SubjectId[]
    dependencies: VersionDependency[]
    scope: RegionId
    establishment: StaticProof | RuntimeGuard | LanguageRule
    witness: ProofWitness
    invalidators: EffectPredicate[]
}
```

Example predicates:

- 0 <= index < length(storage, shape_version).
- storage A and storage B do not overlap during region R.
- field X lies in [-1024, 1023] at content version V.
- callback C cannot resize collection A.
- output storage is private until publication P.
- this iteration performs exactly one observable store.

### 11.1 Proposed experiment: versioned execution capabilities

RESEARCH: package a set of established facts into an internal capability
whose validity is tied to storage identity, version, and lexical scope.

This is not a user-granted security capability.
It is compiler bookkeeping that prevents repeated validation of unchanged facts.

Example:

```text
FixedViewCapability {
    storage_id
    shape_version
    length
    access_mode
    disjoint_group
    region_id
}
```

The capability may be established statically.
Otherwise, an entry guard checks the required relationships once.
Subsequent operations in the region use the established facts.

Structural mutation ends the capability's validity.
An unknown escaping call ends validity unless the call is excluded by the contract.
Copying the bookkeeping record must not extend its scope.
Runtime-facing representations must not be forgeable through ordinary Beryl values.

On the native path, a runtime overlap guard needs a defined implementation.
Do not subtract unrelated C pointers or perform out-of-object pointer arithmetic
to calculate a guard.
If using an address-integer representation, document the target ABI assumptions,
check interval-end arithmetic for overflow, and validate the guard independently.
Prefer static ownership evidence when it makes runtime address reasoning unnecessary.

### 11.2 Why this might help

Repeated array length, alias, and shape checks can dominate small script kernels.
A phase boundary may prove that these properties remain unchanged across many uses.
One validated region can then support several optimizations at once.

The improvement is conditional:

```text
saved repeated validation cost
    > entry validation + version tracking + capability management
```

Static facts should not incur runtime version tracking merely because this model exists.
If ordinary compiler analysis already removes every repeated check,
the capability representation may improve engineering clarity without runtime gain.

### 11.3 Proof checker design

The initial checker should understand a small finite set of proof rules.
Avoid a general theorem prover in the first compiler prototype.

Candidate rules:

- Constant interval containment.
- Interval intersection after a branch.
- Length equality established by an entry guard.
- Disjoint roots from exclusive ownership.
- Non-overlap of statically known field projections.
- Monotone loop index within fixed bounds.
- Effect summary excluding shape mutation.
- Dominance of a guard over a use.
- Exact match of dependency versions.

Each rule has explicit premises and a conclusion.
The transformation supplies a witness.
The checker independently verifies the witness against the current IR.

### 11.4 Invalidation algorithm

```text
for operation in region evaluation order:
    verify facts used by operation
    determine written regions and changed versions
    invalidate facts depending on those versions
    establish facts implied by the operation
    propagate facts to successor regions
    intersect valid facts at merges
```

Loops require a fixed point or a verified loop invariant.
An analysis iteration limit must fall back to a weaker fact set.
It must not turn non-convergence into a proof.

### 11.5 Required counterexample

Start with a valid view over a list.
Call a function that may push to the same list.
Attempt to reuse the old bounds/alias capability afterward.
The verifier must reject the use even if the push rarely occurs.

This one counterexample should exist before any optimization consumes the capability.

## 12. The optimization pipeline and trusted components

The proposed pass order is deliberately conservative.
It exposes useful structure before asking for advanced transformations.

```text
01 resolve and type-check
02 normalize evaluation order
03 build cleanup and access structure
04 verify Structured IR
05 infer conservative effects
06 perform definite initialization and ownership analysis
07 establish ranges, shapes, and version dependencies
08 construct reference phase plan
09 eliminate proven dead pure work
10 remove proven redundant copies and checks
11 identify eligible query and loop regions
12 generate bounded physical-plan candidates
13 verify candidate legality
14 reject candidates unsupported by the target
15 estimate or measure candidate cost
16 select a plan within resource budgets
17 lower with source provenance
18 verify target representation invariants
19 emit artifact and optimization report
```

Earlier passes may expose opportunities for a second bounded analysis pass.
Use explicit iteration budgets.
Record why another iteration was useful.
Do not create an unbounded optimize-until-stable loop over mutually enabling rewrites.

### 12.1 Trusted computing base

The correctness argument depends on:

- Parser and type rules.
- Source-to-IR normalization.
- Ownership and effect summaries.
- Proof-rule checker.
- Runtime helper semantics.
- Target lowering.
- External binding contracts.

Candidate search does not need to be trusted to choose a correct plan
if every candidate must pass independent legality checks.
It still needs resource limits and robust input handling.

Benchmark results do not belong in the proof checker.
Profile thresholds may choose a legal plan but cannot establish its preconditions.

### 12.2 Adoption path

First, build a Structured IR dump for a tiny subset.
Compare it with source evaluation traces.
Next, lower that subset through a reference emitter.
Only then introduce one transformation.

Keep a feature flag at the compiler-development level.
The flag selects the experimental pipeline, not weaker language semantics.
Generated artifacts must identify the selected pipeline version.

During migration, never combine old and new ownership rules silently.
Define which subsystem is authoritative for each compiled function.
If both analyze it, disagreement should be visible to compiler developers.

### 12.3 Dependency strategy

A custom structured representation is the initial candidate.
MLIR could be reconsidered if the number of transformations justifies its cost.
Its Transform dialect is relevant to explicit scheduling infrastructure.
See the [MLIR Transform documentation](https://mlir.llvm.org/docs/Dialects/Transform/).

Do not migrate to a large framework simply to obtain an optimizer-shaped API.
Evaluate compiler size, build complexity, debugging, and EnforceScript readability.
The first experiment should be implementable without a wholesale toolchain replacement.

## 13. Experiment A: checked block execution with scalar recovery

RESEARCH: execute several independent checked iterations together,
while preserving the failure behavior of the original scalar loop.

The initial supported kernel is deliberately narrow:

```text
for i in 0 .. n:
    t = checked_i32_mul(a[i], b[i])
    u = checked_i32_add(t, c[i])
    out[i] = u
```

Required preconditions:

- All four views have at least n elements.
- Input lengths and storage identities remain fixed.
- Inputs are immutable throughout the region.
- Output does not overlap any input.
- Each iteration depends only on its own input elements.
- Each iteration has one final store.
- No callback, destructor, logging operation, or external observer occurs inside.
- All relevant failure sites are represented explicitly.
- The scalar fallback is independently correct.

Do not generalize the first prototype to arbitrary loops.
Division, callbacks, reductions, and multiple interleaved stores are separate projects.

### 13.1 Block algorithm

For a block of W iterations:

1. Load the active input lanes safely.
2. Compute the multiply in a representation that cannot overflow.
3. Test each multiply result against the source i32 range.
4. Compute the addition without introducing implementation overflow.
5. Test each source addition against the i32 range.
6. If every active lane is valid, publish the block's outputs.
7. Otherwise, publish none of this block and run its original scalar iterations.
8. Let the scalar execution produce the successful prefix and first failure.

For this exact i32 multiply/add kernel, signed i64 intermediates can represent
the mathematical products and subsequent additions of i32 inputs.
This argument does not extend automatically to source i64 multiplication.

Pseudocode:

```text
for block_start in blocks_of_width(n, W):
    active = min(W, n - block_start)
    valid = true

    for lane in active_lanes(active):
        i = block_start + lane
        wide_product[lane] = exact_wide_mul(a[i], b[i])
        mul_ok[lane] = fits_i32(wide_product[lane])
        wide_sum[lane] = exact_wide_add(wide_product[lane], c[i])
        add_ok[lane] = fits_i32(wide_sum[lane])
        valid = valid and mul_ok[lane] and add_ok[lane]

    if valid:
        publish_checked_narrowed_outputs_in_allowed_order()
    else:
        execute_original_scalar_block()
```

The inner computation is a candidate for SIMD lowering.
The pseudocode itself does not imply that a compiler will vectorize it.
Inspect generated code and measure the selected instruction sequence.

### 13.2 Why recovery preserves semantics

No speculative operation publishes state.
Speculative arithmetic uses defined implementation operations.
Inputs cannot change between speculative execution and scalar replay.
Previously completed blocks have already produced exactly their scalar outputs.
The failing block starts with no speculative writes visible.
Scalar replay therefore reproduces the required prefix and first failure.

The implementation must not call a checked helper during speculation
if that helper traps before recovery can run.
It must calculate a value and validity information without observable failure.

Inactive tail lanes must not perform out-of-bounds loads.
A later mask cannot legalize an earlier invalid load.

### 13.3 Cost model

Let:

- Cs(W) be the scalar cost for a successful block.
- Cv(W) be vector computation cost.
- G(W) be checks and dispatch overhead.
- q(W) be the chance the block takes recovery.

A rough successful-work model is:

```text
expected block work ~= Cv(W) + G(W) + q(W) * recovery_work(W)
```

For an illustrative independent per-iteration failure probability p:

```text
q(W) = 1 - (1 - p)^W
```

Real failures are often correlated.
A trapping program also stops early, so multiplying this estimate by every block
can badly misrepresent total execution time.
Measure success throughput and failure latency separately.

### 13.4 Experiment design

Compare:

- Ordinary scalar checked Beryl.
- Generated C with the proposed block transformation.
- Rust scalar with equivalent checked operations.
- Rust implementing the same block/recovery algorithm.
- Any vectorization already produced by Clang without the new transformation.

Vary W, input size, alignment, and failure position.
Include every source failure site in every lane.
Include n less than W and n just above a multiple of W.

Retain the transformation only when it improves representative workloads
after accounting for code size and recovery behavior.
LLVM's existing vectorizers provide useful baselines and diagnostics.
See [LLVM vectorization documentation](https://llvm.org/docs/Vectorizers.html).

## 14. Experiment B: range-driven physical precision

RESEARCH: keep source types stable while selecting narrower internal storage
or arithmetic when proven value ranges allow it.

The goal is primarily to reduce data movement and increase useful SIMD density.
Narrow scalar arithmetic is not inherently faster on every CPU.

Example:

```text
Source field:
    energy: i32

Established invariant:
    0 <= energy <= 4095

Candidate physical storage:
    packed unsigned 16-bit column

Read semantics:
    exact widening to source i32
```

The source type remains i32.
The compiler must not change public ABI or serialization because a profile
contained small values.

### 14.1 Sources of range evidence

Acceptable evidence:

- A type-level refinement with checked construction.
- A proven branch condition dominating every use.
- A validated configuration bound.
- A complete entry scan followed by a versioned immutable view.
- A static derivation from already bounded operands.

Unacceptable evidence:

- A training workload never used a larger number.
- A field name suggests a small range.
- A comment says the value is usually positive.
- An AI claims a value cannot overflow.

### 14.2 Two implementation levels

Level 1: static narrowing.
Use only compile-time proofs.
Keep the original physical representation when proof fails.
This level avoids runtime scanning and representation transitions.

Level 2: guarded representation.
Validate a batch, create a compact private representation, and reuse it
while its content and shape dependencies remain valid.
Include conversion, validation, and invalidation in the cost model.

Do not initially mutate a public collection between wide and narrow storage.
Use a private phase-local or cache-local representation.
This limits alias and ABI complications.

### 14.3 Profitability condition

Let conversion cost be C.
Let each subsequent use save d units of time.
Let maintenance cost per update be m and update count be u.
For k uses, the candidate helps only if:

```text
k * d > C + u * m + extra_dispatch
```

The planner must account for the expanded working set if both representations remain.
Compression that adds a second copy can lose on peak memory.

### 14.4 Arithmetic narrowing rules

A source i32 addition can use a narrower operation only if:

1. Operands are represented exactly.
2. Every source intermediate's required behavior is preserved.
3. The selected narrow operation cannot introduce an extra overflow.
4. Widening the result reproduces the source result.

If only the final result fits, that is not sufficient.
A narrow multiply followed by cancellation may overflow even when the result is small.
Use widened arithmetic where the proof requires it.

### 14.5 Experimental extension: certified bit packing

DEFER: pack bounded booleans or small enums into bitsets for query evaluation.
This can accelerate membership operations and reduce memory footprint.
It also adds extraction costs and may create write contention in a future
multithreaded edition.

Do not pack independently observable volatile or atomic fields together.
Do not use bitset iteration order unless it matches the query's declared order.
Engine-facing field layouts remain unchanged.

## 15. Experiment C: derive an incremental program

RESEARCH: compile selected pure derived computations into two programs:

1. A full evaluator.
2. An updater that maintains the same result from input changes.

The intended relation is:

```text
apply_result_delta(Q(S), D(S, input_delta))
    == Q(apply_input_delta(S, input_delta))
```

This relation must include ordering, identity, duplicate handling, and failure policy.
It is easiest to establish first for total, pure queries.

Start with a stable-key filter:

```text
eligible = entities where entity.alive and entity.team == selected_team
```

The result is a deterministic sequence ordered by a declared stable key.
Membership depends on alive, team, entity identity, and selected_team.
Position changes do not invalidate membership.

### 15.1 Initial supported query language

Support:

- A finite keyed input table.
- Pure field predicates.
- Total comparisons.
- Projection of selected fields.
- Stable deterministic ordering.
- Insert, update, and delete events.

Defer:

- Arbitrary effectful callbacks.
- Recursive queries.
- Unbounded joins.
- Floating-point reductions.
- Queries with observable intermediate checked-arithmetic failures.
- Opaque engine object traversal inside the query.

This is a restricted optimization region, not a restriction on all Beryl code.
Unsupported computations use full ordinary execution.

### 15.2 Incremental filter state

```text
FilterState {
    predicate_version
    input_epoch
    membership_by_key
    ordered_result_keys
    projected_values_by_key
}
```

For each update, retain the old value or enough old projected fields
to determine whether a previous result must be removed.
A delete event cannot be processed correctly if required prior state is missing.

For the first filter, use an identity lookup plus an ordered membership structure
with a documented complexity model.
A balanced ordered tree is one candidate when stable keys are arbitrary.
A dense bitset is another when iteration order can be defined by a bounded key space.
A sorted vector has cheap traversal but potentially linear insertion/removal.
Choose one representation for the first experiment and include its real update costs.

Do not materialize a new complete result list after every event unless the consumer
requires it.
Offer a stable iterator or maintain the required materialization explicitly.
If every phase consumes K results, the cost of visiting those K results remains.
Incremental membership does not eliminate downstream dense processing.

### 15.3 Event processing

```text
apply_event(state, event):
    verify expected input epoch and identity generation
    find prior membership for event.key
    determine new row state, if any
    evaluate total predicate on new row

    if previously_present and now_absent:
        remove key from ordered result
        remove projected value

    if previously_absent and now_present:
        insert key in declared order
        store projected value

    if previously_present and now_present:
        update changed projected fields

    advance accepted version
```

Handle duplicate event IDs according to an explicit delivery contract.
Either require exactly-once ordered input or implement deduplication with bounded state.
Do not assume that a network or engine callback provides exactly-once delivery.

### 15.4 Full recomputation fallback

Use full recomputation when:

- A relevant global configuration changes.
- Too much input changed.
- Event history is incomplete.
- State version does not match the trace.
- An index invariant fails.
- A memory budget requires dropping incremental state.

Fallback must reconstruct a result from a coherent current input snapshot.
It must not merge a partially updated old index with a new unrelated snapshot.

### 15.5 Dense fallback crossover

Let N be row count and rho the fraction changed.
An illustrative model is:

```text
Tfull  = N * c_scan
Tdelta = c_fixed + rho * N * c_update
```

For N = 100,000, c_scan = 40 ns, c_update = 220 ns,
and c_fixed = 0.08 ms:

```text
Tfull = 4.00 ms
Tdelta = 0.08 ms + 22.00 ms * rho
break-even rho ~= 0.178
```

These are invented cost inputs, not benchmark results.
Skew, ordered insertion costs, cache behavior, and fan-out can change the crossover.
Measure thresholds on held-out traces.

This model estimates query maintenance only.
If both plans must enumerate or serialize a complete result, add that shared cost.
If one plan requires additional materialization, add that plan-specific cost too.
The large apparent membership speedup can shrink substantially in the full phase.

## 16. Incremental extensions and exact temporal decomposition

After the filter works, extend the algebra one operation at a time.
Each extension needs an update rule and a counterexample suite.

### 16.1 Keyed joins

For signed multiset deltas over an exact algebra:

```text
delta(A join B)
    = (deltaA join B)
    + (A join deltaB)
    + (deltaA join deltaB)
```

The cross term matters when both sides change.
The formula assumes A and B denote the old state.
A sequential-update implementation may account for the cross term differently.
Specify the chosen convention to prevent double counting.

Machine integers are not unbounded mathematical multiplicities.
Restrict counts to proven bounds or define a failure contract that the updater preserves.
Do not introduce a different intermediate-overflow behavior accidentally.

Measure fan-out as well as changed-row count.
One changed key joining to half the world is not a cheap sparse update.

### 16.2 Aggregates

Count is a reasonable next aggregate with a checked, bounded cardinality.
Integer sum needs an explicit accumulation and overflow contract.
Minimum and maximum need replacement handling when the winning row is deleted.
Top-k needs deterministic tie-breaking and an index whose maintenance cost is measured.

Floating-point sum is not algebraically invertible under ordinary machine rounding.
Subtracting the old contribution and adding the new one can differ from full evaluation.
Use a separately specified accumulation contract or retain full recomputation.

### 16.3 Exact temporal decomposition

Split a system by what actually changes:

- Rare configuration-derived values.
- Event-driven membership.
- Per-tick external observations.
- Per-tick evolving internal state.
- Output publication.

For a controller:

```text
configuration changes -> recompute coefficients
membership events     -> maintain eligible entities
every tick             -> read current observations
every tick             -> advance controller state
every tick             -> produce required outputs
```

Unchanged inputs do not imply unchanged state.
A PID integral can evolve while setpoint and measurement remain constant.
A timer can expire without an entity field changing.

The compiler may cache a pure coefficient calculation.
It may not skip state evolution unless it proves an exact closed-form transition
for the elapsed steps under the selected arithmetic and observation contract.

### 16.4 Proposed closed-form transition experiment

DEFER: identify a restricted integer recurrence with no intermediate observations,
prove a batched transition, and compare it with repeated scalar steps.

Example mathematical candidate:

```text
x_next = x + constant_delta
```

A batch of k steps appears to equal x + k * constant_delta.
Under checked arithmetic, intermediate failures still matter.
Under floating point, rounding can differ.
The initial experiment therefore needs bounded integer ranges proving every
intermediate safe and no observer between steps.

Treat a timer's externally visible callbacks as observations.
Batching must reproduce their ordering and count.
If that is expensive, the recurrence optimization may not be useful.

### 16.5 Relationship to existing research

Incremental computation and differential dataflow are established research areas.
Beryl's hypothesis is integration with its language, effect model, and engine boundary.
Compare against relevant implementations, including Rust implementations.

Useful starting sources:

- [Differential dataflow explanation](https://www.frankmcsherry.org/differential/dataflow/2015/04/07/differential.html).
- [Differential dataflow implementation](https://github.com/TimelyDataflow/differential-dataflow).
- [Adapton research paper](https://www.cs.tufts.edu/~jfoster/papers/cs-tr-5027.pdf).

## 17. Experiment D: jointly select layout and schedule

RESEARCH: choose data representation and execution order together.
Layout changes which operations are cheap.
Schedule changes which fields are live and how long intermediates must remain.
Optimizing either in isolation can select the wrong plan.

Candidate representations:

- Array of structures.
- Structure of arrays.
- Small blocks containing structure-of-arrays fields.
- Hot fields separated from cold metadata.
- Dense rows indexed by stable handles.
- A sparse index plus a dense iteration list.
- Compact bounded fields established by section 14.

Start with Beryl-owned tables.
Engine-owned object layout is outside this compiler's control.

### 17.1 Logical identity and physical row

A table element has a stable logical identity.
Its physical row may change during compaction.
Use a mapping rather than treating a row number as identity.

```text
Handle {
    slot
    generation
}

SlotEntry {
    generation
    row
    alive
}

DenseRow {
    owning_slot
    hot_fields
}
```

Deletion updates both directions of the mapping.
Moving the last row into a gap updates the moved row's slot entry.
External references use handles, not raw row positions.

Generation exhaustion needs a defined policy.
Retire an exhausted slot or use another non-resurrecting strategy.
Silently wrapping the generation can make an ancient handle valid again.

### 17.2 Field-use graph

Build a graph with fields as vertices.
Connect fields used together by a hot operation.
Weight edges using measured or static access frequency.

Use this graph to propose clusters.
Do not treat graph clustering as a correctness rule.
The legality checker separately handles identity, ABI, and access constraints.

A candidate layout records:

```text
LayoutPlan {
    logical_type
    physical_columns
    field_to_column_mapping
    row_identity_mapping
    conversion_operations
    supported_access_patterns
    invalidating_operations
}
```

### 17.3 Logical traffic example

Suppose a source record is 128 bytes and a kernel reads six f32 fields.
The fields contain 24 bytes of useful data per record.
For 100,000 records:

```text
record footprint = 12.8 MB
selected field payload = 2.4 MB
logical ratio ~= 5.33
```

This is not a 5.33x speedup prediction.
Cache lines, prefetching, write allocation, and actual access patterns determine traffic.
The generated script VM may have entirely different object and array costs.

### 17.4 Joint planner constraints

The planner must preserve:

- Observable iteration order.
- Stable identity.
- Required failure order.
- Ownership and aliasing rules.
- Public field behavior.
- Wire and persistence schemas.
- Target representation support.

The planner must budget:

- Conversion time.
- Extra indexes.
- Peak temporary storage.
- Code size.
- Compile time.
- Runtime dispatch.
- Maintenance under churn.

Enumerate a few useful layouts first.
A general combinatorial optimizer should wait until measured cases justify it.

## 18. Experiment E: lifetime-directed storage reuse

RESEARCH: use the phase's lifetime graph to avoid repeated allocation
and to place results directly into their final destination.

The first win should come from eliminating unnecessary temporaries.
A custom allocator is not automatically required.

### 18.1 Destination passing

When a result has a known final destination, construct it there if:

- The destination is not observable before successful initialization.
- Reads needed for construction do not alias overwritten storage.
- Failure cleanup remains correct.
- The result's logical ownership transfers correctly.

Example:

```text
naive:
    temporary = build_large_value(inputs)
    destination = duplicate(temporary)
    destroy(temporary)

candidate:
    build_large_value_into_uninitialized_destination(inputs, destination)
```

An in-place assignment into an already initialized value has additional obligations.
The old value may need to remain available if construction fails.
Do not confuse initialization with assignment.

### 18.2 Lifetime graph

Represent each temporary allocation with:

- Size expression.
- Alignment.
- Construction point.
- Last possible use.
- Cleanup requirements.
- Escape classification.
- Whether address identity is observable.

Two allocations may share storage only when their live ranges cannot overlap
and their alignment and initialization requirements are satisfied.
Control-flow alternatives require path-sensitive reasoning or conservative overlap.

An interference graph can guide storage assignment.
The resulting reuse plan still needs a verifier.
Graph coloring alone does not establish correct lifetime handling.

### 18.3 Scratch region policy

Proposed initial scratch policy:

- One private scratch region per phase invocation.
- A statically bounded stack portion where practical.
- Optional reusable heap storage owned by the phase instance.
- Explicit reset after all contained values are destroyed.
- No escaping references.
- A generic allocation fallback when allowed by the source contract.

A no-allocation contract cannot use a hidden allocating fallback.
It must reject an unproven bound or return a documented capacity failure
through an explicitly fallible interface.

### 18.4 Reentrancy

A scratch buffer stored on a component is not automatically safe.
Callbacks can re-enter the component before the first invocation finishes.

Possible policies:

- Prove the phase cannot re-enter.
- Allocate separate storage per invocation.
- Reject re-entry with a documented behavior.
- Queue the invocation under an explicitly different scheduling contract.

The compiler must not infer non-reentrancy solely from a single-threaded target.
Single-threaded execution can still have nested callbacks.

### 18.5 Script reuse

EnforceScript may support useful container reuse, but its exact costs need measurement.
Do not equate native capacity management with an engine array's implementation.

Reusing an object requires resetting all observable state.
Old engine references must not retain access to an object reassigned to another role.
Callbacks, replication identity, and registration can make pooling illegal.

Start with private numeric arrays and private generated value containers.
Measure clear, resize, construction, and access behavior on the installed engine.

### 18.6 Resource budgets

Resource bounds are useful even without hard real-time guarantees.
The compiler can sometimes establish maximum collection size or scratch demand.
That is different from guaranteeing completion before a wall-clock deadline.

Report:

```text
statically established:
    maximum scratch payload = 64 KiB

measured:
    p99 phase duration under benchmark trace = result from actual run

unknown:
    operating-system scheduling delay
```

Never convert a memory bound into a latency guarantee.

## 19. Experiment F: exact demand-driven selection

RESEARCH: optimize for the values the program actually needs to observe,
using proven bounds to avoid computing results that cannot affect that observation.

Example workload:

> Select the highest-scoring eligible target, with a stable identity tie-breaker.

A straightforward implementation computes every full score.
A different exact plan can evaluate inexpensive score bounds first.
If a candidate cannot beat the current winner, its expensive exact score is unnecessary.

This model combines:

- Explicit selection semantics.
- Total pure scoring.
- Admissible bounds.
- Stable ordering.
- Versioned cached information.
- A full-evaluation fallback.

### 19.1 Required score contract

The first prototype should use bounded integer scores.
Every supported score evaluation must be total and side-effect free.
All source arithmetic must be proven non-failing.

If evaluating a losing candidate would have trapped in the source program,
skipping it changes semantics.
Therefore an ordinary eager loop with potentially failing scores is ineligible.

A dedicated query can define total selection semantics.
Alternatively, the compiler can prove the ordinary loop total before transforming it.

### 19.2 Bound contract

For candidate x:

```text
lower(x) <= exact_score(x) <= upper(x)
```

The bound carries dependencies on all input and configuration versions used to derive it.
Its calculation must itself be total.
An invalid or unavailable bound means evaluate the exact score.

The compiler must not infer a bound from a sample maximum.
Statistical confidence is not an admissible exact bound.

### 19.3 Selection algorithm

```text
best = no_candidate

for candidate in a permitted deterministic traversal:
    interval = obtain_valid_bound(candidate)

    if best exists and interval cannot beat best under the full tie rule:
        continue

    score = evaluate_exact_score(candidate)

    if (score, candidate.identity) outranks best:
        best = (score, candidate.identity)

return best
```

For descending score with smaller identity winning ties,
an upper bound equal to the best score is not enough to skip a smaller identity.
Compare the best possible complete ordering tuple.

Traversal may change only if totality and the observation contract permit it.
If traversal order is itself observable, preserve it.

### 19.4 Group bounds

A spatial cell or table block can carry a bound for every member.
If that bound cannot beat the winner, skip the whole group.

The group bound must cover all current members.
Insertion, position changes, and configuration updates may invalidate it.
A conservative enlarged bound is safe but may reduce pruning.
A stale underestimated bound is incorrect.

For a new group member, update or invalidate the bound before exposing the new epoch.
Never publish membership and bound metadata from different epochs.

### 19.5 Exact maintenance under change

Cached exact scores can be reused when their dependencies remain unchanged.
Bounds may be cheaper to refresh than exact scores.
Combine incremental membership with demand-driven score evaluation.

The planner now chooses among:

- Full dense scoring.
- Incremental exact-score maintenance.
- Bound-first selective scoring.
- Group-bound pruning followed by exact scoring.

All plans must return the same result.
An adaptive selector can use dirty fraction and bound effectiveness as cost signals.

### 19.6 Why this could be a substantial win

If exact scoring is expensive and bounds reject most candidates cheaply,
the plan performs less meaningful work, not merely faster instructions.
The possible gain is therefore larger than many local code-generation tweaks.

It can also lose badly:

- Bounds are nearly as expensive as scores.
- Most intervals overlap the winner.
- Maintaining group metadata costs more than scanning.
- Inputs change too rapidly for reuse.
- Small collections make setup dominate.

The experiment must include all of these cases.
An equally optimized Rust implementation can use the same method.
Beryl's proposed advantage is deriving and composing it from a constrained query.

## 20. Equivalent plans and safe adaptive selection

RESEARCH: retain a small set of exact plans and select among them
using workload information available cheaply at the phase boundary.

A plan descriptor is:

```text
PlanDescriptor {
    plan_id
    semantic_hash
    required_facts
    target_capabilities
    representation
    transition_in
    execution_entry
    transition_out
    scratch_bound
    code_size
    validation_evidence
    measurement_domain
}
```

All selectable exact plans share the same semantic hash.
Approximate plans belong to a different contract and cannot enter this set silently.

A matching hash identifies a claimed contract; it does not prove equivalence.
Compute the contract identity from canonical semantic data.
Validate each implementation against that contract through the independent legality path.
Never accept a candidate merely because it supplied the expected hash string.

### 20.1 Dispatch features

Good initial features:

- Input count.
- Dirty row count.
- Whether an incremental cache is valid.
- Whether a compact representation already exists.
- A verified CPU feature set for native execution.
- A known target configuration.

Avoid collecting expensive statistics merely to choose a plan.
Include feature-collection cost in the measurement.

### 20.2 Transition economics

Suppose switching costs C and the new plan saves d per subsequent phase.
For an estimated useful horizon H, switching is worthwhile only if:

```text
H * d > C + uncertainty_margin
```

The horizon estimate is a heuristic, not a semantic assumption.
An incorrect estimate may lose time but must not change results.

Use hysteresis to avoid repeated switching near a crossover.
For example, require a stronger signal to enter a specialized plan
than the signal used to remain in it.
Measure the threshold; do not hard-code an invented universal dirty percentage.

### 20.3 Failure and invalidation

A plan precondition failure selects the generic plan.
A broken internal invariant is a compiler/runtime defect and needs visible reporting.
Do not hide repeated invariant failures behind silent fallback in validation builds.

Representation transitions must preserve:

- Logical values.
- Stable identities.
- Pending update semantics.
- Cleanup ownership.
- Required ordering.

If a transition reports a recoverable failure after partial private construction,
destroy only its initialized private values and retain the valid prior representation.
An aborting allocator cannot report such a failure and must not be used on this path.
Do not publish new mappings or redirect live handles until construction succeeds.
Account for old and new representations being live together.
Section 46.8 also covers the effect of retained indexes on later required allocations.
Public transition semantics and unrecoverable failures follow the selected profile.

### 20.4 Initial limits

Start with at most two or three plans per eligible phase.
Make plan count, code size, and compile-time budgets configurable for experiments.
Prefer a static plan on the script target until dispatch overhead is measured.

## 21. Bounded schedule search

RESEARCH: search a finite space of legal schedules during development or release builds.
Normal compilation should remain predictable and usable offline.

Initial search should be ordinary enumeration with pruning.
Do not require a machine-learning model.

Candidate schedule dimensions:

- Full versus incremental evaluation.
- Row versus column layout.
- Scalar versus checked block kernel.
- Scratch strategy.
- Materialization points.
- Static specialization constants.
- Small tile sizes.

### 21.1 Proposed schedule representation

```text
schedule phase target_selection:
    require semantic_contract exact_integer_selection_v1
    choose membership incremental_filter
    choose scoring bound_first
    choose layout hot_columns
    choose scratch private_reusable
    limit generated_variants 3
    limit scratch_bytes 65536
    fallback reference_dense
```

This is an internal design sketch, not proposed everyday Beryl syntax.
An assistant should not need to write schedules for ordinary mods.
Advanced tuning can expose them later as inspectable artifacts.

### 21.2 Search stages

1. Enumerate candidates within a fixed budget.
2. Reject candidates whose semantic preconditions cannot be established.
3. Reject candidates unsupported by the target.
4. Reject candidates exceeding static resource limits.
5. Rank remaining candidates using a simple cost model.
6. Optionally benchmark a small finalist set on training inputs.
7. Validate the selected candidate on held-out inputs.
8. Persist the choice with source, toolchain, and workload fingerprints.

Training performance must not be reported as held-out performance.
A search budget spent finding a winner is part of compiler/tooling cost.

### 21.3 Equality saturation

DEFER: use equality saturation only in pure, total expression regions
with arithmetic policies attached to every operation.

Rewrite rules must account for checked overflow and floating-point behavior.
The identity f() * 0 == 0 is invalid when f has effects or can fail.
An e-graph does not make an invalid equality true.

Relevant infrastructure exists in [egg](https://github.com/egraphs-good/egg).
Adoption requires evaluating implementation complexity and rule validation.

### 21.4 Optional AI involvement

An AI may propose a schedule or a new rewrite candidate during development.
The compiler must check it by the same rules as any other candidate.
Model output cannot grant safety facts or engine capabilities.

This optional research workflow is separate from compiling Beryl programs.
It is not required for Claude or ChatGPT to write Beryl source.

## 22. Fast compilation and specialization discipline

Runtime optimization is not the only performance requirement.
An assistant benefits from short, deterministic check-and-repair cycles.

Proposed development build priorities:

- Fast parsing and checking.
- Stable diagnostics.
- Minimal repeated work.
- Predictable memory usage.
- Clear target incompatibility errors.

Proposed release build priorities:

- More expensive interprocedural analysis.
- Bounded specialization.
- Optional profile use.
- Optional schedule search.
- Full artifact provenance.

### 22.1 Incremental compilation keys

Cache a result only when every semantic dependency is represented.
Candidate key components:

- Normalized source content.
- Imported public semantic interfaces.
- Compiler semantic version.
- Target profile.
- Binding contract fingerprint.
- Arithmetic and security policies.
- Relevant build configuration.
- Optimization pipeline version.

Filesystem timestamps alone are insufficient.
An imported effect summary can change optimization legality without changing a function name.
Invalidation must account for semantic interface changes.

### 22.2 Specialization limits

Specialize on proven constants or explicitly selected configurations.
Do not specialize on observed values without a runtime guard.

Budget:

- Variants per function.
- Total specialized code size.
- Recursion depth of specialization.
- Time spent constructing candidates.
- Memory used by analysis.

When a budget is exhausted, use the generic implementation.
Report the reason in optimization diagnostics.
Compilation should not fail merely because an optional optimization was expensive.

### 22.3 Determinism

Use stable iteration orders for maps that affect emission.
Separate build identity from source semantics.
Do not include random nonces in semantic hashes.

If an existing platform workaround requires varying an executable artifact,
record that separately from the deterministic generated-source identity.
Do not claim byte-for-byte reproducible executables while such variation remains.

## 23. Parallelism and approximation: separate research tracks

Do not make general parallelism a prerequisite for this architecture.
The initial Enfusion plan respects the target's actual threading model.
No compiler annotation can create unsupported engine threading facilities.

### 23.1 Future native parallelism

Potentially parallel regions require:

- Disjoint writes.
- Safe shared reads.
- No unsupported external calls.
- Defined reduction behavior.
- Defined failure ordering.
- A measured scheduling crossover.

An exact parallel checked loop must still handle failure publication correctly.
Worker completion order is not source iteration order.
Private computation plus ordered publication is a possible design,
but its buffering and cancellation costs must be included.

### 23.2 Approximation

Approximation is an explicit semantic extension.
It cannot be used to inflate an exact Beryl-versus-Rust comparison.

A proposed approximation contract includes:

```text
ApproximationContract {
    value_domain
    error_norm
    maximum_error
    units
    maximum_age
    assumptions
    discontinuity_rules
    exact_fallback
}
```

Start with cosmetic, non-authoritative behavior.
Do not start with damage, inventory authority, or exact collision decisions.

For a quantity changing at a proven rate no greater than V,
holding an old value for age h gives an error bound V * h.
The age includes capture, queueing, and delivery delay.
An empirical average velocity is not a worst-case proof.

If a decision threshold lies inside the result's uncertainty interval,
recompute exactly or use a separately specified conservative decision.
Do not silently choose a side.

### 23.3 Defer conditions

Defer approximation until exact plans, replay, and error reporting work.
Defer parallel engine execution until a supported engine capability is verified.
These tracks should not delay useful exact single-threaded optimizations.

## 24. Target lowering: native and EnforceScript

The shared semantic contract does not imply identical implementation techniques.
Each target must advertise what it can represent and validate.

### 24.1 Native path

Keep C/Clang as the initial native backend.
A direct LLVM backend is a possible later experiment, not a prerequisite.

Emit:

- Defined integer operations.
- Explicit checked helpers where needed.
- Correct alignment and object lifetimes.
- Alias information only when proven.
- Stable names based on resolved symbol identity.
- Source provenance for generated helpers and operations.

Inspect optimized assembly for benchmark finalists.
Otherwise a frontend transformation may appear to help while Clang already
performs the same optimization on the baseline.

C restrict and LLVM alias attributes have specific semantics.
Do not emit them merely because a parameter is named inout.
The ownership proof must cover the actual accesses and lifetime involved.
See the [LLVM language reference](https://llvm.org/docs/LangRef.html).

### 24.2 EnforceScript path

Retain structured loops, conditions, classes, and methods.
Favor generated code that can be traced back to Beryl without reverse engineering.

Potential script improvements include:

- Fewer repeated engine calls where contracts permit caching.
- Fewer temporary generated objects.
- Less duplicated container traversal.
- Exact incremental membership.
- Reused private arrays.
- Simpler specialized branches.
- Elimination of unused helper emission.

Do not assume CPU SIMD operations are available through ordinary script.
Do not infer engine object memory layout from the native backend.
Do not use native kernel speedups as predicted script speedups.

### 24.3 Target capability table

Each language construct should have an explicit target status:

```text
Supported:
    target preserves the chosen semantics directly

Emulated:
    target uses documented support code with the same contract

Restricted:
    supported only under an explicit condition

Rejected:
    no correct lowering is currently available
```

Every target-specific rejection should occur before artifact promotion.
Generating a zero value or omitting a loop is never a valid unsupported-feature strategy.

### 24.4 Numeric representation

The current Enfusion profile emphasizes i32 and f32.
Any extension to other widths needs an explicit representation and cost model.

For checked i32 addition, a helper may establish safety through comparisons
before evaluating the sum.
Its comparison expressions must themselves remain within range.
For multiplication, sign cases and the signed-minimum corner require separate care.

Do not assume a wider engine integer exists without verifying the installed API.
A correct emulation may be slower than rejecting the feature for a hot path.
Make that cost visible to the author.

### 24.5 Values, options, and errors

Generated reference classes must preserve source value ownership.
Options must distinguish absence from a valid zero-like value.
Error results must retain the error identity required by the source contract.

A boolean plus out parameter can represent success/failure only if no additional
error information is semantically required.
Otherwise use a tagged representation or reject the unsupported source form.

The existing Enfusion profile intentionally erases error tags.
Preserve that profile as explicitly limited until a new tagged ABI is implemented.
For an exact shared profile, prefer a primitive tag plus an out value, reserving
zero for success, subject to installed-engine compile and behavior probes.
Reject a catch binding that observes unavailable error identity before emission.
Do not claim exact cross-target error replay under the legacy tag-erasing profile.

Define:

- How success values are initialized.
- How error values are initialized.
- Which fields are valid in each variant.
- Who owns contained values.
- How cleanup works when a result is propagated.
- Whether constructing the result allocates.

### 24.6 Generated-code quality

Use a deterministic naming scheme.
Reserve a generated namespace.
Escape backend keywords.
Preserve readable source names as a component of generated identifiers.
Add a stable disambiguating identity when necessary.

Generated file names should reflect module responsibility.
Avoid one huge file when it makes incremental editor validation and source mapping worse.
Measure whether file splitting affects actual Workbench behavior before standardizing it.

## 25. Binding contracts: teach the compiler the real engine interface

The binding layer is central to AI usability.
An assistant should retrieve a verified declaration rather than guess a method name.
The compiler should reject an engine call with the wrong target version or signature.

Separate two sources of binding knowledge:

1. Extracted API facts from installed documentation or declarations.
2. Reviewed semantic metadata about effects, authority, lifetime, and failure.

Documentation extraction does not prove that a getter is pure or stable.
A semantic overlay must state the evidence for each stronger claim.

### 25.1 Proposed binding record

```text
BindingRecord {
    binding_id
    engine_product
    engine_version_range
    docset_fingerprint
    script_module
    declaring_type
    member_name
    exact_signature
    nullability
    parameter_access
    return_ownership
    lifetime_relationships
    effect_summary
    authority_requirement
    callback_and_reentrancy_behavior
    failure_behavior
    availability_evidence
    semantic_evidence
}
```

The record should distinguish unknown from false.
Unknown allocation behavior is not no-allocation behavior.
Unknown thread safety is not permission to call from a worker.

### 25.2 Stable identity

Use a stable identity derived from the declaration and versioned binding package.
Keep the human-readable name.
Do not use the short method name as the only identity.

Overloads, inherited methods, and script modules require disambiguation.
An assistant's context result should include enough information to select exactly one.

### 25.3 Binding validation

Validate in layers:

- Parse extracted declarations.
- Check binding schema consistency.
- Generate minimal signature probes.
- Compile probes in the intended installed Workbench.
- Run behavior probes only when an explicit scenario is needed.
- Record the exact project and engine identity for the result.

A compile probe establishes availability and type compatibility.
It does not establish runtime purity, authority, or identity semantics.

### 25.4 Version changes

When the installed engine changes:

1. Recompute the documentation/declaration fingerprint.
2. Compare signatures and availability.
3. Mark affected semantic overlays for review.
4. Re-run affected compile probes.
5. Invalidate generated artifacts that depend on changed contracts.

Do not invalidate every binding solely because the current date changed.
Do not trust a stale binding solely because its filename remains the same.

### 25.5 Minimal author-facing surface

An author should see:

- The Beryl binding name.
- Parameters and return type.
- A short explanation of relevant behavior.
- Authority or lifetime restrictions that affect usage.
- One verified example.
- The supported target version.

Compiler developers can inspect the full metadata.
Ordinary mod source should not repeat all of it.

## 26. Engine phases: capture, compute, and apply

Engine interaction needs a protocol because the world is mutable
and command execution can fail partway through.

Proposed phase lifecycle:

```text
Idle
  -> Capturing
  -> SnapshotReady
  -> Computing
  -> ComputationReady
  -> ApplyingCommands
  -> Completed

Any state may transition to a documented failure state.
```

Each transition records an invocation identity and relevant artifact hashes.
The protocol must reject results from a different invocation or source build.

### 26.1 Capture semantics

An adapter defines whether capture is:

- A sequence of reads with no stronger coherence.
- A snapshot guaranteed coherent by the engine.
- A Beryl-owned copy gathered during a defined engine callback phase.

These are different contracts.
Naming a structure Snapshot does not make several engine getters atomic.

The adapter records the capture epoch and time model.
If it cannot guarantee coherence, the source program must use that weaker contract.
The compiler must not merge live reads into a snapshot silently.

### 26.2 Compute semantics

Compute uses the captured inputs and explicit Beryl-owned state.
The optimized core avoids arbitrary live engine calls.
This creates a testable boundary and exposes opportunities for layout and caching.

Any unavoidable engine query remains explicit in the phase contract.
Its effects can block otherwise legal transformations.

### 26.3 Commands

A proposed command record contains:

```text
Command {
    command_id
    target_handle
    required_generation
    authority_context
    operation_binding
    arguments
    source_origin
    ordering_group
    expected_preconditions
}
```

Arguments must remain valid until application.
Do not store a phase-local view in a deferred command.
Copy or transfer owned data through an explicit representation.

### 26.4 Apply semantics

Before each command, revalidate the conditions that can change after capture.
Examples include target existence, authority, and required identity generation.

Application returns:

```text
ApplyResult {
    schema_version
    batch_id
    execution_status
    committed_prefix_length
    first_unresolved_or_failed_command
    command_outcomes: ordered sequence of CommandOutcome
    observed_engine_context
}

CommandOutcome {
    command_id
    effect_status: NotStarted | RejectedBeforeEffect | Applied |
                   PartialEffectsKnown | UnknownOutcome
    operation_finished: true | false | unknown
    known_effects
    completion_evidence
    failure_category
}
```

There is no automatic rollback promise for engine operations.
If command 4 fails after commands 1–3 succeed, report that completed prefix and
command 4's own effect status. Failure must not imply that command 4 had no effects.
Do not replay the whole batch unless every repeated operation is known safe.
Stop issuing later commands after a failed, partial, or unresolved operation.
Section 46.9 defines how timeout, cancellation, reconciliation, and retries affect
this ledger. Job lifecycle status and observed engine effects are separate fields.

### 26.5 State publication policy

Each adapter must choose how Beryl-owned state relates to command success.
Possible policies include:

- Publish desired state, then record actual command outcomes.
- Publish only state associated with the successfully applied prefix.
- Keep pending desired state separate from confirmed engine state.

The initial general recommendation is separate desired and confirmed state.
This avoids pretending the engine has committed an action merely because it was computed.
Retain explicit uncertainty for partially known effects; the completed prefix is
historical execution evidence, not a complete snapshot of current engine state.
The exact representation belongs in the mod's semantic adapter.

### 26.6 Command coalescing

Two writes to the same engine property cannot automatically become one write.
Intermediate setters may trigger callbacks, replication, validation, or logging.

Coalesce only when the binding contract establishes that intermediate writes
are unobservable under the selected phase semantics.
Keep original command order otherwise.

## 27. Replication, authority, and security-related performance

Security checks should be precise enough to optimize safely.
Removing a redundant validated check can help.
Removing a check because input is usually trustworthy is incorrect.

### 27.1 Authority as a runtime condition

A server-only annotation is useful for static checking.
It does not by itself establish that the current runtime invocation is authoritative.

Generated entry wrappers should verify the relevant engine authority condition
using a verified binding.
The compiler may propagate that fact within its valid scope.
A later authority transition can invalidate it.

The exact engine method used for the check must come from installed bindings.
Do not invent a universal IsServer API name in generated code.

### 27.2 Validation refinements

Represent validated input with facts such as:

```text
ValidatedDistance {
    finite
    lower_bound
    upper_bound
    units
    source_message_schema
}
```

The source API may remain a simple checked conversion or validator call.
The compiler tracks the stronger facts internally.

Calling min or max on untrusted input does not universally validate it.
Floating-point NaN behavior and the actual sink requirement matter.
Clamping an integer index also needs a nonempty destination bound.

### 27.3 Replication schema

Generate replication code from an explicit schema:

- Stable field identity.
- Wire type.
- Allowed range.
- Authority direction.
- Update policy.
- Version compatibility.
- Validation rule.
- Maximum message size.

Changing memory layout must not change the wire schema.
Field reordering for cache locality must not silently reorder protocol fields.

### 27.4 Delta replication

Sending only changed values can reduce work and bandwidth.
It requires a defined baseline, versioning, and recovery behavior.

Handle:

- Lost updates.
- Duplicate messages.
- Out-of-order delivery.
- Reconnection.
- Baseline mismatch.
- Entity generation changes.

A delta stream needs a way to recover a complete valid state.
Its cost includes baseline storage, comparisons, and recovery traffic.

### 27.5 Quantization

Quantization can reduce bandwidth but may change values.
Treat it as an explicit serialization contract with units and error bounds.
Do not place it in an exact optimization comparison unless both implementations
use the same quantization contract.

### 27.6 Secret-dependent behavior

If Beryl retains a constant-time claim, specify the threat model and supported operations.
An AST lint alone cannot establish machine-code constant-time behavior.
Adaptive plan selection must not inspect secret-dependent features under such a contract.

For ordinary game logic, avoid imposing cryptographic restrictions without need.
For code that requests them, make unsupported cases explicit.

## 28. A small authoring surface for AI-written mods

AI-friendly syntax should minimize choices that do not change meaning.
It should make the important choices explicit and mechanically checkable.

The desired authoring vocabulary is:

- Ordinary functions for calculations.
- Structs for owned state and inputs.
- Existing parameter modes for access.
- A small set of generated engine adapters.
- A restricted query interface for common collection operations.
- Tests close to the logic they specify.

Do not introduce a separate mini-language for every optimization.
Layout, vector width, cache indexes, and proof witnesses belong in compiler plans.

### 28.1 Canonical patterns

Publish one preferred pattern for each common task:

| Task | Canonical pattern |
|---|---|
| Pure computation | Function with explicit input/output types |
| Stateful tick | Function with one explicit mutable state argument |
| Engine read | Verified binding or generated capture adapter |
| Entity reference | Target handle with explicit validity behavior |
| Client request | Generated validated entry wrapper |
| Derived collection | Restricted pure query |
| Engine mutation | Verified direct call or explicit phase command |
| Expected failure | Typed result handled at the boundary |
| Missing entity | Option or documented lookup result |
| Test | Native logic test plus separate adapter scenario where needed |

Prefer these patterns in documentation and generated examples.
Allow advanced alternatives only when they solve a real problem.

### 28.2 Proposed feature shape

The following is Beryl-shaped design pseudocode.
The names and adapter constructs are not claims about current parser support.

```text
struct TargetingConfig {
    selected_team: i32
    maximum_distance: f32
}

struct TargetingState {
    selected: EntityHandle?
}

struct TargetingInputs {
    tick: TickId
    entities: ReadView<EntityObservation>
}

fn choose_target(
    config: TargetingConfig,
    inputs: TargetingInputs
) -> EntityHandle? {
    return eligible_entities(config, inputs)
        .select_best_by(total_score, stable_identity)
}

fn update_targeting(
    inout state: TargetingState,
    config: TargetingConfig,
    inputs: TargetingInputs
) -> TargetingDecision {
    let next = choose_target(config, inputs)
    state.selected = next
    return TargetingDecision { selected: next }
}
```

The compiler could lower eligible_entities through a full or incremental plan.
The source expresses selection, not a specific index data structure.
The generated adapter separately maps TargetingDecision to verified engine operations.

Before implementing this API, decide:

- Whether query methods are library calls, intrinsics, or syntax.
- How callbacks establish totality and purity.
- How handles are represented on each target.
- What lifetime ReadView permits.
- Which current language features can express the same interface.

Prefer library-shaped APIs when they remain analyzable.
Do not add syntax simply to make a research diagram look elegant.
Initially implement concrete functions over verified collection shapes.
Do not require first-class function values or user-defined generic instantiation.
A later library-shaped query intrinsic may accept a statically resolved function
identity with a verified signature and effects; section 45.10 defines that boundary.

### 28.3 Component generation

A component declaration should identify:

- The verified engine base type.
- The Beryl state type.
- Exposed editor properties.
- Callback-to-function mappings.
- Authority policy.
- Serialization/replication schema, if any.

The generator resolves actual callback signatures from bindings.
An author should not copy an override signature from model memory.

Keep generated wrappers thin.
Move testable logic into ordinary Beryl functions.
Preserve a visible boundary between authored logic and generated engine scaffolding.

### 28.4 Configuration and units

Use named configuration fields instead of positional magic constants.
Represent units in types or verified domain wrappers where practical.
At minimum, generated context must state units explicitly.

Examples of costly ambiguity:

- Degrees versus radians.
- Meters versus centimeters.
- Seconds versus milliseconds.
- Local versus world coordinates.
- Entity identity versus a physical row index.

A small domain library that prevents these mistakes may improve AI productivity
more than adding a complicated new syntax feature.

### 28.5 Formatting

The formatter is a semantic tool for assistants.
It must preserve literal values, comments needed by authors, and parse meaning.
Require parse-format-parse semantic equivalence and formatter idempotence.

Validate literal payloads, suffixes, and AST structure directly.
The existing printable AST dump is not a sufficient equality oracle because it
also rounds floats and omits numeric suffix information.
Use round-trip decimal rendering, preserve an explicit float token when needed,
and escape character/string literals correctly; see section 45.9.

Use one canonical import order and one layout for declarations.
Avoid equivalent syntactic variants that create unnecessary repair choices.
Diagnostic spans should account for the encoding and tabs used by the editor.

## 29. Compiler-generated context for Claude and ChatGPT

The compiler should be able to describe the actual project in a compact,
machine-readable form.
This reduces reliance on stale prose and broad repository searches.

Proposed operations, not existing CLI commands:

```text
context.project
context.symbol
context.binding
context.feature_support
context.example
context.diagnostic
context.optimization
```

These can be exposed through a local CLI, library, or optional MCP adapter.
The semantic data model should be shared across interfaces.

### 29.1 Project context

A project context response should include:

- Language and compiler versions.
- Target profile.
- Manifest identity.
- Source revision/content fingerprint.
- Engine binding fingerprint.
- Module graph.
- Exported symbols.
- Supported and unsupported language features.
- Relevant diagnostics from the latest check.
- Links to verified local examples.

It should omit unrelated repository content.
It should not include credentials or arbitrary environment variables.

### 29.2 Symbol context

For a requested function or type, return:

```text
SymbolContext {
    resolved_identity
    source_location
    declaration
    inferred_effects
    ownership_contract
    target_support
    direct_dependencies
    direct_dependents
    relevant_tests
    examples_with_validation_status
}
```

The assistant can then edit with knowledge of the actual signature and effects.
Large dependency lists should be paginated or summarized with explicit truncation.
Do not omit a relevant dependency while claiming the result is complete.

### 29.3 Context freshness

Each response carries a source fingerprint.
An edit invalidates affected responses.
A diagnostic from an older source version must be labeled stale.

When an assistant submits a patch based on old context,
the tool can reject it with a precise revision mismatch.
It should not quietly apply offsets from an unrelated source version.

### 29.4 Examples as tested assets

Examples should be compiled in the target profile they claim to support.
An example using a proposed feature belongs in research documentation,
not in the current feature-support response.

Attach:

- Example version.
- Required language features.
- Required bindings.
- Latest check status.
- Latest native test status.
- Latest engine validation status, if applicable.

Unavailable validation is recorded as unavailable.
It is not represented as a successful test.

### 29.5 Controlled vocabulary

Use stable terms across compiler, docs, and bridge:

- Source.
- Generated artifact.
- Native test.
- Engine compile validation.
- Runtime scenario.
- Binding contract.
- Exact plan.
- Approximate contract.
- Measurement.

Avoid using build success to mean a runtime scenario passed.
Avoid using validated to mean only parsed.

## 30. Diagnostics that produce reliable repairs

A good diagnostic should explain the failed obligation
and identify the smallest relevant source context.

Proposed diagnostic schema:

```text
Diagnostic {
    schema_version
    code
    severity
    message
    primary_span
    related_spans
    source_fingerprint
    target_profile
    failed_requirement
    evidence
    suggested_repairs
    generated_origin
}
```

Suggested repairs must be conditional where necessary.
Do not present an unsafe cast as a universal fix for a range error.

### 30.1 Ownership diagnostic example

```text
Problem:
    A read view remains live while the backing list may grow.

Evidence:
    View created at source location A.
    The push at location B changes the list shape.
    View used again at location C.

Repair choices:
    End the view before the push.
    Recreate the view after the push.
    Change the algorithm to avoid structural mutation during iteration.
```

The compiler should not invent a fixed line number in a reusable message.
Actual spans come from the current source map.

### 30.2 Optimization explanations

An optimization report should distinguish:

- Applied transformation.
- Legality evidence.
- Estimated benefit.
- Measured benefit, if available.
- Reason a candidate was rejected.

Example:

```text
Candidate: checked block execution
Status: rejected
Reason: output may overlap input a
Evidence: both views derive from the same unresolved storage root
Consequence: reference scalar plan selected
```

This is useful information, not a compilation error.
The assistant can decide whether an algorithmic change is worthwhile.

### 30.3 Repair loop discipline

An assistant should:

1. Read the current diagnostic and its source fingerprint.
2. Retrieve the affected symbol and binding context.
3. Make the smallest semantically justified edit.
4. Re-run the relevant check.
5. Broaden validation when the edit affects a larger contract.

Do not respond to a target incompatibility by repeatedly changing syntax at random.
The tool should expose which feature or binding is unsupported.

### 30.4 Cascading engine errors

Generated-code errors may produce secondary errors in untouched engine files.
Preserve all diagnostics in the raw result.
Group likely primary and secondary errors in the presentation.
Explain the grouping heuristic.

Do not discard engine errors solely because their paths are outside Generated.
A real dependency mismatch can appear in a base-game declaration.

## 31. A local Workbench bridge with explicit capabilities

The bridge is a development tool.
It can be used by a human, a shell script, Claude, or ChatGPT.
Its core does not need a model API.

Use a local command/library interface as the source of truth.
An MCP adapter can expose the same operations to assistants.
Do not make the protocol depend on one vendor's conversation format.

### 31.1 Existing integration to evaluate

The earlier investigation identified a sibling Workbench plugin at:

```text
C:/Users/moham/Desktop/reforger-workbench-plugin
```

It contains useful starting points for API indexing, build validation,
Workbench discovery, RPC, and health checks.
Re-inspect its current revision before integration.
Do not copy old assumptions about its flags or supported engine version.

The earlier observed tooling distinguished headless jobs from live Workbench RPC.
It did not provide a complete game-runtime scenario harness.
Treat runtime scenarios as a separate capability to implement and verify.

### 31.2 Capability discovery

Proposed capability response:

```json
{
  "schemaVersion": 1,
  "capabilities": {
    "inspectProject": true,
    "searchBindings": true,
    "compileGeneratedScript": true,
    "runRuntimeScenario": false,
    "exportProfilerData": null
  },
  "unavailableReasons": {
    "runRuntimeScenario": "No verified scenario adapter is installed",
    "exportProfilerData": "Capability has not been probed"
  }
}
```

Here true means available under the reported environment.
False means known unavailable.
Null means unknown.
Do not convert null into success or absence.

### 31.3 Proposed operations

Read operations:

- Inspect installed tools and versions.
- Inspect the intended project.
- Search bindings.
- Read relevant source and generated artifacts.
- Read job status.
- Read diagnostics.
- Locate source from generated code.

Validation operations:

- Check Beryl source.
- Run selected native tests.
- Generate an artifact into staging.
- Compile that exact artifact in Workbench.
- Run a named scenario when supported and requested.
- Collect a specified profile when supported and requested.

Mutation operations:

- Promote a validated generated artifact.
- Update compiler-owned generated files.
- Start a bridge-owned editor session where needed.

Keep publishing, packing, and launching a game distinct from compilation.
A successful compile must not automatically trigger unrelated lifecycle actions.

### 31.4 Request envelope

```json
{
  "schemaVersion": 1,
  "requestId": "example-request-001",
  "operation": "compileGeneratedScript",
  "projectId": "example-project",
  "sourceFingerprint": "example-source-hash",
  "artifactFingerprint": "example-artifact-hash",
  "bindingFingerprint": "example-binding-hash",
  "executionMode": "headless",
  "timeoutMs": 60000
}
```

Example hashes are placeholders, not measured artifact identities.
An implementation must validate field types and operation-specific requirements.

### 31.5 Job result

```json
{
  "schemaVersion": 1,
  "requestId": "example-request-001",
  "jobId": "example-job-001",
  "status": "failed",
  "stage": "engineCompile",
  "failureCategory": "sourceDiagnostic",
  "sourceFingerprint": "example-source-hash",
  "artifactFingerprint": "example-artifact-hash",
  "diagnostics": [
    {
      "code": "EXAMPLE_SIGNATURE_MISMATCH",
      "severity": "error",
      "message": "Example: callback signature differs from the selected binding.",
      "primarySpan": {
        "file": "src/targeting.be",
        "startByte": 120,
        "endByte": 150
      },
      "sourceFingerprint": "example-source-hash"
    }
  ],
  "rawLogArtifact": "example-log-reference",
  "measurements": null
}
```

The diagnostic code, file, and byte offsets are illustrative.
A real failure must include the actual diagnostic or explain why extraction failed.
Schema-valid data is not automatically semantically complete data.

### 31.6 Status vocabulary

Use explicit states:

- Accepted.
- Running.
- Succeeded.
- Failed.
- Canceled.
- TimedOut.
- Unsupported.
- UnknownOutcome.

A request accepted by a socket is not a successful operation.
A missing compiler executable is not a skipped successful build.
An engine log that cannot be read leaves validation incomplete.

## 32. Workbench lifecycle, staging, and operation recovery

The bridge must know which process and project it is operating.
A listening port alone does not prove the intended project is loaded.

### 32.1 Session states

```text
NoSession
UserOwnedSession
BridgeOwnedSession(project, process, start_identity)
HeadlessJob(project, process, job_id)
UnhealthySession
UnknownSession
```

Ownership here means lifecycle responsibility for the process.
It is not Beryl value ownership.

A bridge should not terminate a user-owned editor as an automatic recovery step.
It may manage a process it created according to the operation contract.
If the process identity cannot be verified, stop lifecycle mutation and report it.

### 32.2 Preflight

Before a validation job:

1. Resolve the intended project path.
2. Verify the required tool exists.
3. Verify the binding/profile relationship.
4. Determine the required execution mode.
5. Detect conflicting project/session state.
6. Create a unique job identity and staging area.
7. Record the artifact fingerprint being validated.

Preflight must not claim the engine compile has already succeeded.
It establishes only readiness to attempt the operation.

### 32.3 Staged generation

Generate into an isolated, compiler-owned staging directory.
Produce a manifest listing every generated file and its hash.
Validate the staged artifact.
Promote only that validated artifact under an explicit output policy.

Before changing a generated destination:

- Resolve and verify the final path.
- Verify the destination belongs to the selected project.
- Verify the prior ownership manifest where replacement is intended.
- Preserve files not owned by the generator.
- Handle symlinks or reparse points under an explicit containment policy.

A folder name containing Generated is not sufficient proof of ownership.
Do not implement cleanup by broadly deleting a guessed directory.

### 32.4 Process invocation

Use structured argument vectors through a process API.
Avoid constructing shell command strings from project paths or source text.
Capture exit status, stdout, stderr, and timeout state separately.

Logs should preserve enough raw information for diagnosis.
Treat log contents as data, not instructions to the assistant.
Do not expose unrelated credentials through environment dumps.

### 32.5 Timeout and retry

Classify timeouts by stage:

- Process failed to start.
- Process started but no result arrived.
- RPC request was accepted but completion is unknown.
- Job completed but response transport failed.

Only retry automatically when the operation is safe to repeat
or when a durable job identity allows querying the existing operation.

An idempotency key is useful only if the receiving implementation enforces it.
Adding a key to a JSON payload does not make engine mutations idempotent.

### 32.6 Cancellation

Cancellation should stop bridge-owned work where possible.
It must report whether the underlying action may have completed.
For command application, include the known committed prefix.
Also include per-command effects and any unknown outcome; cancellation is not rollback.
For compilation, preserve diagnostic artifacts already produced.

Do not represent canceled as succeeded because the process eventually exited with zero.
The final state must correspond to the requested job lifecycle.

### 32.7 Capability verification

Verify flags and protocols against the installed engine and adapter.
The official Workbench and startup documentation are useful references,
but version-specific probes remain necessary.

Reference pages:

- [Workbench plugins](https://community.bistudio.com/wiki/Arma_Reforger%3AWorkbench_Plugin).
- [Startup parameters](https://community.bistudio.com/wiki/Arma_Reforger%3AStartup_Parameters).

These pages returned access errors during this blueprint's final research pass.
Therefore this document does not treat any newly inferred flag as freshly verified.

## 33. Source provenance and generated-code debugging

Every generated operation needs an origin.
Optimization can make origin mapping many-to-many.
A single generated loop can represent several source expressions.
A source expression can appear in several specialized plans.

### 33.1 Origin representation

```text
Origin {
    source_file_id
    source_content_hash
    start_byte
    end_byte
    logical_operation_id
    inline_call_chain
    transformation_chain
    synthetic_reason
}
```

Use byte offsets internally with an explicit encoding.
Convert to the editor's line/column convention at the interface.
Do not mix UTF-8 byte offsets with character columns.

### 33.2 Mapping records

A generated span maps to:

- One primary source origin.
- Zero or more contributing origins.
- The selected plan.
- The transformation that introduced the span.
- The helper origin when the code is synthetic.

Intern origin chains to avoid copying large provenance structures everywhere.
Bound diagnostic rendering depth while retaining access to the complete chain.

### 33.3 Failure mapping

A checked block kernel must report the scalar source failure site.
A helper's generated line is useful secondary context.
It must not replace the meaningful Beryl location.

For an engine callback mismatch, show:

- The Beryl adapter declaration.
- The binding signature used.
- The generated override.
- The installed engine signature when available.

### 33.4 Artifact identity

A source map is valid only for its generated artifact fingerprint.
Reject mapping requests against a different artifact.
Keep old maps only with their corresponding retained artifacts.

A stable source filename does not establish that the map is current.
Hot reload and repeated generation make this especially important.

### 33.5 Debugger limits

Source navigation and diagnostic mapping are initial goals.
Full source-level breakpoints through arbitrary optimized script are a separate feature.
Do not promise debugger stepping behavior without verifying engine support.

An optimization report can still explain a transformed region
even when the engine debugger can only step through generated code.

## 34. Replay and differential validation

Replay should make a bug reproducible without requiring the same live world.
It is a boundary-design problem, not merely recording a random seed.

### 34.1 Replay record

```text
ReplayRecord {
    schema_version
    source_fingerprint
    compiler_fingerprint
    target_contract
    binding_fingerprint
    phase_id
    invocation_id
    prior_state
    captured_inputs
    configuration
    time_inputs
    random_inputs_or_exact_prng_definition
    resource_profile
    expected_outcome
    confirmed_apply_result
}
```

Record actual nondeterministic inputs when reproducing them from a seed is unreliable.
If recording a PRNG seed, also record the algorithm, version, and call sequence contract.
expected_outcome uses section 06's unified event stream, including trace completeness.
Do not reconstruct a global order from separately recorded command and write lists.

### 34.2 Three distinct tests

1. Reference-versus-optimized native replay.
2. Native-versus-generated-script replay under a shared target contract.
3. Live adapter validation against actual engine behavior.

The first tests an optimizer.
The second tests target agreement.
The third tests capture, bindings, and command application.
Passing one does not imply the others passed.

### 34.3 Comparison policy

Compare exact integers, identities, options, errors, and the unified observable
event order exactly within the selected contract.
Use an explicitly selected floating-point comparison policy.
Record both numeric differences and control-flow/output differences.

A tolerance on a numeric output must not conceal a different selected target,
different command sequence, or different failure.
Those differences can be semantically important even when individual floats are close.

### 34.4 Reference independence

A reference evaluator should prioritize simplicity.
Where practical, avoid sharing the transformation's arithmetic helper implementation.
Shared bugs can make differential tests agree incorrectly.

For small domains, compare against a mathematical or exhaustive reference.
For large domains, combine random traces with adversarial boundary cases.

### 34.5 Trace bounds

Keep recording bounded:

- Maximum frames or invocations.
- Maximum entities.
- Maximum payload bytes.
- Maximum retained artifacts.
- Explicit truncation status.

A truncated trace is not complete evidence of a passing scenario.
Capture the first failure and enough preceding state to reproduce it.
Do not continuously record an unbounded world by default.

### 34.6 Engine profiling

Use the installed engine's supported profiler facilities where available.
Record exactly which metric was collected and how.
Script time, allocation count, and frame time are different measurements.

The [script profiling reference](https://community.bistudio.com/wiki/Arma_Reforger%3AScript_Profiling)
is a starting point, subject to installed-version verification.
Do not invent profiler export support when the bridge reports it as unknown.

## 35. Benchmark methodology that can support a strong claim

The benchmark system is part of the architecture.
Without it, the planner can optimize the wrong thing and the project can mistake
an invalid test for a breakthrough.

### 35.1 Separate benchmark families

Maintain four families:

| Family | Purpose |
|---|---|
| Semantic microcases | Verify exact behavior, including failure |
| Native kernels | Measure isolated computational mechanisms |
| Native applications | Include indexes, transitions, allocation, and orchestration |
| Engine scenarios | Measure actual generated-script behavior in Enfusion |

Do not aggregate these families into one language speed number.
Each answers a different question.

### 35.2 Workload contract

Every benchmark manifest must define:

- The problem being solved.
- Input generation or trace provenance.
- Data sizes and distributions.
- Output requirements.
- Ordering requirements.
- Arithmetic policy.
- Failure policy.
- Threading policy.
- Initialization scope.
- Allocation scope.
- Warm-up.
- Repetition policy.
- Result-consumption method.
- Baseline implementations.
- Exclusion rules.

Write the manifest before examining the final results.
Otherwise it is easy to choose a favorable subset after the fact.

### 35.3 Harness correctness

The harness must fail when:

- Compilation fails.
- The executable cannot start.
- The workload exits unexpectedly.
- A checksum or semantic output is wrong.
- A required measurement is missing.
- A timeout occurs.
- A target capability is unavailable.

A failed run must not contribute a zero-duration sample.
A benchmark without an invoked workload is not a performance result.

For checked arithmetic benchmarks, ensure the input generator follows the intended
success or failure contract.
An overflowing pseudo-random generator can cause the benchmark to terminate
before the measured work begins.

### 35.4 Preventing eliminated work

Consume outputs through a method verified for each toolchain.
Use external inputs or explicit optimization barriers where appropriate.
Inspect a representative generated artifact to confirm the workload remains.

Do not rely solely on printing a constant-looking result after a loop.
The optimizer may derive that result without executing the intended loop.
Keep correctness verification outside timed regions when the benchmark contract permits,
and include equivalent verification costs when they are part of the application.

### 35.5 Matching Rust

Record Rust compiler version, target CPU flags, optimization level,
overflow behavior, panic behavior, LTO policy, allocator, and PGO usage.
Record equivalent Beryl/Clang settings.

Rust release overflow settings are configurable.
Match the required behavior explicitly.
See [Cargo profile settings](https://doc.rust-lang.org/cargo/reference/profiles.html).

For checked loops, explicit checked operations may provide the clearest comparison.
For a total query with proven ranges, both implementations may use those same
range assumptions under a justified contract.

Give the Rust implementation the same opportunity to:

- Use the same data layout.
- Reuse allocations.
- Maintain indexes.
- Apply bounds-based pruning.
- Select among equivalent plans.
- Use SIMD or target intrinsics where the comparison permits them.

### 35.6 Sampling

Use independent run blocks.
Randomize or alternate implementation order within each block.
Record thermal and system conditions where practical.
Separate warm-up from measured samples.

Report sample count and the sampling unit.
Thousands of loop iterations inside one process are not thousands
of independent observations of system noise.

Use enough work per sample to avoid timer resolution dominating the result.
Do not hide short workloads by excluding all setup if users pay that setup.

### 35.7 Statistical reporting

For paired run blocks:

```text
speedup_i = rust_time_i / beryl_time_i
log_ratio_i = log(speedup_i)
```

Estimate uncertainty from independent blocks.
A bootstrap or another justified method can be used.
State the method and confidence level.

For a suite, a geometric mean of positive per-workload ratios can be informative.
Show the individual workloads too.
Do not let one extreme outlier hide several important regressions.

Report latency quantiles only with enough observations to support them.
A p99 from a tiny sample has little meaning.
Retain raw measurements for reproducibility.

### 35.8 Proposed success threshold

For an initial native experiment, a reasonable provisional gate is:

- Correctness suite passes.
- The confidence interval supports a practically meaningful improvement.
- The effect exceeds a predeclared noise/regression tolerance.
- Memory and code-size costs remain within the experiment budget.
- A matched tuned Rust comparison is included.

A 5% practical threshold can be an initial planning value.
Adjust it using baseline measurement noise before seeing candidate results.
It is a decision threshold, not an expected improvement.

### 35.9 Application timing

Measure the complete phase:

```text
Tphase =
    Tcapture
  + Tinvalidation
  + Tindex_maintenance
  + Tcomputation
  + Tstate_publication
  + Tcommand_application
  + Tplan_transition
```

Nested instrumentation may perturb timing.
Use total wall time as the primary application result.
Treat component measurements as explanatory, with their overhead stated.

### 35.10 Memory and code size

Report:

- Peak live payload.
- Allocator-observed peak where measurable.
- Retained cache/index memory.
- Scratch capacity.
- Steady-state allocation count.
- Generated source size.
- Native executable/code size.
- Compiler peak memory.

An optimization that saves time by retaining a large index should say so.
Memory is part of the performance tradeoff.

### 35.11 Engine measurements

Run generated and handwritten script in equivalent scenarios.
Use the same entity population, update rate, authority role, and engine version.
Include capture and application overhead.

Separate script CPU time from full frame time.
Rendering, physics, networking, and scheduling may dominate full frame time.
A script speedup can be valuable without producing the same FPS multiplier.

## 36. Worked analytical models and integrated case studies

This section uses invented numbers to make the proposed mechanisms understandable.
The examples are calculations, not simulations of the actual engine or compiler.

### 36.1 Application limits

If fraction f of a workload becomes s times faster:

```text
overall_speedup = 1 / ((1 - f) + f / s)
```

If 90% of runtime improves by 3x:

```text
speedup = 1 / (0.10 + 0.90 / 3) = 2.5x
```

If only 20% improves by 10x:

```text
speedup = 1 / (0.80 + 0.20 / 10) ~= 1.22x
```

This explains why a spectacular arithmetic kernel result may produce
a modest improvement in an engine-heavy mod.

### 36.2 Combined phase model

Illustrative costs:

| Component | Reference | Candidate |
|---|---:|---:|
| Unchanged engine work | 6.0 ms | 6.0 ms |
| Input capture | 2.0 ms | 0.9 ms |
| Allocation/copies | 2.0 ms | 0.2 ms |
| Collection traversal | 3.0 ms | 1.2 ms |
| Arithmetic | 1.0 ms | 0.5 ms |
| Total | 14.0 ms | 8.8 ms |

The implied total improvement is about 1.59x.
The model assumes the candidate component costs already include interactions.
It must not be built by multiplying unrelated microbenchmark wins.

A tuned Rust implementation using the same mechanisms could have the same costs.
The table establishes no language-specific advantage.

### 36.3 Demand-driven selection model

Assume:

- N = 100,000 candidates.
- Exact score cost = 200 ns.
- Bound cost = 10 ns.
- Fraction requiring exact score = 0.10.
- Bound/index maintenance = 0.30 ms per invocation.

Then:

```text
full = 100000 * 200 ns = 20.0 ms
candidate = 100000 * 10 ns
          + 10000 * 200 ns
          + 0.30 ms
          = 3.30 ms
ratio ~= 6.06x
```

If every candidate requires an exact score:

```text
candidate = 1.0 ms + 20.0 ms + 0.30 ms = 21.30 ms
```

The same mechanism regresses by adding overhead.
That failure case belongs in the benchmark suite and plan-selection policy.

### 36.4 Representation reuse model

Suppose compacting a private table costs 1.8 ms.
Each later use saves 0.18 ms.
Ignoring maintenance, ten uses only break even.
At least eleven uses are needed for a strict gain under these assumptions.

If updates require maintenance, add that cost before deciding.
If the table is used once per frame, expected remaining lifetime matters.
A representation that helps a persistent controller may lose for a short-lived effect.

### 36.5 Case study A: target selection

Inputs:

- Stable entity identities.
- Alive/team membership.
- Dynamic position and visibility observations.
- Rare scoring configuration.

Reference:

1. Read a coherent or explicitly sequentially captured input set.
2. Filter eligible entities.
3. Evaluate every total score.
4. Select with a stable tie-breaker.
5. Produce one decision.
6. Apply through the verified adapter.

Candidate ladder:

- A0: scalar full recomputation.
- A1: reusable private output/scratch.
- A2: hot columns for Beryl-owned observations.
- A3: incremental membership.
- A4: admissible score bounds.
- A5: cached scores with complete dependency invalidation.
- A6: adaptive selection among validated plans.

Each step gets an ablation.
The exact same ladder should be available to the strongest Rust comparison.

Adversarial cases:

- Every entity changes team.
- Every score bound overlaps.
- Winner deleted and identity slot reused.
- Configuration changes every invocation.
- Engine capture dominates all computation.

### 36.6 Case study B: controller fleet

Inputs:

- Controller state per entity.
- Per-tick measurements.
- Fixed or rare configuration.
- A specified timestep.

Candidate improvements:

- Precompute configuration-only coefficients.
- Use dense hot state for active controllers.
- Reuse outputs.
- Eliminate temporary value copies.
- Vectorize eligible total or correctly checked kernels on native.

Do not skip integration because measurements repeat.
Do not reorder floating-point expressions under a strict contract.
Measure the generated script separately from the native controller kernel.

Adversarial cases:

- Invalid timestep.
- NaN/infinite observations under the selected policy.
- Controller deletion during command application.
- Reentrant callbacks.
- Very small fleets where setup dominates.

### 36.7 Case study C: inventory eligibility

Inputs:

- Stable item identity.
- Item category and count.
- Player eligibility attributes.
- Capacity and authority constraints.

Candidate improvements:

- Incremental category indexes.
- Validated bounded counts.
- Exact cached predicates.
- Generated request validation.

Correctness risks:

- Duplicate requests.
- Stale authority.
- Count underflow or overflow.
- Removing an item whose cached membership remains.
- Reusing an identity without invalidating a handle.

Security and state correctness are part of this workload's contract.
A faster invalid inventory transition is a failed implementation.

### 36.8 Case study D: replication preparation

Inputs:

- Confirmed authoritative state.
- Per-client acknowledged baseline.
- Explicit replication schema.

Candidate improvements:

- Field-level dirty tracking.
- Layout optimized for serialization access.
- Reused message buffers.
- Delta generation against the acknowledged baseline.

Include recovery traffic and baseline storage.
Compare exact schemas or explicitly matched quantization policies.
Do not omit packet-loss recovery from an application-level claim.

## 37. Validation catalog

This is a proposed test specification, not a claim that these tests exist or pass.
Each identifier names a future acceptance case.
Parameterize cases over supported widths and targets where meaningful.

The oracle should compare the selected semantic outcome, not only a final checksum.
Compiler rejection is the correct outcome for unsupported or unproven transformations.

### 37.1 Evaluation and arithmetic

| ID | Setup | Required observation |
|---|---|---|
| VAL-001 | False left operand with failing right operand of short-circuit AND | Right operand is not evaluated |
| VAL-002 | True left operand with effectful right operand of short-circuit OR | Right operand is not evaluated |
| VAL-003 | Compound assignment with an index-producing callback | Index callback runs exactly once |
| VAL-004 | Two effectful operands | Selected source evaluation order is preserved |
| VAL-005 | Checked maximum plus one | Failure occurs at the addition site |
| VAL-006 | Checked minimum minus one | Failure occurs at the subtraction site |
| VAL-007 | Signed minimum divided by negative one | Selected division failure contract is preserved |
| VAL-008 | Division by zero after an earlier visible write | Earlier write remains visible |
| VAL-009 | Shift count equal to integer width | Selected out-of-range shift failure occurs |
| VAL-010 | Narrow wrapping multiplication | Result matches modular arithmetic without implementation UB |
| VAL-011 | Constant expression and runtime equivalent at a boundary | Both produce the same value or failure |
| VAL-012 | Reassociation that removes an intermediate overflow | Transformation is rejected |

### 37.2 Ownership and initialization

| ID | Setup | Required observation |
|---|---|---|
| VAL-013 | Read an inout argument whose value was never initialized | Compile-time rejection |
| VAL-014 | Initialize only inside a possibly empty loop | Later unconditional read is rejected |
| VAL-015 | Initialize on one branch but not the other | Merge does not claim definite initialization |
| VAL-016 | Initialize after an early break | Break path remains uninitialized |
| VAL-017 | Compound-assign an uninitialized field | Read-before-initialization is detected |
| VAL-018 | Transfer an owning list through sink then read it | Use-after-move is rejected |
| VAL-019 | Duplicate an owning list and mutate one copy | Independent logical values remain |
| VAL-020 | Grow one of two incorrectly shared native list headers | Validation detects the ownership defect |
| VAL-021 | More access-mode arguments than the old small fixed limit | Every argument is analyzed |
| VAL-022 | Deeply nested field projections | No silent truncation of overlap analysis |
| VAL-023 | Two dynamic indices without inequality proof | Exclusive overlap is conservatively handled |
| VAL-024 | Partial aggregate construction fails | Exactly the initialized owned fields are cleaned up |

### 37.3 Effects and facts

| ID | Setup | Required observation |
|---|---|---|
| VAL-025 | Establish length fact, then push, then reuse fact | Old shape-dependent fact is invalid |
| VAL-026 | Change an unrelated field | Unrelated dependency fact may remain valid |
| VAL-027 | Unknown call receives access to tracked storage | Affected facts are conservatively invalidated |
| VAL-028 | Recursive effect summary does not converge within budget | Analysis widens safely |
| VAL-029 | Guard uses overflowing size multiplication | Guard construction is rejected or corrected |
| VAL-030 | Fact established in only one branch | Fact does not escape the merge without proof |
| VAL-031 | Fact references an old storage identity with the same source name | Identity mismatch is detected |
| VAL-032 | no-allocation requirement reaches an unknown call | Unknown effect is explained and requirement is not accepted |
| VAL-033 | Hidden generated duplication allocates | Allocation appears in the effect summary |
| VAL-034 | Callback re-enters a phase using shared scratch | Reentrancy policy prevents unsafe reuse |
| VAL-035 | Time advances while entity fields remain unchanged | Time-dependent computation is invalidated |
| VAL-036 | Engine contract fingerprint changes | Dependent facts and artifacts are invalidated |

### 37.4 Structured IR

| ID | Setup | Required observation |
|---|---|---|
| VAL-037 | Value used outside its defining region | Verifier rejects invalid dominance |
| VAL-038 | Branch yields a value of the wrong type | Verifier rejects the region result |
| VAL-039 | Loop break targets the wrong loop identity | Verifier rejects the exit |
| VAL-040 | Transformation loses a cleanup edge | Verifier or outcome comparison detects the loss |
| VAL-041 | Transformation drops a failure-order dependency | Legality validation rejects the candidate |
| VAL-042 | Same short symbol name in two modules | Resolved identities remain distinct |
| VAL-043 | Backend keyword used as a source identifier | Deterministic valid target name is emitted |
| VAL-044 | Generated temporary collides with an authored name | Identity-based naming prevents collision |
| VAL-045 | Unsupported AST form enters an optimized region | Explicit fallback or diagnostic, never omitted code |
| VAL-046 | Two equivalent source formatting variants | Normalized semantic identity remains consistent where intended |
| VAL-047 | Optimization creates an unreachable marker without proof | Verifier rejects the marker |
| VAL-048 | Source span contains multibyte text | Mapping converts offsets correctly |

### 37.5 Checked block execution

| ID | Setup | Required observation |
|---|---|---|
| VAL-049 | Successful block at every selected width | Outputs equal scalar reference |
| VAL-050 | Multiply failure in each active lane | Scalar prefix and multiply failure site match |
| VAL-051 | Addition failure in each active lane | Scalar prefix and addition failure site match |
| VAL-052 | Later lane multiply fails, earlier lane addition fails | Earlier scalar failure wins |
| VAL-053 | Failure in the second block | First block remains committed correctly |
| VAL-054 | Input size smaller than vector width | No inactive-lane access occurs |
| VAL-055 | Size one beyond a block boundary | Tail result and access bounds are correct |
| VAL-056 | Output aliases an input | Specialized plan is rejected unless separately proven safe |
| VAL-057 | Source i64 multiplication offered to i32 widening proof | Proof checker rejects the mismatch |
| VAL-058 | Effectful call inserted in the loop | Block speculation is rejected |
| VAL-059 | Two observable stores per iteration | Initial restricted transformation is rejected |
| VAL-060 | Failure during speculative candidate arithmetic | Implementation must avoid observable speculative failure |

### 37.6 Compact representation and layout

| ID | Setup | Required observation |
|---|---|---|
| VAL-061 | Every value fits the proven compact range | Round-trip values are exact |
| VAL-062 | One value exceeds the guarded compact range | Generic representation is selected safely |
| VAL-063 | Profile contains only small values without proof | No unchecked narrowing is accepted |
| VAL-064 | Field range changes after compact cache construction | Cache is updated or invalidated |
| VAL-065 | Delete a dense row and move the last row into its place | Both identity mappings remain correct |
| VAL-066 | Reuse a deleted slot with a new generation | Old handle remains invalid |
| VAL-067 | Generation reaches its maximum | Exhaustion policy prevents resurrection |
| VAL-068 | Layout changes while wire schema remains fixed | Serialized data follows the schema |
| VAL-069 | Hot/cold split with an identity-observing operation | Identity behavior is preserved or plan rejected |
| VAL-070 | Two temporaries with overlapping live ranges | Scratch allocator does not share their storage |
| VAL-071 | Alignment requirements differ | Reused storage satisfies each lifetime's alignment |
| VAL-072 | Destination construction fails during assignment | Old value and cleanup follow the chosen assignment contract |

### 37.7 Incremental queries

| ID | Setup | Required observation |
|---|---|---|
| VAL-073 | Insert a matching row | Result equals full recomputation |
| VAL-074 | Insert a nonmatching row | Result membership remains unchanged |
| VAL-075 | Matching row becomes nonmatching | Old result is removed |
| VAL-076 | Nonmatching row becomes matching | New result appears in declared order |
| VAL-077 | Delete the current winner | Replacement matches full recomputation |
| VAL-078 | Update only an irrelevant field | No unnecessary semantic change occurs |
| VAL-079 | Change global predicate configuration | Complete invalidation or correct rebuild occurs |
| VAL-080 | Duplicate event | Delivery contract is followed without duplicate effects |
| VAL-081 | Missing event epoch | Incremental state is not accepted as current |
| VAL-082 | Both sides of a join change | Cross-term accounting is correct |
| VAL-083 | One changed join key has extreme fan-out | Correctness holds and cost is included |
| VAL-084 | Floating-point sum with cancellation | Unsupported exact incremental rewrite is rejected |

### 37.8 Demand-driven selection

| ID | Setup | Required observation |
|---|---|---|
| VAL-085 | Bound is below current winner | Candidate can be skipped with equal final result |
| VAL-086 | Bound equals winner and candidate has winning tie identity | Candidate is evaluated or proven unable to win |
| VAL-087 | Bound metadata is stale | Exact evaluation or safe bound refresh occurs |
| VAL-088 | New member exceeds an old group bound | Group bound is invalidated before use |
| VAL-089 | Every bound overlaps | Full result remains correct and overhead is measured |
| VAL-090 | Skipped score would have trapped | Eager-loop transformation is rejected |
| VAL-091 | Score callback has an observable effect | Demand pruning is rejected |
| VAL-092 | Empty candidate set | Absence result matches the reference |
| VAL-093 | All scores tie | Stable identity rule selects the same result |
| VAL-094 | Configuration changes all score bounds | Cached bounds are not reused incorrectly |
| VAL-095 | Bound arithmetic itself can overflow | Bound construction is rejected or uses safe arithmetic |
| VAL-096 | Group bound remains conservative but loose | Correctness holds despite reduced pruning |

### 37.9 Plan selection and compilation

| ID | Setup | Required observation |
|---|---|---|
| VAL-097 | Sparse/dense workload alternates around crossover | Hysteresis behavior is deterministic and semantically exact |
| VAL-098 | Representation transition reports a recoverable private failure | Initialized private construction is cleaned up and prior valid state remains usable |
| VAL-099 | Candidate has a different semantic hash | Candidate cannot join the exact plan set |
| VAL-100 | CPU feature unavailable | Unsupported native plan is never executed |
| VAL-101 | Search budget exhausted | Generic legal plan remains available |
| VAL-102 | Specialization recursion exceeds budget | Compiler stops specializing safely |
| VAL-103 | Imported effect summary changes | Affected compile cache is invalidated |
| VAL-104 | Profile fingerprint does not match source | Profile is rejected or explicitly treated as unmatched |
| VAL-105 | Hash-map iteration order changes | Generated semantic naming remains deterministic |
| VAL-106 | Candidate wins training inputs but loses held-out inputs | Report distinguishes the two results |
| VAL-107 | Secret-dependent dispatch under a constant-time contract | Dispatch is rejected |
| VAL-108 | Cost model is deliberately inaccurate | Only performance changes, never program meaning |

### 37.10 Engine and bridge

| ID | Setup | Required observation |
|---|---|---|
| VAL-109 | Workbench listener belongs to another project | Bridge detects or reports unverified project identity |
| VAL-110 | Compiler executable is missing | Job fails at startup, never reports compile success |
| VAL-111 | Engine returns nonzero exit with no parsed diagnostic | Raw failure remains visible |
| VAL-112 | Engine reports an error despite zero process exit | Validation does not claim success |
| VAL-113 | RPC accepted but completion times out | Unknown outcome is reported without unsafe replay |
| VAL-114 | User-owned editor blocks a headless job | Bridge reports conflict without automatic termination |
| VAL-115 | Generated output path escapes the owned root | Promotion is rejected |
| VAL-116 | Unowned file exists in generated destination | Generator preserves it or reports a conflict |
| VAL-117 | Source changes after artifact validation | Old validation does not approve the new artifact |
| VAL-118 | Cancellation races with process completion | Final job state reflects the defined lifecycle |
| VAL-119 | Profiler capability is unknown | Metrics remain unavailable, not zero |
| VAL-120 | Runtime scenario adapter is absent | Compile success is not presented as runtime success |

### 37.11 Authority, commands, and replay

| ID | Setup | Required observation |
|---|---|---|
| VAL-121 | Target deleted between capture and application | Command validity is checked at application |
| VAL-122 | Authority changes before application | Runtime authority contract is enforced |
| VAL-123 | Fourth command fails after three succeed | Completed prefix and fourth command's known, partial, or unknown effects are reported separately |
| VAL-124 | Setter has an intermediate callback | Unproven command coalescing is rejected |
| VAL-125 | Deferred command contains a short-lived view | Lifetime checker rejects the escape |
| VAL-126 | Replication baseline mismatch | Full recovery or explicit rejection occurs |
| VAL-127 | Duplicate client request | Declared deduplication/authority policy is enforced |
| VAL-128 | Replay uses a different PRNG algorithm with the same seed | Replay identity mismatch is detected |
| VAL-129 | Numeric tolerance hides a different selected entity | Semantic comparison still fails |
| VAL-130 | Trace is truncated before completion or termination is unknown | Result is incomplete; matching incomplete records cannot establish equivalence |
| VAL-131 | Native replay passes but live binding differs | Adapter test exposes the separate failure |
| VAL-132 | Source map belongs to another artifact | Mapping request is rejected as stale |

### 37.12 Benchmark and authoring evidence

| ID | Setup | Required observation |
|---|---|---|
| VAL-133 | Benchmark program never invokes its workload | Harness validation detects missing work |
| VAL-134 | Input generator traps before timing | Run is failed, not recorded as fast |
| VAL-135 | Rust and Beryl use different overflow policies | Comparison is marked invalid |
| VAL-136 | Candidate excludes index construction while baseline includes it | Manifest mismatch is rejected |
| VAL-137 | One process contributes many inner-loop timings | Sampling report identifies the actual independent unit |
| VAL-138 | Failed sample has a duration field of zero | Failure is excluded from performance ratios |
| VAL-139 | AI context lists an unimplemented proposed feature as available | Context validation fails |
| VAL-140 | Example targets an obsolete binding version | Example is marked stale or unsupported |
| VAL-141 | Formatter changes a floating-point literal's value | Round-trip test fails |
| VAL-142 | Diagnostic points into an older source revision | Staleness is explicit |
| VAL-143 | API search returns multiple overloads | Assistant receives disambiguating signatures |
| VAL-144 | Generated callback compiles but behavior probe fails | Compile and runtime evidence remain separate |

The additional review-derived cases VAL-145 through VAL-180 are in section 37.15.
The second review cases VAL-181 through VAL-232 are in section 37.16.

### 37.13 Metamorphic checks

Use metamorphic relationships when they follow from the exact contract:

- Reordering independent input storage while preserving declared logical order
  should not change an identity-ordered query result.
- Applying a no-op field update should not change a pure derived result.
- Full rebuild after each event should match incremental maintenance.
- Turning off an optimization should preserve the outcome.
- Selecting any eligible exact plan should preserve the outcome.
- Formatting source should preserve its parsed semantics.
- Regenerating an unchanged artifact should preserve its semantic fingerprint.

Do not invent metamorphic properties for floating-point or checked arithmetic.
For example, splitting and recombining a reduction may change its result or failure.

### 37.14 Failure minimization

When a differential test fails, retain:

- The smallest known input.
- Source and plan fingerprints.
- Reference outcome.
- Candidate outcome.
- First differing observable event.
- Transformation and proof records.

Use delta debugging to shrink traces while preserving the mismatch.
A minimized counterexample is a permanent regression test.
Do not discard the original full trace until the reduced case is verified.

### 37.15 Review-derived foundation regressions

These are proposed tests, not claims of tests run during document preparation.
Each test must exercise the real compiler path that could violate the contract.
Where a feature is outside the selected prototype, explicit rejection is acceptable.

| ID | Setup | Required observation |
|---|---|---|
| VAL-145 | Pass an initialized mutable scalar through set | Call remains valid and replaces its value |
| VAL-146 | Pass an initialized immutable scalar through set | Exclusive writable access is rejected |
| VAL-147 | A set callee returns an error union without assigning its output | Every ordinary return is checked; missing assignment is rejected |
| VAL-148 | False AND skips a set call, then its output is read | Output is not treated as definitely initialized |
| VAL-149 | True OR skips a sink call | Skipped branch does not execute; flow analysis uses the selected reachability policy |
| VAL-150 | A set callee returns from a possibly empty loop after assignment | The zero-iteration fallthrough still requires assignment |
| VAL-151 | Break or continue precedes an assignment in a loop body | Unreachable assignment cannot discharge an exit obligation |
| VAL-152 | Argument 18 overlaps an earlier exclusive argument | Conflict is detected or the unsupported analysis is rejected |
| VAL-153 | A nested place beyond six projections overlaps an ancestor | No truncation creates a false disjointness proof |
| VAL-154 | push, set, or clear is invoked through a read-only collection access | Mutating intrinsic is rejected |
| VAL-155 | A collection is resized while an element place or iteration view is live | Invalidating mutation is rejected or a specified snapshot is used |
| VAL-156 | Two logical struct copies contain a list; one list is changed | Value-copy independence is preserved on each supported target |
| VAL-157 | Nested owning elements are copied into another collection | Mutating a nested element cannot affect the original logical value |
| VAL-158 | Owning assignment copies a value onto itself | Value remains valid; cleanup occurs exactly once when implemented |
| VAL-159 | A skipped short-circuit operand contains min with an effectful argument | No temporary initializer escapes the skipped branch |
| VAL-160 | Effectful arguments are passed through nested calls | Selected receiver and argument evaluation order is preserved |
| VAL-161 | An assignment RHS attempts to invalidate the already selected destination | Invalidating access is rejected before retaining a stale place |
| VAL-162 | An ordinary function is used in v0.1 defer on both targets | It executes once at the source position |
| VAL-163 | Two modules each define State with different fields | Types and generated names remain distinct |
| VAL-164 | A private declaration is referenced without a permitted import | Module visibility is enforced by the selected language version |
| VAL-165 | An inner local shadows an outer local in its initializer | Initializer reads the outer identity; emitted names do not self-reference |
| VAL-166 | Source identifiers collide with backend keywords or temporary names | Generated identifiers remain unique and legal |
| VAL-167 | A constant expression overflows i8 while fitting i64 | Constant evaluation follows i8 semantics |
| VAL-168 | Narrow wrapping multiplication would overflow a promoted signed intermediate | Native helper remains defined and returns the modular result |
| VAL-169 | Native shifts encounter negative values or sign-bit boundaries | The documented shift profile is implemented without C undefined behavior |
| VAL-170 | Enfusion saturating arithmetic receives signed endpoint operands | Guarded arithmetic returns the correct endpoint without first overflowing |
| VAL-171 | Enfusion code observes two distinct returned error identities | Tagged profile distinguishes them; unsupported legacy use is rejected |
| VAL-172 | Formatter processes high-precision floats, 1.0, suffixes, and escaped chars | Parsed values, literal categories, suffixes, and structure are preserved |
| VAL-173 | check receives a missing file | Nonzero exit and a machine-readable input failure |
| VAL-174 | check selects Enfusion with an unsupported type hidden in a cast or local | Target rejection occurs before backend emission |
| VAL-175 | An end-to-end program prints expected output and then fails | Harness records failure despite matching text |
| VAL-176 | A program prints trap-like text but exits successfully | Trap test fails unless the selected termination protocol confirms failure |
| VAL-177 | Workbench builder is missing or its job times out | Explicit unavailable or timed-out result, never validated success |
| VAL-178 | Benchmark checked LCG terminates on first overflow | Sample is invalid; no speedup or overhead ratio is produced |
| VAL-179 | min(raw, 7) or an unchecked validator feeds an index | No nonnegative in-bounds proof is fabricated |
| VAL-180 | AI source requests an unsupported contract annotation or callback API | Feature support is diagnosed accurately before a success claim |

### 37.16 Second review regressions and contract counterexamples

These are specifications for future tests, not executed reproductions.
Diagnostic cases must exercise the frontend and CLI rejection path.
Behavior cases must exercise actual lowering and execution for the advertised target.
A target outside the declared subset must reject the construct explicitly.

| ID | Setup | Required observation |
|---|---|---|
| VAL-181 | try can return an error before assigning a set output | Output obligation is diagnosed on the implicit return edge |
| VAL-182 | All set outputs are initialized before try, which then fails | Valid error propagation preserves the initialized outputs |
| VAL-183 | A nested try can return after assigning only one of two set outputs | Every missing output is checked at that edge |
| VAL-184 | An untyped constant refers to itself | Bounded cycle diagnostic during type inference, not stack exhaustion |
| VAL-185 | Several untyped constants form an inference cycle | Diagnostic includes the dependency cycle and terminates |
| VAL-186 | A typed constant evaluates a reference cycle | Value-evaluation cycle is diagnosed independently of known types |
| VAL-187 | A typed boolean constant has a self-reference only in a skipped operand | Short-circuit evaluation does not fabricate an executed value cycle |
| VAL-188 | A very deep acyclic dependency or expression exceeds a configured budget | Controlled resource diagnostic without partial success or host-stack exhaustion |
| VAL-189 | A constant divides signed minimum by negative one | Specified overflow diagnostic without evaluating overflowing host division |
| VAL-190 | A constant computes signed minimum remainder negative one | Result matches the selected native zero-remainder contract without host UB |
| VAL-191 | Constant unary negation receives signed minimum | Specified overflow diagnostic without overflowing host negation |
| VAL-192 | Constant evaluation uses an unsigned value above signed 64-bit maximum | Width and unsigned magnitude remain intact |
| VAL-193 | A constant short-circuit operand would divide by zero if executed | No diagnostic or evaluation from the skipped operand |
| VAL-194 | An admitted float-to-integer constant cast is nonfinite or out of range | Defined selected conversion policy or explicit unsupported rejection; no host UB |
| VAL-195 | error.Bad is returned from a function returning i32 or void | Return-type diagnostic before either backend emits code |
| VAL-196 | A function returning !i32 uses bare return | Missing success payload is rejected under the recommended strict rule |
| VAL-197 | A function returning !void uses bare return | Valid success with no fabricated payload storage |
| VAL-198 | !T succeeds through each supported return branch | Success payload is assigned before success is reported on both admitted targets |
| VAL-199 | Literal 256 is assigned the type u8 without an explicit cast | Representability diagnostic, not implicit conversion to zero |
| VAL-200 | The signed i8 minimum is written as a negated literal magnitude | -128 is accepted without treating its positive magnitude as a standalone i8 value |
| VAL-201 | Positive literal 128 is assigned the type i8 | Representability diagnostic |
| VAL-202 | Negated literal magnitude exceeds the selected signed minimum | -129 for i8 is rejected without host overflow |
| VAL-203 | A u64 literal is exactly the maximum or exceeds it | Maximum is preserved; excess magnitude is rejected at the appropriate stage |
| VAL-204 | An integer-shaped literal acquires an existing floating context | Existing floating literal conversion semantics remain distinct from integer range checking |
| VAL-205 | Two functions omit a default containing min argument temporaries | Each occurrence has valid local definitions; no reference to another function's temporaries |
| VAL-206 | First default use is in a skipped branch and a later use executes | Later evaluation has its own dominating definitions and executes correctly |
| VAL-207 | An omitted default contains an allowed observable call | Call executes once for each actual omission and never for an explicitly supplied argument |
| VAL-208 | A default reads an earlier scalar parameter whose argument is effectful | Earlier argument is evaluated once and the bound value is used, or unsupported dependency is rejected |
| VAL-209 | Caller has a local with the same spelling as a default dependency | Resolved declaration/formal identity is preserved; no accidental caller capture |
| VAL-210 | A default requires its own or a later formal parameter | Unsupported/cyclic dependency is rejected; no uninitialized formal substitution |
| VAL-211 | A client-context omission evaluates a default calling server_only code | The same access diagnostic applies as for the equivalent explicit evaluation |
| VAL-212 | A default carries secret data or calls an unsuitable callee in constant_time context | Taint and call requirements include the implicit evaluation |
| VAL-213 | Default evaluation would conflict with an already selected exclusive argument | Access conflict is rejected before retaining an invalid place |
| VAL-214 | A parameter default contains try or another nonlocal control transfer | Initial default subset rejects it explicitly instead of returning from an accidental caller |
| VAL-215 | A struct field default violates the selected compile-time-default contract | Constant-default diagnostic; do not silently execute it during construction |
| VAL-216 | Enfusion !T call omits its defaulted source argument | Expanded source argument precedes the synthetic output slot |
| VAL-217 | An Enfusion call supplies some arguments and omits several trailing defaults | Signature and call share a complete ordered slot layout |
| VAL-218 | An Enfusion !void call uses defaults | Defaults expand normally and no value-output slot is appended |
| VAL-219 | catch receives a scalar instead of an error union | Source type diagnostic; no generated .err access on a scalar |
| VAL-220 | catch handles supported !i32 success and error paths | Every continuing path follows the declared result policy and initializes its result |
| VAL-221 | catch handles !void | Handler and control flow are preserved without declaring a void temporary |
| VAL-222 | A published write and a callback are exchanged | Unified trace comparison detects cross-kind reordering |
| VAL-223 | Cleanup, visible writes, and failure are interleaved differently | The global event order exposes the first relevant difference |
| VAL-224 | An external call re-enters Beryl before completing | Nested invocation events remain ordered inside the parent call interval |
| VAL-225 | Optional private workspace reservation fails recoverably | Reference state remains valid and fallback runs under its admitted resource contract |
| VAL-226 | A transition would call the public aborting allocator and then claim recovery | Admission/lowering rejects that false recovery path |
| VAL-227 | A retained optional index would starve a later required allocation | Resource proof/budget rejects the plan or the declared adequacy domain excludes that state explicitly |
| VAL-228 | A recoverable transition fails after constructing some owned elements | Only initialized new elements are destroyed; old representation and mappings remain valid |
| VAL-229 | Command four completes with known partial effects after three applied commands | Prefix is three and command four has a separate partial-effect record |
| VAL-230 | Command four times out after possible effects | Outcome remains unknown, later commands stop, and the batch is not automatically replayed |
| VAL-231 | Cancellation races with an operation whose effects are later confirmed | Job cancellation and confirmed effects are both recorded without a rollback claim |
| VAL-232 | A retry supplies an idempotency key unsupported by the receiver | Key alone does not permit replay of an operation with uncertain effects |

## 38. Implementation tickets and dependency order

These tickets describe future authorized implementation work.
They are intentionally smaller than the complete architecture.
Complete the acceptance evidence for one ticket before enabling dependent optimizations.

Directory suggestions below are provisional.
Use current repository conventions after checking the implementation revision.
No directory named here is created by this document.

### IMP-00: establish the current semantic baseline

**Dependencies:** none.
**Purpose:** distinguish historical findings from the current implementation.

Scope:

- Record compiler revision, toolchains, target profiles, and working-tree boundaries.
- Reproduce only the historical findings relevant to the first experiment.
- Identify already completed fixes.
- Inventory current test and benchmark entry points.
- Record unavailable engine capabilities explicitly.
- Refresh R01–R10 in section 45 and R11–R22 in section 46 against the actual working tree.
- Separate static evidence, executable reproductions, and already completed fixes.
- Select the minimal gate set from section 45.12 for the intended experiment.

Deliverable: a short current-state matrix with reproduction evidence.
Acceptance: every claimed prerequisite is linked to source or an executed check.
Stop condition: unresolved semantics affecting the selected experiment.
Do not expand this ticket into an unrelated whole-repository refactor.

### IMP-00A: settle compatibility and establish real identities

**Dependencies:** IMP-00.
**Purpose:** prevent a research feature from changing existing source meaning accidentally.

Scope:

- Record the set, value-copy, immediate-defer, and target error-profile decisions.
- Record return/catch rules, default-evaluation scope, and the resource profile from section 46.
- Use module-qualified declaration identities and enforce visibility deliberately.
- Distinguish binding identity from source spelling in both emitters.
- Allocate collision-free generated identifiers, including helpers and temporaries.
- Define the semantic profile and ABI identity carried by future plans.

Deliverable: a compatibility matrix and identity regression coverage.
Acceptance: VAL-145, VAL-146, and VAL-163 through VAL-166 for supported constructs.
Stop condition: distinct source types or bindings can share one emitted identity.
Ownership replacement with observable destruction remains outside this first task.

### IMP-00B: make local checks, formatting, and result reporting trustworthy

**Dependencies:** IMP-00.
**Purpose:** allow an assistant and harness to distinguish completion from failure.

Scope:

- Propagate input, manifest, target-selection, and frontend failures as nonzero exits.
- Run complete selected-target validation during check, including expression types.
- Preserve literal values, token categories, suffixes, and escapes during formatting.
- Compare parsed semantic structure directly rather than rounded debug dumps.
- Require exit status and output validation in executable test harnesses.
- Define explicit unavailable, failed, timed-out, cancelled, and successful results.
- Prevent simultaneous builds from sharing mutable artifact paths.

Deliverable: trustworthy local validation and a meaning-preserving formatter.
Acceptance: VAL-141, VAL-172 through VAL-177, and relevant job-isolation cases.
Stop condition: a failed operation can produce an accepted success artifact or sample.
Workbench-specific execution remains IMP-07; this task establishes its local prerequisites.

### IMP-00C: repair the selected legacy execution path

**Dependencies:** IMP-00A and IMP-01.
**Purpose:** keep the reference fallback and existing backend behavior trustworthy.

Scope:

- Reproduce control-flow, ownership, order, and arithmetic defects in the selected subset.
- Repair short-circuit initialization and early-exit handling for that subset.
- Check implicit try returns, reject incompatible error returns, and initialize success payloads.
- Bound constant type inference and value evaluation; validate literal magnitudes and host arithmetic.
- Instantiate supported defaults per call, including access/security effects and target argument slots.
- Reject non-error catch operands and unsupported default/control-flow forms before emission.
- Emit temporary statements inside their actual control-flow regions.
- Evaluate effectful operands and destinations exactly once in the selected order.
- Cover mutating intrinsics with the same access rules as ordinary methods.
- Remove unjustified alias promises; reject cases beyond current analysis capacity.
- Preserve immediate defer and explicitly supported target behavior.
- Compare the repaired path with IMP-01's independent oracle.

Deliverable: a bounded legacy subset suitable for reference and fallback execution.
Acceptance: applicable VAL-147 through VAL-162, VAL-167 through VAL-171,
and VAL-181 through VAL-221 for the declared supported subset.
Stop condition: a supposedly safe fallback still changes the selected observable contract.
Use conservative rejection when a full analysis repair belongs in IMP-03.
Do not introduce a second permanent ownership engine; share verified utilities as
the structured pipeline becomes available.

### IMP-01: define one executable semantic reference

**Dependencies:** IMP-00 and IMP-00A.
**Purpose:** make optimization outcomes comparable.

Scope:

- Select bounded integer arrays and a small structured control-flow subset.
- Define evaluation order, checked arithmetic, stores, and failures.
- Implement a simple reference evaluator or independent reference routines.
- Produce one globally ordered observable event stream for test builds.
- Specify resource-domain admission and compare only complete traces from matching profiles.
- Keep the evaluator independent of backend helper implementation where practical.
- Include declared-width constant arithmetic and explicit short-circuit control flow.

Deliverable: semantic contract plus executable oracle.
Acceptance: boundary and failure-order cases have explicit expected outcomes.
Relevant cases: VAL-001 through VAL-012, VAL-147 through VAL-151, VAL-167,
and the admitted arithmetic/return cases in VAL-181 through VAL-204 plus VAL-222 through VAL-224.
Stop condition: source semantics remain disputed or inconsistent across the selected subset.

### IMP-02: add Structured IR for the selected subset

**Dependencies:** IMP-01.
**Purpose:** normalize meaning without rewriting the entire compiler.

Scope:

- Add typed identities, nested regions, places, and failure sites.
- Normalize expression evaluation order.
- Expand defaults into fresh call-occurrence regions before access/security analysis.
- Represent try's error edge as an ordinary error return with output obligations.
- Preserve source provenance.
- Add a stable human-readable IR dump.
- Keep unsupported functions on the existing path.
- Validate semantic-profile and ABI compatibility at every crossing to that path.
- Conservatively classify unverified callees and reject unsupported owning crossings.

Deliverable: source-to-IR lowering and structural verifier.
Acceptance: reference traces from source and IR agree on the selected subset.
Relevant cases: VAL-037 through VAL-048.
Stop condition: lowering requires reconstructing lost semantics from backend code.

### IMP-03: establish access, cleanup, and effect facts

**Dependencies:** IMP-02.
**Purpose:** supply trusted preconditions for transformations.

Scope:

- Analyze structured places without small silent truncation limits.
- Represent cleanup obligations and early exits.
- Infer conservative read/write/shape/failure effects.
- Implement safe widening when analysis budgets are exhausted.
- Use per-edge initialization and move states, including loop exits and short-circuit edges.
- Include intrinsic receivers, collection storage identities, and live-view invalidation.
- Include omitted defaults, implicit returns, and resource effects in analysis coverage.
- Keep taint-lint acceptance separate from typed range and authority evidence.

Deliverable: verified analysis records attached to IR.
Acceptance: negative ownership/effect cases are rejected or conservatively classified.
Relevant cases: VAL-013 through VAL-036, VAL-148 through VAL-155, and VAL-179.
Stop condition: an unknown call can retain unjustified optimization facts.

### IMP-04: lower the reference plan

**Dependencies:** IMP-02, IMP-03, IMP-00B, and IMP-00C.
**Purpose:** prove that the new representation can feed useful target code.

Scope:

- Lower the selected subset to defined C.
- Lower the supported equivalent subset to structured EnforceScript.
- Preserve source mappings and failure categories.
- Reject unsupported target forms before emission.
- Select explicit arithmetic, error, and cleanup profiles for each target.
- Prove compatibility with the legacy calling boundary for the supported subset.
- Use a shared ordered ABI slot descriptor for signatures and calls, including expanded defaults.

Deliverable: reference-plan target emitters for the bounded subset.
Acceptance: native reference agreement and engine compile evidence where available.
Engine runtime agreement remains a separate replay/scenario requirement.
Stop condition: the backend silently weakens a source contract.

### IMP-05: build a trustworthy comparison harness

**Dependencies:** IMP-01, IMP-00B, and IMP-00C for the measured subset; independent of IR implementation.
**Purpose:** obtain credible performance evidence before adding advanced plans.

Scope:

- Define benchmark manifests.
- Verify workload execution and output consumption.
- Capture failures separately from timings.
- Add idiomatic and matched tuned Rust baselines.
- Preserve raw paired samples and environment information.
- Replace the terminating checked-LCG workload with a completing checked workload.
- Compare modular LCG only against baselines with the same modular semantics.
- Treat invalid warmups, failed processes, and mismatched checksums as experiment failures.

Deliverable: one complete, reproducible native comparison.
Acceptance: deliberately broken workloads fail the harness correctly.
Relevant cases: VAL-133 through VAL-138 and VAL-175, VAL-176, VAL-178.
Stop condition: an invalid or unexecuted workload can produce a performance result.

### IMP-06: build a versioned binding index

**Dependencies:** IMP-00 and IMP-00A.
**Purpose:** remove guessed engine API usage.

Scope:

- Reuse or adapt the existing local API-index work where appropriate.
- Preserve exact declarations and overload identities.
- Add target/version fingerprints.
- Separate extracted facts from reviewed semantic overlays.
- Implement one family of compile probes.

Deliverable: searchable binding records with evidence status.
Acceptance: one known API change invalidates the appropriate record and probe.
Stop condition: an unknown effect is represented as a verified harmless effect.

### IMP-07: implement reliable Workbench validation jobs

**Dependencies:** IMP-06, IMP-00B, and the verified existing build path.
**Purpose:** make engine compile results trustworthy.

Scope:

- Inspect project and session identity.
- Stage generated artifacts with hashes.
- Run a supported compile-validation operation.
- Return explicit job states, diagnostics, and raw logs.
- Handle startup failure, timeout, cancellation, and project mismatch.
- Treat a missing builder as unavailable and require evidence for the exact artifact.
- Use owned job directories and reject stale completion messages.

Deliverable: local CLI/library operation and structured result schema.
Acceptance: VAL-109 through VAL-120, within the implemented capability set.
Stop condition: the bridge can claim success for an unvalidated artifact.
An MCP adapter is optional after the core operation works.

### IMP-08: expose current compiler context and diagnostics

**Dependencies:** IMP-00A, IMP-00B, and IMP-06.
**Purpose:** improve AI authoring before advanced optimization is complete.

Scope:

- Return actual supported features.
- Return symbol signatures, target support, and source fingerprints.
- Return binding context and validated examples.
- Provide machine-readable diagnostics with related spans.
- Advertise unsupported generics, callback APIs, and contract annotations accurately.
- Generate examples from validated concrete source, not from research pseudocode.

Deliverable: model-neutral context interface.
Acceptance: stale context and unimplemented examples are identified accurately.
Relevant cases: VAL-139 through VAL-144, VAL-172, VAL-174, and VAL-180.
Stop condition: generated context presents research syntax as current language support.

### IMP-09: implement versioned facts and entry guards

**Dependencies:** IMP-03 and IMP-04.
**Purpose:** amortize validation and support safe region optimization.

Scope:

- Track content, shape, and identity dependencies.
- Implement a small proof-rule checker.
- Establish fixed-view facts statically or through total guards.
- Invalidate facts on relevant effects.

Deliverable: one verified fixed-view region with scalar execution.
Acceptance: shape mutation and alias counterexamples invalidate the capability.
Stop condition: a guard or its arithmetic can fail before selecting fallback.
Do not implement vectorization in this ticket.

### IMP-10: prototype checked block execution

**Dependencies:** IMP-05 and IMP-09.
**Purpose:** test the mechanism in section 13.

Scope:

- Only checked i32 multiply/add.
- Fixed disjoint views.
- One final output store per iteration.
- Safe speculation and scalar recovery.
- A small measured set of block widths.

Deliverable: feature-gated native candidate and equivalent Rust implementation.
Acceptance: VAL-049 through VAL-060 and a complete performance report.
Stop condition: no useful win after widening, guard, and recovery costs.
A failed experiment should leave a clear report, not an enabled complex default.

### IMP-11: prototype one incremental filter

**Dependencies:** IMP-03, IMP-04, and IMP-05.
**Purpose:** test exact reduction in repeated work.

Scope:

- Stable-key finite table.
- One pure total predicate.
- Insert, update, delete.
- Deterministic result order.
- Full rebuild on invalid history.

Deliverable: reference and incremental implementations with trace comparison.
Acceptance: exhaustive tiny states and randomized/adversarial event traces agree.
Relevant cases: VAL-073 through VAL-081.
Stop condition: dependency tracking cannot account for every predicate input.
Do not add joins before the filter's maintenance costs are understood.

### IMP-12: prototype storage and layout improvements

**Dependencies:** IMP-03, IMP-04, and IMP-05.
**Purpose:** isolate copy, allocation, and memory-traffic costs.

Scope:

- One destination-passing transformation.
- One private scratch-reuse transformation.
- One Beryl-owned hot-column layout.
- Explicit conversion and identity maintenance.
- Prove resource admission for peak old-plus-new storage and any recoverable allocation path.

Deliverable: three separately selectable ablations.
Acceptance: ownership, cleanup, and identity cases agree with the reference.
Relevant cases: VAL-065 through VAL-072.
Stop condition: reuse requires undocumented engine identity or lifetime assumptions.

### IMP-13: prototype exact bound-driven selection

**Dependencies:** IMP-09 and IMP-11.
**Purpose:** test section 19 on a concrete total scoring function.

Scope:

- Bounded integer score.
- Verified upper bound.
- Stable identity tie-breaker.
- Exact fallback when bounds are unavailable.
- At most one simple group-bound representation.

Deliverable: dense and bound-first plans with matched Rust versions.
Acceptance: VAL-085 through VAL-096 and held-out selectivity measurements.
Stop condition: bounds cannot be maintained conservatively at acceptable cost.

### IMP-14: prototype compact private representation

**Dependencies:** IMP-09 and IMP-12.
**Purpose:** test range-driven storage reduction.

Scope:

- One bounded integer field family.
- Static narrowing first.
- Optional guarded private cache afterward.
- No public ABI or wire-layout changes.

Deliverable: compact representation with exact round-trip and invalidation tests.
Acceptance: VAL-061 through VAL-064 and measured conversion break-even.
Stop condition: conversion or retained duplicate storage dominates expected reuse.

### IMP-15: select between two exact plans

**Dependencies:** IMP-05 and at least two validated compatible plans.
**Purpose:** determine whether adaptation improves changing workloads.

Scope:

- Cheap phase-entry features.
- Explicit transition costs.
- Measured crossover.
- Hysteresis.
- Generic fallback.
- Distinguish recoverable optional construction from public aborting allocation failure.
- Include retained storage and future required allocations in the admitted resource model.

Deliverable: two-plan selector with alternating-workload tests.
Acceptance: VAL-097 through VAL-100 and end-to-end transition-inclusive timing.
Stop condition: selection overhead erases the benefit over one robust static plan.

### IMP-16: add bounded offline schedule search

**Dependencies:** IMP-15.
**Purpose:** reduce manual tuning effort without weakening legality checks.

Scope:

- Enumerate a small finite candidate set.
- Reuse existing legality validation.
- Enforce compile-time and code-size budgets.
- Separate training and held-out workloads.
- Persist source and environment fingerprints.

Deliverable: reproducible tuning report and selected plan artifact.
Acceptance: VAL-101 through VAL-108.
Stop condition: search repeatedly overfits or makes routine builds unpredictable.
Do not add model inference or equality saturation in the first implementation.

### IMP-17: implement replay across the engine boundary

**Dependencies:** IMP-04 and IMP-07.
**Purpose:** connect native confidence to actual generated-script behavior.

Scope:

- One capture schema.
- One Beryl-owned state schema.
- One command schema.
- Bounded trace recording.
- Reference/native/script comparison.
- A live adapter scenario.
- Unified cross-kind event traces and per-command partial/unknown effect outcomes.

Deliverable: a reproducible failure or success trace from the intended project.
Acceptance: replay distinguishes computational, target, and adapter mismatches.
Relevant cases: VAL-121 through VAL-132.
Stop condition: captured inputs omit a nondeterministic dependency.

### IMP-18: generate one useful component adapter

**Dependencies:** IMP-06, IMP-07, IMP-08, and IMP-17.
**Purpose:** demonstrate simple end-to-end AI authoring.

Scope:

- One verified component base.
- One callback family.
- Editor property mapping.
- Explicit authority behavior.
- Native-testable Beryl logic.
- Source-mapped engine diagnostics.

Deliverable: a small real mod feature written primarily in Beryl.
Acceptance: a second assistant can reproduce the workflow from generated context
without guessing signatures or editing generated wrappers.
Stop condition: the example only works through undocumented manual editor state.

### IMP-19: integrate and decide what becomes default

**Dependencies:** relevant validated performance plans plus IMP-17 and IMP-18.
**Purpose:** select a useful product configuration from the experiments.

Scope:

- Run the integrated cases in section 36.
- Include strong Rust and handwritten-script comparisons.
- Include unfavorable workload regimes.
- Measure authoring effort.
- Evaluate compiler complexity and maintenance cost.

Deliverable: adoption decision for each feature.
Acceptance: every enabled default has correctness evidence, a useful application,
and a documented fallback.
Stop condition: a feature survives only because of an isolated favorable microbenchmark.

### 38.1 Suggested first implementation sequence

The default research sequence is:

```text
IMP-00 -> IMP-00A -> IMP-01 -> IMP-02 -> IMP-03
   |          |         |
   |          +---------+-> IMP-00C
   +-> IMP-00B

IMP-02 + IMP-03 + IMP-00B + IMP-00C -> IMP-04
IMP-01 + IMP-00B + IMP-00C -> IMP-05
IMP-03 + IMP-04 -> IMP-09
IMP-05 + IMP-09 -> IMP-10
IMP-03 + IMP-04 + IMP-05 -> IMP-11 and IMP-12
IMP-09 + IMP-11 -> IMP-13
IMP-09 + IMP-12 -> IMP-14

IMP-00 + IMP-00A -> IMP-06
IMP-06 + IMP-00B -> IMP-07
IMP-00A + IMP-00B + IMP-06 -> IMP-08
IMP-04 + IMP-07 -> IMP-17
IMP-06 + IMP-07 + IMP-08 + IMP-17 -> IMP-18

IMP-05 + validated compatible plans -> IMP-15 -> IMP-16
relevant validated plans + IMP-17 + IMP-18 -> IMP-19
```

The diagram is a reading aid; the dependency lists on tickets are authoritative.
Tooling tickets can provide value before the experimental optimizer is ready.

## 39. Adoption gates and research scorecard

Every candidate moves through explicit evidence levels.
Do not enable a research prototype by default merely because it compiles.

### 39.1 Evidence levels

| Level | Evidence |
|---|---|
| E0 | Written hypothesis and plausible cost model |
| E1 | Precise supported semantics and counterexamples |
| E2 | Reference implementation and local correctness tests |
| E3 | Verified transformation with differential/adversarial validation |
| E4 | Reproducible isolated performance result |
| E5 | End-to-end held-out application result |
| E6 | Target integration and regression monitoring suitable for adoption |

These levels are project process labels, not formal proof classifications.
An E6 feature may still have bugs.
State the actual scope of verification.

### 39.2 Candidate scorecard

For each feature, record:

- Supported program subset.
- Fraction of representative workloads eligible.
- Exact semantic obligations.
- Trusted rules added.
- Fast-path overhead.
- Fallback overhead.
- Best, typical, and unfavorable measured regimes.
- Peak memory change.
- Code-size change.
- Compile-time change.
- AI authoring impact.
- Engine integration status.
- Known failure modes.
- Adoption recommendation.

### 39.3 Suggested default criteria

A feature is a candidate for default enablement when:

- It preserves the declared contract in the supported subset.
- Its legality checks are conservative and inspectable.
- It has a robust fallback.
- Representative applications benefit or remain within a predefined regression budget.
- Its complexity is justified by actual use.
- Diagnostics explain rejection and fallback.
- Generated script remains supportable where the feature targets Enfusion.

A feature can remain opt-in when its benefit depends on a narrow workload.
A feature should be removed or redesigned when its overhead routinely dominates.

### 39.4 Ambitious targets

Suggested stretch goals:

- Repeatable application-level wins over tuned Rust on at least two named native workloads.
- Substantial improvement over strong handwritten EnforceScript in at least one real scenario.
- Fewer repair cycles for assistant-authored mods using verified context and wrappers.
- Reliable reproduction of engine-boundary failures from bounded traces.

Do not assign a guaranteed multiplier before obtaining a baseline.
The project can pursue a large gain without pretending its magnitude is known.

### 39.5 AI authoring measurements

Use a fixed suite of mod tasks.
Provide equivalent project access and budgets to each workflow being compared.
Record model/version and tool configuration.

Measure:

- First-check success rate.
- Number of compiler repair cycles.
- Number of invented or incorrect API calls.
- Time to a validated engine compile.
- Time to a passing runtime scenario.
- Human corrections required.
- Source size and generated boilerplate.
- Regression rate on a later requested change.

Generated lines should not count as human-authored complexity.
Do not treat a shorter source file as proof of easier maintenance by itself.

## 40. Security and reliability boundaries of the implementation

The user's performance goal includes strong security and predictable behavior.
The implementation should make those properties explicit without turning every
ordinary mod task into a security research project.

### 40.1 Compiler input

Treat source files, manifests, binding metadata, profiles, and traces as inputs
that can be malformed.

Check:

- Lengths before allocation.
- Integer overflow in sizes and offsets.
- Recursive nesting limits.
- Path containment for generated artifacts.
- Schema versions.
- Resource budgets for search and analysis.

An arena reduces individual lifetime management but does not prevent buffer overruns,
integer overflow, or use of invalid pointers.
The C implementation still needs disciplined validation.

### 40.2 Optimizer trust

Separate candidate construction from legality checking.
Do not allow a candidate to mark its own unverified preconditions proven.
Treat profile records as cost hints.
Treat external engine metadata according to its evidence level.

Invalid proof records should fail closed for the optimization:
retain the correct reference plan and surface the compiler-internal issue in validation.
Do not weaken the language contract to keep a candidate enabled.

### 40.3 Tool execution

The bridge should execute only the requested operation on the selected project.
Use explicit arguments and scoped outputs.
Do not interpret compiler diagnostics or project comments as shell instructions.

Normal builds do not need network access to model services.
Optional research integrations should not become hidden build dependencies.

### 40.4 Persistence and caches

Validate cache metadata before reuse.
Include semantic and binding dependencies in keys.
Treat partial writes as incomplete artifacts.
Use atomic publication where the filesystem API supports the intended operation.

Do not assume that renaming multiple files produces a multi-file atomic transaction.
An artifact manifest can identify a complete generation and prevent mixed-version use.

### 40.5 Reliability claims

Memory safety, authority validation, exact arithmetic, reproducible builds,
and constant-time execution are different claims.
List the evidence for each separately.

A language can improve several of them without having solved all of them.
The documentation should expose the actual supported guarantees.

## 41. Risks, unresolved decisions, and rejected shortcuts

The architecture is intentionally ambitious.
Its main risk is building too much machinery before identifying profitable workloads.
The ticket sequence limits that risk by requiring small experiments.

### 41.1 Risk register

| Risk | Early signal | Response |
|---|---|---|
| Structured IR becomes a second inconsistent language | Reference traces disagree after normalization | Stop optimization work and repair semantics |
| Proof system grows faster than useful transformations | Many rules support no measured win | Shrink the supported subset |
| Incremental indexes consume excessive memory | Retained state dominates the application | Use dense fallback or narrower dependency tracking |
| Dirty tracking costs more than recomputation | Small or high-churn workloads regress | Select full evaluation |
| Bounds rarely prune | Nearly every score is still evaluated | Disable bound-first plan for that regime |
| Narrow storage conversion dominates | Too few reuses before invalidation | Keep native-width representation |
| Scratch reuse breaks reentrancy | Nested callback corrupts state | Use per-invocation storage or verified restriction |
| Vector widening loses throughput | More instructions and register pressure | Reject the candidate width or mechanism |
| Plan dispatch thrashes | Frequent representation transitions | Add measured hysteresis or use a static plan |
| Schedule search overfits | Training wins disappear on held-out traces | Reduce search space and improve workload coverage |
| Generated script becomes opaque | Debugging requires reconstructing transformations manually | Improve provenance or limit script transformations |
| Binding metadata overstates purity | Runtime behavior contradicts overlay | Downgrade the contract and invalidate dependent plans |
| Engine version changes silently | Compile probes or behavior tests change | Refresh bindings and reject stale artifacts |
| Native tests create false engine confidence | Logic passes while adapter fails | Keep live boundary scenarios mandatory for adapter claims |
| AI examples drift from actual support | Assistants repeatedly generate unavailable syntax | Generate context from the compiler and tested examples |
| Build tooling reports false success | Missing executable or timeout appears successful | Repair result semantics before further integration |
| Benchmark scope is unfair | Candidate omits maintenance paid by baseline | Correct the manifest and rerun |
| Rust adopts the same optimization and closes the gap | Matched tuned baseline becomes equal | Report automatic optimization/productivity value accurately |
| Compile times become unpredictable | Search or specialization dominates checks | Separate development and tuning modes |
| Maintenance exceeds project capacity | Features lack owners and regression coverage | Keep fewer well-supported mechanisms |

### 41.2 Decisions required before the first semantic prototype

These are small explicit decisions, not reasons to postpone the whole project.

| Decision | Proposed starting position | Must be resolved before |
|---|---|---|
| Expression order | Deterministic documented order, including destinations | IMP-01 |
| Checked trap category | Preserve current selected target contract explicitly | IMP-01 |
| Set destinations | Preserve initialized mutable and uninitialized destinations; assign on every ordinary return | IMP-00A |
| User defer | Preserve immediate v0.1 execution; scope-exit behavior requires a versioned change | IMP-00A |
| Cleanup on trap | Preserve abort-without-unwinding initially; specify ownership cleanup separately | IMP-01 |
| Allocation failure | Preserve public abort behavior; choose explicit resource adequacy or resource-observable equivalence | IMP-01; allocation-changing plans before IMP-03/IMP-12 |
| Default arguments | Expand supported expressions per omission in caller order; reject unsupported nonlocal exits | IMP-00A and IMP-00C |
| Error returns and catch | Require matching union types and initialized success/continuation payloads | IMP-01 and IMP-00C |
| Owning duplication | Preserve value assignment; optimize semantic copies without requiring new clone syntax | IMP-00A and IMP-03 |
| Error identity | Explicit legacy tag-erasing profile or verified tagged ABI; no silent equivalence claim | IMP-04 |
| Stored references | Defer; use bounded non-escaping views first | IMP-09 |
| Query ordering | Stable key order unless another explicit order is requested | IMP-11 |
| Query failure semantics | Initial optimized query subset is total | IMP-11 |
| Cross-target FP equality | No blanket bitwise promise | IMP-17 |
| Engine snapshot coherence | Exactly the verified adapter guarantee | IMP-17 |
| State versus command commit | Separate desired, confirmed, and uncertain effects; retain a per-command ledger | IMP-17 |
| Default plan count | Small bounded set, initially two or three | IMP-15 |

If the current specification already settles one of these differently,
record the conflict and either preserve it or propose a deliberate language change.
Do not silently implement the blueprint's preference over established source semantics.

### 41.3 Rejected shortcuts

Do not pursue these as foundations:

- Disabling safety checks and calling the result hyper-optimized.
- Comparing checked Beryl with a different semantic workload in Rust.
- Assuming a native backend's performance transfers to the script VM.
- Treating source annotations as unchecked proof assertions.
- Using observed ranges as guaranteed ranges.
- Skipping unchanged-input state evolution.
- Treating arbitrary engine setters as coalescible assignments.
- Treating every engine getter as a stable pure read.
- Replacing all containers with one fashionable layout.
- Running expensive model inference during ordinary compilation.
- Adding a direct LLVM backend before proving the need.
- Rebuilding the compiler wholesale before one useful experiment works.
- Reporting an analytical visualization as a benchmark.
- Claiming historical uniqueness without a separate research review.

### 41.4 What would invalidate the central hypothesis

The integration hypothesis weakens if:

- Most important workloads remain dominated by opaque engine operations.
- Useful domain information cannot be expressed without burdensome annotations.
- Maintaining exact dependencies costs more than the work it saves.
- The compiler cannot preserve readable, debuggable generated script.
- Strong Rust and handwritten-script implementations remain equally easy to author
  and consistently faster under matched conditions.

Those outcomes should change the architecture.
They do not justify relabeling weak results as revolutionary.

## 42. Research context and evidence boundaries

This blueprint proposes a Beryl-specific integration.
Several ingredients have substantial prior art.
Study them to avoid rediscovering known limitations and to identify strong baselines.

### 42.1 Source map

| Source | Relevant topic | What it does not establish |
|---|---|---|
| [Rust PGO documentation](https://doc.rust-lang.org/rustc/profile-guided-optimization.html) | Profile-informed compilation already available in Rust | A Beryl performance advantage |
| [Cargo profiles](https://doc.rust-lang.org/cargo/reference/profiles.html) | Configuration needed for fair Rust comparisons | Equivalent benchmark semantics by default |
| [LLVM vectorizers](https://llvm.org/docs/Vectorizers.html) | Existing loop and instruction vectorization | Legality of Beryl-specific speculation |
| [LLVM language reference](https://llvm.org/docs/LangRef.html) | Downstream instruction and attribute contracts | Correctness of the Beryl frontend |
| [LLVM UB manual](https://llvm.org/docs/UndefinedBehavior.html) | Undefined and poison-related behavior | Permission to weaken safe Beryl semantics |
| [Clang UBSan](https://clang.llvm.org/docs/UndefinedBehaviorSanitizer.html) | Dynamic detection of selected undefined operations | A complete proof of generated C correctness |
| [Halide scheduling tutorial](https://halide-lang.org/docs/tutorial/lesson_05_scheduling_1.html) | Separating computation from schedule | Beryl's ownership or engine effect rules |
| [MLIR Transform dialect](https://mlir.llvm.org/docs/Dialects/Transform/) | Explicit transformation infrastructure | A requirement to adopt MLIR |
| [Alive2](https://github.com/AliveToolkit/alive2) | LLVM-level translation validation | Whole-language or engine correctness |
| [Differential dataflow](https://github.com/TimelyDataflow/differential-dataflow) | Incremental computation and a Rust comparison point | Automatic wins on small game loops |
| [Adapton](https://www.cs.tufts.edu/~jfoster/papers/cs-tr-5027.pdf) | Demand-driven incremental computation | Free dependency tracking |
| [egg](https://github.com/egraphs-good/egg) | Equality-saturation infrastructure | Correctness of proposed rewrite equalities |
| [Hylo introduction](https://hylo-lang.org/introduction/) | Mutable value-semantics language design | A ready-made Beryl implementation |
| [Mutable value-semantics paper](https://arxiv.org/abs/2106.12678) | Native implementation techniques for value semantics | EnforceScript representation costs |
| [Workbench plugins](https://community.bistudio.com/wiki/Arma_Reforger%3AWorkbench_Plugin) | Engine development integration reference | Installed-version compatibility without a probe |
| [Script profiling](https://community.bistudio.com/wiki/Arma_Reforger%3AScript_Profiling) | Engine measurement reference | Profiler export availability in this bridge |

The descriptions above identify topics to investigate.
They do not claim the systems share Beryl's exact contracts.
Keep source-derived claims separate from proposed Beryl mechanisms.

### 42.2 Formal verification scope

A local proof checker can validate selected transformations.
An LLVM validator can check selected downstream translations within its supported scope.
A differential test can find disagreements on tested inputs.
An exhaustive tiny-domain test can cover that finite domain.

None of these individually proves the complete compiler correct.
The implementation report should say exactly what was checked.
Do not call a bounded test a general theorem.

### 42.3 Novelty questions worth investigating

Potential research questions include:

- Can failure-preserving block execution compose with phase-level ownership facts
  at a lower cost than repeatedly rediscovering them in a general optimizer?
- Can one dependency representation support both exact incremental maintenance
  and admissible demand pruning without excessive bookkeeping?
- Can layout and lifetime planning share enough information to improve both
  memory traffic and allocation behavior in a small compiler?
- Can engine binding contracts make cross-boundary optimizations predictable
  while producing readable script?
- Can compiler-generated context reduce assistant repair cycles measurably?

These are research questions, not established novel contributions.
A publication or patent-oriented claim would require a separate prior-art review.

### 42.4 Evidence recorded for this document

This document was grounded in the repository's existing design, status,
compiler headers, driver structure, and earlier review/hypothesis documents.
The current source tree was read without modification for this delivery.

No new compiler feature was implemented.
No Rust benchmark was executed.
No Beryl performance measurement was produced.
No Workbench session was started or modified.
No runtime mod scenario was run.

The subsequent compatibility review read the compiler, runtime, both backends,
drivers, scripts, tests, and examples against this blueprint.
It verified that the embedded runtime matched its source and that 121 inventoried
files remained unchanged during that review.
Section 45 integrates its static findings and proposed solutions.
Those findings still require focused executable reproductions during authorized
implementation; document edits do not constitute code fixes or measured results.

The official Bohemia pages were not retrievable during the final web pass.
Consequently, exact installed-engine behavior remains a probe requirement.
The document intentionally avoids depending on an unverified new flag or API name.

## 43. Handoff instructions for Claude or ChatGPT

Use this section when beginning a future implementation task.
Do not treat the existence of this document as permission to alter code
while the owner's active request remains document-only.

### 43.1 Suggested implementation prompt

```text
Read docs/BERYL_OPTIMIZATION_AND_ENFUSION_BLUEPRINT.md.
Treat its features as proposals, not as current implementation facts.
Inspect the current repository and preserve unrelated in-progress work.

Begin with the explicitly authorized ticket or, if implementation of the
blueprint has been authorized without a ticket, establish IMP-00, read sections 45 and 46,
and choose the relevant IMP-00A/00B foundation work before IMP-01.
Complete IMP-00C for the selected legacy subset before treating it as a valid
fallback or benchmark baseline.

For each ticket:
  identify the supported semantic subset;
  list dependencies that are actually satisfied;
  implement the smallest complete experiment;
  retain a simple reference path;
  add the counterexamples required by that experiment;
  run the relevant validation;
  report exact scope and limitations;
  measure performance only with a validated harness;
  document the adoption decision.

Do not silently change language semantics.
Preserve value assignment, valid initialized set destinations, and immediate
v0.1 defer unless a separate language-version change is explicitly in scope.
Treat returned error unions as ordinary returns for set obligations.
Include implicit try returns and compiler-expanded defaults in all relevant analyses.
Use one ordered event trace and state the resource domain of every exactness claim.
Preserve partial and unknown command effects independently of job lifecycle status.
Do not reuse taint labels as range proofs or unchecked ownership as alias evidence.
Do not present proposed syntax as already supported.
Do not infer engine APIs from names or memory.
Use the installed binding index and verified project context.
Do not claim faster-than-Rust results without matched measurements.
Do not enable an experimental optimizer by default solely because it compiles.

When an assumption fails, update the design and explain the evidence.
Keep runtime speed, engine integration, and AI authoring quality visible
as separate dimensions of success.
```

### 43.2 Required ticket completion report

A completed implementation ticket should report:

1. The user-visible or compiler-visible behavior added.
2. The exact supported subset.
3. The files and components changed.
4. The semantic obligations enforced.
5. The tests actually executed.
6. The cases still unsupported.
7. Any measurements, with harness and environment identity.
8. Whether the feature is experimental, opt-in, or default.
9. The next dependency-ready ticket.

If engine validation was unavailable, say so directly.
Do not call the entire ticket complete if engine validation is a required
acceptance condition that remains unsatisfied.
Independent native work can still be reported as completed within its own scope.

### 43.3 Handling disappointing results

If a candidate loses:

- Verify that the implementation and harness are correct.
- Identify the dominant added cost.
- Check whether a smaller eligible subset changes the economics.
- Compare against the strongest equivalent implementation.
- Decide to retain, restrict, redesign, or remove the candidate.

Do not keep adding special cases indefinitely to rescue an unsupported claim.
A rejected experiment can save the project significant complexity.

### 43.4 Keeping the language simple

Before adding a new public feature, answer:

- What common author task becomes simpler?
- Can a library or generated adapter express it adequately?
- Can the compiler infer the relevant fact?
- Will an assistant reliably discover the correct usage from compiler context?
- Does the feature have one clear canonical pattern?
- What happens on each target?
- What diagnostic appears when the feature cannot be used?

If the feature mainly exposes optimizer implementation details,
keep it in internal plans or advanced tooling.

## 44. Decisions, glossary, and the intended end state

### 44.1 Candidate architectural decisions

The proposed starting decisions are:

1. Preserve a small, explicit Beryl authoring model.
2. Keep model APIs outside ordinary compilation and execution.
3. Retain C/Clang as the first native backend.
4. Continue generating EnforceScript for Enfusion.
5. Introduce a structured semantic IR for bounded subsets.
6. Make effects, failures, ownership, and dependency versions explicit internally.
7. Retain a simple reference plan for every optimized phase.
8. Start with total queries and one restricted checked block kernel.
9. Optimize Beryl-owned storage before making engine-layout assumptions.
10. Compare all serious native candidates with equivalently optimized Rust.
11. Make binding context, artifacts, diagnostics, and job results machine-readable.
12. Require measured usefulness before enabling a mechanism by default.

### 44.2 Glossary

| Term | Meaning in this blueprint |
|---|---|
| Phase | Bounded computation with identified inputs, state, and effects |
| Reference plan | Simple implementation defining the comparison behavior |
| Physical plan | A choice of layout, schedule, storage, and execution strategy |
| Exact plan | Plan preserving the selected observable contract |
| Observation | Value, write, command, failure, or cleanup behavior included in the contract |
| Place | A storage root plus field/index projections |
| Shape version | Identity of a collection's structural state |
| Content version | Identity of relevant stored values |
| Fact | Typed proposition with scope and dependency evidence |
| Guard | Total runtime test establishing a precondition |
| Versioned capability | Internal token packaging facts valid for a defined region |
| Materialization | Storing a derived result for later use |
| Incremental program | Program maintaining a result from explicit input changes |
| Admissible bound | Bound guaranteed to contain the exact result |
| Demand pruning | Skipping work proven unable to affect the required result |
| Destination passing | Constructing a result directly in a legal final destination |
| Scratch region | Private temporary storage with bounded lifetime |
| Plan transition | Conversion between equivalent representations or execution states |
| Semantic hash | Identity of the selected meaning and policy, not just source spelling |
| Binding fingerprint | Identity of the engine declaration and semantic contract set |
| Artifact fingerprint | Identity of a particular generated output |
| Runtime scenario | Execution in the engine to test behavior beyond compilation |
| Ablation | Measurement with one mechanism changed to isolate its contribution |
| Held-out workload | Evaluation input not used to choose the candidate |
| Approximate contract | Explicit permission for bounded value or freshness differences |

### 44.3 What an exceptional result would look like

An assistant writes a clear Beryl controller or query using verified project context.
The compiler identifies pure work, stateful work, and engine interaction.
It establishes access and arithmetic facts.
It chooses an exact plan suitable for the workload.
It produces readable script and a traceable native test artifact.

On sparse updates, it maintains only the derived data that changed.
On dense updates, it uses an efficient full scan.
Where bounds are useful, it avoids scoring candidates that cannot win.
Where memory traffic dominates, it uses an appropriate private layout.
Where allocation dominates, it constructs into destinations and reuses safe storage.
Where checked computation permits it, it uses validated block execution.

The assistant sees why a plan was chosen or rejected.
An engine compile error points back to the relevant Beryl declaration.
A runtime mismatch can be replayed with the actual captured inputs.
The performance report includes the costs paid at the engine boundary.

The language earns a strong reputation through those concrete properties.
The ambition is substantial measured speed together with a shorter, more reliable
path from an idea to a working Enfusion mod.
This blueprint supplies experiments and implementation contracts for pursuing that result.

## 45. Solutions to the static compatibility review

This section supplies the recommended engineering response to the subsequent review.
It is part of the proposed implementation contract, not a claim of completed repairs.
All implementation work remains subject to a future code-change request.
Examples of diagnostics, IR, helper signatures, and profiles here are proposed.

The intended outcome is a small trusted foundation supporting ambitious optimization.
Repair correctness for a selected semantic subset, prove the boundary, then measure.
Do not make unrelated language features prerequisites for a bounded experiment.
Do not allow a fallback outside that boundary to silently weaken the contract.

### 45.1 Evidence ledger and classification

The static review used the repository anchor and the then-current working tree.
Ownership fixes were already present as uncommitted changes.
They must remain intact unless subsequent evidence identifies a defect in them.
Source links below identify implementation areas; line numbers may move during work.
Use named functions and branches when reproducing each finding.

| Review item | Evidence location | Classification | Recommended owner |
|---|---|---|---|
| R01: set wording excludes valid existing destinations | [ownership.c](../src/sema/ownership.c), check_inout_arg; section 08.2 | Blueprint wording conflict, corrected here | IMP-00A |
| R02: access limits and intrinsic mutation bypass | [ownership.c](../src/sema/ownership.c), path_of and check_call_exclusivity | Existing implementation blocker | IMP-00C, then IMP-03 |
| R03: short-circuit and loop exit initialization | [ownership.c](../src/sema/ownership.c), walk_expr and walk_loop_body | Existing implementation blocker | IMP-00C, then IMP-03 |
| R04: temporary emission and repeated destinations | [c_backend.c](../src/back/c_backend.c), gen_binary and gen_stmt | Existing implementation blocker | IMP-00C, IMP-02, IMP-04 |
| R05: shallow owning copies and divergent target behavior | [c_backend.c](../src/back/c_backend.c); [enforce_backend.c](../src/back/enforce_backend.c), copy emission | Value-semantics defect plus compatibility decision | IMP-00A, IMP-03, IMP-12 |
| R06: arithmetic, error, and defer differences | [beryl_rt.h](../runtime/beryl_rt.h); [enforce_expr.c](../src/back/enforce_expr.c) | Defects and documented target limitations must be distinguished | IMP-01, IMP-00C, IMP-04 |
| R07: named type and emitted binding identity | [resolve.c](../src/sema/resolve.c), make_named_types; [types.c](../src/sema/types.c), intern_ty | Existing implementation blocker | IMP-00A |
| R08: formatter fidelity and unavailable query features | [format.c](../src/parse/format.c); [check_expr.c](../src/sema/check_expr.c) | Formatter defect; query mechanisms are future features | IMP-00B, IMP-08, IMP-11 |
| R09: failed checks and invalid timing samples | [main.c](../src/driver/main.c), cmd_check; [e2e.sh](../scripts/e2e.sh); [bench.sh](../scripts/bench.sh) | Existing validation blocker | IMP-00B, IMP-05, IMP-07 |
| R10: taint labels used beyond their evidence | [taint.c](../src/sema/taint.c), taint_of_call | Current lint limitation; cannot become an optimizer proof | IMP-03, IMP-06, IMP-18 |

For every refreshed entry, record:

```text
ReviewEvidence {
    review_id
    repository_revision
    relevant_working_tree_fingerprints
    inspected_symbol
    source_semantic_profile
    target_profile
    minimal_input
    evidence_kind: static_trace | executed_reproduction | verified_fixed
    expected_observation
    actual_observation_if_executed
    dependent_experiments
}
```

Absence of an executed reproduction is not evidence that a static finding is false.
It does mean that a report must not claim a failing test was run.
Mark a fix complete only with the relevant execution or rejection evidence.

### 45.2 Preserve set compatibility and define its obligations

Recommended rule: set permits a legal writable destination and promises assignment.
It does not require the caller's storage to start empty.

For scalar destinations:

| Caller state | Writable access | Result |
|---|---|---|
| Uninitialized local | Legal initialization access | Permit; require callee assignment |
| Initialized mutable local | Exclusive mutation access | Permit; replace its value |
| Initialized immutable local | No writable access | Reject |
| Read-only borrowed parameter | No writable access | Reject |
| Moved owning local | Legal reinitialization access | Requires the owning lifecycle policy before optimization |
| Field of a live initialized aggregate | Exclusive legal projection | Permit where the selected subset supports it |
| Field of a partially initialized aggregate | Partial initialization support unavailable | Reject conservatively in the first subset |

At function entry, a set parameter is logically unreadable until assigned.
This remains true even if the caller's destination previously held a value.
Assigning it establishes the callee's local initialization fact.
Every reachable ordinary return must establish that fact.
Falling off a void function is an ordinary return edge.
Returning error.SomeName through an error union is also an ordinary return edge.
The implicit error return generated by try has exactly the same obligation.
Section 46.2 defines the required lowering and diagnostic location.
An aborting trap has no continuing caller, so it has no post-return obligation.

At a call site, initialize the destination fact only on edges where the call ran
and returned normally after satisfying its output contract.
A skipped short-circuit operand must not initialize it.
A failed pre-call argument check must not initialize it.
Do not infer completion from an annotation on an unverified external call.

Initially admit scalars and fully supported aggregates without ownership cleanup.
Do not optimize owning set arguments until replacement has a defined lifecycle.
The eventual direct-destination implementation can carry an internal live-storage
flag separate from the callee's logical definite-initialization state.
Each replacement must evaluate its new value first, dispose the old live value
according to the chosen cleanup order, and establish exactly one live replacement.
Do not emit disposal against uninitialized storage.
Do not silently buffer all output writes until return: intermediate writes and
callbacks may be observable under an ordinary function's contract.
If staged output is desirable, give it the explicit phase semantics in section 06.

Required evidence: VAL-145 through VAL-148 and owning replacement cases when admitted.

### 45.3 Replace traversal-based assumptions with flow and access facts

#### 45.3.1 Definite initialization is a per-edge property

Use a finite dataflow domain over supported places.
One useful representation is a set of possible states drawn from:

```text
U = uninitialized
I = initialized and readable
M = moved and unreadable
empty state set = unreachable control-flow edge
```

A read requires exactly I on every reachable incoming path.
Joining branches unions their possible states while excluding unreachable edges.
Assigning a complete supported place establishes I after its RHS succeeds.
Moving an owning value requires I, then establishes M on the continuing edge.
A reachable set return requires I for every required output.
Use distinct diagnostics for possibly uninitialized and possibly moved reads.

Do not use one function-global unreachable Boolean for nested loops and branches.
Represent at least these exit kinds:

```text
normal
return(success_or_error, origin)
break(loop_id)
continue(loop_id)
abort
```

A try expression contributes an error-return edge as well as its success edge.
Traversing only its operand cannot establish the output contract.
Compiler-expanded defaults must be present before these facts are finalized.

An analysis-only control-flow graph may be derived from structured regions.
It need not become the shared low-level representation rejected by the original design.
Keep source structure available for EnforceScript generation and diagnostics.

For a loop:

1. Connect entry state to its condition.
2. Preserve the zero-iteration exit unless the selected semantics prove it impossible.
3. Join continuing body paths and matching continue edges into the back edge.
4. Join matching break edges into the loop's exit state.
5. Keep returns separate from the loop's continuation.
6. Iterate to a fixed point over the finite supported domain.
7. Diagnose reads from the converged facts, with source-path witnesses.

An assignment after break, continue, or return is unreachable on that path.
It must not contribute initialization to any live successor.
If an analysis budget is exceeded, use conservative unknown state or reject the
requested optimized region; do not report a partially converged state as proven.

For a && b, analyze b only on the true successor of a.
For a || b, analyze b only on the false successor of a.
Join the skipped and evaluated paths after the operator.
Constant reachability may remove an edge only when evaluating the condition has
the proven value and preserves all preceding effects and failures.

#### 45.3.2 Access paths must retain their meaning at every depth

Replace fixed field arrays and fixed argument arrays with arena-backed vectors.
A place contains a root identity and the complete supported projection sequence.
Constant and dynamic indices must be represented distinctly.
If an implementation limit remains temporarily, issue a precise diagnostic or
mark overlap unknown; never drop leading projections and continue proving disjointness.

Unknown overlap is not evidence for restrict.
For dynamic array indices, initially assume overlap unless inequality is proven.
Sibling fields are disjoint only when their actual layout and storage ownership justify it.
Two different local names are not necessarily different backing allocations.
Collection storage identity must therefore be distinguished from its header's local identity.

Initially omit restrict where the complete contract is not established.
This may cost native optimization opportunity but preserves correctness.
Later emit alias information from a verified access record whose validity covers
the actual generated pointer lifetime, including callees and nested storage accesses.
A guard may establish disjointness only if its own pointer/extent operations are defined.

#### 45.3.3 Intrinsics participate in the same ownership model

Maintain one compiler-owned intrinsic descriptor table shared by checking and lowering.
Its entries declare receiver access, argument modes, effects, and failure behavior.

| Intrinsic family | Receiver access | Minimum conservative effects |
|---|---|---|
| len | Read | Read shape |
| get/index | Read | Read content, bounds failure, possible element copy |
| set element | Exclusive mutation | Write content, bounds failure, possible copy and cleanup |
| push | Exclusive mutation | Read/write shape, write content, possible allocation and relocation |
| clear | Exclusive mutation | Write shape, possible element cleanup |

Element type determines whether copying and cleanup allocate or have further effects.
The table must not declare List<OwningValue>.get allocation-free solely because
List<i32>.get is cheap.
Unknown or unsupported element behavior propagates conservative effects.

For the initial iteration model, use a read loan over the traversed collection.
Reject conflicting mutation while it is live, including indirect calls and aliases.
Do not confuse a shallow header copy with an independent snapshot.
If snapshot iteration is later offered, define and account for its actual copy cost.
Invalidate shape-dependent facts on structural mutation and content facts on writes.

Required evidence: VAL-148 through VAL-155 and the existing ownership/effect catalog.

### 45.4 Normalize evaluation once, preserve control regions, and verify boundaries

Recommended expression-order decision for the new exact semantic profile:

- Evaluate a call's receiver, then explicit arguments, from left to right.
- Evaluate omitted defaults next in formal order using the bound argument values;
  their declaration scope and per-call effects follow section 46.5.
- Evaluate binary operands from left to right, except skipped short-circuit operands.
- Evaluate an assignment destination, including its index and validity checks, once.
- For compound assignment, read its old value before evaluating the RHS.
- Evaluate the RHS, perform checked computation, then write the destination once.
- Retain a valid exclusive place across that sequence or reject a conflicting RHS.

This order needs an explicit specification decision because current generated C
does not consistently enforce it.
If compatibility requires preserving another established order, select and identify
that profile before lowering; never select order accidentally from C evaluation rules.

Use an expression-lowering result with both a value and its enclosing effects:

```text
LoweredExpression {
    region
    result_value_id
    result_type_id
    exits
    origin
}
```

Append the expression's statements only to the region in which it actually executes.
Do not render an expression by appending arbitrary temporaries to a global output stream.
Short-circuit lowering should look like:

```text
left = evaluate(a)
result = false
if left:
    right_region:
        right = evaluate(b)
        result = right
```

Any min/max argument temporaries, checked operations, or calls inside b remain there.
The result storage or region yield must be initialized on every continuing path.
Evaluation-order tests must observe events, not only the final returned scalar.

For items[next_index()] += compute_delta(), bind the place once as in section 10.4.
The borrow checker must reject compute_delta if it could invalidate that place.
Saving a raw pointer before a reallocating call is not a correct normalization.
Recomputing the index afterward is not equivalent either if it is effectful.

When old and new compiler paths coexist, each call boundary needs:

```text
CallBoundaryContract {
    callee_symbol_id
    semantic_profile_id
    target_abi_id
    parameter_types_and_modes
    result_representation
    ownership_transfer_rules
    error_and_cleanup_behavior
    verified_effect_summary_or_unknown
}
```

Initially allow only compatible scalar and supported aggregate crossings.
Reject unsupported owning representations or use a separately verified adapter.
Do not reinterpret a legacy list header as a new compact table or phase view.
An opaque legacy callee invalidates relevant optimization facts conservatively.
An old backend may remain available without becoming an oracle for the new profile.

Required evidence: VAL-003, VAL-004, VAL-159 through VAL-161 and call-boundary regressions.

### 45.5 Preserve value semantics with explicit internal copy and move operations

The source-level default remains straightforward:

```text
var b = a
```

Where assignment is permitted, b is an independent logical value.
The compiler may implement this cheaply, but mutating b must not alter a through
an accidentally shared owning collection.
The first implementation should use eager recursive copies for supported owning types.
Automatic copy-on-write adds alias, mutation, threading, and identity obligations;
defer it until a measured workload warrants that complexity.

Separate semantic operations before choosing a representation:

```text
ReadBorrow(place)
CopyValue(source, destination)
MoveValue(source, destination)
ReplaceValue(destination, new_value)
DestroyValue(place)
```

A read-only parameter does not require an independent owning copy simply because
the C calling convention happens to pass a header by value.
A new local value binding does require the appropriate semantic copy.
An explicit sink transfers ownership according to the source mode.
Last-use copy elimination may select MoveValue only when source observability permits it.

Derive trivial-copy eligibility recursively from type structure.
Do not decide that a struct is safe to byte-copy because it is physically small.
A two-word object may contain an owning pointer.
For a list, copy live elements into independently owned storage and recursively
copy each element according to its type.
For arrays and structs, recursively handle owning fields and elements.
For options and error unions, operate only on the active initialized variant.
For types whose lifecycle is not implemented, reject their requested optimized use.

For EnforceScript, distinguish copying a container object from copying its elements.
A built-in array Copy operation alone is insufficient evidence for recursive
value semantics when the elements are generated reference classes.
Generate verified recursive helpers or reject that element shape initially.
Probe required engine behavior rather than assuming the engine's ref management
matches native ownership or makes user cleanup timing unobservable.

For replacement:

1. Evaluate the source with the selected evaluation order.
2. Construct a valid replacement before destroying the existing value when required.
3. Preserve the old value if recoverable construction failure is part of the contract.
4. Dispose the old live value exactly once according to the selected lifecycle policy.
5. Publish the replacement and transfer its cleanup responsibility.

Self-assignment and overlapping source/destination subobjects require explicit handling.
Do not free the source storage before completing a necessary copy.
Under abort-only allocation failure, the first subset may reject recoverable
construction entirely; it still must not double-own or use freed storage.

Before admitting owning copies, define lexical ownership cleanup and its ordering.
Current native allocation without generated disposal is not a lifecycle model to
reuse in a long-running mod or a retained incremental index.
Start with runtime-managed storage whose disposal has no user callbacks, then
specify observable destructors separately if the language later introduces them.
Keep compiler-generated destruction separate from immediate user defer.

Allocation growth must validate length, capacity, and byte multiplication before use.
Compute a candidate capacity without overflowing signed arithmetic.
Update a list's pointer and capacity only after successful allocation.
Preserve the required invariant 0 <= length <= capacity in every live state.

Only after these rules are correct should IMP-12 attempt destination construction,
copy elision, scratch reuse, or layout conversion.
Report copies removed, bytes transferred, retained memory, and cleanup costs.
An apparent speedup obtained by skipping required copying is a semantic failure.

Required evidence: VAL-019, VAL-020, VAL-072, VAL-156 through VAL-158.

### 45.6 Use one specified arithmetic contract and independent implementations

Write an operation specification indexed by operand type and semantic profile.
It must determine result bits, failure category, and valid input domain.
Constant evaluation, reference execution, native helpers, and script helpers must
each implement that contract for the subset they advertise.
Sharing a specification is desirable; sharing every implementation between the
oracle and candidate can conceal the same defect on both sides.

#### 45.6.1 Declared-width constants

Resolve literal context and operation types before checking constant results.
An i8 expression must not be accepted merely because its result fits int64_t.
An unsigned 64-bit constant must not be interpreted as a negative signed value.
Preserve width and signedness throughout constant evaluation.

For development tests, an arbitrary-precision mathematical integer evaluator can
provide an independent oracle, with explicit checks at every source operation.
For the compiler implementation, use checked, width-aware arithmetic or a bounded
integer representation sufficient for the supported operations.
Do not depend on overflowing a host signed integer and inspecting it afterward.
Keep the compile-time evaluation budget and separately bound type inference.
Use explicit in-progress states to detect inference and executed value cycles.
Validate division, remainder, negation, and literal magnitudes before host arithmetic.
Section 46.3 specifies the cycle and numeric boundary rules.

Evaluate constant && and || with true short-circuit behavior.
A skipped operand cannot introduce division-by-zero diagnostics or other failures.
Separate numeric casts from literal typing and preserve the chosen conversion rule.
Do not replace the existing meaning of as with checked conversion silently.

#### 45.6.2 Defined wrapping and shifts on native C

For narrow wrapping multiplication, operate in a sufficiently wide unsigned type
that does not undergo the dangerous narrow signed promotion.
Reduce modulo 2^N at the declared width, using defined unsigned arithmetic.
Handle N = 64 separately rather than shifting a 64-bit one by 64.
Convert the modular bit pattern back to a signed result with a defined mapping.
Do not rely on an out-of-range signed cast as a portable semantic definition.

For example, after obtaining an N-bit unsigned result u with mask M:

```text
if u <= signed_max_N:
    result = representable_signed_conversion(u)
else:
    result = -1 - representable_signed_conversion(M - u)
```

The complement distance M - u fits in the corresponding signed range on that branch.
The formula expresses the desired signed interpretation without overflowing it.
Implementation types and promotions still require code review and boundary tests.

Specify shifts separately from arithmetic multiplication.
A recommended bitwise profile shifts the unsigned N-bit representation, then
interprets the result at width N; it validates 0 <= count < N first.
Signed right shift must explicitly define sign filling if that is the selected rule.
Use a dedicated count-zero path when a sign-extension formula would otherwise
shift by the full width.
Do not use signed left shift on a negative value in generated C.
If Beryl instead chooses checked arithmetic left shift, implement that distinct
contract and identify it in the semantic profile; do not mix the two definitions.

#### 45.6.3 Guard arithmetic before evaluating it in EnforceScript

Initially support verified i32 operations without assuming a wider engine integer.
Let MIN and MAX be the representable i32 endpoints.
For checked addition a + b:

```text
if b > 0 and a > MAX - b: fail_overflow
if b < 0 and a < MIN - b: fail_overflow
otherwise: return a + b
```

For checked subtraction a - b:

```text
if b > 0 and a < MIN + b: fail_overflow
if b < 0 and a > MAX + b: fail_overflow
otherwise: return a - b
```

The branch conditions make the guard arithmetic representable.
Evaluate a and b once before using them in several comparisons.
Saturating addition/subtraction use the same guards but return the relevant endpoint.
They must not evaluate an overflowing sum inside Math.Clamp.

Checked multiplication can use sign-specific quotient bounds when division is
verified to truncate toward zero on the installed target:

| Signs | Overflow test, evaluated only in this case |
|---|---|
| a > 0, b > 0 | a > MAX / b |
| a > 0, b < 0 | b < MIN / a |
| a < 0, b > 0 | a < MIN / b |
| a < 0, b < 0 | a < MAX / b |
| Either operand is zero | Result is zero |

These guards avoid zero divisors and the MIN / -1 division case.
Evaluate the product only after the applicable guard establishes representability.
Test sign boundaries, MIN, MAX, zero, one, and negative one independently.
If the required target arithmetic behavior cannot be verified, reject the exact
operation or use a separately specified representation rather than guessing.

Division checks zero and signed MIN / -1 before executing the operation.
Remainder must implement the selected MIN % -1 rule without invoking an undefined
host expression; the current native helper returns zero for that case.
Bounds helpers must check both lower and upper limits before the indexed access.
Helper implementations themselves must satisfy the target failure policy.

#### 45.6.4 Distinguish failure detection from failure delivery

A correct overflow predicate does not establish a portable trap mechanism.
An Enfusion helper that logs a message and continues has not reproduced a native abort.
Record both how a failure is detected and what execution stops afterward.

Prefer one of these explicit profiles:

| Profile | Failure behavior | Admission rule |
|---|---|---|
| Native checked | Current aborting checked failure, with defined helpers | Native tests verify category and termination |
| Verified script exact subset | Same required observations within a supported computation boundary | Compile and behavior probes establish its failure contract |
| Total script subset | Failure excluded by proof over the accepted domain | Unknown or unproven cases are rejected |
| Explicit recoverable phase | Structured failure returned under an authored phase contract | Treat as a distinct contract, never silently as native abort |

The first engine comparison should prefer total bounded logic where possible.
Keep native-only checked-failure experiments useful without waiting for engine-wide
termination behavior that may not be available to a mod.
No branch of a fallback may silently change the selected failure profile.

Required evidence: VAL-005 through VAL-012 and VAL-167 through VAL-170.

Documentation validation on September 5, 2026 checked the proposed addition,
subtraction, and multiplication overflow predicates against exact integer results.
It covered every signed i8 operand pair and a 16-value i32 boundary set including
MIN, MAX, zero, sign changes, and multiplication boundaries: 197,376 comparisons
with no mismatches. This checks the mathematical formulas only; it does not verify
their C implementation, EnforceScript evaluation, or target failure delivery.

### 45.7 Version errors and cleanup without breaking ordinary programs

#### 45.7.1 Error identity

Keep legacy tag-erasing Enfusion output explicitly identified as such.
It is usable where only success versus failure is required by the selected contract.
Reject source that observes unavailable error identity before producing target code.
A catch binding that the handler actually reads is an important negative case.
Do not emit an undefined local for an error tag that was never supplied.

For a future exact tagged profile, prefer a primitive status code and out value:

```text
status = invoke(args, out value)
status == 0: value is initialized and readable
status != 0: status identifies the error; value is not read
```

This is a proposed ABI sketch, not a verified engine signature.
Probe actual supported parameter types, return types, and nested call behavior.
It avoids a new result-object allocation for every scalar error return.
An existing bool-plus-out call can remain behind a deliberate compatibility adapter
when the source contract does not require a distinguishable error identity.

Assign error tags from a collision-checked declaration table.
Do not use a truncated unchecked name hash as proof of distinct error identities.
Reserve zero for success and define capacity failure when the tag space is exhausted.
Use stable semantic error identities in traces and map them to artifact-local tags.
If numeric tags cross a saved-state, replication, or external ABI boundary, version
that mapping explicitly; local renumbering is not a compatible wire-schema change.

Specify initialization independently for tag and payload.
Success initializes its payload before returning success.
Error initializes the tag and does not expose uninitialized payload storage.
Returning an error union still counts as an ordinary return for separate set parameters.
Do not conflate those parameters with the conditionally present result payload.
Reject error literals in non-error return positions.
The recommended strict rule permits bare return for void and !void only.
Validate catch operands and all continuing result paths as specified in section 46.4.

#### 45.7.2 Immediate defer and future scope cleanup

Compatibility repair preserves immediate execution of user defer in v0.1.
Lower its expression with ordinary expression-statement rules on both targets.
Keep any emitted temporaries and final call inside the statement's control region.
Do not discard the rendered call text merely because expression rendering returned
a string instead of emitting a complete statement as a side effect.

A future lexical defer feature needs its own versioned semantic proposal covering:

- Registration versus execution time.
- Capture by value versus by place.
- LIFO ordering within a scope.
- Return, break, continue, and error-propagation exits.
- Interaction with partially initialized values and ownership destruction.
- Explicit behavior on aborting traps.

Until that proposal is implemented, optimizer cleanup regions track obligations
without changing the source meaning of defer.
Preserve abort-without-unwinding in the first native profile.
Do not use a benchmark configuration that omits observable required cleanup.

Required evidence: VAL-162, VAL-171, and lifecycle cases for each admitted type.

### 45.8 Make declaration, type, and generated-name identities unambiguous

Intern named types using declaration identity and their module-qualified origin.
Include actual type arguments when generic instantiation later exists.
Do not use a user-facing short name as the entire canonical key.
Within one compilation, a declaration ID can be dense and efficient.
For persistent caches, serialize a stable key containing qualified identity,
semantic signature, source dependencies, and relevant compiler/profile versions.
Never serialize a host pointer as a stable identity.

Separate these namespaces explicitly:

```text
ModuleId
DeclarationId
TypeId
LocalId within FunctionId
GeneratedIdentifier within TargetArtifactId
```

Two State declarations in different modules must have different TypeIds.
Resolve imports against explicit module scopes and enforce pub visibility.
Fix short-name lookup that selects whichever declaration was seen first.
Ambiguous names require a diagnostic with candidate locations.
Because flat lookup was an acknowledged v0.1 limitation, provide migration
diagnostics for code that relied on accidental cross-module visibility.
Preserve valid qualified references and do not silently bind them to another item.

Generate backend names from resolved identity, not by appending an underscore to
every keyword and hoping that the result is unused.
Maintain a target identifier allocator with a collision table.
Reserve helper, user-symbol, local, and temporary categories internally.
Keep readable stems for diagnostics while adding stable disambiguation.
Detect collisions even if a truncated digest is used for a compact suffix.

Bind an initializer before adding its new local to scope.
Render the already resolved LocalId afterward.
For an inner let x = x, the RHS must refer to the outer local's generated identity.
Do not emit a C initializer that accidentally reads the newly declared variable.

Type layouts and semantic facts must depend on the resolved type identity.
Record the semantic profile in specialization and cache keys.
Identity fixes must invalidate stale caches and context records.
Require cross-file and reversed-file-order tests, not only single-module fixtures.

Required evidence: VAL-163 through VAL-166 and stale-cache/context cases.

### 45.9 Make automated edits and validation preserve meaning

#### 45.9.1 Formatter correctness

Replace default-precision floating rendering with a round-trip representation.
For the current stored binary64 literal payload, 17 significant decimal digits is
a practical starting implementation; validate the actual parser/renderer pair.
Use a locale-independent decimal separator.
Preserve the numeric suffix and emit a decimal point or exponent when necessary
to keep an unsuffixed float a float after reparsing.
Handle nonfinite input-literal results through an explicit lexical policy instead
of emitting identifiers such as inf that the language does not recognize.
Preserve signed zero through the appropriate unary expression and literal structure.

Compare parsed trees by semantic structure, not only their debug text.
Comparison must include node kinds, operator nesting, literal values, numeric
suffixes, resolved meaning where applicable, and statement order.
Ignore source spans and formatting trivia for this semantic comparison.
The existing ast_print output can remain useful for debugging without being the oracle.

Escape char and string literals using the lexer's supported escape repertoire.
Test quote, backslash, newline, carriage return, tab, zero byte, and hex escapes.
Respect precedence for every expression category, including catch, orelse, casts,
unary expressions, and parenthesized struct literals inside conditions.
Preserve comments through token trivia or a concrete-syntax layer; do not promise
ordinary comment retention from an AST that never stored those comments.

Test both properties:

```text
semantic_parse(format(source)) == semantic_parse(source)
format(format(source)) == format(source)
```

Idempotence alone can accept a formatter that corrupts a value on its first pass.
Include high-precision literals and literal-category changes in the test corpus.
The authoring workflow must not automatically format unsupported source into a
different program after a partial parse; report the parse failure instead.

#### 45.9.2 Check and build results

Represent frontend failure independently of the diagnostic count.
A failed read must create an input diagnostic and return a failure result.
The final process status must account for both operation failure and error diagnostics.
Do not print ok or return zero just because an error bypassed the diagnostic bag.
Reject malformed manifest values and unknown target names explicitly.
Do not silently fall back to native when the user selected an invalid target.

Run target validation over resolved declarations, signatures, local declarations,
expression result types, casts, defaults, nested containers, and called intrinsics.
Separate source validity from target support, but require both for a successful
check operation that selected a target.
Use the same target-support predicates in check and emission to prevent drift.
Bindings and future contract annotations participate in that target validation.

The future structured result should contain at least:

```text
ValidationResult {
    status: succeeded | failed | unavailable | timed_out | cancelled
    stage: input | frontend | target_check | emission | native_compile | engine_compile | scenario
    source_fingerprint
    target_profile
    artifact_fingerprint_if_produced
    process_started
    exit_status_if_available
    diagnostics
    log_reference
    completion_evidence
}
```

Only a completed, successful selected stage receives succeeded.
Missing process status is unknown, not zero.
A failed compilation cannot promote an older output file as the current artifact.
Use a unique owned build directory and immutable completion manifest per job.
Separate a deterministic semantic fingerprint from a unique invocation identity.

#### 45.9.3 Executable tests and Workbench jobs

For a successful program test, require a successful launch, normal successful
termination, and matching validated output.
For a trap test, require the selected abnormal-termination or structured-failure
protocol and its expected category; matching a printed phrase alone is insufficient.
Preserve process status before piping output through normalization commands.
Record stdout and stderr separately when practical.
Do not classify arbitrary program text containing permission denied as a launch
failure and rerun a program that may already have performed side effects.
Treat actual execution restrictions as blocked execution evidence, not a reason
to report success or automatically perturb and retry binaries.

For Workbench, missing tooling produces unavailable.
A timeout produces timed_out even if an old success line exists in a log.
A compile result must match the project, source fingerprint, generated artifact,
binding version, and current job identity.
Compile evidence and scenario evidence remain different stages.
Use verified capabilities before invoking an operation or interpreting its result.

Own temporary project directories with a manifest and unique job identity.
Verify the resolved path is inside the intended owned root before cleanup.
Do not recursively delete a fixed shared proof-project directory on startup.
Concurrent jobs require isolated outputs or explicit serialization around the
shared Workbench session, with cancellation and ownership recorded.

Required evidence: VAL-109 through VAL-120 and VAL-172 through VAL-177.

### 45.10 Start AI-friendly queries with capabilities Beryl can actually implement

The first useful API should consist of concrete structs and concrete functions.
Use supported scalar fields, fixed arrays, or a verified List element shape.
Keep scoring and filtering as direct calls with resolved declaration identities.
Do not require closures, first-class function objects, or generic inference to
demonstrate a useful targeting component.

A reasonable first slice is:

1. A concrete observation record with stable identity and bounded score inputs.
2. A concrete pure scoring function over that record.
3. A concrete full-scan selection function with an explicit tie rule.
4. Native tests of that function under the selected arithmetic contract.
5. A thin generated adapter using verified engine bindings.
6. A later incremental implementation with the same selected behavior.

The compiler can first recognize an internal restricted loop pattern or an
explicit internal query operation during lowering.
If a library-shaped select_best_by API is later exposed, its function argument
can be restricted to a statically resolved function declaration.
Verify its exact signature, totality, read effects, and non-escaping arguments.
Reject runtime-selected callees, capturing closures, or unknown effects initially.
This is a new restricted intrinsic mechanism and must be implemented as such;
passing a function name into an ordinary current Beryl call does not create it.

Use generated context to expose a capability record for each feature:

```text
FeatureSupport {
    feature_id
    compiler_revision
    status: supported | restricted | unsupported
    target_profiles
    supported_forms
    restrictions
    validated_example_references
}
```

Parsing support, semantic support, native lowering, script lowering, and live
engine validation are distinct evidence fields.
Do not advertise a generic container or engine operation as fully supported
merely because its type name resolves.
Unsupported contract annotations must receive a clear diagnostic in the future
strict path; the diagnostic can suggest a concrete supported equivalent.
Keep all proposed commands and APIs in this blueprint out of current example
context until their implementation and validation exist.

This sequence reduces AI repair loops without adding model inference to compilation.
Normal authoring and runtime operation remain independent of model-service APIs.

Required evidence: VAL-139, VAL-140, VAL-143, VAL-144, and VAL-180.

### 45.11 Establish actual bounds, authority, and completing benchmarks

#### 45.11.1 Security evidence is typed and specific

Retain taint analysis as a useful lint, with its limitations visible.
Add a separate fact domain for proven numeric ranges and resource capabilities.
Do not implement it by renaming the existing trusted/untrusted bit.

For an index into a collection, require evidence of:

```text
index >= 0
index < length(collection, shape_version)
collection storage remains live
the shape version remains valid until the access
```

min(raw, 7) supplies at most an upper bound under an appropriate numeric contract.
It supplies no nonnegative lower bound.
clamp(raw, lo, hi) requires verified lo <= hi and bounds appropriate to the actual
collection length; an empty collection needs separate handling.
Arithmetic applied afterward may invalidate a previously useful range.
Returned values from a validator acquire only the postconditions its body or
reviewed external contract actually establishes.

Infer simple intervals through comparisons, branches, and arithmetic first.
Join conservatively, account for overflow/failure, and version shape-dependent facts.
Do not require a general theorem prover before retaining ordinary bounds checks.
When proof is unavailable, keep the check or reject a requested check-free plan.

An engine mutation also requires current runtime authority and live entity identity.
A server_only annotation can express a requirement but cannot manufacture the
actual engine capability at an entry point.
The adapter establishes and revalidates that capability using verified bindings.
Reentrancy, entity replacement, ownership changes, and world reloads invalidate it
according to the verified engine contract.

A constant_time annotation is similarly a requirement, not proof of machine timing.
Do not introduce secret-dependent plan dispatch or profile-guided shortcuts under it.
Keep such code outside experimental scheduling until a separately validated
target-specific constant-time methodology exists.

#### 45.11.2 Replace invalid performance inputs and enforce the full contract

The checked LCG in the current benchmark uses an overflowing first multiplication.
It cannot measure completion time for the intended 80 million checked iterations.
Retain it as a negative harness case, not a performance baseline.

Use separate benchmark families:

| Family | Beryl workload | Comparable baseline |
|---|---|---|
| Modular arithmetic | Explicit wrapping LCG with observed final state | Rust and C with equivalent modular arithmetic |
| Checked arithmetic | Runtime-supplied bounded arrays with representable source intermediates | Equivalent checked operations and failure contract |
| Checked failure | Inputs that fail at identified operation positions | Failure category, prefix effects, and detection cost reported separately |
| Collection processing | Same logical values, copy rules, and full lifecycle | Equivalent allocation, copying, indexing, and cleanup costs |
| Engine integration | Verified scenario including capture, script work, and apply | Equivalent handwritten EnforceScript in the same scenario |

For the first checked array workload, choose bounded values and coefficients that
keep each per-element multiply/add in range across ordinary samples.
Use separate boundary inputs to test failure preservation.
Consume a verified output checksum without introducing a different overflow policy
into one baseline's timed work.
Ensure runtime inputs and output observation prevent timing dead or folded work.

Before accepting a sample, verify:

- The requested artifact was compiled from the intended source and settings.
- The intended workload actually ran to its declared completion point.
- Its output or checksum matches the independent expected result.
- Its termination mode matches the benchmark family.
- Its measured region includes all costs charged to its comparator.
- No timeout, stale executable, or process-launch failure was converted to a duration.

A failure invalidates the candidate run; do not silently discard bad samples and
publish a mean over surviving successes as if the workload were reliable.
Retain raw failure evidence and repair the cause before making the comparison.
Use the paired-sample and held-out-workload methodology in section 35.
Best-of-three timing alone is not adequate evidence for a new optimization model.

Compiler-throughput experiments must request a stage their generated input supports.
If generated source has no main, measure check or another implemented non-linking
stage; add a real entry point before timing a complete executable build.
Never time a failed link as a successful compilation-throughput result.

Required evidence: VAL-133 through VAL-138, VAL-175, VAL-176, VAL-178, VAL-179.

### 45.12 Gate each experiment on the facts it actually needs

These gates define evidence requirements, not a new runtime subsystem.
Each evidence record is scoped to a source subset, semantic profile, target,
compiler revision, and implementation fingerprint.
Passing a scalar gate does not certify arbitrary containers or engine calls.

| Gate | Required evidence | First consumers |
|---|---|---|
| G-COMPAT | Set, copy, defer, and error-profile decisions recorded | All feature implementation |
| G-IDENTITY | Distinct declarations and bindings remain distinct through emission | Structured IR, specialization, caches, bindings |
| G-FLOW | Explicit and implicit exits, expanded defaults, initialization, and move obligations hold | Reference lowering, guards, storage reuse |
| G-ORDER | Source effects, defaults, destinations, and failures preserve the unified event order | Checked block execution, fusion, replay |
| G-ACCESS | Actual overlap and intrinsic effects are covered for the selected places | Alias promises, views, vectorization, incremental facts |
| G-ARITH | Reference, constants, and admitted target operations agree | Checked kernels, bounds, compact representations |
| G-VALUE | Recursive copies, replacement, and cleanup preserve logical values | Owning layouts, scratch, retained indexes |
| G-RESOURCE | Resource domain, peak storage, and recoverable/aborting failures match the selected profile | Exactness claims, allocation changes, retained indexes, transitions |
| G-TOOLS | Checks and jobs propagate failures and identify exact artifacts | Automated edits, all benchmarks, Workbench validation |
| G-FORMAT | Formatting preserves source meaning and literal categories | Automatic formatting and generated AI examples |
| G-ENGINE | Required bindings and runtime behaviors are actually verified | Engine adapters and cross-target scenario claims |
| G-SECURITY | Typed bounds and current authority support each removed check or mutation | Network-facing optimized logic |
| G-MEASURE | Work completes correctly and comparator contracts match | Any published performance result |

The first native checked-block experiment needs G-COMPAT, G-IDENTITY, G-FLOW,
G-ORDER, G-ACCESS, G-ARITH, G-TOOLS, and G-MEASURE for fixed supported arrays.
It also needs G-RESOURCE's bounded admission statement for that array workspace;
this does not require implementing a new allocator.
It need not wait for engine authority or arbitrary owning-container cleanup if
those constructs are excluded and the exclusion is enforced by the compiler.

An owning-list layout experiment additionally needs G-VALUE for its element shapes.
An incremental engine query additionally needs verified capture/invalidation,
G-ENGINE, and G-SECURITY where client data or authority affects the result.
An AI authoring demonstration needs G-TOOLS, G-FORMAT, accurate capability context,
and G-ENGINE for any claim that the generated component works in Workbench.

For each gate, store a compact evidence record:

```text
GateEvidence {
    gate_id
    supported_source_subset
    semantic_profile
    target_profile
    compiler_and_dependency_fingerprints
    acceptance_cases_run
    failures_or_unavailable_capabilities
    evidence_artifact_references
}
```

A code, ABI, intrinsic contract, binding, or profile change invalidates dependent
evidence until the relevant checks are rerun.
Do not rerun unrelated experiments just to create activity.
Do not reuse evidence from a stale backend or a different engine profile.

Recommended bounded delivery sequence:

1. Refresh IMP-00 and preserve the current ownership fixes.
2. Complete IMP-00A for the chosen source subset and record compatibility decisions.
3. Complete IMP-00B's reliable local validation and formatter corrections.
4. Establish the independent bounded reference in IMP-01.
5. Repair and verify the corresponding existing path in IMP-00C.
6. Implement Structured IR and verified analyses through IMP-02 and IMP-03.
7. Establish reference lowering and the trustworthy harness in IMP-04 and IMP-05.
8. Run one native optimization experiment with its actual gate set satisfied.
9. Progress binding, context, and Workbench tickets on their independent dependency path.
10. Admit richer storage and engine scenarios only when their additional gates pass.

The foundation tasks have concrete exit criteria and should remain bounded.
The goal is to spend less time debugging invalid optimization assumptions, then
measure ambitious mechanisms against correct, competitive implementations.
No step in this section changes the requirement to demonstrate actual performance.

## 46. Repairs from the second comprehensive review

**Integrated:** September 6, 2026.
**Scope:** document repairs and future implementation requirements only.
**Evidence:** source tracing and small mathematical checks from the preceding review.
No failing compiler reproduction, code repair, Rust measurement, or Workbench
execution is claimed by this section.

The review found nine additional implementation defects, two insufficient design
contracts, and one command-protocol clarification.
The original sections now incorporate the corrected contracts.
This section supplies the implementation detail and counterexamples needed to
avoid replacing one defect with a narrower version of the same defect.

These requirements supplement section 45.
They do not change the current specification or authorize implementation by themselves.
Where a recommended rule tightens accidentally accepted source, record the
compatibility decision and diagnostic before enabling the strict path.
An unsupported construct may be rejected within a bounded prototype; that is
not evidence that the construct has been implemented across the language.

### 46.1 Evidence ledger and repair ownership

Source references name stable files and functions rather than relying on old line numbers.
Refresh each finding using the actual compiler revision before implementation.
Retain existing uncommitted ownership work and verify which cases it already fixes.

| ID | Finding | Evidence location | Repair ownership |
|---|---|---|---|
| R11 | try's implicit return bypasses set obligations | [ownership.c](../src/sema/ownership.c), EX_TRY; [c_backend.c](../src/back/c_backend.c), EX_TRY | IMP-01, IMP-00C, IMP-03 |
| R12 | Untyped constant inference recurses before evaluator limits apply | [check_expr.c](../src/sema/check_expr.c), chk_path; [resolve.c](../src/sema/resolve.c), IT_CONST | IMP-00C |
| R13 | Constant division, remainder, and negation use unsafe host operations | [constfold.c](../src/sema/constfold.c), ev_binary and ev | IMP-01, IMP-00C |
| R14 | Error literals bypass return compatibility; bare !T returns omit payload assignment | [check.c](../src/sema/check.c), ST_RETURN; both return emitters | IMP-00A, IMP-00C, IMP-04 |
| R15 | A default's cached expression text can reference another occurrence's temporaries | [c_backend.c](../src/back/c_backend.c), gen_call and gen_expr | IMP-00C, IMP-02 |
| R16 | Omitted defaults are absent from parts of security/access traversal | [check.c](../src/sema/check.c), check_fn; [taint.c](../src/sema/taint.c), check_fn and call traversal | IMP-00C, IMP-03 |
| R17 | Omitted defaults shift synthetic Enfusion output arguments into source slots | [enforce_backend.c](../src/back/enforce_backend.c), emit_signature; [enforce_expr.c](../src/back/enforce_expr.c), call_args | IMP-00C, IMP-04 |
| R18 | catch accepts a non-error operand that lowering treats as an error union | [check_expr.c](../src/sema/check_expr.c), EX_CATCH; both catch emitters | IMP-00C, IMP-04 |
| R19 | Integer literal type selection lacks a representability check | [check_expr.c](../src/sema/check_expr.c), chk_int_lit | IMP-01, IMP-00C |
| R20 | Separate event-kind lists omit cross-kind order | Section 06's former Outcome schema | IMP-01, IMP-17 |
| R21 | Recovery and exactness claims omit necessary allocation assumptions | Sections 08.4 and 20.3; [beryl_rt.c](../runtime/beryl_rt.c), beryl_grow | IMP-01, IMP-03, IMP-12, IMP-15 |
| R22 | Completed prefix alone does not define the failing command's effects | Section 26.4, read with sections 31 and 32 | IMP-07, IMP-17 |

R11–R19 are source-traced implementation findings.
R20 and R21 identify design requirements that were insufficiently specified.
R22 is a protocol gap, not a demonstrated bug in an implemented batch executor.
Do not convert these classifications into claims that all hypothetical triggers
were compiled, crashed, or were exercised against the engine.

Use ReviewEvidence from section 45.1 for each reproduction.
Add the relevant VAL identifiers and the exact supported semantic/resource profiles.
An existing passing unit suite does not close a case it does not exercise.

### 46.2 Make every error-propagation edge visible to ownership

The recommended set rule remains unchanged:
every ordinary return, including an error-union return, initializes every set output.
A runtime trap that aborts execution is a different edge.

Minimal source-shaped negative case, not an executed reproduction:

```text
fn fail() -> !i32 {
    return error.Bad
}

fn fill(set output: i32) -> !i32 {
    let value = try fail()
    output = value
    return value
}
```

The assignment after try is not evidence for the error edge.
A caller may recover with orelse and continue, so the error edge cannot be
treated as a process abort or as unreachable caller code.

Normalize try before output obligations are finalized:

```text
result = evaluate_once(inner)
if result.is_error:
    check_required_set_outputs_at_this_edge()
    perform_required_return_cleanup()
    return_error(result.tag, origin = try_source_site)
else:
    yield initialized_success_payload(result)
```

The check above is a compile-time obligation, not a new runtime branch.
The cleanup operation follows the selected lifecycle profile; it must not turn
immediate v0.1 defer into scope-exit defer.
Keep aborting traps distinct from ordinary error returns.

For the legacy repair, introduce a shared output-obligation checker used by
explicit returns, fallthrough, and implicit try propagation.
For Structured IR, attach that obligation to every ordinary return terminator.
Avoid two unrelated implementations of the same rule.

Diagnostics should point to the propagating try expression and the unassigned
set parameter declarations, rather than blaming the later explicit return.
Check every output, including nested try expressions inside ordinary arguments.
Default expressions containing nonlocal propagation are rejected by the initial
default subset in section 46.5, so they cannot acquire accidental caller exits.

A positive case assigns all outputs before the possibly failing operation.
Their values remain initialized if that operation returns an error.
Do not weaken the source contract to promise assignment only on success.
The error union's own payload is conditionally present; separate set outputs are not.

Acceptance: VAL-181 through VAL-183, plus explicit-return and fallthrough cases.

### 46.3 Bound constant inference and evaluate declared-width numbers safely

#### 46.3.1 Separate type-inference state from evaluation state

The existing evaluation step budget cannot stop recursion that occurs before
evaluation is entered. Maintain two distinct state machines per constant identity:

```text
type_state: Unresolved | Resolving | Resolved(TypeId) | Failed
value_state: Unevaluated | Evaluating | Evaluated(TypedConstant) | Failed
```

Requesting an unresolved type marks it Resolving before checking the initializer.
Requesting that same unresolved type again emits a cycle diagnostic with its
dependency stack. Failed requests return an error type and suppress cascades.
Resolve constants by declaration identity, not by a short-name global lookup.

An explicit type can be resolved before the initializer value is evaluated.
That does not make a value cycle legal:
const A: i32 = A has a known type but recursively demands its own value.
Mark value evaluation in progress before descending into evaluated dependencies.

Cycle detection follows actual value demands.
A typed boolean initializer false && A does not evaluate A on the skipped edge.
Do not reject it merely because a syntactic dependency graph contains a cycle.
Type checking still validates the skipped expression's type.
Untyped recursive inference remains an error when no type can be established.

Bound dependency depth, visited work, and expression nesting independently.
The parser and recursive checking paths need their own nesting limits; a value
evaluator's budget cannot protect an earlier parser stack.
Use an explicit work stack where appropriate, or enforce a conservative depth
limit before the host call stack is endangered.
Report exhaustion as incomplete/failed compilation, never as a default constant.
Memoize completed typed values within the correct revision and semantic profile.

#### 46.3.2 Resolve literal magnitude before materializing a machine value

Keep the lexer's unsigned magnitude separate from the resolved integer type.
For a positive integer literal, validate it against the selected signed maximum
or unsigned maximum before emitting code or accepting a folded value.
Apply this rule to local initializers, arguments, returns, defaults, and array elements.
It must not exist only for top-level const declarations.

Treat a directly negated integer literal as a sign-and-magnitude case.
The mathematical magnitude of a signed minimum is one greater than its positive
maximum, so -128 at i8 must remain expressible.
Its magnitude 128 must not become an independently evaluated positive i8 value.
An additional negation is an ordinary checked operation and can overflow.
Do not compute the minimum by first overflowing a host signed temporary.

Examples of required outcomes:

| Source situation | Recommended outcome |
|---|---|
| Positive 255 in u8 context | Accept |
| Positive 256 in u8 context | Reject |
| Positive 127 in i8 context | Accept |
| Directly negated magnitude 128 in i8 context | Accept as -128 |
| Positive 128 or negative magnitude 129 in i8 context | Reject |
| Maximum u64 magnitude | Preserve as unsigned |
| Magnitude exceeding the lexer-supported integer domain | Lexical/range diagnostic |

Suffixes participate in type resolution and must not be silently overwritten.
Negative operations on unsigned values follow the selected arithmetic policy;
they are not permission to reinterpret a negative literal as modular arithmetic.
Integer-shaped literals acquiring a floating context retain the existing floating
literal policy. Do not apply an integer-destination rule to that separate case.
Explicit numeric casts remain distinct from implicit literal assignment.

#### 46.3.3 Avoid undefined operations inside the compiler

Represent a constant as a typed value with explicit width and signedness.
Use checked machine operations or a bounded bit-vector implementation in production.
Use an independently implemented mathematical evaluator for validation.
Do not store every u64 value in a signed int64_t and treat the result as its meaning.

Required integer cases:

| Operation | Check before evaluating |
|---|---|
| Checked addition/subtraction/multiplication | Result fits the declared source type |
| Signed division | Nonzero divisor and absence of MIN / -1 |
| Signed remainder | Nonzero divisor; handle MIN % -1 as zero under the selected native profile |
| Checked negation | Operand is not signed MIN; unsigned behavior follows its own profile |
| Shift | Count and operand rules of the selected shift profile |
| Narrow wrapping operation | Declared modular result without dangerous host promotions |

The existing ordinary runtime handles several of these endpoints.
The constant evaluator must implement equivalent outcomes without executing an
unsafe host expression first.
A helper that catches the host fault afterward is not an acceptable evaluator.

For admitted float-to-integer casts, specify nonfinite and out-of-range behavior
before implementation. Use a checked conversion procedure whose bounds and
rounding are valid for the actual source/target widths.
If that conversion profile is unsettled, reject those cases in the strict subset.
Do not silently redefine all existing as conversions as checked conversions.

Run && and || with actual short-circuit evaluation.
Do not generate division diagnostics or value-cycle diagnostics from skipped work.
Source type errors and executed constant-evaluation failures remain distinct.

Acceptance: VAL-184 through VAL-194 and VAL-199 through VAL-204.

### 46.4 Check return forms and initialize every continuing result

Use one return-classification operation before choosing a backend representation.
The recommended strict rules are:

| Declared return type | Source return | Result |
|---|---|---|
| void | bare return | Valid |
| !void | bare return | Valid success without a payload |
| T, where T is non-void | bare return | Reject |
| !T, where T is non-void | bare return | Reject missing success payload |
| !T | error.Name | Valid error return with no readable success payload |
| T or void | error.Name | Reject incompatible error return |
| T | ordinary expression | Require ordinary type compatibility |
| !T | ordinary success expression | Require the selected success-payload type |

Admitting direct forwarding of a whole !T value is a separate source-form
decision; do not invent implicit conversions while repairing the existing forms.
An error literal must never escape checking because its AST kind is special.
Neither an ordinary integer hash nor a boolean false is a substitute for the
required source-level error-union type.

The bare-return tightening removes inconsistent accidental behavior:
zero-filled native aggregate output and an unwritten engine output are not a
portable success-value contract.
Record the change and provide a diagnostic requesting an explicit success value.
Do not repair the engine side by silently supplying zero for every missing payload.

For a success return, construct/assign the payload before reporting success.
For an error return, initialize the tag/status and prevent reads of the inactive
payload. Check independent set obligations on both return categories.
For !void, emit no payload slot and no void-typed temporary.

Before lowering catch, require an error-union operand.
Evaluate that operand once, branch on its status, and declare any supported
error binding only with an actual value available in that target profile.
A scalar operand receives a diagnostic before target emission.

Specify catch's continuing error-path result separately from its handler effects.
The existing native path uses a zero/default result when a handler continues.
Do not silently change that into a handler-yields-value language feature.
Preserve that policy only for payload types with a defined supported default.
For other payload shapes, reject the continuing form in the initial exact subset
or require an already supported explicit fallback/noncontinuing handler.
Never treat arbitrary zero bytes as a valid owning object.

If the handler returns from the enclosing function, that path contributes no
continuing catch result, but must satisfy the enclosing return/output obligations.
For !void catch, preserve effects and control flow without allocating result storage.
For Enfusion, reject catch forms requiring error identities unavailable in the
selected legacy profile; a proposed tagged profile still requires target probes.

Acceptance: VAL-195 through VAL-198 and VAL-219 through VAL-221.

### 46.5 Instantiate defaults as real evaluations

#### 46.5.1 Define scope, order, and the initial supported subset

A parameter default belongs to a declaration but each omission is a distinct
evaluation occurrence. Treat it as compiler-generated source at the call site,
with its declaration scope preserved.

For the proposed deterministic-order profile:

1. Evaluate the receiver and explicitly supplied arguments in source order.
2. Bind those evaluated values/places to formal identities.
3. Instantiate omitted trailing defaults in formal-parameter order.
4. Evaluate each instantiated default once and bind its value.
5. Invoke the callee with the complete logical argument list.

An explicitly supplied argument suppresses evaluation of its default.
A skipped call suppresses every argument/default evaluation belonging to that call.
No default evaluation may escape its controlling branch.
Exclusive places selected for earlier arguments must remain valid throughout
later default evaluation; reject conflicting mutation or shape invalidation.

Resolve default names in declaration scope.
Earlier permitted formal parameters bind to their evaluated argument values,
not to caller variables that happen to have the same spelling.
Do not textually substitute the original effectful argument expression.
Reject self/later formal dependencies that require an unavailable value.
Unrelated declarations with the same name remain governed by normal scope resolution.

Begin with closed expressions and, when implemented and verified, dependencies
on earlier read-only scalar formals.
Reject unsupported dependencies on set/inout/sink places or owning lifetimes.
Do not claim support for all defaults because closed scalar defaults work.

The initial default subset excludes try and other nonlocal control transfers.
A declaration-context return type must not decide which caller a default returns
from. Supporting such transfers would need a separate source-language contract.
Locally handled values may be admitted only through supported expressions whose
effects and control flow are fully analyzed.

Field defaults follow their own specification.
The current specification describes compile-time field defaults.
Enforce that rule using the permitted constant subset; do not use the parameter
default repair as permission to execute arbitrary field-default calls at runtime.

#### 46.5.2 Separate syntax identity from evaluation occurrence

Proposed internal record:

```text
DefaultOccurrence {
    declaration_expression_id
    call_occurrence_id
    destination_region_id
    formal_to_evaluated_argument_bindings
    resolved_type
    source_origin_chain
}
```

Lower each occurrence into fresh value and temporary identities.
Preserve both the default declaration and omission site for diagnostics.
Memoizing a constant value is acceptable when its dependencies/profile match.
Memoizing emitted text that references temporaries across occurrences is not.

Resetting the memo once per function is insufficient.
The first occurrence can be inside a branch that does not execute, while a later
occurrence needs its own initialized temporary.
Any subsequent common-subexpression elimination needs the normal dominance,
purity, dependency, failure, and lifetime evidence.

Remove the need for effectful generators inside formatting macros that evaluate
their argument twice. Materialize each generated Str once before formatting,
or use a formatting interface with single-evaluation arguments.
Do not use a program-global expression cache as compensation for macro evaluation.

#### 46.5.3 Include implicit evaluations in every applicable analysis

The expanded logical call must be visible to:

- Type and target-support checking.
- Definite initialization and move analysis.
- Borrow/exclusivity and shape invalidation analysis.
- Security taint and caller-context restrictions.
- Effect, allocation, and failure summaries.
- Source provenance and execution-order validation.

At declaration time, summarize or conservatively classify a default's effects.
At each omission, apply them in the actual evaluation context.
Passing security checks on the callee body does not validate work executed before
entering that body.

For example, an omitted argument that calls server_only code from client context
must be diagnosed as if the evaluation had been written explicitly.
A secret default must participate in the argument/result taint relationship.
A constant_time caller must account for calls introduced by its omitted defaults.
Unknown effects remain unknown; do not clear taint because an argument was implicit.

The legacy implementation may create an expanded-call side structure before
analysis, then reuse that representation in the new IR pipeline.
Do not fix each pass with a different ad hoc default traversal.

Acceptance: VAL-205 through VAL-215.

### 46.6 Share one complete target argument layout

Both signature emission and call emission must consume the same ABI descriptor:

```text
CallLayout {
    callee_identity
    target_profile
    abi_version
    receiver_representation
    ordered_slots: [
        { source_formal_id_or_synthetic_role, type, access_mode, position }
    ]
    return_representation
}
```

Every source formal is bound by an explicit argument or an expanded default
before target slots are populated.
Only then append the synthetic success-value output for an admitted !T profile.
For !void there is no success-value output slot.
Apply the same rule to methods after accounting for the target's implicit receiver.

Illustrative intended lowering:

```text
Beryl declaration: f(let count: i32 = 7) -> !i32
Beryl call:        f() orelse 0

Internal arguments: [count = 7]
Legacy script ABI:  F(int count, out int result) -> bool
Emitted call:       F(7, result_storage)
```

F(result_storage) has the wrong positional meaning.
It is not an acceptable spelling of the omitted-default call.

For generated internal calls, prefer explicit expansion of all defaults and
required parameters in target signatures.
This avoids depending on target rules for optional parameters before a required
synthetic output, or for nonliteral expressions in default declarations.
Do not emit default-related temporary statements into declaration scope.

Public engine-facing wrappers are a separate ABI boundary.
If external callers depend on target defaults, preserve them through a verified
compatibility wrapper or a deliberate ABI migration.
Do not remove an advertised public call form merely to simplify internal lowering.

Validate slot count, type, convention, and output role before rendering text.
Inspect generated calls and compile them in the selected engine version.
Native success does not verify this script calling convention.

Acceptance: VAL-216 through VAL-218, together with the default evaluation cases.

### 46.7 Preserve one observable order across event kinds

The repaired Outcome in section 06 has one ordered event stream.
This is a semantic/test representation, not a requirement to allocate a trace
object during ordinary optimized execution.

Counterexample to separate per-kind lists:

```text
Trace A: publish x = 1; call observer()
Trace B: call observer(); publish x = 1

Per-kind write list in both:   [publish x = 1]
Per-kind command list in both: [call observer()]
Observer reads:               1 in A, 0 in B, starting from x = 0
```

An in-memory model in the preceding review confirmed this information loss.
It was not a Beryl or engine execution.

Define one observation domain for the supported sequential execution, including
nested callbacks and reentrant invocations.
An external-call begin event precedes its nested events; its end event follows them.
Use invocation relationships to preserve nesting without resetting away global order.
Record actual return/failure information when it is part of the boundary contract.
Enqueuing a command, starting its application, and observing completion are
different events and must not share an ambiguous completed-command label.

Compare event kind, semantic identity, relevant typed payload, and relative order.
Preserve the source failure operation and its position after the visible prefix.
Keep generated helper locations and transformation histories as diagnostic metadata;
different valid schedules need not have identical generated-source locations.
Elapsed time and instrumentation overhead are measurements, not exact trace fields.

Only contractually observable writes and cleanup actions belong in the stream.
Do not require equality of private scratch writes, internal addresses, or eliminated
unobservable copies.
For staged phases, record publication according to their explicit commit contract.
For logging, define logical call order separately from operating-system buffering
or the presentation order of merged stdout and stderr.

A complete sequential trace may use a monotonic ordinal for ordering.
Bound trace storage and report truncation before counters wrap or data is dropped.
Truncated or unavailable traces cannot establish complete equivalence.
Representing Diverged is a semantic possibility, not permission to infer divergence
from a test timeout.

Do not extend this total-order rule to arbitrary parallel schedules without defining
which synchronization and ordering relations are observable.
Parallel validation remains the separate research track in section 23.

Acceptance: VAL-222 through VAL-224 and the existing failure-prefix cases.

### 46.8 State the resource domain and make transition recovery implementable

#### 46.8.1 Choose an explicit exactness profile

No allocation strategy is exact merely because its computations are pure.
Extra allocation may make a previously returning program abort.
Eliding allocation may make a previously aborting program return.
Absence of unwinding does not erase that termination difference.

Use one of these explicit research profiles:

| Profile | Obligation |
|---|---|
| resource_adequate_exact | Exact semantic equality over a declared domain with sufficient resources for the admitted execution and its complete region lifetime |
| resource_observable_exact | Preserve the selected allocation/failure observations, including resource-exhaustion outcomes, over the stated supported states |

The first bounded kernel should use resource_adequate_exact with fixed admitted
workspace and no optional heap allocation inside the kernel.
Record workspace limits and the environment assumptions supporting them.
This is a restricted correctness claim, not an assertion that memory cannot run out.
Include the resource profile in plan eligibility, semantic contracts, cache keys,
replay identities, and benchmark manifests.

For resource_observable_exact, disable allocation-changing transformations until
their resource behavior is proven for the selected domain.
A benchmark win on resource-adequate inputs does not establish this stronger claim.
Preserve the existing public abort-on-allocation-failure behavior on legacy paths.
Introducing a user-visible recoverable allocation result requires a separate
language/runtime decision.

#### 46.8.2 Use a separate fallible operation for optional private storage

A proposed internal try_reserve may return Available or Unavailable.
It must not call beryl_grow and pretend its abort can be caught.
Required properties include:

- Checked size, alignment, capacity, and byte-count arithmetic.
- No modification of the old representation on failure.
- No user callbacks or externally visible publication during private reservation.
- Explicit ownership of successful reservations and partially initialized values.
- A bounded capacity and a documented release policy.

This is an internal design proposal, not an existing runtime API.
Actual support must be implemented and tested before selecting an adaptive plan.
Failure-injection tests should exercise the real fallible path.

Build a new representation privately.
Keep old values, identity maps, pending events, and cleanup ownership valid.
On a recoverable failure, destroy only initialized new values, release their
private storage, and continue with the valid reference representation.
On success, publish the new representation at the specified boundary, then retire
old storage according to live-view and cleanup rules.
Never relabel an invariant violation as an ordinary allocation miss.

#### 46.8.3 Prove more than the initial reservation

Catching allocation failure is necessary for recovery, but not sufficient for
exactness: a successfully retained index can consume memory that a later required
source allocation needs.
The resource argument must cover that later allocation or explicitly restrict
the execution domain so that it remains supported.

Account for:

- Original live values.
- Retained indexes and caches.
- Old and new representations during transition.
- Partially constructed owning elements.
- Scratch and nested/reentrant invocation capacity.
- Required future allocations inside the covered lifetime.
- Allocator overhead/alignment, with fragmentation assumptions stated where relevant.

Prefer a bounded workspace reservation or separate quota for optional plans.
If the implementation cannot bound the covered lifetime's demand, it must not
claim resource-observable equivalence.
It may restrict the optimization to a resource-adequate domain, or disable it.
Releasing an index later is not proof that it never changed an earlier allocation outcome.
Allocator callbacks or observable allocation instrumentation need their own policy.

Do not exclude setup, reservation, transition, or cleanup costs from a comparison
when the application or comparator pays them.
An input outside resource admission is not a successful zero-time sample.

Acceptance: VAL-225 through VAL-228 and the selected growth/cleanup cases.

### 46.9 Track partial and unknown engine effects explicitly

The ApplyResult in section 26 distinguishes execution lifecycle from effect evidence.
Use its per-command ledger as the source of truth.

| Effect status | Meaning | Default continuation |
|---|---|---|
| NotStarted | This executor has not issued the command | May issue only after current preconditions are validated |
| RejectedBeforeEffect | Verified rejection before this command produced effects | Stop the batch; retry requires a suitable changed/validated request |
| Applied | Required operation completion is confirmed under the binding contract | May proceed after revalidating the next command |
| PartialEffectsKnown | Some effects are confirmed but full application did not complete | Stop; preserve the known effects and remaining uncertainty |
| UnknownOutcome | Available evidence cannot establish the command's complete effect state | Stop; reconcile before any unsafe continuation or replay |

operation_finished records whether the underlying operation is still capable of
producing additional effects.
Known partial effects do not imply that an asynchronous operation has stopped.
An acknowledgement of receipt or successful enqueue is not Applied unless the
operation's explicitly selected contract ends at that acknowledgement.

committed_prefix_length is the number of consecutive leading commands recorded
as Applied. It does not describe the currently failing command's effects.
After three applied commands and a partially applied fourth, the prefix is three
and the fourth has its own partial record.
Do not describe the state as if only commands one through three ever affected it.
Validate that ledger IDs and order match the requested batch, and derive the
prefix from that ledger rather than trusting a separately supplied count.
Applied requires completion evidence for the selected operation contract.
A successful batch requires every requested command to be Applied; an independent
job timeout or cancellation remains visible even when effects are later confirmed.

The prefix is also historical evidence.
Later commands, callbacks, or unrelated engine activity may change earlier results.
It is not a substitute for a current authoritative state read.
Keep desired state, confirmed observations, and uncertain effects separately.
Include the observation context/version supporting each confirmation.

A timeout may coexist with an applied or unknown effect outcome.
A canceled job may later yield evidence that its operation completed.
Report both facts; do not turn cancellation into rollback or conceal the effect.
The job status vocabulary in sections 31 and 32 continues to describe the job lifecycle.

After an unknown outcome:

1. Stop issuing dependent commands.
2. Query an existing durable operation identity if the receiver actually supports it.
3. Otherwise use verified reconciliation reads appropriate to that operation.
4. Preserve unknown status when those observations cannot prove what happened.
5. Retry only under a verified idempotency/deduplication contract or proof that
   repetition is safe in the actual state.

Reading a current property does not necessarily prove that a non-idempotent
operation, such as adding a quantity, ran exactly once.
A caller-generated request ID has no deduplication effect without receiver support.
If a receiver offers durable deduplication, verify its relationship to effect
application; recording an ID before or after an unprotected effect is not itself
an exactly-once guarantee.

Begin with verified synchronous commands whose completion/effect behavior is
understood. Unsupported bindings must retain conservative unknown behavior or
be excluded from the first adapter.
Do not invent engine rollback, transaction, polling, or idempotency APIs.
Older result schemas lacking per-command evidence must not silently be upgraded
to a complete no-partial-effects result.

Acceptance: VAL-229 through VAL-232 and VAL-109 through VAL-132 as applicable.

### 46.10 Close findings through evidence, then enable the dependent experiments

Use the existing tickets rather than starting an unbounded compiler rewrite.

| Stage | Concrete completion evidence |
|---|---|
| IMP-00 | R01–R22 classified against the current working tree, with supported subset recorded |
| IMP-00A | Return/default compatibility, identities, target ABI, and resource profile selected |
| IMP-00B | Missing inputs, malformed manifests, target failures, failed runs, and unavailable engine jobs cannot report success |
| IMP-01 | Independent numeric/flow reference and complete unified observation traces |
| IMP-00C | Selected compiler paths pass the new negative and positive regressions |
| IMP-02/IMP-03 | Default occurrences, implicit exits, effects, and resource obligations survive normalization and analysis |
| IMP-04 | Native and admitted script call layouts, results, and failure behavior match their contracts |
| IMP-05 | Completing workloads and matched comparators produce valid raw measurements |
| IMP-12/IMP-15 | Resource admission and transition failure injection justify allocation-changing plans |
| IMP-17 | Actual engine evidence includes nested event ordering and partial/unknown outcomes |

The second review does not supersede unresolved older blockers.
Keep the following acceptance work in the foundation:

- Recursive value-copy independence and collection mutation access.
- Short-circuit and loop-exit initialization.
- Complete target checking and nonzero failure exits.
- Literal-preserving formatting and character escaping.
- Strict manifest booleans; supported inline comments must not silently disable forbid_unsafe.
- Exit-status-aware executable tests and trap tests.
- Completing benchmarks with independently verified results.

For the existing checked LCG, the mathematical first product is
13,622,895,699,525, exceeding the i32 maximum of 2,147,483,647.
This arithmetic was checked in memory during the review.
It establishes that the stated checked loop cannot complete as intended under
the selected arithmetic contract; it is not a measured runtime or Rust comparison.
Keep it as a negative harness test and use the completing workloads in section 45.11.

For each new regression, record the diagnostic or actual executed trace,
generated artifact identity, termination status, and supported profile.
Use sanitizer-backed compiler tests for host arithmetic and lifetime defects where
the installed toolchain supports them; record unavailable instrumentation honestly.
Inspect generated native/script output when verifying argument layout and scope.
Run Workbench behavior probes for claims about actual engine effects.

The document now contains 232 proposed validation cases.
Their presence is a specification inventory, not a passing test count.
The earlier formula checks and the second review's small mathematical checks
remain distinct from compiler tests, target validation, and performance measurements.
Only mark a repair complete after its relevant acceptance evidence exists.
