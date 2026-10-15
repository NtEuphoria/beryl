# Core compiler and authoring continuation — October 14

The user requested a return to building Beryl 4GL because Reforger validation
was consuming too much of the development effort. Further engine work is
parked after the recorded ordinary tablet activation/close success. The
delivery program remains the governing plan; this is a bounded implementation
checkpoint within P2 and P6, not a new language design.

## Current implementation scope

1. Extend experimental plain-value IR with declared, initialized and moved
   root states and `set`/`sink` access modes. Existing AST contracts remain the
   comparison baseline. Production IR, automatic IR selection, owned-container
   lifecycle operations and partial moves are separate gates.
2. Add `beryl mod init --template scalar-component` to create a fresh, complete
   project using the already admitted version-2 scalar component profile.
   Include shared implementation, importing tests, companion data and usage
   instructions. New engine APIs, editor properties, prefab/layout support,
   engine verification and promotion are not part of this slice.
3. Repair `doctor` inventory for the exact current 24/25-file installed bundle
   profiles while retaining historical profiles and content identity checks.

Implementation and independent review run in separate file ownership areas.
Root owns compiler builds and test execution. No engine launch is needed for
these verification gates, and no installed compiler is replaced implicitly.

## Confirmed inventory regression

The extended doctor regression was executed against the earlier private
compiler `build/oct08-wrapper-cli-l8ci669v/beryl.exe`. Historical profiles pass,
then `profile24.valid` fails: doctor returns `unavailable` for a complete valid
current bundle. The result is retained at
`build/doctor & spaces-g0sp8ue8/results.json`.

The root cause is a stale allowed-file-set inventory in `src/driver/doctor.c`.
The installer already emits component and generation bundles containing 24 or
25 files, but that inventory only recognizes older profiles through 21 files.
The repair extends the exact profile list; it does not weaken hash checks or
claim that inventory executes or validates the loader.

## Verification status

The doctor repair passes nine focused verification groups, including the exact
25 bundle cases, against private snapshot compiler
`89a8b2de5f03688462c280463445bcb94a6cf27f44979762d3dd77422f4cff97`.
Receipt: `build/doctor & spaces-v2_kwkpj/results.json`, SHA-256
`675c313fd53b41545e98c650288ebc949ce17685f56d03ccc05a100463f88b8a`.
The old rejection remains a separate failed receipt.

An early starter execution found omitted explicit `inout` arguments in its
test template. The generated failing source is retained at
`build/oct14-scalar-starter-review`; the compiler correctly reports BE0303.
This is a template defect, not a request to weaken the language's access rules.

An earlier corrected starter passes 41/41 integrated cases at
`build/mod-init-bhy5ctu4/results.json`, SHA-256
`6f170bf991b4cebbb4e799f5fab73574ef6dc6bcb123838fbcb8c66d50b6a79c`.
Actual C CLI dispatch, semantic checking, immutable component generation and
reference/native/differential execution are included. Each execution runs six
tests and 13 assertions importing the actual implementation; a deliberately
altered implementation fails them. No engine executes.

An independent installed-tool demo then exposed a second starter defect:
`BerylScalarDemo` passed creation and checking but failed wrapper generation
because the generated engine name uses a reserved prefix. The failure is
retained in `build/oct14-core-authoring-ar87qcbi/results.json`. Creation and
generation now call the same name validator; invalid names fail before a
project directory is created. The current pure inventory is 35 cases; full
integration would contain 43. The historical 41-case receipt does not certify
the later name-policy repair.

Final focused checks for the repaired tools:

| Verification | Result | Receipt |
|---|---|---|
| Starter pure regressions | 35/35 pass | `build/mod-init-9k1248d0/results.json` |
| Existing component generation | 110/110 pass | `build/component-generation-gulctv_v/result.json` |
| Component workflow and private installation | 10 groups pass | `build/component workflow & spaces-x0khfy3b/results.json` |
| Capability context and generated feature documentation | 6 groups pass | `build/capability-context-jrt1x7ts/results.json` |
| Fresh installed-tool demo | Create, check, reference tests and source generation pass | `build/oct14-core-authoring-fscdr_z0/results.json` |

Receipt SHA-256 values in that order:

- `6565ae21ea1b38e968da7411c5f2bc15b7b18620890df0e68b0889a5358721e3`
- `3c9c161f71532c9902d484d99733b7a7c781086acc9530e13364011a21a5abe5`
- `256dcb9788206fcc07288ed18a1fb02cb7b6eb415d40275709dd1f2d99200ec0`
- `e1b2d32da665b2d09a23765de12abb73dd48c6059ba6a8b417704ea6b281f83c`
- `5a2bbd886c3927d88a0b09b45ae35594ec9a365e7f8b30ce667c28f7da559680`

The reviewable demo is at
`build/oct14-core-authoring-fscdr_z0/ScalarComponent/`. Its six reference tests
pass all 13 assertions against the shared implementation. It uses the private
compiler's installed 25-file tool bundle, with no source-tool override. It does
not execute a generated native program or launch Enfusion. Its GUID is an
isolated fixture identity, not a registered shipping addon.

### Experimental IR evidence and remaining execution block

The first IR access-mode corpus passes six tests and 26 assertions through
AST-reference versus schema-5 IR C execution at O0. Receipt:
`build/oct14-core-snapshot-ia3ue2h2/.beryl-cache/job-25596-347783796-1/result.json`,
SHA-256 `d12f3a802bb5b1af43b3ace7d8449e72217956ed8795eb8e222df9d12b0fb783`.
This is a bounded preliminary result, not the full execution matrix.

The initial unit attempt at `build/foundation-ygfdilmy/results.json` is retained
as failed: three historical tests still expected now-supported set/sink
operations to reject, and a fourth negative test now describes a legal first
assignment. The expectations were corrected, with positive access-mode tests
and a real uninitialized-read rejection added. The final unit executable
compiled, but Windows refused its launch with error 4551. The subsequent full
IR differential attempt also stopped before completing its first group because
Windows blocked a generated executable.

| Incomplete gate | Receipt | SHA-256 |
|---|---|---|
| Final foundation unit execution | `build/foundation-jzw0pu20/results.json` | `fe534202c70283bf455fc6cbce2e6bbf7c5515a63220fc70215f91107a7f80c9` |
| Full AST/IR O0/O2 differential matrix | `build/ir differential & spaces-fcqlj3nk/results.json` | `eb077f3c941cc73e0a1a49dff762234c31d27662e5fdd685b674bf801027cd25` |

Code Integrity event 3077 confirms both exact blocked paths and the same policy
identity. The read-only event capture is `build/oct14-core-code-integrity.json`,
SHA-256 `7837deddd95ea5c180f2e05711d0735e7d0ddff7016b9f2d6fb6283a6a2ef5d3`.
This identifies Windows application-control enforcement; it does not establish
which user-facing security setting supplied that policy. No security setting
was changed, and the blocked binaries were neither modified nor retried.
Final unit, full O0/O2, sanitizer and final 43-case native integration acceptance
remain open. Source generation and reference execution are separate evidence.

### Candidate identity and installation boundary

The private core candidate is
`build/oct14-core-snapshot-ia3ue2h2/beryl.exe`, SHA-256
`62760f54629074f03fe4d744916fc88fc802729b9cf38abae441a27a9101110b`.
Its exact captured sources, compiler arguments and tool identities are in the
sibling `result.json`. Its C inputs match the final implementation apart from
two subsequent documentation-comment lines in `src/ir/ir.h`; it is not a claim
that the executable was built from those final exact header bytes.

Only the private candidate's tool bundle was installed for workflow testing.
The active installed compiler was not replaced. Existing dirty changes,
historical failures and immutable engine artifacts remain preserved.

## Remaining delivery boundaries

Beryl still has no released automatic optimizer or established Rust performance
advantage. Full owning storage, production IR, whole-mod descriptions and
deployment acceptance remain incomplete. The existing engine receipts identify
their own tested bytes; they do not verify new compiler or tool source changes.
