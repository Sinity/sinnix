#!/usr/bin/env bash
set -euo pipefail

# Chrome DevTools Protocol (CDP) remote control for Google Chrome.
# Chrome must be running with --remote-debugging-port=9222.
# Uses curl for HTTP endpoints and websocat for WebSocket CDP commands.

CDP_HOST="${CDP_HOST:-127.0.0.1}"
CDP_PORT="${CDP_PORT:-9222}"
CDP_BASE="http://${CDP_HOST}:${CDP_PORT}"

usage() {
  cat <<'USAGE'
Usage: sinnix-chrome-control <command> [options]

Commands:
  list                            List all open pages (id, title, url, type)
  list-tabs                       List only page-type targets
  info <page_id>                  Get detailed info for a page
  new-tab [--url <url>]           Open a new tab (optionally with URL)
  close <page_id>                 Close a page/tab
  activate <page_id>              Bring a page to the front

  screenshot <page_id> [--format png|jpeg] [--quality 80] [--full-page] [--out <file>]
                                  Take a screenshot of a page via CDP

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

  await <page_id> --js <javascript> [--timeout-sec <n>] [--interval-ms <n>]
                                  Poll a JS expression until it returns truthy

Examples:
  sinnix-chrome-control list
  sinnix-chrome-control screenshot <id> --out /tmp/page.png
  sinnix-chrome-control evaluate <id> --js 'document.title'
  sinnix-chrome-control fill-form <id> --selector '#search' --value 'my query'
  sinnix-chrome-control click <id> --selector 'button.submit'
  sinnix-chrome-control navigate <id> --url 'https://example.com'
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
    '{format: $format, quality: $quality, captureBeyondViewport: $full}')
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

  params=$(jq -nc --arg expr "$js" '{expression: $expr, returnByValue: true}')
  result=$(cdp_send_with_result "$ws_url" "Runtime.evaluate" "$params")
  if [[ -n $out_file ]]; then
    echo "$result" | jq --arg expr "$js" '{expression: $expr, result: .}' >"$out_file"
    echo "saved: $out_file"
  else
    echo "$result" | jq -r '.result.value // .result.description // .'
  fi
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
