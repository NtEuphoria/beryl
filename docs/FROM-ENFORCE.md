# Coming from EnforceScript

You already know the shape of this. The differences that matter are all about
what the compiler will now catch before Workbench sees it.

## Side by side

| EnforceScript | Beryl |
|---|---|
| `class SPK_Store` | `pub struct Store` (the prefix comes from `beryl.toml`) |
| `void SPK_Store()` constructor | field defaults: `n: i32 = 0` |
| `protected float m_fKp;` | `kp: f32` |
| `bool Publish(SPK_Entity e)` | `pub fn Store.publish(inout self, let e: Entity) -> bool` |
| `out int result` | `set result: i32`, or return `!i32` |
| `array<int>` | `List<i32>` |
| `map<string, ref X>` | `Map<str, X>` |
| `ref SPK_Foo m_Foo` | just `foo: Foo` — ownership is tracked, not spelled |
| `int` | `i32` |
| `float` | `f32` |
| `string` | `str` |
| `vector` | `Vec3` |
| `Math.Clamp(x, a, b)` | `clamp(x, a, b)` |
| `Print(x)` | `println(x)` |
| `foreach (int v : xs)` | `for v in xs` |
| `for (int i = 0; i < n; i++)` | `for i in 0..n` |
| `null` | there is no null; use `T?` |

## The real change: a fast loop

This is the reason to bother.

```
EnforceScript          edit → Workbench build (10-15 s) → read a cascade of
                       errors, most of them phantom → find the real one → repeat

Beryl                  edit → beryl test (milliseconds) → beryl build -t enfusion
                       → Workbench sees only script that already checks out
```

`SPK_PID.c` says *"Pure maths, unit-tested."* In Beryl that sentence is
executable:

```beryl
test "derivative on measurement produces no setpoint kick" {
    var p = Pid{ kp: 0, kd: 1 }
    let first = p.step(0, 0, 0.1)
    let kick  = p.step(100, 0, 0.1)
    assert(kick == 0)
}
```

```
beryl test
ok  4 tests, 5 assertions
```

## Things that will surprise you

**No `null`.** A `T?` is either present or not, and you must say which. A
missing value cannot silently become a crash three frames later.

**Integers are one width, and it is checked.** `i32` maps to EnforceScript's
`int`. Ask for `i64` on the enfusion target and Beryl refuses at compile time
(`BE0701`) rather than emitting something the engine cannot represent.

**Overflow traps.** EnforceScript wraps silently. Beryl traps natively; on the
enfusion target the engine still wraps, so `wrapping_add` is how you say you
meant it — and the source then reads the same on both targets.

**No implicit conversion.** `float f = someInt;` is routine in EnforceScript.
In Beryl you write `someInt as f32`. This catches more real bugs than it costs.

**Structs are values.** `var b = a` copies. In EnforceScript that would alias,
which is a classic source of "why did that change?" The Enfusion backend inserts
a `BerylCopy()` at exactly the points value semantics require one.

**Mutation is declared.** A method that changes the instance takes
`inout self`; one that only reads takes `let self`. Attempt to assign through a
`let` and you get `BE0407`. The signature now tells you what a call does.

**Aliasing is checked.** `f(inout p, inout p.x)` is refused (`BE0401`).
EnforceScript would let that through, and the resulting bug is miserable.

## What you keep writing by hand

Beryl does not know the engine API. Components, RPCs, `IEntity`, the replication
attributes — those stay in EnforceScript, and they call into Beryl-generated
classes.

That split is deliberate and it is the productive one. The engine-facing shell
is thin and rarely changes; the logic underneath is where the bugs live, where
the tests belong, and where a 10-second build loop actually hurts.

## A porting recipe

1. Pick a class that is **pure logic** — a controller, a state machine, a store,
   a math helper. Something with no `IEntity` in sight.
2. `beryl new` a package beside your mod and point `[target.enfusion] out` at a
   `Generated/` folder inside it.
3. Translate the fields, then the methods. The type table above covers nearly
   all of it.
4. Write the tests you always wanted for it. Run `beryl test`.
5. `beryl build -t enfusion`, then build the mod in Workbench.
6. Delete the original `.c` and have the engine-facing code call the generated
   class instead.

Keep the prefix identical to the one you already use, and generated classes will
sit alongside handwritten ones without a collision.

## Diagnostics you will meet early

| | |
|---|---|
| `BE0701` | a type EnforceScript does not have; the substitute is named |
| `BE0312` | implicit numeric conversion; the cast is in the help line |
| `BE0401` | two overlapping exclusive borrows in one call |
| `BE0403` | use after a `sink` moved it |
| `BE0407` | mutating through a `let` borrow |
| `BE0705` | a `@server_only` function reached from client context |

Every code is documented in [DIAGNOSTICS.md](DIAGNOSTICS.md).
