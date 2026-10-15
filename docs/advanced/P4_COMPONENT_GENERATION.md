# P4-B — experimental scalar component wrapper generation

Checkpoint: October 8, 2026. This packet describes a bounded Python
transformation. It does not establish engine compilation, callback delivery,
tablet lifecycle parity, authority, multiplayer behavior, or a release.

## Objective and implementation boundary

Append a generic `ScriptComponentClass` descriptor and `ScriptComponent`
instance to compiler-generated EnforceScript using exact compiler linkage.
Beryl contains the state and ordinary handlers; the companion describes class
identities and callbacks. Neither an assistant nor the generator invents the
compiler's symbol encoding or edits generated output by hand.

The implementation lives in:

- `tools/beryl-mod/component_generation.py`: pure transformation, without file
  reads, writes, subprocesses, editor sessions, or model APIs.
- `scripts/verify-component-generation.py`: pure Python synthetic regressions
  and an immutable receipt in a new directory under `build/`.
- This packet: scope, admission, origins, evidence, and open gates.

C linkage production, integration into mod orchestration, source-map consumers,
installation, activation, real source fixtures, and engine verification were
separate obligations at the pure-renderer checkpoint. The subsequent integrated
source candidate below completes the source/tooling obligations; engine and live
release obligations stay open.

## API and input identity

```python
generate(config, catalog, context, summary, generated: bytes,
         mapping: dict, companion: dict) -> tuple[bytes, dict]
```

`companion` contains exactly `path` and `sha256`. The function raises
`component_contracts.ContractFailure` with a status and JSON pointer for
malformed, stale, unavailable, or incompatible inputs. It does not modify its
inputs on success or rejection.

The supplied admission summary must exactly equal a fresh
`component_contracts.validate_symbols(config, catalog, context)` result.
Structure admission and generation admission remain distinct: a nested plain
record can pass the former while generation remains unavailable.

The context and source map must contain the same ordered, canonical relative
source paths and SHA-256 fingerprints. Linkage declaration origins must equal
the resolved declaration spans after removing context-only `text` and
`column_unit` and adding the source map's actual `file_id`. Declaration
identities use the existing compiler identity contract.

The map must identify the exact UTF-8, LF-terminated `Beryl_Generated.c` bytes
and contain ordered complete-line mappings, the existing export inventory,
and `linkage_schema_version: 1`. Unsupported or missing linkage is unavailable;
there is no guessed-name fallback.

Metadata agreement is not a filesystem recheck. This API receives no original
source or companion bytes. Its caller must freeze and recheck those bytes,
the compiler executable, the compiled artifact, and tool identities before
using or promoting a result. Changing input bytes requires a fresh operation.

## Exact linkage contract

Concrete struct linkage:

```json
{
  "declaration": "fixture.State",
  "kind": "struct",
  "source": {
    "path": "src/tablet.be", "file_id": 0,
    "byte_offset": 0, "byte_length": 20, "line": 1, "column": 1
  },
  "class": "ActualEmittedStorageName",
  "fields": [{"source": "ready", "name": "ActualEmittedFieldName"}]
}
```

Concrete free-function linkage replaces `class` and `fields` with the exact
`holder` and `method`. Receivers and generic linkage rows are outside this
generator's admission. Every supplied row must resolve to its matching
declaration kind and exact origin. Duplicate, malformed, and conflicting rows
fail instead of being ignored.

The generator inspects the actual generated type and member declarations.
The selected state must have the emitted no-argument default constructor and
the declared scalar fields. Each selected callback must be a static `void`
function with the emitted `out State` argument, and the frame handler adds a
read-only target `float` argument. Field and function names are taken from
linkage and verified against these declarations.

The flattened export inventory must match the companion's class, constructor,
and method mappings in order. Methods are scoped to their receiver classes:
two classes may export `Read`, and an unrelated generated component may also
be named `Read`. Only actual top-level classes and enums reserve global names.
An exported constructor facade does not replace the Beryl storage class;
state storage follows the compiler's exact struct linkage.

## Admitted state and wrapper behavior

Generation admits one to sixteen components under the installed
`enfusion.tablet.script-component.v1` profile. Each component has exactly the
three reviewed callback selections and a public, nongeneric, flat state record
whose fields are `bool`, signed `i32`, or `f32`.

Nested records, arrays, owning containers, engine references inside ordinary
state, arbitrary inheritance, project-provided code strings, and additional
callbacks are not generation capabilities of this packet. The broader
structure checker remains unchanged.

Each generated component owns one protected `ref` state member, initialized
directly with the emitted state's default constructor. The wrapper leaves native
component construction to the engine and emits no custom component constructor.
Handlers receive that same member directly. The wrapper introduces no mirrored
state, callback-time state allocation, or `BerylCopy` call.

Callback order is fixed by the profile:

1. `OnPostInit(IEntity owner)` invokes the superclass, calls the Beryl init
   handler, then requests `EntityEvent.FRAME` through
   `SetEventMask(owner, EntityEvent.FRAME)`.
2. `EOnFrame(IEntity owner, float timeSlice)` calls the frame handler with the
   state member and `timeSlice`; it introduces no superclass frame call.
3. `OnDelete(IEntity owner)` calls the deletion handler, then the superclass.

Requesting frame events follows the retained source order. It is not proof
that an installed engine delivered the callback or that repeated lifecycle
operations are correct. The current signatures pass no `owner` to Beryl;
engine-object and reviewed-service boundaries require their separate contracts.

The profile's `tablet` name refers to the existing source-reviewed callback
order. These wrappers are a generic scalar component fixture, not a migration
of `SPK_TabletComponent`, its gadget, input owner, UI, screen, or prefab.

## Bounds, naming, and compatibility

Input and output metadata, and generated source bytes, are individually bounded
to 16 MiB. JSON traversal, identifier length, token count, source coordinate
representation, and generated brace depth have additional explicit limits.
The component count remains at most sixteen.

Engine class names are checked case-insensitively against reserved engine
identities, language keywords, compiler-reserved names, every detected existing
top-level class/enum, and the other new component identities. Existing member
and linkage identities must also be consistent. Comments and string contents
do not introduce top-level declarations into the collision inventory.

The original generated byte prefix and source-map associations are preserved.
No old output is overwritten in the module. The caller receives a new byte
sequence and map, and promotion remains an independent hash-checked operation.
Already component-expanded maps are rejected instead of expanded a second time.

The supplied summary remains signature-admission evidence. The map's additive
`component_generation` record reports `generated_experimental`, the flat scalar
subset, input context/companion identity, component count, and explicit
`not_run` engine/runtime fields. It retains the catalog's unknown contracts.

## Source origins

Each nonblank appended line has exactly one complete-line mapping. Offsets and
line numbers begin after the unchanged prefix. Existing sources and their
ordered file IDs remain unchanged; companion identity is carried separately.

New kinds are `component_descriptor`, `component_state`,
`component_initializer`, `component_callback`, `component_superclass`,
`component_handler`, and `component_event_mask`.

State and initializer lines use the state declaration's exact origin and
`/components/i/state`. Callback, superclass, handler, and event-mask lines use
the selected handler's origin and `/components/i/callbacks/j/handler`.

Descriptor and instance identity lines have no invented Beryl declaration span.
Their `original` and `declaration` are null. Their companion records point to
the exact scalar class name and include `identity_kind: "engine_class"` and
`expected_value`. Consumers must validate that pointer against the frozen
companion and may report its JSON location without inventing source columns.

## Historical synthetic verification evidence before engine compilation

The original renderer below emitted a zero-argument component constructor.
Actual engine compilation subsequently rejected that constructor; the current
renderer uses member initialization. The receipts below retain their original
scope and bytes, and do not validate the corrected renderer. See the October
engine continuation in the delivery state for current receipts and open gates.

The final pure-Python attempt at this checkpoint passed **110/110** cases:

- Receipt: `build/component-generation-shwjuh24/result.json`.
- Receipt SHA-256:
  `cad8b4661287e48bd83bf8cd75ad5e3b3e0607d489dbf005925ae39b8544109a`.
- Generator SHA-256:
  `8e1aa104c2a4e711feb5cf7a3e2b185c53a285179145303b76474ae023897c6d`.
- Verifier SHA-256:
  `dfeaec2c5eb34b267a4d47018a4a33db36f31546d27a46efdc8878af6731a429`.
- Synthetic single-component output: 1,348 bytes; 26 appended nonblank line
  origins; output SHA-256
  `3e6e0ca616a56ca85eaffdf24edaa541ca070a75d235d9a385ce011c18a30ac7`.

Positive cases independently inspect prefix preservation, deterministic output,
no input mutation, state allocation/calls, callback/event-mask order, exact
origins, sixteen independent component states, constructor-facade storage, and
scoped exported method names. Negative cases exercise profile strings, summary
and source identities, generated byte/hash tampering, linkage kinds/names/spans,
fields, signatures, source ranges, metadata bounds, prior expansion, component
collisions, and nested state rejection. Malformed metadata on unrelated supplied
linkage declarations also produces structured contract failures rather than
uncaught Python exceptions.

The verifier registers the deterministic planned case identities before
execution, rejects duplicate planned identities, and requires the completed
IDs to equal that complete ordered set. Missing or duplicate execution cannot
manufacture a successful receipt. Existing mapping association fields are
required explicitly rather than defaulted from malformed input.

Previous attempts remain immutable:

- `build/component-generation-_vd4gd6p/result.json`: 95/97, failure. The harness
  placed summary recomputation outside its expected-rejection handler for two
  reserved engine base-class cases. SHA-256
  `dcb436ad73a761569de4d2e5bcfcb1e0133b6b93cb075e0a9efb16dfaf1b3f27`.
- `build/component-generation-nqo0xlg4/result.json`: 100/100 before the scoped
  export/facade positives and root review correction. SHA-256
  `c9c74eb32e479001a5d19c8d3cef42255df96e452ccce4571cc1d79093e60cbf`.
- `build/component-generation-ars1foyp/result.json`: 102/102 after scoped export
  handling and facade checks, before the extra malformed-metadata regressions.
  SHA-256
  `2f56f76dfa5fde6ec927055fb313b7a687d9b12fcedac6562fee6c9a2132f226`.
- `build/component-generation-5a6zmbkh/result.json`: 106/106 before the peer
  review completeness correction. Its expected case set was derived from
  executed records, so this attempt does not establish missing/duplicate-case
  detection. SHA-256
  `d251c7fe64d9047beb88f8070803371cd8ba15a1509f97b660e2a453a0771204`.

These receipts executed Python validation only. They contain no compiler
execution, native program execution, engine compilation, runtime comparison,
real mod installation, or promotion evidence.

## Integration and release obligations

1. Build the changed C emitter and verify actual linkage/schema output,
   declaration origins, module holders, exported state/facade names, and fields.
2. Generate wrappers from exact compiler context and staged source sets; retain
   original and expanded generated source/maps and their identities.
3. Extend source-map consumers to validate engine-class companion origins and
   map deliberate engine errors without inventing original spans.
4. Recheck source/companion/compiler/tool identities at the candidate boundary;
   verify ordinary version-1 compatibility and nonexecuting plan behavior.
5. Compile the exact candidate in an owned, identified Workbench job when that
   capability is available. Do not turn synthetic policy receipts into engine
   success.
6. Establish callback delivery, event registration, superclass ordering,
   state/lifetime validity, repeated creation/destruction, reentrancy, world
   teardown, and authority with real runtime fixtures.
7. Introduce actual tablet engine services, properties, UI/event/prefab
   descriptions, lifecycle parity, multiplayer, visual, and authoring gates
   through their separate implementation packets.

No performance or Rust superiority claim follows from generating these
wrappers. No historical Windows 4551 native execution gate is closed by this
pure Python test. No live compiler activation or security setting was changed.

## Subsequent integrated source candidate

The ordinary private compiler at
`build/oct08-wrapper-cli-l8ci669v/beryl.exe` has SHA-256
`76aeaacfea6866e66e3020f983eaa22089d545ad0f3b60fedfd28c3d58972bd7`.
The compiler now emits the linkage records above using its actual type, field,
module-holder and function encoders. No second Python symbol encoder was added.

`mod check` retains declaration admission. Eligible v2 `mod build` now checks
both targets, obtains exact context, emits ordinary EnforceScript and its source
map, applies this renderer, and creates a content-addressed candidate artifact.
The descriptor, state member, initializer, callbacks, superclass calls and event
registration have verified line associations. Companion-only engine identities
map to JSON pointers without inventing a Beryl location. The compiler's original
record constructor/default body is preserved; source inspection is not an
independent numerical or engine-runtime proof of those defaults.

The source-map test passed eight groups against actual compiler output, including
exported constructor facades and same-module split-file functions. The diagnostic
test passed six groups using synthetic errors against real v1/v2 artifacts;
wrong companion kind/value/pointer origins fail. These are mapping tests, not an
engine compilation receipt.

Ten workflow groups check real source admission/generation, strict v1 behavior,
nonexecuting plans, guarded unavailable operations, exact context identities,
and private installed CLI/MCP agreement. The historical 24-file tool profile
was upgraded in a private fixture with backups; the new fixed 25-file profile
adds this renderer. Loader validation still admits only recognized exact payload
sets, preserves known old controls, and rejects unknown or corrupted siblings.
The active compiler/tool installation and live MESH remain unchanged.

Reviewed identity repair:

1. Snapshot writes must report the complete byte count and re-read exactly.
2. Frozen hashes identify both project originals and staged copies.
3. Every source-bearing job checks originals, copies, compiler and tool identity
   before and after returned compiler operations and before publication.
4. Component context uses the frozen hashes, rather than freshly trusting a
   potentially changed staged file.
5. Both companion versions require the compiler-emitted source map to identify
   those frozen Enfusion inputs. This also catches different loaded bytes even
   if a staged file is restored before the later filesystem check.

These checks do not make the filesystem immutable against arbitrary concurrent
actors. They establish the loaded-byte evidence and publication checks for this
bounded workflow; artifact reload/promotion retains its separate hash checks.
`scripts/verify-staged-inputs.py` exercises inert write, mutation and receipt
faults. Refer to the current delivery index for the final scoped count/hash.

The source checks and Python-renderer integration are implemented experimentally.
Public v2 engine verification, scenarios and promotion still return unavailable.
An isolated headless compile attempt failed at adapter startup: PowerShell
reported that running scripts is disabled. Workbench did not launch; no script
compile or callback result exists. The failed outer receipt and raw stderr are
retained at `build/oct08-wrapper-engine-n6bkh13_/result.json`. Its embedded Job
references an unpublished separate result file; the outer record/raw logs are
the available evidence. No synthetic replacement receipt is created.

The next engine packet must first compile the exact artifact, then exercise
actual callback delivery, frame registration, superclass ordering, member `out`
write-through and whole-record replacement. It must cover repeated lifecycles,
reentry and teardown. Only after those contracts pass can a reviewed tablet
service adapter use these language boundaries. Generation alone never closes
tablet, resource/property/UI/prefab, authority, deployment or performance gates.
