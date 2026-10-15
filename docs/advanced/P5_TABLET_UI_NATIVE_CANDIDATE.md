# P5: UI opening, native frames, and destruction candidate

Historical pre-restart checkpoint: 2026-10-10 local time. Its source-only status
is superseded by [complete post-restart UI/frame/destruction execution](P5_TABLET_POST_RESTART_EXECUTION.md).
The original identities, bounds, prepared fixtures and unexecuted statements
below describe that earlier checkpoint; they are not current runtime status.

The preceding [native service checkpoint](P5_TABLET_NATIVE_SERVICE_EXECUTION.md)
passed all seven N1a cases in Enfusion. This packet covers the distinct N1b/N3
candidate. It does not claim successful UI opening, player interaction, native
destruction, rendered output, multiplayer, or a released Beryl capability.

## What is ready

The eight-file experimental package is
[tablet-ui-native-probe](../../packages/sparkos/tablet-ui-native-probe/contract.json).
Its selected-source fingerprint is
`9004a4aa2ce9acc7102b5687f39f6bd04750a1a443d598a2fa816fa19740984f`.
The candidate starts from the recorded N0 tablet source preparation, preserving
its generated Beryl lifecycle logic and captured MESH services. It replaces the
isolated addon identity and adds reversible observation hooks plus the new
fixture resources and RPC handler. It contains 99 admitted files.

The latest [source-preparation receipt](../../build/tablet-ui-native-rx5evy6x/results.json)
is successful. It stages an isolated candidate and fingerprints inputs;
it launches no host or engine.

The root verifier is [verify-tablet-ui-native.py](../../scripts/verify-tablet-ui-native.py).
The engine adapter is [tablet-ui-native-engine.ps1](../../scripts/tablet-ui-native-engine.ps1).
The companion contract explicitly marks this fixture experimental and unreleased.
Live MESH, the installed compiler, and the active tool pointer were not promoted.

## Supporting evidence and its limits

| Gate | Receipt | Scope |
|---|---|---|
| Observation/instrumentation source gate | [43/43](../../build/tablet-ui-native-source-2m60q8ny/result.json) | Source patterns and reversible hooks; no native callbacks |
| RPC driver source gate | [67/67](../../build/tablet-ui-native-runtime-source-pxf9x_jn/result.json) | Source admission and bounded protocol; no RPC execution |
| Independent UI/state oracle | [78/78](../../build/tablet-ui-oracle-5131d18b5cde49f4a1525c925d35fb0f/result.json) | Synthetic analytical trace and deliberate faults |
| Final Python receipt validators | [64/64](../../build/ui-runner-passive-9a186c19b9c94a529d8eb97b964253ca/result.json) | Two valid fixtures and 62 rejected faults; no host |
| Final readiness-guard audit | [14/14](../../build/ui-readiness-guard-passive-40ab6288e5b442a185b3bf0e31036c92/result.json) | Pinned API, marker, budgets, and execution ordering checked from source |
| PowerShell UI receipt fixtures | [Prepared inputs](../../build/oct11-ui-verifier-inert-fixtures.json) | Not executed; not a passing PowerShell gate |
| Exact candidate | [Source preparation](../../build/tablet-ui-native-rx5evy6x/results.json) | Source-only success; neither compilation nor gameplay |

These counts must not be added together as executed engine cases. The oracle is
specified from the preserved original component, UI, and screen implementations;
it does not import the generated lifecycle evaluator as its expected-value source.

## Seven public actions and native observations

Only the first of two native owners receives these actions; the second remains
STOWED for independence checks.

| Action | Operation |
|---|---|
| 0: held | SetHeld(true) |
| 1: focus | Focus() |
| 2: repeated focus | Focus() |
| 3: unfocus | Unfocus() |
| 4: reopen | Focus() |
| 5: stow | SetHeld(false) |
| 6: focused before teardown | SetHeld(true), then Focus() |

Calls delegate to actual services. A successful Open may expose a degraded
interface without a map. A failed actual Open leaves the tablet HELD and cannot
be changed into a successful opening by the harness.

The observer records native OnPostInit, EOnFrame, and OnDelete. It does not invoke
those callbacks directly. Focused-frame observations preserve the original
marker update, binary32 time accumulator, single refresh at the 0.25 threshold,
reset to zero, and accumulator persistence across close/reopen.

Two separate natural-progress windows follow focus and reopen. Each requires at
least 600 ms of host wall time, actual selected-owner focused frames, and actual
deferred UI method observations. The existing ReportRootSize and RefreshTerrain
queue timing remains intact. Window polling does not request mutation or force a
frame. Delivery records do not establish a per-enqueue FIFO or retention contract.

Switching the owned editor back to edit mode must deliver actual native deletion.
The trace requires Close when a UI exists, screen Destroy when a screen exists,
then the pre-superclass witness and a post-superclass witness using a captured
fixture token. No owner, UI, or component-state getter runs after superclass
destruction. Cross-owner deletion order is preserved as observed.

This proves ordered script calls only if the engine executes them. Script-null
state is not a proof that native widget, screen, or graphics storage was released.

## Harness repairs found by independent review

The retained negative fixtures exposed and closed these admission holes:

- Stage replies could previously be reordered or use inconsistent phase/status.
- Pre-spawn owner/init data and premature stop, deletion, frame, or focused state
  could be accepted.
- Natural-progress responses needed the same raw RPC, token, module, API,
  project, resource, game-world, and play identity as their surrounding stages.
- Mutating requests during an observation-only wait were not sufficiently rejected.
- Clock values needed signed-i64 bounds and mutually consistent wall/tick durations.
- Every nonempty callback snapshot needed validation as a complete callback prefix,
  rather than checking only the terminal trace.
- The startup inventory stage needed its actual label; it is not a mutation-stage
  read-lease observation.

Final fixtures pass against the corrected source. Earlier failed receipts remain
failed. An initial static readiness-audit assertion used incorrect positional
argument indices; its correction and scope are recorded in the final audit.

The adapter retains the reviewed predecessor's ownership, launch, listener,
lease, and cleanup functions. Natural progress is a separate ledger entry, not a
fabricated stage response. It allows only installed action names and fixed typed
parameters. There is no arbitrary project script, callback body, or shell text.

## Bounds and unresolved runtime gates

Trace source bounds are 12,288 main rows, 1,024 bytes per row, 2,048 frame
observations, 8,192 invocation records, and 64 queue records. Initialization
requires exactly four rows for the two owners. The raw RPC cap is
1 MiB and the receipt cap is 2 MiB. A larger source trace budget does not make
the transport capable of accepting an 8 MiB message.

Finite floating-point state is compared with the documented tolerance
max(1e-6, 1e-5 * max(abs(a), abs(b))). Rounded threshold ambiguity is unavailable,
not a reason to widen tolerance. This encoding is not bitwise binary32 evidence.

Natural frame activation is still unverified for this candidate. The earlier N0
driver explicitly activated its fixture; this new driver does not change entity
flags. If no frames arrive, inspect actual prefab/activity and game-world state
before changing the fixture. Do not substitute manually invoked frames.

The candidate deliberately omits the input/gadget component. Input OnPostInit can
register defaults and save bindings before its enabled-frame check. Real-player
tests therefore require an owned profile and actual native GetProfilePath
confirmation before spawning that component.

Player acceptance needs a real controlled entity, real gadget holder/manager,
superclass-before-local-owner ordering, and real activation. The WorldEditor
SwitchToGameMode boolean arguments describe debug/fullscreen behavior; they
cannot be treated as a player-creation switch. No player fixture has executed.

Visual behavior, real button clicks, native handler lifetime, complete teardown,
multiplayer, and promotion remain independent gates.

## Why execution stopped

The configured host later stopped returning even fixed literal output.
[Current host evidence](P6_HOST_STARTUP_RECURRENCE.md) records three bounded
timeouts, including a Windows PowerShell comparison. No UI engine job was started
through the new verifier.

The verifier now runs the pinned bounded readiness utility before either engine
job, requesting exact stdout, a 15-second main wait and a 5-second cleanup wait.
A timeout, unconfirmed exit, changed executable, missing marker, or incomplete
evidence stops the operation before compilation. The guard itself is source
audited; the final guarded runner has not been host-executed.

## Resumption order

1. Restore host availability and run one fresh pinned readiness probe.
2. Execute the prepared inert PowerShell UI receipt cases and retain a new receipt.
3. Run the exact UI candidate's headless compilation. Repair actual engine errors
   without changing preserved fixtures.
4. Execute the seven public actions, both natural-progress windows, and native stop/
   destruction. Retain ordered traces and raw logs.
5. Establish owned profile isolation and construct the real player/gadget fixture.
6. Run player, multiplayer, visual, and lifetime gates separately before promotion.

Source-only reproduction:

```text
python -X utf8 scripts/verify-tablet-ui-native.py --package-sha256 9004a4aa2ce9acc7102b5687f39f6bd04750a1a443d598a2fa816fa19740984f
```

Adding --run requests the readiness guard, isolated compilation, and engine
execution. Do not use it repeatedly while the fixed host probe still fails.

## Final byte identities

| Input | SHA-256 |
|---|---|
| scripts/verify-tablet-ui-native.py | `2db01b4486c41188cff32dcde1fee42472fd84a3760724b1fd9a7d95d4d2097d` |
| scripts/tablet-ui-native-engine.ps1 | `1946ef58a63eb4c2fd246bdbb456413b622b781eab8ec4cd02751f1706fa709b` |
| scripts/verify-host-readiness.py | `0067128fa4754d582a3930415ec77991773475d936b204e3be560f4d9928e648` |
| build/tablet-ui-native-rx5evy6x/results.json | `c68a51df7ede4998142e507eaeb23fad4555573857158217455c0042a3e38745` |
| build/ui-runner-passive-9a186c19b9c94a529d8eb97b964253ca/result.json | `3115a530235222bf5d41337d42b03c6f304365bb8ff23a9dd3ffd8376aba2fcd` |
| build/ui-readiness-guard-passive-40ab6288e5b442a185b3bf0e31036c92/result.json | `e726e371173e3c65813f950238050b89f27d07dd7657d008fa65ea20ba20edbe` |

The [final passive preservation audit](../../build/oct11-final-preservation-passive-69e4f82137514cec8cfa9df7b8994fed/result.json) rechecks all 107 compiler/runtime inputs, active/private installation identities, and 25 private tool payloads. All match their recorded hashes and sizes; there are no missing or extra source entries. This is preservation evidence, not a new compiler execution.
