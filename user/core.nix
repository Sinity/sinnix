{
  pkgs,
  lib,
  inputs,
  sinnix,
  secretsExportScript ? "",
  ...
}:
let
  username = sinnix.user.name;
  flakePath = "${inputs.self}";
  hasSecrets = secretsExportScript != "";
  secretsProfilePath = ".config/profile.d/agenix-secrets.sh";
  secretsSourceSnippet = ''if [ -f "$HOME/${secretsProfilePath}" ]; then . "$HOME/${secretsProfilePath}"; fi'';
  secretsScript = lib.optionalString hasSecrets ''
        # shellcheck shell=bash
    ${secretsExportScript}
  '';
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

    file."${secretsProfilePath}" = lib.mkIf hasSecrets {
      text = secretsScript;
    };
  };

  programs = {
    zsh = {
      initContent = lib.mkMerge [
        (lib.mkBefore (
          lib.optionalString hasSecrets ''
            ${secretsSourceSnippet}
          ''
        ))
      ];
      shellAliases = lib.optionalAttrs hasSecrets {
        load-secrets = secretsSourceSnippet;
      };
    };

    home-manager.enable = true;
  }
  // lib.optionalAttrs hasSecrets {
    bash = {
      enable = true;
      bashrcExtra = ''
        ${secretsSourceSnippet}
      '';
      profileExtra = ''
        ${secretsSourceSnippet}
      '';
    };
  };

  nix.gc = {
    automatic = true;
    dates = "weekly";
    options = "--delete-older-than 30d";
  };

}
