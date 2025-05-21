_: {
  imports = [
    ./network.nix
    ./security.nix
    ./services.nix
    ./system.nix
    ./user.nix
    ./nix-ld.nix
    ../service/nginx.nix
  ];
}
