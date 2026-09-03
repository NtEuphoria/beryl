# Beryl — Language & Toolchain Design

**Status:** approved design, normative for v0.1 · **Date:** 2026-09-03 · **Owner:** moham
**Repo:** `C:\Users\moham\Desktop\beryl`

Beryl is a systems language named for beryllium: stiffer than steel per unit weight, very
light, and dimensionally stable at temperature. That is the whole thesis — *stiff* (strong
static guarantees), *light* (small binaries, fast builds), *hot* (real-time game loops).

It compiles to two targets from one frontend: **native** (via C, handed to clang) and
**EnforceScript** (for Arma Reforger's Enfusion engine).

---

## 1. Goals, non-goals, and the honest comparison to Rust

### 1.1 Falsifiable goals

Every headline claim in this project must be measurable. These are the numbers v0.1 is held to.

| Metric | Rust today | Beryl target | Verified by |
|---|---|---|---|
| Hello-world binary | 150–300 KB | **< 20 KB** | `tests/bench/size` |
| Compiler binary | ~150 MB toolchain | **< 1 MB**, zero deps | `scripts/build.sh` output |
| Check 10k LOC (cold) | 3–6 s | **< 500 ms** | `tests/bench/check` |
| Full `-O2` 10k LOC | 15–30 s | **< 3 s** | `tests/bench/build` |
| Hot-loop codegen | baseline | **within 5% of hand-written C** | `tests/bench/perf` |
| Lifetime annotations | `'a` pervasive | **zero — none exist in the grammar** | by construction |
| Build-time code execution | `build.rs`, proc macros | **zero, structurally impossible** | by construction |
| Reproducible builds | opt-in, imperfect | **byte-identical output** | `tests/repro` |
| Overflow-trap overhead | n/a (wraps in release) | **< 3%, published** | `tests/bench/overflow` |

### 1.2 The honest comparison

Beryl and Rust are both AOT-compiled, GC-free, and monomorphized, and both hand off to LLVM.
**Expect parity on hot loops, not a miracle.** Anyone claiming a new language is broadly "2x
faster than Rust" at equivalent optimization level is selling something.

Where Beryl can genuinely win, and what this design targets:

1. **Compile speed** — Rust's real weakness. Beryl treats it as a design constraint, not an
   afterthought: arena allocation throughout the compiler, no proc macros, no build scripts,
   no trait-solver backtracking, and a C backend that lets clang do optimization only in
   release builds.
2. **Binary size and zero runtime** — no unwinding machinery, no landing pads, no
   `core::fmt` pulled in by a stray `Debug` derive. Failure aborts; it never unwinds.
3. **Same safety, zero lifetime annotations** — see §3.
4. **One real codegen edge** — every `inout` parameter lowers to a C `restrict` pointer with
   a compiler-proven exclusivity guarantee behind it. That is precisely the aliasing
   information LLVM most wants, and the thing Rust shipped with `noalias` disabled for years
   because getting it sound was hard.
5. **Stricter arithmetic** — Rust silently wraps on overflow in release builds. Beryl traps
   in every build (§8.1).

### 1.3 Non-goals for v0.1

Deliberately cut, and to be stated plainly in the docs rather than implied:

- **Concurrency.** Enfusion scripting is single-threaded; threads would compromise the
  exclusivity model for no v0.1 benefit. Deferred, and the aliasing rules are designed so it
  can be added soundly later.
- **Async/await.** Same reasoning.
- **A package registry.** Path and git dependencies only.
- **Self-hosting.** Designed for (§9.4), not attempted in v0.1.
- **Direct machine-code backend.** The C backend buys world-class optimization for free.
  A direct x64 backend for instant debug builds is v2.

---

## 2. Lexical structure and syntax

Rust-flavoured but lighter: no semicolons, no lifetime syntax, no turbofish, no `impl`
blocks. Methods are free functions declared on a type.

```beryl
module flight.pid

pub struct Pid {
    kp: f32, ki: f32, kd: f32
    integral_limit: f32
    integral: f32 = 0
    last_meas: f32 = 0
    has_last: bool = false
}

pub fn Pid.step(inout self, sp: f32, meas: f32, dt: f32, saturated: bool = false) -> f32 {
    if dt <= 0 { return 0 }

    let err = sp - meas
    if !saturated {
        self.integral = clamp(self.integral + err * dt,
                              -self.integral_limit, self.integral_limit)
    }

    var deriv: f32 = 0
    if self.has_last { deriv = -(meas - self.last_meas) / dt }
    self.last_meas = meas
    self.has_last = true

    return self.kp * err + self.ki * self.integral + self.kd * deriv
}
```

### 2.1 Tokens

- **Comments** — `//` to end of line; `//!` is a doc comment attached to the following item.
  No block comments (they nest badly and buy little).
- **Identifiers** — `[A-Za-z_][A-Za-z0-9_]*`. ASCII only in v0.1.
- **Integer literals** — `123`, `0xFF`, `0b1010`, `0o777`, with `_` separators. Suffixes
  `i8 i16 i32 i64 u8 u16 u32 u64` allowed.
- **Float literals** — `1.5`, `1e-9`, `1.5f32`. Default `f64` unless context demands `f32`.
- **String literals** — `"..."` with escapes `\n \t \r \\ \" \0 \xNN`. Raw strings `r"..."`.
- **Char literals** — `'a'`, type `char` (a Unicode scalar, 32-bit).
- **Keywords** — `module use pub fn struct enum trait impl let var if else while for in
  return break continue match test const comptime true false inout sink set as is`.

### 2.2 Statement termination

Newline terminates a statement when the expression is complete. A trailing binary operator
continues the line:

```beryl
return self.kp * err
     + self.ki * self.integral    // continues: previous line ended on an operator
```

This rule is the same one Swift uses, and it is unambiguous: the lexer emits a virtual
terminator at a newline **only** when the preceding token can end an expression and the
following token can begin one.

### 2.3 Grammar sketch (v0.1)

```
program     := module_decl item*
module_decl := "module" path
item        := attr* vis? (fn_decl | struct_decl | enum_decl | const_decl | test_decl | use_decl)
fn_decl     := "fn" (ident ".")? ident "(" params? ")" ("->" type)? block
params      := param ("," param)*
param       := conv? ident ":" type ("=" expr)?     // conv on non-self params
             | conv? "self"                          // method receiver
conv        := "let" | "inout" | "sink" | "set"
struct_decl := "struct" ident generics? "{" field* "}"
field       := ident ":" type ("=" expr)?
enum_decl   := "enum" ident "{" variant ("," variant)* "}"
type        := path generics? | "[" type ";" expr "]" | type "?"
stmt        := let_stmt | var_stmt | expr_stmt | if | while | for | return | break | continue
expr        := assign
```

Precedence, loosest to tightest: `|| && == != < <= > >= | ^ & << >> + - * / % unary call/field`.

---

## 3. Memory model — mutable value semantics

**The rule that removes lifetimes:** every value has exactly one owner, and references are
*second-class* — they cannot be stored in a struct, returned from a function, or placed in a
container. A borrow therefore can never outlive the call it was passed to. There is nothing
to annotate and nothing to infer.

### 3.1 Passing conventions

| Convention | Meaning | Lowers to (C) | Lowers to (EnforceScript) |
|---|---|---|---|
| `let` (default) | immutable borrow; callee may read | `const T* restrict` | plain parameter |
| `inout` | exclusive mutable borrow, **guaranteed non-aliasing** | `T* restrict` | `inout` / `out` parameter |
| `sink` | ownership transferred to callee | by value, caller's copy dead | parameter + caller nulls its `ref` |
| `set` | out-parameter; callee **must** initialize before returning | `T* restrict` uninit on entry | `out` parameter |

Small scalars (`≤ 16` bytes, no destructor) pass by value regardless; the convention still
governs *semantics*, and the ABI choice is the backend's.

Locals are `let` (immutable) or `var` (mutable). Returns are always owned values.

### 3.2 The exclusivity law

While an `inout` borrow of a storage location is active, no other read or write of that
location may occur. This is checked statically for locals, parameters, and field paths.
Two `inout` arguments in the same call may not alias — which is what licenses `restrict`.

```beryl
swap(inout a, inout a)   // BE0401: overlapping exclusive borrows of `a`
```

### 3.3 Sharing without stored references

Because references cannot be stored, shared and cyclic structures use explicit handles:

| Type | Use | Native | Enfusion |
|---|---|---|---|
| `Box<T>` | unique heap ownership | malloc/free | `ref T` |
| `Rc<T>` | opt-in reference counting | refcount | **`ref T` — free**, the engine already refcounts |
| `Pool<T>` + `Handle<T>` | graphs, entity stores, observers | dense array + generational index | `array<ref T>` + int index |

`Handle<T>` is a generational index: 32-bit slot plus 32-bit generation. A stale handle is
detected on access rather than dangling. This is the idiomatic answer to "but I need a graph"
and it is *faster* than pointer chasing, not slower.

### 3.4 Initialization and drop

- **Definite initialization** is checked on every path. Reading a possibly-uninitialized
  binding is `BE0302`.
- **Drop** runs at end of scope in reverse declaration order. `sink` moves out; a moved-from
  binding is dead and using it is `BE0403`.
- **No destructors that can fail.** `drop` returns `void` and may not error.

---

## 4. Type system

### 4.1 Primitives

`i8 i16 i32 i64` · `u8 u16 u32 u64` · `f32 f64` · `bool` · `char` · `str` · `void`

Plus built-in game math, first-class because Enfusion has `vector` natively:
`Vec2 Vec3 Vec4 Quat Mat3 Mat4`.

`str` is an immutable UTF-8 slice. Owned strings are `String`.

### 4.2 Aggregates

- `struct` — value type, fields may carry defaults, layout is declaration order unless
  `@layout(packed)` or `@layout(soa)`.
- `enum` — C-like in v0.1 (integer-backed, explicit discriminants allowed). Payload-carrying
  variants are v0.2 (they lower to tag + union natively, tag + fields on Enfusion).
- `[T; N]` — fixed array, `N` const-evaluated.
- `T?` — `Option<T>`. **There is no null.**
- `!T` — error union (§5).

### 4.3 Generics

Monomorphized, always. Constrained by `trait`:

```beryl
trait Ord { fn cmp(let self, let other: Self) -> i32 }

pub fn max<T: Ord>(let a: T, let b: T) -> T {
    if a.cmp(b) >= 0 { return a }
    return b
}
```

Static dispatch by default. `dyn Trait` requires explicit opt-in and is **forbidden on the
enfusion target in v0.1** (it maps to a virtual class hierarchy; deferred to v0.2).

Monomorphization is not merely an optimization here — EnforceScript has no user-defined
generics, so it is mandatory for that backend. This is a case where the two targets pushed
the design in the same direction.

### 4.4 Inference

Local, bidirectional, function-local only. Signatures are always explicit — no global
inference, no HM unification across items. This is a deliberate compile-speed decision and
it makes error messages dramatically better.

---

## 5. Errors — values, never unwinding

```beryl
fn parse_port(s: str) -> !u16 {
    let n = try parse_u32(s)              // propagate on error
    if n > 65535 { return error.OutOfRange }
    return n as u16
}

let port = parse_port(arg) orelse 8080     // supply a default
let port = parse_port(arg) catch |e| {     // handle explicitly
    log("bad port: {}", e)
    return
}
```

- An error is an `i32` tag from a global error set. **Zero allocation.**
- `!T` is returned as a tagged pair; for pointer-sized `T` the backend packs it.
- **Failure aborts, never unwinds.** No landing pads, no `.eh_frame`, no personality
  routine. This is where most of the binary-size win comes from.
- `panic(msg)` is for genuine bugs only (failed invariant), and aborts.

On the enfusion target, `!T` lowers to `bool` return plus an `out` parameter — the exact
idiom the base game already uses.

---

## 6. Modules and packages

```beryl
module mesh.store
use core.collections.List
use flight.pid.Pid
```

- One module per file; the path mirrors the directory.
- `pub` controls visibility. Default is module-private.
- **No circular module dependencies.** Enforced, and it is what keeps the resolver a single
  topological pass rather than a fixpoint.

`beryl.toml`:

```toml
[package]
name    = "sparkos_mesh"
version = "0.1.0"

[target.enfusion]
prefix  = "SPK"                 # class-name prefix; Enfusion has no namespaces
out     = "../SparkOS_Mesh/scripts/Game/SparkOSMesh"

[security]
forbid_unsafe = true
capabilities  = []              # declared, enforced, audited

[dependencies]
mathx = { path = "../mathx" }
```

---

## 7. Backends

```
.be → lex → parse → resolve → typecheck → monomorphize → ownership → MIR
                                                                      ├─→ C → clang → .exe
                                                                      └─→ EnforceScript .c → Workbench
```

MIR is shared. Both backends want explicit copies, explicit drops, and desugared control
flow, so that lowering happens exactly once.

### 7.1 Native backend

Emits C11 to a temp dir, invokes clang. Debug builds use `-O0 -g`; release uses
`-O2 -fno-unwind-tables -fno-asynchronous-unwind-tables`. `inout` becomes `restrict`.
The runtime (`runtime/beryl_rt.c`) is ~200 lines: abort handler, bounds trap, overflow trap,
allocator shim. Nothing else.

### 7.2 Enfusion backend

| Beryl | EnforceScript |
|---|---|
| `struct` | `class` (plus paired `...Class` for components) |
| `module flight.pid` | prefix-mangled `SPK_Flight_Pid` (no namespaces exist) |
| `Store<Entity>` | monomorphized → `SPK_Store_Entity` |
| `List<T>` / `Map<K,V>` | intrinsic `array<T>` / `map<K, ref V>` |
| `Vec3` | native `vector` |
| `T?` | nullable class ref, or sentinel for primitives |
| `!T` | `bool` return + `out` parameter |
| `Rc<T>` | `ref T` — free |
| `Box<T>` | `ref T` |
| `i64 u64 u32 u16 u8 i16 i8` | **`BE0701`: type unsupported on enfusion target** |
| `dyn Trait` | **`BE0702`: deferred to v0.2** |
| raw pointers, all `@unsafe` | **`BE0703`: forbidden by construction** |

Output conventions, non-negotiable because Workbench is strict:

- **UTF-8 with no BOM.** (PowerShell's `Out-File -Encoding utf8` emits one; the backend
  writes bytes directly.)
- **Tabs**, matching Bohemia's own formatting.
- One class per file, filename matching the class.
- Every emitted name carries the configured prefix.

The profile lint runs *before* emission. Beryl refuses at compile time what the engine
cannot express, rather than emitting `.c` that dies 15 seconds later inside a cascade of
phantom errors in untouched base-game files.

### 7.3 Why this matters for the Reforger workflow

Today, verifying pure logic in a mod costs a 10–15 s Workbench build in which one real error
produces a documented cascade of phantom errors across base-game files. With Beryl:

```
beryl test               # PID, mixer, guidance, store — native, milliseconds
beryl build -t enfusion  # emits SPK_*.c, tabs, no BOM, ready for Workbench
```

Workbench only ever sees code that already type-checked, ownership-checked, and passed the
profile lint.

---

## 8. Security model

Almost all of it is free at runtime: capabilities are zero-sized and erase at codegen, taint
analysis is compile-time only, and the supply-chain decisions make builds *faster*. Exactly
one item costs measurable runtime, and it is priced in §8.6 S5.

### 8.1 Memory safety — closing Rust's remaining gaps

| Gap | Rust | Beryl | Cost |
|---|---|---|---|
| Integer overflow | panics in debug, **silently wraps in release** | **traps in every build**; `wrapping_*` / `saturating_*` / `unchecked_*` opt-outs | ~1–3% |
| Uninitialized reads | `MaybeUninit` discipline | definite-init analysis; `set` forces callee init | zero |
| Bounds | checked, `unsafe` opt-out | checked, scoped-capability opt-out | same |
| Null | `Option` | **no null in the language** | zero |

### 8.2 Granular unsafe

Rust's `unsafe` suspends every invariant at once. Beryl splits it into four capabilities, so
an audit reads as a set rather than a line count:

```beryl
@unsafe(unchecked_index) { ... }   // bounds checks only
@unsafe(raw_ptr)         { ... }   // ownership only
@unsafe(ffi)             { ... }   // foreign calls only
@unsafe(transmute)       { ... }   // type punning only
```

Packages declare their unsafe surface in `beryl.toml`; `beryl audit` reports the transitive
set. `forbid_unsafe = true` is enforceable per package, and the **enfusion target forbids all
four by construction**.

### 8.3 Supply chain — won by subtraction

- **No build scripts. Ever.** A dependency cannot execute code at build time.
- **No proc macros.** `comptime` is a sandboxed pure evaluator: no I/O, no syscalls, bounded
  steps and memory, deterministic.
- **Content-hashed lockfile** (BLAKE3), vendored by default.
- **Reproducible builds** — byte-identical output from identical input.

Each of these makes compilation faster. Security and lightness point the same way here.

### 8.4 No ambient authority

I/O requires an unforgeable capability *value*, and capabilities originate only in `main`:

```beryl
fn main(sys: Sys) -> !void {
    let cfg = try read_config(sys.fs)
    run_solver(cfg)                     // no capability => cannot perform I/O
}
```

`Sys`, `Fs`, `Net`, `Clock`, `Rand` are zero-sized types and vanish entirely at codegen.

### 8.5 One taint engine, three policies

A single flow-sensitive dataflow analysis over MIR, reused three ways:

| Policy | Rule | For |
|---|---|---|
| `@untrusted` | network/RPC values may not reach an index, allocation size, or spawn count without passing a validator | Reforger RPC boundaries |
| `Secret<T>` | secret-derived values may not drive branches or memory indices | crypto (Lethe-class) |
| capability flow | capabilities may not be stashed in globals to manufacture ambient authority | §8.4 |

Plus `@server_only`: calling such a function from client context is a compile error rather
than a runtime desync.

### 8.6 Residual register

Following the Lethe convention. **Nothing here is marked "sealed."**

| # | Risk | Mechanism | Status | Residual |
|---|---|---|---|---|
| **S1** | Compiler is written in C, a memory-unsafe language | Arena-only allocation (no `free` bugs by construction), bounds-checked internal containers, ASan/UBSan CI, fuzzed lexer/parser | **BOUNDED** | Real. The only input is source files, but a crafted `.be` could in principle crash or corrupt the compiler. **IRREDUCIBLE until self-hosted** — which is the actual argument for self-hosting. |
| **S2** | Capabilities are erased at codegen | Type-system enforcement + manifest declaration + `beryl audit` | **BOUNDED** | Capabilities bind what compiled Beryl code can *express*, not what machine code can *do*. One `@unsafe(ffi)` block escapes the model entirely. `forbid_unsafe` is the only hard control. |
| **S3** | Static taint analysis is incomplete | Flow-sensitive over MIR, conservative at merge points | **BOUNDED** | A strong lint, **not a proof**. Indirect flows through handles or computed indices defeat it. Soundness must never be claimed. |
| **S4** | Constant-time code survives Beryl's backend, not necessarily clang's | `@constant_time` forbids secret-dependent branches and indices at source; emits optimization barriers | **BOUNDED, weakly** | LLVM may reintroduce branches Beryl forbade, and routing through C makes this harder to control, not easier. v1 is source-level plus barriers; machine-level verification is v2. For crypto, treat as a lint and read the assembly. |
| **S5** | Overflow trapping costs performance | `unchecked_*` opt-out, benchmarked and published | **ACK** | ~1–3% on arithmetic-dense code. Accepted deliberately: correct by default, fast by request. |
| **S6** | Enfusion output runs inside an engine Beryl does not control | Profile lint, `@server_only`, `@untrusted` | **BOUNDED** | Beryl can guarantee properties of the *generated script*, never of the engine executing it. Enfusion's own sandbox is the outer boundary. |

---

## 9. Compiler implementation

### 9.1 Architecture

Written in C11, built by clang into a single dependency-free binary.

```
src/common   arena.c str.c vec.c map.c diag.c source.c   — infrastructure
src/lex      lexer.c token.c
src/parse    parser.c ast.c
src/sema     resolve.c types.c infer.c check.c ownership.c monomorph.c constfold.c taint.c
src/ir       hir.c mir.c
src/opt      constprop.c dce.c inline.c
src/back     c_backend.c enforce_backend.c
src/driver   main.c build.c test.c fmt.c audit.c manifest.c
runtime/     beryl_rt.{h,c}                              — ~200 lines
lib/         core/ collections/                          — stdlib, written in Beryl
```

### 9.2 Memory management in the compiler

**Arena allocation throughout, freed wholesale at exit.** This is the standard fast-compiler
technique and it simultaneously eliminates nearly all of C's memory-bug surface: there are no
`free` calls to get wrong, and no ownership questions between compiler passes. Internal
containers are bounds-checked in debug builds.

### 9.3 Diagnostics

Held to a Rust-grade bar: caret spans, stable error codes (`BE0304`), and a `note:`/`help:`
line where one genuinely helps. Every code is documented in `docs/DIAGNOSTICS.md`.

```
error[BE0401]: overlapping exclusive borrows of `a`
  --> src/main.be:12:10
   |
12 |     swap(inout a, inout a)
   |          ^^^^^^^^  ^^^^^^^ second exclusive borrow here
   |          |
   |          first exclusive borrow here
   |
   = note: `inout` guarantees non-aliasing, which is what licenses `restrict` in codegen
   = help: copy one side first: `var t = a` then `swap(inout t, inout a)`
```

### 9.4 Self-hosting path

The native backend emits C; the compiler is written in C. Porting the compiler to Beryl is
therefore a natural later step, and it is the only real answer to residual **S1**. The
codebase avoids C constructs with no Beryl equivalent so that port stays cheap.

---

## 10. Testing strategy

TDD throughout — test first at every stage.

| Layer | Form | Location |
|---|---|---|
| Compiler internals | C unit tests, no framework | `tests/unit` |
| Lexer / parser | golden token and AST dumps | `tests/golden` |
| Diagnostics | `.be` in → expected error text out | `tests/golden/diag` |
| Native codegen | compile, run, compare stdout | `tests/e2e` |
| Enfusion codegen | golden `.c` output | `tests/golden/enfusion` |
| Language-level | `test "..." { }` blocks run natively | `lib/`, `examples/` |
| Robustness | fuzzed lexer and parser | `tests/fuzz` |

The Enfusion backend's end-to-end proof is a generated mod put through the real
`Invoke-ReforgerBuild.ps1` loop. A golden file proves the text is what was expected; only
Workbench proves it compiles.

---

## 11. Delivery phases

| Phase | Content | Done when |
|---|---|---|
| 0 | arena, str, vec, map, diag, source, test harness, build script | `beryl --version` runs; unit tests pass |
| 1 | lexer | golden token dumps pass |
| 2 | parser + AST + pretty-printer | golden AST dumps pass; `beryl fmt` works |
| 3 | resolver, types, inference, traits, generics, monomorphization, const-eval | golden diagnostics pass |
| 4 | ownership + exclusivity + definite-init | golden diagnostics pass |
| 5 | MIR lowering | MIR dumps stable |
| 6 | C backend + runtime + clang driver | `beryl run` executes; e2e stdout tests pass |
| 7 | Enfusion backend + profile lint | golden `.c` matches; real Workbench build succeeds |
| 8 | stdlib (core, collections), `beryl new/build/run/test/fmt/audit` | stdlib tests pass |
| 9 | security passes: taint engine, capabilities, `beryl audit` | security golden tests pass |
| 10 | docs: SPEC, TOUR, CHEATSHEET, ENFUSION, FROM-RUST, FROM-ENFORCE, DIAGNOSTICS, INTERNALS, THREAT-MODEL, SECURITY | all written; reference artifact published |

---

## 12. Open questions deferred to v0.2

Recorded here so they are not silently forgotten:

1. Payload-carrying enum variants and exhaustive `match`.
2. `dyn Trait` on the enfusion target (maps to a virtual class hierarchy).
3. Concurrency, and whether exclusivity extends to a `Send`/`Sync` equivalent.
4. Machine-level constant-time verification (residual S4).
5. Direct x64 backend for instant debug builds.
6. Self-hosting (residual S1).
