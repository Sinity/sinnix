#!/usr/bin/env bash
set -euo pipefail
if [ -x /home/sinity/.local/bin/agent-verify ]; then
  /home/sinity/.local/bin/agent-verify --quiet >/dev/null 2>&1 || true
fi
