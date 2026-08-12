#!/usr/bin/env bash
set -euo pipefail

hogkill="$1"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

proc="$tmp/proc"
cgroups="$tmp/cgroups"
bin="$tmp/bin"
mkdir -p "$proc/101" "$proc/102" "$bin"

cat >"$bin/ps" <<'EOF'
#!/usr/bin/env bash
printf '%s\n' \
  '101 fixture 12.0 1.0 1024 S /usr/bin/kitty --session live' \
  '102 fixture 4.0 0.5 2048 S /usr/bin/worker --session reused'
EOF
cat >"$bin/gum" <<'EOF'
#!/usr/bin/env bash
case "${1:-}" in
  choose) printf 'cancel\n' ;;
  *) exit 0 ;;
esac
EOF
chmod +x "$bin/ps" "$bin/gum"
sed -i "1c#!$(command -v bash)" "$bin/ps" "$bin/gum"

for pid in 101 102; do
  cat >"$proc/$pid/cgroup" <<EOF
0::/user.slice/user-1000.slice/user@1000.service/agent.slice/sinnix-agent-fixture.scope
EOF
  if [ "$pid" = 101 ]; then
    pss=8192
    anon=6144
    swap=128
    start=222
  else
    pss=4096
    anon=2048
    swap=64
    start=333
  fi
  printf 'Pss:                 %s kB\nPss_Anon:            %s kB\n' "$pss" "$anon" >"$proc/$pid/smaps_rollup"
  printf 'VmSwap:              %s kB\n' "$swap" >"$proc/$pid/status"
  printf 'x %.0s' {1..21} >"$proc/$pid/stat"
  printf '%s\n' "$start" >>"$proc/$pid/stat"
done

cgroup="$cgroups/user.slice/user-1000.slice/user@1000.service/agent.slice/sinnix-agent-fixture.scope"
mkdir -p "$cgroup"
printf '7340032\n' >"$cgroup/memory.current"
printf 'anon 4194304\nfile 3145728\n' >"$cgroup/memory.stat"
printf '65536\n' >"$cgroup/memory.swap.current"

db="$tmp/telemetry.sqlite"
export SINNIX_SCOPE_WRAPPER_ACTIVE=1
sqlite3 "$db" <<'EOF'
create table process_memory_sample (
  pid integer,
  process_start_time_ticks integer,
  pss_anon_kb integer,
  observed_at text
);
insert into process_memory_sample values (101, 111, 200, datetime('now','-1 hour'));
insert into process_memory_sample values (101, 111, 500, datetime('now'));
insert into process_memory_sample values (102, 333, 200, datetime('now','-1 hour'));
insert into process_memory_sample values (102, 333, 400, datetime('now'));
EOF

export PATH="$bin:$PATH"
export SINNIX_HOGKILL_PROC_ROOT="$proc"
export SINNIX_HOGKILL_CGROUP_ROOT="$cgroups"
export SINNIX_HOGKILL_TELEMETRY_DB="$db"

json="$tmp/output.json"
"$hogkill" --json --limit 2 >"$json"
jq -e '
  (.processes | length) == 2 and
  .processes[0].pid == 101 and
  .processes[0].pss_anon_bytes == 6291456 and
  .cgroups[0].current_bytes == 7340032 and
  .cgroups[0].anon_bytes == 4194304
' "$json" >/dev/null

trajectory="$tmp/trajectory.txt"
"$hogkill" --pid 102 --trajectory --dry-run >"$trajectory"
grep -F 'trajectory: stable, 200 KiB..400 KiB' "$trajectory" >/dev/null
if grep -F 'trajectory: stable, 200 KiB..500 KiB' "$trajectory" >/dev/null; then
  echo 'hogkill fixture: PID reuse was not rejected' >&2
  exit 1
fi

echo 'hogkill fixture passed'
