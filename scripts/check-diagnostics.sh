#!/usr/bin/env bash
# Every BE#### code emitted by the compiler must be documented.
set -uo pipefail
cd "$(dirname "$0")/.."

codes=$(grep -rhoE '(diag_error|diag_warn|[^a-z_](err|fail))\([^,]+, *[0-9]{3}' src/ \
        | grep -oE '[0-9]{3}$' | sort -n -u)

missing=0
for c in $codes; do
  if ! grep -q "BE0$c" docs/DIAGNOSTICS.md 2>/dev/null; then
    echo "undocumented: BE0$c"
    missing=$((missing + 1))
  fi
done

total=$(echo "$codes" | wc -w)
if [ "$missing" -eq 0 ]; then
  echo "ok  all $total diagnostic codes documented"
  exit 0
fi
echo "FAILED  $missing of $total codes undocumented"
exit 1
