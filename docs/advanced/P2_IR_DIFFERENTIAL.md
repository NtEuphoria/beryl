# P2 — Experimental native IR differential tests

This checkpoint connects the independently evaluated schema-4 IR to the normal
C11 build, process and evidence infrastructure. It is an explicit, instrumented
test capability. It does not release IR for production programs or select IR
automatically. See the delivery state for the installed compiler and exact
receipts; a source implementation alone is not an installed capability.

## Supported workflow

```text
beryl test --backend differential --lowering ir --clang <clang> <sources.be>...
beryl test --backend differential --lowering ir --release --save-native-evidence <sources.be>...
```

The shared frontend resolves names and checks types, access, ownership, taint
and the native profile. IR admission then checks the complete source set,
including unsupported declarations in unused functions. The IR verifier checks
the resulting tables before emission or source-table access. No native job is
created for a failed IR admission. The receipt distinguishes this admission
from attempting the independent AST reference.

For an admitted successful reference execution, the native driver emits IR C,
compiles that exact source and executes the isolated executable. It compares
stdout and the complete ordered test/assert/print/f32-bit event stream. Both
compilation and execution must finish successfully; a file's existence is not
execution evidence. No generated output is promoted by this test operation.

`--release` selects the existing Clang O2 settings; the default is O0. Both paths
disable contraction and fast-math. `--opt off` retains its existing meaning:
it disables Beryl transformation families without altering Clang optimization.
No Beryl transformation family is released by this work.

## Admission and compatibility

The admitted categories are bool, signed i32, finite f32, initialized plain
records, fixed arrays, let/inout calls, supported scalar output, structured
control flow, checked indexing and the existing numeric intrinsics. Assignment
and array iteration preserve independent logical values. Arguments, record
fields, array elements and destination projections follow explicit IR order.
Immediate `defer` remains immediate.

The existing limits in [P2_IR_ARRAYS.md](P2_IR_ARRAYS.md) still apply. Source
strings as program values, owning storage, engine objects, set/sink,
uninitialized locals, optional/error payloads, arbitrary numeric widths,
aggregate printing and unsupported intrinsics remain outside this profile.

These command combinations remain unavailable or invalid before execution:

- Production `build --lowering ir` and `run --lowering ir`.
- Standalone native `test --lowering ir` without the differential backend.
- Enfusion IR lowering and the AST-reference backend with an IR override.
- Observed output roots through `--observe-root`; this emitter has no registered
  root-snapshot implementation.
- Output/target overrides incompatible with existing differential tests.

`--lowering auto` still selects AST. Unsupported explicit IR never falls back
to AST. The capability registry reports `ir.differential_tests` as experimental
and keeps production `ir.codegen` unavailable. The former does not satisfy the
delivery program's R1 production-backend gate.

## Failure observations

The existing differential expectation syntax is also supported:

```text
--expect-source-trap overflow@<file_id>:<byte_offset>
--expect-source-trap division_by_zero@<file_id>:<byte_offset>
--expect-source-trap bounds@<file_id>:<byte_offset>
```

An expected trap is successful verification of a trapping program, not a
successful program return. The AST reference must report the expected kind and
first source site with a complete observation prefix and no failed assertion.
The emitted program must then have a nonzero completed process exit, identical
stdout and the exact complete prefix ending in the same certified source-trap
record. Later extra JSON events are rejected. Ordinary traps still fail tests.

F32 nonfinite results, invalid float casts, invalid shift widths, reference
budgets and generated test budgets cannot become certified source traps. Native
guards use incomplete domain/resource failure paths. Startup failure, timeout,
cancellation, missing logs, compilation failure and partial observations cannot
satisfy a source-trap expectation. Compiler identity and evidence-stage timeout
or cancellation also propagate to the outer differential result.

The observation boundary is explicit: event/stdout parity does not establish
the absence of every hidden memory write. The package matrix and CLI gate use
deliberate observable mutations; arbitrary registered roots remain a separate
prerequisite for future checked-loop optimization.

## Resource and numeric domain

The generated test harness uses at most one million charged IR instructions
and call depth 128. It admits at most 64 KiB of estimated declared objects per
function. That estimate is not a proof of Clang's stack layout or total stack
consumption. The test emitter also limits generated C output.

The AST and IR evaluators have their own cumulative allocation, output, depth
and step accounting. These differ from generated C. `--max-steps`, `--max-bytes`
and `--max-call-depth` control the reference side; they do not silently redefine
the fixed native test profile. Receipts list the native profile separately.
General resource equivalence, physical allocator behavior and performance are
not claimed.

F32 constants are reconstructed from exact bits, and operations preserve
binary32 rounding and expression grouping. The generated source rejects
fast-math and incompatible float evaluation. Numeric exits outside the admitted
finite domain are retained as failures, not widened into parity by tolerance.

## Identities and shared implementation

`src/ir/c_emit.[ch]` contains the test emitter admitted by the driver. The
repository package under `tools/beryl-ir-experiments` preserves the earlier
independent experiment as an explicitly identified historical overlay. It is
not a second production backend or an installed orchestration path.

The differential receipt adds requested and selected lowering, whether the AST
reference was attempted, the IR schema, source-manifest hash, generated-C hash,
admission, budgets, observation coverage and production/performance exclusions.
It retains existing source/compiler/artifact identities and result fields.
The source-manifest hash identifies captured source bytes; it is not labeled
as a serialization hash of all IR tables.

The native build boundary verifies the IR first, then requires its ordered
source paths and bytes to match the normal build snapshot. An IR input cannot
silently pass through an AST build boundary. Optional native evidence retains
the exact generated C, runtime hashes, executable hash, selected Clang identity,
arguments, LLVM output and assembly with `selected_lowering: ir`. Instrumented
machine output is not a performance measurement.

## Verification and remaining gates

Run `scripts/verify-ir-differential.py` with explicit `--beryl` and `--clang`.
Its isolated checks cover ordered aggregates and scalar values, O0/O2 native
evidence, the complete eight-test PID corpus, certified trap categories and
prefixes, unsupported inputs, incompatible options, unchanged auto lowering,
startup failure, native evidence timeout and executed native mutants.

The unit suite additionally verifies AST-storage independence, deterministic
emission, malformed-table rejection, output bounds, source-identity mismatch
and incompatible build boundaries. The independent package matrix remains a
separate gate across analytical fixtures, AST reference, IR evaluation and
AST/IR C at O0/O2 with UBSan. Its receipt reader now requires exactly four named
process rows and six admission rejections for every case; missing or duplicated
rows cannot silently pass.

Production entry points, source-map artifacts, observed-root snapshots, native
ABI release, Enfusion IR emission, set/sink and independently verified owned
storage remain open. Later work must preserve this reference/evidence path while
adding each admitted category. No optimization or Rust advantage is established
by this correctness checkpoint.
