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
  dispatch <lua-dispatcher-expression>
  send-shortcut <mods> <key> [window]
  send-keystate <mods> <key> <down|repeat|up> <window>
  paste <window> [--text <text> | --text-file <path>] [--enter] [--paste-mods <mods>] [--paste-key <key>] [--enter-key <key>] [--no-focus] [--no-restore-clipboard]
  keyword <name> <value>
  batch "<command1 ; command2 ; ...>"
  screenshot-probe
  snapshot                         monitors, workspaces, clients, active window/workspace, cursor; one JSON document
  window <window> <close|float|fullscreen|move X Y|resize W H>
  exec <command>                   spawn a command in the session (hl.dsp.exec_cmd)
  open <uri>                       xdg-open in the session
  type <window> --text <text> [--delay-ms <n>]   focus, then type with wtype
  pointer <move X Y | click [left|right|middle] [--double] | drag X1 Y1 X2 Y2 | scroll DX DY>

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

lua_quote() {
  need_cmd jq
  jq -nr --arg value "$1" '$value | tojson'
}

hypr_dispatch() {
  hyprctl eval "hl.dispatch($1)"
}

focus_window() {
  local window_lua
  window_lua=$(lua_quote "$1")
  hypr_dispatch "hl.dsp.focus({ window = $window_lua })"
}

send_shortcut() {
  local mods="$1"
  local key="$2"
  local window="${3:-}"
  local mods_lua key_lua window_lua args
  mods_lua=$(lua_quote "$mods")
  key_lua=$(lua_quote "$key")
  args="mods = $mods_lua, key = $key_lua"
  if [[ -n $window ]]; then
    window_lua=$(lua_quote "$window")
    args="$args, window = $window_lua"
  fi
  hypr_dispatch "hl.dsp.send_shortcut({ $args })"
}

send_key_state() {
  local mods_lua key_lua state_lua window_lua
  mods_lua=$(lua_quote "$1")
  key_lua=$(lua_quote "$2")
  state_lua=$(lua_quote "$3")
  window_lua=$(lua_quote "$4")
  hypr_dispatch "hl.dsp.send_key_state({ mods = $mods_lua, key = $key_lua, state = $state_lua, window = $window_lua })"
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
  [[ $# -eq 1 ]] || {
    echo "dispatch requires one Lua dispatcher expression" >&2
    exit 2
  }
  hypr_dispatch "$1"
  ;;

focus-window)
  [[ $# -eq 1 ]] || {
    echo "focus-window requires one window selector" >&2
    exit 2
  }
  focus_window "$1"
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
  send_key_state "$1" "$2" "$3" "$4"
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
    focus_window "$window"
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

snapshot)
  need_cmd jq
  jq -n \
    --arg generation "$(date +%s%N)" \
    --argjson monitors "$(hyprctl -j monitors)" \
    --argjson workspaces "$(hyprctl -j workspaces)" \
    --argjson clients "$(hyprctl -j clients)" \
    --argjson active_window "$(hyprctl -j activewindow)" \
    --argjson active_workspace "$(hyprctl -j activeworkspace)" \
    --arg cursor "$(hyprctl cursorpos)" \
    '{
        generation: $generation,
        monitors: $monitors,
        workspaces: $workspaces,
        clients: $clients,
        active_window: (if ($active_window | type) == "object" and ($active_window.address // "") != "" then $active_window else null end),
        active_workspace: $active_workspace,
        cursor: ($cursor | capture("(?<x>-?[0-9]+), (?<y>-?[0-9]+)") | {x: (.x|tonumber), y: (.y|tonumber)})
      }'
  ;;

window)
  [[ $# -ge 2 ]] || {
    echo "window requires a window selector and an operation" >&2
    exit 2
  }
  window_lua=$(lua_quote "$1")
  op="$2"
  shift 2
  case "$op" in
  close) hypr_dispatch "hl.dsp.window.close({ window = $window_lua })" ;;
  float) hypr_dispatch "hl.dsp.window.float({ window = $window_lua })" ;;
  fullscreen) hypr_dispatch "hl.dsp.window.fullscreen({ window = $window_lua })" ;;
  move)
    [[ $# -eq 2 && $1 =~ ^-?[0-9]+$ && $2 =~ ^-?[0-9]+$ ]] || {
      echo "window move requires integer X Y" >&2
      exit 2
    }
    hypr_dispatch "hl.dsp.window.move({ window = $window_lua, x = $1, y = $2 })"
    ;;
  resize)
    [[ $# -eq 2 && $1 =~ ^[0-9]+$ && $2 =~ ^[0-9]+$ ]] || {
      echo "window resize requires integer W H" >&2
      exit 2
    }
    hypr_dispatch "hl.dsp.window.resize({ window = $window_lua, x = $1, y = $2 })"
    ;;
  *)
    echo "unknown window operation: $op" >&2
    exit 2
    ;;
  esac
  ;;

exec)
  [[ $# -ge 1 ]] || {
    echo "exec requires a command" >&2
    exit 2
  }
  hypr_dispatch "hl.dsp.exec_cmd($(lua_quote "$*"))"
  ;;

open)
  [[ $# -eq 1 ]] || {
    echo "open requires one uri" >&2
    exit 2
  }
  hypr_dispatch "hl.dsp.exec_cmd($(lua_quote "xdg-open $(printf '%q' "$1")"))"
  ;;

type)
  need_cmd wtype
  [[ $# -ge 1 ]] || {
    echo "type requires a window selector" >&2
    exit 2
  }
  window="$1"
  shift
  text=""
  delay_ms=0
  while [[ $# -gt 0 ]]; do
    case "$1" in
    --text)
      text="${2?missing text}"
      shift 2
      ;;
    --delay-ms)
      delay_ms="${2:?missing delay}"
      shift 2
      ;;
    *)
      echo "unknown arg: $1" >&2
      exit 2
      ;;
    esac
  done
  [[ -n $text ]] || {
    echo "type requires --text" >&2
    exit 2
  }
  focus_window "$window" >/dev/null
  sleep 0.15
  wtype -d "$delay_ms" -- "$text"
  ;;

pointer)
  need_cmd jq
  [[ $# -ge 1 ]] || {
    echo "pointer requires an operation" >&2
    exit 2
  }
  op="$1"
  shift
  pointer_tool=""
  if command -v ydotool >/dev/null 2>&1; then pointer_tool="ydotool"; fi
  pointer_move() {
    hypr_dispatch "hl.dsp.cursor.move({ x = $1, y = $2 })" >/dev/null
  }
  pointer_button() {
    # ydotool click codes: 0xC0 left, 0xC1 right, 0xC2 middle (press+release)
    local code
    case "$1" in
    left) code=0xC0 ;;
    right) code=0xC1 ;;
    middle) code=0xC2 ;;
    *) code=0xC0 ;;
    esac
    ydotool click "$code"
  }
  require_pointer_tool() {
    if [[ -z $pointer_tool ]]; then
      jq -nc --arg op "$op" '{available: false, operation: $op, reason: "no virtual pointer tool on this host (ydotool); cursor movement only"}'
      exit 0
    fi
  }
  case "$op" in
  move)
    [[ $# -eq 2 && $1 =~ ^-?[0-9]+$ && $2 =~ ^-?[0-9]+$ ]] || {
      echo "pointer move requires integer X Y" >&2
      exit 2
    }
    pointer_move "$1" "$2"
    jq -nc --argjson x "$1" --argjson y "$2" '{available: true, operation: "move", x: $x, y: $y}'
    ;;
  click)
    button="left"
    double=0
    while [[ $# -gt 0 ]]; do
      case "$1" in
      left | right | middle)
        button="$1"
        shift
        ;;
      --double)
        double=1
        shift
        ;;
      *)
        echo "unknown arg: $1" >&2
        exit 2
        ;;
      esac
    done
    require_pointer_tool
    pointer_button "$button"
    if [[ $double -eq 1 ]]; then
      sleep 0.05
      pointer_button "$button"
    fi
    jq -nc --arg button "$button" --argjson double "$double" '{available: true, operation: "click", button: $button, double: ($double == 1)}'
    ;;
  drag)
    [[ $# -eq 4 ]] || {
      echo "pointer drag requires X1 Y1 X2 Y2" >&2
      exit 2
    }
    require_pointer_tool
    pointer_move "$1" "$2"
    ydotool click 0x40
    sleep 0.05
    pointer_move "$3" "$4"
    sleep 0.05
    ydotool click 0x80
    jq -nc '{available: true, operation: "drag"}'
    ;;
  scroll)
    [[ $# -eq 2 && $1 =~ ^-?[0-9]+$ && $2 =~ ^-?[0-9]+$ ]] || {
      echo "pointer scroll requires integer DX DY" >&2
      exit 2
    }
    require_pointer_tool
    ydotool mousemove --wheel -x "$1" -y "$2"
    jq -nc --argjson dx "$1" --argjson dy "$2" '{available: true, operation: "scroll", dx: $dx, dy: $dy}'
    ;;
  *)
    echo "unknown pointer operation: $op" >&2
    exit 2
    ;;
  esac
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
