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
        assertion =
          !(config.systemd.services ? sinnix-pressure-watchdog)
          && !(lib.hasInfix "pressureWatch" belowModule)
          && !(lib.hasInfix "set-property --runtime" belowModule);
        message = "Below must remain a recorder, not an automatic pressure intervention daemon";
      }
      {
        assertion =
          let
            below = config.systemd.services.below.serviceConfig;
          in
          below.Slice == "system-critical.slice"
          && below.Nice == -5
          && below.IOSchedulingClass == "best-effort"
          && below.IOSchedulingPriority == 0;
        message = "below.service must run in system-critical.slice with Nice=-5 / best-effort prio 0";
      }
    ];
}
