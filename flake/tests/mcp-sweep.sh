#!/usr/bin/env bash
set -euo pipefail

sweep="$1"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
proc="$tmp/proc"
jobs="$tmp/jobs"
capture="$tmp/capture"
mkdir -p "$proc" "$jobs" "$capture"

make_process() {
  local pid="$1" ppid="$2" cgroup="$3" command="$4" pss="$5"
  mkdir -p "$proc/$pid"
  printf 'Name:\tfixture\nPPid:\t%s\nVmRSS:\t42 kB\n' "$ppid" >"$proc/$pid/status"
  printf '0::%s\n' "$cgroup" >"$proc/$pid/cgroup"
  printf '%s\0' "$command" >"$proc/$pid/cmdline"
  printf 'Pss_Anon:       %s kB\n' "$pss" >"$proc/$pid/smaps_rollup"
}

live_cgroup=/user.slice/user-1000.slice/user@1000.service/sinnix-agent-job-live.scope
detached_cgroup=/user.slice/user-1000.slice/user@1000.service/sinnix-agent-job-detached.scope
orphan_cgroup=/user.slice/user-1000.slice/user@1000.service/sinnix-agent-job-orphan.scope
make_process 101 10 "$live_cgroup" 'serena start-mcp-server' 100
make_process 102 1 "$detached_cgroup" 'mcp-polylogue' 200
make_process 103 1 "$orphan_cgroup" 'mcp-lynchpin' 300

cat >"$jobs/live.json" <<EOF
{"schema_version":3,"job_id":"live","lifecycle":"running","launcher":{"pid":10,"cgroup":"$live_cgroup"},"actual_agent":{"pid":11,"cgroup":"$live_cgroup"}}
EOF
cat >"$jobs/detached.json" <<EOF
{"schema_version":3,"job_id":"detached","lifecycle":"running","launcher":{"pid":12,"cgroup":"$detached_cgroup"},"actual_agent":{"pid":13,"cgroup":"$detached_cgroup"}}
EOF
cat >"$jobs/orphan.json" <<EOF
{"schema_version":3,"job_id":"orphan","lifecycle":"completed","launcher":{"pid":998,"cgroup":"$orphan_cgroup"},"actual_agent":{"pid":999,"cgroup":"$orphan_cgroup"}}
EOF

env \
  SINNIX_MCP_SWEEP_PROC_ROOT="$proc" \
  SINNIX_AGENT_JOB_STATE_DIR="$jobs" \
  SINNIX_MCP_SWEEP_CAPTURE_DIR="$capture" \
  "$sweep" --orphans-only --quiet

grep -Fq '"pid":101' "$capture/sweep.jsonl"
grep -Fq '"pid":102' "$capture/sweep.jsonl"
grep -Fq '"pid":103,"ppid":1,"rss_kib":42,"pss_anon_kib":300' "$capture/sweep.jsonl"
jq -e 'select(.pid == 101) | .action == "keep" and .reason == "attested-live-session"' "$capture/sweep.jsonl" >/dev/null
jq -e 'select(.pid == 102) | .action == "keep" and .reason == "attested-live-session"' "$capture/sweep.jsonl" >/dev/null
jq -e 'select(.pid == 103) | .action == "kill" and .reason == "orphaned"' "$capture/sweep.jsonl" >/dev/null
jq -e 'select(.event == "summary") | .before.count == 3 and .before.pss_anon_kib == 600 and .after.count == 3 and .after.pss_anon_kib == 600' "$capture/sweep.jsonl" >/dev/null

# A second safety run remains idempotent and continues to classify identity
# from manifests rather than parent PID.
env \
  SINNIX_MCP_SWEEP_PROC_ROOT="$proc" \
  SINNIX_AGENT_JOB_STATE_DIR="$jobs" \
  SINNIX_MCP_SWEEP_CAPTURE_DIR="$capture" \
  "$sweep" --orphans-only --quiet
jq -e 'select(.event == "summary") | .before.count == 3 and .before.pss_anon_kib == 600' "$capture/sweep.jsonl" >/dev/null
echo 'mcp sweep fixture passed'
