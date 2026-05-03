{ lib, mkServiceTest, ... }:
mkServiceTest {
  name = "services-below";
  service = "below";
  assertions =
    config:
    let
      watchdogEnv = config.systemd.services.sinnix-pressure-watchdog.serviceConfig.Environment or [ ];
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
        assertion = builtins.any (
          pkg: lib.hasInfix "gawk" (toString pkg)
        ) config.systemd.services.sinnix-pressure-watchdog.path;
        message = "Pressure watchdog runtime path must include awk";
      }
      {
        assertion =
          builtins.elem "HOME=/var/log/below/home" watchdogEnv
          && builtins.elem "XDG_CACHE_HOME=/var/log/below/cache" watchdogEnv
          && builtins.elem "XDG_STATE_HOME=/var/log/below/state" watchdogEnv;
        message = "Pressure watchdog must provide HOME/XDG paths for below dump";
      }
    ];
}
