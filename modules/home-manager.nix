# Home Manager Integration
#
# Imports HM module, configures extraSpecialArgs, sets up
# primary user home with XDG paths and state version.
{
  inputs,
  lib,
  config,
  helpers,
  ...
}:
let
  user = config.sinnix.user.name;
  flakePath = config.sinnix.paths.projectRoot;
in
{
  imports = [ inputs.home-manager.nixosModules.home-manager ];

  options.sinnix.home.userImports = lib.mkOption {
    type = lib.types.listOf lib.types.path;
    default = [ ];
    description = "Additional Home Manager modules to import for the primary user.";
  };

  config.home-manager = {
    useUserPackages = true;
    useGlobalPkgs = true;
    backupFileExtension = null;
    extraSpecialArgs = {
      inherit inputs helpers;
      dotsRepoPath = config.sinnix.paths.dotsRoot;
      secretPaths = config.sinnix.secrets.paths;
      inherit (config) sinnix;
      # Pre-bound mkDotsFile helper - modules just need: let mkDotsFile = mkDotsFileFor config;
      mkDotsFileFor = helpers.mkDotsFileFor config.sinnix;
    };
    users."${user}" = {
      imports = config.sinnix.home.userImports;

      home = {
        username = user;
        homeDirectory = "/home/${user}";
        inherit (config.system) stateVersion;
        sessionPath = [ "$HOME/.local/bin" ];
        sessionVariables = {
          FLAKE = flakePath;
          XDG_CONFIG_HOME = "\${HOME}/.config";
          XDG_CACHE_HOME = "\${HOME}/.cache";
          XDG_DATA_HOME = "\${HOME}/.local/share";
          XDG_STATE_HOME = "\${HOME}/.local/state";
        };
      };

      programs.home-manager.enable = true;
      systemd.user.startServices = "suggest";
    };
  };
}
