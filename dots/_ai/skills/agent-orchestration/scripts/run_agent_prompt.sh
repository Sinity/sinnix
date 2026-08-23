#!/usr/bin/env bash
# Native backend translation for the Sinnixd attested-agent contract.
set -euo pipefail

agent=""
workdir=""
prompt_file=""
last_file=""
model=""
reasoning_effort=""
credential_profile="subscription"

usage() {
  cat <<'EOF'
Usage: run_agent_prompt.sh --agent <backend> --workdir <path> --prompt-file <path> --last-file <path> --model <model> --reasoning-effort <effort> [--credential-profile subscription|api]

This is Sinnixd's private backend adapter. AgentCTL owns job identity, logs,
results, cancellation, timeouts, workspaces, and durable records.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
  --agent) agent="${2:?missing backend}"; shift 2 ;;
  --workdir) workdir="${2:?missing workdir}"; shift 2 ;;
  --prompt-file) prompt_file="${2:?missing prompt file}"; shift 2 ;;
  --last-file) last_file="${2:?missing result file}"; shift 2 ;;
  --model) model="${2:?missing model}"; shift 2 ;;
  --reasoning-effort) reasoning_effort="${2:?missing effort}"; shift 2 ;;
  --credential-profile) credential_profile="${2:?missing credential profile}"; shift 2 ;;
  -h|--help) usage; exit 0 ;;
  *) echo "unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

[[ -n $agent && -n $workdir && -n $prompt_file && -n $last_file && -n $model && -n $reasoning_effort ]] || { usage >&2; exit 2; }
[[ -d $workdir && -r $prompt_file ]] || { echo "workdir or prompt is unavailable" >&2; exit 2; }
[[ $credential_profile == subscription || $credential_profile == api ]] || { echo "invalid credential profile" >&2; exit 2; }
mkdir -p "$(dirname "$last_file")"

resolve_agent_bin() {
  case "$1" in
  claude) command -v claude-full 2>/dev/null || command -v claude 2>/dev/null ;;
  codex|gemini) command -v "$1" ;;
  grok) command -v grok-sinnix 2>/dev/null || command -v grok ;;
  antigravity) command -v agy-sinnix 2>/dev/null || command -v agy ;;
  *) return 1 ;;
  esac
}

agent_bin="$(resolve_agent_bin "$agent")" || { echo "$agent runtime not found" >&2; exit 1; }
cd "$workdir"

case "$agent" in
codex)
  exec "$agent_bin" exec -C "$workdir" --model "$model" --output-last-message "$last_file" -c "model_reasoning_effort=\"$reasoning_effort\"" - < "$prompt_file"
  ;;
claude)
  if [[ $credential_profile == subscription ]]; then
    env -u ANTHROPIC_API_KEY "$agent_bin" --print -p "$(<"$prompt_file")" --model "$model" --effort "$reasoning_effort" | tee "$last_file"
  else
    "$agent_bin" --print -p "$(<"$prompt_file")" --model "$model" --effort "$reasoning_effort" | tee "$last_file"
  fi
  ;;
gemini)
  "$agent_bin" < "$prompt_file" | tee "$last_file"
  ;;
grok)
  "$agent_bin" --cwd "$workdir" --single "$(<"$prompt_file")" --model "$model" --reasoning-effort "$reasoning_effort" | tee "$last_file"
  ;;
antigravity)
  "$agent_bin" --model "$model" --effort "$reasoning_effort" --print "$(<"$prompt_file")" | tee "$last_file"
  ;;
esac
