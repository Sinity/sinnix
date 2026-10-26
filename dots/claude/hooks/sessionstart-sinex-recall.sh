#!/usr/bin/env bash
# SessionStart hook — names the Sinex sources that recorded something recently.
#
# This must never block or make startup noisy. If sinexctl, jq or the daemon is
# unavailable, exit silently. It prints source names and times only, never
# captured content.

set -euo pipefail

if [ "${SINEX_SESSIONSTART_RECALL:-1}" = "0" ]; then
  exit 0
fi

if ! command -v sinexctl >/dev/null 2>&1 || ! command -v jq >/dev/null 2>&1; then
  exit 0
fi

hours="${SINEX_SESSIONSTART_RECALL_HOURS:-2}"
limit="${SINEX_SESSIONSTART_RECALL_LIMIT:-8}"
timeout_secs="${SINEX_SESSIONSTART_RECALL_TIMEOUT_SECS:-4}"

if command -v timeout >/dev/null 2>&1; then
  output=$(timeout "${timeout_secs}s" sinexctl --json status 2>/dev/null || true)
else
  output=$(sinexctl --json status 2>/dev/null || true)
fi

if [ -z "$output" ]; then
  exit 0
fi

rendered=$(printf '%s' "$output" | jq -r --argjson hours "$hours" --argjson limit "$limit" '
  def epoch: sub("\\.[0-9]+"; "") | sub("\\+00:00$"; "Z") | fromdateiso8601;
  (now - $hours * 3600) as $since
  | [.sources[]? | select(.last_event != null and (.last_event | epoch) >= $since)]
  | sort_by(.last_event) | reverse
  | if length == 0 then empty else
      "## Recent Sinex sources",
      "",
      ("Sources with events in the last \($hours)h, newest first:"),
      (.[0:$limit][] | "- \(.binding): last event \(.last_event[0:16] | sub("T"; " ")) UTC"),
      "",
      "(`sinexctl recall` shows what they recorded.)"
    end
' 2>/dev/null || true)

if [ -z "$rendered" ]; then
  exit 0
fi

printf '%s\n' "$rendered"
