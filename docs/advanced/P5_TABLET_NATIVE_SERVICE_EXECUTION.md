# P5: native tablet service execution

Date: 2026-10-10. N1a status: **seven native service cases passed**.

This extends the [real-services admission packet](P5_TABLET_REAL_SERVICES_ADMISSION.md).
It is an isolated experimental fixture, not an installed scenario or a live MESH promotion.

## Executed evidence

The [successful native receipt](../../build/tablet-real-services-native-l5vg6pfu/results.json)
has SHA-256 `853fd68b9f65d457d5afd2b25949aa9bd217bd148fe803caa270b9bfa9c592b1`.
The exact 99-file candidate compiled with Workbench 1.8.0.13 in 6.5 seconds:
zero script errors and 19 existing warnings. Both direct host jobs exited zero.
Three compile logs and three runtime logs are retained.

The owned runtime finished in 18,703 ms. Native prefab creation produced two
distinct owners and four ordered initialization witnesses. The seven fixed
public cases produced nine service events and 44 ordered wire rows, 3,257 bytes
including LF delimiters. Main checksum: `490107`; initialization checksum: `326887`.
The independently specified original-source oracle agreed with the complete
state, identity, action and service trace. Both actual screen Enable calls returned
true. Those results establish observed script-service behavior, not native binding
correctness or rendered pixels.

| Case | Actual public operation |
|---|---|
| `n1a.focus-refused.stowed` | Focus refused from STOWED |
| `n1a.held.first` | SetHeld(true), actual screen creation and Enable |
| `n1a.held.repeated` | SetHeld(true), repeated Enable with the same screen |
| `n1a.unfocus-refused.held` | Unfocus refused from HELD |
| `n1a.stow` | SetHeld(false), actual Disable |
| `n1a.stow.repeated` | Repeated SetHeld(false), actual Disable |
| `n1a.independent-state` | Read-only observation of both owners |

The receipt includes ten RPCs, 34 session checks and 13 listener checks.
All 104 pinned-file read leases were acquired, hashed while held and released.
Eight fast namespace checks, the held full check and the post-release full check
passed. A fresh phase-4 edit-mode response preserved the complete pre-stop scalar
trace and initialization prefix. The owned process was stopped with confirmed
exit; cleanup and evidence-error collections are empty.

The source package fingerprint is
`2090471aec3b85555b27b194db11530c83852f157932dbceec6072da8a0c1310`.
Its [source preparation](../../build/tablet-real-services-preparation-_m7kt0ut/results.json)
has SHA `c156a6d97e08e6933997440117ddb9c39806cd044f3bac14414a8fd7ad90f2d9`.
The driver combines the scalar encoder and RPC in the 99th candidate source.
Live MESH and compiler installation are not modified by either operation.

## Confirmed repairs and preserved failures

1. The first [native-candidate compilation](../../build/tablet-real-services-native-do_01f22/results.json)
   failed at generated line 173: `event` is an EnforceScript keyword. The encoder
   parameter was renamed to `serviceEvent`; literal `|event|` wire fields remain
   unchanged. Original source and checker bytes are retained under
   `build/n1-encoder-reserved-repair-993b1xcv/`.
2. The [next compilation](../../build/tablet-real-services-native-8f4tie25/results.json)
   found `Formula too complex` at row construction lines 169, 189 and 237.
   Short sequential concatenations now produce the exact same fields. The checker
   reconstructs their expressions and compares all 44 rows and four initialization
   rows against the independent codec. Earlier bytes remain in
   `build/n1-encoder-formula-repair-2erdqv96/`.
3. Before execution, the prior passing N0 evidence showed that
   `Workbench.GetCurrentGameProjectFile()` reports `./addons/data/ArmaReforger.gproj`
   in this context. The new driver checks that base-game identity separately.
   Addon identity is established by the strict loaded-project set, compiled token,
   candidate manifest and exact registered resource/world paths. An addon path
   was not substituted into the base-game getter contract.
4. Independent negative receipt fixtures showed that Python validation initially
   admitted inconsistent spawn/run status and phase. Every stage now requires its
   exact boundary: ready/0 for load and play, pending/2 for spawn and run,
   complete/4 for stop. Earlier failed checker receipts remain failures.

No service case ran in either failed compilation. Engine module cascade errors
are retained alongside the primary project diagnostics. Failed checker attempts
are preserved separately and are not counted as successful engine executions.

## Supporting checks

- [Encoder gate: 64/64](../../build/tablet-real-service-encoder-qafu4rh1/result.json),
  SHA `85a2e29f97d1af82cbbe373cfa661ec2db5908230891f66af47326b3ed2c4e14`.
- [RPC source gate: 61/61](../../build/tablet-real-services-runtime-source-92ia44g0/result.json),
  SHA `109e4203be0ed9e92d3dc41e0677cfd013517a46d339630a67e95e85f7b4b167`.
- [Transport receipt/source gate: 69/69](../../build/tablet-real-services-transport-30a9d35ae22c45639d253b921a13fbb9/result.json),
  SHA `541826ada92c705c49ed98c95e95550f354ad165e2f23fa326869fcadf53868d`.
- [Executed inert PowerShell gate: 78/78](../../build/tablet-real-services-host-audit-d038e362590c4aebb7f0301c98547c9b/result.json),
  SHA `3ba131620776b4dffdd28b7f1d6bfe0f0fb797f442ac41920e130edfc3d3a123`.
  This executes only allowlisted helper functions with scripted responses, not
  the engine, adapter entry, process inventory or process-stop paths.

The transport source audit checks 35 functions: 24 byte-identical predecessor
functions, four count-only changes and seven N1-specific changes. Startup identity
and owned cleanup retain the predecessor implementation. Numeric-zero text is
not a binary32 bit or signed-zero proof.

## Reproduction

The experimental source preparer and native runner are
[prepare-tablet-real-services.py](../../scripts/prepare-tablet-real-services.py),
[verify-tablet-real-services.py](../../scripts/verify-tablet-real-services.py) and
[tablet-real-services-engine.ps1](../../scripts/tablet-real-services-engine.ps1).
Run the preparer with the current full package fingerprint. Run the native verifier
with the new receipt path, its exact fingerprint, the same package fingerprint
and `--run`. A changed input requires new preparation; do not edit a retained
candidate or reuse its completion as evidence for changed bytes.

## Remaining gates

UI opening, focused native frames, close/reopen, queued UI work and actual native
destruction use a distinct N1b/N3 contract. The seven-case N1a contract deliberately
excludes UI references and focused state. Real player/gadget/input testing requires
verified profile isolation because native input initialization can save bindings.
Multiplayer, visual interaction, physical screen-resource release and promotion
remain separate gates. These N1a jobs completed normally. The subsequent
[UI/destruction candidate](P5_TABLET_UI_NATIVE_CANDIDATE.md) is source-prepared;
[current fixed-host startup failures](P6_HOST_STARTUP_RECURRENCE.md) prevent its
engine execution. The host root cause remains unexplained.
