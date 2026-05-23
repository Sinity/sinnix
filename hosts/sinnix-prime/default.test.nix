{ inputs, lib, ... }:
{
  name = "host-sinnix-prime-observability-policy";
  modules = [
    { imports = [ (inputs.self + "/hosts/sinnix-prime") ]; }
  ];
  assertions =
    config:
    let
      packageNames = map (pkg: pkg.name or "") config.environment.systemPackages;
      airvpn = config.sinnix.services.airvpn-seed;
      machineTelemetry = config.sinnix.services.machine-telemetry;
      polylogue = config.sinnix.services.polylogue;
      sinex = config.sinnix.services.sinex;
      transmission = config.services.transmission.settings;
      transmissionService = config.systemd.services.transmission;
      sinexRuntimeTimerWantedBy =
        lib.attrByPath [ "systemd" "timers" "sinex-runtime" "wantedBy" ] [ ]
          config;
      polylogueHm = config.home-manager.users.${config.sinnix.user.name};
    in
    [
      {
        assertion =
          !(config.systemd.services ? sinnix-sentinel) && !(config.systemd.timers ? sinnix-sentinel);
        message = "sinnix-prime must not run the scan-heavy sentinel loop as a background timer";
      }
      {
        assertion = builtins.elem "sinnix-resource-audit" packageNames;
        message = "sinnix-prime must expose the live resource-policy audit command";
      }
      {
        assertion =
          config.sinnix.gpu.mode == "nvidia"
          && config.hardware.nvidia.open == false
          && lib.hasInfix "NVreg_EnableGpuFirmware=0" config.boot.extraModprobeConfig;
        message = "sinnix-prime must use proprietary NVIDIA with GSP firmware disabled after GSP heartbeat lockups";
      }
      {
        assertion =
          config.systemd.services.sinnix-disable-nvme-aspm.script != null
          && lib.hasInfix "disable_aspm 00:06.0" config.systemd.services.sinnix-disable-nvme-aspm.script
          && lib.hasInfix "disable_aspm 02:00.0" config.systemd.services.sinnix-disable-nvme-aspm.script
          && lib.hasInfix "& ~0x3" config.systemd.services.sinnix-disable-nvme-aspm.script;
        message = "sinnix-prime must clear ASPM on the Crucial P3 /realm NVMe link";
      }
      {
        assertion =
          airvpn.enable
          && airvpn.autoStart == false
          && airvpn.forwardedPort == 20241
          && transmission.bind-address-ipv4 == "10.148.66.217"
          && transmission.peer-port == 20241
          && builtins.elem "wireguard-airvpn-seed.target" (transmissionService.wants or [ ])
          && builtins.elem "wireguard-airvpn-seed.target" (transmissionService.after or [ ]);
        message = "sinnix-prime must keep AirVPN seeding enabled while Transmission owns tunnel startup";
      }
      {
        assertion =
          machineTelemetry.enable
          && machineTelemetry.intervalSec == 10
          && machineTelemetry.serviceIntervalSec == 10
          && machineTelemetry.networkIntervalSec == 300
          && machineTelemetry.bufferbloatIntervalSec == 1800
          && machineTelemetry.gpuIntervalSec == 1.0;
        message = "sinnix-prime must not keep machine telemetry recovery throttles";
      }
      {
        assertion =
          polylogue.enable
          && polylogue.daemon.autoStart
          && polylogue.health.unit == "polylogued.service"
          && polylogueHm.systemd.user.services.polylogued.Install.WantedBy == [ "default.target" ];
        message = "sinnix-prime must autostart Polylogue after live-ingest repair updates";
      }
      {
        assertion =
          sinex.enable
          && sinex.autoStart
          && sinex.health.unit == "sinex-ingestd.service"
          && sinexRuntimeTimerWantedBy == [ "timers.target" ];
        message = "sinnix-prime must install the delayed Sinex runtime timer";
      }
    ];
}
