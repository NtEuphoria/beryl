#!/usr/bin/env bash
# End-to-end tests: compile each program, run it, and compare what it produced.
#
#   <name>.be + <name>.expected  -> stdout must match exactly
#   <name>.be + <name>.trap      -> the program must abort, and its combined
#                                   output must contain the given text
#
# Line endings are normalised on both sides: Windows text-mode stdout turns
# every \n into \r\n, which is not something a test should care about.
set -uo pipefail
cd "$(dirname "$0")/.."

BERYL=build/beryl.exe
OUT=$(mktemp -d build/e2e-XXXXXXXX) || exit 1
if [ ! -x "$BERYL" ]; then
  echo "e2e: $BERYL is missing; run scripts/build.sh first" >&2
  exit 1
fi

strip_cr() { sed -e 's/\r$//'; }

pass=0
fail=0
failed_names=()

for src in tests/e2e/*.be; do
  name=$(basename "$src" .be)
  expected="tests/e2e/$name.expected"
  trapfile="tests/e2e/$name.trap"

  if [ -f "$expected" ]; then
    "$BERYL" run "$src" 2>"$OUT/$name.stderr" | strip_cr > "$OUT/$name.actual"
    rc=$?
    strip_cr < "$expected" > "$OUT/$name.expected"
    if [ "$rc" -eq 0 ] && diff -q "$OUT/$name.actual" "$OUT/$name.expected" >/dev/null; then
      pass=$((pass + 1))
    else
      fail=$((fail + 1))
      failed_names+=("$name")
      echo "FAIL $name"
      diff "$OUT/$name.actual" "$OUT/$name.expected" | head -24 | sed 's/^/    /'
    fi

  elif [ -f "$trapfile" ]; then
    "$BERYL" run "$src" 2>&1 | strip_cr > "$OUT/$name.actual"
    rc=$?
    want=$(strip_cr < "$trapfile" | head -1)
    if [ "$rc" -ne 0 ] && grep -qF "$want" "$OUT/$name.actual"; then
      pass=$((pass + 1))
    else
      fail=$((fail + 1))
      failed_names+=("$name")
      echo "FAIL $name (expected a trap containing: $want)"
      head -10 "$OUT/$name.actual" | sed 's/^/    /'
    fi

  else
    echo "FAIL $name (no .expected or .trap file)"
    fail=$((fail + 1))
    failed_names+=("$name")
  fi
done

echo "e2e logs retained at $OUT"

echo
if [ "$fail" -eq 0 ] && [ "$pass" -gt 0 ]; then
  echo "ok  $pass e2e programs"
  exit 0
fi
echo "FAILED  $fail of $((pass + fail)) e2e programs: ${failed_names[*]}"
exit 1
