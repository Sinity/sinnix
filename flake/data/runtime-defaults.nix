{ lib }:
let
  mkClass = description: serviceConfig: {
    inherit description serviceConfig;
  };

  surfaceType = surface: if surface.manager == "user" then "user" else surface.kind;

  normalizeSurface =
    surface:
    {
      manager = "system";
      kind = "service";
      resourceClass = "system";
      observe = {
        enable = false;
        restartable = false;
      };
      captures = [ ];
    }
    // surface;

  captureRows =
    surfaces:
    lib.concatLists (
      lib.mapAttrsToList (
        _name: surface:
        map (
          capture:
          {
            inherit (capture) name path;
          }
          // lib.optionalAttrs (capture.cadenceSeconds != null) {
            expectedCadenceSeconds = capture.cadenceSeconds;
          }
          // lib.optionalAttrs capture.eventDriven {
            expectedCadence = "event-driven";
          }
        ) surface.captures
      ) (lib.mapAttrs (_: normalizeSurface) surfaces)
    );

  observedServiceRows =
    surfaces:
    lib.mapAttrsToList
      (name: surface: {
        inherit name;
        inherit (surface)
          kind
          manager
          resourceClass
          unit
          ;
        type = surfaceType surface;
        restartable = surface.observe.restartable;
      })
      (
        lib.filterAttrs (_: surface: surface.observe.enable) (lib.mapAttrs (_: normalizeSurface) surfaces)
      );
in
rec {
  # Global earlyoom is only the last-resort floor. Per-scope cgroups own
  # workload containment; this process-name fallback protects only surfaces
  # needed to keep or recover the graphical/login session. Agents, language
  # runtimes, browsers, and generic shells deliberately remain eligible.
  earlyoomEmergencyAvoidPattern =
    "(systemd|systemd-logind|dbus-daemon|dbus-broker|dbus-broker-launch|sshd|agetty|uwsm|start-hyprland|Hyprland|Xwayland|noctalia|quickshell|xdg-desktop-po|pipewire|wireplumber|foot|kitty|below|nix-daemon)";

  classes = {
    interactive-agent = mkClass "Interactive AI agent shells and frontends" { };
    interactive-access = mkClass "Login, SSH, and input services needed to regain control" {
      Slice = "system-critical.slice";
      Nice = -5;
      IOSchedulingClass = "best-effort";
      IOSchedulingPriority = 0;
    };
    developer-build = mkClass "User-initiated builds, tests, and Nix work" { };
    background-maintenance = mkClass "Bulk maintenance that should yield to interaction" {
      Nice = 10;
      IOSchedulingClass = "idle";
      CPUWeight = 5;
      IOWeight = 5;
      MemoryHigh = "1G";
      MemoryMax = "3G";
    };
    backup-maintenance = mkClass "Snapshot and backup jobs" {
      Slice = "background.slice";
      Nice = 10;
      CPUSchedulingPolicy = "idle";
      IOSchedulingClass = "idle";
      CPUWeight = 20;
      IOWeight = 20;
      MemoryHigh = "2G";
      MemoryMax = "4G";
      IOReadBandwidthMax = [
        "/persist 40M"
        "/realm 80M"
        "/outer-realm 40M"
      ];
      IOWriteBandwidthMax = [
        "/persist 20M"
        "/realm 40M"
        "/outer-realm 40M"
      ];
    };
    capture-runtime = mkClass "Long-running capture daemons" {
      Nice = 10;
      IOSchedulingClass = "idle";
      IOWeight = 10;
      MemoryHigh = "6G";
      MemoryMax = "8G";
    };
    capture-substrate = mkClass "Databases and queues backing capture daemons" {
      Nice = 8;
      IOSchedulingClass = "best-effort";
      IOSchedulingPriority = 7;
      IOWeight = 20;
      MemoryHigh = "8G";
    };
    observability = mkClass "Monitoring that should remain responsive during contention" {
      Slice = "system-critical.slice";
      Nice = -5;
      IOSchedulingClass = "best-effort";
      IOSchedulingPriority = 0;
    };
    system = mkClass "Ordinary system services without Sinnix-specific placement" { };
  };

  commandClasses = {
    agent = {
      resourceClass = "interactive-agent";
      slice = "agent.slice";
      nice = null;
      ioniceClass = null;
      ionicePriority = null;
      systemdProperties = {
        IOAccounting = true;
        IOWeight = 300;
        # Bound each transient agent independently. A runaway tool child must
        # sacrifice only its owning agent scope before global earlyoom starts
        # selecting desktop processes. Keep agent.slice itself uncapped: the
        # 2026-06-18 shared ceiling coupled every interactive session and
        # froze healthy agents behind one busy peer.
        MemoryHigh = "8G";
        MemoryMax = "12G";
      };
      envDefaults = { };
    };
    build = {
      resourceClass = "developer-build";
      slice = "build.slice";
      nice = 5;
      ioniceClass = "best-effort";
      ionicePriority = 7;
      systemdProperties = {
        IOAccounting = true;
        IOWeight = 2;
        # Shutdown debris cap (2026-07-10 reboot postmortem): leftover
        # sacrificial scopes (e.g. per-checkout sinex dev-postgres in
        # nix-build scopes) each burned the full 90s DefaultTimeoutStopSec
        # serially during reboot, and held /var/lib/sinex + /var/cache/sinex
        # mounts busy past their unmount attempts. Sacrificial work gets 15s
        # after SIGTERM, then SIGKILL; postgres/rustc state here is
        # regenerable by design.
        TimeoutStopSec = "15s";
      };
      envDefaults = {
        # Matches the single-job/16-core nix rebuild policy (build-policy.nix,
        # SINNIX_REBUILD_CORES): one heavy build gets the full physical core
        # count instead of splitting budget across concurrent jobs.
        CARGO_BUILD_JOBS = "16";
        # Deliberately NOT set: CARGO_INCREMENTAL=0 contradicted
        # build-policy.nix's sccache rationale (incremental compilation is
        # why this host doesn't wire sccache as RUSTC_WRAPPER). No measured
        # reason for disabling it turned up in history — it was added
        # mechanically alongside a job-count bump. Removed 2026-07-06.
        CMAKE_BUILD_PARALLEL_LEVEL = "16";
        MAKEFLAGS = "-j16";
        NIX_BUILD_CORES = "16";
        SCCACHE_IDLE_TIMEOUT = "10";
      };
    };
    background = {
      resourceClass = "background-maintenance";
      slice = "background.slice";
      nice = 10;
      ioniceClass = "idle";
      ionicePriority = null;
      systemdProperties = {
        IOAccounting = true;
        IOWeight = 1;
        # Shutdown debris cap (2026-07-10 reboot postmortem): leftover
        # sacrificial scopes (e.g. per-checkout sinex dev-postgres in
        # nix-build scopes) each burned the full 90s DefaultTimeoutStopSec
        # serially during reboot, and held /var/lib/sinex + /var/cache/sinex
        # mounts busy past their unmount attempts. Sacrificial work gets 15s
        # after SIGTERM, then SIGKILL; postgres/rustc state here is
        # regenerable by design.
        TimeoutStopSec = "15s";
      };
      envDefaults = { };
    };
    nix-build = {
      resourceClass = "developer-build";
      slice = "nix-build.slice";
      nice = 10;
      ioniceClass = "idle";
      ionicePriority = null;
      systemdProperties = {
        IOAccounting = true;
        IOWeight = 2;
        # Shutdown debris cap (2026-07-10 reboot postmortem): leftover
        # sacrificial scopes (e.g. per-checkout sinex dev-postgres in
        # nix-build scopes) each burned the full 90s DefaultTimeoutStopSec
        # serially during reboot, and held /var/lib/sinex + /var/cache/sinex
        # mounts busy past their unmount attempts. Sacrificial work gets 15s
        # after SIGTERM, then SIGKILL; postgres/rustc state here is
        # regenerable by design.
        TimeoutStopSec = "15s";
      };
      envDefaults = { };
    };
  };

  slices = {
    system = {
      background = {
        CPUWeight = 3;
        IOWeight = 1;
        MemoryHigh = "2G";
        MemoryMax = "4G";
        # PSI-scoped oomd (sinnix-3gb): sacrificial work is killed at cgroup
        # granularity when ITS OWN memory pressure stalls it, instead of
        # letting global earlyoom pick victims. 50%/30s (not the 10%/5s
        # defaults) so only a genuinely wedged scope dies, not a busy one.
        ManagedOOMMemoryPressure = "kill";
        ManagedOOMMemoryPressureLimit = "50%";
        ManagedOOMMemoryPressureDurationSec = "30s";
      };
      nix-build = {
        CPUWeight = 5;
        IOWeight = 2;
        # Rust workspaces and NixOS rebuilds should use the workstation, while
        # still leaving room for the desktop and always-on data services.
        MemoryHigh = "22G";
        MemoryMax = "28G";
        # PSI-scoped oomd (sinnix-3gb): sacrificial work is killed at cgroup
        # granularity when ITS OWN memory pressure stalls it, instead of
        # letting global earlyoom pick victims. 50%/30s (not the 10%/5s
        # defaults) so only a genuinely wedged scope dies, not a busy one.
        ManagedOOMMemoryPressure = "kill";
        ManagedOOMMemoryPressureLimit = "50%";
        ManagedOOMMemoryPressureDurationSec = "30s";
      };
      system-critical = {
        IOAccounting = true;
        CPUWeight = 400;
        IOWeight = 300;
        MemoryLow = "2G";
      };
    };
    user = {
      agent = {
        IOAccounting = true;
        CPUWeight = 400;
        IOWeight = 300;
        MemoryLow = "3G";
      };
      app = {
        IOAccounting = true;
        IOWeight = 300;
      };
      session = {
        IOAccounting = true;
        IOWeight = 300;
      };
      backup = {
        IOAccounting = true;
        CPUWeight = 20;
        IOWeight = 20;
        MemoryHigh = "8G";
        MemoryMax = "12G";
      };
      background = {
        IOAccounting = true;
        CPUWeight = 3;
        IOWeight = 1;
        MemoryHigh = "2G";
        MemoryMax = "4G";
        # PSI-scoped oomd (sinnix-3gb): sacrificial work is killed at cgroup
        # granularity when ITS OWN memory pressure stalls it, instead of
        # letting global earlyoom pick victims. 50%/30s (not the 10%/5s
        # defaults) so only a genuinely wedged scope dies, not a busy one.
        ManagedOOMMemoryPressure = "kill";
        ManagedOOMMemoryPressureLimit = "50%";
        ManagedOOMMemoryPressureDurationSec = "30s";
      };
      build = {
        IOAccounting = true;
        CPUWeight = 5;
        IOWeight = 2;
        MemoryHigh = "22G";
        MemoryMax = "28G";
        # PSI-scoped oomd (sinnix-3gb): sacrificial work is killed at cgroup
        # granularity when ITS OWN memory pressure stalls it, instead of
        # letting global earlyoom pick victims. 50%/30s (not the 10%/5s
        # defaults) so only a genuinely wedged scope dies, not a busy one.
        ManagedOOMMemoryPressure = "kill";
        ManagedOOMMemoryPressureLimit = "50%";
        ManagedOOMMemoryPressureDurationSec = "30s";
      };
      nix-build = {
        IOAccounting = true;
        CPUWeight = 5;
        IOWeight = 2;
        MemoryHigh = "22G";
        MemoryMax = "28G";
        # PSI-scoped oomd (sinnix-3gb): sacrificial work is killed at cgroup
        # granularity when ITS OWN memory pressure stalls it, instead of
        # letting global earlyoom pick victims. 50%/30s (not the 10%/5s
        # defaults) so only a genuinely wedged scope dies, not a busy one.
        ManagedOOMMemoryPressure = "kill";
        ManagedOOMMemoryPressureLimit = "50%";
        ManagedOOMMemoryPressureDurationSec = "30s";
      };
    };
  };

  baseSurfaces = {
    sshd = {
      unit = "sshd.service";
      resourceClass = "interactive-access";
    };
    nix-gc = {
      unit = "nix-gc.service";
      resourceClass = "background-maintenance";
    };
    nix-optimise = {
      unit = "nix-optimise.service";
      resourceClass = "background-maintenance";
    };
  };

  mkInventory =
    {
      hostname ? "",
      surfaces ? baseSurfaces,
      mounts ? [ ],
      backups ? { },
    }:
    {
      schema = "sinnix-runtime-inventory-v1";
      inherit
        hostname
        classes
        commandClasses
        earlyoomEmergencyAvoidPattern
        slices
        ;
      surfaces = lib.mapAttrs (_: normalizeSurface) surfaces;
      inherit mounts backups;
      observedServices = observedServiceRows surfaces;
      captures = captureRows surfaces;
    };
}
