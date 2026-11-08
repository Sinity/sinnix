# Noninteractive agent commands must not share the coordinator's memory.high.
# Re-enter the same shell with its original argv in a sibling scope before
# executing any command. Interactive shells and queued job lanes stay put.
# The tool scope is bound to the agent's own scope, so stopping the agent
# stops the commands it started instead of leaving them running unowned.
if [[ ! -o interactive && -r /proc/$$/cgroup &&
      "$(</proc/$$/cgroup)" == */agent-cli.slice/* &&
      -S ${XDG_RUNTIME_DIR:-/run/user/$UID}/systemd/private ]]; then
  () {
    local -a shell_argv bind
    shell_argv=("${(@0)$(</proc/$$/cmdline)}")
    local agent_scope=${${(s:/:)$(</proc/$$/cgroup)}[-1]}
    [[ $agent_scope == *.scope ]] && bind=(-p "BindsTo=$agent_scope" -p "After=$agent_scope")
    # /proc cmdline terminates its final argument with NUL.
    [[ ${shell_argv[-1]} == '' ]] && shell_argv[-1]=()
    # Rank above browser tabs (200-300) as a global OOM victim.
    print 800 >/proc/self/oom_score_adj 2>/dev/null
    exec /run/current-system/sw/bin/systemd-run --user --scope --quiet --collect \
      --expand-environment=no \
      --unit="agent-tool-$$" --slice=agent-tool.slice "${bind[@]}" -- "${shell_argv[@]}"
  }
fi
