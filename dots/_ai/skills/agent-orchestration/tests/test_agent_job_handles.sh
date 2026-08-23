#!/usr/bin/env bash
set -euo pipefail
export SINNIX_AGENT_JOURNAL=0

skill_dir="${SINNIX_AGENT_TEST_SKILL_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)}"
repo_root="${SINNIX_AGENT_TEST_REPO_ROOT:-$(git -C "${skill_dir}" rev-parse --show-toplevel)}"
runner="${skill_dir}/scripts/run_agent_prompt.sh"
control="${skill_dir}/scripts/agent_job_control.sh"
scope_exec="${repo_root}/scripts/sinnix-agent-scope-exec"
# The launcher is generated from the command-class table rather than living
# under scripts/ (flake/launch.nix), so the fixture is handed its path.
scope="${SINNIX_AGENT_TEST_SCOPE_BIN:-$(command -v sinnix-scope 2>/dev/null || true)}"
if [[ -z ${scope} || ! -x ${scope} ]]; then
  echo "sinnix-scope not found; set SINNIX_AGENT_TEST_SCOPE_BIN" >&2
  exit 1
fi

tmp="$(mktemp -d)"
cleanup() {
  [[ -z ${hold_pid:-} ]] || kill "${hold_pid}" 2>/dev/null || true
  wait "${hold_pid:-}" 2>/dev/null || true
  rm -rf "${tmp}"
}
trap cleanup EXIT

make_executable() {
  local target
  for target in "$@"; do
    sed -i "1c#!$(command -v bash)" "$target"
    chmod +x "$target"
  done
}

mkdir -p "${tmp}/bin" "${tmp}/bridge-bin" "${tmp}/scope-bin" "${tmp}/repo" \
  "${tmp}/state" "${tmp}/output" "${tmp}/proc" "${tmp}/scope-receipts" \
  "${tmp}/runtime"
git -C "${tmp}/repo" init -q
git -C "${tmp}/repo" -c user.name=Test -c user.email=test@example.invalid commit -q --allow-empty -m seed
git -C "${tmp}/repo" worktree add -q -b agent-test "${tmp}/worktree"
repo_common_dir="$(git -C "${tmp}/repo" rev-parse --path-format=absolute --git-common-dir)"
printf 'fake prompt\n' >"${tmp}/prompt.prompt"
printf 'hold\n' >"${tmp}/hold.prompt"

cat >"${tmp}/bin/scope-exec" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
unit=""
properties=()
while [[ $1 != -- ]]; do
  case "$1" in
    --unit) unit="$2"; shift 2 ;;
    --property) properties+=("$2"); shift 2 ;;
    *) exit 64 ;;
  esac
done
shift
printf '%s\n' "${properties[@]}" >"${FAKE_SCOPE_RECEIPT_DIR:?}/${unit}"
exec env SINNIX_AGENT_SCOPED=1 SINNIX_AGENT_SCOPE_UNIT="$unit" \
  SINNIX_AGENT_SCOPE_CGROUP="/fake/${unit}" "$@"
EOF
cat >"${tmp}/bin/codex" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
last=""
cflag=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --output-last-message) last="$2"; shift 2 ;;
    -C) cflag="$2"; shift 2 ;;
    *) shift ;;
  esac
done
# Record the -C value this invocation received, independent of the scrubbed
# `env -i` environment the runner execs us under (bare $0 dirname still
# works): the symlink-canonicalization test reads the most recent line.
printf '%s\n' "${cflag}" >>"$(cd "$(dirname "$0")/.." && pwd)/codex-invocations.log"
payload="$(cat)"
printf 'fake final\n' >"${last}"
if [[ $payload == *hold* ]]; then sleep 30; fi
if [[ $payload == *fail* ]]; then exit 23; fi
exit 0
EOF
cat >"${tmp}/bin/grok-sinnix" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
prompt=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --single) prompt="$2"; shift 2 ;;
    *) shift ;;
  esac
done
if [[ $prompt == *fail* ]]; then
  printf 'grok refused\n' >&2
  exit 31
fi
printf 'fake grok final\n'
EOF
cat >"${tmp}/bin/agy-sinnix" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
while [[ $# -gt 0 ]]; do
  case "$1" in
    --print) [[ $2 == "fake prompt" ]]; shift 2 ;;
    *) shift ;;
  esac
done
printf 'fake antigravity final\n'
EOF
cat >"${tmp}/bin/systemctl" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
if [[ $2 == show ]]; then
  if [[ ${FAKE_MISSING_UNIT:-} == "${3:-}" ]]; then
    exit 1
  fi
  cat <<OUT
ActiveState=${FAKE_ACTIVE_STATE:-active}
SubState=${FAKE_SUB_STATE:-running}
MainPID=${FAKE_SYSTEMD_PID:-0}
ControlGroup=${FAKE_SYSTEMD_CGROUP:?missing FAKE_SYSTEMD_CGROUP}
MemoryHigh=2G
MemoryMax=3G
MemoryCurrent=1G
MemoryPeak=1536M
CPUWeight=200
IOWeight=300
RuntimeMaxUSec=600000000
CPUUsageNSec=42000000
Result=${FAKE_RESULT:-success}
OUT
elif [[ $2 == stop ]]; then
  : "${FAKE_STOP_MARKER:?missing FAKE_STOP_MARKER}"
  touch "${FAKE_STOP_MARKER}"
else
  exit 64
fi
EOF
make_executable "${tmp}/bin/"*

run_job() {
  local id="$1"
  local prompt="$2"
  env -u SINNIX_AGENT_SCOPED -u SINNIX_AGENT_SCOPE_UNIT -u SINNIX_AGENT_SCOPE_CGROUP \
    PATH="${tmp}/bin:${PATH}" SINNIX_AGENT_SCOPE_EXEC="${tmp}/bin/scope-exec" \
    FAKE_SCOPE_RECEIPT_DIR="${tmp}/scope-receipts" \
    "${runner}" --job-id "${id}" --job-state-dir "${tmp}/state" --job-role source-review \
    --work-item sinnix-056.1 --parent-job-id parent-1 --coordinator-job-id coord-1 \
    --provider codex --account-hash sha256:test --vendor-session-id vendor-1 \
    --polylogue-session-id polylogue-1 --kitty-socket unix:/tmp/kitty \
    --kitty-window-id 42 --hyprland-address address-1 --quota-snapshot-id quota-1 \
    --checkout-ref sinnix://projects/fixture/checkouts/default \
    --agent codex --model fake --reasoning-effort high \
    --workdir "${tmp}/worktree" --registered-project "${tmp}/repo" \
    --expected-git-common-dir "${repo_common_dir}" --prompt-file "${prompt}" \
    --log-file "${tmp}/output/${id}.log" --last-file "${tmp}/output/${id}.final" \
    --memory-high 2G --memory-max 3G --cpu-weight 200 --io-weight 300
}

run_backend_job() {
  local backend="$1"
  local id="$2"
  local prompt="${3:-${tmp}/prompt.prompt}"
  env -u SINNIX_AGENT_SCOPED -u SINNIX_AGENT_SCOPE_UNIT -u SINNIX_AGENT_SCOPE_CGROUP \
    PATH="${tmp}/bin:${PATH}" SINNIX_AGENT_SCOPE_EXEC="${tmp}/bin/scope-exec" \
    FAKE_SCOPE_RECEIPT_DIR="${tmp}/scope-receipts" \
    "${runner}" --job-id "${id}" --job-state-dir "${tmp}/state" --agent "${backend}" \
    --model fake --reasoning-effort high --workdir "${tmp}/worktree" \
    --registered-project "${tmp}/repo" --expected-git-common-dir "${repo_common_dir}" \
    --prompt-file "${prompt}" --log-file "${tmp}/output/${id}.log" \
    --last-file "${tmp}/output/${id}.final"
}

run_job job-one "${tmp}/prompt.prompt"
run_job job-two "${tmp}/prompt.prompt"
run_backend_job grok job-grok
run_backend_job antigravity job-antigravity

[[ -f ${tmp}/state/job-one.json && -f ${tmp}/state/job-two.json ]]
[[ -f ${tmp}/output/job-one.log && -f ${tmp}/output/job-one.final ]]
jq -e '(.schema_version == 2 or .schema_version == 3) and .backend == "grok" and .lifecycle == "succeeded"' "${tmp}/state/job-grok.json" >/dev/null
jq -e '(.schema_version == 2 or .schema_version == 3) and .backend == "antigravity" and .lifecycle == "succeeded"' "${tmp}/state/job-antigravity.json" >/dev/null
grep -Fxq 'fake grok final' "${tmp}/output/job-grok.final"
grep -Fxq 'fake antigravity final' "${tmp}/output/job-antigravity.final"

# --registered-project and --expected-git-common-dir are the runner's own
# authorization boundary (the typed sinnixd runner supplies both for every
# gateway launch): a direct caller that omits
# either, supplies a stale common-dir, or points at an unrelated checkout
# must be refused before anything runs, not silently trusted.
run_job_variant() {
  # Runs the runner with the given extra args appended after the base
  # required set, without --registered-project/--expected-git-common-dir
  # pre-filled, so each case controls its own identity arguments.
  local id="$1"
  shift
  env -u SINNIX_AGENT_SCOPED -u SINNIX_AGENT_SCOPE_UNIT -u SINNIX_AGENT_SCOPE_CGROUP \
    PATH="${tmp}/bin:${PATH}" SINNIX_AGENT_SCOPE_EXEC="${tmp}/bin/scope-exec" \
    FAKE_SCOPE_RECEIPT_DIR="${tmp}/scope-receipts" \
    "${runner}" --job-id "${id}" --job-state-dir "${tmp}/state" --agent codex --model fake \
    --prompt-file "${tmp}/prompt.prompt" --log-file "${tmp}/output/${id}.log" \
    --last-file "${tmp}/output/${id}.final" "$@"
}

set +e
run_job_variant job-missing-identity --workdir "${tmp}/worktree"
missing_identity_status=$?
set -e
[[ ${missing_identity_status} -eq 2 ]] || {
  echo "runner accepted a launch missing --registered-project/--expected-git-common-dir (status ${missing_identity_status})" >&2
  exit 1
}
[[ ! -f ${tmp}/state/job-missing-identity.json ]]

set +e
run_job_variant job-missing-common-dir --workdir "${tmp}/worktree" --registered-project "${tmp}/repo"
missing_common_dir_status=$?
set -e
[[ ${missing_common_dir_status} -eq 2 ]] || {
  echo "runner accepted --registered-project with no --expected-git-common-dir (status ${missing_common_dir_status})" >&2
  exit 1
}

set +e
run_job_variant job-mismatched-common-dir --workdir "${tmp}/worktree" \
  --registered-project "${tmp}/repo" --expected-git-common-dir "${tmp}/repo/.not-git"
mismatched_status=$?
set -e
[[ ${mismatched_status} -eq 125 ]] || {
  echo "runner accepted a mismatched --expected-git-common-dir (status ${mismatched_status})" >&2
  exit 1
}
[[ ! -f ${tmp}/state/job-mismatched-common-dir.json ]]

git -C "${tmp}" init -q other-repo
git -C "${tmp}/other-repo" -c user.name=Test -c user.email=test@example.invalid commit -q --allow-empty -m seed
other_common_dir="$(git -C "${tmp}/other-repo" rev-parse --path-format=absolute --git-common-dir)"
set +e
run_job_variant job-unlinked-worktree --workdir "${tmp}/other-repo" \
  --registered-project "${tmp}/repo" --expected-git-common-dir "${other_common_dir}"
unlinked_status=$?
set -e
[[ ${unlinked_status} -eq 125 ]] || {
  echo "runner accepted a Git checkout unrelated to --registered-project (status ${unlinked_status})" >&2
  exit 1
}
[[ ! -f ${tmp}/state/job-unlinked-worktree.json ]]

# Execution must bind to the canonical, validated worktree -- not the
# original (possibly symlinked) --workdir input, which is only used to
# derive it. A symlink to an authorized worktree must still be accepted
# (the identity check resolves it), but the agent process itself must run
# against the real path.
ln -s "${tmp}/worktree" "${tmp}/worktree-link"
canonical_worktree="$(cd "${tmp}/worktree" && pwd -P)"
run_job_variant job-symlink-workdir --workdir "${tmp}/worktree-link" \
  --registered-project "${tmp}/repo" --expected-git-common-dir "${repo_common_dir}"
received_cwd="$(tail -n1 "${tmp}/codex-invocations.log")"
[[ ${received_cwd} == "${canonical_worktree}" ]] || {
  echo "codex ran against the symlinked --workdir instead of the canonical validated worktree: ${received_cwd} != ${canonical_worktree}" >&2
  exit 1
}
jq -e --arg worktree "${canonical_worktree}" '.worktree == $worktree' "${tmp}/state/job-symlink-workdir.json" >/dev/null

# --local-workdir is the explicit, clearly-named non-attested opt-out for a
# directory the caller already trusts directly -- it must not be combined
# with the attested identity pair (ambiguous, refused) and must not silently
# reappear as a way to omit worktree identity altogether (the required-args
# check above already covers that: neither form present is still refused).
set +e
run_job_variant job-ambiguous-identity --workdir "${tmp}/worktree" --local-workdir \
  --registered-project "${tmp}/repo" --expected-git-common-dir "${repo_common_dir}"
ambiguous_status=$?
set -e
[[ ${ambiguous_status} -eq 2 ]] || {
  echo "runner accepted --local-workdir combined with the attested identity pair (status ${ambiguous_status})" >&2
  exit 1
}
[[ ! -f ${tmp}/state/job-ambiguous-identity.json ]]

# A non-Git directory (the documented --skip-git-repo-check use case) and a
# subdirectory of a Git checkout (which the attested path can never
# authorize -- it can only attest a whole worktree root) both have no
# worktree identity to attest; --local-workdir must accept and actually run
# them, binding execution to the canonical resolved path exactly like the
# attested path does.
mkdir -p "${tmp}/plain-dir"
run_job_variant job-local-plain-dir --workdir "${tmp}/plain-dir" --local-workdir
jq -e '.lifecycle == "succeeded" and .exit_status == 0' "${tmp}/state/job-local-plain-dir.json" >/dev/null || {
  jq '{lifecycle, exit_status}' "${tmp}/state/job-local-plain-dir.json" >&2
  exit 1
}
canonical_plain_dir="$(cd "${tmp}/plain-dir" && pwd -P)"
[[ $(jq -r .worktree "${tmp}/state/job-local-plain-dir.json") == "${canonical_plain_dir}" ]]

mkdir -p "${tmp}/worktree/subdir"
run_job_variant job-local-subdir --workdir "${tmp}/worktree/subdir" --local-workdir
jq -e '.lifecycle == "succeeded" and .exit_status == 0' "${tmp}/state/job-local-subdir.json" >/dev/null || {
  jq '{lifecycle, exit_status}' "${tmp}/state/job-local-subdir.json" >&2
  exit 1
}

# Symlink canonicalization applies identically under --local-workdir.
ln -s "${tmp}/plain-dir" "${tmp}/plain-dir-link"
canonical_plain_link="$(cd "${tmp}/plain-dir" && pwd -P)"
run_job_variant job-local-symlink --workdir "${tmp}/plain-dir-link" --local-workdir
received_local_cwd="$(tail -n1 "${tmp}/codex-invocations.log")"
[[ ${received_local_cwd} == "${canonical_plain_link}" ]] || {
  echo "codex ran against the symlinked --local-workdir input instead of the canonical resolved path: ${received_local_cwd} != ${canonical_plain_link}" >&2
  exit 1
}

# argv backends (claude/grok/antigravity) get the prompt on the command line,
# never on the runner's own stdin -- so an interactive launch without an
# explicit </dev/null must not block waiting for EOF on whatever the runner
# inherited. Simulate a terminal: a FIFO held open read-write, so open()
# returns immediately but a blocking read() never sees EOF.
mkfifo "${tmp}/fake-tty"
exec 9<>"${tmp}/fake-tty"
set +e
timeout 5 env -u SINNIX_AGENT_SCOPED -u SINNIX_AGENT_SCOPE_UNIT -u SINNIX_AGENT_SCOPE_CGROUP \
  PATH="${tmp}/bin:${PATH}" SINNIX_AGENT_SCOPE_EXEC="${tmp}/bin/scope-exec" \
  FAKE_SCOPE_RECEIPT_DIR="${tmp}/scope-receipts" \
  "${runner}" --job-id job-grok-notty --job-state-dir "${tmp}/state" --agent grok \
  --model fake --reasoning-effort high --workdir "${tmp}/worktree" \
  --registered-project "${tmp}/repo" --expected-git-common-dir "${repo_common_dir}" \
  --prompt-file "${tmp}/prompt.prompt" --log-file "${tmp}/output/job-grok-notty.log" \
  --last-file "${tmp}/output/job-grok-notty.final" <&9
notty_status=$?
set -e
exec 9<&-
if [[ ${notty_status} -eq 124 ]]; then
  echo "grok job blocked draining the runner's own (fake-tty) stdin" >&2
  exit 1
fi
[[ ${notty_status} -eq 0 ]] || {
  echo "grok fake-tty job failed for an unrelated reason (status ${notty_status})" >&2
  exit 1
}

# A retry-ladder attempt whose child exits before /proc/<pid>/stat is
# readable must not leave the manifest's actual_agent.pid (attempt N, the
# newest) paired with actual_agent.proc_start (attempt N-1, a different
# process's start time) -- that pairing is what sinnix-observe orphans keys
# pid-reuse detection on.
printf '{"schema_version":3,"job_id":"job-pairing"}' >"${tmp}/state/job-pairing.json"
SINNIX_AGENT_TEST_JOB_HELPER="${skill_dir}/scripts/run_agent_prompt_job.py" \
  SINNIX_AGENT_TEST_STATE_DIR="${tmp}/state" python3 - <<'PYEOF'
import importlib.util
import os
import sys

spec = importlib.util.spec_from_file_location(
    "run_agent_prompt_job", os.environ["SINNIX_AGENT_TEST_JOB_HELPER"]
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

starts = iter(["100", None])  # attempt 1: readable; attempt 2: child already gone


def fake_proc_start(_pid):
    return next(starts)


module.proc_start = fake_proc_start


class Args:
    job_id = "job-pairing"
    job_state_dir = os.environ["SINNIX_AGENT_TEST_STATE_DIR"]


job = module.Job(Args())
job.record_actual_agent(111)
assert job.actual_agent_pid == "111" and job.actual_agent_proc_start == "100", (
    job.actual_agent_pid,
    job.actual_agent_proc_start,
)

job.record_actual_agent(222)  # attempt 2: proc_start unreadable, must not overwrite
assert job.actual_agent_pid == "111" and job.actual_agent_proc_start == "100", (
    "attempt 2's untraceable pid leaked into the pairing",
    job.actual_agent_pid,
    job.actual_agent_proc_start,
)
print("actual_agent pid/proc_start pairing held across an unreadable retry")
PYEOF
jq -e --arg repo "${tmp}/repo" --arg worktree "${tmp}/worktree" '
  (.schema_version == 2 or .schema_version == 3) and .job_id == "job-one" and .lifecycle == "succeeded" and .exit_status == 0 and
  .repo == $repo and .worktree == $worktree and .checkout_ref == "sinnix://projects/fixture/checkouts/default" and
  .backend == "codex" and .model == "fake" and (.prompt.sha256 | length == 64) and .artifacts.final != "" and
  .launcher.scope_unit == "sinnix-agent-job-job-one.scope" and
  .launcher.cgroup == "/fake/sinnix-agent-job-job-one.scope" and
  .delegation.parent_job_id == "parent-1" and .delegation.coordinator_job_id == "coord-1" and
  .identity.provider == "codex" and .identity.account_hash == "sha256:test" and
  .correlation.vendor_session_id == "vendor-1" and .correlation.polylogue_session_id == "polylogue-1" and
  .correlation.kitty_window_id == "42" and .correlation.hyprland_address == "address-1" and
  .correlation.quota_snapshot_id == "quota-1" and
  (.actual_agent.pid | type == "number") and (.actual_agent.proc_start | length > 0) and
  (.completion.duration_seconds | type == "number") and .completion.verification.outcome == "passed"
' "${tmp}/state/job-one.json" >/dev/null || {
  jq '{schema_version, delegation, identity, correlation, actual_agent, completion}' "${tmp}/state/job-one.json" >&2
  exit 1
}
mapfile -t forwarded_properties <"${tmp}/scope-receipts/sinnix-agent-job-job-one.scope"
[[ ${forwarded_properties[*]} == "MemoryHigh=2G MemoryMax=3G CPUWeight=200 IOWeight=300 RuntimeMaxSec=14400" ]]

jq -e '(.jobs | map(.job_id)) as $ids | ($ids | index("job-one")) != null and ($ids | index("job-two")) != null' <(
  FAKE_SYSTEMD_CGROUP=/fake/unused SINNIX_AGENT_SYSTEMCTL="${tmp}/bin/systemctl" \
    "${control}" --state-dir "${tmp}/state" list
) >/dev/null
FAKE_MISSING_UNIT=sinnix-agent-job-job-two.scope FAKE_SYSTEMD_CGROUP=/fake/unused \
  SINNIX_AGENT_SYSTEMCTL="${tmp}/bin/systemctl" "${control}" --state-dir "${tmp}/state" list |
  jq -e '(.jobs | map(select(.job_id == "job-two"))[0].live.available) == false' >/dev/null

FAKE_SYSTEMD_CGROUP=/fake/sinnix-agent-job-job-one.scope \
  SINNIX_AGENT_SYSTEMCTL="${tmp}/bin/systemctl" "${control}" --state-dir "${tmp}/state" status --job job-one |
  jq -e '.live.MemoryHigh == "2G" and .live.MemoryMax == "3G" and .live.CPUWeight == "200" and .live.IOWeight == "300"' >/dev/null

printf 'fail\n' >"${tmp}/fail.prompt"
if run_job job-fail "${tmp}/fail.prompt"; then
  echo "failing backend unexpectedly succeeded" >&2
  exit 1
fi
jq -e '.lifecycle == "failed" and .exit_status == 23' \
  "${tmp}/state/job-fail.json" >/dev/null

# A backend whose runner copies its own output into the final artifact must
# still report the agent's status: the manifest is the attestation, so a
# refused run may not be recorded as a completed one.
if run_backend_job grok job-grok-fail "${tmp}/fail.prompt"; then
  echo "failing grok backend unexpectedly succeeded" >&2
  exit 1
fi
jq -e '.lifecycle == "failed" and .exit_status == 31 and .completion.verification.outcome == "failed"' \
  "${tmp}/state/job-grok-fail.json" >/dev/null || {
  jq '{lifecycle, exit_status, completion}' "${tmp}/state/job-grok-fail.json" >&2
  exit 1
}
if run_job job-one "${tmp}/prompt.prompt"; then
  echo "duplicate job handle unexpectedly overwrote its manifest" >&2
  exit 1
fi

set +e
env -u SINNIX_AGENT_SCOPED -u SINNIX_AGENT_SCOPE_UNIT -u SINNIX_AGENT_SCOPE_CGROUP \
  PATH="${tmp}/bin:${PATH}" SINNIX_AGENT_SCOPE_EXEC="${tmp}/bin/scope-exec" \
  FAKE_SCOPE_RECEIPT_DIR="${tmp}/scope-receipts" \
  "${runner}" --job-id job-collision --launch-id collision-a --job-state-dir "${tmp}/state" \
  --agent codex --model fake --workdir "${tmp}/worktree" \
  --registered-project "${tmp}/repo" --expected-git-common-dir "${repo_common_dir}" \
  --prompt-file "${tmp}/prompt.prompt" \
  --log-file "${tmp}/output/job-collision.log" --last-file "${tmp}/output/job-collision.final" &
collision_a=$!
env -u SINNIX_AGENT_SCOPED -u SINNIX_AGENT_SCOPE_UNIT -u SINNIX_AGENT_SCOPE_CGROUP \
  PATH="${tmp}/bin:${PATH}" SINNIX_AGENT_SCOPE_EXEC="${tmp}/bin/scope-exec" \
  FAKE_SCOPE_RECEIPT_DIR="${tmp}/scope-receipts" \
  "${runner}" --job-id job-collision --launch-id collision-b --job-state-dir "${tmp}/state" \
  --agent codex --model fake --workdir "${tmp}/worktree" \
  --registered-project "${tmp}/repo" --expected-git-common-dir "${repo_common_dir}" \
  --prompt-file "${tmp}/prompt.prompt" \
  --log-file "${tmp}/output/job-collision.log" --last-file "${tmp}/output/job-collision.final" &
collision_b=$!
wait "${collision_a}"
collision_a_status=$?
wait "${collision_b}"
collision_b_status=$?
set -e
if ! { [[ ${collision_a_status} -eq 0 && ${collision_b_status} -ne 0 ]] ||
  [[ ${collision_a_status} -ne 0 && ${collision_b_status} -eq 0 ]]; }; then
  echo "concurrent same-ID launches did not produce exactly one owner" >&2
  exit 1
fi
reserved_launch="$(<"${tmp}/state/.reservations/job-collision/launch-id")"
[[ $(jq -r .launch_id "${tmp}/state/job-collision.json") == "${reserved_launch}" ]]

env -u SINNIX_AGENT_SCOPED -u SINNIX_AGENT_SCOPE_UNIT -u SINNIX_AGENT_SCOPE_CGROUP \
  PATH="${tmp}/bin:${PATH}" SINNIX_AGENT_SCOPE_EXEC="${tmp}/bin/scope-exec" \
  FAKE_SCOPE_RECEIPT_DIR="${tmp}/scope-receipts" \
  "${runner}" --job-id job-hold --job-state-dir "${tmp}/state" --agent codex --model fake \
  --workdir "${tmp}/worktree" --registered-project "${tmp}/repo" \
  --expected-git-common-dir "${repo_common_dir}" --prompt-file "${tmp}/hold.prompt" \
  --log-file "${tmp}/output/job-hold.log" --last-file "${tmp}/output/job-hold.final" &
hold_pid=$!
for _ in {1..100}; do
  [[ -f ${tmp}/state/job-hold.json ]] && [[ $(jq -r .lifecycle "${tmp}/state/job-hold.json") == running ]] && [[ $(jq -r '.actual_agent.pid // empty' "${tmp}/state/job-hold.json") =~ ^[0-9]+$ ]] && break
  sleep 0.05
done
[[ $(jq -r .lifecycle "${tmp}/state/job-hold.json") == running ]]
manifest_pid="$(jq -r .launcher.pid "${tmp}/state/job-hold.json")"
actual_pid="$(jq -r .actual_agent.pid "${tmp}/state/job-hold.json")"
live_stat="$(<"/proc/${manifest_pid}/stat")"
live_start="$(printf '%s\n' "${live_stat##*) }" | awk '{print $20}')"
[[ $live_start == "$(jq -r .launcher.proc_start "${tmp}/state/job-hold.json")" ]]
mkdir -p "${tmp}/proc/${manifest_pid}"
printf 'x x x x x x x x x x x x x x x x x x x %s\n' "$(jq -r .launcher.proc_start "${tmp}/state/job-hold.json")" >"${tmp}/proc/${manifest_pid}/stat"
printf '0::/wrong/cgroup\n' >"${tmp}/proc/${manifest_pid}/cgroup"
ln -s "${tmp}/worktree" "${tmp}/proc/${manifest_pid}/cwd"
actual_stat="$(<"/proc/${actual_pid}/stat")"
actual_start="$(printf '%s\n' "${actual_stat##*) }" | awk '{print $20}')"
mkdir -p "${tmp}/proc/${actual_pid}"
printf 'x x x x x x x x x x x x x x x x x x x %s\n' "${actual_start}" >"${tmp}/proc/${actual_pid}/stat"
printf '0::/wrong/cgroup\n' >"${tmp}/proc/${actual_pid}/cgroup"

if FAKE_SYSTEMD_CGROUP=/fake/sinnix-agent-job-job-hold.scope FAKE_STOP_MARKER="${tmp}/stopped" \
  SINNIX_AGENT_SYSTEMCTL="${tmp}/bin/systemctl" SINNIX_AGENT_PROC_ROOT="${tmp}/proc" \
  "${control}" --state-dir "${tmp}/state" interrupt --job job-hold; then
  echo "mismatched cgroup interrupt unexpectedly succeeded" >&2
  exit 1
fi
[[ ! -e ${tmp}/stopped ]]
if "${control}" --state-dir "${tmp}/state" interrupt --pid "${manifest_pid}"; then
  echo "PID-only interrupt unexpectedly succeeded" >&2
  exit 1
fi
if "${control}" --state-dir "${tmp}/state" interrupt --title agent-job-hold; then
  echo "title-only interrupt unexpectedly succeeded" >&2
  exit 1
fi

printf '0::/fake/sinnix-agent-job-job-hold.scope\n' >"${tmp}/proc/${manifest_pid}/cgroup"
printf '0::/fake/sinnix-agent-job-job-hold.scope\n' >"${tmp}/proc/${actual_pid}/cgroup"
FAKE_SYSTEMD_PID="${manifest_pid}" \
  FAKE_SYSTEMD_CGROUP=/fake/sinnix-agent-job-job-hold.scope \
  FAKE_STOP_MARKER="${tmp}/stopped" SINNIX_AGENT_SYSTEMCTL="${tmp}/bin/systemctl" \
  SINNIX_AGENT_PROC_ROOT="${tmp}/proc" \
  "${control}" --state-dir "${tmp}/state" interrupt --job job-hold
[[ -e ${tmp}/stopped ]]
[[ $(jq -sr '[.[] | select(.lifecycle == "cancelled")][-1].exit_status' "${tmp}/state/job-hold.events.jsonl") == 143 ]]

# A systemd deadline can terminate the scope before the runner writes its final
# state. Status is the reconciliation boundary for the shared manifest.
jq '.lifecycle="running" | .launcher.scope_unit="sinnix-agent-job-job-timeout.scope"' \
  "${tmp}/state/job-one.json" >"${tmp}/state/job-timeout.json"
jq '.job_id="job-timeout"' "${tmp}/state/job-timeout.json" >"${tmp}/state/job-timeout.tmp"
mv "${tmp}/state/job-timeout.tmp" "${tmp}/state/job-timeout.json"
FAKE_ACTIVE_STATE=inactive FAKE_SUB_STATE=dead FAKE_RESULT=timeout \
  FAKE_SYSTEMD_CGROUP=/fake/sinnix-agent-job-job-timeout.scope \
  SINNIX_AGENT_SYSTEMCTL="${tmp}/bin/systemctl" \
  "${control}" --state-dir "${tmp}/state" status --job job-timeout |
  jq -e '.lifecycle == "timed_out" and .exit_status == 124 and .live.Result == "timeout"' >/dev/null
[[ $(jq -r .lifecycle "${tmp}/state/job-timeout.json") == timed_out ]]
[[ $(jq -sr '[.[] | select(.lifecycle == "timed_out")][-1].exit_status' "${tmp}/state/job-timeout.events.jsonl") == 124 ]]

# Status remains readable during the accepted/starting phase, before the
# cancellation identity has a cgroup attestation.
jq '.job_id="job-starting" | .lifecycle="starting" | .launcher.cgroup=""' \
  "${tmp}/state/job-one.json" >"${tmp}/state/job-starting.json"
FAKE_SYSTEMD_CGROUP=/fake/pending \
  SINNIX_AGENT_SYSTEMCTL="${tmp}/bin/systemctl" \
  "${control}" --state-dir "${tmp}/state" status --job job-starting |
  jq -e '.lifecycle == "starting" and .live.available == true' >/dev/null
if FAKE_SYSTEMD_CGROUP=/fake/pending FAKE_STOP_MARKER="${tmp}/starting-stopped" \
  SINNIX_AGENT_SYSTEMCTL="${tmp}/bin/systemctl" \
  "${control}" --state-dir "${tmp}/state" interrupt --job job-starting; then
  echo "unattested starting job was interruptible" >&2
  exit 1
fi
[[ ! -e ${tmp}/starting-stopped ]]

# Exercise the production bridge: options must reach sinnix-scope, and the
# attestation environment must reach the child command.
cat >"${tmp}/bridge-bin/sinnix-scope" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' "$@" >"${BRIDGE_RECEIPT:?}"
while [[ $# -gt 0 && $1 != -- ]]; do shift; done
[[ ${1:-} == -- ]]
shift
exec "$@"
EOF
make_executable "${tmp}/bridge-bin/sinnix-scope"
# The child shell, not this test process, expands the attestation variables.
# shellcheck disable=SC2016
env -u SINNIX_AGENT_SCOPED -u SINNIX_AGENT_SCOPE_UNIT -u SINNIX_AGENT_SCOPE_CGROUP \
  BRIDGE_RECEIPT="${tmp}/bridge.receipt" PATH="${tmp}/bridge-bin:${PATH}" \
  "${scope_exec}" --unit sinnix-agent-job-bridge.scope \
  --property MemoryHigh=2G --property CPUWeight=200 -- \
  bash -c '[[ $SINNIX_AGENT_SCOPED == 1 && $SINNIX_AGENT_SCOPE_UNIT == sinnix-agent-job-bridge.scope ]]'
jq -Rsc -e 'split("\n") | index("agent") != null and
  index("--unit") != null and index("sinnix-agent-job-bridge.scope") != null and
  index("--agent-property") != null and index("MemoryHigh=2G") != null and
  index("CPUWeight=200") != null' "${tmp}/bridge.receipt" >/dev/null

# Exercise production sinnix-scope with a fake systemd-run. The agent class's
# placement is rendered into the launcher at evaluation time, so these are the
# estate's real values (agent.slice, 8G/12G), not a fixture's: the assertions
# below are what the table means. Explicit job limits must occur after the
# rendered class defaults so they actually override them.
cat >"${tmp}/scope-bin/systemd-run" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' "$@" >"${SYSTEMD_RUN_RECEIPT:?}"
EOF
make_executable "${tmp}/scope-bin/systemd-run"
# Explicit </dev/null: the supervisor-wrapping decision below is keyed off
# whether sinnix-scope's own stdin is a terminal (interactive launches skip
# it so bash doesn't redirect the child's stdin from /dev/null and break TTY
# programs -- see flake/launch/scope-runtime.bash). Force the non-interactive path
# regardless of how this test script itself was invoked.
SYSTEMD_RUN_RECEIPT="${tmp}/systemd-run.receipt" \
  XDG_RUNTIME_DIR="${tmp}/runtime" PATH="${tmp}/scope-bin:${PATH}" \
  "${scope}" agent --unit sinnix-agent-job-scope-test.scope \
  --agent-property MemoryHigh=2G --agent-property CPUWeight=200 \
  --agent-property RuntimeMaxSec=600 -- true </dev/null
jq -Rsc -e '
  (split("\n") | map(select(length > 0))) as $args |
  ($args | map(select(startswith("--property=MemoryHigh=")))) ==
    ["--property=MemoryHigh=8G", "--property=MemoryHigh=2G"] and
  ($args | map(select(startswith("--property=CPUWeight=")))) ==
    ["--property=CPUWeight=200"] and
  ($args | index("--property=MemoryMax=12G")) != null and
  ($args | index("--property=IOAccounting=true")) != null and
  ($args | index("--property=IOWeight=300")) != null and
  ($args | index("--property=RuntimeMaxSec=600")) != null and
  ($args | index("--unit=sinnix-agent-job-scope-test.scope")) != null and
  ($args | index("--slice=agent.slice")) != null and
  ($args | index("--internal-supervise")) != null
' "${tmp}/systemd-run.receipt" >/dev/null

# A scope has no MainPID lifecycle: a daemonized descendant otherwise keeps it
# active after the requested command exits. Exercise the production supervisor
# against a real orphan child, and require both cleanup and status propagation.
orphan_pid_file="${tmp}/orphan.pid"
cgroup_procs="${tmp}/cgroup.procs"
set +e
SINNIX_SCOPE_CGROUP_PROCS="$cgroup_procs" \
  "$scope" --internal-supervise -- bash -c '
    sleep 300 &
    orphan=$!
    printf "%s\n" "$BASHPID" "$orphan" >"$1"
    printf "%s\n" "$orphan" >"$2"
    exit 23
  ' bash "$cgroup_procs" "$orphan_pid_file"
supervisor_status=$?
set -e
[[ $supervisor_status -eq 23 ]]
orphan_pid="$(<"$orphan_pid_file")"
if kill -0 "$orphan_pid" 2>/dev/null; then
  echo "scope supervisor left orphan process $orphan_pid alive" >&2
  exit 1
fi

echo "agent job handle tests passed"
