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
schema and is written to the last file (claude, codex).
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
mkdir -p "$(dirname "$last_file")"
# The contract runner keeps the private prompt input alive for the duration of
# this native backend. Expose the exact snapshot path to worker-side tools;
# lane task can therefore print it without copying prompt content into public
# job metadata.
export AGENTCTL_JOB_PROMPT_FILE="$prompt_file"

resolve_agent_bin() {
  case "$1" in
  claude) command -v claude-full 2>/dev/null || command -v claude 2>/dev/null ;;
  codex | gemini) command -v "$1" ;;
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

# claude --output-format json prints one envelope whose `structured_output`
# holds the schema-conforming object; the last file receives only that object
# so every backend leaves the same document. Only a successful result envelope
# may produce a result; diagnostics belong on stderr.
unwrap_claude_json() {
  python3 -c '
import json, sys
limit = 8 * 1024 * 1024
raw = sys.stdin.buffer.read(limit + 1)
sys.stdout.buffer.write(raw)
if len(raw) > limit:
    sys.exit("claude result exceeds 8 MiB")
try:
    document = json.loads(raw)
except json.JSONDecodeError:
    sys.exit("claude stdout is not one JSON envelope; inspect the captured output")
if isinstance(document, list):
    envelopes = [item for item in document if isinstance(item, dict) and item.get("type") == "result"]
    if len(envelopes) != 1 or document[-1] != envelopes[0]:
        sys.exit("claude did not return exactly one terminal result envelope")
    document = envelopes[0]
if not isinstance(document, dict) or document.get("type") != "result" or document.get("subtype") != "success" or document.get("is_error") is not False:
    sys.exit("claude did not return a successful result envelope")
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
  claude_args=("${resume_args[@]}" --print -p "$(<"$prompt_file")" --model "$model" --effort "$reasoning_effort")
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
    "${claude_cmd[@]}" "${claude_args[@]}" | unwrap_claude_json
  else
    "${claude_cmd[@]}" "${claude_args[@]}" | tee "$last_file"
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
