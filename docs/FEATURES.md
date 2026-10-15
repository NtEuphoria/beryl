# Compiler capability catalogue

Generated from `beryl context capabilities` and `beryl context examples`.
Regenerate with `python scripts/verify-capabilities.py --beryl <compiler> --write-doc`.

Registry schema: 1. Metadata fingerprint: `ab9ef110e63945d18c1a2ba13c3ffd3cdcd312bc3e7b76c15f12e0621ea39f1b`.

This inventory describes compiled implementation boundaries. It does not establish
admission of a particular source set, local tool availability, current execution,
or applicable verification evidence. Test groups identify obligations, not passing
receipts. Use `context project` for actual source admission and the implementation
state for separately identified historical evidence. Receipt resolution remains unimplemented.

The repository paths below are discovery references. An installed compiler can list
them without the source repository; it does not claim those files exist locally.

| Capability | Implementation | Targets | Interface | Boundary |
|---|---|---|---|---|
| `compiler.allocation_arithmetic` | bounded | native, compiler | compiler arenas/vectors and native List growth | Checked size arithmetic and descriptor preparation in the admitted helpers; not whole-compiler memory safety or complete List cleanup. |
| `language.modules` | bounded | native, reference, enfusion | use / pub / qualified names | Explicit imports and qualified declaration identity; generic instantiation and external extension methods remain unsupported. |
| `compiler.parser_limits` | bounded | native, reference, enfusion, compiler | parse_file / BE0210 | Per file: 262144 tokens including EOF, 256 guarded parser frames, AST depth 128, 262144 visited AST nodes, 1048576 charged work units. Lexing precedes this gate; no lexer allocation, cross-module/default-expansion or whole-program resource guarantee. |
| `language.plain_values` | bounded | native, reference, enfusion | struct / fixed arrays / let / inout / set / sink | Target admission differs. Implicit receivers use the same access/move/initialization analysis as explicit arguments. Bounded shared checks contain overlapping projected assignments and mutation across borrowed call capture intervals. This does not establish owning-container copying, cleanup or complete effects/aliasing. |
| `language.taint` | partial | native, reference, enfusion | @untrusted / @secret / @server_only / @constant_time | Bounded context-insensitive monotone propagation through record field paths, conservative indexed-element summaries, mutable arguments and call returns. This is not full symbolic validation, whole-program authority proof or a backend constant-time guarantee. |
| `native.ast` | bounded | native | beryl check / build / run / test / emit-c | Typed AST to C11 and a selected Clang toolchain; only admitted source shapes are supported. |
| `native.checked_arithmetic` | bounded | native | checked integer arithmetic and explicit wrapping/saturating intrinsics | Admitted scalar operations; this is not proof that internal container capacity arithmetic or every backend path is safe. |
| `native.owned_storage` | partial | native | List<T> and owning aggregate paths | Local scalar/plain-element List operations remain admitted; unsupported owning copies, replacements, returns and transfer paths are rejected. General recursive copying, automatic cleanup and complete ownership/effect contracts remain unavailable. |
| `language.storage_admission` | partial | native, enfusion | storage_classify / storage_admit / BE0903 / BE0701 | Recursive resolved-type classification and bounded rejection of unsupported logical owning copies and invalidating borrows. Admitted scalar collection operations and Enfusion scalar collection-field copies do not establish general lifecycle cleanup or complete storage effects. |
| `reference.ast` | bounded | reference | beryl test --backend reference\|differential | Explicit finite numeric/plain-record/fixed-array subset with budgets. Owning containers, conflicting projected destinations and unstable borrowed call captures are outside coverage. |
| `reference.expected_traps` | bounded | native, reference | beryl test --backend differential --expect-source-trap | Overflow, division-by-zero and bounds; bounded ordered observations and optionally one admitted fixed i32 output root. Harness failures never match source traps. |
| `enfusion.ast` | bounded | enfusion | beryl check\|build --target enfusion | Admitted scalar/plain-record subset. Unsupported reference-array copies, set/sink self and whole-self replacement are rejected. Field updates remain admitted; engine execution is separate. |
| `enfusion.bindings` | bounded | enfusion, compiler | beryl context binding | 35 selected local API declarations with hashes. Extracted declarations are not complete typed bindings or verified lifetime/effect/authority contracts. |
| `enfusion.source_maps` | bounded | enfusion | beryl build --target enfusion --source-map | Generated lines map to original byte spans; full nested expansion chains and engine-column interpolation remain unavailable. |
| `mod.class_exports` | bounded | enfusion, tooling | beryl mod check\|build\|verify\|promote | Version 1 covers addon/source identity and scalar class/constructor/method exports. It does not cover complete components, resources, prefabs or layouts. |
| `mod.scenarios` | bounded | enfusion, tooling | beryl mod scenarios / verify --scenario | The installed tool owns exact scenario discovery and availability. Source metadata does not establish local runtime capability or a current successful receipt. |
| `mod.whole_authoring` | unavailable | enfusion, tooling | planned companion authoring expansion | Bounded v2 scalar component generation is separate. Tablet service integration, editor properties, resources, prefab/layout/events and full authoring acceptance remain planned. |
| `mod.component_admission` | experimental | enfusion, tooling | beryl mod check\|plan with strict v2 component profile | ScriptComponent descriptor/instance pairs, three captured callbacks and reviewed superclass order. Check resolves public plain-state/handler signatures; plan only validates structure. No callback behavior, engine lifetime/authority, generation, tablet or resource release is implied. |
| `mod.component_generation` | experimental | enfusion, tooling | beryl mod build with strict v2 component profile | Generates descriptor/instance pairs, one persistent scalar state object, ordered callback/superclass/frame-event code and companion/source origins using exact emitted compiler names. Nested state, tablet services, engine verification and v2 promotion remain unavailable. |
| `tool.context` | bounded | compiler | beryl context project\|symbol\|binding\|optimization\|capabilities\|examples | Uses compiler declarations and admission; does not execute programs or verify an engine session. |
| `tool.doctor` | bounded | compiler, tooling | beryl doctor [--format json] [--probe native] | Default inventory launches nothing. The explicit fixed C11 probe validates selected compile/run readiness only; Python compatibility, loaded engine sessions, complete bindings and Enfusion doctor compilation remain unverified. |
| `tool.native_evidence` | bounded | native, tooling | beryl build --save-native-evidence | Retains selected compiler identity, C, exact argv, LLVM IR and assembly when supported; dependent SDK/linker identity is incomplete. No timing result is implied. |
| `tool.terrain_collection` | bounded | enfusion, tooling | beryl mod verify --scenario measure.terrain.construction | Typed schedules and replayable journals; same-session pairs are dependent exploratory observations, not an adoption decision or game frame-rate claim. |
| `ir.evaluator` | experimental | compiler | internal ir_lower / ir_verify / ir_test API | Bounded finite f32, plain records and fixed arrays, checked dynamic projections, independent copies, initialized/moved root states and let/inout/set/whole-root sink. Loop back edges must preserve admitted outer state. Partial moves, owned storage and production IR remain unsupported. |
| `ir.codegen` | unavailable | native, enfusion | beryl build --lowering ir | Production IR lowering returns unavailable. Auto uses AST. The separate experimental differential-test profile does not release a production backend. |
| `ir.differential_tests` | experimental | native, tooling | beryl test --backend differential --lowering ir | Instrumented schema-5 test emitter: finite binary32, i32, bool, plain records/fixed arrays, initialization and let/inout/set/whole-root sink. Bounded loop-state admission and fixed native budgets; no owning values, production entry point, Enfusion lowering, root snapshots or performance claim. Auto remains AST. |
| `optimizer.released` | unavailable | native, enfusion | beryl build --opt auto\|off / --disable-opt | Flags and research family discovery exist, but no automatic Beryl transformation family is released. Clang optimization flags are separate. |
| `tool.analysis` | bounded | compiler | beryl analyze --request <file> | One-shot C analysis of all supplied bytes, with request/hash/document-version correlation and bounded strict JSON. No logical-source disk fallback, execution, persistent server or editor position conversion. |
| `tool.mcp` | experimental | tooling | beryl mcp --project <path> | Optional installed Python stdio adapter over the same CLI. Typed context, analysis, evidence, v1 export/v2 component workflows and explicit test/mod operations. No promotion, LSP, whole-mod authoring or actual assistant trial evidence is implied. |
| `tool.mod_plan` | bounded | enfusion, tooling | beryl mod plan / beryl_mod operation=plan | Strict v1 exports or bounded v2 component structure: 16 MiB per input, 64 MiB captured inputs, 3 MiB canonical plan. Symbols, target semantics and engine availability remain not_checked. No compiler execution, tablet or whole-mod completion. |
| `tool.mod_init` | experimental | enfusion, tooling | beryl mod init --template scalar-component | Creates fresh shared Beryl logic, importing tests, strict v2 companion and README using explicit project/addon identity. No compiler or engine execution during init; existing destinations are refused and partial writes are reported. Engine verification, promotion, properties, resources, prefabs and layouts remain separate. |
| `tool.lsp` | unavailable | tooling | planned optional LSP adapter | Exact unsaved snapshot analysis exists; LSP transport, editor position conversion and editor extension remain unavailable. |
| `library.general` | unavailable | native, enfusion | planned tested library modules | Compiler intrinsics exist; lib/ currently has no Beryl standard library. The SPARKOS PID is a separate tested package. |

## Example discovery

Every command below is informational and requires the source repository and its
admitted target environment. Catalogue discovery does not execute or verify it.

### arithmetic.native

Native checked arithmetic regression

Targets: native.

From the repository root: beryl run tests/e2e/arith.be

Native fixture only; this entry does not claim reference or Enfusion admission.

- `tests/e2e/arith.be`

### records.native

Native plain-record regression

Targets: native.

From the repository root: beryl run tests/e2e/structs.be

Plain records; no owning-container lifecycle guarantee.

- `tests/e2e/structs.be`

### pid.complete

Complete SPARKOS PID package

Targets: native, reference, enfusion.

Follow packages/sparkos/pid/README.md; explicit source sets and separate native/reference and engine commands are required.

Finite tested PID inputs and scalar exported interface. Historical isolated MESH candidate acceptance does not prove current source execution or dedicated multiplayer.

- `packages/sparkos/pid/pid.be`
- `packages/sparkos/pid/pid_test.be`
- `packages/sparkos/pid/beryl.mod.json`

### tablet.lifecycle_protocol

Experimental SPARKOS tablet lifecycle protocol

Targets: reference.

Run scripts/verify-tablet-lifecycle.py with an explicitly identified compiler; see its implementation packet for source/reference coverage.

Operation-local scalar protocol with synchronous fixture services. No live engine objects, generated tablet service adapter, lifecycle runtime or multiplayer release.

- `packages/sparkos/tablet-lifecycle-prototype/src/lifecycle.be`

## Regression obligations

| Group | Suite source | Positive obligation | Negative obligation |
|---|---|---|---|
| modules | tests/unit/test_modules.c | qualified declarations, imports and receiver identity | private access, ambiguous imports and declaration conflicts |
| values | tests/unit/test_ownership.c | initialization, plain-value modes and disjoint access | uninitialized reads, moves and overlapping call access |
| native | scripts/verify-foundation.py | generated programs at O0/O2 | checked overflow, bounds and division failures |
| reference | scripts/verify-reference.py | bounded reference and differential programs | unsupported programs and exhausted budgets |
| destinations | scripts/verify-reference-destinations.py | safe projected assignment and full PID | overlapping destination mutations rejected before execution |
| call_captures | scripts/verify-call-captures.py | stable borrowed call places, scalar capture and independent snapshots | overlapping selection, nested mutation and move during later argument evaluation rejected before jobs |
| receiver_modes | scripts/verify-receiver-modes.py | implicit receiver and explicit-argument access parity, including first set initialization | borrowed or partial sink, use-after-move, immutable set and premature initialization |
| traps | scripts/verify-expected-traps.py | expected source traps and successful observation prefixes | wrong site, missing trap and changed observation prefix |
| security | scripts/verify-taint.py | bounded field/element/call provenance and fixed-array interval proofs | laundering, helper sinks, propagated errors and secret control; no complete security or runtime authority claim |
| allocation | scripts/verify-allocation.py | checked arena/vector/string/map and native List growth | size overflow, capacity overflow and injected allocation failure |
| enfusion | tests/unit/test_enfusion.c | admitted EnforceScript generation | unsupported types and reference-array copy fields |
| enfusion_receiver_admission | scripts/verify-enfusion-receiver-admission.py | field updates, ordinary explicit parameters and unchanged PID target admission | unsupported implicit receiver replacement and transfer rejected before generation |
| driver | scripts/verify-driver.py | explicit argv and isolated native jobs | failed writes, failed launch, timeout, cancellation and stale publication |
| context | scripts/verify-context.py | resolved signatures, modes, defaults and source identity | ambiguous names, unknown names and unavailable bindings |
| bindings | scripts/verify-binding-registry.py | exact selected declaration fragments and matching identities | missing or mismatched engine/API bytes |
| native_evidence | scripts/verify-native-evidence.py | generated C, arguments and requested compiler artifacts | unsupported lowering and malformed evidence options |
| maps | scripts/verify-source-map-diagnostics.py | generated-line mapping with retained raw diagnostics | stale artifacts, source mismatches and unmappable columns |
| mod | scripts/verify-mod.py | strict companion validation, isolated build and guarded promotion | unknown fields, missing symbols, changed output and rollback conflicts |
| component_contracts | scripts/verify-component-contracts.py | captured ScriptComponent declaration and source-order profile | unknown contracts, stale declared identity, parent/callback/order conflicts and unsafe state signatures |
| component_workflow | scripts/verify-component-workflow.py | strict v1 compatibility, v2 signatures/source artifacts and non-executing CLI/MCP plan parity | stale context, invalid callback/state mappings and unavailable engine promotion |
| component_generation | scripts/verify-component-generation.py | scalar component wrappers using exact compiler linkage and mapped origins | nested state, conflicting symbols, tampered metadata and per-call state copies |
| tablet_lifecycle | scripts/verify-tablet-lifecycle.py | experimental synchronous scalar tablet protocol and independent ordered fixture services | reordered commits/calls, changed cadence, incorrect reentry and incomplete traces |
| scenarios | scripts/verify-mod-scenarios.py | typed scenario discovery and complete case receipts | unknown cases, partial results, stale tokens and session ownership conflicts |
| storage | scripts/verify-storage-scenarios.py | controlled array and Canvas reference observations | incomplete cases, reference-copy rejection and retention control failures |
| terrain | scripts/verify-terrain-scenario.py | complete ordered command payload comparison | deliberate vertex mutation and incomplete receipts |
| collection | scripts/verify-terrain-measurement.py | typed schedules, actual interval collection and journal import | invalid plans and incomplete or inconsistent measurements |
| ir | tests/unit/test_ir.c | independent bounded IR evaluation and actual PID parity | invalid IR, unsupported shapes and deliberate semantic mutants |
| pid | scripts/verify-pid.py | original/generated/reference PID operations and persistent state | missing comparisons, stale source identity and semantic mismatch |
| capabilities | tests/unit/test_capabilities.c | registry dependencies, target domains and deterministic serialization | duplicate IDs, unknown links, cycles and invalid target claims |
| doctor | scripts/verify-doctor.py | read-only inventory and explicit fixed C11 native probe | missing tools, malformed metadata, failed launch, timeout and missing executable |
| parser_limits | scripts/verify-parser-limits.py | admitted ordinary syntax and complete PID sources | deep or oversized syntax rejects with BE0210 before recursive consumers |
| analysis | scripts/verify-analysis.py | exact snapshot admission, byte spans and versions | missing overlays, malformed JSON, stale hashes, held-file mutation and cancellation |
| mcp | scripts/verify-mcp.py | CLI parity over bounded local stdio protocol | invalid parameters, output limits, stale inputs and owned-operation cancellation |
| ir_differential | scripts/verify-ir-differential.py | explicit bounded IR-C differential tests and retained native evidence | unsupported shapes, wrong traps, prefix mutations and incomplete execution |
| mod_plan | scripts/verify-mod-plan.py | deterministic v1 structural plans and real CLI/MCP parity | malformed inputs, stale identities, resource bounds, unexpected side effects and fabricated execution/admission |
| mod_init | scripts/verify-mod-init.py | fresh scalar-component sources, imported tests and actual CLI check/build execution | existing destinations, malformed identity, partial writes and unsupported options cannot overwrite user files or imply engine verification |
| storage_admission | scripts/verify-storage-admission.py | admitted local scalar List operations and target copy profiles | unsupported owning copies/transfers/returns and invalidating borrowed-storage operations |

## Compatibility and limits

The context envelope remains version 1. Existing project/symbol/optimization
fields remain present; the `catalogue` discovery field and the two catalogue
topics are additive. The catalogue itself has an independent versioned identity.

Implementation labels are `unavailable`, `experimental`, `partial`, and `bounded`.
A partial capability is not a safety guarantee. An experimental interpreter does
not release code generation. Target filters limit discovery and do not run admission.

Registered optimization families remain proposed. No released Beryl optimization
plan, current performance measurement, engine contract or Rust advantage is implied.
