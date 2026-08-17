# System Introspection: config dump generation
#
# Generates at build time:
# - /etc/sinnix/config.json   — Serialized config.sinnix attrset (for any consumer)
{
  lib,
  config,
  ...
}:
let
  cfg = config.sinnix;
  inherit (cfg.paths) activityRoot machineRoot commsRoot;

  # ── Collect enabled features ────────────────────────────────────────
  collectEnabled =
    domain: features:
    lib.concatLists (
      lib.mapAttrsToList (
        name: value:
        if builtins.isAttrs value && value ? enable && value.enable then [ "${domain}.${name}" ] else [ ]
      ) features
    );

  enabledFeatures = lib.concatLists (lib.mapAttrsToList collectEnabled (cfg.features or { }));

  enabledServices = lib.filter (
    name:
    let
      svc = cfg.services.${name} or { };
    in
    builtins.isAttrs svc && svc ? enable && svc.enable
  ) (builtins.attrNames (cfg.services or { }));

  # ── Config dump (selective serialization for safety) ────────────────
  configDump = {
    sinnix = {
      inherit (cfg)
        user
        machine
        paths
        projects
        ;
      secrets = {
        inherit (cfg.secrets) enable;
        paths = cfg.secrets.paths or { };
      };
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
          storage = config.services.journald.storage;
          extraConfig = config.services.journald.extraConfig;
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
      hostname = config.networking.hostName;
      configurationRevision = config.system.configurationRevision;
      stateVersion = config.system.stateVersion;
      inherit enabledFeatures enabledServices;
      captures.directories = {
        asciinema = "${activityRoot}/asciinema";
        screenshot = "${activityRoot}/screenshot";
        audio = "${activityRoot}/audio";
        keylog = "${activityRoot}/keylog";
        syslog = "${machineRoot}/syslog";
        machine = machineRoot;
        activitywatch = "${activityRoot}/activitywatch/activitywatch";
        shell = "${activityRoot}/shell";
        comms = "${commsRoot}/comms";
        webhistory = "${activityRoot}/webhistory";
        kitty-scrollback = "${activityRoot}/kitty-scrollback";
      };
      firewallPorts = {
        tcp = config.networking.firewall.allowedTCPPorts;
        udp = config.networking.firewall.allowedUDPPorts;
      };
    };
  };

in
{
  environment.etc."sinnix/config.json" = {
    text = builtins.toJSON configDump;
    mode = "0444";
  };
}
