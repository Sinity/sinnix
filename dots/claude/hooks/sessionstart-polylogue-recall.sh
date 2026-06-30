#!/usr/bin/env bash
# SessionStart hook — emits a brief preamble of recent activity in the
# current project directory, sourced from polylogue.
#
# polylogue is local; if the binary or archive is unavailable we exit
# silently rather than disrupting session start.

set -euo pipefail

cwd="${CLAUDE_PROJECT_DIR:-$PWD}"

if ! command -v polylogue >/dev/null 2>&1; then
  exit 0
fi

# Most recent 3 conversations that referenced files under this cwd.
# `--path` matches paths in tool_use records, which in practice covers
# any session that did file I/O in this directory. Sessions that did
# pure text chat with no file ops won't match — accepted limitation
# until cwd-prefix filter lands.
# Query-first CLI: the `list` verb was removed; recent sessions are now
# `read --all` over the cwd-prefix-filtered, date-sorted selection.
output=$(polylogue --plain --cwd-prefix "$cwd" --sort date --limit 3 read --all 2>/dev/null || true)

if [ -z "$output" ]; then
  exit 0
fi

cat <<EOF
## Recent polylogue sessions in $cwd

$output

(Use the polylogue MCP server for deeper queries: \`list_sessions\`,
\`get_session\`, \`search\`, \`find_resume_candidates\`, \`get_recovery_report\`.)
EOF
