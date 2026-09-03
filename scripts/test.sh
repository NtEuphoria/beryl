#!/usr/bin/env bash
# Build and run the compiler's own unit and golden tests.
set -uo pipefail
cd "$(dirname "$0")/.."

# shellcheck source=scripts/sac.sh
. scripts/sac.sh

mkdir -p build

SRC=()
while IFS= read -r f; do SRC+=("$f"); done < <(find src -name '*.c' ! -path 'src/driver/main.c' | sort)
while IFS= read -r f; do SRC+=("$f"); done < <(find tests -name '*.c' | sort)

sac_build_run build/run_tests.exe \
  clang -std=c11 -Wall -Wextra -Werror -Wno-unused-parameter -g -O0 -Isrc \
  -- "${SRC[@]}"
