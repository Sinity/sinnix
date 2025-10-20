{
  inputs,
  lib,
  config,
  ...
}:
let
  username = "sinity";
in
{
  imports = [ inputs.home-manager.nixosModules.home-manager ];

  config.home-manager = {
    useUserPackages = true;
    useGlobalPkgs = true;
    backupFileExtension = "backup";
    extraSpecialArgs = {
      inherit inputs;
      username = "sinity";
      secretsExportScript = config.sinnix.secrets.exportScript;
      dotsPath = "${inputs.self}/dots";
      secretPaths = config.sinnix.secrets.paths;
    };
    users.${username} = {
      imports = [ ../user ];
    };
  };
}
