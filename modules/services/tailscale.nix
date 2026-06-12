# Tailscale wrapper.
#
# Thin opinion layer over upstream `services.tailscale`. Owns:
#   - the authkey-file convention (`/run/agenix/tailscale-authkey`)
#   - tag injection via extraUpFlags
#   - default routing posture (client)
#   - systemd ordering against agenix decrypt
#
# Inert until explicitly enabled per host. Default routing/firewall changes
# only land when `sinnix.services.tailscale.enable = true`.
{
  config,
  lib,
  ...
}:
let
  cfg = config.sinnix.services.tailscale;
  authKeyArg = "--auth-key=file:${cfg.authKeyFile}";
  tagArg = lib.optionalString (
    cfg.tags != [ ]
  ) "--advertise-tags=${lib.concatStringsSep "," cfg.tags}";
  exitNodeArg = lib.optionalString cfg.enableExitNode "--advertise-exit-node";
in
{
  options.sinnix.services.tailscale = {
    enable = lib.mkEnableOption "Tailscale mesh networking";

    authKeyFile = lib.mkOption {
      type = lib.types.path;
      default = "/run/agenix/tailscale-authkey";
      description = "Path to the agenix-decrypted Tailscale auth key file.";
    };

    tags = lib.mkOption {
      type = lib.types.listOf lib.types.str;
      default = [ ];
      example = [ "tag:workstation" ];
      description = ''
        Tags to advertise via `tailscale up --advertise-tags=`. Must be
        pre-authorized in the tailnet ACL `tagOwners` map.
      '';
    };

    useRoutingFeatures = lib.mkOption {
      type = lib.types.enum [
        "none"
        "client"
        "server"
        "both"
      ];
      default = "client";
      description = "Passed through to upstream services.tailscale.useRoutingFeatures.";
    };

    enableMagicDNS = lib.mkOption {
      type = lib.types.bool;
      default = true;
      description = "Whether the node should request MagicDNS from the control plane.";
    };

    enableExitNode = lib.mkOption {
      type = lib.types.bool;
      default = false;
      description = "Advertise this node as an exit node (requires server-side approval).";
    };

    interfaceName = lib.mkOption {
      type = lib.types.str;
      default = "tailscale0";
      description = "Tailscale network interface name.";
    };
  };

  config = lib.mkIf cfg.enable {
    services.tailscale = {
      enable = true;
      openFirewall = true;
      useRoutingFeatures = cfg.useRoutingFeatures;
      interfaceName = cfg.interfaceName;
      extraUpFlags = lib.filter (s: s != "") [
        authKeyArg
        tagArg
        exitNodeArg
        (lib.optionalString (!cfg.enableMagicDNS) "--accept-dns=false")
      ];
    };

    # Tailscale's autoconnect unit needs the authkey at start time.
    systemd.services.tailscaled-autoconnect = {
      after = [ "agenix.service" ];
      requires = [ "agenix.service" ];
    };
  };
}
