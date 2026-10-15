#!/usr/bin/env bash
# Every BE#### code emitted by the compiler must be documented.
set -euo pipefail
for required in dirname grep sort wc; do
  if ! command -v "$required" >/dev/null 2>&1; then
    printf 'diagnostic check: required utility unavailable: %s\n' "$required" >&2
    exit 2
  fi
done
cd "$(dirname "$0")/.."

codes=$(grep -rhoE '(diag_error|diag_warn|[^a-z_](err|fail))\([^,]+, *[0-9]{3,4}' src/ \
        | grep -oE '[0-9]{3,4}$' | sort -n -u)

missing=0
if [ -z "$codes" ]; then
  printf 'diagnostic check: no codes found; refusing an empty success\n' >&2
  exit 1
fi
for c in $codes; do
  padded=$(printf 'BE%04d' "$c")
  if ! grep -q "$padded" docs/DIAGNOSTICS.md 2>/dev/null; then
    echo "undocumented: $padded"
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
