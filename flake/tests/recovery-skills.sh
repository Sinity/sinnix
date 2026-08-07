#!/usr/bin/env bash
set -euo pipefail
freeze=$1
recover=$2
test_root=$(mktemp -d)
trap 'rm -rf "$test_root"' EXIT
repo="$test_root/repo"
mkdir -p "$repo"
git -C "$repo" init -q
git -C "$repo" config user.email fixture@example.invalid
git -C "$repo" config user.name fixture
echo original >"$repo/artifact.txt"
git -C "$repo" add artifact.txt
git -C "$repo" commit -qm initial
git -C "$repo" branch snapshot-source
echo changed >"$repo/artifact.txt"
freeze_out="$test_root/freeze"
"$freeze" --repo "$repo" --out "$freeze_out" --conflict "$repo/artifact.txt" >/dev/null
jq -e '.schema_version == 1 and .head != "" and (.conflict_hashes | length) == 1' "$freeze_out/manifest.json" >/dev/null
test -s "$freeze_out/reflog.txt"
test -s "$freeze_out/conflicts/0-artifact.txt"
beads_a="$test_root/a.jsonl"
beads_b="$test_root/b.jsonl"
printf '%s\n' '{"id":"artifact.txt","updated_at":"2026-08-07T00:00:00Z","status":"old"}' >"$beads_a"
printf '%s\n' '{"id":"artifact.txt","updated_at":"2026-08-08T00:00:00Z","status":"new"}' >"$beads_b"
mkdir -p "$test_root/snapshot"
echo snapshot >"$test_root/snapshot/artifact.txt"
probe=$("$recover" --repo "$repo" --missing artifact.txt --beads-jsonl "$beads_a" --beads-jsonl "$beads_b" --snapshot-root "$test_root/snapshot")
printf '%s\n' "$probe" | jq -e '.authorities.filesystem == "absent" and .authorities.git_index == 1 and (.authorities.beads | length) == 2 and .authorization_required == true' >/dev/null
git -C "$repo" reflog -n 5 | grep -F initial >/dev/null
echo 'recovery skills fixture passed'
