# Beryl's security model

Read [THREAT-MODEL.md](THREAT-MODEL.md) alongside this. This document says what
the model *does*; that one says where it stops, and the second half is the more
important of the two.

The headline: **almost all of this is free at runtime.** Taint analysis is
compile-time only, the supply-chain decisions make builds *faster*, and exactly
one item costs measurable runtime — which is measured, in
[BENCHMARKS.md](BENCHMARKS.md), and has an opt-out.

## 1. Memory safety, and Rust's remaining gaps

Mutable value semantics removes use-after-free, double-free, null, and
use-after-move. Three gaps that Rust leaves open, Beryl closes:

| gap | Rust | Beryl |
|---|---|---|
| integer overflow | panics in debug, **wraps silently in release** | **traps in every build**; `wrapping_*` / `saturating_*` opt out |
| uninitialized reads | `MaybeUninit` discipline | definite-initialization analysis; `set` forces the callee to assign |
| bounds | checked, `unsafe` opts out | checked, scoped capability opts out |
| null | `Option` | **there is no null in the language** |

Release-mode wraparound is the most defensible "stricter than Rust" claim
available. It is also the one that costs something: see §7.

## 2. Granular unsafe

Rust's `unsafe` suspends every invariant at once, which is why auditing it is
miserable. Beryl splits it into four capabilities, so an audit reads as a *set*
rather than a line count:

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
- **No dependency fetching in v0.1** — path dependencies only.

Every one of these makes compilation *faster*. Security and the lightness goal
point the same direction here, which is unusual and worth noticing.

## 4. The taint engine

One flow-sensitive walk over each function body, several policies. That reuse is
what made it affordable to build.

```beryl
@untrusted     // every parameter arrived from a network or RPC boundary
@validator     // this function's result is trustworthy
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

**`clamp`, `min` and `max` launder untrusted taint**, because bounding a value
is exactly what makes an attacker's index safe to use. They deliberately do
**not** launder a secret: bounding one still reveals it through timing.

`@constant_time` additionally requires every callee to be `@constant_time`
(`BE0607`) — the guarantee has to hold through the whole call graph or it does
not hold at all.

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

Measured, on the worst case we could construct — a dependent multiply-add chain
where every operation is checked and there is nothing to hide the branch behind:

| | |
|---|---|
| checked arithmetic | **+82%** versus unchecked C |
| `wrapping_*` | **−4%**, i.e. identical within noise |

So: correct by default costs about 2x in an arithmetic-bound inner loop, and the
opt-out costs nothing. Everything else in this document — taint, capabilities,
the supply-chain rules — is compile-time and costs zero.

The stated target was "< 3%". It was not met. See
[BENCHMARKS.md](BENCHMARKS.md).

## 8. Reporting a problem

Beryl is a personal project, not a shipped product with a security team. If you
find something, the useful thing is a failing `.be` file that reproduces it.

Before relying on any of this for something that matters, read the residual
register in [THREAT-MODEL.md](THREAT-MODEL.md). In particular, **S1**: the
compiler is written in C, and that is the largest single item on its own threat
model.
