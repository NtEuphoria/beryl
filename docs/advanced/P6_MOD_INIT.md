# P6: create a scalar component authoring project

This slice adds a source-project starter through the existing local mod CLI. It
uses the current strict version-2 scalar component profile and does not expand
engine admission. Its purpose is to let an author start with editable Beryl
logic, a companion description and meaningful tests without copying a private
SPARKOS probe.

## Command

From an existing parent directory:

    beryl mod init --template scalar-component --project ./MyComponent \
      --name "My component" --addon-id MyComponent --addon-guid <16-uppercase-hex-digits>

The example uses line continuations for readability; pass these arguments on one
line in PowerShell. The addon GUID is required input. Init neither borrows a
fixture GUID nor reserves/checks the identity in an engine registry. An optional
repeatable --dependency argument supplies existing addon GUIDs in explicit
order. Duplicate dependencies and self-dependency fail validation.

The project destination must not exist, even as an empty directory. Its parent
must already exist. Linked destinations/ancestors and parent traversal are
rejected. Creation uses an exclusive directory operation followed by exclusive
file writes; existing files are never replaced. A failed write leaves its owned
partial project intact and reports its location and successfully written prefix.
Init does not delete files to roll back uncertain state. Use another fresh
destination after inspecting any reported partial output.

The name follows the companion's printable-ASCII limit. The addon ID must be an
identifier whose generated Component and ComponentClass names also fit the
existing 120-character limit. Engine-facing names beginning with Beryl in any
letter case are reserved. Init and final wrapper generation use the same public
name validator, so these names fail before any project directory is created.

## Created source files

| File | Role |
|---|---|
| beryl.mod.json | Strict v2 description and explicit native, Enfusion and test source sets |
| src/component.be | Public plain scalar state and the three admitted handlers |
| tests/component_test.be | Six tests importing that same implementation |
| README.md | Explicit next commands and support boundaries |

Rendering is deterministic for identical arguments and the same installed
catalog. File hashes, a combined file-manifest identity, compiler/tool/schema/
contract identities and the declared binding identity are returned as JSON.
No timestamp or machine path is embedded in the project files.

The state contains active: bool and last_delta: f32. Initialization activates and
resets it; active frames record the latest binary32 input; deletion deactivates
it. The handler does not accumulate an unbounded counter or elapsed sum. Tests
cover defaults, initialization, active/inactive updates, deletion and
reinitialization, using exactly representable binary32 fixtures. They make 13
assertions across six cases and spell explicit inout at all 13 mutable calls.

The fixed logical module is starter.component. Combining multiple starter
implementations in one source set requires renaming the module and corresponding
imports and companion references together. Engine class names are derived from
the supplied addon ID.

## What the command establishes

Init validates its generated description against the installed v2 schema and the
existing component contract catalog before creating the directory. It declares
that catalog's engine applicability; it does not inspect the user's installed
engine or establish runtime contracts.

Its successful result means source creation only:

- execution remains not_run; compiler checks, tests and engine execution are
  separately marked not_run.
- artifact_sha256 is null, with no engine logs or performance measurements.
- no compiler, engine, arbitrary project script, scenario, promotion or network
  operation is invoked.
- initialization runs before the existing mod Job creation path. The C mod
  dispatcher already forwards explicit arguments and needs no change.

The wrapper profile still admits only depth-one scalar state and its existing
OnPostInit, EOnFrame and OnDelete callback mappings. It does not add properties,
resources, prefab composition, UI layouts, engine references or new callbacks.
Version-2 verify and promote remain explicitly unavailable.

## Explicit next operations

From the created project:

    beryl mod plan --project .
    beryl mod check --project .
    beryl test --backend reference src/component.be tests/component_test.be
    beryl test --backend native src/component.be tests/component_test.be
    beryl test --backend differential src/component.be tests/component_test.be
    beryl mod build --project .

Reference and native execution are separate evidence. The reference backend
does not need a native compiler; native/differential execution needs Clang.
Mod check validates both source targets and the exact handler signatures.
Mod build produces generated EnforceScript and source mappings in an immutable
candidate. It does not execute an engine compile, deploy or run gameplay.

## Verification implementation and current evidence

scripts/verify-mod-init.py has a fixed nonempty inventory: 35 pure cases, or 43
with explicit compiler integration. It rejects missing/duplicated/reordered cases
before reporting success, retains source hashes, failed cases, exact commands,
raw outputs and applicable execution receipts in a fresh build/mod-init-* folder.

The pure cases check deterministic rendering, schema/catalog admission, real
imports, explicit access modes, dependency rules, malformed arguments, literal
path metacharacters, existing destination preservation, absent parents, traversal,
linked ancestors, partial/short writes, cancellation, changed tools and init dispatch without
process or Job creation. Engine-name regressions cover ordinary accepted names,
all-uppercase/lowercase/mixed-case reserved prefixes, shared-policy calls and
absence of output for rejected names.

Integration is explicitly selected:

    python -I scripts/verify-mod-init.py --beryl <private-compiler> \
      --clang <clang> --expect-compiler-sha256 <exact-compiler-hash>

That gate uses the real C CLI with the source mod tool selected explicitly. It
checks and builds the starter, confirms generated class names and mapped origins,
runs all six tests through reference/native/differential modes, and verifies that
a deliberate implementation mutation fails the imported tests. It also checks
that v2 engine verification and promotion remain unavailable.

An early actual compiler run found omitted explicit inout call modes in the
test template (BE0303). That failed starter was preserved; the template now
includes the required modes and the pure inventory checks all call sites. A
runner source review also corrected its expected native summary to the actual
runtime text, "ok  6 tests, 13 assertions". The first integrated run reached 35 successful cases before its loaded older
native-output assertion failed, despite the native program itself returning zero
and the expected six-test summary. Its receipt is retained at
build/mod-init-b1g52bfg/results.json. The earlier corrected implementation passed
all **41/41** integrated cases at `build/mod-init-bhy5ctu4/results.json`, SHA-256
`6f170bf991b4cebbb4e799f5fab73574ef6dc6bcb123838fbcb8c66d50b6a79c`.
The private compiler SHA-256 is
`89a8b2de5f03688462c280463445bcb94a6cf27f44979762d3dd77422f4cff97`.
This includes actual C CLI dispatch, check/build, six tests with 13 assertions
through reference/native/differential execution, the detected implementation
mutation, and unavailable v2 verification/promotion. Engine execution remains
outside this slice, and the active installed compiler/tool bundle is unchanged.

A subsequent actual installed CLI demo exposed a missing early name check:
BerylScalarDemo passed init/check, but wrapper generation correctly rejected the
reserved Beryl prefix. The failure remains recorded in
build/oct14-core-authoring-ar87qcbi/results.json. Init now calls the exact shared
engine-name policy before creation. That repair adds two pure regression cases.
The final **35/35** pure cases pass at
`build/mod-init-9k1248d0/results.json`, SHA-256
`6565ae21ea1b38e968da7411c5f2bc15b7b18620890df0e68b0889a5358721e3`.
All **110/110** existing generator cases and all **10** component-workflow groups
also pass at `build/component-generation-gulctv_v/result.json` and
`build/component workflow & spaces-x0khfy3b/results.json` respectively.

A fresh installed-tool demo then passes actual CLI creation, checking, six
reference tests with 13 assertions, and immutable source generation:
`build/oct14-core-authoring-fscdr_z0/results.json`, SHA-256
`5a2bbd886c3927d88a0b09b45ae35594ec9a365e7f8b30ce667c28f7da559680`.
It uses the private compiler's current installed bundle without a source-tool
override. The final 43-case integration inventory has not run: Windows Code
Integrity blocked generated native execution during the companion IR matrix.
The earlier 41-case result applies to its recorded bytes; it is not a full
final-tool receipt. See [the consolidated checkpoint](CORE_AUTHORING_2026_10_14.md)
for identities, retained failures and the execution limitation.

## Source scope

Changed implementation: tools/beryl-mod/mod.py and a shared pure name validator
in tools/beryl-mod/component_generation.py. Added focused verification:
scripts/verify-mod-init.py. This document is the implementation note.

The original inspected mod.py SHA-256 was
98ccf477cd340da95a7c1e59a659cbdabc50490dfee1042138eafb04b713fd2e.
Existing unrelated source changes were preserved.
The installed bundle already includes mod.py, so no additional bundle payload
member or loader inventory is introduced. Activating an updated installed tool
bundle remains the installation owner's operation. No new MCP mutation tool is
advertised by this change.
