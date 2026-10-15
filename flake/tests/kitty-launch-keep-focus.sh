#!/usr/bin/env bash
# Provably fails when: launch omits --keep-focus or --os-window-class for an
# OS window, or does not restore the previously focused Hyprland window after
# Kitty's existing OS window is activated.
set -euo pipefail

helper="$1"
test_root="$(mktemp -d)"
trap 'rm -rf "$test_root"' EXIT

mkdir -p "$test_root/bin"

cat >"$test_root/bin/hyprctl" <<'EOF'
#!/usr/bin/env bash
if [[ ${HYPR_TEST_MODE:-} == unavailable ]]; then
  echo 'compositor unavailable' >&2
  exit 1
fi
if [[ ${2:-} == status ]]; then
  printf '{"configProvider":"%s"}\n' "${HYPR_TEST_PROVIDER:-lua}"
  exit 0
fi
if [[ ${1:-} == activewindow ]]; then
  if [[ -f ${KITTY_TEST_LOG:-} ]] && grep -q -- '--keep-focus' "$KITTY_TEST_LOG" && { [[ ! -f ${HYPR_LOG:-} ]] || ! grep -q 'hl.dispatch' "$HYPR_LOG"; }; then
    printf '%s\n' '{"address":"0xgrok","class":"kitty","title":"grok"}'
  else
    printf '%s\n' '{"address":"0xchrome","class":"google-chrome","title":"ChatGPT"}'
  fi
  exit 0
fi
if [[ ${1:-} == eval ]]; then
  printf '%s\n' "$*" >>"$HYPR_LOG"
  case ${HYPR_TEST_MODE:-} in
    reject) echo 'rule rejected' >&2; exit 1 ;;
    error-response) echo 'Lua error: invalid rule'; exit 0 ;;
  esac
  printf 'ok\n'
  exit 0
fi
printf '%s\n' "$*" >>"$HYPR_LOG"
if [[ ${HYPR_TEST_MODE:-} == keyword-reject && ${2:-} == *:workspace ]]; then
  echo 'workspace rule rejected' >&2
  exit 1
fi
printf 'ok\n'
EOF

cat >"$test_root/bin/kitty" <<'EOF'
#!/usr/bin/env bash
printf '%s\n' "$*" >>"$KITTY_TEST_LOG"
if [[ ${*: -1} == ls ]]; then
  if [[ ${KITTY_TEST_EXISTING_AGENT:-} == yes ]]; then
    echo '[{"wm_class":"sinnix-agent-terminal","tabs":[{"windows":[{"id":99}]}]}]'
  else
    echo '[]'
  fi
elif [[ $* == *launch* ]]; then
  printf '42\n'
fi
EOF

chmod +x "$test_root/bin"/*
for fixture in "$test_root/bin"/*; do
  sed -i "1c#!$(command -v bash)" "$fixture"
done

export PATH="$test_root/bin:$PATH"
export XDG_RUNTIME_DIR="$test_root/runtime"
export USER=test
unset KITTY_LISTEN_ON KITTY_PID KITTY_WINDOW_ID
mkdir -p "$test_root/runtime"
export KITTY_TEST_LOG="$test_root/kitty.log"
export HYPR_LOG="$test_root/hypr.log"
: >"$KITTY_TEST_LOG"
: >"$HYPR_LOG"

"$helper" launch --type os-window --title agent-test --cwd "$test_root"

grep -F -- '--keep-focus' "$KITTY_TEST_LOG"
grep -F -- '--os-window-class sinnix-agent-terminal' "$KITTY_TEST_LOG"
grep -F -- '--type os-window' "$KITTY_TEST_LOG"
grep -F 'hl.dispatch(hl.dsp.focus({ window = "address:0xchrome" }))' "$HYPR_LOG"

# Any missing, unsupported or rejected placement rule refuses a fresh window.
for mode in unavailable reject error-response; do
  : >"$KITTY_TEST_LOG"
  if HYPR_TEST_MODE="$mode" "$helper" launch --type os-window >"$test_root/stdout" 2>"$test_root/stderr"; then
    echo "launch unexpectedly succeeded for $mode" >&2
    exit 1
  fi
  test ! -s "$KITTY_TEST_LOG"
  test -s "$test_root/stderr"
done
for provider in unsupported hyprlang; do
  : >"$KITTY_TEST_LOG"
  if HYPR_TEST_PROVIDER="$provider" HYPR_TEST_MODE=keyword-reject "$helper" launch --type os-window >"$test_root/stdout" 2>"$test_root/stderr"; then
    echo "launch unexpectedly succeeded for $provider" >&2
    exit 1
  fi
  test ! -s "$KITTY_TEST_LOG"
done

# A successful Hyprlang guard permits the normal launch too.
: >"$KITTY_TEST_LOG"
HYPR_TEST_PROVIDER=hyprlang "$helper" launch --type os-window
grep -F -- '--os-window-class sinnix-agent-terminal' "$KITTY_TEST_LOG"

# Existing graphical terminal tabs do not require installing a new OS-window rule.
: >"$KITTY_TEST_LOG"
HYPR_TEST_MODE=unavailable KITTY_TEST_EXISTING_AGENT=yes "$helper" launch --type tab
grep -F -- '--type tab --keep-focus --match window_id:99' "$KITTY_TEST_LOG"
: >"$KITTY_TEST_LOG"
HYPR_TEST_MODE=unavailable "$helper" send --match id:99 --text harmless
grep -F -- 'send-text --match id:99' "$KITTY_TEST_LOG"

# Requesting a tab without an existing agent window falls back to a guarded window.
: >"$KITTY_TEST_LOG"
if HYPR_TEST_MODE=unavailable "$helper" launch --type tab >"$test_root/stdout" 2>"$test_root/stderr"; then
  echo "unguarded fallback window unexpectedly launched" >&2
  exit 1
fi
! grep -q -- ' launch ' "$KITTY_TEST_LOG"
