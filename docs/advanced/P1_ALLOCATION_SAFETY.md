# P1 allocation arithmetic and capacity safety

Status: implemented bounded compiler/runtime checkpoint; focused verification passed.
The integrated compiler gate and active installation are separate operations.

## Objective and scope

Prevent allocator requests and capacity calculations from wrapping before the
allocator sees them. Preserve live collection state until a replacement
allocation succeeds. Preserve the existing aborting allocation-failure policy.

This packet covers the compiler arena, compiler vectors, compiler string
builder/interner/map, and generated native `List<T>` growth. It does not establish
complete owning-value semantics, recursive collection cleanup, parser resource
bounds, or a whole-compiler memory-safety proof.

## Implemented behavior

### Checked size arithmetic

`src/common/checked_size.h` provides internal C11 inline helpers:

| Helper | Contract |
| --- | --- |
| `checked_size_add` | Rejects addition greater than `SIZE_MAX`. |
| `checked_size_mul` | Rejects multiplication greater than `SIZE_MAX`; zero multiplication succeeds. |
| `checked_size_align` | Requires nonzero power-of-two alignment and a representable rounded result. |
| `checked_size_grow` | Grows geometrically to at least the need, saturating at an explicit element limit. |
| `checked_size_grow_power2` | Doubles a power-of-two table capacity; rejects growth beyond the limit instead of producing a non-power-of-two capacity. |

Each helper leaves its output argument unchanged on rejection. These helpers
report arithmetic feasibility; they do not allocate or predict available RAM.
Their internal callers supply valid output pointers.

### Arena

- Header plus payload allocation is checked before `malloc`.
- `ARENA_ARRAY` now calls `arena_calloc_array`, checking count times element size
  before allocation. The macro no longer multiplies first and passes a wrapped
  byte count to the arena.
- Allocation padding, end offset, requested capacity, total used bytes, and
  total reserved bytes are checked before committing arena state.
- Alignment is calculated from the actual payload address. Aligning only the
  offset had assumed that the payload base already met the requested alignment.
  The tests include actual addresses aligned up to 512 bytes after odd-sized
  allocations and across small block boundaries.
- Alignment zero retains its existing alias for alignment one. Non-power-of-two
  alignments abort with an invalid-alignment message.
- Zero-size allocation retains its existing one-byte physical allocation and
  accounting behavior. Zero-count array allocation therefore returns zeroed
  storage without attempting `count * element` allocation.

The arena still frees its blocks as a group. It does not return allocation
failures to the caller, introduce a new lifetime, or recover from exhaustion.

### Compiler vectors

- `vec_push_need_` checks `len <= cap` and rejects `len == UINT32_MAX` before
  evaluating the macro's length increment. Guarding reserve alone would miss
  the old macro's wrapped `len + 1`.
- `vec_reserve_` accepts a `size_t` need, preventing an oversized caller need
  from first narrowing to `uint32_t`.
- Element size must be nonzero; live length must fit the current capacity.
- Capacity is bounded by `min(UINT32_MAX, SIZE_MAX / element_size)`.
- Both allocation bytes and live-copy bytes are checked.
- New allocation and prefix copying complete before pointer/capacity updates.
  Old arena storage remains retained until the arena is freed, as before.

The macro continues to assume a stable vector lvalue. This work does not make
arbitrary side-effecting macro arguments safe.

### Compiler strings and hash tables

- `str_from` rejects lengths that cannot be represented by the compiler's
  `uint32_t` string length instead of silently narrowing `strlen`.
- NUL-terminated string copies check their extra byte.
- `str_slice` clamps with subtraction, avoiding `start + len` wrap. Empty null
  slices no longer perform null-pointer arithmetic.
- String-builder reserve checks live length plus the requested append and
  bounds capacity to `UINT32_MAX`. Formatted append includes its temporary
  terminating byte in that check.
- String-builder pointer/capacity updates follow successful allocation and
  prefix copying.
- Compiler map and interner capacity growth preserves the power-of-two mask
  invariant. Growth rejects unrepresentable capacity or byte size.
- Load-factor multiplication is performed in `uint64_t`; multiplying `uint32_t`
  counts by ten or seven can no longer wrap in those decisions.

Map key lookup, interning identity, growth policy at ordinary sizes, and map
enumeration behavior are otherwise retained. This is the compiler's internal
map; it does not add a native Beryl `Map` implementation.

### Native `List<T>`

The runtime's inline `be_list_growth_plan` is a pure planner. It accepts current
signed length/capacity and element size, returning proposed capacity and byte
count without allocating. It rejects invalid signed lengths/capacities,
zero-size elements, and requests exceeding either the signed length domain or
the byte-size domain. Its outputs remain unchanged on rejection.

The capacity limit is:

```text
min(INT32_MAX, floor(SIZE_MAX / sizeof(T)))
```

Generated push retains the existing native descriptor shape: element pointer,
`int32_t len`, `int32_t cap`. At a full list it plans growth, obtains a temporary
replacement pointer, and only then commits `data` and `cap`. Length increments
after the new element is stored. A valid descriptor with length below capacity
cannot increment past `INT32_MAX`; a full descriptor at the limit is rejected.

The generated helper assumes a valid compiler-created List descriptor. It does
not validate arbitrary corrupted pointers or foreign fabricated descriptors.
The pure planner separately rejects invalid length/capacity inputs in tests.

## Failure categories and compatibility

Arithmetic infeasibility in an allocation request is a **resource failure**, not
a Beryl checked-arithmetic source trap. Compiler-side diagnostics are direct
fatal allocator messages. Native capacity rejection calls
`beryl_allocation_size_failure`; actual `realloc` failure retains the existing
out-of-memory message and abort behavior.

Neither path emits the test-only `source_trap` terminal event. Consequently an
allocation failure cannot satisfy an expected-overflow source-trap comparison.
There is no unwinding, rollback of earlier source actions, or newly recoverable
allocation result. Descriptor preservation here means the growth operation has
not published a new pointer/capacity before allocation returns successfully.

This work deliberately leaves ordinary List copying, recursive ownership,
destruction, borrowing, and aliasing contracts for their separate safety/IR
gates. Successful allocation tests do not make those paths ownership-safe.

No model API, LLVM rewrite, optimization flag, or installed compiler change is
part of this packet.

## Verification evidence

Final focused evidence at this checkpoint:

```text
build/p1-allocation-butmorsr/results.json
build/p1-allocation-butmorsr/inputs/
build/p1_allocation_check.py
build/allocation-x6qa8ztf/results.json
scripts/verify-allocation.py
```

The report records every input hash, toolchain identity, compiler invocation,
exit status, stdout, stderr, elapsed duration, and generated List source hash.
The snapshot starts from:

```text
build/delivery-baseline-b742d5aaf916468485134457aa2af2bf/inputs
```

It overlays only the explicitly recorded owned allocation files. This avoids
using partially edited semantic work from another workstream. It is a bounded
baseline-plus-patch experiment, **not evidence for the current full working
tree**. The owned files were hashed before and after copying to reject a mixed
capture. Root must run the integrated immutable foundation gate separately.

The focused compiler SHA-256 is:

```text
7c8cd42fa17ea4c4865e2e2bb27f64542a83065fafda78c69424c12eaeace2ba
```

The emitted native List fixture SHA-256 is:

```text
50aedf9268380eb4fd62c50ac2a0156e2102a28b4b62c2c3ecccf060e6bedf6a
```

Results at both O0 and O2, with UBSan and failure on its first report:

- 27 common/allocation unit cases and 865 checks per build.
- Twenty resource-rejection or injected allocator-failure subprocess probes
  per build. Tests do not request enormous allocations; oversized paths are
  intercepted before an allocator call, or exercised through pure planners.
- Generated native List grows through 10,000 inserted values and preserves
  every value.
- Injected List, vector, and string-builder allocation failures inspect the
  old descriptor and live prefix from inside the allocator before it returns
  failure. The expected old state is still present.
- Capacity-limit and allocation failures do not produce a source-trap terminal.
- Small-domain growth properties check all current-capacity/need combinations
  for limits from zero through 64, including monotonicity and bounded output.

The subprocess harness uses test-build-only allocator substitution. Production
sources expose no allocator-failure injection switch. Sanitizer evidence is for
the tested Windows x64 Clang environment; this is not a 32-bit execution claim.

The portable `scripts/verify-allocation.py` replay also passed both optimization
levels with 27 cases/865 checks and the twenty failure probes. It accepts
required `--beryl` and `--clang` paths, optional `--source-root`, `--runtime-dir`,
and `--output-root`. It snapshots the relevant sources and compiler binary,
rejects a changed capture, and retains a result for subprocess startup failure,
timeout, or cancellation instead of treating missing output as success. The
caller must separately establish that a supplied compiler belongs to the
intended source baseline; the script records its hash without inventing that
relationship.

## Integration requirements and remaining gates

1. Register `run_allocation_tests()` from `tests/unit/test_allocation.c` in the
   common unit registry. It uses runtime header inline planning only; ordinary
   compiler unit linking does not need `runtime/beryl_rt.c` added.
2. Regenerate `src/back/runtime_embed.h` from the runtime source of truth before
   native driver build/run verification. This packet's emit-C probes compile
   against the copied runtime source directly.
3. Run the complete immutable foundation and applicable driver regressions with
   the concurrent semantic changes integrated. Preserve the previous installed
   compiler until those gates pass.
4. Include `scripts/verify-allocation.py` in the checkpoint regression gate.
   The original build artifact remains the exact focused-baseline experiment.
5. Complete source/parser/semantic work budgets and review direct byte arithmetic
   at call sites outside these primitives. An already-wrapped expression passed
   to `arena_alloc` cannot be reconstructed by the allocator.
6. Keep owned-storage correctness, cleanup, invalidating-borrow checks, native
   IR emission, and performance adoption separately gated.

Ordinary filesystem source reads currently have a 64 MiB bound. That bound is
useful evidence for file-fed paths; it does not bound every internal API, total
module count, parser depth, or compiler work across the whole project.
