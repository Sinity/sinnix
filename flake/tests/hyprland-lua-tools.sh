#!/usr/bin/env bash
set -euo pipefail

chrome=$1
hypr=$2
keyboard=$3
grid=$4
fixture_bin=$TMPDIR/bin
calls=$TMPDIR/hyprctl-calls
mkdir -p "$fixture_bin"

printf '#!%s\n' "$(command -v bash)" >"$fixture_bin/hyprctl"
cat >>"$fixture_bin/hyprctl" <<'EOF'
set -euo pipefail
printf '%s\n' "$*" >> "$HYPRCTL_CALLS"
case "$*" in
  "instances -j") printf '%s\n' '[{"instance":"fixture"}]' ;;
  "activeworkspace -j") printf '%s\n' '{"name":"1"}' ;;
  "eval "*) printf '%s\n' ok ;;
  *) printf 'unexpected hyprctl call: %s\n' "$*" >&2; exit 1 ;;
esac
EOF
printf '#!%s\n' "$(command -v bash)" >"$fixture_bin/wtype"
cat >>"$fixture_bin/wtype" <<'EOF'
cat >/dev/null
EOF
chmod +x "$fixture_bin/hyprctl" "$fixture_bin/wtype"
export HYPRCTL_CALLS=$calls

PATH="$fixture_bin:$PATH" "$hypr" focus-window 'address:0xabc' >/dev/null
PATH="$fixture_bin:$PATH" "$hypr" dispatch 'hl.dsp.focus({ workspace = 3 })' >/dev/null
PATH="$fixture_bin:$PATH" "$keyboard" type --text fixture --window 'address:0xabc' >/dev/null
PATH="$fixture_bin:$PATH" "$chrome" toggle-agent-workspace >/dev/null

expected=$TMPDIR/expected-hyprctl-calls
cat >"$expected" <<'EOF'
eval hl.dispatch(hl.dsp.focus({ window = "address:0xabc" }))
eval hl.dispatch(hl.dsp.focus({ workspace = 3 }))
eval hl.dispatch(hl.dsp.focus({ window = "address:0xabc" }))
instances -j
activeworkspace -j
eval hl.dispatch(hl.dsp.focus({ workspace = "name:agentbrowser" }))
EOF
cmp "$expected" "$calls"

PYTHONDONTWRITEBYTECODE=1 python - "$grid" <<'PY'
import importlib.machinery
import importlib.util
import sys

loader = importlib.machinery.SourceFileLoader("kitty_grid", sys.argv[1])
spec = importlib.util.spec_from_loader(loader.name, loader)
module = importlib.util.module_from_spec(spec)
loader.exec_module(module)
calls = []
module.run = lambda args, **kwargs: calls.append(list(args))
module.apply_layout([({"address": "0xabc"}, 10, 20, 300, 400)], "work space")
assert calls == [
    ["hyprctl", "eval", 'hl.dispatch(hl.dsp.window.float({ action = "set", window = "address:0xabc" }))'],
    ["hyprctl", "eval", 'hl.dispatch(hl.dsp.window.move({ workspace = "work space", follow = false, window = "address:0xabc" }))'],
    ["hyprctl", "eval", 'hl.dispatch(hl.dsp.window.resize({ x = 300, y = 400, window = "address:0xabc" }))'],
    ["hyprctl", "eval", 'hl.dispatch(hl.dsp.window.move({ x = 10, y = 20, window = "address:0xabc" }))'],
]
PY
