#!/usr/bin/env bash
set -euo pipefail

have() { command -v "$1" >/dev/null 2>&1; }
bool() { [[ "$1" -eq 1 ]] && echo true || echo false; }

codex_ok=0
kitty_ok=0
kitty_remote=0
hyprctl_ok=0
hypr_json_ok=0
tmux_ok=0
jq_ok=0
rg_ok=0
python_ok=0

codex_version=""
kitty_version=""
session_type="${XDG_SESSION_TYPE:-}"
desktop_session="${DESKTOP_SESSION:-}"
hypr_sig="${HYPRLAND_INSTANCE_SIGNATURE:-}"
kitty_socket="${KITTY_LISTEN_ON:-}"
hypr_workspace=""
hypr_active_class=""

if have codex; then
  codex_ok=1
  codex_version="$(SINNIX_SKIP_AGENTS_RENDER=1 codex --version 2>/dev/null || true)"
fi
if have kitty; then
  kitty_ok=1
  kitty_version="$(kitty --version 2>/dev/null || true)"
fi
if have tmux; then tmux_ok=1; fi
if have jq; then jq_ok=1; fi
if have rg; then rg_ok=1; fi
if have python3; then python_ok=1; fi

if [[ -n "${kitty_socket}" ]] && [[ "${kitty_ok}" -eq 1 ]]; then
  if kitty @ ls >/dev/null 2>&1; then
    kitty_remote=1
  fi
fi

if have hyprctl; then
  hyprctl_ok=1
  if hyprctl -j activeworkspace >/dev/null 2>&1; then
    hypr_json_ok=1
    if [[ "${jq_ok}" -eq 1 ]]; then
      hypr_workspace="$(hyprctl -j activeworkspace | jq -r '.name // empty' 2>/dev/null || true)"
      hypr_active_class="$(hyprctl -j activewindow | jq -r '.class // empty' 2>/dev/null || true)"
    fi
  fi
fi

cat <<EOF
{
  "runtime": {
    "session_type": "$(printf '%s' "${session_type}" | sed 's/"/\\"/g')",
    "desktop_session": "$(printf '%s' "${desktop_session}" | sed 's/"/\\"/g')",
    "hyprland_signature_present": $([[ -n "${hypr_sig}" ]] && echo true || echo false)
  },
  "tools": {
    "codex": {"available": $(bool "${codex_ok}"), "version": "$(printf '%s' "${codex_version}" | sed 's/"/\\"/g')"},
    "kitty": {"available": $(bool "${kitty_ok}"), "version": "$(printf '%s' "${kitty_version}" | sed 's/"/\\"/g')"},
    "hyprctl": {"available": $(bool "${hyprctl_ok}"), "json_ok": $(bool "${hypr_json_ok}")},
    "tmux": {"available": $(bool "${tmux_ok}")},
    "jq": {"available": $(bool "${jq_ok}")},
    "rg": {"available": $(bool "${rg_ok}")},
    "python3": {"available": $(bool "${python_ok}")}
  },
  "control_plane": {
    "kitty_listen_on_present": $([[ -n "${kitty_socket}" ]] && echo true || echo false),
    "kitty_remote_ok": $(bool "${kitty_remote}"),
    "hypr_workspace": "$(printf '%s' "${hypr_workspace}" | sed 's/"/\\"/g')",
    "hypr_active_class": "$(printf '%s' "${hypr_active_class}" | sed 's/"/\\"/g')"
  },
  "recommended_mode": "$(
    if [[ "${kitty_remote}" -eq 1 && "${codex_ok}" -eq 1 ]]; then
      echo "codex_exec_kitty"
    elif [[ "${codex_ok}" -eq 1 ]]; then
      echo "codex_exec_batch"
    else
      echo "local_tools_only"
    fi
  )"
}
EOF
