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
    ];
}
