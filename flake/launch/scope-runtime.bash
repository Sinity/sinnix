# Runtime half of sinnix-scope. The policy half (slice, nice, ionice,
# systemd properties, env defaults, the set of legal class names) is rendered
# ahead of this text at evaluation time by flake/launch.nix, which is why
# nothing here reads /etc/sinnix/runtime-inventory.json or shells out to jq:
# by the time this runs, `apply_class_policy` already exists and already
# knows every class sinnix declares.
#
# What remains here is what genuinely cannot be known at evaluation time:
# argument parsing, the caller's cgroup, whether stdin is a terminal, the
# unit name (which encodes a timestamp and pid), and the supervisor that
# outlives a daemonizing child.

supervise_scope_command() {
  if [ "$#" -lt 2 ] || [ "$1" != "--" ]; then
    echo "sinnix-scope: invalid internal supervisor invocation" >&2
    exit 64
  fi
  shift

  local child_pid=""
  local command_status=0
  local cgroup_path=""
  local cgroup_procs=""
  local hierarchy controllers path pid signal
  local -a remaining_pids=()

  # shellcheck disable=SC2329  # invoked from the traps installed below
  forward_signal() {
    signal="$1"
    if [ -n "$child_pid" ]; then
      kill -s "$signal" "$child_pid" 2>/dev/null || true
    fi
  }

  collect_remaining_pids() {
    remaining_pids=()
    while IFS= read -r pid; do
      [[ $pid =~ ^[0-9]+$ ]] || continue
      [ "$pid" -gt 1 ] || continue
      [ "$pid" != "$BASHPID" ] || continue
      if kill -0 "$pid" 2>/dev/null; then
        remaining_pids+=("$pid")
      fi
    done <"$cgroup_procs"
  }

  terminate_remaining_pids() {
    collect_remaining_pids
    [ "${#remaining_pids[@]}" -gt 0 ] || return 0

    for pid in "${remaining_pids[@]}"; do
      kill -s TERM "$pid" 2>/dev/null || true
    done
    for _ in {1..50}; do
      sleep 0.1
      collect_remaining_pids
      [ "${#remaining_pids[@]}" -gt 0 ] || return 0
    done
    for pid in "${remaining_pids[@]}"; do
      kill -s KILL "$pid" 2>/dev/null || true
    done
  }

  trap 'forward_signal HUP' HUP
  trap 'forward_signal INT' INT
  trap 'forward_signal QUIT' QUIT
  trap 'forward_signal TERM' TERM

  "$@" &
  child_pid=$!
  set +e
  wait "$child_pid"
  command_status=$?
  set -e
  trap - HUP INT QUIT TERM

  if [ -n "${SINNIX_SCOPE_CGROUP_PROCS:-}" ]; then
    cgroup_procs="$SINNIX_SCOPE_CGROUP_PROCS"
  else
    while IFS=: read -r hierarchy controllers path; do
      if [ "$hierarchy" = 0 ] && [ -z "$controllers" ]; then
        cgroup_path="$path"
        break
      fi
    done </proc/self/cgroup
    cgroup_procs="/sys/fs/cgroup${cgroup_path}/cgroup.procs"
  fi

  if [ -n "$cgroup_path" ] || [ -n "${SINNIX_SCOPE_CGROUP_PROCS:-}" ]; then
    if [ -r "$cgroup_procs" ]; then
      terminate_remaining_pids
    else
      echo "sinnix-scope: cannot read scope membership at $cgroup_procs" >&2
    fi
  else
    echo "sinnix-scope: cannot resolve the current cgroup" >&2
  fi

  exit "$command_status"
}

if [ "${1:-}" = "--internal-supervise" ]; then
  shift
  supervise_scope_command "$@"
fi

if [ "$#" -lt 3 ]; then
  echo "usage: sinnix-scope <class> [--unit <name>] [--agent-property <Name=Value>] [--allow-nested-agent-scope] [--job-id <uuid>] [--project <id>] [--work-item <id>] -- <command> [args...]" >&2
  exit 64
fi

class="$1"
shift

unit_override=""
agent_properties=()
allow_nested_agent_scope=0

validate_agent_property() {
  local property="$1"
  local name="${property%%=*}"
  local value="${property#*=}"

  if [ "$name" = "$property" ] || [ -z "$value" ]; then
    echo "sinnix-scope: invalid agent property: $property" >&2
    exit 64
  fi

  case "$name" in
  MemoryHigh | MemoryMax)
    [[ $value =~ ^([0-9]+|[0-9]+[KMGTP]([iB])?|infinity)$ ]] || {
      echo "sinnix-scope: invalid $name value: $value" >&2
      exit 64
    }
    ;;
  CPUWeight | IOWeight)
    [[ $value =~ ^[0-9]+$ ]] && [ "$value" -ge 1 ] && [ "$value" -le 10000 ] || {
      echo "sinnix-scope: invalid $name value: $value" >&2
      exit 64
    }
    ;;
  RuntimeMaxSec)
    [[ $value =~ ^[0-9]+$ ]] && [ "$value" -ge 1 ] || {
      echo "sinnix-scope: invalid $name value: $value" >&2
      exit 64
    }
    ;;
  *)
    echo "sinnix-scope: unsupported agent property: $name" >&2
    exit 64
    ;;
  esac
}

# --job-id / --project / --work-item are correlation flags: callers such as
# sinnix-sinex-cache-prebuild pass them, and the values already reach the
# child through the SINNIX_JOB_ID / SINNIX_PROJECT_ID / SINNIX_WORK_ITEM
# environment a --scope launch inherits verbatim. They are accepted and
# consumed here so the launch line stays self-describing.
while [ "$#" -gt 0 ] && [ "$1" != "--" ]; do
  case "$1" in
  --unit)
    [ "$class" = "agent" ] || {
      echo "sinnix-scope: --unit is valid only for the agent class" >&2
      exit 64
    }
    unit_override="${2:?sinnix-scope: --unit requires a value}"
    [[ $unit_override =~ ^[A-Za-z0-9][A-Za-z0-9_.@-]*\.scope$ ]] || {
      echo "sinnix-scope: invalid scope unit: $unit_override" >&2
      exit 64
    }
    shift 2
    ;;
  --agent-property)
    [ "$class" = "agent" ] || {
      echo "sinnix-scope: --agent-property is valid only for the agent class" >&2
      exit 64
    }
    property="${2:?sinnix-scope: --agent-property requires a value}"
    validate_agent_property "$property"
    agent_properties+=("$property")
    shift 2
    ;;
  --allow-nested-agent-scope)
    [ "$class" = "agent" ] || {
      echo "sinnix-scope: --allow-nested-agent-scope is valid only for the agent class" >&2
      exit 64
    }
    allow_nested_agent_scope=1
    shift
    ;;
  --job-id)
    : "${2:?sinnix-scope: --job-id requires a value}"
    shift 2
    ;;
  --project)
    : "${2:?sinnix-scope: --project requires a value}"
    shift 2
    ;;
  --work-item)
    : "${2:?sinnix-scope: --work-item requires a value}"
    shift 2
    ;;
  *)
    echo "sinnix-scope: unknown option: $1" >&2
    exit 64
    ;;
  esac
done

if [ "$#" -lt 2 ] || [ "$1" != "--" ]; then
  echo "usage: sinnix-scope <class> [--unit <name>] [--agent-property <Name=Value>] [--job-id <uuid>] [--project <id>] [--work-item <id>] -- <command> [args...]" >&2
  exit 64
fi
shift

# Rendered above: sets slice / nice_level / ionice_class / ionice_priority /
# class_property_args / class_env_defaults, or rejects an unknown class.
apply_class_policy "$class"

scoped_command=("$@")
# Unit-name identity is taken from the command AS THE CALLER GAVE IT, before
# the nice/ionice/supervisor wrappers are prepended -- the identity segment
# exists for telemetry joins, and a headless launch that names itself after
# its own supervisor defeats that (found 2026-08-18, present since the
# segment was introduced).
identity_cmd0="${1:-}"
identity_cmd1="${2:-}"
property_args=("${class_property_args[@]}")
unscoped_background_xtask=0

command_base="$(basename -- "${1:-}")"
if [ "$command_base" = "xtask" ]; then
  for arg in "$@"; do
    if [ "$arg" = "--bg" ]; then
      unscoped_background_xtask=1
      break
    fi
  done
fi

for env_default in "${class_env_defaults[@]}"; do
  env_name="${env_default%%=*}"
  if [ "${!env_name+x}" != x ]; then
    export "${env_default?}"
  fi
done

# Explicit job limits are overrides, so append them after the class defaults.
# systemd-run applies the last occurrence when a property is specified twice.
for property in "${agent_properties[@]}"; do
  property_args+=("--property=$property")
done

if [ -n "$ionice_class" ] && command -v ionice >/dev/null 2>&1; then
  case "$ionice_class" in
  best-effort)
    scoped_command=(ionice -c 2 -n "${ionice_priority:-7}" -- "${scoped_command[@]}")
    ;;
  idle)
    scoped_command=(ionice -c 3 -- "${scoped_command[@]}")
    ;;
  esac
fi

if [ -n "$nice_level" ] && command -v nice >/dev/null 2>&1; then
  scoped_command=(nice -n "$nice_level" "${scoped_command[@]}")
fi

if [ "$unscoped_background_xtask" = 1 ]; then
  # `xtask ... --bg` intentionally forks a long-lived child and returns. A
  # systemd-run scope is the wrong ownership boundary for that shape: when the
  # launcher exits, the transient scope stops and kills the background job.
  # Keep the nice/ionice/env policy above, but leave lifecycle ownership to
  # xtask's job table and reaper.
  exec "${scoped_command[@]}"
fi

if grep -q "/$slice" /proc/self/cgroup 2>/dev/null; then
  if [ "$allow_nested_agent_scope" = 1 ]; then
    if [ -z "$unit_override" ]; then
      echo "sinnix-scope: nested agent scope requires --unit" >&2
      exit 64
    fi
    if ! command -v systemd-run >/dev/null 2>&1 || [ -z "${XDG_RUNTIME_DIR:-}" ]; then
      echo "sinnix-scope: nested agent scope requires the user systemd manager" >&2
      exit 64
    fi
    exec systemd-run \
      --user \
      --scope \
      --quiet \
      --collect \
      --same-dir \
      --unit="$unit_override" \
      --slice="$slice" \
      "${property_args[@]}" \
      -- env \
      SINNIX_AGENT_SCOPED=1 \
      SINNIX_AGENT_SCOPE_UNIT="$unit_override" \
      "${scoped_command[@]}"
  fi
  if [ -n "$unit_override" ] || [ "${#agent_properties[@]}" -gt 0 ]; then
    echo "sinnix-scope: cannot apply a job scope or overrides from an existing scope" >&2
    exit 64
  fi
  exec "${scoped_command[@]}"
fi

if ! command -v systemd-run >/dev/null 2>&1; then
  exec "${scoped_command[@]}"
fi

# `systemd-run --scope` moves the launched process into a cgroup scope; it
# does NOT sandbox the environment the way a transient --service launch would.
# The child inherits the calling shell's full environment regardless of any
# allowlist, so there is no env boundary to enforce here. If a real env
# boundary is ever wanted, switch these launches to service mode (drop
# --scope) and build a complete, deliberately-maintained allowlist — don't
# resurrect a partial one under --scope.
#
# A scope remains active while any descendant remains in its cgroup; it has no
# service-style MainPID whose exit ends the unit. Run the requested command
# under a small supervisor so a daemonized database, MCP server, or test worker
# cannot keep a completed launcher scope alive indefinitely. Intentional
# background xtask jobs bypass the scope above and retain their own lifecycle.
#
# Interactive launches (a real controlling terminal on stdin) MUST skip the
# supervisor: `supervise_scope_command` backgrounds the target with `"$@" &`,
# and bash — running non-interactively here, no job control (`-m`) — redirects
# a backgrounded command's stdin from /dev/null per POSIX ("If job control is
# not in effect... asynchronous commands... have standard input redirected
# from /dev/null"), so every interactive agent CLI routed through the scope
# sees "stdin is not a terminal". The orphan-cleanup problem the supervisor
# fixes is a background/headless failure mode anyway; an interactive session
# already gets normal terminal signal delivery (SIGHUP on close, Ctrl-C)
# across the whole foreground process group.
if [ -t 0 ]; then
  :
else
  scoped_command=("$0" --internal-supervise -- "${scoped_command[@]}")
fi

# cgroup v2 memory.peak is a cumulative watermark since cgroup
# creation, never reset by the kernel -- for a long-lived slice like
# nix-build.slice that shares one cgroup across every job ever run in it,
# the column reports the slice's all-time high rather than any single job's
# peak, which makes per-job memory analysis over telemetry.sqlite's
# cgroup_memory_sample table useless for that slice. Resetting it here, at
# the moment a new job acquires the slice, turns the already-collected
# column into a true per-job peak. Best-effort: a transient permission or
# path miss must never block the job itself from launching.
reset_slice_memory_peak() {
  local peak_path
  for peak_path in \
    "/sys/fs/cgroup/nix.slice/$slice/memory.peak" \
    "/sys/fs/cgroup/user.slice/user-$(id -u).slice/user@$(id -u).service/nix.slice/$slice/memory.peak"; do
    [ -w "$peak_path" ] || continue
    echo 0 >"$peak_path" 2>/dev/null || true
  done
}
if [ "$slice" = "nix-build.slice" ]; then
  reset_slice_memory_peak
fi

# Job identity goes in the unit name because telemetry.sqlite joins
# process_memory_sample/cgroup_memory_sample to the owning systemd unit by
# name -- encoding the real command here is what makes that join carry job
# identity instead of just "nix-build" for every job. Sanitized and
# length-capped: unit names have a real character/length ceiling and the
# command can be arbitrarily long.
job_identity="$(basename -- "${identity_cmd0:-$command_base}")"
if [ -n "$identity_cmd1" ]; then
  job_identity="${job_identity}-${identity_cmd1}"
fi
job_identity="$(printf '%s' "$job_identity" | tr -c 'A-Za-z0-9_.-' '-' | cut -c1-40)"

if [ "${EUID:-$(id -u)}" -eq 0 ]; then
  unit="${unit_override:-sinnix-${class}-${job_identity}-$(date +%s%N)-$$}"
  exec systemd-run \
    --scope \
    --quiet \
    --collect \
    --same-dir \
    --unit="$unit" \
    --slice="$slice" \
    "${property_args[@]}" \
    -- "${scoped_command[@]}"
fi

if [ -n "${XDG_RUNTIME_DIR:-}" ]; then
  unit="${unit_override:-sinnix-${class}-${job_identity}-$(date +%s%N)-$$}"
  exec systemd-run \
    --user \
    --scope \
    --quiet \
    --collect \
    --same-dir \
    --unit="$unit" \
    --slice="$slice" \
    "${property_args[@]}" \
    -- "${scoped_command[@]}"
fi

exec "${scoped_command[@]}"
