#!/usr/bin/env bash
# Build and run the compiler's own unit and golden tests.
set -euo pipefail
cd "$(dirname "$0")/.."

mkdir -p build

CFLAGS="-std=c11 -Wall -Wextra -Werror -Wno-unused-parameter -g -O0 -Isrc"

# Every compiler source except the CLI entry point (which owns main()).
SRC=$(find src -name '*.c' ! -path 'src/driver/main.c' | sort | tr '\n' ' ')
TESTS=$(find tests -name '*.c' | sort | tr '\n' ' ')

# shellcheck disable=SC2086
clang $CFLAGS -o build/run_tests.exe $SRC $TESTS

./build/run_tests.exe
