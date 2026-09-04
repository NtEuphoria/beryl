# Coming from Rust

Most of what you know transfers. The memory model is the interesting difference,
and it is simpler than you expect.

## Side by side

| Rust | Beryl |
|---|---|
| `fn f(x: &T)` | `fn f(let x: T)` |
| `fn f(x: &mut T)` | `fn f(inout x: T)` |
| `fn f(x: T)` (moves) | `fn f(sink x: T)` |
| `f(&x)` / `f(&mut x)` | `f(x)` / `f(inout x)` |
| `impl Foo { fn bar(&self) }` | `fn Foo.bar(let self)` |
| `let mut x` | `var x` |
| `Option<T>` | `T?` |
| `Result<T, E>` | `!T` (the error set is global) |
| `?` | `try` |
| `.unwrap_or(d)` | `orelse d` |
| `Vec<T>` | `List<T>` |
| `HashMap<K,V>` | `Map<K,V>` |
| `struct`, `enum` (C-like) | the same |
| `match` | ✗ v0.2 |
| `trait` | parses; not usable in v0.1 |
| `fn f<T: Ord>()` | parses; **not instantiated** in v0.1 (`BE0508`) |
| `'a` lifetimes | **do not exist** |
| `unsafe { }` | `@unsafe(raw_ptr) { }` — one capability at a time |
| `#[cfg]`, macros | ✗ and deliberately so |
| `build.rs` | ✗ and deliberately so |

## The memory model: no lifetimes at all

Rust lets a reference be stored, returned, and put in containers, which is
exactly why it needs lifetimes to describe how long each one lives.

Beryl makes references **second-class**: a borrow cannot be stored in a struct,
returned from a function, or placed in a container. It therefore cannot outlive
the call it was passed to, so there is nothing to annotate and nothing to infer.

```rust
// Rust: the annotation exists because the reference escapes
struct Iter<'a> { inner: &'a Store, idx: usize }
fn find<'a>(&'a self, id: &str) -> Option<&'a Entity>;
```

```beryl
// Beryl: it cannot escape, so the question never arises
fn peek(let store: Store, id: str) -> Entity?
```

The price is real and worth knowing: **you cannot build a graph out of stored
references.** The idiom is an index or a handle into a pool. In v0.1 that means
an array index; `Pool<T>` and `Handle<T>` are designed but not implemented
(`BE0902`).

What you get for it: no `'a`, no variance, no `PhantomData`, no
`E0597 borrowed value does not live long enough`, and a checker small enough to
read in an afternoon.

The guarantees you keep: no use-after-free, no double-free, no null, no
use-after-move, no data race from aliasing. `f(inout p, inout p.x)` is refused
just as `&mut` aliasing would be, while `f(inout p.x, inout p.y)` is allowed,
because the paths are disjoint.

## Where Beryl is stricter

**Overflow traps in release.** Rust wraps silently there, which is a real source
of vulnerabilities. Beryl traps in every build; `wrapping_add` and
`saturating_add` are the opt-out and they cost nothing measurable.

**No implicit numeric conversion, not even widening.** Rust already requires
`as` between integer types; Beryl extends that to every numeric pair and to
literals in ambiguous positions.

**No chained comparison.** `a < b < c` is an error, not a parse.

**`@unsafe` is granular.** Rust's `unsafe` suspends every invariant at once,
which is why auditing it is miserable. Beryl splits it into `raw_ptr`,
`unchecked_index`, `ffi` and `transmute`, so an audit reads as a set rather than
a line count — and `forbid_unsafe = true` in `beryl.toml` refuses all four.

**No build-time code execution.** No `build.rs`, no procedural macros. A
dependency cannot run anything while you build. `comptime` evaluation is a pure
interpreter with no I/O implemented, so there is no sandbox to escape.

## Where Rust is far ahead, and will stay so for a while

Be clear-eyed: Beryl v0.1 has **no working generics**, no traits, no `match`, no
concurrency, no async, no ecosystem, no LSP, and a compiler written in C that is
the largest single item on its own [threat model](THREAT-MODEL.md). Rust has all
of those solved and a decade of hardening behind them.

On generated code quality, both are AOT, GC-free, monomorphized, and both hand
off to LLVM. Expect **parity on hot loops**. The one structural edge Beryl has
is that every `inout` lowers to a `restrict` pointer with a compiler-proven
exclusivity guarantee — the aliasing information LLVM most wants, and the thing
Rust shipped with `noalias` disabled for years while it got it right.

## Habits to unlearn

- Reach for an **index**, not a stored reference.
- Write `var`, not `let mut`.
- The convention goes at the **call site** too: `f(inout x)`, not `f(&mut x)`.
- There is no `;`. A line break ends a statement.
- There is no turbofish; generic arguments are inferred (when generics land).
- `self` is explicit in the signature but implicit at the call: `p.bump()`.
