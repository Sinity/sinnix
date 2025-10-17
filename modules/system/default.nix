{ ... }:
{
  imports = [
    ./core.nix
    ./programs.nix
    ./logging.nix
    ./secrets.nix
    ./home-manager.nix
    ./users.nix
    ./access-tokens.nix
    ./interception.nix
  ];
}
