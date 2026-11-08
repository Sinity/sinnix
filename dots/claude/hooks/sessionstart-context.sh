#!/usr/bin/env bash
# SessionStart hook for Claude Code and Codex: one context block, most useful
# first.
#
#   1. Polylogue's session-start brief (`polylogue hook SessionStart`, which
#      also records the event in Polylogue's hook spool). After compaction it
#      is Polylogue's compaction recipe.
#   2. What on the machine needs attention (`sinnix status --attention`):
#      failed or stuck units, failing health lanes, undelivered desktop
#      notices, and the services that are down on purpose (so a fresh session
#      does not report an intentional outage as a finding). Silent when the
#      machine is healthy.
#   3. Sinex: its search index when it is far behind, sources that recorded
#      something in the last two hours, and sources that went quiet (events in
#      the last 7 days but none in the last 24 hours). Names and times only,
#      never captured content.
#
# Parts 2 and 3 describe the machine, so they come only on a new session
# (`startup`, `clear`), not on `resume` or `compact`.
#
# One block, because a harness shows each hook's context separately and
# persists an oversized one to a file with only a short preview inline
# (Claude Code 2.1.316: over 10,000 characters, 2 KB preview). The parts run
# in parallel, so the block takes as long as the slowest part; Polylogue
# bounds its own wait for the daemon below the harness hook timeout.
#
# Every part fails open: a missing tool, a stopped daemon or a timeout drops
# that part and never the session start.
#
# Usage: sessionstart-context.sh [claude-code|codex]   (the event on stdin)

set -uo pipefail

harness=${1:-claude-code}
payload=$(cat)
source=$(printf '%s' "$payload" | jq -r '.source // "startup"' 2>/dev/null || true)

work=$(mktemp -d) || exit 0
trap 'rm -rf "$work"' EXIT

if command -v polylogue >/dev/null 2>&1; then
  printf '%s' "$payload" | polylogue hook SessionStart --harness "$harness" >"$work/brief" 2>/dev/null &
fi

if [ "$source" = startup ] || [ "$source" = clear ]; then
  if command -v sinnix >/dev/null 2>&1; then
    timeout 4s sinnix status --attention >"$work/outages" 2>/dev/null &
  fi
  if [ "${SINEX_SESSIONSTART_RECALL:-1}" != 0 ] && command -v sinexctl >/dev/null 2>&1; then
    timeout "${SINEX_SESSIONSTART_RECALL_TIMEOUT_SECS:-4}s" sinexctl --json status >"$work/sinex" 2>/dev/null &
  fi
fi

wait

brief=$(jq -r '.hookSpecificOutput.additionalContext // empty' "$work/brief" 2>/dev/null || true)
outages=$(cat "$work/outages" 2>/dev/null || true)
sinex=$(jq -r --argjson hours "${SINEX_SESSIONSTART_RECALL_HOURS:-2}" --argjson limit "${SINEX_SESSIONSTART_RECALL_LIMIT:-8}" '
  def epoch: sub("\\.[0-9]+"; "") | sub("\\+00:00$"; "Z") | fromdateiso8601;
  (now - $hours * 3600) as $since
  | (now - 86400) as $day | (now - 7 * 86400) as $week
  | ([.sources[]? | select(.last_event != null and (.last_event | epoch) >= $since)]
     | sort_by(.last_event) | reverse) as $fresh
  | ([.sources[]? | select(.last_event != null)
      | select((.last_event | epoch) < $day and (.last_event | epoch) >= $week)]
     | sort_by(.last_event) | reverse) as $quiet
  | (.search_index.behind // 0) as $behind
  | [
      (if $behind >= 1000 then
         "Sinex search index is \($behind) commits behind; search and follow answers lag."
       else empty end),
      (if ($quiet | length) > 0 then
         "Sinex sources gone quiet (events this week, none in 24h): "
         + ([$quiet[0:$limit][] | "\(.binding) last \(.last_event[0:16])"] | join(", "))
       else empty end),
      (if ($fresh | length) > 0 then
         "Sinex sources with events in the last \($hours)h, newest first (UTC): "
         + ([$fresh[0:$limit][] | "\(.binding) \(.last_event[11:16])"] | join(", "))
         + ". `sinex_recall` or `sinexctl recall` shows what they recorded."
       else empty end)
    ]
  | join("\n")
' "$work/sinex" 2>/dev/null || true)

context=""
for part in "$brief" "$outages" "$sinex"; do
  [ -n "$part" ] || continue
  if [ -n "$context" ]; then
    context+=$'\n\n'
  fi
  context+=$part
done

[ -n "$context" ] || exit 0

jq -n --arg context "$context" \
  '{hookSpecificOutput: {hookEventName: "SessionStart", additionalContext: $context}}'
