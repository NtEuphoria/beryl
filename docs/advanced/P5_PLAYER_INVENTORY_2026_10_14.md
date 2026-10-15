# P5: October 14 player inventory diagnostics

Latest completed engine checkpoint: [the read-only equipment observation passes and reports the tablet already in hand](#equipment-prerequisites-observed-tablet-is-already-in-hand), while retaining verified insertion and callback evidence. Explicit activation, UI and the real-player lifecycle remain open. Earlier sections retain their checkpoint scope.

At the first October 14 diagnostic checkpoint, both the original run and the corrected resource-selection candidate completed their observation protocols. The stale resource GUID is repaired, but actual tablet insertion still fails to complete. This checkpoint advances diagnosis; it does not accept the real-player tablet lifecycle or authorize promotion.

## First October 14 diagnostic result

The exact retained outer receipt is [tablet-owned-profile-run-teublzz4/results.json](../../build/tablet-owned-profile-run-teublzz4/results.json), SHA-256:

`01210f834b7fcaec141e01df72191462f1337d209f4dae0df0773a1d4816e16a`

| Observation | Result and scope |
|---|---|
| Diagnostic transport | All 59 RPCs passed their protocol checks. |
| Native observations | Three snapshots covering 12 diagnostic groups were returned; 19 storages were enumerated. |
| Membership | 3,261 actual `Contains` observations remained false. |
| Failure callbacks | Three genuine `OnFailed` callbacks occurred. They do not establish three independent insertion requests. |
| Original insertion outcome | The fixture reached its declared `time_limit`; insertion remains unverified. |
| Renderer | This run completed without the earlier native GPU crash. |
| Owned process | Recorded PID 33328, start ticks 639276010580562638, start UTC 2026-10-14T18:57:38.0562638Z; cleanup confirmed the owned process stopped. |
| Downstream behavior | Equip, real-player UI opening, player interaction and destruction acceptance remain open. |

The transport success means the requested observations were delivered and checked. It does not convert the insertion timeout into a successful game action. The previous October 12 insertion counts belong to their own immutable candidate and remain historical evidence.

The installed inventory-manager source captured earlier explains how one public insertion request can attempt several storage purposes and deliver several failed callbacks. The new diagnostic result must be read with that implementation, rather than treating the callback count as a retry count. No manual focus/state change or synthetic callback has been used to bypass insertion acceptance.

## Resource observations

A separate bounded monitor recorded 63 samples from 2026-10-14T18:57:01.8445859Z through 18:59:08.3562841Z, lasting 126,508 ms. It stopped when the owned `stop.requested` marker was observed. Its receipt correctly records `cancelled` and `completion_verified: false`: it did not collect all 90 originally requested samples. This monitor cancellation does not describe the engine test's outcome.

The monitor used one batched counter query per sample, followed by disk-space and Discord process-count observations. The samples are not atomic and can miss peaks between observations.

| Metric | Observed range or maximum |
|---|---|
| Available physical memory | Minimum 12,127 MiB. |
| System committed memory | Maximum 25,375,334,400 bytes. |
| System commit limit | 41,419,350,016 bytes throughout the samples. |
| Paired commit fraction | Maximum 61.2644%, using committed bytes and limit from the same counter timestamp. |
| Main nonzero GPU adapter dedicated usage | Maximum 2,762,649,600 bytes for instance `luid_0x00000000_0x0000cfe6_phys_0`. |
| C: available free space | First 6,683,369,472 bytes; minimum 1,788,162,048 bytes; final 1,999,798,272 bytes. |
| Discord process count | Zero in every one of the 63 observations. |

GPU values are retained by adapter instance and are not summed. These are whole-system observations, not allocations attributed to Workbench. They support the conclusion that this run had substantially more commit headroom than the earlier resource-pressure checkpoint. They do not identify a unique cause of the earlier Direct3D failures or establish that changing one resource condition fixed them.

Retained monitor inputs:

- [Timeline receipt](../../build/oct14-inventory-memory-timeline-01/receipt.json), SHA-256 `213c26ef415502453baffe75f87fe4967e27ab52cb8cf6bd814aa31d25a033f8`.
- [63 raw JSONL samples](../../build/oct14-inventory-memory-timeline-01/samples.jsonl), SHA-256 `a8eb3794802ebb43dcbe752efefad21abbedc5da056b692afe385d5f2aeddce0`.

## Module capture: first unavailable, later verified

The separate owned-process module probe at [oct14-readonly-probe-d2rm0pxs/result.json](../../build/oct14-readonly-probe-d2rm0pxs/result.json) returned exit code 2 and unavailable: no matching live private runtime process was found. It therefore supplies no verified Discord-hook absence. A zero Discord process count is not a loaded-module inventory.

The actual native startup record contains the expected 11 arguments, or 12 tokens when including the executable. No argument-shape discrepancy has been established. The older module-probe wrapper recorded elapsed duration but not launch/exit UTC; the native receipt records process start UTC but no precise exit UTC. Those receipts cannot establish whether module discovery overlapped the live process. Filesystem timestamps are metadata, not verified process timing. A rerun solely to force an absence claim is unnecessary.

During the corrected candidate run, a new capture completed successfully and enumerated 116 modules from the verified owned process. No recognized Discord hook module was present in that single observation. The retained [probe receipt](../../build/oct14-readonly-probe-a1i2_4m2/result.json) has SHA-256 `606e0995f88ddd8c3671405f05f9c73e4d2ad121cf65fb36647a0d851ec7f602`; its [stdout capture](../../build/oct14-readonly-probe-a1i2_4m2/stdout.txt) has SHA-256 `3ef2ddd5ec11aae212954e09a7e9bc5b1bd9f298f140c049eb125fb251bb1805`. This establishes absence at that bounded capture, not throughout the session or during the earlier crashes. The earlier unavailable receipt remains unchanged.

The resource-observer source packet adds strict argument-vector checking and bounded output. Its documentation and source identities remain in [the observer handoff](../../build/player-resource-observer-source-20261014-v1/HANDOFF.md). The existing-evidence analyzer is separate from the engine test and cannot turn an unavailable capture into success.

## Resource-selection repair executed; insertion still fails

Source inspection identified a stale hardcoded resource GUID passed to `Resource.Load`. The first candidate passed 11 focused checks. The subsequent version-2 packet strengthens same-buffer source hashing and strict integer checks; it passed 22 regression cases and 33 source checks before engine execution.

The corrected run is [tablet-owned-profile-run-c2xcetr3/results.json](../../build/tablet-owned-profile-run-c2xcetr3/results.json), SHA-256:

`36576dd814eea51ee57783cf218226c93e38f139252f39968263f476c710b2e2`

| Corrected candidate observation | Result |
|---|---|
| Diagnostic protocol | All 63 RPCs passed. |
| Snapshots | Three complete captures, each containing the 12 diagnostic groups and 19 storage rows. |
| Membership | 3,621 actual `Contains` observations remained false. |
| Callbacks | Three genuine `OnFailed` callbacks. |
| Insertion outcome | `time_limit`; insertion remains unverified. |
| Resource warning | The retained native-log search finds no occurrence of the prior wrong-GUID diagnostic. |
| UI and lifecycle | Real-player equip, opening, interaction and destruction acceptance remain open. |

This fixes the identified resource-selection defect, but it is not sufficient to make insertion succeed. Absence of the specific GUID warning is not evidence that all resource or storage semantics are correct. The next investigation continues from the returned item/storage diagnostics and exact installed definitions. No earlier failure is overwritten, and no successful transport result is promoted to gameplay acceptance.

Version-2 identities:

- [Packet source freeze](../../build/player-inventory-resource-identity-20261014-v2/source-freeze.json): `0f2f76749e9e34b581d29e31d09be7c48749378904bbd6cc3a1ac575dbf1f2b0`.
- [22-case regression receipt](../../build/oct14-resource-identity-regression-v2.json): `73d4aed30ff1d4d8d36d39beb4097b69d846a2bdba8cf599f13a7aa9c63419f7`.
- [33 source-check receipt](../../build/oct14-resource-identity-source-checks-v2.json): `33d8eaa3adb870624ba05b4267cc3a390c1da39ea7b6858d37b72807263b670c`.

The [protected Game-profile comparison](../../build/operator-game-profile-preservation-b4ley5ry/result.json), SHA-256 `2bf472a6d65a1dd6be539d824fd2c9515582ab35c548d9694d07e1b5375249d6`, finds all 1,293 recorded files unchanged. This is content-preservation evidence within that inventory; it is not a claim that every possible engine write location has been confined. Live MESH and generated output have not been promoted by this checkpoint.

## Disk recovery and next gate

An earlier read-only root observation found C: free space at 296,173,568 bytes, about 282 MiB, with no Workbench or Discord process running. Engine launches were held. The decline continued while no engine was running, and its cause was not established. No user files were deleted as part of that hold.

Space subsequently recovered to 5,285,998,592 bytes before the corrected run, and a later root observation reports approximately 7.7 GB free. The earlier hold is therefore historical, subject to checking current headroom before further engine work. Windows Update download/failure events were observed during the interval, but no amount of the space change has been attributed to those events.

Next is the bounded capture and review of the exact installed item and prefab definitions, informed by the actual rejection diagnostics. Preserve the original insertion operation while testing a supported correction. Only successful insertion admits the subsequent equip, real-player UI-opening, interaction and destruction tests. Input persistence, dedicated multiplayer, visual review, full tablet acceptance and promotion retain their separate gates.

The historical PowerShell-stalling cause also remains unestablished. Successful commands and this completed diagnostic run demonstrate current execution capability; they do not retrospectively explain every earlier host failure.

Earlier evidence remains in [the October 12 frame and player checkpoint](P5_PLAYER_FRAME_2026_10_12.md).

## Installed definition captures

Three subsequent read-only edit-mode probes completed and captured the exact installed definitions. These operations did not execute insertion, UI actions or player lifecycle tests.

| Capture | RPCs | Captured bytes | Exact receipt |
|---|---:|---:|---|
| Item attribute source | 11 | 4,147 | [ncw0xdol](../../build/tablet-owned-profile-run-ncw0xdol/results.json) |
| Map_Base template | 9 | 690 | [vbkqqww0](../../build/tablet-owned-profile-run-vbkqqww0/results.json) |
| Item_Base template | 10 | 2,147 | [jt70vpa6](../../build/tablet-owned-profile-run-jt70vpa6/results.json) |

Receipt SHA-256 identities, in the same order:

- Item attributes: `9b30e7af0d5c63f7c5ce945db103e744d95b60c1f23d97d9e7396d172abb6936`.
- Map_Base: `53e0ea8e432ceb81cfed6a9180df4bfdb33788c5d939a26d0250a4e46784ef5d`.
- Item_Base: `55e1444295b8754b068f1b8bb723396cf9ff22fd67e23e460cd30ddf00ac4a84`.

Captured source SHA-256 identities:

- [Item attribute source bytes](../../build/game-profile-token-preparation-68x8n5ff/installed-item_attributes_source.bytes): `c0fd8a113f166245666a3db5d398f053bc52e331e2eea899025f596343d68116`.
- [Map_Base bytes](../../build/game-profile-token-preparation-37qj3_dc/installed-map_base_template.bytes): `d51c0c41f55e322b7d166af83f07bc1895a387666e3988d006e891d4e0aa6f71`.
- [Item_Base bytes](../../build/game-profile-token-preparation-2uxh_3mp/installed-item_base_template.bytes): `d56611a181056bb5a774a34211d67c41db37d60cdc498a44568c13a00bb8d57d`.

The captured Map_Base inherits Item_Base. Item_Base explicitly declares `ItemPhysAttributes ItemPhysicalAttributes`, containing `PhysicalAttributes { Weight 0.01 }`, together with `m_Size SLOT_1x1`, `m_SlotType SLOT_LOADOUT_STORAGE` and a hierarchy component. The current isolated tablet fixture lacks those corresponding explicit declarations. These are concrete source differences; capturing the text alone does not prove the complete inherited/cooked configuration or identify which native storage predicate rejected the tablet.

The captured SCR item-attribute implementation returns zero from its volume and weight getters when the physical-attribute object is absent. This explains one possible source of zero-valued diagnostics, but does not prove that a zero value by itself causes rejection or that adding the object is sufficient.

The next controlled candidate adds only the physical-attribute declaration. Its engine result is pending at this checkpoint. Slot type, size and hierarchy are separate differences and must not be bundled into an unverified claim of root cause. Successful real insertion, equip, UI opening and destruction remain unaccepted until their actual operations pass.

## Physical-attribute-only experiment: negative result

The controlled candidate adding only the physical-attribute block has now executed. Its preparation passed 25 focused regression cases and 33 source checks. The engine returned 60 checked RPCs and all three complete snapshots of the 12 diagnostic groups.

The snapshots show weight `0.01` and volume `100`, compared with `0` and `0` in the corrected-GUID baseline. Those are the recorded getter values; no additional unit interpretation is asserted here. This confirms that the added block was loaded and affected the observed item properties. It does not make insertion succeed: 3,576 membership observations remained false, three genuine `OnFailed` callbacks occurred, no completion callback was observed, and the fixture reached `time_limit`.

This is a completed negative experiment. The physical-attribute omission is a real configuration difference, but this candidate still failed in its observed fixture. The differing runtime populations listed below prevent treating it as a matched cross-run causal comparison. The result supersedes the preceding pending status for this experiment; its earlier preparation history remains intact.

Retained identities:

- [Candidate source freeze](../../build/player-inventory-physical-attributes-20261014-v1/source-freeze.json): `c828611eecad30468f50fccd7bd14ca91e049f8a743e71d4852f7c0c2bf7d2b3`.
- [25-case regression result](../../build/oct14-physical-attribute-regression.json) and [33 source-check result](../../build/oct14-physical-attribute-source-checks.json).
- [Exact preparation](../../build/game-profile-token-preparation-qz8gu49w/results.json): `bd9a42a988fc883867ab652273a0ced9bb9144daf0d788e8dbb45dd69db584c6`.
- [Executed result](../../build/tablet-owned-profile-run-pp02aqyr/results.json): `16bdab708fdcac46e8a4d1c85ae9b101285fb62b1f45b41eea032838b4176a4b`.

A separate candidate targeting the hierarchy component is being prepared, and the installed folded-map definition capture is ongoing. Neither has an accepted outcome at this checkpoint. Equip, real-player UI opening, interaction, destruction and promotion remain unaccepted.

## Folded-map capture and hierarchy experiment

The fourth requested definition capture, the installed folded-map template, completed through nine read-only edit-mode RPCs and returned 1,828 bytes. It explicitly declares the SCR item attribute `m_SlotType SLOT_GADGETS_STORAGE`. That source name is evidence; no numeric mapping to the raw diagnostic slot value is inferred.

- [Capture receipt](../../build/tablet-owned-profile-run-i6xx0ivz/results.json): `0fa781c35aa871440fe170bc0fb14c4a1da9031a79e4b8592a9822b41dee1668`.
- [Captured template bytes](../../build/game-profile-token-preparation-s6d8qeee/installed-folded_map_template.bytes): `397086de2de3de3232924d705654e92e03b4478aab1c3ad3a9087561b1e39105`.

The independent hierarchy-only candidate also executed after 25 focused regressions and 33 source checks passed. All 60 RPC checks and three complete 12-group diagnostic snapshots returned. Weight remained `0`, volume `0`, and the observed slot value was raw `2`. Membership remained false on 3,518 reads; three genuine failure callbacks and zero completion callbacks were recorded before `time_limit`. This hierarchy candidate therefore failed in its observed fixture; it does not establish a matched cross-run causal comparison.

| Executed candidate | Storages in that run | Checked RPCs | False membership reads | Failure callbacks | Weight / volume | Insertion outcome |
|---|---:|---:|---:|---:|---|---|
| Corrected resource GUID | 19 | 63 | 3,621 | 3 | 0 / 0 | time_limit |
| Physical attributes only | 16 | 60 | 3,576 | 3 | 0.01 / 100 | time_limit |
| Hierarchy only | 20 | 60 | 3,518 | 3 | 0 / 0 | time_limit |
| Gadget slot only | 18 | 67 | 3,768 | 3 | 0 / 0 | time_limit |
| Combined prerequisites | 19 | 60 | 3,541 | 3 | 0.01 / 100 | time_limit |

The root-verified [inventory comparison](../../build/oct14-inventory-comparison.json) establishes that storage populations were stable within each run but differed between runs: original diagnostic 19, corrected GUID 19, physical attributes 16, hierarchy 20, slot 18 and combined 19. Candidate source changes were isolated, but the runtime storage populations were not matched across candidates. Each negative result therefore shows that its candidate failed in its observed fixture; these are not matched cross-run causal comparisons. The cause of the population variance is unknown. The membership-read counts are also not a performance comparison. No successful insertion fix or later player/UI acceptance has been established.

Hierarchy-candidate evidence:

- [Source freeze](../../build/player-inventory-hierarchy-20261014-v1/source-freeze.json): `e5df387417172c217e9d81de5876a4776e0bd671f1fb1c9887c911598d64c80e`; [25-case regression](../../build/oct14-hierarchy-regression.json) and [33 source checks](../../build/oct14-hierarchy-source-checks.json).
- [Preparation](../../build/game-profile-token-preparation-q_09x6mh/results.json): `902b8460760b87696806e64960862a6d011be47cd68ac14ebb72bc8cc379ba41`.
- [Actual result](../../build/tablet-owned-profile-run-w44ts_or/results.json): `4aa3c48b888dd66547b02641a7f389726f92d2988b9876cb38d35518c4682cb2`.

The next controlled experiment changes the slot declaration alone. A combined candidate follows only if needed. Both remain pending; the completed definition captures and negative experiments do not complete the tablet feature or Beryl.

## Slot-only and combined experiments: negative results

The slot-only experiment passed 33 focused cases and 33 source checks, then executed 67 checked RPCs. Three complete 12-group snapshots recorded weight `0`, volume `0` and raw slot value `4`. Insertion still reached `time_limit`: 3,768 membership reads were false, with three genuine failure callbacks and zero completion callbacks. The declaration change affected the observed slot value, but this candidate did not achieve insertion in its observed fixture.

- [Slot source freeze](../../build/player-inventory-gadget-slot-20261014-v1/source-freeze.json): `a35f05a068736cdead051ef60e2385f339df8a20d0f727db76ea636e6d5df0e2`; [33 focused cases](../../build/oct14-gadget-slot-regression.json) and [33 source checks](../../build/oct14-gadget-slot-source-checks.json).
- [Preparation](../../build/game-profile-token-preparation-tyflxlq6/results.json): `06266a0c20704e43f4561da959876622a373db8541d8caf95da3d3f5d36016ff`.
- [Actual result](../../build/tablet-owned-profile-run-k0qewtcr/results.json): `46128410b25b17c6d4fc6b8d5fedc6400e673c095225337a0e842bd74b3a177c`.

The combined prerequisite candidate passed 28 focused cases and 33 source checks. Its 60 checked RPCs returned three complete diagnostic snapshots showing weight `0.01`, volume `100` and raw slot value `4`. It also timed out, with 3,541 false membership reads, three genuine failure callbacks and zero completion callbacks. The combined candidate did not achieve insertion in its observed fixture.

- [Combined source freeze](../../build/player-inventory-joint-prerequisites-20261014-v1/source-freeze.json): `6bba12d75522a4ddc602f8014ae83021f1ca1c67000dca1aafd0efeed704a45d`; [28 focused cases](../../build/oct14-joint-prerequisites-regression.json) and [33 source checks](../../build/oct14-joint-prerequisites-source-checks.json).
- [Preparation](../../build/game-profile-token-preparation-omdk9p9i/results.json): `bad0e105ed31bb9ae8869567c01e6d49ac1a81bc3f036c02b3d16afe887dde0f`.
- [Actual result](../../build/tablet-owned-profile-run-1fsjh_4x/results.json): `38dcbda83a0bb408e086b609670a5bc3921f15dc84736699d4a020faa8f6f600`.

These outcomes supersede the pending slot/combined experiments above. The stale-GUID correction remains verified, but none of the experimental prefab changes has established an insertion repair and they must not be promoted on that basis.

Next is a bounded native eligibility probe after the original insertion attempt reaches its terminal outcome. It will compare instance/resource eligibility and storage returned for the selected purpose. Source work has begun; the probe is not yet ready or runtime-verified. Equip, UI opening, real-player interaction, destruction and release remain open.

## Eligibility admission revised after the population comparison

The [initial eligibility native source packet, version 1](../../build/player-inventory-eligibility-native-20261014-v1/source-freeze.json), assumed a fixed 19-storage fixture. It was source-only and is superseded before runtime execution. The revised contract is being prepared for a bounded per-run terminal count from 0 through 64. Admission will use that particular run’s completed terminal observation, then require exact reference, order and presence continuity across the later eligibility observations. The bound is a diagnostic limit, not an engine capacity rule.

This revision avoids requiring different scenario runs to produce the same population. It does not relax continuity within a run, explain why the populations differed, or make any negative experiment a successful fix. The revised eligibility probe has no runtime result yet. All earlier receipts and source hashes remain retained above.

## First eligibility execution: dispatcher rejection before the new probe

The revised eligibility packet passed 50 integration cases, 22 resource-identity cases, 12 native source checks, 45 Python cases and 45 PowerShell cases. The exact staged engine source then compiled successfully with zero errors and 19 warnings. These checks did not cover the actual dispatcher allowlist sufficiently.

The executed attempt failed at `eligibility_arm`, before that request was sent to the engine. The stale `Assert-Parameters` action allowlist in the version-1 `profile-engine.ps1`, line 299, excluded the four newly introduced actions. This is a confirmed test-harness defect. No new eligibility queries ran, so this attempt supplies no native eligibility result. The original insertion outcome remained `time_limit`; the later harness failure did not replace that source outcome or make insertion successful. Owned cleanup completed, and the owned process was confirmed absent.

The root-verified [executed receipt](../../build/tablet-owned-profile-run-5cfld1np/results.json) has SHA-256 `960816f827a0c3acc1a9347d04a23223773fd2716726fb3dce25a9772f8e0952`. It remains a failed attempt. Its successful compilation and earlier test counts do not establish successful execution of the new eligibility path.

A version-2 packet is being prepared with the allowlist correction and regression cases through the actual dispatcher. Its engine rerun is pending. Earlier failed receipts remain unchanged; no eligibility, insertion, equip, real-player UI, interaction or destruction acceptance is added by this attempt.

## Eligibility version 2: completed native observations, insertion still failed

The dispatcher correction passed all 35 direct dispatcher regressions and 53 integration source checks. Its fresh engine run completed 66 checked RPCs. The original physical attempt still ended at `time_limit` with insertion unverified, and callback-integrity verification remained true. The later eligibility observation neither retried insertion nor replaced that original outcome.

Case 4 returned all six diagnostic groups from one genuine FRAME. It enumerated 18 storages and verified the same references, ordering and presence against the completed terminal capture and across its before/after continuity checks. Both native find operations selected row index `17`. All 36 eligibility queries returned: 18 instance queries and 18 resource queries. Only row `17` returned true for both; every other row returned false for both. These are results from that later query sequence, not proof of eligibility when the original entity was spawned or when insertion was first requested. They do not by themselves establish the rejection cause or show that insertion would succeed at the later observation point.

Retained evidence:

- [Executed version-2 receipt](../../build/tablet-owned-profile-run-gj_dhofp/results.json): `140e1c6ffff1c841244d8ae106b57376ea6480a3a687b5cf1cfd7e93a2a43de0`.
- [35 direct dispatcher regressions](../../build/oct14-eligibility-dispatch-v2-tests.json): `fe4f30dfc81ec26791084ea0c5d5f530fcf854f15d36d707812c5b7d8ec86e03`.
- [53 integration source checks](../../build/oct14-eligibility-v2-integration-source-checks.json): `53604dac5a87250e576478fd2909f6c1dafb7acb99a5e537855bcf30e896f054`.
- [Version-2 source freeze](../../build/player-inventory-eligibility-20261014-v2/source-freeze.json): `2dce5f9115d85f452ec1ed75858172a4c95192c41fbdcbf3038b4e0451850de9`.

This completes the eligibility observation protocol for this exact run and supersedes the pending version-2 runtime status above. The version-1 dispatcher failure remains a failed receipt. The next controlled test will defer the first insertion of a fresh entity until the next genuine FRAME; it is pending. No experimental prefab changes have been promoted, and successful insertion, equip, real-player UI opening, interaction, destruction and release remain open.

## Deferred first insertion: timing verified, insertion still failed

The fresh one-FRAME experiment passed 21 Python and 21 PowerShell timing cases, 26 resource/source regressions and 33 integration checks. The exact candidate compiled and executed 68 checked RPCs. The independent timing checks confirmed spawn on FRAME 1 and the first and only insertion call on FRAME 2. This was not a retry of an earlier insertion.

Insertion still ended at `time_limit`, with 4,003 false membership reads, three failure callbacks and zero completion callbacks. Terminal capture occurred on FRAME 4,005, and all three diagnostic snapshots contained 16 storages. The baseline failed-insertion branch did not accept final callback-integrity verification; its raw callback observations must not be described as successful insertion or accepted end-to-end callback integrity.

This particular next-FRAME workaround failed in its observed fixture. It does not establish that all timing differences are irrelevant, and the varying per-run storage populations still prevent a matched cross-run causal comparison.

- [Source freeze](../../build/player-inventory-deferred-first-insert-20261014-v1/source-freeze.json): `6b6a764b403674a27e3ae772ea49278173177b98246c9a58e03f15ad52c141b6`.
- [Python timing cases](../../build/oct14-deferred-first-python-tests.json): `fc3e8f87a9f47da2f2f5be1bb85cd26ae1821bf04dfe10215eb7d76e9c7820ba`.
- [PowerShell timing cases](../../build/oct14-deferred-first-powershell-tests.json): `b7cabf983d05557e57811c43feb347ce74525d294d092aa774b4e39f4180612f`.
- [Integration checks](../../build/oct14-deferred-first-integration-source-checks.json): `c72ad03f204f42da0d0ea170dbc38b8b4247787aad0fed0016854df90447ed5f`.
- [Preparation](../../build/game-profile-token-preparation-3_j5tz1j/results.json): `dd7a01afe5ffa194854cba6175560b630e82681c32970ef7f46fc507f7ed3985`.
- [Executed receipt](../../build/tablet-owned-profile-run-pyoca5on/results.json): `fafc4ffe4db398e4a7cbae088eda446cabc55bdb39d7700a0ecae6a37bb99b60`.

This supersedes the pending deferred-insertion status above. The next diagnostic work captures the installed callback implementation and prepares a generic insertion control using the installed folded map. Its real resource name must be resolved; the template's entity ID and inherited parent GUID are not its own resource GUID. No production changes or successful player/UI acceptance follow from these negative results.

## Installed callback implementation captured and reviewed

The owned edit-mode capture returned all 208,194 bytes of `scripts/Game/UI/Inventory/SCR_InventoryMenuUI.c`, reconstructed from 102 ordered chunks through 110 total RPCs (109 fixed protocol actions). It did not enter Play or invoke an inventory callback. The source identity is `717649eaa9a0f39c093e2526c56a17b08d7e63d913d12f41a889497d0d514099`.

`SCR_InvCallBack.OnFailed`, lines 98–108 of the captured source, conditionally requests equipment and deselection through an inventory menu. It does not read or reset the manager return code. The probe does not attach such a menu. This rules out a return-code reset by that installed superclass method as the explanation for the observed zero code. It does not establish what native condition rejected insertion. The method has no error-reason argument, and the manager's script return-code field must not be presented as a verified native failure reason.

- [Successful capture receipt](../../build/tablet-owned-profile-run-51v41h4c/results.json): `29e73b4f445fe36ea21003453674c68ea639369a510cec392e2f7e58b8e4afed`.
- [Captured source bytes](../../build/game-profile-token-preparation-_59y3oe0/installed-inventory_menu_source.bytes).
- [Fresh source freeze](../../build/tablet-definition-inventory_menu_source-ylvvm2jt/source-freeze.json): `a27b044656d4a8596e94d5b2aaa5abef8dc1ce112b8ccfc2ae53871ea5585bd8`.
- [Generator checks](../../build/oct14-callback-generator-v3-tests.json): 40/40; [source checks](../../build/oct14-callback-source-v3-tests.json): 263/263.
- [Protocol checks](../../build/manager-coordinator-artifact-tests-kj62n9l3/result.json): 31/31, SHA-256 `109bf204dc11a72340248e0089f72762fe6b277e7e0044a784f8b5689d32956c`.

An earlier source-only protocol run failed 1 of 31 checks because its inherited wrong-path fixture was the newly selected valid callback path. That [failed receipt](../../build/manager-coordinator-artifact-tests-z85gurzl/result.json), SHA-256 `9ae0eb437a44feae3c18f51ccd8e12def1a6c9cec640d4837a19ab266d4cdf4a`, remains unchanged. A new generator version chooses a distinct negative path for every supported selection; the runtime codec was not loosened to pass the test.

## Installed folded-map resource identity resolved

A separate owned edit-mode job resolved the fixed installed path through `Workbench.GetResourceName`. The exact result is `{13772C903CB5E4F7}Prefabs/Items/Equipment/Maps/Map_Paper_01/PaperMap_01_folded.et`. The engine returned the expected path and external-resource flag. The capture also reconstructed the same 1,828 template bytes as the earlier definition capture, SHA-256 `397086de2de3de3232924d705654e92e03b4478aab1c3ad3a9087561b1e39105`. No loose-file absolute identity was inferred for this packed resource, and no insertion occurred in this job.

- [Executed receipt](../../build/tablet-owned-profile-run-znrj613a/results.json): `6255a536f8aa62ae218af266a63bcf934219ea6241977500ab8a1f54b5155bd9`; nine total RPCs, eight fixed actions.
- [Preparation](../../build/game-profile-token-preparation-k3sh7lha/results.json): `bd89d22cc18ce40f609be384f6d998d69eddef716f2f043e39f5e81ff7d470e5`.
- [Source freeze](../../build/tablet-definition-folded_map_template-svquwqlx/source-freeze.json): `ac5524b297c088749b6b6de6d723e7f500d0e38b5c0f5596e6a16a92819d1343`.
- Generator checks: 23/23; source checks: 289/289; [protocol checks](../../build/manager-coordinator-artifact-tests-pru88ur3/result.json): 36/36, SHA-256 `dd9a15623d49918b1a6fcd1650649a9419cecded3d9e148405d3407bdd29b7fa`.

The isolated lookup profile explicitly repurposes the legacy `resolve_mptest` action and `mptest_*` response fields for this fixed resource. Its actual owned world and SubScene remain unchanged. The contract records this distinction; the stock-map name is not a claim that the loaded world was the map prefab.

Two earlier source-only lookup attempts failed before engine launch: one inherited an obsolete input path in a static fixture ledger, and one contained malformed nested newline literals. The [attempt record](../../build/oct14-stock-lookup-attempts.json) preserves these failures. The repaired fixture updates Raw, Response and normalized representations consistently, and tests reject incorrect paths, malformed names and a changed identity after resolution. These harness repairs do not resolve the gameplay insertion failure.

## Generic insertion controls: stock map and original tablet both failed

Both subjects ran through one frozen generic harness, stock map first and tablet second, in separate owned sessions. The actor retained the original same-FRAME spawn and first insertion, one request, actual superclass callbacks, immediate return-code capture and exact-item membership checks. Only the SPK-specific composition requirement was relaxed. The stock item was the installed resource, with no added SPK components or rewritten prefab.

| Subject | Storages in each of its three snapshots | Checked RPCs | False membership reads | Terminal FRAME | Failure / completion callbacks | Original outcome |
|---|---:|---:|---:|---:|---|---|
| Installed folded map | 16 | 69 | 3,852 | 3,853 | 3 / 0 | `time_limit` |
| Original input-free tablet | 17 | 60 | 3,477 | 3,478 | 3 / 0 | `time_limit` |

Both spawned and requested insertion on FRAME 1. Both retained an absent parent slot in all three diagnostic snapshots; the observed item replication flags were master/owner true and proxy false. Those flags do not constitute a complete authority proof. Optional SPK gadget-owner results are explicitly unavailable for the stock item and lack a completed-observation witness on the failed tablet path. Neither run accepted final callback integrity or successful insertion.

The failure therefore also occurs with the installed stock map under the tested path. This is useful evidence against treating the observed symptom as unique to Beryl's tablet. It is not a matched-loadout comparison, a proof that the engine cannot insert stock maps generally, or proof of a specific capacity, distance, duplicate-item or authority defect. Read counts are not performance results.

- [Frozen generic packet](../../build/player-generic-insertion-control-20261014-v1/source-freeze.json): `fe0d5b20c0a313953c165115849fd38a1c313046737cf7c349b667d1ca2783d2`.
- [Resource tests](../../build/oct14-generic-control-resource-tests.json): 37/37; [source checks](../../build/oct14-generic-control-source-tests.json): 38/38.
- [Python protocol tests](../../build/oct14-generic-protocol-python-tests.json): 22/22; [PowerShell protocol tests](../../build/oct14-generic-protocol-powershell-tests.json): 22/22; [exact source restoration](../../build/oct14-generic-checker-source-tests.json): 5/5. The 21-case composition suite also passed in each language.
- [Stock preparation](../../build/game-profile-token-preparation-ep3pgejl/results.json): `180791cb06b0858013fcca04bdc0e0949b732322ab2547f27122f90545b0c6a5`.
- [Stock executed receipt](../../build/tablet-owned-profile-run-k6nokw4n/results.json): `c02e4319f3563e3830e7a63ba822d9c6827b185b93141609867e9b550d986ee5`.
- [Tablet preparation](../../build/game-profile-token-preparation-dk_bgqeo/results.json): `fd1d1ec6f03b258e16e54ad17d63a989dc2bf58f14aeffc66ff7435c8b2ec14a`.
- [Tablet executed receipt](../../build/tablet-owned-profile-run-mtxyeqew/results.json): `48cea140a2202790d0ae98ae0191de560e48dbba5bc6ab9f8c001bc434113c49`.
- [Comparison extracted from the receipts](../../build/oct14-generic-control-comparison.json): `e2b522e1d464bd06c205a3ffdddce2af210578a6de83d88a94206e407302a17d`.

The next bounded observation examines the exact `WEAPON_PROXY`, `EQUIPMENT_ATTACHMENT` and `DEPOSIT` queries used by the installed insertion routine, then explicitly classifies the existing `ANY` result as hand storage or not. Its conditional hand-item getter will distinguish an empty hand from an unexecuted getter. This remains diagnostic work after the original terminal insertion outcome; it does not authorize a retry, claim an atomic snapshot, or repair the production prefab.

## Purpose probe: DEPOSIT and ANY select the same empty hand storage

The bounded purpose probe executed 64 checked RPCs. The original attempt still reached `time_limit`: 3,591 membership checks were false, three failure callbacks and no completion callbacks were observed, and the original terminal FRAME was 3,592. The separate frozen callback-integrity check passed.

The later one-FRAME observation completed all six groups with 19 storage references, unchanged reference/order/presence checks, and completed native return counts:

| Native observation | Actual result |
|---|---|
| `FindStorageForItem(..., PURPOSE_WEAPON_PROXY)` | Null |
| `FindStorageForItem(..., PURPOSE_EQUIPMENT_ATTACHMENT)` | Null |
| `FindStorageForItem(..., PURPOSE_DEPOSIT)` | Row 18 |
| `FindStorageForItem(..., PURPOSE_ANY)` | Row 18 |
| `FindStorageForResource(..., PURPOSE_ANY)` | Row 18 |
| Explicit hand-storage cast of the selected ANY reference | Succeeded |
| `GetHandSlotItem()` on that hand storage | Returned null |
| Per-storage instance/resource eligibility | All 38 calls returned; only row 18 accepted both |

This establishes the selected storage's class and observed empty-hand state directly, without interpreting raw enum number 1. It also rejects the hypothesis that only the ANY query could select that storage: DEPOSIT selected the same reference. It does not prove that those facts held during the first insertion, that the native insertion contract is identical to its eligibility queries, or that a particular distance/authority/capacity rule caused rejection.

- [Executed receipt](../../build/tablet-owned-profile-run-vo6ef0pj/results.json): `a91174fb9262994d1276bd91167f7af249ba1bba4c6a4d07f0c4eb8be5116750`.
- [Preparation](../../build/game-profile-token-preparation-t9kv5b3x/results.json): `fced11e75c2fee8d87e5f6771a07ea96c805f8ad4d0ee77ae7c1cc7a24eab487`.
- [Integrated source freeze](../../build/player-inventory-purpose-control-20261014-v1/source-freeze.json): `8b97ee0537ef7f80ee1685a43d8015d57ac6a267bf38aca79f6c97f7634d9a07`.
- [Python cases](../../build/oct14-purpose-python-tests.json): 72/72, SHA-256 `c1e3dc83e25ce59eaea77d69a286b4584bbdd6409d54cf141fd38bf370d60f00`; [PowerShell cases](../../build/oct14-purpose-powershell-tests.json): 72/72, SHA-256 `80d8f13cd50d61a6d9fac66d50f6588d2dbb87bab3d7bc2b974b70dbdd6e19f0`.
- [Native source guards](../../build/oct14-purpose-native-source-tests.json): 17/17; [checker restoration](../../build/oct14-purpose-checker-source-tests.json): 5/5; [integration checks](../../build/oct14-purpose-integration-source-tests.json): 54/54; [resource checks](../../build/oct14-purpose-resource-tests.json): 22/22; [actual dispatcher checks](../../build/oct14-purpose-dispatch-tests.json): 35/35.
- Ordered eligibility payload SHA-256: `96c13071269de9d54e9c8d7fe21d1dc329d4b61f2864a64942b4f3e302206db5`.

The next source investigation concerns fixture placement: the current spawn helper passes null spawn parameters and does not request placement relative to the controlled player. Actual prior item/player positions have not been captured, and no reviewed contract currently proves a proximity rejection rule. Any placement experiment must preserve the first-only normal insertion and distinguish requested placement, actual observed placement and insertion outcome. No production fix, equip or real-player UI/destruction acceptance is claimed.

## Baseline placement observed; explicit player-position candidate pending

The original null-parameter Spawn path has now been observed directly. Version 1 of this diagnostic failed engine compilation because it called `GetPlayerController` on a generic `Game` receiver. Runtime did not execute. A fresh version-2 packet uses the already verified `GetGame().GetPlayerController()` accessor after the existing identity guard; the failed packet and receipt remain unchanged.

- [Version-1 failed compilation](../../build/tablet-owned-profile-run-5o8z06p8/results.json): `e99ee0df34f953358c865e007cc47f29f61596d96025ef8c8bd46715f84f3c83`.
- [Version-2 source freeze](../../build/player-inventory-placement-control-20261014-v2/source-freeze.json): `1e092449ac43e391cfe1b568091c61bb3ff3d692e9fd65318a38328d58b57aa2`.
- [Version-2 preparation](../../build/game-profile-token-preparation-9bpwn7k9/results.json): `9e5c3254ba6610f8b457dbf2b9f6ee15d949fd3ef04d735a4737b69efb7920ff`.
- [Version-2 executed receipt](../../build/tablet-owned-profile-run-b5kwonnq/results.json): `895598d443e0f1025db91368215bd211f5cd45f1294b36f772f23d02d9bc1d0b`.

Version 2 compiled and completed 61 checked RPCs. All four world-transform getters returned on original FRAME 1, with their context checks and bounded display capture completed:

| Ordered sample | Recorded world-translation display | Additional native observation |
|---|---|---|
| Controlled player immediately before Spawn | `127.134 1 126.5` | Completed contextual sample |
| Spawned item immediately after Spawn | `0 0 0` | Item basis compared equal to identity |
| Controlled player immediately before Insert | `127.134 1 126.5` | Completed contextual sample |
| Spawned item immediately before Insert | `0 0 0` | Item basis compared equal to identity |

The native component-wise comparison of the two pre-insertion translations returned false. That comparison establishes different sampled positions without parsing the display strings. The displays are not exact floating-point encodings and do not establish a precise distance. These are ordered observations, not an atomic snapshot or a guarantee that the getters are free of side effects.

The original insertion still reached `time_limit`: 3,256 actual membership checks were false, three failure callbacks and zero completion callbacks were recorded, and terminal capture occurred on FRAME 3,257. The later purpose observation enumerated 18 storages. DEPOSIT and ANY selected the same row-17 hand storage, whose hand-item getter returned null; weapon/equipment selections were null. These observations remain separate from insertion success.

The completed sample set establishes placement separation on this null-spawn fixture. The reviewed installed declarations do not specify that null parameters always mean origin zero or that insertion requires a particular proximity. Consequently, neither a general engine proximity rule nor the insertion root cause is established.

Validation retained for these exact inputs:

- [Python placement codec](../../build/oct14-placement-python-tests.json): 55/55; [actual PowerShell placement codec](../../build/oct14-placement-powershell-tests.json): 55/55.
- [Python wire admission](../../build/oct14-placement-wire-python-tests.json): 8/8; [PowerShell wire admission](../../build/oct14-placement-wire-powershell-tests.json): 8/8; [checker restoration](../../build/oct14-placement-checker-source-tests.json): 3/3.
- [Version-2 native source checks](../../build/oct14-placement-v2-native-source-tests.json): 23/23; [version-2 integration checks](../../build/oct14-placement-v2-integration-source-tests.json): 66/66; [version-2 resource checks](../../build/oct14-placement-v2-resource-tests.json): 22/22.
- [Unchanged action dispatcher checks](../../build/oct14-placement-dispatch-tests.json): 35/35. The failed version-1 compile remains a failure; source checks alone did not establish engine compatibility.

At that checkpoint, a fresh candidate explicitly requesting the controlled player's position at Spawn was authorized and being prepared, with its engine result still pending. It was required to retain the first-only normal insertion and distinguish requested placement, observed placement, and the actual insertion outcome. The later executed result appears below. No equip, real-player UI opening, interaction, destruction, or production promotion passed through this baseline checkpoint.

## Explicit player-position candidate: actual insertion passes

The isolated candidate now completes actual tablet insertion through the normal native inventory path. It requests WORLD Spawn parameters using the already captured player translation, with identity basis, scale 1 and no parent. It retains one Spawn, the first and only public Insert request on the same genuine FRAME, the existing callbacks, and actual membership checks. The production prefab and live MESH files are unchanged.

- [Executed candidate receipt](../../build/tablet-owned-profile-run-4ljkiqem/results.json): SHA-256 `311ac643eb0f47d56fd097968f08b64b4b4edab7109f42d01073dad0717d90ab`.
- [Candidate preparation](../../build/game-profile-token-preparation-6698jb9t/results.json): SHA-256 `68105ea56f4a4d4f1031538f2809ab76be90db005265f03ab60c2e3280730e8e`.
- [Candidate source freeze](../../build/player-inventory-player-placement-control-20261014-v1/source-freeze.json): SHA-256 `da2640cb7080aadfa392a8ea78d1a10561ef9878b5c50b6b080f5a52bd8c4cfa`.
- [Selected actual evidence exported from that receipt](../../build/oct14-player-placement-success-summary.json): SHA-256 `266ecb42cfdbd24ba2987700dc567f1826f4147c68e0d7fd5ce94b1432cb33b1`.

| Executed observation | Result and scope |
|---|---|
| Complete protocol | 24 checked RPCs. |
| Original insertion | `inserted` on FRAME 1; one public Insert request. |
| Same-item membership | Actual `Contains` changes from false before insertion to true on the first post-insertion check. |
| Native callback receipt | Two failure callbacks and one completion callback; all three callback entries and returns are recorded. These are outcomes inside one public insertion request. |
| Immediate manager return code | Raw value 0; successful membership is established independently. |
| Post-insertion parent observation | Case 2 observes a parent slot and storage; the parent owner matches the controlled player in the same world. |
| Placement capture | All four ordered FRAME-1 world-transform samples complete with verified context. Each translation display is `127.134 1 128.5`. |
| Native comparison facts | Pre-insertion player/item translation equality is true; both observed item bases compare equal to identity. |
| Callback inspection | The genuine existing `inspect_callback` action verifies the frozen original/live callback receipt in the active owned session. |
| Timeout-only terminal diagnostic | Case 3 is explicitly unavailable because the original insertion succeeded. |
| Purpose probe | Explicitly `not_run`; no eligibility arm, read, or case-4 query is presented as executed. |

The display strings remain opaque observations, not exact float encodings or distance measurements. Native component comparisons supply the separately recorded equality facts.

This is observed insertion success following a bounded fixture-placement repair. It does not establish a universal engine proximity rule or isolate distance as the only causal variable: the successful session has 16 storages, compared with 18 in the null-spawn baseline, and the player positions differ between sessions. The earlier failures, source captures, prefab experiments, and unmatched controls retain their own scope. No manual held/focus state change or synthetic gameplay callback substitutes for this result.

The coordinator now handles both real outcomes faithfully. Successful insertion drains the existing diagnostics, performs the existing callback inspection, and follows the successful Stop/poll path. The timeout path retains the separate purpose diagnostic and original failure reason. Before engine execution, the complete-ledger consumers passed 16/16 Python and 16/16 actual PowerShell replay cases, including explicit synthetic success fixtures and negative action-order/membership/inspection cases. Those synthetic fixtures remain harness evidence; this receipt supplies the separate actual engine result. Exact checker restoration passed 3/3. Final integration passed 69/69 after a formatting-sensitive source guard failed 68/69 and was replaced by checking the parsed proof literal; the failed receipt remains preserved.

Actual equip/activation, real-player UI opening and interaction, stowing, destruction, ownership handover, multiplayer, visual acceptance, and production promotion remain open. The next step is to extend this verified insertion setup through the normal gadget/player lifecycle while retaining its original membership and callback evidence.

## Equipment prerequisite admission repaired; runtime result pending

The next isolated candidate adds a read-only equipment observation after the already verified insertion and genuine callback inspection. One subsequent FRAME records parent slot/storage, gadget mode and association, selected equipment storage/suitable slot, and final context/continuity. Its 34-field metadata distinguishes unexecuted groups from returned false/null observations. It does not invoke Equip, change gadget mode, open UI, or exercise destruction. Original insertion and the additional observation retain separate outcomes.

The first integrated packet passed its source and consumer tests but failed the unchanged runner's admission check. Its manifest used `source_frozen_after_root_checks`; the runner requires `experimental_source_frozen`. This was a packet metadata defect, not an engine compilation or gameplay failure. Neither the host probe nor the engine executed in that rejected attempt.

- [Preserved version-1 freeze](../../build/player-equipment-prerequisite-control-20261014-v1/source-freeze.json): `66b7b5d61f88c713a92238d4ce093f6baca333d0a8b10fd5ae09acd90882bac8`.
- [Version-1 preparation](../../build/game-profile-token-preparation-42_tllur/results.json): `40f7974031c1ce397fc2326e68d5e2e3a471eb5ae995713228cb59109566ae96`.
- [Rejected admission receipt](../../build/tablet-owned-profile-run-95b1nwru/results.json): `d46ab687e0d91d4439b1350192ebb5ccc945cfad5e38d517e6464df875a91812`.

The fresh version-2 packet retains all 74 original source members byte-for-byte. It corrects the manifest status and adds an explicit post-freeze guard and provenance note. The strict runner is unchanged. The guard checks the completed freeze's status, shape, profile and current source hashes, and rejects the preserved version-1 metadata.

- [Version-2 freeze](../../build/player-equipment-prerequisite-control-20261014-v2/source-freeze.json): `dc742a8eac7444c8b61278eccbb18cd4a33d86ae23299823495cbbaac20b9e1b`.
- [Admission correction and unchanged-input scope](../../build/player-equipment-prerequisite-control-20261014-v2/ADMISSION_FIX.md).
- [Actual post-freeze guard receipt](../../build/oct14-equipment-prerequisite-freeze-v2-tests.json): 9/9, SHA-256 `683cc33f662ade17e1f1b713d1e8d72d5ff5f36a6912ff38cf380e717c07c835`.

Existing checks remain evidence for their exact unchanged inputs: native source 32/32; equipment codecs 60/60 in each language; complete-ledger consumer tests 20/20 in each language; checker restoration 4/4; integration 79/79; wire checks 13/13 in each language; resources 22/22; dispatcher 35/35. Synthetic equipment metadata in those tests is not native execution evidence. The packet also uses fresh scalar records for each placement/equipment serialization; whether the previous repeated-Pack warning disappears requires the actual engine log.

At this source-admission checkpoint, the owned version-2 runtime was underway and its equipment result was pending; successful insertion was then the latest completed engine gate. The later actual equipment result appears below. Equip, actual player UI/interaction/destruction, multiplayer, visual acceptance and production promotion remained open.

## Equipment prerequisites observed: tablet is already in hand

The version-2 candidate completed engine compilation and the owned runtime with 25 checked RPCs. The original insertion result remains successful: one first-FRAME Spawn/Insert attempt, actual same-item membership changing from false to true, two failure callbacks and one completion callback with all three entries/returns, and genuine immutable callback inspection. The separate equipment observation then completed its single subsequent FRAME and all five groups.

- [Actual equipment receipt](../../build/tablet-owned-profile-run-ffuttmah/results.json): SHA-256 `3289356164767a0c739f25059e244365fb89ddb8dc49152a576c30d3b0e32544`.
- [Preparation](../../build/game-profile-token-preparation-206fa_1t/results.json): SHA-256 `fa126c1074a0deb3a2de667c28e502b986308cdb441c3a9dcaacf14e21b51c73`.
- [Bounded actual-evidence summary](../../build/oct14-equipment-prerequisite-success-summary.json): SHA-256 `8db855726715ab72c344cd373b58729927c5a44d182202e124a58db18c370c41`.
- [Executed source freeze](../../build/player-equipment-prerequisite-control-20261014-v2/source-freeze.json): `dc742a8eac7444c8b61278eccbb18cd4a33d86ae23299823495cbbaac20b9e1b`.

| Completed native observation | Actual result |
|---|---|
| Equipment record | One request, one returned sample, one FRAME, five completed groups, sealed with no observation failure. |
| Context and inventory | Pre/post contexts verified; current membership true both before and after the observation. |
| Parent association | Parent slot/storage present; an actual hand-storage cast succeeds; the attached entity is the same tablet. |
| Gadget mode | The native `EGadgetMode.IN_HAND` comparison is true; `IN_SLOT` and `IN_STORAGE` comparisons are false. Raw mode 3 is retained, not used to infer the symbolic meaning. |
| Owner association | Character owner matches the controlled player; the gadget manager reports ownership. |
| Equipment-attachment query | `FindStorageForItem(..., PURPOSE_EQUIPMENT_ATTACHMENT)` returns null. |
| Conditional suitable-slot work | No suitable-slot or attached-item getter is called after that null selection. Its default false fields are not separate negative getter results. |
| Final continuity | Parent slot and gadget mode match their earlier values within the observation. |

The tablet is therefore observed in hand after the normal insertion path without an explicit Equip request from this fixture. This closes the bounded equipment-state observation, not an Equip action or complete player interaction. The manager's current held-gadget reference and toggle state have not yet been sampled by this packet.

All four placement samples also complete, displaying `127.134 1 126.5`, with native pre-insertion translation equality and identity item bases. The displays remain opaque text rather than exact coordinate encodings. These observations do not broaden the earlier fixture result into a universal engine distance rule.

The targeted serializer scan finds zero matching warnings in this run's error, script and console logs; the previously recorded 34 placement serialization warnings are absent from that scan. This supplies runtime evidence for the fresh-record serialization correction on this exact run. Other engine warnings remain, and no general warning-free or engine-error-free claim follows. Both recorded processes exited with code 0 and confirmed exit, without recorded cleanup errors. These are execution/cleanup results; their recorded durations are not performance benchmarks.

Post-run preservation also passes: 107 compiler/runtime sources, five installed artifacts and 25 private-profile files remain unchanged in [the installation/private-profile audit](../../build/tablet-post-restart-preservation-m4ecmd22/result.json), SHA-256 `8eaeeabf3f3fc7bbe3cbd9bde771353fc48ede48bb811d3b291fc651161bd193`. The separate [operator-profile audit](../../build/operator-game-profile-preservation-zgcf96zy/result.json) preserves all 1,293 files, SHA-256 `2bf472a6d65a1dd6be539d824fd2c9515582ab35c548d9694d07e1b5375249d6`.

The next source review checks the actual held-gadget identity, `IsToggledOn`, and the normal activation path before adding a bounded interaction test. No explicit Equip, Toggle, UI opening, input initialization, or destruction was exercised here. Real-player activation/interaction/stowing/destruction, ownership handover, multiplayer, visual acceptance and production promotion remain open.

## Held observation prepared: engine execution not yet admitted

The next isolated packet adds one read-only held-gadget and UI observation after the already verified equipment observation. The existing callback inspection arms it with scalar state only. A later genuine FRAME queries the gadget manager's held entity/component references, candidate gadget mode and toggle state, and the current tablet/UI state, root and map presence. These are sequential observations, not an atomic snapshot. It invokes no Equip, Toggle, UI action, callback hook, tree verification, input registration or destruction.

The 31-field carrier has a 3,072-byte bound. Independent consumers preserve the original insertion and equipment results, distinguish returned nulls from uncompleted groups, and reject missing/duplicate fields, premature observations or changed sealed state. A rejected scalar arm retains a false original integrity flag; a later prerequisite rejection may retain true integrity. The original failure/purpose path remains unchanged.

The [V3 checker source](../../build/player-held-observation-checkers-20261014-v3/CHECKER_HANDOFF.md) follows a retained implementation failure: V2's persistent-JavaScript patch closure updated derivation metadata without applying the two consumer guards to the written bytes. The new negative case then remained accepted (24/25), while exact reverse derivation failed (2/4). Those failed receipts and V2 sources remain preserved. V3 applies direct checked replacements; the same negative is now rejected. No native behavior was changed by this correction.

| Verification | Evidence |
|---|---|
| Python held codec | [61/61](../../build/oct14-held-python-tests.json), SHA-256 `52bf177d3cb5a0b74e3210924fc33513520a47286833390402abf30174870464`. |
| Actual PowerShell held codec | [61/61](../../build/oct14-held-powershell-tests.json), `84e435b1d06919cd9f22b4b3bacca42bfaa9471ed7a6dff6deeb10c13ea7b6f3`. |
| Preserved V2 ledger failure | [24/25](../../build/oct14-held-ledger-python-v2-tests.json), `43d18fdf598e96c7b95721d50cb67769b174fb458512a4b8919bb33cfa61b57b`. |
| Preserved V2 restoration failure | [2/4](../../build/oct14-held-checker-source-v2-tests.json), `00b31d9d0f050dd089171b266ec6a0a5e07a0189babc5603ed8643aa3ac08bb9`. |
| V3 Python full ledger | [25/25](../../build/oct14-held-ledger-python-v3-tests.json), `8f449395277caf34dee2b460554ef6695dfadffa3a9f0fa780b4ad22fe9612d6`. |
| V3 actual PowerShell full ledger | [25/25](../../build/oct14-held-ledger-powershell-v3-tests.json), `2fa95cbc4ba5a558be5cfa4377813006f91aee7fa027acb4d9cbcdc5514f63b2`. |
| V3 exact source restoration | [4/4](../../build/oct14-held-checker-source-v3-tests.json), `cbc1fcb53fe5d4fddd43a89f55ea92ed633df296cd62d3263b2cf15b57390b10`. |

The held metadata and added polling in these ledger tests are explicitly synthetic, based on the actual equipment-success ledger. They do not prove engine execution. The V3 actual PowerShell coordinator replay also completes 25/25, with per-case progress output. The [checker freeze](../../build/player-held-observation-checkers-20261014-v3/source-freeze.json), SHA-256 `486563bfbc8a8d7399a3e5c085e2d774d43426c24bd580e85ddce1dac4f315df`, retains 32 exact source/test/provenance members. The preceding long replay showed active CPU work and ultimately passed; elapsed silence alone was not evidence of a stalled PowerShell process.

At this preparation checkpoint, a fresh engine launch was held because the [bounded host snapshot](../../build/oct14-host-space-observation.json), SHA-256 `b9e6a5bfe3f6769ea2333ae7909f20593053bc3bcacaec897818f79f44ef25fd`, recorded 2,106,740,736 free bytes on C:, below the unchanged 2 GiB preflight guard. The snapshot does not establish what consumed the space. The actual equipment observation above was then the latest completed engine gate. The later held-gadget result appears below.

The final integrated [control-v2 freeze](../../build/player-held-observation-control-20261014-v2/source-freeze.json), SHA-256 `44611ab8021e1490025f76e38f46cc042b25fd0347d0606f967c990237b5ef83`, imports all 32 checker members exactly. Its [post-freeze admission guard](../../build/oct14-held-freeze-v2-tests.json) passes 10/10, SHA-256 `ba6ab3e0c9c42f56047eca5c4a65eb38088d6f9474f19a8ba9380d57caa345ff`. This closes the source-freeze admission gate, not compilation or runtime. The [frozen command handoff](../../build/player-held-observation-control-20261014-v2/HANDOFF.md) was written before that guard ran; its pending guard note is superseded by this receipt.

After fresh host readiness satisfies the existing resource guard, the root execution owner can use the existing commands from the repository root. All receipt destinations must be fresh; preparation prints its new receipt path and exact SHA-256.

```text
python build/player-held-observation-control-20261014-v2/verify_freeze.py --result <fresh-guard-receipt.json>
python build/player-held-observation-control-20261014-v2/prepare.py
python build/player-held-observation-control-20261014-v2/run_profile_job.py --preparation <new-preparation-results.json> --expected-preparation-sha256 <printed-sha256>
```

The last command performs the wrapper's non-executing admission path. Add `--run` only when the owned engine job is ready to execute. No old prepared job or compiled addon should be reused. A subsequent host check reported 1,950,085,120 free bytes (about 1.82 GiB), so execution remained held until the later resource recovery below. Source admission does not override that disk guard.

## Actual held observation passes: inactive tablet, no UI yet

After the user's resource recovery, C: reported 7,815,364,608 free bytes. The root closed six path/start-time-verified Discord processes under the existing explicit approval, prepared fresh sources, passed non-executing admission, and completed the frozen control-v2 owned job. The host probe, engine compilation, runtime and independent verification all passed. No frozen source was changed or previous prepared job reused.

- [Executed receipt](../../build/tablet-owned-profile-run-ak8qjwh7/results.json): SHA-256 `2a8b9e2ef93bbbfb39284293c0b8c4ab2a48f0ab7727c162ade56a3b2ca69756`.
- [Fresh preparation](../../build/game-profile-token-preparation-0iyyjodl/results.json): `b971bb21a69063461f817867b8e51da3b29b225a75cbd85d6e257309170da085`.
- [Non-executing admission](../../build/tablet-owned-profile-run-0qz_0y64/results.json): `441d1785f413d0afc3e64a8fc39493a3730ce0d27825150cf039b0b0766a6914`.
- [Bounded actual summary](../../build/oct14-held-success-summary.json): `e1498178719dd7b6a95236e06b686fe95550bd4c6a1abd7916a23380220dbc68`.
- [Unmodified actual RPC fixture](../../build/oct14-held-success-ledger-fixture.json): `a00befff17fa0608c6b15252a99bc4badb5474965d79b3ae289b2f5a55433d78`. Later synthetic activation records must remain labeled separately.

The complete protocol contains 25 checked RPCs. Original insertion still passes on its first FRAME, with actual membership changing from false to true and the same two failed/one completed callback pattern within one Insert request. The separate equipment record completes all five groups. The later held record completes one attempt and three groups with both context guards, no failure and immutable sealing.

| Actual held/UI observation | Result |
|---|---|
| Held entity | Present and exactly the candidate tablet. |
| Held component | Present and exactly the candidate gadget component. |
| Native mode | Symbolic `IN_HAND` comparison true; raw value retained independently. |
| Membership and ownership | Current inventory membership, controlled-character ownership and manager ownership all true. |
| Toggle state | `IsToggledOn()` false. |
| Tablet state | Present, symbolic STOWED true; HELD and FOCUSED false. |
| UI | Absent. UI open/root/map getters therefore were not executed; their false fields are defaults. |

These are sequential reads in one held-observation FRAME after equipment completion, not an atomic snapshot or observations after world teardown. The engine's held-gadget state and the tablet's own lifecycle state are distinct; STOWED before activation is not by itself a bug. The result supplies a valid starting point for a fresh, guarded ordinary `ToggleHeldGadget(true)` test. This packet itself makes no Toggle request and proves no UI-opening causation.

Both engine processes exited with code 0 and confirmed cleanup, with no recorded cleanup errors. Targeted placement/equipment/held serializer-warning scans match zero lines in error, script and console logs; unrelated engine warnings are not suppressed. Post-run [installation/private-profile preservation](../../build/tablet-post-restart-preservation-2ullod5n/result.json) passes for 107 sources, five artifacts and 25 private payloads, SHA-256 `8eaeeabf3f3fc7bbe3cbd9bde771353fc48ede48bb811d3b291fc651161bd193`. The [operator-profile audit](../../build/operator-game-profile-preservation-zibmcmxq/result.json) preserves all 1,293 files, SHA-256 `2bf472a6d65a1dd6be539d824fd2c9515582ab35c548d9694d07e1b5375249d6`.

Next: a separate activation packet must recheck current held identities, membership, owner, mode and inactive/UI-absent preconditions, make one ordinary manager request, and distinguish request return, genuine callback delivery and later UI observations. It must not call `Focus`, `SetHeld` or a callback manually to simulate the player path. Actual activation/UI interaction, stowing, destruction, input initialization, visual review, multiplayer acceptance and promotion remain open.
