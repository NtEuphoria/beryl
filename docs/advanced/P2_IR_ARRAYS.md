# P2 checkpoint: bounded fixed-array IR foundation

Date: 2026-09-07. Status: independently reviewed and focused-test verified;
integrated as an experimental lowering, verifier and evaluator checkpoint.
It does not release an IR emitter, change `--lowering auto`, or make public
`--lowering ir` available.

## Purpose and compatibility

Extend the existing finite-f32/plain-record/let/inout evaluator with fixed-array
values and explicit checked index places. Preserve the complete current PID
corpus while making array evaluation order and access intervals independently
verifiable. Normal production compilation continues through the existing AST
backends. This checkpoint supplies no measured optimization or performance claim.

The unit-facing API remains:

```c
IrProgram *ir_lower(Arena *, DiagBag *, const SourceMap *, Program *);
IrVerification ir_verify(const IrProgram *);
IrRunResult ir_test(const IrProgram *, IrRunOpts);
```

Its input must already be resolved, type-checked and ownership-checked. Shared
ownership errors retain their existing diagnostic, including BE0401 for
overlapping mutable arguments. Experimental subset limitations use BE1101.
BE1102 identifies invalid IR produced by lowering; it is not a substitute for
rejecting known unsupported source constructs during admission.

The internal schema advances from 3 to 4. It is an indexed in-memory C model;
there is no public serialized IR file format or compatibility promise for
handwritten schema-3 IR. Completed IR retains no AST, Type, Item or Local pointer.
The existing ordered source manifest, source content hashes, owned identity
strings and span checks remain in force.

## Admitted values and operations

Fixed arrays contain bool, signed i32, finite f32, admitted plain records or
other admitted fixed arrays. Arrays can be copied, returned, passed through
`let` or `inout`, nested in records, indexed, overwritten and iterated. Array
literals evaluate elements in source order. Compound assignment captures the
destination and old value before evaluating the RHS. A read-only aggregate
argument can borrow its admitted place; returning it creates a separate value.

Exclusive integer range loops, array foreach snapshots, structured exits,
immediate user `defer`, expanded defaults, checked arithmetic and the preceding
record/PID subset retain their existing behavior.

This checkpoint excludes owning containers, strings as program values, engine
objects, option/error payloads, arbitrary integer/float widths, uninitialized
locals, `set`, `sink`, aggregate equality, aggregate printing and unknown
intrinsics. Parsed or type-checked syntax alone does not imply IR support.
`sqrt` and other numeric facilities outside the existing IR intrinsic inventory
remain excluded. Source admission traverses unsupported dead code too.

Arrays have at most 256 logical elements and at most 256 flattened storage cells
including nested values and internal padding. The total aggregate type table is
limited to 256 entries, with at most 2,048 record fields. Existing instruction,
value, place, source, nesting, call-depth, frame-memory and execution-step quotas
continue to apply. These are explicit experimental ceilings, not a sizing claim
for large mods or a general compiler resource proof.

## Representation and verification

`IrAggregate` distinguishes nominal records from structural arrays. Record
identity still comes from its resolved declaration. An array is interned by
its element IR type and logical length. Aggregate definitions are topologically
ordered: an element or field type precedes its containing type. The verifier
rejects duplicate structural arrays, duplicate record identities, invalid enum
values, recursive/forward types, invalid lengths and inconsistent cell counts.

An empty array has logical length zero. Its frame representation reserves one
unobservable cell so all stored values have addressable frame storage. That
cell is never an array element: index zero fails bounds checking, iteration
executes zero times, and no printed value or array-element event represents
padding. Empty nested arrays obey the same rule. Padding is included in resource
accounting and can be copied as private representation bytes.

The new instructions are:

| Instruction | Contract |
|---|---|
| `IR_ARRAY` | Construct a value from exactly its logical number of ordered, correctly typed operands. Empty arrays have zero operands. |
| `IR_INDEX_VALUE` | Evaluate a checked index into an already captured array value and copy the selected logical element. |
| `IR_INDEX_BASE` | Mark selection of an initialized array place before evaluating the index expression. |
| `IR_INDEX_PLACE` | Consume that base capture, check a signed i32 index, then define the element place. |

A dynamic place carries its defining projection instruction. Its parent is an
earlier place in the same function. A static record projection has an exact
field identity; a dynamic array projection has an element type and no field
identity. Root places cannot masquerade as projections. Each base capture has
exactly one matching consumer in the same region and in the correct order.

The verifier rejects a dynamic place used before definition, used across an
unverified region boundary, or used after an overlapping write/control effect
crosses its access interval. `IR_LOAD`, `IR_STORE`, call captures and nested
index bases all check dynamic ancestors. Required read/failure effects cannot
be erased from checked projections. The structural verifier runs before the
evaluator and rejects malformed source spans, tables, list links and operands.

Mutable accesses use conservative possible-overlap ranges. A dynamic index can
refer to any logical element of its containing array; its value is not guessed
from a literal or from earlier conditions. Nested record offsets can distinguish
disjoint subregions, but existing source ownership may reject a program before
this more detailed experimental analysis applies. In particular, simultaneous
mutable indexed arguments can remain rejected even when their source indices
or enclosing fields appear distinct. This checkpoint does not weaken that rule.

Calls can affect storage only through their explicit inout arguments in this
subset. There are no globals, escaping references, mutable let parameters or
unknown external calls. An intervening overlapping call or control operation
therefore rejects the captured interval. Invalid future call/capture indices
are handled conservatively before any dereference during interval scanning.

## Evaluation and failure order

The independent evaluator uses its own indexed frame storage and arithmetic;
it does not call the AST evaluator or runtime arithmetic helpers. Static field
addresses are resolved lazily from the nearest root or already checked dynamic
place. This avoids constructing field pointers from undefined element places
when a frame is first allocated.

For `array[index]`, the admitted order is: select/evaluate the base, evaluate
the index, check `0 <= index < logical_length`, then read or expose the element.
For an array value expression, the base value is copied before index evaluation.
For an array place, overlapping base mutation during index evaluation is rejected
instead of choosing between potentially different AST and flattened-storage
behavior. A failed bounds check never forms an out-of-range element pointer.

For `array[index] += rhs`, select/check the destination once, load its old value,
evaluate the RHS, compute the checked operation, then publish the result. No RHS
operation executes if destination indexing traps first. Earlier index arithmetic
failure wins over the later bounds operation. Existing conservative destination
rules reject overlapping RHS mutation or control effects.

Array foreach evaluates and copies the array once, then copies each logical
element into the iteration binding. Mutating the original array during the body
does not change the snapshot. Continue and break preserve their structured
scope. Loop counters cannot reach the internal padding of an empty array.

Bounds uses the explicit `IR_TRAP_BOUNDS` classification and the existing
`source_trap` event format with kind `bounds`, exact file/offset and successful
observation prefix. Arithmetic overflow and division-by-zero keep their distinct
classifications. Timeout, cancellation, budget exhaustion, invalid IR and I/O
failure cannot become a successful expected source-trap verification.

Finite-f32 grouping and per-operation binary32 rounding remain unchanged.
Nonfinite results, unsupported casts and invalid shift domains retain the
previous limited failure taxonomy; this work does not fabricate new complete
trap categories for them.

## Verification and evidence

The focused runner captures the immutable R0 compiler baseline from
`build/delivery-candidate-n24elssl` and overlays only `src/ir/*` and
`tests/unit/test_ir.c` from the private array staging tree. It records every
captured file hash, overlay identity, toolchain, exact arguments and raw output.
It creates isolated executables and does not install the active compiler.

The regression corpus includes analytical expected outputs plus AST-reference
comparisons of output, status, first failure site and ordered event bytes.
The AST arena is freed before IR execution. Cases cover nested records/arrays,
value copies and returns, defaults and let/inout access, compound evaluation,
foreach snapshot behavior, empty arrays, negative and equal-length bounds,
earlier index arithmetic failure, and suppressed later RHS/call observations.

Malformed IR mutants target aggregate kind, length, element type, cell count,
construction order/arity, projection parent/type/definition, capture ownership,
operand order, missing failure effects and missing source bounds. An otherwise
valid arithmetic mutation must fail an analytical assertion. Repeat lowering
checks stable indexed instruction relationships and source manifest identity.
The complete existing PID implementation and its eight-test, 2,206-assertion
analytical/seeded corpus remain part of this suite.

Final frozen focused evidence: `build/p2-ir-sst1mll7/results.json`. Both O0 and
O2 with UndefinedBehaviorSanitizer passed 51 cases and 1,268 checks. The complete
isolated compiler built successfully with SHA-256
`2489ac8b664e89f0f3e833330fbc43d40557bfd22ece45d917cdb4f2eb0f63bf`.
The retained PID comparison executed 208,908 IR steps, produced 63,834 stdout
bytes and matched 1,516,831 event bytes exactly. These are correctness-corpus
counts, not benchmark results. An independent read-only review of lowering,
types, verifier, evaluator, source retention and array tests found no additional
material admission/order/address issue. It does not constitute a formal proof.

`build/p2-ir-freeze.json` identifies the exact integrated overlays and their
prior R0 bytes. The active compiler was not installed by this task. A later
whole-project receipt must explicitly include this checkpoint before claiming
integrated release validation. Earlier failed development runs are retained as
failures; no failed run counts as release evidence.

This corpus checks observable test prefixes. It does not implement arbitrary
registered aggregate-root snapshots after traps, prove absence of all hidden
writes, establish an emitted-backend equivalence matrix, or demonstrate engine
runtime behavior. Those remain separate gates.

## Next gates

1. Close the source-level alias/admission contract for remaining access modes
   and array cases before widening this subset.
2. Implement and independently test uninitialized/set/sink state transitions
   with explicit initialized-destination rules.
3. Add the unoptimized IR C emitter and verify admitted programs against AST
   reference, IR evaluation and actual O0/O2 generated execution.
4. Add emitted EnforceScript parity with its engine-specific value/storage rules.
5. Release an explicit IR selection only after its published subset passes those
   gates; keep automatic selection unchanged until a separate release decision.

Owned storage, cleanup and optimizer experiments follow their own dependencies.
They are not supplied implicitly by a correct fixed-array value representation.
