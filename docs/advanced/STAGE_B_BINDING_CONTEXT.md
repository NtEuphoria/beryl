# Stage B packet: bounded engine declaration context

Status: implementation added for the next checkpoint; complete binding semantics
and M4/Stage B release gates remain open. See the current
[implementation state](../BERYL_ADVANCED_IMPLEMENTATION_STATE.md) for installed
compiler identity and integration results.

## Objective and scope

Give Claude, ChatGPT and human authors exact selected engine declarations through
the same read-only C CLI. Eliminate the previous always-unavailable binding stub
for the admitted selection without presenting extracted text as verified behavior.

The embedded registry contains 35 declarations from seven installed API documents:
Math, array, CanvasWidget, TriMeshDrawCommand, System, WorkspaceWidget and Game.
The snapshot is paired with Workbench 1.8.0.13 executable SHA-256
`7dd36ca1f662b0c13669a4f2f7f10e3c461c2906b021e742272d64b3ab7e9798`.
Each declaration has a document hash, byte range, line, anchor and fragment hash.
Only selected directly declared members are included; no inherited or overloaded
member is silently substituted.

## Interface and consumers

```text
beryl context binding Math.ClampInt
beryl context binding array
beryl context binding CanvasWidget.SetDrawCommands --engine-executable <path> --api-root <EnfusionScriptAPI/html>
```

The existing version-1 context envelope is preserved. Known bindings now return
success with `extracted_declaration.status = snapshot_available`; a class name
lists its selected members. The formerly null binding fingerprint now identifies
this registry for valid binding requests. Other context topics retain their
existing source identities and null binding fingerprint.

`verified_contract` stays unavailable with null effects, retention and authority.
No engine code executes during context lookup. Optional explicit paths check
engine/document bytes. Mismatch produces `stale_input`; missing/unreadable input
produces `unavailable`; both use exit 3. Malformed CLI requests produce the existing
diagnostic envelope and exit 1. No path is executed or passed through a shell.

This is an authoring-context database, not an additional semantic resolver or a
replacement for the existing Workbench transport. Backends still use their current
reviewed intrinsic mappings. The full binding program must later add typed engine
declarations, reviewed semantic contracts, applicability invalidation, inheritance,
units, nullability, retention, authority and scenario-specific test evidence.

## Files and provenance

- `tools/beryl-bindings/generate.py`: bounded offline extraction and deterministic
  C generation from installed documentation.
- `tools/beryl-bindings/snapshot.json`: normalized selected declarations and source
  identities; no engine implementation or complete documentation is copied.
- `src/driver/binding_registry.inc`: generated compiler input.
- `src/driver/binding_context.[ch]`: read-only lookup and streaming hash checks.
- `src/driver/context.c`: CLI integration and capability inventory.
- `scripts/verify-context.py`: existing public-interface regression consumer.
- `scripts/verify-binding-registry.py` and `tools/beryl-bindings/test_generate.py`:
  analytical extraction and exact installed-document validation.

Ordinary compilation and lookup remain C11-only. Python is used only for offline
maintainer extraction and tests. The registry cannot load arbitrary project code
or project-provided runtime JSON. No existing tool bundle format changes here.

## Verification and compatibility

Positive checks cover all selected declarations, exact UTF-8 byte provenance,
template/ref syntax, defaults, class selection, deterministic C generation and
matching installed engine/document identities.

Negative checks cover missing/duplicate/overloaded or inherited substitutions,
unknown Doxygen layouts, malformed UTF-8, oversized files, invalid source spans,
unrecognized schemas, unsafe document paths, duplicate fields, unreadable paths,
changed engine/document bytes and duplicate CLI options. A matching signature does
not turn `verified_contract` into success.

All source-owned changes are compatible with the ordinary compiler and existing
AST lowering. Existing callers that treated every binding query as unavailable
must now inspect `extracted_declaration` separately from `verified_contract`.
Project/symbol context is unaffected apart from reporting the bounded snapshot
capability. No mod script, resource, companion schema or live MESH file is changed.

## Rejection and rollback

An unknown API remains unavailable until explicitly extracted and reviewed. A
changed engine or selected documentation file makes the snapshot inapplicable;
do not silently continue with old signatures. Existing engine fixtures are
historical evidence for their precise bytes and do not automatically validate a
new engine or compiler build.

The generated include and snapshot must pass the consistency checker before
installation. Installation follows the normal immutable compiler checkpoint and
hash-guarded rollback procedure. This packet has no optimization or performance
adoption decision and does not change generated gameplay behavior.
