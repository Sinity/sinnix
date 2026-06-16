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
]
