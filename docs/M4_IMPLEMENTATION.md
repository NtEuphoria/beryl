# M4 implementation packet: dependable engine evidence and AI context

Status: next milestone; not implemented as a completed milestone. M3's isolated
MESH gameplay/handover gate passed on 2026-09-07. This packet records the next
work and observations made while inspecting the installed Workbench integration.

## Starting evidence

The M3 compiler already provides strict JSON companion checking, isolated addon
generation, explicit class/constructor/method exports, versioned local tool
installation, headless compilation and owned-output promotion. The PID verifier
uses the existing NetAPI transport and starts/stops only an owned hidden session.
It checks the loaded project name, exact compiled artifact token and complete
operation/field counts. The MESH candidate verifier similarly checks project
identity and all nine selected existing suite responses. These mechanisms should
be generalized, not duplicated with a second editor bridge.

`GetLoadedProjects` on this installed Workbench returns a response containing
`"Loaded Projects"`, an array of addon IDs. The verified comparison response was
`["ArmaReforger", "BerylPidComparison"]`. An addon name alone is insufficient to
identify source content: retain the compiled token and artifact hashes as well.

## Required work

1. Add compiler-generated feature discovery and symbol context from resolved
   declarations, including target limitations and explicit parameter modes.
   Return unavailable for unsupported features; do not extract support claims
   from historical research pseudocode.
2. Add generated-source mappings for statements, expression preparation,
   default expansion, value helpers, class constructors and export wrappers.
   Preserve origin spans through helper reordering. Map companion export JSON
   pointers back to the description as related locations.
3. Map engine diagnostics to those origins while retaining the complete raw
   engine message, generated location and exact generated artifact fingerprint.
4. Generalize verified runtime scenarios without allowing project shell/code
   strings. Preserve session ownership, engine identity, complete selection
   checking, timeouts, cancellation and source-staleness rejection.
5. Generalize the existing MESH test wrapper's empty/unknown-selection and partial
   response protection. The candidate wrapper already refuses any preexisting
   game, including an old test instance it did not start.
6. Expose exact binding declarations separately from reviewed semantic annotations:
   nullability, units, retention, authority and verified target version. An
   extracted declaration alone is not a reviewed ownership or authority contract.
7. Extend the common package workflow into concise shared Claude/ChatGPT guidance.
   Add an MCP adapter only after these CLI contracts pass their tests.

## Binding observations requiring focused follow-up

Historical M4 observations below were subsequently reproduced and repaired in
Stage A. The current integer lowering uses integer bindings and bounded
saturating formulations; see [advanced implementation state](BERYL_ADVANCED_IMPLEMENTATION_STATE.md)
for the exact engine receipts. These paragraphs record the original finding,
not an assertion that the defect remains in current source.

The installed plugin's `reference/api-index/index.json` records an index built
2026-08-13, with 8,947 classes and 238,118 members. It does not itself record a
verified engine version, so the current executable version must not be assigned
to every extracted declaration automatically.

The local `classes/Math.md` lists distinct `Min`/`Max`/`Clamp` float functions and
`MinInt`/`MaxInt`/`ClampInt` integer functions. Current
`src/back/enforce_expr.c::gen_intrinsic` emits the float names for generic Beryl
min/max/clamp regardless of i32 result type. Source inspection therefore exposes
a likely integer precision defect above binary32's consecutive integer range.
Reproduce with exact large-integer engine fixtures before declaring a validated
runtime finding, then select the exact integer bindings and retain the regression.

The same function emits saturating integer addition/subtraction as a plain
integer operation followed by `Math.Clamp`. That structure does not prevent the
operation from overflowing before clamping. Reproduce the boundary cases in the
engine and implement a checked branch formulation whose intermediate arithmetic
stays in range. Neither observation affects the tested full PID, whose min/max/
clamp operations are f32. They also do not establish that the whole Enfusion
integer arithmetic profile already matches native checked arithmetic.

## Exit evidence

Use exact declared source spans and fault-injection fixtures for source-map tests.
Exercise wrong project, stale token, incomplete result list, unknown scenario,
cancelled/timeout process and external output modification. Run the AI task set
from the approved plan without editing generated code. Keep runtime compilation,
pure-function execution, host gameplay, independent clients and visual review as
separate evidence levels. No M4 completion or new performance claim is made here.
