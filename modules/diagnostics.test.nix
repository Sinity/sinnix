{
  lib,
  mountTmpfsRoots,
  baseTestConfig,
  ...
}:
{
  name = "core-diagnostics-tools";
  modules = [
    mountTmpfsRoots
    baseTestConfig
    (
      { ... }:
      {
        networking.hostName = "diagnostics-tools-test";
        sinnix.machine.isDesktop = true;
      }
    )
  ];
  assertions = config: [
    {
      assertion = lib.any (pkg: lib.getName pkg == "sinnix-zram-reset") config.environment.systemPackages;
      message = "desktop diagnostics must install the manual zram reset command";
    }
  ];
}
