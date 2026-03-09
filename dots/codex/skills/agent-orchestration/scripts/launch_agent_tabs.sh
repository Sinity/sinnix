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

  local -a cmd

  case "${agent}" in
  codex)
    cmd=(codex exec -C "${workdir}" --model "${model}" --output-last-message "${last_file}")
    if [[ -n ${reasoning_effort} ]]; then
      cmd+=(-c "model_reasoning_effort=\"${reasoning_effort}\"")
    fi
    if [[ -n ${schema_file} ]]; then
      cmd+=(--output-schema "${schema_file}")
    fi
    if [[ ${ephemeral} -eq 1 ]]; then
      cmd+=(--ephemeral)
    fi
    if [[ ${json_mode} -eq 1 ]]; then
      cmd+=(--json)
    fi
    cmd+=(-)
    ;;
  claude)
    cmd=(claude --print -p)
    # Claude reads prompt as argument, not stdin
    ;;
  gemini)
    cmd=(gemini)
    ;;
  *)
    echo "unknown agent: ${agent}" >&2
    return 2
    ;;
  esac

  if [[ ${dry_run} -eq 1 ]]; then
    printf 'DRY-RUN (%s): ' "${prompt_name}"
    if [[ ${skip_agents_render} -eq 1 ]]; then
      printf 'SINNIX_SKIP_AGENTS_RENDER=1 '
    fi
    if [[ ${agent} == "claude" ]]; then
      printf 'claude --print -p "$(cat %s)" --workdir %s' "${prompt_file}" "${workdir}"
    else
      printf '%q ' "${cmd[@]}"
      echo -n "< ${prompt_file}"
    fi
    echo " > ${log_file}"
    return 0
  fi

  if [[ ${agent} == "claude" ]]; then
    # Claude: read prompt file and pass via -p argument
    local prompt_text
    prompt_text="$(cat "${prompt_file}")"
    if [[ ${json_mode} -eq 1 ]]; then
      if [[ ${skip_agents_render} -eq 1 ]]; then
        SINNIX_SKIP_AGENTS_RENDER=1 claude --print -p "$prompt_text" --workdir "${workdir}" >"${json_file}" 2>"${log_file}"
      else
        claude --print -p "$prompt_text" --workdir "${workdir}" >"${json_file}" 2>"${log_file}"
      fi
    else
      if [[ ${skip_agents_render} -eq 1 ]]; then
        SINNIX_SKIP_AGENTS_RENDER=1 claude --print -p "$prompt_text" --workdir "${workdir}" >"${log_file}" 2>&1
      else
        claude --print -p "$prompt_text" --workdir "${workdir}" >"${log_file}" 2>&1
      fi
    fi
  elif [[ ${agent} == "gemini" ]]; then
    # Gemini: read prompt from stdin
    if [[ ${json_mode} -eq 1 ]]; then
      if [[ ${skip_agents_render} -eq 1 ]]; then
        SINNIX_SKIP_AGENTS_RENDER=1 gemini <"${prompt_file}" >"${json_file}" 2>"${log_file}"
      else
        gemini <"${prompt_file}" >"${json_file}" 2>"${log_file}"
      fi
    else
      if [[ ${skip_agents_render} -eq 1 ]]; then
        SINNIX_SKIP_AGENTS_RENDER=1 gemini <"${prompt_file}" >"${log_file}" 2>&1
      else
        gemini <"${prompt_file}" >"${log_file}" 2>&1
      fi
    fi
  else
    # Codex: read prompt from stdin
    if [[ ${json_mode} -eq 1 ]]; then
      if [[ ${skip_agents_render} -eq 1 ]]; then
        SINNIX_SKIP_AGENTS_RENDER=1 "${cmd[@]}" <"${prompt_file}" >"${json_file}" 2>"${log_file}"
      else
        "${cmd[@]}" <"${prompt_file}" >"${json_file}" 2>"${log_file}"
      fi
    else
      if [[ ${skip_agents_render} -eq 1 ]]; then
        SINNIX_SKIP_AGENTS_RENDER=1 "${cmd[@]}" <"${prompt_file}" >"${log_file}" 2>&1
      else
        "${cmd[@]}" <"${prompt_file}" >"${log_file}" 2>&1
      fi
    fi
  fi
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

  local -a agent_cmd
  local launch_cmd
  local env_prefix=""

  if [[ ${skip_agents_render} -eq 1 ]]; then
    env_prefix='SINNIX_SKIP_AGENTS_RENDER=1 '
  fi

  case "${agent}" in
  codex)
    agent_cmd=(codex exec -C "${workdir}" --model "${model}" --output-last-message "${last_file}")
    if [[ -n ${reasoning_effort} ]]; then
      agent_cmd+=(-c "model_reasoning_effort=\"${reasoning_effort}\"")
    fi
    if [[ -n ${schema_file} ]]; then
      agent_cmd+=(--output-schema "${schema_file}")
    fi
    if [[ ${ephemeral} -eq 1 ]]; then
      agent_cmd+=(--ephemeral)
    fi
    if [[ ${json_mode} -eq 1 ]]; then
      agent_cmd+=(--json)
    fi
    agent_cmd+=(-)
    local cmd_q
    printf -v cmd_q '%q ' "${agent_cmd[@]}"
    if [[ ${json_mode} -eq 1 ]]; then
      printf -v launch_cmd 'cat %q | %s%s >%q 2>%q' "${prompt_file}" "${env_prefix}" "${cmd_q}" "${json_file}" "${log_file}"
    else
      printf -v launch_cmd 'cat %q | %s%s >%q 2>&1' "${prompt_file}" "${env_prefix}" "${cmd_q}" "${log_file}"
    fi
    ;;
  claude)
    local prompt_text
    prompt_text="$(cat "${prompt_file}")"
    # Escape for shell
    local prompt_escaped
    printf -v prompt_escaped '%q' "$prompt_text"
    if [[ ${json_mode} -eq 1 ]]; then
      printf -v launch_cmd '%sclaude --print -p %s --workdir %q >%q 2>%q' "${env_prefix}" "${prompt_escaped}" "${workdir}" "${json_file}" "${log_file}"
    else
      printf -v launch_cmd '%sclaude --print -p %s --workdir %q >%q 2>&1' "${env_prefix}" "${prompt_escaped}" "${workdir}" "${log_file}"
    fi
    ;;
  gemini)
    if [[ ${json_mode} -eq 1 ]]; then
      printf -v launch_cmd 'cat %q | %sgemini >%q 2>%q' "${prompt_file}" "${env_prefix}" "${json_file}" "${log_file}"
    else
      printf -v launch_cmd 'cat %q | %sgemini >%q 2>&1' "${prompt_file}" "${env_prefix}" "${log_file}"
    fi
    ;;
  *)
    echo "unknown agent: ${agent}" >&2
    return 2
    ;;
  esac

  if [[ ${dry_run} -eq 1 ]]; then
    echo "DRY-RUN (${prompt_name}): kitty @ launch --type=${launch_type} --tab-title ${prompt_name} --cwd ${workdir} -- zsh -lc ${launch_cmd}"
    return 0
  fi

  kitty @ launch \
    --type="${launch_type}" \
    --tab-title "${prompt_name}" \
    --cwd "${workdir}" \
    -- zsh -lc "${launch_cmd}"
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
