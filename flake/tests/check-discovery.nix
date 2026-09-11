# Exercise the rendered commands: failed discovery must never mean zero green checks.
{ inputs, ... }:
{
  perSystem =
    { pkgs, system, ... }:
    let
      fakeNix = pkgs.writeShellScriptBin "nix" ''
        case "$1" in
          eval)
            [ "''${DISCOVERY_FAIL:-0}" = 0 ] || exit 7
            printf '%s\n' "$DISCOVERY_JSON"
            ;;
          build)
            printf '%s\n' "$2" >> "$BUILD_LOG"
            exit "''${BUILD_STATUS:-0}"
            ;;
          *) exit 64 ;;
        esac
      '';
      registry = import ../command-registry.nix {
        inherit inputs system;
        pkgs = pkgs // {
          nix = fakeNix;
        };
        sinnixScriptRegistry.packageSet.nix-safe = pkgs.writeShellScriptBin "nix-safe" ''
          exec ${fakeNix}/bin/nix "$@"
        '';
      };
      commands =
        map
          (
            name:
            pkgs.writeShellScript name ''
              set -euo pipefail
              ${registry.appCommands.${name}.script}
            ''
          )
          [
            "check"
            "check-master"
            "check-heavy"
            "check-all"
          ];
      activationRegistry = import ../command-registry.nix {
        inherit inputs system;
        pkgs = pkgs // {
          systemd = pkgs.writeShellScriptBin "systemd-run" ''
            printf '%s\n' "$*" >> "$ACTIVATION_LOG"
            exit "$ACTIVATION_STATUS"
          '';
          nix = pkgs.writeShellScriptBin "nix" ''
            echo unexpected-nix >> "$ACTIVATION_LOG"
            exit 99
          '';
        };
        sinnixScriptRegistry.packageSet = {
          sinnix-preflight = pkgs.writeShellScriptBin "sinnix-preflight" "exit 0";
          sinnix-sinex-cache-push = pkgs.writeShellScriptBin "sinnix-sinex-cache-push" ''
            echo cache-push >> "$ACTIVATION_LOG"
          '';
        };
      };
      switchCommand = pkgs.writeShellScript "switch-status" ''
        set -euo pipefail
        ${activationRegistry.appCommands.switch.script}
      '';
    in
    {
      checks.check-discovery = pkgs.runCommand "check-discovery" { } ''
        export SINNIX_FLAKE_DIR="$TMPDIR" BUILD_LOG="$TMPDIR/builds"
        unset AGENTCTL_PRINCIPAL AGENTCTL_OPERATION
        for command in ${pkgs.lib.escapeShellArgs commands}; do
          for malformed in '[]' '{}' 'null' 'invalid' '[1]' '[""]'; do
            : > "$BUILD_LOG"
            if DISCOVERY_JSON="$malformed" "$command"; then
              echo "invalid discovery succeeded: $malformed" >&2
              exit 1
            fi
            test ! -s "$BUILD_LOG"
          done
          : > "$BUILD_LOG"
          if DISCOVERY_FAIL=1 DISCOVERY_JSON='["one"]' "$command"; then
            echo "evaluation failure succeeded" >&2
            exit 1
          fi
          test ! -s "$BUILD_LOG"
          DISCOVERY_JSON='["one","two"]' "$command"
          test -s "$BUILD_LOG"
          if BUILD_STATUS=9 DISCOVERY_JSON='["one"]' "$command"; then
            echo "build failure succeeded" >&2
            exit 1
          fi
        done
        : > "$BUILD_LOG"
        DISCOVERY_JSON='["one","two"]' ${builtins.head commands} --no-build
        test ! -s "$BUILD_LOG"
        export SUDO_HOME="$TMPDIR" ACTIVATION_LOG="$TMPDIR/activation"
        for expected in 7 130; do
          : > "$ACTIVATION_LOG"
          status=0
          ACTIVATION_STATUS="$expected" ${switchCommand} || status=$?
          test "$status" = "$expected"
          test "$(wc -l < "$ACTIVATION_LOG")" = 1
          if grep -q 'unexpected-nix\|cache-push' "$ACTIVATION_LOG"; then
            echo 'failed activation attempted another execution route' >&2
            exit 1
          fi
        done
        touch "$out"
      '';
    };
}
