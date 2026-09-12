# P1: shared projected-destination safety

Status: implemented and focused verification passed against the preserved delivery
baseline plus the files listed below. Integrated delivery verification remains a
separate gate. No active compiler installation or engine launch was performed by
this workstream.

## Problem and compatibility decision

The earlier retained reproducer selected `r.x`, then replaced `r` while evaluating
the assignment RHS. The AST reference reported `10`; native O0/O2 reported `7`.
The reference-only guard rejected that boundary with BE1001, while ordinary native
commands continued accepting it.

P1 moves the safety requirement into shared semantic analysis. A projected
assignment must retain a valid exclusive destination throughout destination
evaluation and its RHS. A conflicting or unproven mutable access is rejected with
BE0401 before generation, native compilation or execution. Neither prior numeric
result becomes the specified answer for that rejected program.

This is an intentional compatibility change for affected source. Refactor such
source into explicit statements that choose the intended mutation, old-value read
and destination-selection order. The diagnostic guidance is not an automatic
equivalence-preserving rewrite, particularly for compound assignment.

## Implementation

| File | Responsibility |
|---|---|
| `src/sema/access.h` | Shared result/status interface and finite analysis limits |
| `src/sema/access.c` | Resolved storage paths, conflict scan and whole-program destination prepass |
| `src/sema/ownership.c` | Runs that prepass before ordinary ownership flow analysis |
| `src/sema/ownership.h` | Documents the additional exclusive-access obligation |
| `src/reference/admit.c` | Reuses the same per-assignment check for direct API admission |
| `tests/unit/test_destinations.c` | Dedicated shared-check regressions; `run_destination_tests` registration belongs to the integrated runner |
| `tests/unit/test_reference.c` | Preserves direct reference API rejection tests even when ownership is deliberately bypassed |
| `tests/reference/destinations/` | Original reproducer fixtures plus shared-analysis boundary cases |
| `scripts/verify-reference-destinations.py` | Checks common CLI rejection, prior-output preservation and accepted executions |

`access_projected_assignment(statement, visits)` returns `ACCESS_SAFE`,
`ACCESS_CONFLICT`, or `ACCESS_UNPROVEN`, with destination/conflict spans and a
reason. It does not change local ownership state. `access_check_destinations`
visits all relevant concrete source bodies, constants and expanded expressions,
including statements that ordinary execution cannot reach.

The per-program prepass and per-assignment checks share a 100,000-visit budget.
Traversal and path depth are bounded at 128. Exhaustion fails closed. These limits
bound this analysis; they are not a claim that every other compiler pass has the
same resource accounting.

Both target paths already invoke `ownership_check` through the common driver
front end. No command dispatcher or backend semantic rewrite was needed.

## Admitted and rejected access intervals

The check covers fields and indexed destinations, including effects in the index
expressions themselves. It scans nested calls, method receivers, explicit
arguments, expanded default arguments, operators, conditional branches, blocks,
loops, immediate defer, error-expression alternatives and unsafe expression
bodies. A skipped or unreachable branch is still checked conservatively.

Writes, `inout`, `set`, `sink`, mutable method receivers and known mutating List
intrinsics count as potential invalidations. Calls with unavailable summaries
cannot manufacture purity. Read-only known intrinsics may still have observations
such as printing; the guard preserves their position and only checks destination
validity, rather than requiring every RHS to be pure.

Paths use resolved local and field identities. Distinct constant array indices
and distinct fields prove separation for recursively plain values. Dynamic
indices are conservatively overlapping. Different local spellings, struct fields
or container indices do not prove backing-storage separation when owning
containers or reference wrappers are involved. Those cases remain unproven
without a separate storage-identity analysis.

Current defaults permit closed expressions and reject formal references or
non-let argument defaults before this pass. The new default fixture checks a
conflicting explicit argument together with an actually expanded closed default;
it does not claim support for mutable formal-dependent defaults.

Accepted behavior includes disjoint plain record fields, disjoint constant fixed
array indices, index calls mutating unrelated plain locals, and explicit separate
mutation/assignment statements. Whole scalar-binding assignment is outside this
new projected-place guard. Existing `x += bump(inout x)` old-value ordering is
retained and exercised, as are safe projected compound assignments.

## Reference defense in depth

Normal CLI reference and differential commands now stop at BE0401 in the common
front end. They do not start a reference job or a native comparison job.

The standalone reference API can be invoked by code that has not called ownership
analysis. Its admission layer therefore retains BE1001, using the shared helper
instead of a second conflict implementation. The dedicated fallback tests bypass
ownership deliberately and assert zero interpreter steps, tests and events.
All other reference unit cases retain their normal complete front end.

## Focused evidence

The source baseline is
`build/delivery-baseline-b742d5aaf916468485134457aa2af2bf/inputs`.
The focused build records every baseline source hash and the explicit P1 overlay.
It does not include the concurrent taint or allocation workstreams.

- [Focused immutable build and UBSan results](../../build/p1-baseline-focused-r8_013y0/results.json):
  **30 unit cases / 158 checks**; independent optimized CLI compiler also built.
- [CLI destination results](../../build/reference-destinations-ip_tzgdi/results.json):
  **17 checks**, with an exact selected/executed set of **15 fixtures**.
- The 14 rejected fixtures each exercise 11 command variants: **154 BE0401
  command checks** covering ordinary/JSON checks, Enfusion checking, C emission,
  native build/run, Enfusion generation, native debug/release testing, reference
  testing and differential testing.
- Rejection creates no build/execution job, emits no C and preserves both prior
  native output bytes and the prior Enfusion output directory contents.
- Safe fixture execution passes reference, differential, native O0 and native O2.
  Safe Enfusion checking and generation pass; no engine runtime parity claim is
  made by that generation check.
- The unchanged complete PID passes **8 tests / 2,206 assertions** through both
  reference and differential execution.

Fixtures include ancestor replacement, compound assignment, nested records,
mutable receiver, fixed-array replacement, unknown index overlap, set, sink,
destination-index mutation, skipped/unreachable code, nested calls, expanded
defaults and potentially shared List storage. The verifier rejects missing or
unexpected fixtures and records unchanged compiler and source hashes at the end.

An independent read-only review found no further material issue within this
bounded contract. Final integrated unit, sanitizer, CLI and engine validation
must still identify their own exact combined source snapshot.

Re-run the focused command check with:

```text
python scripts/verify-reference-destinations.py --beryl <candidate-compiler> --clang <clang>
```

## Remaining boundaries

This completes the projected-assignment safety subtask. It does not complete P1
taint, arithmetic, allocation or parser-resource work, nor the broader ownership
and storage-lifecycle program. General interprocedural effect inference,
owning-container alias proof and less-conservative dynamic-index reasoning remain
separate gates. Shared semantic rejection does not replace the IR verifier's own
independent destination-capture validation.
