# Beryl — Roadmap

**Current delivery order (2026-09-07):**
[BERYL_DELIVERY_PLAN.md](BERYL_DELIVERY_PLAN.md) consolidates the approved safety,
IR, tablet, AI tooling, deployment and measured-performance program.
[Delivery state](BERYL_DELIVERY_STATE.md) records active work and exact new gates.
It takes precedence over historical sequencing below.

**Advanced program (2026-09-07):**
[BERYL_ADVANCED_IMPLEMENTATION_PLAN.md](BERYL_ADVANCED_IMPLEMENTATION_PLAN.md)
extends the SPARKOS sequence with gated performance work. Its
[execution state](BERYL_ADVANCED_IMPLEMENTATION_STATE.md) distinguishes implemented
capabilities from pending experiments and release gates.

**Latest installed delivery checkpoint:** safety containment, expression-order
repairs, generated capability/example context, environment diagnostics,
exact-snapshot analysis and a hardened local MCP bridge. Both foundation builds
passed 496 cases / 10,285 checks and 18 O0/O2 native regressions; the final engine
integer/order and complete PID suites passed. Public IR, full owning storage,
tablet generation, dedicated-client release and automatic optimizations remain
open. [Delivery state](BERYL_DELIVERY_STATE.md) is the authoritative receipt index.

**Earlier installed checkpoint:** bounded engine-binding context, actual storage
probes, experimental record/PID IR parity and a replayable terrain collection are
verified. The final collection recorded 34.06% median paired reduction in command
construction/release time; full-render/resource/independence gates remain open.
No automatic optimizer or public IR backend is released. Use the execution state
above for exact source hashes, corrected harnesses and next dependencies.

**Active implementation plan (2026-09-06):**
[SPARKOS_IMPLEMENTATION_PLAN.md](SPARKOS_IMPLEMENTATION_PLAN.md) is the approved
Enfusion-first sequence; [execution state](SPARKOS_IMPLEMENTATION_STATE.md) records
its gates and current evidence. That sequence takes precedence over historical
release ordering below.

**Written 2026-09-04, against v0.1.**

**Implementation update, 2026-09-06:**
[FOUNDATION_IMPLEMENTATION.md](FOUNDATION_IMPLEMENTATION.md) records the first
compiler-correctness tranche, 259 unit cases / 1,104 checks, 13 O0/O2 native
regressions and targeted Workbench compile results. Read it with the blueprint
before implementing historical findings. The bounded reference interpreter and
declaration/module work now have verified [M2](M2_IMPLEMENTATION.md) and
[M1](M1_IMPLEMENTATION.md) gates. The full PID's current real-mod gate is tracked
in [M3](M3_IMPLEMENTATION.md), whose isolated MESH gameplay/handover gate passed
on September 7. [M4](M4_IMPLEMENTATION.md) is next; live-project deployment and
independent multiplayer remain separate. Historical release labels below do not
override that evidence.

[Browsable version](https://claude.ai/code/artifact/6dc455ec-3425-4828-8b25-5237130f8876) — its source is `docs/roadmap.html`, which is a
curated summary of this file rather than a rendering of it; edit both.

This is the document to re-read before starting any significant piece of work on
Beryl, and to update when a decision here turns out to be wrong.

---

## 0. How to use this

Sections **1–3** are the state of the world: what exists, what it is for, and
everything known to be broken or missing. Read those when returning to the
project after a gap.

Section **2** also settles the two-edition question: **Beryl/Enfusion** and a
general-purpose **Beryl**, shipped from one compiler rather than a fork (§2.1),
with the general edition aimed at games and simulations rather than at Rust in
general (§2.2).

Section **4** is the release plan — §4 for the Enfusion edition, §4.2 for the
general edition's later track. Read it to decide what to do next.

Sections **5–6** are design work: the hard problems worked through in enough
detail to start implementing, plus capabilities not yet on any list. Read the
relevant one before touching that area.

Sections **7–9** are the guardrails: what Beryl deliberately will not do, what
would make it not worth continuing, and a log of decisions already made so they
are not re-litigated.

**The one thing to take away:** §2 argues Beryl has exactly one *proven*
defensible advantage today, and §4.1 proposes a cheap experiment that confirms
or kills it. Do that experiment before building anything else — including
anything on the general edition's track, which is bet entirely on the same
assumption.

---

## 1. Where we are

v0.1 works. It is not a toy — it compiles and runs real programs on two targets,
and the EnforceScript it emits compiles cleanly in the actual Arma Reforger
Workbench.

| | |
|---|---|
| Compiler | 297 KB, C11, zero dependencies |
| Source | ~11,800 lines (common 1.1k · lex 0.8k · parse 2.6k · sema 3.2k · back 2.8k · driver 1.1k · runtime 0.3k) |
| Tests | 204 unit cases, 931 checks, 9 end-to-end programs, 2.6k lines |
| Diagnostics | 59 codes, all documented, enforced by a script |
| Docs | 14 documents, ~2,400 lines, plus a published reference |
| Front end | 10,000 lines checked in 124 ms |
| Back end | 2.3 s for 10,000 lines including `clang -O2` |

**What is genuinely good:** the diagnostics (rustc-grade, with the fix in the
help line), the ownership model (no lifetimes, and the checker is small enough
to read), the Enfusion lowering (verified against real Workbench), and the
honesty discipline in the docs.

This original snapshot predates the installed M1 module implementation and the
delivery safety work. Current counts, supported modules and taint limits are
reported in [STATUS.md](STATUS.md) and [delivery state](BERYL_DELIVERY_STATE.md).

---

## 2. The thesis — what Beryl is for

This section exists because a roadmap without a north star becomes a wishlist,
and the order of everything below depends on getting this right.

Beryl is two languages sharing one compiler:

**(a) Beryl/Enfusion — a better language for Arma Reforger mod logic.** Write it
once, test it natively in milliseconds, emit EnforceScript that Workbench
compiles.

**(b) Beryl — a general-purpose systems language competing with Rust.**

Both are goals. **(a) ships first, because it is the wedge.**

(b) is the harder of the two by a wide margin. It needs generics, traits,
concurrency, an ecosystem, a package registry, an LSP, cross-platform support,
and years of hardening — and a pitch better than "like Rust, but younger and
with fewer libraries," which is a losing one. §2.2 is about finding that pitch,
and it exists: the honest version of (b) is not a general Rust replacement but
**systems programming for games and simulations**, where Rust is structurally
weakest and Beryl's design is structurally strongest.

(a) has a moat, and it is a good one: **nobody else can give you a fast test loop
for EnforceScript.** Today, verifying pure logic in a Reforger mod costs a 10–15
second Workbench build in which one real error spawns a cascade of phantom ones.
Beryl turns that into milliseconds. That advantage is structural — it comes from
having a second back end — and it cannot be copied by a linter, a formatter, or
a better editor plugin.

### What follows from this

Every item below is ordered by **does it serve the wedge**, which reshuffles the
obvious priorities considerably:

| | was | becomes | why |
|---|---|---|---|
| Engine API bindings | not planned | **highest** | without them you can only write the pure-logic half of a mod |
| Component & RPC scaffolding | not planned | **highest** | same |
| Codegen trust | noted as THREAT-MODEL S9 | **highest** | you cannot ship mod code you do not trust |
| Module system | working (it isn't) | **high** | it is broken and it is cheap to fix |
| Generics | headline v0.2 | medium | containers cover most needs; forced duplication is annoying, not blocking |
| Self-hosting | the answer to S1 | low, deferred | see §5.8 — hardening buys most of the risk reduction for 5% of the cost |
| Concurrency | listed as v0.2 | **deferred to the general edition** | Enfusion scripting is single-threaded, so it is a precondition for (b) and irrelevant to (a) — §5.11 |

Note what that reshuffling is *not*: it is not a demotion of (b). Everything on
that list except the two Enfusion rows serves both editions — most of what (a)
needs is a real module system, working generics, a standard library and
trustworthy codegen, which is also the first half of (b). **The wedge is not a
detour, it is the shared foundation with a customer attached.** §2.1 covers how
the two ship from one compiler; §2.2 covers what (b) has to become to be worth
shipping at all.

---

### 2.1 Two editions, one compiler

The intent is two languages: **Beryl/Enfusion**, the Reforger-targeted one being
built now, and **Beryl**, a general-purpose systems language without the engine
parts.

**The mechanism should be editions, not a fork.** That is not a hedge — it is
what the codebase already is.

#### The measurement

Every line of Enfusion-specific code, as of v0.1:

| | |
|---|---|
| `src/back/enforce_*.{c,h}` | 1,331 lines |
| `src/driver/main.c` | ~11 lines — a CLI flag and its dispatch |
| `src/driver/manifest.{c,h}` | ~6 lines — the `[target.enfusion]` section |
| `src/sema/` | **zero.** Every mention is a comment. |
| `src/lex/`, `src/parse/` | **zero.** No mention at all. |

The two mentions in `src/back/c_backend.c` are diagnostic *text* — the BE0901
note telling you `Map` works on the other target — not logic.

**The general edition is the current compiler minus 1,331 lines**, or roughly
11% of it. It already exists; `beryl build` with no `-t enfusion` is it.

#### Why not fork

A fork buys separate branding and costs everything else: two bug fixes for every
bug, two test suites, two sets of diagnostics drifting apart, and a slow
divergence that eventually makes the shared work impossible. Beryl is a
12,000-line compiler maintained by one person — that is exactly the situation a
fork ruins.

Editions cost almost nothing because the profile mechanism already carries the
difference. `BE0701` (a type EnforceScript lacks), `BE0703` (`@unsafe`
forbidden), `BE0901` and `BE0902` (things the native back end lacks) are the
same idea pointed in both directions: **a target profile gates features the
target cannot express, and the language keeps them.**

Separate branding, separate documentation, even separate binaries are all
packaging decisions that sit on top of one compiler. Ship
`beryl-enfusion.exe` as a build with the native profile hidden if that is what
the identity calls for.

#### The one rule that keeps this free

> **Design every feature for the native target first. Then ask how it lowers to
> EnforceScript. If it cannot, profile-gate it — never remove it from the
> language.**

The danger was never code coupling; it is *design contamination* — choosing a
language semantic because Enfusion cannot do otherwise. An audit of v0.1 against
that rule:

| decision | forced by Enfusion? | harms the general edition? |
|---|---|---|
| Monomorphization (D3) | yes | **no** — it is the right choice regardless; Rust does the same |
| `!T` as tag + value | no, that is the native design | no |
| `!T` loses its tag on Enfusion | lowering only | no — a target compromise, not a language rule |
| Value semantics via `BerylCopy` | lowering only | no |
| Full integer set, `i32`-only on Enfusion | profile lint | no — the core kept all widths |
| Verbatim method names (D8) | yes | marginally — the general edition may want a case convention |

**Almost no contamination so far**, and that is not luck: the profile-lint
mechanism absorbed each constraint instead of the core absorbing it. Keep doing
that.

#### When a real fork would be justified

Only if a **core semantic** must diverge — if the general edition wanted
first-class references, breaking D1, for instance. That would be a different
language, not a variant, and it should be named and reasoned about as one. Short
of that, forking is a cost with no matching benefit.

*(If distinct names are wanted later: beryl is a mineral family, and its
varieties — emerald, aquamarine, heliodor, morganite, goshenite — are sitting
right there.)*

---

### 2.2 What "better than Rust" has to mean

The goal is stated. This section is about making it a plan rather than an
aspiration, because "better than Rust" without an axis is not something you can
build toward or ever know you have achieved.

#### Candidate advantages to establish through implementation and measurement

1. **Graphs and cyclic data.** Generational handles may suit game workloads;
   Beryl's Pool/Handle implementation is still proposed. Rust can also use
   index-based or generational handles without first-class graph references.
2. **Compile speed.** Measure equivalent authoring tasks and actual rebuilds.
   The historical synthetic 124 ms result does not establish a Rust comparison.
3. **No lifetime syntax.** This reduces one authoring burden; complete ownership
   and storage safety still need implementation and evidence.
4. **Determinism.** Fixed-point types and a deterministic profile are proposals.
   Rust can implement deterministic numerical policies too.
5. **Checked release arithmetic by default.** Rust supports configurable release
   overflow checks; compare the actual policies and workloads.
6. **No project build scripts or procedural macros.** A deliberate restriction
   on Beryl's authoring model, with the native toolchain still part of the trust boundary.

#### Where Rust wins, and will keep winning for years

- **crates.io.** Roughly 180,000 packages. This is not a feature gap, it is a
  decade of other people's work, and no design decision closes it.
- **Concurrency.** `Send`/`Sync` is genuinely excellent, and Beryl has *cut*
  concurrency entirely. Closing this is a precondition for the general edition,
  not a nice-to-have (see §5.11).
- **Tooling.** cargo, rust-analyzer, clippy, miri. Years of work each.
- **Soundness track record.** Ten years of people trying to break it.
- **Platform breadth.** Beryl compiles on one machine, on one OS, today.

#### The honest conclusion

**"Better than Rust" is achievable on an axis, not globally**, and pretending
otherwise wastes years. The axis that fits Beryl's design is
**systems programming for games and simulations**:

- where graphs and identity are common;
- where iteration time can be measured on real authoring tasks;
- where an explicit deterministic profile may help;
- and where the ecosystem gap is smallest, because game engines bring their own
  world rather than pulling 200 crates.

That is a position you can actually win, and it has an elegant property: **it is
the same domain as the Enfusion edition.** The two editions do not merely share
a compiler, they share a wedge. Everything learned building for Reforger —
handles instead of references, determinism, a fast test loop, trustworthy
codegen — is exactly what the general edition needs.

Aim there. "General purpose" then follows from being genuinely good at
something, which is how every successful language has actually happened.

---

## 3. The ledger

Historical planning ledger, retained to explain the original priorities.
C2 was addressed by qualified module resolution and privacy enforcement. C3 is
being addressed by the bounded delivery taint pass; its broader security gate
remains incomplete. Immediate `defer` is now an explicit preserved contract.
Use the delivery plan and state for current outstanding work; these rows do not
override newer implementation evidence.

### 3.1 Correctness and trust — these can burn you silently

| # | Debt | Why it matters |
|---|---|---|
| **C1** | **Codegen has 9 end-to-end programs guarding two back ends.** | A bug producing *valid but wrong* C passes clang, passes the type checker, passes every test, and ships. This is the one that costs you trust in the whole project. Threat model S9. |
| **C2** | **`pub` is not enforced; `use` is decorative.** *(Found while writing this document.)* A private function in another module is callable with no import. The module system is a flat namespace with cosmetic syntax. | Silent. Any encapsulation you think you have, you do not have. Gets worse the more code exists. |
| **C3** | **Struct fields are not taint-tracked.** Store an untrusted value in a field in one function, read it in another, and the security analysis sees nothing. | The `@untrusted` feature has a hole wide enough to defeat its purpose. Threat model S3. |
| **C4** | **`defer` runs where written, not at scope exit.** | Contradicts the spec and every reader's expectation. Currently harmless because there are no destructors; becomes a real bug the moment there are. |
| **C5** | **`catch` yields a zero value** when the handler does not return. | Fine for `catch \|e\| { log(e); return }`; quietly wrong for anything else. |
| **C6** | **The lexer and parser have never been fuzzed.** | S1's risk is unquantified. A crafted `.be` file is the compiler's only untrusted input. |
| **C7** | **No CI.** Everything is verified by hand on one machine. | Regressions are found when someone remembers to look. |

### 3.2 Capability — these block real use

| # | Debt |
|---|---|
| **P1** | **No engine API bindings.** Beryl knows nothing about `IEntity`, `ScriptComponent`, `RplComponent`, or anything else. Only the pure-logic half of a mod can be written. |
| **P2** | **No component or RPC scaffolding.** The paired `...ComponentClass`, `[Attribute()]` editor properties, and `RplRpc` decorations must all be hand-written. |
| **P3** | **`lib/` is empty.** There is no standard library written in Beryl at all — the directories were scaffolded and never filled. |
| **P4** | **No user-defined generics** (BE0508). Forces copy-paste for anything polymorphic. |
| **P5** | **No traits.** They parse and are then ignored entirely — no resolution, no bound checking. |
| **P6** | **`Box`, `Rc`, `Pool`, `Handle` do not exist** (BE0902). The ownership model is *designed* around handles as the answer to "how do I build a graph", and that answer is not implemented. |
| **P7** | **`Map` has no native representation** (BE0901) and no methods on either target. |
| **P8** | **No `match`, no payload-carrying enums.** |
| **P9** | **No string formatting.** `print` takes one value. There is no `"x = {}"`. |
| **P10** | **No slices.** No way to pass a subrange of an array. |
| **P11** | **No I/O of any kind** beyond `print`. |
| **P12** | **Windows only.** The compiler core is portable C11, but `src/driver/{build,main,manifest}.c` use `_popen`, `_findfirst` and `cmd /c`. Never built or tested elsewhere. |

### 3.3 Ergonomics

| # | Debt |
|---|---|
| **E1** | No LSP — no completion, no go-to-definition, no inline diagnostics. |
| **E2** | No `beryl explain BE0401`. The docs exist; the compiler cannot show them. |
| **E3** | No package management. Path dependencies only, and even those are unimplemented. |
| **E4** | No generated API docs, despite `//!` comments already being parsed and stored. |
| **E5** | No incremental compilation. Not urgent at 124 ms, but it will be. |

### 3.4 Strategic

| # | Debt |
|---|---|
| **S1** | The compiler is written in C — the largest single item on its own threat model. |
| **S2** | **Builds are not reproducible**, and cannot be while the Smart App Control workaround varies the binary per attempt. Two stated goals in direct conflict; unresolved. See §5.9. |
| **S3** | **Two spec targets were measured as failures**: hello-world binary (< 20 KB claimed, 91.6 KB measured, unreachable on this toolchain) and overflow overhead (< 3% claimed, +82% measured). Both are documented; neither is fixed. |
| **S4** | `@constant_time` is a source-level lint that clang can undo. No optimization barriers are emitted. |
| **S5** | **Design contamination is now a live risk.** With the general edition a stated goal (D12), any feature shaped by what EnforceScript cannot do becomes a permanent tax on a second language. D14 is the rule; §2.1's audit is the check. It should be re-run at each release, because it is cheap and the damage is only visible in aggregate. |
| **S6** | **`Pool<T>` has not been designed against concurrency** (§5.11): handles alias where references cannot, so a pool shipped in v0.5 with the wrong API forecloses the cleanest concurrency answer years later. Cheap to avoid now, expensive to retrofit. |

---

## 4. Release plan

Each release has a **theme**, an **exit criterion** that is a fact rather than a
feeling, and a rough size. Sizes are compiler-source lines, which has been a
decent proxy so far.

### v0.2 — "Trust the output, and prove the thesis"

The two things that must be true before any more building: you can trust what
comes out of the compiler, and the reason for the project is real.

1. **Port a real SPARKOS MESH class end to end and ship it in the actual mod**
   (§4.1). Not an example — a class that is currently in the mod, ported,
   generated, and running in-game with the handwritten original deleted.
2. **Fix the module system** (C2, §5.3) — ~300 lines. Cheap, and everything
   built on a broken namespace has to be redone later.
3. **Build the interpreter** (§5.2) — ~900 lines. The keystone: it gives a
   differential oracle for codegen, a near-instant test loop, and a REPL.
4. **Differential and metamorphic testing** (§5.1) — ~400 lines, on top of the
   interpreter.
5. **Fuzz the lexer and parser** (C6) — ~200 lines plus a corpus.
6. **CI** (C7) — build, check-all, bench, on every push.
7. **Fix `defer` and `catch`** (C4, C5).

**Exit criterion:** a real SPARKOS MESH class is running in-game from generated
code, and 10,000 randomly generated programs produce identical output through
the interpreter and the native back end.

**Size:** ~2,000 lines. This is the release that decides whether Beryl is a
project or a hobby.

### v0.3 — "Whole mods"

Everything needed to write a complete Reforger mod in Beryl, not just its pure
logic.

1. **`extern` declarations** (§5.5) — a way to declare engine API surface that
   the Enfusion back end trusts and the native back end refuses.
2. **Hand-written bindings** for the engine API that SPARKOS MESH actually uses.
3. **`@component`** — emits the paired `...ComponentClass` declaration.
4. **`@attribute`** — editor-exposed properties.
5. **`@rpc(server)` / `@rpc(broadcast)`** — emits the `RplRpc` decoration **and
   implies `@untrusted` on every parameter** (§5.5). Nobody has to remember.
6. **In-game headless testing** — run the generated mod hidden and assert on log
   output, using the existing headless capability.

**Exit criterion:** an entire small mod — components, RPCs, editor attributes,
logic — written in Beryl, loading and running in-game.

**Size:** ~1,400 lines.

### v0.4 — "Expressiveness"

The language features whose absence causes daily friction.

1. **Generic functions**, monomorphized (§5.4) — ~600 lines.
2. **Generic structs** — ~400 lines.
3. **Traits with bound checking** — ~500 lines.
4. **`match` and payload-carrying enums** — ~700 lines.
5. **Slices `[]T`** — ~350 lines.
6. **String formatting** — ~400 lines.
7. **`Map` methods and a native representation** — ~500 lines.
8. **The first real `lib/`**, written in Beryl (P3).

**Exit criterion:** the standard library is written in Beryl, not C, and
compiles for both targets.

**Size:** ~3,500 lines.

### v0.5 — "Memory"

Implement the parts of the ownership model that were designed and then skipped.

1. **`Box<T>`** — unique heap ownership.
2. **`Rc<T>`** — free on Enfusion, refcounted natively.
3. **`Pool<T>` + generational `Handle<T>`** (§5.7) — the language's own answer to
   "how do I build a graph", which currently does not exist.
4. **Destructors and real scope-exit `defer`.**
5. **Drop-order checking** in the ownership pass.

**Exit criterion:** a linked structure — a scene graph or an entity store — is
expressible without an array index by hand.

**Size:** ~1,500 lines.

### v0.6 — "Platform"

1. **Cross-platform** (P12) — abstract the three driver files; test on Linux.
2. **LSP** (E1) — ~1,500 lines. The front end is already fast enough to run per
   keystroke.
3. **`beryl explain BE####`** (E2) — ~150 lines, embedding the docs.
4. **`beryl doc`** (E4) — ~400 lines, from the `//!` comments already parsed.
5. **`beryl bench`** — benchmarks as a first-class construct.
6. **Path dependencies** actually implemented (E3).

**Size:** ~2,800 lines.

### v0.7 — "Determinism"

The features a networked game actually needs, which nothing above provides.
See §6.

1. **Fixed-point types** (`q16.16`) for deterministic arithmetic.
2. **`@deterministic`** — forbids anything that varies across machines.
3. **`@serialize`** — compile-time derivation of a wire format for both targets.
4. **Units via newtypes** — `type Meters = f32` with no implicit conversion.

**Size:** ~1,800 lines.

### v0.8 — "Self-hosting groundwork"

Only if v0.2–v0.7 have made the language good enough to write a compiler in.
See §5.8 for why this is late and why that is right.

1. Port the **lexer** to Beryl as a forcing function and a proof.
2. Whatever the standard library turns out to be missing.

### v1.0 — "Stability"

A promise not to break source compatibility without a major version. Do not make
it before the language has been used to build something real for a year.

---

### 4.1 The experiment to run first

Everything above is speculative until this is done, and it costs almost nothing.

**Take `SPK_MeshStore.c` and `SPK_PID.c` out of SPARKOS MESH. Rewrite them in
Beryl. Generate. Delete the originals. Ship it.**

Then answer honestly:

1. Was the loop actually faster, or did generation and re-generation eat the
   gain?
2. Did anything break that the type checker should have caught?
3. Was reading the generated script in Workbench tolerable when something *did*
   break?
4. Would you do it again for the next class?

If the answer to (4) is no, **stop and reconsider the whole project** before
writing another 10,000 lines. If it is yes, everything below is justified and
the ordering in §2 is correct.

This is the highest-value item in this document.

---

### 4.2 The general edition's track

v0.2 through v1.0 above are the **Enfusion edition**. The general edition
(§2.1, D12) runs on a second track that starts after v1.0, because almost
everything in the first track is shared work rather than a detour:

| v0.2–v1.0 item | serves |
|---|---|
| Codegen trust, differential testing, fuzzing (§5.1) | **both** |
| Module system (§5.3) | **both** |
| Generics and traits (§5.4) | **both** |
| The interpreter (§5.2) | **both** |
| `Box` `Rc` `Pool` `Handle` (§5.7) | **both** — with the §5.11 caveat |
| Determinism, fixed-point (§6.1) | **both** |
| Portability and CI (§5.10) | **both** |
| Engine bindings, component and RPC scaffolding (§5.5) | Enfusion only |
| Standard library, I/O, FFI, concurrency, LSP, registry | general only |

Only the last two rows are edition-specific, and only one of them is on the
first track. **That ratio is the argument for D13.**

The second track, in rough dependency order — sizes are guesses, and the
ordering inside it is far less settled than the first track's:

| | theme | contains | exit criterion |
|---|---|---|---|
| **G1** | Reach | macOS + Linux as first-class, real FFI behind `@unsafe(ffi)` — raw pointers, C ABI, a header binder | Beryl calls into an existing C library and is called from one, on three platforms |
| **G2** | Concurrency | §5.11 in full: `Send` inference, scoped tasks, atomics, channels, and the `Pool<T>` aliasing decision | A data race is a compile error, and the ownership checker is still under 2,000 lines |
| **G3** | Standard library | I/O behind capabilities, collections, strings, formatting, time, math — **written in Beryl**, which is also the honest test of whether the language is pleasant | `lib/` is large enough that a non-trivial program needs no C |
| **G4** | Tooling | LSP, debugger integration, a package manager, and a registry only once there is something to put in it | Someone who has never seen the compiler source can be productive in an hour |
| **G5** | Hardening | soundness work at scale, a citable specification, a real conformance suite | A determined outsider fails to break it |

**The split criterion.** The general edition ships as its own thing on the day
a `beryl` binary with the Enfusion profile hidden is genuinely useful to
someone who has never heard of Arma Reforger. Not before — an early split buys
a second README and a second set of expectations to disappoint.

**Honest scale.** G1–G5 is years, and most of it is G3 and G4: a standard
library and tooling are where language projects actually die, not in the
compiler. Nothing on this track should begin until §4.1's experiment has been
run and v1.0 has shipped, because everything here is bet on the assumption that
the language is worth extending — and §4.1 is the cheapest test of that
assumption that exists.

---

## 5. Deep dives

### 5.1 Trusting the code generator

**The problem.** Nine end-to-end programs guard two back ends. A codegen bug that
produces valid-but-wrong C is invisible to clang, to the type checker, and to
every test. The failure mode is not a crash — it is a PID controller that is
subtly wrong in flight.

Writing more end-to-end programs is linear effort for linear coverage. Four
better approaches, in order of value:

**(a) Differential testing against an interpreter.** Build an AST interpreter
(§5.2), then: for a given program, run it interpreted and run the compiled
binary, and require identical output. Now every test program tests the code
generator, and a random program generator makes that arbitrarily many programs.

This is the single highest-leverage testing idea available, and the interpreter
pays for itself three other ways.

**(b) Metamorphic testing.** Transform a program in ways that must not change its
output — rename every binding, reorder independent statements, wrap a body in a
function and call it, replace `a + b` with `wrapping_add(a, b)` where overflow is
impossible — and require identical output. This finds bugs a random generator
misses, because it explores *near* real programs rather than uniformly.

**(c) Optimization-level differential.** Compile the same program at `-O0` and
`-O2` and compare. Any difference is either a codegen bug or emitted C with
undefined behaviour, and both are worth knowing about immediately.

**(d) Cross-target differential.** The hard one, and the most valuable for the
wedge: generate a program, run it natively, emit EnforceScript, run *that* in a
headless Workbench session, and compare. This is the only thing that can prove
the two back ends agree. The headless-run capability already exists in the
Reforger tooling; the missing piece is a generated harness class that prints
results in a parseable form.

**Order:** (a) and (c) in v0.2, (b) shortly after, (d) in v0.3 alongside the
in-game testing work, since they share infrastructure.

**Also:** every future back-end change ships with new end-to-end programs. Nine
was never enough; the rule should be that a code path without an executing test
does not merge.

### 5.2 The interpreter — one component, four payoffs

Build a tree-walking interpreter over the typed AST. Roughly 900 lines. It is the
best-value item on the entire roadmap because it solves four problems at once:

1. **A differential oracle for codegen** (§5.1a) — the scariest gap, closed.
2. **A near-instant test loop.** `beryl test` currently costs a clang invocation
   plus process startup. M0 removes execution retries. Interpreter latency must
   be measured after implementation. For the wedge — *the test loop is the entire
   product* — this matters enormously.
3. **Unifies constant evaluation.** `constfold.c` is already a small interpreter
   over a subset. Replace it with the real one and `comptime` blocks, const
   functions and const generics all become straightforward instead of each being
   a separate special case.
4. **A REPL.** Falls out almost free, and is the fastest way to answer "what does
   this expression actually do".

**Design notes.** Values are a tagged union; locals live in a frame vector
indexed by the `Local.id` the checker already assigns. Traps raise the same
diagnostics the runtime does, so an interpreted overflow reports identically to a
compiled one — which matters, because otherwise the differential test fails on
error messages rather than behaviour. Bound it in steps so a runaway test is a
diagnostic rather than a hang, exactly as constant evaluation already is.

**Sequencing:** interpreter first, then `beryl test` switches to it by default
with `--native` to force compilation, then differential testing on top.

### 5.3 The module system

**Current state:** broken in a way that was not noticed until this document was
written. `use` is parsed and used only for cycle detection. `pub` is stored and
never checked. All short names resolve across the entire program. A private
function in another module is callable with no import.

**The fix**, roughly 300 lines:

1. Resolution consults the **importing module's** scope: its own items, plus
   what its `use` statements name, plus the built-ins.
2. `pub` gates cross-module visibility. Allocate a fresh diagnostic for **`x` is
   private to module `y`**, with a help line offering `pub`.
3. `use a.b.C` imports one item; `use a.b` imports the module for qualified
   access (`b.C`).
4. Ambiguity between two imported modules is an error naming both, not
   first-wins.
5. **Unused import**, as a warning with a fresh diagnostic code. BE0319/BE0320
   already identify vector errors; do not reuse them for module diagnostics.

**Do this in v0.2.** It is cheap, it is a correctness bug, and every line of
Beryl written before it is fixed is written against a namespace that will
change.

### 5.4 Generics and traits

**Settled by the Enfusion target:** monomorphization, not dictionary passing.
EnforceScript has no generics, so instantiation is mandatory rather than an
optimization. This is a case where the second back end made the design decision
for us, and made it correctly.

**Generic functions (~600 lines).**

- *Inference:* unify each declared parameter type (which may contain
  `TY_TYPEPARAM`) against the actual argument type, left to right, collecting a
  substitution. No inference from the return type in v0.4 — it is where most of
  the complexity lives and it buys little.
- *Instantiation:* deep-clone the item, substitute in the type map, mangle the
  name with the argument types, memoize on (item, substitution).
- *Iteration:* instantiating can create new generic call sites, so loop to a
  fixpoint. Cap the depth at 64 and report **BE0506 — generic recursion limit**,
  which is already reserved.
- *Re-checking:* run `check` over each instance. Errors report at the call site
  *and* at the generic definition, both labelled — a generic error reported only
  inside the template is very hard to act on.

**Generic structs (~400 lines).** Additionally need substitution in field types,
layout per instance, and — on the Enfusion side — a mangled class name per
instance (`Store<Entity>` → `SPK_Store_Entity`), which the lowering table already
promises and does not deliver.

**Traits (~500 lines).** Currently parsed and discarded. Needed:

- An implementation table keyed by (trait, type).
- `impl` syntax, which does not exist yet. Given methods are already free
  functions on a type, the natural form is `fn Ord.cmp` for `Pid` — worth
  designing carefully rather than importing Rust's `impl` block wholesale.
- Bound checking at instantiation: **BE0507 — unsatisfied trait bound**, already
  reserved, with the missing method named.
- `dyn` stays out of v0.4. It maps to a virtual class hierarchy on Enfusion and
  to a vtable natively, and neither is needed yet.

### 5.5 The Enfusion wedge — whole-mod capability

This is where the project's value actually is, and it is the least-built part.

**`extern` declarations.** A way to tell Beryl about engine API it cannot see:

```beryl
extern class IEntity {
    fn GetName() -> str
    fn GetOrigin() -> Vec3
}

extern fn Print(let msg: str)
```

The Enfusion back end emits calls to these verbatim and declares nothing. The
native back end refuses any program using one — a new **BE0903 — `extern` is
only available on the enfusion target**. Type-checked like anything else, so a
typo in an engine method name is caught by Beryl rather than by Workbench
fifteen seconds later.

**Generating bindings.** Hand-writing the whole engine API is not viable, and
grepping the base game paks is known to fail silently. The realistic path:
hand-write the surface actually used (a few hundred declarations covers a lot),
then later generate from the Workbench API index. Treat generation as a v0.6
nicety, not a blocker.

**`@component`.** Enfusion splits a scripted component into a class-level
descriptor and an instance. One attribute should emit both:

```beryl
@component(category: "SPARKOS", description: "Drone autonomy")
pub struct AutonomyComponent {
    max_speed: f32 = 20
}
```

emitting the paired `SPK_AutonomyComponentClass : ScriptComponentClass` and
`SPK_AutonomyComponent : ScriptComponent`, with `OnPostInit` and friends
overridable by name — which is exactly why method names are emitted verbatim.

**`@attribute`** for editor-exposed properties, emitting the `[Attribute(...)]`
decoration from the field's Beryl type and default.

**`@rpc` implies `@untrusted` — the best idea in this document.**

```beryl
@rpc(server)
pub fn Store.on_client_update(inout self, let slot: i32, let value: i32) {
    self.slots[slot] = value   // BE0601, automatically
}
```

An RPC handler's parameters arrive from a client you do not control. That is
true *by definition*, so it should not depend on a human remembering to write
`@untrusted`. Making `@rpc` imply it means the security model and the engine
model reinforce each other rather than sitting side by side, and it turns the
most common real Reforger vulnerability — trusting an RPC argument — into a
compile error you cannot forget to enable.

This is also the strongest argument for the whole security apparatus: it is not
a generic language feature looking for a use, it is aimed squarely at the thing
that actually goes wrong in networked mods.

### 5.6 Closing the taint holes

C3 is the serious one: struct fields are not tracked, so laundering taint
through a field defeats the analysis entirely. Two other holes: container
elements, and taint that crosses a function boundary through anything but a
return value.

**Field-sensitivity (~400 lines).** Extend the taint lattice from
`Local → taint` to `(Local, field path) → taint`, reusing the access-path
machinery the ownership checker already has. `path_of()` already computes root
plus field path; taint can key on the same structure. Depth-limit the paths, as
ownership does at six.

**Container elements.** Track one taint value per container rather than per
element — an untrusted value pushed into a list makes the whole list untrusted.
Coarse, and coarse in the safe direction.

**Interprocedural summaries.** A function gets a summary: which parameters flow
to the return value, and which flow into `inout` parameters. One pass over the
call graph in dependency order (already available — module cycles are forbidden).
This is where taint stops being a local lint and starts being useful.

**Constant-time (S4).** The current `@constant_time` is a source-level lint that
LLVM can undo. Two real improvements: emit optimization barriers around
secret-dependent values (an empty `asm volatile` with the value as an in/out
operand, which clang honours), and add a verification mode that disassembles the
emitted function and fails on any conditional branch. The second is real work
and belongs after v1.0 — but the barriers are cheap and should land with v0.7.

**And keep saying it is a lint.** No amount of this makes it a proof. The threat
model's honesty rule is load-bearing.

### 5.7 Box, Rc, Pool, Handle

These are not missing features; they are the ownership model's own answer to
"how do I build a graph" — and that answer currently does not exist, which is a
strange gap to have shipped.

- **`Box<T>`** — unique heap ownership. Native: malloc/free with a drop at scope
  exit. Enfusion: `ref T`. Straightforward once destructors exist.
- **`Rc<T>`** — refcounted. Native: a header word. **Enfusion: free**, because
  the engine already refcounts, which is a genuinely nice property worth
  advertising.
- **`Pool<T>` + `Handle<T>`** — the interesting one. A dense array plus a
  free-list, with a 32-bit slot and 32-bit generation. A stale handle is
  *detected* on access rather than dangling, which is strictly better than the
  raw index the language currently forces. Enfusion: `array<ref T>` plus an int
  index.

Doing these needs **destructors** first, which needs **real scope-exit `defer`**
(C4), which is why they cluster in v0.5.

**One constraint from years away.** `Pool<T>` is the point where the ownership
model's central bargain gets partially undone: **a handle is an index, and
indices alias where references cannot.** That is fine single-threaded, and it is
the whole concurrency problem for the general edition (§5.11, S6). It costs
nothing today to leave room for a `SyncPool<T>` — keep the pool's mutating
operations behind methods rather than exposing the backing array, and do not
promise that `get` returns something borrow-like. Retrofitting that after code
is written against the API is expensive; anticipating it here is free.

### 5.8 Self-hosting — and why not yet

Self-hosting is the only real answer to S1: a memory-safety language whose
compiler is written in a memory-unsafe one. It is also frequently a vanity
project, and here is the honest analysis.

**The bootstrap problem.** To write the Beryl compiler in Beryl you need
generics, traits, a real module system, hashmaps, string building, file I/O, and
error handling that scales past a few hundred call sites. That is v0.4 through
v0.6. Self-hosting is *downstream of almost everything*, so putting it early
means either doing it badly or doing everything else first anyway.

**The risk-reduction question.** How much of S1's risk does self-hosting
actually remove, versus cheaper measures?

| measure | cost | risk removed |
|---|---|---|
| Fuzz lexer and parser | ~200 lines + corpus | most of it — the only untrusted input is source |
| ASan/UBSan in CI | ~1 day | most of the rest |
| Arena-only allocation | **already done** | the entire use-after-free class |
| Self-hosting | ~12,000 lines | the remainder |

Fuzzing plus sanitizers buys the large majority of the risk reduction for
roughly 5% of the cost. **Do those in v0.2. Defer self-hosting to v0.8**, and
start it by porting one pass — the lexer — as a forcing function for the
standard library rather than as a rewrite.

**Keep the option open.** The native back end emits C and the compiler is written
in C; the code deliberately avoids constructs with no Beryl equivalent. Keep
doing that, and self-hosting stays cheap whenever it becomes worth doing.

### 5.9 Reproducibility and artifact identity

M0 removes content-changing rebuild retries. A denied launch is a recorded
startup failure and does not change the binary to seek another verdict.
Generated C has deterministic-output checks. Native binary reproducibility still
needs a verified policy for toolchain versions, embedded paths, timestamps, and
flags. Source and artifact hashes identify the actual tested bytes even when
binary reproducibility has not been established. No retry override is planned.

### 5.10 Portability and CI

**Portability.** The compiler core is portable C11 already — the platform code is
confined to `src/driver/{build,main,manifest}.c`, using `_popen`, `_findfirst`
and `cmd /c`. Abstract those behind three functions (`run_capture`, `list_dir`,
`make_dir`) with POSIX implementations and the port is close to mechanical. Worth
doing not because Linux users are queuing up, but because a second platform
finds latent assumptions — and because CI on Linux is far simpler than CI on
Windows.

**CI.** GitHub Actions on push: build, `check-all.sh`, `bench.sh` with the
numbers recorded so a regression is visible, and the diagnostics-documented
check. The Workbench proof cannot run in CI and stays a manual gate before
release — which should be written down as a release checklist rather than
remembered.

---

### 5.11 Concurrency — the general edition's precondition

Cut from the Enfusion edition (D10) because Enfusion scripting is
single-threaded. **Required** for the general edition, because a systems
language competing with Rust in 2026 without threads is not a competitor.

This section is design, not schedule. Nothing here is built.

#### The good news: the hard part is already done

Rust needs `Send` and `Sync` because references are first-class. A `&T` can be
stored in a struct, returned, and captured, so the compiler must prove that
sharing is safe across an *arbitrary reference graph*. That proof is what
`Sync` is, and it is why the trait is hard to teach.

**Beryl's second-class references delete most of that problem by
construction.** A borrow cannot be stored, returned, or captured — so it cannot
cross a thread boundary at all, and there is no shared-reference graph to
reason about. What is left:

| Rust concept | Beryl equivalent | why |
|---|---|---|
| `&mut T` aliasing rules | **already enforced** | the exclusivity checker (BE0401) proves no two live `inout` borrows overlap. That is precisely the data-race-freedom property |
| `&T` shared across threads | **does not exist** | `let` parameters are values; there is nothing shared to race on |
| `Sync` | *possibly unnecessary* | there is no first-class shared reference for it to be about |
| `Send` | **needed** | which types may cross a thread boundary at all |
| `Rc<T>` vs `Arc<T>` | **needed** | the same split, for the same reason: non-atomic refcounts |

The claim that `Sync` may be unnecessary is a **hypothesis, not a result.** It
should be attacked before it is relied on.

#### The genuine problem: handles reintroduce aliasing

This is the one that matters, and it is worth writing down now, years early,
because it constrains §5.7.

`Pool<T>` + generational `Handle<T>` is Beryl's answer to graphs — the whole
reason second-class references are affordable. But **a handle is not a
reference; it is an index, and indices alias freely.** Two threads holding
handles into the same pool, both calling `pool.get(h)`, is exactly the aliasing
that banning stored references was supposed to prevent, rebuilt one layer up.

So the pool becomes the shared mutable object, and it needs what `RefCell` and
`Mutex` give Rust: a runtime discipline, because the static one does not reach
through an index. Options, in rough order of preference:

1. **The pool is `sink`-passed into a scope, not shared.** Structured
   concurrency over disjoint sub-pools. Cleanest; not always expressible.
2. **A `SyncPool<T>` distinct type** with internal locking, so the cost is
   visible in the type and the single-threaded `Pool<T>` stays free.
3. **Per-handle borrow tracking at runtime**, which is `RefCell` with extra
   steps and a panic surface.

Do not pick now. Do note that **§5.7 should not ship a `Pool<T>` whose API
forecloses (2)** — leaving room for a locking variant costs nothing today and
is expensive to retrofit.

#### What concurrency would actually be

- **Structured only.** A scope owns its tasks and joins them; no detached
  threads, no droppable join handle. This fits second-class references exactly:
  a borrow may be passed *into* a scoped task because the scope's extent is the
  call's extent — the existing rule, unchanged.
- **`Send` as an auto-derived property**, not a hand-written trait impl.
  With value semantics and no stored references, nearly everything qualifies;
  the exceptions are OS handles and `Rc<T>`.
- **Channels and atomics** in the standard library, not the language.
- **No `async`/`await`.** Function colouring infects an entire language, it is
  the part of Rust people complain about most, and the games-and-simulation
  wedge (§2.2) wants job systems and frame-structured parallelism rather than
  futures. Declining async is a *feature* of the pitch, not a gap in it.

#### Cost

Perhaps 2,500–4,000 lines across `Send` inference, the scope primitive,
atomics, channels, and the pool question — but the schedule risk is not the
line count. It is that this is the first feature that could genuinely
compromise the small ownership checker (D1), and it must be designed against
that constraint rather than bolted beside it.

---

## 6. Capabilities worth adding that are on no list yet

The roadmap so far fixes what is broken and finishes what was started. This
section is what Beryl could be that it has not tried to be — filtered by the
thesis in §2, so everything here serves game and simulation code specifically.

### 6.1 Determinism, and why it matters here

A networked game where two machines simulate the same thing must get the same
answer. Floating point makes that hard, and nothing in Beryl currently helps.

**Fixed-point types.** `q16.16` and friends as first-class types with checked
arithmetic. Deterministic across machines, compilers and optimization levels by
construction. For a mesh/drone mod doing position integration, this is the
difference between "clients agree" and "clients drift".

**`@deterministic`.** A function attribute that forbids anything varying across
machines: `f32`/`f64` arithmetic, `sqrt`, any `extern` not itself marked
deterministic. Turns "is this replay-safe?" from a code review question into a
compile error. Pairs naturally with the existing taint engine — it is the same
machinery with a different policy, which is exactly the pattern that made the
security work affordable.

**This is genuinely differentiating.** Rust does not have it. EnforceScript does
not have it. It is directly useful to the mod that motivated the project.

### 6.2 Compile-time serialization

`@serialize` on a struct derives a wire format for both targets: a packed
byte-oriented one natively, and the engine's own serializer on Enfusion.

For a mesh networking mod this is enormous — hand-written pack/unpack is where
protocol bugs live, and the two sides drifting apart is the classic failure. It
also composes with §6.1: a `@serialize @deterministic` struct is a network
message you can reason about.

Requires compile-time reflection over fields, which the AST already carries.
Roughly 600 lines.

### 6.3 Units as newtypes

```beryl
type Meters  = f32
type Seconds = f32
```

with **no implicit conversion between them** — which Beryl's strictness makes
natural rather than bolted on. Adding `Meters` to `Seconds` is a type error;
dividing gives... well, dimensional analysis is a rabbit hole, but even simple
newtype separation catches the classic flight-code bug of mixing degrees with
radians or metres with centimetres.

Cheap (~250 lines) and unusually well-matched to the language's existing
personality.

### 6.4 Testing beyond `assert`

The current test story is `assert(cond)`. For numeric game code that is weak.

- **`expect(value, "12.5")`** — snapshot assertions that self-update with
  `beryl test --update`. Ideal for controller output, where the right answer is
  "whatever it was before I refactored".
- **Property tests** — `test "clamped" for x in i32 { assert(clamp(x,0,9) <= 9) }`.
  For a PID controller or a mixer, generated inputs find things hand-written
  cases do not. The interpreter (§5.2) makes this cheap to run.
- **`bench "name" { }`** with `beryl bench`, recording results so a regression
  is visible. For a project whose README makes performance claims, benchmarks
  should be a language construct, not a shell script.

### 6.5 Smaller things worth doing

- **`beryl explain BE0401`** — embed the docs. ~150 lines, disproportionate
  value.
- **`beryl doc`** — the `//!` comments are already parsed and stored on every
  item and field. Emitting a browsable API reference is nearly free.
- **`@deprecated("use X instead")`** — needed the moment anything else depends
  on your code.
- **Const generics** — `fn dot<N>(a: [f32; N], b: [f32; N])`. Real math code
  wants it; the const evaluator already exists to support it.
- **`beryl fmt` on save** — trivial with an LSP, and it removes an entire class
  of argument.

---

## 7. Explicit non-goals

Writing these down prevents re-litigating them.

- **Concurrency and async *in the Enfusion edition*.** Enfusion scripting is
  single-threaded, so it buys nothing there. It is a **precondition for the
  general edition** and is designed for in §5.11 — this is a scheduling
  decision, not a rejection.
- **A package registry before the general edition needs one.** Path and git
  dependencies are enough for one person and one mod. A registry is a permanent
  operational commitment, and it is (b)'s problem, not (a)'s.
- **Being better than Rust *at everything*.** The goal is to be better on a
  named axis — games and simulations — and honest about the rest. crates.io,
  `Send`/`Sync` maturity, miri and ten years of soundness work are not gaps a
  design decision closes. See §2.2.
- **`dyn` / dynamic dispatch**, until something concretely needs it.
- **A garbage collector**, ever.
- **Build scripts and procedural macros**, ever. This is the supply-chain
  guarantee, and it is worth more than the convenience.
- **Backwards compatibility before v1.0.** Break things while breaking is cheap.

---

## 8. Risks, and what would make me stop

**The wedge does not materialize.** If porting a real SPARKOS MESH class (§4.1)
is not clearly better than writing EnforceScript directly, the project has no
reason to exist. *Mitigation: run that experiment first, in v0.2, before
building anything else.*

**A codegen bug erodes trust.** One silently wrong output in shipped mod code and
you stop believing the compiler — and a language you do not trust is worse than
no language. *Mitigation: §5.1, treated as v0.2's main technical work.*

**Maintenance load exceeds value.** A language is a permanent commitment. Every
Reforger update is a potential EnforceScript change; every clang release is a
potential C-backend change. *Mitigation: keep the compiler small — 297 KB and
~12,000 lines is an asset, not an accident — and resist features that serve the
ambition rather than the wedge.*

**Scope creep into (b).** Every item in §6 is more fun than fixing the module
system. *Mitigation: §4's ordering, and the honest test of "does a SPARKOS MESH
class benefit from this".*

**Bus factor of one.** Nobody else has read this code. *Mitigation: the docs
exist and are honest; keep them that way. `INTERNALS.md` is the on-ramp and
should be updated whenever it goes stale.*

---

## 9. Decision log

Decisions already made, with the reasoning, so they are not re-opened without
new information.

| # | Decision | Why | Revisit if |
|---|---|---|---|
| D1 | Mutable value semantics, second-class references, no lifetimes | Same memory safety with no annotation burden and a far smaller checker | Someone hits a real problem that genuinely needs stored references |
| D2 | Current backends emit from typed AST; M5 introduces structured IR | Approved plan needs explicit places, effects, ownership and provenance while retaining control structure | Superseded by the approved M5 packet |
| D3 | Monomorphization, not dictionary passing | Mandatory for a target with no generics | Never — the Enfusion target settles it |
| D4 | Checked native arithmetic by default | Explicit and consistent policy; Rust can configure the same overflow policy | Target semantics and explicit alternatives require independent validation |
| D5 | No implicit numeric conversion, ever | Catches more real bugs than it costs | Never |
| D6 | No build scripts, no proc macros | The supply-chain guarantee | Never |
| D7 | Compiler in C, self-hosting deferred | Fuzzing and sanitizers buy most of S1's risk reduction for 5% of the cost | v0.8, once the language can host a compiler |
| D8 | Engine-facing names preserved through explicit export mappings | M1 requires collision-free internal names; M3 preserves the SPK_PID interface | Superseded by the approved M1/M3 packets |
| D9 | `!T` loses its tag on Enfusion | Matches the base game idiom; the alternative pollutes every signature | If a real case needs to distinguish errors and an enum return is not enough |
| D10 | Concurrency cut **from the Enfusion edition** | Enfusion scripting is single-threaded, so it buys nothing there | Superseded by D12 — it is a precondition for the general edition, scheduled in §5.11 |
| D11 | Deterministic generated C; native binaries identified by exact hash | M0 removes launch retries; binary reproducibility needs further toolchain controls | Expand the guarantee after reproducibility tests |
| D12 | General-purpose Beryl is a **stated goal**, sequenced after the Enfusion edition reaches v1.0 | User decision, 2026-09-04. The wedge funds the shared work; it does not replace the ambition | Never — this is the direction. Only the ordering is open |
| D13 | Two editions, **one compiler** — not a fork | Measured: Enfusion is 1,331 lines of back end plus ~17 lines of wiring, and zero lines in `sema/`, `lex/` or `parse/`. A fork would double every bug fix to buy branding that packaging already provides | If a **core semantic** must diverge (e.g. the general edition wanting first-class references, breaking D1). That is a different language, not a variant |
| D14 | Enfusion usefulness first, shared semantic foundations for both targets | Approved user priority; keep engine-specific rules in bindings and packages | Supersedes historical native-first ordering |
| D15 | The general edition's wedge is **games and simulations**, not general systems programming | It is where Rust is weakest (graphs, compile times, determinism) and where the ecosystem gap is smallest — and it is the same domain as the Enfusion edition, so the two share a wedge and not just a compiler | If a different domain shows a stronger structural advantage |

---

## 10. Effort summary

| release | theme | ~lines | the point of it |
|---|---|---|---|
| v0.2 | Trust the output, prove the thesis | 2,000 | decides whether this is a project |
| v0.3 | Whole mods | 1,400 | makes the wedge real |
| v0.4 | Expressiveness | 3,500 | makes it pleasant |
| v0.5 | Memory | 1,500 | finishes what was designed |
| v0.6 | Platform | 2,800 | makes it usable by someone else |
| v0.7 | Determinism | 1,800 | the genuinely differentiating part |
| v0.8 | Self-hosting groundwork | — | closes S1 |
| v1.0 | Stability | — | only after a year of real use |

Roughly 13,000 lines to v0.7, against ~11,800 today. That is a real project, not
a weekend — which is the honest framing, and the reason §4.1 exists.

The general edition's track (§4.2) sits after all of that:

| release | theme | ~lines | the point of it |
|---|---|---|---|
| G1 | Reach | 3,000 | three platforms and real FFI |
| G2 | Concurrency | 3,500 | the precondition for competing at all |
| G3 | Standard library | 10,000+ | mostly Beryl, not C — and where language projects die |
| G4 | Tooling | 8,000+ | LSP, package manager, debugger |
| G5 | Hardening | — | ongoing, forever |

Those numbers are guesses with wide error bars, and G3 and G4 dwarf the entire
first track. **That is the real cost of the second edition** — not the compiler
work, which §2.1 shows is nearly done, but the library and tooling surface that
"general purpose" actually means.

---

## 11. If you read only one thing

Do the experiment in **§4.1**. Port a real SPARKOS MESH class, ship it, and see
whether it was worth it.

Everything else in this document — including the general edition, which is a
stated goal and not a daydream — is a plan for a thing that might not need to
exist. That experiment is the only part that tells you whether it does, and it
costs an afternoon.
