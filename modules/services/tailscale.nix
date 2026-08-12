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
  mkServiceModule,
  lib,
  ...
}@args:
mkServiceModule {
  name = "tailscale";
  description = "Tailscale mesh networking";
  extraOptions = {
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
  configFn =
    { cfg, lib, ... }:
    let
      tagArg = lib.optionalString (
        cfg.tags != [ ]
      ) "--advertise-tags=${lib.concatStringsSep "," cfg.tags}";
      exitNodeArg = lib.optionalString cfg.enableExitNode "--advertise-exit-node";
    in
    {
      services.tailscale = {
        enable = true;
        openFirewall = true;
        inherit (cfg) useRoutingFeatures;
        inherit (cfg) interfaceName;
        # Upstream only generates the tailscaled-autoconnect unit when
        # authKeyFile is set; passing the key via extraUpFlags left that
        # unit with no ExecStart (found live 2026-08-12, sinnix-is8).
        authKeyFile = cfg.authKeyFile;
        extraUpFlags = lib.filter (s: s != "") [
          tagArg
          exitNodeArg
          (lib.optionalString (!cfg.enableMagicDNS) "--accept-dns=false")
        ];
      };

      # No agenix ordering needed: agenix decrypts during system activation,
      # before units start. (The previous requires/after on "agenix.service"
      # referenced a unit that does not exist -- agenix is an activation
      # script, not a service -- which made autoconnect fail to load.)
    };
} args
