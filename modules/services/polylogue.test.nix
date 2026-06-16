{
  lib,
  mkServiceTest,
  expect,
  hmFor,
  ...
}:
let
  commonAssertions =
    config:
    let
      hm = hmFor config;
      daemonService = hm.systemd.user.services.polylogued.Service or { };
      backupService = hm.systemd.user.services.polylogue-sqlite-backup.Service or { };
    in
    [
      (expect.hmUserServiceExists hm "polylogued" "Polylogue daemon user service must exist")
      {
        assertion = !(builtins.hasAttr "polylogue-run" hm.systemd.user.services);
        message = "Polylogue must not install a separate batch catch-up writer service";
      }
      {
        assertion = !(builtins.hasAttr "polylogue-run" hm.systemd.user.timers);
        message = "Polylogue must not install a batch catch-up timer";
      }
      {
        assertion = daemonService.ExecStart != null;
        message = "Polylogue daemon must have an ExecStart" + "(either via source symlink or inline text)";
      }
      # No standalone browser-capture unit — the daemon owns it in-process.
      {
        assertion = !(builtins.hasAttr "polylogue-browser-capture" hm.systemd.user.services);
        message = "Standalone browser-capture service must not exist when polylogued owns the receiver";
      }
      (expect.attrPathEq daemonService [
        "Restart"
      ] "on-failure" "Polylogue daemon must restart on failure")
      (expect.attrPathEq daemonService [
        "IOAccounting"
      ] true "Polylogue daemon must expose cgroup IO counters for machine telemetry attribution")
      {
        assertion = backupService.IOAccounting == true;
        message = "Polylogue SQLite DBs must have a low-priority weekly logical backup";
      }
      {
        assertion =
          config.sinnix.runtime.surfaces.polylogue-sqlite-backup.manager == "user"
          && config.sinnix.runtime.surfaces.polylogue-sqlite-backup.observe.enable
          && config.sinnix.runtime.surfaces.polylogue-sqlite-backup.resourceClass == "backup-maintenance";
        message = "Polylogue SQLite backups must land under backed-up /persist and be inventory-visible";
      }
    ];
in
[
  (mkServiceTest {
    name = "services-polylogue";
    service = "polylogue";
    assertions =
      config:
      let
        hm = hmFor config;
      in
      commonAssertions config
      ++ [
        {
          assertion =
            config.sinnix.runtime.surfaces.polylogued.unit == "polylogued.service"
            && config.sinnix.runtime.surfaces.polylogued.observe.enable;
          message = "Polylogue daemon must be present in observability inventory when autostarted";
        }
        {
          assertion = hm.systemd.user.services.polylogued.Install.WantedBy == [ "default.target" ];
          message = "Polylogue daemon must start automatically by default";
        }
      ];
  })
  (mkServiceTest {
    name = "services-polylogue-manual-start";
    service = "polylogue";
    extraModules = [
      {
        sinnix.services.polylogue.daemon.autoStart = false;
      }
    ];
    assertions =
      config:
      let
        hm = hmFor config;
      in
      commonAssertions config
      ++ [
        {
          assertion = !(config.sinnix.runtime.surfaces ? polylogued);
          message = "Polylogue daemon autoStart=false must remove live-service observability metadata";
        }
        {
          assertion = hm.systemd.user.services.polylogued.Install.WantedBy == [ ];
          message = "Polylogue daemon autoStart=false must remove default user-session installation";
        }
      ];
  })
]
