# Advanced stages A/B: verification and authoring foundations

This packet records implementation begun on 2026-09-07 under the
[approved advanced program](../BERYL_ADVANCED_IMPLEMENTATION_PLAN.md).
See [execution state](../BERYL_ADVANCED_IMPLEMENTATION_STATE.md) for final integrated
compiler identity and release gates. Development results below identify their own
candidate; they are not interchangeable evidence for later changed bytes.

## Objective and admitted scope

Make first source failures independently verifiable, repair reproduced Enfusion
integer intrinsic defects, expose compiler context, retain native machine output,
and associate generated engine diagnostics with source. Preserve AST lowering and
ordinary compilation. No Beryl optimization family is released by these changes.

### Source traps

Public verification-only interface:

```text
beryl test --backend differential --expect-source-trap overflow@0:123 source.be
beryl test --backend differential --expect-source-trap bounds@0:234 --observe-root 0:45 source.be
```

Offsets are zero-based bytes, not display columns. File IDs identify the loaded
source sequence (also recorded in result `sources`). Supported expected kinds are
`overflow`, `division_by_zero`, and `bounds`; options reject signs, whitespace,
trailing characters, duplicate selections, and incompatible backends.

An expected-source-trap result can have `status: success` while
`program_outcome: trap`. This means the fixture verified the specified failure; it
does not mean the tested program returned normally. Ordinary tests still fail on
traps. Reference limits, unsupported input domains, missing tools, native crashes,
timeout, cancellation, or incomplete trace are not matching source failures.

Native trace-only wrappers identify the checked operation after arguments have
evaluated. The normal checked arithmetic implementation remains in use. Before an
expected trap, the runtime flushes prior output and emits a terminal typed JSONL
event; the driver checks source kind/site, ordered events, output, and nonzero
completed native exit. The human diagnostic is preserved after the terminal event.

`--observe-root` admits exactly one top-level initialized local `[i32; N]` in one
test, with 1 ≤ N ≤ 4,096. The source offset identifies its declaration. Both
executors inspect that actual array before the terminal trap. Missing, moved,
inactive, unsupported, or partially initialized observations fail admission or
verification. This is not general heap, engine-reference, or hidden-write coverage.

The independent reference was corrected for `INT_MIN % -1`: the specified result
is zero. `INT_MIN / -1` remains an overflow. The correction agrees with the existing
specification and native runtime; it does not redefine arithmetic to satisfy a test.

Development evidence: `build/expected traps & nc6a0ygs/results.json`, with immutable
compiler/source/Clang manifest in `build/expected-trap-compiler-5v2j2nvv/build.json`.
Eight trap fixtures run at O0/O2, the observed prefix `[21,21,0,0]` uses no body
prints, ten compiled mutants are rejected, and crash/timeout/external cancellation
are distinguished. Instrumented execution is semantic evidence; it is not a
performance measurement or a claim about uninstrumented vectorization.

### Enfusion integer repairs

The preserved installed compiler produced 288 mismatches in 858 real Workbench
checks: `build/engine-integers-fpu4w7kf/engine-runtime.json`. Examples included lost
low bits in large-integer min/max/clamp and incorrect signed-boundary saturation.

The repaired emitter selects `Math.MinInt`, `Math.MaxInt`, and `Math.ClampInt` for
i32. Saturating add/sub captures operands once, left-to-right, and uses sign-guarded
threshold comparisons before arithmetic, keeping every intermediate in range.
The float bindings remain separate. Constructor/setter behavior and PID tuning do
not change.

Development candidate `build/engine-integers-n77v37ka/result.json` passed 553
independent fixtures and 860 VM checks, including two added evaluation-order cases.
No failures. The full PID EnforceScript was byte-identical to the earlier verified
`403dd5ef7a67efc670db2779bab2be81adbe9ce22bb4d98921f3d3c4d4a0b3e5`
output in `build/integer-pid-emission-a8vq7maj/result.json`.

This repairs these intrinsics. Ordinary Enfusion checked integer arithmetic and
all failure behaviors do not thereby have complete native parity.

## Context and public controls

```text
beryl context project [files...]
beryl context symbol module.Type.method [files...]
beryl context binding Math.MinInt
beryl context optimization module.function [files...]
beryl context optimization --list
```

Context is read-only C code, JSON by default. It resolves actual declarations and
reports byte spans, source/compiler identity, access modes, and separate native,
Enfusion, and reference admission results. Admission probes execute no user code,
Clang, Workbench, or model. Effects and unreviewed bindings are unavailable rather
than assumed pure/verified. Binding extraction and reviewed semantic contracts are
different capabilities; the current binding command does not invent an installed
verified registry.

The optimization catalog records proposed research families and prerequisites;
the selected/released set is empty. `--disable-opt` accepts registered names and
rejects unknown names. `--opt off` affects Beryl families only; `--release` still
selects Clang O2 with the same arithmetic flags. `--lowering auto` currently selects
AST; explicit `ir` exits unavailable instead of silently selecting AST. Reference
execution accepts its AST mode and rejects incompatible native controls.

Context development verification: nine groups in
`build/context & spaces-6zwks1mk/results.json`, including duplicate names, qualified
lookup, missing input, configured manifest prefix, target admission isolation, and
deterministic output.

## Native evidence

```text
beryl build --release --save-native-evidence --lowering ast --opt off -o candidate.exe program.be
```

Every build already retains isolated source/compile logs. The new opt-in evidence
mode additionally fingerprints the selected native compiler, captures version and
exact argv, generated C/runtime identities, LLVM IR, assembly, and Clang's driver-job
report. These are separate inspection passes under the same optimization/arithmetic
settings. They do not execute the program or constitute timing measurements.

The selected compiler executable is identified; dependent SDK and linker binaries
are explicitly outside that fingerprint scope. Missing/empty required output,
failed launch/pass, timeout, changed compiler, or failed evidence write prevents
publication/execution. Structured version-process status survives failed identity
probes. A previously published executable remains untouched on failure.

Development validation: 18 groups in
`build/native evidence & spaces-sc1hgs0c/results.json`. Tests include distinct prior
output preservation, empty IR/assembly/driver reports, version failures/timeout,
failed passes, and an unwritable evidence manifest. No retry mutates binary content.

## Source mapping contract

```text
beryl build --target enfusion --out-dir generated --source-map source-map.json input.be
```

Sidecars associate generated complete lines with original byte spans. They bind
exact generated/source hashes and preserve declaration identity, source statement,
prepared expression, default template plus requesting expansion site, constructor,
value-helper, and exported-wrapper origins. Mod tooling adds companion export JSON
pointers and includes the sidecar in artifact identity outside engine script discovery.

No engine-column interpolation is claimed. Unknown locations preserve raw
diagnostics. Default expansion records the template and outer requesting occurrence;
the complete intermediate nested expansion stack is not yet serialized. Signature
lines have declaration-level associations rather than token-level mappings for each
argument. Helper-origin associations are compiler synthesis sites, not claims that
the user wrote generated helper statements.

Maps cannot overwrite the Beryl input or generated C path. A failed requested map
write fails generation. Mod promotion requires exact artifact/sidecar identity.
Direct generation can retain incomplete candidate output after a failed sidecar
write; that failed command is not a promotable artifact.

## Compatibility, rollback, and open gates

- Existing native/reference commands remain compatible; added result fields are additive.
- Version-1 companions remain strict; scenario selection uses typed installed CLI parameters.
- Original compiler and dirty-source snapshot are retained in the advanced entry baseline.
- Live MESH, original PID fixtures, brandkit, and external editor integration sources remain preserved.
- The final exact-byte integration evidence is in the advanced execution state;
  the development reports above remain tied to their earlier compiler identities.
  Broader A/B capability gates still require their own evidence.
- General effects/storage/IR, complete binding annotations, profiling/memory inspection,
  all named scenarios, multiplayer acceptance, and whole-mod authoring remain separate work.
- No native-versus-Rust advantage or complete-workload optimization is established here.
