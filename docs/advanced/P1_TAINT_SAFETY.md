# P1: provenance and bounded range checks

Status: implemented in the developing source; final immutable integration gates
are recorded in `../BERYL_DELIVERY_STATE.md`. No engine authority or machine
constant-time guarantee follows from this packet.

## Changes and scope

The previous pass unconditionally removed untrusted provenance at min/max/clamp
and every validator call. It updated direct-local assignments only and did not
propagate callers into helper-internal sinks. New code retains provenance and
separates integer interval proofs at fixed-array index sites.

Record fields use resolved field identity rooted in resolved local identity.
Indexed elements deliberately share one conservative cell. Parent/child reads
include applicable writes; disjoint plain record fields remain separate. Struct
literal writes preserve this separation. Calls include receivers/default-expanded
arguments, return sources, and mutable parameter writes. A monotone whole-program
fixed point runs before sink diagnostics, covering loop backedges and recursive
groups without depending on declaration order.

This first implementation is **context-insensitive**, with joined call inputs and
outputs. It is a conservative repair, not completion of the planned symbolic
summary system. Mutable-parameter field outputs can conservatively taint a whole
caller aggregate. Dynamic storage-length facts, alias precision and complete
engine contracts remain subsequent gates.

## Admission and compatibility

Ordered constant integer clamp bounds and independently bounded helper return
expressions may prove a fixed-array index. Provenance remains for other uses.
Reversed bounds, wrong-array bounds, bare validator annotations, unsupported range
expressions and one-sided min/max do not prove safety. Mutable local initializers
are not treated as persistent bounds facts. No target-specific bound is inferred
from an unavailable engine contract.

Secret control checks include short-circuit, range iteration and optional/error
selection, alongside branches and indices. `@server_only` and `@constant_time`
retain their source-level restrictions. Repair guidance no longer suggests that
adding a server annotation establishes runtime authority.

Limits: 4,096 functions, 65,536 field cells, projection depth 24, evaluation depth
192, bounded range inference depth 64 and 4,000,000 accounted work units. Exceeding
the analysis budget emits BE0608 and fails; it never returns a clean result.

## Verification

The security unit suite preserves existing positive fixed-array clamp/helper
cases and adds failures for incomplete/reversed/wrong-array bounds, fake
validators, helper-internal sinks in both declaration orders, field/element writes,
inout/set propagation, recursive groups, loop backedges, secret short circuit,
mutable range invalidation and zero-argument source propagation. A positive
disjoint-field case guards against unnecessary local field contamination.

The first integrated development run passed 399 cases / 3,201 checks, including
the unchanged actual PID IR corpus. Subsequent edits and release evidence must be
validated against captured inputs; this development count is not reused as a
receipt for later bytes. Additional bounded-resource and adversarial precision
tests are required before broadening the advertised proof subset.
