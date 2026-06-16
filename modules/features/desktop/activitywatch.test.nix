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
        runtimeInventory = builtins.fromJSON config.environment.etc."sinnix/runtime-inventory.json".text;
        observedServiceNames = map (check: check.name) runtimeInventory.observedServices;
        activitywatchEntry = builtins.head (
          builtins.filter (check: check.name == "activitywatch") runtimeInventory.observedServices
        );
        watcherInstall = hm.systemd.user.services.activitywatch-watcher-awatcher.Install or { };
      in
      [
        (expect.hmUserServiceExists hm "activitywatch" "ActivityWatch server service must exist")
        (expect.hmUserServiceExists hm "activitywatch-watcher-awatcher" "awatcher service must exist")
        {
          assertion =
            builtins.elem "activitywatch" observedServiceNames
            && builtins.elem "activitywatch-watcher-awatcher" observedServiceNames
            && activitywatchEntry.manager == "user"
            && activitywatchEntry.kind == "service"
            && activitywatchEntry.resourceClass == "background-maintenance";
          message = "ActivityWatch must be present in runtime inventory with surface metadata";
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
        runtimeInventory = builtins.fromJSON config.environment.etc."sinnix/runtime-inventory.json".text;
        observedServiceNames = map (check: check.name) runtimeInventory.observedServices;
        serverInstall = hm.systemd.user.services.activitywatch.Install or { };
        watcherInstall = hm.systemd.user.services.activitywatch-watcher-awatcher.Install or { };
      in
      [
        {
          assertion =
            !(builtins.elem "activitywatch" observedServiceNames)
            && !(builtins.elem "activitywatch-watcher-awatcher" observedServiceNames);
          message = "ActivityWatch autoStart=false must remove live-service runtime inventory metadata";
        }
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
