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
          "pipe-operators"
          "auto-allocate-uids"
          "ca-derivations"
        ];
        # Do not enable Nix cgroups while the workstation is on the simplified
        # resource-policy baseline.
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
          "hyprland.cachix.org-1:a7pgxzMz7+chwVL3/pzj6jIBMioiJM7ypFP8PwtkuGc="
          "devenv.cachix.org-1:w1cLUi8dv3hnoSPGAuibQv+f9TZLr6cv/Hm9XgU50cw="
          "nixpkgs-wayland.cachix.org-1:3lwxaILxMRkVhehr5StQprHdEo4IrE8sRho9R9HOLYA="
          "chaotic-nyx.cachix.org-1:HfnXSw4pj95iI/n17rIDy40agHj12WfF+Gqk6SonIT8="
          "numtide.cachix.org-1:2ps1kLBUWjxIneOy1Ik6cQjb41X0iXVXeHigGmycPPE="
          "nixpkgs-unfree.cachix.org-1:hqvoInulhbV4nJ9yJOEr+4wxhDV4xq2d1DK7S6Nj6rs="
        ];
        netrc-file = "/etc/nix/netrc";
        # Bound local builds so cache misses cannot fan out into many
        # full-core C++/Rust/Python derivations at once. The previous
        # max-jobs=8/cores=0 policy let each of 8 derivations see every core,
        # amplifying RAM/I/O pressure during devshell and rebuild work.
        # Benchmark future changes against wall time, peak RSS, PSI, and
        # desktop latency before raising this again.
        max-jobs = 4;
        cores = 4;
        builders-use-substitutes = true;

        # DX optimizations: keep build dependencies for faster rebuilds
        keep-outputs = true;
        keep-derivations = true;

        # Continue building unrelated derivations when one fails — avoids
        # wasting already-scheduled work on parallel build failures.
        keep-going = true;

        # Reduce warning spam for dirty git repos during development
        warn-dirty = false;

        # ── Substituter perf tuning ────────────────────────────────────────
        # Higher HTTP parallelism shaves wall-time on cold restores from
        # cache.nixos.org / cachix when many small NARs land at once.
        http-connections = 50;
        # Default connect-timeout is unbounded — a stalled cachix host can
        # block evaluation. 5s is enough for healthy caches and falls
        # through to local build quickly when one is sick.
        connect-timeout = 5;
        # Default download-attempts (5) compounds with connect-timeout when
        # multiple substituters are unreachable. 3 is enough for transient
        # blips without amplifying bad-host latency.
        download-attempts = 3;
        # Cache positive narinfo lookups longer than the default 1h — the
        # store is content-addressed so stale-positives don't exist.
        # Negative lookups stay short so a freshly-pushed path appears soon.
        narinfo-cache-positive-ttl = 86400; # 24 h
        narinfo-cache-negative-ttl = 60; # 1 min

        # Free-space pressure tuning for /nix on the 1 TB SSD: garbage
        # collect during a build when free space drops below 5 GiB, until
        # at least 50 GiB is free. Prevents ENOSPC mid-build without
        # forcing weekly-only GCs to be aggressive.
        min-free = 5368709120; # 5 GiB
        max-free = 53687091200; # 50 GiB

        # lazy-trees disabled — local nix (2.34.6) rejects the setting at
        # nix.conf validation time. Re-enable once the version supports it
        # natively. Tracked elsewhere; not blocking the urgent #581 deploy.
        # lazy-trees = true;
      };

      daemonCPUSchedPolicy = "idle";
      daemonIOSchedClass = "idle";
      daemonIOSchedPriority = 6;

      # Keep build sandbox scratch off /tmp and off /realm. /tmp is RAM-backed
      # and capped; /realm's Crucial P3 has produced NVMe write timeouts under
      # mixed build/database writeback. Root-backed /var/cache is slower, but
      # it is the stable place for disposable scratch until /realm latency is
      # no longer the active failure mode.
      extraOptions = ''
        build-dir = /var/cache/nix-build
      '';

      gc = {
        automatic = true;
        dates = "weekly";
        options = "--delete-generations +10";
      };

      # Daily store dedup runs while the GC stays weekly. Optimise is cheap
      # (re-hardlinks identical files) and keeps /nix/store tight against
      # the steady drip of new derivations from sinex/lynchpin bumps.
      optimise = {
        automatic = true;
        dates = [ "daily" ];
      };
    };

    nixpkgs = {
      config = {
        allowUnfree = true;
        allowAliases = true;
        doCheck = false;
        checkMeta = false;
      };
      hostPlatform = "x86_64-linux";
    };

    documentation.enable = lib.mkDefault false;
    documentation.info.enable = false;
    documentation.nixos.enable = false;
    programs.command-not-found.enable = false;

    environment.systemPackages = lib.mkAfter [
      pkgs.sccache
    ];

    # RUSTC_WRAPPER applies to devshell builds. Keep sccache's write-heavy,
    # disposable object store beside Nix build scratch instead of on /realm or
    # under the user's persisted XDG cache.
    environment.variables = {
      RUSTC_WRAPPER = "${pkgs.sccache}/bin/sccache";
      SCCACHE_DIR = "/var/cache/sccache";
      SCCACHE_IDLE_TIMEOUT = "300";
      SCCACHE_MAX_CACHE_SIZE = "20G";
    };

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

    # Record the flake commit that produced this generation. Surfaces via
    # `nixos-version --revision` and is read at activation time by the
    # lynchpin generation-log script so substrate can join telemetry rows
    # back to the sinnix git history. Falls through to "dirty"/"unknown"
    # if the source tree was uncommitted at build time, which is itself
    # diagnostically useful (rebuilds from local edits are visible).
    system.configurationRevision = inputs.self.rev or inputs.self.dirtyRev or "unknown";

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
      allowedUDPPortRanges = lib.optionals isDesktop [
        {
          from = 1714;
          to = 1764;
        }
      ];
    };

    systemd = {
      tmpfiles.rules = lib.mkAfter ([
        "d ${paths.realmRoot} 0755 root root -"
        "d /var/cache/nix-build 0755 root root -"
        "d /var/cache/sccache 0775 ${username} users -"
        "d /var/cache/sinex 0775 ${username} users -"
        "d ${paths.outerRealm} 0755 root root -"
        "d ${paths.outerRealm}/inbox 0755 ${username} users -"
        "d ${paths.dataRoot} 0755 root root -"
        "d ${paths.capturesRoot} 0755 root root -"
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
        "d /var/run/nscd 0755 nscd nscd -"
      ]);

      services.sinnix-root-cache-attrs = {
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
          install -d -m 0775 -o ${username} -g users /var/cache/sccache
          install -d -m 0775 -o ${username} -g users /var/cache/sinex

          chattr +C /var/cache/nix-build /var/cache/sccache /var/cache/sinex || true
        '';
      };

      services.nix-daemon = {
        requires = [ "sinnix-root-cache-attrs.service" ];
        after = [ "sinnix-root-cache-attrs.service" ];
      };
    };

    services.dbus.implementation = "broker";
    # NOTE: dbus-broker hardening removed - it needs setgroups() to drop privileges
    # for spawned services. The ~@privileged syscall filter blocked this, causing
    # crashes at boot. See: journalctl -b -3 | grep dbus-broker

    # nsncd opens its compatibility socket at /var/run/nscd/socket. On the
    # current systemd/nixpkgs generation the upstream unit bind-mounts /run/nscd
    # but still leaves the /var/run path read-only under ProtectSystem=strict,
    # causing nss-user-lookup.target to fail repeatedly during boot.
    systemd.services.nscd.serviceConfig.ReadWritePaths = [
      "/run/nscd"
      "/var/run/nscd"
    ];
  };
}
