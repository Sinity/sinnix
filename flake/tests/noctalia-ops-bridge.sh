#!/usr/bin/env bash
# Provably fails when: the plugin stops accepting the schema the ops reducer
# stamps (verified by changing SCHEMA in the reducer), stops resuming the SSE
# stream, gains a direct shell-out or state read, fails Noctalia's own
# plugin lint, an entry stops parsing as Luau (verified 2026-08-18 by
# appending a malformed statement to bar-attention.luau: lint alone still
# said ok, the luau-compile pass failed with a SyntaxError), or the panel
# binds a snapshot state key the reducer does not publish (verified
# 2026-08-18 by binding stateValue("gpu") in panel.luau).
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
plugin="${NOCTALIA_OPS_PLUGIN:-$repo_root/dots/noctalia/plugins/sinnix-ops}"
reducer_root="${NOCTALIA_OPS_REDUCER:-$repo_root/pkgs/sinnix-ops-reducer}"
observe_root="${NOCTALIA_OPS_OBSERVE:-$repo_root/pkgs/sinnix-observe}"
contract="${NOCTALIA_OPS_CONTRACT:-$repo_root/flake/tests/noctalia-state-contract.py}"

test -f "$plugin/plugin.toml"
test -f "$plugin/service.luau"
test -f "$plugin/bar.luau"
test -f "$plugin/panel.luau"
noctalia plugins lint "$plugin"

# `noctalia plugins lint` cross-checks the manifest but does not compile Luau;
# parse every entry so a syntax error cannot ride a green check into the shell.
for entry in "$plugin"/*.luau; do
  luau-compile --binary "$entry" >/dev/null
done

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
# system state would be a second, unbounded control plane in the shell.
# (xdg-open of a hub page is deliberate: it hands a URL to the browser, it
# does not read or mutate system state.)
! grep -Eq 'systemctl|jq|curl|sqlite|\.jsonl' "$plugin"/*.luau

# Schema agreement with both producers: every snapshot state key the plugin
# binds must be published by sinnix-observe's report or the reducer's own
# state additions. Both sides are parsed from their source.
NOCTALIA_OPS_PLUGIN="$plugin" \
NOCTALIA_OPS_REDUCER="$reducer_root" \
NOCTALIA_OPS_OBSERVE="$observe_root" \
  python3 "$contract"
echo "noctalia ops bridge fixture passed"
