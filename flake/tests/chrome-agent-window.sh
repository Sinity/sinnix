#!/usr/bin/env bash
# Deterministic fake CDP/Hyprland fixture for sinnix-e3jb. It measures the
# response path and compositor proof without contacting the shared Chrome.
set -euo pipefail

helper="$1"
shift
fixture_root="$(mktemp -d)"
trap 'rm -rf "$fixture_root"' EXIT

mkdir -p "$fixture_root/bin" "$fixture_root/runtime"

cat >"$fixture_root/bin/curl" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

url="${*: -1}"
state="${FAKE_STATE:?}"
case "$url" in
*/json/version)
  printf '%s\n' '{"webSocketDebuggerUrl":"ws://browser"}'
  ;;
*/json|*/json/list)
  if [[ -e "$state/agent-target" ]]; then
    marker="$(sed -n 's/.*<title>\(.*\)<\/title>.*/\1/p' "$state/marker-url")"
    jq -nc --arg marker "$marker" '[{id: "agent-target", title: $marker, url: ("data:text/html,<title>" + $marker + "</title>"), type: "page", webSocketDebuggerUrl: "ws://page/agent-target"}]'
  else
    printf '%s\n' '[]'
  fi
  ;;
*/json/close/*)
  rm -f "$state/agent-target"
  printf '%s\n' '{}'
  ;;
*)
  printf 'unexpected curl call: %s\n' "$*" >&2
  exit 1
  ;;
esac
EOF

cat >"$fixture_root/bin/websocat" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

state="${FAKE_STATE:?}"
request="$(IFS= read -r line; printf '%s' "$line")"

# Chromium accepts CDP request IDs as positive signed 32-bit integers. Its
# invalid-request error is uncorrelated, so a caller that awaits its own ID
# must keep waiting until its response deadline.
if ! jq -e '(.id | type == "number" and floor == . and . >= 1 and . <= 2147483647)' \
  >/dev/null <<<"$request"; then
  printf '%s\n' "{\"error\":{\"code\":-32600,\"message\":\"Message must have integer 'id' property\"}}"
  trap 'exit 0' TERM INT
  while :; do sleep 1; done
fi

id="$(jq -r '.id' <<<"$request")"
method="$(jq -r '.method' <<<"$request")"
printf '%s\t%s\n' "$id" "$method" >>"$state/request-ids"

respond() {
  jq -nc --argjson id "$id" --arg method "$method" '
    if $method == "Target.createTarget" then {id: $id, result: {targetId: "agent-target"}}
    elif $method == "Page.navigate" then {id: $id, result: {frameId: "frame-agent"}}
    elif $method == "Target.closeTarget" then {id: $id, result: {success: true}}
    else {id: $id, result: {}}
    end'
}

case "$method" in
Target.createTarget)
  touch "$state/agent-target"
  jq -r '.params.url' <<<"$request" >"$state/marker-url"
  ;;
Target.closeTarget)
  target_id="$(jq -r '.params.targetId // empty' <<<"$request")"
  printf '%s\n' "$target_id" >>"$state/closed-targets"
  [[ $target_id == agent-target ]] && rm -f "$state/agent-target"
  ;;
Page.navigate)
  jq -r '.params.url' <<<"$request" >"$state/navigated-url"
  ;;
esac

case "${FAKE_CDP_SCENARIO:?}" in
match)
  respond
  ;;
event-first)
  printf '%s\n' '{"method":"Target.targetCreated","params":{"targetInfo":{"targetId":"noise"}}}'
  if [[ " $* " != *' -n1 '* ]]; then
    respond
  fi
  ;;
missing)
  trap 'exit 0' TERM INT
  while :; do sleep 1; done
  ;;
delayed)
  sleep "${FAKE_CDP_DELAY_SEC:-1}"
  respond
  ;;
*)
  printf 'unknown fake CDP scenario: %s\n' "$FAKE_CDP_SCENARIO" >&2
  exit 2
  ;;
esac
EOF

cat >"$fixture_root/bin/hyprctl" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

state="${FAKE_STATE:?}"
printf '%s\n' "$*" >>"$state/hyprctl-calls"
case "$1 $2" in
'instances -j')
  printf '%s\n' '[{"instance":"fake-hyprland"}]'
  ;;
'clients -j')
  if [[ -e "$state/agent-target" && ${FAKE_COMPOSITOR_MAP:-true} == true ]]; then
    marker="$(sed -n 's/.*<title>\(.*\)<\/title>.*/\1/p' "$state/marker-url")"
    workspace="$(cat "$state/workspace" 2>/dev/null || printf operator)"
    jq -nc --arg marker "$marker" --arg workspace "$workspace" \
      --argjson floating "${FAKE_FLOATING:-false}" \
      --argjson pinned "${FAKE_PINNED:-false}" \
      --argjson fullscreen "${FAKE_FULLSCREEN:-0}" '
      [{address: "0xoperator", class: "kitty", title: "operator", workspace: {name: "operator"}, floating: false, pinned: false, fullscreen: 0},
       {address: "0xagent", class: "google-chrome", title: $marker, workspace: {name: $workspace}, floating: $floating, pinned: $pinned, fullscreen: $fullscreen}]'
  else
    printf '%s\n' '[{"address":"0xoperator","class":"kitty","title":"operator","workspace":{"name":"operator"},"floating":false,"pinned":false,"fullscreen":0}]'
  fi
  ;;
'monitors -j')
  if [[ ${FAKE_VISIBLE:-false} == true ]]; then
    printf '%s\n' '[{"activeWorkspace":{"name":"agentbrowser"}}]'
  else
    printf '%s\n' '[{"activeWorkspace":{"name":"operator"}}]'
  fi
  ;;
'activewindow -j')
  if [[ ${FAKE_FOCUS_CHANGE:-false} == true && -e "$state/dispatched" ]]; then
    printf '%s\n' '{"address":"0xother"}'
  else
    printf '%s\n' '{"address":"0xoperator"}'
  fi
  ;;
'dispatch movetoworkspacesilent')
  [[ ${3:-} == name:agentbrowser,address:0xagent ]] || {
    printf 'agent-window moved a non-owned compositor client: %s\n' "${3:-}" >&2
    exit 1
  }
  touch "$state/dispatched"
  printf '%s\n' agentbrowser >"$state/workspace"
  ;;
*)
  printf 'unexpected hyprctl call: %s\n' "$*" >&2
  exit 1
  ;;
esac
EOF

for fake in "$fixture_root/bin"/*; do
  sed -i "1c#!$(command -v bash)" "$fake"
  chmod +x "$fake"
done

run_with_deadline() {
  local name="$1" scenario="$2" deadline_sec="$3"
  local status elapsed_ms pid start_ns deadline_at
  local state="$fixture_root/$name"
  mkdir -p "$state/runtime"
  : >"$state/request-ids"
  : >"$state/closed-targets"
  : >"$state/hyprctl-calls"
  start_ns="$(date +%s%N)"
  deadline_at=$((SECONDS + deadline_sec))
  env \
    PATH="$fixture_root/bin:$PATH" \
    XDG_RUNTIME_DIR="$state/runtime" \
    FAKE_STATE="$state" \
    FAKE_CDP_SCENARIO="$scenario" \
    SINNIX_CDP_TIMEOUT_SEC=2 \
    setsid "$helper" agent-window --url https://example.test >"$state/stdout" 2>"$state/stderr" &
  pid=$!
  while kill -0 "$pid" 2>/dev/null; do
    if (( SECONDS >= deadline_at )); then
      kill -- "-$pid" 2>/dev/null || true
      wait "$pid" 2>/dev/null || true
      status=124
      elapsed_ms=$(( ($(date +%s%N) - start_ns) / 1000000 ))
      printf 'case=%s status=%s elapsed_ms=%s target=%s closed=%s navigated=%s\n' \
        "$name" "$status" "$elapsed_ms" "$(test -e "$state/agent-target" && printf present || printf absent)" \
        "$(wc -l <"$state/closed-targets")" "$(test -e "$state/navigated-url" && printf yes || printf no)"
      return "$status"
    fi
    sleep 0.05
  done
  wait "$pid" || status=$?
  status="${status:-0}"
  elapsed_ms=$(( ($(date +%s%N) - start_ns) / 1000000 ))
  printf 'case=%s status=%s elapsed_ms=%s target=%s closed=%s navigated=%s\n' \
    "$name" "$status" "$elapsed_ms" "$(test -e "$state/agent-target" && printf present || printf absent)" \
    "$(wc -l <"$state/closed-targets")" "$(test -e "$state/navigated-url" && printf yes || printf no)"
  return "$status"
}

assert_fake_wire_rejects_out_of_range_id() {
  local state="$fixture_root/invalid-id" expected_message
  expected_message="Message must have integer 'id' property"
  mkdir -p "$state"
  : >"$state/request-ids"
  if timeout 1 env \
    FAKE_STATE="$state" \
    FAKE_CDP_SCENARIO=match \
    "$fixture_root/bin/websocat" \
    <<< '{"id":2147483648,"method":"Target.createTarget","params":{}}' \
    >"$state/response" 2>"$state/stderr"; then
    printf 'fake CDP wire accepted an out-of-range request ID\n' >&2
    return 1
  fi
  jq -e --arg message "$expected_message" '. == {error: {code: -32600, message: $message}}' \
    "$state/response" >/dev/null
  test ! -e "$state/agent-target"
}

assert_positive_accepted_request_ids() {
  local requests="$1/request-ids" id method
  while IFS=$'\t' read -r id method; do
    [[ $id =~ ^[1-9][0-9]*$ ]] && ((id <= 2147483647)) || {
      printf 'helper emitted an invalid CDP request ID: %s (%s)\n' "$id" "$method" >&2
      return 1
    }
  done <"$requests"
}

mode="${1:-final}"
case "$mode" in
baseline)
  run_with_deadline matching match 8
  if run_with_deadline unsolicited event-first 8; then
    printf 'pre-fix accepted an unsolicited CDP event\n' >&2
    exit 1
  fi
  if run_with_deadline missing missing 3; then
    printf 'pre-fix unexpectedly completed without a CDP response\n' >&2
    exit 1
  fi
  run_with_deadline delayed delayed 8
  ;;
final)
  assert_fake_wire_rejects_out_of_range_id

  run_with_deadline matching match 8
  state="$fixture_root/matching"
  jq -e '.parked == true and .workspace == "agentbrowser" and .url == "https://example.test"' "$state/stdout" >/dev/null
  test "$(cat "$state/navigated-url")" = https://example.test
  ! grep -Fq 'dispatch workspace' "$state/hyprctl-calls"
  ! grep -Fq 'address:0xoperator' "$state/hyprctl-calls"
  assert_positive_accepted_request_ids "$state"

  run_with_deadline unsolicited event-first 8
  state="$fixture_root/unsolicited"
  jq -e '.parked == true' "$state/stdout" >/dev/null
  assert_positive_accepted_request_ids "$state"

  if run_with_deadline missing missing 6; then
    printf 'missing CDP response unexpectedly succeeded\n' >&2
    exit 1
  fi
  state="$fixture_root/missing"
  test ! -e "$state/agent-target"
  test "$(cat "$state/closed-targets")" = agent-target
  grep -Fq 'timed out waiting for CDP response' "$state/stderr"
  assert_positive_accepted_request_ids "$state"

  run_with_deadline delayed delayed 8
  state="$fixture_root/delayed"
  jq -e '.parked == true' "$state/stdout" >/dev/null
  assert_positive_accepted_request_ids "$state"

  FAKE_COMPOSITOR_MAP=false run_with_deadline compositor-map-failure match 8 || true
  state="$fixture_root/compositor-map-failure"
  test ! -e "$state/agent-target"
  test "$(cat "$state/closed-targets")" = agent-target

  for layout in floating pinned fullscreen visible; do
    case "$layout" in
    floating) FAKE_FLOATING=true run_with_deadline "${layout}-agent-window" match 8 || true ;;
    pinned) FAKE_PINNED=true run_with_deadline "${layout}-agent-window" match 8 || true ;;
    fullscreen) FAKE_FULLSCREEN=1 run_with_deadline "${layout}-agent-window" match 8 || true ;;
    visible) FAKE_VISIBLE=true run_with_deadline "${layout}-agent-window" match 8 || true ;;
    esac
    state="$fixture_root/${layout}-agent-window"
    test ! -e "$state/agent-target"
    test "$(cat "$state/closed-targets")" = agent-target
  done

  FAKE_FOCUS_CHANGE=true run_with_deadline focus-change match 8 || true
  state="$fixture_root/focus-change"
  test ! -e "$state/agent-target"
  test "$(cat "$state/closed-targets")" = agent-target
  grep -Fq 'focused compositor client changed' "$state/stderr"
  ;;
*)
  printf 'usage: %s [baseline|final]\n' "$0" >&2
  exit 2
  ;;
esac
