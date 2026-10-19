# System Introspection: config dump generation
#
# Generates at build time:
# - /etc/sinnix/config.json   — the expected live state sinnix-config-drift
#   compares against, and the configuration revision
{
  lib,
  config,
  ...
}:
let
  # ── Config dump: only what sinnix-config-drift reads ────────────────
  configDump = {
    sinnix = {
      drift = {
        sysctls = config.boot.kernel.sysctl;
        slices = config.sinnix.runtime.inventory.slices;
        swap =
          (map (swap: {
            device = swap.device or (swap.label or (swap.uuid or ""));
            priority = swap.priority or 0;
          }) config.swapDevices)
          ++ lib.optional config.zramSwap.enable {
            device = "/dev/zram0";
            priority = config.zramSwap.priority;
          };
        journald = {
          storage = config.services.journald.settings.Journal.Storage or "auto";
          extraConfig = config.environment.etc."systemd/journald.conf".text;
        };
        zram = {
          enable = config.zramSwap.enable;
          memoryMax = config.zramSwap.memoryMax;
          algorithm = config.zramSwap.algorithm;
          priority = config.zramSwap.priority;
        };
        iocost = {
          enabled = config.sinnix.machine.isDesktop;
          path = "/sys/fs/cgroup/io.cost.qos";
        };
        earlyoom = {
          enable = config.services.earlyoom.enable;
          freeMemThreshold = config.services.earlyoom.freeMemThreshold;
          freeSwapThreshold = config.services.earlyoom.freeSwapThreshold;
          extraArgs = config.services.earlyoom.extraArgs;
        };
        generation = {
          revision = config.system.configurationRevision;
          kernel = config.boot.kernelPackages.kernel.version;
          nvidia =
            if config ? hardware.nvidia && config.sinnix.gpu.mode != "igpu" then
              config.hardware.nvidia.package.version
            else
              null;
        };
      };
    };
    meta = {
      configurationRevision = config.system.configurationRevision;
    };
  };

in
{
  environment.etc."sinnix/filesystem-layout.json".source =
    ../pkgs/sinnix-lib/sinnix_lib/filesystem-layout.json;
  environment.etc."sinnix/config.json" = {
    text = builtins.toJSON configDump;
    mode = "0444";
  };
}
