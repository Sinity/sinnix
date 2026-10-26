# Sinex on this host: its Sinnix options. The host imports Sinex's NixOS module and
# modules/services/sinex/bridge.nix, which places its state, secrets and units;
# the host's own configuration names the sources under `services.sinex.sources`.
{ lib, ... }:
{
  options.sinnix.services.sinex = {
    enable = lib.mkEnableOption "Sinex: sinexd, its PostgreSQL and NATS, and the session service";
    retainedStores = lib.mkOption {
      type = lib.types.listOf lib.types.str;
      default = [ ];
      description = ''
        Content stores of earlier Sinex deployments, kept in place under dated
        names. The sinex-blobs Borg job archives them with the running store.
      '';
    };
  };
}
