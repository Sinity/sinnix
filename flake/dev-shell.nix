# Dev shell configuration for nixos-config
#
# Provides:
# - Development tools and Nix helpers
# - Helper scripts for common operations

{ inputs, ... }:
{
  perSystem =
    {
      pkgs,
      system,
      ...
    }:
    let
      lib = pkgs.lib;
      scriptPkgs = (import ./scripts.nix { inherit inputs pkgs; }).packageSet;
      checkTiers = import ./check-tiers.nix { inherit lib; };
      commandRegistry = import ./command-registry.nix {
        inherit inputs pkgs system;
      };
      nix = "${pkgs.nix}/bin/nix";
      safeSudoPathPrefix = "${pkgs.coreutils}/bin";
      rebuildServicePath = lib.makeBinPath [
        pkgs.coreutils
        pkgs.findutils
        pkgs.gnugrep
        pkgs.gnused
        pkgs.systemd
        pkgs.util-linux
      ];
      resolveFlakeDir = ''
        _flake_dir="''${PRJ_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
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
      # Wrapper for nix that serializes heavy subcommands (build, flake check)
      # behind the same lock as switch/boot/test. Passes through all other
      # subcommands (eval, develop, shell, run, fmt, flake update, etc.)
      # without any lock overhead.
      nixWrapper = pkgs.writeShellScriptBin "nix" ''
        set -euo pipefail
        _cmd="''${1:-}"
        _sub="''${2:-}"
        # Decide whether this invocation is nested inside a rebuild that already
        # holds the lock. Two independent signals, because neither alone covers
        # every path:
        #   - SINNIX_REBUILD_ACTIVE=1 is set by switch/boot/test for the build
        #     phase, which runs as the same user — the env survives that hop.
        #   - It does NOT survive the user→root sudo hop that nh makes for the
        #     privileged activation step, which re-invokes us as root to run
        #     `nix build --profile /nix/var/nix/profiles/system …`. That nested
        #     root call must also skip locking: re-acquiring would either EACCES
        #     on the sticky-/tmp lockfile (fs.protected_regular forbids root
        #     opening the user-owned lock) or self-deadlock on the non-blocking
        #     flock the parent switch already holds. `--profile` reliably marks
        #     that profile-install build.
        _nested="''${SINNIX_REBUILD_ACTIVE:-}"
        case " $* " in *" --profile "*) _nested=1 ;; esac
        if [ -z "$_nested" ]; then
          if [ "$_cmd" = "build" ] || { [ "$_cmd" = "flake" ] && [ "$_sub" = "check" ]; }; then
            exec 9>/tmp/sinnix-switch.lock
            if ! ${pkgs.util-linux}/bin/flock --nonblock 9; then
              echo "nix $1: another heavy nix operation is already running — aborting to prevent thrashing" >&2
              echo "  Tip: wait for the running build to finish, or kill it first." >&2
              exit 1
            fi
          fi
        fi
        if [ "$_cmd" = "build" ] || { [ "$_cmd" = "flake" ] && [ "$_sub" = "check" ]; }; then
          export NIX_CONFIG="eval-cache = false"
        fi
        exec ${pkgs.nix}/bin/nix "$@"
      '';

      zramResetGuard = import ./zram-reset-guard.nix { inherit pkgs; };

      mkNhCommand =
        name: action:
        pkgs.writeShellScriptBin name ''
          set -euo pipefail
          exec 9>/tmp/sinnix-switch.lock
          if ! ${pkgs.util-linux}/bin/flock --nonblock 9; then
            echo "sinnix ${name}: another rebuild is already running — aborting to prevent concurrent builds" >&2
            exit 1
          fi
          ${resolveFlakeDir}
          ${localInputOverrideArgs}
          rebuild_jobs="''${SINNIX_REBUILD_MAX_JOBS:-2}"
          rebuild_cores="''${SINNIX_REBUILD_CORES:-12}"

          _rebuild_status=0
          ${pkgs.systemd}/bin/systemd-run \
            --user \
            --quiet --collect --pipe --service-type=exec --wait \
            --setenv=PATH="${rebuildServicePath}:$PATH" \
            --setenv=NIX_CONFIG="eval-cache = false" \
            --setenv=SINNIX_REBUILD_ACTIVE=1 \
            --slice=nix-build.slice \
            -p CPUSchedulingPolicy=idle \
            -p IOSchedulingClass=idle \
            ${pkgs.coreutils}/bin/env -u FLAKE NH_FLAKE="''${_flake_dir}" \
              ${pkgs.nh}/bin/nh os ${action} \
              "''${_flake_dir}#sinnix-prime" \
              --no-nom \
              --max-jobs "$rebuild_jobs" \
              --cores "$rebuild_cores" \
              "''${nh_extra_args[@]}" || _rebuild_status=$?

          # Run the hygiene pass even when nh reports failure: transient
          # activation errors still leave a fully-built generation behind,
          # and the build is what fills zram.
          ${zramResetGuard}
          exit "$_rebuild_status"
        '';

      # Devshell command wrappers — every listed command is directly typeable
      devCommands = {
        check = pkgs.writeShellScriptBin "check" ''
          set -euo pipefail
          ${resolveFlakeDir}
          exec 9>/tmp/sinnix-switch.lock
          if ! ${pkgs.util-linux}/bin/flock --nonblock 9; then
            echo "sinnix check: another heavy nix operation is already running — aborting to prevent thrashing" >&2
            exit 1
          fi

          for arg in "$@"; do
            case "$arg" in
              --no-build)
                ;;
              *)
                echo "sinnix check: unsupported argument '$arg'" >&2
                echo "This command runs the curated default check tier sequentially; use nix directly for custom checks." >&2
                exit 64
                ;;
            esac
          done

          default_targets=(
            ${builtins.concatStringsSep "\n            " (
              map (name: ''"checks.${system}.${name}"'') checkTiers.defaultCheckNames
            )}
          )

          cd "$_flake_dir"
          for target in "''${default_targets[@]}"; do
            echo "Running default check: $target"
            NIX_CONFIG="eval-cache = false" SINNIX_REBUILD_ACTIVE=1 \
              ${scriptPkgs.nix-safe}/bin/nix-safe build "$_flake_dir#$target" --no-link
          done

          echo "Default check tier complete."
        '';
        format = pkgs.writeShellScriptBin "format" ''exec ${nix} fmt "$@"'';
        switch = mkNhCommand "switch" "switch";
        boot = mkNhCommand "boot" "boot";
        test-system = mkNhCommand "test" "test";
        # nh doesn't wrap build-vm; keep direct nixos-rebuild.
        test-vm = pkgs.writeShellScriptBin "test-vm" ''
          set -euo pipefail
          ${resolveFlakeDir}
          ${localInputOverrideArgs}
          rebuild_jobs="''${SINNIX_REBUILD_MAX_JOBS:-2}"
          rebuild_cores="''${SINNIX_REBUILD_CORES:-12}"

          exec sudo ${pkgs.systemd}/bin/systemd-run \
            --quiet --collect --pipe --service-type=exec --wait \
            --setenv=PATH="${rebuildServicePath}:$PATH" \
            --slice=nix-build.slice \
            -p CPUSchedulingPolicy=idle \
            -p IOSchedulingClass=idle \
            ${pkgs.nixos-rebuild}/bin/nixos-rebuild build-vm \
              --flake "path:$_flake_dir#sinnix-prime" \
              --max-jobs "$rebuild_jobs" \
              --cores "$rebuild_cores" \
              "''${nix_override_args[@]}"
        '';
        lint = pkgs.writeShellScriptBin "lint" ''exec ${nix} run .#lint -- "$@"'';
        check-all = pkgs.writeShellScriptBin "check-all" ''exec ${nix} run .#check-all -- "$@"'';
        update = pkgs.writeShellScriptBin "update" ''exec ${nix} flake update "$@"'';
        clean = pkgs.writeShellScriptBin "clean" ''
          exec ${pkgs.nh}/bin/nh clean all --no-ask
        '';
        agenix = pkgs.writeShellScriptBin "agenix" ''exec ${nix} run .#agenix -- "$@"'';
        diff-closure = pkgs.writeShellScriptBin "diff-closure" ''
          set -euo pipefail
          if [ $# -ge 2 ]; then
            exec ${pkgs.nvd}/bin/nvd diff "$@"
          elif [ $# -eq 0 ]; then
            exec ${pkgs.nvd}/bin/nvd diff /nix/var/nix/profiles/system-{1,2}-link
          else
            echo "Usage: diff-closure [before] [after]" >&2
            echo "Default: compares two most recent system profiles" >&2
            exit 1
          fi
        '';
        smoke = pkgs.writeShellScriptBin "smoke" ''
          ${resolveFlakeDir}
          target="''${1:-all}"
          case "$target" in
            terminal) exec ${nix} run "$_flake_dir#host-smoke-terminal" ;;
            services) exec ${nix} run "$_flake_dir#host-smoke-services" ;;
            all)      exec ${nix} run "$_flake_dir#host-smoke-all" ;;
            *) echo "Usage: smoke [terminal|services|all]" >&2; exit 1 ;;
          esac
        '';
      };

      # Grouped table for shellHook
      motdLines = builtins.concatStringsSep "\n" (
        map (
          cat:
          let
            docs = builtins.filter (d: d.category == cat) commandRegistry.commandDocs;
            names = builtins.concatStringsSep " " (map (d: d.name) docs);
          in
          ''printf "  %-11s %s\n" "${cat}" "${names}"''
        ) commandRegistry.categoryOrder
      );

      # Full help with descriptions
      helpLines = builtins.concatStringsSep "\n" (
        lib.concatMap (
          cat:
          let
            docs = builtins.filter (d: d.category == cat) commandRegistry.commandDocs;
          in
          [ ''printf "\n  \033[1m%s\033[0m\n" "${cat}"'' ]
          ++ map (d: ''printf "    %-14s %s\n" "${d.name}" "${d.description}"'') docs
        ) commandRegistry.categoryOrder
      );

      help = pkgs.writeShellScriptBin "help" ''
        echo ""
        echo "NixOS Configuration Development Environment"
        ${helpLines}
        echo ""
      '';
    in
    {
      devShells.default = pkgs.mkShellNoCC {
        name = "nixos-config-dev";

        packages = [
          # nix wrapper must come first — shadows system nix to serialize heavy ops
          nixWrapper

          # Version control
          pkgs.git
          pkgs.gh
          pkgs.delta

          # Nix tools
          pkgs.nil
          pkgs.nixd
          pkgs.nh
          pkgs.nvd
          pkgs.nix-tree

          # Secret management
          inputs.agenix.packages.${system}.default

          # Utilities
          pkgs.nix-output-monitor
          pkgs.jq
          pkgs.yq
          pkgs.fd
          pkgs.ripgrep
          scriptPkgs.lsp-root

          # Help
          help
        ]
        ++ builtins.attrValues devCommands;

        shellHook = ''
          echo ""
          echo "NixOS Configuration Development Environment"
          echo ""
          ${motdLines}
          echo ""
          echo "  Run 'help' for descriptions."
          echo ""
        '';
      };
    };
}
