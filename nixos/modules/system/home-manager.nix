{
  inputs,
  username,
  host,
  flakeRoot,
  projectLib,
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
      inherit
        inputs
        username
        host
        flakeRoot
        projectLib
        ;
      secretsExportScript = config.sinnix.secrets.exportScript;
      quickshellEnable = config.sinnix.interface.quickshell.enable;
    };
    users.${username} = {
      imports = [ ../../../home/profiles/sinity ];
      stylix.targets.vscode.enable = false;
    };
  };
}
