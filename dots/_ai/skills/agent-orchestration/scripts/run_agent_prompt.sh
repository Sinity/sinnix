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
job_id=""
job_state_dir="${SINNIX_AGENT_JOB_STATE_DIR:-${XDG_STATE_HOME:-$HOME/.local/state}/sinnix/agent-jobs}"
job_role=""
work_item=""
memory_high=""
memory_max=""
cpu_weight=""
io_weight=""
internal_agent_scope=0

usage() {
  cat <<'EOF'
Usage:
  run_agent_prompt.sh [options]

Required:
  --agent <claude|codex|gemini>
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

Attested job options:
  --job-id <stable-id>        Generated when omitted
  --job-state-dir <path>      Default: $XDG_STATE_HOME/sinnix/agent-jobs
  --job-role <description>
  --work-item <bead-or-label>
  --memory-high <limit>
  --memory-max <limit>
  --cpu-weight <1-10000>
  --io-weight <1-10000>
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
  --agent) agent="${2:?missing value for --agent}"; shift 2 ;;
  --workdir) workdir="${2:?missing value for --workdir}"; shift 2 ;;
  --prompt-file) prompt_file="${2:?missing value for --prompt-file}"; shift 2 ;;
  --log-file) log_file="${2:?missing value for --log-file}"; shift 2 ;;
  --json-file) json_file="${2:?missing value for --json-file}"; shift 2 ;;
  --last-file) last_file="${2:?missing value for --last-file}"; shift 2 ;;
  --model) model="${2:?missing value for --model}"; shift 2 ;;
  --reasoning-effort) reasoning_effort="${2:?missing value for --reasoning-effort}"; shift 2 ;;
  --schema-file) schema_file="${2:?missing value for --schema-file}"; shift 2 ;;
  --job-id) job_id="${2:?missing value for --job-id}"; shift 2 ;;
  --job-state-dir) job_state_dir="${2:?missing value for --job-state-dir}"; shift 2 ;;
  --job-role) job_role="${2:?missing value for --job-role}"; shift 2 ;;
  --work-item) work_item="${2:?missing value for --work-item}"; shift 2 ;;
  --memory-high) memory_high="${2:?missing value for --memory-high}"; shift 2 ;;
  --memory-max) memory_max="${2:?missing value for --memory-max}"; shift 2 ;;
  --cpu-weight) cpu_weight="${2:?missing value for --cpu-weight}"; shift 2 ;;
  --io-weight) io_weight="${2:?missing value for --io-weight}"; shift 2 ;;
  --internal-agent-scope) internal_agent_scope=1; shift ;;
  --json) json_mode=1; shift ;;
  --skip-agents-render) skip_agents_render=1; shift ;;
  --ephemeral) ephemeral=1; shift ;;
  --claude-api-key-auth) claude_api_key_auth=1; shift ;;
  -h | --help) usage; exit 0 ;;
  *) echo "unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [[ -z ${agent} || -z ${workdir} || -z ${prompt_file} || -z ${log_file} ]]; then
  usage >&2
  exit 2
fi
[[ -f ${prompt_file} ]] || { echo "missing prompt: ${prompt_file}" >&2; exit 1; }
[[ -d ${workdir} ]] || { echo "missing workdir: ${workdir}" >&2; exit 1; }
command -v jq >/dev/null 2>&1 || { echo "run_agent_prompt.sh requires jq" >&2; exit 1; }
command -v sha256sum >/dev/null 2>&1 || { echo "run_agent_prompt.sh requires sha256sum" >&2; exit 1; }

if [[ -z ${job_id} ]]; then
  job_id="agent-$(date -u +%Y%m%dT%H%M%S)-$$-$RANDOM"
fi
[[ ${job_id} =~ ^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$ ]] || {
  echo "invalid --job-id: ${job_id}" >&2
  exit 2
}

mkdir -p "${job_state_dir}" "$(dirname "${log_file}")"
[[ -z ${json_file} ]] || mkdir -p "$(dirname "${json_file}")"
[[ -z ${last_file} ]] || mkdir -p "$(dirname "${last_file}")"

manifest="${job_state_dir}/${job_id}.json"
if [[ ${internal_agent_scope} -eq 0 && -e ${manifest} ]]; then
  echo "refusing to overwrite existing job handle: ${job_id}" >&2
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

write_manifest() {
  local lifecycle="$1"
  local exit_status="${2:-}"
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
    --arg scope_unit "${SINNIX_AGENT_SCOPE_UNIT:-${scope_unit}}" \
    --arg scope_cgroup "${scope_cgroup}" \
    --arg launcher_pid "${BASHPID}" \
    --arg exit_status "${exit_status}" \
    --arg memory_high "${memory_high}" \
    --arg memory_max "${memory_max}" \
    --arg cpu_weight "${cpu_weight}" \
    --arg io_weight "${io_weight}" \
    '{schema_version: 1, job_id: $job_id, created_at: $created_at, updated_at: $updated_at,
      lifecycle: $lifecycle, backend: $backend, model: $model, effort: $effort,
      repo: $repo, worktree: $worktree, branch: $branch,
      prompt: {path: $prompt_path, sha256: $prompt_sha256},
      artifacts: {log: $log_path, json: $json_path, final: $final_path},
      declared: {role: $role, work_item: $work_item},
      launcher: {pid: ($launcher_pid | tonumber), scope_unit: $scope_unit, cgroup: $scope_cgroup},
      resource_overrides: {MemoryHigh: $memory_high, MemoryMax: $memory_max, CPUWeight: $cpu_weight, IOWeight: $io_weight},
      exit_status: (if $exit_status == "" then null else ($exit_status | tonumber) end)}' >"${tmp}"
  mv -f "${tmp}" "${manifest}"
}

if [[ ${internal_agent_scope} -eq 0 && -z ${SINNIX_AGENT_SCOPED:-} ]]; then
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
  inner_args=(
    "$0" --internal-agent-scope --job-id "${job_id}" --job-state-dir "${job_state_dir}"
    --agent "${agent}" --workdir "${workdir}" --prompt-file "${prompt_file}" --log-file "${log_file}"
  )
  [[ -z ${model} ]] || inner_args+=(--model "${model}")
  [[ -z ${reasoning_effort} ]] || inner_args+=(--reasoning-effort "${reasoning_effort}")
  [[ -z ${job_role} ]] || inner_args+=(--job-role "${job_role}")
  [[ -z ${work_item} ]] || inner_args+=(--work-item "${work_item}")
  [[ -z ${memory_high} ]] || inner_args+=(--memory-high "${memory_high}")
  [[ -z ${memory_max} ]] || inner_args+=(--memory-max "${memory_max}")
  [[ -z ${cpu_weight} ]] || inner_args+=(--cpu-weight "${cpu_weight}")
  [[ -z ${io_weight} ]] || inner_args+=(--io-weight "${io_weight}")
  [[ -z ${json_file} ]] || inner_args+=(--json-file "${json_file}")
  [[ -z ${last_file} ]] || inner_args+=(--last-file "${last_file}")
  [[ -z ${schema_file} ]] || inner_args+=(--schema-file "${schema_file}")
  [[ ${json_mode} -eq 0 ]] || inner_args+=(--json)
  [[ ${skip_agents_render} -eq 0 ]] || inner_args+=(--skip-agents-render)
  [[ ${ephemeral} -eq 0 ]] || inner_args+=(--ephemeral)
  [[ ${claude_api_key_auth} -eq 0 ]] || inner_args+=(--claude-api-key-auth)
  set +e
  "${scope_exec}" "${scope_args[@]}" -- "${inner_args[@]}"
  scope_status=$?
  set -e
  lifecycle="$(jq -r '.lifecycle // empty' "${manifest}")"
  if [[ ${lifecycle} == starting || ${lifecycle} == running ]]; then
    write_manifest failed "${scope_status}"
  fi
  exit "${scope_status}"
fi

if [[ -n ${SINNIX_AGENT_SCOPED:-} && ${internal_agent_scope} -eq 0 && ( -n ${memory_high} || -n ${memory_max} || -n ${cpu_weight} || -n ${io_weight} ) ]]; then
  echo "resource overrides require this runner to create the agent scope" >&2
  exit 2
fi

if [[ ${internal_agent_scope} -eq 1 && ( ${SINNIX_AGENT_SCOPED:-} != 1 || ${SINNIX_AGENT_SCOPE_UNIT:-} != "${scope_unit}" || -z ${scope_cgroup} ) ]]; then
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
      write_manifest completed 0
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
    codex|gemini) command -v "$1" ;;
    *) return 1 ;;
  esac
}
agent_bin="$(resolve_agent_bin "${agent}")" || { echo "${agent} runtime not found (Claude accepts claude or claude-full)" >&2; exit 1; }

run_with_optional_env() {
  local -a env_args=(env)
  [[ ${agent} != claude || ${claude_api_key_auth} -eq 1 ]] || env_args+=(-u ANTHROPIC_API_KEY)
  [[ ${skip_agents_render} -eq 0 ]] || env_args+=(SINNIX_SKIP_AGENTS_RENDER=1)
  "${env_args[@]}" "$@"
}

set +e
case "${agent}" in
  codex)
    [[ -n ${model} && -n ${last_file} ]] || { echo "codex requires --model and --last-file" >&2; exit 2; }
    cmd=("${agent_bin}" exec -C "${workdir}" --model "${model}" --output-last-message "${last_file}")
    [[ -z ${reasoning_effort} ]] || cmd+=(-c "model_reasoning_effort=\"${reasoning_effort}\"")
    [[ -z ${schema_file} ]] || cmd+=(--output-schema "${schema_file}")
    [[ ${ephemeral} -eq 0 ]] || cmd+=(--ephemeral)
    [[ ${json_mode} -eq 0 ]] || cmd+=(--json)
    cmd+=(-)
    if [[ ${json_mode} -eq 1 ]]; then run_with_optional_env "${cmd[@]}" <"${prompt_file}" >"${json_file}" 2>"${log_file}"; else run_with_optional_env "${cmd[@]}" <"${prompt_file}" >"${log_file}" 2>&1; fi
    ;;
  claude)
    prompt_text="$(<"${prompt_file}")"
    cmd=("${agent_bin}" --print -p "${prompt_text}")
    [[ -z ${model} ]] || cmd+=(--model "${model}")
    [[ -z ${reasoning_effort} ]] || cmd+=(--effort "${reasoning_effort}")
    if [[ -n ${schema_file} ]]; then [[ -f ${schema_file} ]] || { echo "missing schema: ${schema_file}" >&2; exit 1; }; cmd+=(--json-schema "$(<"${schema_file}")"); fi
    if [[ ${json_mode} -eq 1 ]]; then cmd+=(--output-format json); run_with_optional_env "${cmd[@]}" >"${json_file}" 2>"${log_file}"; [[ -z ${last_file} ]] || jq -r '.result // empty' "${json_file}" >"${last_file}"; else run_with_optional_env "${cmd[@]}" >"${log_file}" 2>&1; [[ -z ${last_file} ]] || cp "${log_file}" "${last_file}"; fi
    ;;
  gemini)
    if [[ ${json_mode} -eq 1 ]]; then run_with_optional_env "${agent_bin}" <"${prompt_file}" >"${json_file}" 2>"${log_file}"; else run_with_optional_env "${agent_bin}" <"${prompt_file}" >"${log_file}" 2>&1; fi
    ;;
  *) echo "unknown agent: ${agent}" >&2; exit 2 ;;
esac
status=$?
set -e

if [[ ${status} -eq 0 ]]; then write_manifest completed 0; else write_manifest failed "${status}"; fi
job_finalized=1
trap - EXIT
exit "${status}"
