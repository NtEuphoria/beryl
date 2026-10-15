# Benchmarks

**v0.2 collector:** [tools/beryl-bench](../tools/beryl-bench/README.md) builds a
Beryl kernel and a C baseline, checks stdout and exit status, then writes
evaluator-v1 receipts. Eligibility is decided by
[evaluate.py](../tools/beryl-experiments/evaluate.py), not by this document.
No Rust speedup is proven.

```powershell
python tools/beryl-bench/run.py collect --workload checked_lcg --beryl build/beryl.exe
```

`scripts/bench.sh` is retired. The tables below are historical notes attributed
to that script on Windows 11, Clang 22 (LLVM-MinGW), `x86_64-w64-windows-gnu`.
Review found an overflowing checked workload, ignored process failures, and a
generated build fixture without a main function. Do not republish them.

The approved
[v0.2 performance plan](V0_2_PERFORMANCE_PLAN.md) and
[advanced implementation plan](BERYL_ADVANCED_IMPLEMENTATION_PLAN.md) §4.3
define paired measurements, semantic checks, baselines, and evidence.

The new [standalone evidence evaluator](../tools/beryl-experiments/README.md)
implements the bounded receipt/statistics gate. Its current analytical tests do
not collect benchmark timings or replace the required workload collectors.

The old pass/fail marks are historical assessments, not current release gates.

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

These recorded sizes apply to an old executable and linking configuration.
They do not establish a minimum achievable size or an advantage over Rust.
Repeat size comparisons with exact tool, target, runtime, debug/strip, panic and
link settings before drawing conclusions. A custom runtime would be a separate
engineering decision, not a consequence proved by this table.

## Overflow checking — target missed, and it mattered

The old experiment attempted a dependent multiply-add chain over 80 million
iterations. Its checked arithmetic can overflow, and ignored process failures
mean the compared runs need not have completed equivalent work.

```
LCG chain, beryl, checked arithmetic     193 ms
LCG chain, beryl, wrapping_*             101 ms
LCG chain, C, unchecked (-O2 -fwrapv)    106 ms

overhead, checked                        +82%
overhead, wrapping_*                       -4%   (identical, within noise)
```

The recorded +82% is invalid as a current checking-overhead estimate. No fixed
cost multiplier follows from this workload. Checked, wrapping and saturating
arithmetic have different semantics; choosing one changes the program contract
and is not an exact optimization of the others.

### On the two numbers that are not here

Earlier notes reported 9% and −25% from different loops. None of these figures
has the required semantic and measurement evidence. Data dependence alone does
not prove identical machine work, and best-of-three does not establish
uncertainty. Use paired independent units, complete execution and retained
machine output under the approved protocol.

## Front end throughput

```
check   2,006 lines     103 ms
check  10,006 lines     124 ms
build  10,006 lines   2,333 ms   (includes clang -O2)
```

These historical end-to-end times do not isolate process startup, parsing,
checking or Clang time. The invalid build fixture also prevents using its build
time as successful compilation evidence. Stage B native evidence preserves
actual generated code, process arguments and outcomes for future measurements.

## Compiler

```
beryl.exe                297,472 bytes, zero dependencies beyond the CRT
startup incl. spawn       34 ms (mean of 20, Windows process creation dominates)
compiler source          ~11,800 lines of C11
```

## Not measured

**Hot-loop codegen versus handwritten C or Rust.** Sharing an optimizer does
not establish equivalent lowering, information or performance. Matched workloads
and measured machine output are required; no current advantage is established.

**Reproducible builds.** Content-changing rebuild nonces and security-control
retries were removed by the foundation work. That repair does not itself prove
byte-identical executable builds across environments. Generated-output
determinism and executable reproducibility remain distinct checks.

## Reproduction

```powershell
python tools/beryl-bench/test_run.py
python tools/beryl-bench/run.py collect --workload checked_lcg --beryl build/beryl.exe --out build/bench-checked_lcg
```

The retired `scripts/bench.sh` exits 2 and prints the collector command.
