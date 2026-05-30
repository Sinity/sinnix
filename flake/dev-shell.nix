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
      mkNhCommand =
        name: action:
        pkgs.writeShellScriptBin name ''
          set -euo pipefail
          ${resolveFlakeDir}
          ${localInputOverrideArgs}
          rebuild_jobs="''${SINNIX_REBUILD_MAX_JOBS:-4}"
          rebuild_cores="''${SINNIX_REBUILD_CORES:-4}"

          exec sudo ${pkgs.systemd}/bin/systemd-run \
            --quiet --collect --pipe --service-type=exec --wait \
            --setenv=PATH="${rebuildServicePath}:$PATH" \
            -p Nice=10 \
            ${pkgs.nh}/bin/nh os ${action} \
              "''${_flake_dir}#sinnix-prime" \
              --max-jobs "$rebuild_jobs" \
              --cores "$rebuild_cores" \
              "''${nix_override_args[@]}" \
              --no-ask
        '';

      # Devshell command wrappers — every listed command is directly typeable
      devCommands = {
        check = pkgs.writeShellScriptBin "check" ''
          exec ${scriptPkgs.nix-safe}/bin/nix-safe flake check "$@"
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
          rebuild_jobs="''${SINNIX_REBUILD_MAX_JOBS:-4}"
          rebuild_cores="''${SINNIX_REBUILD_CORES:-4}"

          exec sudo ${pkgs.systemd}/bin/systemd-run \
            --quiet --collect --pipe --service-type=exec --wait \
            --setenv=PATH="${rebuildServicePath}:$PATH" \
            -p Nice=10 \
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
