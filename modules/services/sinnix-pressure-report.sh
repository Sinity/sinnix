#!/usr/bin/env bash
set -euo pipefail

WINDOW="${1:-2 min ago}"
DURATION="${2:-60 sec}"
export HOME="${HOME:-/var/log/below/home}"
export XDG_CACHE_HOME="${XDG_CACHE_HOME:-/var/log/below/cache}"
export XDG_STATE_HOME="${XDG_STATE_HOME:-/var/log/below/state}"

summarize_process_io() {
  below dump process \
    -b "$WINDOW" \
    --duration "$DURATION" \
    -f datetime pid comm state io.rwbytes_per_sec mem.rss_bytes cmdline \
    -O tsv \
    --raw \
    --disable-title 2>/dev/null \
    | awk -F '\t' '
        NF >= 7 && $5 != "?" {
          key = $2
          value = $5 + 0
          if (!(key in max) || value > max[key]) {
            max[key] = value
            line[key] = $1 "\t" $2 "\t" $3 "\t" $4 "\t" $6 "\t" substr($7, 1, 180)
          }
        }
        END {
          for (key in max) print max[key] "\t" line[key]
        }
      ' \
    | sort -nr \
    | awk -F '\t' '
        BEGIN { print "max_rw_Bps\tdatetime\tpid\tcomm\tstate\trss_B\tcmd" }
        NR <= 8 { print }
      '
}

summarize_cgroup_pressure() {
  below dump cgroup \
    -b "$WINDOW" \
    --duration "$DURATION" \
    -f datetime name pressure.io_full_pct pressure.memory_full_pct io.rwbytes_per_sec mem.total \
    -O tsv \
    --raw \
    --disable-title 2>/dev/null \
    | awk -F '\t' '
        NF >= 6 {
          key = $2
          io_full = ($3 == "" || $3 == "?" ? 0 : $3 + 0)
          rw = ($5 == "" || $5 == "?" ? 0 : $5 + 0)
          if (!(key in max_pressure) || io_full > max_pressure[key] || rw > max_rw[key]) {
            max_pressure[key] = io_full
            max_rw[key] = rw
            line[key] = $1 "\t" $2 "\t" $4 "\t" max_rw[key] "\t" $6
          }
        }
        END {
          for (key in max_pressure) print max_pressure[key] "\t" line[key]
        }
      ' \
    | sort -nr \
    | awk -F '\t' '
        BEGIN { print "max_io_full_pct\tdatetime\tcgroup\tmemory_full_pct\trw_Bps\tmem_B" }
        NR <= 8 { print }
      '
}

echo "=== pressure snapshot $(date --iso-8601=seconds) ==="
echo "--- /proc/pressure ---"
printf 'cpu '; cat /proc/pressure/cpu
printf 'memory '; cat /proc/pressure/memory
printf 'io '; cat /proc/pressure/io
echo

echo "--- memory ---"
free -h
echo

echo "--- blocked tasks ---"
ps -eo pid,ppid,stat,wchan:24,comm,cmd | awk '$3 ~ /D/ || NR == 1' | sed -n '1,40p'
echo

echo "--- below: top recent processes by I/O ---"
summarize_process_io || true
echo

echo "--- below: top recent cgroups by I/O pressure ---"
summarize_cgroup_pressure || true
