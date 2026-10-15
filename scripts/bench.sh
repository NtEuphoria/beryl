#!/usr/bin/env bash
# Retired. The historical overflowing LCG harness is not a measurement protocol.
# Use tools/beryl-bench/run.py (see docs/V0_2_PERFORMANCE_PLAN.md).
printf '%s\n' "scripts/bench.sh is retired. Use: python tools/beryl-bench/run.py collect --workload checked_lcg" >&2
exit 2
