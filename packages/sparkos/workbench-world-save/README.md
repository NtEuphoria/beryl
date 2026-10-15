# Read-only world-save eligibility fixture

This experimental package contains only the trusted
`BerylWorldSaveEligibility` NetAPI handler template. The installed request
action is `observe`. It performs no save, resource opening, module opening,
world creation, play transition, entity operation, callback, or deferred work.
There is no save endpoint or automatic follow-up operation.

The request has exactly two strings: `token` and `action`. The integration owner
renders `@TOKEN@` from exact inputs and `@OUTPUT_ABSOLUTE@` as one fixed new
isolated output path. The request cannot select a different destination.
`output_path` is a declared future destination, not proof that a file was
created or that the engine can save there.

The response registers exactly seven string fields:

```text
token action status failure output_path wb_world_path game_world_path
```

And exactly twelve Boolean fields:

```text
game_present in_play_mode module_present
wb_api_present wb_world_present wb_edit_mode wb_game_mode
game_editor_present game_api_present game_world_present api_same world_same
```

The wire transport must retain the raw response and separately normalize only
actual JSON Boolean or exact integer 0/1 values. Strings, floating-point numbers,
other integers, unknown fields, missing fields, stale token/output identity, and
malformed results fail admission. This source does not implement the transport,
its codec, or its ownership harness; the parent integration owner does.

`eligible` requires the actual synchronous observation to contain all required
nonnull handles/APIs/worlds, Workbench edit mode, no Workbench game mode or
gameplay, equality of both editor API references and both world references,
and empty world paths from both APIs. The handler obtains
`Game.GetWorldEditor()` only when a game context exists and `InPlayMode` is
false. Both paths use the declared `WorldEditorAPI.GetWorldPath(out string)`
operation. `Game.GetWorldFile()` is not substituted.

Missing handles, a mismatched identity, a named world, or incompatible modes
produce `unavailable` with a reason. Wrong token or an unsupported action
produces `failure`. There is no synthetic eligibility result or fallback.
These native equality expressions are proposed target expressions until the
parent's identified compiler and actual engine compile/run establish their
applicability. A rejected equality operation is unavailable; it must not be
replaced by matching path strings or handle-presence assumptions.

The existing original eight captured addon inputs remain immutable. This
handler can be staged as the distinct ninth file in a new owned candidate;
old handlers are inactive and are not called. No captured or live world is
overwritten. Any previously retained artifact or runtime receipt still applies
only to its own bytes and coverage.

## Primary contracts and phase-two boundaries

The exact installed primary document directory is:

`C:/Program Files (x86)/Steam/steamapps/common/Arma Reforger Tools/Workbench/docs/EnfusionScriptAPI/html/`

| Exact file | SHA-256 | Relevant declaration |
|---|---|---|
| `interfaceGame.html` | `dfcab6b926646b8b56cdcbf38bb3e5f9809e96c9e3efaabc11cf806d6ec4b22e` | `GetWorldEditor() -> GameWorldEditor`, line 126; line 664 permits it only outside play |
| `interfaceGameWorldEditor.html` | `7cc3930f097af572521b6d4caddaeb38faf963294bbd5f0a763c49291728abe6` | `GetEditorAPI() -> WorldEditorAPI`, line 123; `SaveWorldAs(string savePath, bool overridePath=false) -> bool`, line 125 |
| `interfaceWorldEditorAPI.html` | `202fbc3822d1c8d9cd465ad4968a9541e90353b51cf4329046187ef8cba1d7b2` | `GetWorld() -> BaseWorld`, line 210; `GetWorldPath(out string path) -> void`, line 225 |
| `interfaceWorldEditor.html` | `51af7415047780b9efa7302dfa3b4573dd89d78c4d90b46968273f010f16f275` | `GetApi() -> WorldEditorAPI`, line 122 |
| `interfaceFileIO.html` | `8be2320b5236b9e2ec5a65fe4d8c82549d8f139daa2149277c5a35fcafb177fb` | `static proto bool FileExists(string name)`, line 116 |

`FileIO.FileExists` is documented at lines 239 onward. Its signature is a
possible additional future-phase check, not a file operation executed by this
handler. The phase-two existence check must be paired with host-side ownership,
ancestor/link checks, exact absent destination, and frozen input guards. A false
existence result alone does not establish an allowed write location.

The installed `SaveWorldAs` documentation at line 208 caps its path at 256
characters and mentions overwriting when `overrideWorld` is true, while the
actual parameter is named `overridePath`. Keep that discrepancy visible. An
eventual distinct phase may propose one new absent short ASCII output and
explicit false; current eligibility does not establish save semantics, absolute
path acceptance, output sidecars/dependencies, resource registration, active-path
changes, completion, or reloadability. This package calls neither
`SaveWorldAs`, parameterless `SaveWorld`, nor generic module `Save`.

The only completion claim this package can support after actual execution is a
bounded identity/mode/path eligibility observation. A future save is a separate
capability gate; a saved file is a separate fixture; reload and real component
callbacks are further gates. Tablet services, multiplayer, visuals, deployment,
and performance remain outside this fixture.
