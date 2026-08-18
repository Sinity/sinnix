#!/usr/bin/env bash
# Provably fails when: the plugin stops accepting the schema the ops reducer
# stamps (verified by changing SCHEMA in the reducer), stops resuming the SSE
# stream, gains a direct shell-out or state read, or fails Noctalia's own
# plugin lint.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
plugin="${NOCTALIA_OPS_PLUGIN:-$repo_root/dots/noctalia/plugins/sinnix-ops}"
reducer_root="${NOCTALIA_OPS_REDUCER:-$repo_root/pkgs/sinnix-ops-reducer}"

test -f "$plugin/plugin.toml"
test -f "$plugin/service.luau"
test -f "$plugin/bar.luau"
test -f "$plugin/panel.luau"
noctalia plugins lint "$plugin"

# Protocol agreement with the producer: the plugin must accept exactly the
# schema the ops reducer stamps on its payloads, and must resume the stream
# the way the reducer's SSE handler expects. Both sides are read from their
# own source, so this is an agreement between two components rather than a
# literal restated from one.
schema="$(sed -n 's/^SCHEMA = "\(.*\)"$/\1/p' "$reducer_root/sinnix_ops_reducer/__init__.py")"
test -n "$schema"
grep -Fq "$schema" "$plugin/service.luau" ||
  {
    echo "plugin does not accept the reducer's payload schema ($schema)" >&2
    exit 1
  }
resume_header="$(grep -o 'Last-Event-ID' "$reducer_root/sinnix_ops_reducer/server.py" | head -n1)"
test -n "$resume_header"
grep -Fq "$resume_header" "$plugin/service.luau" ||
  {
    echo "plugin does not resume the stream with $resume_header" >&2
    exit 1
  }

# The bridge is the plugin's only authority: a shell-out or a direct read of
# estate state would be a second, unbounded control plane in the shell.
! grep -Eq 'systemctl|jq|curl|sqlite|\.jsonl' "$plugin"/*.luau
echo "noctalia ops bridge fixture passed"
