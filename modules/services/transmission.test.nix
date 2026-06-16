{ mkServiceTest, ... }:
let
  commonAssertions = config: [
    {
      assertion = config.systemd.services.transmission.unitConfig ? RequiresMountsFor;
      message = "Transmission must declare required mounts";
    }
    {
      assertion =
        with config.services.transmission.settings;
        start-added-torrents == true
        && download-queue-enabled == false
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
