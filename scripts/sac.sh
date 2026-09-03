#!/usr/bin/env bash
# Smart App Control workaround.
#
# This machine runs Smart App Control in Enforce mode
# (HKLM\SYSTEM\CurrentControlSet\Control\CI\Policy\VerifiedAndReputablePolicyState = 1).
# SAC performs a cloud reputation lookup per file hash, and for an unknown
# unsigned binary the verdict is NOT deterministic: building the identical
# source twice can yield one runnable binary and one blocked one. Measured
# directly — three identical builds gave RAN / BLOCKED / RAN.
#
# A block surfaces as exit code 126 with "Permission denied" from the shell,
# and as CodeIntegrity event 3077 in the Windows event log.
#
# The workaround is to rebuild with a different content hash and roll again.
# BERYL_BUILD_NONCE changes the binary, so each attempt gets an independent
# verdict. Six attempts makes a spurious failure vanishingly unlikely.

SAC_MAX_ATTEMPTS="${SAC_MAX_ATTEMPTS:-6}"

# sac_build_run <exe> <compile-command-prefix...> -- <sources...>
#
# Compiles with an added nonce and runs; retries on a SAC block. Returns the
# program's own exit code, or 126 if every attempt was blocked.
sac_build_run() {
  local exe="$1"; shift
  local -a pre=() srcs=()
  local seen_sep=0
  for arg in "$@"; do
    if [ "$arg" = "--" ]; then seen_sep=1; continue; fi
    if [ $seen_sep -eq 0 ]; then pre+=("$arg"); else srcs+=("$arg"); fi
  done

  local attempt out rc
  for attempt in $(seq 1 "$SAC_MAX_ATTEMPTS"); do
    if ! "${pre[@]}" -DBERYL_BUILD_NONCE="$attempt" -o "$exe" "${srcs[@]}"; then
      return 2   # a genuine compile error: do not retry
    fi

    set +e
    # SAC_PROBE_ARGS lets the caller pick arguments that exit 0.
    # shellcheck disable=SC2086
    out=$("$exe" ${SAC_PROBE_ARGS:-} 2>&1)
    rc=$?
    set -e

    if [ $rc -eq 126 ] || printf '%s' "$out" | grep -qi 'permission denied'; then
      if [ "$attempt" -lt "$SAC_MAX_ATTEMPTS" ]; then
        echo "note: Smart App Control blocked this binary; rebuilding (attempt $((attempt + 1))/$SAC_MAX_ATTEMPTS)" >&2
      fi
      continue
    fi

    printf '%s\n' "$out"
    return $rc
  done

  echo "error: Smart App Control blocked all $SAC_MAX_ATTEMPTS build attempts." >&2
  echo "       This is an environment limit, not a compile failure. See docs/BUILDING.md." >&2
  return 126
}

# sac_run <exe> — run an already-built binary, reporting a SAC block clearly.
sac_run() {
  local out rc
  set +e
  out=$("$1" "${@:2}" 2>&1)
  rc=$?
  set -e
  if [ $rc -eq 126 ] || printf '%s' "$out" | grep -qi 'permission denied'; then
    echo "error: Smart App Control blocked $1 (see docs/BUILDING.md)" >&2
    return 126
  fi
  printf '%s\n' "$out"
  return $rc
}
