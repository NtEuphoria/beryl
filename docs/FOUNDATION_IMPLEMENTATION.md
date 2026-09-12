# Foundation implementation and verified handoff

September 6, 2026. Starting commit: `a2405eac14e2098a8f6b2f68183f04137fb28e3d`.

This is the implementation record for the first foundation tranche of the
[optimization and Enfusion blueprint](BERYL_OPTIMIZATION_AND_ENFUSION_BLUEPRINT.md).
It distinguishes working changes from the much larger research plan. It is the
starting point for Claude or Codex continuing from this checkout.

The owner authorized implementation after the earlier document-only reviews.
Claude's committed fixes were retained. The pre-existing, uncommitted literal
range checking in `src/parse/ast.h` and `src/sema/check_expr.c` was preserved and
extended, rather than reset. Unrelated files and projects were left alone.

## What changed

### Constant types and values

- Constant type inference now tracks unresolved, resolving and checked states.
  Inferred cycles produce BE0504 instead of unbounded recursive checking.
- Initializers are checked in their declaration context. A function's local
  variable cannot accidentally supply a name to a global constant initializer.
- Constant evaluation has a step limit and a nesting limit covering expression
  recursion, not just references between constants.
- Arithmetic respects the checked integer width and signedness. For example,
  `const X: i8 = 127 + 1` produces BE0503.
- Unsigned values have a separate representation through the full u64 range.
  Comparisons and generated literals no longer reinterpret that range as i64.
- Signed minimum literals are constructed directly. They do not first narrow a
  positive operand and then invoke checked negation on an already-negative value.
- Constant `MIN / -1` reports overflow without invoking undefined host arithmetic.
  `MIN % -1` returns zero, matching the existing native runtime. This distinction
  was checked against the runtime rather than inferred from the division rule.
- Constant shifts check the operand width; bit operations normalize to that width.
- Constant f32 operations round intermediate values to f32. Float-to-integer
  constant casts check finite, truncated values against exclusive power-of-two
  bounds before executing a C cast.
- Boolean constant evaluation short-circuits. A typed definition such as
  `const A: bool = false && A` can evaluate to false; type inference and executed
  value dependencies are deliberately separate questions.
- Native floating constant emission preserves valid literal syntax, including
  integral-valued f32 constants. Runtime wrapping multiplication avoids narrow
  integer promotion overflow, and left shifts operate through unsigned storage.

These changes do not complete the numeric semantics work. In particular, dynamic
floating-to-integer casts and full native/Enfusion arithmetic equivalence still
need a specified, independently tested contract.

### Returns, initialization and control flow

- Returning an error from a non-error-returning function is rejected.
- Bare return is valid for void and !void, but does not invent a !T payload.
- Returning an ordinary void call from a !void function preserves the call's effects.
- `try` checks `set` obligations on its implicit failure exit.
- A `set` argument becomes initialized after all call arguments are evaluated.
  A later argument cannot read it on the assumption that the callee ran already.
- Short-circuit operators merge ownership states across the skipped operand.
- Loop analysis tracks break, continue and fallthrough separately and iterates to
  a fixed point. A return inside a possibly empty loop does not erase the path
  after the loop. Unreachable statements do not initialize live paths.
- A returning catch handler does not erase the successful path of the expression.
- Destination index expressions receive ownership analysis. Their calls and reads
  cannot hide inside the left side of an assignment.
- Intrinsic list mutators now respect immutable locals and read-only parameters.
- Call exclusivity checks cover all arguments. Deep access paths conservatively
  overlap when the bounded field representation cannot retain the whole path.
- Explicit inout/set arguments must name local storage.

These are improvements to the existing AST analysis, not a soundness proof of
the entire ownership model. Collection aliases remain a separate blocker.

### Default arguments before security analysis

`src/sema/defaults.c` runs at the end of successful type checking, before ownership,
taint, profile lint, or either backend.

Every omitted default receives a fresh expression tree with the declaration's
resolved bindings and checked types. Nested omission is expanded under a shared
work/depth budget. Recursive defaults fail with BE0504, including unused recursive
templates. Two calls in one statement no longer share a default's generated temporary.

Calls inside defaults are therefore visible to caller-side security analysis.
For example, a client function omitting an argument whose default calls a
`@server_only` function now receives BE0705.

The supported parameter-default subset permits literals, constants, arithmetic,
casts, aggregate expressions, ordinary calls and orelse without formal/local
references or nonlocal control flow. Unsupported forms produce BE0322 and can be
written as explicit call arguments. This is a deliberate bounded implementation,
not a claim that arbitrary default closures or formal substitution exist.

Field defaults are constant-evaluated as the specification already requires.
Omitted field defaults are inserted into struct expression occurrences as well.

### Generated evaluation and naming

- Native binary operands and ordinary call arguments are explicitly sequenced.
  Short-circuit RHS preparation is emitted inside the conditional branch.
- Native compound assignment saves the destination address and old value before
  evaluating the RHS. An indexed destination is evaluated once.
- Native local symbols include their declaration position, separating shadowed
  locals, escaped keywords and compiler temporary names.
- Enfusion sequences effectful operands and arguments with locals, and keeps
  short-circuit RHS preparation inside the branch.
- Enfusion indexed assignment saves the receiver/index and emits an explicit
  store. This repairs Workbench's rejection of `array[index] += value`.
- Enfusion detects collisions among a function's local names, keyword escapes,
  generated `_t...` names and the synthetic result name. A function needing
  disambiguation gets distinct local symbols; ordinary functions retain plain names.
- Catch requires an error union. Native !void catch emits no void temporary.
  Enfusion scalar catch supplies the legacy zero fallback and a generic error
  indicator for the binding. That indicator is **not** the native error tag.
- Unsupported Enfusion handled-union shapes and aggregate catch-zero payloads
  now produce target diagnostics instead of those particular malformed lowerings.
- Enfusion immediate defer calls are emitted rather than silently discarded.
  Defer still has the documented v0.1 immediate timing; scope-exit defer is pending.

`restrict` is intentionally absent from native inout/set signatures. Tracking two
different local names is insufficient to prove disjoint backing storage when
collection copies may alias. Re-enable this metadata only after storage identity
and copy semantics supply the required evidence.

### Compiler tooling and formatting

- Missing input is BE0803 and a failing exit status. Unknown targets/options fail.
- `beryl check` applies the selected target's profile, including local types.
- `beryl emit-c [--tests] files...` writes generated C to stdout without launching
  Clang or a generated executable. This is a useful seam for AI tools and build systems.
- The formatter preserves floating literal kind, double payload and suffixes, and
  escapes character/control values. The AST printer retains precision and numeric
  suffixes so the old roundtrip comparison no longer hides those differences.
- `scripts/verify-foundation.py` uses argv-based subprocesses, separate build
  directories, checked exit statuses, timeouts and optional UBSan. It compares
  two emissions for determinism and compares O0/O2 program outcomes.
- `scripts/reforger-proof.ps1` creates unique addons under this repository's
  build directory. It never deletes the shared `_BerylProof` addon, retains its
  result JSON and treats a missing Workbench helper as a failure, not a pass.

## Validation actually performed

The starting checkout passed **220 unit cases / 982 checks**. The final expanded
suite passed **259 unit cases / 1,104 checks** with UBSan enabled.

The final harness also compiled and ran **13 end-to-end programs at both O0 and
O2**, compared their outcomes, and checked deterministic C emission. Normal cases
required successful exit, exact stdout and empty stderr. Trap cases required a
nonzero exit plus the expected Beryl trap; a sanitizer report cannot substitute
for that trap. The PID example passed **4 tests / 5 assertions**.

The final local evidence is:

- `build/foundation-39wv85ej/results.json`: toolchain identity, every command,
  statuses, output, generated-C hashes and source hashes.
- `build/enfusion-proof-49229ad68f604aa9b2d36a4aa7ab5595/result.json`:
  successful Workbench compilation of `foundation_order.be` after its repair.
- `build/enfusion-proof-987bc94790ec467d8c9fc7843919d0a3/result.json`:
  successful Workbench compilation of `foundation_names_errors.be` after its repair.
- `build/foundation-pzfrtign/results.json`: the subsequent non-sanitized run
  passed 259 unit cases / 1,104 checks and the 65-code documentation check, then
  stopped when Windows Application Control blocked the compiler's first launch
  (WinError 4551). Its end-to-end phase did **not** run; this historical run
  remains a failed gate.
- `build/foundation-xw1faoiu/results.json`: after the owner changed Smart App
  Control and requested continuation, a fresh non-sanitized O2 compiler passed
  the entire verification run: 259 unit cases / 1,104 checks, 65 documented
  literal diagnostic codes, all 13 end-to-end programs at O0/O2 and the PID tests.
- `build/enfusion-proof-efc2b1fbe2c94e8ba4bf09aad315691c/result.json` and
  `build/enfusion-proof-4357904ce53d495fb98ad871757d4c0d/result.json`: the release
  compiler's order and names/error fixtures also compiled cleanly in Workbench.
- `build/foundation-xw1faoiu/publication.json`: records installation of the exact
  verified compiler, its hash, the previous binary's backup and successful
  installed-binary version and Enfusion profile checks.

The source hashes in the native reports match the final `src`, `runtime` and
`tests` files. The Python documentation check was added after the successful
sanitizer run; the subsequent run verified that check before the launch denial.
The shell documentation checker also passed with its required utilities present.

`build/beryl.exe` now contains the verified non-sanitized compiler from
`build/foundation-xw1faoiu/beryl.exe`. The previous default is backed up at
`build/foundation-xw1faoiu/previous-default-beryl.exe`. The installed binary's
SHA-256 is `1e255ad9e5646ea9f2e6e9f38227229466c4edf4762ccc14096e3c27740d7b6c`.
The compiler that completed the sanitizer run remains at
`build/foundation-39wv85ej/beryl.exe`.

The earlier blocked artifact launched successfully at its original path after
the owner's system change. The harness still stops on a denied launch without
automatic retries or binary mutation; the historical failure was not overwritten.

These are ignored build artifacts. They are available in this checkout and are
not promised to exist in a future clone. Recreate them with the commands below.

The Workbench probes first reproduced the indexed compound-assignment and local
name-collision errors, then passed after the repairs. The scenarios live in an
ordinary `exercise` function because Enfusion intentionally omits native `main`.
Earlier probes with the scenarios inside main did **not** validate those bodies
and are not evidence for these fixes.

Workbench results establish successful script compilation for these fixtures.
They do not establish runtime parity, in-game mod correctness or a performance
advantage. No Rust comparison, speedup measurement or complete interpreter oracle
was produced in this tranche.

## Reproduce and continue

From the repository root, with Python and Clang available:

```text
python scripts/verify-foundation.py --sanitize
```

Pass `--clang <absolute-path-to-clang>` when needed. The harness prints the output
directory and evidence location. It performs no execution retry after a denied
launch and does not modify binary contents to obtain another security verdict.
Resolve an Application Control denial through the machine's approved software
trust process before attempting to validate or install a blocked compiler.

For the Workbench compile gate, use the compiler printed by that run:

```powershell
.\scripts\reforger-proof.ps1 -Beryl '<verified compiler path>' -Source tests/e2e/foundation_order.be
.\scripts\reforger-proof.ps1 -Beryl '<verified compiler path>' -Source tests/e2e/foundation_names_errors.be
```

For an AI authoring loop:

1. Write concrete Beryl within the implemented subset in SPEC/STATUS.
2. Run `beryl check -t enfusion <files>` before emitting a mod artifact.
3. Use `beryl emit-c <files>` for deterministic native output inspection.
4. Run native regressions through the explicit harness, then the Workbench compile gate.
5. Require a separate in-engine runtime test before treating the two targets as equivalent.

## Remaining work, in dependency order

This tranche advances IMP-00B/IMP-00C and the prerequisites around defaults and
control flow. It does **not** close all acceptance criteria of either ticket,
implement IMP-01's independent reference evaluator, or complete roadmap v0.2.

| Next work | Why it remains necessary |
|---|---|
| Storage identity and collection ownership | Native collection header copies can share backing storage; nested copies, growth while iterating, lifetimes and release need a single tested contract. Local exclusivity alone does not settle this. |
| Remaining source identities and modules | Local names were repaired, but qualified item/type/field naming, imports, pub visibility and collisions are not a completed module-system implementation. |
| Complete outcome and effect semantics | Scope-exit defer, arbitrary error-union transport, expression forms outside the tested sequencing paths and cross-target failure behavior still need structured treatment. |
| Taint soundness | Field/container propagation, interprocedural effects, validators and unjustified loss of untrusted taint in bounding intrinsics remain audit findings. |
| Driver and manifest hardening | Legacy build/run still use shell command construction, shared cache paths and retry logic; manifest boolean/comment parsing also remains an audit finding. The new verifier/emit-c path avoids relying on that runner. |
| Remaining resource and malformed-input limits | Constant/default recursion is bounded, but this is not whole-compiler parser-depth, allocation-overflow or fuzzing coverage. |
| Independent interpreter and generated corpus | O0/O2 comparisons can agree on the same frontend mistake. Implement a separately specified oracle before relying on them as optimizer validation. |
| Real mod/runtime experiment | Compile probes are not the SPARKOS class port, deployment, gameplay checks or profiling required by roadmap v0.2. |
| Performance experiments | Start the blueprint's checked-block or other bounded experiment only after its particular semantic and evidence gates pass. Compare against an appropriately configured Rust baseline. |

Keep historical review findings as observations of their recorded commits.
Reproduce remaining cases against current source before fixing them, and add an
executing regression when the defect concerns generated behavior. Do not mark
the 232 proposed validation cases as implemented merely because this handoff
contains tests, or treat generated-C determinism as full binary reproducibility.
