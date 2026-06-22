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
      agentGateway = config.sinnix.services.agent-gateway;
      airvpn = config.sinnix.services.airvpn-seed;
      machineTelemetry = config.sinnix.services.machine-telemetry;
      polylogue = config.sinnix.services.polylogue;
      sinex = config.sinnix.services.sinex;
      surfaces = config.sinnix.runtime.surfaces;
      transmissionService = config.systemd.services.transmission;
      firewall = config.networking.firewall;
      sinexRuntimeTimerWantedBy =
        lib.attrByPath [ "systemd" "timers" "sinex-runtime" "wantedBy" ] [ ]
          config;
      polylogueHm = config.home-manager.users.${config.sinnix.user.name};
      logitechMaintenance = config.systemd.user.services.logitech-maintenance;
    in
    [
      {
        assertion =
          agentGateway.enable
          && agentGateway.http.enable
          && builtins.elem "sinnix-agent-gateway-0.1.0" packageNames
          && builtins.elem "sinnix-agent-gateway-mcp" packageNames
          && config.home-manager.users.sinity.systemd.user.services ? sinnix-agent-gateway-http
          && config.environment.etc ? "sinnix/agent-gateway/config.json";
        message = "sinnix-prime must deploy the local agent gateway MCP surface";
      }
      {
        assertion = config.sinnix.gpu.mode == "nvidia" && config.hardware.nvidia.open == false;
        message = "sinnix-prime must use the proprietary NVIDIA stack with GSP firmware disabled";
      }
      {
        assertion = config.systemd.services ? sinnix-disable-nvme-aspm;
        message = "sinnix-prime must clear ASPM on the Crucial P3 /realm NVMe link";
      }
      {
        assertion =
          airvpn.enable
          && airvpn.autoStart == false
          && !(builtins.elem airvpn.forwardedPort firewall.allowedTCPPorts)
          && !(builtins.elem airvpn.forwardedPort firewall.allowedUDPPorts)
          && firewall.interfaces.airvpn-seed.allowedTCPPorts == [ airvpn.forwardedPort ]
          && firewall.interfaces.airvpn-seed.allowedUDPPorts == [ airvpn.forwardedPort ]
          && builtins.elem "wireguard-airvpn-seed.target" (transmissionService.wants or [ ])
          && builtins.elem "wireguard-airvpn-seed.target" (transmissionService.after or [ ]);
        message = "sinnix-prime must keep AirVPN seeding enabled while Transmission owns tunnel startup";
      }
      {
        assertion = machineTelemetry.enable;
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
          && config.systemd.services.interception-tools.unitConfig ? RequiresMountsFor;
        message = "sinnix-prime keyboard interception must keep scribe-tap key capture active";
      }
      {
        assertion = logitechMaintenance.wantedBy == [ "graphical-session.target" ];
        message = "sinnix-prime Logitech maintenance must be installed, not gated off";
      }
    ];
}
