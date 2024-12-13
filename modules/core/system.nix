{ self, pkgs, lib, inputs, ...}: 
{
  # imports = [ inputs.nix-gaming.nixosModules.default ];
  nix = {
    settings = {
      auto-optimise-store = true;
      experimental-features = [ "nix-command" "flakes" ];
      substituters = [ "https://nix-gaming.cachix.org" ];
      trusted-public-keys = [ "nix-gaming.cachix.org-1:nbjlureqMbRAxR1gJ/f3hxemL9svXaZF/Ees8vCUUs4=" ];
    };
  };
  nixpkgs = {
    config = {
      allowUnfreePredicate = pkg: builtins.elem (lib.getName pkg) [
        "discord"
        "spotify"
        "obsidian"
      ];
      permittedInsecurePackages = [
        "electron-25.9.0" # obsidian
      ];
    };
    overlays = [
      inputs.nur.overlays.default
    ];
  };

  environment.systemPackages = with pkgs; [
    wget
    git
  ];

  # locale
  services.xserver.xkb.layout = "pl";
  console.keyMap = "pl2";
  console.font = "Lat2-Terminus16";
  time.timeZone = "Europe/Warsaw";
  i18n.defaultLocale = "en_US.UTF-8";
  i18n.extraLocaleSettings = {
    LC_ADDRESS = "pl_PL.UTF-8";
    LC_IDENTIFICATION = "pl_PL.UTF-8";
    LC_MEASUREMENT = "pl_PL.UTF-8";
    LC_MONETARY = "pl_PL.UTF-8";
    LC_NAME = "pl_PL.UTF-8";
    LC_NUMERIC = "pl_PL.UTF-8";
    LC_PAPER = "pl_PL.UTF-8";
    LC_TELEPHONE = "pl_PL.UTF-8";
    LC_TIME = "pl_PL.UTF-8";
  };

  nixpkgs.config.allowUnfree = true;
  system.stateVersion = "24.05";
}
