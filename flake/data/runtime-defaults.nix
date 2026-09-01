{ lib }:
let
  mkClass = description: serviceConfig: {
    inherit description serviceConfig;
  };

  surfaceType = surface: if surface.manager == "user" then "user" else surface.kind;

  normalizeSurface =
    surface:
    let
      normalized = {
        manager = "system";
        kind = "service";
        resourceClass = "system";
        observe = {
          enable = false;
          restartable = false;
        };
        acknowledged = {
          down = false;
          reason = "";
          since = "";
          ref = "";
        };
        captures = [ ];
        activation = {
          mode = "direct";
          publicEndpoint = null;
          backendEndpoint = null;
          idleTimeout = null;
          exclusiveResource = null;
          dependsOn = [ ];
        };
        workload = {
          class = "unclassified";
          rationale = "";
          processMatchers = [ ];
          earlyoomAvoid = false;
        };
        resources = { };
      }
      // surface;
    in
    normalized
    // {
      effectiveResources = lib.filterAttrs (_: value: value != null) normalized.resources;
    };

  effectiveSurface =
    resourceClasses: surface:
    let
      normalized = normalizeSurface surface;
      classResources = resourceClasses.${normalized.resourceClass}.serviceConfig or { };
    in
    normalized
    // {
      effectiveResources =
        classResources // lib.filterAttrs (_: value: value != null) normalized.resources;
    };

  # One lane, normalized for the inventory. Split out of captureRows so the
  # same shape is produced whether the lane hangs off a runtime surface or
  # stands alone in sinnix.runtime.captures -- a consumer reading the
  # flattened list cannot tell, and should not need to.
  captureRow =
    capture:
    {
      inherit (capture) name path;
    }
    // lib.optionalAttrs ((capture.cadenceSeconds or null) != null) {
      expectedCadenceSeconds = capture.cadenceSeconds;
    }
    // lib.optionalAttrs (capture.eventDriven or false) {
      expectedCadence = "event-driven";
    }
    // lib.optionalAttrs ((capture.staleAfterSeconds or null) != null) {
      expectedStaleAfterSeconds = capture.staleAfterSeconds;
    }
    // lib.optionalAttrs ((capture.requiredPayloadFields or [ ]) != [ ]) {
      inherit (capture) requiredPayloadFields;
    }
    // lib.optionalAttrs ((capture.livenessProbe or null) != null) {
      inherit (capture) livenessProbe;
    };

  captureRows =
    surfaces: standalone:
    (lib.concatLists (
      lib.mapAttrsToList (_name: surface: map captureRow surface.captures) (
        lib.mapAttrs (_: normalizeSurface) surfaces
      )
    ))
    ++ map captureRow standalone;

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
        workload = surface.workload;
        type = surfaceType surface;
        restartable = surface.observe.restartable;
        activationMode = surface.activation.mode;
        acknowledged = surface.acknowledged;
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
  # Single base list: earlyoomPatternFor extends exactly this with the
  # processMatchers of surfaces that opt in via workload.earlyoomAvoid.
  # Entries match unanchored against /proc/<pid>/comm (15 chars max, hence
  # the truncated xdg-desktop-po): keep entries <=15 chars, and only for
  # processes that can exist on our hosts.
  earlyoomEmergencyAvoidBase = [
    "systemd"
    "systemd-logind"
    "dbus-daemon"
    "sshd"
    "agetty"
    "uwsm"
    "start-hyprland"
    "Hyprland"
    "Xwayland"
    "noctalia"
    "xdg-desktop-po"
    "pipewire"
    "wireplumber"
    "kitty"
    "below"
    "nix-daemon"
  ];
  earlyoomEmergencyAvoidPattern = "(${lib.concatStringsSep "|" earlyoomEmergencyAvoidBase})";

  classes = {
    interactive-agent = mkClass "Interactive AI agent shells and frontends" { };
    interactive-access = mkClass "Login, SSH, and input services needed to regain control" {
      Slice = "system-critical.slice";
      Nice = -5;
      IOSchedulingClass = "best-effort";
      IOSchedulingPriority = 0;
    };
    desktop-shell = mkClass "Interactive desktop shell UI" {
      Slice = "desktop-shell.slice";
    };
    developer-build = mkClass "User-initiated builds, tests, and Nix work" { };
    managed-runtime-work = mkClass "Daemon-managed transient work" {
      Slice = "sinnixd-work.slice";
    };
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
    gpu-runtime = mkClass "GPU-accelerated runtimes that must not serialize builds" {
      Nice = 5;
      IOSchedulingClass = "best-effort";
      IOSchedulingPriority = 7;
      IOWeight = 20;
      MemoryHigh = "8G";
      MemoryMax = "12G";
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

  slices = {
    system = {
      background = {
        CPUWeight = 3;
        IOWeight = 1;
        MemoryHigh = "2G";
        MemoryMax = "4G";
        # PSI-scoped oomd: kill sacrificial work at cgroup granularity when
        # ITS OWN memory pressure stalls it, rather than letting global
        # earlyoom pick victims. 50%/30s (not the 10%/5s defaults) so only a
        # genuinely wedged scope dies, not a busy one.
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
        # PSI-scoped oomd: kill sacrificial work at cgroup granularity when
        # ITS OWN memory pressure stalls it, rather than letting global
        # earlyoom pick victims. 50%/30s (not the 10%/5s defaults) so only a
        # genuinely wedged scope dies, not a busy one.
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
        CPUWeight = 100;
        IOWeight = 300;
        MemoryLow = "4G";
      };
      session = {
        IOAccounting = true;
        CPUWeight = 100;
        IOWeight = 300;
      };
      desktop-shell = {
        IOAccounting = true;
        CPUWeight = 400;
        IOWeight = 300;
        MemoryLow = "512M";
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
        # PSI-scoped oomd: kill sacrificial work at cgroup granularity when
        # ITS OWN memory pressure stalls it, rather than letting global
        # earlyoom pick victims. 50%/30s (not the 10%/5s defaults) so only a
        # genuinely wedged scope dies, not a busy one.
        ManagedOOMMemoryPressure = "kill";
        ManagedOOMMemoryPressureLimit = "50%";
        ManagedOOMMemoryPressureDurationSec = "30s";
      };
      # Slice names encode hierarchy. This outer slice is the direct sibling
      # of app.slice and session.slice, so its weights govern host contention.
      sinnixd = {
        IOAccounting = true;
        CPUWeight = 10;
        IOWeight = 10;
        MemoryHigh = "24G";
        ManagedOOMSwap = "kill";
        # Same reasoning as background.slice above: kill a wedged scope, not a
        # busy one. Lane verification phases legitimately stall past 10% for
        # seconds at a time; at 10%/5s oomd killed healthy lanes mid-verify.
        ManagedOOMMemoryPressure = "kill";
        ManagedOOMMemoryPressureLimit = "50%";
        ManagedOOMMemoryPressureDurationSec = "30s";
      };
      sinnixd-work = {
        IOAccounting = true;
        CPUWeight = 100;
        IOWeight = 100;
      };
      sinnixd-work-interactive = {
        IOAccounting = true;
        CPUWeight = 400;
        IOWeight = 400;
      };
      sinnixd-work-agent = {
        IOAccounting = true;
        CPUWeight = 100;
        IOWeight = 100;
      };
      sinnixd-work-normal = {
        IOAccounting = true;
        CPUWeight = 50;
        IOWeight = 50;
      };
      sinnixd-work-bulk = {
        IOAccounting = true;
        CPUWeight = 10;
        IOWeight = 10;
      };
      gpu-runtime = {
        IOAccounting = true;
        CPUWeight = 20;
        IOWeight = 20;
        MemoryHigh = "8G";
        MemoryMax = "12G";
      };
      build = {
        IOAccounting = true;
        CPUWeight = 5;
        IOWeight = 2;
        MemoryHigh = "22G";
        MemoryMax = "28G";
        # PSI-scoped oomd: kill sacrificial work at cgroup granularity when
        # ITS OWN memory pressure stalls it, rather than letting global
        # earlyoom pick victims. 50%/30s (not the 10%/5s defaults) so only a
        # genuinely wedged scope dies, not a busy one.
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
        # PSI-scoped oomd: kill sacrificial work at cgroup granularity when
        # ITS OWN memory pressure stalls it, rather than letting global
        # earlyoom pick victims. 50%/30s (not the 10%/5s defaults) so only a
        # genuinely wedged scope dies, not a busy one.
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

  earlyoomPatternFor =
    surfaces:
    let
      protectedMatchers = lib.concatLists (
        lib.mapAttrsToList (
          _: surface:
          if surface.workload.earlyoomAvoid or false then surface.workload.processMatchers or [ ] else [ ]
        ) surfaces
      );
    in
    "(${lib.concatStringsSep "|" (lib.unique (earlyoomEmergencyAvoidBase ++ protectedMatchers))})";

  mkInventory =
    {
      hostname ? "",
      surfaces ? baseSurfaces,
      mounts ? [ ],
      backups ? { },
      captures ? [ ],
    }:
    {
      schema = "sinnix-runtime-inventory-v1";
      inherit
        hostname
        classes
        slices
        ;
      earlyoomEmergencyAvoidPattern = earlyoomPatternFor (lib.mapAttrs (_: normalizeSurface) surfaces);
      surfaces = lib.mapAttrs (_: effectiveSurface classes) surfaces;
      inherit mounts backups;
      observedServices = observedServiceRows surfaces;
      captures = captureRows surfaces captures;
    };
}
