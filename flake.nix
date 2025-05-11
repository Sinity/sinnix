{
  description = "Sinity's nixos configuration";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    nur.url = "github:nix-community/NUR";

    home-manager = {
      url = "github:nix-community/home-manager";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    agenix = {
      url = "github:ryantm/agenix";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    browser-previews = {
      url = "github:nix-community/browser-previews";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    intercept-bounce = {
      url = "github:sinity/intercept-bounce";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    claude-desktop = {
      url = "github:k3d3/claude-desktop-linux-flake";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = {
    nixpkgs,
    self,
    agenix,
    intercept-bounce,
    browser-previews,
    ...
  } @ inputs: let
    username = "sinity";
    system = "x86_64-linux";
  in {
    nixosConfigurations.desktop = nixpkgs.lib.nixosSystem {
      inherit system;

      modules = [
        agenix.nixosModules.default
        ./modules/core/overlays.nix
        ./modules/core/default.nix
      ];

      specialArgs = {
        host = "desktop";
        inherit self inputs username;
        intercept-bounce = inputs.intercept-bounce.packages.${system}.default;
      };
    };
  };
}
