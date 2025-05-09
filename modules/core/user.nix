{
  pkgs,
  inputs,
  username,
  host,
  ...
}: {
  imports = [inputs.home-manager.nixosModules.home-manager];
  home-manager = {
    useUserPackages = true;
    useGlobalPkgs = true;
    backupFileExtension = "backup";
    extraSpecialArgs = {inherit inputs username host;};
    users.${username} = {
      imports = [./../home/default.nix];
      home.username = "${username}";
      home.homeDirectory = "/home/${username}";
      home.stateVersion = "24.05";
      programs.home-manager.enable = true;
    };
  };

  programs.zsh.enable = true;
  users.mutableUsers = false;
  users.users.${username} = {
    isNormalUser = true;
    extraGroups = ["networkmanager" "wheel" "users" "video" "audio"];
    shell = pkgs.zsh;
    hashedPassword = "REDACTED_HASH";
  };
  nix.settings.allowed-users = ["${username}"];
  nix.settings.trusted-users = ["root" "${username}"];
  users.users.root = {
    shell = pkgs.zsh;
    home = "/root";
    hashedPassword = "REDACTED_HASH";
  };
}
