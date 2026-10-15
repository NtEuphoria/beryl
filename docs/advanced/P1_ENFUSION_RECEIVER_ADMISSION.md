# P1 Enfusion receiver admission containment

Status: source containment and the source-only verification gate passed in a
private candidate, 2026-10-08. Engine execution and live installation remain
unverified.

The shared ownership repair makes implicit method receivers obey the same source
order and ownership contracts as explicit arguments. That repair does not give
EnforceScript's implicit class receiver the physical behavior of a Beryl `set`
or `sink` argument. The native/reference plain-value behavior remains a separate
admitted path.

## Source-established lowering gap

The current EnforceScript emitter omits `self` from the method parameter list
and uses `this` for its expression. For example, an admitted native declaration
and call can initialize previously uninitialized caller storage:

```beryl
struct R { x: i32 }
fn R.fill(set self) { self = R{ x: 7 } }
fn example() -> i32 {
    var r: R
    r.fill()
    return r.x
}
```

The current Enfusion emitter instead declares a class local without constructing
it, invokes an instance method, and renders the whole-self assignment as
`this = ...`. It supplies no explicit caller-storage replacement parameter.
Similarly, a `sink self` method uses the implicit instance without implementing
the ordinary explicit argument's value-transfer boundary. These are inspected
emitter paths, not newly executed engine failure claims.

An `inout self` method can reach the same whole-self assignment emission. Field
updates have a different shape: `self.x = 7` renders a member write through the
existing instance and does not replace `this`.

## Conservative target boundary

`src/back/enforce_backend.c` rejects the following with `BE0701` before generating
or writing EnforceScript:

- Nongeneric function declarations containing `set self` or `sink self`, including
  unused declarations. Existing generic-instantiation and owning-storage gates
  remain separate.
- Direct whole-self assignment, including inside conditionals and other traversed
  blocks. This contains whole replacement in otherwise supported `inout self`
  methods as well.
- Whole `self` used as an explicit `inout` or `set` call argument. Moving the
  assignment into an ordinary helper would otherwise render `this` as its out
  argument without a caller-storage replacement boundary. This conservative
  gate also applies to helpers that happen not to replace their argument.

Read-only receivers, existing `inout self` field mutations, nested field-value
replacement and the full SPARKOS PID remain within their existing admission
boundaries. The check does not add ownership, cleanup, alias analysis or a released
IR mode. It does not prohibit replacing ordinary local values or explicit
`inout`/`set` arguments other than whole implicit `self`. Projected field and index
arguments retain their existing admission; passing `set self.x` differs from
passing `set self`.

Repair advice is to use an ordinary function with an explicit `set` or `sink`
parameter. Whole-self replacement can also be expressed using individually
admitted field writes or an ordinary explicit `inout`/`set` function. All existing
copy, move, borrowed-access and storage restrictions still apply; this advice
does not promise general owned-container transfer or engine-object copying.

The lint runs in `check -t enfusion`, target build admission and the emitter's
checked file-output entry point. Failed generation must leave prior output
untouched. Internal unchecked render helpers still require their caller to
complete target admission first.

## Verification packet

Nine focused unit cases are included in the existing Enfusion unit-test file.
They cover unused sink declarations, uninitialized set receivers, direct and
nested `inout self` replacement, helper-mediated whole-self replacement, retained
field/read methods and field helpers, and ordinary explicit set/sink functions.
Existing PID method-generation unit tests stay in
the same suite.

The source-only end-to-end runner is:

```text
python scripts/verify-enfusion-receiver-admission.py
    --beryl <fresh-identified-candidate>
    --expect-compiler-sha256 <candidate-sha256>
```

It predeclares 60 cases: nine negative fixtures through four Enfusion routes,
and six positive fixtures through four routes. The positive fixtures include
the complete current `packages/sparkos/pid/pid.be`, copied byte-for-byte into the
owned fixture directory. Checks and EnforceScript source generation run only
the explicitly selected compiler; no source program, Clang, Workbench or game is
executed. Native checking of positive fixtures confirms the target containment
did not become a shared-language restriction.

Negative routes check human/JSON diagnostics, source generation to stdout and
generation into a directory containing an existing `SPK_Generated.c` sentinel.
They require `BE0701`, no generated stdout, unchanged prior bytes, no additional
output and no native job. Positive routes check admission and actual generated
source, without treating that source as engine-compiled or executed evidence.

The runner retains exact commands, bounded raw logs, expected/completed case IDs,
compiler identity, source/runtime/tool hashes and generated-source hashes. It
limits each capture to 60 seconds and 1 MiB per stream, checks terminal pipe
errors and the final monotonic deadline, and owns only its selected compiler
process tree. Startup denial, timeout, cancellation, incomplete output, changed
input or an incomplete case set produce a failed receipt. The runner does not
copy, retry or modify a denied executable or change application-control policy.

The integration owner built ordinary candidate SHA-256
`61f3510b2d6024c22d0a21abf972df33f0e6e16d3e68d921103b581c3864828a`
and completed all **60/60** source-only cases in
[`enfusion receiver admission & spaces-ltyf1lu3/results.json`](../../build/enfusion%20receiver%20admission%20%26%20spaces-ltyf1lu3/results.json).
Receipt SHA-256:
`060596a4d2522386ad6d33f86be57baad926d68be5498f752dfeb4c82777f02f`.
The separate UBSan unit-only candidate passed 567 cases / 10,512 checks,
including these nine regression cases. No generated source was compiled in
Workbench or executed in the game. The ordinary generated-native-program gate
remains incomplete because Windows denied executable startup in preceding
matrices. This source-generation result does not bypass that gate.

## Compatibility and historical evidence

The earlier 467-case receiver-mode receipt remains an immutable historical
checkpoint for its own source/compiler hashes. Its successful Enfusion checks
of plain `set self`/`sink self` fixtures do not establish an engine lowering
contract and are no longer the expected result after this narrowing. The native
and reference receiver semantics are unchanged; their old receipts still apply
only to the original bytes. Revalidation of changed sources requires a new
receipt.

The broad receiver runner now expects target-unavailable diagnostics for the
newly excluded Enfusion shapes while retaining native/reference cases and its
complete 467-case inventory. Its existing receipts remain historical. This
packet supplies a separate completed targeted gate; it does not relabel or
complete the old partial native matrix. Neither passing generation nor
passing native/reference tests closes engine compilation, runtime lifecycle,
multiplayer or performance gates.
