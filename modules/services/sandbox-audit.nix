# Kernel audit of refused writes, plus a static check that no unit is confined
# out of its own declared output. Sandboxing denies writes silently; this makes
# both the denial and the resulting gap observable.
{
  mkServiceModule,
  pkgs,
  lib,
  config,
  helpers,
  ...
}@args:
let
  username = config.sinnix.user.name;
  scriptPkgs = helpers.mkSinnixPackagesFor pkgs;
  auditLane = "${config.sinnix.paths.capturesRoot}/audit";
  auditState = "/realm/state/cursors/audit-drain";
in
mkServiceModule {
  name = "sandbox-audit";
  description = "Kernel denial auditing and confinement-vs-declared-output checks";
  extraOptions = {
    kernelAudit = lib.mkOption {
      type = lib.types.bool;
      default = true;
      description = "Enable auditd and the syscall rules recording refused writes.";
    };
    auditEACCES = lib.mkOption {
      type = lib.types.bool;
      default = false;
      description = ''
        Also record EACCES, not just EROFS/EPERM. Ordinary software probes
        unreadable paths constantly, so this is high-volume; EROFS is the
        signal that a mount-namespace sandbox refused a write.
      '';
    };
    intervalMinutes = lib.mkOption {
      type = lib.types.ints.positive;
      default = 60;
      description = "Minutes between audit drains and confinement checks.";
    };
  };
  configFn =
    { cfg, config, ... }:
    {
      # Two units, so the surfaces are declared here rather than through the
      # factory's single-surface argument.
      sinnix.runtime.surfaces = {
        sandbox-audit-drain = {
          unit = "sinnix-audit-drain.service";
          manager = "system";
          resourceClass = "observability";
          observe.enable = true;
          captures = [
            {
              name = "audit-denials";
              path = auditLane;
              eventDriven = true;
            }
          ];
        };
        sandbox-audit-check = {
          unit = "sinnix-sandbox-audit.service";
          manager = "system";
          resourceClass = "observability";
          observe.enable = true;
        };
      };

      environment.systemPackages = [
        scriptPkgs.sinnix-sandbox-audit
        scriptPkgs.sinnix-audit-drain
      ];

      systemd.tmpfiles.rules = [
        "d ${auditLane} 0775 ${username} users -"
        "d ${auditState} 0755 root root -"
      ];

      security.auditd.enable = cfg.kernelAudit;
      security.audit = lib.mkIf cfg.kernelAudit {
        enable = true;
        rules = [
          # Refused writes. EROFS is precisely the mount-namespace refusal
          # that loses data silently; EPERM is its capability-shaped twin.
          "-a always,exit -F arch=b64 -S openat,creat,mkdirat,renameat2,unlinkat,truncate -F exit=-EROFS -k sinnix-denied"
          "-a always,exit -F arch=b64 -S openat,creat,mkdirat,renameat2,unlinkat,truncate -F exit=-EPERM -k sinnix-denied"
          # Process and privilege telemetry: what FAILED to run, and who
          # changed identity to run something.
          #
          # success=0 is load-bearing, not a narrowing of convenience. The
          # unqualified form of this rule (every execve by any uid>=1000)
          # emitted 3.27 MILLION records per hour on 2026-08-16 -- ~57k/min,
          # five records apiece with a full hex PROCTITLE -- because an
          # agent workstation spawns processes at that rate all day. It cost
          # 23 GiB/day on the wear-limited root SSD via auditd's own log,
          # plus a duplicate copy in the journal, and it held the kernel's
          # audit backlog wait at 54s (backlog_wait_time_actual), meaning
          # every exec on the box was being throttled behind it. None of it
          # was ever read: the drain harvested 554 records that day out of
          # roughly 82 million emitted.
          #
          # Successful execs are already captured three times over by lanes
          # that carry far more context -- Atuin shell history, asciinema
          # terminal recordings, and agent session transcripts -- so the
          # blanket rule bought no evidence those lanes lack.
          #
          # Nor is "all FAILED execs" a viable narrowing, which measurement
          # settled rather than reasoning: 1771 of 1771 sampled failures were
          # exit=-2 (ENOENT), because a shell resolving a bare command name
          # execve()s it against every PATH entry until one hits. That is a
          # second firehose wearing the first one's clothes.
          #
          # A refusal is the event with security meaning: something tried to
          # run a binary it was not permitted to run. EACCES and EPERM only,
          # which is rare enough to read.
          "-a always,exit -F arch=b64 -S execve -F auid>=1000 -F auid!=-1 -F exit=-EACCES -k sinnix-exec-refused"
          "-a always,exit -F arch=b64 -S execve -F auid>=1000 -F auid!=-1 -F exit=-EPERM -k sinnix-exec-refused"
          "-a always,exit -F arch=b64 -S setuid,setgid,setreuid,setregid -F auid>=1000 -F auid!=-1 -k sinnix-privchange"
          # System-shape changes worth reconstructing after the fact.
          #
          # There is deliberately NO mount/umount2 rule. It recorded systemd
          # building a mount namespace for every sandboxed unit start -- 4.4
          # million records, dominated by capture-awair and capture-monitor,
          # which start every 60s and 300s at ~120 mount calls each. Scoping
          # it by auid does not separate that from a real mount, which
          # measurement showed after reasoning had predicted otherwise: both
          # of those units live in the operator's user manager, so their
          # namespace setup carries auid=1000 exactly like a mount the
          # operator typed. The syscall cannot tell the two apart on this
          # host, and the question the rule was meant to answer -- what is
          # mounted, and when did that change -- is answered directly by
          # /proc/self/mountinfo and by systemd's own *.mount unit
          # transitions in the journal.
          "-a always,exit -F arch=b64 -S init_module,finit_module,delete_module -k sinnix-module"
          "-a always,exit -F arch=b64 -S clock_settime,settimeofday -k sinnix-time"
        ]
        ++ lib.optionals cfg.auditEACCES [
          "-a always,exit -F arch=b64 -S openat,creat,mkdirat,renameat2,unlinkat,truncate -F exit=-EACCES -k sinnix-denied"
        ];
      };

      # Every kernel audit record was being written TWICE: once by auditd to
      # /var/log/audit/audit.log, and once by journald, which subscribes to
      # the same netlink socket whenever services.journald.audit is on (it
      # defaults to "keep"). auditd is the consumer with the tooling
      # (ausearch, the drain, the lake), so it keeps the records; the journal
      # keeps none. This is also what stops audit volume from crowding out
      # everything else in `journalctl` -- on 2026-08-16 audit was 3270224 of
      # the 3272000 records in the hour, which is what a "readable journal"
      # loses to.
      services.journald.audit = lib.mkIf cfg.kernelAudit false;
      # Audit=false alone is not enough, which is only visible by measuring:
      # it stops journald turning kernel auditing ON, but journald still
      # RECEIVES every record through this socket, which NixOS wants
      # unconditionally. With the setting flipped and the socket still up,
      # 789 audit records still reached the journal in 90 seconds.
      systemd.sockets.systemd-journald-audit.wantedBy = lib.mkIf cfg.kernelAudit (lib.mkForce [ ]);

      # auditd ships with no size ceiling, so its log grows without bound on
      # whatever filesystem /var/log lives on -- here the wear-limited root
      # SSD, where it had reached 5.8 GB in six hours. The lake is the
      # durable copy (the drain archives every record before rotation can
      # reach it), so these logs only need to cover the window between
      # drains. 8 x 64 MiB is several months of the narrowed rule set above
      # while capping the root disk at half a gigabyte.
      security.auditd.settings = lib.mkIf cfg.kernelAudit {
        max_log_file = 64;
        num_logs = 8;
        max_log_file_action = "rotate";
      };

      systemd.services.sinnix-audit-drain = lib.mkIf cfg.kernelAudit {
        description = "Drain kernel audit denial records into the capture lake";
        serviceConfig = lib.sinnix.mkRuntimeServiceConfig {
          runtimeInventory = config.sinnix.runtime.inventory;
          unit = "sinnix-audit-drain.service";
          overrides = {
            Type = "oneshot";
            ExecStart = "${scriptPkgs.sinnix-audit-drain}/bin/sinnix-audit-drain";
            TimeoutStartSec = "300s";
          };
        };
      };

      systemd.services.sinnix-sandbox-audit = {
        description = "Check no unit is confined out of its declared output";
        serviceConfig = lib.sinnix.mkRuntimeServiceConfig {
          runtimeInventory = config.sinnix.runtime.inventory;
          unit = "sinnix-sandbox-audit.service";
          overrides = {
            Type = "oneshot";
            ExecStart = "${scriptPkgs.sinnix-sandbox-audit}/bin/sinnix-sandbox-audit --quiet";
            TimeoutStartSec = "300s";
          };
        };
      };

      systemd.timers.sinnix-audit-drain = lib.mkIf cfg.kernelAudit {
        description = "Periodic kernel audit drain";
        wantedBy = [ "timers.target" ];
        timerConfig = {
          OnBootSec = "10min";
          OnUnitActiveSec = "${toString cfg.intervalMinutes}min";
          AccuracySec = "1min";
        };
      };

      systemd.timers.sinnix-sandbox-audit = {
        description = "Periodic confinement-vs-declared-output check";
        wantedBy = [ "timers.target" ];
        timerConfig = {
          OnBootSec = "15min";
          OnUnitActiveSec = "${toString cfg.intervalMinutes}min";
          AccuracySec = "5min";
        };
      };
    };
} args
