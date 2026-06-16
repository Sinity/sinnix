{ mountTmpfsRoots, baseTestConfig, ... }:
{
  name = "core-performance-policy";
  modules = [
    mountTmpfsRoots
    baseTestConfig
  ];
  assertions = _config: [ ];
}
