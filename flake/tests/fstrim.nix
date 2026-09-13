{ inputs, ... }:
{
  perSystem =
    { pkgs, ... }:
    let
      host = inputs.self.nixosConfigurations.sinnix-prime.config;
      service = host.systemd.services.sinnix-fstrim.serviceConfig;
      timer = host.systemd.timers.sinnix-fstrim;
      surface = host.sinnix.runtime.inventory.surfaces.sinnix-fstrim;
    in
    {
      checks.sinnix-fstrim-policy =
        assert service.Type == "oneshot";
        assert service.Nice == 10;
        assert service.IOSchedulingClass == "idle";
        assert service.IOSchedulingPriority == 7;
        assert timer.timerConfig.OnCalendar == "weekly";
        assert timer.timerConfig.RandomizedDelaySec == "1h";
        assert timer.timerConfig.Persistent == true;
        assert timer.wantedBy == [ "timers.target" ];
        assert surface.resourceClass == "background";
        assert surface.effectiveResources.CPUWeight == 5;
        assert surface.effectiveResources.IOWeight == 5;
        pkgs.runCommand "sinnix-fstrim-policy" { } "touch $out";
    };
}
