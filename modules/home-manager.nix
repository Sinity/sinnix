{
  inputs,
  lib,
  config,
  ...
}:
{
  imports = [ inputs.home-manager.nixosModules.home-manager ];

  config.home-manager = {
    useUserPackages = true;
    useGlobalPkgs = true;
    backupFileExtension = "backup";
    extraSpecialArgs = {
      inherit inputs;
      secretsExportScript = config.sinnix.secrets.exportScript;
      dotsPath = "${inputs.self}/dots";
      secretPaths = config.sinnix.secrets.paths;
    };
    users.sinity = {
      imports = [ ../user ];
    };
  };
}
