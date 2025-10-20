{
  config,
  pkgs,
  lib,
  inputs,
  secretsExportScript ? "",
  ...
}:
let
  username = "sinity";
  flakePath = "${inputs.self}";
in
{
  home = {
    username = username;
    homeDirectory = "/home/${username}";
    stateVersion = "24.05";

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
        nix-direnv-flakes
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

  programs.zsh = {
    initContent = lib.mkMerge [
      (lib.mkBefore ''
        load_secrets() {
          ${lib.optionalString (secretsExportScript != "") secretsExportScript}
        }
        load_secrets || true
      '')
    ];
    shellAliases = {
      load-secrets = "load_secrets";
    };
  };

  nix.gc = {
    automatic = true;
    dates = "weekly";
    options = "--delete-older-than 30d";
  };

  programs.home-manager.enable = true;
}
