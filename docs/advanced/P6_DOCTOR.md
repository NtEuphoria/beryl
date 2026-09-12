# P6: bounded local doctor and native readiness probe

Date: 2026-09-07. The C implementation and focused Windows tests are complete.
This packet records source-level delivery; it does not install the compiler,
start an engine, or complete MCP/LSP/analysis-service work.

## Interface

```text
beryl doctor
beryl doctor --format json
beryl doctor --clang <clang-executable> --python <optional-python-executable>
beryl doctor --tool-dir <installed-beryl-tools-directory>
beryl doctor --engine-executable <workbench-executable> --api-root <EnfusionScriptAPI/html>
beryl doctor --probe native --clang <clang-executable> --job-root <owned-job-parent>
beryl doctor --probe native --timeout-ms 30000 --format json
beryl doctor --probe enfusion-compile --format json
```

The default is readable text; JSON is the stable machine interface. `--project`
selects a directory for bounded manifest inspection; no project sources or
scripts are evaluated. Unknown options, repeated options, unsupported probes
and malformed timeout values fail. `--job-root` and `--timeout-ms` require the
explicit native probe. Each process timeout is 1 through 120,000 milliseconds,
defaulting to 30,000. The version, compilation and execution stages each have
their own bounded process outcome.

Native compiler selection follows `--clang`, then `BERYL_CLANG`, then PATH's
`clang`. Optional Python selection follows `--python`, `BERYL_PYTHON`, then
PATH's `python`. Inventory resolves and hashes files; it never runs either tool.
An explicitly configured `BERYL_MOD_TOOL` is reported separately, without
executing it or declaring it equivalent to the installed bundle.

## Inventory contract

Inventory reads and identifies:

- The current compiler and compiled capability metadata.
- Selected native compiler and optional Python files.
- The existing manifest bytes, if present. Full source admission stays unchecked.
- The installed mod loader, active pointer and supported content-addressed bundle.
- Optional exact engine/Math-document matching through the existing binding API.

Inventory success means the inspection completed. It does not mean all optional
capabilities are available. Individual fields retain `unavailable`, `failure`,
`stale_input`, `not_checked`, or `readable` as appropriate. `readable` means a file
was read and hashed; it is not executable-readiness verification. Consumers must
inspect the capability they require rather than treating the top-level inventory
status as a successful build or engine test.

The default creates no directory or file, makes no write-permission probe, and
launches no process. Python remains optional for ordinary C11 compilation.
No editor/game session is started, inspected through NetAPI, stopped or claimed
owned. Native SDK/linker dependencies and Python compatibility remain unchecked.

The optional binding check is deliberately scoped to the selected engine
executable and the registry's Math document. It does not verify all seven API
documents, loaded projects, runtime signatures, effects, retention or authority.
The existing `context binding` API supplies the raw matching record.

## Installed bundle inspection

The reader accepts the existing 4-, 8-, 13-, 16- and 19-file installed profiles.
It reads only bounded ASCII JSON string maps for `active.json` and `bundle.json`;
this is not a general JSON parser. Duplicate keys, malformed hashes, unexpected
filenames and paths outside the fixed profiles are rejected. Unknown future
file-set versions remain unavailable until explicitly supported.

It hashes every selected file and recomputes the canonical content-map identity.
The loader and metadata are rechecked after inspection. `content_match` means
the observed bytes match the declared identity. Loader recognition, link policy,
Python compatibility and actual dispatch remain separately unchecked. This
read-only inspection never replaces the installed loader's execution checks.

Bounds: active pointer 4 KiB; bundle manifest 64 KiB; loader 1 MiB; each selected
bundle file 16 MiB; selected executable hashing 1 GiB. Oversized, empty or
unreadable files cannot receive a successful file identity.

## Explicit native probe

Only `--probe native` creates an exclusive job using the shared filesystem and
process APIs. The fixed probe is C11 code compiled and run solely to test local
toolchain readiness. It is not an authored Beryl program, semantic equivalence
test or performance benchmark.

The sequence is:

1. Resolve and hash the selected compiler. A missing compiler creates no job.
2. Create an exclusive job and write/read back the fixed source.
3. Retain exact version/compile/run argv and per-process timeout in `plan.json`.
4. Execute the selected compiler's `--version` and retain its actual output.
5. Compile the fixed source through explicit arguments, without a shell.
6. Require a fresh nonempty executable in this job, hash it, then execute that path.
7. Require exit zero and the exact `BERYL_DOCTOR_NATIVE_V1` observation, accepting
   the platform's LF or CRLF newline. Unexpected stderr fails the observation.
8. Recheck source/tool/artifact identity and retain the final JSON receipt.

Compilation success with no executable fails before run. No previous executable,
public build output or active installation path is used. Startup failure, timeout,
cancellation, I/O failure, nonzero exit, changed bytes and wrong output remain
distinct. Failure to retain the required receipt cannot emit a success envelope.
Owned artifacts and logs remain for inspection; there is no retry, security
setting adjustment, installation or promotion.

Exit codes are 0 for successful inventory/probe, 1 for argument/manifest or
completed-process/observation failure, 3 for unavailable requested capability,
and 2 for startup/I/O/timeout/cancellation/stale-input outcomes. JSON status is
the more precise discriminator.

`--probe enfusion-compile` currently returns unavailable without creating a job.
Doctor does not provide a second Workbench bridge. Until integrated with the
existing artifact-bound path, use `mod build` followed by `mod verify --stage
compile` with its explicit immutable artifact.

## Verification and source identity

`scripts/verify-doctor.py --beryl <compiler> --clang <clang>` runs eight groups:

- No-write/no-launch default inventory with missing optional dependencies.
- Correct content-map identity and changed/malformed bundle rejection.
- Engine/document mismatch reporting and unavailable Enfusion probing.
- Manifest and argument failures.
- Missing compiler, failed job directory and invalid executable launch.
- Zero-exit missing output, nonzero compiler exit and actual timeout.
- External cancellation of an owned child.
- Actual fresh native compilation/execution in paths containing spaces and
  shell metacharacters, with exact argv/identity receipts.

The initial normal build passed at
`build/doctor & spaces-cyw2nfex/results.json`. After adding explicit required
capability and binding identity fields, the full suite passed against an O2
UBSan build at `build/doctor & spaces-kh06azqw/results.json`.

Both were isolated builds against the preserved delivery baseline with the
owned doctor/context/catalogue files overlaid. They do not include unrelated
in-progress safety or parser changes. The parent integration must rerun the
appropriate suites on the complete immutable candidate.

An additional read-only inventory of the actual installed 19-file bundle found
content identity `6641a45fd8936d7e52185b50e627ddc7b2e07b83ddf3c2d01d863badba9f4f97`.
Its record is `build/doctor-cli-4970f083f7b544229fe12892e6aa3e0e/installed-inventory.json`.
The installed files were neither executed nor changed.

The implementation uses platform-neutral C and the existing Windows/POSIX
process abstraction. Actual execution evidence in this packet is Windows only;
portable code structure does not establish a tested POSIX doctor release.

## Remaining boundaries

Doctor is an inventory and explicit local readiness check. Full source analysis,
unsaved overlays, applicable-evidence resolution, complete toolchain dependency
identity, automatic repair, shared MCP/LSP transports and engine scenario
execution remain separate capabilities. No component or optimization becomes
supported merely because its development machine passes a native probe.
