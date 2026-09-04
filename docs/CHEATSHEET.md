# Beryl cheatsheet

Everything on one page. `✗` marks what v0.1 does not have; each of those gives a
clear diagnostic rather than odd behaviour.

## Skeleton

```beryl
//! Doc comment for the module.

module flight.pid          // one module per file, path mirrors directories
use core.math.clamp        // import (flat namespace in v0.1)

pub struct Pid {           // `pub` or module-private
    kp: f32                // fields separate on a newline or a comma
    ki: f32 = 0            // defaults are const-evaluated
}

pub fn Pid.step(inout self, sp: f32, dt: f32) -> f32 {
    return self.kp * sp
}

fn main() { }              // native entry point

test "it works" {          // runs under `beryl test`, natively
    assert(1 + 1 == 2)
}
```

## Passing conventions — the whole memory model

| | means | you write at the call site |
|---|---|---|
| `let x: T` | read-only borrow (**default**) | `f(x)` |
| `inout x: T` | exclusive, non-aliasing borrow | `f(inout x)` |
| `sink x: T` | ownership moves in | `f(sink x)` |
| `set x: T` | out-parameter; callee **must** assign it | `f(set x)` |

A borrow **cannot** be stored in a struct, returned, or put in a container.
That single restriction is why there are no lifetimes.

```beryl
let a = 1        // immutable binding
var b = 1        // mutable binding
var c: i32       // declared now, assigned before any read (checked)
```

## Types

```
i8 i16 i32 i64   u8 u16 u32 u64   f32 f64   bool   char   str   void
Vec2 Vec3 Vec4 Quat Mat3 Mat4     [T; N]    T?     !T
List<T>          Map<K,V>         Box<T> Rc<T> Pool<T> Handle<T>  ✗ (native)
```

- `[T; N]` — fixed array, `N` is const-evaluated
- `T?` — optional. **There is no null.**
- `!T` — error union: a tag plus a value, no allocation, no unwinding
- `Map<K,V>` works on the enfusion target; native is v0.2
- **No implicit conversion, ever.** `a as i64` is how you convert.

## Control flow

```beryl
if c { } else if d { } else { }
while c { }
for i in 0..n { }            // half-open
for v in arr { }             // array or List
break     continue     return x     defer cleanup()
```

## Errors

```beryl
fn parse(let s: str) -> !i32 {
    if s == "" { return error.Empty }
    return 1
}

let a = try parse(s)              // propagate; caller must return !T too
let b = parse(s) orelse 0         // supply a fallback
let c = parse(s) catch |e| { }    // handle it
```

Failure **aborts, never unwinds**. No landing pads, no `.eh_frame`.

## Arithmetic

Integer overflow **traps in every build**, release included. Bounds are checked.
Division by zero traps.

```beryl
wrapping_add(a, b)    wrapping_sub(a, b)    wrapping_mul(a, b)
saturating_add(a, b)  saturating_sub(a, b)
```

These are the opt-out, and they cost nothing measurable
([BENCHMARKS](BENCHMARKS.md)).

## Built-ins

```beryl
print(x)   println(x)   println()   assert(cond)
min(a,b)   max(a,b)     clamp(x,lo,hi)   abs(x)   sqrt(x)
```

`List<T>`: `.len()` `.push(v)` `.get(i)` `.set(i,v)` `.clear()`

A user function of the same name shadows any built-in.

## Attributes

| | |
|---|---|
| `@untrusted` | parameters are attacker-controlled; they may not index unbounded |
| `@validator` | this function launders untrusted values |
| `@secret` | parameters must not drive a branch or a memory index |
| `@constant_time` | and every function it calls must be too |
| `@server_only` | not reachable from client context |
| `@unsafe(cap)` | `raw_ptr` · `unchecked_index` · `ffi` · `transmute` |

`clamp`, `min` and `max` launder *untrusted* taint — bounding is what makes an
attacker's index safe. They do **not** launder a *secret*; bounding one still
reveals it through timing.

## CLI

```
beryl new <name>                 scaffold a package
beryl check [files]              parse, type-check, ownership, security
beryl build [files]              compile
beryl run   [files]              compile and run
beryl test  [files]              run every test block natively
beryl audit [files]              report the declared security surface
beryl fmt [--check] <files>      canonical formatting
beryl ast <file>                 dump the syntax tree

  --release        -O2, no unwind tables
  --emit-c         keep the generated C
  -o <path>        output executable
  -t enfusion      emit EnforceScript instead of native code
  --prefix P       class-name prefix for enfusion
  --out-dir D      where to write EnforceScript
```

With a `beryl.toml` present, every command works with **no file arguments** and
reads `src/*.be`.

## beryl.toml

```toml
[package]
name    = "sparkos_mesh"
version = "0.1.0"

[target.enfusion]
prefix = "SPK"
out    = "../SparkOS_Mesh/scripts/Game/SparkOSMesh"

[security]
forbid_unsafe = true
```

## Syntax gotchas

- **No semicolons.** A line break ends a statement; a trailing or leading
  operator continues it.
- **K&R braces.** `{` goes on the same line — `beryl fmt` enforces it.
- **`a < b < c` is an error**, not a chain.
- Struct literals are disabled inside an `if`/`while`/`for` condition, so
  `if p {` is a block. Parenthesise to re-enable: `if (P{ x: 1 }).x {`.
- A reserved word is a valid **member** name: `xs.set(i, v)` parses.
- No turbofish. Generic arguments are inferred.

## Not in v0.1

`fn f<T>(...)` user generics (BE0508) · `trait` bodies · `Map` methods ·
payload enums and `match` · `Box`/`Rc`/`Pool`/`Handle` (BE0902) · `Map` natively
(BE0901) · concurrency · capability-based I/O · `dyn`
