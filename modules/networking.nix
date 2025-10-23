{
  lib,
  pkgs,
  ...
}:
let
  baseNetworkingPackages = with pkgs; [
    networkmanagerapplet
    bluez
    bluez-tools
  ];
  networkingToolPackages = with pkgs; [
    iputils
    ethtool
    iftop
    iperf3
  ];
in
{
  networking = {
    hostName = "sinnix-prime";
    networkmanager = {
      enable = true;
      dns = "systemd-resolved";
    };
  };

  services.resolved = {
    enable = true;
    dnssec = "allow-downgrade";
    domains = [ "~." ];
    dnsovertls = "opportunistic";
    fallbackDns = [
      "1.0.0.1#one.one.one.one"
      "8.8.4.4#dns.google"
      "2606:4700:4700::1001#one.one.one.one"
      "2001:4860:4860::8844#dns.google"
    ];
    extraConfig = ''
      DNS=1.1.1.1#one.one.one.one 8.8.8.8#dns.google 2606:4700:4700::1111#one.one.one.one 2001:4860:4860::8888#dns.google
      FallbackDNS=1.0.0.1#one.one.one.one 8.8.4.4#dns.google 2606:4700:4700::1001#one.one.one.one 2001:4860:4860::8844#dns.google
    '';
  };

  services.openssh = {
    enable = true;
    settings = {
      PermitRootLogin = "no";
      PasswordAuthentication = false;
      KbdInteractiveAuthentication = false;
      LogLevel = "VERBOSE";
    };
  };

  programs.mosh.enable = true;

  hardware.bluetooth = {
    enable = lib.mkDefault true;
    powerOnBoot = lib.mkDefault true;
    settings.Policy.AutoEnable = true;
  };

  hardware.bluetooth.settings.General = {
    ControllerMode = lib.mkDefault "dual";
    DiscoverableTimeout = lib.mkDefault 0;
    FastConnectable = lib.mkDefault true;
  };

  environment.systemPackages = lib.mkAfter (baseNetworkingPackages ++ networkingToolPackages);
}
