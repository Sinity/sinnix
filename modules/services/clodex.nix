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
    { ... }:
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
} args
