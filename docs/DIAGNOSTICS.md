# Diagnostics

### BE0608 — security analysis resource limit

The conservative whole-program taint analysis exceeded its expression-depth,
function, field-cell, or work budget. This is a failed analysis, not a clean
security result. Reduce the source set or expression depth and retain the
diagnostic when reporting unavailable verification.

### BE1001 — reference capability unavailable

The explicitly selected reference backend does not admit a declaration, type,
expression, or empty test selection. No unsupported test is counted as executed.
This includes projected assignments whose destination evaluation or RHS may
mutate overlapping storage. Separate the mutation from selection of the
destination to make the intended order explicit; the interpreter does not choose
between the previously disagreeing reference/native outcomes.
Direct reference API admission also rejects a captured borrowed call argument
whose selection or later arguments may change overlapping storage. Ordinary
CLI frontend checks report `BE0401` for these patterns before execution.

### BE1002 — reference trap or failed assertion

Execution encountered a checked numeric failure, invalid storage/index, a
nonfinite result outside the admitted domain, or a failed test assertion.

### BE1003 — reference resource budget exhausted

The step, call-depth, nesting, allocation, or output budget was exhausted.
This is an incomplete execution, never a successful test result.

### BE1004 — reference output failure

An event or result could not be encoded, written, or flushed completely.

### BE1005 — reference execution interrupted

Execution timed out or was cancelled. The retained result distinguishes the two
statuses. Neither is a completed test run.

### BE1006 — differential validation failed

The native path failed to execute successfully, or its output/ordered events
differed from the reference. Float print observations include exact binary32 bits.
Inspect both retained logs; do not discard mismatched runs as performance noise.

### BE0326 — invalid Enfusion export mapping

An explicit class/method mapping is missing, ambiguous, non-public, conflicting,
reserved, or outside the initial scalar method interface. Export methods require
an exported receiver class. Case-only export collisions are rejected as well.
Compiler-generated names and copy helpers cannot be overwritten by exports.

### BE0325 — invalid or ambiguous native entry point

Executable generation requires at most one non-generic free `main`, taking no
arguments and returning void or i32. A native test harness supplies its own entry
point. Ordinary semantic checking can still inspect library source sets.

### BE0323 — module visibility or receiver ownership violation

A private declaration was accessed from another module, or a method was declared
outside its receiver's module. Import and call diagnostics identify the declaration.

### BE0324 — invalid import

A `use` path does not identify an existing item/module or is ambiguous. Imported
items must be public outside their module. Conflicting local import names use
BE0308 with both declaration sites.

`beryl check --format json` emits one versioned JSON object on stdout, including
success with an empty diagnostic array. Locations use zero-based byte offsets,
byte lengths, and one-based line/byte columns. Non-source failures have a null
primary location. Human-readable output remains the default.

### BE0804 — command input or execution mode is invalid

An option, target, format, timeout, input selection, or test selection is invalid.
No selected test blocks is a failure, not an executed empty suite. Reference and
Enfusion execution require separately implemented backends; generation alone is
not successful test execution.

### BE0811 — context declaration is unknown or ambiguous

The requested symbol does not uniquely identify a resolved declaration. Use the
reported candidate names and pass a module-qualified name. Context admission
results do not establish native execution or engine verification.

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

### BE0210 — parser resource limit
The parser rejects source beyond its configured token, work, recursion or AST
shape limits before exposing that AST to later recursive passes. Split the
source or simplify deeply nested expressions. This is a failed parse, not an
empty successful module. Parser limits do not establish a whole-compiler or
lexer memory budget; see the parser resource packet for exact limits.

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

### BE0321 — integer literal does not fit its type
The checked width and signedness must represent the literal's magnitude. Direct
unary minus permits the signed minimum, such as `-128i8`, without accepting its
positive counterpart. Choose a wider type or correct the value.

### BE0322 — unsupported parameter default
Defaults currently expand from declaration-bound expressions without parameter
references, local bindings or nonlocal exits. Pass the argument explicitly when
it needs those features. Defaults are expanded before ownership and taint checks.

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

Both spans are labelled. This also rejects selection or later-argument effects
that can change an earlier borrowed place, including replacement of its parent
and a later `sink` transfer. The message identifies the captured argument and
the conflicting effect. Move the mutation before the call, or first copy the
intended plain value into an independent binding. Disjoint plain fields and
literal indices remain admitted; dynamic indices and unknown effects fail
conservatively. Scalar `let` arguments are captured by value.

Native pointer parameters use per-function `restrict` admission only when
every exclusive call path is proven. This local analysis does not establish
general collection ownership or engine-reference non-aliasing.

### BE0402 — cannot assign to an immutable binding
`let` binds once. Use `var`. Assigning to a `let` that was *declared without a
value* is the initialization and is allowed.

### BE0403 — use after move
A `sink` argument consumed the binding. The move site is labelled.

### BE0404 — a `set` parameter is not initialized on every path
The callee must assign it before every `return`, including a failure propagated
by `try`, and before falling off the end.

### BE0405 — used before initialized
A binding is initialized only on paths that certainly reach an assignment:

- one branch of an `if` assigning it is not enough;
- **a loop body is not enough** — `while c { x = 1 }` may run zero times;
- **a `catch` handler or an `orelse` fallback is not enough** — they run only
  when the value is an error or empty;
- `x += 1` **reads** `x` first, so it cannot be what initializes it;
- a short-circuit RHS may be skipped;
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
Untrusted provenance reached an index without a range proof for the selected
storage. The initial checker proves constant intervals for fixed arrays, including
ordered constant `clamp` bounds. `min`, `max`, and `@validator` do not remove
provenance. Dynamic-storage bounds require a separately admitted contract;
putting an annotation on a helper is not such a contract.

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
The checked source restriction requires an annotated callee. This is not a
machine-level constant-time guarantee; backend transformations still require
independent analysis.

---

## BE07xx — enfusion target profile

These run **before** emission, so Workbench never sees script that was doomed.
See [ENFUSION.md](ENFUSION.md).

### BE0701 — an unsupported Enfusion type, copy or receiver shape

The source target also rejects `set self`, `sink self`, direct whole-self
replacement and explicit whole-self `inout`/`set` arguments. Its implicit class
receiver does not yet have a verified caller-storage replacement/transfer
lowering. Use an ordinary function with an admitted explicit parameter, or
admitted field writes. Existing ownership, access and storage rules still apply.
This containment is separate from native/reference receiver-mode support.
`i64 u64 u32 u16 u8 i16 i8 f64`. The engine has one integer type (a signed
32-bit `int`) and one float type (32-bit). The help names the substitute.
This also rejects generated struct-copy fields containing arrays/lists of
records or further arrays/lists: the current `.Copy` lowering is not valid for
those reference-element shapes. Scalar-element arrays remain separately admitted.

### BE0703 — `@unsafe` is forbidden on the enfusion target
The engine has no raw pointers, so the capability has nothing to suspend.

### BE0705 — a `@server_only` function called from client context
Route the operation through a verified authority boundary. `@server_only`
restricts source calls; annotating a caller does not arrange server execution.

---

## BE08xx — manifest and driver

### BE0801 — malformed `beryl.toml`
The line number is given. The reader accepts section headers, `key = "value"`,
and `key = true`.

### BE0802 — missing required manifest field, or no sources found
`[package] name` is required. Also raised when a package has no `.be` files
under `src/`.

### BE0803 — source file could not be read
The named input was not readable. The command fails; this is never a successful
empty-program check. Check the path and access to the file.

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
the wrong answer. This code also reports owning-storage operations for which the
AST backend cannot preserve independent values. Follow the operation-specific
migration guidance; an accepted container type alone does not admit every copy,
return, transfer, or mutation boundary.

## BE11xx — experimental structured IR

### BE1101 — outside the experimental IR admission subset
The experimental IR API rejects this operation, type, parameter mode or resource
limit with its source span. Ordinary compilation still uses the AST backend;
this diagnostic does not make public `--lowering ir` available. Consult the
[Stage D packet](advanced/STAGE_D_IR.md) for the bounded admission contract.
The record/PID experiment includes finite f32, static record projections and
`let`/`inout`; fixed arrays, `set`/`sink`, and uncertain overlapping mutation
across a projected assignment remain outside that experiment.

### BE1102 — lowered IR violates an internal invariant
The independent verifier rejected the generated IR. Retain the source and
diagnostic as a compiler defect; do not execute invalid IR or substitute AST
execution and report it as successful IR evaluation.
