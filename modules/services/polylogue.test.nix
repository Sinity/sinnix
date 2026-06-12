{
  lib,
  mkServiceTest,
  expect,
  hmFor,
  inputs,
  ...
}:
let
  commonAssertions =
    config:
    let
      hm = hmFor config;
      daemonService = hm.systemd.user.services.polylogued.Service or { };
      backupService = hm.systemd.user.services.polylogue-sqlite-backup.Service or { };
      backupTimer = hm.systemd.user.timers.polylogue-sqlite-backup.Timer or { };
      source = builtins.readFile (inputs.self + "/modules/services/polylogue.nix");
      # NOTE(2026-05-28): upstream module no longer uses xdg.configFile for
      # polylogue.toml — the daemon writes it at runtime via its own config path.
      daemonExecStart =
        let
          raw = daemonService.ExecStart or [ ];
        in
        if builtins.isList raw then builtins.concatStringsSep " " raw else raw;
      backupExecStart =
        let
          raw = backupService.ExecStart or [ ];
        in
        if builtins.isList raw then builtins.concatStringsSep " " raw else raw;
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
      (expect.textContains daemonExecStart "/bin/polylogued run"
        "Polylogue daemon unit must invoke polylogued run"
      )
      # No standalone browser-capture unit — the daemon owns it in-process.
      {
        assertion = !(builtins.hasAttr "polylogue-browser-capture" hm.systemd.user.services);
        message = "Standalone browser-capture service must not exist when polylogued owns the receiver";
      }
      (expect.attrPathEq daemonService [
        "Restart"
      ] "on-failure" "Polylogue daemon must restart on failure")
      (expect.attrPathEq daemonService [
        "MemoryHigh"
      ] "4G" "Polylogue daemon must have enough soft memory headroom for live insight refresh")
      (expect.attrPathEq daemonService [
        "MemoryMax"
      ] "6G" "Polylogue daemon must keep hard memory headroom above its soft reclaim threshold")
      {
        assertion =
          lib.hasInfix "polylogue-sqlite-backup" backupExecStart
          && backupService.IOSchedulingClass == "idle"
          && backupService.TimeoutStartSec == "2h"
          && backupService.MemoryHigh == "3G"
          && backupService.MemoryMax == "6G"
          && backupTimer.OnCalendar == "Sun 04:35:00"
          && backupTimer.Persistent == false;
        message = "Polylogue SQLite DBs must have a low-priority weekly logical backup";
      }
      {
        assertion =
          lib.hasInfix "/persist/backup/polylogue-sqlite" source
          && builtins.elem "d /persist/backup/polylogue-sqlite 0700 sinity users -" config.systemd.tmpfiles.rules
          && lib.hasInfix "sqlite3 \"$source\" \".backup '$raw_tmp'\"" source
          && lib.hasInfix "zstd -T1" source
          && lib.hasInfix "NR > 3" source
          && config.sinnix.runtime.surfaces.polylogue-sqlite-backup.manager == "user"
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
