#!/usr/bin/env bash
set -euo pipefail

state_dir="${SINNIX_AGENT_JOB_STATE_DIR:-${XDG_STATE_HOME:-$HOME/.local/state}/sinnix/agent-jobs}"
systemctl_bin="${SINNIX_AGENT_SYSTEMCTL:-systemctl}"
proc_root="${SINNIX_AGENT_PROC_ROOT:-/proc}"
archive_dir="${state_dir}/legacy"

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
    .schema_version == 2 and .job_id == $job_id and
    (.launcher.pid | type == "number") and
    (.launcher.proc_start | type == "string" and length > 0) and
    (.launcher.scope_unit | type == "string" and length > 0) and
    (.launcher.cgroup | type == "string" and length > 0) and
    (.worktree | type == "string" and length > 0)
  ' "${manifest}" >/dev/null || {
    echo "refusing malformed or unattested manifest: ${manifest}" >&2
    exit 1
  }
}

proc_start() {
  local stat
  stat="$(cat "${proc_root}/$1/stat" 2>/dev/null || true)"
  printf '%s\n' "${stat##*) }" | awk '{print $20}'
}

migrate_or_archive_legacy() {
  mkdir -p -m 0700 "$archive_dir"
  for source in "$state_dir"/*.json; do
    [[ -e $source ]] || continue
    if jq -e '.schema_version == 1' "$source" >/dev/null 2>&1; then
      # PID-only records cannot be upgraded safely because start-time and
      # cgroup attestations were never recorded. Preserve evidence privately.
      mv "$source" "$archive_dir/$(basename "$source").legacy"
    fi
  done
}

live_scope_json() {
  local unit="$1"
  local properties
  if properties="$(
    "${systemctl_bin}" --user show "${unit}" \
      --property=ActiveState --property=SubState --property=MainPID \
      --property=ControlGroup --property=MemoryHigh --property=MemoryMax \
      --property=MemoryCurrent --property=MemoryPeak \
      --property=CPUWeight --property=IOWeight --property=RuntimeMaxUSec \
      --property=CPUUsageNSec --property=Result 2>/dev/null
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

reconcile_terminal_manifest() {
  local source_manifest="$1"
  local live="$2"
  local lifecycle active_state result terminal exit_status tmp
  lifecycle="$(jq -r '.lifecycle' "${source_manifest}")"
  [[ ${lifecycle} == running || ${lifecycle} == cancel_requested ]] || return 0
  active_state="$(jq -r '.ActiveState // empty' <<<"${live}")"
  [[ ${active_state} == inactive || ${active_state} == failed ]] || return 0
  result="$(jq -r '.Result // empty' <<<"${live}")"
  if [[ ${lifecycle} == cancel_requested ]]; then
    terminal=cancelled
    exit_status=143
  elif [[ ${result} == timeout ]]; then
    terminal=timed_out
    exit_status=124
  else
    terminal=failed
    exit_status=1
  fi
  tmp="$(mktemp "${source_manifest}.reconcile.XXXXXX")"
  jq --arg lifecycle "${terminal}" --arg at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    --argjson exit_status "${exit_status}" \
    '.lifecycle=$lifecycle | .updated_at=$at | .exit_status=$exit_status' \
    "${source_manifest}" >"${tmp}"
  chmod 0600 "${tmp}"
  mv -f "${tmp}" "${source_manifest}"
}

job_status() {
  local source_manifest="$1"
  local unit
  unit="$(jq -r '.launcher.scope_unit' "${source_manifest}")"
  local live
  live="$(live_scope_json "${unit}")"
  reconcile_terminal_manifest "${source_manifest}" "${live}"
  jq --argjson live "${live}" '. + {live: $live}' "${source_manifest}"
}

case "${command}" in
  list)
    umask 077
    mkdir -p -m 0700 "${state_dir}"
    chmod 0700 "${state_dir}"
    migrate_or_archive_legacy
    shopt -s nullglob
    manifests=("${state_dir}"/*.json)
    if [[ ${#manifests[@]} -eq 0 ]]; then
      printf '{"jobs":[],"malformed_records":[],"archived_legacy_records":[]}\n'
    else
      results=()
      malformed=()
      for source_manifest in "${manifests[@]}"; do
        if jq -e '.schema_version == 2 and (.job_id | type == "string")' "${source_manifest}" >/dev/null 2>&1; then
          results+=("$(job_status "${source_manifest}")")
        else
          malformed+=("$(basename "${source_manifest}")")
        fi
      done
      printf '%s\n' "${results[@]}" | jq -s --argjson malformed "$(printf '%s\n' "${malformed[@]}" | jq -Rsc 'split("\n") | map(select(length > 0))')" --argjson archived "$(find "$archive_dir" -maxdepth 1 -type f -name '*.legacy' -printf '%f\n' 2>/dev/null | jq -Rsc 'split("\n") | map(select(length > 0))')" \
        '{jobs: sort_by(.created_at), malformed_records: $malformed, archived_legacy_records: $archived}'
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
    if [[ ${lifecycle} == cancelled ]]; then
      printf '{"job_id":"%s","cancelled":true,"already_terminal":true}\n' "${job_id}"
      exit 0
    fi
    [[ ${lifecycle} == accepted || ${lifecycle} == starting || ${lifecycle} == running ]] || {
      echo "refusing to interrupt non-live job ${job_id} (${lifecycle})" >&2
      exit 1
    }
    [[ ${unit} == "${expected_unit}" ]] || {
      echo "refusing unexpected scope identity for job ${job_id}" >&2
      exit 1
    }
    kill -0 "${pid}" 2>/dev/null || { echo "refusing stale job PID: ${pid}" >&2; exit 1; }
    [[ "$(proc_start "${pid}")" == "$(jq -r '.launcher.proc_start' "${manifest}")" ]] || { echo "refusing PID start-time mismatch for job ${job_id}" >&2; exit 1; }
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
    tmp="$(mktemp "${manifest}.cancel.XXXXXX")"
    jq '.lifecycle = "cancel_requested" | .updated_at = (now | todateiso8601)' "${manifest}" >"${tmp}"
    chmod 0600 "$tmp"
    mv -f "$tmp" "${manifest}"
    "${systemctl_bin}" --user stop "${unit}"
    tmp="$(mktemp "${manifest}.tmp.XXXXXX")"
    jq --arg at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" '.lifecycle="cancelled" | .updated_at=$at | .exit_status=143' "${manifest}" >"${tmp}"
    chmod 0600 "${tmp}"
    mv -f "${tmp}" "${manifest}"
    printf '{"job_id":"%s","cancelled":true,"already_terminal":false}\n' "${job_id}"
    ;;
esac
