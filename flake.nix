{
  description = "Sinity's nixos configuration";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    nur.url = "github:nix-community/NUR";

    hypr-contrib.url = "github:hyprwm/contrib";
    hyprpicker.url = "github:hyprwm/hyprpicker";

    alejandra.url = "github:kamadorueda/alejandra/3.0.0";

    nix-gaming.url = "github:fufexan/nix-gaming";

    home-manager = {
      url = "github:nix-community/home-manager";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    nvchad4nix = {
      url = "github:nix-community/nix4nvchad";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    agenix = {
      url = "github:ryantm/agenix";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    crane = {
      url = "github:ipetkov/crane";
      # Remove the follows line as it causes a warning if crane doesn't declare nixpkgs
      # inputs.nixpkgs.follows = "nixpkgs";
    };

    # Add the intercept-bounce flake as an input
    intercept-bounce = {
      url = "github:sinity/intercept-bounce"; # Assuming it's hosted here
      inputs.nixpkgs.follows = "nixpkgs"; # Ensure it uses the same nixpkgs
    };
  };

  outputs = {
    nixpkgs,
    crane,
    self,
    agenix,
    intercept-bounce, # Add intercept-bounce to the arguments here
    ...
  } @ inputs: let
    username = "sinity";
    system = "x86_64-linux";
  in {
    nixosConfigurations.desktop = nixpkgs.lib.nixosSystem {
      inherit system;
      modules = [
        ./modules/core/default.nix
        agenix.nixosModules.default
        # Import the module from the intercept-bounce flake here
        # Access the module via the system attribute set
        inputs.intercept-bounce.nixosModules.${system}.intercept-bounce # Use inputs.intercept-bounce here
      ];
      specialArgs = {
        host = "desktop";
        inherit self inputs username;
        # Pass the intercept-bounce package derivation to modules
        # Use .default if that's the main package
        intercept-bounce = inputs.intercept-bounce.packages.${system}.default;
      };
    };

    # Expose packages for the specified system
    packages.${system} = let
      pkgs = nixpkgs.legacyPackages.${system};
      # Access crane explicitly via the 'inputs' argument
      craneLib = inputs.crane.lib.${system};
    in {
      # Define the screen-pipe package using the default.nix file
      # Ensure the source code for screen-pipe v0.2.74 and the Cargo.lock
      # are located within the ./screenpipe-0.2.74 directory.
      screen-pipe = pkgs.callPackage ./screenpipe-0.2.74/default.nix {
        inherit pkgs craneLib;
      };

      # You can add other packages here if needed
      # default = self.packages.${system}.screen-pipe; # Optionally set a default package
    };

    # You might want a default package for `nix build`
    # defaultPackage.${system} = self.packages.${system}.screen-pipe;
  };
}
