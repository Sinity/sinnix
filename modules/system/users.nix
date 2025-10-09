{ pkgs, username, ... }:
{
  config = {
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
            "wireshark"
          ];
          shell = pkgs.zsh;
          hashedPasswordFile = "/run/agenix/sinity-password";
        };
        root = {
          shell = pkgs.zsh;
          home = "/root";
          hashedPasswordFile = "/run/agenix/root-password";
        };
      };
    };
  };
}
