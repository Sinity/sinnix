#!/usr/bin/env bash
set -euo pipefail

# Keyboard input automation via wtype (Wayland virtual keyboard protocol).
# Falls back to clipboard+shortcut paste for windows that can't receive wtype directly.
#
# wtype must be installed (currently in /nix/store, add to systemPackages or PATH).
# Without wtype, use the paste fallback which requires wl-copy/wl-paste.

usage() {
  cat <<'USAGE'
Usage: keyboard-control.sh <command> [options]

Commands:
  type --text <text> [--delay-ms <n>] [--window <hyprctl-address>]
      Type text into the currently focused window (or a specific window).
      Uses wtype if available, falls back to clipboard paste.
      NOTE: wtype requires compositor support (zwp_virtual_keyboard_manager_v1).

  key --key <keyname> [--mod <mod1> ...] [--window <hyprctl-address>]
      Press and release a named key (XKB keysym, e.g., Return, Escape, Tab, Left, Right).

  shortcut --mod <mod1> ... --key <keyname> [--window <hyprctl-address>]
      Send a keyboard shortcut (e.g., Ctrl+C, Super+T).
      Uses hyprctl sendshortcut for Wayland apps, wtype for terminal fallback.

  press --key <keyname> [--mod <mod1> ...]
      Press and hold a key (use release to let go).

  release --key <keyname> [--mod <mod1> ...]
      Release a held key.

  status
      Check keyboard control tool availability.

Examples:
  keyboard-control.sh type --text 'hello world'
  keyboard-control.sh key --key Escape
  keyboard-control.sh shortcut --mod ctrl --key c
  keyboard-control.sh shortcut --mod ctrl shift --key t --window 'class:^(kitty)$'
  keyboard-control.sh status
USAGE
}

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "missing dependency: $1" >&2
    exit 1
  }
}

find_wtype() {
  # Try PATH first, then known nix store location
  if command -v wtype >/dev/null 2>&1; then
    echo "wtype"
    return 0
  fi
  local store_wtype
  store_wtype=$(ls -1 /nix/store/*-wtype-*/bin/wtype 2>/dev/null | head -1)
  if [[ -n $store_wtype && -x $store_wtype ]]; then
    echo "$store_wtype"
    return 0
  fi
  return 1
}

# Common XKB key name aliases
resolve_keyname() {
  local name="$1"
  case "${name,,}" in
  enter | return) echo "Return" ;;
  esc | escape) echo "Escape" ;;
  tab) echo "Tab" ;;
  backspace | bs) echo "BackSpace" ;;
  delete | del) echo "Delete" ;;
  space) echo "space" ;;
  left) echo "Left" ;;
  right) echo "Right" ;;
  up) echo "Up" ;;
  down) echo "Down" ;;
  home) echo "Home" ;;
  end) echo "End" ;;
  pageup | pgup) echo "Page_Up" ;;
  pagedown | pgdn) echo "Page_Down" ;;
  insert | ins) echo "Insert" ;;
  f[0-9] | F[0-9]) echo "${name^}" ;;
  *) echo "$name" ;;
  esac
}

# ── Commands ───────────────────────────────────────────────────────────

cmd="${1:-}"
shift || true

case "$cmd" in
status)
  echo "=== Keyboard Control Status ==="
  echo -n "wtype:           "
  if wt=$(find_wtype 2>/dev/null); then
    echo "available ($wt)"
  else
    echo "MISSING (install nixpkgs#wtype)"
  fi
  echo -n "wl-copy:         "
  command -v wl-copy >/dev/null 2>&1 && echo "available" || echo "MISSING"
  echo -n "wl-paste:        "
  command -v wl-paste >/dev/null 2>&1 && echo "available" || echo "MISSING"
  echo -n "hyprctl:         "
  command -v hyprctl >/dev/null 2>&1 && echo "available" || echo "MISSING"
  echo -n "compositor VKBD: "
  if command -v hyprctl >/dev/null 2>&1; then
    # Check if zwp_virtual_keyboard_manager_v1 is supported
    echo "check via runtime test"
  else
    echo "unknown"
  fi
  echo ""
  echo "Capability: via wtype (direct input) or fallback (clipboard paste+shortcut)"
  ;;

type)
  text=""
  delay_ms=""
  window=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
    --text)
      text="${2:?missing text}"
      shift 2
      ;;
    --delay-ms)
      delay_ms="${2:?missing delay}"
      shift 2
      ;;
    --window)
      window="${2:?missing window}"
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

  if [[ -n $window ]]; then
    hyprctl dispatch focuswindow "$window"
    sleep 0.1
  fi

  if wt=$(find_wtype 2>/dev/null); then
    wtype_args=()
    if [[ -n $delay_ms ]]; then
      wtype_args+=(-d "$delay_ms")
    fi
    echo -n "$text" | "$wt" "${wtype_args[@]}" -
  else
    # Fallback: clipboard paste via hyprctl
    need_cmd wl-copy
    need_cmd wl-paste
    need_cmd hyprctl
    need_cmd jq

    win_addr=$(hyprctl -j activewindow | jq -r '.address // ""')
    printf '%s' "$text" | wl-copy
    sleep 0.05
    hyprctl dispatch sendshortcut "CTRL, V, $win_addr"
    echo "typed via clipboard paste (wtype not available)"
  fi
  ;;

key)
  keyname=""
  mods=()
  window=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
    --key)
      keyname="${2:?missing key}"
      shift 2
      ;;
    --mod)
      mods+=("${2:?missing mod}")
      shift 2
      ;;
    --window)
      window="${2:?missing window}"
      shift 2
      ;;
    *)
      echo "unknown arg: $1" >&2
      exit 2
      ;;
    esac
  done
  [[ -n $keyname ]] || {
    echo "key requires --key" >&2
    exit 2
  }
  keyname=$(resolve_keyname "$keyname")

  if [[ -n $window ]]; then
    hyprctl dispatch focuswindow "$window"
    sleep 0.1
  fi

  if wt=$(find_wtype 2>/dev/null); then
    args=()
    for m in "${mods[@]}"; do
      args+=(-M "${m,,}")
    done
    args+=(-k "$keyname")
    for m in "${mods[@]}"; do
      args+=(-m "${m,,}")
    done
    "$wt" "${args[@]}"
  else
    # Fallback via hyprctl sendshortcut is only reliable for single-key
    need_cmd hyprctl
    need_cmd jq
    combined_mods=""
    for m in "${mods[@]}"; do
      combined_mods="${combined_mods}${m^^}, "
    done
    combined_mods="${combined_mods}${keyname}"
    win_addr=$(hyprctl -j activewindow | jq -r '.address // ""')
    hyprctl dispatch sendshortcut "$combined_mods, $win_addr"
  fi
  ;;

shortcut)
  mods=()
  keyname=""
  window=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
    --mod)
      mods+=("${2:?missing mod}")
      shift 2
      ;;
    --key)
      keyname="${2:?missing key}"
      shift 2
      ;;
    --window)
      window="${2:?missing window}"
      shift 2
      ;;
    *)
      echo "unknown arg: $1" >&2
      exit 2
      ;;
    esac
  done
  [[ -n $keyname && ${#mods[@]} -gt 0 ]] || {
    echo "shortcut requires --mod and --key" >&2
    exit 2
  }
  keyname=$(resolve_keyname "$keyname")

  if [[ -n $window ]]; then
    hyprctl dispatch focuswindow "$window"
    sleep 0.1
  fi

  if wt=$(find_wtype 2>/dev/null); then
    args=()
    for m in "${mods[@]}"; do
      args+=(-M "${m,,}")
    done
    args+=(-k "$keyname")
    for m in "${mods[@]}"; do
      args+=(-m "${m,,}")
    done
    "$wt" "${args[@]}"
  else
    need_cmd hyprctl
    need_cmd jq
    payload=""
    for m in "${mods[@]}"; do
      payload="${payload}${m^^}, "
    done
    payload="${payload}${keyname}"
    win_addr=$(hyprctl -j activewindow | jq -r '.address // ""')
    hyprctl dispatch sendshortcut "$payload, $win_addr"
  fi
  ;;

press)
  keyname=""
  mods=()
  while [[ $# -gt 0 ]]; do
    case "$1" in
    --key)
      keyname="${2:?missing key}"
      shift 2
      ;;
    --mod)
      mods+=("${2:?missing mod}")
      shift 2
      ;;
    *)
      echo "unknown arg: $1" >&2
      exit 2
      ;;
    esac
  done
  [[ -n $keyname ]] || {
    echo "press requires --key" >&2
    exit 2
  }
  keyname=$(resolve_keyname "$keyname")

  if wt=$(find_wtype 2>/dev/null); then
    args=()
    for m in "${mods[@]}"; do
      args+=(-M "${m,,}")
    done
    args+=(-P "$keyname")
    "$wt" "${args[@]}"
  else
    echo "press/release requires wtype; not available" >&2
    exit 1
  fi
  ;;

release)
  keyname=""
  mods=()
  while [[ $# -gt 0 ]]; do
    case "$1" in
    --key)
      keyname="${2:?missing key}"
      shift 2
      ;;
    --mod)
      mods+=("${2:?missing mod}")
      shift 2
      ;;
    *)
      echo "unknown arg: $1" >&2
      exit 2
      ;;
    esac
  done
  [[ -n $keyname ]] || {
    echo "release requires --key" >&2
    exit 2
  }
  keyname=$(resolve_keyname "$keyname")

  if wt=$(find_wtype 2>/dev/null); then
    args=()
    args+=(-p "$keyname")
    for m in "${mods[@]}"; do
      args+=(-m "${m,,}")
    done
    "$wt" "${args[@]}"
  else
    echo "press/release requires wtype; not available" >&2
    exit 1
  fi
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
