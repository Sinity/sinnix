# System diagnostics and introspection tools
#
# Hardware introspection and performance-analysis tooling, boot-metrics
# capture, journal indexing, and persistent journald logging.
{
  pkgs,
  lib,
  config,
  inputs,
  helpers,
  ...
}:
let
  inherit (config.sinnix.machine) isDesktop;
  inherit (config.sinnix.paths) capturesRoot;
  username = config.sinnix.user.name;
  scriptPkgs = helpers.mkSinnixPackagesFor pkgs;

  journaldBaseDir = "${capturesRoot}/syslog";
  bootMetricsDir = "${journaldBaseDir}/boot-metrics";
  journalArchiveDir = "${journaldBaseDir}/journal";

  coreDiagnostics = with pkgs; [
    hwinfo
    inxi
    lshw
    smartmontools
    nvme-cli
    hdparm
  ];

  captureBootMetrics = pkgs.writeShellApplication {
    name = "capture-boot-metrics";
    runtimeInputs = with pkgs; [
      coreutils
      findutils
      util-linux
      systemd
    ];
    text = ''
      set -euo pipefail
      BOOT_ID="$(cat /proc/sys/kernel/random/boot_id)"
      OUT_DIR="${bootMetricsDir}/$BOOT_ID"
      mkdir -p "$OUT_DIR"
      systemd-analyze time > "$OUT_DIR/time.txt"
      systemd-analyze blame > "$OUT_DIR/blame.txt"
      journalctl -b -p 0..3 > "$OUT_DIR/journal-errors.log"
      dmesg > "$OUT_DIR/dmesg.log"
    '';
  };

in
{
  config = {
    environment.systemPackages = lib.mkIf isDesktop (
      coreDiagnostics
      ++ [
        scriptPkgs.hogkill
        scriptPkgs.asbl-no-moar
        scriptPkgs.nuke-builds
        scriptPkgs.sinnix-observe
        scriptPkgs."sinnix-free-headroom"
        scriptPkgs.machine-experiment-run
        scriptPkgs.syslog-index
      ]
    );

    # User-owned: these hold boot-metrics captures, not journald's own store.
    systemd.tmpfiles.rules = [
      "d ${journaldBaseDir} 0750 ${username} users -"
      "d ${bootMetricsDir} 0750 ${username} users -"
      "d ${journaldBaseDir}/index 0750 ${username} users -"
    ];

    # Cross-host default; sinnix-prime replaces it wholesale via mkForce with
    # wear-endurance-tuned values.
    services.journald.extraConfig = ''
      Storage=persistent
      Compress=yes

      # Corruption resilience: sync every 30s (default 5min) and keep files
      # small, so power loss costs at most 30s of logs and 100MB of blast
      # radius.
      SyncIntervalSec=30s
      SystemMaxFileSize=100M

      SystemMaxUse=50G
      SystemKeepFree=10G

      # Size is the only retention limit.
      MaxRetentionSec=0

      # Rotate daily to limit the blast radius of corruption.
      MaxFileSec=1day

      RateLimitIntervalSec=30s
      RateLimitBurst=500

      ForwardToSyslog=no
    '';

    systemd.services.capture-boot-metrics = {
      description = "Capture boot metrics";
      # systemd-analyze needs FinishTimestampMonotonic != 0, only set once
      # every boot service has finished (2+ min with slow nofail mounts).
      after = [
        "systemd-journald.service"
        "multi-user.target"
      ];
      serviceConfig = {
        Type = "oneshot";
        ExecStart = "${captureBootMetrics}/bin/capture-boot-metrics";
      };
    };

    systemd.timers.capture-boot-metrics = {
      wantedBy = [ "timers.target" ];
      timerConfig = {
        OnBootSec = "3min";
        AccuracySec = "10s";
      };
    };

    # The journal is the estate's least durable capture and nothing said so:
    # /realm/state/journal is its own btrfs subvolume, snapshots do not cross
    # subvolume boundaries, and so every borg archive of /realm back to
    # 2026-03 held `state/journal` as an EMPTY DIRECTORY. Meanwhile
    # MaxRetentionSec=365day is subordinate to SystemMaxUse=64G, so under the
    # 2026-08 audit firehose the real window collapsed to 6.5 hours. A year of
    # history was evicted with no copy anywhere. This copies sealed files into
    # the lake, which is an ordinary directory under /realm/data and therefore
    # inside borg coverage -- and into precisely the path syslog-index below
    # already scans, which had been reporting "journal_files: 0" since it was
    # written because nothing ever populated it.
    sinnix.runtime.surfaces.journal-archive = {
      unit = "sinnix-journal-archive.service";
      resourceClass = "observability";
      observe.enable = true;
      captures = [
        {
          name = "syslog-journal";
          path = journalArchiveDir;
          # Cadence is the timer's, but a sealed file only appears when
          # journald rotates one, which at normal volume is not every run.
          # Budget generously: silence here means "the journal is quiet",
          # which is the good case.
          eventDriven = true;
          staleAfterSeconds = 604800;
        }
      ];
    };

    systemd.services.sinnix-journal-archive = {
      description = "Copy sealed journal files into the capture lake";
      after = [
        "local-fs.target"
        "systemd-journald.service"
      ];
      unitConfig.RequiresMountsFor = [ journaldBaseDir ];
      serviceConfig = lib.sinnix.mkRuntimeServiceConfig {
        runtimeInventory = config.sinnix.runtime.inventory;
        unit = "sinnix-journal-archive.service";
        overrides = {
          Type = "oneshot";
          ExecStart = "${scriptPkgs.sinnix-journal-archive}/bin/sinnix-journal-archive";
        };
      };
    };

    systemd.timers.sinnix-journal-archive = {
      description = "Rescue sealed journal files before journald evicts them";
      wantedBy = [ "timers.target" ];
      timerConfig = {
        OnBootSec = "2min";
        # Deliberately more frequent than the hourly indexer beside it: this
        # one races journald's eviction, and the cost of a run that finds
        # nothing new is a directory listing.
        OnUnitActiveSec = "15min";
        AccuracySec = "1min";
      };
    };

    systemd.services.syslog-index = {
      description = "Build no-loss syslog/journal capture indexes";
      after = [
        "local-fs.target"
        "systemd-journald.service"
        "sinnix-journal-archive.service"
      ];
      unitConfig.RequiresMountsFor = [ journaldBaseDir ];
      serviceConfig = {
        Type = "oneshot";
        ExecStart = "${scriptPkgs.syslog-index}/bin/syslog-index --no-edge-inspect";
      };
    };

    systemd.timers.syslog-index = {
      description = "Refresh no-loss syslog/journal capture indexes";
      wantedBy = [ "timers.target" ];
      timerConfig = {
        OnBootSec = "4min";
        OnUnitActiveSec = "1h";
        AccuracySec = "1min";
      };
    };
  };
}
