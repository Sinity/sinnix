{ mountTmpfsRoots, baseTestConfig, ... }:
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
  assertions = _config: [ ];
}
