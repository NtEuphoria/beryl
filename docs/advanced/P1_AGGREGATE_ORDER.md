# Aggregate evaluation order: implementation packet

This packet records a confirmed AST-emitter defect discovered by the independent
IR-to-C experiment. It is a correctness repair, not a performance result.

## Contract and original defect

For `Pair { right: mark(2), left: mark(1) }`, the calls execute as `mark(2)` and
then `mark(1)`, even if the declaration lists `left` before `right`. Layout order
does not determine expression order. Each initializer's value must be captured
before a later initializer can mutate its source.

The former native emitter visited declaration fields while generating their
initializer expressions. The former EnforceScript emitter did the same when
assigning fields of the new object. The independent native fixture observed
`1` then `2` while reference execution observed `2` then `1`.

The unchanged values in the final record were insufficient to detect that bug.
The matrix failed because it also compared ordered observable output. Earlier
verified compiler receipts remain valid only for their recorded coverage; they
did not contain this counterexample.

## Implementation

- Native record emission evaluates and captures every normalized initializer in
  source order. Designated C fields then consume those already captured values.
- Native array emission captures each element before evaluating the next one.
  It does not rely on the C implementation's initializer evaluation order.
- EnforceScript record emission visits normalized initializer order and completes
  each field assignment before generating the next expression.
- The existing constant-default admission and generated public constructors are
  preserved. No ownership convention, record layout or external class name changes.

Affected production files are `src/back/c_backend.c` and
`src/back/enforce_expr.c`. Native behavior is exercised by
`tests/e2e/aggregate_order.be`; the real engine suite adds `record_order`,
`record_capture`, and `array_capture` to `tests/engine-integers/operations.be`.
The corresponding values are independently specified in the verifier.

## Related intrinsic argument capture

Bounded follow-up probes confirmed three additional native lowering problems:

- `xs.set(c.value, c.next() + 0)` could use the index after `next` changed it.
- A vector constructor could read its first component after a later component's
  helper mutated that source.
- `c.value.dot(c.next())` could read the receiver vector after `next` replaced it.

Both O0 and O2 reproduced the mismatches with UBSan enabled. The retained probe
receipt is `build/intrinsic-order-sg38zsaa/results.json`. A simpler direct-call
variant sometimes passed, which is why the fixtures include nested arithmetic.

The native emitter now captures a vector receiver and its arguments as values,
and a List receiver as a storage address before capturing its arguments. List
set does not re-evaluate the destination index. EnforceScript inserts ordered
captures when a receiver or argument can perform work. Its existing admission
rules remain intact.

`tests/e2e/intrinsic_order.be` checks the three native cases. The admitted vector
construction case also lives in `tests/engine-integers/target_operations.be`.
The engine verifier labels it **native-and-engine-only** and runs independent
analytical assertions; it does not claim reference or IR support for Vec3.
The List/set and vector-receiver alias probes remain rejected by the current
Enfusion storage gate and are not counted as engine-executed cases.

## A disproved suspicion

Review also raised whether a field default containing `mark()` could execute
again in the EnforceScript constructor or copy helper. The integrated tests
showed that the existing frontend already rejects that source with `BE0501`:
`src/sema/defaults.c` requires field defaults to pass constant evaluation.

The attempted extra Enfusion restriction was removed. Its failed test run is
retained under `build/delivery-aggregate-cwukejvi`, in both foundation receipts.
That attempt also used unsupported enum-member spelling in a new fixture; the
replacement positive test exercises admitted named constants and constant
arithmetic. Neither failed fixture is reported as a compiler regression.

## Verification and release boundary

The private experiment's earlier failed matrices remain retained, including
`build/ir-c-he2_0jyc/results.json`. A fresh full compiler capture and native/engine
revalidation are required after the repair; their final receipt paths belong in
`../BERYL_DELIVERY_STATE.md`.

Verification must include final values, prior-read capture, observable call
order, the unchanged full PID, and successful failure prefixes where supported.
Private instrumented IR-C parity does not release public IR lowering or establish
machine-code performance. Other AST evaluation paths require their own admission
and regressions; this packet alone is not a proof for every expression kind.
