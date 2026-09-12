# Beryl: dependable language, complete Enfusion authoring, measured performance

Approved for implementation by the user on 2026-09-07. This document consolidates
the approved delivery program. [Execution state](BERYL_DELIVERY_STATE.md) records
implementation progress and evidence. It extends the
[SPARKOS plan](SPARKOS_IMPLEMENTATION_PLAN.md) and
[advanced performance plan](BERYL_ADVANCED_IMPLEMENTATION_PLAN.md), starting from
the [installed checkpoint](BERYL_ADVANCED_IMPLEMENTATION_STATE.md).

## 1. Objective and delivery strategy

Develop the working compiler and complete PID port into a dependable authoring
system for complete Enfusion mods, shared by Claude, ChatGPT and human authors.
The selected first complete feature is the existing MESH tablet lifecycle.
Prioritize CLI, diagnostics, environment checks and local MCP before LSP/editor
integration.

The starting checkpoint has AST native/EnforceScript generation, qualified module
identity, bounded independent reference execution, complete PID comparison,
experimental record/PID IR evaluation, bounded mappings, immutable artifacts,
owned engine jobs and actual exploratory terrain timing. Public IR, complete
ownership, whole-mod descriptions, dedicated multiplayer and automatic
optimization remain unfinished. The 34.06% terrain construction/release result
does not establish complete-workload adoption.

Keep C11/Clang, current modes, value/numeric semantics and immediate `defer`.
Ordinary compilation remains independent of Python and model APIs. Optional local
tools reuse the current Python/Workbench integration. Preserve MESH object
identity, public interfaces, resources, wire formats, dirty changes, original
fixtures and rollback artifacts. Release optimizations only through their gates.

| Checkpoint | Deliverable |
|---|---|
| R0 | Known unsafe paths contained, checked allocation arithmetic, truthful capabilities |
| R1 | Released bounded IR and separately admitted owning-storage categories |
| R2 | Complete generated tablet candidate, properties, prefab, UI fragment and scenarios |
| R3 | Dedicated-client, visual, lifecycle and AI-authoring acceptance |
| R4 | Whole-mod resources/components/layouts/scenarios/import/packing, library and editor |
| R5 | Individually adopted workload improvements; experiments adopted/rejected/unavailable |

Critical path: safety, verified execution, complete feature, deployment.
Capability reporting, doctor and regression infrastructure support it from the
beginning. Independent fixtures may proceed in parallel.

## 2. Implementation packets

### P0 — Baseline and capability inventory

Capture source/runtime/compiler/tool identities, exact MESH inputs and seams,
engine/API/plugin identity, arguments/toolchain dependencies and applicable
receipts. Identify tested inputs by content hashes. Create a compiler-owned
registry of targets, implementation state, admission rules, dependencies,
diagnostics, examples and evidence requirements.

Separate implementation, current-program admission, local availability and
verification of the current configuration. Receipts live beside artifacts; no
self-referential current-compiler verification claim is embedded in the binary.
Generate current feature/example tables. Correct stale modules, integer binding,
reference, IR, ownership, package and security claims while labeling historical
reports. Replace the specification's blanket compiler-is-right rule with explicit
contracts, conformance tests and documented deviations.

Gate: context, installed tools, current docs and examples agree; missing/stale
evidence is visible.

### P1 — Existing compiler safety

Move destination protection into shared semantic analysis. Evaluate operands,
arguments and destination projections in source order; each index once; capture
compound old values before RHS. Reject effects that replace/invalidate a selected
destination; retain provably disjoint fields/indices and explain separate-statement
repairs. Do not choose one historical disagreeing result as normative.

Check addition, multiplication, alignment and growth in compiler arenas/vectors
and runtime storage. List capacities satisfy signed-i32 interfaces and byte-size
limits; calculate/allocate before descriptor commit. Distinguish arithmetic,
allocation and harness failure. Add parser/traversal limits.

Classify plain values, owned-storage values and engine references recursively.
Reject unsupported owning copies/moves/returns/call crossings that rely on shallow
descriptors. Publish narrowed admission and migration diagnostics; retain affected
examples as explicit cases. Implement full ownership through IR rather than two
independent ownership runtimes.

Preserve untrusted provenance through min/max/clamp and track ranges separately.
Replace bare validator laundering with checked contracts. Bounds facts apply to
specific storage/shape. Implement fields, conservative element summaries,
symbolic return/mutation dependencies and call-graph fixed points including
recursion, receivers, defaults and mutable modes. Invalidate range facts on
relevant mutation. Runtime authority requires verified engine boundaries;
server-only/constant-time annotations initially express checked source restrictions.

Gate: regressions detect invalidation, shallow ownership, overflow, laundering,
helper sinks and invalid authority assumptions. The existing PID stays supported.

### P2 — Unoptimized IR and independent verification

Extend existing IR with fixed arrays, checked dynamic projections, storage roots,
captures, initialization/move states, plain set/sink and separately tested needed
enum/optional operations. Preserve origins. Whole-root moves and whole-aggregate
initialization first; partial operations have separate gates.

Set parameters are logically uninitialized on entry, while an existing caller
value remains physically intact until successful replacement. Evaluate replacement
before discard; preserve writes completed before later failure; require assignment
on every admitted return. Calls are not transactions.

Implement IR-to-C through current evidence/process tools. Compare analytical
fixtures, AST reference, IR evaluator, AST-to-C O0/O2 where supported and IR-to-C
O0/O2. New owning categories without safe AST emission use independent logical-heap
reference and fixtures, with AST emission explicitly unsupported. Preserve checked
failure order, grouping, short circuit and immediate defer; parity builds disable
contraction and fast-math.

Then implement IR EnforceScript and repeat complete engine PID comparison. Release
explicit IR separately per target. Auto selects IR only for an admitted released
whole source set; unsupported explicit IR returns unavailable. Never silently mix
ownership/calling conventions.

Gate: values, state, first failure and successful prefix agree; deliberate arithmetic,
ordering, branch and state mutants are caught.

### P3 — Owned storage and effects

Order: aggregate lifecycle; recursive admitted List; required immutable dynamic
strings; tagged optional/error payloads/exits; map facilities required by admitted
MESH workloads. Each category has independent admission/release. Only actual tablet
dependencies block the tablet.

Assignment produces independent logical values through eager recursive copies.
Read-only parameters borrow; sink transfers; replacement prepares source before
destroying destination. Cleanup covers fallthrough, return, break, continue and
admitted error propagation. Clear destroys elements; scope exit releases storage.
No new user destructor or trap-unwinding semantics. Value iteration evaluates once
and preserves an independent logical snapshot; later borrowing needs equivalence.

Track bindings, logical values, backing storage and accesses separately. Reject
invalidating mutation during active borrows including callees. Infer conservative
reads/writes/allocation/shape/escape/failure/engine effects; unknown calls retain
relevant worst-case effects. The reference logical heap does not call native
copy/growth/destruction helpers. Verify dynamic string encoding/length units on
engine targets. Engine reference copies retain identity under their binding
contract. List support does not imply general native Map/Box/Rc/Pool/Handle.

Gate: nested/self/overlapping copies, moves, growth, early exits, repeated lifecycles
and injected failures preserve values and bounded physical storage.

### P4 — Typed engine contracts and companion v2

Extract exact tablet component/gadget inheritance, initialization/frame/toggle/delete
callbacks, local ownership, UI/screen APIs, widget/handler retention and resource APIs.
Keep extraction separate from reviewed signature/nullability/validity/units/domain/
retention/superclass-order/world-lifetime/authority contracts and versioned evidence.
Native fixtures use stable tokens and scripted service responses.

Preserve strict v1. V2 admits generated component descriptors/instances, explicit
callback mappings, typed editor/inherited properties, existing resources, prefab
composition, bounded UI fragments/events and installed typed scenario selections.
Structurally valid unavailable capabilities still fail admission. No project shell
commands or arbitrary engine code strings. A project resource lockfile preserves
captured MESH GUIDs and rejects collisions.

Map declarations, constructors, superclass calls, properties, callbacks, widgets,
events, helpers and cleanup to Beryl or JSON pointers. Retain raw engine diagnostics;
unknown columns/origins remain unavailable.

Gate: bad inheritance/properties/resources/signatures, duplicates and dead UI
bindings fail before promotion.

### P5 — Complete tablet feature

Beryl owns lifecycle/gadget/toggle decisions. Generated output owns component
descriptions, existing properties, map-mode fragment and tablet prefab. Preserve
UI/map/telemetry/screen services, engine gadget protocol, existing input/keybindings,
inventory/editable components, model/material/resource identities and class names.
Exactly one production definition per migrated class. One-time handwritten adapter
seams are explicit; routine changes require zero manual generated edits.

Preserve Focus-only-from-HELD; failed UI open stays HELD; degraded map opening after
successful widget creation; input/keybinding connection after open; superclass call
before local-owner check; activation held/focus/population order; no repopulation
on duplicate activation; screen only in HELD; unfocus before stow; UI close/screen
destroy before superclass deletion.

While focused: markers first, add binary32 timeSlice, at >=0.25 reset accumulator
to zero and refresh once. Keep accumulator across reopen. No cadence/catch-up change.
Author existing gadget m_eUseMask=15, m_eAnimVariable=MAP and input-enabled default.
Generate Btn_MapMode and Btn_MapMode_Label inside HeaderBar preserving names,
placement/colors/order/discovery, toggle_mapmode/index -1, single dispatch,
disabled/hover behavior, 2D/3D labels and handler lifetime. Initial descriptions
generate verified widget-construction code; native .layout emission is separate.

Add typed state/service parity, widget/events, full candidate lifecycle and dedicated
multiplayer scenarios; reuse exact existing UI/screen/actions/clicks/prefabaudit suites.
Gate: logic, property, event and prefab changes regenerate/diagnose/verify with zero
generated-file edits.

### P6 — Shared AI workflow

Doctor default inventories compiler/tool/project/schema/native/Python/engine/binding/
plugin identities and current/stale evidence. Explicit probes run isolated native or
Enfusion compilation. Native-only readiness does not require optional engine tools;
inventory does not launch/install/change source.

Extract a request-scoped C analysis API. Add bounded analyze requests for exact source
snapshots/overlays. Optional Python adapters create owned request dirs with exact
bytes/hashes/versions; C loads through SourceMap; missing overlay never falls back
to disk; replies carry snapshot/request identity; stale replies are discarded.
Implement/fuzz JSON input reading, which current output helpers do not supply.

Use optional local stdio MCP over the same CLI: context, examples, mappings,
diagnostics, discovery, evidence, explicit build/test/scenario calls. Lookup never
launches execution; promotion remains separate. Mod workflow plans identify inputs,
outputs, capabilities, stages and unavailable steps; they are not optimization plans.
One shared workflow, client-specific configuration only.

Gate: identical CLI/MCP semantic outcomes, no stale publication on cancellation,
actual fixed authoring tasks completed through supported interfaces.

### P7 — Deployment and PvE pilot

Separate language, independent semantics, native, staged engine compilation, engine
comparison, host gameplay, dedicated server/two independent clients and visual gates.
Dedicated cases: remote toggles never open local UI; authority remains functional;
death/respawn/ownership/disconnect/reconnect/JIP; repeated cycles/multiple tablets;
world teardown without retained UI/input ownership. Visual: ultrawide and 1920x1080,
clipping/hints/disabled/maps/missing services/stale/degraded conditions. Verify actual
rendered colors and separate affiliation/state palettes.

Unavailable capabilities leave gates open while independent work continues. Promote
exact verified artifacts only into owned destinations matching prior hashes; preserve
handwritten files and tested rollback. Gate: full selected matrix plus rollback.

### P8 — Whole mods, library and editor

Expand resource/dependencies, reusable components/properties, prefab templates,
complete layout/events, scenario/deployment and typed import/packing in that order.
Resolve references and preserve stable IDs/handwritten resources. Next migration:
rotor visuals; deployment/inventory follows its authority/spawn/deferred-validity/
consumption contracts.

Ship small used numeric/time/interpolation/filter/state/validation helpers with
widths/units/boundaries/targets/independent expected tests. Keep PID/tablet examples,
products/themes/capabilities/fixtures in SPARKOS package. Explicit deterministic
source sets initially; general dependency resolution is a separate implementation.

After AI workflow, optional Python LSP uses same C analyzer; minimal VS Code launcher.
Support syntax, unsaved diagnostics, hover/signatures/completion/definitions/symbols,
formatting edits, then verified references/rename. Handle byte/UTF-16/CRLF/multibyte
positions. Full snapshots first; incremental/persistent work requires latency evidence.
Gate: sample mod through packing with usable diagnostics and no generated repairs.

### P9 — Measured performance

Isolated experiments may parallelize; adoption waits for applicable lifetime,
deployment and measurement gates. Terrain preserves lattice/band/quad/chunk/winding/
colors/layers and uses fresh published storage; pooling needs separate retention
proof. Map traversal preserves ordered keys/references through histories. Query
elimination preserves append/duplicate/filter/projection/acquisition/cap/UI effects,
with invocation-owned workspaces and fallback before effects. Sensor generations
preserve visibility/repeated dwell/swap alignment/scan behavior and multiplayer.

Tracked mutation order: writer/escape inventory, generated interfaces preserving
references, publication/RPC/JIP/debug/removal/teardown coverage, complete epochs,
expiry certificate, one bounded incremental query, scalar witnesses, bounded demand.
Distinguish key/mutable ID/object/nested/world/cache generations. Invalidate before
mutation; rejected publication does not erase alias writes. Reentrant/incomplete
coverage uses ordinary evaluation. Preserve sweep callback/output/predicate/order.
Initial query is pure/total/bounded/ordered with covered transitions; shape changes
rebuild output. Capacity selects fallback, never a gameplay limit.

Native order: fixed storage reuse, destination construction, owned reuse, static
proofs, total guards, checked-block replay, separate prefix publication, bounded
specialization/PGO/ThinLTO, one private layout, finite plan selection, offline equality
saturation. Global restrict stays disabled. Start checked blocks with approved
i32 mul/add using valid i64 intermediates, iteration/source failure order and safe
inactive lanes. Search: two retained plans, 10000 nodes, 50000 rewrites, two-second
checker/candidate. Normal builds consume checked plans, not open-ended search.
Gate: retained adopted/rejected/unavailable outcomes; only released rules auto-enable.

## 3. Public interfaces and compatibility

Add context capabilities/examples, doctor [--probe native|enfusion-compile], analyze
--request, mod plan, v2 support in existing mod commands, optional mcp/lsp and installed
experiment run <name> --target native|enfusion. Preserve current command/result fields.
IR never silently falls back; auto reports actual path; opt off leaves Clang flags;
unknown family names error. New result fields are additive. Distinguish verification,
return, source trap, start failure, timeout, cancellation, unavailable and stale input.
Owned ABI changes invalidate artifacts and require full rebuild, no implicit mixing.

## 4. Verification and budgets

Wrap existing scripts with registry-driven selection, exact case sets and retained
evidence. Focused checks during work, full compiler checks at semantic boundaries,
engine suites for changed engine-facing output/contracts, full matrix for promotion.
Failed attempts stay failed; harness corrections get new receipts.

Bounded fuzzing: lexer/parser, manifest/companion/analysis, resolver/types, IR
tables/projections/init/origins, mappings/receipts and admitted differential programs.
Probe libFuzzer/sanitizers before claims. Retain seeds, minimized failures and hashes;
reducers preserve failure/prefix. Research cases close only on actual transformations.

AI tasks: PID change, property, event, prefab, deliberate engine-error repair,
correct scenario. Record assistant/client versions, input snapshot, outcomes, repair
rounds, elapsed time, unsupported API attempts and generated edits. Actual Claude
and ChatGPT trials stay distinct from synthetic protocol tests. Zero generated edits.

Performance: freeze metric/data/policy/budgets, baseline-baseline noise, threshold
max(5%, pilot p95 absolute paired variation), >=30 independent balanced paired blocks,
independent sessions unless reset equivalent, all paid setup/sampling/maintenance/
invalidation/conversion/publication/cleanup/cold refresh, semantic complete runs,
held-out workloads and interval-supported improvement. Use current exact
order-statistic median interval; tail estimator separate. Match Rust arithmetic,
layout/allocation/safety/PGO/CPU, both idiomatic and tuned baselines.

| Budget | Initial bound |
|---|---|
| Native private optimization storage | 8 MiB/region, 64 MiB/process |
| Static cache | 4096 entries/region, eight/world |
| Specialization | Two variants plus generic |
| Affected text growth | <=20% |
| Optimized build | <=2x equivalent verified baseline |
| Optional check overhead | <=10% over same correct disabled foundation |

Measure physical engine memory separately from entry counts. Allocation-changing
optimizations default resource_adequate_exact; stronger resource-observable claims
need separate evidence. Missing resources select fallback where the plan permits.

## 5. Execution and completion

Three workstreams: compiler/semantics; engine/authoring; tooling/evidence. One
integration owner for shared semantic contracts and one for engine sessions/promotion.
Every packet records objective/subset/baseline/contracts/dependencies/consumers/tests/
mutants/migration/evidence/fallback/rollback/limitations. Consumers wait for gates.

R0 requires trustworthy supported commands and inventory. R1 requires independently
verified admitted IR/storage. R2 requires complete regenerated tablet. R3 requires
verified PvE tablet/PID workflow. R4 requires whole-mod and AI/editor interfaces.
R5 requires at least one adopted complete-workload improvement and explicit other
experiment outcomes. Native speed does not close Enfusion gates; tablet completion
does not imply all MESH migrated.

Protocol references: [MCP stdio](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports),
[LSP](https://microsoft.github.io/language-server-protocol/specifications/lsp/3.17/specification/),
[libFuzzer](https://llvm.org/docs/LibFuzzer.html).
