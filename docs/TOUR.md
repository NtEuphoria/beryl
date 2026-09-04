# A tour of Beryl

Twenty minutes, assuming you have written something C-like before. Every example
here compiles and runs today.

## 1. Hello

```beryl
module hello

fn main() {
    println("Hello from Beryl")
}
```

```bash
beryl run hello.be
```

No semicolons. A line break ends a statement; a trailing or leading operator
continues one, so this works and means what it looks like:

```beryl
return self.kp * err
     + self.ki * self.integral
```

## 2. Bindings

```beryl
let a = 1          // immutable
var b = 1          // mutable
b = 2

var c: i32         // declared without a value...
if cond { c = 1 } else { c = 2 }
println(c)         // ...but the compiler proved it is assigned first
```

Leave off the `else` and you get:

```
error[BE0405]: `c` is used before it is initialized
```

## 3. Numbers are strict

There is **no implicit conversion**, not even widening.

```beryl
let a: i32 = 1
let b: i64 = 2
let c = a + b       // error[BE0312], with `... as i64` in the help
let d = a as i64 + b
```

Integer literals are polymorphic until context fixes them, which is why
`let x: f32 = 1` is fine — there is no runtime value yet to convert.

**Overflow traps in every build**, release included:

```beryl
var n: i32 = 2147483647
n += 1              // beryl: arithmetic overflow on `+` at demo.be:4
```

When you genuinely want wraparound, say so:

```beryl
n = wrapping_add(n, 1)
```

## 4. Structs and methods

```beryl
pub struct Counter {
    n: i32 = 0
    step: i32 = 1
}

pub fn Counter.bump(inout self) {
    self.n += self.step
}

pub fn Counter.value(let self) -> i32 {
    return self.n
}
```

Methods are free functions declared on a type. The receiver's convention is part
of the signature: `inout self` may mutate, `let self` may not.

Structs are **values**, so this does what you would hope:

```beryl
var a = Counter{ step: 5 }
a.bump()
var b = a          // an independent copy
b.bump()
println(a.value()) // 5
println(b.value()) // 10
```

## 5. The four conventions

This is the entire memory model.

```beryl
fn read(let c: Counter) -> i32 { return c.n }     // borrow, read-only
fn bump(inout c: Counter) { c.n += 1 }            // exclusive borrow
fn take(sink c: Counter) -> i32 { return c.n }    // ownership moves in
fn split(let n: i32, set lo: i32, set hi: i32) {  // callee must assign
    lo = n / 2
    hi = n - lo
}
```

You write the convention at the call site too, which is what makes an exclusive
borrow visible when you are reading the code:

```beryl
bump(inout c)
take(sink c)
split(9, set lo, set hi)
```

**There are no lifetimes** because a borrow can never escape: it cannot be
stored in a struct, returned, or put in a container. That is the whole trick.

Two consequences the compiler enforces:

```beryl
swap(inout a, inout a)   // error[BE0401]: overlapping exclusive borrows
take(sink c)
println(c.n)             // error[BE0403]: use of `c` after it was moved
```

And one that it deliberately allows, because the paths are disjoint:

```beryl
f(inout p.x, inout p.y)  // fine
f(inout p, inout p.x)    // error[BE0401]
```

## 6. Errors are values

```beryl
fn parse_digit(let c: char) -> !i32 {
    if c < '0' { return error.NotADigit }
    if c > '9' { return error.NotADigit }
    return c as i32 - 48
}
```

`!i32` is an error union: a tag plus a value. No allocation, and **failure
aborts rather than unwinding** — no landing pads, no `.eh_frame`, which is where
most of the binary-size advantage comes from.

Three ways to consume one:

```beryl
let a = try parse_digit(c)             // propagate (caller must return !T)
let b = parse_digit(c) orelse -1       // supply a fallback
let d = parse_digit(c) catch |e| {     // handle it
    println("bad input")
}
```

`try` in a function that does not return `!T` is `BE0317`, with the fix in the
help line.

## 7. Collections

```beryl
let fixed: [i32; 4] = [10, 20, 30, 40]   // length is const-evaluated
println(fixed[2])                         // bounds-checked

var xs: List<i32>                         // starts empty
xs.push(1)
xs.push(2)
println(xs.len())
println(xs.get(0))
xs.set(0, 99)
xs.clear()

for v in fixed { }
for i in 0..xs.len() { }                  // ranges are half-open
```

Optionals exist and **null does not**:

```beryl
let found: i32? = lookup(k)
let value = found orelse 0
```

## 8. Constants and compile-time evaluation

```beryl
const WIDTH: i32  = 4
const HEIGHT: i32 = 3
const CELLS: i32  = WIDTH * HEIGHT

let grid: [i32; CELLS] = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
```

The evaluator is a sandbox by construction, not by policy: it interprets pure
arithmetic over integers, floats, bools and strings, and there is no file,
network or clock access to disable because none is implemented. It is bounded in
steps, so a self-referential constant is a diagnostic rather than a hang.

## 9. Tests

```beryl
test "proportional term responds to error" {
    var p = Pid{ kp: 2 }
    let out = p.step(10, 4, 0.1)
    assert(out > 11.9)
    assert(out < 12.1)
}
```

```bash
beryl test
# ok  4 tests, 5 assertions
```

These run **natively**, in milliseconds — which is the entire argument for
writing Reforger logic in Beryl.

## 10. Security attributes

```beryl
@validator
pub fn safe_slot(let raw: i32) -> i32 {
    return clamp(raw, 0, 63)
}

@untrusted                      // every parameter came off the wire
@server_only                    // and a client must not reach this directly
pub fn Store.on_update(inout self, let slot: i32, let v: i32) {
    self.slots[safe_slot(slot)] = v
}
```

Use `slot` directly as an index and you get `BE0601`. `clamp`, `min` and `max`
launder untrusted taint, because bounding a value is exactly what makes an
attacker's index safe to use.

All of it is compile-time. None of it costs anything at runtime. And it is a
lint rather than a proof — [THREAT-MODEL.md](THREAT-MODEL.md) says where it
stops.

## 11. Two targets

```bash
beryl run                                     # native
beryl build -t enfusion --prefix SPK          # EnforceScript for Reforger
```

Same source. See [ENFUSION.md](ENFUSION.md) for the full lowering table and the
handful of things the engine cannot express.

## Where to go next

[CHEATSHEET.md](CHEATSHEET.md) for everything on one page,
[SPEC.md](SPEC.md) when you need the exact rule, and
[STATUS.md](STATUS.md) for what v0.1 does not do yet.
