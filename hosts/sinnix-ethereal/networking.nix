# sinnix-ethereal networking — Hetzner AX42 bare metal.
#
# The cloud profile sets networking.useNetworkd = true and locks the
# firewall to ssh + tailscale0. We just declare the main uplink here.
# Hetzner provides DHCPv4 and SLAAC for IPv6 out of the box.
#
# TODO: confirm interface name once the box is up (Hetzner AX42 usually
# enumerates as `enp*s0` or `eno1`). Network-online ordering is handled
# by systemd-networkd; the wildcard match means we don't have to know the
# name at flake-evaluation time.
{ lib, ... }:
{
  networking.useDHCP = lib.mkForce false;

  systemd.network = {
    enable = true;
    networks."10-uplink" = {
      matchConfig.Name = "en*";
      networkConfig = {
        DHCP = "ipv4";
        IPv6AcceptRA = true;
      };
      linkConfig.RequiredForOnline = "routable";
    };
  };

  # Override the cloud profile's mkForce on TCP 22 only if extra ports are
  # ever needed. Keep this list empty so the profile remains authoritative.
}
