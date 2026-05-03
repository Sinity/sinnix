{ mkServiceTest, ... }:
mkServiceTest {
  name = "services-transmission";
  service = "transmission";
  assertions = config: [
    {
      assertion = config.services.transmission.enable;
      message = "Transmission must be enabled";
    }
    {
      assertion = config.systemd.services.transmission.unitConfig ? RequiresMountsFor;
      message = "Transmission must declare required mounts";
    }
  ];
}
