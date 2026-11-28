{ inputs, ... }:
{
  perSystem =
    { pkgs, ... }:
    let
      host = inputs.self.nixosConfigurations.sinnix-prime.config;
      realm = host.fileSystems."/realm";
      sinex = host.fileSystems."/var/lib/sinex";
    in
    {
      checks.sinnix-realm-discard =
        assert realm.device == sinex.device;
        assert builtins.elem "discard=async" realm.options;
        assert builtins.elem "discard=async" sinex.options;
        assert builtins.elem "nodiscard" host.fileSystems."/".options;
        assert !(host.systemd.timers ? sinnix-fstrim);
        assert !(host.systemd.services ? sinnix-fstrim);
        pkgs.runCommand "sinnix-realm-discard" { } "touch $out";
    };
}
