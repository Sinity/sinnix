#!/usr/bin/env bash
set -euo pipefail

socket="${KITTY_LISTEN_ON:-}"

usage() {
  cat <<'USAGE'
Usage: codex_instance_control.sh [--to SOCKET] <command> [options]

Commands:
  list [--regex <pattern>] [--json]
  self [--regex <pattern>] [--json]
  send (--match <expr> | --self [--self-regex <pattern>]) --text <text> [--enter]
  exec (--match <expr> | --self [--self-regex <pattern>]) --command <shell_cmd> [--timeout-sec <n>] [--interval-sec <n>]
  wait (--match <expr> | --self [--self-regex <pattern>]) --pattern <regex> [--timeout-sec <n>] [--interval-sec <n>] [--extent <extent>]
  batch (--match <expr> | --self [--self-regex <pattern>]) --file <commands.txt> [--timeout-sec <n>]
  kill (--match <expr> | --self [--self-regex <pattern>]) [--mode interrupt|close]
USAGE
}

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "missing dependency: $1" >&2
    exit 1
  }
}

need_cmd kitty
need_cmd jq

run_kitty() {
  if [[ -n $socket ]]; then
    kitty @ --to "$socket" "$@"
  else
    kitty @ "$@"
  fi
}

flatten_windows_json() {
  local data
  data="$(run_kitty ls)"
  printf '%s' "$data" | jq '
    [ .[] as $os
      | ($os.tabs[]? // empty) as $tab
      | ($tab.windows[]? // empty)
      | {
          window_id: .id,
          tab_id: $tab.id,
          os_window_id: $os.id,
          title: (.title // ""),
          cwd: (.cwd // ""),
          pid: (.pid // null)
        }
    ]'
}

resolve_self_match() {
  local regex="$1"
  local windows current_id pwd_abs id
  windows="$(flatten_windows_json)"
  current_id="${KITTY_WINDOW_ID:-}"
  pwd_abs="$(pwd -P 2>/dev/null || pwd)"

  if [[ -n $current_id ]]; then
    id="$(printf '%s' "$windows" | jq -r --argjson id "$current_id" '
      (map(select(.window_id == $id)) | .[0].window_id) // empty
    ')"
    if [[ -n $id ]]; then
      printf 'id:%s\n' "$id"
      return 0
    fi
  fi

  # Prefer codex-like title in current working directory if unique.
  id="$(printf '%s' "$windows" | jq -r --arg r "$regex" --arg p "$pwd_abs" '
    (map(select(((.title // "") | test($r; "i")) and (.cwd == $p))) | if length == 1 then .[0].window_id else empty end)
  ')"
  if [[ -n $id ]]; then
    printf 'id:%s\n' "$id"
    return 0
  fi

  # Fallback to single codex-like window.
  id="$(printf '%s' "$windows" | jq -r --arg r "$regex" '
    (map(select((.title // "") | test($r; "i"))) | if length == 1 then .[0].window_id else empty end)
  ')"
  if [[ -n $id ]]; then
    printf 'id:%s\n' "$id"
    return 0
  fi

  echo "could not resolve --self target unambiguously" >&2
  echo "hint: pass --match explicitly, or tighten --self-regex" >&2
  echo "candidate windows:" >&2
  printf '%s\n' "$windows" | jq -r '.[] | [(.window_id|tostring), .title, .cwd] | @tsv' >&2
  return 1
}

poll_pattern() {
  local match="$1" pattern="$2" timeout_sec="$3" interval_sec="$4" extent="$5"
  local deadline now captured
  deadline=$(($(date +%s) + timeout_sec))
  while :; do
    captured="$(run_kitty get-text --match "$match" --extent "$extent" 2>/dev/null || true)"
    if printf '%s\n' "$captured" | grep -Eq -- "$pattern"; then
      printf '%s\n' "$captured"
      return 0
    fi
    now="$(date +%s)"
    if ((now >= deadline)); then
      return 124
    fi
    sleep "$interval_sec"
  done
}

if [[ $# -lt 1 ]]; then
  usage >&2
  exit 2
fi

if [[ ${1:-} == "--to" ]]; then
  socket="${2:?missing socket}"
  shift 2
fi

cmd="${1:-}"
shift || true

case "$cmd" in
list)
  regex='[Cc]odex'
  emit_json=0
  while [[ $# -gt 0 ]]; do
    case "$1" in
    --regex)
      regex="${2:?missing regex}"
      shift 2
      ;;
    --json)
      emit_json=1
      shift
      ;;
    *)
      echo "unknown arg: $1" >&2
      exit 2
      ;;
    esac
  done
  data="$(run_kitty ls)"
  filtered="$(printf '%s' "$data" | jq --arg r "$regex" '
      [ .[] as $os
        | ($os.tabs[]? // empty) as $tab
        | ($tab.windows[]? // empty)
        | select(((.title // "") | test($r; "i")))
        | {
            window_id: .id,
            tab_id: $tab.id,
            os_window_id: $os.id,
            title: (.title // ""),
            cwd: (.cwd // "")
          }
      ]
    ')"
  if [[ $emit_json -eq 1 ]]; then
    printf '%s\n' "$filtered"
  else
    printf '%s\n' "$filtered" | jq -r '.[] | [(.window_id|tostring), (.tab_id|tostring), (.os_window_id|tostring), .title, .cwd] | @tsv' | awk 'BEGIN{print "WIN_ID\tTAB_ID\tOS_WIN\tTITLE\tCWD"} {print}'
  fi
  ;;

self)
  regex='[Cc]odex'
  emit_json=0
  while [[ $# -gt 0 ]]; do
    case "$1" in
    --regex)
      regex="${2:?missing regex}"
      shift 2
      ;;
    --json)
      emit_json=1
      shift
      ;;
    *)
      echo "unknown arg: $1" >&2
      exit 2
      ;;
    esac
  done
  match="$(resolve_self_match "$regex")"
  wid="${match#id:}"
  windows="$(flatten_windows_json)"
  selected="$(printf '%s' "$windows" | jq --argjson id "$wid" '
      map(select(.window_id == $id)) | .[0]
    ')"
  if [[ $emit_json -eq 1 ]]; then
    jq -n --arg match "$match" --argjson selected "$selected" '{match: $match, selected: $selected}'
  else
    echo "MATCH=$match"
    printf '%s\n' "$selected" | jq -r '[.window_id, .tab_id, .os_window_id, .title, .cwd] | @tsv' | awk 'BEGIN{print "WIN_ID\tTAB_ID\tOS_WIN\tTITLE\tCWD"} {print}'
  fi
  ;;

send)
  match=""
  use_self=0
  self_regex='[Cc]odex'
  text=""
  add_enter=0
  while [[ $# -gt 0 ]]; do
    case "$1" in
    --match)
      match="${2:?missing match}"
      shift 2
      ;;
    --self)
      use_self=1
      shift
      ;;
    --self-regex)
      self_regex="${2:?missing self regex}"
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
    *)
      echo "unknown arg: $1" >&2
      exit 2
      ;;
    esac
  done
  if [[ $use_self -eq 1 ]]; then
    match="$(resolve_self_match "$self_regex")"
  fi
  [[ -n $match && -n $text ]] || {
    echo "send requires --match and --text" >&2
    exit 2
  }
  run_kitty send-text --match "$match" "$text"
  if [[ $add_enter -eq 1 ]]; then
    run_kitty send-key --match "$match" enter
  fi
  ;;

exec)
  match=""
  use_self=0
  self_regex='[Cc]odex'
  shell_cmd=""
  timeout_sec=120
  interval_sec=0.5
  while [[ $# -gt 0 ]]; do
    case "$1" in
    --match)
      match="${2:?missing match}"
      shift 2
      ;;
    --self)
      use_self=1
      shift
      ;;
    --self-regex)
      self_regex="${2:?missing self regex}"
      shift 2
      ;;
    --command)
      shell_cmd="${2:?missing command}"
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
    *)
      echo "unknown arg: $1" >&2
      exit 2
      ;;
    esac
  done
  if [[ $use_self -eq 1 ]]; then
    match="$(resolve_self_match "$self_regex")"
  fi
  [[ -n $match && -n $shell_cmd ]] || {
    echo "exec requires --match and --command" >&2
    exit 2
  }
  sentinel="__CODEX_DONE_$(date +%s%N)__"
  run_kitty send-text --match "$match" "$shell_cmd; printf '%s\\n' '$sentinel'"
  run_kitty send-key --match "$match" enter
  if ! poll_pattern "$match" "^$sentinel$" "$timeout_sec" "$interval_sec" "last_cmd_output"; then
    echo "exec timed out waiting for sentinel" >&2
    exit 124
  fi
  ;;

wait)
  match=""
  use_self=0
  self_regex='[Cc]odex'
  pattern=""
  timeout_sec=120
  interval_sec=0.5
  extent="last_cmd_output"
  while [[ $# -gt 0 ]]; do
    case "$1" in
    --match)
      match="${2:?missing match}"
      shift 2
      ;;
    --self)
      use_self=1
      shift
      ;;
    --self-regex)
      self_regex="${2:?missing self regex}"
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
    *)
      echo "unknown arg: $1" >&2
      exit 2
      ;;
    esac
  done
  if [[ $use_self -eq 1 ]]; then
    match="$(resolve_self_match "$self_regex")"
  fi
  [[ -n $match && -n $pattern ]] || {
    echo "wait requires --match and --pattern" >&2
    exit 2
  }
  if ! poll_pattern "$match" "$pattern" "$timeout_sec" "$interval_sec" "$extent"; then
    echo "wait timed out" >&2
    exit 124
  fi
  ;;

batch)
  match=""
  use_self=0
  self_regex='[Cc]odex'
  file=""
  timeout_sec=120
  while [[ $# -gt 0 ]]; do
    case "$1" in
    --match)
      match="${2:?missing match}"
      shift 2
      ;;
    --self)
      use_self=1
      shift
      ;;
    --self-regex)
      self_regex="${2:?missing self regex}"
      shift 2
      ;;
    --file)
      file="${2:?missing file}"
      shift 2
      ;;
    --timeout-sec)
      timeout_sec="${2:?missing timeout}"
      shift 2
      ;;
    *)
      echo "unknown arg: $1" >&2
      exit 2
      ;;
    esac
  done
  if [[ $use_self -eq 1 ]]; then
    match="$(resolve_self_match "$self_regex")"
  fi
  [[ -n $match && -n $file ]] || {
    echo "batch requires --match and --file" >&2
    exit 2
  }
  [[ -f $file ]] || {
    echo "file not found: $file" >&2
    exit 1
  }
  while IFS= read -r line || [[ -n $line ]]; do
    [[ -z $line || $line =~ ^[[:space:]]*# ]] && continue
    "$0" ${socket:+--to "$socket"} exec --match "$match" --command "$line" --timeout-sec "$timeout_sec"
  done <"$file"
  ;;

kill)
  match=""
  use_self=0
  self_regex='[Cc]odex'
  mode="close"
  while [[ $# -gt 0 ]]; do
    case "$1" in
    --match)
      match="${2:?missing match}"
      shift 2
      ;;
    --self)
      use_self=1
      shift
      ;;
    --self-regex)
      self_regex="${2:?missing self regex}"
      shift 2
      ;;
    --mode)
      mode="${2:?missing mode}"
      shift 2
      ;;
    *)
      echo "unknown arg: $1" >&2
      exit 2
      ;;
    esac
  done
  if [[ $use_self -eq 1 ]]; then
    match="$(resolve_self_match "$self_regex")"
  fi
  [[ -n $match ]] || {
    echo "kill requires --match or --self" >&2
    exit 2
  }
  case "$mode" in
  interrupt)
    run_kitty send-key --match "$match" ctrl+c
    ;;
  close)
    run_kitty close-window --match "$match"
    ;;
  *)
    echo "invalid --mode: $mode (expected interrupt|close)" >&2
    exit 2
    ;;
  esac
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
