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

  environmentAllowList = [
    "AGENT_NAME"
    "AGENT_SESSION_ID"
    "CARGO_BUILD_JOBS"
    "CARGO_HOME"
    "CARGO_INCREMENTAL"
    "CARGO_TARGET_DIR"
    "CMAKE_BUILD_PARALLEL_LEVEL"
    "CODEX_HOME"
    "DATABASE_URL"
    "GEMINI_API_KEY"
    "GITHUB_TOKEN"
    "HOME"
    "LANG"
    "LC_ALL"
    "LOGNAME"
    "MAKEFLAGS"
    "NIX_BUILD_CORES"
    "NIX_CONFIG"
    "NIX_PATH"
    "NIXPKGS_ALLOW_UNFREE"
    "PATH"
    "PGHOST"
    "PGPORT"
    "POLYLOGUE_ROOT"
    "PWD"
    "PYTHONHOME"
    "PYTHONPATH"
    "RUSTC_WRAPPER"
    "RUST_LOG"
    "RUSTUP_HOME"
    "SCCACHE_DIR"
    "SCCACHE_IDLE_TIMEOUT"
    "SHELL"
    "SINEX_CACHE_DIR"
    "SINEX_DEV_CACHE_ROOT"
    "SINEX_DEV_STATE_DIR"
    "SINEX_NATS_DIR"
    "SINEX_ROOT"
    "SINEX_STATE_DIR"
    "SINEX_TEST_RESULTS_DIR"
    "TERM"
    "TERM_PROGRAM"
    "TMPDIR"
    "USER"
    "UV_CACHE_DIR"
    "UV_PROJECT_ENVIRONMENT"
    "VIRTUAL_ENV"
    "XDG_CACHE_HOME"
    "XDG_CONFIG_HOME"
    "XDG_DATA_HOME"
    "XDG_RUNTIME_DIR"
    "XDG_STATE_HOME"
  ];

  commandClasses = {
    agent = {
      resourceClass = "interactive-agent";
      slice = "agent.slice";
      nice = null;
      ioniceClass = null;
      ionicePriority = null;
      systemdProperties = { };
      envDefaults = { };
    };
    build = {
      resourceClass = "developer-build";
      slice = "build.slice";
      nice = 5;
      ioniceClass = "best-effort";
      ionicePriority = 7;
      envDefaults = {
        CARGO_BUILD_JOBS = "12";
        CARGO_INCREMENTAL = "0";
        CMAKE_BUILD_PARALLEL_LEVEL = "12";
        MAKEFLAGS = "-j12";
        NIX_BUILD_CORES = "12";
        SCCACHE_IDLE_TIMEOUT = "10";
      };
    };
    background = {
      resourceClass = "background-maintenance";
      slice = "background.slice";
      nice = 10;
      ioniceClass = "idle";
      ionicePriority = null;
      envDefaults = { };
    };
    nix-build = {
      resourceClass = "developer-build";
      slice = "nix-build.slice";
      nice = 10;
      ioniceClass = "idle";
      ionicePriority = null;
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
      };
      nix-build = {
        CPUWeight = 5;
        IOWeight = 2;
        # Rust workspaces and NixOS rebuilds should use the workstation, while
        # still leaving room for the desktop and always-on data services.
        MemoryHigh = "18G";
        MemoryMax = "24G";
        MemorySwapMax = "0";
      };
      system-critical = {
        CPUWeight = 400;
        IOWeight = 300;
        MemoryLow = "2G";
      };
    };
    user = {
      agent = {
        CPUWeight = 400;
        IOWeight = 300;
        MemoryLow = "3G";
        MemorySwapMax = "0";
      };
      app = {
        MemorySwapMax = "0";
      };
      session = {
        MemorySwapMax = "0";
      };
      backup = {
        CPUWeight = 20;
        IOWeight = 20;
        MemoryHigh = "8G";
        MemoryMax = "12G";
      };
      background = {
        CPUWeight = 3;
        IOWeight = 1;
        MemoryHigh = "2G";
        MemoryMax = "4G";
      };
      build = {
        CPUWeight = 5;
        IOWeight = 2;
        MemoryHigh = "18G";
        MemoryMax = "24G";
        MemorySwapMax = "0";
      };
      nix-build = {
        CPUWeight = 5;
        IOWeight = 2;
        MemoryHigh = "18G";
        MemoryMax = "24G";
        MemorySwapMax = "0";
      };
    };
  };

  baseSurfaces = {
    sshd = {
      unit = "sshd.service";
      resourceClass = "interactive-access";
    };
    sshd-socket = {
      unit = "sshd.socket";
      kind = "socket";
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
        environmentAllowList
        slices
        ;
      surfaces = lib.mapAttrs (_: normalizeSurface) surfaces;
      inherit mounts backups;
      observedServices = observedServiceRows surfaces;
      captures = captureRows surfaces;
    };
}
