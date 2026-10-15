# Beryl

**Active delivery work:** [approved program](docs/BERYL_DELIVERY_PLAN.md) and
[implementation state](docs/BERYL_DELIVERY_STATE.md). New working-tree changes
are not covered automatically by the installed checkpoint's receipts.

**October 14 focus:** core compiler and 4GL authoring work has resumed; further
Reforger testing is parked at the user's request. Source changes add experimental
IR initialization/access modes, a scalar-component project starter and repaired
tool-bundle inventory. The starter and inventory have scoped passing evidence;
Windows Code Integrity blocks completion of the full IR execution matrix.
See the [current implementation packet](docs/advanced/CORE_AUTHORING_2026_10_14.md).

**October 8 development update:** shared call-capture and receiver access repairs,
benchmark-process fixes and typed component admission now have scoped private-candidate
verification: 567 unit cases / 10,512 checks, 102 component-validator cases and
60 Enfusion source-admission cases. CLI/MCP compatibility also passed.
The next private candidate adds experimental scalar component wrappers, exact
compiler linkage and companion source origins. Its isolated tablet protocol
passed 92 cases / 3,432 assertions in reference and native execution, with ten
deliberate faults detected. The same protocol now passes all 92 cases in the
actual Enfusion VM with scripted service replies. A confirmed generated component
constructor defect was repaired and its corrected addon compiles in Workbench.
Plain-script retained state passes a separate 11-case engine probe; real component
callback delivery and tablet services remain open. This is not a production tablet migration.
An isolated Beryl-driven tablet service candidate also compiles with the preserved
MESH Game scripts; its runtime and deployment acceptance remain open.
Earlier Windows application control blocks some generated native executables; the current
release gate and active compiler provenance remain incomplete. Read
[the current evidence and next gates](docs/BERYL_DELIVERY_STATE.md).

**Historical September 7 checkpoint:** 496 cases / 10,285 checks, 18 native regressions at O0/O2, 867 engine
integer/order checks and 65,850 PID comparisons. It adds safety containment,
capability context, `doctor`, exact-snapshot analysis and an optional local MCP
bridge. Read [the current state and open gates](docs/BERYL_DELIVERY_STATE.md).
Production IR lowering, full ownership, the tablet migration and whole-mod authoring
remain unfinished. No game frame-rate or native Rust advantage is claimed.

A systems language named for beryllium: stiffer than steel per unit weight, very
light, and dimensionally stable at temperature. That is the thesis — **stiff**
(strong static guarantees), **light** (small binaries, fast builds), **hot**
(real-time game loops).

One source, two targets:

```
.be ─┬─→ C ──→ clang ──→ native executable
     └─→ EnforceScript ──→ Arma Reforger Workbench
```

Write admitted mod logic once, test it natively, and generate EnforceScript for
Workbench. Pure logic changes can be checked without launching an editor for
every test. Target support and current bounds are listed in
[the generated capability catalogue](docs/FEATURES.md).

```bash
beryl new mymod
cd mymod
beryl test                    # test blocks, run natively
beryl run                     # build and run
beryl build -t enfusion --prefix SPK --out-dir ../MyMod/scripts/Game/MyMod
```

The new optional authoring tool can create a component project with shared logic,
importing tests and a strict companion description:

```text
beryl mod init --template scalar-component --project ./MyComponent --name "My component" --addon-id MyComponent --addon-guid <your-16-uppercase-hex-GUID>
```

Use a fresh destination and a compiler/tool bundle that advertises this feature.
See [the starter's exact domain and commands](docs/advanced/P6_MOD_INIT.md).
It generates source for the existing scalar component profile; engine execution,
deployment and complete prefab/layout authoring remain separate gates.

## The five ideas

**No lifetime annotations, and none needed.** Every value has one owner, and
references are *second-class*: a borrow cannot be stored in a struct, returned,
or put in a container. So a borrow can never outlive the call it was passed to,
there is nothing to annotate, and what remains is ordinary flow analysis rather
than a borrow checker.

The ownership implementation is still incomplete. The current compiler rejects
unsupported owning copies and transfers; general recursive storage cleanup is a
separate delivery gate.

```beryl
fn publish(inout store: MeshStore, sink e: Entity) -> bool
//         ^^^^^ exclusive, non-aliasing   ^^^^ ownership moves in
```

**Checked native integer arithmetic by default.** Explicit `wrapping_add` and
related operations state a different policy at the call site. Rust also supports
checked release arithmetic through [Cargo profiles](https://doc.rust-lang.org/cargo/reference/profiles.html).
Historical overhead figures are unverified; see [benchmark status](docs/BENCHMARKS.md).

**No implicit numeric conversion, ever.** Not even widening. `i32 + i64` is an
error with the cast in the help line.

**Declared provenance is checked at compile time.** `@untrusted` tracks untrusted
values through the admitted analysis; numeric clamping does not erase that
provenance. `@server_only` restricts source calls, while real server execution
requires a verified engine boundary. `@secret` and `@constant_time` enforce
bounded source restrictions. These are [documented checks](docs/THREAT-MODEL.md),
not a whole-program security or machine-code timing proof.

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
| [ROADMAP](docs/ROADMAP.md) | where it goes next, and what to do first |
| [INTERNALS](docs/INTERNALS.md) | how the compiler is built |
| [BUILDING](docs/BUILDING.md) | building the compiler |

Browsable versions:
**[reference](https://claude.ai/code/artifact/296829be-41ec-424f-b86b-13a83b1336f6)** (the cheatsheet, with a
filterable diagnostics table) and
**[roadmap](https://claude.ai/code/artifact/6dc455ec-3425-4828-8b25-5237130f8876)**.

## Where it stands

v0.1 is functional but unfinished. Native programs and selected generated
EnforceScript workloads have executed in recorded checks. Target coverage is
bounded; an earlier Workbench result does not verify every current program or
the current working tree. See [delivery state](docs/BERYL_DELIVERY_STATE.md) for
the actual checkpoints and remaining gates.

The following figures are historical early-v0.1 notes, not measurements of the
current compiler. Their original configuration is not fully recorded here;
do not use them as current size, speed or test-coverage claims.

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

Beryl's native backend generates C for Clang. User-defined generic instantiation
and complete owned-storage semantics are still missing. No equivalent-workload
performance advantage over Rust has been established. Current design priorities:

- **Checked arithmetic by default**, with explicitly selected alternatives.
- **No lifetime annotations**, with ownership correctness still under development.
- **No build-time code execution**, structurally.
- **Compile speed** — a design constraint rather than an accident.

And where it does not: Beryl is a v0.1 with no generics, no traits, no
concurrency, no ecosystem, and a compiler written in C that is itself the
largest item on its own threat model. Rust is none of those things.
