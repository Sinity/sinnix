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
    ];
}
