# Beryl's security model

Read [THREAT-MODEL.md](THREAT-MODEL.md) alongside this. This document says what
the model *does*; that one says where it stops, and the second half is the more
important of the two.

Implementation status is bounded by the [foundation handoff](FOUNDATION_IMPLEMENTATION.md)
and [delivery state](BERYL_DELIVERY_STATE.md). Taint analysis runs at compile
time. The delivery work adds bounded field/element and interprocedural propagation;
symbolic summaries and dynamic-storage bounds remain incomplete. Owned
container copying and cleanup remain incomplete. Neither this design document
nor the historical benchmark numbers establish production safety or performance.

## 1. Intended safety behavior and current limits

Mutable value semantics is Beryl's intended model. Current implementations of
owned collections still have aliasing and lifecycle gaps; M5 must establish their
contracts. Scalar initialization, moves, and access exclusivity have regression
coverage, but that is not a proof of complete memory safety.

| gap | Rust | Beryl |
|---|---|---|
| integer overflow | checks configurable per Cargo profile; explicit checked/wrapping operations | checked native integer arithmetic by default; explicit wrapping/saturating operations |
| uninitialized reads | safe Rust prevents uninitialized reads; unsafe `MaybeUninit` use has obligations | definite-initialization analysis; `set` requires assignment |
| bounds | safe indexing checks; unchecked operations have explicit unsafe obligations | generated checks for supported accesses; unsafe capability machinery remains proposed |
| null | `Option` | **there is no null in the language** |

Checked release arithmetic is a useful default, not a capability Rust lacks.
[Cargo profiles](https://doc.rust-lang.org/cargo/reference/profiles.html) expose
overflow-check configuration. Target-specific Enfusion integer behavior needs
separate validation; native checks do not prove engine arithmetic equivalence.

## 2. Granular unsafe

Rust's `unsafe` permits particular operations with additional obligations; it
does not disable the borrow checker or suspend every invariant.
[Unsafe Rust](https://doc.rust-lang.org/book/ch20-01-unsafe-rust.html).
Beryl proposes four separately named capabilities to make intended permissions
visible during review:

```beryl
@unsafe(unchecked_index) { }   // bounds checks only
@unsafe(raw_ptr)         { }   // ownership only
@unsafe(ffi)             { }   // foreign calls only
@unsafe(transmute)       { }   // type punning only
```

`forbid_unsafe = true` in `beryl.toml` refuses all four (`BE0605`), and the
**enfusion target forbids them by construction** (`BE0703`) — the engine has no
raw pointers, so there is nothing there to suspend.

None of the four is *implemented* in v0.1. They parse, they are audited, and
they are refused where forbidden; there is no raw-pointer or FFI machinery
behind them yet.

## 3. Supply chain, won by subtraction

- **No build scripts. Ever.** A dependency cannot execute code at build time.
- **No procedural macros.** `comptime` evaluation is a pure interpreter over
  integers, floats, bools and strings. There is no sandbox to escape because no
  I/O is implemented.
- **No dependency fetching in v0.1.** Explicit source sets are supported;
  general path-dependency resolution is not implemented by package metadata.

These restrictions limit build-time execution and dependency resolution. Their
performance effects require measurement against a specified alternative.

## 4. The taint engine

A bounded monotone analysis propagates provenance through the analyzed call graph
before reporting sinks. Record fields are separate local paths; indexed elements
share a conservative summary. Arguments, results and mutable parameters propagate
until stable, so loops and declaration order cannot silently hide a later source.
The initial interprocedural implementation is context-insensitive and can reject
safe programs conservatively. Symbolic call summaries remain planned.

```beryl
@untrusted     // every parameter arrived from a network or RPC boundary
@validator     // validation intent; body facts must justify each use
@secret        // every parameter is secret material
@constant_time // no secret-dependent branch or index, transitively
@server_only   // not reachable from client context
```

Sources are the parameters of a marked function. Taint propagates through
arithmetic, casts, field access and calls. Sinks are:

| sink | untrusted | secret |
|---|---|---|
| array or list index | `BE0601` | `BE0603` |
| `if` / `while` condition | — | `BE0602` |

`clamp`, `min`, `max` and `@validator` never erase provenance. The initial bounds
proof admits integer intervals within the actual fixed-array length. Constant
clamp bounds must be ordered and fit that array. Verified return expressions of
small bounded helpers can provide the same fact without an annotation. A bound
for a larger array, a bare validator, one-sided min/max and reversed clamp limits
do not establish a safe index. Dynamic-length proofs remain unavailable. Mutable
locals do not retain initializer range assumptions after possible mutation.

Secret-derived indices and control decisions (including short circuit and error/
optional selection) remain diagnostics even when an index is in bounds. Budget
exhaustion fails analysis with BE0608 rather than treating incomplete propagation
as success.

`@constant_time` additionally requires every callee to be `@constant_time`
(`BE0607`). This is a checked source restriction; no machine-level constant-time
guarantee is established. Similarly, `@server_only` call restrictions do not prove
runtime authority; engine request boundaries need separately verified contracts.

## 5. `beryl audit`

```
beryl audit
```

Reports the unsafe surface with file and line, which security attributes are in
play, and that build-time code execution is none by construction. Its footer
states plainly that this records what the code *declares* rather than proving
what it does. The word "safe" does not appear in the output, and that is
deliberate.

## 6. What is designed but not implemented

The spec describes **capability-based I/O**: `fn main(sys: Sys)`, with `Fs` and
`Net` as unforgeable zero-sized values that must be passed explicitly, so a
library that never receives one cannot touch the filesystem.

**None of that exists in v0.1.** There is also no I/O to protect — `print` is
the only output, and it is deliberate ambient authority matching EnforceScript's
own `Print`. When I/O lands, it lands behind capabilities; today the claim would
be vapour, so it is listed here as designed rather than in §1 as delivered.

## 7. The cost

Historical +82% and -4% figures are unverified: the old benchmark could time a
trapping workload and ignored failed execution. They must not support a security
or optimization decision. M8 requires equivalent semantics, checked outputs,
paired measurements, uncertainty, and full application costs. See
[BENCHMARKS.md](BENCHMARKS.md) for the historical record and the active plan for
the replacement protocol.

## 8. Reporting a problem

Beryl is a personal project, not a shipped product with a security team. If you
find something, the useful thing is a failing `.be` file that reproduces it.

Before relying on any of this for something that matters, read the residual
register in [THREAT-MODEL.md](THREAT-MODEL.md). In particular, **S1**: the
compiler is written in C, and that is the largest single item on its own threat
model.
