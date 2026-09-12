# P5 checkpoint: MCP stdio transport and Windows path identity

Date: 2026-09-07. This packet covers the C process boundary and optional MCP
dispatcher. It does not establish the MCP server's tool semantics, editor
capabilities, deployment permissions or engine runtime correctness.

## Interface and ownership

`ProcessOpts.inherit_stdio = true` passes the original standard input, output and
error streams directly to an owned child. It performs no temporary-file capture,
buffered forwarding, output framing or job-directory creation. `ProcessResult`
still reports startup, exit, timeout, cancellation and I/O outcomes; its capture
paths and captured byte strings remain empty in this mode.

The default false value preserves the existing separate stdout/stderr capture
files and bounded process lifecycle. Existing callers need no behavior change.
Capture-mode `log_dir` and `log_name` remain required. Inherited mode requires
valid input, output and error handles; it does not quietly substitute a null
device for a missing stream.

On Windows, the implementation duplicates exactly those three handles, marks
the duplicates inheritable and restricts inheritance through the existing
`STARTUPINFOEX` handle list. It creates the child suspended, assigns it to an
operation-owned Job Object configured to kill remaining children on close, then
resumes the child. The existing wait loop distinguishes cancellation and timeout.
Cleanup terminates remaining owned descendants even after a normal direct-child
exit. Original parent handles are not closed by dispatch.

On POSIX, inherited mode first validates all three original descriptors, then
duplicates them above descriptor 2 with close-on-exec. The existing child process
group, dup2, exec and cleanup behavior remains. POSIX execution was not available
for this checkpoint's Windows test run; source review is not runtime evidence.

The C API is:

```c
bool process_utf8_arguments(Arena *, int *argc, char ***argv);
bool process_environment(Arena *, const char *name, const char **value);
int driver_mcp(int argc, char **argv);
```

The Windows CLI must call `process_utf8_arguments` before using narrow
`main(char **)` arguments. It loads shell32 from System32 only, retrieves
`CommandLineToArgvW`, parses `GetCommandLineW`, converts each argument with strict
UTF-16-to-UTF-8 checking and releases the Windows/DLL allocations. UTF-8 strings
live in the supplied arena. Failed conversion does not publish partial arguments.
POSIX argument pointers remain unchanged.

This fixes a demonstrated loss before dispatch: the old narrow Windows main
changed `雪` into `?`. A later CreateProcessW call cannot recover characters
already lost at the CLI entry point. Source paths and identities therefore need
the startup hook, independently of MCP.

`process_environment` returns true plus NULL for an absent variable, true plus
an empty string for a present empty value, and false for conversion, bounds or
read failure. Callers must report false rather than silently choose a default
tool. Windows uses checked GetEnvironmentVariableW reads and strict UTF-8
conversion. The limits are fewer than 256 UTF-8 bytes for the name, at most
32,768 UTF-16 buffer units on Windows, and fewer than 131,072 UTF-8 value bytes.
POSIX reads are bounded and validated with the existing common `json_utf8`
validator. Result strings belong to the caller's arena.

## Dispatcher behavior

`driver_mcp` selects the trusted installed launcher next to the running compiler:
`beryl-tools/mcp.py`. A user-configured `BERYL_MCP_TOOL` is an explicit trusted
override. `BERYL_PYTHON` selects Python; otherwise Python is resolved through the
current process PATH. Both environment reads preserve Unicode and distinguish
invalid values from absence.

The exact child argument structure is:

```text
absolute-python -I absolute-launcher --beryl absolute-compiler <user arguments>
```

There is no command interpreter, project-provided script discovery, shell
interpolation or model API dependency. The `-I` switch isolates Python from
project/PYTHONPATH startup imports. This is not a Python sandbox: the installed
launcher and explicit override are trusted local programs.

The dispatcher inherits stdio with no default timeout because an MCP session can
remain open. Cancellation still reaches the owned-process cleanup path. Setup
and launch diagnostics go only to stderr. Ordinary child exits 0–255 pass through;
larger exit values normalize to 1, and dispatcher failures return 2. No protocol
text is appended to stdout by the C dispatcher.

Root integration owns the `beryl mcp` main branch, startup argument hook, other
driver environment callers and the installed Python loader. These are separate
from this packet's tested harness. The full compiler must run the optional
`--beryl` verification below after those consumers are wired.

## Reproducible verification

Run the portable verifier with explicit tool and source paths:

```text
python scripts/verify-mcp-dispatch.py --source-root <source-tree> --clang <clang> --python <python> --output-root <artifacts> [--beryl <full-compiler>]
```

It captures source hashes, builds an isolated harness, records tool identities,
exact child arguments, raw protocol exchanges and lifecycle outputs, and does
not install the compiler. It also runs the existing capture/process/manifest
unit suite through its original child behavior.

Final focused evidence is
`build/mcp-process-nchaqq9l/mcp-dispatch-yqzkff1i/results.json`:

- 67 transport/environment/lifecycle checks passed.
- Existing captured-process suite passed 11 cases and 54 checks.
- Four genuine inherited-pipe sessions each exchanged three requests before
  EOF. Binary NUL/CRLF and UTF-8 payload bytes were retained exactly.
- Empty arguments, spaces, quotes, trailing backslashes, shell metacharacters,
  Unicode arguments, Unicode project/executable paths and a Unicode trusted
  environment override reached the selected child accurately.
- Missing stdin, stdout, stderr and executable cases failed distinctly without
  executing the protocol fixture.
- EOF and child exit status were preserved. Timeout, cancellation and normal
  direct-child exit each left the tested owned descendant stopped.
- Missing, empty, Unicode, invalid UTF-16 and invalid/over-limit environment-name
  cases were distinguished without a fallback on conversion failure.

The harness SHA-256 is
`adddf9cc7a6f15e3abf2a09622d2d96ecb00a58589687cdaad33420608786155`.
Its parent capture record is `build/mcp-process-nchaqq9l/results.json`.
The capture explicitly overlays the current common JSON UTF-8 validator files
because the earlier R0 baseline predates them.

Independent read-only review found no additional material issue in the Windows
handle lifecycle, dispatcher, argv conversion or environment getter. This is a
bounded review and regression result, not a general process-isolation proof.
Python-side ProcessJob ownership and server protocol admission have separate
implementations and separate acceptance evidence.

The source-only integration identity is recorded in
`build/mcp-process-freeze.json`. No active compiler installation is performed by
this checkpoint. Final release evidence must include the actual main/loader
integration and full-compiler pipe run, not just the isolated harness.
