# Beryl compiler review and implementation handoff

Prepared by Codex for the Beryl project owner and Claude Code.

Review date: September 4–5, 2026, America/New_York.

Repository: `C:/Users/moham/Desktop/beryl`

Recorded HEAD: `e151db1653063fe1cefd4c20146392d1606739ff`

**Purpose:** turn a comprehensive read-only review into a prioritized, verifiable work queue. This report preserves the owner's ambition: a language capable of competing with Rust on performance, security, speed of development, and systems-programming usefulness.

## Instructions for Claude Code

Read this report in full, then inspect the current repository and its applicable instructions before implementing. Source line numbers below describe the reviewed snapshot and will move as files change. File paths are repository-relative.

1. Preserve the owner's existing changes. The reviewed checkout was dirty; do not reset or overwrite it to obtain a clean baseline.
2. Reproduce each finding against current source before treating it as a confirmed runtime result. Most findings are established by source inspection, not by executing a newly built compiler.
3. Start with the build blocker, then ownership/memory safety and semantic correctness. Do not prioritize adding syntax or optimizing benchmarks over these issues.
4. Use small, coherent changes. Add meaningful regression tests that fail before the fix and exercise the resulting behavior. For a language-semantics decision, document the rule before expanding its implementation.
5. Do not silently redefine a promised feature to match a broken implementation. Either implement the intended behavior, explicitly reject the unsupported case, or document an intentional language change and its rationale.
6. Do not mark a finding resolved solely because the old test suite passes. Apply the acceptance criteria for that finding and run appropriate fresh-build checks.
7. Record outcomes by finding ID: reproduced, fixed, verified, deferred, or not reproduced. Include exact commands and evidence. Explain any disagreement with this report.
8. Do not infer permission to delete handwritten mod implementations, deploy a mod, publish releases, or remove unrelated files from the roadmap's experimental suggestions. Prepare and validate those changes within the owner's current instructions.

The suggested implementation sequence appears near the end. The report is a work specification, not proof that every proposed reproduction has already been executed.

## Assessment and review scope

Beryl has a coherent design and a substantial compiler prototype. The compiler is small enough to understand and repair. However, the current implementation does not yet deliver its advertised memory-safety guarantees, and the repository does not establish a performance advantage over Rust.

The review covered first-party compiler source and headers, the runtime and embedded runtime, unit tests, end-to-end fixtures, examples, scripts, documentation, the original design and implementation plan, the Markdown and HTML roadmaps, and the working-tree changes. Git internals, binary contents, and unrelated Blender dependencies were excluded from the source review.

The review itself changed no files. Creating this report was separately requested afterward.

### Verification actually performed

- The existing `build/run_tests.exe` ran successfully: **204 cases and 931 checks passed**.
- That executable was last modified at **2026-09-04 18:24:53** local time.
- `build/beryl.exe` was last modified at **2026-09-04 20:13:44** local time.
- `src/back/c_backend.c` was last modified at **2026-09-04 20:28:22** local time.
- Therefore, the existing executable results do **not** validate the current source checkout.
- No fresh compiler build, generated-code execution suite, benchmark rerun, or Workbench build was performed during the read-only review.
- Historical Workbench success is documented in the repository; it was not independently reproduced in this review.

### Existing changes to preserve

At review and report creation, these 12 files were modified, totaling 795 insertions and 13 deletions:

```text
runtime/beryl_rt.h
src/back/c_backend.c
src/back/enforce_backend.c
src/back/enforce_expr.c
src/back/enforce_int.h
src/back/runtime_embed.h
src/parse/ast.h
src/sema/check_expr.c
src/sema/intrinsic.c
src/sema/intrinsic.h
src/sema/types.c
src/sema/types.h
```

Untracked items included `.blender-toolkit/`, `_probe.be`, and `kind)`. The source changes chiefly concern vector operations and expression-emission memoization. Some immediate defects below appear specific to this unfinished work.

## Architecture and intended language model

The main idea is **mutable value semantics with second-class references**: values have owners; borrows are confined to function boundaries rather than freely stored and returned. This can reduce the need for lifetime annotations, provided copying, mutation, ownership transfer, and destruction obey one consistent model.

| Area | Reviewed implementation |
|---|---|
| Compiler | C11, arena allocation, interned strings/types, small internal containers |
| Lexing and parsing | Newline statement termination; recursive-descent items/statements and Pratt expressions |
| Analysis | Resolution, type checking, constant evaluation, ownership analysis, security lints |
| Native backend | Typed AST → C11 → Clang |
| Enfusion backend | Typed AST → EnforceScript classes and functions |
| Runtime | Arithmetic and bounds traps, printing, tests, allocation helpers, vector operations |
| Tooling | Checking, building, running, testing, formatting, auditing, project scaffolding |

The calling conventions are intended to distinguish read access (`let`), exclusive mutation (`inout`), ownership transfer (`sink`), and initialization by a callee (`set`). Their exact semantics must govern intrinsics as well as ordinary functions.

Preserve the useful foundations: a readable compiler, explicit parameter conventions, function-local inference, readable generated output, and the ability to test Enfusion logic natively.

The implemented language is substantially smaller than the designed language. User-defined generics, traits, ownership containers such as `Box`/`Pool`/`Handle`, destruction, a standard library, package dependencies, concurrency, and broad platform support remain absent or incomplete. Basic functions, control flow, structs, methods, arrays, lists, error propagation, diagnostics, and two backends exist, but some combinations are unsound or not emitted correctly.

## Priority and evidence conventions

- **P0 — foundation blocker:** blocks a trustworthy build or violates core memory/ownership guarantees. This is project-local prioritization, not a CVSS rating.
- **P1 — correctness/security blocker:** can change behavior, undermine protection, corrupt source, or invalidate verification.
- **P2 — completeness/tooling/strategy:** necessary for real use, credible claims, or maintainability.
- **Source finding:** a concrete problematic path was identified in the reviewed source; fresh reproduction is still required.
- **Documented gap:** the repository already acknowledges the limitation; the review assessed its implications.
- **Design recommendation:** a proposed direction, not an implemented feature or proven performance result.

## Findings and acceptance criteria

### BR-01 — Repair the current native codegen build and memoization setup

**Priority:** P0. **Evidence:** source finding in current working-tree changes.

**Locations:** `src/back/c_backend.c:118`, `:666`, `:1228`; `src/back/enforce_expr.c:268`; `src/common/map.c`.

`gen_expr` calls `ef_ptr_key`, an EnforceScript helper not declared in the native translation unit, while a native `ptr_key` helper exists. Separately, `cgen_program` initializes `g.emitted` but never initializes the newly added `g.memo`. Fixing only the helper name leaves a null map access during expression generation.

**Work:** repair the helper reference and initialization. Review the lifetime and scope of the memoization strategy itself. Caching expression text must not reuse temporary names across incompatible scopes or suppress effects at distinct evaluation sites. Prefer evaluating generator calls once into local `Str` values rather than relying on a broad cache to compensate for the `S(...)` macro evaluating its argument twice.

**Acceptance:**

- Fresh compiler and test builds pass the configured warning-as-error flags.
- Native emission succeeds for ordinary expressions and `_probe.be`-style `try` expressions.
- Add effect-counting cases around nested expressions and repeated/default expressions as applicable; each executes the language-defined number of times.
- No generated temporary is referenced outside its defining scope.

### BR-02 — Define and implement sound list copy, move, and destruction semantics

**Priority:** P0. **Evidence:** source finding.

**Locations:** `src/back/c_backend.c:229`, `:979`; `runtime/beryl_rt.c:27`; `src/sema/types.c:196`; `src/sema/ownership.c`.

Native lists contain a pointer, length, and capacity. Ordinary initialization/assignment copies this structure. Two values can therefore share one allocation. Mutation through one changes the other, and growth through one can invalidate the other's pointer if `realloc` moves the allocation. Ordinary Beryl code can reach a use-after-free. Structs containing lists inherit the problem.

`beryl_release` exists in the runtime but generated scope-exit destruction does not use it. List allocations leak when owners leave scope. `ty_is_copy` exists but is not integrated into a complete copy/move/drop discipline.

**Work:** choose and document whether owning containers are copied deeply, use sound copy-on-write, or transfer ownership and require explicit cloning. Implement the rule for locals, assignment, parameters, returns, nested aggregates, and container elements. Add correct cleanup on all exits. Do not add freeing to the current shallow-copy representation without first repairing ownership; that would introduce double-free hazards.

**Acceptance:**

- Tests distinguish independent values from intentional ownership transfer.
- Growth after copying/transferring a list cannot leave an accessible stale pointer.
- Nested structs/lists obey the same semantics.
- Passing a value through a function cannot secretly invalidate the caller's allocation.
- Normal scope exits, early returns, loop exits, and error propagation release owned allocations exactly once according to the specified model.
- Execute suitable allocation accounting and ASan checks; use leak checking where supported.

### BR-03 — Repair definite initialization and control-flow analysis

**Priority:** P0. **Evidence:** source finding.

**Locations:** `src/sema/ownership.c:255`, `:400`, `:457`, `:493`; native uninitialized declarations at `src/back/c_backend.c:986`.

The current checker can accept reads of uninitialized values:

- A whole uninitialized variable passed as `inout` is marked initialized, even though the callee may read it before writing.
- Compound assignment can mark a whole binding initialized without checking its previous value.
- Loop analysis can retain initialization performed only in the body even when the loop executes zero times.
- `break` and `continue` do not have the flow-state treatment needed for sound results.
- Short-circuit and fallback expressions are walked as though conditional effects were unconditional.

An illustrative source-level case to reproduce inside a valid function is:

```beryl
var x: i32
while false {
    x = 1
}
println(x)
```

**Work:** separate `inout`'s requirement for an initialized input from `set`'s obligation to initialize an output. Treat compound assignment as a read plus write. Merge loop exits with the zero-iteration path where applicable. Model return/break/continue and conditional expression effects explicitly. Audit traversal of field/index bases and index expressions for nested effects and moves.

**Acceptance:**

- The example above is rejected as a possible uninitialized read.
- Uninitialized `inout` input and `x += 1` on an uninitialized variable are rejected.
- `set` is accepted only when the callee initializes every returning path.
- Tests cover branches, zero/multiple loop iterations, break/continue, early return, short-circuit operators, `orelse`, and `catch`.
- Correctly initialized programs remain accepted; fixing false negatives must not simply reject all useful control flow.

### BR-04 — Make exclusivity complete before promising non-aliasing to C

**Priority:** P0. **Evidence:** source finding.

**Locations:** `src/sema/ownership.c:75`, `:209`, `:255`, `:299`; `src/back/c_backend.c:1137`.

Call access collection silently stops after 17 entries. Field paths truncate after six stored fields in a way that can discard the outer path needed to recognize overlap. List mutation intrinsics do not consistently apply ordinary exclusive receiver checks. These gaps undermine the `restrict` annotations emitted for `inout`/`set` pointers.

**Work:** remove silent analysis cutoffs, or conservatively reject/merge accesses when analysis reaches a documented limit. Give intrinsic receivers explicit access conventions. Ensure `sink` receivers and nested expression effects are handled. Remove aliasing annotations that are not yet justified rather than retaining an optimization based on a false guarantee.

**Acceptance:**

- Overlap in arguments beyond the seventeenth is diagnosed.
- Deep parent/child field overlap is diagnosed; genuinely disjoint fields remain usable.
- Mutating list operations through `let` locals/parameters are checked according to the specified immutable semantics.
- Aliasing-sensitive regressions behave identically in unoptimized and optimized output.
- Document the exact invariant that licenses each emitted `restrict` annotation.

### BR-05 — Preserve evaluation order and conditional execution during lowering

**Priority:** P1. **Evidence:** source finding.

**Locations:** `src/back/c_backend.c:349`, `:1013`; corresponding expression emission in `src/back/enforce_expr.c`.

Native `gen_binary` generates both operands before emitting `&&`/`||`. If generating the right operand emits temporary statements, they execute outside the intended short-circuit region. Compound assignment can emit a side-effecting target expression twice. Direct expression-to-text emission makes these mistakes easy to repeat.

**Work:** define evaluation order explicitly and lower effects into the correct control-flow region. Evaluate an assignment target's address/index once. Share semantic lowering where practical, without requiring both backends to use a low-level SSA representation.

**Acceptance:**

- `false && rhs` and `true || rhs` skip all RHS effects, including intrinsics that need temporaries and error propagation/fallback expressions.
- Side-effecting compound-assignment targets are evaluated once.
- Function arguments and nested calls follow the documented order.
- The same behavioral cases run correctly through both backends where supported.

### BR-06 — Reject or correctly emit every accepted operation

**Priority:** P1. **Evidence:** source finding.

**Locations:** `src/sema/check.c:156`; `src/sema/check_expr.c:748`; `src/back/c_backend.c:762`, `:1052`, and native profile lint.

- Type checking accepts list iteration, but native `ST_FOR` emission handles only ranges and arrays, allowing list loops to disappear.
- List bracket indexing is accepted, while native indexing emission uses an array-style representation rather than list storage.
- String comparisons and some aggregate comparisons are accepted but emitted as invalid C operators on structures.
- Some unsupported types are checked in signatures/fields but can escape profile checks through locals or expressions.
- Enum variant use and useful optional-value construction need conformance review; declarations and wrapper emission alone do not establish working features.

**Work:** inventory accepted typed AST operations against both emitters. Implement them or emit a Beryl diagnostic before code generation. Do not use placeholder zero values or omit statements as a fallback for unsupported source.

**Acceptance:** executing tests for list loops, bracket indexing, string comparisons, supported enum/optional operations, and profile rejection in locals as well as signatures. Every accepted supported case produces valid target code with specified behavior.

### BR-07 — Make generated names preserve binding identity

**Priority:** P1. **Evidence:** source finding.

**Locations:** `src/back/c_backend.c` name mangling, local naming, temporary naming, and `ST_LET` emission.

Source spelling is not a sufficient unique name. Shadowed bindings can cause a C initializer to read the newly declared variable instead of the resolved outer variable. C keyword suffixing can collide with source names that already end in an underscore. User identifiers can collide with generated temporaries; module path flattening can also collide.

**Work:** name locals from resolved binding IDs and items from unambiguous symbol identities. Reserve a collision-safe namespace for compiler temporaries. Apply target identifier rules to fields and other emitted identifiers too.

**Acceptance:** executing shadow-initializer tests; keyword-like names, names resembling temporaries, and colliding flattened module spellings produce correct, distinct target identifiers.

### BR-08 — Implement actual cleanup and error-handler semantics

**Priority:** P1; cleanup is also a dependency of BR-02. **Evidence:** source finding and documented gap.

**Locations:** `src/back/c_backend.c:839`, `:861`, `:1105`; corresponding Enfusion emission; `docs/ROADMAP.md` correctness ledger.

`defer` currently executes where written, not at scope exit. A `catch` handler that falls through can yield a fabricated zero value. Return checking also deserves review for bare returns from value-carrying error unions and error literals returned outside appropriate error-union contexts.

**Work:** define handler result/termination requirements and reject missing results rather than manufacturing them. Lower deferred actions and ownership cleanup across all exits with a specified order. Preserve meaningful error information or explicitly restrict the target's supported error model.

**Acceptance:** side-effect logs verify defer timing/order for normal exit, early return, break, continue, and `try`; missing handler values are diagnosed; valid error propagation preserves the specified success/error outcome.

### BR-09 — Eliminate arithmetic undefined behavior and enforce widths

**Priority:** P1. **Evidence:** source finding.

**Locations:** `runtime/beryl_rt.h:117`, `:145`; `src/sema/check_expr.c:167`; `src/sema/constfold.c` integer evaluation; native casts.

- Shift count checks do not make signed C left shift safe for negative/overflowing operands.
- Narrow unsigned operands can promote to signed `int`; `uint16_t` multiplication can overflow before narrowing, including in supposedly wrapping helpers.
- Integer literals are assigned types without consistently checking representability.
- Constant arithmetic checks 64-bit intermediates rather than consistently enforcing the declared Beryl width.
- Constant division/remainder lack the minimum-signed-value divided by `-1` guard; audit unary negation too.
- Float-to-integer casts need defined behavior for NaN, infinity, and out-of-range values instead of inheriting undefined C behavior.

**Work:** specify checked, wrapping, saturating, shift, and conversion semantics for every width. Use suitably wide unsigned intermediates or compiler intrinsics. Align constant evaluation with runtime behavior; do not narrow silently where the language promises checking.

**Acceptance:** a boundary matrix for all integer widths, signed minima/maxima, zero division, invalid shifts, narrow wrapping multiplication, literal ranges, and float conversion edge cases. Compare constant and runtime results/traps. Run the generated C under applicable UBSan checks.

### BR-10 — Make the two targets agree or reject the difference explicitly

**Priority:** P1. **Evidence:** source finding and documented target compromise.

**Locations:** `src/back/enforce_expr.c:252`, `:377`; `src/back/enforce_backend.c:485`; native equivalents.

Native ordinary integer arithmetic is checked while Enfusion generally uses engine operators. Enfusion saturation clamps after the arithmetic has already overflowed. Error unions lose their tags. Copy behavior for collection-containing values is not consistently equivalent.

**Work:** write a target semantics table. For the portable subset, implement equivalent observable behavior. Profile-gate operations that cannot preserve that contract. If an intentional target-specific behavior remains, make it visible in the language/tooling rather than relying on a footnote.

**Acceptance:** shared cases exercise integer boundaries, saturation, nested copies, errors, vectors, and effects on both targets. Record genuine engine execution separately from golden text checks or Workbench compilation. A native passing test must have a clearly defined predictive value for the portable subset.

### BR-11 — Tighten security lints and make security configuration fail closed

**Priority:** P1. **Evidence:** source finding; some limitations already documented.

**Locations:** `src/sema/taint.c:34`, `:117`, `:252`; `src/driver/manifest.c:98`; attribute handling and audit traversal.

`min`, `max`, and `clamp` unconditionally remove untrusted taint. A one-sided bound does not establish a valid index for a particular collection. Important flows through fields, container methods, mutations, and function boundaries are missed. Loop handling is not the documented fixpoint analysis. `@constant_time` is a limited source lint; `@server_only` checks annotation relationships rather than establishing engine authority.

The manifest parses `forbid_unsafe` as true only for the exact text `true`. A trailing comment such as `forbid_unsafe = true # explanation` instead disables it. Unknown/misspelled security annotations and incomplete audit AST traversal also need explicit validation.

**Work:** reject malformed security values; parse supported comments correctly. Distinguish taint from proven numeric bounds and collection-relative validity. Give intrinsics correct source/sink summaries. Implement conservative flow joins and function summaries where needed, or clearly narrow advertised coverage. Define explicit trust boundaries for validators and engine entry points.

**Acceptance:**

- Invalid booleans cannot silently disable protection; supported inline comments work.
- `min(i, 7)` and `max(i, 0)` do not automatically certify a general array index.
- Tests cover `.get`/`.set`, fields, receiver flows, mutation, function boundaries, and loop-carried taint.
- Unknown security annotations receive actionable diagnostics rather than silently disappearing.
- Audit coverage follows all relevant expression/statement forms.
- Documentation calls constant-time analysis a lint, explains residuals, and does not imply an annotation establishes runtime server authority.

### BR-12 — Make formatting preserve source meaning and comments

**Priority:** P1. **Evidence:** source finding.

**Locations:** `src/parse/format.c:94`, `:114`, precedence handling; lexer comment handling; `src/parse/print.c` and formatter tests.

`%g` defaults to six significant digits, changing some float values. `1.0` can become `1`, changing inferred type. Ordinary comments are lost; character escaping and some precedence-sensitive cases are not preserved. The AST printer also loses information, so equality of its dumps is not a sufficient oracle.

**Work:** preserve trivia or use a lossless syntax representation for formatting. Emit round-trip-safe literals that retain type distinctions. Correct escaping and precedence. Keep format-on-save disabled until semantic preservation is demonstrated.

**Acceptance:** comments survive; high-precision floats and integral-valued floats retain value/type; escaped characters remain valid; formatting is idempotent; independently checked parsed values and executing behavior are unchanged.

### BR-13 — Replace invalid benchmark evidence with a trustworthy harness

**Priority:** P1 for published claims. **Evidence:** source finding, not a benchmark rerun.

**Locations:** `scripts/bench.sh:67`, `:76`, `:86`; `docs/BENCHMARKS.md:15`, `:51`; runtime comments citing overhead.

The checked LCG benchmark starts with `12345` and multiplies by `1103515245` as `i32`, overflowing on its first iteration. A later mask cannot prevent the trap. `best3` suppresses output and ignores exit status, allowing a failed run to be timed as success. The generated large build benchmark lacks `main`, while build errors are hidden. No controlled Beryl/Rust comparison exists in the repository.

**Work:** validate successful builds, exit status, and expected outputs before timing. Use non-overflowing workloads to measure checked arithmetic overhead, and a separate intentionally wrapping workload with equivalent semantics. Produce a valid large-program entry point. Make stale executables impossible to count as successful builds. Withdraw or qualify unsupported numbers throughout the docs and runtime comments until rerun.

**Acceptance:** intentionally failing build/run cases fail the harness; checked and comparison workloads complete equivalent work; results record revision, toolchain, OS/CPU, flags, workload, repetitions, and output validation. Separate checking time, full-build time, runtime, memory, and binary size. Report distributions or stable summaries rather than an unexplained single timing.

### BR-14 — Expand verification beyond the stale unit-test baseline

**Priority:** P1. **Evidence:** test/script review and documented gap.

The repository has nine native end-to-end fixtures: six output cases and three trap cases. That is thin coverage for interacting features and two backends. Golden target text is not execution. Existing passing test counts do not establish current-source correctness. CI and fuzzing are absent from the reviewed tracked project.

**Work:** establish fresh builds in CI; require expected exit status as well as output; run debug/optimized generated programs; use compiler and generated-code sanitizers appropriately; fuzz parsing and later typed-program generation. Build an interpreter if useful as an additional oracle, but recognize that shared front-end errors can affect both interpreter and compiler.

**Acceptance:** all P0/P1 fixes have meaningful regressions; fresh CI cannot pass using stale binaries; positive/trap fixtures check both status and behavior; optimization-level differences are investigated; fuzz failures are minimized into durable regressions. Record Workbench compilation and engine execution as distinct checks.

### BR-15 — Repair module boundaries and document actual feature completeness

**Priority:** P2, earlier when needed by correctness work. **Evidence:** source finding and documented gap.

**Locations:** `src/sema/resolve.c:18`, `:157`, `:238`; `src/sema/check_expr.c` name lookup; `docs/ROADMAP.md:277`; `docs/STATUS.md`, `docs/SPEC.md`, tours and examples.

`pub` does not enforce the promised privacy boundary and `use` does not implement normal import-scoped resolution. Short names resolve through a program-wide map. Traits/generics and several container/optional/enum claims exceed implemented behavior. `lib/` is scaffolding rather than a usable standard library; path dependencies are not actually implemented.

**Work:** make lookup module-scoped, enforce visibility, diagnose ambiguity, and implement documented imports. Maintain one authoritative feature matrix: specified, implemented, tested natively, tested on Enfusion. Turn documentation examples into conformance tests. Reject unsupported feature use explicitly.

**Acceptance:** cross-module private access fails; valid imports resolve predictably; collisions are diagnosed; every public feature claim has a matching status and executable or diagnostic test. Planned features are clearly labeled as planned.

### BR-16 — Clean up repository and driver reliability without touching unrelated work

**Priority:** P2. **Evidence:** source and inventory findings.

The review counted 47 empty tracked files, mostly named after fragments of code. They suggest shell-command accidents. Untracked Blender tooling is unrelated to the compiler. Driver review also found a missing-file checking path that can print an error without returning a failing status, and build scripts/cache behavior deserves stronger failure handling.

**Work:** separately identify accidental tracked files and remove only verified junk within the owner's authorized scope. Leave unrelated/untracked work alone. Ensure CLI failures return nonzero, validate external-process outcomes, and prevent stale/shared cache artifacts from being mistaken for current outputs. Review shell argument construction when improving portability.

**Acceptance:** a missing source file makes `beryl check` fail; failed compilation cannot run an old executable; concurrent or distinct output operations do not silently reuse inappropriate cache state; cleanup is an independently reviewable change.

## Architecture changes recommended by the findings

### Explicit semantic lowering

The roadmap treats a shared IR as useful only for a future machine-code backend. That is too restrictive. A structured high-level representation can preserve readable EnforceScript, while a control-flow representation supports ownership, definite initialization, cleanup, and conditional effects.

A reasonable direction is:

```text
Source → lossless syntax / AST → resolved typed representation
                             → explicit effects, cleanup, and control flow
                             → verified target-specific lowering
                               ├─ C → Clang
                               └─ EnforceScript
```

Do not start with a wholesale rewrite. First isolate the semantics shared by the bugs: evaluating once, conditional execution, binding identity, ownership transfer, and cleanup. Refactor those in small steps with regressions.

### Small supported subset before broad feature coverage

An unsupported construct rejected clearly is safer than an accepted construct with omitted code or fabricated values. Define a portable subset whose tests predict both native and engine behavior. Expand only when the type checker, ownership checker, both applicable emitters, and tests agree.

### Memory model before additional allocating features

Lists already make memory semantics an immediate requirement. Copying, moving, borrowing, and dropping cannot wait until a later release adds `Box` or `Pool`. Generational handles can be useful, but they still need generation rollover, invalidation, aliasing, and future concurrency rules. They are not automatically faster than pointers or automatically race-free.

## Performance and security positioning against Rust

The goal should remain ambitious but measurable. This review does not establish a Beryl runtime advantage, and the C backend does not guarantee one. Both language semantics and emitted optimization information matter.

| Dimension | Credible goal to validate |
|---|---|
| Iteration speed | Fast checking and testing on realistic, growing projects |
| Enfusion development | One implementation of portable logic, tested natively and executed equivalently in-engine |
| Games/simulations | Convenient entity stores and graph ownership with explicit costs |
| Predictable performance | Allocation control, visible copies, useful layouts, stable frame-time behavior |
| Security defaults | Consistent arithmetic checks, valid configuration, narrow unsafe permissions |

### Correct inaccurate comparisons

- Rust can enable overflow checks in release and use aborting panics. Stricter Beryl defaults can be valuable, but those are not capabilities Rust lacks. Compare binary sizes with equivalent stripping, linkage, runtime usage, and panic settings.
- Rust `unsafe` does not suspend every invariant or disable its borrow checker. Describe Beryl's proposed granular permissions on their own merits.
- No lifetime annotations is an ergonomic design choice with tradeoffs, not automatic proof of memory safety or speed.
- Built-in pools/handles and deterministic facilities may be valuable integration choices. Do not claim that Rust users cannot implement related strategies.
- Self-hosting does not by itself prove the compiler sound or eliminate all security risk. Fuzzing, sanitizers, semantic validation, and careful implementation remain necessary.
- A small C compiler executable is not directly comparable to the entire Rust toolchain; native Beryl builds also depend on Clang and its toolchain.

### Reference material

- [Cargo profiles: overflow checks, panic strategy, stripping, LTO](https://doc.rust-lang.org/cargo/reference/profiles.html)
- [The Rust Book: Unsafe Rust](https://doc.rust-lang.org/stable/book/ch20-01-unsafe-rust.html)
- [Hylo introduction: relevant mutable-value-semantics prior art](https://hylo-lang.org/introduction/)
- [Native Implementation of Mutable Value Semantics](https://arxiv.org/abs/2106.12678)
- [Clang UndefinedBehaviorSanitizer](https://clang.llvm.org/docs/UndefinedBehaviorSanitizer.html)

### Benchmark design after correctness

Use matched algorithms and equivalent safety semantics. Include realistic numeric/game kernels, collection growth and copying, entity traversal, and a real application workload as capabilities permit. Verify outputs, then measure runtime, allocations, memory footprint, binary size, checking time, and build time separately. Record toolchain versions and hardware. Inspect profiles/generated code to identify actual bottlenecks before pursuing SIMD, layout changes, bounds-check elimination, LTO, or PGO.

Copying and allocation may dominate arithmetic. Do not hide those costs behind an appealing scalar microbenchmark. Faster execution caused by omitted loops, early traps, or undefined behavior is a compiler failure.

## Suggested implementation sequence

| Milestone | Findings | Exit condition |
|---|---|---|
| A. Trust the build | BR-01, essential BR-14/16 | Fresh source builds; tests cannot pass from stale artifacts; failures are visible |
| B. Specify the safety core | BR-02/03/04/08/09 | Copy/move/drop and arithmetic rules are explicit; critical regressions are reproduced |
| C. Repair the safety core | BR-02/03/04/08/09 | Supported safe programs cannot reach the identified ownership/arithmetic hazards |
| D. Preserve program meaning | BR-05/06/07/10 | Supported operations execute correctly; target differences are implemented or rejected |
| E. Repair tools and protections | BR-11/12/15/16 | Configuration, lints, formatting, and modules behave as documented |
| F. Establish evidence | BR-13/14/15 | Fresh CI, conformance coverage, qualified claims, reproducible benchmark procedure |
| G. Expand through real usage | Design work | Add necessary language/library features with complete semantics and tests |

These milestones may overlap where work is independent. They do not require finishing every future feature before using a tightly restricted, tested subset.

Move memory correctness forward from the roadmap's proposed v0.5: allocating lists already exist. Keep hardening continuous rather than treating it as a late general-edition phase. A real mod is a valuable proving ground, but test and stage changes before replacing its handwritten logic. Failure of one Enfusion experiment would be evidence about that use case, not proof that the wider language has no value.

Avoid using compiler line-count estimates as acceptance criteria. A 900-line interpreter, 2,000-line ownership checker, or 300-line module fix is not valuable because it meets a size estimate; it is valuable if it implements and verifies the required semantics.

## Completion record for implementation work

Claude should maintain a concise record using this structure as work progresses:

```text
Finding ID:
Current status:
Reproduction against current revision:
Chosen semantics / design decision:
Changed files:
Regression tests:
Exact validation commands and outcomes:
Remaining limitations:
Related findings still open:
```

The initial review's overall recommendation is to continue Beryl while making the next release about trustworthy semantics. The language's small compiler and concrete use case are useful foundations. Correct accepted programs, consistent target behavior, and valid measurements are the prerequisites for credible claims about performance and security.
