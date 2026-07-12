#!/usr/bin/env bash
set -euo pipefail

if ! command -v bd >/dev/null 2>&1; then
  exit 0
fi

# Best-effort: bd serializes on an embedded-Dolt lock; under a multi-agent
# fanout a queued `bd where`/`bd prime` can sit for minutes — a hook must
# never block the session on that.
if ! timeout 10 bd where >/dev/null 2>&1; then
  exit 0
fi

timeout 20 bd prime "$@" || exit 0
