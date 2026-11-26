{
  mkFeatureModule,
  pkgs,
  ...
}@args:
mkFeatureModule {
  path = [
    "desktop"
    "sessionRestore"
  ];
  description = "Save the desktop working session and restore it after a reboot";
  configFn =
    {
      config,
      lib,
      helpers,
      pkgs,
      ...
    }:
    let
      scriptPkgs = helpers.mkSinnixPackagesFor pkgs;
      executable = "${scriptPkgs.sinnix-desktop-session}/bin/sinnix-desktop-session";
      graphical = "graphical-session.target";
      restore = "sinnix-desktop-restore";
      snapshot = "sinnix-desktop-snapshot";
      sessionBound = {
        partOf = [ graphical ];
        requisite = [ graphical ];
        after = [ graphical ];
      };
    in
    lib.mkIf
      (config.sinnix.features.desktop.hyprland.enable && config.sinnix.features.desktop.terminal.enable)
      (
        lib.mkMerge [
          (lib.sinnix.mkScheduledJob
            {
              inherit config;
              unitName = snapshot;
              description = "Save the desktop working session";
            }
            {
              manager = "user";
              execStart = "${executable} snapshot";
              unit = sessionBound // {
                after = sessionBound.after ++ [ "${restore}.service" ];
              };
              serviceConfig = {
                TimeoutStartSec = "20s";
                UMask = "0077";
              };
              timer = {
                intervalSec = 60;
                accuracySec = "1us";
              };
            }
          )
          {
            sinnix.persistence.home.directories = lib.mkIf (!config.sinnix.features.desktop.browser.enable) [
              ".local/state/sinnix"
            ];

            systemd.user.timers.${snapshot} = sessionBound // {
              wantedBy = lib.mkForce [ graphical ];
              after = sessionBound.after ++ [ "${restore}.service" ];
              timerConfig.OnActiveSec = "1s";
            };

            systemd.user.services.${restore} = sessionBound // {
              description = "Restore the previous boot's desktop working session";
              after = sessionBound.after ++ [
                "noctalia.service"
                "agentctl-pools.service"
              ];
              wantedBy = [ graphical ];
              serviceConfig = {
                Type = "oneshot";
                ExecStart = "${executable} restore --executable ${executable}";
                TimeoutStartSec = "55s";
                UMask = "0077";
              };
            };
          }
        ]
      );
} args
