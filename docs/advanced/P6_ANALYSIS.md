# P6 — Exact source snapshot analysis

This packet implements the bounded C input and analysis foundation from
`docs/BERYL_DELIVERY_PLAN.md`. It is a one-shot analyzer. It does not complete the
MCP adapter, editor protocol, whole-mod authoring workflow or P6 release gate.

## Purpose and current scope

An assistant or editor needs diagnostics for the bytes it actually supplied,
including unsaved source. Reading an existing disk file in place of an absent
overlay would analyze a different program while appearing successful. This API
requires every source's exact content and binds its answer to that content.

The compiler remains C11. Normal analysis does not require Python, Clang, an
editor, a model API or a game process. The optional Python verification script is
a development test harness only.

New interfaces:

```text
beryl analyze --request <request-directory/request.json>

analyze_snapshot(arena, snapshot, compiler_version)
analyze_request(arena, request_bytes, content_reader, user, compiler_version)
analyze_command(argc, argv, compiler_version)
```

The command emits exactly one JSON response to stdout. It does not create build
directories, write source, discover project files, read a manifest, generate code,
load arbitrary scripts, launch tools, execute tests or contact the engine.

This first interface returns diagnostics and target admission. Existing context
commands remain the symbol/binding catalogue interface. The new analyzer does not
claim completion, hover, rename, reference search, incremental updates or LSP.

## Input contract

The published request schema is `schemas/beryl.analysis.v1.schema.json`.

```json
{
  "schema_version": 1,
  "request_id": "edit.42",
  "snapshot_version": 42,
  "target": "native",
  "forbid_unsafe": true,
  "expected_compiler_sha256": "<64 lowercase hexadecimal characters>",
  "sources": [
    {
      "path": "src/controller.be",
      "sha256": "<SHA-256 of the exact content file bytes>",
      "document_version": 8,
      "content_file": "0001.be"
    }
  ]
}
```

The illustrative angle-bracket hashes above must be replaced; they are not valid
hashes. `expected_compiler_sha256` is optional. Every other displayed root member
is required. Each source has exactly the four displayed members. Unknown members
and duplicate decoded keys fail before a content-reader callback is invoked.

The source list is the complete compilation unit, in compilation order. Imports
resolve only against these supplied sources and the compiler's built-ins. An
absent module is a normal resolution failure, not permission to search disk.

`path` is a logical identity used by SourceMap and diagnostics. It is never
opened. Paths must be relative, forward-slash, valid UTF-8 `.be` names. Empty,
`.` and `..` segments, backslashes, colons, control bytes, reserved punctuation
and trailing spaces/dots in segments are rejected. Rejection is explicit;
the analyzer does not silently normalize different requests into one identity.
Paths are unique after ASCII case folding. Unicode normalization and Unicode
case folding are not performed. Clients must retain their own URI-to-logical-path
mapping rather than assuming this is an operating-system pathname canonicalizer.

`content_file` is an ASCII basename in the request directory. No subdirectories,
absolute paths, UNC paths, streams, traversal, trailing dots or Windows device
names are admitted. Names are unique after ASCII case folding. Content basenames
and logical source paths are separate namespaces.

Versions range from zero through 9,007,199,254,740,991 inclusive. Their JSON token
must contain unsigned decimal digits: `1.0`, `1e0` and `-0` are rejected even
though a generic JSON Schema implementation may treat some as integer values.
The C validator enforces these lexical, byte-length and path restrictions in
addition to the machine-readable schema's structural constraints.

## Ownership and immutable inputs

The future adapter owns a fresh request directory, writes all content files and
the manifest, closes its writers, and invokes the analyzer. It retains the
directory until the response is consumed, then manages cleanup itself. The C
analyzer never creates, deletes or takes ownership of that directory.

The CLI retains open handles to the manifest and every admitted content file
until analysis finishes. It admits regular, single-link files only.

- Windows opens the request directory without delete sharing, rejects a reparse
  point at that directory, and opens files with reparse inspection and read-only
  sharing. Ordinary concurrent writers and deletion/replacement are denied while
  those handles remain held.
- POSIX uses a directory descriptor, `openat`, `O_NOFOLLOW`, regular-file checks
  and one-link checks. It rechecks directory-entry device/inode identity and the
  held bytes after analysis.
- Both implementations re-read held bytes before publication. Detected changes
  produce `stale_input`; the earlier result is nested under `rejected_analysis`
  and is not a publishable admission result.

This is **not** an ACL or directory-ownership verifier. Ancestor reparse points,
ancestor permissions and ownership of the caller's directory are not established
by this interface. Windows directory-relative opens are constructed from the
retained directory's path; the implementation does not claim the stronger
security properties of a complete handle-relative namespace.

The bytes copied into the arena and verified against the supplied hashes define
the analyzed snapshot. Concurrent filesystem writes through pre-existing memory
mappings, write-and-restore histories and external unsaved-buffer changes are not
made impossible by this design. A client must compare request ID, every document
version/hash, snapshot identity and compiler identity before publishing results.
An old result never becomes current merely because the compiler returned success.

The direct C snapshot API receives immutable slices for the duration of the call.
Its caller owns the arena lifetime and synchronization. The reader callback API
is for trusted adapters; its callback must return exact immutable adjacent bytes.
The CLI provides the bounded filesystem reader. Neither API is a script hook.

## Strict bounded JSON reader

`src/common/json_read.[ch]` is independent of compiler semantics. It provides an
arena-backed tree, exact number tokens, decoded strings, source offsets, object
lookup and checked unsigned-integer extraction.

The reader accepts the JSON value grammar and valid UTF-8 scalar values. It
rejects malformed numbers, raw control characters in strings, trailing input,
BOMs, overlong UTF-8, surrogate code points encoded as UTF-8, values above
U+10FFFF, malformed escapes and unpaired UTF-16 surrogate escapes. Valid surrogate
pairs are decoded to UTF-8. Escaped NUL is legal JSON; individual request fields
and Beryl source encoding subsequently reject it where their contract forbids it.

Duplicate object keys are compared after escape decoding. For example, `target`
and `\u0074arget` cannot coexist. The work budget also charges duplicate-key
comparisons, so long common names cannot bypass the scanning budget.

| Input/resource | Bound |
|---|---:|
| JSON request bytes | 1 MiB |
| JSON nodes | 16,384 |
| JSON nesting depth, root counted as one | 48 |
| Total decoded JSON string bytes, names included | 1 MiB |
| JSON scanner/parser/comparison work | 8,388,608 units |
| Source files | 64 |
| Source bytes per file | 1 MiB |
| Total source bytes | 8 MiB |
| Aggregate source tokens, EOF included | 262,144 |
| Logical path | 1,024 UTF-8 bytes |
| Request ID and content basename | 128 ASCII bytes |

Source token totals are checked **after lexing each file**. This is not a lexer
allocation budget. Existing parser and security-analysis bounds still apply and
can reject a request below these wrapper limits. These limits do not constitute
a complete peak-memory, CPU-time, default-expansion or whole-compiler resource
proof. Arena allocation failure follows the compiler's existing abort policy.

## Reused semantic pipeline

All source bytes are hashed and checked for valid UTF-8 without NUL before
semantic processing. The analyzer then runs the existing compiler passes:

1. SourceMap registration, lexing and parsing.
2. Declaration and module resolution.
3. Type and expression checking.
4. Ownership checking.
5. The existing bounded taint/security analysis, with explicit `forbid_unsafe`.
6. Exactly one requested target's admission pass.

Native and Enfusion admission call their existing lints, including the newly
integrated bounded storage admission. Reference admission calls the existing
reference subset checker. No alternative type system, taint rules, ownership
model or target lowering is implemented in this module.

Enfusion admission uses the fixed `BE` generated-name prefix in this version.
It does not validate a companion export description or a project's custom
prefix. It does not establish engine binding identity, compile in Workbench,
execute scripts, verify authority or prove multiplayer behavior.

There is no public IR selection or released optimization involved. Existing
bounded/partial ownership, reference and taint capabilities remain bounded and
partial; an analyzer success does not upgrade those capabilities.

## Response and failure interpretation

Every response names its operation, stage and status, with structured diagnostics
and repair guidance. Valid request metadata is retained on semantic failures.

| Exit | Status | Meaning |
|---:|---|---|
| 0 | `success` | Exact supplied source set passed semantic and target admission |
| 1 | `failure` | Arguments, request, input, encoding, limits or semantic check failed |
| 2 | `stale_input` / `cancelled` | Result must be discarded |
| 3 | `unavailable` | Semantics passed, selected target cannot admit this source set |

An output-write failure also exits 2; partial stdout is not a valid response.
There is no timeout option inside this synchronous API. An external harness
timeout must remain a timeout, not a semantic failure, source trap or success.

`request_fingerprint` hashes the raw request JSON bytes. Insignificant JSON
formatting therefore changes that correlation identity.

`source_fingerprint` hashes `identity_sources`' deterministic ordered JSON array
of logical paths and actual source hashes. The source set's original byte order
and line endings are retained.

`snapshot_fingerprint` hashes compact UTF-8 JSON with these members in order:
`identity_schema` (`beryl.analysis.snapshot.v1`), `request_id`, `snapshot_version`,
`target`, `forbid_unsafe`, and `sources`. Each source descriptor contains `path`,
`sha256`, `document_version`, and zero-based `file_id`, in that order. The compiler
fingerprint is reported separately rather than silently included in this hash.

Source and snapshot fingerprints remain null if all source bytes have not been
verified. The compiler fingerprint is the current executable's actual hash when
readable. Requested compiler mismatch fails before content callbacks run.
Binding and artifact fingerprints remain null because those operations did not
execute. `execution` and `engine_verification` explicitly remain `not_run`.

Diagnostic spans use existing `diag_render_json` fields: logical file, zero-based
byte offset, byte length, and one-based line/byte column. The additive
`location_encoding` object makes the byte convention explicit. No UTF-16 editor
column is guessed. Future LSP transport must convert using the exact source bytes.
Malformed request diagnostics refer to `<analysis-request>` byte spans.

Cancellation is sticky for the process invocation. Checks occur between file
operations and semantic passes, plus before response publication. This first
version does not preempt a pass internally or reuse a cancelled invocation as a
persistent server. A cancelled or stale response cannot retain a publishable
top-level `admitted` status.

## Tests, integration and remaining gates

Focused unit entrypoints:

```text
run_json_read_tests()
run_analyze_tests()
```

Portable CLI verifier after dispatcher integration:

```text
python -B scripts/verify-analysis.py --beryl <captured-compiler>
```

The verifier uses explicit subprocess arguments and owned isolated fixture
directories. It retains raw stdout/stderr and input fingerprints. It checks
unchanged inputs, exact versions, Unicode/CRLF byte spans, all three target
admissions, taint, unknown/duplicate members, malformed UTF-8/surrogates, missing
overlays despite existing logical disk files, hash mismatches, strict paths,
hardlinks and locally available symbolic-link rejection. The Windows run also
observes real held-file locks before attempting concurrent writes and sending
CTRL_BREAK to its own child process.

Reader units include a deterministic raw-byte malformed-input corpus and
mutations of nested valid JSON seeds, run at O0 and O2 with UBSan. This is bounded
regression coverage, not exhaustive fuzzing or a complete security audit.

The combined MCP verifier now establishes CLI parity and an actual isolated
installed C-launcher/loader/server path; see [P6_MCP.md](P6_MCP.md) for its exact
receipt. POSIX compilation/runtime, deterministic POSIX mutation races, directory
ACL verification, stale-client-buffer discard in an actual editor, LSP conversion
and fixed AI authoring tasks remain separate incomplete gates. The adapter reuses
this CLI/API and its identities; it does not reimplement compiler semantics in Python.

Completion evidence is recorded after the final private source freeze and
integrated dispatcher verification. Earlier candidate runs are retained and do
not establish correctness of subsequently changed source bytes.

### Private freeze evidence

The isolated sources and harnesses are retained in
`build/p6-analysis-stage-5c4a11b447cc4fd48790837099f5838c/`.

- `unit-frozen-o0.exe`: 11 cases / 6,192 checks passed.
- `unit-frozen-o2.exe`: 11 cases / 6,192 checks passed with UBSan and no recovery.
- `analyze-frozen.exe`: O2+UBSan CLI candidate, SHA-256
  `c385d30bf6c5e31a0b580fe032924f9109805224b07d6728776cab0eaf784540`.
- `build/analysis & spaces-ordotj5l/results.json`: 64 successful groups; one
  explicitly unavailable symbolic-link creation probe (Windows privilege 1314).
  Hardlink rejection, actual held-input write rejection and process cancellation
  passed. The symbolic-link case is not counted as verified.

The retained source manifest records every private C/header input and both test
harnesses. Independent review of the new reader/analyzer sources found no further
material issue after the direct API's pre-hash/pre-SourceMap byte-bound repair.
The final units include that regression.

These are private candidate results. Dispatcher registration, current combined
compiler suites and trusted-tool-bundle integration are separate root-owned
checks. No active compiler was replaced by this packet.
