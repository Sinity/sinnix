#!/usr/bin/env bash
# The backend adapter agentctl queues for a batch worker, reviewer or integrator:
# one prompt file, one backend invocation, optionally one structured result.
set -euo pipefail

agent=""
workdir=""
prompt_file=""
last_file=""
model=""
reasoning_effort=""
credential_profile="subscription"
resume_session_id=""
output_schema=""

usage() {
  cat <<'EOF'
Usage: run_agent_prompt.sh --agent <backend> --workdir <path> --prompt-file <path> --last-file <path> --model <model> --reasoning-effort <effort> [--credential-profile subscription|api] [--resume-session-id <id>] [--output-schema <file>]

This is agentctl's private backend adapter. pueue owns the job's identity, log,
result, cancellation and timeout; this script only builds the backend argv.
With --output-schema the backend's final message is JSON conforming to that
schema and is written to the last file (claude, codex, pi).
--resume-session-id is honoured by claude and codex; any other backend
refuses it rather than silently starting a fresh session.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
  --agent)
    agent="${2:?missing backend}"
    shift 2
    ;;
  --workdir)
    workdir="${2:?missing workdir}"
    shift 2
    ;;
  --prompt-file)
    prompt_file="${2:?missing prompt file}"
    shift 2
    ;;
  --last-file)
    last_file="${2:?missing result file}"
    shift 2
    ;;
  --model)
    model="${2:?missing model}"
    shift 2
    ;;
  --reasoning-effort)
    reasoning_effort="${2:?missing effort}"
    shift 2
    ;;
  --credential-profile)
    credential_profile="${2:?missing credential profile}"
    shift 2
    ;;
  --resume-session-id)
    resume_session_id="${2:?missing native session id}"
    shift 2
    ;;
  --output-schema)
    output_schema="${2:?missing schema file}"
    shift 2
    ;;
  -h | --help)
    usage
    exit 0
    ;;
  *)
    echo "unknown option: $1" >&2
    usage >&2
    exit 2
    ;;
  esac
done

[[ -n $agent && -n $workdir && -n $prompt_file && -n $last_file && -n $model && -n $reasoning_effort ]] || {
  usage >&2
  exit 2
}
[[ -d $workdir && -r $prompt_file ]] || {
  echo "workdir or prompt is unavailable" >&2
  exit 2
}
[[ $credential_profile == subscription || $credential_profile == api ]] || {
  echo "invalid credential profile" >&2
  exit 2
}
[[ $reasoning_effort =~ ^(low|medium|high|xhigh)$ ]] || {
  echo "invalid reasoning effort: $reasoning_effort (low|medium|high|xhigh)" >&2
  exit 2
}
[[ -z $output_schema || -r $output_schema ]] || {
  echo "output schema is unreadable: $output_schema" >&2
  exit 2
}
# Only codex and claude carry a native session reference this adapter can hand
# back. Every other backend would start a fresh session with the caller still
# believing the earlier context was restored, so a resume request it cannot
# honour is a refusal, never a silent downgrade.
if [[ -n $resume_session_id && $agent != codex && $agent != claude ]]; then
  echo "$agent cannot resume a native session; drop --resume-session-id" >&2
  exit 2
fi
mkdir -p "$(dirname "$last_file")"
# The contract runner keeps the private prompt input alive for the duration of
# this native backend. Expose the exact snapshot path to worker-side tools;
# lane task can therefore print it without copying prompt content into public
# job metadata.
export AGENTCTL_JOB_PROMPT_FILE="$prompt_file"

resolve_agent_bin() {
  case "$1" in
  claude) command -v claude-full 2>/dev/null || command -v claude 2>/dev/null ;;
  codex | gemini | pi) command -v "$1" ;;
  grok) command -v grok-sinnix 2>/dev/null || command -v grok ;;
  antigravity) command -v agy-sinnix 2>/dev/null || command -v agy ;;
  *) return 1 ;;
  esac
}

agent_bin="$(resolve_agent_bin "$agent")" || {
  echo "$agent runtime not found" >&2
  exit 1
}
cd "$workdir"

# claude --output-format json prints a result envelope whose `structured_output`
# holds the schema-conforming object; the last file receives only that object
# so every backend leaves the same document. stdout may carry several JSON
# documents (a stream, a retry, an earlier envelope): the last successful
# result envelope wins, and only when none exists does the run fail.
unwrap_claude_json() {
  python3 -c '
import json, sys
limit = 8 * 1024 * 1024
raw = sys.stdin.buffer.read(limit + 1)
sys.stdout.buffer.write(raw)
if len(raw) > limit:
    sys.exit("claude result exceeds 8 MiB")
def documents(text):
    decoder = json.JSONDecoder()
    position = 0
    while True:
        while position < len(text) and text[position].isspace():
            position += 1
        if position >= len(text):
            return
        try:
            item, end = decoder.raw_decode(text, position)
        except json.JSONDecodeError:
            return
        yield item
        position = end

def envelopes(item):
    if isinstance(item, list):
        for member in item:
            yield from envelopes(member)
    elif isinstance(item, dict):
        yield item

candidates = [
    item
    for document in documents(raw.decode("utf-8", "replace"))
    for item in envelopes(document)
    if item.get("type") == "result"
    and item.get("subtype") == "success"
    and item.get("is_error") is False
    and item.get("structured_output", item.get("result")) is not None
]
if not candidates:
    sys.exit("claude did not return a successful result envelope")
document = candidates[-1]
value = document.get("structured_output", document.get("result"))
if isinstance(value, str):
    try:
        value = json.loads(value)
    except json.JSONDecodeError:
        print("claude result is not JSON: " + value[:200], file=sys.stderr)
        sys.exit(1)
if not isinstance(value, dict):
    sys.exit("claude structured result is not an object")
with open(sys.argv[1], "w") as handle:
    json.dump(value, handle, indent=2)
' "$structured_file"
}

# Pi's `--mode json` is an LF-framed JSON event stream (one `JSON.stringify`
# per line). The extractor relays every byte to stdout as it arrives -- pueue's
# log is the run's live transcript -- while parsing incrementally and keeping
# only the terminal `agent_end` event's final assistant text.
#
# Framing is on b"\n" and nothing else. Python's str.splitlines() also breaks on
# U+2028, U+2029, U+0085, \v and \f; JSON.stringify escapes the C0 controls but
# emits U+2028/U+2029/U+0085 raw inside strings, so a line-splitting reader
# shreds a perfectly valid event, drops both halves as unparseable, and silently
# falls back to an earlier -- stale -- agent_end. Frame on bytes, then decode.
#
# The total stream is unbounded: a long run that ended well must not be failed
# for the size of its own log. Only one record is bounded, because an unframed
# record is the only thing that can grow without limit in memory.
#
# $1 is "object" when --output-schema was requested (the final text must be one
# JSON object) and "text" otherwise. Pi exposes no provider-enforced schema, so
# AgentCTL's ordinary batch-result validation remains the schema authority.
extract_pi_result() {
  python3 -c '
import json, sys

RECORD_LIMIT = 16 * 1024 * 1024
CHUNK = 1 << 16

destination, shape = sys.argv[1], sys.argv[2]
source = sys.stdin.buffer
relay = sys.stdout.buffer

pending = bytearray()
terminal = None
unparsed = 0


def consume(record):
    global terminal, unparsed
    if not record.strip():
        return
    try:
        event = json.loads(record.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        unparsed += 1
        return
    if isinstance(event, dict) and event.get("type") == "agent_end":
        terminal = event


while True:
    # read1 returns as soon as bytes are available; a plain read() would block
    # for a full chunk and defeat the incremental relay.
    chunk = source.read1(CHUNK) if hasattr(source, "read1") else source.read(CHUNK)
    if not chunk:
        break
    relay.write(chunk)
    relay.flush()
    pending += chunk
    start = 0
    while True:
        index = pending.find(b"\n", start)
        if index < 0:
            break
        consume(bytes(pending[start:index]))
        start = index + 1
    if start:
        del pending[:start]
    if len(pending) > RECORD_LIMIT:
        sys.exit("pi emitted a single event larger than 16 MiB")

# A trailing record without its newline means pi died mid-write; it still
# parses if it happened to be complete.
if pending:
    consume(bytes(pending))

if unparsed:
    print("pi: %d unparseable event line(s) ignored" % unparsed, file=sys.stderr)

if terminal is None:
    sys.exit("pi did not emit a terminal agent_end event")

text = None
failure = None
for message in terminal.get("messages") or []:
    if not isinstance(message, dict) or message.get("role") != "assistant":
        continue
    content = message.get("content")
    if isinstance(content, str):
        body = content
    elif isinstance(content, list):
        body = "".join(
            part.get("text", "")
            for part in content
            if isinstance(part, dict) and part.get("type") == "text"
        )
    else:
        continue
    # `pi --mode json` exits 0 even when the final turn errored or was aborted;
    # only the message carries that. Refuse rather than ship its partial text.
    if message.get("stopReason") in ("error", "aborted"):
        failure = message.get("errorMessage") or str(message.get("stopReason"))
        text = None
        continue
    if body.strip():
        text = body
        failure = None

if failure is not None:
    sys.exit("pi final assistant message failed: " + failure)
if text is None:
    sys.exit("pi did not return a final assistant message")

if shape == "object":
    try:
        value = json.loads(text)
    except ValueError as error:
        sys.exit("pi result is not JSON: " + str(error))
    if not isinstance(value, dict):
        sys.exit("pi structured result is not an object")
    payload = json.dumps(value, indent=2)
else:
    payload = text if text.endswith("\n") else text + "\n"

with open(destination, "w") as handle:
    handle.write(payload)
' "$structured_file" "$1"
}

# Run a pipeline and exit with the producer's status when it failed, else
# the consumer's.
pipeline_status() {
  local producer=$1 consumer=$2
  if ((producer != 0)); then
    exit "$producer"
  fi
  exit "$consumer"
}

case "$agent" in
codex)
  codex_args=(exec -C "$workdir" --model "$model" --output-last-message "$last_file")
  if [[ -n $output_schema ]]; then
    codex_args+=(--output-schema "$output_schema")
  fi
  if [[ -n $resume_session_id ]]; then
    codex_args+=(resume "$resume_session_id")
  fi
  exec "$agent_bin" "${codex_args[@]}" \
    -c "model_reasoning_effort=\"$reasoning_effort\"" \
    -c shell_environment_policy.inherit=all \
    - <"$prompt_file"
  ;;
claude)
  resume_args=()
  if [[ -n $resume_session_id ]]; then
    resume_args=(--resume "$resume_session_id")
  fi
  # The prompt goes in on stdin: one argv string is capped at 128 KiB by the
  # kernel and a resume packet with the bead bodies exceeds it.
  claude_args=("${resume_args[@]}" --print --model "$model" --effort "$reasoning_effort")
  if [[ -n $output_schema ]]; then
    # --json-schema takes the schema text, not a path.
    claude_args+=(--output-format json --json-schema "$(<"$output_schema")")
  fi
  if [[ $credential_profile == subscription ]]; then
    claude_cmd=(env -u ANTHROPIC_API_KEY "$agent_bin")
  else
    claude_cmd=("$agent_bin")
  fi
  set +e
  if [[ -n $output_schema ]]; then
    structured_file="$(mktemp "${last_file}.XXXXXX")" || exit 1
    trap 'rm -f -- "$structured_file"' EXIT
    "${claude_cmd[@]}" "${claude_args[@]}" <"$prompt_file" | unwrap_claude_json
  else
    "${claude_cmd[@]}" "${claude_args[@]}" <"$prompt_file" | tee "$last_file"
  fi
  statuses=("${PIPESTATUS[@]}")
  set -e
  if [[ -n $output_schema && ${statuses[0]} -eq 0 && ${statuses[1]} -eq 0 ]]; then
    if [[ ! -s $structured_file ]]; then
      echo "claude exited 0 without a structured result" >&2
      exit 1
    fi
    mv -f -- "$structured_file" "$last_file"
  fi
  pipeline_status "${statuses[0]}" "${statuses[1]}"
  ;;
pi)
  # `pi` is the managed subscription-only wrapper: it pins the OpenAI Codex
  # OAuth provider and refuses a --provider or --api-key override, so this
  # adapter must not pass either. JSON mode keeps the whole event stream in the
  # pueue log while the last file receives only the final assistant text,
  # exactly like every other backend's last file.
  pi_args=(--mode json --model "$model" --thinking "$reasoning_effort")
  structured_file="$(mktemp "${last_file}.XXXXXX")" || exit 1
  if [[ -n $output_schema ]]; then
    prompt_with_schema="$(mktemp "${prompt_file}.pi.XXXXXX")" || exit 1
    trap 'rm -f -- "$structured_file" "$prompt_with_schema"' EXIT
    {
      cat "$prompt_file"
      printf '\n\nReturn only one JSON object conforming exactly to this JSON Schema. Do not use Markdown fences or prose.\n\n%s\n' "$(<"$output_schema")"
    } >"$prompt_with_schema"
    pi_input="$prompt_with_schema"
    pi_shape=object
  else
    trap 'rm -f -- "$structured_file"' EXIT
    pi_input="$prompt_file"
    pi_shape=text
  fi
  set +e
  # Pi reads piped stdin and *prepends* it to the prompt, and blocks until EOF
  # when stdin is not a TTY. The prompt is the @file; stdin must be empty and
  # already at EOF or a queued job can hang before it ever prompts.
  "$agent_bin" "${pi_args[@]}" "@$pi_input" </dev/null | extract_pi_result "$pi_shape"
  statuses=("${PIPESTATUS[@]}")
  set -e
  if [[ ${statuses[0]} -eq 0 && ${statuses[1]} -eq 0 ]]; then
    if [[ ! -s $structured_file ]]; then
      echo "pi exited 0 without a final assistant message" >&2
      exit 1
    fi
    mv -f -- "$structured_file" "$last_file"
  fi
  pipeline_status "${statuses[0]}" "${statuses[1]}"
  ;;
gemini)
  "$agent_bin" <"$prompt_file" | tee "$last_file"
  ;;
grok)
  "$agent_bin" --cwd "$workdir" --single "$(<"$prompt_file")" --model "$model" --reasoning-effort "$reasoning_effort" | tee "$last_file"
  ;;
antigravity)
  "$agent_bin" --model "$model" --effort "$reasoning_effort" --print "$(<"$prompt_file")" | tee "$last_file"
  ;;
esac
