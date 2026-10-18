{ inputs, ... }:
{
  perSystem =
    { pkgs, ... }:
    let
      host = inputs.self.nixosConfigurations.sinnix-prime;
      native = host.pkgs.nats-server;
    in
    {
      checks.nats-monitor-boundary =
        assert pkgs.lib.hasPrefix "${native}/bin/nats-server "
          host.config.systemd.services.nats.serviceConfig.ExecStart;
        assert host.config.systemd.services.nats.restartIfChanged;
        assert !host.config.systemd.services.nats.reloadIfChanged;
        assert host.config.systemd.services.nats.wantedBy == [ ];
        assert !host.config.services.sinex.runtime.restartOnSwitch;
        assert !host.config.systemd.services.postgresql.restartIfChanged;
        pkgs.runCommand "nats-monitor-boundary-check" { nativeBuildInputs = [ pkgs.python3 ]; } ''
          python3 ${./nats_monitor_boundary.py} ${native}/bin/nats-server
          touch "$out"
        '';
    };
}
