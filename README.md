# Beryl

A systems language named for beryllium: stiffer than steel per unit weight, very
light, and dimensionally stable at temperature. That is the thesis — **stiff**
(strong static guarantees), **light** (small binaries, fast builds), **hot**
(real-time game loops).

One source, two targets:

```
.be ─┬─→ C ──→ clang ──→ native executable
     └─→ EnforceScript ──→ Arma Reforger Workbench
```

Which means you can write mod logic once, test it natively in **milliseconds**,
and ship EnforceScript that Workbench compiles — instead of paying a 10–15 second
Workbench build to find out whether your PID controller works.

```bash
beryl new mymod
cd mymod
beryl test                    # test blocks, run natively
beryl run                     # build and run
beryl build -t enfusion --prefix SPK --out-dir ../MyMod/scripts/Game/MyMod
```

## The five ideas

**No lifetime annotations, and none needed.** Every value has one owner, and
references are *second-class*: a borrow cannot be stored in a struct, returned,
or put in a container. So a borrow can never outlive the call it was passed to,
there is nothing to annotate, and what remains is ordinary flow analysis rather
than a borrow checker.

```beryl
fn publish(inout store: MeshStore, sink e: Entity) -> bool
//         ^^^^^ exclusive, non-aliasing   ^^^^ ownership moves in
```

**Overflow traps in every build.** Rust wraps silently in release, which is a
real source of vulnerabilities. Beryl traps — and when you actually need the
speed, `wrapping_add` and friends say so at the call site. On the worst case we
could construct, checking costs +82% and the opt-out costs nothing
([BENCHMARKS](docs/BENCHMARKS.md)).

**No implicit numeric conversion, ever.** Not even widening. `i32 + i64` is an
error with the cast in the help line.

**Security is a compile-time property.** `@untrusted` marks RPC parameters as
attacker-controlled and refuses to let them index anything unbounded.
`@server_only` refuses to be called from client context. `@secret` refuses to
drive a branch. All compile-time, all zero runtime cost — and
[honestly bounded](docs/THREAT-MODEL.md): it is a strong lint, never a proof.

**No build scripts, no procedural macros.** A dependency cannot execute code at
build time. That is not a feature that was added; it is one that was never
allowed, and it happens to make builds faster too.

## Documentation

| | |
|---|---|
| [CHEATSHEET](docs/CHEATSHEET.md) | one page, everything |
| [TOUR](docs/TOUR.md) | the language in twenty minutes |
| [SPEC](docs/SPEC.md) | the normative reference |
| [ENFUSION](docs/ENFUSION.md) | the Arma Reforger workflow |
| [FROM-ENFORCE](docs/FROM-ENFORCE.md) | coming from EnforceScript |
| [FROM-RUST](docs/FROM-RUST.md) | coming from Rust |
| [DIAGNOSTICS](docs/DIAGNOSTICS.md) | every `BE####` code |
| [SECURITY](docs/SECURITY.md) | the security model |
| [THREAT-MODEL](docs/THREAT-MODEL.md) | the residual register |
| [BENCHMARKS](docs/BENCHMARKS.md) | measured, including the misses |
| [STATUS](docs/STATUS.md) | what works and what does not |
| [INTERNALS](docs/INTERNALS.md) | how the compiler is built |
| [BUILDING](docs/BUILDING.md) | building the compiler |

## Where it stands

v0.1 is real but not finished. It compiles and runs real programs on both
targets, and the EnforceScript it emits **compiles cleanly in the actual Arma
Reforger Workbench** (`scripts/reforger-proof.ps1` proves it on demand).

| | |
|---|---|
| Compiler | 297 KB, C11, **zero dependencies** |
| Compiler source | ~11,800 lines |
| Tests | 204 cases, 931 checks, 9 end-to-end programs |
| Check 10,000 lines | 124 ms |
| Build 10,000 lines | 2.3 s including `clang -O2` |
| Hello-world binary | 91.6 KB, of which **3.6 KB is Beryl** (the rest is the C runtime floor) |

**Not in v0.1:** user-defined generics, traits beyond parsing, `Map` methods,
payload-carrying enums and `match`, `Box`/`Rc`/`Pool`/`Handle`, concurrency, and
the capability-based I/O the security model describes — there is no I/O at all
yet beyond `print`. Each of these produces a clear diagnostic rather than
mysterious behaviour. [STATUS](docs/STATUS.md) is the full list.

## Honesty about "better than Rust"

Both are AOT, GC-free, monomorphized, and both hand off to LLVM, so on hot loops
expect **parity, not a miracle**. Where Beryl genuinely differs:

- **Stricter arithmetic** — release-mode wraparound is a real Rust footgun, and
  Beryl does not have it.
- **No lifetime annotations** for the same class of memory safety.
- **No build-time code execution**, structurally.
- **Compile speed** — a design constraint rather than an accident.

And where it does not: Beryl is a v0.1 with no generics, no traits, no
concurrency, no ecosystem, and a compiler written in C that is itself the
largest item on its own threat model. Rust is none of those things.
