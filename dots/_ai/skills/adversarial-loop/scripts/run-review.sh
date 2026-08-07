#!/usr/bin/env bash
# Run one adversarial review through the shared structured-judgment wrapper.
set -euo pipefail

usage() {
  printf 'usage: %s SCHEMA CONTEXT... -- PROMPT\n' "$0" >&2
}

[[ $# -ge 3 ]] || { usage; exit 64; }
schema=$1
shift
contexts=()
while [[ $# -gt 0 && $1 != -- ]]; do
  contexts+=(--context "$1")
  shift
done
[[ ${1:-} == -- ]] || { usage; exit 64; }
shift
[[ $# -gt 0 ]] || { usage; exit 64; }
exec sinnix-claude-judge --schema "$schema" "${contexts[@]}" -- "$*"
