# P5 experimental tablet service candidate

October 8, 2026. The isolated Beryl-driven tablet candidate compiles in
Workbench. Its services and gameplay lifecycle have not yet been executed.
This packet records implementation progress, not completion of P5 or R2.

## Implemented boundary

`packages/sparkos/tablet-service-prototype/tablet-service.c.in` is a trusted
experimental service seam. It retains the existing `SPK_TabletComponent` class,
descriptor, enum, public methods, UI reference and screen reference. The state
decisions come from the unchanged Beryl lifecycle protocol. The adapter dispatches
its yielded requests to the existing MESH UI, input, keybinding and screen APIs.

`scripts/verify-tablet-service-candidate.py` uses the actual private compiler and
strict version-one scalar companion to produce that protocol. It resolves emitted
class, field, module-holder and method names from the compiler's linkage table.
The generated file is selected through its unique manifest/source-map digest and
byte count, not an assumed directory or a second name mangler.

The existing MESH source profile contains 56 `.c` files. The candidate includes
all 54 Game scripts, replaces exactly the tablet source, and appends the untouched
generated lifecycle source. The two WorkbenchGameCommon handlers are excluded
explicitly. Six existing Game debug/probe sources remain inventoried consumers.
Four `.claude-flow` JSON state files are identified as non-source data and are
not copied. Prefabs, models, materials, layouts and other resources are not
assembled by this experiment.

A new addon ID/GUID prevents the candidate from replacing the live project.
It declares the existing base-game dependency `58D0FB3206B6F859`. There is exactly
one production `SPK_TabletComponent` definition in the staged source set.

## Lifecycle ordering and state

Each synchronous invocation has its own `Operation`, reply, input reference and
keybinding reference. The component retains one shared scalar `State`. No copied
state is written back after a service call, so a nested invocation does not get
silently overwritten by an older local snapshot.

The ordinary dispatcher preserves the protocol's admitted ordering:

- Focus checks HELD, constructs/opens the UI, connects input and keybindings,
  commits FOCUSED, then updates screen state.
- Failed opening leaves the state as the original continuation observes it;
  it does not restore a pre-reentry snapshot.
- Unfocus closes before committing HELD. Stowing preserves its intermediate
  HELD screen update before STOWED and disabling.
- Frame handling checks the focus/UI gate once, updates markers, adds the
  binary32 timestep, then resets to zero and refreshes telemetry once at `>=0.25`.
  Close/reopen does not reset the accumulator.
- Screen enable's Boolean result remains ignored as in the original source.
- Missing-input diagnostics retain the existing message and severity.

The original nested expression `m_UI.SetKeybinds(input.GetKeybinds())` requires
care. The exact installed engine's three-case ordinary-script observation
selects the receiver after left-to-right argument evaluation. Accordingly, the
adapter obtains keybindings from the invocation-local input and resolves the
current UI member when servicing the subsequent setter. It does not capture
the UI before the getter. Actual service reentry and retention still need tests.

Exactly one layer owns superclass hooks and FRAME registration. The adapter
does not combine the generic component wrapper with those protocol effects:

1. `OnPostInit` invokes the actual superclass first. It privately acknowledges
   opcode 14, runs the Beryl state reset, and registers FRAME exactly once at
   opcode 15.
2. `OnDelete` closes the UI, destroys the screen, reaches opcode 19, and finishes
   its known invocation-local continuation before invoking the superclass last.
   No Beryl state is accessed afterward.

That final continuation only changes the private operation fields; it introduces
no service call or persistent state write. The unchanged, admitted protocol is
pinned before allowing this policy. Unexpected opcodes, phases or exhausted
internal step budgets emit an explicit diagnostic; they do not invent a service
or silently claim equivalence outside that domain.

The source inventory found no tablet subclass, external telemetry-field consumer
or external `SyncScreen` consumer in the admitted 56 files. This is a bounded
lexical/source review, not compatibility with unknown third-party extensions.

## Evidence and integrity

The successful actual compilation receipt is:

`build/tablet service & spaces-_wtl2u2m/results.json`

It retains the raw `engine-compile.json`, process logs, engine logs, original
MESH inputs, fixture inputs, immutable scalar artifact, source-build job, generated
source map, adapter map and exact staged file/directory sets. Workbench reported
zero script errors and zero warnings. Its executable is version 1.8.0.13,
SHA-256 `7dd36ca1f662b0c13669a4f2f7f10e3c461c2906b021e742272d64b3ab7e9798`.

The unchanged Beryl lifecycle source is SHA-256
`34c2b848e94a7a68132804d08a58fcf31d644f2d0e9eb2b4973e84a39249f792`.
The private compiler remains SHA-256
`76aeaacfea6866e66e3020f983eaa22089d545ad0f3b60fedfd28c3d58972bd7`.
The optional tool bundle is
`dc4627fdf5cdc53b70777579fc4879619900b00b15a773a47651d3ad9677344d`.
These identities do not certify the different active installation.

The preparation-only receipt
`build/tablet service & spaces-1yid__er/results.json` precedes the additive
compile-attempt classification repair; it did not execute the engine. The
seven inert checks in `build/tablet-service-evidence-faults-wr5j05bd/result.json`
cover failed compilation despite exit zero, successful compilation, nonzero
error count despite nominal success, unavailable startup, timeout, absent receipt
and a Boolean schema version. They are harness checks, not service-semantic tests.

Writes are checked and reread. Before/after guards verify original and retained
sources, compiler/tools, plugin set, original artifact, source-build job,
generated bytes and staged output. The only admitted new source-tree output is
the separately recorded, regular root `resourceDatabase.rdb`, bounded to 8 MiB.
It cannot exempt a modified input or an unexpected nested file.

The adapter's sidecar maps exact generated lines to the trusted template.
Columns and automatic associations from adapter statements to original Beryl or
engine statements remain unavailable; the packet does not claim full public
source-map support for this experimental seam.

## Reproduction and admission

Use the explicitly identified private compiler, original readonly MESH project
and installed plugin paths:

```text
python scripts/verify-tablet-service-candidate.py
    --beryl <private-compiler>
    --expect-compiler-sha256 <exact-hash>
    --mesh-project <captured-MESH-source-project>
    --workbench-tools <installed-plugin>
    --prepare-only
```

Add `--run --powershell-host <configured-host> --engine-exe <exact-Workbench>`
for isolated headless script compilation. This does not run gameplay. The
configured PowerShell host is selected without execution-policy overrides.
The source profile is deliberately pinned; a source change needs a new reviewed
baseline and receipt. No retained generated output is manually corrected.

The resource policy is `resource_adequate_exact`: persistent scalar state plus
one new operation object per invocation. Those allocations are additional paid
costs, including frame invocations that immediately return while stowed. No
performance improvement is claimed, and pooling/reuse is not admitted
before the reentry and lifetime contracts justify it.

## Open acceptance gates

Compilation establishes compatibility of the staged service calls and consumers.
It does not establish invocation, results, timing, retention or gameplay behavior.

Next work must verify engine-owned component callbacks, then original/generated
tablet traces through actual opening, degraded UI, input/keybindings, equip,
focus, stow, screen synchronization, repeated instances and destruction. Queued
UI work, handlers, screen resources and world teardown need separate lifetime
evidence. Gadget local-owner behavior, death/respawn, join-in-progress and dedicated
clients remain required deployment gates.

The candidate has no resource closure, prefab/UI/event authoring acceptance,
visual acceptance, multiplayer acceptance, public version-two verification,
promotion or optimization release. Live MESH and the active compiler/tool pointer
remain unchanged. Read the [service contract](P5_TABLET_SERVICE_ADAPTER_CONTRACT.md)
and [engine replay packet](P5_TABLET_ENGINE_REPLAY.md) before extending this boundary.
