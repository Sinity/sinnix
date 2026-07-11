{
  inputs,
  pkgs,
  system,
}:
let
  inherit (pkgs) lib;
  scriptPkgs = (import ./scripts.nix { inherit inputs pkgs; }).packageSet;
  rebuildServicePath = lib.makeBinPath [
    pkgs.coreutils
    pkgs.findutils
    pkgs.gnugrep
    pkgs.gnused
    pkgs.systemd
    pkgs.util-linux
  ];
  resolveFlakeDir = ''
    _flake_dir="''${SINNIX_FLAKE_DIR:-''${NH_FLAKE:-''${FLAKE:-${inputs.self}}}}"
  '';
  loadCheckTargets = outputName: ''
    mapfile -t ${outputName}_targets < <(
      ${pkgs.nix}/bin/nix eval "$_flake_dir#${outputName}.${system}" \
        --apply builtins.attrNames \
        --json \
        | ${pkgs.jq}/bin/jq -r '.[] | "${outputName}.${system}.\(.)"'
    )
  '';
  avoidRepoCwdForActivation = ''
    # nixos-rebuild-ng can trip over a git checkout cwd during activation.
    # Keep the resolved flake path, then leave the repository before invoking it.
    _invoke_flake_dir="$_flake_dir"
    cd "''${SUDO_HOME:-''${HOME:-/root}}"
  '';
  localInputOverrideArgs = ''
    nix_override_args=()
    append_override_arg() {
      nix_override_args+=(
        --override-input "$1" "$2"
        --no-write-lock-file
      )
    }
    if [ -n "''${SINNIX_SINEX_OVERRIDE:-}" ]; then
      append_override_arg sinex "$SINNIX_SINEX_OVERRIDE"
    fi
    if [ -n "''${SINNIX_POLYLOGUE_OVERRIDE:-}" ]; then
      append_override_arg polylogue "$SINNIX_POLYLOGUE_OVERRIDE"
    fi
    if [ -n "''${SINNIX_LYNCHPIN_OVERRIDE:-}" ]; then
      append_override_arg lynchpin "$SINNIX_LYNCHPIN_OVERRIDE"
    fi
    # --impure: modules/secrets.nix reads agenix secrets from
    # /realm/data/secrets/sinnix, outside the flake source (moved out of git
    # 2026-07 -- see that module). Pure flake evaluation cannot see paths
    # outside the flake's own store copy at all (builtins.pathExists/readDir
    # on such a path silently returns false/empty rather than erroring, so
    # this failure mode is silent: a system with zero secrets configured,
    # not a build error). This is a real host-local-data dependency, not a
    # purity shortcut being taken for convenience.
    nh_extra_args=(-- --impure)
    if [ "''${#nix_override_args[@]}" -gt 0 ]; then
      nh_extra_args+=("''${nix_override_args[@]}")
    fi
  '';
  rebuildPressurePreflight = name: ''
    rebuild_pressure_preflight() {
      if [ "''${SINNIX_REBUILD_SKIP_PRESSURE_PREFLIGHT:-0}" = "1" ]; then
        return 0
      fi

      _mem_total_kb="$(${pkgs.gawk}/bin/awk '/^MemTotal:/ {print $2}' /proc/meminfo)"
      _mem_avail_kb="$(${pkgs.gawk}/bin/awk '/^MemAvailable:/ {print $2}' /proc/meminfo)"
      _min_mem_kb="''${SINNIX_REBUILD_MIN_MEM_AVAILABLE_KB:-8388608}"

      if [ "''${_mem_avail_kb:-0}" -lt "$_min_mem_kb" ]; then
        {
          echo "sinnix ${name}: refusing to start host rebuild with low reclaim-aware memory headroom"
          echo "  MemAvailable=$(( _mem_avail_kb / 1024 )) MiB; required=$(( _min_mem_kb / 1024 )) MiB"
          echo "  Override for a deliberate risky run: SINNIX_REBUILD_SKIP_PRESSURE_PREFLIGHT=1 nix run .#${name}"
          echo "  Top RSS processes:"
          ${pkgs.procps}/bin/ps -eo pid,rss,comm,args --sort=-rss | ${pkgs.coreutils}/bin/head -8
        } >&2
        exit 75
      fi
    }
  '';
  rebuildDefaultArgs = ''
    rebuild_jobs="''${SINNIX_REBUILD_MAX_JOBS:-1}"
    rebuild_cores="''${SINNIX_REBUILD_CORES:-16}"
  '';
  # Single source of truth for rebuild concurrency + resource containment, so
  # `nix run .#switch` (this file's appCommands) and the devshell `switch`
  # binary (flake/dev-shell.nix's mkNhCommand) can't drift apart: both must
  # serialize on the same lock and run under the same idle scheduling, or one
  # path becomes an escape hatch around the other's containment.
  rebuildLock = name: ''
    exec 9>/tmp/sinnix-switch.lock
    if ! ${pkgs.util-linux}/bin/flock --nonblock 9; then
      echo "sinnix ${name}: another rebuild is already running — aborting to prevent concurrent builds" >&2
      exit 1
    fi
  '';
  # NOT a ''...'' block: this is spliced mid-line into a backslash-continued
  # systemd-run invocation at each call site. A ''...'' string's own trailing
  # newline plus the call site's template newline produced a blank line in
  # the middle of the continued command, which bash treats as a broken
  # continuation — systemd-run silently got zero command args (2026-07-06
  # incident). concatStringsSep has no trailing separator, so this can't
  # reproduce that regardless of how it's indented at the call site.
  rebuildContainmentFlags =
    lib.concatStringsSep " \\\n    " [
      ''--setenv=NIX_CONFIG="eval-cache = false"''
      "--setenv=SINNIX_REBUILD_ACTIVE=1"
      "--slice=nix-build.slice"
      "-p CPUSchedulingPolicy=idle"
      "-p IOSchedulingClass=idle"
    ]
    + " \\";
  # sinex CI stopped auto-pushing package builds to sinity.cachix.org when
  # hosted Actions went manual-only (sinex#883 "disable automatic paid
  # Actions"), so the desktop now compiles the sinex workspace locally on
  # every input bump — a single sinexd rustc peaks at 8-11.5 GiB RSS
  # (2026-07-09: 17 earlyoom kills before one attempt fit). Publish the
  # freshly activated sinex closure back to the cache after a successful
  # switch so sinnix-ethereal deploys, reinstalls, and post-GC rebuilds
  # substitute instead of repeating that build (sinnix-iln). Best-effort:
  # needs the operator cachix auth token (~/.config/cachix); the push runs
  # as a detached user unit in background.slice so the rebuild command
  # returns without waiting on uploads, and any failure is visible via
  # `journalctl --user` rather than failing the switch.
  sinexCachePush = ''
    if [ "$_rebuild_status" -eq 0 ]; then
      _sinex_pkg_paths="$(${pkgs.nix}/bin/nix path-info -r /run/current-system 2>/dev/null | ${pkgs.gnugrep}/bin/grep -E -- '-sinex-[0-9][^/]*$' || true)"
      if [ -n "$_sinex_pkg_paths" ]; then
        echo "sinnix switch: publishing sinex package closure to sinity.cachix.org in the background"
        # shellcheck disable=SC2086
        ${pkgs.systemd}/bin/systemd-run --user --quiet --collect \
          --slice=background.slice \
          ${pkgs.cachix}/bin/cachix push sinity $_sinex_pkg_paths || true
      fi
    fi
  '';
  switchFallback = ''
    if [ "$_rebuild_status" -ne 0 ] && [ "$_rebuild_status" -ne 130 ]; then
      echo "sinnix switch: nh failed with status $_rebuild_status; trying exact toplevel activation fallback" >&2
      _toplevel_drv="$(
        SINNIX_REBUILD_ACTIVE=1 NIX_CONFIG="eval-cache = false" \
          ${pkgs.nix}/bin/nix eval \
            "$_invoke_flake_dir#nixosConfigurations.sinnix-prime.config.system.build.toplevel.drvPath" \
            --raw \
            --impure \
            "''${nix_override_args[@]}"
      )"
      _toplevel_out="$(
        SINNIX_REBUILD_ACTIVE=1 NIX_CONFIG="eval-cache = false" \
          ${pkgs.nix}/bin/nix-store -r "$_toplevel_drv"
      )"
      # Register the generation BEFORE activating: without the profile entry,
      # switch-to-configuration boot has no generation to point the bootloader
      # at, activation succeeds only in memory, and the next reboot silently
      # resurrects the previous generation (2026-07-11 incident; see
      # flake/dev-shell.nix twin comment).
      /run/wrappers/bin/sudo ${pkgs.nix}/bin/nix-env \
        --profile /nix/var/nix/profiles/system --set "$_toplevel_out"
      _rebuild_status=0
      /run/wrappers/bin/sudo "$_toplevel_out/bin/switch-to-configuration" switch || _rebuild_status=$?
      # switch-to-configuration exits non-zero whenever ANY unit fails to
      # (re)start, even one wholly unrelated to this config change
      # (sinnix-ihi, 2026-07-08: a pre-existing nvidia-container-toolkit-
      # cdi-generator failure silently blocked profile/bootloader
      # registration for 4+ days -- every switch looked successful but
      # never advanced the boot generation). Registering the built
      # generation as the persistent boot default is orthogonal to
      # whether every service started cleanly, so always do it as a
      # separate step -- but keep the real "switch" exit status (unless
      # this step itself fails worse) so a genuine regression still
      # surfaces instead of being silently masked.
      _boot_status=0
      /run/wrappers/bin/sudo "$_toplevel_out/bin/switch-to-configuration" boot || _boot_status=$?
      if [ "$_boot_status" -ne 0 ]; then
        _rebuild_status="$_boot_status"
      fi
    fi
  '';
  hostSmokeTerminalScript = ''
    session="sinnix-host-smoke-$$"
    artifact_dir="''${SINNIX_HOST_SMOKE_ARTIFACT_DIR:-}"
    cleanup_artifacts=0
    if [ -n "$artifact_dir" ]; then
      mkdir -p "$artifact_dir"
      transcript="$artifact_dir/transcript.log"
    else
      artifact_dir="$(mktemp -d -t sinnix-host-smoke-terminal.XXXXXX)"
      transcript="$artifact_dir/transcript.log"
      cleanup_artifacts=1
    fi

    cleanup() {
      ${pkgs.tmux}/bin/tmux kill-session -t "$session" >/dev/null 2>&1 || true
      if [ "$cleanup_artifacts" -eq 1 ]; then
        rm -f "$transcript"
        rm -f "$artifact_dir/summary.txt"
        rmdir "$artifact_dir" >/dev/null 2>&1 || true
      fi
    }
    trap cleanup EXIT

    if ! command -v ${pkgs.tmux}/bin/tmux >/dev/null 2>&1; then
      echo "tmux is required for host-smoke-terminal"
      exit 1
    fi

    ${pkgs.tmux}/bin/tmux new-session -d -s "$session" "env ZDOTDIR=\$HOME HOME=\$HOME ${pkgs.zsh}/bin/zsh -i"

    wait_for() {
      pattern="$1"
      timeout_secs="$2"
      start="$(${pkgs.coreutils}/bin/date +%s)"
      while true; do
        ${pkgs.tmux}/bin/tmux capture-pane -pt "$session" > "$transcript"
        if ${pkgs.gnugrep}/bin/grep -qE "$pattern" "$transcript"; then
          return 0
        fi

        now="$(${pkgs.coreutils}/bin/date +%s)"
        if [ $((now - start)) -ge "$timeout_secs" ]; then
          echo "Timed out waiting for pattern: $pattern" >&2
          cat "$transcript" >&2
          exit 1
        fi

        ${pkgs.coreutils}/bin/sleep 0.2
      done
    }

    ${pkgs.tmux}/bin/tmux send-keys -t "$session" 'print READY' Enter
    wait_for 'READY' 10

    ${pkgs.tmux}/bin/tmux send-keys -t "$session" ':env' Enter
    wait_for 'TOOL CONFIGURATION' 10
    wait_for 'debug requests' 10

    printf 'terminal smoke ok\n' > "$artifact_dir/summary.txt"
    echo "Host terminal smoke passed."
    cat "$transcript"
  '';
  hostSmokeServicesScript = ''
    artifact_dir="''${SINNIX_HOST_SMOKE_ARTIFACT_DIR:-}"
    cleanup_artifacts=0
    if [ -n "$artifact_dir" ]; then
      mkdir -p "$artifact_dir"
    else
      artifact_dir="$(mktemp -d -t sinnix-host-smoke-services.XXXXXX)"
      cleanup_artifacts=1
    fi
    headers_file="$artifact_dir/transmission.headers"
    body_file="$artifact_dir/transmission.body"

    cleanup() {
      if [ "$cleanup_artifacts" -eq 1 ]; then
        rm -f "$headers_file" "$body_file" "$artifact_dir/summary.txt"
        rmdir "$artifact_dir" >/dev/null 2>&1 || true
      fi
    }
    trap cleanup EXIT

    need_active() {
      unit="$1"
      if [ "$(${pkgs.systemd}/bin/systemctl is-active "$unit")" != "active" ]; then
        echo "$unit is not active" >&2
        exit 1
      fi
    }

    need_active below.service
    need_active machine-telemetry.service

    telemetry_db="/realm/data/captures/machine/telemetry.sqlite"
    [ -s "$telemetry_db" ]

    now="$(${pkgs.coreutils}/bin/date +%s)"
    latest_sample="$(${pkgs.sqlite}/bin/sqlite3 "$telemetry_db" "SELECT COALESCE(MAX(strftime('%s', observed_at)), 0) FROM metric_sample;")"
    if [ $((now - latest_sample)) -gt 120 ]; then
      echo "machine telemetry output is stale: $telemetry_db" >&2
      exit 1
    fi

    ${pkgs.findutils}/bin/find /realm/data/captures/machine/below/store -type f | ${pkgs.gnugrep}/bin/grep -q .

    session_id="inactive"
    if [ "$(${pkgs.systemd}/bin/systemctl is-active transmission.service)" = "active" ]; then
      ${pkgs.curl}/bin/curl -sS -D "$headers_file" -o "$body_file" \
        http://127.0.0.1:9091/transmission/rpc || true
      ${pkgs.gnugrep}/bin/grep -q '409 Conflict' "$headers_file"
      session_id="$(${pkgs.gawk}/bin/awk -F': ' '/X-Transmission-Session-Id/ {print $2}' "$headers_file" | ${pkgs.coreutils}/bin/tr -d '\r')"
      [ -n "$session_id" ]
    fi

    printf 'services smoke ok\nsession_id=%s\n' "$session_id" > "$artifact_dir/summary.txt"
    echo "Host service smoke passed."
  '';
  hostSmokeCliScript = ''
    artifact_dir="''${SINNIX_HOST_SMOKE_ARTIFACT_DIR:-}"
    cleanup_artifacts=0
    if [ -n "$artifact_dir" ]; then
      mkdir -p "$artifact_dir"
    else
      artifact_dir="$(mktemp -d -t sinnix-host-smoke-cli.XXXXXX)"
      cleanup_artifacts=1
    fi

    cleanup() {
      if [ "$cleanup_artifacts" -eq 1 ]; then
        rm -f \
          "$artifact_dir/polylogue-help.txt" \
          "$artifact_dir/summary.txt"
        rmdir "$artifact_dir" >/dev/null 2>&1 || true
      fi
    }
    trap cleanup EXIT

    polylogue --help > "$artifact_dir/polylogue-help.txt"

    printf 'cli smoke ok\n' > "$artifact_dir/summary.txt"
    echo "Host CLI smoke passed."
  '';
  hostSmokeAllScript = ''
    ${resolveFlakeDir}
    artifact_root="''${SINNIX_HOST_SMOKE_ROOT:-/realm/data/captures/host-smoke}"
    run_id="$(${pkgs.coreutils}/bin/date -u +%Y%m%dT%H%M%SZ)-$$"
    run_dir="$artifact_root/$run_id"
    mkdir -p "$run_dir"

    (
      export SINNIX_HOST_SMOKE_ARTIFACT_DIR="$run_dir/terminal"
      ${hostSmokeTerminalScript}
    )

    (
      export SINNIX_HOST_SMOKE_ARTIFACT_DIR="$run_dir/services"
      ${hostSmokeServicesScript}
    )

    (
      export SINNIX_HOST_SMOKE_ARTIFACT_DIR="$run_dir/cli"
      ${hostSmokeCliScript}
    )

    cat > "$run_dir/summary.json" <<EOF
    {
      "run_id": "$run_id",
      "flake_dir": "$_flake_dir",
      "artifacts": {
        "terminal": "$run_dir/terminal",
        "services": "$run_dir/services",
        "cli": "$run_dir/cli"
      }
    }
    EOF

    echo "Host smoke suite passed."
    echo "Artifacts: $run_dir"
  '';
in
{
  inherit
    rebuildLock
    rebuildContainmentFlags
    rebuildDefaultArgs
    rebuildServicePath
    localInputOverrideArgs
    sinexCachePush
    ;

  appCommands = {
    lint = {
      description = "Lint Nix and shell files without modifying sources";
      script = ''
        ${resolveFlakeDir}
        cd "$_flake_dir"
        echo "Running deadnix..."
        ${pkgs.deadnix}/bin/deadnix --fail --no-lambda-arg --no-lambda-pattern-names .
        echo "Running statix..."
        ${pkgs.statix}/bin/statix check

        echo "Running shellcheck on packaged/runtime scripts..."
        shellcheck_targets="$(${pkgs.ripgrep}/bin/rg -Il '^#!.*\\b(bash|sh|zsh)\\b' scripts || true)"
        if [ -n "$shellcheck_targets" ]; then
          while IFS= read -r target; do
            [ -n "$target" ] && ${pkgs.shellcheck}/bin/shellcheck "$target"
          done <<<"$shellcheck_targets"
        fi

        echo "Linting complete!"
      '';
    };

    check-heavy = {
      description = "Run heavy non-default checks sequentially to keep evaluation memory bounded";
      script = ''
        ${resolveFlakeDir}
        cd "$_flake_dir"

        ${loadCheckTargets "heavyChecks"}

        for target in "''${heavyChecks_targets[@]}"; do
          echo "Running heavy check: $target"
          ${scriptPkgs.nix-safe}/bin/nix-safe build "$_flake_dir#$target"
        done

        echo "Heavy check suite complete."
      '';
    };

    check-all = {
      description = "Run the default semantic checks, then the heavy non-default suite sequentially";
      script = ''
        ${resolveFlakeDir}
        cd "$_flake_dir"

        echo "Running default semantic checks..."
        ${loadCheckTargets "checks"}

        for target in "''${checks_targets[@]}"; do
          echo "Running default check: $target"
          ${scriptPkgs.nix-safe}/bin/nix-safe build "$_flake_dir#$target"
        done

        echo "Running heavy checks..."
        ${loadCheckTargets "heavyChecks"}
        for target in "''${heavyChecks_targets[@]}"; do
          echo "Running heavy check: $target"
          ${scriptPkgs.nix-safe}/bin/nix-safe build "$_flake_dir#$target"
        done

        echo "Full non-host semantic check suite complete."
      '';
    };

    test-vm = {
      description = "Build a QEMU VM from current configuration and launch it (nixos-rebuild build-vm)";
      script = ''
        ${resolveFlakeDir}
        ${rebuildLock "test-vm"}
        ${localInputOverrideArgs}
        ${rebuildDefaultArgs}
        sudo ${pkgs.systemd}/bin/systemd-run \
          --quiet \
          --collect \
          --pipe \
          --service-type=exec \
          --wait \
          --setenv=PATH="${rebuildServicePath}:$PATH" \
          ${rebuildContainmentFlags}
          ${pkgs.nixos-rebuild}/bin/nixos-rebuild build-vm --flake "$_flake_dir#sinnix-prime" \
          --max-jobs "$rebuild_jobs" \
          --cores "$rebuild_cores" \
          --impure \
          "''${nix_override_args[@]}"
        exec ./result/bin/run-sinnix-prime-vm
      '';
    };

    test-system = {
      description = "Test configuration without applying it to the system (nh os test)";
      script = ''
        ${resolveFlakeDir}
        ${rebuildLock "test-system"}
        ${avoidRepoCwdForActivation}
        ${localInputOverrideArgs}
        ${rebuildDefaultArgs}
        ${pkgs.systemd}/bin/systemd-run \
          --user \
          --quiet --collect --pipe --service-type=exec --wait \
          --setenv=PATH="${rebuildServicePath}:$PATH" \
          ${rebuildContainmentFlags}
          ${pkgs.coreutils}/bin/env -u FLAKE NH_FLAKE="$_invoke_flake_dir" \
            ${pkgs.nh}/bin/nh os test \
            "''${_invoke_flake_dir}#sinnix-prime" \
            --no-nom \
            --max-jobs "$rebuild_jobs" \
            --cores "$rebuild_cores" \
            "''${nh_extra_args[@]}"
      '';
    };

    boot = {
      description = "Build + set boot default, activate on next reboot (nh os boot)";
      script = ''
        ${resolveFlakeDir}
        ${rebuildLock "boot"}
        ${avoidRepoCwdForActivation}
        ${localInputOverrideArgs}
        ${rebuildDefaultArgs}
        ${rebuildPressurePreflight "boot"}
        rebuild_pressure_preflight
        _rebuild_status=0
        ${pkgs.systemd}/bin/systemd-run \
          --user \
          --quiet --collect --pipe --service-type=exec --wait \
          --setenv=PATH="${rebuildServicePath}:$PATH" \
          ${rebuildContainmentFlags}
          ${pkgs.coreutils}/bin/env -u FLAKE NH_FLAKE="$_invoke_flake_dir" \
            ${pkgs.nh}/bin/nh os boot \
            "''${_invoke_flake_dir}#sinnix-prime" \
            --no-nom \
            --max-jobs "$rebuild_jobs" \
            --cores "$rebuild_cores" \
            "''${nh_extra_args[@]}" || _rebuild_status=$?
        exit "$_rebuild_status"
      '';
    };

    switch = {
      description = "Apply configuration changes to the system (nh os switch)";
      script = ''
        ${resolveFlakeDir}
        ${rebuildLock "switch"}
        ${avoidRepoCwdForActivation}
        ${localInputOverrideArgs}
        ${rebuildDefaultArgs}
        ${rebuildPressurePreflight "switch"}
        rebuild_pressure_preflight
        _rebuild_status=0
        ${pkgs.systemd}/bin/systemd-run \
          --user \
          --quiet --collect --pipe --service-type=exec --wait \
          --setenv=PATH="${rebuildServicePath}:$PATH" \
          ${rebuildContainmentFlags}
          ${pkgs.coreutils}/bin/env -u FLAKE NH_FLAKE="$_invoke_flake_dir" \
            ${pkgs.nh}/bin/nh os switch \
            "''${_invoke_flake_dir}#sinnix-prime" \
            --no-nom \
            --max-jobs "$rebuild_jobs" \
            --cores "$rebuild_cores" \
            "''${nh_extra_args[@]}" || _rebuild_status=$?
        ${switchFallback}
        ${sinexCachePush}
        exit "$_rebuild_status"
      '';
    };

    clean = {
      description = "Garbage collect + optimise nix store (nh clean all)";
      script = ''
        if [ "$(id -u)" -ne 0 ]; then
          echo "Error: This command must be run as root (use 'sudo nix run .#clean')"
          exit 1
        fi
        exec ${pkgs.nh}/bin/nh clean all
      '';
    };

    agenix = {
      description = "Manage encrypted secrets with agenix";
      script = ''
        cd /realm/data/secrets/sinnix && exec ${inputs.agenix.packages.${system}.default}/bin/agenix "$@"
      '';
    };

    host-smoke-terminal = {
      description = "Run an opt-in tmux-driven host smoke probe for interactive terminal integrations";
      script = hostSmokeTerminalScript;
    };

    host-smoke-services = {
      description = "Run an opt-in live host smoke probe for long-running service surfaces";
      script = hostSmokeServicesScript;
    };

    host-smoke-all = {
      description = "Run the full opt-in host smoke suite and persist terminal/service/CLI artifacts";
      script = hostSmokeAllScript;
    };
  };

  # Category order for display grouping
  categoryOrder = [
    "Core"
    "Validate"
    "Maintain"
    "Smoke"
  ];

  commandDocs = [
    {
      name = "check";
      category = "Core";
      description = "Validate flake outputs and config assertion tests";
    }
    {
      name = "format";
      category = "Core";
      description = "Format via treefmt";
    }
    {
      name = "switch";
      category = "Core";
      description = "Apply host config (nh os switch)";
    }
    {
      name = "boot";
      category = "Core";
      description = "Build + set boot default — safer, reboot to activate (nh os boot)";
    }
    {
      name = "test-system";
      category = "Core";
      description = "Test host config without persisting (nh os test)";
    }
    {
      name = "test-vm";
      category = "Core";
      description = "Build + launch QEMU VM for smoke-testing (nixos-rebuild build-vm)";
    }
    {
      name = "lint";
      category = "Validate";
      description = "Run deadnix/statix/shellcheck";
    }
    {
      name = "check-all";
      category = "Validate";
      description = "Default + heavy semantic check tiers";
    }
    {
      name = "update";
      category = "Maintain";
      description = "Update flake inputs";
    }
    {
      name = "clean";
      category = "Maintain";
      description = "Garbage collect + optimise store (nh clean all)";
    }
    {
      name = "agenix";
      category = "Maintain";
      description = "Manage encrypted secrets";
    }
    {
      name = "smoke";
      category = "Smoke";
      description = "Host smoke suite (smoke [terminal|services])";
    }
  ];
}
