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
  resourceBudgets = import ./lib/resource-budgets.nix;
  developerBudget = resourceBudgets.developerWork;
  safeNixosRebuild = lib.hiPrio (
    pkgs.writeShellScriptBin "nixos-rebuild" ''
            set -euo pipefail

            export PATH="${
              lib.makeBinPath [
                pkgs.coreutils
                pkgs.systemd
              ]
            }:$PATH"
            rebuild_jobs="''${SINNIX_REBUILD_MAX_JOBS:-auto}"
            rebuild_cores="''${SINNIX_REBUILD_CORES:-0}"
            export NIX_CONFIG="max-jobs = $rebuild_jobs
      cores = $rebuild_cores''${NIX_CONFIG:+
      $NIX_CONFIG}"

            if [[ -z "''${SINNIX_SAFE_REBUILD_SCOPED:-}" ]] && command -v systemd-run >/dev/null 2>&1; then
              if (( EUID == 0 )); then
                exec systemd-run \
                  --scope \
                  --quiet \
                  --collect \
                  --slice=nix-build.slice \
                  -p CPUQuota=${developerBudget.cpuQuota} \
                  -p CPUWeight=${toString developerBudget.cpuWeight} \
                  -p IOWeight=${toString developerBudget.ioWeight} \
                  -p MemoryHigh=${developerBudget.memoryHigh} \
                  -p MemoryMax=${developerBudget.memoryMax} \
                  -p MemorySwapMax=${developerBudget.memorySwapMax} \
                  -p ManagedOOMMemoryPressure=${developerBudget.managedOOMMemoryPressure} \
                  -p ManagedOOMMemoryPressureLimit=${developerBudget.managedOOMMemoryPressureLimit} \
                  --setenv=SINNIX_SAFE_REBUILD_SCOPED=1 \
                  ${config.system.build.nixos-rebuild}/bin/nixos-rebuild "$@"
              elif [[ -n "''${XDG_RUNTIME_DIR:-}" ]]; then
                exec systemd-run \
                  --user \
                  --scope \
                  --quiet \
                  --collect \
                  --slice=background.slice \
                  -p CPUQuota=${developerBudget.cpuQuota} \
                  -p CPUWeight=${toString developerBudget.cpuWeight} \
                  -p IOWeight=${toString developerBudget.ioWeight} \
                  -p MemoryHigh=${developerBudget.memoryHigh} \
                  -p MemoryMax=${developerBudget.memoryMax} \
                  -p MemorySwapMax=${developerBudget.memorySwapMax} \
                  -p ManagedOOMMemoryPressure=${developerBudget.managedOOMMemoryPressure} \
                  -p ManagedOOMMemoryPressureLimit=${developerBudget.managedOOMMemoryPressureLimit} \
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
        # Use the workstation. Containment belongs to nix-build.slice, not to
        # globally serializing Nix into a low-throughput mode.
        max-jobs = "auto";
        cores = 0;
        # Keep build workers under the daemon's systemd slice so MemoryMax,
        # MemorySwapMax, CPUQuota, IOWeight, and oomd apply to the whole build
        # tree as one budget.
        use-cgroups = false;
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

      # Build sandbox scratch on the NVMe cache partition. Default would
      # land in /tmp (tmpfs, RAM-backed) which is fast but capped at half
      # of RAM — sinex's cargo workspace alone produces multi-GB target/
      # trees during nix builds. Routing TMPDIR to NVMe keeps the build
      # fast (Samsung 960 EVO ≈ 3 GB/s read, 1.5 GB/s write) while not
      # consuming RAM that the rest of the workstation needs.
      extraOptions = ''
        build-dir = /cache/nix-build
        # Shared sccache on the cache NVMe — allows Nix build sandboxes
        # to reach the Rust compilation cache.
        extra-sandbox-paths = /cache/sccache
      '';

      gc = {
        automatic = true;
        dates = "weekly";
        options = "--delete-older-than 30d";
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
      };
      hostPlatform = "x86_64-linux";
    };

    # Shadow the stock entrypoint so direct `nixos-rebuild` invocations inherit
    # the same cgroup envelope as `nix-safe` instead of running in the caller's
    # interactive scope.
    environment.systemPackages = lib.mkAfter [
      safeNixosRebuild
      pkgs.sccache
    ];

    # Rust sccache on the /cache NVMe. RUSTC_WRAPPER applies to devshell
    # builds; Nix builds opt in per-flake via extra-sandbox-paths.
    environment.variables = {
      SCCACHE_DIR = "/cache/sccache";
      RUSTC_WRAPPER = "${pkgs.sccache}/bin/sccache";
      SCCACHE_MAX_CACHE_SIZE = "20G";
      # nix-direnv eval cache — recomputed on cd into flake projects.
      # /cache NVMe makes eval-cache misses fast and avoids cluttering ~/.cache.
      NIX_DIRENV_CACHE = "/cache/nix-direnv";
      # Rust: move ~/.cargo (registry + git checkouts) to the cache NVMe.
      # sccache handles compilation artifacts; CARGO_HOME covers deps.
      CARGO_HOME = "/cache/cargo";
      # pip: move package downloads off ~/.cache to the fast scratch disk.
      PIP_CACHE_DIR = "/cache/pip";
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
        "d /cache/sccache 0755 ${username} users -"
        "d /cache/nix-direnv 0755 ${username} users -"
        "d /cache/cargo 0755 ${username} users -"
        "d /cache/pip 0755 ${username} users -"
        "d /cache/sinex 0755 ${username} users -"
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

      services.sinex-cache-prune = {
        description = "Prune stale Sinex development cache artifacts";
        serviceConfig = {
          Type = "oneshot";
          Nice = 19;
          IOSchedulingClass = "idle";
          ExecStart = pkgs.writeShellScript "sinex-cache-prune" ''
            set -euo pipefail

            cache_root="/cache/sinex"
            [ -d "$cache_root" ] || exit 0

            ${pkgs.findutils}/bin/find "$cache_root" -xdev -type f -mtime +2 -delete
            ${pkgs.findutils}/bin/find "$cache_root" -xdev -mindepth 1 -type d -empty -delete
          '';
        };
      };

      timers.sinex-cache-prune = {
        wantedBy = [ "timers.target" ];
        timerConfig = {
          OnCalendar = "daily";
          Persistent = false;
          RandomizedDelaySec = "30m";
        };
      };
    };

    services.dbus.implementation = "broker";
    # NOTE: dbus-broker hardening removed - it needs setgroups() to drop privileges
    # for spawned services. The ~@privileged syscall filter blocked this, causing
    # crashes at boot. See: journalctl -b -3 | grep dbus-broker
  };
}
