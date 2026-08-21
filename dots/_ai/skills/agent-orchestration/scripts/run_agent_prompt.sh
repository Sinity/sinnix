#!/usr/bin/env bash
set -euo pipefail

agent=""
workdir=""
prompt_file=""
log_file=""
json_file=""
last_file=""
model=""
reasoning_effort=""
schema_file=""
json_mode=0
skip_agents_render=0
ephemeral=0
claude_api_key_auth=0
credential_profile="subscription"
job_id=""
launch_id=""
job_state_dir="${SINNIX_AGENT_JOB_STATE_DIR:-${XDG_STATE_HOME:-$HOME/.local/state}/sinnix/agent-jobs}"
job_role=""
work_item=""
parent_job_id=""
coordinator_job_id=""
provider=""
account_hash=""
vendor_session_id=""
polylogue_session_id=""
kitty_socket=""
kitty_window_id=""
hyprland_address=""
quota_snapshot_id=""
environment_file=""
environment_sha256=""
memory_high=""
memory_max=""
cpu_weight=""
io_weight=""
timeout_seconds="14400"
internal_agent_scope=0
job_started_epoch="$(date +%s)"
codex_sandbox=""
codex_home=""
codex_skip_git_check=0
max_retries=3

usage() {
  cat <<'EOF'
Usage:
  run_agent_prompt.sh [options]

Required:
  --agent <claude|codex|gemini|grok|antigravity>
  --workdir <path>
  --prompt-file <path>
  --log-file <path>

Existing options:
  --json-file <path>
  --last-file <path>
  --model <name>
  --reasoning-effort <value>
  --schema-file <path>
  --json
  --skip-agents-render
  --ephemeral
  --claude-api-key-auth       Keep ANTHROPIC_API_KEY for Claude instead of subscription auth
  --credential-profile <subscription|api>

Codex-specific options (ignored by other backends):
  --sandbox <mode>            Passthrough to `codex exec -s <mode>` (e.g. read-only)
  --codex-home <path>         Override CODEX_HOME for this invocation only (e.g. a
                               scratch dir with no AGENTS.md, to run without global
                               environment-memory context)
  --skip-git-repo-check       Passthrough to `codex exec --skip-git-repo-check`

Resilience:
  --max-retries <n>           Retry the agent invocation up to n times (default 3)
                               if its log shows a transient launcher race
                               ("Text file busy" from the shared npm-bootstrap
                               launcher regenerating mid-exec under concurrent
                               fanout). 0 disables retry.

Attested job options:
  --job-id <stable-id>        Generated when omitted
  --launch-id <opaque-id>     Generated when omitted
  --job-state-dir <path>      Default: $XDG_STATE_HOME/sinnix/agent-jobs
  --job-role <description>
  --work-item <bead-or-label>
  --parent-job-id <stable-id>
  --coordinator-job-id <stable-id>
  --provider <provider>
  --account-hash <hash>
  --vendor-session-id <id>
  --polylogue-session-id <id>
  --kitty-socket <path>
  --kitty-window-id <id>
  --hyprland-address <address>
  --quota-snapshot-id <id>
  --environment-file <path>  Private JSON object of explicit child-environment overrides
  --environment-sha256 <digest>  Digest of the environment overlay
  --memory-high <limit>
  --memory-max <limit>
  --cpu-weight <1-10000>
  --io-weight <1-10000>
  --timeout-seconds <seconds>  Enforced by systemd RuntimeMaxSec
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
  --agent)
    agent="${2:?missing value for --agent}"
    shift 2
    ;;
  --workdir)
    workdir="${2:?missing value for --workdir}"
    shift 2
    ;;
  --prompt-file)
    prompt_file="${2:?missing value for --prompt-file}"
    shift 2
    ;;
  --log-file)
    log_file="${2:?missing value for --log-file}"
    shift 2
    ;;
  --json-file)
    json_file="${2:?missing value for --json-file}"
    shift 2
    ;;
  --last-file)
    last_file="${2:?missing value for --last-file}"
    shift 2
    ;;
  --model)
    model="${2:?missing value for --model}"
    shift 2
    ;;
  --reasoning-effort)
    reasoning_effort="${2:?missing value for --reasoning-effort}"
    shift 2
    ;;
  --schema-file)
    schema_file="${2:?missing value for --schema-file}"
    shift 2
    ;;
  --job-id)
    job_id="${2:?missing value for --job-id}"
    shift 2
    ;;
  --launch-id)
    launch_id="${2:?missing value for --launch-id}"
    shift 2
    ;;
  --job-state-dir)
    job_state_dir="${2:?missing value for --job-state-dir}"
    shift 2
    ;;
  --job-role)
    job_role="${2:?missing value for --job-role}"
    shift 2
    ;;
  --work-item)
    work_item="${2:?missing value for --work-item}"
    shift 2
    ;;
  --parent-job-id)
    parent_job_id="${2:?missing value for --parent-job-id}"
    shift 2
    ;;
  --coordinator-job-id)
    coordinator_job_id="${2:?missing value for --coordinator-job-id}"
    shift 2
    ;;
  --provider)
    provider="${2:?missing value for --provider}"
    shift 2
    ;;
  --account-hash)
    account_hash="${2:?missing value for --account-hash}"
    shift 2
    ;;
  --vendor-session-id)
    vendor_session_id="${2:?missing value for --vendor-session-id}"
    shift 2
    ;;
  --polylogue-session-id)
    polylogue_session_id="${2:?missing value for --polylogue-session-id}"
    shift 2
    ;;
  --kitty-socket)
    kitty_socket="${2:?missing value for --kitty-socket}"
    shift 2
    ;;
  --kitty-window-id)
    kitty_window_id="${2:?missing value for --kitty-window-id}"
    shift 2
    ;;
  --hyprland-address)
    hyprland_address="${2:?missing value for --hyprland-address}"
    shift 2
    ;;
  --quota-snapshot-id)
    quota_snapshot_id="${2:?missing value for --quota-snapshot-id}"
    shift 2
    ;;
  --environment-file)
    environment_file="${2:?missing value for --environment-file}"
    shift 2
    ;;
  --environment-sha256)
    environment_sha256="${2:?missing value for --environment-sha256}"
    shift 2
    ;;
  --memory-high)
    memory_high="${2:?missing value for --memory-high}"
    shift 2
    ;;
  --memory-max)
    memory_max="${2:?missing value for --memory-max}"
    shift 2
    ;;
  --cpu-weight)
    cpu_weight="${2:?missing value for --cpu-weight}"
    shift 2
    ;;
  --io-weight)
    io_weight="${2:?missing value for --io-weight}"
    shift 2
    ;;
  --timeout-seconds)
    timeout_seconds="${2:?missing value for --timeout-seconds}"
    shift 2
    ;;
  --internal-agent-scope)
    internal_agent_scope=1
    shift
    ;;
  --json)
    json_mode=1
    shift
    ;;
  --skip-agents-render)
    skip_agents_render=1
    shift
    ;;
  --ephemeral)
    ephemeral=1
    shift
    ;;
  --claude-api-key-auth)
    claude_api_key_auth=1
    credential_profile="api"
    shift
    ;;
  --credential-profile)
    credential_profile="${2:?missing value for --credential-profile}"
    shift 2
    ;;
  --sandbox)
    codex_sandbox="${2:?missing value for --sandbox}"
    shift 2
    ;;
  --codex-home)
    codex_home="${2:?missing value for --codex-home}"
    shift 2
    ;;
  --skip-git-repo-check)
    codex_skip_git_check=1
    shift
    ;;
  --max-retries)
    max_retries="${2:?missing value for --max-retries}"
    shift 2
    ;;
  -h | --help)
    usage
    exit 0
    ;;
  *)
    echo "unknown option: $1" >&2
    usage >&2
    exit 2
    ;;
  esac
done

if [[ -z ${agent} || -z ${workdir} || -z ${prompt_file} || -z ${log_file} ]]; then
  usage >&2
  exit 2
fi
[[ -f ${prompt_file} ]] || {
  echo "missing prompt: ${prompt_file}" >&2
  exit 1
}
[[ -d ${workdir} ]] || {
  echo "missing workdir: ${workdir}" >&2
  exit 1
}
command -v jq >/dev/null 2>&1 || {
  echo "run_agent_prompt.sh requires jq" >&2
  exit 1
}
command -v sha256sum >/dev/null 2>&1 || {
  echo "run_agent_prompt.sh requires sha256sum" >&2
  exit 1
}
command -v python3 >/dev/null 2>&1 || {
  echo "run_agent_prompt.sh requires python3" >&2
  exit 1
}

if [[ -z ${job_id} ]]; then
  job_id="$(cat /proc/sys/kernel/random/uuid)"
fi
if [[ -z ${launch_id} ]]; then
  launch_id="$(cat /proc/sys/kernel/random/uuid)"
fi
[[ ${job_id} =~ ^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$ ]] || {
  echo "invalid --job-id: ${job_id}" >&2
  exit 2
}
[[ ${launch_id} =~ ^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$ ]] || {
  echo "invalid --launch-id: ${launch_id}" >&2
  exit 2
}
[[ ${timeout_seconds} =~ ^[0-9]+$ && ${timeout_seconds} -ge 30 && ${timeout_seconds} -le 86400 ]] || {
  echo "invalid --timeout-seconds: ${timeout_seconds}" >&2
  exit 2
}
[[ ${credential_profile} == subscription || ${credential_profile} == api ]] || {
  echo "invalid --credential-profile" >&2
  exit 2
}
[[ ${max_retries} =~ ^[0-9]+$ && ${max_retries} -le 10 ]] || {
  echo "invalid --max-retries: ${max_retries}" >&2
  exit 2
}
[[ ${credential_profile} != api ]] || claude_api_key_auth=1
cleanup_environment_file() {
  [[ -z ${environment_file} ]] || rm -f -- "${environment_file}"
}
trap cleanup_environment_file EXIT
if [[ -n ${environment_file} ]]; then
  [[ -n ${environment_sha256} && ${environment_sha256} =~ ^[0-9a-f]{64}$ ]] || {
    echo "--environment-file requires a SHA-256 digest" >&2
    exit 2
  }
  [[ -f ${environment_file} ]] || {
    echo "missing environment overlay: ${environment_file}" >&2
    exit 1
  }
fi

umask 077
mkdir -p "${job_state_dir}" "${job_state_dir}/.reservations" "$(dirname "${log_file}")"
chmod 0700 "${job_state_dir}"
chmod 0700 "${job_state_dir}/.reservations"
[[ -z ${json_file} ]] || mkdir -p "$(dirname "${json_file}")"
[[ -z ${last_file} ]] || mkdir -p "$(dirname "${last_file}")"

manifest="${job_state_dir}/${job_id}.json"
reservation="${job_state_dir}/.reservations/${job_id}"
if [[ ${internal_agent_scope} -eq 0 ]]; then
  if ! mkdir -m 0700 "${reservation}" 2>/dev/null; then
    echo "refusing reserved job handle: ${job_id}" >&2
    exit 2
  fi
  printf '%s\n' "${launch_id}" >"${reservation}/launch-id"
  chmod 0600 "${reservation}/launch-id"
  if [[ -e ${manifest} ]]; then
    echo "refusing to overwrite existing job handle: ${job_id}" >&2
    exit 2
  fi
elif [[ ! -r ${reservation}/launch-id || $(<"${reservation}/launch-id") != "${launch_id}" ]]; then
  echo "refusing mismatched job reservation: ${job_id}" >&2
  exit 2
fi
worktree="$(cd "${workdir}" && pwd -P)"
git_common_dir="$(git -C "${worktree}" rev-parse --path-format=absolute --git-common-dir 2>/dev/null || true)"
if [[ -n ${git_common_dir} && $(basename "${git_common_dir}") == .git ]]; then
  repo_root="$(dirname "${git_common_dir}")"
else
  repo_root="$(git -C "${worktree}" rev-parse --show-toplevel 2>/dev/null || printf '%s' "${worktree}")"
fi
branch="$(git -C "${worktree}" symbolic-ref --quiet --short HEAD 2>/dev/null || printf '%s' "DETACHED")"
prompt_sha256="$(sha256sum "${prompt_file}" | awk '{print $1}')"
scope_unit="sinnix-agent-job-${job_id}.scope"
scope_cgroup="${SINNIX_AGENT_SCOPE_CGROUP:-}"
if [[ -z ${scope_cgroup} && -n ${SINNIX_AGENT_SCOPE_UNIT:-} ]]; then
  scope_cgroup="$(awk -F: -v unit="${SINNIX_AGENT_SCOPE_UNIT}" '$3 ~ ("/" unit "$|/" unit "/") { print $3; exit }' /proc/self/cgroup 2>/dev/null || true)"
fi

# The manifest, the event log, the actual-agent attestation, the cgroup
# completion accounting and the supervised run (including the launcher-race
# retry ladder) live in the sibling run_agent_prompt_job.py (sinnix-gdlu): the
# manifest is a hard contract, read directly by agent_job_control.sh and
# attested by `sinnix-observe orphans`, so one implementation owns its bytes.
# This script keeps option parsing, the reservation lock, the self-reexec,
# per-backend argv, and the scrubbed child environment.
job_helper="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)/run_agent_prompt_job.py"
job_args=(
  --job-id "${job_id}"
  --job-state-dir "${job_state_dir}"
  --launch-id "${launch_id}"
  --backend "${agent}"
  --model "${model}"
  --effort "${reasoning_effort}"
  --repo "${repo_root}"
  --worktree "${worktree}"
  --branch "${branch}"
  --prompt-path "${prompt_file}"
  --prompt-sha256 "${prompt_sha256}"
  --log-path "${log_file}"
  --json-path "${json_file}"
  --final-path "${last_file}"
  --role "${job_role}"
  --work-item "${work_item}"
  --parent-job-id "${parent_job_id}"
  --coordinator-job-id "${coordinator_job_id}"
  --provider "${provider}"
  --account-hash "${account_hash}"
  --vendor-session-id "${vendor_session_id}"
  --polylogue-session-id "${polylogue_session_id}"
  --kitty-socket "${kitty_socket}"
  --kitty-window-id "${kitty_window_id}"
  --hyprland-address "${hyprland_address}"
  --quota-snapshot-id "${quota_snapshot_id}"
  --environment-sha256 "${environment_sha256}"
  --agent-executable ""
  --scope-unit "${SINNIX_AGENT_SCOPE_UNIT:-${scope_unit}}"
  --scope-cgroup "${scope_cgroup}"
  --launcher-pid "$$"
  --memory-high "${memory_high}"
  --memory-max "${memory_max}"
  --cpu-weight "${cpu_weight}"
  --io-weight "${io_weight}"
  --timeout-seconds "${timeout_seconds}"
)

write_manifest() {
  if [[ $# -ge 2 ]]; then
    python3 "${job_helper}" write "${job_args[@]}" --lifecycle "$1" --exit-status "$2"
  else
    python3 "${job_helper}" write "${job_args[@]}" --lifecycle "$1"
  fi
}

recorded_lifecycle() {
  python3 "${job_helper}" lifecycle "${job_args[@]}"
}

if [[ ${internal_agent_scope} -eq 0 && -z ${SINNIX_AGENT_SCOPED:-} ]]; then
  write_manifest accepted
  write_manifest starting
  scope_exec="${SINNIX_AGENT_SCOPE_EXEC:-$(command -v sinnix-agent-scope-exec 2>/dev/null || true)}"
  [[ -n ${scope_exec} && -x ${scope_exec} ]] || {
    write_manifest failed 125
    echo "run_agent_prompt.sh requires sinnix-agent-scope-exec for attested jobs" >&2
    exit 1
  }
  scope_args=(--unit "${scope_unit}")
  [[ -z ${memory_high} ]] || scope_args+=(--property "MemoryHigh=${memory_high}")
  [[ -z ${memory_max} ]] || scope_args+=(--property "MemoryMax=${memory_max}")
  [[ -z ${cpu_weight} ]] || scope_args+=(--property "CPUWeight=${cpu_weight}")
  [[ -z ${io_weight} ]] || scope_args+=(--property "IOWeight=${io_weight}")
  scope_args+=(--property "RuntimeMaxSec=${timeout_seconds}")
  inner_args=(
    "$0" --internal-agent-scope --job-id "${job_id}" --launch-id "${launch_id}" --job-state-dir "${job_state_dir}"
    --agent "${agent}" --workdir "${workdir}" --prompt-file "${prompt_file}" --log-file "${log_file}"
    --timeout-seconds "${timeout_seconds}"
  )
  [[ -z ${environment_file} ]] || inner_args+=(--environment-file "${environment_file}" --environment-sha256 "${environment_sha256}")
  [[ -z ${model} ]] || inner_args+=(--model "${model}")
  [[ -z ${reasoning_effort} ]] || inner_args+=(--reasoning-effort "${reasoning_effort}")
  [[ -z ${job_role} ]] || inner_args+=(--job-role "${job_role}")
  [[ -z ${work_item} ]] || inner_args+=(--work-item "${work_item}")
  [[ -z ${parent_job_id} ]] || inner_args+=(--parent-job-id "${parent_job_id}")
  [[ -z ${coordinator_job_id} ]] || inner_args+=(--coordinator-job-id "${coordinator_job_id}")
  [[ -z ${provider} ]] || inner_args+=(--provider "${provider}")
  [[ -z ${account_hash} ]] || inner_args+=(--account-hash "${account_hash}")
  [[ -z ${vendor_session_id} ]] || inner_args+=(--vendor-session-id "${vendor_session_id}")
  [[ -z ${polylogue_session_id} ]] || inner_args+=(--polylogue-session-id "${polylogue_session_id}")
  [[ -z ${kitty_socket} ]] || inner_args+=(--kitty-socket "${kitty_socket}")
  [[ -z ${kitty_window_id} ]] || inner_args+=(--kitty-window-id "${kitty_window_id}")
  [[ -z ${hyprland_address} ]] || inner_args+=(--hyprland-address "${hyprland_address}")
  [[ -z ${quota_snapshot_id} ]] || inner_args+=(--quota-snapshot-id "${quota_snapshot_id}")
  [[ -z ${memory_high} ]] || inner_args+=(--memory-high "${memory_high}")
  [[ -z ${memory_max} ]] || inner_args+=(--memory-max "${memory_max}")
  [[ -z ${cpu_weight} ]] || inner_args+=(--cpu-weight "${cpu_weight}")
  [[ -z ${io_weight} ]] || inner_args+=(--io-weight "${io_weight}")
  [[ -z ${json_file} ]] || inner_args+=(--json-file "${json_file}")
  [[ -z ${last_file} ]] || inner_args+=(--last-file "${last_file}")
  [[ -z ${schema_file} ]] || inner_args+=(--schema-file "${schema_file}")
  [[ -z ${codex_sandbox} ]] || inner_args+=(--sandbox "${codex_sandbox}")
  [[ -z ${codex_home} ]] || inner_args+=(--codex-home "${codex_home}")
  [[ ${codex_skip_git_check} -eq 0 ]] || inner_args+=(--skip-git-repo-check)
  inner_args+=(--max-retries "${max_retries}")
  [[ ${json_mode} -eq 0 ]] || inner_args+=(--json)
  [[ ${skip_agents_render} -eq 0 ]] || inner_args+=(--skip-agents-render)
  [[ ${ephemeral} -eq 0 ]] || inner_args+=(--ephemeral)
  [[ ${claude_api_key_auth} -eq 0 ]] || inner_args+=(--claude-api-key-auth)
  inner_args+=(--credential-profile "${credential_profile}")
  set +e
  "${scope_exec}" "${scope_args[@]}" -- "${inner_args[@]}"
  scope_status=$?
  set -e
  lifecycle="$(recorded_lifecycle)"
  if [[ ${lifecycle} == accepted || ${lifecycle} == starting || ${lifecycle} == running ]]; then
    write_manifest failed "${scope_status}"
  fi
  exit "${scope_status}"
fi

if [[ -n ${SINNIX_AGENT_SCOPED:-} && ${internal_agent_scope} -eq 0 && (-n ${memory_high} || -n ${memory_max} || -n ${cpu_weight} || -n ${io_weight}) ]]; then
  echo "resource overrides require this runner to create the agent scope" >&2
  exit 2
fi

if [[ ${internal_agent_scope} -eq 1 && (${SINNIX_AGENT_SCOPED:-} != 1 || ${SINNIX_AGENT_SCOPE_UNIT:-} != "${scope_unit}" || -z ${scope_cgroup}) ]]; then
  write_manifest failed 125
  echo "run_agent_prompt.sh: agent scope launch did not attest the expected job cgroup" >&2
  exit 125
fi

write_manifest running
# Invoked indirectly by the EXIT trap below. The manifest, not a shell flag,
# says whether the job was already finalized: run_agent_prompt_job.py writes
# the terminal state itself, so a terminal lifecycle means there is nothing
# left to record and anything else means this process died before recording it.
# shellcheck disable=SC2329
finalize_job() {
  local status=$?
  local lifecycle
  cleanup_environment_file
  lifecycle="$(recorded_lifecycle)"
  case "${lifecycle}" in
  succeeded | failed | cancelled | timed_out) return 0 ;;
  esac
  if [[ ${status} -eq 0 ]]; then
    write_manifest succeeded 0
  elif [[ ${lifecycle} == cancel_requested ]]; then
    write_manifest cancelled "${status}"
  elif [[ ${status} -eq 124 || ${status} -eq 137 || ${status} -eq 143 ]]; then
    write_manifest timed_out "${status}"
  else
    write_manifest failed "${status}"
  fi
}
trap finalize_job EXIT
cd "${workdir}"

resolve_agent_bin() {
  case "$1" in
  claude) command -v claude-full 2>/dev/null || command -v claude 2>/dev/null ;;
  codex | gemini) command -v "$1" ;;
  grok) command -v grok-sinnix 2>/dev/null || command -v grok 2>/dev/null ;;
  antigravity) command -v agy-sinnix 2>/dev/null || command -v agy 2>/dev/null ;;
  *) return 1 ;;
  esac
}
agent_bin="$(resolve_agent_bin "${agent}")" || {
  echo "${agent} runtime not found" >&2
  exit 1
}
job_args+=(--agent-executable "${agent_bin}")

# The agent runs with a scrubbed environment: an allowlist of session
# variables plus the per-backend additions, carried as an `env -i` prefix on
# the argv handed to the supervisor.
agent_env=(env -i)
for key in HOME LANG LC_ALL PATH SHELL TERM USER XDG_CONFIG_HOME XDG_DATA_HOME XDG_RUNTIME_DIR XDG_STATE_HOME DBUS_SESSION_BUS_ADDRESS DISPLAY WAYLAND_DISPLAY SSH_AUTH_SOCK SINNIX_AGENT_JOB_STATE_DIR SINNIX_AGENT_SCOPED SINNIX_AGENT_SCOPE_UNIT SINNIX_AGENT_SCOPE_CGROUP SINNIX_CORRELATION_ID; do
  [[ -z ${!key+x} ]] || agent_env+=("$key=${!key}")
done
if [[ ${agent} == claude && ${claude_api_key_auth} -eq 1 && -n ${ANTHROPIC_API_KEY+x} ]]; then agent_env+=("ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY"); fi
[[ ${skip_agents_render} -eq 0 ]] || agent_env+=(SINNIX_SKIP_AGENTS_RENDER=1)
[[ ${agent} != codex || -z ${codex_home} ]] || agent_env+=("CODEX_HOME=${codex_home}")

validate_environment_overlay() {
  python3 - "$environment_file" "$environment_sha256" <<'PY'
import hashlib
import json
import os
import re
import stat
import sys
from pathlib import Path

path = Path(sys.argv[1])
expected = sys.argv[2]
metadata = path.lstat()
if not stat.S_ISREG(metadata.st_mode) or stat.S_IMODE(metadata.st_mode) != 0o600:
    raise SystemExit("environment overlay must be a mode-0600 regular file")
if metadata.st_uid != os.getuid():
    raise SystemExit("environment overlay has an unexpected owner")
try:
    value = json.loads(path.read_text(encoding="utf-8"))
except (OSError, json.JSONDecodeError) as exc:
    raise SystemExit("environment overlay is malformed") from exc
if not isinstance(value, dict) or len(value) > 64:
    raise SystemExit("environment overlay must be an object with at most 64 variables")
for name, item in value.items():
    if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
        raise SystemExit("environment overlay contains an invalid variable name")
    if not isinstance(item, str) or len(item) > 8192 or "\x00" in item:
        raise SystemExit("environment overlay contains an invalid variable value")
payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
if hashlib.sha256(payload).hexdigest() != expected:
    raise SystemExit("environment overlay digest mismatch")
PY
}

if [[ -n ${environment_file} ]]; then
  validate_environment_overlay
  while IFS= read -r -d '' item; do
    agent_env+=("$item")
  done < <(python3 - "$environment_file" <<'PY'
import json
import sys

value = json.loads(open(sys.argv[1], encoding="utf-8").read())
for name, item in value.items():
    sys.stdout.buffer.write(f"{name}={item}".encode() + b"\0")
PY
  )
  rm -f -- "$environment_file"
fi

# Per-backend argv, plus the capture plan the supervisor needs: `split` sends
# stdout to the JSON artifact and stderr to the log, `merged` sends both to
# the log; `--final` says how the last-message artifact is produced; and
# `--stdin-file` marks the backends that read the prompt on stdin.
run_args=(--job-started-epoch "${job_started_epoch}" --max-retries "${max_retries}")
case "${agent}" in
codex)
  [[ -n ${model} && -n ${last_file} ]] || {
    echo "codex requires --model and --last-file" >&2
    exit 2
  }
  cmd=("${agent_env[@]}" "${agent_bin}" exec -C "${workdir}" --model "${model}" --output-last-message "${last_file}")
  [[ -z ${reasoning_effort} ]] || cmd+=(-c "model_reasoning_effort=\"${reasoning_effort}\"")
  [[ -z ${schema_file} ]] || cmd+=(--output-schema "${schema_file}")
  [[ -z ${codex_sandbox} ]] || cmd+=(-s "${codex_sandbox}")
  [[ ${codex_skip_git_check} -eq 0 ]] || cmd+=(--skip-git-repo-check)
  [[ ${ephemeral} -eq 0 ]] || cmd+=(--ephemeral)
  [[ ${json_mode} -eq 0 ]] || cmd+=(--json)
  cmd+=(-)
  run_args+=(--stdin-file "${prompt_file}" --final none)
  if [[ ${json_mode} -eq 1 ]]; then run_args+=(--capture split); else run_args+=(--capture merged); fi
  ;;
claude)
  prompt_text="$(<"${prompt_file}")"
  cmd=("${agent_env[@]}" "${agent_bin}" --print -p "${prompt_text}")
  [[ -z ${model} ]] || cmd+=(--model "${model}")
  [[ -z ${reasoning_effort} ]] || cmd+=(--effort "${reasoning_effort}")
  if [[ -n ${schema_file} ]]; then
    [[ -f ${schema_file} ]] || {
      echo "missing schema: ${schema_file}" >&2
      exit 1
    }
    cmd+=(--json-schema "$(<"${schema_file}")")
  fi
  if [[ ${json_mode} -eq 1 ]]; then
    cmd+=(--output-format json)
    run_args+=(--capture split --final json_result)
  else
    run_args+=(--capture merged --final copy)
  fi
  ;;
gemini)
  cmd=("${agent_env[@]}" "${agent_bin}")
  run_args+=(--stdin-file "${prompt_file}" --final none)
  if [[ ${json_mode} -eq 1 ]]; then run_args+=(--capture split); else run_args+=(--capture merged); fi
  ;;
grok)
  prompt_text="$(<"${prompt_file}")"
  cmd=("${agent_env[@]}" "${agent_bin}" --cwd "${workdir}" --single "${prompt_text}")
  [[ -z ${model} ]] || cmd+=(--model "${model}")
  [[ -z ${reasoning_effort} ]] || cmd+=(--reasoning-effort "${reasoning_effort}")
  if [[ -n ${schema_file} ]]; then
    [[ -f ${schema_file} ]] || {
      echo "missing schema: ${schema_file}" >&2
      exit 1
    }
    cmd+=(--json-schema "$(<"${schema_file}")")
  elif [[ ${json_mode} -eq 1 ]]; then
    cmd+=(--output-format json)
  fi
  if [[ ${json_mode} -eq 1 || -n ${schema_file} ]]; then
    [[ -n ${json_file} ]] || {
      echo "grok JSON output requires --json-file" >&2
      exit 2
    }
    run_args+=(--capture split --final copy)
  else
    run_args+=(--capture merged --final copy)
  fi
  ;;
antigravity)
  prompt_text="$(<"${prompt_file}")"
  cmd=("${agent_env[@]}" "${agent_bin}")
  [[ -z ${model} ]] || cmd+=(--model "${model}")
  [[ -z ${reasoning_effort} ]] || cmd+=(--effort "${reasoning_effort}")
  if [[ -n ${schema_file} ]]; then
    [[ -f ${schema_file} ]] || {
      echo "missing schema: ${schema_file}" >&2
      exit 1
    }
    cmd+=(--json-schema "${schema_file}")
  elif [[ ${json_mode} -eq 1 ]]; then
    cmd+=(--output-format json)
  fi
  cmd+=(--print "${prompt_text}")
  if [[ ${json_mode} -eq 1 || -n ${schema_file} ]]; then
    [[ -n ${json_file} ]] || {
      echo "Antigravity JSON output requires --json-file" >&2
      exit 2
    }
    run_args+=(--capture split --final copy)
  else
    run_args+=(--capture merged --final copy)
  fi
  ;;
*)
  echo "unknown agent: ${agent}" >&2
  exit 2
  ;;
esac

status=0
python3 "${job_helper}" run "${job_args[@]}" "${run_args[@]}" -- "${cmd[@]}" || status=$?
exit "${status}"
