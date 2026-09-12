# Status — what v0.1 actually does

Current work follows the [delivery program](BERYL_DELIVERY_PLAN.md).
[Delivery state](BERYL_DELIVERY_STATE.md) separates new development from the
previously installed and verified checkpoint described below.

The [advanced implementation program](BERYL_ADVANCED_IMPLEMENTATION_PLAN.md) is
authorized. See [its current evidence and open gates](BERYL_ADVANCED_IMPLEMENTATION_STATE.md)
before treating any research or planned optimization as available.

The current September 7 delivery checkpoint adds safety containment, repaired
expression order, capability/example context, `doctor`, exact-snapshot analysis
and a hardened local MCP installation. It passed 496 cases / 10,285 checks in
normal and UBSan builds, 18 native regressions at O0/O2, 867 real engine checks and
65,850 complete PID comparisons. See [delivery state](BERYL_DELIVERY_STATE.md)
for exact identities, receipts, rollback and remaining gates.

The earlier September 7 installed checkpoint added 35 hash-backed engine declaration
lookups, array/Canvas probes, actual terrain construction/release collection and
the experimental record/PID IR evaluator. It also rejects two previously
unsupported verification/copy boundaries explicitly. The final compiler passed
356 unit cases / 2,681 checks normally and under UBSan, plus the documented CLI
and real engine suites. Terrain construction recorded a scoped 34.06% median
paired time reduction; independent-session, resource and full-render acceptance
remain open. Public IR lowering, automatic optimizations and the full advanced
program remain incomplete. The linked execution state records exact evidence,
source identities, installation and rollback.

For where this goes next, see [ROADMAP.md](ROADMAP.md).
The approved [SPARKOS plan](SPARKOS_IMPLEMENTATION_PLAN.md) and its
[execution state](SPARKOS_IMPLEMENTATION_STATE.md) control current implementation.
For the latest implemented repairs and exact validation boundaries, see
[FOUNDATION_IMPLEMENTATION.md](FOUNDATION_IMPLEMENTATION.md), updated September 6.

This describes **Beryl/Enfusion**, the edition targeting Arma Reforger. A
general-purpose edition is a stated goal built from the same compiler rather
than a fork — [ROADMAP.md](ROADMAP.md) §2.1 and §4.2. Nothing below is
Enfusion-only unless it says so.

Coverage is uneven. Unsupported constructs have explicit diagnostics in several
paths, but remaining correctness gaps are recorded below and in the implementation
handoff; this inventory is not a claim that every unsupported path fails cleanly.

## Works

**Language**

- Logical modules spanning files, explicit item/module imports, `pub` enforcement,
  qualified type/receiver identity, and explicit-import cycle detection (M1).
- `struct` with field defaults, methods as `fn Type.name(...)`
- `enum`, C-like, with explicit discriminants
- `const` with compile-time evaluation
- `i8`–`i64`, `u8`–`u64`, `f32`, `f64`, `bool`, `char`, `str`, `void`
- `[T; N]` fixed arrays with const-evaluated length, bounds-checked
- `T?` optionals — and no null anywhere
- `!T` error unions with `try`, `orelse`, `catch`
- Admitted scalar/plain-element `List<T>` operations: `len` `push` `get` `set`
  `clear`; general owning copies and automatic lifecycle cleanup are unfinished
- `let` / `var`, `if` / `else if` / `else`, `while`, `for … in` over a range or
  an array, `break`, `continue`, `return`, `defer`
- passing conventions `let` `inout` `sink` `set`, at declaration and call site
- attributes: `@untrusted` `@validator` `@secret` `@constant_time`
  `@server_only` `@unsafe(cap)`
- `test "..." { }` blocks, native by default; explicit bounded reference and
  differential execution for the [M2 subset](M2_IMPLEMENTATION.md)
- built-ins: `print` `println` `assert` `min` `max` `abs` `clamp` `sqrt`
  `wrapping_add/sub/mul` `saturating_add/sub`
- reserved words usable as member names (`xs.set(i, v)`)

**Analysis**

- bidirectional type checking, function-local inference, explicit signatures
- no implicit numeric conversion of any kind
- ownership: definite initialization, moves, exclusivity, `set`-parameter
  discharge
- taint: `@untrusted`, `@secret`, `@server_only`, `@constant_time`
- stable BE diagnostics, with regression coverage and a documentation check

**Back ends**

- native, via C11 and clang; overflow, bounds and divide-by-zero all trap
- EnforceScript for Arma Reforger, **verified to compile in real Workbench**

**Tooling**

- `beryl new / check / build / run / test / emit-c / fmt / ast / audit / version`
- `beryl.toml`, so every command works with no file arguments
- canonical formatter, idempotent and round-tripping
- Generated capabilities/examples, environment doctor, bounded exact-snapshot
  analysis and optional local stdio MCP over the same CLI

## Does not work yet

| | code | note |
|---|---|---|
| user-defined generics | `BE0508` | parse and type-check; not instantiated. Built-in containers are intrinsic and fine. |
| `trait` bodies | — | parse; no resolution, no bounds checking, no `dyn` |
| `Map<K,V>` methods | `BE0306` | target type emission does not establish admitted method support; full store operations remain M6 work |
| `Map<K,V>` natively | `BE0901` | no native representation yet |
| `Box` `Rc` `Pool` `Handle` | `BE0902` | designed into the ownership model, not implemented |
| payload enums, `match` | — | [ROADMAP.md](ROADMAP.md) v0.4 |
| concurrency, async | — | cut from the Enfusion edition, which is single-threaded; designed for the general edition in [ROADMAP.md](ROADMAP.md) §5.11 |
| capability-based I/O | — | designed ([SECURITY.md](SECURITY.md) §6); there is no I/O to protect yet |
| reproducible binaries | — | generated C has determinism checks; byte-identical native binaries need a separately verified toolchain/path policy |
| `@unsafe` machinery | — | parses, audits, and is refused where forbidden; no raw pointers or FFI behind it |
| package registry, deps | — | path only |
| LSP, syntax highlighting | — | — |

## Known rough edges

- **Module limits:** generic instantiation remains unsupported, external extension
  methods are rejected, and fully qualified references do not add implicit cycle
  edges. Explicit engine exports initially admit scalar method interfaces only;
  scalar constructor mappings and the full PID are implemented and engine-tested;
  the MESH candidate gameplay/handover gate passed in M3. Broader export interfaces
  remain outside the admitted scalar profile.
- **`lib/` is empty.** There is no standard library written in Beryl at all —
  the directories were scaffolded and never filled. The built-ins and the
  container intrinsics are implemented in the compiler, in C.
- **`defer` runs where it is written**, not at scope exit. Correct ordering
  arrives with destructors.
- **`catch` yields a zero value** when the handler does not return. Fine for
  the common `catch |e| { log(e); return }`, loose otherwise.
- **Taint analysis remains bounded.** Delivery work adds field paths, conservative
  element summaries and a whole-program fixed point. Full symbolic summaries and
  dynamic-storage range proofs remain unfinished; see
  [P1 taint safety](advanced/P1_TAINT_SAFETY.md) for scope and evidence.
- **`Quat` and `Mat3/4`** are type names that lower to a target type but have
  no operations at all, not even component access. `Vec2/3/4` are complete
  ([SPEC.md](SPEC.md) §3.1.1); `Vec2` and `Vec4` are native-only.
- **The lexer is ASCII-only** for identifiers, and diagnostic columns count
  bytes, so a multi-byte character before a caret shifts it.
- **No incremental compilation.** Every build is from scratch — which at 124 ms
  for 10,000 lines has not been a problem.

## Environment

M0 replaces native shell composition and execution retries with explicit argv,
isolated jobs, checked publication, and separate process outcomes. Its current
test evidence and remaining gates are in the implementation state. See
[BUILDING.md](BUILDING.md) for the current verified workflow.

## Test coverage

```
356 unit cases, 2,681 checks   previous installed checkpoint, normal and UBSan runs
15 native programs/harnesses   O0/O2 outcomes compared; includes multi-module fixtures
4 PID tests, 5 assertions      test module imports the example implementation
M1 Workbench export probe      multi-module function bodies compiled for real
8 full PID tests, 2,206 assertions   shared complete MESH controller implementation
2,195 engine PID operations    65,850 original/generated/reference field comparisons
9 existing MESH suites         passed in an isolated generated-PID candidate
18 host gameplay checks        all passed; actual takeover/release also passed
```

`python scripts/verify-foundation.py --sanitize` runs the native verification.
`scripts/reforger-proof.ps1` runs Workbench compilation separately.

The thin spot is codegen: 13 programs are still limited coverage for two back ends
([THREAT-MODEL.md](THREAT-MODEL.md) S9). A codegen bug producing *valid but
wrong* C would pass both clang and the type checker.

The installed M3 compiler also supports the initial strict JSON companion profile
through `beryl mod check/build/verify --stage compile/promote`. See the
[package workflow](../packages/sparkos/pid/README.md). M3's isolated MESH candidate
passed actual gameplay and handover on September 7; see
[the exact evidence](M3_IMPLEMENTATION.md). The live MESH project remains unchanged.
Dedicated multiplayer and visual acceptance have not been established.
