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
      persistenceModule = builtins.readFile (inputs.self + "/modules/persistence.nix");
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
      userAgent = config.systemd.user.slices.agent.sliceConfig;
      userBackground = config.systemd.user.slices.background.sliceConfig;
      userBuild = config.systemd.user.slices.build.sliceConfig;
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
          && !(lib.hasInfix "oom_score_adj" (builtins.readFile (inputs.self + "/modules/performance.nix")))
          && !(lib.hasInfix "pgrep -x" (builtins.readFile (inputs.self + "/modules/performance.nix")));
        message = "desktop must not install the retired browser OOM score daemon";
      }
      {
        assertion =
          noLocalSlice "nix"
          && noLocalSlice "sinnix"
          && noLocalSlice "sinnix-maintenance"
          && noLocalSlice "system-critical"
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
          && userBackground.CPUWeight == 10
          && userBackground.IOWeight == 5
          && userBuild.CPUWeight == 20
          && userBuild.IOWeight == 10
          && userAgent.CPUWeight == 200
          && userAgent.IOWeight == 100
          && userAgent.MemoryLow == "1G";
        message = "background/build/agent slices must keep measured resource budgets";
      }
      {
        assertion =
          nixSettings.max-jobs == 4
          && nixSettings.cores == 4
          && !(nixSettings ? use-cgroups)
          && !(builtins.elem "cgroups" nixSettings.experimental-features)
          && lib.hasInfix "SINNIX_REBUILD_MAX_JOBS:-4" commandRegistry
          && lib.hasInfix "SINNIX_REBUILD_CORES:-4" commandRegistry
          && lib.hasInfix "SINNIX_REBUILD_MAX_JOBS:-4" devShell
          && lib.hasInfix "SINNIX_REBUILD_CORES:-4" devShell
          && lib.hasInfix "NIX_SAFE_MAX_JOBS:-4" nixSafeScript
          && lib.hasInfix "NIX_SAFE_CORES:-4" nixSafeScript;
        message = "Nix concurrency must stay bounded without enabling Nix cgroups";
      }
      {
        assertion =
          lib.hasInfix "usage: sinnix-scope <agent|build|background|nix-build>" scopeScript
          && lib.hasInfix "systemd-run" scopeScript
          && lib.hasInfix "agent.slice" scopeScript
          && lib.hasInfix "build.slice" scopeScript
          && lib.hasInfix "background.slice" scopeScript
          && lib.hasInfix "nix-build.slice" scopeScript
          && lib.hasInfix "--unit=\"$unit\"" scopeScript
          && lib.hasInfix "--user" scopeScript;
        message = "sinnix-scope must place heavy work in explicit resource slices";
      }
      {
        assertion =
          builtins.any (rule: lib.hasInfix "/realm/cache/nix-build" rule) config.systemd.tmpfiles.rules
          && builtins.any (rule: lib.hasInfix "/realm/cache/sccache" rule) config.systemd.tmpfiles.rules
          && lib.hasInfix "build-dir = " coreModule
          && lib.hasInfix "/cache/nix-build" coreModule
          && lib.hasInfix "SCCACHE_DIR = " coreModule
          && lib.hasInfix "/cache/sccache" coreModule
          && lib.hasInfix "services.sinnix-realm-cache-attrs" coreModule
          && lib.hasInfix "chattr +C" coreModule
          && lib.hasInfix "before = [ \"nix-daemon.service\" ]" coreModule
          && lib.hasInfix "requires = [ \"sinnix-realm-cache-attrs.service\" ]" coreModule
          && !(lib.hasInfix "/cache/nix/" coreModule)
          && lib.hasInfix "Eval/fetcher cache stays under ~/.cache/nix" persistenceModule;
        message = "Nix and sccache scratch must use prepared /realm cache, not root SATA or the failed /cache NVMe";
      }
      {
        assertion =
          lib.hasInfix "Do not enable Nix cgroups" coreModule
          && !(lib.hasInfix "future `use-cgroups = true` trial" coreModule);
        message = "Nix cgroup notes must match the simplified baseline";
      }
    ];
}
