# Source-supported layered world experiment

This package supplies two fixed source templates derived from the installed Bohemia `SCR_WorldFilesHelper.CreateWorld` implementation. It is an experimental authoring fixture. These files were not authored, compiled, imported or loaded by the engine during preparation.

The exact world source is `worlds/BerylCallbackProbe.ent`, 27 UTF-8 bytes:

```text
Layer default {
 Index 0
}
```

The exact default layer is `worlds/BerylCallbackProbe_Layers/default.layer`, 29 UTF-8 bytes:

```text
GenericWorldEntity world {
}
```

Both files use LF line endings and end with one newline. Their exact bytes and hashes are recorded in `source-contracts.json`. LF is an explicit staging choice; the native bytes produced by `FileHandle.WriteLine` were not measured.

The installed helper takes an addon-prefixed directory and a world name, derives the `.ent` and `_Layers/default.layer` paths, writes the layer declaration at lines70–72, and writes the default `GenericWorldEntity world` at lines106–107 when no prefab list is supplied. The full retained source is [SCR_WorldFilesHelper.c](../../../../build/world-authoring-source-research-20261010-b274dc91/selected/SCR_WorldFilesHelper.c), SHA256 `528602403fa19c909d450394bab04ad582b20cd89de0c1962b394249d269071c`. The exact source archive entry, selected decoding receipt, module, primary declaration and line references are pinned in the contract.

The helper's comment says it registers the world, but its actual `CreateWorld` body contains no `RegisterResourceFile` call. A nonempty returned path therefore cannot establish registration. Registration calls elsewhere in this file belong to duplication paths. The installed helper is compiled under `WORKBENCH` in `WorkbenchGame`; calling it from a different script module is unverified and is not part of this package.

An orchestrator may copy the original eight prepared inputs into a new owned workspace, replace only the legacy world source, add this default layer, and retain the existing world metadata and GUID unchanged. The original artifact and earlier rejected templates remain read-only. The separate observer adds the tenth staged input. This package does not accept user-provided script fragments, alter the opener mechanism, widen timeouts, add fallback, or request play/spawn/save.

The next gate must independently verify staged hashes, unchanged metadata, native registration and resource-name/absolute-path roundtrip, and actual WorldEditor readiness. The unchanged `.ent.meta` is an input, not proof that the new source layout is valid. A successful resource lookup or native `Opened:true` is not sufficient world-readiness evidence.

The installed `worlds/Eden/EmptyEden.ent` was inspected as an imported EBIN resource and contains `GenericTerrainEntity`, ocean and time/weather tokens. It is not this small source fixture, and its dependency closure or load cost has not been established. Earlier one-file `GenericWorldEntity` and empty `SubScene` experiments remain historical; this two-file source-backed experiment does not retroactively validate them.

No callback delivery, actual tablet services, engine-authored minimal world, multiplayer behavior or performance claim follows from these templates.
