# Beryl — six-month roadmap

**Written 2026-10-18, against the `v0.2-performance` working tree.**

This is the calendar layer over the three plans that already exist in this directory:

- [ROADMAP.md](ROADMAP.md) — the feature-ordered release plan
  (v0.2 → v1.0, then the general edition's G1–G5).
- [BERYL_DELIVERY_PLAN.md](BERYL_DELIVERY_PLAN.md) — the approved
  delivery program (P0–P9 packets, R0–R5 checkpoints).
- [V0_2_PERFORMANCE_PLAN.md](V0_2_PERFORMANCE_PLAN.md) — the native
  performance phases 0–6 currently on this branch.

None of those say *when*. This document does. Every month has a theme, the
packets/releases it covers, and an exit criterion that is a fact rather than
a feeling. Where work depends on a decision only you can make — chiefly,
un-parking Reforger testing — the dependency is named instead of smoothed
over.

## Where you are, honestly

| Done (with receipts) | Open |
|---|---|
| P0 baseline, capability registry, doctor, hardened MCP | Full `doctor` profile coverage beyond current bundles |
| P1 safety: destination protection, call-capture/receiver repairs, storage admission, parser limits | Shallow-ownership rejections widening into real owning copies (P3) |
| M0–M4: isolated jobs, module identity, bounded reference interpreter, PID port, tablet service candidate | M4+ live-project deployment |
| Tablet: N0/N1a isolated cases, all 92 protocol cases in-VM, **ordinary open/close verified in the owned Enfusion candidate** | Physical stow, focused destruction, input, visual, multiplayer, promotion |
| Experimental schema-5 IR: init/access modes, `set`/`sink`, first 26-assertion O0 parity | Full AST↔IR O0/O2 matrix — **blocked by Windows Code Integrity 4551** |
| v0.2-perf: phases 1–3 landed (`restrict` emitted, pointer `let`s), 510 cases / 10,317 checks | Every paired-timing gate, UBSan, O0/O2/O3 differential, phases 4–6 |
| `beryl mod init --template scalar-component` (bounded) | Engine execution, prefab/layout authoring, deployment |

The single highest-leverage fact: **the native IR matrix is blocked by
Windows Code Integrity error 4551** — generated executables won't launch.
Everything downstream of P2 depends on resolving that. It is task zero.

The single highest-leverage *strategic* fact: the §4.1 experiment is no
longer hypothetical. The PID is ported and compared (65,850 checks), and a
generated tablet now opens and closes in the real engine. The question "is
the wedge real" has a positive early answer — what remains is proving the
test loop is actually faster than writing EnforceScript, *with timings*.

## Phase 0 — Weeks 0–2 (Oct 19 – Nov 1): unblock and tidy

Small, concrete, unblocks everything.

1. **Defeat Code Integrity 4551.** Order of attack: Dev Drive / ReFS for
   `build/`; `clang -o` output signing policy check; AppLocker/WDAC policy
   audit via the captured event 3077; fall back to running the native matrix
   on Linux CI (see below). Do not weaken the OS policy — work around it.
2. **Delete the ~70 garbage files at repo root** (`!i32`, `0)`,
   `items.data[i])`, …) — pasted shell output accidentally committed. One
   `git rm` sweep; it will keep polluting `git status` and any glob-based
   tooling until it is gone.
3. **Tag v0.1.** Still pending from the Sept 12 plan. Take the snapshot
   before more merges — it is the rollback anchor for everything below.
4. **CI, minimal**: build + `test.sh` + `check-diagnostics.sh` on push.
   Linux runner is the cheap option and doubles as the portability probe
   (§5.10). Workbench stays a manual gate — write the release checklist
   instead of automating it.

**Exit:** the full foundation unit suite executes end-to-end on this
machine or CI without a policy block, `git tag v0.1` exists, root is clean.

## Month 1 — November: finish v0.2, in both senses

Two tracks converge here: *trust the output* and *native performance*.

**Trust (P2 core):**

- Close the schema-5 IR matrix: AST reference vs IR-to-C at O0 **and** O2,
  then IR-to-EnforceScript against the engine PID fixtures.
- Mutant hunting as the exit, not vibes: the deliberate arithmetic /
  ordering / state mutants the delivery plan names must actually be caught.
- Land the deferred small correctness items: `catch` zero-value (C5),
  remaining `defer` edges (C4 is closed as a *spec* item by Phase 6's
  scope-exit work — verify, don't assume).

**Performance (v0.2-perf phases 4–6, in plan order):**

- Phase 4: shared `src/sema/range.c` interval pass → bounds-check
  elimination (`array_sum_2d` must show no `be_idx` in `-S` output).
- Phase 3 re-verify: `inout_axpy` must vectorize; O0/O2/O3 outputs
  byte-identical; `BE0401` false-positive rate unchanged on `tests/` and
  `packages/`.
- Phase 5: `[profile.native]` in `beryl.toml`; refuse `fp_contract=fast`
  with an `[target.enfusion]` package (new BE08xx).
- Phase 6: `reserve`/`with_capacity`, scope-exit release, `Pool<T>` +
  `Handle<T>` generation-checked — the language's answer to "how do I build
  a graph" finally exists.

**Parallel cheap wins:** `beryl explain BE####` (~150 lines, embeds the
docs), `beryl doc` (the `//!` comments are already parsed).

**Exit criterion:** `v0.2` tag cut. Six workloads have receipts that
`evaluate.py` accepts; each phase improved-or-neutral at the §4.3
threshold; the full unit suite passes at O0/O2 **and under UBSan/LSan**;
a wrong-output candidate is rejected by the harness.

## Month 2 — December: owning storage (P3) → checkpoint R1

The ownership model's missing half, delivered through IR rather than a
second runtime — the delivery plan's own rule.

- Aggregate lifecycle; recursive admitted `List`; required immutable
  dynamic strings; tagged optional/error payloads; the map facilities the
  admitted MESH workloads actually use.
- Eager recursive copies on assignment; `sink` transfers; replacement
  prepared before destruction; cleanup on fallthrough/return/break/
  continue/`try` — verified under LSan.
- Effect summaries: reads/writes/shape/escape/failure per function, call
  graph fixed point including recursion, receivers, defaults.
- Invalidating mutation during active borrows rejected — including through
  callees.

**Exit criterion (R1):** released bounded IR per target *and* separately
admitted owning-storage categories, each with its own gate evidence.
Nested/self/overlapping copies, early exits, and injected failures preserve
values with bounded physical storage.

## Month 3 — January: typed engine contracts + companion v2 (P4)

This is the month the `@component`/`@attribute`/`@rpc` story becomes real —
and it's pure compiler/authoring work, no engine launches needed, which is
why it sits inside the parked-Reforger window.

- Extract exact tablet component/gadget inheritance, callback signatures,
  UI/screen APIs, resource APIs → reviewed, versioned contracts.
- Companion v2: generated component descriptors + instances, explicit
  callback mappings, typed editor properties, prefab composition, bounded
  UI fragments, typed scenario selections, project resource lockfile
  (captured MESH GUIDs, collision-rejecting).
- Language surface: `extern` declarations (BE0903 on native),
  `@component` emitting the paired `...ComponentClass`,
  `@attribute`, and **`@rpc(server)`/`@rpc(broadcast)` implying
  `@untrusted` on every parameter** — the best single idea in the roadmap;
  it makes the most common real Reforger vulnerability a compile error you
  cannot forget to enable.

**Exit criterion:** bad inheritance, bad properties, bad resource refs,
duplicate definitions, and dead UI bindings all fail *before* promotion —
demonstrated on deliberately broken candidates, not assumed.

## Month 4 — February: complete tablet feature (P5) → checkpoint R2

Beryl owns the lifecycle; generated output owns component descriptions,
properties, the map-mode fragment, and the tablet prefab. Preserves all 13
named invariants (Focus-only-from-HELD, superclass ordering, no repopulation
on duplicate activation, unfocus-before-stow, screen only in HELD, …).

**The parked gate.** Engine acceptance — physical stow, focused
destruction, input initialization, visual acceptance, dedicated multiplayer —
requires un-parking Reforger testing. If that's still off the table, the
compiler-side P5 work proceeds anyway and the month ends with the generated
candidate *ready* for acceptance instead of accepted. Say so, don't fudge
the checkpoint.

**Fallback if still parked:** pull Month 5's P6 tooling forward, and start
`match` + payload enums from v0.4 (they unblock cleaner component code).

**Exit criterion (R2):** the complete generated tablet candidate passes the
remaining lifecycle cases in owned Enfusion sessions; logic, property,
event and prefab changes regenerate/diagnose/verify with **zero manual
generated-file edits**.

## Month 5 — March: deployment + AI authoring (P6, P7) → checkpoint R3

- **P6:** `doctor --probe native|enfusion-compile`; request-scoped `analyze`
  API; MCP/CLI parity proven on identical tasks; mod-workflow plans that
  name unavailable steps as unavailable.
- **AI-authoring acceptance:** real Claude/ChatGPT trials on the six named
  tasks (PID change, property, event, prefab, engine-error repair, correct
  scenario), recording repair rounds and unsupported-API attempts — the
  "easier to author" leg of the performance thesis, measured.
- **P7:** dedicated-server/two-client matrix (remote toggles never open
  local UI; death/respawn/disconnect/JIP; teardown without retained
  UI/input), visual matrix (ultrawide + 1080p, clipped/disabled/degraded
  states, actual rendered colors), then promote only exact verified
  artifacts with tested rollback.

**Decision gate — §4.1, honestly answered.** With a generated class now
living the full lifecycle, write down: was the loop faster? did anything
break that the checker should have caught? would you port the next class?
A "no" here legitimately reshapes the roadmap — it's a designed off-ramp,
not a failure.

**Exit criterion (R3):** the selected dedicated-client + visual matrix
passes with rollback proven; AI-authoring trial data exists with repair
counts attached.

## Month 6 — April: whole mods + measured performance (P8, P9) → R4/R5

- **P8:** resources/dependencies → reusable components/properties → prefab
  templates → complete layout/events → scenario/deployment → typed
  import/packing, in that order. Ship the small numeric/time/interpolation
  helper library with independent expected tests. Optional Python LSP on
  the same C analyzer — snapshots first, VS Code launcher minimal.
- **P9:** adopt / reject / mark-unavailable each optimization experiment
  per its gate; allocation-changing work defaults to
  `resource_adequate_exact`; only released rules auto-enable.
- **v1.0 candidacy review:** what's actually left between the working tree
  and a stability promise? Backwards compatibility stays cheap to break
  until then — v1.0 is a promise, not a milestone you slide into.

**Exit criterion:** a sample mod — not the tablet — goes end-to-end through
packing with usable diagnostics and no generated repairs; the adopted/
rejected/unavailable ledger is complete for every experiment that started.

## The translation table

| Month | Delivery packets | Checkpoint | ROADMAP.md release |
|---|---|---|---|
| 0 (2 wks) | unblock, hygiene, tag, CI | — | v0.2 prerequisite |
| Nov | P2 finish + perf 4–6 | R1 partial | **v0.2** |
| Dec | P3 owned storage | **R1** | v0.5 core pulled forward |
| Jan | P4 contracts + companion v2 | R2 partial | v0.3 |
| Feb | P5 complete tablet | **R2** | v0.3 exit |
| Mar | P6 + P7 deploy/pilot | **R3** | v0.3 hardening |
| Apr | P8 + P9 start | R4/R5 start | v0.4/v0.6 begins |

Deferred past this window, deliberately: generics/traits/`match` bulk of
v0.4 (pull forward only where they unblock authoring), fixed-point +
`@deterministic` + `@serialize` (v0.7), self-hosting (v0.8), and the entire
general-edition track G1–G5 — all gated on v1.0 per D12, which this plan
does not reopen.

## Risks that move the schedule

| Risk | Mitigation |
|---|---|
| Code Integrity / Smart App Control keeps blocking generated binaries | Phase 0 exists only to resolve this; Linux CI removes the dependency entirely |
| Reforger testing stays parked past February | R2 narrows to "candidate ready"; P6/v0.4 features fill the month; the checkpoint is renamed, not fudged |
| Owned-storage P3 is bigger than it looks — it's ~half the ownership model | It follows P2's IR, not a second runtime; if it slips, P4 contracts work (no engine needed) fills in, not feature work |
| Reforger update changes emitted-code requirements | Bindings isolate engine surface; contracts are versioned evidence, not assumptions |
| Scope creep toward the general edition | §4.2 ordering and the "does a MESH class benefit" test stay in force |
| Bus factor of one | `INTERNALS.md` stays honest; receipts + hash identity mean a fresh reader can verify, not just trust |

## Explicit non-goals for these six months

Concurrency and async in the Enfusion edition (single-threaded target — a
general-edition precondition, designed in §5.11). A package registry.
`dyn`. A GC. Build scripts and proc macros — that one is the supply-chain
guarantee, not a gap. Backwards compatibility — break things while it's
cheap.
