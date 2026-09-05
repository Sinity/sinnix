#!/usr/bin/env bash
set -euo pipefail

# Chrome DevTools Protocol (CDP) remote control for the operator's Chrome,
# which exposes --remote-debugging-port=9222.
# Uses curl for HTTP endpoints and websocat for WebSocket CDP commands.

# ONE browser: the operator's own Chrome, on the CDP port it already exposes.
#
# There used to be a second, "private" Chrome with its own profile seeded from
# the live one. It is gone, and the reason is the seeding: `private-sync-state`
# only ever populated a MISSING profile, so from the day it was created the
# copy drifted -- rotated cookies went stale, expiring sessions expired, and a
# site the operator logged into afterwards was simply not logged in for the
# agent. "If I am authenticated somewhere, you are too" is not achievable with
# a snapshot; it is only achievable by sharing the profile, which is what this
# does now. Auth is identical because it is the same cookie jar, not a copy of
# one, and there is nothing to re-seed or keep in sync.
#
# Headlessness went with it. Headless Chrome announces itself in its own
# User-Agent ("HeadlessChrome/..."), so a bot check needs no cleverness to spot
# it, and the rest of the headless surface (no GPU-backed WebGL renderer,
# empty navigator.plugins, missing window.chrome) is an arms race that is lost
# by default. A real window in a real browser answers all of it honestly.
#
# What replaces the isolation is a WINDOW, not a profile: `agent-window` opens
# a new browser window and parks it on a hidden Hyprland workspace, so agent
# work neither steals focus nor touches the operator's tabs. F7 brings it into
# view. Blast radius is unchanged in any way that matters -- an agent on this
# machine is already root-equivalent by accepted design and could read the
# cookie database directly.
CDP_HOST="${CDP_HOST:-127.0.0.1}"
CDP_PORT="${CDP_PORT:-9222}"
CDP_BASE="http://${CDP_HOST}:${CDP_PORT}"
# Every command gets a bounded CDP request/response exchange. Bash's native
# `read -t` supplies the deadline, so no separate timeout program is needed.
CDP_RESPONSE_TIMEOUT_SEC="${SINNIX_CDP_TIMEOUT_SEC:-5}"
[[ $CDP_RESPONSE_TIMEOUT_SEC =~ ^[1-9][0-9]*$ ]] || {
  echo "SINNIX_CDP_TIMEOUT_SEC must be a positive integer: ${CDP_RESPONSE_TIMEOUT_SEC}" >&2
  exit 2
}
# Chrome accepts command IDs as signed 32-bit integers. Keep the sequence in
# that range and wrap it, rather than deriving a JSON number from a process ID.
CDP_REQUEST_ID_MAX=2147483647
cdp_request_seq=0

# The inactive named workspace agent windows are parked on, and the key that
# switches to it. A special workspace is an overlay and therefore cannot be
# the isolation boundary: if shown, it obscures every ordinary workspace.
# Must match modules/features/desktop/hyprland/{rules,bindings}.nix.
AGENT_WORKSPACE="${SINNIX_AGENT_BROWSER_WORKSPACE:-agentbrowser}"
AGENT_WORKSPACE_TARGET="name:${AGENT_WORKSPACE}"
SUMMON_BINDING="F7"

usage() {
  cat <<'USAGE'
Usage: sinnix-chrome-control <command> [options]

Drives the operator's own Chrome, so the agent is authenticated wherever the
operator is. Do agent work in an `agent-window`, which is parked on a hidden
workspace (F7 shows it) and leaves the operator's tabs alone.

Commands:
  status                          Probe the browser
  agent-window [--url <url>]      Open a new window and park it on the hidden
                                  agent workspace; prints its page id
  toggle-agent-workspace          Switch to the agent workspace, or back to the
                                  previous workspace when already there
  list [--json]                   List all open pages (id, title, url, type)
  list-tabs [--json]              List only page-type targets
  page-snapshot <page_id> [--max-text <n>] [--max-elements <n>]
                                  JSON: url, title, text, links, forms and interactive
                                  elements tagged with data-sinnix-ref ids for this generation
  key <page_id> --key <Enter|Tab|Escape|...|single char> [--mod ctrl|shift|alt|meta ...]
                                  Press one key through CDP Input.dispatchKeyEvent
  download <page_id> --url <url> --out <file>
                                  Fetch a URL with the page's credentials into a local file (<= 1.5 MB)
  info <page_id>                  Get detailed info for a page
  new-tab [--url <url>] [--background]
                                  Open a new tab without activating it when requested
  close <page_id>                 Close a page/tab
  activate <page_id>              Bring a page to the front
  load-extension --path <dir>      Runtime-load an unpacked extension into the selected browser

  screenshot <page_id> [--format png|jpeg] [--quality 80] [--full-page] [--out <file>]
                                  Take a screenshot of a page via CDP

  network-log <page_id> [--seconds 15] [--filter <regex>]
                                  Stream CDP Network request/response events

  evaluate <page_id> --js <javascript> [--out <file>]
                                  Evaluate JavaScript in a page, return result

  navigate <page_id> --url <url>  Navigate a page to a new URL
  reload <page_id>                Reload a page

  inject-text <page_id> --text <text> [--selector <css>]
                                  Type text into the focused element or a specific selector

  click <page_id> --selector <css>   Click an element matching CSS selector
  get-text <page_id> [--selector <css>]
                                  Get text content of the page or a specific element

  get-html <page_id> [--selector <css>] [--out <file>]
                                  Get inner or outer HTML of page/element

  fill-form <page_id> --selector <css> --value <text>
                                  Set the value of a form field and dispatch input event
  upload-files <page_id> --selector <css> --file <path> [--file <path> ...]
                                  Attach local files to a file input through CDP

  wait-selector <page_id> --selector <css> [--timeout-sec <n>] [--interval-ms <n>]
                                  Wait until an element matching CSS selector exists

  await <page_id> --js <javascript> [--timeout-sec <n>] [--interval-ms <n>]
                                  Poll a JS expression until it returns truthy

Examples:
  sinnix-chrome-control agent-window --url https://example.com
  sinnix-chrome-control list
  sinnix-chrome-control screenshot <id> --out /tmp/page.png
  sinnix-chrome-control evaluate <id> --js 'document.title'
  sinnix-chrome-control new-tab --background --url https://example.com
  sinnix-chrome-control upload-files <id> --selector 'input[type=file]' --file /path/to/report.md
  sinnix-chrome-control fill-form <id> --selector '#search' --value 'my query'
  sinnix-chrome-control click <id> --selector 'button.submit'
  sinnix-chrome-control navigate <id> --url 'https://example.com'
  sinnix-chrome-control load-extension --path /realm/project/polylogue/browser-extension
USAGE
}

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "missing dependency: $1" >&2
    exit 1
  }
}

need_cmd curl
need_cmd jq
need_cmd websocat

while [[ $# -gt 0 ]]; do
  case "$1" in
  --help | -h)
    usage
    exit 0
    ;;
  *)
    break
    ;;
  esac
done

target_status() {
  if curl -fsS --max-time 2 "${CDP_BASE}/json/version" | jq .; then
    return 0
  fi
  echo "unavailable: ${CDP_BASE}" >&2
  return 1
}

# ── CDP WebSocket helpers ──────────────────────────────────────────────

cdp_next_request_id() {
  local -n result="$1"
  ((cdp_request_seq = cdp_request_seq % CDP_REQUEST_ID_MAX + 1))
  result="$cdp_request_seq"
}

cdp_send() {
  local ws_url method params_json request_id request read_fd write_fd cdp_pid response status
  ws_url="$1"
  method="$2"
  params_json="${3:-}"
  [[ -n $params_json ]] || params_json='{}'

  # Each invocation owns a fresh WebSocket, so a bounded positive ID is enough
  # to match its response while ignoring unsolicited protocol events.
  cdp_next_request_id request_id
  request=$(jq -nc --argjson id "$request_id" --arg method "$method" --argjson params "$params_json" \
    '{id: $id, method: $method, params: $params}')

  # exec makes the coprocess PID the transport PID. A timeout can then reap
  # the actual websocket process and its inherited agent-window lock.
  coproc SINNIX_CDP_COMMAND { exec websocat -B 2097152 "$ws_url"; }
  read_fd="${SINNIX_CDP_COMMAND[0]}"
  write_fd="${SINNIX_CDP_COMMAND[1]}"
  cdp_pid="$SINNIX_CDP_COMMAND_PID"

  if ! printf '%s\n' "$request" >&"$write_fd"; then
    echo "failed to send CDP request ${request_id} (${method})" >&2
    exec {write_fd}>&-
    exec {read_fd}<&-
    kill "$cdp_pid" 2>/dev/null || true
    wait "$cdp_pid" 2>/dev/null || true
    return 1
  fi

  if response=$(cdp_read_response "$read_fd" "$request_id" "$method" "$CDP_RESPONSE_TIMEOUT_SEC"); then
    :
  else
    status=$?
    exec {write_fd}>&-
    exec {read_fd}<&-
    kill "$cdp_pid" 2>/dev/null || true
    wait "$cdp_pid" 2>/dev/null || true
    return "$status"
  fi

  exec {write_fd}>&-
  exec {read_fd}<&-
  kill "$cdp_pid" 2>/dev/null || true
  wait "$cdp_pid" 2>/dev/null || true
  printf '%s\n' "$response"
}

cdp_send_with_result() {
  local ws_url method params_json response
  ws_url="$1"
  method="$2"
  params_json="${3:-}"
  [[ -n $params_json ]] || params_json='{}'
  response=$(cdp_send "$ws_url" "$method" "$params_json") || return $?
  if jq -e '.error' >/dev/null 2>&1 <<<"$response"; then
    jq . >&2 <<<"$response"
    return 1
  fi
  jq -r '.result // empty' <<<"$response"
}

cdp_read_response() {
  local fd expected_id method timeout_sec line deadline_us now_us remaining_us remaining_sec
  fd="$1"
  expected_id="$2"
  method="$3"
  timeout_sec="$4"
  now_us=$(cdp_now_us)
  deadline_us=$((now_us + timeout_sec * 1000000))
  while :; do
    now_us=$(cdp_now_us)
    remaining_us=$((deadline_us - now_us))
    if ((remaining_us <= 0)); then
      printf 'timed out waiting for CDP response id %s (%s) after %ss\n' \
        "$expected_id" "$method" "$timeout_sec" >&2
      return 124
    fi
    printf -v remaining_sec '%d.%06d' $((remaining_us / 1000000)) $((remaining_us % 1000000))
    if ! IFS= read -r -t "$remaining_sec" line <&"$fd"; then
      if (($(cdp_now_us) >= deadline_us)); then
        printf 'timed out waiting for CDP response id %s (%s) after %ss\n' \
          "$expected_id" "$method" "$timeout_sec" >&2
        return 124
      fi
      printf 'CDP connection closed while waiting for response id %s (%s)\n' \
        "$expected_id" "$method" >&2
      return 1
    fi
    if jq -e --argjson id "$expected_id" '.id == $id' >/dev/null 2>&1 <<<"$line"; then
      printf '%s\n' "$line"
      return 0
    fi
    printf 'CDP message without matching id while waiting for %s (%s): %s\n' \
      "$expected_id" "$method" "$line" >&2
  done
}

cdp_now_us() {
  # EPOCHREALTIME follows LC_NUMERIC; a comma decimal separator would turn
  # the arithmetic below into a comma expression.
  local LC_ALL=C
  local seconds fraction
  seconds="${EPOCHREALTIME%%.*}"
  fraction="${EPOCHREALTIME#*.}000000"
  fraction="${fraction:0:6}"
  printf '%s\n' "$((10#$seconds * 1000000 + 10#$fraction))"
}

print_cdp_http_response() {
  local response
  response="$1"
  if jq -e . >/dev/null 2>&1 <<<"$response"; then
    jq . <<<"$response"
  else
    printf '%s\n' "$response"
  fi
}

# ── Page lookup ────────────────────────────────────────────────────────

get_ws_url() {
  local page_id="$1"
  curl -fsS --max-time 2 "${CDP_BASE}/json" | jq -r --arg id "$page_id" '.[] | select(.id == $id) | .webSocketDebuggerUrl'
}

get_browser_ws_url() {
  curl -fsS --max-time 2 "${CDP_BASE}/json/version" | jq -r '.webSocketDebuggerUrl // empty'
}

find_target_by_marker() {
  local marker="$1"
  curl -fsS --max-time 2 "${CDP_BASE}/json" | jq -r --arg marker "$marker" '
    [ .[]
      | select((.title // "" | contains($marker)) or (.url // "" | contains($marker)))
      | .id
    ]
    | unique
    | if length == 1 then .[0] else empty end'
}

get_hyprctl_bin() {
  local candidate instances
  candidate=$(command -v hyprctl 2>/dev/null || true)
  for candidate in "$candidate" "/etc/profiles/per-user/$(id -un)/bin/hyprctl" /run/current-system/sw/bin/hyprctl; do
    [[ -n $candidate && -x $candidate ]] || continue
    instances=$(env -u LD_LIBRARY_PATH "$candidate" instances -j 2>/dev/null || printf '[]')
    if jq -e 'length > 0' >/dev/null 2>&1 <<<"$instances"; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done
  return 1
}

hyprctl_call() {
  env -u LD_LIBRARY_PATH "$hyprctl_bin" "$@"
}

hyprland_compositor_state() {
  local active_window active_workspaces
  active_window=$(hyprctl_call activewindow -j 2>/dev/null | jq -c '{address: (.address // null)}')
  active_workspaces=$(hyprctl_call monitors -j 2>/dev/null | jq -c '[.[] | {monitor: .name, workspace: .activeWorkspace.name}]')
  jq -nc --argjson active_window "$active_window" --argjson active_workspaces "$active_workspaces" \
    '{active_window: $active_window, active_workspaces: $active_workspaces}'
}

assert_hyprland_compositor_state() {
  local phase="$1" current_state
  current_state=$(hyprland_compositor_state)
  if [[ $current_state != "$compositor_state_before" ]]; then
    restore_operator_focus_after_failed_agent_window
    current_state=$(hyprland_compositor_state)
  fi
  if [[ $current_state != "$compositor_state_before" ]]; then
    printf 'compositor state changed %s: before=%s after=%s\n' \
      "$phase" "$compositor_state_before" "$current_state" >&2
    return 1
  fi
  if [[ -n $focus_before ]] && ! hyprctl_call clients -j 2>/dev/null | jq -e --arg address "$focus_before" \
    'any(.[]; .address == $address)' >/dev/null; then
    printf 'focused compositor client disappeared %s: address=%s\n' "$phase" "$focus_before" >&2
    return 1
  fi
}

restore_operator_focus_after_failed_agent_window() {
  local current_state current_focus current_workspaces expected_workspaces focus_lua
  [[ -n ${focus_before:-} && -n ${compositor_state_before:-} ]] || return 0
  hyprctl_call clients -j 2>/dev/null | jq -e --arg address "$focus_before" \
    'any(.[]; .address == $address)' >/dev/null || return 0
  current_state=$(hyprland_compositor_state)
  current_focus=$(jq -r '.active_window.address // empty' <<<"$current_state")
  [[ $current_focus != "$focus_before" ]] || return 0
  current_workspaces=$(jq -c '.active_workspaces' <<<"$current_state")
  expected_workspaces=$(jq -c '.active_workspaces' <<<"$compositor_state_before")
  [[ $current_workspaces == "$expected_workspaces" ]] || return 0
  focus_lua=$(lua_quote "address:${focus_before}")
  hyprctl_call eval "hl.dispatch(hl.dsp.focus({ window = $focus_lua }))" >/dev/null
  for _ in {1..10}; do
    current_focus=$(hyprctl_call activewindow -j 2>/dev/null | jq -r '.address // empty')
    [[ $current_focus == "$focus_before" ]] && return 0
    sleep 0.05
  done
}

lua_quote() {
  jq -nr --arg value "$1" '$value | tojson'
}

install_agent_window_rules() {
  local guard_name_lua class_lua workspace_lua rule_lua provider
  provider=$(hyprctl_call -j status | jq -r '.configProvider // empty')
  if [[ $provider == "hyprlang" ]]; then
    hyprctl_call keyword 'windowrule[sinnix-agent-window-guard]:match:class' \
      '^(google-chrome|google-chrome-unstable|chromium-browser|Chromium)$' >/dev/null
    hyprctl_call keyword 'windowrule[sinnix-agent-window-guard]:workspace' \
      "${AGENT_WORKSPACE_TARGET} silent" >/dev/null
    hyprctl_call keyword 'windowrule[sinnix-agent-window-guard]:tile' true >/dev/null
    hyprctl_call keyword 'windowrule[sinnix-agent-window-guard]:no_initial_focus' true >/dev/null
    hyprctl_call keyword 'windowrule[sinnix-agent-window-guard]:focus_on_activate' false >/dev/null
    hyprctl_call keyword 'windowrule[sinnix-agent-window-guard]:suppress_event' \
      'activate activatefocus' >/dev/null
    hyprctl_call keyword 'windowrule[sinnix-agent-window-guard]:enable' true >/dev/null
    compositor_rule_provider="hyprlang"
    compositor_rules_installed="true"
    return 0
  fi
  [[ $provider == "lua" ]] || {
    printf 'unsupported Hyprland config provider: %s\n' "${provider:-unknown}" >&2
    return 1
  }
  guard_name_lua=$(lua_quote "sinnix-agent-window-guard-${BASHPID}")
  class_lua=$(lua_quote '^(google-chrome|google-chrome-unstable|chromium-browser|Chromium)$')
  workspace_lua=$(lua_quote "${AGENT_WORKSPACE_TARGET} silent")
  rule_lua="sinnix_agent_window_guard = hl.window_rule({name = ${guard_name_lua}, match = {initial_class = ${class_lua}}, workspace = ${workspace_lua}, tile = true, no_initial_focus = true, focus_on_activate = false, suppress_event = 'activate activatefocus'})"
  compositor_rule_provider="lua"
  compositor_rules_installed="true"
  hyprctl_call eval "$rule_lua" >/dev/null
}

clear_stale_agent_window_rules() {
  local provider
  provider=$(hyprctl_call -j status | jq -r '.configProvider // empty')
  if [[ $provider == "hyprlang" ]]; then
    hyprctl_call keyword 'windowrule[sinnix-agent-window-guard]:enable' false >/dev/null
  elif [[ $provider == "lua" ]]; then
    hyprctl_call eval 'if sinnix_agent_window_guard ~= nil then sinnix_agent_window_guard:set_enabled(false); sinnix_agent_window_guard = nil end' >/dev/null
  else
    printf 'unsupported Hyprland config provider: %s\n' "${provider:-unknown}" >&2
    return 1
  fi
}

disable_agent_window_rules() {
  [[ ${compositor_rules_installed:-false} == "true" ]] || return 0
  if [[ ${compositor_rule_provider:-} == "hyprlang" ]]; then
    disable_output=$(hyprctl_call keyword 'windowrule[sinnix-agent-window-guard]:enable' false)
  else
    disable_output=$(hyprctl_call eval 'if sinnix_agent_window_guard ~= nil then sinnix_agent_window_guard:set_enabled(false); sinnix_agent_window_guard = nil end')
  fi
  if [[ $disable_output == "ok" || -z $disable_output ]]; then
    compositor_rules_installed="false"
  else
    printf 'failed to disable temporary agent-window compositor rules\n' >&2
    return 1
  fi
}

resolve_page_id() {
  local maybe_id="$1"
  [[ -n $maybe_id ]] || {
    echo "empty page id" >&2
    exit 2
  }
  # If it looks like a full UUID, use it directly
  if [[ $maybe_id =~ ^[A-F0-9]{32}$ ]]; then
    echo "$maybe_id"
    return 0
  fi
  # Otherwise try title match
  curl -s "${CDP_BASE}/json" | jq -r --arg t "$maybe_id" \
    '.[] | select((.title | test($t; "i")) or (.url | test($t; "i"))) | .id' | head -1
}

# ── Commands ───────────────────────────────────────────────────────────

cmd="${1:-}"
shift || true

case "$cmd" in
status)
  target_status
  ;;

# Open a new browser WINDOW and hide it on the agent workspace.
#
# This is the isolation boundary now that the profile is shared: agents work
# in their own window, so they never navigate a tab the operator is reading
# and never take focus. What they DO share is the cookie jar, which is the
# entire point -- the operator's logins are the agent's logins, with nothing
# to sync and nothing to go stale.
#
# The compositor rules are installed before CDP creates the target. The guard
# suppresses activation for a new Chrome client, while the exact initial-title
# rule places only this marker window on the hidden workspace as it maps. This
# closes the activation-before-identification gap: the helper never has to
# focus or move a live client after creation. The whole transaction is
# serialized so concurrent agent markers cannot compete for rule handles or
# stability checks.
agent-window)
  url="about:blank"
  while [[ $# -gt 0 ]]; do
    case "$1" in
    --url)
      url="${2:?missing url}"
      shift 2
      ;;
    *)
      echo "unknown arg: $1" >&2
      exit 2
      ;;
    esac
  done

  ws_url=$(get_browser_ws_url)
  [[ -n $ws_url ]] || {
    echo "browser websocket unavailable: ${CDP_BASE}" >&2
    exit 1
  }
  command -v flock >/dev/null 2>&1 || {
    echo "agent-window requires flock" >&2
    exit 1
  }

  agent_window_runtime_dir="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
  exec {agent_window_lock_fd}>"${agent_window_runtime_dir}/sinnix-chrome-agent-window.lock"
  flock -w 15 "$agent_window_lock_fd" || {
    echo "timed out waiting to create an agent browser window" >&2
    exit 1
  }

  hyprland_available="false"
  focus_before=""
  compositor_state_before=""
  compositor_rules_installed="false"
  hyprctl_bin=$(get_hyprctl_bin || true)
  if [[ -n $hyprctl_bin ]]; then
    hyprland_instances=$(hyprctl_call instances -j 2>/dev/null || printf '[]')
    hyprland_instance_count=$(jq 'length' <<<"$hyprland_instances")
    if [[ $hyprland_instance_count -eq 1 ]]; then
      HYPRLAND_INSTANCE_SIGNATURE=$(jq -r '.[0].instance' <<<"$hyprland_instances")
      export HYPRLAND_INSTANCE_SIGNATURE
    fi
    if [[ -n ${HYPRLAND_INSTANCE_SIGNATURE:-} ]] && hyprctl_call clients -j >/dev/null 2>&1; then
      hyprland_available="true"
      focus_before=$(hyprctl_call activewindow -j 2>/dev/null | jq -r '.address // empty')
      compositor_state_before=$(hyprland_compositor_state)
    fi
  fi
  if [[ $hyprland_available != "true" || -z $focus_before || -z $compositor_state_before ]]; then
    echo "agent-window requires a live Hyprland compositor with a focused operator client; hyprctl=${hyprctl_bin:-unavailable}; instances=${hyprland_instance_count:-unknown}; signature=$([[ -n ${HYPRLAND_INSTANCE_SIGNATURE:-} ]] && printf set || printf missing); focus=${focus_before:-unavailable}" >&2
    exit 1
  fi
  if ! clear_stale_agent_window_rules; then
    echo "failed to clear stale agent-window compositor rules" >&2
    exit 1
  fi
  compositor_state_before=$(hyprland_compositor_state)
  focus_before=$(jq -r '.active_window.address // empty' <<<"$compositor_state_before")
  if [[ -z $focus_before ]]; then
    echo "focused operator client disappeared while clearing stale agent-window rules" >&2
    exit 1
  fi

  marker="sinnix-agent-window-${BASHPID}-${RANDOM}-${RANDOM}"
  marker_url="data:text/html,<title>${marker}</title>"

  page_id=""
  retain_created_target="false"
  close_created_target() {
    if [[ -z $page_id ]]; then
      page_id=$(find_target_by_marker "$marker" || true)
    fi
    [[ -n $page_id ]] || return 0
    close_params=$(jq -nc --arg target_id "$page_id" '{targetId: $target_id}')
    cdp_send "$ws_url" "Target.closeTarget" "$close_params" >/dev/null ||
      printf 'failed to close created agent target: %s\n' "$page_id" >&2
  }
  cleanup_failed_agent_window() {
    disable_agent_window_rules
    [[ $retain_created_target == "true" ]] || close_created_target
    restore_operator_focus_after_failed_agent_window
  }
  trap cleanup_failed_agent_window EXIT

  if ! install_agent_window_rules; then
    echo "failed to install temporary agent-window compositor rules" >&2
    exit 1
  fi
  assert_hyprland_compositor_state "before CDP target creation"

  params=$(jq -nc --arg url "$marker_url" '{url: $url, newWindow: true, background: true}')
  if response=$(cdp_send "$ws_url" "Target.createTarget" "$params"); then
    :
  else
    status=$?
    printf 'failed to create agent browser target (status %s)\n' "$status" >&2
    exit "$status"
  fi
  if jq -e '.error' >/dev/null 2>&1 <<<"$response"; then
    jq . <<<"$response" >&2
    exit 1
  fi
  page_id=$(jq -r '.result.targetId // empty' <<<"$response")
  [[ -n $page_id ]] || {
    echo "CDP created no target ID for agent window" >&2
    jq . >&2 <<<"$response"
    exit 1
  }
  assert_hyprland_compositor_state "after CDP target creation"

  parked="false"
  addr=""
  if [[ $hyprland_available == "true" ]]; then
    for _ in {1..40}; do
      sleep 0.1
      assert_hyprland_compositor_state "while identifying target"
      matches=$(hyprctl_call clients -j 2>/dev/null | jq -r --arg marker "$marker" \
        '[.[] | select(.class == "google-chrome" and (.title | contains($marker))) | .address] | unique | .[]')
      match_count=$(wc -l <<<"$matches")
      if [[ $match_count -eq 1 && -n $matches ]]; then
        addr="$matches"
        break
      fi
    done

    if [[ -n $addr ]]; then
      stable_checks=0
      for _ in {1..20}; do
        sleep 0.1
        assert_hyprland_compositor_state "while verifying target placement"
        client_state=$(hyprctl_call clients -j 2>/dev/null | jq -c --arg address "$addr" \
          '.[] | select(.address == $address) | {workspace: .workspace.name, floating, pinned, fullscreen}')
        workspace=$(jq -r '.workspace // empty' <<<"$client_state")
        floating=$(jq -r '.floating' <<<"$client_state")
        pinned=$(jq -r '.pinned' <<<"$client_state")
        fullscreen=$(jq -r '.fullscreen' <<<"$client_state")
        visible=$(hyprctl_call monitors -j 2>/dev/null | jq -r --arg workspace "$AGENT_WORKSPACE" \
          'any(.[]; .activeWorkspace.name == $workspace)')
        if [[ $workspace == "$AGENT_WORKSPACE" && $visible == "false" && $floating == "false" &&
          $pinned == "false" && $fullscreen == "0" ]]; then
          ((stable_checks += 1))
          if [[ $stable_checks -ge 3 ]]; then
            parked="true"
            break
          fi
        else
          stable_checks=0
        fi
      done
    fi
  fi

  if [[ $parked == "true" ]]; then
    page_ws_url=$(get_ws_url "$page_id")
    if [[ -z $page_ws_url ]]; then
      echo "parked agent target disappeared before navigation" >&2
      exit 1
    fi
    navigate_params=$(jq -nc --arg url "$url" '{url: $url}')
    if navigate_response=$(cdp_send "$page_ws_url" "Page.navigate" "$navigate_params"); then
      :
    else
      status=$?
      printf 'failed to navigate parked agent target %s (status %s)\n' "$page_id" "$status" >&2
      exit "$status"
    fi
    if jq -e '.error' >/dev/null 2>&1 <<<"$navigate_response"; then
      jq . <<<"$navigate_response" >&2
      exit 1
    fi
    assert_hyprland_compositor_state "after navigating agent window"
  fi

  if [[ $parked != "true" ]]; then
    echo "window ${page_id} opened but was not verified on ${AGENT_WORKSPACE}; last compositor state: ${client_state:-unavailable}; visible=${visible:-unknown}; stable_checks=${stable_checks:-0}; focus_before=${focus_before:-unavailable}; hyprctl=${hyprctl_bin:-unavailable}; instances=${hyprland_instance_count:-unknown}; signature=$([[ -n ${HYPRLAND_INSTANCE_SIGNATURE:-} ]] && printf set || printf missing)" >&2
    exit 1
  fi
  disable_agent_window_rules
  assert_hyprland_compositor_state "after agent-window transaction"
  jq -nc --arg id "$page_id" --arg url "$url" --argjson parked "$parked" \
    --arg ws "$AGENT_WORKSPACE" --arg key "$SUMMON_BINDING" \
    '{id: $id, url: $url, parked: $parked, workspace: $ws, show_with: $key}'
  retain_created_target="true"
  trap - EXIT
  ;;

toggle-agent-workspace)
  hyprctl_bin=$(get_hyprctl_bin) || {
    echo "hyprctl unavailable" >&2
    exit 1
  }
  active_workspace=$(hyprctl_call activeworkspace -j | jq -r '.name')
  if [[ $active_workspace == "$AGENT_WORKSPACE" ]]; then
    workspace_lua=$(lua_quote previous)
  else
    workspace_lua=$(lua_quote "$AGENT_WORKSPACE_TARGET")
  fi
  hyprctl_call eval "hl.dispatch(hl.dsp.focus({ workspace = $workspace_lua }))"
  ;;

list | list-tabs)
  filter="."
  [[ $cmd == "list-tabs" ]] && filter='map(select(.type == "page"))'
  if [[ ${1:-} == "--json" ]]; then
    curl -fsS "${CDP_BASE}/json" | jq -c "${filter} | map({id, title, url, type})"
    exit 0
  fi
  curl -s "${CDP_BASE}/json" | jq -r "${filter} | .[] | [.id, .title[0:80], .url[0:100], .type] | @tsv" 2>/dev/null |
    awk 'BEGIN{print "PAGE_ID\tTITLE\tURL\tTYPE"} {print}'
  ;;

page-snapshot)
  page_id=""
  max_text=20000
  max_elements=300
  while [[ $# -gt 0 ]]; do
    case "$1" in
    --max-text)
      max_text="${2:?missing max-text}"
      shift 2
      ;;
    --max-elements)
      max_elements="${2:?missing max-elements}"
      shift 2
      ;;
    *)
      if [[ -z $page_id ]]; then
        page_id="$1"
        shift
      else
        echo "unknown arg: $1" >&2
        exit 2
      fi
      ;;
    esac
  done
  [[ -n $page_id ]] || {
    echo "page-snapshot requires page_id" >&2
    exit 2
  }
  page_id=$(resolve_page_id "$page_id")
  ws_url=$(get_ws_url "$page_id")
  [[ -n $ws_url ]] || {
    echo "page not found: $page_id" >&2
    exit 1
  }
  read -r -d '' snapshot_js <<'JS' || true
(() => {
  const MAXT = __MAXT__, MAXE = __MAXE__;
  const gen = (window.__sinnixGen = (window.__sinnixGen || 0) + 1);
  const sel = 'a[href],button,input,select,textarea,[role=button],[role=link],[role=textbox],[role=checkbox],[role=menuitem],[role=tab],[contenteditable=true],summary,[onclick]';
  const vis = e => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
  const trim = (v, n) => String(v == null ? '' : v).trim().slice(0, n);
  const els = []; let n = 0;
  for (const e of document.querySelectorAll('[data-sinnix-ref]')) e.removeAttribute('data-sinnix-ref');
  for (const e of document.querySelectorAll(sel)) {
    if (!vis(e)) continue;
    if (n >= MAXE) break;
    n++;
    const ref = 'g' + gen + 'e' + n;
    e.setAttribute('data-sinnix-ref', ref);
    const r = e.getBoundingClientRect();
    els.push({
      ref, tag: e.tagName.toLowerCase(), type: e.getAttribute('type'), role: e.getAttribute('role'),
      name: trim(e.getAttribute('aria-label') || e.getAttribute('name') || e.getAttribute('placeholder'), 200),
      text: trim(e.innerText || e.textContent, 200), href: e.href || null,
      value: (e.tagName === 'INPUT' || e.tagName === 'TEXTAREA' || e.tagName === 'SELECT') ? trim(e.value, 200) : null,
      disabled: !!e.disabled,
      rect: { x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height) }
    });
  }
  const links = Array.from(document.querySelectorAll('a[href]')).slice(0, MAXE)
    .map(a => ({ text: trim(a.innerText, 200), href: a.href, ref: a.getAttribute('data-sinnix-ref') }));
  const forms = Array.from(document.forms).map((f, i) => ({
    index: i, id: f.id || null, name: f.getAttribute('name'), action: f.action || null, method: f.method || null,
    ref: f.getAttribute('data-sinnix-ref'),
    fields: Array.from(f.elements).filter(vis).slice(0, 100).map(e => ({
      ref: e.getAttribute('data-sinnix-ref'), tag: e.tagName.toLowerCase(), type: e.type || null,
      name: e.name || null, value: trim(e.value, 200)
    }))
  }));
  const body = (document.body && document.body.innerText) || '';
  return JSON.stringify({
    generation: gen, url: location.href, title: document.title, ready_state: document.readyState,
    text: body.slice(0, MAXT), text_truncated: body.length > MAXT, elements: els, links, forms
  });
})()
JS
  snapshot_js="${snapshot_js//__MAXT__/$max_text}"
  snapshot_js="${snapshot_js//__MAXE__/$max_elements}"
  params=$(jq -nc --arg expr "$snapshot_js" '{expression: $expr, returnByValue: true}')
  cdp_send_with_result "$ws_url" "Runtime.evaluate" "$params" | jq -r '.result.value // empty'
  ;;

key)
  page_id=""
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
      if [[ -z $page_id ]]; then
        page_id="$1"
        shift
      else
        echo "unknown arg: $1" >&2
        exit 2
      fi
      ;;
    esac
  done
  [[ -n $page_id && -n $keyname ]] || {
    echo "key requires page_id and --key" >&2
    exit 2
  }
  page_id=$(resolve_page_id "$page_id")
  ws_url=$(get_ws_url "$page_id")
  [[ -n $ws_url ]] || {
    echo "page not found: $page_id" >&2
    exit 1
  }
  modifiers=0
  for m in "${mods[@]}"; do
    case "${m,,}" in
    alt) modifiers=$((modifiers | 1)) ;;
    ctrl | control) modifiers=$((modifiers | 2)) ;;
    meta | super) modifiers=$((modifiers | 4)) ;;
    shift) modifiers=$((modifiers | 8)) ;;
    *)
      echo "unknown modifier: $m" >&2
      exit 2
      ;;
    esac
  done
  text=""
  case "$keyname" in
  Enter | Return) key="Enter" code="Enter" vk=13 text=$'\r' ;;
  Tab) key="Tab" code="Tab" vk=9 ;;
  Escape | Esc) key="Escape" code="Escape" vk=27 ;;
  Backspace) key="Backspace" code="Backspace" vk=8 ;;
  Delete) key="Delete" code="Delete" vk=46 ;;
  Space) key=" " code="Space" vk=32 text=" " ;;
  ArrowLeft | Left) key="ArrowLeft" code="ArrowLeft" vk=37 ;;
  ArrowUp | Up) key="ArrowUp" code="ArrowUp" vk=38 ;;
  ArrowRight | Right) key="ArrowRight" code="ArrowRight" vk=39 ;;
  ArrowDown | Down) key="ArrowDown" code="ArrowDown" vk=40 ;;
  Home) key="Home" code="Home" vk=36 ;;
  End) key="End" code="End" vk=35 ;;
  PageUp) key="PageUp" code="PageUp" vk=33 ;;
  PageDown) key="PageDown" code="PageDown" vk=34 ;;
  ?)
    key="$keyname"
    upper="${keyname^^}"
    code="Key${upper}"
    vk=$(printf '%d' "'$upper")
    [[ $modifiers -eq 0 || $modifiers -eq 8 ]] && text="$keyname"
    ;;
  *)
    echo "unsupported key: $keyname" >&2
    exit 2
    ;;
  esac
  for type in keyDown keyUp; do
    params=$(jq -nc --arg type "$type" --arg key "$key" --arg code "$code" --argjson vk "$vk" --argjson modifiers "$modifiers" --arg text "$text" '{type: $type, key: $key, code: $code, windowsVirtualKeyCode: $vk, nativeVirtualKeyCode: $vk, modifiers: $modifiers}
       + (if $type == "keyDown" and $text != "" then {text: $text} else {} end)')
    cdp_send_with_result "$ws_url" "Input.dispatchKeyEvent" "$params" >/dev/null
  done
  jq -nc --arg id "$page_id" --arg key "$key" --argjson modifiers "$modifiers" '{id: $id, key: $key, modifiers: $modifiers, pressed: true}'
  ;;

download)
  page_id=""
  url=""
  out_file=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
    --url)
      url="${2:?missing url}"
      shift 2
      ;;
    --out)
      out_file="${2:?missing out}"
      shift 2
      ;;
    *)
      if [[ -z $page_id ]]; then
        page_id="$1"
        shift
      else
        echo "unknown arg: $1" >&2
        exit 2
      fi
      ;;
    esac
  done
  [[ -n $page_id && -n $url && -n $out_file ]] || {
    echo "download requires page_id, --url and --out" >&2
    exit 2
  }
  page_id=$(resolve_page_id "$page_id")
  ws_url=$(get_ws_url "$page_id")
  [[ -n $ws_url ]] || {
    echo "page not found: $page_id" >&2
    exit 1
  }
  download_js=$(jq -nc --arg url "$url" '$url' | jq -r '"fetch(" + tojson + ", {credentials: \"include\"}).then(async r => { const b = new Uint8Array(await r.arrayBuffer()); let s = \"\"; for (let i = 0; i < b.length; i++) s += String.fromCharCode(b[i]); return JSON.stringify({status: r.status, type: r.headers.get(\"content-type\"), bytes: b.length, b64: btoa(s)}); })"')
  params=$(jq -nc --arg expr "$download_js" '{expression: $expr, returnByValue: true, awaitPromise: true}')
  payload=$(cdp_send_with_result "$ws_url" "Runtime.evaluate" "$params" | jq -r '.result.value // empty')
  [[ -n $payload ]] || {
    echo "download produced no payload (response may exceed the 2 MB CDP buffer)" >&2
    exit 1
  }
  mkdir -p "$(dirname "$out_file")"
  jq -r '.b64' <<<"$payload" | base64 -d >"$out_file"
  jq -c --arg id "$page_id" --arg url "$url" --arg out "$out_file" 'del(.b64) + {id: $id, url: $url, out: $out}' <<<"$payload"
  ;;

info)
  [[ $# -ge 1 ]] || {
    echo "info requires page_id" >&2
    exit 2
  }
  page_id=$(resolve_page_id "$1")
  shift
  curl -s "${CDP_BASE}/json" | jq --arg id "$page_id" '.[] | select(.id == $id)'
  ;;

new-tab)
  url="about:blank"
  background=0
  while [[ $# -gt 0 ]]; do
    case "$1" in
    --url)
      url="${2:?missing url}"
      shift 2
      ;;
    --background)
      background=1
      shift
      ;;
    *)
      echo "unknown arg: $1" >&2
      exit 2
      ;;
    esac
  done
  if [[ $background -eq 1 ]]; then
    ws_url=$(get_browser_ws_url)
    [[ -n $ws_url ]] || {
      echo "browser websocket unavailable: ${CDP_BASE}" >&2
      exit 1
    }
    params=$(jq -nc --arg url "$url" '{url: $url, background: true}')
    response=$(cdp_send "$ws_url" "Target.createTarget" "$params")
    if jq -e '.error' >/dev/null 2>&1 <<<"$response"; then
      jq . <<<"$response" >&2
      exit 1
    fi
    jq '{id: .result.targetId, title: "", url: $url, background: true}' --arg url "$url" <<<"$response"
    exit 0
  fi

  response=$(curl -fsS -X PUT "${CDP_BASE}/json/new?${url}")
  if ! jq -e . >/dev/null 2>&1 <<<"$response"; then
    printf 'unexpected /json/new response: %s\n' "$response" >&2
    exit 1
  fi
  jq '{id, title, url}' <<<"$response"
  ;;

close)
  [[ $# -ge 1 ]] || {
    echo "close requires page_id" >&2
    exit 2
  }
  page_id=$(resolve_page_id "$1")
  curl -fsS "${CDP_BASE}/json/close/${page_id}" >/dev/null
  for _attempt in {1..50}; do
    if ! curl -fsS "${CDP_BASE}/json/list" | jq -e --arg id "$page_id" 'any(.[]; .id == $id)' >/dev/null; then
      jq -nc --arg id "$page_id" '{id: $id, closed: true}'
      exit 0
    fi
    sleep 0.1
  done
  printf 'CDP accepted close but target remained present: %s\n' "$page_id" >&2
  exit 1
  ;;

activate)
  [[ $# -ge 1 ]] || {
    echo "activate requires page_id" >&2
    exit 2
  }
  page_id=$(resolve_page_id "$1")
  response=$(curl -fsS "${CDP_BASE}/json/activate/${page_id}")
  print_cdp_http_response "$response"
  ;;

load-extension)
  extension_path=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
    --path)
      extension_path="${2:?missing extension path}"
      shift 2
      ;;
    *)
      echo "unknown arg: $1" >&2
      exit 2
      ;;
    esac
  done
  [[ -n $extension_path ]] || {
    echo "load-extension requires --path" >&2
    exit 2
  }
  [[ -d $extension_path ]] || {
    echo "extension path is not a directory: $extension_path" >&2
    exit 1
  }
  [[ -f $extension_path/manifest.json ]] || {
    echo "extension path has no manifest.json: $extension_path" >&2
    exit 1
  }
  ws_url=$(get_browser_ws_url)
  [[ -n $ws_url ]] || {
    echo "browser websocket unavailable: ${CDP_BASE}" >&2
    exit 1
  }

  params=$(jq -nc --arg path "$extension_path" '{path: $path}')
  response=$(cdp_send "$ws_url" "Extensions.loadUnpacked" "$params")
  if jq -e '.error' >/dev/null 2>&1 <<<"$response"; then
    jq . <<<"$response" >&2
    exit 1
  fi
  jq '{id: .result.id, path: $path}' --arg path "$extension_path" <<<"$response"
  ;;

screenshot)
  page_id=""
  format="png"
  quality=80
  full_page=0
  out_file=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
    --format)
      format="${2:?missing format}"
      shift 2
      ;;
    --quality)
      quality="${2:?missing quality}"
      shift 2
      ;;
    --full-page)
      full_page=1
      shift
      ;;
    --out)
      out_file="${2:?missing out file}"
      shift 2
      ;;
    *)
      if [[ -z $page_id ]]; then
        page_id="$1"
        shift
      else
        echo "unknown arg: $1" >&2
        exit 2
      fi
      ;;
    esac
  done
  [[ -n $page_id ]] || {
    echo "screenshot requires page_id" >&2
    exit 2
  }
  page_id=$(resolve_page_id "$page_id")
  ws_url=$(get_ws_url "$page_id")
  [[ -n $ws_url ]] || {
    echo "page not found: $page_id" >&2
    exit 1
  }

  params=$(jq -nc \
    --arg format "$format" \
    --argjson quality "$quality" \
    --argjson full "$full_page" \
    '{format: $format, quality: $quality, captureBeyondViewport: ($full == 1)}')
  if [[ $full_page -eq 0 ]]; then
    params=$(echo "$params" | jq -c 'del(.captureBeyondViewport)')
  fi
  if [[ $format == "png" ]]; then
    params=$(echo "$params" | jq -c 'del(.quality)')
  fi

  result=$(cdp_send_with_result "$ws_url" "Page.captureScreenshot" "$params")
  if [[ -z $result || $result == "null" ]]; then
    echo "screenshot failed" >&2
    exit 1
  fi
  data=$(echo "$result" | jq -r '.data')
  if [[ -n $out_file ]]; then
    mkdir -p "$(dirname "$out_file")"
    echo "$data" | base64 -d >"$out_file"
    echo "saved: $out_file ($(wc -c <"$out_file") bytes)"
  else
    echo "$data" | base64 -d
  fi
  ;;

evaluate)
  page_id=""
  js=""
  out_file=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
    --js)
      js="${2:?missing js}"
      shift 2
      ;;
    --out)
      out_file="${2:?missing out}"
      shift 2
      ;;
    *)
      if [[ -z $page_id ]]; then
        page_id="$1"
        shift
      else
        echo "unknown arg: $1" >&2
        exit 2
      fi
      ;;
    esac
  done
  [[ -n $page_id && -n $js ]] || {
    echo "evaluate requires page_id and --js" >&2
    exit 2
  }
  page_id=$(resolve_page_id "$page_id")
  ws_url=$(get_ws_url "$page_id")
  [[ -n $ws_url ]] || {
    echo "page not found: $page_id" >&2
    exit 1
  }

  # awaitPromise: an async IIFE or any promise-returning expression resolves
  # before we read it, instead of returning an opaque "Promise" object and
  # forcing callers into a store-on-window-then-poll workaround.
  # userGesture: lets evaluate drive gesture-gated APIs (clipboard, autoplay).
  # Errors surface as exceptionDetails, which returnByValue alone discards --
  # print them to stderr and exit non-zero rather than emitting a silent null.
  params=$(jq -nc --arg expr "$js" \
    '{expression: $expr, returnByValue: true, awaitPromise: true, userGesture: true}')
  result=$(cdp_send_with_result "$ws_url" "Runtime.evaluate" "$params")
  if [[ -n $out_file ]]; then
    echo "$result" | jq --arg expr "$js" '{expression: $expr, result: .}' >"$out_file"
    echo "saved: $out_file"
  else
    exception=$(echo "$result" | jq -r '.exceptionDetails // empty')
    if [[ -n $exception ]]; then
      echo "$result" | jq -r '
        .exceptionDetails
        | (.exception.description // .text // "evaluation failed")
          + (if .lineNumber then "  (line \(.lineNumber))" else "" end)' >&2
      exit 1
    fi
    echo "$result" | jq -r '.result.value // .result.description // .'
  fi
  ;;

network-log)
  # Stream CDP Network-domain events for a bounded window. Page-level fetch
  # hooking misses anything the app issued before the hook installed, anything
  # on another origin, and non-fetch transports; the Network domain sees all of
  # it. cdp_send is a bounded request/response exchange, so this opens its own
  # connection and holds it open by
  # keeping stdin alive for the duration.
  page_id=""
  duration=15
  filter=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
    --seconds)
      duration="${2:?missing seconds}"
      shift 2
      ;;
    --filter)
      filter="${2:?missing filter}"
      shift 2
      ;;
    *)
      if [[ -z $page_id ]]; then
        page_id="$1"
        shift
      else
        echo "unknown arg: $1" >&2
        exit 2
      fi
      ;;
    esac
  done
  [[ -n $page_id ]] || {
    echo "network-log requires page_id" >&2
    exit 2
  }
  page_id=$(resolve_page_id "$page_id")
  ws_url=$(get_ws_url "$page_id")
  [[ -n $ws_url ]] || {
    echo "page not found: $page_id" >&2
    exit 1
  }
  {
    echo '{"id":1,"method":"Network.enable"}'
    sleep "$duration"
  } | websocat -B 2097152 "$ws_url" 2>/dev/null |
    jq -c --arg f "$filter" '
      select(.method == "Network.requestWillBeSent" or .method == "Network.responseReceived")
      | if .method == "Network.requestWillBeSent" then
          {phase: "request", method: .params.request.method, url: .params.request.url,
           type: .params.type, id: .params.requestId}
        else
          {phase: "response", status: .params.response.status, url: .params.response.url,
           mime: .params.response.mimeType, type: .params.type, id: .params.requestId}
        end
      | select($f == "" or (.url | test($f)))'
  ;;

navigate)
  page_id=""
  url=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
    --url)
      url="${2:?missing url}"
      shift 2
      ;;
    *)
      if [[ -z $page_id ]]; then
        page_id="$1"
        shift
      else
        echo "unknown arg: $1" >&2
        exit 2
      fi
      ;;
    esac
  done
  [[ -n $page_id && -n $url ]] || {
    echo "navigate requires page_id and --url" >&2
    exit 2
  }
  page_id=$(resolve_page_id "$page_id")
  ws_url=$(get_ws_url "$page_id")
  [[ -n $ws_url ]] || {
    echo "page not found: $page_id" >&2
    exit 1
  }

  params=$(jq -nc --arg url "$url" '{url: $url}')
  cdp_send_with_result "$ws_url" "Page.navigate" "$params" | jq .
  ;;

reload)
  [[ $# -ge 1 ]] || {
    echo "reload requires page_id" >&2
    exit 2
  }
  page_id=$(resolve_page_id "$1")
  ws_url=$(get_ws_url "$page_id")
  [[ -n $ws_url ]] || {
    echo "page not found: $page_id" >&2
    exit 1
  }
  cdp_send_with_result "$ws_url" "Page.reload" | jq .
  ;;

inject-text)
  page_id=""
  text=""
  selector=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
    --text)
      text="${2:?missing text}"
      shift 2
      ;;
    --selector)
      selector="${2:?missing selector}"
      shift 2
      ;;
    *)
      if [[ -z $page_id ]]; then
        page_id="$1"
        shift
      else
        echo "unknown arg: $1" >&2
        exit 2
      fi
      ;;
    esac
  done
  [[ -n $page_id && -n $text ]] || {
    echo "inject-text requires page_id and --text" >&2
    exit 2
  }
  page_id=$(resolve_page_id "$page_id")
  ws_url=$(get_ws_url "$page_id")
  [[ -n $ws_url ]] || {
    echo "page not found: $page_id" >&2
    exit 1
  }

  # If selector given, focus it first
  if [[ -n $selector ]]; then
    focus_params=$(jq -nc --arg sel "$selector" '{expression: "document.querySelector(\($sel|tojson)).focus()", returnByValue: true}')
    cdp_send "$ws_url" "Runtime.evaluate" "$focus_params" >/dev/null 2>&1 || true
  fi

  # Use Input.dispatchKeyEvent for each character (handles React/Vue)
  for ((i = 0; i < ${#text}; i++)); do
    char="${text:i:1}"
    # Send char event
    type_params=$(jq -nc --arg c "$char" '{type: "char", text: $c, unmodifiedText: $c}')
    cdp_send "$ws_url" "Input.dispatchKeyEvent" "$type_params" >/dev/null 2>&1 || true
  done
  echo "ok"
  ;;

click)
  page_id=""
  selector=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
    --selector)
      selector="${2:?missing selector}"
      shift 2
      ;;
    *)
      if [[ -z $page_id ]]; then
        page_id="$1"
        shift
      else
        echo "unknown arg: $1" >&2
        exit 2
      fi
      ;;
    esac
  done
  [[ -n $page_id && -n $selector ]] || {
    echo "click requires page_id and --selector" >&2
    exit 2
  }
  page_id=$(resolve_page_id "$page_id")
  ws_url=$(get_ws_url "$page_id")
  [[ -n $ws_url ]] || {
    echo "page not found: $page_id" >&2
    exit 1
  }

  # Get element bounding box
  box_json=$(cdp_send_with_result "$ws_url" "Runtime.evaluate" \
    "$(jq -nc --arg sel "$selector" '{expression: "(()=>{const e=document.querySelector(\($sel|tojson));if(!e)return null;const r=e.getBoundingClientRect();return{x:r.x+window.scrollX,y:r.y+window.scrollY,w:r.width,h:r.height}})()", returnByValue: true}')")

  if echo "$box_json" | jq -e '.result.value == null' >/dev/null 2>&1; then
    echo "element not found: $selector" >&2
    exit 1
  fi

  x=$(echo "$box_json" | jq -r '.result.value.x')
  y=$(echo "$box_json" | jq -r '.result.value.y')
  w=$(echo "$box_json" | jq -r '.result.value.w')
  h=$(echo "$box_json" | jq -r '.result.value.h')
  cx=$(echo "$x + $w / 2" | bc)
  cy=$(echo "$y + $h / 2" | bc)

  # Mouse events
  mouse_params=$(jq -nc --argjson x "$cx" --argjson y "$cy" '{type: "mousePressed", x: $x, y: $y, button: "left", clickCount: 1}')
  cdp_send "$ws_url" "Input.dispatchMouseEvent" "$mouse_params"
  mouse_params=$(jq -nc --argjson x "$cx" --argjson y "$cy" '{type: "mouseReleased", x: $x, y: $y, button: "left", clickCount: 1}')
  cdp_send "$ws_url" "Input.dispatchMouseEvent" "$mouse_params"
  echo "clicked: $selector at ($cx, $cy)"
  ;;

get-text)
  page_id=""
  selector=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
    --selector)
      selector="${2:?missing selector}"
      shift 2
      ;;
    *)
      if [[ -z $page_id ]]; then
        page_id="$1"
        shift
      else
        echo "unknown arg: $1" >&2
        exit 2
      fi
      ;;
    esac
  done
  [[ -n $page_id ]] || {
    echo "get-text requires page_id" >&2
    exit 2
  }
  page_id=$(resolve_page_id "$page_id")
  ws_url=$(get_ws_url "$page_id")
  [[ -n $ws_url ]] || {
    echo "page not found: $page_id" >&2
    exit 1
  }

  if [[ -n $selector ]]; then
    expr="document.querySelector('${selector}')?.innerText ?? document.querySelector('${selector}')?.textContent ?? ''"
  else
    expr="document.body?.innerText ?? document.body?.textContent ?? ''"
  fi
  params=$(jq -nc --arg expr "$expr" '{expression: $expr, returnByValue: true}')
  cdp_send_with_result "$ws_url" "Runtime.evaluate" "$params" | jq -r '.result.value // empty'
  ;;

get-html)
  page_id=""
  selector=""
  out_file=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
    --selector)
      selector="${2:?missing selector}"
      shift 2
      ;;
    --out)
      out_file="${2:?missing out}"
      shift 2
      ;;
    *)
      if [[ -z $page_id ]]; then
        page_id="$1"
        shift
      else
        echo "unknown arg: $1" >&2
        exit 2
      fi
      ;;
    esac
  done
  [[ -n $page_id ]] || {
    echo "get-html requires page_id" >&2
    exit 2
  }
  page_id=$(resolve_page_id "$page_id")
  ws_url=$(get_ws_url "$page_id")
  [[ -n $ws_url ]] || {
    echo "page not found: $page_id" >&2
    exit 1
  }

  if [[ -n $selector ]]; then
    expr="document.querySelector('${selector}')?.outerHTML ?? ''"
  else
    expr="document.documentElement?.outerHTML ?? ''"
  fi
  params=$(jq -nc --arg expr "$expr" '{expression: $expr, returnByValue: true}')
  html=$(cdp_send_with_result "$ws_url" "Runtime.evaluate" "$params" | jq -r '.result.value // empty')
  if [[ -n $out_file ]]; then
    echo "$html" >"$out_file"
    echo "saved: $out_file"
  else
    echo "$html"
  fi
  ;;

fill-form)
  page_id=""
  selector=""
  value=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
    --selector)
      selector="${2:?missing selector}"
      shift 2
      ;;
    --value)
      value="${2:?missing value}"
      shift 2
      ;;
    *)
      if [[ -z $page_id ]]; then
        page_id="$1"
        shift
      else
        echo "unknown arg: $1" >&2
        exit 2
      fi
      ;;
    esac
  done
  [[ -n $page_id && -n $selector && -n $value ]] || {
    echo "fill-form requires page_id, --selector, --value" >&2
    exit 2
  }
  page_id=$(resolve_page_id "$page_id")
  ws_url=$(get_ws_url "$page_id")
  [[ -n $ws_url ]] || {
    echo "page not found: $page_id" >&2
    exit 1
  }

  # Set value and dispatch events (handles React controlled inputs)
  escaped_value=$(echo "$value" | jq -Rs .)
  expr="((v)=>{const e=document.querySelector('${selector}');if(!e)return'NOT_FOUND';const n=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value');if(n&&n.set){n.set.call(e,v);e.dispatchEvent(new Event('input',{bubbles:true}));e.dispatchEvent(new Event('change',{bubbles:true}));}else{e.value=v;e.dispatchEvent(new Event('input',{bubbles:true}));e.dispatchEvent(new Event('change',{bubbles:true}));}return'OK';})(${escaped_value})"
  params=$(jq -nc --arg expr "$expr" '{expression: $expr, returnByValue: true}')
  result=$(cdp_send_with_result "$ws_url" "Runtime.evaluate" "$params" | jq -r '.result.value // empty')
  echo "$result"
  ;;

upload-files)
  page_id=""
  selector=""
  upload_resolve_id=""
  upload_attach_id=""
  upload_dispatch_id=""
  files=()
  while [[ $# -gt 0 ]]; do
    case "$1" in
    --selector)
      selector="${2:?missing selector}"
      shift 2
      ;;
    --file)
      files+=("${2:?missing file}")
      shift 2
      ;;
    *)
      if [[ -z $page_id ]]; then
        page_id="$1"
        shift
      else
        echo "unknown arg: $1" >&2
        exit 2
      fi
      ;;
    esac
  done
  [[ -n $page_id && -n $selector && ${#files[@]} -gt 0 ]] || {
    echo "upload-files requires page_id, --selector, and at least one --file" >&2
    exit 2
  }
  page_id=$(resolve_page_id "$page_id")
  ws_url=$(get_ws_url "$page_id")
  [[ -n $ws_url ]] || {
    echo "page not found: $page_id" >&2
    exit 1
  }

  files_json='[]'
  for file in "${files[@]}"; do
    [[ -f $file ]] || {
      echo "upload file not found: $file" >&2
      exit 1
    }
    file=$(realpath "$file")
    files_json=$(jq -nc --argjson files "$files_json" --arg file "$file" '$files + [$file]')
  done

  coproc SINNIX_CDP_UPLOAD { websocat -B 2097152 "$ws_url" 2>/dev/null; }
  read_fd="${SINNIX_CDP_UPLOAD[0]}"
  write_fd="${SINNIX_CDP_UPLOAD[1]}"

  cdp_next_request_id upload_resolve_id
  request=$(jq -nc --argjson id "$upload_resolve_id" --arg selector "$selector" \
    '{id: $id, method: "Runtime.evaluate", params: {expression: ("document.querySelector(" + ($selector | tojson) + ")")}}')
  printf '%s\n' "$request" >&"$write_fd"
  response=$(cdp_read_response "$read_fd" "$upload_resolve_id" "Runtime.evaluate" "$CDP_RESPONSE_TIMEOUT_SEC") || {
    echo "CDP failed while resolving file input" >&2
    exit 1
  }
  object_id=$(jq -r '.result.result.objectId // empty' <<<"$response")
  [[ -n $object_id ]] || {
    echo "file input selector did not resolve: $selector" >&2
    exit 1
  }

  cdp_next_request_id upload_attach_id
  request=$(jq -nc --argjson id "$upload_attach_id" --arg objectId "$object_id" --argjson files "$files_json" \
    '{id: $id, method: "DOM.setFileInputFiles", params: {objectId: $objectId, files: $files}}')
  printf '%s\n' "$request" >&"$write_fd"
  response=$(cdp_read_response "$read_fd" "$upload_attach_id" "DOM.setFileInputFiles" "$CDP_RESPONSE_TIMEOUT_SEC") || {
    echo "CDP failed while attaching files" >&2
    exit 1
  }
  if jq -e '.error' >/dev/null 2>&1 <<<"$response"; then
    jq . <<<"$response" >&2
    exit 1
  fi

  cdp_next_request_id upload_dispatch_id
  request=$(jq -nc --argjson id "$upload_dispatch_id" --arg objectId "$object_id" \
    '{id: $id, method: "Runtime.callFunctionOn", params: {objectId: $objectId, functionDeclaration: "function(){this.dispatchEvent(new Event(\"input\",{bubbles:true}));this.dispatchEvent(new Event(\"change\",{bubbles:true}));return this.files.length}", returnByValue: true}}')
  printf '%s\n' "$request" >&"$write_fd"
  response=$(cdp_read_response "$read_fd" "$upload_dispatch_id" "Runtime.callFunctionOn" "$CDP_RESPONSE_TIMEOUT_SEC") || {
    echo "CDP failed while dispatching file events" >&2
    exit 1
  }
  attached=$(jq -r '.result.result.value // 0' <<<"$response")
  exec {write_fd}>&-
  wait "$SINNIX_CDP_UPLOAD_PID" || true
  jq -nc --arg id "$page_id" --arg selector "$selector" --argjson attached "$attached" \
    '{id: $id, selector: $selector, attached: $attached}'
  ;;

wait-selector)
  page_id=""
  selector=""
  timeout_sec=30
  interval_ms=500
  while [[ $# -gt 0 ]]; do
    case "$1" in
    --selector)
      selector="${2:?missing selector}"
      shift 2
      ;;
    --timeout-sec)
      timeout_sec="${2:?missing timeout}"
      shift 2
      ;;
    --interval-ms)
      interval_ms="${2:?missing interval}"
      shift 2
      ;;
    *)
      if [[ -z $page_id ]]; then
        page_id="$1"
        shift
      else
        echo "unknown arg: $1" >&2
        exit 2
      fi
      ;;
    esac
  done
  [[ -n $page_id && -n $selector ]] || {
    echo "wait-selector requires page_id and --selector" >&2
    exit 2
  }
  "$0" await "$page_id" \
    --js "document.querySelector($(jq -nc --arg selector "$selector" '$selector')) !== null" \
    --timeout-sec "$timeout_sec" \
    --interval-ms "$interval_ms"
  ;;

await)
  page_id=""
  js=""
  timeout_sec=30
  interval_ms=500
  while [[ $# -gt 0 ]]; do
    case "$1" in
    --js)
      js="${2:?missing js}"
      shift 2
      ;;
    --timeout-sec)
      timeout_sec="${2:?missing timeout}"
      shift 2
      ;;
    --interval-ms)
      interval_ms="${2:?missing interval}"
      shift 2
      ;;
    *)
      if [[ -z $page_id ]]; then
        page_id="$1"
        shift
      else
        echo "unknown arg: $1" >&2
        exit 2
      fi
      ;;
    esac
  done
  [[ -n $page_id && -n $js ]] || {
    echo "await requires page_id and --js" >&2
    exit 2
  }
  page_id=$(resolve_page_id "$page_id")
  ws_url=$(get_ws_url "$page_id")
  [[ -n $ws_url ]] || {
    echo "page not found: $page_id" >&2
    exit 1
  }

  deadline=$(($(date +%s) + timeout_sec))
  while :; do
    params=$(jq -nc --arg expr "$js" '{expression: $expr, returnByValue: true}')
    val=$(cdp_send_with_result "$ws_url" "Runtime.evaluate" "$params" | jq -r '.result.value // empty')
    if [[ $val != "null" && $val != "false" && $val != "" && $val != "0" ]]; then
      echo "$val"
      exit 0
    fi
    if [[ $(date +%s) -ge $deadline ]]; then
      echo "await timed out after ${timeout_sec}s" >&2
      exit 124
    fi
    sleep "$(echo "scale=3; $interval_ms / 1000" | bc)"
  done
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
