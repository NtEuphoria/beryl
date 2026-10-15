# P5: ordinary tablet activation — October 14, 2026

## Scope and starting evidence

This isolated candidate extends the [successful held-gadget observation](P5_PLAYER_INVENTORY_2026_10_14.md#actual-held-observation-passes-inactive-tablet-no-ui-yet). That run observed the exact tablet as the player's held entity/component, with current membership and ownership, native IN_HAND, toggle off, tablet STOWED and UI absent. It made no activation request.

The activation fixture preserves the original insertion, callback inspection, equipment and held records. After their completion, a later genuine FRAME repeats current identity, ownership, membership, mode, toggle, tablet-state and input-free composition checks. It makes one ordinary `manager.ToggleHeldGadget(true)` request. There is no manual call to `OnToggleActive`, `Focus` or `SetHeld`.

An isolated `modded SPK_TabletGadgetComponent` wrapper observes genuine callback entry and return while forwarding the unchanged production method exactly once. It records bounded scalar tokens, states and ordering, without retaining extra engine references. After a completed true callback, a subsequent FRAME samples actual state and conditional UI presence/open/root/map facts. These are sequential observations, not a rendered-image or input test.

The receipt distinguishes:

- Protocol verification.
- The request returning.
- Genuine callback completion and trace integrity.
- Completion of the later state observation.
- Opening acceptance (`activation_verified`). A completed observation with no open UI is a measured negative.

Missing map attachment is recorded as degraded opening when the UI itself opens. The input-free prefab remains deliberate: keybinding initialization and its native persistence destination are separate admission gates. No production files or installed compiler artifacts are promoted.

## Harness checks

| Check | Result and retained receipt |
|---|---|
| Native source and deliberate faults | [38/38](../../build/oct14-activation-native-source-tests.json), SHA-256 `27d3ecf84d05c9c5690e024457f3b8263eea52d1cc0686396a4b518bc7b18904`. |
| Python metadata/trace validation | [98/98](../../build/oct14-activation-python-tests.json), `134df6918fa39c33890a2915bc5f1b2598521bee28e887f96898f631f43be026`. |
| Actual PowerShell metadata/trace validation | [98/98](../../build/oct14-activation-powershell-tests.json), `e94dc19046b8bc58793a0c7e09f9f0dc2c29eaf27491657a7246e051579fa95d`. |
| Python complete exchange | [31/31](../../build/oct14-activation-ledger-python-tests.json), `f374b87173a0e7b1e490411c4d6ead9769497a2b4c970c0f07c2d6e8087284cc`. |
| Actual PowerShell complete exchange | [31/31](../../build/oct14-activation-ledger-powershell-tests.json), `6d43c658aa3039223199e6d4f5a3317a3a6aa3a8ccecd908eb0bbc97861d2775`. |
| Exact parent-consumer restoration | [4/4](../../build/oct14-activation-checker-source-tests.json), `ce722de729544f161cb0b308960bf3c039d2ae153e5eb4b65dfdd834da6e143c`. |
| Initial integration | [103/103](../../build/oct14-activation-integration-source-tests.json), `751150907929b303b041d930a84e345aa0d880444d4a4cff934083455f2c10e9`. |
| Actual Python/PowerShell wire checks | [23/23 Python](../../build/oct14-activation-wire-python-tests.json), `27b07e91348cbeef9d5ff30240bffd369167fcc1c5c92ac45c35760b187add6b`; [23/23 PowerShell](../../build/oct14-activation-wire-powershell-tests.json), `b5454dc9a3cdbdc40d411f065ec97eb32b6cb9ceb65a5b88cbb711566b79a2f0`. |
| Dispatcher | [35/35](../../build/oct14-activation-dispatch-tests.json), `fe4f30dfc81ec26791084ea0c5d5f530fcf854f15d36d707812c5b7d8ec86e03`. |
| Resource identity | [22/22](../../build/oct14-activation-resource-tests.json), `04a1c81f2fff5a3f22ac17772332aaa6eb814deb635465ebac9a3b93d823078d`. |

Activation records added to exchange fixtures are synthetic; their underlying insertion/held records come from the retained actual run. The tests do not substitute for engine execution. Source review also tightened three initially permissive unavailable-result shapes: an unfinished post-read, an unfinished Toggle request and a premature callback timeout cannot be relabeled as a completed returned failure. Receiver/precondition checks are evidenced by the exact native source and its fault checks, not by independent raw identity values in the wire record.

## Confirmed compile failure and narrow repair

The first activation packet passed host readiness but failed script compilation before gameplay ran. The engine reported `Formula too complex` at `BerylGameProfileObserver.c:1592`, the newly added 19-predicate scalar prerequisite conjunction. The compiler also reported base-script errors; those were retained rather than repaired speculatively.

- [Failed execution receipt](../../build/tablet-owned-profile-run-__vwllrx/results.json): `2c6c502393e84e2c29afc8236cd5562b464b1542e9e2c4d1dfd6f97ffbd3e478`.
- [Compile diagnostics](../../build/tablet-owned-profile-run-__vwllrx/engine-compile.json).
- [Preserved raw compile logs](../../build/activation-compile-failure-logs-cdeba852ace94fdc8a830b1aef4ddf61/receipt.json): `e3e343ea947609d6339d18cbc39d85a1518256c4c47a0cbddea803b8f61446df`.
- [Unchanged failed control-v1 freeze](../../build/player-tablet-activation-control-20261014-v1/source-freeze.json): `587991fc807e796c632bb8b825fb995f75958084d35632e71943928f0e1da588`.

Native-v2 replaces only that conjunction with 19 ordered scalar rejection statements followed by `return true`. It preserves the predicate sequence, short-circuit result and all action/callback behavior. This establishes a repair for the observed expression; it does not establish a universal engine expression-length threshold.

- [Native-v2 freeze](../../build/player-tablet-activation-native-20261014-v2/source-freeze.json): `1f27cccc59ecdb55f7e75a188ad79dfcf44168a87b6720e6af35316efb42c17d`.
- [Native-v2 source checks](../../build/oct14-activation-native-v2-source-tests.json): 38/38, same outcome bytes as the original source suite.
- [Focused accessor checks](../../build/oct14-activation-accessor-v2-tests.json): 32/32, including all 524,288 Boolean predicate assignments and their short-circuit evaluation order; SHA-256 `16583c9018b0bae380d5a606916b59a924f821248416041f30526201b09b5b7e`.
- [Control-v2 integration checks](../../build/oct14-activation-v2-integration-source-tests.json): 106/106, `3d72c89b0bf9a3b342812211d7126e2fae5fe1b9dedf9ad9307b77cf70be721e`.
- [Control-v2 resource checks](../../build/oct14-activation-v2-resource-tests.json): 22/22, `04a1c81f2fff5a3f22ac17772332aaa6eb814deb635465ebac9a3b93d823078d`.

The integration check verifies that 30 prior runtime/consumer inputs remain byte-identical to control-v1. Unchanged validator, coordinator and wire suites were not repeated. The corrected engine run subsequently executed as recorded below.

## Actual activation: UI opens; combined acceptance remains false

Control-v2 passes host readiness and compilation (zero errors, nineteen warnings). The previous `Formula too complex` and associated compile errors no longer occur. The run makes one normal manager toggle request, observes one genuine true callback with trace `E1T;R1;`, and completes all three state-observation groups on the next FRAME. Membership, character ownership, manager ownership, exact held item/component and IN_HAND remain true. The tablet is FOCUSED and its UI is present, open and has a root widget. The fixture has no attached map.

`post_toggled_on` is false. The unchanged activation predicate therefore reports `activation_verified=false`. UI construction is observed; successful combined activation, physical input and visual correctness are not established. A later log reports a 128 × 128 root inside an 1859 × 658 workspace; this is not a visual acceptance result.

The outer result remains **unavailable**, because the broad engine-error scanner rejects the intentional input-free fixture's diagnostic: `[MESH] tablet has no SPK_DroneInputComponent - manual control unavailable`. The exact event appears at the same timestamp in console, error and script logs. This is separate from the observed false engine toggle flag. All owned processes exited, and cleanup reported no errors.

- [Actual outer receipt](../../build/tablet-owned-profile-run-az5h805g/results.json): SHA-256 `085f32c172c634f10449f02096f6ba2b6d8b49c4f46c55bd6570705ccc096d4a`.
- [Readable independently checked summary](../../build/oct14-activation-v2-actual-summary.json): `efed6f402b5464c15fbe138deba4eb97edcb468974f981f02de867107e7edb38`.
- [Actual exchange fixture](../../build/oct14-activation-v2-actual-ledger.json): `653e1a388bd4ad7d623f03a2c0efa5eee2e9fa6c7b7c6470325f53835e712e17`. The unchanged Python verifier independently reconstructed the same proof from all 22 post-identity exchanges. Including the initial loaded-project check, the run contains 23 RPCs.
- [Source/artifact preservation](../../build/tablet-post-restart-preservation-qk2rho9s/result.json): `8eaeeabf3f3fc7bbe3cbd9bde771353fc48ede48bb811d3b291fc651161bd193`, all 107 protected sources, five artifacts and 25 private payloads unchanged.
- [Operator-profile preservation](../../build/operator-game-profile-preservation-h6rvdhvi/result.json): `2bf472a6d65a1dd6be539d824fd2c9515582ab35c548d9694d07e1b5375249d6`, all 1,293 captured files unchanged. Ordinary headless compilation still writes Workbench logs; this audit is not a claim that every user-directory file is unchanged.

The next harness revision classifies only the exact expected fixture event, retaining all raw matches and rejecting any unrelated errors. It requires exact input-free source identity and independently verified callback/UI facts; it cannot change the false toggle observation or activation predicate. Its independent Python and actual PowerShell classifier suites each pass 47/47 cases, with identical result hash `0897097562defd75cc83280ce94a7a22698d2e61cf2434b9aa194f24ad98dfb4` ([Python](../../build/oct14-activation-log-python-tests.json), [PowerShell](../../build/oct14-activation-log-powershell-tests.json)). Full raw-log integration remains a separate check.

Source investigation identifies a relevant method difference: the captured production input invokes `gadget.ToggleActive(wantOpen, SCR_EUseContext.CUSTOM)`, whereas this probe invokes `manager.ToggleHeldGadget(true)`. Installed API documentation distinguishes synchronization from the delivered callback, but does not establish when `IsToggledOn()` changes. Exact installed method bodies are the next evidence sought. This is a testable cause hypothesis, not an established engine defect or a reason to weaken acceptance.

## Installed sources establish missing gadget-state maintenance

Two subsequent owned edit-mode captures establish the exact installed source bodies, without entering Play. Each generated packet passes 263 source checks and 31 protocol checks. Ordered native chunks reconstruct 15,539 bytes for `SCR_GadgetComponent.c` and 46,094 bytes for `SCR_GadgetManagerComponent.c`; the independent wrapper checks original byte counts and hashes. See the [compact source-capture evidence](../../build/oct14-installed-gadget-source-summary.json), SHA-256 `86266fa085c99a3b985c79a6938bee7f9088f0fabaa38af89eb8c46225dd5669`.

- [Installed component](../../build/oct14-installed-SCR_GadgetComponent.c): `015c18b4c94245e72c923e718b74cf933cd516c0a9dc24946735482c2e4e191b`. `IsToggledOn()` returns `m_bActivated` (lines 96–99); the field starts false (75); base `OnToggleActive` is declaration-only (104). `ToggleActive` validates owner, use context and replication ownership, optionally invokes the proxy callback, then asks the manager (265–284). It does not set the field.
- [Installed manager](../../build/oct14-installed-SCR_GadgetManagerComponent.c): `d1f352afc464124f93ae422fe9299a57ccc7106dbd95c8da6d618406e85788c6`. `ToggleHeldGadget` delegates to `ToggleActive(state, FROM_ACTION)` (318–324). Server/client RPC handlers deliver `OnToggleActive` (1124–1149), without updating the field. Ordinary action handling derives its next state from `!IsToggledOn()` (517).

The captured MESH `SPK_TabletGadgetComponent.OnToggleActive` calls the empty superclass callback and drives the local tablet UI, but never maintains the inherited flag. Together with the actual completed true callback and later false getter, these bodies establish the missing adapter bookkeeping. The earlier method-path difference does not explain the flag: both paths reach the same callback machinery once their context checks admit them. Waiting longer is not the repair supported by these sources.

The proposed minimal adapter correction is `m_bActivated = state` immediately after the existing superclass call and before the local-owner guard. The flag records the delivered gadget activation state, including on nonlocal instances; UI availability and focus success remain separate observations. It does not become proof of server authorization, visual readiness or successful UI construction. Repeated true callbacks retain existing focus/population behavior. An isolated candidate and explicit true/false/nonlocal/failure regression cases must verify this correction before promotion; neither the original source nor earlier negative receipts is overwritten.

The [candidate regression receipt](../../build/oct14-gadget-state-fix-tests.json) passes 25/25 checks, SHA-256 `f210a1fcd53f5da258a73f71d01c866f16df28846db1bac772b9eb19f7566ef3`. It verifies exact one-line restoration to the original hash, parses the actual callback body into a bounded model, compares independent branch traces, and detects the original missing assignment plus deliberate ordering/state mutations. External service responses are scripted fixtures; these checks do not claim runtime compilation, delivery, multiplayer or UI-internal equivalence. Exact engine execution of the repaired adapter remains the next gate.

## Corrected candidate admission

Diagnostic-only control-v3 preserves all native behavior and passes 20 Python raw-log/inventory checks, 14 actual PowerShell policy checks, 125 source-integration checks and ten post-freeze checks. The final repaired candidate is `player-tablet-activation-control-20261014-v4c`, freeze `abfc0591e9a2ed63fac7d53902ace0535e67344e7b95dccd55dc42ac69de1df5`.

Its production inventory is explicitly 84 unchanged sources plus the corrected gadget class. Preparation validates the 85 original source files before deriving the candidate; both source identity and the staged manifest describe the actual replacement. The independent wrapper rejects a stale original hash or an unrelated source change. [Staging/admission checks](../../build/oct14-activation-v4-production-override-tests.json) pass 18/18 (`76202babdb3180f362f1634a7cbef92cc0f4d5ef078304a4ddec41c564c035e6`), and [source integration](../../build/oct14-activation-v4-integration-tests.json) passes 133/133 (`bf0d9404cded2d1f1b547544df0f4bd8cded84887623d1e2e61516a3793ff8d9`). Native actions, callback observation and activation acceptance retain their prior bytes.

A freeze-construction mistake produced an empty local inventory in the first v4 packet. It was retained and never prepared or launched. Running its guard also exposed an assumption in a deliberate-mutation fixture: `next(iter(files))` raised `StopIteration` on the empty inventory. The [failed attempt](../../build/oct14-activation-v4-invalid-freeze-attempt.json) remains failure (`163ebf2f090eb75f17120e5733c92661beb6bb1b8d557685cba7a9b59f1206eb`). A complete intermediate v4b remains preserved; v4c adds a standalone mutation fixture and explicit empty-inventory rejection.

The final [post-freeze guard](../../build/oct14-activation-v4c-freeze-tests.json) passes 11/11 (`762d7fdb4c6c2b1bd01a8a7a4cb00e67dbc2441b2fe3d07d98b758984f66f868`). An [actual malformed-inventory invocation](../../build/empty-freeze-regression-7ab1a1ffbc694ffcade0249dd2ffc0ef/result.json) now returns the expected structured failure instead of a traceback (`36bb551f985130dd186caa7455008148f6f22636c25631c816438372576c272e`). Neither malformed-input test runs an engine. The valid v4c candidate proceeds through a fresh owned preparation and engine job.

## Actual repaired activation passes

The fresh v4c candidate passes host readiness, compilation, owned gameplay execution and independent verification of all 25 RPCs. One normal manager activation request delivers one genuine true callback (`E1T;R1;`). The next FRAME observes the same owned, held IN_HAND gadget with **`post_toggled_on=true`**, tablet FOCUSED, and UI present/open/root present. The unchanged predicate now reports **`activation_verified=true`**. Map absence is recorded as degraded opening; the fixture has no map attachment.

- [Actual result](../../build/tablet-owned-profile-run-rc6m2rj6/results.json): SHA-256 `7506fb3988b22d4ac87b7fe4df32ebf28841a088b012f2b717414e44079c71c4`.
- [Readable independently checked summary](../../build/oct14-activation-v4c-actual-summary.json): `106ff9333e89f9284a7780092d2b0d8358b4d2fa985e6ca94fe8e1521c89b61e`.
- [Actual exchange and final native record](../../build/oct14-activation-v4c-actual-ledger.json): `a39cd704fa8c8cf83569828c41fd362948571143f420364f489925c13fb75912`. Future synthetic extensions are not evidence of executed later actions.

The exact expected missing-input event remains visible in all three retained logs and is independently classified. No unadmitted diagnostic remains. Both compiler and runtime coordinator exit zero with confirmed exit and empty cleanup errors. Their elapsed durations are execution records, not performance measurements.

All 107 protected sources, five installed artifacts and 25 private payloads remain unchanged ([audit](../../build/tablet-post-restart-preservation-amm7nl1b/result.json), `8eaeeabf3f3fc7bbe3cbd9bde771353fc48ede48bb811d3b291fc651161bd193`). The old operator-game-profile baseline file was unreadable in the resumed process context, so its direct comparison attempt failed. Without changing permissions, a fresh complete deterministic snapshot was generated; its entire SHA-256 exactly matches the previously recorded baseline `e23dcb9dc462283d4c262d2aca3fa06927c2d5478a65590ee4b4759d459a9f13`. This establishes equality for the 1,293 captured files and namespace ([comparison receipt](../../build/oct14-activation-v4c-game-profile-hash-comparison.json), `067b02a8d13f7a933999bddd70f3437ee36e26e6949c18f3f582db1cc7462cc8`). No ACL or operator-profile change was needed.

This result verifies the minimal adapter correction in the isolated local-player fixture. It does not verify physical input, rendered layout, map interaction, closing, inventory stow, explicit destruction, multiplayer or join-in-progress. No live MESH promotion occurred.

## Subsequent gates

Normal toggle-off, physical inventory stow and explicit destruction need separate action and observation receipts. A false toggle can put the tablet component in STOWED while the engine gadget remains IN_HAND. Current generated toggle-off behavior closes UI, transitions through HELD, then enters STOWED; its observed services must preserve Close, optional screen creation, Enable and Disable ordering.

Explicit destruction must use the verified engine deletion path with current authority checks. The existing component service hooks can observe Close, screen destruction and the pre-super marker. Any post-super marker must use only a pre-captured scalar token, with no access to the destroyed component, owner, UI or screen. A surviving observer may later inspect a weak entity reference.

Directly stowing an active tablet is a distinct required test. The captured manager stow path requests removal from the hand and waits for controller/animation completion; it clears gadget focus but does not itself call `OnToggleActive(false)`. Passing toggle-off followed by stow would therefore not prove automatic closure when an active tablet is stowed. This possible lifecycle gap is not folded into the flag correction. Join-in-progress restoration also remains separate: the captured base replication path serializes gadget mode, which does not establish restoration of the activation flag.

UI opening queues terrain work at 400 ms and a size report at 500 ms. Queue behavior and lifetime require their own bounded follow-up; the presence of deferred work is not itself evidence of a leak. Physical clicks, keybinding persistence, visual acceptance, dedicated clients and production promotion remain open.
