# Beryl: implementation plan grounded in SPARKOS

Approved by the user on 2026-09-06. This document consolidates the approved plan
for implementation. It supersedes historical sequencing where that conflicts
with the priorities below, without treating research proposals as implemented.
Progress and evidence: [implementation state](SPARKOS_IMPLEMENTATION_STATE.md).
Prior fixes: [foundation handoff](FOUNDATION_IMPLEMENTATION.md).
Research backlog: [optimization blueprint](BERYL_OPTIMIZATION_AND_ENFUSION_BLUEPRINT.md).

## 1. Goal, vision, and evidence

Build Beryl into a language and local authoring system that makes Claude and
ChatGPT effective at creating complete Enfusion mods: logic, components, resource
definitions, prefabs, layouts, and tests.

| Decision | Direction |
|---|---|
| Main project | Beryl; SPARKOS supplies requirements and validation workloads |
| Priority | Enfusion usefulness first; shared foundations benefit native performance |
| First audience | The user's multiplayer PvE unit; public distribution later |
| Eventual coverage | Whole mods |
| Source organization | `.be` logic plus validated companion descriptions |
| First substantial release | Complete existing PID integrated into MESH |
| AI integration | Local tools shared by Claude, ChatGPT, scripts, and humans |

SPARKOS is a fictional defense-autonomy company for Arma Reforger. Its hardware
participates in MESH, the connecting software layer for operational pictures,
sensor observations, vehicle state, operator interfaces, and in-game commands.
The family includes BOLT, SHRIKE, PICKET, DRAY, VERGE, and TILLER. Model capabilities
explicitly instead of assuming every node is a quadcopter.

Brand source: `C:/Users/moham/Desktop/sparkos-brandkit/README.md` and its brand
skill/reference files. Greyscale structure, amber hazards, green active/powered
states, separate map-affiliation colors, specification-led language, distinct
corporate/technical typography, manufactured forms, consistent markings, and
honest unavailable/degraded states belong in a SPARKOS package, not compiler rules.

Current evidence establishes a working compiler with recorded correctness fixes.
Live MESH already has flight, sensors, commands, input, telemetry, and runtime
acceptance infrastructure. Host-side records do not prove dedicated-server
correctness with independent clients. A saved terrain-map capture and newer dirty
terrain code supersede older blank-map assumptions. Existing Beryl PID examples
are incomplete. MESH's string-keyed store shares entity references; value copies
would change its contract. Existing Workbench tooling provides API lookup,
compilation, RPC, asset import, prefab validation, and packing.

Preserve working-tree changes in Beryl, MESH, and the brandkit. Identify tested
baselines using source hashes as well as commits.

## 2. Architecture and public interfaces

| Layer | Responsibility |
|---|---|
| Language | Typed logic, explicit access modes, values, control flow, tests |
| Semantics | Declaration identity, ownership, effects, taint, target compatibility |
| Backends | Native C and EnforceScript |
| Mod descriptions | Components, exports, resources, prefabs, layouts, scenarios |
| Local tooling | Staging, validation, engine jobs, diagnostics, promotion |
| SPARKOS package | Products, theme tokens, node conventions, tested MESH examples |

Keep ordinary compilation in C11, independent of Python. Initially use Python's
standard library and existing PowerShell integrations for mod orchestration.
`beryl mod` dispatches to the installed helper using explicit process arguments;
it never executes project-supplied build scripts. Compilation and gameplay need
no model inference or API key. Workbench NetAPI is a local editor channel.

Use versioned JSON, beginning with `beryl.mod.json`, a published schema, and editor
completion. Descriptions identify project/addon identity, explicit native and
Enfusion source sets, binding version, exported classes and constructors,
components/callbacks/editor properties, resources and stable IDs, prefabs, layouts,
themes/events, and named scenarios. Only typed data and Beryl symbol references;
no arbitrary code or command strings. Unknown fields, unresolved symbols,
incompatible signatures, invalid resources, and duplicate identities fail early.

These are planned interfaces until separately implemented and tested:

| Command | Purpose |
|---|---|
| `beryl check --format json` | Structured compiler diagnostics |
| `beryl context project` | Versions, targets, features, source identity |
| `beryl context symbol <name>` | Signature, access modes, docs, source |
| `beryl context binding <name>` | Exact declaration and verification status |
| `beryl test --backend reference\|native\|differential` | Explicit execution mode |
| `beryl mod check` | Validate logic and companion descriptions |
| `beryl mod build` | Generate isolated candidate |
| `beryl mod verify --stage compile` | Workbench compilation of that artifact |
| `beryl mod verify --scenario <name>` | Separately supported runtime scenario |
| `beryl mod promote --artifact <id>` | Install verified compiler-owned output |

Preserve existing commands. Reference execution is opt-in while coverage is
bounded. Shared responses carry schema/operation IDs, source/compiler/binding/
artifact fingerprints, stage/status, spans and related locations, repair guidance,
generated-source mappings, raw log references, and measurements only for executed
operations. Distinguish success, failure, unavailable, timeout, cancellation, and
stale input. Add an optional MCP adapter only after the CLI works; one source of
truth for both assistants.

## 3. Implementation packets and sequence

Every packet records objective, dependencies, current source evidence, exact
behavior/interfaces, affected files/consumers, positive/negative tests, migration,
completion evidence, and remaining limitations. The packets below define these
requirements; implementation evidence belongs in the state record and linked logs.

### M0 — Trustworthy ordinary commands

Dependencies: existing foundation fixes and captured dirty-source baseline.
Consumers: every later milestone and local build scripts.

1. Record source hashes, compiler identity, installed engine version, integration
   tool revision, and existing evidence.
2. Reconcile roadmap, status, security documentation, and research labels:
   implemented, partial, proposed, unverified.
3. Remove security-control rebuild retries and content-changing nonces.
4. Replace shell composition with `CreateProcessW` and correct Windows argument
   encoding; argv-based process execution on supported POSIX systems.
5. Separate stdout, stderr, exit status, startup failure, timeout, cancellation.
6. Use isolated job directories, checked writes, explicit artifact IDs. Failed
   builds cannot run or publish previous executables.
7. Strict manifest handling for comments, booleans, malformed/unsupported values.
8. JSON diagnostics alongside existing human-readable output.

Tests: ordinary check/build/run/test; missing tools, denied launch, child failure,
failed writes, timeout/cancellation, concurrency, spaces/metacharacters, stale
executables, malformed manifests, JSON parsing and diagnostic spans.

Exit: all tested failure conditions are distinct from successful execution.
Correct Rust claims: overflow behavior is configurable, and unsafe does not
disable the borrow checker. See [Cargo profiles](https://doc.rust-lang.org/cargo/reference/profiles.html)
and [Unsafe Rust](https://doc.rust-lang.org/book/ch20-01-unsafe-rust.html).

### M1 — Module, type, and generated-symbol identity

Dependencies: trustworthy checking and test execution.
Files: resolver, type interning, checker, both backends, module tests/examples.

- Resolve lexical scope, current module, explicit imports, built-ins; eliminate
  global first-name-wins fallback.
- Implement item imports and module-qualified access through existing `use` syntax.
- Enforce `pub`; diagnose conflicts with both declaration locations.
- Intern named types by qualified declaration identity. Resolve methods by receiver
  declaration, not spelling. Only declared generic parameters are type parameters.
- Deterministic collision-free item/type/field/helper/temporary names. Explicit
  export mappings retain engine public names and reject conflicts.
- Tests import the real implementation instead of duplicating example logic.

Keep value semantics and parameter modes; no new lifetime syntax.
Exit: same-spelled types/methods in two modules stay distinct on both targets;
private access and ambiguous imports fail consistently.

### M2 — Bounded independent semantic reference

Dependencies: resolved declaration identity; do not wait for owning containers/IR.
Files: new C AST interpreter, semantic fixtures, CLI backend selection, emitters.

Evaluate AST with separate arithmetic/evaluation code from emitters/runtime
helpers. Support scalars, plain records, fixed arrays, function calls/access modes,
conditionals, structured loops, returns, short-circuiting, PID numeric intrinsics.
Enforce step and call-depth budgets. Specify expression/mutation order, widths,
failures; optionally record ordered observable events in tests.

Retain immediate `defer` until a separately versioned language change. Explicitly
reject unsupported owning containers/error unions. Use binary32 for `f32`, retain
grouping, disable contraction/fast-math in native parity builds, and repair Enfusion
literal precision. Admit finite test sequences, not universal floating-point parity.
Independent numerical fixtures and properties supplement agreement tests.

Exit: admitted native/reference corpus agrees and deliberate arithmetic/order/
state-update mutations fail the tests.

### M3 — Full current PID in MESH

Dependencies: M1/M2 subset and minimal explicit class export support. Do not wait
for maps, complete ownership, new optimizer, or whole prefab system.

Source oracle: live MESH `scripts/Game/SparkOSMesh/Flight/SPK_PID.c`; snapshot with
hash before porting. Preserve constructor defaults, gain/integral-limit setters,
derivative tau setter, integral inspection, reset, nonpositive dt, saturation
integral freeze, clamping, derivative on measurement, optional filter, exact state
update and output order. Constructor/setter distinctions are behavior. No retuning.

One Beryl implementation serves native tests and Enfusion. Class export generates
existing `SPK_PID` constructor/method interface, state directly in the generated
object, no adapter state allocation or per-step allocation.

Verification sequence:

1. Fixed and seeded sequences through independent reference.
2. Compiled native execution.
3. Original/generated EnforceScript side by side in isolated comparison addon.
4. Compare output and persistent state after every operation.
5. Generated class in isolated full MESH candidate.
6. Existing PID suite and relevant runtime acceptance scenarios.
7. Actual reset/handover integration.

Discrete state/transitions exact. Finite values use documented initial tolerance
`max(1e-6, 1e-5 * max(abs(a), abs(b)))`; changing it requires numerical explanation,
never hiding failure. Original fixture outside production discovery; exactly one
production SPK_PID. Exit: full tested behavior, running MESH candidate, no manual
generated edits.

### M4 — Reliable engine validation and AI context

Dependencies: successful port with identifiable staged artifacts.
Extend existing Workbench tools, not a competing bridge. Separate headless compile
and live NetAPI; verify engine/loaded project; track session ownership; never stop
unrelated sessions. Bind results to exact artifact. Reject stale completions and
source changes before promotion. Keep raw logs and map generated locations back
to Beryl/companion JSON, including constructors, callbacks, defaults, and statements.

Advertise only verified runtime/prefab/import/profiling capabilities. Harden test
wrappers against empty selections/incomplete results. Compiler-generated feature
inventory and tested examples serve concise Claude/ChatGPT instructions alike.
Exit: either assistant finds a symbol, edits it, checks it, and diagnoses engine
failure without guessing APIs or modifying generated files.

### M5 — Structured lowering and owned storage

Dependencies: independent AST reference and validated PID subset.
Introduce small typed IR with declaration IDs, places/projections, nested regions,
explicit exits, copy/move/replace/destroy, read/write/allocation/shape/failure effects,
and source provenance. First compare PID AST/IR execution, then enable backend path.
Explicit old/new boundaries reject unsupported ownership crossings.

Independent logical assignment values; eager recursive copies first; read-only
arguments borrow; sink transfers ownership. Cleanup on normal and early exits,
independent of user defer. Self-assignment/overlap preserve source until copied.
Check growth/allocation-size arithmetic. Track storage separately from binding;
reject invalidating mutation through active element/iteration borrows, including
callees. Enfusion copies nested values recursively. No native restrict without a
verified non-aliasing contract. Initially runtime-owned storage without observable
user destruction callbacks. Engine references use explicit validity/retention
contracts, never implicit duplication of entities/widgets/resources/live objects.

Exit: nested copy/move/overwrite/early-exit/resize/lifecycle tests show no unwanted
aliasing, invalid access, double cleanup, or unbounded retained storage.

### M6 — MESH data and reusable components

Dependencies: admitted container/string/reference operations documented per target.
Parsed types alone are not support evidence.

Start store migration at a compatibility boundary: Beryl metadata/decisions,
adapter preserves SPK_MeshEntity identity/lifetime. Preserve empty-ID rejection,
strictly newer updates, expiry boundary/persistence, removal results, enumeration,
wire serialization and replication. No detached snapshots without API migration.
Full ownership follows container/reference contract tests.

Verified bindings: exact signature, inheritance, nullability, units, access modes,
retention, authority. Separate extracted declarations from semantic annotations.
Generate descriptors, instance classes, properties, callback adapters invoking
ordinary Beryl functions with explicit state/inputs.

Client values remain untrusted. Repair field/container/interprocedural taint; clamp,
min, max are not universal validators. Generated request boundaries require authority
and validation policies. Requested actions differ from confirmed server state.
Proxy-local changes are not server updates: [Bohemia multiplayer scripting](https://community.bistudio.com/wiki/Arma_Reforger%3AMultiplayer_Scripting).

Exit: one reusable component and admitted store operations pass native checks where
applicable, Workbench compilation, and runtime scenarios.

### M7 — Whole-mod companion descriptions

Dependencies: reliable engine jobs, bindings, ownership-aware promotion.
Expand in order: resources/addon dependencies; components/typed properties;
verified-template prefab composition; UI/events; scenarios/deployment; imports/packing.
Stable resource IDs live in project lockfile; reject collision/missing reference.
Ownership manifest plus expected prior hashes limits promotion to compiler-owned
files; preserve handwritten files/unrelated resources.

UI bindings declare actual handlers, state source, action target, visibility,
enabled state, lifecycle. Actionless buttons are errors. SPARKOS package provides
semantic theme roles, distinct affiliation/state palettes, data plates/product
labels, capability controls, rebindable hints, and authoritative/pending/degraded/
unavailable state examples. Existing Blender pipeline authors assets; descriptions
assemble/validate. Structural prefab and visual checks are separate. Resolve brand/
model specification conflicts in product configuration before shipping.

Exit: complete sample component/prefab/resource set/small UI generated from source
and companions, no manual generated edits.

### M8 — Measured optimizations

Dependencies: declared semantics, reference path, workload measurement infrastructure.
Admit research individually in this order: copy elimination/bounded scratch;
destination construction; collection fusion; dependency-complete caching;
incremental queries; justified check hoisting; private layouts; checked blocks/
native vectors; two verified plans; later offline schedule search.

Use MESH queries, markers, expiry, terrain-processing kernels. Engine terrain
sampling remains opaque engine work. Every optimization retains verified reference.
Approximation, tick reductions, altered arithmetic/gameplay are separate product
experiments. Exit per experiment: preserved behavior, measured gain, explicit memory,
code-size and compile-time budgets met.

## 4. Verification and acceptance

Maintain existing foundation suite. Add regressions for module ambiguity/privacy/
identity/names, manifest/process arguments and failures, concurrency/stale artifacts,
source maps, incomplete test sets, deterministic output. Use available sanitizers;
record unavailable capabilities. Bounded malformed-input tests cover parser depth,
allocation arithmetic, compiler resource use.

PID tests cover defaults/configuration; positive/zero/negative dt; first/later
measurement; setpoint steps; saturation entry/release; positive/negative limits and
constructor/setter differences; filtering on/off/reconfiguration; reset; gain
changes; deterministic long sequences; every output and persistent field.

Evidence levels stay separate:

1. Beryl semantic checks.
2. Native/reference execution.
3. Workbench script compilation.
4. Engine pure-function comparisons.
5. Host gameplay.
6. Dedicated server with two independent clients.
7. Visual/interaction review.

Multiplayer checks authority command delivery, JIP, duplicate/stale updates,
removal, ownership changes, UI confirmation. Missing independent clients leave
the gate incomplete. UI review at current 3440x1440 and 1920x1080 checks clipping,
disabled behavior, hints, selections, missing entities, stale telemetry, map
interactions, color space. Screenshots only prove a captured appearance.

Three separate performance comparisons: Beryl authoring vs current workflow;
generated vs handwritten EnforceScript; native Beryl vs Rust. Record compilers,
flags, CPU, data, allocations, safety semantics, outputs, raw measurements. Both
idiomatic and matched tuned Rust baselines receive equivalent layout/allocation
opportunities with explicit overflow/panic/optimization settings.

Initial experiments: at least 30 independent paired blocks, alternate order,
fail on semantic mismatch/failed execution, report uncertainty/per-workload results.
Provisional 5% practical threshold adjusted for baseline noise before inspecting
candidate; include setup/invalidation/cleanup/maintenance paid by the application.

AI usability tasks: PID change, property addition, event binding, prefab creation,
deliberate engine-error repair, scenario execution. Measure repair rounds, elapsed
time, unsupported-API attempts, manual generated edits. Whole-mod gate requires zero
manual generated-code edits.

## 5. Rollout and completion

Both assistants use the same packets, feature inventory, commands, evidence.
Research pseudocode never establishes implemented support. Compile success alone
cannot close a runtime milestone.

Roll out isolated fixture, isolated MESH candidate, verified integration, unit use,
then broader distribution. Retain rollback artifacts and original behavioral fixtures.
First release completes only when full current PID is Beryl-authored, replaces the
existing implementation in a verified MESH candidate, and changes/tests work through
the documented AI workflow. Later releases require their own complete data,
component, whole-mod, multiplayer, or performance gates.
