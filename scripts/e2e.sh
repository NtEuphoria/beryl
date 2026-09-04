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
    "$BERYL" run "$src" 2>/dev/null | strip_cr > build/e2e_actual.txt
    strip_cr < "$expected" > build/e2e_expected.txt
    if diff -q build/e2e_actual.txt build/e2e_expected.txt >/dev/null; then
      pass=$((pass + 1))
    else
      fail=$((fail + 1))
      failed_names+=("$name")
      echo "FAIL $name"
      diff build/e2e_actual.txt build/e2e_expected.txt | head -24 | sed 's/^/    /'
    fi

  elif [ -f "$trapfile" ]; then
    "$BERYL" run "$src" 2>&1 | strip_cr > build/e2e_actual.txt
    want=$(strip_cr < "$trapfile" | head -1)
    if grep -qF "$want" build/e2e_actual.txt; then
      pass=$((pass + 1))
    else
      fail=$((fail + 1))
      failed_names+=("$name")
      echo "FAIL $name (expected a trap containing: $want)"
      head -10 build/e2e_actual.txt | sed 's/^/    /'
    fi

  else
    echo "FAIL $name (no .expected or .trap file)"
    fail=$((fail + 1))
    failed_names+=("$name")
  fi
done

rm -f build/e2e_actual.txt build/e2e_expected.txt

echo
if [ "$fail" -eq 0 ]; then
  echo "ok  $pass e2e programs"
  exit 0
fi
echo "FAILED  $fail of $((pass + fail)) e2e programs: ${failed_names[*]}"
exit 1
