# P6 checkpoint: local MCP over the shared CLI

Date: 2026-09-07. State: bounded experimental adapter implemented and verified
against the combined compiler. This is not completion of P6, the tablet authoring
workflow, an LSP server, or actual Claude/ChatGPT usability trials.

## Inputs and independent checks

Compiler SHA-256:
`7a7c5883c23a6a0d65cf236760f3b39ed188e3fc75f70ff74fde7965dcb74214`.

The complete protocol/CLI/installed-bridge receipt is
`build/mcp & spaces-7won19za/results.json`, SHA-256
`3802a50f5be3d62edd32baf4226b463becc2efa27f4b02bf32b78f357584025d`.
It passed all **17 required groups**, including **five actual compiler groups**.
No partial prefix or empty selection closes this gate.

The installed 21-file bundle in that test has identity
`b8ea292c71237a27c938ea162f5a58ba52d49a7680a786bdec25017482db3730`.
The isolated installation copied this compiler and used the real C `mcp` command,
inherited pipes, the hash-validating installed loader, Python server and actual
context/snapshot analysis. This was not merely an in-process protocol simulation.

The verifier's initial attempt incorrectly wrote LF fixture text through Windows
text-mode newline conversion. The compiler correctly rejected the mismatched
hash. That failed receipt remains under `build/mcp & spaces-53qhb09q`; the corrected
fixture writes the declared UTF-8 bytes exactly.

One symbolic-link creation subcheck was unavailable because Windows denied the
privilege. Hardlink rejection passed. This limitation is retained in the receipt,
not counted as a successful symlink probe.

## Implementation boundary

`src/driver/mcp_driver.c` selects an explicitly configured trusted Python executable
and the installed `beryl-tools/mcp.py`. It forwards standard input/output directly
through the existing owned-process abstraction. Ordinary compilation still needs
neither Python nor a model service. The default transport opens no listening port.

`tools/beryl-mod/mcp_server.py` provides protocol and workflow adaptation only.
It invokes the existing CLI with an explicit argument vector, preserves the
returned semantic result, and adds process outcome, input identity and raw log
locations. It does not implement another parser, resolver, type checker or engine
bridge. Exact analysis is delegated to `src/driver/analyze.c`.

The standard-library implementation follows the project's dependency policy.
Its admitted MCP subset is version `2025-11-25`: initialize/initialized, ping,
tool listing/calling and cancellation. It supports standard request metadata and
omitted arguments for tools whose schema admits an empty object. Unknown tool
arguments are errors. It does not advertise transports, resources, subscriptions,
sampling, prompts, tasks or other protocol capabilities it has not implemented.
See the official [stdio transport](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports)
and [tool schema](https://modelcontextprotocol.io/specification/2025-11-25/server/tools).

The same six tools and their exact JSON schemas are returned to every client:

| Tool | Behavior |
|---|---|
| `beryl_context` | Project, capability, example, symbol, binding and optimization context |
| `beryl_doctor` | Inventory; explicit optional native readiness probe |
| `beryl_analyze` | Complete exact request plus every supplied content file |
| `beryl_test` | Explicit native/reference/differential test execution |
| `beryl_mod` | Check, build, installed scenario discovery and artifact verification |
| `beryl_evidence` | Bounded JSON receipt/source-map inspection and its hash |

Execution and context lookup remain distinct. Compiler/Python/Workbench locations
belong to launch configuration; tool arguments cannot select executable commands,
shell code or project hooks. Engine verification requires the launcher's installed
Workbench tool directory. Absence returns unavailable without attempting execution.
Promotion remains the separate existing CLI operation and is not exposed here.

## Snapshot and result contract

The analyzer tool receives the exact version-1 C request and a map from each
`content_file` basename to its supplied UTF-8 string. It validates safe names,
duplicates, completeness and byte budgets, writes a unique request directory,
and invokes `beryl analyze --request`. Logical source paths are never opened as
fallback input. The C analyzer independently validates metadata and hashes.

A successful response must carry the requested operation and the selected compiler
identity. Analysis additionally requires the staged request fingerprint, exact
request ID, snapshot version, source descriptors and target. Numeric descriptor
fields require actual integers; booleans cannot masquerade as zero or one.
Missing, forged or mismatched success envelopes produce `invalid_response`.

The adapter returns identical `structuredContent` and serialized text content.
The nested CLI result preserves its existing fields and outcome distinctions.
Native test text remains text with its CLI exit status; it is not converted into
an invented semantic receipt. Reading evidence exposes its hash and leaves its
authorship, applicability and external claims unverified.

Clients must still discard a result after their document version or source snapshot
changes. Byte offsets are not UTF-16 editor positions. Persistent/incremental
analysis and actual editor stale-response handling remain future gates.

## Resource and lifecycle behavior

- One active operation per server; overlapping calls report busy. Ping and
  cancellation stay responsive.
- At most 12 MiB per incoming or fully encoded outgoing protocol frame, JSON
  depth 64 and 262,144 decoded values; 4 MiB per captured stdout/stderr stream.
- At most 4,096 request IDs per session. Request IDs retain exact JSON type;
  boolean cancellation IDs cannot match integer requests.
- Default timeout 120 seconds. The trusted launcher can choose 0.05–1800 seconds.
- C analysis additionally enforces its own stricter request/source budgets.
- Per-operation logs and receipts remain under `.beryl-mcp/jobs/`. There is no
  automatic cleanup of earlier evidence and no claim of a whole-project disk quota.

Oversized streams or encoded responses fail explicitly. The server does not return
a truncated successful diagnostic set. Deep malformed receipt JSON fails without
leaving the session permanently busy. Unexpected worker errors also release the
operation slot.

Cancellation is checked before publication under the operation lock. A cancelled
request cannot later publish a successful adapter receipt/response. Completed
generation side effects are not rolled back by cancelling; promotion retains its
separate ownership and expected-hash gates.

Windows children start suspended, are assigned to a private job and then resume.
Attached descendants are killed on cancellation or host death. The precise
remaining pre-assignment limitation is recorded in
[P6_PROCESS_OWNERSHIP.md](P6_PROCESS_OWNERSHIP.md). No unrelated process or editor is
stopped by the adapter. POSIX behavior remains an unexecuted platform gate on this
Windows checkpoint.

## Verification and rollout

The full verifier checks real CLI context/doctor/snapshot parity, native readiness,
explicit reference tests, real isolated installation, invalid paths and types,
duplicate keys, metadata, fabricated success identities, malformed/deep receipts,
stream/encoded-frame limits, busy handling, exact cancellation IDs, timeouts and
owned descendant cleanup with an unrelated process surviving.

Independent reviews found and corrected optional-argument compatibility, boolean
ID equality, malformed-receipt worker recovery, missing success identities and
pre-attachment process execution. The installer also rejects a damaged existing
bundle manifest before changing its active pointer. New trusted loaders suppress
bytecode-cache writes inside immutable version directories.

The client-neutral instructions live in [AI_WORKFLOW.md](../AI_WORKFLOW.md).
Install only the exact verified compiler/bundle combination, preserve prior
compiler and loader/active-pointer bytes, and retain the receipt index. No client
configuration file or live MESH file was changed by these adapter tests.

Remaining P6 work includes a complete nonexecuting mod workflow planner, broader
binding/context capabilities and actual separate Claude/ChatGPT task trials.
Property/event/prefab authoring requires the still-unfinished version-2 companion
and tablet generation gates. This adapter does not close those dependencies.
