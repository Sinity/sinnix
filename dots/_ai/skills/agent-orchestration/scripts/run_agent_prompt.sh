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
  --claude-api-key-auth       Keep ANTHROPIC_API_KEY for Claude instead of subscription auth
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
  --claude-api-key-auth)
    claude_api_key_auth=1
    shift
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

resolve_agent_bin() {
  case "$1" in
  claude)
    if command -v claude-full >/dev/null 2>&1; then
      command -v claude-full
    elif command -v claude >/dev/null 2>&1; then
      command -v claude
    else
      return 1
    fi
    ;;
  codex | gemini)
    command -v "$1"
    ;;
  *)
    return 1
    ;;
  esac
}

agent_bin="$(resolve_agent_bin "${agent}")" || {
  echo "${agent} runtime not found (Claude accepts claude or claude-full)" >&2
  exit 1
}

run_with_optional_env() {
  local -a env_args=(env)
  if [[ ${agent} == "claude" && ${claude_api_key_auth} -eq 0 ]]; then
    env_args+=(-u ANTHROPIC_API_KEY)
  fi
  if [[ ${skip_agents_render} -eq 1 ]]; then
    env_args+=(SINNIX_SKIP_AGENTS_RENDER=1)
  fi
  "${env_args[@]}" "$@"
}

case "${agent}" in
codex)
  if [[ -z ${model} || -z ${last_file} ]]; then
    echo "codex requires --model and --last-file" >&2
    exit 2
  fi

  cmd=("${agent_bin}" exec -C "${workdir}" --model "${model}" --output-last-message "${last_file}")
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
  cmd=("${agent_bin}" --print -p "${prompt_text}")
  if [[ -n ${model} ]]; then
    cmd+=(--model "${model}")
  fi
  if [[ -n ${reasoning_effort} ]]; then
    cmd+=(--effort "${reasoning_effort}")
  fi
  if [[ -n ${schema_file} ]]; then
    [[ -f ${schema_file} ]] || {
      echo "missing schema: ${schema_file}" >&2
      exit 1
    }
    cmd+=(--json-schema "$(<"${schema_file}")")
  fi

  if [[ ${json_mode} -eq 1 ]]; then
    cmd+=(--output-format json)
    run_with_optional_env "${cmd[@]}" >"${json_file}" 2>"${log_file}"
    if [[ -n ${last_file} ]]; then
      jq -r '.result // empty' "${json_file}" >"${last_file}"
    fi
  else
    run_with_optional_env "${cmd[@]}" >"${log_file}" 2>&1
    if [[ -n ${last_file} ]]; then
      cp "${log_file}" "${last_file}"
    fi
  fi
  ;;
gemini)
  if [[ ${json_mode} -eq 1 ]]; then
    run_with_optional_env "${agent_bin}" <"${prompt_file}" >"${json_file}" 2>"${log_file}"
  else
    run_with_optional_env "${agent_bin}" <"${prompt_file}" >"${log_file}" 2>&1
  fi
  ;;
*)
  echo "unknown agent: ${agent}" >&2
  exit 2
  ;;
esac
