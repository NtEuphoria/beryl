# P5 scalar tablet engine replay and component compilation

October 8, 2026. Experimental evidence, not completion of the tablet feature.

The unchanged Beryl lifecycle protocol now executes in the installed Enfusion
VM against the complete 92-case scripted corpus. A separately generated scalar
component compiles after a confirmed construction defect was repaired. Actual
engine callback delivery and tablet-service integration remain open.

## What executed

`scripts/verify-tablet-engine-replay.py` builds a strict version-1 isolated addon
from `packages/sparkos/tablet-lifecycle-prototype/src/lifecycle.be`. It obtains
the state, operation, field, function and module-holder names from the compiler's
actual linkage metadata. The trusted replay code is a separate fixture file;
the generated implementation and original immutable artifact are not edited.

The independent original-source decision oracle and Python protocol model first
agree on the ordered service observations. Their operation transcripts then
provide fixed inputs and expected states to the actual generated EnforceScript
`next` function. Each invocation owns its own operation object. Nested scripted
operations share the same persistent state, retaining the original ordering.

The engine run checks six observations after every call: opcode, state mode,
operation program counter, screen program counter, returned answer and telemetry
accumulator. It completes **92 cases / 572 calls / 3,432 checks**. The engine
returns the complete ordered case list; missing, extra, reordered or failed
cases invalidate the comparison. The exact staged handler contains the expected
case identities and artifact-specific request token.

This is a numeric comparison. Decimal literals use nine significant digits to
retain admitted binary32 constants. The engine compares floats numerically;
its exact bit encoding has not been verified. In particular, positive and
negative zero remain indistinguishable in this engine comparison. The earlier
reference/native bit observations retain their separate scope.

The engine receives scripted service replies. It does not open the real tablet,
construct widgets, invoke input polling, bind a render target, deliver gameplay
callbacks, reproduce spontaneous engine reentry, or establish multiplayer
authority. Passing this corpus does not verify those contracts.

## Compilation defect and repair

The first scalar signature fixture had no base-game dependency. Workbench could
not obtain its base configurations and timed out. A new companion-based
candidate explicitly includes the verified base-game GUID `58D0FB3206B6F859`.
The old artifact and failed receipt remain intact.

Actual compilation of that candidate then rejected the generator's
zero-argument component constructor: `Overloaded function 'SPK_AdmissionFixture'
not compatible`. This was a generator defect; prior synthetic renderer tests
had not established the native component construction contract.

The current renderer initializes the retained state member directly:

```text
protected ref <compiler-published-state-class> m_BerylState = new <state-class>();
```

It emits no custom component constructor. The existing state default constructor
is preserved, and native component construction remains the engine's responsibility.
The initializer has an explicit `component_initializer` source origin pointing
to the state declaration and companion JSON pointer. Callback order and direct
member passing remain unchanged. The corrected addon compiled successfully in
Workbench with zero reported script errors.

No runtime allocation or component lifecycle claim follows from compilation.
Plain-script state initialization, persistence and replacement now have the
separate member-box execution evidence below. Engine-owned component construction
and engine-delivered lifecycle still need their own execution probe.

## Evidence integrity and engine ownership

Both verifiers explicitly select the configured PowerShell 7 executable with
`-NoProfile -File`; they do not change execution policy. Windows PowerShell 5
and PowerShell 7 reported different configured policies. The historical
PowerShell 5 rejection remains failed evidence.

Execution uses the existing Workbench compile and scenario transports, their
session mutex, exact engine identity and installed plugin fingerprints. Runtime
starts a new owned session, checks the loaded project and exact handler token,
and stops only the owned process. Compilation and VM execution remain distinct
stages. Raw logs and actual subprocess receipts are retained.

Original artifacts, generated files, companion inputs, compiler, tools and
fixture files are checked against frozen hashes. Staging verifies copied bytes
against the manifest before adding the trusted handler. Unknown staged output
fails the gate. Workbench's observed root `resourceDatabase.rdb` is admitted
only as a bounded derived output when absent from the original input manifest;
its bytes and hash are recorded separately. It cannot exempt a modified input
or a similarly named file elsewhere.

## Current receipts

Paths below are relative to the Beryl workspace. Immutable receipts carry exact
compiler, source, tool, engine and plugin identities and retained log paths.

| Receipt | Meaning |
|---|---|
| `build/component-engine-4hgouqgc/result.json` | Failed original no-dependency fixture; engine timeout plus the older harness's unrecognized derived cache |
| `build/tablet-engine-replay-eqys37pe/result.json` | Failed replay harness: too many EnforceScript local variables; generated lifecycle Game source was not the reported error |
| `build/tablet-engine-replay-rw96a39q/result.json` | Complete engine numeric replay passed, with the original protocol bytes |
| `build/tablet-engine-replay-gaqdgxi3/result.json` | Current corrected-tool replay: all 92 cases / 572 calls / 3,432 checks; explicit raw adapter receipts and `runtime_result` |
| `build/component-engine-trhcjksa/result.json` | Confirmed generated component constructor error; staged source integrity passed |
| `build/component-engine-znhfskb6/result.json` | Corrected retained-member initializer compiled successfully; runtime not selected |
| `build/component-generation-oh20d8x8/result.json` | Corrected pure renderer: 110/110 cases |
| `build/component workflow & spaces-2lm9kltf/results.json` | Corrected workflow: 10 groups, including private installed CLI/MCP agreement |
| `build/map-diagnostics-yyracx66/result.json` | Six mapping groups, including the new initializer origin |
| `build/staged inputs & spaces-l69wjzpo/results.json` | 42/42 inert source-integrity faults |
| `build/component-engine-inert-hev82j36/result.json` | Twenty inert selection/cache-output integrity cases |
| `build/component state & spaces-8bsbnxd1/results.json` | Failed detached-component experiment: native component constructor is private; no callback execution |
| `build/component state & spaces-c5e_g7gl/results.json` | Plain-script member box: 11 cases / 73 checks / 95 ordered rows passed; generated component compilation only |
| `build/receiver-argument-order-bi6_dbc7/result.json` | Three actual plain-script receiver/argument observations; left-to-right arguments, receiver selected afterward |
| `build/receiver-harness-faults-qw364umm/result.json` | Thirteen inert malformed-response/finalization cases; no engine execution |
| `build/tablet service & spaces-_wtl2u2m/results.json` | Isolated Beryl-driven tablet with preserved MESH Game consumers compiles; actual services and gameplay not executed |

The first replay harness used a new local integer for every call and exceeded
the engine's observed 64-local limit in long cases. The corrected harness reuses
one integer and caps operation-local declarations below that limit. No Beryl
logic was altered to make those cases pass. The failed receipt is preserved.

The first successful replay used the pre-repair tool bundle because it contains
no generated component. Its outer `runtime` scope flag obscured the response
dictionary, although the actual raw adapter receipt was retained. The later
`gaqdgxi3` run uses the corrected tool bundle and additive `runtime_result` and
`raw_result_receipts` fields. Both passed; they represent different source/tool
checkpoints and neither old receipt is rewritten.

## State and receiver observations

The native `ScriptComponent` constructor is private. The failed detached-
construction experiment is retained; it cannot establish engine-owned state or
callback delivery. A separate ordinary script object contains a retained member
initialized with the compiler-emitted state class. In the actual engine, its
11 cases verify nonzero defaults, field write-through, whole-record replacement,
reset, repeated manual frame-handler calls, independent objects, ordinary
initialization/deletion handlers and nested mutation. Its 73 checks produce
95 ordered rows plus a checksum. The generated component in that addon compiles
but is not instantiated. Plain-object evidence is not component-lifecycle evidence.

The receiver probe executes three bounded ordinary-script expressions on the
exact engine bytes. Arguments execute left to right, and a method invoked on a
mutable member uses the member's value after argument evaluation. Consequently,
the tablet's existing `m_UI.SetKeybinds(input.GetKeybinds())` cannot be modeled
by capturing `m_UI` before `GetKeybinds()` completes. The service boundary must
retain invocation-local input and returned keybindings while resolving the UI
receiver at the original observation point. This observation establishes no
widget lifetime, actual service reentry, gameplay authority or general language
conformance contract.

## Next gates

1. Obtain components from an actual owned prefab/world. Record engine-delivered
   initialization, FRAME callbacks and deletion. A direct callback call or
   structural prefab audit cannot substitute for that evidence.
2. Implement the synchronous service boundary in
   [P5_TABLET_SERVICE_ADAPTER_CONTRACT.md](P5_TABLET_SERVICE_ADAPTER_CONTRACT.md).
   Exactly one layer must own superclass calls and FRAME registration: directly
   combining the generic wrapper with protocol opcodes would duplicate them.
   The [experimental service candidate](P5_TABLET_SERVICE_CANDIDATE.md) now
   implements and compiles that boundary; actual service equivalence remains open.
3. Extend the bounded receiver observation to actual tablet-service behavior;
   verify UI/screen retention, queued work,
   teardown and authoritative/local-owner behavior before candidate integration.
4. Complete properties, UI event, prefab, host, dedicated-client and visual
   acceptance before promotion. Public v2 verification/promotion remains unavailable.

The live MESH project and active compiler/tool installation were not replaced.
No performance or Rust-superiority claim is supported by these correctness checks.
