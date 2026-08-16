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
  auditState = "/realm/state/audit-drain";
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
          # Process and privilege telemetry: what ran, as whom, and who
          # changed identity to run it.
          "-a always,exit -F arch=b64 -S execve -F auid>=1000 -F auid!=-1 -k sinnix-exec"
          "-a always,exit -F arch=b64 -S setuid,setgid,setreuid,setregid -F auid>=1000 -F auid!=-1 -k sinnix-privchange"
          # System-shape changes worth reconstructing after the fact.
          "-a always,exit -F arch=b64 -S mount,umount2 -k sinnix-mount"
          "-a always,exit -F arch=b64 -S init_module,finit_module,delete_module -k sinnix-module"
          "-a always,exit -F arch=b64 -S clock_settime,settimeofday -k sinnix-time"
        ]
        ++ lib.optionals cfg.auditEACCES [
          "-a always,exit -F arch=b64 -S openat,creat,mkdirat,renameat2,unlinkat,truncate -F exit=-EACCES -k sinnix-denied"
        ];
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
