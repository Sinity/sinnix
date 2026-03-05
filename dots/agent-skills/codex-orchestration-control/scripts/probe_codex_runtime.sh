#!/usr/bin/env bash
set -euo pipefail

model="gpt-5.3-codex-spark"
probe_spark=0
workdir="${PWD}"
skip_agents_render=1

while [[ $# -gt 0 ]]; do
  case "$1" in
    --model)
      model="${2:?missing model value}"
      shift 2
      ;;
    --probe-spark)
      probe_spark=1
      shift
      ;;
    --workdir)
      workdir="${2:?missing workdir value}"
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

have_codex=0
have_kitty=0
kitty_remote=0
spark_probe_ok=0
spark_probe_message=""

if command -v codex >/dev/null 2>&1; then
  have_codex=1
  codex_version="$(SINNIX_SKIP_AGENTS_RENDER=1 codex --version 2>/dev/null || true)"
  codex_exec_help="$(SINNIX_SKIP_AGENTS_RENDER=1 codex exec --help 2>/dev/null || true)"
else
  codex_version=""
  codex_exec_help=""
fi

if command -v kitty >/dev/null 2>&1; then
  have_kitty=1
  kitty_version="$(kitty --version 2>/dev/null || true)"
else
  kitty_version=""
fi

if [[ -n "${KITTY_LISTEN_ON:-}" ]] && kitty @ ls >/dev/null 2>&1; then
  kitty_remote=1
fi

if [[ "${probe_spark}" -eq 1 ]]; then
  if [[ "${have_codex}" -ne 1 ]]; then
    spark_probe_message="codex not available"
  else
    tmp_msg="$(mktemp)"
    tmp_log="$(mktemp)"
    if [[ "${skip_agents_render}" -eq 1 ]]; then
      set +e
      SINNIX_SKIP_AGENTS_RENDER=1 codex exec \
        --model "${model}" \
        --skip-git-repo-check \
        -C "${workdir}" \
        --output-last-message "${tmp_msg}" \
        "Reply with exactly: SPARK_OK" >"${tmp_log}" 2>&1
      probe_rc=$?
      set -e
    else
      set +e
      codex exec \
        --model "${model}" \
        --skip-git-repo-check \
        -C "${workdir}" \
        --output-last-message "${tmp_msg}" \
        "Reply with exactly: SPARK_OK" >"${tmp_log}" 2>&1
      probe_rc=$?
      set -e
    fi
    if [[ "${probe_rc}" -eq 0 ]]; then
      if grep -q '^SPARK_OK$' "${tmp_msg}"; then
        spark_probe_ok=1
        spark_probe_message="model responded with SPARK_OK"
      else
        spark_probe_message="request succeeded but sentinel mismatch"
      fi
    else
      spark_probe_message="request failed; see probe log"
    fi
    rm -f "${tmp_msg}" "${tmp_log}"
  fi
fi

supports_ephemeral=false
supports_json=false
supports_output_schema=false
supports_progress_cursor=false
if [[ "${have_codex}" -eq 1 ]]; then
  if grep -q -- '--ephemeral' <<<"${codex_exec_help}"; then
    supports_ephemeral=true
  fi
  if grep -q -- '--json' <<<"${codex_exec_help}"; then
    supports_json=true
  fi
  if grep -q -- '--output-schema' <<<"${codex_exec_help}"; then
    supports_output_schema=true
  fi
  if grep -q -- '--progress-cursor' <<<"${codex_exec_help}"; then
    supports_progress_cursor=true
  fi
fi

cat <<EOF
{
  "codex": {
    "available": ${have_codex},
    "version": "$(printf '%s' "${codex_version}" | sed 's/"/\\"/g')",
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
    "listen_on_present": $([[ -n "${KITTY_LISTEN_ON:-}" ]] && echo true || echo false),
    "remote_control_ok": $([[ "${kitty_remote}" -eq 1 ]] && echo true || echo false)
  },
  "spark_probe": {
    "requested": $([[ "${probe_spark}" -eq 1 ]] && echo true || echo false),
    "model": "$(printf '%s' "${model}" | sed 's/"/\\"/g')",
    "ok": $([[ "${spark_probe_ok}" -eq 1 ]] && echo true || echo false),
    "message": "$(printf '%s' "${spark_probe_message}" | sed 's/"/\\"/g')"
  },
  "execution_recommendation": {
    "skip_agents_render_default": $([[ "${skip_agents_render}" -eq 1 ]] && echo true || echo false),
    "recommended_mode": "$(
      if [[ "${have_codex}" -eq 1 && "${have_kitty}" -eq 1 && "${kitty_remote}" -eq 1 ]]; then
        printf '%s' "codex_exec_kitty"
      elif [[ "${have_codex}" -eq 1 ]]; then
        printf '%s' "codex_exec_batch"
      else
        printf '%s' "unavailable"
      fi
    )"
  }
}
EOF
