#!/usr/bin/env bash
set -euo pipefail

workdir=""
prompt_dir=""
output_dir=""
mode="batch"      # batch | kitty
launch_type="tab" # tab | os-window
model="gpt-5.3-codex"
reasoning_effort=""
schema_file=""
json_mode=0
dry_run=0
skip_agents_render=0
ephemeral=0

usage() {
  cat <<'EOF'
Usage:
  launch_codex_from_prompts.sh [options] <agent...>

Required:
  --workdir <path>
  --prompt-dir <path>
  --output-dir <path>

Options:
  --mode <batch|kitty>         Execution mode (default: batch)
  --launch-type <tab|os-window> Kitty launch type (default: tab)
  --model <name>               Codex model (default: gpt-5.3-codex)
  --reasoning-effort <value>   model_reasoning_effort (minimal|low|medium|high|xhigh)
  --xhigh                      Convenience: --reasoning-effort xhigh
  --spark                      Convenience: set --model gpt-5.3-codex-spark (defaults effort to xhigh unless overridden)
  --schema <file>              JSON schema path for --output-schema
  --json                       Enable codex --json output
  --ephemeral                  Run each exec without persisting session files
  --skip-agents-render         Set SINNIX_SKIP_AGENTS_RENDER=1 for launched codex commands
  --dry-run                    Print commands without executing

Prompt file convention:
  <prompt-dir>/<agent>.prompt
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
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
  echo "no agents specified" >&2
  exit 2
fi

if ! command -v codex >/dev/null 2>&1; then
  echo "codex not found on PATH" >&2
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
  local agent="$1"
  local prompt_file="${prompt_dir}/${agent}.prompt"
  local log_file="${output_dir}/${agent}.log"
  local last_file="${output_dir}/${agent}.last.md"
  local json_file="${output_dir}/${agent}.jsonl"

  if [[ ! -f ${prompt_file} ]]; then
    echo "missing prompt: ${prompt_file}" >&2
    return 1
  fi

  local -a cmd=(codex exec -C "${workdir}" --model "${model}" --output-last-message "${last_file}")
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

  if [[ ${dry_run} -eq 1 ]]; then
    printf 'DRY-RUN (%s): ' "${agent}"
    if [[ ${skip_agents_render} -eq 1 ]]; then
      printf 'SINNIX_SKIP_AGENTS_RENDER=1 '
    fi
    printf '%q ' "${cmd[@]}"
    echo "< ${prompt_file} > ${log_file}"
    return 0
  fi

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
}

run_kitty_agent() {
  local agent="$1"
  local prompt_file="${prompt_dir}/${agent}.prompt"
  local log_file="${output_dir}/${agent}.log"
  local last_file="${output_dir}/${agent}.last.md"
  local json_file="${output_dir}/${agent}.jsonl"

  if [[ ! -f ${prompt_file} ]]; then
    echo "missing prompt: ${prompt_file}" >&2
    return 1
  fi

  local -a codex_cmd=(codex exec -C "${workdir}" --model "${model}" --output-last-message "${last_file}")
  if [[ -n ${reasoning_effort} ]]; then
    codex_cmd+=(-c "model_reasoning_effort=\"${reasoning_effort}\"")
  fi
  if [[ -n ${schema_file} ]]; then
    codex_cmd+=(--output-schema "${schema_file}")
  fi
  if [[ ${ephemeral} -eq 1 ]]; then
    codex_cmd+=(--ephemeral)
  fi
  if [[ ${json_mode} -eq 1 ]]; then
    codex_cmd+=(--json)
  fi
  codex_cmd+=(-)

  local codex_cmd_q
  printf -v codex_cmd_q '%q ' "${codex_cmd[@]}"

  local launch_cmd
  local env_prefix=""
  if [[ ${skip_agents_render} -eq 1 ]]; then
    env_prefix='SINNIX_SKIP_AGENTS_RENDER=1 '
  fi
  if [[ ${json_mode} -eq 1 ]]; then
    printf -v launch_cmd 'cat %q | %s%s >%q 2>%q' "${prompt_file}" "${env_prefix}" "${codex_cmd_q}" "${json_file}" "${log_file}"
  else
    printf -v launch_cmd 'cat %q | %s%s >%q 2>&1' "${prompt_file}" "${env_prefix}" "${codex_cmd_q}" "${log_file}"
  fi

  if [[ ${dry_run} -eq 1 ]]; then
    echo "DRY-RUN (${agent}): kitty @ launch --type=${launch_type} --tab-title ${agent} --cwd ${workdir} -- zsh -lc ${launch_cmd}"
    return 0
  fi

  kitty @ launch \
    --type="${launch_type}" \
    --tab-title "${agent}" \
    --cwd "${workdir}" \
    -- zsh -lc "${launch_cmd}"
}

if [[ ${model} == "gpt-5.3-codex-spark" && -z ${reasoning_effort} ]]; then
  reasoning_effort="xhigh"
fi

for agent in "$@"; do
  if [[ ${mode} == "batch" ]]; then
    run_batch_agent "${agent}"
  else
    run_kitty_agent "${agent}"
    sleep 0.2
  fi
done
