{ inputs, ... }:
{
  name = "host-sinnix-prime-observability-policy";
  modules = [
    { imports = [ (inputs.self + "/hosts/sinnix-prime") ]; }
  ];
  assertions = config: [
    {
      assertion =
        !(config.systemd.services ? sinnix-sentinel) && !(config.systemd.timers ? sinnix-sentinel);
      message = "sinnix-prime must not run the scan-heavy sentinel loop as a background timer";
    }
  ];
}
