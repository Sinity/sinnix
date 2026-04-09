#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: hypr-control.sh <command> [options]

Commands:
  status
  active-window
  clients [--json] [--grep <pattern>]
  workspaces
  binds [--json] [--grep <pattern>]
  focus-window <window>
  dispatch <dispatcher> [args...]
  send-shortcut <mods> <key> [window]
  send-keystate <mods> <key> <down|repeat|up> <window>
  paste <window> [--text <text> | --text-file <path>] [--enter] [--paste-mods <mods>] [--paste-key <key>] [--enter-key <key>] [--no-focus] [--no-restore-clipboard]
  keyword <name> <value>
  batch "<command1 ; command2 ; ...>"
  screenshot-probe

Notes:
- This is a thin, safe wrapper around hyprctl for automation.
- For terminal targets, prefer kitty-remote-control.sh over global shortcut injection.
- Clipboard-backed paste is most reliable for native Wayland apps; XWayland targets are best-effort.
USAGE
}

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "missing dependency: $1" >&2
    exit 1
  }
}

need_cmd hyprctl

join_by() {
  local sep="$1"
  shift || true
  local first=1
  for item in "$@"; do
    if [[ $first -eq 1 ]]; then
      printf '%s' "$item"
      first=0
    else
      printf '%s%s' "$sep" "$item"
    fi
  done
}

send_shortcut() {
  local mods="$1"
  local key="$2"
  local window="${3:-}"
  local payload
  if [[ -n $window ]]; then
    payload="$(join_by ', ' "$mods" "$key" "$window")"
  else
    payload="$(join_by ', ' "$mods" "$key")"
  fi
  hyprctl dispatch sendshortcut "$payload"
}

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

clients)
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
  need_cmd jq
  data="$(hyprctl -j clients)"
  if [[ -n $pattern ]]; then
    data="$(printf '%s' "$data" | jq --arg p "$pattern" 'map(select((((.class // "") | test($p; "i")) or ((.title // "") | test($p; "i")) or ((.address // "") | test($p; "i")) or ((.workspace.name // "") | test($p; "i")))))')"
  fi
  if [[ $json -eq 1 ]]; then
    printf '%s\n' "$data"
  else
    printf '%s' "$data" | jq -r '.[] | [(.class // ""), (.title // ""), (.workspace.name // ""), (.address // "")] | @tsv' | awk 'BEGIN{print "CLASS\tTITLE\tWORKSPACE\tADDRESS"} {print}'
  fi
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

focus-window)
  [[ $# -eq 1 ]] || {
    echo "focus-window requires one window selector" >&2
    exit 2
  }
  hyprctl dispatch focuswindow "$1"
  ;;

send-shortcut)
  [[ $# -ge 2 ]] || {
    echo "send-shortcut requires mods and key" >&2
    exit 2
  }
  mods="$1"
  key="$2"
  window="${3:-}"
  send_shortcut "$mods" "$key" "$window"
  ;;

send-keystate)
  [[ $# -eq 4 ]] || {
    echo "send-keystate requires mods, key, state, and window" >&2
    exit 2
  }
  payload="$(join_by ', ' "$1" "$2" "$3" "$4")"
  hyprctl dispatch sendkeystate "$payload"
  ;;

paste)
  need_cmd wl-copy
  need_cmd wl-paste
  [[ $# -ge 1 ]] || {
    echo "paste requires a window selector" >&2
    exit 2
  }
  window="$1"
  shift
  text=""
  text_file=""
  do_enter=0
  do_focus=1
  restore_clipboard=1
  paste_mods="CTRL"
  paste_key="V"
  enter_key="Return"
  while [[ $# -gt 0 ]]; do
    case "$1" in
    --text)
      text="${2:?missing text}"
      shift 2
      ;;
    --text-file)
      text_file="${2:?missing text file}"
      shift 2
      ;;
    --enter)
      do_enter=1
      shift
      ;;
    --paste-mods)
      paste_mods="${2:?missing paste mods}"
      shift 2
      ;;
    --paste-key)
      paste_key="${2:?missing paste key}"
      shift 2
      ;;
    --enter-key)
      enter_key="${2:?missing enter key}"
      shift 2
      ;;
    --no-focus)
      do_focus=0
      shift
      ;;
    --no-restore-clipboard)
      restore_clipboard=0
      shift
      ;;
    *)
      echo "unknown arg: $1" >&2
      exit 2
      ;;
    esac
  done
  if [[ -n $text && -n $text_file ]]; then
    echo "paste accepts either --text or --text-file, not both" >&2
    exit 2
  fi
  if [[ -z $text && -z $text_file ]]; then
    echo "paste requires --text or --text-file" >&2
    exit 2
  fi
  if [[ -n $text_file ]]; then
    [[ -f $text_file ]] || {
      echo "text file not found: $text_file" >&2
      exit 2
    }
  fi

  clipboard_backup=""
  cleanup() {
    if [[ -n $clipboard_backup && -f $clipboard_backup ]]; then
      wl-copy <"$clipboard_backup"
      rm -f "$clipboard_backup"
    fi
  }
  trap cleanup EXIT

  if [[ $restore_clipboard -eq 1 ]]; then
    if wl-paste --list-types 2>/dev/null | rg -qx 'text/plain(;charset=utf-8)?'; then
      clipboard_backup="$(mktemp)"
      wl-paste --no-newline >"$clipboard_backup" || rm -f "$clipboard_backup"
    fi
  fi

  if [[ -n $text_file ]]; then
    wl-copy <"$text_file"
  else
    printf '%s' "$text" | wl-copy
  fi

  if [[ $do_focus -eq 1 ]]; then
    hyprctl dispatch focuswindow "$window"
    sleep 0.15
  fi

  send_shortcut "$paste_mods" "$paste_key" "$window"
  if [[ $do_enter -eq 1 ]]; then
    sleep 0.05
    send_shortcut "" "$enter_key" "$window"
  fi
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
