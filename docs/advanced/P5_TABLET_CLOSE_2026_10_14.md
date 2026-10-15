# P5: ordinary tablet closing — October 14, 2026

This work follows the [actual repaired activation](P5_TABLET_ACTIVATION_2026_10_14.md#actual-repaired-activation-passes), with exact frozen baseline `player-tablet-activation-control-20261014-v4c` (`abfc0591e9a2ed63fac7d53902ace0535e67344e7b95dccd55dc42ac69de1df5`). Its actual 25-RPC result verifies the engine activation flag and focused/open/root UI after a genuine callback. The input-free fixture remains intentional.

The next candidate adds a separate, bounded toggle-off record. It preserves the sealed activation record, waits until a subsequent genuine FRAME, rechecks current ownership, inventory membership, held identity and open state, then issues one ordinary `manager.ToggleHeldGadget(false)`. A separate callback window records genuine callback entry/return around the unchanged production superclass invocation. A later FRAME observes the resulting state. No direct UI close, state setter, manually invoked callback or action retry substitutes for the ordinary path.

The proposed acceptance requires a completed false callback, engine flag off, tablet STOWED, retained UI closed/root absent and the same owned gadget still IN_HAND. Tablet lifecycle STOWED is distinct from physical inventory stow. A complete negative observation remains negative. Missing or interrupted observations cannot satisfy acceptance.

## Evidence at preparation

- [Native source checks](../../build/oct14-toggle-off-native-source-tests.json): 48/48, SHA-256 `8ff0b90f1de20373879d60b99824e8cdadf0896d66b24c879b8530f1c57f8cb9`. These cover exact prior-source restoration, sequencing, guarded action and deliberate source mutations; they are not Enforce execution.
- [Python metadata/trace checks](../../build/oct14-toggle-off-python-tests.json): 64/64, `1bf48234322a6d68d16599bd977ec6b10bc30c938d9cf3deb0bbeb01e4d347b7`. Activation context comes from the actual successful baseline; every added off record remains synthetic.

- [PowerShell metadata/trace checks](../../build/oct14-toggle-off-powershell-tests.json): 64/64, `b034925c5305cdfa0e03b8f08fb9c7c75d470333e28b7f1e43e15ce4596234be`.
- Complete exchange checks: [Python](../../build/oct14-toggle-off-ledger-python-tests.json) 26/26, `70e99c141404fd163b5306a498d3c3f7b79a74178a50637ca6cc8b0b34ddc5fa`; [actual PowerShell continuation with inert queued RPCs](../../build/oct14-toggle-off-ledger-powershell-tests.json) 26/26, `47698bc441372991e81742553ba6ac3130660466dfcd85fdf54769f9dd248169`. Added toggle-off records are synthetic. Tests reject rewritten sealed records, missing or duplicate polls, over-limit waits, incomplete callbacks and closed-state mismatches.
- Raw diagnostic policy checks: [Python](../../build/oct14-toggle-off-diagnostic-python-tests.json) 21/21 and [PowerShell](../../build/oct14-toggle-off-diagnostic-powershell-tests.json) 15/15. The exact new profile admits the existing input-free fixture diagnostic only with the preserved earlier activation proof; a foreign profile and unrelated errors still fail. Later closing does not rewrite the earlier open-UI evidence.
- [Integration source checks](../../build/oct14-toggle-off-integration-tests.json): 171/171, `6c7199a0c47b6e736868261b07a8fc978a55bb0760c19790f57cebe096cf1184`. These check exact source restoration, helper identities, wire coverage, poll bounds and the narrow diagnostic policy.

At that preparation checkpoint, final source admission, engine compilation and actual toggle-off execution were pending. The synthetic checks alone did not establish closing success. The subsequent real result follows.

## Actual ordinary close passes

The exact frozen candidate `player-tablet-toggle-off-control-20261014-v1` has SHA-256 `54946c886b385721f337ce87e7e254128026da00525fef90ee40b4a57ca4cd5e`: 144 local members, 91 external inputs, 96 staged addon sources and 102 read leases. The [post-freeze guard](../../build/oct14-toggle-off-freeze-tests.json) passes 11/11, receipt `642f76e74861efd183ec56116b914043ba14689b2ebc1db6f85f669c0e895b9f`. No source changed after freezing.

Preparation: [tmzbdhga](../../build/game-profile-token-preparation-tmzbdhga/results.json), `5ae65283c82c36c885384a62ec636aa8b5dce05f7d71bd1a5faf32ec64650e10`. Source-only admission: [sggyk__b](../../build/tablet-owned-profile-run-sggyk__b/results.json), `8a028295e74ea236a52bc6634ae00389107ecad1214d04ce50f422682a4fad3c`.

The [actual owned result](../../build/tablet-owned-profile-run-1ibnd_83/results.json), SHA-256 `eb2c979ae5b9ebbed692b9ba2ba142f45ba9c05e96eb0965cb67298f67c2bf47`, passes host readiness, script compilation and runtime. All 27 RPCs reconstruct through the independent Python ledger verifier. Both `activation_verified` and `toggle_off_verified` are true; protocol success alone was not used as close acceptance.

Observed sequence and state:

- The ordinary activation has a completed true callback, `E1T;R1;`, and its own sealed FOCUSED/open/root UI observation. Its missing map remains an admitted degraded state.
- After fresh guards, the candidate makes exactly one ordinary `ToggleHeldGadget(false)` request. Its separate genuine callback trace is `E1F;R1;`, without overflow or an unmatched callback.
- Toggle-off FRAME 2 completes all three groups. The same owned inventory entity and component remain the held gadget in `IN_HAND`.
- The engine activation flag is false. The tablet lifecycle is STOWED. The retained UI object is closed; its root and map are absent.
- Both launched processes exit with code 0 and confirmed exit. Cleanup and evidence-error lists are empty. Compile and runtime job durations are retained, not interpreted as performance measurements.

The [compact actual summary](../../build/oct14-toggle-off-actual-summary.json) is `154c352ef07c3cea61f5d3adef48fa0a61a1a61ea54d31e5879febc66357bd65`. The [complete actual exchange](../../build/oct14-toggle-off-actual-ledger.json) is `3c00d9b25078c1f95b0079686a41ba5780a52c6d58111093d819becd60768dcb`. The fixture's exact missing-input diagnostic remains retained in its three raw log views and is classified using the immutable earlier activation proof. No unrelated error is ignored.

The [protected source/artifact audit](../../build/tablet-post-restart-preservation-krzqbvcy/result.json) passes for 107 sources, five installed artifacts and 25 private payloads, SHA-256 `8eaeeabf3f3fc7bbe3cbd9bde771353fc48ede48bb811d3b291fc651161bd193`. The [operator game-profile comparison](../../build/operator-game-profile-preservation-nxv0bwrs/result.json) confirms all 1,293 recorded files unchanged, SHA-256 `6fc3bc8891ad9483d343d28fd6b523d9ed8d43f010a19eaef71077920b188234`. The runner separately verifies its protected Workbench profile. Nothing is promoted into live MESH.

Some inherited descriptive scope strings in the experimental wrapper still mention the earlier single activation action. The exact new profile, hashed source, full exchange and separate `scope.toggle_off` / `toggle_off_observation` fields define this run's added off coverage. Correct those descriptions in a future version; do not rewrite this frozen receipt.

## Separate remaining cases

The initial record observes state, not screen enabled state or ordered Close/Enable/Disable service calls. Those need their own receipts. Physical stow additionally waits for genuine controller/animation completion. Direct stow while active must be tested separately from off-then-stow. Focused destruction must run with the UI open; deleting an already closed tablet cannot establish that behavior. Deferred work, input bindings, physical clicks, visual review, multiplayer and promotion remain independent gates.
