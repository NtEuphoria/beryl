#!/usr/bin/env bash
# Measures the numbers docs/BENCHMARKS.md reports. Every figure there comes
# from this script, so a claim that drifts is a claim that gets caught.
set -uo pipefail
cd "$(dirname "$0")/.."

BERYL=build/beryl.exe
OUT=build/bench
mkdir -p "$OUT"

secs() { date +%s%N; }
ms_since() { echo $(( ( $(secs) - $1 ) / 1000000 )); }

echo "== compiler =="
printf 'beryl.exe                 %s bytes\n' "$(wc -c < $BERYL)"
# Averaged over 20 runs; a single one is mostly Windows process creation.
t0=$(secs)
for _ in $(seq 1 20); do "$BERYL" version >/dev/null; done
printf 'startup, incl. spawn      %s ms (mean of 20)\n' "$(( $(ms_since $t0) / 20 ))"

echo
echo "== binary size =="
printf 'module bench.hello\n\nfn main() {\n    println("hi")\n}\n' > "$OUT/hello.be"
"$BERYL" build --release -o "$OUT/hello.exe" "$OUT/hello.be" >/dev/null 2>&1
printf 'int main(void){return 0;}\n' > "$OUT/bare.c"
clang -O2 "$OUT/bare.c" -o "$OUT/bare.exe" 2>/dev/null
printf 'C runtime floor (bare C)   %s bytes\n' "$(wc -c < "$OUT/bare.exe")"
printf 'beryl hello (--release)    %s bytes\n' "$(wc -c < "$OUT/hello.exe")"
printf 'Beryl contribution         %s bytes\n' \
  "$(( $(wc -c < "$OUT/hello.exe") - $(wc -c < "$OUT/bare.exe") ))"

echo
echo "== front end throughput =="
# A generated program of many small functions, which is what a real codebase
# looks like to the front end.
gen() {
  local n=$1 f=$2
  {
    echo "module bench.big"
    echo
    echo "pub struct Acc {"
    echo "    total: i32 = 0"
    echo "}"
    echo
    for ((i = 0; i < n; i++)); do
      echo "pub fn step_$i(let a: i32, let b: i32) -> i32 {"
      echo "    var acc = a"
      echo "    if acc > b {"
      echo "        acc = acc - b"
      echo "    } else {"
      echo "        acc = acc + b"
      echo "    }"
      echo "    return acc * 2 + $i"
      echo "}"
      echo
    done
  } > "$f"
}

for n in 200 1000; do
  gen "$n" "$OUT/big_$n.be"
  lines=$(wc -l < "$OUT/big_$n.be")
  t0=$(secs); "$BERYL" check "$OUT/big_$n.be" >/dev/null 2>&1; el=$(ms_since $t0)
  printf 'check  %5s lines  %5s ms\n' "$lines" "$el"
done

t0=$(secs); "$BERYL" build --release -o "$OUT/big.exe" "$OUT/big_1000.be" >/dev/null 2>&1
printf 'build  %5s lines  %5s ms  (includes clang -O2)\n' \
  "$(wc -l < "$OUT/big_1000.be")" "$(ms_since $t0)"

echo
echo "== overflow-check overhead =="
# A data-dependent chain, so neither compiler can fold the loop away or
# vectorise it into something the other does not do. Best of three runs,
# because a single timing on Windows is dominated by scheduling noise.
best3() {
  local exe=$1 best=999999 t
  for _ in 1 2 3; do
    t0=$(secs); "$exe" >/dev/null 2>&1; t=$(ms_since $t0)
    [ "$t" -lt "$best" ] && best=$t
  done
  echo "$best"
}

cat > "$OUT/lcg.be" <<'BEEOF'
module bench.lcg

fn main() {
    var x = 12345
    for i in 0..80000000 {
        x = x * 1103515245 + 12345
        x = x & 2147483647
    }
    println(x)
}
BEEOF
cat > "$OUT/lcg.c" <<'CEOF'
#include <stdio.h>
int main(void) {
    int x = 12345;
    for (int i = 0; i < 80000000; i++) {
        x = x * 1103515245 + 12345;
        x = x & 2147483647;
    }
    printf("%d\n", x);
    return 0;
}
CEOF
# The same chain written with the explicit opt-outs, to show what they buy.
cat > "$OUT/lcgw.be" <<'BEEOF'
module bench.lcgw

fn main() {
    var x = 12345
    for i in 0..80000000 {
        x = wrapping_add(wrapping_mul(x, 1103515245), 12345)
        x = x & 2147483647
    }
    println(x)
}
BEEOF

"$BERYL" build --release -o "$OUT/lcg.exe" "$OUT/lcg.be" >/dev/null 2>&1
"$BERYL" build --release -o "$OUT/lcgw.exe" "$OUT/lcgw.be" >/dev/null 2>&1
clang -O2 -fwrapv "$OUT/lcg.c" -o "$OUT/lcg_c.exe" 2>/dev/null
bl=$(best3 "$OUT/lcg.exe")
bw=$(best3 "$OUT/lcgw.exe")
cl=$(best3 "$OUT/lcg_c.exe")
printf 'LCG chain  beryl checked     %5s ms\n' "$bl"
printf 'LCG chain  beryl wrapping_*  %5s ms\n' "$bw"
printf 'LCG chain  C     unchecked   %5s ms\n' "$cl"
if [ "$cl" -gt 0 ]; then
  printf 'overhead   checked           %5s %%\n' "$(( (bl - cl) * 100 / cl ))"
  printf 'overhead   wrapping_*        %5s %%\n' "$(( (bw - cl) * 100 / cl ))"
fi
echo
