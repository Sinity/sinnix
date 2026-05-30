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
      nixSettings = config.nix.settings;
      scopeScript = builtins.readFile (inputs.self + "/scripts/sinnix-scope");
      commandRegistry = builtins.readFile (inputs.self + "/flake/command-registry.nix");
      devShell = builtins.readFile (inputs.self + "/flake/dev-shell.nix");
      nixSafeScript = builtins.readFile (inputs.self + "/scripts/nix-safe");
      coreModule = builtins.readFile (inputs.self + "/modules/core.nix");
      performanceModule = builtins.readFile (inputs.self + "/modules/performance.nix");
      persistenceModule = builtins.readFile (inputs.self + "/modules/persistence.nix");
      cliCoreModule = builtins.readFile (inputs.self + "/modules/features/cli/core.nix");
      direnvrc = builtins.readFile (inputs.self + "/scripts/sinnix-direnvrc");
      rootCacheService = config.systemd.services.sinnix-root-cache-attrs;
      runtimeInventory = config.sinnix.runtime.inventory;
      runtimeInventoryJson =
        builtins.fromJSON
          config.environment.etc."sinnix/runtime-inventory.json".text;
      earlyoomAvoid = builtins.elemAt config.services.earlyoom.extraArgs 3;
      earlyoomPrefer = builtins.elemAt config.services.earlyoom.extraArgs 1;
      panicCaptureExec = config.systemd.services.panic-log-capture.serviceConfig.ExecStart;
      cpuPowerLimitExec = config.systemd.services.sinnix-cpu-power-limits.serviceConfig.ExecStart;
      noLocalSlice =
        name:
        !(builtins.hasAttr name config.systemd.slices)
        || (config.systemd.slices.${name}.sliceConfig or { }) == { };
      noUserSlice =
        name:
        !(builtins.hasAttr name config.systemd.user.slices)
        || (config.systemd.user.slices.${name}.sliceConfig or { }) == { };
      systemBackground = config.systemd.slices.background.sliceConfig;
      nixBuild = config.systemd.slices."nix-build".sliceConfig;
      systemCritical = config.systemd.slices."system-critical".sliceConfig;
      userAgent = config.systemd.user.slices.agent.sliceConfig;
      userBackground = config.systemd.user.slices.background.sliceConfig;
      userBuild = config.systemd.user.slices.build.sliceConfig;
      userNixBuild = config.systemd.user.slices."nix-build".sliceConfig;
    in
    [
      {
        assertion =
          config.zramSwap.enable && config.zramSwap.memoryPercent == 25 && config.zramSwap.priority == 100;
        message = "desktop must keep zram enabled as the emergency memory buffer";
      }
      {
        assertion = !config.systemd.oomd.enable && config.services.earlyoom.enable;
        message = "systemd-oomd must stay disabled while earlyoom handles global pressure";
      }
      {
        assertion =
          config.boot.kernel.sysctl."vm.dirty_background_bytes" == 64 * 1024 * 1024
          && config.boot.kernel.sysctl."vm.dirty_bytes" == 256 * 1024 * 1024;
        message = "desktop dirty writeback must stay byte-bounded for NVMe/Btrfs latency";
      }
      {
        assertion =
          config.boot.kernel.sysctl."kernel.hung_task_panic" == 0
          && config.boot.kernel.sysctl."kernel.hung_task_timeout_secs" == 120
          && config.boot.kernel.sysctl."kernel.panic" == 60
          && config.boot.kernel.sysctl."kernel.oops_all_cpu_backtrace" == 1
          && builtins.elem "ramoops" config.boot.kernelModules
          && builtins.elem "ramoops.dump_oops=1" config.boot.kernelParams;
        message = "desktop crash diagnostics must not auto-reboot on ordinary hung-task reports";
      }
      {
        assertion =
          lib.hasInfix "Hyprland" earlyoomAvoid
          && lib.hasInfix "below" earlyoomAvoid
          && lib.hasInfix "chrome" earlyoomAvoid
          && lib.hasInfix "firefox" earlyoomAvoid
          && lib.hasInfix "cargo" earlyoomPrefer
          && lib.hasInfix "nix-daemon" earlyoomPrefer
          && !(lib.hasInfix "chrome" earlyoomPrefer)
          && !(lib.hasInfix "firefox" earlyoomPrefer)
          && config.services.earlyoom.freeMemThreshold == 5
          && config.services.earlyoom.freeSwapThreshold == 15;
        message = "earlyoom must act only as a late emergency guard";
      }
      {
        assertion =
          !(config.systemd.services ? sinnix-iocost-init)
          && !(config.systemd.services ? sinnix-swap-drain)
          && !(config.systemd.timers ? sinnix-swap-drain);
        message = "The retired io.cost and swap-drain services must not be installed";
      }
      {
        assertion =
          lib.hasInfix "/bin/panic-log-capture" panicCaptureExec
          && !(lib.hasInfix "panic-log-capture.sh" panicCaptureExec);
        message = "panic-log-capture must execute a packaged binary, not a non-executable store file";
      }
      {
        assertion =
          lib.hasInfix "/bin/sinnix-apply-cpu-power-limits" cpuPowerLimitExec
          && config.systemd.services.sinnix-cpu-power-limits.wantedBy == [ "multi-user.target" ];
        message = "desktop must apply conservative CPU package power limits at boot";
      }
      {
        assertion =
          !(config.systemd.services ? browser-oom-protect)
          && !(lib.hasInfix "oom_score_adj" performanceModule)
          && !(lib.hasInfix "pgrep -x" performanceModule);
        message = "desktop must not install the retired browser OOM score daemon";
      }
      {
        assertion =
          noLocalSlice "nix"
          && noLocalSlice "sinnix"
          && noLocalSlice "sinnix-maintenance"
          && noUserSlice "app"
          && noUserSlice "session";
        message = "Sinnix must not resurrect retired whole-session or maintenance slice policy";
      }
      {
        assertion =
          systemBackground.CPUWeight == 10
          && systemBackground.IOWeight == 5
          && systemBackground.MemoryHigh == "4G"
          && systemBackground.MemoryMax == "10G"
          && nixBuild.CPUWeight == 20
          && nixBuild.IOWeight == 10
          && nixBuild.MemoryHigh == "8G"
          && nixBuild.MemoryMax == "16G"
          && systemCritical.CPUWeight == 200
          && systemCritical.IOWeight == 100
          && systemCritical.MemoryLow == "512M"
          && userBackground.CPUWeight == 10
          && userBackground.IOWeight == 5
          && userBuild.CPUWeight == 20
          && userBuild.IOWeight == 10
          && userNixBuild.CPUWeight == 20
          && userNixBuild.IOWeight == 10
          && userAgent.CPUWeight == 200
          && userAgent.IOWeight == 100
          && userAgent.MemoryLow == "1G";
        message = "background/build/agent slices must keep measured resource budgets";
      }
      {
        assertion =
          !(config.systemd.user.services ? sinnix-thaw-interactive-scopes)
          && !(config.systemd.user.timers ? sinnix-thaw-interactive-scopes)
          && !(lib.hasInfix "FreezerState" performanceModule)
          && !(lib.hasInfix "systemctl --user thaw" performanceModule);
        message = "desktop must not install automatic frozen-scope repair jobs";
      }
      {
        assertion =
          nixSettings.max-jobs == 4
          && nixSettings.cores == 4
          && nixSettings.http-connections == 16
          && nixSettings.max-substitution-jobs == 8
          && nixSettings.keep-going == false
          && !(nixSettings ? use-cgroups)
          && !(builtins.elem "cgroups" nixSettings.experimental-features)
          &&
            nixSettings.experimental-features == [
              "nix-command"
              "flakes"
              "fetch-tree"
            ]
          && lib.hasInfix "SINNIX_REBUILD_MAX_JOBS:-4" commandRegistry
          && lib.hasInfix "SINNIX_REBUILD_CORES:-4" commandRegistry
          && lib.hasInfix "SINNIX_REBUILD_MAX_JOBS:-4" devShell
          && lib.hasInfix "SINNIX_REBUILD_CORES:-4" devShell
          && lib.hasInfix "NIX_SAFE_MAX_JOBS:-4" nixSafeScript
          && lib.hasInfix "NIX_SAFE_CORES:-4" nixSafeScript;
        message = "Nix concurrency and substitution fan-out must stay bounded without enabling Nix cgroups";
      }
      {
        assertion =
          lib.hasInfix "usage: sinnix-scope <class> -- <command> [args...]" scopeScript
          && lib.hasInfix "SINNIX_RUNTIME_INVENTORY_FILE" scopeScript
          && lib.hasInfix "/etc/sinnix/runtime-inventory.json" scopeScript
          && lib.hasInfix "jq -er" scopeScript
          && lib.hasInfix ".commandClasses[$class] != null" scopeScript
          && lib.hasInfix ".environmentAllowList[]?" scopeScript
          && lib.hasInfix "systemd-run" scopeScript
          && lib.hasInfix "agent.slice" scopeScript
          && lib.hasInfix "build.slice" scopeScript
          && lib.hasInfix "background.slice" scopeScript
          && lib.hasInfix "nix-build.slice" scopeScript
          && lib.hasInfix ".commandClasses[$class].envDefaults" scopeScript
          && lib.hasInfix "ionice -c 2 -n" scopeScript
          && lib.hasInfix "nice -n \"$nice_level\"" scopeScript
          && lib.hasInfix "ionice -c 3" scopeScript
          && lib.hasInfix "--unit=\"$unit\"" scopeScript
          && lib.hasInfix "--user" scopeScript;
        message = "sinnix-scope must place heavy work in explicit resource slices and scheduler classes";
      }
      {
        assertion =
          runtimeInventory.schema == "sinnix-runtime-inventory-v1"
          && runtimeInventoryJson.schema == runtimeInventory.schema
          && runtimeInventory.commandClasses.build.slice == "build.slice"
          && runtimeInventory.commandClasses.build.envDefaults.MAKEFLAGS == "-j4"
          && runtimeInventory.commandClasses.agent.resourceClass == "interactive-agent"
          && runtimeInventory.classes.observability.serviceConfig.Slice == "system-critical.slice"
          && runtimeInventory.classes.interactive-access.serviceConfig.Slice == "system-critical.slice"
          && runtimeInventory.classes.backup-maintenance.serviceConfig.CPUWeight == 20
          && runtimeInventory.classes.capture-runtime.serviceConfig.MemoryMax == "8G"
          && builtins.elem "SINEX_DEV_CACHE_ROOT" runtimeInventory.environmentAllowList
          && runtimeInventory.surfaces.sshd.resourceClass == "interactive-access"
          && runtimeInventory.surfaces.nix-gc.resourceClass == "background-maintenance";
        message = "runtime policy registry must be the single source for command classes and declared surfaces";
      }
      {
        assertion =
          builtins.any (rule: lib.hasInfix "/var/cache/nix-build" rule) config.systemd.tmpfiles.rules
          && builtins.any (rule: lib.hasInfix "/var/cache/sccache" rule) config.systemd.tmpfiles.rules
          && builtins.any (rule: lib.hasInfix "/var/cache/sinex" rule) config.systemd.tmpfiles.rules
          && lib.hasInfix "build-dir = /var/cache/nix-build" config.nix.extraOptions
          && config.environment.variables.SCCACHE_DIR == "/var/cache/sccache"
          && config.environment.variables.SCCACHE_IDLE_TIMEOUT == "300"
          && rootCacheService.before == [ "nix-daemon.service" ]
          && rootCacheService.serviceConfig.Type == "oneshot"
          && lib.hasInfix "chattr +C" rootCacheService.script
          && builtins.elem "sinnix-root-cache-attrs.service" config.systemd.services.nix-daemon.requires
          && !(lib.hasInfix "/var/cache/nix-build" coreModule)
          && !(lib.hasInfix "/var/cache/sccache" coreModule)
          && lib.hasInfix "Eval/fetcher cache stays under ~/.cache/nix" persistenceModule;
        message = "Nix and sccache scratch must use prepared root cache, not /realm or the failed /cache NVMe";
      }
      {
        assertion =
          !(lib.hasInfix "default_sinex_cache=" scopeScript)
          && !(lib.hasInfix "SINEX_DEV_ROOT" scopeScript)
          && lib.hasInfix "builtins.readFile ../../../scripts/sinnix-direnvrc" cliCoreModule
          && lib.hasInfix "_sinnix_setup_sinex_dev_cache" direnvrc
          && lib.hasInfix "/var/cache/sinex/$sinex_user/$sinex_hash" direnvrc
          && lib.hasInfix "export SINEX_DEV_CACHE_ROOT=\"$sinex_cache_base\"" direnvrc
          && lib.hasInfix "export CARGO_TARGET_DIR=\"$SINEX_DEV_CACHE_ROOT/target\"" direnvrc
          && lib.hasInfix "export SINEX_DEV_STATE_DIR=\"$sinex_cache_base/dev-state\"" direnvrc
          && lib.hasInfix "export DATABASE_URL=\"postgresql:///sinex_dev?host=$SINEX_DEV_STATE_DIR/run\"" direnvrc;
        message = "Sinex dev cache relocation belongs to project direnv setup, not generic sinnix-scope";
      }
      {
        assertion =
          lib.hasInfix "earlyoom owns global emergency memory intervention" performanceModule
          && !(lib.hasInfix "while this host is being retuned" performanceModule);
        message = "OOM policy notes must be present-tense rather than retuning history";
      }
    ];
}
