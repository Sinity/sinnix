# Records what is inhibiting idle/display sleep: Hyprland inhibiting clients
# and the logind inhibitor inventory, plus the active window. Polls every 30 s,
# writes on change and a heartbeat every 5 min. Each source carries its own
# status, so an empty inventory differs from an unavailable one. This explains
# idle inhibition; it is not evidence of human presence, and transitions
# shorter than the poll interval can be missed.
{
  mkServiceModule,
  config,
  pkgs,
  helpers,
  ...
}@args:
let
  packages = helpers.mkSinnixPackagesFor pkgs;
in
mkServiceModule {
  name = "capture-idle-inhibitors";
  defaultOnDesktop = true;
  description = "Structured Hyprland and logind idle-inhibitor provenance";
  configFn = _: {
    sinnix.capture.producers.capture-idle-inhibitors = {
      directories = [ config.sinnix.paths.capturePaths.idle-inhibitors ];
      outputs = [
        {
          path = config.sinnix.paths.capturePaths.idle-inhibitors;
          name = "idle-inhibitors";
          eventDriven = true;
          cadenceSeconds = 300;
          staleAfterSeconds = 900;
          requiredPayloadFields = [
            "event"
            "provenance"
          ];
        }
      ];
      execStart = "${packages.sinnix-capture-idle-inhibitors}/bin/sinnix-capture-idle-inhibitors --capture-bin ${packages.sinnix-capture}/bin/sinnix-capture --capture-root ${config.sinnix.paths.activityRoot}";
      description = "Capture idle-inhibitor provenance";
      stream = { };
    };
  };
} args
