# Shared Claude, ChatGPT, and human workflow

Use the same compiler and installed local tools. No model API key is needed to
compile Beryl or run generated code. Read the current
[delivery record](BERYL_DELIVERY_STATE.md) before assuming a planned
feature is available. Advanced IR and optimization ideas are not released support.

At the user's October 14 priority change, further engine testing is parked while
core compiler and 4GL authoring work continues. See the
[core continuation packet](advanced/CORE_AUTHORING_2026_10_14.md). Engine examples
below document supported historical workflows; they are not instructions to
resume a parked session or evidence that the current sources passed those gates.

The isolated tablet UI/frame/destruction checkpoint now passes actual Enfusion
execution. Read [its exact evidence and limitations](advanced/P5_TABLET_POST_RESTART_EXECUTION.md)
before using the experimental harness. Real player/equipment/click acceptance,
visual review and promotion remain open; generated lifecycle success does not
establish those capabilities.

## Find the implementation and its supported domain

```text
beryl context project source.be test.be
beryl context capabilities
beryl context examples
beryl doctor --format json
beryl context symbol sparkos.flight.pid.Pid.step pid.be
beryl context optimization sparkos.flight.pid.Pid.step pid.be
beryl context optimization --list
beryl context binding Math.ClampInt
beryl context binding CanvasWidget.SetDrawCommands
```

Context defaults to JSON and uses the files actually loaded. Package discovery uses
`beryl.toml` when files are omitted. A signature's parameter access modes are part of
its contract. Target admission is a compiler check, not evidence that the engine
executed that program. Unavailable binding/effect information must not be guessed.
The [bounded binding registry](advanced/STAGE_B_BINDING_CONTEXT.md) exposes 35
selected installed declarations with exact documentation fingerprints and byte
origins. Optional `--engine-executable` and `--api-root` paths verify matching
files without launching them. A successful lookup is a snapshot lookup;
`verified_contract` remains separate and unavailable. Use the repository's exact
tested binding fixtures and installed engine declarations for semantic claims.

## Make a bounded source change and verify it

For a fresh scalar component project, discover `tool.mod_init` first, then use:

```text
beryl mod init --template scalar-component --project ./MyComponent --name "My component" --addon-id MyComponent --addon-guid <your-16-uppercase-hex-GUID>
```

Creation requires a fresh destination and explicit addon identity. It writes
shared implementation, importing tests, a strict v2 companion and next commands.
The compiler-reserved `Beryl` prefix and reserved generated class names are not
valid addon IDs for this template. Init runs no compiler or engine checks;
follow the created README for check, reference/native tests and candidate build.
See [the supported starter profile](advanced/P6_MOD_INIT.md). Do not infer
properties, prefab/layout support or engine verification from source creation.

```text
beryl check --format json source.be test.be
beryl test --backend differential --lowering ast source.be test.be
beryl build --release --save-native-evidence source.be
```

The differential backend remains limited to its advertised reference subset. Native
and Enfusion have separate admission. The source toolchain additionally implements
experimental `test --backend differential --lowering ir` for the bounded plain-value
profile in [the IR packet](advanced/P2_IR_DIFFERENTIAL.md). Check the installed
compiler's registry before using it: the previous active installation is not
automatically updated by source changes. Production `build/run --lowering ir`,
Enfusion IR and incompatible reference overrides remain unavailable. `auto` remains
AST. Never silently change an explicitly requested verification mode. Expected
traps use dedicated fixtures and their exact byte sites, not a rule that all nonzero
processes are acceptable.

Native evidence retains C, exact compiler arguments and identity, LLVM IR, assembly,
and process logs. Inspect these before claiming fewer checks, copies, allocations,
or machine instructions. Evidence generation alone is not a performance experiment.
`--opt off` does not change Clang's optimization level. No family is currently released.

## Build and verify an isolated Enfusion candidate

The October component/tablet work has separate experimental harnesses documented
in [the engine packet](advanced/P5_TABLET_ENGINE_REPLAY.md). They require explicit
private compiler and exact engine/tool identities. They are not public v2
`mod verify` support: compilation, scripted VM replay, plain-member state,
actual callback delivery and tablet services are separate evidence scopes.
Use immutable raw receipts and the current source identity; a successful prior
run does not certify changed bytes.

The [tablet runtime acceptance packet](advanced/P5_TABLET_RUNTIME_ACCEPTANCE.md)
identifies the real input/gadget/component path, exact existing suite selectors
and separate callback/service/retention/deployment gates. The debug tablet view
opens UI directly and cannot certify the migrated lifecycle. The source-only
`scripts/prepare-tablet-resources.py --mesh-project <captured MESH root>` copies
eight reviewed files under a fresh build directory, preserving resource IDs.
It does not compile, import, resolve all resource dependencies or launch an engine.
Its `--self-test` records unavailable filesystem capabilities separately from
passed cases. The controlled source-layered game-world fixture now passes the
seven native scalar callback cases for its recorded inputs. Earlier opener
attempts remain failed; consult the current
[callback packet](advanced/P4_COMPONENT_CALLBACK_DELIVERY.md) before selecting a
specific engine job.

The [preserved tablet-suite packet](advanced/P5_TABLET_EXISTING_SUITES.md) records
the opt-in `tablet-suites-v1` resource/handler candidate and the actual five-suite
gate. `scripts/verify-tablet-existing-suites.py` accepts the exact fresh S1 receipt,
its SHA-256 and explicit host/engine/tool paths. Default preparation launches no
host; `--run` performs isolated compilation and the fixed five requests. Stale
inputs, unknown cases, unrelated sessions and incomplete receipts fail. Its
schema checker preserves native enumeration order while requiring the exact six
distinct components. Current source compilation includes warning diagnostics;
historical zero-warning counters do not establish their absence.

Those structural suites do not execute the Beryl tablet component. Continue
through [native tablet admission](advanced/P5_TABLET_NATIVE_LIFECYCLE_ADMISSION.md),
which separates component-only callbacks, real services, the complete prefab,
teardown and player/gadget ownership. The full input component can save default
keybindings during initialization; an owned addon alone is not an isolated user
profile. These experimental source harnesses are not installed public scenarios.

The current [native stowed-execution packet](advanced/P5_TABLET_NATIVE_STOWED_EXECUTION.md)
records a successful exact N0 candidate: five native cases, two owners with 64
complete stowed frame pairs each, 260 rows and confirmed owned cleanup. Its
independent terminal audit passes 40 named obligations. The capture harness holds 98 pinned-file
read leases with full byte checks around the capture window; fast checks inside
that window are namespace/readability/length evidence. The separate 314 lease,
33 actual pure startup and 91 inert wrapper cases do not replace native trace
verification. The optional symbolic-link guard remains untested locally.
Continue with [real-services admission](advanced/P5_TABLET_REAL_SERVICES_ADMISSION.md).
Do not substitute this stowed fixture for real UI/screen, player/gadget,
profile-isolation, deletion/retention, multiplayer or visual acceptance, or use
it as public `mod verify` support. Installation and performance releases remain
separate.

The [N1a execution packet](advanced/P5_TABLET_NATIVE_SERVICE_EXECUTION.md) now
records all seven actual native service cases, with the strict encoder and owned
RPC/session checks. Preserve its exact candidate and original failed attempts.

The [UI/destruction candidate](advanced/P5_TABLET_UI_NATIVE_CANDIDATE.md)
has passed complete isolated native execution, including the optional widget-slot
repair with zero GUI errors; see the exact
[post-restart receipts and limitations](advanced/P5_TABLET_POST_RESTART_EXECUTION.md).
Its default verifier stages sources; --run explicitly
requests the pinned readiness probe, isolated compile and engine execution.
The [historical host failure](advanced/P6_HOST_STARTUP_RECURRENCE.md) is retained;
host readiness now succeeds after restart. Do not treat source fixtures or a successful inventory as
runtime evidence. Do not fabricate native callbacks, UI replies, or a player.

Player/gadget tests require confirmed owned-profile isolation before native input
initialization can save bindings. Numeric text, script screen flags and owner
tokens do not establish bitwise floating-point, native binding, pixels, or lifetime.

```text
beryl mod plan --project <project>
beryl mod check --project <project>
beryl mod build --project <project>
beryl mod scenarios --project <project>
beryl mod verify --project <project> --artifact <id> --stage compile --workbench-tools <installed-plugin>
beryl mod verify --project <project> --artifact <id> --scenario probe.map.cursor --scenario-count 64 --workbench-tools <installed-plugin>
beryl mod verify --project <project> --artifact <id> --scenario compare.terrain.chunks --workbench-tools <installed-plugin>
beryl mod verify --project <project> --artifact <id> --scenario probe.array.storage --workbench-tools <installed-plugin>
beryl mod verify --project <project> --artifact <id> --scenario probe.canvas.retention --workbench-tools <installed-plugin>
```

The mod orchestrator uses installed Python; set `BERYL_PYTHON` to its executable if
Python is not on PATH. Ordinary Beryl compilation remains independent of Python.
The source `mod plan` operation describes exact companion/source bytes without
running compiler checks, programs or the engine. A successful plan can describe
invalid Beryl source; use the separate check before building. Read its unavailable
stages rather than assuming a command template is executable. This optional tool
revision is not automatically installed with a source edit.
Use the returned artifact ID, source/tool/compiler fingerprints, and complete receipt.
Scenario inventory reports what the installed bundle provides; absent capabilities
remain unavailable. Do not substitute a similarly named handwritten test.
The terrain scenario compares fixed cached-grid command payloads before Canvas
publication. It does not measure rendering speed or prove consumer lifetime.
See [the engine experiment packet](advanced/STAGE_C_ENGINE_EXPERIMENTS.md).
The [storage and collection packet](advanced/STAGE_C_STORAGE_AND_COLLECTION.md)
defines the new probes precisely. Immediate script-reference observations do not
establish native rendering lifetime or permit reuse of published buffers.

The strict version-1 companion selects source sets, bindings, and exports. The
version-2 component pilot adds bounded declaration, source-order and signature
admission. Its experimental `mod build` renders generic scalar component
wrappers with exact compiler linkage; nested state and tablet services remain
outside generation. Public v2 engine verification and promotion remain unavailable.
Its captured engine hash is declared applicability, not a checked running engine.
The pinned signature catalog retains its original admission-only status; the
separate `mod.component_generation` capability describes the renderer.
Staged inputs must match frozen project hashes before and after compiler
operations and before publication. A changed copy fails as stale input.
Scenario
CLI parameters are typed by the installed scenario. Do not add unrecognized fields,
project shell commands, arbitrary engine code strings, or manual generated edits.

Generated source-map sidecars carry exact hashes. Engine diagnostics retain `raw`
data and, when validated, `mapped_span` with Beryl origin, default request location,
and companion export pointer. A mapped span is not a token-column translation.
If a location remains unavailable, inspect its retained raw log and exact staged
generated file. Repair `.be`, companion data, or the generator as appropriate;
rebuild to obtain a new artifact.

Only owned engine sessions may be stopped. A busy editor is a distinct unavailable
condition. Timeout, cancellation, stale bytes, missing cases, and partial output
never pass. Native tests, Workbench compile, VM comparisons, host integration,
dedicated multiplayer, and visual checks are separate gates.

## Promote only after the required gates

```text
beryl mod promote --project <project> --artifact <id> --destination <compiler-owned-output>
```

Promotion checks the exact successful compile receipt and previous generated hashes,
preserves handwritten files, and retains rollback data. A compile receipt alone does
not establish gameplay, authority, multiplayer, or visual correctness; use the
release gate for the affected change. Existing MESH identity, wire formats, PID
behavior, and SPARKOS product conventions remain contractual requirements.

When reporting work, identify source/artifact/compiler/tool versions, checks actually
executed, positive and negative outcomes, and remaining unavailable gates. A proposed
optimization, synthetic test, or favorable single timing cannot establish a speedup.

## Evaluate collected performance evidence

The experimental standalone [receipt evaluator](../tools/beryl-experiments/README.md)
accepts a strict versioned contract and requires baseline-noise calibration,
frozen policy, at least 30 balanced independent pairs, complete semantic receipts,
resource budgets and held-out evidence. It does not collect measurements or
authenticate an external collector's assertions. The separate
[Enfusion collector](../tools/beryl-experiments/COLLECTOR.md) records actual scoped
construction/release intervals and retains replayable raw evidence. Its initial
results remain exploratory: same-session batches do not establish independence,
and whole-engine memory counters do not establish per-workload allocation or peak
memory. Missing metrics remain unavailable. Analytical fixtures for these tools
are synthetic validation, not Beryl performance results.

`beryl experiment run` remains a planned interface. Do not invent that command's
support from the presence of the standalone evaluator. A successful evaluation
process may still return a rejected performance decision; inspect `decision`.

## Respect the experimental execution boundary

The internal IR evaluator runs the admitted record/fixed-array/PID subset.
Experimental native differential testing can explicitly select `--lowering ir`
in source revisions that advertise it. Production IR build/run and Enfusion IR
remain unavailable; `--lowering auto` remains AST. Read the
[array IR packet](advanced/P2_IR_ARRAYS.md) for precise coverage before extending it.

BE1001 can reject projected assignment when its RHS or index evaluation may mutate
overlapping storage. Make the intended order explicit in separate source statements
before selecting the destination, then rerun differential tests. Do not silence the
diagnostic, widen a floating tolerance, or edit generated code to obtain a pass.
The older reference/native disagreement is retained as a counterexample; it is not
the specification for either result.

BE0401 also rejects mutation that can replace an aggregate or projected mutable
place while an earlier call argument is borrowed. Mutate before selecting the
argument or prepare an independent value snapshot in a separate statement.
Method receivers obey the same `let`, `inout`, `set` and `sink` access checks as
ordinary arguments. A source-only target check does not prove engine execution;
unsupported Enfusion receiver replacement/transfer must use an admitted explicit
function boundary or wait for a verified lowering.

## Analyze exact unsaved bytes

`beryl analyze --request <request-directory/request.json>` runs the existing C
semantic passes over a complete supplied snapshot. The published
[version-1 request schema](../schemas/beryl.analysis.v1.schema.json) requires the
request ID, snapshot/document versions, target, unsafe policy, logical source paths,
SHA-256 values and adjacent content filenames. Every content file is mandatory.
Missing content never falls back to a similarly named project file.

Responses report byte offsets and byte columns, not LSP UTF-16 positions. Apply a
response only while its request ID, versions, source bytes and compiler identity
still match the client. Read the [analysis packet](advanced/P6_ANALYSIS.md) for
resource limits and the distinction between an admitted program and executed code.
This interface does not launch Clang, Python, Workbench or a model.

## Optional local MCP transport

The delivery candidate adds an experimental standard-library Python adapter.
Install the trusted tool bundle beside the selected verified compiler before using
`beryl mcp`; an older compiler/bundle does not acquire this command from this document.
Both assistants use the same server and this workflow. No model API key or listening
network service is needed.

Configure the client's local stdio server with the selected Beryl executable and
arguments `mcp --project <absolute-project-directory>`. Set `BERYL_PYTHON` to the
trusted Python executable if needed. For explicit engine verification, add the
server launch option `--workbench-tools <installed-plugin-directory>`. Without that
option engine verification reports unavailable; context and native work still run.

The [MCP stdio protocol](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports)
uses newline-delimited JSON-RPC on standard input/output. The adapter implements
version `2025-11-25`, initialization, ping, tool discovery/calls and cancellation.
It does not expose HTTP, sampling, prompts, resource subscriptions, task queues or
an implicit promotion operation. Standard input/output belongs exclusively to the
protocol. Diagnostics and raw child logs are retained separately.

| Tool | Supported operation |
|---|---|
| `beryl_context` | Actual project/capability/example/symbol/binding/optimization context |
| `beryl_doctor` | Inventory; optional explicit native readiness probe |
| `beryl_analyze` | Exact request plus supplied content strings, passed to the C analyzer |
| `beryl_test` | Explicit native/reference/differential execution of selected sources |
| `beryl_mod` | Installed check/build/scenario discovery and explicit artifact verification |
| `beryl_evidence` | Bounded receipt/source-map JSON and its hash; applicability stays unchecked |

Tool parameters never contain shell commands or executable overrides. Compiler,
Python and Workbench tool locations are launcher configuration. Sources and receipt
paths are project-relative and reject traversal, links and ambiguous forms. Reading
a source map is supported; automatic diagnostic mapping remains the existing mod
tool's responsibility rather than a second Python semantic implementation.

Only one operation owns a server at a time. A second execution request reports busy;
ping and cancellation remain responsive. Cancellation terminates the current owned
process tree and suppresses a successful response from that request. It does not
undo completed file generation or substitute for promotion's hash/ownership gates.
Default operation timeout is 120 seconds; the trusted launcher may select
`--timeout-seconds` within 0.05–1800 seconds for an appropriate installed scenario.

Limits are 12 MiB per JSON frame, depth 64, 262,144 decoded values, 4 MiB per captured
output stream, and 4,096 request IDs per session. The C analyzer's stricter source
and request limits still apply. Oversized output is an explicit failure, with capped
raw logs; it is never a truncated successful diagnostic response.

Adapter receipts live under `.beryl-mcp/jobs/`. The nested CLI result is preserved;
CLI process completion, source traps, admission and engine verification retain their
different meanings. A receipt read does not authenticate its author or establish
current applicability. Synthetic protocol tests are not actual Claude/ChatGPT trials;
the fixed authoring task trials and complete tablet workflow remain separate gates.
