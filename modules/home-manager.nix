{
  inputs,
  lib,
  config,
  ...
}:
{
  imports = [ inputs.home-manager.nixosModules.home-manager ];

  options.sinnix.home.userImports = lib.mkOption {
    type = lib.types.listOf lib.types.path;
    default = [ ../user ];
    description = "Home Manager modules to import for the primary user.";
  };

  config.home-manager = {
    useUserPackages = true;
    useGlobalPkgs = true;
    backupFileExtension = "hm-bak";
    extraSpecialArgs = {
      inherit inputs;
      secretsExportScript = config.sinnix.secrets.exportScript;
      dotsPath = "${inputs.self}/dots";
      secretPaths = config.sinnix.secrets.paths;
      inherit (config) sinnix;
    };
    users."${config.sinnix.user.name}" = {
      imports = config.sinnix.home.userImports;
    };
  };
}
