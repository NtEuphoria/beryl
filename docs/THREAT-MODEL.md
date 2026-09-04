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
| **S1** | **The compiler is written in C**, a memory-unsafe language, and is the single largest item on this list. | Arena-only allocation, so there are no `free` calls to get wrong and no ownership questions between passes. Bounds-checked internal containers. 204 unit cases, 931 checks. | **BOUNDED** | Real and unquantified. The only untrusted input is a `.be` source file, but a crafted one could in principle crash or corrupt the compiler. Not fuzzed yet. **IRREDUCIBLE until self-hosted** — which is the actual argument for self-hosting, not aesthetics. |
| **S2** | Capabilities are erased at codegen, so they bind what compiled Beryl code can *express*, not what machine code can *do*. | Type-system enforcement, manifest declaration, `beryl audit`. | **NOT-IMPLEMENTED** | Capability-based I/O does not exist in v0.1 (SECURITY §6). There is also no I/O to protect. When it lands, the residual above applies in full: **one `@unsafe(ffi)` block leaves the model entirely**, and `forbid_unsafe` is the only hard control. |
| **S3** | Static taint analysis is **incomplete**. | Flow-sensitive over each function body, conservative at merges, taint accumulating on assignment. | **BOUNDED** | A strong lint, **not a proof**. Defeated by: indirect flow through a computed index or a handle; taint through a struct field written in one function and read in another (fields are not tracked per-field); anything crossing a `Map` or `List` element. Soundness must never be claimed. |
| **S4** | `@constant_time` survives Beryl's front end, not necessarily clang's back end. | Source-level refusal of secret-dependent branches and indices, transitively through callees. | **BOUNDED, weakly** | The classic problem: **LLVM may reintroduce a branch Beryl forbade**, and routing through C makes this harder to control, not easier. No optimization barriers are emitted in v0.1. Treat as a lint and read the assembly. Machine-level verification is v0.2. |
| **S5** | Overflow trapping costs performance. | `wrapping_*` and `saturating_*` opt-outs, measured. | **ACK** | **+82%** on a dependent multiply-add chain — far above the "< 3%" the spec targeted. Accepted deliberately: correct by default, fast by request, with the opt-out measured at −4% (i.e. free). See [BENCHMARKS.md](BENCHMARKS.md). |
| **S6** | Enfusion output runs inside an engine Beryl does not control. | Profile lint, `@server_only`, `@untrusted`, no-BOM/tab output conventions. | **BOUNDED** | Beryl can guarantee properties of the **generated script**, never of the engine executing it. Enfusion's own sandbox, its RPC layer, and its replication rules are the outer boundary and are entirely outside this model. |
| **S7** | `!T` loses the error tag on the enfusion target. | Lowered to `bool` + `out`, the idiom the base game uses. | **ACK** | A caller can tell that *an* error occurred, not *which*. Deliberate: the alternative pollutes every signature with a second `out`. Return an enum where the distinction matters. |
| **S8** | The build depends on `clang` being the one you think it is. | None. | **ACK** | Beryl shells out to `clang` from `PATH`. A hostile `clang` compromises every build. This is the same trust every C project extends, but it is worth naming: Beryl is not reproducible against a substituted toolchain, and no lockfile or hash covers the C compiler. |
| **S9** | Generated C is not reviewed before it is compiled. | `--emit-c` keeps it for inspection; the backend's own bugs surface as clang errors that say plainly they are compiler bugs. | **BOUNDED** | A codegen bug that produces *valid but wrong* C is invisible to clang and to the type checker. The 9 end-to-end programs and 3 trap tests are the only thing standing between a codegen bug and silently wrong behaviour. That surface is thin. |

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

**Not caught** — each of these is a real hole, not a hypothetical:

```beryl
@untrusted
fn on_rpc(inout self, let i: i32) {
    self.pending = i           // a struct field: not tracked
    self.apply()               // ...so this is invisible to the analysis
}
```

```beryl
@untrusted
fn on_rpc(inout self, let i: i32) {
    var xs: List<i32>
    xs.push(i)
    self.slots[xs.get(0)] = 1  // laundered by passing through a container
}
```

The engine tracks **local bindings within one function body**. That is genuinely
useful for the shape RPC handlers usually take, and it is nowhere near a proof.

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
