# M0 implementation packet

Date: 2026-09-06. Governing plan: [SPARKOS_IMPLEMENTATION_PLAN.md](SPARKOS_IMPLEMENTATION_PLAN.md).
Live progress: [SPARKOS_IMPLEMENTATION_STATE.md](SPARKOS_IMPLEMENTATION_STATE.md).

## Objective and dependencies

Make ordinary native commands and their evidence dependable before module and
PID work. Starts from the previously verified foundation compiler and preserves
preexisting working-tree changes. Scope is the compiler/driver, local scripts,
regressions, and documentation; no live MESH production scripts change in M0.

## Source evidence and changed responsibilities

Before M0, build.c constructed shell commands, shared `.beryl-cache/out.c` across
jobs, and retried blocked executables with changed binary content. The manifest
parser ignored unknown fields and treated malformed booleans as false. Enfusion
run/test could report generation as successful execution. Native tests accepted
an empty selected test set. Captured output did not distinguish child channels.

The driver now uses:

- `src/common/fs.*`: checked UTF-8-path I/O, isolated job directories, atomic rename.
- `src/driver/process.*`: CreateProcessW on Windows, fork/execvp on POSIX, explicit
  arguments, owned child groups/jobs, separate log files, timeout/cancellation.
- `src/driver/build.*`: exact candidate compilation, retained logs/argv, artifact
  hashes, output locking and checked publication, execution of the isolated file.
- `src/common/hash.*` and `src/driver/identity.*`: SHA-256 loaded-source/compiler/
  artifact identities. Hash implementation has independent standard known-answer tests.
- `src/common/json.*` and diagnostic rendering: valid JSON even for malformed
  diagnostic bytes; source spans, related locations, notes/help.
- `src/driver/manifest.*`: explicit supported grammar, comment-aware strings,
  strict booleans, unknown/duplicate/malformed setting errors.
- `scripts/compile-once.sh`: single candidate build/probe/publication, replacing
  the removed content-changing retry helper.
- `scripts/verify-driver.py`: real CLI behavior, concurrency, cancellation, failure
  and publication checks; all fixtures and raw results retained.

## Public behavior and compatibility

Existing successful check/build/run/test workflows remain. Human diagnostics are
default. `check --format json` adds schema version 1 without mixing human text
into stdout. `--clang <path>` or BERYL_CLANG selects one executable. `--timeout-ms`
sets a positive per-child limit; default 120 seconds. PATH lookup on Windows does
not implicitly prefer a project-local compiler executable.

`build` preserves its default published output; `run`/`test` use isolated executables
and publish a copy only when `-o` is explicit. Failed compilation cannot execute
an older output. New package creation refuses existing directories and validates
package names as data. Unknown settings that were silently ignored now fail;
explicit CLI configuration takes precedence over manifest defaults.

Empty test selections fail. Enfusion run/test are explicitly unavailable through
the ordinary native commands. Use build plus an engine validation job; generation
does not prove execution. No new interpreter backend is claimed by this packet.

## Evidence contract

Each job retains out.c, embedded runtime sources, compile.argv.json, separate
stdout/stderr logs per executed stage, program.exe on successful compilation, and
result.json. Status distinguishes process exit from startup failure, timeout,
cancellation, and capture I/O failure. A child exit 127 is an ordinary child failure,
not inferred missing-tool status. A compiler returning zero without output fails.

Source SHA-256 covers bytes actually loaded, including manifest bytes when present.
Compiler and executable hashes identify tested artifacts. Check has no binding or
executable artifact, so those fields are null. JSON byte offsets are zero-based;
line/byte-column values are one-based. Null primary locations represent failures
without a loaded source span. SHA-256 identity is not a semantic-correctness proof.

Verifiers capture hashes before running and reject source changes during the run.
No measurement is inferred for work that did not execute.

## Positive and negative validation

- Foundation unit tests and all existing O0/O2 e2e programs/PID example tests.
- OS-delivered argument equality: empty strings, embedded quotes, trailing
  backslashes, spaces, UNC-like strings, and shell metacharacters.
- Distinct child stdout/stderr, exit 127, missing tool, capture write failure.
- CLI JSON success/error parsing, malformed UTF-8, spans, exact source/compiler hash.
- Security boolean with trailing comment remains true; malformed values fail.
- Successful run/test actually execute; no tests and unsupported engine execution fail.
- Failed/missing/lying compiler cannot overwrite or execute prior output.
- Missing output directory and contended publication lock fail without replacement.
- Six simultaneous jobs have independent source and executable outputs.
- Runtime timeout and external cancellation are separate retained outcomes.
- Package creation preserves existing source; metacharacter package names fail.

Exact run directories and counts live in the state record. Failed early regression
runs remain in build/: one exposed Windows CRCRLF forwarding, which was repaired;
another exposed a singular/plural expectation error in the new test, corrected
after inspecting the actual successful child output.

## Remaining limitations and gates

- Windows is the locally tested process platform. POSIX implementation exists but
  has not been executed on a POSIX host in this task; do not claim its gate passed.
- Only the admitted manifest subset is supported, not complete TOML.
- Source identity records loaded input; validation/promotion compare-and-swap and
  stale engine completion handling remain M4/M7 responsibilities.
- The driver reads at most 64 MiB per file and retains artifacts/logs. Parser/arena
  resource hardening and bounded malformed-input testing remain open; this is
  not an exhaustive security audit.
- Publication locks are fail-closed. A crashed process may leave a lock requiring
  deliberate inspection; automatic stale-lock deletion is not implemented.
- Captured subprocess stdin is EOF; interactive native input is not supported.
- Generated-C determinism is checked. Reproducible native binary bytes are not
  yet a guarantee; job paths/toolchain metadata can affect them.
- No verified bindings, full PID port, AST interpreter, structured IR, whole-mod
  schema, or Rust performance advantage is implied by M0 completion on Windows.

## Rollback and next packet

Retain previous default compiler and result/source hashes with the verified
candidate. Rollback restores that exact prior binary without deleting the new
diagnostic evidence. Next: M1 qualified declaration identity, explicit imports,
visibility, method receiver identity, and generated-name collisions, followed by
the independent semantic reference and full current PID.
