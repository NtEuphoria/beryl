# Native performance collector

Phase 0 of [the v0.2 performance plan](../../docs/V0_2_PERFORMANCE_PLAN.md).
Status as of 2026-10-08: bounded process capture is implemented and tested;
complete performance collection is **unavailable** because mandatory resource
observations are missing. See [the capture repair packet](../../docs/advanced/P9_NATIVE_CAPTURE_REPAIR.md).

The proposed collector builds a Beryl kernel and a C baseline and checks
complete stdout and exit status against a golden. The current `collect` command
returns `status=unavailable` before builds, timings or output directories. It
cannot emit complete evaluator-v1 resource evidence yet and claims no speedup.

```powershell
python tools/beryl-bench/test_run.py
python tools/beryl-bench/run.py list
```

The tests run small Python executable fixtures for silent hangs, concurrent
output, limits, exact bytes, nonzero exits, startup failure, cancellation and
owned process cleanup. Controlled reader scheduling exercises terminal overflow,
cancellation and deadline crossing. Synthetic evaluator receipts remain
explicitly untimed.

Capture defaults to 4 MiB per output stream and an explicit positive deadline.
Paid durations use the monotonic clock; actual UTC timestamps remain unchanged.
Only the exact owned tree is stopped. Compiler/tool/evaluator subprocess helpers
use the same capture path. Successful execution requires final capture and owned
cleanup to finish within the monotonic deadline.

Rust sources under `rust/` are the matched/idiomatic/tuned baselines. This
revision of `run.py` times the C diagnostic baseline only (`--against c`).

Missing resource observations are reported as unavailable. Allocation counts
are uninstrumented, peak working set is not retained storage, and binary file
size is not text-section size. No substitute values are written. A successful
Windows memory query reports direct-child peak working set only; the POSIX peak
query remains unavailable.

Reopening collection requires verified resource instrumentation and a reviewed
compile identity contract. The dormant build/reject-check path also needs to
forward the selected Clang consistently (including Beryl's native compiler),
record executable hashes and exact arguments, and avoid the reject-check's
current implicit `clang` lookup. Those paths are blocked by resource admission
and were not executed during the capture repair.

`scripts/bench.sh` is retired. Historical numbers in `docs/BENCHMARKS.md` remain
retracted.
