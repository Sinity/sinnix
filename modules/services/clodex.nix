{
  mkServiceModule,
  config,
  helpers,
  lib,
  pkgs,
  ...
}@args:
let
  user = config.sinnix.user.name;
  scriptPkgs = helpers.mkSinnixPackagesFor pkgs;
  clodex = "/home/${user}/.local/bin/clodex";
in
mkServiceModule {
  name = "clodex";
  description = "Local Clodex proxy for subscription-authenticated Claude Code sessions";
  docs = "docs/clodex.md";
  surface = {
    unit = "sinnix-clodex.service";
    manager = "user";
    resourceClass = "interactive-agent";
    observe = {
      enable = true;
      restartable = true;
    };
  };
  configFn =
    { cfg, ... }:
    {
      home-manager.users.${user}.systemd.user.services.sinnix-clodex = {
        Unit = {
          Description = "Local Clodex proxy for Claude Code";
          # Before device-code OAuth finishes, leave this enabled unit inactive
          # rather than crash-looping a credential-dependent service.
          ConditionPathExists = "/home/${user}/.clodex/providers.json";
          After = [ "graphical-session.target" ];
        };
        Service =
          (lib.sinnix.mkRuntimeServiceConfig {
            runtimeInventory = config.sinnix.runtime.inventory;
            unit = "sinnix-clodex.service";
          })
          // {
            Type = "simple";
            # The CLI owns the mutable model registry. Reconcile it before
            # every start, then refuse readiness when the patched Claude
            # binary no longer matches the recorded version and size.
            # Unit values are single lines: each pre-start step is a store
            # script, not an inline shell body.
            ExecStartPre = [
              "${pkgs.writeShellScript "sinnix-clodex-aliases" ''
                set -euo pipefail
                cli=${lib.escapeShellArg clodex}
                models="$($cli models --json)"
                for alias in $(printf '%s' "$models" | ${pkgs.jq}/bin/jq -r '.[] | .alias // empty'); do
                  case "$alias" in
                    ${
                      if cfg.aliases == { } then
                        "__sinnix_no_declared_alias__"
                      else
                        lib.concatStringsSep "|" (lib.attrNames cfg.aliases)
                    }) ;;
                    *) "$cli" models --unalias "$alias" >/dev/null 2>&1 || true ;;
                  esac
                done
                ${lib.concatMapStringsSep "\n" (name: ''
                  "$cli" models --alias ${lib.escapeShellArg "${name}=${cfg.aliases.${name}}"}
                '') (lib.attrNames cfg.aliases)}
              ''}"
            ];
            ExecCondition = "${pkgs.writeShellScript "sinnix-clodex-patch-check" ''
                set +e
                (
                set -euo pipefail
                manifest="/home/${user}/.clodex/patch-state.json"
                if [ ! -r "$manifest" ]; then
                  echo "clodex: Claude Code is not patched; run clodex patch, then systemctl --user start sinnix-clodex" >&2
                  exit 78
                fi
                binary="$(${pkgs.jq}/bin/jq -er '.binaryPath' "$manifest")"
                expected="$(${pkgs.jq}/bin/jq -er '.claudeVersion' "$manifest")"
                if [ ! -x "$binary" ]; then
                  echo "clodex: patched Claude Code binary is missing: $binary; run clodex patch, then systemctl --user start sinnix-clodex" >&2
                  exit 78
                fi
                actual="$($binary --version 2>/dev/null | ${pkgs.gnugrep}/bin/grep -Eo '[0-9]+(\.[0-9]+)+' | ${pkgs.coreutils}/bin/head -n1 || true)"
                size="$(${pkgs.coreutils}/bin/stat -c '%s' "$binary")"
                patched_size="$(${pkgs.jq}/bin/jq -er '.patchedSize' "$manifest")"
                if [ -z "$actual" ] || [ "$actual" != "$expected" ] || [ "$size" != "$patched_size" ]; then
                  echo "clodex: Claude Code patch is stale (expected $expected/$patched_size, found ''${actual:-unknown}/$size); run clodex patch, then systemctl --user start sinnix-clodex" >&2
                  exit 78
                fi
                )
                status=$?
                case "$status" in
                  0) exit 0 ;;
                  78) exit 1 ;;
                  *) exit 255 ;;
                esac
              ''}";
            ExecStart = "/home/${user}/.local/bin/sinnix-clodex-server";
            Environment = [
              "CLODEX_CREDENTIAL_HELPER=${scriptPkgs.sinnix-clodex-credential-helper}/bin/sinnix-clodex-credential-helper"
            ];
            Restart = "on-failure";
            RestartSec = "5s";
            UMask = "0077";
          };
        Install.WantedBy = [ "default.target" ];
      };
    };
  extraOptions.aliases = lib.mkOption {
    type = lib.types.attrsOf lib.types.str;
    default = {
      sol = "clodex:openai-oauth:gpt-5.6-sol";
      terra = "clodex:openai-oauth:gpt-5.6-terra";
      luna = "clodex:openai-oauth:gpt-5.6-luna";
    };
    description = "Exact Clodex model aliases reconciled before the bridge starts.";
  };
} args
