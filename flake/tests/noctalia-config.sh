#!/usr/bin/env bash

set -euo pipefail

dots_dir="${1:?dots/noctalia directory required}"
test_root="$(mktemp -d)"
trap 'rm -rf "$test_root"' EXIT

mkdir -p "$test_root/config" "$test_root/state" "$test_root/.local/share/noctalia/pinned/official/timer"
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

NOCTALIA_CONFIG_HOME="$test_root/config" \
  NOCTALIA_STATE_HOME="$test_root/state" \
  HOME="$test_root" \
  noctalia config validate
