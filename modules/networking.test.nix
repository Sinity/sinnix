{ mountTmpfsRoots, baseTestConfig, ... }:
{
  name = "networking-resolved-router-authority";
  modules = [
    mountTmpfsRoots
    baseTestConfig
    (
      { ... }:
      {
        networking.hostName = "networking-test";
      }
    )
  ];
  assertions = config: [
    {
      assertion = config.networking.networkmanager.dns == "systemd-resolved";
      message = "NetworkManager must keep using systemd-resolved as the local stub";
    }
    {
      assertion = config.services.resolved.enable;
      message = "systemd-resolved must stay enabled";
    }
    {
      assertion = config.services.resolved.settings.Resolve.DNSSEC == false;
      message = "Local systemd-resolved DNSSEC must be disabled when the router is the DNS authority";
    }
    {
      assertion = config.services.resolved.settings.Resolve.FallbackDNS == "";
      message = "Local systemd-resolved fallback DNS must be disabled when the router is authoritative";
    }
  ];
}
