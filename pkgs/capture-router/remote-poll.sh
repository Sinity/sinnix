#!/bin/sh
# Runs on sinnix-gw (busybox ash) via `ssh sinnix-gw sh -s -- <offset> <first-line>`,
# piped in from the local Nix store path -- never installed on the router.
#
# Always emits leases, per-AP wifi associations, and the current nlbwmon
# period. The syslog section is an incremental delta computed from the
# watermark passed in as $1/$2; see capture-router.nix for the rotation-safety
# design this implements. busybox logread rotates by renaming syslog ->
# syslog.old and starting a fresh syslog, i.e. copy-truncate, not append-only.
set -e

prev_offset="${1:-0}"
prev_first_line="${2:-}"

echo "===LEASES==="
cat /tmp/dhcp.leases 2>/dev/null || true

echo "===ASSOC==="
for ap in phy0-ap0 phy0-ap1 phy1-ap0 phy1-ap1; do
	printf '%s\t' "$ap"
	ubus -S call "hostapd.$ap" get_clients 2>/dev/null || echo '{}'
done

echo "===NLBW_PERIODS==="
nlbw -c list 2>/dev/null || true

echo "===NLBW_CURRENT==="
nlbw -c csv 2>/dev/null || true

echo "===SYSLOG==="
cur_first="$(head -n1 /overlay/log/syslog 2>/dev/null || true)"
cur_size="$(wc -c < /overlay/log/syslog 2>/dev/null || echo 0)"

if [ -z "$prev_first_line" ]; then
	# First-ever poll: backfill the whole of syslog.old once (the only time
	# it is read in full), then all of current syslog.
	if [ -f /overlay/log/syslog.old ]; then
		cat /overlay/log/syslog.old
	fi
	cat /overlay/log/syslog 2>/dev/null || true
	new_offset="$cur_size"
elif [ "$cur_first" = "$prev_first_line" ] && [ "$cur_size" -ge "$prev_offset" ]; then
	# Same file, grew normally: tail just the new bytes.
	if [ "$cur_size" -gt "$prev_offset" ]; then
		tail -c "+$((prev_offset + 1))" /overlay/log/syslog
	fi
	new_offset="$cur_size"
else
	# Rotated. The unread tail from before rotation is now at the end of
	# syslog.old (confirm identity via its first line before trusting the
	# offset into it), then take the whole fresh syslog.
	old_first="$(head -n1 /overlay/log/syslog.old 2>/dev/null || true)"
	old_size="$(wc -c < /overlay/log/syslog.old 2>/dev/null || echo 0)"
	if [ "$old_first" = "$prev_first_line" ] && [ "$old_size" -gt "$prev_offset" ]; then
		tail -c "+$((prev_offset + 1))" /overlay/log/syslog.old
	fi
	cat /overlay/log/syslog 2>/dev/null || true
	new_offset="$cur_size"
fi

echo "===END==="
>&2 echo "WATERMARK ${new_offset}|${cur_first}"
