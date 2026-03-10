#!/usr/bin/env zsh

if [[ -z ${ZSH_VERSION:-} ]]; then
  return 0 2>/dev/null || exit 0
fi

if [[ -z ${SINNIX_ASCIINEMA_ACTIVE:-} ]]; then
  return 0
fi

if [[ -n ${SINNIX_CAPTURE_HOOKED:-} ]]; then
  return 0
fi

if [[ -z ${SINNIX_CAPTURE_SESSION_FILE:-} || -z ${SINNIX_CAPTURE_EVENTS_FILE:-} ]]; then
  return 0
fi

export SINNIX_CAPTURE_HOOKED=1

autoload -Uz add-zsh-hook
zmodload zsh/datetime 2>/dev/null || true

typeset -gi SINNIX_CAPTURE_ACTIVE_MS=0
typeset -gi SINNIX_CAPTURE_IDLE_MS=0
typeset -gi SINNIX_CAPTURE_EVENT_COUNT=0
typeset -gi SINNIX_CAPTURE_COMMAND_COUNT=0
typeset -g SINNIX_CAPTURE_LAST_PROMPT_MS="${SINNIX_CAPTURE_STARTED_AT_MS:-0}"
typeset -g SINNIX_CAPTURE_LAST_COMMAND_MS=""

_sinnix_capture_now_ms() {
  local raw="${EPOCHREALTIME:-0}"
  local sec="${raw%%.*}"
  local frac="${raw#*.}"

  if [[ "$frac" == "$raw" ]]; then
    frac="0"
  fi

  frac="${frac}000"
  print -r -- "${sec}${frac[1,3]}"
}

_sinnix_capture_guess_project_root() {
  local cwd="$1"
  if [[ "$cwd" == /realm/project/* ]]; then
    local suffix="${cwd#/realm/project/}"
    local name="${suffix%%/*}"
    if [[ -n "$name" ]]; then
      print -r -- "/realm/project/$name"
      return 0
    fi
  fi
  print -r -- ""
}

_sinnix_capture_json_escape() {
  local value="$1"
  value=${value//\\/\\\\}
  value=${value//\"/\\\"}
  value=${value//$'\n'/\\n}
  value=${value//$'\r'/\\r}
  value=${value//$'\t'/\\t}
  print -nr -- "$value"
}

_sinnix_capture_json_string() {
  print -nr -- '"'
  _sinnix_capture_json_escape "$1"
  print -nr -- '"'
}

_sinnix_capture_json_nullable_string() {
  if [[ -n "$1" ]]; then
    _sinnix_capture_json_string "$1"
  else
    print -nr -- 'null'
  fi
}

_sinnix_capture_json_nullable_int() {
  if [[ -n "$1" ]]; then
    print -nr -- "$1"
  else
    print -nr -- 'null'
  fi
}

_sinnix_capture_find_repo_root() {
  local dir="${1:A}"

  while [[ -n "$dir" && "$dir" != "/" ]]; do
    if [[ -d "$dir/.git" || -f "$dir/.git" ]]; then
      print -r -- "$dir"
      return 0
    fi
    dir="${dir:h}"
  done

  return 1
}

_sinnix_capture_repo_branch() {
  local repo_root="$1"

  if [[ -z "$repo_root" ]] || ! command -v git >/dev/null 2>&1; then
    return 0
  fi

  git -C "$repo_root" symbolic-ref --quiet --short HEAD 2>/dev/null \
    || git -C "$repo_root" rev-parse --short HEAD 2>/dev/null \
    || true
}

_sinnix_capture_append_prefix() {
  local type="$1"
  local ts_ms="$2"
  print -nr -- '{"type":'
  _sinnix_capture_json_string "$type"
  print -nr -- ',"ts_ms":'
  print -nr -- "$ts_ms"
}

_sinnix_capture_append_session_start() {
  local ts_ms="$(_sinnix_capture_now_ms)"
  local project_root="${SINNIX_CAPTURE_PROJECT_ROOT:-${SINNIX_CAPTURE_START_REPO_ROOT:-}}"

  {
    _sinnix_capture_append_prefix "session_start" "$ts_ms"
    print -nr -- ',"cwd":'
    _sinnix_capture_json_nullable_string "${SINNIX_CAPTURE_START_CWD:-$PWD}"
    print -nr -- ',"project_root":'
    _sinnix_capture_json_nullable_string "$project_root"
    print -nr -- ',"repo_root":'
    _sinnix_capture_json_nullable_string "${SINNIX_CAPTURE_START_REPO_ROOT:-}"
    print -nr -- ',"tty":'
    _sinnix_capture_json_nullable_string "${SINNIX_CAPTURE_TTY:-}"
    print -nr -- ',"terminal":'
    _sinnix_capture_json_nullable_string "${SINNIX_CAPTURE_TERMINAL:-}"
    print -r -- '}'
  } >>| "$SINNIX_CAPTURE_EVENTS_FILE"

  SINNIX_CAPTURE_EVENT_COUNT=$((SINNIX_CAPTURE_EVENT_COUNT + 1))
}

_sinnix_capture_append_command_start() {
  local ts_ms="$1"
  local cmd="$2"
  local cwd="$3"
  local repo_root="$4"
  local project_root="$5"

  {
    _sinnix_capture_append_prefix "command_start" "$ts_ms"
    print -nr -- ',"command":'
    _sinnix_capture_json_string "$cmd"
    print -nr -- ',"cwd":'
    _sinnix_capture_json_nullable_string "$cwd"
    print -nr -- ',"project_root":'
    _sinnix_capture_json_nullable_string "$project_root"
    print -nr -- ',"repo_root":'
    _sinnix_capture_json_nullable_string "$repo_root"
    print -r -- '}'
  } >>| "$SINNIX_CAPTURE_EVENTS_FILE"

  SINNIX_CAPTURE_EVENT_COUNT=$((SINNIX_CAPTURE_EVENT_COUNT + 1))
}

_sinnix_capture_append_command_end() {
  local ts_ms="$1"
  local exit_code="$2"
  local duration_ms="$3"

  {
    _sinnix_capture_append_prefix "command_end" "$ts_ms"
    print -nr -- ',"exit_code":'
    _sinnix_capture_json_nullable_int "$exit_code"
    print -nr -- ',"duration_ms":'
    _sinnix_capture_json_nullable_int "$duration_ms"
    print -r -- '}'
  } >>| "$SINNIX_CAPTURE_EVENTS_FILE"

  SINNIX_CAPTURE_EVENT_COUNT=$((SINNIX_CAPTURE_EVENT_COUNT + 1))
}

_sinnix_capture_append_session_end() {
  local ts_ms="$1"
  local exit_code="$2"
  local exit_reason="$3"
  local final_cwd="$4"
  local final_project_root="$5"
  local final_repo_root="$6"

  {
    _sinnix_capture_append_prefix "session_end" "$ts_ms"
    print -nr -- ',"exit_code":'
    _sinnix_capture_json_nullable_int "$exit_code"
    print -nr -- ',"exit_reason":'
    _sinnix_capture_json_string "$exit_reason"
    print -nr -- ',"cwd":'
    _sinnix_capture_json_nullable_string "$final_cwd"
    print -nr -- ',"project_root":'
    _sinnix_capture_json_nullable_string "$final_project_root"
    print -nr -- ',"repo_root":'
    _sinnix_capture_json_nullable_string "$final_repo_root"
    print -nr -- ',"active_ms":'
    _sinnix_capture_json_nullable_int "$SINNIX_CAPTURE_ACTIVE_MS"
    print -nr -- ',"idle_ms":'
    _sinnix_capture_json_nullable_int "$SINNIX_CAPTURE_IDLE_MS"
    print -r -- '}'
  } >>| "$SINNIX_CAPTURE_EVENTS_FILE"

  SINNIX_CAPTURE_EVENT_COUNT=$((SINNIX_CAPTURE_EVENT_COUNT + 1))
}

_sinnix_capture_write_session_file() {
  local finished_at_ms="$1"
  local exit_code="$2"
  local exit_reason="$3"
  local final_cwd="$4"
  local final_repo_root="$5"
  local repo_branch="$6"
  local project_root="${SINNIX_CAPTURE_PROJECT_ROOT:-${SINNIX_CAPTURE_START_REPO_ROOT:-}}"
  local final_project_root="$(_sinnix_capture_guess_project_root "$final_cwd")"
  local duration_ms=""

  if [[ -n "$finished_at_ms" && -n ${SINNIX_CAPTURE_STARTED_AT_MS:-} ]]; then
    duration_ms=$((finished_at_ms - SINNIX_CAPTURE_STARTED_AT_MS))
  fi

  {
    print -r -- "{"
    print -nr -- '  "schema": '; _sinnix_capture_json_string "terminal-session-v1"; print -r -- ","
    print -nr -- '  "schema_generation": '; _sinnix_capture_json_string "terminal-session-v1"; print -r -- ","
    print -nr -- '  "session_id": '; _sinnix_capture_json_nullable_string "${SINNIX_CAPTURE_SESSION_ID:-}"; print -r -- ","
    print -nr -- '  "cast_path": '; _sinnix_capture_json_nullable_string "${SINNIX_ASCIINEMA_FILE:-}"; print -r -- ","
    print -nr -- '  "events_path": '; _sinnix_capture_json_nullable_string "${SINNIX_CAPTURE_EVENTS_FILE:-}"; print -r -- ","
    print -nr -- '  "host": '; _sinnix_capture_json_nullable_string "${SINNIX_CAPTURE_HOST:-}"; print -r -- ","
    print -nr -- '  "user": '; _sinnix_capture_json_nullable_string "${SINNIX_CAPTURE_USER:-}"; print -r -- ","
    print -nr -- '  "tty": '; _sinnix_capture_json_nullable_string "${SINNIX_CAPTURE_TTY:-}"; print -r -- ","
    print -nr -- '  "terminal": '; _sinnix_capture_json_nullable_string "${SINNIX_CAPTURE_TERMINAL:-}"; print -r -- ","
    print -nr -- '  "shell": '; _sinnix_capture_json_nullable_string "${SINNIX_CAPTURE_SHELL:-}"; print -r -- ","
    print -nr -- '  "term_type": '; _sinnix_capture_json_nullable_string "${SINNIX_CAPTURE_TERM_TYPE:-}"; print -r -- ","
    print -nr -- '  "start_cwd": '; _sinnix_capture_json_nullable_string "${SINNIX_CAPTURE_START_CWD:-}"; print -r -- ","
    print -nr -- '  "final_cwd": '; _sinnix_capture_json_nullable_string "$final_cwd"; print -r -- ","
    print -nr -- '  "project_root": '; _sinnix_capture_json_nullable_string "$project_root"; print -r -- ","
    print -nr -- '  "final_project_root": '; _sinnix_capture_json_nullable_string "$final_project_root"; print -r -- ","
    print -nr -- '  "repo_root": '; _sinnix_capture_json_nullable_string "${SINNIX_CAPTURE_START_REPO_ROOT:-}"; print -r -- ","
    print -nr -- '  "final_repo_root": '; _sinnix_capture_json_nullable_string "$final_repo_root"; print -r -- ","
    print -nr -- '  "repo_branch": '; _sinnix_capture_json_nullable_string "$repo_branch"; print -r -- ","
    print -nr -- '  "started_at_ms": '; _sinnix_capture_json_nullable_int "${SINNIX_CAPTURE_STARTED_AT_MS:-}"; print -r -- ","
    print -nr -- '  "finished_at_ms": '; _sinnix_capture_json_nullable_int "$finished_at_ms"; print -r -- ","
    print -nr -- '  "duration_ms": '; _sinnix_capture_json_nullable_int "$duration_ms"; print -r -- ","
    print -nr -- '  "active_ms": '; _sinnix_capture_json_nullable_int "$SINNIX_CAPTURE_ACTIVE_MS"; print -r -- ","
    print -nr -- '  "idle_ms": '; _sinnix_capture_json_nullable_int "$SINNIX_CAPTURE_IDLE_MS"; print -r -- ","
    print -nr -- '  "command_count": '; _sinnix_capture_json_nullable_int "$SINNIX_CAPTURE_COMMAND_COUNT"; print -r -- ","
    print -nr -- '  "event_count": '; _sinnix_capture_json_nullable_int "$SINNIX_CAPTURE_EVENT_COUNT"; print -r -- ","
    print -nr -- '  "exit_code": '; _sinnix_capture_json_nullable_int "$exit_code"; print -r -- ","
    print -nr -- '  "exit_reason": '; _sinnix_capture_json_string "$exit_reason"; print
    print -r -- "}"
  } >| "$SINNIX_CAPTURE_SESSION_FILE"
}

_sinnix_capture_preexec() {
  local now_ms="$(_sinnix_capture_now_ms)"
  local cwd="$PWD"
  local repo_root="$(_sinnix_capture_find_repo_root "$cwd" || true)"
  local project_root="$(_sinnix_capture_guess_project_root "$cwd")"

  if [[ -n ${SINNIX_CAPTURE_LAST_PROMPT_MS:-} ]]; then
    SINNIX_CAPTURE_IDLE_MS=$((SINNIX_CAPTURE_IDLE_MS + now_ms - SINNIX_CAPTURE_LAST_PROMPT_MS))
  fi

  SINNIX_CAPTURE_LAST_COMMAND_MS="$now_ms"
  SINNIX_CAPTURE_COMMAND_COUNT=$((SINNIX_CAPTURE_COMMAND_COUNT + 1))

  _sinnix_capture_append_command_start "$now_ms" "$1" "$cwd" "$repo_root" "$project_root"
}

_sinnix_capture_precmd() {
  local exit_code=$?
  local now_ms="$(_sinnix_capture_now_ms)"

  if [[ -n ${SINNIX_CAPTURE_LAST_COMMAND_MS:-} ]]; then
    local duration_ms=$((now_ms - SINNIX_CAPTURE_LAST_COMMAND_MS))
    SINNIX_CAPTURE_ACTIVE_MS=$((SINNIX_CAPTURE_ACTIVE_MS + duration_ms))
    _sinnix_capture_append_command_end "$now_ms" "$exit_code" "$duration_ms"
    SINNIX_CAPTURE_LAST_COMMAND_MS=""
  fi

  SINNIX_CAPTURE_LAST_PROMPT_MS="$now_ms"
}

_sinnix_capture_zshexit() {
  local exit_code=$?
  local now_ms="$(_sinnix_capture_now_ms)"
  local final_cwd="$PWD"
  local final_repo_root="$(_sinnix_capture_find_repo_root "$final_cwd" || true)"
  local final_project_root="$(_sinnix_capture_guess_project_root "$final_cwd")"
  local repo_branch="$(_sinnix_capture_repo_branch "$final_repo_root")"
  local exit_reason="shell_exit"

  if (( exit_code >= 128 )); then
    exit_reason="signal"
  fi

  if [[ -n ${SINNIX_CAPTURE_LAST_COMMAND_MS:-} ]]; then
    SINNIX_CAPTURE_ACTIVE_MS=$((SINNIX_CAPTURE_ACTIVE_MS + now_ms - SINNIX_CAPTURE_LAST_COMMAND_MS))
    SINNIX_CAPTURE_LAST_COMMAND_MS=""
  elif [[ -n ${SINNIX_CAPTURE_LAST_PROMPT_MS:-} ]]; then
    SINNIX_CAPTURE_IDLE_MS=$((SINNIX_CAPTURE_IDLE_MS + now_ms - SINNIX_CAPTURE_LAST_PROMPT_MS))
  fi

  _sinnix_capture_append_session_end "$now_ms" "$exit_code" "$exit_reason" "$final_cwd" "$final_project_root" "$final_repo_root"
  _sinnix_capture_write_session_file "$now_ms" "$exit_code" "$exit_reason" "$final_cwd" "$final_repo_root" "$repo_branch"
}

touch "$SINNIX_CAPTURE_EVENTS_FILE"
_sinnix_capture_append_session_start
_sinnix_capture_write_session_file "" "" "running" "${SINNIX_CAPTURE_START_CWD:-$PWD}" "${SINNIX_CAPTURE_START_REPO_ROOT:-}" ""

add-zsh-hook preexec _sinnix_capture_preexec
add-zsh-hook precmd _sinnix_capture_precmd
add-zsh-hook zshexit _sinnix_capture_zshexit
