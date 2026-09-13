# Provisional declared-activity state and bounded reconsideration delivery.
# No behavior classification: the CLI owns declarations, systemd owns time.
{
  mkServiceModule,
  pkgs,
  helpers,
  ...
}@args:
let
  activity = (helpers.mkSinnixPackagesFor pkgs).sinnix-activity;
in
mkServiceModule {
  name = "activity";
  description = "Declared activity state and bounded reconsideration notifications";
  docs = "docs/activity.md";
  surface = {
    unit = "sinnix-activity.service";
    manager = "user";
    resourceClass = "ordinary";
    observe.enable = true;
  };
  job = {
    manager = "user";
    resourceClass = "ordinary";
    execStart = "${activity}/bin/sinnix-activity tick --notify";
    serviceConfig = {
      TimeoutStartSec = "20s";
      UMask = "0077";
    };
    timer = {
      onStartupSec = "15s";
      intervalSec = 30;
      accuracySec = "1s";
    };
  };
  configFn = { config, ... }: {
    environment.systemPackages = [ activity ];
    home-manager.users.${config.sinnix.user.name}.home.file.".local/bin/sinnix-activity".source =
      "${activity}/bin/sinnix-activity";
    # The parent .local/state/sinnix is already persisted by the desktop configuration.
  };
} args
