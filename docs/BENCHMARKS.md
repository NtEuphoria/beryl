# Benchmarks

Every number here comes from `scripts/bench.sh`, so a claim that drifts is a
claim that gets caught. Measured on the development machine: Windows 11,
clang 22 (LLVM-MinGW), `x86_64-w64-windows-gnu`.

**Including the targets that were missed.** The spec set falsifiable numbers so
that failing them would be visible, and two of them failed.

## Scorecard

| metric | target | measured | |
|---|---|---|---|
| Compiler binary | < 1 MB | **297 KB**, zero dependencies | ✅ |
| Check 10,000 lines | < 500 ms | **124 ms** | ✅ |
| Full `-O2` build, 10,000 lines | < 3 s | **2.3 s** | ✅ |
| Lifetime annotations | zero | zero, none exist in the grammar | ✅ |
| Build-time code execution | zero | zero, structurally | ✅ |
| Hello-world binary | < 20 KB | **91.6 KB** | ❌ |
| Overflow-trap overhead | < 3% | **+82%** worst case | ❌ |
| Reproducible builds | byte-identical | not implemented | ❌ |
| Hot-loop codegen vs hand-C | within 5% | not measured | — |

## Binary size — target missed, and why

```
C runtime floor (bare C, int main(){return 0;})   88,064 bytes
beryl hello world (--release)                     91,648 bytes
Beryl's own contribution                           3,584 bytes
```

The `< 20 KB` target is **unreachable on this toolchain regardless of
language**: MinGW's C runtime alone is 88 KB, and a bare `int main(){return 0;}`
compiled with clang produces exactly that. Beryl adds 3.6 KB on top.

So the target was wrong rather than the implementation. The honest claim is
"Beryl's contribution to a binary is a few kilobytes", and the honest comparison
is that a Rust hello world on a comparable target is 150–300 KB — Beryl is
smaller, just not by the margin the target implied.

Reaching a genuinely small binary means `-nostdlib` with direct Win32 calls and
a hand-rolled integer formatter. That is a real v0.2 item, not a tweak.

## Overflow checking — target missed, and it mattered

The worst case that can be constructed: a dependent multiply-add chain, 80
million iterations, where every operation is a checked one and there is nothing
for the branch to hide behind.

```
LCG chain, beryl, checked arithmetic     193 ms
LCG chain, beryl, wrapping_*             101 ms
LCG chain, C, unchecked (-O2 -fwrapv)    106 ms

overhead, checked                        +82%
overhead, wrapping_*                       -4%   (identical, within noise)
```

**The `< 3%` target was badly wrong.** In an arithmetic-bound inner loop,
checking costs roughly 2x.

This measurement changed the design rather than being written up around: the
`wrapping_*` and `saturating_*` intrinsics exist *because* of it. They run at
the speed of unchecked C, so the accurate claim is:

> Correct by default costs about 2x in an arithmetic-bound loop. The opt-out
> costs nothing, and it says so at the call site.

### On the two numbers that are not here

Earlier revisions of this benchmark reported 9%, then −25%, from loops mixing
`+` and `%`. Those were measuring the optimizer, not the checks — in one run
Beryl came out *faster* than unchecked C, which is not a coherent thing for an
overhead measurement to say. They were removed rather than reported. A number
known to be noise is worse than no number.

The remaining figure uses a data-dependent chain (so neither compiler can fold
or vectorise it differently) and best-of-three (so scheduling noise does not
dominate).

## Front end throughput

```
check   2,006 lines     103 ms
check  10,006 lines     124 ms
build  10,006 lines   2,333 ms   (includes clang -O2)
```

The near-flat curve from 2k to 10k lines is process startup dominating: roughly
90 ms of the total is spawning the process and reading files, so the front end
itself is handling 10,000 lines in a few tens of milliseconds. Arena allocation
throughout, no proc macros, and no trait solver are why.

`beryl check` is the loop you actually live in. The 2.3 s full build is almost
entirely `clang -O2`, which is the price of getting LLVM's optimizer for free.

## Compiler

```
beryl.exe                297,472 bytes, zero dependencies beyond the CRT
startup incl. spawn       34 ms (mean of 20, Windows process creation dominates)
compiler source          ~11,800 lines of C11
```

## Not measured

**Hot-loop codegen versus hand-written C.** The claim in the README is parity,
on the reasoning that both go through clang's optimizer with the same
information. That is plausible but **unverified**, and it should not be believed
without a benchmark that does not exist yet.

**Reproducible builds.** Not implemented. `-DBERYL_BUILD_NONCE` deliberately
varies per attempt to work around Smart App Control ([BUILDING.md](BUILDING.md)),
which means output is currently *not* byte-identical between builds. These two
goals are in direct conflict and the conflict has not been resolved.

## Reproducing

```bash
bash scripts/build.sh
bash scripts/bench.sh
```
