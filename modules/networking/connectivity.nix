{
  config,
  lib,
  pkgs,
  host,
  ...
}:
let
  cfg = config.sinnix.networking.enable;
in
{
  options.sinnix.networking.enable = lib.mkOption {
    type = lib.types.bool;
    default = false;
    description = "Enable NetworkManager, resolved, SSH, and Bluetooth defaults.";
  };

  config = lib.mkIf cfg {
    networking = {
      hostName = host;
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
      enable = true;
      settings.Policy.AutoEnable = true;
    };

    environment.systemPackages = with pkgs; [
      networkmanagerapplet
      bluez
      bluez-tools
    ];
  };
}
