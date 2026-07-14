#!/usr/bin/env bash
set -euo pipefail

skill_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
repo_root="$(git -C "${skill_dir}" rev-parse --show-toplevel)"
runner="${skill_dir}/scripts/run_agent_prompt.sh"
control="${skill_dir}/scripts/agent_job_control.sh"
scope_exec="${repo_root}/scripts/sinnix-agent-scope-exec"
scope="${repo_root}/scripts/sinnix-scope"

tmp="$(mktemp -d)"
cleanup() {
  [[ -z ${hold_pid:-} ]] || kill "${hold_pid}" 2>/dev/null || true
  wait "${hold_pid:-}" 2>/dev/null || true
  rm -rf "${tmp}"
}
trap cleanup EXIT

mkdir -p "${tmp}/bin" "${tmp}/bridge-bin" "${tmp}/scope-bin" "${tmp}/repo" \
  "${tmp}/state" "${tmp}/output" "${tmp}/proc" "${tmp}/scope-receipts" \
  "${tmp}/runtime"
git -C "${tmp}/repo" init -q
git -C "${tmp}/repo" -c user.name=Test -c user.email=test@example.invalid commit -q --allow-empty -m seed
git -C "${tmp}/repo" worktree add -q -b agent-test "${tmp}/worktree"
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
while [[ $# -gt 0 ]]; do
  case "$1" in
    --output-last-message) last="$2"; shift 2 ;;
    *) shift ;;
  esac
done
cat >/dev/null
printf 'fake final\n' >"${last}"
if [[ ${FAKE_CODEX_HOLD:-0} == 1 ]]; then sleep 30; fi
exit "${FAKE_CODEX_EXIT:-0}"
EOF
cat >"${tmp}/bin/systemctl" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
if [[ $2 == show ]]; then
  if [[ ${FAKE_MISSING_UNIT:-} == "${3:-}" ]]; then
    exit 1
  fi
  cat <<OUT
ActiveState=active
SubState=running
MainPID=${FAKE_SYSTEMD_PID:-0}
ControlGroup=${FAKE_SYSTEMD_CGROUP:?missing FAKE_SYSTEMD_CGROUP}
MemoryHigh=2G
MemoryMax=3G
CPUWeight=200
IOWeight=300
OUT
elif [[ $2 == stop ]]; then
  : "${FAKE_STOP_MARKER:?missing FAKE_STOP_MARKER}"
  touch "${FAKE_STOP_MARKER}"
else
  exit 64
fi
EOF
chmod +x "${tmp}/bin/"*

run_job() {
  local id="$1"
  local prompt="$2"
  env -u SINNIX_AGENT_SCOPED -u SINNIX_AGENT_SCOPE_UNIT -u SINNIX_AGENT_SCOPE_CGROUP \
    PATH="${tmp}/bin:${PATH}" SINNIX_AGENT_SCOPE_EXEC="${tmp}/bin/scope-exec" \
    FAKE_SCOPE_RECEIPT_DIR="${tmp}/scope-receipts" \
    "${runner}" --job-id "${id}" --job-state-dir "${tmp}/state" --job-role source-review \
    --work-item sinnix-056.1 --agent codex --model fake --reasoning-effort high \
    --workdir "${tmp}/worktree" --prompt-file "${prompt}" \
    --log-file "${tmp}/output/${id}.log" --last-file "${tmp}/output/${id}.final" \
    --memory-high 2G --memory-max 3G --cpu-weight 200 --io-weight 300
}

run_job job-one "${tmp}/prompt.prompt"
run_job job-two "${tmp}/prompt.prompt"

[[ -f ${tmp}/state/job-one.json && -f ${tmp}/state/job-two.json ]]
[[ -f ${tmp}/output/job-one.log && -f ${tmp}/output/job-one.final ]]
jq -e --arg repo "${tmp}/repo" --arg worktree "${tmp}/worktree" '
  .job_id == "job-one" and .lifecycle == "completed" and .exit_status == 0 and
  .repo == $repo and .worktree == $worktree and .backend == "codex" and .model == "fake" and
  (.prompt.sha256 | length == 64) and .artifacts.final != "" and
  .launcher.scope_unit == "sinnix-agent-job-job-one.scope" and
  .launcher.cgroup == "/fake/sinnix-agent-job-job-one.scope"
' "${tmp}/state/job-one.json" >/dev/null
mapfile -t forwarded_properties <"${tmp}/scope-receipts/sinnix-agent-job-job-one.scope"
[[ ${forwarded_properties[*]} == "MemoryHigh=2G MemoryMax=3G CPUWeight=200 IOWeight=300" ]]

jq -e '[.[] | .job_id] == ["job-one", "job-two"]' <(
  FAKE_SYSTEMD_CGROUP=/fake/unused SINNIX_AGENT_SYSTEMCTL="${tmp}/bin/systemctl" \
    "${control}" --state-dir "${tmp}/state" list
) >/dev/null
FAKE_MISSING_UNIT=sinnix-agent-job-job-two.scope FAKE_SYSTEMD_CGROUP=/fake/unused \
  SINNIX_AGENT_SYSTEMCTL="${tmp}/bin/systemctl" "${control}" --state-dir "${tmp}/state" list |
  jq -e 'length == 2 and (map(select(.job_id == "job-two"))[0].live.available == false)' >/dev/null

FAKE_SYSTEMD_CGROUP=/fake/sinnix-agent-job-job-one.scope \
  SINNIX_AGENT_SYSTEMCTL="${tmp}/bin/systemctl" "${control}" --state-dir "${tmp}/state" status --job job-one |
  jq -e '.live.MemoryHigh == "2G" and .live.MemoryMax == "3G" and .live.CPUWeight == "200" and .live.IOWeight == "300"' >/dev/null

if FAKE_CODEX_EXIT=23 run_job job-fail "${tmp}/prompt.prompt"; then
  echo "failing backend unexpectedly succeeded" >&2
  exit 1
fi
jq -e '.lifecycle == "failed" and .exit_status == 23' \
  "${tmp}/state/job-fail.json" >/dev/null
if run_job job-one "${tmp}/prompt.prompt"; then
  echo "duplicate job handle unexpectedly overwrote its manifest" >&2
  exit 1
fi

env -u SINNIX_AGENT_SCOPED -u SINNIX_AGENT_SCOPE_UNIT -u SINNIX_AGENT_SCOPE_CGROUP \
  PATH="${tmp}/bin:${PATH}" SINNIX_AGENT_SCOPE_EXEC="${tmp}/bin/scope-exec" FAKE_CODEX_HOLD=1 \
  FAKE_SCOPE_RECEIPT_DIR="${tmp}/scope-receipts" \
  "${runner}" --job-id job-hold --job-state-dir "${tmp}/state" --agent codex --model fake \
  --workdir "${tmp}/worktree" --prompt-file "${tmp}/hold.prompt" \
  --log-file "${tmp}/output/job-hold.log" --last-file "${tmp}/output/job-hold.final" &
hold_pid=$!
for _ in {1..100}; do
  [[ -f ${tmp}/state/job-hold.json ]] && [[ $(jq -r .lifecycle "${tmp}/state/job-hold.json") == running ]] && break
  sleep 0.05
done
[[ $(jq -r .lifecycle "${tmp}/state/job-hold.json") == running ]]
manifest_pid="$(jq -r .launcher.pid "${tmp}/state/job-hold.json")"
mkdir -p "${tmp}/proc/${manifest_pid}"
printf '0::/wrong/cgroup\n' >"${tmp}/proc/${manifest_pid}/cgroup"
ln -s "${tmp}/worktree" "${tmp}/proc/${manifest_pid}/cwd"

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
FAKE_SYSTEMD_PID="${manifest_pid}" \
  FAKE_SYSTEMD_CGROUP=/fake/sinnix-agent-job-job-hold.scope \
  FAKE_STOP_MARKER="${tmp}/stopped" SINNIX_AGENT_SYSTEMCTL="${tmp}/bin/systemctl" \
  SINNIX_AGENT_PROC_ROOT="${tmp}/proc" \
  "${control}" --state-dir "${tmp}/state" interrupt --job job-hold
[[ -e ${tmp}/stopped ]]

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
chmod +x "${tmp}/bridge-bin/sinnix-scope"
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

# Exercise production sinnix-scope with a fake systemd-run. Explicit job limits
# must occur after inventory defaults so they actually override them.
cat >"${tmp}/scope-bin/systemd-run" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' "$@" >"${SYSTEMD_RUN_RECEIPT:?}"
EOF
chmod +x "${tmp}/scope-bin/systemd-run"
cat >"${tmp}/runtime-inventory.json" <<'EOF'
{
  "commandClasses": {
    "agent": {
      "slice": "agent-test.slice",
      "systemdProperties": {"MemoryHigh": "1G", "CPUWeight": "100"}
    }
  }
}
EOF
SYSTEMD_RUN_RECEIPT="${tmp}/systemd-run.receipt" \
  SINNIX_RUNTIME_INVENTORY_FILE="${tmp}/runtime-inventory.json" \
  XDG_RUNTIME_DIR="${tmp}/runtime" PATH="${tmp}/scope-bin:${PATH}" \
  "${scope}" agent --unit sinnix-agent-job-scope-test.scope \
  --agent-property MemoryHigh=2G --agent-property CPUWeight=200 -- true
jq -Rsc -e '
  (split("\n") | map(select(length > 0))) as $args |
  ($args | map(select(startswith("--property=MemoryHigh=")))) ==
    ["--property=MemoryHigh=1G", "--property=MemoryHigh=2G"] and
  ($args | map(select(startswith("--property=CPUWeight=")))) ==
    ["--property=CPUWeight=100", "--property=CPUWeight=200"] and
  ($args | index("--unit=sinnix-agent-job-scope-test.scope")) != null and
  ($args | index("--slice=agent-test.slice")) != null and
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
