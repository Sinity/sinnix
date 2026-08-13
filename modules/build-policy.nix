# Build and Nix daemon policy
#
# Bounds local builds, keeps cache restores parallel, and puts write-heavy
# build scratch on root-backed /var/cache rather than /tmp or /realm.
{
  lib,
  config,
  pkgs,
  ...
}:
let
  username = config.sinnix.user.name;
in
{
  config = {
    nix = {
      settings = {
        auto-optimise-store = true;
        experimental-features = [
          "nix-command"
          "flakes"
          "fetch-tree"
        ];
        accept-flake-config = true;
        trusted-users = [
          username
          "root"
          "@wheel"
        ];
        substituters = [
          "https://sinity.cachix.org"
          "https://nix-community.cachix.org"
          "https://nix-gaming.cachix.org"
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
          "nixpkgs-wayland.cachix.org-1:3lwxaILxMRkVhehr5StQprHdEo4IrE8sRho9R9HOLYA="
          "chaotic-nyx.cachix.org-1:HfnXSw4pj95iI/n17rIDy40agHj12WfF+Gqk6SonIT8="
          "numtide.cachix.org-1:2ps1kLBUWjxIneOy1Ik6cQjb41X0iXVXeHigGmycPPE="
          "nixpkgs-unfree.cachix.org-1:hqvoInulhbV4nJ9yJOEr+4wxhDV4xq2d1DK7S6Nj6rs="
        ];
        netrc-file = "/etc/nix/netrc";

        # The overcommit guard is nix-build.slice's memory ceiling (the daemon
        # and every build it spawns run inside it — see Slice= below), not
        # these numbers.
        max-jobs = 4;
        cores = 16;
        builders-use-substitutes = true;
        keep-outputs = true;
        keep-derivations = true;
        keep-going = false;
        warn-dirty = false;

        http-connections = 16;
        max-substitution-jobs = 8;
        connect-timeout = 5;
        download-attempts = 3;
        narinfo-cache-positive-ttl = 86400;
        narinfo-cache-negative-ttl = 60;

        min-free = 5368709120;
        max-free = 53687091200;
      };

      daemonCPUSchedPolicy = "idle";
      daemonIOSchedClass = "idle";
      daemonIOSchedPriority = 6;

      extraOptions = ''
        build-dir = /var/cache/nix-build
      '';

      gc = {
        automatic = true;
        dates = "weekly";
        # `--delete-generations +N` is a nix-env flag; nix-collect-garbage
        # rejects it as an unrecognised flag and the whole run silently fails.
        options = "--delete-older-than 30d";
      };

      optimise = {
        automatic = true;
        dates = [ "daily" ];
      };
    };

    # sccache is not wired as RUSTC_WRAPPER: it bypasses incremental
    # compilation, which every Rust consumer here relies on, and measured no
    # benefit. Only worth revisiting for a non-incremental Rust workload
    # needing cross-checkout caching.

    systemd.tmpfiles.rules = lib.mkAfter [
      "d /var/cache/nix-build 0755 root root -"
      "d /var/cache/sinex 0775 ${username} users -"
    ];

    systemd.services = {
      sinnix-root-cache-attrs = {
        description = "Prepare root cache directories for write-heavy scratch";
        before = [ "nix-daemon.service" ];
        wantedBy = [ "multi-user.target" ];
        path = [
          pkgs.coreutils
          pkgs.e2fsprogs
        ];
        serviceConfig = {
          Type = "oneshot";
          RemainAfterExit = true;
        };
        script = ''
          install -d -m 0755 -o root -g root /var/cache/nix-build
          install -d -m 0775 -o ${username} -g users /var/cache/sinex

          chattr +C /var/cache/nix-build /var/cache/sinex || true
        '';
      };

      nix-daemon = {
        requires = [ "sinnix-root-cache-attrs.service" ];
        after = [ "sinnix-root-cache-attrs.service" ];
        serviceConfig = {
          # Places the daemon — and every build process it spawns — under the
          # slice's resource policy. flake/data/runtime-defaults.nix is the
          # single source of its CPU/IO weights, memory ceilings, and oomd
          # policy; do not duplicate caps here.
          Slice = "nix-build.slice";
        };
      };
    };
  };
}
