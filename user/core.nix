{
  pkgs,
  lib,
  inputs,
  sinnix,
  ...
}:
let
  username = sinnix.user.name;
  flakePath = "${sinnix.paths.projectRoot}";
in
{
  home = {
    inherit username;
    homeDirectory = "/home/${username}";
    stateVersion = "24.05";

    # Ensure user-local scripts are discoverable by default
    sessionPath = [ "$HOME/.local/bin" ];

    sessionVariables = {
      FLAKE = flakePath;
      XDG_CONFIG_HOME = "\${HOME}/.config";
      XDG_CACHE_HOME = "\${HOME}/.cache";
      XDG_DATA_HOME = "\${HOME}/.local/share";
      XDG_STATE_HOME = "\${HOME}/.local/state";
    };

    packages = lib.mkAfter (
      with pkgs;
      [
        nix-output-monitor
        nvd
        cachix
        nix-direnv
        killall
        procps
        psmisc
        iotop
        entr
        file
        tldr
        xdg-utils
        xxd
        graphicsmagick
      ]
    );
  };

  programs.home-manager.enable = true;

  nix.gc = {
    automatic = true;
    dates = "weekly";
    options = "--delete-older-than 30d";
  };

}
