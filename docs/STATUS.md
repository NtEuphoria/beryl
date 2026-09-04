# Status — what v0.1 actually does

For where this goes next, see [ROADMAP.md](ROADMAP.md).

A straight inventory, so nobody has to discover a gap by hitting it. Everything
listed as missing produces a **clear diagnostic**, not odd behaviour.

## Works

**Language**

- `module` declarations and circular-import detection — but see the rough edges
  below: `pub` and `use` are not yet enforced
- `struct` with field defaults, methods as `fn Type.name(...)`
- `enum`, C-like, with explicit discriminants
- `const` with compile-time evaluation
- `i8`–`i64`, `u8`–`u64`, `f32`, `f64`, `bool`, `char`, `str`, `void`
- `[T; N]` fixed arrays with const-evaluated length, bounds-checked
- `T?` optionals — and no null anywhere
- `!T` error unions with `try`, `orelse`, `catch`
- `List<T>` with `len` `push` `get` `set` `clear`
- `let` / `var`, `if` / `else if` / `else`, `while`, `for … in` over a range or
  an array, `break`, `continue`, `return`, `defer`
- passing conventions `let` `inout` `sink` `set`, at declaration and call site
- attributes: `@untrusted` `@validator` `@secret` `@constant_time`
  `@server_only` `@unsafe(cap)`
- `test "..." { }` blocks, run natively
- built-ins: `print` `println` `assert` `min` `max` `abs` `clamp` `sqrt`
  `wrapping_add/sub/mul` `saturating_add/sub`
- reserved words usable as member names (`xs.set(i, v)`)

**Analysis**

- bidirectional type checking, function-local inference, explicit signatures
- no implicit numeric conversion of any kind
- ownership: definite initialization, moves, exclusivity, `set`-parameter
  discharge
- taint: `@untrusted`, `@secret`, `@server_only`, `@constant_time`
- 59 diagnostics, every one documented and tested

**Back ends**

- native, via C11 and clang; overflow, bounds and divide-by-zero all trap
- EnforceScript for Arma Reforger, **verified to compile in real Workbench**

**Tooling**

- `beryl new / check / build / run / test / fmt / ast / audit / version`
- `beryl.toml`, so every command works with no file arguments
- canonical formatter, idempotent and round-tripping

## Does not work yet

| | code | note |
|---|---|---|
| user-defined generics | `BE0508` | parse and type-check; not instantiated. Built-in containers are intrinsic and fine. |
| `trait` bodies | — | parse; no resolution, no bounds checking, no `dyn` |
| `Map<K,V>` methods | `BE0306` | usable as a type; works fully on the enfusion target |
| `Map<K,V>` natively | `BE0901` | no native representation yet |
| `Box` `Rc` `Pool` `Handle` | `BE0902` | designed into the ownership model, not implemented |
| payload enums, `match` | — | [ROADMAP.md](ROADMAP.md) v0.4 |
| concurrency, async | — | deliberately cut from v0.1 |
| capability-based I/O | — | designed ([SECURITY.md](SECURITY.md) §6); there is no I/O to protect yet |
| reproducible builds | — | conflicts with the SAC workaround; unresolved |
| `@unsafe` machinery | — | parses, audits, and is refused where forbidden; no raw pointers or FFI behind it |
| package registry, deps | — | path only |
| LSP, syntax highlighting | — | — |

## Known rough edges

- **The module system does not enforce anything.** `use` is parsed and used only
  for cycle detection; `pub` is stored and never checked. Every short name
  resolves across the whole program, so a private function in another module is
  callable with no import. First item of real work in
  [ROADMAP.md](ROADMAP.md) §5.3.
- **`lib/` is empty.** There is no standard library written in Beryl at all —
  the directories were scaffolded and never filled. The built-ins and the
  container intrinsics are implemented in the compiler, in C.
- **`defer` runs where it is written**, not at scope exit. Correct ordering
  arrives with destructors.
- **`catch` yields a zero value** when the handler does not return. Fine for
  the common `catch |e| { log(e); return }`, loose otherwise.
- **Struct fields are not taint-tracked**, so taint laundered through a field is
  invisible ([THREAT-MODEL.md](THREAT-MODEL.md) §2).
- **`Vec2/3/4`, `Quat`, `Mat3/4`** are type names that lower correctly, but have
  no operations beyond arithmetic on the vector types.
- **The lexer is ASCII-only** for identifiers, and diagnostic columns count
  bytes, so a multi-byte character before a caret shifts it.
- **No incremental compilation.** Every build is from scratch — which at 124 ms
  for 10,000 lines has not been a problem.

## Environment

This machine runs **Smart App Control in Enforce mode**, which blocks freshly
built unsigned binaries non-deterministically. Both `scripts/*.sh` and
`beryl run` handle it by rebuilding with a changed content hash and retrying.
A `note: Smart App Control blocked this binary; rebuilding` line is expected and
harmless. [BUILDING.md](BUILDING.md) has the details.

## Test coverage

```
204 unit cases, 931 checks     compiler internals, all 59 diagnostics
9 end-to-end programs           compiled, run, stdout compared; 3 are trap tests
1 Workbench build               generated EnforceScript, compiled for real
```

`bash scripts/check-all.sh` runs everything except the Workbench build, which is
`scripts/reforger-proof.ps1`.

The thin spot is codegen: 9 programs is not many for two back ends
([THREAT-MODEL.md](THREAT-MODEL.md) S9). A codegen bug producing *valid but
wrong* C would pass both clang and the type checker.
