#!/usr/bin/env bash
set -euo pipefail

socket="${KITTY_LISTEN_ON:-}"
raw_json=0
proc_root="${SINNIX_KITTY_PROC_ROOT:-/proc}"

usage() {
  cat <<'USAGE'
Usage: kitty-remote-control.sh [--to SOCKET] <command> [options]

Commands:
  list [--json]
  focus --match <expr>
  launch-agent-here --agent <codex|claude|gemini|hermes>
  send --match <expr> --text <text> [--enter] [--bracketed-paste]
  run --match <expr> --command <command>
  key --match <expr> --keys <key1> [key2 ...]
  capture --match <expr> [--extent screen|all|selection|last_cmd_output|last_non_empty_output] [--ansi] [--out file]
  await --match <expr> --pattern <regex> [--timeout-sec <n>] [--interval-sec <n>] [--extent <extent>] [--ansi] [--out file]
  send-await --match <expr> --text <text> --pattern <regex> [--enter] [--bracketed-paste] [--timeout-sec <n>] [--interval-sec <n>] [--extent <extent>] [--ansi] [--out file]

Examples:
  kitty-remote-control.sh list
  kitty-remote-control.sh send --match 'title:Codex' --text 'status' --enter
  kitty-remote-control.sh capture --match 'title:Codex' --extent all --out /tmp/codex.txt
  kitty-remote-control.sh await --match 'title:Codex' --pattern 'done|completed' --timeout-sec 60
USAGE
}

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "missing dependency: $1" >&2
    exit 1
  }
}

need_cmd kitty

run_kitty() {
  if [[ -n $socket ]]; then
    kitty @ --to "$socket" "$@"
  else
    kitty @ "$@"
  fi
}

poll_for_pattern() {
  local match="$1"
  local pattern="$2"
  local timeout_sec="$3"
  local interval_sec="$4"
  local extent="$5"
  local ansi="$6"
  local out_file="$7"
  local deadline now captured

  deadline=$(($(date +%s) + timeout_sec))
  while :; do
    local -a args=(get-text --match "$match" --extent "$extent")
    if [[ $ansi -eq 1 ]]; then
      args+=(--ansi)
    fi
    captured="$(run_kitty "${args[@]}" 2>/dev/null || true)"
    if printf '%s\n' "$captured" | grep -Eq -- "$pattern"; then
      if [[ -n $out_file ]]; then
        mkdir -p "$(dirname "$out_file")"
        printf '%s\n' "$captured" >"$out_file"
      fi
      printf '%s\n' "$captured"
      return 0
    fi
    now="$(date +%s)"
    if ((now >= deadline)); then
      if [[ -n $out_file ]]; then
        mkdir -p "$(dirname "$out_file")"
        printf '%s\n' "$captured" >"$out_file"
      fi
      return 124
    fi
    sleep "$interval_sec"
  done
}

proc_start_time() {
  local pid="$1"
  [[ -r "$proc_root/$pid/stat" ]] || return 1
  awk '{print $22}' "$proc_root/$pid/stat"
}

is_descendant_of() {
  local child="$1"
  local ancestor="$2"
  local parent

  for _ in {1..32}; do
    [[ $child == "$ancestor" ]] && return 0
    parent="$(ps -o ppid= -p "$child" 2>/dev/null | tr -d ' ')"
    [[ $parent =~ ^[0-9]+$ && $parent != 1 ]] || return 1
    child="$parent"
  done
  return 1
}

notify_agent_fallback() {
  local cwd="$1"
  local reason="$2"
  if command -v notify-send >/dev/null 2>&1; then
    notify-send -t 2500 "Agent launch fallback" "$reason. Starting in $cwd."
  fi
}

launch_agent_here() {
  local agent=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
    --agent)
      agent="${2:?missing agent}"
      shift 2
      ;;
    *)
      echo "launch-agent-here: unknown arg: $1" >&2
      exit 2
      ;;
    esac
  done

  local command_path
  case "$agent" in
  codex) command_path="$HOME/.local/bin/codex" ;;
  claude) command_path="$HOME/.local/bin/claude-lean" ;;
  gemini) command_path="$HOME/.local/bin/gemini" ;;
  hermes) command_path="$HOME/.local/bin/hermes" ;;
  *)
    echo "launch-agent-here: agent must be codex, claude, gemini, or hermes" >&2
    exit 2
    ;;
  esac

  local fallback_cwd="${SINNIX_AGENT_FALLBACK_CWD:-${SINNIX_PROJECT_ROOT:-/realm/project/sinnix}}"
  [[ -d $fallback_cwd ]] || fallback_cwd="$HOME"
  local active_json active_class kitty_pid runtime_dir socket_path kitty_json focused_json foreground_json
  local foreground_pid foreground_cwd kitty_start foreground_start proc_cwd
  active_json="$(hyprctl -j activewindow 2>/dev/null || true)"
  active_class="$(printf '%s' "$active_json" | jq -r '.class // ""')"
  kitty_pid="$(printf '%s' "$active_json" | jq -r '.pid // 0')"
  runtime_dir="${XDG_RUNTIME_DIR:-/run/user/$UID}"
  socket_path="$runtime_dir/kitty-${USER:-$(id -u)}-$kitty_pid"

  if [[ $active_class != kitty || ! $kitty_pid =~ ^[0-9]+$ || $kitty_pid == 0 || ! -S $socket_path ]]; then
    notify_agent_fallback "$fallback_cwd" "focused window is not a resolvable Kitty window"
    uwsm app -- kitty --directory "$fallback_cwd" "$command_path" >/dev/null 2>&1 &
    return 0
  fi

  socket="unix:$socket_path"
  kitty_start="$(proc_start_time "$kitty_pid" || true)"
  kitty_json="$(kitty @ --to "$socket" ls 2>/dev/null || true)"
  focused_json="$(printf '%s' "$kitty_json" | jq -c '[.[] | select(.is_focused == true) | .tabs[]? | select(.is_focused == true) | .windows[]? | select(.is_focused == true)][0] // empty')"
  foreground_json="$(printf '%s' "$focused_json" | jq -c '(.foreground_processes // [])[-1] // empty')"
  foreground_pid="$(printf '%s' "$foreground_json" | jq -r '.pid // 0')"
  foreground_cwd="$(printf '%s' "$foreground_json" | jq -r '.cwd // empty')"
  foreground_start="$(proc_start_time "$foreground_pid" || true)"

  if [[ -z $kitty_start || -z $focused_json || ! $foreground_pid =~ ^[0-9]+$ || $foreground_pid == 0 || -z $foreground_start || -z $foreground_cwd ]] || ! is_descendant_of "$foreground_pid" "$kitty_pid"; then
    notify_agent_fallback "$fallback_cwd" "focused Kitty process identity could not be verified"
    uwsm app -- kitty --directory "$fallback_cwd" "$command_path" >/dev/null 2>&1 &
    return 0
  fi

  proc_cwd="$(readlink -f "$proc_root/$foreground_pid/cwd" 2>/dev/null || true)"
  if [[ -z $proc_cwd || ! -d $proc_cwd ]]; then
    notify_agent_fallback "$fallback_cwd" "focused Kitty cwd could not be verified"
    uwsm app -- kitty --directory "$fallback_cwd" "$command_path" >/dev/null 2>&1 &
    return 0
  fi

  run_kitty launch --type os-window --cwd "$proc_cwd" --keep-focus "$command_path"
}

if [[ $# -lt 1 ]]; then
  usage >&2
  exit 2
fi

if [[ $1 == "--to" ]]; then
  socket="${2:?missing socket}"
  shift 2
fi

cmd="${1:-}"
shift || true

case "$cmd" in
launch-agent-here)
  launch_agent_here "$@"
  ;;
list)
  if [[ ${1:-} == "--json" ]]; then
    raw_json=1
    shift
  fi
  data="$(run_kitty ls)"
  if [[ $raw_json -eq 1 ]]; then
    printf '%s\n' "$data"
    exit 0
  fi
  need_cmd jq
  echo "$data" | jq -r '
      .[] as $os
      | ($os.tabs[]? // empty) as $tab
      | ($tab.windows[]? // empty)
      | [
          (.id|tostring),
          ($tab.id|tostring),
          ($os.id|tostring),
          (.title // ""),
          (.cwd // "")
        ]
      | @tsv
    ' | awk 'BEGIN{print "WIN_ID\tTAB_ID\tOS_WIN\tTITLE\tCWD"} {print}'
  ;;

focus)
  match=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
    --match)
      match="${2:?missing match}"
      shift 2
      ;;
    *)
      echo "unknown arg: $1" >&2
      exit 2
      ;;
    esac
  done
  [[ -n $match ]] || {
    echo "focus requires --match" >&2
    exit 2
  }
  run_kitty focus-window --match "$match"
  ;;

send)
  match=""
  text=""
  add_enter=0
  bracketed=0
  while [[ $# -gt 0 ]]; do
    case "$1" in
    --match)
      match="${2:?missing match}"
      shift 2
      ;;
    --text)
      text="${2:?missing text}"
      shift 2
      ;;
    --enter)
      add_enter=1
      shift
      ;;
    --bracketed-paste)
      bracketed=1
      shift
      ;;
    *)
      echo "unknown arg: $1" >&2
      exit 2
      ;;
    esac
  done
  [[ -n $match && -n $text ]] || {
    echo "send requires --match and --text" >&2
    exit 2
  }
  args=(send-text --match "$match")
  if [[ $bracketed -eq 1 ]]; then
    args+=(--bracketed-paste enable)
  fi
  args+=("$text")
  run_kitty "${args[@]}"
  if [[ $add_enter -eq 1 ]]; then
    run_kitty send-key --match "$match" enter
  fi
  ;;

run)
  match=""
  command_text=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
    --match)
      match="${2:?missing match}"
      shift 2
      ;;
    --command)
      command_text="${2:?missing command}"
      shift 2
      ;;
    *)
      echo "unknown arg: $1" >&2
      exit 2
      ;;
    esac
  done
  [[ -n $match && -n $command_text ]] || {
    echo "run requires --match and --command" >&2
    exit 2
  }
  run_kitty send-text --match "$match" "$command_text"
  run_kitty send-key --match "$match" enter
  ;;

key)
  match=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
    --match)
      match="${2:?missing match}"
      shift 2
      ;;
    --keys)
      shift
      break
      ;;
    *)
      echo "unknown arg: $1" >&2
      exit 2
      ;;
    esac
  done
  [[ -n $match ]] || {
    echo "key requires --match" >&2
    exit 2
  }
  [[ $# -ge 1 ]] || {
    echo "key requires at least one key after --keys" >&2
    exit 2
  }
  run_kitty send-key --match "$match" "$@"
  ;;

capture)
  match=""
  extent="screen"
  ansi=0
  out_file=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
    --match)
      match="${2:?missing match}"
      shift 2
      ;;
    --extent)
      extent="${2:?missing extent}"
      shift 2
      ;;
    --ansi)
      ansi=1
      shift
      ;;
    --out)
      out_file="${2:?missing out file}"
      shift 2
      ;;
    *)
      echo "unknown arg: $1" >&2
      exit 2
      ;;
    esac
  done
  [[ -n $match ]] || {
    echo "capture requires --match" >&2
    exit 2
  }
  args=(get-text --match "$match" --extent "$extent")
  if [[ $ansi -eq 1 ]]; then
    args+=(--ansi)
  fi
  captured="$(run_kitty "${args[@]}")"
  if [[ -n $out_file ]]; then
    mkdir -p "$(dirname "$out_file")"
    printf '%s\n' "$captured" >"$out_file"
  else
    printf '%s\n' "$captured"
  fi
  ;;

await)
  match=""
  pattern=""
  timeout_sec=30
  interval_sec=0.5
  extent="all"
  ansi=0
  out_file=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
    --match)
      match="${2:?missing match}"
      shift 2
      ;;
    --pattern)
      pattern="${2:?missing pattern}"
      shift 2
      ;;
    --timeout-sec)
      timeout_sec="${2:?missing timeout}"
      shift 2
      ;;
    --interval-sec)
      interval_sec="${2:?missing interval}"
      shift 2
      ;;
    --extent)
      extent="${2:?missing extent}"
      shift 2
      ;;
    --ansi)
      ansi=1
      shift
      ;;
    --out)
      out_file="${2:?missing out file}"
      shift 2
      ;;
    *)
      echo "unknown arg: $1" >&2
      exit 2
      ;;
    esac
  done
  [[ -n $match && -n $pattern ]] || {
    echo "await requires --match and --pattern" >&2
    exit 2
  }
  if ! poll_for_pattern "$match" "$pattern" "$timeout_sec" "$interval_sec" "$extent" "$ansi" "$out_file"; then
    echo "await timed out after ${timeout_sec}s (pattern not observed)" >&2
    exit 124
  fi
  ;;

send-await)
  match=""
  text=""
  pattern=""
  add_enter=0
  bracketed=0
  timeout_sec=30
  interval_sec=0.5
  extent="last_cmd_output"
  ansi=0
  out_file=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
    --match)
      match="${2:?missing match}"
      shift 2
      ;;
    --text)
      text="${2:?missing text}"
      shift 2
      ;;
    --pattern)
      pattern="${2:?missing pattern}"
      shift 2
      ;;
    --enter)
      add_enter=1
      shift
      ;;
    --bracketed-paste)
      bracketed=1
      shift
      ;;
    --timeout-sec)
      timeout_sec="${2:?missing timeout}"
      shift 2
      ;;
    --interval-sec)
      interval_sec="${2:?missing interval}"
      shift 2
      ;;
    --extent)
      extent="${2:?missing extent}"
      shift 2
      ;;
    --ansi)
      ansi=1
      shift
      ;;
    --out)
      out_file="${2:?missing out file}"
      shift 2
      ;;
    *)
      echo "unknown arg: $1" >&2
      exit 2
      ;;
    esac
  done
  [[ -n $match && -n $text && -n $pattern ]] || {
    echo "send-await requires --match, --text, and --pattern" >&2
    exit 2
  }
  args=(send-text --match "$match")
  if [[ $bracketed -eq 1 ]]; then
    args+=(--bracketed-paste enable)
  fi
  args+=("$text")
  run_kitty "${args[@]}"
  if [[ $add_enter -eq 1 ]]; then
    run_kitty send-key --match "$match" enter
  fi
  if ! poll_for_pattern "$match" "$pattern" "$timeout_sec" "$interval_sec" "$extent" "$ansi" "$out_file"; then
    echo "send-await timed out after ${timeout_sec}s (pattern not observed)" >&2
    exit 124
  fi
  ;;

-h | --help | help)
  usage
  ;;

*)
  echo "unknown command: $cmd" >&2
  usage >&2
  exit 2
  ;;
esac
