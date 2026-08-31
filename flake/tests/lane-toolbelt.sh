#!/usr/bin/env bash
set -euo pipefail

lane=$1
root=$(mktemp -d)
origin=$root/origin.git
repo=$root/repo
bin=$root/bin
state=$root/state
mkdir -p "$bin" "$state" "$origin" "$repo"
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
git -C "$repo" branch -M feature/lane-toolbelt
git -C "$repo" push -q --set-upstream origin feature/lane-toolbelt

report=$root/report.md
printf '# fixture report\ncomplete\n' >"$report"

printf 'dirty\n' >"$repo/dirty.txt"
set +e
dirty_output=$(cd "$repo" && "$lane" done "$report" 2>&1)
dirty_status=$?
set -e
test "$dirty_status" -eq 1
grep -Fq 'dirty-uncommitted' <<<"$dirty_output"
grep -Fq 'dirty.txt' <<<"$dirty_output"

rm "$repo/dirty.txt"
printf 'committed WIP\n' >>"$repo/work.txt"
git -C "$repo" add work.txt
git -C "$repo" commit -qm 'fixture WIP'

captured=$root/captured.result
(cd "$repo" && "$lane" done "$report") >"$captured"
test "$(cat "$captured")" = "$(cat "$report")"
remote_head=$(git --git-dir="$origin" rev-parse refs/heads/feature/lane-toolbelt)
local_head=$(git -C "$repo" rev-parse HEAD)
test "$remote_head" = "$local_head"

printf 'partial uncommitted\n' >>"$repo/work.txt"
incomplete=$root/incomplete.result
(cd "$repo" && "$lane" done --incomplete "$report") >"$incomplete"
grep -Fq 'INCOMPLETE HANDOFF' "$incomplete"
grep -Fq '# fixture report' "$incomplete"
test -n "$(git -C "$repo" status --porcelain)"

mkdir -p "$repo/.agentctl" "$state/sinnixd/inputs"
cat >"$repo/.agentctl/project.toml" <<'EOF'
schema = 1

[project]
id = "fixture"
display_name = "Fixture"
root_markers = [".agentctl"]

[operations.verify_quick]
description = "Fixture quick verification"
exec = ["fixture-check"]
EOF
printf '#!%s\n' "$BASH" >"$bin/agentctl"
cat >>"$bin/agentctl" <<'EOF'
set -euo pipefail
case "$1 $2" in
  job\ start)
    printf '{"ok":true,"payload":{"value":{"job_id":"fixture-verification"}}}\n'
    ;;
  job\ wait)
    printf '{"ok":true,"payload":{"value":{"state":{"phase":"succeeded"}}}}\n'
    ;;
  *)
    exit 2
    ;;
esac
EOF
chmod +x "$bin/agentctl"
verify_output=$(cd "$repo" && PATH="$bin:$PATH" SINNIXD_JOB_ID=job-1 SINNIXD_PROJECT_ID=fixture SINNIXD_CHECKOUT_ID=default SINNIXD_TIMEOUT_SECONDS=60 "$lane" verify)
grep -Fq 'succeeded' <<<"$verify_output"

printf 'launch snapshot\n' >"$state/sinnixd/inputs/job-1.prompt"
task_output=$(cd "$repo" && HOME="$root/home" XDG_STATE_HOME="$state" SINNIXD_JOB_ID=job-1 SINNIXD_PROJECT_ID=fixture SINNIXD_CHECKOUT_ID=default "$lane" task)
test "$task_output" = 'launch snapshot'

printf 'lane toolbelt fixture passed\n'
