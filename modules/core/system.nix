{ self, pkgs, lib, inputs, username, ...}: 
{
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
    nix-output-monitor
    nvd
  ];

  programs.nh = {
    enable = true;
    clean = {
      enable = true;
      extraArgs = "--keep-since 7d --keep 5";
    };
    flake = "/home/${username}/workdir/nixos-config";
  };

  programs.nix-ld.enable = true;
  # programs.nix-ld.libraries = with pkgs; [];
  services.dbus.enable = true;

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

  services.earlyoom = {
    enable = true;
    enableNotifications = true;
    freeMemThreshold = 5;
    freeSwapThreshold = 5;
    reportInterval = 5;
    extraArgs = [
      "-g" # kill entire process groups
     	"-p" # set earlyoom niceness to -20
      "--prefer '(^|/)(java|chromium|floorp)$'"
      "--avoid '(^|/)(init|systemd|sshd)$'"
    ];
  };

  nixpkgs.config.allowUnfree = true;
  system.stateVersion = "24.05";
}
