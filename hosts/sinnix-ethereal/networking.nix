{ lib, ... }:
{
  networking.useDHCP = lib.mkDefault true;
  networking.firewall.allowedTCPPorts = [
    22
    80
    443
  ];
}
