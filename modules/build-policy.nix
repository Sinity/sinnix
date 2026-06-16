# Build and Nix daemon policy
#
# Keeps local builds bounded, cache restores parallel but not explosive, and
# write-heavy scratch on root-backed /var/cache instead of /tmp or /realm.
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
          "devenv.cachix.org-1:w1cLUi8dv3hnoSPGAuibQv+f9TZLr6cv/Hm9XgU50cw="
          "nixpkgs-wayland.cachix.org-1:3lwxaILxMRkVhehr5StQprHdEo4IrE8sRho9R9HOLYA="
          "chaotic-nyx.cachix.org-1:HfnXSw4pj95iI/n17rIDy40agHj12WfF+Gqk6SonIT8="
          "numtide.cachix.org-1:2ps1kLBUWjxIneOy1Ik6cQjb41X0iXVXeHigGmycPPE="
          "nixpkgs-unfree.cachix.org-1:hqvoInulhbV4nJ9yJOEr+4wxhDV4xq2d1DK7S6Nj6rs="
        ];
        netrc-file = "/etc/nix/netrc";

        # Keep ordinary rebuilds latency-bounded. The daemon lives in
        # nix-build.slice, but evaluation/build client memory and cache
        # substitution tails still affect the interactive session; use explicit
        # opt-in overrides for throughput experiments instead of making every
        # switch a 20-thread compile.
        max-jobs = 2;
        cores = 2;
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
        options = "--delete-generations +10";
      };

      optimise = {
        automatic = true;
        dates = [ "daily" ];
      };
    };

    # sccache is intentionally NOT wired as RUSTC_WRAPPER. The only Rust
    # consumers on this host (sinex, intercept-bounce, scribe-tap) use
    # incremental compilation for fast warm rebuilds; sccache bypasses
    # incremental and measured ~0 benefit (even slower on cold builds — see
    # sinex .agent/scratch/048). Re-add here if a non-incremental Rust workload
    # ever needs cross-checkout caching.

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
          # Place the daemon — and all build processes it spawns — into
          # nix-build.slice so the slice's CPUWeight=5/IOWeight=2 apply.
          # The daemon already carries CPUSchedulingPolicy=idle from the NixOS
          # nix module; the slice adds IO weight and the memory guard below.
          # Without this, nix-daemon lives in system.slice with no memory cap.
          Slice = "nix-build.slice";
          # Soft + hard memory ceilings: reclaim from build processes before
          # they evict desktop/video/sinexd working sets, and kill the build
          # cgroup before global pressure reaches earlyoom territory. The host
          # has 32G total but runs a large always-on terminal/browser/Postgres
          # stack, so 16G+ build residency is not operationally acceptable.
          MemoryHigh = "9G";
          MemoryMax = "14G";
          MemorySwapMax = "0";
        };
      };
    };
  };
}
