#!/usr/bin/env bash
set -euo pipefail

lane=$1
schema=$2
root=$(mktemp -d)
origin=$root/origin.git
repo=$root/repo
bin=$root/bin
mkdir -p "$bin" "$origin" "$repo"
export HOME=$root/home
mkdir -p "$HOME"
export GIT_CONFIG_COUNT=1
export GIT_CONFIG_KEY_0=safe.directory
export GIT_CONFIG_VALUE_0='*'

git init --bare "$origin" >/dev/null
git -C "$repo" init -q
git -C "$repo" config user.name fixture
git -C "$repo" config user.email fixture@example.invalid
git -C "$repo" remote add origin "$origin"
printf 'initial\n' >"$repo/work.txt"
git -C "$repo" add work.txt
git -C "$repo" commit -qm initial
git -C "$repo" branch -M batch/fixture/w1
git -C "$repo" push -q --set-upstream origin batch/fixture/w1

mkdir -p "$repo/.lane"
cp "$schema" "$repo/.lane/worker.schema.json"

write_result() {
  local sha=$1
  cat >"$root/result.json" <<EOF
{
  "candidate_sha": "$sha",
  "beads": [
    {
      "id": "fixture-1",
      "criteria": [
        { "text": "the fixture passes", "status": "satisfied", "evidence": "work.txt:2" }
      ]
    }
  ],
  "unresolved": [],
  "verification": [{ "command": "true", "receipt": "exit 0" }]
}
EOF
}

printf 'committed WIP\n' >>"$repo/work.txt"
git -C "$repo" add work.txt
git -C "$repo" commit -qm 'fixture WIP'
head=$(git -C "$repo" rev-parse HEAD)
write_result "$head"

# A dirty tree is refused; `.lane/` is not counted.
printf 'dirty\n' >"$repo/dirty.txt"
set +e
dirty_output=$(cd "$repo" && "$lane" done "$root/result.json" 2>&1)
dirty_status=$?
set -e
test "$dirty_status" -eq 1
grep -Fq 'uncommitted' <<<"$dirty_output"
grep -Fq 'dirty.txt' <<<"$dirty_output"
rm "$repo/dirty.txt"

# A result that does not validate is refused.
printf '{"candidate_sha": "%s", "beads": []}\n' "$head" >"$root/invalid.json"
set +e
invalid_output=$(cd "$repo" && "$lane" done "$root/invalid.json" 2>&1)
invalid_status=$?
set -e
test "$invalid_status" -eq 1
grep -Fq 'does not validate' <<<"$invalid_output"
grep -Fq 'unresolved' <<<"$invalid_output"

# A result naming another commit is refused.
write_result "$(printf '0%.0s' $(seq 1 40))"
set +e
mismatch_output=$(cd "$repo" && "$lane" done "$root/result.json" 2>&1)
mismatch_status=$?
set -e
test "$mismatch_status" -eq 1
grep -Fq 'is not HEAD' <<<"$mismatch_output"

# A valid result at HEAD is printed verbatim and nothing is pushed.
write_result "$head"
captured=$root/captured.result
(cd "$repo" && "$lane" done "$root/result.json") >"$captured"
test "$(cat "$captured")" = "$(cat "$root/result.json")"
remote_head=$(git --git-dir="$origin" rev-parse refs/heads/batch/fixture/w1)
test "$remote_head" != "$head"

mkdir -p "$repo/.agentctl"
cat >"$repo/.agentctl/project.toml" <<'EOF'
schema = 1

[project]
id = "fixture"
display_name = "Fixture"
root_markers = [".agentctl"]

[workspace]
root = "/tmp"
verify = { focused = "verify_quick" }

[operations.verify_quick]
description = "Fixture quick verification"
exec = ["fixture-check"]
EOF
printf '#!%s\n' "$BASH" >"$bin/agentctl"
cat >>"$bin/agentctl" <<'EOF'
set -euo pipefail
printf '%s\n' "$*" >> "${AGENTCTL_CALLS:?}"
case "$1 $2" in
  job\ start)
    printf '{"job_id": 7, "phase": "succeeded", "terminal": true}\n'
    ;;
  *)
    exit 2
    ;;
esac
EOF
chmod +x "$bin/agentctl"
export AGENTCTL_CALLS=$root/agentctl.calls
verify_output=$(cd "$repo" && PATH="$bin:$PATH" AGENTCTL_TIMEOUT_SECONDS=60 "$lane" verify)
grep -Fq 'succeeded' <<<"$verify_output"
grep -Fq "job start fixture verify_quick --workspace $repo --wait --timeout-seconds 60" "$AGENTCTL_CALLS"

printf 'launch snapshot\n' >"$repo/.lane/prompt.md"
task_output=$(cd "$repo" && "$lane" task)
test "$task_output" = 'launch snapshot'
printf 'named prompt\n' >"$root/named.md"
task_output=$(cd "$repo" && AGENTCTL_JOB_PROMPT_FILE="$root/named.md" "$lane" task)
test "$task_output" = 'named prompt'

printf 'lane toolbelt fixture passed\n'
