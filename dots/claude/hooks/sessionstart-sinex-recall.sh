#!/usr/bin/env bash
# SessionStart hook — emits a compact Sinex machine-context preamble.
#
# This must never block or make startup noisy. If sinexctl, jq, the runtime
# target, or the daemon is unavailable, exit silently.

set -euo pipefail

if [ "${SINEX_SESSIONSTART_RECALL:-1}" = "0" ]; then
  exit 0
fi

if ! command -v sinexctl >/dev/null 2>&1 || ! command -v jq >/dev/null 2>&1; then
  exit 0
fi

cwd="${CLAUDE_PROJECT_DIR:-${CODEX_WORKING_DIR:-${PWD}}}"
sinex_root="${SINEX_ROOT:-/realm/project/sinex}"
window="${SINEX_SESSIONSTART_RECALL_WINDOW:-2h}"
limit="${SINEX_SESSIONSTART_RECALL_LIMIT:-8}"
timeout_secs="${SINEX_SESSIONSTART_RECALL_TIMEOUT_SECS:-4}"

target=""
probe="$cwd"
while [ -n "$probe" ] && [ "$probe" != "/" ]; do
  candidate="$probe/.sinex/state/runtime-target.json"
  if [ -r "$candidate" ]; then
    target="$candidate"
    break
  fi
  probe="${probe%/*}"
done

if [ -z "$target" ]; then
  if [ -n "${SINEX_RUNTIME_TARGET_CONFIG:-}" ] && [ -r "${SINEX_RUNTIME_TARGET_CONFIG}" ]; then
    target="${SINEX_RUNTIME_TARGET_CONFIG}"
  fi
fi

if [ -z "$target" ]; then
  if [ -z "$target" ] && [ -r "$sinex_root/.sinex/state/runtime-target.json" ]; then
    target="$sinex_root/.sinex/state/runtime-target.json"
  fi
fi

args=(recall --window "$window" --limit "$limit" --format json)
if [ -n "$target" ]; then
  args=(--runtime-target "$target" "${args[@]}")
fi

if command -v timeout >/dev/null 2>&1; then
  output=$(timeout "${timeout_secs}s" sinexctl "${args[@]}" 2>/dev/null || true)
else
  output=$(sinexctl "${args[@]}" 2>/dev/null || true)
fi

if [ -z "$output" ]; then
  exit 0
fi

rendered=$(printf '%s' "$output" | jq -r '
  def trunc($n): tostring | if length > $n then .[0:$n] + "..." else . end;
  .payload as $p
  | if ($p | type) != "object" then empty else
      [
        "## Recent Sinex machine context",
        "",
        ("Window: " + ($p.since // "unknown")
          + " | events: " + (($p.total_events // 0) | tostring)
          + " | sources: " + (($p.source_count // 0) | tostring)),
        (if (($p.sessions // []) | length) > 0
          then "Sessions:" else empty end),
        (($p.sessions // [])[0:2][]
          | "- " + ((.started_at // .latest_ts // "?") | tostring)
            + " " + (.event_type // "activity.session.boundary")
            + " ref " + (.ref.id // .ref.label // "-" | tostring)),
        (if (($p.sources // []) | length) > 0
          then "Sources:" else empty end),
        (($p.sources // [])[0:6][]
          | "- " + (.label // .source // "source")
            + ": " + (.latest_event.event_type // "?")
            + " @ " + (.latest_ts // "?")
            + " ref " + (.latest_event.ref.label // .latest_event.ref.id // "-" | tostring)
            + " — " + ((.latest_event.summary // "") | trunc(120))),
        (if (($p.source_caveats // []) | length) > 0
          then "Caveats:" else empty end),
        (($p.source_caveats // [])[0:3][]
          | "- " + (.id // "caveat") + ": " + ((.message // "") | trunc(160))),
        "",
        "(Use sinexctl recall/show or the Sinex MCP read role for resolvable refs.)"
      ] | map(select(. != null and . != "")) | .[]
    end
' 2>/dev/null || true)

if [ -z "$rendered" ]; then
  exit 0
fi

printf '%s\n' "$rendered"
