# P1: target-specific storage copy and borrow admission

Status: the shared classifier and admission implementation passed focused unit
verification. Integration into the common target lints and the public-driver
pre-job boundary is a separate root-owned gate. This packet does not mark the
whole ownership milestone or release gate complete.

## Purpose and compatibility decision

Beryl promises independent logical values, but its current emitters do not
implement every required copy, transfer and destruction operation. Successful
parsing of `List<T>` or another container is not evidence that every use works.
This change rejects the known unsupported operations before generation or
execution while retaining the established scalar List programs.

The native `List<T>` representation is a data pointer, length and capacity.
Ordinary C assignment copies those three fields. Without a recursive copy, two
apparent Beryl values share the allocation; later growth can invalidate the
other descriptor. Nesting that descriptor inside a struct, fixed array, option
or error payload does not make the copy independent.

Enfusion uses reference objects for records and collections. Its current
`BerylCopy` helper recursively copies record fields and uses collection `Copy`
for scalar array/List fields. However, the ordinary expression copy hook handles
record places only. A standalone array/List binding or return of an existing
collection therefore retains a shared collection object. Collection insertion,
retrieval and `foreach` binding also lack the general recursive value-copy
operation for reference-valued elements. A shallow `Map<str, Entity>` helper
does not establish independent `Entity` values.

These are different target failures and receive different admission decisions.
The gate does not silently implement reference semantics for a value, reinterpret
`let` as a transfer, or change either emitter's evaluation order.

## Implementation interface and prerequisites

Files owned by this packet:

| File | Responsibility |
|---|---|
| `src/sema/storage.h` | `StorageTarget`, recursive classification flags and public admission API |
| `src/sema/storage.c` | Declaration-based recursive classification, copy boundaries and storage-lifetime interval checks |
| `tests/unit/test_storage_admission.c` | Both-target positive/negative semantic cases and classifier limits |
| `scripts/verify-storage-admission.py` | Public CLI rejection, previous-output preservation and retained List output oracle |
| `build/p1_storage_check.py` | Retained focused immutable-baseline build runner; not an installed tool |

```c
StorageClass storage_classify(const Type *type, StorageTarget target);
bool storage_admit(DiagBag *d, Program *p, StorageTarget target);
```

The targets are `STORAGE_NATIVE` and `STORAGE_ENFUSION`. Classification reports
owned storage, shared/reference storage, a target reference representation and
unknown classification separately. `logical_copy_supported` describes the
current emitter's whole-value copying path; it is **not** a cleanup guarantee or
an engine lifetime/authority annotation.

Classification follows resolved `Type` and `Field` identities. It descends through
struct fields, fixed arrays, options/error payloads and collection elements/keys.
Cycles, unsupported wrappers, unresolved generic types and classification
exhaustion never become plain values. The exported classifier is independently
bounded. The admission walk shares a 100,000-visit allowance across AST and type
inspection and a depth limit of 128. These are this analysis's limits, not a
global compiler resource guarantee.

**Required order:** resolve and type-check, expand defaults/instantiate concrete
functions as required by the target, run shared ownership checks, then target
admission before a build job, output publication or process launch. Keep the
same gate in target lint/emitter entry points as defense for direct API callers.
The analysis depends on ownership's prohibition of mutation through `let`
parameters and invalid moves. It is not a replacement ownership checker.

Native diagnostics use **BE0903** for these unsupported storage operations;
Enfusion uses its existing **BE0701** target-profile diagnostic. Existing native
representation errors such as Map/Box may remain the first diagnostic when the
native type lint rejects the declaration before the storage pass.

## Admitted and unavailable operations

| Operation | Native | Enfusion |
|---|---|---|
| Scalar/plain-record values, independent copies and ordinary returns | Retained | Retained through existing record copy hook |
| Fixed array of recursively plain values copied as an ordinary value | Retained inline representation | Existing array places cannot be copied as independent standalone values |
| Local scalar List, push/get/set/clear, one retained owner | Retained legacy profile | Retained existing scalar collection path |
| `let` collection argument used only for admitted reads | Borrowed descriptor; cannot escape or materialize an owning copy | Borrowed object reference; cannot escape through unsupported copying |
| `inout` collection argument used for admitted operations | Pointer to existing descriptor | Existing `out`/reference convention |
| Struct containing scalar List, created without copying an existing List | Retained | Retained |
| Copy of that owning struct | Unavailable: duplicates native descriptor | Retained where the existing scalar-field `BerylCopy` helper provides the independent copy |
| Native owning replacement, even with a fresh value | Unavailable: replaced allocation has no cleanup lowering | Subject to the supported record-copy/assignment path |
| Owning return signatures or owning `sink`/`set` transfer | Unavailable | Unavailable in this bounded profile |
| Nested collection element copies, reference-element collection helpers | Unavailable when the element contains unsupported storage | Unavailable when element copying would retain references |
| Box/Pool representation and Rc/Handle retention in concrete locals/parameters | Not admitted by a claimed borrow alone | Requires a separately reviewed representation/retention contract |

A fresh array/record literal is recursively checked. Being syntactically fresh
does not permit embedding a borrowed owning value. Native List elements can be
recursively plain records or fixed arrays because those values are inline;
Enfusion reference-valued element operations remain unavailable. The pass does
not reject every unused parsed container type, and it does not claim that a
container's method API exists merely because its type is classified.

The pass examines concrete bodies, including unreachable statements and skipped
branches, and checks defaults at declaration and expanded use sites. Enfusion
record field defaults that would directly retain an existing reference-valued
source are unavailable because constructor-default emission does not insert
the ordinary record copy hook there.

## Borrow and iteration intervals

Copy containment alone is insufficient. A temporary native List descriptor can
still be captured before another expression grows the List. The interval checks
therefore cover:

1. A collection/reference receiver or argument retained while later call
   arguments are evaluated, including nested calls and expanded defaults.
2. A collection-derived `inout` element address retained while a later argument
   can mutate storage.
3. The base of an index read while the index expression executes.
4. A List iteration's retained descriptor, and Enfusion collection iteration's
   reference, throughout the loop body.

For example, this is unavailable:

```beryl
println(xs[grow(inout xs)])
```

The native emitter can capture the old descriptor before `grow` reallocates.
The source may explicitly choose a safe order instead:

```beryl
let index = grow(inout xs)
println(xs[index])
```

Similarly, `read(xs, grow(inout xs))` and `for value in xs { xs.push(value) }`
are unavailable. A read-only scalar List sum loop remains admitted.

Without independently tracked backing-storage identities, the interval scan
conservatively rejects **any potentially relevant storage mutation** in the
interval, including through mutable receivers and non-`let` arguments. It can
reject a mutation of a different collection that a future storage-identity
analysis could prove disjoint. Plain scalar accumulation remains supported.
Unknown/external/indirect call effects and unsafe effects do not acquire an
implicit purity or non-invalidation certificate.

A scalar `let` argument read from a record or collection is already captured as
an independent scalar. It does not keep an owning borrow merely because its
source has reference-backed storage. `min(c.value, c.next())` and
`read(xs[0], grow(inout xs))` therefore remain admitted, while the analogous
`inout xs[0]` argument retains an address and still rejects later invalidation.
This distinction was corrected after the first integrated suite caught an
over-conservative rejection in an existing evaluation-order fixture.

Native fixed-array iteration retains its existing inline snapshot. Enfusion
fixed-array iteration uses the engine collection reference and therefore rejects
body mutations that could change it. Range-loop bound evaluation is a separate
emitter ordering boundary. The companion integration repair captures native
`lo` before evaluating `hi` and captures Enfusion `lo` and `hi` once before loop
entry. Its root-owned regression/evidence gate covers mutated bounds and List
size bounds; the `foreach` admission check is not credited for that repair.

## Compatibility fixtures and verification

The original `tests/e2e/lists.be`, its `lists.expected` output, and
`examples/proof.be` are preserved. They cover scalar List fields, local growth,
read-only and mutable methods, bracket access, fixed range growth, scalar
iteration and empty iteration. Unsafe old fixtures stay as explicit negative
tests; deleting them would hide the compatibility decision.

The focused snapshot `build/p1-storage-ze6xyhiu/results.json` records the preserved
delivery baseline plus the three new source/test overlays and private target
lint integration. It passed **34 unit cases / 223 checks** at both O0+UBSan and
O2+UBSan, generated and ran the legacy List program at both optimization levels,
and checked the preserved List/proof sources on both targets. Generated C may
contain an intentionally unused loop binding; the focused generated-C command
allows that warning. Compiler-source warnings remain errors.

The scalar-capture correction adds two positive cases. The subsequent snapshot
`build/p1-storage-vnp_ap_3/results.json` passes **36 cases / 231 checks** at both
O0+UBSan and O2+UBSan and compares both actual legacy List outputs against the
required original expected-output fixture. Final integrated evidence, rather
than the older 34-case snapshot, is required to credit that correction in the
release record.

The portable gate is:

```text
python scripts/verify-storage-admission.py --beryl <candidate> --clang <clang>
```

It has an exact, nonempty 11-case negative corpus, checks every declared target
selection, requires diagnostic identity, rejects native C output, preserves
previous executable/generated bytes, and requires rejection before a job starts.
It then executes native debug/release List output against the **required existing
`lists.expected` file**, generates Enfusion sources and checks the proof example.
It retains command logs and compiler/source hashes and fails if inputs change.
It does not launch Workbench or claim engine execution.

An initial CLI gate correctly found that placing the check only in native lint
was too late: `build` created its job before cgen rejected the source. The retained
failed receipt is `build/storage-admission-qtxon43p/results.json`. Driver/direct
build integration must close that gap; the no-job assertion must not be weakened.
The final integrated receipt belongs in the central delivery evidence record.

Independent source review identified the index-read lifetime case, which is now
covered by a negative growth fixture and positive split-evaluation fixture. The
remaining bounded classifier/copy/interval source review found no further
material issue in the admitted subset. That review is not a proof of the
unimplemented ownership features.

## Remaining gates and migration

This checkpoint deliberately retains native List allocation without complete
automatic scope-exit cleanup. `clear()` resets logical length; it does not free
the allocation. Successful semantic admission, passing UBSan and matching output
do not establish bounded retained storage across repeated lifecycles. R0 and the
complete owned-storage milestone remain incomplete.

Before broad owning storage is admitted, implement and verify recursive copies,
ownership transfer, overlapping replacement, cleanup on normal/early exits,
nested element replacement, storage-generation identity and invalidation through
callees. Then extend the reference/IR coverage and lifecycle tests rather than
removing these checks speculatively. Keep engine entity/widget/resource identity
under explicit retention and validity bindings; a Beryl value copy must never
implicitly duplicate a live engine object.

For a rejected program, choose a single owner and an admitted read-only/mutable
borrow, use a plain fixed representation on a supporting target, or retain a
reviewed external adapter until the required lowering exists. Separating
mutation from selection makes evaluation order explicit. None of this guidance
is an automatic behavior-preserving rewrite for every source expression.
