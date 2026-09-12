# How the compiler is built

C11, clang, zero dependencies, ~11,800 lines. If you want to change something,
this is the map.

## Pipeline

```
.be → lex → parse → resolve → check/default expansion → ownership → taint
                                                                  ├→ C → clang
                                                                  └→ EnforceScript → Workbench
```

Each stage runs only when the previous one was clean. That is why a syntax error
never produces a cascade of invented type errors.

**There is no MIR.** The design doc originally specified a shared low-level IR
feeding both back ends; that was wrong for this language pair. EnforceScript is
a *high-level* language, and lowering to SSA only to reconstruct classes, loops
and expressions from it would destroy exactly the structure that back end must
emit — and make the generated script unreadable, which matters because it gets
debugged inside Workbench. Both back ends emit from the **typed AST**.

## Layout

| | |
|---|---|
| `src/common/` | arena, `Str`, vec, map, source map, diagnostics |
| `src/lex/` | tokens, scanner, the newline rule |
| `src/parse/` | AST, recursive-descent items and statements, Pratt expressions, printer, formatter |
| `src/sema/` | types, resolve, check, defaults, constfold, ownership, taint, intrinsics |
| `src/back/` | C emission, EnforceScript emission, the two profile lints |
| `src/driver/` | CLI, manifest, build orchestration, audit |
| `runtime/` | ~200 lines: traps, checked arithmetic, `List` growth, test harness |

## The decisions that shaped it

**Arena allocation everywhere.** One arena per compilation, freed wholesale at
exit. This is the standard fast-compiler technique, and it simultaneously
removes nearly all of C's memory-bug surface: there are no `free` calls to get
wrong and no ownership questions between passes. It is also the main reason
`beryl check` handles 10,000 lines in ~124 ms.

**Interned types.** `ty_eq` is a pointer comparison. Interning is keyed on the
canonical rendering, which is unique per type.

**Interned identifiers.** Equal strings share a pointer after `intern()`.

**Structural analysis, not a CFG.** Beryl has no `goto`, so ownership and taint
walk the AST directly. Ownership merges continuing paths and tracks loop breaks
and continues separately, iterating the finite state lattice to a fixpoint. Loop bodies
run *quietly* to the fixpoint and then once more with diagnostics enabled, so a
problem in a loop is reported once rather than once per iteration.

**Default expansion precedes access/security analysis.** `defaults.c` clones each
omitted parameter default into its call, retaining declaration resolution. The
bounded subset rejects formal references and nonlocal exits. Generated code and
the analyses now see the same explicit arguments. Details, verified repairs and
remaining limits are in [FOUNDATION_IMPLEMENTATION.md](FOUNDATION_IMPLEMENTATION.md).

**Constant checking has separate phases.** `chk_const` tracks type resolution and
does not borrow a caller's local scope. `constfold.c` evaluates typed values with
separate signed/unsigned representations and depth/work budgets. Its short-circuit
value dependencies are not the same as the dependencies needed to infer a type.

**Diagnostics are a first-class subsystem.** Caret spans, multiple labels on one
line with connector rows, tab-aware alignment, notes and helps, stable
`BE####` codes. `scripts/check-diagnostics.sh` fails if a code exists in `src/`
without an entry in `docs/DIAGNOSTICS.md`.

**Format-checked varargs.** `sb_fmt` and every `diag_*` function carries
`__attribute__((format(printf)))`. This was added after a missing argument in
one format string produced a segfault and several minutes of confusion; the
attribute makes that whole class a compile error.

**The runtime is embedded.** `scripts/embed_runtime.py` turns `runtime/*.{h,c}`
into `src/back/runtime_embed.h`, which is committed. `beryl.exe` writes the
runtime into its cache directory at build time, so the compiler stays a single
self-contained binary with no lib directory to install. A build never needs
Python; regenerating the header does.

## Adding a diagnostic

1. Pick a code in the right range (see DIAGNOSTICS.md).
2. `diag_error(d, code, span, "...")`, then `diag_label`, `diag_note`,
   `diag_help` as they help. A label on the primary span is what draws the
   caret when other labels exist.
3. Add a golden test asserting the code *and* a distinctive phrase.
4. Document it. `scripts/check-diagnostics.sh` will fail until you do.

Write the help line as the fix, not as a restatement of the problem. `BE0312`
puts the exact cast in it; `BE0601` names `clamp(i, 0, n - 1)`.

## Adding a built-in

1. `Intrinsic` enum in `src/sema/intrinsic.h`, plus the name table.
2. Type rule in `chk_intrinsic` (`src/sema/check_expr.c`).
3. Emission in `gen_call_intrinsic` for **both** back ends.
4. An end-to-end program under `tests/e2e/`.

Container methods dispatch by receiver type in `chk_call` and live in the same
enum, separated by range predicates — `intrinsic_is_list_method` rather than a
bare `>=`, which is a bug waiting to happen once a second range exists.

## Testing

```bash
bash scripts/test.sh            # 204 unit cases, 931 checks
bash scripts/e2e.sh             # 9 programs: compile, run, compare stdout
bash scripts/check-all.sh       # everything above
bash scripts/bench.sh           # the numbers in BENCHMARKS.md
bash scripts/check-diagnostics.sh
pwsh scripts/reforger-proof.ps1 # real Workbench compile
```

The unit tests use a tiny harness in `tests/unit/test.h`: `CASE`, `CHECK`,
`CHECK_EQ_I`, `CHECK_EQ_S`, `CHECK_CONTAINS`. No framework.

Golden tests assert on *rendered diagnostics*, so a change to the renderer or to
a message shows up immediately. The two-label `BE0401` test asserts the layout
byte-for-byte, which is what stops the diagnostic format from drifting.

**The thin spot is codegen.** Nine end-to-end programs is not much for two back
ends, and a codegen bug producing valid-but-wrong C would pass both clang and
the type checker. New back-end work should come with new e2e programs.

## Smart App Control

This machine blocks freshly built unsigned binaries non-deterministically. The
scripts and `beryl run` both handle it by rebuilding with a changed content hash
and retrying. It is not a compile failure and not caused by the code. See
[BUILDING.md](BUILDING.md).

## Self-hosting

The native back end emits C, and the compiler is written in C, so porting it to
Beryl is a natural later step. It is also the only real answer to residual
**S1** in the [threat model](THREAT-MODEL.md): a memory-safety language whose
compiler is written in a memory-unsafe one. The code deliberately avoids C
constructs with no Beryl equivalent so that port stays cheap.
