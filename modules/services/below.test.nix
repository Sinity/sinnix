{
  mkServiceTest,
  ...
}:
mkServiceTest {
  name = "services-below";
  service = "below";
  assertions = config: [
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
