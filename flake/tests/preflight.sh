#!/usr/bin/env bash
set -euo pipefail

preflight="$1"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
mkdir -p "$tmp/home/persisted" "$tmp/home/unpersisted" "$tmp/var" "$tmp/bin"
cat > "$tmp/bin/sinnix-heavy-lease" <<'EOF'
#!/usr/bin/env bash
exit 1
EOF
sed -i "1c#!$(command -v bash)" "$tmp/bin/sinnix-heavy-lease"
chmod +x "$tmp/bin/sinnix-heavy-lease"
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

set +e
SINNIX_PREFLIGHT_MEMINFO="$tmp/meminfo" "$preflight" switch >/dev/null 2>&1
status=$?
set -e
[ "$status" -eq 75 ]
SINNIX_PREFLIGHT_FORCE=1 SINNIX_PREFLIGHT_MEMINFO="$tmp/meminfo" "$preflight" switch >/dev/null
echo 'preflight fixture passed'
