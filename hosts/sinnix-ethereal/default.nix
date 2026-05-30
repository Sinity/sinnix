{
  inputs,
  lib,
  ...
}:
{
  imports = [
    ./hardware-configuration.nix
    ./boot.nix
    ./networking.nix
    ./storage.nix
    ./disko.nix
    # Pull in the sinex module graph so deploymentRole = replica can take
    # effect; the bridge translates sinnix options into upstream
    # services.sinex toggles.
    inputs.sinex.nixosModules.default
    ../../modules/services/sinex/bridge.nix
  ];

  networking.hostName = "sinnix-ethereal";

  # Headless cloud-host posture: isDesktop=false, systemd-networkd, serial
  # console, firewall locked to ssh + tailscale0, xserver/qemuGuest disabled.
  sinnix.profiles.cloud.enable = true;

  sinnix.services.tailscale = {
    enable = true;
    tags = [ "tag:infra" ];
    useRoutingFeatures = "client";
  };

  sinnix.services.sinex = {
    enable = true;
    prepareHost = true;
    provisionDatabase = true;
    activationProfile = "foundation";
    deploymentRole = "replica";
    environment = "prod";
    autoStart = true;
  };

  # Allow root login via SSH for break-glass / nixos-anywhere rebuilds.
  # The cloud profile already locks the firewall to ssh + tailscale.
  services.openssh.settings.PermitRootLogin = "prohibit-password";

  programs.zsh.enable = true;
}
