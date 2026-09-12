# P0: compiler-owned capability and example catalogue

Date: 2026-09-07. Implemented as a bounded, additive context interface. This
packet does not install a compiler or complete doctor, analysis overlays, MCP,
LSP, complete owned storage, whole-mod authoring, or optimization release gates.

## Purpose and public interface

Give humans and local tools one compiler-owned inventory of implemented
boundaries and target-scoped examples. Keep four questions separate:

1. What implementation exists in this compiler?
2. Does the actual source set pass the selected admission rules?
3. Is the required capability available on this local machine?
4. Which verification receipts apply to these exact bytes and identities?

```text
beryl context capabilities
beryl context capabilities native.owned_storage
beryl context capabilities --target enfusion
beryl context examples
beryl context examples pid.complete
beryl context examples --target native
```

The optional target is one of `native`, `reference`, `enfusion`, `compiler`, or
`tooling`. Example target domains are limited to the three execution targets;
filtering examples for `compiler` or `tooling` returns an empty catalogue, not
a claim that examples executed. An explicitly selected ID outside the requested
target fails. Unknown IDs, repeated targets, unknown options and extra source
arguments fail with the existing structured context envelope and BE0804.

These commands are read-only. They do not load a project manifest, read example
sources, create build directories, invoke Python, run Beryl programs, or launch
Workbench. They can operate from an empty directory beside an installed compiler.
Repository paths are discovery metadata, not claims of local file availability.

`context project` remains the existing way to check actual complete loaded source
sets against reference/native/Enfusion admission. The catalogue never substitutes
its implementation label for those passes. Bindings still separate declaration
extraction from unverified lifetime/effect/authority contracts.

## Data and ownership

`src/driver/features.c` owns four immutable indexed tables:

- Features: stable ID, title, implementation state, target domain, public
  interface, bounded contract, admission rule, source, dependencies and test groups.
- Test groups: suite source and positive/negative obligations.
- Examples: explicit target domain, source set, feature/test links, usage and limits.
- Optimization families: the existing names, hypothesis IDs and prerequisite text.

The public `FeatureRegistry` representation permits malformed table fixtures in
unit tests without changing production constants. `features_validate` checks
bounded counts, required fields, IDs, target masks, source-path shape, duplicate
IDs and links, missing test groups, unknown references, dependency cycles,
unsupported example features, uncovered example targets and family identity.

Every implemented/partial/experimental feature links a registered test group
with positive and negative obligations. This establishes an auditable test
inventory; it does not prove that those tests ran or covered every boundary.
The CLI verifier checks that each referenced source exists in the repository
and records its hash. The compiler itself does not inspect those source paths.

The catalogue initially includes 23 features and three examples: native arithmetic,
native plain records, and the complete SPARKOS PID package. The PID spans distinct
native/reference/Enfusion workflows; its usage does not invent a single command
that performs every validation level.

## JSON and identity contract

The outer context envelope remains schema version 1 with its existing source,
compiler, binding and artifact fingerprint fields. The two new topic responses
contain a separate registry schema/version and metadata fingerprint.

Each feature distinguishes:

```text
implementation.status = unavailable | experimental | partial | bounded
admission.status = not_checked
local_availability.status = not_checked
applicable_evidence.status = not_checked
applicable_evidence.receipts = []
```

The fingerprint hashes deterministic serialized registry metadata: features,
test groups, examples and optimization families. It is not the executable hash,
source snapshot identity or proof of current execution. Exact compiler identity
continues to come from the outer envelope. No process pointers are serialized.

Receipt resolution is explicitly `not_implemented`. A later resolver must match
external receipts to compiler/source/tool/engine identities. It must not compile
a claim of current self-verification into the same binary that the claim identifies.

Ordinary project/symbol/optimization data gains an additive `catalogue` discovery
object. All prior fields remain. Optimization family metadata now has one owner;
its legacy JSON shape and known-family option validation are unchanged.
All families remain proposed, ineligible and unreleased.

## Verification

`tests/unit/test_capabilities.c` exposes `run_capability_tests(void)` for the
normal unit registry. Seven cases and 65 checks cover registry integrity,
malformed dependency/test graphs, target admission claims, unknown future
features, separate evidence axes, deterministic identities and family compatibility.

The isolated unit suite passed at O0 and optimized O2 with UBSan. Artifacts are
under `build/capabilities-a68ca4ad3a03478ca3574e72613cb51e`.

An isolated compiler was built from the preserved delivery baseline with only
the new feature/context files overlaid:

```text
build/capabilities-cli-a42ccedc6158472c9775991b18f85681/beryl.exe
```

The new CLI suite passed all six groups, including malformed options, exact
target filtering, unchanged prior context fields, and a no-files-created check:

```text
build/capability-context-ceqgui8a/results.json
```

The existing nine context regression groups also passed:

```text
build/context & spaces-tejjy8b4/results.json
```

These reports bind their tested inputs and compiler identities. They do not
claim the unrelated in-progress delivery changes were included, nor replace
the final integrated foundation/engine suites.

## Generated documentation and integration

`scripts/verify-capabilities.py --beryl <compiler> --write-doc` writes
`docs/FEATURES.md` from the actual compiler catalogue. Without `--write-doc`,
the script requires the document to match; it never silently regenerates it.
Metadata source changes therefore require a rebuilt compiler and deliberate
document regeneration. Test results/evidence stay outside the generated table.

Integration needs only the `run_capability_tests` call in the existing test
registry. `context` already dispatches through the main CLI, so no new top-level
dispatcher is required. Doctor and the later analyzer can call the feature APIs;
they must report their own local probes and source admission separately.

Before promotion, run the full integrated unit/CLI suites and retain exact
source equivalence. This packet alone neither replaces the installed compiler
nor changes any generated/live MESH artifact.
