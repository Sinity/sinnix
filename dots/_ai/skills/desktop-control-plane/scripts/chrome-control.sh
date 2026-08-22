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

# The hidden workspace agent windows are parked on, and the key that shows it.
# Must match modules/features/desktop/hyprland/{rules,bindings}.nix.
AGENT_WORKSPACE="${SINNIX_AGENT_BROWSER_WORKSPACE:-special:agentbrowser}"
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
  list                            List all open pages (id, title, url, type)
  list-tabs                       List only page-type targets
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

cdp_send() {
  local ws_url method params_json
  ws_url="$1"
  method="$2"
  params_json="${3:-}"
  [[ -n $params_json ]] || params_json='{}'
  echo "{\"id\":1,\"method\":\"$method\",\"params\":$params_json}" |
    websocat -B 2097152 -n1 "$ws_url" 2>/dev/null
}

cdp_send_with_result() {
  local ws_url method params_json
  ws_url="$1"
  method="$2"
  params_json="${3:-}"
  [[ -n $params_json ]] || params_json='{}'
  cdp_send "$ws_url" "$method" "$params_json" | jq -r '.result // empty'
}

cdp_read_response() {
  local fd expected_id line
  fd="$1"
  expected_id="$2"
  while IFS= read -r line <&"$fd"; do
    if jq -e --argjson id "$expected_id" '.id == $id' >/dev/null 2>&1 <<<"$line"; then
      printf '%s\n' "$line"
      return 0
    fi
  done
  return 1
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
  curl -s "${CDP_BASE}/json" | jq -r --arg id "$page_id" '.[] | select(.id == $id) | .webSocketDebuggerUrl'
}

get_browser_ws_url() {
  curl -fsS --max-time 2 "${CDP_BASE}/json/version" | jq -r '.webSocketDebuggerUrl // empty'
}

resolve_page_id() {
  local maybe_id="$1"
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
# The window is identified by DIFFING Hyprland's client list across the
# creation, not by matching a class or a title. Every window of one Chrome
# process carries the same class, so a windowrule cannot tell this window from
# the operator's; and a title match would race the page's own title changes.
# The whole create-to-park transaction is serialized because concurrent callers
# would otherwise diff the same client set and both select one new address.
# `movetoworkspacesilent` moves that unique address without pulling the
# operator's view along with it. Chrome may still finish mapping its native
# window after CDP returns, so success requires observing that exact address on
# the hidden workspace after the move.
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
  before=""
  if command -v hyprctl >/dev/null 2>&1; then
    hyprland_available="true"
    before=$(hyprctl clients -j 2>/dev/null | jq -r '.[].address' | sort)
  fi

  params=$(jq -nc --arg url "$url" '{url: $url, newWindow: true}')
  response=$(cdp_send "$ws_url" "Target.createTarget" "$params")
  if jq -e '.error' >/dev/null 2>&1 <<<"$response"; then
    jq . <<<"$response" >&2
    exit 1
  fi
  page_id=$(jq -r '.result.targetId' <<<"$response")

  parked="false"
  addr=""
  if [[ $hyprland_available == "true" ]]; then
    for _ in {1..40}; do
      sleep 0.1
      after=$(hyprctl clients -j 2>/dev/null | jq -r '.[].address' | sort)
      addr=$(comm -13 <(printf '%s\n' "$before") <(printf '%s\n' "$after") | awk 'NR == 1 { print; exit }')
      [[ -n $addr ]] && break
    done

    if [[ -n $addr ]]; then
      stable_checks=0
      for _ in {1..20}; do
        hyprctl dispatch movetoworkspacesilent "${AGENT_WORKSPACE},address:${addr}" >/dev/null 2>&1 || true
        sleep 0.1
        workspace=$(hyprctl clients -j 2>/dev/null | jq -r --arg address "$addr" \
          '.[] | select(.address == $address) | .workspace.name // empty')
        if [[ $workspace == "$AGENT_WORKSPACE" ]]; then
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

  jq -nc --arg id "$page_id" --arg url "$url" --argjson parked "$parked" \
    --arg ws "$AGENT_WORKSPACE" --arg key "$SUMMON_BINDING" \
    '{id: $id, url: $url, parked: $parked, workspace: $ws, show_with: $key}'
  if [[ $parked != "true" ]]; then
    echo "window ${page_id} opened but was not verified on ${AGENT_WORKSPACE}" >&2
    exit 1
  fi
  ;;

list | list-tabs)
  filter="."
  [[ $cmd == "list-tabs" ]] && filter='map(select(.type == "page"))'
  curl -s "${CDP_BASE}/json" | jq -r "${filter} | .[] | [.id, .title[0:80], .url[0:100], .type] | @tsv" 2>/dev/null |
    awk 'BEGIN{print "PAGE_ID\tTITLE\tURL\tTYPE"} {print}'
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
  response=$(curl -fsS "${CDP_BASE}/json/close/${page_id}")
  print_cdp_http_response "$response"
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
  # it. cdp_send uses `websocat -n1`, which closes after one message and cannot
  # observe events, so this opens its own connection and holds it open by
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

  request=$(jq -nc --arg selector "$selector" \
    '{id: 1, method: "Runtime.evaluate", params: {expression: ("document.querySelector(" + ($selector | tojson) + ")")}}')
  printf '%s\n' "$request" >&"$write_fd"
  response=$(cdp_read_response "$read_fd" 1) || {
    echo "CDP connection closed while resolving file input" >&2
    exit 1
  }
  object_id=$(jq -r '.result.result.objectId // empty' <<<"$response")
  [[ -n $object_id ]] || {
    echo "file input selector did not resolve: $selector" >&2
    exit 1
  }

  request=$(jq -nc --arg objectId "$object_id" --argjson files "$files_json" \
    '{id: 2, method: "DOM.setFileInputFiles", params: {objectId: $objectId, files: $files}}')
  printf '%s\n' "$request" >&"$write_fd"
  response=$(cdp_read_response "$read_fd" 2) || {
    echo "CDP connection closed while attaching files" >&2
    exit 1
  }
  if jq -e '.error' >/dev/null 2>&1 <<<"$response"; then
    jq . <<<"$response" >&2
    exit 1
  fi

  request=$(jq -nc --arg objectId "$object_id" \
    '{id: 3, method: "Runtime.callFunctionOn", params: {objectId: $objectId, functionDeclaration: "function(){this.dispatchEvent(new Event(\"input\",{bubbles:true}));this.dispatchEvent(new Event(\"change\",{bubbles:true}));return this.files.length}", returnByValue: true}}')
  printf '%s\n' "$request" >&"$write_fd"
  response=$(cdp_read_response "$read_fd" 3) || {
    echo "CDP connection closed while dispatching file events" >&2
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
