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
  if [[ ${FAKE_ACTIVATION_BEFORE_PARK:-false} == true && ! -e "$state/pre-map-rules" ]]; then
    printf '%s\n' activation-before-park >>"$state/focus-workspace-actions"
    printf '%s\n' agentbrowser >"$state/active-workspace"
    printf '%s\n' 0xagent >"$state/active-window"
    touch "$state/activation-stolen"
  fi
  if [[ ${FAKE_CDP_SCENARIO:?} == operator-disappears ]]; then
    rm -f "$state/operator-window" "$state/active-window"
  fi
  if [[ ${FAKE_FOCUS_CHANGE:-false} == true ]]; then
    printf '%s\n' 0xother >"$state/active-window"
  fi
  if [[ -e "$state/pre-map-rules" ]]; then
    printf '%s\n' agentbrowser >"$state/workspace"
  fi
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
match|activation-before-park|operator-disappears)
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
eval\ *)
  if [[ $* == *hl.window_rule* ]]; then
    touch "$state/pre-map-rules"
  fi
  if [[ $* == *set_enabled* ]]; then
    touch "$state/rules-disabled"
    rm -f "$state/pre-map-rules"
  fi
  printf '%s\n' ok
  ;;
'clients -j')
  if [[ -e "$state/agent-target" && ${FAKE_COMPOSITOR_MAP:-true} == true ]]; then
    marker="$(sed -n 's/.*<title>\(.*\)<\/title>.*/\1/p' "$state/marker-url")"
    workspace="$(cat "$state/workspace" 2>/dev/null || printf operator)"
    operator_window='[]'
    if [[ -e "$state/operator-window" ]]; then
      operator_window='[{"address":"0xoperator","class":"kitty","title":"operator","workspace":{"name":"operator"},"floating":false,"pinned":false,"fullscreen":0}]'
    fi
    jq -nc --arg marker "$marker" --arg workspace "$workspace" --argjson operator "$operator_window" \
      --argjson floating "${FAKE_FLOATING:-false}" \
      --argjson pinned "${FAKE_PINNED:-false}" \
      --argjson fullscreen "${FAKE_FULLSCREEN:-0}" '
      $operator +
      [{address: "0xagent", class: "google-chrome", title: $marker, workspace: {name: $workspace}, floating: $floating, pinned: $pinned, fullscreen: $fullscreen}]'
  else
    if [[ -e "$state/operator-window" ]]; then
      printf '%s\n' '[{"address":"0xoperator","class":"kitty","title":"operator","workspace":{"name":"operator"},"floating":false,"pinned":false,"fullscreen":0}]'
    else
      printf '%s\n' '[]'
    fi
  fi
  ;;
'monitors -j')
  if [[ ${FAKE_VISIBLE:-false} == true ]]; then
    printf '%s\n' '[{"activeWorkspace":{"name":"agentbrowser"}}]'
  else
    workspace="$(cat "$state/active-workspace" 2>/dev/null || printf operator)"
    jq -nc --arg workspace "$workspace" '[{activeWorkspace: {name: $workspace}}]'
  fi
  ;;
'activewindow -j')
  if [[ -e "$state/active-window" ]]; then
    jq -nc --arg address "$(cat "$state/active-window")" '{address: $address}'
  else
    printf '%s\n' '{"address":null}'
  fi
  ;;
dispatch\ *)
  if [[ $1 == dispatch && $2 == focuswindow && $3 == address:0xoperator ]]; then
    printf '%s\n' 0xoperator >"$state/active-window"
    printf '%s\n' "$*" >>"$state/focus-workspace-actions"
    printf '%s\n' ok
  else
    printf 'agent-window issued an unexpected compositor dispatch: %s\n' "$*" >&2
    exit 1
  fi
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
  : >"$state/focus-workspace-actions"
  : >"$state/operator-window"
  printf '%s\n' operator >"$state/active-workspace"
  printf '%s\n' 0xoperator >"$state/active-window"
  start_ns="$(date +%s%N)"
  deadline_at=$((SECONDS + deadline_sec))
  env \
    PATH="$fixture_root/bin:$PATH" \
    XDG_RUNTIME_DIR="$state/runtime" \
    FAKE_STATE="$state" \
    FAKE_CDP_SCENARIO="$scenario" \
    FAKE_ACTIVATION_BEFORE_PARK=true \
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

assert_rules_cleaned() {
  local state="$1"
  test -e "$state/rules-disabled"
  test ! -e "$state/pre-map-rules"
}

assert_activation_before_park_reproduced() {
  local state="$fixture_root/activation-before-park-reproduction"
  mkdir -p "$state"
  : >"$state/focus-workspace-actions"
  printf '%s\n' operator >"$state/active-workspace"
  printf '%s\n' 0xoperator >"$state/active-window"
  printf '%s\n' 0xoperator >"$state/operator-window"
  env \
    PATH="$fixture_root/bin:$PATH" \
    FAKE_STATE="$state" \
    FAKE_CDP_SCENARIO=activation-before-park \
    FAKE_ACTIVATION_BEFORE_PARK=true \
    "$fixture_root/bin/websocat" \
    <<< '{"id":1,"method":"Target.createTarget","params":{"url":"data:text/html,<title>unprotected</title>","newWindow":true,"background":true}}' \
    >"$state/response"
  test -e "$state/activation-stolen"
  test "$(cat "$state/active-workspace")" = agentbrowser
  test "$(cat "$state/active-window")" = 0xagent
  test "$(cat "$state/focus-workspace-actions")" = activation-before-park
}

mode="${1:-final}"
case "$mode" in
reproduce)
  assert_activation_before_park_reproduced
  ;;
final)
  assert_fake_wire_rejects_out_of_range_id
  assert_activation_before_park_reproduced

  run_with_deadline matching match 8
  state="$fixture_root/matching"
  jq -e '.parked == true and .workspace == "agentbrowser" and .url == "https://example.test"' "$state/stdout" >/dev/null
  test "$(cat "$state/navigated-url")" = https://example.test
  test ! -e "$state/activation-stolen"
  test ! -s "$state/focus-workspace-actions"
  ! grep -Fq 'dispatch' "$state/hyprctl-calls"
  assert_rules_cleaned "$state"
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
  assert_rules_cleaned "$state"
  assert_positive_accepted_request_ids "$state"

  run_with_deadline delayed delayed 8
  state="$fixture_root/delayed"
  jq -e '.parked == true' "$state/stdout" >/dev/null
  assert_positive_accepted_request_ids "$state"

  FAKE_COMPOSITOR_MAP=false run_with_deadline compositor-map-failure match 8 || true
  state="$fixture_root/compositor-map-failure"
  test ! -e "$state/agent-target"
  test "$(cat "$state/closed-targets")" = agent-target
  assert_rules_cleaned "$state"

  if run_with_deadline operator-disappearance operator-disappears 8; then
    printf 'operator disappearance during creation unexpectedly succeeded\n' >&2
    exit 1
  fi
  state="$fixture_root/operator-disappearance"
  test ! -e "$state/agent-target"
  test "$(cat "$state/closed-targets")" = agent-target
  test ! -e "$state/navigated-url"
  grep -Fq 'compositor state changed after CDP target creation' "$state/stderr" ||
    grep -Fq 'focused compositor client disappeared after CDP target creation' "$state/stderr"
  assert_rules_cleaned "$state"

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
    assert_rules_cleaned "$state"
  done

  FAKE_FOCUS_CHANGE=true run_with_deadline focus-change match 8
  state="$fixture_root/focus-change"
  test -e "$state/agent-target"
  test ! -s "$state/closed-targets"
  test "$(cat "$state/active-window")" = 0xoperator
  test "$(cat "$state/focus-workspace-actions")" = 'dispatch focuswindow address:0xoperator'
  assert_rules_cleaned "$state"
  ;;
*)
  printf 'usage: %s [reproduce|final]\n' "$0" >&2
  exit 2
  ;;
esac
