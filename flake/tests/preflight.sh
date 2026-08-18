#!/usr/bin/env bash
# Provably fails when: a gate stops blocking the condition it exists for
# (verified by making the nix-storage gate always report healthy).
set -euo pipefail

preflight="$1"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
mkdir -p "$tmp/home/persisted" "$tmp/home/unpersisted" "$tmp/var" "$tmp/bin"
export PATH="$tmp/bin:$PATH"
truncate -s 101M "$tmp/home/persisted/keep.bin"
truncate -s 101M "$tmp/home/unpersisted/private.bin"
printf 'MemTotal:       1000000 kB\nMemAvailable:   1000 kB\n' >"$tmp/meminfo"
printf 'some avg10=1.00 avg60=2.00 avg300=3.00 total=4\n' >"$tmp/pressure"

set +e
output="$({
  SINNIX_PREFLIGHT_HOME_ROOT="$tmp/home" \
    SINNIX_PREFLIGHT_VARLIB_ROOT="$tmp/var" \
    SINNIX_PREFLIGHT_PERSISTED_PREFIXES="$tmp/home/persisted" \
    SINNIX_PREFLIGHT_MEMINFO="$tmp/meminfo" \
    SINNIX_PREFLIGHT_MEMORY_PRESSURE="$tmp/pressure" \
    SINNIX_PREFLIGHT_NVIDIA_MODULE_VERSION=570.1 \
    SINNIX_PREFLIGHT_NVIDIA_USERSPACE_VERSION=560.1 \
    SINNIX_PREFLIGHT_SNAPSHOT_FREE_KIB=100 \
    "$preflight" reboot
} 2>&1)"
status=$?
set -e
[ "$status" -eq 0 ]
grep -Fq 'BLOCK unpersisted-valuables: 1 large unpersisted files' <<<"$output"
grep -Fq 'largest=105906176 bytes' <<<"$output"
grep -Fq 'BLOCK nvidia-pairing: module=570.1, userspace=560.1' <<<"$output"
grep -Fq 'BLOCK snapshot-headroom: free=100 KiB' <<<"$output"
! grep -Fq 'private.bin' <<<"$output"

# switch mode blocks on a REAL condition and FORCE overrides it. This used to
# stub `pgrep` to exit 0 and assert that the resulting "concurrent switch"
# verdict blocked -- which tested the detection mechanism rather than the
# behaviour, and kept passing while that mechanism false-positived on any
# process whose command line merely mentioned "nh os switch". The nix-storage
# floor is a genuine blocker with a genuine threshold, so demand more free
# space than any machine has.
set +e
switch_output="$(SINNIX_PREFLIGHT_MIN_NIX_FREE_KB=999999999999 \
  SINNIX_PREFLIGHT_MEMINFO="$tmp/meminfo" "$preflight" switch 2>&1)"
status=$?
set -e
[ "$status" -eq 75 ]
grep -Fq 'BLOCK nix-storage' <<<"$switch_output"

SINNIX_PREFLIGHT_FORCE=1 SINNIX_PREFLIGHT_MIN_NIX_FREE_KB=999999999999 \
  SINNIX_PREFLIGHT_MEMINFO="$tmp/meminfo" "$preflight" switch >/dev/null
echo 'preflight fixture passed'
