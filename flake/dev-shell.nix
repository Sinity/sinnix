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
      inherit (pkgs) lib;
      scriptPkgs = (import ./scripts.nix { inherit inputs pkgs; }).packageSet;
      commandRegistry = import ./command-registry.nix {
        inherit inputs pkgs system;
      };
      nix = "${pkgs.nix}/bin/nix";
      inherit (commandRegistry) rebuildServicePath localInputOverrideArgs;
      resolveFlakeDir = ''
        _flake_dir="''${PRJ_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
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
              echo "  Override for a deliberate risky run: SINNIX_REBUILD_SKIP_PRESSURE_PREFLIGHT=1 ${name}"
              echo "  Top RSS processes:"
              ${pkgs.procps}/bin/ps -eo pid,rss,comm,args --sort=-rss | ${pkgs.coreutils}/bin/head -8
            } >&2
            exit 75
          fi
        }
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

      mkNhCommand =
        name: action:
        pkgs.writeShellScriptBin name ''
          set -euo pipefail
          ${commandRegistry.rebuildLock name}
          ${resolveFlakeDir}
          ${localInputOverrideArgs}
          ${commandRegistry.rebuildDefaultArgs}
          ${rebuildPressurePreflight name}
          rebuild_pressure_preflight

          _rebuild_status=0
          ${pkgs.systemd}/bin/systemd-run \
            --user \
            --quiet --collect --pipe --service-type=exec --wait \
            --setenv=PATH="${rebuildServicePath}:$PATH" \
            ${commandRegistry.rebuildContainmentFlags}
            ${pkgs.coreutils}/bin/env -u FLAKE NH_FLAKE="''${_flake_dir}" \
              ${pkgs.nh}/bin/nh os ${action} \
              "''${_flake_dir}#sinnix-prime" \
              --no-nom \
              --max-jobs "$rebuild_jobs" \
              --cores "$rebuild_cores" \
              "''${nh_extra_args[@]}" || _rebuild_status=$?

          if [ "${action}" = "switch" ] && [ "$_rebuild_status" -ne 0 ] && [ "$_rebuild_status" -ne 130 ]; then
            echo "sinnix ${name}: nh failed with status $_rebuild_status; trying exact toplevel activation fallback" >&2
            _toplevel_drv="$(
              SINNIX_REBUILD_ACTIVE=1 NIX_CONFIG="eval-cache = false" \
                ${pkgs.nix}/bin/nix eval \
                  "$_flake_dir#nixosConfigurations.sinnix-prime.config.system.build.toplevel.drvPath" \
                  --raw \
                  --impure \
                  "''${nix_override_args[@]}"
            )"
            _toplevel_out="$(
              SINNIX_REBUILD_ACTIVE=1 NIX_CONFIG="eval-cache = false" \
                ${pkgs.nix}/bin/nix-store -r "$_toplevel_drv"
            )"
            # Register the generation BEFORE activating: without the profile
            # entry, switch-to-configuration boot has no generation to point
            # the bootloader at, activation succeeds only in memory, and the
            # next reboot silently resurrects the previous generation
            # (2026-07-11 incident: taxonomy switch activated live, exit-4 on
            # a failed unit meant nh never ran its profile step, reboot came
            # back on the pre-taxonomy config and recreated retired paths).
            /run/wrappers/bin/sudo ${pkgs.nix}/bin/nix-env \
              --profile /nix/var/nix/profiles/system --set "$_toplevel_out"
            _rebuild_status=0
            /run/wrappers/bin/sudo "$_toplevel_out/bin/switch-to-configuration" switch || _rebuild_status=$?
            # switch-to-configuration exits non-zero whenever ANY unit fails
            # to (re)start, even one wholly unrelated to this config change
            # (sinnix-ihi, 2026-07-08: a pre-existing nvidia-container-
            # toolkit-cdi-generator failure silently blocked profile/
            # bootloader registration for 4+ days -- every switch looked
            # successful but never advanced the boot generation).
            # Registering the built generation as the persistent boot
            # default is orthogonal to whether every service started
            # cleanly, so always do it as a separate step -- but keep the
            # real "switch" exit status (unless this step itself fails
            # worse) so a genuine regression still surfaces instead of
            # being silently masked.
            _boot_status=0
            /run/wrappers/bin/sudo "$_toplevel_out/bin/switch-to-configuration" boot || _boot_status=$?
            if [ "$_boot_status" -ne 0 ]; then
              _rebuild_status="$_boot_status"
            fi
          fi

          if [ "${action}" = "switch" ]; then
            ${commandRegistry.sinexCachePush}
          fi

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

          mapfile -t default_targets < <(
            ${nix} eval "$_flake_dir#checks.${system}" \
              --apply builtins.attrNames \
              --json \
              | ${pkgs.jq}/bin/jq -r '.[] | "checks.${system}.\(.)"'
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
          ${commandRegistry.rebuildLock "test-vm"}
          ${resolveFlakeDir}
          ${localInputOverrideArgs}
          ${commandRegistry.rebuildDefaultArgs}

          # Not `exec`: sudo may close inherited fds (incl. the lock fd held
          # above), so the lock must stay held by this shell until the build
          # actually completes rather than being handed off across the hop.
          sudo ${pkgs.systemd}/bin/systemd-run \
            --quiet --collect --pipe --service-type=exec --wait \
            --setenv=PATH="${rebuildServicePath}:$PATH" \
            ${commandRegistry.rebuildContainmentFlags}
            ${pkgs.nixos-rebuild}/bin/nixos-rebuild build-vm \
              --flake "$_flake_dir#sinnix-prime" \
              --max-jobs "$rebuild_jobs" \
              --cores "$rebuild_cores" \
              --impure \
              "''${nix_override_args[@]}"
        '';
        lint = pkgs.writeShellScriptBin "lint" ''exec ${nix} run .#lint -- "$@"'';
        check-all = pkgs.writeShellScriptBin "check-all" ''exec ${nix} run .#check-all -- "$@"'';
        update = pkgs.writeShellScriptBin "update" ''
          set -euo pipefail
          if [ "$#" -gt 0 ]; then
            exec ${nix} flake update "$@"
          fi
          # Routine (no-arg) updates bump every input EXCEPT nixpkgs-ai: that
          # input feeds CUDA-narrowed AI packages (flake/overlay/package/local-ai.nix)
          # whose derivation hash breaks on any nixpkgs rev change, forcing an
          # hours-long recompile. Bump it deliberately: `update nixpkgs-ai`.
          mapfile -t _routine_inputs < <(
            ${nix} flake metadata --json \
              | ${pkgs.jq}/bin/jq -r '.locks.nodes.root.inputs | keys[] | select(. != "nixpkgs-ai")'
          )
          exec ${nix} flake update "''${_routine_inputs[@]}"
        '';
        clean = pkgs.writeShellScriptBin "clean" ''
          exec ${pkgs.nh}/bin/nh clean all
        '';
        # secrets.nix + secret/*.age live outside the checkout at
        # /realm/data/secrets/sinnix (see modules/secrets.nix) — cd there so
        # RULES defaults to ./secrets.nix and relative FILE args like
        # `secret/foo.age` keep resolving exactly as before the move.
        agenix = pkgs.writeShellScriptBin "agenix" ''
          cd /realm/data/secrets/sinnix && exec ${inputs.agenix.packages.${system}.default}/bin/agenix "$@"
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
          pkgs.duckdb
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
