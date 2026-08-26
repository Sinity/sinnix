#!/usr/bin/env bash
# Canonical implementation lives with the orchestrate skill.
exec "$(dirname "$0")/../../orchestrate/scripts/harvest_queue2.sh" "$@"
