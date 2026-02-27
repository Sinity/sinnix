# System Introspection: config dump and health policy generation
#
# Generates at build time:
# - /etc/sinnix/config.json   — Serialized config.sinnix attrset (for any consumer)
# - /etc/sinnix/health-policy.json — Auto-derived health checks (for sentinel)
#
# The health policy maps enabled sinnix services to their systemd units,
# capture directories to freshness thresholds, and mounts to disk pressure
# limits. Adding a new service module and registering it in serviceMonitoring
# is all that's needed to get automatic health monitoring.
{
  lib,
  config,
  ...
}:
let
  cfg = config.sinnix;
  capturesRoot = cfg.paths.capturesRoot;

  # ── Service → systemd unit mapping ──────────────────────────────────
  # Add entries here when creating new service modules.
  # Set to null for services that have no monitorable systemd unit.
  serviceMonitoring = {
    power-watchdog = {
      unit = "power-watchdog.service";
      type = "service";
      restartable = true;
    };
    below = {
      unit = "below.service";
      type = "service";
      restartable = true;
    };
    transmission = {
      unit = "transmission.service";
      type = "service";
      restartable = true;
    };
    terminal-capture = null; # Shell hook via asciinema exec, no persistent daemon
    polylogue = {
      unit = "polylogue-run.timer";
      type = "timer";
      restartable = false;
    };
    sinex = null; # Complex multi-service stack — skip for now
    sentinel = null; # Self-monitoring would be recursive
  };

  # ── Capture → freshness mapping ─────────────────────────────────────
  # Only captures that are continuously produced by services.
  # Event-driven captures (screenshot, audio) can't have freshness checks.
  captureMonitoring = lib.filter (x: x != null) [
    (
      if (cfg.services.power-watchdog.enable or false) then
        {
          name = "power-watchdog";
          path = "${capturesRoot}/power-watchdog";
          maxStaleHours = 0.1; # Updates every second
        }
      else
        null
    )
    (
      if (cfg.services.terminal-capture.enable or false) then
        {
          name = "asciinema";
          path = "${capturesRoot}/asciinema";
          maxStaleHours = 24; # Terminal might be idle
        }
      else
        null
    )
    (
      if (cfg.features.desktop.activitywatch.enable or false) then
        {
          name = "activitywatch";
          path = "${capturesRoot}/activitywatch";
          maxStaleHours = 24; # Desktop might be idle
        }
      else
        null
    )
  ];

  # ── Mount monitoring ────────────────────────────────────────────────
  mountMonitoring = [
    {
      path = cfg.paths.realmRoot;
      warnPct = 80;
      failPct = 90;
    }
    {
      path = cfg.paths.neoOuterRealm;
      warnPct = 80;
      failPct = 90;
    }
  ];

  # ── Backup monitoring ───────────────────────────────────────────────
  backupMonitoring = {
    snapshotDirs = [
      "${cfg.paths.realmRoot}/.snapshots"
      "/.snapshots"
      "${cfg.paths.neoOuterRealm}/.snapshots"
    ];
    backupTarget = "${cfg.paths.neoOuterRealm}/backups/realm";
    maxStaleHours = 2;
  };

  # ── Journal pattern checks ─────────────────────────────────────────
  journalChecks = [
    {
      pattern = "oom_reaper|Out of memory";
      severity = "fail";
      window = "1h";
    }
    {
      pattern = "BTRFS.*error";
      severity = "warn";
      window = "24h";
    }
  ];

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

  enabledBundles = lib.filter (
    name:
    let
      b = cfg.bundles.${name} or { };
    in
    builtins.isAttrs b && b ? enable && b.enable
  ) (builtins.attrNames (cfg.bundles or { }));

  # ── Build service health checks from enabled services ───────────────
  enabledServiceChecks = lib.filter (x: x != null) (
    lib.mapAttrsToList (
      name: meta:
      if meta != null && (builtins.elem name enabledServices) then meta // { inherit name; } else null
    ) serviceMonitoring
  );

  # Always monitor btrbk (configured by backup.nix, not sinnix.services)
  btrbkChecks = [
    {
      name = "btrbk";
      unit = "btrbk.timer";
      type = "timer";
      restartable = false;
    }
    {
      name = "btrbk-health";
      unit = "btrbk-health.timer";
      type = "timer";
      restartable = false;
    }
  ];

  # ── Assemble health policy ─────────────────────────────────────────
  healthPolicy = {
    services = enabledServiceChecks ++ btrbkChecks;
    captures = captureMonitoring;
    mounts = mountMonitoring;
    backups = backupMonitoring;
    journal = journalChecks;
  };

  # ── Config dump (selective serialization for safety) ────────────────
  configDump = {
    sinnix = {
      inherit (cfg)
        user
        machine
        paths
        projects
        storage
        ;
      secrets = {
        inherit (cfg.secrets) enable;
        paths = cfg.secrets.paths or { };
      };
    };
    meta = {
      hostname = config.networking.hostName;
      stateVersion = config.system.stateVersion;
      inherit enabledFeatures enabledServices enabledBundles;
      captures.directories = {
        asciinema = "${capturesRoot}/asciinema";
        screenshot = "${capturesRoot}/screenshot";
        audio = "${capturesRoot}/audio";
        keylog = "${capturesRoot}/keylog";
        syslog = "${capturesRoot}/syslog";
        power-watchdog = "${capturesRoot}/power-watchdog";
        activitywatch = "${capturesRoot}/activitywatch";
        shell = "${capturesRoot}/shell";
        comms = "${capturesRoot}/comms";
        webhistory = "${capturesRoot}/webhistory";
        kitty-scrollback = "${capturesRoot}/kitty-scrollback";
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

  environment.etc."sinnix/health-policy.json" = {
    text = builtins.toJSON healthPolicy;
    mode = "0444";
  };
}
