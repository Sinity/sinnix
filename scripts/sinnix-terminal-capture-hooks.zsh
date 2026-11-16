#!/usr/bin/env zsh
# @sinnix-package: skip

if [[ -z ${ZSH_VERSION:-} ]]; then
  return 0 2>/dev/null || exit 0
fi

if [[ -z ${SINNIX_CAPTURE_ACTIVE:-} ]]; then
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
zmodload zsh/system 2>/dev/null || true

typeset -gi SINNIX_CAPTURE_ACTIVE_MS=0
typeset -gi SINNIX_CAPTURE_IDLE_MS=0
typeset -gi SINNIX_CAPTURE_EVENT_COUNT=0
typeset -gi SINNIX_CAPTURE_COMMAND_COUNT=0
typeset -g SINNIX_CAPTURE_LAST_PROMPT_MS="${SINNIX_CAPTURE_STARTED_AT_MS:-0}"
typeset -g SINNIX_CAPTURE_LAST_COMMAND_MS=""
# Write end of the session writer's pipe. While it is set, this shell writes
# event lines there and touches neither the capture directory nor git, so a
# stalled disk cannot hold a prompt. Empty means this shell writes the files
# itself, as it does when no session writer is reading.
typeset -g _sinnix_capture_events_fd=""
typeset -gi _sinnix_capture_direct=0
typeset -g _sinnix_capture_line=""

# The helpers below return in REPLY: a command substitution would fork on
# every prompt.

_sinnix_capture_now_ms() {
  local raw="${EPOCHREALTIME:-0}"
  raw="${raw//,/.}"
  local sec="${raw%%.*}"
  local frac="${raw#*.}"

  if [[ "$frac" == "$raw" ]]; then
    frac="0"
  fi

  frac="${frac}000"
  REPLY="${sec}${frac[1,3]}"
}

_sinnix_capture_guess_project_root() {
  local cwd="$1"
  REPLY=""
  if [[ "$cwd" == /realm/project/* ]]; then
    local suffix="${cwd#/realm/project/}"
    local name="${suffix%%/*}"
    if [[ -n "$name" ]]; then
      REPLY="/realm/project/$name/repo"
    fi
  fi
}

_sinnix_capture_json_string() {
  local value="$1"
  value=${value//\\/\\\\}
  value=${value//\"/\\\"}
  # JSON requires every non-NUL ASCII control byte to be escaped. Shell
  # arguments cannot contain NUL; decoding preserves these control values.
  if [[ "$value" == *[$'\x01'-$'\x1f']* ]]; then
    local code hex control
    for code in {1..31}; do
      printf -v hex '%02x' "$code"
      printf -v control '%b' "\\x$hex"
      value=${value//"$control"/"\\u00$hex"}
    done
  fi
  REPLY="\"$value\""
}

_sinnix_capture_json_nullable_string() {
  if [[ -n "$1" ]]; then
    _sinnix_capture_json_string "$1"
  else
    REPLY='null'
  fi
}

_sinnix_capture_find_repo_root() {
  local dir="${1:A}"
  REPLY=""

  while [[ -n "$dir" && "$dir" != "/" ]]; do
    if [[ -d "$dir/.git" || -f "$dir/.git" ]]; then
      REPLY="$dir"
      return 0
    fi
    dir="${dir:h}"
  done
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

_sinnix_capture_repo_commit() {
  local repo_root="$1"

  if [[ -z "$repo_root" ]] || ! command -v git >/dev/null 2>&1; then
    return 0
  fi

  git -C "$repo_root" rev-parse HEAD 2>/dev/null || true
}

_sinnix_capture_repo_dirty() {
  local repo_root="$1"

  if [[ -z "$repo_root" ]] || ! command -v git >/dev/null 2>&1; then
    return 0
  fi

  if [[ -n "$(git -C "$repo_root" status --porcelain --ignore-submodules=dirty 2>/dev/null)" ]]; then
    print -r -- "true"
  else
    print -r -- "false"
  fi
}

# An event line is built in _sinnix_capture_line and recorded with
# _sinnix_capture_emit.

_sinnix_capture_begin() {
  _sinnix_capture_line="{\"type\":\"$1\",\"ts_ms\":$2"
}

_sinnix_capture_add_string() {
  _sinnix_capture_json_nullable_string "$2"
  _sinnix_capture_line+=",\"$1\":$REPLY"
}

_sinnix_capture_add_int() {
  _sinnix_capture_line+=",\"$1\":${2:-null}"
}

_sinnix_capture_open_events_pipe() {
  local pipe="${SINNIX_CAPTURE_EVENTS_PIPE:-}"
  local fd

  [[ -n "$pipe" ]] || return 1
  # Opening an anonymous pipe through /proc neither waits for a reader nor
  # fails without one; a missing reader shows at the first write.
  sysopen -w -o cloexec -u fd "$pipe" 2>/dev/null || return 1
  _sinnix_capture_events_fd="$fd"
}

# Hand the line to the session writer. Fails once no reader holds the pipe.
_sinnix_capture_send() {
  [[ -n "$_sinnix_capture_events_fd" ]] || return 1
  setopt localoptions localtraps
  # A write to a pipe whose reader died must fail here, not kill the shell.
  trap '' PIPE
  if print -r -u "$_sinnix_capture_events_fd" -- "$_sinnix_capture_line" 2>/dev/null; then
    return 0
  fi
  exec {_sinnix_capture_events_fd}>&-
  _sinnix_capture_events_fd=""
  return 1
}

# Take over the files the session writer would have written: the directory
# and the start-of-session repository state now, the session record at exit.
_sinnix_capture_write_files_directly() {
  local start_repo_root="${SINNIX_CAPTURE_START_REPO_ROOT:-}"

  _sinnix_capture_direct=1
  ( umask 077; mkdir -p -- "${SINNIX_CAPTURE_SESSION_FILE:h}" ) 2>/dev/null
  typeset -g SINNIX_CAPTURE_START_REPO_BRANCH="$(_sinnix_capture_repo_branch "$start_repo_root")"
  typeset -g SINNIX_CAPTURE_START_REPO_COMMIT="$(_sinnix_capture_repo_commit "$start_repo_root")"
  typeset -g SINNIX_CAPTURE_START_REPO_DIRTY="$(_sinnix_capture_repo_dirty "$start_repo_root")"
}

_sinnix_capture_emit() {
  if ! _sinnix_capture_send; then
    (( _sinnix_capture_direct )) || _sinnix_capture_write_files_directly
    (
      umask 077
      print -r -- "$_sinnix_capture_line" >>| "$SINNIX_CAPTURE_EVENTS_FILE"
    )
  fi
  SINNIX_CAPTURE_EVENT_COUNT=$((SINNIX_CAPTURE_EVENT_COUNT + 1))
}

_sinnix_capture_build_session_start() {
  local project_root="${SINNIX_CAPTURE_PROJECT_ROOT:-${SINNIX_CAPTURE_START_REPO_ROOT:-}}"

  _sinnix_capture_now_ms
  _sinnix_capture_begin "session_start" "$REPLY"
  _sinnix_capture_add_string cwd "${SINNIX_CAPTURE_START_CWD:-$PWD}"
  _sinnix_capture_add_string project_root "$project_root"
  _sinnix_capture_add_string repo_root "${SINNIX_CAPTURE_START_REPO_ROOT:-}"
  # Null through the pipe: the session writer fills these in.
  _sinnix_capture_add_string repo_branch "${SINNIX_CAPTURE_START_REPO_BRANCH:-}"
  _sinnix_capture_add_string repo_commit "${SINNIX_CAPTURE_START_REPO_COMMIT:-}"
  _sinnix_capture_add_string repo_dirty "${SINNIX_CAPTURE_START_REPO_DIRTY:-}"
  _sinnix_capture_add_string tty "${SINNIX_CAPTURE_TTY:-}"
  _sinnix_capture_add_string terminal "${SINNIX_CAPTURE_TERMINAL:-}"
  _sinnix_capture_line+="}"
}

_sinnix_capture_build_session_end() {
  local ts_ms="$1"
  local exit_code="$2"
  local exit_reason="$3"
  local final_cwd="$4"
  local final_project_root="$5"
  local final_repo_root="$6"
  local final_repo_branch="$7"
  local final_repo_commit="$8"
  local final_repo_dirty="$9"

  _sinnix_capture_begin "session_end" "$ts_ms"
  _sinnix_capture_add_int exit_code "$exit_code"
  _sinnix_capture_add_string exit_reason "$exit_reason"
  _sinnix_capture_add_string cwd "$final_cwd"
  _sinnix_capture_add_string project_root "$final_project_root"
  _sinnix_capture_add_string repo_root "$final_repo_root"
  _sinnix_capture_add_string repo_branch "$final_repo_branch"
  _sinnix_capture_add_string repo_commit "$final_repo_commit"
  _sinnix_capture_add_string repo_dirty "$final_repo_dirty"
  _sinnix_capture_add_int active_ms "$SINNIX_CAPTURE_ACTIVE_MS"
  _sinnix_capture_add_int idle_ms "$SINNIX_CAPTURE_IDLE_MS"
  _sinnix_capture_line+="}"
}

# Only used while this shell writes the files itself.
_sinnix_capture_write_session_file() {
  local finished_at_ms="$1"
  local exit_code="$2"
  local exit_reason="$3"
  local final_cwd="$4"
  local final_repo_root="$5"
  local final_repo_branch="$6"
  local final_repo_commit="$7"
  local final_repo_dirty="$8"
  local project_root="${SINNIX_CAPTURE_PROJECT_ROOT:-${SINNIX_CAPTURE_START_REPO_ROOT:-}}"
  local duration_ms=""

  _sinnix_capture_guess_project_root "$final_cwd"
  local final_project_root="$REPLY"

  if [[ -n "$finished_at_ms" && -n ${SINNIX_CAPTURE_STARTED_AT_MS:-} ]]; then
    duration_ms=$((finished_at_ms - SINNIX_CAPTURE_STARTED_AT_MS))
  fi

  # kind (s: nullable string, i: nullable integer), key, value
  local -a fields=(
    s schema "terminal-session-v1"
    s schema_generation "terminal-session-v1"
    s session_id "${SINNIX_CAPTURE_SESSION_ID:-}"
    s cast_path "${SINNIX_CAPTURE_CAST_FILE:-}"
    s events_path "${SINNIX_CAPTURE_EVENTS_FILE:-}"
    s host "${SINNIX_CAPTURE_HOST:-}"
    s user "${SINNIX_CAPTURE_USER:-}"
    s tty "${SINNIX_CAPTURE_TTY:-}"
    s terminal "${SINNIX_CAPTURE_TERMINAL:-}"
    s shell "${SINNIX_CAPTURE_SHELL:-}"
    s term_type "${SINNIX_CAPTURE_TERM_TYPE:-}"
    s start_cwd "${SINNIX_CAPTURE_START_CWD:-}"
    s final_cwd "$final_cwd"
    s project_root "$project_root"
    s final_project_root "$final_project_root"
    s repo_root "${SINNIX_CAPTURE_START_REPO_ROOT:-}"
    s final_repo_root "$final_repo_root"
    s repo_branch "${SINNIX_CAPTURE_START_REPO_BRANCH:-}"
    s final_repo_branch "$final_repo_branch"
    s repo_commit "${SINNIX_CAPTURE_START_REPO_COMMIT:-}"
    s final_repo_commit "$final_repo_commit"
    s repo_dirty "${SINNIX_CAPTURE_START_REPO_DIRTY:-}"
    s final_repo_dirty "$final_repo_dirty"
    i started_at_ms "${SINNIX_CAPTURE_STARTED_AT_MS:-}"
    i finished_at_ms "$finished_at_ms"
    i duration_ms "$duration_ms"
    i active_ms "$SINNIX_CAPTURE_ACTIVE_MS"
    i idle_ms "$SINNIX_CAPTURE_IDLE_MS"
    i command_count "$SINNIX_CAPTURE_COMMAND_COUNT"
    i event_count "$SINNIX_CAPTURE_EVENT_COUNT"
    i exit_code "$exit_code"
    s exit_reason "$exit_reason"
  )
  local kind key value
  local -a rows=()
  for kind key value in "${fields[@]}"; do
    if [[ "$kind" == s ]]; then
      _sinnix_capture_json_nullable_string "$value"
    else
      REPLY="${value:-null}"
    fi
    rows+=("  \"$key\": $REPLY")
  done

  (
    umask 077
    print -r -- "{"$'\n'"${(pj:,\n:)rows}"$'\n'"}" >| "$SINNIX_CAPTURE_SESSION_FILE"
  )
}

_sinnix_capture_preexec() {
  _sinnix_capture_now_ms
  local now_ms="$REPLY"
  local cwd="$PWD"
  _sinnix_capture_find_repo_root "$cwd"
  local repo_root="$REPLY"
  _sinnix_capture_guess_project_root "$cwd"
  local project_root="$REPLY"

  if [[ -n ${SINNIX_CAPTURE_LAST_PROMPT_MS:-} ]]; then
    SINNIX_CAPTURE_IDLE_MS=$((SINNIX_CAPTURE_IDLE_MS + now_ms - SINNIX_CAPTURE_LAST_PROMPT_MS))
  fi

  SINNIX_CAPTURE_LAST_COMMAND_MS="$now_ms"
  SINNIX_CAPTURE_COMMAND_COUNT=$((SINNIX_CAPTURE_COMMAND_COUNT + 1))

  _sinnix_capture_begin "command_start" "$now_ms"
  _sinnix_capture_json_string "$1"
  _sinnix_capture_line+=",\"command\":$REPLY"
  _sinnix_capture_add_string cwd "$cwd"
  _sinnix_capture_add_string project_root "$project_root"
  _sinnix_capture_add_string repo_root "$repo_root"
  _sinnix_capture_line+="}"
  _sinnix_capture_emit
}

_sinnix_capture_precmd() {
  local exit_code=$?
  _sinnix_capture_now_ms
  local now_ms="$REPLY"

  if [[ -n ${SINNIX_CAPTURE_LAST_COMMAND_MS:-} ]]; then
    local duration_ms=$((now_ms - SINNIX_CAPTURE_LAST_COMMAND_MS))
    SINNIX_CAPTURE_ACTIVE_MS=$((SINNIX_CAPTURE_ACTIVE_MS + duration_ms))
    _sinnix_capture_begin "command_end" "$now_ms"
    _sinnix_capture_add_int exit_code "$exit_code"
    _sinnix_capture_add_int duration_ms "$duration_ms"
    _sinnix_capture_line+="}"
    _sinnix_capture_emit
    SINNIX_CAPTURE_LAST_COMMAND_MS=""
  fi

  SINNIX_CAPTURE_LAST_PROMPT_MS="$now_ms"
}

_sinnix_capture_zshexit() {
  local exit_code=$?
  _sinnix_capture_now_ms
  local now_ms="$REPLY"
  local final_cwd="$PWD"
  _sinnix_capture_find_repo_root "$final_cwd"
  local final_repo_root="$REPLY"
  _sinnix_capture_guess_project_root "$final_cwd"
  local final_project_root="$REPLY"
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

  # Through the pipe the shell leaves at once: the session writer queries the
  # final repository state and rewrites session.json after the shell is gone.
  _sinnix_capture_build_session_end "$now_ms" "$exit_code" "$exit_reason" "$final_cwd" "$final_project_root" "$final_repo_root" "" "" ""
  if _sinnix_capture_send; then
    SINNIX_CAPTURE_EVENT_COUNT=$((SINNIX_CAPTURE_EVENT_COUNT + 1))
    return 0
  fi

  local final_repo_branch="$(_sinnix_capture_repo_branch "$final_repo_root")"
  local final_repo_commit="$(_sinnix_capture_repo_commit "$final_repo_root")"
  local final_repo_dirty="$(_sinnix_capture_repo_dirty "$final_repo_root")"
  _sinnix_capture_build_session_end "$now_ms" "$exit_code" "$exit_reason" "$final_cwd" "$final_project_root" "$final_repo_root" "$final_repo_branch" "$final_repo_commit" "$final_repo_dirty"
  _sinnix_capture_emit
  _sinnix_capture_write_session_file "$now_ms" "$exit_code" "$exit_reason" "$final_cwd" "$final_repo_root" "$final_repo_branch" "$final_repo_commit" "$final_repo_dirty"
}

_sinnix_capture_open_events_pipe
_sinnix_capture_build_session_start
if _sinnix_capture_send; then
  SINNIX_CAPTURE_EVENT_COUNT=$((SINNIX_CAPTURE_EVENT_COUNT + 1))
else
  _sinnix_capture_write_files_directly
  _sinnix_capture_build_session_start
  _sinnix_capture_emit
  _sinnix_capture_write_session_file \
    "" \
    "" \
    "running" \
    "${SINNIX_CAPTURE_START_CWD:-$PWD}" \
    "${SINNIX_CAPTURE_START_REPO_ROOT:-}" \
    "" \
    "" \
    ""
fi

add-zsh-hook preexec _sinnix_capture_preexec
add-zsh-hook precmd _sinnix_capture_precmd
add-zsh-hook zshexit _sinnix_capture_zshexit
