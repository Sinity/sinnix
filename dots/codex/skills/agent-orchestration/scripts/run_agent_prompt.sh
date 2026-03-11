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

usage() {
  cat <<'EOF'
Usage:
  run_agent_prompt.sh [options]

Required:
  --agent <claude|codex|gemini>
  --workdir <path>
  --prompt-file <path>
  --log-file <path>

Options:
  --json-file <path>
  --last-file <path>
  --model <name>
  --reasoning-effort <value>
  --schema-file <path>
  --json
  --skip-agents-render
  --ephemeral
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
    -h|--help)
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

if [[ ! -f ${prompt_file} ]]; then
  echo "missing prompt: ${prompt_file}" >&2
  exit 1
fi

if [[ ! -d ${workdir} ]]; then
  echo "missing workdir: ${workdir}" >&2
  exit 1
fi

mkdir -p "$(dirname "${log_file}")"
if [[ -n ${json_file} ]]; then
  mkdir -p "$(dirname "${json_file}")"
fi
if [[ -n ${last_file} ]]; then
  mkdir -p "$(dirname "${last_file}")"
fi

cd "${workdir}"

run_with_optional_env() {
  if [[ ${skip_agents_render} -eq 1 ]]; then
    SINNIX_SKIP_AGENTS_RENDER=1 "$@"
  else
    "$@"
  fi
}

case "${agent}" in
  codex)
    if [[ -z ${model} || -z ${last_file} ]]; then
      echo "codex requires --model and --last-file" >&2
      exit 2
    fi

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

    if [[ ${json_mode} -eq 1 ]]; then
      run_with_optional_env "${cmd[@]}" <"${prompt_file}" >"${json_file}" 2>"${log_file}"
    else
      run_with_optional_env "${cmd[@]}" <"${prompt_file}" >"${log_file}" 2>&1
    fi
    ;;
  claude)
    prompt_text="$(cat "${prompt_file}")"
    cmd=(claude --print -p "${prompt_text}" --workdir "${workdir}")

    if [[ ${json_mode} -eq 1 ]]; then
      run_with_optional_env "${cmd[@]}" >"${json_file}" 2>"${log_file}"
    else
      run_with_optional_env "${cmd[@]}" >"${log_file}" 2>&1
    fi
    ;;
  gemini)
    if [[ ${json_mode} -eq 1 ]]; then
      run_with_optional_env gemini <"${prompt_file}" >"${json_file}" 2>"${log_file}"
    else
      run_with_optional_env gemini <"${prompt_file}" >"${log_file}" 2>&1
    fi
    ;;
  *)
    echo "unknown agent: ${agent}" >&2
    exit 2
    ;;
esac
