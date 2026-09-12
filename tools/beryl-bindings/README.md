# Bounded engine declaration registry

The compiler embeds 35 selected declarations from the installed EnfusionScriptAPI
Doxygen 1.16.1 documentation paired with Workbench 1.8.0.13. The snapshot covers
numeric helpers, arrays, Canvas command fields/publication, workspace access and
measurement counters. This is a read-only authoring aid. It is not a new compiler
binding mechanism, full engine API database, or optimization legality contract.

```text
beryl context binding Math.ClampInt
beryl context binding array.Copy
beryl context binding CanvasWidget.SetDrawCommands
beryl context binding System.GetTickCount
beryl context binding Math --engine-executable <Workbench-exe> --api-root <EnfusionScriptAPI/html>
```

A class query lists only the selected members. Missing members return unavailable;
absence from this bounded registry does not establish absence from the engine.
Signatures retain documented access modifiers, parameter direction, generic types,
defaults and field initializers. They are extracted text, not a complete parsed
engine type system. No overload or inherited-member substitution is inferred.

`extracted_declaration` supplies normalized signature text and exact HTML document,
fragment hashes, byte ranges, line and anchor. `binding_fingerprint` identifies the
complete registry snapshot. An optional engine or document path is read and hashed,
never executed. A different hash returns `stale_input` and exit 3; an unreadable
file or unknown selection returns `unavailable` and exit 3. Invalid syntax exits 1.

Without these paths, applicability is explicitly `not_checked`. A successful lookup
means the snapshot was found, not that this machine currently has that engine or
that a loaded session uses it. Engine dependencies and loaded-session identity
remain the existing Workbench bridge's responsibility.

`verified_contract` is deliberately separate and currently unavailable. Historical
integer/PID comparisons and new storage probes live in their immutable experiment
receipts. Their bounded results must be reviewed before adding semantic annotations
to a future contract registry. A method's name or return type cannot establish
allocation behavior, purity, aliasing, retention, authority or ordering. In particular,
`array.Copy` must not be treated as recursive value copying and Canvas publication
must not be treated as permission to overwrite its command storage.

## Maintainer capture and verification

```text
python tools/beryl-bindings/generate.py --api-root <EnfusionScriptAPI/html> --engine-executable <Workbench-exe> --engine-version <verified-version>
python tools/beryl-bindings/generate.py --check
python tools/beryl-bindings/test_generate.py
python scripts/verify-binding-registry.py --beryl <candidate-compiler> --api-root <EnfusionScriptAPI/html> --engine-executable <Workbench-exe>
```

The version label is an explicit maintainer input and must agree with independently
read executable metadata. The executable hash is captured from actual bytes and is
the applicability test; a caller-supplied label alone never establishes identity.

Capture reads seven explicitly selected documents, validates all selections, and
writes the repository-owned snapshot and C include. It rejects missing or duplicated
members, unsupported generator layouts, malformed UTF-8 and oversized documents.
Regeneration does not carry forward semantic annotations. Review changed signatures
and rerun affected engine fixtures after an update.

The generated include is a compiler build input. Runtime lookup does not parse
project-provided registries or execute scripts. Normal C11 compilation has no
Python dependency; only offline capture/check tooling uses the standard library.

`--check` validates snapshot/include consistency and extractor identity. The context
regressions cover unknown declarations, engine/document mismatch, unreadable paths,
malformed options, and separation of extracted information from verified contracts.
The installed-document verification additionally checks every recorded byte span.
