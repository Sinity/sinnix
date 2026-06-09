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
      surfaces = config.sinnix.runtime.surfaces;
      transmission = config.services.transmission.settings;
      transmissionService = config.systemd.services.transmission;
      sinexRuntimeTimerWantedBy =
        lib.attrByPath [ "systemd" "timers" "sinex-runtime" "wantedBy" ] [ ]
          config;
      polylogueHm = config.home-manager.users.${config.sinnix.user.name};
      keylogRoot = "${config.sinnix.paths.capturesRoot}/keylog";
      interceptionConfig = config.services.interception-tools.udevmonConfig;
      logitechMaintenance = config.systemd.user.services.logitech-maintenance;
    in
    [
      {
        assertion = builtins.elem "sinnix-resource-audit" packageNames;
        message = "sinnix-prime must expose the live resource-policy audit command";
      }
      {
        assertion =
          config.sinnix.gpu.mode == "nvidia"
          && config.hardware.nvidia.open == false
          && lib.hasInfix "NVreg_EnableGpuFirmware=0" config.boot.extraModprobeConfig;
        message = "sinnix-prime must use the proprietary NVIDIA stack with GSP firmware disabled";
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
          && transmission.bind-address-ipv6 == "::1"
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
        message = "sinnix-prime must keep machine telemetry at the normal desktop cadence";
      }
      {
        assertion =
          polylogue.enable
          && polylogue.daemon.autoStart
          && surfaces.polylogued.unit == "polylogued.service"
          && surfaces.polylogued.observe.enable
          && polylogueHm.systemd.user.services.polylogued.Install.WantedBy == [ "default.target" ];
        message = "sinnix-prime must autostart Polylogue after live-ingest repair updates";
      }
      {
        assertion =
          sinex.enable
          && sinex.autoStart
          && surfaces.sinex-runtime.unit == "sinex-runtime.target"
          && surfaces.sinex-runtime.observe.enable
          && sinexRuntimeTimerWantedBy == [ "timers.target" ];
        message = "sinnix-prime must install the delayed Sinex runtime timer";
      }
      {
        assertion =
          config.sinnix.services.lynchpin.enable
          && config.sinnix.services.lynchpin.materializationTimer.enable
          && config.systemd.services ? lynchpin-materialize
          && config.systemd.timers ? lynchpin-materialize
          && !(config.systemd.services ? lynchpin-refresh-worker)
          && !(config.systemd.timers ? lynchpin-refresh-worker);
        message = "sinnix-prime must run daily Lynchpin materialization without the legacy refresh-worker timer";
      }
      {
        assertion =
          config.services.interception-tools.enable
          && lib.hasInfix "scribe-tap" interceptionConfig
          && lib.hasInfix keylogRoot interceptionConfig
          && builtins.elem keylogRoot config.systemd.services.interception-tools.unitConfig.RequiresMountsFor
          && builtins.elem "d ${keylogRoot} 0700 ${config.sinnix.user.name} users -" config.systemd.tmpfiles.rules;
        message = "sinnix-prime keyboard interception must keep scribe-tap key capture active";
      }
      {
        assertion = logitechMaintenance.wantedBy == [ "graphical-session.target" ];
        message = "sinnix-prime Logitech maintenance must be installed, not gated off";
      }
      {
        assertion = polylogueHm.systemd.user.startServices == false;
        message = "Home Manager activation must not restart user services during live system switches";
      }
    ];
}
