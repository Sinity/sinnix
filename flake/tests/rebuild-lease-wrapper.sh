#!/usr/bin/env bash
# Falsifies sinnix-dv8: a real rebuild verb (switch/boot/test-system/test-vm)
# built from flake/command-registry.nix's shared `rebuildLease` fragment must
# exit non-zero with an unambiguous "nothing was built or activated" message
# when the host-wide heavy lease is held by another job -- never silently
# succeed while doing nothing.
set -euo pipefail

wrapper="${1:?path to a compiled rebuildLease-wrapping script required}"
holder_lease_bin="${2:?path to a standalone sinnix-heavy-lease binary required}"

fixture="$(mktemp -d)"
trap 'rm -rf "$fixture"' EXIT
export SINNIX_HEAVY_LEASE_STATE_DIR="$fixture/state"

# Hold the lease from a separate process, exactly as a concurrent real
# rebuild/build job would.
"$holder_lease_bin" --state-dir "$fixture/state" --project sinnix --work-item holder -- sleep 5 &
holder=$!
for _ in {1..50}; do
  [[ -f "$fixture/state/owner.json" ]] && break
  sleep 0.02
done
[[ -f "$fixture/state/owner.json" ]]

set +e
output="$("$wrapper" 2>&1)"
status=$?
set -e

kill -TERM "$holder" 2>/dev/null || true
wait "$holder" 2>/dev/null || true

echo "$output"

[ "$status" -eq 75 ]
grep -Fq 'BLOCKED' <<<"$output"
grep -Fq 'nothing was built or activated' <<<"$output"
! grep -Fq 'SENTINEL' <<<"$output"

echo 'rebuild-lease-wrapper fixture passed'
