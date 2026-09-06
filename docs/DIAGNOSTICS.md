# Diagnostics

Every code the compiler can emit. `scripts/check-diagnostics.sh` fails the build
if a code exists in `src/` without an entry here, so this list cannot drift.

Codes are grouped by the pass that raises them:

| range | pass |
|---|---|
| `BE01xx` | lexer |
| `BE02xx` | parser |
| `BE03xx` | resolve and type check |
| `BE04xx` | ownership |
| `BE05xx` | constant evaluation and generics |
| `BE06xx` | security |
| `BE07xx` | enfusion target profile |
| `BE08xx` | manifest and driver |
| `BE09xx` | native target profile |

---

## BE01xx — lexer

### BE0101 — unterminated string literal
The closing `"` is missing, or the string ran to the end of a line. Beryl has no
multi-line string literals.

### BE0102 — unterminated or empty character literal
`'a'` holds exactly one character. `''` is empty; `'ab'` is two.

### BE0103 — unknown escape sequence
Supported: `\n \t \r \0 \\ \" \' \xNN`. `\x` needs exactly two hex digits.

### BE0104 — unknown numeric suffix
Valid suffixes are `i8 i16 i32 i64 u8 u16 u32 u64 f32 f64`. Also raised when a
numeric literal has no digits after its radix prefix.

### BE0105 — unexpected character
The character is not part of Beryl's syntax.

### BE0106 — integer literal too large
The literal does not fit in 64 bits, before any suffix is applied.

### BE0107 — block comments are not supported
Use `//`. They nest predictably and read better in diffs.

---

## BE02xx — parser

### BE0201 — expected a specific token
The message names what was expected and what was found. Frequently a knock-on
from an earlier mistake; fix the first one and rebuild.

### BE0202 — expected an expression

### BE0203 — expected a type

### BE0204 — expected an item
At the top level, only `fn` `struct` `enum` `const` `test` `use` `trait` (and
`pub`, `@attr`) may appear. Also raised for an `@` attribute in an expression
position other than `@unsafe(...)`.

### BE0205 — duplicate parameter name
Both spans are labelled.

### BE0206 — `self` must be the first parameter
```beryl
fn Pid.step(inout self, sp: f32) -> f32   // yes
fn Pid.step(sp: f32, inout self) -> f32   // BE0206
```

### BE0207 — a `let`-only parameter may have a default
A default value is copied at the call site, which has no meaning for a borrow or
a move. `inout`, `sink` and `set` parameters cannot have one.

### BE0208 — comparison operators cannot be chained
`a < b < c` is almost always carried over from another language. Write
`a < b && b < c`.

### BE0209 — a file must begin with a `module` declaration

---

## BE03xx — resolve and type check

### BE0301 — cannot find a name in this scope
An undeclared variable, or a function that does not exist.

### BE0302 — unknown type
Also raised when a built-in generic gets the wrong number of type arguments,
e.g. `Map<i32>`.

### BE0303 — type mismatch
The general case. The message names the expected and found types and the context
("in this argument", "in this return"). Also covers: assigning to something that
is not a place, a fractional literal given an integer type, an operator applied
to a type that does not support it, and a call-site convention that does not
match the declaration.

### BE0304 — wrong number of arguments
The declaration is labelled.

### BE0305 — unknown field

### BE0306 — unknown method
For `List<T>`, the help names the methods that do exist.

### BE0307 — this is not callable
A value or a type used where a function was expected.

### BE0308 — defined twice
Two items, two struct fields, or two bindings in one scope with the same name.
Shadowing in an *inner* scope is allowed and is not this error.

### BE0309 — module import cycle
Beryl forbids circular module dependencies, which is what keeps resolution a
single ordered pass rather than a fixpoint.

### BE0310 — not every path returns a value
Give the `if` an `else`, or add a trailing `return`.

### BE0311 — a condition must be `bool`
There is no truthiness. Compare explicitly: `if x != 0 { }`.

### BE0312 — implicit numeric conversion
The single most common mistake in a language with no implicit conversion, so it
gets its own code and a help line containing the exact cast to write.

```
error[BE0312]: expected `f32`, found `i64` on the right of this operator
  = note: Beryl performs no implicit numeric conversion, not even widening
  = help: write an explicit cast: `... as f32`
```

### BE0313 — this type cannot be indexed
Indexable: `[T; N]`, `List<T>`, `Map<K,V>`, `Vec2`/`Vec3`/`Vec4`.

### BE0314 — missing field in a struct literal
Only fields with no default must be given. Container fields default to empty.

### BE0315 — unknown field in a struct literal

### BE0316 — `break` or `continue` outside a loop

### BE0317 — `try` requires the enclosing function to return `!T`
Change the return type, or handle the error with `orelse` or `catch`.

### BE0318 — unreachable code *(warning)*
Statements after a `return`.

### BE0319 — `cross` is only defined on `Vec3`
The cross product exists only in three dimensions. For `Vec2`, the scalar
`a.x*b.y - a.y*b.x` is usually what is wanted; write it out.

### BE0320 — this vector has no such component
`Vec2` has `x` and `y`; `Vec3` adds `z`; `Vec4` adds `w`. Naming a component
is checked against the arity, which is why `v.z` on a `Vec2` is an error where
`v[2]` could only trap at run time.

---

## BE04xx — ownership

### BE0401 — overlapping exclusive borrows
Two accesses in one call where at least one is `inout` or `set`, and their
storage overlaps. Disjoint field paths are fine.

```beryl
f(inout p.x, inout p.y)   // allowed: disjoint
f(inout p, inout p.x)     // BE0401: one contains the other
p.bump(inout p)           // BE0401: the receiver counts too
```

Both spans are labelled, and the note explains that this guarantee is what
licenses `restrict` in the generated code.

### BE0402 — cannot assign to an immutable binding
`let` binds once. Use `var`. Assigning to a `let` that was *declared without a
value* is the initialization and is allowed.

### BE0403 — use after move
A `sink` argument consumed the binding. The move site is labelled.

### BE0404 — a `set` parameter is not initialized on every path
The callee must assign it before every `return`, and before falling off the end.

### BE0405 — used before initialized
A binding is initialized only on paths that certainly reach an assignment:

- one branch of an `if` assigning it is not enough;
- **a loop body is not enough** — `while c { x = 1 }` may run zero times;
- **a `catch` handler or an `orelse` fallback is not enough** — they run only
  when the value is an error or empty;
- `x += 1` **reads** `x` first, so it cannot be what initializes it;
- passing `inout x` is not enough. `inout` lends an existing value and the
  callee may read it; only `set` promises the callee will assign one.

The last four each let a program read uninitialized stack memory in v0.1.

### BE0406 — cannot move out
Either out of a field (`sink o.i`), which would leave the parent in a state with
no name, or out of a borrowed parameter — declare it `sink` if the function
should consume it.

### BE0407 — cannot mutate through a read-only borrow
Assigning through a `let` parameter, or passing a `let` parameter or an
immutable local as `inout`.

---

## BE05xx — constant evaluation and generics

### BE0501 — not a constant expression
Constants are built from literals, other constants, and arithmetic on them. A
function call is not constant — there is nothing to sandbox here because
nothing beyond pure arithmetic is implemented.

### BE0502 — division by zero in a constant

### BE0503 — constant arithmetic overflows 64 bits
Also raised for an out-of-range shift.

### BE0504 — constant evaluation exceeded its limits
Bounded at 100,000 steps and 64 levels of nesting, so a self-referential
constant is a diagnostic rather than a hang.

### BE0505 — array length must be a constant, non-negative integer

### BE0508 — user-defined generics are not instantiated in v0.1
Monomorphization is v0.2. The built-in generic containers — `List`, `Map`,
`Box`, `Rc`, `Pool`, `Handle` — are intrinsic and unaffected.

---

## BE06xx — security

See [SECURITY.md](SECURITY.md) for the model and
[THREAT-MODEL.md](THREAT-MODEL.md) for what it does *not* guarantee.

### BE0601 — an untrusted value indexes without being bounded
A parameter of an `@untrusted` function reached an index. Bound it with
`clamp(i, 0, n - 1)`, or route it through a function marked `@validator`.

### BE0602 — a secret value decides a branch
Branching on a secret makes its value observable through timing. Compute both
sides and select without branching.

### BE0603 — a secret value indexes memory
The access pattern is observable through the cache, which leaks the secret
regardless of what the code does with it. Note that `clamp` does **not** launder
a secret — bounding one still reveals it.

### BE0605 — `@unsafe` in a package declaring `forbid_unsafe`
Remove it, or set `forbid_unsafe = false` and accept the audit surface.

### BE0607 — a `@constant_time` function calls one that is not
The guarantee has to hold through every callee, or it does not hold at all.

---

## BE07xx — enfusion target profile

These run **before** emission, so Workbench never sees script that was doomed.
See [ENFUSION.md](ENFUSION.md).

### BE0701 — a type EnforceScript does not have
`i64 u64 u32 u16 u8 i16 i8 f64`. The engine has one integer type (a signed
32-bit `int`) and one float type (32-bit). The help names the substitute.

### BE0703 — `@unsafe` is forbidden on the enfusion target
The engine has no raw pointers, so the capability has nothing to suspend.

### BE0705 — a `@server_only` function called from client context
Mark the caller `@server_only` too, or route the call through an authority
check.

---

## BE08xx — manifest and driver

### BE0801 — malformed `beryl.toml`
The line number is given. The reader accepts section headers, `key = "value"`,
and `key = true`.

### BE0802 — missing required manifest field, or no sources found
`[package] name` is required. Also raised when a package has no `.be` files
under `src/`.

---

## BE09xx — native target profile

### BE0901 — `Map<K, V>` has no native representation in v0.1
It works today on the enfusion target, where it lowers to the engine's own
`map`. Natively, use `List<T>` with a linear scan until v0.2.

### BE0902 — `Box<T>`, `Rc<T>`, `Pool<T>` and `Handle<T>` are not implemented
The ownership model is designed around these, but v0.1 ships only value types,
arrays and `List`. Use a value or an array index.

### BE0903 — the native back end cannot lower this construct
The type checker accepts more than the back end emits. Where that gap exists it
must be an error, because the alternative is worse: a `for` over a `List` used
to emit **no loop at all**, so the program compiled, ran, and quietly returned
the wrong answer. If you see this, the program is fine and the compiler is not.
