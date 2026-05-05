{
  mountTmpfsRoots,
  baseTestConfig,
  hmFor,
  ...
}:
[
  {
    name = "minimal-no-features";
    modules = [
      mountTmpfsRoots
      baseTestConfig
      (
        { ... }:
        {
          networking.hostName = "minimal";
          sinnix.bundles.dev.enable = false;
        }
      )
    ];
    assertions =
      config:
      let
        hm = hmFor config;
      in
      [
        {
          assertion = !(hm.programs.starship.enable or false);
          message = "Starship should not be enabled in minimal";
        }
        {
          assertion = !(config.services.transmission.enable or false);
          message = "Transmission should not be enabled in minimal";
        }
      ];
  }
  {
    name = "paths-configured";
    modules = [
      mountTmpfsRoots
      baseTestConfig
      (
        { ... }:
        {
          networking.hostName = "paths-test";
        }
      )
    ];
    assertions = config: [
      {
        assertion = config.sinnix.paths.realmRoot == "/realm";
        message = "realmRoot must be /realm";
      }
      {
        assertion = config.sinnix.paths.dataRoot == "/realm/data";
        message = "dataRoot must be /realm/data";
      }
      {
        assertion = config.sinnix.paths.capturesRoot == "/realm/data/captures";
        message = "capturesRoot must be correct";
      }
      {
        assertion = config.sinnix.user.name == "sinity";
        message = "Default user must be sinity";
      }
    ];
  }
]
