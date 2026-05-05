{
  lib,
  mountTmpfsRoots,
  baseTestConfig,
  inputs,
  ...
}:
{
  name = "core-performance-policy";
  modules = [
    mountTmpfsRoots
    baseTestConfig
    (
      { ... }:
      {
        networking.hostName = "performance-policy-test";
        sinnix.machine.isDesktop = true;
        sinnix.features.cli.core.enable = true;
      }
    )
  ];
  assertions =
    config:
    let
      hmService = config.systemd.services."home-manager-${config.sinnix.user.name}".serviceConfig;
      systemSlice = config.systemd.slices.system.sliceConfig;
      userSlice = config.systemd.slices.user.sliceConfig;
      appSlice = config.systemd.user.slices.app.sliceConfig;
      userBackgroundSlice = config.systemd.user.slices.background.sliceConfig;
      buildSlice = config.systemd.user.slices.build.sliceConfig;
      systemBackgroundSlice = config.systemd.slices.background.sliceConfig;
      nixParentSlice = config.systemd.slices.nix.sliceConfig;
      nixBuildSlice = config.systemd.slices."nix-build".sliceConfig;
      sinnixParentSlice = config.systemd.slices.sinnix.sliceConfig;
      maintenanceSlice = config.systemd.slices."sinnix-maintenance".sliceConfig;
      nixDaemonService = config.systemd.services.nix-daemon.serviceConfig;
      nixGcService = config.systemd.services.nix-gc.serviceConfig;
      nixGcRestartIfChanged = config.systemd.services.nix-gc.restartIfChanged;
      nixOptimiseService = config.systemd.services.nix-optimise.serviceConfig;
      nixOptimiseRestartIfChanged = config.systemd.services.nix-optimise.restartIfChanged;
      sinexDevCachePruneService = config.systemd.services.sinex-dev-cache-prune.serviceConfig;
      sinexDevCachePruneRestartIfChanged = config.systemd.services.sinex-dev-cache-prune.restartIfChanged;
      nixGcTimer = config.systemd.timers.nix-gc.timerConfig;
      nixOptimiseTimer = config.systemd.timers.nix-optimise.timerConfig;
      nixSettings = config.nix.settings;
      scopeScript = builtins.readFile (inputs.self + "/scripts/sinnix-scope");
      commandRegistry = builtins.readFile (inputs.self + "/flake/command-registry.nix");
      devShell = builtins.readFile (inputs.self + "/flake/dev-shell.nix");
      nixSafeScript = builtins.readFile (inputs.self + "/scripts/nix-safe");
      observeScript = builtins.readFile (inputs.self + "/scripts/sinnix-observe");
      coreModule = builtins.readFile (inputs.self + "/modules/core.nix");
      persistenceModule = builtins.readFile (inputs.self + "/modules/persistence.nix");
      pretooluseBash = builtins.readFile (inputs.self + "/dots/claude/hooks/pretooluse-bash.sh");
      hm = config.home-manager.users.${config.sinnix.user.name};
      nixUserCacheRule = "d /cache/nix/user/${config.sinnix.user.name} 0755 ${config.sinnix.user.name} users -";
      direnvrc = hm.xdg.configFile."direnv/direnvrc".text or "";
      earlyoomAvoid = builtins.elemAt config.services.earlyoom.extraArgs 1;
      earlyoomPrefer = builtins.elemAt config.services.earlyoom.extraArgs 3;
      packageNames = map (pkg: pkg.name or "") config.environment.systemPackages;
      interactiveIoLatencyTargets = [
        "/dev/disk/by-uuid/f4782d9f-aabe-408e-b18b-2f2baa9e9a02 75ms"
        "/dev/disk/by-uuid/7f603111-8f3a-40aa-bad0-0cac69c140f1 25ms"
        "/dev/disk/by-uuid/bd19092f-a195-47ab-9c0d-c923d1e5bfea 25ms"
      ];
      opportunisticIoLatencyTargets = [
        "/dev/disk/by-uuid/f4782d9f-aabe-408e-b18b-2f2baa9e9a02 250ms"
        "/dev/disk/by-uuid/7f603111-8f3a-40aa-bad0-0cac69c140f1 100ms"
        "/dev/disk/by-uuid/bd19092f-a195-47ab-9c0d-c923d1e5bfea 100ms"
      ];
      hasHardResourceCeiling =
        slice:
        (slice ? MemoryHigh)
        || (slice ? MemoryMax)
        || (slice ? MemorySwapMax)
        || (slice ? CPUQuota)
        || (slice ? IOReadBandwidthMax)
        || (slice ? IOWriteBandwidthMax);
      hasPressureShedding =
        slice:
        slice.ManagedOOMMemoryPressure == "kill"
        && slice.ManagedOOMMemoryPressureLimit == "10%"
        && slice.ManagedOOMMemoryPressureDurationSec == "5s";
    in
    [
      {
        assertion = !(config.systemd.services ? "nixos-rebuild-switch-to-configuration");
        message = "nixos-rebuild switch-to-configuration must remain transient";
      }
      {
        assertion = !(builtins.elem "nixos-rebuild" packageNames);
        message = "bare nixos-rebuild must not be shadowed by a high-priority wrapper";
      }
      {
        assertion = (hmService.Slice or "") == "nix-build.slice";
        message = "Home Manager activation must stay in nix-build.slice";
      }
      {
        assertion =
          !(userSlice ? MemoryHigh)
          && !(userSlice ? MemoryMax)
          && userSlice.MemoryMin == "2G"
          && userSlice.MemoryLow == "12G"
          && userSlice.IODeviceLatencyTargetSec == interactiveIoLatencyTargets
          && userSlice.TasksMax == "10000";
        message = "user.slice must protect recovery headroom and I/O latency without a parent memory cap";
      }
      {
        assertion =
          config.systemd.oomd.enable
          && !config.systemd.oomd.enableRootSlice
          && !config.systemd.oomd.enableSystemSlice
          && !config.systemd.oomd.enableUserSlices
          && config.systemd.oomd.settings.OOM.DefaultMemoryPressureDurationSec == "5s";
        message = "systemd-oomd must be enabled only for explicitly opted-in pressure slices";
      }
      {
        assertion =
          lib.hasInfix "waybar" earlyoomAvoid
          && lib.hasInfix "tofi" earlyoomAvoid
          && !(lib.hasInfix "waybar" earlyoomPrefer)
          && !(lib.hasInfix "tofi" earlyoomPrefer);
        message = "earlyoom must treat Waybar/tofi as recovery UI, not preferred victims";
      }
      {
        assertion =
          !hasHardResourceCeiling systemSlice
          && systemSlice.MemoryMin == "1G"
          && systemSlice.MemoryLow == "2G"
          && systemSlice.CPUWeight == 1000
          && systemSlice.IOWeight == 1000
          && systemSlice.IODeviceLatencyTargetSec == interactiveIoLatencyTargets
          && systemSlice.ManagedOOMPreference == "avoid";
        message = "system.slice must reserve a baseline for PID 1 support services";
      }
      {
        assertion =
          !hasHardResourceCeiling appSlice
          && appSlice.MemoryMin == "1G"
          && appSlice.MemoryLow == "8G"
          && appSlice.ManagedOOMPreference == "avoid"
          && appSlice.CPUWeight == 800
          && appSlice.IOWeight == 800
          && appSlice.IODeviceLatencyTargetSec == interactiveIoLatencyTargets;
        message = "app.slice must protect Waybar/terminals with latency targets, not hard caps";
      }
      {
        assertion =
          !hasHardResourceCeiling config.systemd.user.slices.session.sliceConfig
          && config.systemd.user.slices.session.sliceConfig.MemoryMin == "1G"
          && config.systemd.user.slices.session.sliceConfig.MemoryLow == "2G"
          &&
            config.systemd.user.slices.session.sliceConfig.IODeviceLatencyTargetSec
            == interactiveIoLatencyTargets
          && config.systemd.user.slices.session.sliceConfig.ManagedOOMPreference == "avoid";
        message = "session.slice must protect Hyprland/session supervision without hard caps";
      }
      {
        assertion =
          !hasHardResourceCeiling userBackgroundSlice
          && hasPressureShedding userBackgroundSlice
          && userBackgroundSlice.CPUWeight == 20
          && userBackgroundSlice.IOWeight == 50
          && userBackgroundSlice.IODeviceLatencyTargetSec == opportunisticIoLatencyTargets;
        message = "user background.slice must stay weighted, latency-sheddable, and pressure-sheddable without hard ceilings";
      }
      {
        assertion =
          !hasHardResourceCeiling buildSlice
          && hasPressureShedding buildSlice
          && buildSlice.CPUWeight == 20
          && buildSlice.IOWeight == 50
          && buildSlice.IODeviceLatencyTargetSec == opportunisticIoLatencyTargets;
        message = "build.slice must stay observable/weighted, latency-sheddable, and pressure-sheddable without hard ceilings";
      }
      {
        assertion =
          !hasHardResourceCeiling systemBackgroundSlice
          && hasPressureShedding systemBackgroundSlice
          && systemBackgroundSlice.CPUWeight == 20
          && systemBackgroundSlice.IOWeight == 50
          && systemBackgroundSlice.IODeviceLatencyTargetSec == opportunisticIoLatencyTargets;
        message = "system background.slice must stay weighted, latency-sheddable, and pressure-sheddable without hard ceilings";
      }
      {
        assertion =
          nixParentSlice.IODeviceLatencyTargetSec == opportunisticIoLatencyTargets
          && sinnixParentSlice.IODeviceLatencyTargetSec == opportunisticIoLatencyTargets;
        message = "nix.slice and sinnix.slice parents must carry root-level latency-shedding targets";
      }
      {
        assertion =
          !hasHardResourceCeiling nixBuildSlice
          && hasPressureShedding nixBuildSlice
          && nixBuildSlice.CPUWeight == 20
          && nixBuildSlice.IOWeight == 50
          && nixBuildSlice.IODeviceLatencyTargetSec == opportunisticIoLatencyTargets;
        message = "nix-build.slice must stay observable/weighted, latency-sheddable, and pressure-sheddable without hard ceilings";
      }
      {
        assertion =
          !hasHardResourceCeiling maintenanceSlice
          && maintenanceSlice.ManagedOOMMemoryPressure == "kill"
          && maintenanceSlice.ManagedOOMMemoryPressureLimit == "5%"
          && maintenanceSlice.ManagedOOMMemoryPressureDurationSec == "5s"
          && maintenanceSlice.CPUWeight == 10
          && maintenanceSlice.IOWeight == 1
          && maintenanceSlice.IODeviceLatencyTargetSec == opportunisticIoLatencyTargets;
        message = "sinnix-maintenance.slice must serialize low-priority work without hard ceilings";
      }
      {
        assertion =
          !hasHardResourceCeiling nixDaemonService
          && nixDaemonService.Slice == "nix-build.slice"
          && hasPressureShedding nixDaemonService
          && nixDaemonService.CPUWeight == 20
          && nixDaemonService.IOWeight == 50
          && nixDaemonService.IODeviceLatencyTargetSec == opportunisticIoLatencyTargets;
        message = "nix-daemon must stay in nix-build.slice with pressure/latency-sheddable build policy";
      }
      {
        assertion =
          nixGcService.Slice == "sinnix-maintenance.slice"
          && nixGcRestartIfChanged == false
          && nixGcService.Nice == 19
          && nixGcService.CPUWeight == 10
          && nixGcService.IOWeight == 1
          && nixGcService.IOSchedulingClass == "idle"
          && nixGcTimer.Persistent == false
          &&
            builtins.match ".*sinnix-maintenance-gate.*nix-gc\\.service.*" nixGcService.ExecCondition != null;
        message = "Nix GC must run as gated low-priority maintenance, not unweighted system.slice I/O";
      }
      {
        assertion =
          nixOptimiseService.Slice == "sinnix-maintenance.slice"
          && nixOptimiseRestartIfChanged == false
          && nixOptimiseService.Nice == 19
          && nixOptimiseService.CPUWeight == 10
          && nixOptimiseService.IOWeight == 1
          && nixOptimiseService.IOSchedulingClass == "idle"
          && nixOptimiseTimer.Persistent == false
          &&
            builtins.match ".*sinnix-maintenance-gate.*nix-optimise\\.service.*" nixOptimiseService.ExecCondition
            != null;
        message = "Nix store optimisation must run as gated low-priority maintenance";
      }
      {
        assertion =
          sinexDevCachePruneService.Slice == "sinnix-maintenance.slice"
          && sinexDevCachePruneRestartIfChanged == false
          && sinexDevCachePruneService.Nice == 19
          && sinexDevCachePruneService.CPUWeight == 10
          && sinexDevCachePruneService.IOWeight == 1
          && sinexDevCachePruneService.IOSchedulingClass == "idle"
          &&
            builtins.match ".*sinnix-maintenance-gate.*sinex-dev-cache-prune\\.service.*" sinexDevCachePruneService.ExecCondition
            != null;
        message = "Sinex dev cache pruning must run as gated low-priority maintenance";
      }
      {
        assertion =
          nixSettings.max-jobs == 8
          && nixSettings.cores == 0
          && !(nixSettings ? use-cgroups)
          && lib.hasInfix "SINNIX_REBUILD_MAX_JOBS:-8" commandRegistry
          && lib.hasInfix "SINNIX_REBUILD_CORES:-0" commandRegistry
          && lib.hasInfix "SINNIX_REBUILD_MAX_JOBS:-8" devShell
          && lib.hasInfix "SINNIX_REBUILD_CORES:-0" devShell
          && lib.hasInfix "NIX_SAFE_MAX_JOBS:-8" nixSafeScript
          && lib.hasInfix "NIX_SAFE_CORES:-0" nixSafeScript
          && !(lib.hasInfix "SINNIX_REBUILD_MAX_JOBS:-auto" commandRegistry)
          && !(lib.hasInfix "NIX_SAFE_MAX_JOBS:-auto" nixSafeScript);
        message = "Nix build concurrency must default to measured middle-ground throughput pending benchmark";
      }
      {
        assertion =
          hm.home.file ? ".cache/nix"
          && hm.home.file.".cache/nix".force == true
          && builtins.elem nixUserCacheRule config.systemd.tmpfiles.rules
          && lib.hasInfix "mkOutOfStoreSymlink \"/cache/nix/user/" coreModule
          && lib.hasInfix "future `use-cgroups = true` trial" coreModule
          && lib.hasInfix "per-derivation attribution" coreModule
          && lib.hasInfix "~/.cache/nix is intentionally not persisted" persistenceModule
          && !(lib.hasInfix "      \".cache/nix\"" persistenceModule);
        message = "Nix eval/fetcher cache must live on /cache with documented cgroup trial intent";
      }
      {
        assertion = !(config.services.ananicy.enable or false);
        message = "Ananicy name-based process tuning must stay disabled; resource policy belongs in explicit slices";
      }
      {
        assertion =
          lib.hasInfix ''uid="''${EUID:-$(id -u)}"'' scopeScript
          && lib.hasInfix "# The system nix-build slice exists for root/nix-daemon work." scopeScript
          && lib.hasInfix ''slice="build.slice"'' scopeScript
          && lib.hasInfix ''[ "$uid" -eq 0 ] && [ "$class" = "build" ]'' scopeScript
          && lib.hasInfix ''slice="nix-build.slice"'' scopeScript
          && lib.hasInfix "--nice=0" scopeScript;
        message = "sinnix-scope must keep user and root build placement on configured slices without inheriting agent nice priority";
      }
      {
        assertion =
          !(lib.hasInfix "SINEX_DEV_CACHE_ROOT=\"/cache/sinex" scopeScript)
          && !(lib.hasInfix "apply_project_cache_policy" scopeScript);
        message = "sinnix-scope must only place scopes; host cache policy belongs outside the scope wrapper";
      }
      {
        assertion =
          !(lib.hasInfix "updatedInput" pretooluseBash)
          && !(lib.hasInfix "Rewrapped pytest" pretooluseBash)
          && !(lib.hasInfix "heavy_command_requires_scope" pretooluseBash)
          && !(lib.hasInfix "unscoped heavyweight" pretooluseBash)
          && lib.hasInfix "profile" pretooluseBash
          && lib.hasInfix "git" pretooluseBash
          && lib.hasInfix "force-push" pretooluseBash
          && lib.hasInfix "permissionDecision: \"deny\"" pretooluseBash;
        message = "Claude Bash hook must stay limited to true guardrails; resource placement belongs in dev environments";
      }
      {
        assertion =
          lib.hasInfix "_sinnix_project_scope_setup" direnvrc
          && lib.hasInfix "_sinnix_project_root()" direnvrc
          && lib.hasInfix "/realm/project/sinnix) printf '%s\\n' sinnix" direnvrc
          && lib.hasInfix "/realm/project/sinity-lynchpin) printf '%s\\n' lynchpin" direnvrc
          && lib.hasInfix "/realm/project/sinex | /realm/project/sinex-*" direnvrc
          && lib.hasInfix "/realm/project/polylogue | /realm/project/polylogue-*" direnvrc
          && lib.hasInfix "/realm/project/scribe-tap) printf '%s\\n' rust-project" direnvrc
          && lib.hasInfix "/realm/project/intercept-bounce) printf '%s\\n' rust-project" direnvrc
          && lib.hasInfix "/realm/project/knowledge-extract) printf '%s\\n' python-project" direnvrc
          && lib.hasInfix "/realm/project/pwrank) printf '%s\\n' web-project" direnvrc
          && lib.hasInfix "realm-project" direnvrc
          && lib.hasInfix "SINEX_DEV_CACHE_ROOT" direnvrc
          && lib.hasInfix "SINNIX_SCOPE_ORIGINAL_PATH" direnvrc
          && lib.hasInfix "SINNIX_SCOPE_WRAPPER_PROJECT" direnvrc
          && lib.hasInfix "SINNIX_SCOPE_WRAPPER_PROJECT_ROOT" direnvrc
          && lib.hasInfix "ln -sfn .sinnix-scope-wrapper" direnvrc
          && lib.hasInfix "xtask" direnvrc
          && lib.hasInfix "polylogue" direnvrc
          && lib.hasInfix "check just make" direnvrc
          && lib.hasInfix "npm pnpm yarn bun" direnvrc
          && lib.hasInfix "use_flake() {\n    _sinnix_project_scope_setup\n    _sinnix_original_use_flake" direnvrc
          && lib.hasInfix ''"$scope_bin" "$class" -- "$cmd" "$@"'' direnvrc;
        message = "Active /realm/project devshells must transparently route heavy commands through sinnix-scope";
      }
      {
        assertion =
          lib.hasInfix "below recent history" observeScript
          && lib.hasInfix "collect_below" observeScript
          && lib.hasInfix "below" observeScript
          && lib.hasInfix "collect_storage" observeScript
          && lib.hasInfix "workload_rows" observeScript
          && lib.hasInfix "gaps_summary" observeScript
          && lib.hasInfix "chrome I/O attribution" observeScript
          && lib.hasInfix "collect_chrome_io" observeScript
          && lib.hasInfix "chrome_io" observeScript
          && lib.hasInfix "SINNIX_OBSERVE_CHROME_DU" observeScript
          && lib.hasInfix ".config/chrome-ws" observeScript
          && lib.hasInfix "counter_scope" observeScript
          && lib.hasInfix "IODeviceLatencyTargetUSec" observeScript
          && lib.hasInfix "io_device_latency_target" observeScript
          && lib.hasInfix "sinex.invocation.lacks_cgroup" observeScript
          && lib.hasInfix "polylogue.run.lacks_cgroup" observeScript
          && lib.hasInfix ''"--format"'' observeScript
          && lib.hasInfix "findmnt" observeScript
          && lib.hasInfix ''"iostat", "-xz", "1", "2"'' observeScript
          && lib.hasInfix "discard_max_bytes" observeScript
          && lib.hasInfix ".local/share/polylogue" observeScript
          && lib.hasInfix "/realm/data/captures/sinex" observeScript
          && lib.hasInfix "/var/lib/postgresql" observeScript
          && lib.hasInfix "fstrim.service" observeScript
          && lib.hasInfix "SINNIX_OBSERVE_BEGIN" observeScript
          && lib.hasInfix "SINNIX_OBSERVE_SINEX_DB" observeScript
          && lib.hasInfix "SINNIX_OBSERVE_POLYLOGUE_DB" observeScript
          && lib.hasInfix ".sinex/state/xtask-history.db" observeScript
          && !(lib.hasInfix "XTASK_HISTORY_DB" observeScript);
        message = "sinnix-observe must include JSON workload rows, gap reporting, storage pressure, below joins, and canonical project ledgers";
      }
    ];
}
