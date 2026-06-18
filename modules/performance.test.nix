{
  lib,
  mountTmpfsRoots,
  baseTestConfig,
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
      runtimeInventory = config.sinnix.runtime.inventory;
      runtimeInventoryJson =
        builtins.fromJSON
          config.environment.etc."sinnix/runtime-inventory.json".text;
      noLocalSlice =
        name:
        !(builtins.hasAttr name config.systemd.slices)
        || (config.systemd.slices.${name}.sliceConfig or { }) == { };
      noWholeSessionCaps =
        name:
        let
          sliceConfig = config.systemd.user.slices.${name}.sliceConfig or { };
        in
        !(sliceConfig ? MemoryHigh) && !(sliceConfig ? MemoryMax);
      noOomdPressure =
        sliceConfig:
        !(sliceConfig ? ManagedOOMMemoryPressure) && !(sliceConfig ? ManagedOOMMemoryPressureLimit);
      systemSlicesWithoutOomd = [
        "background"
        "nix-build"
      ];
      userSlicesWithoutOomd = [
        "background"
        "build"
        "nix-build"
      ];
      userDbusBroker = config.systemd.user.services.dbus-broker;
    in
    [
      {
        assertion = config.zramSwap.enable && config.swapDevices == [ ];
        message = "desktop memory policy must use zram without disk swap";
      }
      {
        assertion = config.systemd.oomd.enable && config.services.earlyoom.enable;
        message = "oomd stays available while earlyoom handles global emergencies";
      }
      {
        assertion =
          !userDbusBroker.reloadIfChanged
          && !userDbusBroker.restartIfChanged
          && !userDbusBroker.stopIfChanged;
        message = "user dbus-broker must not be reloaded or restarted during switch activation";
      }
      {
        assertion =
          (config.systemd.services ? sinnix-iocost-init)
          && !(config.systemd.services ? sinnix-swap-drain)
          && !(config.systemd.timers ? sinnix-swap-drain);
        message = "sinnix-iocost-init must be installed (IOWeight is a no-op on NVMe without it); swap-drain must remain retired";
      }
      {
        assertion =
          !(config.systemd.services ? browser-oom-protect)
          && !(config.systemd.user.services ? sinnix-thaw-interactive-scopes)
          && !(config.systemd.user.timers ? sinnix-thaw-interactive-scopes);
        message = "desktop must not install the retired browser OOM score daemon";
      }
      {
        assertion =
          noLocalSlice "sinnix"
          && noLocalSlice "sinnix-maintenance"
          && noWholeSessionCaps "app"
          && noWholeSessionCaps "session";
        message = "Sinnix must not resurrect retired whole-session memory caps or maintenance slice policy";
      }
      {
        assertion =
          builtins.all (
            name: noOomdPressure config.systemd.slices.${name}.sliceConfig
          ) systemSlicesWithoutOomd
          && builtins.all (
            name: noOomdPressure config.systemd.user.slices.${name}.sliceConfig
          ) userSlicesWithoutOomd;
        message = "background/build slices must not use oomd PSI kills";
      }
      {
        assertion =
          runtimeInventory.schema == "sinnix-runtime-inventory-v1"
          && runtimeInventoryJson.schema == runtimeInventory.schema
          && builtins.hasAttr (lib.removeSuffix ".slice" runtimeInventory.commandClasses.build.slice) config.systemd.user.slices
          && builtins.elem "SINEX_DEV_CACHE_ROOT" runtimeInventory.environmentAllowList;
        message = "runtime policy registry must be the single source for command classes and declared surfaces";
      }
      {
        assertion =
          runtimeInventory.commandClasses.agent.systemdProperties == { }
          && !(config.systemd.user.slices.agent.sliceConfig ? MemoryHigh)
          && !(config.systemd.user.slices.agent.sliceConfig ? MemoryMax)
          && config.systemd.user.slices.agent.sliceConfig.MemorySwapMax == "0"
          && config.systemd.user.slices.agent.sliceConfig.MemoryLow == "3G";
        message = "interactive agent frontends must not share a cgroup memory throttle";
      }
      {
        assertion =
          config.systemd.user.slices.app.sliceConfig.MemorySwapMax == "0"
          && config.systemd.user.slices.session.sliceConfig.MemorySwapMax == "0";
        message = "interactive app and session slices must not be pushed into zram";
      }
    ];
}
