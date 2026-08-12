#!/usr/bin/env bash

set -euo pipefail

dots_dir="${1:?dots/noctalia directory required}"
test_root="$(mktemp -d)"
trap 'rm -rf "$test_root"' EXIT

mkdir -p "$test_root/config" "$test_root/state" "$test_root/.local/share/noctalia/pinned/official/timer" "$test_root/.local/share/noctalia/pinned/community/keybind-cheatsheet"
cp "$dots_dir/"*.toml "$test_root/config/"

cat >"$test_root/.local/share/noctalia/pinned/official/timer/plugin.toml" <<'EOF'
id = "noctalia/timer"
name = "Timer"
version = "1.2.0"
plugin_api = 3
[[service]]
id = "timer"
entry = "service.luau"
EOF

cat >"$test_root/.local/share/noctalia/pinned/community/keybind-cheatsheet/plugin.toml" <<'EOF'
id = "kenn/keybind-cheatsheet"
name = "Keybind Cheatsheet"
version = "0.2.1"
plugin_api = 9
[[panel]]
id = "cheatsheet"
entry = "panel.luau"
EOF

NOCTALIA_CONFIG_HOME="$test_root/config" \
  NOCTALIA_STATE_HOME="$test_root/state" \
  HOME="$test_root" \
  noctalia config validate
