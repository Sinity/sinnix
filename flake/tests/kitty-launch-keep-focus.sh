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
  printf 'ok\n'
  exit 0
fi
printf '%s\n' "$*" >>"$HYPR_LOG"
EOF

cat >"$test_root/bin/kitty" <<'EOF'
#!/usr/bin/env bash
printf '%s\n' "$*" >>"$KITTY_TEST_LOG"
if [[ $* == *launch* ]]; then
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
