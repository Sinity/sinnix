#!/usr/bin/env bash
# SessionStart hook — tell the agent which services are down ON PURPOSE.
#
# Without this, every fresh session that looks at the machine rediscovers an
# intentional outage as an emergency and reports it as a finding. The
# acknowledgements live in the runtime inventory next to the surfaces they
# describe (sinnix.runtime.surfaces.<name>.acknowledged), so this hook is a
# read of declared state, not a second list to keep in sync.
#
# Silent when there is nothing acknowledged, and silent on any error: a
# session must never fail to start because a status preamble could not render.

set -euo pipefail

inventory="${SINNIX_RUNTIME_INVENTORY_FILE:-/etc/sinnix/runtime-inventory.json}"

command -v jq >/dev/null 2>&1 || exit 0
[ -r "$inventory" ] || exit 0

rows="$(jq -r '
  (.surfaces // {})
  | to_entries
  | map(select(.value.acknowledged.down == true))
  | .[]
  | "- \(.key) (\(.value.unit // "?")) — \(.value.acknowledged.reason // "no reason recorded") [since \(.value.acknowledged.since // "?"), ref \(.value.acknowledged.ref // "?")]"
' "$inventory" 2>/dev/null || true)"

[ -n "$rows" ] || exit 0

printf '## Acknowledged outages (known-down, do not re-report as incidents)\n\n%s\n\n' "$rows"
printf 'These are declared in the runtime inventory with a tracking reference. Treat them as\nexpected state. If one looks stale, check its reference rather than raising it as new.\n'
