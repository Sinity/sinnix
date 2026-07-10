#!/usr/bin/env bash
set -euo pipefail

state_dir="${SINNIX_AGENT_JOB_STATE_DIR:-${XDG_STATE_HOME:-$HOME/.local/state}/sinnix/agent-jobs}"
systemctl_bin="${SINNIX_AGENT_SYSTEMCTL:-systemctl}"
proc_root="${SINNIX_AGENT_PROC_ROOT:-/proc}"

usage() {
  cat <<'EOF'
Usage:
  agent_job_control.sh [--state-dir <path>] list
  agent_job_control.sh [--state-dir <path>] status --job <job-id>
  agent_job_control.sh [--state-dir <path>] interrupt --job <job-id>

Interrupt intentionally accepts only an attested job ID. PID, title, and
window selectors are not control identities and are rejected.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --state-dir) state_dir="${2:?agent_job_control.sh: --state-dir requires a value}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) break ;;
  esac
done

command="${1:-}"
[[ -n ${command} ]] || { usage >&2; exit 64; }
shift

job_id=""
case "${command}" in
  list)
    [[ $# -eq 0 ]] || { usage >&2; exit 64; }
    ;;
  status|interrupt)
    [[ ${1:-} == --job && $# -eq 2 ]] || { usage >&2; exit 64; }
    job_id="$2"
    [[ ${job_id} =~ ^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$ ]] || { echo "invalid job ID: ${job_id}" >&2; exit 64; }
    ;;
  *)
    echo "unknown command: ${command}" >&2
    usage >&2
    exit 64
    ;;
esac

manifest_for() {
  printf '%s/%s.json\n' "${state_dir}" "$1"
}

require_manifest() {
  manifest="$(manifest_for "${job_id}")"
  [[ -r ${manifest} ]] || { echo "unknown job ID: ${job_id}" >&2; exit 1; }
  jq -e --arg job_id "${job_id}" '
    .schema_version == 1 and .job_id == $job_id and
    (.launcher.pid | type == "number") and
    (.launcher.scope_unit | type == "string" and length > 0) and
    (.launcher.cgroup | type == "string" and length > 0) and
    (.worktree | type == "string" and length > 0)
  ' "${manifest}" >/dev/null || {
    echo "refusing malformed or unattested manifest: ${manifest}" >&2
    exit 1
  }
}

live_scope_json() {
  local unit="$1"
  local properties
  if properties="$(
    "${systemctl_bin}" --user show "${unit}" \
      --property=ActiveState --property=SubState --property=MainPID \
      --property=ControlGroup --property=MemoryHigh --property=MemoryMax \
      --property=CPUWeight --property=IOWeight 2>/dev/null
  )"; then
    jq -Rn --arg properties "${properties}" '
      ($properties | split("\n")
        | map(select(test("=")) | split("=") | {key: .[0], value: (.[1:] | join("="))})
        | from_entries) + {available: true}
    '
  else
    printf '{"available":false}\n'
  fi
}

job_status() {
  local source_manifest="$1"
  local unit
  unit="$(jq -r '.launcher.scope_unit' "${source_manifest}")"
  local live
  live="$(live_scope_json "${unit}")"
  jq --argjson live "${live}" '. + {live: $live}' "${source_manifest}"
}

case "${command}" in
  list)
    mkdir -p "${state_dir}"
    shopt -s nullglob
    manifests=("${state_dir}"/*.json)
    if [[ ${#manifests[@]} -eq 0 ]]; then
      printf '[]\n'
    else
      for source_manifest in "${manifests[@]}"; do
        job_status "${source_manifest}"
      done | jq -s 'sort_by(.created_at)'
    fi
    ;;
  status)
    require_manifest
    job_status "${manifest}"
    ;;
  interrupt)
    require_manifest
    pid="$(jq -r '.launcher.pid' "${manifest}")"
    unit="$(jq -r '.launcher.scope_unit' "${manifest}")"
    expected_unit="sinnix-agent-job-${job_id}.scope"
    recorded_cgroup="$(jq -r '.launcher.cgroup' "${manifest}")"
    worktree="$(jq -r '.worktree' "${manifest}")"
    lifecycle="$(jq -r '.lifecycle' "${manifest}")"
    [[ ${lifecycle} == starting || ${lifecycle} == running ]] || {
      echo "refusing to interrupt non-live job ${job_id} (${lifecycle})" >&2
      exit 1
    }
    [[ ${unit} == "${expected_unit}" ]] || {
      echo "refusing unexpected scope identity for job ${job_id}" >&2
      exit 1
    }
    kill -0 "${pid}" 2>/dev/null || { echo "refusing stale job PID: ${pid}" >&2; exit 1; }
    [[ -r ${proc_root}/${pid}/cgroup ]] || { echo "refusing unreadable cgroup for PID: ${pid}" >&2; exit 1; }
    grep -Fxq "0::${recorded_cgroup}" "${proc_root}/${pid}/cgroup" || {
      echo "refusing cgroup mismatch for job ${job_id}" >&2
      exit 1
    }
    [[ "$(readlink -f "${proc_root}/${pid}/cwd")" == "$(readlink -f "${worktree}")" ]] || {
      echo "refusing worktree mismatch for job ${job_id}" >&2
      exit 1
    }
    live="$(live_scope_json "${unit}")"
    [[ "$(jq -r '.available' <<<"${live}")" == true ]] || {
      echo "refusing unavailable systemd scope for job ${job_id}" >&2
      exit 1
    }
    [[ "$(jq -r '.ControlGroup // empty' <<<"${live}")" == "${recorded_cgroup}" ]] || {
      echo "refusing systemd cgroup mismatch for job ${job_id}" >&2
      exit 1
    }
    live_pid="$(jq -r '.MainPID // empty' <<<"${live}")"
    [[ -z ${live_pid} || ${live_pid} == 0 || ${live_pid} == "${pid}" ]] || {
      echo "refusing systemd PID mismatch for job ${job_id}" >&2
      exit 1
    }
    "${systemctl_bin}" --user stop "${unit}"
    ;;
esac
