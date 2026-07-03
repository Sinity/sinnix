#!/usr/bin/env bash
set -euo pipefail

if ! command -v bd >/dev/null 2>&1; then
  exit 0
fi

if ! bd where >/dev/null 2>&1; then
  exit 0
fi

exec bd prime "$@"
