# P6: recurring PowerShell startup failure

Continued checkpoint: 2026-10-10 local time. **Pinned host readiness now succeeds
after the user restarted Windows. The historical stall root cause remains
unestablished.** The earlier failed observations below remain historical failures.

The fresh [exact-marker probe](../../build/host-readiness-9062afc2e68b42baa604ad134a65e03b/result.json)
confirmed exit zero and empty stderr. Subsequent actual inert helpers and
[complete UI/frame/destruction execution](P5_TABLET_POST_RESTART_EXECUTION.md)
also completed. Recovery does not identify a security product, driver, or
PowerShell subsystem as the original cause; no operating-system policy was
changed by these tests.

Earlier successful recovery and harness repairs are preserved in
[P6_HOST_RECOVERY_2026_10_10.md](P6_HOST_RECOVERY_2026_10_10.md). They do not establish
the cause of this recurrence. The seven [N1a native service cases](P5_TABLET_NATIVE_SERVICE_EXECUTION.md)
passed before it. The next [UI/destruction candidate](P5_TABLET_UI_NATIVE_CANDIDATE.md)
is source-prepared only.

## Controlled observations

The readiness utility launches an explicit executable and literal arguments,
without a shell, profile, harness script, engine, or Beryl program. Output goes to
owned regular files; stdin is closed. Each attempt has a 15-second main wait and
a separate 5-second cleanup wait.

| Attempt | Receipt | Outcome |
|---|---|---|
| Pinned bundled PowerShell 7 | [88ad20](../../build/host-readiness-88ad20dbd7be45b9a77cbe512833cdc7/result.json) | Timeout; termination requested; direct-child exit unconfirmed |
| Windows PowerShell 5 diagnostic comparison | [533dfc](../../build/host-readiness-533dfc33d3214d6080ef078bc98eafc9/result.json) | Same timeout and unconfirmed exit; not an engine fallback |
| One fresh bundled-host probe after prior processes were no longer observable | [5bec88](../../build/host-readiness-5bec880b23e642548632961e58597033/result.json) | Same timeout and unconfirmed exit |

The command was:

```text
pwsh.exe -NoProfile -NonInteractive -Command "Write-Output 'BERYL_FIXED_HOST_PROBE'"
```

Bundled host identity:
`362a356ce7f0940ec74f73a8fc2c990a2cc24a38a11c90bbd8eca947110ad139`.
Windows PowerShell comparison identity:
`60c9b29843624dd8af6b6a7b26147753be6aeef65098b9a503cc50850afe410f`.

The same pinned bundled host had earlier completed the actual 78-case inert
N1a PowerShell check in about 3.95 seconds. The failure therefore cannot be
explained merely by a permanently unusable executable. The current probes
exclude the Beryl adapter and Enfusion workload from their executed path; they
do not identify an operating-system driver, security product, debugger, or
runtime subsystem responsible for the stall.

Both different host generations failing is useful diagnostic evidence, not a
proof that their shared operating-system dependencies caused the problem.

## Native diagnostics and limitations

Readonly snapshots are retained under build:

- oct11-stalled-host-native-state.json
- oct11-stalled-host-thread-state.json
- oct11-stalled-host-module-state.json
- oct11-late-host-state.json
- oct11-owned-console-cleanup.json

The earlier bounded process/thread snapshot reported one thread in each selected
stalled host, with numeric thread state 5 and wait reason 0. These codes do not
identify a blocking object or responsible driver.

A later [actual asynchronous WCT query](../../build/oct11-owned-host-wct-aa6a547c4f3f45fc963182b24f64b38e/result.json)
validated the exact owned PID, creation time and literal command line first.
It returned callback status zero, one thread node (type 8, status 2), and no cycle.
The fresh native snapshot recorded thread state 5 and wait reason 27; these are
separate observations, not interchangeable with the earlier snapshot. The
query/synchronize process handle was nonsignaled, exit FILETIME was zero, and the
owned WCT session closed successfully.

A single-node WCT result can occur for an unblocked thread or an unsupported
synchronization wait. It cannot identify which applies here or establish that
the host is healthy. No blocking object or stack was obtained. See
[Microsoft's GetThreadWaitChain contract](https://learn.microsoft.com/en-us/windows/win32/api/wct/nf-wct-getthreadwaitchain).
Receipt SHA-256:
`8aca0955013432c99192ef91750750d8bb244f71a8ee537bf23ab54199a7e482`.
No debug privilege was enabled, no other process chain was followed, and no
process was launched or terminated by this diagnostic.

Some early diagnostic waits used a query-only handle. Their WAIT_FAILED result
cannot establish process exit. Debugger/module queries were unavailable and must
not be described as negative findings. Module queries also have a recorded access-
mask limitation. A later command-line query could no longer open three older
owned processes; this supplements their history without rewriting a timeout or
unconfirmed cleanup into a successful run.

The ten inspected CLR startup/profiling environment-variable names were absent
in the diagnostic process. That observation is not a full environment, machine
policy, or runtime audit.

The latest fixed-probe process was still observable by exact literal command line
at the final readonly check. Its cleanup remains unconfirmed. No unrelated
process was selected for termination. Repeated process creation was stopped.

A separate Python 3.13 non-TTY interactive startup produced a console error loop.
Only that exactly identified owned Python process was stopped. The working basic
TTY Python session was used for source-only recovery. This is a diagnostic-tool
failure, not an Enfusion callback result.

Sandboxed command startup also stalled independently; source inspection and
workspace-only writes succeeded through approved cmd/Python execution. That
visibility difference does not identify a particular security mechanism.

## Containment implemented

The UI verifier now runs the existing bounded readiness utility before any
engine job. It pins the utility and executable hashes, requires exact stdout and
empty stderr, records separate execution and cleanup status, and refreshes source
identity after the probe. The final [14-check source audit](../../build/ui-readiness-guard-passive-40ab6288e5b442a185b3bf0e31036c92/result.json)
passes. It does not claim the host currently starts.

No execution policy, Smart App Control, antivirus configuration, user profile,
live MESH project, or installed compiler was changed. No listening bridge or
alternate editor transport was introduced.

## Recovery and next diagnosis

A Windows restart is a reasonable recovery step for the current host state, not
a demonstrated root-cause fix. It was not performed automatically.

After recovery, run one fresh exact-identity probe:

```text
python -X utf8 scripts/verify-host-readiness.py --powershell-host C:/Users/moham/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/powershell/pwsh.exe --expected-host-sha256 362a356ce7f0940ec74f73a8fc2c990a2cc24a38a11c90bbd8eca947110ad139 --probe --timeout 15 --cleanup-timeout 5
```

A successful inventory without --probe is not execution evidence. Require a new
success receipt with exact marker output and confirmed exit. Then run the inert
UI PowerShell checks and resume the engine sequence. If the fixed probe still
fails, capture a native stack or wait chain for the exact owned process using an
available trusted diagnostic capability. Do not blame a subsystem without that
evidence or weaken verification to call the stall success.

## Fresh post-restart evidence

The user's Windows restart was followed by a fresh pinned probe:
[9062af](../../build/host-readiness-9062afc2e68b42baa604ad134a65e03b/result.json).
The exact marker was returned, stderr was empty, exit code was zero, and direct-child exit was confirmed. Runtime was approximately 4.305 seconds. This establishes recovered host availability for that execution; it does not identify the historical blocking subsystem or turn earlier timeouts into successes.

The subsequent actual inert UI helper check passes [97/97](../../build/tablet-ui-native-inert-13f409a4eef746efbe996b8e161da2f0/outer/result.json). Earlier inert failures remain retained: a deliberately resealed prefix fixture had a stale byte count, then its derived packet hash was not passed to the checker. Both harness defects were repaired with distinct source and prepared-input identities and a positive check of the resealed mutation.

The repaired UI candidate then compiled with zero script errors and reached actual UI opening/reopening. Its [runtime attempt](../../build/tablet-ui-native-3kn95p9u/results.json) failed while serializing an adapter receipt exceeding 2 MiB. That is a separate evidence-harness failure, not a recurrence of the literal-output host stall. UI trace, player and release gates remain incomplete pending a fresh bounded receipt.
