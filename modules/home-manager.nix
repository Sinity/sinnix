{
  inputs,
  username,
  host,
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
      inherit inputs username host;
      secretsExportScript = config.sinnix.secrets.exportScript;
    };
    users.${username} = {
      imports = [ ../user ];
      stylix.targets.vscode.enable = false;
    };
  };
}
