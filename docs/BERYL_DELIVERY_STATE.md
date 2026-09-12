# Beryl delivery implementation state

Updated 2026-09-07. Status: **verified foundation/tooling checkpoint installed;
delivery program incomplete**. Completion is evaluated per capability; this file
does not replace immutable verification receipts.

## Current installed checkpoint

The active `build/beryl.exe` is SHA-256
`81c227eef60670da6f22c8cb6a0e68510c48d1d281dd2ca36e9231c7dd35e8d6`.
Its 21-file optional tool bundle is
`b8ea292c71237a27c938ea162f5a58ba52d49a7680a786bdec25017482db3730`.
The compiler capture is `build/delivery-order-final-oopz_pd3/snapshot.json`.

The [installed receipt index](../build/delivery-installed-checkpoint.json) records
15 successful scoped receipts. Index SHA-256:
`1d7be87be847167ff8c22fa6186456d24e4bcb511c185fe524c7dd15cbef8298`.
An identical copy is beside the installed compiler at
`build/verification/81c227eef60670da6f22c8cb6a0e68510c48d1d281dd2ca36e9231c7dd35e8d6/checkpoint.json`.

This installs checked allocation helpers, parser limits, destination and owning
copy containment, stronger taint propagation, truthful capability/example context,
environment inventory, exact-snapshot analysis and the optional local MCP bridge.
It also repairs confirmed aggregate/List/vector evaluation-order defects and
rejects untracked files in installed tool bundles before importing them.

| Final compiler evidence | Outcome |
|---|---|
| Normal and UBSan foundation | 496 cases / 10,285 checks in each mode |
| Native regression programs/modules | 18 at O0 and O2, including aggregate/intrinsic ordering |
| Driver | 11 groups / 41 commands |
| Exact snapshot analysis | 64 passed; symbolic-link creation capability unavailable |
| Context / doctor / capability registry | 9 / 8 / 6 groups |
| MCP protocol, CLI parity, faults and installed bridge | 17 groups |
| Mod artifacts and hardened loader | 12 groups |
| Source maps / expected traps | 7 / 9 groups |
| Real Workbench integer and order execution | 560 fixtures / 867 checks |
| Complete original/generated PID comparison | 2,195 operations / 65,850 comparisons |
| Actual installed-path smoke | Version, inventory, context, semantic check, native test and MCP bootstrap passed |

The 560 engine fixtures include 559 reference/native/engine cases and one
independently specified native/engine-only vector case. No reference/IR Vec3
coverage is implied. Workbench VM execution is separate from gameplay, dedicated
clients and visual acceptance.

Activation receipt:
`build/checkpoint-81de375b3c2c4cec963f0a23b4ba15d5/receipt.json`.
That directory preserves all previous mutable installation bytes and the exact
manifest. The activation helper passed 13 isolated groups, including a complete
activation/rollback cycle and failure-preservation cases. Individual replacements
are atomic; the sequence requires quiescence and is not a multi-file transaction.
The live installation passed its own post-activation smoke. A live rollback was
not performed merely to repeat the isolated rollback test.

No live MESH files, resource identities, client configuration, or global PATH
were changed. No complete tablet, whole-mod release, automatic optimization or
Rust performance advantage is claimed.

## Objective and success criteria

Implement the approved delivery program: trustworthy compiler foundations,
verified IR and admitted ownership, the complete existing MESH tablet lifecycle,
shared AI tooling, deployment acceptance, whole-mod authoring, and measured
performance releases. Preserve current semantics, working-tree changes, engine
object identity and rollback evidence. Every release must pass its own gates.

## Captured starting point

- Source snapshot: `build/delivery-baseline-b742d5aaf916468485134457aa2af2bf`;
  288 repository inputs and 106 MESH script/resource hashes. This is a capture,
  not a new verification run.
- The sandbox could not read the installed executable or earlier installation
  receipts. That failed read remains recorded in the tool output. A separate
  authorized identity capture succeeded at
  `build/delivery-identities-4c3218c0d8a643b3b81032209cb4ca5a/manifest.json`.
- Installed compiler SHA-256:
  `aa7e9d51360cb8980f51e69313f0d8ee4dda59e54c3319f34697087b6a9d9b04`.
- Engine SHA-256:
  `7dd36ca1f662b0c13669a4f2f7f10e3c461c2906b021e742272d64b3ab7e9798`.
- Prior applicable evidence remains in `BERYL_ADVANCED_IMPLEMENTATION_STATE.md`.
  It does not establish that subsequently changed bytes passed.

## Current work and owners

| Work | Owner | Return condition |
|---|---|---|
| Plan, integration, taint/range safety, documentation | root | Integrated source and exact test receipts |
| Fixed-array IR and interactive process dispatch | native_compiler | Private verification, independent review and integration |
| Independent IR/MCP review and tablet inventory | incremental_semantics | Bounded verification and retained exact-source contracts |
| Exact-snapshot analysis and bounded JSON input | sitrep_gaps | Shared C API, CLI and malformed-input verification |

The workers own separate files. Root integrates shared test registration and
diagnostic documentation. No worker installs the active compiler.

## Checkpoint status

| Checkpoint | State |
|---|---|
| R0 safety and truthful capabilities | Installed bounded P0/P1 foundation; full resource/effect guarantees remain open |
| R1 IR and owned storage | Experimental array IR evaluator and private IR-C parity; no public IR or owned-storage release |
| R2 complete tablet candidate | Pending typed bindings and generation |
| R3 dedicated-client PvE pilot | Pending; independent-client availability unverified |
| R4 whole-mod authoring and editor | Pending |
| R5 adopted performance releases | Pending; existing terrain timing remains exploratory |

## Historical first implementation checks

- Shared destination protection: isolated baseline-plus-owned-files UBSan run
  passed 30 cases / 158 checks; CLI exercised 154 unsafe command variants plus
  safe native/reference/Enfusion and full PID comparisons. Packet:
  `advanced/P1_DESTINATION_SAFETY.md`.
- Allocation expanded slice: isolated O0 and O2+UBSan runs passed 27 cases / 865
  checks and 20 rejection/failure probes per build. The portable verifier retained
  evidence at `build/allocation-x6qa8ztf/results.json`; string/map arithmetic is
  included. This is not an integrated receipt. Root regenerated the embedded
  runtime after the allocator source freeze.
- Capability catalogue: 7 cases / 65 checks, six new CLI groups and nine existing
  context groups passed against a captured baseline with registry-only overlay.
  Packet: `advanced/P0_CAPABILITY_REGISTRY.md`.
- Integrated development smoke: 399 cases / 3,201 checks passed at
  `build/delivery-unit-8dd9228cf974425a9f6c5137d5a37b78/unit.log`, including new
  taint tests and unchanged IR PID 8 tests / 2,206 assertions. This compiled the
  developing tree; it is not yet an immutable release/foundation receipt.
- Taint source now preserves provenance, proves bounded fixed-array indices
  separately, tracks field/element writes and propagates calls/returns/mutable
  arguments to a bounded fixed point. This initial implementation is conservative
  and context-insensitive; full symbolic summaries and dynamic-storage bounds
  remain separate follow-up work. New BE0608 fails on exhausted analysis limits.
- Doctor isolated verification: eight groups passed at
  `build/doctor & spaces-cyw2nfex/results.json`, including a real native compile/run,
  invalid/missing tools, malformed bundle metadata, timeout and cancellation.
  Inventory does not launch the engine; the Enfusion probe remains unavailable.
- Root additionally uses checked pointer-array allocations in main/mod dispatch
  and bounds Windows path resolution buffers, rejecting changed required lengths.
  These changes await integrated driver verification.

## Retained failed integration attempts

The first fixed integrated capture contains 326 files at
`build/delivery-candidate-2u9xx3_h/snapshot.json`. Both foundation modes retained
failures: `build/foundation-syw5tokx/results.json` and
`build/foundation-4ztt4xyb/results.json` under that capture. They ran 462 cases /
3,574 checks and failed nine checks. The new storage gate was too conservative
for an already captured scalar argument; that admission rule is being repaired.
An old optional-record-field test expected shallow wrapper copying to pass; its
source is retained as an explicit unsupported-copy regression, with a separate
positive local-wrapper representation case. These attempts remain failures.

Further failed captures remain at `delivery-candidate-0aa5ra5l` (a capability
test assumed registry ordering) and `delivery-candidate-bbl91sps` (a generated
temporary-name assertion was incorrect). The intervening `delivery-candidate-ucd3l51b`
passed before the additional compound-assignment repair. These receipts retain
their original outcomes; no failed attempt is relabeled as a pass.

Independent O2+UBSan taint review passed at
`build/taint-independent-ig1sn08l/results.json`. It detected missing catch-binding
and propagated-try return provenance; both are repaired. Deleting either fix
reproduced the missed diagnostic. This is bounded regression evidence, not a
whole-security proof.

## Historical verified P0/P1 candidate

Exact input capture: `build/delivery-candidate-n24elssl/snapshot.json` (326 files).
The verified receipt index is `build/delivery-p0-p1-checkpoint.json`, SHA-256
`9e207c28206901a0c799cb437e8074f9d6df6709ecfbb47584830f50795c5609`.
It identifies 21 successful receipts and explicitly excludes the failed source-map
attempt. Normal candidate compiler SHA-256:
`45f773ea905ee76ce6bcf3d01ed089d2a14958429c660e6d5fa18ed173ad9c29`.
Under that immutable capture, both foundation modes passed **466 cases / 3,590
checks**, with **16 native program/module checks at O0/O2**:

- Normal compiler: `build/foundation-xeb3f85s/results.json`.
- UBSan compiler: `build/foundation-fqvy3wwv/results.json`.

Additional receipts under the same capture:

| Coverage | Receipt | Outcome |
|---|---|---|
| Driver, concurrent jobs, startup/write failures, cancellation | `build/driver & spaces-8ieah4ys/results.json` | Passed |
| Reference semantics | `build/reference-7oeb8wpi/results.json` | 6 groups passed |
| Expected traps and successful prefixes | `build/expected traps & 07ms_j0_/results.json` | 9 groups, including 10 deliberate mutants |
| Native evidence | `build/native evidence & spaces-8gml86zg/results.json` | 18 groups passed |
| Environment doctor | `build/doctor & spaces-t7t7s_nu/results.json` | 8 groups passed |
| Taint and range separation | `build/taint-np2dpsme/results.json` | 34 target checks passed |
| Context and source locations | `build/context & spaces-v77laq_r/results.json` | 9 groups passed |
| Mapped diagnostics | `build/map-diagnostics-5qthjr5a/result.json` | 4 groups passed |
| Offline mod/artifact contracts | `build/mod & spaces-4ed_p6l9/result.json` | 7 groups passed |
| Offline scenario receipt contracts | `build/mod-scenarios & spaces-l9o4ayvw/result.json` | 7 groups passed; not runtime scenarios |
| Owning-copy containment | `build/storage-admission-2pvkjjy1/results.json` | 11 cases / 93 rejected command paths |
| Parser limits | `build/parser-limits-c0wi6wrx/results.json` | 15 malformed fixtures plus unchanged PID |
| Checked allocation | `build/allocation-htk9niiu/results.json` | Passed |
| Destination protection | `build/reference-destinations-86xp4mor/results.json` | 17 admission checks passed |
| Workbench integer/order execution | `build/engine-integers-e7tukonq/result.json` | 556 fixtures / 863 engine checks |
| Complete PID comparison | `build/pid-bd6lrk7p/result.json` | 2,195 operations / 65,850 engine comparisons |

Range bounds are now captured once, in source order, on both emitters. Enfusion
compound assignment captures the old value before an effectful RHS. The expanded
engine suite executed these cases, rather than relying only on emitted text.

Two verification-only follow-ups ran from the working repository against that
same candidate compiler: `build/source-maps & spaces-koa0ouoy/result.json` (7
groups) and `build/capability-context-ej6tkolu/results.json` (6 groups). The source-map
fixture now retains shallow optional-record copying as an explicit rejected case;
its earlier failed receipt remains at the candidate's `source-maps & spaces-jh85ih8y`.
`docs/FEATURES.md` was generated from the verified candidate. The immutable source
capture was not edited to substitute newer documentation or harness bytes.

This is a bounded development checkpoint. Full symbolic effects, complete owning
storage, all compiler resource paths, emitted IR, whole-mod authoring and deployment
gates remain incomplete. No active compiler installation or live MESH promotion
has occurred as part of this checkpoint yet.

## Next action

Continue P2 from the independently checked IR-C experiment into unoptimized
production lowering, keeping resource policies and public admission explicit.
Then admit owning-storage categories individually and implement the typed engine
contracts and companion-v2 features needed by the tablet. The captured contract is in
`advanced/P4_TABLET_CONTRACT_INVENTORY.md`; it is an inventory, not a port.

## Historical intermediate compiler/tooling integration

The array IR evaluator and bounded JSON/snapshot analyzer are integrated as source.
Their focused packets are `advanced/P2_IR_ARRAYS.md` and `advanced/P6_ANALYSIS.md`.
The optional MCP adapter uses the same CLI and supports typed context, inventory,
exact snapshots, evidence inspection and explicit test/mod operations. It remains
experimental: the complete adapter/installed-bridge gate passed, but actual
Claude and ChatGPT authoring trials remain unexecuted.

Windows argument and environment handling now preserves UTF-8 identities. The
shared process abstraction supports inherited pipes without captured-output
buffering. The Python process owner starts children suspended, attaches them to
the private job, then resumes them; attached trees have kill-on-close protection.
Focused packets: `advanced/P5_MCP_PROCESS.md`, `advanced/P6_PROCESS_OWNERSHIP.md`.
Abrupt host death before attachment may leave a suspended child that has not run
user code; atomic ownership at creation is not claimed.

Combined immutable input capture: `build/delivery-analysis-mcp-g13lv7bw`.
Normal/UBSan foundation runs passed in `build/foundation-qoybatad` and
`build/foundation-tjpa3hju` under that capture: **494 cases / 10,279 checks** in
each mode and **16 native program/module checks at O0/O2**. The normal compiler
SHA-256 is `7a7c5883c23a6a0d65cf236760f3b39ed188e3fc75f70ff74fde7965dcb74214`.
Earlier capture attempts that saw
concurrent verifier edits retain failure, and an earlier sandbox-created capture
was unreadable to the elevated runner. The successful capture and builds use one
execution identity; no permissions or security controls were changed.

IR-to-C is now an independent private experiment. It has no public command route
or production release, and is excluded from this combined candidate.

### Combined candidate follow-up receipts

These runs use the combined compiler above and retain the applicable live
verifier/tool hashes in their own receipts. They do not replace files in the
immutable compiler capture.

| Coverage | Receipt | Outcome |
|---|---|---|
| Exact snapshot analysis | `build/analysis & spaces-25pef4ns/results.json` | 64 groups; unavailable symlink-creation capability reported separately |
| MCP protocol, faults, cancellation and installed bridge | `build/mcp & spaces-7won19za/results.json` | 17 groups, including 5 real compiler groups |
| C inherited-pipe dispatch and Unicode arguments/environment | `build/mcp-dispatch-gpn06udt/results.json` | 75 checks |
| Python process ownership and hard termination | `build/process-job & spaces-4kbwppr2/results.json` | 7 checks |
| Doctor | `build/doctor & spaces-izg14wf9/results.json` | 8 groups / 28 commands |
| Context | `build/context & spaces-saaxjh5g/results.json` | 9 groups / 39 commands |
| Generated capabilities/examples | `build/capability-context-oyjdacq5/results.json` | 6 groups; generated feature table agrees |
| Mod artifacts and installed bundle validation | `build/mod & spaces-w2qnmuyu/result.json` | 8 groups |
| Offline scenario contracts | `build/mod-scenarios & spaces-5n29om3q/result.json` | 7 groups; no runtime scenario claim |
| Expected source traps and successful prefixes | `build/expected traps & 86jv3v_i/results.json` | 9 groups, including 10 deliberate mutants |
| Source maps | `build/source-maps & spaces-192e1aa4/result.json` | 7 groups |
| Native evidence | `build/native evidence & spaces-31dc19o1/results.json` | 18 groups |
| Workbench integer/order execution | `build/engine-integers-7jk8lft9/result.json` | 556 fixtures / 863 checks |

The 21-file optional bundle identity is
`b8ea292c71237a27c938ea162f5a58ba52d49a7680a786bdec25017482db3730`.
Launcher files have separate identities; a bundle hash does not cover its loader.
Independent review found that launch-time validation must also reject extra
untracked sibling files before Python imports from the bundle. This repair and
its regression were subsequently completed before the current installation above.

Retained unsuccessful follow-ups include:

- `driver & spaces-83457b_k`: the timeout fixture expired during real Clang
  compilation under load, before its intended runtime timeout observation.
  The revised fixture precompiles a real Beryl infinite loop and uses a trusted
  copying tool during the timeout case; its receipt distinguishes that setup.
- `driver & spaces-dx1jtog0`: all behavioral groups passed, but the final source
  check correctly rejected an analysis-verifier edit during execution.
- `analysis & spaces-3gn5g_hc`: the held-file observation window was missed.
  The revised bounded fixture requires observing the lock before proceeding.
- `mcp & spaces-53qhb09q`: Windows newline translation changed fixture bytes;
  the analyzer correctly rejected the mismatched hash. Fixture writing now
  preserves exact bytes.
- `engine-integers-mk85my3s` and `engine-integers-lzjkdrej`: an existing
  Workbench session prevented owned compilation or VM execution. The latter
  compiled successfully but did not execute its runtime comparison. Neither
  is counted as a semantic pass. Session-conflict fixtures and real engine jobs
  now run separately.

## Blockers and limitations

No source implementation blocker has been established. Existing build artifacts
may require authorized access outside the restricted sandbox. No live MESH
promotion, multiplayer result or new performance result is claimed. The owned
Workbench executions listed above are pure integer/PID comparisons, not host
tablet lifecycle or dedicated-client acceptance.

## Additional retained attempts and corrections

- `delivery-aggregate-cwukejvi`: both foundation attempts failed four new test
  assertions. The new fixture incorrectly assumed effectful field defaults were
  admitted; the existing frontend already rejected them with BE0501. The extra
  restriction was removed. The other new fixture used unsupported enum-member
  spelling. These were test/review assumptions, not newly established compiler
  defects. The final constant-default tests passed.
- `mod & spaces-8wtvs0ht`: Windows denied a newly created version-directory
  rename before any loader or active-pointer activation. Subsequent inspection
  found ordinary owned files, matching hashes and no persistent access/sharing
  barrier; the earlier cause is unknown. One fresh isolated run passed at
  `mod & spaces-6b3m74pg` with no source or security-setting changes.
- Confirmed initializer and intrinsic failures are retained in the independent
  IR-C and `intrinsic-order-sg38zsaa` probe receipts. The final emitter repairs
  passed both the compiler matrix and the admitted real engine cases. Details:
  [expression-order packet](advanced/P1_AGGREGATE_ORDER.md).

The private IR-C gate passed at `build/ir-c-f53bg9ro/results.json`: 36
reference/IR/IR-C cases at O0 and O2 with UBSan, including the full PID; 31 also
had AST-C comparisons. Five domain/budget cases explicitly excluded AST-C.
Six generated-C mutants and 216 malformed/configuration checks were detected.
Its resource guards are not a proof of compiler-generated stack layout, and
instrumented parity is not performance evidence. It has no public lowering route.
