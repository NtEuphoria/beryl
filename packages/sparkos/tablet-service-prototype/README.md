# Experimental synchronous tablet service candidate

This package prepares an isolated replacement for the existing
`SPK_TabletComponent`, driven by the unchanged scalar continuation protocol in
`packages/sparkos/tablet-lifecycle-prototype/src/lifecycle.be`. It preserves the
descriptor, public getters, Focus/Unfocus/SetHeld, callback signatures, state
values, telemetry interval, and actual reviewed UI/input/screen calls. It is a
trusted adapter experiment, not released version-2 service generation.

Preparation has not itself established engine compilation or runtime equivalence.
The integration owner runs the verifier with an explicitly identified private
compiler. By default it checks/generates source and prepares a candidate. `--run`
additionally invokes the existing owned headless compilation bridge with an
explicit PowerShell host. It never executes gameplay, promotes files, or edits
live MESH. Successful compilation proves only that these exact scripts compile.

```text
python scripts/verify-tablet-service-candidate.py
  --beryl <private compiler under build>
  --expect-compiler-sha256 <exact SHA-256>
  --mesh-project <original SparkOS_Mesh source directory>
  --workbench-tools <existing reforger-workbench-plugin>
  --prepare-only
```

For headless compilation replace `--prepare-only` with `--run` and supply
`--powershell-host <configured host>` and `--engine-exe <exact Workbench executable>`.
No execution-policy switches are used. Missing/stale tooling, failed generation,
failed compilation, cancellation and timeout remain distinct receipt outcomes.

## Source and generated boundaries

The strict version-1 companion generates only the existing plain State/Operation
and `next` function. The generator resolves actual class/field/function names from
the emitted linkage and validates the direct `out State, out Operation, int`
signature. It discovers the generated script through the immutable artifact file
set plus source-map file hash/size, preserving its actual path and bytes. It does
not assume a script directory, repair emitted code or synthesize mangled names.

The candidate has a new addon ID/GUID and the captured base-game dependency. It
does not load the original MESH addon alongside duplicated classes. A frozen
56-script source profile admits exactly the reviewed installation. It retains all
56 originals outside production discovery, including the old tablet fixture.
Its candidate includes 54 Game scripts, replacing precisely the tablet source;
the two WorkbenchGameCommon test handlers are excluded. Six existing Game debug/
probe consumers are explicitly listed and retained without execution claims.
Four `.claude-flow` JSON metadata paths are explicitly ignored and never staged.
No models, prefabs, materials, resource closure or world is assembled here.

The source inventory finds one original production class and rejects a tablet
subclass/modded extension, external `m_fTelemetryAccum`/`SyncScreen`, and projected
`m_eState` references. The frozen lexical inventory retains exact line matches.
Other unqualified `m_eState` occurrences are separate health, laser and warhead
fields. This is bounded source review, not general type-resolved compatibility.
The original protected state fields and SyncScreen helper are replaced by private
generated scalar state/protocol; compatibility with external subclasses is not
claimed. Public interfaces and service-reference identity remain preserved.

## Synchronous order and allocation policy

One persistent `ref State` stores mode/accumulator. Every synchronous entry creates
its own `ref Operation`; input, keybinding result and reply are invocation-local.
Nested entries share state but cannot overwrite an outer operation's continuation.
There is no state-copy/writeback transaction or component-wide active operation.

Each yielded service executes immediately before resuming `next`. UI.Open precedes
input lookup/hookup; failed Open retains UI and nested state changes. Opcode 6 calls
GetKeybinds using the captured input. Opcode 7 reads the current `m_UI` afterward,
as required by the separately retained receiver/argument-order engine probe.
SetInput does not reuse a receiver captured for the entire operation. Screen
Enable reads GetOwner at its original call point and ignores the bool result.
Focused stow preserves Close at FOCUSED, HELD/Enable, then STOWED/Disable.

Frame checks once, calls markers, then adds the finite binary32 timestep to the
shared accumulator. It resets to zero before one telemetry call at `>=0.25`.
It adds no catch-up, remainder, nonpositive-time guard, reopen reset, second UI/
state guard, or superclass frame call. UI/screen references are not cleared by
the adapter's deletion path, and existing deferred work is not cancelled.

One trusted layer owns superclass calls and FRAME registration. The actual
OnPostInit override calls superclass first; protocol opcode 14 subsequently
acknowledges that completed call, then opcode 15 commits STOWED before one mask
registration. Initial next at pc0 changes only the private invocation PC, so the
acknowledgment movement adds no intervening state/service observation.

OnDelete drives Close then Destroy and requires opcode 19 at pc5. The pinned pc5
continuation finishes only the private Operation before actual superclass
teardown. That move has no state/service effects or checked source failure, and
avoids accessing Beryl State after teardown. Unexpected opcodes/phases are logged
and refused, not guessed or serviced twice. Source/hash admission is essential;
an altered protocol needs a new review. The finite operation budgets are 32 steps
for ordinary entries and 16 for deletion, above the pinned protocol's paths;
they do not bound a reentrant engine stack.

Admission uses `resource_adequate_exact`: persistent State and per-invocation
Operation allocations are additional costs. This packet claims neither identical
out-of-memory behavior nor a performance improvement. No continuation reuse or
pooling is attempted before its retention/reentry contract is verified.

## Evidence and remaining acceptance

The verifier retains compiler/tool/plugin/host/Python fingerprints, exact original
MESH and protocol bytes, source-build job receipts, immutable artifact, generated
source map/linkage, staged file and directory sets, adapter template line origins,
raw compile receipt and engine logs. Engine binaries use streamed fingerprints.
Only an engine-created root `resourceDatabase.rdb` of at most 8 MiB is allowed as
a separate derived output. All source/gproj/generated bytes remain exact.

Adapter origins map every nonblank emitted line to its exact trusted template
line. They do not guess original Beryl/engine source columns or label hand-authored
adapter service expressions as compiler-generated language spans. The original
language source-map sidecar stays untouched.

Runtime acceptance remains not run: matched original/adapter service-entry and
state traces, engine-delivered callbacks, valid-owner/teardown conditions,
reentrant real services, close/reopen queued work, widget and handler lifetime,
screen binding, gadget/local-owner behavior, prefab/resource closure, host play,
dedicated clients, visual interaction, and paid allocation/performance costs.
There is no synthetic runtime case receipt in the compile-only workflow.
