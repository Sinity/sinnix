#!/usr/bin/env bash
set -euo pipefail

agent="codex"
workdir=""
prompt_dir=""
output_dir=""
mode="batch"      # batch | kitty
launch_type="tab" # tab | os-window
model=""
reasoning_effort=""
schema_file=""
json_mode=0
dry_run=0
skip_agents_render=0
ephemeral=0
parallel=1
workspace=""
claude_api_key_auth=0
persist_windows=0
per_task_workdir_base=""
job_prefix=""
status_only=0
tails_mode=0
tails_n=12
tails_all=0
persist_shell="${SHELL:-bash}"
codex_sandbox=""
codex_home=""
codex_skip_git_check=0
max_retries=""
no_agents_md=0

usage() {
  cat <<'EOF'
Usage:
  launch_agent_tabs.sh [options] <prompt_file...>

Required:
  --agent <claude|codex|gemini|grok|antigravity>
  --workdir <path>
  --prompt-dir <path>
  --output-dir <path>

Options:
  --mode <batch|kitty>         Execution mode (default: batch)
  --launch-type <tab|os-window> Kitty launch type (default: tab)
  --model <name>               Agent model (agent-specific default)
  --reasoning-effort <value>   Agent effort level (agent-specific values)
  --xhigh                      Convenience: --reasoning-effort xhigh (codex only)
  --spark                      Convenience: set --model gpt-5.3-codex-spark (codex only)
  --schema <file>              JSON schema path for structured output
  --json                       Enable agent --json output
  --ephemeral                  Run each exec without persisting session files (codex only)
  --parallel <n>               Concurrent batch workers (default: 1; batch mode only)
  --workspace <name>           Silently move Kitty OS windows to this Hyprland workspace
  --claude-api-key-auth        Keep ANTHROPIC_API_KEY for Claude instead of subscription auth
  --skip-agents-render         Set SINNIX_SKIP_AGENTS_RENDER=1 for launched agent commands
  --sandbox <mode>              Codex only: passthrough to `codex exec -s <mode>`
                                (e.g. read-only). Not persisted; pass every run.
  --codex-home <path>           Codex only: override CODEX_HOME for every task
  --no-agents-md                Codex only: auto-provision (and cache, refreshed
                                when the real config.toml changes) a scratch
                                CODEX_HOME with auth.json/config.toml/models
                                copied over but no AGENTS.md, so tasks run
                                without the global environment-memory file.
                                Equivalent to a managed --codex-home.
  --skip-git-repo-check         Codex only: passthrough --skip-git-repo-check
  --max-retries <n>              Passthrough retry count for the shared-launcher
                                race (default from run_agent_prompt.sh: 3)
  --persist-windows            Kitty mode: keep each window open after the runner
                               exits (drops to an interactive shell in the task
                               workdir) and write <name>.exit status markers
  --per-task-workdir-base <dir> Resolve each task's workdir as <dir>/<prompt_name>
                               (e.g. per-lane git worktrees); makes --workdir optional
  --job-prefix <prefix>        Pass attested job identity to the runner:
                               --job-id <prefix><name> --work-item <name>
  --status                     Report task states from --output-dir (.exit/.log
                               markers) instead of launching; then exit.
                               Colored on a tty (NO_COLOR disables); shows
                               runtime and idle (time since last log write)
  --tails [n]                  Show the last n lines (default 12) of each
                               RUNNING task's newest log, legibly separated;
                               add task names to limit, or --tails-all to
                               include finished/stale tasks
  --tails-all                  With --tails: include non-running tasks
  --dry-run                    Print commands without executing

Prompt file convention:
  <prompt-dir>/<prompt_name>.prompt
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
  --prompt-dir)
    prompt_dir="${2:?missing value for --prompt-dir}"
    shift 2
    ;;
  --output-dir)
    output_dir="${2:?missing value for --output-dir}"
    shift 2
    ;;
  --mode)
    mode="${2:?missing value for --mode}"
    shift 2
    ;;
  --launch-type)
    launch_type="${2:?missing value for --launch-type}"
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
  --xhigh)
    reasoning_effort="xhigh"
    shift
    ;;
  --spark)
    model="gpt-5.3-codex-spark"
    shift
    ;;
  --schema)
    schema_file="${2:?missing value for --schema}"
    shift 2
    ;;
  --json)
    json_mode=1
    shift
    ;;
  --ephemeral)
    ephemeral=1
    shift
    ;;
  --parallel)
    parallel="${2:?missing value for --parallel}"
    shift 2
    ;;
  --workspace)
    workspace="${2:?missing value for --workspace}"
    shift 2
    ;;
  --claude-api-key-auth)
    claude_api_key_auth=1
    shift
    ;;
  --persist-windows)
    persist_windows=1
    shift
    ;;
  --per-task-workdir-base)
    per_task_workdir_base="${2:?missing value for --per-task-workdir-base}"
    shift 2
    ;;
  --job-prefix)
    job_prefix="${2:?missing value for --job-prefix}"
    shift 2
    ;;
  --status)
    status_only=1
    shift
    ;;
  --tails)
    tails_mode=1
    if [[ ${2:-} =~ ^[0-9]+$ ]]; then
      tails_n="$2"
      shift
    fi
    shift
    ;;
  --tails-all)
    tails_all=1
    shift
    ;;
  --skip-agents-render)
    skip_agents_render=1
    shift
    ;;
  --sandbox)
    codex_sandbox="${2:?missing value for --sandbox}"
    shift 2
    ;;
  --codex-home)
    codex_home="${2:?missing value for --codex-home}"
    shift 2
    ;;
  --no-agents-md)
    no_agents_md=1
    shift
    ;;
  --skip-git-repo-check)
    codex_skip_git_check=1
    shift
    ;;
  --max-retries)
    max_retries="${2:?missing value for --max-retries}"
    shift 2
    ;;
  --dry-run)
    dry_run=1
    shift
    ;;
  -h | --help)
    usage
    exit 0
    ;;
  --)
    shift
    break
    ;;
  -*)
    echo "unknown option: $1" >&2
    usage >&2
    exit 2
    ;;
  *)
    break
    ;;
  esac
done

# State classification (log-generation grouping, fuser-based writer-PID
# liveness, RUNNING/DONE/FAILED/STALE verdicts, tty color/tail formatting)
# lives in the sibling launch_agent_tabs_status.py (sinnix-3pjj); this stays
# a thin dispatcher so the launch-orchestration half below stays shell-only.
if [[ ${status_only} -eq 1 || ${tails_mode} -eq 1 ]]; then
  if [[ -z ${output_dir} || ! -d ${output_dir} ]]; then
    echo "--status/--tails require an existing --output-dir" >&2
    exit 2
  fi
  status_script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
  status_helper="${status_script_dir}/launch_agent_tabs_status.py"
  declare -a status_py_args=(--output-dir "${output_dir}")
  if [[ ${tails_mode} -eq 1 ]]; then
    status_py_args+=(--tails --tails-n "${tails_n}")
    [[ ${tails_all} -eq 1 ]] && status_py_args+=(--tails-all)
    status_py_args+=(-- "$@")
  else
    status_py_args+=(--status)
  fi
  exec python3 "${status_helper}" "${status_py_args[@]}"
fi

if [[ -z ${workdir} && -z ${per_task_workdir_base} ]] || [[ -z ${prompt_dir} || -z ${output_dir} ]]; then
  usage >&2
  exit 2
fi

if [[ ${mode} != "batch" && ${mode} != "kitty" ]]; then
  echo "invalid --mode: ${mode}" >&2
  exit 2
fi

if [[ ${launch_type} != "tab" && ${launch_type} != "os-window" ]]; then
  echo "invalid --launch-type: ${launch_type}" >&2
  exit 2
fi

if [[ ! ${parallel} =~ ^[1-9][0-9]*$ ]]; then
  echo "invalid --parallel value: ${parallel}" >&2
  exit 2
fi
if [[ ${parallel} -gt 1 && ${mode} != "batch" ]]; then
  echo "--parallel is supported only with --mode batch" >&2
  exit 2
fi
if [[ -n ${workspace} && (${mode} != "kitty" || ${launch_type} != "os-window") ]]; then
  echo "--workspace requires --mode kitty --launch-type os-window" >&2
  exit 2
fi

if [[ $# -lt 1 ]]; then
  echo "no prompt files specified" >&2
  exit 2
fi

# Set only the model defaults required by current batch runners. Claude uses
# the configured CLI default unless --model is supplied.
if [[ -z ${model} ]]; then
  case "${agent}" in
  claude)
    ;;
  codex)
    model="gpt-5.6-terra"
    ;;
  gemini)
    model="gemini-2.0-flash"
    ;;
  grok)
    model="grok-4.5"
    ;;
  antigravity)
    model="gemini-3.1-pro-high"
    ;;
  *)
    echo "unknown agent: ${agent}" >&2
    exit 2
    ;;
  esac
fi

resolve_agent_bin() {
  case "${agent}" in
  claude) command -v claude-full >/dev/null 2>&1 || command -v claude >/dev/null 2>&1 ;;
  codex | gemini) command -v "${agent}" >/dev/null 2>&1 ;;
  grok) command -v grok-sinnix >/dev/null 2>&1 || command -v grok >/dev/null 2>&1 ;;
  antigravity) command -v agy-sinnix >/dev/null 2>&1 || command -v agy >/dev/null 2>&1 ;;
  *) return 1 ;;
  esac
}
if ! resolve_agent_bin; then
  echo "${agent} runtime not found on PATH" >&2
  exit 1
fi

mkdir -p "${output_dir}"

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
runner="${script_dir}/run_agent_prompt.sh"

if [[ ! -x ${runner} ]]; then
  echo "runner helper is not executable: ${runner}" >&2
  exit 1
fi

if [[ ${mode} == "kitty" ]]; then
  if ! command -v kitty >/dev/null 2>&1; then
    echo "kitty not found on PATH for --mode kitty" >&2
    exit 1
  fi
  if [[ -z ${KITTY_LISTEN_ON:-} ]]; then
    echo "KITTY_LISTEN_ON is empty; cannot use kitty remote control" >&2
    exit 1
  fi
  if [[ -n ${workspace} ]] && ! command -v sinnix-hypr-control >/dev/null 2>&1; then
    echo "sinnix-hypr-control not found; cannot route Kitty window to ${workspace}" >&2
    exit 1
  fi
fi

resolve_task_workdir() {
  local prompt_name="$1"
  if [[ -n ${per_task_workdir_base} ]]; then
    printf '%s/%s' "${per_task_workdir_base}" "${prompt_name}"
  else
    printf '%s' "${workdir}"
  fi
}

# Appends the runner invocation shared by batch and kitty launch, into the
# array named by $1 (nameref), for task $2 with its per-task file paths.
build_runner_cmd() {
  local -n out_cmd="$1"
  local prompt_name="$2" prompt_file="$3" log_file="$4" last_file="$5" json_file="$6" task_workdir="$7"

  # run_agent_prompt.sh requires worktree identity in exactly one of two
  # forms. This script has no separate "registered project" concept of its
  # own -- a direct launch is self-authorizing to whatever directory the
  # caller already trusted enough to pass as --workdir -- so:
  #
  #  - When task_workdir is itself a Git worktree root (the common case: a
  #    repo checkout or a linked worktree), register it against itself in
  #    the attested form. The runner still verifies it is a real,
  #    uncorrupted Git worktree with a consistent Git common directory
  #    before it runs anything.
  #  - Otherwise -- a non-Git directory (the documented --skip-git-repo-check
  #    use case) or a subdirectory of a Git checkout that is not itself a
  #    worktree root (the runner's attestation can only authorize a whole
  #    worktree, never a subdirectory of one) -- use --local-workdir, the
  #    runner's explicit non-attested opt-out for a caller-trusted directory.
  local canonical_workdir registered_project git_common_dir
  canonical_workdir="$(cd "${task_workdir}" && pwd -P)"
  registered_project="$(git -C "${canonical_workdir}" rev-parse --path-format=absolute --show-toplevel 2>/dev/null)" || registered_project=""
  if [[ -n ${registered_project} && ${registered_project} == "${canonical_workdir}" ]]; then
    git_common_dir="$(git -C "${registered_project}" rev-parse --path-format=absolute --git-common-dir 2>/dev/null)" || {
      echo "launch_agent_tabs.sh: ${prompt_name}: --workdir reports a Git toplevel but its common directory could not be resolved: ${task_workdir}" >&2
      return 1
    }
    out_cmd=(
      "${runner}"
      --agent "${agent}"
      --workdir "${task_workdir}"
      --registered-project "${registered_project}"
      --expected-git-common-dir "${git_common_dir}"
      --prompt-file "${prompt_file}"
      --log-file "${log_file}"
    )
  else
    out_cmd=(
      "${runner}"
      --agent "${agent}"
      --workdir "${task_workdir}"
      --local-workdir
      --prompt-file "${prompt_file}"
      --log-file "${log_file}"
    )
  fi
  if [[ -n ${job_prefix} ]]; then
    out_cmd+=(--job-id "${job_prefix}${prompt_name}" --work-item "${prompt_name}")
  fi

  if [[ -n ${json_file} ]]; then
    out_cmd+=(--json-file "${json_file}")
  fi
  if [[ -n ${last_file} ]]; then
    out_cmd+=(--last-file "${last_file}")
  fi
  if [[ -n ${model} ]]; then
    out_cmd+=(--model "${model}")
  fi
  if [[ -n ${reasoning_effort} ]]; then
    out_cmd+=(--reasoning-effort "${reasoning_effort}")
  fi
  if [[ -n ${schema_file} ]]; then
    out_cmd+=(--schema-file "${schema_file}")
  fi
  if [[ ${json_mode} -eq 1 ]]; then
    out_cmd+=(--json)
  fi
  if [[ ${skip_agents_render} -eq 1 ]]; then
    out_cmd+=(--skip-agents-render)
  fi
  if [[ ${ephemeral} -eq 1 ]]; then
    out_cmd+=(--ephemeral)
  fi
  if [[ ${claude_api_key_auth} -eq 1 ]]; then
    out_cmd+=(--claude-api-key-auth)
  fi
  if [[ -n ${codex_sandbox} ]]; then
    out_cmd+=(--sandbox "${codex_sandbox}")
  fi
  if [[ -n ${codex_home} ]]; then
    out_cmd+=(--codex-home "${codex_home}")
  fi
  if [[ ${codex_skip_git_check} -eq 1 ]]; then
    out_cmd+=(--skip-git-repo-check)
  fi
  if [[ -n ${max_retries} ]]; then
    out_cmd+=(--max-retries "${max_retries}")
  fi
}

run_batch_agent() {
  local prompt_name="$1"
  local prompt_file="${prompt_dir}/${prompt_name}.prompt"
  local log_file="${output_dir}/${prompt_name}.log"
  local last_file="${output_dir}/${prompt_name}.last.md"
  local json_file="${output_dir}/${prompt_name}.jsonl"
  local task_workdir
  task_workdir="$(resolve_task_workdir "${prompt_name}")"

  if [[ ! -f ${prompt_file} ]]; then
    echo "missing prompt: ${prompt_file}" >&2
    return 1
  fi
  if [[ ! -d ${task_workdir} ]]; then
    echo "missing workdir for ${prompt_name}: ${task_workdir}" >&2
    return 1
  fi

  local -a cmd
  build_runner_cmd cmd "${prompt_name}" "${prompt_file}" "${log_file}" "${last_file}" "${json_file}" "${task_workdir}"

  if [[ ${dry_run} -eq 1 ]]; then
    printf 'DRY-RUN (%s): ' "${prompt_name}"
    printf '%q ' "${cmd[@]}"
    echo
    return 0
  fi

  local ec=0
  if "${cmd[@]}"; then
    ec=0
  else
    ec=$?
  fi
  printf '%s\n' "${ec}" >"${output_dir}/${prompt_name}.exit"
  return "${ec}"
}

run_kitty_agent() {
  local prompt_name="$1"
  local prompt_file="${prompt_dir}/${prompt_name}.prompt"
  local log_file="${output_dir}/${prompt_name}.log"
  local last_file="${output_dir}/${prompt_name}.last.md"
  local json_file="${output_dir}/${prompt_name}.jsonl"
  local task_workdir
  task_workdir="$(resolve_task_workdir "${prompt_name}")"

  if [[ ! -f ${prompt_file} ]]; then
    echo "missing prompt: ${prompt_file}" >&2
    return 1
  fi
  if [[ ! -d ${task_workdir} ]]; then
    echo "missing workdir for ${prompt_name}: ${task_workdir}" >&2
    return 1
  fi

  local -a launch_cmd
  build_runner_cmd launch_cmd "${prompt_name}" "${prompt_file}" "${log_file}" "${last_file}" "${json_file}" "${task_workdir}"

  local window_title="agent-${prompt_name//[^A-Za-z0-9_.-]/-}"

  local -a exec_argv=("${launch_cmd[@]}")
  if [[ ${persist_windows} -eq 1 ]]; then
    local exit_file="${output_dir}/${prompt_name}.exit"
    local inner
    inner="$(printf '%q ' "${launch_cmd[@]}")"
    inner+='; ec=$?'
    inner+="; printf '%s\\n' \"\${ec}\" > $(printf '%q' "${exit_file}")"
    inner+="; printf '[%s finished exit=%s — window persists for inspection]\\n' $(printf '%q' "${prompt_name}") \"\${ec}\""
    inner+="; exec ${persist_shell} -i"
    exec_argv=("${persist_shell}" -lc "${inner}")
  fi

  if [[ ${dry_run} -eq 1 ]]; then
    printf 'DRY-RUN (%s): kitty @ launch --keep-focus --type=%s --title %q --tab-title %q --cwd %q -- ' "${prompt_name}" "${launch_type}" "${window_title}" "${prompt_name}" "${task_workdir}"
    printf '%q ' "${exec_argv[@]}"
    if [[ -n ${workspace} ]]; then
      printf '; move silently to workspace %q' "${workspace}"
    fi
    echo
    return 0
  fi

  kitty @ launch \
    --keep-focus \
    --type="${launch_type}" \
    --title "${window_title}" \
    --tab-title "${prompt_name}" \
    --cwd "${task_workdir}" \
    -- "${exec_argv[@]}"

  if [[ -n ${workspace} ]]; then
    local selector="title:^(${window_title})$"
    local moved=0
    for _ in {1..20}; do
      if sinnix-hypr-control dispatch movetoworkspacesilent "${workspace},${selector}" >/dev/null 2>&1; then
        moved=1
        break
      fi
      sleep 0.05
    done
    if [[ ${moved} -ne 1 ]]; then
      echo "warning: launched ${prompt_name} but could not route it to workspace ${workspace}" >&2
    fi
  fi
}

if [[ (-n ${codex_sandbox} || -n ${codex_home} || ${no_agents_md} -eq 1 || ${codex_skip_git_check} -eq 1) && ${agent} != "codex" ]]; then
  echo "--sandbox/--codex-home/--no-agents-md/--skip-git-repo-check require --agent codex" >&2
  exit 2
fi
if [[ ${no_agents_md} -eq 1 && -n ${codex_home} ]]; then
  echo "--no-agents-md and --codex-home are mutually exclusive (--no-agents-md manages its own CODEX_HOME)" >&2
  exit 2
fi
if [[ ${no_agents_md} -eq 1 ]]; then
  real_codex_home="${CODEX_HOME:-$HOME/.codex}"
  scratch_codex_home="${XDG_STATE_HOME:-$HOME/.local/state}/sinnix/agent-orchestration/codex-home-no-agents-md"
  if [[ ! -f ${scratch_codex_home}/config.toml || ${real_codex_home}/config.toml -nt ${scratch_codex_home}/config.toml ]]; then
    mkdir -p "${scratch_codex_home}"
    for f in auth.json config.toml models-v1.json; do
      [[ -f ${real_codex_home}/${f} ]] && cp -f "${real_codex_home}/${f}" "${scratch_codex_home}/${f}"
    done
    rm -f "${scratch_codex_home}/AGENTS.md"
    echo "launch_agent_tabs.sh: (re)provisioned no-AGENTS.md CODEX_HOME at ${scratch_codex_home}" >&2
  fi
  codex_home="${scratch_codex_home}"
fi

# Special handling for codex with spark model
if [[ ${model} == "gpt-5.3-codex-spark" && -z ${reasoning_effort} ]]; then
  reasoning_effort="xhigh"
fi
if [[ ${agent} == "codex" && -z ${reasoning_effort} ]]; then
  reasoning_effort="high"
fi
if [[ ${agent} == "grok" || ${agent} == "antigravity" ]] && [[ -z ${reasoning_effort} ]]; then
  reasoning_effort="high"
fi

batch_active=0
batch_failed=0
for prompt_name in "$@"; do
  # Remove .prompt extension if provided
  prompt_name="${prompt_name%.prompt}"

  if [[ ${mode} == "batch" ]]; then
    run_batch_agent "${prompt_name}" &
    batch_active=$((batch_active + 1))
    if [[ ${batch_active} -ge ${parallel} ]]; then
      if ! wait -n; then
        batch_failed=1
      fi
      batch_active=$((batch_active - 1))
    fi
  else
    run_kitty_agent "${prompt_name}"
    sleep 0.2
  fi
done

if [[ ${mode} == "batch" ]]; then
  while [[ ${batch_active} -gt 0 ]]; do
    if ! wait -n; then
      batch_failed=1
    fi
    batch_active=$((batch_active - 1))
  done
  exit "${batch_failed}"
fi
