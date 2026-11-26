# Noninteractive agent tool commands must not share the coordinator's
# memory.high. Re-enter the same shell with its original argv outside the
# agent's unit before executing the command. Interactive shells and queued
# job lanes stay put.
#
# Only tool commands move: Claude Code's Bash commands, which begin by sourcing
# its shell snapshot, and Codex's, which run as login shells. Hooks and status
# lines also arrive as `zsh -c` from the agent's unit, but they run on every
# tool call and hold no meaningful memory; moving them would add a second
# shell start to every call.
#
# agent-tool-command places the shell in its agent's unit under
# agent-tool.slice and marks it with its PID, so a shell it already handled,
# moved or left in place, is not sent through again.
#
# This file is linked from the checkout, so it can be newer than the installed
# system. Without the installed command it uses one scope for this command,
# bound to the agent's own scope so stopping the agent stops the command.
if [[ ! -o interactive && -r /proc/$$/cgroup &&
      ${AGENT_TOOL_COMMAND_PID:-} != $$ &&
      ( -o login || $ZSH_EXECUTION_STRING == 'source '*/shell-snapshots/snapshot-* ) &&
      "$(</proc/$$/cgroup)" == */agent-cli.slice/* ]]; then
  () {
    local -a shell_argv bind
    shell_argv=("${(@0)$(</proc/$$/cmdline)}")
    # /proc cmdline terminates its final argument with NUL.
    [[ ${shell_argv[-1]} == '' ]] && shell_argv[-1]=()
    local place=/run/current-system/sw/bin/agent-tool-command
    [[ -x $place ]] && exec $place -- "${shell_argv[@]}"
    [[ -S ${XDG_RUNTIME_DIR:-/run/user/$UID}/systemd/private ]] || return
    local agent_scope=${${(s:/:)$(</proc/$$/cgroup)}[-1]}
    [[ $agent_scope == *.scope ]] && bind=(-p "BindsTo=$agent_scope" -p "After=$agent_scope")
    # Rank above browser tabs (200-300) as a global OOM victim.
    print 800 >/proc/self/oom_score_adj 2>/dev/null
    # A fixed description: without one systemd logs the whole command line,
    # heredocs included, to a journal that is kept, backed up and captured.
    exec /run/current-system/sw/bin/systemd-run --user --scope --quiet --collect \
      --expand-environment=no \
      --description="Agent tool command" \
      --unit="agent-tool-$$" --slice=agent-tool.slice "${bind[@]}" -- "${shell_argv[@]}"
  }
fi
