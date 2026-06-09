{
  mkServiceTest,
  ...
}:
mkServiceTest {
  name = "services-lynchpin";
  service = "lynchpin";
  extraModules = [
    {
      sinnix.services.lynchpin = {
        materializationTimer.enable = true;
      };
    }
  ];
  assertions = config: [
    {
      assertion = config.systemd.services ? lynchpin-materialize;
      message = "Lynchpin full materialization service must exist when materializationTimer is enabled";
    }
    {
      assertion = config.systemd.timers ? lynchpin-materialize;
      message = "Lynchpin full materialization timer must exist when materializationTimer is enabled";
    }
    {
      assertion = !(config.systemd.services ? lynchpin-refresh-worker);
      message = "Lynchpin must not install the legacy refresh-worker service";
    }
    {
      assertion = !(config.systemd.timers ? lynchpin-refresh-worker);
      message = "Lynchpin must not install the legacy refresh-worker timer";
    }
  ];
}
