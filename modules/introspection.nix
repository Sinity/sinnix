# System Introspection: config dump and health policy generation
#
# Generates at build time:
# - /etc/sinnix/config.json   — Serialized config.sinnix attrset (for any consumer)
# - /etc/sinnix/health-policy.json — Auto-derived health checks (for sentinel)
#
# The health policy maps enabled sinnix services to their self-declared
# health metadata, capture directories to freshness thresholds, and mounts
# to disk pressure limits.
{
  lib,
  config,
  ...
}:
let
  cfg = config.sinnix;
  capturesRoot = cfg.paths.capturesRoot;

  # ── Feature-provided service checks ─────────────────────────────────
  # These services are implemented in feature modules rather than
  # sinnix.services.* modules, so they are listed here explicitly.
  featureServiceChecks =
    lib.optionals
      (
        (cfg.features.desktop.activitywatch.enable or false)
        && (cfg.features.desktop.activitywatch.autoStart or true)
      )
      [
        {
          name = "activitywatch";
          unit = "activitywatch.service";
          type = "user";
          restartable = true;
        }
        {
          name = "activitywatch-watcher-awatcher";
          unit = "activitywatch-watcher-awatcher.service";
          type = "user";
          restartable = true;
        }
      ];

  # ── Capture → freshness mapping ─────────────────────────────────────
  # Only captures that are continuously produced by services.
  # Event-driven captures (screenshot, audio) can't have freshness checks.
  captureMonitoring = lib.filter (x: x != null) [
    (
      if (cfg.services.machine-telemetry.enable or false) then
        {
          name = "machine-telemetry";
          path = "${capturesRoot}/machine/${config.networking.hostName}";
          maxStaleHours = 0.1; # Samples every few seconds.
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
  # Snapshot directories are monitored for recency.
  # backupTargets are the off-disk incremental targets.
  backupMonitoring = {
    snapshotDirs = [
      "${cfg.paths.realmRoot}/.btrfs/snapshot"
      "/persist/.btrfs/snapshot"
    ];
    # Borg repository freshness is intentionally not probed from the 60s
    # sentinel loop. Even read-only `borg list` can block on backup storage;
    # the dedicated Borg check timer owns that slower repository inspection.
    backupTargets = [ ];
    maxStaleHours = 24; # Increased from 2h to be more realistic for daily/hourly batches
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
  enabledServiceChecks =
    (lib.filter (x: x != null) (
      lib.mapAttrsToList (
        name: svc:
        if builtins.elem name enabledServices && svc ? health && svc.health != null then
          svc.health // { inherit name; }
        else
          null
      ) (cfg.services or { })
    ))
    ++ featureServiceChecks;

  # Always monitor btrbk (configured by backup.nix, not sinnix.services)
  btrbkChecks = [
    {
      name = "btrbk";
      unit = "btrbk.timer";
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
        machine = "${capturesRoot}/machine";
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
