# P6 — Non-executing version-1 mod workflow plans

## Objective and scope

This packet records the version-1 implementation checkpoint. The later
[P4-A component admission](P4_COMPONENT_ADMISSION.md) adds strict version-2
structural planning through the same CLI/MCP interface. That plan still leaves
symbols unchecked. The subsequent [P4-B renderer](P4_COMPONENT_GENERATION.md)
adds a conditional source-build action for flat scalar state; planning still
does not execute it, establish engine availability, or enable promotion.
The historical scope and receipts below remain tied to their original bytes.

`beryl mod plan` describes the current class-export workflow for an exact
version-1 companion and its declared source bytes. Claude, ChatGPT and a human
receive the same machine-readable plan, identities, dependencies, unavailable
steps and repair guidance. This is a workflow description, not an optimization
plan, semantic verification, build receipt or authorization to promote files.

The optional Python tool implements this command using the existing strict v1
schema, path checks, source-set validation, export receiver check and installed
scenario registry. It does not invoke the compiler's parser or semantic passes.
An invalid Beryl program can therefore have a successfully constructed plan:
the response explicitly leaves symbols and target semantics `not_checked`.

The C compiler, companion schema, installed loader templates and active
installation are unchanged by this implementation. The changed optional tool
files acquire a new bundle fingerprint. Earlier receipts apply to their earlier
bytes; installing this tool revision remains a separate guarded operation.

## Public interfaces

```text
beryl mod plan --project <directory>

# Direct trusted-tool invocation, useful before installation:
python -I -B tools/beryl-mod/mod.py plan --project <directory> --beryl <compiler>

# Existing local MCP tool:
beryl_mod({"operation": "plan"})
```

Only project/compiler selection is accepted by the direct CLI. Artifact,
scenario, scenario parameters, measurement plans, stage, destination and
Workbench execution options fail before a mod Job is created. The MCP launcher
already fixes the compiler and project; the plan tool arguments contain only
`operation`. The existing mixed-operation `beryl_mod` tool retains its
conservative `readOnlyHint: false`, because other operations can execute code.

The planner creates no files, directories, artifacts, jobs or logs. It starts
no subprocess and does not compile or execute Beryl, run a native readiness
probe, inspect a live engine, or run an installed scenario. It disables Python
bytecode writes before importing scenario metadata.

There is a transport distinction: the existing C `beryl mod` dispatcher starts
the Python tool and retains its own `.beryl-cache` logs. The MCP adapter likewise
retains request/response logs. Neither wrapper behavior is evidence of program
execution, and this packet does not claim those wrappers perform zero writes.

## Response contract

The existing envelope uses `schema_version: 1`, `operation: "mod plan"`, a fresh
operation ID and `stage: "planning"`. Successful construction returns:

| Field | Meaning |
|---|---|
| `status: success` | Structural snapshot validation and plan construction completed |
| `success_means` | Human-readable explanation of that restricted success |
| `execution: not_run` | No compiler, native program or engine execution by the planner |
| Compiler/tool/schema hashes | Exact bytes read, without claiming the compiler is executable or the engine exists |
| Source hash | Canonical hash of the companion and declared source-file hash map, matching the mod build snapshot convention |
| Binding hash | Hash of the declared binding data; engine compatibility remains unchecked |
| `artifact_sha256: null` | No generated artifact is established by this operation |
| `raw_logs: []`, `measurements: []` | No execution logs or performance measurements are fabricated |
| `plan` | Versioned `beryl.mod.workflow` data described below |
| `plan_sha256` | SHA256 of compact, sorted-key, ASCII-escaped JSON encoding of `plan` |

The operation ID changes on repeated calls; the plan payload and its fingerprint
remain identical when the project location and all relevant input bytes are
unchanged. Relocating a project changes its absolute command arguments and
therefore its plan identity, while the source-content fingerprint is separate.

The plan contains:

1. Project/addon identity, declared binding version, and explicit source sets.
2. Every captured input's path, hash, byte length and source role.
3. Export summaries with source/name/constructor, method count and companion JSON
   pointer. Method declarations remain in the identified companion rather than
   being duplicated throughout the plan.
4. Expected artifact location templates and an explicit statement that this
   operation produced none of them. Existing artifact presence is not inspected.
5. Capability requirements distinguishing structural validation performed now
   from compiler/tool/runtime availability and source admission not checked.
6. Stage dependencies, structured argument templates, required values, expected
   outputs, non-execution state, evidence arrays and limitations.
7. Existing installed scenario definitions copied from the shared registry,
   with no selected scenario and no implied runtime evidence.

An action's arguments are typed data. A required argument is represented by a
`{"value": "parameter_name"}` reference. These are not shell fragments, a build
script or a ready-to-execute list. Consumers must select and validate required
parameters before explicitly invoking an operation. Backend choices are
`reference`, `native` or `differential`; artifact IDs must come from a successful
candidate build. Workbench paths come from trusted local configuration.

The optional installed-scenario template is deliberately conditional: a chosen
scenario's own typed parameters must be validated. For example, terrain
measurement additionally requires an explicit measurement plan. The template
does not automatically select defaults for every registered scenario.

## Stage behavior and unavailable work

| Stage | Current workflow behavior | Evidence from planning |
|---|---|---|
| Semantic check | Existing `mod check` checks native and Enfusion inputs and export signatures | None; `not_checked` |
| Native tests | Explicit selected backend and declared implementation/test inputs | None; unavailable when no tests are declared |
| Candidate build | Existing `mod build` repeats checks and generates a staged addon/source map/identity | None; no artifact generated |
| Workbench compile | Existing artifact-bound compile operation with explicit Workbench tooling | Engine/version/tool availability unverified |
| Installed scenario | Separately selected, typed installed fixture | No scenario selected or executed |
| Promotion | Existing explicit artifact and ownership/hash-guarded destination operation | Not authorized or performed by planning |

Version-2 descriptions, tablet lifecycle/button/prefab generation, project
gameplay scenarios, dedicated-server/two-client acceptance, visual interaction
acceptance, and broader resource/component/prefab/layout/import/packing authoring
are explicitly unavailable within this v1 workflow. Existing small engine
fixtures do not close any of those gates.

The recorded promotion dependency reflects the current tool's compile-receipt
requirement. It does not claim compile-only acceptance is enough to ship a mod;
the separate runtime, multiplayer and visual gates remain visible as incomplete.

## Validation, bounds and stale inputs

The shared `description_snapshot` helper now supplies both the read-only planner
and the existing Job snapshot writer. It validates the same published schema,
case-conflicting source paths, duplicate source roles, native/test overlap,
missing input files and addon self-dependencies. Companion paths now use the
same linked-path rejection as source paths. The planner additionally invokes
the existing pure export-flag validation, which checks the written receiver
prefix. Only the compiler can establish declaration identity, signature validity,
visibility and export-name conflicts.

Planning bounds are 16 MiB per input, 64 MiB total captured bytes and 3 MiB of
canonical plan JSON. Exceeding a plan-only bound reports `unavailable` and does
not reject the project as invalid Beryl. Existing check/build source-set limits
are unchanged. MCP retains its independent framing/output limits.

The planner re-reads all input hashes, compiler bytes, tool identity and schema
identity before returning. A detected change reports `stale_input`; it cannot
return success with the first snapshot as though that snapshot were current.
This is a bounded copied-byte snapshot with a recheck, not an atomic filesystem
transaction, ongoing monitor, directory ownership verification or ACL audit.
Consumers must discard a plan when the described inputs or tools change.

Malformed JSON, duplicate/unknown fields, unsupported version, missing input and
inapplicable CLI options produce structured failure diagnostics and repair
guidance. Plan failures do not refer to nonexistent retained compiler logs.

## Implementation and verification

Changed consumers:

- `tools/beryl-mod/mod.py`: shared structural snapshot, workflow data and plan
  dispatch, leaving ordinary semantic checks in the existing compiler path.
- `tools/beryl-mod/mcp_server.py`: additive plan operation, same typed command
  dispatch, and validation of plan identity/non-execution claims.
- `scripts/verify-mod-plan.py`: focused guard, failure, stale-input and CLI/MCP
  parity fixtures with separate receipts.

Run the focused verifier against an explicitly selected candidate compiler:

```text
python -I -B scripts/verify-mod-plan.py --beryl <candidate-compiler>
```

The test replaces Job creation, subprocess APIs and writable file APIs with
failure sentinels while planning a real PID companion. It also checks deliberately
invalid Beryl source and non-executable compiler bytes to establish that planning
does not quietly invoke semantic or execution checks. Negative cases include
malformed/unknown/v2 descriptions, duplicate/case-conflicting paths, absent
inputs, unsupported options, absent tests, changed source/tool fingerprints,
resource limits and altered MCP response identities or execution claims.

The same test compares direct tool output, the real C dispatcher and the real
local stdio MCP adapter. Existing `scripts/verify-mod.py` remains the regression
gate for the shared snapshot extraction and ordinary mod operations. Its
synthetic engine receipts test promotion policy and are not engine evidence.

Completion means those bounded interfaces and regressions pass. It does not
complete the wider P6 AI usability trials, install the optional tool revision,
release tablet authoring, or establish any optimization/performance advantage.
