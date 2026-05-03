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
      commandRegistry = import ./command-registry.nix {
        inherit inputs pkgs system;
      };
      resourceBudgets = import ../modules/lib/resource-budgets.nix;
      developerBudget = resourceBudgets.developerWork;
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
      '';
      mkRebuildCommand =
        name: action:
        pkgs.writeShellScriptBin name ''
          set -euo pipefail
          ${resolveFlakeDir}
          ${localInputOverrideArgs}

          rebuild_runner="$(${pkgs.coreutils}/bin/mktemp)"
          rebuild_pid=""

          cleanup_rebuild() {
            local status=$?
            trap - EXIT HUP INT TERM
            if [ -n "''${rebuild_pid:-}" ] && kill -0 "$rebuild_pid" 2>/dev/null; then
              kill -TERM -- "-$rebuild_pid" 2>/dev/null || true
              ${pkgs.coreutils}/bin/sleep 1
              kill -KILL -- "-$rebuild_pid" 2>/dev/null || true
            fi
            ${pkgs.coreutils}/bin/rm -f "$rebuild_runner"
            exit "$status"
          }

          trap cleanup_rebuild EXIT HUP INT TERM

          cat >"$rebuild_runner" <<'EOF'
          #!${pkgs.bash}/bin/bash
          set -euo pipefail
          flake_ref="$1"
          shift
          rebuild_jobs="''${SINNIX_REBUILD_MAX_JOBS:-auto}"
          rebuild_cores="''${SINNIX_REBUILD_CORES:-0}"
          PATH="${safeSudoPathPrefix}:$PATH" \
            sudo ${pkgs.systemd}/bin/systemd-run \
            --quiet \
            --collect \
            --pipe \
            --service-type=exec \
            --wait \
            --setenv=PATH="${rebuildServicePath}:$PATH" \
            -p Slice=nix-build.slice \
            -p CPUWeight=${toString developerBudget.cpuWeight} \
            -p IOWeight=${toString developerBudget.ioWeight} \
            ${pkgs.nixos-rebuild}/bin/nixos-rebuild \
              ${action} \
              --flake "$flake_ref" \
              "$@" \
              --max-jobs "$rebuild_jobs" \
              --cores "$rebuild_cores" \
              --log-format internal-json \
              -v 2>&1 \
            | ${pkgs.nix-output-monitor}/bin/nom --json
          EOF

          ${pkgs.coreutils}/bin/chmod +x "$rebuild_runner"

          cd "$HOME"
          ${pkgs.util-linux}/bin/setsid "$rebuild_runner" \
            "path:$_flake_dir#sinnix-prime" \
            "''${nix_override_args[@]}" &
          rebuild_pid=$!
          wait "$rebuild_pid"
          status=$?

          trap - EXIT HUP INT TERM
          ${pkgs.coreutils}/bin/rm -f "$rebuild_runner"
          exit "$status"
        '';

      # Devshell command wrappers — every listed command is directly typeable
      devCommands = {
        check = pkgs.writeShellScriptBin "check" ''
          exec ${scriptPkgs.nix-safe}/bin/nix-safe flake check "$@"
        '';
        format = pkgs.writeShellScriptBin "format" ''exec ${nix} fmt "$@"'';
        switch = mkRebuildCommand "switch" "switch";
        test-system = mkRebuildCommand "test-system" "test";
        lint = pkgs.writeShellScriptBin "lint" ''exec ${nix} run .#lint -- "$@"'';
        check-all = pkgs.writeShellScriptBin "check-all" ''exec ${nix} run .#check-all -- "$@"'';
        update = pkgs.writeShellScriptBin "update" ''exec ${nix} flake update "$@"'';
        clean = pkgs.writeShellScriptBin "clean" ''
          ${resolveFlakeDir}
          exec sudo ${nix} run --accept-flake-config "$_flake_dir#clean" -- "$@"
        '';
        agenix = pkgs.writeShellScriptBin "agenix" ''exec ${nix} run .#agenix -- "$@"'';
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
          # Version control
          pkgs.git
          pkgs.gh
          pkgs.delta

          # Nix tools
          pkgs.nil
          pkgs.nixd

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
