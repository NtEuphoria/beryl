# Beryl for Arma Reforger

## Why this exists

Enfusion runs EnforceScript and nothing else. Mods ship as `.c` files that
Workbench compiles into the engine's `Game` module alongside roughly 5,600 base
game files; the shipped game loads no user native code. So there is exactly one
honest way for Beryl to be useful here: **it compiles to EnforceScript.**

That turns out to be worth doing, for one reason above all others.

`SPK_PID.c` in SparkOS MESH carries the header comment *"Pure maths,
unit-tested."* Verifying it today costs a 10–15 second Workbench build in which
one real error produces a documented cascade of phantom errors across untouched
base-game files. With Beryl:

```bash
beryl test               # the PID, the mixer, the guidance — natively, in ms
beryl build -t enfusion  # emits SPK_*.c, ready for Workbench
```

Workbench only ever sees script that already type-checked, ownership-checked,
and passed the profile lint. Same source, both paths.

## Getting started

```bash
beryl new mesh_logic
cd mesh_logic
```

Then point the manifest at your mod:

```toml
[package]
name    = "mesh_logic"
version = "0.1.0"

[target.enfusion]
prefix = "SPK"
out    = "../SparkOS_Mesh/scripts/Game/SparkOSMesh/Generated"

[security]
forbid_unsafe = true
```

```bash
beryl test                  # fast loop while writing
beryl build -t enfusion     # writes SPK_Generated.c into `out`
```

With no `--out-dir`, the EnforceScript goes to stdout, which is the quickest way
to see what a change produces.

## What the generated script looks like

Beryl emits in Bohemia's own style, because you will be reading it in Workbench:
tabs, Allman braces, `//!` doc comments, prefixed class names.

```beryl
pub struct Pid {
    kp: f32
    ki: f32 = 0
    integral: f32 = 0
}

pub fn Pid.step(inout self, sp: f32, meas: f32, dt: f32) -> f32 {
    if dt <= 0 {
        return 0
    }
    let err = sp - meas
    self.integral += err * dt
    return self.kp * err + self.ki * self.integral
}
```

becomes

```c
class SPK_Pid
{
	float kp;
	float ki;
	float integral;

	void SPK_Pid()
	{
		ki = 0;
		integral = 0;
	}

	//! Value semantics: Beryl structs copy on assignment. Named
	//! BerylCopy rather than Clone, which the engine base class already has.
	SPK_Pid BerylCopy()
	{
		SPK_Pid c = new SPK_Pid();
		c.kp = kp;
		c.ki = ki;
		c.integral = integral;
		return c;
	}

	float step(float sp, float meas, float dt)
	{
		if ((dt <= 0))
		{
			return 0;
		}
		float err = (sp - meas);
		integral += (err * dt);
		return ((kp * err) + (ki * integral));
	}
}
```

Method names are emitted **verbatim**, not PascalCased. That is not only 1:1
with your Beryl source when you are staring at a Workbench error — it is
required, because a method overriding an engine callback must match its name
exactly.

## The lowering table

| Beryl | EnforceScript |
|---|---|
| `struct` | `class`, prefixed |
| `enum` | `enum`, prefixed |
| `i32` | `int` |
| `f32` | `float` |
| `bool` `str` | `bool` `string` |
| `char` | `int` |
| `Vec2` `Vec3` `Vec4` | `vector` |
| `List<T>` / `[T; N]` | `array<T>` |
| `Map<K,V>` | `map<K, ref V>` |
| `Box<T>` `Rc<T>` | `ref T` — **`Rc` costs nothing here**, the engine already refcounts |
| `T?` | a generated `SPK_Opt_T` wrapper class |
| `!T` | `bool` return plus an `out` parameter |
| `inout` / `set` param | `out` param |
| free function | a static method on a per-module holder class |
| module doc, field doc | `//!` |
| `i64 u64 u32 u16 u8 i16 i8 f64` | **BE0701** — refused |
| `@unsafe(...)` | **BE0703** — refused |
| `@server_only` misuse | **BE0705** |

## The three things worth knowing

**Value semantics cost a copy.** Beryl structs are values; EnforceScript classes
are references. Each emitted class gets a `BerylCopy()`, and the emitter calls it
at exactly the points the language requires a copy — binding, assigning or
returning a place expression — and nowhere else. An argument that merely borrows
needs no copy, so the common case is free.

**`!T` loses the error tag.** It lowers to `bool` + `out`, the idiom the base
game already uses. A caller can tell that *an* error happened, not *which*. If
you need to distinguish, return an enum.

**The profile lint runs before emission.** `i64` is not a narrower `int`, it is
a type EnforceScript does not have, so Beryl refuses it at compile time with the
substitute named:

```
error[BE0701]: `i64` is not supported on the enfusion target
 --> src/mesh.be:4:5
  |
4 |     big: i64
  |     ^^^^^^^^
  |
  = note: EnforceScript has one integer type, a signed 32-bit `int`
  = help: use `i32` for this field
```

That refusal is the entire point. It costs you one clear error instead of
fifteen seconds and a cascade.

## Proving it compiles

A golden test proves the emitted text is what was expected. Only Workbench
proves it compiles, and the difference is not academic — the first real build
found two bugs whose output looked entirely reasonable:

- `out` is a reserved word in EnforceScript. Colliding with it surfaces only as
  `Broken expression (missing ';'?)`, with no hint of the cause.
- `Clone` is already declared on the engine's base class, so redeclaring it is a
  hard error.

Both are now regression tests, and the check is repeatable:

```powershell
.\scripts\reforger-proof.ps1
# ok  Workbench compiled the generated script cleanly
```

It builds a throwaway addon containing nothing but generated script, so your
real mod is never touched.

## Security, for a mod taking client RPCs

This is the case the security model was built for: the arguments arrive from a
client you do not control.

```beryl
//! Bounds an index the caller supplied. `@validator` is what tells the taint
//! engine its result is trustworthy.
@validator
pub fn safe_slot(let raw: i32) -> i32 {
    return clamp(raw, 0, 63)
}

@server_only
pub fn Store.commit(inout self, let slot: i32, let value: i32) {
    self.slots[slot] = value
}

//! Every parameter here came off the wire.
@untrusted
@server_only
pub fn Store.on_client_update(inout self, let slot: i32, let value: i32) {
    self.commit(safe_slot(slot), value)
}
```

Drop the `safe_slot` call and you get `BE0601` pointing at the index. Call
`commit` from a function that is not `@server_only` and you get `BE0705`. Both
are compile-time and cost nothing at runtime.

Read [THREAT-MODEL.md](THREAT-MODEL.md) before relying on this: it is a strong
lint, not a proof, and residual **S6** notes that Beryl can guarantee properties
of the *generated script*, never of the engine executing it.

## Limits worth knowing before you start

- **`test` blocks are not emitted.** They run natively, which is the point.
- **`main` is not emitted.** Enfusion has its own entry points.
- **No component scaffolding yet.** The paired `...ComponentClass` declaration
  a scripted component needs is v0.2; write that shell by hand and call into
  Beryl-generated classes from it.
- **No engine API bindings.** Beryl does not know about `IEntity`, `Print`
  aside, or anything else in the engine. Today it is for the *pure logic* half
  of a mod: controllers, state machines, math, data structures. That is also the
  half that most benefits from being testable in milliseconds.
