# airvpn-seed: AirVPN WireGuard tunnel for Transmission seeding
#
# Creates a WireGuard interface bound to AirVPN with policy routing
# so only Transmission traffic goes through the VPN. All other traffic
# stays on the normal connection.
#
# Requires agenix secrets:
#   secret/airvpn-seed-key.age  — WireGuard private key
#   secret/airvpn-seed-psk.age  — WireGuard preshared key
{
  mkServiceModule,
  lib,
  pkgs,
  config,
  helpers,
  ...
}@args:
let
  username = config.sinnix.user.name;
  vpnIP = "10.148.66.217";
  vpnRoutingTable = 200;
in
mkServiceModule {
  name = "airvpn-seed";
  description = "AirVPN WireGuard tunnel for Transmission seeding with policy routing";
  health = {
    unit = "wireguard-airvpn-seed.service";
    type = "service";
    restartable = true;
  };
  extraOptions = {
    forwardedPort = lib.mkOption {
      type = lib.types.int;
      default = 51413;
      description = "AirVPN forwarded port (check https://airvpn.org/ports/).";
    };
    endpoint = lib.mkOption {
      type = lib.types.str;
      default = "europe3.vpn.airdns.org:1637";
      description = "AirVPN WireGuard endpoint.";
    };
    dns = lib.mkOption {
      type = lib.types.listOf lib.types.str;
      default = [ "10.128.0.1" ];
      description = "DNS servers (VPN-internal).";
    };
    autoStart = lib.mkOption {
      type = lib.types.bool;
      default = true;
      description = ''
        Start the AirVPN WireGuard target automatically at boot. Disable this
        when Transmission is manually started and the VPN should come up only
        as part of that workflow.
      '';
    };
  };
  configFn =
    { cfg, pkgs, ... }:
    let
      keyFile = "/run/agenix/airvpn-seed-key";
      pskFile = "/run/agenix/airvpn-seed-psk";
    in
    {
      # ── WireGuard interface ─────────────────────────────────────────
      networking.wireguard.interfaces.airvpn-seed = {
        ips = [ "${vpnIP}/32" ];
        privateKeyFile = keyFile;
        mtu = 1320;
        allowedIPsAsRoutes = false;
        peers = [
          {
            publicKey = "PyLCXAQT8KkM4T+dUsOQfn+Ub3pGxfGlxkIApuig+hk=";
            presharedKeyFile = pskFile;
            endpoint = cfg.endpoint;
            # Keep WireGuard peer selection complete while routing those
            # prefixes through the dedicated policy table below.
            allowedIPs = [ "0.0.0.0/0" ];
            persistentKeepalive = 15;
          }
        ];
        postSetup = ''
          # Add default route only in custom table ${toString vpnRoutingTable}
          # This prevents the VPN from taking over normal internet traffic
          ${pkgs.iproute2}/bin/ip route replace 0.0.0.0/0 dev airvpn-seed table ${toString vpnRoutingTable}

          # Policy routing: traffic FROM VPN IP uses the VPN table
          ${pkgs.iproute2}/bin/ip rule add from ${vpnIP} table ${toString vpnRoutingTable} priority 100 2>/dev/null || true
          ${pkgs.iproute2}/bin/ip rule add from ${vpnIP} suppress_prefixlength 0 table ${toString vpnRoutingTable} priority 101 2>/dev/null || true
        '';
      };

      # ── Transmission settings ───────────────────────────────────────
      # Bind to VPN IP so all torrent traffic goes through AirVPN
      services.transmission.settings = {
        bind-address-ipv4 = vpnIP;
        peer-port = cfg.forwardedPort;
        # Port forwarding is now handled by AirVPN, not UPnP
        port-forwarding-enabled = false;
      };

      # ── Dependencies ────────────────────────────────────────────────
      # Transmission must wait for the VPN tunnel
      systemd.targets.wireguard-airvpn-seed.wantedBy = lib.mkIf (!cfg.autoStart) (lib.mkForce [ ]);

      systemd.services.transmission = {
        after = [ "wireguard-airvpn-seed.target" ];
        wants = [ "wireguard-airvpn-seed.target" ];
        # Restart Transmission when the VPN is restarted during activation.
        unitConfig.PartOf = [ "wireguard-airvpn-seed.target" ];
        # Only keep Transmission running while the wg interface is up.
        unitConfig.Requires = lib.mkForce [ ];
        unitConfig.BindsTo = [ "wireguard-airvpn-seed.target" ];
      };

      # ── Firewall: allow forwarded port on VPN interface only ────────
      networking.firewall.interfaces.airvpn-seed = {
        allowedTCPPorts = [ cfg.forwardedPort ];
        allowedUDPPorts = [ cfg.forwardedPort ];
      };
    };
} args
