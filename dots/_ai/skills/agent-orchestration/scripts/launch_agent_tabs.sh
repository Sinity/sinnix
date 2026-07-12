#!/usr/bin/env bash
set -euo pipefail

agent="codex"
workdir=""
prompt_dir=""
output_dir=""
mode="batch"      # batch | kitty
launch_type="tab" # tab | os-window
model=""
reasoning_effort=""
schema_file=""
json_mode=0
dry_run=0
skip_agents_render=0
ephemeral=0
parallel=1
workspace=""
claude_api_key_auth=0
persist_windows=0
per_task_workdir_base=""
job_prefix=""
status_only=0
persist_shell="${SHELL:-bash}"

usage() {
  cat <<'EOF'
Usage:
  launch_agent_tabs.sh [options] <prompt_file...>

Required:
  --agent <claude|codex|gemini>
  --workdir <path>
  --prompt-dir <path>
  --output-dir <path>

Options:
  --mode <batch|kitty>         Execution mode (default: batch)
  --launch-type <tab|os-window> Kitty launch type (default: tab)
  --model <name>               Agent model (agent-specific default)
  --reasoning-effort <value>   Agent effort level (agent-specific values)
  --xhigh                      Convenience: --reasoning-effort xhigh (codex only)
  --spark                      Convenience: set --model gpt-5.3-codex-spark (codex only)
  --schema <file>              JSON schema path for structured output
  --json                       Enable agent --json output
  --ephemeral                  Run each exec without persisting session files (codex only)
  --parallel <n>               Concurrent batch workers (default: 1; batch mode only)
  --workspace <name>           Silently move Kitty OS windows to this Hyprland workspace
  --claude-api-key-auth        Keep ANTHROPIC_API_KEY for Claude instead of subscription auth
  --skip-agents-render         Set SINNIX_SKIP_AGENTS_RENDER=1 for launched agent commands
  --persist-windows            Kitty mode: keep each window open after the runner
                               exits (drops to an interactive shell in the task
                               workdir) and write <name>.exit status markers
  --per-task-workdir-base <dir> Resolve each task's workdir as <dir>/<prompt_name>
                               (e.g. per-lane git worktrees); makes --workdir optional
  --job-prefix <prefix>        Pass attested job identity to the runner:
                               --job-id <prefix><name> --work-item <name>
  --status                     Report task states from --output-dir (.exit/.log
                               markers) instead of launching; then exit
  --dry-run                    Print commands without executing

Prompt file convention:
  <prompt-dir>/<prompt_name>.prompt
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
  --prompt-dir)
    prompt_dir="${2:?missing value for --prompt-dir}"
    shift 2
    ;;
  --output-dir)
    output_dir="${2:?missing value for --output-dir}"
    shift 2
    ;;
  --mode)
    mode="${2:?missing value for --mode}"
    shift 2
    ;;
  --launch-type)
    launch_type="${2:?missing value for --launch-type}"
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
  --xhigh)
    reasoning_effort="xhigh"
    shift
    ;;
  --spark)
    model="gpt-5.3-codex-spark"
    shift
    ;;
  --schema)
    schema_file="${2:?missing value for --schema}"
    shift 2
    ;;
  --json)
    json_mode=1
    shift
    ;;
  --ephemeral)
    ephemeral=1
    shift
    ;;
  --parallel)
    parallel="${2:?missing value for --parallel}"
    shift 2
    ;;
  --workspace)
    workspace="${2:?missing value for --workspace}"
    shift 2
    ;;
  --claude-api-key-auth)
    claude_api_key_auth=1
    shift
    ;;
  --persist-windows)
    persist_windows=1
    shift
    ;;
  --per-task-workdir-base)
    per_task_workdir_base="${2:?missing value for --per-task-workdir-base}"
    shift 2
    ;;
  --job-prefix)
    job_prefix="${2:?missing value for --job-prefix}"
    shift 2
    ;;
  --status)
    status_only=1
    shift
    ;;
  --skip-agents-render)
    skip_agents_render=1
    shift
    ;;
  --dry-run)
    dry_run=1
    shift
    ;;
  -h | --help)
    usage
    exit 0
    ;;
  --)
    shift
    break
    ;;
  -*)
    echo "unknown option: $1" >&2
    usage >&2
    exit 2
    ;;
  *)
    break
    ;;
  esac
done

if [[ ${status_only} -eq 1 ]]; then
  if [[ -z ${output_dir} || ! -d ${output_dir} ]]; then
    echo "--status requires an existing --output-dir" >&2
    exit 2
  fi
  printf '%-30s %-9s %s\n' TASK STATE DETAIL
  found_any=0
  for exit_file in "${output_dir}"/*.exit; do
    [[ -e ${exit_file} ]] || continue
    found_any=1
    task_name="$(basename "${exit_file%.exit}")"
    task_ec="$(<"${exit_file}")"
    if [[ ${task_ec} == "0" ]]; then
      printf '%-30s %-9s %s\n' "${task_name}" DONE "${output_dir}/${task_name}.last.md"
    else
      printf '%-30s %-9s exit=%s %s\n' "${task_name}" FAILED "${task_ec}" "${output_dir}/${task_name}.log"
    fi
  done
  for log_file in "${output_dir}"/*.log; do
    [[ -e ${log_file} ]] || continue
    task_name="$(basename "${log_file%.log}")"
    [[ -e "${output_dir}/${task_name}.exit" ]] && continue
    found_any=1
    printf '%-30s %-9s log %s\n' "${task_name}" RUNNING "$(du -h "${log_file}" 2>/dev/null | cut -f1)"
  done
  if [[ ${found_any} -eq 0 ]]; then
    echo "(no task artifacts in ${output_dir})"
  fi
  exit 0
fi

if [[ -z ${workdir} && -z ${per_task_workdir_base} ]] || [[ -z ${prompt_dir} || -z ${output_dir} ]]; then
  usage >&2
  exit 2
fi

if [[ ${mode} != "batch" && ${mode} != "kitty" ]]; then
  echo "invalid --mode: ${mode}" >&2
  exit 2
fi

if [[ ${launch_type} != "tab" && ${launch_type} != "os-window" ]]; then
  echo "invalid --launch-type: ${launch_type}" >&2
  exit 2
fi

if [[ ! ${parallel} =~ ^[1-9][0-9]*$ ]]; then
  echo "invalid --parallel value: ${parallel}" >&2
  exit 2
fi
if [[ ${parallel} -gt 1 && ${mode} != "batch" ]]; then
  echo "--parallel is supported only with --mode batch" >&2
  exit 2
fi
if [[ -n ${workspace} && ( ${mode} != "kitty" || ${launch_type} != "os-window" ) ]]; then
  echo "--workspace requires --mode kitty --launch-type os-window" >&2
  exit 2
fi

if [[ $# -lt 1 ]]; then
  echo "no prompt files specified" >&2
  exit 2
fi

# Set only the model defaults required by current batch runners. Claude uses
# the configured CLI default unless --model is supplied.
if [[ -z ${model} ]]; then
  case "${agent}" in
  claude)
    ;;
  codex)
    model="gpt-5.6-terra"
    ;;
  gemini)
    model="gemini-2.0-flash"
    ;;
  *)
    echo "unknown agent: ${agent}" >&2
    exit 2
    ;;
  esac
fi

if [[ ${agent} == "claude" ]]; then
  if ! command -v claude-full >/dev/null 2>&1 && ! command -v claude >/dev/null 2>&1; then
    echo "claude runtime not found (expected claude or claude-full)" >&2
    exit 1
  fi
elif ! command -v "${agent}" >/dev/null 2>&1; then
  echo "${agent} runtime not found on PATH" >&2
  exit 1
fi

mkdir -p "${output_dir}"

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
runner="${script_dir}/run_agent_prompt.sh"

if [[ ! -x ${runner} ]]; then
  echo "runner helper is not executable: ${runner}" >&2
  exit 1
fi

if [[ ${mode} == "kitty" ]]; then
  if ! command -v kitty >/dev/null 2>&1; then
    echo "kitty not found on PATH for --mode kitty" >&2
    exit 1
  fi
  if [[ -z ${KITTY_LISTEN_ON:-} ]]; then
    echo "KITTY_LISTEN_ON is empty; cannot use kitty remote control" >&2
    exit 1
  fi
  if [[ -n ${workspace} ]] && ! command -v sinnix-hypr-control >/dev/null 2>&1; then
    echo "sinnix-hypr-control not found; cannot route Kitty window to ${workspace}" >&2
    exit 1
  fi
fi

resolve_task_workdir() {
  local prompt_name="$1"
  if [[ -n ${per_task_workdir_base} ]]; then
    printf '%s/%s' "${per_task_workdir_base}" "${prompt_name}"
  else
    printf '%s' "${workdir}"
  fi
}

run_batch_agent() {
  local prompt_name="$1"
  local prompt_file="${prompt_dir}/${prompt_name}.prompt"
  local log_file="${output_dir}/${prompt_name}.log"
  local last_file="${output_dir}/${prompt_name}.last.md"
  local json_file="${output_dir}/${prompt_name}.jsonl"
  local task_workdir
  task_workdir="$(resolve_task_workdir "${prompt_name}")"

  if [[ ! -f ${prompt_file} ]]; then
    echo "missing prompt: ${prompt_file}" >&2
    return 1
  fi
  if [[ ! -d ${task_workdir} ]]; then
    echo "missing workdir for ${prompt_name}: ${task_workdir}" >&2
    return 1
  fi

  local -a cmd=(
    "${runner}"
    --agent "${agent}"
    --workdir "${task_workdir}"
    --prompt-file "${prompt_file}"
    --log-file "${log_file}"
  )
  if [[ -n ${job_prefix} ]]; then
    cmd+=(--job-id "${job_prefix}${prompt_name}" --work-item "${prompt_name}")
  fi

  if [[ -n ${json_file} ]]; then
    cmd+=(--json-file "${json_file}")
  fi
  if [[ -n ${last_file} ]]; then
    cmd+=(--last-file "${last_file}")
  fi
  if [[ -n ${model} ]]; then
    cmd+=(--model "${model}")
  fi
  if [[ -n ${reasoning_effort} ]]; then
    cmd+=(--reasoning-effort "${reasoning_effort}")
  fi
  if [[ -n ${schema_file} ]]; then
    cmd+=(--schema-file "${schema_file}")
  fi
  if [[ ${json_mode} -eq 1 ]]; then
    cmd+=(--json)
  fi
  if [[ ${skip_agents_render} -eq 1 ]]; then
    cmd+=(--skip-agents-render)
  fi
  if [[ ${ephemeral} -eq 1 ]]; then
    cmd+=(--ephemeral)
  fi
  if [[ ${claude_api_key_auth} -eq 1 ]]; then
    cmd+=(--claude-api-key-auth)
  fi

  if [[ ${dry_run} -eq 1 ]]; then
    printf 'DRY-RUN (%s): ' "${prompt_name}"
    printf '%q ' "${cmd[@]}"
    echo
    return 0
  fi

  local ec=0
  if "${cmd[@]}"; then
    ec=0
  else
    ec=$?
  fi
  printf '%s\n' "${ec}" >"${output_dir}/${prompt_name}.exit"
  return "${ec}"
}

run_kitty_agent() {
  local prompt_name="$1"
  local prompt_file="${prompt_dir}/${prompt_name}.prompt"
  local log_file="${output_dir}/${prompt_name}.log"
  local last_file="${output_dir}/${prompt_name}.last.md"
  local json_file="${output_dir}/${prompt_name}.jsonl"
  local task_workdir
  task_workdir="$(resolve_task_workdir "${prompt_name}")"

  if [[ ! -f ${prompt_file} ]]; then
    echo "missing prompt: ${prompt_file}" >&2
    return 1
  fi
  if [[ ! -d ${task_workdir} ]]; then
    echo "missing workdir for ${prompt_name}: ${task_workdir}" >&2
    return 1
  fi

  local -a launch_cmd=(
    "${runner}"
    --agent "${agent}"
    --workdir "${task_workdir}"
    --prompt-file "${prompt_file}"
    --log-file "${log_file}"
  )
  if [[ -n ${job_prefix} ]]; then
    launch_cmd+=(--job-id "${job_prefix}${prompt_name}" --work-item "${prompt_name}")
  fi

  if [[ -n ${json_file} ]]; then
    launch_cmd+=(--json-file "${json_file}")
  fi
  if [[ -n ${last_file} ]]; then
    launch_cmd+=(--last-file "${last_file}")
  fi
  if [[ -n ${model} ]]; then
    launch_cmd+=(--model "${model}")
  fi
  if [[ -n ${reasoning_effort} ]]; then
    launch_cmd+=(--reasoning-effort "${reasoning_effort}")
  fi
  if [[ -n ${schema_file} ]]; then
    launch_cmd+=(--schema-file "${schema_file}")
  fi
  if [[ ${json_mode} -eq 1 ]]; then
    launch_cmd+=(--json)
  fi
  if [[ ${skip_agents_render} -eq 1 ]]; then
    launch_cmd+=(--skip-agents-render)
  fi
  if [[ ${ephemeral} -eq 1 ]]; then
    launch_cmd+=(--ephemeral)
  fi
  if [[ ${claude_api_key_auth} -eq 1 ]]; then
    launch_cmd+=(--claude-api-key-auth)
  fi

  local window_title="agent-${prompt_name//[^A-Za-z0-9_.-]/-}"

  local -a exec_argv=("${launch_cmd[@]}")
  if [[ ${persist_windows} -eq 1 ]]; then
    local exit_file="${output_dir}/${prompt_name}.exit"
    local inner
    inner="$(printf '%q ' "${launch_cmd[@]}")"
    inner+="; ec=\$?"
    inner+="; printf '%s\\n' \"\${ec}\" > $(printf '%q' "${exit_file}")"
    inner+="; printf '[%s finished exit=%s — window persists for inspection]\\n' $(printf '%q' "${prompt_name}") \"\${ec}\""
    inner+="; exec ${persist_shell} -i"
    exec_argv=("${persist_shell}" -lc "${inner}")
  fi

  if [[ ${dry_run} -eq 1 ]]; then
    printf 'DRY-RUN (%s): kitty @ launch --keep-focus --type=%s --title %q --tab-title %q --cwd %q -- ' "${prompt_name}" "${launch_type}" "${window_title}" "${prompt_name}" "${task_workdir}"
    printf '%q ' "${exec_argv[@]}"
    if [[ -n ${workspace} ]]; then
      printf '; move silently to workspace %q' "${workspace}"
    fi
    echo
    return 0
  fi

  kitty @ launch \
    --keep-focus \
    --type="${launch_type}" \
    --title "${window_title}" \
    --tab-title "${prompt_name}" \
    --cwd "${task_workdir}" \
    -- "${exec_argv[@]}"

  if [[ -n ${workspace} ]]; then
    local selector="title:^(${window_title})$"
    local moved=0
    for _ in {1..20}; do
      if sinnix-hypr-control dispatch movetoworkspacesilent "${workspace},${selector}" >/dev/null 2>&1; then
        moved=1
        break
      fi
      sleep 0.05
    done
    if [[ ${moved} -ne 1 ]]; then
      echo "warning: launched ${prompt_name} but could not route it to workspace ${workspace}" >&2
    fi
  fi
}

# Special handling for codex with spark model
if [[ ${model} == "gpt-5.3-codex-spark" && -z ${reasoning_effort} ]]; then
  reasoning_effort="xhigh"
fi
if [[ ${agent} == "codex" && -z ${reasoning_effort} ]]; then
  reasoning_effort="high"
fi

batch_active=0
batch_failed=0
for prompt_name in "$@"; do
  # Remove .prompt extension if provided
  prompt_name="${prompt_name%.prompt}"

  if [[ ${mode} == "batch" ]]; then
    run_batch_agent "${prompt_name}" &
    batch_active=$((batch_active + 1))
    if [[ ${batch_active} -ge ${parallel} ]]; then
      if ! wait -n; then
        batch_failed=1
      fi
      batch_active=$((batch_active - 1))
    fi
  else
    run_kitty_agent "${prompt_name}"
    sleep 0.2
  fi
done

if [[ ${mode} == "batch" ]]; then
  while [[ ${batch_active} -gt 0 ]]; do
    if ! wait -n; then
      batch_failed=1
    fi
    batch_active=$((batch_active - 1))
  done
  exit "${batch_failed}"
fi
