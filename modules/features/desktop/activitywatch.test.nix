{
  mkFeatureTest,
  hmFor,
  expect,
  ...
}:
[
  (mkFeatureTest {
    name = "desktop-activitywatch";
    feature = "sinnix.features.desktop.activitywatch.enable";
    assertions =
      config:
      let
        hm = hmFor config;
        serverService = hm.systemd.user.services.activitywatch.Service or { };
        watcherInstall = hm.systemd.user.services.activitywatch-watcher-awatcher.Install or { };
      in
      [
        (expect.hmUserServiceExists hm "activitywatch" "ActivityWatch server service must exist")
        (expect.hmUserServiceExists hm "activitywatch-watcher-awatcher" "awatcher service must exist")
        {
          assertion =
            serverService.Nice == 10
            && serverService.IOSchedulingClass == "idle"
            && serverService.IOWeight == 10
            && serverService.MemoryHigh == "1G"
            && serverService.MemoryMax == "2G";
          message = "ActivityWatch must run with background resource guardrails";
        }
        {
          assertion = watcherInstall.WantedBy == [ "graphical-session.target" ];
          message = "ActivityWatch watcher must autostart by default";
        }
      ];
  })
  (mkFeatureTest {
    name = "desktop-activitywatch-manual-start";
    feature = "sinnix.features.desktop.activitywatch.enable";
    extraModules = [
      {
        sinnix.features.desktop.activitywatch.autoStart = false;
      }
    ];
    assertions =
      config:
      let
        hm = hmFor config;
        serverInstall = hm.systemd.user.services.activitywatch.Install or { };
        watcherInstall = hm.systemd.user.services.activitywatch-watcher-awatcher.Install or { };
      in
      [
        {
          assertion = serverInstall.WantedBy == [ ];
          message = "ActivityWatch autoStart=false must remove server graphical-session installation";
        }
        {
          assertion = watcherInstall.WantedBy == [ ];
          message = "ActivityWatch autoStart=false must remove watcher graphical-session installation";
        }
      ];
  })
]
