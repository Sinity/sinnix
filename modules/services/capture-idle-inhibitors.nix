# Native inhibitor inventories are diagnostic provenance, not human presence.
{
  mkServiceModule,
  mkCaptureLane,
  config,
  pkgs,
  helpers,
  ...
}@args:
let
  packages = helpers.mkSinnixPackagesFor pkgs;
in
mkServiceModule (mkCaptureLane {
  name = "capture-idle-inhibitors";
  defaultOnDesktop = true;
  description = "Structured Hyprland and logind idle-inhibitor provenance";
  username = config.sinnix.user.name;
  laneDir = config.sinnix.paths.capturePaths.idle-inhibitors;
  mode = "stream";
  captureName = "idle-inhibitors";
  eventDriven = true;
  cadenceSeconds = 300;
  staleAfterSeconds = 900;
  requiredPayloadFields = [
    "event"
    "provenance"
  ];
  execStart = "${packages.sinnix-capture-idle-inhibitors}/bin/sinnix-capture-idle-inhibitors --capture-bin ${packages.sinnix-capture}/bin/sinnix-capture --capture-root ${config.sinnix.paths.activityRoot}";
  unitDescription = "Capture idle-inhibitor provenance";
}) args
