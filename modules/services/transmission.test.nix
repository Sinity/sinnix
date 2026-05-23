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
        Nice == 10 && CPUWeight == 20 && IOWeight == 10 && IOSchedulingClass == "idle";
      message = "Transmission must run below interactive desktop priority";
    }
    {
      assertion =
        with config.systemd.services.transmission.serviceConfig;
        MemoryHigh == "1G" && MemoryMax == "4G";
      message = "Transmission must not be able to consume unbounded memory";
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
