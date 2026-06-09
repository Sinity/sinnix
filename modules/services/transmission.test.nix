{
  lib,
  mkServiceTest,
  ...
}:
let
  commonAssertions = config: [
    {
      assertion = config.services.transmission.enable;
      message = "Transmission must be enabled";
    }
    {
      assertion = config.systemd.services.transmission.unitConfig ? RequiresMountsFor;
      message = "Transmission must declare required mounts";
    }
    {
      assertion =
        let
          preStart = config.systemd.services.transmission.serviceConfig.ExecStartPre or [ ];
        in
        builtins.any (line: lib.hasInfix "/bin/install -d" line) preStart
        && !(builtins.any (line: lib.hasInfix "/tdown" line) config.systemd.tmpfiles.rules);
      message = "Transmission must create automount-backed torrent directories only when started";
    }
    {
      assertion =
        with config.systemd.services.transmission.serviceConfig;
        Nice == 10
        && CPUWeight == 5
        && IOWeight == 5
        && IOSchedulingClass == "idle"
        && !(config.systemd.services.transmission.serviceConfig ? IOSchedulingPriority);
      message = "Transmission must yield during desktop I/O pressure";
    }
    {
      assertion =
        with config.systemd.services.transmission.serviceConfig;
        MemoryHigh == "1G" && MemoryMax == "3G";
      message = "Transmission must not be able to consume unbounded memory";
    }
    {
      assertion =
        with config.services.transmission.settings;
        start-added-torrents == true
        && cache-size-mb == 128
        && download-queue-enabled == false
        && download-queue-size == 20
        && queue-stalled-enabled == false
        && seed-queue-enabled == false;
      message = "Transmission must actively start added torrents and avoid silent stalled queues";
    }
  ];
in
[
  (mkServiceTest {
    name = "services-transmission";
    service = "transmission";
    assertions =
      config:
      commonAssertions config
      ++ [
        {
          assertion = config.systemd.timers.transmission-autostart.wantedBy == [ "timers.target" ];
          message = "Transmission autostart must be enabled by default";
        }
      ];
  })
  (mkServiceTest {
    name = "services-transmission-manual-start";
    service = "transmission";
    extraModules = [
      {
        sinnix.services.transmission.autoStart = false;
      }
    ];
    assertions =
      config:
      commonAssertions config
      ++ [
        {
          assertion = config.systemd.timers.transmission-autostart.wantedBy == [ ];
          message = "Transmission autoStart=false must remove the boot timer";
        }
      ];
  })
]
