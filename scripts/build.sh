#!/usr/bin/env bash
# Build the beryl compiler. Release by default; pass --debug for -O0 -g.
set -euo pipefail
cd "$(dirname "$0")/.."

mkdir -p build

MODE="${1:-release}"
if [ "$MODE" = "--debug" ] || [ "$MODE" = "debug" ]; then
  OPT="-O0 -g"
else
  OPT="-O2 -DNDEBUG"
fi

CFLAGS="-std=c11 -Wall -Wextra -Werror -Wno-unused-parameter $OPT -Isrc"

if [ ! -f src/driver/main.c ]; then
  echo "build: src/driver/main.c does not exist yet — nothing to link."
  echo "       (this is expected until Task 12; use scripts/test.sh meanwhile)"
  exit 0
fi

SRC=$(find src -name '*.c' | sort | tr '\n' ' ')

# shellcheck disable=SC2086
clang $CFLAGS -o build/beryl.exe $SRC

SIZE=$(wc -c < build/beryl.exe)
echo "built build/beryl.exe  (${SIZE} bytes)"
