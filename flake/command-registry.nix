{
  inputs,
  pkgs,
  system,
}:
let
  lib = pkgs.lib;
  scriptPkgs = (import ./scripts.nix { inherit inputs pkgs; }).packageSet;
  checkTiers = import ./check-tiers.nix { inherit lib; };
  rebuildServicePath = lib.makeBinPath [
    pkgs.coreutils
    pkgs.findutils
    pkgs.gnugrep
    pkgs.gnused
    pkgs.systemd
    pkgs.util-linux
  ];
  defaultCheckNames = checkTiers.defaultCheckNames;
  heavyCheckNames =
    map (name: "nixos-${name}") checkTiers.heavySpecNames
    ++ checkTiers.runtimeCheckNames
    ++ lib.optionals pkgs.stdenv.hostPlatform.isLinux checkTiers.vmCheckNames
    ++ lib.optionals (system == "x86_64-linux") checkTiers.hostBuildCheckNames;
  resolveFlakeDir = ''
    _flake_dir="''${SINNIX_FLAKE_DIR:-''${NH_FLAKE:-''${FLAKE:-${inputs.self}}}}"
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
    nh_extra_args=()
    if [ "''${#nix_override_args[@]}" -gt 0 ]; then
      nh_extra_args=(-- "''${nix_override_args[@]}")
    fi
  '';
  rebuildDefaultArgs = ''
    rebuild_jobs="''${SINNIX_REBUILD_MAX_JOBS:-2}"
    rebuild_cores="''${SINNIX_REBUILD_CORES:-12}"
  '';
  zramResetGuard = import ./zram-reset-guard.nix { inherit pkgs; };
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
  appCommands = {
    lint = {
      description = "Lint Nix and shell files without modifying sources";
      script = ''
        ${resolveFlakeDir}
        cd "$_flake_dir"
        echo "Running deadnix..."
        ${pkgs.deadnix}/bin/deadnix --fail .
        echo "Running statix..."
        ${pkgs.statix}/bin/statix check

        echo "Running shellcheck on shell helpers..."
        ${pkgs.fd}/bin/fd -t f -e sh -x ${pkgs.shellcheck}/bin/shellcheck {}
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

        heavy_targets=(
          ${builtins.concatStringsSep "\n          " (
            map (name: ''"heavyChecks.${system}.${name}"'') heavyCheckNames
          )}
        )

        for target in "''${heavy_targets[@]}"; do
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
        default_targets=(
          ${builtins.concatStringsSep "\n          " (
            map (name: ''"checks.${system}.${name}"'') defaultCheckNames
          )}
        )

        for target in "''${default_targets[@]}"; do
          echo "Running default check: $target"
          ${scriptPkgs.nix-safe}/bin/nix-safe build "$_flake_dir#$target"
        done

        echo "Running heavy checks..."
        ${
          let
            heavyTargets = builtins.concatStringsSep "\n          " (
              map (name: ''"heavyChecks.${system}.${name}"'') heavyCheckNames
            );
          in
          ''
            heavy_targets=(
              ${heavyTargets}
            )

            for target in "''${heavy_targets[@]}"; do
              echo "Running heavy check: $target"
              ${scriptPkgs.nix-safe}/bin/nix-safe build "$_flake_dir#$target"
            done
          ''
        }

        echo "Full non-host semantic check suite complete."
      '';
    };

    test-vm = {
      description = "Build a QEMU VM from current configuration for smoke-testing without switching";
      script = ''
        ${resolveFlakeDir}
        if [ "$(id -u)" -ne 0 ]; then
          echo "Error: This command must be run as root (use 'sudo nix run $_flake_dir#test-vm')"
          exit 1
        fi
        ${avoidRepoCwdForActivation}
        ${localInputOverrideArgs}
        ${rebuildDefaultArgs}
        ${pkgs.systemd}/bin/systemd-run \
          --quiet \
          --collect \
          --pipe \
          --service-type=exec \
          --wait \
          --setenv=PATH="${rebuildServicePath}:$PATH" \
          -p Nice=10 \
          ${pkgs.nixos-rebuild}/bin/nixos-rebuild test-vm --flake "path:$_invoke_flake_dir#sinnix-prime" \
          --max-jobs "$rebuild_jobs" \
          --cores "$rebuild_cores" \
          "''${nix_override_args[@]}"
      '';
    };

    test-system = {
      description = "Test configuration without applying it to the system (nh os test)";
      script = ''
        ${resolveFlakeDir}
        ${avoidRepoCwdForActivation}
        ${localInputOverrideArgs}
        ${rebuildDefaultArgs}
        ${pkgs.systemd}/bin/systemd-run \
          --user \
          --quiet --collect --pipe --service-type=exec --wait \
          --setenv=PATH="${rebuildServicePath}:$PATH" \
          -p Nice=10 \
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
        ${avoidRepoCwdForActivation}
        ${localInputOverrideArgs}
        ${rebuildDefaultArgs}
        _rebuild_status=0
        ${pkgs.systemd}/bin/systemd-run \
          --user \
          --quiet --collect --pipe --service-type=exec --wait \
          --setenv=PATH="${rebuildServicePath}:$PATH" \
          -p Nice=10 \
          ${pkgs.coreutils}/bin/env -u FLAKE NH_FLAKE="$_invoke_flake_dir" \
            ${pkgs.nh}/bin/nh os boot \
            "''${_invoke_flake_dir}#sinnix-prime" \
            --no-nom \
            --max-jobs "$rebuild_jobs" \
            --cores "$rebuild_cores" \
            "''${nh_extra_args[@]}" || _rebuild_status=$?
        ${zramResetGuard}
        exit "$_rebuild_status"
      '';
    };

    switch = {
      description = "Apply configuration changes to the system (nh os switch)";
      script = ''
        ${resolveFlakeDir}
        ${avoidRepoCwdForActivation}
        ${localInputOverrideArgs}
        ${rebuildDefaultArgs}
        _rebuild_status=0
        ${pkgs.systemd}/bin/systemd-run \
          --user \
          --quiet --collect --pipe --service-type=exec --wait \
          --setenv=PATH="${rebuildServicePath}:$PATH" \
          -p Nice=10 \
          ${pkgs.coreutils}/bin/env -u FLAKE NH_FLAKE="$_invoke_flake_dir" \
            ${pkgs.nh}/bin/nh os switch \
            "''${_invoke_flake_dir}#sinnix-prime" \
            --no-nom \
            --max-jobs "$rebuild_jobs" \
            --cores "$rebuild_cores" \
            "''${nh_extra_args[@]}" || _rebuild_status=$?
        ${zramResetGuard}
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
        exec ${pkgs.nh}/bin/nh clean all --no-ask
      '';
    };

    agenix = {
      description = "Manage encrypted secrets with agenix";
      script = ''
        ${inputs.agenix.packages.${system}.default}/bin/agenix "$@"
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
      description = "Build QEMU VM for smoke-testing (nixos-rebuild test-vm)";
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
