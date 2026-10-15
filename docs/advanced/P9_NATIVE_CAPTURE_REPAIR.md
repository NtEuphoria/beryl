# P9 native collector: bounded process capture

Updated 2026-10-08. Status: **capture repair verified on Windows; complete native
performance collection unavailable pending required resource observations.**

## Confirmed defects and repair

The previous `run_binary` read stdout to EOF and then stderr to EOF before
applying its timeout. A silent infinite process never reached the timeout. A
process filling stderr before closing stdout could deadlock. Captures were
unbounded. Paid duration used the wall clock, and backward or short intervals
were replaced with invented positive durations or extended timestamps.

`tools/beryl-bench/run.py` now uses the existing `ProcessJob` implementation and
explicit process arguments. Two reader threads drain stdout and stderr
concurrently. Each retains at most 4 MiB by default; exceeding either bound
rejects the execution. The optional internal bound is 1 through 64 MiB per
stream. Deadlines must be finite, positive and at most 3,600 seconds.

The deadline starts before owned startup, applies throughout execution and
capture, and is checked after startup/attachment. Synchronous OS startup and
job-attachment API calls are not preempted internally; this is not a hard
real-time guarantee on an unresponsive operating system. Stop/reap and reader
cleanup are separately bounded, and the final monotonic deadline is rechecked
after readers join and owned cleanup before a successful result is formed.
Cleanup time is included in paid duration and must fit the admitted deadline
for success. Cleanup acts on the exact owned process tree,
including descendants retaining capture handles; it does not match processes
by name. Cancellation uses an optional event or `KeyboardInterrupt`.

Compile execution, tool-version lookup and evaluator invocation reuse the same
bounded capture path. Workload golden comparison preserves complete output,
normalizes the existing CRLF/LF convention, and rejects nonzero exits.

Terminal cancellation, overflow and read-error flags are checked again after
readers join and owned cleanup. Independent review reproduced a child that
returned zero after writing 2,048 bytes with a 1,024-byte limit: delayed readers
previously published overflow between the main flag checks and completion
branch, so the runner returned success with truncated stdout. The final check
and deterministic scheduling regression prevent that outcome.
The same scheduling technique also exposed completion beyond the deadline;
independent cancellation, overflow and deadline checks now reject all three
terminal cases after capture/cleanup.

Failures carry distinct statuses:

| Status | Meaning |
|---|---|
| `invalid_input` | Invalid deadline, output limit or empty arguments |
| `startup_failure` | Process creation or ownership attachment failed |
| `timeout` | Execution or capture exceeded its deadline |
| `cancelled` | Cancellation was observed |
| `output_limit` | Stdout or stderr exceeded the admitted bound |
| `capture_failure` | Reading an output stream failed |
| `cleanup_failure` | Owned termination, reaping or capture closure failed |
| `program_failure` | Executed program returned nonzero |
| `semantic_mismatch` | Complete output differs from the golden |
| `clock_failure` | Invalid monotonic duration, backward UTC interval or unusable receipt window |
| `unavailable` | Required resource observations are not implemented |

Paid duration uses the monotonic clock and includes process setup, execution,
capture and owned cleanup. UTC start/end timestamps remain the actual observed
values. A positive UTC interval shorter than the monotonic paid duration is
reported as an unavailable receipt window. Evaluator-v1 measurement creation
rejects that window; no timestamp is extended to make evidence acceptable.

## Resource admission correction

The previous collector substituted zero when peak-memory inspection failed,
then raised that number to one byte. It also labeled peak memory as retained
storage, recorded uninstrumented allocation counts as zero, and called complete
binary file size text-section size. Those are different observations.

On Windows, a successful `GetProcessMemoryInfo` query reports only the direct
child's peak working set. Failed queries return `None` with explicit unavailable
capability. The POSIX path does not use cumulative `RUSAGE_CHILDREN` as a
per-process observation; per-process peak memory is currently unavailable there.

Retained storage, allocation counts and text-section size remain unmeasured.
`collect` therefore rejects before builds, timings, directories or complete
performance receipts. The evaluator-v1 format is preserved, and analytical
receipt compatibility remains tested. This correction supplies no new native
performance result, Rust comparison or optimization adoption.

Before collection can reopen, implement and validate the required resource
observations and their scope, or introduce an explicitly approved evidence
profile that can represent unavailable metrics. Do not encode them as numbers.

The dormant compile/reject-check path also needs consistent forwarding of the
selected Clang to Beryl's native compiler and the wrong-candidate build, exact
executable hashes/arguments, and correction of `reject_check`'s implicit default
`clang` lookup. These are explicit blocked obligations, not capabilities
established by this repair. Resource admission prevents those paths running.

## Verification

Command: `python -B tools/beryl-bench/test_run.py`.

Final receipt: `build/bench-harness-check-7ecq_v0y/result.json`.
SHA256: `9151de42cc8b8d4d75d3deb09b680544fdb428952eaa3c95ed2d6a0f25ec1058`.

All 27 tests passed, with zero skips. Executable fixtures cover:

- Exact stdout bytes and independent stderr.
- Two MiB of stderr before two MiB of stdout, exercising the previous deadlock.
- Silent infinite execution and infinite execution after both output pipes close.
- Stdout/stderr limits and an exact boundary-sized successful capture.
- Immediate-exit output overflow and a delayed-reader terminal-overflow race.
- Delayed terminal completion beyond the deadline and terminal cancellation.
- Startup failure, nonzero exit and golden mismatch.
- Cancellation and no launch when already cancelled.
- Owned descendant termination while an unrelated process survives.
- Monotonic payment, backward UTC rejection and unchanged short UTC timestamps.
- Missing resource capability and rejection before any collection build/receipt.
- The same deadline applied to compiler execution.
- Synthetic evaluator-v1 receipt freezing; this fixture is explicitly untimed.

Verified source hashes:

| File | SHA256 |
|---|---|
| `tools/beryl-bench/run.py` | `191f5a77c1569158424a5bc9456772ec02fc24191f6d8f508f911af9720fb59c` |
| `tools/beryl-bench/test_run.py` | `af2adb1695acdca944de0c0de55af79337cda3b2ed96b4db8ff40b15da53c862` |
| Existing `process_job.py` dependency | `7f8ca0d0fe61684ce71df934409ab075d543c1d7e332bc56a77d50e66ea760db` |

The failed first attempt remains at
`build/bench-harness-check-ck8xqwsm/result.json`: four tests rejected ordinary
Windows UTC/monotonic interval differences. The repair records those differences
without changing timestamps and confines evaluator-window admission to receipt
creation. The intermediate 23-test pass at `bench-harness-check-0tkxla8d` predates
the final deadline upper bound and startup argument-error classification.
The 23-test pass at `bench-harness-check-uqx9pt75` predates the terminal flag
repair. Its independently confirmed negative reproduction is preserved at
`build/bench-capture-review-fede1b42574840cbbee569c4ceed4b5f/result.json`.
The 25-test pass at `bench-harness-check-p1u6ie81` predates the terminal
deadline check. Its independent negative deadline result remains at
`build/bench-capture-review-fixed-55d8a3bdf7bd4fb3837c70e89132da6e/deadline-result.json`.

Independent final acceptance reran controlled terminal overflow, cancellation
and actual delayed-reader deadline completion against the final runner hash:
`build/bench-capture-review-final-b49d7c065a98414c9144c8b73c4985f1/` contains
`result.json`, `cancellation-result.json` and `deadline-result.json`. All three
returned the appropriate failure status and retained unchanged source hashes.

Windows fixtures passed. POSIX execution and platform-specific cleanup have not
been executed locally. The inherited `ProcessJob` pre-assignment host-death
window remains documented; this packet does not claim atomic ownership at
process creation. No compiler/runtime source, engine session or installation
was changed by this repair.
