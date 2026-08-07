#!/usr/bin/env bash
set -euo pipefail

scanner=${1:?scanner path}
root=$(mktemp -d)
trap 'rm -rf "$root"' EXIT
mkdir -p "$root/local/.claude" "$root/global/.claude" "$root/suspicious/.claude" "$root/secret/.claude"
cat > "$root/local/.claude/settings.json" <<EOF
{"env":{"LOCAL":"$root/local/cache"}}
EOF
cat > "$root/global/.claude/settings.json" <<'EOF'
{"env":{"CACHE":"/realm/data/shared-cache"}}
EOF
cat > "$root/suspicious/.claude/settings.json" <<'EOF'
{"env":{"CLOUD":"/tmp/cloud-only-path"}}
EOF
cat > "$root/secret/.claude/settings.json" <<'EOF'
{"env":{"API_TOKEN":"super-secret-value"}}
EOF

set +e
report=$(python3 "$scanner" --root "$root" --intentional-prefix /realm/data)
status=$?
set -e
test "$status" -eq 2
printf '%s' "$report" | jq -e '
  .schema == "sinnix-settings-env-lint-v1"
  and .unexplained_count == 1
  and ([.findings[] | select(.value_class == "repository_local")] | length) == 1
  and ([.findings[] | select(.value_class == "host_global_intentional")] | length) == 1
  and ([.findings[] | select(.value_class == "suspicious_cross_host")] | length) == 1
  and ([.findings[] | select(.key == "API_TOKEN" and .value_class == "secret_valued" and .value_redacted == true and (has("value") | not))] | length) == 1
' >/dev/null

set +e
clean=$(python3 "$scanner" --root "$root" --intentional-prefix /realm/data --intentional-prefix /tmp/cloud-only-path)
status=$?
set -e
test "$status" -eq 0
printf '%s' "$clean" | jq -e '.unexplained_count == 0 and ([.findings[] | select(.value_class == "host_global_intentional")] | length) == 2' >/dev/null
echo 'settings-env-lint fixture passed'
