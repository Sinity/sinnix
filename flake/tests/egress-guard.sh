#!/usr/bin/env bash
set -euo pipefail

scanner=$1
root=$2
mkdir -p "$root"
printf '%s\n' 'clean technical text' > "$root/clean.txt"
printf '%s\n' 'token ghp_123456789012345678901234567890' > "$root/secret.txt"
head -c 1048577 /dev/zero > "$root/large.bin"
printf '\0ghp_123456789012345678901234567890' > "$root/binary.bin"

run() {
  SINNIX_HOOK_COMMAND="$1" SINNIX_HOOK_CWD="$root" XDG_STATE_HOME="$root/state" "$scanner"
}

run 'gh api repos/Sinity/sinnix -X POST --raw-field body=clean' | jq -e '.hookSpecificOutput.permissionDecision == "allow"' >/dev/null
run 'gh pr create --title change --body ghp_123456789012345678901234567890' | jq -e '.hookSpecificOutput.permissionDecision == "deny"' >/dev/null
run "gh api repos/Sinity/sinnix -X POST --input $root/clean.txt" | jq -e '.hookSpecificOutput.permissionDecision == "allow"' >/dev/null
run "gh api repos/Sinity/sinnix -X POST --input $root/secret.txt" | jq -e '.hookSpecificOutput.permissionDecision == "deny"' >/dev/null
run "gh api repos/Sinity/sinnix -X POST --input $root/binary.bin" | jq -e '.hookSpecificOutput.permissionDecision == "allow"' >/dev/null
run "gh api repos/Sinity/sinnix -X POST --input $root/large.bin" | jq -e '.hookSpecificOutput.permissionDecision == "deny"' >/dev/null
run 'printf ghp_123456789012345678901234567890' | jq -e '.hookSpecificOutput.permissionDecision == "allow"' >/dev/null
SINNIX_EGRESS_GUARD_OVERRIDE=1 run "gh api repos/Sinity/sinnix -X POST --input $root/secret.txt" | jq -e '.hookSpecificOutput.permissionDecision == "allow"' >/dev/null
test -s "$root/state/sinnix/egress-guard.jsonl"
printf 'egress guard fixtures passed\n'
