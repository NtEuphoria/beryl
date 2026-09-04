#!/usr/bin/env bash
# Everything: compiler unit tests, then the end-to-end programs.
set -uo pipefail
cd "$(dirname "$0")/.."

echo "== unit =="
bash scripts/test.sh || exit 1

echo
echo "== build =="
bash scripts/build.sh || exit 1

echo
echo "== e2e =="
bash scripts/e2e.sh || exit 1

echo
echo "== stdlib and examples =="
for f in examples/*_test.be; do
  [ -f "$f" ] || continue
  printf '%-40s ' "$f"
  build/beryl.exe test "$f" || exit 1
done

echo
echo "== diagnostics documented =="
bash scripts/check-diagnostics.sh || exit 1

echo
echo "all green"
