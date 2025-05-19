{
  pkgs,
  inputs,
  username,
  host,
  ...
}:
{
  imports = [ inputs.home-manager.nixosModules.home-manager ];
  home-manager = {
    useUserPackages = true;
    useGlobalPkgs = true;
    backupFileExtension = "backup";
    extraSpecialArgs = { inherit inputs username host; };
    users.${username} = {
      imports = [ ./../home/default.nix ];
      home = {
        username = "${username}";
        homeDirectory = "/home/${username}";
        stateVersion = "24.05";
      };
      programs.home-manager.enable = true;
    };
  };

  programs.zsh.enable = true;
  
  # User configuration
  users = {
    mutableUsers = false;
    users = {
      ${username} = {
        isNormalUser = true;
        extraGroups = [
          "networkmanager"
          "wheel"
          "users"
          "video"
        ];
        shell = pkgs.zsh;
        hashedPassword = "REDACTED_HASH";
      };
      root = {
        shell = pkgs.zsh;
        home = "/root";
        hashedPassword = "REDACTED_HASH";
      };
    };
  };
  
  # Nix settings
  nix.settings = {
    allowed-users = [ "${username}" ];
    trusted-users = [
      "root"
      "${username}"
    ];
  };
}
