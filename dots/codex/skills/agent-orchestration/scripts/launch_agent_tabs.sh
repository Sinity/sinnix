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
  --reasoning-effort <value>   model_reasoning_effort (minimal|low|medium|high|xhigh, codex only)
  --xhigh                      Convenience: --reasoning-effort xhigh (codex only)
  --spark                      Convenience: set --model gpt-5.3-codex-spark (codex only)
  --schema <file>              JSON schema path for --output-schema (codex only)
  --json                       Enable agent --json output
  --ephemeral                  Run each exec without persisting session files (codex only)
  --skip-agents-render         Set SINNIX_SKIP_AGENTS_RENDER=1 for launched agent commands
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

if [[ -z ${workdir} || -z ${prompt_dir} || -z ${output_dir} ]]; then
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

if [[ $# -lt 1 ]]; then
  echo "no prompt files specified" >&2
  exit 2
fi

# Set default models per agent if not specified
if [[ -z ${model} ]]; then
  case "${agent}" in
  claude)
    model="claude-opus-4.6"
    ;;
  codex)
    model="gpt-5.3-codex"
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

if ! command -v "${agent}" >/dev/null 2>&1; then
  echo "${agent} not found on PATH" >&2
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
fi

run_batch_agent() {
  local prompt_name="$1"
  local prompt_file="${prompt_dir}/${prompt_name}.prompt"
  local log_file="${output_dir}/${prompt_name}.log"
  local last_file="${output_dir}/${prompt_name}.last.md"
  local json_file="${output_dir}/${prompt_name}.jsonl"

  if [[ ! -f ${prompt_file} ]]; then
    echo "missing prompt: ${prompt_file}" >&2
    return 1
  fi

  local -a cmd=(
    "${runner}"
    --agent "${agent}"
    --workdir "${workdir}"
    --prompt-file "${prompt_file}"
    --log-file "${log_file}"
  )

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

  if [[ ${dry_run} -eq 1 ]]; then
    printf 'DRY-RUN (%s): ' "${prompt_name}"
    printf '%q ' "${cmd[@]}"
    echo
    return 0
  fi

  "${cmd[@]}"
}

run_kitty_agent() {
  local prompt_name="$1"
  local prompt_file="${prompt_dir}/${prompt_name}.prompt"
  local log_file="${output_dir}/${prompt_name}.log"
  local last_file="${output_dir}/${prompt_name}.last.md"
  local json_file="${output_dir}/${prompt_name}.jsonl"

  if [[ ! -f ${prompt_file} ]]; then
    echo "missing prompt: ${prompt_file}" >&2
    return 1
  fi

  local -a launch_cmd=(
    "${runner}"
    --agent "${agent}"
    --workdir "${workdir}"
    --prompt-file "${prompt_file}"
    --log-file "${log_file}"
  )

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

  if [[ ${dry_run} -eq 1 ]]; then
    printf 'DRY-RUN (%s): kitty @ launch --type=%s --tab-title %q --cwd %q -- ' "${prompt_name}" "${launch_type}" "${prompt_name}" "${workdir}"
    printf '%q ' "${launch_cmd[@]}"
    echo
    return 0
  fi

  kitty @ launch \
    --type="${launch_type}" \
    --tab-title "${prompt_name}" \
    --cwd "${workdir}" \
    -- "${launch_cmd[@]}"
}

# Special handling for codex with spark model
if [[ ${model} == "gpt-5.3-codex-spark" && -z ${reasoning_effort} ]]; then
  reasoning_effort="xhigh"
fi

for prompt_name in "$@"; do
  # Remove .prompt extension if provided
  prompt_name="${prompt_name%.prompt}"

  if [[ ${mode} == "batch" ]]; then
    run_batch_agent "${prompt_name}"
  else
    run_kitty_agent "${prompt_name}"
    sleep 0.2
  fi
done
