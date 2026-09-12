# Experimental P2 IR-to-C test emitter

This repository-owned package preserves an isolated, verified experiment. It
does not add a compiler command, production backend or installed tool. Ordinary
AST backends and public `--lowering ir` availability are unchanged. The emitter
and probe retain the exact bytes of the completed private checkpoint below.

## Interface and admission

`src/ir/c_emit.[ch]` adds `ir_emit_c(Arena *, const IrProgram *, IrCOpts)`.
It verifies schema 4 before producing C. The result contains `ok`, complete
source on success, an originating span and an explanatory rejection reason.
Failure never returns a usable partial C source. The API builds a standalone
test executable, not a production entry point, FFI or exported-class ABI.

The emitter accepts the existing verified bool/i32/finite-f32, plain record,
fixed-array, let/inout, expanded-default, structured-control subset. It retains
the IR admission exclusions: owned containers, strings, f64, set/sink, globals,
external/engine objects, aggregate comparisons and unsupported alias intervals.
Unsupported opcodes/types/indices/effects fail the existing independent verifier.
There is no AST node or type pointer in the completed IR or emitter input.

Each instruction becomes an ordered C statement. Values use named typed
temporaries. Records and arrays are inline C structs; assignments, argument
captures and returns therefore copy logical plain values. Let aggregates borrow
const typed pointers when IR explicitly captures a place; inout parameters use
mutable typed pointers. The emitter does not add `restrict` or a new allocation
runtime. Static projections are formed lazily; dynamic projections cannot form
an address until their explicit bounds instruction succeeds. Bounds checks use
logical length, including zero. Zero-length arrays contain a byte of physical
padding with no element member; generated code never reads or reports padding.

Structured loop labels keep `continue` on the loop's step path and `break` on
its exit. Returns copy their value through C's return convention. Immediate
`defer` is already represented in the verified instruction order and remains
immediate. All call arguments are evaluated/captured before the C call itself.

## Numeric and failure contract

Integer checked arithmetic and bounds use the current runtime's traced helpers,
including source-file ID and exact source byte offset. Division by zero,
overflow and bounds are the only certified terminal source-trap categories.
`INT32_MIN % -1` remains zero. Wrapping and bitwise conversions use explicit
unsigned bits and an in-range signed reconstruction; shifts check width before
shifting and explicitly implement sign extension.

F32 constants are reconstructed from exact bits. Every arithmetic result is
rounded through binary32 storage and checked for finiteness. Float-to-i32 casts
check finiteness and the exact admitted range before executing the C cast.
Min/max/clamp preserve strict comparisons and selected operands, including
signed-zero ties. Generated code rejects fast-math/finite-math-only and requires
binary32 evaluation (`FLT_EVAL_METHOD == 0`); tests also explicitly disable
contraction and fast-math. No tolerance is widened to pass this matrix.

Nonfinite results, out-of-range float casts and invalid shift widths remain
outside the admitted finite execution domain. Their generated failure path
flushes completed output but never emits a complete source-trap record. These
cases are compared against the two interpreters and IR-C only. Current ordinary
AST-C has a wider numeric domain; no native AST parity is claimed there.

The test harness limits executed instructions to one million and call depth to
128, using uncertified failure paths. It does not mirror the IR evaluator's
64 MiB cumulative frame allocation/output budgets or dynamic region-depth
counter. The declared-object storage estimate is
capped at 64 KiB per function. This is not a proof of Clang's physical stack
layout, stack-exhaustion behavior, interpreter allocation accounting or general
resource equivalence. Process startup, compilation, timeout and cancellation
are recorded separately and cannot satisfy expected-source-trap checks.

## Observation and provenance scope

The matrix compares stdout and the ordered JSON event stream byte for byte:
test boundaries, print events, f32 bits, assertions and the first certified
source failure. It preserves raw stderr separately. Human assertion labels may
use the copied qualified IR identity rather than the original test label; raw
diagnostic wording is not an equality claim. This prototype has no registered
root snapshot extension, source-map artifact format or hidden-write completeness
claim. A prefix proves the recorded observations, not all unobserved memory.

Source paths, source manifest hashes and bounded source spans come from the
copied IR source manifest. Source line lookup uses sorted requested offsets and
one forward scan per source, rather than rescanning the whole file per emitted
instruction. Generated names are deterministic table indices. No project code,
shell script or external model API is evaluated while emitting C.

## Reproducible matrix

Run `check.py` with explicit `--clang` and `--output` paths. Optional `--baseline`
selects a source root containing `src`, `runtime`, `packages` and `tests`; it
defaults to this package's checkout. The source root must match schema 4 and the
fixed analytical fixture set. The output directory must already exist. Example
from the repository root (substitute installed Python and Clang paths):

```powershell
& $python -I tools/beryl-ir-experiments/check.py --clang $clang --output build
```

To reproduce against the captured post-repair source root instead of current
working files, add `--baseline build/delivery-order-final-oopz_pd3`. That capture
is a local evidence artifact and is not guaranteed to exist in a fresh checkout.
The checker prints the unique result directory first and `results.json` last.
It requires Python assertions enabled and rejects `-O`/`-OO` invocations.

Before compiling, the checker hashes the four complete source trees, copies
them, and compares both the copied files and a fresh source inventory with the
first inventory. A changed, missing or newly added file aborts capture. It then
checks the experimental overlays before, during and after their copy. This
detects observed changes; it is not a filesystem transaction or protection
against an adversarial writer restoring the original bytes between reads.
The receipt records these inventories, every final compiled input and toolchain
identity. Builds and executions use distinct case directories. Optional
`--ast-backend-overlay` identifies and
hashes a corrected AST C backend explicitly; it never silently mixes source
versions. The fixed analytical fixture-name set must match before a run begins.
Negative `--limit` values are rejected. Every positive `--limit` selects a
development subset, reports `pilot_passed` with `gate_complete: false`, and
cannot satisfy the complete gate.

The probe parses/resolves/checks the source, emits AST C, runs the independent
AST reference, lowers to IR, then frees the entire AST arena before IR emission
and IR evaluation. The matrix compiles both emitted artifacts with Clang O0 and
O2 plus UBSan and contraction disabled. Existing analytical IR fixtures and the
complete captured SPARKOS PID package are consumed without duplicating PID
implementation logic. Exact subprocess execution goes through the existing
`process_run` infrastructure; native results require successful launch and
completed execution, not merely the existence of an executable.

Negative evidence includes malformed IR, output limits, invalid test identity,
fast-math rejection, oversized declared storage, finite-domain guards, budgets,
and generated-C mutants for missing observations, wrong arithmetic, missing
terminal traps, wrong source sites, extra array writes and removed finite checks.
Field defaults retain the frontend's existing constant-expression requirement:
positive tests use admitted constant defaults and verify copied changed values;
effectful `mark()` defaults are explicit BE0501 admission failures. An initial
attempt to execute those inadmissible defaults failed honestly and is retained.
Timeout or failed compilation is an experiment failure, not a killed semantic
mutant or a passing source trap.

## Completed private gate and remaining work

The original private captured matrix is `../../build/ir-c-f53bg9ro/results.json` (SHA256
`24a1d63a3c788f78a7c6c08f3e114e560b03b7f5f76a6714d220f89fa6628a45`).
It reports `passed` and `gate_complete: true` for 36 cases. All 36 agree across
the AST reference, independent IR evaluator, and IR-C O0/O2 builds with UBSan.
The 31 admitted native-comparison cases also agree with AST-C O0/O2. Three
numeric-domain exits and two budget exits are explicitly outside AST-C parity.
The complete PID contributes eight tests and 2,206 assertions; its stdout and
ordered event bytes match exactly. Six generated-C mutants are detected; six
malformed/configuration checks across each case give 216 rejection instances.
Fast-math, oversized declared storage and two effectful field-default programs
are rejected. The separately executed prefix run reports `pilot_passed` with
`gate_complete: false`; negative selection exits before creating a build.

The C backend overlay is the captured root correction at
`../../build/delivery-order-final-oopz_pd3/src/back/c_backend.c`, SHA256
`969a9fb849683ec0296a9335d1d84bf29d7733a9bd323ffb15d918e020854959`.
The remaining baseline is the verified schema-4 capture at
`../../build/p2-ir-sst1mll7/inputs`. Every compiled input and private overlay is hashed in
the final receipt. Evidence is from Windows x86_64 and the recorded LLVM-MinGW
toolchain; this is not cross-platform certification.

A prior matrix exposed the AST record-literal ordering bug: the source
`R{b: mark(2), a: mark(1)}` printed `1, 2` through AST-C but `2, 1` through both
interpreters and IR-C. The earlier `ir-c-he2_0jyc` report correctly failed its
overall AST parity gate while completing IR/PID and mutation evidence. The
`ir-c-ormwvqcx` report then passed the corrected written-order case but failed
the invalid effectful-default fixture assumption. Both failures remain retained;
the final gate uses valid constant defaults plus explicit BE0501 negatives.

An independent source review found no additional emitter correctness defect in
the admitted subset. It prompted the exact-corpus/pilot reporting guards and
explicit separation of resource policies. The separate bounded native intrinsic
audit is retained at `../../build/intrinsic-order-sg38zsaa/results.json`; it exposed List
and vector argument-capture defects in the older combined compiler. Root owns
those shared emitter corrections and their native/engine verification.

Even a successful private native matrix does not release public IR lowering:
production entry points, complete native evidence integration, root snapshots,
Enfusion IR emission, remaining access modes and owned-storage semantics keep
their separate gates. No performance improvement is measured or claimed by this
instrumented test emitter.
