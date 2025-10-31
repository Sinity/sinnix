{
  inputs,
  lib,
  config,
  ...
}:
let
  username = config.sinnix.user.name;
  paths = config.sinnix.paths;
in
{
  config = {
    nix = {
      settings = {
        auto-optimise-store = true;
        experimental-features = [
          "nix-command"
          "flakes"
        ];
        trusted-users = [
          username
          "root"
          "@wheel"
        ];
        substituters = [
          "https://cache.nixos.org/"
          "https://sinity.cachix.org"
          "https://nix-gaming.cachix.org"
        ];
        trusted-public-keys = [
          "cache.nixos.org-1:6NCHdD59X431o0gWypbMrAURkbJ16ZPMQFGspcDShjY="
          "sinity.cachix.org-1:i5YsUuuRv9r790gdwwE+FiJiUcWULV1lEOmKE50Y+TI="
          "nix-gaming.cachix.org-1:nbjlureqMbRAxR1gJ/f3hxemL9svXaZF/Ees8vCUUs4="
        ];
        netrc-file = "/etc/nix/netrc";
        max-jobs = 4;
        cores = 0;
        allowed-users = [
          "root"
          "@wheel"
          username
        ];
      };

      daemonCPUSchedPolicy = "idle";
      daemonIOSchedClass = "idle";
      daemonIOSchedPriority = 6;

      gc = {
        automatic = true;
        dates = "weekly";
        options = "--delete-older-than 30d";
      };

      optimise = {
        automatic = true;
        dates = [ "weekly" ];
      };
    };

    nixpkgs = {
      config = {
        allowUnfree = true;
        allowAliases = true;
      };
      overlays = [ inputs.nur.overlays.default ];
    };

    services.xserver.xkb.layout = "pl";

    system.activationScripts.githubNetrc = ''
      if [ -r ${config.sinnix.secrets.paths."github-token"} ]; then
        token="$(tr -d '\r\n' < ${config.sinnix.secrets.paths."github-token"})"
        install -m 0640 -o root -g nixbld -D /dev/null /etc/nix/netrc
        printf 'machine github.com login x-access-token password %s\n' "$token" > /etc/nix/netrc
        printf 'machine api.github.com login x-access-token password %s\n' "$token" >> /etc/nix/netrc
      else
        rm -f /etc/nix/netrc
      fi
    '';

    console.keyMap = "pl2";
    console.font = "Lat2-Terminus16";
    time.timeZone = "Europe/Warsaw";
    i18n = {
      defaultLocale = "en_US.UTF-8";
      extraLocaleSettings = {
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
    };

    system.stateVersion = "24.05";

    security = {
      rtkit.enable = true;
      sudo.wheelNeedsPassword = false;
    };

    networking.firewall = {
      enable = true;
      allowedTCPPorts = [ 22 ];
      allowedUDPPortRanges = [
        {
          from = 60000;
          to = 61000;
        }
      ];
    };

    systemd.tmpfiles.rules = lib.mkAfter [
      "d ${paths.outerRealm}/inbox 0755 ${username} users -"
      "d ${paths.dataRoot} 0755 ${username} users -"
      "d ${paths.dataRoot}/screenshot 0755 ${username} users -"
    ];
  };
}
