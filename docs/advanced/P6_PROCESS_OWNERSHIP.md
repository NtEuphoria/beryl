# P6 — Python process ownership boundary

The shared `tools/beryl-mod/process_job.py` now starts Windows children suspended,
assigns them to its own Job Object, and resumes the verified primary thread only
after assignment. Both existing callers retain their `owner.flags` /
`owner.attach(process)` interface: `mod.Job.run` and the local MCP worker.

The Job Object receives `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` before child creation.
Abrupt loss of the Python host therefore terminates a successfully attached
process tree, including descendants that outlive the direct child.

## Launch and teardown contract

1. Create a private, non-inheritable Job Object and set kill-on-close.
2. Call `Popen` with `CREATE_SUSPENDED`, `CREATE_NEW_PROCESS_GROUP` and
   `CREATE_NO_WINDOW` through the shared `flags` value.
3. Assign the exact `Popen` process handle to the job.
4. Enumerate threads with the documented Toolhelp API. Require exactly one
   thread belonging to that still-suspended PID; ambiguous results fail closed.
5. Open the identified thread for resume and limited query, then recheck its
   owning process ID to detect reuse between enumeration and handle acquisition.
6. Call `ResumeThread` once. Its previous suspend count must be exactly one.
   No further resume calls attempt to override an external suspension.
7. On attach failure, kill and wait for the exact direct child. On normal stop
   or context exit, terminate the owned job. Closing its configured handle also
   covers abrupt host death after assignment.

No undocumented `NtResumeProcess`, shell command, global process-name match or
unrelated session shutdown is used. The system-wide thread enumeration only
selects entries belonging to the exact created PID. It has a 262,144-entry bound.

This is not atomic job assignment at process creation. If the host is forcibly
killed between `CreateProcess` and `AssignProcessToJobObject`, an unassigned
**suspended** process can remain. Its user code has not been resumed. The existing
C layer also uses a two-step suspended-create/assign/resume sequence. Eliminating
that final startup interval would require separately verified job-at-creation
support; this packet does not claim that capability.

POSIX behavior is unchanged. This Windows fix does not claim parent-death
containment for POSIX process groups.

## Verification

```text
python -I -B scripts/verify-process-job.py --clang <verified-clang-path>
```

The script creates isolated fixtures under `build/`, keeps raw evidence and never
starts an engine or installs a compiler. It verifies:

- No marker/user code executes before `attach`; execution starts after resume.
- A child that immediately spawns a descendant has both processes stopped by
  the owning job.
- Hard-killing an attached Python host stops the direct child and descendant.
- The same hard-death result holds through the actual MCP server worker.
- The existing `mod.Job.run` interface preserves stdout and exit/log behavior.
- A private copied mutant removing suspended creation fails the pre-attach gate.
- A private copied mutant removing kill-on-close fails the host-death gate.

The mutant survivors are cleaned up through exact retained process handles after
their executable paths have been checked against the owned fixture. No global
process enumeration or name-based cleanup is used.

Final Windows evidence:
`build/process-job & spaces-4kbwppr2/results.json` — seven checks passed, including
the two expected mutant detections. The receipt hashes the exact helper, fixture
executable and MCP server bytes involved in those checks. Independent review
found no material Win64 structure-layout, exact-thread-selection, assignment,
resume or ordinary cleanup defect in this implementation.

Broader combined mod/MCP suites and the final installed tool-bundle fingerprint
remain integration checks. The helper's source change invalidates earlier
bundle-specific evidence until the corresponding checks run again.
