# P4-A: bounded component contract admission

Status: structure and resolved-signature validator implemented, 2026-10-08.
This is the first component admission boundary. It does not generate a component,
port the tablet, verify callback bodies or establish engine runtime correctness.
CLI/MCP integration passed in the integration owner's separately captured
private checkpoint below. No live installation was activated.

## Implemented profile

The profile is `enfusion.tablet.script-component.v1`, selected in a strict
version-2 companion's `binding.contract_profile`. The binding also requires the
exact declared engine version and SHA-256:

```text
version: 1.8.0.13
sha256: 7dd36ca1f662b0c13669a4f2f7f10e3c461c2906b021e742272d64b3ab7e9798
```

Matching the catalog means a matching declaration, not a local executable probe
or a live Workbench session. A different declared identity reports stale input;
an unknown contract profile reports unavailable.

The version-2 schema preserves v1's common name, addon, sources, exports and
definitions. V1 files and validation remain unchanged. V2 adds 1–16 components
with separate descriptor/instance names and parents, a qualified state symbol,
and exactly three callback mappings:

| Callback | Required superclass order | Beryl handler signature |
|---|---|---|
| `ScriptComponent.OnPostInit` | `first` | Public ordinary function taking only `inout State`, returning void |
| `ScriptComponent.EOnFrame` | `none` | Public ordinary function taking `inout State`, then `let f32`, returning void |
| `ScriptComponent.OnDelete` | `last` | Public ordinary function taking only `inout State`, returning void |

The descriptor parent must be ScriptComponentClass; the instance parent must be
ScriptComponent. The order constraint is reviewed MESH source order, not an
engine-mandated universal convention. In particular the original frame callback
does not call its superclass. A declaration of that order in a companion does
not prove that a handler performs the existing marker/telemetry work correctly.

Callback functions must have no receiver, generics, self parameter or default
arguments. Parameter names may differ. The first parameter resolves to the exact
selected state declaration; another module's identically spelled State cannot
substitute for it. The state itself must be a public record. Its nested records
may be private when their exact declaration identities exist in the same checked
context. Scalar leaves are limited to bool, signed i32 and f32. Arrays,
containers, strings, option/error payloads, engine references and unresolved
types are outside this profile. Every visited record must carry explicit empty
compiler `generic_parameters` metadata; absent/nonempty metadata is unavailable.

Duplicate component/export production names, engine-base name conflicts,
duplicate export sources and duplicate method export names/sources fail
validation. Unknown callbacks, missing/duplicate required callbacks, wrong
parents and wrong orders identify the responsible companion JSON pointer.
Gadgets, properties, resources, prefabs, UI, scenarios and generation are not
admitted fields in this profile.

## Catalog evidence and trust boundary

The source-controlled
[`tablet-component-contracts.v1.json`](../../tools/beryl-mod/tablet-component-contracts.v1.json)
separates three kinds of evidence:

1. Exact installed ScriptComponent declarations and their API document hash.
2. The current MESH tablet's reviewed superclass/callback order and source hash.
3. Unknown lifetime, authority, reentrancy and callback-delivery contracts, with
   runtime evidence explicitly `not_run` and generation `unavailable`.

Its source evidence comes from the preserved
[October recovery capture](../../build/tablet-recovery-1ae28bbb58d4499d808b467a390b6fc1/source-evidence.json).
The catalog is selected by installed tooling, never by a project-supplied path,
script or code string. The validator pins the exact catalog bytes and canonical
content. Changing that evidence requires a deliberate validator/catalog revision
and fresh installation identity; a file containing modified claims is rejected.
That pin establishes catalog integrity, not the truth of unexecuted contracts.

The catalog's raw SHA-256 is
`a48c7764b4e6cd47ee35001872f638e01edcbf764053d843d0d30cfb370b58b4`.
The previous binding extraction registry is not silently promoted into a complete
engine type/lifetime system by this additional profile.

## Module API and integration responsibilities

[`component_contracts.py`](../../tools/beryl-mod/component_contracts.py) exposes:

| API | Contract |
|---|---|
| `ContractFailure(message, status, pointer)` | Accurate failure/unavailable/stale-input status and authored JSON pointer |
| `load_catalog(path, read, parse)` | Reads through caller helpers returning bytes/parsed JSON; validates the bounded exact source-controlled catalog |
| `validate_components(config, catalog)` | Non-executing structural admission, declaration/review origins and explicit unavailable stages |
| `validate_symbols(config, catalog, context)` | Signature admission from the caller's checked `context.project` envelope; no source execution |

Common companion fields must also pass the shared published schema and existing
path/source/export validation. This module does not replace those checks.
The integration owner runs both target checks, invokes compiler context for the
same captured inputs and verifies source/compiler identity before passing it
here. The module never launches the compiler, probes the engine or determines
whether an external snapshot is still current by itself.

Context declaration IDs are validated against the compiler's deterministic
`beryl.declaration.v1:<kind>:<qualified-name>` SHA-256 contract. Type references
resolve through exact qualified declaration entries and IDs; short type names
are never used as a fallback. Missing/failed context envelopes, mismatched IDs
and incomplete declarations cannot masquerade as a successful signature check.

Results include component JSON-pointer origins, extracted declarations,
source-order review and compiler/source fingerprints when supplied. Source
locations preserve byte coordinates and omit duplicated full source text. Null
origins remain null. Summaries stay bounded, serializable and non-executing.

Structural planning leaves symbols and target admission `not_checked`.
Successful signature validation still leaves generation/promotion unavailable,
runtime verification `not_run` and handler body/lifecycle `not_verified`.
The context format does not prove function body correctness. The integration
checkpoint adds explicit struct-generic metadata; older contexts missing it are
rejected for state admission. Unresolved/non-plain field types are rejected; a
passed signature must not be reported as verified lifecycle behavior.

## Resource limits

| Limit | Bound |
|---|---|
| Catalog input | 64 KiB; exact revision required |
| Components | 1–16 |
| Callbacks per component | Exactly three, once each |
| State nesting | Eight record levels |
| Fields per record | 64 |
| Expanded logical state fields | 256; shared record declarations count for every value occurrence |
| Compiler declarations | 4,096 |
| Parsed context traversal | 100,000 nodes, depth 32, 16 MiB text accounting |
| Individual context strings | 65,536 characters |
| JSON protocol integers | At most 64 bits; booleans remain distinct |
| Returned summary | 1 MiB canonical JSON |

Recursive state graphs are rejected. Memoized traversal retains both expanded
field count and depth, preventing repeated nested declarations from bypassing
either limit. These are admission budgets, not measured engine allocation costs
or permanent language limits.

## Verification and fixture

[`verify-component-contracts.py`](../../scripts/verify-component-contracts.py)
passed **102/102 cases, zero skips** in
[`component-contracts-7oa1_1hb/result.json`](../../build/component-contracts-7oa1_1hb/result.json).
Receipt SHA-256:
`c683533788f573acf88b81d17a1b83f8ab05c1b8958726210928ea39829276ec`.
Its captured inputs remained unchanged. The suite runs Python validation only:
no compiler, Beryl program, generated executable or engine was executed.
The earlier [97-case receipt](../../build/component-contracts-bx51kwpq/result.json)
is retained as history. It predates the mandatory nongeneric record metadata
check and the additional Unicode/integer protocol limits; it does not cover the
final module revision.

Coverage includes v1 compatibility, strict-v2 fields, stale identities, catalog
tampering, duplicate exports/components, callback order/signature failures,
qualified type identity, nested private records, cycles, depth/width/expanded
field limits and incomplete context envelopes. The synthetic contexts test this
protocol; real CLI/MCP context results require their own integration receipts.
Invalid Unicode and oversized integers fail through structured diagnostics;
they do not escape as an unexpected Python encoding/conversion exception.

[`packages/sparkos/tablet-admission`](../../packages/sparkos/tablet-admission/README.md)
contains a plain public state and three deliberately empty callback fixtures for
real compiler signature checks. They do not implement the tablet. Passing their
admission is not a lifecycle port, engine compile, live input test or MESH release.

## Integrated CLI/MCP checkpoint

The final private ordinary compiler is SHA-256
`61f3510b2d6024c22d0a21abf972df33f0e6e16d3e68d921103b581c3864828a`.
Its compiler/runtime source capture is
[`oct08-component-candidate-zw_cydzb/snapshot.json`](../../build/oct08-component-candidate-zw_cydzb/snapshot.json).
The separate UBSan unit-only gate passed 567 cases / 10,512 checks; this does
not close generated-native-program or engine acceptance.

[`verify-component-workflow.py`](../../scripts/verify-component-workflow.py)
passed 10 groups in
[`component workflow & spaces-8_ss5s7j/results.json`](../../build/component%20workflow%20%26%20spaces-8_ss5s7j/results.json),
receipt SHA-256
`11c3363b0638db164bf45fc96ef6bc1081d0f5d933d16d3d9203628ff122b489`.
It uses real compiler semantic checks and resolved context, tests invalid
signatures, structural and identity failures, non-executing planning, unavailable
generation/promotion and strict v1 compatibility. Valid-shaped context with
the wrong compiler/source identity fails instead of certifying a signature.

The private 24-file bundle is
`547acaea69d7d5065a8e7d107495f815dff723e4f61855b6868790cb62414d75`.
The fixture exercised actual hardened 21-to-24-file migration, retained prior
bytes and the same CLI/MCP result contract beside that private compiler. Neither
the active `build/beryl.exe` nor its optional bundle was changed.

The first workflow fixture failure is retained at
[`component workflow & spaces-f3ww6wor/results.json`](../../build/component%20workflow%20%26%20spaces-f3ww6wor/results.json).
Its injected mutation occurred between the native and Enfusion source reads,
before the captured final bytes, so the planner correctly accepted that captured
input. The corrected fixture mutates after both reads and verifies stale-input
rejection. The corrected run has its own receipt; no failed attempt was erased.

`mod plan` checks structure without executing compiler analysis and reports
symbol/target admission `not_checked`. `mod check` checks both source targets,
requires the exact context compiler/source fingerprint and then admits signatures.
V2 `build`, `verify`, scenarios and `promote` remain unavailable. The validation
summary explicitly leaves runtime `not_run` and lifecycle `not_verified`.

## Next dependency

Implement the bounded descriptor/instance generator and plain tablet logic in
an isolated candidate, using the checked source/signature boundary. Compare original and
generated ordered service calls, returns and persistent state before expanding
to the gadget, inherited properties, map-mode fragment or prefab.

The [recovery packet](P4_TABLET_RECOVERY_2026_10_08.md) remains the behavioral and
resource inventory. It records queued UI teardown questions, unreviewed screen
bindings, property enum gaps and dedicated-client/visual gates. This admission
layer closes none of those executed acceptance gates by itself.
