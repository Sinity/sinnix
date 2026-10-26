# Noninteractive agent commands must not share the coordinator's memory.high.
# Re-enter the same shell with its original argv in a sibling scope before
# executing any command. Interactive shells and queued job lanes stay put.
if [[ ! -o interactive && -r /proc/$$/cgroup &&
      "$(</proc/$$/cgroup)" == */agent-cli.slice/* &&
      -S ${XDG_RUNTIME_DIR:-/run/user/$UID}/systemd/private ]]; then
  () {
    local -a shell_argv
    shell_argv=("${(@0)$(</proc/$$/cmdline)}")
    # /proc cmdline terminates its final argument with NUL.
    [[ ${shell_argv[-1]} == '' ]] && shell_argv[-1]=()
    exec /run/current-system/sw/bin/systemd-run --user --scope --quiet --collect \
      --expand-environment=no \
      --unit="agent-tool-$$" --slice=agent-tool.slice -- "${shell_argv[@]}"
  }
fi
