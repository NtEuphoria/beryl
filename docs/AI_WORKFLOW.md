# Shared Claude, ChatGPT, and human workflow

Use the same compiler and installed local tools. No model API key is needed to
compile Beryl or run generated code. Read the current
[delivery record](BERYL_DELIVERY_STATE.md) before assuming a planned
feature is available. Advanced IR and optimization ideas are not released support.

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

```text
beryl check --format json source.be test.be
beryl test --backend differential --lowering ast source.be test.be
beryl build --release --save-native-evidence source.be
```

The differential backend remains limited to its advertised reference subset. Native
and Enfusion have separate admission. `--lowering ir` currently returns unavailable;
do not remove an unsupported-feature error by silently changing the requested
verification mode. Expected traps use dedicated fixtures and their exact byte sites,
not a rule that all nonzero processes are acceptable.

Native evidence retains C, exact compiler arguments and identity, LLVM IR, assembly,
and process logs. Inspect these before claiming fewer checks, copies, allocations,
or machine instructions. Evidence generation alone is not a performance experiment.
`--opt off` does not change Clang's optimization level. No family is currently released.

## Build and verify an isolated Enfusion candidate

```text
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
Use the returned artifact ID, source/tool/compiler fingerprints, and complete receipt.
Scenario inventory reports what the installed bundle provides; absent capabilities
remain unavailable. Do not substitute a similarly named handwritten test.
The terrain scenario compares fixed cached-grid command payloads before Canvas
publication. It does not measure rendering speed or prove consumer lifetime.
See [the engine experiment packet](advanced/STAGE_C_ENGINE_EXPERIMENTS.md).
The [storage and collection packet](advanced/STAGE_C_STORAGE_AND_COLLECTION.md)
defines the new probes precisely. Immediate script-reference observations do not
establish native rendering lifetime or permit reuse of published buffers.

The strict version-1 companion selects source sets, bindings, and exports. Scenario
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

The internal IR evaluator now runs the admitted record/fixed-array/PID subset. It is not an
available public backend: `--lowering auto` remains AST, and explicitly selecting
unsupported IR still returns unavailable. Read the
[array IR packet](advanced/P2_IR_ARRAYS.md) for precise coverage before extending it.

BE1001 can reject projected assignment when its RHS or index evaluation may mutate
overlapping storage. Make the intended order explicit in separate source statements
before selecting the destination, then rerun differential tests. Do not silence the
diagnostic, widen a floating tolerance, or edit generated code to obtain a pass.
The older reference/native disagreement is retained as a counterexample; it is not
the specification for either result.

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
