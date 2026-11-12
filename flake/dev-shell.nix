# Dev shell configuration for nixos-config
#
# Provides:
# - Development tools and Nix helpers
# - Helper scripts for common operations

{ ... }:
{
  perSystem =
    {
      pkgs,
      sinnixCommandRegistry,
      ...
    }:
    let
      inherit (pkgs) lib;
      commandRegistry = sinnixCommandRegistry;
      nix = "${pkgs.nix}/bin/nix";
      # resolveFlakeDir is shared with command-registry.nix's appCommands
      # (`nix run .#switch` etc.) so both entry points resolve the same way
      # instead of silently drifting apart. scriptPkgs comes from the same
      # place for a plainer reason: `import ./scripts.nix { ... }` is a
      # function application, and Nix memoises the import but not the call --
      # sinnixScriptRegistry (flake/script-registry.nix) is the one evaluation
      # of it per perSystem `pkgs`, shared via `_module.args` with every
      # perSystem module for this system, not just this one.
      inherit (commandRegistry)
        activationPackages
        scriptPkgs
        resolveFlakeDir
        ;
      registryDevCommands = lib.mapAttrs commandRegistry.mkAppCommand (
        lib.filterAttrs (name: _: !builtins.hasAttr name activationPackages) commandRegistry.appCommands
      );
      # Devshell command wrappers — every listed command is directly typeable
      devCommands =
        activationPackages
        // registryDevCommands
        // {
          format = pkgs.writeShellScriptBin "format" ''exec ${nix} fmt "$@"'';
          update = pkgs.writeShellScriptBin "update" ''
            set -euo pipefail
            if [ "$#" -gt 0 ]; then
              # A product input (sinex, polylogue-rewrite) moves only to a
              # revision whose package its CI already published to
              # sinity.cachix.org: the new lock is written aside, each moved
              # product's package is fetched with --max-jobs 0, and only then
              # does the lock replace flake.lock. A switch therefore never
              # compiles a product. The flake reference names the same source
              # Sinnix evaluates; products keep their own nixpkgs, so it is the
              # same derivation.
              _lock_dir=$(mktemp -d)
              trap 'rm -rf "$_lock_dir"' EXIT
              ${nix} flake update "$@" --output-lock-file "$_lock_dir/flake.lock"
              for _product in sinex polylogue-rewrite; do
                _old_lock=$(${pkgs.jq}/bin/jq -cS --arg n "$_product" '.nodes[$n].locked' flake.lock)
                _new_lock=$(${pkgs.jq}/bin/jq -cS --arg n "$_product" '.nodes[$n].locked' "$_lock_dir/flake.lock")
                _new=$(${pkgs.jq}/bin/jq -r --arg n "$_product" '.nodes[$n].locked.rev // empty' "$_lock_dir/flake.lock")
                if [ -z "$_new" ] || [ "$_old_lock" = "$_new_lock" ]; then
                  continue
                fi
                _repo=$(${pkgs.jq}/bin/jq -er --arg n "$_product" '.nodes[$n].locked
                  | if .type == "github" then "\(.owner)/\(.repo)"
                    else .url | capture("^https://github.com/(?<r>[^/]+/[^/.]+)").r end' "$_lock_dir/flake.lock")
                # Preserve the locked fetcher and its source-export policy.
                _package_source=$(PRODUCT_LOCK_JSON="$_new_lock" ${nix} eval --impure --raw \
                  --expr 'builtins.flakeRefToString (builtins.fromJSON (builtins.getEnv "PRODUCT_LOCK_JSON"))')
                _package_ref="$_package_source#default"
                # Git URLs omit locked narHash; verify their resolved content.
                _package_hash=$(${nix} flake metadata --json "$_package_source" | ${pkgs.jq}/bin/jq -er '.locked.narHash')
                _locked_hash=$(printf '%s' "$_new_lock" | ${pkgs.jq}/bin/jq -er '.narHash')
                if [ "$_package_hash" != "$_locked_hash" ]; then
                  echo "update: resolved source hash differs from the locked input; flake.lock is unchanged." >&2
                  exit 1
                fi
                _package_path=$(${nix} eval --raw "$_package_ref.outPath")
                # max-jobs=0 still downloads build inputs before refusing an
                # uncached output. Check the product itself before realization.
                if ! ${nix} path-info --store https://sinity.cachix.org \
                  --option narinfo-cache-negative-ttl 0 "$_package_path" >/dev/null; then
                  echo "update: evaluated product $_package_path is not published; flake.lock is unchanged." >&2
                  exit 1
                fi
                echo "update: fetching $_product $_new from sinity.cachix.org" >&2
                # symlinkJoin defaults to refusing substitutes even when its
                # exact aggregate was published alongside the runtime packages.
                # The exact locked fetcher binds the same exported source
                # tree Sinnix evaluates, including export-ignore policy.
                if ! ${nix} build --max-jobs 0 --option always-allow-substitutes true \
                  --no-link "$_package_ref"; then
                  echo "update: $_repo $_new is not in sinity.cachix.org; flake.lock is unchanged." >&2
                  echo "update: its package workflow publishes master commits; for another revision run" >&2
                  echo "update:   gh workflow run package -R $_repo -f rev=$_new" >&2
                  exit 1
                fi
              done
              cp "$_lock_dir/flake.lock" flake.lock
              exit 0
            fi
            # Routine (no-arg) updates bump every input EXCEPT nixpkgs-ai and the
            # deployed products. nixpkgs-ai feeds CUDA-narrowed AI packages
            # (flake/overlay/package/local-ai.nix) whose derivation hash breaks on
            # any nixpkgs rev change, forcing an hours-long recompile. sinex and
            # polylogue-rewrite name a branch, not a revision, so moving them is
            # a deploy. Bump each deliberately: `update <input>`.
            _routine_input_lines=$(
              ${nix} flake metadata --json \
                | ${pkgs.jq}/bin/jq -er '.locks.nodes.root.inputs | if type != "object" then error("invalid flake inputs") else keys | map(select(. != "nixpkgs-ai" and . != "sinex" and . != "polylogue-rewrite")) | if length == 0 then error("no routine inputs") else .[] end end'
            )
            mapfile -t _routine_inputs <<< "$_routine_input_lines"
            exec ${nix} flake update "''${_routine_inputs[@]}"
          '';
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

      # Keep package-specific Python test dependencies out of the general
      # development shell.  This shell is the lightweight source-test entry
      # point for focused gateway tests. Test executables are declared here;
      # they are not dependencies of the deployed runtime. The runner uses one Python
      # environment so pytest can import the gateway's runtime dependencies.
      agentctlTestTools = builtins.filter (
        p:
        lib.elem (p.pname or (lib.getName p)) [
          "git"
          "beads"
          "beads-with-dolt"
          "worktrunk"
          "pueue"
        ]
      ) scriptPkgs.agentctl.runtimeDependencies;
      gatewayTestPython = pkgs.python3.withPackages (
        ps:
        [
          ps.pytest
          ps.pytest-timeout
        ]
        ++ builtins.filter (
          p:
          !(lib.elem (p.pname or "") [
            "agentctl"
            "sinnix-lib"
            "sinnix-runtime"
          ])
        ) scriptPkgs.sinnix-agent-gateway.dependencies
      );
      gatewayTestRunner = pkgs.writeShellScriptBin "gateway-pytest" ''
        exec ${gatewayTestPython}/bin/python -m pytest "$@"
      '';
      gatewayTestShell = pkgs.mkShellNoCC {
        name = "sinnix-agent-gateway-tests";
        packages = [
          gatewayTestRunner
          scriptPkgs.sinnix-capture
          pkgs.fd
          pkgs.file
          pkgs.git
          pkgs.ripgrep
        ]
        ++ agentctlTestTools;
        shellHook = ''
          _gateway_root="''${PRJ_ROOT:-$(${pkgs.git}/bin/git rev-parse --show-toplevel 2>/dev/null || pwd)}"
          export PYTHONPATH="$_gateway_root/pkgs/sinnix-runtime:$_gateway_root/pkgs/sinnix-lib:$_gateway_root/pkgs/agentctl:$_gateway_root/pkgs/sinnix-agent-gateway:''${PYTHONPATH:-}"
        '';
      };
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

          # Utilities
          pkgs.nix-output-monitor
          pkgs.jq
          pkgs.yq
          pkgs.duckdb
          pkgs.fd
          pkgs.ripgrep
          scriptPkgs.lsp-root
          scriptPkgs.sinnix-rank
          scriptPkgs.sinnix-fs
          scriptPkgs.sinnix-url-ledger
          # Verification must use this checkout, not the installed CLI dispatcher.
          scriptPkgs.sinnix-sqlite-backup

          # Help
          help
        ]
        ++ builtins.attrValues devCommands;

        shellHook = ''
          # Cached shells resolve their source afresh on entry. Metadata copies
          # the tracked tree to an immutable store path without evaluating the
          # host, and binds its revision before the caller can change directory.
          unset SINNIX_DEV_SHELL_FLAKE SINNIX_DEV_SHELL_REV SINNIX_DEV_SHELL_SOURCE
          ${resolveFlakeDir}
          _sinnix_shell_root="$_flake_dir"
          if ! _sinnix_source_metadata=$(${nix} flake metadata --json --no-write-lock-file "$_sinnix_shell_root"); then
            echo "sinnix: cannot capture devshell source" >&2
            exit 69
          fi
          SINNIX_DEV_SHELL_SOURCE="$(printf '%s' "$_sinnix_source_metadata" | ${pkgs.jq}/bin/jq -er '.path')" || exit 69
          SINNIX_DEV_SHELL_REV="$(printf '%s' "$_sinnix_source_metadata" | ${pkgs.jq}/bin/jq -er '.revision // .dirtyRevision // "unknown"')" || exit 69
          export SINNIX_DEV_SHELL_SOURCE SINNIX_DEV_SHELL_REV
          export SINNIX_DEV_SHELL_FLAKE="$_sinnix_shell_root"
          unset _sinnix_source_metadata
          # Keep command stdout usable for typed AgentCTL results.
          {
            echo ""
            echo "NixOS Configuration Development Environment"
            echo ""
            ${motdLines}
            echo ""
            echo "  Run 'help' for descriptions."
            echo ""
          } >&2
        '';
      };

      devShells.gateway-tests = gatewayTestShell;
      devShells.reverse-engineering = pkgs.mkShell {
        name = "sinnix-reverse-engineering";
        packages = [
          scriptPkgs.rea
          pkgs.ghidra
          pkgs.python3
        ];
      };
    };
}
