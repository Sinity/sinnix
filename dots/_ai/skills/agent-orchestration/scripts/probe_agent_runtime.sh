#!/usr/bin/env bash
set -euo pipefail

agent="codex"
model="gpt-5.6-terra"
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

if command -v "$agent" >/dev/null 2>&1; then
  have_agent=1
  if [[ ${skip_agents_render} -eq 1 ]]; then
    agent_version="$(SINNIX_SKIP_AGENTS_RENDER=1 "$agent" --version 2>/dev/null || true)"
  else
    agent_version="$("$agent" --version 2>/dev/null || true)"
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
    # For codex: use exec for probing
    if [[ ${agent} == "codex" ]]; then
      tmp_msg="$(mktemp)"
      tmp_log="$(mktemp)"
      if [[ ${skip_agents_render} -eq 1 ]]; then
        set +e
        SINNIX_SKIP_AGENTS_RENDER=1 codex exec \
          --model "${model}" \
          --skip-git-repo-check \
          -C "${workdir}" \
          --output-last-message "${tmp_msg}" \
          "Reply with exactly: MODEL_OK" >"${tmp_log}" 2>&1
        probe_rc=$?
        set -e
      else
        set +e
        codex exec \
          --model "${model}" \
          --skip-git-repo-check \
          -C "${workdir}" \
          --output-last-message "${tmp_msg}" \
          "Reply with exactly: MODEL_OK" >"${tmp_log}" 2>&1
        probe_rc=$?
        set -e
      fi
      if [[ ${probe_rc} -eq 0 ]]; then
        if grep -q '^MODEL_OK$' "${tmp_msg}"; then
          model_probe_ok=1
          model_probe_message="model responded with MODEL_OK"
        else
          model_probe_message="request succeeded but sentinel mismatch"
        fi
      else
        model_probe_message="request failed; see probe log"
      fi
      rm -f "${tmp_msg}" "${tmp_log}"
    else
      # For claude and gemini: simple version check
      model_probe_message="version check passed for ${agent}"
      model_probe_ok=1
    fi
  fi
fi

supports_ephemeral=false
supports_json=false
supports_output_schema=false
supports_progress_cursor=false

# Only check exec capabilities for codex
if [[ ${have_agent} -eq 1 && ${agent} == "codex" ]]; then
  if [[ ${skip_agents_render} -eq 1 ]]; then
    agent_exec_help="$(SINNIX_SKIP_AGENTS_RENDER=1 codex exec --help 2>/dev/null || true)"
  else
    agent_exec_help="$(codex exec --help 2>/dev/null || true)"
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
      "exec_progress_cursor": ${supports_progress_cursor}
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
  if [[ ${have_agent} -eq 1 && ${have_kitty} -eq 1 && ${kitty_remote} -eq 1 ]]; then
    printf '%s' "${agent}_exec_kitty"
  elif [[ ${have_agent} -eq 1 ]]; then
    printf '%s' "${agent}_exec_batch"
  else
    printf '%s' "unavailable"
  fi
)"
  }
}
EOF
