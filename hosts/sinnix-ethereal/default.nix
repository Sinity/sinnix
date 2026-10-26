{ ... }:
{
  imports = [
    ./hardware-configuration.nix
    ./boot.nix
    ./networking.nix
    ./storage.nix
    ./disko.nix
  ];

  networking.hostName = "sinnix-ethereal";

  # Headless cloud-host defaults: isDesktop=false, systemd-networkd, serial
  # console, firewall locked to ssh + tailscale0, xserver/qemuGuest disabled.
  sinnix.profiles.cloud.enable = true;

  sinnix.services.tailscale = {
    enable = true;
    tags = [ "tag:infra" ];
    useRoutingFeatures = "client";
  };

  # Allow root login via SSH for break-glass / nixos-anywhere rebuilds.
  # The cloud profile already locks the firewall to ssh + tailscale.
  services.openssh.settings.PermitRootLogin = "prohibit-password";

  programs.zsh.enable = true;
}
