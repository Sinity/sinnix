{ lib, mountTmpfsRoots, baseTestConfig, inputs, ... }:
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
      }
    )
  ];
  assertions =
    config:
    let
      hmService = config.systemd.services."home-manager-${config.sinnix.user.name}".serviceConfig;
      userSlice = config.systemd.slices.user.sliceConfig;
      appSlice = config.systemd.user.slices.app.sliceConfig;
      userBackgroundSlice = config.systemd.user.slices.background.sliceConfig;
      buildSlice = config.systemd.user.slices.build.sliceConfig;
      systemBackgroundSlice = config.systemd.slices.background.sliceConfig;
      nixBuildSlice = config.systemd.slices."nix-build".sliceConfig;
      nixDaemonService = config.systemd.services.nix-daemon.serviceConfig;
      scopeScript = builtins.readFile (inputs.self + "/scripts/sinnix-scope");
      observeScript = builtins.readFile (inputs.self + "/scripts/sinnix-observe");
      pretooluseBash = builtins.readFile (inputs.self + "/dots/claude/hooks/pretooluse-bash.sh");
      packageNames = map (pkg: pkg.name or "") config.environment.systemPackages;
      hasHardResourceCeiling =
        slice:
        (slice ? MemoryHigh)
        || (slice ? MemoryMax)
        || (slice ? MemorySwapMax)
        || (slice ? CPUQuota)
        || (slice ? IOReadBandwidthMax)
        || (slice ? IOWriteBandwidthMax);
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
          && userSlice.MemoryLow == "4G"
          && userSlice.TasksMax == "10000";
        message = "user.slice must protect recovery headroom without a parent memory cap";
      }
      {
        assertion =
          !hasHardResourceCeiling appSlice && appSlice.CPUWeight == 800 && appSlice.IOWeight == 800;
        message = "app.slice must prefer desktop work by weight, not by hard memory/CPU/I/O caps";
      }
      {
        assertion =
          !hasHardResourceCeiling userBackgroundSlice
          && userBackgroundSlice.CPUWeight == 20
          && userBackgroundSlice.IOWeight == 50;
        message = "user background.slice must stay weighted without arbitrary hard ceilings";
      }
      {
        assertion =
          !hasHardResourceCeiling buildSlice && buildSlice.CPUWeight == 20 && buildSlice.IOWeight == 50;
        message = "build.slice must stay observable/weighted without arbitrary hard ceilings";
      }
      {
        assertion =
          !hasHardResourceCeiling systemBackgroundSlice
          && systemBackgroundSlice.CPUWeight == 20
          && systemBackgroundSlice.IOWeight == 50;
        message = "system background.slice must stay weighted without arbitrary hard ceilings";
      }
      {
        assertion =
          !hasHardResourceCeiling nixBuildSlice
          && nixBuildSlice.CPUWeight == 20
          && nixBuildSlice.IOWeight == 50;
        message = "nix-build.slice must stay observable/weighted without arbitrary hard ceilings";
      }
      {
        assertion =
          !hasHardResourceCeiling nixDaemonService
          && nixDaemonService.Slice == "nix-build.slice"
          && nixDaemonService.CPUWeight == 20
          && nixDaemonService.IOWeight == 50;
        message = "nix-daemon must stay in nix-build.slice with weights only";
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
          && lib.hasInfix ''slice="nix-build.slice"'' scopeScript;
        message = "sinnix-scope must keep user and root build placement on configured slices";
      }
      {
        assertion =
          !(lib.hasInfix "SINEX_DEV_CACHE_ROOT=\"/cache/sinex" scopeScript)
          && !(lib.hasInfix "apply_project_cache_policy" scopeScript);
        message = "sinnix-scope must only place scopes; project cache policy belongs in project devshells";
      }
      {
        assertion =
          !(lib.hasInfix "updatedInput" pretooluseBash)
          && !(lib.hasInfix "Rewrapped pytest" pretooluseBash)
          && !(lib.hasInfix "sinnix-scope build" pretooluseBash);
        message = "Claude Bash hook must not transparently rewrite pytest/build commands";
      }
      {
        assertion =
          lib.hasInfix "below_recent_history" observeScript
          && lib.hasInfix "below dump cgroup" observeScript
          && lib.hasInfix "below dump process" observeScript
          && lib.hasInfix "storage_pressure" observeScript
          && lib.hasInfix ''findmnt -T "$mount"'' observeScript
          && lib.hasInfix "iostat -xz 1 2" observeScript
          && lib.hasInfix "discard_max_bytes" observeScript
          && lib.hasInfix "$HOME/.local/share/polylogue" observeScript
          && lib.hasInfix "/realm/data/captures/sinex" observeScript
          && lib.hasInfix "/var/lib/postgresql" observeScript
          && lib.hasInfix "fstrim.service" observeScript
          && lib.hasInfix "SINNIX_OBSERVE_BEGIN" observeScript
          && lib.hasInfix "$SINEX_ROOT/.sinex/state/xtask-history.db" observeScript
          && !(lib.hasInfix "XTASK_HISTORY_DB" observeScript);
        message = "sinnix-observe must include storage pressure, below joins, and canonical Sinex xtask history path";
      }
    ];
}
