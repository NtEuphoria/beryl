# M2 implementation packet: bounded semantic reference

Status: bounded Windows reference/native gate passed; M2 compiler installed. Governing plan:
[SPARKOS_IMPLEMENTATION_PLAN.md](SPARKOS_IMPLEMENTATION_PLAN.md).

**September 7 admission refinement:** the advanced checkpoint found a case outside
the established parity corpus: selecting a record field as an assignment
destination, then replacing the enclosing record during RHS evaluation. The
preserved reproducer prints `10` in the earlier reference interpreter and `7` in
native O0/O2 execution. The language specification does not settle this boundary;
neither result becomes a new normative rule here. Reference admission now rejects
potentially overlapping mutation during projected destination evaluation or its
RHS, with BE1001 before executing tests. Explicit IR destination guards separately
reject that boundary. Statically disjoint field/constant-index operations and the
full PID remain within their tested subsets. Ordinary native compilation is
unchanged. See the [current integration evidence](BERYL_ADVANCED_IMPLEMENTATION_STATE.md)
and [IR packet](advanced/STAGE_D_IR.md) before applying the older parity claim.

## Objective and dependency gate

Run a deliberately bounded part of the checked Beryl AST through independent
evaluation code before introducing structured IR. The complete current MESH PID
is the first customer. M1 must first pass native, driver and Workbench compilation
checks. Reference execution is selected explicitly; native remains the default.

## Public contract

- `beryl test --backend native` preserves the existing compiled test path.
- `beryl test --backend reference` admits supported AST/types before execution,
  then runs selected tests with independent evaluation and arithmetic.
- `beryl test --backend differential` executes both admitted paths, retaining
  their outputs and ordered observable test events. A missing path, failure,
  trap, budget exhaustion, output difference or event difference fails the job.
- Explicit step/call-depth budgets and an allocation budget bound the reference.
- Unsupported syntax or types produce an unavailable-capability diagnostic;
  no expression is silently replaced by zero and no test is silently skipped.

The first numeric admission is bool, i32 and binary32 f32, plus immutable string
literals used for output. Plain records and fixed arrays recursively contain
admitted values. Wider integers/floats, vectors, owned containers, options and
error unions require separately added admission and tests.

## Evaluation model

Use resolved declaration/local identities. Do not call emitter evaluation code,
native runtime arithmetic helpers, or constant-folded values as the runtime
oracle. Evaluate original constant initializer expressions independently.

Records and arrays hold independent logical values. Assignment copies them;
read-only parameters borrow admitted storage, inout/set parameters refer to
caller storage, and sink transfers the admitted value. Fixed storage remains
stable during an admitted borrow. There is no claim of general owned-container
coverage or observable destruction callbacks.

Evaluate ordinary operands and arguments left to right. Evaluate target places
and indices once before assignment RHS work. A compound assignment observes the
old target value before RHS side effects. Short-circuit operators evaluate only
the selected RHS. Structured loop control and returns propagate explicitly.
Keep current immediate `defer` execution; do not introduce scope-exit semantics.

Each f32 operation rounds to binary32; preserve AST expression grouping. Force
rounding through actual float storage in the reference and keep native parity
builds free of contraction/fast-math. Preserve finite signed-zero behavior where
observable. Nonfinite arithmetic is outside the initial PID admitted corpus;
it must be reported, not used to claim cross-target universal equivalence.

Define checked i32 overflow, division by zero and invalid indices as traps.
Explicit wrapping operations, if admitted, compute modulo 2^32 without C signed
overflow or implementation-defined narrowing. Cast admission and numeric failure
conditions must be documented beside their implementation.

## Required independent evidence

- Small numerical fixtures with externally calculated expected answers.
- Expression/argument/compound-assignment ordering and short-circuit cases.
- Aliased-place rejection inherited from the checked contract plus independent
  value-copy, nested fixed-array and scalar mutation execution checks.
- Normal/early return, break, continue, immediate defer and recursion-budget cases.
- Empty test selection, unsupported feature, budget and trap failures.
- Native/reference output and ordered event comparison.
- Deliberate arithmetic, ordering and state-update mutations that make the
  comparison or independent assertions fail.
- Binary32 literal round-trip tests for Enfusion generation, including values
  whose existing `%g` formatting loses required precision.

M3 adds seeded complete PID operation sequences and compares persistent state
after every operation. Agreement between generated targets is insufficient by
itself; fixtures and properties remain independent checks.

## Rollout and evidence

Implement the bounded interpreter in C, maintaining ordinary compilation's
independence from Python. Keep unsupported owning/error-union paths outside its
advertised inventory. Record exact source/compiler identities, admitted features,
budgets, executed test counts, event logs and failures. No optimizer or production
MESH source is changed as a side effect of this milestone.

## Implemented contract and limits

The interpreter lives in `src/reference/`, with CLI orchestration in
`src/driver/reference_driver.c`. Native remains the default test backend.
`--max-steps` defaults to 1,000,000, `--max-call-depth` to 128, and
`--max-bytes` to 67,108,864. Allocation accounting is cumulative for the run;
all reference-owned storage is released afterwards. It is not a reusable heap
or a measurement of the generated program's memory consumption.

Admission examines all loaded concrete declarations, including unused functions.
It also bounds AST/type walks, fixed-array elements and evaluation nesting.
Reference execution has a separate timeout, cancellation hook and 64 MiB output
limit. Test assertions continue and count failures, but only the first source
assertion creates a compiler diagnostic. Ordered JSONL events retain all results.

Differential tests compare stdout and ordered assertions/prints/test transitions.
Every printed f32 additionally records its exact binary32 bits. Native tracing
is enabled only for this test mode. Result artifacts identify admission,
reference execution, native compilation, native execution or comparison as the
actual stage; unavailable, timeout and cancellation do not become ordinary
successful exits. A differential native failure does not print the reference
path's successful summary as though the combined operation passed.

The independent rounding fixture found two real double-rounding defects:
decimal literals parsed through binary64 before f32 conversion, and folded
integer literals converted to f32 through binary64. The lexer now preserves
numeric spelling, f32 checking parses it directly, and integer folding casts
directly to binary32. Formatting retains that spelling. Enfusion emits an exact
widening of the rounded binary32 value, including a floating suffix where needed.
The reproduced failing run remains at
`.beryl-cache/job-40504-89569453-1/result.json`.

Finite f32 sequences are the admitted numerical domain. This is not a proof of
universal floating-point equivalence, host rounding-environment independence,
Enfusion runtime parity, arbitrary strings or general owned-storage semantics.
No Enfusion interpreter backend or performance comparison is implied.

## Completion evidence

- Normal foundation: `build/foundation-3bys9qw6/results.json`, 309 cases and
  1,820 checks; 15 native programs/harnesses at O0/O2, shared PID example tests.
- UBSan: `build/foundation-qbhjsxdh/results.json`, same complete corpus passed.
- Reference/differential: `build/reference-nj1ndyej/results.json`. Admitted
  corpus, exact float observations, formatting/rounding fixtures, module tests,
  partial PID example, unsupported/empty/failed/trapped/budget/timeout cases,
  external cancellation, and three compiled mutants all behaved as expected.
  Arithmetic, ordering and a missing state update were each detected.
- Driver: `build/driver & spaces-1zud1uax/results.json`, all existing gate groups.
- Workbench 1.8.0.13:
  `build/enfusion-proof-f6378159ca1e4bb6899f3f42209edd0a/result.json`, precision
  fixture ordinary function compiled with no errors or warnings. This was
  compilation, not execution of the engine numerical comparison.
- Installed compiler SHA-256:
  `77b37cb58d2aa35dec024257bb30d55089ade0d1187fc648b3c8c32ac9e92315`.
  Publication and M1 rollback executable are under `build/foundation-3bys9qw6/`.

M3 still must port the complete current controller and execute its engine tests.
