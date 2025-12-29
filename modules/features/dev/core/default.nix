{
  lib,
  config,
  ...
}:
let
  cfg = config.sinnix.features.dev.core;
  user = config.sinnix.user.name;
in
{
  options.sinnix.features.dev.core = {
    enable = lib.mkEnableOption "Core Development Environment (Shell, Git, Tools)";
  };

  config = lib.mkIf cfg.enable {
    home-manager.users.${user} = { ... }: {
      imports = [
        ./base.nix
        ./git.nix
        ./htop.nix
        ./shell.nix
        ./starship.nix
      ];
    };
  };
}
