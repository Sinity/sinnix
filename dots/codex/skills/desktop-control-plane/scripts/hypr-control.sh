#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: hypr-control.sh <command> [options]

Commands:
  status
  active-window
  workspaces
  binds [--json] [--grep <pattern>]
  dispatch <dispatcher> [args...]
  keyword <name> <value>
  batch "<command1 ; command2 ; ...>"
  screenshot-probe

Notes:
- This is a thin, safe wrapper around hyprctl for automation.
- For keyboard text injection, use kitty-remote-control.sh for terminal targets.
USAGE
}

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "missing dependency: $1" >&2
    exit 1
  }
}

need_cmd hyprctl
cmd="${1:-}"
shift || true

case "$cmd" in
status)
  need_cmd jq
  monitors="$(hyprctl -j monitors)"
  active_ws="$(hyprctl -j activeworkspace)"
  active_win="$(hyprctl -j activewindow)"
  jq -n \
    --argjson monitors "$monitors" \
    --argjson ws "$active_ws" \
    --argjson win "$active_win" \
    '{
        active_workspace: ($ws.name // ""),
        active_window: {class: ($win.class // ""), title: ($win.title // "")},
        focused_monitor: (
          ($monitors | map(select(.focused == true)) | .[0]) as $m
          | {
              name: ($m.name // ""),
              format: ($m.currentFormat // ""),
              cm_preset: ($m.colorManagementPreset // ""),
              sdr_brightness: ($m.sdrBrightness // null),
              sdr_saturation: ($m.sdrSaturation // null),
              vrr: ($m.vrr // null)
            }
        )
      }'
  ;;

active-window)
  hyprctl -j activewindow
  ;;

workspaces)
  hyprctl -j workspaces
  ;;

binds)
  json=0
  pattern=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
    --json)
      json=1
      shift
      ;;
    --grep)
      pattern="${2:?missing pattern}"
      shift 2
      ;;
    *)
      echo "unknown arg: $1" >&2
      exit 2
      ;;
    esac
  done
  data="$(hyprctl -j binds)"
  if [[ -n $pattern ]]; then
    need_cmd jq
    data="$(printf '%s' "$data" | jq --arg p "$pattern" 'map(select((((.key // "") | test($p; "i")) or (((.dispatcher // "") | test($p; "i")) or (((.arg // "") | test($p; "i")))))))')"
  fi
  if [[ $json -eq 1 ]]; then
    printf '%s\n' "$data"
  else
    need_cmd jq
    printf '%s' "$data" | jq -r '.[] | [(.modmask // ""), (.key // ""), (.dispatcher // ""), (.arg // "")] | @tsv' | awk 'BEGIN{print "MOD\tKEY\tDISPATCHER\tARG"} {print}'
  fi
  ;;

dispatch)
  [[ $# -ge 1 ]] || {
    echo "dispatch requires dispatcher name" >&2
    exit 2
  }
  hyprctl dispatch "$@"
  ;;

keyword)
  [[ $# -ge 2 ]] || {
    echo "keyword requires name and value" >&2
    exit 2
  }
  name="$1"
  shift
  value="$*"
  hyprctl keyword "$name" "$value"
  ;;

batch)
  [[ $# -eq 1 ]] || {
    echo "batch requires one quoted command string" >&2
    exit 2
  }
  hyprctl --batch "$1"
  ;;

screenshot-probe)
  need_cmd jq
  hyprctl -j monitors | jq '{
      focused: (map(select(.focused == true)) | .[0] | {
        name,
        currentFormat,
        colorManagementPreset,
        sdrBrightness,
        sdrSaturation,
        refreshRate
      }),
      any_hdr: (map(.colorManagementPreset == "hdr") | any)
    }'
  ;;

-h | --help | help | "")
  usage
  ;;

*)
  echo "unknown command: $cmd" >&2
  usage >&2
  exit 2
  ;;
esac
