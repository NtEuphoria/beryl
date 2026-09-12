#!/usr/bin/env bash
# Build and probe the exact candidate once. No security-control workarounds.
# compile_once_run <public-output> <compiler-and-flags...> -- <sources...>
# Caller may set the RUN_ARGS array, e.g. RUN_ARGS=(version).
compile_once_run() {
  local exe="$1"; shift
  local -a pre=() sources=()
  local split=0 arg rc job candidate
  for arg in "$@"; do
    if [ "$arg" = "--" ]; then split=1; continue; fi
    if [ "$split" -eq 0 ]; then pre+=("$arg"); else sources+=("$arg"); fi
  done
  [ "$split" -eq 1 ] && [ "${#sources[@]}" -gt 0 ] || return 2
  job=$(mktemp -d build/compile-XXXXXXXX) || return 2
  candidate="$job/program.exe"
  "${pre[@]}" -o "$candidate" "${sources[@]}" || return $?
  [ -s "$candidate" ] || return 2
  "$candidate" "${RUN_ARGS[@]}"
  rc=$?
  if [ "$rc" -ne 0 ]; then
    echo "compile: exact candidate failed to execute successfully (exit $rc); retained at $candidate" >&2
    return "$rc"
  fi
  # Lock prevents simultaneous shell publishers; candidate is retained for audit.
  mkdir "$exe.beryl-lock" || return 2
  cp "$candidate" "$exe.beryl-lock/publish.tmp" && mv -f "$exe.beryl-lock/publish.tmp" "$exe"
  rc=$?
  if [ "$rc" -eq 0 ]; then rmdir "$exe.beryl-lock" || return 2; fi
  return "$rc"
}
