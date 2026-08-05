#!/usr/bin/env bash
set -euo pipefail

agent="codex"
model=""
probe_model=0
workdir="${PWD}"
skip_agents_render=1

while [[ $# -gt 0 ]]; do
  case "$1" in
  --agent)
    agent="${2:?missing agent}"
    shift 2
    ;;
  --model)
    model="${2:?missing model}"
    shift 2
    ;;
  --probe-model)
    probe_model=1
    shift
    ;;
  --workdir)
    workdir="${2:?missing workdir}"
    shift 2
    ;;
  --no-skip-agents-render)
    skip_agents_render=0
    shift
    ;;
  *)
    echo "unknown option: $1" >&2
    exit 2
    ;;
  esac
done

have_agent=0
have_kitty=0
kitty_remote=0
model_probe_ok=0
model_probe_message=""

agent_version=""
agent_exec_help=""
kitty_version=""

resolve_agent_bin() {
  case "${agent}" in
  claude) command -v claude-full 2>/dev/null || command -v claude 2>/dev/null ;;
  codex | gemini) command -v "${agent}" 2>/dev/null ;;
  grok) command -v grok-sinnix 2>/dev/null || command -v grok 2>/dev/null ;;
  antigravity) command -v agy-sinnix 2>/dev/null || command -v agy 2>/dev/null ;;
  *) return 1 ;;
  esac
}

if [[ -z ${model} ]]; then
  case "${agent}" in
  codex) model="gpt-5.6-terra" ;;
  grok) model="grok-4.5" ;;
  antigravity) model="gemini-3.1-pro-high" ;;
  esac
fi

agent_bin="$(resolve_agent_bin || true)"

if [[ -n ${agent_bin} ]]; then
  have_agent=1
  if [[ ${skip_agents_render} -eq 1 ]]; then
    agent_version="$(SINNIX_SKIP_AGENTS_RENDER=1 "${agent_bin}" --version 2>/dev/null || true)"
  else
    agent_version="$("${agent_bin}" --version 2>/dev/null || true)"
  fi
fi

if command -v kitty >/dev/null 2>&1; then
  have_kitty=1
  kitty_version="$(kitty --version 2>/dev/null || true)"
fi

if [[ -n ${KITTY_LISTEN_ON:-} ]] && kitty @ ls >/dev/null 2>&1; then
  kitty_remote=1
fi

if [[ ${probe_model} -eq 1 ]]; then
  if [[ ${have_agent} -ne 1 ]]; then
    model_probe_message="${agent} not available"
  else
    # Codex, Grok, and Antigravity have a documented non-interactive probe.
    if [[ ${agent} == "codex" || ${agent} == "grok" || ${agent} == "antigravity" ]]; then
      tmp_msg="$(mktemp)"
      tmp_log="$(mktemp)"
      if [[ ${agent} == "codex" ]]; then
        probe_cmd=("${agent_bin}" exec --model "${model}" --skip-git-repo-check -C "${workdir}" --output-last-message "${tmp_msg}" "Reply with exactly: MODEL_OK")
      elif [[ ${agent} == "grok" ]]; then
        probe_cmd=("${agent_bin}" --cwd "${workdir}" --model "${model}" --single "Reply with exactly: MODEL_OK" --tools "" --no-memory --no-subagents)
      else
        probe_cmd=("${agent_bin}" --model "${model}" --effort high --print "Reply with exactly: MODEL_OK")
      fi
      if [[ ${skip_agents_render} -eq 1 ]]; then
        set +e
        SINNIX_SKIP_AGENTS_RENDER=1 "${probe_cmd[@]}" >"${tmp_log}" 2>&1
        probe_rc=$?
        set -e
      else
        set +e
        "${probe_cmd[@]}" >"${tmp_log}" 2>&1
        probe_rc=$?
        set -e
      fi
      if [[ ${probe_rc} -eq 0 ]]; then
        if [[ ${agent} == "codex" && -f ${tmp_msg} ]] && grep -q '^MODEL_OK$' "${tmp_msg}" ||
          [[ ${agent} != "codex" ]] && grep -q 'MODEL_OK' "${tmp_log}"; then
          model_probe_ok=1
          model_probe_message="model responded with MODEL_OK"
        else
          model_probe_message="request succeeded but sentinel mismatch"
        fi
      else
        model_probe_message="request failed with exit status ${probe_rc}"
      fi
      rm -f "${tmp_msg}" "${tmp_log}"
    else
      # Claude and Gemini do not have one stable cross-version probe contract.
      model_probe_message="version check passed for ${agent}"
      model_probe_ok=1
    fi
  fi
fi

supports_ephemeral=false
supports_json=false
supports_output_schema=false
supports_progress_cursor=false
supports_print=false
supports_model=false
supports_effort=false

# Check native headless capabilities where the CLI exposes them.
if [[ ${have_agent} -eq 1 && (${agent} == "codex" || ${agent} == "grok" || ${agent} == "antigravity") ]]; then
  if [[ ${skip_agents_render} -eq 1 ]]; then
    if [[ ${agent} == "codex" ]]; then
      agent_exec_help="$(SINNIX_SKIP_AGENTS_RENDER=1 "${agent_bin}" exec --help 2>&1 || true)"
    else
      agent_exec_help="$(SINNIX_SKIP_AGENTS_RENDER=1 "${agent_bin}" --help 2>&1 || true)"
    fi
  else
    if [[ ${agent} == "codex" ]]; then
      agent_exec_help="$("${agent_bin}" exec --help 2>&1 || true)"
    else
      agent_exec_help="$("${agent_bin}" --help 2>&1 || true)"
    fi
  fi
  if grep -q -- '--ephemeral' <<<"${agent_exec_help}"; then
    supports_ephemeral=true
  fi
  if grep -q -- '--json' <<<"${agent_exec_help}"; then
    supports_json=true
  fi
  if grep -q -- '--output-schema' <<<"${agent_exec_help}"; then
    supports_output_schema=true
  fi
  if grep -q -- '--progress-cursor' <<<"${agent_exec_help}"; then
    supports_progress_cursor=true
  fi
  if grep -q -- '--print\|--single' <<<"${agent_exec_help}"; then
    supports_print=true
  fi
  if grep -q -- '--model' <<<"${agent_exec_help}"; then
    supports_model=true
  fi
  if grep -q -- '--effort\|--reasoning-effort' <<<"${agent_exec_help}"; then
    supports_effort=true
  fi
fi

cat <<EOF
{
  "agent": {
    "name": "${agent}",
    "available": ${have_agent},
    "version": "$(printf '%s' "${agent_version}" | sed 's/"/\\"/g')",
    "capabilities": {
      "exec_ephemeral": ${supports_ephemeral},
      "exec_json": ${supports_json},
      "exec_output_schema": ${supports_output_schema},
      "exec_progress_cursor": ${supports_progress_cursor},
      "print": ${supports_print},
      "model": ${supports_model},
      "effort": ${supports_effort}
    }
  },
  "kitty": {
    "available": ${have_kitty},
    "version": "$(printf '%s' "${kitty_version}" | sed 's/"/\\"/g')",
    "listen_on_present": $([[ -n ${KITTY_LISTEN_ON:-} ]] && echo true || echo false),
    "remote_control_ok": $([[ ${kitty_remote} -eq 1 ]] && echo true || echo false)
  },
  "model_probe": {
    "requested": $([[ ${probe_model} -eq 1 ]] && echo true || echo false),
    "model": "$(printf '%s' "${model}" | sed 's/"/\\"/g')",
    "ok": $([[ ${model_probe_ok} -eq 1 ]] && echo true || echo false),
    "message": "$(printf '%s' "${model_probe_message}" | sed 's/"/\\"/g')"
  },
  "execution_recommendation": {
    "skip_agents_render_default": $([[ ${skip_agents_render} -eq 1 ]] && echo true || echo false),
    "recommended_mode": "$(
  if [[ ${have_agent} -eq 1 ]]; then
    printf '%s' "${agent}_exec_batch"
  else
    printf '%s' "unavailable"
  fi
)"
  }
}
EOF
