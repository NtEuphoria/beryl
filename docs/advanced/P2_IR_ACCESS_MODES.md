# P2 — Plain-value initialization and access modes

This October 14, 2026 implementation extends the experimental IR test path to schema 5. It adds declared-but-uninitialized locals, plain-value `set` parameters, and whole-root `sink` transfers. It does not release production IR lowering, change automatic lowering, or introduce owned storage.

## Source identity and verification status

The pre-change bytes are preserved under `build/p2-ir-access-modes-source-baseline-20261014-v1/`. The ten implementation, unit-test, differential-runner and fixture inputs handed to the integration owner are identified by `build/p2-ir-access-modes-source-ready-20261014-v1.json` (SHA-256 `a1bfbc21cd13b1a95dbcda07ffeb8292c624805ba9e68baba075a617821fc060`). These identify source inputs, not successful verification or an installed compiler.

An early private candidate executed the new six-test corpus with 26 assertions and the expected ordered output prefix `7`, `5`, `90`. The development foundation attempt `build/foundation-ygfdilmy` retained seven failed assertions among 10,690 checks in 580 cases. Six failures came from three obsolete tests that still expected the newly admitted access modes to be unavailable. The seventh changed an initializer into a first store, which is now valid. The revised tests exercise successful access-mode behavior and replace that obsolete mutation with an actual uninitialized read. The failed attempt remains evidence for its original inputs.

The final frozen foundation attempt `build/foundation-jzw0pu20/results.json` compiled its unit executable, but Windows application control refused launch with error 4551. That is an unavailable execution capability, not a passing or failing unit result. The separate differential matrix then stopped on the same launch restriction for a generated executable. Both blocked binaries are preserved without modification or launch retries. Full final-unit, O0/O2 differential and sanitizer acceptance remain incomplete. The earlier runnable private compiler matches the implementation sources apart from header documentation; its preliminary corpus result does not close those gates. See [the consolidated checkpoint](CORE_AUTHORING_2026_10_14.md) for exact receipts and Code Integrity events.

## Admission and semantics

The existing bool, i32, finite-f32, plain-record and fixed-array categories remain the value domain. Source strings as values, owning types, engine references, partial moves, partial aggregate initialization and error-payload ownership remain outside this profile. Existing source checks run before IR admission; the IR verifier additionally rejects malformed or inconsistent tables.

A local has distinct undeclared, declared-but-uninitialized, initialized and moved states. A declaration makes its root available but does not make it readable. The initializer is evaluated before the declaration is installed, preserving source order and outer-binding resolution. Reads require definite initialization on every path reaching the read. A whole-root assignment or successful `set` call may initialize an uninitialized or moved root, including an immutable root; replacing an already initialized immutable root remains forbidden.

A `set` parameter starts logically uninitialized in the callee. Physically, it aliases the caller's destination; entry does not clear or replace the caller's previous value. The replacement expression is evaluated before its store. The callee must initialize the parameter before reading it and before every admitted normal return. Completed writes survive a later source failure: the call is not transactional. An initialized `set` parameter may itself be moved as a whole root and must be reinitialized before normal return.

A whole-root `sink` argument snapshots its plain value and moves the source during that argument's evaluation, before subsequent arguments. It receives independent callee storage. A later read of the moved root is rejected until reinitialization. LET and INOUT parameter roots cannot be moved; SINK and initialized SET roots may be. A literal or computed value can be passed to SINK without inventing a source root. No destructor or trap-unwinding semantics are added.

Receiver evaluation precedes explicit arguments. Existing expanded defaults retain their formal order and LET-only admission. A SET destination is captured exactly once and its caller-side logical initialization is published only after all argument captures have been checked. Thus an initialized destination's previous value can still be read by a later scalar argument; a previously uninitialized destination cannot. Overlapping invalidation by declaration reset, move, store, INOUT or SET calls invalidates an earlier active capture. Projection checks retain the existing bounded access contract.

## Control flow and bounded loop admission

Branches merge possible logical states; a read requires the merged state to be exactly initialized. A returning branch does not poison the normal continuation of its sibling. SET obligations are checked at every return rather than inferred from one successful branch.

Loop conditions execute with their effects even when the body executes zero times. Break states contribute to the post-loop state. Continue states contribute to the actual back edge. Per-iteration declarations reset local logical state at the declaration. Immediate `defer` remains an ordinary operation at its existing position.

This implementation conservatively requires each outer root's logical state at a reachable back edge to equal its loop-head state. Moving and restoring a root before that edge is admitted. A valid source program that changes its outer initialization state across iterations may remain unavailable with BE1101; the verifier does not silently discard that transition or declare it language-invalid. More general loop analysis is a separate extension.

## Representation and consumers

`IR_DECLARE` and `IR_MOVE` make declaration/reset and whole-root transfer explicit. `IR_CAPTURE` records the access mode, so SET captures do not require a prior read. The verifier checks declaration identity, initialization, capture consumption, overlap, calls, control exits and SET return obligations. All consumers use `IR_SCHEMA_VERSION`; the differential runner rejects a stale schema receipt.

The independent evaluator applies declaration and move restrictions through verified IR. Physical plain-value transfer copies the value; it does not introduce a second owned-storage runtime. SET retains the existing alias to caller storage. The C test emitter follows the same contract: LET aggregate parameters borrow const data, SET/INOUT alias caller destinations, and SINK aggregates are copied into independent callee roots. No source operation may cross an incompatible ownership convention.

The shared frontend, ordinary AST emitter and production backend selection are unchanged. The historical schema-4 package under `tools/beryl-ir-experiments` is not extended into a competing schema-5 implementation.

## Verification contract

The independent expected-value corpus is `tests/reference/access-modes/plain.be`. It covers immutable first initialization, records and arrays, copy independence, whole-root moves and reinitialization, SET/SINK receivers, expanded defaults, once-only index evaluation, SET forwarding, moving an initialized SET parameter, branch exits, loop continue/break and immediate defer.

The unit suite defines comparisons of analytical expected outcomes with AST reference and independently evaluated IR. Separate table mutants exercise uninitialized reads, unavailable declaration roots, duplicate declarations, missing move operations, missing SET initialization, parameter resets and invalid loop back edges. Emitter tests retain deterministic output, bounds and source-table independence while exercising the new parameter conventions. The final expanded unit suite compiled but did not execute because of the recorded launch block.

Run `scripts/verify-ir-differential.py --beryl <candidate-compiler> --clang <verified-clang>`. The runner executes the access corpus through AST-to-C and IR-to-C at both O0 and O2, alongside the existing complete PID, trap, admission and deliberate-native-mutation checks. Parity builds retain disabled floating-point contraction and fast-math. Existing foundation and sanitizer suites remain required integration gates.

Two additional expected-failure fixtures cover a first SET replacement expression that traps and a completed SET write followed by a later trap. They verify the exact source failure and successful stdout/event prefix across AST/IR emission at O0/O2. That evidence does **not** inspect arbitrary caller memory after abnormal termination or prove the absence of hidden writes. Registered root snapshots remain unavailable in this IR test emitter, and no stronger failure-memory claim is made.

## Remaining gates

The full differential attempt at
`build/ir differential & spaces-fcqlj3nk/results.json` also stopped before its
first completed group: Windows rejected the generated program's launch with
error 4551. Receipt SHA-256:
`eb077f3c941cc73e0a1a49dff762234c31d27662e5fdd685b674bf801027cd25`.
The frozen foundation receipt SHA-256 is
`fe534202c70283bf455fc6cbce2e6bbf7c5515a63220fc70215f91107a7f80c9`.
The Code Integrity 3077 events for both exact paths are retained in
`build/oct14-core-code-integrity.json`; neither the policy nor the blocked
executables was changed or retried. O0/O2 matrix and sanitizer acceptance remain
incomplete. The earlier successful six-case differential execution is separate
evidence, not a substitute for this matrix.

This category remains experimental until its exact integration receipts pass. It does not close R1's production backend gate. Production build/run IR, EnforceScript IR lowering, automatic selection, owned collection lifecycle, partial aggregate initialization, broader loop admission, arbitrary trap-root observation and performance adoption remain separate work.
