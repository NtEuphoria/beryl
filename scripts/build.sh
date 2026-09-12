#!/usr/bin/env bash
# Build the beryl compiler. Release by default; pass --debug for -O0 -g.
set -uo pipefail
cd "$(dirname "$0")/.."

# shellcheck source=scripts/compile-once.sh
. scripts/compile-once.sh

mkdir -p build

# Keep the embedded runtime in step with runtime/*. The generated header is
# committed, so a build never actually requires Python.
if command -v python >/dev/null 2>&1; then
  python scripts/embed_runtime.py >/dev/null
fi

MODE="${1:-release}"
if [ "$MODE" = "--debug" ] || [ "$MODE" = "debug" ]; then
  OPT=(-O0 -g)
else
  OPT=(-O2 -DNDEBUG)
fi

if [ ! -f src/driver/main.c ]; then
  echo "build: src/driver/main.c does not exist yet — nothing to link."
  echo "       (expected until Task 12; use scripts/test.sh meanwhile)"
  exit 0
fi

SRC=()
while IFS= read -r f; do SRC+=("$f"); done < <(find src -name '*.c' | sort)

# Probe the exact candidate before publication.
RUN_ARGS=(version)
compile_once_run build/beryl.exe \
  clang -std=c11 -Wall -Wextra -Werror -Wno-unused-parameter "${OPT[@]}" -Isrc \
  -- "${SRC[@]}" >/dev/null
rc=$?
if [ $rc -ne 0 ]; then
  echo "build: compile failed" >&2
  exit $rc
fi

SIZE=$(wc -c < build/beryl.exe)
echo "built build/beryl.exe  (${SIZE} bytes)"
