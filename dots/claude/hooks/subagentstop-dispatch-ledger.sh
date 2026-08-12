#!/usr/bin/env bash
# SubagentStop hook — appends a "dispatch_end" row to the fanout dispatch
# ledger (polylogue-u49yr), pairing with the "dispatch_start" row the
# PreToolUse(Agent) hook (pretooluse-agent-model.sh) writes on dispatch.
#
# Completion telemetry (duration, token usage, last-message size) is
# best-effort, derived from the subagent's own transcript_path when the
# SubagentStop payload carries one — the hook payload itself does not
# include these directly. Append-only, failure-silent: no `set -e`, every
# step degrades to null on parse failure, and the script always exits 0 so a
# broken ledger can never block subagent completion.
#
# Ledger: ~/.local/state/claude-code/dispatch-ledger.jsonl
# Reader recipes (jq) — see pretooluse-agent-model.sh header for the full set
# (by model / by session / inherited-model count). Pairing a dispatch_start
# with its dispatch_end is a session_id + nearest-timestamp join, e.g.:
#   jq -s 'group_by(.session_id) | map({session_id:.[0].session_id, starts:[.[]|select(.type=="dispatch_start")]|length, ends:[.[]|select(.type=="dispatch_end")]|length})' <ledger>
set -uo pipefail

LEDGER="${XDG_STATE_HOME:-${HOME}/.local/state}/claude-code/dispatch-ledger.jsonl"
mkdir -p "${LEDGER%/*}" 2>/dev/null || exit 0

INPUT=$(cat 2>/dev/null)
[[ -z ${INPUT:-} ]] && exit 0

# Candidate sampling is deliberately best-effort and synchronous only for a
# bounded local append. The judge runs separately so SubagentStop never waits
# on Claude transport or schema validation.
if command -v sinnix-vacuity-sampler >/dev/null 2>&1; then
  printf '%s' "$INPUT" | sinnix-vacuity-sampler enqueue >/dev/null 2>&1 || true
fi

SESSION_ID=$(jq -r '.session_id // "unknown"' <<<"$INPUT" 2>/dev/null)
[[ -z $SESSION_ID ]] && SESSION_ID="unknown"
TRANSCRIPT=$(jq -r '.transcript_path // empty' <<<"$INPUT" 2>/dev/null)

DURATION="null"
TOKENS="null"
LAST_MSG_SIZE="null"

if [[ -n ${TRANSCRIPT:-} && -r $TRANSCRIPT ]]; then
  # First/last timestamped transcript lines -> wall-clock duration (secs);
  # last message.usage -> token counts; last assistant message -> content
  # size as a proxy for "last-message size". Any shape mismatch -> nulls,
  # never an error.
  READ=$(jq -cs '
        def parse_ts: sub("\\.[0-9]+Z$"; "Z") | try fromdateiso8601 catch null;
        [ .[] | select(.timestamp != null) ] as $ts
        | (
            if ($ts | length) >= 2 then
              (($ts[-1].timestamp | parse_ts) as $end
               | ($ts[0].timestamp | parse_ts) as $start
               | if $end != null and $start != null then $end - $start else null end)
            else null end
          ) as $duration
        | ([ .[] | select(.message.usage != null) ] | last) as $last_usage
        | ([ .[] | select(.message.role == "assistant") ] | last) as $last_msg
        | {
            duration: $duration,
            tokens: ($last_usage.message.usage // null),
            last_message_size: (
              if $last_msg == null then null
              else ($last_msg.message.content | tostring | length)
              end
            )
          }
    ' "$TRANSCRIPT" 2>/dev/null)
  if [[ -n ${READ:-} ]]; then
    D=$(jq -r 'if .duration == null then "null" else (.duration|tostring) end' <<<"$READ" 2>/dev/null)
    T=$(jq -c '.tokens // null' <<<"$READ" 2>/dev/null)
    L=$(jq -r 'if .last_message_size == null then "null" else (.last_message_size|tostring) end' <<<"$READ" 2>/dev/null)
    [[ -n $D ]] && DURATION="$D"
    [[ -n $T ]] && TOKENS="$T"
    [[ -n $L ]] && LAST_MSG_SIZE="$L"
  fi
fi

# Braced so the `>> "$LEDGER"` open failure (e.g. unwritable dir) is also
# caught by the group's stderr redirect — a bare `cmd >> file 2>/dev/null`
# does NOT suppress that particular error, since bash reports a failed
# redirection before the command's own fd2 redirect takes effect.
{
  jq -nc \
    --arg type "dispatch_end" \
    --arg timestamp "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    --arg session_id "$SESSION_ID" \
    --argjson duration "$DURATION" \
    --argjson tokens "$TOKENS" \
    --argjson last_message_size "$LAST_MSG_SIZE" \
    '{type:$type, timestamp:$timestamp, session_id:$session_id, duration:$duration, tokens:$tokens, last_message_size:$last_message_size}' \
    >>"$LEDGER"
} 2>/dev/null

exit 0
