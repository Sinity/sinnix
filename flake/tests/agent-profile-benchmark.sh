#!/usr/bin/env bash
# Provably fails when: the benchmark miscounts a profile's tools or samples
# (verified by double-counting duplicate tool names), or stops reporting
# provider usage as unavailable when no provider answered.
set -euo pipefail

benchmark=${1:?benchmark path}
root=$(mktemp -d)
trap 'rm -rf "$root"' EXIT
mkdir -p "$root/home/.config/claude/skills/demo" "$root/home/.codex" "$root/out"
printf 'standing instructions\n' >"$root/home/.config/claude/CLAUDE.md"
printf 'description: demo\n' >"$root/home/.config/claude/skills/demo/SKILL.md"
printf '{"mcpServers":{"demo":{}}}\n' >"$root/home/.config/claude/mcp.json"
cat >"$root/home/.codex/system-config.toml" <<'EOF'
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
  --codex-config "$root/home/.codex/system-config.toml" \
  --gateway-bin "bash $root/fake-gateway" \
  --profiles claude,codex,gateway-operator \
  --repeats 3 \
  --output "$root/out/raw.json" \
  --summary-output "$root/out/summary.json" >"$root/out/stdout.json"
jq -e '
  .schema == "sinnix-agent-profile-benchmark-v1"
  and (.profiles | keys == ["claude", "codex", "gateway-operator"])
  and .profiles["claude"].sample_count == 3
  and .profiles["gateway-operator"].sample_count == 3
  and .profiles["claude"].tool_count == 1
  and .profiles["codex"].tool_count == 1
  and .profiles["gateway-operator"].tool_count == 1
  and .recommendations.task_success_guard
  and (all(.profiles[]; has("wall_ns") and (has("cold_wall_ns") | not) and (has("warm_wall_ns") | not)))
' "$root/out/summary.json" >/dev/null
jq -e '(.schema == "sinnix-agent-profile-benchmark-v1") and ((.records | length) == 9) and all(.records[]; .provider_usage.status == "unavailable" and (has("phase") | not))' "$root/out/raw.json" >/dev/null

python3 - "$benchmark" "$root" <<'PYTEST'
import runpy
import sys
from pathlib import Path

module = runpy.run_path(sys.argv[1])
root = Path(sys.argv[2])
skills = root / "linked-skills"
skills.mkdir()
source = root / "source-skill"
source.mkdir()
(source / "SKILL.md").write_text("description: linked skill\n")
(skills / "directory-link").symlink_to(source, target_is_directory=True)
(skills / "file-link.md").symlink_to(source / "SKILL.md")
(source / "cycle").symlink_to(skills, target_is_directory=True)
assert module["files_under"](skills) == [
    skills / "directory-link" / "SKILL.md",
    skills / "file-link.md",
]
blocked = skills / "blocked"
blocked.mkdir()
blocked.chmod(0)
try:
    try:
        module["files_under"](skills)
    except PermissionError:
        pass
    else:
        raise AssertionError("unreadable skill subtree was silently omitted")
finally:
    blocked.chmod(0o700)
PYTEST
echo 'agent-profile-benchmark fixture passed'
