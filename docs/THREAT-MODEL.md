# Beryl — Threat Model & Residual Attack Surface

**Status:** v0.1 · maintained alongside [SECURITY.md](SECURITY.md), which
describes what the model *does*; this one describes where it stops.

**Legend.** **FIXED** = landed in code and tested · **BOUNDED** = a real risk a
defence limits to a stated degree *at a stated cost* — **not eliminated** ·
**IRREDUCIBLE** = a limit the current design cannot remove; stated with its
floor, never marked sealed · **ACK** = known, accepted, priced ·
**NOT-IMPLEMENTED** = designed but absent, so it protects nothing today.

**Honesty rule for this document:** a fundamental limit is never written
"FIXED". It is "BOUNDED to X at cost Y" or "IRREDUCIBLE at floor X". Nothing
here is described as making a program "safe".

**Adversary.** Two, depending on the target. Natively: a malicious or careless
*dependency*, and a *crafted source file* fed to the compiler. On the enfusion
target: a **client you do not control**, sending arbitrary RPC arguments to a
server-side mod, plus everything the engine itself permits.

---

## 1. Residual register

| # | Risk | Mechanism | Status | Residual |
|---|---|---|---|---|
| **S1** | The compiler is written in C; crafted source and tooling inputs can reach parser, allocator and traversal defects. | Checked allocation arithmetic and bounded analyses are being integrated in the delivery program. | **BOUNDED** | Targeted tests do not establish absence of memory defects. See the delivery state for exact tested scope. General fuzzing and all-input resource containment remain incomplete. Self-hosting alone would not establish correctness or remove this risk. |
| **S2** | Capabilities are erased at codegen, so they bind what compiled Beryl code can *express*, not what machine code can *do*. | Type-system enforcement, manifest declaration, `beryl audit`. | **NOT-IMPLEMENTED** | Capability-based I/O does not exist in v0.1 (SECURITY §6). There is also no I/O to protect. When it lands, the residual above applies in full: **one `@unsafe(ffi)` block leaves the model entirely**, and `forbid_unsafe` is the only hard control. |
| **S3** | Static taint analysis is incomplete. | Delivery work adds monotone whole-program propagation, field paths, conservative element summaries and finite fixed-array interval checks. | **BOUNDED** | Context-insensitive source restrictions, with explicit analysis limits. Full symbolic dependencies, dynamic-storage range facts and reviewed engine boundaries remain incomplete. The tested repairs do not establish general security soundness. |
| **S4** | `@constant_time` survives Beryl's front end, not necessarily clang's back end. | Source-level refusal of secret-dependent branches and indices, transitively through callees. | **BOUNDED, weakly** | The classic problem: **LLVM may reintroduce a branch Beryl forbade**, and routing through C makes this harder to control, not easier. No optimization barriers are emitted in v0.1. Treat as a lint and read the assembly. Machine-level verification is v0.2. |
| **S5** | Checked arithmetic can cost performance. | Checked, wrapping and saturating operations have different explicit arithmetic contracts. | **ACK** | Historical microbenchmarks apply only to their recorded inputs and flags; they do not establish current whole-workload overhead or that an operation is free. Adoption requires the delivery program's matched measurement protocol. |
| **S6** | Enfusion output runs inside an engine Beryl does not control. | Profile lint, `@server_only`, `@untrusted`, no-BOM/tab output conventions. | **BOUNDED** | Beryl can guarantee properties of the **generated script**, never of the engine executing it. Enfusion's own sandbox, its RPC layer, and its replication rules are the outer boundary and are entirely outside this model. |
| **S7** | `!T` loses the error tag on the enfusion target. | Lowered to `bool` + `out`, the idiom the base game uses. | **ACK** | A caller can tell that *an* error occurred, not *which*. Deliberate: the alternative pollutes every signature with a second `out`. Return an enum where the distinction matters. |
| **S8** | Builds depend on a trusted native compiler and local toolchain. | Explicit argv execution and retained native evidence identify the selected tool and inputs. | **ACK** | A recorded hash identifies bytes; it does not certify a trustworthy compiler. PATH/configuration and toolchain provenance remain part of the trust boundary. |
| **S9** | Generated C can be valid but semantically wrong. | Retained generated C, O0/O2 execution, bounded independent reference evaluation and expected-trap comparisons. | **BOUNDED** | Only admitted and tested semantics have this evidence. Public IR and complete ownership remain gated. Test counts and applicable receipts are in the delivery state rather than duplicated here. |

---

## 2. What the taint engine actually catches

Worth being concrete, because "taint analysis" oversells it.

**Caught:**

```beryl
@untrusted
fn on_rpc(inout self, let i: i32) {
    self.slots[i] = 1          // BE0601
    let j = i + 1
    self.slots[j] = 1          // BE0601 — taint survives arithmetic
}
```

**Historical gaps addressed by the delivery taint work:**

```beryl
@untrusted
fn on_rpc(inout self, let i: i32) {
    self.pending = i           // provenance is now recorded on the field
    self.apply()               // propagated through admitted method calls
}
```

```beryl
@untrusted
fn on_rpc(inout self, let i: i32) {
    var xs: List<i32>
    xs.push(i)
    self.slots[xs.get(0)] = 1  // element summary retains untrusted provenance
}
```

The examples illustrate flow shapes, not independent executable fixtures.
[P1 taint safety](advanced/P1_TAINT_SAFETY.md) identifies the executable regressions
and implementation limits. The pass joins calls, returns and mutable arguments
to a bounded fixed point. It does not prove engine authority or arbitrary
storage-validity contracts.

---

## 3. What is deliberately out of scope

- **Denial of service.** Nothing bounds loop counts, allocation, or recursion
  depth in generated code. An `@untrusted` value can still drive a loop.
- **Cryptographic correctness.** `@constant_time` is a lint over one narrow
  property (S4). Beryl has no crypto primitives and offers no opinion on yours.
- **The engine's own attack surface** (S6).
- **Anything about the host toolchain** beyond S8.

---

## 4. If you are relying on this

The honest summary: Beryl v0.1's security work is **real and useful as a set of
compile-time lints that catch a class of mistake early**, particularly the
RPC-boundary one it was built for. It is not an assurance argument, it has not
been reviewed by anyone else, the compiler underneath it is written in C and has
not been fuzzed, and the codegen surface (S9) is thin.

Use it the way you would use a good linter that happens to be part of the type
system. Do not use it as the reason something is safe.
