#!/usr/bin/env bash
set -euo pipefail

agent=""
workdir=""
prompt_file=""
log_file=""
json_file=""
last_file=""
model=""
reasoning_effort=""
schema_file=""
json_mode=0
skip_agents_render=0
ephemeral=0
claude_api_key_auth=0
credential_profile="subscription"
job_id=""
launch_id=""
job_state_dir="${SINNIX_AGENT_JOB_STATE_DIR:-${XDG_STATE_HOME:-$HOME/.local/state}/sinnix/agent-jobs}"
job_role=""
work_item=""
parent_job_id=""
coordinator_job_id=""
provider=""
account_hash=""
vendor_session_id=""
polylogue_session_id=""
kitty_socket=""
kitty_window_id=""
hyprland_address=""
quota_snapshot_id=""
memory_high=""
memory_max=""
cpu_weight=""
io_weight=""
timeout_seconds="14400"
internal_agent_scope=0
job_started_epoch="$(date +%s)"
actual_agent_pid=""
actual_agent_proc_start=""
codex_sandbox=""
codex_home=""
codex_skip_git_check=0
max_retries=3

usage() {
  cat <<'EOF'
Usage:
  run_agent_prompt.sh [options]

Required:
  --agent <claude|codex|gemini|grok|antigravity>
  --workdir <path>
  --prompt-file <path>
  --log-file <path>

Existing options:
  --json-file <path>
  --last-file <path>
  --model <name>
  --reasoning-effort <value>
  --schema-file <path>
  --json
  --skip-agents-render
  --ephemeral
  --claude-api-key-auth       Keep ANTHROPIC_API_KEY for Claude instead of subscription auth
  --credential-profile <subscription|api>

Codex-specific options (ignored by other backends):
  --sandbox <mode>            Passthrough to `codex exec -s <mode>` (e.g. read-only)
  --codex-home <path>         Override CODEX_HOME for this invocation only (e.g. a
                               scratch dir with no AGENTS.md, to run without global
                               environment-memory context)
  --skip-git-repo-check       Passthrough to `codex exec --skip-git-repo-check`

Resilience:
  --max-retries <n>           Retry the agent invocation up to n times (default 3)
                               if its log shows a transient launcher race
                               ("Text file busy" from the shared npm-bootstrap
                               launcher regenerating mid-exec under concurrent
                               fanout). 0 disables retry.

Attested job options:
  --job-id <stable-id>        Generated when omitted
  --launch-id <opaque-id>     Generated when omitted
  --job-state-dir <path>      Default: $XDG_STATE_HOME/sinnix/agent-jobs
  --job-role <description>
  --work-item <bead-or-label>
  --parent-job-id <stable-id>
  --coordinator-job-id <stable-id>
  --provider <provider>
  --account-hash <hash>
  --vendor-session-id <id>
  --polylogue-session-id <id>
  --kitty-socket <path>
  --kitty-window-id <id>
  --hyprland-address <address>
  --quota-snapshot-id <id>
  --memory-high <limit>
  --memory-max <limit>
  --cpu-weight <1-10000>
  --io-weight <1-10000>
  --timeout-seconds <seconds>  Enforced by systemd RuntimeMaxSec
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
  --agent)
    agent="${2:?missing value for --agent}"
    shift 2
    ;;
  --workdir)
    workdir="${2:?missing value for --workdir}"
    shift 2
    ;;
  --prompt-file)
    prompt_file="${2:?missing value for --prompt-file}"
    shift 2
    ;;
  --log-file)
    log_file="${2:?missing value for --log-file}"
    shift 2
    ;;
  --json-file)
    json_file="${2:?missing value for --json-file}"
    shift 2
    ;;
  --last-file)
    last_file="${2:?missing value for --last-file}"
    shift 2
    ;;
  --model)
    model="${2:?missing value for --model}"
    shift 2
    ;;
  --reasoning-effort)
    reasoning_effort="${2:?missing value for --reasoning-effort}"
    shift 2
    ;;
  --schema-file)
    schema_file="${2:?missing value for --schema-file}"
    shift 2
    ;;
  --job-id)
    job_id="${2:?missing value for --job-id}"
    shift 2
    ;;
  --launch-id)
    launch_id="${2:?missing value for --launch-id}"
    shift 2
    ;;
  --job-state-dir)
    job_state_dir="${2:?missing value for --job-state-dir}"
    shift 2
    ;;
  --job-role)
    job_role="${2:?missing value for --job-role}"
    shift 2
    ;;
  --work-item)
    work_item="${2:?missing value for --work-item}"
    shift 2
    ;;
  --parent-job-id)
    parent_job_id="${2:?missing value for --parent-job-id}"
    shift 2
    ;;
  --coordinator-job-id)
    coordinator_job_id="${2:?missing value for --coordinator-job-id}"
    shift 2
    ;;
  --provider)
    provider="${2:?missing value for --provider}"
    shift 2
    ;;
  --account-hash)
    account_hash="${2:?missing value for --account-hash}"
    shift 2
    ;;
  --vendor-session-id)
    vendor_session_id="${2:?missing value for --vendor-session-id}"
    shift 2
    ;;
  --polylogue-session-id)
    polylogue_session_id="${2:?missing value for --polylogue-session-id}"
    shift 2
    ;;
  --kitty-socket)
    kitty_socket="${2:?missing value for --kitty-socket}"
    shift 2
    ;;
  --kitty-window-id)
    kitty_window_id="${2:?missing value for --kitty-window-id}"
    shift 2
    ;;
  --hyprland-address)
    hyprland_address="${2:?missing value for --hyprland-address}"
    shift 2
    ;;
  --quota-snapshot-id)
    quota_snapshot_id="${2:?missing value for --quota-snapshot-id}"
    shift 2
    ;;
  --memory-high)
    memory_high="${2:?missing value for --memory-high}"
    shift 2
    ;;
  --memory-max)
    memory_max="${2:?missing value for --memory-max}"
    shift 2
    ;;
  --cpu-weight)
    cpu_weight="${2:?missing value for --cpu-weight}"
    shift 2
    ;;
  --io-weight)
    io_weight="${2:?missing value for --io-weight}"
    shift 2
    ;;
  --timeout-seconds)
    timeout_seconds="${2:?missing value for --timeout-seconds}"
    shift 2
    ;;
  --internal-agent-scope)
    internal_agent_scope=1
    shift
    ;;
  --json)
    json_mode=1
    shift
    ;;
  --skip-agents-render)
    skip_agents_render=1
    shift
    ;;
  --ephemeral)
    ephemeral=1
    shift
    ;;
  --claude-api-key-auth)
    claude_api_key_auth=1
    credential_profile="api"
    shift
    ;;
  --credential-profile)
    credential_profile="${2:?missing value for --credential-profile}"
    shift 2
    ;;
  --sandbox)
    codex_sandbox="${2:?missing value for --sandbox}"
    shift 2
    ;;
  --codex-home)
    codex_home="${2:?missing value for --codex-home}"
    shift 2
    ;;
  --skip-git-repo-check)
    codex_skip_git_check=1
    shift
    ;;
  --max-retries)
    max_retries="${2:?missing value for --max-retries}"
    shift 2
    ;;
  -h | --help)
    usage
    exit 0
    ;;
  *)
    echo "unknown option: $1" >&2
    usage >&2
    exit 2
    ;;
  esac
done

if [[ -z ${agent} || -z ${workdir} || -z ${prompt_file} || -z ${log_file} ]]; then
  usage >&2
  exit 2
fi
[[ -f ${prompt_file} ]] || {
  echo "missing prompt: ${prompt_file}" >&2
  exit 1
}
[[ -d ${workdir} ]] || {
  echo "missing workdir: ${workdir}" >&2
  exit 1
}
command -v jq >/dev/null 2>&1 || {
  echo "run_agent_prompt.sh requires jq" >&2
  exit 1
}
command -v sha256sum >/dev/null 2>&1 || {
  echo "run_agent_prompt.sh requires sha256sum" >&2
  exit 1
}

if [[ -z ${job_id} ]]; then
  job_id="$(cat /proc/sys/kernel/random/uuid)"
fi
if [[ -z ${launch_id} ]]; then
  launch_id="$(cat /proc/sys/kernel/random/uuid)"
fi
[[ ${job_id} =~ ^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$ ]] || {
  echo "invalid --job-id: ${job_id}" >&2
  exit 2
}
[[ ${launch_id} =~ ^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$ ]] || {
  echo "invalid --launch-id: ${launch_id}" >&2
  exit 2
}
[[ ${timeout_seconds} =~ ^[0-9]+$ && ${timeout_seconds} -ge 30 && ${timeout_seconds} -le 86400 ]] || {
  echo "invalid --timeout-seconds: ${timeout_seconds}" >&2
  exit 2
}
[[ ${credential_profile} == subscription || ${credential_profile} == api ]] || {
  echo "invalid --credential-profile" >&2
  exit 2
}
[[ ${max_retries} =~ ^[0-9]+$ && ${max_retries} -le 10 ]] || {
  echo "invalid --max-retries: ${max_retries}" >&2
  exit 2
}
[[ ${credential_profile} != api ]] || claude_api_key_auth=1

umask 077
mkdir -p -m 0700 "${job_state_dir}" "${job_state_dir}/.reservations" "$(dirname "${log_file}")"
chmod 0700 "${job_state_dir}"
chmod 0700 "${job_state_dir}/.reservations"
[[ -z ${json_file} ]] || mkdir -p "$(dirname "${json_file}")"
[[ -z ${last_file} ]] || mkdir -p "$(dirname "${last_file}")"

manifest="${job_state_dir}/${job_id}.json"
events="${job_state_dir}/${job_id}.events.jsonl"
reservation="${job_state_dir}/.reservations/${job_id}"
if [[ ${internal_agent_scope} -eq 0 ]]; then
  if ! mkdir -m 0700 "${reservation}" 2>/dev/null; then
    echo "refusing reserved job handle: ${job_id}" >&2
    exit 2
  fi
  printf '%s\n' "${launch_id}" >"${reservation}/launch-id"
  chmod 0600 "${reservation}/launch-id"
  if [[ -e ${manifest} ]]; then
    echo "refusing to overwrite existing job handle: ${job_id}" >&2
    exit 2
  fi
elif [[ ! -r ${reservation}/launch-id || $(<"${reservation}/launch-id") != "${launch_id}" ]]; then
  echo "refusing mismatched job reservation: ${job_id}" >&2
  exit 2
fi
worktree="$(cd "${workdir}" && pwd -P)"
git_common_dir="$(git -C "${worktree}" rev-parse --path-format=absolute --git-common-dir 2>/dev/null || true)"
if [[ -n ${git_common_dir} && $(basename "${git_common_dir}") == .git ]]; then
  repo_root="$(dirname "${git_common_dir}")"
else
  repo_root="$(git -C "${worktree}" rev-parse --show-toplevel 2>/dev/null || printf '%s' "${worktree}")"
fi
branch="$(git -C "${worktree}" symbolic-ref --quiet --short HEAD 2>/dev/null || printf '%s' "DETACHED")"
prompt_sha256="$(sha256sum "${prompt_file}" | awk '{print $1}')"
scope_unit="sinnix-agent-job-${job_id}.scope"
scope_cgroup="${SINNIX_AGENT_SCOPE_CGROUP:-}"
if [[ -z ${scope_cgroup} && -n ${SINNIX_AGENT_SCOPE_UNIT:-} ]]; then
  scope_cgroup="$(awk -F: -v unit="${SINNIX_AGENT_SCOPE_UNIT}" '$3 ~ ("/" unit "$|/" unit "/") { print $3; exit }' /proc/self/cgroup 2>/dev/null || true)"
fi

proc_start() {
  local stat
  stat="$(cat "/proc/$1/stat" 2>/dev/null || true)"
  printf '%s\n' "${stat##*) }" | awk '{print $20}'
}
event() {
  local lifecycle="$1" exit_status="${2:-}"
  jq -cn --arg at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" --arg job_id "$job_id" --arg lifecycle "$lifecycle" --arg scope "${SINNIX_AGENT_SCOPE_UNIT:-${scope_unit}}" --arg cgroup "$scope_cgroup" --arg status "$exit_status" \
    '{schema_version:2,at:$at,job_id:$job_id,event:(
      {accepted:"accepted",starting:"starting",running:"heartbeat",succeeded:"completion",failed:"failure",cancel_requested:"approval",cancelled:"completion",timed_out:"failure"}[$lifecycle] // "lifecycle"),lifecycle:$lifecycle,scope_unit:$scope,cgroup:$cgroup,exit_status:(if $status == "" then null else ($status|tonumber) end)}' >>"$events"
  chmod 0600 "$events"
  if [[ ${SINNIX_AGENT_JOURNAL:-1} == 1 ]] && command -v logger >/dev/null 2>&1; then
    printf 'SYSLOG_IDENTIFIER=sinnix-agent-job\nMESSAGE=agent job %s entered %s\nSINNIX_JOB_ID=%s\nSINNIX_JOB_LIFECYCLE=%s\nSINNIX_SCOPE_UNIT=%s\nSINNIX_CGROUP=%s\n' \
      "$job_id" "$lifecycle" "$job_id" "$lifecycle" "${SINNIX_AGENT_SCOPE_UNIT:-${scope_unit}}" "$scope_cgroup" |
      logger --journald 2>/dev/null || true
  fi
}

update_manifest() {
  local filter="$1"
  shift
  local tmp
  tmp="$(mktemp "${manifest}.update.XXXXXX")"
  jq "$@" --arg at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${filter} | .updated_at=\$at" "${manifest}" >"${tmp}"
  chmod 0600 "${tmp}"
  mv -f "${tmp}" "${manifest}"
}

record_actual_agent() {
  local pid="$1" start
  start="$(proc_start "${pid}")"
  [[ -n ${start} ]] || return 0
  actual_agent_proc_start="${start}"
  update_manifest '.actual_agent={pid:$pid,proc_start:$start,attested_at:(now|todateiso8601)}' \
    --argjson pid "${pid}" --arg start "${start}"
}

run_and_attest() {
  local input_path
  input_path="$(mktemp "${job_state_dir}/${job_id}.stdin.XXXXXX")"
  cat >"${input_path}"
  "$@" <"${input_path}" &
  actual_agent_pid=$!
  record_actual_agent "${actual_agent_pid}"
  wait "${actual_agent_pid}"
  local result=$?
  rm -f "${input_path}"
  return "${result}"
}

record_completion() {
  local status="$1" cgroup_root="/sys/fs/cgroup${scope_cgroup}" memory_peak="" cpu_usec="" io_bytes="" duration
  duration=$(($(date +%s) - job_started_epoch))
  [[ -r ${cgroup_root}/memory.peak ]] && memory_peak="$(<"${cgroup_root}/memory.peak")"
  [[ -r ${cgroup_root}/cpu.stat ]] && cpu_usec="$(awk '$1 == "usage_usec" {print $2}' "${cgroup_root}/cpu.stat")"
  [[ -r ${cgroup_root}/io.stat ]] && io_bytes="$(awk '{for (i=1; i<=NF; i++) if ($i ~ /^rbytes=|^wbytes=/) {split($i,a,"="); sum+=a[2]}} END {print sum+0}' "${cgroup_root}/io.stat")"
  update_manifest '.completion={duration_seconds:($duration|tonumber),peak_memory_bytes:(if $memory_peak=="" then null else ($memory_peak|tonumber) end),cpu_usage_usec:(if $cpu_usec=="" then null else ($cpu_usec|tonumber) end),io_bytes:(if $io_bytes=="" then null else ($io_bytes|tonumber) end),artifacts:.artifacts,verification:{exit_status:($status|tonumber),outcome:(if ($status|tonumber)==0 then "passed" else "failed" end)}}' \
    --arg status "${status}" --arg duration "${duration}" --arg memory_peak "${memory_peak}" --arg cpu_usec "${cpu_usec}" --arg io_bytes "${io_bytes}"
}

write_manifest() {
  local lifecycle="$1"
  local exit_status="${2:-}"
  local launcher_pid="$BASHPID"
  local updated_at
  updated_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  local created_at="$updated_at"
  if [[ -f ${manifest} ]]; then
    created_at="$(jq -r '.created_at // empty' "${manifest}")"
    [[ -n ${created_at} ]] || created_at="$updated_at"
  fi
  local tmp
  tmp="$(mktemp "${manifest}.tmp.XXXXXX")"
  jq -n \
    --arg job_id "${job_id}" \
    --arg launch_id "${launch_id}" \
    --arg created_at "${created_at}" \
    --arg updated_at "${updated_at}" \
    --arg lifecycle "${lifecycle}" \
    --arg backend "${agent}" \
    --arg model "${model}" \
    --arg effort "${reasoning_effort}" \
    --arg repo "${repo_root}" \
    --arg worktree "${worktree}" \
    --arg branch "${branch}" \
    --arg prompt_path "${prompt_file}" \
    --arg prompt_sha256 "${prompt_sha256}" \
    --arg log_path "${log_file}" \
    --arg json_path "${json_file}" \
    --arg final_path "${last_file}" \
    --arg role "${job_role}" \
    --arg work_item "${work_item}" \
    --arg parent_job_id "${parent_job_id}" \
    --arg coordinator_job_id "${coordinator_job_id}" \
    --arg provider "${provider}" \
    --arg account_hash "${account_hash}" \
    --arg vendor_session_id "${vendor_session_id}" \
    --arg polylogue_session_id "${polylogue_session_id}" \
    --arg kitty_socket "${kitty_socket}" \
    --arg kitty_window_id "${kitty_window_id}" \
    --arg hyprland_address "${hyprland_address}" \
    --arg quota_snapshot_id "${quota_snapshot_id}" \
    --arg scope_unit "${SINNIX_AGENT_SCOPE_UNIT:-${scope_unit}}" \
    --arg scope_cgroup "${scope_cgroup}" \
    --arg launcher_pid "${launcher_pid}" \
    --arg launcher_start "$(proc_start "${launcher_pid}")" \
    --arg exit_status "${exit_status}" \
    --arg memory_high "${memory_high}" \
    --arg memory_max "${memory_max}" \
    --arg cpu_weight "${cpu_weight}" \
    --arg io_weight "${io_weight}" \
    --arg timeout_seconds "${timeout_seconds}" \
    '{schema_version: 3, job_id: $job_id, launch_id: $launch_id, created_at: $created_at, updated_at: $updated_at,
      lifecycle: $lifecycle, backend: $backend, model: $model, effort: $effort,
      repo: $repo, worktree: $worktree, branch: $branch,
      prompt: {path: $prompt_path, sha256: $prompt_sha256},
      artifacts: {log: $log_path, json: $json_path, final: $final_path},
      declared: {role: $role, work_item: $work_item},
      delegation: {parent_job_id: (if $parent_job_id == "" then null else $parent_job_id end), coordinator_job_id: (if $coordinator_job_id == "" then null else $coordinator_job_id end)},
      identity: {role: $role, bead_id: (if $work_item == "" then null else $work_item end), provider: (if $provider == "" then null else $provider end), account_hash: (if $account_hash == "" then null else $account_hash end)},
      correlation: {vendor_session_id: (if $vendor_session_id == "" then null else $vendor_session_id end), polylogue_session_id: (if $polylogue_session_id == "" then null else $polylogue_session_id end), kitty_socket: (if $kitty_socket == "" then null else $kitty_socket end), kitty_window_id: (if $kitty_window_id == "" then null else $kitty_window_id end), hyprland_address: (if $hyprland_address == "" then null else $hyprland_address end), quota_snapshot_id: (if $quota_snapshot_id == "" then null else $quota_snapshot_id end)},
      launcher: {pid: ($launcher_pid | tonumber), proc_start: $launcher_start, scope_unit: $scope_unit, cgroup: $scope_cgroup},
      resource_overrides: {MemoryHigh: $memory_high, MemoryMax: $memory_max, CPUWeight: $cpu_weight, IOWeight: $io_weight, RuntimeMaxSec: $timeout_seconds},
      exit_status: (if $exit_status == "" then null else ($exit_status | tonumber) end)}' >"${tmp}"
  chmod 0600 "${tmp}"
  mv -f "${tmp}" "${manifest}"
  event "$lifecycle" "$exit_status"
}

if [[ ${internal_agent_scope} -eq 0 && -z ${SINNIX_AGENT_SCOPED:-} ]]; then
  write_manifest accepted
  write_manifest starting
  scope_exec="${SINNIX_AGENT_SCOPE_EXEC:-$(command -v sinnix-agent-scope-exec 2>/dev/null || true)}"
  [[ -n ${scope_exec} && -x ${scope_exec} ]] || {
    write_manifest failed 125
    echo "run_agent_prompt.sh requires sinnix-agent-scope-exec for attested jobs" >&2
    exit 1
  }
  scope_args=(--unit "${scope_unit}")
  [[ -z ${memory_high} ]] || scope_args+=(--property "MemoryHigh=${memory_high}")
  [[ -z ${memory_max} ]] || scope_args+=(--property "MemoryMax=${memory_max}")
  [[ -z ${cpu_weight} ]] || scope_args+=(--property "CPUWeight=${cpu_weight}")
  [[ -z ${io_weight} ]] || scope_args+=(--property "IOWeight=${io_weight}")
  scope_args+=(--property "RuntimeMaxSec=${timeout_seconds}")
  inner_args=(
    "$0" --internal-agent-scope --job-id "${job_id}" --launch-id "${launch_id}" --job-state-dir "${job_state_dir}"
    --agent "${agent}" --workdir "${workdir}" --prompt-file "${prompt_file}" --log-file "${log_file}"
    --timeout-seconds "${timeout_seconds}"
  )
  [[ -z ${model} ]] || inner_args+=(--model "${model}")
  [[ -z ${reasoning_effort} ]] || inner_args+=(--reasoning-effort "${reasoning_effort}")
  [[ -z ${job_role} ]] || inner_args+=(--job-role "${job_role}")
  [[ -z ${work_item} ]] || inner_args+=(--work-item "${work_item}")
  [[ -z ${parent_job_id} ]] || inner_args+=(--parent-job-id "${parent_job_id}")
  [[ -z ${coordinator_job_id} ]] || inner_args+=(--coordinator-job-id "${coordinator_job_id}")
  [[ -z ${provider} ]] || inner_args+=(--provider "${provider}")
  [[ -z ${account_hash} ]] || inner_args+=(--account-hash "${account_hash}")
  [[ -z ${vendor_session_id} ]] || inner_args+=(--vendor-session-id "${vendor_session_id}")
  [[ -z ${polylogue_session_id} ]] || inner_args+=(--polylogue-session-id "${polylogue_session_id}")
  [[ -z ${kitty_socket} ]] || inner_args+=(--kitty-socket "${kitty_socket}")
  [[ -z ${kitty_window_id} ]] || inner_args+=(--kitty-window-id "${kitty_window_id}")
  [[ -z ${hyprland_address} ]] || inner_args+=(--hyprland-address "${hyprland_address}")
  [[ -z ${quota_snapshot_id} ]] || inner_args+=(--quota-snapshot-id "${quota_snapshot_id}")
  [[ -z ${memory_high} ]] || inner_args+=(--memory-high "${memory_high}")
  [[ -z ${memory_max} ]] || inner_args+=(--memory-max "${memory_max}")
  [[ -z ${cpu_weight} ]] || inner_args+=(--cpu-weight "${cpu_weight}")
  [[ -z ${io_weight} ]] || inner_args+=(--io-weight "${io_weight}")
  [[ -z ${json_file} ]] || inner_args+=(--json-file "${json_file}")
  [[ -z ${last_file} ]] || inner_args+=(--last-file "${last_file}")
  [[ -z ${schema_file} ]] || inner_args+=(--schema-file "${schema_file}")
  [[ -z ${codex_sandbox} ]] || inner_args+=(--sandbox "${codex_sandbox}")
  [[ -z ${codex_home} ]] || inner_args+=(--codex-home "${codex_home}")
  [[ ${codex_skip_git_check} -eq 0 ]] || inner_args+=(--skip-git-repo-check)
  inner_args+=(--max-retries "${max_retries}")
  [[ ${json_mode} -eq 0 ]] || inner_args+=(--json)
  [[ ${skip_agents_render} -eq 0 ]] || inner_args+=(--skip-agents-render)
  [[ ${ephemeral} -eq 0 ]] || inner_args+=(--ephemeral)
  [[ ${claude_api_key_auth} -eq 0 ]] || inner_args+=(--claude-api-key-auth)
  inner_args+=(--credential-profile "${credential_profile}")
  set +e
  "${scope_exec}" "${scope_args[@]}" -- "${inner_args[@]}"
  scope_status=$?
  set -e
  lifecycle="$(jq -r '.lifecycle // empty' "${manifest}")"
  if [[ ${lifecycle} == accepted || ${lifecycle} == starting || ${lifecycle} == running ]]; then
    write_manifest failed "${scope_status}"
  fi
  exit "${scope_status}"
fi

if [[ -n ${SINNIX_AGENT_SCOPED:-} && ${internal_agent_scope} -eq 0 && (-n ${memory_high} || -n ${memory_max} || -n ${cpu_weight} || -n ${io_weight}) ]]; then
  echo "resource overrides require this runner to create the agent scope" >&2
  exit 2
fi

if [[ ${internal_agent_scope} -eq 1 && (${SINNIX_AGENT_SCOPED:-} != 1 || ${SINNIX_AGENT_SCOPE_UNIT:-} != "${scope_unit}" || -z ${scope_cgroup}) ]]; then
  write_manifest failed 125
  echo "run_agent_prompt.sh: agent scope launch did not attest the expected job cgroup" >&2
  exit 125
fi

write_manifest running
job_finalized=0
# Invoked indirectly by the EXIT trap below.
# shellcheck disable=SC2329
finalize_job() {
  local status=$?
  if [[ ${job_finalized} -eq 0 ]]; then
    if [[ ${status} -eq 0 ]]; then
      write_manifest succeeded 0
    elif [[ $(jq -r '.lifecycle // empty' "${manifest}") == cancel_requested ]]; then
      write_manifest cancelled "${status}"
    elif [[ ${status} -eq 124 || ${status} -eq 137 || ${status} -eq 143 ]]; then
      write_manifest timed_out "${status}"
    else
      write_manifest failed "${status}"
    fi
  fi
}
trap finalize_job EXIT
cd "${workdir}"

resolve_agent_bin() {
  case "$1" in
  claude) command -v claude-full 2>/dev/null || command -v claude 2>/dev/null ;;
  codex | gemini) command -v "$1" ;;
  grok) command -v grok-sinnix 2>/dev/null || command -v grok 2>/dev/null ;;
  antigravity) command -v agy-sinnix 2>/dev/null || command -v agy 2>/dev/null ;;
  *) return 1 ;;
  esac
}
agent_bin="$(resolve_agent_bin "${agent}")" || {
  echo "${agent} runtime not found" >&2
  exit 1
}

run_with_optional_env() {
  local -a env_args=(env -i)
  for key in HOME LANG LC_ALL PATH SHELL TERM USER XDG_CONFIG_HOME XDG_DATA_HOME XDG_RUNTIME_DIR XDG_STATE_HOME DBUS_SESSION_BUS_ADDRESS DISPLAY WAYLAND_DISPLAY SSH_AUTH_SOCK SINNIX_AGENT_JOB_STATE_DIR SINNIX_AGENT_SCOPED SINNIX_AGENT_SCOPE_UNIT SINNIX_AGENT_SCOPE_CGROUP SINNIX_CORRELATION_ID; do
    [[ -z ${!key+x} ]] || env_args+=("$key=${!key}")
  done
  [[ ${agent} != claude || ${claude_api_key_auth} -eq 1 || -z ${ANTHROPIC_API_KEY+x} ]] || :
  if [[ ${agent} == claude && ${claude_api_key_auth} -eq 1 && -n ${ANTHROPIC_API_KEY+x} ]]; then env_args+=("ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY"); fi
  [[ ${skip_agents_render} -eq 0 ]] || env_args+=(SINNIX_SKIP_AGENTS_RENDER=1)
  [[ ${agent} != codex || -z ${codex_home} ]] || env_args+=("CODEX_HOME=${codex_home}")
  "${env_args[@]}" "$@"
}

# Detects the transient sinnix-agent-npm-bootstrap launcher race: every
# wrapped-CLI invocation regenerates ~/.local/state/<tool>/launch.sh
# in-place and then execve()s it; a sibling process's execve() during that
# window returns ETXTBSY ("Text file busy"), independent of the model/task
# itself. Fixed at the source (atomic rename) in
# scripts/sinnix-agent-npm-bootstrap, but this retry is kept as defense in
# depth for hosts that haven't rebuilt yet and for any other transient
# collision in the launcher chain. Never retries a genuine task failure.
looks_like_launcher_race() {
  local target="$1"
  [[ -s ${target} ]] && grep -Fq 'Text file busy' "${target}"
}

set +e
retry_attempt=0
while true; do
  case "${agent}" in
  codex)
    [[ -n ${model} && -n ${last_file} ]] || {
      echo "codex requires --model and --last-file" >&2
      exit 2
    }
    cmd=("${agent_bin}" exec -C "${workdir}" --model "${model}" --output-last-message "${last_file}")
    [[ -z ${reasoning_effort} ]] || cmd+=(-c "model_reasoning_effort=\"${reasoning_effort}\"")
    [[ -z ${schema_file} ]] || cmd+=(--output-schema "${schema_file}")
    [[ -z ${codex_sandbox} ]] || cmd+=(-s "${codex_sandbox}")
    [[ ${codex_skip_git_check} -eq 0 ]] || cmd+=(--skip-git-repo-check)
    [[ ${ephemeral} -eq 0 ]] || cmd+=(--ephemeral)
    [[ ${json_mode} -eq 0 ]] || cmd+=(--json)
    cmd+=(-)
    if [[ ${json_mode} -eq 1 ]]; then run_and_attest run_with_optional_env "${cmd[@]}" <"${prompt_file}" >"${json_file}" 2>"${log_file}"; else run_and_attest run_with_optional_env "${cmd[@]}" <"${prompt_file}" >"${log_file}" 2>&1; fi
    ;;
  claude)
    prompt_text="$(<"${prompt_file}")"
    cmd=("${agent_bin}" --print -p "${prompt_text}")
    [[ -z ${model} ]] || cmd+=(--model "${model}")
    [[ -z ${reasoning_effort} ]] || cmd+=(--effort "${reasoning_effort}")
    if [[ -n ${schema_file} ]]; then
      [[ -f ${schema_file} ]] || {
        echo "missing schema: ${schema_file}" >&2
        exit 1
      }
      cmd+=(--json-schema "$(<"${schema_file}")")
    fi
    if [[ ${json_mode} -eq 1 ]]; then
      cmd+=(--output-format json)
      run_and_attest run_with_optional_env "${cmd[@]}" >"${json_file}" 2>"${log_file}"
      [[ -z ${last_file} ]] || jq -r '.result // empty' "${json_file}" >"${last_file}"
    else
      run_and_attest run_with_optional_env "${cmd[@]}" >"${log_file}" 2>&1
      [[ -z ${last_file} ]] || cp "${log_file}" "${last_file}"
    fi
    ;;
  gemini)
    if [[ ${json_mode} -eq 1 ]]; then run_and_attest run_with_optional_env "${agent_bin}" <"${prompt_file}" >"${json_file}" 2>"${log_file}"; else run_and_attest run_with_optional_env "${agent_bin}" <"${prompt_file}" >"${log_file}" 2>&1; fi
    ;;
  grok)
    prompt_text="$(<"${prompt_file}")"
    cmd=("${agent_bin}" --cwd "${workdir}" --single "${prompt_text}")
    [[ -z ${model} ]] || cmd+=(--model "${model}")
    [[ -z ${reasoning_effort} ]] || cmd+=(--reasoning-effort "${reasoning_effort}")
    if [[ -n ${schema_file} ]]; then
      [[ -f ${schema_file} ]] || {
        echo "missing schema: ${schema_file}" >&2
        exit 1
      }
      cmd+=(--json-schema "$(<"${schema_file}")")
    elif [[ ${json_mode} -eq 1 ]]; then
      cmd+=(--output-format json)
    fi
    if [[ ${json_mode} -eq 1 || -n ${schema_file} ]]; then
      [[ -n ${json_file} ]] || {
        echo "grok JSON output requires --json-file" >&2
        exit 2
      }
      run_and_attest run_with_optional_env "${cmd[@]}" >"${json_file}" 2>"${log_file}"
      [[ -z ${last_file} ]] || cp "${json_file}" "${last_file}"
    else
      run_and_attest run_with_optional_env "${cmd[@]}" >"${log_file}" 2>&1
      [[ -z ${last_file} ]] || cp "${log_file}" "${last_file}"
    fi
    ;;
  antigravity)
    prompt_text="$(<"${prompt_file}")"
    cmd=("${agent_bin}")
    [[ -z ${model} ]] || cmd+=(--model "${model}")
    [[ -z ${reasoning_effort} ]] || cmd+=(--effort "${reasoning_effort}")
    if [[ -n ${schema_file} ]]; then
      [[ -f ${schema_file} ]] || {
        echo "missing schema: ${schema_file}" >&2
        exit 1
      }
      cmd+=(--json-schema "${schema_file}")
    elif [[ ${json_mode} -eq 1 ]]; then
      cmd+=(--output-format json)
    fi
    cmd+=(--print "${prompt_text}")
    if [[ ${json_mode} -eq 1 || -n ${schema_file} ]]; then
      [[ -n ${json_file} ]] || {
        echo "Antigravity JSON output requires --json-file" >&2
        exit 2
      }
      run_and_attest run_with_optional_env "${cmd[@]}" >"${json_file}" 2>"${log_file}"
      [[ -z ${last_file} ]] || cp "${json_file}" "${last_file}"
    else
      run_and_attest run_with_optional_env "${cmd[@]}" >"${log_file}" 2>&1
      [[ -z ${last_file} ]] || cp "${log_file}" "${last_file}"
    fi
    ;;
  *)
    echo "unknown agent: ${agent}" >&2
    exit 2
    ;;
  esac
  status=$?
  if [[ ${status} -eq 0 || ${retry_attempt} -ge ${max_retries} ]]; then
    break
  fi
  race_detected=0
  looks_like_launcher_race "${log_file}" && race_detected=1
  if [[ ${race_detected} -eq 0 && -n ${json_file} ]]; then
    looks_like_launcher_race "${json_file}" && race_detected=1
  fi
  if [[ ${race_detected} -eq 0 ]]; then
    break
  fi
  retry_attempt=$((retry_attempt + 1))
  mv -f "${log_file}" "${log_file}.attempt${retry_attempt}" 2>/dev/null || true
  [[ -z ${json_file} ]] || mv -f "${json_file}" "${json_file}.attempt${retry_attempt}" 2>/dev/null || true
  echo "run_agent_prompt.sh: launcher race detected, retrying (attempt ${retry_attempt}/${max_retries})" >&2
  sleep "0.$(((RANDOM % 900) + 100))" 2>/dev/null || sleep 1
done
set -e

if [[ ${status} -eq 0 ]]; then write_manifest succeeded 0; else write_manifest failed "${status}"; fi
if [[ -n ${actual_agent_pid} && -n ${actual_agent_proc_start} ]]; then
  update_manifest '.actual_agent={pid:$pid,proc_start:$start,attested_at:(now|todateiso8601)}' \
    --argjson pid "${actual_agent_pid}" --arg start "${actual_agent_proc_start}"
fi
record_completion "${status}"
job_finalized=1
trap - EXIT
exit "${status}"
