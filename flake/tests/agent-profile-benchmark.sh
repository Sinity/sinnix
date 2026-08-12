#!/usr/bin/env bash
set -euo pipefail

benchmark=${1:?benchmark path}
root=$(mktemp -d)
trap 'rm -rf "$root"' EXIT
mkdir -p "$root/home/.config/claude/skills/demo" "$root/home/.codex" "$root/out"
printf 'standing instructions\n' >"$root/home/.config/claude/CLAUDE.md"
printf 'description: demo\n' >"$root/home/.config/claude/skills/demo/SKILL.md"
printf '{"mcpServers":{"demo":{}}}\n' >"$root/home/.config/claude/mcp-lean.json"
cat >"$root/home/.codex/lean.config.toml" <<'EOF'
[mcp_servers.demo]
command = "demo"
EOF
cat >"$root/fake-gateway" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' '{"schema":"sinnix.gateway-tools.v1","tools":[{"name":"demo"}],"sha256":"fixture-manifest"}'
EOF
chmod +x "$root/fake-gateway"
python3 "$benchmark" \
  --home "$root/home" \
  --gateway-bin "bash $root/fake-gateway" \
  --profiles claude-lean,gateway-remote-readonly \
  --repeats 3 \
  --output "$root/out/raw.json" \
  --summary-output "$root/out/summary.json" >"$root/out/stdout.json"
jq -e '
  .schema == "sinnix-agent-profile-benchmark-v1"
  and (.profiles | keys == ["claude-lean", "gateway-remote-readonly"])
  and .profiles["claude-lean"].sample_count == 6
  and .profiles["gateway-remote-readonly"].sample_count == 6
  and .profiles["claude-lean"].tool_count == 1
  and .profiles["gateway-remote-readonly"].tool_count == 1
  and .recommendations.task_success_guard
' "$root/out/summary.json" >/dev/null
jq -e '(.schema == "sinnix-agent-profile-benchmark-v1") and ((.records | length) == 12) and all(.records[]; .provider_usage.status == "unavailable")' "$root/out/raw.json" >/dev/null
echo 'agent-profile-benchmark fixture passed'
