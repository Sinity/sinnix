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
      resolveFlakeDir = ''
        _flake_dir="''${PRJ_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
      '';
      withLocalInputOverrides = ''
        nix_override_args=()
        local_override_root=""

        append_override_arg() {
          nix_override_args+=(
            --override-input "$1" "$2"
            --no-write-lock-file
          )
        }

        ensure_local_override_root() {
          if [ -z "$local_override_root" ]; then
            local_override_root="$(${pkgs.coreutils}/bin/mktemp -d -t sinnix-local-input.XXXXXX)"
          fi
        }

        cleanup_local_override_root() {
          if [ -n "$local_override_root" ]; then
            rm -rf "$local_override_root"
          fi
        }

        repo_is_dirty() {
          repo_path="$1"
          [ -d "$repo_path" ] || return 1
          git -C "$repo_path" rev-parse --is-inside-work-tree >/dev/null 2>&1 || return 1
          [ -n "$(git -C "$repo_path" status --short --untracked-files=normal 2>/dev/null)" ]
        }

        maybe_snapshot_input() {
          input_name="$1"
          repo_path="$2"
          override_value="$3"
          shift 3

          if [ -n "$override_value" ]; then
            append_override_arg "$input_name" "$override_value"
            return 0
          fi

          if ! repo_is_dirty "$repo_path"; then
            return 0
          fi

          ensure_local_override_root
          snapshot_path="$local_override_root/$input_name"
          rsync_args=(
            -a
            --exclude='.git'
            --exclude='.direnv'
            --exclude='.devenv'
            --exclude='.venv'
            --exclude='.mypy_cache'
            --exclude='.pytest_cache'
            --exclude='__pycache__'
            --exclude='node_modules'
          )
          for exclude_name in "$@"; do
            rsync_args+=("--exclude=$exclude_name")
          done
          ${pkgs.rsync}/bin/rsync "''${rsync_args[@]}" "$repo_path/" "$snapshot_path/"
          append_override_arg "$input_name" "path:$snapshot_path"
        }

        maybe_snapshot_input sinex /realm/project/sinex "''${SINNIX_SINEX_OVERRIDE:-}" .sinex
        maybe_snapshot_input polylogue /realm/project/polylogue "''${SINNIX_POLYLOGUE_OVERRIDE:-}"
        maybe_snapshot_input lynchpin /realm/project/sinity-lynchpin "''${SINNIX_LYNCHPIN_OVERRIDE:-}" .playwright-mcp

        if [ -n "$local_override_root" ]; then
          trap cleanup_local_override_root EXIT
        fi
      '';

      # Devshell command wrappers — every listed command is directly typeable
      devCommands = {
        check = pkgs.writeShellScriptBin "check" ''exec ${nix} flake check "$@"'';
        format = pkgs.writeShellScriptBin "format" ''exec ${nix} fmt "$@"'';
        switch = pkgs.writeShellScriptBin "switch" ''
          set -euo pipefail
          ${resolveFlakeDir}
          ${withLocalInputOverrides}
          cd "$HOME"
          PATH="${safeSudoPathPrefix}:$PATH" \
            sudo ${pkgs.nixos-rebuild}/bin/nixos-rebuild \
            switch \
            --flake "$_flake_dir#sinnix-prime" \
            "''${nix_override_args[@]}" \
            --log-format internal-json \
            -v 2>&1 \
            | ${pkgs.nix-output-monitor}/bin/nom --json
        '';
        test-system = pkgs.writeShellScriptBin "test-system" ''
          set -euo pipefail
          ${resolveFlakeDir}
          ${withLocalInputOverrides}
          cd "$HOME"
          PATH="${safeSudoPathPrefix}:$PATH" \
            sudo ${pkgs.nixos-rebuild}/bin/nixos-rebuild \
            test \
            --flake "$_flake_dir#sinnix-prime" \
            "''${nix_override_args[@]}" \
            --log-format internal-json \
            -v 2>&1 \
            | ${pkgs.nix-output-monitor}/bin/nom --json
        '';
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

        packages =
          [
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
