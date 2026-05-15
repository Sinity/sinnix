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
      noLocalSlice =
        name:
        !(builtins.hasAttr name config.systemd.slices)
        || (config.systemd.slices.${name}.sliceConfig or { }) == { };
      noUserSlice =
        name:
        !(builtins.hasAttr name config.systemd.user.slices)
        || (config.systemd.user.slices.${name}.sliceConfig or { }) == { };
    in
    [
      {
        assertion = !config.zramSwap.enable;
        message = "zram must stay disabled on the workstation baseline";
      }
      {
        assertion = !config.systemd.oomd.enable && config.services.earlyoom.enable;
        message = "systemd-oomd must stay disabled while earlyoom handles global pressure";
      }
      {
        assertion =
          lib.hasInfix "Hyprland" earlyoomAvoid
          && lib.hasInfix "below" earlyoomAvoid
          && lib.hasInfix "cargo" earlyoomPrefer
          && lib.hasInfix "nix-daemon" earlyoomPrefer;
        message = "earlyoom must prefer expendable build/browser work and avoid recovery/UI processes";
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
          noLocalSlice "nix"
          && noLocalSlice "nix-build"
          && noLocalSlice "background"
          && noLocalSlice "sinnix"
          && noLocalSlice "sinnix-maintenance"
          && noLocalSlice "system-critical"
          && noUserSlice "agent"
          && noUserSlice "build"
          && noUserSlice "background"
          && noUserSlice "app"
          && noUserSlice "session";
        message = "Sinnix must not define custom resource-policy slices on the simplified baseline";
      }
      {
        assertion =
          nixSettings.max-jobs == 8
          && nixSettings.cores == 0
          && !(nixSettings ? use-cgroups)
          && !(builtins.elem "cgroups" nixSettings.experimental-features)
          && lib.hasInfix "SINNIX_REBUILD_MAX_JOBS:-8" commandRegistry
          && lib.hasInfix "SINNIX_REBUILD_CORES:-0" commandRegistry
          && lib.hasInfix "SINNIX_REBUILD_MAX_JOBS:-8" devShell
          && lib.hasInfix "SINNIX_REBUILD_CORES:-0" devShell
          && lib.hasInfix "NIX_SAFE_MAX_JOBS:-8" nixSafeScript
          && lib.hasInfix "NIX_SAFE_CORES:-0" nixSafeScript;
        message = "Nix concurrency must stay moderate without enabling Nix cgroups";
      }
      {
        assertion =
          lib.hasInfix "usage: sinnix-scope <agent|build|background|nix-build>" scopeScript
          && lib.hasInfix "exec \"$@\"" scopeScript
          && !(lib.hasInfix "systemd-run" scopeScript)
          && !(lib.hasInfix "agent.slice" scopeScript)
          && !(lib.hasInfix "nix-build.slice" scopeScript);
        message = "sinnix-scope must be a compatibility shim, not a slice placer";
      }
      {
        assertion =
          builtins.elem "d /var/cache/nix-build 0755 root root -" config.systemd.tmpfiles.rules
          && lib.hasInfix "build-dir = /var/cache/nix-build" coreModule
          && !(lib.hasInfix "/cache/nix/" coreModule)
          && lib.hasInfix "Eval/fetcher cache stays under ~/.cache/nix" persistenceModule;
        message = "Nix scratch and eval cache must not rely on the failed /cache NVMe";
      }
      {
        assertion =
          lib.hasInfix "Do not enable Nix cgroups" coreModule
          && !(lib.hasInfix "future `use-cgroups = true` trial" coreModule);
        message = "Nix cgroup notes must match the simplified baseline";
      }
    ];
}
