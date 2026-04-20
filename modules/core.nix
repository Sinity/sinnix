# Core Nix Configuration
#
# Nix daemon settings, binary caches, build parallelism,
# GC, store optimization, security, firewall base config.
{
  inputs,
  lib,
  config,
  pkgs,
  ...
}:
let
  username = config.sinnix.user.name;
  inherit (config.sinnix) paths;
  inherit (config.sinnix.machine) isDesktop;
  safeNixosRebuild = lib.hiPrio (
    pkgs.writeShellScriptBin "nixos-rebuild" ''
      set -euo pipefail

      export PATH="${lib.makeBinPath [ pkgs.coreutils pkgs.systemd ]}:$PATH"

      if [[ -z "''${SINNIX_SAFE_REBUILD_SCOPED:-}" ]] && command -v systemd-run >/dev/null 2>&1; then
        if (( EUID == 0 )); then
          exec systemd-run \
            --scope \
            --quiet \
            --collect \
            --slice=nix-build.slice \
            -p CPUWeight=20 \
            -p IOWeight=50 \
            -p MemoryHigh=18G \
            -p MemoryMax=20G \
            -p MemorySwapMax=0 \
            -p ManagedOOMMemoryPressure=kill \
            -p ManagedOOMMemoryPressureLimit=50% \
            --setenv=SINNIX_SAFE_REBUILD_SCOPED=1 \
            ${config.system.build.nixos-rebuild}/bin/nixos-rebuild "$@"
        elif [[ -n "''${XDG_RUNTIME_DIR:-}" ]]; then
          exec systemd-run \
            --user \
            --scope \
            --quiet \
            --collect \
            --slice=background.slice \
            -p CPUWeight=20 \
            -p IOWeight=50 \
            -p MemoryHigh=18G \
            -p MemoryMax=20G \
            -p MemorySwapMax=0 \
            -p ManagedOOMMemoryPressure=kill \
            -p ManagedOOMMemoryPressureLimit=50% \
            --setenv=SINNIX_SAFE_REBUILD_SCOPED=1 \
            ${config.system.build.nixos-rebuild}/bin/nixos-rebuild "$@"
        fi
      fi

      exec ${config.system.build.nixos-rebuild}/bin/nixos-rebuild "$@"
    ''
  );
in
{
  config = {
    nix = {
      settings = {
        auto-optimise-store = true;
        experimental-features = [
          "nix-command"
          "flakes"
          "cgroups"
        ];
        accept-flake-config = true;
        trusted-users = [
          username
          "root"
          "@wheel"
        ];
        substituters = [
          "https://cache.nixos.org/"
          "https://sinity.cachix.org"
          "https://nix-community.cachix.org"
          "https://nix-gaming.cachix.org"
          "https://cuda-maintainers.cachix.org"
          "https://hyprland.cachix.org"
          "https://devenv.cachix.org"
          "https://nixpkgs-wayland.cachix.org"
          "https://chaotic-nyx.cachix.org"
          "https://numtide.cachix.org"
          "https://nixpkgs-unfree.cachix.org"
        ];
        trusted-public-keys = [
          "cache.nixos.org-1:6NCHdD59X431o0gWypbMrAURkbJ16ZPMQFGspcDShjY="
          "sinity.cachix.org-1:i5YsUuuRv9r790gdwwE+FiJiUcWULV1lEOmKE50Y+TI="
          "nix-community.cachix.org-1:mB9FSh9qf2dCimDSUo8Zy7bkq5CX+/rkCWyvRCYg3Fs="
          "nix-gaming.cachix.org-1:nbjlureqMbRAxR1gJ/f3hxemL9svXaZF/Ees8vCUUs4="
          "cuda-maintainers.cachix.org-1:0dq3bujKpuEPMCX6U4WylrUDZ9JyUG0VpVZa7CNfq5E="
          "hyprland.cachix.org-1:a7pgxzMz7+chwVL3/pzj6jIBMioiJM7ypFP8PwtkuGc="
          "devenv.cachix.org-1:w1cLUi8dv3hnoSPGAuibQv+f9TZLr6cv/Hm9XgU50cw="
          "nixpkgs-wayland.cachix.org-1:3lwxaILxMRkVhehr5StQprHdEo4IrE8sRho9R9HOLYA="
          "chaotic-nyx.cachix.org-1:HfnXSw4pj95iI/n17rIDy40agHj12WfF+Gqk6SonIT8="
          "numtide.cachix.org-1:2ps1kLBUWjxIneOy1Ik6cQjb41X0iXVXeHigGmycPPE="
          "nixpkgs-unfree.cachix.org-1:hqvoInulhbV4nJ9yJOEr+4wxhDV4xq2d1DK7S6Nj6rs="
        ];
        netrc-file = "/etc/nix/netrc";
        # Let Nix use the machine normally; interactive protection lives in the
        # dedicated build slice and systemd-oomd policy, not in a hardcoded
        # workstation-wide job/core throttle.
        max-jobs = "auto";
        cores = 0;
        # Let the systemd-managed nix-build/background slices be the only cgroup
        # authority. With Nix's own builder cgroups enabled, the heavy build
        # workers escape the slice budget and only the daemon itself stays
        # constrained, which defeats the desktop protection model.
        use-cgroups = false;
        builders-use-substitutes = true;

        # DX optimizations: keep build dependencies for faster rebuilds
        keep-outputs = true;
        keep-derivations = true;

        # Reduce warning spam for dirty git repos during development
        warn-dirty = false;
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
      hostPlatform = "x86_64-linux";
    };

    # Shadow the stock entrypoint so direct `nixos-rebuild` invocations inherit
    # the same cgroup envelope as `nix-safe` instead of running in the caller's
    # interactive scope.
    environment.systemPackages = lib.mkAfter [ safeNixosRebuild ];

    services.xserver.xkb.layout = "pl";

    system.activationScripts.githubNetrc = lib.mkIf config.sinnix.secrets.enable ''
      if [ -r ${config.sinnix.secrets.paths."github-token"} ]; then
        token="$(tr -d '\r\n' < ${config.sinnix.secrets.paths."github-token"})"
        install -m 0640 -o root -g nixbld -D /dev/null /etc/nix/netrc
        printf 'machine github.com login x-access-token password %s\n' "$token" > /etc/nix/netrc
        printf 'machine api.github.com login x-access-token password %s\n' "$token" >> /etc/nix/netrc
      else
        rm -f /etc/nix/netrc
      fi
    '';

    system.stateVersion = "24.05";

    security = {
      rtkit.enable = true;
      sudo.wheelNeedsPassword = false;
    };

    networking.firewall = {
      enable = true;
      allowPing = true;
      allowedTCPPorts = [ 22 ];
      allowedTCPPortRanges = lib.optionals isDesktop [
        {
          from = 1714;
          to = 1764;
        }
      ];
      allowedUDPPortRanges = [
        {
          from = 60000;
          to = 61000;
        }
      ]
      ++ lib.optionals isDesktop [
        {
          from = 1714;
          to = 1764;
        }
      ];
    };

    systemd = {
      tmpfiles.rules = lib.mkAfter ([
        "d ${paths.realmRoot} 0755 root root -"
        "d ${paths.outerRealm} 0755 root root -"
        "d ${paths.neoOuterRealm} 0755 root root -"
        "d ${paths.outerRealm}/inbox 0755 ${username} users -"
        "d ${paths.dataRoot} 0755 ${username} users -"
        "d ${paths.capturesRoot} 0755 ${username} users -"
        "d ${paths.capturesRoot}/shell 0755 ${username} users -"
        "d ${paths.capturesRoot}/shell/zsh 0700 ${username} users -"
        "d ${paths.capturesRoot}/comms 0755 ${username} users -"
        "d ${paths.capturesRoot}/comms/irc 0755 ${username} users -"
        "d ${paths.exportsRoot} 0755 ${username} users -"
        "d ${paths.librariesRoot} 0755 ${username} users -"
        "d ${paths.capturesRoot}/activitywatch 0755 ${username} users -"
        "d ${paths.capturesRoot}/activitywatch/raw 0755 ${username} users -"
        "d ${paths.capturesRoot}/audio 0755 ${username} users -"
        "d ${paths.capturesRoot}/audio/raw 0755 ${username} users -"
        "d ${paths.capturesRoot}/audio/archive 0755 ${username} users -"
        "d ${paths.capturesRoot}/asciinema 0755 ${username} users -"
        "d ${paths.capturesRoot}/keylog 0700 ${username} users -"
        "d ${paths.capturesRoot}/screenshot 0755 ${username} users -"
        "d ${paths.capturesRoot}/screenshot/mpv 0755 ${username} users -"
        "d ${paths.exportsRoot}/lastpass 0755 ${username} users -"
        "d ${paths.exportsRoot}/lastpass/raw 0755 ${username} users -"
      ]);
    };

    services.dbus.implementation = "broker";
    # NOTE: dbus-broker hardening removed - it needs setgroups() to drop privileges
    # for spawned services. The ~@privileged syscall filter blocked this, causing
    # crashes at boot. See: journalctl -b -3 | grep dbus-broker
  };
}
