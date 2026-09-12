# Beryl language reference

Language contracts are normative within their explicitly admitted version and
target. A compiler disagreement requires a conformance test and a recorded
implementation deviation; observed output alone does not define the language.
Current admission and remaining gaps are recorded in `BERYL_DELIVERY_STATE.md`
and the installed checkpoint's capability/evidence records. The design rationale lives in
`docs/superpowers/specs/2026-09-03-beryl-language-design.md`; this is the
reference you consult when you need the exact rule.

Anything marked **v0.2** is not implemented and produces a diagnostic.

---

## 1. Lexical structure

**Encoding.** UTF-8. Identifiers are ASCII in v0.1.

**Comments.** `//` to end of line. `//!` is a doc comment attached to the
following item or field. Block comments do not exist (`BE0107`).

**Identifiers.** `[A-Za-z_][A-Za-z0-9_]*`.

**Keywords.** `module use pub fn struct enum trait let var if else while for in
return break continue test const comptime true false inout sink set as try catch
orelse error defer self match`

A keyword is accepted wherever a **field or method name** is expected, because
nothing but a name can follow a `.`, so `xs.set(i, v)` is unambiguous.

**Integer literals.** `123`, `0xFF`, `0b1010`, `0o777`, with `_` separators.
Optional suffix `i8 i16 i32 i64 u8 u16 u32 u64`. A literal that does not fit in
64 bits is `BE0106`.

**Float literals.** `1.5`, `1e-9`, `2.5E+3`, with optional `f32`/`f64` suffix. A
`.` begins a fraction only when a digit follows, so `1..2` is `1`, `..`, `2`.
An integer literal with a float suffix is a float: `1f32` is `1.0f`.

**String literals.** `"..."` with escapes `\n \t \r \0 \\ \" \' \xNN`. Raw
strings `r"..."` take no escapes. Neither may span a line.

**Char literals.** `'a'`, `'\n'`, `'\x41'`. Type `char`, a 32-bit scalar.

### 1.1 Statement termination

There are no semicolons. A line break terminates a statement when **all** hold:

1. bracket depth for `(` and `[` is zero;
2. the previous significant token can end an expression — a literal, an
   identifier, `self`, `)`, `]`, `}`, `?`, `break`, `continue`, `return`;
3. the next significant token is not a continuation — not a binary operator,
   `.`, `..`, `as`, `,`, `:`, `->`, `=>`, an assignment operator, `)`, `]`, `}`,
   `else`, `catch`, or `orelse`.

Consecutive breaks collapse. So both of these are one statement:

```beryl
return self.kp * err
     + self.ki * self.integral

let total = a +
            b
```

Because a `>` closing a generic type can never end an *expression*, rule 2
suppresses the terminator after `List<i32>`. The parser therefore also accepts a
**real line break** as a statement or member separator, which is what makes
this work:

```beryl
struct S {
    items: List<i32>
    count: i32
}
```

---

## 2. Modules

One module per file; the path mirrors the directory structure.

```beryl
module flight.pid
use core.math.clamp
```

`pub` makes an item visible outside its module; the default is module-private.
**Circular module dependencies are forbidden** (`BE0309`), which is what keeps
resolution a single ordered pass rather than a fixpoint.

The implemented M1 module rules resolve lexical scope, current-module items,
explicit imports and built-ins. Private cross-module access and conflicting
imports are rejected. Named types and methods use qualified declaration identity.
The former flat, first-name-wins behavior is historical; it is not supported
module semantics. See `M1_IMPLEMENTATION.md` for the implementation boundary.

---

## 3. Types

### 3.1 Primitives

```
i8 i16 i32 i64    u8 u16 u32 u64    f32 f64
bool  char  str  void
Vec2 Vec3 Vec4 Quat Mat3 Mat4
```

`str` is an immutable UTF-8 slice. There is **no null**.

`Quat` and `Mat3/4` are names that lower to a target type but have **no
operations at all** — not even component access. Treat them as reserved.

### 3.1.1 Vectors

`Vec2`, `Vec3` and `Vec4` are aggregates of 2, 3 and 4 **`f32`** components.
The width is `f32` on both targets, because EnforceScript's `vector` is three
32-bit floats and a wider native component would make the two back ends
disagree on rounding.

```beryl
let v = Vec3(1.0, 2.0, 3.0)     // positional construction
v.x   v.y   v.z   v.w           // named components, checked against the arity
v[i]                            // indexed, bounds-checked like an array
```

Both spellings are assignable (`v.y = 1.0`, `v[2] = 3.0`). A name is checked at
compile time, so `v.z` on a `Vec2` is `BE0320`, where `v[2]` could only trap.

| operator | meaning |
|---|---|
| `a + b`, `a - b` | component-wise |
| `a * b`, `a / b` | component-wise |
| `a * s`, `s * a` | scale by an `f32` |
| `a / s` | scale by the reciprocal — `s / a` is **not** accepted |
| `-a` | negate |
| `a == b`, `a != b` | component-wise, exact |

| method | on | result |
|---|---|---|
| `.length()` | all | `f32` |
| `.length_sq()` | all | `f32` — no square root |
| `.dot(b)` | all | `f32` |
| `.distance(b)` | all | `f32` |
| `.normalized()` | all | the vector, scaled to unit length |
| `.cross(b)` | `Vec3` only | `Vec3` (`BE0319` otherwise) |

**A zero-length vector normalizes to zero, not to NaN.** IEEE would give
`0.0/0.0` per component; both back ends special-case it instead, so the two
targets agree and the common "direction to a coincident point" case does not
poison everything downstream.

`Vec2` and `Vec4` are **native-only**: EnforceScript's `vector` is exactly
three floats, so both are `BE0701` on the enfusion target.

### 3.2 Compound

| | |
|---|---|
| `[T; N]` | fixed array; `N` is const-evaluated (`BE0505`) |
| `T?` | optional |
| `!T` | error union |
| `List<T>` | growable array |
| `Map<K,V>` | enfusion target only in v0.1 (`BE0901`) |
| `Box<T>` `Rc<T>` `Pool<T>` `Handle<T>` | **v0.2** (`BE0902`) |

### 3.3 Structs

```beryl
pub struct Pid {
    kp: f32
    ki: f32 = 0        // defaults must pass constant evaluation
}
```

Fields separate on a comma, a line break, or both. Layout is declaration order.
Structs are **value types**: assignment copies.

Record initializer expressions execute once in the order written, independently
of the record's layout. Missing defaults are expanded after explicit fields in
declaration order. Field defaults must pass constant evaluation; effectful calls
are rejected (`BE0501`). Array literal elements execute once from left to right;
each value is captured before the next expression runs.

A field of container type defaults to empty, so a literal need not name it.
Any other field without a default must be given (`BE0314`).

### 3.4 Enums

```beryl
pub enum Mode {
    Idle
    Armed = 3
    Active
}
```

Integer-backed, explicit discriminants allowed. Payload-carrying variants and
`match` are **v0.2**.

### 3.5 Conversions

**There is no implicit conversion, ever — not even widening** (`BE0312`).
`as` converts between numbers, characters and enums, and nothing else.

Integer literals are polymorphic until context fixes them, defaulting to `i32`.
Adopting a float type is not a conversion, because there is no runtime value
yet: `let x: f32 = 1` is legal, `let x: i32 = 1.5` is not.

---

## 4. Bindings and the memory model

### 4.1 Locals

```beryl
let a = 1        // immutable
var b = 1        // mutable
var c: i32       // declared; must be assigned before any read
```

A binding declared without a value is checked by definite-initialization
analysis (`BE0405`). A container declared without a value starts **empty**.

A binding counts as initialized only where every path reaching that point
assigns it. A loop body, one branch of an `if`, a `catch` handler and an
`orelse` fallback are all conditional, so none of them alone is enough.
`x += 1` reads `x` before writing it, and `inout x` lends a value the callee
may read — only `set x` promises the callee will assign one.

### 4.2 Passing conventions

| | meaning | lowers to (C) | lowers to (EnforceScript) |
|---|---|---|---|
| `let` (default) | immutable borrow | by value | plain parameter |
| `inout` | exclusive, non-aliasing borrow | `T *` | `out` parameter |
| `sink` | ownership transferred | by value; caller's binding dies | plain parameter |
| `set` | out-parameter; callee **must** assign | `T *` | `out` parameter |

The convention is written at the call site too:

```beryl
f(x)          f(inout x)          f(sink x)          f(set x)
```

A mismatch between declaration and call site is an error, because `inout` at the
call site is what makes the exclusive borrow visible to a reader.

### 4.3 Second-class references

A borrow **cannot** be stored in a struct, returned, or placed in a container.
It therefore cannot outlive the call it was passed to.

**This is why Beryl has no lifetime annotations.** There is no syntax for one.

The consequence: graphs and back-references use an index or a handle, not a
stored reference.

### 4.4 Exclusivity

While an `inout` borrow of a location is live, no other access to that location
may occur in the same call (`BE0401`). Two `inout` arguments may not overlap.
The receiver of a method taking `inout self` counts as one of the accesses.

```beryl
f(inout p.x, inout p.y)   // allowed: disjoint paths
f(inout p, inout p.x)     // BE0401: one contains the other
p.bump(inout p)           // BE0401
```

The current checker verifies local access paths. Collection copies can still
share backing storage, so generated C omits `restrict` until storage identity is
proved. That implementation limit does not relax the source exclusivity rule.

### 4.5 Moves

A `sink` argument consumes its source. Using it afterwards is `BE0403`; the move
site is labelled. Moving out of a field or out of a borrowed parameter is
`BE0406`.

An `if` whose branches both move is fine; one that moves on only one branch
poisons the merge, because the state after is "possibly moved".

---

## 5. Expressions

Precedence, loosest to tightest:

```
orelse catch
||
&&
== != < <= > >=          (non-associative — BE0208)
|
^
&
<< >>
+ -
* / %
unary  - ! ~ try
postfix  .  ()  []  as
```

**Struct literals** are disabled while parsing the condition of `if`, `while` or
`for`, so `if p {` opens a block. Parentheses re-enable them:
`if (P{ x: 1 }).x {`.

**There is no turbofish.** Generic arguments at call sites are inferred, which
is what makes `<` unambiguously a comparison.

`a.b` always parses as field access. Whether it is really a module path is
decided during resolution.

---

## 6. Statements

```beryl
let x = e        var x = e        var x: T
x = e            x += e   -= *= /= %=
if c { } else if d { } else { }
while c { }
for i in 0..n { }          for v in arr { }
break     continue     return     return e
defer e
```

`for` over a range is half-open. `for` iterates a range, an array, or a `List`.

**`defer` runs where it is written** in v0.1, not at scope exit; correct
ordering arrives with destructors.

`break` or `continue` outside a loop is `BE0316`.

---

## 7. Functions

```beryl
pub fn name(params) -> T { }              // free function
pub fn Type.name(inout self, ...) -> T { } // method
```

A method's first parameter is `self` with a convention; `self` elsewhere is
`BE0206`. Only `let` parameters may have defaults (`BE0207`). Every path of a
non-`void` function must return (`BE0310`).

Generic parameters parse (`fn f<T: Bound>`) but are **not instantiated** in v0.1
(`BE0508`).

---

## 8. Errors

`!T` is an error union: an `i32` tag plus a value. No allocation.

```beryl
fn parse(let s: str) -> !i32 {
    if s == "" { return error.Empty }
    return 1
}

let a = try parse(s)            // propagate; the caller must return !T (BE0317)
let b = parse(s) orelse 0       // fallback
let c = parse(s) catch |e| { }  // handle
```

**Failure aborts; it never unwinds.** There are no landing pads, no `.eh_frame`,
and no personality routine, which is where most of the binary-size advantage
comes from.

`orelse` also applies to `T?`.

On the enfusion target `!T` lowers to `bool` + `out`, and the **error tag is not
preserved** — a caller learns that an error occurred, not which.

---

## 9. Arithmetic

Integer overflow **traps in every build**, release included. Division and
remainder by zero trap. `INT_MIN / -1` traps; `INT_MIN % -1` is zero.
Shifts by a negative amount or an amount greater than or equal to the width
trap. Array and list indices are bounds-checked.

Opt-outs, which say so at the call site:

```beryl
wrapping_add(a, b)   wrapping_sub(a, b)   wrapping_mul(a, b)
saturating_add(a, b) saturating_sub(a, b)
```

Wrapping is defined as two's-complement wraparound; it is implemented through
the unsigned type, because signed overflow is undefined in C and "undefined" is
not what `wrapping_add` promises.

Float arithmetic is unchecked IEEE-754.

---

## 10. Attributes

| | applies to | effect |
|---|---|---|
| `@untrusted` | function | parameters are attacker-controlled |
| `@validator` | function | validation intent; does not erase provenance or replace a bounds proof |
| `@secret` | function | parameters are secret |
| `@constant_time` | function | no secret branch or index, transitively |
| `@server_only` | function | not reachable from client context |
| `@unsafe(cap)` | block or item | suspends one invariant: `raw_ptr`, `unchecked_index`, `ffi`, `transmute` |

See [SECURITY.md](SECURITY.md) and [THREAT-MODEL.md](THREAT-MODEL.md).

---

## 11. Constant evaluation

`const` items are evaluated at their declaration. The evaluator handles
literals, other constants, and arithmetic, comparison and logic over integers,
floats, bools and strings.

It is a sandbox **by construction, not by policy**: no file, network,
environment or clock access is implemented, so there is none to disable. It is
bounded at 100,000 steps and 64 levels of nesting (`BE0504`).

Integer constant arithmetic uses the checked width and signedness, not a universal
i64 approximation. Logical operators short-circuit during value evaluation. f32
constant operations round intermediate values to f32. Constant float-to-integer
casts diagnose a nonfinite or out-of-range truncated result before a host cast.
This does not establish the same checks for dynamic casts on either backend.

`comptime` is a reserved word; the block form is v0.2.

---

## 12. Tests

```beryl
test "a non-positive dt produces no output" {
    var p = Pid{ kp: 2 }
    assert(p.step(10, 0, 0) == 0)
}
```

`beryl test` compiles every test block into a native binary and runs it. Test
blocks are **not** emitted to the enfusion target.

---

## 13. Built-ins

Shadowed by any user function of the same name.

```
print(x)  println(x)  println()  assert(cond)
min(a,b)  max(a,b)  clamp(x,lo,hi)  abs(x)  sqrt(x)
wrapping_add/sub/mul(a,b)   saturating_add/sub(a,b)
```

`List<T>`: `.len()` `.push(v)` `.get(i)` `.set(i,v)` `.clear()`

`print` is deliberate ambient authority, matching EnforceScript's own `Print`.
Real I/O is designed to require a capability value and does not exist in v0.1.

---

## 14. Manifest

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

With a manifest present, every command reads `src/*.be` in sorted order when
given no file arguments. The reader accepts section headers, `key = "value"` and
`key = true`, and **cannot execute anything** — which is the point of having no
build scripts.
