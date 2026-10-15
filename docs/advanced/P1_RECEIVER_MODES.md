# Receiver modes: bounded ownership implementation packet

This packet addresses method receiver accounting in the existing AST frontend.
It does not add owned-container transfers, runtime cleanup, production IR
lowering, performance optimizations, or an engine-runtime acceptance result.

## Confirmed baseline defects

The read-only audit used compiler
`6207c9660130b8382b76b90b12890149ff4fa70cfd3ab67e989ac47d9ab6eec6`.
Its retained sources, commands, generated candidates and outcomes are in
`build/receiver modes & spaces-kvr14r5y/results.json`, SHA256
`4e02003d430101a990228f0d12f74c3176f81fc825c7a52afa3d14fa82d20c14`.
All 76 audit commands completed. This means the audit ran; it does not mean the
tested programs all satisfied the language contracts.

The audit paired explicit and implicit uses of plain records:

| Operation | Method receiver before repair | Equivalent explicit argument |
|---|---|---|
| Consume a record and read it afterward | Native/Enfusion checks accepted; native O0/O2 retained `1`; reference failed on moved storage | `BE0403` |
| Consume a `let` or `inout` parameter | Accepted; native O0/O2 retained the caller's value; reference failed after consumption | `BE0406` |
| Consume a projected child | Accepted; native O0/O2 retained `1`; reference failed on the moved child | `BE0406` |
| Initialize an uninitialized whole record via `set` | Incorrectly rejected twice with `BE0405` | Reference/native O0/O2/differential initialized it to `7` |
| Replace an initialized immutable local via `set` | Accepted and changed it to `7` | `BE0407` |
| Replace a `let` parameter via `set` | Accepted and changed it to `7`; native generation warned about discarded `const` | `BE0407` |

Four sink-method fixtures failed both reference and differential verification.
Those eight failures remain failures in the audit receipt. In the differential
failures, reference execution stopped before a native comparison was attempted;
the separate ordinary native O0/O2 commands establish the native outcomes.

Owning `sink` and `set` method declarations were already contained: native
checking rejected them with `BE0903`, and Enfusion checking with `BE0701`, just
like explicit parameters. This repair preserves that declaration-level boundary.

## Contract and implementation

`src/sema/ownership.c` now uses one `walk_call_argument` routine for implicit
receivers and written arguments. A receiver remains the first evaluated actual
argument. Expanded defaults follow written arguments under the existing default
expansion rules.

| Mode | Before entering the callee | After all argument evaluation |
|---|---|---|
| `let` | Walk the expression once, preserving reads and index effects | No ownership transition |
| `sink` | Use the existing `do_move`; reject borrowed/partial moves and mark a valid whole owner moved | No synthetic reinitialization |
| `inout` | Walk the place once; check exclusive access and initialization; projected access requires an initialized parent | No initialization promise |
| `set` | Walk the place once; check destination permissions without reading an uninitialized whole root; projected access requires an initialized parent | Mark an admitted whole root initialized only after all arguments and exclusivity checks |

The `finish_call_argument` routine performs the existing post-call whole-root
`set` transition for receivers and explicit arguments. It does not promote a
partially initialized aggregate into an initialized whole value.

An initialized immutable local still cannot be replaced. Its first initialization
through `set` remains admitted when the entire binding was uninitialized. A
whole-root `set` can reinitialize storage after a whole move, consistent with the
existing explicit-argument contract. A nested `set` method can discharge its
caller's own `set` initialization obligation.

The caller cannot read the old uninitialized receiver through a later argument
merely because the future callee promises initialization. Such reads fail before
entry. Conversely, successful writes already performed by a callee remain
observable if later execution fails. Calls are not transactional. The repair
changes frontend state accounting; it does not introduce rollback or trap
unwinding.

Place selection is analyzed once. Previously a `let` method receiver could pass
through both `walk_place` and `walk_expr`, analyzing an effectful index twice.
The new regression selects an array element using a helper that consumes its
index argument. The selection is admitted once; a subsequent use of that index
remains a use-after-move error. This is an ownership traversal guarantee, not a
claim that arbitrary dynamic indices prove disjointness.

Existing whole-call exclusivity, `restrict` admission, bounded captured-call
analysis, target storage admission, generated calling conventions and reference
evaluation remain in place. A non-place `inout`/`set` receiver remains rejected
by the shared call-capture admission boundary (`BE0401`). This packet does not
claim a new general alias analysis.

## Regression coverage

`tests/unit/test_ownership.c` adds 20 focused cases for:

- Whole, borrowed and partial receiver moves; later argument reads after move.
- Independent sink temporaries.
- Whole-root `set` initialization, first initialization of a `let`, outer `set`
  obligations, and reinitialization after a move.
- Immutable/read-only replacement rejection, delayed initialization, partially
  uninitialized parents, and conditional callee initialization obligations.
- Once-only receiver index transfers, their retained move state, and defaults.

`tests/e2e/receiver_mode_order.be` has a fixed expected ordered output in its
`.expected` companion. It covers method and explicit `set`, nonmutating defaults,
move/reinitialization, first initialization, indexed `let` and `set` receivers,
and a fresh sink receiver. Its markers must appear once at the original positions.

`scripts/verify-receiver-modes.py` contains deterministic standalone source
fixtures. It materializes them only in an isolated `build/receiver modes verified
& spaces-*` directory and records their exact hashes. It never changes an
installation, launches Workbench, or selects an arbitrary project script.

The runner has 29 negative fixtures. Its 25 plain-mode negatives run through 15
admitted CLI routes:
human/JSON native and Enfusion checking, native C emission, AST native build/run,
Enfusion generation, native O0/O2 testing, AST reference testing, and AST/IR
differential O0/O2 frontend admission. Mode failures must occur before jobs,
generation, execution, or replacement of prior output sentinels. Four owning
declaration fixtures run the ten native/Enfusion frontend routes applicable to
their physical storage admission and retain `BE0903`/`BE0701`. Owning types are
outside the reference/IR subsets; their different unavailable stages are not
misreported as these storage frontend gates.

Its ten positive fixtures each run native/Enfusion checks and analytical AST
reference/native differential execution at O0/O2. Their fixed assertion counts
and ordered output are independent expected values. The e2e main program runs
at O0/O2 and compares ordered text with CRLF normalized. Differential comparisons
retain exact ordered events and binary log hashes.

The complete inventory is 467 cases: 415 negative routes, 20 positive frontend
checks, 30 positive reference/differential executions, and two e2e executions.
The 30 positive semantic executions have 39 analytical assertions in total.

Only the AST execution paths currently admitting these modes are selected for
positive execution. An IR frontend rejection test does not imply IR `set` or
`sink` support, and explicit production IR selection remains unavailable.

## Verification and handoff

Run against a freshly built, explicitly identified candidate:

```text
python scripts/verify-receiver-modes.py --beryl <candidate> --clang <clang>
    --expect-compiler-sha256 <candidate-hash>
```

The runner predeclares the entire expected case set before execution. Startup
failure, timeout, cancellation, wrong diagnostics, source changes, native failure,
output/event mismatch, or incomplete cases retain a failed receipt. Prior failures
are preserved even if a corrected harness subsequently passes.

Compiler, Clang, source/runtime, unit/e2e inputs, generated fixtures and the runner
are hashed before and after verification. Each positive comparison retains its
job receipt, event hash, generated C hash and actual native executable hash.

The separate 76-case pre-fix audit and the earlier 242-case captured-call
verification remain valid within their own hashes and scopes; neither is
substituted for verification of this changed compiler.

## Current verification — October 8, 2026

The compiled source capture is
`build/oct08-receiver-candidate-yrocyf2o/snapshot.json`, SHA256
`41b554688eb18df634b2a00bba3ef59a9d6c2c6194a1119ccf959c81d94b8df0`.
All 107 captured compiler/runtime files agree with the current root's checked
bytes. The targeted runner received harness corrections after the capture; no
compiler source was changed for those corrections.

| Evidence | Recorded outcome |
|---|---|
| Normal unit-only attempt | Compilation succeeded; unit executable startup denied by Application Control, WinError `4551`; no normal-unit pass |
| UBSan unit-only attempt | 558 cases / 10,478 checks passed; generated native regression programs were explicitly not selected |
| Normal CLI compilation | Produced compiler `1cc17253ebc0cb6ed86003368f1125cdfdf408091048c4cd3f1c57c128b3f9db`; compile-only evidence is not a conformance result |
| Corrected receiver matrix | 429/467 cases completed, then optimized reinitialization candidate startup failed with OS error `4551` |
| Source-only continuation | The remaining 14 safe native/Enfusion checks passed; no cache change or generated-program execution |

The corrected matrix completed all **415 negative routes**, including borrowed
and partial receiver moves, use-after-move, read-only replacement, initialization
ordering, owning transfer containment, and non-place mutable receiver rejection.
It completed eight semantic executions with ten analytical assertions: reference
and native differential O0/O2 for whole-root uninitialized method/explicit `set`,
and reference plus native differential O0 for move/reinitialization. Five native
comparison candidates actually executed successfully. The optimized
reinitialization candidate compiled but did not execute; its failure is not a
source trap or a semantic mismatch.

The source-only continuation covers the other seven safe fixtures on both
targets. Together with the main attempt, all 20 positive frontend checks are
complete. This establishes 443 distinct completed cases across the two receipts,
with 24 planned execution cases still incomplete, including the denied one.
The complete 467-case matrix, e2e O0/O2 gate, and normal foundation gate remain
open. No denied executable was retried, modified, or made into a new variant.
No engine was launched and no installation was changed.

| Receipt | SHA256 |
|---|---|
| `build/oct08-receiver-candidate-yrocyf2o/build/foundation-l90nmk33/results.json` — normal unit startup failure | `caf2861da875fb06a6fd3a3db14ebf4d98561512fd7f325df714ea670038f37e` |
| `build/oct08-receiver-candidate-yrocyf2o/build/foundation-uzwpb5ny/results.json` — UBSan unit-only success | `aec29f4c56951cafdada6e733f150f22ff1ff01d5ec9f54515e2fdd915febd4e` |
| `build/oct08-cli-compile-tsfphc2f/result.json` — normal CLI compilation only | `fb3a1efb0bb02117553a671f9724ca3e38fd45e49f1cfdf66cb30e04db28ff88` |
| `build/receiver modes verified & spaces-236oew5_/results.json` — incomplete receiver matrix | `9e5a807f22a69ade9773361cd20aacc720cb9da0866ee6a488fe56605f86b8b5` |
| `build/receiver modes verified & spaces-236oew5_/source-only-checks.json` — bounded continuation | `a396b828fbfb47d65b2d46d0118898823059cbabc728aa89a328924c2169a15a` |

The source-only receipt links the unchanged failed parent receipt and identifies
the exact original fixture bytes. It explicitly sets `full_matrix_complete` to
false. A successful source-only check does not establish execution parity.

Two earlier harness failures are preserved:

- `build/receiver modes verified & spaces-4n9b1yui/results.json`, SHA256
  `b4791467321fab78af3db9e4052229f27a0db801d707193ab735da2cf32f1662`:
  173/487 cases completed; a declaration-only owning fixture stopped at empty
  test selection (`BE0804`). A neutral selected test was added to the negative
  fixtures so actual storage admission could be checked.
- `build/receiver modes verified & spaces-xvu48ekq/results.json`, SHA256
  `eec596c9e3806e12124f6d90e32b2e31a0bd81f7ba5a3d01f6b7b26693df2606`:
  175/487 cases completed; an owning reference route correctly reported its
  unsupported declaration type (`BE1001`) through its own unavailable job.
  The erroneous physical-storage-stage oracle was corrected by limiting those
  four owning fixtures to their ten applicable native/Enfusion routes. The
  resulting explicit inventory is 467 cases. Unsupported reference/IR owning
  storage was not admitted to make the harness pass.

The repeat of the captured-call matrix on the final normal CLI is also
incomplete: `build/call captures & spaces-09mv8ybl/results.json`, SHA256
`dbf1822ca3b7788b9bb453ba6801da0f0932ca7cc946b277184d045839690f17`.
It completed 230/242 cases, including all 225 negative routes, then its disjoint
AST O2 candidate startup failed with OS error `4551`. Its earlier full success
on compiler `6207...` remains a historical checkpoint, not a complete pass for
the final compiler.


## Compatibility with Enfusion receiver containment

The verification table above records the earlier `1cc172...` checkpoint. Its
107 compiler/runtime hashes agreed with the worktree when that evidence was
captured; subsequent P4 and Enfusion backend changes require their own source
capture and verification. It is historical evidence, not a claim about later
compiler bytes.

The current Enfusion backend explicitly rejects declarations containing `set
self` or `sink self` with `BE0701`. Its implicit EnforceScript instance receiver
cannot initialize caller storage or transfer the caller's logical value. This
is target containment; the repaired native ownership and admitted AST reference
contracts remain unchanged.

The runner preserves all ten safe fixtures, all 29 negative fixtures, and all
467 predeclared cases. A reviewed per-fixture target inventory now expects:

| Safe fixture | Native check | Enfusion check |
|---|---|---|
| `uninit_method` | Admitted | Unavailable, `BE0701` (`set self`) |
| `uninit_explicit` | Admitted | Admitted (ordinary explicit `set` parameter) |
| `set_reinitialize` | Admitted | Unavailable, `BE0701` (`set`/`sink self`) |
| `let_first_init` | Admitted | Unavailable, `BE0701` (`set self`) |
| `outer_set` | Admitted | Unavailable, `BE0701` (`set self` declaration) |
| `sink_literal` | Admitted | Unavailable, `BE0701` (`sink self`) |
| `index_let_once` | Admitted | Admitted (`let self`, explicit scalar `sink`) |
| `index_set_once` | Admitted | Unavailable, `BE0701` (`set self`) |
| `defaults` | Admitted | Unavailable, `BE0701` (`set`/`sink self`) |
| `method_explicit_parity` | Admitted | Unavailable, `BE0701` (`set`/`sink self`) |

Every source-only target check records its target outcome separately from the
compiler's JSON status. Expected Enfusion unavailability requires a nonzero
exit, JSON failure, the selected compiler identity, `BE0701`, and no new job.
An unavailable target check can complete its declared verification case; it
cannot establish successful Enfusion compilation, generation, or execution.
A new fixture without an explicitly reviewed target oracle stops the runner.

Ownership negatives retain their earlier `BE0403`/`BE0404`/`BE0405`/`BE0406`/
`BE0407`/`BE0401` source failures before target lowering. The four owning
negative fixtures still require native `BE0903` and Enfusion `BE0701`.
Reference and native O0/O2 positive execution selections are unchanged. No
fixture or case was removed to accommodate the target boundary.

The original runner SHA256 was
`97c2e818c55e21253dc2f5ab0a4420866d1c5e2231e0b8cf784ef2086c1c9d4f`.
The unchanged 429/467 receipt and 14-case source-only continuation above retain
that runner identity, their original target outcomes, and the 443/467 union.
They must not be reclassified using the new target expectations. The recovery
index is `build/oct08-recovery-index-7b91aa46cec349b1915fbeac063fb35f.json`,
SHA256 `ddef4d0a656d038452022d385c0a3dd84cdde06c5a169134ba53d0d5f04dff06`.

This compatibility update has only been statically reviewed and syntax parsed.
No generated program, full matrix, denied artifact, or engine was rerun. A
future execution uses a fresh explicit source/candidate identity and creates
new receipts; existing failed and partial receipts remain unchanged.
