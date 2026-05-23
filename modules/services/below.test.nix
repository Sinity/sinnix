{
  lib,
  mkServiceTest,
  inputs,
  ...
}:
mkServiceTest {
  name = "services-below";
  service = "below";
  assertions =
    config:
    let
      watchdogEnv = config.systemd.services.sinnix-pressure-watchdog.serviceConfig.Environment or [ ];
      watchdogPath = config.systemd.services.sinnix-pressure-watchdog.path;
      belowModule = builtins.readFile (inputs.self + "/modules/services/below.nix");
    in
    [
      {
        assertion = config.systemd.services ? below;
        message = "Below service must exist";
      }
      {
        assertion = config.environment.systemPackages != [ ];
        message = "Below package must be installed";
      }
      {
        assertion = config.systemd.services ? sinnix-pressure-watchdog;
        message = "Pressure watchdog service must exist when below is enabled";
      }
      {
        assertion = builtins.any (pkg: lib.hasInfix "gawk" (toString pkg)) watchdogPath;
        message = "Pressure watchdog runtime path must include awk";
      }
      {
        assertion = builtins.any (pkg: lib.hasInfix "util-linux" (toString pkg)) watchdogPath;
        message = "Pressure watchdog runtime path must include runuser for user-slice backoff";
      }
      {
        assertion =
          builtins.elem "HOME=/var/log/below/home" watchdogEnv
          && builtins.elem "XDG_CACHE_HOME=/var/log/below/cache" watchdogEnv
          && builtins.elem "XDG_STATE_HOME=/var/log/below/state" watchdogEnv;
        message = "Pressure watchdog must provide HOME/XDG paths for below dump";
      }
      {
        assertion =
          lib.hasInfix "/bin/sinnix-observe --format human" belowModule
          && lib.hasInfix ''--since "2 min ago"'' belowModule
          && lib.hasInfix ''--duration "60 sec"'' belowModule
          && !(lib.hasInfix "sinnix-pressure-report" belowModule);
        message = "Pressure watchdog must emit the correlated sinnix-observe report";
      }
      {
        assertion =
          lib.hasInfix "pressureWatch.backoff" belowModule
          && lib.hasInfix "set-property --runtime" belowModule
          && lib.hasInfix "backoff_active" belowModule
          && lib.hasInfix "restore_backoff" belowModule
          && lib.hasInfix "system_backoff_units" belowModule
          && lib.hasInfix "user_backoff_units" belowModule
          && !(lib.hasInfix "nix.slice" belowModule)
          && !(lib.hasInfix "sinnix.slice" belowModule)
          && !(lib.hasInfix "sinnix-maintenance.slice" belowModule)
          && !(lib.hasInfix "maintenanceCpuWeight" belowModule)
          && !(lib.hasInfix "maintenanceIoWeight" belowModule)
          && lib.hasInfix "demote_agent_heavy_processes" belowModule
          && lib.hasInfix ''*"/agent.slice/"*'' belowModule
          && lib.hasInfix "polylogue.cli maintenance" belowModule
          && lib.hasInfix "ionice -c 3 -p" belowModule
          && lib.hasInfix "runuser -u" belowModule
          && lib.hasInfix "applied PSI runtime backoff" belowModule
          && lib.hasInfix "restored PSI runtime backoff" belowModule;
        message = "Pressure watchdog must apply and restore optional runtime backoff for opportunistic slices";
      }
      # Fix D — below.service must run in system-critical.slice with priority
      # knobs so it can sample at sub-second intervals during the contention
      # it exists to capture.
      {
        assertion =
          let
            below = config.systemd.services.below.serviceConfig;
          in
          below.Slice == "system-critical.slice"
          && below.Nice == -5
          && below.IOSchedulingClass == "best-effort"
          && below.IOSchedulingPriority == 0;
        message = "below.service must run in system-critical.slice with Nice=-5 / best-effort prio 0 (Fix D)";
      }
    ];
}
