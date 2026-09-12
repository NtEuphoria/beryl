# Building and verifying Beryl

The compiler is C11 and uses Clang plus the C runtime. The foundation verification
runner additionally requires Python 3, with no third-party Python packages.

## Verified development loop

```text
python scripts/verify-foundation.py --sanitize
```

Use `--clang <absolute-path>` if Clang is not on PATH. The runner:

1. Builds and runs the C unit suite.
2. Builds a compiler from the same source.
3. Checks CLI failures and target-profile enforcement.
4. Emits each end-to-end program twice and compares the generated C.
5. Compiles and runs it at O0 and O2, checking output, exit status and traps.
6. Runs the PID test blocks.
7. Writes commands, outcomes, hashes and toolchain information to `results.json`.

Each invocation writes to a new directory under `build/` and prints its location.
Timeouts, denied launches, compilation failures and sanitizer reports fail the run.
No binary mutation or execution retries are performed. M0 extends that discipline
to ordinary native commands and replaces the old shell retry helper. The
[advanced implementation state](BERYL_ADVANCED_IMPLEMENTATION_STATE.md) records
the current installed compiler, exact validation evidence and rollback artifacts.
Do not infer its identity from the version string alone.

The bounded engine declaration registry is compiled into the C executable.
After changing its snapshot, run `python tools/beryl-bindings/generate.py --check`
and `python scripts/verify-binding-registry.py --beryl <candidate>`. The latter
also accepts `--api-root` and `--engine-executable` to verify exact installed
documentation and executable bytes without starting Workbench. Offline registry
generation uses Python; ordinary compilation and context lookup do not.

## Native driver gates and artifacts

The bounded reference backend is explicitly selected:

```text
beryl test --backend reference examples/pid.be examples/pid_test.be
beryl test --backend differential --clang <clang-executable> examples/pid.be examples/pid_test.be
python scripts/verify-reference.py --beryl <candidate-compiler> --clang <clang-executable>
```

See [M2_IMPLEMENTATION.md](M2_IMPLEMENTATION.md) for admission, budgets, events,
numerical limits and verified evidence. Unsupported declarations fail admission;
an empty selection does not pass. The example above is the small PID example,
not the complete MESH controller port tracked by M3.

```text
python scripts/verify-driver.py --beryl <candidate-compiler> --clang <clang-executable>
beryl check --format json source.be
beryl run --clang <clang-executable> --timeout-ms 120000 source.be
```

`BERYL_CLANG` can also name the native compiler executable. It is one argument,
not a shell command. Paths with spaces and shell metacharacters remain literal.
The driver uses CreateProcessW on Windows and execvp on POSIX. The current Windows
implementation is exercised locally; POSIX execution needs its own platform run.

Every native operation has an isolated `.beryl-cache/job-*` directory containing
generated C/runtime, exact compiler argv, separate compile/run logs, and result.json.
The result contains source and artifact SHA-256 identities and process outcomes.
A check result has no executable or binding fingerprint; those fields are null.
Source identity covers loaded bytes and their paths, including a loaded manifest.
It does not assert that the files remain unchanged after the command completes.

`build` publishes to `-o` or its existing default cache path. `run`/`test` execute
their own isolated artifact; they publish an additional copy only with explicit
`-o`. Publication uses an exclusive `<output>.beryl-lock` directory and atomic
replacement. Missing parents, concurrent publishers, and failed writes fail
explicitly. A crash may leave a lock; inspect ownership and retained artifacts
before removing it. There is no automatic stale-lock deletion.

Startup failure, child exit, timeout, cancellation, and capture I/O failure are
distinct. There are no launch retries or content-changing nonces. Commands have
a default 120-second limit per child process, configurable with `--timeout-ms`.
Captured child stdin is EOF; interactive programs are not supported by this driver.
The file reader currently admits files up to 64 MiB and fails larger reads.
Artifacts/logs are retained for inspection; automatic cache collection is future work.

`test` rejects empty selections. Enfusion `run`/`test` are unavailable through these
commands: emitting script alone cannot count as execution. Use the separate
Workbench proof workflow for compilation evidence.

The supported manifest subset has single-line quoted strings, literal strings,
booleans, and comments outside strings. Only quote and backslash escapes in basic
strings are currently admitted. Unsupported fields, sections, duplicate settings,
malformed values, and unreadable manifests are errors. Explicit CLI values override
manifest defaults.

## Build one release compiler in PowerShell

From the repository root, with Clang on PATH:

Consult the [delivery execution record](BERYL_DELIVERY_STATE.md), the historical
[advanced record](BERYL_ADVANCED_IMPLEMENTATION_STATE.md) and
[SPARKOS record](SPARKOS_IMPLEMENTATION_STATE.md) for the currently installed
compiler's exact hash, validation, and rollback artifact. Historical M0 records
identify historical binaries. The commands below rebuild from source; rerun
verification after making changes.

```powershell
New-Item -ItemType Directory -Force build | Out-Null
$berylCandidate = Join-Path 'build' ('manual-candidate-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $berylCandidate | Out-Null
$berylSources = @(rg --files src -g '*.c' | Sort-Object)
$berylCandidateExe = Join-Path $berylCandidate 'beryl.exe'
clang -std=c11 -Wall -Wextra -Werror -Wno-unused-parameter -O2 -DNDEBUG -Isrc $berylSources -o $berylCandidateExe
if ($LASTEXITCODE -ne 0) { throw 'Beryl compilation failed' }
& $berylCandidateExe version
```

This creates a candidate without replacing the active compiler. The sample's
flags and resulting bytes need their own verification; historical receipts do
not apply merely because compilation succeeded.

### Guarded activation and rollback

`scripts/activate-checkpoint.py` activates a separately verified compiler and
trusted 21-file tool bundle. Its strict manifest names the explicit build and
stage directories, every staged hash, and every expected prior hash or absence.
The allowed mutable destinations are only `beryl.exe`, the two tool loaders,
and `beryl-tools/active.json`. Versioned bundle files are retained.

```text
python scripts/activate-checkpoint.py activate --build-dir <absolute-build> --manifest <reviewed-manifest.json>
python scripts/activate-checkpoint.py rollback --build-dir <absolute-build> --receipt <checkpoint-receipt.json> --expected-current <reviewed-hashes.json>
```

Use a quiescent installation boundary: the helper coordinates its own jobs but
does not lock arbitrary running compilers or editors. Replacements are atomic
individually, not as one multi-file operation. The helper preserves prior bytes,
journals intended writes, and restores only recognized bytes after a failure.
Unknown changes block rollback instead of being overwritten. Keep the receipt
and backups; do not remove or steal a lock left by a force-killed job.

The helper verifies installation identities and file ownership boundaries. It
does not run semantic tests or decide whether a candidate is ready to release.

A changed runtime requires regenerating the embedded header before building:

```text
python scripts/embed_runtime.py
```

The generated header is committed, so a compiler build from unchanged runtime
sources does not require Python.

## Inspect output without invoking the native build driver

The advanced compiler also provides read-only JSON context and optional native
evidence. Interfaces and their admitted limits are in the
[Stage A/B packet](advanced/STAGE_A_B_FOUNDATION.md). No released optimization
family or IR lowering is implied by the presence of their control flags.

```powershell
.\build\beryl.exe check -t enfusion examples/proof.be
.\build\beryl.exe emit-c tests/e2e/foundation_order.be
.\build\beryl.exe emit-c --tests examples/pid.be examples/pid_test.be
```

`emit-c` writes C to stdout and launches no compiler or program. The Python
verification runner captures it as UTF-8, avoiding shell-dependent redirection
encodings.

## Real Workbench compilation

```powershell
.\scripts\reforger-proof.ps1 -Beryl .\build\beryl.exe -Source tests/e2e/foundation_order.be
.\scripts\reforger-proof.ps1 -Beryl .\build\beryl.exe -Source tests/e2e/foundation_names_errors.be
```

The local Workbench helper must be installed. A missing helper is a failed gate.
The proof script creates a unique addon under `build/`, preserves its generated
files and JSON result, and does not delete an existing addon.

Place engine probe scenarios in ordinary functions: Enfusion intentionally omits
native `main` and test blocks. Successful compilation does not establish runtime
parity or gameplay correctness. See the implementation handoff for the exact
scope and evidence of the latest runs.
