# Captured call arguments: bounded implementation packet

This packet covers a confirmed correctness mismatch and its shared admission
boundary. It makes no ownership-completion, performance, or engine-runtime claim.

## Confirmed problem and selected contract

Native AST calls capture a pointer for each `inout`/`set` argument and for a
non-copy `let` aggregate that names local storage. The reference interpreter also
captures a place for plain records and fixed arrays. Their physical storage
representations differ: native aggregates live inline, while the reference
interpreter retains separate logical member objects.

When `observe(parent.child, replace(inout parent))` selects a child and then
replaces its parent while evaluating the next argument, the two implementations
can observe different children. The reproduced record and fixed-array cases
returned `9` natively at O0/O2 while the reference fixture expected the selected
value `1`. Those disagreements are defects, not successful differential checks.

The selected containment contract rejects a captured borrowed place whose own
selection or later argument evaluation can write, move, or replace overlapping
storage. The diagnostic is `BE0401`, before a job, generated output, or native
execution. Authors make the intended order explicit: mutate before selecting the
argument, or bind an independent value snapshot before the mutation.

An ordinary scalar `let` argument is already captured by value. An aggregate
rvalue is prepared in independent temporary storage. Neither needs to keep its
original source place live through later argument evaluation. A direct later
`sink` of local storage is a transfer during evaluation; an independent sink
literal or returned value consumes no earlier local storage.

## Shared analysis and limits

`src/sema/access.c` reuses its bounded mutation scanner for call capture. A method
receiver is the first selected argument. The protected interval includes index
selection and the normalized trailing defaults produced by semantic analysis.
Nested blocks, calls, loops, branches, and immediate `defer` are visited. Potential
writes in short-circuit or unreachable source remain conservatively checked.

Declared field identity and unequal literal indices prove separation only when
the involved roots are recursively plain logical values. Dynamic indices,
unknown call effects, generic/external calls without a reviewed summary, and
owning/reference roots cannot manufacture a non-aliasing guarantee.

`src/reference/admit.c` also checks this boundary for direct reference-API callers
that did not run the ordinary shared ownership pass. Ordinary CLI paths report
`BE0401`; direct reference admission reports its own unavailable outcome.

This is a bounded mutation check, not complete interprocedural effects or
ownership. Existing whole-call exclusivity still checks direct `inout`/`set`
overlap. Method move accounting, owned-container lifetimes, and the complete
native alias contract require their own gates. This packet does not claim those
issues are repaired or release production IR lowering.

## Regression corpus

`tests/reference/call-captures/` contains exactly 20 named source fixtures:

| Category | Fixtures | Required outcome |
|---|---|---|
| Projected captured storage | `projected_record`, `projected_array`, `array_element`, `projected_inout`, `projected_set` | `BE0401` before generation or execution |
| Receiver and selection | `method_receiver`, `method_inout`, `selection_index` | Same frontend rejection |
| Transfer and nested effects | `direct_sink`, `nested_sink`, `nested_set`, `nested_mutation`, `nested_block`, `loop_mutation`, `short_circuit` | Same frontend rejection, including potentially skipped writes |
| Independent repairs | `snapshot`, `scalar`, `disjoint`, `sink_temporary`, `defaults` | Exact analytical assertions and ordered output |

The positive analytical oracles are fixed in the runner, independently of the
implementations. Each fixture has one test. Snapshot checks six assertions and
prints `1, 1`; scalar checks three and prints `8`; disjoint checks eight and
prints `1, 11, 11`; independent sink values check three and print `8, 4`.
Default expansion checks two assertions and prints `77, 77, 1, 1`, showing one
nonmutating observable default evaluation for each free/method call. These are
ordered lines, not unordered value sets.

The disjoint fixture also requires an unrelated index helper to execute exactly
once. It does not establish arbitrary alias or iteration support.

## Verification runner

Run `scripts/verify-call-captures.py --beryl <fresh-candidate> --clang <clang>`
against an explicit candidate after its matching source capture/build exists.
The runner creates one isolated `build/call captures & spaces-*` directory.
It never launches Workbench, changes an installation, or promotes an artifact.

For each of 15 rejected fixtures, the runner checks 15 supported routes:

- Human/JSON `check` for native and Enfusion.
- `emit-c --tests`.
- Explicit AST native `build` and `run`, preserving a previous output sentinel.
- Enfusion generation into a directory containing a previous source sentinel.
- Native AST tests at O0/O2.
- Explicit AST reference tests.
- Differential tests selecting AST and experimental IR at O0/O2.

Every route must produce `BE0401` with the call-capture repair diagnostic. No cache
job or output change may occur. `emit-c` must emit no C text. Enfusion checking and
generation commands here test frontend admission; no engine execution is implied.

The five safe fixtures run through reference and AST differential O0/O2. The
snapshot fixture additionally selects experimental IR differential O0/O2 within
its existing plain-record/array admission. The runner does not loosen IR to admit
disjoint dynamic places, `set`, `sink`, or other unsupported categories.
Production `build/run --lowering ir` and `reference --lowering ir` are unavailable
or incompatible before frontend analysis, so they are not mislabeled as `BE0401`
routes. Reference execution remains AST-based.

Successful verification requires the complete deterministic inventory: 242 cases
(225 negative command cases and 17 positive executed cases). Each retained
positive execution identifies its original source, exact compiler, job receipt,
ordered event stream, and generated native candidate where applicable. The runner
checks compiler, Clang, runtime, relevant source, script, and fixture hashes before
and after the matrix. A startup failure, timeout, cancellation, missing fixture,
changed input, or partial inventory is failure; absent execution is never success.

The runner's receipt lives beside its raw outputs. It records the exact candidate
identity and predeclared expected cases, allowing the integration owner to attach
it to the matching immutable checkpoint. A partial attempted inventory cannot
close this gate.

## Completed bounded verification — October 8, 2026

The first targeted execution passed all 20 groups and all 242 expected cases:
225 frontend rejections, five reference executions, ten AST differential native
executions, and two experimental IR differential snapshot executions. The 17
positive executions completed 78 analytical assertions. Each of the 12 native
executables was identified from its retained bytes and checked against its
execution receipt; generated C and ordered reference events are retained too.

| Input or evidence | Exact identity |
|---|---|
| Compiler | `6207c9660130b8382b76b90b12890149ff4fa70cfd3ab67e989ac47d9ab6eec6` |
| Clang | `e04c3380970bf64d07074c390f550371dbd12dbb46a263609b11cd164ac1faf8` |
| Targeted runner | `2727d639865e312a0b21c1cfda4f904286b4f209b083df97e265a50af13e1530` |
| Candidate source capture | `d2a386ec6e4c1d75af5fee971a529a914c7859caa5c12f4ae405921e201a8fd1` |
| Targeted receipt | `4f60c394303069689d969f224a2f4e072a9962cdf6539dab80ac35c33e8965ef` |

The candidate is
`build/oct08-verified-candidate-jnp61es8/build/foundation-etwpyyq3/beryl.exe`.
The source capture is
`build/oct08-verified-candidate-jnp61es8/snapshot.json`. All 107 captured compiler
and runtime files agree with the targeted receipt's actual inputs. The runner
and two fixtures (`nested_block` and `loop_mutation`) were corrected after that
capture; the targeted receipt identifies their corrected bytes explicitly. The
fixtures use valid statement blocks and loops inside `inout` helpers rather than
unsupported value-producing block expressions. No compiler source changed for
those harness corrections.

The targeted receipt and raw outputs are in
`build/call captures & spaces-xyxrcstx/results.json`. Its complete tracked input
set was unchanged across execution. Enfusion frontend/generation rejection was
checked, but no engine was launched, no compiler was installed, and no production
IR backend was released.

This bounded success does not erase an independent foundation-run startup
failure or establish a complete language release. The integration owner retains
broader suite results separately, including unavailable or denied execution.
