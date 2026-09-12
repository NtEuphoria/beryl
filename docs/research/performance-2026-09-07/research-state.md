# Performance research state

Date: 2026-09-07. Scope: research and hypotheses only; no compiler or mod changes.
Audience: owner, Claude, ChatGPT, future compiler implementers.
Decision: which exact semantic and domain-specific optimizations merit bounded experiments next.
Assumptions: Enfusion usefulness first; native Rust comparisons are a separate target;
M3 candidate evidence remains the implementation baseline; M4–M8 are not complete.
Primary sources: project source and evidence, official engine/compiler documentation,
original papers and maintained original research projects. Secondary sources may locate
primary work but do not establish technical claims.

The requested plan tool is not exposed in this session (tool inventory checked).
This file records its intended scope, phases, evidence gaps and completion state.

## Plan

1. Complete — reconcile existing proposals and current implementation; first-pass
   discovery in Enfusion workloads, native compilation and incremental semantics.
2. Complete — merged three research packets and independently checked consequential
   map, array, Canvas, LLVM, cache-transfer and certificate claims. Iterator guarantees,
   reliable alias invalidation and actual runtime costs remain experiment gates.
3. Complete — synthesized fourteen hypotheses, counterexamples, experiment packets and
   a realistic dependency graph, with exact vs approximate behavior separated.
4. Complete — canonical report and source ledger written; three independent agent
   reviews reconciled. All 25 local links/line bounds verified; 152 input fingerprints
   unchanged; fourteen hypotheses and twenty-five counterexamples checked. Final report
   published as docs/BERYL_PERFORMANCE_RESEARCH_2026-09-07.md and byte-compared with the
   reviewed canonical source. Detailed checks are in quality-check.json.

## Research ownership

- Root: scope, local baseline, experiment methodology, independent claim verification,
  evidence reconciliation, synthesis and final report.
- Enfusion worker: actual MESH loops and engine constraints/profiling.
- Native worker: representation, allocation, compiler optimization and fair baselines.
- Incremental worker: change propagation, demand and exact semantic work avoidance.

## Initial gap matrix

| Question | Current support | Missing / next action |
|---|---|---|
| Where does current MESH spend time? | No new profile; official map API marks indexed access O(n), current source loops use it | Probe installed iterator order/complexity; measure scaling before claiming quadratic runtime |
| What does Beryl emit today? | Typed AST, C/Clang and EnforceScript, bounded reference | Inspect optimization barriers and distinguish implemented from proposed |
| Can exact incremental work avoid repeated scans? | Primary research supports change propagation; mutable aliases and reverse expiry order expose local contracts | Result-stability certificates, coherent epochs, bounded cache retention and exact f32 deadlines |
| Can native Beryl exceed tuned Rust? | No relevant measured claim | Match layout, allocation and safety; identify domain information beyond ordinary backend flags |
| How are experimental transforms trusted? | Alive2 is bounded LLVM translation validation, not a Beryl/Enfusion proof; original blueprint preserves ordered effects | Use independently checked local contracts; no unbounded proof claims from finite tests |
| How do AI tools benefit? | Shared CLI and strict companion profile | Reproducible experiment packets, explicit context and invalidation contracts |

## Boundary

No new performance measurements are being represented as evidence. Numerical examples,
if included, must be explicitly analytic. No hypothetical native speedup is transferable
to the Enfusion runtime without a separate script-engine experiment.
