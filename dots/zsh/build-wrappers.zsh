# Build command wrappers - run builds in memory-limited cgroup
# These wrap cargo/make/ninja to run in builds.slice (shared 28G limit with nix-daemon)
#
# Works with nix shells: `command -v` finds the nix-provided command in PATH
#
# The systemd-run --scope creates a transient scope that:
# - Inherits to all child processes (rustc spawned by cargo, etc.)
# - Shares the parent builds.slice memory limit (28G total with nix-daemon)
# - Runs at low CPU/IO priority (doesn't block desktop)
#
# Polkit rule allows this without sudo (see modules/performance.nix)

# Wrapper function that runs command in builds.slice
_run_in_builds_slice() {
  local cmd="$1"
  shift

  # Find the real command path (works with nix shells)
  local real_cmd
  real_cmd=$(command -v "$cmd" 2>/dev/null)

  if [[ -z "$real_cmd" ]]; then
    echo "Error: $cmd not found in PATH" >&2
    return 127
  fi

  # Run in builds.slice with memory limit + low priority
  # --quiet suppresses systemd-run output, build output still shows
  systemd-run --scope \
    --slice=builds.slice \
    --property=CPUWeight=30 \
    --property=IOWeight=30 \
    --property=Nice=10 \
    --quiet \
    "$real_cmd" "$@"
}

# Wrap build commands (works with both global and nix-shell provided commands)
# Each wrapper checks if _run_in_builds_slice exists to handle partial sourcing
# (e.g., Claude Code shell snapshots may capture functions without dependencies)

cargo() {
  if (( $+functions[_run_in_builds_slice] )); then
    _run_in_builds_slice cargo "$@"
  else
    command cargo "$@"
  fi
}

make() {
  if (( $+functions[_run_in_builds_slice] )); then
    _run_in_builds_slice make "$@"
  else
    command make "$@"
  fi
}

ninja() {
  if (( $+functions[_run_in_builds_slice] )); then
    _run_in_builds_slice ninja "$@"
  else
    command ninja "$@"
  fi
}

cmake() {
  if (( $+functions[_run_in_builds_slice] )); then
    _run_in_builds_slice cmake "$@"
  else
    command cmake "$@"
  fi
}

meson() {
  if (( $+functions[_run_in_builds_slice] )); then
    _run_in_builds_slice meson "$@"
  else
    command meson "$@"
  fi
}

# Unwrapped versions (bypass the cgroup wrapper)
alias cargo-raw='command cargo'
alias make-raw='command make'
alias ninja-raw='command ninja'
alias cmake-raw='command cmake'
alias meson-raw='command meson'
