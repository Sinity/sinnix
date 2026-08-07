#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
plugin="${NOCTALIA_OPS_PLUGIN:-$repo_root/dots/noctalia/plugins/sinnix-ops}"

test -f "$plugin/plugin.toml"
test -f "$plugin/service.luau"
test -f "$plugin/bar.luau"
test -f "$plugin/panel.luau"
noctalia plugins lint "$plugin"

grep -Fq 'httpStream' "$plugin/service.luau"
grep -Fq 'Last-Event-ID' "$plugin/service.luau"
grep -Fq 'sinnix-ops-v1' "$plugin/service.luau"
grep -Fq 'systemStats' "$plugin/service.luau"
grep -Fq 'sinity-ops.view' "$plugin/bar.luau"
grep -Fq 'panel.render' "$plugin/panel.luau"
! grep -Eq 'systemctl|jq|curl|sqlite|\.jsonl' "$plugin"/*.luau
echo "noctalia ops bridge fixture passed"
