#!/usr/bin/env bash
set -euo pipefail

if [ $# -lt 3 ]; then
  echo "Usage: $0 <workdir> <prompt_dir> <Agent...>" >&2
  exit 2
fi

workdir="$1"
prompt_dir="$2"
shift 2

if ! command -v kitty >/dev/null 2>&1; then
  echo "kitty not found on PATH" >&2
  exit 1
fi

if [ -z "${KITTY_LISTEN_ON:-}" ]; then
  echo "KITTY_LISTEN_ON is not set; run inside Kitty or export it." >&2
  exit 1
fi

for agent in "$@"; do
  prompt_file="$prompt_dir/${agent}.prompt"
  log_file="$prompt_dir/${agent}.md"

  if [ ! -f "$prompt_file" ]; then
    echo "Missing prompt file: $prompt_file" >&2
    exit 1
  fi

  if [ ! -f "$log_file" ]; then
    : >"$log_file"
  fi

  kitty @ launch --type=tab --tab-title "$agent" --cwd "$workdir" -- \
    zsh -lc "codex exec -C \"$workdir\" \"$(cat "$prompt_file")\""

  sleep 0.2
done
